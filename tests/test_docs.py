"""Testes do README, do site do GitHub Pages e dos guias do repositório."""
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
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
            "avaliação",
            "/plugin marketplace add cd2tec/cd2-skills",
            "/plugin install cd2-varejo@cd2-skills",
            "codex plugin marketplace add cd2tec/cd2-skills",
        ):
            self.assertIn(needle, text)

    def test_readme_platform_details(self):
        text = read("README.md")
        for needle in (
            "COMMERCIAL.md",
            "90 dias",
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
            self.assertIn(f"releases/latest/download/cd2-varejo-{pkg}.zip", text)

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
            "Skills de IA para o varejo, de graça para avaliar",
            "Como a skill conversa com você",
            "Conecte seu sistema",
            'role="tablist"',
            "CC BY-NC-ND 4.0",
            "COMMERCIAL.md",
            "90 dias",
            "CD2 Escala 6x1",
            "CD2 VR/VA: quanto custa",
            "/plugin marketplace add cd2tec/cd2-skills",
            "codex plugin marketplace add cd2tec/cd2-skills",
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

    def test_no_dash_no_gabriel(self):
        for rel in self.FILES:
            text = read(rel)
            self.assertNotIn(EM, text, rel)
            self.assertNotIn(EN, text, rel)
            self.assertNotIn("Gabriel", text, rel)
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
        for rel in ("README.md", "docs/index.html", "plugins/codex/cd2-varejo/README.md"):
            text = read(rel)
            self.assertIn("codex plugin marketplace add cd2tec/cd2-skills", text, rel)
            self.assertIn("codex plugin add cd2-varejo@cd2-skills", text, rel)

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
            "Sincronia com os sites",
            "utm_source",
            "plugin.core.json",
            "CHANGELOG.md",
        ):
            self.assertIn(needle, text)

    def test_claude_md_points_to_agents(self):
        self.assertIn("AGENTS.md", read("CLAUDE.md"))

    def test_changelog_starts_at_first_version(self):
        text = read("CHANGELOG.md")
        self.assertIn("## 0.1.0", text)
        self.assertIn("2026-11-07", text)


if __name__ == "__main__":
    unittest.main()
