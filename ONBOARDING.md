# ONBOARDING — AI Vault

Welcome to **AI Vault**, the single-repo platform for multi-agent workflow automation, DevOps daily protocols, and cross-skill integration.

---

## 1. Quick Start

### Prerequisites

- **Git** (2.x+)
- **Java 25+** (for Groovy/Java tooling)
- **Node.js 20+** (for MCP daemon & JS utilities)
- **Docker / Docker Compose** (optional, for local service testing)
- **GitHub CLI (`gh`)** — for PR reviews and ticket workflows

### First Steps

```bash
# Clone the repository
git clone https://github.com/<org>/ai-vault.git
cd ai-vault

# Set up skills symlinks (see README.md § Symlink Setup)
ln -s ./skills ~/.cursor/skills
ln -s ./skills ~/.agent/skills
ln -s ./rules/.rules ~/.agent/.rules
```

### Understanding the Structure

```
ai-vault/
├── .agent/skills                 ← symlink → skills/
├── .cursor/skills                ← symlink → skills/
├── skills/                       ← single truth for SKILLS
│   ├── developer-protocol/       ← RESEARCH→INNOVATE→PLAN→EXECUTE
│   ├── devops-daily-protocol/    ← Day Start→Pickup→Investigation→Done→Day End
│   │   └── SKILL.md              ← workflow + tool contracts
│   ├── jenkins-pipeline-architect/ ← CI/CD pipelines, JIRA notifications
│   │   └── syntax_check.groovy   ← pipeline validation script
│   └── jira-worklog-processor/   ← content generation patterns
│       ├── SKILL.md              ← worklog structure, FINDINGS/SOLUTIONS format
│       ├── ticket-pickup.prompt  ← static template (read-only)
│       └── examples.md           ← completed-ticket walkthroughs
├── .rules                         ← single truth for Rules
└── README.md                      ← this file
```

---

## 2. Skill Protocols

### Active Skills

| Skill | Source | Governs |
|-------|--------|---------|
| `developer-protocol` | `skills/developer-protocol/` | Mode discipline: RESEARCH → INNOVATE → PLAN → EXECUTE |
| `devops-daily-protocol` | `skills/devops-daily-protocol/` | Lifecycle shell, tool contracts (JIRA CLI, NR CLI), Write Gate Protocol |
| `jenkins-pipeline-architect` | `skills/jenkins-pipeline-architect/` | Jenkins scripted pipelines, JIRA notifications from CI/CD |
| `jira-worklog-processor` | `skills/jira-worklog-processor/` | Content generation: worklog sections, FINDINGS patterns, solution options, PR review workflow |

### How Skills Layer

```
┌─────────────────────────────────────────────────┐
│  developer-protocol                             │
│  Governance: RESEARCH → INNOVATE → PLAN → EXEC   │
├─────────────────────────────────────────────────┤
│  devops-daily-protocol                          │
│  Lifecycle: pickup, investigation, done, verify │
│  Tools: JIRA CLI, NR CLI, Tempo API             │
├─────────────────────────────────────────────────┤
│  jira-worklog-processor                         │
│  Content: FINDINGS patterns, solution options,   │
│  gap analysis, gate plans, cross-ticket refs    │
├─────────────────────────────────────────────────┤
│  jenkins-pipeline-architect                     │
│  CI/CD: scripted pipelines, JIRA notifications   │
└─────────────────────────────────────────────────┘
```

When multiple skills are active, `devops-daily-protocol` governs *when* and *how* to create/update files; `jira-worklog-processor` governs *what goes inside them*.

---

## 3. Workspace Layout (Post-Onboarding)

After initial setup, your workspace should look like:

```
ai-vault/
├── .agent/skills                 ← symlink → skills/
├── .cursor/skills                ← symlink → skills/
├── skills/                       ← single truth for SKILLS
│   ├── developer-protocol/
│   │   └── SKILL.md
│   ├── devops-daily-protocol/    ← workflow + tool contracts
│   │   └── SKILL.md
│   ├── jenkins-pipeline-architect/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── syntax_check.groovy
│   └── jira-worklog-processor/   ← content generation patterns
│       ├── SKILL.md
│       ├── ticket-pickup.prompt  ← static template (read-only)
│       ├── worklog.template      ← worklog scaffold
│       ├── examples.md           ← completed-ticket walkthroughs
│       └── worklog-reference.md  ← section specifications
├── .rules                         ← single truth for Rules
├── README.md                      ← this file
├── VERSIONING.md                  ← versioning policy
├── plan.md                        ← current project plan
├── worklog/
│   ├── done/                       ← archive for completed tickets
│   └── interface/                  ← service connectivity hub
│       ├── jira/credentials        ← JIRA + Tempo tokens (NEVER commit)
│       ├── newrelic/credentials    ← NR API keys (NEVER commit)
│       ├── aws/                    ← AWS profile files per account
│       └── eks/                    ← EKS context files per cluster
├── zzzrecycle/monitor_commands.txt ← kubectl diagnostic patterns
├── prompt.log                      ← session audit trail (append-only)
└── tmp/                            ← scratch artifacts (per-ticket folders)
```

---

## 4. Key Files & Ownership

| File | Location | Owner | Notes |
|------|----------|-------|-------|
| `SKILL.md` | `skills/<skill>/` | Skill author | Single source of truth for each skill's workflow |
| `ticket-pickup.prompt` | `skills/jira-worklog-processor/` | User-maintained | **Static template** — agent reads only, never edits |
| `worklog.template` | `skills/jira-worklog-processor/` | User-maintained | Worklog scaffold — sync with SKILL.md structure |
| `examples.md` | `skills/jira-worklog-processor/` | Community | Completed-ticket walkthroughs for reference |
| `.rules` | Root | All contributors | Single truth for project rules |
| `prompt.log` | Root | System | Session audit trail — append-only, never edit manually |

---

## 5. Contributing Guidelines

### Code Changes

- **Java/Groovy**: Use `gitAdd` + `gitCommit`. Follow the Write Gate Protocol for any file creation/editing.
- **Python/Node.js**: Standard git workflow with PR reviews.
- **Jenkins Pipelines**: Run `skills/jenkins-pipeline-architect/scripts/syntax_check.groovy` before committing.

### Worklog Changes

1. Create worklogs in `worklog/YYYY-MM-DD_<TICKET-KEY>.log`
2. Follow the template structure from `worklog.template`
3. Use numbered FINDINGS, labeled solution options (A–E), and phased PROPOSED ACTIONS
4. Archive completed worklogs to `worklog/done/`

### PR Review Workflow

Triggered by "review this PR", "review PR #N", or a GitHub PR URL:

1. Extract PR metadata via `gh pr view <URL-or-number> --json title,body,author,baseRefName,headRefName,files,reviews,reviewRequests,state`
2. Identify the ticket key (patterns: `KD-1234`, `DEVOPS-123`, `CWP-1234`)
3. Find the worklog in `worklog/*_<TICKET-KEY>.log` or `worklog/done/*_<TICKET-KEY>.log`
4. Compare PR diff against PROPOSED ACTIONS checklist:
   - `[ ]` → not covered by this PR (still pending)
   - `[~]` → covered by this PR, PR still open
   - `[x]` → done — change landed (only after merge)

### Merge Follow-up

When a PR is merged:
1. Confirm via `gh pr view` shows `state: MERGED`
2. Update worklog PROPOSED ACTIONS: change matched `[~]` items to `[x]`
3. Append merge note to ACTION LOG with PR number and checklist coverage count
4. Append follow-up block under the original review in `PR.log`

---

## 6. Safety Rules

### Write Gate Protocol (All Writes)

1. **ANNOUNCE** the operation type
2. **PREVIEW** full content (file content, API payload, git command)
3. **WAIT** — "Proceed? (yes/no)"
4. **EXECUTE** only after user confirms
5. **VERIFY** success (re-read file, re-run verify)

### Read-Only by Default

| Operation | Allowed | Notes |
|-----------|---------|-------|
| JIRA CLI (`jira/jira-ticket-info.sh`) | Always | 5 modes: `summary`, `<KEY>`, `rejected`, `tempo [DATE]`, `verify [DATE]` |
| NR CLI (`newrelic/newrelic-info.sh`) | Always | 6 modes: `apps`, `app <ID>`, `hosts <ID>`, `deployments <ID>`, `alerts <ID>`, `violations` |
| File reads | Always | No restrictions |
| kubectl (read-only) | Always | Use patterns from `zzzrecycle/monitor_commands.txt` |

### Never Commit

- `worklog/interface/jira/credentials` — JIRA + Tempo tokens
- `worklog/interface/newrelic/credentials` — NR API keys
- `.gitignore` should exclude all credential files

---

## 7. Mode Discipline

Follow the developer protocol modes. Declare mode at the start of every response:

| Mode | Allowed | Forbidden |
|------|---------|-----------|
| **RESEARCH** | Read files, JIRA/NR CLI, questions | Suggestions, planning, implementation |
| **INNOVATE** | Options, pros/cons, discussion | Detailed plans, code, implementation |
| **PLAN** | File paths, checklists, specs | Code implementation |
| **EXECUTE** | Exactly what the plan says | Deviations, creative additions |

Transition only on explicit `MODE: <name>` from user.

---

## 8. Troubleshooting

### Skills Not Loading

- Verify symlinks exist: `.agent/skills` → `skills/`, `.cursor/skills` → `skills/`
- Check that each skill's `SKILL.md` is present and readable

### Worklog Template Out of Sync with SKILL.md

- Read `skills/jira-worklog-processor/SKILL.md` for current section structure
- Update `worklog.template` to match
- Run `gitAdd . && gitCommit -m "sync worklog.template with jira-worklog-processor/SKILL.md"`

### JIRA CLI Not Found

```bash
# Ensure the script is executable
chmod +x worklog/interface/jira/jira-ticket-info.sh

# Test a query
./worklog/interface/jira/jira-ticket-info.sh summary KD-1234
```

---

## 9. Getting Help

| Question | Where to Look |
|----------|---------------|
| How to structure a worklog? | `skills/jira-worklog-processor/SKILL.md` + `worklog.template` |
| PR review process? | `skills/jira-worklog-processor/SKILL.md` § PR Review Workflow |
| Jenkins pipeline syntax? | `skills/jenkins-pipeline-architect/scripts/syntax_check.groovy` |
| Mode transitions? | `skills/developer-protocol/SKILL.md` |
| Cross-skill integration? | `CROSS_SKILL_INTEGRATION.md` |

---

## 10. License & Attribution

This project is governed by the rules in `.rules`. See `VERSIONING.md` for versioning policy and `CROSS_SKILL_INTEGRATION.md` for data flows between skills.

Thank you for contributing to AI Vault! 🚀