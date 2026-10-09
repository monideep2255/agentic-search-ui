# Guardrail safe part build: cards 84 and 72

The builder's record for the guardrail's safe part, approved by the owner on 2026-10-09: step 1 and steps 3a and 3c of `testing/Developer/reports/2026-10-08_guardrail_design/design.md`, section 4. Step 3b (the server-pause fix) and the sweep that depends on it are not built. The guardrail's admit or refuse decisions are develop's, case for case.

- Branch: `fix/card84-72-guardrail-safe-part`
- Base: `b01dee92b2981afce665ecf5949e693664cea3fe` (origin/develop)
- Source of the work: the parked commits under the local tag `parked/card84-72-guardrail-2026-10-08`
- No live model calls; no model credit spent.

## Table of contents

- [What a person sees](#what-a-person-sees)
- [Parts and commits](#parts-and-commits)
- [Deviations from the parked commits](#deviations-from-the-parked-commits)
- [The decision grid against develop](#the-decision-grid-against-develop)
- [Each test bites](#each-test-bites)
- [Test runs](#test-runs)
- [Left open](#left-open)
- [Fix round](#fix-round)

## What a person sees

- When the check every question passes first cannot finish, the message now reads: "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again." Before, it read "Try asking again in a moment".
- A question the provider refuses, a 400 and a 401 keep develop's words, "Try asking again, or rephrase the question". Two unreadable replies from the check read the new words since the fix round (J-GRS-08, A-GRS-08); the table in the fix round gives every case.
- Nothing in an answer or a refusal changes. The guardrail admits and refuses exactly what develop does.
- The money counted for each Jev reply follows the owner's rule of 2026-09-29, so the cost caps see what Jev says it charged.
- Test query: number 109 in `testing/Test_queries_and_workflows.md`.

## Parts and commits

| Part | Design step | Commit | From | Files |
|---|---|---|---|---|
| 1 | Step 1: plain words when the guardrail fails | `329b4ef3` | `2cc13e0e` and its A-GR-10 fix `3592e856`, web app only | `frontend/src/hooks/useRunView.ts` (`FATAL_COPY` and the failure branch), `useRunView.retryAfter.test.ts` |
| 2 | Step 3a: Jev's charges by the owner's rule | `3261eb47` | `e2568d73`, not `1ce2c8d4` | `harness/jev_client.py`; the charge comment at `core/graph.py` `_jev_injection_pick`, `harness/decide.py` `_run_jev_pick` and `synthesis/sentence_check.py` `_ask_jev`; the debugging guide's `jev_client` row; the charge tests; the decision grid test |
| 3 | Step 3c: the log line keeps only what a host name needs | `c7711c98` | `9e5a79ce` | `harness/call_log.py`, `test_call_log.py` |

The charge rule as built:

| What a Jev reply states | Charged |
|---|---|
| A finite cost above $0 and at most $0.01, one under the floor included ($0.00002) | That cost |
| A cost above $0.01, however spelled: 0.05, 1e309, Infinity, an integer too large for a float, a numeric string | The $0.0001 floor (fix round; this build first charged the $0.01 ceiling) |
| $0, no cost, or an unreadable amount: NaN, a negative figure, a boolean, text | The $0.0001 floor |
| An unreadable body | The floor |
| An error status, 500, 429 or 402 | The floor |
| A timeout or a transport failure, where no reply came | Nothing |

Usable or unreadable makes no difference to the charge.

## Deviations from the parked commits

- Part 1, the backend class of two unreadable replies: `3592e856` also changed `core/graph.py` `_guardrail_after_prefilter` to send two unreadable guard replies as "transient". That function is outside this change's file fence, so it is not taken. Two unreadable replies still arrive as "recoverable" and keep develop's words. The test case that expected them to read the new words now pins develop's words for them. Taking the one-line class change later gives them the new words with no web app change. Superseded: the fix round takes it.
- Part 2, infinity: `e2568d73` charged a stated Infinity the $0.01 ceiling. The brief reads infinity as unreadable, so `_stated_cost_usd` and `jev_charge_usd` now charge infinity, NaN and a negative figure the floor. The tests that pinned Infinity at the ceiling, in `test_jev_cost_bounds.py`, `test_jev_client.py`, `test_decide.py` and `test_sentence_check.py`, now pin the floor.
- Part 2, the floor: `1ce2c8d4`, which raised a stated cost under the floor to the floor, is not taken (the verifier's V-GR-11). A stated $0.00002 is charged $0.00002.
- Part 2, docstrings: `e2568d73` also rewrote the docstrings of `decide._run_jev_pick` and `sentence_check._ask_jev`. They are left as develop has them, inside the fence's "charge line only". The comments beside each charge line, and one comment in `_ask_jev`'s cap reservation that would otherwise say the client bills the ceiling for an unreadable reply, are updated.
- Part 3: taken as parked. The line stays at WARNING.

## The decision grid against develop

`tests/system_03_search_agent/guardrail/test_decision_grid_matches_develop.py` drives the real `guardrail_node`, `decide()`, `call_jev` and charge sites, stubbing only `litellm.acompletion` and `jev_client._post`.

| Axis | Values |
|---|---|
| Question | an off-topic-sounding one Jev's relevancy judges, an allowlisted one, a forbidden one |
| Guard classifier | admit, off topic, injection, two unreadable replies |
| Jev injection reply | 12 outcomes: sensible cost, stated $0, above the ceiling, Infinity, no cost, an option outside the set, null probabilities, HTTP 500, HTTP 429, not JSON |
| Jev relevancy reply | 7 outcomes: on or off topic, stated $0, above the ceiling, Infinity, HTTP 500, not JSON |
| Guard fallback pick | on topic, off topic |

- 768 cases. Develop's verdicts are recorded in `develop_decision_grid.json`, written by running the same grid with develop's four source files from `b01dee92` in place.
- Develop's verdicts across the grid: injection 218, off topic 216, step error 192, admitted 130, read-only reply 12.
- Before, develop's source in place: "1 passed in 3.55s".
- After, this branch: "1 passed in 3.17s".
- Mutation: `call_jev` using a reply that states more than the ceiling, charged at the ceiling: "98 of 768 verdicts differ from develop's", for example "allowlisted | admit | injection, Infinity: develop {'category': 'ok', 'passed': True}, now {'passed': False, 'category': 'injection'}". Restored after.

## Each test bites

| Part | Broken | Result, pasted |
|---|---|---|
| 1 | `useRunView.ts` back to develop's file | "Tests  4 failed \| 7 passed (11)": the double timeout and the three wait cases |
| 1 | The guardrail words for every class but "cancelled" (the first parked build) | "Tests  4 failed \| 7 passed (11)": the content-policy, 400, two unreadable replies and 401 cases |
| 2 | Stated costs under the floor raised to it (`1ce2c8d4`'s rule) | "18 failed, 288 passed", `test_a_stated_cost_under_the_floor_is_charged_as_stated` among them |
| 2 | Infinity charged the ceiling again (`e2568d73`'s rule) | "7 failed, 299 passed", `test_infinity_nan_and_negative_are_unreadable_and_charged_the_floor[inf]` among them |
| 2 | An error status charged nothing (develop's rule) | "10 failed, 296 passed", the HTTP 500, 429 and 402 arms |
| 2 | `jev_client.py` back to develop's file | "4 errors" at collection: `cannot import name 'JEV_FLOOR_COST_USD'` |
| 3 | `call_log.py` back to develop's file | "7 failed, 24 passed" |
| 3 | Only control characters dropped, every printable character kept | "5 failed, 26 passed" |

Each break was restored and the file compared with its saved copy before the next.

## Test runs

| Run | Result |
|---|---|
| `tests/system_03_search_agent/guardrail` | "348 passed in 60.29s" |
| `tests/system_03_search_agent/harness` | "513 passed in 23.20s" |
| `synthesis/test_sentence_check.py` | "99 passed in 2.70s" |
| `synthesis/test_sentence_pair_check.py` | "47 passed in 3.24s" |
| `core/test_write_answers_sooner.py` and `core/test_bare_topic_clarification.py`, which import `jev_client` | "92 passed in 9.29s" |
| `frontend/src/hooks/useRunView.retryAfter.test.ts` | "Tests  11 passed (11)" |
| `frontend/src/hooks`, all twelve files | "Tests  90 passed (90)" |
| `npx tsc --noEmit -p .` | exit 0 |
| `ruff check` over the repository | "All checks passed!" |
| `isort --check-only src tests` | exit 0 |

## Left open

- Two unreadable guard replies still read "rephrase the question". Taking `3592e856`'s one-line class change in `core/graph.py` fixes it; it was outside this change's fence. Closed in the fix round.
- Every guardrail step error still sends `retry_after_s: 0` (A-GR-01, J-GR-05), so the "about N seconds" words never show yet. The web app is ready for a named wait.
- The adversary's key-shaped host name (adversary.md, around line 33): `provider_of` keeps every character a router key uses, so such a string would still reach the log. Not in this part's scope. Closed in the fix round.
- Step 3b, the server-pause fix, and the sweep against develop that depends on it, are not built (the verifier's V-GR-01, V-GR-04 and V-GR-08 stand against the parked version).

## Fix round

One fix round on the judge's and the adversary's findings (`judge.md`, `adversary.md`, both in this folder), on top of `664e0e5b`. The guardrail's admit or refuse decisions are still develop's: the decision grid passes, with one approved class change named below.

### What changed, by finding

| Finding | What changed |
|---|---|
| A-GRS-05 | `jev_client._unusable_reply` logs a fixed category (`not_json`, `cost_above_ceiling`, `wrong_shape`, `option_outside_set`), the reply's length in bytes and the charge; never Jev's choice, a figure's text or the body. The error's own message, which callers do not log, keeps its detail. |
| A-GRS-08, J-GRS-08, J-GRS-12 | `core/graph.py` takes `3592e856`'s one-line class change and its comment, nothing else: two unreadable guard replies end as "transient", so the web app shows the step 1 words. The tests `3592e856` changed with it are taken (`test_followup_guardrail.py`, `test_call_log.py`). The web test now sends two unreadable replies as "transient" and expects the new words; `useRunView.ts` changes in its comment only. Test query 109 is corrected. |
| J-GRS-03, J-GRS-04, A-GRS-03 | `jev_charge_usd` follows the owner's row of 2026-09-29 literally: a finite stated cost above $0 and at most `MAX_JEV_COST_USD` is charged as stated, everything else the $0.0001 floor. A stated cost above the ceiling is charged the floor whatever its form: 0.05, 1e309, Infinity, an integer too large for a float, a numeric string. Develop charged the $0.01 ceiling above `MAX_JEV_COST_USD`; this follows the owner's row literally. Such a reply is still not used, so no verdict moves. |
| A-GRS-01, J-GRS-10, A-GRS-07 | `call_log.provider_of` keeps the provider only when the whole value is host-name-shaped (ASCII letters, digits, dot, hyphen, underscore, 1 to 64 characters) and not key- or token-shaped (a credential opening such as a router key's, a bearer word or a JWT's header; a run of 16 or more characters with a digit; a run over 32). Anything else logs as "unknown", never a repaired copy. `log_model_call` cuts each text field to 64 characters and the line to 512. The stated figure in a cost-above-ceiling error message is written `:.6g`, so it stays short. |
| A-GRS-06 | Two new arms kill the surviving mutations: a batch reply with an option outside the set stating $0 (M4), and a body nested 100,000 deep, single and batch (M5). |
| J-GRS-11 | `_send` now writes the warning its docstring promised for an error-status charge: "Jev returned HTTP <status> for <subject>, reply length <n> bytes; it is charged $0.000100", with no body text. |

Left as they are, by the lead's instruction:

- A-GRS-02: near a per-query cap of about one cent the branch refuses as off topic a few questions develop admits. Out of reach at develop's $0.25 cap.
- A-GRS-04 and J-GRS-05: a stated tiny positive cost (5e-324, 1e-300) is above $0, so it is charged as stated, per the rule. `test_the_boundary_at_zero` pins it.
- J-GRS-06: every non-200 status, a 401, 404 or 302 included, is charged the floor.

### What a person reads when the guardrail fails

Develop's classes come from `harness._classify_exception` and `_guardrail_after_prefilter`. "Plain words" is the step 1 text: "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again." "Rephrase" is develop's "This run could not be completed. Try asking again, or rephrase the question."

| Guard failure | Class, develop then branch | Develop shows | This branch shows |
|---|---|---|---|
| One timeout, then no time left for a second attempt | transient, transient | "This run could not be completed. Try asking again in a moment." | Plain words |
| One timeout, then an unreadable reply | recoverable, transient | Rephrase | Plain words |
| Double timeout | transient, transient | "... Try asking again in a moment." | Plain words |
| Rate limit (429) on both attempts, or a wait that does not fit | transient, transient | "... Try asking again in a moment." | Plain words (`retry_after_s` is always 0, so never "in about N seconds" yet) |
| 5xx (500, 502, 503) on both attempts | transient, transient | "... Try asking again in a moment." | Plain words |
| Connection error on both attempts | transient, transient | "... Try asking again in a moment." | Plain words |
| Two unreadable replies | recoverable, transient | Rephrase | Plain words |
| Content-policy refusal | recoverable, recoverable | Rephrase | Rephrase |
| 400 | recoverable, recoverable | Rephrase | Rephrase |
| 401 | unexpected, unexpected | Rephrase | Rephrase |

None of them now tells a person "nothing was searched, the problem was ours" when their question was at fault: the two failures a question can cause, a content-policy refusal and a 400, keep "rephrase". One limit, read not probed: a question written to make the guard model answer in prose rather than JSON could cause two unreadable replies, and would then read the plain words. Asking again fails the same way and nothing is admitted either way; the three unreadable replies seen on 2026-09-29 were cut-off replies from the provider.

### Each new test red on 664e0e5b, green after

Red: the changed test files run on a scratch export of `664e0e5b`'s `src` with this round's tests in place: "65 failed, 369 passed in 60.65s". Among them the grid test ("192 of 768" two-unreadable-reply cases), every `test_no_reply_text_reaches_the_log` arm, every `test_an_error_status_charge_writes_a_warning` arm, every above-ceiling charge arm, every key-shape arm and `test_a_5000_character_value_keeps_the_line_bounded`.

The M4 and M5 arms pass on `664e0e5b`, whose behaviour was already right; they bite under the adversary's mutations, each restored and compared after:

| Mutation | Result, pasted |
|---|---|
| M4: the batch invalid-option arm charged `parsed.cost_usd` | "1 failed, 342 passed", `[unusable, states $0 (A-GRS-06, M4)]` |
| M5: `_json_payload` catching `ValueError` only | "2 failed, 341 passed", the two "a body nested too deep" arms |
| `_unusable_reply` logging `detail` again | "2 failed, 72 passed", the two option-outside-the-set arms |
| The error-status warning removed from `_send` | "6 failed, 68 passed" |
| `_looks_like_a_credential` removed from `provider_of` | "7 failed, 36 passed", every key shape under 65 characters |
| `core/graph.py` back to "recoverable" | "4 failed, 44 passed" across the grid test and `test_followup_guardrail.py` |

Green after:

| Run | Result |
|---|---|
| `test_decision_grid_matches_develop.py` | "1 passed in 3.48s" |
| `tests/system_03_search_agent/guardrail` | "353 passed in 60.91s" |
| `tests/system_03_search_agent/harness` | "562 passed in 23.12s" |
| `synthesis/test_sentence_check.py` and `test_sentence_pair_check.py` | "146 passed in 3.69s" |
| `npx vitest run src/hooks/useRunView.retryAfter.test.ts` | "Tests  11 passed (11)" |
| `npx tsc --noEmit -p .` | exit 0 |
| `ruff check` (no path) | "All checks passed!" |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |

### Open after the fix round

- A provider name with a space, such as "Google AI Studio", now logs as "unknown", because a space is not in the host-name set the lead named. Allowing single spaces between words would keep those names.
- `core/graph.py` `_jev_injection_pick` keeps a comment that says "the ceiling when it states more", now stale; and `_log_step_failed` still logs two unreadable replies as "recoverable" while the wire class is "transient". Both are left because this round changes nothing else in `core/graph.py`.
- The grid test now applies one named change to develop's record (`_APPROVED_CLASS_CHANGES`), so it no longer passes with develop's `core/graph.py` in place; the JSON itself is unedited.
