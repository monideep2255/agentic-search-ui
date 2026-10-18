Verdict: a search asked in the current browser tab never gets `hasSavedAnswer` set on its own rail row, so clicking it always falls to the re-ask branch, which is exactly what the screenshot shows: the just-answered BRCA1 row, sitting active at the top of the rail, re-running when clicked.

## The click path

`frontend/src/App.tsx`, the `HistoryRail`'s `onOpen` prop (lines 1947 to 1973): looks up the clicked row in `history` by `id`. If `item.hasSavedAnswer === true` and `item.traceId` and `token` are all present, it fetches the stored answer (`fetchHistoryAnswer`, `lib/api.ts`) and shows `SavedAnswerScreen` (`components/screens/SavedAnswerScreen.tsx`). Otherwise it falls straight to `void ask(item.question, depth)`, a full fresh run.

## Every fallback condition, checked against the screenshot

1. `item.hasSavedAnswer !== true`: this is the actual cause. See below.
2. No `item.traceId`: not the cause here. `traceId` is set on the local row as soon as `createRun` resolves (App.tsx around line 1381), which happens before the row could ever be clicked from a landed answer.
3. No `token` (guest): not the cause. The screenshot shows a signed-in shell (account menu, full rail, no guest allowance banner).
4. `fetchHistoryAnswer` failing: not the primary cause, though it is also a fallback path and can't be ruled out without a network trace. The `hasSavedAnswer` gap below is sufficient on its own to explain the report.

## Root cause

`hasSavedAnswer` is only ever set in one place: `mergeServerHistory` (App.tsx line 316), which maps `item.has_saved_answer === true` from `GET /v1/history` rows. `mergeServerHistory` is only called from one effect (App.tsx line 674), gated on `[token]`, so it runs once per sign-in / token change, not again afterward.

A row created by asking a question in the current tab is pushed with `{ id: entryId, question }` only (App.tsx line 1233), no `hasSavedAnswer` field at all, so it is `undefined`. `traceId` is attached a few lines later once the run is admitted, but `hasSavedAnswer` is never attached to that same local row for the rest of the tab's life; nothing re-fetches `/v1/history` or re-runs `mergeServerHistory` after a run lands and its answer is captured server-side.

So: any search asked in this tab session, then clicked again from the rail before a reload or a fresh sign-in, has `hasSavedAnswer === undefined`, fails the `=== true` check, and re-runs. This matches the screenshot exactly, the row that just answered (BRCA1) is the active, highlighted, top-of-rail item, i.e. a row created in this same session. A row restored from a previous session (after reload/sign-in, via `mergeServerHistory`) would carry `hasSavedAnswer: true` and would correctly show the saved answer, so item 10.2 does work, just not for anything asked since the page loaded.

## Deploy check

`git log --oneline origin/develop` and `git merge-base --is-ancestor` confirm both `1fd16e2` and `a98a019` are ancestors of `origin/develop`. The deployed commit includes 10.2's code; this is a logic gap in that code, not a missed deploy.

## Smallest fix

In the `ask` success path (App.tsx, near line 1381 where `traceId` is attached), also set `hasSavedAnswer: true` on that same row once the run lands and Section 16's capture write is expected to have landed (e.g. on the write step completing, or optimistically once `view.landed` is true for a signed-in run), matching what `mergeServerHistory` would eventually report from the server. Alternatively, re-run the `GET /v1/history` fetch and `mergeServerHistory` after a run finishes, not only on token change.

No live-data check is needed to settle this; the code path is deterministic and traced above.
