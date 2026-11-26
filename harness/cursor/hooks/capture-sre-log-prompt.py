#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sre_log_common as sre


def main() -> int:
    payload = json.load(sys.stdin)
    conversation_id, generation_id = sre.require_ids(payload)
    roots = sre.workspace_roots(payload)
    sre.clear_conversation(conversation_id)
    prompt = payload.get("prompt") or ""
    if not sre.is_followup(prompt):
        sre.save_generation(
            {
                "conversation_id": conversation_id,
                "generation_id": generation_id,
                "workspace_roots": [str(root) for root in roots],
                "invoked": sre.prompt_invokes(prompt),
                "waived": False,
                "baseline": sre.log_sizes(roots),
            }
        )
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
