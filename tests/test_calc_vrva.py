"""Testes do motor da skill custo-vrva.

Portados 1 a 1 de core/calculator.test.ts, src/lib/actions.test.ts e
src/lib/validation.test.ts da calculadora de VR e VA da CD2, mais os testes
de robustez da skill (validação, CLI, rede, override).

Os scripts das duas skills se chamam calc.py e render.py. Por isso os módulos
desta skill são carregados pelo caminho, com nome próprio, sem mexer no
sys.path dos testes da fim-escala-6x1.
"""
import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "core" / "cd2-varejo" / "skills" / "custo-vrva"
SHARED = ROOT / "core" / "cd2-varejo" / "shared" / "scripts"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


def load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


calc = load_module("custo_vrva_calc", SKILL / "scripts" / "calc.py")

PARAMS, A, _ = calc.load_params()
EM, EN = chr(0x2014), chr(0x2013)

BAKERY = [
    {"id": "alelo", "name": "Alelo", "sales": 18000, "rate": 6.5, "days": 30},
    {"id": "pluxee", "name": "Pluxee (Sodexo)", "sales": 12000, "rate": 5.9, "days": 30},
    {"id": "ticket", "name": "Ticket", "sales": 10000, "rate": 6.0, "days": 32},
    {"id": "vr", "name": "VR", "sales": 8000, "rate": 4.5, "days": 25},
]

# t.actions de src/i18n/pt-BR.ts, literal
RATE = "Peça por escrito a taxa de até 3,6%, que é o teto do decreto."
DAYS = "Peça por escrito o repasse em até 15 dias corridos da venda."
OTHER_FEES = "Confira se há cobrança além da taxa, como aluguel ou anuidade, e pergunte à operadora com base em quê."
COMPARE = "Compare a sua maquininha atual com uma que aceite todos os vales."
MONTHLY = "Confira todo mês no extrato se a taxa cobrada é a do contrato."


def bakery():
    return copy.deepcopy(BAKERY)


def one(**over):
    brand = {"id": "x", "name": "X", "sales": 9000, "rate": 3.6, "days": 15}
    brand.update(over)
    return [brand]


def store(brands=None, money=None):
    return calc.calc_store(brands if brands is not None else bakery(), PARAMS, A, money)


def by_id(result, brand_id):
    return next(b for b in result["brands"] if b["brand"]["id"] == brand_id)


def example_input(**extra):
    data = {"brands": [{k: v for k, v in b.items() if k != "id"} for b in bakery()], "money_cost_month_percent": 2}
    data.update(extra)
    return data


class ReferenceBakeryTest(unittest.TestCase):
    """Valores de conferência de docs/metodologia.md."""

    def test_reference_bakery(self):
        r = store(money=2)
        expected = {
            "Alelo": (522.00, 9000.00, 180.00),
            "Pluxee (Sodexo)": (276.00, 6000.00, 120.00),
            "Ticket": (240.00, 5666.67, 113.33),
            "VR": (72.00, 2666.67, 53.33),
        }
        self.assertEqual([b["brand"]["name"] for b in r["brands"]], list(expected))
        for row in r["brands"]:
            fee, stuck, cost = expected[row["brand"]["name"]]
            with self.subTest(brand=row["brand"]["name"]):
                self.assertAlmostEqual(row["excess_fee_month"], fee, places=2)
                self.assertAlmostEqual(row["stuck_money"], stuck, places=2)
                self.assertAlmostEqual(row["stuck_cost_month"], cost, places=2)
        self.assertAlmostEqual(r["total_month"], 1576.67, places=2)
        self.assertAlmostEqual(r["total_year"], 18920.0, places=2)


class BakeryTest(unittest.TestCase):
    """describe('padaria de exemplo') de core/calculator.test.ts."""

    def setUp(self):
        self.r = store()

    def test_excess_fee(self):
        self.assertAlmostEqual(self.r["excess_fee_month"], 1110, places=2)
        self.assertAlmostEqual(self.r["excess_fee_year"], 13320, places=2)
        for row, value in zip(self.r["brands"], (522, 276, 240, 72)):
            self.assertAlmostEqual(row["excess_fee_month"], value, places=2)

    def test_stuck_money(self):
        self.assertAlmostEqual(self.r["stuck_money"], 23333.33, places=2)
        self.assertAlmostEqual(self.r["stuck_cost_month"], 466.67, places=2)
        self.assertAlmostEqual(self.r["stuck_cost_year"], 5600, places=2)
        ticket = by_id(self.r, "ticket")
        self.assertEqual(ticket["extra_days"], 17)
        self.assertAlmostEqual(ticket["stuck_money"], 5666.67, places=2)

    def test_totals(self):
        self.assertAlmostEqual(self.r["total_month"], 1576.67, places=2)
        self.assertAlmostEqual(self.r["total_year"], 18920, places=2)

    def test_colors_and_verdict(self):
        self.assertEqual([b["status"] for b in self.r["brands"]], ["red", "red", "red", "amber"])
        self.assertEqual(self.r["above_count"], 4)
        self.assertEqual(self.r["counted"], 4)
        self.assertEqual(self.r["top"]["brand"]["id"], "alelo")
        self.assertEqual(self.r["money_cost_month_percent"], 2)


class BrandRulesTest(unittest.TestCase):
    """describe('regras por bandeira') de core/calculator.test.ts."""

    def test_brand_within_rule_is_green_and_zero(self):
        r = store(one())
        self.assertEqual(r["brands"][0]["status"], "green")
        self.assertEqual(r["total_month"], 0)
        self.assertEqual(r["stuck_money"], 0)
        self.assertEqual(r["above_count"], 0)
        self.assertIsNone(r["top"])

    def test_rate_inside_days_above(self):
        r = store(one(rate=3, days=20))
        self.assertEqual(r["brands"][0]["status"], "amber")
        self.assertEqual(r["excess_fee_month"], 0)
        self.assertAlmostEqual(r["stuck_money"], (9000 / 30) * 5, places=6)

    def test_30_days_is_red(self):
        self.assertEqual(calc.brand_status(3, 30, PARAMS, A), "red")

    def test_one_point_above_is_red_less_is_amber(self):
        # 4,6 menos 3,6 dá 0,9999999999999996 em ponto flutuante: a margem de 1e-9 segura o vermelho.
        self.assertLess(4.6 - 3.6, 1)
        self.assertEqual(calc.brand_status(4.6, 15, PARAMS, A), "red")
        self.assertEqual(calc.brand_status(4.59, 15, PARAMS, A), "amber")

    def test_zero_sales_left_out(self):
        r = store(bakery() + [{"id": "flash", "name": "Flash", "sales": 0, "rate": 9, "days": 60}])
        self.assertEqual(r["counted"], 4)
        self.assertFalse(any(b["brand"]["id"] == "flash" for b in r["brands"]))

    def test_editable_money_cost(self):
        r = store(money=3)
        self.assertAlmostEqual(r["stuck_cost_month"], 700, places=2)
        self.assertEqual(r["money_cost_month_percent"], 3)

    def test_default_money_cost_comes_from_assumptions(self):
        self.assertEqual(calc.calc_store(bakery(), PARAMS, A)["money_cost_month_percent"], 2)

    def test_no_sales(self):
        r = store([dict(b, sales=0) for b in bakery()])
        self.assertEqual(r["counted"], 0)
        self.assertIsNone(r["top"])
        self.assertEqual(r["total_month"], 0)
        self.assertEqual(r["brands"], [])

    def test_top_ignores_brands_without_cost(self):
        r = store(one() + [{"id": "y", "name": "Y", "sales": 100, "rate": 5, "days": 15}])
        self.assertEqual(r["top"]["brand"]["id"], "y")

    def test_top_keeps_first_on_tie(self):
        twin = [dict(BAKERY[0], id="a"), dict(BAKERY[0], id="b")]
        self.assertEqual(store(twin)["top"]["brand"]["id"], "a")


class ActionsTest(unittest.TestCase):
    """describe('O que fazer') de src/lib/actions.test.ts."""

    def run_actions(self, brands=None):
        return calc.actions(store(brands))

    def test_bakery_starts_with_alelo_and_has_6_items(self):
        items = self.run_actions()
        self.assertEqual(len(items), 6)
        self.assertIn("Alelo", items[0])
        self.assertEqual(items[0], "Comece pela Alelo: é onde está a maior parte do custo.")
        self.assertEqual(items[1:], [RATE, DAYS, OTHER_FEES, COMPARE, MONTHLY])

    def test_all_green_has_only_the_usual_3(self):
        items = self.run_actions([{"id": "vr", "name": "VR", "sales": 5000, "rate": 3, "days": 10}])
        self.assertEqual(items, [OTHER_FEES, COMPARE, MONTHLY])

    def test_rate_inside_days_above_does_not_ask_for_rate(self):
        items = self.run_actions([{"id": "vr", "name": "VR", "sales": 5000, "rate": 3, "days": 30}])
        self.assertNotIn(RATE, items)
        self.assertIn(DAYS, items)

    def test_unnamed_brand(self):
        items = self.run_actions([{"name": "  ", "sales": 5000, "rate": 6, "days": 15}])
        self.assertEqual(items[0], "Comece pela Outra bandeira: é onde está a maior parte do custo.")

    def test_actions_follow_overridden_cap(self):
        params, _, _ = calc.load_params({"mdr_cap_percent": 3.0, "settlement_max_days": 10})
        items = calc.actions(calc.calc_store(bakery(), params, A), params)
        self.assertIn("Peça por escrito a taxa de até 3%, que é o teto do decreto.", items)
        self.assertIn("Peça por escrito o repasse em até 10 dias corridos da venda.", items)

    def test_join_names(self):
        self.assertEqual(calc.join_names([]), "")
        self.assertEqual(calc.join_names(["A"]), "A")
        self.assertEqual(calc.join_names(["A", "B", "C"]), "A, B e C")


class VerdictTest(unittest.TestCase):
    def test_above(self):
        v = calc.verdict(store())
        self.assertEqual(v, {"status": "red", "title": "Acima da regra em 4 de 4 bandeiras"})

    def test_singular(self):
        v = calc.verdict(store(one(rate=4)))
        self.assertEqual(v, {"status": "amber", "title": "Acima da regra em 1 de 1 bandeira"})

    def test_ok(self):
        v = calc.verdict(store(one()))
        self.assertEqual(v, {"status": "green", "title": "Dentro da regra em todas as bandeiras"})


class FieldValidationTest(unittest.TestCase):
    """describe('validação') de src/lib/validation.test.ts."""

    def errors_for(self, **brand):
        base = {"name": "Alelo", "sales": 18000, "rate": 6.5, "days": 30}
        base.update(brand)
        return calc.validate({"brands": [base]})

    def test_rate_and_days_limits(self):
        self.assertTrue(self.errors_for(rate=31))
        self.assertEqual(self.errors_for(rate=6.5), [])
        self.assertIn("Informe a taxa", self.errors_for(rate=None)[0])
        self.assertTrue(self.errors_for(days=121))
        self.assertEqual(self.errors_for(days=30), [])
        self.assertIn("Informe o prazo", self.errors_for(days=None)[0])
        # fieldError('sales') é sempre null no site: vendas não têm teto.
        self.assertEqual(self.errors_for(sales=10_000_000), [])

    def test_fraction_rate_blocks_result(self):
        errors = self.errors_for(rate=0.065)
        self.assertEqual(len(errors), 1)
        self.assertIn("A taxa vai em porcentagem. Se a sua é 6,5%, digite 6,5.", errors[0])

    def test_result_only_with_sales_and_valid_fields(self):
        default = [{"name": n, "sales": 0, "rate": 0, "days": 0} for n in ("Alelo", "Pluxee (Sodexo)", "Ticket", "VR")]
        self.assertEqual(calc.validate({"brands": default}), ["Preencha as vendas de pelo menos uma bandeira."])
        self.assertEqual(calc.validate(example_input()), [])
        missing_rate = example_input()
        missing_rate["brands"][0]["rate"] = 0
        self.assertTrue(calc.validate(missing_rate))
        too_long = example_input()
        too_long["brands"][0]["days"] = 200
        self.assertTrue(calc.validate(too_long))
        zero_sales_bad = example_input()
        zero_sales_bad["brands"][0].update(sales=0, rate=0, days=0)
        self.assertEqual(calc.validate(zero_sales_bad), [])

    def test_max_limits_name_the_number(self):
        self.assertIn("A taxa vai até 30%", self.errors_for(rate=31)[0])
        self.assertIn("O prazo vai até 120 dias", self.errors_for(days=121)[0])


class ValidateTest(unittest.TestCase):
    def test_validate(self):
        cases = {
            "rate_text": ("rate", "6,5"),
            "rate_31": ("rate", 31),
            "days_121": ("days", 121),
            "negative_sales": ("sales", -1),
        }
        for label, (field, value) in cases.items():
            with self.subTest(case=label):
                data = example_input()
                data["brands"][0][field] = value
                errors = calc.validate(data)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("Bandeira 1 (Alelo)", errors[0])
                p = subprocess.run(
                    [sys.executable, str(SKILL / "scripts" / "calc.py")],
                    input=json.dumps(data), capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(p.returncode, 2)
                self.assertNotIn("Traceback", p.stderr)
                self.assertEqual(json.loads(p.stdout)["errors"], errors)

    def test_message_format(self):
        data = example_input()
        data["brands"][2]["sales"] = "x"
        self.assertEqual(
            calc.validate(data),
            ["Bandeira 3 (Ticket): vendas no mês precisa ser um número maior ou igual a zero, em reais, como 18000."],
        )

    def test_not_an_object(self):
        self.assertTrue(calc.validate([1, 2]))

    def test_brands_must_be_a_list(self):
        self.assertTrue(calc.validate({"brands": "Alelo"}))
        self.assertTrue(calc.validate({"brands": []}))
        self.assertTrue(calc.validate({"brands": ["Alelo"]}))

    def test_name_must_be_text(self):
        data = example_input()
        data["brands"][0]["name"] = 123
        self.assertTrue(any("Bandeira 1" in e and "nome" in e for e in calc.validate(data)))

    def test_bool_is_not_a_number(self):
        data = example_input()
        data["brands"][0]["rate"] = True
        self.assertTrue(calc.validate(data))

    def test_money_cost(self):
        for bad in (0, -1, 101, "2", None):
            with self.subTest(money=bad):
                self.assertTrue(calc.validate(example_input(money_cost_month_percent=bad)))
        self.assertEqual(calc.validate(example_input(money_cost_month_percent=3.5)), [])
        data = example_input()
        del data["money_cost_month_percent"]
        self.assertEqual(calc.validate(data), [])

    def test_bad_date_and_unknown_override(self):
        self.assertTrue(calc.validate(example_input(today="06/11/2026")))
        self.assertTrue(calc.validate(example_input(params_override={"nao_existe": 1})))

    def test_network_errors_name_the_store(self):
        data = {
            "stores": [
                {"name": "Loja A", "brands": example_input()["brands"]},
                {"name": "Loja B", "brands": [{"name": "Alelo", "sales": 100, "rate": 40, "days": 30}]},
            ]
        }
        errors = calc.validate(data)
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Loja B: Bandeira 1 (Alelo)"))

    def test_network_needs_stores(self):
        self.assertTrue(calc.validate({"stores": []}))
        self.assertTrue(calc.validate({"stores": ["x"]}))
        self.assertTrue(calc.validate({"stores": [{"name": "A", "brands": example_input()["brands"],
                                                   "money_cost_month_percent": -2}]}))


class CapOverrideTest(unittest.TestCase):
    def test_cap_override(self):
        out = calc.run(example_input(params_override={"mdr_cap_percent": 3.0}))
        alelo = out["result"]["brands"][0]
        self.assertEqual(alelo["brand"]["name"], "Alelo")
        self.assertEqual(alelo["excess_fee_month"], 630.0)
        self.assertEqual(out["overridden"], ["mdr_cap_percent"])
        self.assertEqual(out["params_version"], PARAMS["version"] + "+override")
        self.assertEqual(out["rules"]["mdr_cap_percent"], 3)

    def test_load_params_override(self):
        params, assumptions, keys = calc.load_params({"settlement_max_days": 10, "red_days": 20})
        self.assertEqual(params["settlement_max_days"], 10)
        self.assertEqual(assumptions["red_days"], 20)
        self.assertEqual(sorted(keys), ["red_days", "settlement_max_days"])
        self.assertEqual(calc.load_params()[0]["settlement_max_days"], 15)
        with self.assertRaises(ValueError):
            calc.load_params({"nao_existe": 1})

    def test_judicial_status_override(self):
        status = {"text": "Decisão nova.", "checked_at": "2026-11-07", "sources": ["https://www.stf.jus.br/"]}
        out = calc.run(example_input(params_override={"judicial_status": status}))
        self.assertEqual(out["judicial_status"], status)
        self.assertEqual(out["overridden"], ["judicial_status"])

    def test_default_money_cost_override(self):
        data = example_input(params_override={"money_cost_month_percent": 3})
        del data["money_cost_month_percent"]
        self.assertAlmostEqual(calc.run(data)["result"]["stuck_cost_month"], 700, places=2)


class RunTest(unittest.TestCase):
    def test_single_store_shape(self):
        out = calc.run(example_input(today="2026-11-07"))
        self.assertEqual(out["skill"], "custo-vrva")
        self.assertEqual(out["params_version"], PARAMS["version"])
        self.assertEqual(out["checked_at"], PARAMS["checked_at"])
        self.assertEqual(out["judicial_status"], PARAMS["judicial_status"])
        self.assertEqual(out["overridden"], [])
        self.assertEqual(out["today"], "2026-11-07")
        self.assertEqual(
            out["rules"],
            {
                "decree": PARAMS["decree"],
                "official_text_url": PARAMS["official_text_url"],
                "mdr_cap_percent": 3.6,
                "settlement_max_days": 15,
                "rate_cap_since": "2026-02-10",
                "interoperability_starts_on": "2026-11-07",
                "days_per_month": 30,
                "red_excess_rate_points": 1,
                "red_days": 30,
            },
        )
        self.assertEqual(out["verdict"]["title"], "Acima da regra em 4 de 4 bandeiras")
        self.assertEqual(len(out["actions"]), 6)
        self.assertAlmostEqual(out["result"]["total_month"], 1576.67, places=2)
        json.dumps(out, ensure_ascii=False)

    def test_network_sums_stores(self):
        data = {
            "money_cost_month_percent": 2,
            "stores": [
                {"name": "Loja A", "brands": example_input()["brands"]},
                {"name": "Loja B", "brands": example_input()["brands"], "money_cost_month_percent": 3},
                {"name": "", "brands": [{"name": "VR", "sales": 1000, "rate": 3, "days": 10}]},
            ],
        }
        self.assertEqual(calc.validate(data), [])
        out = calc.run(data)
        self.assertNotIn("result", out)
        self.assertEqual([s["name"] for s in out["stores"]], ["Loja A", "Loja B", "Loja 3"])
        for s in out["stores"]:
            self.assertEqual(set(s), {"name", "result", "verdict", "actions"})
        a, b = out["stores"][0]["result"], out["stores"][1]["result"]
        self.assertEqual(b["money_cost_month_percent"], 3)
        net = out["network"]
        self.assertAlmostEqual(net["total_month"], a["total_month"] + b["total_month"])
        self.assertAlmostEqual(net["total_year"], 12 * net["total_month"])
        self.assertAlmostEqual(net["excess_fee_month"], 2220)
        self.assertEqual(net["counted"], 9)
        self.assertEqual(net["above_count"], 8)
        self.assertEqual(net["stores_counted"], 3)
        self.assertEqual(net["top_store"], "Loja B")
        self.assertEqual(net["verdict"], {"status": "red", "title": "Acima da regra em 8 de 9 bandeiras"})

    def test_top_level_money_cost_default(self):
        data = example_input()
        del data["money_cost_month_percent"]
        self.assertEqual(calc.run(data)["result"]["money_cost_month_percent"], 2)

    def test_integral_numbers_serialize_as_ints(self):
        text = json.dumps(calc.run(example_input()))
        self.assertIn('"excess_fee_month": 522,', text)

    def test_input_is_not_mutated(self):
        data = example_input()
        before = copy.deepcopy(data)
        calc.run(data)
        self.assertEqual(data, before)

    def test_no_dashes_in_texts(self):
        text = json.dumps(calc.run(example_input()), ensure_ascii=False)
        self.assertNotIn(EM, text)
        self.assertNotIn(EN, text)

    def test_params_files_match_the_site(self):
        self.assertEqual(PARAMS["version"], "2026-11-06")
        self.assertEqual(PARAMS["mdr_cap_percent"], 3.6)
        self.assertEqual(PARAMS["settlement_max_days"], 15)
        self.assertEqual(A, {"money_cost_month_percent": 2, "days_per_month": 30, "red_excess_rate_points": 1,
                             "red_days": 30, "max_rate_percent": 30, "max_days": 120})


class CliTest(unittest.TestCase):
    script = str(SKILL / "scripts" / "calc.py")

    def call(self, stdin=None, args=()):
        return subprocess.run(
            [sys.executable, self.script, *args], input=stdin, capture_output=True, text=True, encoding="utf-8"
        )

    def assert_clean_rejection(self, data):
        p = self.call(json.dumps(data))
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        self.assertTrue(json.loads(p.stdout)["errors"])

    def test_stdin_ok(self):
        p = self.call(json.dumps(example_input()))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["skill"], "custo-vrva")

    def test_input_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dados.json"
            path.write_text(json.dumps(example_input(), ensure_ascii=False), encoding="utf-8")
            p = self.call(args=("--input", str(path)))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Pluxee (Sodexo)", p.stdout)

    def test_invalid_json_exit_2(self):
        p = self.call("{nao e json")
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)
        self.assertTrue(json.loads(p.stdout)["errors"])

    def test_missing_file_exit_2(self):
        p = self.call(args=("--input", "/nao/existe.json"))
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)

    def test_bad_params_override_values(self):
        for bad in (
            "abc",
            {"mdr_cap_percent": "3,6"},
            {"mdr_cap_percent": 0},
            {"mdr_cap_percent": 101},
            {"settlement_max_days": 0},
            {"days_per_month": 0},
            {"red_days": -1},
            {"money_cost_month_percent": 0},
            {"max_rate_percent": "x"},
            {"interoperability_starts_on": "07/11/2026"},
            {"verified_against_official_text": "sim"},
            {"decree": ""},
            {"judicial_status": "liminar"},
            {"judicial_status": {"text": "", "checked_at": "2026-11-07", "sources": []}},
            {"judicial_status": {"text": "x", "checked_at": "ontem", "sources": []}},
            {"judicial_status": {"text": "x", "checked_at": "2026-11-07", "sources": "https://a"}},
        ):
            with self.subTest(bad=bad):
                self.assert_clean_rejection(example_input(params_override=bad))

    def test_main_catch_all(self):
        import io
        from unittest import mock

        out = io.StringIO()
        with mock.patch.object(calc, "run", side_effect=RuntimeError("boom")), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(example_input()))), \
                mock.patch.object(sys, "stdout", out):
            code = calc.main([])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue()), {"errors": ["Erro inesperado ao calcular: RuntimeError."]})


if __name__ == "__main__":
    unittest.main()
