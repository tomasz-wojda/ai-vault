---
name: devops-daily-protocol
description: Orchestrates daily DevOps operations: pulling JIRA tickets, selecting work items, creating structured worklog files, integrating New Relic monitoring, and managing Tempo time logging. Use when starting a work day, picking up a ticket, investigating issues, finishing ticket work, or logging time.
---

# DevOps Daily Protocol

## Safety Rules

All operations are **read-only by default**. Any write operation requires the Write Gate Protocol (section below).

Write operations include:
- Creating or editing files (worklog files, raw logs)
- HTTP POST/PUT/DELETE to JIRA, Tempo, or any external API
- Git commits, pushes, or any repository modifications

Read operations (always allowed without approval):
- Running JIRA CLI in any mode (summary, ticket, rejected, tempo, verify)
- Running New Relic CLI in any mode (apps, app, hosts, deployments, alerts, violations)
- Reading any workspace file
- Running kubectl read-only commands (get, describe, top, logs)

After every interaction, append a summary to `prompt.log` (see Prompt Logging section).

## Available Tools

All paths are relative to the workspace root.

### JIRA CLI

**Path**: `jira/jira-ticket-info.sh`

| Mode | Command | Purpose |
|------|---------|---------|
| summary | `jira/jira-ticket-info.sh summary` | Board overview: in-progress, blocked, to-do, recently completed |
| ticket | `jira/jira-ticket-info.sh <KEY>` | Full ticket detail: fields, description, comments, worklogs, assignment |
| rejected | `jira/jira-ticket-info.sh rejected` | List rejected (Odrzucone) tickets |
| tempo | `jira/jira-ticket-info.sh tempo [YYYY-MM-DD]` | Daily Tempo timesheet entries (defaults to today) |
| verify | `jira/jira-ticket-info.sh verify [YYYY-MM-DD]` | Compare local worklog/ files against Tempo entries |

### New Relic CLI

**Path**: `newrelic/newrelic-info.sh`

| Mode | Command | Purpose |
|------|---------|---------|
| apps | `newrelic/newrelic-info.sh apps` | All applications with health status and metrics |
| app | `newrelic/newrelic-info.sh app <ID>` | Single application detail |
| hosts | `newrelic/newrelic-info.sh hosts <ID>` | Hosts for an application |
| deployments | `newrelic/newrelic-info.sh deployments <ID>` | Deployment history for an application |
| alerts | `newrelic/newrelic-info.sh alerts <ID>` | Alert conditions targeting an application |
| violations | `newrelic/newrelic-info.sh violations` | All open alert violations |

### Monitoring References

- **kubectl patterns**: `zzzrecycle/monitor_commands.txt` — read this file for cluster diagnostic commands
- **NR host audit**: `zzzrecycle/nr-audit.sh` — remote audit of New Relic config on docker hosts
- **Worklog template**: `worklog/TEMPLATE.log` — structure for worklog files

## Workflow Modes

Five modes triggered by user intent. Detect the appropriate mode from context.

### MODE: Day Start

Trigger: user starts work, asks "what should I work on", or requests ticket overview.

Steps:
1. Run `jira/jira-ticket-info.sh summary` to pull current board state
2. Run `jira/jira-ticket-info.sh tempo` to check hours already logged today
3. Present ticket overview grouped by board column
4. Suggest which ticket to pick up next, prioritizing by:
   - Priority field (Wysoki > Sredni > Niski)
   - Ticket age (older unresolved tickets first)
   - Blocked tickets (flag but skip for pickup)
5. If there are open NR violations, mention them: run `newrelic/newrelic-info.sh violations`

### MODE: Ticket Pickup

Trigger: user selects a ticket to work on, or says "pick up TICKET-KEY".

Steps:
1. Run `jira/jira-ticket-info.sh <TICKET-KEY>` to fetch full ticket detail
2. Parse the output to extract: key, summary, status, type, priority, project, assignee, reporter, components, created, updated, description
3. Check if `worklog/done/*_TICKET-KEY*.log` exists (reopened ticket detection)
   - If found: inform user "Previous worklog found in `done/` for this ticket: [list files]. Copy back to `worklog/`?"
   - **WRITE GATE**: show files and proposed copy action
   - If user approves: copy files back to `worklog/`, skip creating new worklog from template
   - If user declines: proceed with creating fresh worklog from template as normal
4. **WRITE GATE**: Propose creating worklog file at `worklog/YYYY-MM-DD_TICKET-KEY.log`
   - Pre-populate ticket header from JIRA response using TEMPLATE.log structure:
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
5. After approval, create the file
6. If ticket involves monitoring, alerting, or infrastructure, suggest relevant NR commands

### MODE: Investigation

Trigger: user is actively working on a ticket — researching, querying, analyzing.

This mode supports the user during active investigation. Use tools as needed:

**New Relic investigation patterns**:
- Open violations: `newrelic/newrelic-info.sh violations`
- App-specific alerts: `newrelic/newrelic-info.sh alerts <APP_ID>`
- App health overview: `newrelic/newrelic-info.sh apps` then `app <ID>`
- Host inspection: `newrelic/newrelic-info.sh hosts <APP_ID>`
- Recent deployments: `newrelic/newrelic-info.sh deployments <APP_ID>`

**Kubernetes diagnostics** (read `zzzrecycle/monitor_commands.txt` for full list):
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

### MODE: Ticket Done

Trigger: user says ticket is done, finished, complete, or asks to log time.

Steps:
1. Read the worklog file (`worklog/YYYY-MM-DD_TICKET-KEY*.log`) to summarize accomplishments
2. Determine time spent:
   - Ask the user for their estimate, OR
   - Propose an estimate based on worklog complexity and session context
   - Time must be in seconds for the API (1h = 3600, 30m = 1800)
3. Run `jira/jira-ticket-info.sh tempo` to show current day's logged hours
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
6. Run `jira/jira-ticket-info.sh verify` to confirm the entry appears in Tempo
7. Present verification result
8. **WRITE GATE**: Propose moving worklog files to `done/` subfolder
   - Identify all files matching `worklog/*_TICKET-KEY*.log` (glob on ticket key)
   - List all files to be moved and their destination (`worklog/done/`)
   - After approval: create `worklog/done/` if it doesn't exist, move all matching files
   - Confirm move by listing the moved files in `worklog/done/`

### MODE: Day End

Trigger: user ends their day, asks for daily summary, or wants to verify logged hours.

Steps:
1. Run `jira/jira-ticket-info.sh verify` to compare worklog files vs Tempo for today
2. Run `jira/jira-ticket-info.sh tempo` to show total hours logged today
3. Analyze the output:
   - **MATCHED**: worklog file exists AND Tempo entry exists — no action needed
   - **MISSING FROM TEMPO**: worklog file exists but no hours logged — flag for action, offer to log via Ticket Done mode
   - **MISSING FROM WORKLOG**: Tempo entry but no local file — informational only
4. Present daily summary: tickets worked on, total hours, any gaps

## Write Gate Protocol

Every non-read operation MUST follow this protocol:

1. **ANNOUNCE**: State the operation type clearly
   - "I will CREATE a new file at ..."
   - "I will EDIT the file at ..."
   - "I will POST to the Tempo API ..."
   - "I will run a git commit ..."

2. **PREVIEW**: Show the full content that will be written or sent
   - For files: show complete file content or the exact diff
   - For API calls: show method, URL, headers (redact tokens), and full payload
   - For git: show the exact command and what it will affect

3. **WAIT**: Ask explicitly: "Proceed? (yes/no)"

4. **EXECUTE**: Only after the user confirms with approval

5. **VERIFY**: Confirm the operation succeeded
   - Re-read the file to confirm contents
   - Re-run `verify` or `tempo` to confirm API writes
   - Show the verification output

If the user declines, do NOT execute. Ask if they want modifications to the proposed operation.

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

All worklog files follow `worklog/TEMPLATE.log`:

| Section | Content |
|---------|---------|
| Header | Ticket metadata from JIRA (key, summary, status, type, priority, project, assignee, reporter, components, created, updated, description) |
| FINDINGS | Numbered findings with sub-sections using dotted separators |
| PROPOSED SOLUTIONS | Options with labels (e.g., SOLUTION A, SOLUTION B) including pros/cons |
| PROPOSED ACTIONS | Numbered action items, grouped by priority (IMMEDIATE, NEXT) |
| ACTION LOG | Chronological record of actions taken during the session |
| `done/` subfolder | Archive for completed ticket worklogs, excluded from `verify` scanning |

### tickets.log

The file `worklog/tickets.log` stores the latest output from `jira/jira-ticket-info.sh summary`. Overwrite it each time summary is run at day start.

## Prompt Logging

After every interaction, append to `prompt.log` at the workspace root:

```
--- PROMPT LOG ENTRY ---
TIMESTAMP: YYYY-MM-DD
USER: <concise summary of what the user asked>
ASSISTANT: <mode used> — <concise summary of actions taken and outcomes>
  <key details: files created, commands run, time logged, etc.>
--- END PROMPT LOG ENTRY ---
```

For multi-tab sessions, use sub-sections:

```
--- PROMPT LOG ENTRY ---
TIMESTAMP: YYYY-MM-DD
USER: Multiple topics in single session.

TAB 1: <tab description>
  <details>

TAB 2: <tab description>
  <details>
--- END PROMPT LOG ENTRY ---
```

## New Relic Integration

### Investigation Decision Tree

| Need | Command |
|------|---------|
| Check for active incidents | `newrelic/newrelic-info.sh violations` |
| Find alert conditions for an app | `newrelic/newrelic-info.sh alerts <APP_ID>` |
| Check app health and metrics | `newrelic/newrelic-info.sh app <APP_ID>` |
| List all apps to find an ID | `newrelic/newrelic-info.sh apps` |
| Check which hosts serve an app | `newrelic/newrelic-info.sh hosts <APP_ID>` |
| Check recent deployments | `newrelic/newrelic-info.sh deployments <APP_ID>` |
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
