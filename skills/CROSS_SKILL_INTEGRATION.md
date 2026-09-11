# Cross-Skill Integration Guide

This document establishes the interaction model, handoff protocols, and unified architecture for the five skills in `ai-vault`:

1. `developer-protocol` (Mode Discipline & Execution Safety)
2. `devops-daily-protocol` (Operational Lifecycle Shell & Tool Contracts)
3. `jira-worklog-processor` (Worklog Content Generation & Structuring)
4. `jenkins-pipeline-architect` (CI/CD Pipeline & Scripted Jenkinsfile Patterns)
5. `pr-review-comments` (Evidence-Backed PR Comment Authoring & Posting)

---

## 1. The Skill Stack

Three governing layers, then two specialists invoked by surface rather than
stacked on each other:

```
┌───────────────────────────────────────────────────────────────────┐
│ Layer 1: developer-protocol                                      │
│ Governance & Mode Discipline (RESEARCH → INNOVATE → PLAN → EXECUTE)│
├───────────────────────────────────────────────────────────────────┤
│ Layer 2: devops-daily-protocol                                    │
│ Operational Shell (Day Start → Pickup → Investigation → Done)     │
├───────────────────────────────────────────────────────────────────┤
│ Layer 3: jira-worklog-processor                                   │
│ Content Engine (Header, FINDINGS, SOLUTIONS, ACTIONS, ACTION LOG)  │
├─────────────────────────────────┬─────────────────────────────────┤
│ Layer 4:                        │ Layer 5:                        │
│ jenkins-pipeline-architect      │ pr-review-comments              │
│ CI/CD Specialist                │ PR Comment Specialist           │
│ (Jenkinsfile, CPS, syntax check)│ (evidence bars, inline posting) │
└─────────────────────────────────┴─────────────────────────────────┘
```

L4 and L5 are peers. Neither constrains the other, and a session may activate
one, both, or neither.

### Layer Responsibilities

| Layer | Skill | Owns | Governs |
|-------|-------|------|---------|
| **L1** | `developer-protocol` | Mode state machine (RESEARCH/INNOVATE/PLAN/EXECUTE) | What actions are allowed at any given time |
| **L2** | `devops-daily-protocol` | Tool contracts (JIRA CLI, New Relic operator, kubectl), Write Gate Protocol, prompt.log | When and how tools are invoked, safety enforcement |
| **L3** | `jira-worklog-processor` | Worklog content patterns, worklog.template, PR.log, ticket-pickup.prompt | What goes inside worklog files, content quality |
| **L4** | `jenkins-pipeline-architect` | Jenkinsfile patterns, CPS rules, syntax_check.groovy, postJiraComment | How CI/CD pipelines are structured and validated |
| **L5** | `pr-review-comments` | Evidence bars, comment structure, severity calibration, suggestion blocks, the `POSTED COMMENTS` and `NOT POSTED` blocks of PR.log | How a review finding is proven, worded and anchored on GitHub |

### Inter-Layer Communication Rules

1. **Higher layers constrain lower layers** — L1 mode rules override L2/L3/L4/L5 actions
2. **Lower layers never override higher layers** — L4 and L5 cannot bypass L1 mode restrictions
3. **Sibling layers coordinate via handoffs** — L2↔L3, L2↔L4, L3↔L4 and L3↔L5 compose through the rules in section 2, not through direct calls
4. **All write operations route through L2** — L4 pipeline edits and L5 PR.log appends both use L2's Write Gate Protocol
5. **Specialists do not call each other** — L4 and L5 are peers; where a PR touches pipeline code, L3 sequences them (see 2.9)

---

## 2. Inter-Layer Rules

Twenty-seven rules, grouped by the concern they govern. Each states a constraint
that binds at decision time. The skill named as owner holds the canonical
statement of the rule; this document fixes how the layers compose and which rule
wins when two of them collide.

### 2.1 Mode Governance — owner `developer-protocol`

- **R-01** Every action is bound by the current mode. A session starts in RESEARCH, transitions only on the exact phrase `MODE: <name>`, and declares the active mode at the start of every response. A lower layer cannot bypass an L1 restriction.
- **R-02** Any deviation from an approved plan reverts to PLAN immediately — a failed syntax check, an unexpected API error, or an executed step that was not in the plan.
- **R-03** Read operations need no mode change and no gate: Jira and New Relic reads, file reads, `kubectl get`, and syntax validation of an unmodified file.
- **R-04** `MODE: EXECUTE` declared without a preceding PLAN is permitted, but the absence of a plan must be stated before acting on it.

### 2.2 Write Routing — owner `devops-daily-protocol`

- **R-05** Every write routes through the Write Gate: file creation and edits, HTTP POST/PUT/DELETE, git operations, Tempo submission, and `--apply` on any framework command. L3 worklog edits, L4 pipeline edits and L5 PR.log appends are not exempt.
- **R-06** The gate's five steps map onto modes — ANNOUNCE, PREVIEW and WAIT belong to PLAN; EXECUTE and VERIFY belong to EXECUTE. User approval does not substitute for `MODE: EXECUTE`.
- **R-07** One gate is active at a time. A mode switch mid-gate cancels it, and the operation is re-evaluated in the new mode.
- **R-08** Credential files are referenced by path and never read for their values, in any mode.

### 2.3 Worklog Content — owner `jira-worklog-processor`

- **R-09** Mode gates the analytical sections only: FINDINGS in RESEARCH, PROPOSED SOLUTIONS in INNOVATE, PROPOSED ACTIONS in PLAN, ACTION LOG in EXECUTE. Structural sections — TICKET header, RELATED TICKET, REFERENCED REPOSITORIES, STATUS, TIME LOGGED, DELIVERY STATE — carry no mode restriction and are governed by R-05 alone. Ticket pickup therefore writes the header while in RESEARCH, and closeout writes TIME LOGGED and STATUS while in EXECUTE.
- **R-10** FINDINGS hold observations only. A fix identified during RESEARCH is held for INNOVATE rather than recorded as a finding.
- **R-11** Output too large for the worklog goes to `worklog/YYYY-MM-DD_<KEY>_<suffix>_raw.log` and is referenced from FINDINGS by path. `_raw.log` files are excluded from `verify` scanning and Tempo correlation.
- **R-12** A plan that modifies an existing script or tool must carry regression test steps for every existing command or feature it touches. Skipping is permitted only with a documented reason, such as execution exceeding 60 seconds.
- **R-13** PR review marks covered checklist items `[~]`, never `[x]`; `[x]` is applied only once the PR merges. Changes outside the plan are flagged, not corrected — correcting them requires INNOVATE.
- **R-14** One worklog per ticket. Related tickets are linked through RELATED TICKET sections rather than merged. A ticket reopened from `done/` is either copied back or started fresh under a new date prefix, never both.

### 2.4 Pipeline Work — owner `jenkins-pipeline-architect`

- **R-15** Pipeline code is written only in EXECUTE. Creation and modification both pass through PLAN first, including single-line changes and CPS refactoring.
- **R-16** `scripts/syntax_check.sh` runs after every pipeline edit and is mandatory; failure reverts to PLAN per R-02. `ai-worklog service jenkins syntax-check` is a front end to that same script, not a second implementation, so either entry point discharges this rule. It validates Groovy grammar only, so a pass does not mean the pipeline works — that limitation belongs in the ACTION LOG. The wrapper resolves a JDK at or below the `MAX_JDK` ceiling set in that script; invoking `syntax_check.groovy` directly under a newer JDK fails with `Unsupported class file major version <N>`.
- **R-17** A `vars/*.groovy` change affects every consumer of the shared library and requires regression coverage for all of them within the same change.

### 2.5 Framework Integration — owner `ai-worklog-framework`

- **R-18** `ai-worklog preflight` runs at session start and `preflight --ticket <KEY>` at pickup. BLOCKED halts dependent operations; DEGRADED is reported and work continues.
- **R-19** `ticket prepare` is the source of the worklog history, repositories, delivery paths and preparation gaps handed to L3.
- **R-20** State mutations are previewed in PLAN, applied with `--apply` in EXECUTE, and verified read-only through `delivery status`. `.ai-worklog/state/*.json` is never hand-edited.
- **R-21** Structured JSON leads automation and the worklog leads narrative. Where the two contradict, the contradiction is surfaced rather than silently overwritten. Jira remains the authority on board state.
- **R-22** `closeout report` precedes the Tempo and archival Write Gates. Evidence produced by `diag run` is redacted and referenced by bundle path from FINDINGS or ACTION LOG.

### 2.6 Precedence

- **R-23** Where rules conflict, precedence runs safety, then mode, then content, then style. Concretely: the Write Gate's WAIT step is a safety requirement and is outside the scope of the `.rules` §5 prohibition on questions. A confirmation prompt before a write is mandatory regardless of response-style directives.

### 2.7 Runtime Precondition

- **R-24** The `ai-worklog service` operators — `jira`, `jenkins`, `newrelic`, `automox` — exist only in the Groovy runtime. Under the Python runtime the command is rejected before reaching an operator, with `invalid choice: 'service'`, which removes every L2 tool contract at once. Every other framework command (R-18 to R-22) works under both runtimes. The runtime resolves from `--runtime`, then `AI_WORKLOG_RUNTIME`, then the `runtime` key in `~/.ai-worklog/config.json`, defaulting to `groovy` when no config file exists. Verify with `ai-worklog config runtime` before relying on any tool contract.

### 2.8 PR Comment Authoring — owner `pr-review-comments`

- **R-25** A finding reaches the pull request only once it is proven by a read-only execution, bounded by a statement of what it cannot affect, and measured for how often it fires. A finding failing any of the three goes to chat, never to the PR. Evidence is never produced by mutating the target system; if a proof would require a write, say so and stop.
- **R-26** One inline comment per defect, anchored to its line or contiguous line range at the pinned head SHA — re-fetched, since the author may have pushed. A defect recurring across non-contiguous regions is still one comment, not several. Top-level comments listing multiple findings are not used.
- **R-27** L5 contributes the `POSTED COMMENTS` and `NOT POSTED` blocks to `PR.log`; L3 owns the entry format and L2 gates the append, so L5 never redefines the entry. Posting the comment is the only write L5 makes to the pull request.

### 2.9 Composite Sequences

The rules above compose into three recurring sequences. Each step names the
owning layer.

**Full ticket lifecycle.** L2 preflight (R-18) → L2 fetches the ticket → L3
creates the worklog from `worklog.template` and fills the header (R-09) → L2
investigation tools run, L4 joins for any Jenkins surface → L3 formats FINDINGS
(R-10, R-11) → `MODE: INNOVATE`, L3 writes PROPOSED SOLUTIONS → `MODE: PLAN`,
L3 writes PROPOSED ACTIONS including regression steps (R-12) and any syntax-check
gate (R-16) → `MODE: EXECUTE`, L2 gates each write (R-05) while L3 appends to the
ACTION LOG → L2 runs `closeout report` (R-22), submits Tempo, and archives to
`worklog/done/`.

**PR review.** RESEARCH throughout the analysis. L3 reads PR metadata and diff,
locates the worklog for the ticket key, and compares the diff against PROPOSED
ACTIONS. If the diff touches a Jenkinsfile or `vars/*.groovy`, L4 checks CPS
rules and flags shared-library impact (R-17). L3 then takes two gated writes: the
`PR.log` entry, and the checklist transition to `[~]` (R-13). Where the user asks
for a finding to be raised on GitHub, L5 takes over: it proves the finding against
the live system, anchors one comment per defect at the pinned head SHA (R-25,
R-26), and contributes its `POSTED COMMENTS` and `NOT POSTED` blocks to the same
`PR.log` entry (R-27).

**Incident response.** RESEARCH throughout triage. L2 queries New Relic
violations, issues and deployments, plus `kubectl`, and runs any catalog-matched
`diag` pack. Where a deployment correlates with the alert, L4 inspects the
deploying pipeline — correlation is recorded with its uncertainty, not as cause.
L3 opens an incident worklog with FINDINGS and `_raw.log` companions (R-11).
Mitigation then follows the mode sequence from INNOVATE onward.

---

## 3. Data Flow & Workspace Artifact Ownership

```
[User Request]
      │
      ▼
┌───────────────────────────┐
│ developer-protocol        │  <-- Enforces Mode (e.g. RESEARCH)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐     Reads/Writes     ┌───────────────────────────┐
│ devops-daily-protocol     │ ──────────────────> │ integrations/             │ (JIRA CLI, New Relic operator)
└─────────────┬─────────────┘                      └───────────────────────────┘
              │ Hand-off
              ▼
┌───────────────────────────┐     Reads Template   ┌───────────────────────────┐
│ jira-worklog-processor    │ ──────────────────> │ skills/.../worklog.template│
└─────────────┬─────────────┘                      └───────────────────────────┘
              │ Formats & Saves
              ▼
┌───────────────────────────┐     Appends Audit    ┌───────────────────────────┐
│ worklog/YYYY-MM-DD_*.log  │ ──────────────────> │ prompt.log                │
└───────────────────────────┘                      └───────────────────────────┘
```

### Artifact Ownership Table

| Artifact | Owner (Content) | Owner (Lifecycle) | Read By |
|----------|----------------|-------------------|---------|
| `worklog/YYYY-MM-DD_<KEY>.log` | `jira-worklog-processor` | `devops-daily-protocol` | All skills |
| `worklog/YYYY-MM-DD_<KEY>_raw.log` | `jira-worklog-processor` | `devops-daily-protocol` | `jira-worklog-processor` |
| `worklog/done/*` | (archived) | `devops-daily-protocol` | `jira-worklog-processor` (reopened check) |
| `worklog/tickets.log` | `devops-daily-protocol` | `devops-daily-protocol` | All skills |
| `prompt.log` | All skills (append-only) | `devops-daily-protocol` | All skills |
| `PR.log` | `jira-worklog-processor` (entry format); `pr-review-comments` (`POSTED COMMENTS`, `NOT POSTED`, follow-up blocks) | `devops-daily-protocol` through Write Gates | All skills |
| GitHub PR review comments | `pr-review-comments` | GitHub | `pr-review-comments` (re-read rather than recalled) |
| `worklog.template` | `jira-worklog-processor` | User-maintained | `jira-worklog-processor` |
| `ticket-pickup.prompt` | `jira-worklog-processor` | User-maintained | `jira-worklog-processor` |
| `.ai-worklog/state/<KEY>.json` | `ai-worklog-framework` schema | `devops-daily-protocol` through Write Gates | Daily, delivery, and closeout reports |
| `.ai-worklog/evidence/*` | `ai-worklog-framework` | Runtime workspace | Investigation and delivery routines |
| `.ai-worklog/config.json` | User/workspace | `ai-worklog workspace init` | Framework commands |
| `syntax_check.groovy` | `jenkins-pipeline-architect` | `jenkins-pipeline-architect` | `jenkins-pipeline-architect` |
| `tmp/<KEY>/` | `jira-worklog-processor` | `jira-worklog-processor` | All skills |
| Jenkinsfiles | `jenkins-pipeline-architect` | Workspace/SCM | `jenkins-pipeline-architect` |
| `vars/*.groovy` | `jenkins-pipeline-architect` | Workspace/SCM | `jenkins-pipeline-architect` |

### Shared Artifact Conflict Rules

1. **`prompt.log`** is append-only — no skill may edit or delete existing entries
2. **Worklog files** — only one skill writes at a time; `devops-daily-protocol` manages file locks via Write Gate sequencing
3. **Template files** (`worklog.template`, `ticket-pickup.prompt`) — agent reads only, user maintains
4. **`_raw.log` files** — excluded from `verify` scanning and Tempo correlation

---

## 4. Decision Tree for Skill Activation

When a user prompt is received, evaluate in sequence:

```
                            ┌──────────────────────┐
                            │   User Prompt        │
                            └──────────┬───────────┘
                                       │
                         ┌─────────────▼──────────────┐
                    ┌────┤ Contains Jenkins/CI/CD/     │────┐
                    │YES │ Groovy pipeline keywords?   │ NO │
                    │    └────────────────────────────┘    │
                    ▼                                       ▼
          Activate L4:                          ┌──────────────────────┐
          jenkins-pipeline-architect       ┌────┤ Contains ticket key, │────┐
          + L1 if code mods planned        │YES │ "pick up", "log time",│ NO │
                                           │    │ "work status"?       │    │
                                           ▼    └──────────────────────┘    ▼
                                 Activate L2:                    ┌─────────────────┐
                                 devops-daily-protocol      ┌───┤ Contains MODE:  │───┐
                                 + L3 for worklog content   │YES│ constraint?     │NO │
                                 + L1 for mode governance   │   └─────────────────┘   │
                                                            ▼                          ▼
                                                  Enforce L1:            Activate L1:
                                                  developer-protocol     developer-protocol
                                                  on top of all          lifecycle discipline
                                                  active skills          on target workspace
```

### Activation Matrix Quick Reference

| User Says | L1 | L2 | L3 | L4 | L5 |
|-----------|----|----|----|----|----|
| "what should I work on?" | ✅ RESEARCH | ✅ Day Start | ○ | ○ | ○ |
| "pick up DEVOPS-123" | ✅ RESEARCH→PLAN | ✅ Ticket Pickup | ✅ Create worklog | ○ | ○ |
| "investigate the OOM issue" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ○ | ○ |
| "the Jenkins build failed" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ✅ Pipeline analysis | ○ |
| "create a Jenkinsfile for deploy" | ✅ Full cycle | ○ | ○ | ✅ Pipeline creation | ○ |
| "review PR #45" | ✅ RESEARCH | ○ | ✅ PR Review | ✅ If PR has Jenkinsfile | ○ |
| "comment finding 2 in <PR URL>" | ✅ RESEARCH | ✅ Gates the PR.log append | ✅ Owns the PR.log entry | ○ | ✅ Prove, author, post |
| "log 2 hours on DEVOPS-123" | ✅ EXECUTE | ✅ Ticket Done | ✅ Time logging | ○ | ○ |
| "end of day summary" | ✅ RESEARCH | ✅ Day End | ○ | ○ | ○ |
| "MODE: PLAN" | ✅ Transition | ○ | ○ | ○ | ○ |
| "refactor this function" | ✅ Full cycle | ○ | ○ | ○ | ○ |
| "PR #45 merged" | ✅ EXECUTE | ○ | ✅ Merge follow-up | ○ | ✅ Follow-up outcomes |

---

## 5. Edge Cases & Conflict Resolution

### 5.1 Conflicting Modes

| Conflict | Resolution |
|----------|------------|
| User requests Write Gate in RESEARCH mode | Deny. Require `MODE: PLAN` before proposing, `MODE: EXECUTE` before performing. |
| User says "just do it" without PLAN | Agent must still propose in PLAN format. "I need to plan this first — switching to PLAN mode." |
| Two skills want to write to same worklog section | Sequenced by Write Gate — only one Write Gate active at a time. |
| User switches mode mid-Write Gate | Cancel current Write Gate. Re-evaluate in new mode. |

### 5.2 Duplicate Worklogs

| Scenario | Resolution |
|----------|------------|
| `worklog/2026-07-28_DEVOPS-123.log` already exists, user picks up same ticket | Warn: "Worklog already exists for today. Continue updating existing file, or create `_v2` suffix?" |
| Worklog in `done/` and `worklog/` for same ticket | `done/` file is stale. Active file in `worklog/` takes precedence. |
| Two worklogs for same ticket, different dates | Both are valid (multi-day work). Cross-reference them in RELATED TICKET section. |

### 5.3 API Limits & Failures

| Failure | Skill | Recovery |
|---------|-------|----------|
| JIRA CLI returns empty/error | `devops-daily-protocol` | Retry once. If still failing, log error in worklog FINDINGS and continue with manual data. |
| Tempo API 401 Unauthorized | `devops-daily-protocol` | Check `integrations/jira/jira.properties`. Surface to user. Do not retry with same token. |
| Tempo API 429 Rate Limited | `devops-daily-protocol` | Wait 60 seconds, retry with exponential backoff (max 3 attempts). |
| New Relic operator returns no data | `devops-daily-protocol` | Log "No NR data available" in FINDINGS. Suggest manual NR UI check. |
| `gh` CLI not authenticated | `jira-worklog-processor` | PR review workflow fails gracefully. Log error, suggest `gh auth login`. |
| `syntax_check` JDK error | `jenkins-pipeline-architect` | JDK newer than the script's `MAX_JDK` ceiling. Suggest running `scripts/syntax_check.sh`, or setting `JAVA_HOME` to an install at or below it. |
| Artifactory Storage API timeout | `jenkins-pipeline-architect` | Active Choice parameter returns fallback: `["ERROR: timeout", "1.0.0"]`. |

### 5.4 Prompt.log Conflicts

| Scenario | Resolution |
|----------|------------|
| Long session with 20+ interactions | Each interaction appends independently. Use TAB sub-sections for multi-topic sessions. |
| Session crashes mid-write | `prompt.log` may have incomplete entry. Next session should detect and close the dangling entry. |
| Multiple agent instances write simultaneously | Not supported. One agent session per workspace at a time. |

---

## 6. Troubleshooting Guide

### Symptom: Skill Not Activating

```
CHECK 1: Does the user prompt contain trigger keywords?
         └── See Activation Matrix (Section 4)
         
CHECK 2: Is the skill directory mounted or placed in the IDE agent skills path?
         └── E.g., .cursor/skills/<skill-name>/, .agents/skills/<skill-name>/, or global agent configuration
         
CHECK 3: Does SKILL.md have valid YAML frontmatter?
         └── Must start with --- and end with ---
         └── Must have name: and description: fields
```

### Symptom: Write Gate Not Triggering

```
CHECK 1: Is developer-protocol in PLAN or EXECUTE mode?
         └── Write Gates require PLAN to propose, EXECUTE to perform
         
CHECK 2: Is the operation actually a write?
         └── Read operations (JIRA CLI, New Relic operator reads, file reads, kubectl get) bypass Write Gate
         
CHECK 3: Is the agent following the 5-step protocol?
         └── ANNOUNCE → PREVIEW → WAIT → EXECUTE → VERIFY
         └── Missing any step = protocol violation
```

### Symptom: Worklog Sections Not Populating

```
CHECK 1: Is the correct mode active for the target section? (R-09)
         └── Analytical sections are mode-gated:
             FINDINGS → RESEARCH, PROPOSED SOLUTIONS → INNOVATE,
             PROPOSED ACTIONS → PLAN, ACTION LOG → EXECUTE
         └── Structural sections are NOT mode-gated:
             TICKET header, RELATED TICKET, REFERENCED REPOSITORIES,
             STATUS, TIME LOGGED, DELIVERY STATE
             If one of these is not populating, the cause is a missing
             Write Gate (R-05), not the mode
         
CHECK 2: Is worklog.template accessible?
         └── Path: skills/jira-worklog-processor/worklog.template
         
CHECK 3: Is the worklog file path correct?
         └── Pattern: worklog/YYYY-MM-DD_<KEY>.log
         └── Date must be today's date
```

### Symptom: Jenkins Syntax Check Fails

```
CHECK 1: Is an installed JDK at or below the ceiling?
         └── Ceiling is MAX_JDK in scripts/syntax_check.sh; read it there
         └── Groovy cannot read class files from JDKs newer than it supports
         └── macOS: /usr/libexec/java_home -v <ceiling>
         └── Linux: $JVM_SEARCH_PATH (default /usr/lib/jvm)
         └── Any platform: export JAVA_HOME_17 (legacy name, any
             version at or below the ceiling is accepted)

CHECK 2: Is the syntax check accessible?
         └── Wrapper: skills/jenkins-pipeline-architect/scripts/syntax_check.sh
         └── Script:  skills/jenkins-pipeline-architect/scripts/syntax_check.groovy
         
CHECK 3: Is the Jenkinsfile a valid Groovy file?
         └── Check brace matching, string literals, closure syntax
         └── Jenkins DSL methods (node, stage) won't validate locally
```

---

## 7. Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | Initial | Basic interaction matrix, data flow, decision tree |
| 2.0 | IMP-03.1 | Full 45-pattern handoff contracts, edge cases, troubleshooting, composite workflows |
| 2.1 | 2026-08-10 | Added ai-worklog preflight, state, diagnostics, daily, and closeout contracts |
| 3.0 | 2026-09-11 | Replaced the 53-pattern matrix with 23 inter-layer rules (R-01..R-23). Corrected the mode/section mapping: structural worklog sections are not mode-gated. Added R-23, fixing the unresolved conflict between the Write Gate's confirmation step and the `.rules` §5 style directive. |
| 3.1 | 2026-09-11 | Removed the hardcoded JDK 17 requirement. The ceiling is `MAX_JDK` in `syntax_check.sh`, which had already moved to 26 while every document still named 17. |
| 3.2 | 2026-09-11 | Added R-24: the `ai-worklog service` operators require the Groovy runtime. Previously undocumented anywhere, so switching to the Python runtime silently removed every L2 tool contract. |
| 3.3 | 2026-09-11 | Documented the Automox operator, implemented in the framework on 2026-09-10 and until now absent from every skill. Added it to R-24's operator list. |
| 3.4 | 2026-09-11 | Documented the Jenkins operator's 15 actions, of which only `credentials` had been described. Noted in R-16 that its `syntax-check` is a front end to this repo's `syntax_check.sh`, not a rival implementation. |
| 3.5 | 2026-09-11 | Added `pr-review-comments` as L5, a peer specialist to L4. New §2.8 with R-25..R-27, PR.log co-ownership in the artifact table, and an activation row. The skill had existed since 2026-09-11 with no layer, no rules and no mention here. |
