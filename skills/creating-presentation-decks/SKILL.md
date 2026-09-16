---
name: creating-presentation-decks
version: 1.1.0
description: Use when creating, revising, localizing, rendering, or validating slide decks, presentation PDFs, speaker notes, live-demo talks, or ReportLab presentations.
---

# Creating Presentation Decks

Apply [DECK-CONTRACT.md](DECK-CONTRACT.md) throughout the task.

## Workflow

1. Classify each file as source of truth, generated artifact, or user-owned draft.
2. Establish audience, slot length, language, technical depth, narrative, demo role, and required deliverables from available context.
3. Choose the template branch.
4. Edit structured content, notes, timing, renderer, or configuration at their declared source.
5. Create or merge `slide-notes-temp.md` so every slide has matching spoken prose.
6. Synchronize every page-indexed structure after insertions, moves, or deletions.
7. Validate structure and table-cell fit before rendering.
8. Rebuild every affected generated artifact.
9. Inspect previews of changed pages and immediate neighbors.
10. Report artifact paths, validation evidence, timing, and unresolved warnings.

## Template branch

For a new deck or visual redesign, create one representative template slide first. Use the neutral package in `templates/` as a starting point. Render a one-page PDF and preview image, verify typography and boundaries, show the preview, and wait for user approval before building the full deck. Approval makes that generator and configuration the visual source of truth.

For an existing deck, reuse its approved template. Reopen template approval only for a requested redesign or an incompatible structural change.

## Source discipline

Slides contain concise visible content. Notes contain narration, transitions, cues, and timing. Modify source modules and regenerate PDFs or exported notes; preserve manually maintained drafts unless explicitly requested.

Treat `slide-notes-temp.md` as a persistent collaborative draft. Create one `## Slide N — Title` section per slide. Whenever visible content changes, update its section in the same change. Preserve unaffected prose byte-for-byte; renumber headings without rewriting bodies. Merge user edits instead of regenerating the file.

Derive voice in this order: exact wording and corrections from the current session, user-authored reference notes, structured notes, then visible slide content. Write natural first-person narration that explains what the audience sees and why it matters rather than reading bullets aloud. Copy cadence and terminology, not mistakes or unsupported personal claims.

Treat user-approved wording as immutable. Preserve punctuation, capitalization, spacing, diacritics, and agreed technical terms. Verify exact copy in source and rendered output.

## Validation

Use `scripts/validate_reportlab_deck.py` for:

- slide, notes, and timing key parity;
- timing totals and slot warnings;
- table shape and span coordinates;
- wrapped cell height against fixed or variable row heights;
- required exact text;
- `slide-notes-temp.md` section order, count, and title parity via `--temp-notes`.

Then run the native renderer and notes exporter. A page-level bottom-boundary check does not prove that text fits inside fixed-height table cells.

## Completion

Finish only when sources, temporary notes, generated page counts, exported notes, approved copy, timing, and visual previews agree. On failure, apply one focused fix, rerun the exposing check, and undo the fix before reevaluating if it fails.

Use [SCENARIOS.md](SCENARIOS.md) for evaluated pressure cases and expected behavior.
