"""Roda em SQLite as consultas-modelo dos relatórios, sobre fixtures com valores calculados à mão."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "core/cd2-varejo/kits/dados/scripts"))

from dados_arquivo import carregar, consultar  # noqa: E402

# Seção 3.1 de relatorio-vendas/references/relatorios.md, convertida para SQLite pela
# tabela de regras-sqlite.md: sem OFFSET 0 ROWS, marcadores trocados pelas colunas de
# vendas.csv e descrição na própria linha, em vez do join com o cadastro.
SQL_ABC_VENDAS = """
SELECT y.codigo, y.descricao, CAST(y.qtd AS float) qtd, CAST(y.valor AS float) valor,
       CAST(100.0 * y.valor / NULLIF(y.total, 0) AS float) part_pct,
       CAST(100.0 * y.acum / NULLIF(y.total, 0) AS float) acum_pct,
       CASE WHEN 100.0 * (y.acum - y.valor) / NULLIF(y.total, 0) < 80 THEN 'A'
            WHEN 100.0 * (y.acum - y.valor) / NULLIF(y.total, 0) < 95 THEN 'B' ELSE 'C' END classe
FROM (SELECT x.codigo, x.descricao, x.qtd, x.valor,
             SUM(x.valor) OVER () total,
             SUM(x.valor) OVER (ORDER BY x.valor DESC, x.codigo ROWS UNBOUNDED PRECEDING) acum
      FROM (SELECT i.codigo codigo, MAX(i.descricao) descricao,
                   SUM(i.quantidade) qtd, SUM(i.valor_liquido) valor
            FROM vendas i
            WHERE i.situacao <> 'Cancelado'
              AND i.data >= '2026-08-01' AND i.data < '2026-11-01'
            GROUP BY i.codigo
            HAVING SUM(i.valor_liquido) > 0) x) y
ORDER BY y.valor DESC, y.codigo
"""

CORE = ROOT / "core/cd2-varejo"


def secao(skill, titulo):
    """Texto da seção `titulo` (por exemplo "3.1") de relatorios.md da skill: o modelo tem de estar lá."""
    arquivo = CORE / "skills" / skill / "references/relatorios.md"
    assert arquivo.exists(), f"falta {arquivo}"
    texto = arquivo.read_text(encoding="utf-8")
    inicio = texto.index(f"### {titulo} ")
    fim = texto.find("\n### ", inicio + 1)
    return texto[inicio:] if fim < 0 else texto[inicio:fim]


# Seção 3.1 de relatorio-estoque, em SQLite: sem o join com departamento nem OFFSET, filtro
# de loja fixo em 1 e a coluna de departamento na própria linha do arquivo.
SQL_ESTOQUE_POSICAO = """
SELECT x.departamento, x.itens, x.itens_negativos, x.itens_zerados,
       CAST(x.valor_custo AS float) valor_custo, CAST(x.valor_venda AS float) valor_venda,
       CAST(100.0 * x.valor_custo / NULLIF(SUM(x.valor_custo) OVER (), 0) AS float) part_pct
FROM (SELECT s.departamento,
             SUM(CASE WHEN s.saldo > 0 THEN 1 ELSE 0 END) itens,
             SUM(CASE WHEN s.saldo < 0 THEN 1 ELSE 0 END) itens_negativos,
             SUM(CASE WHEN s.saldo = 0 THEN 1 ELSE 0 END) itens_zerados,
             SUM(CASE WHEN s.saldo > 0 THEN s.saldo * COALESCE(s.custo, 0) ELSE 0 END) valor_custo,
             SUM(CASE WHEN s.saldo > 0 THEN s.saldo * COALESCE(s.preco, 0) ELSE 0 END) valor_venda
      FROM estoque_saldo s
      WHERE s.loja = 1
      GROUP BY s.departamento) x
ORDER BY x.valor_custo DESC, x.departamento
"""

# Seção 3.1 de relatorio-compras, em SQLite: venda a custo, saldo e pendente vêm de dois
# arquivos (o pendente já somado por produto, no lugar da subconsulta de pedidos).
SQL_COMPRAS_ABC = """
SELECT z.codigo, z.descricao, CAST(z.qtd AS float) qtd, CAST(z.valor AS float) valor,
       CAST(z.part_pct AS float) part_pct, CAST(z.acum_pct AS float) acum_pct, z.classe,
       CAST(z.saldo AS float) saldo, CAST(z.dias_cobertura AS float) dias_cobertura,
       CAST(z.pendente AS float) pendente,
       CASE WHEN z.classe = 'A' AND z.saldo <= 0 THEN 'Ruptura em item crítico'
            WHEN z.classe = 'A' AND z.dias_cobertura < 7 AND z.pendente = 0 THEN 'Risco de ruptura em item crítico'
            WHEN z.classe = 'C' AND z.dias_cobertura > 90 THEN 'Excesso em item de baixa relevância'
            ELSE '' END alerta
FROM (SELECT y.codigo, y.descricao, y.qtd, y.valor, y.part_pct, y.acum_pct, y.classe,
             COALESCE(s.saldo, 0) saldo,
             COALESCE(s.saldo, 0) / NULLIF(y.qtd / 90.0, 0) dias_cobertura,
             COALESCE(s.pendente, 0) pendente
      FROM (SELECT w.codigo, w.descricao, w.qtd, w.valor,
                   100.0 * w.valor / NULLIF(w.total, 0) part_pct,
                   100.0 * w.acum / NULLIF(w.total, 0) acum_pct,
                   CASE WHEN 100.0 * (w.acum - w.valor) / NULLIF(w.total, 0) < 80 THEN 'A'
                        WHEN 100.0 * (w.acum - w.valor) / NULLIF(w.total, 0) < 95 THEN 'B' ELSE 'C' END classe
            FROM (SELECT x.codigo, x.descricao, x.qtd, x.valor,
                         SUM(x.valor) OVER () total,
                         SUM(x.valor) OVER (ORDER BY x.valor DESC, x.codigo ROWS UNBOUNDED PRECEDING) acum
                  FROM (SELECT i.codigo codigo, MAX(i.descricao) descricao,
                               SUM(i.quantidade) qtd, SUM(i.quantidade * i.custo) valor
                        FROM compras_vendas i
                        WHERE i.situacao <> 'Cancelado'
                          AND i.data >= '2026-08-01' AND i.data < '2026-11-01'
                        GROUP BY i.codigo
                        HAVING SUM(i.quantidade * i.custo) > 0) x) w) y
      LEFT JOIN compras_saldo s ON s.codigo = y.codigo) z
ORDER BY z.valor DESC, z.codigo
"""

# Seção 3.1 de relatorio-precos, em SQLite: departamento e custo unitário na própria linha.
SQL_PRECOS_MARGEM = """
SELECT x.d departamento,
       CAST(x.venda AS float) venda, CAST(x.custo AS float) custo,
       CAST(x.venda - x.custo AS float) contribuicao,
       CAST(100.0 * (x.venda - x.custo) / NULLIF(x.venda, 0) AS float) margem_pct,
       CAST(100.0 * x.venda / NULLIF(SUM(x.venda) OVER (), 0) AS float) part_venda_pct,
       CAST(100.0 * (x.venda - x.custo) / NULLIF(SUM(x.venda - x.custo) OVER (), 0) AS float) part_contrib_pct
FROM (SELECT i.departamento d, SUM(i.valor_liquido) venda,
             SUM(COALESCE(i.custo_unitario, 0) * i.quantidade) custo
      FROM precos_itens i
      WHERE i.situacao <> 'Cancelado' AND i.data >= '2026-10-01' AND i.data < '2026-11-01'
        AND COALESCE(i.custo_unitario, 0) > 0
      GROUP BY i.departamento) x
ORDER BY x.venda - x.custo DESC, x.d
"""

# Seção 3.1 de relatorio-perdas, em SQLite: departamento na própria linha da quebra, loja fixa
# em 1 e "(sem motivo)" para o motivo vazio, que a seção manda mostrar.
SQL_PERDAS_MOTIVO = """
SELECT q.departamento, COALESCE(q.motivo, '(sem motivo)') motivo, COUNT(*) ocorrencias,
       CAST(SUM(q.quantidade) AS float) qtd,
       CAST(SUM(q.quantidade * COALESCE(q.custo, 0)) AS float) valor_custo,
       CAST(100.0 * SUM(q.quantidade * COALESCE(q.custo, 0))
            / NULLIF(SUM(SUM(q.quantidade * COALESCE(q.custo, 0))) OVER (), 0) AS float) part_pct
FROM perdas_quebras q
WHERE q.loja = 1 AND q.data >= '2026-10-01' AND q.data < '2026-11-01'
GROUP BY q.departamento, COALESCE(q.motivo, '(sem motivo)')
ORDER BY valor_custo DESC, q.departamento, motivo
"""

# Seção 3.5 de relatorio-compras, em SQLite: só notas de compra, período fixo e colunas do arquivo.
SQL_COMPRAS_VARIACAO = """
SELECT t.produto, t.fornecedor, t.custo_ultima, t.custo_penultima,
       CAST(100.0 * t.custo_ultima / NULLIF(t.custo_penultima, 0) - 100.0 AS float) variacao_pct,
       t.valor_comprado
FROM (SELECT e.produto, e.fornecedor,
             CAST(MAX(CASE WHEN e.rn = 1 THEN e.custo END) AS float) custo_ultima,
             CAST(MAX(CASE WHEN e.rn = 2 THEN e.custo END) AS float) custo_penultima,
             CAST(SUM(e.qtd * e.custo) AS float) valor_comprado
      FROM (SELECT ni.produto, ni.fornecedor, ni.custo custo, ni.quantidade qtd,
                   ROW_NUMBER() OVER (PARTITION BY ni.produto, ni.fornecedor
                                      ORDER BY ni.data DESC, ni.chave DESC) rn
            FROM compras_entradas ni
            WHERE ni.operacao = 'Compra' AND ni.data >= '2026-08-01' AND ni.data < '2026-11-01') e
      GROUP BY e.produto, e.fornecedor) t
ORDER BY ABS(100.0 * t.custo_ultima / NULLIF(t.custo_penultima, 0) - 100.0) DESC
"""

# Seção 3.1 de relatorio-financeiro, em SQLite: DATEDIFF vira diferença de julianday, referência
# fixa em 31/10/2026, sem filtro de empresa e sem OFFSET.
SQL_FINANCEIRO_AGING = """
SELECT x.faixa, COUNT(*) titulos, CAST(SUM(x.saldo) AS float) valor,
       CAST(100.0 * SUM(x.saldo) / NULLIF(SUM(SUM(x.saldo)) OVER (), 0) AS float) part_pct
FROM (SELECT d.saldo,
             CASE WHEN d.dias < -90 THEN '1 vencido > 90'
                  WHEN d.dias < -60 THEN '2 vencido 61-90'
                  WHEN d.dias < -30 THEN '3 vencido 31-60'
                  WHEN d.dias <   0 THEN '4 vencido 1-30'
                  WHEN d.dias <=  7 THEN '5 a vencer 0-7'
                  WHEN d.dias <= 15 THEN '6 a vencer 8-15'
                  WHEN d.dias <= 30 THEN '7 a vencer 16-30'
                  WHEN d.dias <= 60 THEN '8 a vencer 31-60'
                  ELSE '9 a vencer > 60' END faixa
      FROM (SELECT t.saldo,
                   CAST(julianday(t.vencimento) - julianday('2026-10-31') AS integer) dias
            FROM financeiro_pagar t
            WHERE t.situacao = 'Aberto' AND t.saldo > 0) d) x
GROUP BY x.faixa
ORDER BY x.faixa
"""

# Seção 3.1 de relatorio-fiscal, em SQLite: loja 1 e outubro de 2026 fixos, situação "Autorizada"
# e a junção por loja, nota, série e modelo.
SQL_FISCAL_CFOP = """
SELECT x.cfop, x.itens, CAST(x.valor AS float) valor,
       CAST(x.icms AS float) icms, CAST(x.icms_st AS float) icms_st,
       CAST(100.0 * x.valor / NULLIF(SUM(x.valor) OVER (), 0) AS float) part_pct
FROM (SELECT i.cfop cfop, COUNT(*) itens,
             SUM(COALESCE(i.valor, 0)) valor,
             SUM(COALESCE(i.icms, 0)) icms,
             SUM(COALESCE(i.icms_st, 0)) icms_st
      FROM fiscal_itens i
      JOIN fiscal_notas h ON h.loja = i.loja AND h.nota = i.nota
                         AND h.serie = i.serie AND h.modelo = i.modelo
      WHERE h.situacao = 'Autorizada' AND h.loja = 1
        AND h.data >= '2026-10-01' AND h.data < '2026-11-01'
      GROUP BY i.cfop) x
ORDER BY x.valor DESC, x.cfop
"""

# Seção 3.1 de relatorio-contabil, em SQLite: <deb> e <cre> expandidos para o formato "uma linha
# por conta, com D ou C", competência de outubro de 2026 e exercício desde 01/01/2026.
SQL_CONTABIL_BALANCETE = """
SELECT pc.codigo, pc.descricao, pc.natureza,
       CAST(SUM(CASE WHEN l.data <  '2026-10-01' THEN CASE WHEN l.dc = 'D' THEN l.valor ELSE 0 END
                                                      - CASE WHEN l.dc = 'C' THEN l.valor ELSE 0 END
                     ELSE 0 END) AS float) saldo_anterior,
       CAST(SUM(CASE WHEN l.data >= '2026-10-01' THEN CASE WHEN l.dc = 'D' THEN l.valor ELSE 0 END ELSE 0 END) AS float) debitos,
       CAST(SUM(CASE WHEN l.data >= '2026-10-01' THEN CASE WHEN l.dc = 'C' THEN l.valor ELSE 0 END ELSE 0 END) AS float) creditos,
       CAST(SUM(CASE WHEN l.dc = 'D' THEN l.valor ELSE 0 END - CASE WHEN l.dc = 'C' THEN l.valor ELSE 0 END) AS float) saldo_atual
FROM contabil_lancamentos l
JOIN contabil_plano pc ON pc.conta = l.conta
WHERE l.situacao = 'Efetivado'
  AND l.data >= '2026-01-01' AND l.data < '2026-11-01'
GROUP BY pc.codigo, pc.descricao, pc.natureza
HAVING SUM(CASE WHEN l.dc = 'D' THEN l.valor ELSE 0 END) <> 0 OR SUM(CASE WHEN l.dc = 'C' THEN l.valor ELSE 0 END) <> 0
ORDER BY pc.codigo
"""


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name) / "base.sqlite"

    def carregar(self, *nomes):
        return carregar([FIXTURES / n for n in nomes], self.base)

    def linhas(self, sql):
        resultado = consultar(self.base, sql)
        return [dict(zip(resultado["colunas"], l)) for l in resultado["linhas"]]


class TestModelos(Base):
    def test_abc_vendas(self):
        # Em vendas.csv, dentro do período e sem cancelado:
        #   0101 Arroz    3.200 + 1.800 = 5.000  acumulado antes   0%, depois  50%  A
        #   0102 Feijão               2.000      acumulado antes  50%, depois  70%  A
        #   0103 Café                 1.500      acumulado antes  70%, depois  85%  A (cruza os 80%)
        #   0104 Açúcar               1.000      acumulado antes  85%, depois  95%  B
        #   0105 Óleo                   300      acumulado antes  95%, depois  98%  C (95% não é menor que 95)
        #   0106 Sal                    200      acumulado antes  98%, depois 100%  C
        # Soma da curva: 10.000. Fora dela: 0107 Vela (-50, líquido negativo), 0108 Fósforo
        # (700, em julho) e o cancelado de 999 do Arroz, que o TOTAL GERAL de 10.650 não traz.
        perfil = self.carregar("vendas.csv")
        self.assertEqual(perfil["tabelas"][0]["tabela_totais"], "vendas__totais")

        linhas = self.linhas(SQL_ABC_VENDAS)

        self.assertEqual([l["codigo"] for l in linhas], ["0101", "0102", "0103", "0104", "0105", "0106"])
        self.assertEqual([l["classe"] for l in linhas], ["A", "A", "A", "B", "C", "C"])
        for linha, valor, part, acum in zip(
            linhas,
            [5000.0, 2000.0, 1500.0, 1000.0, 300.0, 200.0],
            [50.0, 20.0, 15.0, 10.0, 3.0, 2.0],
            [50.0, 70.0, 85.0, 95.0, 98.0, 100.0],
        ):
            self.assertAlmostEqual(linha["valor"], valor)
            self.assertAlmostEqual(linha["part_pct"], part)
            self.assertAlmostEqual(linha["acum_pct"], acum)
        self.assertAlmostEqual(linhas[0]["qtd"], 500.0)

        # Prova da seção 3.1: soma das classes é a venda do período, e o último acumulado é 100.
        por_classe = {c: sum(l["valor"] for l in linhas if l["classe"] == c) for c in "ABC"}
        self.assertAlmostEqual(por_classe["A"], 8500.0)
        self.assertAlmostEqual(por_classe["B"], 1000.0)
        self.assertAlmostEqual(por_classe["C"], 500.0)
        self.assertAlmostEqual(sum(por_classe.values()), 10000.0)

        # Conferência com o total do próprio arquivo, que não entra na soma principal.
        total_geral = self.linhas("SELECT valor_liquido FROM vendas__totais WHERE data = 'TOTAL GERAL'")
        fora_da_curva = -50.0 + 700.0
        self.assertAlmostEqual(total_geral[0]["valor_liquido"], sum(por_classe.values()) + fora_da_curva)

    def test_estoque_posicao(self):
        self.assertIn("### 3.1 Estoque geral", secao("relatorio-estoque", "3.1"))
        # Em estoque-saldo.csv, só a loja 1 (o café da loja 2 fica fora), saldo > 0 vira valor:
        #   Mercearia: arroz 10 x 5 = 50 e feijão 20 x 4 = 80, a custo 130; a venda é 80 + 120 = 200;
        #              2 itens com saldo, 0 negativos, 1 zerado (sal)
        #   Laticínios: leite 30 x 3 = 90, a venda 135; 1 item com saldo; o queijo (-4) é negativo
        #              e fica fora do valor
        #   Bazar: vela 5, sem custo (vazio vale 0), a custo 0, a venda 5 x 3 = 15
        # Total a custo 220: Mercearia 130/220 = 59,0909%, Laticínios 90/220 = 40,9091%, Bazar 0%.
        self.carregar("estoque-saldo.csv")

        linhas = self.linhas(SQL_ESTOQUE_POSICAO)

        self.assertEqual([l["departamento"] for l in linhas], ["Mercearia", "Laticínios", "Bazar"])
        self.assertEqual([l["itens"] for l in linhas], [2, 1, 1])
        self.assertEqual([l["itens_negativos"] for l in linhas], [0, 1, 0])
        self.assertEqual([l["itens_zerados"] for l in linhas], [1, 0, 0])
        for linha, custo, venda, part in zip(
            linhas, [130.0, 90.0, 0.0], [200.0, 135.0, 15.0], [130 / 2.2, 90 / 2.2, 0.0]
        ):
            self.assertAlmostEqual(linha["valor_custo"], custo)
            self.assertAlmostEqual(linha["valor_venda"], venda)
            self.assertAlmostEqual(linha["part_pct"], part)

        # Prova da seção 3.1: soma do relatório = SUM(saldo x custo) direto na tabela, mesmos filtros, sem join.
        direto = self.linhas(
            "SELECT SUM(CASE WHEN saldo > 0 THEN saldo * COALESCE(custo, 0) ELSE 0 END) total "
            "FROM estoque_saldo WHERE loja = 1"
        )
        self.assertAlmostEqual(sum(l["valor_custo"] for l in linhas), direto[0]["total"])
        self.assertAlmostEqual(direto[0]["total"], 220.0)

    def test_compras_abc(self):
        self.assertIn("### 3.1 ABC de abastecimento", secao("relatorio-compras", "3.1"))
        # Em compras-vendas.csv, no período e sem cancelado, a venda a custo (quantidade x custo):
        #   C001 Arroz   100 x 4 + 25 x 4 = 500  antes   0%, depois  50%  A   saldo 5, pendente 0
        #   C002 Feijão  100 x 3          = 300  antes  50%, depois  80%  A   saldo 0, pendente 200
        #   C003 Óleo     30 x 5          = 150  antes  80%, depois  95%  B   saldo 100
        #   C004 Sal     100 x 0,5        =  50  antes  95%, depois 100%  C   saldo 300
        # Fora: o cancelado de 10 do Sal e a Vela de julho. Total 1.000, demanda diária = qtd / 90.
        # Cobertura em dias = saldo / demanda diária: C001 5 / (125/90) = 3,6; C002 0; C003 100 / (30/90) = 300;
        # C004 300 / (100/90) = 270. Alertas: C001 risco (A, menos de 7 dias, sem pendente); C002 ruptura
        # (A, saldo 0, mesmo com pendente); C003 nenhum (B); C004 excesso (C, mais de 90 dias).
        # O C006 está só no arquivo de saldo, não vendeu: não entra na curva e não multiplica linhas.
        self.carregar("compras-vendas.csv", "compras-saldo.csv")

        linhas = self.linhas(SQL_COMPRAS_ABC)

        self.assertEqual([l["codigo"] for l in linhas], ["C001", "C002", "C003", "C004"])
        self.assertEqual([l["classe"] for l in linhas], ["A", "A", "B", "C"])
        for linha, valor, part, acum in zip(
            linhas,
            [500.0, 300.0, 150.0, 50.0],
            [50.0, 30.0, 15.0, 5.0],
            [50.0, 80.0, 95.0, 100.0],
        ):
            self.assertAlmostEqual(linha["valor"], valor)
            self.assertAlmostEqual(linha["part_pct"], part)
            self.assertAlmostEqual(linha["acum_pct"], acum)
        self.assertEqual([l["qtd"] for l in linhas], [125.0, 100.0, 30.0, 100.0])
        self.assertEqual([l["saldo"] for l in linhas], [5.0, 0.0, 100.0, 300.0])
        self.assertEqual([l["pendente"] for l in linhas], [0.0, 200.0, 0.0, 0.0])
        for linha, dias in zip(linhas, [3.6, 0.0, 300.0, 270.0]):
            self.assertAlmostEqual(linha["dias_cobertura"], dias)
        self.assertEqual(
            [l["alerta"] for l in linhas],
            ["Risco de ruptura em item crítico", "Ruptura em item crítico", "", "Excesso em item de baixa relevância"],
        )

        # Prova da seção 3.1: soma da medida = total do período, e o cruzamento mantém o número de itens.
        self.assertAlmostEqual(sum(l["valor"] for l in linhas), 1000.0)
        sem_cruzar = self.linhas(
            "SELECT COUNT(DISTINCT codigo) itens FROM compras_vendas "
            "WHERE situacao <> 'Cancelado' AND data >= '2026-08-01' AND data < '2026-11-01'"
        )
        self.assertEqual(len(linhas), sem_cruzar[0]["itens"])

    def test_precos_margem(self):
        self.assertIn("### 3.1 Margem", secao("relatorio-precos", "3.1"))
        # Em precos-itens.csv, em outubro e sem cancelado, só entra a venda com custo maior que zero:
        #   Mercearia: M01 100 (10 x 6 = 60) + M02 200 (20 x 7 = 140) = venda 300, custo 200,
        #              contribuição 100, margem 100/300 = 33,3333%
        #   Bebidas:   B01 150 (10 x 12 = 120) = venda 150, custo 120, contribuição 30, margem 20%
        # Ficam de fora por falta de custo: B02 (custo vazio) 50 e B03 (custo 0) 40, venda sem custo 90.
        # Fora do período e do relatório: o M01 de setembro (100) e o cancelado de 50.
        # Venda com custo 450: Mercearia 300/450 = 66,6667%, Bebidas 33,3333%.
        # Contribuição total 130: Mercearia 100/130 = 76,9231%, Bebidas 23,0769%.
        self.carregar("precos-itens.csv")

        linhas = self.linhas(SQL_PRECOS_MARGEM)

        self.assertEqual([l["departamento"] for l in linhas], ["Mercearia", "Bebidas"])
        for linha, venda, custo, contrib, margem, pv, pc in zip(
            linhas,
            [300.0, 150.0],
            [200.0, 120.0],
            [100.0, 30.0],
            [100 / 3, 20.0],
            [200 / 3, 100 / 3],
            [100 / 1.3, 30 / 1.3],
        ):
            self.assertAlmostEqual(linha["venda"], venda)
            self.assertAlmostEqual(linha["custo"], custo)
            self.assertAlmostEqual(linha["contribuicao"], contrib)
            self.assertAlmostEqual(linha["margem_pct"], margem)
            self.assertAlmostEqual(linha["part_venda_pct"], pv)
            self.assertAlmostEqual(linha["part_contrib_pct"], pc)

        # Prova da seção 3.1: venda do relatório + venda sem custo = venda total do período (540).
        sem_custo = self.linhas(
            "SELECT SUM(valor_liquido) v FROM precos_itens WHERE situacao <> 'Cancelado' "
            "AND data >= '2026-10-01' AND data < '2026-11-01' AND COALESCE(custo_unitario, 0) <= 0"
        )
        total = self.linhas(
            "SELECT SUM(valor_liquido) v FROM precos_itens WHERE situacao <> 'Cancelado' "
            "AND data >= '2026-10-01' AND data < '2026-11-01'"
        )
        self.assertAlmostEqual(sem_custo[0]["v"], 90.0)
        self.assertAlmostEqual(sum(l["venda"] for l in linhas) + sem_custo[0]["v"], total[0]["v"])
        self.assertAlmostEqual(total[0]["v"], 540.0)

    def test_perdas_por_motivo(self):
        self.assertIn("### 3.1 Quebra por motivo e departamento", secao("relatorio-perdas", "3.1"))
        # Em perdas-quebras.csv, loja 1 em outubro (a quebra da loja 2 e a de setembro ficam fora), a custo:
        #   Açougue, Vencimento: 1 ocorrência, qtd 4,  4 x 12,5 = 50   35,7143% de 140
        #   Padaria, Vencimento: 2 ocorrências, qtd 15, 10 x 2 + 5 x 4 = 40   28,5714%
        #   Açougue, Outros:     1 ocorrência, qtd 1,  1 x 30 = 30   21,4286%
        #   Padaria, (sem motivo): 1 ocorrência, qtd 1, 1 x 10 = 10   7,1429% (motivo vazio)
        #   Padaria, Avaria:     1 ocorrência, qtd 2,  2 x 5 = 10   7,1429%
        # Total 140; o empate de 10 desempata por departamento e motivo, e "(" vem antes de "A".
        self.carregar("perdas-quebras.csv")

        linhas = self.linhas(SQL_PERDAS_MOTIVO)

        self.assertEqual(
            [(l["departamento"], l["motivo"]) for l in linhas],
            [
                ("Açougue", "Vencimento"),
                ("Padaria", "Vencimento"),
                ("Açougue", "Outros"),
                ("Padaria", "(sem motivo)"),
                ("Padaria", "Avaria"),
            ],
        )
        self.assertEqual([l["ocorrencias"] for l in linhas], [1, 2, 1, 1, 1])
        self.assertEqual([l["qtd"] for l in linhas], [4.0, 15.0, 1.0, 1.0, 2.0])
        for linha, valor in zip(linhas, [50.0, 40.0, 30.0, 10.0, 10.0]):
            self.assertAlmostEqual(linha["valor_custo"], valor)
            self.assertAlmostEqual(linha["part_pct"], valor / 1.4)

        # Prova da seção 3.1: total por motivo = total por departamento = total de quebras do período.
        por_motivo = self.linhas(
            "SELECT COALESCE(motivo, '(sem motivo)') k, SUM(quantidade * COALESCE(custo, 0)) v FROM perdas_quebras "
            "WHERE loja = 1 AND data >= '2026-10-01' AND data < '2026-11-01' GROUP BY 1"
        )
        por_departamento = self.linhas(
            "SELECT departamento k, SUM(quantidade * COALESCE(custo, 0)) v FROM perdas_quebras "
            "WHERE loja = 1 AND data >= '2026-10-01' AND data < '2026-11-01' GROUP BY 1"
        )
        total = sum(l["valor_custo"] for l in linhas)
        self.assertAlmostEqual(sum(l["v"] for l in por_motivo), total)
        self.assertAlmostEqual(sum(l["v"] for l in por_departamento), total)
        self.assertAlmostEqual(total, 140.0)

    def test_compras_variacao_custo(self):
        self.assertIn("### 3.5 Variação de custo de compra", secao("relatorio-compras", "3.5"))
        # Em compras-entradas.csv, só nota de compra entre agosto e outubro de 2026:
        #   E01: 05/08 a 10,00 x 100 e 10/10 a 12,00 x 50; penúltima 10, última 12,
        #        variação 12 / 10 - 1 = 20%, valor comprado 1.000 + 600 = 1.600
        #   E02: uma entrada só, 15/09 a 8,00 x 25; sem penúltima, variação vazia, valor 200
        # Fora: a bonificação do E02 (custo 0, não é compra) e o E01 de julho (9,00 x 10).
        # Total das entradas de compra do período: 1.800. E01 vem primeiro por |variação| maior.
        self.carregar("compras-entradas.csv")

        linhas = self.linhas(SQL_COMPRAS_VARIACAO)

        self.assertEqual([l["produto"] for l in linhas], ["E01", "E02"])
        self.assertEqual([l["custo_ultima"] for l in linhas], [12.0, 8.0])
        self.assertEqual(linhas[0]["custo_penultima"], 10.0)
        self.assertIsNone(linhas[1]["custo_penultima"])
        self.assertAlmostEqual(linhas[0]["variacao_pct"], 20.0)
        self.assertIsNone(linhas[1]["variacao_pct"])
        self.assertEqual([l["valor_comprado"] for l in linhas], [1600.0, 200.0])

        # Prova da seção 3.5: soma do valor comprado = total das entradas de compra, direto na tabela.
        direto = self.linhas(
            "SELECT SUM(quantidade * custo) total FROM compras_entradas "
            "WHERE operacao = 'Compra' AND data >= '2026-08-01' AND data < '2026-11-01'"
        )
        self.assertAlmostEqual(sum(l["valor_comprado"] for l in linhas), direto[0]["total"])
        self.assertAlmostEqual(direto[0]["total"], 1800.0)

    def test_financeiro_aging(self):
        self.assertIn("### 3.1 Contas a pagar por vencimento", secao("relatorio-financeiro", "3.1"))
        # Em financeiro-pagar.csv, referência 31/10/2026, só situação Aberto com saldo > 0
        # (T11 liquidado, T12 cancelado e T13 aberto de saldo zero ficam fora). Dias até o vencimento:
        #   T01 -103: 1 vencido > 90                  1.000
        #   T02  -82: 2 vencido 61-90                 T02   500
        #   T03  -46: 3 vencido 31-60                 T03   300
        #   T04  -11: 4 vencido 1-30                  T04   200
        #   T05    0 e T06 7: 5 a vencer 0-7          100 + 50 = 150 (7 ainda é desta faixa)
        #   T07    8: 6 a vencer 8-15                 400
        #   T08   30: 7 a vencer 16-30                250
        #   T10   60: 8 a vencer 31-60                150
        #   T09   61: 9 a vencer > 60                 600
        # Total em aberto: 3.550.
        self.carregar("financeiro-pagar.csv")

        linhas = self.linhas(SQL_FINANCEIRO_AGING)

        self.assertEqual([l["faixa"][0] for l in linhas], list("123456789"))
        self.assertEqual([l["titulos"] for l in linhas], [1, 1, 1, 1, 2, 1, 1, 1, 1])
        valores = [1000.0, 500.0, 300.0, 200.0, 150.0, 400.0, 250.0, 150.0, 600.0]
        for linha, valor in zip(linhas, valores):
            self.assertAlmostEqual(linha["valor"], valor)
            self.assertAlmostEqual(linha["part_pct"], valor / 35.5)

        # Prova da seção 3.1: faixas exclusivas somam o total em aberto, e esse total vem de outra conta:
        # original - baixado, título a título, sem passar pela coluna de saldo nem pelas faixas.
        independente = self.linhas(
            "SELECT SUM(original - baixado) total, COUNT(*) n FROM financeiro_pagar "
            "WHERE situacao = 'Aberto' AND original - baixado > 0"
        )
        self.assertAlmostEqual(sum(l["valor"] for l in linhas), independente[0]["total"])
        self.assertAlmostEqual(independente[0]["total"], 3550.0)
        self.assertEqual(sum(l["titulos"] for l in linhas), independente[0]["n"])
        # Amostra: em nenhum título aberto o saldo exportado difere de original - baixado.
        divergentes = self.linhas(
            "SELECT COUNT(*) n FROM financeiro_pagar WHERE situacao = 'Aberto' AND original - baixado <> saldo"
        )
        self.assertEqual(divergentes[0]["n"], 0)

    def test_fiscal_cfop(self):
        self.assertIn("### 3.1 Documentos fiscais: sintético", secao("relatorio-fiscal", "3.1"))
        # Em fiscal-notas.csv e fiscal-itens.csv, loja 1, outubro de 2026, só Autorizada:
        # entram as notas 100/série 1, 100/série 2, 101 e 105 (a 102 está cancelada, a 103 é de
        # setembro e a 104 é da loja 2). Valor de produtos dos cabeçalhos: 1.000 + 300 + 500 + 800 = 2.600.
        #   5102: itens 600 (100/1) + 300 (100/2) + 500 (101) = 1.400, ICMS 72 + 36 + 60 = 168, 3 itens
        #   1102: item 800 (105), ICMS 96, 1 item
        #   5405: item 400 (100/1), ICMS-ST 40, 1 item
        # Participação sobre 2.600: 1.400 = 53,8462%, 800 = 30,7692%, 400 = 15,3846%.
        self.carregar("fiscal-notas.csv", "fiscal-itens.csv")

        linhas = self.linhas(SQL_FISCAL_CFOP)

        self.assertEqual([l["cfop"] for l in linhas], [5102, 1102, 5405])
        self.assertEqual([l["itens"] for l in linhas], [3, 1, 1])
        self.assertEqual([l["valor"] for l in linhas], [1400.0, 800.0, 400.0])
        self.assertEqual([l["icms"] for l in linhas], [168.0, 96.0, 0.0])
        self.assertEqual([l["icms_st"] for l in linhas], [0.0, 0.0, 40.0])
        for linha, valor in zip(linhas, [1400.0, 800.0, 400.0]):
            self.assertAlmostEqual(linha["part_pct"], valor / 26.0)

        # Prova da seção 3.1: soma por CFOP = valor de produtos dos cabeçalhos autorizados do período,
        # total que vem da tabela de notas e não passa pela junção com os itens.
        cabecalho = self.linhas(
            "SELECT SUM(valor_produtos) total, COUNT(*) notas FROM fiscal_notas "
            "WHERE situacao = 'Autorizada' AND loja = 1 AND data >= '2026-10-01' AND data < '2026-11-01'"
        )
        self.assertAlmostEqual(sum(l["valor"] for l in linhas), cabecalho[0]["total"])
        self.assertAlmostEqual(cabecalho[0]["total"], 2600.0)
        self.assertEqual(cabecalho[0]["notas"], 4)

        # Por que a chave leva a série: juntando só por loja e número, a nota 100 casa com duas
        # séries e o sintético passa de 2.600.
        sem_serie = self.linhas(
            "SELECT SUM(i.valor) total FROM fiscal_itens i JOIN fiscal_notas h ON h.loja = i.loja AND h.nota = i.nota "
            "WHERE h.situacao = 'Autorizada' AND h.loja = 1 AND h.data >= '2026-10-01' AND h.data < '2026-11-01'"
        )
        self.assertGreater(sem_serie[0]["total"], 2600.0)

    def test_contabil_balancete(self):
        self.assertIn("### 3.1 Balancete de verificação", secao("relatorio-contabil", "3.1"))
        # Em contabil-lancamentos.csv, só Efetivado (o rascunho L5 de 999 fica fora), exercício
        # desde 01/01/2026 e período de outubro. Saldo com sinal: débito positivo, crédito negativo.
        #   1.1.01.001 Caixa:         anterior +1.000, débitos 500, créditos 200 + 40 = 240, atual +1.260
        #   2.1.01.001 Fornecedores:  anterior 0, débitos 40, créditos 100, atual -60
        #   2.3.01.001 Capital:       anterior -1.000, sem movimento no mês, atual -1.000
        #   3.1.01.001 Receita:       anterior 0, créditos 500, atual -500
        #   4.1.01.001 Despesas:      anterior 0, débitos 200 + 100 = 300, atual +300
        # Débitos do mês 500 + 40 + 300 = 840 e créditos 240 + 100 + 500 = 840.
        self.carregar("contabil-plano.csv", "contabil-lancamentos.csv")

        linhas = self.linhas(SQL_CONTABIL_BALANCETE)

        self.assertEqual([l["codigo"] for l in linhas], ["1.1.01.001", "2.1.01.001", "2.3.01.001", "3.1.01.001", "4.1.01.001"])
        self.assertEqual([l["saldo_anterior"] for l in linhas], [1000.0, 0.0, -1000.0, 0.0, 0.0])
        self.assertEqual([l["debitos"] for l in linhas], [500.0, 40.0, 0.0, 0.0, 300.0])
        self.assertEqual([l["creditos"] for l in linhas], [240.0, 100.0, 0.0, 500.0, 0.0])
        self.assertEqual([l["saldo_atual"] for l in linhas], [1260.0, -60.0, -1000.0, -500.0, 300.0])

        # Prova da seção 3.1: débitos = créditos no período, calculados no lançamento por D e C
        # (não pelas colunas do balancete), e a soma dos saldos com sinal é zero.
        direto = self.linhas(
            "SELECT SUM(CASE WHEN dc = 'D' THEN valor ELSE 0 END) deb, SUM(CASE WHEN dc = 'C' THEN valor ELSE 0 END) cre "
            "FROM contabil_lancamentos WHERE situacao = 'Efetivado' AND data >= '2026-10-01' AND data < '2026-11-01'"
        )
        self.assertAlmostEqual(direto[0]["deb"], direto[0]["cre"])
        self.assertAlmostEqual(sum(l["debitos"] for l in linhas), direto[0]["deb"])
        self.assertAlmostEqual(sum(l["creditos"] for l in linhas), direto[0]["cre"])
        self.assertAlmostEqual(direto[0]["deb"], 840.0)
        self.assertAlmostEqual(sum(l["saldo_atual"] for l in linhas), 0.0)
        self.assertAlmostEqual(sum(l["saldo_anterior"] for l in linhas), 0.0)
        # Equação patrimonial: ativo 1.260 = passivo 60 + patrimônio líquido 1.000 + resultado (500 - 300).
        self.assertAlmostEqual(1260.0, 60.0 + 1000.0 + (500.0 - 300.0))


if __name__ == "__main__":
    unittest.main()
