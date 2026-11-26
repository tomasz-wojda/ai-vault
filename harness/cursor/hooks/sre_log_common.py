#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from handoff_common import read_state, require_ids, workspace_roots, write_state


STATE_ROOT = Path.home() / ".cursor" / "hook-state" / "sre-log"
SKILL_NAME = "sre-incident-investigation"
SKILL_SUFFIX = f"{SKILL_NAME}/SKILL.md"
LOG_NAME = "SRE.log"
FOLLOWUP_PREFIX = "SRE log (R-31):"
WAIVER = "No SRE log entry needed."


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
    directory = STATE_ROOT / conversation_id
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        if path.suffix in (".json", ".tmp"):
            path.unlink(missing_ok=True)


def log_sizes(roots: list[Path]) -> dict[str, int]:
    sizes = {}
    for root in roots:
        path = Path(root) / LOG_NAME
        sizes[str(root)] = path.stat().st_size if path.is_file() else 0
    return sizes


def log_grew(state: dict) -> bool:
    baseline = state.get("baseline") or {}
    current = log_sizes([Path(root) for root in baseline])
    return any(current[root] > int(size) for root, size in baseline.items())


def is_skill_path(path: str) -> bool:
    if not path:
        return False
    candidates = (Path(path).as_posix(), Path(path).resolve().as_posix())
    return any(candidate.endswith(SKILL_SUFFIX) for candidate in candidates)


def prompt_invokes(prompt: str) -> bool:
    return SKILL_NAME in (prompt or "")


def is_followup(prompt: str) -> bool:
    return (prompt or "").lstrip().startswith(FOLLOWUP_PREFIX)


def followup_message() -> str:
    return (
        f"{FOLLOWUP_PREFIX} this turn invoked `{SKILL_NAME}` and `{LOG_NAME}` "
        "did not grow. In the current mode and without a Write Gate preview, "
        "write one entry in the format of "
        "`repos/ai-vault/skills/jira-worklog-processor/worklog-reference.md` "
        "§ \"SRE.log Entry Format\" to `incidents/<key>/sre-log-<YYYYMMDDTHHMM>.txt` "
        "and append it from the workspace root with `python3 "
        "repos/ai-vault/skills/sre-incident-investigation/scripts/"
        "append_sre_log.py --entry <that file>`. If the turn only read or "
        "edited the skill files without investigating an incident, reply "
        f"`{WAIVER}` and stop."
    )
