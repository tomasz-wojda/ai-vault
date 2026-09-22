#!/usr/bin/env python3

import importlib.util
import json
import os
import shlex
from pathlib import Path


STATE_ROOT = Path.home() / ".cursor" / "hook-state" / "git-handoff"
MIGRATION_GRACE = STATE_ROOT / ".migration-grace"


def vault_root() -> Path:
    return Path(__file__).resolve().parents[3]


def engine_path() -> Path:
    return vault_root() / "scripts" / "commit_handoff.py"


def load_engine():
    path = engine_path()
    spec = importlib.util.spec_from_file_location("commit_handoff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace_roots(payload: dict) -> list[Path]:
    roots = payload.get("workspace_roots") or []
    if not roots:
        raise RuntimeError("workspace_roots is missing")
    return [Path(item).resolve() for item in roots]


def require_ids(payload: dict) -> tuple[str, str]:
    conversation_id = payload.get("conversation_id")
    generation_id = payload.get("generation_id")
    if not conversation_id:
        raise RuntimeError("conversation_id is missing")
    if not generation_id:
        raise RuntimeError("generation_id is missing")
    return conversation_id, generation_id


def state_path(conversation_id: str, generation_id: str) -> Path:
    return STATE_ROOT / conversation_id / f"{generation_id}.json"


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def read_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint_snapshot(repo: Path, engine) -> dict[str, list[object]]:
    snapshot = engine.repository_snapshot(repo)
    return {path: list(fingerprint) for path, fingerprint in snapshot.items()}


def restore_snapshot(raw: dict[str, list[object]]) -> dict[str, tuple[object, ...]]:
    return {path: tuple(values) for path, values in raw.items()}


def renderer_command(repo: Path, paths: list[str]) -> str:
    script = engine_path()
    quoted_paths = " ".join(
        f"--path {shlex.quote(path)}" for path in paths
    )
    return (
        f"python3 {shlex.quote(str(script))} render "
        f"--repo {shlex.quote(str(repo.resolve()))} "
        f"{quoted_paths} --title '<semantic-title>' "
        f"--description '<one-paragraph-description>'"
    )
