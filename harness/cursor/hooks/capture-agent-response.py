#!/usr/bin/env python3

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_common import (
    MIGRATION_GRACE,
    attributed_repo_paths,
    correlation_metadata,
    load_engine,
    pending_stop_path,
    read_state,
    require_ids,
    state_path,
    write_state,
)


def persist_validation(
    path: Path,
    state: dict,
    conversation_id: str,
    generation_id: str,
    payload: dict,
) -> None:
    metadata = correlation_metadata(
        conversation_id,
        generation_id,
        payload,
    )
    state.update(
        {
            "captured_at_ns": metadata["captured_at_ns"],
            "response_signature": metadata["response_signature"],
        }
    )
    write_state(path, state)
    write_state(pending_stop_path(conversation_id), metadata)


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = require_ids(payload)
    path = state_path(conversation_id, generation_id)
    if not path.is_file():
        if MIGRATION_GRACE.is_file():
            MIGRATION_GRACE.unlink(missing_ok=True)
            persist_validation(
                path,
                {
                    "conversation_id": conversation_id,
                    "generation_id": generation_id,
                    "validated": True,
                    "valid": True,
                    "violations": [],
                    "repo_paths": {},
                },
                conversation_id,
                generation_id,
                payload,
            )
            print("{}")
            return 0
        raise RuntimeError("commit handoff baseline state is missing")
    try:
        state = read_state(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("commit handoff baseline state is corrupt") from exc
    repo_paths, diagnostics = attributed_repo_paths(
        conversation_id,
        generation_id,
    )
    for diagnostic in diagnostics:
        print(
            f"git-handoff attribution diagnostic: {diagnostic}",
            file=sys.stderr,
        )
    if repo_paths:
        engine = load_engine()
        result = engine.validate_response_multi(
            payload.get("text", ""),
            repo_paths,
        )
    else:
        result = {"valid": True, "violations": []}
    state.update(
        {
            "validated": True,
            "valid": result["valid"],
            "violations": result.get("violations") or [],
            "repo_paths": repo_paths,
        }
    )
    persist_validation(
        path,
        state,
        conversation_id,
        generation_id,
        payload,
    )
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
