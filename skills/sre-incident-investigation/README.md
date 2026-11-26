# SRE Incident Investigation Skill

A reusable agent skill for architecture-aware production incident investigation. It guides an agent from alert validation and impact assessment through architecture reconstruction, evidence collection, hypothesis testing, causal analysis, and remediation recommendations.

## Contents

- `SKILL.md` — skill entry point and mandatory investigation workflow.
- `references/architecture-mapping.md` — reconstructing the real system and drawing Mermaid diagrams.
- `references/hypothesis-catalog.md` — broad failure domains and diagnostic directions.
- `references/evidence-and-testing.md` — evidence handling, telemetry correlation, safe tests, and hypothesis ranking.
- `references/root-cause-and-remediation.md` — causal analysis and remediation planning.
- `references/output-templates.md` — incident updates, report, hypothesis matrix, and RCA templates.
- `references/worked-examples.md` — illustrative investigations.
- `references/further-reading.md` — primary references.

## Design principles

1. **Architecture first:** investigate the actual topology and request/job path instead of assuming a generic stack.
2. **Hypothesis-driven:** every candidate cause has predicted signals and a test that can weaken or falsify it.
3. **Evidence over confidence theater:** unknowns and telemetry gaps remain visible; certainty is never fabricated.
4. **Safe by default:** investigation is read-only. Production changes require explicit authorization for the exact action and scope.
5. **Remediation is causal:** fixes map to a demonstrated mechanism and include risks, rollout, rollback, and measurable verification.
6. **Tool-agnostic:** use the observability, cloud, source-control, CI/CD, and runtime tools that are actually available. The examples do not assume a particular vendor.

## Installation

Place the directory in the skills location supported by your agent runtime. For example, a repository may keep it under:

```text
.agents/skills/sre-incident-investigation/
  SKILL.md
  README.md
  references/
```

Use the exact discovery path required by the agent framework in use. Keep `SKILL.md` and its `references/` directory together.

## Customization recommended before production use

Add organization-specific information in separate reference files rather than bloating `SKILL.md`:

- Service catalog, owners, criticality, and dependency map.
- Severity definitions, escalation contacts, incident roles, and communication cadence.
- SLOs, alert definitions, dashboards, and approved query examples.
- Production access policy, read-only roles, change-approval process, and emergency procedures.
- Environment-specific command examples and known failure modes.

Do not add real secrets, tokens, private keys, customer payloads, or sensitive incident data. Review the skill after significant architecture or tooling changes and validate it against completed incidents.

## Tooling note

No diagnostic scripts are included because safe commands and telemetry queries depend on the real account, cluster, observability platform, permissions, and naming conventions. Add scripts only after those interfaces are known; make their default behavior read-only, bounded, explicit about scope, and safe on missing data.
