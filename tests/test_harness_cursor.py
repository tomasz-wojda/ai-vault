import contextlib
import importlib.util
import io
import json
import subprocess
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
capture = load_module("capture_hook", HOOKS / "capture-agent-response.py")
stop = load_module("stop_hook", HOOKS / "require-commit-handoff.py")
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


class GuardHookTest(unittest.TestCase):
    def setUp(self):
        self.script = HOOKS / "guard-git-mutations.py"

    def payload(self, command: str, cwd: Path) -> dict:
        return {
            "command": command,
            "cwd": str(cwd),
            "sandbox": False,
        }

    def test_denies_add_inside_vault(self):
        code, output = run_script(
            self.script,
            self.payload("git add -- file.txt", ROOT),
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "deny")

    def test_denies_git_c_commit(self):
        code, output = run_script(
            self.script,
            self.payload(f"git -C {ROOT} commit -m test", ROOT.parent),
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "deny")

    def test_denies_chained_directory_push(self):
        code, output = run_script(
            self.script,
            self.payload(f"cd {ROOT} && git push", ROOT.parent),
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "deny")

    def test_allows_read_only_git(self):
        code, output = run_script(
            self.script,
            self.payload("git status --short", ROOT),
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

    def test_allows_unrelated_repository_add(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = run_script(
                self.script,
                self.payload("git add -- file.txt", Path(directory)),
            )
        self.assertEqual(code, 0)
        self.assertEqual(output["permission"], "allow")


class ResponseHooksTest(unittest.TestCase):
    def invoke(self, module, payload: dict, workspace: Path) -> dict:
        stdin = io.StringIO(json.dumps(payload))
        stdout = io.StringIO()
        with (
            mock.patch.object(module, "workspace_root", return_value=workspace),
            mock.patch.object(module.sys, "stdin", stdin),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(module.main(), 0)
        return json.loads(stdout.getvalue()) if stdout.getvalue().strip() else {}

    def test_valid_response_allows_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            paths = ["changed.txt"]
            response = engine.render_handoff(
                paths,
                "feat(governance): validate hook response",
                "Validate the exact response before allowing the agent to stop.",
            )
            generation = "valid-generation"
            fake_engine = types.SimpleNamespace(
                changed_paths=lambda _: paths,
                validate_response=engine.validate_response,
            )
            with mock.patch.object(capture, "load_engine", return_value=fake_engine):
                capture_output = self.invoke(
                    capture,
                    {
                        "generation_id": generation,
                        "workspace_roots": [str(workspace)],
                        "text": response,
                    },
                    workspace,
                )
            self.assertEqual(capture_output, {})
            stop_output = self.invoke(
                stop,
                {
                    "generation_id": generation,
                    "workspace_roots": [str(workspace)],
                    "status": "completed",
                    "loop_count": 0,
                },
                workspace,
            )
            self.assertEqual(stop_output, {})

    def test_invalid_response_forces_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "invalid-generation"
            fake_engine = types.SimpleNamespace(
                changed_paths=lambda _: ["changed.txt"],
                validate_response=engine.validate_response,
            )
            with mock.patch.object(capture, "load_engine", return_value=fake_engine):
                self.invoke(
                    capture,
                    {
                        "generation_id": generation,
                        "workspace_roots": [str(workspace)],
                        "text": "No handoff commands.",
                    },
                    workspace,
                )
            output = self.invoke(
                stop,
                {
                    "generation_id": generation,
                    "workspace_roots": [str(workspace)],
                    "status": "completed",
                    "loop_count": 0,
                },
                workspace,
            )
            self.assertIn("followup_message", output)
            self.assertIn("exactly two bash blocks", output["followup_message"])

    def test_missing_state_forces_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = self.invoke(
                stop,
                {
                    "generation_id": "missing-generation",
                    "workspace_roots": [str(workspace)],
                    "status": "completed",
                    "loop_count": 1,
                },
                workspace,
            )
            self.assertIn("validation state is missing", output["followup_message"])

    def test_corrupt_state_forces_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "corrupt-generation"
            state = (
                workspace
                / ".cursor"
                / "hook-state"
                / "ai-vault-handoff"
                / f"{generation}.json"
            )
            state.parent.mkdir(parents=True)
            state.write_text("{", encoding="utf-8")
            output = self.invoke(
                stop,
                {
                    "generation_id": generation,
                    "workspace_roots": [str(workspace)],
                    "status": "completed",
                    "loop_count": 0,
                },
                workspace,
            )
            self.assertIn("validation state is corrupt", output["followup_message"])

    def test_no_changes_allows_response_without_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generation = "no-changes-generation"
            fake_engine = types.SimpleNamespace(
                changed_paths=lambda _: [],
                validate_response=engine.validate_response,
            )
            with mock.patch.object(capture, "load_engine", return_value=fake_engine):
                self.invoke(
                    capture,
                    {
                        "generation_id": generation,
                        "workspace_roots": [str(workspace)],
                        "text": "No repository changes.",
                    },
                    workspace,
                )
            output = self.invoke(
                stop,
                {
                    "generation_id": generation,
                    "workspace_roots": [str(workspace)],
                    "status": "completed",
                    "loop_count": 0,
                },
                workspace,
            )
            self.assertEqual(output, {})

    def test_non_completed_stop_does_not_follow_up(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = self.invoke(
                stop,
                {
                    "generation_id": "aborted-generation",
                    "workspace_roots": [str(workspace)],
                    "status": "aborted",
                    "loop_count": 0,
                },
                workspace,
            )
            self.assertEqual(output, {})


class InstallerTest(unittest.TestCase):
    def test_preview_apply_preserve_and_repeat(self):
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
            actions, hooks, path = installer.plan_install(workspace, ROOT)
            self.assertTrue(any(item["status"] == "create" for item in actions))
            self.assertFalse((cursor / "hooks" / "ai-vault-guard-git.py").exists())
            installer.apply_install(actions, hooks, path)
            installer.verify_install(actions, path)
            self.assertEqual(memory_rule.read_text(encoding="utf-8"), "memory\n")
            installed = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item["command"]
                for item in installed["hooks"]["beforeShellExecution"]
            ]
            self.assertIn(".cursor/hooks/unrelated.py", commands)
            self.assertIn(".cursor/hooks/ai-vault-guard-git.py", commands)
            self.assertEqual(installed["hooks"]["stop"][0]["loop_limit"], 2)
            repeated, repeated_hooks, repeated_path = installer.plan_install(
                workspace,
                ROOT,
            )
            self.assertTrue(all(item["status"] == "unchanged" for item in repeated))
            installer.apply_install(repeated, repeated_hooks, repeated_path)
            installer.verify_install(repeated, repeated_path)

    def test_refuses_to_replace_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / ".cursor" / "hooks" / "ai-vault-guard-git.py"
            target.parent.mkdir(parents=True)
            target.write_text("conflict\n", encoding="utf-8")
            with self.assertRaises(installer.InstallError):
                installer.plan_install(workspace, ROOT)


if __name__ == "__main__":
    unittest.main()
