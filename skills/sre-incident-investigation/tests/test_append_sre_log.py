import contextlib
import io
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import append_sre_log

VALID_ENTRY = """--- 2026-11-26T14:30 ---
INCIDENT KD-1234 | prod | checkout-api | Ticket: KD-1234
Mode: RESEARCH   Worklog: worklog/2026-11-26_KD-1234.log

SUMMARY:
Status: investigating   Severity: unassigned
Start (UTC): 2026-11-26T13:10Z   Detected (UTC): 2026-11-26T13:14Z
Impact: 5xx rate 12% on checkout (measured)
EVIDENCE:
1. New Relic — error rate by host — spike on two pods (2026-11-26T13:12Z)
HYPOTHESES:
H1 supported medium — If the pool is exhausted, then requests fail because acquire times out — Test: pool metrics — Result: untested
ROOT CAUSE: undetermined — Trigger: undetermined none — not established
ACTIONS:
none — no action proposed yet
OPEN QUESTIONS:
- Did the 13:05 deploy change pool size?
"""

UNDETERMINED = "ROOT CAUSE: undetermined — Trigger: undetermined none — not established"
HEADER_TIME = re.compile(r"^--- (\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}) ---")


def entry_name(text):
    match = HEADER_TIME.match(text)
    stamp = "{}{}{}T{}{}".format(*match.groups()) if match else "20261126T1430"
    return f"sre-log-{stamp}.txt"


def default_now(text):
    match = HEADER_TIME.match(text)
    if not match:
        return datetime(2026, 11, 26, 14, 31)
    return datetime(*map(int, match.groups())) + timedelta(minutes=1)


class AppendSreLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = self.root / "SRE.log"

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, text, directory=None, name=None, now=None):
        folder = directory or self.root / "incidents" / "KD-1234"
        folder.mkdir(parents=True, exist_ok=True)
        entry = folder / (name or entry_name(text))
        entry.write_text(text, encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        clock = mock.patch.object(
            append_sre_log, "current_time", return_value=now or default_now(text)
        )
        with clock, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
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
        self.assertEqual(self.run_main(second)[0], 0)
        self.assertEqual(self.log.read_text(encoding="utf-8"), VALID_ENTRY + "\n" + second)

    def assert_rejected(self, text, fragment, existing="existing\n", **location):
        self.log.write_text(existing, encoding="utf-8")
        code, stdout, stderr = self.run_main(text, **location)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn(fragment, stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8"), existing)

    def assert_accepted(self, text, existing="", **location):
        self.log.write_text(existing, encoding="utf-8")
        code, _, stderr = self.run_main(text, **location)
        self.assertEqual(code, 0, stderr)

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

    def test_entry_outside_incidents_rejected(self):
        self.assert_rejected(
            VALID_ENTRY, "inside incidents/<key>/", directory=self.root / "tmp" / "KD-1234"
        )

    def test_directory_not_matching_key_rejected(self):
        self.assert_rejected(
            VALID_ENTRY,
            "directory must equal the incident key",
            directory=self.root / "incidents" / "KD-9999",
        )

    def test_file_name_not_matching_header_rejected(self):
        self.assert_rejected(VALID_ENTRY, "file name", name="sre-log-20261126T1431.txt")

    def test_future_header_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace("2026-11-26T14:30", "2099-01-01T00:00"),
            "in the future",
            now=datetime(2026, 11, 26, 14, 31),
        )

    def test_header_earlier_than_same_key_rejected(self):
        existing = VALID_ENTRY.replace("14:30", "15:45")
        self.assert_rejected(
            VALID_ENTRY, "earlier than the latest KD-1234 entry", existing=existing
        )

    def test_header_earlier_than_other_key_accepted(self):
        other = VALID_ENTRY.replace("14:30", "15:45").replace(
            "INCIDENT KD-1234", "INCIDENT KD-9999"
        )
        self.assert_accepted(VALID_ENTRY, existing=other)

    def test_invalid_ticket_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace("Ticket: KD-1234", "Ticket: kd-1234"), "line 2"
        )

    def test_bare_none_actions_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace("none — no action proposed yet", "none"),
            "requires a reason",
        )

    def test_confirmed_root_cause_with_unconfirmed_trigger_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace(
                UNDETERMINED, "ROOT CAUSE: confirmed — Trigger: probable correlational — chain"
            ),
            "confirmed root cause requires a confirmed trigger",
        )

    def test_confirmed_trigger_with_correlational_evidence_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace(
                UNDETERMINED, "ROOT CAUSE: most likely — Trigger: confirmed correlational — chain"
            ),
            "confirmed trigger requires direct evidence",
        )

    def test_undetermined_trigger_with_direct_evidence_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace(
                UNDETERMINED, "ROOT CAUSE: undetermined — Trigger: undetermined direct — chain"
            ),
            "undetermined trigger takes 'none'",
        )

    def test_monitoring_with_undetermined_trigger_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace("Status: investigating", "Status: monitoring"),
            "requires a determined trigger",
        )

    def test_recovered_with_undetermined_trigger_accepted(self):
        self.assert_accepted(VALID_ENTRY.replace("Status: investigating", "Status: recovered"))

    def test_header_older_than_tolerance_rejected(self):
        self.assert_rejected(
            VALID_ENTRY,
            "more than 15 minutes before now",
            now=datetime(2026, 11, 26, 14, 50),
        )

    def test_header_within_tolerance_accepted(self):
        self.assert_accepted(VALID_ENTRY, now=datetime(2026, 11, 26, 14, 40))

    def test_new_key_differing_from_ticket_rejected(self):
        self.assert_rejected(
            VALID_ENTRY.replace("INCIDENT KD-1234", "INCIDENT checkout-api-20261126"),
            "must equal the ticket KD-1234",
            directory=self.root / "incidents" / "checkout-api-20261126",
        )

    def test_existing_slug_key_with_later_ticket_accepted(self):
        slug = VALID_ENTRY.replace("INCIDENT KD-1234", "INCIDENT checkout-api-20261126")
        existing = slug.replace("Ticket: KD-1234", "Ticket: none")
        self.assert_accepted(
            slug.replace("14:30", "15:45"),
            existing=existing,
            directory=self.root / "incidents" / "checkout-api-20261126",
        )

    def test_new_slug_key_without_ticket_accepted(self):
        self.assert_accepted(
            VALID_ENTRY.replace("INCIDENT KD-1234", "INCIDENT checkout-api-20261126").replace(
                "Ticket: KD-1234", "Ticket: none"
            ),
            directory=self.root / "incidents" / "checkout-api-20261126",
        )

    def test_recurring_with_undetermined_trigger_accepted(self):
        self.assert_accepted(VALID_ENTRY.replace("Status: investigating", "Status: recurring"))


if __name__ == "__main__":
    unittest.main()
