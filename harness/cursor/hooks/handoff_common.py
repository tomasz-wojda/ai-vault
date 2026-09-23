#!/usr/bin/env python3

import importlib.util
import json
import os
import shlex
import shutil
import time
import uuid
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


def generation_tracking_root(
    conversation_id: str,
    generation_id: str,
) -> Path:
    return STATE_ROOT / conversation_id / generation_id


def attribution_events_root(
    conversation_id: str,
    generation_id: str,
) -> Path:
    return generation_tracking_root(
        conversation_id,
        generation_id,
    ) / "attribution"


def shell_tool_path(
    conversation_id: str,
    generation_id: str,
    tool_use_id: str,
) -> Path:
    safe_tool_id = "".join(
        character
        for character in tool_use_id
        if character.isalnum() or character in {"-", "_"}
    )
    if not safe_tool_id:
        raise RuntimeError("tool_use_id is invalid")
    return generation_tracking_root(
        conversation_id,
        generation_id,
    ) / "shell" / f"{safe_tool_id}.json"


def clear_generation_tracking(
    conversation_id: str,
    generation_id: str,
) -> None:
    shutil.rmtree(
        generation_tracking_root(conversation_id, generation_id),
        ignore_errors=True,
    )


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


def repository_for_path(path: Path) -> Path | None:
    resolved = path.resolve()
    current = resolved if resolved.is_dir() else resolved.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def path_is_in_workspace(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return any(
        resolved == root or root in resolved.parents
        for root in roots
    )


def record_attribution(
    conversation_id: str,
    generation_id: str,
    repo: Path,
    relative_path: str,
    source: str,
) -> None:
    engine = load_engine()
    validated = engine.validate_paths(repo, [relative_path])[0]
    event = {
        "conversation_id": conversation_id,
        "generation_id": generation_id,
        "repo": str(repo.resolve()),
        "path": validated,
        "fingerprint": list(engine.path_fingerprint(repo, validated)),
        "source": source,
        "captured_at_ns": time.time_ns(),
    }
    event_path = attribution_events_root(
        conversation_id,
        generation_id,
    ) / f"{event['captured_at_ns']}-{uuid.uuid4().hex}.json"
    write_state(event_path, event)


def attributed_repo_paths(
    conversation_id: str,
    generation_id: str,
) -> tuple[dict[str, list[str]], list[str]]:
    engine = load_engine()
    root = attribution_events_root(conversation_id, generation_id)
    latest: dict[tuple[str, str], dict] = {}
    diagnostics: list[str] = []
    if not root.is_dir():
        return {}, diagnostics
    for event_path in sorted(root.glob("*.json")):
        try:
            event = read_state(event_path)
        except (OSError, json.JSONDecodeError):
            diagnostics.append(f"corrupt attribution event: {event_path.name}")
            continue
        if (
            event.get("conversation_id") != conversation_id
            or event.get("generation_id") != generation_id
        ):
            diagnostics.append(
                f"mismatched attribution event: {event_path.name}"
            )
            continue
        repo_value = event.get("repo")
        path_value = event.get("path")
        captured_at_ns = event.get("captured_at_ns")
        if (
            not isinstance(repo_value, str)
            or not isinstance(path_value, str)
            or not isinstance(captured_at_ns, int)
        ):
            diagnostics.append(
                f"incomplete attribution event: {event_path.name}"
            )
            continue
        key = (repo_value, path_value)
        previous = latest.get(key)
        if (
            previous is None
            or captured_at_ns > previous["captured_at_ns"]
        ):
            latest[key] = event
    grouped: dict[str, list[str]] = {}
    changed_by_repo: dict[str, set[str]] = {}
    for (repo_value, path_value), event in sorted(latest.items()):
        repo = Path(repo_value)
        if repo_value not in changed_by_repo:
            try:
                changed_by_repo[repo_value] = set(engine.changed_paths(repo))
            except engine.HandoffError:
                diagnostics.append(
                    f"attributed repository is unavailable: {repo_value}"
                )
                continue
        if path_value not in changed_by_repo[repo_value]:
            continue
        current_fingerprint = list(
            engine.path_fingerprint(repo, path_value)
        )
        if current_fingerprint != event.get("fingerprint"):
            diagnostics.append(
                f"attributed path changed after agent edit: "
                f"{repo_value}/{path_value}"
            )
            continue
        grouped.setdefault(repo_value, []).append(path_value)
    return grouped, diagnostics


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
