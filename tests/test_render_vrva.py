"""Testes da entrega da skill custo-vrva (render.py e template.html)."""
import codecs
import copy
import csv
import importlib.util
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
render = load_module("custo_vrva_render", SKILL / "scripts" / "render.py")
import brand  # noqa: E402

TODAY = "2026-11-07"
BAKERY = [
    {"name": "Alelo", "sales": 18000, "rate": 6.5, "days": 30},
    {"name": "Pluxee (Sodexo)", "sales": 12000, "rate": 5.9, "days": 30},
    {"name": "Ticket", "sales": 10000, "rate": 6.0, "days": 32},
    {"name": "VR", "sales": 8000, "rate": 4.5, "days": 25},
]
FORMATS = ("html", "csv", "whatsapp", "markdown")
REGRA = "Decreto 12.712/2025"
CHECKED = "06/11/2026"
EM, EN = chr(0x2014), chr(0x2013)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def example_input(**extra):
    data = {"today": TODAY, "brands": copy.deepcopy(BAKERY), "money_cost_month_percent": 2}
    data.update(extra)
    return data


def output(**extra):
    data = example_input(**extra)
    assert calc.validate(data) == [], calc.validate(data)
    return calc.run(data)


def html(**extra):
    return render.render(output(**extra), "html")


def network_output():
    data = {
        "today": TODAY,
        "stores": [
            {"name": "Loja Centro", "brands": copy.deepcopy(BAKERY)},
            {"name": "Loja Bairro", "brands": [{"name": "VR", "sales": 5000, "rate": 3, "days": 10}]},
        ],
    }
    assert calc.validate(data) == [], calc.validate(data)
    return calc.run(data)


class HtmlTest(unittest.TestCase):
    def test_html_has_signature_footer(self):
        page = html()
        self.assertIn('class="cd2-assinatura"', page)
        self.assertIn("<svg", page)
        self.assertIn(REGRA, page)
        self.assertIn(CHECKED, page)
        self.assertIn(".cd2-logo--dark { display: none; }", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))

    def test_disclaimer_names_rule_after_date(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(output(), fmt)
                self.assertIn(f"nossa leitura da regra em {CHECKED} ({REGRA})", text)

    def test_total_in_highlight(self):
        page = html()
        self.assertIn("R$ 1.576,67", page)
        self.assertIn("R$ 18.920,00", page)
        hero = re.search(r'<section class="bloco veredito.*?</section>', page, re.S).group(0)
        self.assertIn('class="stat', hero)
        self.assertIn("R$ 1.576,67", hero)
        self.assertIn("R$ 18.920,00", hero)
        self.assertIn("Acima da regra em 4 de 4 bandeiras", hero)

    def test_two_separate_cards(self):
        page = html()
        self.assertIn("Taxa acima do teto de 3,6%", page)
        self.assertIn("R$ 1.110,00 por mês", page)
        self.assertIn("Dinheiro parado além de 15 dias", page)
        self.assertIn("R$ 23.333,33 presos", page)
        self.assertIn("Custam R$ 466,67 por mês, a 2% ao mês.", page)

    def test_all_green(self):
        page = html(brands=[{"name": "VR", "sales": 5000, "rate": 3, "days": 10}])
        self.assertIn("Dentro da regra em todas as bandeiras", page)
        self.assertIn("Nenhuma bandeira cobra acima de 3,6%.", page)
        self.assertIn("Todas as bandeiras pagam em até 15 dias.", page)

    def test_status_labels_are_textual(self):
        brands = copy.deepcopy(BAKERY) + [{"name": "Caju", "sales": 3000, "rate": 3.5, "days": 10}]
        page = html(brands=brands)
        for label in ("Acima", "Pouco acima", "Dentro"):
            self.assertIn(f">{label}<", page)

    def test_judicial_status_with_date_and_sources(self):
        page = html()
        self.assertIn("As grandes operadoras ainda contestam o decreto na Justiça.", page)
        self.assertIn("Situação conferida em 06/11/2026", page)
        for url in calc.load_params()[0]["judicial_status"]["sources"]:
            self.assertIn(f'href="{url}"', page)

    def test_judicial_override_filters_bad_urls(self):
        status = {"text": "Nova decisão <b>x</b>.", "checked_at": "2026-11-07",
                  "sources": ["javascript:alert(1)", "https://www.stf.jus.br/"]}
        out = output(params_override={"judicial_status": status})
        page = render.render(out, "html")
        self.assertIn("Nova decisão &lt;b&gt;x&lt;/b&gt;.", page)
        self.assertIn("Situação conferida em 07/11/2026", page)
        self.assertIn('href="https://www.stf.jus.br/"', page)
        self.assertNotIn("javascript:", page)
        self.assertIn("Parâmetro atualizado pela pesquisa", page)

    def test_interoperability_section(self):
        page = html()
        self.assertIn("O que muda com a interoperabilidade (07/11/2026)", page)
        self.assertIn("Qualquer maquininha passa a poder aceitar qualquer cartão de vale", page)

    def test_escapes_brand_names(self):
        brands = copy.deepcopy(BAKERY)
        brands[0]["name"] = "<script>alert(1)</script>"
        page = render.render(output(brands=brands), "html")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_csv_quotes_brand_with_separator(self):
        brands = copy.deepcopy(BAKERY)
        brands[1]["name"] = "Caju; Flash"
        sheet = render.render(output(brands=brands), "csv").lstrip("﻿")
        lines = sheet.splitlines()
        header_cols = len(lines[0].split(";"))
        row = next(line for line in lines if "Flash" in line)
        self.assertIn('"Caju; Flash"', row)
        cells = list(csv.reader([row], delimiter=";"))[0]
        self.assertEqual(len(cells), header_cols)

    def test_csv_blocks_formula_injection(self):
        brands = copy.deepcopy(BAKERY)
        brands[0]["name"] = "=HYPERLINK(1)"
        sheet = render.render(output(brands=brands), "csv")
        self.assertNotIn(";=HYPERLINK", sheet)
        self.assertNotIn("\r\n=HYPERLINK", sheet)
        self.assertIn("'=HYPERLINK", sheet)

    def test_empty_store_message(self):
        data = example_input(brands=[dict(b, sales=0) for b in BAKERY])
        out = calc.run(data)
        self.assertEqual(out["result"]["counted"], 0)
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                self.assertIn("Nenhuma bandeira com vendas no mês", text)
                self.assertNotIn("R$ 0,00 por mês a mais", text)

    def test_errors_payload_all_formats(self):
        errors = calc.validate(example_input(brands=[dict(b, sales=0) for b in BAKERY]))
        self.assertEqual(errors, ["Preencha as vendas de pelo menos uma bandeira."])
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render({"errors": errors}, fmt)
                self.assertIn("Preencha as vendas de pelo menos uma bandeira.", text)
                if fmt == "html":
                    self.assertIn('class="cd2-assinatura"', text)
                    self.assertIn(".cd2-logo--dark { display: none; }", text)
                else:
                    self.assertIn("CD2 Tech", [line.strip('"') for line in text.lstrip("﻿").splitlines()])

    def test_errors_are_escaped(self):
        page = render.render({"errors": ["Bandeira 1 (<b>x</b>): erro."]}, "html")
        self.assertNotIn("<b>x</b>", page)

    def test_override_is_disclosed(self):
        out = output(params_override={"mdr_cap_percent": 3.0})
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                self.assertIn("Parâmetro atualizado pela pesquisa", text)
                self.assertIn("teto da taxa", text)
        page = render.render(out, "html")
        self.assertIn("Taxa acima do teto de 3%", page)
        self.assertNotIn("Parâmetro atualizado pela pesquisa", html())

    def test_links_have_utm_and_site(self):
        page = html()
        self.assertIn("calc-vrva.cd2.com.br/?utm_source={{UTM_SOURCE}}&amp;utm_medium=skill&amp;utm_campaign=custo-vrva", page)
        self.assertIn("calc-fim-escala6x1.cd2.com.br/?utm_source={{UTM_SOURCE}}&amp;utm_medium=skill&amp;utm_campaign=custo-vrva", page)
        self.assertIn("cd2.com.br/?utm_source={{UTM_SOURCE}}", page)
        self.assertIn("archeo.cd2.com.br/?utm_source={{UTM_SOURCE}}", page)
        self.assertIn("wa.me/5519982355172?text=", page)
        for fmt in ("whatsapp", "markdown"):
            with self.subTest(fmt=fmt):
                self.assertIn("calc-vrva.cd2.com.br/?utm_source={{UTM_SOURCE}}&utm_medium=skill&utm_campaign=custo-vrva",
                              render.render(output(), fmt))

    def test_whatsapp_link_names_skill_and_platform(self):
        page = render.render(output(), "html", platform="Codex")
        href = re.search(r'href="(https://wa\.me/5519982355172\?text=[^"]+)"', page).group(1)
        message = urllib.parse.unquote(href.split("?text=", 1)[1])
        self.assertEqual(
            message,
            "Oi, vim pela skill Quanto o VR/VA custa de verdade no Codex e quero falar sobre uso na minha empresa.",
        )

    def test_insights_rendered_escaped(self):
        page = render.render(output(), "html", insights=["<b>x</b>", "A Alelo puxa um terço do custo."])
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("Leitura da CD2", page)
        self.assertIn("A Alelo puxa um terço do custo.", page)

    def test_sources_and_profile(self):
        sources = [
            {"title": "Diário Oficial da União", "url": "https://www.in.gov.br/", "date": "2026-11-07"},
            {"title": "Link ruim", "url": "javascript:alert(1)", "date": "07/11/2026"},
        ]
        page = render.render(output(), "html", sources=sources, profile={"name": "Padaria <Pão> Bom", "role": "dono"})
        self.assertIn('href="https://www.in.gov.br/"', page)
        self.assertIn("07/11/2026", page)
        self.assertIn("Link ruim", page)
        self.assertNotIn("javascript:", page)
        self.assertIn("Padaria &lt;Pão&gt; Bom", page)
        self.assertIn("planalto.gov.br", page)

    def test_theme_attribute_only_on_html_tag(self):
        dark = render.render(output(), "html", theme="dark")
        self.assertIn('<html lang="pt-BR" data-theme="dark">', dark)
        self.assertEqual(dark.count("data-theme="), 1 + dark.count("[data-theme="))
        auto = render.render(output(), "html", theme="auto")
        self.assertIn('<html lang="pt-BR">', auto)
        self.assertIn("cd2-logo--dark", auto)

    def test_no_leftover_placeholders(self):
        for out in (output(), network_output(), {"errors": ["x"]}):
            for fmt in FORMATS:
                with self.subTest(fmt=fmt):
                    text = render.render(out, fmt, insights=["Um"])
                    self.assertEqual(re.findall(r"\{\{(?!UTM_SOURCE\}\})[^}]*\}\}", text), [])

    def test_copy_has_no_dashes_or_emoji(self):
        outs = [output(), network_output(), output(brands=[{"name": "VR", "sales": 1, "rate": 3, "days": 1}]),
                {"errors": ["x"]}]
        for out in outs:
            for fmt in FORMATS:
                with self.subTest(fmt=fmt):
                    text = render.render(out, fmt)
                    self.assertNotIn(EM, text)
                    self.assertNotIn(EN, text)
                    self.assertIsNone(EMOJI.search(text))
                    self.assertNotIn(PERSON, text)
                    self.assertNotIn("nesta conversa", text)

    def test_network_renders_each_store(self):
        out = network_output()
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                self.assertIn("Loja Centro", text)
                self.assertIn("Loja Bairro", text)
        page = render.render(out, "html")
        self.assertIn(brand.format_brl(out["network"]["total_month"]), page)
        self.assertIn("Somando as 2 lojas da rede.", page)

    def test_bridge_points_to_6x1_and_agents(self):
        for fmt in ("html", "markdown"):
            with self.subTest(fmt=fmt):
                text = render.render(output(), fmt)
                self.assertIn("fim-escala-6x1", text)
                self.assertIn("agentes de IA", text)
                self.assertIn("calc-fim-escala6x1.cd2.com.br/", text)

    def test_how_we_calculate_uses_store_numbers(self):
        page = html()
        self.assertIn("Alelo: R$ 18.000,00 × (6,5% menos 3,6%) = R$ 522,00 por mês acima do teto.", page)
        self.assertIn("Ticket: R$ 10.000,00 ÷ 30 × 17 dias = R$ 5.666,67 parados, que custam R$ 113,33 por mês.", page)

    def test_user_placeholder_stays_literal(self):
        brands = copy.deepcopy(BAKERY)
        brands[0]["name"] = "{{FOOTER}}"
        page = render.render(output(brands=brands), "html", insights=["{{HERO}}"], profile={"name": "{{TITLE}}"})
        self.assertIn("{{HERO}}", page)
        self.assertIn("{{FOOTER}}", page)
        self.assertIn("{{TITLE}}", page)
        self.assertEqual(page.count('class="cd2-assinatura"'), 1)
        self.assertEqual(page.count('id="veredito"'), 1)

    def test_commercial_text_states_90_day_evaluation(self):
        for fmt in ("html", "markdown"):
            with self.subTest(fmt=fmt):
                text = render.render(output(), fmt)
                self.assertNotIn("quanto quiser", text)
                self.assertIn("Avaliar na sua operação é livre por até 90 dias.", text)
                self.assertIn("com suporte e responsabilidade, fale com a CD2", text)
        for fmt in FORMATS:
            self.assertNotIn("quanto quiser", render.render(output(), fmt))

    def test_header_dates_are_escaped(self):
        out = output()
        out["today"] = "<script>alert(1)</script>"
        out["checked_at"] = "<i>x</i>"
        page = render.render(out, "html")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("<i>x</i>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_unknown_format_and_theme(self):
        with self.assertRaises(ValueError):
            render.render(output(), "pdf")
        with self.assertRaises(ValueError):
            render.render(output(), "html", theme="sepia")


class TextFormatsTest(unittest.TestCase):
    def test_text_formats_use_literal_name(self):
        out = output()
        for fmt in ("whatsapp", "csv", "markdown"):
            with self.subTest(fmt=fmt):
                text = render.render(out, fmt)
                lines = [line.strip('"') for line in text.lstrip("﻿").splitlines()]
                self.assertIn("CD2 Tech", lines)
                self.assertNotIn("<svg", text)
                self.assertIn(REGRA, text)

    def test_csv_header_and_rows(self):
        sheet = render.render(output(), "csv")
        self.assertTrue(sheet.startswith("﻿"))
        lines = sheet.lstrip("﻿").split("\r\n")
        self.assertEqual(
            lines[0],
            "Bandeira;Vendas no mês (R$);Taxa (%);Acima do teto por mês (R$);Prazo (dias);Dias além do prazo;"
            "Dinheiro parado (R$);Custo do parado por mês (R$);Total por mês (R$);Situação",
        )
        self.assertIn("Alelo;18000,00;6,5;522,00;30;15;9000,00;180,00;702,00;Acima", lines)
        self.assertIn("Ticket;10000,00;6;240,00;32;17;5666,67;113,33;353,33;Acima", lines)
        self.assertIn("VR;8000,00;4,5;72,00;25;10;2666,67;53,33;125,33;Pouco acima", lines)
        self.assertIn("Total;48000,00;;1110,00;;;23333,33;466,67;1576,67;", lines)
        self.assertEqual(lines[-3].strip('"'), "CD2 Tech")

    def test_csv_network_has_store_column_and_network_total(self):
        lines = render.render(network_output(), "csv").lstrip("﻿").split("\r\n")
        self.assertTrue(lines[0].startswith("Loja;Bandeira;"))
        self.assertTrue(any(line.startswith("Loja Bairro;VR;5000,00;3;0,00;10;0;0,00;0,00;0,00;Dentro") for line in lines))
        self.assertTrue(any(line.startswith("Loja Centro;Total;48000,00;") for line in lines))
        self.assertTrue(any(line.startswith("Rede;Total;53000,00;") for line in lines))

    def test_whatsapp_is_short_and_has_site(self):
        text = render.render(output(), "whatsapp")
        self.assertIn("calc-vrva.cd2.com.br/?utm_source={{UTM_SOURCE}}", text)
        self.assertIn("R$ 1.576,67 por mês", text)
        self.assertIn("Bandeiras acima: Alelo, Pluxee (Sodexo), Ticket e VR.", text)
        self.assertIn("As grandes operadoras ainda contestam o decreto na Justiça.", text)
        self.assertLess(len(text), 2500)

    def test_markdown_escapes_table_cells(self):
        brands = copy.deepcopy(BAKERY)
        brands[0]["name"] = "Frios | <b>x</b>"
        text = render.render(output(brands=brands), "markdown")
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
            insights.write_text(json.dumps(["A Alelo puxa o custo."], ensure_ascii=False), encoding="utf-8")
            done = self.run_cli("--result", str(result), "--format", "html", "--insights", str(insights), "--theme", "dark")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('data-theme="dark"', done.stdout)
            self.assertIn("A Alelo puxa o custo.", done.stdout)

    def test_cli_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "entrega.csv"
            done = self.run_cli("--format", "csv", "--output", str(target), stdin=json.dumps(output()))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("1576,67", target.read_text(encoding="utf-8"))

    def test_cli_renders_errors_payload(self):
        done = self.run_cli("--format", "whatsapp", stdin=json.dumps({"errors": ["Preencha as vendas de pelo menos uma bandeira."]}))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Preencha as vendas de pelo menos uma bandeira.", done.stdout)

    def test_cli_unexpected_error_is_clean_json_plus_stderr(self):
        done = self.run_cli("--format", "html", stdin=json.dumps({"result": {"brands": [{}]}}))
        self.assertEqual(done.returncode, 2)
        self.assertIn("Erro inesperado", json.loads(done.stdout)["errors"][0])
        self.assertIn("KeyError", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_cli_wrong_shape(self):
        done = self.run_cli("--format", "html", stdin=json.dumps({"scenarios": {}}))
        self.assertEqual(done.returncode, 2)
        self.assertIn("saída do calc.py", json.loads(done.stdout)["errors"][0])

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
    def read(self, name):
        return (SKILL / name).read_text(encoding="utf-8")

    def test_skill_md_frontmatter_and_references(self):
        text = self.read("SKILL.md")
        self.assertTrue(text.startswith("---\nname: custo-vrva\ndescription: "))
        front = text.split("---", 2)[1]
        for trigger in ("vale-refeição", "vale-alimentação", "VR", "VA", "taxa da Alelo", "Ticket", "Pluxee",
                        "MDR", "3,6%", "repasse", "PAT", "Decreto 12.712", "quanto pago de taxa no vale"):
            self.assertIn(trigger, front)
        for ref in ("references/fluxo-conversa.md", "references/marca.md", "references/metodologia.md",
                    "references/bandeiras.md", "references/legal-params.json", "scripts/calc.py", "scripts/render.py"):
            self.assertIn(ref, text)
        shared = ROOT / "core" / "cd2-varejo" / "shared"
        for ref in re.findall(r"`((?:references|scripts|assets)/[^`]+)`", text):
            self.assertTrue((SKILL / ref).exists() or (shared / ref).exists(), ref)

    def test_skill_md_footer_matches_brand(self):
        block = re.search(r"```text\n(.*?)\n```", self.read("SKILL.md"), re.S).group(1)
        self.assertEqual(block, brand.footer_text(REGRA, CHECKED))

    def test_skill_md_runs_scripts_from_working_folder(self):
        text = self.read("SKILL.md")
        self.assertIn("python3 <pasta da skill>/scripts/calc.py", text)
        self.assertIn("python3 <pasta da skill>/scripts/render.py", text)
        self.assertIn("pasta de trabalho", text)

    def test_skill_md_research_and_consent(self):
        text = self.read("SKILL.md")
        for needle in ("situação judicial", "Comitê Gestor do PAT", "params_override", "Só com o sim da pessoa",
                       "extrato", "contrato", "06/11/2026"):
            self.assertIn(needle, text)

    def test_limits_match_methodology(self):
        skill = self.read("SKILL.md").lower()
        method = self.read("references/metodologia.md").lower()
        page = html().lower()
        for needle in ("tarifa de intercâmbio", "aluguel de maquininha", "antecipação", "impostos",
                       "situação judicial pode mudar quem precisa cumprir o decreto",
                       "comitê gestor do pat pode alterar o teto e o prazo"):
            for name, text in (("SKILL.md", skill), ("metodologia.md", method), ("html", page)):
                self.assertIn(needle, text, f"{needle} em {name}")

    def test_methodology_keeps_reference_values(self):
        method = self.read("references/metodologia.md")
        for needle in ("R$ 1.576,67 por mês", "R$ 18.920 por ano", "| Ticket | R$ 10.000 | 6,0% | 32 | R$ 240,00 | R$ 5.666,67 | R$ 113,33 |",
                       "Decreto 12.712/2025", "3,6%", "15 dias"):
            self.assertIn(needle, method)

    def test_bandeiras_lists_default_and_extra(self):
        text = self.read("references/bandeiras.md")
        for name in ("Alelo", "Pluxee (Sodexo)", "Ticket", "VR", "Flash", "Caju", "iFood Benefícios", "Swile"):
            self.assertIn(name, text)

    def test_docs_have_no_dashes_emoji_or_personal_name(self):
        for name in ("SKILL.md", "references/metodologia.md", "references/bandeiras.md"):
            text = self.read(name)
            self.assertNotIn(EM, text, name)
            self.assertNotIn(EN, text, name)
            self.assertIsNone(EMOJI.search(text), name)
            self.assertNotIn(PERSON, text, name)
            self.assertNotIn(" tela", text, name)
            self.assertNotIn("nesta conversa", text, name)

    def test_skill_md_example_input_runs(self):
        text = self.read("SKILL.md")
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S) if '"brands"' in b and "{...}" not in b]
        self.assertEqual(len(blocks), 1)
        data = blocks[0]
        self.assertEqual(calc.validate(data), [])
        self.assertIn("Acima da regra", render.render(calc.run(data), "html"))

    def test_params_files_are_the_site_copies(self):
        legal = json.loads(self.read("references/legal-params.json"))
        self.assertEqual(legal["checked_at"], "2026-11-06")
        self.assertEqual(legal["judicial_status"]["checked_at"], "2026-11-06")
        self.assertEqual(len(legal["judicial_status"]["sources"]), 3)


if __name__ == "__main__":
    unittest.main()
