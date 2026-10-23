# Canvas Composer: Widgets

> **Warning: captured copy, may be stale.** Verbatim excerpt of the Miro
> Canvas Composer skill returned by `canvas_get_canvas_composer_skill`,
> captured 2026-10-24. The live tool output is authoritative: call it
> before the first canvas call in a session, and when its text differs
> from this file, follow the tool and warn the user which rule changed.

Omitted from this copy: SLIDE_CONTAINER, STICKY_STACK, and every custom
widget (ACTION_BUTTON, ALIGNMENT_SCALE, APP_CARD, CARD, CODE, COMPANION_QR,
DOT_VOTING, DYNAMIC_POLL, EMBED, EMOJI, ESTIMATES, FLIP_CARD, LEADERBOARD,
PEOPLE, PEOPLE_STICKER, POLL, SPINNER, STAMP, USER_CARD). Read them from the
live tool when needed.

### 2. WIDGETS

#### BASIC WIDGETS

##### CONNECTOR
A relationship between two widgets that stays attached as they move.

- Every connector requires data-start and data-end references to local widget ids.
- x1 and y1 are the start point; x2 and y2 are the end point.
- Reference actual widgets, never frames or other connectors.
- For a line attached to no widget (separator, rule, border), use a divider instead.
- Connect each relationship directly; do not draw shared backbones or lines through widgets.
- Avoid crossing frame boundaries unless the user requests it.
- Connectors may loop or share endpoints.
- Give parallel connectors between the same widgets distinct labels.
- Keep stroke-width between 1 and 4 unless the design requires otherwise.
- Use data-arrow for arrowheads; do not draw arrowhead shapes.
- Pin data-start-side and data-end-side (top/right/bottom/left) so links do not cross other widgets; e.g. a left-to-right tree uses start right, end left. Omit for auto.
- Connectors linking labeled nodes into a diagram (mind map, org chart, concept map) mean you are hand-assembling a diagram: call canvas_load_format_skill(format_name="diagramming", notation="free_form") before create_from_svg for its palette, borders, shapes, and routing.

+ `data-start`: Local id of the start widget.
+ `data-end`: Local id of the end widget.
+ `stroke`: Line color.
+ `stroke-width` (1-24): Line thickness in pixels.
+ `data-arrow` (start|end|both): Arrowhead placement.
+ `stroke-dasharray`: Use 5,5 for dashed or 2,2 for dotted.
+ `data-shape` (straight|curved|elbowed): Routing style: prefer elbowed for tree and flow diagrams, straight for short direct links; use curved only for a deliberately organic look, never by default.
+ `data-start-side` (top|right|bottom|left): Side of the start widget to attach to (top/right/bottom/left); omit for auto.
+ `data-end-side` (top|right|bottom|left): Side of the end widget to attach to (top/right/bottom/left); omit for auto.
+ `data-content`: Short relationship label.

```xml
<line id="link" x1="300" y1="200" x2="500" y2="200" stroke="#1a1a1a" stroke-width="2" data-arrow="end" data-start="source" data-end="target" data-content="approved" />
```

##### DIVIDER
A free-standing straight line: a separator, rule, border, or axis attached to no widget.

- x1/y1 and x2/y2 are the two ends; horizontal and vertical lines are typical, any angle works.
- Place it inside a frame to separate sections of that frame.
- Use a connector instead when the line relates two widgets.

+ `stroke`: Line color.
+ `stroke-width` (at most 24): Line thickness in pixels.
+ `stroke-opacity`: Line opacity from 0 to 1.
+ `data-line-style` (solid|dashed|dotted|dash_dotted|dashed_dense|dashed_short|dashed_short_dense): Dash pattern; omit for solid.

```xml
<line data-type="divider" x1="100" y1="300" x2="700" y2="300" stroke="#b0b0b0" stroke-width="2" />
```

##### FRAME
A titled container that groups a board section and owns its child layout.

- Author a g with translate(x,y); every child coordinate is relative to that origin.
- The first child must be a rect with data-type=frame at x=0 and y=0.
- Put data-frame on the g and fill on the background rect.
- On an update, only a non-empty data-frame changes the title.
- Frames do not accept border strokes or border radius. The only styling parameter is the background color through `fill` parameter. For a transparent background use `fill=#ffffffff` (a thin border will exist).
- `width` and `height` are fully respected on the canvas.
- If a frame hosts a sticky dropping area, it should leave plenty of empty space. Ideally, several times the size of a single sticky.
- If a `frame-title` is given it sits right above top left corner of the frame. Do not include any other title or element in that region.

+ `data-frame`; alias: `data-title`: Frame title.
+ `fill`: Background color on the frame rect.

```xml

<g id="section" transform="translate(100,100)" data-frame="Research">
    <rect data-type="frame" x="0" y="0" width="1200" height="800" fill="#ffffff" data-title="Research" />
    ...
</g>

```

##### IMAGE
An image from a reachable URL or an existing board resource for photos, illustrations, and visual assets.

- Place a generated image by its numeric resource id: `href="resource://<resourceId>"`.
- The board preserves the source aspect ratio, so provided height may be adjusted.
- Images served from the local /images/ path are available during development.

+ `href`; alias: `xlink:href`: Public image URL or resource://<resourceId>.
+ `data-alt-text`: Read-only image description (alt text).

```xml
<image id="photo" data-type="image" href="https://example.com/photo.png" x="100" y="100" width="640" height="360" />

<image id="generated" data-type="image" href="resource://12345" x="800" y="100" width="1024" height="1024" />
```

##### SHAPE
A geometric object for labeled nodes, backgrounds, regions, and decoration.

- Author rect, circle, ellipse, or polygon; data-shape selects another supported shape.
- Use data-content for embedded labels (center/middle by default); data-text-align and data-text-align-vertical set either axis. Use standalone text for freely placed copy.
- To migrate a top-left layout label, add data-text-align="left" data-text-align-vertical="top" to the shape.
- The rx value is an exact, non-scaling pixel radius; use 12 for soft corners or 62 for a pill-like shape, and omit it for sharp corners.
- Keep both dimensions at least 8 pixels. Smaller dimensions grow to 8 around the same center; use a divider for a thin line.
- `data-content` accepts rich formatting via html tags: `<b>` `<i> <u>` `<em>` `<strong>` `<s>` `<sub>` `<sup>` `<br>`

When richer content is needed instead of a simple label a rect can act as a panel or card:
```xml
<-- A rect with multiline content -->
<rect x="835" y="262" width="400" height="150" rx="6" fill="#FFD9C7"/>
<circle cx="871" cy="298" r="18" fill="#F2704B"/>
<text x="871" y="304" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="700" fill="#FFFFFF">1</text>
<text x="901" y="304" font-family="sans-serif" font-size="16" font-weight="600" fill="#6B2F11">Weekly customer feedback call</text>
<text x="901" y="332" font-family="sans-serif" font-size="13" fill="#8A5033">why now: churn signals are unclear</text>
```

+ `data-content`: Embedded shape label; centered by default.
+ `data-shape` (can|circle|cloud|cross|flow_chart_predefined_process|hexagon|left_arrow|left_brace|left_right_arrow|octagon|parallelogram|pentagon|rectangle|rhombus|right_arrow|right_brace|round_rectangle|star|trapezoid|triangle|wedge_round_rectangle_callout): Explicit board shape; otherwise inferred from the SVG tag.
+ `rx`: Exact corner radius in pixels for rects.
+ `fill`: Shape fill color.
+ `data-text-color`: Label text color.
+ `data-font-family` (abril_fatface|arial|bangers|caveat|eb_garamond|formular|fredoka_one|georgia|graduate|gravitas_one|lemon_tuesday|nixie_one|noto_sans|open_sans|permanent_marker|plex_mono|plex_sans|plex_serif|pt_sans|pt_sans_narrow|pt_serif|rammetto_one|roboto|roboto_condensed|roboto_mono|roboto_slab|spoof|tiempos_text|times_new_roman|titan_one); alias: `font-family`: Label font family.
+ `data-font-size` (10-288): Label font size in pixels.
+ `data-font-weight` (normal|bold|bolder|400|600|700|800|900): Use bold for a bold label.
+ `data-text-align` (left|center|right): Horizontal label alignment; defaults to center on create.
+ `data-text-align-vertical` (top|middle|bottom): Vertical label alignment; defaults to middle on create.
+ `stroke`: Border color; use none for no visible border.
+ `stroke-dasharray`: Use 5,5 for a dashed or 2,2 for a dotted border; none resets to solid.
+ `stroke-width` (at most 24): Border thickness in pixels, greater than 1; 1 or less is rejected on write.

```xml
<!-- A rect with embedded content -->

<rect id="proj" x="0" y="0" width="300" height="100" rx="12" fill="#2D3142" stroke="none" data-content="THIS PROJECT" data-text-color="#FFFFFF" data-font-size="14" data-font-weight="bold" />


<!-- A rect as a placeholder -->

<rect x="100" width="100" height="150" rx="6" fill="#FCFBF6" stroke="#CFC9BA" stroke-width="2" stroke-dasharray="5,5"/>

```

##### STICKY
A lightweight note for spatial thinking, clustering, and short ideas.

- Use a 199x228 box for a square sticky or 350x228 for a wide sticky.
- For other sizes, keep square height near width x 1.15 or wide height near width x 0.65.
- A width-to-height ratio above about 1.16 selects wide; otherwise it selects square.
- The board fits and centers that fixed shape inside the authored box, so avoid flat or stretched boxes.
- Stickies accept data-rotation but do not visually rotate.
- Often, when a group of stickies exist, perfect alignment is not desirable. Instead rough positioning makes it look more realistic.
- When a region it's supposed to be used to drop stickies by the users, leave ample empty spaces to suggest dropping areas. If a sticky dropping area is intended, the container should be as big as several times the size of a sticky
- `data-content` accepts rich formatting via html tags: `<b>` `<i> <u>` `<em>` `<strong>` `<s>` `<sub>` `<sup>` `<br>`

+ `data-content`: Note text.
+ `data-color` (black|blue|cyan|dark_blue|dark_green|gray|green|light_blue|light_green|light_pink|light_yellow|orange|pink|red|violet|yellow): Named sticky color, not a hex value.
+ `data-tags`: Comma-separated tag titles. Read-only: authored changes are not applied.
+ `data-text-align` (left|center|right) (read-only; ignored on writes): Horizontal text alignment.
+ `data-text-align-vertical` (top|middle|bottom) (read-only; ignored on writes): Vertical text alignment.

```xml
<rect id="note" data-type="sticky" x="100" y="100" width="199" height="228" data-color="yellow" data-content="Customer insight" />
```

##### TEXT
Flowing paragraphs, headers, labels, and freely positioned copy.

- Use textArea for paragraphs and multiline text; width controls wrapping.
- A textArea's height is optional and grows with its content.
- Use text only for a short standalone heading or label; it does not wrap.
- Do not overlay text on a labeled shape or sticky; put the label in data-content.
- A textArea body supports `<b>`, `<i>`, `<u>`, `<s>`, `<strong>`, `<em>`, `<a href="...">`, and `<br/>`. Write them as literal markup inside the body; entity-escaped tags such as &lt;b&gt; render as visible text.
- Source whitespace collapses, so use `<br/>` for explicit line breaks and one textArea per logical block.
- A textArea uses top-left x and y. A text uses baseline y, with x at the start, middle, or end selected by text-anchor.
- Delete a text widget to remove it; an empty body on update preserves its content.

+ element body: Text content.
+ `fill`: Text color.
+ `font-family` (abril_fatface|arial|bangers|caveat|eb_garamond|formular|fredoka_one|georgia|graduate|gravitas_one|lemon_tuesday|nixie_one|noto_sans|open_sans|permanent_marker|plex_mono|plex_sans|plex_serif|pt_sans|pt_sans_narrow|pt_serif|rammetto_one|roboto|roboto_condensed|roboto_mono|roboto_slab|spoof|tiempos_text|times_new_roman|titan_one); alias: `data-font-family`: Font family.
+ `font-size` (1-1600): Font size in pixels.
+ `text-align` (left|center|right): Flowing text alignment.
+ `text-anchor` (start|middle|end): Horizontal anchor relative to x.
+ `font-weight` (normal|bold|bolder|400|600|700|800|900): Use bold for bold text.

```xml
<textArea id="summary" x="100" y="100" width="600" font-size="24"><b>Overview</b><br/>First point</textArea>
```

#### STRUCTURED WIDGETS

##### DIAGRAM
A structured diagram generated from Mermaid source.

- Prefer one diagram widget over hand-assembling a node-and-edge diagram from shapes and connectors.
- An empty diagram already on the board (no Mermaid source, nothing inside it) is a place to draw. When the user has selected one or is working inside one, draw into it, not beside it: with canvas_update_from_svg, author the foreignObject with that diagram's data-miro-id and omit width and height. A new diagram next to it would leave the empty one behind.
- Never author a Mermaid gantt or timeline here; a Gantt chart, timeline, schedule, or roadmap uses the native timeline widget unless the user asks for it "with mermaid".
- The foreignObject body is Mermaid text; the board resizes the widget to fit the rendered diagram, but read-back always states 1600x900.
- Before creating, editing, or moving a diagram, call canvas_load_format_skill(format_name="diagramming", notation=<what you draw>) for its syntax, sizing, colors, and a worked example.
- No Mermaid notation and no native widget fit (e.g. a mind map, concept map, freeform sketch)? You must hand-assemble from shapes and connectors -- but FIRST call canvas_load_format_skill(format_name="diagramming", notation="free_form"), THEN build it with create_from_svg following that guidance. Do not skip straight to create_from_svg.

+ natural size: 1600x900 at creation, before it resizes to its content
+ element body: Mermaid source; XML-escape special characters.
+ `data-title`: Diagram title.

```xml
<foreignObject id="flow" x="100" y="100" width="1600" height="900" data-type="diagram" data-title="Auth flow">
flowchart TD
    A[Client] --&gt; B[API]
</foreignObject>
```

##### DOC
A long-form markdown document for briefs, notes, specs, and meeting records.

- The foreignObject body is markdown text and may interleave nested widgets in document order: `<foreignObject data-type="table|kanban|timeline">`, top-level tags `<rect data-type="custom-widget" data-widget-type="code|card|embed">`, or opaque `<rect data-type="foreign" data-widget-type="…">` for slot embeds this dialect cannot inspect.
- Nested widgets use the same DSL as top-level ones; omit board x/y (slot placement owns position).
- Do not put a raw HTML `<table>` in the body; GFM pipe tables and markdown images are rejected. Nest a `data-type="table"` (or kanban/timeline) foreignObject for tables; place images on the board outside the doc.
- A fenced (```` ```python ````) or indented code block becomes a nested code widget; one inside a list item or quote is rejected. On update, code blocks fill this doc's code widgets that the body does not reference by `data-miro-id` (same content first, then edited blocks between their unchanged neighbours); extra ones add new widgets.
- Nested images and other unsupported types read back as opaque `data-type="foreign"` stubs — reorder or `data-deleted="true"` only; do not invent them or edit their body.
- The width is fixed at 784px times `data-scale` (default 1) and the height auto-sizes from at least 1105px times it; size docs to a layout with `data-scale`, not width/height. `data-scale` is set at creation only.
- Use standard Markdown, start with an H1, and keep markdown runs at column zero.
- Updating the body replaces markdown runs; nested embeds with `data-miro-id` update in place. To change part of the markdown, send `<edit>` children (each `<old>` within one markdown run) instead of the body.
- A nested `data-miro-id` must already belong to this doc — do not pull in a top-level board widget by id (re-parenting is not supported). Add a new nested code/card/embed/table by omitting `data-miro-id` (opaque foreign stubs cannot be created).
- To reposition a nested embed inside the doc, keep its `data-miro-id` and place that element where it should appear in the body; do not set board x/y.
- Nested embed PATCH: omit a nested element to keep it — omission keeps its place in the document (surrounding markdown and order). Delete only with `data-deleted="true"`. For nested tables, omit a row/column to keep it; delete only with `data-deleted="true"` on the th/tr.
- A body-less nested stub (type attrs + `data-miro-id`, optional `id`) keeps content and slot placement — do not invent x/y. Nested widgets omit board x/y on write and read back at the origin (slot placement owns position).
- Nested embeds are not measured; lay out around the parent doc's footprint, not the nested element.
- To move an existing doc without replacing content, send only `data-type`, `data-miro-id`, `x`, and `y`; omit the body.

+ element body: Markdown source when the doc has no nested widgets.
+ `data-scale`: Uniform size factor; 1 is the native 784px width.

```xml
<foreignObject id="brief" x="100" y="100" width="784" height="1105" data-type="doc">
# Project brief

- Goal one
- Goal two
</foreignObject>
```

##### TABLE
A structured dataset shown as a table, kanban board, timeline, or tree.

- One table with one th header row; every td row matches its column count. Header titles are unique and non-empty.
- Use kanban for status workflows and timeline for schedules, roadmaps, or Gantt charts; prefer this native timeline over a Mermaid timeline/gantt diagram unless the user asks for it "with mermaid".
- A read stamps `data-field-id` on each th and `data-record-id` on each tr. Its width and height are a measured footprint to lay out around, never a size to set.
- Before creating, editing, moving, or scaling a table, call canvas_load_format_skill(format_name="tables") for its column, cell, layout, and editing rules.
- To add a stamp column, send a th with `data-record-info` and no `data-field-id`: the board fills every row itself. One column per stamp kind.

+ `data-title`: Widget title.
+ `data-type` (table|kanban|timeline|tree|matrix): Board presentation mode.
+ `data-group-by`: Column to group records by, optionally with :asc or :desc; an empty value removes the grouping.
+ `data-scale`: Uniform size factor, 1 is natural size; omitted, it keeps the current one.
+ `data-lanes`: Kanban only: the single-value select column whose options are the lanes. Omitted on create, the Status column.
+ `data-window`: Timeline only: visible range as ISO start/end, e.g. 2026-01-01/2026-06-30. Omitted, it fits the rows' dates.
+ `data-date-unit` (day|week|month|quarter|year): Timeline only: time-axis granularity.
+ `data-nesting`: Table, timeline, or kanban: show records nested under their parents.
+ `data-dependencies`: Timeline or kanban: draw dependency links between records.
+ `data-direction` (top_to_bottom|left_to_right): Tree only: the direction the tree grows.
+ `data-view-id`: Update only: the saved view, from data-views, that the layout, title, view settings, grouping, and column order apply to.
+ `data-views`: Read-only, on a table with several saved views: each as id=name (layout). Ignored on write.
+ `data-integration`: External system this table syncs records from, read-only, e.g. jira. Rows carrying data-integration-id mirror an item in it.
+ TableColumn fields:
  + element body: Column title inside the th element.
  + `data-type` (text|number|date|select|link|person|formula): Cell value type; default is text.
  + `data-options`: Required select options as labels with optional :#hex colors.
  + `data-decimals`: Decimal places for number columns.
  + `data-format`: Display format for date columns.
  + `data-percentage`: Display a number or formula column's values as a percentage.
  + `data-currency`: Display a formula column's values as a currency, by ISO 4217 code such as USD.
  + `data-formula`: Expression of a formula column, required on it. Reference a column as field_ plus its data-field-id, with underscores for hyphens. Cells of a formula column are computed and cannot be written.
  + `data-multiple`: Allow multiple select, link, or person values where the layout permits it.
  + `data-field-id`: Board id of the column, echoed back from a read; identifies it on update.
  + `data-integration-field`: External field this column mirrors, read-only: its cells are owned by the sync and cannot be edited here.
  + `data-record-info`: The record stamp this column shows (created_at, created_by, last_edited_at, last_edited_by). The board fills its cells; delete with data-deleted; renaming or retyping is refused and its cells are ignored.
  + `data-read-only`: Backend-computed column (formula, rollup, relation, latest update); its cells cannot be edited. Set only by a read; an authored value is ignored.
  + `data-role` (title|description|status|tags|assignee|start_date|end_date|estimate): Semantic role the layouts bind to, on a plain table only; kanban and timeline take their roles from the fixed column names instead. Omitted, it preserves the column's live role; the reserved value "default" clears an existing role.

```xml
<foreignObject id="plan" x="100" y="100" width="640" height="400" data-type="table" data-title="Plan"><table><thead><tr><th>Task</th><th data-type="select" data-options="Todo:#cccccc, Done:#00b86b">Status</th></tr></thead><tbody><tr><td>Review</td><td>Todo</td></tr></tbody></table></foreignObject>
```
