---
name: devops-daily-protocol
version: "1.1.0"
description: >-
  Orchestrates daily DevOps operations: pulling JIRA tickets, selecting work items,
  creating structured worklog files, integrating ai-worklog and New Relic monitoring,
  and managing Tempo time logging. Use when starting a work day, picking up a ticket,
  investigating issues, finishing ticket work, or logging time.
---

# DevOps Daily Protocol

## Safety Rules
All operations are **read-only by default**. Any write operation requires the Write Gate Protocol (section below).

Write operations include:
- Creating or editing files (worklog files, raw logs)
- Applying `ai-worklog workspace` or `ai-worklog state` changes
- HTTP POST/PUT/DELETE to JIRA, Tempo, or any external API
- Git commits, pushes, or any repository modifications

Read operations (always allowed without approval):
- Running JIRA CLI in any mode (summary, ticket, rejected, tempo, verify)
- Running New Relic CLI in any mode (apps, app, hosts, deployments, alerts, violations)
- Reading any workspace file
- Running kubectl read-only commands (get, describe, top, logs)
- Running `ai-worklog` preflight, prepare, report, catalog, diagnostic, and toolchain reads

After every interaction, append a summary to `prompt.log` (see Prompt Logging section).

31: ## Available Tools
32: All paths are relative to the workspace root. `integrations/` is the canonical
33: service hub: every external service has one subfolder holding its `credentials` file
34: and, where applicable, its CLI script. See
35: [worklog-reference.md](../jira-worklog-processor/worklog-reference.md) § "Interface Directory"
36: for the full service inventory.
37: 
38: ### JIRA CLI
39: **Path**: `integrations/jira/jira-ticket-info.sh`
40: 
41: | Mode | Command | Purpose |
42: |------|---------|---------|
43: | summary | `integrations/jira/jira-ticket-info.sh summary` | Board overview: in-progress, blocked, to-do, recently completed |
44: | ticket | `integrations/jira/jira-ticket-info.sh <KEY>` | Full ticket detail: fields, description, comments, worklogs, assignment |
45: | rejected | `integrations/jira/jira-ticket-info.sh rejected` | List rejected (Odrzucone) tickets |
46: | tempo | `integrations/jira/jira-ticket-info.sh tempo [YYYY-MM-DD]` | Daily Tempo timesheet entries (defaults to today) |
47: | verify | `integrations/jira/jira-ticket-info.sh verify [YYYY-MM-DD]` | Compare local worklog/ files against Tempo entries |
48: 
49: ### New Relic CLI
50: **Path**: `integrations/newrelic/newrelic-info.sh`
51: 
52: | Mode | Command | Purpose |
53: |------|---------|---------|
54: | apps | `integrations/newrelic/newrelic-info.sh apps` | All applications with health status and metrics |
55: | app | `integrations/newrelic/newrelic-info.sh app <ID>` | Single application detail |
56: | hosts | `integrations/newrelic/newrelic-info.sh hosts <ID>` | Hosts for an application |
57: | deployments | `integrations/newrelic/newrelic-info.sh deployments <ID>` | Deployment history for an application |
58: | alerts | `integrations/newrelic/newrelic-info.sh alerts <ID>` | Alert conditions targeting an application |
59: | violations | `integrations/newrelic/newrelic-info.sh violations` | All open alert violations |

### Monitoring References
- **kubectl patterns**: `zzzrecycle/monitor_commands.txt` — read this file for cluster diagnostic commands
- **NR host audit**: `zzzrecycle/nr-audit.sh` — remote audit of New Relic config on docker hosts
- **Worklog template**: `skills/jira-worklog-processor/worklog.template` — structure for worklog files (managed by sibling skill `jira-worklog-processor`)

### AI Worklog CLI
- `ai-worklog workspace init <path>` — preview workspace initialization; add `--apply` only after a Write Gate
- `ai-worklog preflight [--ticket <KEY>] [--service <SERVICE>...]` — environment readiness
- `ai-worklog ticket prepare <KEY>` — worklogs, catalog, repositories, PRs, and delivery path
- `ai-worklog state ...` — validated local structured state; mutations require dry-run preview and Write Gate
- `ai-worklog delivery status <KEY>` and `closeout report <KEY>` — read-only reconciliation reports
- `ai-worklog diag list|run` — registered read-only diagnostics and redacted evidence
- `ai-worklog day start|end` and `toolchain check|list|env` — daily and runtime reports

## Cross-Skill Handoffs

This skill serves as the **operational lifecycle shell (Layer 2)** and orchestrates handoffs to sibling skills:

1. **Handoff to `jira-worklog-processor` (Content Engine):**
   - **Trigger:** Ticket Pickup or Investigation update.
   - **Contract:** `devops-daily-protocol` executes JIRA CLI commands to fetch ticket metadata and then delegates worklog section formatting to `jira-worklog-processor` using `skills/jira-worklog-processor/worklog.template`.

2. **Handoff to `jenkins-pipeline-architect` (CI/CD Specialist):**
   - **Trigger:** Investigation mode identifies a Jenkins failure or build pipeline bug.
   - **Contract:** Delegates Jenkinsfile inspection, Groovy CPS analysis, and syntax validation (`syntax_check.groovy`) to `jenkins-pipeline-architect`.

3. **Governance by `developer-protocol` (Mode Control):**
   - Read operations (JIRA CLI, NR CLI, kubectl) execute under `RESEARCH` mode.
   - All Write Gate proposals (file updates, Tempo time logging, git operations) execute under `PLAN` / `EXECUTE` modes.

For the full interaction matrix, see [CROSS_SKILL_INTEGRATION.md](../CROSS_SKILL_INTEGRATION.md).

## Workflow Routines

Nine routines triggered by user intent. Detect the appropriate routine from context.
Governance modes (RESEARCH, INNOVATE, PLAN, EXECUTE) are orthogonal and controlled
by the developer-protocol skill. These routines define WHEN operational activities
happen; governance modes define WHAT actions are permitted.

### ROUTINE: Preflight
Trigger: start of session, or user requests environment check.
Steps:
1. Run `ai-worklog preflight` (from ai-worklog-framework) to validate workspace,
   binaries, authentication, and connectivity
2. Report any BLOCKED or DEGRADED services
3. If ticket-scoped, run `ai-worklog preflight --ticket <TICKET-KEY>`
4. For a new workspace, preview `ai-worklog workspace init <path>` and use a Write Gate before `--apply`

### ROUTINE: Day Start
Trigger: user starts work, asks "what should I work on", or requests ticket overview.
Steps:
1. Run `ai-worklog day start` to reconcile structured state and active worklogs
2. Run `integrations/jira/jira-ticket-info.sh summary` to pull current board state
3. Run `integrations/jira/jira-ticket-info.sh tempo` to check hours already logged today
4. Present ticket overview grouped by board column
5. Suggest which ticket to pick up next, prioritizing by:
   - Priority field (Wysoki > Sredni > Niski)
   - Ticket age (older unresolved tickets first)
   - Blocked tickets (flag but skip for pickup)
6. If there are open NR violations, mention them: run `integrations/newrelic/newrelic-info.sh violations`

### ROUTINE: Ticket Pickup
Trigger: user selects a ticket to work on, or says "pick up TICKET-KEY".
Steps:
1. Run `ai-worklog ticket prepare <TICKET-KEY>` and ticket-scoped preflight
2. Run `integrations/jira/jira-ticket-info.sh <TICKET-KEY>` to fetch full ticket detail
3. Parse the output to extract: key, summary, status, type, priority, project, assignee, reporter, components, created, updated, description
4. Check if `worklog/done/*_TICKET-KEY*.log` exists (reopened ticket detection)
   - If found: inform user "Previous worklog found in `done/` for this ticket: [list files]. Copy back to `worklog/`?"
   - **WRITE GATE**: show files and proposed copy action
   - If user approves: copy files back to `worklog/`, skip creating new worklog from template
   - If user declines: proceed with creating fresh worklog from template as normal
5. **WRITE GATE**: Propose creating worklog file and initializing `ai-worklog state`
   - Pre-populate ticket header from JIRA response using template structure:
     ```
     ================================================================================
       TICKET: <key>
       Summary:    <summary>
       Status:     <status>
       Type:       <type>
       Priority:   <priority>
       Project:    <project>
       Assignee:   <assignee>
       Reporter:   <reporter>
       Components: <components>
       Created:    <created>
       Updated:    <updated>
       Description:
         <description>
     ================================================================================

     ================================================================================
       FINDINGS
     ================================================================================

     ================================================================================
       PROPOSED SOLUTIONS
     ================================================================================

     ================================================================================
       PROPOSED ACTIONS
     ================================================================================

     ================================================================================
       ACTION LOG
     ================================================================================
     ```
   - Show the full proposed file content and path before creating
6. After approval, create the file and run `ai-worklog state init <TICKET-KEY> --apply`
7. If ticket involves monitoring, alerting, or infrastructure, suggest relevant diagnostic or NR commands

### ROUTINE: Investigation
Trigger: user is actively working on a ticket — researching, querying, analyzing.
This mode supports the user during active investigation. Use tools as needed:

**New Relic investigation patterns**:
- Open violations: `integrations/newrelic/newrelic-info.sh violations`
- App-specific alerts: `integrations/newrelic/newrelic-info.sh alerts <APP_ID>`
- App health overview: `integrations/newrelic/newrelic-info.sh apps` then `app <ID>`
- Host inspection: `integrations/newrelic/newrelic-info.sh hosts <APP_ID>`
- Recent deployments: `integrations/newrelic/newrelic-info.sh deployments <APP_ID>`

**Kubernetes diagnostics** (read `zzzrecycle/monitor_commands.txt` for full list):
- Prefer a matching read-only pack from `ai-worklog diag list`; run it with `ai-worklog diag run` and reference its evidence bundle in FINDINGS
- Unhealthy pods: `kubectl get pods --all-namespaces | awk '$4 != "Running" && $4 != "Completed" && NR > 1'`
- Pod resource usage: `kubectl top pods -n <NAMESPACE> --sort-by=memory`
- Recent failure events: `kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -iE "not ready|unhealthy|back-off|failed" | tail -20`
- HPA status: `kubectl get hpa -n <NAMESPACE>`

**Updating worklog files**:
- Each update to the worklog file is a **WRITE GATE** — show proposed changes before applying
- Add findings, proposed solutions, proposed actions as investigation progresses
- For detailed data (NRQL results, large outputs, data tables), propose creating a `_raw.log` companion:
  `worklog/YYYY-MM-DD_TICKET-KEY_suffix_raw.log`
- Suffixes describe the sub-investigation (e.g., `_oomkilled`, `_zoltan-alerts`, `_solr-logs`)

### ROUTINE: Delivery
Trigger: implementation is complete; user is ready to commit, open PRs, build, deploy, or verify.
This routine tracks the progression from local implementation to live-verified deployment.

**Delivery lifecycle states** (tracked per-ticket):
- `implemented_locally` — code written but not committed
- `committed` — changes committed to a branch
- `pr_open` — pull request created
- `pr_merged` — pull request merged to target branch
- `built` — CI build succeeded, artifact produced
- `configured` — GitOps manifests updated (image tag, config)
- `synchronized` — ArgoCD or deploy system applied the change
- `verified_live` — live environment confirmed working

**Key activities:**
- Track multi-repository PR dependencies and merge order
- Record build numbers, image tags, and chart versions
- Detect ArgoCD sync state (including false-positive Synced without live update)
- Document manual operations not captured in PRs (forced syncs, seed runs)
- Run verification commands from the service catalog
- Preview structured changes with `ai-worklog state ...`; after Write Gate approval, apply them with `--apply`
- Run `ai-worklog delivery status <TICKET-KEY>` after mutations to reconcile lifecycle gaps

**Updating worklog DELIVERY STATE section:**
- Each delivery lifecycle change is a **WRITE GATE** — show proposed update before applying
- Record the complete state including all repositories and environments
- Structured JSON leads automation; mirror material state into the human worklog in a separate Write Gate

### ROUTINE: Ticket Done
Trigger: user says ticket is done, finished, complete, or asks to log time.
Steps:
1. Run `ai-worklog closeout report <TICKET-KEY>`, then read matching worklogs
2. Determine time spent:
   - Ask the user for their estimate, OR
   - Propose an estimate based on worklog complexity and session context
   - Time must be in seconds for the API (1h = 3600, 30m = 1800)
3. Run `integrations/jira/jira-ticket-info.sh tempo` to show current day's logged hours
4. **WRITE GATE**: Propose Tempo time logging. Show the exact operation:
   - Method: POST
   - URL: `https://jira.pl.grupa.iti/rest/tempo-timesheets/3/worklogs`
   - Headers: `Authorization: Bearer <token from jira.properties>`, `Content-Type: application/json`
   - Payload:
     ```json
     {
       "issueKey": "<TICKET-KEY>",
       "dateStarted": "<YYYY-MM-DD>",
       "timeSpentSeconds": <seconds>,
       "comment": "<brief summary of work done>"
     }
     ```
   - Present the payload with actual values filled in
5. After approval, execute the POST request
6. Run `integrations/jira/jira-ticket-info.sh verify` to confirm the entry appears in Tempo
7. Present verification result
8. **WRITE GATE**: Propose moving worklog files to `done/` subfolder
   - Identify all files matching `worklog/*_TICKET-KEY*.log` (glob on ticket key)
   - List all files to be moved and their destination (`worklog/done/`)
   - After approval: create `worklog/done/` if it doesn't exist, move all matching files
   - Confirm move by listing the moved files in `worklog/done/`

### ROUTINE: Day End
Trigger: user ends their day, asks for daily summary, or wants to verify logged hours.
Steps:
1. Run `ai-worklog day end` for the structured continuation capsule
2. Run `integrations/jira/jira-ticket-info.sh verify` to compare worklog files vs Tempo for today
3. Run `integrations/jira/jira-ticket-info.sh tempo` to show total hours logged today
4. Analyze the output:
   - **MATCHED**: worklog file exists AND Tempo entry exists — no action needed
   - **MISSING FROM TEMPO**: worklog file exists but no hours logged — flag for action, offer to log via Ticket Done mode
   - **MISSING FROM WORKLOG**: Tempo entry but no local file — informational only
5. Present daily summary: tickets worked on, total hours, any gaps

## Write Gate Protocol
Every non-read operation MUST follow this protocol:

1. **ANNOUNCE**: State the operation type clearly (e.g., "Creating worklog file", "Posting to Tempo API", "Moving files").
2. **PREVIEW**: Show the intended change using these compact formats:
   - **File (New/Overwrite)**: Fenced code block with the filename on top, then the full content.
     ```
     # File: worklog/2026-03-07_DEVOPS-123.log
     [full file content]
     ```
   - **File (Edit)**: Unified diff format (`---`/`+++`/`@@`) for efficiency.
     ```diff
     --- worklog/2026-03-07_DEVOPS-123.log
     +++ worklog/2026-03-07_DEVOPS-123.log
     @@ -5,8 +5,9 @@
       FINDINGS
     ================================================================================

     1. Found OOMKilled in pod xyz
     ================================================================================
     ```
   - **API Call**: `[METHOD] URL | Payload: {JSON_SUMMARY}` (redact tokens).
     ```
     [POST] https://jira.pl.grupa.iti/rest/tempo-timesheets/3/worklogs | Payload: {"issueKey": "DEVOPS-123", "dateStarted": "2026-03-07", "timeSpentSeconds": 3600, "comment": "..."}
     ```
   - **Git/CLI**: Exact command and target files.
     ```
     cp worklog/2026-03-07_DEVOPS-123.log worklog/done/
     ```
3. **WAIT**: Ask explicitly: "Proceed? (yes/no)"
4. **EXECUTE**: Only after the user confirms with approval.
5. **VERIFY**: Confirm the operation succeeded (re-read file or re-run command).

## Worklog File Conventions
### Naming
```
worklog/YYYY-MM-DD_TICKET-KEY.log              (primary worklog)
worklog/YYYY-MM-DD_TICKET-KEY_suffix.log        (sub-investigation worklog)
worklog/YYYY-MM-DD_TICKET-KEY_suffix_raw.log    (detailed investigation data)
worklog/done/YYYY-MM-DD_TICKET-KEY.log          (completed ticket worklog)
worklog/done/YYYY-MM-DD_TICKET-KEY_suffix.log   (completed sub-investigation)
worklog/done/YYYY-MM-DD_TICKET-KEY_suffix_raw.log (completed investigation data)
```

- Date prefix: today's date in ISO format
- Ticket key: exact JIRA key (e.g., DEVOPS-748, CWP-4430)
- Suffix: lowercase descriptor when multiple worklogs exist for the same ticket on the same day
- `_raw.log` files contain detailed data (NRQL output, large tables, samples) and are excluded from `verify` mode scanning
- `done/` subfolder holds worklogs for tickets that have been closed/done in JIRA — files retain their original names, no renaming on move
- `done/` is created automatically if it doesn't exist
- Files in `done/` are excluded from `verify` scanning

### Structure
All worklog files follow the `skills/jira-worklog-processor/worklog.template` structure:

| Section | Content |
|---------|---------|
| Header | Ticket metadata from JIRA (key, summary, status, type, priority, project, assignee, reporter, components, created, updated, description) |
| REFERENCED REPOSITORIES | Repos involved, local clone status, default branches |
| FINDINGS | Numbered findings with sub-sections using dotted separators |
| PROPOSED SOLUTIONS | Options with labels (e.g., SOLUTION A, SOLUTION B) including pros/cons |
| RISK CONSIDERATIONS | Identified risks and mitigations |
| PROPOSED ACTIONS | Numbered action items, grouped by priority (IMMEDIATE, NEXT) or gates (G0-G4) |
| OPEN DECISIONS | Tracked decisions with status (open/resolved/superseded) |
| BLOCKERS | Active and resolved blockers with owners |
| ACTION LOG | Chronological record of actions taken during the session |
| DELIVERY STATE | Multi-dimensional lifecycle: implementation, committed, PR, built, GitOps, synced, verified |
| STATUS | Current ticket status summary |
| TIME LOGGED | Tempo entries and session durations |
| NEXT ACTION | Explicit continuation point for next session |

340: ### tickets.log
341: The file `worklog/tickets.log` stores the latest output from `integrations/jira/jira-ticket-info.sh summary`. Overwrite it each time summary is run at day start.
342: 
343: ## Prompt Logging
344: After every interaction, append to `prompt.log` at the workspace root:
345: ```
346: --- PROMPT LOG ENTRY ---
347: TIMESTAMP: YYYY-MM-DD
348: USER: <concise summary of what the user asked>
349: ASSISTANT: <mode used> — <concise summary of actions taken and outcomes>
350:   <key details: files created, commands run, time logged, etc.>
351: --- END PROMPT LOG ENTRY ---
352: ```
353: 
354: For multi-tab sessions, use sub-sections:
355: ```
356: --- PROMPT LOG ENTRY ---
357: TIMESTAMP: YYYY-MM-DD
358: USER: Multiple topics in single session.
359: 
360: TAB 1: <tab description>
361:   <details>
362: 
363: TAB 2: <tab description>
364:   <details>
365: --- END PROMPT LOG ENTRY ---
366: ```
367: 
368: ## New Relic Integration
369: ### Investigation Decision Tree
370: | Need | Command |
371: |------|---------|
372: | Check for active incidents | `integrations/newrelic/newrelic-info.sh violations` |
373: | Find alert conditions for an app | `integrations/newrelic/newrelic-info.sh alerts <APP_ID>` |
374: | Check app health and metrics | `integrations/newrelic/newrelic-info.sh app <APP_ID>` |
375: | List all apps to find an ID | `integrations/newrelic/newrelic-info.sh apps` |
376: | Check which hosts serve an app | `integrations/newrelic/newrelic-info.sh hosts <APP_ID>` |
377: | Check recent deployments | `integrations/newrelic/newrelic-info.sh deployments <APP_ID>` |
| Audit NR config on a remote host | Read `zzzrecycle/nr-audit.sh`, run on target host via SSH |

### Common NRQL Patterns
For investigations requiring direct NRQL queries (run via NR UI or API):
| Purpose | Pattern |
|---------|---------|
| Log volume by entity | `SELECT count(*), bytecountestimate()/1e6 as 'MB' FROM Log WHERE entity.name LIKE '%<NAME>%' SINCE 7 days ago FACET entity.name` |
| Error rate by status | `SELECT percentage(count(*), WHERE level = 'ERROR') FROM Log WHERE entity.name = '<NAME>' SINCE 30 days ago` |
| Daily timeseries | `SELECT count(*) FROM Log WHERE entity.name = '<NAME>' SINCE 30 days ago TIMESERIES 1 day` |
| Lambda entity search | `SELECT uniques(entity.name) FROM Log WHERE entity.name LIKE '%lambda%' SINCE 30 days ago LIMIT MAX` |
| OTel metric percentage | `SELECT percentage(sum(getField(<metric>, count)), WHERE status_code > 499) FROM Metric WHERE service.name = '<SVC>' SINCE 1 hour ago` |

### Kubernetes Diagnostics
Read `zzzrecycle/monitor_commands.txt` for the full command reference. Key commands:
| Purpose | Command |
|---------|---------|
| Unhealthy pods | `kubectl get pods --all-namespaces \| awk '$4 != "Running" && $4 != "Completed" && NR > 1'` |
| Pod resources | `kubectl top pods -n <NS> --sort-by=memory` |
| HPA status | `kubectl get hpa -n <NS>` |
| Failure events | `kubectl get events --all-namespaces --sort-by='.lastTimestamp' \| grep -iE "not ready\|unhealthy\|back-off\|failed" \| tail -20` |
| Container limits | `kubectl get deployment <NAME> -n <NS> -o jsonpath='{.spec.template.spec.containers[0].resources}' \| python3 -m json.tool` |
