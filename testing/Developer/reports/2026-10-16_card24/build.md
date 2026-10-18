# Card 24 build: the Plain language and Researcher switch on an answer

Branch `fix/card24-answer-depth-switch`, from develop `bce08af9`. Built by the lead's builder, dial 2, on the owner's decision of 2026-10-15 (`DECISIONS.md`).

## Table of contents

- [What the person sees](#what-the-person-sees)
- [The cherry-pick](#the-cherry-pick)
- [The cost line](#the-cost-line)
- [Tests and mutations](#tests-and-mutations)
- [Gates](#gates)
- [Design gaps](#design-gaps)
- [Not covered](#not-covered)
- [Learnings](#learnings)

## What the person sees

- A two-button switch, Plain language and Researcher, in the answer's status strip on the right, before Show work.
- Clicking the mode already shown does nothing.
- Clicking the other mode shows one line under the strip's row and runs nothing. "Ask again" runs the question once at that mode, and the answer they were reading folds above the new one like a follow-up. "Cancel" closes the line.
- While the new answer is being written the switch is gone, so a run in flight cannot be switched.
- Screenshots with the cost line open, signed in: `w1280_cost_line.png` and `w390_cost_line.png` in this folder.

## The cherry-pick

Commit `df7d7a2c` from the local tag `parked/phase-8.4-2026-09-25`, nothing else, kept with its own message. It is commit `0b49ac45` here. Two conflicts:

| File | Conflict | Resolution |
|---|---|---|
| `DepthControl.test.tsx` | Import line | `import { DepthControl, DepthStripToggle, displayedMode } from "./DepthControl";`. `ANSWER_MODE_EXPLAINER` is used nowhere else in the file, so it is left out. |
| `AnswerScreen.tsx` | The landed branch of the answer body. Develop's phase 8.7 body is one `AnswerBody` at one position for running and landed; the port still had the old two-branch shape | Kept develop's structure whole and added `onDepthChange` and `depthValue` to the landed `AnswerBody` only. The streaming preview gets neither. |

## The cost line

- Where it comes from: `depthConfirmCopy` in `App.tsx`, beside `dailyLimitLine`, reading the same `allowance` state `dailyLimitPhrase` reads. `AnswerScreen` hands it to the live `AnswerBody`. The screen writes no number of its own.
- Counted caller (a guest, `allowance.counted` true): `Ask this question again in <mode>? It counts as one new search (<N> left today).` with `<N>` = `Math.max(total - used, 0)`.
- Anyone else, or before the count loads: `Ask this question again in <mode>? It runs as one new search.`
- `<mode>` is the label from `AUDIENCE_MODE_OPTIONS`. Line: `data-testid="answer-depth-confirm"`, `body2`, `inkMuted`. An `aria-live="polite"` box stays mounted while the strip shows and holds the line only while a mode is held. "Ask again" is styled as New search, "Cancel" as Show work. The held mode clears when the answer's mode or question changes.
- The strip's outer box now has `data-testid="answer-status-strip"`.
- The 12 "Card 33" comments and test names under `frontend/src` now say card 24.

## Tests and mutations

Unit, after the port: `App.depthToggle.test.tsx` (4 tests), `AnswerScreen.depthToggle.test.tsx` (9), `DepthControl.test.tsx` (cherry-picked cases). Each was proved red by one change, then restored (`cmp` against backups confirmed).

| Mutation | Red tests |
|---|---|
| The switch's handler also calls `onDepthChange` | 7 of 13: cost line shows and runs nothing, Ask again, Cancel, the App dispatch test, both forms, in flight. The e2e spec also goes red at both widths. |
| "Ask again" does not call `onDepthChange` | 3: Ask again, App dispatch, in flight |
| "Cancel" calls `onDepthChange` | 1: Cancel |
| The guest form is built whatever `counted` says | 1: signed-in form has no number |
| The same-mode check in `DepthStripToggle` removed | 1: same mode does nothing |
| `onDepthChange`, `meta` and `outcome` passed to the streaming body | 1: no switch on the streaming preview (the existing test gained `meta` and `outcome`, without which the strip never drew and the mutation passed unseen) |

The guest-form test asserts "(3 left today)" from `used: 2, total: 5`. New spec `frontend/e2e/answer-depth-switch.spec.ts`, at 1280 and 390: switch visible with Plain language pressed, clicking Researcher shows the line with no new POST, axe scan of `answer-status-strip` clean, no sideways scroll, "Ask again" records exactly one new POST with `audience_depth: "researcher"`. The harness account is signed in, so it shows the signed-in form; the guest form is covered by the unit test.

## Gates

| Gate | Result |
|---|---|
| `npm run build` | passes (only the existing chunk-size warning) |
| `npx vitest run --maxWorkers=2` | 71 files, 649 tests passed |
| Card 22, 23 and 102 tests (`AnswerScreen.card22.test.tsx`, `src/answerLayout.test.tsx`, `SavedAnswerScreen.card102.test.tsx`) | 3 files, 41 tests passed |
| Playwright `answer-depth-switch.spec.ts` and `accessibility.spec.ts` | 12 passed |
| `ruff check` (no path) | All checks passed |
| isort (gate 2 paths) | passed |
| `pytest tests/system_03_search_agent` | not run: no Python file changed |

## Design gaps

- The confirmation line and its two buttons are drawn nowhere in the mockups or the prototype. Built from existing tokens, no new colour, size or weight.
- `Mobile.dc.html` draws the strip with no switch, and `app.html` has no rule for it. The strip wraps, so at 390 the switch drops to its own line.
- The design system draws the control only before asking, on the navy hero, with the old three modes. The two-mode list is the app's.

## Not covered

- At "(0 left today)", "Ask again" still sends the run and the server refuses it with the existing daily-limit refusal. No test proves that refusal here.
- The live app was not asked any questions; the fake-model tests carry the proof.

## Learnings

- A test of "the switch is gone while running" passed unseen until the streaming body was given `meta`, because the strip only draws when `meta` or `outcome` exists. A negative test must make the thing it forbids possible first.
- The e2e harness account can start on Researcher (its saved depth), so the spec picks Plain language on the home page before asking.
