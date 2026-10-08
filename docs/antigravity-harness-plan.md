# AntiGravity Harness Plan

Status: proposed, not implemented
Created: 2026-10-08
Scope: `ai-vault` (harness, installer, docs) and `ai-worklog-framework`
(workspace setup)

## Goal

Give AntiGravity the same workspace behavior that Cursor and Claude Code now
have:

| Capability | Cursor | Claude Code | AntiGravity today |
| --- | --- | --- | --- |
| `.rules` (MODE protocol, Absolute Mode, safety) always on | `AGENTS.md` link | `CLAUDE.md` imports `@.rules` | Probably via `AGENTS.md` link (symlink support unverified) |
| Git handoff governance rule | `.cursor/rules/git-handoff-governance.mdc` | Imported by `CLAUDE.md` | Missing |
| Worklog memory rule and turn capture | `.cursor/rules/worklog-chat-memory.mdc` | Imported by `CLAUDE.md` | Missing |
| `RESUME.md` in context at session start | Not inlined (`@file` is read on demand) | Inlined by `@worklog-chat/RESUME.md` | Missing |
| Skills | `.cursor/skills/` | `.claude/skills/` | `.agents/skills/` (already materialized) |
| Git mutation guard | `beforeShellExecution` hook | Rule-driven only (hooks blocked by policy) | Missing |
| Commit handoff enforcement and attribution | Cursor hooks | Rule-driven only | Missing |
| Installed by `ai-worklog workspace apply` | Yes | Yes | Skills only |

## Verified AntiGravity Facts

Source: official documentation at antigravity.google, read 2026-10-08. Recheck
these pages before implementing.

Rules (https://antigravity.google/docs/rules):

- Workspace rules live in `<workspace>/.agents/rules/*.md`; `.agent/` (singular)
  is legacy only.
- Every file in `rules/` must start with YAML frontmatter declaring
  `trigger: always_on | model_decision | glob | manual`. A missing or invalid
  trigger makes AntiGravity silently discard the rule, so the Cursor
  `alwaysApply: true` frontmatter cannot be reused.
- The scan is flat; nested rule files need registration in `.agents/rules.json`.
- `AGENTS.md` or `GEMINI.md` at the workspace root, and in each directory up the
  tree from an edited file, are read as always-on rules without frontmatter.
- `.rules` and `CLAUDE.md` are not mentioned and must be assumed unread.
- Global always-on files: `~/.gemini/AGENTS.md` or `~/.gemini/GEMINI.md`;
  modular global rules: `~/.gemini/config/rules/*.md` (frontmatter required).
- An inline include, written as `@[label]` immediately followed by `(path)`,
  inlines the target file before evaluation and size checks; relative paths
  resolve from the rule file's directory. A bare `@filename` is only resolved to
  a path and read on demand.
- Limits: 24,000 bytes per rule file after inlining, 20,000 tokens for all rules.

Skills (https://antigravity.google/docs/skills):

- Workspace skills: `<workspace>/.agents/skills/<skill>/`; `.agent/skills` is
  legacy.
- Global skills: `~/.gemini/config/skills/<skill>/`.

Hooks (https://antigravity.google/docs/hooks):

- `hooks.json` at `<workspace>/.agents/hooks.json` or
  `~/.gemini/config/hooks.json`.
- Events: `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`.
- A shell guard is `PreToolUse` with `"matcher": "run_command"`; stdout
  `decision` is `allow`, `deny`, `ask`, `force_ask`, or `deny_unless_prior_grant`.
- `Stop` can return `"continue"` to keep the agent running.

Permissions (https://antigravity.google/docs/permissions):

- Deny rules use `command(prefix)` or `command(regex:pattern)`.

Workflows (https://antigravity.google/docs/ide/workflows): IDE workflows stop
working on 2026-10-19 and are replaced by skills. None are used here; do not add
any.

Unverified: symlink support for rules, skills, and `AGENTS.md`; the JSON payload
fields each hook event receives; the tool names for file edits.

## Corrections to Current Docs

These statements are wrong today and are fixed in Phase 1:

- `README.md` and `ONBOARDING.md` link skills to `~/.agent/skills` and rules to
  `~/.agent/.rules`. AntiGravity reads `~/.gemini/config/skills/` and
  `~/.gemini/AGENTS.md`; `~/.agent/` is not a documented location.
- The README Windows example links `.rules` under `.gemini\.agent\`, which is
  not a documented rules path either.
- `CLAUDE.md` and the README tree say AntiGravity consumes `.rules`. It reads
  `AGENTS.md`, which is already linked to `.rules` in every installed workspace.

## Phase 1 — Rules and Skills

### 1.1 AntiGravity rule files in the harness

Add `harness/antigravity/rules/` with three managed rule templates. Each file
is the frontmatter block `trigger: always_on` followed by one inline include
(`@[label]` immediately followed by `(path)`) of an existing rule body, so the
rule text has a single source:

- `git-handoff-governance.md` includes `git-handoff-governance.mdc`.
- `worklog-chat-memory.md` includes `worklog-chat-memory.mdc`.
- `worklog-chat-resume.md` includes `<workspace>/worklog-chat/RESUME.md` in its
  own file, because `RESUME.md` (22,000 bytes) plus the memory rule would exceed
  the 24,000-byte limit and the whole rule would be silently dropped.

The included Cursor bodies carry their own `alwaysApply` frontmatter as text;
confirm in 1.5 that this does not confuse AntiGravity, otherwise move the shared
bodies to `harness/shared/rules/*.md` without frontmatter and have both the
Cursor `.mdc` files and these templates use them.

### 1.2 Installer

Extend `scripts/install-cursor-harness.py --workspace-rules`:

- Write the three files to `<workspace>/.agents/rules/` as managed generated
  files (marker comment, like `CLAUDE.md`), with include paths computed relative
  to `<workspace>/.agents/rules/`. Generated files avoid depending on unverified
  symlink support.
- Keep the existing `AGENTS.md` link to `.rules`; it already covers AntiGravity
  when symlinks are followed. If 1.5 shows AntiGravity does not follow it,
  replace `AGENTS.md` with a managed file whose only content is an inline
  include of the vault `.rules`.
- Apply the same adopt, update-if-marked, and refuse-otherwise rules used for
  `CLAUDE.md`.
- Add installer tests for creation, idempotency, update of marked files, refusal
  of unmanaged files, and the size of each generated file after include
  expansion (fail when a rule exceeds 24,000 bytes).

### 1.3 Framework

- `workspace apply` already runs `--workspace-rules`; no code change is needed
  for installation.
- Optionally pass the selected IDEs (`--ide cursor --ide antigravity`) so the
  installer writes only the files those IDEs read. Add `--ide` to the installer
  first.
- Improve AntiGravity detection in `shared/setup-rules.json`: add
  `~/.gemini` to `config_homes` and the `antigravity` command if it exists.

### 1.4 Documentation

- Fix the three corrections above in `README.md`, `ONBOARDING.md`, and
  `CLAUDE.md`.
- Optional global setup: link `~/.gemini/config/skills/<skill>` to vault skills
  and `~/.gemini/AGENTS.md` to the vault `.rules`, only for users who want the
  rules outside registered workspaces.

### 1.5 Verification on a machine with AntiGravity

1. Run `ai-worklog workspace apply --ide antigravity`.
2. Start a new AntiGravity agent session in the workspace.
3. The first reply starts with `MODE: RESEARCH` (proves `AGENTS.md` is read
   through the link).
4. Ask which always-on rules are active; all three `.agents/rules/` files are
   listed, and the agent can quote a line from `RESUME.md`.
5. Ask the agent to use the `worklog-chat-memory` skill; it resolves from
   `.agents/skills/`.
6. Record findings for every Unverified item in this plan.

## Phase 2 — Turn Capture

The capture path is rule-driven and IDE-neutral, so no new code is expected:

- The memory rule tells the agent to write the payload with its file tool and
  run `record_turn.py` with `source_ide` `antigravity`; confirm the rule text
  says "this IDE" rather than naming Cursor.
- Verify one real capture: payload written to
  `<workspace>/tmp/journal-turns/`, `record_turn.py` run from the workspace root,
  journal row with `source_ide` `antigravity`, and `prompt.log` entry appended.
- Confirm AntiGravity's permission preset does not prompt for the
  `record_turn.py` command on every turn; if it does, add an allow rule for that
  exact command prefix.

## Phase 3 — Git Guard and Commit Handoff

### 3.1 Immediate guard through permissions

Add deny rules to the AntiGravity permission settings, documented in
`README.md`:

```
command(regex:(^|[;&|(]\s*)(sudo\s+)?git(\s+-C\s+\S+)?(\s+-c\s+\S+)*\s+(add|commit|push)\b)
```

This is a coarse prefix and regex match and does not understand quoting. It
blocks direct mutations but can still block a command whose quoted text contains
`; git commit`, which is the problem fixed for Cursor in `guard-git-mutations.py`.
Treat it as a stopgap until 3.2.

### 3.2 Hooks port

Add `harness/antigravity/hooks.fragment.json` and thin adapters in
`harness/antigravity/hooks/` that translate AntiGravity hook payloads into the
existing logic in `harness/cursor/hooks/`:

| Cursor hook | AntiGravity event | Adapter work |
| --- | --- | --- |
| `beforeShellExecution` → `guard-git-mutations.py` | `PreToolUse`, matcher `run_command` | Map command and cwd fields; translate `permission` to `decision` |
| `beforeSubmitPrompt` → `capture-turn-baseline.py` | `PreInvocation` | Map conversation and generation identifiers |
| `preToolUse`/`postToolUse` Shell → shell baseline and attribution | `PreToolUse`/`PostToolUse`, matcher `run_command` | Map tool-use identifier and working directory |
| `afterFileEdit` → `record-file-attribution.py` | `PostToolUse`, matcher for the file-edit tool | Identify tool name and file path field |
| `afterAgentResponse` → `capture-agent-response.py` | `PostInvocation` | Map response text and generation identifier |
| `stop` → `require-commit-handoff.py` | `Stop` | Return `"continue"` with the handoff instruction instead of Cursor's follow-up |

Steps:

1. Log the raw payload of every event once with a temporary logging hook and
   record the field names in this plan.
2. Factor `handoff_common.py` so identifiers come from an IDE-specific payload
   reader; keep the Cursor reader unchanged and covered by existing tests.
3. Add the AntiGravity readers and adapters, with fixture payloads from step 1
   in new `tests/test_harness_antigravity.py`.
4. Install globally into `~/.gemini/config/hooks.json` with the same merge,
   legacy-removal, and fail-closed rules as the Cursor user-scope installer
   (`--ide antigravity --scope user`).
5. Remove the 3.1 regex deny rule once the guard hook is verified.

All hook scripts must keep `from __future__ import annotations` and run on
Python 3.9, matching the Cursor hooks.

## Phase 4 — Skills Documentation

No AntiGravity-specific change: skills use the same `SKILL.md` frontmatter, and
`description` is already present in every skill. Confirm `validate-skills.sh`
still accepts all seven skills and that `name` matches the directory, which
AntiGravity treats as optional but Cursor and Claude Code require.

## Acceptance

- A fresh `ai-worklog workspace apply --ide antigravity` produces a workspace
  where a new AntiGravity session starts in `MODE: RESEARCH`, sees the git
  handoff and memory rules and `RESUME.md`, and finds all seven skills.
- `ai-worklog workspace check` reports the AntiGravity rule files in its `rules`
  layer.
- A turn captured from AntiGravity appears in `journal.db` with `source_ide`
  `antigravity` before its `prompt.log` entry.
- An agent-issued `git add`, `git commit`, or `git push` in a repository is
  denied, while recording a reply that contains the handoff text is allowed.
- Harness and skill validation pass under the default Python and Python 3.9.

## Open Questions

1. Does AntiGravity follow symlinks for `AGENTS.md`, rule files, and skill
   folders?
2. What are the exact payload fields for each hook event and the file-edit tool
   name?
3. Is `RESUME.md` worth its share of the 20,000-token rules budget in every
   session, or should AntiGravity read it on demand like Cursor?

---
Created using Anthropic Claude. Keep this on internal versions until a human
has reviewed and verified the content.
