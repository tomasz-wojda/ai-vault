# Miro output

Built for the Miro MCP Canvas Composer tools (`canvas_create_from_svg`,
`canvas_update_from_svg`, `canvas_search`, `canvas_read_as_svg`). Call
`canvas_get_canvas_composer_skill` once before the first canvas call in a
session. An offline copy of the rules this skill uses is in
[board-format](canvas-composer/board-format.md),
[widgets](canvas-composer/widgets.md),
[create and update protocol](canvas-composer/create-update-protocol.md), and
[search and read](canvas-composer/search-read.md). When the live text
differs from the copy, follow the tool and warn the user.

## Document structure

- The generator emits frames, shapes (including `data-shape="can"`
  cylinders and `rx` rounding), `textArea` text and connectors; their DSL
  rules are in [board-format](canvas-composer/board-format.md) and
  [widgets](canvas-composer/widgets.md).
- Ids follow the rules in [board-format](canvas-composer/board-format.md):
  never author `data-miro-id`.

## Limits

- One call accepts at most 200,000 characters of SVG.
- Keep each batch at 90,000 characters or fewer so the saved result can be
  read back in one pass; `miro-details` splits batches automatically.
- Save every tool result to `results/<batch>.json`. The JSON carries
  `success`, `created_count`, `failed_items`, `message` and `result_svg`;
  frame ids are in `result_svg`.

## Two-pass publish

1. `build_diagram.py miro-details SPEC --out DIR` writes
   `DIR/miro/frames/<key>.svg`, `DIR/miro/batch-<n>.svg` and
   `DIR/miro/layout.json`. Detail frames sit right of the overview on a
   4-column grid.
2. Create each batch with `canvas_create_from_svg` on the target board and
   save each result JSON.
3. `build_diagram.py miro-ids --layout DIR/miro/layout.json --results
   RESULT.json… --out DIR/miro/frame_ids.json` maps frame keys to Miro ids
   and fails if any frame is missing.
4. `build_diagram.py miro-overview SPEC --out DIR --board-url URL
   --frame-ids DIR/miro/frame_ids.json` writes the overview frame at (0,0)
   with every `expands` node title and the Detail frames index linked to
   `URL?moveToWidget=<frame id>`, plus `DIR/miro/snapshot.svg` holding all
   frames.
5. Create the overview with `canvas_create_from_svg` and save its result.

## Expected messages

- "Measured dimensions differ" for `textArea` items: Miro auto-sizes text
  height and vertical position. Compare the rendered bounds only for
  overlaps with neighbouring items.
- A subtitle `textArea` renders 31 high for one line at font 22; the
  generator already uses 31.
- When a call reports changed dimensions, handle them as described in
  [create and update protocol](canvas-composer/create-update-protocol.md).

## Updating an existing board

- Read live geometry first with `canvas_read_as_svg` (selected
  `widget_ids`) or `canvas_search`, because users move frames; send partial
  documents as described in
  [create and update protocol](canvas-composer/create-update-protocol.md).
- To retitle a frame, resend its `<g>` with `data-miro-id`, the live
  `transform`, and the frame `rect` with the new `data-title`; children can
  be omitted.
- Deletions follow
  [create and update protocol](canvas-composer/create-update-protocol.md)
  and need explicit user confirmation of the specific items.
- No tool renames a board. Report the rename as a manual step (board name at
  the top left).

## Read-back verification

1. `canvas_search` with `result_mode: "overview"`: compare `total_items`,
   item counts by type, and frame titles with the generator output.
2. `canvas_search` with `result_mode: "matches"` for stale labels after a
   rename or relabel; expect zero results.
3. Confirm every `failed_items` list was empty and no connector references
   a missing endpoint (the generator guarantees this before sending).

Search modes and read limits are in
[search and read](canvas-composer/search-read.md).

## Versioning

Keep a local version directory beside the snapshots, for example
`tmp/miro/<BOARD>/`:

- `<version>.svg`: the combined snapshot (`snapshot.svg`).
- `<version>/`: spec, generated frames, batches, layout and saved results.
- `versions.json`: read and merge, never overwrite. One entry per version
  with `version`, `saved_at`, `board_name`, `board_url`, `frame_title`,
  `frame_miro_id`, `frame_url`, `detail_frames` (key to id), `snapshot`,
  `items` and `summary`.

Restoring a version means creating its snapshot SVG on a board; ids in the
snapshot are local and Miro assigns new ones.
