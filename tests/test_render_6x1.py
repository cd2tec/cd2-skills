"""Testes da entrega da skill fim-escala-6x1 (render.py e template.html)."""
import codecs
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSON = codecs.decode("Tnoevry", "rot13")  # nome próprio que nenhum arquivo pode citar
SKILL = ROOT / "core" / "cd2-varejo" / "skills" / "fim-escala-6x1"
sys.path.insert(0, str(ROOT / "core" / "cd2-varejo" / "shared" / "scripts"))
sys.path.insert(0, str(SKILL / "scripts"))

import calc  # noqa: E402
import render  # noqa: E402
import brand  # noqa: E402
from brand import format_brl_compact  # noqa: E402

TODAY = "2026-11-07"
STORE = {"days_open_per_week": 7, "hours_open_per_day": 13, "payroll_charges_factor": 0.7}
EXAMPLE_SECTORS = [
    {"name": "Caixa", "headcount": 14, "avg_monthly_salary": 1900, "min_simultaneous_staff": 5},
    {"name": "Reposição", "headcount": 12, "avg_monthly_salary": 1900},
    {"name": "Açougue", "headcount": 6, "avg_monthly_salary": 2600},
    {"name": "Padaria", "headcount": 5, "avg_monthly_salary": 2300},
    {"name": "Hortifrúti", "headcount": 4, "avg_monthly_salary": 2000},
    {"name": "Recebimento", "headcount": 3, "avg_monthly_salary": 2100},
]
FORMATS = ("html", "csv", "whatsapp", "markdown")
EM, EN = chr(0x2014), chr(0x2013)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def example_input(**extra):
    data = {"today": TODAY, "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)}
    data.update(extra)
    return data


def output(**extra):
    data = example_input(**extra)
    assert calc.validate(data) == [], calc.validate(data)
    return calc.run(data)


def html(**extra):
    return render.render(output(**extra), "html")


class HtmlTest(unittest.TestCase):
    def test_html_has_signature_footer(self):
        page = html()
        self.assertIn('class="cd2-assinatura"', page)
        self.assertIn("<svg", page)
        self.assertIn("Emenda Constitucional 141/2026", page)
        self.assertIn("02/11/2026", page)  # data de conferência dos parâmetros

    def test_html_embeds_base_css(self):
        page = html()
        self.assertIn(".cd2-logo--dark { display: none; }", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))

    def test_html_highlights_verdict_and_range(self):
        out = output()
        page = render.render(out, "html")
        self.assertIn(out["scenarios"]["without_agreement"]["verdict"]["title"], page)
        min_cost = out["scenarios"]["without_agreement"]["result"]["min_monthly_cost"]
        self.assertEqual(format_brl_compact(min_cost), "R$ 17,5 mil")
        self.assertIn("R$ 17,5 mil", page)
        self.assertIn('class="display-lg"', page)

    def test_html_shows_both_scenarios_before_phase2(self):
        page = html()
        self.assertIn("Sem acordo coletivo", page)
        self.assertIn("Com acordo coletivo", page)
        later = html(today="2027-12-16")
        self.assertNotIn("Com acordo coletivo", later)

    def test_status_labels_are_textual(self):
        page = html()
        for label in ("Apertado", "Atenção", "Tranquilo"):
            self.assertIn(f">{label}<", page)

    def test_escapes_sector_names(self):
        sectors = copy.deepcopy(EXAMPLE_SECTORS)
        sectors[0]["name"] = "<script>alert(1)</script>"
        sectors[1]["name"] = "Frios; laticínios"
        out = output(sectors=sectors)
        page = render.render(out, "html")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        sheet = render.render(out, "csv").lstrip("﻿")
        lines = sheet.splitlines()
        header_cols = len(lines[0].split(";"))
        row = next(line for line in lines if "laticínios" in line)
        self.assertIn('"Frios; laticínios"', row)
        cells = list(__import__("csv").reader([row], delimiter=";"))[0]
        self.assertEqual(len(cells), header_cols)

    def test_csv_blocks_formula_injection(self):
        sectors = copy.deepcopy(EXAMPLE_SECTORS)
        sectors[0]["name"] = "=HYPERLINK(1)"
        sheet = render.render(output(sectors=sectors), "csv")
        self.assertNotIn(";=HYPERLINK", sheet)
        self.assertIn("'=HYPERLINK", sheet)

    def test_empty_store_message(self):
        data = example_input(sectors=[{"name": "Caixa", "headcount": 0, "avg_monthly_salary": 1900}])
        errors = calc.validate(data)
        self.assertIn("Preencha as pessoas de pelo menos um setor.", errors)
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render({"errors": errors}, fmt)
                self.assertIn("Preencha as pessoas de pelo menos um setor.", text)
                if fmt == "html":
                    self.assertIn('class="cd2-assinatura"', text)
                    self.assertIn(".cd2-logo--dark { display: none; }", text)
                else:
                    self.assertIn("CD2 Tech", [line.strip('"') for line in text.lstrip("﻿").splitlines()])

    def test_result_without_people_falls_back_to_message(self):
        # run() sem passar pelo validate(): a entrega não quebra e explica o que falta.
        out = calc.run(example_input(sectors=[{"name": "Caixa", "headcount": 0, "avg_monthly_salary": 1900}]))
        page = render.render(out, "html")
        self.assertIn("Preencha as pessoas de pelo menos um setor.", page)

    def test_errors_are_escaped(self):
        page = render.render({"errors": ["Setor 1 (<b>x</b>): erro."]}, "html")
        self.assertNotIn("<b>x</b>", page)

    def test_override_is_disclosed(self):
        out = output(params_override={"daily_hours_limit": 7})
        self.assertEqual(out["overridden"], ["daily_hours_limit"])
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                self.assertIn("Parâmetro atualizado pela pesquisa", render.render(out, fmt))
        self.assertNotIn("Parâmetro atualizado pela pesquisa", html())

    def test_links_have_utm_and_site(self):
        page = html()
        self.assertIn("calc-fim-escala6x1.cd2.com.br/?utm_source={{UTM_SOURCE}}", page)
        self.assertIn("utm_campaign=fim-escala-6x1", page)
        self.assertIn("wa.me/5519982355172?text=", page)
        self.assertIn("archeo.cd2.com.br/?utm_source={{UTM_SOURCE}}", page)
        self.assertIn("calc-vrva.cd2.com.br/?utm_source={{UTM_SOURCE}}", page)

    def test_whatsapp_link_names_skill_and_platform(self):
        page = render.render(output(), "html", platform="Codex")
        href = re.search(r'href="(https://wa\.me/5519982355172\?text=[^"]+)"', page).group(1)
        message = urllib.parse.unquote(href.split("?text=", 1)[1])
        self.assertEqual(
            message,
            "Oi, vim pela skill Fim da escala 6x1 no Codex e quero falar sobre uso na minha empresa.",
        )

    def test_insights_rendered_escaped(self):
        page = render.render(output(), "html", insights=["<b>x</b>", "Padaria tem folga."])
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("Leitura da CD2", page)
        self.assertIn("Padaria tem folga.", page)

    def test_sources_and_profile(self):
        sources = [
            {"title": "Diário Oficial da União", "url": "https://www.in.gov.br/", "date": "2026-11-07"},
            {"title": "Link ruim", "url": "javascript:alert(1)", "date": "07/11/2026"},
        ]
        page = render.render(output(), "html", sources=sources, profile={"name": "Mercado <Bom> Preço", "role": "dono"})
        self.assertIn('href="https://www.in.gov.br/"', page)
        self.assertIn("07/11/2026", page)
        self.assertIn("Link ruim", page)
        self.assertNotIn("javascript:", page)
        self.assertIn("Mercado &lt;Bom&gt; Preço", page)
        self.assertIn("planalto.gov.br", page)

    def test_theme_attribute_only_on_html_tag(self):
        dark = render.render(output(), "html", theme="dark")
        self.assertIn('<html lang="pt-BR" data-theme="dark">', dark)
        self.assertEqual(dark.count("data-theme="), 1 + dark.count('[data-theme='))
        auto = render.render(output(), "html", theme="auto")
        self.assertIn('<html lang="pt-BR">', auto)
        self.assertIn("cd2-logo--dark", auto)

    def test_no_leftover_placeholders(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(output(), fmt, insights=["Um"])
                self.assertEqual(re.findall(r"\{\{(?!UTM_SOURCE\}\})[^}]*\}\}", text), [])

    def test_copy_has_no_dashes_or_emoji(self):
        outs = [output(), output(today="2027-12-16"), {"errors": ["x"]}]
        for out in outs:
            for fmt in FORMATS:
                with self.subTest(fmt=fmt):
                    text = render.render(out, fmt)
                    self.assertNotIn(EM, text)
                    self.assertNotIn(EN, text)
                    self.assertIsNone(EMOJI.search(text))
                    self.assertNotIn(PERSON, text)

    def test_convention_hours_single_scenario(self):
        page = html(overrides={"weekly_hours_override": 38})
        self.assertIn("Com a jornada da sua convenção", page)
        self.assertNotIn("Sem acordo coletivo", page)

    def test_network_renders_each_store(self):
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja Centro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja Bairro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS[:2])},
            ],
        }
        self.assertEqual(calc.validate(data), [])
        out = calc.run(data)
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                self.assertIn("Loja Centro", text)
                self.assertIn("Loja Bairro", text)
        net = out["network"]["without_agreement"]
        self.assertIn(format_brl_compact(net["max_monthly_cost"]), render.render(out, "html"))

    def test_network_mixed_agreements_note(self):
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja Centro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS),
                 "overrides": {"weekly_hours_override": 42}},
                {"name": "Loja Bairro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
            ],
        }
        out = calc.run(data)
        note = "Loja Centro entra com a jornada da própria convenção (42h)."
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                self.assertIn(note, render.render(out, fmt))
        # Os setores no vermelho listados batem com a contagem da soma, loja substituída incluída.
        text = render.render(out, "whatsapp")
        without = text.split("Sem acordo coletivo (40h)")[1].split("Com acordo coletivo")[0]
        self.assertIn("Loja Centro, setores no vermelho:", without)
        self.assertIn("Loja Bairro, setores no vermelho:", without)
        self.assertNotIn("entra com a jornada", render.render(calc.run({
            "today": TODAY,
            "stores": [
                {"name": "Loja A", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja B", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
            ],
        }), "html"))

    def test_bridge_does_not_assume_same_conversation(self):
        for fmt in ("html", "markdown"):
            text = render.render(output(), fmt)
            self.assertNotIn("nesta conversa", text)
            self.assertIn("custo-vrva", text)
            self.assertIn("calc-vrva.cd2.com.br/?utm_source={{UTM_SOURCE}}", text)

    def test_disclaimer_names_rule_after_date(self):
        for fmt in FORMATS:
            text = render.render(output(), fmt)
            self.assertIn("nossa leitura da regra em 02/11/2026 (Emenda Constitucional 141/2026)", text)

    def test_lower_bound_cost_wording(self):
        self.assertIn("custa o custo por pessoa do próprio setor", html())

    def test_user_placeholder_stays_literal(self):
        sectors = copy.deepcopy(EXAMPLE_SECTORS)
        sectors[0]["name"] = "{{FOOTER}}"
        page = render.render(output(sectors=sectors), "html", insights=["{{HERO}}"], profile={"name": "{{TITLE}}"})
        self.assertIn("{{HERO}}", page)
        self.assertIn("{{FOOTER}}", page)
        self.assertIn("{{TITLE}}", page)
        self.assertEqual(page.count('class="cd2-assinatura"'), 1)
        self.assertEqual(page.count('id="veredito"'), 1)

    def test_network_whatsapp_has_top_action_per_store(self):
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja Centro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja Bairro", "store": dict(STORE), "sectors": [dict(EXAMPLE_SECTORS[2], headcount=1)]},
            ],
        }
        out = calc.run(data)
        text = render.render(out, "whatsapp")
        for store in out["stores"]:
            first = store["scenarios"]["without_agreement"]["actions"][0]
            self.assertIn(f"{store['name']}: {first}", text)

    def test_commercial_text_states_free_testing(self):
        for fmt in ("html", "markdown"):
            with self.subTest(fmt=fmt):
                text = render.render(output(), fmt)
                self.assertNotIn("quanto quiser", text)
                self.assertIn("Testar na sua operação é livre.", text)
                self.assertIn("com suporte e responsabilidade, fale com a CD2", text)
        for fmt in FORMATS:
            self.assertNotIn("quanto quiser", render.render(output(), fmt))

    def test_header_dates_are_escaped(self):
        # Aqui o "hoje" precisa ser uma data válida (vira prazo); a data de conferência é texto livre.
        out = output()
        out["checked_at"] = "<script>alert(1)</script>"
        page = render.render(out, "html")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_network_red_line_wording(self):
        data = {
            "today": TODAY,
            "stores": [
                {"name": "Loja Centro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS)},
                {"name": "Loja Bairro", "store": dict(STORE), "sectors": copy.deepcopy(EXAMPLE_SECTORS[:2])},
            ],
        }
        text = render.render(calc.run(data), "whatsapp")
        self.assertNotIn("No vermelho em", text)
        self.assertIn("Loja Centro, setores no vermelho: Caixa, Reposição", text)
        single = render.render(output(), "whatsapp")
        self.assertIn("No vermelho: Caixa", single)

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            render.render(output(), "pdf")


class TextFormatsTest(unittest.TestCase):
    def test_text_formats_use_literal_name(self):
        out = output()
        for fmt in ("whatsapp", "csv", "markdown"):
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                lines = [line.strip('"') for line in text.lstrip("﻿").splitlines()]
                self.assertIn("CD2 Tech", lines)
                self.assertNotIn("<svg", text)
                self.assertIn("Emenda Constitucional 141/2026", text)

    def test_csv_header_and_rows(self):
        sheet = render.render(output(), "csv").lstrip("﻿")
        lines = sheet.splitlines()
        self.assertTrue(lines[0].startswith("Situação;Setor;Status"))
        self.assertTrue(any(line.startswith("\"Sem acordo, 40h\";Caixa;Apertado;14;56;2;6460") for line in lines))
        self.assertEqual(lines[-2].strip('"'), "CD2 Tech")

    def test_whatsapp_is_short_and_has_site(self):
        text = render.render(output(), "whatsapp")
        self.assertIn("calc-fim-escala6x1.cd2.com.br/?utm_source={{UTM_SOURCE}}", text)
        self.assertIn("R$ 17,5 mil", text)
        self.assertLess(len(text), 2500)

    def test_markdown_escapes_table_cells(self):
        sectors = copy.deepcopy(EXAMPLE_SECTORS)
        sectors[0]["name"] = "Frios | <b>x</b>"
        text = render.render(output(sectors=sectors), "markdown")
        self.assertNotIn("<b>x</b>", text)
        self.assertIn("Frios \\|", text)


class CliTest(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "render.py"), *args],
            input=stdin, capture_output=True, text=True, encoding="utf-8",
        )

    def test_cli_renders_calc_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "saida.json"
            insights = Path(tmp) / "insights.json"
            result.write_text(json.dumps(output(), ensure_ascii=False), encoding="utf-8")
            insights.write_text(json.dumps(["Padaria tem folga."], ensure_ascii=False), encoding="utf-8")
            done = self.run_cli("--result", str(result), "--format", "html", "--insights", str(insights), "--theme", "dark")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('data-theme="dark"', done.stdout)
            self.assertIn("Padaria tem folga.", done.stdout)

    def test_cli_renders_errors_payload(self):
        done = self.run_cli("--format", "whatsapp", stdin=json.dumps({"errors": ["Preencha as pessoas de pelo menos um setor."]}))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Preencha as pessoas de pelo menos um setor.", done.stdout)

    def test_cli_unexpected_error_is_clean_json_plus_stderr(self):
        done = self.run_cli("--format", "html", stdin=json.dumps({"scenarios": {"without_agreement": {}}}))
        self.assertEqual(done.returncode, 2)
        self.assertIn("Erro inesperado", json.loads(done.stdout)["errors"][0])
        self.assertIn("KeyError", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_cli_without_result_on_tty_does_not_hang(self):
        import os
        import pty
        master, slave = pty.openpty()
        try:
            done = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "render.py"), "--format", "html"],
                stdin=slave, capture_output=True, text=True, encoding="utf-8", timeout=20,
            )
        finally:
            os.close(slave)
            os.close(master)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--result", json.loads(done.stdout)["errors"][0])

    def test_cli_bad_input_exits_2_without_traceback(self):
        done = self.run_cli("--format", "html", stdin="isto não é json")
        self.assertEqual(done.returncode, 2)
        self.assertIn("errors", json.loads(done.stdout))
        self.assertNotIn("Traceback", done.stderr)


class SkillDocTest(unittest.TestCase):
    def test_skill_md_frontmatter_and_references(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: fim-escala-6x1\ndescription: "))
        for trigger in ("escala 6x1", "5x2", "40 horas", "fim da 6x1", "EC 141", "quantas pessoas vou precisar contratar", "jornada"):
            self.assertIn(trigger, text.split("---", 2)[1])
        for ref in ("references/fluxo-conversa.md", "references/marca.md", "references/metodologia.md",
                    "scripts/calc.py", "scripts/render.py"):
            self.assertIn(ref, text)
        shared = ROOT / "core" / "cd2-varejo" / "shared"
        kit = ROOT / "core" / "cd2-varejo" / "kits" / "calculadora"
        for ref in re.findall(r"`((?:references|scripts|assets)/[^`]+)`", text):
            self.assertTrue((SKILL / ref).exists() or (shared / ref).exists() or (kit / ref).exists(), ref)

    def test_skill_md_footer_matches_brand(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        block = re.search(r"```text\n(.*?)\n```", text, re.S).group(1)
        self.assertEqual(block, brand.footer_text("Emenda Constitucional 141/2026", "02/11/2026"))

    def test_skill_md_runs_scripts_from_working_folder(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("python3 <pasta da skill>/scripts/calc.py", text)
        self.assertIn("python3 <pasta da skill>/scripts/render.py", text)
        self.assertIn("pasta de trabalho", text)

    def test_limits_match_methodology(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
        method = (SKILL / "references" / "metodologia.md").read_text(encoding="utf-8").lower()
        page = html().lower()
        for needle in ("cláusulas coletivas incompatíveis", "terceirizados da administração pública",
                       "ganho de escala entre lojas", "adicional noturno", "rotatividade"):
            for name, text in (("SKILL.md", skill), ("metodologia.md", method), ("html", page)):
                self.assertIn(needle, text, f"{needle} em {name}")

    def test_docs_have_no_dashes_emoji_or_personal_name(self):
        for name in ("SKILL.md", "references/metodologia.md"):
            text = (SKILL / name).read_text(encoding="utf-8")
            self.assertNotIn(EM, text, name)
            self.assertNotIn(EN, text, name)
            self.assertIsNone(EMOJI.search(text), name)
            self.assertNotIn(PERSON, text, name)
            self.assertNotIn(" tela", text, name)

    def test_skill_md_example_input_runs(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S) if '"sectors"' in b and "{...}" not in b]
        self.assertEqual(len(blocks), 1)
        data = blocks[0]
        self.assertEqual(calc.validate(data), [])
        self.assertIn("Com a jornada da sua convenção", render.render(calc.run(data), "html"))


if __name__ == "__main__":
    unittest.main()
