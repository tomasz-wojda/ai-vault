#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import os
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^--- \d{4}-\d{2}-\d{2}T\d{2}:\d{2} ---$")
INCIDENT = re.compile(r"^INCIDENT ([^|]*)\|([^|]*)\|(.*)$")
MODE = re.compile(r"^Mode: (RESEARCH|INNOVATE|PLAN|EXECUTE) +Worklog: \S.*$")
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


def validate_entry(raw: bytes) -> list[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["entry is not valid UTF-8"]
    if not text.strip():
        return ["entry is empty"]
    lines = text.splitlines()
    violations = []
    if not HEADER.match(lines[0]):
        violations.append("line 1 must be '--- YYYY-MM-DDTHH:MM ---'")
    incident = INCIDENT.match(lines[1]) if len(lines) > 1 else None
    if not incident or not all(field.strip() for field in incident.groups()):
        violations.append(
            "line 2 must be 'INCIDENT <key> | <environment> | <service>'"
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
    violations = validate_entry(raw)
    if violations:
        for violation in violations:
            print(f"rejected: {violation}", file=sys.stderr)
        return 2
    written = append_entry(args.log, raw.decode("utf-8"))
    print(f"appended {written} bytes to {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
