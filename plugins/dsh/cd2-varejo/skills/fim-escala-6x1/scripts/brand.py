"""Kit de marca CD2 Tech compartilhado pelos renderizadores das skills.

So biblioteca padrao. O sync copia este arquivo para scripts/ de cada skill e
os logos para assets/brand/, por isso os logos sao lidos de ../assets/brand/
relativo a este arquivo. No conhecimento de um GPT o ChatGPT poe todos os
arquivos numa pasta so; nesse caso os logos ficam ao lado deste arquivo.
"""
import html
import re
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _assets_dir() -> Path:
    for path in (_HERE.parent / "assets" / "brand", _HERE / "assets" / "brand", _HERE):
        if (path / "cd2tech-horizontal.svg").is_file():
            return path
    return _HERE.parent / "assets" / "brand"


_ASSETS = _assets_dir()

# Texto puro, sem f-string: o sync troca o placeholder pelo utm_source de cada
# plataforma e o valor chega intacto ao link.
UTM_SOURCE = "deepseek"

TOKENS = {
    "blue-retail": "#0000ff",
    "blue-tech": "#3c1fff",
    "white-human": "#f2f2f2",
    "black-agile": "#000000",
    "purple-shift": "#210e9e",
    "yellow-like": "#dbff2a",
    "blue-sky": "#019eff",
    "frente-neutro-escuro": "#464a53",
    "gray-solution": "#a1a6ae",
    "gray-tech": "#6a717f",
    "surface-raised-light": "#ffffff",
    "surface-raised-dark": "#121212",
}

WHATSAPP = "https://wa.me/5519982355172"

_DISCLAIMER = (
    "Estas contas e informações são apenas gerenciais, uma referência. "
    "Elas usam os números informados e a nossa leitura da regra em {data} "
    "({regra}), que pode mudar. A CD2 Tech não tem nenhuma responsabilidade sobre estes "
    "resultados nem sobre decisões tomadas com base neles. "
    "Confira com seu contador e seu advogado antes de agir."
)


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def csv_cell(text: str) -> str:
    text = str(text)
    if any(c in text for c in (";", ",", '"', "\n", "\r")):
        return '"' + text.replace('"', '""') + '"'
    return text


def _round_half_up(value: float, digits: int) -> Decimal:
    # Mesmo arredondamento do toFixed do JS (metade para cima sobre o valor binario exato).
    return Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def _group(int_part: str) -> str:
    return f"{int(int_part):,}".replace(",", ".")


def format_brl(value: float) -> str:
    dec = _round_half_up(abs(value), 2)
    int_part, frac = f"{dec:.2f}".split(".")
    sign = "-" if value < 0 and dec != 0 else ""
    return f"{sign}R$ {_group(int_part)},{frac}"


def _decimal_br(value: float, digits: int = 1) -> str:
    return f"{_round_half_up(value, digits):.{digits}f}".replace(".", ",")


def format_brl_compact(value: float) -> str:
    if value >= 1e6:
        return f"R$ {_decimal_br(value / 1e6)} mi"
    if value >= 1000:
        return f"R$ {_decimal_br(value / 1000)} mil"
    return f"R$ {int(_round_half_up(value, 0))}"


def format_date_br(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def link(url: str, campaign: str) -> str:
    sep = "&" if "?" in url else "?"
    return url + sep + "utm_source=" + UTM_SOURCE + "&utm_medium=skill&utm_campaign=" + campaign


def whatsapp_link(skill_title: str, platform_title: str) -> str:
    msg = (
        f"Oi, vim pela skill {skill_title} no {platform_title} "
        "e quero falar sobre uso na minha empresa."
    )
    return f"{WHATSAPP}?text={urllib.parse.quote(msg)}"


def disclaimer(regra: str, data_br: str) -> str:
    return _DISCLAIMER.format(regra=regra, data=data_br)


def _logo(theme: str, css_class: str) -> str:
    name = "cd2tech-horizontal-white.svg" if theme == "dark" else "cd2tech-horizontal.svg"
    svg = (_ASSETS / name).read_text(encoding="utf-8")
    svg = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)

    # Remove width/height fixos da tag raiz para o logo escalar pelo CSS (viewBox mantido).
    def fix_root(m):
        tag = re.sub(r'\s(?:width|height)="[^"]*"', "", m.group(0))
        return tag.replace(
            "<svg", f'<svg class="{css_class}" role="img" aria-label="CD2 Tech"', 1
        )

    return re.sub(r"<svg\b[^>]*>", fix_root, svg, count=1).strip()


def logo_svg(theme: str = "light") -> str:
    return _logo("dark" if theme == "dark" else "light", "cd2-logo")


def logo_pair_html() -> str:
    """Os dois logos inline; o base_css() mostra um conforme o tema do leitor."""
    return (
        _logo("light", "cd2-logo cd2-logo--light")
        + _logo("dark", "cd2-logo cd2-logo--dark")
    )


def footer_html(regra: str, data_br: str, theme: str = "auto") -> str:
    logo = logo_svg(theme) if theme in ("light", "dark") else logo_pair_html()
    return (
        '<footer class="cd2-assinatura">'
        f'<div class="cd2-assinatura-logo">{logo}</div>'
        f'<p class="cd2-assinatura-aviso">{esc(disclaimer(regra, data_br))}</p>'
        "</footer>"
    )


def footer_text(regra: str, data_br: str) -> str:
    return "CD2 Tech\n" + disclaimer(regra, data_br)


def base_css() -> str:
    t = TOKENS
    return f"""
:root {{
  --surface: {t['white-human']};
  --surface-raised: {t['surface-raised-light']};
  --surface-brand: {t['blue-retail']};
  --ink: {t['black-agile']};
  --ink-muted: {t['frente-neutro-escuro']};
  --ink-on-brand: {t['white-human']};
  --link: {t['blue-retail']};
  --action: {t['blue-retail']};
  --action-hover: {t['blue-tech']};
  --border: {t['gray-tech']};
  --focus-ring: {t['blue-tech']};
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 24px;
  --radius-pill: 999px;
  --font: Manrope, system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --surface: {t['black-agile']};
    --surface-raised: {t['surface-raised-dark']};
    --ink: {t['white-human']};
    --ink-muted: {t['gray-solution']};
    --link: {t['blue-sky']};
    --focus-ring: {t['yellow-like']};
  }}
}}
:root[data-theme="dark"] {{
  --surface: {t['black-agile']};
  --surface-raised: {t['surface-raised-dark']};
  --ink: {t['white-human']};
  --ink-muted: {t['gray-solution']};
  --link: {t['blue-sky']};
  --focus-ring: {t['yellow-like']};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--surface);
  color: var(--ink);
  font-family: var(--font);
  font-size: 16px;
  line-height: 24px;
}}
main, .cd2-container {{ max-width: 1200px; margin: 0 auto; padding: 0 16px; }}
@media (min-width: 768px) {{
  main, .cd2-container {{ padding: 0 64px; }}
}}
h1, h2, h3 {{ font-weight: 800; letter-spacing: -0.01em; }}
a {{ color: var(--link); }}
:focus-visible {{ outline: 2px solid var(--focus-ring); outline-offset: 2px; }}
.cd2-card {{
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: none;
}}
.cd2-botao {{
  display: inline-block;
  background: var(--action);
  color: var(--ink-on-brand);
  border-radius: var(--radius-pill);
  padding: 12px 16px;
  font-weight: 700;
  text-decoration: none;
}}
.cd2-botao:hover {{ background: var(--action-hover); }}
.cd2-logo {{ height: 32px; width: auto; display: block; }}
.cd2-logo--dark {{ display: none; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) .cd2-logo--dark {{ display: block; }}
  :root:not([data-theme="light"]) .cd2-logo--light {{ display: none; }}
}}
[data-theme="dark"] .cd2-logo--dark {{ display: block; }}
[data-theme="dark"] .cd2-logo--light {{ display: none; }}
[data-theme="light"] .cd2-logo--dark {{ display: none; }}
[data-theme="light"] .cd2-logo--light {{ display: block; }}
.cd2-assinatura {{
  display: flex;
  gap: 24px;
  align-items: center;
  margin-top: 48px;
  padding: 24px 0;
  border-top: 1px solid var(--border);
}}
.cd2-assinatura-logo {{ flex: 0 0 auto; }}
.cd2-assinatura-aviso {{ margin: 0; font-size: 14px; line-height: 20px; color: var(--ink-muted); }}
@media (max-width: 600px) {{
  .cd2-assinatura {{ flex-direction: column; align-items: flex-start; gap: 16px; }}
}}
""".strip()
