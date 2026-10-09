# Card 109 build: a history row with no saved answer says so

## What changed

- `frontend/src/App.tsx`, `formatHistoryMeta`: when the API sends `has_saved_answer: false`, the row reads "No answer saved" in place of "N sources cited". The date part stays.
- The decision is by the saved-answer flag, not by the outcome. An answered row whose outcome is something else keeps its count. A row with no flag (an older API) keeps today's behaviour.
- `frontend/src/App.test.tsx`: one new test covering four rows.
- `testing/Test_queries_and_workflows.md`: one line under query 56 (Stop a search).

## Before and after, in the user's words

- Before: stop a search after its records appear, and "Your searches" shows "21 sources cited", the same as an answered search. You cannot tell which row holds an answer.
- After: that row reads "No answer saved · Oct 9". An answered row reads "4 sources cited · Oct 9". Guardrail refusals and clarifying questions, which also save no answer, read "No answer saved" too.

## Width at 390 px

The meta line is a block text span with normal wrapping (`FollowUp.tsx`, around line 737). "No answer saved" is shorter than "21 sources cited", so nothing new overflows. A long question wraps as before.

## Tests

- Red run: with the condition mutated so it never matches, `npx vitest run src/App.test.tsx` gives 1 failed, 38 passed: `expected 'Stopped question21 sources cited · Au…' to match /No answer saved/`.
- Restored: `npx vitest run src/App.test.tsx` gives 39 passed.
- `npx tsc --noEmit -p .`: no output (clean).
- `npm run build`: succeeds (only the existing chunk size warning).
- `ruff check` from the root: All checks passed.

## Fix round

Finding F-109-V-01 (major): `withValidatedOptionalFields` in `frontend/src/lib/api.ts` kept `has_saved_answer` only when true, so the real `fetchHistory` turned `false` into absent and the row kept its source count. The round 1 test passed only because it mocked `fetchHistory`.

- Fix: the validator keeps `has_saved_answer` when it is a boolean, true or false. A string, a number or null is still dropped to absent. The field comment in `HistoryItem` now says so.
- Readers of the flag in `frontend/src`: `formatHistoryMeta` tests `=== false` (the new "No answer saved" path, the only one that changes); the restored-row builder tests `=== true` to set `hasSavedAnswer`, so false gives false, as absent did; the reopen handler tests `item.hasSavedAnswer === true`, so a false row still re-asks exactly as before. Nothing tests `!== undefined` or `in`. A person sees one change: the false row's text.
- New tests: `frontend/src/lib/api.fetchHistory.test.ts` (real `fetchHistory`, fetch stubbed, rows false, true, absent, and a string "false" arrive as false, true, undefined, undefined) and `frontend/src/App.historyNoAnswer.test.tsx` (App rendered with only `fetch` stubbed; the false row reads "No answer saved", the true row and the no-flag row read "21 sources cited").
- Red on the old validator: 2 failed, 8 passed (`undefined` instead of `false`; `Stopped question21 sources cited` did not match `/No answer saved/`). Green after the fix: 10 passed. Mutated back to `=== true`: 2 failed, restored.
- Whole frontend suite: 67 files, 610 tests passed. `npx tsc --noEmit -p .`: clean. `npm run build`: succeeds (existing chunk size warning only). `ruff check` from the root: All checks passed.
