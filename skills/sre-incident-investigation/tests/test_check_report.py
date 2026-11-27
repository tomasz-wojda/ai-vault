import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import check_report

PLAN_READY = """# Incident investigation — KD-1234 checkout errors

## 1. Executive summary
- Report state: PLAN-READY
- Go/No-go: READY — every blocking validation passed
- Status: recurring
- Severity: unassigned

## 2. Architecture and failure path
- Verified components/edges: ingress -> checkout-api

## 3. Timeline (UTC)
| Time | Event / observation | Source | Fact or inference |
|---|---|---|---|
| 13:10 | 5xx rise | New Relic | fact |

## 4. Evidence
| ID | Observation | Source/query/scope | Timestamp | Limitations |
|---|---|---|---|---|
| E1 | pool exhausted | NRQL | 13:12 | none |

## 5. Hypotheses and tests
| Rank | Hypothesis and mechanism | Evidence for | Evidence against / gap | Discriminating test | Result | Status / confidence |
|---:|---|---|---|---|---|---|
| 1 | If the pool is exhausted, requests fail | E1 | none | pool metrics | pool at 100% | confirmed, high |
| 2 | If a worker leaks, memory grows | none | flat memory | stage soak test | Not run | open, low |

## 6. Root-cause assessment
- Root cause (most likely): pool size below peak concurrency
- Trigger (confirmed; direct): 13:05 deploy halved the pool

## 7. Remediation

### 7.1 Options
| ID | Option | Category | Addresses | Advantages | Disadvantages / risk |
|---|---|---|---|---|---|
| O1 | Restore pool size | corrective | H1 | config only | none |

Recommended combination: O1.

### 7.2 Plan
| Priority | Action | Category | Evidence link | Owner | Risk / approval | Success / rollback criteria |
|---|---|---|---|---|---|---|
| 1 | Restore pool size | corrective | E1 | team | low / required | 5xx below 0.1% / revert |

IMPLEMENTATION CHECKLIST:
1. Request approval and MODE: EXECUTE; restore the pool size.

### 7.3 Pre-EXECUTE validation
| ID | Unproven | Ref | Plan step | Test and environment | Owner | Blocking | Status |
|---|---|---|---|---|---|---|---|
| V1 | worker leak | H2 | 1 | soak test, stage | team | yes | passed |

## 8. Recovery verification
- Original impact signals: 5xx

## 9. Open questions and next actions
- [ ] none
"""

RESEARCH_ONLY = (
    PLAN_READY.replace("- Report state: PLAN-READY", "- Report state: RESEARCH")
    .replace("- Go/No-go: READY — every blocking validation passed", "- Go/No-go: NOT READY — research")
    .split("## 7. Remediation")[0]
    + "## 7. Remediation\n\n## 8. Recovery verification\n\n## 9. Open questions and next actions\n"
)


class CheckReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.report = Path(self.temp.name) / "report.md"

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, text):
        self.report.write_text(text, encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = check_report.main(["--report", str(self.report)])
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_valid(self, text, state):
        code, stdout, stderr = self.run_main(text)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, f"report ok: {state}\n")

    def assert_invalid(self, text, fragment):
        code, stdout, stderr = self.run_main(text)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn(fragment, stderr)

    def test_plan_ready_report_valid(self):
        self.assert_valid(PLAN_READY, "PLAN-READY")

    def test_research_report_valid(self):
        self.assert_valid(RESEARCH_ONLY, "RESEARCH")

    def test_missing_report_state_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("- Report state: PLAN-READY\n", ""), "Report state"
        )

    def test_state_and_go_mismatch_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("Go/No-go: READY —", "Go/No-go: NOT READY —"),
            "report state PLAN-READY requires go/no-go READY",
        )

    def test_missing_heading_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("## 8. Recovery verification", "## 8. Residual risk"),
            "'## 8. Recovery verification' is missing",
        )

    def test_innovate_without_option_rows_invalid(self):
        innovate = (
            RESEARCH_ONLY.replace("Report state: RESEARCH", "Report state: INNOVATE")
            .replace("## 7. Remediation\n", "## 7. Remediation\n\n### 7.1 Options\nnone yet\n")
        )
        self.assert_invalid(innovate, "7.1 Options needs at least one option row")

    def test_plan_ready_without_checklist_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("IMPLEMENTATION CHECKLIST:\n", ""),
            "7.2 Plan needs 'IMPLEMENTATION CHECKLIST:'",
        )

    def test_untested_hypothesis_missing_from_validation_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("| worker leak | H2 |", "| worker leak | precondition |"),
            "untested hypothesis H2 must be listed",
        )

    def test_plan_ready_with_pending_blocking_row_invalid(self):
        self.assert_invalid(
            PLAN_READY.replace("| yes | passed |", "| yes | pending |"),
            "PLAN-READY allows no pending blocking validation",
        )

    def test_conditions_without_pending_blocking_row_invalid(self):
        conditions = PLAN_READY.replace(
            "Report state: PLAN-READY", "Report state: PLAN-READY-WITH-CONDITIONS"
        ).replace("Go/No-go: READY —", "Go/No-go: READY WITH CONDITIONS —")
        self.assert_invalid(
            conditions,
            "PLAN-READY-WITH-CONDITIONS needs at least one pending blocking validation",
        )

    def test_validation_none_with_reason_valid(self):
        tested = PLAN_READY.replace("| Not run | open, low |", "| flat after 24 h | rejected, medium |")
        table = tested.split("### 7.3 Pre-EXECUTE validation\n")[1].split("\n## 8.")[0]
        self.assert_valid(
            tested.replace(table, "none — every hypothesis was tested\n"), "PLAN-READY"
        )

    def test_invalid_blocking_and_status_values_invalid(self):
        code, _, stderr = self.run_main(PLAN_READY.replace("| yes | passed |", "| maybe | done |"))
        self.assertEqual(code, 2)
        self.assertIn("Blocking must be yes or no", stderr)
        self.assertIn("Status must be pending|passed|failed|waived", stderr)


if __name__ == "__main__":
    unittest.main()
