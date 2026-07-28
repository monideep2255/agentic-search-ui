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

Status: done
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
- [x] `resolve_model("guard" | "plan" | "synth")` returns the value of `GUARD_MODEL` / `PLAN_MODEL` / `SYNTH_MODEL` from the environment when set, and falls back to an app-config default per tier when the env var is unset or empty
- [x] No model id string is hardcoded outside the one app-config default table; a repo-wide grep for a literal OpenRouter-shaped model id (a string containing a provider-prefixed `/`) finds it only in that table, never inline in harness, node, or graph code
- [x] A tier's resolved model is fetched once at query start and held for the query's duration: two resolutions of the same tier within one query context return the identical value even when a test mutates the underlying env var mid-query
- [x] Passing a tier value outside `{"guard", "plan", "synth"}` raises a typed error before any network or model call is attempted

Breakdown:
- [x] `resolve_model()` reading env vars with app-config fallback
- [x] Query-scoped tier cache (resolve-once-per-query)
- [x] Tests: env-set, env-unset-fallback, mid-query-mutation-ignored, invalid-tier

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report.
- Criterion 1: `src/system_03_search_agent/harness/tiers.py:97-101` reads `_ENV_VAR_BY_TIER[validated]` and returns `_DEFAULT_MODELS[validated]` on an unset or empty value. Verified by `test_tiers.py` env-set / env-unset / empty-string parametrizations, 9 tests, all passing.
- Criterion 2: judge ran an independent grep, not the builder's own test: `grep -rn -E "deepseek|moonshotai|z-ai|openai/|anthropic/|gpt-4|claude-3|gemini" src/ | grep -v tiers.py` returns exit 1 (no matches). The only literals are `tiers.py:54-56`. The repo's own scan test (`test_no_model_id_shaped_string_outside_the_default_table`, `test_tiers.py:188-209`) carries a positive and a negative control, so it is not dead code.
- Criterion 3: `TierContext.resolve` (`tiers.py:125-141`) caches under a lock. `test_tier_context_valid_input_mid_query_env_mutation_is_ignored` (`test_tiers.py:90-106`) mutates `PLAN_MODEL` between two `resolve("plan")` calls and asserts both return the original.
- Criterion 4: `_validate_tier` (`tiers.py:64-72`) raises `UnknownTierError` before `os.environ.get` is reached; three invalid-tier tests pass.
- Command output: `python3 -m pytest tests/system_03_search_agent/harness/ -v` -> 115 passed; `python3 -m pytest tests/system_03_search_agent/harness/test_tiers.py -q` -> 21 passed.

History:
- 2026-07-28 lead: created, scoped from Section 25 row 2.0 and Section 3.1/3.3
- 2026-07-28 judge: verified all four acceptance criteria against the real code and an independent grep; marked done

### T-2.0-02: LiteLLM/OpenRouter `call_tier` with cost accounting

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-01
Spec: Technical_specification.md Section 3.3 (450-465), Section 3.5 (508-540), Section 19.2 (2813-2819)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/harness.py`
- `tests/system_03_search_agent/harness/test_harness.py`

Acceptance criteria:
- [x] Every call to `Harness.call_tier` issues its request through LiteLLM targeting `openrouter/<model_id>`, where `<model_id>` is `resolve_model(tier)`'s return value, never a direct provider SDK call
- [x] `call_tier` returns token usage (`prompt_tokens`, `completion_tokens`) alongside the completion and computes `call_cost_usd` as `prompt_tokens * input_price + completion_tokens * output_price`, using the OpenRouter price for the exact model that answered
- [x] A retried `call_tier` invocation (production-standards retry-safety gate) is metered as an independent billable event: its own `call_cost_usd` is computed and does not overwrite or absorb the first attempt's recorded cost
- [x] A `call_tier` invocation that hits an unresolvable tier or a LiteLLM/OpenRouter transport failure raises a classified error (transient, recoverable, or unexpected per Section 3.5) rather than silently returning a default or empty completion
- [x] Tests cover a mocked successful call asserting cost computation, a mocked transient failure with one retry counted as its own billable event, and an invalid-tier input

Breakdown:
- [x] `Harness.call_tier` wrapping LiteLLM's `openrouter/*` call shape
- [x] Token-usage to `call_cost_usd` computation against OpenRouter's per-model pricing
- [x] Transient/recoverable/unexpected error classification on call failure
- [x] Tests: success-path cost math, retried-call independent metering, invalid tier

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report.
- Criterion 1: `harness.py:324` builds `target = f"openrouter/{model_id}"` and `harness.py:329` passes it to `litellm.acompletion`. No provider SDK is imported anywhere in `src/`. Proven at runtime, not only by unit test: the judge's own end-to-end run through `core.run.run()` captured the four LiteLLM call targets `openrouter/judge-provider/guard-model`, `openrouter/judge-provider/guard-model`, `openrouter/judge-provider/plan-model`, `openrouter/judge-provider/synth-model`, in that order.
- Criterion 2: `harness.py:341-356` reads `usage.prompt_tokens`/`usage.completion_tokens` and computes `prompt_tokens * input_price + completion_tokens * output_price`; `_price_per_token` (`harness.py:176-214`) sources the price from `litellm.get_model_info(model=f"openrouter/{model_id}")` for the exact resolved model, falling back to a local table and raising `HarnessCallError(error_class="unexpected")` rather than pricing at zero when neither source knows the model.
- Criterion 3: the retry loop (`harness.py:327-339`) `continue`s only on a transient class and only while `attempt < max_attempts`; a successful retry computes and meters its own `call_cost_usd` at `harness.py:344-348`. `test_call_tier_transient_failure_retries_once_and_succeeds` (`test_harness.py:177-202`) asserts `call_count == 2`, the retry's own cost math, and that the running total equals exactly one call's cost (the failed first attempt billed nothing). `track_cost` (`harness.py:383-384`) adds, never assigns, so no attempt can overwrite another's cost.
- Criterion 4: `UnknownTierError` surfaces unwrapped from `_tier_context.resolve` at `harness.py:322` before any network attempt; every transport failure is classified by `_classify_exception` (`harness.py:148-160`) against explicit transient and recoverable exception tuples before `HarnessCallError` is raised. There is no code path that returns a default or empty completion.
- Criterion 5: `python3 -m pytest tests/system_03_search_agent/harness/test_harness.py -v` -> 27 passed, including the three named cases.
- Minor observation for a future ticket, not a criterion failure: `call_tier`'s internal retry does not re-run `cost_control.check_per_query_cap` before the second attempt, where Section 19.2 says a retried call's "estimated cost is checked against the remaining per-query budget before it is allowed to fire". Benign in this design, since the failed first attempt records zero cost, so the retry's projection is identical to the one the caller already approved.

History:
- 2026-07-28 lead: created, scoped from Section 3.3/3.5/19.2
- 2026-07-28 judge: verified all five acceptance criteria against the real code, the unit suite, and a live end-to-end capture of the LiteLLM call targets; marked done

### T-2.0-03: Cost caps enforcement and the cost event

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 19.1 (2800-2811), 19.2 (2813-2819), 19.3 (2821-2825), 19.4 (2827-2831), 19.5 (2833-2840)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/cost_control.py`
- `tests/system_03_search_agent/harness/test_cost_control.py`
- `env.example` (rename `PER_USER_DAILY_CAP_USD` to `PER_USER_DAILY_QUERY_CAP`, per the scope decision above)

Acceptance criteria:
- [x] A cap check runs before a model call fires: the harness estimates the next call's cost from the tier's typical token profile and refuses to dispatch a call that would push `query_cost_usd` past the per-query cap ($0.10 starter value, `PER_QUERY_COST_CAP_USD`), rather than dispatching first and discovering the overage afterward
- [x] When the per-query cap is hit, the loop stops making further model calls and moves directly to Write with whatever tool results already exist, shipping a partial cited result, never a blank failure
- [x] A user who has reached `PER_USER_DAILY_QUERY_CAP` (100) queries in the current daily boundary has a new query declined before Guardrail runs, with the decline message stating the query count and a reset time, never a dollar figure
- [x] Once `system_daily_cost_usd` reaches `SYSTEM_DAILY_CAP_USD`, a new query from any user is declined with a plain "paused for the day to stay within operating budget" message, no dollar figure, no technical cause named
- [x] `query_cost_usd`, `user_daily_query_count`, and `system_daily_cost_usd` are three independently tracked running counters; `system_daily_cost_usd` and `user_daily_query_count` are read back from the `interactions` table (Section 15) at process start rather than reset to zero on restart
- [x] A `cost` event fires after every metered model call, using `CostPayload` already defined in `contracts/events.py` (`query_cost_usd`, `query_cap_usd`, `cap_fraction`, `model_tier`), and `query_cost_usd`/`cap_fraction` are running totals, not deltas
- [x] The web_sse adapter's `/query` response never includes a `cost`-type event in what reaches the client, even though the harness's internal state tracks it
- [x] No dollar figure or currency symbol appears in any string reachable from a per-query-cap, per-user-cap, or system-wide-cap decline path

Breakdown:
- [x] Pre-flight cost estimate and per-query cap enforcement
- [x] Per-user daily query count enforcement, persisted and restart-safe
- [x] System-wide daily dollar cap enforcement, persisted and restart-safe
- [x] Cost event emission wired to `CostPayload`
- [x] Adapter-boundary filter dropping `cost` events from the end-user stream
- [x] `env.example` rename and comment fix
- [x] Tests: pre-flight refusal, partial-result-on-cap, per-user decline message, system-wide decline message, restart-safe counters, adapter filter, no-dollar-figure-in-user-text

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report.
- Criterion 1 (fires BEFORE the call, not after): `core/graph.py:191-194` is the single dispatch path every model-calling node uses, and it calls `cost_control.check_per_query_cap(...)` on line 191, then `harness.enforce_timeout(... harness.call_tier ...)` on 192-194. The check is a plain sync call that raises before the coroutine is ever awaited. Proven at runtime by the judge, not only by reading: with `PER_QUERY_COST_CAP_USD=0.0015` (below the guard tier's own `estimate_call_cost_usd` of 0.003), a real `run()` produced `['token', 'done']` and `len(mock_acompletion.call_args_list) == 0`, i.e. zero LiteLLM calls were ever dispatched.
- Criterion 2 (partial result, not a blank failure), verified through the real graph at a mid-loop boundary: with `PER_QUERY_COST_CAP_USD=0.0045` (enough for guard and think, not for plan), a real `run()` produced `['guard', 'cost', 'think', 'cost', 'token', 'done']`, made exactly two LiteLLM calls (both guard-tier), never invoked `coordinator_worker_execute`, emitted the `token` event carrying `PER_QUERY_CAP_PARTIAL_RESULT_NOTE`, and terminated with `done.trust_outcome == 'flag'`. The successful guard and think events were retained, not discarded.
- Criteria 3 and 4: `cost_control.py:308-334` and `375-394` raise `UserDailyQueryCapExceededError` / `SystemDailyCostCapExceededError`; `graph.py:234-244` runs both inside a real `session_scope()` at the top of `guardrail_node`, before its own `_dispatch_tier_call`, and `_decline_for_daily_cap` (`graph.py:269-294`) routes straight to `END` past `write`. Scope note accepted: the criterion's literal wording is "before Guardrail runs" and the implementation runs it as the first thing inside `guardrail_node`; since no guardrail validation logic exists yet and no model call fires first, the substantive property holds, and T-2.0-07's own scope note authorized this placement.
- Criterion 5 (restart-safe): verified structurally, which is stronger than the criterion asks. There is no in-process counter to lose. `get_user_daily_query_count` (`cost_control.py:265-275`) and `get_system_daily_cost_usd` (`cost_control.py:344-355`) issue a live `SELECT COUNT` / `SELECT COALESCE(SUM(...))` against `interactions` on every check, not a cached value read once at process start. `test_system_and_user_caps_are_restart_safe_via_a_fresh_session` (`test_cost_control.py:401-437`) commits rows, discards every reference, and reads back through a brand-new `Session`.
- Criterion 6: `build_cost_event_payload` (`cost_control.py:414-441`) reads `harness.get_query_cost_usd(trace_id)`, the same accumulator `track_cost` maintains, and computes `cap_fraction` from it. Judge's live capture of a real `run()` shows the four `cost` events as strictly increasing running totals, not deltas: `0.00096000`, `0.00192000`, `0.00288000`, `0.00384000`, with `cap_fraction` `0.0096 / 0.0192 / 0.0288 / 0.0384` against a `query_cap_usd` of 0.1.
- Criterion 7: `adapters/web_sse/app.py:62` applies `filter_events_for_end_user`. Judge's live capture: unfiltered `run()` output was `['guard','cost','think','cost','plan','cost','cost','done']`, filtered output was `['guard','think','plan','done']`. The repo's own `TestPostQueryFiltersCostEvents` (`test_query_endpoint.py:373-407`) additionally proves the filter is non-vacuous by asserting the unfiltered stream did contain a `cost` event; that test hits the real local PostgreSQL through the real FastAPI app.
- Criterion 8: judge inspected every user-facing string by hand. `user_daily_cap_decline_message` (`cost_control.py:278-290`) interpolates only an integer count and an `%H:%M UTC` label; `SYSTEM_DAILY_CAP_DECLINE_MESSAGE` (`361-364`) and `PER_QUERY_CAP_PARTIAL_RESULT_NOTE` (`402-405`) are static and carry no number at all. The `$` and `USD` tokens appear in this module only inside docstrings, comments, and identifier names, never inside a message string. `QueryCapExceededError`'s own message (`246-251`) also carries no figure, and `graph.py` never surfaces it to a user anyway.
- Command output: `python3 -m pytest tests/system_03_search_agent/harness/ -v` -> 115 passed; `python3 -m pytest tests/system_03_search_agent/adapters/web_sse/ -v` -> 27 passed.
- `env.example:86-94` rename verified in the diff against `main`: `PER_USER_DAILY_CAP_USD` -> `PER_USER_DAILY_QUERY_CAP`, with the unit-clarifying comment added.
- Gap recorded for the lead, explicitly out of this ticket's scope and therefore not a rejection: nothing in `src/` ever constructs an `Interaction` row (`grep -rn "Interaction(" src/` matches only the model definition at `data/models.py:154`). Both daily-cap counters therefore read zero forever in production until a later ticket persists interactions at query completion. The enforcement path is correct and tested; its input is not yet fed.

History:
- 2026-07-28 lead: created, scoped from Section 19.1-19.5; carries the `PER_USER_DAILY_CAP_USD` rename decision
- 2026-07-28 judge: verified all eight acceptance criteria, including two forced cap-hit runs through the real graph and a hand inspection of every user-facing string; marked done, with the unwritten-`interactions` gap recorded above

### T-2.0-04: Per-step timeout enforcement

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 19.1 (2800-2811, the per-step timeout row), Section 3.5 (508-540, `enforce_timeout`)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/harness.py` (extends T-2.0-02's `enforce_timeout` method)
- `tests/system_03_search_agent/harness/test_harness.py` (extends T-2.0-02's file)

Acceptance criteria:
- [x] `enforce_timeout(step, coro, budget_s)` aborts and returns a timeout signal if `coro` has not completed within `budget_s`, without leaving the underlying task running unbounded in the background
- [x] `budget_s` for a given query resolves from Think's emitted `query_class` using the fixed mapping recorded in this phase's scope decisions: `lookup` to 5s, `single_hop` to 10s, `aggregate` and `multi_hop` both to 30s, `exploratory` to 120s
- [x] On a per-step timeout, the loop does not hang or crash: it proceeds to synthesize from whatever partial tool results already exist, per Section 19.1's trigger behavior for this cap. Satisfied at this ticket's file scope by raising a catchable, classified `HarnessCallError` rather than letting a `TimeoutError` propagate unhandled; the actual Guardrail-to-Write loop nodes that catch it and drive the partial-synthesis handoff are not built yet (T-2.0-05 onward), so this criterion is structurally met, not loop-wired
- [x] A step that completes just under `budget_s` is not falsely aborted: a test with a fast-completing coroutine asserts the real result is returned, not a timeout
- [x] A step that exceeds `budget_s` produces a classified `error` event (`scope="step"`, an `error_class` per Section 3.5's transient/recoverable/unexpected taxonomy) distinguishable from a step that failed for a non-timeout reason. Satisfied at this ticket's file scope: `HarnessCallError.error_class="transient"` and `source=f"harness.enforce_timeout:{step}"` carry everything a future `ErrorPayload(scope="step", ...)` needs; no `ErrorPayload` is constructed here since no loop node exists yet to emit it

Breakdown:
- [x] `enforce_timeout` wrapping any step coroutine with a hard deadline and clean cancellation
- [x] `query_class` to `budget_s` mapping table
- [x] Timeout-triggered partial-synthesis handoff (structural only, see acceptance criterion 3 note; full wiring is a loop-node ticket)
- [x] Tests: real abort under budget, false-positive-abort check, error event shape on timeout

Evidence:
- `enforce_timeout(step, coro, budget_s)` added to `Harness` in `src/system_03_search_agent/harness/harness.py:236-306` (method body `279-306`), using `asyncio.wait_for` so a timeout cancels and awaits the inner task before raising, never leaving it running.
- `QueryClass` alias, `_QUERY_CLASS_BUDGET_S` table, and `budget_for_query_class()` in `src/system_03_search_agent/harness/harness.py:71-72` and `203-229`, implementing the settled 2026-07-28 DECISIONS.md mapping unchanged.
- Tests added to `tests/system_03_search_agent/harness/test_harness.py`: fast-step-returns-real-result, slow-step-aborts-and-raises, step-name-distinguishes-two-timeouts, aborted-task-actually-cancelled-not-orphaned (real `asyncio.sleep`, flag-set-only-on-graceful-completion), non-timeout-failure-propagates-unchanged, call_tier-failure-inside-a-step-keeps-its-own-source-and-error_class, and the five-way `budget_for_query_class` parametrized resolution plus an unmapped-class `ValueError` test.
- `python3 -m pytest tests/system_03_search_agent/harness/test_harness.py -q`: 27 passed (19 pre-existing T-2.0-02 tests unchanged plus 8 new). `python3 -m pytest tests/system_03_search_agent/harness/ -q`: 48 passed (adds `test_tiers.py`).
- No existing T-2.0-02 code was modified, only its module docstring (reflecting `enforce_timeout` no longer being absent) and the `typing` import line (added `Awaitable`).

Judge verification, 2026-07-28, independent of the builder's report above:

- Criterion 1 (aborted, not orphaned): `harness.py:455-466` uses `asyncio.wait_for`, which cancels and awaits the inner task before re-raising. Proven with a real cancellation, not a mock: `test_enforce_timeout_aborted_step_is_actually_cancelled_not_orphaned` (`test_harness.py:396-417`) sets a flag only after a real `asyncio.sleep(0.3)` completes, times the step out at `budget_s=0.05`, then waits a further 0.35s and asserts the flag is still `False`. An orphaned background task would have set it.
- Criterion 2 (mapping matches DECISIONS.md exactly): `_QUERY_CLASS_BUDGET_S` at `harness.py:225-231` reads `lookup: 5.0, single_hop: 10.0, aggregate: 30.0, multi_hop: 30.0, exploratory: 120.0`. The judge compared this character by character against the 2026-07-28 DECISIONS.md row ("`lookup` to 5s, `single_hop` to 10s, `aggregate` and `multi_hop` both to 30s, `exploratory` to the 120s deep-research budget") and against the task brief's stated mapping. All three agree. The five parametrized cases in `test_harness.py` assert each value.
- Criteria 3 and 5 (the deferred half): the builder's note deferred loop-wiring to a later ticket. The judge confirmed T-2.0-07 actually closed it rather than taking the deferral on trust. `graph.py:257-258, 319-320, 364-365, 451-452` catch `HarnessCallError` at every model-calling node, `_step_error_kwargs` (`graph.py:197-216`) builds a real `ErrorPayload` with `scope="step"` and the classified `error_class`, and `write_node` (`graph.py:410-429`) emits it and ships a `done` with `trust_outcome="refuse"` instead of crashing. Covered by `test_step_failure_on_think_routes_to_write_as_a_refusal` (`test_graph.py`), passing.
- Criterion 4 (no false abort): `test_enforce_timeout_fast_step_returns_real_result_within_budget`, passing.
- Command output: `python3 -m pytest tests/system_03_search_agent/harness/test_harness.py -v` -> 27 passed. `python3 -m pytest tests/system_03_search_agent/harness/ -v` -> 115 passed.

History:
- 2026-07-28 lead: created, scoped from Section 19.1/3.5; carries the query_class-to-budget mapping decision
- 2026-07-28 builder: implemented `enforce_timeout` and the query_class-to-budget_s mapping on top of the merged T-2.0-02 `Harness` class; 8 new tests added, all 27 tests in `test_harness.py` pass (48 across the harness test directory); left uncommitted in worktree per instructions
- 2026-07-28 judge: re-verified all five acceptance criteria from the code and a real cancellation test, confirmed the budget mapping against DECISIONS.md, and confirmed T-2.0-07 actually closed the two structurally-met criteria rather than accepting the deferral on the ticket's own word; marked done

### T-2.0-05: Coordinator-worker split scaffold

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 3.4 (467-506)

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/coordinator_worker.py`
- `tests/system_03_search_agent/harness/test_coordinator_worker.py`

Acceptance criteria:
- [x] `coordinator_worker_execute(tool_calls)` runs independent tool calls concurrently via `asyncio.gather`, not sequentially: a test with two artificially delayed fake tool calls asserts total wall-clock time is close to the slower call alone, not the sum of both
- [x] A tool result flagged as containing untrusted free text is routed through an isolated reader call before Write ever sees it; a tool result carrying only structured fields passes straight through with no reader call
- [x] The reader call is constructed with access to Read plus only the one API/tool that produced the payload; it is never given Write access or the ability to invoke a different tool
- [x] The function's return value for a free-text-routed result is the reader's structured findings only (extracted entities, normalized ids, a short evidence summary), never the original free-text payload; the return value for a structured result is the pass-through structured fields
- [x] Tests use fake/fixture tool calls, since no real tool exists yet (`cypher_query` lands in phase 2.1), and assert the free-text/structured branching by inspecting the returned `Finding` shape

Breakdown:
- [x] `Finding` type (internal, harness-owned, not part of the wire-level Event taxonomy)
- [x] `coordinator_worker_execute` with `asyncio.gather` fan-out
- [x] Isolated reader-pass call, scoped to Read plus the originating tool only
- [x] Structured-vs-free-text branching
- [x] Tests: concurrency timing, free-text routing, structured pass-through, reader scope

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report.
- Criterion 1: `coordinator_worker.py:291-293` fans out via `asyncio.gather`. `test_free_text_reader_calls_run_concurrently` (`test_coordinator_worker.py:55-83`) uses two real 0.2s-delayed reader calls and asserts total elapsed `< 0.34s`, which a sequential run at 0.4s cannot pass. Uses a real `asyncio.sleep`, not a mocked clock.
- Criterion 2: `_process_one` (`coordinator_worker.py:249-252`) branches on `contains_untrusted_free_text`. `test_structured_result_passes_through_with_no_reader_call` asserts `harness.call_tier.assert_not_awaited()`, so a structured result makes exactly zero `call_tier` calls. `test_mixed_batch_only_calls_reader_for_free_text_entry` asserts `await_count == 1` for a two-item batch with one free-text entry.
- Criterion 3 (reader isolation): enforced structurally, not only by prompt. `Harness.call_tier`'s signature (`harness.py:285-291`) accepts only `tier`, `messages`, and `cache_prefix`; there is no tools parameter, so the reader has no tool-calling surface to be given in the first place. `_build_reader_messages` (`coordinator_worker.py:163-177`) passes exactly two messages, the fixed scoping system prompt and the one payload, with nothing from the surrounding query or other tool results. `_reader_pass` (`222-232`) issues exactly one call with no retry or follow-up loop. The tier is `"guard"`, matching Section 3.2's "Act, coordinator-worker reader pass -> Guard" row. The scoping prompt itself is asserted in `test_free_text_result_routes_through_reader_call` (`test_coordinator_worker.py:120-127`), which checks the system message states "no ability to call any tool" and "write or modify", and that the user message equals the payload exactly.
- Criterion 4 (no raw-payload leak): `_parse_reader_response` (`coordinator_worker.py:180-219`) never reads `result.free_text`, and on any parse failure degrades to empty findings plus a fixed string rather than falling back to the reader's raw content. Two tests plant a unique marker string in the payload and assert it is absent from every `Finding` field and from `repr(finding)`, including the case where a misbehaving reader echoes the whole payload back as its response. `_MAX_ENTITIES` / `_MAX_NORMALIZED_IDS` / `_MAX_EVIDENCE_SUMMARY_CHARS` (`coordinator_worker.py:70-74`) apply the multi-agent pipeline gate's maxItems/maxLength discipline to a dataclass that Pydantic does not cover.
- Criterion 5: `ToolExecutionResult` (`coordinator_worker.py:101-126`) is the fixture type; all seven tests branch on the returned `Finding.source` field.
- Criterion satisfied at the loop level too, which this ticket did not itself require: the judge confirmed `act_node` (`graph.py:388`) genuinely invokes `coordinator_worker_execute`. A spy installed on `graph_module.coordinator_worker_execute` during a real `run()` recorded exactly one invocation, with `(0, 0)` paired list lengths. The module is not dead code.
- Command output: `python3 -m pytest tests/system_03_search_agent/harness/test_coordinator_worker.py -v` -> 7 passed.
- Residual noted, not a criterion failure: a reader that returns well-formed JSON whose `evidence_summary` echoes the payload would pass that text through, truncated at 500 chars. Inherent to the reader pattern (the reader's output is the finding); worth a defense if a later phase hardens this path.

History:
- 2026-07-28 lead: created, scoped from Section 3.4
- 2026-07-28 judge: verified all five acceptance criteria, including a real-clock concurrency assertion and a marker-based leak test, and confirmed the module is actually called by `act_node`; marked done

### T-2.0-06: Prompt-cache stable-prefix scaffold

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-02
Spec: Technical_specification.md Section 4.2 (569-590), Section 4.5 (624-626); `prompt-cache-discipline.md`

Files this ticket may create or modify:
- `src/system_03_search_agent/harness/cache.py`
- `tests/system_03_search_agent/harness/test_cache.py`

Acceptance criteria:
- [x] `build_stable_prefix()` assembles the prefix in the fixed order: system instructions and behavioral directives, then the tool-schema slot (an empty, alphabetically-sortable list is acceptable now since no tool exists yet; the slot's position never shifts when tool schemas are added starting phase 2.1), then the static graph/BioLink concept-level schema (10 labels, 14 predicates)
- [x] Two calls to `build_stable_prefix()` invoked with different dynamic-suffix inputs (the suffix is passed and used separately, never merged into the prefix) produce byte-identical prefix output, verified by a SHA-256 equality assertion in a test
- [x] No timestamp, request id, `trace_id`, or session id appears anywhere in the assembled prefix: a test constructs two calls with different simulated trace ids and asserts the prefix hash is unchanged
- [x] The tool-schema slot's sort order is fixed in code (alphabetic by tool name) and is never re-derived at runtime from a source that could reorder between calls
- [x] `Harness.call_tier` (T-2.0-02) accepts a `cache_prefix` parameter built by this module, matching the Harness class signature in Section 3.5

Breakdown:
- [x] `build_stable_prefix()` with the three fixed slots
- [x] SHA-256 byte-equality helper for prefix verification
- [x] `call_tier` wiring to accept and forward `cache_prefix`
- [x] Tests: assembly order, byte-equality across differing suffixes, no-volatile-token check

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report.
- Criterion 1: `build_stable_prefix` (`cache.py:194-197`) joins exactly three sections in the fixed order `SYSTEM_INSTRUCTIONS`, `_build_tool_schema_section(...)`, `_BIOLINK_CONCEPT_SCHEMA`. The tool-schema slot renders as two fixed boundary markers with nothing between them when empty (`cache.py:91-92`), so adding schemas in phase 2.1 fills the slot rather than restructuring the string around it; `test_tool_schema_slot_position_stable_when_schemas_are_added` asserts exactly that. Label counts: the module uses the live-verified 11 vertex / 14 edge labels from `docs/data-engineering/Knowledge_graph_on_server_reference.md` rather than Section 4.2's stated 10/14, a deviation the builder flagged in `cache.py:31-41` and logged to DECISIONS.md rather than silently choosing; the judge accepts the deviation as disclosed and correctly escalated to the Step 6.2 reconciliation.
- Criterion 2: `test_prefix_byte_identical_across_differing_dynamic_suffixes` (`test_cache.py:84-100`) builds two full message lists whose suffixes differ, asserts the lists differ, then asserts `prefix_sha256(...) == prefix_sha256(...)` AND raw string equality on the leading system message. The signature itself is the stronger guarantee: `build_stable_prefix` takes no suffix-shaped parameter at all, so the two cannot be conflated by a future caller.
- Criterion 3: `test_no_volatile_token_leaks_across_differing_trace_ids` (`test_cache.py:110-125`) calls through a helper that holds a differing `trace_id` in local scope and asserts both the string and the SHA-256 are unchanged; a sibling test does the same for a simulated timestamp, and a third asserts the literal substrings `trace_id`, `session_id`, `request_id`, `timestamp` never appear in the assembled output.
- Criterion 4: `_build_tool_schema_section` (`cache.py:94-98`) always re-sorts by `name` and serializes with `json.dumps(..., sort_keys=True)`, so neither caller ordering nor dict key ordering can shift the bytes. Three tests cover unsorted input, already-sorted input, and differing key order.
- Criterion 5: `Harness.call_tier(..., cache_prefix: str | None = None)` at `harness.py:285-291`, threaded through `_with_cache_prefix` (`harness.py:253-262`) as a leading system message. `build_stable_prefix` returns `str`, so the types line up.
- Command output: `python3 -m pytest tests/system_03_search_agent/harness/test_cache.py -v` -> 16 passed.
- Gap recorded for the lead, outside this ticket's stated criteria and therefore not a rejection: `grep -rn "build_stable_prefix" src/` finds no caller. `core/graph.py` calls `harness.call_tier(tier, messages)` with no `cache_prefix`, so every model call the real loop makes today runs with no stable prefix and the prompt-cache saving this module exists to produce is not yet realized. The ticket only required that `call_tier` accept the parameter, which it does; wiring it belongs to a follow-up.

History:
- 2026-07-28 lead: created, scoped from Section 4.2/4.5 and prompt-cache-discipline.md
- 2026-07-28 judge: verified all five acceptance criteria including the SHA-256 byte-equality and no-volatile-token assertions; marked done, with the zero-production-callers gap recorded above

### T-2.0-07: LangGraph five-node loop, stub nodes

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: T-2.0-01, T-2.0-02, T-2.0-03, T-2.0-04, T-2.0-05, T-2.0-06
Spec: Technical_specification.md Section 3.2 (429-448), Section 25 row 2.0 (line 3181); CLAUDE.md's agent-loop pattern

Files this ticket may create or modify:
- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/core/state.py`
- `src/system_03_search_agent/core/run.py`
- `src/system_03_search_agent/adapters/web_sse/app.py` (added at integration time: this is the one point Section 19.4's builder-only cost-event filter, already built as `cost_control.filter_events_for_end_user` in T-2.0-03, needs to be applied now that `run()` can emit a real `cost` event; T-2.0-03 explicitly deferred this wiring here since no real loop existed when it was built)
- `tests/system_03_search_agent/core/test_graph.py`
- `tests/system_03_search_agent/core/test_run.py` (extends the existing phase 1.0 test)
- `tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py` (extend only, for the cost-event-filter assertion)

Acceptance criteria:
- [x] `run(query, context)` is backed by a real LangGraph `StateGraph` with five nodes named `guardrail`, `think`, `plan`, `act`, `write`, compiled and invoked in that fixed sequence for every query
- [x] The `guardrail` and `think` nodes call `Harness.call_tier` with `tier="guard"`; the `plan` node calls with `tier="plan"`; the `write` node calls with `tier="synth"`, matching Section 3.2's step-to-tier table exactly
- [x] Every node's model call passes through `enforce_timeout` with the budget resolved per T-2.0-04's mapping, and every node's cost is tracked through T-2.0-03's cost control before the node returns
- [x] The graph still emits only Section 2.3 typed `Event` instances end to end: the intermediate `think`, `plan`, and `cost` events all validate against their Section 2.3 payload models. Builder's note on this criterion's second clause: the phase 1.0 guard-then-done test scenario (guard event emitted, done terminal, schema-valid, trace_id/seq/ts hold) still passes, but the literal test FILE is not byte-unmodified, since the ticket's own file list marks `test_run.py` "extends the existing phase 1.0 test" and the build prompt explicitly required updating it to assert the real (now longer) event sequence rather than weakening it to "doesn't crash". Treated the file-list note as authoritative over this bullet's stricter wording; flagging the tension rather than silently resolving it
- [x] Each stub node produces a schema-valid payload without performing real classification, tool selection, or synthesis logic; no stub node fabricates a citation or a `trust_signal` outcome that a later phase has not yet earned (real Act tool logic lands in phase 2.1+, guardrail's real validation in phase 3.0, write's real grounding in phase 2.2)
- [x] The per-query cap's trigger behavior (T-2.0-03) is reachable through the real graph: a test that forces the cap to be hit mid-loop asserts the graph moves to `write` early with partial results rather than continuing to `act`
- [x] `POST /query`'s response never includes a `cost`-type event, now that `run()` can actually emit one: `cost_control.filter_events_for_end_user` is applied to the event list before it reaches the client

Breakdown:
- [x] `core/state.py` graph state type
- [x] `core/graph.py` StateGraph definition and compilation, five stub nodes
- [x] `core/run.py` rewritten to build and invoke the compiled graph instead of the phase 1.0 linear scaffold
- [x] `adapters/web_sse/app.py` wired to `filter_events_for_end_user`
- [x] Tests: node sequence, per-node tier assignment, event schema validation on every emitted type, stub-node non-fabrication check, cap-triggered early exit to write, adapter cost-event filter

Evidence:
- `src/system_03_search_agent/core/state.py`: `GraphState` TypedDict (94 lines), `events` field uses `Annotated[list[Event], add]` as a reducer so each node returns only the events it added; every other field is plain last-write-wins.
- `src/system_03_search_agent/core/graph.py` (~400 lines): five nodes (`guardrail_node`, `think_node`, `plan_node`, `act_node`, `write_node`), `_EventSink` per-node event/seq bookkeeping, `_dispatch_tier_call` (the shared check-cap-then-enforce-timeout-then-call_tier sequence), conditional routing (`_route_after_guardrail/_think/_plan`) sending a per-query cap hit or a step `HarnessCallError` straight to `write`, and the two daily caps checked once in `guardrail_node` via a real `session_scope()` DB session, routing straight to `END` on a decline. `compiled_graph` is compiled once at module import time (documented rationale in the module docstring: the graph structure is static, every per-query value lives in `GraphState`).
- `src/system_03_search_agent/core/run.py`: rewritten to build one `Harness`, assemble the initial `GraphState`, and `await compiled_graph.ainvoke(...)` inside `langsmith.run_helpers.tracing_context(enabled=False)` (see the tracing-scope note below), yielding the accumulated `events` list. Still `async def` with a `yield`, so `inspect.isasyncgenfunction(run)` still holds.
- `src/system_03_search_agent/adapters/web_sse/app.py`: `POST /query` now applies `filter_events_for_end_user` to the collected event list before returning it.
- Tests: `tests/system_03_search_agent/core/test_graph.py` (new, 21 tests): five-node structure, the full happy-path event-type sequence (`guard, cost, think, cost, plan, cost, cost, done`), per-node tier assignment (guardrail+think call the guard-tier model twice, plan calls plan-tier once, write calls synth-tier once), schema validation on every emitted event, no fabricated `citation`/`trust_signal`, the `act` node's `coordinator_worker_execute([], [])` integration point, a per-query-cap hit forced on `plan` short-circuiting to `write` without reaching `act` (asserted via a spy on `coordinator_worker_execute`), the same cap hit discovered at `write` itself, a non-cap `HarnessCallError` (an unexpected model failure) routing to `write` as a refusal, and all three daily-cap paths (system-cap decline, user-cap decline, `user_id=None` skipping only the per-user check).
- `tests/system_03_search_agent/core/test_run.py` (rewritten, 16 tests, was 12): kept every phase-1.0-shaped assertion that still holds (Event instances, guard event schema-valid, exactly one terminal `done`, trace_id propagation, monotonic no-repeat `seq`, tz-aware `ts`); updated `test_done_event_payload_is_schema_valid` since `total_cost_usd` is now a real positive metered total, not the scaffold's hardcoded `0.0`; removed `TestRunMakesNoDirectLlmOrToolCall` (asserted `core/run.py`'s source contained no `litellm`/`harness` imports, which is now false by design, the ticket's entire point); added `TestRunEmitsTheFullFiveNodeLoop` (4 new tests: `think`/`plan`/`cost` events present and schema-valid, no fabricated `citation`/`trust_signal`).
- `tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py` (extended, +2 tests, 24 total, was 22): added `_harness_env`/`_mock_litellm` autouse fixtures (needed for every pre-existing test in this file to keep passing now that `run()` drives real `Harness.call_tier` calls) and `TestPostQueryFiltersCostEvents`, which asserts the HTTP response never contains a `cost`-type event AND that the real, unfiltered `run()` output did produce one (proving the filter does real work, not passing vacuously).
- Tracing scope note (logged in DECISIONS.md, 2026-07-28): this repo's `.env` sets `LANGCHAIN_TRACING_V2=true` with no `LANGSMITH_API_KEY`, staged ahead of the phase 5.0/5.1 tracing deliverable. `run()` is the first code path to actually invoke a compiled LangGraph graph; without disabling tracing, every call made a real, failing outbound HTTPS call to `api.smith.langchain.com`. `run()` wraps its one `ainvoke()` in `langsmith.run_helpers.tracing_context(enabled=False)` (scoped to that call, not a process-wide env override) until phase 5.0/5.1 replaces it with a real tracer.
- `python3 -m pytest tests/ -q`: 463 passed (baseline before this ticket: 436; net +27, matching the three files' own before/after counts). `ruff check` clean on every file this ticket touched (two pre-existing, unrelated findings confirmed via `git show HEAD:...` diff: `app.py`'s `Depends()`-in-default-arg B008, and `test_query_endpoint.py`'s already-present RUF100 unused-`noqa` findings on its module-level, post-`pytest.skip`, `# noqa: E402` imports).
- Left uncommitted per instructions, on `phase/2.0-langgraph-agent-loop`, for lead review.

Judge verification, 2026-07-28, independent of the builder's report above. The judge wrote and ran its own integration harness rather than relying on the repo's tests:

- Criterion 1 (a real, invocable LangGraph loop): `graph.py:525-547` builds a `StateGraph(GraphState)` with the five named nodes and compiles it. The judge imported `system_03_search_agent.core.run.run`, built a valid `Query`/`RequestContext`, mocked only `litellm.acompletion`/`get_model_info`, and drove `run()` to completion. Real output: `seq=0 guard`, `seq=1 cost`, `seq=2 think`, `seq=3 cost`, `seq=4 plan`, `seq=5 cost`, `seq=6 cost`, `seq=7 done`. Every event carried `version=v1`, the request `trace_id`, a tz-aware `ts`, a monotonic no-repeat `seq`, and a payload that passed `PAYLOAD_MODEL_BY_TYPE[type].model_validate(...)`.
- Criterion 2 (tier assignment matches Section 3.2): the judge captured the actual LiteLLM call targets from that run, in order: `openrouter/judge-provider/guard-model`, `openrouter/judge-provider/guard-model`, `openrouter/judge-provider/plan-model`, `openrouter/judge-provider/synth-model`. Guardrail and think on guard, plan on plan, write on synth, `act` firing no model call at all. Exactly Section 3.2's table.
- Criterion 3: `_dispatch_tier_call` (`graph.py:174-194`) is the single path all four model-calling nodes use, and it runs `check_per_query_cap` then `enforce_timeout(step, call_tier(...), budget_s)`. Budgets resolve through `budget_for_query_class` at `graph.py:254, 316, 360, 444`. Every successful node emits a `cost` event before returning.
- Criterion 4 (typed events end to end): validated above. On the builder's flagged tension about `test_run.py` being modified rather than byte-unmodified: the judge reviewed the diff. The only removal is `TestRunMakesNoDirectLlmOrToolCall`, which asserted `core/run.py`'s source contains no `litellm` or `harness` import, an assertion this ticket's entire purpose makes false by design. Removing an assertion that contradicts the newly intended design is legitimate, and the builder disclosed it rather than removing it silently. Every phase-1.0-shaped assertion that still holds was kept; net `test_run.py` grew from 12 to 16 tests. Not a weakened verify surface under `goal-contracts`.
- Criterion 5 (no fabrication): the judge's own run produced no `citation` and no `trust_signal` event. `guardrail` emits `passed=True, category="ok"`, `think` emits `query_class="lookup"` with a narrative that names itself a stub, `plan` emits `tool_calls=[]`. No stub claims an outcome it has not earned.
- Criterion 6 (cap-triggered early exit, run by the judge, not read): with `PER_QUERY_COST_CAP_USD=0.0045`, a real `run()` produced `['guard','cost','think','cost','token','done']`, made exactly two LiteLLM calls (both guard-tier), and a spy installed on `graph_module.coordinator_worker_execute` recorded zero invocations, proving `act` was never reached. The `token` event carried `PER_QUERY_CAP_PARTIAL_RESULT_NOTE` and `done.trust_outcome` was `flag`. A second scenario at `PER_QUERY_COST_CAP_USD=0.0015` refused before the very first call (zero LiteLLM calls) and still shipped `['token','done']`, never a blank failure. The repo's own `test_per_query_cap_hit_on_plan_short_circuits_to_write_without_reaching_act` (`test_graph.py:325-361`) covers the same path with its own spy; it passes.
- Criterion 7 (`cost` filtered at the adapter): `app.py:62`. Judge's live comparison: unfiltered `run()` output `['guard','cost','think','cost','plan','cost','cost','done']`, filtered `['guard','think','plan','done']`.
- Command output: `python3 -m pytest tests/ -q` -> 463 passed (baseline on `main`: 314 passed, so +149 across the phase). `python3 -m pytest tests/system_03_search_agent/core/ -v` -> 37 passed. `python3 -m pytest tests/system_03_search_agent/adapters/web_sse/ -v` -> 27 passed.
- Evidence correction, recorded because a judge must not let a false evidence claim stand: this ticket's own bullet above states "`ruff check` clean on every file this ticket touched (two pre-existing, unrelated findings ...)". That is false against `main`. `ruff check .` on `main` reports 5 findings, none of them in `src/` or `tests/`; on this branch it reports 20, i.e. 15 new findings, all in `src/` and `tests/`. `git log -S` attributes the `app.py` B008 and the six `test_query_endpoint.py` RUF100 findings to commit 22d56b7 (T-2.0-08), which is on this phase branch, so they were pre-existing only relative to this ticket's own base, never relative to `main`. See the phase-level lint finding below.

History:
- 2026-07-28 lead: created, scoped from Section 3.2/25; integrates T-2.0-01 through T-2.0-06
- 2026-07-28 builder: implemented `core/state.py`, `core/graph.py`, rewrote `core/run.py`, wired `adapters/web_sse/app.py` to `filter_events_for_end_user`; added `test_graph.py` (21 tests), rewrote `test_run.py` (16 tests, was 12), extended `test_query_endpoint.py` (+2 tests, 24 total); full suite 463 passed (up from 436), no regressions; logged the LangSmith `tracing_context(enabled=False)` scope decision to DECISIONS.md; left uncommitted for lead review, status set to in-review (not done) per instructions
- 2026-07-28 judge: verified all seven acceptance criteria with an independently written end-to-end integration harness (real `run()`, real graph, real harness, only LiteLLM mocked) plus two forced cap-hit runs; corrected the ticket's false "ruff check clean" evidence claim; marked done

### T-2.0-08: Server-derive `user_id` on `/query`

Status: done
Refine: refined
Branch: phase/2.0-langgraph-agent-loop
Depends on: none
Spec: F-1.1-17 (`tracker/phase_1.1.md`, lines 671-689); `requirements/phase_6/Continuation_prompt.md` line 98 ("Phase 2.0 owns server-deriving that value")

Files this ticket may create or modify:
- `src/system_03_search_agent/adapters/web_sse/app.py`
- `src/system_03_search_agent/contracts/query.py`
- `tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py`

Acceptance criteria:
- [x] `POST /query` requires a valid Bearer access token via the existing `get_current_user` dependency; a request with no token or an invalid or expired token is rejected with 401 before `run()` is ever called
- [x] The `user_id` passed into `run()`'s `Query` is always the server-derived value from the verified token's subject claim, never a client-supplied value
- [x] A test posts a request carrying an attacker-chosen `user_id` in the body and asserts the value actually used downstream is the token's subject, not the body's, whether `Query.user_id` is removed from the client-facing contract or silently overwritten before `run()` is called
- [x] The existing phase 1.0 test asserting `/query`'s typed-event round trip is updated to authenticate first, and continues to pass

Breakdown:
- [x] `get_current_user` wired as a dependency on `POST /query`
- [x] Server-side override or removal of client-supplied `user_id`
- [x] Tests: no-token-401, attacker-chosen-user_id-ignored, existing round trip updated and passing

Evidence:
- Judge-verified 2026-07-28, independent of the builder's report. F-1.1-17 is closed.
- Criterion 1: `app.py:56-59` declares `current_user: User = Depends(get_current_user)`. FastAPI resolves dependencies before the handler body, so a 401 fires before `run()` is reachable. Four tests cover it: `test_missing_token_returns_401`, `test_invalid_token_returns_401`, `test_missing_bearer_scheme_returns_401`, and `test_missing_token_never_invokes_run` (`test_query_endpoint.py:297-311`), which installs a spy on `app_module.run` and asserts the spy was never entered on the 401 path. That last test is what makes the "before `run()` is ever called" clause verified rather than assumed.
- Criterion 2: `app.py:60` builds `authenticated_query = request.query.model_copy(update={"user_id": str(current_user.id)})` and passes that copy, never `request.query`, into `run()` on line 61. The client-supplied value is unconditionally overwritten, not merely validated.
- Criterion 3 (the attacker test, run by the judge): `test_attacker_supplied_user_id_is_ignored_for_the_query_passed_to_run` (`test_query_endpoint.py:329-344`) posts a body carrying `"user_id": "attacker-chosen-user-id"` with a valid token for a different, freshly signed-up user, spies on `run()`, and asserts `captured["user_id"] == user_id` and `captured["user_id"] != "attacker-chosen-user-id"`. Two sibling tests cover the omitted-`user_id` case and two distinct authenticated users each resolving to their own id. `python3 -m pytest "tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py::TestPostQueryAuth" -q` -> 7 passed. These tests hit the real local PostgreSQL through the real FastAPI app, so `get_current_user` resolves a genuine `User` row rather than a mock.
- Criterion 4: the phase 1.0 round-trip tests (`TestPostQueryValidRequest`, 5 tests) were updated to authenticate first and all pass. `tests/.../auth/test_router.py` was also updated for the routing shadow (commit c17a82d) and passes.
- Contract note: `Query.user_id` stays on the wire (`contracts/query.py:33`) with a comment marking it advisory. Silently overwriting rather than rejecting is one of the two dispositions the criterion explicitly permits.
- Lint regression attributable to this ticket, recorded so it is not lost: commit 22d56b7 introduced 7 of the phase's 15 new `ruff` findings, all absent on `main`. `app.py:58` B008 (`Depends()` in a default arg) departs from the repo's own established convention, since every `Depends()` default in `auth/router.py` carries `# noqa: B008 - idiomatic FastAPI DI`. Six more are RUF100 unused-`noqa` findings from `# noqa: E402` directives added at `test_query_endpoint.py:68-73` for a rule this repo does not enable. Not an acceptance-criterion failure, so not grounds for rejection; see the phase-level finding below.

History:
- 2026-07-28 lead: created, closing F-1.1-17 per the continuation prompt's explicit assignment to this phase
- 2026-07-28 judge: verified all four acceptance criteria, ran the attacker-supplied-`user_id` test and the never-invokes-`run` test directly against the real app and database; marked done and closed F-1.1-17

## Findings

Carried forward from phase 1.1, not newly filed in this phase:

### F-1.1-17: `/query` is unauthenticated and trusts a client-supplied `user_id`

Severity: low. Status: closed 2026-07-28 by the judge, verified fixed under T-2.0-08. Previously rejected as a phase 1.1 defect (correct behavior for phase 1.0's shipped scope) and converted to this phase's T-2.0-08. See `tracker/phase_1.1.md` lines 671-689 for the original ruling, and T-2.0-08's Evidence block above for the verification.

Filed by the judge at phase close, 2026-07-28. None blocks the phase; all are recorded so the lead can dispatch them rather than lose them. The judge files, the judge does not fix or close.

### F-2.0-01: 15 new `ruff` findings in `src/` and `tests/`, on a lint-clean base

Severity: low. Status: closed 2026-07-28 by the lead. `ruff check --fix` resolved 13 automatically (verified: full suite still 463 passed after the auto-fix); the remaining 4 fixed by hand: `app.py:58` got the same `# noqa: B008 - idiomatic FastAPI dependency injection` convention `auth/dependencies.py` already uses; `cache.py`'s join became an f-string; `harness.py:202`'s `except Exception: pass` kept its documented reasoning with an added `# noqa: S110`; `test_harness.py:56`'s bare `Exception` became `RuntimeError`. `ruff check src/system_03_search_agent/ tests/system_03_search_agent/` now reports "All checks passed!".

`ruff check .` on `main` reports 5 findings, none of them in `src/` or `tests/`. On `phase/2.0-langgraph-agent-loop` it reports 20. The 15 new ones are all in code this phase wrote:

- `src/system_03_search_agent/adapters/web_sse/app.py:58` B008, and `tests/.../test_query_endpoint.py:68-73` six RUF100 unused-`noqa` findings. Both from commit 22d56b7 (T-2.0-08), confirmed with `git log -S`. The B008 departs from the repo's own convention, since every `Depends()` default in `auth/router.py` carries `# noqa: B008 - idiomatic FastAPI DI`.
- `src/system_03_search_agent/harness/harness.py`: UP035 (line 69, `Awaitable` from `typing`), S110 (201, `try`/`except`/`pass`), RUF100 (330, unused `noqa: BLE001`), UP041 (457, `asyncio.TimeoutError` alias).
- `src/system_03_search_agent/harness/cache.py:195` FLY002.
- `tests/.../test_cache.py` I001 and F401 (unused `json` import); `tests/.../test_harness.py:56` TRY002.

Why it matters: the `/verify` skill runs `ruff check .` and treats a real lint violation as FAIL, so this blocks a clean `/release` run even though none of the 15 is a correctness or security defect. 11 are auto-fixable.

### F-2.0-02: `harness/__init__.py`'s docstring contradicts the package it documents

Severity: low. Status: closed 2026-07-28 by the lead. Docstring rewritten to name all four modules built this phase (`harness.py`, `cost_control.py`, `coordinator_worker.py`, `cache.py`) as present and wired into `core/graph.py`, rather than describing them as future work.

### F-2.0-03: `build_stable_prefix()` has zero production callers

Severity: medium. Status: closed 2026-07-28 by the lead. `core/graph.py` now builds `_STABLE_PREFIX = build_stable_prefix()` once at import time and passes it as `cache_prefix` on every `call_tier` invocation via `_dispatch_tier_call`, so all four model-calling nodes (guardrail, think, plan, write) ship it. New test `test_every_model_call_carries_the_stable_prefix_as_its_leading_message` (`tests/system_03_search_agent/core/test_graph.py`) asserts the leading message on every mocked `litellm.acompletion` call is the exact stable-prefix string, so this is verified as actually reaching the model call, not just constructed and discarded. Full suite: 464 passed (up from 463), `ruff check` clean.

### F-2.0-04: nothing persists an `Interaction` row, so two of the four caps are inert

Severity: medium. Status: open. Owner: unassigned.

`grep -rn "Interaction(" src/` matches only the model definition at `data/models.py:154`. `get_user_daily_query_count` and `get_system_daily_cost_usd` read live from the `interactions` table on every check, which is exactly the restart-safety property T-2.0-03 was asked for, but no component ever writes a row. Both daily counters therefore return zero forever in production, and the per-user and system-wide caps cannot fire. T-2.0-03's module docstring explicitly scopes the write out ("a different component's job (the Write step, a later ticket)"), so this is a correctly-declared boundary rather than an oversight. Recorded because Section 25 calls for "cost caps and the cost event enforced from day one": the per-query cap and the per-step timeout are genuinely enforced end to end today, the two daily caps are wired but unfed.

### F-2.0-05: `done.total_cost_usd`, a real dollar figure, reaches the end-user response

Severity: low. Status: open, needs a product call rather than a code fix. Owner: unassigned.

The judge's live run produced `done` with `total_cost_usd: 0.00384` in the filtered, end-user-facing response. Section 19.5 states "No dollar figure ever reaches an end-user surface"; Section 19.3 states "The `done` event carries the final `query_cost_usd` as its terminal value, so a subscriber that misses intermediate cost events still gets the total". Those two sentences conflict, and `filter_events_for_end_user` drops only `cost`, so today Section 19.3 wins by default. No ticket criterion covers this, and `DonePayload.total_cost_usd` is a phase 1.0 contract field, so neither builder introduced it. Worth resolving at the Step 6.2 reconciliation rather than by a silent code change, since removing or zeroing the field on the end-user path is a contract-visible decision.

### F-2.0-06: `call_tier`'s internal retry does not re-run the pre-flight cap check

Severity: low. Status: open. Owner: unassigned.

Section 19.2: "A retried model call ... is a new billable event ... so its estimated cost is checked against the remaining per-query budget before it is allowed to fire." `check_per_query_cap` runs once in `graph.py:191`, before `call_tier` is entered; the retry at `harness.py:332-333` fires inside `call_tier` with no fresh check. Benign in the current design, because a failed first attempt records zero cost, so the retry's projection is identical to the one already approved. It stops being benign the moment a partially-billed failure mode exists (a streamed response that errors mid-completion, for example). Worth closing when retry policy is next touched.

## History

- 2026-07-28 lead: phase opened, dependency verified against Section 25 and `tracker/BOARD.md`, LEARNINGS.md read filtered to this phase, decomposed into 8 tickets (T-2.0-01 through T-2.0-08), all refined at creation
- 2026-07-28 judge: reviewed all 8 tickets with fresh context against the real code and real test runs, not the builders' self-reports. All 8 pass; every one moved to `done`. Full suite `python3 -m pytest tests/ -q` -> 463 passed, against a 314-passed baseline on `main`. Phase-level premise verified separately from the per-ticket check, per `goal-contracts.md` and the bossman-mode judge section: the judge wrote and ran its own integration harness that imports `core.run.run`, mocks only LiteLLM, and drives a real query to completion. Section 25 row 2.0's four named deliverables are all present and genuinely wired together, not merely unit-tested in isolation. Six findings filed (F-2.0-01 through F-2.0-06), none blocking, all for the lead to dispatch. One false evidence claim corrected in T-2.0-07's Evidence block
- 2026-07-28 lead: closed F-2.0-01 (lint), F-2.0-02 (stale docstring), and F-2.0-03 (`build_stable_prefix` unwired), each with evidence in its own Findings entry above. Left F-2.0-04 and F-2.0-06 open as documented, correctly-scoped boundaries (no code change due). Left F-2.0-05 open, surfaced to the product owner as a genuine Section 19.3/19.5 spec conflict needing a Step 6.2 call, not a unilateral code fix. Full suite after fixes: 464 passed (463 plus one new test proving the F-2.0-03 fix), `ruff check src/system_03_search_agent/ tests/system_03_search_agent/` clean
