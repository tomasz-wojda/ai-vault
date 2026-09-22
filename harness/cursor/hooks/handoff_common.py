#!/usr/bin/env python3

import importlib.util
import json
import os
import shlex
import time
from pathlib import Path


STATE_ROOT = Path.home() / ".cursor" / "hook-state" / "git-handoff"
MIGRATION_GRACE = STATE_ROOT / ".migration-grace"
PENDING_STOP_MAX_AGE_NS = 300 * 1_000_000_000
RESPONSE_SIGNATURE_FIELDS = (
    "model",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


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


def pending_stop_path(conversation_id: str) -> Path:
    return STATE_ROOT / conversation_id / ".pending-stop.json"


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def read_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def response_signature(payload: dict) -> dict[str, object] | None:
    signature = {
        field: payload.get(field)
        for field in RESPONSE_SIGNATURE_FIELDS
    }
    if any(value is None for value in signature.values()):
        return None
    return signature


def correlation_metadata(
    conversation_id: str,
    generation_id: str,
    payload: dict,
) -> dict:
    return {
        "conversation_id": conversation_id,
        "generation_id": generation_id,
        "captured_at_ns": time.time_ns(),
        "response_signature": response_signature(payload),
    }


def correlation_is_fresh(metadata: dict, now_ns: int | None = None) -> bool:
    captured_at_ns = metadata.get("captured_at_ns")
    if not isinstance(captured_at_ns, int):
        return False
    current_ns = time.time_ns() if now_ns is None else now_ns
    age_ns = current_ns - captured_at_ns
    return 0 <= age_ns <= PENDING_STOP_MAX_AGE_NS


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
