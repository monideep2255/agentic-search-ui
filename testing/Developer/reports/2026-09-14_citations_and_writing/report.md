# Quieter citations and a writing state, 2026-09-14

Built by a sub-agent at the product owner's request ("the inline citations overwhelm the answer", "show people the answer is loading, in the sense like [scientist] is writing the answer"). The harness refused the builder's own write of this file, so the main agent wrote it from the builder's final report. Screenshots sit beside this file.

## Table of contents

- [What changed for the reader](#what-changed-for-the-reader)
- [Design choice and tokens](#design-choice-and-tokens)
- [Design gaps named](#design-gaps-named)
- [Files changed](#files-changed)
- [Tests whose requirement changed](#tests-whose-requirement-changed)
- [Verify results](#verify-results)
- [Screenshots](#screenshots)
- [Proposed change to hand-test 12](#proposed-change-to-hand-test-12)
- [Open points](#open-points)
- [Follow-up round](#follow-up-round)

## What changed for the reader

- Citations: each boxed chip is now a small superscript number, rendered as a real button in the source's layer colour.
  - One to three sources show as a comma list, for example `5, 6`.
  - Four or more show as one marker: a range such as `1–13` when the numbers run in order, otherwise the first number plus how many more (`1 +3`). Three is the limit because a longer list starts to crowd the sentence again and each marker is one Tab stop; the marker's card lists every source, so nothing is lost.
- The card: hover, keyboard focus or tap opens it. It shows the source name and id, the tool, the layer in words (`[1] L2 · live`) and an "Open the record" link.
  - The link appears only for an allowed https host; otherwise the card says "Not linked: this URL is not on a recognised NCBI host."
  - The allowed-host list now lives in one place, and the Sources section reads the same one.
  - The card closes on Escape, blur, a click outside, scroll or pointer leave. At 390px it stays 16px inside both screen edges.
  - The Sources section below the answer is unchanged.
- Screen readers: each marker is named "Source 1, layer 2". A range is named "Sources 1 to 13: Source 1, layer 2; …". Uncited sentences still say "This sentence has no source."
- Writing state:
  - During Write the caption reads "{Lead} is writing the answer" with three pulsing dots.
  - While sentences stream in, a quiet "writing..." line follows the text, and disappears when the run lands or Stop is pressed.
  - Under reduced motion both ellipses are static.

## Design choice and tokens

No new colour, radius or type size; `frontend/src/theme.ts` is unchanged.

| Element | Where the value comes from |
|---|---|
| Marker: mono 11px, weight 700, 0.06em tracking | The layer badge `.n` rule (`identity/layer-badges.html`); 11px is also the theme's `overline` size |
| Marker colour | `layerColour(n).main`; a range spanning several layers uses `inkMuted` |
| Comma | `inkFaint` |
| Focus ring: 3px, offset 2px, 4px radius | The prototype's `:focus-visible` rule (`app.html:25`), colour `link`, radius `--r-sm` |
| Card: surface, 1px `line` border, 8px radius, shadow, 12px 14px padding, 280 wide | The `PersonaInfo` card |
| Card layer dot, 12px with 3px radius | `.dot` in layer-badges |
| Card name 13.5px/600 `ink`; tool mono 12.5px `inkMuted`; link 12.5px `link`; off-host note 11.5px `risk` | The persona card and source card rows |
| Ellipsis: opacity 0.35 to 1 over 1.1s | The live pip's `@keyframes p` in `screens/streaming.html` |
| "writing..." line: 13.5px `inkMuted` | The inline note in the same grid |

## Design gaps named

- Citation chip: it is designed, so this is a deliberate change the product owner asked for. A dated note with a sample was added to `docs/build/design/design-system/identity/citation-chip.html`.
- Marker card and writing line: neither has a design. Both are built from the neighbours listed above.
- Write caption: it no longer matches `components/persona.html` and `prototype/app.html:988`, which say "…, citing as it goes". Recorded in the chip card's note; the persona card is not edited.
- One value with no token: the range card's `maxHeight: min(60vh, 320px)`, a layout bound rather than a colour, radius or type size.
- Animation rule: Section 12.7 bans an animated persona. Only the progress dots move; the chip and avatar stay still.

## Files changed

- New:
  - `frontend/src/components/answer/CitationMarkers.tsx`
  - `frontend/src/components/answer/CitationMarkers.test.tsx`
  - `frontend/src/components/screens/WritingState.test.tsx`
  - `frontend/e2e/citations-and-writing.spec.ts`, which also produces the screenshots
- Edited:
  - `frontend/src/components/screens/AnswerScreen.tsx`: markers replace both chip renderers; new `writing` and `stopped` props; the host list is re-exported.
  - `frontend/src/components/shell/PersonaChip.tsx`: the Write caption text, `WritingEllipsis`, `usePrefersReducedMotion`.
  - `frontend/src/App.tsx`: passes `stopped` to the answer screen for follow-ups.
  - `frontend/e2e/citation-host-allowlist.spec.ts`: one added test.
  - `docs/build/design/design-system/identity/citation-chip.html`: the change note.

## Tests whose requirement changed

No accessibility or host-allowlist assertion was weakened.

- `e2e/trust-surface.spec.ts`: `getByLabel(/^source 1$/)` became `getByRole("button", {name: /^source 1, layer 1$/})`, which is stricter because it also checks the role and the layer.
- `e2e/tool-chip.spec.ts`: the "never repeats its own source" check now reads the card opened by focusing the marker, because the source name no longer sits on the marker.
- `src/phase49Premise.test.tsx`, identity test: the source name is checked in each card, and each card must not show its neighbour's name.
- `src/phase49Premise.test.tsx`, layer colour test: it reads `color` instead of `borderLeftColor`, and pins the exact layer 1 and layer 3 values.
- Added coverage: a browser test that the marker card links only the allowed host.

## Verify results

Each command in `frontend/`, on its own exit code.

- `npm run build`: exit 0, after removing one unused import that failed the first attempt.
- `npx vitest run`: baseline 410 of 410 across 41 files. After the change, 430 tests, 429 passed; the one failure was a 15-second load timeout in `railCollapsePremise.test.tsx`, which passed 20 of 20 when rerun alone. A targeted run of the new and edited files passed 58 of 58.
- Mutation checks: removing `onFocus` turned 3 tests red; letting the host check accept any URL turned the allowlist test red. The source file was restored byte for byte.
- `npx playwright test e2e/trust-surface.spec.ts e2e/cite-or-refuse.spec.ts e2e/citation-host-allowlist.spec.ts e2e/query-stream-and-stop.spec.ts e2e/second-turn.spec.ts e2e/accessibility.spec.ts --workers=1`: 36 passed, exit 0.
- `tool-chip.spec.ts` and the screenshot spec: 2 and 4 passed. The first screenshot run failed because the scripted `done` frame lacked required fields; it passed once the frame was fixed.
- `python3 tracker/check_design_tokens.py`: 35 files, 0 invented colours, exit 0.

## Screenshots

At 1280 and 390 wide, from the e2e harness with the mock model:

- `w1280_cited_answer.png`, `w390_cited_answer.png`
- `w1280_marker_card_open.png`, `w390_marker_card_open.png`
- `w1280_write_step.png`, `w390_write_step.png`

In the 390 answer, the fixed footer overlapping the follow-up field is a full-page capture artifact and appeared the same way before this change.

## Proposed change to hand-test 12

Not applied by the builder; the main agent owns `testing/Product/Product_workflows.md`.

- Steps: get the answer → hover, tap, or Tab to a small number after a sentence → read the card → press Escape → read the line under the answer → click its "i" → look through the sources → open "Show work".
- Expected: each cited sentence ends in small raised numbers, not boxes, and a sentence with many sources shows one range such as 1–13. Hovering, tapping or tabbing to a number opens a small card naming the source, its id, its layer in words, and an "Open the record" link. Escape or clicking elsewhere closes it. Any sentence with no source has no number and must never look like a cited claim. While the answer is being written, the line under the stepper reads "{scientist} is writing the answer..." and "writing..." follows the sentences; both disappear when the answer lands or Stop is pressed.

## Open points

- Speed is measured separately, in `testing/Developer/reports/2026-09-14_synth_effort_none/`.
- Raw markers while streaming: until the citation frames arrive, streamed sentences show raw `[1][2]…` text next to a grey spine (visible in `w1280_write_step.png`). Sent back to the builder the same day to render them quietly instead.

## Follow-up round

Asked the same day: a streaming sentence must never show raw `[1][2]` text, and a sentence still waiting for its sources must not read as uncited.

### How uncited was decided mid-stream

- `useRunView.ts` stripped only the `[N]` markers whose citation frames had already arrived (the F-4.8-R-05 rule: nothing is stripped by pattern alone). Mid-stream, tokens arrive before their citation frames, so nothing matched and the brackets stayed.
- A claim with no resolved citation got `layer: null` and `citations: []`. `AnswerScreen.tsx` renders that as the grey `lineStrong` spine segment and the hidden words "This sentence has no source.". So a pending sentence looked, and was announced, exactly like an uncited one.

### The fix, least invasive

- `useRunView.ts`: while the run has NOT landed, a token strips as many bracketed numbers as it has unresolved `marker_ids`, and records that count as `claim.pendingCitations`. Once the run lands, `unresolved` is 0, so the landed answer is classified exactly as before. An unresolved marker on a landed answer stays as prose.
- `CitationMarkers.tsx`: a claim with `pending` and no resolved citations renders a pending superscript instead of the "no source" words:
  - same mono 11px bold type as a real marker, in `designTokens.inkFaint`;
  - one middle dot per pending source, capped at three (the trust line's separator glyph);
  - a plain `<sup>`, not a button: not focusable, no card;
  - spoken "Source pending." or "2 sources pending.".
- `AnswerScreen.tsx`: a claim with `layer: null` and `pendingCitations` gets `data-layer="pending"` and the lighter `designTokens.line` spine colour, never the uncited `lineStrong`. When the frames arrive the claim resolves to real markers and its layer colour on the next render.
- No new colour, radius or type size. `python3 tracker/check_design_tokens.py`: 0 invented colours.

### Tests, populate-checked

New file `frontend/src/streamingPendingCitations.test.tsx`, 5 tests:

- mid-stream `[1][2]` with no citation frames: no bracket text, "2 sources pending.", no button, no "no source" words, spine `pending`;
- the same sentence after both frames arrive: real "Source 1, layer 2" and "Source 2, layer 2" buttons, spine layer 2;
- one of two frames arrived: one real marker, one pending, no brackets;
- landed answer: a genuinely uncited sentence still says "This sentence has no source." with spine `none`;
- landed answer with a marker that never resolved: the `[1][2]` stays as prose (R-05 unchanged).

`frontend/e2e/citations-and-writing.spec.ts`, write-step test: now also asserts no bracket text, a pending marker and a pending spine segment, and zero "no source" words, in a real browser.

Mutation check: forcing `unresolved = 0` turned 2 of the 5 tests red; the source was restored byte for byte.

### Verify, each on its own exit code

| Command | Result |
|---|---|
| `npm run build` | exit 0 |
| `npx vitest run`, first full run | exit 1: 9 failed, all 15 to 30 second timeouts, run while Playwright was also running |
| `npx vitest run`, second full run | exit 1: 62 failed, 373 passed, 44 files; all timeouts; machine load average 33 to 46 from other processes (three editor extension hosts near 95% CPU each) |
| The 8 files that timed out, each run alone | 7 passed at once: AuthGate 9, personaIdentity 5, phase410Premise 17, phase48Premise 26, phase49Premise 21, railCollapsePremise 20, threadContinuation 3. `App.test.tsx` timed out again at load 12 to 26, then passed 38 of 38 alone at load 9 to 10, with 0 timeouts and 0 assertion errors |
| New and related unit files together | 42 of 42 |
| `npx playwright test e2e/citations-and-writing.spec.ts e2e/query-stream-and-stop.spec.ts e2e/trust-surface.spec.ts --workers=1` | exit 0, 15 passed |
| `python3 tracker/check_design_tokens.py` | exit 0, 0 invented colours |

Not established: one clean full-suite `npx vitest run` with every file green in a single pass. The machine's load did not allow it during this round; every file is green when run alone.

### Screenshots

`w1280_write_step.png` and `w390_write_step.png` are regenerated. Both show the sentences with no bracket text, faint pending dots after each sentence, a lighter spine than the uncited grey, and "writing..." under the text. In the 390 capture the app bar and footer overlap the content; that is the full-page capture artifact seen in the earlier screenshots.

### Files changed in this round

- `frontend/src/hooks/useRunView.ts`
- `frontend/src/components/answer/CitationMarkers.tsx`
- `frontend/src/components/screens/AnswerScreen.tsx`
- `frontend/src/streamingPendingCitations.test.tsx` (new)
- `frontend/e2e/citations-and-writing.spec.ts`
