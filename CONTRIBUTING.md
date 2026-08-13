# CONTRIBUTING — AI Vault

Welcome! This document covers how to contribute to **AI Vault**, the single-repo platform for multi-agent workflow automation, DevOps daily protocols, and cross-skill integration.

---

## 1. Contribution Categories

Contributions fall into one of four categories:

| Category | Examples | Skill(s) Involved |
|----------|----------|-------------------|
| **Protocol Updates** | Adding a new workflow mode, refining SKILL.md structure | `devops-daily-protocol`, `jira-worklog-processor` |
| **Content Patterns** | New FINDINGS patterns, solution option formats, PR review templates | `jira-worklog-processor` |
| **CI/CD & Tooling** | Jenkins pipeline syntax checks, repo validation scripts, Groovy tooling | `jenkins-pipeline-architect`, core tools |
| **Documentation** | README updates, examples walkthroughs, cross-skill integration guide | All skills + `skills/CROSS_SKILL_INTEGRATION.md` |

---

## 2. Pre-Commit Checklist

Before submitting any contribution:

### Protocol Changes (`SKILL.md`)

- [ ] Read the existing `SKILL.md` for consistency in formatting and terminology
- [ ] Ensure all workflow modes are documented (RESEARCH → INNOVATE → PLAN → EXECUTE)
- [ ] Verify tool contracts (JIRA CLI, NR CLI, Tempo API) are accurate
- [ ] Update `worklog.template` if the worklog structure changes
- [ ] Add examples to `examples.md` for new patterns

### Content Pattern Changes (`jira-worklog-processor/`)

- [ ] Follow existing FINDINGS format (numbered, dotted sub-sections)
- [ ] Use labeled solution options (A through E) with PROS/CONS
- [ ] Include RISK CONSIDERATIONS section for each option or cross-cutting concern
- [ ] Create phased PROPOSED ACTIONS with checkbox tracking
- [ ] Document gate-based action plans (G0 → G1 → G2 → G3 → G4)

### PR Review Changes

- [ ] Update the `PR.log` entry format if needed
- [ ] Clarify `[ ]`, `[~]`, `[x]` checkbox semantics
- [ ] Add any new review criteria or risk flags

### CI/CD & Tooling (`jenkins-pipeline-architect/`)

- [ ] Run `skills/jenkins-pipeline-architect/scripts/syntax_check.sh` before committing
- [ ] Run `scripts/validate-skills.sh` before committing any skill or rule change
- [ ] Ensure pipeline syntax is valid and tested
- [ ] Add JIRA notification comments via `postJiraComment` if applicable
- [ ] Document any new pipeline stages or gates

---

## 3. Worklog Contribution Guidelines

### Creating a New Worklog Example

1. Create a sample ticket in JIRA (e.g., `KD-9999`)
2. Run the full pipeline: "pull up KD-9999"
3. The agent will create:
   - `worklog/YYYY-MM-DD_KD-9999.log` — primary worklog
   - `worklog/YYYY-MM-DD_KD-9999_jira.log` — raw JIRA dump (optional)
4. Review the generated worklog for accuracy and completeness
5. If improvements are needed, submit a PR to update `examples.md` with the corrected example

### Worklog Section Requirements

| Section | Required? | Notes |
|---------|-----------|-------|
| TICKET header | Yes | Key, summary, status, type, priority, project, assignee, reporter, components, created, updated, description |
| FINDINGS | Yes | Numbered findings with dotted sub-sections for detail |
| REFERENCED REPOSITORIES | Optional | Add after TICKET header if ticket involves code repos |
| PROPOSED SOLUTIONS | Yes | Options labeled A through E with PROS/CONS |
| RISK CONSIDERATIONS | Yes | For each option or cross-cutting concern |
| PROPOSED ACTIONS | Yes | Phased checklist with checkbox tracking |
| ACTION LOG | Yes | Timestamped entries as work progresses |
| STATUS | Yes | Always maintain current state (RESEARCH, INNOVATE, PLAN, EXECUTE, BLOCKED, PARKED, DONE) |
| TIME LOGGED | Yes | Update on ticket completion |

---

## 4. PR Review Contribution Guidelines

### Adding a New PR Review Pattern

1. Identify the gap in the current review workflow
2. Draft the new pattern in `skills/jira-worklog-processor/SKILL.md`
3. Create an example in `examples.md` showing:
   - The ticket key and worklog
   - The PR diff
   - The structured review output
4. Submit a PR with the changes

### Updating PR.log Format

1. Read existing entries in `PR.log` for consistency
2. Draft the new format with all required sections:
   - METADATA (title, author, branch, created, state, labels, CI, reviews)
   - CHANGED FILES (file list with change type and description)
   - WORKLOG CROSS-REFERENCE (ticket key, worklog path, checklist coverage, out-of-scope changes)
   - OBSERVATIONS (numbered observations about the PR)

---

## 5. Code Contribution Guidelines

### Java/Groovy Files

1. Follow the Write Gate Protocol for any file creation/editing:
   - ANNOUNCE the operation type
   - PREVIEW full content (file content, API payload, git command)
   - WAIT — "Proceed? (yes/no)"
   - EXECUTE only after user confirms
   - VERIFY success (re-read file, re-run verify)
2. The agent never commits or pushes. It proposes a semantic commit title and description; the contributor runs the git commands.

### Jenkins Pipelines

1. Run `skills/jenkins-pipeline-architect/scripts/syntax_check.sh` before committing
2. Ensure pipeline syntax is valid and tested
3. Add JIRA notification comments via `postJiraComment` if applicable

### Skills and Rules

1. Run `scripts/validate-skills.sh`; it must exit 0
2. Keep each `SKILL.md` under 500 lines — move detail into a sibling `references/` file
3. Bump the `version:` field in the skill's frontmatter per `VERSIONING.md`

---

## 6. Testing & Verification

### Local Testing

```bash
./scripts/validate-skills.sh

./skills/jenkins-pipeline-architect/scripts/syntax_check.sh

./integrations/jira/jira-ticket-info.sh summary
./integrations/jira/jira-ticket-info.sh KD-1234

./integrations/newrelic/newrelic-info.sh apps
```

### PR Review Testing

1. Create a sample ticket in JIRA (e.g., `KD-9999`)
2. Run the full pipeline: "pull up KD-9999"
3. Create a sample PR with relevant changes
4. Trigger a PR review: "review this PR" or "review PR #N"
5. Verify the structured review output matches expectations

---

## 7. Issue Reporting

### Bug Reports

Include in your issue:

1. **Reproduction Steps**: Exact commands to reproduce the issue
2. **Expected Behavior**: What should happen
3. **Actual Behavior**: What actually happens
4. **Environment**: Java version, Groovy version, Git version, OS
5. **Logs/Output**: Relevant output from CLI tools or agent logs

### Feature Requests

Include in your issue:

1. **Problem Description**: Clear statement of the problem
2. **Proposed Solution**: Suggested approach (if any)
3. **Impact**: Why this is important
4. **Related Tickets**: JIRA ticket key if applicable
5. **Example**: Expected input/output or before/after code

---

## 8. Code Style & Formatting

### Java/Groovy

- Use `@CompileStatic` for performance-critical paths
- Use dynamic DSL for configuration and scripting
- Follow standard indentation (4 spaces)
- Add comments for complex logic

### Worklog Templates

- Use the exact structure from `worklog.template`
- Maintain consistent section headers with `================================================================================`
- Number findings sequentially
- Label solution options A through E

### PR Review Output

- Follow the format in `skills/jira-worklog-processor/SKILL.md` § PR Review Workflow
- Include all required sections: METADATA, CHANGED FILES, WORKLOG CROSS-REFERENCE, OBSERVATIONS

---

## 9. Commit Message Conventions

```
feat: description of change

Detailed explanation of the change and its impact.

Related ticket: KD-1234
```

### Example Commit Messages

```
feat: add deployment verification mode to devops-daily-protocol
Update SKILL.md with new Deployment Verification workflow mode.
Add corresponding section to worklog.template.

Related ticket: DEVOPS-9999
```

```
docs: update PR review format in jira-worklog-processor/SKILL.md
Clarify [~] and [x] checkbox semantics for PR reviews.
Add example of structured review output.

Related ticket: KD-1234
```

---

## 10. Getting Started as a Contributor

### Step 1: Understand the Architecture

Read these files in order:

1. `README.md` — Project overview and structure
2. `ONBOARDING.md` — Setup, workspace layout, safety rules
3. `skills/CROSS_SKILL_INTEGRATION.md` — How skills interact
4. `VERSIONING.md` — Versioning policy

### Step 2: Pick a Contribution

Choose one of these starting points:

1. **Update an example** in `examples.md` based on your own work
2. **Add a new FINDINGS pattern** to `jira-worklog-processor/SKILL.md`
3. **Improve the PR review format** in `jira-worklog-processor/SKILL.md`
4. **Add a new workflow mode** to `devops-daily-protocol/SKILL.md`

### Step 3: Create a Pull Request

1. Fork the repository (if contributing from outside)
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes
4. Run any applicable checks (e.g., syntax check for Jenkins pipelines)
5. Commit with a clear message following the convention above
6. Push and open a PR

### Step 4: Review & Merge

1. Reviewers will check:
   - Consistency with existing patterns
   - Completeness of documentation
   - Correctness of examples
   - Adherence to safety rules (Write Gate Protocol)
2. Address any feedback from reviewers
3. Once approved, the PR will be merged by a maintainer

---

## 11. Community Guidelines

### Respect & Collaboration

- Be respectful and constructive in all discussions
- Acknowledge others' contributions
- Provide helpful feedback on PRs

### Quality Standards

- All code must pass syntax checks (where applicable)
- All documentation must be accurate and up-to-date
- All examples must be tested and working
- All worklogs must follow the template structure

### Safety First

- Follow the Write Gate Protocol for all writes
- Never commit credentials or sensitive data
- Always verify changes before committing

---

## 12. Thank You!

Thank you for contributing to AI Vault. Your contributions help make this platform more robust, useful, and accessible to everyone.

For questions or feedback, please open an issue in the repository.