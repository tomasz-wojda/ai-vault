#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    correlation_is_fresh,
    pending_stop_path,
    read_state,
    renderer_command,
    require_ids,
    response_signature,
    state_path,
)


def followup_for_repo(repo: Path, paths: list[str], details: str) -> str:
    return (
        f"The commit handoff for {repo} is invalid: {details}. Run "
        f"{renderer_command(repo, paths)} and paste its two Markdown blocks "
        f"exactly for that repository. Do not run git add, git commit, or "
        f"git push."
    )


def load_validation_state(
    payload: dict,
    conversation_id: str,
    generation_id: str,
) -> tuple[Path | None, dict | None, str | None]:
    exact_path = state_path(conversation_id, generation_id)
    if exact_path.is_file():
        try:
            return exact_path, read_state(exact_path), None
        except (OSError, json.JSONDecodeError):
            return None, None, "commit handoff validation state is corrupt"
    pending_path = pending_stop_path(conversation_id)
    if not pending_path.is_file():
        return None, None, "commit handoff validation state is missing"
    try:
        metadata = read_state(pending_path)
    except (OSError, json.JSONDecodeError):
        return None, None, "response correlation state is corrupt"
    if metadata.get("conversation_id") != conversation_id:
        return None, None, "response correlation conversation is mismatched"
    captured_generation = metadata.get("generation_id")
    if not isinstance(captured_generation, str) or not captured_generation:
        return None, None, "response correlation generation is missing"
    if not correlation_is_fresh(metadata):
        return None, None, "response correlation state is stale"
    signature = response_signature(payload)
    captured_signature = metadata.get("response_signature")
    if (
        signature is not None
        and captured_signature is not None
        and captured_signature != signature
    ):
        return None, None, "response correlation signature is mismatched"
    captured_path = state_path(conversation_id, captured_generation)
    if not captured_path.is_file():
        return None, None, "correlated validation state is missing"
    try:
        state = read_state(captured_path)
    except (OSError, json.JSONDecodeError):
        return None, None, "correlated validation state is corrupt"
    if (
        state.get("conversation_id") != conversation_id
        or state.get("generation_id") != captured_generation
    ):
        return None, None, "correlated validation identity is mismatched"
    if state.get("captured_at_ns") != metadata.get("captured_at_ns"):
        return None, None, "correlated validation timestamp is mismatched"
    if state.get("response_signature") != captured_signature:
        return None, None, "correlated validation signature is mismatched"
    if not state.get("validated"):
        return None, None, "correlated response validation state is missing"
    return captured_path, state, None


def diagnose(details: str) -> None:
    print(f"git-handoff hook diagnostic: {details}", file=sys.stderr)


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("status") != "completed":
        print("{}")
        return 0
    conversation_id, generation_id = require_ids(payload)
    pending_path = pending_stop_path(conversation_id)
    try:
        path, state, failure = load_validation_state(
            payload,
            conversation_id,
            generation_id,
        )
        if failure:
            diagnose(failure)
            print("{}")
            return 0
        if not state.get("validated"):
            diagnose("response validation state is missing")
            print("{}")
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
                f"The commit handoff is invalid for {len(repo_paths)} "
                f"repositories: {details}. Render one handoff per repository "
                "using:\n"
                + "\n".join(repo_lines)
                + "\nPaste two Markdown blocks per repository. Do not run git "
                "add, git commit, or git push."
            )
        print(json.dumps({"followup_message": message}))
        return 0
    finally:
        pending_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
