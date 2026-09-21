# Bold and stagger, state of the worktree

Inventory of uncommitted work in `.claude/worktrees/agent-a8393711bb57d579b` (branch `worktree-agent-a8393711bb57d579b`, based on develop `e5947e0`), covering UI fix 11.27 (too much bold) and 11.28 (pace searching to writing). Written 2026-09-19, agent stopped before it reported.

## Table of contents

- [Summary](#summary)
- [What exists, per file](#what-exists-per-file)
- [Test results](#test-results)
- [What is missing or wrong](#what-is-missing-or-wrong)
- [Conflict with develop](#conflict-with-develop)
- [Recommendation](#recommendation)

## Summary

Both items have a real, substantial implementation, not a stub. 11.27 (bold) is complete and passes its own test plus the existing pinned test it changed the requirement on. 11.28 (stagger) is also substantially built, respects all four hard bounds from the ticket, and ships its own unit tests and a Playwright e2e spec, but its landing broke one existing premise test from build phase 4.9 that the agent did not fix or acknowledge, unlike five other pre-existing test files where it correctly widened timeouts for the same underlying cause. `node_modules` is present in the worktree (not fresh-installed by me). `tsc -b` and `npm run build` are clean. The full unit suite is 473 passed, 1 failed, out of 474.

## What exists, per file

| File | Status | What it does |
|---|---|---|
| `frontend/src/hooks/usePacedEvents.ts` | New | The 11.28 core. Releases a growing prefix of the real event array, one event at a time, each held at `max(arrival, previous release + dwell)` and capped at `arrival + maxLagMs` (3500ms). Never reorders or invents events. Flushes (shows everything at once) on Stop, a failed stream, an `error` event, a failed guard, an answer-level refusal, or a clarification. Reduced motion swaps in a `REDUCED_PACING` table with the same order and a 1000ms cap. A new `runKey`, or an event array that no longer starts with what was already seen, resets the schedule. |
| `frontend/src/hooks/usePacedEvents.test.ts` | New | 12 or so unit tests, fake timers, covering ordering, dwell minimums, the maxLag cap, flush on stop/error/refusal/clarification, reduced motion, and run-key reset. |
| `frontend/src/App.tsx` | Modified | Wires `usePacedEvents` between `useAgentRun` and `useRunView`. Reads `prefers-reduced-motion` via `useMediaQuery`. Keeps `stopEnabled` derived from the real (unpaced) event stream via a new `deriveStopEnabled` import from `StopButton`, specifically so Stop does not stay offered once the server-side run is actually done while its last stages are still animating. Passes `reducedMotion` through to `useAnswerReveal` as well. |
| `frontend/src/hooks/useAnswerReveal.ts` | Modified | Adds `reducedMinBannerMs` (300ms) and a `reducedMotion` option so the writing-banner minimum hold also shortens under reduced motion, keeping the existing banner-then-sentences order. |
| `frontend/src/hooks/useAnswerReveal.test.ts` | Modified | One new test asserting the reduced banner minimum is shorter and that order is preserved. |
| `frontend/src/components/screens/AnswerScreen.tsx` | Modified | The 11.27 core. Deletes `withEmphasis` (bolded every backend `emphasis` term everywhere: prose, table cells, stacked rows). Adds `mainPointFor`, which picks exactly one term from the lead prose claim only (never a table row, list item, or record line), preferring a term the question itself names, else the first term in the sentence. Adds `withMainPoint`, which bolds only that one term's first occurrence. Table cells and other emphasis sites now render plain text. Also turns three previously-bold status/trust spans (outcome word, mono badge, trust signal spans) to regular weight, on the stated reasoning that colour and the risk tone already carry the signal. Threads a new `question` prop into `AnswerBody` and `FoldedTurn` so `mainPointFor` can prefer a question-named term. |
| `frontend/src/answerBold.test.tsx` | New | Unit tests for `mainPointFor` and the rendered bold count: exactly one `<strong>` in the lead, none elsewhere, prefers a question-named term, falls back to the first term when nothing matches, returns null (no bold) when the lead carries no emphasis. |
| `frontend/e2e/bold-and-stagger.spec.ts` | New | Playwright spec, scripted single-body SSE stream, for both fixes at 1280 and 390: landed bold placement, and a burst run shown in stages with lower-bound dwell assertions and mid-handoff screenshots. Explicitly does not cover the 3.5s cap, Stop, or reduced motion (left to the unit tests). Not run in this verification pass since it needs a running app plus Playwright browsers; scope was vitest, tsc, and build. |
| `frontend/src/App.test.tsx`, `phase410Premise.test.tsx`, `phase49Premise.test.tsx`, `threadContinuation.test.tsx` | Modified | Five `findByTestId`/`findByText` timeouts widened from 5000ms to 10000ms, with comments explaining that landing an answer now also waits through the reveal/pacing hold. Mechanical and consistent with the pacing change. |
| `frontend/src/set9AnswerStructure.test.tsx` | Modified | Updates the pinned bold assertion to the new 11.27 behaviour: exactly one `<strong>` in the lead claim (`BRCA1`), the second previously-bold term (`Familial cancer of breast`) now plain. Comment marks it as a deliberate requirement change, correctly. |
| `testing/Developer/reports/2026-09-14_answer_layout/*.png`, `2026-09-14_citations_and_writing/*.png` | Modified (binary) | Re-captured screenshots, presumably from re-running the existing Playwright specs against the new behaviour. Not inspected pixel by pixel. |
| `testing/Developer/reports/2026-09-14_bold_and_stagger/` | New directory | Presumably the new spec's screenshot output. |

## Test results

Run from `frontend/` inside the worktree. `node_modules` was already present; I did not install anything.

Requested targeted run:

```
npx vitest run src/answerBold.test.tsx src/hooks/usePacedEvents.test.ts src/hooks/useAnswerReveal.test.ts
```
Result: 3 files, 21 tests, all passed.

Other files the diff touches (`App.test.tsx`, `phase410Premise.test.tsx`, `phase49Premise.test.tsx`, `set9AnswerStructure.test.tsx`, `threadContinuation.test.tsx`):

```
npx vitest run src/App.test.tsx src/phase410Premise.test.tsx src/phase49Premise.test.tsx src/set9AnswerStructure.test.tsx src/threadContinuation.test.tsx
```
Result: 5 files, 87 tests, 86 passed, 1 failed.

Failing test: `phase49Premise.test.tsx`, "shows the same reasoning detail while the run is still going" (build phase 4.9's own premise, tag F-4.8-D-10). It streams guard, think, plan and one running tool_start, closes the connection with no `done` and no error, then asserts the reasoning log already contains the think and plan narrative. It failed both in the isolated run and in the full suite, with the log showing only the Guard line at assertion time. See "What is missing or wrong" below.

Full suite:

```
npx vitest run
```
Result: 50 files, 474 tests, 473 passed, 1 failed (the same test above; no other regressions found across the whole frontend suite).

Type check and build:

```
npx tsc -b
```
Result: clean, no output, no errors.

```
npm run build
```
Result: succeeded. `tsc -b && vite build`, 944 modules, output written to `dist/`, only the pre-existing chunk-size-over-500kB advisory warning (unrelated to this change).

## What is missing or wrong

Against 11.27 (bold): nothing found wrong. The change is self-consistent, has its own test file, and correctly updates the one pinned test (`set9AnswerStructure.test.tsx`) whose expectation the new requirement supersedes, with a comment naming it as a deliberate requirement change rather than a silent edit. This matches `goal-contracts.md`'s guidance on the difference between fixing a check and fixing the subject.

Against 11.28 and its four hard bounds:

- "may add at most about 4 seconds": met. `maxLagMs` is 3500ms and the docstring states the arithmetic (600+700+700+350+... capped at 3500 for a two-helper run).
- "must add nothing when the run is already slow": met by construction. Each event releases at `max(arrival, previous release + dwell)`, so when real arrivals are already spaced out past the dwell, release happens immediately at arrival with zero added wait.
- "must yield immediately to Stop or an error": met for Stop, `error` events, a failed guard, an answer-level refusal, and a clarification question, all via `isFlushEvent` plus the `stopped`/`flush` options passed from `App.tsx`. Not exercised end to end here (would need the e2e spec or a manual run), but the unit tests do cover each flush path with fake timers.
- "reduced motion respected": met. `prefers-reduced-motion` is read in `App.tsx` and threaded into both `usePacedEvents` and `useAnswerReveal`, each swapping to a shortened timing table that keeps the same order.

One real defect found: the pacing change broke an existing, pinned premise test from build phase 4.9, "shows the same reasoning detail while the run is still going" (F-4.8-D-10). That test's contract is that once the reasoning log renders at all during an in-progress run, it already shows the full think/plan detail available so far, because previously every event in a single SSE chunk landed in one synchronous update. Under pacing, the same burst is now spread across up to roughly 2 seconds (`guardMs` + `thinkMs` + `planMs` = 600 + 700 + 700), so the reasoning log can render with only the Guard line visible at the moment a test (or a fast reader) first observes it. The agent fixed the five other timeout-sensitive tests by widening their timeouts with an explanatory comment, but did not touch this one, so the work was left in a state where its own test suite is red for a reason inside the new code. Whether this is "just" a test that needs a similar wait-and-recheck, or an actual product regression (a reader watching the reasoning log while the run is genuinely stalled now sees stale detail for up to ~2s), is a real open question, not just a scheduling nit, since 11.28's ticket says pacing "must add nothing when the run is already slow" and a stalled/no-further-events run is the slow case: here it silently added up to 2 seconds of staleness rather than nothing.

Not evaluated: the Playwright e2e spec (`bold-and-stagger.spec.ts`) was read but not executed, since running it needs the dev server and Playwright browsers, outside the requested vitest/tsc/build scope. Its own comment says it deliberately does not cover the maxLag cap, Stop, or reduced motion, leaving those to the unit tests, which is a reasonable split but means Stop/error yield-immediately behaviour has only been unit-tested with fake timers, never observed against a real browser paint.

## Conflict with develop

```
git -C <main repo> diff --stat e5947e0..ba38cc9 -- frontend/
```
returns nothing: no frontend file changed on develop between the worktree's base commit and develop's current tip. Every file this worktree touches under `frontend/` is therefore untouched on develop since the branch point, so a merge would apply cleanly with no textual conflicts. This says nothing about whether the change is correct, only that landing it would not require conflict resolution.

## Recommendation

Finish this work rather than discard it. Both features are substantially built, the bold change is complete and correct, tsc and the build are clean, 473 of 474 unit tests pass, and there is no merge conflict with develop. The one failing test is a scoped, nameable defect (the reasoning log can go stale for up to about 2 seconds during a genuinely stalled run) rather than evidence the approach is wrong, and it is the kind of gap a short follow-up session closes: either widen that test's wait the same way the other five were widened, if staleness up to 2s is acceptable, or add reasoning-log content to the list of things that flush immediately (alongside Stop, error, refusal and clarification) if it is not. Rebuilding either 11.27 or 11.28 from scratch would throw away a design that already respects all four stated hard bounds on 11.28 and already has real unit and e2e test coverage.
