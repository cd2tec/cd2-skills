"""Testes do painel de varejo e da ficha do Archeo MCP Creator, nas cópias geradas para o Claude."""
import codecs
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Nomes do repositório e das skills antigas, em rot13 para este arquivo não carregar o que ele procura.
NOMES_ANTIGOS = tuple(codecs.decode(s, "rot13") for s in (
    "nepurb-unearff", "nanylmr-zpc", "ohvyq-zpc-qnfuobneq", "fcrp-zpc-gbby", "Ergnvy Grpu"))
CORE = ROOT / "core/cd2-super/skills"
PAINEL = ROOT / "plugins/claude/cd2-super/skills/painel-varejo"
FICHA = ROOT / "plugins/claude/cd2-super/skills/ficha-archeo-mcp"
BUILD = PAINEL / "scripts/build_dashboard.py"
PREVIEW = PAINEL / "scripts/preview_dashboard.py"

CONFIG_BANCO = {
    "titulo": "Painel Rede Exemplo",
    "rede": "Rede Exemplo · 3 lojas",
    "origem": "banco",
    "fonte": {"banco": "erp_varejo", "engine": "SQL Server 16", "conector": "Archeo MCP Creator da CD2"},
    "geradoEm": "2026-11-08T09:30:00-03:00",
    "modo": "snapshot",
    "veredito": {"titulo": "Vendeu mais, com margem menor", "texto": "A venda subiu 4,8%."},
    "metaSecao": "kpis",
    "secoes": [
        {"id": "kpis", "tipo": "kpis", "titulo": "Totalizadores", "campoComparavel": "comparavel",
         "cards": [{"campo": "venda_liquida", "anterior": "venda_liquida_ant", "rotulo": "Venda líquida",
                    "formato": "moeda", "melhor": "alta"}],
         "dados": [{"venda_liquida": 51159.2, "venda_liquida_ant": 48800.0, "comparavel": 1,
                    "periodo_ini": "2026-10-01", "periodo_fim": "2026-10-31",
                    "anterior_ini": "2026-09-01", "anterior_fim": "2026-09-30"}]},
        {"id": "deptos", "tipo": "barras", "titulo": "Departamentos", "formato": "moeda",
         "dados": [{"rotulo": "Açougue", "valor": 5597.26}]},
    ],
}
CONFIG_ARQUIVO = {**CONFIG_BANCO, "origem": "arquivo", "fonte": {"nome": "vendas-outubro.csv"}}


def construir(cfg, bruto=None):
    with tempfile.TemporaryDirectory() as tmp:
        entrada, saida = Path(tmp) / "c.json", Path(tmp) / "p.html"
        entrada.write_text(bruto if bruto is not None else json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        res = subprocess.run([sys.executable, str(BUILD), str(entrada), str(saida)], capture_output=True, text=True)
        return res, saida.read_text(encoding="utf-8") if saida.exists() else ""


def sem_origem(cfg):
    out = copy.deepcopy(cfg)
    del out["origem"]
    return out


def descricao(skill):
    texto = (CORE / skill / "SKILL.md").read_text(encoding="utf-8")
    return re.search(r"^description:\s*(.+)$", texto, re.M).group(1)


class Painel(unittest.TestCase):
    def test_painel_exige_origem(self):
        res, _ = construir(sem_origem(CONFIG_ARQUIVO))
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("origem", res.stdout)
        res, _ = construir({**CONFIG_ARQUIVO, "origem": "nuvem"})
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("origem", res.stdout)

    def test_painel_snapshot_com_marca(self):
        res, html = construir(CONFIG_BANCO)
        self.assertEqual(res.returncode, 0, res.stdout)
        for marca in ("__FONT_FACE__", "__TOKENS_CSS__", "__LOGO__", "__FOOTER__", "__DASH_CONFIG__", "__DASH_TITLE__"):
            self.assertNotIn(marca, html)
        self.assertIn("--brand: #0000ff", html)
        self.assertIn("font/woff2;base64", html)
        self.assertIn('alt="CD2 Tech"', html)
        self.assertIn("cd2-assinatura", html)
        self.assertIn("08/11/2026", html)
        self.assertIn("A CD2 Tech não tem nenhuma responsabilidade", html)
        self.assertNotIn("LIVE-START", html)
        self.assertNotIn("ARCHEO", html)

    def test_selo_do_arquivo_nunca_diz_prova_fechada(self):
        res, html = construir(CONFIG_ARQUIVO)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("o arquivo informado", html)
        self.assertNotIn("os dados do banco conectado", html)
        self.assertNotIn("Prova fechada", html)
        self.assertNotIn("Consultas somente leitura", html)
        self.assertIn("Conferido só contra o arquivo", html)
        banco = construir(CONFIG_BANCO)[1]
        self.assertIn("os dados do banco conectado", banco)
        self.assertNotIn("Conferido só contra o arquivo", banco)

    def test_digitado_tem_o_mesmo_selo_do_relatorio(self):
        cfg = {**CONFIG_ARQUIVO, "origem": "digitado", "fonte": {"nome": "números informados na conversa"}}
        res, html = construir(cfg)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("Conferido só contra o arquivo", html)
        self.assertNotIn("Prova fechada", html)

    def test_painel_sem_conexao_so_snapshot(self):
        for origem in ("arquivo", "digitado"):
            live = {**CONFIG_ARQUIVO, "origem": origem, "modo": "live", "live": {"server": "s", "tool": "t"}}
            live.pop("veredito")
            live["secoes"] = [dict(s, sql="SELECT 1") for s in live["secoes"]]
            for s in live["secoes"]:
                s.pop("dados")
            res, _ = construir(live)
            self.assertEqual(res.returncode, 1, res.stdout)
            self.assertIn("conexão", res.stdout)

    def test_ao_vivo_com_banco_recusa_veredito(self):
        live = {**CONFIG_BANCO, "modo": "live", "live": {"server": "s", "tool": "t"}}
        live["secoes"] = [dict({k: v for k, v in s.items() if k != "dados"}, sql="SELECT 1") for s in live["secoes"]]
        res, _ = construir(live)
        self.assertEqual(res.returncode, 1)
        self.assertIn("veredito", res.stdout)
        live.pop("veredito")
        res, html = construir(live)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("LIVE-START", html)

    def test_fonte_do_arquivo_exige_nome(self):
        res, _ = construir({**CONFIG_ARQUIVO, "fonte": {"banco": "x"}})
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("fonte.nome", res.stdout)

    def test_dado_nao_expande_marca_nem_fecha_script(self):
        cfg = copy.deepcopy(CONFIG_ARQUIVO)
        cfg["rede"] = "__LOGO__"
        cfg["secoes"][1]["dados"][0]["rotulo"] = "</script><img src=x onerror=alert(1)>"
        cfg["secoes"][1]["dados"].append({"rotulo": "<!--<script>", "valor": 1})
        res, html = construir(cfg)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn('"rede": "__LOGO__"', html)
        self.assertNotIn("</script><img", html)
        self.assertNotIn("<!--<script>", html)
        payload = html.split('id="dash-config">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("<", payload)
        self.assertEqual(json.loads(payload)["secoes"][1]["dados"][1]["rotulo"], "<!--<script>")

    def test_arquivo_entregue_e_documento_completo(self):
        _, html = construir(CONFIG_ARQUIVO)
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn('<html lang="pt-BR">', html)
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn('name="viewport"', html)
        self.assertLess(html.index("<meta charset"), html.index("<title>"))
        self.assertTrue(html.rstrip().endswith("</html>"))

    def test_tipo_errado_no_config_nao_da_traceback(self):
        casos = [
            {**CONFIG_BANCO, "fonte": "erp"},
            {**CONFIG_ARQUIVO, "fonte": ["a.csv"]},
            {**CONFIG_ARQUIVO, "secoes": ["kpis"]},
            {**CONFIG_ARQUIVO, "secoes": {"id": "x"}},
            {**CONFIG_ARQUIVO, "secoes": [dict(CONFIG_ARQUIVO["secoes"][1], formato=["moeda"])]},
            {**CONFIG_ARQUIVO, "secoes": [dict(CONFIG_ARQUIVO["secoes"][1], tipo=["barras"])]},
            {**CONFIG_ARQUIVO, "leitura": ["texto"]},
            {**CONFIG_ARQUIVO, "origem": ["arquivo"]},
            {**CONFIG_ARQUIVO, "titulo": 5},
            {**CONFIG_ARQUIVO, "titulo": ["x"]},
            {**CONFIG_ARQUIVO, "rede": 3},
            {**CONFIG_ARQUIVO, "periodo": ["x"]},
            {**CONFIG_ARQUIVO, "fonte": {"nome": 7}},
            {**CONFIG_ARQUIVO, "fonte": {"nome": ["a.csv"]}},
            {**CONFIG_BANCO, "fonte": {"banco": 1, "engine": "e", "conector": "c"}},
        ]
        for cfg in casos:
            res, _ = construir(cfg)
            self.assertEqual(res.returncode, 1, (cfg, res.stdout, res.stderr))
            self.assertNotIn("Traceback", res.stderr)
            self.assertIn("Config invalido", res.stdout)
        res, _ = construir(None, bruto="[1, 2]")
        self.assertEqual(res.returncode, 1)
        self.assertNotIn("Traceback", res.stderr)

    def test_outro_mcp_nao_afirma_somente_leitura(self):
        cfg = {**CONFIG_BANCO, "origem": "outro-mcp"}
        _, html = construir(cfg)
        self.assertNotIn("Consultas somente leitura", html)
        self.assertIn("Fonte: erp_varejo", html)

    def test_preview_usa_pasta_propria_e_valida_argumentos(self):
        codigo = PREVIEW.read_text(encoding="utf-8")
        self.assertNotIn("glob(", codigo)
        self.assertNotIn("getcwd", codigo)
        self.assertIn("TemporaryDirectory", codigo)
        self.assertIn('encoding="utf-8"', codigo)

    def test_preview_sem_playwright_avisa(self):
        codigo = (
            "import runpy, sys\n"
            "sys.modules['playwright'] = None\n"
            "sys.modules['playwright.async_api'] = None\n"
            f"sys.argv = ['preview_dashboard.py', 'nao-importa.html']\n"
            f"runpy.run_path({str(PREVIEW)!r}, run_name='__main__')\n"
        )
        res = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
        saida = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, saida)
        self.assertNotIn("Traceback", saida)
        self.assertIn("Playwright", saida)
        self.assertIn("não foi conferida", saida)

    def test_skill_sem_referencia_para_fora(self):
        for md in (CORE / "painel-varejo").rglob("*.md"):
            self.assertNotIn("../", md.read_text(encoding="utf-8"), md)

    def test_descricao_separa_painel_de_relatorio(self):
        texto = descricao("painel-varejo")
        self.assertIn("arquivo", texto)
        self.assertRegex(texto, r"relatorio-\*|relatorio-vendas")
        self.assertIn("painel de vendas", texto)

    def test_modos_ao_vivo_e_agendado_so_com_conexao(self):
        skill = (CORE / "painel-varejo/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Sem conexão", skill)
        self.assertIn("só o modo snapshot", skill)
        modos = (CORE / "painel-varejo/references/modos-atualizacao.md").read_text(encoding="utf-8")
        self.assertIn("exigem conexão", modos)


class Ficha(unittest.TestCase):
    def setUp(self):
        self.skill = (CORE / "ficha-archeo-mcp/SKILL.md").read_text(encoding="utf-8")

    def test_ficha_sem_conexao_marca_nao_validada(self):
        self.assertIn("## Sem conexão", self.skill)
        secao = self.skill.split("## Sem conexão", 1)[1].split("\n## ", 1)[0]
        self.assertIn("não validada", secao)
        self.assertIn("validação precisa do banco", secao)
        self.assertRegex(secao.lower(), r"nunca[^\n]*pronta para (cadastrar|registrar)|não[^\n]*(oferece|apresenta)[^\n]*pronta", )
        self.assertIn("**Validação:** não validada", self.skill)
        self.assertIn("não validada (<motivo", self.skill)
        self.assertIn("esqueleto da ficha", secao)
        self.assertIn("nem coluna", secao)
        self.assertIn("https://archeo.cd2.com.br/?utm_source={{UTM_SOURCE}}&utm_medium=skill&utm_campaign=ficha-archeo-mcp", self.skill)

    def test_ficha_nao_exige_conector(self):
        for texto in (self.skill, descricao("ficha-archeo-mcp")):
            self.assertNotIn("Requisito", texto)
            self.assertNotIn("banco conectado ao Archeo", texto)
        self.assertNotRegex(descricao("ficha-archeo-mcp"), r"Sempre explora e valida")

    def test_ficha_usa_o_nome_do_produto(self):
        self.assertIn("Archeo MCP Creator da CD2", self.skill)
        self.assertNotRegex(self.skill, r"conector Archeo\b")
        self.assertNotIn(NOMES_ANTIGOS[3], self.skill)

    def test_ficha_sem_referencia_para_fora(self):
        for md in (CORE / "ficha-archeo-mcp").rglob("*.md"):
            self.assertNotIn("../", md.read_text(encoding="utf-8"), md)

    def test_exemplo_de_ficha_marca_a_validacao(self):
        exemplo = (CORE / "ficha-archeo-mcp/references/exemplo-ficha.md").read_text(encoding="utf-8")
        self.assertIn("**Validação:**", exemplo)


class Textos(unittest.TestCase):
    def test_sem_travessao_nem_nomes_antigos(self):
        proibidos = ("—", "–") + NOMES_ANTIGOS
        for skill in ("painel-varejo", "ficha-archeo-mcp"):
            for arq in (CORE / skill).rglob("*"):
                if arq.is_file() and arq.suffix in (".md", ".py", ".html", ".json"):
                    texto = arq.read_text(encoding="utf-8")
                    for p in proibidos:
                        self.assertNotIn(p, texto, f"{arq}: {p}")


if __name__ == "__main__":
    unittest.main()
