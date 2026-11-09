"""Kit de marca CD2 Tech compartilhado pelos renderizadores das skills.

So biblioteca padrao. O sync copia este arquivo para scripts/ de cada skill e
os logos para assets/brand/, por isso os logos sao lidos de ../assets/brand/
relativo a este arquivo. No conhecimento de um GPT o ChatGPT poe todos os
arquivos numa pasta so; nesse caso os logos ficam ao lado deste arquivo.

Tem duas familias de funcoes: as das calculadoras (format_brl, base_css,
footer_html, disclaimer...) e as dos relatorios (moeda, numero, tokens_css,
footer_dados_html, disclaimer_dados...), que escolhem o aviso pela origem
dos dados.
"""
import base64
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
    "blue-experience": "#011e80",
    "blue-qwerty": "#0333f7",
    "frente-lilas": "#8a72ff",
}

WHATSAPP = "https://wa.me/5519982355172"

_DISCLAIMER = (
    "Estas contas e informações são apenas gerenciais, uma referência. "
    "Elas usam os números informados e a nossa leitura da regra em {data} "
    "({regra}), que pode mudar. A CD2 Tech não tem nenhuma responsabilidade sobre estes "
    "resultados nem sobre decisões tomadas com base neles. "
    "Confira com seu contador e seu advogado antes de agir."
)


def esc(text) -> str:
    return html.escape(str(text), quote=True)


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


# ---------------------------------------------------------------------------
# Relatorios: numeros em pt-BR, marca e aviso por origem dos dados.
# ---------------------------------------------------------------------------

FORMATOS = ("moeda", "inteiro", "decimal", "pct", "pp", "dias", "data", "texto")
SEM_DADO = "s/d"
ORIGENS = ("banco", "outro-mcp", "arquivo", "digitado")

_FONTE_POR_ORIGEM = {
    "banco": "os dados do banco conectado",
    "outro-mcp": "os dados do banco conectado",
    "arquivo": "o arquivo informado",
    "digitado": "os dados informados",
}
_DISCLAIMER_DADOS = (
    "Estas contas e informações são apenas gerenciais, uma referência. "
    "Elas usam {fonte} em {data}. "
    "A CD2 Tech não tem nenhuma responsabilidade sobre estes resultados nem sobre "
    "decisões tomadas com base neles. "
    "Confira com seu contador e seu advogado antes de agir."
)


def _arredonda(valor, casas: int) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def numero(valor, casas: int = 0) -> str:
    dec = _arredonda(abs(valor), casas)
    inteiro, _, frac = f"{dec:.{casas}f}".partition(".")
    corpo = _group(inteiro) + ("," + frac if casas else "")
    return ("-" if valor < 0 and dec != 0 else "") + corpo


def moeda(valor) -> str:
    texto = numero(abs(valor), 2)
    return ("-" if valor < 0 and texto != "0,00" else "") + "R$ " + texto


def moeda_compacta(valor) -> str:
    sinal = "-" if valor < 0 else ""
    v = abs(valor)
    if v >= 1e6:
        return f"{sinal}R$ {numero(v / 1e6, 1)} mi"
    if v >= 1000:
        return f"{sinal}R$ {numero(v / 1000, 0)} mil"
    return f"{sinal}R$ {numero(v, 0)}"


def pct(valor, casas: int = 1) -> str:
    return numero(valor, casas) + "%"


def data_br(iso) -> str:
    texto = str(iso)
    if len(texto) >= 10 and texto[4] == "-" and texto[7] == "-":
        return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]}"
    return texto


def e_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def formatar(valor, formato=None) -> str:
    if valor is None or valor == "":
        return SEM_DADO
    if formato == "data":
        return data_br(valor)
    if not e_numero(valor):
        return str(valor)
    if formato == "moeda":
        return moeda(valor)
    if formato == "decimal":
        return numero(valor, 2)
    if formato == "pct":
        return pct(valor)
    if formato == "pp":
        return numero(valor, 1) + " p.p."
    if formato == "dias":
        return numero(valor, 0) + " d"
    if formato == "inteiro":
        return numero(valor, 0)
    return numero(valor, 0) if float(valor).is_integer() else numero(valor, 2)


def _skill_assets_dirs() -> tuple:
    """Pastas candidatas a conter assets/fonts: a raiz da skill, ao lado do script ou a pasta plana do GPT."""
    return (_HERE.parent / "assets", _HERE / "assets", _HERE)


def _data_uri(caminho: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(caminho.read_bytes()).decode("ascii")


def font_face() -> str:
    """Manrope embutida (OFL). Sem o arquivo no pacote, fica o system-ui."""
    for base in _skill_assets_dirs():
        for caminho in (base / "fonts" / "Manrope-Variable.woff2", base / "Manrope-Variable.woff2"):
            if caminho.is_file():
                uri = _data_uri(caminho, "font/woff2")
                return (
                    "@font-face { font-family: 'Manrope'; "
                    f"src: url({uri}) format('woff2'); "
                    "font-weight: 200 800; font-display: swap; }"
                )
    return ""


def logo_html() -> str:
    """Os dois logos como imagem; tokens_css() mostra o certo conforme o tema de quem abre."""
    claro = _data_uri(_ASSETS / "cd2tech-horizontal.svg", "image/svg+xml")
    escuro = _data_uri(_ASSETS / "cd2tech-horizontal-white.svg", "image/svg+xml")
    return (
        f'<img class="cd2-logo cd2-logo-claro" src="{claro}" alt="CD2 Tech">'
        f'<img class="cd2-logo cd2-logo-escuro" src="{escuro}" alt="CD2 Tech">'
    )


_ESCURO = """
  --surface: {black-agile}; --raised: #121212; --ink: {white-human}; --muted: {gray-solution};
  --link: {blue-sky}; --hairline: {frente-neutro-escuro}; --focus: {yellow-like};
  --up: #3ecf8a; --down: #ff8a80; --warn-ink: #ffb800;
  --chart-1: {blue-sky}; --chart-2: {gray-solution}; --track: #2a2a2e;
  --band-a: rgba(1, 158, 255, .20); --band-b: rgba(138, 114, 255, .12); --band-c: rgba(161, 166, 174, .07);
  --s1: #0b1730; --s2: {blue-experience}; --s3: {blue-qwerty}; --s4: {blue-sky}; --s5: #a5dcff;
  --cla: {blue-sky}; --on-cla: {black-agile}; --clb: {frente-lilas}; --on-clb: {black-agile};
  color-scheme: dark;
"""


def tokens_css() -> str:
    c = TOKENS
    escuro = _ESCURO.format(**c)
    return f"""
:root {{
  --surface: {c['white-human']}; --raised: #ffffff; --brand: {c['blue-retail']}; --ink: {c['black-agile']};
  --muted: {c['frente-neutro-escuro']}; --on-brand: {c['white-human']}; --link: {c['blue-retail']};
  --border: {c['gray-tech']}; --hairline: {c['gray-solution']}; --focus: {c['blue-tech']};
  --highlight: {c['yellow-like']}; --on-highlight: {c['black-agile']};
  --red: #c4281c; --on-red: #ffffff; --amber: #ffb800; --on-amber: #000000; --green: #13804a; --on-green: #ffffff;
  --up: #13804a; --down: #c4281c; --warn-ink: #8a5a00;
  --chart-1: {c['blue-retail']}; --chart-2: {c['gray-tech']}; --track: #d9d9de;
  --band-a: rgba(0, 0, 255, .10); --band-b: rgba(33, 14, 158, .06); --band-c: rgba(70, 74, 83, .05);
  --s1: #dfe0ff; --s2: #a9acff; --s3: #6a6eff; --s4: #2b30ff; --s5: #0000b8;
  --cla: {c['blue-retail']}; --on-cla: {c['white-human']}; --clb: {c['purple-shift']}; --on-clb: {c['white-human']};
  --r-sm: 6px; --r-md: 12px; --r-lg: 24px; --r-pill: 999px;
  --font: 'Manrope', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{{escuro}}} }}
:root[data-theme="dark"] {{{escuro}}}
.cd2-logo {{ height: 28px; width: auto; display: block; }}
.cd2-logo-escuro {{ display: none; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) .cd2-logo-escuro {{ display: block; }}
  :root:not([data-theme="light"]) .cd2-logo-claro {{ display: none; }}
}}
:root[data-theme="dark"] .cd2-logo-escuro {{ display: block; }}
:root[data-theme="dark"] .cd2-logo-claro {{ display: none; }}
.cd2-assinatura {{ display: flex; gap: 24px; align-items: center; margin-top: 8px; padding: 24px 0; border-top: 1px solid var(--border); }}
.cd2-assinatura-logo {{ flex: none; }}
.cd2-assinatura-aviso {{ margin: 0; font-size: 14px; line-height: 20px; color: var(--muted); }}
@media (max-width: 600px) {{ .cd2-assinatura {{ flex-direction: column; align-items: flex-start; gap: 16px; }} }}
""".strip()


def disclaimer_dados(origem: str, data_br: str) -> str:
    """Aviso de isencao do relatorio: diz de onde vieram os numeros (ver ORIGENS)."""
    if origem not in _FONTE_POR_ORIGEM:
        raise ValueError(f"origem '{origem}' invalida (use {', '.join(ORIGENS)})")
    return _DISCLAIMER_DADOS.format(fonte=_FONTE_POR_ORIGEM[origem], data=data_br)


def footer_dados_html(origem: str, data_br: str) -> str:
    return (
        f'<footer class="cd2-assinatura"><div class="cd2-assinatura-logo">{logo_html()}</div>'
        f'<p class="cd2-assinatura-aviso">{esc(disclaimer_dados(origem, data_br))}</p></footer>'
    )


def footer_dados_text(origem: str, data_br: str) -> str:
    return "CD2 Tech\n" + disclaimer_dados(origem, data_br)
