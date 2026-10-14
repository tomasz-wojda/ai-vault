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
    "ticket_sync_prompt_hook",
    HOOKS / "capture-ticket-sync-prompt.py",
)
response_hook = load_module(
    "ticket_sync_response_hook",
    HOOKS / "capture-ticket-sync-response.py",
)
edit_hook = load_module(
    "ticket_sync_edit_hook",
    HOOKS / "record-ticket-sync-edit.py",
)
stop_hook = load_module(
    "ticket_sync_stop_hook",
    HOOKS / "require-ticket-sync.py",
)
sync = sys.modules["ticket_sync_common"]

PRIMARY = "2026-10-12_SCTASK1280900.log"
RAW = "2026-10-12_SCTASK1280900_raw.log"
JIRA = "2026-10-13_KD-6945.log"


class TicketSyncTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name).resolve()
        self.workspace = base / "workspace"
        (self.workspace / "worklog" / "done").mkdir(parents=True)
        self.state_root = base / "state"
        self.state_patch = mock.patch.object(
            sync,
            "STATE_ROOT",
            self.state_root,
        )
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.directory.cleanup()

    def worklog(self, name: str, done: bool = False) -> Path:
        directory = self.workspace / "worklog"
        if done:
            directory = directory / "done"
        path = directory / name
        path.write_text("worklog\n", encoding="utf-8")
        return path

    def payload(self, generation: str = "generation-1", **extra) -> dict:
        return {
            "conversation_id": "conversation-1",
            "generation_id": generation,
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

    def state(self, generation: str = "generation-1") -> dict | None:
        return sync.load_generation("conversation-1", generation)

    def stop(self, status: str = "completed", loop_count: int = 0) -> dict:
        return self.run_hook(
            stop_hook,
            self.payload(status=status, loop_count=loop_count),
        )

    def test_worklog_key_parsing(self):
        self.assertEqual("SCTASK1280900", sync.worklog_key(PRIMARY))
        self.assertEqual("SCTASK1280900", sync.worklog_key(RAW))
        self.assertEqual("KD-6945", sync.worklog_key(JIRA))
        self.assertEqual(
            "KD-6945",
            sync.worklog_key("2026-10-13_KD-6945_jira.log"),
        )
        self.assertIsNone(sync.worklog_key("notes.log"))
        self.assertIsNone(sync.worklog_key("2026-10-13_lower.log"))
        self.assertIsNone(sync.worklog_key("2026-10-13_KD-6945.txt"))

    def test_active_worklogs_ignore_done(self):
        self.worklog(PRIMARY)
        self.worklog(RAW)
        self.worklog(JIRA, done=True)
        (self.workspace / "worklog" / "notes.log").write_text(
            "x\n",
            encoding="utf-8",
        )
        self.assertEqual(
            {"SCTASK1280900": [f"worklog/{PRIMARY}", f"worklog/{RAW}"]},
            sync.active_worklogs([self.workspace]),
        )
        self.assertEqual({}, sync.active_worklogs([self.workspace / "none"]))

    def test_mentioned_keys_match_whole_tokens(self):
        keys = {"KD-69", "KD-6945", "SCTASK1280900"}
        self.assertEqual(
            {"KD-6945", "SCTASK1280900"},
            sync.mentioned_keys(
                f"see KD-6945 and worklog/{PRIMARY}",
                keys,
            ),
        )
        self.assertEqual({"KD-69"}, sync.mentioned_keys("KD-69 only", keys))
        self.assertEqual(set(), sync.mentioned_keys("XKD-69 KD-694", keys))
        self.assertEqual(set(), sync.mentioned_keys("", keys))

    def test_baseline_resets_and_records_prompt_keys(self):
        self.worklog(PRIMARY)
        self.worklog(JIRA)
        stale = self.state_root / "conversation-1" / "old.json"
        stale.parent.mkdir(parents=True)
        stale.write_text("{}", encoding="utf-8")
        output = self.run_hook(
            prompt_hook,
            self.payload(prompt="update SCTASK1280900 please"),
        )
        self.assertEqual({}, output)
        self.assertFalse(stale.exists())
        state = self.state()
        self.assertEqual(["SCTASK1280900"], state["keys"])
        self.assertEqual([], state["edited_keys"])
        self.assertEqual([str(self.workspace)], state["workspace_roots"])

    def test_response_adds_keys(self):
        self.worklog(PRIMARY)
        self.worklog(JIRA)
        self.run_hook(prompt_hook, self.payload(prompt="update SCTASK1280900"))
        output = self.run_hook(
            response_hook,
            self.payload(text="KD-6945 also changed"),
        )
        self.assertEqual({}, output)
        self.assertEqual(["KD-6945", "SCTASK1280900"], self.state()["keys"])

    def test_response_without_state_is_noop(self):
        self.worklog(PRIMARY)
        output = self.run_hook(
            response_hook,
            self.payload(text="SCTASK1280900"),
        )
        self.assertEqual({}, output)
        self.assertIsNone(self.state())
        self.assertFalse((self.state_root / "conversation-1").exists())

    def test_edit_records_worklog_and_ignores_other_files(self):
        primary = self.worklog(PRIMARY)
        done = self.worklog(JIRA, done=True)
        other = self.workspace / "notes.txt"
        other.write_text("x\n", encoding="utf-8")
        self.run_hook(prompt_hook, self.payload(prompt=""))
        self.run_hook(edit_hook, self.payload(file_path=str(other)))
        self.run_hook(edit_hook, self.payload(file_path=str(done)))
        self.assertEqual([], self.state()["edited_keys"])
        self.run_hook(edit_hook, self.payload(file_path=str(primary)))
        state = self.state()
        self.assertEqual(["SCTASK1280900"], state["keys"])
        self.assertEqual(["SCTASK1280900"], state["edited_keys"])

    def test_stop_forces_followup_for_pending_key(self):
        self.worklog(JIRA)
        self.run_hook(prompt_hook, self.payload(prompt="look at KD-6945"))
        output = self.stop()
        self.assertEqual(
            {
                "followup_message": (
                    "Ticket sync (R-29): this turn touched `KD-6945` "
                    "(`worklog/2026-10-13_KD-6945.log`). Without a Write Gate "
                    "preview and in the current mode, record anything new "
                    "from this turn in each listed worklog and, where "
                    "`.ai-worklog/state/<KEY>.json` exists, apply the "
                    "matching `ai-worklog state` commands with `--apply`. Do "
                    "not create, archive, or close out worklogs or state. If "
                    "nothing new was produced for a ticket, reply `No ticket "
                    "sync needed for <KEY>.` and stop."
                )
            },
            output,
        )
        self.assertFalse(
            sync.generation_path("conversation-1", "generation-1").exists()
        )

    def test_stop_lists_two_keys_sorted(self):
        self.worklog(PRIMARY)
        self.worklog(RAW)
        self.worklog(JIRA)
        self.run_hook(
            prompt_hook,
            self.payload(prompt="SCTASK1280900 and KD-6945"),
        )
        message = self.stop()["followup_message"]
        self.assertIn(
            "touched `KD-6945` (`worklog/2026-10-13_KD-6945.log`), "
            "`SCTASK1280900` (`worklog/2026-10-12_SCTASK1280900.log`, "
            "`worklog/2026-10-12_SCTASK1280900_raw.log`).",
            message,
        )

    def test_stop_skips_edited_key(self):
        primary = self.worklog(PRIMARY)
        self.run_hook(prompt_hook, self.payload(prompt="SCTASK1280900"))
        self.run_hook(edit_hook, self.payload(file_path=str(primary)))
        self.assertEqual({}, self.stop())

    def test_stop_skips_followup_generation(self):
        self.worklog(PRIMARY)
        self.run_hook(prompt_hook, self.payload(prompt="SCTASK1280900"))
        self.assertEqual({}, self.stop(loop_count=1))
        self.assertIsNone(self.state())

    def test_stop_skips_incomplete_generation(self):
        self.worklog(PRIMARY)
        self.run_hook(prompt_hook, self.payload(prompt="SCTASK1280900"))
        self.assertEqual({}, self.stop(status="aborted"))
        self.assertIsNone(self.state())

    def test_stop_without_state_is_noop(self):
        self.worklog(PRIMARY)
        self.assertEqual({}, self.stop())

    def test_stop_skips_worklog_moved_to_done(self):
        primary = self.worklog(PRIMARY)
        self.run_hook(prompt_hook, self.payload(prompt="SCTASK1280900"))
        primary.rename(self.workspace / "worklog" / "done" / PRIMARY)
        self.assertEqual({}, self.stop())


if __name__ == "__main__":
    unittest.main()
