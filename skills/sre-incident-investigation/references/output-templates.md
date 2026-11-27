# Incident Output Templates

Use the shortest template that communicates the current state. During an active incident, lead with impact, status, and next action. In the final report, include architecture, evidence, hypothesis tests, cause, and remediation. The Investigation report lives in `incidents/<key>/report.md` and is kept current every investigating turn.

## Active incident update

```markdown
### Incident update — <UTC timestamp>
- Status: investigating / mitigating / recovered / recurring / monitoring / resolved
- Severity: <organization-defined value or unassigned>
- Impact: <verified user/business impact; state estimates explicitly>
- Affected scope: <service, environment, region/AZ, tenant, route, version>
- Since last update: <new facts or test results>
- Leading hypothesis: <statement + confidence; or not yet established>
- Current action: <read-only test or approved mitigation>
- Risk / blocker: <if any>
- Next update / next decision: <time or event, if agreed>
```

## Hypothesis matrix

| Rank | Hypothesis and mechanism | Evidence for | Evidence against / gap | Discriminating test | Result | Status / confidence |
|---:|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

## Investigation report

```markdown
# Incident investigation — <incident identifier/title>

## 1. Executive summary
- Report state: <RESEARCH|INNOVATE|PLAN-READY|PLAN-READY-WITH-CONDITIONS|EXECUTING|VERIFIED>
- Go/No-go: <READY|READY WITH CONDITIONS|NOT READY> — <reason>
- Status:
- Severity:
- Start/detection/recovery times (UTC):
- Affected service/environment:
- User/business impact:
- Root-cause status and confidence:

## 2. Architecture and failure path
<Verified Mermaid diagram>

- Verified components/edges:
- Unknown or inferred components/edges:
- Relevant shared dependencies and blast-radius boundaries:

## 3. Timeline (UTC)
| Time | Event / observation | Source | Fact or inference |
|---|---|---|---|

## 4. Evidence
| ID | Observation | Source/query/scope | Timestamp | Limitations |
|---|---|---|---|---|

## 5. Hypotheses and tests
<Insert ranked hypothesis matrix. Include expected predictions and actual results.>

## 6. Root-cause assessment
- Root cause (confirmed / most likely / undetermined):
- Trigger (confirmed / most likely / probable / undetermined; direct / correlational / none):
- Contributing factors:
- Propagation/amplification:
- Detection/response gaps:
- Causal chain:
- Remaining uncertainty:

## 7. Remediation

### 7.1 Options
| ID | Option | Category | Addresses | Advantages | Disadvantages / risk |
|---|---|---|---|---|---|

Recommended combination:

### 7.2 Plan
| Priority | Action | Category | Evidence link | Owner | Risk / approval | Success / rollback criteria |
|---|---|---|---|---|---|---|

IMPLEMENTATION CHECKLIST:
1.

### 7.3 Pre-EXECUTE validation
| ID | Unproven | Ref | Plan step | Test and environment | Owner | Blocking | Status |
|---|---|---|---|---|---|---|---|
| V1 | <what is unproven> | H<rank> or plan precondition | <checklist step> | <test, environment> | <owner or unassigned> | yes/no | pending/passed/failed/waived |

## 8. Recovery verification
- Original impact signals:
- Before/after comparison:
- Observation window:
- Data integrity checks:
- Residual risk:

## 9. Open questions and next actions
- [ ]
```

## RCA summary for a wider audience

```markdown
### What happened
<Plain-language description of the user-visible failure and its duration.>

### Why it happened
<Specific technical mechanism. State certainty honestly.>

### What increased the impact
<Contributing conditions and propagation mechanisms.>

### How it was detected and mitigated
<Detection, response, and recovery timeline.>

### What will prevent recurrence
<Owned, prioritized corrective/preventive/detection actions.>
```

## Evidence wording

Prefer:
- `Observed: ... in <source> for <scope> between <UTC start> and <UTC end>.`
- `Inference: ... because observations A and B align; limitation C remains.`
- `Hypothesis: ...; not yet tested.`
- `Not observed: ...; the source may be sampled or incomplete, so this does not exclude the cause.`

Avoid unsupported statements such as `the database was the root cause`, `the deployment caused it`, or `the issue is fixed` without showing the mechanism and verification evidence.
