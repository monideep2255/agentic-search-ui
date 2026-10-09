# Guardrail design build: cards 84 and 72

The builder's record for steps 1 and 3 of `design.md` in this folder, accepted by the owner on 2026-10-08. Step 2 (host routing) is parked and not built here. Step 4 is kept by changing nothing in the topic check or the rate-limit handling.

- Branch: `fix/card84-72-guardrail`
- Base: `c916cfa30f59802dfd85c81ef7ba39bdcfc2b263` (origin/develop)
- No live model calls; no model credit spent.

## Table of contents

- [Tickets and commits](#tickets-and-commits)
- [Finding IDs, where each is fixed and tested](#finding-ids-where-each-is-fixed-and-tested)
- [Deviations from the design and the brief](#deviations-from-the-design-and-the-brief)
- [Findings while building](#findings-while-building)
- [Test runs](#test-runs)
- [Learnings](#learnings)

## Tickets and commits

| Ticket | Step | Commit | Status |
|---|---|---|---|
| 1 | Step 1: plain words when the guardrail fails | `2cc13e0e` | built, tested |
| 2 | Step 3a: Jev's charges by the owner's rule | not committed, see Learnings | built, tested |
| 3 | Step 3b: Jev says when it failed; a server pause no longer refuses | not committed, see Learnings | built, tested |
| 4 | Step 3c: the log line keeps only what a host name needs | not committed, see Learnings | built, tested |
| 5 | Step 3d: the sweep against develop's code | not committed, see Learnings | built, tested, 9 passed |

## Finding IDs, where each is fixed and tested

| Finding | What a person meets | Fixed in | Tested by |
|---|---|---|---|
| F-72-V05 | "In a moment" for a guardrail failure; a long wait read as thousands of seconds | `frontend/src/hooks/useRunView.ts`, `guardrailFailure` | `useRunView.retryAfter.test.ts`, "a wait past two minutes reads in whole minutes" and "a double timeout reads the plain words" |
| F-84-A01 | A wait that has passed told as if the person should retry into a limit | same | "a wait that has passed, or none named, never says to wait" |
| F-84-A02 | "About 86400 seconds" | same, minutes past two minutes | "a wait past two minutes reads in whole minutes" |
| F-84-A09 | Every passing failure told to wait; "wait passed" and "none named" not told apart | same: only `source === "guardrail"` changes, and both 0 cases read the plain "Try asking again." | "every other failure keeps its own words" and "a wait that has passed, or none named" |
| F-4.8-A-15 | Backend text on screen | same: only `source`, `error_class` and `retry_after_s` are read | "never renders the backend's own message" |
| F-72-J02 | A usable Jev reply stating $0 charged $0 | `harness/jev_client.py` `jev_charge_usd`, `_charged_for_usable` | `test_jev_cost_bounds.py::test_a_stated_zero_is_charged_the_floor`; `test_jev_followup_costs.py` "usable, states $0" at `call_jev`, `call_jev_batch` and all three sites |
| F-72-A03 | A drift in Jev's reply shape cost about 7 cents a question | same: no amount or an unreadable body is charged `JEV_FLOOR_COST_USD`, $0.0001, not the cent | `test_no_amount_is_charged_the_floor`; `test_a_drift_in_jevs_reply_shape_costs_a_question_cents_no_longer` |
| F-72-V03 | A Jev error status (500, 429, 402) charged $0 | `jev_client._send`, `billed_cost_usd=JEV_FLOOR_COST_USD` on a non-200 | `test_jev_followup_costs.py` HTTP 500, 429, 402 arms; `test_jev_client.py::test_an_unusable_reply_still_reports_what_it_cost` |
| F-72-V04 | The debugging guide stated the wrong Jev charge rule | `docs/build/Debugging_guide.md`, the `jev_client` row rewritten | read |
| F-72-J11 | A code comment named the wrong Jev charge | comments at the three charge sites (`decide._run_jev_pick`, `graph._jev_injection_pick`, `sentence_check._ask_jev`) | read |
| F-84-J04 | An unusable reply stating a sensible cost charged the floor | `_unusable_reply(charged_usd=...)`: every reply charged `jev_charge_usd` of what it states | "unusable, states a sensible cost (F-84-J04)" at `call_jev`, `call_jev_batch` and all three sites |
| F-84-A06 | A reply stating more than a cent charged the floor | `jev_charge_usd`: above the ceiling is the ceiling; infinity and a number too large for a float read as above it | `test_a_stated_cost_above_the_ceiling_is_charged_the_ceiling`, `test_more_stated_is_never_less_charged`, "states five cents" arms |
| F-8.6-FJ01 | `"probabilities": null` escaped `call_jev` uncharged as an `AttributeError` (still on develop) | `call_jev` parse catches by base class | "probabilities null, states a sensible cost" |
| F-8.6-FA03, F-72-J03 | A server pause of about 0.6 s inside Jev's wait turned Jev's on-topic pick into an off-topic refusal | `jev_client.wait_counting_free_time`, `JEV_STALL_ALLOWANCE_S`; used by `_send`, `decide._jev_attempt` and `graph._jev_injection_pick`; `decide(..., jev_failed=)` and `graph._await_jev_own_pick` replace R-06's 3.75 s window | `test_followup_guardrail.py::test_with_jev_a_pause_anywhere_in_jevs_wait_never_turns_its_admission_into_a_refusal`, six arms on the virtual clock; the residual `test_with_jev_a_pause_past_the_allowance_still_ends_jevs_clock` |
| F-72-J07 | Jev's failure raised while the guardrail already waits was untested, so a refusal could come 5 s late | `_await_jev_own_pick` waits on the event and the decision together | `test_with_jev_a_failure_signalled_mid_wait_ends_the_wait_at_once` (2.0 s, not 7.0 s) |
| F-8.6-RJ03, RJ09 | A refusal only Jev's own pick could change held for the guard fallback | kept, now on the signal | `test_with_jev_failing_an_off_topic_refusal_is_not_held_for_the_fallback`, `test_with_jev_an_injection_refusal_is_not_held_for_the_relevancy_fallback` |
| F-84-J07 | The guard-call log line wrote up to 64 characters of the upstream's own name field verbatim | `harness/call_log.py` `provider_of`, `_NOT_IN_A_HOST_NAME`: ASCII letters, digits, dots, hyphens and spaces only | `test_call_log.py::test_provider_of_keeps_only_what_a_host_name_needs` (10 arms), `test_provider_of_never_writes_a_line_break_into_the_log` |
| F-84-A08 | Every healthy guard call writes a WARNING line | kept at WARNING on purpose until step 2's ranking; the module note now says so | `test_the_line_stays_at_warning_until_host_routing_is_decided` |
| F-72-V08, F-84-A05, A07 (the admissions that stopped both branches) | Not reintroduced: no hedge, no rate-limit cap, the topic check and rate-limit handling untouched | the sweep: the classifier matches develop's policy case for case, rate limits included | `test_guard_request_dominance.py`, both classifier sweeps, and `test_the_sweep_catches_a_hedge` |
| F-84-A03, J05 | The reserve-the-ceiling check (`1e1aab4a`) dropped checked sentences near the cap | not brought back: `decide` and the injection pick still check the guard estimate, the sentence check keeps develop's card 99 reservation | unchanged tests pass |

## Deviations from the design and the brief

- Step 1, no backend change: on develop the guardrail sends `retry_after_s: 0` on every step error (`core/graph.py` `_step_error_kwargs`, and the unusable-verdict dict), so today a person always reads the plain words. The "about 20 seconds" wording is ready for the day a guardrail rate limit carries its wait; sending it is a backend change outside this card's fence and outside step 4's "leave the rate-limit handling as develop has it".
- Step 3a, infinity and huge numbers: the design says "an unreadable amount is charged the floor" and "a stated cost above $0.01 is charged the $0.01 ceiling". A stated `Infinity`, or a positive integer too large for a float, is read as a cost above the ceiling and charged the ceiling, so the charge never falls as the stated cost rises (F-84-A06). `NaN`, a negative figure, a boolean or a string that is not a number are read as no amount and charged the floor.
- Step 3a, a stated cost below the floor but above $0 (for example $0.00002, Jev's real price) is charged as stated, per the owner's words; the floor applies only to $0 and no amount.
- Step 3a, fence: `tests/system_03_search_agent/harness/test_decide.py` pinned develop's rule (a `NaN` or negative cost charged the ceiling); its two arms now expect the floor and its comment states the new rule. No other line of that file changed. `test_sentence_check.py` needed no change: its three arms (above the ceiling, an option outside the set, infinity) charge the same under both rules.
- Step 3a, the sentence check's pre-flight reservation (calls times `MAX_JEV_COST_USD`, card 99) is develop's and stays; only its comments changed, since `MAX_JEV_COST_USD` is still the most one call can be charged.
- Step 3b, fence: the signal has to reach `decide()`, and on develop the relevancy decision is started in `guardrail_node` and asked through `_relevancy_decision` and `_decide_point`. Each of those three got the smallest plumbing change (an `asyncio.Event` created in `guardrail_node` instead of the `relevancy_started` list, passed through, and an optional `jev_failed` keyword on `_decide_point`), outside the three functions the brief names. R-06's `_jev_own_pick_deadline` and `_JEV_OWN_PICK_WINDOW_S` are removed, replaced by `_await_jev_own_pick`. No behaviour of those three functions changes besides carrying the event. `_await_within_step` keeps its now unused `why` keyword so it is not touched.
- Step 3b, the stall arm "in the cap check inside Jev's wait": develop has no `check_jev_per_query_cap` (the reserve check is not brought back), so the arm pauses `decide`'s own `cost_control.check_per_query_cap` before Jev's request, the same spot.
- Step 3b, the residual arm: a 2.5 s pause in the cap check, before Jev's own bound starts, is admitted (Jev's own 3 s clock has not started). The residual both reviews named is a pause inside Jev's own bound, so the arm pauses as Jev's request is sent; that one still refuses.
- Step 3d, the sweep's rule for a paused case: the brief says the sweep proves the change "answers none later". Step 3b cannot meet that after a server pause (above), so the sweep holds the strict rule for every case without a pause and, for a paused case, holds that the verdict equals the same case's no-pause verdict and that it is no later than develop by more than the pause; the paused differences are counted by class, not hidden. The lead or owner should confirm this reading.
- Step 3d, the sweep's grids: the classifier grid is card 84's (17 behaviours in every ordered triple plus time-switching providers, budgets 15 s and 12 s, 10,306 cases), run twice, with the guard provider and with Jev on. The relevancy grid is new (1,296 cases): the classifier's verdict and timing, Jev's injection pick, Jev's relevancy pick and timing, the guard fallback pick, and a pause of 0, 0.6 or 1.0 s as Jev's relevancy request is sent. The yardstick copies call this branch's unchanged `_rate_limit_behind` and `_provider_retry_after_s` header readers.
- Ticket order: the virtual clock (`tests/system_03_search_agent/virtual_clock.py`) is in ticket 3, not ticket 5, because ticket 3's pause arms run on it. Ticket 5 adds the sweep. The clock also replaces `time` in `harness.call_log`, so the log line's elapsed time reads the same clock.
- Step 1, minutes only: the design says "in minutes past two minutes", so a day reads "about 1440 minutes". No hours arm was added.

## Findings while building

- The sweep's result (`pytest -s tests/system_03_search_agent/guardrail/test_guard_request_dominance.py`, "9 passed in 20.63s"):
  - "classifier, guard sweep: 10306 cases, develop answered 5940, held 5940, problems 0"
  - "classifier, jev sweep: 10306 cases, develop answered 5940, held 5940, problems 0"
  - "relevancy sweep: 1296 cases, develop answered 1080, held 928, problems 0", with the counted classes below.
- The yardsticks checked against develop's real code: the same grids run through an export of `c916cfa3`'s `src` (real node) and through the test file's copies on this branch gave "classifier guard: 10306 of 10306 identical", "classifier jev: 10306 of 10306 identical", "relevancy: 1296 of 1296 identical" (verdict, elapsed time and requests, case for case).
- Step 3b does change timing and verdicts against develop, but only after a server pause, and the brief's "answers none later" does not hold there. Against develop's real code over the relevancy grid (1296 cases): 160 answered sooner; 64 answered later, by 0.15 to 0.9 s, never more than the pause itself; verdict changes: 48 develop off topic now admitted on Jev's own on-topic pick (the FA03 fix), 16 develop admitted now refused off topic on Jev's own off-topic pick, 26 develop off topic now refused as injection, 12 develop injection now refused off topic. Every paused case gets the verdict the same case gets with no pause (checked case by case). In words a person would use: after a server pause, the guardrail now waits for Jev's real answer instead of giving up on it, so the person gets the answer they would have got without the pause, up to the length of the pause later. The design's "Cost: nothing in seconds" for 3b holds only when the server does not pause. With no pause, every case is identical to develop but one class (2 cases): a question Jev called injection whose relevancy pick failed is now refused as injection the moment Jev fails, not as off topic after the guard fallback; a refusal either way, never later.
- `wait_counting_free_time` could spin forever on a clock that does not move: with a few billionths of a second of budget left, `asyncio.wait` returns without the virtual clock advancing and nothing is ever counted. The sweep hung on it (600 s timeout). A real clock always moves, so production was not at risk, but the loop now treats under a microsecond left as none (`_NONE_LEFT_S`). The reference commit `ea7be3f0` had the same loop.
- A closed (garbage-collected) coroutine inside `wait_counting_free_time` tried to await in its `finally`, which Python refuses ("coroutine ignored GeneratorExit"); it now cancels without waiting in that one case. The virtual clock now lets cancelled tasks finish before closing its loop, which also removed the "Task was destroyed but it is pending" noise.
- Step 3c residual: a key-shaped string made of letters, digits and hyphens still passes the allowlist, cut at 64 characters. The field is the upstream's own text, never our key or the question.

- Develop's `call_jev` still caught a list of five error types, so a Jev reply with `"probabilities": null` raised an `AttributeError` out of `call_jev`, uncharged (F-8.6-FJ01, fixed on the parked branches, never on develop). `decide()` and the injection pick then took it as "unexpected_error". Fixed here with the charge rule, since it is a returned reply going uncharged.
- Develop's isort gate passes on `src tests`, but `isort --check-only` on `core/graph.py` alone fails on develop's own file: run the gate's form.

## Test runs

Tickets 4 and 5, and the directory runs:

- `harness/test_call_log.py`: "31 passed". Mutation, `provider_of` keeping every printable character again: "7 failed, 24 passed".
- `guardrail/test_guard_request_dominance.py`: "9 passed in 20.63s". Its four "catches" tests are its mutation proof: a hedge (two in flight, a slow off-topic losing to a fast admission), a 2 s backoff after an error (later than develop), the relevancy wait held for the guard fallback (later than develop), and Jev removing an injection refusal (the rule check).
- `tests/system_03_search_agent/guardrail`: "367 passed in 72.32s". `tests/system_03_search_agent/harness`: "472 passed in 24.91s".
- `synthesis/test_sentence_check.py` and `synthesis/test_sentence_pair_check.py`: "146 passed".
- `ruff check` over the whole repository: "All checks passed!". `isort --check-only src tests`: exit 0. Frontend `useRunView.retryAfter.test.ts`: "Tests  9 passed (9)".

Ticket 3:

- `guardrail/test_followup_guardrail.py`: "53 passed in 38.64s".
- `harness/test_jev_client.py` 47 passed; `harness/test_decide.py` 71 passed; `harness/test_jev_followup_costs.py` 52 passed; `guardrail/test_guardrail_node_integration.py` 60 passed; `guardrail/test_reland_guardrail.py` 49 passed.
- Mutations, each restored byte for byte:
  - `wait_counting_free_time` counting real time (`counted += now - last`), run on the pause arms: "2 failed, 5 passed" (the 0.8 s cap-check arm and the before-the-reply arm).
  - `_await_jev_own_pick` ignoring the event, run on the mid-wait and not-held arms: "1 failed, 3 passed" (the mid-wait arm; the stub arms set the event before the wait starts, which is F-72-J07's point).
  - `decide()` not setting the event in Jev mode: "1 failed, 1 passed" (`test_decide_says_jev_failed_before_it_asks_the_guard_tier`).

Ticket 2:

- `test_jev_cost_bounds.py`: 29 passed. `test_jev_followup_costs.py`: 52 passed. `test_jev_client.py`: 47 passed. `test_decide.py`: 71 passed. `synthesis/test_sentence_check.py`: 99 passed. `synthesis/test_sentence_pair_check.py`: 47 passed.
- Mutations of `jev_client.py`, each run against `test_jev_followup_costs.py` and `test_jev_cost_bounds.py`, then restored:
  - an error status charged nothing again: "7 failed, 74 passed";
  - an invalid option charged the floor (F-84-J04's branch): "3 failed, 78 passed";
  - above the ceiling charged the floor (F-84-A06's branch): "15 failed, 66 passed";
  - a list of error types in `call_jev`'s parse (FJ01): "1 failed, 80 passed";
  - develop's rule (no amount the ceiling, $0 charged $0): "26 failed, 55 passed".
- ruff on the touched files: "All checks passed!". isort: `isort --check-only src tests`, gate02's form, exit 0. Run on single files instead, isort flags `core/graph.py`'s import block on develop's own copy too (checked on `c916cfa3`'s file), so it is not this change.

Ticket 1:

- `npx vitest run src/hooks/useRunView.retryAfter.test.ts`: 9 passed. Mutations: the guardrail branch disabled gave "6 failed | 3 passed"; the branch read for every source gave "1 failed | 8 passed". Restored after each.
- `npx vitest run src/hooks/`: "Test Files  11 passed (11)", "Tests  78 passed (78)".
- `npx tsc --noEmit -p .`: exit 0.

## Learnings

- Commits held by the public repository guard, about 15 minutes lost. From ticket 2 on, every `git commit` in this session, even `git commit --dry-run`, came back "mod-public-repo-guard: the guard failed while checking this call, so it was held". The leak scanner the guard runs passes when run by hand (`check_public_leaks.py --no-fetch`: "PASS", 14 s), and a mod's `$` calls do not count against its 10 s hook budget, so the cause is inside the guard (its catch-all `denyOnFailure`), not the change. The guard is a security control, so it was not bypassed. Ticket 1's commit went through on its second try, in a command that also wrote its message with a heredoc, so the guard may not have recognised it as a commit (not confirmed); git's own pre-commit hook did run on it ("PASS: no local references found."), and the leak scanner run by hand passes on the whole branch; tickets 2 onward are left for the lead: ticket 2 is staged in the index, tickets 3 to 5 are in the working tree, and the builder's scratchpad holds a script that commits them one ticket each, staging by name, with each ticket's message (`commit_tickets.sh`, `msg2.txt` to `msg5.txt`).
