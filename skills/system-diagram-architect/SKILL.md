---
name: system-diagram-architect
version: "1.1.0"
description: Use when analyzing a repository, application, service, pipeline, or other resource to explain how it works and presenting the result as Mermaid diagrams or Miro boards, including architecture overviews, expanded per-component views, and control and data flows. Builds an evidence-backed model (observed, derived, inferred, unknown) from source before drawing, then renders both formats from one JSON spec.
---

# System Diagram Architect

Map how a resource works, prove every element against its source, and render
the proven model as Mermaid and Miro diagrams from one spec.

## When to use

- Source repositories, multi-repository systems, configuration trees,
  pipelines and Jenkinsfiles, infrastructure definitions, and services
  described by their configuration.
- Requests such as "diagram how X works", "architecture of these repos",
  "expand this block", "show the data flow", "put it on Miro".

Skip this skill when the claim depends on shipped binaries or runtime-only
behaviour with no source. Use a reverse-engineering toolchain there and draw
only the evidence it returns.

## Outputs

- `spec.json`: the single source of truth (format in
  [references/diagram-spec.md](references/diagram-spec.md)).
- Mermaid: `mermaid/overview.mmd` plus one file per expanded block.
- Miro: one overview frame and one detail frame per expanded block, with
  overview blocks and an index panel deep-linked to their frames.
- `ledger.json`: every card, node and edge with evidence and sources.

## Workflow

Work through the phases in order. Each phase has an exit condition.

1. **Frame.** Fix the audience, the resource boundary, the output format,
   and the question checklist: components, entry points, control flow,
   data stores with their writers and readers, external systems, trust and
   authority boundaries, lifecycle and scheduling, coupling contracts.
   Exit: the checklist exists with the evidence each question needs.
2. **Inventory summary-first.** Read manifests, build files, entry points,
   the directory map, configuration, contracts and schemas, and test
   layout. Exit: every top-level unit has an owner path.
3. **Decompose.** Split independent subsystems across parallel explore
   workers. Each returns sources, tagged conclusions and gaps. Worker
   claims stay unverified until their cited lines are re-read.
4. **Trace.** Follow each question from its entry point through data and
   state changes to its result. Record each relationship with a relation,
   an evidence label and the calling or reading site.
5. **Ledger.** For each conclusion keep evidence label, sources, search
   boundary and remaining unknowns.
6. **Model.** Write the spec. The overview holds zones, nodes, edges and
   notes. Every overview node with internals gets a detail frame of 2 to 6
   areas whose cards name concrete artefacts and their readers.
7. **Verify.** Re-read the source for every count, name, ordering, weight
   and version on every card. Downgrade anything not re-read to inferred.
   Record what was not examined. Run `validate --strict`.
8. **Render.** Generate Mermaid and Miro outputs with the commands below.
9. **Publish and report.** Publish Miro in two passes, verify by reading
   the board back, write snapshots and the version index. Mark each
   checklist question answered, partially answered or unresolved, and list
   unknowns and limitations.

Method detail, coverage terms and the verification pass:
[references/analysis-method.md](references/analysis-method.md).

## Granularity

- Overview: 45 nodes or fewer, one zone per repository, runtime or data
  boundary.
- Detail frame: 2 to 6 areas, 3 to 12 cards per area.
- Card title: one concrete artefact (file, class, command, table, rule).
- Card body: 160 characters or fewer naming functions, fields, counts,
  orders or thresholds.
- Card footer: the readers, consumers or callers of that artefact.
- Wide cards only when one column cannot hold the content.
- One category per visual meaning, every category in the legend.

## Evidence rules

- observed: read in source at a cited location.
- derived: computed from observed facts, such as a count.
- inferred: naming, pattern or convention without a confirming read.
- unknown: required by a question but not established.
- Missing coverage is unknown, never absence. An item not drawn is not
  proved absent from the resource.
- Ambiguous or dynamic relationships stay as notes, not edges.
- Never present an inference as an observation; the renderers mark
  inferred and unknown items visibly.

## Edge vocabulary

`calls`, `runs`, `loads`, `imports`, `sends`, `invokes`, `handles`,
`exposes`, `contains`, `observed_as` draw solid. `reads`, `writes`,
`persists_to`, `configures` draw dashed. Every edge cites its calling or
reading site. Meanings: [references/diagram-spec.md](references/diagram-spec.md).

## Safety

- Analysis is read-only. Do not run the target or change its files.
- Reference credential files by path; never open them for their values.
- Miro deletions require explicit user confirmation of the specific items.
- No tool renames a Miro board; report a rename as a manual step.
- Never send a Canvas Composer document over 200,000 characters.

## Commands

Run from `scripts/` or call `scripts/build_diagram.py` by path. Python 3
standard library only.

| Command | Result |
|---------|--------|
| `build_diagram.py validate SPEC [--strict]` | counts, evidence totals, errors with JSON paths, text-fit warnings |
| `build_diagram.py mermaid SPEC --out DIR [--board-url URL --frame-ids FILE] [--check]` | `DIR/mermaid/*.mmd`, structural check, optional `mmdc` render |
| `build_diagram.py miro-details SPEC --out DIR` | `DIR/miro/frames/<key>.svg`, `batch-<n>.svg`, `layout.json` |
| `build_diagram.py miro-ids --layout FILE --results FILE... --out FILE` | frame key to Miro id map from saved create results |
| `build_diagram.py miro-overview SPEC --out DIR --board-url URL --frame-ids FILE` | linked overview frame and combined `snapshot.svg` |
| `build_diagram.py ledger SPEC --out DIR` | `DIR/ledger.json` |

Start a new spec from [templates/example-spec.json](templates/example-spec.json).
Run the tests with `python3 -m unittest discover -s tests -p 'test_*.py'`
from the skill directory.

## References

- [references/analysis-method.md](references/analysis-method.md): question
  checklist, inventory sources, tracing, evidence labels, coverage, ledger,
  verification pass, closing checklist.
- [references/diagram-spec.md](references/diagram-spec.md): every spec field,
  palette, relation vocabulary, granularity limits.
- [references/mermaid-output.md](references/mermaid-output.md): generated
  flowcharts, hand-written sequence, state and ER diagrams, ids, escaping,
  validation.
- [references/miro-output.md](references/miro-output.md): Canvas Composer
  structure and limits, two-pass publish, updates, read-back verification,
  versioning.
- [board format](references/canvas-composer/board-format.md),
  [widgets](references/canvas-composer/widgets.md),
  [create and update protocol](references/canvas-composer/create-update-protocol.md),
  [search and read](references/canvas-composer/search-read.md): verbatim
  Canvas Composer rules captured 2026-10-24: board format, diagram widgets,
  create and update protocol, search and rendered bounds; the live tool wins
  on any difference.
