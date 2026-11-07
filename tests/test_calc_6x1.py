"""Testes do motor da skill fim-escala-6x1.

Portados 1 a 1 de core/calculator.test.ts, src/lib/verdict.test.ts,
src/lib/actions.test.ts e src/lib/deadline.test.ts da calculadora CD2,
mais os testes de robustez da skill (validacao, CLI, rede, override).
"""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "core" / "cd2-varejo" / "skills" / "fim-escala-6x1"
sys.path.insert(0, str(ROOT / "core" / "cd2-varejo" / "shared" / "scripts"))
sys.path.insert(0, str(SKILL / "scripts"))

import calc  # noqa: E402
from brand import format_brl_compact  # noqa: E402

PARAMS, ASSUMPTIONS, _ = calc.load_params()
EM, EN = chr(0x2014), chr(0x2013)


def rule(weekly_hours, max_work_days=5):
    return {
        "weekly_hours": weekly_hours,
        "max_work_days": max_work_days,
        "legal_weekly_limit": 42,
        "above_legal_limit": False,
        "days_need_compensation": False,
    }


def sector(headcount, **over):
    base = {
        "name": "Setor",
        "headcount": headcount,
        "avg_monthly_salary": 2000,
        "min_simultaneous_staff": None,
        "current_weekly_hours": 44,
        "current_work_days": 6,
    }
    base.update(over)
    return base


STORE = {"days_open_per_week": 7, "hours_open_per_day": 13, "payroll_charges_factor": 0.7}

EXAMPLE_SECTORS = [
    sector(14, name="Caixa", avg_monthly_salary=1900, min_simultaneous_staff=5),
    sector(12, name="Reposição", avg_monthly_salary=1900),
    sector(6, name="Açougue", avg_monthly_salary=2600),
    sector(5, name="Padaria", avg_monthly_salary=2300),
    sector(4, name="Hortifrúti", avg_monthly_salary=2000),
    sector(3, name="Recebimento", avg_monthly_salary=2100),
]


def reds(r):
    return [s["sector"]["name"] for s in r["sectors"] if s["status"] == "red"]


class SectionBriefTest(unittest.TestCase):
    def test_10_people_44_to_42(self):
        r = calc.calc_sector(sector(10), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["lost_hours"], 20)
        self.assertEqual(r["needed_by_hours"], 11)
        self.assertEqual(r["additional_headcount"], 1)

    def test_10_people_44_to_40(self):
        r = calc.calc_sector(sector(10), STORE, rule(40), ASSUMPTIONS)
        self.assertEqual(r["lost_hours"], 40)
        self.assertEqual(r["needed_by_hours"], 11)
        self.assertEqual(r["additional_headcount"], 1)

    def test_7_day_store_13h_3_posts_42h(self):
        r = calc.calc_sector(sector(10, min_simultaneous_staff=3), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["shifts_per_day"], 2)
        self.assertEqual(r["needed_by_days"], 9)

    def test_days_criterion_wins_when_larger(self):
        r = calc.calc_sector(sector(2, min_simultaneous_staff=3), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["additional_headcount"], 7)

    def test_additional_headcount_never_negative(self):
        r = calc.calc_sector(sector(50, min_simultaneous_staff=1), STORE, rule(42), ASSUMPTIONS)
        self.assertGreaterEqual(r["additional_headcount"], 0)

    def test_rule_for_date(self):
        for date, hours in [("2026-12-15", 44), ("2026-12-16", 42), ("2027-12-15", 42), ("2027-12-16", 40)]:
            with self.subTest(date=date):
                self.assertEqual(calc.rule_for_date(date, PARAMS)["weekly_hours"], hours)

    def test_override_replaces_hours_in_every_scenario(self):
        over = {"weekly_hours_override": 41}
        self.assertEqual(calc.rule_for_scenario("with_agreement", PARAMS, over)["weekly_hours"], 41)
        self.assertEqual(calc.rule_for_scenario("without_agreement", PARAMS, over)["weekly_hours"], 41)

    def test_max_days_override_changes_divisor(self):
        r = calc.calc_sector(sector(2, min_simultaneous_staff=3), STORE, rule(42, 4), ASSUMPTIONS)
        self.assertEqual(r["needed_by_days"], 11)


class ScenariosTest(unittest.TestCase):
    today = "2026-11-02"

    def test_without_agreement_gives_40h(self):
        self.assertEqual(calc.rule_for_scenario("without_agreement", PARAMS, None, self.today)["weekly_hours"], 40)

    def test_with_agreement_gives_42h(self):
        self.assertEqual(calc.rule_for_scenario("with_agreement", PARAMS, None, self.today)["weekly_hours"], 42)

    def test_both_scenarios_until_phase2(self):
        self.assertEqual(calc.available_scenarios("2027-12-15", PARAMS), ["without_agreement", "with_agreement"])

    def test_one_scenario_from_phase2(self):
        self.assertEqual(calc.available_scenarios("2027-12-16", PARAMS), ["without_agreement"])
        self.assertEqual(
            calc.rule_for_scenario("without_agreement", PARAMS, None, "2027-12-16")["weekly_hours"], 40
        )

    def test_convention_hours_leave_single_scenario(self):
        self.assertEqual(
            calc.available_scenarios(self.today, PARAMS, {"weekly_hours_override": 41}), ["with_agreement"]
        )

    def test_zero_override_means_no_override(self):
        self.assertEqual(
            calc.available_scenarios(self.today, PARAMS, {"weekly_hours_override": 0}),
            ["without_agreement", "with_agreement"],
        )
        r = calc.rule_for_scenario("with_agreement", PARAMS, {"weekly_hours_override": 0}, self.today)
        self.assertEqual(r["weekly_hours"], 42)


class LegalLimitTest(unittest.TestCase):
    def test_44h_above_limit_loses_nothing(self):
        r = calc.rule_for_scenario("with_agreement", PARAMS, {"weekly_hours_override": 44}, "2026-11-02")
        self.assertTrue(r["above_legal_limit"])
        self.assertEqual(calc.calc_store(STORE, EXAMPLE_SECTORS, r, ASSUMPTIONS)["total_lost_hours"], 0)

    def test_43h_above_42h_limit(self):
        r = calc.rule_for_scenario("with_agreement", PARAMS, {"weekly_hours_override": 43}, "2026-11-02")
        self.assertTrue(r["above_legal_limit"])

    def test_42h_above_limit_from_phase2(self):
        r = calc.rule_for_scenario("with_agreement", PARAMS, {"weekly_hours_override": 42}, "2027-12-16")
        self.assertTrue(r["above_legal_limit"])

    def test_6_days_need_compensation_not_limit_error(self):
        r = calc.rule_for_scenario("with_agreement", PARAMS, {"max_work_days_override": 6}, "2026-11-02")
        self.assertTrue(r["days_need_compensation"])
        self.assertFalse(r["above_legal_limit"])


class ExampleStoreTest(unittest.TestCase):
    def test_at_42h(self):
        r = calc.calc_store(STORE, EXAMPLE_SECTORS, rule(42), ASSUMPTIONS)
        self.assertEqual(r["total_lost_hours"], 88)
        self.assertEqual(r["min_additional"], 3)
        self.assertEqual(r["max_additional"], 6)
        self.assertEqual(format_brl_compact(r["min_monthly_cost"]), "R$ 10,5 mil")
        self.assertEqual(format_brl_compact(r["max_monthly_cost"]), "R$ 21,8 mil")
        self.assertEqual(reds(r), ["Caixa", "Reposição"])

    def test_at_40h(self):
        r = calc.calc_store(STORE, EXAMPLE_SECTORS, rule(40), ASSUMPTIONS)
        self.assertEqual(r["total_lost_hours"], 176)
        self.assertEqual(r["min_additional"], 5)
        self.assertEqual(r["max_additional"], 8)
        self.assertEqual(format_brl_compact(r["min_monthly_cost"]), "R$ 17,5 mil")
        self.assertEqual(format_brl_compact(r["max_monthly_cost"]), "R$ 28,2 mil")
        self.assertEqual(reds(r), ["Caixa", "Reposição", "Açougue", "Padaria"])

    def test_annual_cost_and_payroll_share(self):
        r = calc.calc_store(STORE, EXAMPLE_SECTORS, rule(42), ASSUMPTIONS)
        self.assertAlmostEqual(r["max_annual_cost"], r["max_monthly_cost"] * 12)
        self.assertAlmostEqual(r["max_payroll_pct"], 14.1, places=1)
        self.assertAlmostEqual(r["min_payroll_pct"], 6.8, places=1)


class PeopleRangeTest(unittest.TestCase):
    def test_low_end_cost_does_not_invert(self):
        sectors = [
            sector(14, name="Caixa", avg_monthly_salary=1900, min_simultaneous_staff=10),
            sector(30, name="Açougue", avg_monthly_salary=6000),
        ]
        r = calc.calc_store(STORE, sectors, rule(42), ASSUMPTIONS)
        self.assertEqual(r["min_additional"], 14)
        self.assertEqual(r["max_additional"], 16)
        self.assertEqual(format_brl_compact(r["min_monthly_cost"]), "R$ 45,2 mil")
        self.assertEqual(format_brl_compact(r["max_monthly_cost"]), "R$ 65,6 mil")

    def test_low_end_never_above_high_end(self):
        sectors = [sector(1, avg_monthly_salary=1000), sector(40, avg_monthly_salary=9000)]
        r = calc.calc_store(STORE, sectors, rule(42), ASSUMPTIONS)
        self.assertLessEqual(r["min_monthly_cost"], r["max_monthly_cost"])

    def test_equal_range_uses_high_end_cost(self):
        r = calc.calc_store(STORE, [sector(10)], rule(42), ASSUMPTIONS)
        self.assertEqual(r["min_additional"], r["max_additional"])
        self.assertEqual(r["min_monthly_cost"], r["max_monthly_cost"])


class StatusColorsTest(unittest.TestCase):
    def status_for(self, headcount, hours):
        return calc.calc_sector(sector(headcount), STORE, rule(hours), ASSUMPTIONS)["status"]

    def test_half_a_person_is_red(self):
        self.assertEqual(self.status_for(10, 42), "amber")
        r = calc.calc_sector(sector(21, current_weekly_hours=43), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["status"], "red")

    def test_quarter_of_a_person_is_amber(self):
        r = calc.calc_sector(sector(21, current_weekly_hours=42.5), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["person_equivalent"], 0.25)
        self.assertEqual(r["status"], "amber")

    def test_less_than_a_quarter_is_green(self):
        self.assertEqual(self.status_for(3, 42), "green")

    def test_posts_that_do_not_close_week_are_red(self):
        r = calc.calc_sector(sector(2, min_simultaneous_staff=3), STORE, rule(42), ASSUMPTIONS)
        self.assertLess(r["person_equivalent"], 0.25)
        self.assertEqual(r["status"], "red")


class OtherCostsTest(unittest.TestCase):
    def test_hour_cost_increase(self):
        self.assertAlmostEqual(
            calc.calc_store(STORE, EXAMPLE_SECTORS, rule(42), ASSUMPTIONS)["hour_cost_increase_pct"], 4.76, places=2
        )
        self.assertAlmostEqual(
            calc.calc_store(STORE, EXAMPLE_SECTORS, rule(40), ASSUMPTIONS)["hour_cost_increase_pct"], 10, places=2
        )

    def test_overtime_uses_weekly_hours_divisor(self):
        r = calc.calc_sector(sector(14, avg_monthly_salary=1900), STORE, rule(42), ASSUMPTIONS)
        self.assertAlmostEqual(r["overtime_monthly_cost"], 28 * 4.33 * (1900 / 210) * 1.5)

    def test_overtime_above_daily_cap(self):
        with_cap = {**STORE, "overrides": {"overtime_cap_hours_per_day": 0.1}}
        self.assertTrue(calc.calc_store(with_cap, [sector(10)], rule(42), ASSUMPTIONS)["overtime_above_cap"])
        self.assertFalse(calc.calc_store(STORE, [sector(10)], rule(42), ASSUMPTIONS)["overtime_above_cap"])


class PersonInputsTest(unittest.TestCase):
    def test_sector_already_on_fewer_hours(self):
        r = calc.calc_sector(sector(10, current_weekly_hours=40), STORE, rule(42), ASSUMPTIONS)
        self.assertEqual(r["lost_hours"], 0)
        self.assertEqual(r["needed_by_hours"], 10)
        self.assertEqual(r["additional_headcount"], 0)
        self.assertEqual(r["status"], "green")

    def test_store_with_nobody_returns_zeros(self):
        r = calc.calc_store(STORE, [sector(0)], rule(42), ASSUMPTIONS)
        self.assertEqual(len(r["sectors"]), 0)
        for key in ("total_headcount", "min_monthly_cost", "min_payroll_pct", "max_payroll_pct", "person_equivalent"):
            self.assertEqual(r[key], 0, key)

    def test_empty_store_is_safe(self):
        r = calc.calc_store(STORE, [], rule(42), ASSUMPTIONS)
        self.assertEqual(r["total_headcount"], 0)
        self.assertEqual(r["hour_cost_increase_pct"], 0)

    def test_exact_division_does_not_round_up(self):
        self.assertEqual(calc.calc_sector(sector(42), STORE, rule(42), ASSUMPTIONS)["needed_by_hours"], 44)

    def test_5000_people_finite(self):
        r = calc.calc_store(STORE, [sector(5000, avg_monthly_salary=3000)], rule(40), ASSUMPTIONS)
        self.assertEqual(r["max_additional"], 500)
        self.assertLess(abs(r["max_monthly_cost"]), float("inf"))


class HourCostLimitStatusTest(unittest.TestCase):
    def test_never_negative_when_everyone_works_less(self):
        r = calc.calc_store(STORE, [sector(10, current_weekly_hours=36)], rule(40), ASSUMPTIONS)
        self.assertEqual(r["hour_cost_increase_pct"], 0)

    def test_counts_only_sectors_whose_hours_go_down(self):
        r = calc.calc_store(STORE, [sector(10, current_weekly_hours=36), sector(10)], rule(40), ASSUMPTIONS)
        self.assertAlmostEqual(r["hour_cost_increase_pct"], 5)

    def test_no_green_above_legal_limit(self):
        above = {**rule(44), "above_legal_limit": True}
        r = calc.calc_store(STORE, EXAMPLE_SECTORS, above, ASSUMPTIONS)
        self.assertEqual(r["counts"]["green"], 0)
        self.assertTrue(all(s["status"] == "amber" for s in r["sectors"]))

    def test_no_green_with_compensation_regime(self):
        compensated = {**rule(42, 6), "days_need_compensation": True}
        self.assertEqual(calc.calc_store(STORE, [sector(3)], compensated, ASSUMPTIONS)["counts"]["green"], 0)


class DaysUntilTest(unittest.TestCase):
    def test_counts_whole_days(self):
        self.assertEqual(calc.days_until("2026-12-16", "2026-11-02"), 44)
        self.assertEqual(calc.days_until("2026-12-16", "2026-12-16"), 0)
        self.assertEqual(calc.days_until("2026-12-16", "2026-12-20"), -4)


def fake_result(red=0, amber=0, green=0, hours=42, above=False, days=5, compensation=False):
    return {
        "counts": {"red": red, "amber": amber, "green": green},
        "rule": {
            "weekly_hours": hours,
            "max_work_days": days,
            "legal_weekly_limit": 42,
            "above_legal_limit": above,
            "days_need_compensation": compensation,
        },
    }


class VerdictTest(unittest.TestCase):
    def test_counts_red_sectors(self):
        self.assertEqual(
            calc.verdict(fake_result(red=2)), {"status": "red", "title": "Atenção: 2 setores no vermelho"}
        )
        self.assertEqual(calc.verdict(fake_result(red=1))["title"], "Atenção: 1 setor no vermelho")

    def test_counts_amber_when_none_red(self):
        self.assertEqual(
            calc.verdict(fake_result(amber=1)), {"status": "amber", "title": "Cuidado: 1 setor pede ajuste"}
        )
        self.assertEqual(calc.verdict(fake_result(amber=3))["title"], "Cuidado: 3 setores pedem ajuste")

    def test_calm_when_all_green(self):
        self.assertEqual(
            calc.verdict(fake_result(green=4)),
            {"status": "green", "title": "Tranquilo: dá para ajustar a escala"},
        )

    def test_never_calm_above_legal_limit(self):
        self.assertEqual(
            calc.verdict(fake_result(green=4, hours=44, above=True)),
            {"status": "amber", "title": "Cuidado: 44h passa do limite de 42h"},
        )

    def test_warns_about_more_than_5_days(self):
        self.assertEqual(
            calc.verdict(fake_result(green=4, days=6, compensation=True)),
            {"status": "amber", "title": "Cuidado: 6 dias por semana pedem regime compensatório"},
        )


TODAY = "2026-11-02"


def run_scenarios(sectors=None, overrides=None):
    sectors = EXAMPLE_SECTORS if sectors is None else sectors
    store = {**STORE, "overrides": overrides}

    def at(scenario):
        return calc.calc_store(
            store, sectors, calc.rule_for_scenario(scenario, PARAMS, overrides, TODAY), ASSUMPTIONS
        )

    return at("without_agreement"), at("with_agreement")


class ActionsTest(unittest.TestCase):
    def test_lists_example_store_at_42h_in_order(self):
        without, with_ = run_scenarios()
        self.assertEqual(
            calc.build_actions(with_, {"without": without, "with": with_}),
            [
                "Procure seu sindicato antes de 16/12/2026. Com acordo coletivo dá para trabalhar 8h24 por dia até 16/12/2027. Sem ele, pela nossa leitura do texto, o limite é 8h por dia: 176h a menos por semana, em vez de 88h.",
                "Comece a contratar para caixa e reposição.",
                "Açougueiro é difícil de achar: comece a procurar agora.",
                "Treine gente para cobrir mais de um setor. É isso que aproxima você de 3 contratações, e não de 6.",
                "Padaria, hortifrúti e recebimento perdem pouco: ajuste a escala antes de contratar.",
                "Monte a escala pensando no domingo: a regra prefere uma das folgas nesse dia, e é dia de loja cheia.",
            ],
        )

    def test_no_past_date_after_rule_starts(self):
        without, with_ = run_scenarios()
        first = calc.build_actions(with_, {"without": without, "with": with_}, "2027-03-10")[0]
        self.assertEqual(
            first,
            "Procure seu sindicato. Com acordo coletivo dá para trabalhar 8h24 por dia até 16/12/2027. Sem ele, pela nossa leitura do texto, o limite é 8h por dia: 176h a menos por semana, em vez de 88h.",
        )

    def test_skips_union_item_with_single_scenario(self):
        _, with_ = run_scenarios()
        self.assertNotIn("sindicato", " ".join(calc.build_actions(with_)))

    def test_starts_with_lawyer_check_above_limit(self):
        _, with_ = run_scenarios(overrides={"weekly_hours_override": 44})
        self.assertEqual(
            calc.build_actions(with_)[0],
            "A jornada de 44h que você informou passa do limite de 42h. Confirme com seu advogado se a sua convenção permite isso.",
        )

    def test_starts_with_lawyer_check_above_5_days(self):
        _, with_ = run_scenarios(overrides={"max_work_days_override": 6})
        self.assertEqual(
            calc.build_actions(with_)[0],
            "Mais de 5 dias por semana só com regime compensatório em convenção ou acordo coletivo. Confirme com seu advogado.",
        )

    def test_no_training_item_without_range(self):
        single = [{**EXAMPLE_SECTORS[0], "headcount": 10, "min_simultaneous_staff": None}]
        _, with_ = run_scenarios(single)
        self.assertEqual(with_["min_additional"], with_["max_additional"])
        self.assertNotIn("Treine", " ".join(calc.build_actions(with_)))

    def test_no_butcher_item_when_butcher_green(self):
        small = [{**EXAMPLE_SECTORS[2], "headcount": 1}]
        _, with_ = run_scenarios(small)
        self.assertNotIn("Açougueiro", " ".join(calc.build_actions(with_)))

    def test_reviews_amber_sectors_other_than_butcher(self):
        amber = [{**EXAMPLE_SECTORS[3], "headcount": 6}]
        _, with_ = run_scenarios(amber)
        self.assertIn("Padaria: reveja a escala e acompanhe de perto.", calc.build_actions(with_))


class DeadlineTest(unittest.TestCase):
    def test_format_date(self):
        from brand import format_date_br

        self.assertEqual(format_date_br("2026-12-16"), "16/12/2026")

    def test_counts_days_before_rule(self):
        self.assertEqual(calc.deadline_text(PARAMS, "2026-11-02"), "Faltam 44 dias para a nova regra (16/12/2026)")

    def test_singular_on_last_day(self):
        self.assertEqual(calc.deadline_text(PARAMS, "2026-12-15"), "Falta 1 dia para a nova regra (16/12/2026)")

    def test_in_force(self):
        for today in ("2026-12-16", "2026-12-20"):
            with self.subTest(today=today):
                self.assertEqual(
                    calc.deadline_text(PARAMS, today),
                    "Regra em vigor desde 16/12/2026. As 40h para todos chegam em 16/12/2027.",
                )

    def test_names_last_phase(self):
        self.assertEqual(calc.deadline_text(PARAMS, "2027-12-20"), "Regra em vigor desde 16/12/2027")

    def test_never_negative_count(self):
        self.assertNotIn("-", calc.deadline_text(PARAMS, "2028-01-01"))


def example_input(**extra):
    data = {"today": TODAY, "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)}
    data.update(extra)
    return data


class ValidateTest(unittest.TestCase):
    def test_valid_input_has_no_errors(self):
        self.assertEqual(calc.validate(example_input()), [])

    def test_validate_rejects_bad_input(self):
        for bad in ("3,5", -1, 2.5):
            with self.subTest(headcount=bad):
                data = example_input()
                data["sectors"][1]["headcount"] = bad
                errors = calc.validate(data)
                self.assertEqual(len(errors), 1)
                self.assertIn("Setor 2 (Reposição)", errors[0])
                self.assertIn("pessoas", errors[0])
        data = example_input()
        data["store"]["days_open_per_week"] = 5
        self.assertEqual(
            [e for e in calc.validate(data) if "days_open_per_week" in e],
            ["Dias abertos por semana (days_open_per_week) precisa ser 6 ou 7."],
        )
        data = example_input()
        data["sectors"][2]["avg_monthly_salary"] = -100
        errors = calc.validate(data)
        self.assertTrue(any("Setor 3 (Açougue)" in e and "salário" in e for e in errors))

    def test_message_format(self):
        data = example_input()
        data["sectors"][2]["headcount"] = "x"
        self.assertEqual(
            calc.validate(data),
            ["Setor 3 (Açougue): pessoas precisa ser um número inteiro maior ou igual a zero."],
        )

    def test_needs_someone(self):
        data = example_input()
        for s in data["sectors"]:
            s["headcount"] = 0
        self.assertTrue(calc.validate(data))

    def test_salary_required_when_people(self):
        data = example_input()
        data["sectors"][0]["avg_monthly_salary"] = 0
        self.assertTrue(any("Setor 1 (Caixa)" in e for e in calc.validate(data)))

    def test_bad_date_and_unknown_override(self):
        self.assertTrue(calc.validate(example_input(today="02/11/2026")))
        self.assertTrue(calc.validate(example_input(params_override={"nao_existe": 1})))

    def test_not_an_object(self):
        self.assertTrue(calc.validate([1, 2]))

    def test_network_errors_name_the_store(self):
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja A", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja B", "store": {**STORE, "days_open_per_week": 5}, "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
            ],
        }
        errors = calc.validate(data)
        self.assertEqual(len(errors), 1)
        self.assertIn("Loja B", errors[0])


class RunTest(unittest.TestCase):
    def test_single_store_shape(self):
        out = calc.run(example_input())
        self.assertEqual(out["skill"], "fim-escala-6x1")
        self.assertEqual(out["checked_at"], PARAMS["version"])
        self.assertEqual(out["params_version"], PARAMS["version"])
        self.assertEqual(out["overridden"], [])
        self.assertEqual(out["today"], TODAY)
        self.assertEqual(out["deadline"], "Faltam 44 dias para a nova regra (16/12/2026)")
        self.assertEqual(list(out["scenarios"]), ["without_agreement", "with_agreement"])
        for sc in out["scenarios"].values():
            self.assertEqual(set(sc), {"result", "verdict", "actions"})
        self.assertEqual(out["scenarios"]["with_agreement"]["result"]["max_additional"], 6)
        json.dumps(out, ensure_ascii=False)

    def test_params_override_is_reported(self):
        out = calc.run(example_input(params_override={"daily_hours_limit": 7}))
        self.assertEqual(out["scenarios"]["without_agreement"]["result"]["rule"]["weekly_hours"], 35)
        self.assertEqual(out["overridden"], ["daily_hours_limit"])
        self.assertEqual(out["params_version"], PARAMS["version"] + "+override")
        self.assertEqual(out["checked_at"], PARAMS["version"])

    def test_load_params_override(self):
        params, assumptions, keys = calc.load_params({"daily_hours_limit": 7, "overtime_multiplier": 2})
        self.assertEqual(params["daily_hours_limit"], 7)
        self.assertEqual(assumptions["overtime_multiplier"], 2)
        self.assertEqual(sorted(keys), ["daily_hours_limit", "overtime_multiplier"])
        self.assertEqual(calc.load_params()[0]["daily_hours_limit"], 8)

    def test_network_sums_stores(self):
        one = calc.run(example_input())
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja A", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja B", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
            ],
        }
        out = calc.run(data)
        self.assertEqual([s["name"] for s in out["stores"]], ["Loja A", "Loja B"])
        net = out["network"]["without_agreement"]
        single = one["scenarios"]["without_agreement"]["result"]
        self.assertEqual(net["max_additional"], 2 * single["max_additional"])
        self.assertAlmostEqual(net["max_monthly_cost"], 2 * single["max_monthly_cost"])
        self.assertEqual(net["total_lost_hours"], 2 * single["total_lost_hours"])
        self.assertEqual(
            net["counts"]["red"], 2 * single["counts"]["red"]
        )
        self.assertEqual(
            set(net),
            {"min_additional", "max_additional", "min_monthly_cost", "max_monthly_cost",
             "min_annual_cost", "max_annual_cost", "total_lost_hours", "counts"},
        )

    def test_after_phase2_single_scenario(self):
        out = calc.run(example_input(today="2027-12-16"))
        self.assertEqual(list(out["scenarios"]), ["without_agreement"])

    def test_top_level_overrides(self):
        out = calc.run(example_input(overrides={"weekly_hours_override": 41}))
        self.assertEqual(list(out["scenarios"]), ["with_agreement"])
        self.assertEqual(out["scenarios"]["with_agreement"]["result"]["rule"]["weekly_hours"], 41)

    def test_integral_numbers_serialize_as_ints(self):
        text = json.dumps(calc.run(example_input()))
        self.assertIn('"total_lost_hours": 88,', text)

    def test_sectors_sorted_by_lost_hours(self):
        out = calc.run(example_input())
        lost = [s["lost_hours"] for s in out["scenarios"]["with_agreement"]["result"]["sectors"]]
        self.assertEqual(lost, sorted(lost, reverse=True))

    def test_no_dashes_in_texts(self):
        out = calc.run(example_input())
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(EM, text)
        self.assertNotIn(EN, text)


class CliTest(unittest.TestCase):
    script = str(SKILL / "scripts" / "calc.py")

    def call(self, stdin=None, args=()):
        return subprocess.run(
            [sys.executable, self.script, *args], input=stdin, capture_output=True, text=True, encoding="utf-8"
        )

    def test_stdin_ok(self):
        p = self.call(json.dumps(example_input()))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["skill"], "fim-escala-6x1")

    def test_input_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dados.json"
            path.write_text(json.dumps(example_input()), encoding="utf-8")
            p = self.call(args=("--input", str(path)))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Reposição", p.stdout)

    def test_validation_error_exit_2_without_traceback(self):
        data = example_input()
        data["sectors"][0]["headcount"] = "3,5"
        p = self.call(json.dumps(data))
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)
        self.assertTrue(json.loads(p.stdout)["errors"])

    def test_invalid_json_exit_2(self):
        p = self.call("{nao e json")
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)
        self.assertTrue(json.loads(p.stdout)["errors"])

    def test_missing_file_exit_2(self):
        p = self.call(args=("--input", "/nao/existe.json"))
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)


class FixRound1Test(unittest.TestCase):
    script = str(SKILL / "scripts" / "calc.py")

    def cli(self, data):
        return subprocess.run(
            [sys.executable, self.script], input=json.dumps(data), capture_output=True, text=True, encoding="utf-8"
        )

    def assert_clean_rejection(self, data):
        p = self.cli(data)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        self.assertTrue(json.loads(p.stdout)["errors"])

    def test_bad_params_override_values(self):
        for bad in (
            {"daily_hours_limit": "x"},
            {"daily_hours_limit": 0},
            {"phases": []},
            {"phases": [PARAMS["phases"][0]]},
            {"phases": [{**PARAMS["phases"][0], "starts_on": "x"}, PARAMS["phases"][1]]},
            {"phases": [{**PARAMS["phases"][0], "weekly_hours": 0}, PARAMS["phases"][1]]},
            {"phases": [{**PARAMS["phases"][0], "max_work_days": 8}, PARAMS["phases"][1]]},
            {"overtime_divisor_per_weekly_hour": 0},
            {"weeks_per_month": "a"},
            {"current": {"weekly_hours": 0, "max_work_days": 6}},
        ):
            with self.subTest(bad=bad):
                self.assert_clean_rejection(example_input(params_override=bad))

    def test_bad_top_level_overrides_in_network_mode(self):
        data = {
            "today": TODAY,
            "overrides": "abc",
            "stores": [{"name": "A", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)}],
        }
        self.assertTrue(calc.validate(data))
        self.assert_clean_rejection(data)

    def test_max_work_days_override_range(self):
        for bad in (0.5, 8, 5.5, "5"):
            with self.subTest(bad=bad):
                self.assertTrue(calc.validate(example_input(overrides={"max_work_days_override": bad})))
        self.assertEqual(calc.validate(example_input(overrides={"max_work_days_override": 6})), [])

    def test_current_work_days_and_null_hours(self):
        data = example_input()
        data["sectors"][0]["current_work_days"] = 9
        self.assertTrue(any("Setor 1" in e and "dias" in e for e in calc.validate(data)))
        data = example_input()
        data["sectors"][0]["current_weekly_hours"] = None
        self.assertTrue(any("Setor 1" in e for e in calc.validate(data)))

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
