# AI Vault - One Repo To Rule Them All

```
ai-vault/
├── .agent/skills                 <- Create symlink to skills/        (AntiGravity)
├── .cursor/skills                <- Create symlink to skills/        (Cursor)
├── skills/                       <- Single truth for SKILLS
│   ├── developer-protocol/
│   │   └── SKILL.md
│   ├── devops-daily-protocol/
│   │   └── SKILL.md
│   ├── jenkins-pipeline-architect/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── syntax_check.groovy
│   └── jira-worklog-processor/
│       ├── SKILL.md
│       ├── default_prompt
│       ├── worklog.template
│       ├── worklog-reference.md
│       └── examples.md
├── .rules                        <- Single truth for Rules           (AntiGravity, Cursor)
└── README.md                     <- This file
```

## Skill Layering

```
┌─────────────────────────────────────────────────┐
│  jira-worklog-processor                         │
│  Content: FINDINGS patterns, solution options,  │
│  gap analysis, gate plans, cross-ticket refs    │
├─────────────────────────────────────────────────┤
│  devops-daily-protocol                          │
│  Lifecycle: pickup, investigation, done, verify │
│  Tools: JIRA CLI, NR CLI, Tempo API             │
├─────────────────────────────────────────────────┤
│  developer-protocol                             │
│  Modes: RESEARCH → INNOVATE → PLAN → EXECUTE   │
├─────────────────────────────────────────────────┤
│  jenkins-pipeline-architect                     │
│  CI/CD: scripted pipelines, JIRA notifications  │
└─────────────────────────────────────────────────┘
```

## Symlink Setup

### Skills

Windows:
```
mklink /J C:\Users\YOUR_PROFILE\.gemini\.agent\skills X:\repositories\ai-vault\skills
```

macOS/Linux:
```
ln -s /path/to/ai-vault/skills ~/.cursor/skills
ln -s /path/to/ai-vault/skills ~/.agent/skills
```

### Rules

Windows:
```
mklink C:\Users\YOUR_PROFILE\.gemini\.agent\.rules X:\repositories\ai-vault\.rules
```

macOS/Linux:
```
ln -s /path/to/ai-vault/.rules ~/YOUR_WORKSPACE/.rules
ln -s /path/to/ai-vault/.rules ~/.agent/.rules
```
