"""Testes do renderizador comum e do kit de marca, na cópia gerada para o Claude."""
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins/claude/cd2-super/skills/relatorio-vendas/scripts"


def _carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _carregar_da_copia_gerada():
    """Carrega brand e render_relatorio da cópia do Claude, sem deixar o brand do core, que outros testes já
    importaram com esse mesmo nome, trocar de lugar. O render_relatorio faz `import brand`, então o brand da cópia
    fica em sys.modules só durante a carga."""
    anterior = sys.modules.pop("brand", None)
    try:
        marca = _carregar("brand", SCRIPTS / "brand.py")
        render = _carregar("render_relatorio_gerado", SCRIPTS / "render_relatorio.py")
    finally:
        if anterior is None:
            sys.modules.pop("brand", None)
        else:
            sys.modules["brand"] = anterior
    return marca, render


brand, rr = _carregar_da_copia_gerada()

BASE = json.loads((ROOT / "tests/fixtures/relatorio-abc.json").read_text(encoding="utf-8"))


def novo(origem=None):
    rel = copy.deepcopy(BASE)
    if origem:
        rel["origem"] = origem
        if origem in ("arquivo", "digitado"):
            rel["fonte"] = {"nome": "vendas-outubro.csv" if origem == "arquivo" else "números digitados na conversa"}
    return rel


def rodar(rel, *args):
    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / "r.json"
        entrada.write_text(json.dumps(rel, ensure_ascii=False), encoding="utf-8")
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = rr.main(["--input", str(entrada), *args])
    return codigo, saida.getvalue()


class SaidaDoCli(unittest.TestCase):
    def test_cli_nao_diz_prova_para_arquivo_ou_digitado(self):
        for origem in ("arquivo", "digitado"):
            with tempfile.TemporaryDirectory() as tmp:
                _, texto = rodar(novo(origem), "--format", "html", "--output", str(Path(tmp) / "r.html"))
            self.assertIn("Conferência: fechou", texto, origem)
            self.assertNotIn("Prova", texto, origem)

    def test_cli_diz_prova_para_banco_e_outro_mcp(self):
        for origem in ("banco", "outro-mcp"):
            with tempfile.TemporaryDirectory() as tmp:
                _, texto = rodar(novo(origem), "--format", "html", "--output", str(Path(tmp) / "r.html"))
            self.assertIn("Prova: fechou", texto, origem)


class Formatos(unittest.TestCase):
    def test_moeda_e_numero(self):
        self.assertEqual(brand.moeda(4812640), "R$ 4.812.640,00")
        self.assertEqual(brand.moeda(-1234.5), "-R$ 1.234,50")
        self.assertEqual(brand.moeda(-0.001), "R$ 0,00")
        self.assertEqual(brand.numero(5130), "5.130")

    def test_arredondamento_para_cima(self):
        self.assertEqual(brand.moeda(1.005), "R$ 1,01")
        self.assertEqual(brand.pct(79.75), "79,8%")

    def test_compacta_e_data(self):
        self.assertEqual(brand.moeda_compacta(1642310.4), "R$ 1,6 mi")
        self.assertEqual(brand.moeda_compacta(40000), "R$ 40 mil")
        self.assertEqual(brand.data_br("2026-11-08T09:30:00"), "08/11/2026")

    def test_vazio_vira_sem_dado(self):
        self.assertEqual(brand.formatar(None, "moeda"), "s/d")

    def test_tokens_do_design_system(self):
        css = brand.tokens_css()
        self.assertIn("--brand: #0000ff", css)
        self.assertIn("--surface: #f2f2f2", css)
        self.assertIn("Manrope", css)
        self.assertIn('prefers-color-scheme: dark', css)
        self.assertIn(':root[data-theme="dark"]', css)

    def test_rodape_tem_logo_e_aviso(self):
        rodape = brand.footer_dados_html("banco", "08/11/2026")
        self.assertIn("cd2-logo-claro", rodape)
        self.assertIn("08/11/2026", rodape)
        self.assertIn("CD2 Tech", brand.footer_dados_text("banco", "08/11/2026"))


class Validacao(unittest.TestCase):
    def test_sem_prova_nao_sai(self):
        rel = novo()
        rel["prova"]["conferencias"] = []
        codigo, saida = rodar(rel, "--format", "html")
        self.assertEqual(codigo, 2)
        self.assertIn("Relatório sem prova não sai", json.loads(saida)["errors"][0])

    def test_recorte_e_obrigatorio(self):
        rel = novo()
        del rel["recorte"]["periodo"]
        self.assertTrue(any("recorte.periodo" in e for e in rr.validar(rel)))

    def test_cpf_sem_mascara_e_recusado(self):
        rel = novo()
        rel["leitura"][0]["texto"] = "Cliente 123.456.789-09 parou de comprar."
        self.assertTrue(any("CPF" in e for e in rr.validar(rel)))

    def test_coluna_cpf_sem_pontuacao_e_recusada(self):
        rel = novo()
        bloco = rel["blocos"][4]
        bloco["colunas"].append({"campo": "cpf", "rotulo": "CPF"})
        bloco["linhas"][0]["cpf"] = "12345678909"
        self.assertTrue(any("CPF" in e for e in rr.validar(rel)))

    def test_cpf_mascarado_passa(self):
        rel = novo()
        rel["leitura"][0]["texto"] = "Cliente ***.456.789-** parou de comprar."
        self.assertEqual(rr.validar(rel), [])

    def test_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada = Path(tmp) / "r.json"
            entrada.write_text("{", encoding="utf-8")
            saida = io.StringIO()
            with redirect_stdout(saida):
                self.assertEqual(rr.main(["--input", str(entrada), "--format", "html"]), 2)

    def test_sem_origem_recusa(self):
        rel = novo()
        del rel["origem"]
        codigo, saida = rodar(rel, "--format", "html")
        self.assertEqual(codigo, 2)
        self.assertIn("origem", json.dumps(json.loads(saida)["errors"], ensure_ascii=False))

    def test_origem_desconhecida_recusa(self):
        rel = novo()
        rel["origem"] = "planilha"
        self.assertTrue(any("origem" in e for e in rr.validar(rel)))

    def test_sem_skill_recusa(self):
        rel = novo()
        del rel["skill"]
        codigo, saida = rodar(rel, "--format", "html")
        self.assertEqual(codigo, 2)
        self.assertIn("skill", json.dumps(json.loads(saida)["errors"], ensure_ascii=False))

    def test_skill_fora_do_padrao_recusa(self):
        rel = novo()
        rel["skill"] = "vendas&utm_source=x"
        self.assertTrue(any("skill" in e for e in rr.validar(rel)))

    def test_arquivo_pede_nome_do_arquivo_e_nao_banco(self):
        rel = novo("arquivo")
        self.assertEqual(rr.validar(rel), [])
        del rel["fonte"]["nome"]
        self.assertTrue(any("fonte.nome" in e for e in rr.validar(rel)))

    def test_tipo_de_bloco_invalido(self):
        rel = novo()
        rel["blocos"].append({"tipo": "pizza", "titulo": "x"})
        self.assertTrue(any("pizza" in e for e in rr.validar(rel)))


class Prova(unittest.TestCase):
    def test_dentro_da_tolerancia_fecha(self):
        res = rr.avaliar_prova({"conferencias": [{"nome": "a", "esperado": 100.0, "obtido": 101.5}]})
        self.assertTrue(res[0]["fechou"])

    def test_acima_da_tolerancia_nao_fecha(self):
        res = rr.avaliar_prova({"conferencias": [{"nome": "a", "esperado": 100.0, "obtido": 103.0}]})
        self.assertFalse(res[0]["fechou"])

    def test_tolerancia_zero(self):
        res = rr.avaliar_prova({"conferencias": [{"nome": "d=c", "esperado": 1000.0, "obtido": 1000.5, "tolerancia_pct": 0}]})
        self.assertFalse(res[0]["fechou"])

    def test_sem_obtido_nao_fecha(self):
        res = rr.avaliar_prova({"conferencias": [{"nome": "a", "esperado": 100.0, "obtido": None, "motivo": "tabela vazia"}]})
        self.assertFalse(res[0]["fechou"])
        self.assertEqual(res[0]["diferenca"], "tabela vazia")

    def test_prova_que_nao_fecha_vem_antes_do_veredito(self):
        rel = novo()
        rel["prova"]["conferencias"][0]["obtido"] = 4000000.0
        pagina = rr.render_html(rel)
        self.assertIn("Este relatório ainda não fechou", pagina)
        self.assertLess(pagina.index("Este relatório ainda não fechou"), pagina.index(rel["veredito"]["titulo"]))
        self.assertIn("A CONFERIR", pagina)

    def test_prova_fechada_mostra_selo(self):
        self.assertIn("Prova fechada, diferença de R$ 0,00", rr.render_html(novo()))


class TiposErrados(unittest.TestCase):
    def test_fechou_que_nao_e_booleano_recusa(self):
        for valor in ("false", "não", "true", 0, 1, None, []):
            rel = novo()
            rel["prova"]["conferencias"][1]["fechou"] = valor
            codigo, saida = rodar(rel, "--format", "html")
            self.assertEqual(codigo, 2, valor)
            self.assertIn("fechou", json.dumps(json.loads(saida)["errors"], ensure_ascii=False))

    def test_fechou_false_nao_fecha_a_prova(self):
        rel = novo()
        rel["prova"]["conferencias"][1]["fechou"] = False
        self.assertFalse(rr.avaliar_prova(rel["prova"])[1]["fechou"])
        self.assertIn("Prova não fechou", rr.render_html(rel))

    def test_formas_erradas_saem_com_codigo_2_e_sem_traceback(self):
        casos = {
            "conferencias lista de texto": lambda r: r["prova"].update(conferencias=["x"]),
            "conferencias texto": lambda r: r["prova"].update(conferencias="x"),
            "prova texto": lambda r: r.update(prova="x"),
            "fonte lista": lambda r: r.update(fonte=["x"]),
            "fonte texto": lambda r: r.update(fonte="x"),
            "recorte texto": lambda r: r.update(recorte="x"),
            "recorte lista": lambda r: r.update(recorte=[1]),
            "veredito texto": lambda r: r.update(veredito="x"),
            "numeros texto": lambda r: r["veredito"].update(numeros="abc"),
            "numeros itens texto": lambda r: r["veredito"].update(numeros=["a"]),
            "leitura texto": lambda r: r.update(leitura="x"),
            "leitura itens texto": lambda r: r.update(leitura=["x"]),
            "resumo itens texto": lambda r: r.update(resumo=["x"]),
            "resumo numero": lambda r: r.update(resumo=3),
            "colunas texto": lambda r: r["blocos"][4].update(colunas="x"),
            "colunas itens texto": lambda r: r["blocos"][4].update(colunas=["x"]),
            "linhas itens texto": lambda r: r["blocos"][4].update(linhas=["x"]),
            "total texto": lambda r: r["blocos"][4].update(total="x"),
            "classes itens texto": lambda r: r["blocos"][0].update(classes=["x"]),
            "barras linhas texto": lambda r: r["blocos"][1].update(linhas="x"),
            "pontos itens texto": lambda r: r["blocos"][2].update(pontos=["x"]),
            "etapas itens texto": lambda r: r["blocos"][3].update(etapas=["x", "y"]),
            "blocos texto": lambda r: r.update(blocos="x"),
            "bloco texto": lambda r: r.update(blocos=["x"]),
            "premissas lista": lambda r: r.update(premissas=[]),
            "premissas filtros texto": lambda r: r["premissas"].update(filtros="x"),
            "proximos texto": lambda r: r.update(proximos="x"),
            "avisos texto": lambda r: r.update(avisos="x"),
            "tolerancia texto": lambda r: r["prova"].update(tolerancia_pct="2"),
            "titulo numero": lambda r: r.update(titulo=5),
            "origem lista": lambda r: r.update(origem=["banco"]),
            "nivel lista": lambda r: r["leitura"][0].update(nivel=[]),
            "nivel dict": lambda r: r["leitura"][0].update(nivel={}),
            "formato da coluna lista": lambda r: r["blocos"][4]["colunas"][1].update(formato=[]),
            "formato da coluna dict": lambda r: r["blocos"][4]["colunas"][1].update(formato={}),
            "tipo do bloco lista": lambda r: r["blocos"][4].update(tipo=[]),
            "tipo da etapa lista": lambda r: r["blocos"][3]["etapas"][0].update(tipo=[]),
            "raiz lista": None,
        }
        for nome, mexer in casos.items():
            rel = novo()
            if mexer is None:
                rel = ["x"]
            else:
                mexer(rel)
            for fmt in ("html", "csv"):
                try:
                    codigo, saida = rodar(rel, "--format", fmt)
                except Exception as exc:  # pragma: no cover - a falha é o que o teste procura
                    self.fail(f"{nome}: levantou {type(exc).__name__}: {exc}")
                self.assertEqual(codigo, 2, nome)
                self.assertTrue(json.loads(saida)["errors"], nome)


class SugerirConexao(unittest.TestCase):
    """Quem disse não à sugestão de conectar não recebe a linha do Archeo MCP Creator."""

    def saida(self, rel, fmt):
        codigo, texto = rodar(rel, "--format", fmt)
        self.assertEqual(codigo, 0, texto)
        return texto

    def test_false_tira_a_linha_em_todo_formato(self):
        for origem in ("arquivo", "digitado"):
            for fmt in rr.SAIDAS:
                rel = novo(origem)
                rel["sugerir_conexao"] = False
                saida = self.saida(rel, fmt)
                self.assertNotIn("Archeo MCP Creator", saida, (origem, fmt))
                self.assertNotIn("archeo.cd2.com.br", saida, (origem, fmt))

    def test_padrao_e_true_mantem_a_linha(self):
        for origem in ("arquivo", "digitado"):
            for fmt in ("html", "markdown", "whatsapp"):
                com_padrao, explicito = novo(origem), novo(origem)
                explicito["sugerir_conexao"] = True
                self.assertEqual(self.saida(com_padrao, fmt).count("Archeo MCP Creator da CD2"), 1, (origem, fmt))
                self.assertEqual(self.saida(explicito, fmt).count("Archeo MCP Creator da CD2"), 1, (origem, fmt))

    def test_false_nao_muda_o_selo_nem_o_convite(self):
        rel = novo("arquivo")
        rel["sugerir_conexao"] = False
        saida = self.saida(rel, "markdown")
        self.assertIn(rr.SELO_ARQUIVO, saida)
        self.assertNotIn("Prova fechada", saida)
        self.assertIn(rr.CONVITE, saida)

    def test_nao_booleano_sai_com_codigo_2(self):
        for valor in ("false", 0, 1, None, [], {}):
            rel = novo("arquivo")
            rel["sugerir_conexao"] = valor
            codigo, texto = rodar(rel, "--format", "markdown")
            self.assertEqual(codigo, 2, repr(valor))
            self.assertIn("sugerir_conexao", json.loads(texto)["errors"][0], repr(valor))


class Selo(unittest.TestCase):
    def test_selo_prova_exige_a_origem(self):
        with self.assertRaises(TypeError):
            rr.selo_prova(rr.avaliar_prova(novo()["prova"]))

    def test_selo_prova_nao_diz_fechada_para_arquivo(self):
        res = rr.avaliar_prova(novo()["prova"])
        for origem in ("arquivo", "digitado"):
            self.assertEqual(rr.selo_prova(res, origem), "Conferido só contra o arquivo")
        for origem in ("banco", "outro-mcp"):
            self.assertTrue(rr.selo_prova(res, origem).startswith("Prova fechada"))

    def test_arquivo_nunca_diz_prova_fechada(self):
        for origem in ("arquivo", "digitado"):
            for fmt in ("html", "markdown", "whatsapp", "csv"):
                rel = novo(origem)
                codigo, saida = rodar(rel, "--format", fmt)
                self.assertEqual(codigo, 0, (origem, fmt))
                self.assertNotIn("Prova fechada", saida, (origem, fmt))
                self.assertIn("Conferido só contra o arquivo", saida, (origem, fmt))

    def test_banco_e_outro_mcp_dizem_prova_fechada(self):
        for origem in ("banco", "outro-mcp"):
            for fmt in ("html", "markdown"):
                rel = novo(origem)
                codigo, saida = rodar(rel, "--format", fmt)
                self.assertEqual(codigo, 0)
                self.assertIn("Prova fechada, diferença de R$ 0,00", saida, (origem, fmt))
                self.assertNotIn("Conferido só contra o arquivo", saida, (origem, fmt))

    def test_conferencia_que_nao_fecha_abre_vermelho_em_toda_origem(self):
        for origem in brand.ORIGENS:
            rel = novo(origem)
            rel["prova"]["conferencias"][0]["obtido"] = 1.0
            codigo, saida = rodar(rel, "--format", "html")
            self.assertEqual(codigo, 0)
            esperado = "Prova não fechou" if origem in ("banco", "outro-mcp") else "Conferência não fechou"
            self.assertIn(esperado, saida, origem)
            self.assertNotIn("Prova fechada", saida, origem)
            self.assertNotIn("Conferido só contra o arquivo", saida, origem)

    def test_aviso_por_origem(self):
        esperado = {
            "banco": "Elas usam os dados do banco conectado em 08/11/2026.",
            "outro-mcp": "Elas usam os dados do banco conectado em 08/11/2026.",
            "arquivo": "Elas usam o arquivo informado em 08/11/2026.",
            "digitado": "Elas usam os dados informados em 08/11/2026.",
        }
        for origem, frase in esperado.items():
            rel = novo(origem)
            for fmt in ("html", "markdown", "whatsapp"):
                _, saida = rodar(rel, "--format", fmt)
                self.assertIn(frase, saida, (origem, fmt))
        self.assertIn(esperado["arquivo"], brand.disclaimer_dados("arquivo", "08/11/2026"))
        with self.assertRaises(ValueError):
            brand.disclaimer_dados("planilha", "08/11/2026")

    def test_cabecalho_e_leitura_seguem_a_origem(self):
        rel = novo("arquivo")
        pagina = rr.render_html(rel)
        self.assertIn("DO SEU ARQUIVO", pagina)
        self.assertNotIn("DO SEU BANCO", pagina)
        self.assertIn("Fonte: arquivo vendas-outubro.csv", pagina)
        self.assertNotIn("ARCHEO", pagina)


class Titulo(unittest.TestCase):
    MARCAS = {"html": ">Conferência</h2>", "markdown": "**Conferência**", "csv": "\r\nConferência\r\n"}
    MARCAS_BANCO = {"html": ">Prova</h2>", "markdown": "**Prova**", "csv": "\r\nProva\r\n"}

    def test_arquivo_e_digitado_dizem_conferencia_nos_quatro_formatos(self):
        for origem in ("arquivo", "digitado"):
            for fmt in ("html", "markdown", "csv", "whatsapp"):
                codigo, saida = rodar(novo(origem), "--format", fmt)
                self.assertEqual(codigo, 0, (origem, fmt))
                self.assertNotIn("Prova", saida, (origem, fmt))
                if fmt in self.MARCAS:
                    self.assertIn(self.MARCAS[fmt], saida, (origem, fmt))

    def test_banco_continua_dizendo_prova(self):
        for origem in ("banco", "outro-mcp"):
            for fmt, marca in self.MARCAS_BANCO.items():
                self.assertIn(marca, rodar(novo(origem), "--format", fmt)[1], (origem, fmt))

    def test_nao_fechou_diz_conferencia_nos_quatro_formatos(self):
        esperado = {"html": "Conferência não fechou", "markdown": "A conferência não fechou",
                    "csv": "Conferência não fechou", "whatsapp": "Conferência: NÃO FECHOU"}
        for origem in ("arquivo", "digitado"):
            rel = novo(origem)
            rel["prova"]["conferencias"][0]["obtido"] = 1.0
            for fmt, marca in esperado.items():
                _, saida = rodar(rel, "--format", fmt)
                self.assertIn(marca, saida, (origem, fmt))
                self.assertNotIn("Prova", saida, (origem, fmt))

    def test_banco_que_nao_fechou_continua_prova(self):
        esperado = {"html": "Prova não fechou", "markdown": "A prova não fechou",
                    "csv": "Prova não fechou", "whatsapp": "Prova: NÃO FECHOU"}
        rel = novo("banco")
        rel["prova"]["conferencias"][0]["obtido"] = 1.0
        for fmt, marca in esperado.items():
            self.assertIn(marca, rodar(rel, "--format", fmt)[1], fmt)


class ProvaFechadaNoTexto(unittest.TestCase):
    def casos(self):
        return {
            "veredito": lambda r: r["veredito"].update(texto="Prova fechada, pode confiar."),
            "resumo": lambda r: r["resumo"][0].update(legenda="prova FECHADA"),
            "leitura": lambda r: r["leitura"][0].update(texto="A Prova fechada mostra que bate."),
        }

    def test_arquivo_e_digitado_recusam(self):
        for origem in ("arquivo", "digitado"):
            for campo, mexer in self.casos().items():
                rel = novo(origem)
                mexer(rel)
                codigo, texto = rodar(rel, "--format", "markdown")
                self.assertEqual(codigo, 2, (origem, campo))
                self.assertIn(campo, json.loads(texto)["errors"][0], (origem, campo))

    def test_banco_aceita(self):
        for origem in ("banco", "outro-mcp"):
            for campo, mexer in self.casos().items():
                rel = novo(origem)
                mexer(rel)
                self.assertEqual(rodar(rel, "--format", "markdown")[0], 0, (origem, campo))


class AvisoConferencia(unittest.TestCase):
    AVISO = "Não é documento oficial"

    def test_fiscal_e_contabil_trazem_o_aviso_sem_o_campo(self):
        for skill in ("relatorio-fiscal", "relatorio-contabil"):
            for valor in (None, False):
                rel = novo()
                rel["skill"] = skill
                rel.pop("conferencia", None)
                if valor is False:
                    rel["conferencia"] = False
                self.assertIn(self.AVISO, rr.render_html(rel), skill)
                self.assertIn(self.AVISO, rr.render_markdown(rel), skill)

    def test_outras_skills_nao_trazem(self):
        rel = novo()
        rel.pop("conferencia", None)
        self.assertNotIn(self.AVISO, rr.render_html(rel))
        self.assertNotIn(self.AVISO, rr.render_markdown(rel))


class Comercial(unittest.TestCase):
    def test_sem_conexao_traz_linha_do_creator(self):
        for origem in ("arquivo", "digitado"):
            rel = novo(origem)
            for fmt in ("html", "markdown", "whatsapp"):
                _, saida = rodar(rel, "--format", fmt)
                self.assertEqual(saida.count("Archeo MCP Creator da CD2"), 1, (origem, fmt))
                self.assertEqual(saida.count("conecta o banco do sistema"), 1, (origem, fmt))
                self.assertIn("utm_campaign=relatorio-vendas", saida, (origem, fmt))
        for origem in ("banco", "outro-mcp"):
            rel = novo(origem)
            for fmt in ("html", "markdown", "whatsapp"):
                _, saida = rodar(rel, "--format", fmt)
                self.assertNotIn("conecta o banco do sistema", saida, (origem, fmt))
                self.assertNotIn("archeo.cd2.com.br", saida, (origem, fmt))

    def test_linha_do_creator_vem_antes_do_rodape(self):
        pagina = rr.render_html(novo("arquivo"))
        self.assertLess(pagina.index("Archeo MCP Creator da CD2"), pagina.index('<p class="cd2-assinatura-aviso"'))

    def test_convite_comercial(self):
        for fmt in ("html", "markdown", "whatsapp"):
            _, saida = rodar(novo(), "--format", fmt)
            self.assertIn("Testar na sua operação é livre.", saida, fmt)
            self.assertIn("https://wa.me/5519982355172?text=", saida, fmt)
            self.assertNotIn("ameaça", saida)

    def test_plataforma_entra_na_mensagem_do_whatsapp(self):
        _, saida = rodar(novo(), "--format", "markdown", "--platform", "Codex")
        self.assertIn("no%20Codex", saida)
        self.assertIn("skill%20Relat%C3%B3rio%20de%20vendas", saida)

    def test_utm_da_skill_nos_links(self):
        pagina = rr.render_html(novo("arquivo"))
        self.assertIn("utm_source=claude&amp;utm_medium=skill&amp;utm_campaign=relatorio-vendas", pagina)
        self.assertNotIn("{{UTM_SOURCE}}", pagina)


class Html(unittest.TestCase):
    def setUp(self):
        self.pagina = rr.render_html(novo())

    def test_sem_marcador_sobrando(self):
        self.assertNotIn("{{", self.pagina)

    def test_autocontido(self):
        self.assertIn("font/woff2;base64", self.pagina)
        self.assertNotIn('src="http', self.pagina)
        self.assertNotIn("<link", self.pagina)

    def test_titulo_antes_da_fonte(self):
        self.assertLess(self.pagina.index("<title>"), 8000)

    def test_secoes_na_ordem(self):
        marcos = ["386 produtos fazem", 'class="recorte"', 'aria-label="Resumo"', "DO SEU BANCO", "Curva ABC", "Prova</h2>", "Premissas e qualidade", '<p class="cd2-assinatura-aviso"']
        posicoes = [self.pagina.index(m) for m in marcos]
        self.assertEqual(posicoes, sorted(posicoes))

    def test_sem_travessao_gerado(self):
        self.assertNotIn(chr(0x2014), self.pagina)
        self.assertNotIn(chr(0x2013), self.pagina)

    def test_celula_maliciosa_na_pagina(self):
        rel = novo()
        rel["blocos"][4]["linhas"][0]["descricao"] = "<script>x</script>"
        self.assertNotIn("<script>x", rr.render_html(rel))

    def test_escapa_texto_do_banco(self):
        rel = novo()
        rel["blocos"][4]["linhas"][0]["descricao"] = "<script>alert(1)</script>"
        rel["premissas"]["consulta"] = "SELECT '</pre><img src=x>'"
        pagina = rr.render_html(rel)
        self.assertNotIn("<script>alert", pagina)
        self.assertNotIn("<img src=x>", pagina)

    def test_marcador_vindo_do_banco_nao_expande(self):
        rel = novo()
        rel["cliente"] = "{{FONT_FACE}}"
        self.assertIn("{{FONT_FACE}}", rr.render_html(rel))

    def test_alerta_na_coluna(self):
        self.assertEqual(self.pagina.count('class="n alerta"'), 1)

    def test_tabela_corta_em_30_linhas(self):
        rel = novo()
        rel["blocos"][4]["linhas"] = [{"descricao": f"Item {i}", "valor": 1.0, "margem": 5.0, "classe": "C"} for i in range(45)]
        pagina = rr.render_html(rel)
        self.assertIn("Item 29", pagina)
        self.assertNotIn("Item 30<", pagina)
        self.assertIn("Mostrando 30 de 45", pagina)

    def test_aviso_de_conferencia(self):
        rel = novo()
        rel["conferencia"] = True
        self.assertIn("Não é documento oficial", rr.render_html(rel))

    def test_tema_forcado(self):
        self.assertIn('data-theme="dark"', rr.render_html(novo(), "dark"))
        self.assertNotIn('<html lang="pt-BR" data-theme', self.pagina)

    def test_linha_com_valores_negativos(self):
        rel = novo()
        rel["blocos"][2]["pontos"] = [{"x": "2026-10-01", "atual": -5000.0}, {"x": "2026-10-02", "atual": 8000.0}]
        self.assertIn("polyline", rr.render_html(rel))


class Texto(unittest.TestCase):
    def test_markdown_segue_o_metodo(self):
        texto = rr.render_markdown(novo())
        marcos = ["**ABC de venda**", "Fonte: erp_varejo (SQL Server 16), via Archeo MCP Creator da CD2", "Recorte:", "**Resumo**", "**Relatório**", "**Leitura**", "**Prova**", "**Premissas e qualidade do dado**", "CD2 Tech"]
        posicoes = [texto.index(m) for m in marcos]
        self.assertEqual(posicoes, sorted(posicoes))

    def test_markdown_escapa_barra(self):
        rel = novo()
        rel["blocos"][4]["linhas"][0]["descricao"] = "A|B"
        self.assertIn("A\\|B", rr.render_markdown(rel))

    def test_whatsapp_curto(self):
        texto = rr.render_whatsapp(novo())
        self.assertIn("*386 produtos fazem 80% da sua venda*", texto)
        self.assertIn("Prova: fechou, diferença de R$ 0,00.", texto)
        self.assertTrue(texto.rstrip().endswith("agir."))

    def test_whatsapp_avisa_prova_aberta(self):
        rel = novo()
        rel["prova"]["conferencias"][0]["obtido"] = 1.0
        self.assertIn("NÃO FECHOU", rr.render_whatsapp(rel))

    def test_csv_para_excel_brasileiro(self):
        texto = rr.render_csv(novo())
        self.assertTrue(texto.startswith("﻿"))
        self.assertIn("184734,00", texto)
        self.assertIn(";", texto)

    def test_csv_neutraliza_formula(self):
        rel = novo()
        rel["blocos"][4]["linhas"][0]["descricao"] = '=HYPERLINK("http://x")'
        texto = rr.render_csv(rel)
        self.assertNotIn(";=HYPERLINK", texto)
        self.assertNotIn("\r\n=HYPERLINK", texto)
        self.assertIn("'=HYPERLINK", texto)

    def test_celula_maliciosa(self):
        rel = novo()
        rel["blocos"][4]["linhas"][0]["descricao"] = "<script>x</script>"
        rel["blocos"][4]["linhas"][1]["descricao"] = "=HYPERLINK(1)"
        pagina = rr.render_html(rel)
        self.assertNotIn("<script>x", pagina)
        texto = rr.render_csv(rel)
        for linha in texto.split("\r\n"):
            for celula in linha.split(";"):
                self.assertFalse(celula.lstrip('"').startswith("="), celula)
        self.assertIn("'=HYPERLINK(1)", texto)

    def test_csv_traz_o_selo_como_linha(self):
        self.assertIn("Selo;", rr.render_csv(novo()))
        texto = rr.render_csv(novo("arquivo"))
        self.assertIn("Selo;Conferido só contra o arquivo", texto)
        self.assertNotIn("Prova fechada", texto)

    def test_csv_leva_todas_as_linhas(self):
        rel = novo()
        rel["blocos"][4]["linhas"] = [{"descricao": f"Item {i}", "valor": 1.0, "margem": 5.0, "classe": "C"} for i in range(45)]
        self.assertIn("Item 44", rr.render_csv(rel))


class Cli(unittest.TestCase):
    def test_grava_arquivo_e_informa_a_prova(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "saida.html"
            codigo, saida = rodar(novo(), "--format", "html", "--output", str(destino))
            self.assertEqual(codigo, 0)
            self.assertIn("Prova: fechou", saida)
            self.assertTrue(destino.read_text(encoding="utf-8").startswith("<!doctype html>"))


ATA = json.loads((ROOT / "tests/fixtures/rotina-ata.json").read_text(encoding="utf-8"))


def ata():
    return copy.deepcopy(ATA)


def bloco(rel, tipo):
    return next(b for b in rel["blocos"] if b["tipo"] == tipo)


class BlocosDeRotina(unittest.TestCase):
    def test_ata_aceita_e_titulo_proprio(self):
        codigo, _ = rodar(ata(), "--format", "markdown")
        self.assertEqual(codigo, 0)
        self.assertEqual(rr._titulo_skill(ata()), "Ata de negociação")

    def test_acordo_sem_trecho_recusa(self):
        for vazio in ("", "   "):
            rel = ata()
            bloco(rel, "acordos")["itens"][0]["trecho"] = vazio
            codigo, saida = rodar(rel, "--format", "markdown")
            self.assertEqual(codigo, 2, vazio)
            self.assertIn("trecho", saida)

    def test_pendencia_sem_dono_ou_data_recusa(self):
        for campo in ("dono", "data"):
            rel = ata()
            del bloco(rel, "pendencias")["itens"][0][campo]
            codigo, saida = rodar(rel, "--format", "markdown")
            self.assertEqual(codigo, 2, campo)
            self.assertIn(campo, saida)

    def test_lista_vazia_entrega(self):
        for tipo in ("agenda", "acordos", "pendencias"):
            rel = ata()
            bloco(rel, tipo)["itens"] = []
            codigo, _ = rodar(rel, "--format", "markdown")
            self.assertEqual(codigo, 0, tipo)
            self.assertIn("Sem itens neste recorte", rr.render(rel, "html"), tipo)
            self.assertIn("Sem itens neste recorte", rr.render(rel, "markdown"), tipo)

    def test_origem_texto_sai_no_html_e_no_markdown(self):
        for formato in ("html", "markdown"):
            self.assertIn("De: anotações da visita", rr.render(ata(), formato), formato)

    def test_origem_texto_em_bloco_antigo(self):
        rel = novo()
        rel["blocos"][0]["origem_texto"] = "De: venda por dia, banco Exemplo"
        self.assertIn("De: venda por dia, banco Exemplo", rr.render(rel, "html"))

    def test_origem_texto_nao_texto_recusa(self):
        rel = ata()
        rel["blocos"][0]["origem_texto"] = 123
        codigo, saida = rodar(rel, "--format", "markdown")
        self.assertEqual(codigo, 2)
        self.assertIn("origem_texto", saida)

    def test_trecho_com_html_sai_escapado(self):
        rel = ata()
        bloco(rel, "acordos")["itens"][0]["trecho"] = "<script>x</script>"
        pagina = rr.render(rel, "html")
        self.assertNotIn("<script>x</script>", pagina)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", pagina)

    def test_csv_e_whatsapp_com_blocos_novos(self):
        for formato in ("csv", "whatsapp"):
            codigo, _ = rodar(ata(), "--format", formato)
            self.assertEqual(codigo, 0, formato)
        self.assertIn("fechamos 35 dias", rr.render(ata(), "csv"))

    def test_skill_fora_da_lista_recusa(self):
        rel = ata()
        rel["skill"] = "rotina-qualquer"
        codigo, saida = rodar(rel, "--format", "markdown")
        self.assertEqual(codigo, 2)
        self.assertIn("skill", saida)

    def test_cinco_rotinas_aceitas(self):
        titulos = {
            "briefing-do-dia": "Briefing do dia", "sinais-da-operacao": "Sinais da operação",
            "preparo-de-negociacao": "Preparo de negociação", "ata-de-negociacao": "Ata de negociação",
            "plano-de-ofertas": "Plano de ofertas",
        }
        for skill, titulo in titulos.items():
            rel = ata()
            rel["skill"] = skill
            codigo, _ = rodar(rel, "--format", "markdown")
            self.assertEqual(codigo, 0, skill)
            self.assertEqual(rr._titulo_skill(rel), titulo)


if __name__ == "__main__":
    unittest.main()
