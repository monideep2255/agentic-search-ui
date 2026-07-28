# Phase 2.0: LangGraph agent loop

Branch: `phase/2.0-langgraph-agent-loop`
Depends on: 1.0 (done, merged as PR #5)
Delivers (Technical_specification.md Section 25, line 3181): the LangGraph graph implementing Guardrail, Think, Plan, Act, Write with stub nodes; the three-tier harness wired to LiteLLM and OpenRouter (Decision C); the coordinator-worker split scaffold; cost caps and the cost event enforced from day one.

Dependency check at open: Section 25's dependency graph gives 2.0 a single incoming edge from 1.0, which is `done` on `tracker/BOARD.md` and merged into `main`. This phase can start.

Rules that bind this phase specifically: `prompt-cache-discipline.md` (the stable prefix `harness/call_tier` depends on) and `system-design-patterns.md` pattern 11 (`resolve_model()` never hardcodes a model id). Both are read before any harness code is written, per the phase 6 continuation prompt.

Scope decisions made at open, recorded here rather than left implicit in code:

- `env.example`'s `PER_USER_DAILY_CAP_USD` is misnamed. Section 19.1 defines this cap as a query count (100 queries/day), not a dollar figure. T-2.0-03 renames it to `PER_USER_DAILY_QUERY_CAP` and updates the surrounding comment. Logged to `DECISIONS.md`.
- Section 19.1's per-step timeout table names four query classes (lookup, single-hop, multi-hop, deep research). `ThinkPayload.query_class` (contracts/events.py) already ships five (`lookup`, `single_hop`, `multi_hop`, `aggregate`, `exploratory`) from phase 1.0, and neither Section 19.1 nor Section 2.3 states the mapping between the two lists. T-2.0-04 fixes the mapping as `lookup` to 5s, `single_hop` to 10s, `aggregate` and `multi_hop` both to 30s, `exploratory` to the 2-minute deep-research budget. Logged to `DECISIONS.md`.

LEARNINGS.md filtered to this phase: no entry is tool-specific to LangGraph or the harness yet, since this is the first phase to touch either. Four general-process entries still bind: use the Edit tool for board and doc files, never `sed` or a heredoc, since PostToolUse hooks fire only on Edit and Write; re-verify any worktree-isolated builder's test run in the target checkout, a worktree's green suite proves nothing about the checkout it merges into; a documented "defer to a later ticket" reasoning must be re-checked against what actually ships in the SAME phase, not taken on the deferring ticket's own word; and an acceptance criterion for a stated security or cost property must be worded as the property itself, not as the mechanism meant to produce it (this phase's cap-enforcement criteria below are written as the trigger behavior Section 19.1 states, not just as "a check exists").

## Tickets

### T-2.0-01: Tier resolution (`resolve_model`)

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: none
Spec: Technical_specification.md Section 3.1 (lines 419-427), Section 3.3 (450-465); `system-design-patterns.md` pattern 11; `prompt-cache-discipline.md` obligation 1

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/__init__.py`
- `src/system_03_search_agent/harness/tiers.py`
- `tests/system_03_search_agent/harness/__init__.py`
- `tests/system_03_search_agent/harness/test_tiers.py`

Acceptance criteria:
- [ ] `resolve_model("guard" | "plan" | "synth")` returns the value of `GUARD_MODEL` / `PLAN_MODEL` / `SYNTH_MODEL` from the environment when set, and falls back to an app-config default per tier when the env var is unset or empty
- [ ] No model id string is hardcoded outside the one app-config default table; a repo-wide grep for a literal OpenRouter-shaped model id (a string containing a provider-prefixed `/`) finds it only in that table, never inline in harness, node, or graph code
- [ ] A tier's resolved model is fetched once at query start and held for the query's duration: two resolutions of the same tier within one query context return the identical value even when a test mutates the underlying env var mid-query
- [ ] Passing a tier value outside `{"guard", "plan", "synth"}` raises a typed error before any network or model call is attempted

Breakdown:
- [ ] `resolve_model()` reading env vars with app-config fallback
- [ ] Query-scoped tier cache (resolve-once-per-query)
- [ ] Tests: env-set, env-unset-fallback, mid-query-mutation-ignored, invalid-tier

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 25 row 2.0 and Section 3.1/3.3

### T-2.0-02: LiteLLM/OpenRouter `call_tier` with cost accounting

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-01
Spec: Technical_specification.md Section 3.3 (450-465), Section 3.5 (508-540), Section 19.2 (2813-2819)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/harness.py`
- `tests/system_03_search_agent/harness/test_harness.py`

Acceptance criteria:
- [ ] Every call to `Harness.call_tier` issues its request through LiteLLM targeting `openrouter/<model_id>`, where `<model_id>` is `resolve_model(tier)`'s return value, never a direct provider SDK call
- [ ] `call_tier` returns token usage (`prompt_tokens`, `completion_tokens`) alongside the completion and computes `call_cost_usd` as `prompt_tokens * input_price + completion_tokens * output_price`, using the OpenRouter price for the exact model that answered
- [ ] A retried `call_tier` invocation (production-standards retry-safety gate) is metered as an independent billable event: its own `call_cost_usd` is computed and does not overwrite or absorb the first attempt's recorded cost
- [ ] A `call_tier` invocation that hits an unresolvable tier or a LiteLLM/OpenRouter transport failure raises a classified error (transient, recoverable, or unexpected per Section 3.5) rather than silently returning a default or empty completion
- [ ] Tests cover a mocked successful call asserting cost computation, a mocked transient failure with one retry counted as its own billable event, and an invalid-tier input

Breakdown:
- [ ] `Harness.call_tier` wrapping LiteLLM's `openrouter/*` call shape
- [ ] Token-usage to `call_cost_usd` computation against OpenRouter's per-model pricing
- [ ] Transient/recoverable/unexpected error classification on call failure
- [ ] Tests: success-path cost math, retried-call independent metering, invalid tier

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 3.3/3.5/19.2

### T-2.0-03: Cost caps enforcement and the cost event

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 19.1 (2800-2811), 19.2 (2813-2819), 19.3 (2821-2825), 19.4 (2827-2831), 19.5 (2833-2840)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/cost_control.py`
- `tests/system_03_search_agent/harness/test_cost_control.py`
- `env.example` (rename `PER_USER_DAILY_CAP_USD` to `PER_USER_DAILY_QUERY_CAP`, per the scope decision above)

Acceptance criteria:
- [ ] A cap check runs before a model call fires: the harness estimates the next call's cost from the tier's typical token profile and refuses to dispatch a call that would push `query_cost_usd` past the per-query cap ($0.10 starter value, `PER_QUERY_COST_CAP_USD`), rather than dispatching first and discovering the overage afterward
- [ ] When the per-query cap is hit, the loop stops making further model calls and moves directly to Write with whatever tool results already exist, shipping a partial cited result, never a blank failure
- [ ] A user who has reached `PER_USER_DAILY_QUERY_CAP` (100) queries in the current daily boundary has a new query declined before Guardrail runs, with the decline message stating the query count and a reset time, never a dollar figure
- [ ] Once `system_daily_cost_usd` reaches `SYSTEM_DAILY_CAP_USD`, a new query from any user is declined with a plain "paused for the day to stay within operating budget" message, no dollar figure, no technical cause named
- [ ] `query_cost_usd`, `user_daily_query_count`, and `system_daily_cost_usd` are three independently tracked running counters; `system_daily_cost_usd` and `user_daily_query_count` are read back from the `interactions` table (Section 15) at process start rather than reset to zero on restart
- [ ] A `cost` event fires after every metered model call, using `CostPayload` already defined in `contracts/events.py` (`query_cost_usd`, `query_cap_usd`, `cap_fraction`, `model_tier`), and `query_cost_usd`/`cap_fraction` are running totals, not deltas
- [ ] The web_sse adapter's `/query` response never includes a `cost`-type event in what reaches the client, even though the harness's internal state tracks it
- [ ] No dollar figure or currency symbol appears in any string reachable from a per-query-cap, per-user-cap, or system-wide-cap decline path

Breakdown:
- [ ] Pre-flight cost estimate and per-query cap enforcement
- [ ] Per-user daily query count enforcement, persisted and restart-safe
- [ ] System-wide daily dollar cap enforcement, persisted and restart-safe
- [ ] Cost event emission wired to `CostPayload`
- [ ] Adapter-boundary filter dropping `cost` events from the end-user stream
- [ ] `env.example` rename and comment fix
- [ ] Tests: pre-flight refusal, partial-result-on-cap, per-user decline message, system-wide decline message, restart-safe counters, adapter filter, no-dollar-figure-in-user-text

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 19.1-19.5; carries the `PER_USER_DAILY_CAP_USD` rename decision

### T-2.0-04: Per-step timeout enforcement

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 19.1 (2800-2811, the per-step timeout row), Section 3.5 (508-540, `enforce_timeout`)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/harness.py` (extends T-2.0-02's `enforce_timeout` method)
- `tests/system_03_search_agent/harness/test_harness.py` (extends T-2.0-02's file)

Acceptance criteria:
- [ ] `enforce_timeout(step, coro, budget_s)` aborts and returns a timeout signal if `coro` has not completed within `budget_s`, without leaving the underlying task running unbounded in the background
- [ ] `budget_s` for a given query resolves from Think's emitted `query_class` using the fixed mapping recorded in this phase's scope decisions: `lookup` to 5s, `single_hop` to 10s, `aggregate` and `multi_hop` both to 30s, `exploratory` to 120s
- [ ] On a per-step timeout, the loop does not hang or crash: it proceeds to synthesize from whatever partial tool results already exist, per Section 19.1's trigger behavior for this cap
- [ ] A step that completes just under `budget_s` is not falsely aborted: a test with a fast-completing coroutine asserts the real result is returned, not a timeout
- [ ] A step that exceeds `budget_s` produces a classified `error` event (`scope="step"`, an `error_class` per Section 3.5's transient/recoverable/unexpected taxonomy) distinguishable from a step that failed for a non-timeout reason

Breakdown:
- [ ] `enforce_timeout` wrapping any step coroutine with a hard deadline and clean cancellation
- [ ] `query_class` to `budget_s` mapping table
- [ ] Timeout-triggered partial-synthesis handoff
- [ ] Tests: real abort under budget, false-positive-abort check, error event shape on timeout

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 19.1/3.5; carries the query_class-to-budget mapping decision

### T-2.0-05: Coordinator-worker split scaffold

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 3.4 (467-506)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/coordinator_worker.py`
- `tests/system_03_search_agent/harness/test_coordinator_worker.py`

Acceptance criteria:
- [ ] `coordinator_worker_execute(tool_calls)` runs independent tool calls concurrently via `asyncio.gather`, not sequentially: a test with two artificially delayed fake tool calls asserts total wall-clock time is close to the slower call alone, not the sum of both
- [ ] A tool result flagged as containing untrusted free text is routed through an isolated reader call before Write ever sees it; a tool result carrying only structured fields passes straight through with no reader call
- [ ] The reader call is constructed with access to Read plus only the one API/tool that produced the payload; it is never given Write access or the ability to invoke a different tool
- [ ] The function's return value for a free-text-routed result is the reader's structured findings only (extracted entities, normalized ids, a short evidence summary), never the original free-text payload; the return value for a structured result is the pass-through structured fields
- [ ] Tests use fake/fixture tool calls, since no real tool exists yet (`cypher_query` lands in phase 2.1), and assert the free-text/structured branching by inspecting the returned `Finding` shape

Breakdown:
- [ ] `Finding` type (internal, harness-owned, not part of the wire-level Event taxonomy)
- [ ] `coordinator_worker_execute` with `asyncio.gather` fan-out
- [ ] Isolated reader-pass call, scoped to Read plus the originating tool only
- [ ] Structured-vs-free-text branching
- [ ] Tests: concurrency timing, free-text routing, structured pass-through, reader scope

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 3.4

### T-2.0-06: Prompt-cache stable-prefix scaffold

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 4.2 (569-590), Section 4.5 (624-626); `prompt-cache-discipline.md`

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/cache.py`
- `tests/system_03_search_agent/harness/test_cache.py`

Acceptance criteria:
- [ ] `build_stable_prefix()` assembles the prefix in the fixed order: system instructions and behavioral directives, then the tool-schema slot (an empty, alphabetically-sortable list is acceptable now since no tool exists yet; the slot's position never shifts when tool schemas are added starting phase 2.1), then the static graph/BioLink concept-level schema (10 labels, 14 predicates)
- [ ] Two calls to `build_stable_prefix()` invoked with different dynamic-suffix inputs (the suffix is passed and used separately, never merged into the prefix) produce byte-identical prefix output, verified by a SHA-256 equality assertion in a test
- [ ] No timestamp, request id, `trace_id`, or session id appears anywhere in the assembled prefix: a test constructs two calls with different simulated trace ids and asserts the prefix hash is unchanged
- [ ] The tool-schema slot's sort order is fixed in code (alphabetic by tool name) and is never re-derived at runtime from a source that could reorder between calls
- [ ] `Harness.call_tier` (T-2.0-02) accepts a `cache_prefix` parameter built by this module, matching the Harness class signature in Section 3.5

Breakdown:
- [ ] `build_stable_prefix()` with the three fixed slots
- [ ] SHA-256 byte-equality helper for prefix verification
- [ ] `call_tier` wiring to accept and forward `cache_prefix`
- [ ] Tests: assembly order, byte-equality across differing suffixes, no-volatile-token check

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 4.2/4.5 and prompt-cache-discipline.md

### T-2.0-07: LangGraph five-node loop, stub nodes

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-01, T-2.0-02, T-2.0-03, T-2.0-04, T-2.0-05, T-2.0-06
Spec: Technical_specification.md Section 3.2 (429-448), Section 25 row 2.0 (line 3181); CLAUDE.md's agent-loop pattern

Files this ticket may create or modify:
- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/core/state.py`
- `src/system_03_search_agent/core/run.py`
- `tests/system_03_search_agent/core/test_graph.py`
- `tests/system_03_search_agent/core/test_run.py` (extends the existing phase 1.0 test)

Acceptance criteria:
- [ ] `run(query, context)` is backed by a real LangGraph `StateGraph` with five nodes named `guardrail`, `think`, `plan`, `act`, `write`, compiled and invoked in that fixed sequence for every query
- [ ] The `guardrail` and `think` nodes call `Harness.call_tier` with `tier="guard"`; the `plan` node calls with `tier="plan"`; the `write` node calls with `tier="synth"`, matching Section 3.2's step-to-tier table exactly
- [ ] Every node's model call passes through `enforce_timeout` with the budget resolved per T-2.0-04's mapping, and every node's cost is tracked through T-2.0-03's cost control before the node returns
- [ ] The graph still emits only Section 2.3 typed `Event` instances end to end: the existing guard-then-done round trip from the phase 1.0 test suite still passes unmodified, and the suite is extended to assert intermediate `think`, `plan`, and `cost` events also validate against their Section 2.3 payload models
- [ ] Each stub node produces a schema-valid payload without performing real classification, tool selection, or synthesis logic; no stub node fabricates a citation or a `trust_signal` outcome that a later phase has not yet earned (real Act tool logic lands in phase 2.1+, guardrail's real validation in phase 3.0, write's real grounding in phase 2.2)
- [ ] The per-query cap's trigger behavior (T-2.0-03) is reachable through the real graph: a test that forces the cap to be hit mid-loop asserts the graph moves to `write` early with partial results rather than continuing to `act`

Breakdown:
- [ ] `core/state.py` graph state type
- [ ] `core/graph.py` StateGraph definition and compilation, five stub nodes
- [ ] `core/run.py` rewritten to build and invoke the compiled graph instead of the phase 1.0 linear scaffold
- [ ] Tests: node sequence, per-node tier assignment, event schema validation on every emitted type, stub-node non-fabrication check, cap-triggered early exit to write

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 3.2/25; integrates T-2.0-01 through T-2.0-06

### T-2.0-08: Server-derive `user_id` on `/query`

Status: todo
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: none
Spec: F-1.1-17 (`tracker/phase_1.1.md`, lines 671-689); `requirements/phase_6/Continuation_prompt.md` line 98 ("Phase 2.0 owns server-deriving that value")

Files this ticket may create or modify:
- `src/system_03_search_agent/adapters/web_sse/app.py`
- `src/system_03_search_agent/contracts/query.py`
- `tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py`

Acceptance criteria:
- [ ] `POST /query` requires a valid Bearer access token via the existing `get_current_user` dependency; a request with no token or an invalid or expired token is rejected with 401 before `run()` is ever called
- [ ] The `user_id` passed into `run()`'s `Query` is always the server-derived value from the verified token's subject claim, never a client-supplied value
- [ ] A test posts a request carrying an attacker-chosen `user_id` in the body and asserts the value actually used downstream is the token's subject, not the body's, whether `Query.user_id` is removed from the client-facing contract or silently overwritten before `run()` is called
- [ ] The existing phase 1.0 test asserting `/query`'s typed-event round trip is updated to authenticate first, and continues to pass

Breakdown:
- [ ] `get_current_user` wired as a dependency on `POST /query`
- [ ] Server-side override or removal of client-supplied `user_id`
- [ ] Tests: no-token-401, attacker-chosen-user_id-ignored, existing round trip updated and passing

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, closing F-1.1-17 per the continuation prompt's explicit assignment to this phase

## Findings

Carried forward from phase 1.1, not newly filed in this phase:

### F-1.1-17: `/query` is unauthenticated and trusts a client-supplied `user_id`

Severity: low. Status: rejected as a phase 1.1 defect (correct behavior for phase 1.0's shipped scope), converted to this phase's T-2.0-08. See `tracker/phase_1.1.md` lines 671-689 for the full judge ruling.

No new findings filed yet. This section fills in as building and adversarial review happen during the phase.

## History

- 2026-07-28 lead: phase opened, dependency verified against Section 25 and `tracker/BOARD.md`, LEARNINGS.md read filtered to this phase, decomposed into 8 tickets (T-2.0-01 through T-2.0-08), all refined at creation
