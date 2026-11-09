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
