# Card 84: R-10's sound parts, builder report

Built 2026-09-29 on `fix/card84-r10-sound-parts`, cut from develop `d9e05c4e`. One builder, no dispatched agents, nothing pushed. Every model and Jev reply is stubbed in every test; no live model or provider was called. Paths are relative to `<repo-root>`, under `src/system_03_search_agent/` unless they start with `tests/`, `frontend/` or `docs/`. Line numbers are as of the last code commit, `48d5c24c`.

## Table of contents

- [What a person notices](#what-a-person-notices)
- [Commits](#commits)
- [Reused from the parked branch](#reused-from-the-parked-branch)
- [Acceptance line 1, corrected](#acceptance-line-1-corrected)
- [Acceptance, line by line](#acceptance-line-by-line)
- [The sweep](#the-sweep)
- [Break-it results](#break-it-results)
- [Gates](#gates)
- [Not closed, and choices the lead should see](#not-closed-and-choices-the-lead-should-see)

## What a person notices

- No screening reply ever races another. A question is judged by one reply at a time, so an off-topic question is never admitted because a second reply to it came back faster (card 72's V08 cannot happen).
- Whenever the screening model fails without rate-limiting, the person gets exactly what develop gave them, at the same moment: the same retries, the same waits, the same answer (card 72's V06 is gone, and R-05's one-second blip is still outlasted).
- A screening request that fails slowly, followed by one that would answer inside the 15 seconds, still fails at 15 s, as on develop (FJ11 is open again; see the corrected section).
- A question Jev judges on topic is not refused because the server paused where the judge put the pause, or anywhere else in Jev's wait up to 2 s of pause (FA03).
- When the screening model is rate-limited and says how long to wait, the web app says "Try asking again in about N seconds"; when it says nothing, "Wait a little, then try asking again", never "in a moment".
- The one thing a person could lose: a search whose screening call was rate-limited, since such a call now sends two requests at most and waits when the provider says to, where develop sent up to four at once.

## Commits

| Commit | Subject |
| --- | --- |
| `ec1984b3` | fix(harness): a Jev reply is never charged $0 or a whole cent, and a server stall no longer times Jev out |
| `c2ee7f3d` | fix(guardrail): a question Jev judges on topic is no longer refused because the server paused |
| `c1091c84` | fix(harness): a guard model call can be held to one request, still resends without the reasoning setting, and names the host that answered |
| `f5b06193` | fix(guardrail): the screening step sends at most two requests, one after the other, and never loses or slows a search develop answered within two |
| `c863f226` | fix(harness): a Jev reply with an error status is charged the small floor, never $0 |
| `1e1aab4a` | fix(harness): Jev never takes a question past its cost cap, even two calls at once or the sentence check |
| `d5f091e9` | fix(web-ui): a rate-limited search says how many seconds to wait, and to wait a little when no wait is known |
| `48d5c24c` | docs: the debugging guide says how a Jev reply is charged and how a screening call sends its requests |
| `ed0f5299` | docs: card 84's builder report |
| `3e33c995` | fix(guardrail): screening keeps develop's retries for every failure but a rate limit, so no search develop answers is lost or slowed |
| `f1b5828e` | docs: the debugging guide says screening keeps develop's retries and caps only a rate-limited call |

## Reused from the parked branch

From `fix/card72-r10-guardrail`, nothing of the hedge:

- `29b53b0c` and `ea7be3f0`, applied together as `ec1984b3`: Jev's charge rule (`jev_charge_usd`, `JEV_FLOOR_COST_USD`, `_unusable_reply`), `check_jev_per_query_cap`, and `wait_counting_free_time` for every Jev clock. The first commit's "one cent" subject was superseded by the owner's floor, so the two went in as one commit under the second's subject.
- `dc1ab2bd` as `c2ee7f3d`: `decide(..., jev_failed=)` and `_await_jev_own_pick`.
- The stall and mid-wait arms of `c263c159` and `a186b558`, with `tests/system_03_search_agent/virtual_clock.py`, copied by hand into `c2ee7f3d`.
- `4449b74a` and `ac3a471f` as `c1091c84`: `call_tier(retry=False)` keeping the reasoning fallback, and `LLMResponse.upstream_provider`. One docstring sentence about "a hedge" was reworded.
- `7c028486`'s `useRunView` branch and test, adapted in `d5f091e9` (transient errors only, and the no-wait line changed).
- Not reused: `26a47145` and everything in `c263c159` built on the hedge: its racing `ask_guard_model`, `second_request_at`, the stricter-reply ranks and its sweep. `ask_guard_model` on this branch is new code under the same name.

## Acceptance line 1, corrected

The lead corrected line 1 on 2026-09-29. R-10 caps only a RATE-LIMITED guard model at two requests, so:

- A rate-limited call: at most two requests, a stated `Retry-After` honoured.
- Every other failure: develop's behaviour exactly, its third and fourth requests and its timing included.
- Always: never two requests in flight, and no hedge.

This section supersedes what the sections below say about:

- Line 1 and FJ11.
- The sweep's counts.
- Break-its M1 to M4, M8, M14, M15 and M21.

### What changed

- Commit `3e33c995`. `harness/decide.py` `ask_guard_model` now runs develop's policy request for request: `attempts` attempts (2 for the classifier, 1 for a guard pick), the first cut at `first_share` of the budget, an immediate resend of a transient error inside each attempt, and R-05's backoff between attempts (`GUARD_RETRY_BACKOFF_S`, `_attempt_wait_s`), with the cap pre-flight once per attempt.
- The rate-limit rule overlays it: once any request meets a 429, no further request goes unless it is the second in all (`GUARD_RATE_LIMITED_MAX_REQUESTS = 2`); a stated `Retry-After` is waited out first, or ends the call when it would leave less than 3 s; that last request keeps all the rest of the budget.
- Each request is still one `call_tier(retry=False)` in its own `enforce_timeout`, so a 429 is seen on the request that carried it; one request at a time.
- The log line now reads "N requests" rather than "N of at most 2".

### FJ11 is open again

- R-10 line 2 (FJ11) was closed by giving the resend all of the 15 s instead of cutting it at the first attempt's 10 s. That changes develop's timing: whenever the resend hangs and develop's third request, sent at 10 s, would answer, the question is lost. Measured, the rejected variant (break-it C4) turns the sweep red on exactly those cases.
- No policy can both admit FJ11's shape and keep develop's timing, so under the corrected line 1 FJ11 stays as on develop. `test_followup_guardrail.py::test_fj11_stays_as_on_develop_a_slow_failure_then_a_slow_answer_fails` pins it: a 503 at 9 s, a resend cut at 10 s, a third request at 10 s, the step error at 15 s.
- This is the lead's or the owner's call: FJ11 closed with the losses above, or FJ11 open.

### The sweep, rerun

- Classifier, 10,306 cases (the same grid): develop answered 5,940. 4,872 were answered without a 429 on develop, and every one of them is answered here with the same requests, the same verdict, at the same moment: 0 lost, 0 later, 0 different.
- The 1,068 cases develop answered after meeting a 429 are the only ones that differ: 630 lost, 210 the same but later, 216 the same and no later, 12 a different verdict (6 admitting where develop refused, 6 refusing where develop admitted; each is the reply to a request develop sent where this branch waited as the provider asked, or never sent).
- No case had two requests in flight, passed its budget, or sent a request after a 429 other than as the second in all.
- Pick, 280 cases: develop picked 150; 132 were picked without a 429, all held; the 18 rate-limited ones: 6 lost, 6 later, 6 the same.
- R-05's RJ08 blip is answered on the third request as on develop (`test_the_sweep_reports_what_the_cap_gives_up`, `test_an_error_lasting_about_a_second_is_outlasted_as_on_develop`).
- The develop port behind the sweep is unchanged, and was checked case for case against develop's real code at `d9e05c4e` (10,306 and 280 identical).

### Tests changed

- `test_guard_request_dominance.py`: the check is now "every case develop answered without a 429: same requests, same verdict, same moment"; `test_a_rate_limited_call_never_sends_a_third_request` replaces the old third-request test.
- `test_followup_guardrail.py`: the FJ11 pin above; the RJ08 blip arm; `test_no_verdict_is_no_answer_and_no_path_passes_the_budget` now asserts the exact request count for 13 shapes (develop's four for errors every time, two once rate-limited); the unusable-then-error arm expects develop's three requests; the log line's wording.
- `test_reland_guardrail.py`: `test_a_transient_error_twice_then_a_verdict` is back (connection errors, three requests, admitted), beside `test_a_rate_limited_call_stops_at_two_requests`.

### Break-it, rerun

The same byte-for-byte runner (`b84/mutate2.py`), every run `restored=True`, `git status` clean after.

| # | Mutation | Red |
| --- | --- | --- |
| C1 | a rate-limited call allowed three requests | 2 |
| C2 | no backoff between attempts (RJ08) | 3 |
| C3 | no resend inside an attempt | 14 |
| C4 | the resend keeps all 15 s (the old FJ11 fix) | 3 |
| C5 | one attempt for the classifier | 24 |
| C6 | a stated wait ignored | 3 |
| C7 | an unusable reply ends the call | 5 |
| C8 | the classifier on `call_tier`'s own retry | 24 |
| C9 | the wait read only from the first request | 1 |
| C10 | no upstream host in the log line | 1 |
| M5, M6, M7 | Jev's clocks, the signal ignored, the signal never set | 3, 1, 1 |
| M9 to M13 | Jev charges and the cap pre-flight | 4, 4, 2, 1, 6 |
| M16, M17, M18 | the rate-limit wording | 9, 3, 4 |
| M19, M20 | the pick on `call_tier`'s retry, the reasoning fallback | 2, 3 |
| M23, M24 | the web app (vitest, unchanged code, from the first round) | 2, 1 |

### Gates, rerun

On `f1b5828e`, each polled until it exited.

| Gate | Command | Result |
| --- | --- | --- |
| Unit suite, as `.github/gates/gate04_unit_suite.sh` runs it | `pytest -m "not integration" -q -rs`, CI's placeholder settings, with `USER_DB_URL` pointed at this machine's own PostgreSQL role (its database has no `postgres` role, which CI's service creates) | 6667 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0, 393 s |
| Touched tests | `tests/system_03_search_agent/guardrail/`, `harness/`, `core/test_graph.py`, `synthesis/test_sentence_check.py` | 1144 passed, 6 skipped |
| Frontend tests | `npx vitest run` in `frontend/`, `node_modules` linked for the run and unlinked after | 59 files, 490 tests passed, exit 0 |
| Lint | `ruff check .` | All checks passed |
| Import order, as `.github/gates/gate02_import_order.sh` runs it | `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |
| Doc structure | `tracker/check_doc_drift.py --check` | 0 stale, 0 structural |

## Acceptance, line by line

### 1. No hedge; develop's sequential policy; never lost and never slower

- Commit: `f5b06193`.
- Code: `harness/decide.py:392` `ask_guard_model`, used by the classifier (`core/graph.py:1857`) and by every guard pick (`harness/decide.py:532` `_run_guard_pick`, so the relevancy decision's pick and Think's and Plan's too). `GUARD_MAX_REQUESTS = 2` (`decide.py:254`). One request at a time: each is `enforce_timeout` around `call_tier(retry=False)`.
- The policy is develop's own request sequence cut at two. Request 1 runs to two thirds of the budget for the classifier (R-01, unchanged), to the pick's own 15 s for a pick. The second goes: at once after an error (when develop's `call_tier` sent its resend), at the cut after a hang, at once after an unusable classifier reply. It keeps all the rest of the budget. A stated `Retry-After` is waited out first (line 5).
- Tests: `tests/system_03_search_agent/guardrail/test_guard_request_dominance.py`, the sweep below; `test_followup_guardrail.py::test_an_error_is_followed_at_once_as_on_develop` (V06: admitted at 0.65 s, as develop), `test_a_first_request_that_hangs_gets_its_second_at_ten_seconds`, `test_no_verdict_is_no_answer_and_no_path_passes_the_budget` (11 shapes: at most 2 requests, peak 1 in flight, never past 15 s).
- Status: closed for every search develop answered within its first two requests. NOT closed, and cannot be with two requests, for searches develop answered on its third or fourth request, and for a stated wait develop ignored. Counted, and the trade stated, in the sweep and the last section.

### 2. R-10 line 1, FA03, including where the judge put the stall

- Commits: `ec1984b3` (`harness/jev_client.py:324` `wait_counting_free_time` on Jev's own bound, `decide()`'s net and the injection net), `c2ee7f3d` (`decide()` sets `jev_failed` at `decide.py:866` and `:890`; `core/graph.py:1567` `_await_jev_own_pick` waits on it, never a clock).
- Tests, `test_followup_guardrail.py`: `test_with_jev_a_stall_anywhere_in_jevs_wait_never_turns_its_admission_into_a_refusal`, six arms on the virtual clock through the real `decide()`: 1.0 s where the builder put it, 0.6 s and 0.8 s in the cap check where the judge put it, 0.6 s and 1.0 s while the reply is read, 0.6 s just before it arrives. `test_with_jev_a_failure_signalled_mid_wait_ends_the_wait_at_once` (J07), `test_decide_says_jev_failed_before_it_asks_the_guard_tier`.
- Status: closed up to `JEV_STALL_ALLOWANCE_S` (2 s of pause on top of Jev's 3 s, `jev_client.py:321`). A longer pause still ends Jev's clock; see the last section.

### 3. R-10 line 2, FJ11

- Commit: `f5b06193`. Code: `decide.py:452`, the second request's budget is all that is left, not the first request's share.
- Test: `test_a_slow_failure_then_an_answer_inside_the_budget_keeps_the_question` (a 503 at 9 s, the second answering 5.5 s after it is sent, admitted at 14.5 s; develop failed it at 15 s).
- Status: OPEN since the correction; see "Acceptance line 1, corrected".

### 4. R-10 line 3 as amended: every reply charged, never past the cap

- Commits: `ec1984b3` (the rule), `c863f226` (V03: `jev_client.py:498`, a non-200 reply is charged `JEV_FLOOR_COST_USD`), `1e1aab4a` (V02 and J09: `decide.py:620` `jev_charge_reserved`, wrapped around the call and the charge at all three sites, `decide.py` `_run_jev_pick`, `core/graph.py:1523` and `synthesis/sentence_check.py:366`).
- Tests, `tests/system_03_search_agent/harness/test_jev_followup_costs.py`: every unusable shape at every site charged the floor; `test_a_usable_reply_is_charged_its_sensible_cost_or_the_floor_at_every_site`; `test_a_reply_with_another_status_is_charged_the_floor_at_every_site` (500, 429, 402); `test_a_call_no_reply_came_back_from_is_charged_nothing`; `test_no_jev_charge_takes_a_question_past_its_cap`; `test_two_jev_calls_checked_at_once_never_pass_the_cap` (V02, from $0.085 and $0.089 of $0.10); `test_the_hold_is_let_go_once_the_charge_lands`; `test_the_sentence_check_checks_the_cost_it_can_be_charged` (J09, from $0.0965).
- Status: closed for Jev charges against Jev pre-flights. A guard-tier call's own pre-flight does not count what Jev holds; see the last section.

### 5. R-10 line 4: rate limits

- Commits: `f5b06193` (backend), `d5f091e9` (web app).
- Code: a stated wait is read from every request, the later one winning (`decide.py:472`), and waited out when it leaves the second request 3 s (`decide.py:480`); otherwise the call ends at once. `core/graph.py:1465` `_rate_limited_step_error`: "in about N seconds, not straight away", "about 1 second" for one, `retry_after_s` N; "Wait a little before trying the query again." when no wait was named; "was busy a moment ago. Try the query again." when the named wait has already passed (J04). Web app: `frontend/src/hooks/useRunView.ts:1218`, a transient error's `retry_after_s` read into "Try asking again in about N seconds", and `:1202`, the transient line "Wait a little, then try asking again." (V05).
- Tests: `test_a_rate_limit_storm_costs_two_requests_and_says_to_wait`, `test_a_providers_retry_after_is_honoured_when_it_fits`, `test_a_retry_after_that_does_not_fit_says_when_to_come_back`, `test_a_retry_after_is_honoured_whichever_request_carried_it` (5 arms), `test_the_rate_limit_message_counts_seconds_in_words` (10 values), `test_a_rate_limit_storm_gives_each_guard_call_two_requests`, `test_the_relevancy_pick_honours_a_retry_after`; `frontend/src/hooks/useRunView.retryAfter.test.ts` (5 cases).
- Status: closed per guard call, as the line says.

### 6. J08

- Commit: `c1091c84`. Code: `harness/harness.py:683`, `retry=False` turns off only the transient resend.
- Tests: `tests/system_03_search_agent/harness/test_harness.py::test_retry_false_still_resends_without_the_reasoning_block`, `test_retry_false_takes_the_reasoning_fallback_once_and_no_transient_retry`; `test_followup_guardrail.py::test_a_guard_model_that_cannot_turn_reasoning_off_still_screens`.
- Status: closed.

### 7. Logging

- Commits: `c1091c84` (`harness.py:158` `_upstream_provider`), `f5b06193` (`decide.py:511` `_log_guard_call`).
- One WARNING line per guard call, for example: "guard call guard classification (trace t-...): answered after 10.20s in all, 2 of at most 2 requests; request 1: cut at its budget after 10.00s; request 2: answered after 0.20s, upstream DeepInfra". Failed requests name the error class and the provider exception's type name only. WARNING because develop's only logging configuration sets the root to WARN.
- Test: `test_each_guard_call_logs_its_time_and_upstream_host_and_nothing_private` (exact line; no key, question, prompt text or line break; the host cut to 64 characters).
- Status: closed.

### 8. The debugging guide

- Commit: `48d5c24c`. The `jev_client` row now states the owner's rule (V04), and the `decide`, `harness` and `useRunView` rows name what this card added.
- Status: closed.

### 9. Unchanged

- The 15 s guardrail budget and R-01's two-thirds share (`test_the_first_request_keeps_two_thirds_and_the_budget_is_unchanged`), the pick's `_GUARD_BUDGET_S`, the guard model, `MAX_JEV_COST_USD` and every cap value, `JEV_TOTAL_TIMEOUT_S`. No file under `contracts/` or `frontend/src/lib/events.ts` changed; `retry_after_s` stays `int, ge=0`.
- R-05's `_CLASSIFIER_RETRY_BACKOFF_S` is gone: under a two-request cap it only ever timed develop's third request.

## The sweep

The counts in this section are the first build's, before the correction; the rerun's are in "Acceptance line 1, corrected".

File: `tests/system_03_search_agent/guardrail/test_guard_request_dominance.py`.

- Yardstick: develop's classifier policy and develop's `_run_guard_pick`, ported line for line. The port was checked against develop's REAL code: `git archive d9e05c4e src` into the scratch folder, the real develop `guardrail_node` run over the same grid, and compared case by case. Classifier: 10,306 of 10,306 identical (verdict, time, request count). Pick: 280 of 280 identical.
- The new policy runs through the REAL guardrail node and the real `_run_guard_pick`, on the virtual clock, with the real 15 s budget and a 12 s one.
- Grid, varying timings AND verdicts: every ordered triple of 17 per-request behaviours (admit, injection or off topic after 0.3, 6 or 12 s; unusable; a 503 after 0.05 or 9 s; a 429 with no wait, a 2 s wait or a 13 s wait; a refused key; a hang), plus 240 providers whose reply changes with the time a request is sent (for example a slow off-topic before 3 s and a fast admission after). 5,153 providers at two budgets: 10,306 cases. The pick: 280 cases.
- Result, classifier: develop reached a verdict in 5,940 cases. In 4,923 the new policy reached the same verdict, no later. No case had more than 2 requests, 2 in flight, or passed its budget. The other 1,017 are only these two classes:
  - Develop's verdict came on its third or fourth request (609): lost 570; same verdict 21 (9 of them later); a different verdict 18, of which 6 admit where develop refused and 6 refuse where develop admitted. Those 12 are the second request's own reply, which develop cut at 10 s and then asked a third time; it is one reply read, not a race.
  - A request before develop's verdict stated a `Retry-After` develop ignored (408): lost 204, same but later 204.
- Result, pick: develop picked in 150 cases; 138 held; the 12 others all stated a wait (6 lost, 6 later).
- Not vacuous: `test_the_sweep_catches_a_hedge` (card 72's V08 shape reported as two in flight and "develop off_topic, new ok"), `test_the_sweep_catches_a_backoff_after_an_error` (V06: "develop 0.35s, new 2.35s"), `test_the_sweep_catches_a_second_request_cut_at_the_first_share`. Mutations M1 to M4, M14 and M19 below also turn it red.
- The sweep runs in about 7 s.

## Break-it results

How each control was broken:

- Runner: the session scratchpad's `b84/mutate.py`, one mutation at a time in the worktree.
- Restore: the file's original bytes written back after each run and compared by SHA-256. Every run printed `restored=True`.
- After all runs, `git status` was clean.

| # | Mutation | Red |
| --- | --- | --- |
| M1 | three requests allowed | 18 |
| M2 | a 2 s backoff after an error (V06) | 11 |
| M3 | the first share applied to the second request (FJ11) | 5 |
| M4 | the classifier on `call_tier`'s own retry | 25 |
| M5 | Jev's clocks count real time (FA03) | 3 |
| M6 | the wait ignores Jev's failure signal (J07) | 1 |
| M7 | `decide()` never says Jev failed | 1 |
| M8 | no second request after an unusable reply | 2 |
| M9 | a stated $0 charged $0 | 4 |
| M10 | a non-200 reply charged nothing (V03) | 4 |
| M11 | the Jev pre-flight ignores what is held (V02) | 2 |
| M12 | the sentence check checks the guard estimate only (J09) | 1 |
| M13 | the Jev pre-flight checks the guard estimate only | 6 |
| M14 | a stated wait ignored | 3 |
| M15 | the wait read only from the first request | 1 |
| M16 | a rate limit ends in the generic step error | 9 |
| M17 | "seconds" for one and "not straight away" always (J04) | 3 |
| M18 | a passed wait still says to wait (J04 residual) | 4 |
| M19 | the relevancy pick on `call_tier`'s own retry (J05) | 2 |
| M20 | `retry=False` drops the reasoning fallback (J08) | 3 |
| M21 | no upstream host in the log line | 1 |
| M22 | the log's own cleaning of the host removed | 0 |
| M22b | both the log's and the harness's cleaning removed | 1 |
| M23 | the web app ignores `retry_after_s` (vitest) | 2 |
| M24 | "in a moment" again (vitest) | 1 |

M22 stays green because `harness._upstream_provider` already cleans the host. Each layer covers the other. Removing both turns the log test red (M22b).

## Gates

Each polled until it exited, on `48d5c24c`.

| Gate | Command | Result |
| --- | --- | --- |
| Unit suite, as `.github/gates/gate04_unit_suite.sh` runs it | `pytest -m "not integration" -q -rs`, CI's placeholder settings | 6663 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0, 274 s |
| Touched tests | `tests/system_03_search_agent/guardrail/`, `harness/`, `core/test_graph.py`, `synthesis/test_sentence_check.py` | 1135 passed, 6 skipped, inside the suite above |
| Frontend tests | `npx vitest run` in `frontend/` | 59 files, 490 tests passed, exit 0 |
| Frontend build | `npm run build` in `frontend/` | exit 0, the existing chunk-size warning only |
| Lint | `ruff check .` | All checks passed |
| Import order, as `.github/gates/gate02_import_order.sh` runs it | `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |
| Doc structure | `tracker/check_doc_drift.py --check` | 0 stale, 0 structural |

- The first run of the suite gave 6 failures, all "role \"postgres\" does not exist": this machine's PostgreSQL has no `postgres` role, which CI's service creates. The same 6 fail on develop's own code (`git archive d9e05c4e` into the scratch folder). With `USER_DB_URL` pointed at the local role, the two files (`core/test_think_retry.py`, `adapters/graphql/test_no_cost_channel.py`) pass 9 of 9 on this branch and on develop, and the whole suite is the clean run in the table.
- `frontend/node_modules` was linked to the main checkout's for the frontend runs only, never staged, and unlinked after (`ls` then says no such file).

## Not closed, and choices the lead should see

The first bullet is superseded by the correction: every failure but a rate limit now keeps develop's third and fourth requests, and FJ11 is open instead (see "Acceptance line 1, corrected").

- Line 1 cannot be met in full as written, and this is the owner's trade. "At most two requests per guard call" and "a search develop answers is never lost and never slower" contradict each other, because develop sends up to four requests. Proof in one case: when the first request fails at once, develop resends at once. If the provider is healthy again, only a resend at once is as fast as develop; if the error lasts about a second, a resend at once fails too and develop answers on its third request, after R-05's 2 s backoff. No two-request policy wins both. This build keeps "never slower" and identical verdicts for everything develop answered within two requests, and gives up develop's third and fourth requests: 609 of 5,940 answered cases in the sweep, 570 of them lost, including R-05's RJ08 blip (`test_the_sweep_reports_what_the_cap_gives_up`, and `test_reland_guardrail.py::test_two_transient_errors_are_the_limit`, which replaced a pin of develop's third request). The alternatives for the owner:
  - Keep this build.
  - Allow develop's third and fourth requests for errors that are not rate limits (line 1's cap then holds only for rate limits, as line 4 words it).
  - Send the second request no sooner than 2 s after the first was sent: keeps the blip, at up to 2 s slower than develop after a fast isolated failure.
- A stated `Retry-After` is honoured, as line 4 requires, where develop resent at once: 408 sweep cases differ, 204 lost. Only a provider that answers before its own stated wait loses anything.
- FJ11's longer second request means 12 sweep cases reach a different verdict from develop, 6 admitting where develop refused, all from the second request's own reply develop cut off. One reply decides, as on develop; it is not card 72's race.
- FA03 holds up to `JEV_STALL_ALLOWANCE_S` of pause. The fresh verifier's 2.4 s pause before Jev's request still refuses, as on the parked branch. Raising or removing the allowance changes what bounds a Jev call when the server keeps stalling (the sentence check has no other real-time bound), so it is left as it was.
- Line 4's cap: a guard-tier call's own pre-flight (`cost_control.check_per_query_cap`, outside the fence) does not count what Jev calls hold, so a guard call charged between a Jev pre-flight and that Jev call's charge can take a question past its cap by at most that guard call's cost. A Jev call that times out is charged nothing, by the decision's words ("a reply that reached the provider").
- Wider than the guardrail: `_run_guard_pick` serves every `decide()` point, so Think's and Plan's guard picks now also honour a stated `Retry-After`, where develop resent at once, and each writes the WARNING log line. Their timing is otherwise develop's.
- The web app's transient line changed for every transient error, not only rate limits: "Wait a little, then try asking again." A long wait still reads as a count of seconds (the backend caps it at a day); minutes were not added, since line 5 names seconds.
- A question the allowlist misses can still send four guard requests in a rate-limit storm, two for the classifier and two for the pick; line 4 is per guard call.
- No failure took over five minutes, so no `LEARNINGS.md` row was added.
