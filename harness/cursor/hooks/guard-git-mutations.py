#!/usr/bin/env python3

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


MUTATION = re.compile(
    r"(?:^|(?:&&|\|\||[;|&])\s*)(?:sudo\s+)?"
    r"git(?:\s+-C\s+(?:\"[^\"]+\"|'[^']+'|\S+))?\s+"
    r"(?:--[^\s]+\s+)*(add|commit|push)\b"
)
GIT_C = re.compile(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)")
CD = re.compile(r"(?:^|[;&|]\s*|&&\s*)cd\s+(\"[^\"]+\"|'[^']+'|[^;&|\s]+)")


def unquote(value: str) -> str:
    try:
        values = shlex.split(value)
    except ValueError:
        return value.strip("'\"")
    return values[0] if values else ""


def git_root(path: Path) -> Path | None:
    try:
        output = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        return None
    return Path(output.stdout.decode("utf-8").strip()).resolve()


def target_paths(command: str, cwd: Path) -> list[Path]:
    paths = [cwd]
    for match in GIT_C.finditer(command):
        candidate = Path(unquote(match.group(1))).expanduser()
        paths.append(candidate if candidate.is_absolute() else cwd / candidate)
    for match in CD.finditer(command):
        candidate = Path(unquote(match.group(1))).expanduser()
        paths.append(candidate if candidate.is_absolute() else cwd / candidate)
    return paths


def resolves_to_git_repo(path: Path) -> bool:
    return git_root(path) is not None


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("command", "")
    cwd = Path(payload.get("cwd") or ".").resolve()
    mutation = MUTATION.search(command)
    if not mutation:
        print(json.dumps({"permission": "allow"}))
        return 0
    if not any(resolves_to_git_repo(path) for path in target_paths(command, cwd)):
        print(json.dumps({"permission": "allow"}))
        return 0
    action = mutation.group(1)
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": (
                    f"Agent-issued git {action} is blocked for Git repositories. "
                    "Use the two-command handoff."
                ),
                "agent_message": (
                    "Do not mutate Git state directly. Run read-only checks, "
                    "then render and provide the required commands."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
