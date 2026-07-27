# Worklog Examples — Real Ticket Patterns

Concrete examples from completed and active worklogs showing how each ticket
type maps to the worklog structure.

## Example 1: Distributed Tracing (KD-6945) — Research-Heavy

**Ticket type**: Platform feature — observability/tracing across 28 microservices.

**Key patterns used**:
- Architecture overview finding (28 services cataloged by layer)
- Current state audit (OTel stack component table)
- Gap analysis (6 gaps ranked by severity)
- Key files listing (6 repo paths)
- 3 solution options (A: complete existing, B: full platform, C: Datadog)
- 6 risk considerations
- Related ticket cross-reference (KD-6863 gateway migration)
- 8 referenced repositories

**Worklog sections populated**:
```
TICKET header (15 fields + description + comments + linked + time)
RELATED TICKET: KD-6863 (impact analysis, non-blocking)
REFERENCED REPOSITORIES (8 repos with roles)
FINDINGS (5 numbered: architecture, stack audit, done%, gaps, key files)
PROPOSED SOLUTIONS (3 options with pros/cons + recommendation)
RISK CONSIDERATIONS (6 risks with mitigations)
PROPOSED ACTIONS (7 action items)
ACTION LOG (1 entry — research session)
STATUS (research complete, awaiting decision + clarification)
TIME LOGGED (2 entries — reporter + investigator)
```

**How research was done**:
1. Fetched ticket from JIRA — parsed description (Polish, translated)
2. Checked 8 repos for OTel configs, Helm values, Traefik settings
3. Cross-referenced KD-6863 worklog (669 lines) for routing context
4. Built component table from live cluster + repo configs
5. Identified gaps by comparing desired state vs current

**Time**: 30m for full research + worklog creation

---

## Example 2: CUE-UM Monitoring (DEVOPS-796) — Infrastructure Rollout

**Ticket type**: EC2 monitoring deployment — multi-environment phased rollout.

**Key patterns used**:
- Environment inventory (3 envs with instance IDs, IPs, versions)
- Gap summary table (5 layers × 3 environments)
- 5 solution options with hybrid recommendation
- Gate-based phases (G0–G4)
- tmp/ artifacts: install script, flex configs, verify script, rollout plan
- Implementation summary in Polish (for Jira close-out comment)
- Cross-ticket reference (DEVOPS-795 AMI alignment)

**Worklog sections populated**:
```
TICKET header (with English translation of summary)
FINDINGS (6 numbered: context, monitoring target, NR state, env inventory, repos, gap table)
INNOVATE — SOLUTION OPTIONS (5 options A–E + recommendation)
PROPOSED SOLUTIONS (selected approach detail)
RISK CONSIDERATIONS (6 risks)
PROPOSED ACTIONS (4 phases: PREP, Phase 1-3, CLOSE with checkboxes)
ACTION LOG (3 dated entries with SSH probes, blocker discovery)
STATUS (MODE: PLAN with spec reference)
TIME LOGGED (1 Tempo entry)
IMPLEMENTATION SUMMARY (Polish, with rollout status table)
```

**tmp/ artifacts created**:
```
tmp/DEVOPS-796/
├── install-cue-um-flex.sh
├── verify-nr.sh
├── set-nr-license-stage1.sh
├── nr-alerts.md
├── rollout-plan.md
├── plan-stage1-prerequisites.md
├── prerequisites-stage1.md
└── integrations.d/
    ├── cue-um-health-flex.stage1.yml
    ├── cue-um-health-flex.stage2.yml
    └── cue-um-health-flex.prod.yml
```

---

## Example 3: ARM64 CI Runners (KD-6699) — CI/CD Change (DONE)

**Ticket type**: CI infrastructure — change GHA runner architecture.

**Key patterns used**:
- Full application inventory table (22 apps with runner, test type, compose)
- Runner infrastructure audit (Kubernetes scale sets, Karpenter NodePools)
- Per-app compatibility assessment
- Single solution with phased rollout (reusable workflow matrix strategy)
- Moved to `worklog/done/` on completion

**Findings structure**:
```
1. CI TEST INFRASTRUCTURE - GITHUB ACTIONS
   (reusable workflow chain, 3 jobs, trigger patterns)

1a. FULL APPLICATION INVENTORY - CI TEST WORKFLOWS
   (22-row table: app → repo → runner → tests → type → compose)
   SUMMARY: 17/20 test-enabled, all on amd64, runner change = central)

2. GHA RUNNERS - KUBERNETES SCALE SETS
   (CUE dev cluster ARC + Karpenter details)
```

**Completion pattern**:
- ACTION LOG records all PRs merged, jobs tested
- STATUS set to DONE with final summary
- TIME LOGGED with all Tempo entries
- Files moved to `worklog/done/`

---

## Example 4: Dead Ingress Routes (DEVOPS-233) — Audit & Cleanup

**Ticket type**: Infrastructure audit — find and remove stale IngressRoutes.

**Key patterns used**:
- Probe pod for in-cluster DNS resolution (PSS-restricted manifest)
- Config cross-reference: domain → Jenkins config line → IngressRoute → removal order
- Read-only investigation with explicit approval gates
- Multiple tmp/ scripts: local ping, internal ping, probe pod YAML
- Candidate list in separate file

**tmp/ artifacts**:
```
tmp/DEVOPS-233_local_ping.sh      (147 lines)
tmp/DEVOPS-233_internal_ping.sh   (160 lines)
tmp/devops233-probe.yaml          (PSS-restricted pod manifest)
tmp/DEVOPS-233_prod_candidates.list
tmp/devops233_cmds.txt            (329 lines — session commands)
tmp/devops233_config_crossref.md  (Jenkins config line mapping)
tmp/plan_devops233_probe.md       (92 lines — investigation plan)
```

**MODE discipline enforced**:
- plan_devops233_probe.md explicitly states: no `kubectl apply/create/delete`,
  no `git push`, no Jenkins triggers without explicit "go"
- Investigation uses read-only alternatives first

---

## Example 5: Jenkins Branches (KD-6557) — Large Refactor (DONE)

**Ticket type**: CI/CD refactoring — 38 files changed across multiple repos.

**Key patterns used**:
- Comprehensive pre-change audit
- master/develop branch mapping per host
- Implementation checklist with 38+ items
- Regression testing after implementation
- STATUS: DONE with final file count

---

## Anti-Patterns to Avoid

### 1. Skipping FINDINGS before SOLUTIONS
Never propose solutions without documented findings. Research first.

### 2. Single-option proposals
Always present at least 2 options, even if one is clearly better.
The "worse" option documents why it was rejected.

### 3. Undated ACTION LOG entries
Every entry must have YYYY-MM-DD (and HH:MM for same-day entries).

### 4. Vague STATUS
Bad: "Working on it"
Good: "MODE: PLAN — Stage1 prerequisites. Spec: tmp/DEVOPS-796/plan.md. Next: G0 checklist. Blockers: NR license."

### 5. Missing cross-references
When discovery affects another ticket, always note it and reference the worklog path.

### 6. Secrets in worklogs
Never: API keys, license keys, passwords, tokens.
Instead: SHA256 hashes, "key present (54B)", reference to properties file path.

---

## Ticket Type → Section Priority Matrix

| Section | Feature | Infra | CI/CD | Monitoring | Audit |
|---------|---------|-------|-------|------------|-------|
| REFERENCED REPOS | HIGH | MED | HIGH | LOW | MED |
| Architecture finding | HIGH | MED | HIGH | LOW | LOW |
| Environment inventory | LOW | HIGH | LOW | HIGH | MED |
| Gap analysis | HIGH | HIGH | MED | HIGH | HIGH |
| Solution options | HIGH | HIGH | HIGH | MED | MED |
| Gate-based actions | LOW | HIGH | LOW | MED | LOW |
| tmp/ scripts | LOW | HIGH | MED | HIGH | HIGH |
| Implementation summary | MED | HIGH | HIGH | HIGH | MED |

---

## Default Prompt Workflow — Full Sequence

When user triggers via `ticket-pickup.prompt` or equivalent:

```
INPUT:  "pull up KD-6945, create worklog with all the comments, findings,
         proposed actions and a plan with solutions and options,
         innovate on finding a solution, parse for referenced repositories
         and other actions, rename the session tab to just the ticket number"

OUTPUT SEQUENCE:
1. jira/jira-ticket-info.sh KD-6945
2. Check worklog/done/*KD-6945* (reopened?)
3. Read skill's worklog.template file
4. WRITE GATE: Create worklog/YYYY-MM-DD_KD-6945.log
5. Research: grep repos, read related worklogs, check tmp/
6. Populate: TICKET, REFERENCED REPOSITORIES, FINDINGS
7. Innovate: generate options A/B/C
8. Populate: PROPOSED SOLUTIONS, RISK CONSIDERATIONS
9. Plan: create phased checklist
10. Populate: PROPOSED ACTIONS, ACTION LOG, STATUS, TIME LOGGED
11. Rename tab to "KD-6945"
```

Total expected time for a medium-complexity ticket: 15-45 minutes of research
→ 200-700 line worklog file.
