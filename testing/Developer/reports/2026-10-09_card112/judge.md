# Card 112 judge report

Judge, fresh context, branch fix/card112-history-after-stop at c37c5f1f, base develop d0319502. Findings are appended as established.

## Findings

### J-112-01: the stopped row's date comes from the ask's start, the server's from the capture write, and the comment says they are the same instant
- Severity: minor
- What: the new effect in `frontend/src/App.tsx` builds the stopped row's date from `runStartedAt` (set by `ask` at `Date.now()` before `createRun`), and its comment says this is "the same instant the server stores as `asked_at`". It is not. `GET /v1/history` returns `asked_at=row.created_at` (`feedback/history.py:315`), and `Interaction.created_at` is `server_default=now()` (`data/models.py:191-192`), written by `_capture_interaction` in `run()`'s `finally`, that is after the stop lands, not when the question was asked.
- Reproduction: read, not run. `git grep -n "created_at" -- src/system_03_search_agent/feedback/` shows no writer setting `created_at`; the column default is `now()` at insert. A search asked at 23:59:50 local and stopped at 00:00:10 reads "No answer saved · Oct 9" on screen and "No answer saved · Oct 10" after a reload.
- Why it matters: the date differs only across a local midnight (or with a skewed client clock), so the visible effect is rare. The comment, though, states a false fact as the reason the screen and the reload agree, which is the F-4.13-FV-02 hazard: the next reader stops checking there. Either take the date at the cancelled reply, or correct the comment.
- NOT FIXED

### J-112-02: with a full server history, the list before a reload is longer than after it, so "the list before a reload now matches the list after one" does not hold
- Severity: minor
- What: `GET /v1/history` returns at most 20 rows (`DEFAULT_LIMIT = 20`, `feedback/history.py:84`; `fetchHistory` passes no limit). `ask` now only ever adds a row, so a re-ask on an account with 20 stored searches puts 21 rows on screen, and a reload shows 20. Before card 112 a re-ask of a listed question removed at least one row, so a re-ask could not grow the list (a brand new question already could, on develop too).
- Reproduction: own probe (temporary vitest file, removed), real `fetchHistory`, `fetch` stubbed. Server history of 20 rows, one of them "Which diseases are associated with BRCA1?". Asked that question, pressed Stop, sent the `cancelled` reply. Rail rows before reload: 21. Remounted with the server's newest 20 (the stopped run plus the first 19): 20 rows. Output: `A before reload count 21`, `A after reload count 20 missing after reload: [ 'Q19 question3 sources cited · Oct 7' ]`. The other 20 rows matched in text and order.
- Why it matters: the person sees one more row before a reload than after; the oldest row disappears on reload. Small, and the same class already existed for new questions, but it contradicts the build report's claim and the brief's "list equals what the screen showed before reload".
- NOT FIXED

### J-112-03: the rail highlights the newest row of a question, not the row that was opened
- Severity: minor
- What: `activeId` in `frontend/src/App.tsx` (the `HistoryRail` props) is `history.find((item) => item.question === searchView.question)?.id`, first match by question text. Card 112 keeps every row of a re-asked question in the tab, so opening an older row's saved answer highlights the newest row of that question, a different run. The brief asks for highlight by id; it is by text. The build report names this under "Left as it is" and says nothing new reaches a person; the state was reachable on develop only when the server history itself held duplicates, and after this change every re-ask in a session creates it.
- Reproduction: own probe. Signed in, asked BRCA1 and stopped (row r1), re-asked it from the rail (r2), merged a server history holding r1, t-answered-2, t-egfr and t-answered-1, let r2 land. Clicked the fifth row (t-answered-1, "7 sources cited · Sep 30"): `fetchHistoryAnswer` was called with `t-answered-1` (correct), and the emotion classes of the five rows were `["css-1hjyd8n","css-1s9wqtc","css-1s9wqtc","css-1s9wqtc","css-1s9wqtc"]`, that is the highlight sat on row 1 (r2, "1 tool call · 2 sources cited from 1 layer"), not on the opened row 5.
- Why it matters: a person reading a saved answer from Sep 30 sees the rail mark today's search as the one on screen. It states which run is shown and states it wrongly, the F-4.13-A-07 "rail states something about a past run" class, though only through highlight. Keying `activeId` on the opened row's id closes it.
- NOT FIXED

### J-112-04: no shipped test pins "a stop whose request failed leaves the row as it was"
- Severity: minor
- What: the build report names the server-confirmation guard (`stopConfirmed` requires a fatal error event) as the rule that keeps a failed stop's row unchanged. No test in the suite pins it. Replacing `stopConfirmed` with plain `stopped` writes "No answer saved" onto a row whose stop never reached the server, a run the server may still answer and save, and the whole suite stays green.
- Reproduction: mutation in `frontend/src/App.tsx`, `const stopConfirmed = stopped;`. `npx vitest run`: 614 passed, 2 failed, the two failures both in my own temporary probe file (the failed-stop probe D, and probe A which fails on J-112-02 anyway). Every one of the 613 shipped tests passed. Probe D: `stopRun` rejected once, Stop pressed, run read "Search stopped", rail expected `[QUESTION]`. Green on the branch, red under the mutation. File restored with `git checkout`, SHA-256 `750a5ba9...` matches.
- Why it matters: the guard is the only thing standing between this change and a fabricated "No answer saved" on a run that answered, the F-4.8-J-01 class. A later edit can remove it with every gate green. The brief asked for this behaviour; the behaviour is right today, unguarded tomorrow.
- NOT FIXED

### J-112-05: the trace id tagging change (by row id, not by question text) is not pinned by any test
- Severity: minor (unsure of user impact)
- What: card 112 changed `ask`'s trace id tagging from `item.question === question && item.traceId === undefined` to `item.id === entryId && item.traceId === undefined`. Reverting it passes every test that touches history. Under the revert, an older row of the same question with no trace id (an ask whose `createRun` failed) would also be tagged with the new run's id, so two rows would carry one `traceId`. I did not build a probe for the visible effect; by reading, `onOpen` only uses `traceId` with `hasSavedAnswer`, which is written by row id, so the visible effect looks small.
- Reproduction: mutation in `frontend/src/App.tsx` as above. `npx vitest run src/App.historyAfterStop.test.tsx src/App.test.tsx src/App.historyNoAnswer.test.tsx`: 42 passed, 0 failed. Restored with `git checkout`, SHA-256 matches.
- Why it matters: the build report lists this as one of the three changes; nothing holds it in place.
- NOT FIXED

## Verified by own probes versus read

Own probes (a temporary vitest file through the real `fetchHistory` with `fetch` stubbed, moved out of the checkout afterwards):

- Re-ask of a restored question from the rail adds a new row on top, earlier rows stay: yes.
- The landing run's meta goes only onto its own new row; with the seeding fetch landing mid-stream (the F-4.13-FV-01 order) every restored row of the same question kept its own text: yes, `landed.slice(1)` equalled `midStream.slice(1)`.
- Ids unique after two re-asks, two confirmed stops and a late merge with server history holding one of the local runs: no duplicate-key warning, the merged local run was not duplicated (6 rows, as expected).
- Each row opens its own run: clicking t-answered-1, t-answered-2 and the local answered row called `fetchHistoryAnswer` with `t-answered-1`, `t-answered-2` and the local run id; clicking the stopped row re-asked its own question.
- After a confirmed stop, the stopped row reads "No answer saved · Oct 9" and every earlier row stays; after a remount with the server's own list, rows, text and order matched except the J-112-02 overflow row.
- A stop whose request failed leaves the row as bare question text: yes.
- Highlight: by question text, wrong row after opening an older one (J-112-03).

Mutations: restoring the filter turned 6 tests red (the two new, the two updated F-4.13 tests, two probes); disabling the stopped-row effect turned 3 red (one shipped, two probes); dropping the server-confirmation guard turned only my probe red (J-112-04); reverting the tagging matcher turned nothing red (J-112-05). Every mutation restored with `git checkout`, SHA-256 of `App.tsx` checked each time.

Gates run by me: `npx vitest run` 68 files, 613 passed; `npx tsc --noEmit -p .` exit 0; `npm run build` built (chunk size warning only); `ruff check` from the root, all checks passed.

Read only, not probed: guests (the effect is gated on `signedIn`, the rail is not shown to a guest; a guest's rows still enter `history` and survive sign-in, as on develop), the follow-up panel (a follow-up goes through the same `ask`, its only change is that no row is filtered), the J-112-01 midnight case, and StrictMode.

Inside this phase's own fix: J-112-01 (the new effect's date and its comment) and J-112-04 and J-112-05 (the new code's test gaps) sit in card 112's own change. All three are minor; none is a reachable wrong statement today.

## Verdict

MERGE. The card's behaviour holds under my own probes, and every F-4.13 failure mode (A-07, RV-01, FV-01) stays closed. Five minor findings are filed, none blocking. Cheapest follow-ups: pin the failed-stop rule with a test (J-112-04), correct the date comment (J-112-01), key the highlight on the opened row's id (J-112-03).
