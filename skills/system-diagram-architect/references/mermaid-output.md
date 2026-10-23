# Mermaid output

`build_diagram.py mermaid SPEC --out DIR` writes `DIR/mermaid/overview.mmd`
and one `DIR/mermaid/<frame key>.mmd` per frame, then checks each file's
structure.

## Shape of the output

- Overview: `flowchart LR`, one `subgraph` per zone with `direction TB`,
  nodes inside their zone, then edges, class definitions and optional
  `click` links to Miro frames.
- Detail frame: `flowchart TB`, one `subgraph` per area with its cards as
  nodes and no edges; footers join the body after a middle dot.
- Node forms: `["…"]` box, `[("…")]` cylinder for `can`, `("…")` rounded
  for `round`.
- Edges: `-->` for call relations, `-.->` for data relations, label in
  `|…|`.
- Colours: one `classDef cat_<category>` per used category.
- Evidence: `ev_inferred` (dash 5 5) and `ev_unknown` (dash 2 4) classes
  outline uncertain nodes.

## Other diagram types

The script emits flowcharts only. Write these by hand from the ledger:

| Need | Diagram | Rule |
|------|---------|------|
| One request or job over time | `sequenceDiagram` | one participant per overview node involved; messages are observed edges in call order |
| Lifecycle of one entity | `stateDiagram-v2` | states and transitions cited to the code that sets them |
| Tables and keys | `erDiagram` | only columns read in migrations or schemas |

## Ids and escaping

- Ids are generated as `n_`, `z_` or `c_` plus the source id with every
  character outside `A-Z a-z 0-9 _` replaced by `_`.
- Never emit a bare reserved word as an id: `end`, `graph`, `subgraph`,
  `click`, `style`, `class`, `flowchart`. The prefixes prevent this.
- Labels escape `"` as `#quot;`, `<` as `#lt;`, `>` as `#gt;` and `|` as
  `#124;`; formatting uses `<b>`, `<i>` and `<br/>`.

## Size

Keep one file to about 60 nodes. Split larger views by frame instead of
shrinking text; the detail files already follow the Miro frame split.

## Validation

- Structural check (always): balanced `subgraph`/`end`, unique ids,
  declared edge endpoints, no reserved ids.
- `--check` additionally runs `mmdc -i file.mmd -o file.mmd.svg` when the
  Mermaid CLI is on `PATH`, and reports `mmdc not found; structural checks
  only` otherwise. Do not install it unasked.

## Mermaid and Miro

Miro's diagram widget lays Mermaid out in a single stacked column, losing
lanes and subgraph placement. Use the Miro output in
[miro-output.md](miro-output.md) for boards and keep Mermaid for Markdown,
pull requests and documentation sites.
