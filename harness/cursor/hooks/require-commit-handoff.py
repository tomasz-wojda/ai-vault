#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    engine_path,
    read_state,
    renderer_command,
    require_ids,
    state_path,
)


def followup_for_repo(repo: Path, paths: list[str], details: str) -> str:
    return (
        f"The commit handoff for {repo} is invalid: {details}. Run "
        f"{renderer_command(repo, paths)} and paste its two Markdown blocks "
        f"exactly for that repository. Do not run git add, git commit, or "
        f"git push."
    )


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("status") != "completed":
        print("{}")
        return 0
    conversation_id, generation_id = require_ids(payload)
    path = state_path(conversation_id, generation_id)
    if not path.is_file():
        violations = ["commit handoff validation state is missing"]
        print(
            json.dumps(
                {
                    "followup_message": (
                        "The commit handoff is invalid: commit handoff "
                        "validation state is missing. Ensure the git-handoff "
                        f"baseline hook ran, then use {engine_path()} render "
                        "with --repo and --path for each touched repository. "
                        "Do not run git add, git commit, or git push."
                    )
                }
            )
        )
        return 0
    try:
        state = read_state(path)
    except (OSError, json.JSONDecodeError):
        print(
            json.dumps(
                {
                    "followup_message": (
                        "The commit handoff is invalid: commit handoff "
                        "validation state is corrupt. Retry the turn so the "
                        "baseline hook can recreate state. Do not run git "
                        "add, git commit, or git push."
                    )
                }
            )
        )
        return 0
    if not state.get("validated"):
        print(
            json.dumps(
                {
                    "followup_message": (
                        "The commit handoff is invalid: response validation "
                        "state is missing. Ensure afterAgentResponse capture "
                        "ran before stop. Do not run git add, git commit, or "
                        "git push."
                    )
                }
            )
        )
        return 0
    repo_paths = state.get("repo_paths") or {}
    if not repo_paths:
        path.unlink(missing_ok=True)
        print("{}")
        return 0
    if state.get("valid"):
        path.unlink(missing_ok=True)
        print("{}")
        return 0
    violations = state.get("violations") or []
    details = "; ".join(str(item) for item in violations)
    if len(repo_paths) == 1:
        repo_str, paths = next(iter(repo_paths.items()))
        message = followup_for_repo(Path(repo_str), paths, details)
    else:
        repo_lines = []
        for repo_str in sorted(repo_paths):
            repo = Path(repo_str)
            paths = repo_paths[repo_str]
            repo_lines.append(renderer_command(repo, paths))
        message = (
            f"The commit handoff is invalid for {len(repo_paths)} repositories: "
            f"{details}. Render one handoff per repository using:\n"
            + "\n".join(repo_lines)
            + "\nPaste two Markdown blocks per repository. Do not run git add, "
            "git commit, or git push."
        )
    print(json.dumps({"followup_message": message}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
