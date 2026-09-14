# Answer layout, 2026-09-14

The product owner's approved answer layout (`design/Main.dc.html`, `Researcher.dc.html`, `Mobile.dc.html`, `Streaming.dc.html`) built into the web app, plus the clean-copy fix, the no-inline-records fix, and the writing state adapted to the streaming measurement. Frontend files only; nothing committed.

## Table of contents

- [What changed](#what-changed)
- [Streaming and writing state](#streaming-and-writing-state)
- [Clean copy](#clean-copy)
- [Records never inline](#records-never-inline)
- [Design mapping and tokens](#design-mapping-and-tokens)
- [Deviations from the mockups](#deviations-from-the-mockups)
- [Requirement changes to existing tests](#requirement-changes-to-existing-tests)
- [Verification](#verification)
- [Screenshot comparison](#screenshot-comparison)
- [Proposed hand tests 1, 7 and 12](#proposed-hand-tests-1-7-and-12)
- [Proposed DECISIONS.md rows](#proposed-decisionsmd-rows)
- [Findings during the work](#findings-during-the-work)

## What changed

| File | Change |
|------|--------|
| `frontend/src/components/screens/AnswerScreen.tsx` | Spine retired; `buildAnswerBlocks` groups claims into prose, headings, notes and record blocks; `.rtab` tables, stacked rows below 720px; Notes list; medical line; Sources rule; card padding |
| `frontend/src/components/answer/CitationMarkers.tsx` | Marker name moved to `aria-label`; record link name to `aria-label`; spoken statements get `user-select: none` |
| `frontend/src/components/screens/RunProgress.tsx` | `WritingBanner`; during Write it replaces the caption, handoff lines, tool chips and reasoning log |
| `frontend/src/components/screens/RunScreen.tsx` | Mockup card padding and 16px phone gutter |
| `frontend/src/hooks/useRunView.ts` | Write begins when Act closes or the plan selects no tool; `resultCount` on chips; `findingsTail` on claims; any table header width |
| `frontend/src/hooks/useAnswerReveal.ts` (new) | One-by-one reveal with a minimum banner time |
| `frontend/src/hooks/useAgentRun.ts` | Skips `step` and `stage` frames by name |
| `frontend/src/App.tsx` | Routes the view through `useAnswerReveal` |
| Tests (new) | `answerLayout.test.tsx`, `hooks/useAnswerReveal.test.ts`, `hooks/useRunView.writeState.test.tsx`, `hooks/useAgentRun.forwardCompat.test.ts`, `e2e/answer-layout.spec.ts` |

## Streaming and writing state

Adapted to the coordinator's measurement (6 live runs, 28 frames at 250ms: all tokens arrive within 1 to 217ms after a 1.9 to 22.6 second silent gap, because Write uses `sink.emit`).

- Write is entered when Act is complete, not on the first token. `useRunView` treats Act as complete when every opened call (from `tool_start`, plus the plan's `tool_calls` once any of them has reached the wire) has a `tool_result` and at least one result arrived.
- No-tool refusal path: a `plan` with an empty `tool_calls` and no started tool enters Write.
- A later `tool_start` reopens Act. A guardrail refusal lands with no live step. Stop shows no banner.
- The banner (`WritingBanner`) and a filled stepper up to WRITE show through the whole silent gap. Unit arm: "shows the writing banner in the gap between the last tool_result and the first token" (`useRunView.writeState.test.tsx`).
- `events.ts` has no step or stage event type. `consumeEventStream` now skips a `step` or `stage` frame by name, so a future live Write progress frame cannot end the run; a `cost` frame is still rejected (`useAgentRun.forwardCompat.test.ts`).
- Reveal (`useAnswerReveal`): the first sentence waits until the Write state has been seen for 1500ms; then one sentence per 110ms while live, or 40ms per sentence once `done` has arrived. Until the last sentence shows, the view reports `landed: false` and `activeStep: "Write"`, so the screen stays in the writing state rather than landing half an answer. When complete it returns the input view object unchanged, so nothing is dropped.
- With today's backend `done` arrives in the same burst, so the observed pace is 40ms per sentence (33 sentences take about 1.3s). The 110ms pace applies once Write streams live.
- Stop freezes the reveal and clears its timer (unit arm "freezes cleanly when Stop latches mid-reveal"). Stop is disabled once `done` has arrived, as before (`deriveStopEnabled`), so after `done` the reveal simply completes.
- A failed stream (`useAgentRun` status `error`) flushes: every sentence that arrived shows at once (`flush` option, unit arm "shows everything at once when the stream failed"). Found by the e2e suite, see Findings.
- Rise animation: `.45s ease-out`, 4px, on each newly revealed sentence, heading, note and row while streaming; none under `prefers-reduced-motion`. The "writing..." line sits at the end until the run lands or stops.
- The durable backend fix (Write emitting live) is not depended on.

## Clean copy

- The marker button's accessible name ("Source 1, layer 2", "Sources 1 to 4: ...") is now its `aria-label`; the visible digits stay `aria-hidden`. The name is unchanged, and the text node that polluted copies is gone.
- The card's record link keeps "Open the record for source N, opens in a new tab" as `aria-label`.
- A word joiner (U+2060) sits ahead of the first marker, `aria-hidden` and `user-select: none`, because a button is an atomic inline and a lone marker could otherwise wrap onto its own line at 390px.
- "This sentence has no source." and "N sources pending." have no control to label, so they stay visually hidden text with `user-select: none`, which keeps them out of a selection.
- Proof: `answerLayout.test.tsx` asserts the claims container text has no "Source N, layer" while four named buttons exist; `e2e/answer-layout.spec.ts` checks a real selection, the clipboard after Ctrl or Cmd+C, and `innerText`.

## Records never inline

Record-shaped claims become a record block under a heading, never prose:

- consecutive `table_row` claims: one table with their header (any width) and a narrow unlabelled Sources column (`aria-label="Sources"`);
- consecutive `list_item` claims: one table;
- record lines after the findings-tail note, for typed and kind-less producers (`useRunView` sets `findingsTail` from the note until the next heading), grouped by label, with the label as the heading and the value as the row;
- two or more adjacent record lines in the same paragraph, even with no tail note. A lone record line stays prose.

Recognised prefixes, deterministic, case-insensitive: one of the entity types `Disease`, `Gene`, `Clinical trial`, `Literature entity`, `Sequence variant`, `SequenceVariant`, `Chemical entity`, `Protein`, followed by one of the fields `name`, `symbol`, `title`, `preferred name`, `preferred_name`, then `": "`. The row shows the claim text with only that prefix removed; its trailing full stop is kept.

A cell is set in mono (the `.g` rule) only when it looks like an identifier: a CURIE, a letter prefix with 6 or more digits (`C0346153`), `NCT` plus 8 digits, or `rs` plus digits. Gene symbols such as BRCA1 stay in the sans face, per `theme.ts`.

## Design mapping and tokens

| Element | Values | Source |
|---------|--------|--------|
| Prose paragraph | 16.5px, line height 1.68, 66ch, 18px below; 16px and 1.65 at 720px or narrower; no max width at 860px or narrower | prototype `.answer p` and its 860px rule; `.turn .answer p` for 16px |
| Section heading | 11.5px, .13em, uppercase, 700, `inkFaint`, 32px above and 14px below (28px and 10px on a phone), 7px and a 1px `line` rule | `.answer .ah` |
| Record table | 13.5px, 1px `line`, `surface`; cells 8px 11px with a `line` rule; header 10.5px .1em uppercase 700 `inkFaint` on `surfaceSunk` | `.rtab` |
| Identifier cell | mono 12.5px, nowrap, `inkMuted` | `.rtab td.g`, colour from the mockup |
| Stacked row | name 15px/1.45 `ink`; identifier mono 12.5px `inkMuted`; 10px padding, `line` rule | mockup `.row`, `.rn`, `.rm`; 15px is the prototype's `.fu-bar input` |
| Notes | heading `.ah`; list 14.5px/1.6 `inkMuted`, 20px indent, 6px gap; 14px and 18px on a phone | mockup `ul.notes`; prototype `.nolist li`, `.conflict` 14px |
| Medical line | 13.5px `inkMuted`, 22px above (13px, 18px on a phone) | mockup; theme `body2` |
| Sources | 1px `line` rule above, 22px above, 14px inside; count pill with no fill | mockup |
| Trust line | 14px above, 12.5px `inkMuted` | mockup; theme `caption` |
| Citation marker | unchanged: mono 11px 700, layer colour | `CitationMarkers.tsx` |
| Uncited sentence | `inkMuted` ink, no marker | theme token |
| Writing banner | `surfaceSunk`, 1px `line`, radius 8px, 16px 18px, 12px gap; 30px `layer1Wash` circle with `blue` pencil; lead 16px `ink`, name 700; dots 700 `blue`, 2px tracking; right line 12.5px `inkMuted` | mockup; theme `shape`, `body1`, `caption` |
| Writing line | 13.5px `inkMuted`, dots 700 `blue` | mockup |
| Card | padding 26px 32px 32px (20px 18px 24px on a phone), page gutter 16px on a phone | mockup |

No new colour, radius or type size, and no `theme.ts` change. `python3 tracker/check_design_tokens.py`: 0 invented colours.

## Deviations from the mockups

- Question heading stays 19px (theme `h3`, prototype `.q`). The mockup's 21px is not a design-system size.
- The banner's dots are at the line's 16px. The mockup's 18px is not a design-system size.
- The Plain language / Researcher toggle the mockups draw in the status strip is not moved there. Mode is still chosen before asking; moving it would need a decision on whether switching re-runs the question.
- The mockup's desktop column widths (62%, 72%) are not fixed; the browser sizes the columns, with the Sources column at 36px.
- The phone row's identifier is the cell as sent ("C0346153"); the mockup writes "MedGen C0346153", which the tokens do not carry.

## Requirement changes to existing tests

Each follows the approved design; none weakens an accessibility or host-allowlist assertion.

- `set9AnswerStructure.test.tsx`: a `list_item` renders as a table row (`tr`), not an `li`; "one spine segment per claim" becomes one `claim-text` per claim carrying `data-layer`, and no spine element exists.
- `phase48Premise.test.tsx`: "the provenance spine renders one segment per claim" becomes "every claim carries its own provenance", same count and the same uncited `none`.
- `streamingPendingCitations.test.tsx`, `e2e/citations-and-writing.spec.ts`: `spine-segment-N` `data-layer` is read from `claim-text-N`.
- `App.test.tsx`: the anonymous no-content arm checks for no `claim-text` instead of no spine segment, since a spine query would now pass vacuously.
- `CitationMarkers.test.tsx`: the name is asserted as the button's accessible name and as absent from the claim text; the visible-glyph arm ignores the hidden word joiner.
- `phase49Premise.test.tsx`: four arms ("does not dress a refusal in a success tick", "never reports a grounding verdict the run did not give", "colours each citation chip by its OWN source's layer", "never says a number of layers agreed") wait 5000ms for the landed answer, the same wait as that file's own `landAnAnswer` helper, because landing now includes the reveal. The chip arm asserts each marker's accessible name instead of name text inside the claim. "shows the same reasoning detail while the run is still going" now ends its stream during Act (one call still open), because once every tool result is in the run is in Write and the banner stands in for the reasoning log.
- `App.test.tsx`, "renders the truncation disclosure once the run lands": waits 5000ms for the note, the same wait every other landed-answer arm in that file uses, because landing now includes the reveal.
- `RunProgress.handoff.test.tsx`: during Write the banner replaces the handoff lines.
- `e2e/trust-surface.spec.ts`: segment count and layers are read from `claim-text`; "each spine segment stays level with the claim" becomes "each citation marker sits inside the claim it cites", the property the spine test protected.
- `e2e/cite-or-refuse.spec.ts`: the refusal arms count `claim-text` (the spine count was redundant with it); the grounded arm counts one `claim-text`.

## Verification

All commands run in `frontend/` unless noted, on 2026-09-14, at a machine load average of 50 to 180 from other agents' suites.

| Check | Result |
|-------|--------|
| `npm run build` | Exit 0 (the existing chunk-size warning only), after the last source change |
| `python3 tracker/check_design_tokens.py` (repository root) | Exit 0: 36 files, 0 invented colours, after the last source change |
| `npx tsc -b` | Exit 0 |
| `npx vitest run` (full) | 48 files, 460 tests: 41 files passed; 49 tests in 7 files failed, 46 of them on the 15 second timeout |
| Re-run alone, `--testTimeout=60000` | `App.test.tsx`, `personaIdentity.test.tsx`, `phase410Premise.test.tsx`, `phase48Premise.test.tsx`, `railCollapsePremise.test.tsx`, `threadContinuation.test.tsx`: all pass (load timeouts only). `phase49Premise.test.tsx`: 5 real failures from this change, fixed as listed under Requirement changes, then 21 of 21 pass |
| New unit files | `answerLayout.test.tsx` 9, `useAnswerReveal.test.ts` 7, `useRunView.writeState.test.tsx` 7, `useAgentRun.forwardCompat.test.ts` 2: all pass |
| e2e batch 1 (8 specs, 49 cases, `--workers=1`) | 45 passed, 4 failed: three 30 second test timeouts and the flush defect |
| e2e re-run (`answer-layout`, `trust-surface`, the three timed-out cases) | 16 of 17 passed, including the three and the fixed `trust-surface` arm; one `answer-layout` case timed out at load 183 |
| That case, alone, `--timeout=90000` | The four landed-answer layout cases: 4 of 4 passed |
| `cite-or-refuse`, `citation-host-allowlist`, `citations-and-writing`, `query-stream-and-stop`, `second-turn`, `accessibility` re-run after the last source change | 35 of 35 passed, exit 0 |

Playwright's `webServer` start timed out at this load, so the mock backend (`python3 -m tests.e2e_support.mock_llm_backend`, port 8931) and Vite (port 5273, `VITE_API_BASE_URL=http://127.0.0.1:8931`) were started by hand with the config's own commands and reused.

Accessibility: `e2e/accessibility.spec.ts` passed its cases in batch 1 except the timed-out "the run and answer screens are clean", which passed on re-run. `answer-layout.spec.ts` runs axe (WCAG 2.1 A and AA) on each landed answer at 1280 and 390, with 0 violations, asserts no sideways scroll at 390, and the citation markers keep their names ("Sources 1 to 4: Source 1, layer 2; ...").

## Screenshot comparison

Screenshots in this folder, from `e2e/answer-layout.spec.ts` against the e2e harness backend (mock model) with scripted BRCA1-shaped streams. The first four landed screenshots were taken before the lead paragraph break was added to the stream; the re-run replaces them. In full-page captures the sticky footer is painted mid-page, which is how Playwright stitches a page taller than the viewport, not a layout defect.

| Mockup element | Main (1280, Plain) | Researcher (1280) | Mobile (390, Plain) | Streaming (1280 and 390) |
|----------------|-------------------|-------------------|---------------------|--------------------------|
| Card, question, New search | Match (question at 19px, see Deviations) | Match | Match; question wraps with New search beside it | Match |
| Status strip: Answered, time, counts, Show work | Match | Match | Match, wraps to two lines | Not shown while writing, as in the mockup |
| Mode toggle in the strip | Not built (Deviations) | Not built | Not in the mobile mockup | n/a |
| Prose with bold terms and superscript layer-coloured markers | Match | Match, longer prose | Match | Match |
| Two lead paragraphs | One paragraph in the first capture; stream fixed | Same | Same | Same |
| Small-caps section heading with rule | Match | Match | Match | Match |
| Disease record table with narrow citation column | Match | Match, extra Source layer column | Stacked rows, name with marker, identifier under it | Rows appear under the banner |
| Gene section | Prose under The gene | Record table | Prose | n/a |
| Trials table | Match | Match | Stacked rows | Match |
| Notes muted list | Match | Match, no medical line | Match | Hidden until landed |
| Medical-advice line | Match | Absent, as in the mockup | Match | Hidden until landed |
| Sources collapsed with count and rule above | Match | Match | Match | Hidden until landed |
| Trust line with high-risk span | Match | Match | Match, wraps | Hidden until landed |
| No spine bar | Match | Match | Match | Match |
| Stepper filled to WRITE | n/a | n/a | n/a | Match |
| Writing banner: pencil in wash circle, lead name, dots, helpers found N records | n/a | n/a | n/a | Match; right line wraps under at 390 |
| "writing..." line at the end | n/a | n/a | n/a | Match |
| Phone: a marker never alone on a line | n/a | n/a | One orphan "8" in the first capture; fixed with the word joiner | n/a |
| No sideways scroll at 390 | n/a | n/a | Asserted | Asserted |

## Proposed hand tests 1, 7 and 12

- 1: Ask "Which diseases are associated with BRCA1?" in Plain language on a laptop. While it runs, the stepper reaches WRITE and a banner reads "{scientist} is writing the answer..." with who found how many records, before any sentence appears. Sentences then appear one by one. The landed answer reads as paragraphs, then small-caps headings over tables of diseases and trials, with small coloured numbers after sentences and in each row's last column, then Notes, "This is a research summary, not medical advice.", Sources and the trust line. No coloured bar runs beside the sentences.
- 7: Select the whole answer and paste it into a text editor. It reads as prose and table text only, with citation digits but no "Source 1, layer 2" or "Sources 1 to 4" text. With a screen reader, each citation number still announces its source and layer.
- 12: Repeat question 1 on a phone (about 390px wide) in Researcher. Tables become stacked rows, name first with its citation number, identifier underneath; the page never scrolls sideways; the banner wraps without overflow.

## Proposed DECISIONS.md rows

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-09-14 | Enter the Write state in the UI when Act closes (every opened call has a result, or the plan selected no tool) | Keep keying Write on the first token; wait for a backend live Write event | <details><summary>why</summary>Measured: tokens arrive in one burst after a 1.9 to 22.6s silent gap, so keyed on the first token the writing state never showed. The backend fix is owned elsewhere; the frontend derivation needs no wire change and stays correct if a live event arrives later.</details> |
| 2026-09-14 | Reveal a token burst one sentence at a time (1.5s minimum banner, 110ms live, 40ms after done) and hold the view unlanded until complete | Render the burst at once; reveal only inside the answer body while the answer screen shows landed | <details><summary>why</summary>A fast write must still read as writing. Gating the whole view keeps every consumer (answer screen, history, tour) in one consistent state and returns the original view object unchanged, so nothing is dropped.</details> |
| 2026-09-14 | Retire the per-sentence provenance spine; carry provenance on each claim as `data-layer`, with muted ink and the spoken statement for uncited sentences | Keep the spine beside the new layout; keep hidden spine elements for tests | <details><summary>why</summary>The approved mockups have no spine and use marker colour for layer. A hidden spine kept only for tests would assert a design that no longer exists.</details> |
| 2026-09-14 | Marker accessible names via `aria-label`; spoken statements with no control keep hidden text under `user-select: none` | Visually hidden text nodes (the old way); CSS generated content | <details><summary>why</summary>Hidden text nodes were copied with the prose. `aria-label` keeps identical names. Generated content is invisible to jsdom tests and read inconsistently.</details> |
| 2026-09-14 | Group record-shaped claims (table rows, list items, labelled record lines) into record blocks, parsing a fixed label list in the frontend | Leave record lines as prose; wait for the backend to type the findings tail | <details><summary>why</summary>The product owner saw "Disease name: X.1 Disease name: Y.2" as one line. A fixed label list is deterministic, changes no words beyond the prefix, and works for today's and older producers.</details> |
| 2026-09-14 | Skip `step` and `stage` SSE frames by name in `consumeEventStream` | Skip every unknown frame; leave the throw | <details><summary>why</summary>The throw would end every run the day the backend emits a live Write frame. A two-name allowlist keeps rejecting `cost` frames.</details> |

## Findings during the work

- Machine load average 52 during verification (other agents running suites). Vitest timeouts on touched files passed at a 60s timeout; the real failures below are fixed.
- My own defect: `useRunView` read `plan.payload.tool_calls` unguarded, and a fixture in `phase48Premise.test.tsx` omits it. Guarded.
- My own defect: `useRunView` kept a table header only with exactly two cells, which would have dropped the Researcher table's three-column header. Now any width.
- `parseAgentEvent` throws on an unknown frame, which ends the run; handled as above.
- Real defect, found by the rewritten trust-surface arm: a stream that ends in an error (that spec's scripted `done` frame is malformed, so `useAgentRun` reports status `error` without the view landing) kept its sentences behind the reveal, so no marker existed when the test looked. Fixed with the `flush` option; `App` passes `flush: status === "error"`.
- Phone screenshot: a citation marker could wrap onto a line of its own ("gene expression" then "8"). Fixed with a hidden word joiner.
- First full e2e batch (8 specs, 49 cases, 15 minutes at load average 60 to 68): 45 passed, 4 failed. Three failed only on the 30 second test timeout (`accessibility` "the run and answer screens are clean", `query-stream-and-stop` "stop halts the run on the server", `second-turn` "a follow-up question produces a second answer"); their snapshots show a landed answer, or a follow-up still at Guard with no event from the mock backend yet, so no reveal is involved. The fourth is the flush defect above. All four are being re-run.
- Playwright's own `webServer` start timed out (60 seconds) at this load, so the mock backend and Vite were started by hand on the configured ports (8931, 5273) and reused via `reuseExistingServer`.
- Two assertions in my new layout test were wrong, not the code: MUI renders the inline note as a `p`, and a table's `textContent` has no whitespace between rows. Both corrected.
