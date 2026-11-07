#!/usr/bin/env python3
"""Entrega da skill fim-escala-6x1: monta a página, a planilha, o resumo de
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
import json
import re
import sys
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# brand.py e calc.py ficam ao lado deste arquivo no pacote final (o sync copia
# brand.py). No repositório (layout core) brand.py mora em cd2-varejo/shared/scripts.
_HERE = Path(__file__).resolve().parent
_PATHS = [_HERE]
if len(_HERE.parents) > 2:
    _PATHS.append(_HERE.parents[2] / "shared" / "scripts")
for _p in _PATHS:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))

import brand  # noqa: E402
import calc  # noqa: E402
from brand import esc, format_brl_compact, format_date_br  # noqa: E402

SKILL = "fim-escala-6x1"
SKILL_TITLE = "Fim da escala 6x1"
# Nome da regra no aviso do brand.py: "a nossa leitura da regra em {data} ({regra})".
REGRA = "Emenda Constitucional 141/2026"
FORMATS = ("html", "csv", "whatsapp", "markdown")
THEMES = ("light", "dark", "auto")

SITE_URL = "https://calc-fim-escala6x1.cd2.com.br/"
VRVA_URL = "https://calc-vrva.cd2.com.br/"
CD2_URL = "https://cd2.com.br/"
ARCHEO_URL = "https://archeo.cd2.com.br/"
METODOLOGIA_URL = (
    "https://github.com/cd2tec/cd2-skills/blob/main/core/cd2-varejo/skills/"
    "fim-escala-6x1/references/metodologia.md"
)

STATUS_LABEL = {"red": "Apertado", "amber": "Atenção", "green": "Tranquilo"}
_ICON = {
    "red": '<path d="M3 3l6 6M9 3l-6 6"/>',
    "amber": '<path d="M6 2.5v4.5M6 9.5v.01"/>',
    "green": '<path d="M2.5 6.5l2.5 2.5 4.5-5.5"/>',
}
_INFO_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
    '<path d="M12 11v5M12 8h.01"/></svg>'
)
_NO_PEOPLE = "Preencha as pessoas de pelo menos um setor."
_SMALL_BUSINESS = "Para MEI e pequena empresa, a lei específica ainda não saiu: regra e data podem mudar."
_UNNAMED = "Setor sem nome"
_ON = ' class="on"'

_PARAM_LABELS = {
    "version": "data de conferência dos parâmetros",
    "source": "fonte da regra",
    "official_text_url": "link do texto oficial",
    "verified_against_official_text": "conferência no texto oficial",
    "current": "jornada de hoje",
    "daily_hours_limit": "limite de horas por dia",
    "phases": "datas e jornadas das fases da regra",
    "sunday_rest_preferred": "folga no domingo",
    "salary_reduction_allowed": "redução de salário",
    "collective_bargaining_override": "papel do acordo coletivo",
    "default_charges_factor": "encargos padrão",
    "weeks_per_month": "semanas por mês",
    "overtime_multiplier": "adicional de hora extra",
    "overtime_divisor_per_weekly_hour": "divisor de hora extra",
    "default_overtime_cap_hours_per_day": "limite de hora extra por dia",
    "red_person_equivalent": "corte do vermelho",
    "amber_person_equivalent": "corte do amarelo",
}

_NOT_COUNTED = (
    "Adicional noturno, insalubridade, intervalo intrajornada e rescisão.",
    "Custo de contratar e treinar, e rotatividade.",
    "Movimento da loja por dia e por hora.",
    "Horas devolvidas ao time por agentes de IA ou outra automação.",
    "Regime compensatório por norma coletiva, com média de 2 folgas no mês.",
    "Cláusulas coletivas incompatíveis com a emenda, que perdem efeito em 16/12/2026.",
    "Empregado com diploma de nível superior e salário alto, que fica fora das regras de jornada.",
    "Medidas para MEI, microempresa e empresa de pequeno porte, que dependem de lei complementar ainda não publicada.",
    "Terceirizados da administração pública, que têm regra própria.",
    "Ganho de escala entre lojas. Em rede, cada loja tem a sua conta e a rede soma as faixas.",
)


# ------------------------------------------------------------------ números

def _fixed(value, digits=1) -> str:
    # Mesmo arredondamento do toFixed da calculadora (metade para cima sobre o valor binário).
    q = Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:.{digits}f}".replace(".", ",")


def _round(value) -> int:
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _int(value) -> str:
    return f"{int(value):,}".replace(",", ".")


def _num(value) -> str:
    """Horas e pessoas: inteiro com milhar, ou uma casa decimal."""
    return _int(value) if float(value).is_integer() else _fixed(value, 1)


def _pct(value, digits=1) -> str:
    return f"{_fixed(value, digits)}%"


def _plural(count, singular, plural) -> str:
    return singular if count == 1 else plural


def _people(count) -> str:
    return f"{_num(count)} {_plural(count, 'pessoa', 'pessoas')}"


def _date(iso) -> str:
    return format_date_br(iso) if isinstance(iso, str) and re.match(r"^\d{4}-\d{2}-\d{2}", iso) else str(iso or "")


# ------------------------------------------------------------------ leitura

def _name(sector: dict) -> str:
    return str(sector.get("name") or "").strip() or _UNNAMED


def _has_people(scenarios: dict) -> bool:
    return any(s["result"]["sectors"] for s in scenarios.values())


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
        self.overridden = list(output.get("overridden") or [])
        ov = set(self.overridden)
        phases = self.legal["phases"]
        # Datas das fases só quando não foram trocadas pela pesquisa: a saída não traz as novas.
        self.first = None if "phases" in ov else phases[0]["starts_on"]
        self.last = None if "phases" in ov else phases[-1]["starts_on"]
        self.today = output.get("today") or ""
        self.checked = _date(output.get("checked_at") or self.legal["version"])
        self.errors = [str(e) for e in output.get("errors") or []]

        if "stores" in output:
            self.units = [(str(s.get("name") or f"Loja {i}"), s["scenarios"]) for i, s in enumerate(output["stores"], 1)]
            self.network = output.get("network") or {}
        elif "scenarios" in output:
            self.units = [(None, output["scenarios"])]
            self.network = None
        else:
            self.units = []
            self.network = None
        if not self.errors and not any(_has_people(sc) for _, sc in self.units):
            self.errors = [_NO_PEOPLE]
        self.keys = [k for k in calc.SCENARIO_ORDER if any(k in sc for _, sc in self.units)]

    @property
    def multi(self) -> bool:
        return self.network is not None

    @property
    def store_label(self) -> str:
        return "rede" if self.multi else "loja"

    def rule(self, key) -> dict:
        for _, scenarios in self.units:
            if key in scenarios:
                return scenarios[key]["result"]["rule"]
        return {}

    def hours(self, key):
        return self.rule(key).get("weekly_hours")

    def numbers(self, key) -> dict:
        """Totais da situação: o resultado da loja, ou a soma da rede."""
        if self.multi:
            entry = dict(self.network.get(key) or {})
            entry["rule"] = self.rule(key)
            return entry
        return self.units[0][1][key]["result"]

    def verdict(self, key) -> dict:
        if self.multi:
            numbers = self.numbers(key)
            return calc.verdict({"rule": numbers["rule"], "counts": numbers.get("counts") or {"red": 0, "amber": 0, "green": 0}})
        return self.units[0][1][key]["verdict"]

    def label(self, key):
        """(título, explicação, rótulo curto) da situação."""
        h = _num(self.hours(key) or 0)
        first = _date(self.first) if self.first else ""
        last = _date(self.last) if self.last else ""
        if self.keys == ["with_agreement"]:
            return "Com a jornada da sua convenção", "A jornada da convenção substitui a regra geral nas contas.", f"Sua convenção, {h}h"
        if self.keys == ["without_agreement"]:
            return "Regra para todos", (f"Em vigor desde {last}." if last else ""), f"Para todos, {h}h"
        if key == "without_agreement":
            sub = f"Pela nossa leitura do texto, a partir de {first}." if first else "Pela nossa leitura do texto."
            return "Sem acordo coletivo", sub, f"Sem acordo, {h}h"
        return "Com acordo coletivo", (f"De {first} até {last}." if first else ""), f"Com acordo, {h}h"

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
        f"conferido em {_date(ctx.legal['version'])}. As contas abaixo já usam o valor novo."
    )


def _hero_sub(ctx) -> str:
    key = ctx.keys[0]
    parts = []
    if ctx.multi:
        parts.append(f"Somando as {len(ctx.units)} lojas da rede.")
    if len(ctx.keys) == 2:
        parts.append("Pela situação sem acordo coletivo, a mais apertada. A situação com acordo vem logo abaixo.")
    elif ctx.keys == ["with_agreement"]:
        parts.append("Com a jornada da sua convenção.")
    elif key == "without_agreement" and ctx.last:
        parts.append(f"Com a regra que vale para todos desde {_date(ctx.last)}.")
    return " ".join(parts)


def _people_text(numbers):
    """(número, explicação) da gente a mais."""
    mn, mx = numbers["min_additional"], numbers["max_additional"]
    if mx == 0:
        if numbers["rule"].get("above_legal_limit"):
            return "Nenhuma contratação", "Só vale se essa jornada for permitida. Confirme com seu advogado."
        return "Nenhuma contratação", "Pelas contas, a equipe atual cobre as horas."
    if mn == mx:
        return _people(mx), "a mais. Treinar gente para cobrir mais de um setor não reduz este número."
    return (
        f"{_num(mn)} a {_people(mx)}",
        f"a mais. {_num(mn)} se você treinar gente para cobrir mais de um setor, {_num(mx)} com uma contratação em cada setor.",
    )


def _cost_text(numbers):
    """(mínimo, máximo ou None, explicação) do custo por mês, ou None sem contratação."""
    mx = numbers["max_additional"]
    if mx == 0:
        return None
    lo, hi = format_brl_compact(numbers["min_monthly_cost"]), format_brl_compact(numbers["max_monthly_cost"])
    ylo, yhi = format_brl_compact(numbers["min_annual_cost"]), format_brl_compact(numbers["max_annual_cost"])
    has_pct = "max_payroll_pct" in numbers
    if lo == hi:
        folha = f"{_pct(numbers['max_payroll_pct'])} a mais na folha. " if has_pct else ""
        return lo, None, f"por mês. {folha}{yhi} no ano, com encargos."
    folha = f"De +{_pct(numbers['min_payroll_pct'])} a +{_pct(numbers['max_payroll_pct'])} na folha. " if has_pct else ""
    return lo, hi, f"por mês. {folha}No ano, de {ylo} a {yhi}, com encargos."


def _lost_line(numbers) -> str:
    hours = numbers["rule"].get("weekly_hours") or 1
    equivalent = numbers.get("person_equivalent", numbers["total_lost_hours"] / hours)
    n = _round(equivalent)
    if n < 1:
        return "a menos por semana na loja, menos do que perder uma pessoa."
    where = "na rede" if "person_equivalent" not in numbers else "na loja"
    return f"a menos por semana {where}, como perder cerca de {_people(n)}."


def _extra_lines(numbers):
    """(número, explicação) das saídas sem contratar, quando a saída traz o valor."""
    out = []
    if "overtime_monthly_cost" in numbers:
        text = "por mês em hora extra, se tentar cobrir sem contratar. Tem limite legal e risco trabalhista: serve para tapar buraco, não como plano."
        if numbers.get("overtime_above_cap"):
            text += " Pelas contas, a hora extra por pessoa passaria do limite diário."
        out.append((format_brl_compact(numbers["overtime_monthly_cost"]), text))
    if "hour_cost_increase_pct" in numbers:
        out.append((f"+{_pct(numbers['hour_cost_increase_pct'], 2)}", "no custo da hora da equipe, mesmo sem contratar, porque o salário não pode cair."))
    return out


def _join_stat(stat, line) -> str:
    """Número e explicação numa frase só, para os formatos de texto."""
    return f"{stat} {line}" if line.startswith("a ") else f"{stat}. {line}"


def _sector_cells(row):
    """Textos de um setor numa situação: horas, contratação e alerta de postos."""
    lost = f"{_num(row['lost_hours'])}h a menos por semana"
    add = row["additional_headcount"]
    hire = "Ninguém a mais" if add == 0 else f"+{_people(add)}, {format_brl_compact(row['additional_monthly_cost'])} por mês"
    alert = ""
    if row["days_gap"] > 0:
        posts = row["sector"].get("min_simultaneous_staff") or 0
        alert = f"Com {_num(posts)} postos abertos, os dias não fecham com {_people(row['sector']['headcount'])}."
    return lost, hire, alert


def _matched_rows(scenarios, keys):
    """Linhas do primeiro cenário com o mesmo setor nos demais (a ordem pode mudar entre cenários)."""
    base = scenarios[keys[0]]["result"]["sectors"]
    pools = {k: list(scenarios[k]["result"]["sectors"]) for k in keys[1:] if k in scenarios}
    rows = []
    for row in base:
        line = {keys[0]: row}
        for key, pool in pools.items():
            for i, other in enumerate(pool):
                if other["sector"] == row["sector"]:
                    line[key] = pool.pop(i)
                    break
        rows.append((row["sector"], line))
    return rows


def _red_names(scenarios, key):
    return [_name(r["sector"]) for r in scenarios[key]["result"]["sectors"] if r["status"] == "red"]


def _legend(ctx) -> str:
    text = (
        "Apertado (vermelho): perde meia pessoa ou mais por semana, ou não fecha os postos informados. "
        "Atenção (amarelo): perde entre um quarto e meia pessoa. "
        "Tranquilo (verde): perde menos que isso, e dá para resolver na escala."
    )
    if {"red_person_equivalent", "amber_person_equivalent"} & set(ctx.overridden):
        text += " Os cortes foram atualizados pela pesquisa."
    return text


def _how_items(ctx):
    """(título, texto) de "Como calculamos". Com números da loja quando é uma loja só."""
    key = ctx.keys[0]
    rule = ctx.rule(key)
    h, d = rule.get("weekly_hours") or 0, rule.get("max_work_days") or 5
    hh = _num(h)
    items = []
    if len(ctx.keys) == 2:
        daily = _num(h / d) if d else ""
        until = f", até {_date(ctx.last)}" if ctx.last else ""
        items.append((
            "Com e sem acordo:",
            f"o limite é de {daily} horas por dia, e com {7 - d} folgas sobram {d} dias: {hh}h. "
            f"Só convenção ou acordo coletivo amplia o dia para chegar a {_num(ctx.hours('with_agreement'))}h{until}. "
            "Esta é uma leitura do texto: confirme com seu advogado.",
        ))
    single = None if ctx.multi else ctx.units[0][1][key]["result"]
    lost = "pessoas × (jornada atual − nova jornada), nunca abaixo de zero."
    if single:
        lost += (
            f" Na situação {ctx.label(key)[2].lower()}: {_num(single['total_lost_hours'])}h por semana. "
            f"{_num(single['total_lost_hours'])}h ÷ {hh}h = {_fixed(single['person_equivalent'])} pessoas."
        )
    items.append(("Horas a menos:", lost))
    top = "setor por setor, pessoas × jornada atual ÷ nova jornada, arredondado para cima, menos as pessoas de hoje."
    if single:
        top += f" Somando os setores: {_num(single['max_additional'])}."
    items.append(("Limite de cima, com uma contratação em cada setor:", top))
    if single:
        raw = single["total_person_hours"] / h
        up = calc.round_up(raw)
        more = max(0, up - single["total_headcount"])
        bottom = (
            f"{_num(single['total_person_hours'])} horas ÷ {hh} = {_fixed(raw)}, vira {_num(up)}, "
            f"que é {_num(more)} a mais que as {_num(single['total_headcount'])} pessoas de hoje."
        )
        gap = sum(r["days_gap"] for r in single["sectors"])
        if gap > 0 and single["min_additional"] == gap:
            bottom += f" Para fechar os postos são {_num(gap)} a mais, e esse é o limite de baixo."
    else:
        bottom = "o total de horas da loja ÷ nova jornada, arredondado para cima, menos as pessoas de hoje. Nunca fica abaixo do que falta para fechar os postos."
    items.append(("Limite de baixo, olhando a loja inteira:", bottom))
    posts = (
        "turnos = horas abertas ÷ (jornada ÷ dias), arredondado para cima. "
        "Pessoas-dia = dias abertos × postos × turnos. Necessárias = pessoas-dia ÷ dias, arredondado para cima."
    )
    if single:
        with_posts = [r for r in single["sectors"] if r.get("needed_by_days") is not None]
        if with_posts:
            r = with_posts[0]
            posts += f" Em {_name(r['sector'])}, dá {_people(r['needed_by_days'])}."
    items.append(("Pelos postos, quando informados:", posts))
    cost = "salário médio × (1 + encargos), já com 13º e férias."
    if single and single["sectors"]:
        r = single["sectors"][0]
        salary = r["sector"].get("avg_monthly_salary") or 0
        if salary:
            factor = (r["monthly_cost_per_head"] / salary - 1) * 100
            enc = _int(round(factor)) if abs(factor - round(factor)) < 1e-9 else _fixed(factor)
            average = single["monthly_payroll"] / single["total_headcount"] if single["total_headcount"] else 0
            cost = (
                f"salário médio × (1 + {enc}% de encargos), já com 13º e férias. No limite de baixo, quem falta "
                "para fechar os postos custa o custo por pessoa do próprio setor, e o restante usa o custo médio da loja: "
                f"{format_brl_compact(average)}."
            )
    items.append(("Custo por pessoa:", cost))
    items.append(("Custo da hora, sem contratar:", "jornada atual ÷ nova jornada − 1, porque o salário não pode cair."))
    ov = set(ctx.overridden)
    if {"weeks_per_month", "overtime_divisor_per_weekly_hour", "overtime_multiplier"} & ov:
        overtime = "horas a menos × semanas por mês × (salário ÷ divisor) × adicional, com os valores atualizados pela pesquisa."
    else:
        a = ctx.assumptions
        divisor = _num(h * a["overtime_divisor_per_weekly_hour"])
        overtime = (
            f"horas a menos × {_fixed(a['weeks_per_month'], 2)} semanas × (salário ÷ {divisor}) × "
            f"{_num(a['overtime_multiplier'])}. O divisor ainda é premissa: confirme com seu contador."
        )
    items.append(("Hora extra:", overtime))
    items.append(("Cor do setor:", _legend(ctx)))
    return items


_COMMERCIAL_TITLE = "Quer ir além da estimativa?"
_COMMERCIAL_TEXT = (
    "Esta avaliação é livre: use quanto quiser para entender a sua loja. Para usar no dia a dia da empresa, "
    "a skill é para clientes CD2, que ganham suporte, manutenção e responsabilidade da CD2."
)
_ARCHEO_TITLE = "Seus números estão no ERP ou na folha?"
_ARCHEO_TEXT = "O Archeo MCP Creator, da CD2, cria a conexão para puxar os dados direto do sistema, sem digitar."
_SITE_TITLE = "Quer só a conta rápida?"
_SITE_TEXT = "A calculadora gratuita da CD2 faz em menos de 5 minutos, sem cadastro."
_VRVA_TITLE = "Quanto o VR e o VA custam de verdade"
_VRVA_TEXT = (
    "Veja se a sua loja paga acima do teto de 3,6% no vale-refeição e no vale-alimentação, e quanto dinheiro "
    "fica parado com as operadoras. A CD2 também tem a skill custo-vrva e a calculadora gratuita de VR e VA."
)
_AGENTS_TITLE = "Menos tarefa manual, menos hora apertada"
_AGENTS_TEXT = (
    "Agentes de IA podem assumir parte do trabalho repetitivo da operação e devolver horas para o time. "
    "A CD2 ajuda a ver onde isso faz sentido na sua loja e a implantar. Este ganho não entra nos números acima."
)


def _links(ctx) -> dict:
    return {
        "site": brand.link(SITE_URL, SKILL),
        "vrva": brand.link(VRVA_URL, SKILL),
        "cd2": brand.link(CD2_URL, SKILL),
        "archeo": brand.link(ARCHEO_URL, SKILL),
        "whatsapp": brand.whatsapp_link(SKILL_TITLE, ctx.platform),
    }


def _safe_url(url) -> str:
    url = str(url or "").strip()
    return url if urllib.parse.urlparse(url).scheme in ("http", "https") else ""


def _source_items(ctx):
    """(título, url segura ou "", data) das fontes, a oficial embutida primeiro."""
    items = []
    if not {"source", "official_text_url"} & set(ctx.overridden):
        items.append((_text_or(ctx.legal.get("source"), "Texto oficial"), _safe_url(ctx.legal.get("official_text_url")),
                      f"Texto oficial conferido em {_date(ctx.legal['version'])}"))
    for s in ctx.sources:
        title = str(s.get("title") or s.get("url") or "").strip()
        if title:
            items.append((title, _safe_url(s.get("url")), _date(s.get("date"))))
    return items


def _text_or(value, default) -> str:
    return str(value).strip() if value else default


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
    meta = ['<p class="eyebrow">FIM DA ESCALA 6X1</p>']
    if ctx.profile_line:
        meta.append(f'<p class="para">Preparado para {esc(ctx.profile_line)}</p>')
    if ctx.today and not ctx.errors:
        meta.append(f'<p class="caption">Calculado em {_date(ctx.today)}. Regras conferidas em {ctx.checked}.</p>')
    return "".join(meta)


def _html_hero(ctx) -> str:
    key = ctx.keys[0]
    verdict = ctx.verdict(key)
    status = verdict["status"]
    sub = _hero_sub(ctx)
    sub_html = f'<p class="veredito-sub">{esc(sub)}</p>' if sub else ""
    return (
        f'<section class="bloco veredito v-{status}" aria-labelledby="veredito">'
        f'{_pill(status, "selo")}'
        f'<h1 class="display-lg" id="veredito">{esc(verdict["title"])}</h1>{sub_html}</section>'
    )


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


def _html_timeline(ctx) -> str:
    deadline = ctx.output.get("deadline") or ""
    days = calc.days_until(ctx.first, ctx.today) if ctx.first and ctx.today else None
    if days is not None and days >= 1:
        head = (
            f'<div><p class="stat">{_int(days)} {_plural(days, "dia", "dias")}</p>'
            f'<p class="stat-line">para a nova regra, que começa em {_date(ctx.first)}.</p></div>'
        )
    else:
        head = f'<div><p class="label mut">Prazo</p><p class="heading-sm">{esc(deadline)}</p></div>'
    steps = ""
    if ctx.first and ctx.today and not {"current", "daily_hours_limit"} & set(ctx.overridden):
        legal = ctx.legal
        first, last = legal["phases"][0], legal["phases"][-1]
        started = ctx.today >= first["starts_on"]
        if started:
            hours_today = calc.rule_for_scenario("without_agreement", legal, None, ctx.today)["weekly_hours"]
        else:
            hours_today = calc.rule_for_date(ctx.today, legal)["weekly_hours"]
        phase1 = f"5x2, ou {_num(first['weekly_hours'])}h com acordo coletivo"
        note_today = "6x1" if not started else ("5x2, para todos" if ctx.today >= last["starts_on"] else phase1)
        items = [
            ("Hoje", hours_today, note_today, True),
            (_date(first["starts_on"]), legal["daily_hours_limit"] * first["max_work_days"], phase1, False),
            (_date(last["starts_on"]), last["weekly_hours"], "5x2, para todos", False),
        ]
        lis = "".join(
            f'<li{_ON if on else ""}><span class="caption">{esc(when)}</span>'
            f'<b>{_num(hours)}h</b><span class="caption">{esc(note)}</span></li>'
            for when, hours, note, on in items
        )
        steps = f'<ol class="tempo" aria-label="Linha do tempo da nova jornada">{lis}</ol>'
    return (
        f'<section class="bloco b-raised prazo" aria-label="Prazo">{head}{steps}'
        f'<p class="caption">{esc(_SMALL_BUSINESS)}</p></section>'
    )


def _html_card(ctx, key, primary) -> str:
    title, sub, _ = ctx.label(key)
    numbers = ctx.numbers(key)
    verdict = ctx.verdict(key)
    situacao = "pill situacao" if primary else "pill situacao outra"
    parts = [
        f'<div class="cenario-topo"><span class="{situacao}">{esc(title)}</span>'
        f'<span class="label">{_num(ctx.hours(key))}h por semana</span></div>'
    ]
    if sub:
        parts.append(f'<p class="body-sm mut">{esc(sub)}</p>')
    parts.append(f'<p class="cenario-veredito">{_pill(verdict["status"])}<span>{esc(verdict["title"])}</span></p>')
    stat, line = _people_text(numbers)
    parts.append(
        f'<div class="numero"><p class="label">Gente a mais</p><p class="stat">{esc(stat)}</p>'
        f'<p class="stat-line">{esc(line)}</p></div>'
    )
    cost = _cost_text(numbers)
    if cost:
        lo, hi, line = cost
        value = f'<span class="nw">{esc(lo)}</span>' + (f' <span class="stat-ate">a {esc(hi)}</span>' if hi else "")
        parts.append(
            f'<div class="numero"><p class="label">Custo a mais</p><p class="stat">{value}</p>'
            f'<p class="stat-line">{esc(line)}</p></div>'
        )
    small = [(f"{_num(numbers['total_lost_hours'])}h", _lost_line(numbers))] + _extra_lines(numbers)
    dl = "".join(f"<div><dt>{esc(a)}</dt><dd>{esc(b)}</dd></div>" for a, b in small)
    parts.append(f'<dl class="miudos">{dl}</dl>')
    return f'<article class="bloco b-raised cenario" aria-label="{esc(title)}">{"".join(parts)}</article>'


def _html_scenarios(ctx) -> str:
    two = len(ctx.keys) == 2
    title = "Quanto custa, nas duas situações" if two else "Quanto custa"
    where = "Somando todas as lojas da rede." if ctx.multi else "Faixa de contratação e custo para a loja inteira."
    cards = "".join(_html_card(ctx, key, i == 0) for i, key in enumerate(ctx.keys))
    return (
        '<section class="secao" aria-labelledby="t-cenarios"><div class="secao-topo">'
        f'<h2 class="heading-md" id="t-cenarios">{title}</h2><p class="body-sm mut">{where}</p></div>'
        f'<div class="cenarios{" dois" if two else ""}">{cards}</div></section>'
    )


def _html_table(ctx, scenarios) -> str:
    keys = [k for k in ctx.keys if k in scenarios]
    labels = {k: ctx.label(k)[2] for k in keys}
    head = '<th scope="col">Setor</th><th scope="col">Hoje</th>' + "".join(f'<th scope="col">{esc(labels[k])}</th>' for k in keys)
    body = []
    for sector, line in _matched_rows(scenarios, keys):
        today = _people(sector["headcount"])
        posts = sector.get("min_simultaneous_staff")
        if posts:
            today += f'<span class="cel caption">{_num(posts)} postos ao mesmo tempo</span>'
        cells = [f'<th scope="row">{esc(_name(sector))}</th>', f'<td data-label="Hoje">{today}</td>']
        for key in keys:
            row = line.get(key)
            if row is None:
                cells.append(f'<td data-label="{esc(labels[key])}">Sem dado</td>')
                continue
            lost, hire, alert = _sector_cells(row)
            extra = f'<span class="alerta">{esc(alert)}</span>' if alert else ""
            cells.append(
                f'<td data-label="{esc(labels[key])}">{_pill(row["status"])}'
                f'<span class="cel">{esc(lost)}</span><span class="cel">{esc(hire)}</span>{extra}</td>'
            )
        body.append(f"<tr>{''.join(cells)}</tr>")
    klass = "tabela dois" if len(keys) == 2 else "tabela"
    return f'<table class="{klass}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _html_actions_list(actions) -> str:
    return "".join(f"<li><span>{esc(a)}</span></li>" for a in actions)


def _html_sectors(ctx) -> str:
    intro = (
        f"{_legend(ctx)} A conta de cada setor considera contratar só para ele. Por isso a soma dá o limite de cima."
    )
    if not ctx.multi:
        return (
            '<section class="secao" aria-labelledby="t-setores"><div class="secao-topo">'
            '<h2 class="heading-md" id="t-setores">Setor por setor</h2>'
            f'<p class="body-sm mut">{esc(intro)}</p></div>{_html_table(ctx, ctx.units[0][1])}</section>'
        )
    stores = []
    for name, scenarios in ctx.units:
        keys = [k for k in ctx.keys if k in scenarios]
        verdict = scenarios[keys[0]]["verdict"]
        lines = []
        for key in keys:
            result = scenarios[key]["result"]
            stat, _ = _people_text(result)
            cost = _cost_text(result)
            money = f", {cost[0]}" + (f" a {cost[1]}" if cost[1] else "") + " por mês" if cost else ""
            lines.append(f"<p><b>{esc(ctx.label(key)[2])}:</b> {esc(stat)} a mais{esc(money)}.</p>")
        actions = scenarios[keys[0]]["actions"]
        stores.append(
            f'<article class="bloco b-raised loja" aria-label="{esc(name)}">'
            f'<h3 class="heading-sm">{esc(name)}</h3>'
            f'<p class="cenario-veredito">{_pill(verdict["status"])}<span>{esc(verdict["title"])}</span></p>'
            f'<div class="loja-linhas">{"".join(lines)}</div>{_html_table(ctx, scenarios)}'
            f'<h4 class="label">O que fazer nesta loja</h4><ol class="acoes">{_html_actions_list(actions)}</ol></article>'
        )
    return (
        '<section class="secao" aria-labelledby="t-lojas"><div class="secao-topo">'
        '<h2 class="heading-md" id="t-lojas">Loja por loja</h2>'
        f'<p class="body-sm mut">{esc(intro)}</p></div>{"".join(stores)}</section>'
    )


def _actions_caption(ctx) -> str:
    if len(ctx.keys) == 2:
        return "Em ordem de prioridade, pela situação sem acordo coletivo."
    return "Em ordem de prioridade."


def _html_actions(ctx) -> str:
    if ctx.multi:
        return ""
    actions = ctx.units[0][1][ctx.keys[0]]["actions"]
    return (
        '<section class="bloco b-raised" aria-labelledby="t-acoes"><div class="secao-topo">'
        '<h2 class="heading-md" id="t-acoes">O que fazer</h2>'
        f'<p class="body-sm mut">{esc(_actions_caption(ctx))}</p></div>'
        f'<ol class="acoes">{_html_actions_list(actions)}</ol></section>'
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


def _html_how(ctx) -> str:
    paragraphs = "".join(f"<p><b>{esc(t)}</b> {esc(x)}</p>" for t, x in _how_items(ctx))
    not_counted = "".join(f"<li>{esc(x)}</li>" for x in _NOT_COUNTED)
    return (
        '<section class="bloco b-raised" aria-labelledby="t-como">'
        '<h2 class="heading-md" id="t-como">Como calculamos</h2>'
        '<p class="body-sm mut">É a mesma conta da calculadora gratuita da CD2. Uma estimativa gerencial, '
        'não um parecer jurídico. A convenção coletiva do seu sindicato prevalece.</p>'
        f'<div class="conta">{paragraphs}</div>'
        f'<h3 class="label">O que a conta não considera</h3><ul class="fora">{not_counted}</ul>'
        f'<p class="body-sm">{_a(METODOLOGIA_URL, "Ler a metodologia completa")}</p></section>'
    )


def _html_sources(ctx) -> str:
    items = _source_items(ctx)
    if not items:
        return ""
    lis = []
    for title, url, date in items:
        name = _a(url, title) if url else f"<b>{esc(title)}</b>"
        when = f'<span class="caption">{esc(date)}</span>' if date else ""
        lis.append(f"<li>{name}{when}</li>")
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
        f'<p><b>{_ARCHEO_TITLE}</b> {esc(_ARCHEO_TEXT)} {_a(link["archeo"], "Conhecer o Archeo")}</p>'
        f'<p><b>{_SITE_TITLE}</b> {esc(_SITE_TEXT)} {_a(link["site"], "Abrir a calculadora")}</p>'
        "</div></section>"
    )


def _html_bridges(ctx) -> str:
    link = _links(ctx)
    return (
        '<section class="pontes" aria-label="Também da CD2">'
        '<article class="bloco b-raised ponte"><span class="tag">Também da CD2</span>'
        f'<h2 class="heading-sm">{_VRVA_TITLE}</h2><p class="body-sm">{esc(_VRVA_TEXT)}</p>'
        f'{_a(link["vrva"], "Abrir a calculadora do VR e VA")}</article>'
        '<article class="bloco b-raised ponte"><span class="tag">Outra saída</span>'
        f'<h2 class="heading-sm">{_AGENTS_TITLE}</h2><p class="body-sm">{esc(_AGENTS_TEXT)}</p>'
        f'{_a(link["cd2"], "Conhecer os agentes de IA da CD2")}</article></section>'
    )


def _render_html(ctx) -> str:
    theme = ctx.theme
    values = {
        "THEME_ATTR": f' data-theme="{theme}"' if theme in ("light", "dark") else "",
        "COLOR_SCHEME": theme if theme in ("light", "dark") else "light dark",
        "TITLE": esc(SKILL_TITLE + (f": {ctx.profile_line}" if ctx.profile_line else "")),
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
            "TIMELINE": _html_timeline(ctx),
            "SCENARIOS": _html_scenarios(ctx),
            "SECTORS": _html_sectors(ctx),
            "ACTIONS": _html_actions(ctx),
            "INSIGHTS": _html_insights(ctx),
            "HOW": _html_how(ctx),
            "SOURCES": _html_sources(ctx),
            "COMMERCIAL": _html_commercial(ctx),
            "BRIDGES": _html_bridges(ctx),
        })
    for key in ("NOTICES", "TIMELINE", "SCENARIOS", "SECTORS", "ACTIONS", "INSIGHTS", "HOW", "SOURCES", "COMMERCIAL", "BRIDGES"):
        values.setdefault(key, "")
    return _fill(_template(), values)


# ---------------------------------------------------------------- textos

def _summary_line(ctx, key) -> str:
    numbers = ctx.numbers(key)
    title = ctx.label(key)[0]
    mn, mx = numbers["min_additional"], numbers["max_additional"]
    people = f"{_people(mx)} a mais" if mn == mx else f"De {_num(mn)} a {_num(mx)} pessoas a mais"
    lo, hi = format_brl_compact(numbers["min_monthly_cost"]), format_brl_compact(numbers["max_monthly_cost"])
    cost = lo if lo == hi else f"De {lo} a {hi}"
    return (
        f"{title} ({_num(ctx.hours(key))}h): {_num(numbers['total_lost_hours'])} horas a menos por semana. "
        f"{people}. {cost} por mês."
    )


def _red_lines(ctx, key):
    out = []
    for name, scenarios in ctx.units:
        if key not in scenarios:
            continue
        reds = _red_names(scenarios, key)
        if reds:
            where = f" em {name}" if name else ""
            out.append(f"No vermelho{where}: {calc.join_names(reds)}.")
    return out


def _alerts(ctx):
    out = []
    for key in ctx.keys:
        rule = ctx.rule(key)
        if rule.get("above_legal_limit"):
            out.append(f"Atenção: a jornada de {_num(rule['weekly_hours'])}h informada passa do limite de {_num(rule['legal_weekly_limit'])}h.")
        if rule.get("days_need_compensation"):
            out.append(f"Atenção: {_num(rule['max_work_days'])} dias por semana pedem regime compensatório.")
    return list(dict.fromkeys(out))


def _title_text(ctx) -> str:
    return SKILL_TITLE + (f": {ctx.profile_line}" if ctx.profile_line else "")


def _render_whatsapp(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked)
    lines = [f"*{_title_text(ctx)}*", ""]
    if ctx.errors:
        lines += ["Faltam dados para fazer a conta:"] + [f"- {e}" for e in ctx.errors] + ["", footer]
        return "\n".join(lines) + "\n"
    key = ctx.keys[0]
    lines += [f"*{ctx.verdict(key)['title']}*", ctx.output.get("deadline", "") + "."]
    if ctx.overridden:
        lines.append(_override_text(ctx))
    lines += _alerts(ctx)
    lines.append("")
    for k in ctx.keys:
        lines.append(_summary_line(ctx, k))
        lines += _red_lines(ctx, k)
        lines.append("")
    if ctx.multi:
        lines.append("*Primeiro passo em cada loja*")
        for name, scenarios in ctx.units:
            keys = [k for k in ctx.keys if k in scenarios]
            actions = scenarios[keys[0]]["actions"] if keys else []
            if actions:
                lines.append(f"- {name}: {actions[0]}")
        lines.append("")
    else:
        actions = ctx.units[0][1][key]["actions"][:3]
        lines.append("*O que fazer primeiro*")
        lines += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
        lines.append("")
    if ctx.insights:
        lines.append("*Leitura da CD2*")
        lines += [f"- {i}" for i in ctx.insights]
        lines.append("")
    lines += ["Faça a conta da sua loja, de graça e sem cadastro:", _links(ctx)["site"], "", footer]
    return "\n".join(lines) + "\n"


_MD_SPECIAL = re.compile(r"([\\`*_\[\]|#<>])")


def _md(text) -> str:
    """Texto de fora (nomes, insights) seguro em Markdown: sem HTML cru e sem quebrar tabela."""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _MD_SPECIAL.sub(r"\\\1", text).replace("\n", " ")


def _md_link(text, url) -> str:
    return f"[{_md(text)}]({url})" if url else _md(text)


def _md_table(ctx, scenarios):
    keys = [k for k in ctx.keys if k in scenarios]
    labels = [ctx.label(k)[2] for k in keys]
    out = ["| Setor | Hoje | " + " | ".join(labels) + " |", "|" + "---|" * (2 + len(keys))]
    for sector, line in _matched_rows(scenarios, keys):
        cells = [_md(_name(sector)), _people(sector["headcount"])]
        for key in keys:
            row = line.get(key)
            if row is None:
                cells.append("Sem dado")
                continue
            lost, hire, alert = _sector_cells(row)
            cells.append(f"{STATUS_LABEL[row['status']]}: {lost}, {hire[0].lower() + hire[1:]}." + (f" {alert}" if alert else ""))
        out.append("| " + " | ".join(cells) + " |")
    return out


def _render_markdown(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked)
    lines = [f"# {_md(_title_text(ctx))}", ""]
    if ctx.errors:
        lines += ["## Faltam dados para fazer a conta", ""] + [f"- {_md(e)}" for e in ctx.errors]
        lines += ["", "Corrija e rode a conta de novo. Nenhum número foi calculado.", "", "---", "", footer]
        return "\n".join(lines) + "\n"
    key = ctx.keys[0]
    lines += [f"## {ctx.verdict(key)['title']}", ""]
    sub = _hero_sub(ctx)
    if sub:
        lines += [sub, ""]
    lines += [f"{ctx.output.get('deadline', '')}. {_SMALL_BUSINESS}", ""]
    if ctx.today:
        lines += [f"Calculado em {_date(ctx.today)}. Regras conferidas em {ctx.checked}.", ""]
    if ctx.overridden:
        lines += [f"> **{_override_text(ctx)}** {_override_detail(ctx)}", ""]
    for alert in _alerts(ctx):
        lines += [f"> {alert}", ""]

    lines += ["## Quanto custa" + (", nas duas situações" if len(ctx.keys) == 2 else ""), ""]
    for k in ctx.keys:
        title, sub, _ = ctx.label(k)
        numbers = ctx.numbers(k)
        verdict = ctx.verdict(k)
        lines += [f"### {title}, {_num(ctx.hours(k))}h por semana", ""]
        if sub:
            lines += [sub, ""]
        stat, line = _people_text(numbers)
        lines.append(f"- **Situação:** {STATUS_LABEL[verdict['status']]}. {verdict['title']}.")
        lines.append(f"- **Gente a mais:** {_join_stat(stat, line)}")
        cost = _cost_text(numbers)
        if cost:
            value = cost[0] + (f" a {cost[1]}" if cost[1] else "")
            lines.append(f"- **Custo a mais:** {value} {cost[2]}")
        lines.append(f"- **Horas a menos:** {_num(numbers['total_lost_hours'])}h {_lost_line(numbers)}")
        for value, text in _extra_lines(numbers):
            lines.append(f"- **{value}** {text}")
        lines.append("")

    if ctx.multi:
        lines += ["## Loja por loja", "", _md(_legend(ctx)), ""]
        for name, scenarios in ctx.units:
            keys = [k for k in ctx.keys if k in scenarios]
            verdict = scenarios[keys[0]]["verdict"]
            lines += [f"### {_md(name)}", "", f"**{STATUS_LABEL[verdict['status']]}.** {verdict['title']}.", ""]
            lines += _md_table(ctx, scenarios) + ["", "O que fazer nesta loja:", ""]
            lines += [f"{i}. {_md(a)}" for i, a in enumerate(scenarios[keys[0]]["actions"], 1)] + [""]
    else:
        lines += ["## Setor por setor", "", _md(_legend(ctx)), ""] + _md_table(ctx, ctx.units[0][1]) + [""]
        lines += ["## O que fazer", "", _actions_caption(ctx), ""]
        lines += [f"{i}. {_md(a)}" for i, a in enumerate(ctx.units[0][1][key]["actions"], 1)] + [""]

    if ctx.insights:
        lines += ["## Leitura da CD2", ""] + [f"- {_md(i)}" for i in ctx.insights] + [""]

    lines += ["## Como calculamos", "", "É a mesma conta da calculadora gratuita da CD2. Uma estimativa gerencial, não um parecer jurídico.", ""]
    lines += [f"- **{t}** {_md(x)}" for t, x in _how_items(ctx)]
    lines += ["", "O que a conta não considera:", ""] + [f"- {x}" for x in _NOT_COUNTED]
    lines += ["", f"[Ler a metodologia completa]({METODOLOGIA_URL})", ""]

    sources = _source_items(ctx)
    if sources:
        lines += ["## Fontes", ""]
        lines += [f"- {_md_link(t, u)}" + (f", {_md(d)}" if d else "") for t, u, d in sources] + [""]

    link = _links(ctx)
    lines += [
        f"## {_COMMERCIAL_TITLE}", "", _COMMERCIAL_TEXT, "",
        f"- Fale com a CD2 no WhatsApp: {link['whatsapp']}",
        f"- Conheça a CD2: {link['cd2']}",
        f"- {_ARCHEO_TITLE} {_ARCHEO_TEXT} {link['archeo']}",
        f"- {_SITE_TITLE} {_SITE_TEXT} {link['site']}",
        f"- {_VRVA_TITLE}: {_VRVA_TEXT} {link['vrva']}",
        f"- {_AGENTS_TITLE}: {_AGENTS_TEXT}",
        "", "---", "", footer,
    ]
    return "\n".join(lines) + "\n"


def _cell(value) -> str:
    """Célula de texto do CSV, protegida contra fórmula (=, +, -, @) ao abrir no Excel."""
    text = str(value)
    if text and text[0] in "=+-@\t\r":
        text = "'" + text
    return brand.csv_cell(text)


def _csv_number(value) -> str:
    return str(int(value)) if float(value).is_integer() else _fixed(value, 1)


def _render_csv(ctx) -> str:
    footer = brand.footer_text(REGRA, ctx.checked).split("\n")
    if ctx.errors:
        rows = [_cell("Faltam dados para fazer a conta")] + [_cell(e) for e in ctx.errors]
        rows += [""] + [_cell(line) for line in footer]
        return "﻿" + "\r\n".join(rows) + "\r\n"
    headers = ["Situação", "Setor", "Status", "Pessoas hoje", "Horas a menos por semana", "Pessoas a mais", "Custo mensal a mais"]
    if ctx.multi:
        headers = ["Loja"] + headers
    rows = [";".join(_cell(h) for h in headers)]
    for name, scenarios in ctx.units:
        for key in [k for k in ctx.keys if k in scenarios]:
            label = ctx.label(key)[2]
            for r in scenarios[key]["result"]["sectors"]:
                cells = [_cell(label), _cell(_name(r["sector"])), _cell(STATUS_LABEL[r["status"]]),
                         _csv_number(r["sector"]["headcount"]), _csv_number(r["lost_hours"]),
                         _csv_number(r["additional_headcount"]), str(_round(r["additional_monthly_cost"]))]
                if ctx.multi:
                    cells = [_cell(name)] + cells
                rows.append(";".join(cells))
    rows.append("")
    rows += [_cell(_summary_line(ctx, k)) for k in ctx.keys]
    if ctx.overridden:
        rows.append(_cell(_override_text(ctx)))
    rows += [_cell(a) for a in _alerts(ctx)]
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
    parser = argparse.ArgumentParser(description="Entrega da skill fim-escala-6x1 (CD2 Tech).")
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
    if not isinstance(output, dict) or not ({"errors", "scenarios", "stores"} & set(output)):
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
