# Diagram spec (`system-diagram/1`)

One JSON file drives every output: Mermaid files, Miro frames and the
ledger. Start from [../templates/example-spec.json](../templates/example-spec.json).
`build_diagram.py validate` reports every error with its JSON path.

## Top level

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `schema` | string | yes | `system-diagram/1` |
| `title` | string | yes | non-empty |
| `categories` | object | no | name to `[fill, stroke, text]` hex colours, merged over the palette |
| `overview` | object | yes | see Overview |
| `frames` | array | no | one entry per expanded overview block |

## Overview

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `title` | string | yes | becomes the Miro frame title and heading |
| `subtitle` | string | no | one sentence: what the diagram shows and how to read arrows |
| `legend` | array | no | `{category, label}`; category must exist |
| `zones` | array | yes | see Zone |
| `nodes` | array | yes | see Node |
| `edges` | array | no | see Edge |
| `notes` | array | no | `{title, lines[]}` panels under the zones |

### Zone

| Field | Type | Default | Rule |
|-------|------|---------|------|
| `id` | string | required | unique |
| `name` | string | required | repository, boundary or runtime name |
| `subtitle` | string | empty | location or role, for example `src/` |
| `lane` | integer | 0 | column index, 0 or greater; lanes render left to right |
| `columns` | integer | 2 | 1 to 4 node columns inside the zone |

Zones in the same lane stack in array order. Put callers in lower lanes and
callees, stores and external systems in higher lanes so most edges run left
to right. Use one column for narrow lanes such as external systems.

### Node

| Field | Type | Default | Rule |
|-------|------|---------|------|
| `id` | string | required | unique |
| `zone` | string | required | existing zone id |
| `title` | string | required | the component name |
| `body` | string | empty | concrete contents; keep title and body under about 100 characters |
| `category` | string | required | palette name |
| `shape` | string | `rect` | `rect`, `can` (database or file store) or `round` (queue, stream) |
| `evidence` | string | required | `observed`, `derived`, `inferred` or `unknown` |
| `sources` | array | required | paths with line numbers; may be empty only for `unknown` |
| `expands` | string | none | frame key; links the node to its detail frame |

### Edge

| Field | Type | Default | Rule |
|-------|------|---------|------|
| `from`, `to` | string | required | existing node ids; no self-edges |
| `relation` | string | required | from the vocabulary below |
| `label` | string | relation | short verb phrase or payload name |
| `evidence`, `sources` | | required | as for nodes; cite the calling or reading site |

## Frame

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `key` | string | yes | unique, `^[a-z0-9][a-z0-9-]*$` |
| `title` | string | yes | `<owner>: <block names>` |
| `subtitle` | string | yes | what the frame covers and what footers mean |
| `legend` | array | no | `{category, label}` |
| `areas` | array | yes unless `from_svg` | 2 to 6 areas |
| `from_svg` | string | no | path, relative to the spec, of an existing frame snapshot to reuse |

### Area and card

An area is `{name, cards[]}` with unique names per frame. Cards:

| Field | Type | Default | Rule |
|-------|------|---------|------|
| `category` | string | required | palette name; one meaning per category, explained in the legend |
| `title` | string | required | one concrete artefact: file, class, command, table |
| `body` | string | empty | 160 characters or fewer, naming functions, fields or counts |
| `foot` | string | empty | readers, consumers or callers |
| `span` | integer | 1 | 1 or 2; wide cards only when one column cannot hold the content |
| `evidence`, `sources` | | required | as for nodes |

Inferred and unknown cards get the label appended to their footer.

## Palette

`blue`, `green`, `grey`, `stone`, `purple`, `lilac`, `yellow`, `white`,
`orange`, `red`, `muted`. Zone tints rotate through six pale backgrounds.
Typical use: `white` for external systems, `stone` or `grey` for stores,
`red` for writers or destructive operations, `muted` for unused or
test-only items.

## Relation vocabulary

| Relation | Line | Use |
|----------|------|-----|
| `calls` | solid | function, API or command invocation |
| `runs` | solid | starts a process, job or stage |
| `loads` | solid | loads a module, plugin or rule set at start |
| `imports` | solid | static code dependency |
| `sends` | solid | publishes a message or event |
| `invokes` | solid | IPC or remote procedure call |
| `handles` | solid | handler registered for a channel or route |
| `exposes` | solid | publishes an interface to another boundary |
| `contains` | solid | packaging or containment |
| `observed_as` | solid | runtime instance of a static component |
| `reads` | dashed | reads a file, table or config |
| `writes` | dashed | writes or appends |
| `persists_to` | dashed | durable storage of state |
| `configures` | dashed | configuration that changes behaviour |

## Granularity

- Overview: 45 nodes or fewer.
- Each overview node with internals gets a frame.
- Frame: 2 to 6 areas, 3 to 12 cards per area.
- Lint warns when estimated text exceeds a card (about 6 lines of 46
  characters) or a node (about 4 lines of 34 characters).
