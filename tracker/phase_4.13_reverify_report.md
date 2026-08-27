# Build phase 4.13 re-verify report: review round 2, STOPPED MID-ROUND

Branch: `phase/4.13-durable-history`, graded at `8a95a2b`.
Round run 2026-08-27 from fresh context, against the code, the database and the tests rather than against any summary.

## Verdict: FAIL, and the round STOPPED before completing

The round did not finish. It stopped on F-4.13-RV-01, a defect located inside commit `10da7fa`, the code written this phase to fix F-4.13-A-07. The round's own stop condition requires exactly that: a defect inside an earlier fix is a signal that the fix APPROACH is wrong rather than incomplete, so the round halts and the phase escalates to the product owner on the spot instead of accumulating more findings.

Checks 1 through 6 had completed before the stop. Check 7, the frontend, is where the stop fired, on its first item.

## Table of contents

- [Verdict: FAIL, and the round stopped before completing](#verdict-fail-and-the-round-stopped-before-completing)
- [The stop: F-4.13-RV-01](#the-stop-f-413-rv-01)
- [Checks completed before the stop](#checks-completed-before-the-stop)
- [Checks not started](#checks-not-started)
- [Tree cleanliness](#tree-cleanliness)

## The stop: F-4.13-RV-01

`Regression of: F-4.13-A-07`. Major, LIVE-REACHABLE. Full row in `tracker/phase_4.13.md`.

Commit `10da7fa` rewrote `ask()`'s history reducer at `frontend/src/App.tsx:567-570` into a filter-then-unshift, transcribing the prototype's `start()`. The `.filter` removes an entry, and the id generator on the line directly above it, untouched by the fix, is `id: String(current.length)`. That is unique only while the list grows monotonically. Once a re-ask can shrink it, two rows take the same id.

Three consumers read that id as a key: `FollowUp.tsx:441` (`key={item.id}`), `FollowUp.tsx:459-464` (`item.id === activeId`), and `App.tsx:1064-1066`, whose `onOpen` resolves a click through `history.find((entry) => entry.id === id)` and takes the FIRST match.

The reproduction, all of it ordinary use:

1. Ask A. History holds one row, id `0`.
2. Re-ask A from the rail, the exact interaction F-4.13-A-07's fix exists to enable. Length is 1, so the new row takes id `1`, and the filter removes the old one, leaving length 1 again.
3. Ask B. Length is 1 AGAIN, so B also takes id `1`.
4. Click the BRCA1 row. The product runs the CFTR question.

Measured in a throwaway worktree, post-fix:

```
FAIL  src/rvIdCollision.test.tsx > clicking one rail row must re-ask THAT row's question, not another's
AssertionError: expected "vi.fn()" to be called with arguments: [ ObjectContaining{…}, 'test-token' ]
  1st vi.fn() call:
-     "text": "What is BRCA1?",
+     "text": "Which variant is pathogenic in CFTR?",
 Test Files  1 failed (1)
```

The same clause PASSES when only that one hunk is reverted to its pre-`10da7fa` form:

```
 Test Files  1 passed (1)
      Tests  1 passed (1)
```

`App.tsx` was then restored and the restore proven byte-identical:

```
db88c5b3c2517fe18e334416296e731c66c360c41fd63f225f4a5f1edcc6a5de  frontend/src/App.tsx
BYTE-IDENTICAL RESTORE CONFIRMED
```

Neither vitest clause `10da7fa` added can see it: both seed the rail from `fetchHistory`, so every row they exercise carries a `trace_id` id rather than a positional one, and the collision is reachable only among locally-created rows.

## Checks completed before the stop

### Check 1: F-4.13-A-01, the blocker. PASS

The original defect was reproduced and is now refused. A guest was minted, ran a real query, and its `guest_sessions` row was deleted; every owner-scoped route on the surface was then called with the same credential. All seven refuse, with the structured detail:

```
-- deleted 1 guest_sessions row(s) for cbe6c1fe-23b9-45f1-b5a7-098e13bf1b73 --
GET /v1/history                  -> 401 {"detail":{"reason":"guest_session_revoked","message":"this guest session is no longer valid"}}
GET /v1/allowance                -> 401 {"detail":{"reason":"guest_session_revoked",...}}
POST /v1/query                   -> 401 {"detail":{"reason":"guest_session_revoked",...}}
GET /v1/query/{id}/events        -> 401 {"detail":{"reason":"guest_session_revoked",...}}
GET /v1/query/{id}/citations     -> 401 {"detail":{"reason":"guest_session_revoked",...}}
POST /v1/query/{id}/stop         -> 401 {"detail":{"reason":"guest_session_revoked",...}}
POST /v1/query/{id}/feedback     -> 401 {"detail":{"reason":"guest_session_revoked",...}}
```

The refusal CONTRACT did not regress. Build phase 4.10's F-4.10-A-05 requires a revoked session and a merely unusable token to stay distinguishable, and they do:

```
CONTRACT migrated-guest GET /v1/allowance   -> 401 {"reason": "guest_session_revoked", "message": "..."}
CONTRACT migrated-guest POST /v1/query      -> 401 {"reason": "guest_session_revoked", "message": "..."}
CONTRACT migrated-guest GET /v1/history     -> 401 {"reason": "guest_session_revoked", "message": "..."}
CONTRACT garbage token  GET /v1/allowance   -> 401 "invalid or expired credentials"   (bare string)
CONTRACT garbage token  GET /v1/history     -> 401 "invalid or expired credentials"   (bare string)
CONTRACT expired guest  GET /v1/allowance   -> 401 "invalid or expired credentials"   (bare string)
```

One route is NOT covered by the category fix, and this is correct rather than a gap: `GET /v1/persona` resolves through `resolve_caller_from_bearer_token` directly, never `get_caller`, and it returns 200 to a revoked guest. It reads only `Principal.user_id`, which is `None` for every guest, so a revoked guest gets the identical anonymous session-keyed draw an unauthenticated caller gets. Nothing owner-scoped is disclosed. Recorded so the next reader does not have to re-derive it.

### Check 2: the ADMIT path. PASS

A guardrail has no safe direction of failure. A live guest completes a real run and reads its own history, and an account is untouched by the guest branch:

```
ADMIT live guest POST /v1/query                  202
ADMIT live guest GET /v1/history sees own row    200, items=1
ADMIT live guest GET /v1/allowance               200 {"kind":"guest","used":1,"total":5,"counted":true}
ADMIT live guest GET events / citations / stop   200 / 200 / 200
ADMIT account    GET /v1/history after migration 200
22/22 checks passed
```

### Check 3: F-4.13-A-02's degradation. PASS on honesty, INCOMPLETE on reach

`omitted_count` is accurate and cannot under-report on the paths the fix covers, measured against real rows in the real database:

```
S1 two good rows + one 3000-char query_text -> 200  count=2 omitted=1  ['GOOD ROW ONE','GOOD ROW TWO']
S2 three bad + one good                     -> 200  count=1 omitted=3
S3 over-long trace_id                       -> 200  count=1 omitted=1
S6 limit=2 with the bad row at position 2   -> 200  count=1 omitted=1
```

One bad row no longer costs the caller their whole list through the response-model path. It still does through one path the fix did not reach, filed below as F-4.13-RV-02.

### Check 4: F-4.13-A-08's duplicate-`limit` refusal. PASS

Every duplicate spelling is refused with an actionable message, and ordinary calls are unaffected:

```
(none)                     -> 200  items=6
?limit=3                   -> 200  items=3
?limit=1&limit=50          -> 422  "send exactly one `limit` query parameter, got 2: ['1', '50']"
?limit=50&limit=1          -> 422  "send exactly one `limit` query parameter, got 2: ['50', '1']"
?limit=abc&limit=2         -> 422  "send exactly one `limit` query parameter, got 2: ['abc', '2']"
?limit=1&limit=1           -> 422  "send exactly one `limit` query parameter, got 2: ['1', '1']"
?limit=1&limit=2&limit=3   -> 422  "send exactly one `limit` query parameter, got 3: ['1', '2', '3']"
?limit=2&limit=abc         -> 422  int_parsing (FastAPI's own binding fires first; still a refusal)
?limit=0 / 51 / -1 / 1.5   -> 422  each naming its own violated bound
?limit=1 / 50 / %2b5       -> 200  items=1 / 6 / 5
```

### Check 5: the migration. PASS

`upgrade` and `downgrade` both actually run, against a real PostgreSQL database (`rv413_probe`, created for this check rather than risking the shared one), through the full cycle 0008 to 0009 to 0008 to 0009. The index is absent after the downgrade, present and `indisvalid = t` after each upgrade, and `alembic_version` stamps correctly both ways.

The index is genuinely used by the query `list_history` issues, measured against the real `search_agent_users` database (24,463 rows) for a real caller holding 29 rows. AFTER, with the index available:

```
Limit  (cost=0.41..83.12 rows=20 width=191) (actual time=0.648..4.482 rows=20 loops=1)
  Buffers: shared hit=16
  ->  Index Scan using idx_interactions_owner_id_created_at_id on interactions
        Index Cond: (owner_id = 'guest:1111...'::text)
        Buffers: shared hit=16
Execution Time: 4.537 ms
```

BEFORE, index access suppressed in a rolled-back transaction so the comparison runs on the same data in the same session:

```
Limit  (cost=1979.56..1979.61 rows=20 width=191) (actual time=97.667..97.669 rows=20 loops=1)
  ->  Sort  (Sort Key: created_at DESC, id DESC)
        ->  Seq Scan on interactions
              Filter: (owner_id = 'guest:1111...'::text)
              Rows Removed by Filter: 24476
              Buffers: shared hit=1673
Execution Time: 97.708 ms
```

No `Sort` node in the new plan, 16 buffer hits against 1679, 4.5 ms against 97.7 ms.

The `autocommit_block` usage is correct and load-bearing, proven by removing it rather than by reading:

```
sqlalchemy.exc.InternalError: (psycopg2.errors.ActiveSqlTransaction)
CREATE INDEX CONCURRENTLY cannot run inside a transaction block
```

The migration file was restored and the restore proven by SHA-256 against the main checkout (`bd4fa3b9...` on both).

### Check 6: every new or changed test, by mutation. PASS, and this is the round's strongest result

31 mutations, run in a throwaway worktree, each restored byte-identically with a SHA-256 assertion before the next. Worktree baseline: `49 passed`.

All seventeen tests added this round are attributable to at least one mutation they catch. There are NO vacuous arms among them, which is the opposite of what this phase's history predicted.

| Mutation | Result |
|---|---|
| M-A drop `trace_id` `max_length` | CAUGHT |
| M-B drop `question` `max_length` | CAUGHT |
| M-C drop `trust_signal` `max_length` | CAUGHT |
| M-D drop `items` `max_length` | CAUGHT |
| M-E `HistoryItem` `extra="forbid"` to `"ignore"` | CAUGHT |
| M-F `HistoryResponse` `extra="forbid"` to `"ignore"` | CAUGHT |
| M-G duplicate threshold `> 1` to `> 2` | CAUGHT |
| M-H `_reject_duplicate_limit` made a no-op | CAUGHT |
| M-I drop the `_reject_duplicate_limit` call site | CAUGHT |
| M-J degradation reverted, `ValidationError` escapes again | CAUGHT |
| M-K `omitted_count` never increments | CAUGHT |
| M-L `omitted_count` hardcoded 0 in the response | CAUGHT |
| M-N `count` reports the pre-drop entry total | CAUGHT |
| M-O drop the liveness call from `get_caller` | CAUGHT |
| M-P revoked-but-present row admitted | CAUGHT |
| M-Q unknown guest id admitted | CAUGHT |
| M-R liveness 401 detail becomes a bare string | CAUGHT |
| M-S liveness gate applied to accounts instead of guests | CAUGHT |
| M-T drop the owner `WHERE` clause | CAUGHT |
| M-U the F-4.5-A-02 shape in the handler | CAUGHT |
| M-M drop `citation_count` `ge=0` | MISSED |
| N1 duplicate refusal over-fires on a SINGLE limit | CAUGHT |
| N2 `omitted_count` starts at 1 | CAUGHT |
| N3 `question` bound narrowed 2000 to 1999 | CAUGHT |
| N4 `items` bound narrowed `MAX_LIMIT` to `MAX_LIMIT - 1` | CAUGHT |
| N5 drop `question` `max_length`, no `-x` | CAUGHT |
| N6 duplicate check no-op, no `-x` | CAUGHT |
| N7 drop the liveness call, no `-x` | CAUGHT |
| N8 liveness gate hits accounts | CAUGHT |
| N10 `trust_signal` bound narrowed 20 to 5 | CAUGHT |
| N9 `trace_id` bound narrowed 64 to 63 | MISSED |
| Z1 migration builds the index in the WRONG column order | CAUGHT |
| Z2 migration's `upgrade()` creates no index at all | CAUGHT |

Attribution, so each of the seventeen is accounted for rather than covered in aggregate:

- `test_two_valid_but_different_limits_are_both_refused`, `test_one_malformed_occurrence_does_not_let_the_other_win`: N6
- `test_a_single_limit_occurrence_is_unaffected`: N1
- `test_an_oversized_row_is_omitted_and_disclosed_not_a_500`: N2, N5, M-J, M-K, M-L, M-N
- `test_every_row_conforming_reports_zero_omitted`: N2
- `test_question_over_max_length_is_refused`: N5
- `test_question_at_max_length_is_accepted`: N3
- `test_trace_id_over_max_length_is_refused`: M-A
- `test_trust_signal_over_max_length_is_refused`: M-C
- `test_an_unknown_field_on_history_item_is_refused`: M-E
- `test_history_response_items_over_max_length_is_refused`: M-D
- `test_history_response_items_at_max_length_is_accepted`: N4
- `test_an_unknown_field_on_history_response_is_refused`: M-F
- `test_history_refuses_the_migrated_guests_token_rather_than_serving_its_ghost_row`: N7, N8, M-O, M-P, M-R
- `test_a_run_scoped_route_the_finding_named_uncovered_also_refuses`: N7, N8
- `test_an_unknown_guest_id_is_refused_on_history_too`: N7, M-Q
- `test_an_account_principal_is_unaffected_and_never_guest_gated`: N8
- `test_interactions_indexes_exist`, the extended assertion: Z1, Z2

The two misses are gate gaps with no reachable defect behind them, filed as F-4.13-RV-03. Neither is a vacuous arm: they are bounds nothing pins.

## Checks not started

Check 7's remaining items were NOT started, deliberately. The stop fired on its first item.

- `formatHistoryMeta`'s behaviour on an absent, malformed or hostile `asked_at`: NOT verified. Reading suggests the guard is on `Number.isNaN(askedAt.getTime())`, which is a validity check rather than a type check, so a JSON `asked_at` of `[]`, `1` or `true` would produce a valid 1970 date rather than being omitted. That is an observation from reading only, it was not run, and under this round's own rule an unverified check is a fail, not a pass. It is recorded here rather than filed as a finding, because filing a defect on reading alone is what this phase has already been bitten by twice.
- Whether the frontend suite's remaining new clauses are mutation-proof: NOT started.
- The full backend and frontend suite re-measurement: NOT re-derived. Taken as reported by the coordinator: backend `4115 passed, 159 skipped, 1 xfailed, 0 failed`, frontend `18 files, 231 tests`.

## Tree cleanliness

Every mutation in this round ran inside a throwaway git worktree at `HEAD`, never in the main checkout, and every one was restored byte-identically with a SHA-256 assertion before the next mutation ran. The one file mutated outside that worktree was none.
