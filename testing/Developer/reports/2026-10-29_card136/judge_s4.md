# Judge report, card 136 slice S4 (pull request 316), round 1

Branch fix/card136-show-older-searches at 4938a8e2. Findings are appended as they are established.

## Findings

### Evidence E1: security through the real app, real guest tokens, local database (own probes)

Probe: FastAPI `TestClient(app)`, two guests minted by `POST /auth/guest`, 45 rows each seeded on the SAME instants.

- Owner A walks its history: pages `[(20, True), (20, True), (5, False)]`, every row once, in order, no row of B's.
- A's token with B's cursor: `200 {"items":[],"count":0,"omitted_count":0,"has_more":false}`; with a never-existing cursor: byte-identical body, no header differs (`header diff: {}`).
- Timing, 400 shuffled requests each: stranger cursor median 3.923 ms (p10 3.274, p90 4.810), unknown cursor median 3.899 ms (p10 3.285, p90 5.408). No measurable difference locally.
- No token, garbage token, expired guest token (signed with the real key, exp two days ago): `401 {"detail":"invalid or expired credentials"}`. A validly signed token for a guest with no `guest_sessions` row: 401 `guest_session_revoked`. A malformed cursor without a token is 401, not 422, so validation never runs for an anonymous caller.
- Validation: empty, 65 chars, 65 emoji are Pydantic 422s; `%00`, `a%00b`, `%0A`, `%09`, `%7F` are 422 with "`before` must be the `trace_id` of one of your own searches, as returned in `items`"; `' OR 1=1--`, `%`, `_`, `*`, `\`, path traversal, ideographic space, RTL override, C1 `%C2%85`, a lone surrogate `%ED%A0%80`, `%FF%FE`, an upper-cased own id, own id with a leading or trailing space: all `200` empty page, identical to unknown. Duplicate `before` (same or different values): 422 naming the parameter. `limit=0`, `51`, `abc` with a cursor: 422. `before=<own>&limit=1` gives one row and `has_more: true`.
- SQL: the cursor lookup and page query are SQLAlchemy expressions (`feedback/history.py` `select(...).where(Interaction.owner_id == owner_id, Interaction.trace_id == before)`), no string building.

### J-136S4-01: After the 12-minute token rotation picks up a search asked elsewhere, "Show older searches" is a dead button and the oldest searches can never be reached
- Severity: blocking. Inside this phase's new code (the cursor choice in `showOlderSearches`).
- What: `frontend/src/App.tsx:775` to `776` picks the cursor as the LAST row in the rail whose `id === traceId`. `mergeServerHistory` (`App.tsx:336` to `351`, unchanged) APPENDS any server row not already shown to the END of the list. The seeding effect (`App.tsx:738` to `756`) re-runs on every token change, and the token rotates every 12 minutes (`App.tsx:1060` to `1082`). So a search asked in another tab or on another device lands at the bottom of the rail as a restored row, and becomes the cursor. The server then answers with the 20 rows just below that newest search, every one already shown, so `mergeServerHistory` adds nothing, `has_more` stays true, and the cursor is the same row next press. Forever, until a reload.
- Reproduction (own probe, temporary file `frontend/src/App.judgeProbe136.test.tsx`, deleted after; real `fetchHistory`, keyset `fetch` stub, fake timers): 45 server rows, sign in, press "Show older searches" once (rail 40 rows), the server gains one newer row `t-new` ("Other device question"), advance 12 minutes so `refreshSession` rotates the token. Observed: `P1 rail after rotation: first Past question 0 | last Other device question | length 41`, then `P1 cursor sent: t-new | rail length after press 41 | control still shown true`, then `P1 second press cursor: t-new | rail length 41`; assertion `expected [ 'Past question 0', …(40) ] to include 'Past question 44'` fails. The same holds without a first press: the cursor is the appended newest row from the start.
- What a person sees: someone signed in on a laptop and a phone asks a question on the phone; within 12 minutes the laptop's rail shows that question at the very bottom, below their oldest loaded search, and "Show older searches" stays on screen and does nothing however often they press it. Their oldest searches cannot be reached without reloading. The bottom placement alone pre-dates this card (develop appends the same way); the dead control and the unreachable rows are new.
- NOT FIXED

### J-136S4-02: Asking a search while the first older page is loading makes one loaded search vanish from the list
- Severity: major. Inside this phase's new code (the trim gate at `App.tsx:1529` to `1535` and `historyPagedOlder`, set only when the page lands at `App.tsx:785`).
- What: while the first older page is in flight `historyPagedOlder.current` is still false, so a new ask trims the rail to 20 and drops its last row, which is exactly the cursor row the in-flight request was sent with. The page that lands holds only rows strictly older than that cursor, so the dropped row is never brought back, and after the merge `historyPagedOlder` is true, so nothing re-offers it.
- Reproduction (own probe P2): 45 rows, sign in, rail `Past question 0..19`; hold the older-page response; press "Show older searches" (cursor `t-19`); type and submit "A brand new question"; release. Observed: `P2 cursor t-19 length 40 has 19: false`; diff against the expected list `- "Past question 19"`.
- What a person sees: they press "Show older searches", ask a question before it finishes, and "Past question 19" (a search that was on screen a second ago) is gone from the list, with the list otherwise looking complete. The acceptance's "never makes older ones I loaded disappear" fails for that row until a reload. Window is the length of one fetch, so it is a race, but a real one on a slow connection.
- NOT FIXED

### Evidence E2: paging boundaries through the real app and database (own probe)

Walks following `items[-1].trace_id` with a real guest token, `(count, omitted_count, has_more)` per page:

- 0 rows `[(0, 0, False)]`; 1 row `[(1, 0, False)]`; 19 `[(19, 0, False)]`; exactly 20 `[(20, 0, False)]`; 21 `[(20, 0, True), (1, 0, False)]`.
- 45 rows on five shared timestamps, `limit=7`: 45 seen, 45 unique, the exact seeded set.
- A row withheld by the per-row guard (question of 2500 characters) at newest-first index 19: page 1 `count 19 omitted 1 has_more True`, walk `[(19, 1, True), (5, 1, False)]`. `has_more` survives the withheld row; see J-136S4-03 for the count.
- A NULL-owner row's `trace_id` as cursor: empty page, identical to unknown.

### Evidence E3: backward compatibility against origin/develop's own code (own probe)

`git archive origin/develop src` into the scratchpad, the same requests with the same guest token and database through both apps. Every response equals develop's once the additive `has_more` key is removed: `''`, `?limit=5`, `?limit=50` (200); `?limit=51`, `?limit=0`, `?limit=5&limit=6`, `?limit=abc` (422, identical bodies); no token (401). MCP `list_history(owner, 7)`: same trace ids, same order. The one difference: `?before=x` was ignored on develop (newest page) and is now an empty page, which is the feature.

### J-136S4-03: A withheld row is counted twice in `omitted_count` across two pages
- Severity: minor. Disclosed by the builder in "Limits stated"; filed so it is tracked.
- What: the cursor the client sends is the last VISIBLE row, so the next page re-reads the withheld row and withholds it again. `omitted_count` summed over a walk overstates.
- Reproduction: E2's walk with one 2500-character question: `[(19, 1, True), (5, 1, False)]`, one withheld row, total omitted 2.
- What a person sees: nothing today; the web app does not read `omitted_count`. An API caller summing it would report one more hidden search than exists.
- NOT FIXED

### Evidence E4: backend mutations, own runner (each applied, the four related test files run, file restored with `git checkout --`)

Baseline: `127 passed, 2 warnings in 8.44s` (`test_history.py`, `test_history_endpoint.py`, `test_saved_answer_endpoint.py`, `mcp/test_parity_tools.py`).

| Mutation | Result | First red test |
|---|---|---|
| M1 cursor lookup without owner filter | RED, 2 failed | `test_another_owners_cursor_returns_nothing_of_theirs_or_ours` |
| M2 page query without owner filter | RED, 13 failed | `test_owner_scoping_returns_only_the_callers_own_rows` |
| M3 keyset on `created_at` alone | RED, 1 failed | `test_ties_on_one_timestamp_split_cleanly_across_page_boundaries` |
| M4 keyset `<=` | RED, 7 failed | `test_older_pages_reach_every_row_once...[21]` |
| M5 `has_more` as `>=` | RED, 2 failed | `...[20]` |
| M6 `has_more` always False | RED, 5 failed | `...[21]` |
| M7 fetch `limit` rows, not `limit + 1` | RED, 5 failed | `...[21]` |
| M8 unknown cursor returns the newest page | RED, 2 failed | `test_another_owners_cursor...` |
| M9 no control-character check | RED, 5 failed | `test_a_malformed_cursor_is_refused_before_any_query[newline]` |
| M10 NUL only | RED, 5 failed | `[newline]`, `[delete]` |
| M11 duplicate `before` allowed | RED, 1 failed | `test_a_duplicate_before_is_refused` |
| M12 no `max_length` | RED, 1 failed | `test_an_over_long_before_is_refused_before_any_query` |
| M13 no `min_length` | RED, 1 failed | `test_an_empty_before_is_refused` |
| M14 endpoint drops `has_more` | RED, 2 failed | `test_has_more_is_true_when_an_older_row_exists` |
| M15 `has_more` cleared when a row is withheld | RED, 1 failed | `test_has_more_survives_a_withheld_last_row` |
| M16 cursor `ValueError` becomes a 500 | RED, 5 failed | `test_a_control_character_in_before_is_a_422_never_a_500` |
| M17 422 detail prefixed with the internal `ValueError` text | GREEN, 127 passed | none (J-136S4-04) |
| M18 endpoint ignores `before` | RED, 9 failed | `test_before_reaches_the_read_function...` |
| M19 a stranger's cursor raises (distinguishable) | RED, 2 failed | `test_a_strangers_cursor_and_an_unknown_one_answer_identically_over_http` |

### J-136S4-04: The 422 text for a malformed cursor is not pinned by any test
- Severity: minor.
- What: `app.py:1074` to `1085` promises the 422 "says what to send and nothing about whether any row exists". No test asserts the detail string, so a change that adds internal text to it stays green.
- Reproduction: mutation M17, detail built as `f"{error} " "`before` must be ..."`: `127 passed`. Today's text leaks nothing (E1: "`before` must be the `trace_id` of one of your own searches, as returned in `items`").
- What a person sees: nothing today. A regression that echoed internal or row-dependent text into the error would ship unnoticed.
- NOT FIXED

### Evidence E5: frontend mutations, own runner, against the builder's tests (`src/App.historyPaging.test.tsx`, `src/lib/api.fetchHistory.test.ts`; baseline `Tests 16 passed (16)`)

| Mutation | Builder's tests |
|---|---|
| F1 sign-out AND token change stop aborting the in-flight older page | GREEN, 16 passed (J-136S4-05) |
| F2 sign-out does not reset `historyPagedOlder` | GREEN, 16 passed (J-136S4-06) |
| F3 sign-out does not reset `historyHasOlder` | GREEN, 16 passed (J-136S4-06) |
| F4 `then()` aborted guard and token-change abort both removed | GREEN, 16 passed (J-136S4-05) |
| F5 rail ignores `hasOlder` | RED, 4 failed |
| F6 older fetch without `before` | RED, 4 failed |
| F7 `historyPagedOlder` never set | RED, 1 failed |
| F8 trim does not turn the control on | RED, 1 failed |
| F9 older page's `has_more` not read | RED, 3 failed |
| F10 `fetchHistory` drops `before` | RED, 5 failed |
| F11 `has_more` read as truthy | RED, 1 failed |
| F12 failed load shows nothing | RED, 1 failed |
| F13 seed refetch overrides `hasOlder` after paging (guard at `App.tsx:748` removed) | GREEN, 16 passed (J-136S4-06) |
| F14 control not disabled while loading | GREEN, 16 passed (J-136S4-06) |
| F15 cursor is the first row, not the last | RED, 4 failed |
| F16 re-ask after paging still trims to 20 | RED, 1 failed |

My own probe P3 (sign out while an older page is held in flight, release it, sign straight back in, expect exactly the newest 20 and a fresh control) passes on the branch and goes RED under F1, so the abort is load-bearing and the property is testable.

### J-136S4-05: No test guards "a second identity never inherits the first one's older page"
- Severity: major. The control is new in this phase; the builder's account names it (`App.tsx:933`, `:754`) but its mutation table has no row for it.
- What: removing the abort on sign-out and on token change (F1), or removing the `if (controller.signal.aborted) return;` guard with the token abort (F4), leaves every builder test green.
- Reproduction: E5 rows F1 and F4: `Tests 16 passed (16)`. Under F1 my probe P3 fails: the held older page lands after sign-out and the rail on the next sign-in is not the newest 20.
- What a person sees: today nothing; the code is right. On a shared computer, a later change that dropped the abort would show the next person searches from the account that just signed out, and nothing in CI would say so.
- NOT FIXED

### J-136S4-06: Four smaller behaviours of the control have no test
- Severity: minor.
- What and reproduction (E5): F2 (`historyPagedOlder` not reset on sign-out, so the next account's re-asks never trim), F3 (`historyHasOlder` not reset on sign-out), F13 (after the person reaches the end, the 12-minute token refetch brings "Show older searches" back; pressing it then answers an empty page and the control goes again) and F14 (the control stays pressable while a page loads) each leave `Tests 16 passed (16)`.
- What a person sees: nothing today. F13's regression would be a control that reappears every 12 minutes and does nothing visible when pressed.
- NOT FIXED

### Evidence E6: CI gates and the touched tests, run by the judge

- `ruff check .`: `All checks passed!`
- `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2's command): exit 0.
- `npx tsc --noEmit -p .` from `frontend/`: exit 0.
- `npx vitest run src/App.historyPaging.test.tsx src/lib/api.fetchHistory.test.ts src/components/answer/ src/App.test.tsx`: `Test Files 8 passed (8)`, `Tests 96 passed (96)`.
- Backend related files: `127 passed, 2 warnings in 8.44s`.
- Query plan on the local database (149,922 interaction rows): the page query is `Index Scan using idx_interactions_owner_id_created_at_id` with `Index Cond: ((owner_id = ...) AND (ROW(created_at, id) < ROW(...)))`; the cursor lookup is `Index Scan using interactions_trace_id_key` with `Filter: (owner_id = ...)`.

## Verdict

FAIL, blocking J-136S4-01.

The server half is sound: owner scoping on both queries, parameterised SQL, bounded limit and cursor, no distinguishable answer for a stranger's cursor, all verified with my own probes and 18 of 19 mutations red. The web half fails the acceptance "I can keep going until there are none left": a search asked in another tab or on another device turns the control into a dead button within 12 minutes (J-136S4-01), and a search asked while the first older page loads drops a loaded row (J-136S4-02). Both sit inside this phase's new code.

Verified with my own probes: E1 to E6, J-01, J-02, J-03, J-05 (P3 under F1), the mutation tables. Read only, not run: the phone drawer staying open on a press (FollowUp comment), the visual style of the control, the builder's EXPLAIN claim beyond my own plan check.

