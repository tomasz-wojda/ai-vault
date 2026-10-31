import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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

    def hold_lock(self, seconds: float) -> subprocess.Popen:
        lock = self.workspace / ".ai-worklog" / "locks" / "_journal.sqlite"
        lock.parent.mkdir(parents=True, exist_ok=True)
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sqlite3, sys, time\n"
                "c = sqlite3.connect(sys.argv[1], isolation_level=None)\n"
                "c.execute('BEGIN EXCLUSIVE')\n"
                "print('held', flush=True)\n"
                "time.sleep(float(sys.argv[2]))\n",
                str(lock),
                str(seconds),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(holder.stdout.readline().strip(), "held")
        return holder

    def test_busy_lock_records_nothing_and_leaves_prompt_log_alone(self):
        self.ingester(0)
        self.write_payload()
        holder = self.hold_lock(5)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--workspace-root",
                    str(self.workspace),
                    "--payload",
                    str(self.payload),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "AI_MEMORY_LOCK_TIMEOUT": "0.3",
                },
            )
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(result.returncode, 75)
        self.assertIn("memory lock busy", result.stderr)
        self.assertFalse(self.received.exists())
        self.assertFalse((self.workspace / "prompt.log").exists())
        self.assertTrue(self.payload.exists())

    def test_waits_for_a_short_lock_then_records(self):
        self.ingester(0)
        self.write_payload()
        holder = self.hold_lock(1)
        try:
            result = self.run_script()
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / "prompt.log").exists())

    def test_lock_off_switch_does_not_create_the_lock_file(self):
        self.ingester(0)
        self.write_payload()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(self.workspace),
                "--payload",
                str(self.payload),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "AI_MEMORY_LOCK": "0"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(
            (self.workspace / ".ai-worklog" / "locks" / "_journal.sqlite").exists()
        )

    def test_parallel_writers_keep_prompt_log_entries_whole(self):
        self.ingester(0)
        big = "x" * 200_000
        per_writer = 10
        failures = []

        def writer(name: str) -> None:
            for index in range(per_writer):
                payload_path = self.payload.parent / f"{name}-{index}.json"
                payload_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "source_ide": "cursor",
                            "source_kind": "rule_write",
                            "source_identity": "prompt.log",
                            "user_text": f"{name}-{index}",
                            "assistant_text": big + name,
                        }
                    ),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--workspace-root",
                        str(self.workspace),
                        "--payload",
                        str(payload_path),
                    ],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                if result.returncode != 0:
                    failures.append(result.stderr)

        threads = [threading.Thread(target=writer, args=(name,)) for name in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        text = (self.workspace / "prompt.log").read_text(encoding="utf-8")
        entries = text.split("--- PROMPT LOG ENTRY ---\n")[1:]
        self.assertEqual(len(entries), 2 * per_writer)
        for entry in entries:
            self.assertTrue(entry.endswith("--- END PROMPT LOG ENTRY ---\n"))
            self.assertEqual(entry.count("--- END PROMPT LOG ENTRY ---"), 1)
            self.assertEqual(entry.count("x" * 1000), 200)

    def test_wrong_schema_version_is_rejected(self):
        self.ingester(0)
        self.write_payload(schema_version=2)
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.received.exists())


if __name__ == "__main__":
    unittest.main()
