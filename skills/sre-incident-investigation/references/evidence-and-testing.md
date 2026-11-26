# Evidence Collection and Hypothesis Testing

## Evidence quality

Classify every material statement as one of:

- **Observed fact:** directly present in a source (metric, log, trace, event, config, audit record, command output).
- **Inference:** a reasoned interpretation of multiple facts; state the reasoning.
- **Hypothesis:** a possible explanation that still needs a discriminating test.
- **Unknown:** unavailable, incomplete, ambiguous, sampled, or untrusted evidence.

For material evidence capture source/tool, entity or query scope, time range, retrieval time (UTC), dimensions, and limitations. Preserve relevant trace/request IDs in redacted form where permitted.

Do not treat dashboard screenshots or single aggregate values as the complete truth. Inspect raw series, aggregation window, unit, sampling, filters, and whether the displayed data is delayed. Confirm metric semantics (for example, request count vs attempt count; server-side vs client-side latency; container vs node memory).

## Time correlation

- Normalize the investigation timeline to UTC.
- Separate event time, observation time, and ingestion time.
- Use the same time bounds across metrics, logs, traces, and deployment/audit events.
- Include a pre-incident baseline and a post-symptom period.
- Consider clock skew across clients, hosts, collectors, and providers.
- Compare the first known bad event with first alert, first customer report, and first recovery signal.

## Cross-signal correlation

Use metrics to locate when and where behavior changed; traces to locate latency and errors along a request path; logs/events to explain specific failures; profiles/resource data to explain runtime cost; and change/audit records to identify what changed.

Where supported, correlate trace ID/span ID, request ID, service/version, route, region/AZ, tenant class, and dependency. OpenTelemetry context propagation can link spans across service boundaries and correlate traces with logs; verify that propagation and sampling actually work in this environment.

Do not over-rely on distributed traces: missing spans can be caused by sampling, instrumentation gaps, async context loss, or telemetry ingestion problems. A missing span is not proof that a call did not happen.

## Design a discriminating test

A useful test answers one question and has different expected outcomes for competing explanations.

```text
Question:
Hypothesis:
Target and scope:
Time range (UTC):
Read-only method/query/command:
Expected if true:
Expected if false:
Observed result:
Interpretation:
Effect on ranking/confidence:
Evidence source and retrieval time:
Limitations / safety notes:
```

Prefer tests that:
- Locate the earliest failing or slow boundary in a path.
- Compare affected and unaffected instances under similar conditions.
- Split by service version, route, tenant, region/AZ, status code, or dependency.
- Compare request arrival rate with completed work and queue wait.
- Examine one representative trace and related logs before broad data pulls.
- Verify the actual deployed image/config/state, not just the intended repository definition.

## Hypothesis ranking

Use qualitative ranking unless the organization has a validated scoring model. Do not manufacture numerical probabilities.

Consider:
- Fit to the observed symptom and causal path.
- Fit to the timeline and known changes.
- Directness and quality of supporting evidence.
- Contradictory evidence and healthy controls.
- Blast radius and customer impact if true.
- Safety, cost, and information value of the next test.

A practical label set:

- **Untested:** plausible but not investigated.
- **Supported:** evidence matches one or more predictions, but alternatives remain.
- **Weakened:** one or more important predictions are absent or contradict the model.
- **Rejected:** strong evidence contradicts the necessary mechanism.
- **Confirmed:** direct evidence supports the mechanism and material alternatives are reasonably excluded.

Confidence (low/medium/high) is separate from status. Explain why. For example, a hypothesis may be supported with medium confidence because the key telemetry is sampled.

## Safe diagnostic execution

Before running any command/query/tool:

1. Identify the target environment/account/cluster/namespace/service and ensure it is the intended one.
2. Determine whether the operation reads or changes state. Inspect unfamiliar commands, scripts, aliases, and wrappers.
3. Bound the time range, result count, resource scope, and output fields.
4. Avoid dumping environment variables, secret objects, credentials, customer payloads, or unrestricted database rows.
5. Prefer metadata and aggregate results over raw sensitive data.
6. Record what ran and what it returned.

Examples of generally read-oriented operation classes include listing/description APIs, reading pod events/logs, querying existing metrics, viewing traces, inspecting deployment history, reading IaC diffs, and checking provider status. The exact command/API and its safety must still be verified for the target platform and permissions.

Never assume that an apparently informational command is harmless: plugins, shell aliases, scripts, hooks, and CLI wrappers can have side effects. Do not use production write operations as experiments. Do not delete pods to test resilience, inject faults, drain nodes, alter network rules, force failover, or replay messages during an active investigation without an explicitly approved exercise/change plan.

## Handling weak or conflicting evidence

- If sources disagree, preserve both observations and determine differences in scope, aggregation, clock, sampling, or ownership.
- If data is missing, identify the system that should have produced it and a safe alternate source.
- If telemetry itself may be affected, corroborate with a second independent signal.
- If test results are ambiguous, refine the hypothesis or design a better discriminator; do not force a conclusion.
- If several causes fit, report the leading candidates and the smallest test that separates them.
