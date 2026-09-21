#!/usr/bin/env python3

import json
import re
import shlex
import sys
from pathlib import Path


MUTATION = re.compile(
    r"(?:^|(?:&&|\|\||[;|&])\s*)(?:sudo\s+)?"
    r"git(?:\s+-C\s+(?:\"[^\"]+\"|'[^']+'|\S+))?\s+"
    r"(?:--[^\s]+\s+)*(add|commit|push)\b"
)
GIT_C = re.compile(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)")
CD = re.compile(r"(?:^|[;&|]\s*|&&\s*)cd\s+(\"[^\"]+\"|'[^']+'|[^;&|\s]+)")


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def unquote(value: str) -> str:
    try:
        values = shlex.split(value)
    except ValueError:
        return value.strip("'\"")
    return values[0] if values else ""


def target_paths(command: str, cwd: Path) -> list[Path]:
    paths = [cwd]
    for match in GIT_C.finditer(command):
        candidate = Path(unquote(match.group(1))).expanduser()
        paths.append(candidate if candidate.is_absolute() else cwd / candidate)
    for match in CD.finditer(command):
        candidate = Path(unquote(match.group(1))).expanduser()
        paths.append(candidate if candidate.is_absolute() else cwd / candidate)
    return paths


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("command", "")
    cwd = Path(payload.get("cwd") or ".").resolve()
    vault = Path(__file__).resolve().parents[3]
    mutation = MUTATION.search(command)
    if not mutation:
        print(json.dumps({"permission": "allow"}))
        return 0
    if not any(inside(path, vault) for path in target_paths(command, cwd)):
        print(json.dumps({"permission": "allow"}))
        return 0
    action = mutation.group(1)
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": (
                    f"Agent-issued git {action} is blocked for ai-vault. "
                    "Use the two-command handoff."
                ),
                "agent_message": (
                    "Do not mutate ai-vault Git state. Run read-only checks, "
                    "then render and provide the required commands."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
