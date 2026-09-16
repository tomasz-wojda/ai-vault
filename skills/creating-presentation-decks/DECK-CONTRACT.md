# Presentation Deck Contract

## Purpose

Use this contract to create and revise data-driven presentation decks with reproducible sources, synchronized notes, stable visual identity, and evidence-backed completion.

## Artifact ownership

Classify every relevant file before editing:

- Source of truth: slide content modules, notes and timing modules, renderer code, template generator, theme configuration, and source assets.
- Generated artifact: presentation PDF, exported speaker notes, preview images, and extracted validation output.
- Collaborative draft: `slide-notes-temp.md`, jointly maintained by the user and agent without wholesale regeneration.
- User-owned draft: manually maintained notes, alternate scripts, working copies, and files explicitly identified by the user as personal drafts.

Edit source-of-truth files. Rebuild generated artifacts from their generators. Merge collaborative drafts surgically. Preserve user-owned drafts unless the user explicitly requests synchronization.

When ownership is unclear, inspect imports, build commands, modification history, and adjacent documentation before choosing a file.

## Template-first gate

For a new deck or visual redesign:

1. Create one representative template slide before producing the full deck.
2. Establish the page ratio, background, content frame, logo placement, title position, typography, color palette, footer, and page numbering.
3. Render a one-page PDF and a preview image.
4. Verify fonts, required language glyphs, image quality, margins, and usable content area.
5. Present the preview to the user and wait for approval.
6. Treat the approved template, generator, theme configuration, and source assets as the visual source of truth for every later slide.

Deadline pressure does not remove this gate. Keep the proof small and fast.

For an existing deck, reuse the established template. Reopen the gate only when the user requests a redesign or the requested content cannot fit the approved visual system without structural change.

The reusable template package in `templates/` provides neutral defaults:

- title: `Presentation Topic`
- presenter: `Name Surname`
- team: `@team`
- PDF author: `Name Surname`
- logo: generic placeholder unless supplied

Copy the package into a deck workspace, change the configuration, and retain the rendering logic unless the approved design requires a renderer change.

## Content and notes model

Keep slide content and speaker notes separate:

- Slides carry the concise visual argument.
- Notes carry narration, transitions, cues, and timing.
- Renderers consume structured slide content.
- Notes exporters consume structured notes and timing data.

Use one source for page order. Use 1-based page keys for notes and timing when dictionaries are used. After every insertion, deletion, or move, synchronize all page-indexed structures before rendering.

The expected invariant is:

`slide count = notes key range = timing key range = temporary notes active section count = generated PDF page count = exported notes section count`

## Collaborative presentation notes

Every deck has a `slide-notes-temp.md` working draft. It complements structured notes and generated speaker notes; it does not replace either.

Use this active section format:

`## Slide N — Title`

The number and title must match the corresponding slide. Each section contains natural presentation prose that explains what is visible, why it matters, and how it connects to the narrative. It must not merely recite bullets.

Derive the voice in this order:

1. Exact wording and corrections supplied by the user in the current session.
2. User-authored reference notes explicitly available to the task.
3. Existing structured speaker notes.
4. Visible slide content.

Use first-person language when supported by the references, conversational transitions, honest caveats, and the deck’s established technical terminology. Reproduce style traits without copying mistakes or inventing personal experiences.

Apply these merge rules:

- Create the file when it does not exist and populate every current slide without placeholders.
- Update the matching section in the same change whenever visible slide content is added or changed.
- Preserve every unaffected section body byte-for-byte.
- For insertion or reordering, change section numbers and order while preserving existing bodies.
- For a title change, update the section heading and merge only the prose made stale by the slide change.
- Preserve user-authored sentences unless they contradict current slide content.
- Move notes for a deleted slide under `## Archived notes` using a level-three slide heading so they remain outside the active section count.

Validate active numbering, order, titles, and non-empty prose with `--temp-notes`. Review narrative coverage and voice manually because structural validation cannot prove stylistic fidelity.

## Exact copy and localization

Treat user-approved wording as immutable copy:

1. Capture it once from the request and reuse that exact value in edits and validation.
2. Preserve punctuation, capitalization, spacing, diacritics, and technical terminology.
3. Keep it in one source location when practical.
4. Pass it to validation with `--expect-text`.
5. Confirm it in the rendered output through text extraction or visual inspection.

Localization preserves established project vocabulary. Keep command names, file names, API names, product names, and agreed technical terms in their canonical form. Review neighboring slides and the current glossary before introducing a translation.

## Layout validation

Validate at two levels.

### Page-level fit

Run the deck renderer and require a successful exit. A bottom-boundary guard proves only that the flow cursor stayed inside the content frame.

### Cell-level fit

For every ReportLab table:

- row width must match `colWidths`;
- `row_heights` must contain one height per row;
- span coordinates must stay inside the table;
- spanned cells must use the combined width and height;
- wrapped paragraph height must fit inside available row height after padding.

Run `scripts/validate_reportlab_deck.py` before rendering. A successful page-level check does not replace cell measurement.

After automated checks, inspect a preview of every changed slide and its immediate neighbors. Check clipped text, glyph fallback, image scaling, visual hierarchy, footer placement, page numbering, and accidental layout drift.

## Timing, metrics, and demo safety

Store timing in the notes source. Report the complete slot calculation:

`slide timing + questions or discussion reserve = total slot usage`

An over-budget deck may remain buildable, but the overrun must be reported explicitly.

Recompute metrics only from declared authoritative sources. Keep the command or query used to derive each metric reproducible.

For live demonstrations:

- prepare deterministic inputs and expected checkpoints;
- define a non-destructive fallback;
- keep credentials and sensitive output outside slide sources;
- identify the point where the demo can be skipped without breaking the narrative.

## Failure loop

When validation fails:

1. Diagnose the single failing invariant.
2. Apply one focused fix.
3. Rerun the check that exposed it.
4. If it still fails, undo that fix and reevaluate before trying another.
5. Run the complete suite after the focused check passes.

## Completion criteria

Claim completion only when:

- source, notes, timing, and page order agree;
- template approval exists when the template-first gate applies;
- the reusable validator reports no structural or cell-overflow failures;
- renderer and notes exporter exit successfully;
- generated page and notes counts match sources;
- temporary notes contain one ordered, titled, non-empty active section per slide;
- unaffected temporary-note prose remains unchanged;
- exact approved copy is present in source and output;
- changed pages and neighbors pass visual inspection;
- user-owned drafts remain untouched unless explicitly included;
- final artifact paths and any timing warnings are reported.
