#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticket_sync_common as sync


def pending_worklogs(state: dict) -> dict[str, list[str]]:
    roots = [Path(root) for root in state.get("workspace_roots") or []]
    active = sync.active_worklogs(roots)
    edited = set(state.get("edited_keys") or [])
    return {
        key: active[key]
        for key in sorted(set(state.get("keys") or []) - edited)
        if key in active
    }


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sync.require_ids(payload)
    try:
        if payload.get("status") != "completed":
            print("{}")
            return 0
        if int(payload.get("loop_count") or 0) > 0:
            print("{}")
            return 0
        state = sync.load_generation(conversation_id, generation_id)
        if state is None:
            print("{}")
            return 0
        pending = pending_worklogs(state)
        if not pending:
            print("{}")
            return 0
        print(json.dumps({"followup_message": sync.followup_message(pending)}))
        return 0
    finally:
        sync.generation_path(conversation_id, generation_id).unlink(
            missing_ok=True
        )


if __name__ == "__main__":
    sys.exit(main())
