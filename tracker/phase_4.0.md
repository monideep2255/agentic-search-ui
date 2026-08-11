# Phase 4.0: the REST plus SSE adapter finalized as the public API surface

Build phase 4.0 finalizes `adapters/web_sse/` (Section 13.1) as the one canonical public API surface every other adapter builds on: build phase 4.2 (CLI) is a thin client over this surface, and build phase 4.1 (MCP) folds through the same `run()` core. Nothing downstream should have to work around a gap in this phase's own deliverable.

Depends on: build phase 2.2 (done, PR #18, merged). Not blocked on 3.x; this phase only touches the adapter layer above `run()`, never a tool.
Branch: `phase/4.0-rest-sse-hardening`
Spec: `requirements/Technical_specification.md` Section 13.1 (the REST plus SSE API table, resumability, cost/done filtering), Section 19.4/19.5 (operator visibility), Section 2.2 (the `seq` field the resumability design reuses)
Reference: `tracker/phase_1.2.md` (T-1.2-02's "minimal REAL version" scope note, explicitly naming this phase as the one that reworks `/query` into the finalized shape), `LEARNINGS.md`'s 2026-07-28 entry ("Adversary found run-lifecycle resource leaks", F-1.2-01/02/03), `docs/build/Build_workflow_cadence.md`

## Phase premise (the done-when)

A client that creates a run via `POST /v1/query`, disconnects from `GET /v1/query/{run_id}/events` mid-stream, and reconnects with `Last-Event-ID` set to the last `seq` it saw, receives every event it missed (never a gap, never a duplicate) and then the live tail, exactly as if it had never disconnected. A second, independent client attaching to the same `run_id` at the same time gets its own complete view of the stream, not zero events (F-1.2-03). A run nobody is listening to for longer than a short grace window stops consuming model and tool budget rather than running to completion unobserved (F-1.2-02). A registry that has been running for a long time does not grow without bound: a finished run's buffered events are dropped after the run's lifetime plus five minutes, matching Section 13.1's own retention window (F-1.2-01). `GET /v1/query/{run_id}/citations` returns the full, unredacted citation set for a run that has reached a terminal state, and a clear, actionable error for one that has not. An operator-scoped credential sees the real `cost` events and an unredacted `done.total_cost_usd` on `GET /v1/query/{run_id}/events`; every other credential never does, regardless of anything in the request body, matching the same server-side-only derivation the legacy `POST /query` endpoint already enforces for the operator allowlist (Section 19.4). The legacy `POST /query` endpoint, which Section 13.1 does not name and the frontend does not call, is removed, so "the public API surface" names one real set of endpoints, not two.

The verify surface is `tests/system_03_search_agent/adapters/web_sse/test_phase_4_0_premise.py`, not a suite total, per `tracker/phase_3.1.md`'s standing rule.

Correction, F-4.0-J-02 (judge review, build phase 4.0): this line originally asserted the gate "is written and watched failing... before any of T-4.0-01 through T-4.0-06 lands" as settled fact. The gate was genuinely written first and its failing arms were watched during the build session, but that state was never isolated into its own commit or its output captured into this file, so `git log` shows the gate landing in the same commit as the implementation it gates (`d5b79f6`), and the claim above was unverifiable from the repo alone, exactly the shape LEARNINGS.md row 43 exists to prevent. Per `.claude/rules/goal-contracts.md`'s "a verify surface must state its own coverage" and the judge's own instruction, the claim is corrected here rather than left standing on session memory: treat the failing-first observation as asserted, not git-verified, for this phase. The durable fix, to apply starting with the next phase, is to commit the premise gate on its own, watch and paste the failing run's real output into this file, and only then start implementation, so the claim is checkable by anyone reading the repo rather than resting on the builder's word.

## Scope boundary, decided rather than asked (v1-scope-boundary check)

Section 13.1 also names session-cookie auth for the web UI ("a session cookie for the web UI; a bearer API key for the CLI, the MCP adapter's own internal calls, and any other programmatic caller"). This is NOT built in this phase. It is a documented, already-judge-reviewed spec-versus-reality gap, not a gap this phase owns: `tracker/phase_1.2.md`'s judge round (line 187) already found and PASSED-on-substance that this backend has no cookie session, every protected route requires a Bearer token, and the native browser `EventSource` API cannot set custom headers, so the frontend's `useAgentRun.ts` hand-rolls SSE consumption on `fetch()` instead. That decision is logged in `DECISIONS.md` (2026-07-28 row). Rebuilding session-cookie auth now, with CSRF protection and a second auth mechanism to keep in sync with the bearer-token one, would be new architecture invented mid-phase with no named trigger, exactly what `.claude/rules/v1-scope-boundary.md` exists to stop. Flagged here rather than silently substituted: bearer-token auth stays the one real mechanism for every surface, and Section 13.1's cookie line is carried to Step 6.2's successor reconciliation (whenever one is next scheduled) as a spec correction, the same disposition already given to phase 3.2's `spdi/canonical_representative` substitution and phase 3.5's `SNP_distances.tsv` size gap.

## Pre-build source read (done before any code, before any ticket)

Per `.claude/rules/attack-the-constraint.md`'s instruction to read the actual input before debugging generation, and LEARNINGS.md's standing pre-build-probe pattern (phases 3.2/3.3/3.5): read every file this phase touches before writing a ticket.

| Read | Finding |
|------|---------|
| `core/run_registry.py` (current) | Single `asyncio.Queue` per run, drained destructively by exactly one consumer. A second attacher on the same `run_id` gets an empty stream, matching F-1.2-03 exactly. No eviction of `_runs` (F-1.2-01). No subscriber-count or cancellation-on-abandonment logic (F-1.2-02) |
| `contracts/events.py` | `Event.seq: int = Field(..., ge=0)` already exists on the envelope (Section 2.2); `core/run.py` already assigns it monotonically per run, starting at 0, with no gaps, including through the crash-fallback path (`start_seq` threading). Resumability's ordering key already exists end to end; only the registry needs to retain and expose it |
| `adapters/web_sse/app.py` (current) | `GET /v1/query/{run_id}/events` calls `sanitize_event_for_end_user` unconditionally, with no operator branch at all, so an operator credential cannot see cost data through the finalized streaming path today, only through the legacy buffered `POST /query`. No `Last-Event-ID` handling. No citations endpoint. `POST /query` (buffered, list-response) coexists with the `/v1/query` triplet; `contracts/query.py`'s `RequestContext.operator_mode` is client-settable on `POST /query`'s body only, gated by `is_operator_user`'s allowlist as a second check, never read at all by the `/v1/query` family |
| `harness/cost_control.py` | `is_operator_user(user_id)` already derives operator status purely server-side from the `OPERATOR_USER_IDS` env allowlist keyed by the authenticated user's id; no client-supplied field is required to make this check, so wiring it into `/v1/query`'s family needs no new mechanism, only a call site |
| `frontend/src/hooks/useAgentRun.ts` | Calls `GET /v1/query/{run_id}/events` exclusively (fetch-based SSE parsing, documented reason above). Never calls `POST /query`. Confirms `POST /query` is dead in production, kept alive only by its own test coverage |
| Grep for `operator_mode` outside `contracts/query.py`, `app.py`, `cost_control.py` | None. `RequestContext.operator_mode` has zero effect inside the graph/core; it is purely an adapter-level filtering flag, so this phase's fix is confined to `app.py`, no contract or core change |

## Ticket map

| Ticket | Slice | Files |
|--------|-------|-------|
| T-4.0-01 | The premise gate, blocking | `tests/system_03_search_agent/adapters/web_sse/test_phase_4_0_premise.py` (new) |
| T-4.0-02 | `RunRegistry` redesign: an append-only per-run event log keyed by `seq`, multi-consumer `subscribe(run_id, after_seq)` replacing the single destructive queue (closes F-1.2-03), a lazy eviction sweep of runs past lifetime-plus-five-minutes (closes F-1.2-01), and subscriber-count-based delayed cancellation of an abandoned run (closes F-1.2-02) | `core/run_registry.py` |
| T-4.0-03 | Resumability on `GET /v1/query/{run_id}/events`: read `Last-Event-ID` (this backend's `fetch`-based SSE client can set arbitrary headers, unlike a native `EventSource`, so the header is honored directly, no query-param fallback needed), replay buffered events with `seq` greater than it, then continue live via T-4.0-02's `subscribe` | `adapters/web_sse/app.py` |
| T-4.0-04 | `GET /v1/query/{run_id}/citations`: full citation objects for a run in a terminal state (`done`, or a fatal `error`), reading `citation` events out of T-4.0-02's buffered log; `409` with an actionable message ("run has not finished; poll `/events` or retry after `done`") for a run still in flight, `404`/`403` reusing `_get_owned_run`'s existing ownership check | `adapters/web_sse/app.py` |
| T-4.0-05 | `operator_mode` server-side derivation on `POST /v1/query` and `GET /v1/query/{run_id}/events`: `is_operator_user(current_user.id)` alone decides whether the stream is filtered, never a client-supplied field (there is none on `CreateRunRequest` to remove; this is purely wiring the existing allowlist check into the two call sites that currently ignore it) | `adapters/web_sse/app.py` |
| T-4.0-06 | Remove the legacy `POST /query` endpoint, `QueryRequest`, and the doc comment block describing it as phase 1.0/2.0 scaffolding; port its unique test value (the typed-event-contract round-trip proof) onto the `/v1/query` family if not already covered there. Logged as a decision in `DECISIONS.md`: the frontend never called it (confirmed by grep above), and Section 13.1 does not name it, so "finalized as the public API surface" means removing the surface that was never part of the finalized shape, not keeping two parallel query endpoints in sync forever | `adapters/web_sse/app.py`, `tests/system_03_search_agent/adapters/web_sse/` |

Depends-on chain: T-4.0-01 blocks everything (written and watched failing first). T-4.0-02 is the foundation ticket; T-4.0-03, T-4.0-04, and T-4.0-05 all depend on it (they read/replay the buffered log T-4.0-02 introduces). T-4.0-06 depends on nothing but T-4.0-01.

Correction made before dispatch, not after: the original ticket map scoped T-4.0-05 as touching both `POST /v1/query` and `GET /v1/query/{run_id}/events`, which would have collided with T-4.0-03's edit to the same `GET /events` handler. On closer read, `POST /v1/query` does no event filtering itself (it only creates the run and returns `202`; every filtering decision happens at read time), so T-4.0-05 is entirely a `GET /events` change, the same handler T-4.0-03 already rewrites for resumability. Folded into one task rather than dispatched as two builders racing the same function body.

Dispatch plan: the lead writes T-4.0-02 directly (the concurrency-sensitive core: subscriber bookkeeping, eviction, delayed cancellation are the highest-defect-risk surface in this phase and get the strongest available reasoning rather than a delegated, bounded task, per `.claude/rules/plan-then-fan-out.md`'s "work where every item needs frontier reasoning... keep those on the stronger model"). The lead also does T-4.0-06 directly (small, mechanical deletion, not worth a dispatch's fixed setup cost per `plan-then-fan-out.md`). One `isolation: "worktree"` builder takes T-4.0-03, T-4.0-04, and T-4.0-05 together (all three live in the same region of `app.py`, all three consume T-4.0-02's `subscribe` interface, and none of them touch the file's top half where T-4.0-06 works), running concurrently with the lead's T-4.0-06 edit in the main checkout. The lead integrates the builder's branch back onto the phase branch afterward.

## Premise gate design

Written and watched failing before T-4.0-02 exists, per LEARNINGS.md row 43's discipline (every failure `ModuleNotFoundError`/`AttributeError`, never a network fault or a fixture bug).

### The arms (planned)

| Arm | Cases | What it pins |
|-----|-------|---------------|
| Resumability | Create a run, drain some events, disconnect mid-stream, reconnect with `Last-Event-ID` set to the last seen `seq`; assert no gap, no duplicate, the stream still ends on `done` | The real reconnect path Section 13.1 requires |
| Multi-consumer | Create a run, attach two independent subscribers before it finishes; assert both see the complete event set (F-1.2-03) | The core defect the adversary found in build phase 1.2 |
| Eviction | Create a run, let it finish, advance past the retention window (a monkeypatched clock or an injectable TTL, not a real 5-minute sleep), assert the run is no longer retrievable and a stale read returns 404, not stale data (F-1.2-01) | The unbounded-growth fix |
| Abandonment | Create a run, attach and then disconnect the only subscriber, advance past the grace window; assert the run's background task is cancelled and no further tool/model calls occur (F-1.2-02) | The wasted-cost fix |
| Citations, terminal | A finished run's `GET /citations` returns every `citation` event's payload, matching what `/events` would have shown | The export shape |
| Citations, in-flight | A run still executing returns `409` with an actionable message, never a partial or fabricated citation list | The retry-safety gate (production-standards.md): the error tells the caller what to do next |
| Operator visibility | An operator-allowlisted credential sees `cost` events and an unredacted `done.total_cost_usd` on `GET /events`; a non-operator credential never does, regardless of any request body content (there is none to vary, confirming the fix removed the client-controllable surface entirely) | Closes the silent regression versus the legacy endpoint |
| Legacy removal | `POST /query` returns 404 (route gone), and the full typed-event-contract round-trip this route used to prove is still asserted somewhere in the suite, against `/v1/query` instead | Confirms nothing was lost by removing dead code |
| Wire-level resumability (added, fix round, F-4.0-J-01) | Every SSE frame carries an `id:` line matching its own `seq`; a reconnect driven exclusively by that wire `id:` (never the JSON body's `seq`) delivers real remaining events with zero overlap against what the first connection already saw | Closes the gap the judge's own wire capture found: the original gate proved resumability by reading `seq` out of the JSON body, the exact workaround a standards-conforming client cannot perform |
| Invalid resume cursor (added, fix round, F-4.0-J-03) | A `Last-Event-ID` beyond the run's highest emitted `seq` is rejected with `400`, not silently accepted as a valid (if unservable) subscriber | Closes the abandonment-check bypass: an unservable subscriber no longer counts toward `subscriber_count` |

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s coverage-declaration discipline: session-cookie auth (out of scope per the boundary above), true multi-process registry state (still explicitly single-process, module-level, per `run_registry.py`'s own existing scope note, unchanged by this phase), and load-scale behavior under many concurrent runs (a rate-limiting and concurrency concern owned by build phase 6.0, not this one).

## Findings

Judge round 1, verdict FAIL, ran against the integrated branch (`d5b79f6` + `5784caa`). Two blocking, five non-blocking. The judge wrote nothing to this file itself (correct per protocol on a FAIL verdict); these rows are the lead's transcription of its report, for the fix round to work against.

| Finding | Severity | Status | Description |
| --- | --- | --- | --- |
| F-4.0-J-01 | BLOCKING (major) | closed (judge round 2) | `GET /v1/query/{run_id}/events` never emitted an SSE `id:` line, so no standards-conforming client (a native `EventSource`, or any off-the-shelf library build phase 4.2's CLI might use) could ever produce a real `Last-Event-ID` on reconnect; the premise gate itself worked around the gap by reading `seq` out of the JSON body instead of the wire `id:`. Judge captured raw wire bytes proving a reconnect with an empty `Last-Event-ID` re-delivers the entire run as duplicates, the exact failure the phase premise names as forbidden. Fixed in `app.py`'s `_event_stream`: every yielded frame now carries `"id": str(forwarded.seq)`. Judge round 2 confirmed independently, not via the phase's own arms: a fresh wire capture shows `id: 0`, `id: 2`, `id: 4`, `id: 6`, `id: 7`, `id: 8`, `id: 9`, `id: 11` on the eight frames a non-operator sees, each matching its own body `seq`, and the gaps at 1, 3, 5, 10 are the filtered `cost` events, which is the proof that using the envelope `seq` rather than a per-connection counter was the correct call. A reconnect driven only by the wire `id:` returned exactly `['2','4','6','7','8','9','11']` against an expected `['2','4','6','7','8','9','11']`, compared as an ordered list rather than a set so a duplicate would fail, and the round-1 repro (empty `Last-Event-ID`) now behaves correctly as a deliberate full replay |
| F-4.0-J-02 | BLOCKING (evidence) | closed (judge round 2) | The "written and watched failing first" claim (this file, line 14) was unverifiable from git history: the gate landed in the same commit as its implementation, no separate failing-first commit or captured output exists. Corrected above rather than asserted as fact; process note added for future phases. Judge round 2 accepts this disposition: the correction downgrades the claim to "asserted, not git-verified" instead of manufacturing evidence after the fact, which is the honest resolution, and it names a durable process fix (commit the gate alone, paste its failing output here, then implement) that makes the claim checkable from the repo starting next phase. Closed as a corrected record, not as a verified failing-first run |
| F-4.0-J-03 | moderate | closed (judge round 2) | A subscriber attaching with an `after_seq` far beyond anything the run has ever produced (e.g. `Last-Event-ID: 999999999999`) still counted toward `subscriber_count`, defeating F-1.2-02's abandonment check: a run can be held alive indefinitely by a caller who will never actually receive an event. Fixed at the HTTP boundary in `GET /events`: `after_seq` is now rejected with `400` if it exceeds the run's highest emitted `seq` at request time, checked before `EventSourceResponse` is constructed so the rejection is a real status code, not an error inside an already-started stream. Judge round 2 verified the case the phase's own arm does not cover, an in-flight run rather than a drained one, which is where the wasted-budget attack actually lives: `Last-Event-ID: 999999999999` against a live run whose highest emitted seq was 0 returned `400` with an actionable detail, and `entry.subscriber_count` stayed at 0, so the rejected cursor no longer pins the run. Three boundary regressions were checked against the fix itself and all pass: a cursor equal to the run's highest seq returns `200` with zero frames (a legitimate caught-up resume, not a `400`), a cursor of `-1` returns `200` with a full 8-frame replay, and a brand-new run with zero buffered events and no header returns `200` rather than tripping the `current_max_seq = -1` comparison, which would have broken every run's first connection |
| F-4.0-J-04 | minor | closed (judge round 2) | Three comments outside `app.py` still referenced the removed `POST /query` route (`contracts/query.py:33`, `core/graph.py:719`, `tests/system_03_search_agent/core/test_graph.py:1992`). Corrected to `POST /v1/query`. Judge round 2 re-grepped all three sites and confirmed each now reads `POST /v1/query`. A repo-wide grep for `POST /query` returns three remaining hits (`app.py:84`, `auth/test_router.py:567`, `test_phase_4_0_premise.py:7`), all of which correctly name the removed endpoint as removed and must keep the old spelling |
| F-4.0-J-05 | minor | closed (judge round 2) | `run_registry.py`'s module docstring described `RunEntry.queue` as "drained destructively by exactly one consumer," no longer true of any shipped path now that `GET /events` reads `subscribe()` instead; only this phase's own test suite still reads `queue` directly. Docstring corrected to state this explicitly, per `.claude/rules/self-eval-loop.md`'s "a comment asserting a property is a claim to be tested". Judge round 2 read the corrected docstring and confirms it now states plainly that no shipped HTTP path reads `queue`, that both buffers coexist and consume memory together for a run's lifetime, and that this is intentional test-fixture support bounded by the same eviction window rather than a leak. That matches the code: `_drain_into_entry` still appends to both, and the tests that justify keeping it are real (`test_run_registry.py` lines 101, 117, 148, 168, 171, 222, 312 and `test_streaming_endpoints.py` lines 347, 504, 505) |
| F-4.0-J-06 | minor | closed (judge round 2) | `GET /citations` had no `maxItems` cap (`production-standards.md`'s multi-agent pipeline gate requires one on every array) and constructed `CitationPayload(**event.payload)` with no guard against a malformed payload turning into an unhandled 500. Fixed: response capped at 50 (matching Section 13.2's MCP citation array), and a malformed citation event is now skipped with a logged warning rather than crashing the export. Judge round 2 verified the guard by bypassing the envelope validator with `Event.model_construct` to inject a citation payload that `CitationPayload` rejects: the export returned `200` with `[]` instead of a 500. Two notes that make the 50-cap safe rather than a silent-truncation risk of the kind phase 3.2's `_cap()` finding warns about. First, `Event` itself validates a `citation` payload against `CitationPayload` at construction, so the malformed case is unreachable through any normal producer, which is why the injection needed `model_construct`. Second, `core/graph.py`'s `_MAX_CITATIONS_PER_ANSWER = 20` already caps a run's citations at 20 and surfaces its own `citations_capped` flag, so the 50-item break is genuine defense in depth with a 2.5x margin, not a live truncation path. The `app.py` comment attributing the bound to Section 21's tool-call cap names the wrong mechanism, but reaches the right conclusion |
| F-4.0-J-07 | minor | closed (judge round 2) | `Last-Event-ID` header had no `max_length`, against the rule's blanket requirement (not exploitable in practice, since `int()` already bounds every malicious shape tried). Capped at 32 chars. Judge round 2 verified both sides of the boundary: a 33-character `Last-Event-ID` returns `422` at the FastAPI validation layer, and a 32-character one passes the length check and is then rejected `400` on its value by F-4.0-J-03's check, which is the correct division of labor between the two gates |
| F-4.0-J3-01 | moderate | open, carried | New, filed by judge round 3 against the adversary fix round. The two disclosure headers that round added, `X-Run-Cancelled` (F-4.0-A-05, closing a major finding) and `X-Citations-Export-Truncated` (F-4.0-A-13), are unreadable by a cross-origin browser client, because the CORS middleware at `adapters/web_sse/app.py:70-76` declares `allow_headers` but no `expose_headers`. Verified live: a `GET /v1/query/{run_id}/citations` carrying `Origin: http://localhost:5173` returns `access-control-allow-origin: http://localhost:5173` and `access-control-expose-headers: None`, so JavaScript on the frontend's own dev origin cannot read either header. Section 13.1 names the web UI as one of the two first-class consumers of this surface, and the CORS middleware exists in this app precisely because the frontend is cross-origin, so this is the one consumer class the disclosure does not reach. The named build-order consumers are unaffected: build phase 4.1's MCP adapter and 4.2's CLI are server-side HTTP callers with no CORS layer, and the header is correct on the wire for both. Not blocking, argued both ways in the Judge review section below. The fix is one line, adding `expose_headers=["X-Run-Cancelled", "X-Citations-Export-Truncated"]` to the existing middleware call, with no design risk |
| F-4.0-J-08 | minor | open, carried | New, filed by judge round 2 against the fix round itself. `frontend/src/hooks/useAgentRun.ts:118` still reads "`id:` and `retry:` lines are part of the SSE spec but are never emitted by `_event_stream`; intentionally not parsed." As of `d8bec51` the backend does emit `id:`, so the comment is now false. No behavior is affected: `parseSseFrame` only reads `event:` and `data:` lines and silently ignores everything else, and the frontend suite is green at 120 of 120. Carried open rather than fixed here for a named reason, per this repo's carried-finding convention: the frontend does not yet consume `id:` at all, and wiring a real reconnect cursor into the client is build phase 4.2's client-side work, so the comment should be corrected in the same change that makes the client actually use the field, not left half-updated in between |

## Judge review

Round 1, 2026-08-10, against `d5b79f6` plus `5784caa`: FAIL. Two blocking findings (F-4.0-J-01, F-4.0-J-02) and five non-blocking. Full report transcribed in the Findings table above.

Round 2, 2026-08-10, against `d8bec51`: PASS. Ready for the adversary round.

### Evidence, round 2

Every number below was produced by the judge in this session, not taken from the fix round's report.

| Check | Result |
| --- | --- |
| Phase premise gate | `21 passed in 5.61s` (was 18; three arms added for F-4.0-J-01 and F-4.0-J-03) |
| Adapter, registry and auth-router regression suite | `105 passed, 1 warning in 11.93s` (was 102) |
| Full repo suite | `6 failed, 2392 passed, 113 skipped, 1 xfailed, 1 warning in 49.57s` |
| Ruff, all four changed source files | `All checks passed!` |
| Frontend suite | `Test Files 15 passed (15)`, `Tests 120 passed (120)` |

The 6 full-suite failures are the same pre-existing, live-network-opt-in-gated failures round 1 already cleared, unchanged in count and identity. All six are in `tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py`, all fail on `LiveHttpCallInUnitSuiteError` against `clinicaltrials.gov` and other live hosts, and `git diff develop...HEAD -- tests/system_03_search_agent/synthesis/ | wc -l` returns `0`, so this branch never touched that file or the tools it exercises. Not a regression.

### Independent verification of the fixes

The fix round added its own premise-gate arms for F-4.0-J-01 and F-4.0-J-03. Those arms were not treated as the evidence, since a fix grading itself is the maker-checker violation `.claude/rules/self-eval-loop.md` forbids. Each finding was re-verified with a separate judge-authored probe driving the real FastAPI app, and the per-finding results are appended to each row of the Findings table above.

Two observations recorded rather than filed as findings, since the properties they concern are pinned elsewhere and proven:

- The new arm `test_reconnecting_using_only_the_wire_id_line_yields_zero_duplicates` compares id sets, and a set cannot detect a duplicate, so its name claims more than its assertion checks. The no-duplicate property is genuinely held: it is pinned by the pre-existing `test_reconnecting_with_last_event_id_replays_only_what_was_missed`, which compares ordered lists, and independently confirmed by the judge's own ordered-list probe.
- The premise-gate table row added for F-4.0-J-01 describes the reconnect as delivering events "with zero overlap against what the first connection already saw." The reconnect legitimately does overlap, because the first connection was a full undisconnected drain, and the test's own inline comment explains this correctly at length. The table row's wording, not the test, is what is imprecise.

### Ticket status

Judge is the only role permitted to write `done` here, per the task-tracker convention.

| Ticket | Status | Reason |
| --- | --- | --- |
| T-4.0-01 | done | The premise gate exists and is green at 21 of 21, and now pins the wire-level `id:` contract and the invalid-cursor rejection that round 1 found it was missing. Its coverage-exclusion statement is present and honest. The failing-first claim is corrected rather than asserted, per F-4.0-J-02 |
| T-4.0-02 | done | `RunRegistry`'s multi-consumer `subscribe`, lazy eviction and grace-period abandonment all verified by judge probes: no hang when a run finishes with nothing past `after_seq`, no dangling or double-scheduled `abandonment_check`, cancellation reaches `_drain_into_entry`'s `finally` and sets `finished=True` within one loop turn, and a live subscriber's stream terminates cleanly when `POST /stop` cancels the run |
| T-4.0-03 | done | Resumability is now complete on both ends. `Last-Event-ID` is read in and the matching `id:` is written out, verified on the wire at `id: 0, 2, 4, 6, 7, 8, 9, 11` with the gaps being filtered `cost` events, and a reconnect driven only by the wire id replays exactly the missing events in order with no duplicate |
| T-4.0-04 | done | `GET /citations` verified end to end: full citation set on a `done` run, empty list on a fatal-error terminal state, `409` with an actionable retry message in flight, `404` unknown, `403` wrong owner. `_get_owned_run` is the handler's first statement, so ownership is enforced before any data is read, and a cancelled run reaches the terminal state so the `409` clears rather than persisting forever |
| T-4.0-05 | done | Operator visibility derives only from `is_operator_user(current_user.id)` against the `OPERATOR_USER_IDS` env allowlist. `CreateRunRequest` is `extra="forbid"` with no operator field and `QueryRequest` is gone, so no client-controllable surface remains. Verified that the sanitizer copies rather than mutates, so an operator reading a run after a non-operator still sees the real `total_cost_usd` |
| T-4.0-06 | done | `POST /query` returns 404, `QueryRequest` is deleted, the unique test value was ported onto the `/v1/query` family rather than dropped, the auth-router routing regression was repointed, the decision is logged in `DECISIONS.md`, and the three stale comments round 1 found were corrected |

### Carried open

- F-4.0-J-08, minor, a stale comment in `frontend/src/hooks/useAgentRun.ts:118`. No behavior affected, frontend suite green. Reason for carrying: it belongs with build phase 4.2's client-side reconnect work, which is where the frontend will actually start consuming the `id:` field.

No `.claude/rules/v1-scope-boundary.md` crossing: the phase is adapter-and-registry only, and a grep of the full branch diff for BLAST, VCF, sequence-similarity, UCSC, distillation and ensemble surfaces returns nothing.

### Round 3, confirmation of the adversary fix round

2026-08-11, against `b42b26d`: PASS. All 8 targeted findings verified closed, the 2 disclosure resolutions verified accurate rather than cosmetic, and the 4 carried-open dispositions accepted with two qualifications recorded below. One new moderate finding filed (F-4.0-J3-01), carried, not blocking.

Verification stack, all run by the judge:

| Check | Result |
| --- | --- |
| Phase premise gate | `25 passed in 8.55s` |
| Targeted regression (adapters, registry, auth, contracts, graph) | `419 passed, 1 warning in 19.12s` |
| Full repo suite | `6 failed, 2396 passed, 113 skipped, 1 xfailed, 1 warning in 57.50s` |
| Ruff, all three changed source files | `All checks passed!` |
| Frontend suite | `Test Files 15 passed (15)`, `Tests 120 passed (120)` |

The 6 full-suite failures remain the same pre-existing live-network-gated cases cleared in rounds 1 and 2, unchanged in identity. Per-finding confirming evidence is appended to each row of the Adversary findings table above; it came from judge-authored probes driving the real app and the real registry, never from the fix round's own new gate arms.

Two things checked that the fix round did not claim, since a fix round is where a new regression is most likely to hide:

- The new `except asyncio.CancelledError` block in `_drain_into_entry` awaits (a lock acquire and a queue put) before it re-raises, so a second `cancel()` arriving mid-handler could in principle abort it and lose the synthetic terminal event. Attacked with a double and then triple stop in the same loop turn: the terminal event survives, `entry.cancelled` is `True`, `finished` is `True`.
- The cancellation event composes correctly with the resumability and cursor-validation machinery from rounds 1 and 2. A full replay of a cancelled run ends on the `error` frame; resuming from the last real event id delivers exactly the cancellation event and nothing else; resuming from the cancellation event's own id returns `200` with zero frames; resuming one past it returns `400`. No gap, no duplicate, no off-by-one introduced by giving the synthetic event a `seq`.

Attacked and held, recorded so it is not re-derived: `_SEQ_CURSOR_PATTERN`'s `\d` matches Unicode category Nd, which is broader than the ASCII digits `Event.seq` actually is, so a Unicode-digit cursor such as `٢` would pass the grammar check. It is unreachable over HTTP: header values are latin-1, and enumeration of all 256 latin-1 code points shows `\d` matches exactly `0` through `9` there. Not filed.

Assessment of the four carried-open dispositions, since the judge is not obliged to agree with the lead:

- F-4.0-A-14, accepted without qualification. Rushing a second redesign of `_reschedule_abandonment_check` in the same round that just rewrote its timer accounting is precisely the risk `LEARNINGS.md`'s build-phase-2.1 retrospective measured, where the worst defect in every round was a regression in the previous round's fix. The gap is documented in the module's own docstring, not left implicit.
- F-4.0-A-12, accepted as a genuine scope call rather than an excuse. The adapter has no structured field to read: `citations_capped` reaches the wire only as narrative `token` prose or a non-fatal refusal `error`, and inferring truncation from a citation count would be a guess, which is worse than disclosing nothing. One observation the round should own, though: it disclosed the unreachable truncation (F-4.0-A-13's local 50-cap, which `_MAX_CITATIONS_PER_ANSWER = 20` makes unhittable) and left the reachable one (a real run cut at 20) undisclosed on the export path. The priority is inverted relative to which gap a user can actually hit.
- F-4.0-A-10 and F-4.0-A-11, accepted on sequencing, but the rule citation is wrong and should not be repeated. `.claude/rules/v1-scope-boundary.md` governs capabilities named on the PRD out-of-scope list or the technical specification's fast-follow table; rate limiting is on neither. It is build phase 6.0 in the locked Section 25 build order, which that rule explicitly permits building toward. So the real argument is phase sequencing and round hygiene, not a scope boundary, and it is a good argument on its own: the exclusion was pre-registered in this file's coverage paragraph at phase open rather than invented after the finding, build phase 6.0 owns rate limiting by name, and there is no deploy or public URL, so the exhaustion path is not reachable by anyone but the product owner today. Two conditions attach to accepting the carry. First, the phase premise's clause "a registry that has been running for a long time does not grow without bound" is now known to be false as literally written, since bounding retention alone does not bound size when creation is unbounded; the fix round's own carried-open text says so honestly, and that disclosure must not be lost. Second, and this is the load-bearing one, F-4.0-A-10 and F-4.0-A-12 must be written into build phase 6.0's and their successor phase's own tickets, not left living only in this phase's file. `LEARNINGS.md`'s F-2.0-15 entry is the precedent: a deferral with a well-reasoned justification fell through twelve consecutive phases because no later phase ever actually named it, and it took a manual smoke test to find.

The two disclosure resolutions were checked against the code rather than accepted at face value, and both are substantive. F-4.0-A-08's comment states that the operator snapshot is per-connection, gives the reason, says when a revocation does take effect, and names why `_operator_user_ids()` being live-reloadable could otherwise read as a promise this call site does not keep; that matches `is_operator` being computed once before `_event_stream` is constructed. F-4.0-A-09's comment names the id-gap disclosure as the accepted cost of F-4.0-J-01's envelope-`seq` choice and explains why the alternative was rejected; that matches the observed non-operator id sequence `0, 2, 4, 6, 7, 8, 9, 11`.

On F-4.0-J3-01, the one new finding, the judgment call is recorded in both directions rather than asserted. Against blocking: the header is correct on the wire, both named build-order consumers of this endpoint (build phase 4.1's MCP adapter, 4.2's CLI) are server-side and read it fine, and no browser code calls `/citations` today. For blocking: Section 13.1 names the web UI as a first-class consumer, the CORS middleware exists in this app precisely because the frontend is cross-origin, and a future frontend developer who wires up a citation panel would see no header and could render a partial export as complete, which is a trust-moat failure of exactly the shape F-4.0-A-05 was filed for. The call is not to block, because nothing built today is wrong and no current consumer is affected, but the recommendation is to apply the one-line fix before this phase ships rather than carry it, since it has no design risk to weigh.

## Adversary findings

Round 1, 2026-08-10, against `d8bec51`. Unscripted adversary pass per `.claude/rules/self-eval-loop.md`'s two-verification-modes split: the judge above is the scripted checker and owns the accept-or-reject call, this section is the unscripted adversary and over-reports on purpose. The finder is not the closer: every row is filed `open` and none is triaged, fixed or closed here.

How these were driven: the real FastAPI app (`system_03_search_agent.adapters.web_sse.app:app`) was run under `uvicorn` on a real port with real `search_agent_users` PostgreSQL auth (real `/auth/signup` plus `/auth/login`, real bearer tokens) and the real LangGraph loop, using the same stub set the phase premise gate uses (`_harness_env`, the dispatching `litellm` stub, `_stub_symbol_resolution`, `_stub_ncbi_efetch_dispatch`, `_no_op_daily_caps`, `_auth_secret`). Nothing in `src/` was modified. Two additive things the harness adds, both outside the code under test: a read-only `/__adv/registry` introspection route so registry internals are observed rather than guessed, and a magic marker in the query text that makes the stubbed model sleep so a run can be held in flight long enough to observe lifecycle behavior on a real clock. The two lifecycle windows were scaled down through the constructor parameters `RunRegistry` already exposes (`abandon_grace_seconds` 30.0 to 3.0), so a 30-second grace window is observable inside a session; no code path changed.

| Finding | Severity | Status | Description |
| --- | --- | --- | --- |
| F-4.0-A-01 | major | closed (judge round 3) | Rapid connect-then-disconnect churn resets the abandonment timer indefinitely, so a client that never consumes a single event can hold an unwatched run alive past its grace window without limit, defeating F-1.2-02's stated purpose. `core/run_registry.py:253-263` (`_reschedule_abandonment_check`) cancels any pending check and schedules a brand new full-length one every time `subscriber_count` changes, and `core/run_registry.py:395-398` (`subscribe`'s `finally`) calls it on every detach. The window is therefore re-armed from zero on each reconnect rather than accumulating unwatched time, so any reconnect cadence shorter than `abandon_grace_seconds` keeps the run running forever. Judge round 3 confirmed by re-running the adversary's own churn attack at registry level, not via the new gate arm: control (grace 1.0s, nobody attaches) cancelled at t=1.02s, and the churn arm at a 0.45s cadence accumulated `cumulative_unwatched_seconds` 0.00 -> 0.40 -> 0.80 and was cancelled at t=1.36s over 3 cycles, versus the adversary's pre-fix 16.4s survival against a 3.0s window. A separate regression guard confirms the grace window still does its real job: a genuine 0.3s drop followed by a real reader is NOT killed. |
| F-4.0-A-02 | moderate | closed (judge round 3) | A malformed `Last-Event-ID` is silently downgraded to "replay the entire run", producing exactly the duplicate delivery the phase premise forbids, while a malformed-but-too-high one is rejected `400`. `adapters/web_sse/app.py:194-199` catches `ValueError` from `int(last_event_id)` and assigns `after_seq = -1`, `subscribe`'s replay-everything sentinel. `0x3`, `3.0`, `inf`, `nan`, `{"a":1}` and an empty string all take that path and return the whole run again with `200`. The same handler rejects `10` on a run whose highest seq is `9` with a `400` (F-4.0-J-03). Both inputs are cursors this run cannot honor; one is an error and the other is a silent full replay. Judge round 3 re-ran the adversary's full `Last-Event-ID` shape table against a live run: `+3`, `-0`, `-1`, `1_0`, `0x3`, `3.0`, `inf`, `nan`, the empty string, a 31-digit negative and `{"a":1}` all return `400`; zero shapes still silently full-replay. An absent header still full-replays by design. |
| F-4.0-A-03 | minor | closed (judge round 3) | `int()` accepts shapes no SSE client would ever emit and no reader would expect, so the cursor's accepted grammar is Python's integer literal grammar rather than the digits Section 2.2's `seq` actually is. `adapters/web_sse/app.py:196` uses a bare `int(last_event_id)`: `1_0` (PEP 515 underscore separator) parses as `10`, `+3` parses as `3`, `-0` parses as `0`, and a 31-digit negative parses to a huge negative that replays everything. No `pattern` constrains the header the way `CitationPayload.source_url` is host-pinned or `Event.seq` is `ge=0`. Judge round 3 confirmed the strict digit grammar in the same table run. Also attacked and held: non-ASCII digits (Arabic-Indic, fullwidth, Bengali) would match Python's `\d`, but HTTP header values are latin-1 and within latin-1 `\d` matches exactly ASCII 0-9, so the wider Unicode grammar is unreachable over HTTP. Verified by enumeration, not assumed. |
| F-4.0-A-04 | major | closed (judge round 3) | A cancelled run's SSE stream ends with no terminal event at all, so a client cannot tell "this run was stopped" from "my connection dropped". `POST /stop` cancels the background task, `core/run_registry.py:216-221` (`_drain_into_entry`'s `finally`) sets `finished=True` and notifies, and `subscribe` (`core/run_registry.py:393-394`) then returns on `entry.finished and not pending` without ever yielding a `done` or a fatal `error`. `adapters/web_sse/app.py:257-264` forwards whatever `subscribe` yields, so the HTTP response simply closes after the last real event. Every other exit path from this stream carries a terminal event; the one the API itself offers a button for does not. Judge round 3 confirmed a stopped run's stream now ends `('error', seq=1, error_class='cancelled', fatal=True)` after its last real event, with no seq collision and monotonic ordering. The double-and-triple-stop race I flagged as a regression risk against the new `except asyncio.CancelledError` block (which awaits, and so could be interrupted by a second cancel) does not materialize: the terminal event survives. |
| F-4.0-A-05 | major | closed (judge round 3) | `GET /citations` returns `200` with a silently incomplete citation list for a cancelled run, indistinguishable from a run that genuinely produced no citations. `adapters/web_sse/app.py:283-295` gates only on `entry.finished`, which a cancellation sets exactly as a normal completion does (`core/run_registry.py:217`), so a run killed after two events exports `200 []`. This is the same defect class `core/graph.py:2534` was fixed for at build phase 2.1 (F-2.1-C12), whose comment states the principle directly: "a result the user is shown only part of must never look identical to one they are shown in full." The export carries no `cancelled`, `complete` or `capped` flag of any kind. Judge round 3 confirmed `X-Run-Cancelled: true` on a run stopped after one real citation (body carries the real partial citation, header discloses it), and confirmed the absence of a false positive: a run that completes normally carries no such header. See F-4.0-J3-01 for the one gap in this disclosure channel. |
| F-4.0-A-06 | moderate | closed (judge round 3) | The `409` message tells a caller to do something that will never happen for a run that gets stopped. `adapters/web_sse/app.py:289-295` returns "run has not finished; poll GET /v1/query/{run_id}/events or retry this request after the done event", but a cancelled run never emits a `done` event (F-4.0-A-04), so a client following the message's own instruction on a run it is about to stop, or that abandonment cancels, waits for a signal that cannot arrive. `production-standards.md`'s retry-safety gate is explicitly what this string was written for: the error must say what to do next, and here it names a wrong next step for one real terminal path. Judge round 3 confirmed the live 409 detail is now "run has not reached a terminal state yet; poll GET /v1/query/{run_id}/events or retry this request once the stream ends (a done event, or a stop or cancellation)", which names the complete terminal set rather than `done` alone. |
| F-4.0-A-07 | minor | closed (judge round 3) | Every run leaves a sleeping abandonment-check task behind after it has already finished, for the full grace window. `core/run_registry.py:395-398` (`subscribe`'s `finally`) calls `_reschedule_abandonment_check` when the last subscriber detaches, and at that instant `entry.task.done()` is still `False`, because the drain task has not yet returned from its own `finally`. The guard at `core/run_registry.py:262` therefore passes and a fresh `_cancel_if_still_abandoned` task is created for a run that is over. Observed on every completed run in this round: `{'finished': True, 'task_done': True, 'abandonment_pending': True}`. It self-clears one grace window later (or on eviction, `core/run_registry.py:250-251`), so this is a bounded leak, not an unbounded one, but at the rate F-1.2-01 measured (400 runs in 32 seconds) the shipped 30-second window means hundreds of live sleeping tasks steady-state. Judge round 3 confirmed `abandonment_check is None` after a completed run drained by a subscriber, and after an unwatched run that finished on its own, against the adversary's observation of `abandonment_pending: True` on every finished run. |
| F-4.0-A-08 | minor | resolved by disclosure | Operator status is snapshotted once per request and held for the whole stream, so revoking an operator's allowlist membership does not stop an already-open SSE stream from continuing to emit `cost` events and an unredacted `done.total_cost_usd`. `adapters/web_sse/app.py:228` computes `is_operator = is_operator_user(str(current_user.id))` before `EventSourceResponse` is constructed, and `_event_stream` closes over that boolean for the life of the connection. `_operator_user_ids()` (`harness/cost_control.py:489-499`) deliberately re-reads the env var on every call precisely so the allowlist can change without a restart, and this call site is the one that cannot benefit from it. An SSE stream on a long-running deep-research query is exactly the connection that outlives an access change |
| F-4.0-A-09 | minor | resolved by disclosure | The wire `id:` gaps a non-operator receives disclose how many `cost` events were withheld and where in the pipeline each occurred. A non-operator's stream carries `ids = ['0', '2', '4', '6', '7', '9']`, so the four missing seq values are directly readable as four suppressed events, one after each of the guard, think, plan and synth model calls. The same comment that defines this boundary (`harness/cost_control.py:523-538`) records the product owner's rule as "cost and token usage are internal-only data", and the count of billable model calls is cost metadata. `adapters/web_sse/app.py:261` uses the envelope `seq` as the wire id, which F-4.0-J-01's fix chose deliberately and for a real reason (a per-connection counter would desync from `subscribe(after_seq=...)` across the filter), so this is a named tradeoff rather than an oversight. Filed because the tradeoff is not written down anywhere as a tradeoff |
| F-4.0-A-10 | major | open, carried (scope: build phase 6.0) | Eviction bounds how LONG a finished run is retained, not how MANY runs one caller can pile up inside that window, so F-1.2-01's underlying shape survives at a far larger scale than the 400-runs-in-32-seconds the original finding measured. One account created 9,615 runs in roughly 50 seconds of bursts with zero rejections, every one retained. `adapters/web_sse/app.py:137-152` (`post_v1_query`) has no admission control of any kind, and `core/run_registry.py:293-305` (`create_run`) unconditionally builds a `RunEntry` and starts a task. `PER_USER_DAILY_QUERY_CAP` cannot help, because it is enforced one layer below the registry, inside the run (`core/graph.py:731`), after the entry and its task already exist: verified live with the cap set to `2`, where 10 of 10 creates returned `202` and 10 of 10 registry entries were created |
| F-4.0-A-11 | moderate | open, carried (scope: build phase 6.0) | The lazy eviction sweep is O(n) over every retained run and fires on every `create_run` and every `get_run`, so the cost of the fix for F-1.2-01 is paid by every request and grows with what an attacker has piled up. `core/run_registry.py:237-251` (`_evict_expired`) builds a list comprehension across the whole `_runs` dict, and it is called at `core/run_registry.py:293` and `core/run_registry.py:315`, meaning every `POST /v1/query`, every `GET /events`, every `GET /citations` and every `POST /stop` scans the entire registry. Measured: median `GET /citations` went from 1.53 ms at 14 retained runs to 4.18 ms at 9,615, max 15.51 ms. Not a cliff at this scale, but it is superlinear work an unauthenticated-rate-limit-free create path controls, and the module docstring's justification ("every caller-facing entry point already touches the registry once per call, which is enough to bound staleness") reads the coupling as a benefit without naming the cost |
| F-4.0-A-12 | moderate | open, carried (needs a `DonePayload` contract change) | `GET /citations` drops the truncation disclosure the core deliberately produces, so an export consumer cannot tell a complete citation set from a capped one even though the run itself knew. `core/graph.py:4017` computes `citations_capped`, and `core/graph.py:4057-4062` turns it into a disclosure, but that disclosure is emitted as a `token` event (narrative prose) or, on the refusal branch, as a non-fatal `error` event. `adapters/web_sse/app.py:310-312` filters `entry.events` to `event.type == "citation"` only, so both disclosure channels are discarded. The endpoint exists precisely so a caller does not have to consume the whole stream (build phase 4.1's MCP surface and 4.2's CLI are its named consumers), and it is the one read path where the caller is guaranteed not to see the note. `core/graph.py:2519-2523`'s own comment states the rule this breaks: a caller must be able to tell "every citeable row is shown" from "there were more and the rest were silently dropped" |
| F-4.0-A-13 | minor | closed (judge round 3) | The `_MAX_CITATIONS_PER_RUN = 50` break is a silent truncation with no disclosure, the shape `tracker/phase_3.2.md`'s `_cap()` finding was fixed for. `adapters/web_sse/app.py:321-322` breaks out of the loop once 50 citations are collected and returns the list with nothing saying more existed. Unreachable today, and that is verified rather than assumed: `core/graph.py:4171` is the only `sink.emit("citation", ...)` call site in the codebase, and it iterates a list already cut to `_MAX_CITATIONS_PER_ANSWER = 20` at `core/graph.py:2535`. The reason to file it anyway is that the 2.5x margin is the ONLY thing making it safe, it is asserted in a comment rather than enforced by anything, and the two constants live in different modules with no test binding them. Raising `_MAX_CITATIONS_PER_ANSWER` past 50 in a later phase turns this into a live silent-truncation path with no failing test. Judge round 3 confirmed the boundary exactly: 50 citation events return 50 with no header, 51 return 50 with `X-Citations-Export-Truncated: true`. See F-4.0-J3-01, the header is unreadable cross-origin. |
| F-4.0-A-14 | moderate | open, carried (needs delivery-based liveness tracking) | One idle TCP connection that never reads a byte suppresses the abandonment check completely, which is a simpler bypass of F-1.2-02 than F-4.0-A-01's churn loop and shares its root cause. `core/run_registry.py:366-369` increments `subscriber_count` the moment `subscribe` is entered, and `core/run_registry.py:262` gates cancellation on `subscriber_count == 0`, so the registry's definition of "someone is watching" is "a connection is attached", never "an event was actually delivered". A client that opens `GET /events`, reads the response headers and then stops reading holds the count above zero indefinitely. Read together with F-4.0-A-10 (nothing bounds run creation), the composition is one idle socket per run, arbitrarily many runs, and the control that exists to stop unwatched runs never fires for any of them |

### F-4.0-A-01 repro

Harness grace window 3.0s (shipped default 30.0s; ratio preserved, see the note above). Control arm first, to prove the timer does fire when it is not being reset. Both arms run in the same process against the same live server, from `p02_abandon.py`.

Control, a run nobody ever subscribes to (real output, `GET /__adv/registry` polled once a second):

```
=== A: run nobody ever subscribes to (grace=3s) ===
  t= 1.0s {'subscriber_count': 0, 'finished': False, 'events': 0, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 2.0s {'subscriber_count': 0, 'finished': False, 'events': 2, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 3.0s {'subscriber_count': 0, 'finished': True,  'events': 2, 'task_done': True,  'task_cancelled': True,  'abandonment_pending': False, ...}
  model calls: 2
```

The control is cancelled between t=2.0s and t=3.0s, exactly one grace window after `create_run`, and `task_cancelled` is `True`. F-1.2-02's fix works when nothing resets it.

Attack arm, identical run, with one attach-and-immediately-drop cycle every 2.0s (under the 3.0s grace window). The attacker never consumes an event; each cycle is a bare `GET /v1/query/{run_id}/events` held open 0.05s and dropped:

```
=== C: CHURN - reconnect every 2s (< 3s grace), never consume ===
  t=  2.1s cycle=1 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t=  4.1s cycle=2 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t=  6.2s cycle=3 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t=  8.2s cycle=4 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 10.3s cycle=5 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 12.3s cycle=6 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 14.4s cycle=7 {'subscriber_count': 0, 'finished': False, 'task_done': False, 'task_cancelled': False, 'abandonment_pending': True, ...}
  t= 16.4s cycle=8 {'subscriber_count': 0, 'finished': True,  'task_done': True,  'task_cancelled': False, ...}
  >>> grace window is 3s; run survived 16.4 s of churn
```

Read the two arms together. `subscriber_count` is `0` at every single observation point in the attack arm, exactly as in the control, and `abandonment_pending` is `True` at every one of them, so a pending check genuinely exists the whole time and simply never gets to fire. The run survived 16.4s against a 3.0s window, more than five full grace windows, and ended by running out of work rather than by cancellation (`task_cancelled: False`, versus the control's `True`). Scaled to the shipped 30.0s default the same loop is one connection every 20 seconds, which no rate limit in this phase's surface bounds.

Reproduced twice: a second run of the identical script gave the same shape, the control cancelled inside one grace window and the churned run alive past five, with `task_cancelled: False` on the churned run both times.

Why this matters beyond the timer: the phase premise states "a run nobody is listening to for longer than a short grace window stops consuming model and tool budget rather than running to completion unobserved". A churning client is not listening in any meaningful sense (it receives nothing, `subscriber_count` is zero at every sampled instant) yet the run runs to completion, which is the exact outcome the premise forbids. The premise gate cannot catch this because all three of its abandonment arms (`test_a_run_nobody_ever_subscribes_to_...`, `test_a_run_a_subscriber_dropped_from_...`, `test_a_new_subscriber_before_the_grace_window_elapses_prevents_cancellation`) attach at most once. The third arm is the closest, and it pins the opposite property: that a reconnect DOES prevent cancellation, which is the intended behavior on a single reconnect and the bug on an unbounded sequence of them. No arm attaches twice.

Not filed as critical, and the reason is worth stating rather than leaving to the reader: a single run's spend is still bounded by `PER_QUERY_COST_CAP_USD`, so this is not unbounded spend per run. It is unbounded run lifetime, unbounded registry residency for the churned run, and the loss of the one control this phase built to stop budget being spent on output nobody reads. Whether the fix is a cumulative unwatched-time budget rather than a resettable timer, a cap on reconnects per run, or a decision that this is acceptable, is the closer's call, not the adversary's.

### F-4.0-A-02 and F-4.0-A-03 repro

One finished run, real server, real bearer token. The run emitted 10 events (`seq` 0 through 9); the caller is a non-operator, so the visible wire ids are `['0', '2', '4', '6', '7', '9']` and the four gaps are filtered `cost` events. Every row below is one real `GET /v1/query/{run_id}/events` with only the `Last-Event-ID` header varied, from `p04_inputs.py`:

```
=== Last-Event-ID shapes (internal max seq is 9) ===
  plain 0                  -> 200 ids=['2', '4', '6', '7', '9']
  leading zeros            -> 200 ids=['4', '6', '7', '9']
  plus sign                -> 200 ids=['4', '6', '7', '9']
  minus zero               -> 200 ids=['2', '4', '6', '7', '9']
  negative                 -> 200 ids=['0', '2', '4', '6', '7', '9']
  underscore int           -> 400 {"detail":"Last-Event-ID 10 exceeds this run's highest emitted seq (9); ..."}
  hex                      -> 200 ids=['0', '2', '4', '6', '7', '9']
  float                    -> 200 ids=['0', '2', '4', '6', '7', '9']
  inf                      -> 200 ids=['0', '2', '4', '6', '7', '9']
  nan                      -> 200 ids=['0', '2', '4', '6', '7', '9']
  empty                    -> 200 ids=['0', '2', '4', '6', '7', '9']
  32 char huge int         -> 400 {"detail":"Last-Event-ID 99999999999999999999999999999999 exceeds ..."}
  32 char negative         -> 200 ids=['0', '2', '4', '6', '7', '9']
  33 char                  -> 422 {"detail":[{"type":"string_too_long","loc":["header","Last-Event-ID"], ...}]}
  exact max seq            -> 200 ids=[]
  max seq + 1              -> 400 {"detail":"Last-Event-ID 10 exceeds this run's highest emitted seq (9); ..."}
  json injection           -> 200 ids=['0', '2', '4', '6', '7', '9']
```

Read the `hex`, `float`, `inf`, `nan`, `empty` and `json injection` rows against the `max seq + 1` row. Every one of the first six is a cursor this run cannot honor, and every one returns `200` plus a complete re-delivery of the run, six frames the resuming client already has. The last one is also a cursor the run cannot honor and returns `400`. Same class of input, two opposite dispositions, and the silent one is the one that produces duplicates. The phase premise's own words are "receives every event it missed (never a gap, never a duplicate)".

F-4.0-J-01's round-1 write-up in the table above named this exact behavior as the failure ("a reconnect with an empty `Last-Event-ID` re-delivers the entire run as duplicates, the exact failure the phase premise names as forbidden") and round 2 closed it by reclassifying the same observed behavior as "a deliberate full replay". Filed here as still-open on purpose rather than deferring to that closure, because the fix that closed F-4.0-J-01 added the missing `id:` line and did not change the fallback: `empty -> 200 ids=['0','2','4','6','7','9']` above is the round-1 repro, unchanged, run against `d8bec51`. Whether a deliberate full replay is the right disposition is the closer's call; what an adversary can say is that the endpoint currently cannot tell "I am a new client, send me everything" apart from "I am a resuming client whose cursor got mangled", and it answers both the same way.

F-4.0-A-03 is the `underscore int` row: `Last-Event-ID: 1_0` was parsed as the integer `10`, which is why that row rejects against a max seq of 9. `+3` and the leading-zero form were likewise accepted and honored as `3`. None of these are exploitable on their own, which is why this is minor, but the accepted grammar for the cursor is currently "whatever `int()` takes", not "the digits `seq` is defined as", and F-4.0-J-07 already capped the header's length without constraining its shape.

Reproduced twice: the second run of the identical script returned the identical status code and id list for all 17 sendable rows.

### Verified clean, recorded so the next reviewer does not re-run them

These were attacked and held. Recorded because a finding list with no negative results tells the reader nothing about coverage.

| Attacked | Result |
| --- | --- |
| Cross-user reads of another user's run | `GET /events`, `GET /citations` and `POST /stop` by a second real authenticated user all return `403 {"detail":"you do not own this run"}`. `_get_owned_run` is the first statement of all three handlers (`adapters/web_sse/app.py:185, 282, 335`) |
| Hostile `run_id` shapes | `'; DROP TABLE users;--`, `%00`, a 5000-char id, an RTL-override id, `*`, `null` and `0` all return `404 {"detail":"no such run"}`; `../../../../etc/passwd` and `..%2f..%2fhealth` return the router's own `404 {"detail":"Not Found"}`. No 500, no traceback, no path resolution |
| Auth edges | Missing header, `Bearer` with no token, `Basic` scheme, a garbage token, a token with its last three characters rewritten, and an `alg: none` shaped JWT all return `401 {"detail":"invalid or expired access token"}` with no distinguishing detail between them |
| `POST /v1/query` body validation | `text` at 2000 chars accepted, 2001 rejected `422`; `session_id` at 64 accepted, 65 rejected `422`; `text` as int, list or null rejected `422`; missing fields rejected `422`; a bogus `audience_depth` rejected `422`. `extra="forbid"` rejected `operator_mode`, a nested `context` object and a `user_id` spoof, each `422 extra_forbidden`, confirming there is no client-controllable operator surface on the create path |
| Malformed transport | Truncated JSON, form-encoded body, and `DELETE` on the events route return `422`, `422` and `405` respectively. No stack trace, no internal path, no other user's data in any error body. The server log stayed empty of tracebacks across every probe in this round |
| CORS | An `OPTIONS` preflight from `https://evil.example` returns `400` with no `access-control-allow-origin` header at all; the same preflight from `http://localhost:5173` returns `200` with `access-control-allow-origin: http://localhost:5173`. `_allowed_origins` (`adapters/web_sse/app.py:38-58`) does not default to `*` |

### F-4.0-A-04, F-4.0-A-05, F-4.0-A-06 and F-4.0-A-07 repro

One script, `p05_races.py`, real server, real bearer token, one real user. The query text carries a marker that makes the stubbed model sleep two seconds per call, so the run is genuinely in flight when it is stopped rather than racing a run that had already finished. Real output:

```
=== 2. STOP mid-flight: what terminal event does the stream carry? ===
   stop -> 200 {"stopped":true}
   citations IMMEDIATELY after stop -> 200 []
   pre-stop:  {'subscriber_count': 0, 'finished': False, 'events': 2, 'task_done': False, 'task_cancelled': False, ...}
   post-stop: {'subscriber_count': 0, 'finished': True,  'events': 2, 'task_done': True,  'task_cancelled': True,  ...}
   replay of a cancelled run -> 200 types=['guard']
   citations after cancel -> 200 []
```

Three separate findings sit in those six lines.

- F-4.0-A-04 is the `replay of a cancelled run -> 200 types=['guard']` line. The run emitted two events (`guard` and one filtered `cost`), was cancelled, and the stream a client reads back contains `guard` and then end-of-response. No `done`, no `error`, nothing that says the run was stopped. A client that reconnects after a dropped connection and a client reading a deliberately cancelled run see byte-identical shapes. Build phase 4.2's CLI is a thin client over exactly this surface and will have to guess.
- F-4.0-A-05 is the `citations after cancel -> 200 []` line. The run was killed two events in, so its citation set is not a set at all, it is whatever happened to exist at the moment of the kill. The response is `200 []`, exactly what a completed run that legitimately cited nothing returns.
- F-4.0-A-06 is the `409` string, seen in probe 4 of the same script against a brand-new run: `409 {"detail":"run has not finished; poll GET /v1/query/{run_id}/events or retry this request after the done event"}`. Follow that instruction on a run that is then stopped, or that abandonment cancels, and the `done` event it names never arrives.

The double-stop and stop-racing-a-read arm confirms the same shape under real concurrency, and confirms that the idempotency claim itself holds:

```
=== 3. concurrent double stop, and stop racing a read ===
   stopA: 200 {"stopped":true}
   stopB: 200 {"stopped":true}
   read:  200 ['guard']
   final: {'finished': True, 'task_done': True, 'task_cancelled': True, ...}
```

Two concurrent `POST /stop` calls both return `200 {"stopped":true}` with no error and no double-cancel fault, which is correct per the retry-safety gate. The concurrent read again terminates on `guard` with no terminal event, so F-4.0-A-04 is not an artifact of reading after the fact.

F-4.0-A-07 is visible in the final-state line of every completed run in the round, for example the twelve-reader arm's `final: {'subscriber_count': 0, 'finished': True, 'task_done': True, 'task_cancelled': False, 'abandonment_pending': True}`. The run is over and a check is still pending against it.

Reproduced twice: a second run of the identical script produced the same `types=['guard']` on the cancelled run, the same `200 []` citation export, and `abandonment_pending: True` on every finished run.

### More verified clean

| Attacked | Result |
| --- | --- |
| Caught-up resume on an IN-FLIGHT run | The case the premise gate does not cover (its F-4.0-J-03 arm uses a drained run). `Last-Event-ID: 1` against a live run whose highest emitted seq was 1 returned `200` and then continued live, delivering `ids=['2','4','6','7','9']`, `types=['think','plan','token','trust_signal','done']`, ending on `done`. It neither errored on the boundary nor hung waiting for an event it had already been given |
| Twelve concurrent readers of one in-flight run | All twelve returned `200`, six frames each, last frame `done`, with no interleaving loss, no starved reader and no duplicate. F-1.2-03's multi-consumer fix holds well past the two-reader case the premise gate pins (`{'200 n=6 last=done': 12}`) |
| Double `POST /stop` | Both concurrent calls return `200 {"stopped":true}`; `cancel_run`'s idempotency (`core/run_registry.py:336-337`) holds under a real race |
| `GET /citations` on a run with zero events yet | `409` with the actionable-message shape, not a `500` and not a fabricated empty list. The ordering in `adapters/web_sse/app.py:282-283` (ownership first, then terminal check) holds when `entry.events` is empty |

### F-4.0-A-08 and F-4.0-A-09 repro, and the operator boundary's clean result

`p06_operator.py`, real server, two real users, the allowlist written through the same `OPERATOR_USER_IDS` env var the shipped `_operator_user_ids()` reads fresh on every call. Baseline first, showing the boundary working exactly as T-4.0-05 claims:

```
operator sees : ['guard','cost','think','cost','plan','cost','token','trust_signal','cost','done']
                total_cost_usd = 0.00011999999999999999  ids = ['0','1','2','3','4','5','6','7','8','9']
non-op sees   : ['guard','think','plan','token','trust_signal','done']
                total_cost_usd = 0.0                     ids = ['0','2','4','6','7','9']
```

Seven attempts to buy visibility from the non-operator side, every one refused:

```
  query param (?operator_mode=true)  -> 200 cost_event=False total=0.0 LEAK=False
  query param (?operator&is_operator)-> 200 cost_event=False total=0.0 LEAK=False
  header X-Operator-Mode: true       -> 200 cost_event=False total=0.0 LEAK=False
  header operator_mode: true         -> 200 cost_event=False total=0.0 LEAK=False
  header X-User-Id: <operator uuid>  -> 200 cost_event=False total=0.0 LEAK=False
  header X-Forwarded-User: <op uuid> -> 200 cost_event=False total=0.0 LEAK=False
  GET with a JSON body carrying operator_mode and a nested context.operator_mode
                                     -> 200 cost_event=False total=0.0
```

Twenty concurrent mixed reads, ten by the operator across five of its own runs and ten by the non-operator across five of its own, interleaved on one event loop:

```
  operator reads : cost_seen = [True]*10   totals = [0.00011999999999999999]
  non-op reads   : cost_seen = [False]*10  totals = [0.0]
```

No cross-contamination in either direction, which independently confirms the judge's point that `_redact_done_event_for_end_user` copies rather than mutates: ten redacting readers running concurrently with ten non-redacting ones never zeroed the shared buffered `Event` objects the operator readers were also holding.

F-4.0-A-08 is the revocation arm. An operator's stream was opened against an in-flight run, and 0.5 seconds later the allowlist was rewritten to remove that user:

```
  allowlist revoked 0.5s into the stream -> ['guard','cost','think','cost','plan','cost','token','trust_signal','cost','done'] total = 0.00011999999999999999
  a NEW request after revocation         -> ['guard','think','plan','token','trust_signal','done']                            total = 0.0
```

The already-open stream kept full operator visibility through to `done`; the next request correctly had none. Whether per-request snapshot semantics is the intended contract is the closer's call, and it is defensible; what is filed is that nothing states it, and the allowlist's own implementation goes out of its way to be live-reloadable.

F-4.0-A-09 is readable directly off the non-operator's `ids = ['0','2','4','6','7','9']` in the baseline above.

Reproduced twice: identical results on a second run, including the same four gap positions and the same revocation behavior.

### F-4.0-A-10 and F-4.0-A-11 repro

`p07_exhaust.py`, one real account, bursts of `POST /v1/query` at concurrency 20, with an anchor run whose `GET /citations` latency is sampled 12 times after each burst. `runs` is read from the registry itself. Two consecutive sessions against the same live server:

```
runs=    14  GET /citations median=   1.53 ms  max=   4.30 ms
+  200 created ok=200 rejected={} in    0.7s | runs=   214 unfinished=0 | median=  1.50 ms max=  4.43 ms
+  200 created ok=200 rejected={} in    0.7s | runs=   414 unfinished=0 | median=  1.59 ms max=  3.72 ms
+  400 created ok=400 rejected={} in    2.3s | runs=   814 unfinished=0 | median=  1.59 ms max=  3.78 ms
+  800 created ok=800 rejected={} in    4.0s | runs=  1614 unfinished=0 | median=  3.30 ms max=  6.00 ms
+ 1600 created ok=1600 rejected={} in   7.4s | runs=  3215 unfinished=0 | median=  2.00 ms max=  4.75 ms
+ 3200 created ok=3200 rejected={} in  18.5s | runs=  6415 unfinished=0 | median=  2.89 ms max=  5.54 ms
+ 3200 created ok=3200 rejected={} in  22.9s | runs=  9615 unfinished=0 | median=  4.18 ms max= 15.51 ms
```

`rejected={}` on every row: 9,615 of 9,615 creates accepted. Server process RSS went from 62.0 MB at 1,614 retained runs to 365.9 MB at 9,615, roughly 38 KB per retained run, which is consistent with each entry holding the same events twice (the `events` list plus the retained `queue`, the deliberate coexistence F-4.0-J-05 documents). At the shipped 300-second retention window, steady state is 300 times whatever create rate a caller can sustain, and nothing in this phase's surface bounds that rate.

The daily-cap arm, run against a separate server instance started with the real `check_user_daily_query_cap` left in place (not stubbed out) and `PER_USER_DAILY_QUERY_CAP=2`:

```
PER_USER_DAILY_QUERY_CAP is set to 2 on the server for this probe
POST /v1/query status codes for 10 sequential creates: [202, 202, 202, 202, 202, 202, 202, 202, 202, 202]
registry entries created for this user: 10 of 10 attempts
```

This is the part worth reading twice. The cost control that exists to bound a user's daily query volume cannot bound registry residency, because `create_run` runs at the adapter and the cap runs inside `run_streaming`. A capped user still mints a registry entry and a background task per request. Stated as a code-path fact rather than an inference: `core/graph.py:731` is where `check_user_daily_query_cap` is called, and `adapters/web_sse/app.py:151` has already returned from `default_registry.create_run(...)` by then.

Reproduced twice: the burst table above is itself two independent sessions against the same server (rows 1 to 4, then rows 5 to 7 after a restart of the driver), and the daily-cap arm was re-run with a second fresh account, again 10 of 10 `202` and 10 of 10 entries.

Scope note, stated rather than assumed: `tracker/phase_4.0.md`'s own coverage-exclusion paragraph defers "load-scale behavior under many concurrent runs" to build phase 6.0, and rate limiting is explicitly that phase's job. F-4.0-A-10 and F-4.0-A-11 are filed anyway, for two reasons the closer should weigh rather than take as settled. First, F-1.2-01 is one of the three findings THIS phase claims to close, and its original repro was exactly a create burst; a fix that bounds the window but not the burst closes half of it. Second, F-4.0-A-11 is not a load-balancing concern at all, it is the algorithmic cost of the eviction design this phase introduced, and it is chosen here, not inherited.

### F-4.0-A-14 repro

`p11_slowloris.py`. Raw `asyncio` sockets rather than an HTTP client library, so the client side is fully controlled: the probe writes the request, reads exactly the response headers with `readuntil(b"\r\n\r\n")`, and then never reads again. Grace window 30.0 seconds, the shipped default, unscaled. Real output:

```
=== a run held by 5 attached-but-never-reading connections ===
   with 5 silent subscribers: {'subscriber_count': 5, 'finished': False, 'events':  0, 'abandonment_pending': False, ...}
   t=+ 5s (grace is 30s):    {'subscriber_count': 5, 'finished': False, 'events':  6, 'abandonment_pending': False, ...}
   t=+10s (grace is 30s):    {'subscriber_count': 5, 'finished': False, 'events':  6, 'abandonment_pending': False, ...}

   closing all 5 connections
   after close:              {'subscriber_count': 0, 'finished': True,  'events': 10, 'abandonment_pending': True, ...}
```

`abandonment_pending: False` at every sampled instant while the five sockets are attached: no check is even scheduled, because `_reschedule_abandonment_check`'s `subscriber_count == 0` guard never holds. Not one byte of event data was read by any of the five connections, and the run advanced from 0 to 6 to 10 events throughout. Closing the sockets restores the correct behavior immediately (`subscriber_count` back to 0, a check scheduled again), which is what makes the mechanism unambiguous: the count tracks attachment, and nothing tracks delivery.

Reproduced twice: identical `subscriber_count: 5` and `abandonment_pending: False` across the full window on a second run.

The second arm of the same probe attacked the adjacent hypothesis, that a silent subscriber could pin a finished run past its retention window, and it did not hold:

```
   registry entry 6s after finish (retention=2s): {'finished': True, 'task_done': True, ...}
   GET /citations -> 404 {"detail":"no such run"}
   registry entry after a sweep-triggering call: None
```

An attached subscriber does not block eviction. The entry survived only until the next caller-facing call ran the sweep, and the stale read was a `404`, never stale data, which is F-1.2-01's stated property holding under a case the premise gate does not cover.

### Final verified clean

| Attacked | Result |
| --- | --- |
| Eviction racing concurrent readers | Retention set to 2 seconds, ten reads of one finished run fired across the boundary at t=0.5s through t=5.0s. Both endpoints returned `200` with the complete 6-frame stream and the full citation export before the boundary, and `404 {"detail":"no such run"}` after it, on both endpoints, at every sample. No torn read, no partial citation list, no 500, no window where one endpoint said `200` and the other `404` |
| Odd call orderings on one run | `stop`, `events`, `citations`, `stop`, `citations`, `events`, `stop` in sequence on a single run: `200, 200, 200, 200, 200, 200, 200`, no 500, no exception, no state corruption. (The `citations -> 200 []` responses in that sequence are F-4.0-A-05, not a separate defect) |
| Same `session_id` across two different users | Both creates return `202`, each user reads only its own run, and a cross-read of the other user's run returns `404` once the run has been evicted or `403` while it is live. No session-keyed collision in the registry, which is keyed by `run_id` alone |
| Unusual but schema-passing `POST /v1/query` bodies | 500 characters of RTL override, `{{7*7}} ${jndi:ldap://x} <script>alert(1)</script>`, a path-shaped `session_id`, a blank `session_id`, 400 emoji, embedded `\n`/`\r`/`\t`, and a NUL byte inside `session_id` all returned `202` and ran without incident. Worth noting rather than filing: `text` and `session_id` are length-capped but not character-class-constrained, so control characters and bidirectional-override characters reach the model prompt and will reach the interactions table when build phase 4.6 adds one. No injection, no crash, no reflected markup in any response body (every response is JSON through a Pydantic model) |
| Server-side exceptions across the entire round | `grep -c Traceback` over the server log after every probe in this round: `0`. Nothing in this phase's surface produced a 500, an unhandled exception, or a stack trace in a response body |

### Adversary round 1 summary

14 findings filed, all `open`, none triaged or closed here: 4 major (F-4.0-A-01, A-04, A-05, A-10), 5 moderate (A-02, A-06, A-11, A-12, A-14), 5 minor (A-03, A-07, A-08, A-09, A-13).

Three root causes account for nine of the fourteen, which matters more than the count:

- "Watched" is defined as connected, never as delivered. `subscriber_count` (`core/run_registry.py:366-369`) counts attached iterators, and the abandonment timer is re-armed from zero on every change (`core/run_registry.py:253-263`). F-4.0-A-01 (churn resets it forever) and F-4.0-A-14 (one idle socket suppresses it entirely) are two doors into the same room, and both defeat the property F-1.2-02 exists to guarantee.
- A cancelled run is treated as a completed run everywhere downstream. `_drain_into_entry`'s `finally` (`core/run_registry.py:216-221`) sets exactly the same `finished`/`finished_at` state for a kill as for a clean finish, and nothing above it distinguishes the two. F-4.0-A-04 (no terminal event on the stream), F-4.0-A-05 (a silently incomplete citation export) and F-4.0-A-06 (a `409` naming a `done` event that will never arrive) all fall out of that one conflation.
- Admission is unbounded and the fix for unbounded retention made every request pay for it. F-4.0-A-10 and F-4.0-A-11.

The operator-mode boundary (T-4.0-05) is the strongest part of this phase and was not broken by anything tried: seven request-shaped attacks, a JSON body on a GET, and 20 concurrent mixed reads all failed to leak a `cost` event or a non-zero `total_cost_usd` to a non-allowlisted caller, and the two findings against it (A-08, A-09) are both about what the design does not say rather than what it does wrong. Ownership isolation (`_get_owned_run`) was likewise not broken by any run_id shape, header trick or race tried.

Scope check, per the adversary's own brief: nothing found here implicates the cite-or-refuse or trust-signal path, and no finding required or suggested a change outside `adapters/web_sse/app.py` and `core/run_registry.py`, so `.claude/rules/v1-scope-boundary.md` is not crossed and no earlier phase's deliverable is reopened. One nuance the closer should not miss, though, because it sits right on that line: F-4.0-A-12 is an adapter-layer defect that silently degrades an honesty guarantee an earlier phase built. `core/graph.py` correctly computes and emits a truncation disclosure (F-2.1-C12's fix), and `GET /citations` correctly refuses to invent anything, but it filters that disclosure out on the way to the caller. The trust machinery is intact; the surface this phase finalizes as the one canonical public API drops part of its output. That is this phase's defect to fix, not build phase 2.1's to reopen.

Harness note for whoever verifies these: every probe drove the real app over real HTTP with real PostgreSQL auth and real bearer tokens. Nothing under `src/` was modified. The two registry lifecycle windows were varied through `RunRegistry`'s own constructor parameters (`abandon_grace_seconds`, `retention_seconds`), and F-4.0-A-14 was run at the shipped 30.0-second grace default with no scaling at all. Findings A-01 and A-14 should be re-verified at the shipped defaults before any fix is graded, since a fix that only moves a constant would pass a scaled test and fail a real one.

### Reproduction discipline

Every "reproduced twice" claim above was earned by actually re-running the probe a second time in this session, against a freshly restarted server and a freshly signed-up account, not by asserting it. The second pass covered: the churn and control arms (F-4.0-A-01), the `Last-Event-ID` shape table (F-4.0-A-02, A-03), the stop and race arms (F-4.0-A-04, A-05, A-06, A-07), the full operator boundary including the revocation arm (F-4.0-A-08, A-09), the daily-cap arm with a second account (F-4.0-A-10), and the five-silent-subscribers arm at the shipped 30.0-second grace default with no scaling (F-4.0-A-14). Every second pass matched the first on status codes, id lists, event-type lists and registry state.

This paragraph exists because the first draft of this section asserted "reproduced twice" before the second runs had happened, which is the same shape of unverifiable claim F-4.0-J-02 was filed against one section earlier in this very file. Caught and corrected before the section was handed off rather than after.

## Fix round, adversary findings

10 of 14 findings closed this round (8 code fixes, 2 resolved by disclosure/documentation rather than a behavior change); 4 carried open with a named reason each. The lead made these dispositions directly rather than escalating, since each had a clear, boundable answer; re-verification is still the judge's job, not self-graded here, per `.claude/rules/self-eval-loop.md`.

### Fixed

- F-4.0-A-01 (major): `RunEntry` gained `cumulative_unwatched_seconds` and `unwatched_since`. `_reschedule_abandonment_check` (`core/run_registry.py`) now folds real elapsed time into the running total on every attach and schedules only the REMAINING budget on every detach, instead of a brand-new full-length timer each time. A churn cadence shorter than the grace window can no longer hold a run alive forever; every unwatched interval still counts toward cancellation, even a short one between two brief attaches. Pinned by `TestAbandonment::test_rapid_churn_does_not_hold_a_run_alive_past_cumulative_grace_time`.
- F-4.0-A-02 and F-4.0-A-03 (moderate, minor): `GET /events` now requires a PRESENT `Last-Event-ID` to match the strict digit grammar `Event.seq` actually is (`_SEQ_CURSOR_PATTERN`, `adapters/web_sse/app.py`). A malformed present value (`1_0`, `+3`, `-1`, hex, float, `inf`, `nan`, empty) is rejected `400`, the same disposition an out-of-range one already got, never silently reinterpreted as "start over". A genuinely ABSENT header is unchanged: still a real full replay. Pinned by `TestResumability::test_a_malformed_last_event_id_is_rejected_not_silently_full_replayed`.
- F-4.0-A-04 (major): `_drain_into_entry` (`core/run_registry.py`) now catches `asyncio.CancelledError` explicitly, sets a new `RunEntry.cancelled` flag, appends a synthetic fatal `error` event (`error_class="cancelled"`, an additive enum value on `contracts/events.py`'s `ErrorPayload`, kept in sync with the frontend's own hand-maintained copy at `frontend/src/lib/events.ts`, the same class of gap Step 6.2's F-3.0-01 fixed once already) to both read paths, then re-raises so cancellation still propagates normally. `subscribe`'s existing fatal-error termination check needed no change. Pinned by `TestCancellationTerminalState::test_a_stopped_run_emits_a_real_terminal_event_not_silence`.
- F-4.0-A-05 (major): `GET /citations` sets `X-Run-Cancelled: true` when `entry.cancelled`, disclosing a partial export as metadata rather than changing the response body's wire shape (still a bare JSON array, Section 13.1). Pinned by `TestCancellationTerminalState::test_citations_export_discloses_cancellation_via_response_header`.
- F-4.0-A-06 (moderate): the `409` message no longer names "the done event" specifically, since a stopped or abandonment-cancelled run does not emit one; reworded to name the real, complete set of terminal shapes. Existing test `test_409s_with_an_actionable_message_for_a_run_still_in_flight` updated to match.
- F-4.0-A-07 (minor): `_drain_into_entry`'s `finally` block now cancels any pending `abandonment_check` the instant a run actually ends (`core/run_registry.py`), rather than leaving it to sleep out its own grace window against a run that is already over. Covered incidentally by every existing completion-path test; no dedicated arm added since the property (no dangling task after finish) is implicit in the existing eviction and completion assertions.
- F-4.0-A-13 (minor): the local `_MAX_CITATIONS_PER_RUN` break now sets `X-Citations-Export-Truncated: true` when the count of real `citation` events in `entry.events` exceeds the cap, so the currently-unreachable path degrades to a disclosed header rather than a silent, unenforced-margin truncation if a future phase raises `_MAX_CITATIONS_PER_ANSWER` past 50.

### Resolved by disclosure, not a behavior change

- F-4.0-A-08 (minor): per-connection operator-visibility snapshotting is an intentional design decision (re-checking the allowlist per-event would cost a live env read on every yielded event for a revocation scenario expected to be rare), now stated explicitly in a comment at the `is_operator` computation (`adapters/web_sse/app.py`) rather than left for a reader to infer or mistake for an oversight.
- F-4.0-A-09 (minor): the wire `id:` gap disclosure to a non-operator caller is the accepted cost of F-4.0-J-01's deliberate choice to use the envelope `seq` rather than a per-connection counter (a real correctness requirement, not an oversight); now stated as a named tradeoff in a comment at the `subscribe` call site.

### Carried open, adversary findings

- F-4.0-A-10, F-4.0-A-11 (major, moderate): unbounded run creation and the O(n) eviction sweep's cost under it. `tracker/phase_4.0.md`'s own coverage-exclusion paragraph already defers "load-scale behavior under many concurrent runs" to build phase 6.0 ("per-layer throttling, the concurrency queue strategy, the at-most-20-calls-per-query budget", Section 25), and admission control is squarely a rate-limiting concern. Correction, judge round 3: the original version of this paragraph cited `.claude/rules/v1-scope-boundary.md` for this carry, which is imprecise. That rule governs capabilities named on the PRD out-of-scope list or the technical specification's fast-follow table, and rate limiting is on neither; it is build phase 6.0 in the locked Section 25 build order, which the rule explicitly permits building toward. The real basis is phase sequencing and round hygiene, not a scope-boundary crossing: the exclusion was pre-registered in this file's coverage paragraph at phase open, build phase 6.0 owns rate limiting by name, and no deploy exists yet to make the exhaustion path reachable by anyone but the product owner. F-1.2-01's own fix (bounding RETENTION time) is unaffected and remains closed; F-4.0-A-10 shows the same underlying resource-exhaustion shape survives via unbounded CREATION rate instead, a related but genuinely distinct control for build phase 6.0 to own. Both findings are now also tracked in `tracker/BOARD.md`'s Open flags table so they carry forward with a named owner rather than depending on this file being re-read.
- F-4.0-A-12 (moderate): the correct fix threads a new additive `DonePayload` field through `core/graph.py`'s `write_node`, which has multiple exit branches and its own existing test coverage; doing this correctly needs its own focused, separately tested change, not a rushed addition at the tail of an already-large fix round. A one-line pointer comment was added at the citations endpoint's read loop so a future reader is not surprised by the gap.
- F-4.0-A-14 (moderate): closing this needs delivery-based liveness tracking (each subscriber proving forward progress, e.g. a per-subscriber idle-read timeout), a materially bigger design change than the timer-accounting fix F-4.0-A-01 made to the exact same concurrency-sensitive method this round. Rushing a second redesign of `_reschedule_abandonment_check` in the same round that just changed it risks a worse regression than shipping with this gap named and open. Documented in `core/run_registry.py`'s own module docstring as a known open gap, not left implicit.

### Verification, this round

```text
$ python3 -m pytest tests/system_03_search_agent/adapters/web_sse/test_phase_4_0_premise.py -v
25 passed in 6.02s
$ python3 -m pytest tests/system_03_search_agent/adapters/web_sse/ tests/system_03_search_agent/core/test_run_registry.py tests/system_03_search_agent/auth/test_router.py tests/system_03_search_agent/contracts/ tests/system_03_search_agent/core/test_graph.py -q
419 passed in 14.88s
$ python3 -m pytest tests/ -q
6 failed, 2396 passed, 113 skipped, 1 xfailed, 1 warning in 54.00s
```

The 6 full-suite failures are the same pre-existing, live-network-opt-in-gated cases from both judge rounds, unchanged in identity (`test_citation_trust_full_premise.py`, `LiveHttpCallInUnitSuiteError`), not a regression. Frontend suite: `Test Files 15 passed (15)`, `Tests 120 passed (120)`, confirming the `events.ts` type-guard widening (required for F-4.0-A-04's new `error_class="cancelled"` value to not be silently rejected client-side, the same hand-maintained-copy gap Step 6.2's F-3.0-01 fix found once already) introduced no regression. `ruff check` clean on every file this round touched.

Judge round 3 (confirmation of this fix round) is next.
