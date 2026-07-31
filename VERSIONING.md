# VERSIONING.md — Semantic Versioning Strategy

## Overview

This document defines the semantic versioning strategy for all skills, templates, and artifacts in `ai-vault`. It ensures backward compatibility, clear change tracking, and smooth migration paths.

## 1. Versioning Conventions

### 1.1 SKILL.md Files
Every skill's `SKILL.md` must carry a `version` key in its YAML frontmatter, alongside
`name` and `description`. It is frontmatter, not a body line — `scripts/validate-skills.sh`
reads it from there.

```markdown
---
name: example-skill
version: "1.0.0"
description: Brief description of this skill...
---
```

**Version Semantics:**
- **Major (`X`)**: Breaking changes — new modes, renamed workflows, incompatible template structures, or API contract changes. Requires migration guide.
- **Minor (`Y`)**: Backward-compatible additions — new investigation patterns, additional worklog sections, enhanced CLI integrations. Existing skills remain compatible.
- **Patch (`Z`)**: Bug fixes, typo corrections, documentation updates, non-breaking template tweaks.

### 1.2 Templates (e.g., `worklog.template`)
Templates inherit the versioning of their parent skill but may have independent minor/patch versions when they diverge from the SKILL.md structure.

### 1.3 Cross-Skill Integration Document
`skills/CROSS_SKILL_INTEGRATION.md` documents handoff contracts between skills. Update it
whenever a skill's major version changes or a handoff pattern is added, removed, or altered.

## 2. Template Compatibility

`worklog.template` is owned by `jira-worklog-processor`. Its section list must match the
sections documented in that skill's `SKILL.md` and `worklog-reference.md`.

**Rule:** a template version must never exceed its parent skill's major version. When the
parent skill bumps to a new major, the template is updated in the same change or explicitly
deprecated. `worklog.template` currently carries no version header; it tracks
`jira-worklog-processor` directly.

## 3. Migration Guide (Breaking Changes)

### When a Major Version Bump Occurs:
1. **Publish `VERSIONING.md` update** with migration instructions and the new § 6 row.
2. **Update all affected SKILL.md files** to reflect the new frontmatter version.
3. **Create a migration checklist** for any required template updates.
4. **Notify contributors** via JIRA ticket referencing the migration guide.

### Example Migration Checklist:
- [ ] Update `version:` field in all SKILL.md files
- [ ] Review and update any template that references old sections
- [ ] Verify backward compatibility of CLI tools with new workflow modes
- [ ] Document deprecated fields/sections for future reference
- [ ] Add migration notes to `skills/CROSS_SKILL_INTEGRATION.md` if handoff patterns changed

## 4. Enforcement

`scripts/validate-skills.sh` enforces versioning locally. Run it before every commit that
touches `skills/` or `.rules`. It fails when a `SKILL.md` lacks a frontmatter `version`
matching `MAJOR.MINOR.PATCH`, and also checks frontmatter name-to-directory agreement,
description length, link integrity, code-fence balance, and skill file size.

There is no CI in this repository. The script is the enforcement point.

## 5. Changelog Placement

Skills do not carry an inline changelog. Version history lives in git. A change that bumps
a skill's version must state the bump in its commit description, using the semantics in
§ 1.1.

## 6. Current Skill Versions

| Skill | Version | Last Updated | Notes |
|-------|---------|--------------|-------|
| developer-protocol | 1.0.0 | 2026-07-31 | Canonical mode protocol; `.rules` § 3 delegates here |
| devops-daily-protocol | 1.0.0 | 2026-07-31 | Lifecycle shell, Write Gate, tool contracts |
| jira-worklog-processor | 1.0.0 | 2026-07-31 | Worklog content patterns, PR review workflow |
| jenkins-pipeline-architect | 1.0.0 | 2026-07-31 | Core rules in SKILL.md, detail in `references/` |

Update this table in the same change that bumps a skill's frontmatter version.

## Appendix: Versioning Commands

```bash
./scripts/validate-skills.sh

grep -rn '^version:' skills/*/SKILL.md
```

---

*Last updated: 2026-07-31*  
*Maintained by: `ai-vault` repository maintainers*