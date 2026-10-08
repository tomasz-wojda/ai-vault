#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "journal-writer-contract.json"
)


def load_payload(path: Path, contract: dict) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read payload {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    missing = [
        field
        for field in contract["required_fields"]
        if field not in payload
    ]
    if missing:
        raise ValueError(f"payload is missing {', '.join(missing)}")
    if payload["schema_version"] != contract["schema_version"]:
        raise ValueError(
            f"schema_version must be {contract['schema_version']}"
        )
    return payload


def discover_workspace_root(payload_path: Path, ingester_subpath: str) -> Path | None:
    for candidate in payload_path.parents:
        if (candidate / ingester_subpath).is_dir():
            return candidate
    return None


def prompt_log_entry(payload: dict, timestamp: str) -> str:
    mode = payload.get("mode")
    assistant = payload["assistant_text"]
    if mode:
        assistant = f"{mode} — {assistant}"
    return (
        "--- PROMPT LOG ENTRY ---\n"
        f"TIMESTAMP: {timestamp}\n"
        f"USER: {payload['user_text']}\n"
        f"ASSISTANT: {assistant}\n"
        "--- END PROMPT LOG ENTRY ---\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a turn in journal.db, then append prompt.log.",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.environ.get("MEMORY_WORKSPACE_ROOT"),
        help=(
            "Workspace root; defaults to MEMORY_WORKSPACE_ROOT, then the "
            "nearest payload ancestor that contains the ingester"
        ),
    )
    parser.add_argument("--payload", required=True, help="Payload JSON file")
    parser.add_argument(
        "--keep-payload",
        action="store_true",
        help="Keep the payload file after a successful record",
    )
    arguments = parser.parse_args()

    payload_path = Path(arguments.payload).expanduser().resolve()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if arguments.workspace_root:
        root = Path(arguments.workspace_root).expanduser().resolve()
    else:
        root = discover_workspace_root(payload_path, contract["ingester_subpath"])
        if root is None:
            parser.error(
                "workspace root not found; pass --workspace-root or write the "
                "payload under the workspace"
            )
    try:
        payload = load_payload(payload_path, contract)
    except ValueError as error:
        print(f"record_turn: {error}", file=sys.stderr)
        return 2

    memory_repo = root / contract["ingester_subpath"]
    ingester = memory_repo / "ai-memory-ingester"
    if not ingester.is_file():
        print(f"record_turn: ingester not found: {ingester}", file=sys.stderr)
        return 2
    with payload_path.open("rb") as stdin:
        result = subprocess.run(
            [str(ingester), contract["command"]],
            cwd=memory_repo,
            stdin=stdin,
            check=False,
        )
    if result.returncode != 0:
        print(
            "record_turn: record-event failed; prompt.log not appended",
            file=sys.stderr,
        )
        return result.returncode

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with (root / "prompt.log").open("a", encoding="utf-8") as log:
        log.write(prompt_log_entry(payload, timestamp))
    if not arguments.keep_payload:
        payload_path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
