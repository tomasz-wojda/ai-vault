#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def workspace_root(payload: dict, vault: Path) -> Path:
    roots = [Path(item).resolve() for item in payload.get("workspace_roots") or []]
    for root in roots:
        try:
            vault.relative_to(root)
            return root
        except ValueError:
            continue
    raise RuntimeError("ai-vault is not inside a Cursor workspace root")


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("status") != "completed":
        print("{}")
        return 0
    generation_id = payload.get("generation_id")
    if not generation_id:
        raise RuntimeError("generation_id is missing")
    vault = Path(__file__).resolve().parents[3]
    workspace = workspace_root(payload, vault)
    state_path = (
        workspace
        / ".cursor"
        / "hook-state"
        / "ai-vault-handoff"
        / f"{generation_id}.json"
    )
    if not state_path.is_file():
        violations = ["commit handoff validation state is missing"]
    else:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            violations = [] if state.get("valid") else state.get("violations") or []
        except (OSError, json.JSONDecodeError):
            violations = ["commit handoff validation state is corrupt"]
    if not violations:
        state_path.unlink(missing_ok=True)
        print("{}")
        return 0
    details = "; ".join(str(item) for item in violations)
    print(
        json.dumps(
            {
                "followup_message": (
                    "The ai-vault completion handoff is invalid: "
                    f"{details}. Use scripts/commit_handoff.py render against "
                    "repos/ai-vault and paste its two Markdown blocks exactly. "
                    "Do not run git add, git commit, or git push."
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
