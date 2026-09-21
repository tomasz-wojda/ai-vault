# CLAUDE.md

Claude Code equivalent of `.rules` (which Claude Code does not read). Cursor and
AntiGravity consume `.rules`; Claude Code consumes this file.

The full rule set lives in `.rules` and is imported below. The directives restated
here are the ones whose failure causes damage, so they hold even if the import does
not resolve.

@.rules

## Non-negotiables

- **Git inspection is read-only.** Never run `git add`, `git commit`, or
  `git push`. After changes are applied, run `scripts/commit_handoff.py render`
  and paste its two Markdown blocks exactly. The first command is
  `git add -- …`; the second uses exactly two `-m` flags so Git inserts one
  blank line after the title. The description is one paragraph wrapped at 70
  characters per line with no blank lines. Never use HEREDOC or additional
  `-m` flags.
- **Journal capture is rule-driven, not hook-driven.** Do not configure Claude
  user or project hooks for turn capture; organization policy blocks them.
  After every response, write the turn to `journal.db` first through
  `ai-memory-ingester record-event` with JSON on stdin per
  `skills/worklog-chat-memory/references/journal-writer-contract.json`, using
  exact user text and exact final assistant response text. Only after a
  successful write append the same current `prompt.log` audit entry. If
  `record-event` fails, leave the failure visible and do not append
  `prompt.log`. Never overwrite `prompt.log`; create it only if absent.
- **Read before Write.** The Write tool overwrites; it does not append. If a file
  exists, read it and merge.
- **No unsolicited documentation or code comments.** Only when explicitly asked.
- **Never read a credential file for its values.** Pass the path to the consuming
  script. Applies to `**/credentials`, `**/*.properties`, `**/cookie`.
- **Jenkinsfiles use scripted pipeline syntax**, not declarative.
- If it is not in the context and the answer is unknown, say "I don't know".

## Response Style — Absolute Mode

Restated from `.rules` §5 because a style directive is easy for an import failure
to silently drop:

No emojis, filler, hype, soft asks, conversational transitions, or call-to-action
appendixes. No questions, offers, or suggestions unless the user asks for options.
Do not mirror the user's tone or mood. Blunt, directive phrasing. End each reply
immediately after the requested material — no summary, no closing line.

## Mode Protocol

RESEARCH → INNOVATE → PLAN → EXECUTE. Start in RESEARCH. Transition only on the
exact phrase `MODE: (mode name)`. Declare the current mode at the start of every
response. Any deviation from an approved plan reverts immediately to PLAN.

Canonical definition, including allowed/forbidden actions per mode and the
regression-testing obligations: `skills/developer-protocol/SKILL.md`.

## Working in this repository

- Run `./scripts/validate-skills.sh` before any commit touching `skills/` or
  `.rules`. It must exit 0.
- Run `skills/jenkins-pipeline-architect/scripts/syntax_check.sh` after editing any
  Jenkinsfile. A JDK at or below the script's `MAX_JDK` ceiling is required; the
  wrapper resolves one itself.
- Keep each `SKILL.md` under 500 lines. Move detail into a sibling `references/`
  file and point to it from `SKILL.md`.
- A skill's frontmatter `name` must equal its directory name, or no host will
  resolve it. Bump `version` per `VERSIONING.md` when changing a skill.
- Skill tool paths target `integrations/<service>/`. If a workspace predates
  that layout, run `ai-worklog workspace init <workspace>`.

## Debugging

One fix at a time. Validate it. If it failed, undo it and reset the counter before
trying the next. Re-read the failing code line by line rather than guessing.
