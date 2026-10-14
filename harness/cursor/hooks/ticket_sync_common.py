#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from handoff_common import read_state, require_ids, workspace_roots, write_state


STATE_ROOT = Path.home() / ".cursor" / "hook-state" / "ticket-sync"
WORKLOG_NAME = re.compile(
    r"^\d{4}-\d{2}-\d{2}_([A-Z][A-Z0-9]*(?:-[0-9]+)?)"
    r"(?:_[A-Za-z0-9_-]+)?\.log$"
)


def worklog_key(name: str) -> str | None:
    match = WORKLOG_NAME.match(name)
    return match.group(1) if match else None


def active_worklogs(roots: list[Path]) -> dict[str, list[str]]:
    worklogs: dict[str, list[str]] = {}
    for root in roots:
        directory = Path(root) / "worklog"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.log")):
            key = worklog_key(path.name)
            if key and path.is_file():
                worklogs.setdefault(key, []).append(f"worklog/{path.name}")
    return worklogs


def mentioned_keys(text: str, keys) -> set[str]:
    if not text:
        return set()
    return {
        key
        for key in keys
        if re.search(
            rf"(?<![A-Za-z0-9-]){re.escape(key)}(?![A-Za-z0-9])",
            text,
        )
    }


def generation_path(conversation_id: str, generation_id: str) -> Path:
    return STATE_ROOT / conversation_id / f"{generation_id}.json"


def load_generation(conversation_id: str, generation_id: str) -> dict | None:
    path = generation_path(conversation_id, generation_id)
    if not path.is_file():
        return None
    try:
        state = read_state(path)
    except (OSError, json.JSONDecodeError):
        return None
    if (
        state.get("conversation_id") != conversation_id
        or state.get("generation_id") != generation_id
    ):
        return None
    return state


def save_generation(state: dict) -> None:
    write_state(
        generation_path(state["conversation_id"], state["generation_id"]),
        state,
    )


def clear_conversation(conversation_id: str) -> None:
    shutil.rmtree(STATE_ROOT / conversation_id, ignore_errors=True)


def followup_message(pending: dict[str, list[str]]) -> str:
    touched = ", ".join(
        f"`{key}` ("
        + ", ".join(f"`{path}`" for path in pending[key])
        + ")"
        for key in sorted(pending)
    )
    return (
        f"Ticket sync (R-29): this turn touched {touched}. Without a Write "
        "Gate preview and in the current mode, record anything new from "
        "this turn in each listed worklog and, where "
        "`.ai-worklog/state/<KEY>.json` exists, apply the matching "
        "`ai-worklog state` commands with `--apply`. Do not create, archive, "
        "or close out worklogs or state. If nothing new was produced for a "
        "ticket, reply `No ticket sync needed for <KEY>.` and stop."
    )
