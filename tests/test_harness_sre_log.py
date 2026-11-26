import contextlib
import importlib.util
import io
import json
import sys
import tempfile
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


prompt_hook = load_module(
    "sre_log_prompt_hook",
    HOOKS / "capture-sre-log-prompt.py",
)
read_hook = load_module(
    "sre_log_read_hook",
    HOOKS / "record-sre-skill-read.py",
)
response_hook = load_module(
    "sre_log_response_hook",
    HOOKS / "capture-sre-log-response.py",
)
stop_hook = load_module(
    "sre_log_stop_hook",
    HOOKS / "require-sre-log-entry.py",
)
sre = sys.modules["sre_log_common"]


class SreLogHookTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name).resolve()
        self.workspace = base / "workspace"
        self.workspace.mkdir()
        self.state_root = base / "state"
        self.state_patch = mock.patch.object(sre, "STATE_ROOT", self.state_root)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.directory.cleanup()

    def payload(self, **extra) -> dict:
        return {
            "conversation_id": "conversation-1",
            "generation_id": "generation-1",
            "workspace_roots": [str(self.workspace)],
            **extra,
        }

    def run_hook(self, module, payload: dict) -> dict:
        stdout = io.StringIO()
        with mock.patch.object(
            sys,
            "stdin",
            io.StringIO(json.dumps(payload)),
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(0, module.main())
        return json.loads(stdout.getvalue())

    def state(self) -> dict | None:
        return sre.load_generation("conversation-1", "generation-1")

    def prompt(self, text: str = "check the alert") -> dict:
        return self.run_hook(prompt_hook, self.payload(prompt=text))

    def read(self, key: str, path: str) -> dict:
        return self.run_hook(
            read_hook,
            self.payload(tool_name="Read", tool_input={key: path}),
        )

    def stop(self, status: str = "completed", loop_count: int = 0) -> dict:
        return self.run_hook(
            stop_hook,
            self.payload(status=status, loop_count=loop_count),
        )

    def invoke(self) -> None:
        self.prompt("use sre-incident-investigation on the 5xx alert")

    def test_prompt_naming_skill_marks_invoked(self):
        self.assertEqual({}, self.prompt("run sre-incident-investigation"))
        self.assertTrue(self.state()["invoked"])
        self.assertFalse(self.state()["waived"])
        self.assertEqual({str(self.workspace): 0}, self.state()["baseline"])

    def test_followup_prompt_saves_no_state(self):
        self.assertEqual({}, self.prompt(f"{sre.FOLLOWUP_PREFIX} write it"))
        self.assertIsNone(self.state())

    def test_skill_reads_mark_invoked(self):
        paths = (
            ("path", "/w/.cursor/skills/sre-incident-investigation/SKILL.md"),
            ("file_path", "/w/repos/ai-vault/skills/sre-incident-investigation/SKILL.md"),
            ("target_file", "/w/.claude/skills/sre-incident-investigation/SKILL.md"),
        )
        for key, path in paths:
            with self.subTest(key=key):
                self.prompt()
                self.assertFalse(self.state()["invoked"])
                self.assertEqual({}, self.read(key, path))
                self.assertTrue(self.state()["invoked"])

    def test_other_read_does_not_mark_invoked(self):
        self.prompt()
        self.read("path", "/w/repos/ai-vault/skills/sre-incident-investigation/README.md")
        self.read("file_path", "/w/repos/ai-vault/skills/pr-review-comments/SKILL.md")
        self.assertFalse(self.state()["invoked"])

    def test_stop_without_growth_requests_entry(self):
        self.invoke()
        result = self.stop()
        self.assertTrue(result["followup_message"].startswith(sre.FOLLOWUP_PREFIX))
        self.assertIn("append_sre_log.py", result["followup_message"])
        self.assertIn(sre.WAIVER, result["followup_message"])
        self.assertFalse(
            sre.generation_path("conversation-1", "generation-1").exists()
        )

    def test_stop_after_log_created_is_quiet(self):
        self.invoke()
        (self.workspace / sre.LOG_NAME).write_text("entry\n", encoding="utf-8")
        self.assertEqual({}, self.stop())

    def test_stop_after_log_grew_is_quiet(self):
        log = self.workspace / sre.LOG_NAME
        log.write_text("first\n", encoding="utf-8")
        self.invoke()
        with log.open("a", encoding="utf-8") as handle:
            handle.write("second\n")
        self.assertEqual({}, self.stop())

    def test_stop_after_waiver_is_quiet(self):
        self.invoke()
        self.run_hook(
            response_hook,
            self.payload(text=f"Skill edited. {sre.WAIVER}"),
        )
        self.assertTrue(self.state()["waived"])
        self.assertEqual({}, self.stop())

    def test_stop_ignores_incomplete_or_looped_generations(self):
        for status, loop_count in (("aborted", 0), ("completed", 1)):
            with self.subTest(status=status, loop_count=loop_count):
                self.invoke()
                self.assertEqual({}, self.stop(status, loop_count))
                self.assertIsNone(self.state())

    def test_stop_without_invocation_is_quiet(self):
        self.prompt()
        self.assertEqual({}, self.stop())
        self.assertIsNone(self.state())


if __name__ == "__main__":
    unittest.main()
