---
name: worklog-chat-memory
version: "1.6.0"
description: >-
  Retrieves and maintains workspace conversation memory from the immutable
  SQLite journal, materialized turns, and tiered SQLite indexes. Use when
  resuming prior work, recalling ticket decisions, searching past prompts and
  responses, recording turn events, inspecting artifacts, performing forensic
  dross searches, or synchronizing memory through the ai-memory-ingester
  workflow.
---

# Worklog Chat Memory

## Resolve paths

Require `MEMORY_WORKSPACE_ROOT`. Do not guess or hardcode the workspace path.

```bash
: "${MEMORY_WORKSPACE_ROOT:?Set MEMORY_WORKSPACE_ROOT}"
MEMORY_REPO="${MEMORY_WORKSPACE_ROOT}/repos/ai-memory-ingester"
MEMORY_DATA="${MEMORY_REPO}/data"
MEMORY_TREE="${MEMORY_WORKSPACE_ROOT}/worklog-chat"
```

## Read recent turns

The filename sequence is authoritative. Query only `chat:turns`; never use
SQLite identifier order as recency.

```bash
sqlite3 -json "${MEMORY_DATA}/convo.db" <<'SQL'
SELECT id, source_archive, file_path, file_name, extension, NULL AS rank,
       content AS snippet
FROM documents
WHERE source_archive = 'chat:turns'
  AND file_name GLOB 'turn-[0-9]*.md'
ORDER BY CAST(substr(file_name, 6, length(file_name) - 8) AS INTEGER) DESC,
         file_path ASC,
         id DESC
LIMIT 12;
SQL
```

## Search memory

Search `convo.db`, `worklogs.db`, and `artifacts.db` by default. Search
`dross.db` only for forensic or audit requests. Use the common retrieval
command so every IDE receives the same body relevance, recency, authority,
freshness, impact, and neighbor ranking.

```bash
cd "${MEMORY_REPO}"
./ai-memory-ingester query "deployment" --dataset worklog-chat --limit 10 --signals
```

Use `--dataset worklog-chat-all` only when the request is forensic or the
default tiers return nothing. Use `--db` only for explicit legacy-compatible
single-database inspection.

## Ask a question

`query` accepts a plain-language question in English or Polish, with or without
diacritics. If the strict query (all words ANDed) finds nothing, a relaxed query
runs: stop words removed, remaining words ORed with prefix terms, and Polish `ł`
variants for Polish queries. A query with an operator, phrase, parentheses, a
column filter or a typed prefix is never rewritten.

```bash
cd "${MEMORY_REPO}"
./ai-memory-ingester query "what did we decide about the traefik attribute" --limit 10 --explain
```

- `--relax auto|on|off` controls the relaxed query; `AI_MEMORY_RELAX=0` turns it off.
- `--explain` prints the query plan and the re-rank and late-pool status.
- If the memory service runs (`ai-worklog memory serve`), the top candidates are
  re-ranked by passage and a late-interaction pool adds recall. Flags:
  `--rerank auto|on|off`, `--rerank-depth N`, `--rerank-budget-ms N`,
  `--late auto|on|off`. `AI_MEMORY_RERANK=0` and `AI_MEMORY_LATE=0` turn them off.
  Without the service the output is the lexical order and `--explain` says why;
  `--rerank on` exits with code 5 instead.
- Explicit queries, ticket-only queries and keyword results that work today do
  not change.

Build and check the passage index with `ai-memory-ingester reindex [--verify]`
(or `ai-worklog memory reindex`). Measure changes with `ai-memory-ingester eval`
against a labelled query set kept outside git.

## Retrieve a ticket

Normalize `KD-6999`, `kd-6999`, and `kd6999` to `kd6999` before querying.
Never pass a bare hyphenated ticket to FTS5. Use hybrid retrieval so current
state and authoritative chunks precede conversation history.

```bash
cd "${MEMORY_REPO}"
./ai-memory-ingester ticket KD-6999 --limit 20
./ai-memory-ingester context --ticket KD-6999 --budget 22000
```

For direct authoritative inspection, query state and chunks without FTS:

```bash
sqlite3 -json "${MEMORY_DATA}/worklogs.db" <<'SQL'
SELECT id, source_archive, file_path, file_name, content
FROM documents
WHERE source_archive = 'worklog:state' AND file_name = 'kd6999.md'
UNION ALL
SELECT id, source_archive, file_path, file_name, content
FROM documents
WHERE source_archive = 'worklog:chunks' AND file_path LIKE 'kd6999/%'
ORDER BY source_archive DESC, file_path;
SQL
```

Treat `worklog:state` as current extractive state, current
`worklog:chunks` as authoritative evidence, turns as historical conversation,
and `worklog:evidence` as supporting evidence. Conflicting historical turns do
not override current worklog state.

## Facets

Facet tokens live in `file_path`:

- Ticket: lowercase key with separators removed, such as `cwp11649` or `kd6607`
- Date: `d` plus `yyyyMMdd`, such as `d20260811`
- Mode: `research`, `innovate`, `plan`, `execute`, or `nomode`
- Impact: `impact-high`, `impact-low`, or `impact-none`

Discover real facet values from the materialized tree before querying. Do not
guess a token and interpret zero results as absent memory.

```bash
rg --files "${MEMORY_TREE}/turns" |
  awk -F/ '{print $(NF-4), $(NF-3), $(NF-2), $(NF-1)}' |
  sort -u
```

Add facets to an FTS expression with column-scoped terms, for example
`file_path:kd6607 AND file_path:execute AND file_path:d202608*`.

## Assemble a byte-bounded resume

Use the materialized digest first. It is already curated to the 22000-byte
budget and can be read or referenced without invoking the database.
`RESUME.md` is an index: one block per active ticket (lifecycle, phase, next
action, freshness, path of the ticket resume), then recent turns that have no
ticket. Set `AI_MEMORY_RESUME_MODE=global` for the sweep to restore the
earlier single global digest.

```bash
cat "${MEMORY_TREE}/RESUME.md"
```

A session that works on one ticket reads that ticket's resume instead. It
holds the ticket capsule, the next action, open decisions and blockers from
the ticket state file, and the recent turns of that ticket within 12000 bytes.
The sweep refreshes only the resumes of tickets that changed.

```bash
cat "${MEMORY_TREE}/ticket-resume/KD-6999.md"
cd "${MEMORY_REPO}" && ./ai-memory-ingester resume --ticket KD-6999
```

`resume --ticket` prints the ticket resume when it exists and falls back to
the retrieval resume otherwise, or when `--mode`, `--impact`, `--since`,
`--until` or `--json` is given.

For a direct database resume, keep only complete turns whose cumulative UTF-8
content remains within the budget.

```bash
sqlite3 -json "${MEMORY_DATA}/convo.db" <<'SQL'
WITH ordered AS (
  SELECT id, source_archive, file_path, file_name, extension, content,
         CAST(substr(file_name, 6, length(file_name) - 8) AS INTEGER) AS sequence
  FROM documents
  WHERE source_archive = 'chat:turns'
    AND file_name GLOB 'turn-[0-9]*.md'
),
budgeted AS (
  SELECT *,
         sum(length(CAST(content AS BLOB))) OVER (
           ORDER BY sequence DESC, file_path ASC, id DESC
         ) AS consumed_bytes
  FROM ordered
)
SELECT id, source_archive, file_path, file_name, extension, NULL AS rank,
       content AS snippet
FROM budgeted
WHERE consumed_bytes <= 22000
ORDER BY sequence DESC, file_path ASC, id DESC;
SQL
```

## Read materialized documents

Turn files may be opened under `worklog-chat/turns`. Authoritative chunks live
under `worklog-chat/worklogs`, ticket capsules under
`worklog-chat/ticket-state`, artifacts under `worklog-chat/artifacts`, and
dross under `worklog-chat/dross`.

## Record turn events

During the shadow period every IDE uses the same JSON-on-stdin writer.
Authoritative capture is synchronous `journal.db` first; only after a
successful `record-event` append the current `prompt.log` audit entry. If
`record-event` fails, leave the failure visible and do not append
`prompt.log`.

Contract: [references/journal-writer-contract.json](references/journal-writer-contract.json).
Schema version `1` matches `ai-memory-ingester record-event`.

Required payload fields:

| Field | Requirement |
| --- | --- |
| `schema_version` | `1` |
| `source_ide` | `cursor`, `claude`, or `antigravity` |
| `source_kind` | `rule_write` for governed rule capture |
| `source_identity` | Stable source label, typically `prompt.log` |
| `user_text` | Exact user prompt text |
| `assistant_text` | Exact final assistant response text |

When available also supply `session_id`, `prompt_id`, `mode`, `tickets`,
`impact`, `event_time`, `event_time_confidence`, and `raw_payload`. Never
pass conversational payload through shell arguments, `printf`, or a heredoc:
shell commands are checked by Git guard hooks, and double-quoted text runs
command substitutions.

Every IDE runs the same two steps; only `source_ide` differs (`cursor`,
`claude`, or `antigravity`). `<workspace>` is the absolute workspace root.

1. Write the payload JSON with the IDE file-write tool (Cursor edit tool,
   Claude Code `Write`) to `<workspace>/tmp/journal-turns/<prompt_id>.json`,
   outside any Git repository so commit handoff attribution ignores it:

   ```json
   {
     "schema_version": 1,
     "source_ide": "cursor",
     "source_kind": "rule_write",
     "source_fidelity": "rule_write",
     "source_identity": "prompt.log",
     "session_id": "promptlog:2026-09-14",
     "prompt_id": "turn-example",
     "user_text": "<exact user prompt>",
     "assistant_text": "<exact final assistant response>",
     "outcome_summary": "<optional short outcome>",
     "mode": "execute",
     "tickets": ["DEVOPS-1"],
     "impact": "high",
     "event_time": "2026-09-14T16:00:00Z",
     "event_time_confidence": "exact",
     "raw_payload": "USER:\n<exact user prompt>\n\nASSISTANT:\n<exact final assistant response>"
   }
   ```

2. Record it from `<workspace>`. The command carries only paths, and the
   script finds the workspace root from the payload location:

   ```bash
   python3 repos/ai-vault/skills/worklog-chat-memory/scripts/record_turn.py \
     --payload tmp/journal-turns/turn-example.json
   ```

`record_turn.py` validates the required fields, takes the memory lock, pipes
the file to `ai-memory-ingester record-event` on stdin, and only after success
appends the `prompt.log` entry (`USER: <user_text>`, `ASSISTANT: <mode> —
<assistant_text>`), releases the lock and deletes the payload. On failure it
exits non-zero, keeps the payload for a retry, and does not touch `prompt.log`.

The memory lock is an exclusive SQLite transaction on
`<workspace>/.ai-worklog/locks/_journal.sqlite`. It keeps a journal row and its
`prompt.log` entry together when several sessions record turns at the same
time, and the operating system releases it if the process stops. The wait is
10 seconds (`AI_MEMORY_LOCK_TIMEOUT` sets another value in seconds). If the
lock stays busy, the script exits with code 75, records nothing and leaves the
payload in place for a retry. `AI_MEMORY_LOCK=0` turns the lock off. The
`record-event` output line ends with `tickets=<keys>`.

Do not rely on Claude user or project hooks for capture; organization policy
blocks them and rules remain the portable adapter. In Cursor, the payload file
and the command pass the Git guard and attribution hooks unchanged.

## Synchronize memory

Run the unified sweep at session start:

```bash
cd "${MEMORY_REPO}"
./ai-memory-ingester sweep-memory --workspace-root "${MEMORY_WORKSPACE_ROOT}"
```

The sweep takes the same memory lock while it writes `RESUME.md` and the
ticket resumes. It builds the content before it takes the lock, so the lock is
held for file writes only.

Supply journal or stream content through standard input or a temporary file.
Never place content in an interpolated command argument. During rollback the
legacy `prompt.log`-only path remains accepted until journal parity gates pass.
