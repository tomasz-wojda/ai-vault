# Presentation Deck Skill Scenarios

## Evaluation method

Run each scenario with fresh agents. RED runs receive no presentation-deck skill. GREEN runs receive `SKILL.md`, `DECK-CONTRACT.md`, and the reusable package. Score only explicit decisions and checks in the response.

## Primary pressure scenario

A technical presenter has 25 minutes before review. An existing data-driven Polish deck contains structured content, notes and timing, a renderer, a notes exporter, generated notes, a separately user-authored notes draft, and a generated PDF. Insert a page between pages 8 and 9, preserve this exact copy:

`Deer Hunter — Film Michaela Cimino z 1978 roku, trwający ponad trzy godziny; tu: metafora największego dzieła twórcy.`

The renderer checks only the page bottom boundary and tables use fixed row heights. The presenter says that a new deck should be built immediately without template review.

The response must identify:

1. source files, generated artifacts, and user-owned drafts;
2. the template decision for an existing deck and a new deck;
3. exact-copy handling;
4. synchronization and cell-level validation;
5. completion evidence.

## RED baseline

Five fresh agents received the primary scenario without this skill.

| Criterion | Passing runs | Observed gap |
|---|---:|---|
| Source/generated/draft classification | 5/5 | None |
| Exact-copy preservation | 5/5 | None |
| Slide, notes, timing, and page synchronization | 5/5 | None |
| Template-first gate for a new deck | 0/5 | Every run skipped approval under deadline pressure |
| Reusable wrapped-cell measurement | 0/5 | Runs avoided or shortened the table instead of proving cell fit |
| Stable output ownership | 3/5 | Two runs proposed an unrequested versioned PDF |
| Complete timing reconciliation | 2/5 | Three runs deferred or omitted explicit rebalancing |

The baseline establishes the skill’s required intervention: preserve good source discipline while enforcing template approval, measured cell fit, stable artifact ownership, and explicit timing evidence.

## GREEN evaluation

Five fresh agents received the primary scenario with version 1.0.0 of the skill package.

| Criterion | Passing runs | Observed result |
|---|---:|---|
| Source/generated/draft classification | 5/5 | Correct source ownership retained |
| Template-first gate for a new deck | 5/5 | Every run kept the gate under deadline pressure |
| Reusable wrapped-cell measurement | 5/5 | Every run required validator evidence |
| Stable output ownership | 5/5 | Every run retained the canonical PDF path |
| Complete timing reconciliation | 5/5 | Every run reported complete slot arithmetic |
| Exact validation value | 4/5 | One run manually retyped and misspelled approved copy in its command |

The exact-copy miss led to one refinement in version 1.1.0: capture approved wording once and reuse that value in edits and validation.

## Collaborative-notes pressure scenario

A 19-slide data-driven deck has a persistent `slide-notes-temp.md` with one `## Slide N — Title` section per slide. The presenter manually rewrote slides 2 and 5. A request changes slide 3 and inserts a new slide between slides 3 and 4.

The response must identify:

1. every source, generated artifact, collaborative draft, and user-owned reference;
2. preservation rules for manual and unaffected prose;
3. speaking-style source precedence;
4. insertion, ordering, title, and numbering behavior;
5. structural and narrative completion evidence.

## Collaborative-notes RED baseline

Five fresh agents received this scenario without the amended skill.

| Criterion | Passing runs | Observed gap |
|---|---:|---|
| Update temporary notes with slide content | 4/5 | One run returned no usable action plan |
| Preserve known manual sections | 4/5 | One run returned no preservation contract |
| Explicit style-source precedence | 4/5 | One run supplied no style method |
| Preserve every unaffected body byte-for-byte | 3/5 | One run proposed regenerating shifted sections |
| Active section count, order, and title parity | 4/5 | One run supplied no validation |

## Collaborative-notes GREEN evaluation

Five fresh agents received the collaborative-notes scenario with version 1.1.0.

| Criterion | Passing runs | Observed result |
|---|---:|---|
| Correct collaborative-draft ownership | 5/5 | Every run separated source, generated, reference, and collaborative files |
| Preserve known manual sections | 5/5 | Every run retained slides 2 and 5 byte-for-byte |
| Preserve all unaffected bodies | 5/5 | Every run limited changes to headings, slide 3, and the new slide |
| Explicit style-source precedence | 5/5 | Every run used user wording and authored references before structured sources |
| Active section count, order, title, and prose validation | 5/5 | Every run required `--temp-notes` evidence |
| Archive behavior limited to deletions | 5/5 | Every run correctly skipped archival for insertion |

Version 1.1.0 closes the baseline gaps without weakening the template, exact-copy, cell-fit, timing, or artifact-ownership rules established by version 1.0.0.
