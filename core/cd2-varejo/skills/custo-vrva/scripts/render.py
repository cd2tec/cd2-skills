#!/usr/bin/env python3
"""Entrega da skill custo-vrva: monta a página, a planilha, o resumo de
WhatsApp e o texto a partir da saída do calc.py.

Os números vêm todos da saída do calc.py. Aqui só se formata, escapa e
organiza. Toda entrega termina com o rodapé de assinatura da CD2 Tech.

Uso:
    python3 calc.py --input dados.json > saida.json
    python3 render.py --result saida.json --format html > entrega.html
    python3 render.py --result saida.json --format whatsapp --insights insights.json

Formatos: html, csv, whatsapp, markdown. Só biblioteca padrão (Python 3.10+).
"""
import argparse
import base64
import importlib.util
import json
import re
import sys
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# brand.py fica ao lado deste arquivo no pacote final (o sync copia). No
# repositório (layout core) ele mora em cd2-varejo/shared/scripts.
_HERE = Path(__file__).resolve().parent
_PATHS = [_HERE]
if len(_HERE.parents) > 2:
    _PATHS.append(_HERE.parents[2] / "shared" / "scripts")
for _p in _PATHS:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))

import brand  # noqa: E402
from brand import esc, format_brl, format_date_br  # noqa: E402


def _load_calc():
    # As duas skills têm um calc.py. Carregar pelo caminho, com nome próprio, garante
    # que esta entrega usa o motor desta skill mesmo quando a outra já foi importada.
    name = "custo_vrva_calc"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _HERE / "calc.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


calc = _load_calc()

SKILL = "custo-vrva"
SKILL_TITLE = "Quanto o VR/VA custa de verdade"
# Nome da regra no aviso do brand.py: "a nossa leitura da regra em {data} ({regra})".
REGRA = "Decreto 12.712/2025"
FORMATS = ("html", "csv", "whatsapp", "markdown")
THEMES = ("light", "dark", "auto")

SITE_URL = "https://calc-vrva.cd2.com.br/"
SIXBYONE_URL = "https://calc-fim-escala6x1.cd2.com.br/"
CD2_URL = "https://cd2.com.br/"
ARCHEO_URL = "https://archeo.cd2.com.br/"
METODOLOGIA_URL = (
    "https://github.com/cd2tec/cd2-skills/blob/main/core/cd2-varejo/skills/"
    "custo-vrva/references/metodologia.md"
)

# Rótulos do semáforo, do próprio site (t.result.status em src/i18n/pt-BR.ts).
STATUS_LABEL = {"red": "Acima", "amber": "Pouco acima", "green": "Dentro"}
_ICON = {
    "red": '<path d="M3 3l6 6M9 3l-6 6"/>',
    "amber": '<path d="M6 2.5v4.5M6 9.5v.01"/>',
    "green": '<path d="M2.5 6.5l2.5 2.5 4.5-5.5"/>',
}
_INFO_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
    '<path d="M12 11v5M12 8h.01"/></svg>'
)
_NO_SALES = "Nenhuma bandeira com vendas no mês. " + calc.NO_SALES

_PARAM_LABELS = {
    "version": "data de conferência dos parâmetros",
    "checked_at": "data de conferência das regras",
    "decree": "texto do decreto",
    "official_text_url": "link do texto oficial",
    "verified_against_official_text": "conferência no texto oficial",
    "mdr_cap_percent": "teto da taxa (MDR)",
    "settlement_max_days": "prazo máximo de repasse",
    "rate_cap_since": "início do teto",
    "interoperability_starts_on": "data da interoperabilidade",
    "judicial_status": "situação na Justiça",
    "money_cost_month_percent": "custo do dinheiro padrão",
    "days_per_month": "dias do mês",
    "red_excess_rate_points": "corte do vermelho na taxa",
    "red_days": "corte do vermelho no prazo",
    "max_rate_percent": "taxa máxima aceita",
    "max_days": "prazo máximo aceito",
}


# ------------------------------------------------------------------ números

def _fixed(value, digits=2) -> str:
    # Mesmo arredondamento do toFixed da calculadora (metade para cima sobre o valor binário).
    q = Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:.{digits}f}".replace(".", ",")


def _pct(value) -> str:
    return calc.format_percent(value)


def _num(value) -> str:
    return str(int(value)) if float(value).is_integer() else _pct(value)


def _plural(count, singular, plural) -> str:
    return singular if count == 1 else plural


def _days(value) -> str:
    return f"{_num(value)} {_plural(value, 'dia', 'dias')}"


def _date(iso) -> str:
    return format_date_br(iso) if isinstance(iso, str) and re.match(r"^\d{4}-\d{2}-\d{2}", iso) else str(iso or "")


# ------------------------------------------------------------------ leitura

def _name(row) -> str:
    return calc.brand_name(row["brand"].get("name"))


class _Ctx:
    """Tudo o que a entrega precisa, lido uma vez da saída do calc.py."""

    def __init__(self, output, insights, profile, sources, theme, platform):
        self.output = output
        self.insights = [str(i).strip() for i in insights if str(i).strip()]
        self.profile = profile or {}
        self.sources = [s for s in sources if isinstance(s, dict)]
        self.theme = theme
        self.platform = platform
        self.legal, self.assumptions, _ = calc.load_params()
        defaults = {**self.legal, **self.assumptions}
        rules = {**defaults, **(output.get("rules") or {})}
        self.rules = rules
        self.cap = _pct(rules["mdr_cap_percent"])
        self.max_days = _num(rules["settlement_max_days"])
        self.overridden = list(output.get("overridden") or [])
        self.today = output.get("today") or ""
        self.checked = _date(output.get("checked_at") or self.legal["checked_at"])
        judicial = output.get("judicial_status")
        self.judicial = judicial if isinstance(judicial, dict) else self.legal["judicial_status"]
        self.errors = [str(e) for e in output.get("errors") or []]

        if "stores" in output:
            self.units = [(str(s.get("name") or f"Loja {i}"), self._entry(s)) for i, s in enumerate(output["stores"], 1)]
            self.network = output.get("network") or {}
        elif "result" in output:
            self.units = [(None, self._entry(output))]
            self.network = None
        else:
            self.units = []
            self.network = None
        if not self.errors and not any(entry["result"]["counted"] for _, entry in self.units):
            self.errors = [_NO_SALES]

    def _entry(self, block) -> dict:
        result = block["result"]
        return {
            "result": result,
            "verdict": block.get("verdict") or calc.verdict(result),
            "actions": block.get("actions") or calc.actions(result, self.rules),
        }

    @property
    def multi(self) -> bool:
        return self.network is not None

    def numbers(self) -> dict:
        """Totais: o resultado da loja, ou a soma da rede."""
        return self.network if self.multi else self.units[0][1]["result"]

    def verdict(self) -> dict:
        if self.multi:
            return self.network.get("verdict") or calc.verdict({**self.network, "brands": [
                row for _, entry in self.units for row in entry["result"]["brands"]]})
        return self.units[0][1]["verdict"]

    def money_percent(self):
        values = {entry["result"]["money_cost_month_percent"] for _, entry in self.units}
        return values.pop() if len(values) == 1 else None

    @property
    def profile_line(self) -> str:
        name = str(self.profile.get("name") or "").strip()
        role = str(self.profile.get("role") or "").strip()
        return ", ".join(p for p in (name, role) if p)


# ------------------------------------------------------ textos da entrega

def _override_text(ctx) -> str:
    labels = [_PARAM_LABELS.get(k, k) for k in ctx.overridden]
    return f"Parâmetro atualizado pela pesquisa: {calc.join_names(labels)}."


def _override_detail(ctx) -> str:
    return (
        "Usamos o valor que você confirmou na pesquisa de novidades, no lugar do que vem na skill, "
        f"conferido em {_date(ctx.legal['checked_at'])}. As contas abaixo já usam o valor novo."
    )


def _ok_text(ctx) -> str:
    return (
        f"Taxa até {ctx.cap}% e repasse em até {ctx.max_days} dias. Vale conferir o extrato todo mês, "
        "porque a taxa cobrada nem sempre é a do contrato."
    )


def _hero_sub(ctx) -> str:
    parts = []
    if ctx.multi:
        parts.append(f"Somando as {len(ctx.units)} lojas da rede.")
        top = ctx.network.get("top_store")
        if top:
            parts.append(f"A loja com mais custo é {top}.")
    if ctx.numbers()["total_month"] <= 0:
        parts.append(_ok_text(ctx))
    return " ".join(parts)


_PER_MONTH = "por mês a mais do que o decreto permite."
_PER_YEAR = "por ano, somando 12 meses."


def _total_line(numbers) -> str:
    # t.summary.total do site, com o valor exato.
    return f"{format_brl(numbers['total_month'])} por mês, {format_brl(numbers['total_year'])} por ano, acima do que o decreto permite."


def _excess_card(ctx, numbers):
    """(título, valor ou None, texto) do cartão da taxa acima do teto."""
    title = f"Taxa acima do teto de {ctx.cap}%"
    if numbers["excess_fee_month"] > 0:
        return (title, f"{format_brl(numbers['excess_fee_month'])} por mês",
                f"{format_brl(numbers['excess_fee_year'])} por ano. É a diferença entre a sua taxa e {ctx.cap}%, "
                "sobre o que você vende em vale.")
    return title, None, f"Nenhuma bandeira cobra acima de {ctx.cap}%."


def _stuck_card(ctx, numbers):
    """(título, valor ou None, texto) do cartão do dinheiro parado."""
    title = f"Dinheiro parado além de {ctx.max_days} dias"
    if numbers["stuck_money"] > 0:
        money = ctx.money_percent()
        rate = f", a {_pct(money)}% ao mês" if money is not None else ", ao custo do dinheiro de cada loja"
        return (title, f"{format_brl(numbers['stuck_money'])} presos",
                f"Custam {format_brl(numbers['stuck_cost_month'])} por mês{rate}. "
                "É o que as operadoras seguram além do prazo da regra.")
    return title, None, f"Todas as bandeiras pagam em até {ctx.max_days} dias."


def _legend(ctx) -> str:
    points = ctx.rules["red_excess_rate_points"]
    return (
        f"Dentro: taxa até {ctx.cap}% e prazo até {ctx.max_days} dias. "
        f"Acima: taxa {_num(points)} {_plural(points, 'ponto', 'pontos')} ou mais acima do teto, "
        f"ou prazo de {_num(ctx.rules['red_days'])} dias ou mais. Pouco acima: o resto."
    )


def _interop_title(ctx) -> str:
    return f"O que muda com a interoperabilidade ({_date(ctx.rules['interoperability_starts_on'])})"


def _interop_items(ctx):
    return [
        "Qualquer maquininha passa a poder aceitar qualquer cartão de vale, sem contrato com cada operadora. "
        "A adoção vai ser gradual: nem todo cartão vai passar em toda maquininha logo no primeiro dia.",
        f"A taxa e o prazo passam a ser negociados também com quem fornece a maquininha. O teto de {ctx.cap}% "
        f"e os {ctx.max_days} dias continuam valendo.",
    ]


_JUDICIAL_TITLE = "Situação na Justiça"
_JUDICIAL_NOTE = (
    "A situação judicial pode mudar quem precisa cumprir o decreto. Antes de cobrar a operadora, "
    "confira se saiu decisão nova."
)


def _judicial_date(ctx) -> str:
    return f"Situação conferida em {_date(ctx.judicial.get('checked_at'))}"


def _judicial_sources(ctx):
    """(texto, url segura) das fontes da situação na Justiça."""
    out = []
    for url in ctx.judicial.get("sources") or []:
        safe = _safe_url(url)
        if safe:
            host = urllib.parse.urlparse(safe).netloc
            out.append((host[4:] if host.startswith("www.") else host, safe))
    return out


def _how_lines(ctx):
    """(formulas, linhas por bandeira) de "Como calculamos"."""
    dpm = _num(ctx.rules["days_per_month"])
    money = ctx.money_percent()
    cost = (f"Custo do parado por mês = dinheiro parado × {_pct(money)}% ao mês." if money is not None
            else "Custo do parado por mês = dinheiro parado × custo do dinheiro de cada loja, em % ao mês.")
    formulas = [
        f"Acima do teto por mês = vendas no mês × (sua taxa menos {ctx.cap}%).",
        f"Dinheiro parado = vendas no mês ÷ {dpm} × dias além de {ctx.max_days}.",
        cost,
        "Por ano = por mês × 12.",
    ]
    rows = []
    if not ctx.multi:
        for row in ctx.units[0][1]["result"]["brands"]:
            name, sales = _name(row), format_brl(row["brand"]["sales"])
            if row["excess_rate"] > 0:
                rows.append(f"{name}: {sales} × ({_pct(row['brand']['rate'])}% menos {ctx.cap}%) = "
                            f"{format_brl(row['excess_fee_month'])} por mês acima do teto.")
            if row["extra_days"] > 0:
                rows.append(f"{name}: {sales} ÷ {dpm} × {_days(row['extra_days'])} = {format_brl(row['stuck_money'])} "
                            f"parados, que custam {format_brl(row['stuck_cost_month'])} por mês.")
    return formulas, rows


_HOW_INTRO = "Contas feitas só com os números informados, bandeira por bandeira, e somadas no fim."
_MONEY_NOTE = "O custo do dinheiro é uma premissa. Você pode informar outro valor, como o que pagaria num capital de giro."

_LIMITS = (
    "Não entram tarifa de intercâmbio, que não é cobrada da loja, aluguel de maquininha, antecipação, "
    "impostos ou outras cobranças.",
    "A situação judicial pode mudar quem precisa cumprir o decreto.",
    "O Comitê Gestor do PAT pode alterar o teto e o prazo.",
    "A conta usa a taxa e o prazo informados. O que foi cobrado de verdade está no extrato de cada operadora.",
)

_COMMERCIAL_TITLE = "Quer ir além da estimativa?"
_COMMERCIAL_TEXT = (
    "Testar na sua operação é livre. Para usar no dia a dia da empresa, "
    "com suporte e responsabilidade, fale com a CD2."
)
_ERP_TITLE = "Seu ERP concilia isso sozinho?"
_ERP_TEXT = (
    "Taxa diferente do contrato e repasse atrasado só aparecem quando alguém confere venda por venda. "
    "A CD2 faz isso com os dados do seu ERP."
)
_ARCHEO_TITLE = "Seus números estão no ERP?"
_ARCHEO_TEXT = "O Archeo MCP Creator, da CD2, cria a conexão para puxar os dados direto do sistema, sem digitar."
_SITE_TITLE = "Quer só a conta rápida?"
_SITE_TEXT = "A calculadora gratuita da CD2 faz em 2 minutos, sem cadastro."
_SIXBYONE_TITLE = "Fim da escala 6x1: prepare sua loja"
_SIXBYONE_TEXT = (
    "Veja quanta gente a mais a nova jornada pede, quanto custa por mês e o que fazer primeiro. "
    "A CD2 também tem a skill fim-escala-6x1 e a calculadora gratuita da 6x1."
)
_AGENTS_TITLE = "Menos conferência manual, mais hora para o time"
_AGENTS_TEXT = (
    "Agentes de IA podem assumir parte do trabalho repetitivo, como conferir extrato, taxa e repasse, "
    "e devolver horas para o time. A CD2 ajuda a ver onde isso faz sentido na sua loja e a implantar. "
    "Este ganho não entra nos números acima."
)


def _links(ctx) -> dict:
    return {
        "site": brand.link(SITE_URL, SKILL),
        "sixbyone": brand.link(SIXBYONE_URL, SKILL),
        "cd2": brand.link(CD2_URL, SKILL),
        "archeo": brand.link(ARCHEO_URL, SKILL),
        "whatsapp": brand.whatsapp_link(SKILL_TITLE, ctx.platform),
    }


def _safe_url(url) -> str:
    url = str(url or "").strip()
    return url if urllib.parse.urlparse(url).scheme in ("http", "https") else ""


def _source_items(ctx):
    """(título, url segura ou "", data) das fontes, o texto oficial primeiro."""
    items = [("Decreto 12.712/2025 no site do Planalto", _safe_url(ctx.rules.get("official_text_url")),
              f"Texto oficial conferido em {ctx.checked}. Arts. 182-B e 182-C.")]
    for s in ctx.sources:
        title = str(s.get("title") or s.get("url") or "").strip()
        if title:
            items.append((title, _safe_url(s.get("url")), _date(s.get("date"))))
    return items


def _above_names(result):
    return [_name(r) for r in result["brands"] if r["status"] != "green"]


# ---------------------------------------------------------------------- HTML

def _pill(status, cls="pill") -> str:
    return (
        f'<span class="{cls} {status}"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{_ICON[status]}</svg>{STATUS_LABEL[status]}</span>"
    )


def _a(href, text, cls="") -> str:
    klass = f' class="{cls}"' if cls else ""
    return f'<a{klass} href="{esc(href)}" target="_blank" rel="noopener">{esc(text)}</a>'


def _find(*candidates):
    for path in candidates:
        if path.is_file():
            return path
    return None


def _template() -> str:
    path = _find(_HERE.parent / "assets" / "template.html", _HERE / "assets" / "template.html", _HERE / "template.html")
    if path is None:
        raise FileNotFoundError("assets/template.html")
    return path.read_text(encoding="utf-8")


def _font_face() -> str:
    """Manrope embutida (OFL), se o arquivo vier no pacote. Sem ele, fica o system-ui."""
    path = _find(
        _HERE.parent / "assets" / "fonts" / "Manrope-Variable.woff2",
        _HERE / "assets" / "fonts" / "Manrope-Variable.woff2",
        _HERE / "fonts" / "Manrope-Variable.woff2",
        _HERE / "Manrope-Variable.woff2",
    )
    if path is None:
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        "@font-face { font-family: Manrope; font-weight: 200 800; font-display: swap; "
        f'src: url(data:font/woff2;base64,{data}) format("woff2"); }}'
    )


def _fill(template, values) -> str:
    # Uma passada só: o texto inserido nunca é relido como placeholder.
    # Placeholders desconhecidos (como o de UTM, trocado pelo sync) ficam como estão.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template)


def _html_header(ctx) -> str:
    meta = ['<p class="eyebrow">NOVAS REGRAS DO VR E VA</p>']
    if ctx.profile_line:
        meta.append(f'<p class="para">Preparado para {esc(ctx.profile_line)}</p>')
    if ctx.today and not ctx.errors:
        meta.append(f'<p class="caption">Calculado em {esc(_date(ctx.today))}. Regras conferidas em {esc(ctx.checked)}.</p>')
    return "".join(meta)


def _html_hero(ctx) -> str:
    verdict = ctx.verdict()
    status = verdict["status"]
    numbers = ctx.numbers()
    sub = _hero_sub(ctx)
    parts = [_pill(status, "selo"), f'<h1 class="display-lg" id="veredito">{esc(verdict["title"])}</h1>']
    if sub:
        parts.append(f'<p class="veredito-sub">{esc(sub)}</p>')
    if numbers["total_month"] > 0:
        parts.append(
            '<div class="veredito-numeros">'
            f'<div><p class="stat"><span class="nw">{format_brl(numbers["total_month"])}</span></p>'
            f'<p class="stat-line">{_PER_MONTH}</p></div>'
            f'<div><p class="stat stat-sm"><span class="nw">{format_brl(numbers["total_year"])}</span></p>'
            f'<p class="stat-line">{_PER_YEAR}</p></div></div>'
        )
    return f'<section class="bloco veredito v-{status}" aria-labelledby="veredito">{"".join(parts)}</section>'


def _html_errors(ctx) -> str:
    items = "".join(f"<li>{esc(e)}</li>" for e in ctx.errors)
    return (
        '<section class="bloco b-raised" role="alert" aria-labelledby="erros">'
        '<p class="eyebrow">FALTAM DADOS</p>'
        '<h1 class="heading-md" id="erros">Faltam dados para fazer a conta</h1>'
        f'<ul class="erros">{items}</ul>'
        '<p class="body-sm mut">Corrija e rode a conta de novo. Nenhum número foi calculado.</p></section>'
    )


def _html_notices(ctx) -> str:
    if not ctx.overridden:
        return ""
    return (
        f'<section class="aviso" role="note">{_INFO_ICON}<div><b>{esc(_override_text(ctx))}</b>'
        f"<p>{esc(_override_detail(ctx))}</p></div></section>"
    )


def _html_cost_card(card) -> str:
    title, value, text = card
    if value:
        body = f'<p class="stat stat-sm"><span class="nw">{esc(value)}</span></p><p class="stat-line">{esc(text)}</p>'
    else:
        body = f'<p class="body-sm">{esc(text)}</p>'
    return f'<article class="bloco b-raised custo"><h2 class="label mut">{esc(title)}</h2>{body}</article>'


def _html_costs(ctx) -> str:
    numbers = ctx.numbers()
    cards = _html_cost_card(_excess_card(ctx, numbers)) + _html_cost_card(_stuck_card(ctx, numbers))
    return f'<section class="custos" aria-label="Os dois custos">{cards}</section>'


_COLUMNS = ("Vendas no mês", "Taxa", "Prazo", "Acima do teto por mês", "Parado além do prazo",
            "Custo do parado por mês", "Total por mês")


def _html_table(result) -> str:
    head = '<th scope="col">Bandeira</th>' + "".join(f'<th scope="col" class="n">{c}</th>' for c in _COLUMNS)
    head += '<th scope="col">Situação</th>'
    body = []
    for row in result["brands"]:
        values = (format_brl(row["brand"]["sales"]), f"{_pct(row['brand']['rate'])}%", _days(row["brand"]["days"]),
                  format_brl(row["excess_fee_month"]), format_brl(row["stuck_money"]),
                  format_brl(row["stuck_cost_month"]), format_brl(row["total_month"]))
        cells = "".join(f'<td class="n" data-label="{c}">{v}</td>' for c, v in zip(_COLUMNS, values))
        body.append(f'<tr><th scope="row">{esc(_name(row))}</th>{cells}'
                    f'<td data-label="Situação">{_pill(row["status"])}</td></tr>')
    totals = (format_brl(sum(r["brand"]["sales"] for r in result["brands"])), "", "",
              format_brl(result["excess_fee_month"]), format_brl(result["stuck_money"]),
              format_brl(result["stuck_cost_month"]), format_brl(result["total_month"]))
    foot = "".join(f'<td class="n" data-label="{c}">{v}</td>' for c, v in zip(_COLUMNS, totals))
    return (
        f'<table class="tabela"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>'
        f'<tfoot><tr><th scope="row">Total</th>{foot}<td></td></tr></tfoot></table>'
    )


def _html_actions_list(actions) -> str:
    return "".join(f"<li><span>{esc(a)}</span></li>" for a in actions)


def _html_brands(ctx) -> str:
    legend = f'<p class="legenda">{esc(_legend(ctx))}</p>'
    if not ctx.multi:
        return (
            '<section class="secao" aria-labelledby="t-bandeiras"><div class="secao-topo">'
            '<h2 class="heading-md" id="t-bandeiras">Por bandeira</h2>'
            f'<p class="body-sm mut">Só as bandeiras com vendas no mês entram na conta.</p></div>'
            f'{_html_table(ctx.units[0][1]["result"])}{legend}</section>'
        )
    stores = []
    for name, entry in ctx.units:
        result, verdict = entry["result"], entry["verdict"]
        if not result["counted"]:
            stores.append(f'<article class="bloco b-raised loja" aria-label="{esc(name)}"><h3 class="heading-sm">{esc(name)}</h3>'
                          '<p class="body-sm mut">Nenhuma bandeira com vendas no mês nesta loja.</p></article>')
            continue
        money = (f"<p>{esc(_total_line(result))}</p>" if result["total_month"] > 0 else "")
        stores.append(
            f'<article class="bloco b-raised loja" aria-label="{esc(name)}">'
            f'<h3 class="heading-sm">{esc(name)}</h3>'
            f'<p class="loja-linha">{_pill(verdict["status"])}<span>{esc(verdict["title"])}</span></p>{money}'
            f'{_html_table(result)}'
            f'<h4 class="label">O que fazer nesta loja</h4><ol class="acoes">{_html_actions_list(entry["actions"])}</ol></article>'
        )
    return (
        '<section class="secao" aria-labelledby="t-lojas"><div class="secao-topo">'
        '<h2 class="heading-md" id="t-lojas">Loja por loja</h2>'
        '<p class="body-sm mut">Cada loja tem a sua conta. A rede soma.</p></div>'
        f'{"".join(stores)}{legend}</section>'
    )


def _html_actions(ctx) -> str:
    if ctx.multi:
        return ""
    return (
        '<section class="bloco b-raised" aria-labelledby="t-acoes"><div class="secao-topo">'
        '<h2 class="heading-md" id="t-acoes">O que fazer</h2>'
        '<p class="body-sm mut">Em ordem de prioridade.</p></div>'
        f'<ol class="acoes">{_html_actions_list(ctx.units[0][1]["actions"])}</ol></section>'
    )


def _html_interop(ctx) -> str:
    items = "".join(f"<li>{esc(i)}</li>" for i in _interop_items(ctx))
    return (
        '<section class="bloco b-raised" aria-labelledby="t-interop">'
        f'<h2 class="heading-md" id="t-interop">{esc(_interop_title(ctx))}</h2>'
        f'<ul class="lista">{items}</ul></section>'
    )


def _html_insights(ctx) -> str:
    if not ctx.insights:
        return ""
    items = "".join(f"<li>{esc(i)}</li>" for i in ctx.insights)
    return (
        '<section class="bloco b-brand leitura" aria-labelledby="t-leitura">'
        '<span class="grifo">DO SEU CASO</span>'
        f'<h2 class="heading-md" id="t-leitura">Leitura da CD2</h2><ul>{items}</ul></section>'
    )


def _html_judicial(ctx) -> str:
    links = "".join(f"<li>{_a(url, host)}</li>" for host, url in _judicial_sources(ctx))
    sources = f'<h3 class="label">Fontes</h3><ul class="fontes">{links}</ul>' if links else ""
    return (
        '<section class="bloco b-raised justica" aria-labelledby="t-justica">'
        f'<h2 class="heading-md" id="t-justica">{_JUDICIAL_TITLE}</h2>'
        f'<span class="data">{esc(_judicial_date(ctx))}</span>'
        f'<p class="texto">{esc(str(ctx.judicial.get("text") or ""))}</p>'
        f'<p class="body-sm mut">{esc(_JUDICIAL_NOTE)}</p>{sources}</section>'
    )


def _html_how(ctx) -> str:
    formulas, rows = _how_lines(ctx)
    lines = "".join(f"<p><b>{esc(f)}</b></p>" for f in formulas) + "".join(f"<p>{esc(r)}</p>" for r in rows)
    limits = "".join(f"<li>{esc(x)}</li>" for x in _LIMITS)
    return (
        '<section class="bloco b-raised" aria-labelledby="t-como">'
        '<h2 class="heading-md" id="t-como">Como calculamos</h2>'
        f'<p class="body-sm mut">É a mesma conta da calculadora gratuita da CD2. {esc(_HOW_INTRO)}</p>'
        f'<div class="conta">{lines}<p>{esc(_legend(ctx))}</p><p>{esc(_MONEY_NOTE)}</p></div>'
        f'<h3 class="label">Limites</h3><ul class="fora">{limits}</ul>'
        f'<p class="body-sm">{_a(METODOLOGIA_URL, "Ler a metodologia completa")}</p></section>'
    )


def _html_sources(ctx) -> str:
    lis = []
    for title, url, when in _source_items(ctx):
        name = _a(url, title) if url else f"<b>{esc(title)}</b>"
        date = f'<span class="caption">{esc(when)}</span>' if when else ""
        lis.append(f"<li>{name}{date}</li>")
    return (
        '<section class="secao" aria-labelledby="t-fontes">'
        f'<h2 class="heading-sm" id="t-fontes">Fontes</h2><ul class="fontes">{"".join(lis)}</ul></section>'
    )


def _html_commercial(ctx) -> str:
    link = _links(ctx)
    return (
        '<section class="bloco b-raised comercial" aria-labelledby="t-comercial">'
        f'<h2 class="heading-md" id="t-comercial">{_COMMERCIAL_TITLE}</h2><p>{esc(_COMMERCIAL_TEXT)}</p>'
        f'<div class="botoes">{_a(link["whatsapp"], "Falar com a CD2 no WhatsApp", "cd2-botao")}'
        f'{_a(link["cd2"], "Conhecer a CD2", "cd2-botao sec")}</div>'
        '<div class="extras">'
        f'<p><b>{_ERP_TITLE}</b> {esc(_ERP_TEXT)}</p>'
        f'<p><b>{_ARCHEO_TITLE}</b> {esc(_ARCHEO_TEXT)} {_a(link["archeo"], "Conhecer o Archeo")}</p>'
        f'<p><b>{_SITE_TITLE}</b> {esc(_SITE_TEXT)} {_a(link["site"], "Abrir a calculadora")}</p>'
        "</div></section>"
    )


def _html_bridges(ctx) -> str:
    link = _links(ctx)
    return (
        '<section class="pontes" aria-label="Também da CD2">'
        '<article class="bloco b-raised ponte"><span class="tag">Também da CD2</span>'
        f'<h2 class="heading-sm">{_SIXBYONE_TITLE}</h2><p class="body-sm">{esc(_SIXBYONE_TEXT)}</p>'
        f'{_a(link["sixbyone"], "Abrir a calculadora da 6x1")}</article>'
        '<article class="bloco b-raised ponte"><span class="tag">Outra saída</span>'
        f'<h2 class="heading-sm">{_AGENTS_TITLE}</h2><p class="body-sm">{esc(_AGENTS_TEXT)}</p>'
        f'{_a(link["cd2"], "Conhecer os agentes de IA da CD2")}</article></section>'
    )


_SECTIONS = ("NOTICES", "COSTS", "BRANDS", "ACTIONS", "INTEROP", "INSIGHTS", "JUDICIAL", "HOW", "SOURCES",
             "COMMERCIAL", "BRIDGES")


def _render_html(ctx) -> str:
    theme = ctx.theme
    values = {
        "THEME_ATTR": f' data-theme="{theme}"' if theme in ("light", "dark") else "",
        "COLOR_SCHEME": theme if theme in ("light", "dark") else "light dark",
        "TITLE": esc(_title_text(ctx)),
        "FONT_FACE": _font_face(),
        "BASE_CSS": brand.base_css(),
        "LOGO": brand.logo_svg(theme) if theme in ("light", "dark") else brand.logo_pair_html(),
        "HEADER_META": _html_header(ctx),
        "FOOTER": brand.footer_html(REGRA, ctx.checked, theme),
    }
    if ctx.errors:
        values["HERO"] = _html_errors(ctx)
    else:
        values.update({
            "HERO": _html_hero(ctx),
            "NOTICES": _html_notices(ctx),
            "COSTS": _html_costs(ctx),
            "BRANDS": _html_brands(ctx),
            "ACTIONS": _html_actions(ctx),
            "INTEROP": _html_interop(ctx),
            "INSIGHTS": _html_insights(ctx),
            "JUDICIAL": _html_judicial(ctx),
            "HOW": _html_how(ctx),
            "SOURCES": _html_sources(ctx),
            "COMMERCIAL": _html_commercial(ctx),
            "BRIDGES": _html_bridges(ctx),
        })
    for key in _SECTIONS:
        values.setdefault(key, "")
    return _fill(_template(), values)


# ---------------------------------------------------------------- textos

def _title_text(ctx) -> str:
    return SKILL_TITLE + (f": {ctx.profile_line}" if ctx.profile_line else "")


def _status_lines(ctx):
    """Total e bandeiras acima, ou o texto de "dentro da regra", como o resumo do site."""
    numbers = ctx.numbers()
    if numbers["total_month"] <= 0:
        return [_ok_text(ctx)]
    lines = [_total_line(numbers)]
    if not ctx.multi:
        lines.append(f"Bandeiras acima: {calc.join_names(_above_names(ctx.units[0][1]['result']))}.")
    return lines


def _judicial_line(ctx) -> str:
    when = _date(ctx.judicial.get("checked_at"))
    return f"{_JUDICIAL_TITLE}, conferida em {when}. {str(ctx.judicial.get('text') or '').strip()}"


def _render_whatsapp(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked)
    lines = [f"*{_title_text(ctx)}*", ""]
    if ctx.errors:
        lines += ["Faltam dados para fazer a conta:"] + [f"- {e}" for e in ctx.errors] + ["", footer]
        return "\n".join(lines) + "\n"
    lines.append(f"*{ctx.verdict()['title']}*")
    lines += _status_lines(ctx)
    if ctx.overridden:
        lines.append(_override_text(ctx))
    lines.append("")
    if ctx.multi:
        lines.append("*Loja por loja*")
        for name, entry in ctx.units:
            result = entry["result"]
            text = f"{format_brl(result['total_month'])} por mês" if result["total_month"] > 0 else "dentro da regra"
            first = f" Primeiro passo: {entry['actions'][0]}" if result["counted"] else " Nenhuma bandeira com vendas no mês."
            lines.append(f"- {name}: {text}.{first}")
        lines.append("")
    else:
        lines.append("*O que fazer primeiro*")
        lines += [f"{i}. {a}" for i, a in enumerate(ctx.units[0][1]["actions"][:3], 1)]
        lines.append("")
    if ctx.insights:
        lines.append("*Leitura da CD2*")
        lines += [f"- {i}" for i in ctx.insights]
        lines.append("")
    lines += [_judicial_line(ctx), ""]
    lines += ["Faça a conta da sua loja, de graça e sem cadastro:", _links(ctx)["site"], "", footer]
    return "\n".join(lines) + "\n"


_MD_SPECIAL = re.compile(r"([\\`*_\[\]|#<>])")


def _md(text) -> str:
    """Texto de fora (nomes, insights) seguro em Markdown: sem HTML cru e sem quebrar tabela."""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _MD_SPECIAL.sub(r"\\\1", text).replace("\n", " ")


def _md_link(text, url) -> str:
    return f"[{_md(text)}]({url})" if url else _md(text)


def _md_table(result):
    out = ["| Bandeira | " + " | ".join(_COLUMNS) + " | Situação |", "|" + "---|" * (len(_COLUMNS) + 2)]
    for row in result["brands"]:
        cells = [_md(_name(row)), format_brl(row["brand"]["sales"]), f"{_pct(row['brand']['rate'])}%",
                 _days(row["brand"]["days"]), format_brl(row["excess_fee_month"]), format_brl(row["stuck_money"]),
                 format_brl(row["stuck_cost_month"]), format_brl(row["total_month"]), STATUS_LABEL[row["status"]]]
        out.append("| " + " | ".join(cells) + " |")
    total = ["**Total**", format_brl(sum(r["brand"]["sales"] for r in result["brands"])), "", "",
             format_brl(result["excess_fee_month"]), format_brl(result["stuck_money"]),
             format_brl(result["stuck_cost_month"]), f"**{format_brl(result['total_month'])}**", ""]
    out.append("| " + " | ".join(total) + " |")
    return out


def _render_markdown(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked)
    lines = [f"# {_md(_title_text(ctx))}", ""]
    if ctx.errors:
        lines += ["## Faltam dados para fazer a conta", ""] + [f"- {_md(e)}" for e in ctx.errors]
        lines += ["", "Corrija e rode a conta de novo. Nenhum número foi calculado.", "", "---", "", footer]
        return "\n".join(lines) + "\n"
    verdict = ctx.verdict()
    numbers = ctx.numbers()
    lines += [f"## {verdict['title']}", ""]
    if numbers["total_month"] > 0:
        lines += [f"**{format_brl(numbers['total_month'])}** {_PER_MONTH} **{format_brl(numbers['total_year'])}** {_PER_YEAR}", ""]
    sub = _hero_sub(ctx)
    if sub:
        lines += [_md(sub), ""]
    if ctx.today:
        lines += [f"Calculado em {_date(ctx.today)}. Regras conferidas em {ctx.checked}.", ""]
    if ctx.overridden:
        lines += [f"> **{_override_text(ctx)}** {_override_detail(ctx)}", ""]

    lines += ["## Os dois custos", ""]
    for title, value, text in (_excess_card(ctx, numbers), _stuck_card(ctx, numbers)):
        lines.append(f"- **{title}:** " + (f"{value}. {text}" if value else text))
    lines.append("")

    if ctx.multi:
        lines += ["## Loja por loja", "", "Cada loja tem a sua conta. A rede soma.", ""]
        for name, entry in ctx.units:
            result = entry["result"]
            lines += [f"### {_md(name)}", ""]
            if not result["counted"]:
                lines += ["Nenhuma bandeira com vendas no mês nesta loja.", ""]
                continue
            lines += [f"**{STATUS_LABEL[entry['verdict']['status']]}.** {entry['verdict']['title']}.", ""]
            if result["total_month"] > 0:
                lines += [_total_line(result), ""]
            lines += _md_table(result) + ["", "O que fazer nesta loja:", ""]
            lines += [f"{i}. {_md(a)}" for i, a in enumerate(entry["actions"], 1)] + [""]
        lines += [_legend(ctx), ""]
    else:
        lines += ["## Por bandeira", ""] + _md_table(ctx.units[0][1]["result"]) + ["", _legend(ctx), ""]
        lines += ["## O que fazer", "", "Em ordem de prioridade.", ""]
        lines += [f"{i}. {_md(a)}" for i, a in enumerate(ctx.units[0][1]["actions"], 1)] + [""]

    lines += [f"## {_interop_title(ctx)}", ""] + [f"- {i}" for i in _interop_items(ctx)] + [""]

    if ctx.insights:
        lines += ["## Leitura da CD2", ""] + [f"- {_md(i)}" for i in ctx.insights] + [""]

    lines += [f"## {_JUDICIAL_TITLE}", "", f"{_md(ctx.judicial.get('text') or '')} {_judicial_date(ctx)}.", "",
              _JUDICIAL_NOTE, ""]
    lines += [f"- [{_md(host)}]({url})" for host, url in _judicial_sources(ctx)] + [""]

    formulas, rows = _how_lines(ctx)
    lines += ["## Como calculamos", "", f"É a mesma conta da calculadora gratuita da CD2. {_HOW_INTRO}", ""]
    lines += [f"- {f}" for f in formulas] + [f"- {_md(r)}" for r in rows]
    lines += ["", _MONEY_NOTE, "", "Limites:", ""] + [f"- {x}" for x in _LIMITS]
    lines += ["", f"[Ler a metodologia completa]({METODOLOGIA_URL})", ""]

    lines += ["## Fontes", ""]
    lines += [f"- {_md_link(t, u)}" + (f", {_md(d)}" if d else "") for t, u, d in _source_items(ctx)] + [""]

    link = _links(ctx)
    lines += [
        f"## {_COMMERCIAL_TITLE}", "", _COMMERCIAL_TEXT, "",
        f"- Fale com a CD2 no WhatsApp: {link['whatsapp']}",
        f"- Conheça a CD2: {link['cd2']}",
        f"- {_ERP_TITLE} {_ERP_TEXT}",
        f"- {_ARCHEO_TITLE} {_ARCHEO_TEXT} {link['archeo']}",
        f"- {_SITE_TITLE} {_SITE_TEXT} {link['site']}",
        f"- {_SIXBYONE_TITLE}. {_SIXBYONE_TEXT} {link['sixbyone']}",
        f"- {_AGENTS_TITLE}. {_AGENTS_TEXT} Conheça os agentes de IA da CD2: {link['cd2']}",
        "", "---", "", footer,
    ]
    return "\n".join(lines) + "\n"


def _cell(value) -> str:
    """Célula de texto do CSV, protegida contra fórmula (=, +, -, @) ao abrir no Excel."""
    text = str(value)
    if text and text[0] in "=+-@\t\r":
        text = "'" + text
    return brand.csv_cell(text)


_CSV_HEADERS = ["Bandeira", "Vendas no mês (R$)", "Taxa (%)", "Acima do teto por mês (R$)", "Prazo (dias)",
                "Dias além do prazo", "Dinheiro parado (R$)", "Custo do parado por mês (R$)", "Total por mês (R$)",
                "Situação"]


def _csv_rows(name, result):
    prefix = [_cell(name)] if name is not None else []
    rows = []
    for r in result["brands"]:
        cells = [_cell(_name(r)), _fixed(r["brand"]["sales"]), _pct(r["brand"]["rate"]), _fixed(r["excess_fee_month"]),
                 _num(r["brand"]["days"]), _num(r["extra_days"]), _fixed(r["stuck_money"]),
                 _fixed(r["stuck_cost_month"]), _fixed(r["total_month"]), _cell(STATUS_LABEL[r["status"]])]
        rows.append(";".join(prefix + cells))
    return rows


def _csv_total(label, numbers, sales):
    cells = ["Total", _fixed(sales), "", _fixed(numbers["excess_fee_month"]), "", "", _fixed(numbers["stuck_money"]),
             _fixed(numbers["stuck_cost_month"]), _fixed(numbers["total_month"]), ""]
    return ";".join(([_cell(label)] if label is not None else []) + cells)


def _render_csv(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked).split("\n")
    if ctx.errors:
        rows = [_cell("Faltam dados para fazer a conta")] + [_cell(e) for e in ctx.errors]
        rows += [""] + [_cell(line) for line in footer]
        return "﻿" + "\r\n".join(rows) + "\r\n"
    headers = (["Loja"] if ctx.multi else []) + _CSV_HEADERS
    rows = [";".join(_cell(h) for h in headers)]
    all_sales = 0
    for name, entry in ctx.units:
        result = entry["result"]
        sales = sum(r["brand"]["sales"] for r in result["brands"])
        all_sales += sales
        rows += _csv_rows(name, result)
        rows.append(_csv_total(name, result, sales))
    if ctx.multi:
        rows.append(_csv_total("Rede", ctx.network, all_sales))
    rows.append("")
    rows += [_cell(line) for line in [ctx.verdict()["title"] + "."] + _status_lines(ctx)]
    if ctx.overridden:
        rows.append(_cell(_override_text(ctx)))
    rows.append(_cell(_judicial_line(ctx)))
    rows.append("")
    rows += [_cell(line) for line in footer]
    return "﻿" + "\r\n".join(rows) + "\r\n"


# ---------------------------------------------------------------------- API

def render(output: dict, fmt: str, *, insights=(), profile=None, sources=(), theme: str = "light",
           platform: str = "Claude") -> str:
    """Monta a entrega no formato pedido. `output` é a saída do calc.py, ou {"errors": [...]}."""
    if fmt not in FORMATS:
        raise ValueError(f"formato desconhecido: {fmt} (use {', '.join(FORMATS)})")
    if theme not in THEMES:
        raise ValueError(f"tema desconhecido: {theme} (use {', '.join(THEMES)})")
    if not isinstance(output, dict):
        raise ValueError("a saída do calc.py precisa ser um objeto JSON")
    ctx = _Ctx(output, list(insights or ()), profile, list(sources or ()), theme, platform or "Claude")
    return {"html": _render_html, "csv": _render_csv, "whatsapp": _render_whatsapp, "markdown": _render_markdown}[fmt](ctx)


# ---------------------------------------------------------------------- CLI

def _fail(errors) -> int:
    print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
    return 2


def _read_json(path, label):
    try:
        if path is None:
            raw = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as exc:
        raise ValueError(f"Não consegui ler {label}: {exc.strerror or exc}.")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"JSON inválido em {label}: {exc}.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Entrega da skill custo-vrva (CD2 Tech).")
    parser.add_argument("--result", help="saída JSON do calc.py (padrão: stdin)")
    parser.add_argument("--format", required=True, choices=FORMATS)
    parser.add_argument("--insights", help="arquivo JSON com a lista de insights (textos)")
    parser.add_argument("--sources", help='arquivo JSON com as fontes: [{"title", "url", "date"}]')
    parser.add_argument("--profile", help='arquivo JSON com o perfil: {"name", "role"}')
    parser.add_argument("--theme", default="light", choices=THEMES)
    parser.add_argument("--platform", default="Claude", help="nome da plataforma na mensagem do WhatsApp")
    parser.add_argument("--output", help="grava a entrega neste arquivo em vez de imprimir")
    args = parser.parse_args(argv)
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if args.result is None and sys.stdin.isatty():
        return _fail(["Informe a saída do calc.py com --result saida.json, ou mande o JSON pela entrada padrão."])
    try:
        output = _read_json(args.result, "o resultado")
        insights = _read_json(args.insights, "os insights") if args.insights else []
        sources = _read_json(args.sources, "as fontes") if args.sources else []
        profile = _read_json(args.profile, "o perfil") if args.profile else None
    except ValueError as exc:
        return _fail([str(exc)])
    problems = []
    if not isinstance(output, dict) or not ({"errors", "result", "stores"} & set(output)):
        problems.append("O resultado precisa ser a saída do calc.py.")
    if not isinstance(insights, list):
        problems.append("Os insights precisam ser uma lista de textos.")
    if not isinstance(sources, list):
        problems.append("As fontes precisam ser uma lista.")
    if profile is not None and not isinstance(profile, dict):
        problems.append("O perfil precisa ser um objeto.")
    if problems:
        return _fail(problems)
    try:
        text = render(output, args.format, insights=insights, profile=profile, sources=sources,
                      theme=args.theme, platform=args.platform)
    except Exception as exc:  # rede de segurança: JSON limpo no stdout, detalhe no stderr, sem traceback
        print(f"render.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return _fail([f"Erro inesperado ao montar a entrega: {type(exc).__name__}."])
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
