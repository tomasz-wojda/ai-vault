#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticket_sync_common as sync


def edited_worklog_key(file_path: str, roots: list[Path]) -> str | None:
    path = Path(file_path).resolve()
    for root in roots:
        if path.parent == (root / "worklog").resolve():
            return sync.worklog_key(path.name)
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sync.require_ids(payload)
    state = sync.load_generation(conversation_id, generation_id)
    if state is None:
        print("{}")
        return 0
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        print("{}")
        return 0
    roots = [Path(root) for root in state.get("workspace_roots") or []]
    key = edited_worklog_key(file_path, roots)
    if key is None:
        print("{}")
        return 0
    state["keys"] = sorted(set(state.get("keys") or []) | {key})
    state["edited_keys"] = sorted(set(state.get("edited_keys") or []) | {key})
    sync.save_generation(state)
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
