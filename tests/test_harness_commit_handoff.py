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


class RepositoryDeltaTest(RepositoryFixture):
    def test_repository_delta_excludes_preexisting_dirty(self):
        (self.repo / "tracked.txt").write_text("preexisting\n", encoding="utf-8")
        baseline = engine.repository_snapshot(self.repo)
        (self.repo / "rename.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(
            engine.repository_delta_paths(self.repo, baseline),
            ["rename.txt"],
        )

    def test_repository_delta_excludes_no_net_change(self):
        baseline = engine.repository_snapshot(self.repo)
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.assertEqual(engine.repository_delta_paths(self.repo, baseline), [])

    def test_repository_delta_includes_modified_preexisting_dirty(self):
        (self.repo / "tracked.txt").write_text("preexisting\n", encoding="utf-8")
        baseline = engine.repository_snapshot(self.repo)
        (self.repo / "tracked.txt").write_text(
            "changed again with a different size\n",
            encoding="utf-8",
        )
        self.assertEqual(
            engine.repository_delta_paths(self.repo, baseline),
            ["tracked.txt"],
        )

    def test_snapshot_delta_detects_rename_and_delete(self):
        baseline = engine.repository_snapshot(self.repo)
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "delete.txt").unlink()
        self.git("mv", "rename.txt", "renamed.txt")
        current = engine.repository_snapshot(self.repo)
        self.assertEqual(
            set(engine.snapshot_delta(baseline, current)),
            {"tracked.txt", "delete.txt", "renamed.txt"},
        )

    def test_discovers_repositories_beyond_two_directory_levels(self):
        nested = self.repo / "one" / "two" / "three"
        nested.mkdir(parents=True)
        subprocess.run(["git", "-C", str(nested), "init"], check=True)
        discovered = engine.discover_git_repos([self.repo.parent])
        self.assertIn(self.repo.resolve(), discovered)
        self.assertIn(nested.resolve(), discovered)


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

    def test_renders_git_c_for_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")
            rendered = engine.render_handoff(
                ["file.txt"],
                "fix(governance): render git c",
                "Render location-independent git commands for touched paths.",
                repo=repo,
            )
            repo_arg, _ = engine.parse_add_command(
                engine.BASH_BLOCK.findall(rendered)[0].strip()
            )
            self.assertEqual(Path(repo_arg).resolve(), repo.resolve())
            result = engine.validate_response_multi(
                rendered,
                {str(repo.resolve()): ["file.txt"]},
            )
            self.assertTrue(result["valid"])

    def test_validates_multi_repo_pairs_independent_of_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_one = root / "one"
            repo_two = root / "two"
            repo_one.mkdir()
            repo_two.mkdir()
            rendered = "\n\n".join(
                [
                    engine.render_handoff(
                        ["two.txt"],
                        "fix(two): validate handoff",
                        "Validate the second repository before the first.",
                        repo=repo_two,
                    ),
                    engine.render_handoff(
                        ["one.txt"],
                        "fix(one): validate handoff",
                        "Validate the first repository after the second.",
                        repo=repo_one,
                    ),
                ]
            )
            result = engine.validate_response_multi(
                rendered,
                {
                    str(repo_one.resolve()): ["one.txt"],
                    str(repo_two.resolve()): ["two.txt"],
                },
            )
            self.assertTrue(result["valid"])

    def test_rejects_commit_targeting_different_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_one = root / "one"
            repo_two = root / "two"
            repo_one.mkdir()
            repo_two.mkdir()
            rendered = engine.render_handoff(
                ["file.txt"],
                "fix(governance): reject mismatched repository",
                "Reject add and commit commands that target different repositories.",
                repo=repo_one,
            ).replace(
                f"git -C {repo_one.resolve()} commit",
                f"git -C {repo_two.resolve()} commit",
            )
            result = engine.validate_response_multi(
                rendered,
                {str(repo_one.resolve()): ["file.txt"]},
            )
            self.assertFalse(result["valid"])
            self.assertIn(
                "same repository",
                " ".join(result["violations"]),
            )

    def test_renders_multi_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_one = root / "one"
            repo_two = root / "two"
            repo_one.mkdir()
            repo_two.mkdir()
            for repo in (repo_one, repo_two):
                subprocess.run(["git", "-C", str(repo), "init"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "config", "user.email", "t@example.com"],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "config", "user.name", "Test"],
                    check=True,
                )
                (repo / "file.txt").write_text("base\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "-m", "test: base"],
                    check=True,
                    stdout=subprocess.PIPE,
                )
                (repo / "file.txt").write_text("changed\n", encoding="utf-8")
            rendered = engine.render_multi_repo_handoff(
                {
                    str(repo_one.resolve()): ["file.txt"],
                    str(repo_two.resolve()): ["file.txt"],
                },
                "feat(governance): multi repo handoff",
                "Render one validated command pair for each touched repository.",
            )
            self.assertEqual(rendered.count("```bash"), 4)
            result = engine.validate_response_multi(
                rendered,
                {
                    str(repo_one.resolve()): ["file.txt"],
                    str(repo_two.resolve()): ["file.txt"],
                },
            )
            self.assertTrue(result["valid"])

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

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            with self.assertRaises(engine.HandoffError):
                engine.validate_paths(repo, ["../outside.txt"])

    def test_cli_render_with_explicit_paths(self):
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
            (root / "one.txt").write_text("base\n", encoding="utf-8")
            (root / "two.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-m", "test: base"],
                check=True,
                stdout=subprocess.PIPE,
            )
            (root / "one.txt").write_text("changed\n", encoding="utf-8")
            (root / "two.txt").write_text("also\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "python3",
                    str(ENGINE_PATH),
                    "render",
                    "--repo",
                    str(root),
                    "--path",
                    "one.txt",
                    "--title",
                    "fix: explicit path",
                    "--description",
                    "Render only the explicitly attributed path.",
                ],
                check=False,
                stdout=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("one.txt", result.stdout)
            self.assertNotIn("two.txt", result.stdout)

    def test_cli_rejects_clean_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init"], check=True)
            result = subprocess.run(
                [
                    "python3",
                    str(ENGINE_PATH),
                    "render",
                    "--repo",
                    str(root),
                    "--title",
                    "fix: clean repo",
                    "--description",
                    "Clean repositories must be rejected.",
                ],
                check=False,
                stdout=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 2)

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
                repo=root,
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
