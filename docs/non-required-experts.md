# Non-Required Expert Skills

Status: proposed, not implemented
Created: 2026-10-24
Scope: `ai-vault` (`skills/`, `skills/manifest.json`)

## Need

ai-vault skills cover workflow: modes, the daily protocol, worklogs, and
memory. A few optional skills cover tooling: Jenkins pipelines, PR review
comments, presentation decks, and system diagrams. No skill holds domain
expertise such as databases or security, so agents answer those questions from
general knowledge. The vault needs expert skills for those domains.

## Definition

An expert skill meets all three rules below.

- **Not required.** Its `skills/manifest.json` entry has `"required": false`.
  Every required skill and every workflow runs unchanged when the expert is
  absent.
- **Not connected.** No other skill references, invokes, or depends on it. It
  is not added to the layers, inter-layer rules, or composite sequences in
  `skills/CROSS_SKILL_INTEGRATION.md`. It owns no workspace artifact. It is
  activated only by its own `description` match or by an explicit user
  request.
- **Governed.** The mode protocol, Write Gate, read-only Git, and the
  credential rules in `.rules` apply unchanged. An expert advises and reviews;
  it never redefines those rules.

## Candidate experts

| Expert | Scope |
| --- | --- |
| `database` | Schema and index review, query plans, migrations and rollback, locking and isolation, backup and restore checks, engine-specific settings for MySQL and PostgreSQL |
| `security` | Secret handling, dependency CVE triage, IAM and least privilege, container image hardening, security findings in PR review |
| `kubernetes` | Manifests and Helm values, Argo CD sync behaviour, resource requests and limits, probes |
| `networking` | DNS, TLS certificates, load balancers, firewall and security-group rules |
| `observability` | New Relic queries, alert thresholds, SLOs |

The list is open-ended and grows with need.

## Layout

- Each expert is a normal skill under `skills/<expert>/` with a `SKILL.md` and
  an optional `references/` directory.
- The frontmatter `name` equals the directory name.
- `version` follows `VERSIONING.md`.
- `SKILL.md` stays under 500 lines.
- The manifest entry uses `"required": false` and
  `"ides": ["antigravity", "claude", "cursor"]`.
- `scripts/validate-skills.sh` must exit 0.

## Out of scope

This document creates no skill; each expert gets its own plan before
implementation.
