import codecs
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Nada disto pode aparecer num arquivo público: nome de pessoa, caminho local,
# ferramenta interna ou repositório privado das calculadoras.
# Os nomes próprios ficam em rot13 para este arquivo não carregar o que ele procura.
LEAKS = tuple(codecs.decode(s, "rot13") for s in (
    "Tnoevry", "anlnovat", "sevqnl", "pq2grp/pq2-pnyp", "nepurb-unearff-cyhtvaf",
    "nanylmr-zpc", "ohvyq-zpc-qnfuobneq", "fcrp-zpc-gbby", "Ergnvy Grpu",
)) + (
    "/private/tmp", "scratchpad", "claude.ai/artifact", "docs/superpowers")
NOMES_ANTIGOS = tuple(codecs.decode(s, "rot13") for s in (
    "nepurb-unearff", "nanylmr-zpc", "ohvyq-zpc-qnfuobneq", "fcrp-zpc-gbby", "Ergnvy Grpu"))
PERSON = codecs.decode("Tnoevry", "rot13")
INTERNAL_DIRS = ("interno/", ".superpowers/", "dist/")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        raise unittest.SkipTest("git indisponível")
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def tracked_texts():
    """(caminho, texto) de cada arquivo de texto versionado, menos os testes."""
    for rel in tracked_files():
        if rel.startswith("tests/") or not (ROOT / rel).is_file():
            continue
        try:
            yield rel, (ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


LICENSE_90 = re.compile(
    r"livre por até 90 dias|por até 90 dias, (só )?para avaliar|até 90 dias, para avaliar"
    r"|avaliação grátis por 90|90 dias de avaliação|stat\">90 dias"
)


class RepoTest(unittest.TestCase):
    def test_license_is_official_cc_by_nc_nd(self):
        self.assertIn("Attribution-NonCommercial-NoDerivatives 4.0 International", read("LICENSE"))

    def test_notice_credits_cd2_tech_only(self):
        text = read("NOTICE")
        self.assertIn("CD2 Tech", text)
        self.assertNotIn(PERSON, text)

    def test_no_leaks_in_any_tracked_file(self):
        for rel, text in tracked_texts():
            lowered = text.lower()
            for needle in LEAKS:
                self.assertFalse(needle.lower() in lowered, f"{rel}: {needle}")

    def test_internal_dirs_are_ignored_and_untracked(self):
        ignore = read(".gitignore").split()
        for folder in INTERNAL_DIRS:
            self.assertIn(folder, ignore)
        for rel in tracked_files():
            self.assertFalse(rel.startswith(INTERNAL_DIRS + ("docs/superpowers/",)), rel)

    def test_no_deliverable_says_use_as_much_as_you_want(self):
        # O teste na empresa é livre e sem prazo (COMMERCIAL.md): nenhum texto pode dizer o contrário.
        for rel, text in tracked_texts():
            self.assertFalse("quanto quiser" in text, rel)

    def test_notice_states_font_exception(self):
        text = read("NOTICE")
        self.assertIn("SIL Open Font License 1.1", text)
        self.assertIn("não é coberta pela licença Creative Commons", text)

    def test_commercial_testar_livre(self):
        text = read("COMMERCIAL.md")
        self.assertIn("para testar, livremente e sem prazo", text)
        for needle in ("cliente", "wa.me/5519982355172"):
            self.assertIn(needle, text)

    def test_licenca_sem_prazo(self):
        for rel, text in tracked_texts():
            if rel == "CHANGELOG.md":
                continue  # histórico da 0.1.0 continua verdadeiro
            self.assertIsNone(LICENSE_90.search(text), rel)

    def test_testes_tambem_sem_nomes_antigos(self):
        # tracked_texts() pula tests/: este teste cobre os outros arquivos de teste. Só o test_repo.py
        # os cita (em rot13).
        for path in sorted((ROOT / "tests").glob("*.py")):
            if path.name == "test_repo.py":
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for needle in NOMES_ANTIGOS:
                self.assertNotIn(needle.lower(), lowered, f"{path.name}: {needle}")

    def test_sem_apache(self):
        # A licença é só a CC BY-NC-ND 4.0. A Manrope (assets/fonts) segue na OFL e fica de fora.
        for rel, text in tracked_texts():
            if "/fonts/" in rel or rel.endswith("OFL.txt"):
                continue
            self.assertNotIn("apache", text.lower(), rel)

    def test_json_files_parse(self):
        core = json.loads(read("core/cd2-super/plugin.core.json"))
        skills = json.loads(read("skills.json"))
        harnesses = json.loads(read("harnesses.json"))
        self.assertEqual(core["version"], "0.3.0")
        self.assertEqual(
            {s["name"] for s in skills},
            {
                "fim-escala-6x1", "custo-vrva", "relatorio-vendas", "relatorio-estoque",
                "relatorio-compras", "relatorio-precos", "relatorio-perdas", "relatorio-financeiro",
                "relatorio-fiscal", "relatorio-contabil", "painel-varejo", "ficha-archeo-mcp",
                "perfil-da-operacao", "briefing-do-dia",
            },
        )
        self.assertEqual(set(harnesses["plugins"]["cd2-super"]["harnesses"]), {"claude", "codex", "dsh", "gpt"})


if __name__ == "__main__":
    unittest.main()
