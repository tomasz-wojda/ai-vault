# Technical Specification: Groovy SQLite FTS5 Context Memory Engine

## 1. Target Component: Build & Path Infrastructure (`ai-worklog-framework`)
- Target File: `groovy/build.gradle`
  - Add dependency: `implementation 'org.xerial:sqlite-jdbc:3.45.1.0'`.
- Target File: `groovy/src/main/groovy/ai/worklog/framework/core/FrameworkPaths.groovy`
  - Add property: `final File memoryDb = new File(this.configDir, 'memory.db')`.

## 2. Target Component: Database Connection & Schema Management (`ai-worklog-framework`)
- Target File: `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryDatabase.groovy`
  - Class `MemoryDatabase`:
    - Method `static Sql getSql(FrameworkPaths paths)`: Instantiates `groovy.sql.Sql` with URL `jdbc:sqlite:${paths.memoryDb.absolutePath}`.
    - Method `static void init(FrameworkPaths paths)`: Ensures `.ai-worklog/` directory exists, executes PRAGMAs (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`), and executes DDL statements:
      - Table `sessions` (`session_id TEXT PRIMARY KEY`, `started_at TEXT`, `workspace_path TEXT`, `active_ticket TEXT`, `metadata TEXT`).
      - Table `interactions` (`id INTEGER PRIMARY KEY AUTOINCREMENT`, `session_id TEXT`, `turn_index INTEGER`, `timestamp TEXT`, `mode TEXT`, `ticket_key TEXT`, `prompt_text TEXT`, `response_text TEXT`, `token_estimate INTEGER`).
      - FTS5 Table `interactions_fts` (columns: `prompt_text`, `response_text`, `ticket_key`, `mode`).
      - Table `decisions` (`id TEXT PRIMARY KEY`, `ticket_key TEXT`, `category TEXT`, `summary TEXT`, `context TEXT`, `created_at TEXT`).
      - FTS5 Table `decisions_fts` (columns: `summary`, `context`, `ticket_key`).

## 3. Target Component: Memory Persistence & Writer (`ai-worklog-framework`)
- Target File: `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryWriter.groovy`
  - Class `MemoryWriter`:
    - Method `static long logTurn(FrameworkPaths paths, String prompt, String response, String mode, String ticketKey, String sessionId)`: Inserts interaction row into `interactions` and synchronizes `interactions_fts`.
    - Method `static void recordDecision(FrameworkPaths paths, String ticketKey, String category, String summary, String context)`: Inserts record into `decisions` and synchronizes `decisions_fts`.

## 4. Target Component: Retrieval & Context Synthesis (`ai-worklog-framework`)
- Target File: `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryQuery.groovy`
  - Class `MemoryQuery`:
    - Method `static List<Map> queryFts(FrameworkPaths paths, String queryText, String ticketKey, int limit)`: Executes BM25 match query against `interactions_fts` and `decisions_fts`.
    - Method `static List<Map> queryTicketHistory(FrameworkPaths paths, String ticketKey, int limit)`: Returns recent turns and decisions for given ticket.
    - Method `static String formatContextSnippet(List<Map> records)`: Converts retrieved turns and decisions into high-density Markdown for prompt context injection.

## 5. Target Component: CLI Command Handler & Main Dispatcher (`ai-worklog-framework`)
- Target File: `groovy/src/main/groovy/ai/worklog/framework/commands/MemoryCommands.groovy`
  - Class `MemoryCommands`:
    - Method `static int run(String action, List<String> args, FrameworkPaths paths, ExitCodes exitCodes)`: Handles subcommands `init`, `log`, `query`, and `export`.
- Target File: `groovy/src/main/groovy/ai/worklog/framework/Main.groovy`
  - Import `ai.worklog.framework.commands.MemoryCommands`.
  - Route `command == 'memory'` to `MemoryCommands.run(action, args, paths, exitCodes)`.

## 6. Target Component: Testing & Validation (`ai-worklog-framework`)
- Target File: `groovy/src/test/groovy/ai/worklog/framework/memory/MemoryDatabaseTest.groovy`
  - Test SQLite schema creation and WAL initialization.
  - Test turn insertion and FTS index synchronization.
  - Test BM25 ranked querying and ticket-scoped extraction.
  - Test CLI subcommands `memory init`, `memory log`, `memory query`.

## 7. Target Component: Protocol Rules & Non-Negotiables (`ai-vault`)
- Target File: `ai-vault/.rules`
  - Update Rule 1: Specify `prompt.log` as append-only raw file audit log; replace mandatory full `prompt.log` reading with targeted memory querying and active ticket state loading.
- Target File: `ai-vault/CLAUDE.md`
  - Update Non-negotiables section: Specify targeted context ingestion via memory query and ticket state.
- Target File: `skills/jira-worklog-processor/SKILL.md`
  - Add `.ai-worklog/memory.db` to Workspace Dependencies table.
- Target File: `skills/devops-daily-protocol/SKILL.md`
  - Add `.ai-worklog/memory.db` to Workspace Dependencies and update Day Start context loading sequence.

## IMPLEMENTATION CHECKLIST:
1. Add `org.xerial:sqlite-jdbc:3.45.1.0` dependency to `groovy/build.gradle`.
2. Add `memoryDb` property to `groovy/src/main/groovy/ai/worklog/framework/core/FrameworkPaths.groovy`.
3. Create `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryDatabase.groovy` with schema initialization and connection management.
4. Create `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryWriter.groovy` with turn and decision persistence.
5. Create `groovy/src/main/groovy/ai/worklog/framework/memory/MemoryQuery.groovy` with FTS5 search and context snippet formatting.
6. Create `groovy/src/main/groovy/ai/worklog/framework/commands/MemoryCommands.groovy` with CLI command implementations.
7. Update `groovy/src/main/groovy/ai/worklog/framework/Main.groovy` to register and dispatch `memory` subcommands.
8. Create `groovy/src/test/groovy/ai/worklog/framework/memory/MemoryDatabaseTest.groovy` with unit tests.
9. Execute `./gradlew test` in `ai-worklog-framework/groovy`.
10. Update `ai-vault/.rules` with updated context loading and prompt logging directives.
11. Update `ai-vault/CLAUDE.md` with updated non-negotiables.
12. Update `ai-vault/skills/jira-worklog-processor/SKILL.md` workspace dependencies.
13. Update `ai-vault/skills/devops-daily-protocol/SKILL.md` workspace dependencies.
14. Execute `./scripts/validate-skills.sh` in `ai-vault` to verify all skill contracts.
