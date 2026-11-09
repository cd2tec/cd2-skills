#!/usr/bin/env python3
"""Motor de calculo da skill custo-vrva (VR e VA, Decreto 12.712/2025).

Port fiel do motor TypeScript da calculadora gratuita de VR e VA da CD2 Tech
(core/calculator.ts, src/lib/actions.ts, src/lib/validation.ts). Mesma logica,
inclusive a margem de 1e-9 no vermelho (4,6 menos 3,6 da 0,9999999999999996),
o filtro das bandeiras sem vendas e a escolha da bandeira de maior custo.

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

_HERE = Path(__file__).resolve().parent
REFERENCES = _HERE.parent / "references"
SKILL = "custo-vrva"


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
    `judicial_status` entra inteiro.
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

def brand_status(rate: float, days: float, params: dict, a: dict) -> str:
    excess = rate - params["mdr_cap_percent"]
    if excess <= 0 and days <= params["settlement_max_days"]:
        return "green"
    # Margem pequena para nao errar por arredondamento de ponto flutuante (4,6 menos 3,6).
    if excess >= a["red_excess_rate_points"] - 1e-9 or days >= a["red_days"]:
        return "red"
    return "amber"


def calc_brand(brand: dict, params: dict, a: dict, money_cost_percent: float) -> dict:
    excess_rate = max(0, brand["rate"] - params["mdr_cap_percent"])
    excess_fee_month = (brand["sales"] * excess_rate) / 100
    extra_days = max(0, brand["days"] - params["settlement_max_days"])
    stuck_money = (brand["sales"] / a["days_per_month"]) * extra_days
    stuck_cost_month = (stuck_money * money_cost_percent) / 100
    return {
        "brand": brand,
        "excess_rate": excess_rate,
        "excess_fee_month": excess_fee_month,
        "extra_days": extra_days,
        "stuck_money": stuck_money,
        "stuck_cost_month": stuck_cost_month,
        "total_month": excess_fee_month + stuck_cost_month,
        "status": brand_status(brand["rate"], brand["days"], params, a),
    }


def _sum(items, pick):
    total = 0
    for item in items:
        total += pick(item)
    return total


def calc_store(brands: list, params: dict, a: dict, money_cost_percent=None) -> dict:
    if money_cost_percent is None:
        money_cost_percent = a["money_cost_month_percent"]
    rows = [calc_brand(b, params, a, money_cost_percent) for b in brands if b["sales"] > 0]

    def total(key):
        return _sum(rows, lambda row: row[key])

    top = None
    for row in rows:
        if row["total_month"] > 0 and (top is None or row["total_month"] > top["total_month"]):
            top = row
    excess_fee_month = total("excess_fee_month")
    stuck_cost_month = total("stuck_cost_month")
    total_month = total("total_month")
    return {
        "brands": rows,
        "excess_fee_month": excess_fee_month,
        "excess_fee_year": excess_fee_month * 12,
        "stuck_money": total("stuck_money"),
        "stuck_cost_month": stuck_cost_month,
        "stuck_cost_year": stuck_cost_month * 12,
        "total_month": total_month,
        "total_year": total_month * 12,
        "above_count": len([row for row in rows if row["status"] != "green"]),
        "counted": len(rows),
        "top": top,
        "money_cost_month_percent": money_cost_percent,
    }


# ------------------------------------------------- textos (src/i18n/pt-BR.ts)

UNNAMED = "Outra bandeira"
NO_SALES = "Preencha as vendas de pelo menos uma bandeira."
RATE_FRACTION_HINT = "A taxa vai em porcentagem. Se a sua é 6,5%, digite 6,5."
VERDICT_OK = "Dentro da regra em todas as bandeiras"

_ACTION_OTHER_FEES = (
    "Confira se há cobrança além da taxa, como aluguel ou anuidade, e pergunte à operadora com base em quê."
)
_ACTION_COMPARE = "Compare a sua maquininha atual com uma que aceite todos os vales."
_ACTION_MONTHLY = "Confira todo mês no extrato se a taxa cobrada é a do contrato."


def _plural(count, singular, plural):
    return singular if count == 1 else plural


def format_percent(value) -> str:
    """formatPercent do site: até 2 casas, sem zeros sobrando, com vírgula (3,6; 2; 4,59)."""
    rounded = math.floor(value * 100 + 0.5) / 100  # Math.round do JS
    text = str(int(rounded)) if float(rounded).is_integer() else repr(rounded)
    return text.replace(".", ",")


def _days_text(value) -> str:
    return str(int(value)) if float(value).is_integer() else format_percent(value)


def brand_name(name) -> str:
    return str(name or "").strip() or UNNAMED


def join_names(names: list) -> str:
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} e {names[-1]}"


def verdict_above(count, counted) -> str:
    return f"Acima da regra em {count} de {counted} {_plural(counted, 'bandeira', 'bandeiras')}"


# --------------------------------------------------------- veredito e acoes

def verdict(result: dict) -> dict:
    """Veredito do topo do resultado: acima da regra (com custo) ou dentro em todas."""
    if result["total_month"] > 0:
        statuses = [row["status"] for row in result.get("brands", [])]
        status = "red" if "red" in statuses else "amber"
        return {"status": status, "title": verdict_above(result["above_count"], result["counted"])}
    return {"status": "green", "title": VERDICT_OK}


def actions(result: dict, params=None) -> list:
    """buildActions do site. `params` padrão: legal-params.json (o teto e o prazo entram no texto)."""
    if params is None:
        params = _read_json("legal-params.json")
    cap = format_percent(params["mdr_cap_percent"])
    days = _days_text(params["settlement_max_days"])
    items = []
    if result.get("top"):
        items.append(f"Comece pela {brand_name(result['top']['brand'].get('name'))}: é onde está a maior parte do custo.")
    if any(row["excess_rate"] > 0 for row in result["brands"]):
        items.append(f"Peça por escrito a taxa de até {cap}%, que é o teto do decreto.")
    if any(row["extra_days"] > 0 for row in result["brands"]):
        items.append(f"Peça por escrito o repasse em até {days} dias corridos da venda.")
    items += [_ACTION_OTHER_FEES, _ACTION_COMPARE, _ACTION_MONTHLY]
    return items


# ---------------------------------------------------------------- validacao

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_date(value) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _money_cost_error(value, prefix) -> str:
    if _is_number(value) and 0 < value <= 100:
        return ""
    return f"{prefix}money_cost_month_percent (custo do dinheiro parado) precisa ser um número maior que zero e até 100, em % ao mês, como 2."


def _validate_brands(brands, a, prefix, errors):
    if not isinstance(brands, list) or not brands:
        errors.append(f"{prefix}brands precisa ser uma lista com pelo menos uma bandeira.")
        return
    any_sales = False
    start = len(errors)
    for i, item in enumerate(brands, start=1):
        if not isinstance(item, dict):
            errors.append(f"{prefix}Bandeira {i}: precisa ser um objeto com name, sales, rate e days.")
            continue
        name = item.get("name")
        label = f"{prefix}Bandeira {i} ({name.strip()})" if isinstance(name, str) and name.strip() else f"{prefix}Bandeira {i}"
        if name is not None and not isinstance(name, str):
            errors.append(f"{label}: o nome da bandeira precisa ser um texto.")
        sales = item.get("sales")
        if not (_is_number(sales) and sales >= 0):
            errors.append(f"{label}: vendas no mês precisa ser um número maior ou igual a zero, em reais, como 18000.")
            continue
        if sales <= 0:
            continue  # bandeira sem vendas fica fora da conta, como no site
        any_sales = True
        rate = item.get("rate")
        if not _is_number(rate) or rate <= 0:
            errors.append(f"{label}: Informe a taxa, em %, como 6.5 para 6,5%.")
        elif rate < 1:
            errors.append(f"{label}: {RATE_FRACTION_HINT}")
        elif rate > a["max_rate_percent"]:
            errors.append(f"{label}: A taxa vai até {format_percent(a['max_rate_percent'])}%.")
        days = item.get("days")
        if not _is_number(days) or days <= 0:
            errors.append(f"{label}: Informe o prazo de recebimento, em dias corridos, como 30.")
        elif days > a["max_days"]:
            errors.append(f"{label}: O prazo vai até {_days_text(a['max_days'])} dias.")
    if not any_sales and len(errors) == start:
        errors.append(f"{prefix}{NO_SALES}")


_POSITIVE = ("settlement_max_days", "days_per_month", "red_days", "max_rate_percent", "max_days")
_NON_NEGATIVE = ("red_excess_rate_points",)
_TEXT = ("version", "decree", "official_text_url")
_DATES = ("checked_at", "rate_cap_since", "interoperability_starts_on")


def _validate_params_override(po, errors):
    if "mdr_cap_percent" in po and not (_is_number(po["mdr_cap_percent"]) and 0 < po["mdr_cap_percent"] <= 100):
        errors.append("params_override: mdr_cap_percent precisa ser um número maior que zero e até 100, como 3.6.")
    if "money_cost_month_percent" in po and _money_cost_error(po["money_cost_month_percent"], ""):
        errors.append("params_override: " + _money_cost_error(po["money_cost_month_percent"], ""))
    for key in _POSITIVE:
        if key in po and not (_is_number(po[key]) and po[key] > 0):
            errors.append(f"params_override: {key} precisa ser um número maior que zero.")
    for key in _NON_NEGATIVE:
        if key in po and not (_is_number(po[key]) and po[key] >= 0):
            errors.append(f"params_override: {key} precisa ser um número maior ou igual a zero.")
    for key in _TEXT:
        if key in po and not (isinstance(po[key], str) and po[key].strip()):
            errors.append(f"params_override: {key} precisa ser um texto.")
    for key in _DATES:
        if key in po and not _valid_date(po[key]):
            errors.append(f"params_override: {key} precisa ser uma data no formato AAAA-MM-DD.")
    if "verified_against_official_text" in po and not isinstance(po["verified_against_official_text"], bool):
        errors.append("params_override: verified_against_official_text precisa ser verdadeiro ou falso.")
    if "judicial_status" in po:
        status = po["judicial_status"]
        if not isinstance(status, dict):
            errors.append('params_override: judicial_status precisa ser um objeto {"text", "checked_at", "sources"}.')
            return
        if not (isinstance(status.get("text"), str) and status["text"].strip()):
            errors.append("params_override: judicial_status.text precisa ser um texto.")
        if not _valid_date(status.get("checked_at")):
            errors.append("params_override: judicial_status.checked_at precisa ser uma data no formato AAAA-MM-DD.")
        sources = status.get("sources")
        if not (isinstance(sources, list) and all(isinstance(s, str) for s in sources)):
            errors.append("params_override: judicial_status.sources precisa ser uma lista de links.")


def validate(data) -> list:
    """Erros de entrada, em portugues. Lista vazia = entrada valida."""
    if not isinstance(data, dict):
        return ["A entrada precisa ser um objeto JSON."]
    errors = []
    today = data.get("today")
    if today is not None and not _valid_date(today):
        errors.append("today precisa ser uma data no formato AAAA-MM-DD.")
    if "money_cost_month_percent" in data:
        message = _money_cost_error(data["money_cost_month_percent"], "")
        if message:
            errors.append(message)
    _, assumptions, _ = load_params()
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
                before = len(errors)
                _validate_params_override(po, errors)
                if len(errors) == before:
                    _, assumptions, _ = load_params(po)
    if "stores" in data:
        stores = data["stores"]
        if not isinstance(stores, list) or not stores:
            errors.append("stores precisa ser uma lista com pelo menos uma loja.")
            return errors
        for i, item in enumerate(stores, start=1):
            if not isinstance(item, dict):
                errors.append(f"Loja {i}: precisa ser um objeto com name e brands.")
                continue
            name = item.get("name")
            prefix = f"{name.strip()}: " if isinstance(name, str) and name.strip() else f"Loja {i}: "
            if "money_cost_month_percent" in item:
                message = _money_cost_error(item["money_cost_month_percent"], prefix)
                if message:
                    errors.append(message)
            _validate_brands(item.get("brands"), assumptions, prefix, errors)
    else:
        _validate_brands(data.get("brands"), assumptions, "", errors)
    return errors


# --------------------------------------------------------------------- run

def _jsonable(value):
    """Inteiros-valorados viram int, como o JS os serializa (522, nao 522.0)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _normalize_brand(item: dict) -> dict:
    out = dict(item)
    out["name"] = item.get("name") or ""
    return out


def _run_store(brands_in, money, params, assumptions) -> dict:
    result = calc_store([_normalize_brand(b) for b in brands_in], params, assumptions, money)
    return {"result": result, "verdict": verdict(result), "actions": actions(result, params)}


_NETWORK_SUMS = ("excess_fee_month", "excess_fee_year", "stuck_money", "stuck_cost_month", "stuck_cost_year",
                 "total_month", "total_year", "above_count", "counted")


def _network(stores: list) -> dict:
    results = [s["result"] for s in stores]
    network = {key: _sum(results, lambda r, key=key: r[key]) for key in _NETWORK_SUMS}
    network["stores_counted"] = len([r for r in results if r["counted"] > 0])
    top = None
    for s in stores:
        if s["result"]["total_month"] > 0 and (top is None or s["result"]["total_month"] > top["result"]["total_month"]):
            top = s
    network["top_store"] = top["name"] if top else None
    network["verdict"] = verdict({**network, "brands": [row for r in results for row in r["brands"]]})
    return network


def run(data: dict) -> dict:
    params, assumptions, overridden = load_params(data.get("params_override"))
    today = data.get("today") or date.today().isoformat()
    money = data.get("money_cost_month_percent")
    if money is None:
        money = assumptions["money_cost_month_percent"]

    output = {
        "skill": SKILL,
        "params_version": params["version"] + ("+override" if overridden else ""),
        "checked_at": params["checked_at"],
        "judicial_status": copy.deepcopy(params["judicial_status"]),
        "overridden": overridden,
        "today": today,
        "rules": {
            "decree": params["decree"],
            "official_text_url": params["official_text_url"],
            "mdr_cap_percent": params["mdr_cap_percent"],
            "settlement_max_days": params["settlement_max_days"],
            "rate_cap_since": params["rate_cap_since"],
            "interoperability_starts_on": params["interoperability_starts_on"],
            "days_per_month": assumptions["days_per_month"],
            "red_excess_rate_points": assumptions["red_excess_rate_points"],
            "red_days": assumptions["red_days"],
        },
    }
    if "stores" in data:
        stores = []
        for i, item in enumerate(data["stores"], start=1):
            store_money = item.get("money_cost_month_percent")
            entry = _run_store(item["brands"], money if store_money is None else store_money, params, assumptions)
            stores.append({"name": str(item.get("name") or "").strip() or f"Loja {i}", **entry})
        output["stores"] = stores
        output["network"] = _network(stores)
    else:
        output.update(_run_store(data["brands"], money, params, assumptions))
    return _jsonable(copy.deepcopy(output))


# --------------------------------------------------------------------- CLI

def _fail(errors) -> int:
    print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Motor de cálculo do custo do VR e do VA (CD2 Tech).")
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
