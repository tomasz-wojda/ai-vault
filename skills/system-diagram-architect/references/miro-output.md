# Miro output

Built for the Miro MCP Canvas Composer tools (`canvas_create_from_svg`,
`canvas_update_from_svg`, `canvas_search`, `canvas_read_as_svg`). Read the
Canvas Composer skill tool once before the first canvas call in a session.

## Document structure

- Frame: `<g id transform="translate(x,y)" data-frame="Title">` whose first
  child is `<rect data-type="frame" … data-title="Title" />`.
- Shapes: `rect` with `data-content` holding escaped HTML (`<b>`, `<i>`,
  `<br />`, `<a href>`), `data-shape="can"` for cylinders, `rx` for rounded.
- Text: `textArea` with plain text.
- Connectors: `line` with `data-start`, `data-end`, `data-start-side`,
  `data-end-side`, `data-shape` (`straight` or `elbowed`), `data-arrow`,
  optional `stroke-dasharray` and `data-content` label.
- Never send `data-miro-id` on create; Miro assigns it.

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

## Updating an existing board

- Send a partial document with `canvas_update_from_svg`; elements are
  matched on `data-miro-id`. Read live geometry first with
  `canvas_read_as_svg` (selected `widget_ids`) or `canvas_search`, because
  users move frames.
- To retitle a frame, resend its `<g>` with `data-miro-id`, the live
  `transform`, and the frame `rect` with the new `data-title`; children can
  be omitted.
- Omitting an element never deletes it. Deletion needs
  `data-deleted="true"` and explicit user confirmation of the specific items.
- No tool renames a board. Report the rename as a manual step (board name at
  the top left).

## Read-back verification

1. `canvas_search` with `result_mode: "overview"`: compare `total_items`,
   item counts by type, and frame titles with the generator output.
2. `canvas_search` with `result_mode: "matches"` for stale labels after a
   rename or relabel; expect zero results.
3. Confirm every `failed_items` list was empty and no connector references
   a missing endpoint (the generator guarantees this before sending).

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
