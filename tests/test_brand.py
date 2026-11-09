import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core" / "cd2-super" / "shared" / "scripts"))

import brand  # noqa: E402

EM = chr(0x2014)
EN = chr(0x2013)
REGRA = "Decreto 12.712/2025"
DATA = "07/11/2026"


class BrandTest(unittest.TestCase):
    def test_footer_calculadora_nao_mudou(self):
        # O rodapé das calculadoras fica byte a byte como antes dos relatórios.
        html = brand.footer_html("X", "01/01/2026")
        self.assertTrue(html.startswith('<footer class="cd2-assinatura"><div class="cd2-assinatura-logo"><svg '))
        self.assertTrue(
            html.endswith(
                '</div><p class="cd2-assinatura-aviso">Estas contas e informações são apenas gerenciais, '
                "uma referência. Elas usam os números informados e a nossa leitura da regra em 01/01/2026 (X), "
                "que pode mudar. A CD2 Tech não tem nenhuma responsabilidade sobre estes resultados nem sobre "
                "decisões tomadas com base neles. Confira com seu contador e seu advogado antes de agir."
                "</p></footer>"
            )
        )
        self.assertEqual(html.count("<svg"), 2)

    def test_disclaimer_dados_texto_fixo(self):
        base = (
            "Estas contas e informações são apenas gerenciais, uma referência. Elas usam {} em 08/11/2026. "
            "A CD2 Tech não tem nenhuma responsabilidade sobre estes resultados nem sobre decisões tomadas "
            "com base neles. Confira com seu contador e seu advogado antes de agir."
        )
        for origem, fonte in (
            ("banco", "os dados do banco conectado"),
            ("outro-mcp", "os dados do banco conectado"),
            ("arquivo", "o arquivo informado"),
            ("digitado", "os dados informados"),
        ):
            self.assertEqual(brand.disclaimer_dados(origem, "08/11/2026"), base.format(fonte))
        self.assertEqual(brand.ORIGENS, ("banco", "outro-mcp", "arquivo", "digitado"))

    def test_footer_dados_html_e_text(self):
        html = brand.footer_dados_html("arquivo", "08/11/2026")
        self.assertIn("cd2-logo-claro", html)
        self.assertIn("o arquivo informado", html)
        self.assertTrue(brand.footer_dados_text("digitado", "08/11/2026").startswith("CD2 Tech\n"))
        with self.assertRaises(ValueError):
            brand.footer_dados_html("nada", "08/11/2026")

    def test_formatos_de_relatorio(self):
        self.assertEqual(brand.moeda(1.005), "R$ 1,01")
        self.assertEqual(brand.moeda(-0.001), "R$ 0,00")
        self.assertEqual(brand.numero(5130), "5.130")
        self.assertEqual(brand.pct(79.75), "79,8%")
        self.assertEqual(brand.moeda_compacta(1642310.4), "R$ 1,6 mi")
        self.assertEqual(brand.data_br("2026-11-08T09:30:00"), "08/11/2026")
        self.assertEqual(brand.formatar(None, "moeda"), brand.SEM_DADO)
        self.assertFalse(brand.e_numero(True))

    def test_tokens_ganharam_chaves_sem_mudar_valores(self):
        for chave in ("blue-experience", "blue-qwerty", "frente-lilas"):
            self.assertIn(chave, brand.TOKENS)
        self.assertEqual(brand.TOKENS["blue-retail"], "#0000ff")
        self.assertIn("--s2: #011e80", brand.tokens_css())

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

    def test_footer_html_auto_has_both_logos(self):
        html = brand.footer_html(REGRA, DATA)
        self.assertEqual(html.count("<svg"), 2)
        self.assertIn("cd2-logo--light", html)
        self.assertIn("cd2-logo--dark", html)

    def test_footer_html_forced_theme_has_single_logo(self):
        dark = brand.footer_html(REGRA, DATA, theme="dark")
        self.assertEqual(dark.count("<svg"), 1)
        self.assertIn("#ffffff", dark.lower())
        self.assertNotIn("cd2-logo--light", dark)
        light = brand.footer_html(REGRA, DATA, theme="light")
        self.assertEqual(light.count("<svg"), 1)
        self.assertNotIn("cd2-logo--dark", light)
        self.assertNotEqual(light, dark)

    def test_css_toggles_logos(self):
        css = brand.base_css()
        self.assertIn(".cd2-logo--dark { display: none; }", css)
        self.assertIn(".cd2-logo--light { display: none; }", css)
        self.assertIn('[data-theme="light"] .cd2-logo--dark', css)
        self.assertIn('[data-theme="dark"] .cd2-logo--light', css)
        dark_media = css.split("prefers-color-scheme: dark", 1)[1]
        self.assertIn(".cd2-logo--dark", dark_media)

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
        self.assertNotIn(EM, text)
        self.assertNotIn(EN, text)
        self.assertEqual(
            text,
            "Estas contas e informações são apenas gerenciais, uma referência. Elas usam os números "
            "informados e a nossa leitura da regra em 07/11/2026 (Decreto 12.712/2025), que pode mudar. "
            "A CD2 Tech não tem nenhuma responsabilidade sobre estes resultados nem sobre decisões tomadas "
            "com base neles. Confira com seu contador e seu advogado antes de agir.",
        )

    def test_tokens_and_css(self):
        self.assertEqual(brand.TOKENS["blue-retail"], "#0000ff")
        self.assertEqual(brand.TOKENS["yellow-like"], "#dbff2a")
        css = brand.base_css()
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("Manrope", css)
        self.assertIn("1200px", css)
        self.assertNotIn(EM, css)
        self.assertNotIn(EN, css)

    def test_brand_sources_have_no_dash(self):
        src = (ROOT / "core/cd2-super/shared/scripts/brand.py").read_text()
        self.assertNotIn(EM, src)
        self.assertNotIn(EN, src)


if __name__ == "__main__":
    unittest.main()
