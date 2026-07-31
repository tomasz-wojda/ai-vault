# AI Vault - One Repo To Rule Them All

```
ai-vault/
├── skills/                       <- Single truth for SKILLS
│   ├── CROSS_SKILL_INTEGRATION.md <- Handoff contracts between skills
│   ├── developer-protocol/
│   │   └── SKILL.md
│   ├── devops-daily-protocol/
│   │   └── SKILL.md
│   ├── jenkins-pipeline-architect/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   └── pipeline-patterns.md
│   │   └── scripts/
│   │       ├── syntax_check.sh       <- macOS/Linux entry point, resolves JDK 17
│   │       └── syntax_check.groovy
│   └── jira-worklog-processor/
│       ├── SKILL.md
│       ├── ticket-pickup.prompt
│       ├── worklog.template
│       ├── worklog-reference.md
│       └── examples.md
├── scripts/
│   └── validate-skills.sh        <- Repo integrity checks; run before every commit
├── .rules                        <- Single truth for Rules           (AntiGravity, Cursor)
├── .gitignore
├── README.md                     <- This file
├── ONBOARDING.md                 <- Setup and workspace layout
├── CONTRIBUTING.md               <- Contribution guide
└── VERSIONING.md                 <- Versioning policy
```

Agent hosts read the skills through symlinks created outside this repository
(`~/.cursor/skills`, `~/.agent/skills`). See § Symlink Setup.

## Skill Layering & Integration

```
┌─────────────────────────────────────────────────┐
│  developer-protocol                             │
│  Governance: RESEARCH → INNOVATE → PLAN → EXEC  │
├─────────────────────────────────────────────────┤
│  devops-daily-protocol                          │
│  Lifecycle: pickup, investigation, done, verify │
│  Tools: JIRA CLI, NR CLI, Tempo API             │
├─────────────────────────────────────────────────┤
│  jira-worklog-processor                         │
│  Content: FINDINGS patterns, solution options,  │
│  gap analysis, gate plans, cross-ticket refs    │
├─────────────────────────────────────────────────┤
│  jenkins-pipeline-architect                     │
│  CI/CD: scripted pipelines, JIRA notifications  │
└─────────────────────────────────────────────────┘
```

For full details on handoff protocols, artifact ownership, and data flows between skills, see the master [Cross-Skill Integration Guide](skills/CROSS_SKILL_INTEGRATION.md).


## Symlink Setup

On macOS and Linux the symlink target must be an **absolute** path. A relative target
(`ln -s ./skills ...`) is resolved against the link's own directory and produces a
dangling link. Verify with `readlink -f ~/.cursor/skills`.

### Skills

Windows:
```
mklink /J C:\Users\YOUR_PROFILE\.gemini\.agent\skills X:\repositories\ai-vault\skills
```

macOS/Linux:
```
VAULT=/absolute/path/to/ai-vault
ln -s "$VAULT/skills" ~/.cursor/skills
ln -s "$VAULT/skills" ~/.agent/skills
```

### Rules

Windows:
```
mklink C:\Users\YOUR_PROFILE\.gemini\.agent\.rules X:\repositories\ai-vault\.rules
```

macOS/Linux:
```
VAULT=/absolute/path/to/ai-vault
ln -s "$VAULT/.rules" ~/YOUR_WORKSPACE/.rules
ln -s "$VAULT/.rules" ~/.agent/.rules
```

## Validation

Run before every commit that touches `skills/` or `.rules`:
```
./scripts/validate-skills.sh
```
