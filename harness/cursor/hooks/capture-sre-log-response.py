#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sre_log_common as sre


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sre.require_ids(payload)
    state = sre.load_generation(conversation_id, generation_id)
    if state is None:
        print("{}")
        return 0
    if sre.WAIVER in (payload.get("text") or ""):
        state["waived"] = True
        sre.save_generation(state)
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
