import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core" / "cd2-varejo" / "shared" / "scripts"))

import brand  # noqa: E402

REGRA = "Decreto 12.712/2025"
DATA = "07/11/2026"


class BrandTest(unittest.TestCase):
    def test_footer_html_has_logo_and_disclaimer(self):
        html = brand.footer_html(REGRA, DATA)
        self.assertIn("<svg", html)
        self.assertNotIn("<?xml", html)
        self.assertIn('role="img"', html)
        self.assertIn('aria-label="CD2 Tech"', html)
        self.assertIn("não tem nenhuma responsabilidade", html)
        self.assertIn("Decreto 12.712/2025", html)
        self.assertIn("cd2-assinatura", html)

    def test_logo_dark_uses_white_version(self):
        self.assertNotEqual(brand.logo_svg("light"), brand.logo_svg("dark"))
        self.assertIn("#ffffff", brand.logo_svg("dark").lower())

    def test_footer_text_uses_literal_name(self):
        self.assertTrue(brand.footer_text(REGRA, DATA).startswith("CD2 Tech\n"))

    def test_link_adds_utm(self):
        utm = "?utm_source={{UTM_SOURCE}}&utm_medium=skill&utm_campaign=custo-vrva"
        self.assertTrue(brand.link("https://cd2.com.br", "custo-vrva").endswith(utm))
        self.assertEqual(
            brand.link("https://calc-vrva.cd2.com.br/", "custo-vrva"),
            "https://calc-vrva.cd2.com.br/" + utm,
        )
        self.assertIn(
            "?a=1&utm_source={{UTM_SOURCE}}", brand.link("https://x.com/?a=1", "c")
        )

    def test_whatsapp_message_is_exact_template(self):
        url = brand.whatsapp_link("Fim da escala 6x1", "Claude")
        prefix = "https://wa.me/5519982355172?text="
        self.assertTrue(url.startswith(prefix))
        self.assertEqual(
            urllib.parse.unquote(url[len(prefix):]),
            "Oi, vim pela skill Fim da escala 6x1 no Claude e quero falar sobre uso na minha empresa.",
        )
        url = brand.whatsapp_link("VR/VA", "Claude")
        self.assertEqual(
            urllib.parse.unquote(url[len(prefix):]),
            "Oi, vim pela skill VR/VA no Claude e quero falar sobre uso na minha empresa.",
        )

    def test_esc_and_csv_cell(self):
        self.assertEqual(brand.esc("<script>"), "&lt;script&gt;")
        self.assertEqual(brand.csv_cell("a;b"), '"a;b"')
        self.assertEqual(brand.csv_cell('a"b'), '"a""b"')
        self.assertEqual(brand.csv_cell("a,b"), '"a,b"')
        self.assertEqual(brand.csv_cell("a\nb"), '"a\nb"')
        self.assertEqual(brand.csv_cell("ab"), "ab")

    def test_format_brl(self):
        self.assertEqual(brand.format_brl(1576.6667), "R$ 1.576,67")
        self.assertEqual(brand.format_brl(0), "R$ 0,00")
        self.assertEqual(brand.format_brl(1234567.5), "R$ 1.234.567,50")

    def test_format_brl_compact(self):
        for value, expected in [
            (950, "R$ 950"),
            (10540, "R$ 10,5 mil"),
            (10524.5, "R$ 10,5 mil"),
            (21760, "R$ 21,8 mil"),
            (1250000, "R$ 1,3 mi"),
            (0, "R$ 0"),
        ]:
            self.assertEqual(brand.format_brl_compact(value), expected, value)

    def test_format_date_br(self):
        self.assertEqual(brand.format_date_br("2026-12-16"), "16/12/2026")

    def test_no_dash_in_disclaimer(self):
        text = brand.disclaimer(REGRA, DATA)
        self.assertNotIn("—", text)
        self.assertNotIn("–", text)
        self.assertIn("nossa leitura de Decreto 12.712/2025 em 07/11/2026,", text)

    def test_tokens_and_css(self):
        self.assertEqual(brand.TOKENS["blue-retail"], "#0000ff")
        self.assertEqual(brand.TOKENS["yellow-like"], "#dbff2a")
        css = brand.base_css()
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("Manrope", css)
        self.assertIn("1200px", css)
        self.assertNotIn("—", css)
        self.assertNotIn("–", css)

    def test_brand_sources_have_no_dash(self):
        src = (ROOT / "core/cd2-varejo/shared/scripts/brand.py").read_text()
        self.assertNotIn("—", src)
        self.assertNotIn("–", src)


if __name__ == "__main__":
    unittest.main()
