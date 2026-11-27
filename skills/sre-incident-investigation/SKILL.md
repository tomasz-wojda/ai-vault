---
name: sre-incident-investigation
version: "2.1.0"
description: Use when an SRE, platform, application, or production incident needs investigation; when alerts report elevated 5xx errors, latency, saturation, availability loss, failed deployments, pod or service instability, queue backlogs, database or dependency failures, or unexplained service degradation. Use to reconstruct architecture, develop and test competing hypotheses, identify root causes, and propose evidence-based remediation. Do not use this skill to execute unapproved production changes. Also use for New Relic violations or issues, OOMKilled or CrashLoopBackOff pods, and production problems found during ticket investigation. Every invocation appends an SRE.log entry.
---

# SRE Incident Investigation

## Mission

Investigate an incident from observed symptoms to an evidence-supported causal explanation and a safe remediation plan. Work from the actual system architecture, not generic assumptions. Keep the investigation broad enough to find cross-layer causes, but make every hypothesis specific and testable.

**Primary outcome:** a concise incident assessment, an architecture/dependency diagram, a ranked hypothesis matrix with test results, a root-cause assessment with confidence, and a prioritized remediation and verification plan.

**Operating priority:** protect users and data, establish impact, stabilize through the approved incident process, preserve evidence, then deepen the diagnosis. Full root-cause certainty is not a prerequisite for proposing a safe mitigation.

## Scope and safety boundary

This skill covers incident intake, triage, architecture-aware debugging, hypothesis testing, root-cause assessment, and remediation recommendations. It may inspect available systems and run verified read-only diagnostics. It does not independently perform production remediation.

- Treat production as **read-only by default**. Do not restart, scale, redeploy, roll back, fail over, drain, delete, modify flags/configuration/IAM/network policies, run database writes, purge queues/caches, rotate secrets, or change traffic unless the user or authorized incident commander explicitly approves the exact action and scope.
- Never run an unreviewed command, script, query, or tool call with possible side effects. Check command semantics first. Prefer read-only APIs and dry-run modes where available; a dry run is not proof that a command is harmless.
- Do not expose, copy, or place credentials, tokens, private keys, customer data, or secret values in reports. Redact sensitive identifiers and payloads.
- Preserve relevant logs, traces, events, deployment metadata, and timestamps before they expire. Do not alter evidence to make an alert disappear.
- Do not infer facts from missing telemetry. Mark unavailable, sampled, delayed, or untrusted data explicitly.
- Do not call correlation causation. Do not declare a confirmed root cause without evidence for the causal mechanism.
- Escalate promptly through the incident process for suspected data loss/corruption, security compromise, safety risk, broad customer impact, payment/authentication outage, or an incident beyond the investigator's permissions or expertise.
- Follow the organization's severity definitions, incident commander, communication channel, escalation policy, and runbooks when they exist. Do not invent severity levels, owners, or approval authority.

## ai-vault integration

- **Layer:** L6, governed by R-30 and R-31 in [CROSS_SKILL_INTEGRATION.md](../CROSS_SKILL_INTEGRATION.md).
- **Modes:** read-only diagnostics are R-03 reads and run in every mode. Steps 1–7 belong to RESEARCH, remediation options to INNOVATE, the remediation plan to PLAN, and approved actions run in EXECUTE through the Write Gate of [devops-daily-protocol](../devops-daily-protocol/SKILL.md). Approval from the user or an incident commander does not replace `MODE: EXECUTE` (R-06). Phases change on `MODE:` or inside an incident pipeline (R-32).
- **Tools:** diagnostics use L2's read-only contracts (`ai-worklog service newrelic` reads, read-only `kubectl`, `ai-worklog diag list` and `ai-worklog diag run`). Credential files are passed by path only (R-08).
- **Worklog:** when a ticket worklog exists, L3 formats the FINDINGS, and large output goes to a `_raw.log` file (R-11).
- **SRE.log:** follow R-31 and use the format in [worklog-reference.md](../jira-worklog-processor/worklog-reference.md) § "SRE.log Entry Format".
- **Incident directory:** every incident file lives in `incidents/<key>/` at the workspace root: `report.md`, the `sre-log-*.txt` entry files, `evidence/` (each exact query or command next to its output) and `artifacts/` (boards, screenshots, scripts). Writes there follow the R-31 exception. Incident work does not use `tmp/`.
- **Shared helpers:** Prometheus ranges use `python3 repos/ai-vault/skills/sre-incident-investigation/scripts/prom_range.py --context <kube context> --out incidents/<key>/evidence/prom ...`. Python HTTPS calls to internal endpoints set `SSL_CERT_FILE` to the bundle written by `scripts/build_ca_bundle.py` (default `~/.cache/ai-vault/ca-bundle.pem`). Helpers are called, never copied into incidents.

## Investigation workflow

### 1. Establish incident state and impact

Collect what is available; do not block investigation because an input is missing. Record missing information as an explicit gap.

Establish:
- Incident/alert identifier, environment, affected service or workflow, reporter, and incident commander if assigned.
- First known bad time, detection time, current state, and timezone. Normalize the working timeline to UTC while retaining original timestamps when useful.
- User/business impact: affected operations, regions, tenants, customer segments, request classes, and approximate affected proportion. Separate measured impact from estimates.
- Symptoms and SLI signals: availability, error rate by class, throughput, p50/p95/p99 latency, saturation, queue age/depth, and relevant business outcomes.
- Baseline: compare with a suitable healthy period, normal traffic pattern, and unaffected regions/versions/tenants. Account for seasonality and expected traffic changes.
- Severity and urgency using the organization's policy. If no policy is known, report observable impact and state that severity is not assigned.
- Prior entries for the incident key or its ticket: `rg -n "^INCIDENT <key> |Ticket: <ticket>$" SRE.log`. Mint the key once: the Jira key when the incident arrives with a ticket, otherwise the New Relic issue or violation ID, otherwise `<primary-service>-<YYYYMMDD of the UTC start>` with `-2`, `-3` on collision. The key never changes; the full rule is in [worklog-reference.md](../jira-worklog-processor/worklog-reference.md) § "SRE.log Entry Format".

Do not focus only on the alert. Determine whether the alert reflects customer impact, an internal component symptom, telemetry failure, or a false positive.

### 2. Build the actual architecture and failure path

Reconstruct the architecture from available, current evidence: service documentation, repositories, deployment manifests, Helm/Kustomize, Kubernetes objects, Terraform/IaC, cloud inventory, load balancer/API gateway configuration, service catalog, dashboards, traces, and runbooks.

Create a Mermaid diagram when sufficient evidence exists. Include, where relevant:
- User/client entry points, DNS, CDN/WAF, load balancer, ingress/API gateway, and request routing.
- Services, jobs/workers, synchronous calls, asynchronous queues/events, caches, databases, object storage, and third-party dependencies.
- Runtime/platform boundaries: cluster, namespace, workload, node/pool, region/AZ, network, and cloud services.
- Control plane and change path: source repository, CI pipeline, artifact/image registry, IaC, deployment controller, and runtime rollout. Keep this separate from the live request/data path.
- Observability path: instrumentation, agents/collectors, telemetry pipeline, and metrics/logs/traces backend. Consider telemetry failure as a possible source of misleading evidence.
- Trust/security boundaries and important ownership boundaries when known.

Label edges with protocol, request/event direction, timeout/retry behavior, or other relevant details only when verified. Mark unknown or inferred components as `unknown` or `inferred`; use dashed edges for unverified relationships. Never present a generic reference architecture as the observed production architecture.

For every component on the affected request or job path, identify its upstream and downstream dependencies, owner (if known), relevant SLI, and available telemetry. See `references/architecture-mapping.md`.

### 3. Establish a time-aligned evidence set

Build one UTC timeline covering the period before, during, and after the incident. Include:
- Alerts and SLI changes.
- Deployments, rollbacks, image/artifact changes, feature-flag changes, configuration/secrets/certificate changes, and infrastructure changes.
- Scaling, restarts, rescheduling, node/AZ/region events, cloud-provider events, quota/limit events, and maintenance.
- Traffic changes, batch jobs, scheduled tasks, migrations, backfills, data imports, and unusual client behavior.
- Dependency health, database/queue/cache events, network/DNS/TLS events, and third-party status.

In the first turn, before retention expires, save namespace events, HPA and ScaledObject descriptions, rollout history, and container restart reasons (`lastState`) to `incidents/<key>/evidence/`.

Use comparable time windows and consistent dimensions. Distinguish event time from ingestion time. Check clock skew, delayed ingestion, sampling, retention, and cardinality limitations.

Correlate metrics, logs, and traces using request/trace identifiers and consistent attributes where available. Inspect successful and failed examples, not only aggregate failures. Compare a failing path with a healthy control (region, AZ, version, tenant, endpoint, or dependency) when safe and meaningful.

Do not assume a deployment is causal only because it preceded the incident. Verify whether the affected version/configuration maps to the affected traffic and whether behavior changed as predicted.

### 4. Generate broad, architecture-specific hypotheses

Start with the observed failure boundary, then examine adjacent upstream and downstream components. Consider multiple causes and interactions; do not stop at the first plausible explanation.

At minimum, consider these domains when relevant:
1. Application behavior: code defect, exception, deadlock, race, memory leak, garbage collection, thread/event-loop starvation, connection-pool exhaustion, regression, feature flag, or bad input.
2. Compute/runtime: CPU or memory saturation, throttling, OOM, file descriptors, disk/inodes, ephemeral storage, process limits, startup/readiness/liveness behavior, noisy neighbor, or resource requests/limits.
3. Orchestration/platform: scheduling, node pressure, autoscaler lag, rollout strategy, probe failures, eviction, cluster capacity, CNI, service discovery, ingress, network policy, or control-plane degradation.
4. Network/edge: DNS, TLS/certificates, routing, load balancer health, proxy, firewall, NAT/egress ports, connection churn, packet loss, MTU, rate limiting, or regional path issues.
5. Dependencies: database, cache, queue, identity provider, payment provider, API, storage, or other service failure; include timeout mismatch, retry amplification, circuit-breaker behavior, pool limits, quota, throttling, and dependency degradation.
6. Data/query: slow or regressed query, lock contention, missing/unused index, plan change, schema migration, replication lag, hot key, data skew, connection exhaustion, or incorrect/corrupt data.
7. Traffic/capacity: traffic spike, concurrency, fan-out, payload size, uneven distribution, hot partition, queue backlog/age, batch overlap, autoscaling delay, or capacity ceiling.
8. Release/configuration/supply chain: code or config change, incompatible artifact, image/tag/digest mismatch, dependency update, build pipeline, secret/certificate expiry, rollout, or IaC drift.
9. Cloud/provider: region/AZ issue, managed-service degradation, service quota, API throttling, maintenance, or provider-side change. Verify with provider evidence; do not assume provider fault.
10. Security/identity/policy: IAM or authorization change, expired token/certificate, identity-provider issue, policy enforcement, WAF/rate-limit rule, or secret retrieval failure. Do not disclose secret contents.
11. Observability/control: monitoring gap, bad alert expression, telemetry pipeline delay/drop, sampling, clock skew, broken instrumentation, or deployment/event correlation gap.
12. Operational/process: manual action, runbook error, scheduled operation, ownership gap, unsafe rollout, missing capacity plan, or failed change control.

Use `references/hypothesis-catalog.md` to expand relevant branches. Do not mechanically list irrelevant categories. Tailor hypotheses to the reconstructed architecture and incident evidence.

### 5. Rank hypotheses and define falsifiable tests

Create a short ranked list (normally 3–8 hypotheses; fewer when evidence is decisive). Each hypothesis must state a causal mechanism, not just a component name.

For each hypothesis record:
- **Hypothesis:** a concise `If X, then Y occurs because Z` statement.
- **Why it fits:** specific evidence and timeline correlation.
- **What argues against it:** contradictory evidence or healthy controls.
- **Predictions:** the observable signals expected if it is true, including where and when they should appear.
- **Test:** the safest, most discriminating diagnostic and exact scope/time range.
- **Expected outcomes:** what would confirm, weaken, or falsify it.
- **Result:** observed evidence with source and timestamp; never pre-fill a result.
- **Confidence/status:** untested, supported, weakened, rejected, or confirmed; low/medium/high confidence with a reason.

Prioritize tests by customer impact, causal plausibility, information gained, safety, and time to execute. Prefer one test that distinguishes competing hypotheses over many low-value checks. Test upstream and downstream boundaries to locate where a request first deviates from healthy behavior.

A test is not complete until its result is interpreted against the prediction. If evidence is unavailable, leave the hypothesis unresolved rather than treating missing evidence as disproof. See `references/evidence-and-testing.md`.

### 6. Execute safe diagnostics

Discover the tools and permissions actually available in the current environment. Use existing observability integrations, read-only APIs, approved CLI tools, source repositories, and runbooks. Do not invent tool names, dashboards, metric names, query syntax, Kubernetes resources, cloud identifiers, or commands.

For every diagnostic action:
1. State the question it answers.
2. Confirm that the operation is read-only and its scope is bounded.
3. Specify the target, time range, filters, and dimensions.
4. Run the narrowest useful query or command.
5. Capture source, query/command, timestamp, and result summary.
6. Explain how the result changes the hypothesis ranking.

Use representative samples before large log or trace pulls. Bound queries by time, service, environment, status, and request/trace identifier when possible. Avoid unbounded scans and unnecessary high-cardinality queries. Redact secrets and personal/customer data.

If a potentially useful test is state-changing, expensive, disruptive, or outside granted permissions, do not run it. Describe the proposed test, risk, scope, expected value, and required approval.

### 7. Determine the causal explanation

Build a causal chain, not just a list of correlated events:

`precondition / latent weakness -> trigger -> failure mechanism -> propagation or amplification -> user-visible symptom -> impact`

Separate:
- **Root cause:** the underlying technical or systemic condition that made the failure possible.
- **Trigger:** the event that activated the condition.
- **Contributing factors:** conditions that increased likelihood, duration, or blast radius.
- **Propagation/amplification:** retries, queues, fan-out, failover, shared dependencies, or other mechanisms that spread impact.
- **Detection/response gaps:** why detection, diagnosis, mitigation, or recovery was delayed.

Declare a root cause **confirmed** only when the causal mechanism is supported by direct evidence, the timeline and affected path fit, and material competing explanations have been tested or reasonably excluded. Otherwise label it **most likely**, **probable**, or **undetermined**, state confidence, and list the evidence needed to confirm it.

Label the trigger separately, with its own certainty and evidence type (`direct` or `correlational`). A root cause is **confirmed** only with a confirmed trigger backed by direct evidence. While the trigger is undetermined, the status is `recovered` once impact ends, never `monitoring` or `resolved`. Use `recurring` while impact keeps returning and the precondition persists, whatever the trigger label.

A recovery after a change is useful evidence but is not automatically proof: check for concurrent changes, traffic changes, delayed recovery, and regression risk. Multiple interacting root causes are possible.

### 8. Recommend remediation and verification

Separate recommendations into four layers:
1. **Mitigation:** reduce current user impact using the smallest, reversible, approved action. Full causal certainty is not required if the affected boundary is known and the mitigation is safe.
2. **Corrective fix:** remove the demonstrated defect or failure mechanism.
3. **Prevention/resilience:** reduce recurrence or blast radius through limits, isolation, backpressure, bounded retries/timeouts, idempotency, capacity controls, safer rollout, dependency resilience, data safeguards, or architecture changes as appropriate.
4. **Detection/operability:** improve SLOs, alerts, dashboards, tracing/logging, runbooks, ownership, tests, and incident readiness.

For every recommendation provide: linked evidence/root cause, expected effect, priority, scope, owner/team if known, risk and side effects, prerequisites, rollout/canary approach, success criteria, rollback plan, and required approval. Do not invent owners or claim approval.

Prefer staged, reversible changes with narrow blast radius. Call out data-integrity, compatibility, availability, security, cost, and cross-service risks. Do not recommend simply increasing resources, retrying more, or restarting components without explaining why that addresses the mechanism and what new risks it creates.

After an authorized fix is applied, verify recovery against the original impact signals and business outcomes. Check error rate, latency, throughput, saturation, queue age/depth, dependency health, and affected customer paths as appropriate. Confirm that healthy controls remain healthy and that the system stays stable for a meaningful observation window. State the observation window and residual risk. Do not call an incident resolved from a single healthy datapoint.

### 9. Communicate continuously

Keep `incidents/<key>/report.md` current in every investigating turn, using the Investigation report template. Chat carries only what changed. Before the SRE.log append, run `python3 repos/ai-vault/skills/sre-incident-investigation/scripts/check_report.py --report incidents/<key>/report.md` from the workspace root and fix every violation. `H<n>` in SRE.log equals rank n in report section 5.

For an active incident, provide a short status update when material evidence changes, when the leading hypothesis changes, before a risky proposed action, and at an agreed incident cadence. Separate facts, hypotheses, decisions, and unknowns. Avoid speculation in customer-facing statements.

If investigation is blocked, state exactly what evidence or access is missing, why it matters, and the smallest next step to obtain it. Continue with available evidence rather than repeatedly asking for information already supplied.

### 10. Record the invocation in SRE.log

1. Write the entry with the Write tool to `incidents/<key>/sre-log-<YYYYMMDDTHHMM>.txt`, taking the timestamp from `date +%Y%m%dT%H%M` (local time, never `date -u`). The append rejects headers more than 15 minutes old and new keys that differ from `Ticket:`.
2. From the workspace root, run `python3 repos/ai-vault/skills/sre-incident-investigation/scripts/append_sre_log.py --entry <that file>`.
3. This happens in any mode, without PREVIEW or WAIT. If the append is rejected, fix the entry and rerun.
4. A turn that only reads or edits the skill files ends with `No SRE log entry needed.` instead.

## Phase gates and incident pipeline

A phase is complete only when its gate passes. `check_report.py` checks structure; the agent checks content.

- **RESEARCH gate:** sections 1–6 filled; every hypothesis has a status; the root cause and trigger are labelled; impact and detection are measured or written as `not measured — <reason>`; the first-turn snapshot is saved.
- **INNOVATE gate:** every 7.1 row names the hypothesis it addresses, followed by a `Recommended combination:` line.
- **PLAN gate:** the 7.2 table and implementation checklist, with every production step naming its approval and `MODE: EXECUTE`; 7.3 lists every untested hypothesis and precondition the plan depends on; the report state is PLAN-READY or PLAN-READY-WITH-CONDITIONS.

**Incident pipeline (R-32):**
- It starts with `PIPELINE: <ticket, alert or incident key>` and is bound to that one incident key.
- It advances RESEARCH, INNOVATE and PLAN without `MODE:` phrases when each gate passes, declaring the mode in each response.
- It returns to RESEARCH when new evidence contradicts the root cause.
- The SRE.log `Mode:` is the mode at the end of the turn.
- It stops at PLAN-READY or PLAN-READY-WITH-CONDITIONS, at any user `MODE:` phrase, or when blocked; a blocker is written into section 9.
- It never enters EXECUTE.

## Required final deliverable

Use `references/output-templates.md`. The deliverable lives in `incidents/<key>/report.md`. At minimum, report:

1. **Incident summary:** report state and go/no-go, current status, severity (or unassigned), affected service/environment, start time (UTC), and customer/business impact.
2. **Architecture:** verified Mermaid diagram of the relevant request/job path, dependencies, control plane, and observability path; list unknowns.
3. **Timeline:** key symptoms, changes, events, tests, mitigations, and recovery markers in UTC.
4. **Evidence:** sources, exact queries/commands where useful, observations, limitations, and missing telemetry.
5. **Hypothesis matrix:** ranked candidates, predictions, test, result, status, and confidence.
6. **Root-cause assessment:** causal chain; root cause, trigger, contributors, propagation, and detection/response gaps; clearly label certainty.
7. **Remediation:** 7.1 options (INNOVATE); 7.2 plan with immediate mitigation, corrective fix, preventive work, detection improvements, priorities, risks, approvals, owners (if known), verification/rollback criteria and the implementation checklist (PLAN); 7.3 pre-EXECUTE validation listing every test still needed, whether it blocks, and its status.
8. **Open questions and next actions:** only unresolved items that materially affect diagnosis or safe recovery.

Do not pad the report with generic advice. Every major conclusion must point to evidence. Clearly distinguish observed fact, inference, hypothesis, and recommendation.

## Reference files

Load only the references needed for the current incident:
- `references/architecture-mapping.md` — architecture discovery, Mermaid guidance, and diagram patterns.
- `references/hypothesis-catalog.md` — cross-layer failure modes, symptoms, and discriminating tests.
- `references/evidence-and-testing.md` — evidence quality, telemetry correlation, safe diagnostic design, and hypothesis scoring.
- `references/root-cause-and-remediation.md` — causal analysis, mitigation/fix/prevention, and recovery verification.
- `references/output-templates.md` — active incident updates, investigation report, hypothesis matrix, and RCA format.
- `references/worked-examples.md` — illustrative end-to-end investigations.
- `references/further-reading.md` — primary SRE, cloud operations, and observability references.
- [worklog-reference.md](../jira-worklog-processor/worklog-reference.md) § "SRE.log Entry Format" — the SRE.log entry fields and their order.
