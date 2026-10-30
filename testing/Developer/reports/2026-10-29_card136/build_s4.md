# Card 136 slice S4: show older searches

What the person sees now: when they have more than 20 searches, "Show older searches" sits at the foot of "Your searches". Each press loads the next 20 older ones, and the control goes when there are none left. A new search still goes on top, and once they have loaded older searches, asking a new one never makes any of them disappear. Every page is their own searches only, a guest's included.

## Table of contents

- [Change](#change)
- [How owner scoping and the cursor work](#how-owner-scoping-and-the-cursor-work)
- [Choices made](#choices-made)
- [Tests](#tests)
- [Mutations](#mutations)
- [Limits stated](#limits-stated)
- [Fix round](#fix-round)
- [Fix round, left](#fix-round-left)

## Change

| File | What changed |
|---|---|
| `src/system_03_search_agent/feedback/history.py` | New `list_history_page(owner_id, limit, before=None)` returning `HistoryPage(entries, has_more)`. Fetches `limit + 1` rows to learn `has_more`. `list_history` keeps its two-argument shape and returns `list_history_page(...).entries`, so the MCP tool is unchanged |
| `src/system_03_search_agent/adapters/web_sse/app.py` | `GET /v1/history` takes an optional `before` query parameter and returns an additive `has_more: bool = False`. A duplicate `before` is refused like a duplicate `limit` |
| `frontend/src/lib/api.ts` | `fetchHistory` sends `before`, encoded, and reads `has_more` only when it is a real `true` |
| `frontend/src/App.tsx` | `showOlderSearches` fetches the page older than the rail's last server row and appends it through `mergeServerHistory`. The re-ask trim to 20 now applies only until an older page is loaded |
| `frontend/src/components/answer/FollowUp.tsx` | `HistoryRail` shows "Show older searches" when `hasOlder`, "Loading older searches…" while a page loads, and "Older searches did not load. Try again." after a failure |

No migration, no stored data, no auth code. The existing alembic 0009 index `(owner_id, created_at DESC, id DESC)` serves the new query: `EXPLAIN` on the local database shows one `Index Scan using idx_interactions_owner_id_created_at_id` with both the owner equality and the row comparison in its `Index Cond`.

## How owner scoping and the cursor work

Server:

- The owner filter is on both queries. The cursor lookup is `WHERE owner_id = caller AND trace_id = before` (`feedback/history.py:381` to `382`); the page query is `WHERE owner_id = caller` (`:374`), applied before the keyset condition is added.
- A cursor that is another person's search, or one that never existed, resolves to no row, and the function returns `HistoryPage(entries=[], has_more=False)` (`:385` to `:386`). The HTTP response is byte-identical for both causes, so it never confirms that someone else's search exists.
- Older rows are `(created_at, id) < (cursor's created_at, cursor's id)` (`:388` to `:389`), the same two columns in the same order as the `ORDER BY` and the index. `id` is unique, so two searches on one timestamp land on exactly one page each.
- `next_before` (fix round) is the `trace_id` of the oldest row the page query read, the `limit`th, when a `limit + 1`th row exists, else null (`feedback/history.py:422`). `has_more` is a property derived from it (`:264`), so the two cannot disagree. Both come from the database rows, before the endpoint's per-row guard, so a withheld row never hides or stalls an older page.

Cursor validation:

- Length: `FastAPIQuery(None, min_length=1, max_length=64)` (`adapters/web_sse/app.py:1070`), 64 being the write path's own `trace_id` bound. Empty or over-long is a 422 that names the bound, before any query.
- Control characters, NUL above all: `_check_cursor` (`feedback/history.py:257` to `:273`) raises `ValueError` before a session opens. PostgreSQL text cannot hold NUL and the driver would raise, so this is what keeps it from being a 500. The endpoint turns it into a 422 that says what to send and nothing about whether any row exists (`app.py:1074` to `:1085`).
- Duplicates: `_SINGLE_OCCURRENCE_HISTORY_PARAMS = ("limit", "before")` (`app.py:990`, used at `:1016`).
- `limit` is unchanged: 1 to 50, a 422 above 50 (the owner's decision of 2026-08-27).

Web:

- The cursor is the server's own `next_before`, stored from this session's first newest page and from each older page (`historyCursor`, `App.tsx:533`), never read off the rail (fix round, J-136S4-01). The token rotation's refetch never moves it. The server scopes it anyway, so a wrong cursor can only cost an empty page.
- An older page in flight is aborted, and never merged, on sign-out (`App.tsx:933`) or a token change (`:754`), so a second identity never inherits the first one's older page.

## Choices made

- Memory bound. Until the person first presses "Show older searches", a new ask still trims the rail to 20 (card 112's rule, so the list before a reload matches the list after one). A row that trim drops is held back and turns the control on, and the next press puts it back before the server's next page (fix round), so the row stays reachable. From the press on, even while the page loads, a new ask drops nothing (fix round, J-136S4-02). The list is then bounded by what the person chose to load, 20 rows per press, plus the searches asked in this tab, which the daily allowance bounds (100 a day). Sign-out empties it.
- The control's look. The brief said "styled like + New search". It takes that button's shape, padding, font size and weight, but the secondary colours of the collapse control beside it (blue text, the `line` border, the `surfaceSunk` hover), so the rail keeps one filled blue action. This is a product call to confirm at the product check.
- A failed load says "Older searches did not load. Try again." and keeps the control, so the next step is clear.
- On a phone, pressing the control does not close the drawer, since the person is still choosing.

## Tests

| Command | Result |
|---|---|
| `pytest tests/system_03_search_agent/feedback/test_history.py tests/system_03_search_agent/feedback/test_history_saved_answer.py tests/system_03_search_agent/adapters/web_sse/test_history_endpoint.py tests/system_03_search_agent/adapters/web_sse/test_saved_answer_endpoint.py tests/system_03_search_agent/adapters/mcp/test_parity_tools.py` | 139 passed |
| `npx vitest run src/components/answer/ src/lib/ src/App.historyPaging.test.tsx src/App.historyAfterStop.test.tsx src/App.historyNoAnswer.test.tsx src/App.savedAnswer.test.tsx src/App.test.tsx` | 19 files, 197 passed |
| `npx tsc --noEmit -p .` | clean |
| `ruff check .` | all checks passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2) | clean |

New cases:

- `tests/system_03_search_agent/feedback/test_history.py`, against the real local database: paging at 20, 21, 40, 41 and 45 rows (sizes, `has_more` on every page, every row once and in order); 45 rows on five shared timestamps paged seven at a time; another owner's cursor, a cursor that never existed, and an own cursor beside a stranger's interleaved rows; the same two cursors over HTTP giving byte-identical bodies; empty, over-long, NUL, newline and delete cursors refused; a 64-character cursor accepted; `list_history` still a list for MCP.
- `tests/system_03_search_agent/adapters/web_sse/test_history_endpoint.py`: `has_more` at 20 and 21 rows; `before` reaching the read function with the caller's own owner; `has_more` surviving a withheld last row; another owner's cursor; duplicate, empty, over-long and at-the-bound cursors; five control-character cursors a 422 through the real function. The fake now patches `list_history_page`; `test_saved_answer_endpoint.py`'s fake moved with it.
- `frontend/src/App.historyPaging.test.tsx` (new), through the real `fetchHistory` with a keyset `fetch` stub: 45 searches load in three pages and the control goes; exactly 20 shows no control; a new ask after loading older keeps all 40 below it; a row the first-page trim drops comes back through the control; a failed load says so and a retry works.
- `frontend/src/lib/api.fetchHistory.test.ts`: `before` is sent encoded beside `limit`; `has_more` is read only when it is a real `true`.

## Mutations

Each part was broken, the touched tests run, and the file restored byte for byte.

| Mutation | Result |
|---|---|
| Cursor lookup without the owner filter | Red: another owner's cursor |
| Page query without the owner filter | Red: owner scoping |
| Keyset on `created_at` alone | Red: ties across page boundaries |
| `has_more` as `>=` | Red: the 20-row boundary |
| No control-character check | Red: the newline cursor |
| Endpoint drops `has_more` | Red: `has_more` at 21 rows |
| Duplicate `before` allowed | Red: the duplicate refusal |
| No `max_length` on `before` | Red: the over-long refusal |
| Rail ignores `hasOlder` | Red: exactly 20 shows no control |
| Older page fetched without `before` | Red: three pages, and the new-ask arm |
| `historyPagedOlder` never set, so a re-ask trims to 20 | Red: a new ask keeps loaded rows |
| The trim no longer turns the control on | Red: the trimmed row stays reachable |
| `has_more` not read from an older page | Red: the control goes at the end |
| `fetchHistory` drops `before` | Red: `before` sent, and three pages |
| `fetchHistory` reads `has_more` as truthy | Red: only a real `true` |
| A failed load shows nothing | Red: a failed load says so |

## Limits stated

- An empty page answers one lookup query whether the cursor is a stranger's or never existed. Both probe the unique `trace_id` index; a stranger's row also reads one heap row before the owner filter drops it. The difference was not measured; it is named here for the adversary to judge.
- Superseded by the fix round: the web cursor is now the server's `next_before`, which names the withheld row itself, so the next page never reads it again and a page of 20 unreadable rows still moves on. An API client that follows `items[-1]` instead still sees a withheld row counted twice (J-136S4-03, left).
- A token rotation in this tab aborts an older page in flight; the control returns to "Show older searches" and the next press loads it.

## Fix round

The one fix round, on the judge's and adversary's round 1 reports (`judge_s4.md`, `adversary_s4.md`, both in this folder). What the person sees now: a search they ask on their phone shows up near the top of the laptop's list within 12 minutes, and "Show older searches" keeps loading older ones until there are none, then goes. A search they ask while older ones are loading never takes a loaded one off the list.

| Id | Fix | Proof |
|---|---|---|
| J-136S4-01 (blocking) | The server names the cursor: additive `next_before` on `GET /v1/history`, the `trace_id` of the oldest row the page read, withheld rows included, or null. The web stores it from the first newest page and from each older page and sends it back; it never reads a row of its own list. The 12-minute refetch never moves it. `mergeServerHistory` places a server row by its `asked_at`, above the first restored row strictly older, so a row from another tab lands at the top of restored history, not the foot | Judge's P1, P2, P3, P4 re-run against the fix with a stub that answers `next_before`: 4 passed. New arm "a search from another device ... paging still reaches the end": the cursor sent is `t-19` then `t-39`, all 45 reached, the control goes |
| A-136S4-01 | Same cursor: a page whose 20 rows are all withheld answers `next_before` of its 20th row, so the next press moves on | Adversary's A1 shape over HTTP on the real database: walk `[(20, 0, True), (0, 20, True), (5, 0, False)]`, the five oldest reached. New pytest `test_a_page_of_only_withheld_rows_never_stops_the_walk_over_http` and endpoint arm; new web arm "a page whose rows are all withheld still moves on" |
| A-136S4-02 | `has_more` is now derived from `next_before` (a property), true only when a `limit + 1`th stored row exists, so the two always agree; `fetchHistory` keeps `has_more` only beside a usable cursor | Adversary's A2 shape: `[(20, 0, True), (0, 1, False)]`. What the person sees in that shape: the control shows once, the press adds nothing, the control goes; it is never a dead button. `has_more` still counts stored rows, withheld ones included: telling "older rows exist but none can be shown" apart would need the per-row guard below the endpoint, which this round did not move |
| A-136S4-05 | Same cursor: a row this tab asked that never reached the server can no longer become the cursor. A row the trim drops is held back in the tab and put back by the next press, so it does not depend on the server holding it either | New arm "a trimmed row and the next server page both come back, in order, by the server's cursor": cursor sent `t-19` |
| J-136S4-02 | The press, not the page landing, turns the trim off (`historyPagedOlder` set at the top of `showOlderSearches`) | Judge's P2 passes; new arm "a search asked while an older page loads drops no loaded row" |
| A-136S4-03 | `Cache-Control: no-store` on every `GET /v1/history` 200, first page and older pages | New arm `test_the_history_response_is_never_stored_by_a_cache`; judge's probe re-run: `no-store` on both the stranger and the unknown cursor |
| J-136S4-04 | The malformed-cursor 422 detail pinned whole. Its text now names `next_before`: "`before` must be the `trace_id` of one of your own searches, as returned in `next_before`" | Mutation M17 (detail prefixed with the internal `ValueError`) now red |
| J-136S4-05 | Two arms with a `fetch` that answers even after its request was aborted: sign-out while an older page is held, and the token rotation while one is held. Neither page is ever merged; after a rotation the control is back to "Show older searches" and the next press loads it. An aborted page that answers anyway now also resets the control from "Loading" (found by the rotation arm) | F1 and F4 red, below |
| J-136S4-06 | One arm each: sign-out resets the paged flag (F2), sign-out resets the control (F3, the next session's newest page fails), the 12-minute refetch after the last page does not bring the control back (F13), the control is disabled while loading (F14) | F2, F3, F13, F14 red, below |

Files: `feedback/history.py`, `adapters/web_sse/app.py` (history endpoint only), `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, and their tests (`test_history.py`, `test_history_endpoint.py`, `test_saved_answer_endpoint.py` fake, `App.historyPaging.test.tsx`, `api.fetchHistory.test.ts`). `FollowUp.tsx` needed no change. `HistoryResponse.next_before` is optional in the web type, so the other App test files' `fetchHistory` mocks read as "no older page" unchanged.

Tests, fix round:

| Command | Result |
|---|---|
| `pytest` on the same five Python files as above | 142 passed |
| `npx vitest run src/components/answer/ src/lib/ src/App.historyPaging.test.tsx src/App.historyAfterStop.test.tsx src/App.historyNoAnswer.test.tsx src/App.savedAnswer.test.tsx src/App.test.tsx` | 19 files, 206 passed |
| `npx vitest run src/App.depthToggle.test.tsx src/App.stopAfterAnswer.test.tsx src/App.stopUntilAnswer.test.tsx src/threadContinuation.test.tsx` (their `fetchHistory` mocks predate `next_before`) | 4 files, 28 passed |
| `npx tsc --noEmit -p .` | clean |
| `ruff check .` | all checks passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2) | clean |

Mutations, fix round. Each applied by a script, the related tests run, and every file restored byte for byte (the working-tree diff hash compared before and after):

| Mutation | Result |
|---|---|
| B1 `next_before` always null | Red: the 21-row walk |
| B2 `next_before` the `limit + 1`th row, off by one | Red: the 21-row walk |
| B3 endpoint drops `next_before` | Red: the withheld-page walk over HTTP |
| B4 endpoint cursor from the visible items | Red: the withheld-page walk over HTTP |
| B5 no `Cache-Control: no-store` | Red: the no-store arm |
| B6 422 detail prefixed with the internal text (judge's M17) | Red: the pinned detail |
| M1 cursor lookup without the owner filter (security) | Red: another owner's cursor |
| M2 page query without the owner filter (security) | Red: owner scoping |
| G1 cursor read off the rail again | Red: trimmed row, trimmed row with next page, withheld page |
| G2 server rows appended at the foot again | Red: another device |
| G3 paged flag set when the page lands (J-136S4-02's cause) | Red: ask while loading |
| G4 held-back rows never put back | Red: both trimmed-row arms |
| G5 `fetchHistory` keeps `has_more` without a cursor | Red: the `has_more` and cursor arm |
| F1 no abort on sign-out or token change | Red: both never-merged arms |
| F4 `aborted` guard and token-change abort removed | Red: both never-merged arms |
| F2 sign-out keeps the paged flag | Red: the F2 arm |
| F3 sign-out keeps the control | Red: the F3 arm |
| F13 every refetch moves the cursor and the control | Red: another device, and after the last page |
| F14 control pressable while loading | Red: ask while loading |

Security, re-run after the change (the judge's own probes `probe1.py` and `probe2.py`, the walk now following `next_before`; real app through `TestClient`, real guest tokens from `POST /auth/guest`, local database):

- Owner A walks its history: `[(20, True), (20, True), (5, False)]`, every row once and in order, no row of B's (B seeded on the same instants). `next_before` per page: A's 25th newest, A's 5th oldest, null.
- A's token with B's cursor and with a never-existing cursor: both `200 {"items":[],"count":0,"omitted_count":0,"has_more":false,"next_before":null}`, byte-identical, header diff `{}`, both `cache-control: no-store`.
- No token, garbage token, expired guest token: 401. A validly signed token for a guest with no session row: 401 `guest_session_revoked`. Malformed cursor without a token: 401, not 422.
- Validation unchanged from the judge's E1: empty, 65 characters, 65 emoji are Pydantic 422s; NUL, `a%00b`, newline, tab, delete are 422 with the pinned detail; SQL-looking, wildcard, traversal, ideographic space, RTL override, C1, lone surrogate, `%FF%FE`, upper-cased own id, own id with a space: `200` empty page with `next_before` null; duplicate `before`: 422 naming it; `limit` 0, 51, `abc` with a cursor: 422.
- Owner filter still on both queries, before the keyset condition: mutations M1 and M2 red.

Local database residue from these probes, beside the round 1 residue: `interactions` rows with `trace_id` prefixes `fixr-`, `fixrA1`, `fixrA2`, `fixrJ3`, `histpage-withheld`, and the guest sessions the probes minted.

## Fix round, left

Named and not fixed, as briefed:

- J-136S4-03 (minor), a withheld row counted twice in `omitted_count`. Its cause is gone for any client that follows `next_before`, the web app included: the adversary's shape with one 2500-character question at newest-first index 19 now walks `[(19, 1, True), (20, 0, True), (4, 0, False)]`, total omitted 1. An API client that still follows `items[-1]` re-reads the row and counts it again.
- A-136S4-04 (major, older than this card), 16 concurrent `GET /v1/history` requests from one caller exhaust the database pool for 30 seconds. Unchanged: the same on develop, on the first page alone.
- A-136S4-06 (minor), the MCP history tool has one page. `list_history(owner_id, limit)` is unchanged.
