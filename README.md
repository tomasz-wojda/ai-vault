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
│   └── jenkins-pipeline-architect/
│       ├── SKILL.md
│       └── scripts/
│           └── syntax_check.groovy
├── .rules                        <- Single truth for Rules           (AntiGravity, Cursor)
└── README.md                     <- This file
```

Symlink creation command:
mklink /J C:\Users\YOUR_PROFILE\.gemini\.agent\skills X:\repositories\ai-vault\skills
Junction created for C:\Users\YOUR_PROFILE\.gemini\.agent\skills <<===>> X:\repositories\ai-vault\skills
