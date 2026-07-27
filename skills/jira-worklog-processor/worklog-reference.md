# Worklog Reference — Section Specifications

Detailed specifications for each worklog section, content patterns, and quality
standards derived from 40+ completed and active worklogs.

## Workspace Folder Trees

### worklog/

```
worklog/
├── start_tunnel.sh                     # Prometheus port-forward (kontoprod2)
├── kontoprod2-traffic-by-app.sh        # Traefik traffic analysis
├── kontoprod2-traffic-last7days.sh
├── kontoprod2-traffic-last7days.groovy
├── kontoprod2-traffic-last30days.sh
├── YYYY-MM-DD_TICKET-KEY.log           # Active worklogs (13+)
├── YYYY-MM-DD_TICKET-KEY_jira.log      # JIRA companion dumps
├── done/                               # Archived completed (24+ files)
│   ├── YYYY-MM-DD_TICKET-KEY.log
│   ├── YYYY-MM-DD_TICKET-KEY_jira.log
│   ├── YYYY-MM-DD_TICKET-KEY_suffix.log  # Sub-investigations
│   └── *.txt                             # Data snapshots (ec2 tags, tables)
└── interface/                          # Service connectivity hub
    ├── aws/                            #   AWS profiles (export AWS_PROFILE=...)
    ├── eks/                            #   EKS contexts (export KUBECONFIG=...)
    ├── jira/                           #   JIRA CLI + credentials
    ├── newrelic/                       #   NR CLI + credentials
    ├── jenkins/                        #   Jenkins credentials
    ├── github/                         #   GitHub tokens
    ├── argocd/                         #   Argo CD credentials
    ├── artifactory/                    #   Artifactory credentials
    ├── ssh/                            #   SSH configs / jump hosts
    ├── snow/                           #   ServiceNow session
    └── datadog/                        #   Datadog API keys
```

### repos/ (21 cloned repositories)

```
repos/
├── ai-vault/                           # Agent skills + rules (this repo)
├── TVN-eks_konto-eks_konto/            # EKS cluster config, kube-core, OTel, Traefik
├── TVN-eks_konto-eks_deployments/      # Argo CD deployment overlays per env
├── TVN-eks_konto-jenkins/              # Jenkins pipelines (build, deploy, test)
├── TVN-gitadmins-helm_charts/          # Helm charts — konto_all_chart + values/
├── TVN-gitadmins-sso_github_actions/   # GHA reusable workflows (run-ci.yml)
├── TVN-gitadmins-jira_integration/     # JIRA integration scripts
├── TVN-gitadmins-gha-runners/          # GHA runner infrastructure
├── TVN-gitadmins-anonymization/        # DB anonymization pipelines
├── TVN-gitadmins-SFBR_pipelines/       # SFBR Jenkins job definitions
├── TVN-eks-commons/                    # Shared EKS scripts (dyff, bump, validate)
├── TVN-cue-eks_cue/                    # CUE EKS cluster config
├── TVN-cue-environments_configuration/ # CUE docker-compose / envfile configs
├── TVN-sso-aaa_api/                    # aaa-api (Node.js backend)
├── TVN-sso-oauth_api/                  # oauth-api
├── TVN-sso-oauth_provider_api/         # oauth-provider-api
├── TVN-sso-tvnaccount_demo_app/        # demo app
├── TVN-account-test_e2e/               # E2E test suite
├── TVN-account-ts_sdk/                 # TypeScript SDK
├── TVN-brookselkad7-bng/               # BNG project (Windows/.NET)
└── tvn-account-webcomponent/           # Web component library (TypeScript/Lit)
```

### tmp/ (ticket artifacts + scratch)

```
tmp/
├── TICKET-KEY/                         # Per-ticket artifact folders
│   ├── ssh/{role}/manifest.txt         #   SSH evidence snapshots
│   ├── *.sh                            #   Install/verify/collect scripts
│   ├── *.md                            #   Plans, diffs, prerequisites
│   └── integrations.d/*.yml            #   Config files for deployment
├── worklog_skill/                      # Worklog processor skill (source copy)
├── geralt/                             # NR NRQL facet query results
├── TVN-cue-*/                          # CUE repo clones (3)
├── TVN-zoltan-*/                       # Zoltan repo clones (~20)
├── TICKET-KEY_*.sh                     # Standalone ticket scripts
├── TICKET-KEY_*.list                   # Data candidate lists
├── devopsNNN-probe.yaml                # Probe pod manifests
├── devopsNNN_cmds.txt                  # Session command logs
├── *_config_crossref.md                # Jenkins config line mapping
├── plan_*.md                           # Investigation plans
├── kontoprod2-rightsize.py             # EKS CPU rightsizing report
├── player-consumer-check.sh            # Resource sweep script
├── list_tvn_zoltan_codeowners.py       # GitHub CODEOWNERS audit
├── tickets.log                         # JIRA assigned-ticket snapshot
├── lambdas.log                         # CWP-4430 lambda investigation
├── *.csv                               # Data exports (emails, etc.)
└── *.properties                        # ⚠ Credentials — never commit
```

## Interface Directory — Service Connectivity

`worklog/interface/` is the canonical location for service credentials and CLI scripts.
Each subfolder corresponds to one external service.

### Credential File Format

Use shell export format (source-able):

```bash
export JIRA_BASE_URL="https://jira.pl.grupa.iti"
export JIRA_TOKEN="Bearer ..."
```

Usage: `source worklog/interface/jira/credentials`

### Per-Service Structure

```
worklog/interface/<service>/
├── credentials                 # export VAR=value (source-able, never commit)
└── <service>-info.sh           # CLI script (optional, service-specific)
```

### Service Inventory

| Service | Folder | Credentials | Script | Notes |
|---------|--------|-------------|--------|-------|
| JIRA + Tempo | `jira/` | `credentials` (JIRA_BASE_URL, JIRA_TOKEN) | `jira-ticket-info.sh` (5 modes: summary, ticket, rejected, tempo, verify) | Primary ticket interface |
| New Relic | `newrelic/` | `credentials` (NR_API_KEY, NR_ACCOUNT_ID) | `newrelic-info.sh` (6 modes: apps, app, hosts, deployments, alerts, violations) | Monitoring investigations |
| AWS | `aws/` | Profile files (export AWS_PROFILE=...) | — | One file per account/role (cue-stage, cue-prod, konto-prod) |
| EKS | `eks/` | Context files (export KUBECONFIG=... or context name) | — | One file per cluster (konto, cue) |
| Jenkins | `jenkins/` | `credentials` (JENKINS_URL, JENKINS_USER, JENKINS_TOKEN) | — | Build triggers, job config |
| GitHub | `github/` | `credentials` (GH_TOKEN) | — | gh CLI, API calls |
| Argo CD | `argocd/` | `credentials` (ARGOCD_SERVER, ARGOCD_AUTH_TOKEN) | — | GitOps sync status |
| Artifactory | `artifactory/` | `credentials` (ARTIFACTORY_URL, ARTIFACTORY_TOKEN) | — | Artifact version queries |
| SSH | `ssh/` | Config files per environment (cue-stage, cue-prod) | — | Jump host configs, ProxyJump |
| ServiceNow | `snow/` | `cookie` (session cookie for CHG API) | — | Change management |
| Datadog | `datadog/` | `credentials` (DD_API_KEY, DD_APP_KEY) | — | If Datadog adopted per KD-6945 |

### Security

- All credential files MUST be in `.gitignore` — never commit tokens.
- Reference credentials in worklogs by path only: "source worklog/interface/jira/credentials"
- Scripts may be committed; credentials never.

## Worklog Template Structure

The canonical scaffold lives at [worklog.template](worklog.template) (ships with this skill). Every worklog uses
80-character `=` separator lines between sections.

```
================================================================================
  SECTION TITLE
================================================================================
```

## TICKET Header — Field Mapping

Map JIRA CLI output fields to worklog header:

| Worklog Field | JIRA Source | Notes |
|---------------|-------------|-------|
| TICKET | issue key | e.g. KD-6945 |
| Summary | summary field | Translate PL to EN if needed, keep original in parentheses |
| Status | status + column | e.g. "W trakcie (In progress)" |
| Type | issuetype | Task, Bug, Story, Epic |
| Priority | priority | Wysoki/Średni/Normalny/Niski → High/Medium/Normal/Low |
| Project | project name + key | e.g. "KD - Tech Titans" |
| Assignee | assignee display | "Surname, Name (since DATE)" if assignment date available |
| Reporter | reporter display | "Surname, Name" |
| Components | components list | "None" if empty |
| Labels | labels list | Include all, "None" if empty |
| Epic | epic link | Key + name if available |
| Created | created date | YYYY-MM-DD |
| Updated | updated date | YYYY-MM-DD |
| Time Spent | worklog entries | "Xh (Name — DATE)" per entry, "None" if empty |
| Description | description | Clean formatting, translate PL→EN with original note |
| Comments | comment list | "(brak komentarzy na JIRA)" or "(none on JIRA)" if empty |
| Linked Issues | issue links | "(brak)" or "(none)" if empty |

### Extended Header Fields (use when present)

| Field | When to include |
|-------|----------------|
| Creator | If different from Reporter |
| Resolution | If ticket has resolution set |
| English | Translated summary/description when original is Polish |
| Related work | Cross-references to other tickets found during research |

## RELATED TICKET Section

Add between TICKET header and FINDINGS when the ticket relates to another.
Include: status summary, impact analysis, blocking/non-blocking assessment,
worklog path reference.

```
================================================================================
  RELATED TICKET: OTHER-KEY (Short Description)
================================================================================

  Status: <current status from other worklog>

  <2-4 line description of the other ticket's scope>

  Impact on <THIS-KEY>:
    <How they relate, what depends on what>
    <Blocking or non-blocking assessment>

  Worklog: worklog/YYYY-MM-DD_OTHER-KEY.log (N lines)
```

## REFERENCED REPOSITORIES Section

Add after TICKET header (or after RELATED TICKET if present).
Number each repo. Include GitHub org and role description.

```
================================================================================
  REFERENCED REPOSITORIES
================================================================================

1. REPO-NAME (GitHub: org-name)
   - Primary role in this ticket context
   - Key files/paths relevant to investigation

2. ANOTHER-REPO (GitHub: org-name)
   - Role description
```

Common repo patterns in this workspace:
- `TVN-gitadmins-helm_charts` — Helm charts, konto_all_chart values
- `TVN-eks_konto-eks_konto` — EKS cluster config, kube-core, OTel
- `TVN-eks_konto-eks_deployments` — Argo CD deployment overlays
- `TVN-eks_konto-jenkins` — Jenkins pipelines
- `TVN-gitadmins-sso_github_actions` — GHA reusable workflows
- `TVN-AWS-Infra-Projects-CUE` — CUE EC2/ASG/ALB Terraform
- `TVN-cue-environments_configuration` — CUE docker-compose configs
- `TVN-cue-jenkins` — CUE Jenkins pipeline jobs

## FINDINGS Section — Content Patterns

### Pattern 1: Architecture Overview
Used when ticket involves a platform or system. Number services, group by layer.

```
1. PLATFORM ARCHITECTURE (N services on PLATFORM)
.................................................................

   BACKEND SERVICES (tech stack):
   - service-a, service-b, service-c

   FRONTEND:
   - frontend-app

   INFRASTRUCTURE:
   - Cluster: name (environments)
   - Ingress: type (middlewares)
   - CD: tool for GitOps
```

### Pattern 2: Current State Audit
Used for infrastructure, monitoring, config tickets. Table format.

```
2. CURRENT STATE (source — date)
.................................................................

   COMPONENT               STATUS       DETAILS
   Component A             DEPLOYED     version, config notes
   Component B             MISSING      gap description
   Component C             ACTIVE       health status
```

### Pattern 3: Gap Analysis
Severity-ranked table of gaps between desired and current state.

```
3. GAPS IDENTIFIED
.................................................................

   GAP                    SEVERITY   DESCRIPTION
   Missing config X       HIGH       Prod values lack annotation
   No monitoring Y        MEDIUM     No NR visibility for hosts
   Missing docs Z         LOW        Runbook not updated
```

### Pattern 4: Environment Inventory
Per-environment breakdown with instance IDs, IPs, versions.

```
4. ENVIRONMENT INVENTORY (live checks YYYY-MM-DD)
.................................................................

  ENV1 — account XXXX
    instance-id  hostname  ip
    version  health-status  ASG/LT details

  ENV2 — account XXXX
    instance-id  hostname  ip
    version  health-status
```

### Pattern 5: Key Files Listing
When ticket requires changes to specific files.

```
5. KEY FILES FOR THIS TICKET
.................................................................

   - repo/path/to/file.yaml
     (description of what this file controls)
   - repo/another/path.yml
     (description)
```

## PROPOSED SOLUTIONS Section — Option Format

Label options A through E. Mark recommended with "(RECOMMENDED)".

```
OPTION A: "SHORT MEMORABLE LABEL" (RECOMMENDED — rationale)
.................................................................

   1-3 sentence description of approach.

   Detail steps if helpful:
   1. First step
   2. Second step

   PROS: Concise benefit list. Separated by periods.
   CONS: Concise drawback list.

OPTION B: "ALTERNATIVE LABEL" (effort level)
.................................................................
   ...

RECOMMENDATION: A + B hybrid on stage pilot → prod rollout.
```

### Hybrid Recommendations
Common pattern: recommend combining elements from multiple options.
State rollout order: Stage1 → Stage2 → Prod template → Prod ASG.

## RISK CONSIDERATIONS Section

Number each risk. Include: title, description, severity (implied by order),
mitigation strategy.

```
1. RISK TITLE
   Description of what could go wrong.
   Mitigation: specific action to reduce risk.

2. ANOTHER RISK
   Impact assessment.
   Mitigation: approach.
```

Common risk categories:
- Ambiguous requirements (clarify with reporter)
- Production impact (canary rollout, sampling rate)
- Cross-team coordination (dev team changes needed)
- Performance regression (test on low-traffic service first)
- Configuration drift (SHA256 comparison, manifest snapshots)

## PROPOSED ACTIONS Section — Phased Checklists

### Simple Format
```
PREP (done YYYY-MM-DD)
[x] Jira fetch TICKET-KEY
[x] Create worklog and artifacts

PHASE 1 — Scope Description
[ ] Specific action with target
[ ] Another action with expected outcome

CLOSE
[ ] Jira resolution + link related tickets
```

### Gate Format (infrastructure tickets)
```
G0 — Read-Only Prerequisites
[x] SSH access verified
[x] AWS SSO role confirmed
[ ] CHG approved in ServiceNow

G1 — Config Alignment
[ ] Template diff → expected state
[ ] Config SHA256 match

G2 — Build/Bake
[ ] create-image → new AMI
[ ] LT version update

G3 — Live Change (CHG required)
[ ] Instance refresh with approval
[ ] Rollback plan documented

G4 — Close-Out
[ ] Jira comment with AMI/LT/CHG IDs
[ ] Tempo time logged
[ ] Move to done/
```

### Checkbox States (PR lifecycle)

| Marker | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | Covered by an open PR — diff matches, awaiting merge |
| `[x]` | Done — PR merged and change landed |

On PR review: matched items go `[ ]` → `[~]` (append PR URL on the line).
On PR merge: items for that PR go `[~]` → `[x]`.
Never skip `[~]` — do not mark `[x]` until merge is confirmed.

Example after review:
```
PHASE 1 — Config changes
[~] Update UAT values for aaa-public-api (PR #182)
[ ] Update PROD values (separate PR pending)
```

Example after merge:
```
PHASE 1 — Config changes
[x] Update UAT values for aaa-public-api (PR #182 — merged)
```

## ACTION LOG Section

Chronological, timestamped, factual. No opinions — just what was done.

```
YYYY-MM-DD HH:MM - Action taken
                   Supporting detail (PR URL, AMI ID, test result)
                   Cross-reference if relevant

YYYY-MM-DD HH:MM - Next action
                   Detail
```

Entries should include:
- What was done (verb first)
- Evidence (IDs, URLs, command output summaries)
- Outcome or blocker discovered
- Cross-references to related tickets/worklogs

## STATUS Section

Single current-state block. Update on every significant change.

```
CURRENT: <MODE> — <phase description> (YYYY-MM-DD)
         Spec: tmp/TICKET-KEY/plan-name.md (if applicable)
         Next: <immediate next step>
         Blockers: <list or "none">
```

## TIME LOGGED Section

Table format matching Tempo entries.

```
YYYY-MM-DD  Xh   Name, Surname    Description
YYYY-MM-DD  Xm   Name, Surname    Description
```

## IMPLEMENTATION SUMMARY Section (optional)

For completed tickets, add a Polish+English implementation summary after
TIME LOGGED. This serves as the Jira close-out comment source.

```
================================================================================
  PODSUMOWANIE WDROŻENIA / IMPLEMENTATION SUMMARY (YYYY-MM-DD)
================================================================================

  OPIS / DESCRIPTION
  ---
  <Polish description of what was implemented>

  STATUS ROLLOUT
  ---
  | Environment | Host | Config Path | Status |
  ...

  IMPLEMENTATION STEPS
  ---
  | # | Step | What it does |
  ...

  OUT OF SCOPE
  ---
  • Items deferred to other tickets
```

## tmp/ Artifact Patterns

### Folder Structure
```
tmp/TICKET-KEY/
├── ssh/
│   ├── stage1/manifest.txt
│   ├── stage2/manifest.txt
│   ├── template/
│   │   ├── manifest.txt
│   │   ├── package-inventory.txt
│   │   └── root-history.txt
│   └── asg/manifest.txt
├── plan-description.md
├── rollout-plan.md
├── diff-summary.md
├── install-script.sh
├── verify-script.sh
└── integrations.d/
    └── config-per-env.yml
```

### Manifest Collection Script Pattern
```bash
#!/usr/bin/env bash
set -euo pipefail
HOST_LABEL="${1:-unknown}"
echo "=== TICKET manifest ==="
# OS, packages, services, ports, health, config SHA256
echo "=== END ==="
```

### Verification Script Pattern
```bash
#!/usr/bin/env bash
set -euo pipefail
HOSTNAME="${1:?usage: verify.sh <hostname>}"
# NRQL or API query to confirm deployment
# Check: SystemSample > 0, custom events present, expected values
```

## PR Tracking Patterns

### PR.log

`PR.log` lives at the workspace root. Each entry is a self-contained PR review record
separated by `================================================================================`.

Entry structure:

| Section | Content |
|---------|---------|
| Header | `--- YYYY-MM-DDTHH:MM ---` timestamp + `PR #N \| org/repo` + URL |
| METADATA | Title, author, branch, created, state, labels, CI, reviews, requested reviewers |
| CHANGED FILES | Count + per-file summary with change type and description |
| REFERENCED MODULE | External dependency details — tags, changelogs, related PRs (when applicable) |
| WORKLOG CROSS-REFERENCE | Ticket key, worklog path, checklist coverage ([~] in PR / [ ] missing), out-of-scope changes |
| SCALING COMPARISON | Before/after metrics (when PR changes resource configs) |
| OBSERVATIONS | Numbered analysis: risks, missing items, patterns, recommendations |

### PR.log ↔ Worklog Cross-Reference

When a PR relates to a worklog:
- PR.log entry includes WORKLOG CROSS-REFERENCE with checklist coverage map using `[~]` for covered items
- Worklog ACTION LOG gets an entry: `YYYY-MM-DD HH:MM - Reviewed PR #N (org/repo): <outcome>, N items marked [~]`
- **On review**: matched PROPOSED ACTIONS items go `[ ]` → `[~]` (append PR URL)
- **On merge**: items tied to that PR go `[~]` → `[x]`; ACTION LOG notes merge and count marked `[x]`
- PR.log gets a merge follow-up note when applicable

### PR Types by Review Depth

| PR type | Worklog expected? | Review focus |
|---------|-------------------|--------------|
| Feature from your ticket | Yes — full cross-reference | Checklist coverage, missing items |
| Colleague's PR (you're reviewer) | Maybe — check by ticket key | Correctness, risk, scope |
| Dependency bump | No | Version jumps, breaking changes, CI status |
| Config change | Maybe | Right-sizing, env correctness, PDB impact |
| Cleanup/deletion | Rarely | Scope completeness, residual references |

## Jira Companion Files (_jira.log)

Raw JIRA exports saved separately when ticket data is large:
- Contains: full description, all comments with timestamps, worklog entries
- Naming: `worklog/YYYY-MM-DD_TICKET-KEY_jira.log`
- Purpose: preserve original JIRA state at time of investigation
- Excluded from verify scanning

## Cross-Ticket Reference Rules

1. Never duplicate full content — reference the worklog path
2. Note blocking/non-blocking status explicitly
3. Update related ticket STATUS if discoveries affect it
4. Common patterns:
   - AMI/config tickets (DEVOPS-795 ↔ DEVOPS-796)
   - Feature + infrastructure (KD-6945 ↔ KD-6863)
   - Epic parent + child tasks (DEVOPS-374 → DEVOPS-233)

## Language Conventions

- Technical sections: English preferred
- JIRA content: preserve original Polish, add English translation
- Format: "Polish text (English translation)" or separate English field
- Status values: keep JIRA Polish originals + English in parentheses
  e.g. "W trakcie (In progress)", "Do podjęcia (To Do)"
- Implementation summaries for Jira close-out: Polish primary, English section headers

## Security Rules

- NEVER paste secrets, API keys, or license keys into worklog files
- Use SHA256 hashes for config verification, not raw content
- Reference credential files by path only (e.g. "jira.properties", "newrelic.properties")
- Mask instance IDs and IPs in shared/public contexts
- Companion files with secrets: note as "contains production secrets — do not commit"

## ai-vault Integration

The canonical source for agent skills is `repos/ai-vault` (GitHub: `tomasz-wojda/ai-vault`).

### Repository Structure
```
repos/ai-vault/
├── .rules                              # Global agent rules (mirrors Cursor user rules)
├── README.md                           # Symlink setup instructions
└── skills/
    ├── developer-protocol/SKILL.md     # Mode discipline (RESEARCH→EXECUTE)
    ├── devops-daily-protocol/SKILL.md  # Lifecycle: Day Start→Pickup→Done→Day End
    ├── jenkins-pipeline-architect/
    │   ├── SKILL.md                    # Jenkins scripted pipelines + JIRA notifications
    │   └── scripts/syntax_check.groovy
    └── jira-worklog-processor/
        ├── SKILL.md                    # Worklog content generation patterns
        ├── ticket-pickup.prompt              # Ticket pickup template ({TICKET_KEY} placeholder)
        ├── worklog.template            # Worklog section scaffold (was TEMPLATE.log)
        ├── worklog-reference.md        # Section specs, folder trees, interface directory
        └── examples.md                 # Real ticket examples
```

### Skill Layering Model

```
┌─────────────────────────────────────────────────┐
│  jira-worklog-processor (this skill)            │
│  Content: FINDINGS patterns, solution options,  │
│  gap analysis, gate plans, cross-ticket refs,   │
│  tmp/ artifacts, implementation summaries        │
├─────────────────────────────────────────────────┤
│  devops-daily-protocol (ai-vault)               │
│  Lifecycle: pickup, investigation, done, verify │
│  Tools: JIRA CLI, NR CLI, Tempo API             │
│  Safety: Write Gate, prompt.log                 │
├─────────────────────────────────────────────────┤
│  developer-protocol (ai-vault)                  │
│  Modes: RESEARCH → INNOVATE → PLAN → EXECUTE   │
│  Rules: no deviations, regression testing       │
├─────────────────────────────────────────────────┤
│  jenkins-pipeline-architect (ai-vault)          │
│  CI/CD: scripted pipelines, JIRA notifications  │
│  (used during EXECUTE phase for Jenkins work)   │
└─────────────────────────────────────────────────┘
```

### Deployment Options

**Option A — Workspace-local (current)**:
Keep in `tmp/worklog_skill/`. Available only in this workspace.

**Option B — Personal skill**:
Copy to `~/.cursor/skills/jira-worklog-processor/`. Available across all projects.

**Option C — Add to ai-vault**:
Add `skills/jira-worklog-processor/` to `repos/ai-vault/`. Version-controlled,
shared via symlinks to both Cursor and other agents. Canonical source of truth.

### .rules Overlap

The ai-vault `.rules` file contains rules that overlap with Cursor user rules:
- Append-only `prompt.log` (rules 2)
- Write-before-merge discipline (top rule)
- Developer protocol modes (rule 4)
- Systematic debugging (rule 5)

These reinforce the same behaviors this skill depends on. No conflicts.
