# Build phase 4.10 judge report

Branch: `phase/4.10-guest-allowance`
Commits graded: `1d65a2c`, `24632a0`, `9ca36ed` (`git log --oneline develop..HEAD`)
Judge: fresh context, no stake in the work. Graded 2026-08-15.
Working tree confirmed clean after every mutation was reverted (`git status --porcelain` empty).

## Verdict

FAIL.

Ten findings: 2 critical, 2 major, 6 minor.

The shipped code is, on the evidence I gathered, largely correct. What fails is the gate. Two of the premise gate's seventeen clauses cannot fail, and both were proven so by mutation rather than argued: the domain-separation clause the tracker itself said must be watched going red before it is credited (it does not go red), and the concurrency clause that claims to catch a read-then-write allowance (it does not catch one). Separately, `_migrate_guest_session`'s docstring asserts "NEVER raises" and the code can raise, from a threading invariant this phase broke and nothing checks.

## Gates, measured

Every number below is from a command I ran on this branch, not from a report.

| Gate | Command | Result |
|------|---------|--------|
| Python suite | `python -m pytest tests/ -q` | 6 failed, 2550 passed, 113 skipped, 1 xfailed, 79.51s. The 6 failures are all `synthesis/test_citation_trust_full_premise.py`, the known live-network-gated set carried since build phase 4.0. Nothing else failed. |
| Backend premise gate | `python -m pytest tests/.../test_phase_4_10_premise.py -q` | 17 passed, 5.93s. The DB was reachable (`postgresql://localhost:5432/search_agent_users`, probed directly), so the file's `pytestmark` skip did not fire and the gate genuinely ran. |
| Frontend unit | `cd frontend && npx vitest run` | 12 files, 169 tests, all passed |
| Typecheck | `npx tsc --noEmit` | clean, exit 0 |
| Production build | `npm run build` | clean, 935 modules, exit 0 |
| Lint | `ruff check src/ tests/` | 5 errors. Identical, file-for-file, on `develop` (verified by checking out `develop` and re-running). Pre-existing, not this phase's. |
| Doc drift | `python tracker/check_doc_drift.py --check` | exit 1, 6 stale facts. See F-4.10-J-09. |
| Alembic migration suite | `python -m pytest tests/.../data/test_migration.py -q` | 9 passed. The tests are live, not skipped, so 0003's upgrade and downgrade are genuinely exercised. |
| Playwright e2e | not run | UNCHECKED. Out of the four gates I was asked to run; `accessibility.spec.ts` exists but I did not execute it, so T-4.10-08's "no new axe violation" is reported unchecked, never as passing. |

## Per-ticket acceptance criteria

Grading note, and it is load-bearing: `tracker/phase_4.10.md` was never updated after the builders finished. Every ticket still reads `Status: todo` and `Evidence: (filled at close)`, and the file header still reads "Builders not yet dispatched" against three landed commits (F-4.10-J-08). So no criterion could be graded from the tracker's own evidence field. Everything below was graded against the code and against commands I ran.

### T-4.10-01: guest token primitives

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| `auth/guest.py` exposes `mint_guest_token`/`decode_guest_token` | PASS | `src/system_03_search_agent/auth/guest.py:107,139` |
| Key is `HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`, derived at call time | PASS | `auth/guest.py:87-104`. `_get_auth_secret()` reads `os.environ` per call; no module-level cache. |
| `decode_guest_token` pins HS256, requires `exp`/`typ == "guest"`/`guest_id` | PASS | `auth/guest.py:180-209`. Probed directly: `typ=""`, `typ=None`, `typ=123`, `typ=["guest"]`, `typ="access"` and `alg: none` are each rejected with `ValueError: guest token is invalid`. |
| Rejects `exp` beyond 7 days + 60s skew | PASS | `auth/guest.py:203-205`. Probed: `exp=now+400 days` rejected. |
| Access token rejected by `decode_guest_token`, guest token rejected by `decode_access_token`, both directions | PASS | Probed both directions directly, both rejected. Also covered by `tests/.../auth/test_guest.py`. A guest token carrying an extra `user_id` claim decodes as a guest and returns only `guest_id`, and `Principal.user_id` is hardcoded `None` for that branch (`auth/dependencies.py:218`), so the extra claim is inert. |
| No token value, payload, or derived key in any log or exception string | PASS | Every `raise` in `auth/guest.py` uses a fixed literal. `auth/router.py:337,352,360` log static strings and an integer count only. `test_guest.py` asserts it at line ~279. |
| Tests cover valid, tampered, expired, wrong-key, wrong-`typ`, missing-claim, null | PASS | `tests/.../auth/test_guest.py`, 30 tests, all green. Three of them go red under the key-derivation mutation, so they are real. |

Ticket: PASS.

### T-4.10-02: `guest_sessions` and its atomic spend

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| Table declared with the named columns and FK `ON DELETE SET NULL` | PASS | `data/models.py`, `GuestSession`, all six columns present |
| `CheckConstraint("runs_used >= 0")` | PASS | `data/models.py`, `__table_args__`; mirrored at `alembic/versions/0003_guest_sessions.py:74` |
| Revision 0003 hand-written, working `downgrade`, expand-contract stated | PASS | `alembic/versions/0003_guest_sessions.py:1-29,78-79`. `upgrade()` only creates a table; `downgrade()` drops it. Reversal proven by `test_downgrade_base_removes_every_table_index_and_extension`, which now asserts `ALL_TABLES.isdisjoint(tables)` with `guest_sessions` in the set. 9/9 green. |
| Spend is ONE conditional `UPDATE ... RETURNING` | PASS | `data/guest_sessions.py:130-135,176-178` |
| Three-state result, not a bare bool | PASS | `SpendState` enum + `SpendResult` dataclass, `data/guest_sessions.py:48-73` |
| A test drives concurrent spends at the cap boundary | PASS | `tests/.../data/test_guest_sessions.py:~350-383`, real `ThreadPoolExecutor` against a real database. Mutation-verified: replacing the atomic UPDATE with a read-then-write turns this test red with "6 of 6 concurrent spends succeeded". |
| Tests cover valid, invalid, null | PASS | 23 tests in that file, all green |

Ticket: PASS.

### T-4.10-03: the principal resolver and the four query endpoints

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| `Principal` carries `owner_id`, `user_id`, `kind` | PASS | `auth/dependencies.py:146-165` |
| `get_caller` resolves either token, one detail string for every failure | PASS | `auth/dependencies.py:180-239`. `_INVALID_CALLER_DETAIL` is the only string emitted. |
| All four `/v1/query` endpoints accept a guest | PASS | `app.py:277,414,562,659` all now `Depends(get_caller)`. Premise gate `TestAdmitArm` exercises create, events and citations end to end. |
| `_get_owned_run` compares `owner_id` and nothing else, 404 before 403 | PASS | `app.py:398-408`. Mutation-verified: swapping the comparison to `entry.user_id != caller.user_id` turns `test_a_guest_cannot_touch_another_guests_run` red. |
| Cross-principal isolation on read/stop/citations, both directions | PASS | Gate clauses at `test_phase_4_10_premise.py:533,560`, both real under the mutation above |
| `is_operator_user` never called with a namespaced id; a guest is never an operator | PASS | `app.py:498` passes `caller.user_id`, which is `None` for a guest; `harness/cost_control.py:513-514` returns False for `None`. Mutation-verified: forcing `is_operator = True` turns `test_a_guest_is_never_an_operator` red. |
| Guest token rejected by `/auth/me` and every `get_current_user` route | PASS | `get_current_user` is untouched; `decode_access_token` fails on signature. Gate clause at line 505. |
| `Query.user_id` receives a bare UUID or `None`, never namespaced | PASS | `app.py:365` passes `caller.user_id`. Grepped every consumer: `core/graph.py:712`, `harness/cost_control.py:304`, `core/run_registry.py:584`. None receives a namespaced string. |
| Tests cover valid, invalid, null on every endpoint, both classes | PASS | New `TestAllowanceEndpoint` and cross-principal blocks in `tests/.../web_sse/test_streaming_endpoints.py` |

Ticket: PASS.

### T-4.10-04: `POST /auth/guest` and `GET /v1/allowance`

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| `POST /auth/guest` creates a row, returns the four fields, 201, no body required | PASS | `auth/router.py:502-511`; `test_router.py::test_guest_valid_input_no_body_returns_201_with_a_fresh_allowance` |
| `GET /v1/allowance` returns `{kind, used, total, counted}` | PASS | `app.py:212-247` |
| Registered `total` reads the same function the enforcement path reads | PASS | `app.py:247` calls `per_user_daily_query_cap()`, `harness/cost_control.py:141`, the same function `check_user_daily_query_cap` uses. No second literal. |
| Registered `used` reported truthfully, "zero used" distinguished from "not counted" | PASS | `app.py:247` returns `counted=False`; `dailyLimitPhrase` in `frontend/src/lib/guestSession.ts` branches on it and never renders an uncounted zero as a count |
| Both endpoints rate-limit-considered: minting "carries its own bound" | FAIL | `auth/router.py:481-500` is a long comment considering the bound and deferring it to build phase 6.0. No bound is implemented, and `grep` finds no rate-limit middleware anywhere in `app.py`. See F-4.10-J-05. |
| Tests cover valid, invalid, null | PASS | `test_router.py` (4 new guest tests), `test_streaming_endpoints.py` (4 new allowance tests) |

Ticket: FAIL on one criterion.

### T-4.10-05: bound run creation per principal, closing F-4.0-A-10

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| `create_run` refuses past a per-principal cap, both classes | PASS | `core/run_registry.py:572-580` |
| The refusal is a 429 with `retry_after` naming what to do next | PARTIAL FAIL | True on the web surface (`app.py:313-329,371-383`). False on the MCP surface, which calls `create_run` at `adapters/mcp/server.py:699` with no handler at all, so the same condition escapes as a raw `RuntimeError`. See F-4.10-J-04. |
| The cap is a named constant with its value justified in a comment | PASS | `core/run_registry.py:163-176` |
| A test reproduces F-4.0-A-10's shape and asserts it is bounded | PASS | `test_streaming_endpoints.py::test_rapid_repeated_run_creation_from_one_caller_is_now_bounded`, asserts 429, the reason string, and the `Retry-After` header |
| Eviction still works; a completed run does not count | PASS | `count_active_runs_for_owner` calls `_evict_expired()` and filters `not entry.finished` (`run_registry.py:466-471`); `test_a_completed_run_does_not_count_against_the_cap` covers it |

Ticket: FAIL on one criterion.

### T-4.10-06: migration on signup and login

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| Optional `guest_token` BODY field on both, re-points live runs | PASS | `auth/schemas.py` (`SignupRequest`/`LoginRequest`), `auth/router.py:294-360,383,411` |
| Guest session revoked in the same transaction | PASS | `auth/router.py:339-347`, one `UPDATE` setting `revoked_at` and `migrated_to_user_id` together |
| Idempotent on replay | PASS | `revoked_at.is_(None)` predicate + `rowcount != 1` early return; `test_replaying_the_same_signup_guest_token_is_idempotent` |
| An invalid/expired/already-migrated guest token does NOT fail signup or login; failure logged, never fatal | FAIL | `reassign_owner` is called at `auth/router.py:354`, OUTSIDE the `try/except` that ends at line 352. It can raise `RuntimeError` (reproduced), and that propagates out of signup/login as a 500 after the guest session is already revoked and committed. See F-4.10-J-03. |
| A guest token belonging to a different guest cannot migrate a third party's runs | PASS | `old_owner_id` is built only from the presented token's own claim (`router.py:355`); `test_a_guest_tokens_migration_never_touches_another_guests_session` |
| Sign-in wall copy corrected | PASS | `frontend/src/components/guest/GuestAllowance.tsx`, now "The ones from this visit move with you when you sign in" |
| Tests cover valid, invalid, null, replayed, cross-guest | PASS | 9 new tests in `test_router.py`, all green |

Ticket: FAIL on one criterion.

### T-4.10-07: the two additive `CitationPayload` fields

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| Prove the data exists BEFORE adding the field | PASS | F-4.10-02 in `tracker/phase_4.10.md` records the investigation and its honest negative result: no per-row ingest date exists, so `snapshot_date` is documented as a graph-snapshot proxy, not an ingestion date. The caveat is repeated in `contracts/events.py`'s own comment. |
| Both fields optional, defaulting to `None` | PASS | `contracts/events.py:177-178` |
| `maxLength` on each new string field | PASS | `max_length=32` and `max_length=256`, same lines |
| Producer populates only where the value is real | PASS | `core/graph.py`, `_snapshot_date_for_citation` and `_entity_name_for_citation` both return `None` on every gap case, including the F-2.1-B07 vocabulary-artifact case |
| `frontend/src/lib/events.ts` learns both fields | PASS | `events.ts:121-131` (interface) and `353-354` (the `isCitationPayload` guard actually validates them, so they are not validated-then-discarded) |
| Tests cover present, absent, malformed | PASS | `tests/.../contracts/test_events.py`, `tests/.../core/test_graph.py`, `frontend/src/lib/events.test.ts` (all green) |

Ticket: PASS.

### T-4.10-08: the frontend anonymous path

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| First-time visitor mints and can ask; the `if (!signedIn) → wall` intercept removed | PASS | `frontend/src/App.tsx`, the intercept is gone from `ask`; `phase410Premise.test.tsx` "mints a guest token on the first question an anonymous visitor actually asks" |
| Dots render from the SERVER's count; `setUsed((n) => n + 1)` deleted, not supplemented | PASS | `grep -n "setUsed" frontend/src` returns nothing. `App.tsx` now holds `allowance: AllowanceResponse \| null`, set only from `getAllowance`/`mintGuest`. The gate clause asserts the server value 3/5 renders as "2 searches left", which a client counter incremented once would render as 4. |
| The wall appears only when the server refuses | PASS | `App.tsx` branches on `error.status === 403 && error.reason === "guest_allowance_exhausted"`; two gate clauses cover 403-shows and 429-does-not |
| Guest token passed to signup and login | PASS | `AuthGate.tsx`, `credentials` omits the key entirely when null; two gate clauses cover present and absent |
| F-4.8-P-04 does not regress: no rail for an anonymous visitor, asserted after an ask | PASS | `phase410Premise.test.tsx:229-251` |
| Typecheck clean, production build succeeds, no new axe violation | PARTIAL | Typecheck and build verified clean above. Axe: UNCHECKED, I did not run Playwright. |

Ticket: PASS, with the axe criterion unchecked.

### T-4.10-09: correct the search-limit copy, F-4.9-A-16

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| `AccountMenu` no longer says "unlimited searches"; states the real cap from `GET /v1/allowance` | PASS | `AccountMenu.tsx:184-197`, renders `limitCopy`, no literal number in the component |
| Rail footer says the same thing from the same source | PASS | Both are built from `dailyLimitPhrase` in `lib/guestSession.ts`, computed once in `App.tsx` as `dailyLimitLine`. Structurally unable to disagree. Asserted by the gate clause "read it from the same GET /v1/allowance fetch, not two hardcoded copies". |
| `railCollapsePremise.test.tsx:439` updated, not deleted, guarantee not weakened | PASS | The test survives, renamed, and is now STRONGER: it keeps the email assertion, asserts the real figure, and adds `queryByText(/unlimited searches/i)).not.toBeInTheDocument()`, which the old version did not have |
| If the honest answer is "not counted yet", the copy says so | PASS | `dailyLimitPhrase` branches on `counted`: `false` yields "up to N searches a day" (a limit, not a count), `true` yields "N of M searches left today" |

Ticket: PASS.

### T-4.10-10: the premise gate

| Criterion | Grade | Evidence |
|-----------|-------|----------|
| Written and watched FAILING before any ticket claimed | PASS | Commit `1d65a2c` predates `24632a0`; the file's own docstring records 16 red, 1 pass, and correctly flags that one pass as vacuous |
| Two arms, admit and refuse | PASS | `TestAdmitArm` (5 clauses), `TestRefuseArm` (10), `TestAcceptedBehaviour` (1) |
| States its own coverage | PASS in form, FAIL in accuracy | The docstring's "What this gate covers" claims it covers the AUTH_SECRET-forgery case and "the property a read-then-write implementation silently fails". Neither is true. See F-4.10-J-01 and F-4.10-J-02. |
| Runs the way production runs | PASS | Real FastAPI app over `ASGITransport`, real PostgreSQL, stubbed model harness only |
| Admit: guest completes a real run end to end | PASS | Verified green with the DB reachable |
| Admit: runs 2-5 succeed | PASS | `test_the_allowance_is_five_runs_not_one` |
| Admit: count rises by exactly one per run | PASS | `test_the_server_reported_count_rises_by_exactly_one_per_run` |
| Admit: signup re-points the guest's runs | PASS | `test_signing_up_moves_the_guest_runs_to_the_new_account` |
| Refuse: sixth run is 403 `guest_allowance_exhausted` | PASS | `test_the_sixth_run_is_refused_with_a_reason_a_client_can_branch_on` |
| Refuse: tampered, `AUTH_SECRET`-signed, and expired tokens each rejected 401 | FAIL | The `AUTH_SECRET`-signed clause cannot fail. Proven by mutation. F-4.10-J-01. |
| Refuse: guest token refused by `/auth/me`; access token refused by `decode_guest_token` | PASS | Both clauses real |
| Refuse: guest A cannot read/stop/export guest B's run | PASS | Mutation-verified |
| Refuse: six concurrent requests yield at most five successes | FAIL | The clause cannot fail. Proven by mutation and by direct probe. F-4.10-J-02. |
| Refuse: a migrated, revoked guest token cannot start a new run | PASS | `test_a_migrated_guest_token_cannot_keep_spending` |
| Refuse: a guest is never an operator, no `cost` event | PASS | Mutation-verified |
| Accepted behaviour: clearing the token yields a fresh allowance | PASS | `TestAcceptedBehaviour` |
| Stated non-coverage, four items | PASS in form | The four are stated. A hostile reader would add a fifth: the gate does not state that its concurrency arm is bounded by a second, unrelated cap. See F-4.10-J-02. |

Ticket: FAIL on two criteria.

## Findings

### F-4.10-J-01: the domain-separation clause cannot fail, and the tracker made crediting it conditional on exactly this check

Severity: critical.
Location: `tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py:446-482`.

`tracker/phase_4.10.md` line 8 says, verbatim: "The judge re-runs that one clause against a working guest path with the derivation replaced by bare `AUTH_SECRET` and watches it go red before crediting it." I ran that exact experiment. It does not go red.

Reproduce:

```bash
# 1. Replace the derived key with the bare secret.
#    src/system_03_search_agent/auth/guest.py:104
#    -  return hmac.new(secret.encode("utf-8"), _GUEST_KEY_DOMAIN, hashlib.sha256).digest()
#    +  return secret.encode("utf-8")
python -m pytest tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py -q
# measured: 17 passed in 40.40s
```

The mutation is not inert. It removes the phase's headline security property outright. Under it, a token forged from bare `AUTH_SECRET` for a REAL `guest_sessions` id is fully admitted:

```
decode_guest_token(forged) -> {'guest_id': '8593b4e2-90f5-458a-8c22-239eab5aea74'}
GET  /v1/allowance  with AUTH_SECRET-forged token -> 200 {"kind":"guest","used":0,"total":5,"counted":true}
POST /v1/query      with AUTH_SECRET-forged token -> 202 {"run_id":"0eeffaff-...","persona_name":"Assistant"}
```

Against the unmutated code the same three calls give `ValueError: guest token is invalid`, 401, 401. So the property is real and the mutation reaches it. The gate simply cannot see it.

Root cause, and it is the same shape as F-4.10-03: the clause forges its token for `str(uuid.uuid4())`, an id with no `guest_sessions` row. Even when the signature verifies, `spend_one_run` returns `REVOKED_OR_UNKNOWN` and `app.py:349-355` returns 401. The clause asserts `status_code == 401` and gets one from the unknown-guest path, never from signature rejection. It is a 401-shaped coincidence.

Mitigation, stated so the severity is calibrated honestly: the property IS covered elsewhere. Under the same mutation, `tests/system_03_search_agent/auth/test_guest.py` turns three clauses red (`test_guest_signing_key_is_not_the_bare_auth_secret`, `test_decode_guest_token_invalid_input_signed_with_bare_auth_secret_raises`, `test_domain_separation_survives_even_if_claim_checks_were_bypassed`). The shipped code is correct. What is broken is the gate, its written coverage statement, and the one condition the phase file itself set for crediting it.

Fix direction, not a fix: mint a real guest through `POST /auth/guest`, then forge a token carrying THAT guest_id signed with bare `AUTH_SECRET`. That token differs from a legitimate one only in its signature, so a 401 can then only come from signature rejection.

### F-4.10-J-02: the concurrency clause cannot fail, because a second cap of the same value masks the one it tests

Severity: critical.
Location: `test_phase_4_10_premise.py:574-593`, specifically the assertion at line 588.

`DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 5` (`core/run_registry.py:176`) and `FREE_RUN_ALLOWANCE = 5` (`data/guest_sessions.py:45`) are the same number. The clause fires six concurrent `POST /v1/query` from one guest and asserts `len(accepted) <= 5`. The sixth is refused by the concurrent-run cap before the allowance is ever consulted, so the assertion holds no matter what the allowance implementation does.

Direct probe of the clause's own scenario:

```
0 202  {"run_id":"264f9136-..."}
1 202  {"run_id":"40f5ac9c-..."}
2 202  {"run_id":"6c7bd1fc-..."}
3 202  {"run_id":"e829194a-..."}
4 202  {"run_id":"a10897f1-..."}
5 429  {"detail":{"reason":"concurrent_run_cap_exceeded", ...}}
```

The sixth response is `concurrent_run_cap_exceeded`, not `guest_allowance_exhausted`. The clause's own docstring says it tests "the property a read-then-write implementation silently fails". It does not:

```bash
# Replace the atomic UPDATE in data/guest_sessions.py's spend_one_run with a
# SELECT-then-UPDATE (the exact defect design decision 3 forbids), then:
python -m pytest tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py -q
# measured: 17 passed in 8.95s          <-- the gate does not notice

python -m pytest tests/system_03_search_agent/data/test_guest_sessions.py -q
# measured: 1 failed, 22 passed
# AssertionError: 6 of 6 concurrent spends succeeded; the allowance is not
# being enforced atomically
```

There is a second, independent reason the clause is hollow, and it would still apply if the cap values were changed. `post_v1_query` is `async def` but calls `spend_one_run` synchronously (psycopg2, blocking), with no `await` anywhere between the cap precheck and `create_run`. Six requests gathered on one event loop therefore execute that region strictly serially. No interleaving exists at the layer a read-then-write race lives in, so `asyncio.gather` over an ASGI transport cannot produce the race regardless of the caps.

Mitigation: `tests/.../data/test_guest_sessions.py`'s `ThreadPoolExecutor` test is genuine and catches the defect, as shown above. So the property is verified; the gate's clause is not the thing verifying it, and the gate's coverage statement claims otherwise.

### F-4.10-J-03: `_migrate_guest_session` says "NEVER raises" and can raise, from a threading invariant this phase broke

Severity: major.
Location: `src/system_03_search_agent/auth/router.py:294-360` (the docstring's claim at line 297, the call at line 354) and `src/system_03_search_agent/core/run_registry.py:473-504`.

Three facts, each measured:

1. `signup`, `login` and `create_guest` are plain `def`, not `async def` (`router.py:363,391,503`). FastAPI dispatches a sync path operation to a threadpool. Instrumenting `RunRegistry.reassign_owner` during a real signup that carries a guest token:

```
main/event-loop thread: MainThread
guest run created: 202
signup: 201
reassign_owner ran on thread: {'thread': 'AnyIO worker thread', 'is_main': False}
```

`core/run_registry.py`'s module docstring states the invariant this violates: "No lock guards `RunRegistry._runs` ... Every mutation runs on the single asyncio event loop thread with no `await` between a read and the write it informs, so CPython's GIL makes each individual mutation atomic." That sentence is now false. `reassign_owner` is the first `_runs` mutator that runs off the loop, and nothing in the module or the tests records the change.

2. `reassign_owner:499` iterates `for entry in self._runs.values()` with no guard, while `create_run:591` inserts into the same dict from the event loop. Reproduced in isolation:

```
RuntimeError from reassign_owner's unguarded iteration: ['dictionary changed size during iteration']
```

3. The call at `router.py:354` sits OUTSIDE the `try/except Exception` that closes at line 352. So that `RuntimeError` is not caught. It propagates out of `_migrate_guest_session`, out of `signup`/`login`, and becomes a 500 — after the guest session has already been revoked and committed at line 347. The caller loses their allowance, gets no token, and a retry hits a 409 on the taken email.

This fails T-4.10-06's criterion "migration is best-effort and its failure is logged, never fatal" and contradicts the function's own first line of documentation. It is the pattern-3 case exactly: a confident comment sitting where the last reader stopped checking, with no test asserting the property it claims.

The window is narrow (one signup concurrent with one run creation) but it is not theoretical, and it widens with traffic. Note also that the `except Exception` at line 333 is `noqa: BLE001`'d precisely because "migration must never fail signup/login, any error included" — the intent is documented, the call is just on the wrong side of it.

### F-4.10-J-04: the MCP surface can now raise a run-cap error it has no handler for, and stringifies an internal id into it

Severity: major.
Location: `src/system_03_search_agent/adapters/mcp/server.py:699`, `src/system_03_search_agent/core/run_registry.py:574-580`.

No builder touched `adapters/mcp/server.py`, which is why this slipped. It calls `default_registry.create_run(query_obj, context, run_id=run_id)` with no `owner_id` and no `try/except`. This phase made `create_run` raise `ConcurrentRunCapExceededError` (a `RuntimeError`). Every other failure mode in that handler is converted to a structured `MCPError` (`server.py:294,299,340,575`); this one is not.

The owner namespace is shared: with `owner_id=None`, `create_run:554-556` derives `f"user:{query.user_id}"`, the same string `get_caller` builds for the web surface. So a user with five runs in flight from the browser gets the raw `RuntimeError` on their next MCP tool call, not a 429 and not an `MCPError`.

The exception message is `f"owner {resolved_owner_id!r} already has {active} run(s) in flight..."`, i.e. it embeds the internal namespaced owner id. `tracker/BOARD.md` records F-4.1-J3-01 for build phase 4.1 as "raw exception stringification into an external-facing message". This is that shape again, reintroduced from a different direction.

The same `str(exc)` appears on the web surface at `app.py:379`, inside the 429 detail. There it only returns the caller's own id to the caller, so it is the lesser case, but it is the same habit.

On the allowance question the brief asked about directly: MCP does NOT spend the guest allowance, and it cannot be reached by a guest at all — `_authenticate_mcp_caller` uses `resolve_user_from_bearer_token`, which calls `decode_access_token`, which rejects a guest token on signature. That part is sound. Only the cap error is unhandled.

### F-4.10-J-05: `POST /auth/guest` is an unauthenticated, unthrottled write, against a criterion that says it "carries its own bound"

Severity: minor.
Location: `src/system_03_search_agent/auth/router.py:479-511`.

T-4.10-04's criterion reads: "Both endpoints are rate-limit-considered: minting a guest token is an unauthenticated write, so it carries its own bound." What shipped is a 20-line comment considering the bound and deferring it to build phase 6.0. `grep -n "middleware\|rate_limit\|limiter"` over `app.py` finds only `CORSMiddleware`. There is no bound.

The comment's own argument for why this is acceptable is that the clearable-token decision already lets a determined caller get a fresh allowance. That is true for allowance abuse and does not cover the other thing an unbounded unauthenticated write does: each call inserts a `guest_sessions` row, and nothing prunes them. This is unbounded storage growth from an anonymous caller.

Filed as minor because the reasoning is documented and the deferral is deliberate, not as a pass, because the criterion as written is not met.

### F-4.10-J-06: a docstring claims a defensive backstop that does not exist

Severity: minor.
Location: `src/system_03_search_agent/adapters/web_sse/app.py:217-225`.

`_guest_uuid_from_owner_id`'s docstring says "the ValueError path exists as a defensive backstop, never expected to fire in practice." There is no `except`. Line 225 is a bare `return uuid.UUID(owner_id.split(":", 1)[1])`. If it ever fires, the result is an uncaught 500, not a backstop.

The precondition is genuinely hard to violate (`decode_guest_token` only requires `guest_id` to be a non-empty string, not a UUID, but only the server mints guest tokens), so this is not currently reachable. It is filed because a comment asserting a safety property the code does not implement is the pattern this repository has been bitten by.

### F-4.10-J-07: a revoked guest session is reported as a live, counted allowance

Severity: minor.
Location: `src/system_03_search_agent/adapters/web_sse/app.py:227-241`.

After migration, `revoked_at` is set but the token still decodes and `get_caller` still admits the Principal. `GET /v1/allowance` reads only `runs_used` and returns `{kind: "guest", used: N, total: 5, counted: true}` with no indication the session can no longer spend. `counted: true` is design decision 6's honesty field, and here it asserts the count is real for an allowance that is unusable: the very next `POST /v1/query` returns 401 "this guest session is no longer valid".

Low impact in practice because `App.tsx` clears the guest token at sign-in. It matters because this endpoint's stated purpose is "to describe the allowance honestly".

### F-4.10-J-08: `tracker/phase_4.10.md` still says the builders have not been dispatched

Severity: minor.
Location: `tracker/phase_4.10.md:6` and every ticket's Status/Evidence block.

Line 6 reads "Status: OPEN. Decomposed, premise gate written and WATCHED FAILING, 16 of 17 red. Builders not yet dispatched." Three commits have landed. All ten tickets read `Status: todo`, every `Evidence:` block reads `(filled at close)`, and every breakdown checkbox is unticked, including T-4.10-10's, which is demonstrably done.

`tracker/BOARD.md` WAS updated (`todo` to `in-progress`, `tech_refine` to `refined`), so the two tracker files now disagree with each other. This is why the per-ticket grading above had to be done entirely from code: the file that is supposed to carry the evidence carries none.

### F-4.10-J-09: the doc-drift gate fails

Severity: minor.
Command: `python tracker/check_doc_drift.py --check`, exit 1.

```
AGENTS.md:16: says 2565 python tests (computed: 2670)
AGENTS.md:16: says 155 frontend tests (computed: 169)
CLAUDE.md:16: says 2565 python tests (computed: 2670)
CLAUDE.md:16: says 155 frontend tests (computed: 169)
requirements/phase_6/Continuation_prompt.md:96: says 2565 python tests (computed: 2670)
requirements/phase_6/Continuation_prompt.md:97: says 155 frontend tests (computed: 169)
error: 10 facts computed | 6 stale | 0 structural
```

`verify` and `phase-checkpoint` both gate on this, so it must be green before the phase closes. Filed as minor because the checkpoint has not run yet; noted because the brief asked for any measured number that disagrees with a stated one.

### F-4.10-J-10: an accepted race is documented that cannot occur, which is not free

Severity: minor.
Location: `src/system_03_search_agent/adapters/web_sse/app.py:279-311`.

The 33-line comment above the cap precheck names "a narrow, accepted gap": two concurrent requests from the same caller racing between the precheck and the spend. That race is not reachable. `post_v1_query` is `async def` and contains no `await` between the precheck at line 313 and `create_run` at line 370 (`spend_one_run` is synchronous psycopg2). One event loop, no yield point, no interleaving.

Not a defect in behaviour. Filed because a documented "accepted race" is a standing instruction to a future reader not to look, and because the same fact (no await, therefore no interleaving) is half of why F-4.10-J-02's concurrency clause is hollow. The blocking database call inside an async handler is itself worth a look under load: it serializes the whole event loop for the duration of the spend.

## What I checked and found clean

Recorded so the coverage of this review is arguable rather than assumed.

- Token confusion, both directions, and every edge case named in the brief. Probed directly against the primitives: `typ=""`, `typ=None`, `typ=123`, `typ=["guest"]`, `typ="access"`, `alg: none`, a wrong algorithm (HS384), an `exp` 400 days out, a genuine access token, and a genuine guest token cross-presented. All rejected. Two acceptances, both correct: a guest token carrying an extra `user_id` claim decodes as a guest and that claim is discarded (`Principal.user_id` is hardcoded `None`); an access token carrying `typ: "guest"` decodes as an access token, which is what it is.
- Namespaced ids reaching a bare-UUID consumer. Grepped every reader of `Query.user_id`, `RunEntry.user_id` and `is_operator_user`. `RunEntry.user_id` now has no readers at all outside its own assignment. `caller.user_id` is the only value reaching `is_operator_user` and `Query.user_id`, and it is `None` or a bare UUID by construction.
- Whether MCP bypasses the allowance. It cannot: a guest token never authenticates there.
- Migration cross-guest, replay, invalid, expired and null cases. All covered by real tests in `test_router.py`, all green.
- Whether anything logs a token, key or decoded payload. Nothing does; every log line and every `raise` uses a fixed literal or an integer count.
- Alembic 0003's downgrade. `upgrade()` creates one table; `downgrade()` drops it; `test_downgrade_base_removes_every_table_index_and_extension` proves it with `guest_sessions` now in `ALL_TABLES`. 9/9 green against a live database.
- The three lead-authored edits I was told to scrutinize hardest:
  - `test_migration.py`'s `-1` to `"0001_user_data_schema"` retarget: legitimate. Every assertion is unchanged; `-1` meant "one back from head" and adding 0003 moved head. The explicit revision id cannot drift.
  - `ALL_TABLES` gaining `guest_sessions`: a strengthening, not a weakening. It makes both the upgrade assertion (line 166) and the downgrade assertion (line 359) require the new table.
  - The `_ALLOWED_RESPONSE_KEYS` edit in `test_phase_4_1_premise.py`: legitimate, and the accompanying `test_the_two_phase_4_10_citation_fields_are_really_on_the_wire` is a real positive pin, not decoration. The negative test (`spend_usd`/`tokens_billed`) still fails the allowlist.
  - The new anti-fabrication clause in `phase410Premise.test.tsx`: REAL, and I verified it rather than taking the report's word. Forcing a fabricated cited source into `AnswerScreen` turns it red. Its `answer-meta` wait is a genuine positive anchor.
- `phase48Premise.test.tsx` clause 3e's removal of `expect(createRunSpy).not.toHaveBeenCalled()`: not a weakening. That line encoded "anonymous callers never reach the backend", which this phase deliberately makes false, and it was replaced by a stronger positive assertion that the call happened with a guest token specifically.
- `railCollapsePremise.test.tsx`'s updated footer clause: strengthened, not weakened. It keeps the email assertion, asserts the real figure, and adds a negative assertion the old version lacked.
- Mutations that DID fire, so the gate is not hollow everywhere: `_get_owned_run` comparing `user_id` instead of `owner_id` (turns the cross-guest clause red), and forcing `is_operator = True` (turns the operator clause red).

## What a hostile reader would still say is uncovered

Beyond the four items the gate itself declares:

- The gate's concurrency arm does not state that it is bounded by a second, unrelated cap of the same value. That omission is what let F-4.10-J-02 read as coverage.
- Nothing anywhere asserts that `_migrate_guest_session` does not raise. A test that patches `reassign_owner` to raise and asserts signup still returns 201 would have caught F-4.10-J-03.
- No test exercises the MCP surface at the concurrent-run cap, which is how F-4.10-J-04 stayed invisible.
- No test asserts that `run_registry`'s single-thread invariant still holds, which is reasonable, because until this phase nothing could break it.
