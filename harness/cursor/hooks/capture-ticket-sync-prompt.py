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
    roots = sync.workspace_roots(payload)
    sync.clear_conversation(conversation_id)
    prompt = payload.get("prompt") or ""
    keys = sync.mentioned_keys(prompt, sync.active_worklogs(roots))
    if not sync.is_sync_followup(prompt):
        sync.bind_keys(conversation_id, keys)
    sync.save_generation(
        {
            "conversation_id": conversation_id,
            "generation_id": generation_id,
            "workspace_roots": [str(root) for root in roots],
            "keys": sorted(keys),
            "edited_keys": [],
        }
    )
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
