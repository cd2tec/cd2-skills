"""Testes do leitor de arquivo exportado (kit dados), direto do core."""
import datetime
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "core/cd2-varejo/kits/dados/scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import dados_arquivo as da  # noqa: E402
from dados_arquivo import (  # noqa: E402
    ErroDados, carregar, consultar, detectar_csv, e_linha_total, ler_xlsx,
    nome_seguro, normalizar_data, normalizar_numero,
)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.base = self.dir / "base.sqlite"

    def csv(self, nome, conteudo, codificacao="utf-8"):
        caminho = self.dir / nome
        caminho.write_bytes(conteudo.encode(codificacao))
        return caminho

    def sql(self, texto):
        return consultar(self.base, texto)


class TestNormalizacao(unittest.TestCase):
    def test_negativo_entre_parenteses_e_reais(self):
        self.assertEqual(normalizar_numero("(R$ 1.234,50)"), -1234.5)

    def test_formatos_comuns(self):
        self.assertEqual(normalizar_numero("1.234,56"), 1234.56)
        self.assertEqual(normalizar_numero("-12,5"), -12.5)
        self.assertEqual(normalizar_numero("12,5-"), -12.5)
        self.assertEqual(normalizar_numero("1.234.567"), 1234567.0)
        self.assertEqual(normalizar_numero("12,5%"), 12.5)
        self.assertIsNone(normalizar_numero("abc"))
        self.assertIsNone(normalizar_numero(""))

    def test_reais_com_parenteses_por_dentro(self):
        self.assertEqual(normalizar_numero("R$ (5,00)"), -5.0)
        self.assertEqual(normalizar_numero("(5,00)"), -5.0)

    def test_datas(self):
        self.assertEqual(normalizar_data("31/01/2026"), "2026-01-31")
        self.assertEqual(normalizar_data("2026-01-31"), "2026-01-31")
        self.assertEqual(normalizar_data("05-02-26"), "2026-02-05")
        self.assertIsNone(normalizar_data("31/02/2026"))
        self.assertIsNone(normalizar_data("Arroz"))
        self.assertEqual(normalizar_data("31.01.2026"), "2026-01-31")

    def test_codigo_de_conta_nao_e_data(self):
        for codigo in ("1.1.01", "2.1.01", "3.1.02", "4.1.03"):
            self.assertIsNone(normalizar_data(codigo), codigo)

    def test_coluna_de_codigos_de_conta_fica_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / "plano.csv"
            arq.write_text("Conta;Codigo\n1;1.1.01\n2;2.1.01\n3;3.1.01\n", encoding="utf-8")
            perfil = carregar([arq], Path(tmp) / "b.sqlite")
            tipos = {c["nome"]: c["tipo"] for c in perfil["tabelas"][0]["colunas"]}
            self.assertEqual(tipos["codigo"], "texto")
            r = consultar(Path(tmp) / "b.sqlite", "SELECT codigo FROM plano ORDER BY conta")
            self.assertEqual([l[0] for l in r["linhas"]], ["1.1.01", "2.1.01", "3.1.01"])

    def test_nome_seguro(self):
        usados = set()
        self.assertEqual(nome_seguro("Preço Líquido", usados), "preco_liquido")
        self.assertEqual(nome_seguro("Preço Líquido", usados), "preco_liquido_2")
        self.assertEqual(nome_seguro("", usados), "col")
        self.assertEqual(nome_seguro("2026", usados), "c_2026")

    def test_linha_total(self):
        self.assertTrue(e_linha_total(["Subtotal", "", "6", "10,00"]))
        self.assertTrue(e_linha_total(["", "TOTAL GERAL", "10"]))
        self.assertTrue(e_linha_total(["Total do dia", "5"]))
        self.assertTrue(e_linha_total(["Total:", "5"]))
        self.assertFalse(e_linha_total(["Total Clean Detergente 500ml", "4,99", "3"]))
        self.assertFalse(e_linha_total(["Total", "", ""]))
        self.assertFalse(e_linha_total(["Arroz", "5"]))

    def test_detectar_csv(self):
        texto, delim = detectar_csv("a;b;c\n1,5;2;3\n".encode("cp1252"))
        self.assertEqual(delim, ";")
        texto, delim = detectar_csv(b"\xef\xbb\xbfa\tb\n1\t2\n")
        self.assertEqual(delim, "\t")
        self.assertTrue(texto.startswith("a"))
        texto, delim = detectar_csv("nome,qtd\nCafé,2\n".encode("utf-8"))
        self.assertEqual(delim, ",")
        self.assertIn("Café", texto)


class TestCarregar(Base):
    def test_windows1252_ponto_e_virgula(self):
        perfil = carregar([FIXTURES / "erp-vendas-1252.csv"], self.base)
        tabela = perfil["tabelas"][0]
        self.assertEqual(tabela["tabela"], "erp_vendas_1252")
        self.assertEqual(tabela["linhas"], 3)
        r = self.sql("SELECT produto, data, valor FROM erp_vendas_1252 ORDER BY data")
        self.assertEqual(r["linhas"][0], ["Café Pilão 500g", "2026-01-31", 1234.56])
        self.assertEqual(r["linhas"][2][2], -5.5)
        tipos = {c["nome"]: c["tipo"] for c in tabela["colunas"]}
        self.assertEqual(tipos["data"], "data")
        self.assertEqual(tipos["qtd"], "inteiro")
        self.assertEqual(tipos["valor"], "real")

    def test_subtotal_e_total_geral_nao_somam(self):
        perfil = carregar([FIXTURES / "erp-vendas-1252.csv"], self.base)
        tabela = perfil["tabelas"][0]
        self.assertEqual(tabela["linhas_total"], 2)
        soma = self.sql("SELECT ROUND(SUM(valor), 2), SUM(qtd) FROM erp_vendas_1252")
        self.assertEqual(soma["linhas"][0], [1239.06, 6])
        totais = self.sql("SELECT COUNT(*) FROM erp_vendas_1252__totais")
        self.assertEqual(totais["linhas"][0][0], 2)

    def test_utf8_bom_e_tab(self):
        perfil = carregar([FIXTURES / "erp-estoque-tab.csv"], self.base)
        r = self.sql("SELECT codigo, descricao, saldo FROM erp_estoque_tab ORDER BY codigo")
        # código com zero à esquerda continua texto
        self.assertEqual(r["linhas"], [["00123", "Arroz", 10.5], ["00456", "Feijão", 3.0]])
        self.assertEqual(perfil["tabelas"][0]["colunas"][1]["original"], "Descrição")

    def test_coluna_ambigua_gera_aviso(self):
        arq = self.csv("peso.csv", "item;kg\nA;1.234\nB;2.250\n")
        perfil = carregar([arq], self.base)
        r = self.sql("SELECT kg FROM peso ORDER BY item")
        self.assertEqual([x[0] for x in r["linhas"]], [1.234, 2.25])
        self.assertTrue(any("kg" in a for a in perfil["avisos"]))

    def test_coluna_com_virgula_trata_ponto_como_milhar(self):
        arq = self.csv("v.csv", "item;valor\nA;1.234\nB;2,5\nC;1.000,50\n")
        perfil = carregar([arq], self.base)
        r = self.sql("SELECT valor FROM v ORDER BY item")
        self.assertEqual([x[0] for x in r["linhas"]], [1234.0, 2.5, 1000.5])
        self.assertFalse(any("valor" in a for a in perfil["avisos"]))

    def test_coluna_maliciosa_nao_injeta(self):
        arq = self.csv("t.csv", 'id;"x""; DROP TABLE t; --"\n1;2\n')
        perfil = carregar([arq], self.base)
        nome = perfil["tabelas"][0]["colunas"][1]["nome"]
        self.assertRegex(nome, r"^[a-z0-9_]+$")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM t")["linhas"][0][0], 1)
        self.assertEqual(perfil["tabelas"][0]["colunas"][1]["original"], 'x"; DROP TABLE t; --')

    def test_cpf_mascarado_ao_carregar(self):
        arq = self.csv("c.csv", "nome;doc;cpf_cliente\nAna;123.456.789-09;12345678909\nBia;Livre;98765432100\n")
        perfil = carregar([arq], self.base)
        r = self.sql("SELECT doc, cpf_cliente FROM c ORDER BY nome")
        self.assertEqual(r["linhas"][0], ["***.456.789-**", "***.456.789-**"])
        self.assertEqual(r["linhas"][1], ["Livre", "***.654.321-**"])
        self.assertTrue(any("CPF" in a for a in perfil["avisos"]))
        self.assertNotIn("123.456.789-09", json.dumps(perfil, ensure_ascii=False))

    def test_dois_arquivos_e_join(self):
        a = self.csv("vendas.csv", "sku;qtd\nA;2\nB;5\n")
        b = self.csv("produtos.csv", "sku;nome\nA;Arroz\nB;Feijão\n")
        perfil = carregar([a, b], self.base)
        self.assertEqual([t["tabela"] for t in perfil["tabelas"]], ["vendas", "produtos"])
        r = self.sql("SELECT p.nome, v.qtd FROM vendas v JOIN produtos p ON p.sku = v.sku ORDER BY v.qtd")
        self.assertEqual(r["linhas"], [["Arroz", 2], ["Feijão", 5]])

    def test_arquivos_com_mesmo_nome_nao_colidem(self):
        sub = self.dir / "outra"
        sub.mkdir()
        a = self.csv("dados.csv", "x\n1\n")
        (sub / "dados.csv").write_text("x\n2\n")
        perfil = carregar([a, sub / "dados.csv"], self.base)
        self.assertEqual([t["tabela"] for t in perfil["tabelas"]], ["dados", "dados_2"])

    def test_arquivo_vazio_e_so_cabecalho(self):
        with self.assertRaises(ErroDados) as ctx:
            carregar([self.csv("vazio.csv", "")], self.base)
        self.assertIn("vazio", ctx.exception.erros[0])
        perfil = carregar([self.csv("so.csv", "a;b\n")], self.base)
        self.assertEqual(perfil["tabelas"][0]["linhas"], 0)
        self.assertTrue(any("so.csv" in a for a in perfil["avisos"]))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM so")["linhas"][0][0], 0)

    def test_arquivo_gigante_recusa(self):
        arq = self.csv("g.csv", "a;b\n1;2\n")
        with mock.patch.object(da, "LIMITE_BYTES", 4):
            with self.assertRaises(ErroDados) as ctx:
                carregar([arq], self.base)
        self.assertIn("grande", ctx.exception.erros[0])

    def test_sqlite_antigo_avisa(self):
        arq = self.csv("a.csv", "a\n1\n")
        with mock.patch.object(sqlite3, "sqlite_version_info", (3, 20, 0)):
            perfil = carregar([arq], self.base)
        self.assertTrue(any("3.25" in a for a in perfil["avisos"]))

    def test_xls_antigo_pede_para_salvar(self):
        arq = self.dir / "velho.xls"
        arq.write_bytes(b"\xd0\xcf\x11\xe0")
        with self.assertRaises(ErroDados) as ctx:
            carregar([arq], self.base)
        self.assertIn("CSV", ctx.exception.erros[0])

    def test_apagar_remove_base(self):
        carregar([self.csv("a.csv", "a\n1\n")], self.base)
        self.assertTrue(self.base.exists())
        self.assertEqual(da.apagar(self.base)["apagado"], True)
        self.assertFalse(self.base.exists())
        self.assertEqual(da.apagar(self.base)["apagado"], False)


class TestRevisao(Base):
    def avisos(self, nome, conteudo):
        return carregar([self.csv(nome, conteudo)], self.base)["avisos"]

    def test_produto_com_nome_total_fica_na_tabela_principal(self):
        arq = self.csv("p.csv", "produto;preco;qtd\nTotal Clean Detergente;4,99;3\nArroz;5,00;2\n"
                                "Subtotal;;5\nTOTAL GERAL;;5\nTotal do dia;;5\nTotal:;;5\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(perfil["tabelas"][0]["linhas"], 2)
        self.assertEqual(perfil["tabelas"][0]["linhas_total"], 4)
        r = self.sql("SELECT produto FROM p ORDER BY produto")
        self.assertEqual([x[0] for x in r["linhas"]], ["Arroz", "Total Clean Detergente"])

    def test_coluna_quase_numerica_nao_vira_texto(self):
        arq = self.csv("n.csv", "item;valor\nA;1.234,56\nB;n/d\nC;10,00\nD;1,00\nE;2,00\nF;3,00\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(self.sql("SELECT ROUND(SUM(valor), 2) FROM n")["linhas"][0][0], 1250.56)
        self.assertEqual(self.sql("SELECT valor FROM n WHERE item='B'")["linhas"][0][0], None)
        self.assertEqual(perfil["tabelas"][0]["colunas"][1]["tipo"], "real")
        aviso = [a for a in perfil["avisos"] if "valor" in a]
        self.assertTrue(aviso and "n/d" in aviso[0])

    def test_coluna_com_muita_coisa_nao_numerica_continua_texto(self):
        perfil = carregar([self.csv("m.csv", "a;b\n1;x\n2;y\nz;w\n")], self.base)
        self.assertEqual(perfil["tabelas"][0]["colunas"][0]["tipo"], "texto")

    def test_aviso_lista_no_maximo_cinco_falhas(self):
        linhas = "".join(f"i{i};ruim{i}\n" for i in range(10)) + "".join(f"j{i};{i},5\n" for i in range(60))
        aviso = [a for a in self.avisos("c.csv", "item;v\n" + linhas) if "\"v\"" in a][0]
        self.assertIn("ruim4", aviso)
        self.assertNotIn("ruim5", aviso)

    def test_cabecalho_repetido_por_paginacao_sai(self):
        arq = self.csv("pg.csv", "item;qtd\nA;1\nitem;qtd\nB;2\nITEM;QTD\nC;3\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(perfil["tabelas"][0]["linhas"], 3)
        self.assertEqual(self.sql("SELECT SUM(qtd) FROM pg")["linhas"][0][0], 6)
        self.assertTrue(any("cabeçalho" in a and "2" in a for a in perfil["avisos"]))

    def test_milhar_ambiguo_em_coluna_mista_avisa(self):
        arq = self.csv("k.csv", "item;kg\nA;1.234\nB;12\nC;12.345\n")
        perfil = carregar([arq], self.base)
        self.assertTrue(any("kg" in a for a in perfil["avisos"]))
        self.assertEqual([x[0] for x in self.sql("SELECT kg FROM k ORDER BY item")["linhas"]], [1.234, 12.0, 12.345])

    def test_dois_grupos_de_ponto_tudo_vira_milhar(self):
        arq = self.csv("q.csv", "item;n\nA;1.234\nB;1.234.567\n")
        perfil = carregar([arq], self.base)
        self.assertEqual([x[0] for x in self.sql("SELECT n FROM q ORDER BY item")["linhas"]], [1234, 1234567])
        self.assertFalse(any('"n"' in a for a in perfil["avisos"]))

    def test_cpf_em_texto_livre_e_mascarado(self):
        arq = self.csv("o.csv", "id;obs\n1;CPF 123.456.789-09 ok\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(self.sql("SELECT obs FROM o")["linhas"][0][0], "CPF ***.456.789-** ok")
        self.assertNotIn("123.456.789-09", json.dumps(perfil))

    def test_onze_digitos_em_coluna_sem_nome_cpf_avisa(self):
        arq = self.csv("d.csv", "id;doc\n1;12345678909\n2;98765432100\n")
        perfil = carregar([arq], self.base)
        self.assertTrue(any("doc" in a and "CPF" in a for a in perfil["avisos"]))

    def test_tabela_sqlite_ganha_prefixo(self):
        perfil = carregar([self.csv("sqlite_master.csv", "a\n1\n")], self.base)
        self.assertEqual(perfil["tabelas"][0]["tabela"], "t_sqlite_master")


class TestRobustez(Base):
    def test_apagar_nao_apaga_o_que_nao_e_base(self):
        txt = self.dir / "naobase.txt"
        txt.write_text("importante")
        with self.assertRaises(ErroDados):
            da.apagar(txt)
        self.assertTrue(txt.exists())

    def test_carregar_recusa_base_igual_a_entrada(self):
        entrada = self.csv("v.csv", "a\n1\n")
        with self.assertRaises(ErroDados):
            carregar([entrada], entrada)
        self.assertEqual(entrada.read_text(), "a\n1\n")

    def test_carregar_recusa_sobrescrever_arquivo_alheio(self):
        alheio = self.dir / "alheio.txt"
        alheio.write_text("meu")
        with self.assertRaises(ErroDados):
            carregar([self.csv("a.csv", "a\n1\n")], alheio)
        self.assertEqual(alheio.read_text(), "meu")

    def test_falha_no_meio_nao_deixa_base_pela_metade(self):
        ok = self.csv("ok.csv", "a\n1\n")
        with self.assertRaises(ErroDados):
            carregar([ok, self.csv("vazio.csv", "")], self.base)
        self.assertFalse(self.base.exists())

    def test_xlsx_com_crc_ruim_vira_erro(self):
        caminho = self.dir / "crc.xlsx"
        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_STORED) as z:
            z.writestr("xl/workbook.xml", "<workbook>" + "A" * 200 + "</workbook>")
        dados = bytearray(caminho.read_bytes())
        i = dados.index(b"AAAA")
        dados[i] = ord("B")
        caminho.write_bytes(bytes(dados))
        with self.assertRaises(ErroDados):
            carregar([caminho], self.base)
        with self.assertRaises(ErroDados):
            ler_xlsx(caminho)

    def test_xlsx_com_coluna_absurda_recusa(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        caminho = self.dir / "col.xlsx"
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook {ns}><sheets><sheet name="A" sheetId="1"/></sheets></workbook>')
            z.writestr("xl/worksheets/sheet1.xml",
                       f'<worksheet {ns}><sheetData><row r="1"><c r="ZZZZZ1" t="inlineStr"><is><t>x</t></is></c>'
                       '</row></sheetData></worksheet>')
        with self.assertRaises(ErroDados):
            carregar([caminho], self.base)

    def test_xml_grande_demais_recusa(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        caminho = self.dir / "gg.xlsx"
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook {ns}><sheets><sheet name="A" sheetId="1"/></sheets></workbook>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData/></worksheet>')
        with mock.patch.object(da, "LIMITE_XML_BYTES", 20):
            with self.assertRaises(ErroDados):
                ler_xlsx(caminho)

    def test_caminho_com_interrogacao_na_consulta(self):
        pasta = self.dir / "a?b#c"
        pasta.mkdir()
        base = pasta / "b.sqlite"
        carregar([self.csv("t.csv", "a\n1\n")], base)
        self.assertEqual(consultar(base, "SELECT a FROM t")["linhas"], [[1]])

    def test_cli_erro_de_so_sistema_sai_com_2(self):
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = da.main(["apagar", "--base", str(self.dir)])
        self.assertIn(codigo, (0, 2))
        arq = self.dir / "x.txt"
        arq.write_text("nao e base")
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = da.main(["apagar", "--base", str(arq)])
        self.assertEqual(codigo, 2)
        self.assertIn("errors", json.loads(saida.getvalue()))
        self.assertTrue(arq.exists())

    def test_cli_arquivo_ilegivel_sai_com_2(self):
        arq = self.dir / "ruim.csv"
        arq.write_text("a\n1\n")
        arq.chmod(0)
        self.addCleanup(arq.chmod, 0o600)
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = da.main(["carregar", "--base", str(self.base), str(arq)])
        self.assertEqual(codigo, 2)
        self.assertIn("errors", json.loads(saida.getvalue()))


class TestXlsx(Base):
    def montar(self, nome="p.xlsx", duas_planilhas=False):
        serial = (datetime.date(2026, 1, 31) - datetime.date(1899, 12, 30)).days
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
        planilhas = '<sheet name="Vendas" sheetId="1" r:id="rId1"/>'
        if duas_planilhas:
            planilhas += '<sheet name="Outra" sheetId="2" r:id="rId2"/>'
        arquivos = {
            "xl/workbook.xml": f'<workbook {ns} {rel}><sheets>{planilhas}</sheets></workbook>',
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>'),
            "xl/sharedStrings.xml": (
                f'<sst {ns}><si><t>Data</t></si><si><t>Produto</t></si><si><t>Valor</t></si>'
                '<si><r><t>Caf</t></r><r><t>é</t></r></si></sst>'),
            "xl/styles.xml": (
                f'<styleSheet {ns}><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
                '<cellXfs count="3"><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/></cellXfs></styleSheet>'),
            "xl/worksheets/sheet1.xml": (
                f'<worksheet {ns}><sheetData>'
                '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
                f'<row r="2"><c r="A2" s="1"><v>{serial}</v></c><c r="B2" t="s"><v>3</v></c><c r="C2"><v>1234.5</v></c></row>'
                f'<row r="3"><c r="A3" s="2"><v>{serial + 1}</v></c><c r="B3" t="inlineStr"><is><t>Pão</t></is></c>'
                '<c r="C3"><v>0.125</v></c></row>'
                '</sheetData></worksheet>'),
        }
        if duas_planilhas:
            arquivos["xl/worksheets/sheet2.xml"] = f'<worksheet {ns}><sheetData/></worksheet>'
        caminho = self.dir / nome
        with zipfile.ZipFile(caminho, "w") as z:
            for k, v in arquivos.items():
                z.writestr(k, v)
        return caminho

    def test_xlsx_com_data_e_shared_strings(self):
        caminho = self.montar()
        linhas = ler_xlsx(caminho)
        self.assertEqual(linhas[0], ["Data", "Produto", "Valor"])
        self.assertEqual(linhas[1][0], "2026-01-31")
        self.assertEqual(linhas[1][1], "Café")
        self.assertEqual(linhas[2][0], "2026-02-01")
        perfil = carregar([caminho], self.base)
        r = self.sql("SELECT data, produto, valor FROM p ORDER BY data")
        self.assertEqual(r["linhas"], [["2026-01-31", "Café", 1234.5], ["2026-02-01", "Pão", 0.125]])
        self.assertEqual(perfil["tabelas"][0]["colunas"][0]["tipo"], "data")

    def test_xlsx_com_varias_planilhas_avisa(self):
        perfil = carregar([self.montar("m.xlsx", duas_planilhas=True)], self.base)
        self.assertTrue(any("planilha" in a and "Vendas" in a for a in perfil["avisos"]))

    def test_xlsx_corrompido_vira_erro(self):
        ruim = self.dir / "ruim.xlsx"
        ruim.write_bytes(b"nao e zip")
        with self.assertRaises(ErroDados):
            carregar([ruim], self.base)


class TestCabecalho(Base):
    def colunas(self, perfil):
        return [c["nome"] for c in perfil["tabelas"][0]["colunas"]]

    def test_titulo_e_periodo_antes_do_cabecalho(self):
        arq = self.csv("v.csv", "Relatório de vendas\nPeriodo:;01/01/2026 a 31/01/2026\n"
                                "Loja;Produto;Valor\nA;X;100,00\nB;Y;200,00\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(self.colunas(perfil), ["loja", "produto", "valor"])
        self.assertEqual(perfil["tabelas"][0]["linhas"], 2)
        self.assertEqual(self.sql("SELECT SUM(valor) FROM v")["linhas"][0][0], 300.0)
        aviso = [a for a in perfil["avisos"] if "antes do cabeçalho" in a]
        self.assertEqual(len(aviso), 1)
        self.assertIn("Relatório de vendas", aviso[0])
        self.assertIn("Periodo:", aviso[0])

    def test_vazias_a_direita_nao_contam_na_largura(self):
        arq = self.csv("v.csv", "Titulo;;;\nEmissao;hoje;;\nA;B;C;D\n1;2;3;4\n5;6;7;8\n")
        self.assertEqual(self.colunas(carregar([arq], self.base)), ["a", "b", "c", "d"])

    def test_aviso_cita_no_maximo_tres_linhas(self):
        arq = self.csv("v.csv", "L1\nL2\nL3\nL4\nL5\nA;B;C\n1;2;3\n4;5;6\n")
        perfil = carregar([arq], self.base)
        aviso = [a for a in perfil["avisos"] if "antes do cabeçalho" in a][0]
        self.assertIn("5", aviso)
        self.assertIn("L3", aviso)
        self.assertNotIn("L4", aviso)

    def test_periodo_com_dois_pontos_nao_vira_cabecalho_de_duas_colunas(self):
        arq = self.csv("v.csv", "Titulo\nPeriodo:;01/01/2026 a 31/01/2026\nItem;Valor\nA;1,00\nB;2,00\n")
        self.assertEqual(self.colunas(carregar([arq], self.base)), ["item", "valor"])

    def test_cabecalho_mais_largo_que_as_linhas_de_dado(self):
        # Última coluna quase vazia: a largura dominante é menor que a do cabeçalho.
        arq = self.csv("v.csv", "Cod;Nome;Grupo;Valor;Obs\nA;Arroz;Merc;1,00;\nB;Pao;Merc;2,00;\nC;Sal;Merc;3,00;x\n")
        perfil = carregar([arq], self.base)
        self.assertEqual(self.colunas(perfil), ["cod", "nome", "grupo", "valor", "obs"])
        self.assertEqual(perfil["tabelas"][0]["linhas"], 3)
        self.assertFalse(any("antes do cabeçalho" in a for a in perfil["avisos"]))

    def test_cabecalho_com_anos_cai_na_primeira_linha_da_largura(self):
        arq = self.csv("v.csv", "Comparativo\nProduto;2025;2026\nArroz;1;2\nPao;3;4\n")
        self.assertEqual(self.colunas(carregar([arq], self.base)), ["produto", "c_2025", "c_2026"])

    def test_cpf_em_linha_descartada_nao_vai_para_o_aviso(self):
        arq = self.csv("v.csv", "Cliente 123.456.789-09\nA;B\n1;2\n3;4\n")
        perfil = carregar([arq], self.base)
        self.assertNotIn("123.456.789-09", json.dumps(perfil, ensure_ascii=False))
        self.assertTrue(any("***.456.789-**" in a for a in perfil["avisos"]))

    def test_opcao_cabecalho(self):
        arq = self.csv("v.csv", "a;b;c\nx;y;z\n1;2;3\n")
        perfil = carregar([arq], self.base, cabecalho=2)
        self.assertEqual(self.colunas(perfil), ["x", "y", "z"])
        self.assertEqual(perfil["tabelas"][0]["linhas"], 1)

    def test_opcao_cabecalho_fora_do_arquivo_ou_em_linha_vazia(self):
        arq = self.csv("v.csv", "a;b\n\n1;2\n")
        for linha in (0, 2, 9):
            with self.assertRaises(ErroDados, msg=linha):
                carregar([arq], self.base, cabecalho=linha)

    def test_opcao_cabecalho_na_linha_de_comando(self):
        arq = self.csv("v.csv", "a;b;c\nx;y;z\n1;2;3\n")
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = da.main(["carregar", "--base", str(self.base), "--cabecalho", "2", str(arq)])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(saida.getvalue())["tabelas"][0]["colunas"][0]["nome"], "x")

    def test_opcao_cabecalho_usa_a_linha_real_do_xlsx(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        def celula(ref, texto):
            return f'<c r="{ref}" t="inlineStr"><is><t>{texto}</t></is></c>'
        caminho = self.dir / "g.xlsx"
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook {ns}><sheets><sheet name="A" sheetId="1"/></sheets></workbook>')
            z.writestr("xl/worksheets/sheet1.xml",
                       f'<worksheet {ns}><sheetData><row r="2">{celula("A2", "Titulo")}</row>'
                       f'<row r="4">{celula("A4", "x")}{celula("B4", "y")}</row>'
                       f'<row r="5"><c r="A5"><v>1</v></c><c r="B5"><v>2</v></c></row></sheetData></worksheet>')
        perfil = carregar([caminho], self.base, cabecalho=4)
        self.assertEqual(self.colunas(perfil), ["x", "y"])


class TestTotais(Base):
    def carga(self, conteudo):
        arq = self.csv("t.csv", conteudo)
        perfil = carregar([arq], self.base)
        return perfil, perfil["tabelas"][0]

    def soma(self):
        return self.sql("SELECT ROUND(SUM(valor), 2) FROM t")["linhas"][0][0]

    def test_total_de_grupo_na_quarta_coluna_nao_conta_em_dobro(self):
        _, tab = self.carga("Loja;Depto;Cod;Descricao;Valor\n1;Merc;10;Arroz;100,00\n1;Merc;11;Feijao;200,00\n"
                            "1;Merc;;Total Depto;300,00\n;;;Total Geral;300,00\n")
        self.assertEqual(self.soma(), 300.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (2, 2))

    def test_subtotal_sem_rotulo_vai_para_totais_com_aviso_proprio(self):
        perfil, tab = self.carga("Loja;Prod;Valor\nA;X;100,00\nA;Y;200,00\n;;300,00\n")
        self.assertEqual(self.soma(), 300.0)
        self.assertEqual(tab["linhas_total"], 1)
        self.assertEqual(self.sql("SELECT valor FROM t__totais")["linhas"], [[300.0]])
        self.assertTrue(any("possível subtotal sem rótulo" in a for a in perfil["avisos"]))

    def test_primeiras_colunas_vazias_na_maioria_nao_sao_subtotal(self):
        _, tab = self.carga("a;b;valor\n;;1,00\n;;2,00\nx;y;3,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 0))

    def test_linha_sem_rotulo_com_data_nao_e_subtotal(self):
        _, tab = self.carga("a;b;d;valor\nx;y;01/02/2026;1,00\nz;w;02/02/2026;2,00\n;;03/02/2026;3,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 0))

    def test_baixa_total_e_categoria_e_fica_na_tabela(self):
        _, tab = self.carga("Titulo;Baixa;Valor\nT1;Total;100,00\nT2;Parcial;50,00\nT3;Total;200,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 0))
        self.assertEqual(self.soma(), 350.0)

    def test_categoria_na_primeira_coluna_fica_na_tabela(self):
        _, tab = self.carga("Baixa;Titulo;Valor\nTotal;T1;100,00\nParcial;T2;50,00\nTotal;T3;200,00\nParcial;T4;10,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (4, 0))

    def test_total_clean_continua_na_tabela(self):
        _, tab = self.carga("Cod;Descricao;Valor\n1;Arroz;5,00\n2;Total Clean Detergente;4,99\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (2, 0))

    def test_arquivo_pequeno_com_uma_linha_de_total(self):
        _, tab = self.carga("item;valor\nA;10,00\nB;20,00\nTotal;30,00\n")
        self.assertEqual(tab["linhas_total"], 1)
        self.assertEqual(self.soma(), 30.0)

    def test_subtotal_repetido_em_grupos_pequenos_nao_vira_categoria(self):
        _, tab = self.carga("Depto;Produto;Valor\nMerc;Arroz;100,00\nMerc;Feijao;200,00\nSubtotal;;300,00\n"
                            "Frios;Queijo;50,00\nSubtotal;;50,00\nTotal Geral;;350,00\n")
        self.assertEqual(self.soma(), 350.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 3))


class TestTotaisReexame(Base):
    def carga(self, conteudo):
        arq = self.csv("t.csv", conteudo)
        perfil = carregar([arq], self.base)
        return perfil, perfil["tabelas"][0]

    def soma(self):
        return self.sql("SELECT ROUND(SUM(valor), 2) FROM t")["linhas"][0][0]

    def avisos_de_rotulo(self, perfil):
        return [a for a in perfil["avisos"] if "dobro" in a]

    def test_saldo_vazio_quando_baixa_total_nao_tira_titulo_real(self):
        # 20 títulos de 100,00: 20 x 100 = 2000. 12 com Baixa=Total e Saldo vazio.
        linhas = []
        for i in range(20):
            total = i % 5 < 3
            linhas.append(f"T{i};F{i};01/02/2026;{'Total' if total else 'Parcial'};05/02/2026;{'' if total else '10,00'};100,00\n")
        perfil, tab = self.carga("Titulo;Fornecedor;Vencimento;Baixa;Dt Baixa;Saldo;Valor\n" + "".join(linhas))
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (20, 0))
        self.assertEqual(self.soma(), 2000.0)
        aviso = self.avisos_de_rotulo(perfil)
        self.assertEqual(len(aviso), 1)
        self.assertIn('"Baixa"', aviso[0])
        self.assertIn("12", aviso[0])

    def test_furo_a_esquerda_do_rotulo_continua_total(self):
        # Subtotal não bate com a soma e repete em 2 de 6 linhas, mas deixa Cod vazio: 100 + 200 + 50 + 25 = 375.
        _, tab = self.carga("Cod;Grupo;Desc;Valor\n10;M;Arroz;100,00\n11;M;Feijao;200,00\n;M;Subtotal;999,00\n"
                            "12;F;Queijo;50,00\n13;F;Sal;25,00\n;F;Subtotal;999,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (4, 2))
        self.assertEqual(self.soma(), 375.0)

    def test_total_que_fecha_o_dia_vai_para_totais(self):
        # 3 dias de 60 + 40 = 100: 300 sem as linhas de total.
        linhas = "".join(f"0{d}/01/2026;Loja A;60,00\n0{d}/01/2026;Loja B;40,00\n0{d}/01/2026;Total;100,00\n" for d in (1, 2, 3))
        perfil, tab = self.carga("Data;Loja;Valor\n" + linhas)
        self.assertEqual(self.soma(), 300.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (6, 3))
        self.assertEqual(self.avisos_de_rotulo(perfil), [])

    def test_subtotal_que_fecha_grupos_de_dois_vai_para_totais(self):
        # 10 + 20 + 5 + 5 = 40; os subtotais 30 e 10 ficam fora.
        perfil, tab = self.carga("Produto;Qtd;Valor\nA;1;10,00\nB;1;20,00\nSubtotal;2;30,00\n"
                                 "C;1;5,00\nD;1;5,00\nSubtotal;2;10,00\n")
        self.assertEqual(self.soma(), 40.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (4, 2))
        self.assertEqual(self.avisos_de_rotulo(perfil), [])

    def test_total_que_nao_fecha_fica_na_tabela_com_aviso(self):
        # (60 + 40 + 90) x 3 = 570: o 90 não é a soma do dia, então nada é movido, e o aviso diz o risco.
        linhas = "".join(f"0{d}/01/2026;Loja A;60,00\n0{d}/01/2026;Loja B;40,00\n0{d}/01/2026;Total;90,00\n" for d in (1, 2, 3))
        perfil, tab = self.carga("Data;Loja;Valor\n" + linhas)
        self.assertEqual(self.soma(), 570.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (9, 0))
        aviso = self.avisos_de_rotulo(perfil)
        self.assertEqual(len(aviso), 1)
        self.assertIn('"Loja"', aviso[0])
        self.assertIn("3 linha", aviso[0])
        self.assertIn('"Total"', aviso[0])

    def test_subtotal_que_nao_fecha_na_primeira_coluna_avisa(self):
        # 10 + 20 + 25 + 5 + 5 + 7 = 72: os "Subtotal" 25 e 7 não fecham e ficam, com aviso.
        perfil, tab = self.carga("Produto;Qtd;Valor\nA;1;10,00\nB;1;20,00\nSubtotal;2;25,00\n"
                                 "C;1;5,00\nD;1;5,00\nSubtotal;2;7,00\n")
        self.assertEqual(self.soma(), 72.0)
        self.assertEqual(tab["linhas_total"], 0)
        aviso = self.avisos_de_rotulo(perfil)
        self.assertTrue(aviso and '"Produto"' in aviso[0] and "2 linha" in aviso[0])

    def test_categoria_com_valor_coincidente_nao_vira_total(self):
        # Parcial e Total alternados, valor igual: cada Total "fecha" um grupo de 1 linha. 4 x 100 = 400.
        perfil, tab = self.carga("Titulo;Baixa;Valor\nT1;Parcial;100,00\nT2;Total;100,00\nT3;Parcial;100,00\nT4;Total;100,00\n")
        self.assertEqual(self.soma(), 400.0)
        self.assertEqual(tab["linhas_total"], 0)
        self.assertTrue(self.avisos_de_rotulo(perfil))

    def test_rotulo_sem_numero_nao_avisa(self):
        perfil, _ = self.carga("Item;Obs;Valor\nA;Total;\nB;Total;\nC;x;1,00\n")
        self.assertEqual(self.avisos_de_rotulo(perfil), [])

    def test_nome_de_produto_nao_e_rotulo(self):
        for nome in ("Total Dia Sabonete", "Total Loja Cereal", "Total Depto Clean", "Total Clean Detergente"):
            self.assertFalse(e_linha_total([nome, "4,99", "3"]), nome)

    def test_rotulos_que_continuam_valendo(self):
        for rotulo in ("Total do dia", "Total da loja 3", "Total Geral", "Subtotal", "Total:", "Total Depto",
                       "Total Loja 3", "Total Dia 15"):
            self.assertTrue(e_linha_total([rotulo, "", "10,00"]), rotulo)

    def test_produtos_total_na_primeira_coluna_ficam_na_tabela(self):
        # 5 + 7 + 3 = 15.
        _, tab = self.carga("Descricao;Qtd;Valor\nTotal Dia Sabonete;1;5,00\nTotal Loja Cereal;1;7,00\nArroz;1;3,00\n")
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 0))
        self.assertEqual(self.soma(), 15.0)


class TestTotalComNome(Base):
    def carga(self, conteudo):
        arq = self.csv("t.csv", conteudo)
        perfil = carregar([arq], self.base)
        return perfil, perfil["tabelas"][0]

    def soma(self):
        return self.sql("SELECT ROUND(SUM(valor), 2) FROM t")["linhas"][0][0]

    def dobro(self, perfil):
        return [a for a in perfil["avisos"] if "dobro" in a]

    def confere_movido(self, conteudo, soma, linhas, totais):
        perfil, tab = self.carga(conteudo)
        self.assertEqual(self.soma(), soma)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (linhas, totais))
        self.assertEqual(self.dobro(perfil), [])

    def test_total_depto_em_coluna_de_depto(self):
        # 1 + 2 + 1 + 2 = 6; os dois totais de 3 ficam fora.
        self.confere_movido("Depto;Produto;Valor\nMercearia;Arroz;1,00\nMercearia;Feijao;2,00\nTotal Depto Mercearia;;3,00\n"
                            "Frios;Queijo;1,00\nFrios;Presunto;2,00\nTotal Depto Frios;;3,00\n", 6.0, 4, 2)

    def test_total_depto_na_primeira_coluna_com_produtos(self):
        # 1 + 2 + 1 + 2 = 6; a quantidade também fecha: 1 + 1 = 2.
        self.confere_movido("Produto;Qtd;Valor\nArroz;1;1,00\nFeijao;1;2,00\nTotal Depto Mercearia;2;3,00\n"
                            "Queijo;1;1,00\nSal;1;2,00\nTotal Depto Frios;2;3,00\n", 6.0, 4, 2)

    def test_total_grupo_em_coluna_propria(self):
        # 10 + 20 + 10 + 20 = 60.
        self.confere_movido("Grupo;Produto;Valor\nAlimentos;Arroz;10,00\nAlimentos;Feijao;20,00\nTotal Grupo Alimentos;;30,00\n"
                            "Limpeza;Sabao;10,00\nLimpeza;Pano;20,00\nTotal Grupo Limpeza;;30,00\n", 60.0, 4, 2)

    def test_total_grupo_na_primeira_coluna_com_produtos(self):
        # 10 + 20 + 10 + 20 = 60.
        self.confere_movido("Produto;Qtd;Valor\nArroz;1;10,00\nFeijao;1;20,00\nTotal Grupo Alimentos;2;30,00\n"
                            "Sabao;1;10,00\nPano;1;20,00\nTotal Grupo Alimentos;2;30,00\n", 60.0, 4, 2)

    def test_coincidencia_unica_fica_e_avisa(self):
        # 10 + 10 + 20 = 40: uma só linha fechando não é evidência.
        perfil, tab = self.carga("Produto;Qtd;Valor\nArroz;1;10,00\nFeijao;1;10,00\nTotal Clean Detergente;2;20,00\n")
        self.assertEqual(self.soma(), 40.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (3, 0))
        aviso = self.dobro(perfil)
        self.assertEqual(len(aviso), 1)
        self.assertIn('"Produto"', aviso[0])
        self.assertIn("Total Clean Detergente", aviso[0])

    def test_um_total_depto_so_fica_e_avisa(self):
        # 1 + 2 + 3 = 6: sem segundo fechamento, nada sai da tabela.
        perfil, tab = self.carga("Depto;Produto;Valor\nMercearia;Arroz;1,00\nMercearia;Feijao;2,00\nTotal Depto Mercearia;;3,00\n")
        self.assertEqual(self.soma(), 6.0)
        self.assertEqual(tab["linhas_total"], 0)
        self.assertTrue(self.dobro(perfil))

    def test_produto_total_dia_so_avisa(self):
        # 5 + 7 = 12.
        perfil, tab = self.carga("Produto;Valor\nTotal Dia Sabonete;5,00\nArroz;7,00\n")
        self.assertEqual(self.soma(), 12.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (2, 0))
        aviso = self.dobro(perfil)
        self.assertTrue(aviso and "Total Dia Sabonete" in aviso[0])

    def test_grupo_de_uma_linha_nao_fecha(self):
        # 5 + 5 + 7 + 7 = 24: dois fechamentos, mas cada um com uma linha só.
        perfil, tab = self.carga("Produto;Qtd;Valor\nArroz;1;5,00\nTotal Alfa;1;5,00\nFeijao;1;7,00\nTotal Beta;1;7,00\n")
        self.assertEqual(self.soma(), 24.0)
        self.assertEqual(tab["linhas_total"], 0)
        self.assertTrue(self.dobro(perfil))

    def test_coluna_numerica_que_nao_fecha_impede(self):
        # Valor fecha, Qtd (9) não: 1 + 2 + 3 + 1 + 2 + 3 = 12.
        perfil, tab = self.carga("Produto;Qtd;Valor\nArroz;1;1,00\nFeijao;1;2,00\nTotal Depto A;9;3,00\n"
                                 "Queijo;1;1,00\nSal;1;2,00\nTotal Depto B;9;3,00\n")
        self.assertEqual(self.soma(), 12.0)
        self.assertEqual(tab["linhas_total"], 0)
        self.assertTrue(self.dobro(perfil))

    def test_produto_com_total_no_nome_entra_na_soma_do_grupo(self):
        # 1 + 2 fecham em 3 mesmo com o produto Total Clean no grupo: 1 + 2 + 1 + 2 = 6.
        perfil, tab = self.carga("Produto;Qtd;Valor\nArroz;1;1,00\nTotal Clean;1;2,00\nTotal Depto A;2;3,00\n"
                                 "Queijo;1;1,00\nSal;1;2,00\nTotal Depto B;2;3,00\n")
        self.assertEqual(self.soma(), 6.0)
        self.assertEqual((tab["linhas"], tab["linhas_total"]), (4, 2))
        aviso = self.dobro(perfil)
        self.assertEqual(len(aviso), 1)
        self.assertIn("Total Clean", aviso[0])

    def test_varios_produtos_geram_um_aviso_por_coluna(self):
        # 1 + 2 + 3 + 4 = 10.
        perfil, _ = self.carga("Produto;Valor\nTotal Alfa;1,00\nTotal Beta;2,00\nTotal Gama;3,00\nArroz;4,00\n")
        self.assertEqual(self.soma(), 10.0)
        aviso = self.dobro(perfil)
        self.assertEqual(len(aviso), 1)
        self.assertIn("3 linha", aviso[0])

    def test_acento_e_caixa_nao_importam_no_aviso(self):
        perfil, _ = self.carga("Produto;Valor\nTOTÁL Depósito;1,00\nArroz;4,00\n")
        self.assertTrue(self.dobro(perfil))

    def test_palavra_total_sozinha_ou_no_meio_nao_avisa(self):
        perfil, _ = self.carga("Produto;Valor\nSubtotalzinho;1,00\nArroz Total;4,00\n")
        self.assertEqual(self.dobro(perfil), [])


class TestDataZerada(Base):
    def carga(self):
        linhas = "".join(f"{i};{'00/00/0000' if i <= 12 else f'{i:02d}/01/2026'}\n" for i in range(1, 21))
        return carregar([self.csv("d.csv", "id;baixa\n" + linhas)], self.base)

    def test_data_zerada_nao_vota_contra_a_coluna(self):
        # 12 de 20 em aberto (60%), 8 datas reais: dias 13 a 20.
        perfil = self.carga()
        coluna = perfil["tabelas"][0]["colunas"][1]
        self.assertEqual(coluna["tipo"], "data")
        self.assertEqual((coluna["min"], coluna["max"]), ("2026-01-13", "2026-01-20"))
        self.assertEqual(coluna["vazios_pct"], 60.0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM d WHERE baixa IS NULL")["linhas"][0][0], 12)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM d WHERE baixa >= '2026-01-15'")["linhas"][0][0], 6)

    def test_aviso_cita_a_data_zerada_uma_vez(self):
        aviso = [a for a in self.carga()["avisos"] if '"baixa"' in a]
        self.assertEqual(len(aviso), 1)
        self.assertEqual(aviso[0].count("00/00/0000"), 1)
        self.assertIn("12", aviso[0])

    def test_lixo_de_verdade_aparece_antes_da_zerada(self):
        linhas = "".join(f"{i};00/00/0000\n" for i in range(1, 7)) + "7;abc\n" + "".join(f"{i};{i:02d}/01/2026\n" for i in range(8, 20))
        aviso = [a for a in carregar([self.csv("d.csv", "id;baixa\n" + linhas)], self.base)["avisos"] if '"baixa"' in a]
        self.assertLess(aviso[0].index("abc"), aviso[0].index("00/00/0000"))

    def test_coluna_toda_zerada_nao_vira_data(self):
        perfil = carregar([self.csv("d.csv", "id;baixa\n1;00/00/0000\n2;00/00/0000\n")], self.base)
        self.assertEqual(perfil["tabelas"][0]["colunas"][1]["tipo"], "texto")


class TestDataComLixo(Base):
    def test_data_invalida_vira_nulo_com_aviso(self):
        linhas = "".join(f"{i};{i:02d}/01/2026\n" for i in range(1, 10)) + "10;00/00/0000\n"
        perfil = carregar([self.csv("d.csv", "id;data\n" + linhas)], self.base)
        coluna = perfil["tabelas"][0]["colunas"][1]
        self.assertEqual(coluna["tipo"], "data")
        self.assertEqual((coluna["min"], coluna["max"]), ("2026-01-01", "2026-01-09"))
        self.assertEqual(self.sql("SELECT data FROM d WHERE id = 10")["linhas"], [[None]])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM d WHERE data >= '2026-01-05'")["linhas"][0][0], 5)
        aviso = [a for a in perfil["avisos"] if '"data"' in a]
        self.assertTrue(aviso and "00/00/0000" in aviso[0])

    def test_abaixo_de_80_por_cento_continua_texto(self):
        perfil = carregar([self.csv("d.csv", "id;d\n1;01/01/2026\n2;abc\n3;def\n")], self.base)
        self.assertEqual(perfil["tabelas"][0]["colunas"][1]["tipo"], "texto")

    def test_data_valida_nao_gera_aviso(self):
        perfil = carregar([self.csv("d.csv", "id;data\n1;01/01/2026\n2;02/01/2026\n")], self.base)
        self.assertFalse(any('"data"' in a for a in perfil["avisos"]))


class TestPerfilValores(Base):
    def coluna(self, perfil, nome):
        return next(c for c in perfil["tabelas"][0]["colunas"] if c["nome"] == nome)

    def test_coluna_de_texto_lista_valores_distintos(self):
        perfil = carregar([self.csv("v.csv", "id;status\n1;Ativo\n2;Cancelado\n3;Ativo\n4;\n")], self.base)
        self.assertEqual(self.coluna(perfil, "status")["valores"],
                         [{"valor": "Ativo", "linhas": 2}, {"valor": "Cancelado", "linhas": 1}])

    def test_acima_de_20_valores_nao_lista(self):
        linhas = "".join(f"{i};v{i}\n" for i in range(21))
        self.assertNotIn("valores", self.coluna(carregar([self.csv("v.csv", "id;s\n" + linhas)], self.base), "s"))

    def test_20_valores_ainda_lista(self):
        linhas = "".join(f"{i};v{i}\n" for i in range(20))
        self.assertEqual(len(self.coluna(carregar([self.csv("v.csv", "id;s\n" + linhas)], self.base), "s")["valores"]), 20)

    def test_coluna_numerica_nao_lista(self):
        self.assertNotIn("valores", self.coluna(carregar([self.csv("v.csv", "id;s\n1;x\n2;y\n")], self.base), "id"))

    def test_possivel_cpf_nao_aparece_no_perfil(self):
        for nome, valores in (("n", ("12345678909", "98765432100")), ("z", ("01234567890", "09876543210"))):
            with self.subTest(nome):
                arq = self.csv(f"{nome}.csv", f"id;doc\n1;{valores[0]}\n2;{valores[1]}\n")
                perfil = carregar([arq], self.base)
                coluna = self.coluna(perfil, "doc")
                self.assertNotIn("min", coluna)
                self.assertNotIn("max", coluna)
                self.assertNotIn("valores", coluna)
                for valor in valores:
                    self.assertNotIn(valor, json.dumps(perfil, ensure_ascii=False))


class TestConsultar(Base):
    def setUp(self):
        super().setUp()
        carregar([self.csv("t.csv", "a;b\n1;x\n2;y\n3;z\n")], self.base)

    def test_consultar_e_so_leitura(self):
        for sql in ("INSERT INTO t VALUES (9, 'q')", "DROP TABLE t", "DELETE FROM t",
                    "ATTACH DATABASE ':memory:' AS m", "PRAGMA query_only=OFF",
                    "SELECT 1; DROP TABLE t"):
            with self.assertRaises(ErroDados, msg=sql):
                consultar(self.base, sql)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM t")["linhas"][0][0], 3)

    def test_funcoes_de_janela_e_cte(self):
        r = self.sql("WITH x AS (SELECT a, SUM(a) OVER (ORDER BY a) s FROM t) SELECT s FROM x ORDER BY a")
        self.assertEqual([l[0] for l in r["linhas"]], [1, 3, 6])

    def test_limite_trunca_e_avisa(self):
        r = consultar(self.base, "SELECT a FROM t ORDER BY a", limite=2)
        self.assertEqual(r["linhas"], [[1], [2]])
        self.assertTrue(r["truncado"])
        self.assertTrue(r["avisos"])
        r = consultar(self.base, "SELECT a FROM t", limite=3)
        self.assertFalse(r["truncado"])
        self.assertEqual(r["colunas"], ["a"])

    def test_coluna_inexistente_diz_o_que_falta(self):
        with self.assertRaises(ErroDados) as ctx:
            consultar(self.base, "SELECT preco FROM t")
        msg = ctx.exception.erros[0]
        self.assertIn("preco", msg)
        self.assertIn("t(a, b)", msg)

    def test_tabela_inexistente_lista_tabelas(self):
        with self.assertRaises(ErroDados) as ctx:
            consultar(self.base, "SELECT * FROM vendas")
        self.assertIn("vendas", ctx.exception.erros[0])
        self.assertIn("t(a, b)", ctx.exception.erros[0])

    def test_base_inexistente(self):
        with self.assertRaises(ErroDados):
            consultar(self.dir / "nao.sqlite", "SELECT 1")


class TestCli(Base):
    def rodar(self, *args):
        saida = io.StringIO()
        with redirect_stdout(saida):
            try:
                codigo = da.main(list(args))
            except SystemExit as e:
                codigo = e.code
        return codigo, json.loads(saida.getvalue())

    def test_fluxo_completo(self):
        arq = self.csv("a.csv", "n\n1\n2\n")
        codigo, perfil = self.rodar("carregar", "--base", str(self.base), str(arq))
        self.assertEqual(codigo, 0)
        self.assertEqual(perfil["tabelas"][0]["linhas"], 2)
        codigo, r = self.rodar("consultar", "--base", str(self.base), "--sql", "SELECT SUM(n) FROM a")
        self.assertEqual((codigo, r["linhas"]), (0, [[3]]))
        codigo, r = self.rodar("apagar", "--base", str(self.base))
        self.assertEqual(codigo, 0)

    def test_erro_sai_com_2_e_json(self):
        codigo, r = self.rodar("consultar", "--base", str(self.base), "--sql", "SELECT 1")
        self.assertEqual(codigo, 2)
        self.assertIn("errors", r)
        codigo, r = self.rodar("carregar", "--base", str(self.base), str(self.dir / "nao.csv"))
        self.assertEqual(codigo, 2)
        self.assertIn("errors", r)


if __name__ == "__main__":
    unittest.main()
