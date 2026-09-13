---
name: worklog-chat-memory
version: "1.1.0"
description: >-
  Retrieves and maintains workspace conversation memory from materialized
  prompt-log turns and tiered SQLite indexes. Use when resuming prior work,
  recalling ticket decisions, searching past prompts and responses, inspecting
  artifacts, performing forensic dross searches, or synchronizing prompt.log
  through the ai-memory-ingester workflow.
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
`dross.db` only for forensic or audit requests. Set the FTS expression as a
bound parameter.

```bash
sqlite3 -json "${MEMORY_DATA}/convo.db" <<'SQL'
PRAGMA trusted_schema=ON;
.parameter init
.parameter set @query 'deployment'
SELECT d.id, d.source_archive, d.file_path, d.file_name, d.extension,
       bm25(documents_fts) AS rank, substr(d.content, 1, 2000) AS snippet
FROM documents_fts
JOIN documents d ON d.id = documents_fts.rowid
WHERE documents_fts MATCH @query
ORDER BY rank
LIMIT 10;
SQL
```

Repeat the bound query against `artifacts.db` when factual dumps may contain
the answer. Repeat it against `dross.db` only when the default tiers return
nothing or the request is forensic.

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

```bash
cat "${MEMORY_TREE}/RESUME.md"
```

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

## Synchronize memory

Run the unified sweep at session start:

```bash
cd "${MEMORY_REPO}"
./ai-memory-ingester sweep-memory --workspace-root "${MEMORY_WORKSPACE_ROOT}"
```

Supply journal or stream content through standard input or a temporary file.
Never place content in an interpolated command argument. Append to
`prompt.log`; never overwrite or insert into existing content.
