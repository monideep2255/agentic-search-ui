# Build phase 4.11, round 3 independent re-verification

Reviewer: independent re-verifier, round 4 (grading round 3).
Date: 2026-08-22.
Branch: `phase/4.11-graph-query-service`. Round 3 commit: `4a637e7`.
Scope: ROUND 3 ONLY. Rounds 1 and 2 had their own independent passes; their findings are closed or tracked and are not reopened here.

Authorised round 3 scope was two findings:
- `F-4.11-RV-01`: unbounded rate-limit and refusal bookkeeping tables.
- `F-4.11-RV-04`: untested concurrency slot release in a `finally`.

New arms under grade: `test_p23_the_hard_cap_on_tracked_sources_actually_holds`, `test_p23b_idle_source_keys_are_evicted_as_their_window_passes`, `test_p24_a_failed_query_returns_its_concurrency_slot`.

Method: mutation, not reading. Round 3 shipped a vacuous arm twice; reading is a proven-insufficient instrument on this phase.

Bottom line, stated first: **none of the three new arms is vacuous**, and **neither monkeypatch in P23 weakens a check** - both isolate. Every control the three arms claim to prove dies when that control is deleted. The problems are elsewhere: two majors sit INSIDE the round 3 fix, one of them a measured regression against `ac538ca`. Recommendation at the foot of this file: MERGE WITH TRACKED FLAGS.

---

## Question 1: are the three new arms vacuous?

Baseline before any mutation: `tests/system_03_search_agent/tools/test_graph_query_service_premise.py tests/services tests/.../test_graph_http_transport.py` = **118 passed, 7 skipped**.

### First-order mutation results (delete the exact control each arm claims to prove)

| # | Mutation | Expected killer | Result |
|---|----------|-----------------|--------|
| M1 | `_RateLimiter._enforce_cap` body disabled (`if False and len(...)`) | P23 | **RED** - P23 failed. Correct. |
| M1a | only the post-append `self._enforce_cap()` removed, leaving the one inside `_evict_idle` | P23 | **RED** - P23 failed. The off-by-one the round 3 commit claims to have fixed IS genuinely pinned: table settles at cap+1 and P23 sees it. |
| M2 | `_RateLimiter._evict_idle` sweep predicate forced false (sweep keeps everything) | P23b | **RED** - "still retains 51 source keys". Correct. |
| M3 | `self._evict_idle(now)` call removed from `_RefusalLog.should_emit` | P23b | **RED** - P23b failed on the refusal half. Correct. |
| M4 | `finally: query_slots.release()` replaced with an unconditional release placed after the try (the exact F-4.11-RV-04 mutation) | P24 | **RED** - P24 failed. Correct. |

**Verdict on the first-order question: none of the three arms is vacuous.** Each one dies when the control it names is removed, and P23 additionally dies on the narrower off-by-one variant, which is stronger than the commit message claims.

### The two monkeypatches in P23: isolation or weakening?

`monkeypatch.setattr(app_module, "MAX_TRACKED_SOURCES", 25)` - **ISOLATION, legitimate.** It lowers the ceiling so 250 sources cross it, rather than raising traffic to 10001 sources. The property under test (does the cap hold at all, and does it hold at exactly its documented value) is unchanged by the ceiling's numeric value, and M1/M1a prove the assertion is load-bearing at 25. This is the correct fix for the first vacuity: the previous version asserted a ceiling it never approached.

`monkeypatch.setattr(app_module, "_TRUSTED_PROXY_HOSTS", frozenset({"testclient", "127.0.0.1"}))` - **ISOLATION, legitimate, with one caveat.** `TestClient`'s peer is the literal string `"testclient"`, so without the patch every request collapses to one source key and the arm proves nothing (that was vacuity #2). The patch restores the arm's ability to produce distinct keys; it does not touch the cap logic. The caveat: it means P23 exercises `client_source` under a trust set the deployment does not have. That is acceptable only because P20 independently pins the rightmost-element rule against the real `_TRUSTED_PROXY_HOSTS`, and it does. Neither patch weakens a check in the `goal-contracts` sense.

The `assert tracked > 1` populate-check is the durable guard and it is the right instrument: it is what makes "the bound held" distinguishable from "nothing happened", and it is what would have caught both prior vacuities.

### Third-way vacuity probes: what the three arms do NOT see

Five further mutations, each a plausible way the round 3 fix could be wrong. Two of the three arms have real holes next to them.

| # | Mutation | Result | Meaning |
|---|----------|--------|---------|
| M5 | `_enforce_cap` sort reversed (`reverse=True`), so the cap drops the MOST recently seen key instead of the least | **SURVIVES, 94 passed** | Nothing pins WHICH keys the cap drops. Under this mutation the caller's own just-appended key is the first evicted, so past the cap the rate limiter tracks nobody and stops limiting entirely. The count assertion in P23 cannot see it. |
| M6 | the `if len(self._last_emitted) > MAX_TRACKED_SOURCES:` branch in `_RefusalLog._evict_idle` disabled | **SURVIVES, 94 passed** | The refusal log's hard cap has NO arm. Only the rate limiter's cap is pinned (P23) and only the refusal log's idle sweep is pinned (P23b). The one remaining quadrant is untested. |
| M8 | amortisation clock set so the sweep can never fire | RED (P23b) | The `_last_eviction` clock is correctly pinned; it cannot stall unseen. |
| M9 | trailing `self._enforce_cap()` inside `_evict_idle` deleted | **SURVIVES, 94 passed** | Provably redundant: the only path that reaches `_evict_idle` without also reaching the post-append `_enforce_cap()` is the rate-limited early return, which adds no key. Dead control, not a defect. |
| M10 | sweep predicate forced true, so a source whose window has NOT expired is evicted | **SURVIVES, 94 passed** | The gate checks only that keys ARE dropped, never that a live key is KEPT. Over-eviction, which is the rate-limit-reset direction, is invisible to the gate. |

M7 (release moved to a failure-only handler, so every SUCCESSFUL query leaks a slot) was caught by four arms including P24, so the slot release is covered in both directions.

## Findings

### F-4.11-R3V-01. The round 3 fix silently zeroes the refusal log's withheld counter

- Round: 4
- Severity: **major** (reachable in normal operation, no attacker required, defeats a stated design property, invisible to the gate)
- File: `services/graph_query_service/app.py`, `_RefusalLog._evict_idle` (lines 505 to 530), called from `should_emit` line 506
- Regression of: F-4.11-J-05, introduced by the fix for F-4.11-RV-01

`_evict_idle` pops BOTH `self._last_emitted[key]` and `self._suppressed[key]`. The withheld counter is therefore destroyed whenever any other source emits a refusal more than one interval after a given source last emitted. `_emit_refusal`'s own docstring says the opposite in as many words: "The withheld count is carried on the emitted line rather than dropped, because '429 refusals suppressed' is the number an operator needs to see a flood; a bound that hides its own suppression turns a volume control into a blind spot." `_evict_idle`'s docstring adds "eviction discards nothing the bound relies on." Both are now false.

Measured through the real HTTP endpoint with a controlled clock (source 203.0.113.1 refused 42 times, 40 of them withheld, then one refusal from a second source at t+61 to trigger the sweep):

```
HEAD (4a637e7):
  auth rejected caller=403117ce... suppressed=0
  auth rejected caller=45d0b5a2... suppressed=0
  auth rejected caller=403117ce... suppressed=0     <- 40 withheld, reports 0

ac538ca (before round 3):
  auth rejected caller=403117ce... suppressed=0
  auth rejected caller=45d0b5a2... suppressed=0
  auth rejected caller=403117ce... suppressed=40    <- correct
```

Who triggers it: any operator reading the journal during a multi-source flood, which is the only scenario the counter exists for. With two or more active sources, every sweep run zeroes the counters of every source that has been quiet for one interval, so the flood-volume number an operator needs reads 0 while thousands of refusals are being withheld. Under a single-source flood the counter survives, which is exactly why a hand-check would miss this.

Why the gate cannot see it: P16 asserts only `any("suppressed=" in r.getMessage() for r in records)`. It pins that the field is PRESENT, never that its value is right. That is the same "asserts the log is CLEAN, never that it is COMPLETE" shape the phase already recorded against P11b for F-4.11-03, now a third time.

Fix direction: evict `_last_emitted` and keep `_suppressed`, or fold the withheld count into the emitted line before the key can be dropped. The counter is bounded by the same key set either way, so retaining it costs no additional growth.

### F-4.11-R3V-02. The memory bound is paid for with a 990x CPU amplification on the pre-auth path

- Round: 4
- Severity: **major** (unauthenticated, pre-auth, attacker controls the multiplier, lands synchronously on the event loop)
- File: `services/graph_query_service/app.py`, `_RateLimiter._enforce_cap` (lines 412 to 419) and `_RefusalLog._evict_idle` (lines 505 to 530)
- Regression of: F-4.11-RV-01 (the defect is inside its fix), and it lands in the same failure class as F-4.11-08

Both eviction paths are O(n) or O(n log n) in the size of the table, and both run on the request path. `_enforce_cap` is called after every accepted insert, so once the table sits at `MAX_TRACKED_SOURCES` every subsequent request from a fresh source pushes it to cap+1 and pays a full `sorted()` over 10001 keys to drop exactly one. `_RefusalLog._evict_idle` has no amortisation guard at all (unlike `_RateLimiter._evict_idle`, which is gated on `self._last_eviction`), so it scans the whole index on every emitted refusal.

Measured on this machine, `PYTHONPATH=src`, real code, no mutation:

```
rate limiter, table filled to 10000 keys
  at-cap _RateLimiter.check   0.8572 ms/request
  cold   _RateLimiter.check   0.00087 ms/request      amplification 990x

refusal log, index filled to 10000 keys
  at-cap should_emit          0.4779 ms/emit
  cold   should_emit          0.00263 ms/emit         amplification 182x

time to fill the refusal index from empty to 10000 keys: 1.04 s of CPU
```

Who triggers it and how: an unauthenticated caller with an IPv6 /64, which the module docstring itself already names as the attacker model for F-4.11-RV-01. 10000 distinct sources inside one 60-second window is 167 requests/second, and it puts both tables at their cap. From then on every request costs about 1.34 ms of synchronous bookkeeping before auth is even checked, versus about 3.5 microseconds today. This runs on the event loop, in the same `async def` that F-4.11-08 was filed against for holding the loop and stalling the unauthenticated `/healthz` that `tracker/preflight.py` reads to decide whether the graph is up.

Honest bounding, because this should not be overstated: at ~1.34 ms per request the loop saturates somewhere near 750 requests/second, so this is a degradation amplifier and not an outright bypass, and it is still strictly better than the unbounded memory growth it replaced. It should not block the merge on its own. It should be tracked, because the shape is the phase's recurring one: the fix moved the exhaustion rather than removing it, for the second time on the same finding.

Fix direction: evict in batches (drop to, say, 90 percent of the cap rather than to exactly the cap) so the sort amortises to O(1) per request, and put `_RefusalLog._evict_idle` behind the same `_last_eviction` guard `_RateLimiter._evict_idle` already has. An `OrderedDict` with `move_to_end` plus `popitem(last=False)` removes the sort entirely.

### F-4.11-R3V-03. Nothing pins which keys the hard cap drops

- Round: 4
- Severity: **latent** (the shipped code is correct; the gate cannot tell)
- File: `services/graph_query_service/app.py`, `_RateLimiter._enforce_cap` lines 414 to 418

Mutation M5, adding `reverse=True` to the sort, leaves the entire local suite green at 94 passed. Under that mutation the cap evicts the MOST recently seen key, which after the `bucket.append(now)` on line 405 is the current caller's own key, so past the cap the limiter forgets every caller immediately and rate limiting stops working altogether while the count assertion in P23 still reads 25. P23 asserts HOW MANY keys survive and never WHICH, so the property that makes the cap a control rather than a truncation is unasserted. This is the same class as F-4.11-RV-04, a correctness property stated in a docstring ("Drop the least recently seen keys") that no arm checks.

### F-4.11-R3V-04. The refusal log's hard cap has no arm

- Round: 4
- Severity: **latent**
- File: `services/graph_query_service/app.py`, `_RefusalLog._evict_idle` lines 522 to 527

Mutation M6, disabling the `len(self._last_emitted) > MAX_TRACKED_SOURCES` branch, leaves the suite green at 94 passed. The round 3 fix touches four controls: rate limiter sweep, rate limiter cap, refusal log sweep, refusal log cap. P23 pins the second, P23b pins the first and the third. The fourth is unpinned, and it is the one that handles the adversarial case (sources arriving faster than they expire) for the table an unauthenticated flood grows fastest.

### F-4.11-R3V-05. The gate checks eviction in one direction only

- Round: 4
- Severity: **latent**
- File: `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, P23b

Mutation M10, forcing the sweep predicate true so a source whose window has NOT expired is evicted, leaves the suite green at 94 passed. P23b asserts `tracked <= 2` after ten idle windows: it proves dead keys are dropped and never that live keys are kept. Over-eviction is the rate-limit-reset direction, so the half of the property with security consequence is the half the arm does not test.

The shipped predicate is nonetheless correct, and this is worth stating because it answers the brief's sharpest question directly. `now - bucket[-1] > self._window` is true only when the newest timestamp in the bucket has aged out, which means every timestamp has aged out, which means the drain loop on lines 395 to 396 would empty that bucket on the caller's very next request anyway. So the SWEEP cannot drop a live budget. See F-4.11-R3V-06 for the path that can.

### F-4.11-R3V-06. The hard cap can reset an active caller's budget, but buys the attacker nothing

- Round: 4
- Severity: **latent** (filed for the record because the brief asks for it directly, and because a future change to the cap could make it matter)
- File: `services/graph_query_service/app.py`, `_RateLimiter._enforce_cap`

Unlike the sweep, `_enforce_cap` drops by recency alone and does not check whether the dropped key still has live timestamps. A caller that has exhausted its budget stops appending, so its `bucket[-1]` freezes and it sorts toward the front of the eviction list. An attacker can therefore force eviction of its own throttled key by driving the table past the cap, and then start again with a full budget.

It is graded latent rather than major because the capability is already free: reaching the cap requires 10000 distinct sources inside a window, and 10000 distinct sources each get their own full budget by construction, so a caller able to do this has already defeated a per-source limiter without touching eviction. The direction that would matter, forcing eviction to DENY a legitimate caller, is not available: dropping a key can only forget history and grant budget, never invent a refusal. The docstring says exactly this and the docstring is right.

### F-4.11-R3V-07. Dead control: the `_enforce_cap()` call at the end of `_evict_idle`

- Round: 4
- Severity: **minor** (no behavioural consequence; noted because the phase's cost has been comments and controls that claim more than they do)
- File: `services/graph_query_service/app.py`, line 402

Mutation M9, deleting it, leaves the suite green, and analysis agrees it is genuinely redundant rather than merely untested: the only path reaching `_evict_idle` without also reaching the post-append `_enforce_cap()` on line 407 is the rate-limited early return, and that path adds no key, so the table cannot have grown. It is harmless but it doubles the cost measured in F-4.11-R3V-02 on the accepted path.

## Question 2: the rest of the round 3 fix

Answered item by item against the brief.

Is the eviction correct, and did the cap's off-by-one move rather than get fixed? Fixed, and pinned. Measured directly against the real classes with no mutation: driving `MAX_TRACKED_SOURCES` (10000) distinct sources into `_RateLimiter` leaves exactly 10000 tracked, and 200 further requests leave it at exactly 10000, never 10001. The same holds for `_RefusalLog`. Mutation M1a, removing only the post-append `_enforce_cap()` and leaving the pre-insert one, reproduces the cap+1 state and P23 fails on it. So the arm genuinely holds the code to its documented number rather than to a looser one.

Can eviction drop a key that is actively being rate-limited, letting a caller reset its own budget? The SWEEP cannot, and the argument is short enough to state completely. The predicate is `not bucket or now - bucket[-1] > self._window`. `bucket[-1]` is the newest timestamp, so if it has aged out then every timestamp has aged out, and the drain loop on lines 395 to 396 would empty that bucket on the caller's very next request regardless. Eviction and expiry therefore coincide exactly; the sweep can only delete what was already dead. The HARD CAP can, because it drops by recency alone with no liveness check, and a throttled caller's `bucket[-1]` freezes and sorts toward the front. That is filed as F-4.11-R3V-06 and graded latent, because reaching the cap requires 10000 distinct sources and 10000 distinct sources already each carry a full budget, so the path buys an attacker nothing it did not already have. The direction with real consequence, forcing eviction to DENY a legitimate caller, does not exist: dropping a key can only grant budget, never invent a refusal.

Is the amortisation clock correct, and can it stall? Correct, and it cannot stall unseen. `self._last_eviction` is initialised from `time.monotonic()` and set to `now` inside the guard, so the sweep runs at most once per window and at least once per window on any traffic. Mutation M8, setting the initial value one thousand seconds in the future so the guard can never fire, is caught by P23b.

Is the sweep's sort ordering right? The `_enforce_cap` key `self._calls[k][-1] if self._calls[k] else 0.0` is correct: `0.0` is below any `time.monotonic()` value, so an emptied deque sorts first and is evicted first, which is the right priority. But nothing tests it. Reversing the order leaves the suite green (F-4.11-R3V-03), and the reversed version silently disables rate limiting past the cap.

Can two coroutines mutate a dict during a sweep, and can that raise "dictionary changed size during iteration"? No, on three independent grounds, and it was tested rather than argued. First, `cypher_endpoint` is `async def` and there is no `await` anywhere between `client_source(request)` and the end of `_emit_refusal`, so every limiter mutation is atomic with respect to the event loop. Second, both sweeps materialise their delete list as a full list comprehension before deleting anything, and `sorted()` materialises its input before calling the key function, so even a re-entrant call could not iterate a mutating dict. Third, the threadpool never touches these tables: `asyncio.to_thread` is applied only to `execute_cypher`, which takes no limiter reference. Empirically: 1000 concurrent pre-auth requests across 200 sources through an `httpx.ASGITransport` with `MAX_TRACKED_SOURCES` forced down to 20 so the sort and the delete loop run on essentially every request, zero exceptions, and both tables settled at exactly 20. `graph-query-service.service` runs uvicorn with no `--workers` flag, so there is one process and one copy of each table.

What Q2 did turn up is filed above: F-4.11-R3V-01 (the withheld counter is destroyed by the new eviction) and F-4.11-R3V-02 (the fix trades bounded memory for a 990x per-request CPU cost on the pre-auth path).

## Question 3: does the phase hold end to end?

| Check | Result |
|-------|--------|
| `RUN_PREMISE_GATE=1 ./venv/bin/python -m pytest .../test_graph_query_service_premise.py -q` | **54 passed in 20.63s, zero skipped.** The live arms genuinely ran; the same file without the flag is 47 passed and 7 skipped, and 47 + 7 = 54, so every gated arm executed. |
| `services/graph_query_service/deploy/check_drift.sh` | **5 of 5 ok.** cypher_validator.py, graph_schema_constants.py, graph_connection.py, graph_http_transport.py, app.py all byte-identical to this working tree. The findings above therefore describe the DEPLOYED service, not only the repository. |
| Local suites (`tests/services`, the premise file, `test_graph_http_transport.py`) | 118 passed, 7 skipped, before and after every mutation. |
| Full suite `./venv/bin/python -m pytest -q` | **3747 passed, 6 failed, 137 skipped, 1 xfailed.** The 6 failures are exactly the pre-existing `tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py` set that also fails on `develop`. Not filed. |
| Working tree after all 10 mutations | `git diff --stat HEAD` empty. Only this report is untracked. No mutation left behind. |

Mutations were run strictly serially through a single runner that aborts if `app.py` is already dirty, restores with `git checkout --`, and verifies the restore before returning. No two mutation processes ran against the file at once.

## Recommendation

**MERGE WITH TRACKED FLAGS.**

The single strongest reason: round 3's authorised fix works and is genuinely pinned (all five first-order control mutations go red on the arm that claims them, and none of the three new arms is vacuous), but the fix carries a defect inside itself for the third consecutive round, and that defect is F-4.11-R3V-01, a one-line change that silently zeroes the very number `_emit_refusal`'s own docstring calls "the number an operator needs to see a flood."

Why flags rather than a fourth round. The two majors are both degradations of a diagnostic rather than breaches of a control. R3V-01 costs the operator an accurate suppression count during a multi-source flood; the refusals are still bounded, still logged, and still attributed. R3V-02 costs about 1.3 ms of event-loop CPU per pre-auth request once an attacker has parked 10000 sources in the tables, which is worse than it should be but is strictly better than the unbounded memory growth it replaced. Neither reopens the unauthenticated-exhaustion hole F-4.11-RV-01 named, and `check_drift.sh` confirms the deployed copy is the reviewed copy.

Against that, this phase has now measured its own base rate: three rounds, three defects planted inside the round's own fix, plus one arm written vacuous twice by the party that wrote the code it grades. A fourth lead-written in-phase round is the option with the worst measured track record available. The five findings should become tracked tickets, and F-4.11-R3V-01 and F-4.11-R3V-04 (the refusal log's hard cap, which has no arm at all) are the two that most deserve to be fixed together, since both live in `_RefusalLog._evict_idle` and one arm can cover both.

The call on whether to spend a fourth round is the product owner's, not this reviewer's, and the escalation exists precisely for it.

## Status log

- [x] Q1 arms mutated. 10 mutations, run serially, tree verified clean after each. Verdict: not vacuous; both monkeypatches isolate rather than weaken.
- [x] Q2 fix inspected. Eviction correct, clock correct, ordering correct but unpinned, no concurrency hazard. Two majors found inside the fix.
- [x] Q3 end to end. 54 live arms passed with zero skips, drift 5 of 5, full suite matches develop's baseline.
