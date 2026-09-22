#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    MIGRATION_GRACE,
    load_engine,
    pending_stop_path,
    require_ids,
    state_path,
    write_state,
    workspace_roots,
)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = require_ids(payload)
    MIGRATION_GRACE.unlink(missing_ok=True)
    pending_stop_path(conversation_id).unlink(missing_ok=True)
    engine = load_engine()
    repos = engine.discover_git_repos(workspace_roots(payload))
    baselines = {}
    for repo in repos:
        baselines[str(repo)] = {
            path: list(fingerprint)
            for path, fingerprint in engine.repository_snapshot(repo).items()
        }
    state = {
        "conversation_id": conversation_id,
        "generation_id": generation_id,
        "workspace_roots": [
            str(root) for root in workspace_roots(payload)
        ],
        "baselines": baselines,
        "repos": [str(repo) for repo in repos],
        "validated": False,
        "valid": False,
        "violations": [],
        "repo_paths": {},
    }
    write_state(state_path(conversation_id, generation_id), state)
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
