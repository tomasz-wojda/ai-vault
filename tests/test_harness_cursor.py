import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "harness" / "cursor" / "hooks"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load_module("handoff_engine", ROOT / "scripts" / "commit_handoff.py")
baseline = load_module("baseline_hook", HOOKS / "capture-turn-baseline.py")
file_attribution = load_module(
    "file_attribution_hook",
    HOOKS / "record-file-attribution.py",
)
shell_baseline = load_module(
    "shell_baseline_hook",
    HOOKS / "capture-shell-baseline.py",
)
shell_attribution = load_module(
    "shell_attribution_hook",
    HOOKS / "record-shell-attribution.py",
)
capture = load_module("capture_hook", HOOKS / "capture-agent-response.py")
stop = load_module("stop_hook", HOOKS / "require-commit-handoff.py")
common = sys.modules["handoff_common"]
installer = load_module(
    "cursor_installer",
    ROOT / "scripts" / "install-cursor-harness.py",
)


def run_script(path: Path, payload: dict) -> tuple[int, dict]:
    result = subprocess.run(
        ["python3", str(path)],
        input=json.dumps(payload),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, output


class RepositoryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        subprocess.run(["git", "-C", str(self.repo), "init"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Test User"],
            check=True,
        )
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-m", "test: base"],
            check=True,
            stdout=subprocess.PIPE,
        )

    def tearDown(self):
        self.temporary.cleanup()


class GuardHookTest(unittest.TestCase):
    def setUp(self):
        self.script = HOOKS / "guard-git-mutations.py"

    def payload(self, command: str, cwd: Path) -> dict:
        return {
            "command": command,
            "cwd": str(cwd),
            "sandbox": False,
        }

    def test_denies_add_inside_git_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            code, output = run_script(
                self.script,
                self.payload("git add -- file.txt", repo),
            )
            self.assertEqual(code, 0)
            self.assertEqual(output["permission"], "deny")

    def test_denies_git_c_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            code, output = run_script(
                self.script,
                self.payload(f"git -C {repo} commit -m test", repo.parent),
            )
            self.assertEqual(code, 0)
            self.assertEqual(output["permission"], "deny")

    def test_denies_chained_directory_push(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            code, output = run_script(
                self.script,
                self.payload(f"cd {repo} && git push", repo.parent),
            )
            self.assertEqual(code, 0)
            self.assertEqual(output["permission"], "deny")

    def test_allows_read_only_git(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            code, output = run_script(
                self.script,
                self.payload("git status --short", repo),
            )
            self.assertEqual(code, 0)
            self.assertEqual(output["permission"], "allow")

    def test_allows_git_words_inside_command_argument(self):
        code, output = run_script(
            self.script,
            self.payload(
                "python3 renderer.py --description 'required git add command'",
                ROOT,
            ),
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "allow")

    def test_allows_non_git_directory_add(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = run_script(
                self.script,
                self.payload("git add -- file.txt", Path(directory)),
            )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "allow")


class ResponseHooksTest(unittest.TestCase):
    def setUp(self):
        self.state_root = Path(tempfile.mkdtemp())
        self.state_patch = mock.patch.object(common, "STATE_ROOT", self.state_root)
        self.migration_grace = self.state_root / ".migration-grace"
        self.baseline_grace_patch = mock.patch.object(
            baseline,
            "MIGRATION_GRACE",
            self.migration_grace,
        )
        self.capture_grace_patch = mock.patch.object(
            capture,
            "MIGRATION_GRACE",
            self.migration_grace,
        )
        self.state_patch.start()
        self.baseline_grace_patch.start()
        self.capture_grace_patch.start()

    def tearDown(self):
        self.capture_grace_patch.stop()
        self.baseline_grace_patch.stop()
        self.state_patch.stop()
        for path in self.state_root.rglob("*"):
            if path.is_file():
                path.unlink()
        for path in sorted(self.state_root.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
        self.state_root.rmdir()

    def invoke(self, module, payload: dict) -> dict:
        stdin = io.StringIO(json.dumps(payload))
        stdout = io.StringIO()
        with (
            mock.patch.object(module.sys, "stdin", stdin),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(module.main(), 0)
        return json.loads(stdout.getvalue()) if stdout.getvalue().strip() else {}

    def invoke_expect_error(self, module, payload: dict):
        stdin = io.StringIO(json.dumps(payload))
        stdout = io.StringIO()
        with (
            mock.patch.object(module.sys, "stdin", stdin),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(RuntimeError),
        ):
            module.main()

    def baseline_payload(self, workspace: Path, generation: str) -> dict:
        return {
            "conversation_id": "conversation-1",
            "generation_id": generation,
            "workspace_roots": [str(workspace)],
        }

    def response_fields(self) -> dict:
        return {
            "model": "test-model",
            "input_tokens": 120,
            "output_tokens": 40,
            "cache_read_tokens": 80,
            "cache_write_tokens": 20,
        }

    def capture_payload(
        self,
        workspace: Path,
        generation: str,
        text: str,
    ) -> dict:
        return {
            **self.baseline_payload(workspace, generation),
            **self.response_fields(),
            "text": text,
        }

    def stop_payload(
        self,
        workspace: Path,
        generation: str,
    ) -> dict:
        return {
            **self.baseline_payload(workspace, generation),
            **self.response_fields(),
            "status": "completed",
            "loop_count": 0,
        }

    def record_edit(
        self,
        workspace: Path,
        generation: str,
        path: Path,
    ) -> None:
        self.invoke(
            file_attribution,
            {
                **self.baseline_payload(workspace, generation),
                "file_path": str(path),
                "edits": [],
            },
        )

    def shell_payload(
        self,
        workspace: Path,
        generation: str,
        repo: Path,
        tool_use_id: str = "shell-tool-1",
    ) -> dict:
        return {
            **self.baseline_payload(workspace, generation),
            "tool_name": "Shell",
            "tool_input": {
                "command": "formatter",
                "working_directory": str(repo),
            },
            "tool_use_id": tool_use_id,
            "cwd": str(repo),
        }

    def initialize_repo(
        self,
        repo: Path,
        filename: str = "file.txt",
    ) -> Path:
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test User"],
            check=True,
        )
        path = repo / filename
        path.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", filename], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "test: base"],
            check=True,
            stdout=subprocess.PIPE,
        )
        return path

    def test_valid_response_allows_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
            )
            (repo / "changed.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "changed.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "test: base"],
                check=True,
                stdout=subprocess.PIPE,
            )
            generation = "valid-generation"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            (repo / "changed.txt").write_text("changed\n", encoding="utf-8")
            self.record_edit(
                workspace,
                generation,
                repo / "changed.txt",
            )
            response = engine.render_handoff(
                    ["changed.txt"],
                    "feat(governance): validate hook response",
                    "Validate the exact response before allowing the agent to stop.",
                    repo=repo,
            )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": response,
                },
            )
            stop_output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertEqual(stop_output, {})

    def test_mismatched_stop_generation_uses_captured_response(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertEqual(output, {})
            self.assertFalse(
                common.pending_stop_path("conversation-1").exists()
            )
            self.assertFalse(
                common.state_path(
                    "conversation-1",
                    captured_generation,
                ).exists()
            )

    def test_mismatched_stop_generation_preserves_invalid_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            captured_generation = "captured-invalid-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            (repo / "changed.txt").write_text("changed\n", encoding="utf-8")
            self.record_edit(
                workspace,
                captured_generation,
                repo / "changed.txt",
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No handoff commands.",
                ),
            )
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertIn("followup_message", output)
            self.assertIn(str(repo.resolve()), output["followup_message"])
            self.assertFalse(
                common.pending_stop_path("conversation-1").exists()
            )

    def test_exact_generation_state_precedes_pending_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            exact_generation = "exact-generation"
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, exact_generation),
            )
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            output = self.invoke(
                stop,
                self.stop_payload(workspace, exact_generation),
            )
            self.assertEqual(output, {})
            self.assertFalse(
                common.pending_stop_path("conversation-1").exists()
            )

    def test_mismatched_response_signature_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            payload = self.stop_payload(
                workspace,
                "different-stop-generation",
            )
            payload["output_tokens"] += 1
            output = self.invoke(stop, payload)
            self.assertEqual(output, {})
            self.assertFalse(
                common.pending_stop_path("conversation-1").exists()
            )

    def test_incomplete_stop_signature_uses_validated_response(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            payload = self.stop_payload(
                workspace,
                "different-stop-generation",
            )
            del payload["cache_write_tokens"]
            output = self.invoke(stop, payload)
            self.assertEqual(output, {})
            self.assertFalse(
                common.pending_stop_path("conversation-1").exists()
            )

    def test_incomplete_stop_signature_preserves_invalid_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            (repo / "changed.txt").write_text("changed\n", encoding="utf-8")
            self.record_edit(
                workspace,
                captured_generation,
                repo / "changed.txt",
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No handoff commands.",
                ),
            )
            payload = self.stop_payload(
                workspace,
                "different-stop-generation",
            )
            del payload["cache_write_tokens"]
            output = self.invoke(stop, payload)
            self.assertIn("followup_message", output)
            self.assertIn(str(repo.resolve()), output["followup_message"])

    def test_stale_pending_response_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            pending = common.pending_stop_path("conversation-1")
            metadata = common.read_state(pending)
            metadata["captured_at_ns"] = (
                common.time.time_ns()
                - common.PENDING_STOP_MAX_AGE_NS
                - 1
            )
            common.write_state(pending, metadata)
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertEqual(output, {})

    def test_corrupt_pending_response_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            common.pending_stop_path("conversation-1").write_text(
                "{",
                encoding="utf-8",
            )
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertEqual(output, {})

    def test_cross_conversation_pending_response_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            pending = common.pending_stop_path("conversation-1")
            metadata = common.read_state(pending)
            metadata["conversation_id"] = "different-conversation"
            common.write_state(pending, metadata)
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertEqual(output, {})

    def test_mismatched_pending_timestamp_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            pending = common.pending_stop_path("conversation-1")
            metadata = common.read_state(pending)
            metadata["captured_at_ns"] += 1
            common.write_state(pending, metadata)
            output = self.invoke(
                stop,
                self.stop_payload(workspace, "different-stop-generation"),
            )
            self.assertEqual(output, {})

    def test_new_baseline_clears_pending_response(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            captured_generation = "captured-generation"
            self.invoke(
                baseline,
                self.baseline_payload(workspace, captured_generation),
            )
            self.invoke(
                capture,
                self.capture_payload(
                    workspace,
                    captured_generation,
                    "No repository changes.",
                ),
            )
            pending = common.pending_stop_path("conversation-1")
            self.assertTrue(pending.exists())
            self.invoke(
                baseline,
                self.baseline_payload(workspace, "next-generation"),
            )
            self.assertFalse(pending.exists())

    def test_invalid_response_forces_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            generation = "invalid-generation"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            (repo / "changed.txt").write_text("changed\n", encoding="utf-8")
            self.record_edit(
                workspace,
                generation,
                repo / "changed.txt",
            )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "No handoff commands.",
                },
            )
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertIn("followup_message", output)
            self.assertIn("exactly two bash blocks", output["followup_message"])
            self.assertIn(str(repo.resolve()), output["followup_message"])

    def test_missing_state_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, "missing-generation"),
                    "status": "completed",
                    "loop_count": 1,
                },
            )
            self.assertEqual(output, {})

    def test_corrupt_state_is_non_interrupting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "corrupt-generation"
            state = common.state_path("conversation-1", generation)
            state.parent.mkdir(parents=True)
            state.write_text("{", encoding="utf-8")
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertEqual(output, {})

    def test_no_changes_allows_response_without_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "no-changes-generation"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "No repository changes.",
                },
            )
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertEqual(output, {})

    def test_preexisting_dirty_untouched_allows_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
            )
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "dirty.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "test: base"],
                check=True,
                stdout=subprocess.PIPE,
            )
            (repo / "dirty.txt").write_text("preexisting\n", encoding="utf-8")
            generation = "preexisting-dirty"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Read-only turn with unrelated dirty file.",
                },
            )
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertEqual(output, {})

    def test_direct_edit_excludes_other_conversation_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo_one = workspace / "one"
            repo_two = workspace / "two"
            path_one = self.initialize_repo(repo_one)
            path_two = self.initialize_repo(repo_two)
            generation_one = "generation-one"
            generation_two = "generation-two"
            payload_one = self.baseline_payload(workspace, generation_one)
            payload_two = {
                "conversation_id": "conversation-2",
                "generation_id": generation_two,
                "workspace_roots": [str(workspace)],
            }
            self.invoke(baseline, payload_one)
            self.invoke(baseline, payload_two)
            path_one.write_text("agent one\n", encoding="utf-8")
            self.invoke(
                file_attribution,
                {
                    **payload_one,
                    "file_path": str(path_one),
                    "edits": [],
                },
            )
            path_two.write_text("agent two\n", encoding="utf-8")
            self.invoke(
                file_attribution,
                {
                    **payload_two,
                    "file_path": str(path_two),
                    "edits": [],
                },
            )
            self.invoke(
                capture,
                {
                    **payload_one,
                    "text": "Missing handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation_one)
            )
            self.assertEqual(
                state["repo_paths"],
                {str(repo_one.resolve()): ["file.txt"]},
            )

    def test_post_edit_collision_excludes_attributed_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            generation = "post-edit-collision"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            path.write_text("agent edit\n", encoding="utf-8")
            self.record_edit(workspace, generation, path)
            path.write_text("external edit\n", encoding="utf-8")
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "No handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(state["repo_paths"], {})

    def test_duplicate_edit_events_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            generation = "duplicate-edits"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            path.write_text("first edit\n", encoding="utf-8")
            self.record_edit(workspace, generation, path)
            path.write_text("second edit\n", encoding="utf-8")
            self.record_edit(workspace, generation, path)
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(
                state["repo_paths"],
                {str(repo.resolve()): ["file.txt"]},
            )

    def test_reverted_attributed_path_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            generation = "reverted-edit"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            path.write_text("agent edit\n", encoding="utf-8")
            self.record_edit(workspace, generation, path)
            path.write_text("base\n", encoding="utf-8")
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "No handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(state["repo_paths"], {})

    def test_preexisting_dirty_agent_edit_is_attributed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            path.write_text("preexisting\n", encoding="utf-8")
            generation = "preexisting-agent-edit"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            path.write_text("agent edit\n", encoding="utf-8")
            self.record_edit(workspace, generation, path)
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(
                state["repo_paths"],
                {str(repo.resolve()): ["file.txt"]},
            )

    def test_shell_attribution_is_scoped_to_working_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo_one = workspace / "one"
            repo_two = workspace / "two"
            path_one = self.initialize_repo(repo_one)
            path_two = self.initialize_repo(repo_two)
            generation = "shell-scoped"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            payload = self.shell_payload(
                workspace,
                generation,
                repo_one,
            )
            self.assertEqual(
                self.invoke(shell_baseline, payload),
                {"permission": "allow"},
            )
            path_one.write_text("shell edit\n", encoding="utf-8")
            path_two.write_text("external edit\n", encoding="utf-8")
            self.assertEqual(
                self.invoke(shell_attribution, payload),
                {},
            )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(
                state["repo_paths"],
                {str(repo_one.resolve()): ["file.txt"]},
            )

    def test_failed_shell_still_attributes_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            generation = "failed-shell"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            payload = self.shell_payload(
                workspace,
                generation,
                repo,
            )
            self.invoke(shell_baseline, payload)
            path.write_text("partial shell edit\n", encoding="utf-8")
            payload.update(
                {
                    "hook_event_name": "postToolUseFailure",
                    "error_message": "failed",
                    "failure_type": "error",
                }
            )
            self.invoke(shell_attribution, payload)
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(
                state["repo_paths"],
                {str(repo.resolve()): ["file.txt"]},
            )

    def test_shell_without_matching_baseline_adds_no_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo = workspace / "repo"
            path = self.initialize_repo(repo)
            generation = "missing-shell-baseline"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            path.write_text("unattributed edit\n", encoding="utf-8")
            payload = self.shell_payload(
                workspace,
                generation,
                repo,
            )
            self.assertEqual(
                self.invoke(shell_attribution, payload),
                {},
            )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "No handoff.",
                },
            )
            state = common.read_state(
                common.state_path("conversation-1", generation)
            )
            self.assertEqual(state["repo_paths"], {})

    def test_two_repositories_require_two_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            repo_one = workspace / "one"
            repo_two = workspace / "two"
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
            generation = "two-repos"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            for repo in (repo_one, repo_two):
                (repo / "file.txt").write_text("changed\n", encoding="utf-8")
                self.record_edit(
                    workspace,
                    generation,
                    repo / "file.txt",
                )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing both handoffs.",
                },
            )
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertIn("2 repositories", output["followup_message"])
            self.assertIn(str(repo_one.resolve()), output["followup_message"])
            self.assertIn(str(repo_two.resolve()), output["followup_message"])

    def test_repository_created_after_baseline_requires_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "new-repository"
            self.invoke(baseline, self.baseline_payload(workspace, generation))
            repo = workspace / "new-repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True)
            (repo / "created.txt").write_text("created\n", encoding="utf-8")
            self.record_edit(
                workspace,
                generation,
                repo / "created.txt",
            )
            self.invoke(
                capture,
                {
                    **self.baseline_payload(workspace, generation),
                    "text": "Missing new repository handoff.",
                },
            )
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, generation),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertIn("followup_message", output)
            self.assertIn(str(repo.resolve()), output["followup_message"])
            self.assertIn("--path created.txt", output["followup_message"])

    def test_capture_missing_baseline_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.invoke_expect_error(
                capture,
                {
                    **self.baseline_payload(workspace, "missing-baseline"),
                    "text": "No baseline.",
                },
            )

    def test_migration_grace_allows_only_inflight_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.migration_grace.parent.mkdir(parents=True, exist_ok=True)
            self.migration_grace.write_text("pending\n", encoding="utf-8")
            payload = {
                **self.baseline_payload(workspace, "migration-generation"),
                "text": "Migration turn.",
            }
            self.invoke(capture, payload)
            self.assertFalse(self.migration_grace.exists())
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(
                        workspace,
                        "migration-generation",
                    ),
                    "status": "completed",
                    "loop_count": 0,
                },
            )
            self.assertEqual(output, {})
            self.invoke_expect_error(
                capture,
                {
                    **self.baseline_payload(workspace, "next-generation"),
                    "text": "No baseline.",
                },
            )

    def test_non_completed_stop_does_not_follow_up(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = self.invoke(
                stop,
                {
                    **self.baseline_payload(workspace, "aborted-generation"),
                    "status": "aborted",
                    "loop_count": 0,
                },
            )
            self.assertEqual(output, {})


class InstallerTest(unittest.TestCase):
    def invoke_main(self, arguments: list[str]) -> tuple[int, dict]:
        stdout = io.StringIO()
        with (
            mock.patch.object(installer.sys, "argv", ["installer", *arguments]),
            contextlib.redirect_stdout(stdout),
        ):
            code = installer.main()
        return code, json.loads(stdout.getvalue())

    def test_workspace_argument_preserves_legacy_cli_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.invoke_main(["--workspace", directory])
            self.assertEqual(code, 0)
            self.assertEqual(output["scope"], "workspace")

    def test_user_scope_preview_apply_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            cursor = home / ".cursor"
            cursor.mkdir(parents=True)
            hooks_path = cursor / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "beforeShellExecution": [
                                {"command": ".cursor/hooks/unrelated.py"}
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(Path, "home", return_value=home):
                actions, hooks, path = installer.plan_install(
                    "user",
                    None,
                    ROOT,
                    migrate_legacy=False,
                )
            self.assertTrue(any(item["status"] == "create" for item in actions))
            with mock.patch.object(Path, "home", return_value=home):
                installer.apply_install(actions, hooks, path)
                installer.verify_install(actions, path, ROOT, "user")
            installed = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item["command"]
                for definitions in installed["hooks"].values()
                for item in definitions
            ]
            self.assertIn(".cursor/hooks/unrelated.py", commands)
            self.assertIn("hooks/git-handoff-guard-git.py", commands)
            self.assertIn("hooks/git-handoff-baseline.py", commands)
            self.assertIn(
                "hooks/git-handoff-file-attribution.py",
                commands,
            )
            self.assertIn(
                "hooks/git-handoff-shell-baseline.py",
                commands,
            )
            self.assertIn(
                "hooks/git-handoff-shell-attribution.py",
                commands,
            )
            with mock.patch.object(Path, "home", return_value=home):
                repeated, repeated_hooks, repeated_path = installer.plan_install(
                    "user",
                    None,
                    ROOT,
                    migrate_legacy=False,
                )
            self.assertTrue(all(item["status"] == "unchanged" for item in repeated))

    def test_workspace_preview_apply_preserve_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cursor = workspace / ".cursor"
            rules = cursor / "rules"
            rules.mkdir(parents=True)
            memory_rule = rules / "worklog-chat-memory.mdc"
            memory_rule.write_text("memory\n", encoding="utf-8")
            hooks_path = cursor / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "beforeShellExecution": [
                                {"command": ".cursor/hooks/unrelated.py"}
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            actions, hooks, path = installer.plan_install(
                "workspace",
                workspace,
                ROOT,
                migrate_legacy=True,
            )
            self.assertTrue(any(item["status"] == "create" for item in actions))
            installer.apply_install(actions, hooks, path)
            installer.verify_install(actions, path, ROOT, "workspace")
            self.assertEqual(memory_rule.read_text(encoding="utf-8"), "memory\n")
            installed = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item["command"]
                for definitions in installed["hooks"].values()
                for item in definitions
            ]
            self.assertIn(".cursor/hooks/unrelated.py", commands)
            self.assertIn(".cursor/hooks/git-handoff-guard-git.py", commands)
            self.assertEqual(
                installed["hooks"]["preToolUse"][0]["matcher"],
                "Shell",
            )
            self.assertEqual(
                installed["hooks"]["postToolUse"][0]["matcher"],
                "Shell",
            )
            self.assertEqual(
                installed["hooks"]["postToolUseFailure"][0]["matcher"],
                "Shell",
            )
            self.assertEqual(installed["hooks"]["stop"][0]["loop_limit"], 2)
            repeated, repeated_hooks, repeated_path = installer.plan_install(
                "workspace",
                workspace,
                ROOT,
                migrate_legacy=True,
            )
            self.assertTrue(all(item["status"] == "unchanged" for item in repeated))

    def test_migrates_legacy_workspace_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cursor = workspace / ".cursor"
            hook_dir = cursor / "hooks"
            hook_dir.mkdir(parents=True)
            legacy = hook_dir / "ai-vault-guard-git.py"
            source = HOOKS / "guard-git-mutations.py"
            legacy.symlink_to(os.path.relpath(source.resolve(), hook_dir.resolve()))
            hooks_path = cursor / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "beforeShellExecution": [
                                {
                                    "command": ".cursor/hooks/ai-vault-guard-git.py",
                                    "failClosed": True,
                                },
                                {"command": ".cursor/hooks/unrelated.py"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            actions, hooks, path = installer.plan_install(
                "workspace",
                workspace,
                ROOT,
                migrate_legacy=True,
            )
            installer.apply_install(actions, hooks, path)
            installer.verify_install(actions, path, ROOT, "workspace")
            installed = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item["command"]
                for item in installed["hooks"]["beforeShellExecution"]
            ]
            self.assertNotIn(".cursor/hooks/ai-vault-guard-git.py", commands)
            self.assertIn(".cursor/hooks/git-handoff-guard-git.py", commands)
            self.assertIn(".cursor/hooks/unrelated.py", commands)
            self.assertFalse(legacy.exists())

    def test_user_migration_removes_legacy_and_installs_generic_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cursor = workspace / ".cursor"
            hook_dir = cursor / "hooks"
            rule_dir = cursor / "rules"
            hook_dir.mkdir(parents=True)
            rule_dir.mkdir(parents=True)
            legacy_hook = hook_dir / "ai-vault-guard-git.py"
            legacy_hook.symlink_to(
                os.path.relpath(
                    (HOOKS / "guard-git-mutations.py").resolve(),
                    hook_dir.resolve(),
                )
            )
            legacy_rule = rule_dir / "ai-vault-governance.mdc"
            legacy_rule.symlink_to(
                os.path.relpath(
                    (
                        ROOT
                        / "harness"
                        / "cursor"
                        / "rules"
                        / "ai-vault-governance.mdc"
                    ).resolve(),
                    rule_dir.resolve(),
                )
            )
            hooks_path = cursor / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "beforeShellExecution": [
                                {
                                    "command": ".cursor/hooks/ai-vault-guard-git.py"
                                },
                                {"command": ".cursor/hooks/unrelated.py"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            actions, hooks, path = installer.plan_legacy_removal(
                workspace,
                ROOT,
            )
            installer.apply_install(actions, hooks, path)
            installer.verify_legacy_removal(actions, path)
            installed = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item["command"]
                for item in installed["hooks"]["beforeShellExecution"]
            ]
            self.assertEqual(commands, [".cursor/hooks/unrelated.py"])
            self.assertFalse(legacy_hook.exists())
            self.assertFalse(legacy_rule.exists())
            self.assertTrue(
                (rule_dir / "git-handoff-governance.mdc").is_symlink()
            )

    def test_migration_preserves_foreign_legacy_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            hook_dir = workspace / ".cursor" / "hooks"
            rule_dir = workspace / ".cursor" / "rules"
            hook_dir.mkdir(parents=True)
            rule_dir.mkdir(parents=True)
            foreign_target = workspace / "foreign.py"
            foreign_target.write_text("foreign\n", encoding="utf-8")
            foreign_hook = hook_dir / "ai-vault-guard-git.py"
            foreign_hook.symlink_to(foreign_target)
            foreign_rule = rule_dir / "ai-vault-governance.mdc"
            foreign_rule.write_text("foreign\n", encoding="utf-8")
            actions, _, _ = installer.plan_legacy_removal(workspace, ROOT)
            removal_targets = {
                Path(item["target"])
                for item in actions
                if item["kind"] == "symlink-remove"
            }
            self.assertNotIn(foreign_hook, removal_targets)
            self.assertNotIn(foreign_rule, removal_targets)

    def test_refuses_to_replace_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / ".cursor" / "hooks" / "git-handoff-guard-git.py"
            target.parent.mkdir(parents=True)
            target.write_text("conflict\n", encoding="utf-8")
            with self.assertRaises(installer.InstallError):
                installer.plan_install("workspace", workspace, ROOT, migrate_legacy=False)


if __name__ == "__main__":
    unittest.main()
