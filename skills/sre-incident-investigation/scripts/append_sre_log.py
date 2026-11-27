#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HEADER = re.compile(r"^--- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}) ---$")
INCIDENT = re.compile(
    r"^INCIDENT ([^|]*)\|([^|]*)\|([^|]*)\| Ticket: ([A-Z][A-Z0-9]+-\d+|none)$"
)
INCIDENT_KEY = re.compile(r"^INCIDENT (\S+) ")
MODE = re.compile(r"^Mode: (RESEARCH|INNOVATE|PLAN|EXECUTE) +Worklog: \S.*$")
STATUS = re.compile(
    r"^Status: (investigating|mitigating|recovered|recurring|monitoring|resolved) +Severity: \S.*$"
)
LABELS = "confirmed|most likely|probable|undetermined"
ROOT_CAUSE = re.compile(
    rf"^ROOT CAUSE: ({LABELS}) — Trigger: ({LABELS}) (direct|correlational|none) — \S.*$"
)
ENTRY_NAME = re.compile(r"^sre-log-(\d{8}T\d{4})\.txt$")
HEADER_FORMAT = "%Y-%m-%dT%H:%M"
STAMP_FORMAT = "%Y%m%dT%H%M"
FUTURE_TOLERANCE = timedelta(minutes=5)
PAST_TOLERANCE = timedelta(minutes=15)
INCIDENTS_DIR = "incidents"
SECTIONS = (
    "SUMMARY:",
    "EVIDENCE:",
    "HYPOTHESES:",
    "ROOT CAUSE:",
    "ACTIONS:",
    "OPEN QUESTIONS:",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one SRE.log entry and append it to SRE.log."
    )
    parser.add_argument("--entry", required=True, type=Path)
    parser.add_argument("--log", default=Path("SRE.log"), type=Path)
    return parser.parse_args(argv)


def read_entry(path: Path) -> bytes:
    return path.read_bytes()


def current_time() -> datetime:
    return datetime.now()


def parse_header_time(line: str) -> datetime | None:
    match = HEADER.match(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), HEADER_FORMAT)
    except ValueError:
        return None


def first_line(lines: list[str], prefix: str) -> int | None:
    return next(
        (number for number, line in enumerate(lines) if line.startswith(prefix)),
        None,
    )


def structure_violations(lines: list[str]) -> list[str]:
    violations = []
    if parse_header_time(lines[0]) is None:
        violations.append("line 1 must be '--- YYYY-MM-DDTHH:MM ---'")
    incident = INCIDENT.match(lines[1]) if len(lines) > 1 else None
    if (
        not incident
        or not all(field.strip() for field in incident.groups())
        or len(incident.group(1).split()) != 1
    ):
        violations.append(
            "line 2 must be 'INCIDENT <key> | <environment> | <service> | "
            "Ticket: <Jira key|none>'"
        )
    if len(lines) < 3 or not MODE.match(lines[2]):
        violations.append(
            "line 3 must be 'Mode: <RESEARCH|INNOVATE|PLAN|EXECUTE>   "
            "Worklog: <path|none>'"
        )
    if any(HEADER.match(line) for line in lines[1:]):
        violations.append("entry contains a second header line")
    position = 0
    for label in SECTIONS:
        index = next(
            (
                number
                for number, line in enumerate(lines[position:], position)
                if line.startswith(label)
            ),
            None,
        )
        if index is None:
            violations.append(f"section '{label}' is missing or out of order")
            continue
        position = index + 1
    return violations


def path_violations(entry: Path, key: str | None, header: datetime | None) -> list[str]:
    resolved = entry.resolve()
    violations = []
    if resolved.parent.parent.name != INCIDENTS_DIR:
        violations.append("entry must be inside incidents/<key>/")
    elif key and resolved.parent.name != key:
        violations.append("entry directory must equal the incident key")
    name = ENTRY_NAME.match(resolved.name)
    if not name or (header and name.group(1) != header.strftime(STAMP_FORMAT)):
        violations.append(
            "entry file name must be sre-log-<YYYYMMDDTHHMM>.txt matching the header"
        )
    return violations


def latest_header(log: Path, key: str) -> datetime | None:
    if not log.is_file():
        return None
    latest = None
    current = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if HEADER.match(line):
            current = parse_header_time(line)
            continue
        match = INCIDENT_KEY.match(line)
        if match and match.group(1) == key and current:
            latest = current if latest is None else max(latest, current)
    return latest


def time_violations(
    header: datetime, key: str | None, log: Path, now: datetime
) -> list[str]:
    violations = []
    if header > now + FUTURE_TOLERANCE:
        violations.append("header time is in the future")
    if header < now - PAST_TOLERANCE:
        violations.append(
            "header time is more than 15 minutes before now; take it from "
            "local `date`, not `date -u`"
        )
    latest = latest_header(log, key) if key else None
    if latest and header < latest:
        violations.append(
            f"header time is earlier than the latest {key} entry "
            f"({latest.strftime(HEADER_FORMAT)})"
        )
    return violations


def key_violations(key: str, ticket: str, log: Path) -> list[str]:
    if ticket == "none" or key == ticket or latest_header(log, key):
        return []
    return [f"a new incident key must equal the ticket {ticket}"]


def status_value(lines: list[str]) -> tuple[str | None, list[str]]:
    index = first_line(lines, "Status:")
    match = STATUS.match(lines[index]) if index is not None else None
    if not match:
        return None, [
            "status line must be 'Status: <investigating|mitigating|recovered|"
            "recurring|monitoring|resolved>   Severity: <value|unassigned>'"
        ]
    return match.group(1), []


def root_cause_violations(lines: list[str], status: str | None) -> list[str]:
    index = first_line(lines, "ROOT CAUSE:")
    if index is None:
        return []
    match = ROOT_CAUSE.match(lines[index])
    if not match:
        return [
            "ROOT CAUSE line must be 'ROOT CAUSE: <label> — Trigger: <label> "
            "<direct|correlational|none> — <causal chain|not established>'"
        ]
    overall, trigger, evidence = match.groups()
    violations = []
    if trigger == "confirmed" and evidence != "direct":
        violations.append("a confirmed trigger requires direct evidence")
    if (trigger == "undetermined") != (evidence == "none"):
        violations.append(
            "an undetermined trigger takes 'none' evidence, and 'none' is used "
            "only with an undetermined trigger"
        )
    if overall == "confirmed" and trigger != "confirmed":
        violations.append("a confirmed root cause requires a confirmed trigger")
    if status in ("monitoring", "resolved") and trigger == "undetermined":
        violations.append(
            f"status '{status}' requires a determined trigger; use 'recovered'"
        )
    return violations


def actions_violations(lines: list[str]) -> list[str]:
    index = first_line(lines, "ACTIONS:")
    if index is None:
        return []
    following = next((line.strip() for line in lines[index + 1:] if line.strip()), "")
    if following == "none":
        return ["ACTIONS 'none' requires a reason: 'none — <reason>'"]
    return []


def validate_entry(raw: bytes, entry: Path, log: Path, now: datetime) -> list[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["entry is not valid UTF-8"]
    if not text.strip():
        return ["entry is empty"]
    lines = text.splitlines()
    header = parse_header_time(lines[0])
    key_match = INCIDENT.match(lines[1]) if len(lines) > 1 else None
    key = key_match.group(1).strip() if key_match else None
    ticket = key_match.group(4) if key_match else None
    violations = structure_violations(lines)
    violations += path_violations(entry, key, header)
    if header:
        violations += time_violations(header, key, log, now)
    if key and ticket:
        violations += key_violations(key, ticket, log)
    status, status_errors = status_value(lines)
    violations += status_errors
    violations += root_cause_violations(lines, status)
    violations += actions_violations(lines)
    return violations


def append_entry(log: Path, text: str) -> int:
    body = text.rstrip("\n") + "\n"
    with open(log, "a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            if os.fstat(handle.fileno()).st_size > 0:
                body = "\n" + body
            handle.write(body)
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return len(body.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        raw = read_entry(args.entry)
    except OSError as error:
        print(f"cannot read entry: {error}", file=sys.stderr)
        return 2
    violations = validate_entry(raw, args.entry, args.log, current_time())
    if violations:
        for violation in violations:
            print(f"rejected: {violation}", file=sys.stderr)
        return 2
    written = append_entry(args.log, raw.decode("utf-8"))
    print(f"appended {written} bytes to {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
