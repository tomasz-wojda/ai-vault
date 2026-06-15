---
name: jira-worklog-processor
description: >-
  Process JIRA tickets into structured worklog files following a multi-phase
  research-first workflow. Extends devops-daily-protocol with content generation
  patterns (FINDINGS, solution options, gap analysis, phased action plans).
  Also handles PR reviews by comparing diffs against worklog plans.
  Use when the user picks up a JIRA ticket, asks to create a worklog,
  references default_prompt, says "pull up TICKET-KEY", says "review this PR",
  says "review PR #N", or starts daily DevOps work on a ticket.
---

# JIRA Worklog Processor

Extends the `devops-daily-protocol` skill (from `repos/ai-vault`) with **content
generation patterns** — how to structure findings, write solution options, build
phased action plans, and manage cross-ticket investigations.

## Relationship to ai-vault Skills

| Skill | Source | What it covers |
|-------|--------|----------------|
| `devops-daily-protocol` | `repos/ai-vault/skills/` | Lifecycle shell: Day Start → Pickup → Investigation → Done → Day End. Tool contracts (JIRA CLI, NR CLI). Write Gate Protocol. Tempo API. prompt.log. |
| `developer-protocol` | `repos/ai-vault/skills/` | Mode discipline: RESEARCH → INNOVATE → PLAN → EXECUTE. Transition rules. Regression testing. |
| `jenkins-pipeline-architect` | `repos/ai-vault/skills/` | Jenkins scripted pipelines. JIRA notification from CI/CD (`postJiraComment`). Syntax validation. |
| **this skill** | `tmp/worklog_skill/` | **Content generation**: how to write each worklog section. FINDINGS patterns (architecture, audit, gap, inventory). Solution option format. Gate-based action plans. Cross-ticket references. tmp/ artifact management. Real examples from 40+ tickets. |

This skill does NOT duplicate the lifecycle/tool/safety rules from `devops-daily-protocol` —
it layers content quality patterns on top. When both skills are active, `devops-daily-protocol`
governs *when* and *how* to create/update files; this skill governs *what goes inside them*.

## Workspace Dependencies

Required in the workspace (NOT in ai-vault — workspace-specific):

```
worklog/done/                           # Archive for completed tickets
worklog/interface/                      # Service connectivity hub
worklog/interface/jira/credentials      # JIRA + Tempo tokens (never commit)
worklog/interface/jira/jira-ticket-info.sh  # JIRA CLI (5 modes)
worklog/interface/newrelic/credentials  # NR API keys (never commit)
worklog/interface/newrelic/newrelic-info.sh  # NR CLI (6 modes)
worklog/interface/aws/                  # AWS profile files per account
worklog/interface/eks/                  # EKS context files per cluster
worklog/interface/snow/cookie           # ServiceNow session cookie
zzzrecycle/monitor_commands.txt         # kubectl diagnostic patterns
prompt.log                              # Session audit trail (append-only)
```

The `default_prompt` template ships with this skill at [default_prompt](default_prompt).

See [worklog-reference.md](worklog-reference.md) § "Interface Directory" for full service inventory.

## Quick Start — Default Prompt

This skill ships with a [default_prompt](default_prompt) template containing `{TICKET_KEY}`
as a placeholder. The agent never edits this file — it reads it as an instruction template.

### Trigger Patterns

| User says | Behavior |
|-----------|----------|
| "pull up KD-1234" | Full pipeline: RESEARCH → INNOVATE → PLAN. Read `default_prompt`, substitute `{TICKET_KEY}` with KD-1234, execute all steps. |
| "research KD-1234" | Stop after Phase 2 (FINDINGS only). No solutions or plan. |
| "review PR #123" | PR review workflow (see PR Review section). |

### Full Pipeline Steps (triggered by "pull up")

1. Extract `TICKET-KEY` from user input
2. Read [default_prompt](default_prompt), substitute `{TICKET_KEY}`
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

The `default_prompt` file is a **static template** — the agent never modifies it.

| Aspect | Behavior |
|--------|----------|
| Ownership | User-maintained. Agent reads only. |
| Placeholder | `{TICKET_KEY}` — resolved at runtime from what the user types in chat, not from editing the file. |
| After worklog creation | No change. The template stays as-is with `{TICKET_KEY}`. |
| Multi-ticket sessions | User types the next ticket key directly in chat. The trigger patterns table handles resolution. |
| Location | Ships with this skill at [default_prompt](default_prompt). Also kept at workspace root for quick reference. |

The file exists so new sessions can reference it as a startup instruction set. The `{TICKET_KEY}` placeholder is never literally written anywhere — it is always substituted in-memory when the agent reads the template.

## Safety Rules

All operations are **read-only by default**. Any write requires the Write Gate Protocol.

Write operations: creating/editing files, HTTP POST/PUT/DELETE, git commits/pushes.
Read operations (always allowed): JIRA CLI, NR CLI, file reads, kubectl read-only.

### Write Gate Protocol

1. **ANNOUNCE** the operation type
2. **PREVIEW** full content (file content, API payload, git command)
3. **WAIT** — "Proceed? (yes/no)"
4. **EXECUTE** only after user confirms
5. **VERIFY** success (re-read file, re-run verify)

## Available Tools

| Tool | Path | Key Commands |
|------|------|-------------|
| JIRA CLI | `jira/jira-ticket-info.sh` | `summary`, `<KEY>`, `rejected`, `tempo [DATE]`, `verify [DATE]` |
| New Relic CLI | `newrelic/newrelic-info.sh` | `apps`, `app <ID>`, `hosts <ID>`, `deployments <ID>`, `alerts <ID>`, `violations` |
| Worklog template | [worklog.template](worklog.template) | Section scaffold (ships with this skill) |
| kubectl patterns | `zzzrecycle/monitor_commands.txt` | Cluster diagnostics |

## Phase 1: Ticket Pickup

0. Read [default_prompt](default_prompt) template. Extract `TICKET-KEY` from user input.
   Substitute `{TICKET_KEY}` in the template. Follow all steps described in the template.
1. Run `jira/jira-ticket-info.sh <TICKET-KEY>` to fetch full ticket detail
2. Parse output: key, summary, status, type, priority, project, assignee, reporter,
   components, labels, epic, created, updated, description, comments, linked issues, time spent
3. **Reopened ticket check**: look for `worklog/done/*_<TICKET-KEY>*.log`
   - If found: "Previous worklog found in `done/`: [list]. Copy back to `worklog/`?"
   - On approval: copy back, skip fresh creation
4. **WRITE GATE**: Create `worklog/YYYY-MM-DD_<TICKET-KEY>.log`
   - Read [worklog.template](worklog.template) for structure
   - Pre-populate TICKET header from JIRA fields
   - Include Comments and Linked Issues if present
   - Include Time Spent from Tempo data
5. If ticket has related tickets, add a RELATED TICKET section after the header

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

### Scratch Artifacts in tmp/

For scripts, SSH outputs, plans, data files:

- Create `tmp/<TICKET-KEY>/` folder
- Name scripts with ticket prefix: `<TICKET-KEY>_description.sh`
- SSH evidence: `tmp/<TICKET-KEY>/ssh/<role>/manifest.txt`
- Plans: `tmp/<TICKET-KEY>/plan-description.md`
- Reference from worklog FINDINGS/ACTION LOG

## PR Review Workflow

Triggered by "review this PR", "review PR #N", or a GitHub PR URL.

### Flow

1. **Extract PR metadata** — use `gh pr view <URL-or-number> --json title,body,author,baseRefName,headRefName,files,reviews,reviewRequests`
2. **Identify the ticket key** — parse from PR title, branch name, or body (patterns: `KD-1234`, `DEVOPS-123`, `CWP-1234`)
3. **Find the worklog** — search `worklog/*_<TICKET-KEY>.log` and `worklog/done/*_<TICKET-KEY>.log`
4. **Read the worklog** — extract PROPOSED ACTIONS / IMPLEMENTATION CHECKLIST / PROPOSED SOLUTIONS to understand what the PR *should* be doing
5. **Fetch the PR diff** — `gh pr diff <number>`
6. **Compare diff against worklog plan** — for each changed file, check:
   - Does this change match a checklist item? Mark it.
   - Are there changes NOT in the plan? Flag as out-of-scope.
   - Are there checklist items NOT covered by the diff? Flag as missing.
7. **Produce structured review output** — see format below
8. **WRITE GATE**: Append entry to `PR.log`
9. **Update worklog ACTION LOG** — note the PR review with PR number, repo, outcome

### PR.log Entry Format

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

WORKLOG CROSS-REFERENCE: <TICKET-KEY>
  Worklog: worklog/YYYY-MM-DD_<TICKET-KEY>.log
  Checklist coverage:
    [x] Step N — covered by file.ext changes
    [x] Step M — covered by file2.ext changes
    [ ] Step K — NOT in this PR (still pending)
  Out-of-scope changes:
    - file3.ext — not mentioned in worklog plan

OBSERVATIONS:
  1. Numbered observations about the PR
  2. Risk flags, missing tests, config concerns
  3. Comparison to worklog PROPOSED SOLUTIONS

================================================================================
```

### Review Without Worklog

If no worklog is found for the ticket key (or no ticket key in the PR):
- Skip WORKLOG CROSS-REFERENCE section
- Review the PR on its own merits: correctness, risk, scope, missing tests
- Note in OBSERVATIONS: "No worklog found for this PR"

## Phase 6: Completion

1. Update STATUS to DONE
2. Ask user for time estimate (or propose based on session complexity)
3. Run `jira/jira-ticket-info.sh tempo` to check today's hours
4. **WRITE GATE**: Log time via Tempo API
5. Run `jira/jira-ticket-info.sh verify` to confirm
6. Update TIME LOGGED section in worklog
7. **WRITE GATE**: Move worklog files to `worklog/done/`

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

After every interaction, append to `prompt.log` at workspace root:

```
--- PROMPT LOG ENTRY ---
TIMESTAMP: YYYY-MM-DD
USER: <concise summary>
ASSISTANT: <mode> — <actions taken and outcomes>
  <files created, commands run, key details>
--- END PROMPT LOG ENTRY ---
```

## Mode Discipline

Follow the developer protocol modes. Declare mode at the start of every response:

| Mode | Allowed | Forbidden |
|------|---------|-----------|
| RESEARCH | Read files, JIRA/NR CLI, questions | Suggestions, planning, implementation |
| INNOVATE | Options, pros/cons, discussion | Detailed plans, code, implementation |
| PLAN | File paths, checklists, specs | Code implementation |
| EXECUTE | Exactly what the plan says | Deviations, creative additions |

Transition only on explicit `MODE: <name>` from user.

## Additional Resources

- For detailed worklog section specifications and content patterns, see [worklog-reference.md](worklog-reference.md)
- For concrete examples from completed tickets, see [examples.md](examples.md)
