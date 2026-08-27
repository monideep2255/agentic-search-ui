# Build phase 4.13 judge report: durable cross-reload search history

Branch: `phase/4.13-durable-history`. Graded at `97a7cbb`, five commits ahead of `develop`.
Judge round run 2026-08-27, from fresh context, against the code and the tests rather than against any summary.

## Verdict: FAIL

One reachable major introduced by this phase blocks it under the merge bar: F-4.13-A-01, a revoked guest credential that `GET /v1/history` serves while every sibling route on the same surface refuses it. Reproduced independently by this judge, not accepted from the adversary's report.

Everything the phase set out to control, it controls. Ownership scoping is correct and mutation-proven, the F-4.5-A-02 shape is caught, the premise gate is strong, and the fix commit under extra scrutiny is sound. The defect is one layer above the one the phase named: whether the caller was entitled to claim the `owner_id` it presented at all.

## Table of contents

- [What was graded, and how](#what-was-graded-and-how)
- [Grading item 1: correctness of the read path](#grading-item-1-correctness-of-the-read-path)
- [Grading item 2: the production and AI security gates](#grading-item-2-the-production-and-ai-security-gates)
- [Grading item 3: plan adherence against the done-when](#grading-item-3-plan-adherence-against-the-done-when)
- [Grading item 4: the gate itself, by mutation](#grading-item-4-the-gate-itself-by-mutation)
- [Grading item 5: commit ebb62f4, the same-session fix](#grading-item-5-commit-ebb62f4-the-same-session-fix)
- [Independent reproduction of the adversary's load-bearing findings](#independent-reproduction-of-the-adversarys-load-bearing-findings)
- [Findings filed by this judge](#findings-filed-by-this-judge)
- [Ticket dispositions](#ticket-dispositions)
- [Suite and gate evidence](#suite-and-gate-evidence)
- [Tree cleanliness](#tree-cleanliness)

## What was graded, and how

Read in full: `src/system_03_search_agent/feedback/history.py`, the `GET /v1/history` block in `adapters/web_sse/app.py`, `feedback/writer.py`'s `_caller_owns_row` and its degraded-row path, `auth/dependencies.py`'s `Principal`, the premise gate, both new Python test files, the frontend diff, and the Playwright spec.

Measured, never asserted: 22 mutations applied one at a time to the two product files, each restored byte-identically and verified by SHA-256 before the next. The harness is `scratchpad/mutate.py`; it holds the original bytes in memory, writes the mutant, runs the three test files, writes the original back, and asserts the hash matches.

## Grading item 1: correctness of the read path

PASS.

Ownership is scoped on the fact, not a proxy. `feedback/history.py:141`:

```python
.where(Interaction.owner_id == owner_id)
```

One direct string equality on the column capture recorded, matching `feedback/writer.py:456`'s `_caller_owns_row` (`row.owner_id is not None and row.owner_id == owner_id`) rather than deriving anything from `user_id`. `adapters/web_sse/app.py`'s handler passes `caller.owner_id`, the namespaced `user:<uuid>` or `guest:<uuid>` string from `auth/dependencies.py:163`, never `caller.user_id`.

The NULL-row claim in the module docstring (`history.py:25-31`) is true rather than merely confident: SQL's own `NULL = 'guest:...'` semantics exclude a pre-migration row, and the premise gate proves it with a paired control (`test_a_row_with_no_owner_is_returned_to_nobody`).

The F-4.5-A-02 shape is caught, not just avoided. Mutation M15 rewrote the handler to `list_history(owner_id=caller.user_id or "guest", limit=limit)`, the exact defect build phase 4.5 shipped:

```
M15-f45-shape-user-id-or-guest: CAUGHT 1/1 | 1 failed, 2 warnings in 2.85s
```

Removing the WHERE clause entirely, and weakening it to `is_not(None)` so every owned row goes to everybody, are both caught:

```
M1-drop-owner-where:         CAUGHT 1/1
M2-owner-where-to-isnotnull: CAUGHT 1/1
```

Field bounds cannot 500 on read. `HistoryItem.question` is `max_length=2000` and `InteractionRow.query_text` is `max_length=2000` (`feedback/contracts.py:180`); the degraded-row path substitutes the constant `PAYLOAD_DROPPED_TEXT` and keeps `owner_id` (`writer.py:294`, `:290`), and `_storable`'s replacement is a single code point (`_REPLACEMENT_CHARACTER = "�"`, `writer.py:164`), so no write path can widen a stored value past the read bound. `TrustSignal` is four literals of at most six characters against `max_length=20`. See F-4.13-A-02 for why that exact equality is nonetheless fragile.

## Grading item 2: the production and AI security gates

PASS, with one unguarded invariant filed as F-4.13-J-04.

- Parameterised queries, no f-string or `.format()` in any query: PASS. `history.py` builds no SQL text at all; it issues a SQLAlchemy `select()` construct. The only two f-strings in the file are `ValueError` messages at `:125` and `:130`. `grep -c '\.format(' feedback/history.py` returns 0.
- `max_length` on every string and a bounded list: PASS in the code. `HistoryItem` bounds `trace_id` (64), `question` (2000) and `trust_signal` (20); `HistoryResponse.items` carries `max_length=MAX_LIMIT`; both models set `extra="forbid"`.
- Input validation for valid, invalid and null: PASS, measured. Every bound is enforced and every enforcement is caught by a test: `M9` (boundary flip on the owner-id length check), `M11` and `M12` (the limit guards), `M16` (dropping `le=MAX_LIMIT`), `M17` (silently clamping instead of refusing), `M18` (dropping `ge=1`), `M19` (default drift) all go red. The 422 names the bound, satisfying `tool-call-budgets`' actionable-error requirement.
- No credential or DSN in any log line or exception string: PASS. `git diff develop...HEAD -- src/` contains no added line matching `log`, `print`, `secret`, `token`, `dsn`, `password`, `str(exc)` or `USER_DB_URL`. `feedback/history.py` performs no logging and catches no exception.
- Least privilege: PASS. The route is read-only and `Depends(get_caller)` gates it; an unauthenticated caller gets 401, not an empty 200, proven by the gate's own arm.

Not gated: the bounds above are present but asserted by no test (F-4.13-J-04).

Pre-existing, not this phase's: an `OperationalError` from `session_scope()` propagates uncaught out of `get_v1_history`, and `writer.py:385-392` documents that such an exception can carry the DSN in its own message. The sibling `get_v1_allowance` has the identical exposure through `Depends(get_session)`, so this is the surface's standing posture rather than a regression. Recorded here, not filed against this phase.

## Grading item 3: plan adherence against the done-when

PARTIAL, and the gap is the product owner's, already decided.

The done-when, from the premise gate's module docstring:

> A person's searches survive closing the browser: a caller who has run queries gets exactly their OWN past questions back on a fresh client carrying the same identity, never anyone else's, and a guest's searches follow them into the account they create.

Every clause of that sentence is delivered and proven, on the server. What is not delivered is the phase's own product-level sentence, "a person asks a question, closes the browser, comes back", because no visitor's browser carries an identity that reaches the rail. Verified independently rather than read off the finding:

- `git show develop:frontend/src/App.tsx` line 161 already held `const [token, setToken] = useState<string | null>(null)`, so the account token living only in React state is pre-existing, not introduced here.
- The only persisted credentials in `frontend/src` are `guestSession.ts:46` (the guest token) and `guestSession.ts:99` (a migration marker). No access or refresh token is persisted anywhere.
- `App.tsx:409`: `const railAvailable = signedIn && screen === "search" && searchView.name !== "signin";` so the one principal whose identity does survive a reload never sees a rail.

So an account keeps the rail and loses the identity; a guest keeps the identity and gets no rail. F-4.13-02 names the first half, F-4.13-A-05 names the composition. The product owner has decided on the record that the phase merges with F-4.13-02 open and "keep me signed in" becomes its own scoped work. That decision is respected here and is not re-litigated: it is a scope call, not a defect in the delivered work.

The tickets each satisfy their own acceptance criteria. The set of them does not satisfy the product sentence, and the phase says so in its own coverage statement rather than leaving it invisible, which is the behaviour the harness asks for.

## Grading item 4: the gate itself, by mutation

PASS on the premise gate. 22 mutations, 19 caught, 3 missed. Every miss is filed.

| Mutation | Result |
|---|---|
| M1 drop the owner WHERE clause | CAUGHT 1/1 |
| M2 owner WHERE to `is_not(None)` | CAUGHT 1/1 |
| M3 order ascending | CAUGHT 1/1 |
| M4 drop the `id` tiebreaker | CAUGHT 10/10 |
| M5 drop the SQL LIMIT | CAUGHT 1/1 |
| M6 SQL `LIMIT MAX_LIMIT` plus a Python slice | MISSED 0/1, F-4.13-J-03 |
| M7 drop the empty-`owner_id` guard | CAUGHT 1/1 |
| M8 drop the over-long-`owner_id` guard | CAUGHT 1/1 |
| M9 owner-id bound `>` to `>=` | CAUGHT 1/1 |
| M10 `citation_count` always zero | CAUGHT 1/1 |
| M11 drop the `limit > MAX_LIMIT` guard | CAUGHT 1/1 |
| M12 drop the `limit < 1` guard | CAUGHT 1/1 |
| M13 return `trace_id` as the question | CAUGHT 1/1 |
| M14 constant `trust_signal` | CAUGHT 1/1 |
| M15 the F-4.5-A-02 shape (`caller.user_id or "guest"`) | CAUGHT 1/1 |
| M16 drop `le=MAX_LIMIT` | CAUGHT 1/1 |
| M17 silently clamp instead of refusing | CAUGHT 1/1 |
| M18 drop `ge=1` | CAUGHT 1/1 |
| M19 default limit drift 20 to 35 | CAUGHT 1/1 |
| M20 drop every `max_length` on `HistoryItem` | MISSED 0/1, F-4.13-J-04 |
| M21 drop `max_length` on `HistoryResponse.items` | MISSED 0/1, F-4.13-J-04 |
| M22 drop `extra="forbid"` on `HistoryItem` | MISSED 0/1, F-4.13-J-04 |

The populate-check is real on every bound arm, not decorative. `_row_owner` (`test_phase_4_13_premise.py:376-396`) reads the seeded row's stored owner straight from the table and asserts the row exists before any isolation assertion runs, and every isolation clause asserts BOTH controls held before asserting the refusal. An implementation returning `{"items": []}` to everybody fails the durability arm rather than passing the isolation arm, which is the property the file's own "why this gate has two arms" section claims and delivers.

The gate's coverage statement is the strongest artifact in this phase. It names five omissions including the sharpest one against itself, that it holds one bearer token in a Python variable across two clients, which is what no browser does.

The one omission it does not name, and could not have derived from its own arms, is guest-session revocation: nothing in this file asks whether the credential presenting an `owner_id` is still a credential the server recognises. That is F-4.13-A-01's blind spot as much as the code's.

## Grading item 5: commit ebb62f4, the same-session fix

PASS. Reviewed harder than the original code, per instruction, and it holds.

`git show ebb62f4 --stat` touches three files and no product code. The two corrections are real, not cosmetic:

- The premise-gate arm was renamed from `test_the_list_is_newest_first_and_the_order_is_total` to `test_the_list_reads_newest_first`, and its docstring now claims only newest-first with an explicit pointer to the clause that owns the rest. Verified: `M3-order-ascending` catches this arm, `M4-drop-id-tiebreaker` correctly does not, matching what the docstring now says.
- The unit clause was raised from two tied rows to six (`_TIED_ROW_COUNT = 6`), with the expected order read back from the actual `id` values rather than assumed from insertion sequence. Verified at 10 of 10 under mutation, against the 3 of 10 the lead measured before the fix:

```
M4-drop-id-tiebreaker: CAUGHT 10/10 | 1 failed, 14 passed, 2 warnings in 4.43s
```

And exactly one clause does the catching, which is what the corrected docstrings claim:

```
FAILED tests/system_03_search_agent/feedback/test_history.py::test_order_is_total_when_created_at_collides
1 failed, 31 passed, 2 warnings in 4.00s
```

F-4.13-01 is CLOSED, verified.

Two residues of the same claim survived the fix, both filed. The commit corrected the overclaim in the gate's docstring and in the file's coverage statement, and left it standing in the product module's docstring (F-4.13-J-01) and in the arm's own failure message (F-4.13-J-02). The first is the one that matters: `feedback/history.py:112-113` still points a reader at an arm that no longer exists, for a property that arm was proven not to test. A confident comment is where the next reader stops checking, which is the reason this class is filed rather than waved through.

## Independent reproduction of the adversary's load-bearing findings

Ten adversary findings landed in `tracker/phase_4.13.md` while this round ran. The three claimed LIVE-REACHABLE that would change the verdict were reproduced from scratch by this judge, against the real app over `ASGITransport` and the real `search_agent_users` database. Script: `/tmp/judge_verify.py`.

F-4.13-A-01, CONFIRMED, and this is the blocker. One guest credential, one run, two routes:

```
deleted 1 guest_sessions row(s) for af967b50-d22d-414c-86aa-86af4375016a
GET /v1/allowance -> 401 {"detail":{"reason":"guest_session_revoked","message":"this guest session is no longer valid"}}
GET /v1/history   -> 200 {"items":[{"trace_id":"judge-05dbc94af51a...","question":"GHOST GUEST QUESTION 664d3b","asked_at":"2026-08-27T12:12:11.584030-04:00","trust_sig...
```

`get_caller` verifies the JWT signature and stops there; the `guest_sessions` liveness check is written inline per route (`get_v1_allowance` refuses on `row is None or row[0] is not None`). This phase added the third reader of a guest identity on this surface and did not join that pair. A credential the server has revoked still answers questions about the principal it names. Reachable, major, and introduced here.

F-4.13-A-04, CONFIRMED. Person B, signing up at person A's browser while A's guest token is still in `localStorage` by the standing F-4.10-A-05 decision, is served A's question:

```
signup(with A's guest token) -> 201
person B GET /v1/history -> 200; sees A's question: True
items: ['PERSON A am I a BRCA1 carrier 4c8d29']
```

The reassignment is build phase 4.6's and the guest-token persistence is build phase 4.10's product-owner decision. What this phase changes is that the transfer stopped being invisible bookkeeping and became a list of another person's biomedical questions on screen. Reachable, major, and a product-owner call rather than a fix inside `history.py`.

F-4.13-A-03, CONFIRMED in its conclusion, with its evidence CORRECTED. The adversary reported exactly two indexes on `interactions`; there are seven. None is on `owner_id`, so the conclusion stands and the plan is what it claimed:

```
interactions rows: 22569
indexes: ['interactions_pkey', 'interactions_trace_id_key', 'idx_interactions_created_at',
          'idx_interactions_user_id', 'idx_interactions_rubric',
          'idx_interactions_coverage_tags', 'idx_interactions_query_trgm']
Limit  (cost=1826.86..1826.87 rows=2) (actual time=10.553..10.555 rows=0 loops=1)
  ->  Sort  (cost=1826.86..1826.87 rows=2) (actual time=10.552..10.552 rows=0 loops=1)
        Sort Key: created_at DESC, id DESC
        ->  Seq Scan on interactions  (cost=0.00..1826.85 rows=2) (actual time=10.511..10.511 rows=0 loops=1)
              Filter: (owner_id = 'guest:does-not-exist'::text)
```

Every call sequentially scans and sorts the whole append-only capture table. One caller's cost scales with every row every user has ever had captured. The fix is one index in one migration.

F-4.13-A-02, severity CORRECTED to major/LATENT rather than live-reachable. The behaviour is real (an eager `HistoryItem` construction turns one non-conforming row into a 500 for the caller's entire history, with no partial degradation). The trigger is not: the adversary's own reason cell concedes no shipped surface can write a row that violates the bound, so the row must be placed by a database write or a future widening. It does not block under the merge bar; the underlying fragility, an exact equality between two bounds in two modules that do not reference each other, with no database constraint behind either, is real and worth fixing.

The remaining adversary findings (A-05 through A-10) are read as filed. A-06 and A-09 in particular are correct and cheap: the coverage statement says fifty where the shipped default path delivers twenty, and `count` is the page size under a name that reads as a total.

## Findings filed by this judge

All four are minor and latent. None blocks. Each has an owner in the tracker's Findings table.

- F-4.13-J-01: `feedback/history.py:112-113` points at `test_the_list_is_newest_first_and_the_order_is_total`, an arm ebb62f4 renamed out of existence, and claims it "exercises directly" the total-order property F-4.13-01 established that arm cannot test. The same overclaim was corrected in two other files by the same commit and left standing in the product module.
- F-4.13-J-02: `test_phase_4_13_premise.py:486`, the failure message of the corrected arm, still reads "and the order must be total so rows sharing a timestamp do not shuffle". The docstring was fixed; the message a failing reader actually sees was not.
- F-4.13-J-03: `test_limit_is_a_real_sql_limit_and_returns_the_newest`, and the coverage bullet at `test_history.py:19`, claim the LIMIT is "real SQL, not a Python slice". Mutation M6 replaced the SQL limit with `.limit(MAX_LIMIT)` plus a Python slice and all 32 tests stayed green. The claim is a static property of the source, like the f-string bullet the same file already declares unprovable at runtime, and should be declared the same way.
- F-4.13-J-04: the response-model bounds `app.py`'s own comment invokes by name ("`production-standards`' multi-agent pipeline gate applies here exactly as it does to every other response model") are asserted by no test. M20, M21 and M22 stripped every `max_length`, the list bound, and `extra="forbid"`, and all 32 tests stayed green. A comment asserting a security property with no test asserting the same property is the liability `self-eval-loop` names.

## Ticket dispositions

| Ticket | Judge disposition | Reason |
|---|---|---|
| T-4.13-01 | NOT moved (was `in-progress`, not `in-review`) | The deliverable is correct and mutation-proven; the owner may move it to `in-review` for closure |
| T-4.13-02 | NOT done | F-4.13-A-01 is a defect in this ticket's own deliverable: the endpoint admits a credential the server has revoked |
| T-4.13-03 | NOT moved | F-4.13-A-07's reducer interaction is against `App.tsx` and unresolved |
| T-4.13-04 | `in-review` to DONE | Every acceptance criterion met and measured: 11 arms, populate-check on every bound arm, both isolation directions for guests and accounts, the NULL-owner refusal, durability through a real driven run, the guest-to-account handover, the limit bound, and a coverage statement that names five omissions including one against itself. 19 of 22 mutations caught; the three misses are filed as F-4.13-J-03 and F-4.13-J-04 and are coverage-statement gaps, not criterion failures |
| T-4.13-05 | NOT moved | Vitest covers seed, merge-without-duplicate, degraded fetch and the identity switch; the re-ask case F-4.13-A-07 describes is uncovered |
| T-4.13-06 | `todo`, unchanged | Doc drift is red, expected while this ticket is open |

## Suite and gate evidence

Phase tests, all 32, no skips:

```
32 passed, 2 warnings in 4.55s
```

Full Python suite on the branch:

```
4098 passed, 159 skipped, 1 xfailed, 5 warnings in 115.70s (0:01:55)
```

Frontend vitest:

```
Test Files  18 passed (18)
      Tests  226 passed (226)
```

Frontend production build: `build exit=0`, `dist/assets/index-olpoptMP.js 393.65 kB`.

Section 24 gates, run exactly as `.github/gates/` defines them:

| Gate | Result |
|---|---|
| 1 compile and import | Environmental only: the local venv has no `pip install -e .`. Proven equivalent with `PYTHONPATH=src:.`, which compiles all of `src services tests alembic` and imports the three named modules: `gate01 equivalent: OK` |
| 2 import order | `exit=0`. `app.py` sits in isort's `extend_skip` by design (`pyproject.toml`), with ruff's `I001` still policing it |
| 3 lint | `exit=0`, `All checks passed!` |
| 4 unit suite | `exit=0`, `4098 passed, 136 skipped, 23 deselected, 1 xfailed` |
| 4b no unsanctioned skips | `exit=0`, `ok: 4235 test cases, every skip sanctioned` |
| 9 required paths | `exit=0`, `27 passed`, none skipped |
| 8 frontend build and test | Script expects CI's working directory; run directly, vitest is 226 of 226 and the build exits 0 |

Doc drift, expected red while T-4.13-06 is open:

```
error: 10 facts computed | 10 stale | 0 structural
```

## Tree cleanliness

Every one of the 22 mutations was restored byte-identically. The harness asserts a SHA-256 match on restore before proceeding, and the product tree is verified clean against `HEAD`:

```
$ git diff HEAD --stat -- src/ tests/ frontend/
(no output)
```

`git status --short` shows only this judge's sanctioned writes plus two junit artifacts produced by running gates 4 and 9 (`unit-results.xml`, `required-paths.xml`), which are CI outputs, are untracked, and are not gitignored. They are reported rather than deleted.
