#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sre_log_common as sre


def needs_entry(state: dict | None) -> bool:
    if state is None:
        return False
    if not state.get("invoked") or state.get("waived"):
        return False
    return not sre.log_grew(state)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sre.require_ids(payload)
    try:
        if payload.get("status") != "completed":
            print("{}")
            return 0
        if int(payload.get("loop_count") or 0) > 0:
            print("{}")
            return 0
        if not needs_entry(sre.load_generation(conversation_id, generation_id)):
            print("{}")
            return 0
        print(json.dumps({"followup_message": sre.followup_message()}))
        return 0
    finally:
        sre.generation_path(conversation_id, generation_id).unlink(
            missing_ok=True
        )


if __name__ == "__main__":
    sys.exit(main())
