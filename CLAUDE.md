# CLAUDE.md

Claude Code equivalent of `.rules` (which Claude Code does not read). Cursor and
AntiGravity consume `.rules`; Claude Code consumes this file.

The full rule set lives in `.rules` and is imported below. The directives restated
here are the ones whose failure causes damage, so they hold even if the import does
not resolve.

@.rules

## Non-negotiables

- **Never commit or push.** After changes are applied, provide a semantic commit
  title and description. The user runs the git commands.
- **`prompt.log` is append-only.** Never overwrite it. Create it only if absent.
  Append a summary after every interaction.
- **Read before Write.** The Write tool overwrites; it does not append. If a file
  exists, read it and merge.
- **No unsolicited documentation or code comments.** Only when explicitly asked.
- **Never read a credential file for its values.** Pass the path to the consuming
  script. Applies to `**/credentials`, `**/*.properties`, `**/cookie`.
- **Jenkinsfiles use scripted pipeline syntax**, not declarative.
- If it is not in the context and the answer is unknown, say "I don't know".

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
  Jenkinsfile. JDK 17 or lower is required; the wrapper resolves it.
- Keep each `SKILL.md` under 500 lines. Move detail into a sibling `references/`
  file and point to it from `SKILL.md`.
- A skill's frontmatter `name` must equal its directory name, or no host will
  resolve it. Bump `version` per `VERSIONING.md` when changing a skill.
- Skill tool paths target `integrations/<service>/`. If a workspace predates
  that layout, run `ai-worklog workspace init <workspace>`.

## Debugging

One fix at a time. Validate it. If it failed, undo it and reset the counter before
trying the next. Re-read the failing code line by line rather than guessing.
