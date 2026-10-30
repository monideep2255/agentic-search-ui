# Card 136 slice S4: show older searches

What the person sees now: when they have more than 20 searches, "Show older searches" sits at the foot of "Your searches". Each press loads the next 20 older ones, and the control goes when there are none left. A new search still goes on top, and once they have loaded older searches, asking a new one never makes any of them disappear. Every page is their own searches only, a guest's included.

## Table of contents

- [Change](#change)
- [How owner scoping and the cursor work](#how-owner-scoping-and-the-cursor-work)
- [Choices made](#choices-made)
- [Tests](#tests)
- [Mutations](#mutations)
- [Limits stated](#limits-stated)

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
- `has_more` is `len(rows) > limit` from the database rows (`:407`), before the endpoint's per-row guard, so a withheld row never hides an older page.

Cursor validation:

- Length: `FastAPIQuery(None, min_length=1, max_length=64)` (`adapters/web_sse/app.py:1070`), 64 being the write path's own `trace_id` bound. Empty or over-long is a 422 that names the bound, before any query.
- Control characters, NUL above all: `_check_cursor` (`feedback/history.py:257` to `:273`) raises `ValueError` before a session opens. PostgreSQL text cannot hold NUL and the driver would raise, so this is what keeps it from being a 500. The endpoint turns it into a 422 that says what to send and nothing about whether any row exists (`app.py:1074` to `:1085`).
- Duplicates: `_SINGLE_OCCURRENCE_HISTORY_PARAMS = ("limit", "before")` (`app.py:990`, used at `:1016`).
- `limit` is unchanged: 1 to 50, a 422 above 50 (the owner's decision of 2026-08-27).

Web:

- The cursor is the `trace_id` of the rail's last row restored from the server (`App.tsx:772` onward). The server scopes it anyway, so a wrong cursor can only cost an empty page.
- An older page in flight is aborted, and never merged, on sign-out (`App.tsx:933`) or a token change (`:754`), so a second identity never inherits the first one's older page.

## Choices made

- Memory bound. Until the person loads an older page, a new ask still trims the rail to 20 (card 112's rule, so the list before a reload matches the list after one). A row that trim drops turns the control on (`App.tsx:1532`), and the next page starts just below the new last row, so the row stays reachable. After an older page is loaded, a new ask drops nothing (`App.tsx:1529`). The list is then bounded by what the person chose to load, 20 rows per press, plus the searches asked in this tab, which the daily allowance bounds (100 a day). Sign-out empties it.
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
- The web cursor is the last row the rail shows. If the server withheld the last row of a page (`omitted_count`), the next page reads that row again and withholds it again, so the count can repeat. Paging still moves forward unless a whole page of 20 is unreadable, which no write path produces.
- A token rotation in this tab aborts an older page in flight; the control returns to "Show older searches" and the next press loads it.
