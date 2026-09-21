#!/usr/bin/env python3

import importlib.util
import json
import os
import sys
from pathlib import Path


sys.dont_write_bytecode = True


def load_engine(vault: Path):
    path = vault / "scripts" / "commit_handoff.py"
    spec = importlib.util.spec_from_file_location("commit_handoff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace_root(payload: dict, vault: Path) -> Path:
    roots = [Path(item).resolve() for item in payload.get("workspace_roots") or []]
    for root in roots:
        try:
            vault.relative_to(root)
            return root
        except ValueError:
            continue
    raise RuntimeError("ai-vault is not inside a Cursor workspace root")


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    payload = json.load(sys.stdin)
    generation_id = payload.get("generation_id")
    if not generation_id:
        raise RuntimeError("generation_id is missing")
    vault = Path(__file__).resolve().parents[3]
    workspace = workspace_root(payload, vault)
    engine = load_engine(vault)
    paths = engine.changed_paths(vault)
    if paths:
        result = engine.validate_response(payload.get("text", ""), paths)
    else:
        result = {"valid": True, "violations": []}
    result.update(
        {
            "generation_id": generation_id,
            "paths": paths,
            "vault": str(vault),
        }
    )
    state = (
        workspace
        / ".cursor"
        / "hook-state"
        / "ai-vault-handoff"
        / f"{generation_id}.json"
    )
    write_state(state, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
