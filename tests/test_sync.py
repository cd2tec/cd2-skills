"""Testes do sync por plataforma (scripts/sync_plugins.py) e do empacotamento.

O sync roda via subprocess numa pasta temporária (--out-root), para não mexer
nas cópias do repositório. Os scripts das skills também rodam via subprocess:
as duas skills têm um calc.py e importar os dois no mesmo processo confunde.
"""
import codecs
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSON = codecs.decode("Tnoevry", "rot13")  # nome próprio que nenhum arquivo pode citar
SYNC = ROOT / "scripts" / "sync_plugins.py"
PACKAGE = ROOT / "scripts" / "package_plugins.py"
PLUGIN = "cd2-super"
SKILLS = ("fim-escala-6x1", "custo-vrva")
PLACEHOLDER = "{{" + "UTM_SOURCE" + "}}"
EM, EN = chr(0x2014), chr(0x2013)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
TEXT_SUFFIXES = {".md", ".py", ".html", ".json", ".txt", ".svg"}
JUNK = ("__pycache__", ".pyc", ".DS_Store")

BAKERY = {
    "today": "2026-11-07",
    "brands": [
        {"name": "Alelo", "sales": 18000, "rate": 6.5, "days": 30},
        {"name": "Pluxee (Sodexo)", "sales": 12000, "rate": 5.9, "days": 30},
        {"name": "Ticket", "sales": 10000, "rate": 6.0, "days": 32},
        {"name": "VR", "sales": 8000, "rate": 4.5, "days": 25},
    ],
    "money_cost_month_percent": 2,
}
STORE_6X1 = {
    "today": "2026-11-07",
    "store": {"days_open_per_week": 7, "hours_open_per_day": 13, "payroll_charges_factor": 0.7},
    "sectors": [
        {"name": "Caixa", "headcount": 14, "avg_monthly_salary": 1900, "min_simultaneous_staff": 5},
        {"name": "Açougue", "headcount": 6, "avg_monthly_salary": 2600, "current_weekly_hours": 44},
    ],
}
INPUTS = {"custo-vrva": BAKERY, "fim-escala-6x1": STORE_6X1}


def run_sync(*args):
    return subprocess.run(
        [sys.executable, str(SYNC), *args], capture_output=True, text=True, cwd=str(ROOT)
    )


def text_files(tree: Path):
    for path in sorted(tree.rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            yield path


def run_skill(scripts: Path, workdir: Path, data: dict, utm: str):
    """Roda calc.py e render.py --format html a partir de `scripts`; devolve o HTML."""
    (workdir / "entrada.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    calc = subprocess.run(
        [sys.executable, str(scripts / "calc.py"), "--input", "entrada.json"],
        capture_output=True, text=True, cwd=str(workdir),
    )
    if calc.returncode != 0:
        raise AssertionError(f"calc.py falhou: {calc.stderr or calc.stdout}")
    (workdir / "saida.json").write_text(calc.stdout, encoding="utf-8")
    render = subprocess.run(
        [sys.executable, str(scripts / "render.py"), "--result", "saida.json", "--format", "html",
         "--output", "entrega.html"],
        capture_output=True, text=True, cwd=str(workdir),
    )
    if render.returncode != 0:
        raise AssertionError(f"render.py falhou: {render.stderr or render.stdout}")
    return (workdir / "entrega.html").read_text(encoding="utf-8")


class SyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="cd2-sync-")
        cls.out = Path(cls._tmp.name)
        cls.result = run_sync("--out-root", str(cls.out))
        if cls.result.returncode != 0:
            raise AssertionError(f"sync falhou:\n{cls.result.stdout}\n{cls.result.stderr}")
        cls.claude = cls.out / "plugins" / "claude" / PLUGIN
        cls.codex = cls.out / "plugins" / "codex" / PLUGIN
        cls.dsh = cls.out / "plugins" / "dsh" / PLUGIN
        cls.gpts = cls.out / "gpts"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_claude_skill_is_self_contained(self):
        skill = self.claude / "skills" / "custo-vrva"
        self.assertTrue((skill / "scripts" / "brand.py").is_file())
        self.assertTrue((skill / "assets" / "brand" / "cd2tech-horizontal.svg").is_file())
        self.assertTrue((skill / "references" / "fluxo-conversa.md").is_file())
        self.assertTrue((skill / "references" / "marca.md").is_file())
        for name in ("LICENSE", "NOTICE", "COMMERCIAL.md"):
            self.assertTrue((self.claude / name).is_file(), name)
            self.assertTrue((self.codex / name).is_file(), name)

    def test_dsh_skills_carry_license(self):
        for skill in SKILLS:
            for name in ("LICENSE", "NOTICE", "COMMERCIAL.md"):
                self.assertTrue((self.dsh / "skills" / skill / name).is_file(), f"{skill}/{name}")
        self.assertTrue((self.dsh / "install.py").is_file())

    def test_render_runs_from_package(self):
        scripts = self.dsh / "skills" / "custo-vrva" / "scripts"
        with tempfile.TemporaryDirectory() as work:
            page = run_skill(scripts, Path(work), BAKERY, "deepseek")
        self.assertIn("<svg", page)
        self.assertIn("utm_source=deepseek&", page)
        self.assertNotIn("{deepseek}", page)
        self.assertNotIn(PLACEHOLDER, page)
        self.assertNotIn("utm_source=" + "{", page)

    def test_utm_replaced_per_harness(self):
        expected = {self.claude: "claude", self.codex: "codex", self.dsh: "deepseek", self.gpts: "gpt-store"}
        for tree, source in expected.items():
            found = False
            for path in text_files(tree):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(PLACEHOLDER, text, path)
                self.assertNotIn("utm_source={", text, path)
                found = found or f"utm_source={source}&" in text
            self.assertTrue(found, f"utm_source={source} não aparece em {tree}")
        # brand.link() nas cópias devolve o utm_source do harness, sem chaves.
        brand_py = (self.claude / "skills" / "custo-vrva" / "scripts" / "brand.py").read_text(encoding="utf-8")
        self.assertIn('UTM_SOURCE = "claude"', brand_py)

    def test_gpt_bundle_layout(self):
        for skill in SKILLS:
            base = self.gpts / skill
            knowledge = base / "knowledge"
            for rel in ("scripts/calc.py", "scripts/render.py", "scripts/brand.py", "assets/template.html",
                        "assets/fonts/Manrope-Variable.woff2", "assets/brand/cd2tech-horizontal.svg",
                        "assets/brand/simbolo.svg", "references/metodologia.md",
                        "references/legal-params.json", "references/fluxo-conversa.md"):
                self.assertTrue((knowledge / rel).is_file(), f"{skill}: {rel}")
            self.assertFalse((knowledge / "SKILL.md").exists())
            files = [p for p in knowledge.rglob("*") if p.is_file()]
            self.assertLessEqual(len(files), 20, f"{skill}: GPT aceita no máximo 20 arquivos")
            names = [p.name for p in files]
            self.assertEqual(len(names), len(set(names)), f"{skill}: nomes repetidos quebram o upload plano")
            meta = json.loads((base / "gpt.json").read_text(encoding="utf-8"))
            self.assertEqual(
                set(meta), {"name", "description", "conversation_starters", "capabilities", "profile_picture"}
            )
            self.assertEqual(len(meta["conversation_starters"]), 4)
            self.assertEqual(
                meta["capabilities"], {"web_browsing": True, "code_interpreter": True, "image_generation": False}
            )
            self.assertEqual(meta["profile_picture"], "knowledge/assets/brand/simbolo.svg")
            self.assertTrue((base / meta["profile_picture"]).is_file())
        names = {json.loads((self.gpts / s / "gpt.json").read_text(encoding="utf-8"))["name"] for s in SKILLS}
        self.assertEqual(names, {"CD2 Escala 6x1", "CD2 VR/VA: quanto custa"})
        for name in ("LICENSE", "NOTICE", "COMMERCIAL.md", "README.md"):
            self.assertTrue((self.gpts / name).is_file(), name)

    def test_gpt_knowledge_runs_flat(self):
        """ChatGPT achata o upload numa pasta só (/mnt/data): os scripts acham os vizinhos ali."""
        for skill in SKILLS:
            knowledge = self.gpts / skill / "knowledge"
            with tempfile.TemporaryDirectory() as flat_dir, tempfile.TemporaryDirectory() as work:
                flat = Path(flat_dir)
                for path in knowledge.rglob("*"):
                    if path.is_file():
                        shutil.copy2(path, flat / path.name)
                page = run_skill(flat, Path(work), INPUTS[skill], "gpt-store")
            self.assertIn("<svg", page, skill)
            self.assertIn("utm_source=gpt-store&", page, skill)
            self.assertIn("@font-face", page, skill)
            self.assertNotIn(PLACEHOLDER, page, skill)

    def test_gpt_instructions_under_limit(self):
        for skill in SKILLS:
            text = (self.gpts / skill / "instructions.md").read_text(encoding="utf-8")
            self.assertLessEqual(len(text), 8000, f"{skill}: {len(text)} caracteres")

    def test_gpt_instructions_content(self):
        other = {"fim-escala-6x1": "CD2 VR/VA: quanto custa", "custo-vrva": "CD2 Escala 6x1"}
        rules = {"fim-escala-6x1": "Emenda Constitucional 141/2026", "custo-vrva": "Decreto 12.712/2025"}
        for skill in SKILLS:
            text = (self.gpts / skill / "instructions.md").read_text(encoding="utf-8")
            for needle in ("calc.py", "render.py", "archeo.cd2.com.br/?utm_source=gpt-store&",
                           "https://wa.me/5519982355172", "cd2.com.br/?utm_source=gpt-store&",
                           "CD2 Tech\nEstas contas e informações são apenas gerenciais", rules[skill],
                           other[skill], "Claude", "Codex", "interpretador de código"):
                self.assertIn(needle, text, f"{skill}: falta {needle!r}")
            self.assertNotIn(EM, text)
            self.assertNotIn(EN, text)
            self.assertNotIn(PERSON, text)
            self.assertIsNone(EMOJI.search(text), skill)
            self.assertEqual(re.findall(r"\{\{[^}]*\}\}", text), [], skill)

    def test_no_junk_in_copies(self):
        for path in self.out.rglob("*"):
            for junk in JUNK:
                self.assertNotIn(junk, path.name, path)

    def test_check_passes_after_sync(self):
        result = run_sync("--check", "--out-root", str(self.out))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(run_sync("--out-root", str(out)).returncode, 0)
            self.assertEqual(run_sync("--check", "--out-root", str(out)).returncode, 0)
            target = out / "plugins" / "claude" / PLUGIN / "skills" / "custo-vrva" / "SKILL.md"
            target.write_text(target.read_text(encoding="utf-8") + "\nmexido à mão\n", encoding="utf-8")
            result = run_sync("--check", "--out-root", str(out))
            self.assertEqual(result.returncode, 1)
            self.assertIn("custo-vrva/SKILL.md", result.stderr)

    def test_check_detects_long_gpt_instructions_and_leftover_utm(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(run_sync("--out-root", str(out)).returncode, 0)
            target = out / "gpts" / "custo-vrva" / "instructions.md"
            target.write_text("x" * 8001, encoding="utf-8")
            brand_py = out / "plugins" / "codex" / PLUGIN / "skills" / "custo-vrva" / "scripts" / "brand.py"
            brand_py.write_text(brand_py.read_text(encoding="utf-8") + f"\n# {PLACEHOLDER}\n", encoding="utf-8")
            result = run_sync("--check", "--out-root", str(out))
            self.assertEqual(result.returncode, 1)
            self.assertIn("8.000", result.stderr)
            self.assertIn("UTM_SOURCE", result.stderr)

    def test_manifests_license(self):
        manifests = [
            ROOT / "plugins" / "claude" / PLUGIN / ".claude-plugin" / "plugin.json",
            ROOT / "plugins" / "codex" / PLUGIN / "plugin.json",
            ROOT / "plugins" / "dsh" / PLUGIN / "plugin.json",
        ]
        for path in manifests:
            meta = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(meta["name"], PLUGIN, path)
            self.assertEqual(meta["version"], "0.3.0", path)
            self.assertEqual(meta["license"], "CC-BY-NC-ND-4.0", path)
            self.assertEqual(meta["author"], {"name": "CD2 Tech", "url": "https://cd2.com.br"}, path)
            self.assertEqual(meta["homepage"], "https://cd2tec.github.io/super/", path)
            self.assertEqual(meta["repository"], "https://github.com/cd2tec/super", path)
        # Manifestos e marketplace falam dos relatórios, do painel e da ficha, e não só das calculadoras.
        claude_entry = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["plugins"][0]
        for meta in [json.loads(p.read_text(encoding="utf-8")) for p in manifests] + [claude_entry]:
            self.assertIn("relatorio-", meta["description"])
            self.assertIn("painel-varejo", meta["description"])
            self.assertIn("ficha-archeo-mcp", meta["description"])
            self.assertIn("relatorio", meta["keywords"])
            self.assertIn("painel", meta["keywords"])
        codex = json.loads(manifests[1].read_text(encoding="utf-8"))["extensions"]["com.openai"]["interface"]
        self.assertEqual(codex["displayName"], "CD2 Super")
        self.assertEqual(codex["developerName"], "CD2 Tech")
        claude_mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        codex_mp = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(claude_mp["name"], "super")
        self.assertEqual(codex_mp["name"], "super")
        self.assertEqual(codex_mp["interface"]["displayName"], "Super (CD2 Tech)")
        entry = claude_mp["plugins"][0]
        self.assertEqual(entry["name"], PLUGIN)
        self.assertNotIn("version", entry)
        self.assertEqual(entry["license"], "CC-BY-NC-ND-4.0")
        self.assertEqual(entry["source"], "./plugins/claude/cd2-super")
        self.assertEqual(codex_mp["plugins"][0]["source"]["path"], "./plugins/codex/cd2-super")

    def test_readme_and_site_blocks(self):
        for rel, utm in (("README.md", "utm_source=github&"), ("docs/index.html", "utm_source=site-skills&")):
            text = (self.out / rel).read_text(encoding="utf-8")
            start, end = text.index("<!-- skills:start -->"), text.index("<!-- skills:end -->")
            block = text[start:end]
            self.assertIn("Fim da escala 6x1", block, rel)
            self.assertIn("Quanto o VR/VA custa de verdade", block, rel)
            self.assertIn(utm, block, rel)
            self.assertIn("utm_campaign=fim-escala-6x1", block, rel)


class CollisionTest(unittest.TestCase):
    """Um arquivo compartilhado nunca sobrescreve um arquivo da skill com o mesmo nome."""

    def test_shared_file_colliding_with_skill_file_fails(self):
        spec = importlib.util.spec_from_file_location("cd2_sync_plugins", SYNC)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill, shared, dest = base / "skills" / "x", base / "shared", base / "out"
            (skill / "references").mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")
            (skill / "references" / "marca.md").write_text("da skill", encoding="utf-8")
            (shared / "references").mkdir(parents=True)
            (shared / "references" / "marca.md").write_text("compartilhado", encoding="utf-8")
            problems = module.assemble_skill(skill, [shared], dest)
            self.assertTrue(any("marca.md" in p for p in problems), problems)
            self.assertEqual((dest / "references" / "marca.md").read_text(encoding="utf-8"), "da skill")


def load_sync():
    spec = importlib.util.spec_from_file_location("cd2_sync_plugins", SYNC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_core(base: Path, skills: dict[str, dict]) -> tuple[Path, dict, list[dict]]:
    """core temporário com shared/, kits e uma skill por entrada de `skills` (nome -> item do skills.json)."""
    core = base / "core"
    write(core / "shared" / "scripts" / "brand.py")
    write(core / "kits" / "calculadora" / "references" / "fluxo-conversa.md")
    write(core / "kits" / "relatorio" / "scripts" / "render_relatorio.py")
    write(core / "kits" / "sql" / "references" / "regras-sql.md")
    write(core / "kits" / "dados" / "scripts" / "dados_arquivo.py")
    write(core / "kits" / "rotina" / "references" / "regras-rotina.md")
    write(core / "gpts" / "_preamble.md", "preambulo {{SKILL}}")
    items = []
    for nome, item in skills.items():
        write(core / "skills" / nome / "SKILL.md", f"---\nname: {nome}\ndescription: y\n---\n")
        items.append({"name": nome, **item})
    spec = {"shared": "shared", "kits": {
        "calculadora": ["calculadora"], "relatorio": ["sql", "dados", "relatorio"],
        "painel": ["sql", "dados"], "ficha": ["sql"], "rotina": ["sql", "dados", "relatorio", "rotina"],
    }}
    return core, spec, items


SKILL_FONTE = (
    "---\nname: relatorio-compras\ndescription: y\n---\n"
    "# T\nUse `references/relatorios.md`.\n## Prova\nsoma\n## Entrega\ncortar\n## Depois\nfica\n## Fechamento\ncortar2\n"
)


class ReaproveitaTest(unittest.TestCase):
    def setUp(self):
        self.sync = load_sync()
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def montar(self, reaproveita):
        core, spec, items = make_core(self.base, {
            "relatorio-compras": {"tipo": "relatorio", "gpt": False},
            "r": {"tipo": "rotina", "gpt": False, "reaproveita": reaproveita},
        })
        write(core / "skills" / "relatorio-compras" / "SKILL.md", SKILL_FONTE)
        write(core / "skills" / "relatorio-compras" / "references" / "relatorios.md", "Teste: SKILL.md, seção X\n")
        return core, spec, items

    def test_reaproveita_gera_relatorios_e_guia(self):
        core, spec, items = self.montar(["relatorio-compras"])
        work = self.base / "work"
        self.assertEqual(self.sync.build_skills(core, spec, items, work), [])
        refs = work / "skills" / "r" / "references"
        self.assertIn("guia-compras.md", (refs / "relatorios-compras.md").read_text(encoding="utf-8"))
        guia = (refs / "guia-compras.md").read_text(encoding="utf-8")
        self.assertNotIn("name: relatorio-compras", guia)
        self.assertIn("references/relatorios-compras.md", guia)
        self.assertIn("soma", guia)
        self.assertIn("fica", guia)
        self.assertNotIn("cortar", guia)

    def test_reaproveita_skill_inexistente_acusa(self):
        core, spec, items = self.montar(["relatorio-nada"])
        problems = self.sync.build_skills(core, spec, items, self.base / "work")
        self.assertTrue(any("relatorio-nada" in p for p in problems), problems)

    def test_reaproveita_fora_de_rotina_acusa(self):
        items = [{"name": "relatorio-x", "tipo": "relatorio", "gpt": False, "reaproveita": ["relatorio-x"]}]
        problems = self.sync.check_skills_json(items)
        self.assertTrue(any("reaproveita" in p and "relatorio-x" in p for p in problems), problems)

    def test_reaproveita_de_nao_relatorio_acusa(self):
        items = [
            {"name": "painel-varejo", "tipo": "painel", "gpt": False},
            {"name": "r", "tipo": "rotina", "gpt": False, "reaproveita": ["painel-varejo"]},
        ]
        problems = self.sync.check_skills_json(items)
        self.assertTrue(any("reaproveita" in p and "painel-varejo" in p for p in problems), problems)


class KitsTest(unittest.TestCase):
    def setUp(self):
        self.sync = load_sync()
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_kit_entra_so_no_tipo_certo(self):
        core, spec, items = make_core(self.base, {
            "calc-x": {"tipo": "calculadora", "gpt": False},
            "relatorio-x": {"tipo": "relatorio", "gpt": False},
        })
        work = self.base / "work"
        self.assertEqual(self.sync.build_harness(core, spec, items, "plugin", work), [])
        calc, rel = work / "skills" / "calc-x", work / "skills" / "relatorio-x"
        self.assertTrue((calc / "references" / "fluxo-conversa.md").is_file())
        self.assertTrue((calc / "scripts" / "brand.py").is_file())
        self.assertFalse((calc / "scripts" / "render_relatorio.py").exists())
        self.assertFalse((calc / "scripts" / "dados_arquivo.py").exists())
        for rel_path in ("scripts/render_relatorio.py", "scripts/dados_arquivo.py",
                         "references/regras-sql.md", "scripts/brand.py"):
            self.assertTrue((rel / rel_path).is_file(), rel_path)
        self.assertFalse((rel / "references" / "fluxo-conversa.md").exists())

    def test_kits_da_skill(self):
        core, spec, items = make_core(self.base, {"p": {"tipo": "painel", "gpt": False}})
        self.assertEqual(
            self.sync.kits_da_skill(core, spec, items, "p"),
            [core / "shared", core / "kits" / "sql", core / "kits" / "dados"],
        )

    def test_colisao_entre_kits_e_erro(self):
        core, spec, items = make_core(self.base, {"r": {"tipo": "relatorio", "gpt": False}})
        write(core / "kits" / "sql" / "scripts" / "dados_arquivo.py", "outro")
        problems = self.sync.build_harness(core, spec, items, "plugin", self.base / "work")
        self.assertTrue(any("colisão" in p and "dados_arquivo.py" in p for p in problems), problems)

    def test_kit_inexistente_e_acusado(self):
        core, spec, items = make_core(self.base, {"f": {"tipo": "ficha", "gpt": False}})
        shutil.rmtree(core / "kits" / "sql")
        problems = self.sync.build_harness(core, spec, items, "plugin", self.base / "work")
        self.assertTrue(any("inexistente" in p and "sql" in p for p in problems), problems)

    def test_skill_em_core_fora_do_skills_json_acusa(self):
        core, spec, items = make_core(self.base, {"a": {"tipo": "ficha", "gpt": False}})
        write(core / "skills" / "orfa" / "SKILL.md", "---\nname: orfa\ndescription: y\n---\n")
        problems = self.sync.build_harness(core, spec, items, "plugin", self.base / "work")
        self.assertTrue(any("orfa" in p and "skills.json" in p for p in problems), problems)

    def test_skill_sem_tipo_acusa(self):
        core, spec, items = make_core(self.base, {"a": {"gpt": False}})
        problems = self.sync.build_harness(core, spec, items, "plugin", self.base / "work")
        self.assertTrue(any("a" in p and "tipo" in p for p in problems), problems)
        self.assertTrue(any("tipo" in p for p in self.sync.check_skills_json(items)))

    def test_skill_sem_gpt_nao_gera_pasta(self):
        core, spec, items = make_core(self.base, {
            "com": {"tipo": "calculadora", "gpt": True},
            "sem": {"tipo": "ficha", "gpt": False},
        })
        write(core / "gpts" / "com" / "instructions.md", "corpo")
        write(core / "gpts" / "com" / "gpt.json", "{}")
        work = self.base / "work"
        self.assertEqual(self.sync.build_harness(core, spec, items, "gpt", work), [])
        self.assertTrue((work / "com" / "instructions.md").is_file())
        self.assertTrue((work / "com" / "knowledge" / "references" / "fluxo-conversa.md").is_file())
        self.assertFalse((work / "sem").exists())

    def test_skill_com_gpt_sem_instrucoes_acusa(self):
        core, spec, items = make_core(self.base, {"com": {"tipo": "calculadora", "gpt": True}})
        problems = self.sync.build_harness(core, spec, items, "gpt", self.base / "work")
        self.assertTrue(any("com" in p and "instructions.md" in p for p in problems), problems)

    def test_pasta_de_gpt_de_skill_sem_gpt_acusa(self):
        core, spec, items = make_core(self.base, {"sem": {"tipo": "ficha", "gpt": False}})
        write(core / "gpts" / "sem" / "instructions.md")
        problems = self.sync.build_harness(core, spec, items, "gpt", self.base / "work")
        self.assertTrue(any("core/gpts/sem" in p for p in problems), problems)

    def test_cabecalho_e_rotulos_por_tipo(self):
        calc = {"name": "c", "title": "C", "summary": "s", "site_url": "https://calc.cd2.com.br/",
                "rule": "Decreto 1", "status": "disponível", "tipo": "calculadora", "gpt": True}
        rel = {**calc, "name": "r", "site_url": "https://archeo.cd2.com.br/", "rule": "", "tipo": "relatorio", "gpt": False}
        table = self.sync.readme_block([calc, rel])
        self.assertIn("| Skill | O que faz | Regra | Site | Status |", table)
        self.assertIn("Não se aplica", table)
        cards = self.sync.site_block([calc, rel])
        self.assertIn("Abrir a calculadora gratuita", cards)
        self.assertIn("Conecte seu ERP", cards)
        self.assertEqual(cards.count("Base:"), 1)


class PackageTest(unittest.TestCase):
    def test_package_builds_zips_without_junk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = subprocess.run(
                [sys.executable, str(PACKAGE), "--out", str(out)], capture_output=True, text=True, cwd=str(ROOT)
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for harness in ("claude", "codex", "dsh", "gpts"):
                for name in (f"{PLUGIN}-{harness}.zip", f"{PLUGIN}-{harness}-0.3.0.zip"):
                    path = out / name
                    self.assertTrue(path.is_file(), name)
                    with zipfile.ZipFile(path) as zf:
                        entries = zf.namelist()
                    self.assertIn("LICENSE", entries, name)
                    for entry in entries:
                        for junk in JUNK:
                            self.assertNotIn(junk, entry, f"{name}: {entry}")
            with zipfile.ZipFile(out / f"{PLUGIN}-claude.zip") as zf:
                self.assertIn(".claude-plugin/plugin.json", zf.namelist())
                self.assertIn(".claude-plugin/icon.png", zf.namelist())
            with zipfile.ZipFile(out / f"{PLUGIN}-gpts.zip") as zf:
                self.assertIn("custo-vrva/knowledge/scripts/calc.py", zf.namelist())



class ClaudeIconTest(unittest.TestCase):
    """O diretório de plugins do Claude procura o ícone em .claude-plugin/icon.png."""

    def test_icon_is_square_png_and_matches_site(self):
        import struct
        icon = ROOT / "plugins" / "claude" / PLUGIN / ".claude-plugin" / "icon.png"
        data = icon.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 512)
        self.assertLessEqual(len(data), 2 * 1024 * 1024)
        self.assertEqual(data, (ROOT / "docs" / "assets" / "icon-512.png").read_bytes())

class DescriptionLimits(unittest.TestCase):
    """O validador de plugin do Claude recusa descrição acima de 500 caracteres."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("sync_limites", ROOT / "scripts/sync_plugins.py")
        cls.sync = importlib.util.module_from_spec(spec)
        sys.modules["sync_limites"] = cls.sync
        spec.loader.exec_module(cls.sync)

    def manifesto(self, tamanho):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "plugin.json"
        path.write_text(json.dumps({"name": "cd2-super", "version": "1.0.0", "license": self.sync.LICENSE_ID,
                                    "description": "x" * tamanho}), encoding="utf-8")
        return self.sync.check_manifest(path, {"name": "cd2-super", "version": "1.0.0"}, str)

    def test_manifesto_acima_do_limite_acusa(self):
        self.assertTrue(any("500" in p for p in self.manifesto(501)))

    def test_manifesto_no_limite_passa(self):
        self.assertEqual(self.manifesto(500), [])

    def test_manifestos_e_marketplace_reais_cabem(self):
        for rel in ("plugins/claude/cd2-super/.claude-plugin/plugin.json", "plugins/codex/cd2-super/plugin.json",
                    "plugins/dsh/cd2-super/plugin.json"):
            with self.subTest(rel):
                self.assertLessEqual(len(json.loads((ROOT / rel).read_text(encoding="utf-8"))["description"]), 500)
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        for entry in market["plugins"]:
            self.assertLessEqual(len(entry.get("description", "")), 500)

    def test_descricao_de_skill_cabe_em_1024(self):
        for skill in (ROOT / "core/cd2-super/skills").glob("*/SKILL.md"):
            with self.subTest(skill.parent.name):
                texto = skill.read_text(encoding="utf-8")
                self.assertLessEqual(len(re.search(r"^description:\s*(.+)$", texto, re.M).group(1)), 1024)


class FrontmatterYaml(unittest.TestCase):
    def conferir(self, descricao, nome="minha-skill"):
        spec = importlib.util.spec_from_file_location("sync_frontmatter", SYNC)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules["sync_frontmatter"] = modulo
        spec.loader.exec_module(modulo)
        with tempfile.TemporaryDirectory() as tmp:
            core = Path(tmp)
            pasta = core / "skills" / "minha-skill"
            pasta.mkdir(parents=True)
            (pasta / "SKILL.md").write_text(f"---\nname: {nome}\ndescription: {descricao}\n---\n\n# T\n", encoding="utf-8")
            return modulo.check_frontmatter(core)

    def test_dois_pontos_com_espaco_e_acusado(self):
        problemas = self.conferir('Faz a ficha (tela "Nova"): nome e schema.')
        self.assertTrue(any("description" in p for p in problemas), problemas)

    def test_comeca_com_caractere_especial_e_acusado(self):
        for inicio in ("*", "&", "!", "[", "{", "#", "%", "@", "|", ">", "- ", "? ", "`", '"sem fechar', "'sem fechar"):
            problemas = self.conferir(f"{inicio}texto da skill")
            self.assertTrue(any("description" in p for p in problemas), (inicio, problemas))

    def test_entre_aspas_passa(self):
        self.assertEqual(self.conferir('"Faz a ficha (tela Nova): nome e schema."'), [])
        self.assertEqual(self.conferir("'Faz: a ficha.'"), [])

    def test_texto_comum_passa(self):
        self.assertEqual(self.conferir("Faz a ficha, com hora 10:30 e link https://cd2.com.br/."), [])

    def test_as_skills_do_core_passam(self):
        spec = importlib.util.spec_from_file_location("sync_frontmatter_core", SYNC)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules["sync_frontmatter_core"] = modulo
        spec.loader.exec_module(modulo)
        self.assertEqual(modulo.check_frontmatter(ROOT / "core" / PLUGIN), [])


if __name__ == "__main__":
    unittest.main()
