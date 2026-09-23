#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    path_is_in_workspace,
    record_attribution,
    repository_for_path,
    require_ids,
    state_path,
    workspace_roots,
)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = require_ids(payload)
    if not state_path(conversation_id, generation_id).is_file():
        print("{}")
        return 0
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise RuntimeError("file_path is missing")
    path = Path(file_path).resolve()
    roots = workspace_roots(payload)
    if not path_is_in_workspace(path, roots):
        print("{}")
        return 0
    repo = repository_for_path(path)
    if repo is None:
        print("{}")
        return 0
    relative_path = str(path.relative_to(repo))
    record_attribution(
        conversation_id,
        generation_id,
        repo,
        relative_path,
        "afterFileEdit",
    )
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
