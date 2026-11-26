# Cross-Layer Hypothesis Catalog

Use this catalog to avoid narrow diagnosis. Select and tailor only branches that fit the real architecture and symptom. The listed signals are diagnostic directions, not proof.

| Domain | Example causal hypotheses | Signals to inspect | Useful discriminating tests |
|---|---|---|---|
| Application/code | A release introduced an exception, lock contention, deadlock, race, unbounded work, or slow code path. | Error class, stack trace, endpoint/version split, CPU profile, thread/event-loop state, trace span duration. | Compare old/new versions on the same operation; inspect one failing trace and corresponding logs; compare code/config diff. |
| Memory/runtime | Heap growth or native memory exhaustion causes GC pauses, OOM kills, or process restarts. | RSS/heap, GC pause/time, OOM events, restart count, memory by container/process. | Compare memory slope and restart timestamps by version/replica; distinguish container limit from node pressure. |
| CPU/concurrency | CPU throttling, thread-pool exhaustion, event-loop blocking, file descriptor exhaustion, or connection pool saturation prevents request completion. | CPU usage and throttling, run queue, worker/thread pool, active/idle connections, FD count, queue wait. | Compare utilization with configured limits and request concurrency; inspect the first saturated resource. |
| Kubernetes/platform | Scheduling or node pressure, probe failures, rollout behavior, CNI, ingress, HPA, or cluster capacity disrupts workloads. | Pod events, pending pods, evictions, node conditions, replica availability, HPA decisions, rollout history, probe failures. | Compare affected and healthy nodes/AZs; inspect event sequence and desired vs ready replicas; check autoscaler lag. |
| Network/edge | DNS, TLS, load balancer, proxy, NAT/egress, routing, or packet loss breaks one path. | DNS failures/latency, TLS handshake/certificate errors, LB target health, resets, connection timeouts, egress/NAT metrics. | Compare source-to-target path from affected and healthy locations; resolve names; inspect handshake and connection phase. |
| Database | Query plan regression, lock contention, connection exhaustion, storage pressure, failover, replication lag, or index/schema change slows or breaks operations. | Query latency, waits/locks, active connections, pool wait, IOPS/throughput, CPU, replica lag, failover events, query plans. | Compare slow and healthy query fingerprints; inspect lock/wait events and pool usage; compare before/after plan or schema change. |
| Cache | Cache outage, eviction, hot key, stampede, stale data, or changed hit ratio overloads an origin. | Hit/miss ratio, evictions, latency, key distribution, origin request rate, connection state. | Compare cache hit/miss by key class or tenant; inspect origin load when hit ratio changed. |
| Queue/stream | Consumer failure or lag, poison messages, partition skew, rebalances, throttling, or retry storm increases queue age. | Queue depth and oldest age, publish/consume rate, lag by partition, retries, DLQ count, consumer health. | Compare producer and consumer rates; inspect a bounded sample of failed messages with payload redaction; compare partition distribution. |
| Traffic/capacity | Traffic spike, fan-out, large payload, hot tenant, uneven sharding, batch overlap, or autoscaling delay exceeds capacity. | RPS, concurrency, payload size, tenant/route distribution, queue age, resource saturation, scaling events. | Segment by route/tenant/region/client; compare arrivals with service capacity and autoscaler reaction time. |
| Capacity response | The autoscaler does not react: its signal disappears when pods crash, `noDataError: false` reads missing data as zero load, the minimum replica count leaves no headroom, or crash-looping and metric-less pods are discounted on scale-up. | Desired vs current replicas, HPA/ScaledObject conditions and events, scaler metric value and gaps, per-pod load against the scaling threshold, restart timestamps. | Overlay replica count on restart timestamps; check whether the scaling metric is self-reported by the failing pods; compare per-pod load before the incident with the threshold. |
| Dependencies/third parties | Downstream latency, quota, rate limit, auth failure, regional degradation, or changed API behavior propagates upstream. | Dependency span latency/error, status codes, retry counts, provider status, quota/throttle metrics, auth errors. | Compare caller and provider evidence; identify the earliest slow/error span; check rate-limit headers and quotas. |
| Release/configuration | Bad config, feature flag, secret/certificate expiry, image mismatch, incompatible dependency, rollout, or IaC drift changes runtime behavior. | Change audit, deployment events, config checksum/version, image digest, flag history, cert expiry, runtime vs desired state. | Compare affected and unaffected replicas/regions; verify artifact digest and effective config version without exposing secret values. |
| Cloud/provider | Managed service or control-plane event, AZ/region impairment, quota, or provider API throttling creates a failure. | Provider health/advisories, service events, API throttles, resource state, region/AZ correlation. | Check provider evidence and account-specific events; compare other AZ/region and customer-managed components. |
| Security/identity | IAM/policy change, token/certificate expiry, IdP degradation, WAF rule, or secret retrieval issue denies otherwise valid work. | 401/403 split, auth latency, token validity metadata, policy audit, WAF logs, secret-store access errors. | Compare identity and resource policy events with exact failing operation; never retrieve or print secret contents. |
| Data/migrations | Migration, backfill, malformed data, data skew, schema incompatibility, or replication issue breaks one path. | Migration timeline, validation errors, row/partition skew, replication lag, data-quality checks. | Compare affected records/partitions using privacy-safe aggregates; inspect schema compatibility and migration progress. |
| Observability | Collector/backend ingestion lag, sampling, cardinality, clock drift, or instrumentation regression creates missing or misleading signals. | Telemetry volume, dropped spans/logs, collector queue, ingest delay, scrape gaps, clock offsets. | Compare source-side counters with backend ingestion; use application-level evidence independently of dashboards. |
| Operations/process | Manual change, scheduled task, runbook action, unsafe change window, or ownership/escalation gap contributes. | Audit trail, change records, job schedules, operator actions, incident timeline, approval records. | Match exact action and scope with affected components; interview/context is corroboration, not sole technical proof. |

## Symptom-to-domain starting points

- **5xx increase:** separate application-generated 5xx from gateway/dependency errors; segment by route, version, region, and dependency. Check if errors are immediate or follow timeout duration.
- **Latency increase without 5xx:** inspect queueing, saturation, dependency spans, lock/pool wait, cache hit ratio, and GC; compare p50 with p95/p99 to identify tail-only effects.
- **Only one region/AZ/tenant/version:** prioritize local configuration, rollout, routing, node, data partition, or tenant-specific load; verify whether dependencies are shared.
- **Pods restarting or not ready:** inspect event chronology, OOM, probe behavior, image/config change, node pressure, startup duration, and dependency readiness assumptions.
- **Pods restarting while the replica count stays flat:** inspect the autoscaler's signal source, its behaviour on missing data, and per-pod headroom against the scaling threshold.
- **Queue backlog:** compare producer vs consumer throughput, oldest message age, partition skew, poison messages, retries, DLQ, consumer scaling, and downstream limits.
- **Database degradation:** distinguish database engine saturation from client-side pool wait, query plan change, lock contention, storage/IO limits, and network latency.
- **Intermittent failures:** segment by instance, route, tenant, AZ, connection reuse, retries, time, and request characteristics; avoid relying only on averages.
- **Alert with no apparent user impact:** validate SLI semantics, alert thresholds, sampling/aggregation, synthetic probes, internal-only paths, and telemetry integrity.

## Cross-domain interactions to test

A single incident can be a chain. Examples include:

- Dependency latency -> client timeouts -> retries -> connection/thread pool exhaustion -> elevated 5xx.
- Cache miss spike -> database load -> query latency -> request queueing -> autoscaler lag.
- Slow startup/readiness -> rollout removes healthy capacity -> remaining replicas saturate -> cascading failures.
- DNS/TLS issue -> connection failures -> retry storm -> egress/NAT port exhaustion.
- Queue consumer failure -> backlog growth -> replay burst -> database saturation.
- Crash loop -> self-reported scaling metric drops to zero -> no scale-out -> load concentrates on surviving pods.

Treat these as candidate mechanisms. Prove each link with time-aligned evidence.
