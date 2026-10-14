#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticket_sync_common as sync


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sync.require_ids(payload)
    state = sync.load_generation(conversation_id, generation_id)
    if state is None:
        print("{}")
        return 0
    roots = [Path(root) for root in state.get("workspace_roots") or []]
    keys = sync.mentioned_keys(
        payload.get("text") or "",
        sync.active_worklogs(roots),
    )
    state["keys"] = sorted(set(state.get("keys") or []) | keys)
    sync.save_generation(state)
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
