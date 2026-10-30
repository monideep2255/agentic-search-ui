# Card 136 slice S4 adversary report, round 1

Adversary for draft pull request #316, worktree detached at 4938a8e2. Findings are appended as they are established.

## Findings

### A-136S4-01: A page whose rows are all withheld answers `has_more: true` with no item to continue from, so older searches become unreachable
- Severity: minor (no shipped write path produces a withheld row today; the shape is reachable by any direct write, a future widening of a bound, or rows already in the table). Inside this phase's new code (the cursor contract "the `trace_id` of one of your own searches, as returned in `items`" combined with `has_more` computed before the per-row guard).
- What: when every row of an older page fails the endpoint's per-row guard (citations not a list, question over 2000 characters), the response is `{"items":[],"count":0,"omitted_count":20,"has_more":true}`. The contract says the next cursor is a `trace_id` from `items`, and `items` is empty, so neither an API client nor the web app can ever page past it. The web app's cursor stays the last rail row, so "Show older searches" re-requests the same page forever: a dead button, by a different cause than J-136S4-01. The builder named this in "Limits stated"; filed so it is tracked with a reproduction.
- What a person sees: "Show older searches" stays on screen and nothing appears however often it is pressed; their five oldest searches cannot be reached.
- Evidence (own probe, real app via `TestClient`, real guest token from `POST /auth/guest`, local database; 45 rows: 20 newest normal, the next 20 with `citations = '"x"'`, the 5 oldest normal): walk following `items[-1].trace_id` gave `[(200, 20, 0, True), (200, 0, 20, True)]`, `older five reached: False`; page 2 body `{"items":[],"count":0,"omitted_count":20,"has_more":true}`.
- Worse than develop: no in the sense that develop showed only the newest 20 and never offered older rows; the dead control itself is new.
- NOT FIXED

### A-136S4-02: `has_more: true` when the only older rows are withheld, so the control loads nothing and vanishes
- Severity: minor. Inside this phase's new code (`has_more = len(rows) > limit` before the guard, `feedback/history.py:407`).
- What: 21 rows where the oldest has a non-list `citations`: page 1 says `has_more: true`, page 2 is `count 0, omitted 1, has_more false`. The `has_more` the person acts on promises a search they will never be shown.
- What a person sees: "Show older searches" appears, they press it, nothing is added and the control disappears. Nothing tells them a search was withheld, because the web app does not read `omitted_count`.
- Evidence (same probe): `A2 walk [(200, 20, 0, True), (200, 0, 1, False)]`.
- Worse than develop: new surface; develop showed no control.
- NOT FIXED

### Evidence AE1: guest-to-account carry-over with cursors (own probe, real app, real tokens)

Guest seeds 25 rows, signs up and logs in with `guest_token`, account has 25 rows of its own interleaved by time. Account walk `[(200, 20, 0, True), (200, 20, 0, True), (200, 10, 0, False)]`, 50 unique, exactly the 50 seeded, order identical to the database's `created_at DESC, id DESC`. The revoked guest token with its own pre-migration cursor: `401 guest_session_revoked`. The account with a migrated guest cursor: rows continue across guest and account rows. A third guest with a migrated cursor or an account cursor: `200 {"items":[],"count":0,"omitted_count":0,"has_more":false}`. No leak found on this path.

### A-136S4-03: `GET /v1/history` carries no `Cache-Control: no-store`, so every older page of a person's searches may be written to the browser's disk cache
- Severity: minor, unsure. Not inside this phase's fix: the header was missing on develop too. Filed because this phase multiplies the number of distinct history URLs a browser holds, one per page.
- What: `/auth/login` answers with `cache-control: no-store`; `/v1/history` (with or without `before`) answers with only `content-length` and `content-type`. Nothing tells a browser or an intermediary not to store a list of a person's questions.
- What a person sees: nothing on screen. On a shared computer, after they sign out, their questions can remain in the browser's cache files. I did not prove a browser stores or reuses this response; I proved only the header is absent.
- Evidence (own probe, `TestClient`, real guest token): `GET /v1/history` -> `200 {'content-length': '57', 'content-type': 'application/json'}`; `POST /auth/login` -> `cache-control: no-store`.
- Worse than develop: no (same header set on develop); more URLs exposed.
- NOT FIXED

### Evidence AE2: cost of a page on a 60,000-row history, ties at every timestamp (own probe)

One guest, 60,000 rows on 5,000 distinct timestamps (12 rows share each). Medians of 50 requests through the real app: first page `limit=50` 4.27 ms; mid-history cursor 5.75 ms; cursor at the oldest row, `limit=50`, `(200, 0, False)` 3.79 ms; unknown cursor 3.07 ms. `EXPLAIN (ANALYZE, BUFFERS)` of the page query at the mid cursor: `Index Scan using idx_interactions_owner_id_created_at_id`, `Index Cond` holds both the owner and `ROW(created_at, id) < ROW(...)`, 55 buffers, 0.108 ms. A full walk at `limit=50`: 1,200 pages, 60,000 seen, 60,000 unique, last page `(200, 50, 0, False)`, 6.5 s. No sequential scan, no duplicate, no skip found.

### Evidence AE3: stranger cursor versus unknown cursor timing (own probe)

400 cursors of the 60,000-row owner (strangers to the caller) against 400 never-existing ones, shuffled, three passes at the function level and one over HTTP. Function level p10/p50/p90 in microseconds: stranger `[387.9, 440.4, 847.8]`, unknown `[387.6, 442.1, 851.6]`. HTTP: stranger `[2861.2, 4143.5, 7094.4]`, unknown `[2856.2, 4079.6, 7824.2]`. No usable difference.

### A-136S4-04: Sixteen concurrent `GET /v1/history` requests from one guest deadlock the database pool for 30 seconds and return 500s
- Severity: major, but NOT inside this phase's fix and NOT worse than develop: develop's code deadlocks the same way. Filed because the brief asked for "many concurrent pages" and the answer is that the server falls over before the cursor matters.
- What: each request holds one pooled connection from the auth dependency (left `idle in transaction` on `SELECT guest_sessions.revoked_at ...`) and then asks the same pool (size 5, overflow 10, timeout 30 s, `data/base.py:60` defaults) for a second connection inside `list_history_page`'s `session_scope`. Fifteen requests in flight hold all fifteen connections and each waits for a sixteenth that never frees, until the 30-second pool timeout turns them into 500s. While that lasts, every other database-backed request on the process waits too: `POST /auth/guest` from `curl -m 5` returned nothing (`000`).
- What a person sees: one guest (or one impatient script) sending sixteen history requests at once makes the whole site hang for about 30 seconds for everyone on that process, and some of those requests fail.
- Evidence (own probe, a local `uvicorn` on 127.0.0.1 serving this branch, real guest token, 2,000 own rows; `pE.py <concurrency> <requests>` in my scratchpad):
  - Branch, concurrency 16, 200 requests, no cursor: `E nocursor {200: 191, 500: 9} 30.3 s`, nine `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00` in the server log. The same with a cursor right after: `{200: 200} 0.3 s` (the race did not form that run).
  - Branch, concurrency 300, 3,000 requests: 273 of the same `TimeoutError`; `pg_stat_activity` showed exactly 15 sessions `idle in transaction | ClientRead | SELECT guest_sessions.revoked_at FROM guest_sessions WHERE guest_sessions.id =`.
  - Develop (`git archive origin/develop src`, 4eda8ca5, served the same way), concurrency 300, 1,000 requests, no cursor: 131 of the same `TimeoutError`, the same 15 `idle in transaction` sessions.
- Worse than develop: no. Same deadlock, same trigger, on the first page alone.
- NOT FIXED

### Evidence AE4: time zones, microsecond gaps, ties, and inserts during a walk (own probe, real app, real guest token)

- Server session time zone `America/New_York`. 25 rows: 13 across the 2025-11-02 fall-back hour every 10 minutes, 6 one microsecond apart, 6 on one identical instant. Walks at `limit` 1, 2, 3 and 7: `exact order True` against the database's `created_at DESC, id DESC` every time, last page `has_more False`.
- 60 rows walked five at a time while, after every page, two newer rows (now) and one row a day older than all of them were inserted: 15 pages, 0 duplicates, every original row seen, 14 of 15 older inserts seen (the 15th was written after the last page was read), last `(4, False)`.

### A-136S4-05: When no restored row is left in the rail, the web cursor falls back to a row from this tab, and if that search's row never reached the server the control loads nothing and vanishes
- Severity: unsure, minor. Inside this phase's new code (`App.tsx:776`, the fallback cursor). READ ONLY, NOT RUN: I did not build a probe for it.
- What: after 20 asks in one tab without pressing "Show older searches", the first-page trim has dropped every restored row, so `showOlderSearches` sends the `traceId` (the run id) of the oldest search asked in this tab. Capture is best-effort (`core/run.py:464` logs "interaction capture failed" and moves on), so that run may have no `interactions` row. The server then answers the unknown-cursor empty page with `has_more: false`, the control disappears, and every older search is unreachable until a reload.
- What a person sees, if it happens: they press "Show older searches", nothing is added, and the control goes, as if they had no older searches.
- Evidence: reading only. `App.tsx:775` to `776`; `feedback/history.py:385` to `386` (unknown cursor is `entries=[], has_more=False`); E1 of the judge (unknown cursor answers an empty page). The trigger needs a capture failure on exactly the oldest search asked in the tab, so it is rare.
- Worse than develop: new surface.
- NOT FIXED

### A-136S4-06: The MCP history tool still has no way past its one page
- Severity: minor. Not inside this phase's fix; not worse than develop.
- What: `adapters/mcp/server.py:1535` calls `list_history(owner_id, limit)`, which by design (`feedback/history.py`, "Kept with its original two-argument shape for the MCP tool, which pages nothing") returns only the newest page, at most 50. A person using the product through an MCP client hits the same wall the card removes from the web: no way to reach older searches. Read, plus the builder's and judge's MCP parity runs (`list_history(owner, 7)` same ids and order as develop).
- What a person sees: through an MCP client, their older searches remain unreachable.
- Worse than develop: no.
- NOT FIXED

## Verdict

Server half: no way found for one identity to learn anything about another's searches. Paging is exact under ties, time zones and concurrent inserts, and a page costs one index scan at 60,000 rows. Against the card's acceptance, the phase is FAIL, carried by the judge's J-136S4-01 (not re-filed here). This round adds no blocking finding.

Inside this phase's new code: A-136S4-01, A-136S4-02 (minor, both from `has_more` counted before the per-row guard, reachable only through rows no shipped write path produces) and A-136S4-05 (unsure, read only). Not inside it and not worse than develop: A-136S4-03 (no `no-store` on history) and A-136S4-04 (major: 16 concurrent history requests deadlock the connection pool for 30 s, the same on develop). A-136S4-06 is a minor gap on the MCP surface.

Verified with my own probes: A-01, A-02, A-03, A-04 (branch and develop), AE1 carry-over, AE2 cost and plan, AE3 timing, AE4 ordering. Read only: A-05, A-06; the claim that `owner_id` case cannot vary (it is built from a signed claim minted by the server, so it is unreachable without the signing key; not probed).

Local database residue from my probes, left in place for the lead to decide: `interactions` rows with `trace_id` prefixes `advA1`, `advA2`, `advBg`, `advBu`, `advC`, `advD-` (60,000 rows), `advE-` (6,000 rows over three runs), `advF`; one `users` row `adv-0ef31bb83b@example.com`; the guest sessions minted by `POST /auth/guest`.
