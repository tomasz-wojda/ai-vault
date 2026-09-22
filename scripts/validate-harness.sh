#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s tests -p 'test_harness_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m json.tool \
    harness/cursor/hooks.fragment.json >/dev/null

printf '\nHarness Validation\n\n'
printf '  ✓ Commit handoff renderer\n'
printf '  ✓ Cursor hook behavior\n'
printf '  ✓ User/workspace installer\n'
printf '\nPASS  3 checks\n'
