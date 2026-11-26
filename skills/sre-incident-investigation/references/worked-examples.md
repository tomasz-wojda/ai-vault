# Worked Examples

All examples are fictional and demonstrate the reasoning format. Metrics, services, timelines, and results are illustrative, not operational facts or commands to run.

## Example 1 — 5xx increase after a release

### Initial observation

A service reports a sharp increase in HTTP 5xx responses shortly after a rollout. The alert alone does not prove the rollout caused the incident.

### Architecture to reconstruct

Trace the affected route through gateway -> service version/replicas -> synchronous dependencies -> data store. Add the CI/build/artifact/deployment path separately. Determine whether all replicas run the same image digest and effective configuration.

### Competing hypotheses

| Rank | Hypothesis | Prediction | Test |
|---:|---|---|---|
| 1 | New application version causes an exception on a particular route/input. | Errors cluster by version and route; trace/log shows matching exception. | Compare error rate by version/route and inspect bounded failing traces/logs. |
| 2 | New configuration points to an invalid dependency endpoint or credential reference. | Failures appear on replicas with the new effective config; dependency connection/auth failures occur. | Compare effective non-secret config metadata and dependency errors by replica/version. |
| 3 | Downstream dependency degraded independently and the rollout is coincidental. | Similar dependency latency/errors affect old and new versions. | Compare dependency spans and old-version traffic over the same interval. |
| 4 | Gateway or routing behavior changed during rollout. | Gateway status/target health or route distribution changes before application errors. | Correlate gateway events, target health, and per-target responses. |

### Example test interpretation

Suppose errors occur only on the new version, and a representative trace shows a new code path raising a specific exception before any downstream call. Old-version requests to the same dependency succeed. This supports a release regression and weakens an independent dependency outage. A code/config diff and reproducible failing condition may provide confirmation.

### Causal statement

`Most likely: the new application version introduced an exception in the affected route. The rollout triggered exposure; route-specific traffic determined the scope. Confirmation requires matching the exception to the changed code path and excluding an effective configuration difference.`

### Remediation proposal

Recommend a scoped, approved rollback or traffic shift as mitigation if the old version is verified healthy and compatibility permits. Propose a corrective code fix, regression test for the failing path, canary checks by route/version, and recovery verification of 5xx, latency, and business success. Do not execute the rollback without explicit approval.

## Example 2 — p99 latency increase with no major error-rate change

### Initial observation

The service remains available, but p99 latency increases. p50 is relatively stable. This pattern suggests a tail-latency or queueing problem, but it does not identify the component.

### Competing hypotheses

| Rank | Hypothesis | Prediction | Test |
|---:|---|---|---|
| 1 | Database lock or query wait affects a subset of requests. | Slow traces show database spans; lock/wait or query latency rises for matching operations. | Compare slow and normal traces, DB waits, and query fingerprints in the same time window. |
| 2 | Connection pool wait or thread starvation creates queueing. | Application-side wait increases before DB call; pool/thread utilization reaches a limit. | Compare pool wait, active connections, thread/event-loop metrics, and span timing. |
| 3 | One tenant/key/partition is hot. | Tail latency clusters by tenant, key class, or partition. | Compare latency and workload distribution by safe aggregate dimensions. |
| 4 | A downstream dependency has intermittent slowness. | Slow traces have a long dependency span; unaffected traces do not. | Segment traces by dependency and compare caller/callee timing. |

### Example test interpretation

Suppose slow traces show most added time before the database query begins, and pool-wait time rises while the database itself remains within its normal latency range. This weakens the hypothesis that the database engine is slow and supports client-side connection-pool contention. Verify whether concurrency, pool sizing, connection leaks, or downstream-held connections explain the wait.

### Remediation proposal

Do not immediately increase pool size: that may transfer overload to the database. First establish whether connections are held too long, leaked, or sized incorrectly relative to database capacity. Recommend a measured corrective change, concurrency limits/backpressure where needed, load testing, and p99 plus database saturation verification.

## Example 3 — asynchronous queue backlog

### Initial observation

Queue depth and oldest-message age increase. The producer remains healthy and the consumer group appears active.

### Competing hypotheses

| Rank | Hypothesis | Prediction | Test |
|---:|---|---|---|
| 1 | Consumer throughput fell due to downstream database latency or throttling. | Consume rate falls; consumer traces show slow DB calls or throttling. | Compare publish/consume rates, consumer spans, and downstream saturation. |
| 2 | Partition or key skew concentrates work on a subset of consumers. | Lag is uneven by partition/key; some consumers are saturated while others are idle. | Compare lag and throughput per partition/consumer. |
| 3 | Poison messages or repeated retries block progress. | Repeated failures/re-deliveries correlate with message age; DLQ/retry counters rise. | Inspect a tightly bounded, redacted sample and retry/DLQ metadata. |
| 4 | Consumer deployment/configuration reduced effective parallelism. | Desired vs active consumers, concurrency, or partition assignment changes at incident start. | Compare rollout/config history and effective consumer assignment. |

### Example test interpretation

Suppose consume rate falls exactly when downstream database throttling rises, and consumer traces show the database call dominates processing time. Partition lag is balanced and retry counts are normal. This supports downstream capacity/throttling as the bottleneck rather than a poison-message or partition-skew problem.

### Remediation proposal

Recommend protecting the database and restoring bounded consumer throughput with an approved, staged change. Consider backpressure, controlled concurrency, retry budgets, and replay safety. Verify oldest-message age, backlog drain rate, database health, duplicate/idempotency behavior, and end-to-end processing outcomes.
