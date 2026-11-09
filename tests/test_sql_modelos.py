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


if __name__ == "__main__":
    unittest.main()
