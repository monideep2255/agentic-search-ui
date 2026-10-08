# R-10 and card 72: builder report

Built 2026-09-29 on `fix/card72-r10-guardrail`, cut from develop `beaccf36`. One builder, no dispatched agents. Every model is stubbed in every test; no live model or provider was called. Paths are relative to `<repo-root>`, under `src/system_03_search_agent/` unless they start with `tests/` or `docs/`.

## Table of contents

- [What a person notices](#what-a-person-notices)
- [Commits](#commits)
- [Acceptance, line by line](#acceptance-line-by-line)
- [The eight flags](#the-eight-flags)
- [Break-it results](#break-it-results)
- [Gates](#gates)
- [Not closed, and choices the lead should see](#not-closed-and-choices-the-lead-should-see)

## What a person notices

- In a slow spell of the guard model, a search gets past the screening step in about 4 to 7 seconds instead of failing at 15 with "A step in this query hit a temporary error". On a normal day nothing changes.
- A question Jev judges on topic is no longer turned away because the server paused for a second.
- When the provider rate-limits the screening call, the person is told to try again in about the number of seconds the provider named, not "Retrying the query may succeed".
- Nothing the person sees changes in how a question is admitted or refused otherwise: no verdict is still no answer, and Jev can still only add a refusal.

## Commits

| Commit | Subject |
|---|---|
| `29b53b0c` | fix(harness): every Jev reply that cannot be used is charged one cent, and the log says so |
| `dc1ab2bd` | fix(guardrail): a question Jev judges on topic is no longer refused because the server paused |
| `4449b74a` | fix(harness): a model call can be limited to one request, and names the host that answered |
| `26a47145` | fix(guardrail): a slow screening call gets a second request at 4 s instead of failing the search |
| `78b12c84` | docs: the debugging guide says an unusable Jev reply is charged one cent |

## Acceptance, line by line

### R-10, line 1: a Jev decision that failed says so; the guardrail acts on the signal, never on the clock

- Commit: `dc1ab2bd`.
- Code:
  - `harness/decide.py:401`, `decide(..., jev_failed=...)`: set at `:493` the moment Jev fails, before the guard tier is asked, and at `:469` at once with the guard provider.
  - `core/graph.py:1947` `_relevancy_decision` passes the event; `core/graph.py:1956` `_await_jev_own_pick` waits on the decision, the event or the step's deadline, nothing else. `_JEV_OWN_PICK_WINDOW_S` and `_jev_own_pick_deadline` are gone.
- Tests, `tests/system_03_search_agent/guardrail/test_followup_guardrail.py`:
  - `test_decide_says_jev_failed_before_it_asks_the_guard_tier`, `test_decide_never_says_jev_failed_when_jev_picked`, `test_with_the_guard_provider_decide_says_at_once_that_jev_will_not_pick`.
  - `test_with_jev_a_stalled_loop_never_turns_jevs_admission_into_a_refusal`: FA03's shape through the real `decide()`, a 1.0 s blocking stall before Jev's request and a reply 2.9 s after it, admitted at about 3.9 s.
  - R-06's arms kept, now on the signal: the refusal Jev's failure makes certain still returns at once.
- Status: closed.

### R-10, line 2: a guard classifier that answers inside 15 s on a later attempt admits the question

- Commit: `26a47145`.
- Code: `core/graph.py:1648` `_classify_within_budget`. The second request goes out as a hedge at 4 s, or earlier after a failure, and the backoff is capped at the hedge point (`core/graph.py:1584`), so it never takes time from the second request.
- Tests: `test_a_slow_failure_then_a_slow_answer_is_admitted` (FJ11's shape on the real budget: a 503 at 9.8 s, the second answering 9.5 s after it was sent, admitted at about 13.5 s), `test_a_quick_error_never_backs_off_past_the_hedge_point`, `test_the_backoff_never_passes_the_hedge_point`.
- Status: closed. One boundary, stated rather than hidden: a provider that fails TWICE and would answer on a third request is no longer served, because card 72 caps the classifier at two requests. `test_two_transient_errors_are_the_limit` pins that.

### R-10, line 3: every Jev reply that reached the provider is charged between one cent and `MAX_JEV_COST_USD`, and the log names the amount

- Commit: `29b53b0c`.
- Code: `harness/jev_client.py:239` `_unusable_reply` is the one place an unusable reply's charge is fixed, always `MAX_JEV_COST_USD` ($0.01), with one warning "could not be used: ...; it is charged $0.01". The body is read by base class (`:275` and the two parse arms at `:470` and `:649`). `_reported_cost_usd` (`:214`) now only reads and never logs.
- Tests: `tests/system_03_search_agent/harness/test_jev_followup_costs.py` covers every shape at `call_jev` and `call_jev_batch`: cost too large for a float, confidence or probability too large, confidence a string, out of range with cost 0, `probabilities` null, a list or a string, a body nested too deep, not JSON, empty, not text. The same shapes plus an option outside the set are checked at all three charge sites on a real `Harness`: `decide`, `_jev_injection_pick` and `sentence_check._ask_jev`. `tests/system_03_search_agent/harness/test_jev_cost_bounds.py` covers the two helpers.
- Status: closed, under the reading in the last section: an UNUSABLE reply is charged exactly one cent, and a usable one the cost it states.

### R-10, line 4: at most two requests to a rate-limited guard model, Retry-After honoured from either request, and "try again later" when it does not fit

- Commits: `4449b74a` (`harness/harness.py:598` `retry=False` and `:677`: one request per call) and `26a47145` (`core/graph.py:1467` `_CLASSIFIER_MAX_REQUESTS = 2`, `:1597` `_rate_limited_step_error`, `:866` the messages).
- Tests:
  - `test_a_rate_limit_storm_costs_two_requests_and_says_to_wait`.
  - `test_a_retry_after_that_does_not_fit_says_when_to_come_back`: one request, "in about 20 seconds, not straight away", `retry_after_s: 20`.
  - `test_a_retry_after_is_honoured_whichever_request_carried_it`, three arms.
  - The `no_path_passes_the_budget` arms assert at most 2 requests and at most 2 in flight on every failure shape.
  - `tests/system_03_search_agent/harness/test_harness.py::test_retry_false_sends_exactly_one_request`.
- Status: closed for the guardrail's classifier call. See the last section for the relevancy decision's guard fallback.

### Card 72, option A: the hedged request

- Commit: `26a47145`. Code: `core/graph.py:1460` `_CLASSIFIER_HEDGE_AFTER_S = 4.0` and `:1648` `_classify_within_budget`. The hedge is sent at `:1758` without cancelling the first. The first usable reply returns. The loser is cancelled in the `finally` arm and awaited, so `call_tier`'s cancellation charge lands before the cost event.
- Tests:
  - `test_a_first_request_that_hangs_gets_a_hedge_at_four_seconds`: admitted at 4.8 to 5.8 s. The hung first request is cancelled and charged the cancelled-call estimate.
  - `test_a_first_reply_at_six_seconds_wins_and_the_hedge_is_cancelled`: the hedge is cancelled and charged the same way.
  - `test_both_requests_slow_past_the_budget_give_todays_step_error`: the real 15 s, today's exact step error.
  - `test_with_jev_a_classifier_that_never_answers_is_never_an_admission`, and in `test_reland_guardrail.py` `test_with_jev_two_failed_attempts_are_never_an_admission`: no verdict is no answer, and Jev never stands in.
  - `test_a_slow_first_reply_is_no_longer_thrown_away`.
- Status: closed. Option F is not built: nothing admits without a classifier verdict.

### Card 72, D's logging

- Commits: `4449b74a` (`harness/harness.py:158` `_upstream_provider`, read from OpenRouter's `provider` field, bounded to 64 printable characters, on `LLMResponse.upstream_provider`) and `26a47145` (`core/graph.py:1624` `_log_guard_request`).
- The line: "guard classification request N of 2 (trace ...): <outcome> after X.XXs, upstream <host or not named>". There is one per request, cancelled ones included.
- It goes out at WARNING on purpose. The service configures no logging of its own, and the only configuration on develop is alembic's, applied in-process at start-up, which sets the root level to WARN. An INFO line would never reach develop's log.
- Tests: `test_the_log_names_each_requests_time_and_upstream_host_and_nothing_private` asserts the level, the host, "not named", the trace id, and that neither the key nor the question's text appears. The harness arm is `test_the_upstream_provider_openrouter_names_is_on_the_reply`.
- Status: closed.

### Card 72, line 4: nothing else changes

- Unchanged: the 15 s budget (`budget_for_step`), the guard model, `MAX_JEV_COST_USD`, every cost cap, and `_CLASSIFIER_RETRY_BACKOFF_S` and `_CLASSIFIER_MIN_SECOND_ATTEMPT_S`.
- `call_tier`'s default keeps both retries for every other caller (`test_the_default_still_retries_a_transient_error_once`).
- No event contract change.

## The eight flags

| Flag | Status | Where |
|---|---|---|
| FA03 | closed | `dc1ab2bd`; the guardrail waits on `decide()`'s signal, not a 3.75 s window |
| FJ11 | closed | `26a47145`; the hedge at 4 s and the capped backoff |
| FJ01 | closed | `29b53b0c`; parse by base class, every unusable body charged $0.01 |
| FA01 | closed | `29b53b0c`; `_json_payload` catches `RecursionError` by base class |
| FJ03 | closed | `29b53b0c`; the one warning is written where the charge is fixed and names it |
| FJ04 | closed, classifier call | `4449b74a` and `26a47145`; two requests at most |
| FA02 | closed | `26a47145`; "try again in about N seconds", `retry_after_s` N |
| FA05 | closed | `26a47145`; every request's `Retry-After` read |

Also closed by the same change, though not in the list: FJ02 (a malformed reply stating $0 was charged $0), and the rate-limit half of FJ05 (the step error said to retry now).

## Break-it results

Each control was broken once, the named tests run, and the file restored byte for byte. Every "restored" check printed True, and `git status` was clean of the mutation after each.

| # | Mutation | Red |
|---|---|---|
| M1 | `call_jev`'s parse arm back to the old list of error types | 10 (the `probabilities` shapes at `call_jev`, `decide`, the injection pick) |
| M2 | `_json_payload` back to `except ValueError` | 6 (the deep body at every site) |
| M3 | an unusable reply charged $0.00002 | 49 |
| M4 | R-06's clock again: the wait ends 3.75 s after the decision began | 1 (the stalled-loop arm) |
| M5 | `decide()` never sets `jev_failed` | 1 |
| M6 | `call_tier` ignores `retry=False` | 3 |
| M7 | `upstream_provider` never read | 3 |
| M8 | the classifier calls `call_tier` with `retry=True` | 2 |
| M9 | the hedge at 10 s, R-01's cut | 1 |
| M10 | the first request cancelled when the hedge is sent | 1 |
| M11 | a rate limit ends in R-05's "retry now" step error | 5 |
| M12 | the backoff ignores the hedge point | 4 |
| M13 | three requests allowed | 9 |
| M14 | a `Retry-After` read only from the second request | 1 |
| M15 | no log line for an answered request | 1 |
| M16 | the hedge never sent | 1 |
| M17 | any unusable reply decides the step error's words | 1 |

One mutation needed a second try: M4 first counted the 3.75 s from when the guardrail began waiting, which comes after the stall, and stayed green. Counted from the decision's start, as R-06 did, it went red.

## Gates

All run on `78b12c84`, each polled until it exited.

| Gate | Command | Result |
|---|---|---|
| Unit suite, as `.github/gates/gate04_unit_suite.sh` runs it | `pytest -m "not integration" -q -rs` | 6599 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0, 304 s |
| Lint | `ruff check .` | All checks passed |
| Import order, as `.github/gates/gate02_import_order.sh` runs it | `isort --check-only --diff src tests services tracker alembic .claude .github` | clean, exit 0 |
| Doc structure | `tracker/check_doc_drift.py --check` | 0 stale, 0 structural |
| Touched tests | `tests/system_03_search_agent/guardrail/`, `harness/`, `synthesis/test_sentence_check.py` | guardrail 367 passed; harness and sentence check 844 passed before the hedge, all inside the suite run above |

## Not closed, and choices the lead should see

- The charge reading for R-10 line 3. "Between one cent and `MAX_JEV_COST_USD`" names a single value, since the ceiling is one cent. I read it as: every reply that cannot be used, whatever its shape, is charged exactly one cent; a usable reply is still charged the cost it states. Charging usable replies a cent would put about 5 to 7 cents per question on the accumulator against the $0.10 per-query cap.
  - The trade-off to weigh: if Jev's alpha endpoint ever drifts to a shape the parse rejects on every reply (for example `"probabilities": null`), each Jev call costs a cent on the cap, about 5 to 7 cents per question before the answer models. That is the same exposure a garbage-body outage already had under R-07.
  - To revert to "charge the stated amount", change one line in `_unusable_reply`.
- Rate limits outside the classifier call. The relevancy decision's guard-tier pick (`harness/decide.py`'s `_run_guard_pick`) still uses `call_tier`'s default immediate retry. With the guard provider, a question that misses the biomedical allowlist can still send the rate-limited guard model 2 more requests, 4 in all. Moving it to `retry=False` changes every `decide()` point, which the brief puts out of bounds ("every other step untouched"). Not closed; named.
- Reasoning fallback on the classifier call. With `retry=False`, a guard model that refused `reasoning: {"effort": "none"}` would fail the classifier rather than resend without it. Today's guard model accepts it, so nothing changes today. A future guard model change is the owner's.
- `_JEV_WAIT_S`, `decide()`'s outer net for Jev, is still counted from the decision's start. A stall of more than half a second between the start and Jev's request can make Jev report a timeout of its own. The guardrail then acts on that signal, as line 1 asks, but Jev's pick is lost. Changing that net is a budget value, so it is left alone.
- Files outside the fence, forced by the charge rule:
  - `tests/system_03_search_agent/synthesis/test_sentence_check.py`: one pinned charge, $0.004 to the ceiling, and its docstring.
  - `synthesis/sentence_check.py`'s docstring and comment still say an unusable reply is "charged its reported cost". It is a source file outside the fence, so it is not edited; the words are now stale.
- Test time: four of the new arms run on the real 15 s budget (about 5, 6, 15 and 13.5 s).
