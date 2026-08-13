# Cross-Skill Integration Guide

This document establishes the interaction model, handoff protocols, and unified architecture for the four core skills in `ai-vault`:

1. `developer-protocol` (Mode Discipline & Execution Safety)
2. `devops-daily-protocol` (Operational Lifecycle Shell & Tool Contracts)
3. `jira-worklog-processor` (Worklog Content Generation & Structuring)
4. `jenkins-pipeline-architect` (CI/CD Pipeline & Scripted Jenkinsfile Patterns)

---

## 1. The 4-Layer Skill Stack

The skills are designed as a layered architecture. Each layer handles a distinct concern:

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
├───────────────────────────────────────────────────────────────────┤
│ Layer 4: jenkins-pipeline-architect                               │
│ CI/CD Specialist (Scripted Jenkinsfile, CPS rules, syntax check)  │
└───────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Skill | Owns | Governs |
|-------|-------|------|---------|
| **L1** | `developer-protocol` | Mode state machine (RESEARCH/INNOVATE/PLAN/EXECUTE) | What actions are allowed at any given time |
| **L2** | `devops-daily-protocol` | Tool contracts (JIRA CLI, NR CLI, kubectl), Write Gate Protocol, prompt.log | When and how tools are invoked, safety enforcement |
| **L3** | `jira-worklog-processor` | Worklog content patterns, worklog.template, PR.log, ticket-pickup.prompt | What goes inside worklog files, content quality |
| **L4** | `jenkins-pipeline-architect` | Jenkinsfile patterns, CPS rules, syntax_check.groovy, postJiraComment | How CI/CD pipelines are structured and validated |

### Inter-Layer Communication Rules

1. **Higher layers constrain lower layers** — L1 mode rules override L2/L3/L4 actions
2. **Lower layers never override higher layers** — L4 cannot bypass L1 mode restrictions
3. **Sibling layers coordinate via handoffs** — L2↔L3, L2↔L4, L3↔L4 use explicit trigger/contract patterns
4. **All write operations route through L2** — Even L4 pipeline edits use L2's Write Gate Protocol

---

## 2. Complete Interaction Matrix (53 Patterns)

### Legend

| Symbol | Meaning |
|--------|---------|
| **→** | Handoff direction (source → target) |
| **⟷** | Bidirectional interaction |
| **▶** | Trigger phrase or event |
| **📤** | Data/artifact passed in handoff |
| **⚠️** | Edge case or failure mode |

---

### 2.1 developer-protocol → devops-daily-protocol (6 patterns)

#### P-01: Mode Enforcement on Day Start
- **▶ Trigger:** User starts day; `devops-daily-protocol` activates Day Start mode
- **📤 Data:** Current mode state (`RESEARCH`)
- **Contract:** All Day Start operations (JIRA summary, Tempo check, NR violations) execute under `RESEARCH` mode. No suggestions or planning permitted.
- **⚠️ Edge Case:** User says "what should I work on" — this is `RESEARCH` mode even though it requests a recommendation. The recommendation is based solely on priority/age heuristics, not creative planning.

#### P-02: Mode Enforcement on Investigation
- **▶ Trigger:** User enters Investigation mode in `devops-daily-protocol`
- **📤 Data:** Current mode state (`RESEARCH` or `INNOVATE`)
- **Contract:** Read-only tool operations (NRQL, kubectl, NR CLI) are always `RESEARCH`. When user evaluates solution options, mode transitions to `INNOVATE` — only discussions, pros/cons allowed.
- **⚠️ Edge Case:** User asks "should we restart the pod?" during RESEARCH — this is a solution suggestion. Agent must say: "That's a solution proposal. Switch to `MODE: INNOVATE` to discuss options."

#### P-03: Mode Enforcement on Write Gate
- **▶ Trigger:** `devops-daily-protocol` proposes a Write Gate operation
- **📤 Data:** Current mode state (`PLAN` or `EXECUTE`)
- **Contract:** Write Gate proposals (creating files, Tempo API POST, git operations) require `PLAN` mode to be proposed and `EXECUTE` mode to be performed. The Write Gate's 5-step flow (ANNOUNCE→PREVIEW→WAIT→EXECUTE→VERIFY) maps to `PLAN` (steps 1-3) and `EXECUTE` (steps 4-5).
- **⚠️ Edge Case:** User approves Write Gate but hasn't switched to `EXECUTE` mode — agent must request explicit `MODE: EXECUTE` before proceeding.

#### P-04: Mode Enforcement on Ticket Pickup
- **▶ Trigger:** User picks up a ticket
- **📤 Data:** Mode state transitions through: `RESEARCH` → `INNOVATE` → `PLAN`
- **Contract:** Ticket pickup initiates in `RESEARCH` (fetch ticket, read comments). The worklog file creation Write Gate requires `PLAN`/`EXECUTE` sequence.
- **⚠️ Edge Case:** Reopened ticket detection (files in `done/`) — the copy-back operation is a Write Gate requiring `EXECUTE` mode.

#### P-05: Mode Enforcement on Ticket Done
- **▶ Trigger:** User marks ticket done, requests Tempo logging
- **📤 Data:** Mode must be `EXECUTE` for Tempo API POST
- **Contract:** Reading worklog summary and proposing time = `PLAN` mode. Executing Tempo POST and moving files = `EXECUTE` mode.
- **⚠️ Edge Case:** User says "log 2 hours" without switching to EXECUTE — agent proposes in `PLAN`, waits for `MODE: EXECUTE` before HTTP POST.

#### P-06: Deviation Handling — Forced Revert to PLAN
- **▶ Trigger:** Unexpected issue during `EXECUTE` mode in any `devops-daily-protocol` operation
- **📤 Data:** Error context, deviation description
- **Contract:** Per `developer-protocol` rules: "If any issue arises that requires deviation from the plan, immediately revert to PLAN mode." This applies to all L2 operations.
- **⚠️ Edge Case:** Tempo API returns 401 during Ticket Done → revert to PLAN, surface credential issue, re-plan.

---

### 2.2 developer-protocol → jira-worklog-processor (6 patterns)

#### P-07: Mode Governs Worklog Section Population — FINDINGS
- **▶ Trigger:** Agent populates FINDINGS section in worklog
- **📤 Data:** Mode state = `RESEARCH`
- **Contract:** FINDINGS section can only be populated during `RESEARCH` mode. Content must be exclusively observations, data, code paths — no suggestions or solutions.
- **⚠️ Edge Case:** Agent discovers an obvious fix while writing findings — must NOT include it in FINDINGS. Note it for `INNOVATE` phase.

#### P-08: Mode Governs Worklog Section Population — PROPOSED SOLUTIONS
- **▶ Trigger:** Agent populates PROPOSED SOLUTIONS section
- **📤 Data:** Mode state = `INNOVATE`
- **Contract:** Solution options (A/B/C/D) with pros/cons can only be written during `INNOVATE` mode. No concrete implementation plans or code.
- **⚠️ Edge Case:** User asks "just pick the best one and do it" — agent must transition through `PLAN` before `EXECUTE`. Shortcutting is not permitted.

#### P-09: Mode Governs Worklog Section Population — PROPOSED ACTIONS
- **▶ Trigger:** Agent populates PROPOSED ACTIONS checklist
- **📤 Data:** Mode state = `PLAN`
- **Contract:** Action checklists (phased with gates G0-G4) require `PLAN` mode. Must include regression test steps per `developer-protocol` rules.
- **⚠️ Edge Case:** Plan modifies existing script → `IMPLEMENTATION CHECKLIST` must include regression test steps for all existing commands/features.

#### P-10: Mode Governs Worklog Section Population — ACTION LOG
- **▶ Trigger:** Agent appends entries to ACTION LOG
- **📤 Data:** Mode state = `EXECUTE`
- **Contract:** ACTION LOG entries are timestamped records of executed actions. Only populated during `EXECUTE` mode as steps are completed.
- **⚠️ Edge Case:** Agent logs an action that wasn't in the plan → immediate revert to `PLAN` mode per deviation handling.

#### P-11: Mode Governs PR Review Workflow
- **▶ Trigger:** User requests PR review
- **📤 Data:** Mode state = `RESEARCH` (reading diff, comparing to plan)
- **Contract:** PR review is a read-only analysis operation → `RESEARCH` mode. Updating worklog checkboxes (`[ ]` → `[~]`) and appending to PR.log are Write Gates requiring `PLAN`/`EXECUTE`.
- **⚠️ Edge Case:** PR review reveals out-of-scope changes — agent flags them but does NOT suggest corrections (that would require `INNOVATE`).

#### P-12: Regression Testing Requirement Injection
- **▶ Trigger:** Worklog PROPOSED ACTIONS modify an existing script or tool
- **📤 Data:** Regression test requirement from `developer-protocol`
- **Contract:** `developer-protocol` requires: "When the plan modifies an existing script or tool, the implementation checklist must include regression test steps." `jira-worklog-processor` must include these in PROPOSED ACTIONS.
- **⚠️ Edge Case:** Regression test execution exceeds 60 seconds → skip with documented reason per `developer-protocol` rules.

---

### 2.3 developer-protocol → jenkins-pipeline-architect (5 patterns)

#### P-13: Mode Enforcement on Jenkinsfile Creation
- **▶ Trigger:** User requests new Jenkinsfile or pipeline
- **📤 Data:** Mode sequence: `RESEARCH` (understand requirements) → `PLAN` (specify structure) → `EXECUTE` (write code)
- **Contract:** Pipeline code writing is forbidden in `RESEARCH` and `INNOVATE`. Detailed file paths and function names in `PLAN`. Actual Groovy code only in `EXECUTE`.
- **⚠️ Edge Case:** User provides example code in their prompt — agent can reference it in `RESEARCH`/`INNOVATE` but cannot write derived code until `EXECUTE`.

#### P-14: Mode Enforcement on Jenkinsfile Modification
- **▶ Trigger:** User requests changes to existing Jenkinsfile
- **📤 Data:** Mode must reach `PLAN` before any code changes
- **Contract:** Modifications must pass through full `PLAN` mode with implementation checklist before `EXECUTE`. This includes CPS refactoring, stage restructuring, and parameter changes.
- **⚠️ Edge Case:** "Just fix this one-liner" — still requires `PLAN` → `EXECUTE` sequence. No shortcuts for pipeline code.

#### P-15: Mode Enforcement on Shared Library Edits
- **▶ Trigger:** User edits `vars/*.groovy` shared library files
- **📤 Data:** Mode must be `EXECUTE` with approved plan
- **Contract:** `vars/` files affect all pipelines using that library. `developer-protocol` requires full plan with regression test steps for all consumers.
- **⚠️ Edge Case:** Change to `vars/postJiraComment.groovy` → must regression-test all pipelines that call `postJiraComment.start()`, `.completion()`, `.error()`, `.artifact()`.

#### P-16: Syntax Validation as EXECUTE Gate
- **▶ Trigger:** Any Jenkinsfile creation or edit completes in `EXECUTE` mode
- **📤 Data:** File path(s) to validate
- **Contract:** `syntax_check.groovy` must run after every pipeline edit. Failing syntax check → revert to `PLAN` mode (deviation handling). This is a mandatory step, not optional.
- **⚠️ Edge Case:** syntax_check only validates Groovy grammar, not Jenkins DSL — successful syntax check does NOT guarantee pipeline works. Note this limitation in ACTION LOG.

#### P-17: CPS/NonCPS Analysis in RESEARCH Mode
- **▶ Trigger:** User investigates CPS serialization issue or pipeline failure
- **📤 Data:** CPS diagnostic rules from `jenkins-pipeline-architect`
- **Contract:** In `RESEARCH` mode, agent can read pipeline code and identify CPS violations (e.g., `.each` in CPS context, non-serializable types). Suggesting fixes requires `INNOVATE`/`PLAN`.
- **⚠️ Edge Case:** Agent identifies a `_` variable scoping issue — can document the finding but cannot suggest the fix (`k` replacement) until `INNOVATE` mode.

---

### 2.4 devops-daily-protocol → jira-worklog-processor (8 patterns)

184:   1. `devops-daily-protocol` fetches ticket via `integrations/jira/jira-ticket-info.sh <KEY>`
185:   2. Checks for reopened ticket in `worklog/done/`
186:   3. Hands off to `jira-worklog-processor` to create `worklog/YYYY-MM-DD_<KEY>.log` using `worklog.template`
187:   4. `jira-worklog-processor` pre-populates TICKET header from JIRA response
188: - **⚠️ Edge Case — Reopened Ticket:** If `worklog/done/*_<KEY>*.log` exists, `devops-daily-protocol` offers to copy back. If user declines, `jira-worklog-processor` creates fresh worklog with new date prefix.
189: - **⚠️ Edge Case — Duplicate Worklogs:** If `worklog/*_<KEY>.log` already exists for today, warn user before creating a second worklog for the same ticket.
190: 
191: #### P-19: Investigation Update Handoff — FINDINGS
192: - **▶ Trigger:** `devops-daily-protocol` Investigation mode produces tool output (NRQL results, kubectl output, NR alerts)
193: - **📤 Data:** Raw tool output, investigation context
194: - **Contract:** `devops-daily-protocol` runs the tools; `jira-worklog-processor` formats results into numbered FINDINGS sub-sections with dotted separators. Raw data goes to `_raw.log` companion files.
195: - **⚠️ Edge Case — Large Output:** NRQL query returns 500+ rows → `jira-worklog-processor` creates `worklog/YYYY-MM-DD_<KEY>_<suffix>_raw.log` and references it from FINDINGS. Only summary goes in main worklog.
196: 
197: #### P-20: Investigation Update Handoff — PROPOSED SOLUTIONS
198: - **▶ Trigger:** Agent transitions from RESEARCH to INNOVATE during investigation
199: - **📤 Data:** FINDINGS summary, solution evaluation criteria
200: - **Contract:** `jira-worklog-processor` generates labeled options (OPTION A/B/C/D) with pros/cons and a RECOMMENDATION line. `devops-daily-protocol` manages the Write Gate for updating the file.
201: - **⚠️ Edge Case:** Only one viable solution → still document as OPTION A with rationale; include "No viable alternatives identified" note.
202: 
203: #### P-21: Investigation Update Handoff — PROPOSED ACTIONS
204: - **▶ Trigger:** Agent transitions from INNOVATE to PLAN during investigation
205: - **📤 Data:** Selected solution option, action scope
206: - **Contract:** `jira-worklog-processor` creates phased checklist with gates (G0-G4). `devops-daily-protocol` manages Write Gate. Complex tickets use gate system; simple tickets use PHASE 1/PHASE 2.
207: - **⚠️ Edge Case — Cross-Team Actions:** Actions requiring other teams (e.g., "Request CHG from ops") should be flagged with `BLOCKED` status and owner.
208: 
209: #### P-22: Ticket Done Handoff — Time Logging
210: - **▶ Trigger:** User says ticket is done or asks to log time
211: - **📤 Data:** Worklog file path, session summary, time estimate
212: - **Contract:**
213:   1. `devops-daily-protocol` reads worklog to summarize accomplishments
214:   2. `jira-worklog-processor` formats the Tempo comment from worklog content
215:   3. `devops-daily-protocol` proposes Tempo POST via Write Gate
216:   4. After approval: `devops-daily-protocol` executes POST, runs verify
217:   5. `jira-worklog-processor` updates TIME LOGGED section and STATUS to DONE
218:   6. `devops-daily-protocol` moves files to `worklog/done/`
219: - **⚠️ Edge Case — Partial Day Work:** User worked on ticket across multiple sessions → time should aggregate. Check `integrations/jira/jira-ticket-info.sh tempo` for existing entries.
220: 
221: #### P-23: Day End Handoff — Verification
222: - **▶ Trigger:** User ends day or requests daily summary
223: - **📤 Data:** `verify` output comparing worklog files vs Tempo entries
224: - **Contract:** `devops-daily-protocol` runs `verify`, identifies MATCHED / MISSING FROM TEMPO / MISSING FROM WORKLOG. For MISSING FROM TEMPO, offers to enter Ticket Done flow with `jira-worklog-processor`.
225: - **⚠️ Edge Case — `_raw.log` Files:** These are excluded from verify scanning. Only primary `YYYY-MM-DD_<KEY>.log` files are checked against Tempo.
226: 
227: #### P-24: Sub-Investigation Raw Log Handoff
228: - **▶ Trigger:** Investigation produces large data artifacts
229: - **📤 Data:** Raw output (NRQL tables, SSH manifests, kubectl dumps)
230: - **Contract:** `devops-daily-protocol` generates raw data via tool commands. `jira-worklog-processor` decides the suffix (`_oomkilled`, `_solr-logs`, etc.) and creates `_raw.log` companion file. Main worklog FINDINGS reference the raw file by path.
231: - **⚠️ Edge Case — Multiple Sub-Investigations:** Same ticket may have multiple `_raw.log` files. Each gets a unique suffix. All follow naming convention: `worklog/YYYY-MM-DD_<KEY>_<suffix>_raw.log`.
232: 
233: #### P-25: Cross-Ticket Reference Handoff
234: - **▶ Trigger:** JIRA ticket has linked issues or related tickets
235: - **📤 Data:** Related ticket keys, blocking/non-blocking status
236: - **Contract:** `devops-daily-protocol` fetches linked issue metadata via JIRA CLI. `jira-worklog-processor` adds RELATED TICKET section after header with status summary and worklog path reference.
237: - **⚠️ Edge Case — Circular Dependencies:** Ticket A blocks B which blocks A → flag both as BLOCKED with mutual reference.
238: 
239: ---
240: 
241: ### 2.5 devops-daily-protocol → jenkins-pipeline-architect (5 patterns)
242: 
243: #### P-26: Jenkins Failure Investigation Handoff
244: - **▶ Trigger:** Investigation mode identifies a Jenkins build failure
245: - **📤 Data:** Build URL, failure logs, Jenkinsfile path
246: - **Contract:**
247:   1. `devops-daily-protocol` detects Jenkins failure (from JIRA ticket, NR alert, or user report)
248:   2. Hands off to `jenkins-pipeline-architect` for:
249:      - Jenkinsfile inspection and CPS analysis
250:      - Build log parsing using structured logging patterns
251:      - Groovy syntax validation via `syntax_check.groovy`
252:   3. Results feed back into worklog FINDINGS via `jira-worklog-processor`
253: - **⚠️ Edge Case — No Access to Jenkins:** If `syntax_check.groovy` cannot locate the Jenkinsfile locally, agent must request the file path or fetch from SCM.
254: 
255: #### P-27: Pipeline Deployment Monitoring
256: - **▶ Trigger:** Jenkins deployment job runs, user wants to track status
257: - **📤 Data:** Build results, deployment targets, duration
258: - **Contract:** `jenkins-pipeline-architect` provides patterns for monitoring deployment jobs (async polling, timeout handling). `devops-daily-protocol` uses NR CLI to verify deployment health post-deploy.
259: - **⚠️ Edge Case — Deployment Timeout:** `withRetry` exceeds `maxAttempts` → `devops-daily-protocol` logs timeout in worklog ACTION LOG and triggers NR violations check.
260: 
261: #### P-28: NR Alert → Build Correlation
262: - **▶ Trigger:** NR violation detected during or after a Jenkins deployment
263: - **📤 Data:** NR alert data, recent deployment history
264: - **Contract:** `devops-daily-protocol` runs `integrations/newrelic/newrelic-info.sh violations` and `deployments <APP_ID>`. If a deployment correlates temporally with the alert, hands off to `jenkins-pipeline-architect` to inspect the deployment pipeline.
- **⚠️ Edge Case — False Correlation:** Deployment and alert coincide but are unrelated. Agent should note correlation in FINDINGS but flag uncertainty.

#### P-29: Kubernetes Issue → Pipeline Config Check
- **▶ Trigger:** kubectl diagnostics reveal pod failures potentially caused by pipeline-deployed artifacts
- **📤 Data:** Pod failure data (OOMKilled, CrashLoopBackOff), deployment name
- **Contract:** `devops-daily-protocol` identifies infrastructure issue via kubectl. If the failing pod was deployed by a Jenkins pipeline, `jenkins-pipeline-architect` inspects resource configuration, artifact versions, and Helm values in the pipeline.
- **⚠️ Edge Case — Non-Pipeline Deployments:** If the deployment was manual or via ArgoCD (not Jenkins), `jenkins-pipeline-architect` is not involved.

#### P-30: Pipeline Syntax Check During Investigation
- **▶ Trigger:** User investigates a Jenkinsfile bug or pipeline behavior
- **📤 Data:** Jenkinsfile path
- **Contract:** `devops-daily-protocol` in Investigation mode can invoke `jenkins-pipeline-architect`'s syntax validation as a read-only check (no modifications). Results go to worklog FINDINGS.
- **⚠️ Edge Case — JDK Version Mismatch:** the syntax check requires JDK 17 or lower. Run it through `scripts/syntax_check.sh`, which resolves a suitable JDK automatically. If none is found it exits 1 naming the required version. Invoking `syntax_check.groovy` directly under a newer JDK fails with `Unsupported class file major version <N>`.

---

### 2.6 jira-worklog-processor → jenkins-pipeline-architect (4 patterns)

#### P-31: CI Status Notification via postJiraComment
- **▶ Trigger:** Jenkins pipeline completes (success or failure)
- **📤 Data:** Build results map, duration, artifact summaries, issue key
- **Contract:** `jenkins-pipeline-architect` templates include `postJiraComment.start()`, `.completion()`, `.error()`, `.artifact()` calls that post CI status updates to JIRA ticket keys. These ticket keys are the same ones tracked in `jira-worklog-processor` worklogs.
- **⚠️ Edge Case — Stale Ticket Key:** Pipeline posts to a ticket that's already DONE/moved to `worklog/done/`. The JIRA comment still appears but the worklog is archived.

#### P-32: PR Review Cross-Reference with CI
- **▶ Trigger:** PR review workflow identifies CI-related changes
- **📤 Data:** Changed Jenkinsfile paths, CI status from `gh pr view`
- **Contract:** `jira-worklog-processor` PR review workflow checks if changed files include Jenkinsfiles. If so, the review should reference `jenkins-pipeline-architect` CPS rules and recommend syntax validation.
- **⚠️ Edge Case — PR modifies `vars/*.groovy`:** Shared library changes affect all consumers. Review should flag impact scope.

#### P-33: Worklog PROPOSED ACTIONS Include Pipeline Steps
- **▶ Trigger:** Ticket solution involves CI/CD changes
- **📤 Data:** Pipeline change plan
- **Contract:** `jira-worklog-processor` PROPOSED ACTIONS may include Jenkins-specific steps (create pipeline, modify Jenkinsfile, update shared library). These steps must reference `jenkins-pipeline-architect` patterns and include syntax validation as a gate.
- **⚠️ Edge Case:** Action item says "update Jenkinsfile" without specifying which patterns — agent should cross-reference `jenkins-pipeline-architect` rules (CPS, sandbox, etc.) when executing.

#### P-34: Build Artifact Tracking in Worklog
- **▶ Trigger:** Jenkins pipeline produces artifacts (JARs, AMIs, Docker images)
- **📤 Data:** Artifact versions, download URLs, fingerprints
- **Contract:** `jira-worklog-processor` logs artifact details in ACTION LOG entries. `jenkins-pipeline-architect` `postJiraComment.artifact()` posts the same info to JIRA.
- **⚠️ Edge Case — Artifact Mismatch:** Worklog records version 1.2.3 but JIRA comment shows 1.2.4 → data inconsistency. Use `archiveArtifacts` fingerprint for ground truth.

---

### 2.7 Reverse Handoffs (4 patterns)

#### P-35: jira-worklog-processor → devops-daily-protocol (Tempo Verification)
- **▶ Trigger:** After `jira-worklog-processor` updates TIME LOGGED section
- **📤 Data:** Expected Tempo entry details
- **Contract:** `devops-daily-protocol` runs `verify` to confirm Tempo entry exists. If discrepancy found, triggers correction flow.
- **⚠️ Edge Case:** Tempo API latency — entry may not appear immediately after POST. Wait 5 seconds before verify.

#### P-36: jenkins-pipeline-architect → devops-daily-protocol (Post-Deploy Health)
- **▶ Trigger:** Jenkins deployment completes
- **📤 Data:** Deployment metadata (app, version, environment)
- **Contract:** After deployment, `devops-daily-protocol` runs NR health checks (`app`, `hosts`, `violations`) to verify deployment didn't degrade service health.
- **⚠️ Edge Case:** New deployment has no NR data yet — wait for one monitoring cycle (5 minutes) before health check.

#### P-37: jenkins-pipeline-architect → jira-worklog-processor (Build Status Update)
- **▶ Trigger:** `postJiraComment` posts build status to JIRA
- **📤 Data:** JIRA comment with build results
- **Contract:** If a worklog exists for the ticket, `jira-worklog-processor` should update ACTION LOG with build outcome reference.
- **⚠️ Edge Case:** Build triggers automatically (SCM poll) without user session — no worklog update possible.

#### P-38: jira-worklog-processor → developer-protocol (Mode State Query)
- **▶ Trigger:** `jira-worklog-processor` needs to determine which worklog section to write
- **📤 Data:** Current mode from `developer-protocol`
- **Contract:** Before writing any worklog section, check current mode:
  - RESEARCH → FINDINGS only
  - INNOVATE → PROPOSED SOLUTIONS only
  - PLAN → PROPOSED ACTIONS only
  - EXECUTE → ACTION LOG only
- **⚠️ Edge Case:** User hasn't declared a mode → default to RESEARCH (read-only).

---

### 2.8 Self-Interactions (4 patterns)

#### P-39: developer-protocol — Mode Transition Validation
- **▶ Trigger:** User issues `MODE: <name>` command
- **Contract:** Validate that the transition is legal (any mode can transition to any other mode, but only via explicit user command). Declare new mode at start of response.
- **⚠️ Edge Case:** User says "MODE: EXECUTE" without having done PLAN → allowed but risky. Agent should warn that no plan exists.

#### P-40: devops-daily-protocol — Multi-Mode Session Management
- **▶ Trigger:** User works across multiple workflow modes in one session
- **Contract:** Each mode (Day Start, Ticket Pickup, Investigation, Ticket Done, Day End) maintains its own state. `prompt.log` tracks all modes used with TAB sub-sections.
- **⚠️ Edge Case:** User does Day Start, picks up ticket, then says "what else is on the board?" → re-enters Day Start without completing Ticket Pickup. Both modes remain active.

#### P-41: jira-worklog-processor — Multi-Worklog Session
- **▶ Trigger:** User works on multiple tickets in one session
- **Contract:** Each ticket has its own worklog file. `jira-worklog-processor` manages them independently. Cross-references between tickets use RELATED TICKET sections.
- **⚠️ Edge Case:** Two tickets for the same issue → agent should suggest linking them in JIRA before creating separate worklogs.

#### P-42: jenkins-pipeline-architect — Multi-Pipeline Consistency
- **▶ Trigger:** User modifies multiple Jenkinsfiles in one session
- **Contract:** Changes to shared patterns (credential IDs, deployment functions, shared library calls) must be consistent across all modified files. Syntax check runs on all modified files.
- **⚠️ Edge Case:** Changing `vars/postJiraComment.groovy` signature → must update all calling Jenkinsfiles in the same session.

---

### 2.9 Composite Workflows (3 patterns)

#### P-43: Full Ticket Lifecycle (L1→L2→L3→L4)
- **▶ Trigger:** User picks up a CI/CD-related JIRA ticket and works it through to completion
- **Flow:**
  ```
  User: "pick up DEVOPS-456"
       │
       ▼
  ┌─ L1: developer-protocol ──────────────────────────────────┐
  │  MODE: RESEARCH                                            │
  │  ┌─ L2: devops-daily-protocol ──────────────────────────┐  │
  │  │  Ticket Pickup: jira-ticket-info.sh DEVOPS-456        │  │
  │  │  ┌─ L3: jira-worklog-processor ───────────────────┐   │  │
  │  │  │  Create worklog from template                   │   │  │
  │  │  │  Populate TICKET header                         │   │  │
  │  │  └─────────────────────────────────────────────────┘   │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  MODE: RESEARCH (continued)                                  │
  │  ┌─ L2: Investigation ──────────────────────────────────┐   │
  │  │  NR CLI, kubectl, log analysis                        │   │
  │  │  ┌─ L4: jenkins-pipeline-architect ───────────────┐   │   │
  │  │  │  Inspect Jenkinsfile, CPS analysis             │   │   │
  │  │  └────────────────────────────────────────────────┘   │   │
  │  │  ┌─ L3: jira-worklog-processor ───────────────────┐   │   │
  │  │  │  Format FINDINGS from tool output              │   │   │
  │  │  └────────────────────────────────────────────────┘   │   │
  │  └───────────────────────────────────────────────────────┘   │
  │                                                              │
  │  MODE: INNOVATE                                              │
  │  ┌─ L3: jira-worklog-processor ──────────────────────────┐  │
  │  │  Generate PROPOSED SOLUTIONS (A/B/C)                   │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  MODE: PLAN                                                  │
  │  ┌─ L3: jira-worklog-processor ──────────────────────────┐  │
  │  │  Create PROPOSED ACTIONS with gates                    │  │
  │  │  Include regression test steps (L1 requirement)        │  │
  │  │  Include syntax_check.groovy gate (L4 requirement)     │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  MODE: EXECUTE                                               │
  │  ┌─ L2: devops-daily-protocol ──────────────────────────┐   │
  │  │  Write Gate: Edit Jenkinsfile                          │   │
  │  │  ┌─ L4: jenkins-pipeline-architect ───────────────┐    │   │
  │  │  │  Apply pipeline changes, run syntax_check      │    │   │
  │  │  └────────────────────────────────────────────────┘    │   │
  │  │  ┌─ L3: jira-worklog-processor ───────────────────┐    │   │
  │  │  │  Update ACTION LOG, STATUS                     │    │   │
  │  │  └────────────────────────────────────────────────┘    │   │
  │  └───────────────────────────────────────────────────────┘   │
  │                                                              │
  │  MODE: EXECUTE (Ticket Done)                                 │
  │  ┌─ L2: devops-daily-protocol ──────────────────────────┐   │
  │  │  Tempo API POST, verify, move to done/                 │   │
  │  │  ┌─ L3: jira-worklog-processor ───────────────────┐    │   │
  │  │  │  Update TIME LOGGED, STATUS = DONE             │    │   │
  │  │  └────────────────────────────────────────────────┘    │   │
  │  └───────────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────────┘
  ```

#### P-44: PR Review with CI Cross-Reference (L1→L3→L4)
- **▶ Trigger:** User says "review PR #123" for a PR that modifies pipeline code
- **Flow:**
  ```
  User: "review PR #123"
       │
       ▼
  ┌─ L1: MODE: RESEARCH ─────────────────────────────────────┐
  │  ┌─ L3: jira-worklog-processor ────────────────────────┐  │
  │  │  1. gh pr view #123 → extract metadata               │  │
  │  │  2. Extract ticket key from PR title/branch           │  │
  │  │  3. Find worklog for ticket key                       │  │
  │  │  4. Read worklog PROPOSED ACTIONS                     │  │
  │  │  5. gh pr diff #123                                   │  │
  │  │  6. Compare diff against worklog plan                 │  │
  │  │                                                       │  │
  │  │  If PR modifies Jenkinsfile or vars/*.groovy:         │  │
  │  │  ┌─ L4: jenkins-pipeline-architect ─────────────┐     │  │
  │  │  │  Validate CPS rules on changed files          │     │  │
  │  │  │  Check for sandbox compatibility              │     │  │
  │  │  │  Flag shared library impact scope             │     │  │
  │  │  └──────────────────────────────────────────────┘     │  │
  │  │                                                       │  │
  │  │  7. Produce structured review output                  │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                              │
  │  MODE: PLAN/EXECUTE (Write Gates)                            │
  │  ┌─ L3: jira-worklog-processor ────────────────────────┐    │
  │  │  8. Write Gate: Append to PR.log                      │    │
  │  │  9. Write Gate: Update worklog [ ] → [~]              │    │
  │  │  10. Update ACTION LOG with review notes              │    │
  │  └───────────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────────┘
  ```

#### P-45: Incident Response (L1→L2→L3→L4)
- **▶ Trigger:** NR violation or user reports production incident
- **Flow:**
  ```
  User: "production alert on app X"
       │
       ▼
  ┌─ L1: MODE: RESEARCH ─────────────────────────────────────┐
  │  ┌─ L2: devops-daily-protocol ──────────────────────────┐ │
  │  │  1. newrelic-info.sh violations                       │ │
  │  │  2. newrelic-info.sh alerts <APP_ID>                  │ │
  │  │  3. newrelic-info.sh deployments <APP_ID>             │ │
  │  │  4. kubectl get pods (check health)                   │ │
  │  │                                                       │ │
  │  │  If deployment correlation found:                     │ │
  │  │  ┌─ L4: jenkins-pipeline-architect ─────────────┐     │ │
  │  │  │  Inspect deployment pipeline                  │     │ │
  │  │  │  Check artifact version, config changes       │     │ │
  │  │  └──────────────────────────────────────────────┘     │ │
  │  │                                                       │ │
  │  │  ┌─ L3: jira-worklog-processor ─────────────────┐     │ │
  │  │  │  Create incident worklog                      │     │ │
  │  │  │  FINDINGS: NR data, kubectl output            │     │ │
  │  │  │  _raw.log: full NRQL results                  │     │ │
  │  │  └──────────────────────────────────────────────┘     │ │
  │  └───────────────────────────────────────────────────────┘ │
  │                                                             │
  │  MODE: INNOVATE → PLAN → EXECUTE (mitigation)              │
  └─────────────────────────────────────────────────────────────┘
  ```

### 2.10 ai-worklog-framework Integration (8 patterns)

#### P-46: Session Preflight
- **Trigger:** Session start
- **Contract:** Run `ai-worklog preflight`; BLOCKED stops dependent operations, DEGRADED is reported.

#### P-47: Ticket-Scoped Preflight
- **Trigger:** Ticket Pickup
- **Contract:** `ai-worklog preflight --ticket <KEY>` resolves catalog services, repositories, and prerequisites.

#### P-48: Ticket Preparation Handoff
- **Trigger:** Ticket key selected
- **Contract:** `ticket prepare` supplies worklog history, repositories, delivery paths, and preparation gaps to L3.

#### P-49: Structured State Mutation
- **Trigger:** Lifecycle state changes
- **Contract:** PLAN previews the state delta; EXECUTE applies `ai-worklog state ... --apply`; `delivery status` verifies read-only.

#### P-50: Diagnostic Evidence
- **Trigger:** A catalog diagnostic pack matches the investigation
- **Contract:** `diag run` creates redacted evidence; L3 references the bundle from FINDINGS or ACTION LOG.

#### P-51: Dual Delivery Representation
- **Trigger:** Structured or human delivery state changes
- **Contract:** JSON leads automation, worklog leads narrative, and contradictions must be surfaced rather than silently overwritten.

#### P-52: Daily Continuation
- **Trigger:** Day Start or Day End
- **Contract:** Framework reports consume `next_action`, blockers, and uncommitted state while JIRA remains board authority.

#### P-53: Closeout Handoff
- **Trigger:** Ticket Done
- **Contract:** `closeout report` precedes Tempo and archival Write Gates.

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
184:   1. `devops-daily-protocol` fetches ticket via `integrations/jira/jira-ticket-info.sh <KEY>`
185:   2. Checks for reopened ticket in `worklog/done/`
186:   3. Hands off to `jira-worklog-processor` to create `worklog/YYYY-MM-DD_<KEY>.log` using `worklog.template`
187:   4. `jira-worklog-processor` pre-populates TICKET header from JIRA response
188: - **⚠️ Edge Case — Reopened Ticket:** If `worklog/done/*_<KEY>*.log` exists, `devops-daily-protocol` offers to copy back. If user declines, `jira-worklog-processor` creates fresh worklog with new date prefix.
189: - **⚠️ Edge Case — Duplicate Worklogs:** If `worklog/*_<KEY>.log` already exists for today, warn user before creating a second worklog for the same ticket.
190: 
191: #### P-19: Investigation Update Handoff — FINDINGS
192: - **▶ Trigger:** `devops-daily-protocol` Investigation mode produces tool output (NRQL results, kubectl output, NR alerts)
193: - **📤 Data:** Raw tool output, investigation context
194: - **Contract:** `devops-daily-protocol` runs the tools; `jira-worklog-processor` formats results into numbered FINDINGS sub-sections with dotted separators. Raw data goes to `_raw.log` companion files.
195: - **⚠️ Edge Case — Large Output:** NRQL query returns 500+ rows → `jira-worklog-processor` creates `worklog/YYYY-MM-DD_<KEY>_<suffix>_raw.log` and references it from FINDINGS. Only summary goes in main worklog.
196: 
197: #### P-20: Investigation Update Handoff — PROPOSED SOLUTIONS
198: - **▶ Trigger:** Agent transitions from RESEARCH to INNOVATE during investigation
199: - **📤 Data:** FINDINGS summary, solution evaluation criteria
200: - **Contract:** `jira-worklog-processor` generates labeled options (OPTION A/B/C/D) with pros/cons and a RECOMMENDATION line. `devops-daily-protocol` manages the Write Gate for updating the file.
201: - **⚠️ Edge Case:** Only one viable solution → still document as OPTION A with rationale; include "No viable alternatives identified" note.
202: 
203: #### P-21: Investigation Update Handoff — PROPOSED ACTIONS
204: - **▶ Trigger:** Agent transitions from INNOVATE to PLAN during investigation
205: - **📤 Data:** Selected solution option, action scope
206: - **Contract:** `jira-worklog-processor` creates phased checklist with gates (G0-G4). `devops-daily-protocol` manages Write Gate. Complex tickets use gate system; simple tickets use PHASE 1/PHASE 2.
207: - **⚠️ Edge Case — Cross-Team Actions:** Actions requiring other teams (e.g., "Request CHG from ops") should be flagged with `BLOCKED` status and owner.
208: 
209: #### P-22: Ticket Done Handoff — Time Logging
210: - **▶ Trigger:** User says ticket is done or asks to log time
211: - **📤 Data:** Worklog file path, session summary, time estimate
212: - **Contract:**
213:   1. `devops-daily-protocol` reads worklog to summarize accomplishments
214:   2. `jira-worklog-processor` formats the Tempo comment from worklog content
215:   3. `devops-daily-protocol` proposes Tempo POST via Write Gate
216:   4. After approval: `devops-daily-protocol` executes POST, runs verify
217:   5. `jira-worklog-processor` updates TIME LOGGED section and STATUS to DONE
218:   6. `devops-daily-protocol` moves files to `worklog/done/`
219: - **⚠️ Edge Case — Partial Day Work:** User worked on ticket across multiple sessions → time should aggregate. Check `integrations/jira/jira-ticket-info.sh tempo` for existing entries.
220: 
221: #### P-23: Day End Handoff — Verification
222: - **▶ Trigger:** User ends day or requests daily summary
223: - **📤 Data:** `verify` output comparing worklog files vs Tempo entries
224: - **Contract:** `devops-daily-protocol` runs `verify`, identifies MATCHED / MISSING FROM TEMPO / MISSING FROM WORKLOG. For MISSING FROM TEMPO, offers to enter Ticket Done flow with `jira-worklog-processor`.
225: - **⚠️ Edge Case — `_raw.log` Files:** These are excluded from verify scanning. Only primary `YYYY-MM-DD_<KEY>.log` files are checked against Tempo.
226: 
227: #### P-24: Sub-Investigation Raw Log Handoff
228: - **▶ Trigger:** Investigation produces large data artifacts
229: - **📤 Data:** Raw output (NRQL tables, SSH manifests, kubectl dumps)
230: - **Contract:** `devops-daily-protocol` generates raw data via tool commands. `jira-worklog-processor` decides the suffix (`_oomkilled`, `_solr-logs`, etc.) and creates `_raw.log` companion file. Main worklog FINDINGS reference the raw file by path.
231: - **⚠️ Edge Case — Multiple Sub-Investigations:** Same ticket may have multiple `_raw.log` files. Each gets a unique suffix. All follow naming convention: `worklog/YYYY-MM-DD_<KEY>_<suffix>_raw.log`.
232: 
233: #### P-25: Cross-Ticket Reference Handoff
234: - **▶ Trigger:** JIRA ticket has linked issues or related tickets
235: - **📤 Data:** Related ticket keys, blocking/non-blocking status
236: - **Contract:** `devops-daily-protocol` fetches linked issue metadata via JIRA CLI. `jira-worklog-processor` adds RELATED TICKET section after header with status summary and worklog path reference.
237: - **⚠️ Edge Case — Circular Dependencies:** Ticket A blocks B which blocks A → flag both as BLOCKED with mutual reference.
238: 
239: ---
240: 
241: ### 2.5 devops-daily-protocol → jenkins-pipeline-architect (5 patterns)
242: 
243: #### P-26: Jenkins Failure Investigation Handoff
244: - **▶ Trigger:** Investigation mode identifies a Jenkins build failure
245: - **📤 Data:** Build URL, failure logs, Jenkinsfile path
246: - **Contract:**
247:   1. `devops-daily-protocol` detects Jenkins failure (from JIRA ticket, NR alert, or user report)
248:   2. Hands off to `jenkins-pipeline-architect` for:
249:      - Jenkinsfile inspection and CPS analysis
250:      - Build log parsing using structured logging patterns
251:      - Groovy syntax validation via `syntax_check.groovy`
252:   3. Results feed back into worklog FINDINGS via `jira-worklog-processor`
253: - **⚠️ Edge Case — No Access to Jenkins:** If `syntax_check.groovy` cannot locate the Jenkinsfile locally, agent must request the file path or fetch from SCM.
254: 
255: #### P-27: Pipeline Deployment Monitoring
256: - **▶ Trigger:** Jenkins deployment job runs, user wants to track status
257: - **📤 Data:** Build results, deployment targets, duration
258: - **Contract:** `jenkins-pipeline-architect` provides patterns for monitoring deployment jobs (async polling, timeout handling). `devops-daily-protocol` uses NR CLI to verify deployment health post-deploy.
259: - **⚠️ Edge Case — Deployment Timeout:** `withRetry` exceeds `maxAttempts` → `devops-daily-protocol` logs timeout in worklog ACTION LOG and triggers NR violations check.
260: 
261: #### P-28: NR Alert → Build Correlation
262: - **▶ Trigger:** NR violation detected during or after a Jenkins deployment
263: - **📤 Data:** NR alert data, recent deployment history
264: - **Contract:** `devops-daily-protocol` runs `integrations/newrelic/newrelic-info.sh violations` and `deployments <APP_ID>`. If a deployment correlates temporally with the alert, hands off to `jenkins-pipeline-architect` to inspect the deployment pipeline.
265: - **⚠️ Edge Case — False Correlation:** Deployment and alert coincide but are unrelated. Agent should note correlation in FINDINGS but flag uncertainty.
266: 
267: #### P-29: Kubernetes Issue → Pipeline Config Check
268: - **▶ Trigger:** kubectl diagnostics reveal pod failures potentially caused by pipeline-deployed artifacts
269: - **📤 Data:** Pod failure data (OOMKilled, CrashLoopBackOff), deployment name
270: - **Contract:** `devops-daily-protocol` identifies infrastructure issue via kubectl. If the failing pod was deployed by a Jenkins pipeline, `jenkins-pipeline-architect` inspects resource configuration, artifact versions, and Helm values in the pipeline.
271: - **⚠️ Edge Case — Non-Pipeline Deployments:** If the deployment was manual or via ArgoCD (not Jenkins), `jenkins-pipeline-architect` is not involved.
272: 
273: #### P-30: Pipeline Syntax Check During Investigation
274: - **▶ Trigger:** User investigates a Jenkinsfile bug or pipeline behavior
275: - **📤 Data:** Jenkinsfile path
276: - **Contract:** `devops-daily-protocol` in Investigation mode can invoke `jenkins-pipeline-architect`'s syntax validation as a read-only check (no modifications). Results go to worklog FINDINGS.
277: - **⚠️ Edge Case — JDK Version Mismatch:** the syntax check requires JDK 17 or lower. Run it through `scripts/syntax_check.sh`, which resolves a suitable JDK automatically. If none is found it exits 1 naming the required version. Invoking `syntax_check.groovy` directly under a newer JDK fails with `Unsupported class file major version <N>`.
278: 
279: ---
280: 
281: ### 2.6 jira-worklog-processor → jenkins-pipeline-architect (4 patterns)
282: 
283: #### P-31: CI Status Notification via postJiraComment
284: - **▶ Trigger:** Jenkins pipeline completes (success or failure)
285: - **📤 Data:** Build results map, duration, artifact summaries, issue key
286: - **Contract:** `jenkins-pipeline-architect` templates include `postJiraComment.start()`, `.completion()`, `.error()`, `.artifact()` calls that post CI status updates to JIRA ticket keys. These ticket keys are the same ones tracked in `jira-worklog-processor` worklogs.
287: - **⚠️ Edge Case — Stale Ticket Key:** Pipeline posts to a ticket that's already DONE/moved to `worklog/done/`. The JIRA comment still appears but the worklog is archived.
288: 
289: #### P-32: PR Review Cross-Reference with CI
290: - **▶ Trigger:** PR review workflow identifies CI-related changes
291: - **📤 Data:** Changed Jenkinsfile paths, CI status from `gh pr view`
292: - **Contract:** `jira-worklog-processor` PR review workflow checks if changed files include Jenkinsfiles. If so, the review should reference `jenkins-pipeline-architect` CPS rules and recommend syntax validation.
293: - **⚠️ Edge Case — PR modifies `vars/*.groovy`:** Shared library changes affect all consumers. Review should flag impact scope.
294: 
295: #### P-33: Worklog PROPOSED ACTIONS Include Pipeline Steps
296: - **▶ Trigger:** Ticket solution involves CI/CD changes
297: - **📤 Data:** Pipeline change plan
298: - **Contract:** `jira-worklog-processor` PROPOSED ACTIONS may include Jenkins-specific steps (create pipeline, modify Jenkinsfile, update shared library). These steps must reference `jenkins-pipeline-architect` patterns and include syntax validation as a gate.
299: - **⚠️ Edge Case:** Action item says "update Jenkinsfile" without specifying which patterns — agent should cross-reference `jenkins-pipeline-architect` rules (CPS, sandbox, etc.) when executing.
300: 
301: #### P-34: Build Artifact Tracking in Worklog
302: - **▶ Trigger:** Jenkins pipeline produces artifacts (JARs, AMIs, Docker images)
303: - **📤 Data:** Artifact versions, download URLs, fingerprints
304: - **Contract:** `jira-worklog-processor` logs artifact details in ACTION LOG entries. `jenkins-pipeline-architect` `postJiraComment.artifact()` posts the same info to JIRA.
305: - **⚠️ Edge Case — Artifact Mismatch:** Worklog records version 1.2.3 but JIRA comment shows 1.2.4 → data inconsistency. Use `archiveArtifacts` fingerprint for ground truth.
306: 
307: ---
308: 
309: ### 2.7 Reverse Handoffs (4 patterns)
310: 
311: #### P-35: jira-worklog-processor → devops-daily-protocol (Tempo Verification)
312: - **▶ Trigger:** After `jira-worklog-processor` updates TIME LOGGED section
313: - **📤 Data:** Expected Tempo entry details
314: - **Contract:** `devops-daily-protocol` runs `verify` to confirm Tempo entry exists. If discrepancy found, triggers correction flow.
315: - **⚠️ Edge Case:** Tempo API latency — entry may not appear immediately after POST. Wait 5 seconds before verify.
316: 
317: #### P-36: jenkins-pipeline-architect → devops-daily-protocol (Post-Deploy Health)
318: - **▶ Trigger:** Jenkins deployment completes
319: - **📤 Data:** Deployment metadata (app, version, environment)
320: - **Contract:** After deployment, `devops-daily-protocol` runs NR health checks (`app`, `hosts`, `violations`) to verify deployment didn't degrade service health.
321: - **⚠️ Edge Case:** New deployment has no NR data yet — wait for one monitoring cycle (5 minutes) before health check.
322: 
323: #### P-37: jenkins-pipeline-architect → jira-worklog-processor (Build Status Update)
324: - **▶ Trigger:** `postJiraComment` posts build status to JIRA
325: - **📤 Data:** JIRA comment with build results
326: - **Contract:** If a worklog exists for the ticket, `jira-worklog-processor` should update ACTION LOG with build outcome reference.
327: - **⚠️ Edge Case:** Build triggers automatically (SCM poll) without user session — no worklog update possible.
328: 
329: #### P-38: jira-worklog-processor → developer-protocol (Mode State Query)
330: - **▶ Trigger:** `jira-worklog-processor` needs to determine which worklog section to write
331: - **📤 Data:** Current mode from `developer-protocol`
332: - **Contract:** Before writing any worklog section, check current mode:
333:   - RESEARCH → FINDINGS only
334:   - INNOVATE → PROPOSED SOLUTIONS only
335:   - PLAN → PROPOSED ACTIONS only
336:   - EXECUTE → ACTION LOG only
337: - **⚠️ Edge Case:** User hasn't declared a mode → default to RESEARCH (read-only).
338: 
339: ---
340: 
341: ### 2.8 Self-Interactions (4 patterns)
342: 
343: #### P-39: developer-protocol — Mode Transition Validation
344: - **▶ Trigger:** User issues `MODE: <name>` command
345: - **Contract:** Validate that the transition is legal (any mode can transition to any other mode, but only via explicit user command). Declare new mode at start of response.
346: - **⚠️ Edge Case:** User says "MODE: EXECUTE" without having done PLAN → allowed but risky. Agent should warn that no plan exists.
347: 
348: #### P-40: devops-daily-protocol — Multi-Mode Session Management
349: - **▶ Trigger:** User works across multiple workflow modes in one session
350: - **Contract:** Each mode (Day Start, Ticket Pickup, Investigation, Ticket Done, Day End) maintains its own state. `prompt.log` tracks all modes used with TAB sub-sections.
351: - **⚠️ Edge Case:** User does Day Start, picks up ticket, then says "what else is on the board?" → re-enters Day Start without completing Ticket Pickup. Both modes remain active.
352: 
353: #### P-41: jira-worklog-processor — Multi-Worklog Session
354: - **▶ Trigger:** User works on multiple tickets in one session
355: - **Contract:** Each ticket has its own worklog file. `jira-worklog-processor` manages them independently. Cross-references between tickets use RELATED TICKET sections.
356: - **⚠️ Edge Case:** Two tickets for the same issue → agent should suggest linking them in JIRA before creating separate worklogs.
357: 
358: #### P-42: jenkins-pipeline-architect — Multi-Pipeline Consistency
359: - **▶ Trigger:** User modifies multiple Jenkinsfiles in one session
360: - **Contract:** Changes to shared patterns (credential IDs, deployment functions, shared library calls) must be consistent across all modified files. Syntax check runs on all modified files.
361: - **⚠️ Edge Case:** Changing `vars/postJiraComment.groovy` signature → must update all calling Jenkinsfiles in the same session.
362: 
363: ---
364: 
365: ### 2.9 Composite Workflows (3 patterns)
366: 
367: #### P-43: Full Ticket Lifecycle (L1→L2→L3→L4)
368: - **▶ Trigger:** User picks up a CI/CD-related JIRA ticket and works it through to completion
369: - **Flow:**
370:   ```
371:   User: "pick up DEVOPS-456"
372:        │
373:        ▼
374:   ┌─ L1: developer-protocol ──────────────────────────────────┐
375:   │  MODE: RESEARCH                                            │
376:   │  ┌─ L2: devops-daily-protocol ──────────────────────────┐  │
377:   │  │  Ticket Pickup: jira-ticket-info.sh DEVOPS-456        │  │
378:   │  │  ┌─ L3: jira-worklog-processor ───────────────────┐   │  │
379:   │  │  │  Create worklog from template                   │   │  │
380:   │  │  │  Populate TICKET header                         │   │  │
381:   │  │  └─────────────────────────────────────────────────┘   │  │
382:   │  └────────────────────────────────────────────────────────┘  │
383:   │                                                              │
384:   │  MODE: RESEARCH (continued)                                  │
385:   │  ┌─ L2: Investigation ──────────────────────────────────┐   │
386:   │  │  NR CLI, kubectl, log analysis                        │   │
387:   │  │  ┌─ L4: jenkins-pipeline-architect ───────────────┐   │   │
388:   │  │  │  Inspect Jenkinsfile, CPS analysis             │   │   │
389:   │  │  └────────────────────────────────────────────────┘   │   │
390:   │  │  ┌─ L3: jira-worklog-processor ───────────────────┐   │   │
391:   │  │  │  Format FINDINGS from tool output              │   │   │
392:   │  │  └────────────────────────────────────────────────┘   │   │
393:   │  └───────────────────────────────────────────────────────┘   │
394:   │                                                              │
395:   │  MODE: INNOVATE                                              │
396:   │  ┌─ L3: jira-worklog-processor ──────────────────────────┐  │
397:   │  │  Generate PROPOSED SOLUTIONS (A/B/C)                   │  │
398:   │  └────────────────────────────────────────────────────────┘  │
399:   │                                                              │
400:   │  MODE: PLAN                                                  │
401:   │  ┌─ L3: jira-worklog-processor ──────────────────────────┐  │
402:   │  │  Create PROPOSED ACTIONS with gates                    │  │
403:   │  │  Include regression test steps (L1 requirement)        │  │
404:   │  │  Include syntax_check.groovy gate (L4 requirement)     │  │
405:   │  └────────────────────────────────────────────────────────┘  │
406:   │                                                              │
407:   │  MODE: EXECUTE                                               │
408:   │  ┌─ L2: devops-daily-protocol ──────────────────────────┐   │
409:   │  │  Write Gate: Edit Jenkinsfile                          │   │
410:   │  │  ┌─ L4: jenkins-pipeline-architect ───────────────┐    │   │
411:   │  │  │  Apply pipeline changes, run syntax_check      │    │   │
412:   │  │  └────────────────────────────────────────────────┘    │   │
413:   │  │  ┌─ L3: jira-worklog-processor ───────────────────┐    │   │
414:   │  │  │  Update ACTION LOG, STATUS                     │    │   │
415:   │  │  └────────────────────────────────────────────────┘    │   │
416:   │  └───────────────────────────────────────────────────────┘   │
417:   │                                                              │
418:   │  MODE: EXECUTE (Ticket Done)                                 │
419:   │  ┌─ L2: devops-daily-protocol ──────────────────────────┐   │
420:   │  │  Tempo API POST, verify, move to done/                 │   │
421:   │  │  ┌─ L3: jira-worklog-processor ───────────────────┐    │   │
422:   │  │  │  Update TIME LOGGED, STATUS = DONE             │    │   │
423:   │  │  └────────────────────────────────────────────────┘    │   │
424:   │  └───────────────────────────────────────────────────────┘   │
425:   └──────────────────────────────────────────────────────────────┘
426:   ```
427: 
428: #### P-44: PR Review with CI Cross-Reference (L1→L3→L4)
429: - **▶ Trigger:** User says "review PR #123" for a PR that modifies pipeline code
430: - **Flow:**
431:   ```
432:   User: "review PR #123"
433:        │
434:        ▼
435:   ┌─ L1: MODE: RESEARCH ─────────────────────────────────────┐
436:   │  ┌─ L3: jira-worklog-processor ────────────────────────┐  │
437:   │  │  1. gh pr view #123 → extract metadata               │  │
438:   │  │  2. Extract ticket key from PR title/branch           │  │
439:   │  │  3. Find worklog for ticket key                       │  │
440:   │  │  4. Read worklog PROPOSED ACTIONS                     │  │
441:   │  │  5. gh pr diff #123                                   │  │
442:   │  │  6. Compare diff against worklog plan                 │  │
443:   │  │                                                       │  │
444:   │  │  If PR modifies Jenkinsfile or vars/*.groovy:         │  │
445:   │  │  ┌─ L4: jenkins-pipeline-architect ─────────────┐     │  │
446:   │  │  │  Validate CPS rules on changed files          │     │  │
447:   │  │  │  Check for sandbox compatibility              │     │  │
448:   │  │  │  Flag shared library impact scope             │     │  │
449:   │  │  └──────────────────────────────────────────────┘     │  │
450:   │  │                                                       │  │
451:   │  │  7. Produce structured review output                  │  │
452:   │  └───────────────────────────────────────────────────────┘  │
453:   │                                                              │
454:   │  MODE: PLAN/EXECUTE (Write Gates)                            │
455:   │  ┌─ L3: jira-worklog-processor ────────────────────────┐    │
456:   │  │  8. Write Gate: Append to PR.log                      │    │
457:   │  │  9. Write Gate: Update worklog [ ] → [~]              │    │
458:   │  │  10. Update ACTION LOG with review notes              │    │
459:   │  └───────────────────────────────────────────────────────┘   │
460:   └──────────────────────────────────────────────────────────────┘
461:   ```
462: 
463: #### P-45: Incident Response (L1→L2→L3→L4)
464: - **▶ Trigger:** NR violation or user reports production incident
465: - **Flow:**
466:   ```
467:   User: "production alert on app X"
468:        │
469:        ▼
470:   ┌─ L1: MODE: RESEARCH ─────────────────────────────────────┐
471:   │  ┌─ L2: devops-daily-protocol ──────────────────────────┐ │
472:   │  │  1. newrelic-info.sh violations                       │ │
473:   │  │  2. newrelic-info.sh alerts <APP_ID>                  │ │
474:   │  │  3. newrelic-info.sh deployments <APP_ID>             │ │
475:   │  │  4. kubectl get pods (check health)                   │ │
476:   │  │                                                       │ │
477:   │  │  If deployment correlation found:                     │ │
478:   │  │  ┌─ L4: jenkins-pipeline-architect ─────────────┐     │ │
479:   │  │  │  Inspect deployment pipeline                  │     │ │
480:   │  │  │  Check artifact version, config changes       │     │ │
481:   │  │  └──────────────────────────────────────────────┘     │ │
482:   │  │                                                       │ │
483:   │  │  ┌─ L3: jira-worklog-processor ─────────────────┐     │ │
484:   │  │  │  Create incident worklog                      │     │ │
485:   │  │  │  FINDINGS: NR data, kubectl output            │     │ │
486:   │  │  │  _raw.log: full NRQL results                  │     │ │
487:   │  │  └──────────────────────────────────────────────┘     │ │
488:   │  └───────────────────────────────────────────────────────┘ │
489:   │                                                             │
490:   │  MODE: INNOVATE → PLAN → EXECUTE (mitigation)              │
491:   └─────────────────────────────────────────────────────────────┘
492:   ```
493: 
494: ### 2.10 ai-worklog-framework Integration (8 patterns)
495: 
496: #### P-46: Session Preflight
497: - **Trigger:** Session start
498: - **Contract:** Run `ai-worklog preflight`; BLOCKED stops dependent operations, DEGRADED is reported.
499: 
500: #### P-47: Ticket-Scoped Preflight
501: - **Trigger:** Ticket Pickup
502: - **Contract:** `ai-worklog preflight --ticket <KEY>` resolves catalog services, repositories, and prerequisites.
503: 
504: #### P-48: Ticket Preparation Handoff
505: - **Trigger:** Ticket key selected
506: - **Contract:** `ticket prepare` supplies worklog history, repositories, delivery paths, and preparation gaps to L3.
507: 
508: #### P-49: Structured State Mutation
509: - **Trigger:** Lifecycle state changes
510: - **Contract:** PLAN previews the state delta; EXECUTE applies `ai-worklog state ... --apply`; `delivery status` verifies read-only.
511: 
512: #### P-50: Diagnostic Evidence
513: - **Trigger:** A catalog diagnostic pack matches the investigation
514: - **Contract:** `diag run` creates redacted evidence; L3 references the bundle from FINDINGS or ACTION LOG.
515: 
516: #### P-51: Dual Delivery Representation
517: - **Trigger:** Structured or human delivery state changes
518: - **Contract:** JSON leads automation, worklog leads narrative, and contradictions must be surfaced rather than silently overwritten.
519: 
520: #### P-52: Daily Continuation
521: - **Trigger:** Day Start or Day End
522: - **Contract:** Framework reports consume `next_action`, blockers, and uncommitted state while JIRA remains board authority.
523: 
524: #### P-53: Closeout Handoff
525: - **Trigger:** Ticket Done
526: - **Contract:** `closeout report` precedes Tempo and archival Write Gates.
527: 
528: ---
529: 
530: ## 3. Data Flow & Workspace Artifact Ownership
531: 
532: ```
533: [User Request]
534:       │
535:       ▼
536: ┌───────────────────────────┐
537: │ developer-protocol        │  <-- Enforces Mode (e.g. RESEARCH)
538: └─────────────┬─────────────┘
539:               │
540:               ▼
541: ┌───────────────────────────┐     Reads/Writes     ┌───────────────────────────┐
542: │ devops-daily-protocol     │ ──────────────────> │ integrations/             │ (JIRA CLI, NR CLI)
543: └─────────────┬─────────────┘                      └───────────────────────────┘
544:               │ Hand-off
545:               ▼
546: ┌───────────────────────────┐     Reads Template   ┌───────────────────────────┐
547: │ jira-worklog-processor    │ ──────────────────> │ skills/.../worklog.template│
548: └─────────────┬─────────────┘                      └───────────────────────────┘
549:               │ Formats & Saves
550:               ▼
551: ┌───────────────────────────┐     Appends Audit    ┌───────────────────────────┐
552: │ worklog/YYYY-MM-DD_*.log  │ ──────────────────> │ prompt.log                │
553: └───────────────────────────┘                      └───────────────────────────┘
554: ```
555: 
556: ### Artifact Ownership Table
557: 
558: | Artifact | Owner (Content) | Owner (Lifecycle) | Read By |
559: |----------|----------------|-------------------|---------|
560: | `worklog/YYYY-MM-DD_<KEY>.log` | `jira-worklog-processor` | `devops-daily-protocol` | All skills |
561: | `worklog/YYYY-MM-DD_<KEY>_raw.log` | `jira-worklog-processor` | `devops-daily-protocol` | `jira-worklog-processor` |
562: | `worklog/done/*` | (archived) | `devops-daily-protocol` | `jira-worklog-processor` (reopened check) |
563: | `worklog/tickets.log` | `devops-daily-protocol` | `devops-daily-protocol` | All skills |
564: | `prompt.log` | All skills (append-only) | `devops-daily-protocol` | All skills |
565: | `PR.log` | `jira-worklog-processor` | `jira-worklog-processor` | All skills |
566: | `worklog.template` | `jira-worklog-processor` | User-maintained | `jira-worklog-processor` |
567: | `ticket-pickup.prompt` | `jira-worklog-processor` | User-maintained | `jira-worklog-processor` |
568: | `.ai-worklog/state/<KEY>.json` | `ai-worklog-framework` schema | `devops-daily-protocol` through Write Gates | Daily, delivery, and closeout reports |
569: | `.ai-worklog/evidence/*` | `ai-worklog-framework` | Runtime workspace | Investigation and delivery routines |
570: | `.ai-worklog/config.json` | User/workspace | `ai-worklog workspace init` | Framework commands |
571: | `syntax_check.groovy` | `jenkins-pipeline-architect` | `jenkins-pipeline-architect` | `jenkins-pipeline-architect` |
572: | `tmp/<KEY>/` | `jira-worklog-processor` | `jira-worklog-processor` | All skills |
573: | Jenkinsfiles | `jenkins-pipeline-architect` | Workspace/SCM | `jenkins-pipeline-architect` |
574: | `vars/*.groovy` | `jenkins-pipeline-architect` | Workspace/SCM | `jenkins-pipeline-architect` |
575: 
576: ### Shared Artifact Conflict Rules
577: 
578: 1. **`prompt.log`** is append-only — no skill may edit or delete existing entries
579: 2. **Worklog files** — only one skill writes at a time; `devops-daily-protocol` manages file locks via Write Gate sequencing
580: 3. **Template files** (`worklog.template`, `ticket-pickup.prompt`) — agent reads only, user maintains
581: 4. **`_raw.log` files** — excluded from `verify` scanning and Tempo correlation
582: 
583: ---
584: 
585: ## 4. Decision Tree for Skill Activation
586: 
587: When a user prompt is received, evaluate in sequence:
588: 
589: ```
590:                             ┌──────────────────────┐
591:                             │   User Prompt        │
592:                             └──────────┬───────────┘
593:                                        │
594:                          ┌─────────────▼──────────────┐
595:                     ┌────┤ Contains Jenkins/CI/CD/     │────┐
596:                     │YES │ Groovy pipeline keywords?   │ NO │
597:                     │    └────────────────────────────┘    │
598:                     ▼                                       ▼
599:           Activate L4:                          ┌──────────────────────┐
600:           jenkins-pipeline-architect       ┌────┤ Contains ticket key, │────┐
601:           + L1 if code mods planned        │YES │ "pick up", "log time",│ NO │
602:                                            │    │ "work status"?       │    │
603:                                            ▼    └──────────────────────┘    ▼
604:                                  Activate L2:                    ┌─────────────────┐
605:                                  devops-daily-protocol      ┌───┤ Contains MODE:  │───┐
606:                                  + L3 for worklog content   │YES│ constraint?     │NO │
607:                                  + L1 for mode governance   │   └─────────────────┘   │
608:                                                             ▼                          ▼
609:                                                   Enforce L1:            Activate L1:
610:                                                   developer-protocol     developer-protocol
611:                                                   on top of all          lifecycle discipline
612:                                                   active skills          on target workspace
613: ```
614: 
615: ### Activation Matrix Quick Reference
616: 
617: | User Says | L1 | L2 | L3 | L4 |
618: |-----------|----|----|----|----|
619: | "what should I work on?" | ✅ RESEARCH | ✅ Day Start | ○ | ○ |
620: | "pick up DEVOPS-123" | ✅ RESEARCH→PLAN | ✅ Ticket Pickup | ✅ Create worklog | ○ |
621: | "investigate the OOM issue" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ○ |
622: | "the Jenkins build failed" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ✅ Pipeline analysis |
623: | "create a Jenkinsfile for deploy" | ✅ Full cycle | ○ | ○ | ✅ Pipeline creation |
624: | "review PR #45" | ✅ RESEARCH | ○ | ✅ PR Review | ✅ If PR has Jenkinsfile |
625: | "log 2 hours on DEVOPS-123" | ✅ EXECUTE | ✅ Ticket Done | ✅ Time logging | ○ |
626: | "end of day summary" | ✅ RESEARCH | ✅ Day End | ○ | ○ |
627: | "MODE: PLAN" | ✅ Transition | ○ | ○ | ○ |
628: | "refactor this function" | ✅ Full cycle | ○ | ○ | ○ |
629: | "PR #45 merged" | ✅ EXECUTE | ○ | ✅ Merge follow-up | ○ |
630: 
631: ---
632: 
633: ## 5. Edge Cases & Conflict Resolution
634: 
635: ### 5.1 Conflicting Modes
636: 
637: | Conflict | Resolution |
638: |----------|------------|
639: | User requests Write Gate in RESEARCH mode | Deny. Require `MODE: PLAN` before proposing, `MODE: EXECUTE` before performing. |
640: | User says "just do it" without PLAN | Agent must still propose in PLAN format. "I need to plan this first — switching to PLAN mode." |
641: | Two skills want to write to same worklog section | Sequenced by Write Gate — only one Write Gate active at a time. |
642: | User switches mode mid-Write Gate | Cancel current Write Gate. Re-evaluate in new mode. |
643: 
644: ### 5.2 Duplicate Worklogs
645: 
646: | Scenario | Resolution |
647: |----------|------------|
648: | `worklog/2026-07-28_DEVOPS-123.log` already exists, user picks up same ticket | Warn: "Worklog already exists for today. Continue updating existing file, or create `_v2` suffix?" |
649: | Worklog in `done/` and `worklog/` for same ticket | `done/` file is stale. Active file in `worklog/` takes precedence. |
650: | Two worklogs for same ticket, different dates | Both are valid (multi-day work). Cross-reference them in RELATED TICKET section. |
651: 
652: ### 5.3 API Limits & Failures
653: 
654: | Failure | Skill | Recovery |
655: |---------|-------|----------|
656: | JIRA CLI returns empty/error | `devops-daily-protocol` | Retry once. If still failing, log error in worklog FINDINGS and continue with manual data. |
657: | Tempo API 401 Unauthorized | `devops-daily-protocol` | Check `integrations/jira/credentials`. Surface to user. Do not retry with same token. |
658: | Tempo API 429 Rate Limited | `devops-daily-protocol` | Wait 60 seconds, retry with exponential backoff (max 3 attempts). |
659: | NR CLI returns no data | `devops-daily-protocol` | Log "No NR data available" in FINDINGS. Suggest manual NR UI check. |
660: | `gh` CLI not authenticated | `jira-worklog-processor` | PR review workflow fails gracefully. Log error, suggest `gh auth login`. |
661: | `syntax_check` JDK error | `jenkins-pipeline-architect` | JDK too new. Suggest running `scripts/syntax_check.sh`, or setting `JAVA_HOME` to a JDK 17 install. |
662: | Artifactory Storage API timeout | `jenkins-pipeline-architect` | Active Choice parameter returns fallback: `["ERROR: timeout", "1.0.0"]`. |
663: 
664: ### 5.4 Prompt.log Conflicts
665: 
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
| `PR.log` | `jira-worklog-processor` | `jira-worklog-processor` | All skills |
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

| User Says | L1 | L2 | L3 | L4 |
|-----------|----|----|----|----|
| "what should I work on?" | ✅ RESEARCH | ✅ Day Start | ○ | ○ |
| "pick up DEVOPS-123" | ✅ RESEARCH→PLAN | ✅ Ticket Pickup | ✅ Create worklog | ○ |
| "investigate the OOM issue" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ○ |
| "the Jenkins build failed" | ✅ RESEARCH | ✅ Investigation | ✅ Format FINDINGS | ✅ Pipeline analysis |
| "create a Jenkinsfile for deploy" | ✅ Full cycle | ○ | ○ | ✅ Pipeline creation |
| "review PR #45" | ✅ RESEARCH | ○ | ✅ PR Review | ✅ If PR has Jenkinsfile |
| "log 2 hours on DEVOPS-123" | ✅ EXECUTE | ✅ Ticket Done | ✅ Time logging | ○ |
| "end of day summary" | ✅ RESEARCH | ✅ Day End | ○ | ○ |
| "MODE: PLAN" | ✅ Transition | ○ | ○ | ○ |
| "refactor this function" | ✅ Full cycle | ○ | ○ | ○ |
| "PR #45 merged" | ✅ EXECUTE | ○ | ✅ Merge follow-up | ○ |

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
| Tempo API 401 Unauthorized | `devops-daily-protocol` | Check `integrations/jira/credentials`. Surface to user. Do not retry with same token. |
| Tempo API 429 Rate Limited | `devops-daily-protocol` | Wait 60 seconds, retry with exponential backoff (max 3 attempts). |
| NR CLI returns no data | `devops-daily-protocol` | Log "No NR data available" in FINDINGS. Suggest manual NR UI check. |
| `gh` CLI not authenticated | `jira-worklog-processor` | PR review workflow fails gracefully. Log error, suggest `gh auth login`. |
| `syntax_check` JDK error | `jenkins-pipeline-architect` | JDK too new. Suggest running `scripts/syntax_check.sh`, or setting `JAVA_HOME` to a JDK 17 install. |
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
         └── Read operations (JIRA CLI, NR CLI, file reads, kubectl get) bypass Write Gate
         
CHECK 3: Is the agent following the 5-step protocol?
         └── ANNOUNCE → PREVIEW → WAIT → EXECUTE → VERIFY
         └── Missing any step = protocol violation
```

### Symptom: Worklog Sections Not Populating

```
CHECK 1: Is the correct mode active for the target section?
         └── FINDINGS → RESEARCH mode
         └── PROPOSED SOLUTIONS → INNOVATE mode
         └── PROPOSED ACTIONS → PLAN mode
         └── ACTION LOG → EXECUTE mode
         
CHECK 2: Is worklog.template accessible?
         └── Path: skills/jira-worklog-processor/worklog.template
         
CHECK 3: Is the worklog file path correct?
         └── Pattern: worklog/YYYY-MM-DD_<KEY>.log
         └── Date must be today's date
```

### Symptom: Jenkins Syntax Check Fails

```
CHECK 1: Is a JDK 17 (or lower) installed?
         └── Groovy 3.x cannot read class files from newer JDKs
         └── macOS: /usr/libexec/java_home -v 17
         └── Linux: $JVM_SEARCH_PATH (default /usr/lib/jvm)
         └── Any platform: export JAVA_HOME_17

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
