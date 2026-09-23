#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    fingerprint_snapshot,
    load_engine,
    path_is_in_workspace,
    repository_for_path,
    require_ids,
    shell_tool_path,
    state_path,
    workspace_roots,
    write_state,
)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = require_ids(payload)
    if not state_path(conversation_id, generation_id).is_file():
        print(json.dumps({"permission": "allow"}))
        return 0
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        raise RuntimeError("tool_use_id is missing")
    tool_input = payload.get("tool_input") or {}
    working_directory = (
        tool_input.get("working_directory")
        or payload.get("cwd")
    )
    if not isinstance(working_directory, str) or not working_directory:
        raise RuntimeError("shell working directory is missing")
    cwd = Path(working_directory).resolve()
    roots = workspace_roots(payload)
    if not path_is_in_workspace(cwd, roots):
        print(json.dumps({"permission": "allow"}))
        return 0
    repo = repository_for_path(cwd)
    if repo is None:
        print(json.dumps({"permission": "allow"}))
        return 0
    engine = load_engine()
    write_state(
        shell_tool_path(conversation_id, generation_id, tool_use_id),
        {
            "conversation_id": conversation_id,
            "generation_id": generation_id,
            "tool_use_id": tool_use_id,
            "repo": str(repo.resolve()),
            "snapshot": fingerprint_snapshot(repo, engine),
        },
    )
    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
