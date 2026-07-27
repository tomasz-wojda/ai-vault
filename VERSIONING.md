# VERSIONING.md — Semantic Versioning Strategy

## Overview

This document defines the semantic versioning strategy for all skills, templates, and artifacts in `ai-vault`. It ensures backward compatibility, clear change tracking, and smooth migration paths.

## 1. Versioning Conventions

### 1.1 SKILL.md Files
Every skill's `SKILL.md` must include a version field at the top:

```markdown
# [Skill Name]

version: "1.2.0"
description: Brief description of this skill...
```

**Version Semantics:**
- **Major (`X`)**: Breaking changes — new modes, renamed workflows, incompatible template structures, or API contract changes. Requires migration guide.
- **Minor (`Y`)**: Backward-compatible additions — new investigation patterns, additional worklog sections, enhanced CLI integrations. Existing skills remain compatible.
- **Patch (`Z`)**: Bug fixes, typo corrections, documentation updates, non-breaking template tweaks.

### 1.2 Templates (e.g., `worklog.template`)
Templates inherit the versioning of their parent skill but may have independent minor/patch versions when they diverge from the SKILL.md structure.

```yaml
# In worklog.template header or metadata section:
template-version: "1.0.3"
parent-skill-version: "2.1.0"
```

### 1.3 Cross-Skill Integration Document
`CROSS_SKILL_INTEGRATION.md` tracks the version of each skill it references and must be updated whenever a skill's major version changes or handoff patterns are affected.

## 2. Template Compatibility Matrix

| Parent Skill Version | Compatible Template Versions | Notes |
|---------------------|------------------------------|-------|
| `SKILL.md` 1.x.x | `template` 1.x.x | Original structure; no breaking changes |
| `SKILL.md` 2.0.0 | `template` 2.0.x+ | Major change: new worklog sections added; older templates may miss fields |
| `SKILL.md` 2.1.0 | `template` 2.1.x+ | Minor change: METRICS section added; template should include it for full support |

**Rule:** A template version must never exceed its parent skill's major version. If the parent skill bumps to a new major, the template must be updated or deprecated.

## 3. Migration Guide (Breaking Changes)

### When a Major Version Bump Occurs:
1. **Publish `VERSIONING.md` update** with migration instructions.
2. **Update all affected SKILL.md files** to reflect new version.
3. **Create a migration script or checklist** for any required template updates.
4. **Archive deprecated templates** in `templates/archive/` directory (if needed).
5. **Notify contributors** via JIRA ticket referencing the migration guide.

### Example Migration Checklist:
- [ ] Update `version:` field in all SKILL.md files
- [ ] Review and update any template that references old sections
- [ ] Verify backward compatibility of CLI tools with new workflow modes
- [ ] Document deprecated fields/sections for future reference
- [ ] Add migration notes to `CROSS_SKILL_INTEGRATION.md` if handoff patterns changed

## 4. Versioning in CI/CD (IMP-03.4)

The syntax validation pipeline should enforce:
1. **Version field presence**: Every SKILL.md must contain a valid semantic version (`MAJOR.MINOR.PATCH`).
2. **Template compatibility check**: Validate that template versions do not exceed parent skill major versions.
3. **No missing versions**: Reject commits where any new SKILL.md lacks a `version:` header.

## 5. Version History Template

```markdown
# [Skill Name]

version: "1.2.0"
description: Brief description...

### Changelog

#### v1.2.0 (YYYY-MM-DD)
- **Added**: New investigation pattern for Kubernetes OOMKilled failures
- **Fixed**: Worklog template missing METRICS section
- **Changed**: Updated JIRA CLI command syntax

#### v1.1.0 (YYYY-MM-DD)
- **Added**: Deployment Verification Mode documentation
- **Bugfix**: Fixed typo in Write Gate preview format

#### v1.0.0 (YYYY-MM-DD)
- Initial release
```

## 6. Versioning for `CROSS_SKILL_INTEGRATION.md`

This document tracks the version of each skill it references:

| Skill | Current Version | Last Updated | Notes |
|-------|----------------|--------------|-------|
| developer-protocol | 1.0.0 | YYYY-MM-DD | Stable; no major changes planned |
| devops-daily-protocol | 2.1.0 | YYYY-MM-DD | METRICS section added in v2.1.0 |
| jira-worklog-processor | 1.5.0 | YYYY-MM-DD | Template sync with SKILL.md |
| jenkins-pipeline-architect | 1.2.0 | YYYY-MM-DD | Syntax check script updated |

## Appendix: Versioning Commands

```bash
# Check version field in a skill's SKILL.md
grep -n "^version:" skills/devops-daily-protocol/SKILL.md

# Validate all SKILL.md files have version fields
find skills/ -name "SKILL.md" -exec grep -q "^version: [0-9]\.[0-9]\.[0-9]" {} \;

# List all versions in the repo
grep -r "^version:" skills/ | sort -u
```

---

*Last updated: 2026-03-07*  
*Maintained by: `ai-vault` repository maintainers*