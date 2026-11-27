#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADINGS = (
    "## 1. Executive summary",
    "## 2. Architecture and failure path",
    "## 3. Timeline (UTC)",
    "## 4. Evidence",
    "## 5. Hypotheses and tests",
    "## 6. Root-cause assessment",
    "## 7. Remediation",
    "## 8. Recovery verification",
    "## 9. Open questions and next actions",
)
STATES = (
    "RESEARCH",
    "INNOVATE",
    "PLAN-READY",
    "PLAN-READY-WITH-CONDITIONS",
    "EXECUTING",
    "VERIFIED",
)
GO_FOR_STATE = {
    "RESEARCH": ("NOT READY",),
    "INNOVATE": ("NOT READY",),
    "PLAN-READY": ("READY",),
    "PLAN-READY-WITH-CONDITIONS": ("READY WITH CONDITIONS",),
    "EXECUTING": ("READY", "READY WITH CONDITIONS"),
    "VERIFIED": ("READY", "READY WITH CONDITIONS"),
}
BLOCKING_RULES = {
    "PLAN-READY": ({"pending", "failed"}, None),
    "PLAN-READY-WITH-CONDITIONS": ({"failed"}, "pending"),
    "EXECUTING": ({"failed"}, None),
    "VERIFIED": ({"pending", "failed"}, None),
}
STATE = re.compile(r"^- Report state: (\S+)$")
GO = re.compile(r"^- Go/No-go: (READY WITH CONDITIONS|NOT READY|READY) — \S.*$")
LABELS = "confirmed|most likely|probable|undetermined"
ROOT_CAUSE = re.compile(rf"^- Root cause \(({LABELS})\): \S")
TRIGGER = re.compile(rf"^- Trigger \(({LABELS}); (direct|correlational|none)\): \S")
OPTIONS = "### 7.1 Options"
PLAN = "### 7.2 Plan"
VALIDATION = "### 7.3 Pre-EXECUTE validation"
VALIDATION_HEADER = (
    "ID",
    "Unproven",
    "Ref",
    "Plan step",
    "Test and environment",
    "Owner",
    "Blocking",
    "Status",
)
BLOCKING_VALUES = ("yes", "no")
STATUS_VALUES = ("pending", "passed", "failed", "waived")
CHECKLIST = "IMPLEMENTATION CHECKLIST:"
CHECKLIST_ITEM = re.compile(r"^\d+\. \S")
NONE_LINE = re.compile(r"^none — \S")
UNTESTED = re.compile(r"^(not run|untested)", re.IGNORECASE)
HYPOTHESIS_REF = re.compile(r"\bH\d+\b")
SEPARATOR = re.compile(r"^:?-+:?$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
HEADING = re.compile(r"^(#+) ")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check an incident report against its declared report state."
    )
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(argv)


def read_report(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section_text(lines: list[str], heading: str) -> list[str] | None:
    if heading not in lines:
        return None
    level = len(heading.split(" ", 1)[0])
    start = lines.index(heading) + 1
    body = []
    for line in lines[start:]:
        match = HEADING.match(line)
        if match and len(match.group(1)) <= level:
            break
        body.append(line)
    return body


def table_rows(text: list[str]) -> list[list[str]]:
    rows = []
    for line in text:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        inner = stripped[1:-1] if stripped.endswith("|") else stripped[1:]
        cells = [cell.strip() for cell in CELL_SPLIT.split(inner)]
        if all(SEPARATOR.match(cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def state_violations(lines: list[str]) -> tuple[str | None, list[str]]:
    summary = section_text(lines, HEADINGS[0]) or []
    state_match = next(filter(None, map(STATE.match, summary)), None)
    go_match = next(filter(None, map(GO.match, summary)), None)
    violations = []
    state = state_match.group(1) if state_match else None
    if state not in STATES:
        violations.append(
            f"section 1 must contain '- Report state: <{'|'.join(STATES)}>'"
        )
        state = None
    if not go_match:
        violations.append(
            "section 1 must contain '- Go/No-go: <READY|READY WITH CONDITIONS|"
            "NOT READY> — <reason>'"
        )
    elif state and go_match.group(1) not in GO_FOR_STATE[state]:
        allowed = " or ".join(GO_FOR_STATE[state])
        violations.append(f"report state {state} requires go/no-go {allowed}")
    return state, violations


def heading_violations(lines: list[str]) -> list[str]:
    violations = []
    position = 0
    for heading in HEADINGS:
        index = next(
            (number for number, line in enumerate(lines[position:], position) if line == heading),
            None,
        )
        if index is None:
            violations.append(f"heading '{heading}' is missing or out of order")
            continue
        position = index + 1
    return violations


def root_cause_violations(lines: list[str]) -> list[str]:
    assessment = section_text(lines, HEADINGS[5])
    if assessment is None:
        return []
    violations = []
    if not any(ROOT_CAUSE.match(line) for line in assessment):
        violations.append(
            f"section 6 must contain '- Root cause (<{LABELS}>): <text>'"
        )
    if not any(TRIGGER.match(line) for line in assessment):
        violations.append(
            f"section 6 must contain '- Trigger (<{LABELS}>; "
            "<direct|correlational|none>): <text>'"
        )
    return violations


def options_violations(lines: list[str], state: str) -> list[str]:
    if state not in STATES[1:]:
        return []
    options = section_text(lines, OPTIONS)
    if options is None:
        return [f"section '{OPTIONS}' is required from INNOVATE on"]
    if len(table_rows(options)) < 2:
        return ["7.1 Options needs at least one option row"]
    return []


def plan_violations(lines: list[str], state: str) -> list[str]:
    if state not in STATES[2:]:
        return []
    plan = section_text(lines, PLAN)
    if plan is None:
        return [f"section '{PLAN}' is required from PLAN-READY on"]
    if CHECKLIST not in plan or not any(
        CHECKLIST_ITEM.match(line) for line in plan[plan.index(CHECKLIST) + 1:]
    ):
        return [f"7.2 Plan needs '{CHECKLIST}' with at least one numbered step"]
    return []


def validation_rows(lines: list[str]) -> tuple[list[list[str]] | None, list[str]]:
    validation = section_text(lines, VALIDATION)
    if validation is None:
        return None, [f"section '{VALIDATION}' is required from PLAN-READY on"]
    table = table_rows(validation)
    if not table:
        if any(NONE_LINE.match(line.strip()) for line in validation):
            return [], []
        return None, ["7.3 needs the validation table or 'none — <reason>'"]
    if tuple(table[0]) != VALIDATION_HEADER:
        return None, [f"7.3 header must be '| {' | '.join(VALIDATION_HEADER)} |'"]
    violations = [
        f"7.3 row '{row[0]}' must have {len(VALIDATION_HEADER)} cells"
        for row in table[1:]
        if len(row) != len(VALIDATION_HEADER)
    ]
    rows = [row for row in table[1:] if len(row) == len(VALIDATION_HEADER)]
    return rows, violations


def untested_hypotheses(lines: list[str]) -> list[str]:
    table = table_rows(section_text(lines, HEADINGS[4]) or [])
    if not table:
        return []
    header = table[0]
    result = header.index("Result") if "Result" in header else 5
    return [
        f"H{row[0]}"
        for row in table[1:]
        if len(row) > result and row[0].isdigit() and UNTESTED.match(row[result])
    ]


def validation_violations(
    rows: list[list[str]], state: str, untested: list[str]
) -> list[str]:
    violations = []
    blocking_statuses = []
    for row in rows:
        blocking, status = row[6].lower(), row[7].lower()
        if blocking not in BLOCKING_VALUES:
            violations.append(f"7.3 row '{row[0]}' Blocking must be yes or no")
        if status not in STATUS_VALUES:
            violations.append(
                f"7.3 row '{row[0]}' Status must be {'|'.join(STATUS_VALUES)}"
            )
        if blocking == "yes":
            blocking_statuses.append(status)
    referenced = {ref for row in rows for ref in HYPOTHESIS_REF.findall(row[2])}
    violations += [
        f"untested hypothesis {ref} must be listed in the 7.3 Ref column"
        for ref in untested
        if ref not in referenced
    ]
    forbidden, required = BLOCKING_RULES.get(state, (set(), None))
    present = forbidden.intersection(blocking_statuses)
    if present:
        violations.append(
            f"{state} allows no {' or '.join(sorted(present))} blocking validation"
        )
    if required and required not in blocking_statuses:
        violations.append(f"{state} needs at least one {required} blocking validation")
    return violations


def validate_report(text: str) -> tuple[str | None, list[str]]:
    if not text.strip():
        return None, ["report is empty"]
    lines = text.splitlines()
    state, violations = state_violations(lines)
    violations += heading_violations(lines)
    violations += root_cause_violations(lines)
    if state:
        violations += options_violations(lines, state)
        violations += plan_violations(lines, state)
    if state in STATES[2:]:
        rows, row_errors = validation_rows(lines)
        violations += row_errors
        if rows is not None:
            violations += validation_violations(rows, state, untested_hypotheses(lines))
    return state, violations


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        text = read_report(args.report)
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read report: {error}", file=sys.stderr)
        return 2
    state, violations = validate_report(text)
    if violations:
        for violation in violations:
            print(f"invalid: {violation}", file=sys.stderr)
        return 2
    print(f"report ok: {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
