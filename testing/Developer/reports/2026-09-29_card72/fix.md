# R-10 and card 72: fix round

The single fix round after the judge (F-72-J01 to J11) and the adversary (F-72-A01 to A05), on `fix/card72-r10-guardrail`, 2026-09-29. One fix agent holding every finding, serially (Review_rounds Rule 1). Every model and Jev reply is a stub; no live provider was called. Paths are relative to `<repo-root>`, under `src/system_03_search_agent/` unless they start with `tests/`, `frontend/` or `testing/`.

Status: every finding fixed except one piece of F-72-J09 at the sentence check, which needs a line of code outside the fence and is recorded under "Open, and why". Nothing pushed.

## Table of contents

- [Commits](#commits)
- [What a person notices](#what-a-person-notices)
- [Findings](#findings)
- [The dominance sweep](#the-dominance-sweep)
- [Break-it results](#break-it-results)
- [Gates](#gates)
- [Open, and why](#open-and-why)

## Commits

| Commit | Subject |
|---|---|
| `ac3a471f` | fix(harness): a guard model that cannot turn reasoning off still screens every question |
| `ea7be3f0` | fix(harness): a Jev reply is never charged $0 or a whole cent, and a server stall no longer times Jev out |
| `c263c159` | fix(guardrail): no search develop answered is lost to the hedge, and a refusal in hand always wins |
| `7c028486` | fix(web-ui): a rate-limited search says how many seconds to wait, not "in a moment" |
| `a186b558` | test(guardrail): a stall just before Jev's reply arrives is pinned, and two break-it claims are corrected |

## What a person notices

- A search is no longer lost because the guard model was slow for a few seconds: every search develop's policy answered in the sweep is answered, and 24 more, because a slow first reply between 10 and 15 s now decides instead of being thrown away.
- In a slow spell the screening step takes about 10.6 s, as on develop, not the 4 to 7 s the builder's hedge gave; that hedge lost every spell of 4 to 10 s, which is why it moved.
- A question the classifier refuses is never admitted because another reply to the same question said yes.
- A question Jev judges on topic is not refused because the server stalled for a second.
- A rate-limited search says "Try asking again in about 20 seconds" in the web app, and "about 1 second" when it is one.
- A question that misses the biomedical word list is not held to 15 s in a slow spell.
- Nothing about Jev's charges shows on the screen; a drift in Jev's reply shape can no longer pause everyone at the system's daily cap.

## Findings

Reproduced before any fix, from the judge's and the adversary's own probes, run against `9e08d1d0`. Outputs are in the session scratchpad, `fix72/before/`. The commit for each finding is in its entry.

### F-72-J01 and J10: two usable replies in hand, the stricter wins

- Reproduced: `judge72/p1_same_tick.py` gave `('A', 'I') ... is_injection= False`, and `p1b_node.py` admitted a question the hedge had called injection, logging that reply as cancelled.
- Fix: `harness/decide.py` `ask_guard_model` reads every request that has ended, not only the ones `asyncio.wait` returned, and any other request that ended before the verdict is acted on; when more than one usable reply is in hand, `strictness` picks: injection, then any other refusal, then an admission (`core/graph.py` `_classifier_strictness`). For a guard pick, a pick other than the fail-open default beats it (`_pick_strictness`: off topic beats on topic). The log now says "answered, a stricter reply decided" for the reply that lost, not "cancelled".
- Test: `test_followup_guardrail.py::test_two_replies_in_hand_the_refusal_wins`, through the real `guardrail_node`: both orders in one tick, and the judge's shape (the refusal ends first, the admission one tick after). `test_the_stricter_reply_ranks_are_the_refusals_first`.
- J10, the bias toward the faster sample: closed where it can be, when both samples are in hand. It remains a note where only one reply has come back: that one decides, as before. The hedge now goes at 10 s, not 4 s, so far fewer questions get a second sample at all (those whose first request passes 10 s: 1, 0, 0 and 12 of 150 in the four golden runs the diagnosis measured).
- Commit: `c263c159`. Status: fixed.

### F-72-J02, A03, J09: Jev's charge and the per-query cap

- Reproduced: `judge72/p3_jev_cost.py` (a usable reply stating $0 charged $0 at the injection pick and at `decide`), `adv72/p3_jev_drift.py` (a shape drift cost $0.02004 in the guardrail, against $0.00004 on develop), `judge72/p13_cap.py` ($0.0965 plus an unusable reply ended at $0.1065 of a $0.10 cap).
- Fix, the product owner's decision of 2026-09-29: `harness/jev_client.py` `jev_charge_usd` and one named constant, `JEV_FLOOR_COST_USD = 0.0001`. A reply that came back is charged the cost it states when that is above $0 and at most `MAX_JEV_COST_USD`, and the floor otherwise: unusable, $0, missing, above the ceiling, not an amount. The amount is fixed in `jev_client` (`JevResult.cost_usd`, `JevCallError.billed_cost_usd`), so all three charge sites (`decide._run_jev_pick`, `graph._jev_injection_pick`, `sentence_check._ask_jev`) charge it without a change of their own. The log names the amount whenever the floor is charged.
- The cap: `harness/decide.py` `check_jev_per_query_cap`, used before the call at `decide` and the injection pick, refuses when the running cost plus `MAX_JEV_COST_USD`, the most a Jev call can be charged, would pass the cap.
- Tests: `test_jev_followup_costs.py` (every unusable shape charged the floor at `call_jev`, `call_jev_batch` and all three sites; `test_a_usable_reply_is_charged_its_sensible_cost_or_the_floor_at_every_site`; `test_a_floor_charge_is_logged_by_amount`; `test_no_jev_charge_takes_a_question_past_its_cap`), `test_jev_cost_bounds.py::test_a_reply_is_charged_its_sensible_cost_or_the_floor`, `test_decide.py::test_the_cost_cap_refuses_a_jev_call_whose_charge_could_pass_it`, and the pins moved from one cent to the floor in `test_jev_client.py`, `test_decide.py`, `test_sentence_check.py`.
- Commit: `ea7be3f0`.
- What a person notices: nothing on the answer. A drift in Jev's reply shape now costs about $0.0007 a question, not $0.07, so it cannot pause everyone at the system's daily cap.
- Status: fixed at `decide` and the injection pick. At the sentence check the charge amount is fixed (it comes from `jev_client`), but its pre-flight still checks the guard tier's $0.003 estimate, so a USABLE batch reply stating between $0.003 and $0.01 could still pass the cap by up to $0.007. Closing it needs one line in `synthesis/sentence_check.py`'s code, outside the fence: see "Open, and why".

### F-72-J03: a stall anywhere in Jev's wait

- Reproduced: `judge72/p4_fa03.py`, stalls of 0.8 s and 0.6 s in the cap check inside Jev's wait refused "Tell me about the tree of life." as off topic.
- Fix: `harness/jev_client.py` `wait_counting_free_time`. Every clock on a Jev call counts only time the event loop was free: Jev's own 3 s bound (`_send`), `decide()`'s outer net (`_jev_attempt`) and the guardrail's injection net (`_jev_injection_pick`). A stall anywhere, before the request or while the reply is read, is not counted against Jev; a reply that has arrived always wins over the clock. A real-time ceiling, `JEV_STALL_ALLOWANCE_S = 2.0`, keeps a server that keeps stalling from holding the wait open. A trickling body does not stall the loop, so F-8.2-J03's total bound still holds.
- Test: `test_followup_guardrail.py::test_with_jev_a_stall_anywhere_in_jevs_wait_never_turns_its_admission_into_a_refusal`, on the virtual clock through the real `decide()`: a 1.0 s stall where the builder put it, 0.6 s and 0.8 s where the judge put it, and 0.6 s and 1.0 s while Jev's reply is read. Every arm admits, on Jev's own pick.
- Commits: `ea7be3f0`, and the arm where the reply arrives after the stall, `a186b558`. Status: fixed.

### F-72-J04: "about 1 seconds"

- Reproduced: `judge72/p5_rl.py`.
- Fix: `core/graph.py` `_rate_limited_step_error` says "second" when the wait is one, and skips a wait that is not a finite number (the probe's `inf` raised `OverflowError`).
- Tests: `test_the_rate_limit_message_counts_seconds_in_words`, and the "has passed" arm of `test_a_retry_after_is_honoured_whichever_request_carried_it`.
- Commit: `c263c159`. Status: fixed.

### F-72-J05 and A02: the relevancy decision's guard pick

- Reproduced: `judge72/p6_rl_count.py` (4 requests, the pick's second at once), `adv72/p2_slow_spell.py` (a question the allowlist misses held to 15.00 s).
- Fix, by category: every guard-tier request the guardrail makes goes through `ask_guard_model`. `harness/decide.py` `_run_guard_pick` now uses it, with the guardrail's own deadline passed through `decide(..., deadline=)` from `core/graph.py` `_relevancy_decision`; at most two requests, the hedge, `Retry-After` honoured, one log line per request ("guard pick for guardrail.relevancy request N of 2").
- Tests: `test_a_rate_limit_storm_gives_each_guard_call_two_requests_and_a_backoff`, `test_the_relevancy_pick_honours_a_retry_after`, `test_in_a_slow_spell_a_question_the_allowlist_misses_is_not_held_to_15_s` (guard provider, and Jev on with its relevancy pick failing), all through the real node.
- What a person notices: in a slow spell, "Why do naked mole rats live so long?" passes at about 10.6 s, where it waited to 15 s.
- Commit: `c263c159`. Status: fixed per guard call, as decided. Per question, a rate-limit storm on a question the allowlist misses still sends two requests for the classifier and two for the pick, four in all, now each second one after the backoff or the provider's wait. `_run_guard_pick` serves every `decide()` point, so Think's and Plan's guard picks take the same path: two requests at most, a stated wait honoured, and after an error the second request about 2 s later rather than at once.

### F-72-J06: an unusable fast reply never beats a usable slow one

- Fix: none needed in the logic; the test was missing.
- Test: `test_a_usable_slow_reply_beats_an_unusable_fast_one`, both orders, both requests in flight, admitted at 12 s.
- Commit: `c263c159`. Status: fixed (test added).

### F-72-J07: the Jev failure signal raised while the guardrail waits

- Test: `test_with_jev_a_failure_signalled_mid_wait_ends_the_wait_at_once`: the classifier refuses at 0.05 s, Jev fails at 2 s, the fallback would take 5 s more; the refusal comes at 2.00 s.
- Commit: `c263c159`. Status: fixed (test added).

### F-72-J08: `retry=False` and the reasoning fallback

- Reproduced: `judge72/p12_reasoning.py`, a reasoning-mandatory guard model failed the classifier in 0.06 s.
- Fix: `harness/harness.py` `call_tier` takes the reasoning fallback whatever `retry` says; `retry=False` turns off only the transient retry.
- Tests: `test_harness.py::test_retry_false_still_resends_without_the_reasoning_block`, `test_retry_false_takes_the_reasoning_fallback_once_and_no_transient_retry`, and at the front door `test_followup_guardrail.py::test_a_guard_model_that_cannot_turn_reasoning_off_still_screens`.
- Commits: `ac3a471f` (the harness and its tests), `c263c159` (the front-door test). Status: fixed. The resend is part of the same request; it is not counted against the two-request promise, which is about a provider that is refusing, not a request it could not read.

### F-72-J11: the stale docstring

- Fix: `synthesis/sentence_check.py` `_ask_jev`'s docstring and comment now say what is charged: the stated cost when sensible, the floor otherwise.
- Commit: `ea7be3f0`. Status: fixed.

### F-72-A01: the web app's words

- Reproduced: `adv72/p1_rl_event.py` with the adversary's vitest probe: "Try asking again in a moment" for `retry_after_s: 20`.
- Fix: `frontend/src/hooks/useRunView.ts`, words only: with `retry_after_s` above 0 the failure reads "This run could not be completed. Try asking again in about N seconds.", "second" for one. `retry_after_s` is a number on the wire, so no backend text is rendered. No visual value changed; the event contract did not change.
- Test: `frontend/src/hooks/useRunView.retryAfter.test.ts`.
- Commit: `7c028486`. Status: fixed.

### F-72-A04: dominance

- See the next section. Commit: `c263c159`. Status: fixed, with the known limit stated there.

### F-72-A05: a hedge with a fraction of a second left

- Reproduced: `adv72/p7_late_hedge.py`, a hedge at 4.0 s with 0.3 s left, charged $0.000256.
- Fix: `harness/decide.py` `GUARD_MIN_HEDGE_S = 2.0`: no hedge when less than two seconds would be left. A request that is not sent is not charged (the only charge for a request is `call_tier`'s own, on a request it sent).
- Test: `test_no_hedge_goes_out_with_too_little_left` (4.3, 4.9 and 5.9 s left: one request, one cut-call charge).
- Commit: `c263c159`. Status: fixed. Against develop this is the one place the new policy sends less: with under 6 s left when the classifier starts, develop still sent a second attempt with under 2 s; the sweep's budgets (15 s and 12 s) do not reach it.

## The dominance sweep

File: `tests/system_03_search_agent/guardrail/test_guard_request_dominance.py`. It runs develop's classifier policy (`d23674f4`, R-01 and R-05, ported line for line as the yardstick) and the new one over the same grid, on a virtual clock, with the real constants and the real 15 s budget.

- Grid: 376 provider behaviours, each at two budgets (15 s, and 12 s for a question whose daily-cap checks took 3 s): 752 cases.
- The provider's behaviour depends on when a request is sent. Families: hang spells of 0.5 to 20 s (A04's shape), spells held and answered as they end, slow windows, stalls that catch the first request in flight, 503 and dropped-connection spells from a single failure to 20 s with the error after 0.05, 0.5 or 1 s, single slow failures (2 to 12 s), 429 spells with an honest `Retry-After` and with none, unusable-reply spells, and a refused key. Replies after a spell take 0.6, 1.5 or 3 s.
- Result: develop answered 429 of 752; the new policy answered 453, every one develop answered plus 24 more, never with more than two requests, never past the budget.
- The sweep is not vacuous: with the builder's 4-second hedge it reports A04's lost spells, and with "a failed request is retried at once" it reports lost error spells (RJ08's blip). Both are committed as tests.

What the sweep changed in the design, in the user's words: in a slow spell where every request hangs, the second request now goes when develop's did, at 10 s, so a spell of 4 to 10 s is answered at about 10.6 s as on develop, where the 4-second hedge lost it. The first request is still never cut, so a slow first reply between 10 and 15 s now decides instead of being thrown away. After an error, the second request goes when develop's last request would have gone (its immediate resend, backoff, fresh attempt and resend), but never so late that it keeps less time than develop gave its own second chance, and never after 10 s. The lead's example, a failed request retried at once, lost the 1-second error blip that develop's backoff outlasts, so it is not what shipped.

- A04 in numbers, the adversary's burst on a virtual clock: spells of 3, 5 and 8 s are answered at 10.60 s by both policies with 2 requests; an 11 s spell is lost by both.
- The trade, stated: a short spell (under 10 s) is no longer answered at about 4.6 s as the builder's hedge did; it is answered at 10.6 s, as on develop. Dominance and a 4-second hedge cannot both hold with two requests: a second request sent before 10 s lands inside any spell longer than it and shorter than 10 s, which develop's later request outlasts.

The known limit, measured, not in the committed grid:

- Error spells whose errors take 2 to 4 s to arrive: 16 of 108 such cases are answered by develop and not by the new policy (spells of 7.5 and 8 s with 2 s errors, 10 and 12 s with 4 s errors). There develop's four requests put its last one later than a second request can go while still giving an isolated failure the time develop gave it; the design keeps the isolated failure.
- "Fail, fail, then answer", whatever the time: develop answers with 3 requests; no two-request policy can.
- A provider that names a `Retry-After` and answers before it is up: R-10 line 4 requires the wait honoured, so the new policy waits where develop's immediate resend ignored it.

## Break-it results

Each fix was broken once on the committed tree, its tests run, and the file restored byte for byte; every run printed `restored=True clean=True` (`git diff --quiet`). Runner: the session scratchpad, `fix72/mutate.py`.

| # | Finding | Mutation | Red |
|---|---|---|---|
| M1 | J01 | the first usable reply by request number decides, not the strictest | 2 |
| M2 | J06 | an unusable reply ends the question while the other request runs | 2 |
| M3 | A04 | the hedge at 4 s of 15 (share 4/15) | 13, the sweep included |
| M4 | A04, RJ08 | a failed request retried at once | 11, the sweep included |
| M5 | FJ11 | the explicit hedge-point cap removed | 0: redundant at a two-thirds share, see below |
| M5b | FJ11 | R-05's backoff, the second 2 s after the failure | 7 |
| M6 | A05 | no floor on the hedge | 3 |
| M7 | J05, A02 | the guard pick back on `call_tier`'s own retry, no hedge | 4 |
| M8 | J04 | "seconds" always | 3 |
| M9 | J02 | a stated $0 charged $0 | 4 |
| M10 | J09 | the Jev pre-flight checks the guard estimate only | 3 |
| M11 | A03 | an unusable reply charged the one-cent ceiling | 74 |
| M12 | J03 | Jev's clocks count real time | 2 |
| M13 | J07 | the wait ignores Jev's failure signal | 1 |
| M14 | J08 | `retry=False` drops the reasoning fallback | 3 |
| M15 | A01 | the web app ignores `retry_after_s` | 2 (vitest) |

Two results changed the tests rather than the code (`a186b558`):

- M5 stayed green. At a hedge share of two thirds, whenever the failure time plus a third of the budget reaches the hedge point, develop's own last send already equals it, so the cap never binds. It is kept as a stated promise; FJ11's tests now name M5b as their break, which turns them red.
- M12 first turned only one arm red: in the reply-read arms, a reply already in hand wins over the clock on its own. An arm where the reply arrives after the stall ends now pins the free-time count, and M12 turns two arms red.

## Gates

Each polled until it exited, on `a186b558`.

| Gate | Command | Result |
|---|---|---|
| Unit suite, as `.github/gates/gate04_unit_suite.sh` runs it | `pytest -m "not integration" -q -rs` | 6642 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0, 211 s (the 7 warnings are the existing strawberry and JWT ones) |
| Lint | `ruff check .` | All checks passed |
| Import order, as `.github/gates/gate02_import_order.sh` runs it | `isort --check-only --diff src tests services tracker alembic .claude .github` | clean, exit 0 |
| Frontend tests | `npx vitest run` in `frontend/` | 59 files, 489 tests passed, exit 0 |
| Frontend build | `npm run build` in `frontend/` | exit 0 (the existing chunk-size warning only) |
| Touched tests | `tests/system_03_search_agent/harness/`, `guardrail/`, `synthesis/test_sentence_check.py`, `core/test_graph.py` | inside the suite above; the intermediate commit `ea7be3f0` alone, checked out in a scratch worktree: 1125 passed |

`frontend/node_modules` was linked to the main checkout's for the frontend gates and never staged.

## Open, and why

- F-72-J09 at the sentence check (blocked by the fence). `synthesis/sentence_check.py` `_ask_jev` checks the per-query cap with `cost_control.check_per_query_cap(harness, trace_id, "guard")`, the guard tier's $0.003 estimate. An unusable reply is now charged the $0.0001 floor, well inside that, but a usable batch reply stating between $0.003 and $0.01 is charged what it states and could take a question past its cap by up to $0.007. The fix is one line of code in that file, calling `harness.decide.check_jev_per_query_cap(harness, trace_id)` instead; the fence allowed only its docstring. Recorded here, per the brief's blocked-stop; nothing else in this round waits on it.
- `docs/build/Debugging_guide.md` (outside the fence) still says an unusable Jev reply is charged "the `MAX_JEV_COST_USD` ceiling, one cent" (the builder's `78b12c84`). It is now the $0.0001 `JEV_FLOOR_COST_USD`, and a usable reply stating $0 is charged the floor too. One sentence for the lead.
- J05 per question. Each guard call sends two requests at most, as decided. A rate-limit storm on a question the allowlist misses still sends four in all, two for the classifier and two for the relevancy pick, each second one now after the backoff or the provider's wait. A per-question limit of two would stop the classifier's own retry while the pick's first request was in flight, and so lose searches develop answered.
- The dominance limit, measured and stated in "The dominance sweep": error spells whose errors take 2 to 4 s to arrive (16 of 108 such cases), "fail, fail, then answer", and a provider that answers before its own `Retry-After`. With under 6 s left when the classifier starts, no hedge is sent (A05), where develop still sent a second attempt.
- `_run_guard_pick` serves every `decide()` point, so Think's and Plan's guard picks now also send two requests at most, honour a stated wait, and after an error send their second about 2 s later rather than at once. With the guard provider at its default this is production's path for those decisions.
- J10 where only one reply is in hand: that reply decides, as before.
- A Jev call that times out is still charged $0: no reply came back. The owner's decision covers replies; a timeout is not one.
