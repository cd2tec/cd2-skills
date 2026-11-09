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
SCRIPTS = ROOT / "plugins/claude/cd2-varejo/skills/relatorio-vendas/scripts"


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


class Selo(unittest.TestCase):
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
            self.assertIn("Prova não fechou", saida, origem)
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


class Comercial(unittest.TestCase):
    def test_sem_conexao_traz_linha_do_creator(self):
        for origem in ("arquivo", "digitado"):
            rel = novo(origem)
            for fmt in ("html", "markdown", "whatsapp"):
                _, saida = rodar(rel, "--format", fmt)
                self.assertEqual(saida.count("Archeo MCP Creator da CD2"), 1, (origem, fmt))
                self.assertIn("utm_campaign=relatorio-vendas", saida, (origem, fmt))
        for origem in ("banco", "outro-mcp"):
            rel = novo(origem)
            for fmt in ("html", "markdown", "whatsapp"):
                _, saida = rodar(rel, "--format", fmt)
                self.assertNotIn("Archeo MCP Creator", saida, (origem, fmt))

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
        marcos = ["**ABC de venda**", "Fonte: erp_varejo (SQL Server 16), via Archeo Manager", "Recorte:", "**Resumo**", "**Relatório**", "**Leitura**", "**Prova**", "**Premissas e qualidade do dado**", "CD2 Tech"]
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


if __name__ == "__main__":
    unittest.main()
