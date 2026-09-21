import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "scripts" / "commit_handoff.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load_module("commit_handoff", ENGINE_PATH)


class RepositoryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "rename.txt").write_text("rename\n", encoding="utf-8")
        (self.repo / "delete.txt").write_text("delete\n", encoding="utf-8")
        self.git("add", "--", "tracked.txt", "rename.txt", "delete.txt")
        self.git("commit", "-m", "test: base")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


class ChangedPathsTest(RepositoryFixture):
    def test_discovers_all_worktree_states(self):
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new file.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "delete.txt").unlink()
        self.git("mv", "rename.txt", "renamed.txt")
        self.git("add", "--", "tracked.txt")
        self.assertEqual(
            engine.changed_paths(self.repo),
            [
                "delete.txt",
                "new file.txt",
                "renamed.txt",
                "tracked.txt",
            ],
        )


class RenderingTest(unittest.TestCase):
    def test_renders_and_validates_exact_handoff(self):
        paths = ["file one.txt", "skills/example/SKILL.md"]
        rendered = engine.render_handoff(
            paths,
            "feat(governance): enforce commit handoff",
            "Add deterministic rendering and validation for the required "
            "two-command handoff without modifying repository state.",
        )
        result = engine.validate_response(rendered, paths)
        self.assertTrue(result["valid"])
        self.assertEqual(rendered.count("```bash"), 2)
        self.assertIn("git add -- 'file one.txt' skills/example/SKILL.md", rendered)
        self.assertEqual(rendered.count("  -m "), 2)

    def test_wraps_description_at_seventy_characters(self):
        rendered = engine.render_handoff(
            ["file.txt"],
            "fix(governance): wrap commit description",
            "This description contains enough words to require multiple "
            "physical lines while remaining one continuous commit paragraph.",
        )
        _, body = engine.parse_commit_command(
            engine.BASH_BLOCK.findall(rendered)[1].strip()
        )
        self.assertTrue(all(len(line) <= 70 for line in body.splitlines()))
        self.assertNotIn("\n\n", body)

    def test_rejects_invalid_title(self):
        with self.assertRaises(engine.HandoffError):
            engine.render_handoff(
                ["file.txt"],
                "not semantic",
                "Valid description.",
            )

    def test_rejects_blank_description_paragraph(self):
        with self.assertRaises(engine.HandoffError):
            engine.render_handoff(
                ["file.txt"],
                "fix: reject blank paragraph",
                "First paragraph.\n\nSecond paragraph.",
            )

    def test_rejects_extra_message_flag(self):
        response = """```bash
git add -- file.txt
```

```bash
git commit -m "fix: title" -m "Body." -m "Extra."
```"""
        result = engine.validate_response(response, ["file.txt"])
        self.assertFalse(result["valid"])
        self.assertIn("exactly two -m", " ".join(result["violations"]))

    def test_rejects_heredoc(self):
        response = """```bash
git add -- file.txt
```

```bash
git commit -m "$(cat <<'EOF'
fix: title
EOF
)"
```"""
        result = engine.validate_response(response, ["file.txt"])
        self.assertFalse(result["valid"])
        self.assertIn("HEREDOC", " ".join(result["violations"]))

    def test_rejects_incomplete_paths(self):
        rendered = engine.render_handoff(
            ["one.txt"],
            "fix: include changed paths",
            "Include all changed paths.",
        )
        result = engine.validate_response(rendered, ["one.txt", "two.txt"])
        self.assertFalse(result["valid"])
        self.assertIn("do not match", " ".join(result["violations"]))

    def test_cli_validate_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test User"],
                check=True,
            )
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "--", "base.txt"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-m", "test: base"],
                check=True,
                stdout=subprocess.PIPE,
            )
            (root / "base.txt").write_text("changed\n", encoding="utf-8")
            rendered = engine.render_handoff(
                ["base.txt"],
                "fix: validate response",
                "Validate the response through the command line interface.",
            )
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".md",
            ) as response_file:
                response_file.write(rendered)
                response_file.flush()
                result = subprocess.run(
                    [
                        "python3",
                        str(ENGINE_PATH),
                        "validate-response",
                        "--repo",
                        str(root),
                        "--response-file",
                        response_file.name,
                    ],
                    check=False,
                    stdout=subprocess.PIPE,
                    text=True,
                )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
