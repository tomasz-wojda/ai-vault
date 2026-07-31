# ONBOARDING — AI Vault

Welcome to **AI Vault**, the single-repo platform for multi-agent workflow automation, DevOps daily protocols, and cross-skill integration.

---

## 1. Quick Start

### Prerequisites

- **Git** (2.x+)
- **JDK 17** — required by the Jenkins syntax check. JDK 18 and newer break it: Groovy 3.x cannot read their class files.
- **Groovy 3.x** — for `syntax_check.groovy`
- **GitHub CLI (`gh`)** — for PR reviews and ticket workflows

### First Steps

Symlink targets must be absolute paths; a relative target produces a dangling link.

```bash
git clone https://github.com/<org>/ai-vault.git
cd ai-vault

VAULT="$(pwd)"
ln -s "$VAULT/skills" ~/.cursor/skills
ln -s "$VAULT/skills" ~/.agent/skills
ln -s "$VAULT/.rules" ~/.agent/.rules
```

### Understanding the Structure

Symlinks live outside the repository, in your agent host's config directory. They are
not repo contents.

```
~/.cursor/skills   → <vault>/skills        (Cursor)
~/.agent/skills    → <vault>/skills        (AntiGravity)
~/.agent/.rules    → <vault>/.rules

ai-vault/
├── skills/                       ← single truth for SKILLS
│   ├── CROSS_SKILL_INTEGRATION.md ← handoff contracts between skills
│   ├── developer-protocol/       ← RESEARCH→INNOVATE→PLAN→EXECUTE
│   ├── devops-daily-protocol/    ← Day Start→Pickup→Investigation→Done→Day End
│   │   └── SKILL.md              ← workflow + tool contracts
│   ├── jenkins-pipeline-architect/ ← CI/CD pipelines, JIRA notifications
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   └── pipeline-patterns.md
│   │   └── scripts/
│   │       ├── syntax_check.sh   ← macOS/Linux entry point (resolves JDK 17)
│   │       └── syntax_check.groovy
│   └── jira-worklog-processor/   ← content generation patterns
│       ├── SKILL.md              ← worklog structure, FINDINGS/SOLUTIONS format
│       ├── ticket-pickup.prompt  ← static template (read-only)
│       └── examples.md           ← completed-ticket walkthroughs
├── scripts/validate-skills.sh    ← repo integrity checks
├── .rules                         ← single truth for Rules
├── .gitignore                     ← excludes credentials and session artifacts
└── README.md                      ← project overview
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

The repository holds only skills, rules, and tooling. The `worklog/`, `tmp/`,
`zzzrecycle/`, and `prompt.log` paths below live in your working workspace, not in
this repository, and are excluded by `.gitignore`.

```
ai-vault/
├── skills/                       ← single truth for SKILLS
│   ├── CROSS_SKILL_INTEGRATION.md
│   ├── developer-protocol/
│   │   └── SKILL.md
│   ├── devops-daily-protocol/    ← workflow + tool contracts
│   │   └── SKILL.md
│   ├── jenkins-pipeline-architect/
│   │   ├── SKILL.md
│   │   ├── references/pipeline-patterns.md
│   │   └── scripts/
│   │       ├── syntax_check.sh
│   │       └── syntax_check.groovy
│   └── jira-worklog-processor/   ← content generation patterns
│       ├── SKILL.md
│       ├── ticket-pickup.prompt  ← static template (read-only)
│       ├── worklog.template      ← worklog scaffold
│       ├── examples.md           ← completed-ticket walkthroughs
│       └── worklog-reference.md  ← section specifications
├── scripts/validate-skills.sh    ← repo integrity checks
├── .rules                         ← single truth for Rules
├── .gitignore
├── README.md                      ← project overview
├── CONTRIBUTING.md                ← contribution guide
├── VERSIONING.md                  ← versioning policy
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
| `prompt.log` | Workspace root | System | Session audit trail — append-only, never edit manually, never committed |

---

## 5. Contributing Guidelines

### Code Changes

- Follow the Write Gate Protocol for any file creation or editing.
- The agent never commits or pushes. After changes are applied it proposes a semantic commit title and description; you run the git commands.
- **Jenkins Pipelines**: run `skills/jenkins-pipeline-architect/scripts/syntax_check.sh` before committing.
- **Any skill or rule change**: run `scripts/validate-skills.sh` before committing.

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
| JIRA CLI (`worklog/interface/jira/jira-ticket-info.sh`) | Always | 5 modes: `summary`, `<KEY>`, `rejected`, `tempo [DATE]`, `verify [DATE]` |
| NR CLI (`worklog/interface/newrelic/newrelic-info.sh`) | Always | 6 modes: `apps`, `app <ID>`, `hosts <ID>`, `deployments <ID>`, `alerts <ID>`, `violations` |
| File reads | Always | No restrictions |
| kubectl (read-only) | Always | Use patterns from `zzzrecycle/monitor_commands.txt` |

### Never Commit

- `worklog/interface/jira/credentials` — JIRA + Tempo tokens
- `worklog/interface/newrelic/credentials` — NR API keys

The repository `.gitignore` already excludes `**/credentials`, `**/*.properties`,
`**/cookie`, `worklog/`, `tmp/`, `prompt.log`, and `PR.log`. Verify with
`git check-ignore -v <path>` before adding any file that may carry a secret.

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

- Verify the symlinks resolve: `readlink -f ~/.agent/skills` and `readlink -f ~/.cursor/skills` must point inside the vault. A relative `ln -s` target yields a dangling link.
- Check that each skill's `SKILL.md` is present and readable
- Run `scripts/validate-skills.sh`; a `name` that does not match its directory prevents the skill from resolving

### Worklog Template Out of Sync with SKILL.md

- Read `skills/jira-worklog-processor/SKILL.md` for current section structure
- Update `worklog.template` to match
- Commit the change yourself with a semantic message; the agent proposes it but never commits

### JIRA CLI Not Found

```bash
chmod +x worklog/interface/jira/jira-ticket-info.sh
./worklog/interface/jira/jira-ticket-info.sh summary
./worklog/interface/jira/jira-ticket-info.sh KD-1234
```

---

## 9. Getting Help

| Question | Where to Look |
|----------|---------------|
| How to structure a worklog? | `skills/jira-worklog-processor/SKILL.md` + `worklog.template` |
| PR review process? | `skills/jira-worklog-processor/SKILL.md` § PR Review Workflow |
| Jenkins pipeline syntax? | `skills/jenkins-pipeline-architect/SKILL.md` + `references/pipeline-patterns.md` |
| Mode transitions? | `skills/developer-protocol/SKILL.md` |
| Cross-skill integration? | `skills/CROSS_SKILL_INTEGRATION.md` |

---

## 10. License & Attribution

This project is governed by the rules in `.rules`. See `VERSIONING.md` for versioning policy and `skills/CROSS_SKILL_INTEGRATION.md` for data flows between skills.