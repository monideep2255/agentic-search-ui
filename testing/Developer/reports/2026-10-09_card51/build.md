# Card 51 build: the About page stops describing a retired track

## Table of contents

- [Base](#base)
- [What changed](#what-changed)
- [Evidence for each sentence](#evidence-for-each-sentence)
- [Tests](#tests)
- [Mutation checks](#mutation-checks)
- [Facts checker](#facts-checker)
- [Test query](#test-query)
- [Deviations](#deviations)
- [Fix round](#fix-round)

## Base

Branch `fix/card51-about-page-truth`, cut from `origin/develop` at `d5dcc02c41a148f39c243ae2df4a03d5a53b94fd`. Dial position 1, a copy fix. No model call was made.

## What changed

- `frontend/src/components/screens/InfoScreens.tsx`, About, "Cite or refuse": the sentence about a track beside each answer now says each claim's marker carries its layer's colour and a claim with no source shows in muted ink with no marker after it.
- Same file, About stop 5: after the reworded-sentence sentence, a new sentence says a copied cut is judged the same way and a sentence with any piece held back is dropped whole.
- `testing/Test_queries_and_workflows.md`, query 102: one line added for the corrected sentence.

## Evidence for each sentence

| Sentence | Evidence |
|---|---|
| The track was retired | `AnswerScreen.tsx` header comment: "No provenance spine beside each sentence: the citation marker's layer colour carries the layer." Also the comment above `uncitedInk`: "what the retired spine segment carried ... muted ink with no marker after it." |
| Uncited claim in muted ink | `uncitedInk(claim)` in `AnswerScreen.tsx` applies `designTokens.inkMuted` when a claim has no citations and none pending |
| Copied cut is judged by a model | `core/graph.py` comment on the ground step: "asking a model about reworded sentences and copied cuts"; merged in pull request 204 (`5c1a9f8b`) |
| A held piece drops the whole sentence | Commit `aa5cea1c` "Drop the whole sentence when a copied piece is held back"; comment in `core/graph.py` near the "dropped whole" line |

## Tests

- `npx vitest run src/components/screens/AboutScreen.test.tsx`: Test Files 1 passed (1), Tests 12 passed (12).
- `npx tsc --noEmit -p .`: no output, clean.

## Mutation checks

No existing test reads these two sentences, and the card asks for a copy fix only, so no test was added and there is no red run to show. The old wording is gone from the tree (`grep "track beside"` finds nothing under `frontend/src`).

## Facts checker

Fact `loop.sentences_checked_by_code_alone` in `.claude/skills/verify/scripts/facts_registry.py` reads the sentence "One that passes but was reworded is then judged by a model, and kept only when the model finds it adds nothing beyond the record's own words." I left that sentence word for word and added the new content as a separate sentence, so the fact still passes. Run on this branch: `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`. Nothing under `.claude/` was edited. No fact reads the track sentence, so none needs updating; the registry work (diagnosis part 2) waits on the owner.

## Test query

Query 102 gained: About, "Cite or refuse" describes only what you can see on an answer, and does not mention a coloured track beside it.

## Deviations

- The stop 5 text is a second sentence, not a rewrite of the first, to keep the facts checker green without touching `.claude/`.
- Not changed, though the diagnosis lists them as unchecked: the other About, Architecture and Home claims. The diagnosis calls only the track sentence false, and it says "Layers 2 and 3 are stored nowhere" and the Home line "need a look", which is a judgment for the owner.

## Fix round

Base: 68e9d7d5. One round.

| Finding | Status | What changed |
|---|---|---|
| V-51-01 | Fixed | Stop 5 now says "if any copied part is held back the whole sentence is dropped". The code drops a sentence whole only for a held copied piece (`held_for_check`, grounding.py), and a held reworded clause is stripped alone, so the word "copied" is the scope |
| V-51-04 | Fixed | "A copied cut" became "A sentence that copies part of a record word for word", in the reader's words, which also stops "cut" clashing with stop 4's truncated results. The other words of the sentence match the code: copied pieces go to the same model check, and are held when it cannot run |
| V-51-02 | Fixed | "a claim with no source" became "a line of framing with no source", so it no longer contradicts "Every claim is tied to a specific record". The text in muted ink is framing kept by grounding without a marker |
| V-51-03 | Open | A marker spanning several layers is drawn in muted ink. It is a rare case, and naming it needs a clause the page does not otherwise carry; the sentence is true for the common single-layer case and no worse than develop, which said nothing about colour |

Query 102's line was updated to the new wording. Runs: `AboutScreen.test.tsx` 12 passed; `npx tsc --noEmit -p .` clean; facts checker `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`. No em dash, en dash, spaced hyphen or bold in any added line. No test reads these sentences, so there is no red run to show, as in the build.
