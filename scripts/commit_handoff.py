#!/usr/bin/env python3

import argparse
import json
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path


SEMANTIC_TITLE = re.compile(
    r"^(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([a-z0-9._/-]+\))?!?: [^\n]+$"
)
BASH_BLOCK = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)


class HandoffError(ValueError):
    pass


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def changed_paths(repo: Path) -> list[str]:
    tracked = run_git(repo, "diff", "--name-only", "-z", "HEAD", "--")
    untracked = run_git(
        repo,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
    )
    paths = {
        item.decode("utf-8", "surrogateescape")
        for item in (tracked + untracked).split(b"\0")
        if item
    }
    return sorted(paths)


def validate_title(title: str) -> None:
    if len(title) > 70:
        raise HandoffError("semantic title exceeds 70 characters")
    if not SEMANTIC_TITLE.fullmatch(title):
        raise HandoffError("semantic title does not match conventional syntax")


def wrap_description(description: str) -> list[str]:
    if re.search(r"\n[ \t]*\n", description):
        raise HandoffError("description contains an internal blank line")
    paragraph = " ".join(description.split())
    if not paragraph:
        raise HandoffError("description is empty")
    lines = textwrap.wrap(
        paragraph,
        width=70,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if any(len(line) > 70 for line in lines):
        raise HandoffError("description contains an unwrappable token")
    return lines


def double_quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )
    return f'"{escaped}"'


def render_handoff(paths: list[str], title: str, description: str) -> str:
    if not paths:
        raise HandoffError("repository has no changed paths")
    validate_title(title)
    body = "\n".join(wrap_description(description))
    add_command = "git add -- " + " ".join(shlex.quote(path) for path in paths)
    commit_command = (
        "git commit \\\n"
        f"  -m {double_quote(title)} \\\n"
        f"  -m {double_quote(body)}"
    )
    return (
        f"```bash\n{add_command}\n```\n\n"
        f"```bash\n{commit_command}\n```"
    )


def parse_commit_command(command: str) -> tuple[str, str]:
    if "<<" in command:
        raise HandoffError("HEREDOC commit messages are forbidden")
    try:
        tokens = shlex.split(command.replace("\\\n", ""))
    except ValueError as exc:
        raise HandoffError(f"commit command is not valid shell: {exc}") from exc
    if tokens[:2] != ["git", "commit"]:
        raise HandoffError("second command must be git commit")
    messages: list[str] = []
    index = 2
    while index < len(tokens):
        if tokens[index] != "-m" or index + 1 >= len(tokens):
            raise HandoffError("git commit may contain only two -m arguments")
        messages.append(tokens[index + 1])
        index += 2
    if len(messages) != 2:
        raise HandoffError("git commit must contain exactly two -m arguments")
    return messages[0], messages[1]


def parse_add_command(command: str) -> list[str]:
    if "\n" in command:
        raise HandoffError("git add must be one physical command line")
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise HandoffError(f"git add command is not valid shell: {exc}") from exc
    if tokens[:3] != ["git", "add", "--"]:
        raise HandoffError("first command must be git add -- <changed paths>")
    if len(tokens) == 3:
        raise HandoffError("git add command contains no paths")
    return tokens[3:]


def validate_response(response: str, paths: list[str]) -> dict[str, object]:
    violations: list[str] = []
    blocks = BASH_BLOCK.findall(response)
    if len(blocks) != 2:
        violations.append("response must contain exactly two bash blocks")
        return {"valid": False, "violations": violations}
    try:
        add_paths = parse_add_command(blocks[0].strip())
        if sorted(add_paths) != sorted(paths):
            violations.append("git add paths do not match current changed paths")
    except HandoffError as exc:
        violations.append(str(exc))
    try:
        title, body = parse_commit_command(blocks[1].strip())
        validate_title(title)
        if re.search(r"\n[ \t]*\n", body):
            violations.append("commit description contains an internal blank line")
        if not body.strip():
            violations.append("commit description is empty")
        if any(len(line) > 70 for line in body.splitlines()):
            violations.append("commit description exceeds 70 characters per line")
    except HandoffError as exc:
        violations.append(str(exc))
    return {"valid": not violations, "violations": violations}


def command_render(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    print(render_handoff(changed_paths(repo), args.title, args.description))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    response = Path(args.response_file).read_text(encoding="utf-8")
    result = validate_response(response, changed_paths(repo))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["valid"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render")
    render.add_argument("--repo", required=True)
    render.add_argument("--title", required=True)
    render.add_argument("--description", required=True)
    render.set_defaults(handler=command_render)
    validate = subparsers.add_parser("validate-response")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--response-file", required=True)
    validate.set_defaults(handler=command_validate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except HandoffError as exc:
        print(json.dumps({"valid": False, "violations": [str(exc)]}))
        return 2
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", "replace").strip()
        print(json.dumps({"valid": False, "violations": [message]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
