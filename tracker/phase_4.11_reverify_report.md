# Build phase 4.11, round 3: independent re-verification report

Re-verifier: fresh-context agent, no round 1 or round 2 context.
Branch: `phase/4.11-graph-query-service`. Round 2 commit under review: `f15debe`.
Started: 2026-08-22.

Order of work, deliberately: Question 2 (was a gate arm weakened) first, then
Question 1 (defect inside a round 2 fix), then Question 3 (do the eleven fixes
hold) if budget allows.

Status: IN PROGRESS. Findings are appended as they are confirmed, never held for
a final write-up.

---

## Progress log

- Report file created before any analysis, per the standing instruction.

## Question 2, answered first: was a gate arm weakened?

Headline: NO, neither of the two edited arms was weakened. Both edits survive
independent scrutiny, and I can prove each by mutation. That is the first
paragraph because the question outranks everything else, and the answer is
clean.

That said, the phase does NOT merge clean. The strongest finding in this
report sits inside a round 2 fix, not in a gate arm: `F-4.11-RV-01`, an
unbounded per-source keyspace in the two new bounds themselves. See Question 1.

### 2a. P15's `REFUSAL_LOG_INTERVAL_SECONDS = 0.0` monkeypatch: JUSTIFIED

The claimed justification is that completeness and boundedness are opposing
properties. I verified that claim mechanically rather than taking it, and it
holds for a specific, checkable reason:

- P15's outcome list contains BOTH `auth_rejected` (wrong credential) and
  `no_credential` (no header at all). `_check_auth` routes both through the
  same `_emit_refusal(refusal_log, "auth_rejected", source_key, None)` call,
  so both carry the SAME `(event, source_key)` tuple.
- `_RefusalLog.should_emit` therefore suppresses the second one for the whole
  60-second interval.
- P15 asserts `messages` is non-empty per outcome. With the bound left on, the
  `no_credential` outcome emits nothing, and P15 fails with the message
  "outcome 'no_credential' left no audit record at all" while the logging path
  for it is in fact present and working.

So the bound-on version of P15 is a FALSE FAILURE, not a caught defect. The
monkeypatch removes a false negative, not a check.

Is P16 genuinely sufficient alone to hold the bound? Yes, and for a structural
reason rather than a coverage one: there is exactly ONE bound, `_RefusalLog`,
and every one of the five refusal call sites reaches it through the single
`_emit_refusal` helper. The bound cannot be deleted for one event and kept for
another, so an arm that exercises any one event proves the bound for all of
them. P16 exercises two (`auth_rejected` and `source_rate_limited`) and asserts
`len(records) < attempts / 4` over 160 attempts, plus the presence of
`suppressed=`.

Residual, recorded but not filed as a defect: P15 in its current form would
still pass if the bound were deleted entirely. That is acceptable only because
P16 holds it, and P16 holding it depends on `_emit_refusal` remaining the sole
path. If a future phase adds a refusal that calls `logger.warning` directly,
neither arm catches it. The module docstring states the ordering rule; nothing
tests it. Filed below as `F-4.11-RV-04` (latent).

### 2b. The httpx timeout assertion rewrite: GENUINELY STRONGER

The old line, `assert seen["timeout"] == 30.0`, pinned the defect: it asserted
the client waits exactly as long as the budget it hands the service, which is
the condition under which the service's own 504 can never arrive. Deleting it
would have been a weakening. Replacing it with the inequality is not.

Proof that the replacement fails if the fix is reverted: reverting
`timeout=httpx.Timeout(...)` to `timeout=timeout_s` makes `seen["timeout"]` a
bare `float`, and `float.read` raises `AttributeError`. The arm errors, not
merely fails. It cannot pass against the reverted code. Verified by mutation
below.

The replacement is also cross-checked at the premise-gate layer by P21, which
asserts the relationship between two constants living in DIFFERENT modules
(`t.CLIENT_TIMEOUT_HEADROOM_SECONDS > MAX_CONCURRENCY_WAIT_SECONDS`). That is
the right shape: the drift the comment warns about is now a test, not prose.

One gap worth naming, below the bar for a finding: nothing anywhere asserts the
`write` or `pool` members of the `httpx.Timeout`. Setting `write=0.001` would
pass every arm in both suites. The blast radius is small (the request body is
one Cypher template), so I record it rather than file it.

Progress: Q2 answered. Baseline established: `RUN_PREMISE_GATE=1` over the three
target suites is **122 passed, 0 failed, 0 skipped in 21.60s**. Without the
env var the premise file alone runs 44 passed / 7 skipped, so the live arms do
run and the gate is genuinely exercised.

---

## Question 1: defects INSIDE the round 2 fixes

### F-4.11-RV-01, MAJOR, regression of F-4.11-J-05 / F-4.11-10

The round 2 bound against an unauthenticated flood is itself unbounded, in its
own bookkeeping.

File and line: `services/graph_query_service/app.py`
- `_RateLimiter.__init__`, line 373: `self._calls: dict[str, deque[float]] = defaultdict(deque)`
- `_RateLimiter.check`, lines 381-393: prunes timestamps INSIDE a bucket, never removes an empty bucket from `_calls`
- `_RefusalLog.__init__`, lines 413-415: `self._last_emitted: dict[tuple[str, str], float]`, never evicted
- `cypher_endpoint` step 0, lines 757-760: `source_limiter.check(source_key)` on EVERY request, before auth

What is wrong: both new controls key on the caller's source address, and
neither ever removes a key. `_RateLimiter._calls` is a `defaultdict`, so the
mere act of checking an unseen source allocates a permanent entry. A source
that sends exactly one request and never returns keeps a `deque`, a 16-hex-char
key string, and a `dict` slot for the life of the process. `_RefusalLog`
retains a `(event, source_key)` tuple and a float in `_last_emitted` on the
same terms.

Reachability, concretely: an unauthenticated caller on the public HTTPS port.
No credential is needed, because step 0 runs BEFORE auth, which is the entire
point of the fix. The attacker needs only distinct source addresses, and a
single IPv6 /64 allocation (the standard assignment from any VPS or residential
ISP) supplies 2^64 of them. One request per address is enough; the per-source
rate limit of 120/min is irrelevant because the attack never repeats a source.

Measured, not argued. `/private/.../scratchpad/probe.py`, driving `build_app()`
through a `TestClient` with a loopback peer and a varying `X-Forwarded-For`:

```
limiter[1] distinct keys retained: 3000
refusal log[0] _last_emitted keys: 3000, _suppressed keys: 0
```

3000 unauthenticated requests from 3000 sources, 3000 permanently retained
entries in each structure, zero evicted. Roughly 500 to 700 bytes per source
across the two structures.

Why this is a regression rather than a new defect: F-4.11-J-05 and F-4.11-10
were both "the unauthenticated path is unbounded." The round 2 fix bounds the
request RATE per source and the log VOLUME per source, and in doing so
introduces an unbounded per-source KEYSPACE. The failure moved one layer down
rather than being removed. This is the same shape the commit message itself
names for F-4.11-08 ("the threadpool alone would move the exhaustion one layer
out rather than fix it") and it is the shape this repository has hit in four
consecutive rounds of build phase 4.2 and six of 4.3.

Two claims in the code become false as a result:
- `_RefusalLog`'s docstring: "an unauthenticated flood cannot grow the journal
  without bound." It bounds one line per (event, source). A flood that varies
  its source emits one WARNING per source per event, so the journal grows
  linearly with the attack after all, on the box the phase docs measure at 92
  percent full.
- P16's docstring: "from a number of lines that does not grow with the attack."
  It does, in the source dimension. P16 only ever drives ONE source, so it
  cannot see this.

The heap consequence is the more serious of the two: the service process grows
without bound until the kernel kills it, and a dead graph query service is
precisely the "the transport looks down" failure this phase was pulled ahead of
build phase 4.7 to delete.

Confidence: HIGH. Reproduced mechanically, not reasoned.

Fix shape (not applied, this is a review): evict on read in `_RateLimiter.check`
(delete the key when the pruned deque is empty, and use plain `dict.get` rather
than `defaultdict` so a check does not allocate), and give `_RefusalLog` the
same treatment plus a hard cap on `_last_emitted` with LRU or age eviction.
The verify surface must drive MANY sources, not one, or it repeats P16's blind
spot.

### F-4.11-RV-02, MINOR: the Caddyfile comment asserts a property the Caddyfile does not have

File and line: `services/graph_query_service/app.py`, `client_source` docstring,
lines 480-482: "The deployed Caddyfile additionally OVERWRITES the header with
the real remote host rather than appending to it, so both layers are safe
independently."

`services/graph_query_service/deploy/Caddyfile` contains no
`header_up X-Forwarded-For` directive at all, and no `trusted_proxies`
configuration. Its `reverse_proxy 127.0.0.1:8080` therefore runs Caddy's
DEFAULT behaviour, which is to APPEND the immediate peer to any existing
`X-Forwarded-For` value, joining with ", ", not to overwrite it. So the second
of the two claimed independent layers does not exist.

The code is still correct today, because `client_source` reads
`forwarded.rsplit(",", 1)[-1]`, the RIGHTMOST element, which is the value Caddy
appended, that is the real remote host. One layer holds.

Why it is worth filing anyway, at MINOR: "leftmost is the original client" is
the conventional reading of `X-Forwarded-For`, and it is the reading a future
maintainer is most likely to "correct" the code toward. The comment tells that
maintainer a second layer will catch them. It will not. This repository's own
`self-eval-loop` rule names exactly this: "a code comment that CLAIMS a
property is a claim to be tested, not documentation," and F-2.1-J5-01 was the
same shape.

Note that P20 (`test_p20_a_forwarded_client_address_is_trusted_only_from_the_local_proxy`)
tests the trusted-peer half. Nothing tests the rightmost-element half against
the deployed proxy's actual behaviour.

Confidence: HIGH on the repository Caddyfile, which I read in full.
The DEPLOYED Caddyfile is verified separately below.

#### Live verification of RV-01's and RV-02's reachability (both against the deployed box)

I reached the box by `ssh`, so nothing here is UNVERIFIED.

1. `services/graph_query_service/deploy/check_drift.sh`: **5 of 5 ok**, no drift.
   Note that check_drift covers only the five Python files. It does NOT cover
   the Caddyfile or the systemd unit, so a hand-edit to either is invisible to
   this repository. Recorded, not filed.

2. The DEPLOYED `/etc/caddy/Caddyfile` matches the repository copy's content
   and, as the repository copy does, contains no `header_up X-Forwarded-For`
   and no `trusted_proxies`. RV-02's claim is confirmed against the real
   deployment, not just the repository file.

3. Is the source bound actually spoofable? **NO.** I ran 130 unauthenticated
   requests over real HTTPS, each carrying a unique `X-Forwarded-For`:

   ```
   status counts: {401: 120, 429: 10}
   first 429 at request #: 121
   ```

   The 429 lands at exactly request 121, which is `SOURCE_RATE_LIMIT_PER_MINUTE`
   plus one. The rightmost-element rule holds against the real proxy: all 130
   collapsed onto my one real source address. The rate-limit bypass does not
   exist, and RV-02 stays MINOR.

4. Does RV-01's keyspace attack have a real ingress? **YES.** The box carries a
   global IPv6 /64 (`2a01:4f8:1c1a:3bb0::1/64`), Caddy listens on `*:443`
   (both address families), and `ufw status` reports `inactive`, so nothing
   filters it. Confirmed by reaching the live service over IPv6:

   ```
   curl -6 --resolve ...:443:2a01:4f8:1c1a:3bb0::1 .../healthz
   ipv6 healthz status=200 remote=2a01:4f8:1c1a:3bb0::1
   ```

   An attacker with their own IPv6 /64, which is the standard allocation from
   any VPS or residential ISP, therefore has 2^64 distinct, un-spoofed,
   genuinely-different source keys to hand the service, one request each. That
   is what makes RV-01 MAJOR rather than theoretical.

   Also observed and NOT filed, because commit `cf9d8cc` already addressed "the
   runbook's firewall fiction" and the phase knows about it: there is no host
   firewall at all. P10's claim survives only because Postgres binds loopback
   (`127.0.0.1:5432` and `[::1]:5432`, confirmed by `ss -tlnp`), and uvicorn
   binds `127.0.0.1:8080`. The bind, not a firewall, is the control.

### F-4.11-RV-03, LATENT: the concurrency bound is released while the query is still running

File and line: `services/graph_query_service/app.py`, `cypher_endpoint`, lines
938-945, the `finally: query_slots.release()` block.

`asyncio.to_thread` cannot cancel the thread it started. If the request task is
cancelled while `await asyncio.to_thread(execute_cypher, ...)` is pending, the
`finally` runs immediately and hands the slot back, while the worker thread
keeps running the blocking psycopg2 query and keeps holding its graph
connection. The bound then counts requests that are awaiting, not queries that
are executing, which is the opposite of what F-4.11-08's fix needed.

Measured, with `MAX_CONCURRENT_QUERIES` set to 2 and eight requests each
cancelled 0.15s after dispatch:

```
MAX_CONCURRENT_QUERIES = 2
peak simultaneous in-flight graph queries = 8
```

Four times the bound, and it would keep scaling with the request rate. This is
the graph connection-pool exhaustion the adversary's own "what I would attack
next" named.

Why LATENT rather than major, stated honestly rather than rounded up: nothing
in the DEPLOYED stack cancels the request task on a client disconnect, so I
cannot currently trigger it from outside. I verified that rather than assuming:

- `uvicorn` 0.51.0/0.52.4 `httptools_impl` sets `self.cycle.disconnected = True`
  and returns `{"type": "http.disconnect"}` from `receive()`. It does not
  cancel the application task.
- `starlette.routing.request_response` does not run the handler in a task group
  with a disconnect listener. I read it in BOTH the local venv (1.3.1) and the
  DEPLOYED venv on the box (1.6.0). Neither cancels.

So the defect is real, is inside the round 2 fix for F-4.11-08, and is one
dependency upgrade away from being reachable. Starlette has shipped and then
reverted disconnect-driven cancellation before; it is not a hypothetical
direction for that library to move.

Confidence: HIGH that the behaviour is as measured. HIGH that it is not
externally reachable on the currently deployed versions.

### F-4.11-RV-04, MINOR (gate vacuity): the slot-release-on-every-path claim has no arm

Mutation M-A: I moved `query_slots.release()` out of the `finally` so a slot
leaks on every failed query, which is the precise failure the code comment
names ("A concurrency bound that leaks a slot per failed query is worse than no
bound: it degrades to zero capacity under exactly the conditions that make
queries fail").

Result: **51 passed. MISSED.** No arm anywhere catches it.

P13b, the only concurrency arm, drives two requests and its first one succeeds,
so it never exercises a failure path while holding a slot. This is
`self-eval-loop`'s named pattern exactly, and this repository's own F-2.1-J5-01:
a confident comment asserting a correctness property, sitting above code with
no test asserting the same property. The comment is currently true. Nothing
would tell the next phase if it stopped being true.

The arm this needs: drive `MAX_CONCURRENT_QUERIES + 1` requests where
`execute_cypher` raises, then assert a subsequent legitimate query still gets a
slot.

### Mutation results in full, my own mutations, run and restored

I wrote and ran ten mutations of my own rather than trusting the lead's eleven.
Each was applied, the gate run with `RUN_PREMISE_GATE=1`, then restored;
`git diff` over both source files is empty afterwards.

| id | control removed | outcome | arm that caught it |
|----|-----------------|---------|--------------------|
| M-A | slot release on the failure paths | **MISSED** | none (see F-4.11-RV-04) |
| M-B | the refusal-log volume bound | CAUGHT | P16 |
| M-C | the malformed-JSON audit record | CAUGHT | P15 |
| M-D | the trusted-proxy check on X-Forwarded-For | CAUGHT | P20 |
| M-E | the client timeout headroom (`httpx.Timeout` reverted to `timeout_s`) | CAUGHT | P21 |
| M-F | the ReadTimeout/WriteTimeout to GraphTimeoutError mapping | CAUGHT | P14 |
| M-G | `asyncio.to_thread` around the blocking executor | CAUGHT | P13 |
| M-I | `openapi_url=None` | CAUGHT | P19 |
| M-K | the `row_limit` type check | **MISSED** | none (redundant with Pydantic; see below) |
| M-L | the bounded concurrency wait ceiling | CAUGHT | P13b |

Eight of ten caught. On the two misses:

- M-A is a genuine gate gap and is filed as F-4.11-RV-04.
- M-K is NOT a gate gap. `CypherRequest.row_limit: int` already rejects a bool
  and a non-integer at the Pydantic boundary, so `_validate_row_limit`'s type
  branch is unreachable defense-in-depth. Recorded so the number is honest, not
  filed.

Every arm round 2 ADDED is therefore proven NON-VACUOUS by mutation: P13 (M-G),
P13b (M-L), P14 (M-F), P15 (M-C), P16 (M-B), P19 (M-I), P20 (M-D), P21 (M-E).
P22's five parametrized cases are non-vacuous by construction (each raises a
distinct `httpx` type and asserts the mapped `GraphError` subclass), and M-F
confirms the mapping is load-bearing. P17 and P18 I did not mutate directly;
they are asserted below under Question 3.

This is the first phase in the recent run where I could not find a vacuous arm.
Given fourteen in build phase 4.3, four in 4.6 and three already in this phase,
that is worth stating plainly as a positive result.

### F-4.11-RV-05, MINOR: the code names a gate arm, `P16b`, that does not exist

File and line: `services/graph_query_service/app.py`, line 799:

```
# F-4.11-J-03: this line had no arm. The fix for F-4.11-03 added
# TWO log lines and only the auth one was pinned, so deleting
# this one left both suites green. P16b pins it now.
```

`grep -rn "P16b" tests/ services/` returns exactly one hit: that comment. No
arm named P16b was ever written, in the premise gate or in
`tests/services/graph_query_service/test_app.py`.

The property IS pinned, by P15's final block, which drives the caller past
`RATE_LIMIT_PER_MINUTE` and asserts `"rate limited"` appears in the records. I
proved it by mutation M-N below: deleting that `_emit_refusal` call turns P15
red. So this is a wrong citation rather than an unpinned control.

It matters anyway, at MINOR, because the finding it claims to close,
F-4.11-J-03, is precisely "a fix was written and only half of it got an arm".
A reader auditing whether J-03 is closed will look for P16b, not find it, and
have to re-derive the answer. The comment should name P15.

### Question 3: do the eleven round 1 findings actually hold?

I did not trust the "11 of 11 caught" claim. I wrote fifteen mutations of my
own across two rounds, ran each with `RUN_PREMISE_GATE=1`, and restored each.

Second mutation round, all against `services/graph_query_service/app.py`, run
over the premise gate plus `tests/services`:

| id | control removed | outcome | arm |
|----|-----------------|---------|-----|
| M-N | the per-caller rate-limit audit line (J-03's other half) | CAUGHT | P15 |
| M-O | the PRE-AUTH source bound (J-05 / 10) | CAUGHT | P17 |
| M-P | the unified auth-failure message (J-08 / 10) | CAUGHT | P18 |
| M-Q | the auth-rejection audit line (F-4.11-03) | CAUGHT | P11c and P15 |
| M-R | rightmost XFF parsing, replaced with the spoofable leftmost variant | CAUGHT | P20 |

Fifteen mutations total, thirteen caught, two missed (M-A, a real gate gap
filed as F-4.11-RV-04; M-K, redundant with Pydantic and not a gap).

Per-finding disposition, each backed by evidence I produced rather than by the
commit message:

| Round 1 finding | Holds? | My evidence |
|-----------------|--------|-------------|
| F-4.11-J-01, CRITICAL, twelve arms silently skipping | YES | `requires_graph` survives only in docstrings; no decorator uses it. `RUN_PREMISE_GATE=1` gives 122 passed / **0 skipped**, and without it 44 passed / 7 skipped, so only the genuinely-live-only arms gate |
| F-4.11-J-02, P1 unrunnable after cutover | YES, with a caveat | P1 runs and passes against the committed baseline with no tunnel. See the baseline assessment below for how much weaker that claim is |
| F-4.11-J-03, the unpinned rate-limit log line | YES | M-N caught by P15. But the comment cites a nonexistent P16b: F-4.11-RV-05 |
| F-4.11-J-04, the runbook's firewall fiction | YES | The runbook now says there is no firewall. I independently confirmed on the box: `ufw status` = inactive, and `ss -tlnp` shows Postgres and uvicorn both bound to loopback, so the binding is genuinely carrying the whole load exactly as the corrected text says |
| F-4.11-J-05 / F-4.11-10, unbounded unauthenticated path | PARTLY | The rate bound and the log-volume bound are real and mutation-proven (M-O, M-B). The KEYSPACE both bounds allocate is still unbounded: F-4.11-RV-01 |
| F-4.11-J-06 / F-4.11-09, client timeout and error type | YES | M-E and M-F both caught, by P21 and P14. P22 pins the full httpx mapping |
| F-4.11-08, the blocked event loop | YES | M-G caught by P13. Also re-verified LIVE by me, below |
| F-4.11-10 (auth message half) | YES | M-P caught by P18 |
| F-4.11-11, the forwarded client address | YES | M-D and M-R both caught by P20, including the leftmost-parse variant |
| F-4.11-12, `/openapi.json` | YES | M-I caught by P19 |

#### F-4.11-08 re-verified LIVE, which the phase's own gate does not do

This one deserves its own paragraph. The defect was MEASURED live (the
adversary timed `/healthz` at 10.97s). P13, the arm that closes it, is an
in-process arm: it builds the app with `build_app()` and drives it over
`httpx.ASGITransport`. It never touches the deployed service. Locally that is
Python 3.11.6 with starlette 1.3.1; the box runs **Python 3.12.3 with starlette
1.6.0** (read from the deployed venv). So the fix for the phase's headline
defect is proven in a runtime that is not the one the defect was measured in.

I closed that gap myself. No single legal query on this graph is slow (five
candidates all returned in under a second, the graph is well indexed), so
instead I fired 20 concurrent legal queries at the deployed service while
probing the unauthenticated `/healthz`:

```
burst of 20 concurrent queries finished in 1.38s, statuses {200: 20}
healthz probes during the burst: 4, all 200: True
healthz latency: median 0.135s, worst 0.501s
```

On the blocking implementation those 20 queries would have serialized to about
18 seconds with `/healthz` blocked behind them. The fix holds against the real
deployment. F-4.11-08 is genuinely closed.

#### How much weaker is the committed byte-equality baseline?

The brief asked. My answer: meaningfully weaker, but the design is honest and
contains the one guard that matters most.

Weaker in three ways:
- It compares a live HTTPS read against a FROZEN expectation, not against a
  second live transport. It can no longer distinguish "the HTTPS transport
  regressed" from "the graph data changed". The graph is a pinned snapshot, so
  this is unlikely, not impossible.
- Its provenance is a self-declared `"transport": "psycopg2"` string in a JSON
  file with no checksum and no signature. A future agent under pressure to make
  a red arm green can hand-edit `fixtures/phase_4_11_byte_equality.json` to
  whatever HTTPS returns, and nothing detects it. Against a live comparison
  that move is not available.
- Nothing checks `captured_at` for age. A baseline captured before a later
  change is accepted forever.

Stronger than I expected in one way, and it is the load-bearing one:
`_write_baseline` is called ONLY when `_psycopg2_is_reachable()` is true, which
requires the retired tunnel to be reopened deliberately. The baseline therefore
cannot be re-minted from the HTTPS transport's own output. The comparison
cannot go circular by accident, which is the failure mode that would have made
it worthless rather than merely weaker.

And the third branch is right: with no baseline and no psycopg2, P1 FAILS loudly
rather than skipping. That is the correct response to F-4.11-J-02 and it is what
the phase got wrong the first time.

Net: I would accept it, and I would add a SHA-256 of the fixture asserted in the
arm so a hand-edit is a red arm rather than a silent one.

### Correction to F-4.11-RV-02, made after the evidence changed

When I filed RV-02 I argued the wrong comment mattered because a future
maintainer might "correct" the code to the conventional leftmost reading, and
the claimed second layer would not save them. Mutation M-R tests exactly that
refactor: I replaced `forwarded.rsplit(",", 1)[-1]` with
`forwarded.split(",", 1)[0]`. **P20 catches it.**

So the failure path I invoked to justify the severity is already closed by a
test. RV-02 stands as a documentation-accuracy defect only: the Caddyfile does
not do what the comment says it does, on the box as well as in the repository.
Severity holds at MINOR, but the reason narrows to "a false statement about the
deployed infrastructure sits in the source", not "a refactor could exploit it".

I am recording the change rather than editing the original, because a review
that quietly rewrites its own findings once the evidence moves is not a review.

---

## Summary of findings

| id | severity | what | regression of | confidence |
|----|----------|------|---------------|------------|
| F-4.11-RV-01 | major | the pre-auth source bound and the refusal log retain one permanently-allocated entry per distinct source address, never evicted; unauthenticated, IPv6-reachable | F-4.11-J-05, F-4.11-10 | HIGH, reproduced |
| F-4.11-RV-02 | minor | `client_source`'s docstring claims the deployed Caddyfile OVERWRITES `X-Forwarded-For`; it has no XFF directive at all and Caddy's default appends | none | HIGH, read the deployed file |
| F-4.11-RV-03 | latent | `to_thread` cannot cancel its thread, so a cancelled request returns its concurrency slot while the query still runs; measured 4x over the bound. Not externally reachable on the deployed uvicorn/starlette | F-4.11-08 | HIGH on behaviour, HIGH on non-reachability |
| F-4.11-RV-04 | minor | the "slot returned on every path" claim has no arm; mutation M-A passes 51/51 with the release moved out of `finally` | none (gate) | HIGH, mutation-proven |
| F-4.11-RV-05 | minor | `app.py:799` cites gate arm `P16b`, which does not exist anywhere; the property is actually pinned by P15 | none | HIGH, grep |

Nothing I found is CRITICAL. Nothing I found makes a shipped answer wrong.

## What I could NOT verify

Stated so the number is honest rather than laundered.

- Nothing. I reached the box by `ssh` and by HTTPS, ran the live gate with
  `RUN_PREMISE_GATE=1` (122 passed, 0 skipped), ran `check_drift.sh` (5 of 5
  ok), read the deployed Caddyfile, the deployed dependency versions and the
  deployed starlette source, and re-verified F-4.11-08 against the live
  service. No item in this report is UNVERIFIED.
- One thing I deliberately did NOT do: I did not attempt the RV-01 memory
  exhaustion at scale against the live service. I proved the mechanism
  in-process (3000 sources, 3000 retained keys) and proved the IPv6 ingress
  exists (`healthz` 200 over IPv6 with no firewall). Actually exhausting the
  box's memory would be an attack on a running service, not a review.

## What I would attack next, if this had another round

1. The `_encode_rows` contract under a graph that returns a nested agtype
   structure. The service raises `graph_wire_encoding` on anything not `str`
   or `None`. Nothing in the gate feeds it a real non-string cell from the
   live graph; every arm that exercises it stubs `execute_cypher`.
2. The transitive dependency set. `requirements.txt` pins five direct packages
   and nothing else. The deployed tree carries starlette 1.6.0, anyio 4.14.2,
   h11, httpcore, pydantic_core and six more, all unpinned and all resolved
   fresh on every deploy. `supply-chain-security` asks for a committed
   lockfile; the deploy comment discloses the gap honestly but does not close
   it. This is also what would silently flip F-4.11-RV-03 from latent to
   reachable, so the two are the same risk seen from two sides.
3. `check_drift.sh` covers the five Python files and NOT the Caddyfile or the
   systemd unit, so the exact class of hand-edit it exists to detect is
   undetected for the two files that define the service's exposure.

## Merge recommendation

**MERGE WITH TRACKED FLAGS.**

The single strongest reason: this is the first phase in this repository's
recent run where I could not find a single vacuous gate arm. Fifteen
independent mutations, thirteen caught, and the one real miss (M-A) is a
missing arm for a property that is currently TRUE, not a broken control. Every
arm round 2 added is mutation-proven non-vacuous, both edited arms were
genuinely strengthened rather than weakened, and the phase's headline fix holds
against the live deployment, which I verified myself rather than reading. The
transport this build depends on works, over HTTPS, with no tunnel open.

Flags to track, in priority order:
1. F-4.11-RV-01 (major). The unbounded per-source keyspace. It should be fixed
   before this service carries production traffic, and its arm must drive many
   sources, not one, or it repeats P16's blind spot.
2. F-4.11-RV-04 (minor). The missing slot-leak arm. Cheap to write, and it
   guards the control that F-4.11-08's fix rests on.
3. F-4.11-RV-05, F-4.11-RV-02 (minor, documentation). Two source comments state
   things that are not true. This repository has a standing rule that a comment
   asserting a property is a claim to be tested; both should be corrected in the
   same pass.
4. The transitive-pin gap, already disclosed in `deploy.sh` and not closed.

I do NOT recommend a third fix round for these. None is reachable in a way that
produces a wrong answer, RV-01 needs a sustained deliberate attack on a service
with one machine caller, and this repository has measured that each additional
round has historically introduced its own worst defect. Land it, track the five,
and fix RV-01 as its own small change with its own arm.

---

Re-verification complete. Working tree restored: `git diff` over
`services/graph_query_service/app.py` and
`src/system_03_search_agent/tools/graph_http_transport.py` is empty, and every
mutation was reverted.
