# Root Cause, Remediation, and Recovery Verification

## Causal model

Describe the incident as a chain from conditions to impact. Include intermediate propagation mechanisms where they matter.

```text
Latent condition / design weakness
              |
              v
Trigger or change
              |
              v
Failure mechanism in component A
              |
              v
Propagation / amplification through dependency or shared resource
              |
              v
User-visible symptom / failed business operation
              |
              v
Observed impact and duration
```

Add or remove links based on evidence. A simple chain is not mandatory; interacting causes may form a graph.

## Root cause vs trigger vs contributing factor

- The **root cause** explains why the failure mechanism occurred or why the system could not tolerate it.
- The **trigger** explains why it happened at that time.
- A **contributing factor** made the failure more likely, severe, or long-lived.
- A **propagation mechanism** explains how a local failure became broader (for example, unbounded retries or shared resource exhaustion).
- A **detection/response gap** explains why the issue was not detected, localized, mitigated, or recovered sooner.

Do not describe a person as the root cause. Examine the system conditions, controls, interfaces, assumptions, and incentives that allowed the action or failure to create impact.

## Evidence threshold

A defensible root-cause statement should answer:

1. What failed, in which component and path?
2. By what technical mechanism did it fail?
3. Why did the mechanism produce the observed symptoms and affected scope?
4. What evidence ties the mechanism to the incident timeline?
5. Which competing explanations were tested, and what weakened or excluded them?
6. What uncertainty remains?

Use labels consistently:
- **Confirmed:** direct evidence for the causal mechanism; timeline and blast radius fit; important alternatives reasonably excluded.
- **Most likely / probable:** strongest explanation but one or more key links are inferred or not yet tested.
- **Undetermined:** several explanations remain or telemetry is insufficient.

A change followed by recovery is supporting evidence, not automatic proof. Check for concurrent changes, natural traffic decline, delayed effects, and rollback confounders.

## Remediation layers

### 1. Immediate mitigation

Goal: reduce user impact quickly while preserving safety and evidence.

Examples to consider, only when supported by the failure model and approved: stop or reduce a faulty rollout, revert a known-bad configuration, shed noncritical load, disable a problematic feature, route around an unhealthy dependency, or apply bounded traffic controls.

For each proposed mitigation explain the smallest scope, reversibility, expected impact, risks, exact approval needed, success signal, and rollback condition. A mitigation can be appropriate before full root cause is known, but its rationale and uncertainty must be explicit.

### 2. Corrective fix

Remove the demonstrated defect or failure mechanism. Examples may include correcting code/config, fixing a query or index, addressing connection lifecycle, repairing dependency contracts, correcting an IAM/policy rule, or resolving a resource/limit mismatch. Tie each fix directly to evidence.

### 3. Prevention and resilience

Consider guardrails that reduce recurrence or blast radius:
- Timeouts with coherent budgets across call chains.
- Bounded retries with backoff/jitter and retry budgets.
- Circuit breaking, bulkheads, admission control, rate limits, and backpressure.
- Idempotency and safe replay for asynchronous work.
- Capacity headroom, autoscaling signals, quotas, and load testing.
- Isolation by tenant, region, workload, or criticality.
- Safe rollout, canary analysis, automated rollback criteria, and configuration validation.
- Data validation, migration safeguards, backups, and recovery tests.
- Dependency failure modes and graceful degradation.

Do not recommend generic increases in replicas, CPU, memory, timeouts, or retries without a measured bottleneck and an analysis of secondary effects.

### 4. Detection and operations

Improve the ability to detect and respond:
- User-facing SLOs and alerts tied to actionable symptoms.
- Saturation, queue age, dependency latency, and business-operation signals.
- Dashboards with service/version/region/tenant segmentation where appropriate.
- Trace/log correlation and telemetry completeness.
- Runbooks with owner, safe diagnostics, escalation, and approval steps.
- Deployment/change visibility and service ownership metadata.
- Exercises for high-risk failure modes.

## Action item format

For each proposed action capture:

| Field | Required detail |
|---|---|
| Action | Specific change or investigation task |
| Category | Mitigation / corrective / preventive / detection |
| Evidence link | Root-cause or risk evidence this action addresses |
| Priority | P0/P1/P2 only if the organization defines these; otherwise critical/high/medium/low |
| Owner | Named team/person only when known; otherwise `unassigned` |
| Scope | Service, region, environment, tenant, and rollout scope |
| Risk | Availability, data, security, compatibility, cost, and operational risks |
| Prerequisites | Tests, approvals, backups, dependency coordination, or maintenance window |
| Rollout | Canary/staged approach and observation criteria |
| Success criteria | Measurable target and required stable observation window |
| Rollback | Trigger, method, and responsible authority |

## Recovery verification

Define verification before the change where possible. Compare with the pre-incident baseline and original user impact:

- The affected operation succeeds end-to-end, not merely that processes are running.
- Error rate and latency recover for the affected route/tenant/region/version.
- Throughput and business outcomes return to expected levels.
- Saturation, pool wait, dependency health, queue depth/oldest age, and replication lag return to safe ranges.
- No data loss, duplication, corruption, or delayed asynchronous failures are evident.
- Healthy controls remain healthy; no new error class or downstream regression appears.
- Recovery persists for a meaningful observation window appropriate to traffic patterns and delayed work.

Record the observation interval, evidence sources, residual impact, and rollback trigger. A green health check alone is insufficient evidence of service recovery.
