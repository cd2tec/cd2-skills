import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class RepoTest(unittest.TestCase):
    def test_license_is_official_cc_by_nc_nd(self):
        self.assertIn("Attribution-NonCommercial-NoDerivatives 4.0 International", read("LICENSE"))

    def test_notice_credits_cd2_tech_only(self):
        text = read("NOTICE")
        self.assertIn("CD2 Tech", text)
        self.assertNotIn("Gabriel", text)

    def test_commercial_has_evaluation_and_clients(self):
        text = read("COMMERCIAL.md")
        for needle in ("avaliação", "cliente", "wa.me/5519982355172"):
            self.assertIn(needle, text)

    def test_json_files_parse(self):
        core = json.loads(read("core/cd2-varejo/plugin.core.json"))
        skills = json.loads(read("skills.json"))
        harnesses = json.loads(read("harnesses.json"))
        self.assertEqual(core["version"], "0.1.0")
        self.assertEqual({s["name"] for s in skills}, {"fim-escala-6x1", "custo-vrva"})
        self.assertEqual(set(harnesses["plugins"]["cd2-varejo"]["harnesses"]), {"claude", "codex", "dsh", "gpt"})


if __name__ == "__main__":
    unittest.main()
