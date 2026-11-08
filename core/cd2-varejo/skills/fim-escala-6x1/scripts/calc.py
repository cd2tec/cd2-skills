#!/usr/bin/env python3
"""Motor de calculo da skill fim-escala-6x1 (fim da escala 6x1, EC 141/2026).

Port fiel do motor TypeScript da calculadora gratuita da CD2 Tech
(core/calculator.ts, verdict.ts, actions.ts, deadline.ts). Mesma logica,
inclusive round_up = ceil(x - 1e-9), a ordenacao dos setores por horas
perdidas e a semantica `||` dos overrides (0 ou ausente = sem override).

Uso:
    python3 calc.py --input dados.json
    cat dados.json | python3 calc.py

So biblioteca padrao (Python 3.10+).
"""
import argparse
import copy
import json
import math
import sys
from datetime import date
from pathlib import Path

# brand.py fica ao lado deste arquivo no pacote final (o sync copia). No
# repositorio (layout core) ele mora em cd2-varejo/shared/scripts.
_HERE = Path(__file__).resolve().parent
_PATHS = [_HERE]
if len(_HERE.parents) > 2:
    _PATHS.append(_HERE.parents[2] / "shared" / "scripts")
for _p in _PATHS:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))

from brand import format_date_br  # noqa: E402

REFERENCES = _HERE.parent / "references"
SKILL = "fim-escala-6x1"
SCENARIO_ORDER = ("without_agreement", "with_agreement")


# ---------------------------------------------------------------- parametros

def _find_reference(name: str) -> Path:
    # references/ ao lado de scripts/, ou tudo na mesma pasta (conhecimento do GPT).
    for path in (REFERENCES / name, _HERE / name):
        if path.is_file():
            return path
    raise FileNotFoundError(name)


def _read_json(name: str) -> dict:
    with open(_find_reference(name), encoding="utf-8") as fh:
        return json.load(fh)


def load_params(override=None):
    """Devolve (legal_params, assumptions, overridden_keys).

    `override` aceita chaves de topo de legal-params.json e assumptions.json;
    `phases` entra inteiro.
    """
    legal = _read_json("legal-params.json")
    assumptions = _read_json("assumptions.json")
    overridden = []
    for key, value in (override or {}).items():
        if key in legal:
            legal[key] = copy.deepcopy(value)
        elif key in assumptions:
            assumptions[key] = value
        else:
            raise ValueError(f"parametro desconhecido: {key}")
        overridden.append(key)
    return legal, assumptions, overridden


# ------------------------------------------------------------------- calculo

def round_up(value: float) -> int:
    return math.ceil(value - 1e-9)


def _sum(items, pick):
    total = 0
    for item in items:
        total += pick(item)
    return total


def _active_phase(today: str, params: dict) -> dict:
    started = [p for p in params["phases"] if p["starts_on"] <= today]
    return started[-1] if started else params["phases"][0]


def _build_rule(weekly_hours, max_days, limit_hours, limit_days, overrides=None) -> dict:
    overrides = overrides or {}
    # semantica `||` do JS: 0 e None valem como "sem override"
    weekly = overrides.get("weekly_hours_override") or weekly_hours
    days = overrides.get("max_work_days_override") or max_days
    return {
        "weekly_hours": weekly,
        "max_work_days": days,
        "legal_weekly_limit": limit_hours,
        "above_legal_limit": weekly > limit_hours,
        "days_need_compensation": days > limit_days,
    }


def rule_for_date(date_iso: str, params: dict, overrides=None) -> dict:
    if date_iso < params["phases"][0]["starts_on"]:
        cur = params["current"]
        return _build_rule(cur["weekly_hours"], cur["max_work_days"], cur["weekly_hours"], cur["max_work_days"], overrides)
    phase = _active_phase(date_iso, params)
    return _build_rule(phase["weekly_hours"], phase["max_work_days"], phase["weekly_hours"], phase["max_work_days"], overrides)


def available_scenarios(today: str, params: dict, overrides=None) -> list:
    if (overrides or {}).get("weekly_hours_override"):
        return ["with_agreement"]
    if today >= params["phases"][-1]["starts_on"]:
        return ["without_agreement"]
    return ["without_agreement", "with_agreement"]


def rule_for_scenario(scenario: str, params: dict, overrides=None, today=None) -> dict:
    phase = _active_phase(today if today is not None else params["phases"][0]["starts_on"], params)
    without = min(phase["weekly_hours"], params["daily_hours_limit"] * phase["max_work_days"])
    hours = phase["weekly_hours"] if scenario == "with_agreement" else without
    return _build_rule(hours, phase["max_work_days"], phase["weekly_hours"], phase["max_work_days"], overrides)


def days_until(date_iso: str, today: str) -> int:
    return (date.fromisoformat(date_iso) - date.fromisoformat(today)).days


def calc_sector(sector: dict, store: dict, rule: dict, assumptions: dict) -> dict:
    headcount = sector["headcount"]
    salary = sector["avg_monthly_salary"]
    current_hours = sector["current_weekly_hours"]
    hours = rule["weekly_hours"]

    lost_hours = headcount * max(0, current_hours - hours)
    person_equivalent = lost_hours / hours
    needed_by_hours = max(headcount, round_up((headcount * current_hours) / hours))

    shifts_per_day = None
    needed_by_days = None
    if sector.get("min_simultaneous_staff"):
        shifts_per_day = round_up(store["hours_open_per_day"] / (hours / rule["max_work_days"]))
        person_days = store["days_open_per_week"] * sector["min_simultaneous_staff"] * shifts_per_day
        needed_by_days = round_up(person_days / rule["max_work_days"])

    needed = max(needed_by_hours, needed_by_days or 0)
    additional_headcount = max(0, needed - headcount)
    monthly_cost_per_head = salary * (1 + store["payroll_charges_factor"])
    additional_monthly_cost = additional_headcount * monthly_cost_per_head
    days_gap = max(0, (needed_by_days or 0) - headcount)

    hourly_rate = salary / (hours * assumptions["overtime_divisor_per_weekly_hour"])
    overtime_monthly_cost = lost_hours * assumptions["weeks_per_month"] * hourly_rate * assumptions["overtime_multiplier"]

    status = "green"
    if person_equivalent >= assumptions["red_person_equivalent"] or days_gap > 0:
        status = "red"
    elif person_equivalent >= assumptions["amber_person_equivalent"]:
        status = "amber"
    elif rule["above_legal_limit"] or rule["days_need_compensation"]:
        status = "amber"

    return {
        "sector": sector,
        "lost_hours": lost_hours,
        "person_equivalent": person_equivalent,
        "needed_by_hours": needed_by_hours,
        "shifts_per_day": shifts_per_day,
        "needed_by_days": needed_by_days,
        "additional_headcount": additional_headcount,
        "monthly_cost_per_head": monthly_cost_per_head,
        "additional_monthly_cost": additional_monthly_cost,
        "additional_annual_cost": additional_monthly_cost * 12,
        "overtime_monthly_cost": overtime_monthly_cost,
        "status": status,
        "days_gap": days_gap,
    }


def calc_store(store: dict, sectors: list, rule: dict, assumptions: dict) -> dict:
    hours = rule["weekly_hours"]
    results = [calc_sector(s, store, rule, assumptions) for s in sectors if s["headcount"] > 0]
    # sorted() e estavel e reverse=True preserva a ordem dos empatados, como o sort do JS
    results.sort(key=lambda r: r["lost_hours"], reverse=True)

    total_headcount = _sum(results, lambda r: r["sector"]["headcount"])
    total_person_hours = _sum(results, lambda r: r["sector"]["headcount"] * r["sector"]["current_weekly_hours"])
    total_lost_hours = _sum(results, lambda r: r["lost_hours"])
    monthly_payroll = _sum(results, lambda r: r["sector"]["headcount"] * r["monthly_cost_per_head"])

    max_additional = _sum(results, lambda r: r["additional_headcount"])
    max_monthly_cost = _sum(results, lambda r: r["additional_monthly_cost"])
    days_gap = _sum(results, lambda r: r["days_gap"])
    store_floor = max(0, round_up(total_person_hours / hours) - total_headcount)
    min_additional = min(max_additional, max(store_floor, days_gap))

    gap_cost = _sum(results, lambda r: r["days_gap"] * r["monthly_cost_per_head"])
    average_cost = monthly_payroll / total_headcount if total_headcount else 0
    range_cost = gap_cost + max(0, min_additional - days_gap) * average_cost
    min_monthly_cost = max_monthly_cost if min_additional == max_additional else min(max_monthly_cost, range_cost)

    def share(cost):
        return (cost / monthly_payroll) * 100 if monthly_payroll else 0

    cap = (store.get("overrides") or {}).get("overtime_cap_hours_per_day")
    if cap is None:
        cap = assumptions["default_overtime_cap_hours_per_day"]

    counts = {"red": 0, "amber": 0, "green": 0}
    for r in results:
        counts[r["status"]] += 1

    if total_headcount:
        hour_cost_increase_pct = (
            _sum(results, lambda r: r["sector"]["headcount"] * max(r["sector"]["current_weekly_hours"], hours))
            / (total_headcount * hours)
            - 1
        ) * 100
    else:
        hour_cost_increase_pct = 0

    return {
        "rule": rule,
        "sectors": results,
        "total_headcount": total_headcount,
        "total_person_hours": total_person_hours,
        "total_lost_hours": total_lost_hours,
        "person_equivalent": total_lost_hours / hours,
        "monthly_payroll": monthly_payroll,
        "min_additional": min_additional,
        "max_additional": max_additional,
        "min_monthly_cost": min_monthly_cost,
        "max_monthly_cost": max_monthly_cost,
        "min_annual_cost": min_monthly_cost * 12,
        "max_annual_cost": max_monthly_cost * 12,
        "min_payroll_pct": share(min_monthly_cost),
        "max_payroll_pct": share(max_monthly_cost),
        "hour_cost_increase_pct": hour_cost_increase_pct,
        "overtime_monthly_cost": _sum(results, lambda r: r["overtime_monthly_cost"]),
        "overtime_above_cap": any(
            max(0, r["sector"]["current_weekly_hours"] - hours) / rule["max_work_days"] > cap for r in results
        ),
        "counts": counts,
    }


# ------------------------------------------------- textos (src/i18n/pt-BR.ts)

def _plural(count, singular, plural):
    return singular if count == 1 else plural


def _verdict_above_limit(hours, limit):
    return f"Cuidado: {hours}h passa do limite de {limit}h"


def _verdict_compensation(days):
    return f"Cuidado: {days} dias por semana pedem regime compensatório"


def _verdict_red(count):
    return f"Atenção: {count} {_plural(count, 'setor', 'setores')} no vermelho"


def _verdict_amber(count):
    return f"Cuidado: {count} {_plural(count, 'setor pede', 'setores pedem')} ajuste"


_VERDICT_GREEN = "Tranquilo: dá para ajustar a escala"

_ACTION_COMPENSATION = (
    "Mais de 5 dias por semana só com regime compensatório em convenção ou acordo coletivo. "
    "Confirme com seu advogado."
)
_ACTION_BUTCHER = "Açougueiro é difícil de achar: comece a procurar agora."
_ACTION_SUNDAY = (
    "Monte a escala pensando no domingo: a regra prefere uma das folgas nesse dia, e é dia de loja cheia."
)
_ACTION_UNNAMED = "Setor sem nome"


def _action_above_limit(hours, limit):
    return (
        f"A jornada de {hours}h que você informou passa do limite de {limit}h. "
        "Confirme com seu advogado se a sua convenção permite isso."
    )


def _action_union(date_text, end, without, with_agreement):
    prefix = f" antes de {date_text}" if date_text else ""
    return (
        f"Procure seu sindicato{prefix}. Com acordo coletivo dá para trabalhar 8h24 por dia até {end}. "
        f"Sem ele, pela nossa leitura do texto, o limite é 8h por dia: {without}h a menos por semana, "
        f"em vez de {with_agreement}h."
    )


def _action_train(minimum, maximum):
    return (
        "Treine gente para cobrir mais de um setor. É isso que aproxima você de "
        f"{minimum} {_plural(minimum, 'contratação', 'contratações')}, e não de {maximum}."
    )


def _deadline_many(days, date_text):
    return f"Faltam {days} dias para a nova regra ({date_text})"


# --------------------------------------------------------- veredito e acoes

def verdict(store_result: dict) -> dict:
    rule, counts = store_result["rule"], store_result["counts"]
    if rule["above_legal_limit"]:
        return {"status": "amber", "title": _verdict_above_limit(rule["weekly_hours"], rule["legal_weekly_limit"])}
    if rule["days_need_compensation"]:
        return {"status": "amber", "title": _verdict_compensation(rule["max_work_days"])}
    if counts["red"]:
        return {"status": "red", "title": _verdict_red(counts["red"])}
    if counts["amber"]:
        return {"status": "amber", "title": _verdict_amber(counts["amber"])}
    return {"status": "green", "title": _VERDICT_GREEN}


def join_names(names: list) -> str:
    if len(names) < 2:
        return names[0] if names else ""
    return f"{', '.join(names[:-1])} e {names[-1]}"


def _mid_sentence(names):
    return join_names([n.lower() for n in names])


def _opening(names):
    text = _mid_sentence(names)
    return text[:1].upper() + text[1:]


def build_actions(store_result: dict, comparison=None, today: str = "", params=None) -> list:
    """`comparison` = {"without": StoreResult, "with": StoreResult}. `params` padrao: legal-params.json."""
    if params is None:
        params = _read_json("legal-params.json")

    def names(status):
        return [s["sector"].get("name") or _ACTION_UNNAMED for s in store_result["sectors"] if s["status"] == status]

    def is_butcher(name):
        return "açougue" in name.lower()

    red, amber, green = names("red"), names("amber"), names("green")
    out = []
    rule = store_result["rule"]

    if rule["above_legal_limit"]:
        out.append(_action_above_limit(rule["weekly_hours"], rule["legal_weekly_limit"]))
    if rule["days_need_compensation"]:
        out.append(_ACTION_COMPENSATION)
    if comparison and comparison["without"]["total_lost_hours"] > comparison["with"]["total_lost_hours"]:
        first, second = params["phases"][0]["starts_on"], params["phases"][1]["starts_on"]
        out.append(
            _action_union(
                format_date_br(first) if today < first else None,
                format_date_br(second),
                comparison["without"]["total_lost_hours"],
                comparison["with"]["total_lost_hours"],
            )
        )
    if red:
        out.append(f"Comece a contratar para {_mid_sentence(red)}.")
    if any(is_butcher(n) for n in red + amber):
        out.append(_ACTION_BUTCHER)
    review = [n for n in amber if not is_butcher(n)]
    if review:
        out.append(f"{_opening(review)}: reveja a escala e acompanhe de perto.")
    if store_result["min_additional"] < store_result["max_additional"]:
        out.append(_action_train(store_result["min_additional"], store_result["max_additional"]))
    if green:
        out.append(f"{_opening(green)} {_plural(len(green), 'perde', 'perdem')} pouco: ajuste a escala antes de contratar.")
    out.append(_ACTION_SUNDAY)
    return out


def deadline_text(params: dict, today: str) -> str:
    first, last = params["phases"][0], params["phases"][-1]
    start, end = format_date_br(first["starts_on"]), format_date_br(last["starts_on"])
    days = days_until(first["starts_on"], today)
    if days > 1:
        return _deadline_many(days, start)
    if days == 1:
        return f"Falta 1 dia para a nova regra ({start})"
    if today < last["starts_on"]:
        return f"Regra em vigor desde {start}. As 40h para todos chegam em {end}."
    return f"Regra em vigor desde {end}"


# ---------------------------------------------------------------- validacao

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_int(value) -> bool:
    return _is_number(value) and float(value).is_integer()


def _valid_date(value) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_overrides(overrides, prefix, errors):
    if overrides is None:
        return
    if not isinstance(overrides, dict):
        errors.append(f"{prefix}overrides precisa ser um objeto.")
        return
    value = overrides.get("weekly_hours_override")
    if value is not None and not (_is_number(value) and 0 <= value <= 168):
        errors.append(f"{prefix}weekly_hours_override precisa ser um número maior ou igual a zero (0 ou vazio usa a regra geral).")
    value = overrides.get("max_work_days_override")
    if value is not None and not (_is_int(value) and 0 <= value <= 7):
        errors.append(f"{prefix}max_work_days_override precisa ser um número inteiro de 1 a 7 (0 ou vazio usa a regra geral).")
    cap = overrides.get("overtime_cap_hours_per_day")
    if cap is not None and not (_is_number(cap) and cap >= 0):
        errors.append(f"{prefix}overtime_cap_hours_per_day precisa ser um número maior ou igual a zero.")


def _validate_store_block(store, sectors, overrides, prefix, errors):
    if not isinstance(store, dict):
        errors.append(f"{prefix}store precisa ser um objeto com dias e horas de funcionamento.")
        store = {}
    else:
        days = store.get("days_open_per_week")
        if not (_is_int(days) and days in (6, 7)):
            errors.append(f"{prefix}Dias abertos por semana (days_open_per_week) precisa ser 6 ou 7.")
        hours = store.get("hours_open_per_day")
        if not (_is_number(hours) and 0 < hours <= 24):
            errors.append(f"{prefix}Horas abertas por dia (hours_open_per_day) precisa ser um número maior que zero e até 24.")
        factor = store.get("payroll_charges_factor")
        if factor is not None and not (_is_number(factor) and factor >= 0):
            errors.append(f"{prefix}Encargos (payroll_charges_factor) precisa ser um número maior ou igual a zero, como 0.7.")
        _validate_overrides(store.get("overrides"), prefix, errors)
    _validate_overrides(overrides, prefix, errors)

    if not isinstance(sectors, list) or not sectors:
        errors.append(f"{prefix}sectors precisa ser uma lista com pelo menos um setor.")
        return
    any_people = False
    for i, sec in enumerate(sectors, start=1):
        if not isinstance(sec, dict):
            errors.append(f"{prefix}Setor {i}: precisa ser um objeto.")
            continue
        name = sec.get("name")
        label = f"{prefix}Setor {i} ({name})" if isinstance(name, str) and name.strip() else f"{prefix}Setor {i}"
        head = sec.get("headcount")
        head_ok = _is_int(head) and head >= 0
        if not head_ok:
            errors.append(f"{label}: pessoas precisa ser um número inteiro maior ou igual a zero.")
        elif head > 0:
            any_people = True
        salary = sec.get("avg_monthly_salary")
        if not _is_number(salary) or salary < 0:
            errors.append(f"{label}: salário médio precisa ser um número maior ou igual a zero.")
        elif head_ok and head > 0 and salary <= 0:
            errors.append(f"{label}: salário médio precisa ser maior que zero.")
        posts = sec.get("min_simultaneous_staff")
        if posts is not None and not (_is_int(posts) and posts >= 0):
            errors.append(f"{label}: postos abertos ao mesmo tempo precisa ser um número inteiro maior ou igual a zero.")
        if "current_work_days" in sec:
            cwd = sec["current_work_days"]
            if not (_is_int(cwd) and 1 <= cwd <= 7):
                errors.append(f"{label}: dias de trabalho atuais precisa ser um número inteiro de 1 a 7.")
        cur = sec.get("current_weekly_hours", 44)
        if cur is None or not (_is_number(cur) and 0 < cur <= 168):
            errors.append(f"{label}: jornada semanal atual precisa ser um número maior que zero.")
    if not any_people and not errors:
        errors.append(f"{prefix}Preencha as pessoas de pelo menos um setor.")


_POSITIVE_PARAMS = ("weeks_per_month", "overtime_divisor_per_weekly_hour", "daily_hours_limit")
_NON_NEGATIVE_PARAMS = (
    "default_charges_factor", "overtime_multiplier", "default_overtime_cap_hours_per_day",
    "red_person_equivalent", "amber_person_equivalent",
)
_BOOL_PARAMS = ("sunday_rest_preferred", "salary_reduction_allowed", "collective_bargaining_override",
                "verified_against_official_text")


def _validate_rule_block(block, label, errors):
    if not isinstance(block, dict):
        errors.append(f"params_override: {label} precisa ser um objeto.")
        return
    hours = block.get("weekly_hours")
    if not (_is_number(hours) and 0 < hours <= 168):
        errors.append(f"params_override: {label}.weekly_hours precisa ser um número maior que zero.")
    days = block.get("max_work_days")
    if not (_is_int(days) and 1 <= days <= 7):
        errors.append(f"params_override: {label}.max_work_days precisa ser um número inteiro de 1 a 7.")


def _validate_params_override(po, errors):
    for key in _POSITIVE_PARAMS:
        if key in po and not (_is_number(po[key]) and po[key] > 0):
            errors.append(f"params_override: {key} precisa ser um número maior que zero.")
    for key in _NON_NEGATIVE_PARAMS:
        if key in po and not (_is_number(po[key]) and po[key] >= 0):
            errors.append(f"params_override: {key} precisa ser um número maior ou igual a zero.")
    for key in _BOOL_PARAMS:
        if key in po and not isinstance(po[key], bool):
            errors.append(f"params_override: {key} precisa ser verdadeiro ou falso.")
    for key in ("version", "source"):
        if key in po and not (isinstance(po[key], str) and po[key].strip()):
            errors.append(f"params_override: {key} precisa ser um texto.")
    if "current" in po:
        _validate_rule_block(po["current"], "current", errors)
    if "phases" in po:
        phases = po["phases"]
        if not isinstance(phases, list) or len(phases) < 2:
            errors.append("params_override: phases precisa ser uma lista com pelo menos 2 fases.")
            return
        starts = []
        for i, phase in enumerate(phases, start=1):
            label = f"phases[{i}]"
            _validate_rule_block(phase, label, errors)
            ok = isinstance(phase, dict) and _valid_date(phase.get("starts_on"))
            if not ok:
                errors.append(f"params_override: {label}.starts_on precisa ser uma data no formato AAAA-MM-DD.")
            else:
                starts.append(phase["starts_on"])
        if len(starts) == len(phases) and starts != sorted(starts):
            errors.append("params_override: phases precisa estar em ordem de data de início.")


def validate(data) -> list:
    """Erros de entrada, em portugues. Lista vazia = entrada valida."""
    errors = []
    if not isinstance(data, dict):
        return ["A entrada precisa ser um objeto JSON."]
    today = data.get("today")
    if today is not None and not _valid_date(today):
        errors.append("today precisa ser uma data no formato AAAA-MM-DD.")
    po = data.get("params_override")
    if po is not None:
        if not isinstance(po, dict):
            errors.append("params_override precisa ser um objeto.")
        else:
            try:
                load_params(po)
            except ValueError as exc:
                errors.append(f"params_override: {exc}.")
            else:
                _validate_params_override(po, errors)
    if "stores" in data:
        _validate_overrides(data.get("overrides"), "", errors)
        stores = data["stores"]
        if not isinstance(stores, list) or not stores:
            errors.append("stores precisa ser uma lista com pelo menos uma loja.")
        else:
            for i, item in enumerate(stores, start=1):
                if not isinstance(item, dict):
                    errors.append(f"Loja {i}: precisa ser um objeto.")
                    continue
                name = item.get("name")
                prefix = f"{name}: " if isinstance(name, str) and name.strip() else f"Loja {i}: "
                _validate_store_block(item.get("store"), item.get("sectors"), item.get("overrides"), prefix, errors)
    else:
        _validate_store_block(data.get("store"), data.get("sectors"), data.get("overrides"), "", errors)
    return errors


# --------------------------------------------------------------------- run

def _jsonable(value):
    """Inteiros-valorados viram int, como o JS os serializa (88, nao 88.0)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _normalize_sector(sec: dict) -> dict:
    out = dict(sec)
    out.setdefault("name", "")
    out["min_simultaneous_staff"] = sec.get("min_simultaneous_staff") or None
    out.setdefault("current_weekly_hours", 44)
    out.setdefault("current_work_days", 6)
    return out


def _run_store(store_in, sectors_in, overrides, today, params, assumptions) -> dict:
    merged = {**(store_in.get("overrides") or {}), **(overrides or {})}
    store = dict(store_in)
    if store.get("payroll_charges_factor") is None:
        store["payroll_charges_factor"] = assumptions["default_charges_factor"]
    store["overrides"] = merged or None
    sectors = [_normalize_sector(s) for s in sectors_in]
    scenarios = available_scenarios(today, params, merged)

    def at(scenario):
        return calc_store(store, sectors, rule_for_scenario(scenario, params, merged, today), assumptions)

    comparison = {"without": at("without_agreement"), "with": at("with_agreement")} if len(scenarios) == 2 else None
    out = {}
    for scenario in scenarios:
        result = comparison["without" if scenario == "without_agreement" else "with"] if comparison else at(scenario)
        out[scenario] = {
            "result": result,
            "verdict": verdict(result),
            "actions": build_actions(result, comparison, today, params),
        }
    return out


def run(data: dict) -> dict:
    params, assumptions, overridden = load_params(data.get("params_override"))
    today = data.get("today") or date.today().isoformat()
    top_overrides = data.get("overrides")

    output = {
        "skill": SKILL,
        "params_version": params["version"] + ("+override" if overridden else ""),
        "checked_at": params["version"],
        "overridden": overridden,
        "today": today,
        "deadline": deadline_text(params, today),
    }
    if "stores" in data:
        stores = []
        for i, item in enumerate(data["stores"], start=1):
            scenarios = _run_store(
                item["store"], item["sectors"], item.get("overrides", top_overrides), today, params, assumptions
            )
            stores.append({"name": item.get("name") or f"Loja {i}", "scenarios": scenarios})
        output["stores"] = stores
        output["network"] = _network(stores)
    else:
        output["scenarios"] = _run_store(data["store"], data["sectors"], top_overrides, today, params, assumptions)
    return _jsonable(output)


def _network(stores: list) -> dict:
    """Soma da rede por situação.

    Loja sem a situação (por exemplo, com convenção própria e só a situação "com acordo")
    entra com a única situação que tem, para a rede não perder a loja. Os nomes dessas
    lojas vão em `stores_substituted`, para a entrega avisar.
    """
    fields = ("min_additional", "max_additional", "min_monthly_cost", "max_monthly_cost",
              "min_annual_cost", "max_annual_cost", "total_lost_hours")
    network = {}
    for scenario in SCENARIO_ORDER:
        if not any(scenario in s["scenarios"] for s in stores):
            continue
        results, substituted = [], []
        for s in stores:
            if scenario in s["scenarios"]:
                results.append(s["scenarios"][scenario]["result"])
            elif s["scenarios"]:
                own = next(k for k in SCENARIO_ORDER if k in s["scenarios"])
                results.append(s["scenarios"][own]["result"])
                substituted.append(s["name"])
        entry = {f: _sum(results, lambda r, f=f: r[f]) for f in fields}
        entry["counts"] = {k: _sum(results, lambda r, k=k: r["counts"][k]) for k in ("red", "amber", "green")}
        entry["stores_counted"] = len(results)
        entry["stores_substituted"] = substituted
        network[scenario] = entry
    return network


# --------------------------------------------------------------------- CLI

def _fail(errors) -> int:
    print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Motor de cálculo do fim da escala 6x1 (CD2 Tech).")
    parser.add_argument("--input", help="arquivo JSON de entrada (padrão: stdin)")
    args = parser.parse_args(argv)
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        if args.input:
            with open(args.input, encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
    except OSError as exc:
        return _fail([f"Não consegui ler o arquivo de entrada: {exc.strerror or exc}."])
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return _fail([f"JSON inválido: {exc}."])
    try:
        errors = validate(data)
        if errors:
            return _fail(errors)
        output = json.dumps(run(data), ensure_ascii=False, indent=2)
    except Exception as exc:  # rede de seguranca: a validacao e quem deve barrar entrada ruim
        return _fail([f"Erro inesperado ao calcular: {type(exc).__name__}."])
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
