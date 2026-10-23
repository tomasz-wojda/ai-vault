# Analysis method

Adapted from the investigation discipline of evidence-first reverse-engineering
tools: every element on a diagram is a claim, and every claim carries its
evidence, its source and the boundary of the search that produced it.

## 1. Question checklist

Write the checklist before reading code. Each question names the evidence
that would answer it.

| Category | Question | Evidence that answers it |
|----------|----------|--------------------------|
| Components | What are the deployable or runnable units? | Build files, manifests, entry points, Dockerfiles |
| Entry points | Where does work start: CLI, HTTP, schedule, hook, event? | `main` functions, route tables, cron and pipeline triggers |
| Control flow | Which unit calls which, and in what order? | Call sites, dispatchers, stage lists |
| Data stores | What persists state, and who writes and reads it? | Schemas, migrations, file paths, connection settings |
| External systems | What leaves the boundary? | Clients, URLs, SDK imports, credentials referenced by path |
| Boundaries | Where do trust, authority or runtime change? | Process launches, network hops, permission checks |
| Lifecycle | What runs when, and what runs in the background? | Schedulers, hooks, watchers, retries |
| Contracts | Which schemas, configs or rule files couple components? | JSON/YAML schemas, shared config, generated code |

Resolve scope and identity from the conversation and workspace first. Ask
only when the boundary of the resource is genuinely ambiguous.

## 2. Inventory, summary first

Start with the smallest view that names every top-level unit, then expand
only where a checklist question needs it.

| Resource | First reads |
|----------|-------------|
| Repository | README, top-level tree, package or build manifests, entry points, `config/`, `schemas/`, tests directory names |
| Pipeline or Jenkinsfile | Stage list, shared libraries, parameters, credentials references, agents |
| Kubernetes, Helm, Terraform | Workload kinds, values files, module graph, outputs, providers |
| Service configuration | Listeners, upstreams, storage, scheduled jobs |
| Multi-repo system | One inventory per repository, then the files that cross repositories |

Exit when every top-level unit has an owner path. Units without an owner
path are recorded as unknown, not dropped.

## 3. Decompose

Split independent subsystems across parallel explore workers when available.
Give each worker one scope, the existing findings, and this return format:

- sources read (paths with line ranges)
- conclusions, each tagged observed, derived or inferred
- gaps and unread areas

Worker output is a lead, not evidence. Re-read the cited lines before a
worker claim reaches a card.

## 4. Trace

Follow each question from its entry point through data and state changes to
its result. Record every relationship as an edge with:

- relation from the fixed vocabulary in [diagram-spec.md](diagram-spec.md)
- the calling or reading site as its source
- an evidence label

Batch related reads around one hypothesis. Expand only when the returned
evidence leaves a concrete gap. Keep ambiguous or dynamic relationships
(string-built names, reflection, runtime registration) as notes instead of
edges.

## 5. Evidence labels

| Label | Meaning | Example |
|-------|---------|---------|
| observed | Read directly in source at a cited location | `sweep` runs four stages, read in the stage list |
| derived | Computed from observed facts | 23 rule files, counted from the directory listing |
| inferred | Pattern, naming or convention without a confirming read | a `rateLimiter` middleware is assumed per-IP |
| unknown | Required by a question but not established | no dead-letter queue declaration found |

Authority and certainty are separate: a file you read can still only support
an inference. Unknown is never rendered as absence.

## 6. Coverage

Keep four counts distinct for every inventory:

- discovered: items found by listing or search
- applicable: items relevant to the question
- examined: items actually read
- returned: items placed on the diagram

A complete page of a filtered selection does not make the parent inventory
complete. An item missing from the diagram is not proved absent from the
resource. State the search boundary in the report.

## 7. Finding ledger

`build_diagram.py ledger` writes one entry per card, node and edge. During
analysis keep the same fields for each conclusion:

- conclusion
- evidence label
- sources
- search boundary (paths and patterns examined)
- remaining unknowns

## 8. Verification pass

Before rendering:

1. Re-read the source for every count, ordering, weight, threshold, version
   and name on every card.
2. Downgrade any claim whose source was not re-read to inferred.
3. Confirm each edge at its calling or reading site.
4. Remove cards that restate another card.
5. Record what was not examined.

## 9. Closing checklist

Revisit the question checklist and mark each question:

- answered: every required claim is observed or derived
- partially answered: some required claims are inferred or unknown
- unresolved: no qualifying evidence

Do not describe the analysis as complete while required questions remain
partially answered or unresolved.
