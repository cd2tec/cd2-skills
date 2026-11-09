"""Testes do README, do site do GitHub Pages e dos guias do repositório."""
import codecs
import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
PERSON = codecs.decode("Tnoevry", "rot13")  # nome próprio que nenhum arquivo pode citar
DOCS = ROOT / "docs"
EM, EN = chr(0x2014), chr(0x2013)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
WA_README = "Oi, vim pelo GitHub das skills da CD2 e quero falar sobre uso na minha empresa."
WA_SITE = "Oi, vim pelo site das skills da CD2 e quero falar sobre uso na minha empresa."
# Hosts aceitos em src/href absolutos do site. O resto tem de ser relativo.
SITE_HOSTS = ("cd2.com.br", "wa.me", "github.com")
UTM_HOSTS = ("cd2.com.br",)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def host_ok(host, allowed):
    return any(host == h or host.endswith("." + h) for h in allowed)


def urls_in(text):
    return re.findall(r"https?://[^\s)\"'<>\]]+", text)


def without_generated_block(text):
    return re.sub(r"<!-- skills:start -->.*?<!-- skills:end -->", "", text, flags=re.S)


class ReadmeTest(unittest.TestCase):
    def test_readme_sections(self):
        text = read("README.md")
        for needle in (
            "Claude Code",
            "Claude Cowork",
            "Codex",
            "ChatGPT Work",
            "DeepSeek Harness",
            "GPT Store",
            "CC BY-NC-ND 4.0",
            "Teste grátis na sua empresa",
            "/plugin marketplace add cd2tec/super",
            "/plugin install cd2-super@super",
            "codex plugin marketplace add cd2tec/super",
        ):
            self.assertIn(needle, text)

    def test_readme_platform_details(self):
        text = read("README.md")
        for needle in (
            "COMMERCIAL.md",
            "sem prazo",
            "CD2 Escala 6x1",
            "CD2 VR/VA: quanto custa",
            "gpts/README.md",
            "developer preview",
            "planos de empresa",
            "SIL Open Font License",
            "```mermaid",
            "<!-- skills:start -->",
            "<!-- skills:end -->",
        ):
            self.assertIn(needle, text)
        for pkg in ("claude", "codex", "dsh", "gpts"):
            self.assertIn(f"releases/latest/download/cd2-super-{pkg}.zip", text)

    def test_readme_contact_and_utm(self):
        text = read("README.md")
        wa = [u for u in urls_in(text) if urlparse(u).netloc == "wa.me"]
        self.assertTrue(wa)
        for url in wa:
            self.assertEqual(urlparse(url).path, "/5519982355172")
            query = parse_qs(urlparse(url).query)
            if "text" in query:
                self.assertEqual(query["text"][0], WA_README)
        self.assertTrue(any("text" in parse_qs(urlparse(u).query) for u in wa))
        cd2 = [u for u in urls_in(text) if host_ok(urlparse(u).netloc, UTM_HOSTS)]
        self.assertTrue(any(urlparse(u).netloc == "archeo.cd2.com.br" for u in cd2))
        for url in cd2:
            self.assertIn("utm_source=github&utm_medium=skill&utm_campaign=", url, url)


    def test_readme_explica_com_e_sem_conexao(self):
        text = read("README.md")
        for needle in (
            "## Relatórios e painel",
            "Com conexão",
            "Sem conexão",
            "Conferido só contra o arquivo",
            "Prova fechada",
            "Para exportar",
            "relatorio-vendas",
            "painel-varejo",
            "ficha-archeo-mcp",
            "Archeo MCP Creator da CD2",
        ):
            self.assertIn(needle, text)
        # A conexão se defende só com o que as skills fazem: lê o banco todo, confere no banco, só lê.
        for needle in ("só lê", "SELECT", "Online"):
            self.assertIn(needle, text)
        self.assertNotRegex(text, r"(?i)dados? (nunca )?sa[ei]m? da (sua )?empresa|nada sai da")
        # Relatório não é painel: o painel é uma skill só.
        self.assertRegex(text, r"(?s)relat[óo]rios?.{0,200}painel")

    def test_gpt_so_nas_calculadoras(self):
        skills = json.loads(read("skills.json"))
        com_gpt = {s["name"] for s in skills if s.get("gpt")}
        self.assertEqual(com_gpt, {"fim-escala-6x1", "custo-vrva"})
        self.assertEqual(sorted(p.name for p in (ROOT / "gpts").iterdir() if p.is_dir()), sorted(com_gpt))
        for rel in ("README.md", "docs/index.html"):
            text = read(rel)
            self.assertIn("só para as duas calculadoras", text, rel)
            self.assertNotIn("um GPT para cada skill", text, rel)

    def test_teste_sem_prazo_nao_fala_em_periodo(self):
        for rel in ("README.md", "docs/index.html", "AGENTS.md"):
            text = read(rel)
            self.assertNotIn("Nesse período", text, rel)
            self.assertNotIn("está avaliando", text, rel)
        self.assertIn("Nesse uso de teste", read("README.md"))
        self.assertIn("Nesse uso de teste", read("docs/index.html"))
        self.assertIn("está testando", read("AGENTS.md"))


class ReadmeExampleTest(unittest.TestCase):
    """Os números dos exemplos de conversa saem das contas dos scripts, com os dados ao lado."""

    def load(self, skill):
        import importlib.util
        import sys
        shared = str(ROOT / "core" / "cd2-super" / "shared" / "scripts")
        if shared not in sys.path:
            sys.path.insert(0, shared)
        name = f"readme_example_{skill.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(name, ROOT / "core" / "cd2-super" / "skills" / skill / "scripts" / "calc.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_6x1_example_inputs_give_readme_numbers(self):
        calc = self.load("fim-escala-6x1")
        import brand
        data = {
            "today": "2026-11-07",
            "store": {"days_open_per_week": 7, "hours_open_per_day": 13},
            "sectors": [
                {"name": "Caixa", "headcount": 14, "avg_monthly_salary": 1900, "min_simultaneous_staff": 5},
                {"name": "Açougue", "headcount": 6, "avg_monthly_salary": 2600},
                {"name": "Padaria", "headcount": 5, "avg_monthly_salary": 2200},
            ],
        }
        self.assertEqual(calc.validate(data), [])
        out = calc.run(data)["scenarios"]
        without = out["without_agreement"]["result"]
        with_agreement = out["with_agreement"]["result"]
        text = read("README.md")
        self.assertIn(f"você precisa de {without['min_additional']} a {without['max_additional']} pessoas a mais", text)
        self.assertIn(f"de {brand.format_brl(without['min_monthly_cost'])} a {brand.format_brl(without['max_monthly_cost'])} por mês", text)
        self.assertEqual([s["status"] for s in without["sectors"]], ["red", "red", "red"])
        self.assertIn(f"cai para {with_agreement['min_additional']} a {with_agreement['max_additional']} pessoas", text)
        for needle in ("7 dias abertos, 13h por dia", "Caixa: 14 pessoas, R$ 1.900,00", "5 postos",
                       "Açougue: 6 pessoas, R$ 2.600,00", "Padaria: 5 pessoas, R$ 2.200,00", "encargos de 70%"):
            self.assertIn(needle, text)

    def test_relatorio_example_abc_numbers(self):
        # Mercearia de exemplo do README e do site: seis produtos, cortes de 80% (A) e 95% (B).
        values = [5000, 3000, 1000, 500, 300, 200]
        total = sum(values)
        acc, classes = 0, {"A": [], "B": [], "C": []}
        for v in values:
            acc += v
            classes["A" if acc / total <= 0.80 else "B" if acc / total <= 0.95 else "C"].append(v)
        self.assertEqual({k: len(v) for k, v in classes.items()}, {"A": 2, "B": 2, "C": 2})
        self.assertEqual(sum(classes["A"]), 8000)
        self.assertEqual(round(100 * sum(classes["B"]) / total), 15)
        self.assertEqual(round(100 * sum(classes["C"]) / total), 5)
        for rel in ("README.md", "docs/index.html"):
            text = read(rel)
            self.assertIn("Dois produtos fazem 80% da venda: R$ 8.000,00 de R$ 10.000,00", text, rel)
            self.assertIn("mais dois, com 15%", text, rel)
            self.assertIn("R$ 5.000,00, R$ 3.000,00, R$ 1.000,00, R$ 500,00, R$ 300,00 e R$ 200,00", text, rel)

    def test_vrva_example_annual_with_cents(self):
        calc = self.load("custo-vrva")
        import brand
        data = {
            "today": "2026-11-07",
            "brands": [
                {"name": "Alelo", "sales": 18000, "rate": 6.5, "days": 30},
                {"name": "Pluxee (Sodexo)", "sales": 12000, "rate": 5.9, "days": 30},
                {"name": "Ticket", "sales": 10000, "rate": 6.0, "days": 32},
                {"name": "VR", "sales": 8000, "rate": 4.5, "days": 25},
            ],
            "money_cost_month_percent": 2,
        }
        result = calc.run(data)["result"]
        for rel in ("README.md", "docs/index.html"):
            text = read(rel)
            self.assertIn(f"{brand.format_brl(result['total_month'])} por mês acima do permitido, "
                          f"ou {brand.format_brl(result['total_year'])} por ano", text, rel)


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.html = read("docs/index.html")

    def test_site_is_self_contained(self):
        for needle in ("<title>", "prefers-color-scheme", "blue-retail"):
            self.assertIn(needle, self.html)
        for attr, url in re.findall(r'\b(src|href)="([^"]*)"', self.html):
            parsed = urlparse(url)
            if parsed.scheme:
                self.assertEqual(parsed.scheme, "https", url)
                self.assertTrue(host_ok(parsed.netloc, SITE_HOSTS), url)
            else:
                self.assertFalse(url.startswith("//"), url)

    def test_site_relative_assets_exist(self):
        for attr, url in re.findall(r'\b(src|href)="([^"]*)"', self.html):
            url = url.replace("&amp;", "&")
            parsed = urlparse(url)
            if parsed.scheme or not parsed.path:
                continue
            self.assertTrue((DOCS / unquote(parsed.path)).exists(), url)
        for url in re.findall(r'url\("?([^")]+)"?\)', self.html):
            if not url.startswith("data:"):
                self.assertTrue((DOCS / url).exists(), url)
        for name in ("cd2tech-horizontal.svg", "cd2tech-horizontal-white.svg", "simbolo.svg", "icon-512.png"):
            self.assertIn(f"assets/{name}", self.html)
        self.assertTrue((DOCS / "assets" / "fonts" / "OFL.txt").is_file())
        self.assertTrue((DOCS / ".nojekyll").is_file())

    def test_site_sections_and_themes(self):
        for needle in (
            "Skills de IA para o varejo, de graça para testar",
            "Como a skill conversa com você",
            "Conecte seu sistema",
            'role="tablist"',
            "CC BY-NC-ND 4.0",
            "COMMERCIAL.md",
            "Sem prazo",
            "CD2 Escala 6x1",
            "CD2 VR/VA: quanto custa",
            "/plugin marketplace add cd2tec/super",
            "codex plugin marketplace add cd2tec/super",
            "SIL Open Font License",
            ':root[data-theme="dark"]',
            ":focus-visible",
        ):
            self.assertIn(needle, self.html)
        # Sem JS as abas viram lista: nenhum painel nasce escondido no HTML.
        self.assertNotRegex(self.html, r'role="tabpanel"[^>]*\bhidden\b')
        # Marca plana: sem sombra e sem degradê.
        self.assertNotIn("box-shadow", self.html.replace("box-shadow: none", ""))
        self.assertNotIn("gradient", self.html)

    def test_site_tem_secao_de_relatorios(self):
        html = self.html
        self.assertIn('id="relatorios"', html)
        self.assertIn('href="#relatorios"', html)
        section = html.split('id="relatorios"', 1)[1].split("</section>", 1)[0]
        for skill in ("relatorio-vendas", "relatorio-estoque", "relatorio-compras", "relatorio-precos",
                      "relatorio-perdas", "relatorio-financeiro", "relatorio-fiscal", "relatorio-contabil",
                      "painel-varejo", "ficha-archeo-mcp"):
            self.assertIn(skill, section, skill)
        for needle in ("Com conexão", "Sem conexão", "Conferido só contra o arquivo", "Prova fechada",
                       "só lê", "SELECT", "Online", "Archeo MCP Creator da CD2"):
            self.assertIn(needle, section, needle)
        self.assertRegex(section, r'class="chat"')
        # O hero e os fatos falam das doze skills, não de duas.
        self.assertNotIn('<span class="stat">2</span>', html)
        self.assertIn('<span class="stat">12</span>', html)
        self.assertNotRegex(html, r"(?i)dados? (nunca )?sa[ei]m? da (sua )?empresa|nada sai da")
        # Os cards gerados mostram as doze e não fingem calculadora nos relatórios.
        block = html.split("<!-- skills:start -->")[1].split("<!-- skills:end -->")[0]
        self.assertEqual(block.count('class="skill-card"'), 12)
        self.assertEqual(block.count("Abrir a calculadora gratuita"), 2)

    def test_site_contact_and_utm(self):
        urls = [u.replace("&amp;", "&") for u in urls_in(self.html)]
        wa = [u for u in urls if urlparse(u).netloc == "wa.me"]
        self.assertTrue(wa)
        for url in wa:
            self.assertEqual(parse_qs(urlparse(url).query)["text"][0], WA_SITE)
        cd2 = [u for u in urls if host_ok(urlparse(u).netloc, UTM_HOSTS)]
        self.assertTrue(any(urlparse(u).netloc == "archeo.cd2.com.br" for u in cd2))
        for url in cd2:
            self.assertIn("utm_source=site-skills&utm_medium=skill&utm_campaign=", url, url)

    def test_root_index_redirects_to_docs(self):
        text = read("index.html")
        self.assertIn('http-equiv="refresh"', text)
        self.assertIn('url=docs/', text)


class CopyRulesTest(unittest.TestCase):
    FILES = ("README.md", "docs/index.html", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "index.html")

    def test_no_dash_no_personal_name(self):
        for rel in self.FILES:
            text = read(rel)
            self.assertNotIn(EM, text, rel)
            self.assertNotIn(EN, text, rel)
            self.assertNotIn(PERSON, text, rel)
            self.assertIsNone(EMOJI.search(text), rel)

    def test_generated_block_untouched_by_hand(self):
        # Os textos à mão ficam fora do bloco gerado; dentro dele só o que o sync escreve.
        for rel in ("README.md", "docs/index.html"):
            text = read(rel)
            self.assertEqual(text.count("<!-- skills:start -->"), 1, rel)
            self.assertEqual(text.count("<!-- skills:end -->"), 1, rel)
            self.assertTrue(without_generated_block(text).strip(), rel)


class LaunchTruthTest(unittest.TestCase):
    """O que o README e o site prometem tem de ser verdade no dia do lançamento."""

    DOCS = ("README.md", "docs/index.html")

    NEAR = re.compile(r"GPT Store.{0,160}?em breve|em breve.{0,160}?GPT Store", re.S | re.I)
    GPT_NAMES = ("CD2 Escala 6x1", "CD2 VR/VA: quanto custa")
    FORBIDDEN = ("publicado pela cd2", "publicados pela cd2", "procure na gpt store")

    def check_gpt_store_text(self, text, rel):
        self.assertRegex(text, self.NEAR, rel)
        for name in self.GPT_NAMES:
            self.assertIn(name, text, rel)
        lowered = text.lower()
        for phrase in self.FORBIDDEN:
            self.assertNotIn(phrase, lowered, rel)

    def test_gpt_store_is_coming_soon(self):
        for rel in self.DOCS:
            self.check_gpt_store_text(read(rel), rel)
        self.assertNotIn("6 plataformas", read("README.md"))
        self.assertNotIn('<span class="stat">6</span>', read("docs/index.html"))

    def test_gpt_store_guard_is_live(self):
        # Cada guarda tem de falhar quando a frase proibida volta ou um nome de GPT some.
        for rel in self.DOCS:
            text = read(rel)
            broken = [
                text + "\nCada skill virou um GPT, publicado pela CD2 Tech.",
                text + "\nProcure na GPT Store por CD2 Escala 6x1.",
                text.replace("CD2 Escala 6x1", "CD2 Escala"),
                text.replace("CD2 VR/VA: quanto custa", "CD2 VR/VA"),
                text.replace("em breve", "agora").replace("Em breve", "Agora"),
            ]
            for variant in broken:
                with self.assertRaises(AssertionError, msg=rel):
                    self.check_gpt_store_text(variant, rel)

    def test_codex_command_agrees_everywhere(self):
        for rel in ("README.md", "docs/index.html", "plugins/codex/cd2-super/README.md"):
            text = read(rel)
            self.assertIn("codex plugin marketplace add cd2tec/super", text, rel)
            self.assertIn("codex plugin add cd2-super@super", text, rel)

    def test_cowork_owner_wording_agrees(self):
        for rel in self.DOCS:
            self.assertIn("Owner ou Primary Owner", read(rel), rel)

    def test_free_use_includes_sharing_unchanged(self):
        for rel in self.DOCS:
            self.assertIn("compartilhar sem alterações", read(rel), rel)

    def test_every_img_has_alt(self):
        for rel in self.DOCS:
            for tag in re.findall(r"<img\b[^>]*>", read(rel)):
                self.assertRegex(tag, r'\balt="[^"]+"', f"{rel}: {tag}")


class SiteA11yTest(unittest.TestCase):
    def setUp(self):
        self.html = read("docs/index.html")

    def test_focus_ring_visible_on_blue_blocks(self):
        # Sobre blue-retail e azuis escuros o anel blue-tech some: tem de virar yellow-like.
        for selector in (r"\.on-brand", r"\.block--brand", r"\.chat"):
            rule = re.compile(selector + r"[^{]*\{[^}]*--focus-ring:\s*var\(--yellow-like\)")
            self.assertRegex(self.html, rule, selector)

    def test_tab_panels_hidden_before_first_paint(self):
        # O script do <head> põe a classe js; o CSS esconde os painéis fora do ar antes do primeiro quadro.
        head = self.html.split("</head>")[0]
        self.assertIn('classList.add("js")', head)
        self.assertRegex(head, r"\.js \.panel:not\(\.is-on\)\s*\{[^}]*display:\s*none")
        panels = re.findall(r'<div class="panel[^"]*" role="tabpanel"', self.html)
        self.assertEqual(len(panels), 6)
        self.assertIn("is-on", panels[0])
        self.assertTrue(all("is-on" not in p for p in panels[1:]))


class GuidesTest(unittest.TestCase):
    def test_agents_md_has_new_skill_checklist(self):
        text = read("AGENTS.md")
        for needle in (
            "skills.json",
            "sync_plugins.py",
            "legal-params.json",
            "assumptions.json",
            "core/",
            "flat-skills",
            "Somar uma calculadora nova",
            "Somar um relatório novo",
            "kits/",
            "Para exportar",
            "harnesses.json",
            "Sincronia com os sites",
            "utm_source",
            "plugin.core.json",
            "CHANGELOG.md",
        ):
            self.assertIn(needle, text)

    def test_agents_md_descreve_tipos_e_kits(self):
        text = read("AGENTS.md")
        for needle in ("`tipo`", "`gpt`", "`kits`", "calculadora", "relatorio", "painel", "ficha",
                       "kits/sql", "kits/dados", "kits/relatorio", "kits/calculadora",
                       "vale só para calculadoras"):
            self.assertIn(needle, text)

    def test_claude_md_points_to_agents(self):
        self.assertIn("AGENTS.md", read("CLAUDE.md"))

    def test_changelog_starts_at_first_version(self):
        text = read("CHANGELOG.md")
        self.assertIn("## 0.1.0", text)
        self.assertIn("2026-11-07", text)

    def test_changelog_0_2_0(self):
        text = read("CHANGELOG.md")
        self.assertLess(text.index("## 0.2.0"), text.index("## 0.1.0"))
        section = text.split("## 0.2.0", 1)[1].split("## 0.1.0", 1)[0]
        for needle in ("relatorio-vendas", "painel-varejo", "ficha-archeo-mcp", "sem conexão", "sem prazo",
                       "nomes novos"):
            self.assertIn(needle, section, needle)


if __name__ == "__main__":
    unittest.main()
