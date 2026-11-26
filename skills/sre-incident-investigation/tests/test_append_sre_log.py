import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import append_sre_log

VALID_ENTRY = """--- 2026-11-26T14:30 ---
INCIDENT KD-1234 | prod | checkout-api
Mode: RESEARCH   Worklog: worklog/2026-11-26_KD-1234.log

SUMMARY:
Status: investigating   Severity: unassigned
Start (UTC): 2026-11-26T13:10Z   Detected (UTC): 2026-11-26T13:14Z
Impact: 5xx rate 12% on checkout (measured)
EVIDENCE:
1. New Relic — error rate by host — spike on two pods (2026-11-26T13:12Z)
HYPOTHESES:
H1 supported medium — If the pool is exhausted, then requests fail because acquire times out — Test: pool metrics — Result: untested
ROOT CAUSE: undetermined — not established
ACTIONS:
none
OPEN QUESTIONS:
- Did the 13:05 deploy change pool size?
"""


class AppendSreLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = self.root / "SRE.log"

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, text, name="entry.txt"):
        entry = self.root / name
        entry.write_text(text, encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = append_sre_log.main(["--entry", str(entry), "--log", str(self.log)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_entry_creates_log(self):
        code, stdout, stderr = self.run_main(VALID_ENTRY)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8"), VALID_ENTRY)
        self.assertIn(f"appended {len(VALID_ENTRY.encode('utf-8'))} bytes to {self.log}", stdout)

    def test_second_append_keeps_first_entry(self):
        second = VALID_ENTRY.replace("14:30", "15:45")
        self.assertEqual(self.run_main(VALID_ENTRY)[0], 0)
        self.assertEqual(self.run_main(second, "second.txt")[0], 0)
        self.assertEqual(self.log.read_text(encoding="utf-8"), VALID_ENTRY + "\n" + second)

    def assert_rejected(self, text, fragment):
        self.log.write_text("existing\n", encoding="utf-8")
        code, stdout, stderr = self.run_main(text)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn(fragment, stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8"), "existing\n")

    def test_missing_header_rejected(self):
        self.assert_rejected(VALID_ENTRY.split("\n", 1)[1], "line 1")

    def test_missing_section_rejected(self):
        self.assert_rejected(VALID_ENTRY.replace("ROOT CAUSE:", "CAUSE:"), "'ROOT CAUSE:'")

    def test_invalid_mode_rejected(self):
        self.assert_rejected(VALID_ENTRY.replace("Mode: RESEARCH", "Mode: DEBUG"), "line 3")

    def test_second_header_rejected(self):
        self.assert_rejected(VALID_ENTRY + "--- 2026-11-26T16:00 ---\n", "second header")

    def test_empty_entry_rejected(self):
        self.assert_rejected("  \n", "entry is empty")


if __name__ == "__main__":
    unittest.main()
