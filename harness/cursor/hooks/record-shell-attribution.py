#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    load_engine,
    read_state,
    record_attribution,
    require_ids,
    restore_snapshot,
    shell_tool_path,
)


def diagnose(details: str) -> None:
    print(f"git-handoff shell diagnostic: {details}", file=sys.stderr)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = require_ids(payload)
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        diagnose("tool_use_id is missing")
        print("{}")
        return 0
    path = shell_tool_path(
        conversation_id,
        generation_id,
        tool_use_id,
    )
    if not path.is_file():
        print("{}")
        return 0
    try:
        state = read_state(path)
        if (
            state.get("conversation_id") != conversation_id
            or state.get("generation_id") != generation_id
            or state.get("tool_use_id") != tool_use_id
        ):
            diagnose("shell baseline identity is mismatched")
            print("{}")
            return 0
        repo = Path(state["repo"])
        baseline = restore_snapshot(state.get("snapshot") or {})
        engine = load_engine()
        for relative_path in engine.repository_delta_paths(repo, baseline):
            record_attribution(
                conversation_id,
                generation_id,
                repo,
                relative_path,
                "Shell",
            )
        print("{}")
        return 0
    except (
        KeyError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
    ) as exc:
        diagnose(str(exc))
        print("{}")
        return 0
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
