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
| 2 | Step 3a: Jev's charges by the owner's rule | pending | built, tested |

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
| F-84-A03, J05 | The reserve-the-ceiling check (`1e1aab4a`) dropped checked sentences near the cap | not brought back: `decide` and the injection pick still check the guard estimate, the sentence check keeps develop's card 99 reservation | unchanged tests pass |

## Deviations from the design and the brief

- Step 1, no backend change: on develop the guardrail sends `retry_after_s: 0` on every step error (`core/graph.py` `_step_error_kwargs`, and the unusable-verdict dict), so today a person always reads the plain words. The "about 20 seconds" wording is ready for the day a guardrail rate limit carries its wait; sending it is a backend change outside this card's fence and outside step 4's "leave the rate-limit handling as develop has it".
- Step 3a, infinity and huge numbers: the design says "an unreadable amount is charged the floor" and "a stated cost above $0.01 is charged the $0.01 ceiling". A stated `Infinity`, or a positive integer too large for a float, is read as a cost above the ceiling and charged the ceiling, so the charge never falls as the stated cost rises (F-84-A06). `NaN`, a negative figure, a boolean or a string that is not a number are read as no amount and charged the floor.
- Step 3a, a stated cost below the floor but above $0 (for example $0.00002, Jev's real price) is charged as stated, per the owner's words; the floor applies only to $0 and no amount.
- Step 3a, fence: `tests/system_03_search_agent/harness/test_decide.py` pinned develop's rule (a `NaN` or negative cost charged the ceiling); its two arms now expect the floor and its comment states the new rule. No other line of that file changed. `test_sentence_check.py` needed no change: its three arms (above the ceiling, an option outside the set, infinity) charge the same under both rules.
- Step 3a, the sentence check's pre-flight reservation (calls times `MAX_JEV_COST_USD`, card 99) is develop's and stays; only its comments changed, since `MAX_JEV_COST_USD` is still the most one call can be charged.
- Step 1, minutes only: the design says "in minutes past two minutes", so a day reads "about 1440 minutes". No hours arm was added.

## Findings while building

- Develop's `call_jev` still caught a list of five error types, so a Jev reply with `"probabilities": null` raised an `AttributeError` out of `call_jev`, uncharged (F-8.6-FJ01, fixed on the parked branches, never on develop). `decide()` and the injection pick then took it as "unexpected_error". Fixed here with the charge rule, since it is a returned reply going uncharged.
- Develop's isort gate passes on `src tests`, but `isort --check-only` on `core/graph.py` alone fails on develop's own file: run the gate's form.

## Test runs

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

- None yet.
