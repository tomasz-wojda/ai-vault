import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "worklog-chat-memory" / "scripts" / "record_turn.py"
HANDOFF = (
    "Done.\n```bash\ngit -C /repo add -- README.md\n```\n"
    "Quoting `$(rm -rf x)` and \"$HOME\" stays literal."
)


class RecordTurnTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.directory.name)
        self.memory_repo = self.workspace / "repos" / "ai-memory-ingester"
        self.memory_repo.mkdir(parents=True)
        self.received = self.workspace / "received.json"
        self.payload = self.workspace / "tmp" / "turn.json"
        self.payload.parent.mkdir()

    def tearDown(self):
        self.directory.cleanup()

    def ingester(self, exit_code: int) -> None:
        script = self.memory_repo / "ai-memory-ingester"
        script.write_text(
            "#!/bin/sh\n"
            f"[ \"$1\" = record-event ] || exit 9\n"
            f"cat > '{self.received}'\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def write_payload(self, **overrides) -> dict:
        payload = {
            "schema_version": 1,
            "source_ide": "cursor",
            "source_kind": "rule_write",
            "source_identity": "prompt.log",
            "user_text": "commit this",
            "assistant_text": HANDOFF,
            "mode": "execute",
        }
        payload.update(overrides)
        self.payload.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def run_script(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(self.workspace),
                "--payload",
                str(self.payload),
                *extra,
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_records_journal_then_appends_exact_prompt_log_entry(self):
        self.ingester(0)
        payload = self.write_payload()
        prompt_log = self.workspace / "prompt.log"
        prompt_log.write_text("earlier\n", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.received.read_text()), payload)
        text = prompt_log.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("earlier\n--- PROMPT LOG ENTRY ---\n"))
        self.assertIn("USER: commit this\n", text)
        self.assertIn(f"ASSISTANT: execute — {HANDOFF}\n", text)
        self.assertTrue(text.endswith("--- END PROMPT LOG ENTRY ---\n"))
        self.assertFalse(self.payload.exists())

    def test_creates_prompt_log_and_keeps_payload_on_request(self):
        self.ingester(0)
        self.write_payload(mode=None)
        result = self.run_script("--keep-payload")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.workspace / "prompt.log").read_text(encoding="utf-8")
        self.assertIn(f"ASSISTANT: {HANDOFF}\n", text)
        self.assertTrue(self.payload.exists())

    def test_record_event_failure_skips_prompt_log(self):
        self.ingester(3)
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 3)
        self.assertIn("prompt.log not appended", result.stderr)
        self.assertFalse((self.workspace / "prompt.log").exists())
        self.assertTrue(self.payload.exists())

    def test_invalid_payload_is_rejected_before_record_event(self):
        self.ingester(0)
        self.write_payload()
        payload = json.loads(self.payload.read_text())
        del payload["assistant_text"]
        self.payload.write_text(json.dumps(payload), encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing assistant_text", result.stderr)
        self.assertFalse(self.received.exists())
        self.assertFalse((self.workspace / "prompt.log").exists())

    def test_discovers_workspace_root_from_payload_path(self):
        self.ingester(0)
        self.write_payload()
        environment = {
            key: value
            for key, value in os.environ.items()
            if key != "MEMORY_WORKSPACE_ROOT"
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--payload", str(self.payload)],
            capture_output=True,
            text=True,
            cwd=self.directory.name,
            env={**environment, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / "prompt.log").exists())

    def test_payload_outside_workspace_requires_root(self):
        with tempfile.TemporaryDirectory() as outside:
            payload = Path(outside) / "turn.json"
            payload.write_text("{}", encoding="utf-8")
            environment = {
                key: value
                for key, value in os.environ.items()
                if key != "MEMORY_WORKSPACE_ROOT"
            }
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--payload", str(payload)],
                capture_output=True,
                text=True,
                env=environment,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("workspace root not found", result.stderr)

    def test_wrong_schema_version_is_rejected(self):
        self.ingester(0)
        self.write_payload(schema_version=2)
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.received.exists())


if __name__ == "__main__":
    unittest.main()
