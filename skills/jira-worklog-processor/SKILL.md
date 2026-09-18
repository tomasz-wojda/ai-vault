---
name: jira-worklog-processor
version: "1.1.6"
description: >-
  Process JIRA tickets into structured worklog files following a multi-phase
  research-first workflow. Extends devops-daily-protocol with content generation
  patterns (FINDINGS, solution options, gap analysis, phased action plans).
  Also handles PR reviews by comparing diffs against worklog plans.
  Use when the user picks up a JIRA ticket, asks to create a worklog,
  references ticket-pickup.prompt, says "pull up TICKET-KEY", says "review this PR",
  says "review PR #N", or starts daily DevOps work on a ticket.
---

# JIRA Worklog Processor

Extends the `devops-daily-protocol` skill (from `repos/ai-vault`) with **content
generation patterns** — how to structure findings, write solution options, build
phased action plans, and manage cross-ticket investigations.

## Relationship to ai-vault Skills

| Skill | Source | What it covers |
|-------|--------|----------------|
| `devops-daily-protocol` | `skills/devops-daily-protocol/` | Lifecycle shell: Preflight → Day Start → Pickup → Investigation → Delivery → Done → Day End. Tool contracts and Write Gates. |
| `developer-protocol` | `skills/developer-protocol/` | Mode discipline: RESEARCH → INNOVATE → PLAN → EXECUTE. Transition rules. Regression testing. |
| `jenkins-pipeline-architect` | `skills/jenkins-pipeline-architect/` | Jenkins scripted pipelines. JIRA notification from CI/CD (`postJiraComment`). Syntax validation. |
| **this skill** | `skills/jira-worklog-processor/` | **Content generation**: how to write each worklog section. FINDINGS patterns (architecture, audit, gap, inventory). Solution option format. Gate-based action plans. Cross-ticket references. Worklog template (`worklog.template`). |

This skill does NOT duplicate the lifecycle/tool/safety rules from `devops-daily-protocol` —
it layers content quality patterns on top. When both skills are active, `devops-daily-protocol`
governs *when* and *how* to create/update files; this skill governs *what goes inside them*.

For full interaction details, see the master [Cross-Skill Integration Guide](../CROSS_SKILL_INTEGRATION.md).


## Workspace Dependencies

Required in the workspace (NOT in ai-vault — workspace-specific):

```
worklog/                                # Active worklog files
worklog/done/                           # Archive
integrations/                           # Service connectivity hub (12 services)
integrations/jira/                      #   jira.properties + jira-operator.json
integrations/newrelic/                  #   newrelic.properties (profile-scoped API keys)
integrations/aws/                       #   AWS profile files per account
integrations/eks/                       #   EKS context files per cluster
integrations/jenkins/                   #   Jenkins credentials
integrations/github/                    #   GitHub tokens
integrations/argocd/                    #   Argo CD credentials
integrations/artifactory/               #   Artifactory credentials
integrations/automox/                   #   automox.properties (profile-scoped) + token
integrations/ssh/                       #   SSH configs / jump hosts
integrations/snow/                      #   ServiceNow session cookie
integrations/datadog/                   #   Datadog API keys
.ai-worklog/config.json                 # Framework workspace configuration
.ai-worklog/state/<TICKET-KEY>.json     # Machine-readable ticket lifecycle
.ai-worklog/evidence/                   # Redacted diagnostic evidence
integrations/eks/monitor_commands.txt    # kubectl diagnostic patterns
tmp/                                    # Per-ticket scratch artifacts
repos/ai-memory-ingester/data/journal.db # Authoritative turn journal (SQLite)
prompt.log                              # Shadow audit trail during rollback (append-only)
```

Credential files are never committed and never read for their values. If
`integrations/` is absent, the workspace predates this layout — run
`ai-worklog workspace init <workspace>` first, then apply it through a Write Gate.
See [worklog-reference.md](worklog-reference.md) § "Interface Directory".

The `ticket-pickup.prompt` template ships with this skill at [ticket-pickup.prompt](ticket-pickup.prompt).

See [worklog-reference.md](worklog-reference.md) § "Interface Directory" for full service inventory.

## Quick Start — Default Prompt

This skill ships with a [ticket-pickup.prompt](ticket-pickup.prompt) template containing `{TICKET_KEY}`
as a placeholder. The agent never edits this file — it reads it as an instruction template.

### Trigger Patterns

| User says | Behavior |
|-----------|----------|
| "pull up KD-1234" | Full pipeline: RESEARCH → INNOVATE → PLAN. Read `ticket-pickup.prompt`, substitute `{TICKET_KEY}` with KD-1234, execute all steps. |
| "research KD-1234" | Stop after Phase 2 (FINDINGS only). No solutions or plan. |
| "review PR #123" | PR review workflow (see PR Review section). |
| "PR #123 merged" | Merge follow-up: `[~]` → `[x]` in PROPOSED ACTIONS (see PR Review section). |

### Full Pipeline Steps (triggered by "pull up")

1. Extract `TICKET-KEY` from user input
2. Read [ticket-pickup.prompt](ticket-pickup.prompt), substitute `{TICKET_KEY}`
3. Fetch the ticket via JIRA CLI
4. Check for existing worklog in `worklog/` and `worklog/done/`
5. Create `worklog/YYYY-MM-DD_<TICKET-KEY>.log` from [worklog.template](worklog.template)
6. Populate TICKET header from JIRA response
7. RESEARCH — deep-dive into repos, infra, prior worklogs → FINDINGS, REFERENCED REPOSITORIES
8. INNOVATE — propose solution options (A/B/C/D) with pros/cons → PROPOSED SOLUTIONS, RISK CONSIDERATIONS
9. PLAN — detailed action checklist with phases/gates → PROPOSED ACTIONS
10. Initialize ACTION LOG, STATUS, TIME LOGGED
11. Rename session tab to just the ticket number

## Default Prompt Lifecycle

The `ticket-pickup.prompt` file is a **static template** — the agent never modifies it.

| Aspect | Behavior |
|--------|----------|
| Ownership | User-maintained. Agent reads only. |
| Placeholder | `{TICKET_KEY}` — resolved at runtime from what the user types in chat, not from editing the file. |
| After worklog creation | No change. The template stays as-is with `{TICKET_KEY}`. |
| Multi-ticket sessions | User types the next ticket key directly in chat. The trigger patterns table handles resolution. |
| Location | Ships with this skill at [ticket-pickup.prompt](ticket-pickup.prompt). Also kept at workspace root for quick reference. |

The file exists so new sessions can reference it as a startup instruction set. The `{TICKET_KEY}` placeholder is never literally written anywhere — it is always substituted in-memory when the agent reads the template.

## Safety Rules

All operations are **read-only by default**. Any write requires the Write Gate Protocol.

Write operations: creating/editing files, HTTP POST/PUT/DELETE, git commits/pushes.
Read operations (always allowed): JIRA CLI, New Relic operator reads, file reads, kubectl read-only.

The Write Gate Protocol itself — its five steps and the required PREVIEW
formats — is owned and specified by `devops-daily-protocol`; see
[its SKILL.md](../devops-daily-protocol/SKILL.md) § "Write Gate Protocol". Every
write named in this skill routes through that gate, including worklog creation,
section updates, `PR.log` appends and checklist transitions.

The gate's WAIT step is a safety requirement and is not suspended by the
response-style directive in `.rules` §5. See
[CROSS_SKILL_INTEGRATION.md](../CROSS_SKILL_INTEGRATION.md) R-05, R-06 and R-23.

## Available Tools

| Tool | Path | Key Commands |
|------|------|-------------|
| JIRA CLI | `ai-worklog service jira` | `summary`, `ticket <KEY>`, `rejected`, `reporter <NAME>`, `tempo [DATE]`, `verify [DATE]`, `whoami`; `log-time` is dry-run unless Write Gate authorizes `--apply` |
| New Relic operator | `ai-worklog service newrelic` | Read actions include `profiles`, `applications`, `application <ID>`, `hosts <ID>`, `deployments <ID>`, `violations`, `alert-conditions`, `nrql`; mutations and `dashboard-export --apply` require Write Gate |
| Jenkins operator | `ai-worklog service jenkins` | 14 read actions grouped as controller (`controllers`, `health`, `whoami`, `nodes`, `queue`), jobs (`jobs`, `job`, `seed`, `views`), builds (`artifacts`), config (`plugins`, `credentials`, `credential-domains`) and `syntax-check`; `download-artifact` requires Write Gate and `--apply` |
| Automox operator | `ai-worklog service automox` | 14 read actions including `profiles`, `orgs`, `groups`, `devices`, `device <ID>`, `device-packages`, `activity`, `patch-summary`, `policies`, `policy`, `policy-stats`, `device-queue`; `policy-run`, `worklet-create`, `policy-delete`, `device-move` and `policy-add-group` require Write Gate and `--apply` |
| Artifactory operator | `ai-worklog service artifactory` | Read-only `profiles`, `status`, `auth-test`, `repositories`, `artifacts`, `artifact`, and bounded text `manifest`; use the operator instead of reading credential files |
| AI Worklog | `ai-worklog` on PATH | `preflight`, `ticket prepare`, `state`, `diag`, `delivery`, `closeout` |
| Worklog template | [worklog.template](worklog.template) | Section scaffold (ships with this skill) |
| kubectl patterns | `integrations/eks/monitor_commands.txt` | Cluster diagnostics |

## Phase 1: Ticket Pickup

0. Read [ticket-pickup.prompt](ticket-pickup.prompt) template. Extract `TICKET-KEY` from user input.
   Substitute `{TICKET_KEY}` in the template. Follow all steps described in the template.
1. Run `ai-worklog preflight --ticket <TICKET-KEY>` and `ai-worklog ticket prepare <TICKET-KEY>`
2. Run `ai-worklog service jira ticket <TICKET-KEY>` to fetch full ticket detail
3. Parse output: key, summary, status, type, priority, project, assignee, reporter,
   components, labels, epic, created, updated, description, comments, linked issues, time spent
4. **Reopened ticket check**: look for `worklog/done/*_<TICKET-KEY>*.log`
   - If found: "Previous worklog found in `done/`: [list]. Copy back to `worklog/`?"
   - On approval: copy back, skip fresh creation
5. **WRITE GATE**: Create the worklog and initialize structured ticket state
   - Read [worklog.template](worklog.template) for structure
   - Pre-populate TICKET header from JIRA fields
   - Include Comments and Linked Issues if present
   - Include Time Spent from Tempo data
6. If ticket has related tickets, add a RELATED TICKET section after the header

## Phase 2: Research (FINDINGS)

Systematically investigate the ticket scope. This phase is **read-only**.

### Investigation Checklist

- [ ] Read all JIRA comments and linked issues
- [ ] Identify referenced repositories — clone or browse under `repos/`
- [ ] Check prior worklogs for related tickets
- [ ] Check `tmp/` for existing artifacts on this or related tickets
- [ ] For infrastructure tickets: SSH manifests, AWS console, kubectl, NR queries
- [ ] For CI/CD tickets: Jenkins configs, GHA workflows, Helm values
- [ ] For monitoring tickets: NRQL queries, NR app/host/alert data
- [ ] Run catalog-matched `ai-worklog diag` packs and reference evidence in FINDINGS

### Findings Format

Number each finding. Use dotted sub-sections for detail:

```
1. FINDING TITLE
.................................................................
   Detailed observations, data tables, code paths, live state.
```

### Referenced Repositories

If the ticket involves code repos, add after TICKET header:

```
================================================================================
  REFERENCED REPOSITORIES
================================================================================

1. REPO-NAME (GitHub: org)
   - Role/purpose in this ticket
```

## Phase 3: Innovate (PROPOSED SOLUTIONS)

Brainstorm solution options labeled A through E. For each:

```
OPTION A: "SHORT LABEL" (RECOMMENDED if applicable)
.................................................................
   Description of approach.

   PROS: ...
   CONS: ...
```

Always include a RECOMMENDATION line at the end comparing options.

### Risk Considerations

For each option or cross-cutting concern:

```
1. RISK TITLE
   Description. Mitigation strategy.
```

## Phase 4: Plan (PROPOSED ACTIONS)

Create phased action items with checkbox tracking:

```
PREP (done YYYY-MM-DD)
[x] Completed preparation step
[x] Another completed step

PHASE 1 — Description
[ ] Action item with specific details
[ ] Another action item

PHASE 2 — Description
[ ] Action item
```

For complex tickets, use gates (G0 read-only → G1 config → G2 bake → G3 infra → G4 close):

| Gate | Purpose | Rule |
|------|---------|------|
| G0 | Read-only prerequisites | No mutations, no pushes |
| G1 | Config alignment | Template sync, diff review |
| G2 | Build/bake | AMI, image, artifact creation |
| G3 | Infrastructure change | CHG required, rollback defined |
| G4 | Close-out | Jira comment, Tempo, move to done/ |

## Phase 5: Execute & Track

### ACTION LOG

Append timestamped entries as work progresses:

```
YYYY-MM-DD HH:MM - Description of action taken
                   Additional detail, PR links, test results
```

### STATUS

Always maintain current state:

```
CURRENT: <phase description>
         <blockers or next steps>
         <pending decisions>
```

Valid status labels: RESEARCH, INNOVATE, PLAN, EXECUTE, BLOCKED, PARKED, DONE

### Structured State

Preview every `ai-worklog state` mutation, apply it only after a Write Gate, then
run `ai-worklog delivery status <TICKET-KEY>`. Mirror material lifecycle changes
into DELIVERY STATE and ACTION LOG. Never hand-edit `.ai-worklog/state/*.json`.

### Scratch Artifacts in tmp/

For scripts, SSH outputs, plans, data files:

- Create `tmp/<TICKET-KEY>/` folder
- Name scripts with ticket prefix: `<TICKET-KEY>_description.sh`
- SSH evidence: `tmp/<TICKET-KEY>/ssh/<role>/manifest.txt`
- Plans: `tmp/<TICKET-KEY>/plan-description.md`
- Reference from worklog FINDINGS/ACTION LOG

## PR Review Workflow

Triggered by "review this PR", "review PR #N", or a GitHub PR URL.

### PROPOSED ACTIONS Checkbox States

| Marker | Meaning | When applied |
|--------|---------|--------------|
| `[ ]` | Not started | Default at plan time |
| `[~]` | In PR — diff covers this item, PR still open | PR review (step 9 below) |
| `[x]` | Done — change landed | PR merged (see Merge Follow-up below) |

Never mark `[x]` during review. Review marks covered items `[~]` only.

### Flow

1. **Extract PR metadata** — use `gh pr view <URL-or-number> --json title,body,author,baseRefName,headRefName,files,reviews,reviewRequests,state`
2. **Identify the ticket key** — parse from PR title, branch name, or body (patterns: `KD-1234`, `DEVOPS-123`, `CWP-1234`)
3. **Find the worklog** — search `worklog/*_<TICKET-KEY>.log` and `worklog/done/*_<TICKET-KEY>.log`
4. **Read the worklog** — extract PROPOSED ACTIONS / IMPLEMENTATION CHECKLIST / PROPOSED SOLUTIONS to understand what the PR *should* be doing
5. **Fetch the PR diff** — `gh pr diff <number>`
6. **Compare diff against worklog plan** — for each changed file, check:
   - Does this change match a checklist item? Candidate for `[~]` (not `[x]`).
   - Are there changes NOT in the plan? Flag as out-of-scope.
   - Are there checklist items NOT covered by the diff? Leave as `[ ]`, flag as missing.
7. **Produce structured review output** — see format below
8. **WRITE GATE**: Append entry to `PR.log`
9. **WRITE GATE**: Update worklog PROPOSED ACTIONS — change matched `[ ]` items to `[~]`; append PR link on the same line
10. **Update worklog ACTION LOG** — note the PR review with PR number, repo, outcome, count of `[~]` items

### Merge Follow-up

Triggered when user says "PR #N merged", or when `gh pr view` shows `state: MERGED`.

1. Confirm PR is merged via `gh pr view`
2. **WRITE GATE**: In worklog PROPOSED ACTIONS, change `[~]` items tied to that PR from `[~]` to `[x]`
3. Update ACTION LOG: `YYYY-MM-DD HH:MM - PR #N merged (org/repo): N checklist items marked [x]`
4. **WRITE GATE**: Append merge note to `PR.log` entry (or add short follow-up block under the original review)

### PR.log Entry Format

An entry has a fixed head, a fixed tail, and a freely composed middle. Only the
head, `METADATA` and `OBSERVATIONS` appear in every entry.

**Required — every entry:**

```
--- YYYY-MM-DDTHH:MM ---
PR #N | org/repo
URL: https://github.com/org/repo/pull/N

METADATA:
  Title:    <title>
  Author:   <name> (<username>)
  Branch:   <head> → <base>
  Created:  <ISO timestamp>
  State:    <state>, <mergeable>
  Labels:   <labels or "none">
  CI:       <check status summary>
  Reviews:  <review status>
  Requested reviewers: <list>

CHANGED FILES (N files, +X/-Y):
  1. path/to/file [MODIFIED|ADDED|DELETED]
     - Description of change

OBSERVATIONS:
  1. Numbered observations about the PR
  2. Risk flags, missing tests, config concerns
  3. Comparison to worklog PROPOSED SOLUTIONS
```

`OBSERVATIONS` is always last of the analysis sections. Anything appended after
it is a record of action taken, not analysis.

**Conditional — when a ticket key resolves to a worklog.** Place before
`OBSERVATIONS`. Omit per "Review Without Worklog" below when none is found:

```
WORKLOG CROSS-REFERENCE: <TICKET-KEY>
  Worklog: worklog/YYYY-MM-DD_<TICKET-KEY>.log
  Checklist coverage:
    [~] Step N — covered by file.ext changes (PR open)
    [ ] Step K — NOT in this PR (still pending)
  Out-of-scope changes:
    - file3.ext — not mentioned in worklog plan
```

**Optional — named context sections.** Between `CHANGED FILES` and
`OBSERVATIONS`, add as many upper-case sections as the PR warrants, named for
what they hold. Existing entries use `CONTEXT`, `SCOPE`, `CHANGES`,
`REFERENCES`, `JOB CONTEXT`, `BREAKING CHANGES`, `COMMIT HISTORY`,
`CI FAILURES`, `REFERENCED MODULE` (external dependency tags and changelogs) and
`SCALING COMPARISON` (before/after metrics when resource configs change), among
others. This is deliberate: a Helm chart bump and a Jenkinsfile
refactor do not summarise the same way. Do not invent a section that duplicates
`OBSERVATIONS`.

**Appended by `pr-review-comments`** when findings were posted to GitHub. That
skill owns the content of these blocks; this document fixes only their position,
which is after `OBSERVATIONS`:

```
POSTED COMMENTS:
  1. <severity> — <one-line verdict>
     <path>:<line or start-end>
     https://github.com/<org>/<repo>/pull/<N>#discussion_r<id>
     Suggestion: yes|no   From: OBSERVATION <n>

NOT POSTED (kept in chat):
  - <finding> — <which evidence bar it failed>

POSTED COMMENTS FOLLOW-UP (YYYY-MM-DDTHH:MM):
  1. r<id> — suggestion applied in <sha>
  2. r<id> — still open at merge
```

**Separator.** End an entry with an 80-character `=` rule. It is a visual aid,
not a delimiter — some entries lack it, so **parse by splitting on the
`--- YYYY-MM-DDTHH:MM ---` header, never on the rule.**

```
================================================================================
```

### Review Without Worklog

If no worklog is found for the ticket key (or no ticket key in the PR):
- Skip WORKLOG CROSS-REFERENCE section
- Review the PR on its own merits: correctness, risk, scope, missing tests
- Note in OBSERVATIONS: "No worklog found for this PR"

## Phase 6: Completion

1. Run `ai-worklog closeout report <TICKET-KEY>`
2. Update STATUS to DONE
3. Ask user for time estimate (or propose based on session complexity)
4. Run `ai-worklog service jira tempo` to check today's hours
5. Run `ai-worklog service jira log-time <KEY> <DATE> <SECONDS> <COMMENT>`, then use a **WRITE GATE** before repeating it with `--apply`
6. Run `ai-worklog service jira verify` to confirm
7. Update TIME LOGGED section in worklog
8. **WRITE GATE**: Move worklog files to `worklog/done/` and update closeout state

## File Naming Conventions

```
worklog/YYYY-MM-DD_TICKET-KEY.log              # primary worklog
worklog/YYYY-MM-DD_TICKET-KEY_jira.log         # raw JIRA dump
worklog/YYYY-MM-DD_TICKET-KEY_suffix.log       # sub-investigation
worklog/done/YYYY-MM-DD_TICKET-KEY.log         # archived completed
tmp/TICKET-KEY/                                # scratch artifacts
tmp/TICKET-KEY_script.sh                       # standalone scripts
```

## Cross-Ticket References

When a ticket relates to another:
- Add RELATED TICKET section with status summary from the other worklog
- Note blocking/non-blocking dependency
- Reference the other worklog path: `worklog/YYYY-MM-DD_<OTHER-KEY>.log`

## Prompt Logging

After every interaction, follow
[worklog-chat-memory](../worklog-chat-memory/SKILL.md) § "Record turn events".
Include active ticket keys in the JSON `tickets` array when known. Write
`journal.db` synchronously first with exact user text and exact final assistant
response. Only after success append the shadow audit entry to `prompt.log` at
workspace root:

```
--- PROMPT LOG ENTRY ---
TIMESTAMP: YYYY-MM-DD
USER: <exact user prompt or concise summary>
ASSISTANT: <mode> — <exact final assistant response or concise outcome>
  <files created, commands run, ticket keys, key details>
--- END PROMPT LOG ENTRY ---
```

If `record-event` fails, leave the failure visible and do not append
`prompt.log`.

## Mode Discipline

Follow the developer protocol modes. Declare mode at the start of every response:

| Mode | Allowed | Forbidden |
|------|---------|-----------|
| RESEARCH | Read files, JIRA/New Relic operator reads, questions | Suggestions, planning, implementation |
| INNOVATE | Options, pros/cons, discussion | Detailed plans, code, implementation |
| PLAN | File paths, checklists, specs | Code implementation |
| EXECUTE | Exactly what the plan says | Deviations, creative additions |

Transition only on explicit `MODE: <name>` from user.

## Additional Resources

- For detailed worklog section specifications and content patterns, see [worklog-reference.md](worklog-reference.md)
- For concrete examples from completed tickets, see [examples.md](examples.md)
