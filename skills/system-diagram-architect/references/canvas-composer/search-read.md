# Canvas Composer: Search, Read and Rendered Bounds

> **Warning: captured copy, may be stale.** Verbatim excerpt of the Miro
> Canvas Composer skill returned by `canvas_get_canvas_composer_skill`,
> captured 2026-10-24. The live tool output is authoritative: call it
> before the first canvas call in a session, and when its text differs
> from this file, follow the tool and warn the user which rule changed.

## 6. HOW TO SEARCH, READ, AND NAVIGATE A BOARD

+ canvas_search is your entry point to anything you want to find in the canvas, it allows you to traverse the board and narrow down your scope. Full board reads are disabled to avoid overwhelming the context window.
+ If you are completely new to the board, and the user hasn't given you any context for what to search, you may call canvas_search with result_mode="overview" to get a rough high-level index of what's in the board, if you are asked for a rough summary this is usually enough, unless you or the user want to get a more granular view.
+ For a summary or a request with no search clue, call canvas_search once with result_mode="overview" and no patterns. Never use a match-all regex to discover the board.
+ Use result_mode="areas" for remembered sections, sessions, layouts, or concepts. Use result_mode="matches" for exact items, occurrences, IDs, attributes, or captures.
+ Start with one areas call that batches a few independent clues. Plain patterns search decoded text literally and case-insensitively. Prefix only structural SVG regexes with re:.
+ Use target_id only to inspect one candidate and cursor only when a useful result page is incomplete. Do not enumerate the board.
+ STOP when one result clearly satisfies the request, don't go rogue trying to read everything; then call canvas_read_as_svg. Pass scope.x, scope.y, scope.width, and scope.height as scope_x, scope_y, scope_width, and scope_height. Use widget_ids only for a narrowly targeted read.
+ NEVER try brute force through a full board read by calling canvas_read_as_svg multiple times, always use canvas_search to narrow the scope and only do a bbox read once you have gained enough confidence through the search, if the bbox read doesn't validate what you were looking for, go back to the search instead of attempting more uninformed bbox reads.
+ If the user asks for a general summary, just use the overview, don't go rogue trying to read everything.  Interpret it for the user don't just forward the raw results. Only drill down if the user asks for more detail.
+ If there is information you already have in context, just reuse it, don't re-read unnecessarily.


## RENDERED BOUNDS (READ-ONLY)

+ `data-rendered-bounds="x y width height"` is the box the board ACTUALLY paints for that widget, measured on the canvas. Server-assigned and READ-ONLY - never author it, editing it has no effect. To move or resize a widget, change its own x/y/width/height.
+ WHERE THEY APPEAR: canvas_read_as_svg carries them for every measured widget in the region you read; a create or update result_svg carries them for every widget THAT call addressed, created or edited, whose painted box differs from its own x/y/width/height. A widget the call never mentioned is not re-measured, so to learn what untouched content occupies, read the region.
+ The numbers are ABSOLUTE board coordinates, always - including for elements nested in a frame, whose own x/y are relative to that frame's translate. Add the frame's translate before comparing the two.
+ These bounds OVERRIDE the authored box: authored width/height is what was requested, the bounds are what exists. When you place a widget next to existing content, check it against the most recent bounds you hold for that content rather than the authored numbers, and keep the spacing this skill already specifies (20-40px within a cluster, 100px or more between clusters).
+ Docs, decks and prototyping containers carry bounds but their contents do not - a doc's nested embeds (table/kanban/timeline, code, card, embed, and opaque foreign stubs), a deck's slides, a prototype's screens and anything sitting inside them hold container-relative coordinates, so lay out around the container's box, never around a child's. A FRAME is the opposite: the frame itself carries no bounds, its children carry absolute ones.
+ `data-rendered-bounds="unmeasured"` means the board could NOT measure that widget - never that it is small, empty or absent. Its footprint is UNKNOWN, not zero, whatever its own width/height say (a deck's `<g>` states no size, some elements state 0x0): treat that area as occupied, keep 100px or more clear of it, or call canvas_read_as_svg scoped to that region to see what is actually there before placing.
+ On an element a call did measure, NO attribute means the widget needs no measurement - its own width/height is its real box, so use those.
