# Canvas Composer: Board Format

> **Warning: captured copy, may be stale.** Verbatim excerpt of the Miro
> Canvas Composer skill returned by `canvas_get_canvas_composer_skill`,
> captured 2026-10-24. The live tool output is authoritative: call it
> before the first canvas call in a session, and when its text differs
> from this file, follow the tool and warn the user which rule changed.

The following is a specification on how to interact with a Miro board using a bespoke DSL and board-editing protocol.
The DSL is a subset of the SVG format, but with some additional constraints and features. Each svg component maps to a widget in the miro board.

## 1. The SVG board format

The payload is a single <svg> root element; each element directly inside it is one complete top-level module: a frame `<g data-frame>`, a container widget that owns its children by design (see its widget entry), or a loose widget. Wrap every module in that one <svg>...</svg> root, even when there is only one.

Widget forms and positioning:
+ Basic widgets use native SVG positioning: `<rect>`, `<image>`, and `<textArea>` x/y are top-left; `<circle>` and `<ellipse>` cx/cy are their center; `<polygon>` uses points; `<text>` x is its anchor and y its baseline; `<line>` uses two endpoints; a frame's translate is its top-left origin.
+ Custom widgets use a `<rect data-type="custom-widget" data-widget-type="NAME">` placeholder and must not be drawn manually. Their x/y are top-left; width/height are optional. Use the natural size below and do not stretch it.
+ Structured widgets use a `<foreignObject>` with the widget's `data-type`. Their x/y are top-left; an untyped `<foreignObject>` is rejected.


### 3. VALID WIDGET ATTRIBUTES

Available font families are: Abril Fatface, Arial, Bangers, Caveat, EB Garamond, Formular, Fredoka One, Georgia, Graduate, Gravitas One, Lemon Tuesday, Nixie One, Noto Sans, Open Sans, Permanent Marker, Plex Mono, Plex Sans, Plex Serif, PT Sans, PT Sans Narrow, PT Serif, Rammetto One, Roboto, Roboto Condensed, Roboto Mono, Roboto Slab, Spoof, Tiempos Text, Times New Roman, Titan One.

ROTATION: shapes, text, cards, and custom widgets accept data-rotation="degrees" (e.g. data-rotation="15"; negative values allowed; applied around the widget center). An element's own transform="rotate(deg)" is honored as a fallback when data-rotation is absent. Stickies accept the attribute but do not visually rotate. Frames, images, embeds, and connectors do not rotate. Omit the attribute for unrotated widgets - 0 is the default.

### 4. VERY IMPORTANT NOTES

- Elements outside frames use ABSOLUTE coordinates (relative to canvas origin 0,0).
- Inside a <g data-frame>, ALL coordinates are RELATIVE to the frame. The <g> uses transform="translate(x,y)" to position the frame on the canvas. Example: <g transform="translate(3000,2000)" data-frame="Title"><rect data-type="frame" x="0" y="0" width="1500" height="1000" fill="#fff" data-title="Title" /><rect data-type="sticky" x="50" y="50" width="100" height="100" data-color="yellow" /></g> - the sticky is at canvas position (3050, 2050).
- Use hex colors (e.g. fill="#1a1a1a") for all fill, stroke, and color attributes. Named CSS colors like "red" or "black" also work but hex is preferred.
- For a <text> element, y is the baseline (bottom of text): to gap a title and subtitle, the subtitle y must be at least title_y + title_font_size + desired_gap (e.g. title at y="100" font-size="40" -> a 20px-gap subtitle at y="160"). A <textArea>, by contrast, uses TOP-LEFT y and stacks by box: next_y = prev_y + prev_height + gap.
- Escape XML special characters in ALL attribute values and text content, or the whole SVG fails to parse and nothing is created. Specifically: & becomes &amp;, < becomes &lt;, > becomes &gt;. This applies to titles, labels, data-content, and standalone <text> alike - e.g. data-frame="Create &amp; Manage", data-content="A &lt; B". A raw & (as in "Create & Manage") is the most common cause of a failed request. Already-escaped entities like &amp; must not be double-escaped.
- Don't use linebreaks inside data-content attribute values. SVG elements themselves should be on separate lines for readability.
- References must be pasted as full URLs (https://...). Shorthand like "PR #123", "ref: JIRA-456", or bare ticket numbers does NOT turn into a link on the board - it stays dead text. A full http(s) URL in text/sticky/shape content becomes a real clickable link automatically. For a custom label instead of the raw URL, author the anchor explicitly with escaped markup, e.g. data-content="&lt;a href=&quot;https://...&quot;&gt;the design doc&lt;/a&gt;". Omit the reference entirely if you do not have the real URL. Same rules also apply to widget references. Any widget reference can and should be deep-linked by appending ?moveToWidget=<data-miro-id> to the board URL. Clicking on a link like that pans the user's viewport to that widget. Use these links ACTIVELY: whenever you build a table of contents, index, legend, or overview, or otherwise refer to another frame/section/widget, make the reference a real deep-link instead of dead text. A widget id is just an internal technical number, so showing it to the user is not good UX. Try to hide it under a label to avoid showing a raw id.
- DO NOT create weird freeform shapes, only use the ones that are available, creatively.
- Standalone text is for: a freestanding heading/label (<text>), a flowing paragraph or list block (<textArea>), or text freely positioned over a background shape. Never use standalone text to label a shape that should use data-content (centered text). Reach for <textArea> whenever the block is more than one line.
- Z-INDEX IS DETERMINED BY CREATION ORDER. Elements created first are behind, elements created last are in front. If a line connects shapes, create the line BEFORE the shapes so the shapes sit on top of it. This is critical for timelines, flowcharts, and any connected layouts.
- Don't create a superframe to wrap everything, everything gets directly placed on the infinite canvas. Container widgets whose entry says they hold children (decks, prototypes) are not superframes: they are top-level modules whose children live inside them by design.
on IDs:
+ There are TWO distinct id attributes. Do not confuse them.
+ `id` (the local SVG id, e.g. id="s1", id="box2", id="f1"): YOU author these, short and unique, so connectors can reference widgets via data-start/data-end. For frames, place the id on the <g> element: <g id="f1" transform="translate(x,y)" data-frame="Title">.
+ `data-miro-id` (the board identity of an already-created widget): the SERVER assigns these. NEVER author, invent, guess, or copy a data-miro-id. The only valid source is the result_svg returned by canvas_create_from_svg or canvas_update_from_svg (or canvas_read_as_svg). Reuse those values verbatim.
