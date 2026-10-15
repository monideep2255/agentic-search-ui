# Card 112 adversary report

Fresh-context adversary, 2026-10-09, checkout detached at c37c5f1f, base develop d0319502. Probes are vitest files run against the real App and the real fetchHistory with fetch stubbed, kept outside the checkout.

## Findings

### A-112-01: a re-ask that fails to start leaves a row that is never on the server, and every retry adds another
- Severity: minor
- What: `ask` now unshifts a new row and removes nothing. When `createRun` fails (network error, server error), the row stays at the top with no second line and no trace id. Each retry of the same question adds one more. The server has no row for any of them, so a reload removes them. The build's claim "the list before a reload now matches the list after one" does not hold for this case. Before card 112 the text filter collapsed repeated attempts into one row (while also hiding the real earlier rows, which was the bug).
- Reproduction: probe `P1` (real App, real fetchHistory, fetch stubbed with the four-row history of `App.historyAfterStop.test.tsx`, `createRun` rejecting with `Error("network down")`). Sign in, click the restored "No answer saved · Oct 8" row three times, waiting for the "network down" banner each time. Rail rows observed: `["Q", "Q", "Q", "Q 21 sources cited · Oct 9", "EGFR 55 sources cited · Oct 9", "Q No answer saved · Oct 8", "Q 21 sources cited · Oct 7"]`, 7 rows. `GET /v1/history` after a reload returns 4.
- What a person sees: on a bad connection, three bare copies of the question pile up on top of "Your searches", none of which is a search they can open as an answer, and all three vanish on reload.
- NOT FIXED

### A-112-02: opening an older saved search highlights the newest row of the same question, not the one opened
- Severity: minor
- What: the rail's highlighted row (`activeId`) is still `history.find((item) => item.question === searchView.question)`, first text match. Card 112 now keeps the earlier rows after a re-ask, so in one session a person can re-ask, then click an older saved row of the same question. The saved answer shown is the right one (`fetchHistoryAnswer` is called with that row's own trace id), but the highlight sits on the top row, a different search. The build's "Left as it is" says "nothing new reaches a person"; before card 112 the older rows were gone after a re-ask, so this click was not possible in that session.
- Reproduction: probe `P2`. Sign in, type the BRCA1 question, let it answer (`answerAndDone`), then click the restored "21 sources cited · Oct 7" row (trace `t-answered-1`). `fetchHistoryAnswer` calls: `["t-answered-1"]`. Rail row classes: the active class `css-1hjyd8n` is on row 0, "Q 1 tool call · 2 sources cited from 1 layer" (this tab's answered re-ask); the Oct 7 row carries the inactive class `css-1s9wqtc`. Same in probe `P9` after a confirmed stop: opening the Oct 7 row leaves the highlight on the top "No answer saved · Oct 9" row.
- What a person sees: they open their Oct 7 answer and the list marks today's search as the one on screen.
- NOT FIXED

### A-112-03: the same trace twice in a history response gives two rows with one React key
- Severity: minor (pre-existing, not introduced by card 112; unsure whether the server can send it)
- What: `mergeServerHistory` removes server rows that match a local trace id but does not remove a duplicate within the server list itself, so both copies become rows with `id` equal to the same trace id.
- Reproduction: probe `P7`, history `items` = the four rows plus `t-answered-2` again. Rail shows 5 rows, the last a second "Q 21 sources cited · Oct 9"; React logged 1 "Encountered two children with the same key" error.
- What a person sees: one search listed twice; with the shared key React may reuse or drop the wrong row on later updates.
- NOT FIXED

### A-112-04: the stopped row's date comes from the browser clock at the ask, not from what the server stores, so it can show a different day than a reload
- Severity: minor (unsure how often it reaches a person; it is in the new card 112 effect)
- What: the new effect builds the date from `runStartedAt`, the browser's `Date.now()` when the question was sent. Its comment says this is "the same instant the server stores as `asked_at`". It is not: `asked_at` is `interactions.created_at` (`data/models.py`, `server_default=now()`), and the row is inserted by the capture in the run's `finally` block, after the run ends or is stopped, on the server's clock. So the two differ by the run's length plus any browser clock error. A search sent before local midnight and stopped after it, or any search from a browser whose clock is off by a day, reads one date now and another after a reload.
- Reproduction: probe `P20`. `Date.now` stubbed to local 2026-01-01 23:59:58 only for the ask, then Stop and the server's `cancelled` reply. Top rail row: "No answer saved · Jan 1". The server would store the time it wrote the row (here, today), and a reload shows that date.
- What a person sees: rarely, a stopped search that says "Jan 1" and then "Jan 2" (or the real date) after a reload.
- NOT FIXED

### A-112-05: a guest who stops a search and then signs in keeps a bare row for it, while the server already says "No answer saved"
- Severity: minor (depends on the sign-in carrying the guest's searches into the account, which `_migrate_guest_session` is described as doing; not checked against the backend)
- What: the new effect is gated on `signedIn` and runs only while the stopped run is on screen. A guest's stop is never labelled, and sign-in sets the view to home, so the effect returns early. `mergeServerHistory` then drops the server's own row for that trace (it matches the local trace id) and keeps the bare local one.
- Reproduction: probe `P14`. Signed out, ask the BRCA1 question (guest run `run-G`), Stop, server sends `cancelled`, "Search stopped" shown. Log in; history returns `run-G` with `has_saved_answer: false` plus the four rows. Rail: top row "Q" with no second line; the server's "No answer saved · Oct 9" for `run-G` is not shown. After a reload it is.
- What a person sees: the search they stopped just before signing in has no "No answer saved" line until they reload.
- NOT FIXED

### A-112-06: a run that fails (no Stop) still reads like an answered search, "2 sources cited", and opening it tries to load a saved answer that does not exist
- Severity: minor (pre-existing, not introduced by card 112; the sibling of the card's cause 2, and it contradicts the build's "the list before a reload now matches the list after one")
- What: `useRunView` treats a fatal error as `landed`, so the meta effect writes the run's counts and the item 12.13 effect sets `hasSavedAnswer: true` on a failed run. The server saves no answer for it (`capture.py`, only saveable outcomes), so after a reload the same row reads "No answer saved".
- Reproduction: probe `P11`. Sign in, ask the BRCA1 question, records arrive, the server sends a fatal error with `error_class: "unexpected"` and no Stop. Top row: "Q 1 tool call · 2 sources cited from 1 layer". Clicking it calls `fetchHistoryAnswer(token, "run-A")`, which the real server answers 404, then falls back to a fresh search.
- What a person sees: a failed search listed like an answered one; clicking it shows a loading screen, then charges a new search.
- NOT FIXED

### A-112-07: a Stop followed by a re-ask before the server replies leaves the stopped row bare, while a reload shows "No answer saved"
- Severity: unsure (the build chose to leave a row with no server reply as it is; filed so the choice is visible)
- What: the re-ask resets the stop and closes the old stream, so the server's `cancelled` reply for the first run is never read and the first row gets no second line. The server records that run as stopped with no saved answer.
- Reproduction: probe `P3`. Sign in, ask the BRCA1 question (`run-A`, `stopRun` pending), press Stop, then click the restored "No answer saved · Oct 8" row before any reply (`run-B`). The `cancelled` reply sent on `run-A`'s stream afterwards is ignored. Rail: row 1, `run-A`, reads "Q" with no second line, through `run-B`'s answer. A reload would show it as "No answer saved · Oct 9".
- What a person sees: until they reload, the search they stopped looks like one still running or one that never finished.
- NOT FIXED

## Probes that held

- Stop pressed, then the answer finished first (card 59, `P4`), also with a stray `cancelled` after `done` in the same chunk (`P16`): the row reads "1 tool call · 2 sources cited from 1 layer", never "No answer saved", and the answer stays on screen.
- Stop, then a non-cancel fatal error (`P13`): "No answer saved · Oct 9", which matches what the server saves.
- Stop request fails (`P5`): "Search stopped" shown, row left bare, as the build says.
- Stop double click (`P15`): one `stopRun` call.
- Run again after a confirmed stop, stopped again (`P10`): two rows, each "No answer saved · Oct 9"; no other row of the question relabelled.
- Follow-up with the same question text, stopped (`P18`): only the new row relabelled; the answered row above it keeps its counts.
- Opening rows (`P9`): a saved restored row fetches its own trace id (`t-answered-1`); the stopped local row starts a new search, not a saved-answer fetch.
- Duplicate React keys: none across all probes except the server-side duplicate in A-112-03.

## Verdict

PASS against card 112's stated goal: earlier rows of a re-asked question stay, and a confirmed stop reads "No answer saved · <date>" on that row and no other. Nothing above sits inside the fix in a way that breaks that goal, but A-112-01 (phantom rows on failed retries) and A-112-04 (the date source in the new effect) are inside this card's own change, and A-112-02 is reached more often because of it. The build's claim "the list before a reload now matches the list after one" is not true in general (A-112-01, A-112-04, A-112-05, A-112-06, A-112-07).

Verified by my own probes (vitest, real App, real `fetchHistory`, `fetch` stubbed): every reproduction above. Read only, not run: that `interactions.created_at` is set at capture time after the run (A-112-04), that guest sign-in moves the guest's searches into the account (A-112-05), and that the server saves no answer for a failed run (A-112-06). No live run was made.
