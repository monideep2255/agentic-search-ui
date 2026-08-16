# Build phase 4.10 independent verification report

Branch: `phase/4.10-guest-allowance`
Scope: the per-guest attempt ceiling and everything the last two commits touched. `data/guest_sessions.py`, `core/run_registry.py`'s refusal callback, `adapters/web_sse/app.py`'s refusal paths and `GET /v1/allowance`, `harness/cost_control.py`'s `anon_daily_run_cap` and `_MIN_ANON_DAILY_CAP_MULTIPLE`, `alembic/versions/0005_guest_attempts.py`, and the clauses in `test_phase_4_10_premise.py`, `test_guest_sessions.py` and `test_cost_control.py` that guard them.
Verifier: independent, files and running code only, fixes nothing. Ran no git command. Every mutation applied to a source file was restored and the restore verified by SHA-256 comparison against the pre-mutation bytes.
Date: 2026-08-15.

## Verdict

FAIL.

Six findings: 1 critical, 0 major, 3 moderate, 2 minor.

The mechanism work is correct and I could not break it. The attempt ceiling holds under true OS-thread concurrency at its own boundary, the refund cannot fire twice or without a genuine guardrail refusal, neither counter can be driven out of range, the one-transaction spend survives both a raising daily statement and a dropped connection, and the charged/uncharged signal is right in both directions and never reaches the wire. Ten mutations, every one confirmed to reach the code path, all red. I found no added assertion that cannot fail.

What fails is the same thing that failed in each of the last three rounds, one layer above the mechanism. `ATTEMPT_ALLOWANCE = 10` bounds an identity. Nothing bounds a source, and the shipped mint throttle hands one source 60 identities a minute against a day that 20 identities can exhaust. One apparent source took the entire anonymous product offline in 1.56 seconds, against the shipped defaults, with the throttle live and zero mints refused. F-4.10-R-01 measured 1.68 seconds. The fix multiplied the attacker's mint count by 20 and left the wall-clock time and the outcome unchanged.

## Gates, measured

Every number is from a command run on this branch.

| Gate | Command | Result |
|------|---------|--------|
| Python suite | `python -m pytest tests/ -q` | 6 failed, 2593 passed, 113 skipped, 1 xfailed, 260.66s. All 6 failures are `synthesis/test_citation_trust_full_premise.py`, the known live-network-gated set. Matches the expected baseline exactly. |
| Backend premise gate | `python -m pytest .../test_phase_4_10_premise.py -q` | 32 passed, 8.75s. PostgreSQL reachable, so the `pytestmark` skip did not fire and the gate genuinely ran. |
| Guest data and cost control | `python -m pytest .../test_guest_sessions.py .../test_cost_control.py -q` | 109 passed, 5.88s |
| Frontend unit | `cd frontend && npx vitest run --maxWorkers=2` | 12 files, 177 tests, all passed, 67.43s, clean on the first run |
| Lint | `ruff check src/ tests/` | 5 errors. Pre-existing, matches the baseline the judge and re-review both recorded. |
| Doc drift | `python tracker/check_doc_drift.py --check` | `ok: 10 facts computed | 0 stale | 0 structural`, exit 0. F-4.10-R-08 is closed. |
| Playwright e2e | not run | UNCHECKED. Reported as unchecked, never as passing. `tracker/phase_4.10.md`'s close line claims "Playwright 30 of 30 including the full axe sweep"; that claim is not verified by this round. |

## Findings

### F-4.10-V-01: the attempt ceiling bounds an identity, nothing bounds a source, and one source still takes the anonymous product offline in 1.56 seconds

Severity: CRITICAL.
Location: `src/system_03_search_agent/data/guest_sessions.py:58-71` (the `ATTEMPT_ALLOWANCE` rationale), `src/system_03_search_agent/harness/cost_control.py:138-145` (`_MIN_ANON_DAILY_CAP_MULTIPLE`), `src/system_03_search_agent/auth/router.py:157,175` (`_MINT_THROTTLE_WINDOW_S`, `_MINT_THROTTLE_MAX_PER_WINDOW`), `env.example:118`.

The F-4.10-R-01 fix rests on one sentence, written at `guest_sessions.py:63-65`:

> Ten rather than fifty because this is the only per-identity bound on how much of the SHARED daily budget one anonymous caller can move: at ten, draining a 200-run day needs 20 mints instead of one, which is a burst the per-source mint throttle can see.

The throttle cannot see it. `_MINT_THROTTLE_MAX_PER_WINDOW = 60` over `_MINT_THROTTLE_WINDOW_S = 60`, so one source is handed 60 guest identities a minute. Draining the shipped 200-run day needs 20. Twenty is a third of the allowance, so the throttle never fires, and a fixed window means 120 across a boundary.

The arithmetic, computed from the shipped constants:

```
ATTEMPT_ALLOWANCE            = 10
_MIN_ANON_DAILY_CAP_MULTIPLE = 10
shipped ANON_DAILY_RUN_CAP   = 200
mint throttle                = 60 per 60s per source
identities needed to drain   = 20
throttle fires?              = False
cap at which the throttle would fire = > 600 runs/day
attempt ceiling at which the shipped cap needs > 60 mints = < 3.33
```

Measured end to end against the real FastAPI app over `ASGITransport`, the real `search_agent_users` database, the same stub set as the premise gate, `ANON_DAILY_RUN_CAP=200` (the shipped `env.example` value), the mint throttle LIVE and never reset mid-attack:

```
D1 cap=200 attempt_ceiling=10 -> 20 mints
D1 mints=20 throttled_mints=0 accepted_runs=200 day_used=200/200 in 1.56s
D1 victim mint status=201
D1 VICTIM query status=429 {'reason': 'anon_daily_cap_reached', ...}
D1 VICTIM allowance={'kind':'guest','used':0,'total':5,'counted':True,
                     'blocked_reason':'anon_daily_cap_reached'}
```

Reproduction:

```
repeat 20 times:
    POST /auth/guest                       (201 every time; 20 < 60)
    repeat 10 times:
        POST /v1/query {"text": "Should this patient be started on tamoxifen
                                 given her BRCA1 status?"}
        drain the run
then: mint a 21st guest, ask any legitimate question -> 429 until UTC midnight
```

The text matters and is the second half of the finding. `_INJECTION_REFUSAL_TEXT` is refused by the pre-filter with `charged=False`, so the new day refund gives the slot back and the attack does not work with it. `_PAID_REFUSAL_TEXT` is the `forbidden.screen` ADV-01 shape: refused AFTER a real Guard-tier call, so `charged=True`, the day stays charged by design, and the guest's own ANSWER is refunded. Each identity therefore converts all ten of its attempts into ten permanent day charges while its own allowance never moves. The fix's own asymmetry is the delivery mechanism.

Three further things this establishes, each worth naming separately:

- Two shipped controls are in direct structural conflict. Making 20 mints throttled requires `_MINT_THROTTLE_MAX_PER_WINDOW < 20`. The premise gate's own admit arm, `TestMintThrottleHasBothArms::test_an_ordinary_shared_address_is_not_refused`, asserts 25 consecutive mints from one source all return 201. The gate pins the throttle above the number the attack needs, so no throttle value satisfies both today.
- The `_MIN_ANON_DAILY_CAP_MULTIPLE = 10` rationale is false in the same way: "it takes ten determined callers rather than one to deny the product to everyone else, and the mint throttle is what stands in front of that." It takes ten *identities*, not ten *callers*, and the throttle stands in front of nothing at these values.
- `tracker/phase_4.10.md:10` states at close: "an anonymous caller could start 200 paid pipelines in 1.68 seconds and take the product offline for everyone else for the rest of the day. That is now 10." An anonymous caller can still start 200. An anonymous *identity* is now capped at 10. The sentence the phase closes on is not true as written.

Why the gate did not see it. `TestOneGuestCannotTakeTheAnonymousProductOffline`'s coverage statement declares the omission out loud: "NOT exercised here: the attack from MANY minted identities, which is `TestAnonymousSpendIsBounded` above and is bounded by the daily ceiling plus the mint throttle rather than by the attempt counter." The deferral is the hole. `TestAnonymousSpendIsBounded` proves the daily ceiling exists and refuses past it; it never asks whether one source can reach it. The declaration was made honestly and pointed at a clause that does not answer the question. This is the second consecutive round in which a coverage statement named the very omission that hid the critical, and the third consecutive round in which the worst defect sits inside the previous round's fix.

Not a fix, a direction, since the trade is a product decision: nothing here bounds a source. The re-review's own third option is the one that was not taken, a per-source sub-bound under the daily cap so that no single source key can take more than a fraction of the day. Alternatives include raising `ANON_DAILY_RUN_CAP` above `_MINT_THROTTLE_MAX_PER_WINDOW * ATTEMPT_ALLOWANCE` (over 600), lowering the mint throttle below the attack's mint count and revisiting the gate's admit arm, or charging the day only for refusals a paying user would also have paid for. Whichever is chosen, the two comments and the close line above must be corrected rather than left standing, because building on the previous round's false rationale is exactly what produced this finding.

### F-4.10-V-02: three zero-output outcomes still charge a guest an answer AND an attempt, and F-4.10-R-06 is neither closed nor carried

Severity: MODERATE.
Location: `src/system_03_search_agent/core/run_registry.py:_fire_guard_refusal_callback`, `src/system_03_search_agent/core/graph.py:_decline_for_daily_cap`, `tracker/phase_4.10.md`'s "Carried open, with an owner each" table.

The refund fires only on `guard` carrying `passed: false`. Measured against the running app:

```
C4 stopped run:  guest row=(runs_used 1, attempts_used 1)  day charged 1
C4 errored run (Guard-tier HarnessCallError): row=(1, 1)   day charged 1
```

A run the user stops, a run that dies with a step error, and a run declined by `_decline_for_daily_cap` all cost the visitor one of five answers and one of ten attempts, with no refund and no reason given to them. The cap-declined case is the strongest of the three, and the re-review already said so: that run is refused before any work at all, so the phase's own principle ("a visitor must not be pushed toward the sign-in wall by questions that were never answered") applies to it more forcefully than to the guardrail case the refund was built for.

The new part is the process half. F-4.10-R-06 was filed MODERATE at re-review, is not fixed (measured above), and does not appear in the carried-open table, which was written at phase close and states "nothing below is unowned". F-4.10-R-07 (the migrated marker read once at mount, `App.tsx:128`) is in the same state: unchanged in the code, absent from the table. Two re-review findings have no disposition anywhere, in the same phase that filed F-4.10-R-04 for exactly that failure and answered it with that table.

### F-4.10-V-03: the new `guest_attempt_limit_reached` reporting value has no consumer, and unlike the one it copies it never clears

Severity: MODERATE.
Location: `src/system_03_search_agent/adapters/web_sse/app.py:388-403`, `frontend/src/lib/api.ts:216`, `frontend/src/App.tsx` and `frontend/src/components/guest/GuestAllowance.tsx`.

`GET /v1/allowance` now returns `blocked_reason: "guest_attempt_limit_reached"` for a guest at the ceiling, and the server side is right: it applies the same ordering the enforcement path uses, and mutation M7 proves the clause guarding it can fail. Nothing reads it. `blocked_reason` appears in `frontend/src/` only as a type declaration in `lib/api.ts`; no component branches on it.

So a visitor who has spent all ten attempts on refused questions sees `{used: 0, total: 5}`, which the home screen renders as five unused dots, while every question they ask is refused 403. The gate asserts the endpoint is honest and stops there.

Filed separately from F-4.10-05 rather than folded into it, because the two differ in the way that matters. F-4.10-05 is carried on the grounds that it only bites "on a day the whole system has hit its anonymous ceiling", and that condition clears at UTC midnight. This one is permanent for the identity: `attempts_used` never decreases, so the dots lie to that visitor for the remaining life of a 7-day token, with no event that would ever make them true again. Adding a second enum value to a field nothing consumes made the existing gap strictly worse while the carried-open entry still describes only the milder half.

### F-4.10-V-04: the refund's day and the spend's day are two independent clock reads

Severity: MINOR.
Location: `src/system_03_search_agent/data/guest_sessions.py:539` (`today = datetime.now(UTC).date()`), `src/system_03_search_agent/adapters/web_sse/app.py:686` (`datetime.now(UTC).date()` passed as `spend_day`).

`refund_one_run`'s docstring argues, correctly, that the day must be passed in rather than recomputed at refusal time "so the refund lands on the day the run was actually CHARGED. A run refused a few seconds after UTC midnight would otherwise decrement the new day's row, taking a slot from the day that never charged it."

The value passed in is not the day the run was charged to. It is a second `datetime.now(UTC).date()` call made in the handler AFTER `spend_one_anonymous_run` has already committed its own charge against its own clock read. Across a UTC midnight falling between the two, the charge lands on day D and the refund is aimed at day D+1: D stays permanently over-charged by one, and D+1 is decremented for a run it never took. The correct source is the day the spend used, which `spend_one_anonymous_run` computes and does not return.

Narrow: a sub-millisecond window once per UTC day, and the residue is one slot in each direction. Filed because the defect is precisely the one the comment says has been designed out, which is the shape this repository has been bitten by before: a confident comment is where the next reader stops checking.

### F-4.10-V-05: `charged` never travels, but which screen refused does, and screen identity determines `charged`

Severity: MINOR.
Location: `src/system_03_search_agent/core/run_registry.py:338-354` (the "HOW `charged` REACHES THE CALLBACK WITHOUT REACHING THE GUEST" argument), `src/system_03_search_agent/guardrail/prefilter.py`, `guardrail/forbidden.py`.

The plumbing claim holds and I verified both halves. The flag lives on `RunEntry`, is derived from a `cost` event the SSE sanitizer strips for every non-operator caller, and appears nowhere on the wire. Driving both refusal shapes through the real app, a guest's `POST /v1/query` response headers, event stream, event-type set, `GET /v1/allowance` body and citations response are byte-identical between a free refusal and a paid one apart from run identifiers. No `cost` event, no `charged` token, `done.total_cost_usd` redacted to 0.0 in both.

What is not identical is `GuardPayload.category`, which the guest does receive. `injection` is emitted only by `prefilter.screen` (`charged=False`); `off_topic` only by the classifier (`charged=True`). A guest who reads their own refusal category therefore knows whether that question cost money, deterministically, for those two values. Latency separates them too, by a Guard-tier round trip.

Recorded as a minor and deliberately not as a defect. The category is a product requirement, the leak is screen identity rather than any cost or token figure, and Sections 19.4 and 19.5 govern the latter. The `medical_advice` category is emitted by both a free and a paid screen with a byte-identical `reason` string, which is a genuinely good result. The claim to soften is the docstring's, which reads as "nothing a guest can see tells them which questions cost money"; what is true is "no cost figure and no charged flag reaches a guest".

### F-4.10-V-06: the Playwright and axe claim in the phase close is unverified by any round

Severity: MINOR (process).
Location: `tracker/phase_4.10.md:8`.

The close line states "Playwright 30 of 30 including the full axe sweep". The re-review explicitly reported Playwright as not run and T-4.10-08's "no new axe violation" as ungraded, and this round did not run it either. Either a run happened and its output is recorded nowhere, or the number was carried forward from an earlier phase's expectation. A gate count in a close line is read as measured; this one is not, by any report on file.

## Mutation results: can the newest assertions fail?

Question 7 of the brief. For each mutation I asserted the anchor matched exactly once, asserted the file content actually changed, ran the targeted selection, then restored and verified the restore by SHA-256. Every failure message below is the specific one the clause was written to produce, which is what proves the mutation reached the code path rather than merely tripping something.

| # | Mutation | Clause(s) it should kill | Result |
|---|----------|--------------------------|--------|
| M1 | `_UNSPEND_STATEMENT` also decrements `attempts_used` (F-4.10-R-01's defect restored) | the attempt-ceiling arm | RED, 6 clauses. "one guest token started 45 runs against an attempt ceiling of 10" |
| M2 | `refund_one_run` given `daily_day` unconditionally, paid refusals included | `..._still_charges_the_system_wide_daily_budget` | RED, `assert 202 == 429` |
| M3 | `daily_day` never passed, so a free refusal keeps charging the day | `..._cannot_drain_the_whole_anonymous_day` | RED. "one guest burned 10 of the day's 40 shared anonymous runs on refusals that made no model call at all" |
| M4 | `ATTEMPT_ALLOWANCE = 40`, the exact value F-4.10-R-11 recorded as fooling the old gate | `test_the_shipped_default_daily_cap_dwarfs_the_per_guest_attempt_ceiling` | RED, `assert 200 >= (40 * 10)`. The F-4.10-R-11 fix is real. |
| M5 | drop `AND attempts_used < :attempt_cap` from `_SPEND_STATEMENT` | the attempt-ceiling arm | RED, 3 clauses, `assert 45 <= 10` |
| M6 | `spend_one_anonymous_run` commits after `_apply_spend` (F-4.10-R-03's two-transaction shape restored) | `test_a_raising_daily_statement_leaves_the_guest_uncharged`, `test_a_daily_ceiling_refusal_leaves_the_guest_uncharged` | RED, 2 clauses. "the per-guest spend committed while the daily spend failed" |
| M7 | `GET /v1/allowance` never sets `guest_attempt_limit_reached` | the reporting-path clause | RED, `assert None == 'guest_attempt_limit_reached'` |
| M8 | the attempt refusal reuses `guest_allowance_exhausted` | the distinct-reason clause | RED |
| M9 | `_apply_spend` reports ATTEMPTS_EXHAUSTED ahead of EXHAUSTED | the refusal-ordering clauses | RED, 6 clauses across both files |
| M10 | `_DAILY_UNSPEND_STATEMENT` loses its `runs_used > 0` floor | `test_a_daily_refund_can_never_drive_the_shared_counter_negative` | RED, a real `CheckViolation` with `Failing row contains (2026-08-15, -1)` |

Conclusion: no added assertion that cannot fail. Ten for ten, each confirmed to reach the code path first.

## The seven questions, answered from running code

1. Can a guest exceed 10 attempts by any route? No, by every route I could construct. Six OS threads with six event loops racing the LAST attempt against a live database yielded exactly one 202 and five 403s, `attempts_used` landing on exactly 10, with zero `concurrent_run_cap_exceeded` refusals among them, so the run cap was not what refused them and the clause is not hollow in the F-4.10-J-02 way. Both counters advance in the one conditional `UPDATE` and both ceilings gate it, so no ordering exists to slip through. A stopped run, an errored run and a cancelled run each consume an attempt and never return it. A daily-cap refusal consumes none, because the whole transaction rolls back. The MCP surface cannot reach this path at all: it authenticates through `resolve_user_from_bearer_token`, which requires a `users` row and a token that `decode_access_token` accepts, and a guest token is signed with the derived key. `create_run` has exactly two call sites and the MCP one passes no refund callback.
2. Can the refund fire without a genuine refusal, or twice for one run? No to both. `emit("guard", ...)` occurs at exactly two places in `src/`, and only `_decline_for_guardrail` can carry `passed=False`. The callback is set to `None` before it is invoked, so a second `done` event finds nothing to call; I drove nine event orderings through `_fire_guard_refusal_callback` directly, including two `done` events, `done` with no guard event, an error-then-done shape, and a callback that raises. The raising callback still consumed its one shot and did not fail the run. `runs_used` is unaffected in every non-firing case.
3. Can the counters be driven out of range or out of step? No. Five refunds against a zeroed row left `(0, 0)` and returned False each time. One spend followed by two refunds left `(runs_used 0, attempts_used 1)`. Repeated daily refunds floored the shared counter at 0 rather than tripping the CHECK, and M10 proves the clause guarding that floor can fail. `runs_used <= attempts_used` holds structurally: the two advance together and only the first is ever given back.
4. Is the charged signal correct, and does anything guest-visible disclose it? The signal is correct in both directions (see question 5). Nothing guest-visible carries the flag; see F-4.10-V-05 for the one inference channel that survives, which leaks screen identity rather than cost.
5. Is the daily counter charged where it should be and not where it should not? Yes, measured on all three shapes through the real app: a free pre-filter refusal left the day at 0 with the guest at `(0, 1)`; a paid post-classification refusal moved the day by exactly +1 with the guest at `(0, 1)`; an ordinary admitted run moved the day by exactly +1 with the guest at `(1, 1)`. No `cost` event is emitted anywhere before the guard verdict, so the "stray earlier cost" ordering that would mis-mark a free refusal as charged is unreachable, and it fails safe (toward over-charging the day) if it ever becomes reachable.
6. The transaction boundary. Sound. Replacing `_DAILY_SPEND_STATEMENT` with a raising statement left the guest at `(0, 0)` and the day unmoved; invalidating the connection mid-transaction left the guest at `(0, 0)`. F-4.10-R-03 is genuinely closed, and M6 proves the clause that pins it can fail.
7. Assertions that cannot fail. None found. See the mutation table.

## What I checked and found clean

Recorded so the coverage of this round is arguable rather than assumed.

- The alembic 0005 revision: a pure expand on upgrade (one `NOT NULL` column with a server default of 0, so 0004-era code keeps inserting successfully), a pure contract on downgrade, the CHECK dropped explicitly before the column. Existing rows start at 0, and the docstring states why backfilling from `runs_used` was rejected and what the rollback re-exposes.
- The refusal ordering in `_apply_spend`: answers before attempts, mirrored identically in `GET /v1/allowance`'s `blocked_reason`, and M9 proves swapping it goes red in six places across both the data layer and the HTTP layer.
- Every user-visible string these commits added. The 403's message ("you have asked as many questions as a guest can") is true on the only path that emits it. `WALL_COPY`'s three sentences are each true on their own trigger, and the frontend gate asserts each one's presence AND the other two's absence, so no hedged single sentence passes. `SignInWall`'s heading is true on all three. F-4.10-R-02 is genuinely closed.
- Secrets and interpolation in everything the last two commits added: no token, key, payload or `str(exc)` reaches any log line or external message. The refund's own failure log carries a fixed literal plus `run_id`.
- `refund_one_run`'s deliberate omission of `revoked_at IS NULL`, which is argued correctly: a revoked session cannot spend again, so decrementing it changes nothing observable, and adding the predicate would create a second definition of "live".
- The `daily_cap` keyword-only parameter with no default, which makes the system-wide ceiling impossible to lose silently at the call site.
- Doc drift, which the re-review reported failing at 6 stale facts and now passes at 0.

## What a hostile reader would still say is uncovered

- Nothing anywhere asks whether one SOURCE, as opposed to one identity, can exhaust the shared ceiling. That is F-4.10-V-01, and it is the direct consequence of a coverage statement that declared the omission and deferred it to a clause that does not answer it.
- Nothing asserts what a stopped, errored or cap-declined run costs a guest. That is F-4.10-V-02, unchanged from the re-review.
- No clause exercises two live `App` mounts sharing one `localStorage`. Unchanged from the re-review's F-4.10-R-07.
- Nothing consumes `blocked_reason` on the client, so no test can assert the dots stop promising a search the next request refuses. That is F-4.10-V-03.
- The daily ceiling across a UTC midnight remains declared non-coverage, correctly, and F-4.10-V-04 is the one case where that boundary is not merely untested but wrong.
- Playwright and the axe sweep remain unrun by every round that has reported, while the phase close states a number for them.
