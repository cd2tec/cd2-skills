import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def wf(name):
    return (WF / name).read_text(encoding="utf-8")


class WorkflowTest(unittest.TestCase):
    def test_three_workflows_exist(self):
        self.assertEqual(sorted(p.name for p in WF.glob("*.yml")), ["check-sync.yml", "pages.yml", "release.yml"])

    def test_check_sync_runs_sync_tests_and_json(self):
        text = wf("check-sync.yml")
        for needle in (
            "pull_request:",
            "branches: [main]",
            "python-version: \"3.12\"",
            "sync_plugins.py --check",
            "unittest discover -s tests -v",
            "json.tool",
            "gpts/*/gpt.json",
            "core/*/plugin.core.json",
            ".agents/plugins/marketplace.json",
            ".claude-plugin/marketplace.json",
            "harnesses.json",
            "skills.json",
        ):
            self.assertIn(needle, text)

    def test_pages_publishes_docs(self):
        text = wf("pages.yml")
        for needle in ("path: docs", '"docs/**"', "workflow_dispatch:", "actions/deploy-pages@v4", "actions/upload-pages-artifact@v3", "actions/configure-pages@v5"):
            self.assertIn(needle, text)

    def test_release_checks_packages_and_tags(self):
        text = wf("release.yml")
        for needle in (
            "sync_plugins.py --check",
            "package_plugins.py --out dist",
            '"core/*/plugin.core.json"',
            "workflow_dispatch:",
            "gh release create",
            "gh release upload",
            'dist/"$plugin"-*.zip',
        ):
            self.assertIn(needle, text)
        # A tag cd2-varejo-v<versão> sai de <plugin>-v<versão> (package_plugins.py).
        self.assertIn("-v", text)
        self.assertLess(text.index("sync_plugins.py --check"), text.index("package_plugins.py"))

    def test_release_notes_name_every_platform_and_zip(self):
        text = wf("release.yml")
        for needle in ("Claude Cowork", "Codex e ChatGPT Work", "DeepSeek Harness", "GPTs para a GPT Store"):
            self.assertIn(needle, text)
        for pkg in ("claude", "codex", "dsh", "gpts"):
            self.assertIn(f"$plugin-{pkg}-$version.zip", text)
            self.assertIn(f"$plugin-{pkg}.zip", text)

    def test_tag_prefix_matches_package_script(self):
        script = (ROOT / "scripts" / "package_plugins.py").read_text(encoding="utf-8")
        self.assertIn('f"{plugin}-v{version}"', script)
        self.assertIn("cd2-varejo", (ROOT / "harnesses.json").read_text(encoding="utf-8"))
        self.assertIn("cd2-varejo-v", "cd2-varejo-v0.2.0")

    def test_actions_are_pinned_and_text_is_clean(self):
        for path in WF.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            for use in re.findall(r"uses:\s*(\S+)", text):
                self.assertRegex(use, r"@v\d+$", f"{path.name}: {use}")
            self.assertNotRegex(text, "[—–]", path.name)
            self.assertNotRegex(text, "[\U0001F300-\U0001FAFF☀-➿]", path.name)


if __name__ == "__main__":
    unittest.main()
