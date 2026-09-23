#!/usr/bin/env python3

import argparse
import json
import os
import re
import shlex
import stat
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


def is_git_repo(path: Path) -> bool:
    return git_root(path) is not None


def normalize_relative_path(repo: Path, path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(repo.resolve())
        except ValueError as exc:
            raise HandoffError(f"path escapes repository: {path}") from exc
    else:
        candidate = Path(os.path.normpath(path))
        if candidate.parts and candidate.parts[0] == "..":
            raise HandoffError(f"path escapes repository: {path}")
    normalized = candidate.as_posix()
    if normalized in (".", ""):
        raise HandoffError("repository path cannot be empty")
    return normalized


def validate_paths(repo: Path, paths: list[str]) -> list[str]:
    if not paths:
        raise HandoffError("repository has no changed paths")
    normalized = [normalize_relative_path(repo, path) for path in paths]
    current = set(changed_paths(repo))
    missing = sorted(set(normalized) - current)
    if missing:
        raise HandoffError(
            "paths are not current changed paths: " + ", ".join(missing)
        )
    return sorted(set(normalized))


def has_commits(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def changed_paths(repo: Path) -> list[str]:
    if has_commits(repo):
        tracked = run_git(repo, "diff", "--name-only", "-z", "HEAD", "--")
    else:
        tracked = b""
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


def path_git_code(repo: Path, rel_path: str) -> str:
    output = run_git(
        repo,
        "status",
        "--porcelain=v1",
        "--",
        rel_path,
    ).decode("utf-8", "surrogateescape")
    if not output:
        return ""
    return output[:2]


def path_fingerprint(repo: Path, rel_path: str) -> tuple[object, ...]:
    code = path_git_code(repo, rel_path)
    full = repo / rel_path
    if not full.exists():
        return ("absent", code)
    try:
        info = full.lstat()
    except OSError:
        return ("missing", code)
    return (
        "present",
        code,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        stat.S_ISDIR(info.st_mode),
    )


def repository_snapshot(repo: Path) -> dict[str, tuple[object, ...]]:
    return {path: path_fingerprint(repo, path) for path in changed_paths(repo)}


def snapshot_delta(
    before: dict[str, tuple[object, ...]],
    after: dict[str, tuple[object, ...]],
) -> list[str]:
    keys = set(before) | set(after)
    return sorted(key for key in keys if before.get(key) != after.get(key))


def repository_delta_paths(
    repo: Path,
    baseline: dict[str, tuple[object, ...]],
    current: dict[str, tuple[object, ...]] | None = None,
) -> list[str]:
    current = current if current is not None else repository_snapshot(repo)
    delta = snapshot_delta(baseline, current)
    changed = set(changed_paths(repo))
    return sorted(path for path in delta if path in changed)


def discover_git_repos(roots: list[Path]) -> list[Path]:
    discovered: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if not resolved.is_dir():
            continue
        for current, directory_names, file_names in os.walk(resolved):
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not name.startswith(".")
                and name not in {
                    ".git",
                    ".hg",
                    ".svn",
                    ".cache",
                    ".tox",
                    ".venv",
                    "__pycache__",
                    "build",
                    "dist",
                    "node_modules",
                    "target",
                    "venv",
                }
            )
            current_path = Path(current)
            if current_path == resolved or ".git" in file_names:
                repo = git_root(current_path)
                if repo is not None:
                    discovered.add(repo)
            elif (current_path / ".git").is_dir():
                repo = git_root(current_path)
                if repo is not None:
                    discovered.add(repo)
    return sorted(discovered)


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


def render_handoff(
    paths: list[str],
    title: str,
    description: str,
    repo: Path | None = None,
) -> str:
    if not paths:
        raise HandoffError("repository has no changed paths")
    validate_title(title)
    body = "\n".join(wrap_description(description))
    if repo is None:
        add_command = "git add -- " + " ".join(shlex.quote(path) for path in paths)
        commit_command = (
            "git commit \\\n"
            f"  -m {double_quote(title)} \\\n"
            f"  -m {double_quote(body)}"
        )
    else:
        repo_abs = shlex.quote(str(repo.resolve()))
        add_command = (
            f"git -C {repo_abs} add -- "
            + " ".join(shlex.quote(path) for path in paths)
        )
        commit_command = (
            f"git -C {repo_abs} commit \\\n"
            f"  -m {double_quote(title)} \\\n"
            f"  -m {double_quote(body)}"
        )
    return (
        f"```bash\n{add_command}\n```\n\n"
        f"```bash\n{commit_command}\n```"
    )


def render_multi_repo_handoff(
    repos: dict[str, list[str]],
    title: str,
    description: str,
) -> str:
    if not repos:
        raise HandoffError("no repositories require a handoff")
    blocks: list[str] = []
    for repo_path in sorted(repos):
        blocks.append(
            render_handoff(
                repos[repo_path],
                title,
                description,
                repo=Path(repo_path),
            )
        )
    return "\n\n".join(blocks)


def parse_commit_command_details(
    command: str,
) -> tuple[str | None, str, str]:
    if "<<" in command:
        raise HandoffError("HEREDOC commit messages are forbidden")
    try:
        tokens = shlex.split(command.replace("\\\n", ""))
    except ValueError as exc:
        raise HandoffError(f"commit command is not valid shell: {exc}") from exc
    if len(tokens) >= 5 and tokens[0] == "git" and tokens[1] == "-C":
        if tokens[3] != "commit":
            raise HandoffError("second command must be git commit")
        repo_arg = tokens[2]
        cursor = 4
    elif tokens[:2] == ["git", "commit"]:
        repo_arg = None
        cursor = 2
    else:
        raise HandoffError("second command must be git commit")
    messages: list[str] = []
    while cursor < len(tokens):
        if tokens[cursor] != "-m" or cursor + 1 >= len(tokens):
            raise HandoffError("git commit may contain only two -m arguments")
        messages.append(tokens[cursor + 1])
        cursor += 2
    if len(messages) != 2:
        raise HandoffError("git commit must contain exactly two -m arguments")
    return repo_arg, messages[0], messages[1]


def parse_commit_command(command: str) -> tuple[str, str]:
    _, title, body = parse_commit_command_details(command)
    return title, body


def parse_add_command(command: str) -> tuple[str | None, list[str]]:
    if "\n" in command:
        raise HandoffError("git add must be one physical command line")
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise HandoffError(f"git add command is not valid shell: {exc}") from exc
    if len(tokens) >= 5 and tokens[0] == "git" and tokens[1] == "-C":
        if tokens[3:5] != ["add", "--"]:
            raise HandoffError("first command must be git add -- <changed paths>")
        if len(tokens) == 5:
            raise HandoffError("git add command contains no paths")
        return tokens[2], tokens[5:]
    if tokens[:3] != ["git", "add", "--"]:
        raise HandoffError("first command must be git add -- <changed paths>")
    if len(tokens) == 3:
        raise HandoffError("git add command contains no paths")
    return None, tokens[3:]


def validate_response(response: str, paths: list[str]) -> dict[str, object]:
    return validate_response_multi(response, {None: paths})


def validate_response_multi(
    response: str,
    repos_paths: dict[str | None, list[str]],
) -> dict[str, object]:
    violations: list[str] = []
    blocks = BASH_BLOCK.findall(response)
    expected_pairs = sum(1 for paths in repos_paths.values() if paths)
    if expected_pairs == 0:
        if blocks:
            violations.append(
                "response must not contain handoff commands when no paths changed"
            )
        return {"valid": not violations, "violations": violations}
    if len(blocks) != expected_pairs * 2:
        violations.append(
            "response must contain exactly two bash blocks per repository"
        )
        return {"valid": False, "violations": violations}
    expected = {
        None if repo is None else str(Path(repo).resolve()): sorted(paths)
        for repo, paths in repos_paths.items()
        if paths
    }
    seen: set[str | None] = set()
    for block_index in range(0, len(blocks), 2):
        add_block = blocks[block_index].strip()
        commit_block = blocks[block_index + 1].strip()
        try:
            repo_arg, add_paths = parse_add_command(add_block)
            commit_repo, title, body = parse_commit_command_details(commit_block)
            normalized_repo = (
                None if repo_arg is None else str(Path(repo_arg).resolve())
            )
            normalized_commit_repo = (
                None if commit_repo is None else str(Path(commit_repo).resolve())
            )
            if normalized_repo != normalized_commit_repo:
                violations.append(
                    "git add and git commit must target the same repository"
                )
            if normalized_repo not in expected:
                violations.append(
                    f"unexpected handoff repository: {normalized_repo}"
                )
            elif normalized_repo in seen:
                violations.append(
                    f"duplicate handoff repository: {normalized_repo}"
                )
            elif sorted(add_paths) != expected[normalized_repo]:
                violations.append(
                    "git add paths do not match current changed paths"
                )
            seen.add(normalized_repo)
            validate_title(title)
            if re.search(r"\n[ \t]*\n", body):
                violations.append("commit description contains an internal blank line")
            if not body.strip():
                violations.append("commit description is empty")
            if any(len(line) > 70 for line in body.splitlines()):
                violations.append("commit description exceeds 70 characters per line")
        except HandoffError as exc:
            violations.append(str(exc))
    missing = sorted(
        (repo for repo in expected if repo not in seen),
        key=lambda item: "" if item is None else item,
    )
    if missing:
        violations.append(
            "missing handoff repositories: "
            + ", ".join("<legacy>" if repo is None else repo for repo in missing)
        )
    return {"valid": not violations, "violations": violations}


def command_render(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    if args.path:
        paths = validate_paths(repo, args.path)
    else:
        paths = changed_paths(repo)
        if not paths:
            raise HandoffError("repository has no changed paths")
    print(render_handoff(paths, args.title, args.description, repo=repo))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    response = Path(args.response_file).read_text(encoding="utf-8")
    if args.path:
        paths = validate_paths(repo, args.path)
    else:
        paths = changed_paths(repo)
    result = validate_response_multi(response, {str(repo.resolve()): paths})
    print(json.dumps(result, sort_keys=True))
    return 0 if result["valid"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render")
    render.add_argument("--repo", required=True)
    render.add_argument("--title", required=True)
    render.add_argument("--description", required=True)
    render.add_argument("--path", action="append", default=[])
    render.set_defaults(handler=command_render)
    validate = subparsers.add_parser("validate-response")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--response-file", required=True)
    validate.add_argument("--path", action="append", default=[])
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
