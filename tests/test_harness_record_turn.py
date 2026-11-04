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

    def ingester(self, exit_code: int, stderr_text: str = "", stdout_text: str = "") -> None:
        script = self.memory_repo / "ai-memory-ingester"
        stderr_file = self.workspace / "stub-stderr.txt"
        stdout_file = self.workspace / "stub-stdout.txt"
        stderr_file.write_text(stderr_text, encoding="utf-8")
        stdout_file.write_text(stdout_text, encoding="utf-8")
        script.write_text(
            "#!/bin/sh\n"
            f"[ \"$1\" = record-event ] || exit 9\n"
            f"cat > '{self.received}'\n"
            f"cat '{stdout_file}'\n"
            f"cat '{stderr_file}' >&2\n"
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

    def error_log(self) -> Path:
        return self.payload.resolve().with_name(self.payload.name + ".error.log")

    def test_failure_writes_an_error_log_with_the_stderr_and_java_lines(self):
        message = "java.lang.UnsupportedClassVersionError: PrecompiledRunner was compiled by a more recent version\n"
        self.ingester(1, stderr_text=message)
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        log = self.error_log()
        self.assertTrue(log.exists())
        text = log.read_text(encoding="utf-8")
        self.assertIn("exit code: 1", text)
        self.assertIn("UnsupportedClassVersionError", text)
        self.assertIn("JAVA_HOME:", text)
        self.assertIn("java on PATH:", text)
        self.assertIn(f"payload: {self.payload.resolve()}", text)
        self.assertIn("working folder:", text)

    def test_failure_message_names_the_log_and_keeps_the_phrase(self):
        self.ingester(3, stderr_text="boom\n")
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 3)
        self.assertIn("exit 3", result.stderr)
        self.assertIn(f"details in {self.error_log()}", result.stderr)
        self.assertIn("prompt.log not appended", result.stderr)
        self.assertIn("boom", result.stderr)
        self.assertFalse((self.workspace / "prompt.log").exists())
        self.assertTrue(self.payload.exists())

    def test_error_log_does_not_contain_the_payload_text(self):
        self.ingester(1, stderr_text="boom\n")
        self.write_payload(user_text="private user words", assistant_text="private assistant words")
        self.run_script()
        text = self.error_log().read_text(encoding="utf-8")
        self.assertNotIn("private user words", text)
        self.assertNotIn("private assistant words", text)

    def test_stderr_longer_than_64_kb_is_cut_in_the_log(self):
        self.ingester(1, stderr_text="e" * 200000)
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        size = self.error_log().stat().st_size
        self.assertLess(size, 70000)
        self.assertGreater(size, 65000)

    def test_success_removes_a_stale_error_log(self):
        self.ingester(0)
        self.write_payload()
        self.error_log().write_text("old failure\n", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.error_log().exists())
        self.assertFalse(self.payload.exists())

    def test_result_line_on_stdout_still_passes_through(self):
        self.ingester(0, stdout_text="record-event\tid=abc\tsequence=1\n")
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn("record-event\tid=abc\tsequence=1", result.stdout)

    def test_stderr_of_a_successful_write_is_still_shown_and_leaves_no_log(self):
        self.ingester(0, stderr_text="note: something to read\n")
        self.write_payload()
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn("note: something to read", result.stderr)
        self.assertFalse(self.error_log().exists())

    def test_unwritable_log_folder_keeps_the_exit_code_and_the_phrase(self):
        self.ingester(2, stderr_text="boom\n")
        self.write_payload()
        os.chmod(self.payload.parent, 0o555)
        try:
            result = self.run_script()
        finally:
            os.chmod(self.payload.parent, 0o755)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot write", result.stderr)
        self.assertIn("prompt.log not appended", result.stderr)
        self.assertNotIn("details in", result.stderr)


if __name__ == "__main__":
    unittest.main()
