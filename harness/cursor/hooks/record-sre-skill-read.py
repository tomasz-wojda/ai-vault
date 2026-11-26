#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sre_log_common as sre

PATH_KEYS = ("path", "file_path", "target_file")


def read_path(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sre.require_ids(payload)
    state = sre.load_generation(conversation_id, generation_id)
    if state is None:
        print("{}")
        return 0
    if sre.is_skill_path(read_path(payload)):
        state["invoked"] = True
        sre.save_generation(state)
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
