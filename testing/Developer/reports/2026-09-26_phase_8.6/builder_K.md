# Builder K, build phase 8.6: Jev decides, the guard tier only steps in when Jev fails

Tickets T-8.6-01, T-8.6-02 and T-8.6-03 (`tracker/phase_8.6.md`). Each finding is written here the moment it is established.

## Table of contents

- [Findings](#findings)
- [T-8.6-01](#t-86-01)
- [T-8.6-02](#t-86-02)
- [T-8.6-03](#t-86-03)
- [T-8.6-08](#t-86-08)
- [T-8.6-09](#t-86-09)
- [Tests and gates](#tests-and-gates)
- [Follow-ups for the lead](#follow-ups-for-the-lead)
- [Debugging guide rows for the lead](#debugging-guide-rows-for-the-lead)

## Findings

- K-01 (blocker for T-8.6-02's wiring, established on reading the code): the sentence check's model call is not made in `synthesis/sentence_check.py`. It is made in `core/graph.py::_ground_with_sentence_check`, which builds the messages with `build_sentence_check_messages`, dispatches the guard tier through `_dispatch_tier_call`, and parses with `approved_keys`. Nothing awaited on that path is inside this builder's fence, so the check cannot switch to Jev without a change to `core/graph.py`, which another builder owns in this phase. The plan: build the whole Jev path inside `sentence_check.py` as one awaitable, test it there, prove the wiring in a scratch copy under `/private/tmp`, and hand the exact `core/graph.py` hunk to the lead.

- K-02 (probe 1, live, 2026-09-26): the decisions endpoint has no `bool` question type. A `"type": "bool"` question is refused with HTTP 400 naming the three types it accepts: `noul`, `choice` and `score`. A `noul` question (only `instructions`, no options or criteria) is accepted and answers with one number, `{"type": "noul", "noul": 0.98}` for "Is the statement about the sky?" over "The sky is blue on a clear day.", 499 ms, $0.0000118. It carries no pick and no probabilities per option, so turning it into accept or reject would need a cut-off nobody has decided. A two-option `choice` question ("yes" or "no") is the boolean the sentence check uses: it returns a pick among the offered options plus a probability for each, the shape `decide()` already validates.

- K-03 (probe 2, live, 2026-09-26): the endpoint takes several questions in ONE call and answers each under its own key. Four `choice` questions (`item_1` to `item_4`, options "yes" and "no"), the four items numbered in one 604-character `state`, each question's code-authored instructions naming its item: HTTP 200 in 436 ms, $0.0000532, 1267 input tokens. All four verdicts were right:

  | Item | Sentence against its quote | Jev | Probabilities |
  | --- | --- | --- | --- |
  | 1 | "broken bones and kidney disease" for "bone fractures, chronic renal disease" | no, adds nothing | no 0.75, yes 0.25 |
  | 2 | "causes" for "is associated with" | yes, adds something | yes 1.0 |
  | 3 | "hand washing" for "hand hygiene" | no, adds nothing | no 0.94, yes 0.06 |
  | 4 | adds "in children", which the quote does not name | yes, adds something | yes 1.0 |

  So T-8.6-02 sends one call per answer, as the brief prefers, not one per sentence.

- K-04 (probes 3 and 4, live, 2026-09-26): at the 30-item cap (`MAX_CANDIDATES`), the four items above repeated, 4610-character state, 15 faithful and 15 unfaithful sentences per call:

  | Checker | Calls | Unfaithful sentences approved | Faithful sentences refused | Time, cost per call |
  | --- | --- | --- | --- | --- |
  | Jev, one call, 30 two-option questions | 4 | 5 of 60, all "in children" rows, four at 0.51 to 0.54 and one at 0.79 | 0 of 60 | 343 to 611 ms over five calls, $0.00033 |
  | Guard tier today (deepseek/deepseek-v4-flash, today's exact prompt and parser) | 3 | 15 of 45: one call approved every item | 7 of 45: one call refused every hand-washing row | not timed, about $0.00007 |

  What the person reading an answer would notice:

  - With Jev, a sentence that adds something its source does not say slips through less often than with today's checker.
  - A faithful plain-language sentence was never refused by Jev.
  - Jev's slips sit near even odds. The sentence check follows the product owner's rule of 2026-09-25, no confidence threshold on Jev's decisions, so Jev's pick decides. Whether an approval should need more than even odds is the owner's call, and these numbers are the evidence for it.
  - A fifth, first run of the Jev probe had 2 wrong of 30 with the direction not printed.

- K-06 (live, 2026-09-26, the final T-8.6-02 code): `check_reworded_sentences` with `CLASSIFIER_PROVIDER=jev`, the real endpoint and a guard stand-in that fails the run if it is ever asked, so every verdict below is Jev's:

  | Answer size | Runs | Wall time | Unfaithful sentences approved | Faithful sentences refused | Cost per answer |
  | --- | --- | --- | --- | --- | --- |
  | 4 sentences (2 faithful, 2 not) | 3 | 444 to 976 ms | 0 of 6 | 0 of 6 | $0.000061 |
  | 30 sentences (15 faithful, 15 not) | 3 | 365 to 574 ms | 2 of 45 | 0 of 45 | $0.00039 |

- K-05 (fence, established running `tests/system_03_search_agent/test_debugging_guide_coverage.py`): the coverage test goes red on this branch, `test_no_repurposed_file_keeps_a_stale_row`, naming `harness/decide.py`. It is right to: `decide.py`'s docstring summary changed because the file's job changed, and `docs/build/Debugging_guide.md`'s row still says `decide()` "asks Jev and the guard tier the same closed-option question concurrently". The guide and `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json` are outside this builder's fence, and builder L's docstring changes will need the same two files, so the lead should apply the rows below once both branches are merged, then regenerate the manifest once with `python tests/system_03_search_agent/test_debugging_guide_coverage.py`. Keeping the old summary line to turn the test green would have hidden a stale row, so it was not done. The replacement rows are in [Debugging guide rows for the lead](#debugging-guide-rows-for-the-lead).

## T-8.6-01

What the person asking notices: with Jev switched on, each small choice the loop makes (is this on topic, ask back, how recent, papers or records) takes Jev's own time, 218 to 499 ms in every single-question live probe so far (builder D's three and this report's K-02), instead of Jev's time plus up to one second spent waiting on a second model whose pick was only written down. When Jev fails, the guard tier still answers, so the question is never held up by a Jev outage beyond Jev's 3-second limit plus the guard's own call.

What changed, `harness/decide.py` only; `decide()`'s signature is unchanged:

- `CLASSIFIER_PROVIDER=jev`: Jev is asked alone, through `_jev_attempt`, inside the same outer net as before (`_JEV_WAIT_S`, Jev's 3-second total bound plus 0.5 s). A valid pick returns at once with `decided_by="jev"`, `guard_choice` None, `agreed` None, `fallback_reason` None and Jev's latency.
- The guard tier is asked only after Jev failed, through `_guard_fallback_pick`, within its own 15-second step budget. The record names Jev's reason: `timeout`, `http_error`, `malformed_reply`, `invalid_option`, `cost_cap` or `unexpected_error`. Both failing still records `no_usable_pick:<reason>` with the caller's fail-open default, exactly as in build phase 8.2.
- Removed: the concurrent guard task, `GUARD_COMPARISON_GRACE_S`, `GUARD_NOT_READY` and the three task-reading helpers. `asyncio.wait_for` replaces the two tasks, so a caller that cancels a decision cancels Jev's call with it and nothing is left running.
- `CLASSIFIER_PROVIDER=guard`, the code default: the guard-only branch is unchanged, and so are its tests. T-8.6-02 later moved its one condition into `jev_decides()`, the same expression.
- One `logger.warning` per Jev failure names the decision point, the trace and the reason, never the state.

Measured wall time of `decide()`, `pytest --durations=0` on the tests in `tests/system_03_search_agent/harness/test_decide.py`:

| Case | Fake Jev | Fake guard | decide() wall time | Decided by, record |
| --- | --- | --- | --- | --- |
| Jev answers at once | 0 s | 5 s, must not start | 0.00 s | jev; the guard never started |
| Jev answers fast | 0.05 s | 5 s, must not start | 0.05 s | jev; the guard never started |
| Jev answers slowly | 0.4 s | 5 s, must not start | 0.40 s | jev; the guard never started |
| Jev fails at once (HTTP error) | fails | 1.5 s | 1.50 s | guard; `http_error` |
| Jev slow, real `call_jev` | 5 s, cut at 3 s | 0.2 s, started at 3 s or later | 3.20 s | guard; `timeout` |
| Jev ignores its own bound | hangs | 0.2 s | 3.70 s | guard; `timeout` at the outer net |

The first three rows are the acceptance: the decision takes Jev's time, not Jev's time plus a grace. Build phase 8.2's design took 1.00 s in the same "Jev in time, guard slow" case.

Tests, all in `test_decide.py`, 53 in the file at this ticket's commit:

- New: Jev alone with the guard never called, even in the background; the three wall-time arms above; every failure path raised from the Jev pick itself, six arms including `cost_cap` refused for Jev while the guard's own check passes, and `unexpected_error`; an option outside the set and a reply missing its fields through the real `call_jev`; the guard asked after Jev (its start time is at least 2.9 s into a Jev timeout); the removed constants stay removed.
- Changed: each of the four `JevCallError` fallback arms now also asserts the guard was called exactly once; the state-cap arm reaches the guard through a Jev failure, since a Jev success no longer calls it; the cost arm asserts Jev's charge exactly.
- Kept unchanged: guard mode never calls Jev, the description tests, the parse tests, both-failing records, cancellation leaves no unretrieved asyncio error.

Break-it checks, each in a scratch copy of `src/` and `tests/` under `/private/tmp`, never in this worktree's `src/`:

- The pre-ticket `decide.py` (`git show HEAD:...`) against the new tests: 7 failed, including all three wall-time arms and "never asks the guard".
- The new `decide.py` with one background guard call put back beside Jev: 17 failed.

Regression: `tests/system_03_search_agent/core` and `tests/system_03_search_agent/guardrail`, outside the fence but the callers of `decide()`: 1391 passed, 56 skipped, 1 deselected.

## T-8.6-02

What the person reading an answer notices, once the wiring below lands: a plain-language sentence written from a paper or record is judged by Jev, in one call for the whole answer that took 365 to 976 ms live, instead of a guard-tier call. In the probes Jev let fewer invented details through than the guard tier and never refused a faithful sentence (K-04, K-06). When Jev fails, today's guard check runs instead if at least 2 seconds are left, so a Jev outage costs nothing but time. Nothing that code decides changed.

What changed:

- `harness/jev_client.py`: `call_jev_batch` sends several `choice` questions over one shared `state` in one call and returns a `JevBatchResult`, one validated `JevAnswer` per question. It is strict: every question asked must be answered under its own key, no other key may appear, and an answer outside its question's options fails the whole reply. It keeps `call_jev`'s 3-second total bound, which a caller may shorten but never lengthen; a bound of zero is refused before any request. At most 30 questions, the reported cost capped at $0.01 per call, every question's text at 1000 characters, no retries. `call_jev` now shares one transport helper, `_send`, with the same error messages as before.
- `harness/decide.py`: `jev_decides()`, the one reading of `CLASSIFIER_PROVIDER`, used by `decide()` and the sentence check so the two can never disagree.
- `synthesis/sentence_check.py`: `check_reworded_sentences(candidates, *, harness, trace_id, budget_s, ask_guard)`, the one entry point.
  - Guard mode, the code default: one `ask_guard` call with `build_sentence_check_messages(candidates)` and the whole budget, parsed by `approved_keys`. The messages are byte-identical to the committed version (three cases compared by SHA-256, including 40 over-long items and a hostile sentence).
  - Jev mode: one `call_jev_batch` call. The state is the same numbered items the guard reads, whole items only, at most 30 and at most 30,000 characters. One question per item, `item_1` to `item_n`, options "yes" and "no", asking "does its SENTENCE say anything its QUOTES do not?" with `SENTENCE_CHECK_INSTRUCTION`'s rules. Only "no" approves. Cap-checked before the call, and Jev's cost charged after, like `decide()`.
  - After a Jev failure (timeout, HTTP error, malformed or unreadable reply, an answer outside the two options, anything unexpected), the guard is asked exactly as in guard mode with what is left of the budget, only when at least `GUARD_FALLBACK_MIN_S` (2 s) is left.
  - It raises only what `core/graph.py` already catches: the cost cap (no guard call after a Jev cap refusal), `HarnessCallError`, `SentenceCheckUnreadable`. Each approves nothing.
- Not changed: `SENTENCE_CHECK_INSTRUCTION`, `approved_keys`, the exact checks in `grounding.py`, `MAX_CANDIDATES`.

The wiring, blocked by the fence (K-01): `core/graph.py::_ground_with_sentence_check` must call `check_reworded_sentences`, passing a closure that makes today's `_dispatch_tier_call(..., "guard", "write", messages, budget_s=..., max_tokens=256, cache_prefix=None)` call. The exact hunk, plus three graph-level tests that need it, is in `sentence_check_wiring.patch` in this folder. It applies cleanly to this branch (`git apply --check`), and results from running it in a scratch copy are below. Until it is applied, the loop makes today's guard call and nothing the person sees changes.

Tests, `tests/system_03_search_agent/synthesis/test_sentence_check.py` (62, 33 of them new) and `tests/system_03_search_agent/harness/test_jev_client.py` (32, 15 of them new):

- Guard mode: one call with today's messages byte for byte and the whole budget, parsed by today's parser, Jev never called, for the provider unset, `guard`, `GUARD` with a trailing space, and any other value; it raises only what the caller already catches; no candidates asks nobody.
- Jev mode: one call, one yes-or-no question per sentence with its item number, Jev's own 3-second bound or less when less is left, only "no" approves, the cost is capped first and charged after, an unanswered, unasked or out-of-option verdict is unreadable.
- Fails closed: the cost cap asks nobody; a failed Jev then a failed or unreadable guard approves nothing; too little time after a Jev failure skips the guard; a zero budget sends nothing at all, through the real client.
- Falls back: each Jev failure (timeout, HTTP error, malformed reply, invalid option, an unexpected error, an unreadable verdict) with time left asks today's guard check with what is left.
- The exact checks stay in front: a sentence with a quote not in the record, a number in no quote, or a flipped negation never reaches Jev; a faithful rewording does, and Jev's "no" lets the second grounding pass accept it.
- Bounds: past 30 items nothing is sent or approved; whole items only up to the state cap; a hostile sentence travels as a JSON string in the state and never in a question.
- The batch call: one request for every question, strict key matching, options per question, an impossible cost, a shorter caller bound, a bound that cannot be lengthened, a zero bound never sent, no retries, and bad batches refused in code.

Break-it checks, each on a scratch copy under `/private/tmp`, restored and compared byte for byte (`filecmp`, shallow off) after every run; baseline 62 passed:

| Guarantee broken | Tests that went red |
| --- | --- |
| The exact checks stop running in front (`exact_synthesis_checks_pass` always true) | 7, including every "never reaches Jev" arm |
| Guard mode asks Jev instead | 4, every guard-mode arm |
| The guard is also asked after Jev answers | 12 |
| A "yes" approves too, which would widen what it accepts | 2 |
| An unmatched set of answers is read anyway | 2 |
| An answer outside "yes" and "no" is read anyway | 1 |
| The cost cap falls back to the guard instead of approving nothing | 1 |
| Too little time still asks the guard | 3 |
| A failed guard after a failed Jev approves everything | 1 |
| No fallback to the guard after a Jev failure | 7 |
| Sentences past the 30-item cap are sent | 1 |
| The sentence travels as bare text instead of a JSON string | 2 |
| Jev's cost is not charged | 1 |
| Batch call: a reply with the wrong keys is read anyway | 3 |
| Batch call: an answer outside its options is read anyway | 1 |
| Batch call: a caller can lengthen Jev's total bound | 1 |

The wiring patch, applied to a scratch copy:

- `test_sentence_check.py` with the three graph-level tests: 65 passed.
- `tests/system_03_search_agent/core`, `guardrail` and `synthesis` together: 1897 passed, 66 skipped, 1 deselected, 1 xfailed.
- The three graph-level tests against today's unwired `core/graph.py`: the two Jev-mode arms go red; the fallback arm passes, since the guard call it checks has the same shape before and after the wiring.

## T-8.6-03

What the product owner gets, at no cost to anyone asking a question, since no live path runs it:

- For each decision point, how often Jev and the guard tier agree on this product's own questions.
- How fast each model answered.
- Every case where they differ, with Jev's confidence.

What was built:

- `harness/decide.py`: `compare_models(harness, trace_id, point, state, options, *, instructions, criteria)` asks Jev and the guard tier the same decision at the same time, through the same bounded state, description, cost-cap checks and time bounds `decide()` uses, whatever `CLASSIFIER_PROVIDER` says. It returns a `ModelComparison`, whose `live_record(default)` is the record Jev-mode `decide()` returns for those picks. Both paths build that record through one helper, `_jev_mode_record`, so they cannot drift apart.
- `testing/Developer/scripts/compare_classifiers.py`: given golden ids (or `--all`), it runs the loop's own Guardrail, Think and Plan steps per question, never Act or Write, with every module-level `decide` the loop imported swapped for a recorder. The recorder asks `compare_models`, records both picks, and hands the loop the live record, so the loop takes develop's path. A comparison the loop stops waiting for, such as the literature decision cancelled once a gene resolves or a relevancy decision the refusal made moot, still finishes and is recorded, marked "the loop had moved on".
- Spend bound in code: the budget (`--budget-usd`, default $0.50) divided by the number of questions becomes the per-query cost cap the harness checks before every model call. Below $0.02 per question the script refuses before reading any credential, since Think's own call would be refused.
- It finds the repository from its own path and reads `.env` from this checkout's root, or for a worktree from the main checkout's root, through `git rev-parse --git-common-dir`, never printing a value. It names no absolute path.
- Its docstring and every report it writes state what it does not compare.

The live run, `classifier_comparison.md` in this folder, 10 golden questions chosen to reach every decision point (G-003, G-008, G-009, G-013, G-021, G-022, G-030, G-038, G-042, G-050):

| Decision point | Asked | Agreed | Jev median ms | Guard median ms |
| --- | --- | --- | --- | --- |
| `guardrail.relevancy` | 4 | 4 | 314 | 1234 |
| `plan.literature` | 7 | 7 | 266 | 1334 |
| `think.recent_years` | 7 | 7 | 270 | 947 |

- K-07: 18 of 18 decisions agreed, $0.0097 spent under the $0.50 budget, 46 s.
- K-08: the script ran twice, because the first report's opening paragraph failed the house style check (a four-item comma chain) and the committed file had to be the script's own output. The first run, minutes earlier, also cost $0.0097, so about $0.02 was spent in all. It disagreed once, on G-009, "the": Jev off_topic at 0.84 (probabilities 0.92 and 0.08), the guard tier on_topic. In the second run the guard tier said off_topic and Jev said the same as before. On this one question Jev was the steadier of the two.
- K-09: Jev answered each decision three to five times faster than the guard tier (median 266 to 314 ms against 947 to 1334 ms), which is what T-8.6-01 now gives every question.
- K-10 (coverage): no golden question reaches `think.ask_back`. It is asked only for a first message of one to three words, and the golden set's only two, G-008 "334" and G-009 "the", are refused at the guardrail before Think runs. `guardrail.relevancy` was asked for 4 of the 10, since the biomedical word list admits the rest without a model. Comparing ask-back needs short questions the guardrail admits, which the golden set does not have.
- K-14 (reported by the lead after merging both builders' branches, reproduced here): `test_the_recorder_compares_hands_back_the_live_record_and_survives_a_cancel` called `_install_recorder`, which swaps `decide` on EVERY loaded `system_03_search_agent.*` module still holding the original, `core.graph` included once any earlier test had imported it, and nothing put them back. Every later test that relied on `core.graph.decide` then ran through the recorder. Reproduction, `tests/system_03_search_agent/harness/test_compare_classifiers_script.py` with `core/test_graph.py::test_a_decision_nobody_made_is_recorded_as_what_the_run_did`: 4 failed, 7 passed. My own runs did not catch it: in `harness/` and `synthesis/` no test after this one goes through `core.graph.decide`, and I ran `core/` in a separate process.

  Fixed in two places. `_install_recorder` now returns `(patched, uninstall)`, and `_run` calls `uninstall` in a `finally`, so the script leaves every module as it found it. The test also registers every loaded module's `decide` with `monkeypatch` before the recorder touches it, so teardown restores them even when the test fails midway, and it asserts `uninstall` put them back. After the fix, the lead's reproduction command: 11 passed. `tests/system_03_search_agent/harness` and `core` in one process: 1502 passed, 56 skipped, 1 deselected.
- K-11: the plan tier in this local run was the code default, `moonshotai/kimi-k2.6`, because the main checkout's `.env` does not set `PLAN_MODEL`, while develop overrides it to `deepseek/deepseek-v4-flash`. That model runs Think's own classification, which is not compared; the report states it. The script does not pin a model id, since model identity belongs to the environment (`system-design-patterns` pattern 11).

Tests:

- `test_decide.py`, 12 new: `compare_models` asks both models whatever the provider, with the same description; it asks them at the same time (two 0.4-second models finish under 0.7 s); for five combinations of Jev and guard behaviour, its `live_record` equals what `decide()` returns in Jev mode; a bad default and bad options are refused as `decide()` refuses them; nothing under `src/` but `decide.py` names `compare_models`, `ModelComparison` or the script.
- `test_compare_classifiers_script.py`, 7: the repository is found from the script's own path and the source names no absolute path; a budget below $0.02 per question refuses before credentials are read; an unknown golden id stops the run; ids come back in order; the recorder hands back the live record and a cancelled wait still records the finished comparison; the report's agreement row, disagreement row and failure row, and the "None" line when nothing disagreed.

## T-8.6-08

Added by the lead from the product harness review (`testing/Developer/reports/2026-09-25_harness_review/product_harness.md` in the main checkout, W6, W7, C4, C5, C6).

- K-12 (on reading the code): the operator-only `cost` event is not built in `harness/harness.py`. `harness/cost_control.py::build_cost_event_payload(harness, trace_id, tier)` builds it, and `core/graph.py` calls it after each metered model call. A new optional field on `CostPayload` would stay empty unless that builder fills it, so T-8.6-08 adds two lines there that read the new timing from the harness. `cost_control.py` is outside the lead's file list for this ticket but inside no other builder's fence; `core/graph.py` is not touched.
- K-13 (litellm as installed): the 400 in W6 reaches `call_tier` as `litellm.BadRequestError`, and `str(exc)` carries the provider's own words: `litellm.BadRequestError: OpenrouterException - {"error":{"message":"Reasoning is mandatory for this endpoint and cannot be disabled.","code":400}}`. `ContextWindowExceededError`, `ContentPolicyViolationError` and `UnsupportedParamsError` are subclasses of it, so the fallback is keyed on the text naming reasoning, not on the class alone.

What the product owner and the person asking notice:

- A writer model that cannot turn reasoning off now answers instead of failing every question with "A step in this query could not complete as requested". The frontier-writer bench can measure answer quality rather than a request-shape clash (W6). Develop's models accept `effort: none`, so nothing changes there.
- A model deployed with no known price fails before the provider is asked, so nobody pays for a reply that is then thrown away, and the error says where to add the price (W7).
- Each model call's time sits beside its cost: on `LLMResponse.elapsed_s`, and as `call_elapsed_s` on the operator-only `cost` event. The next speed decision (W9) can be read from the event stream.

What changed:

- `harness/harness.py`, `call_tier`:
  - The price is looked up before anything is sent; the success path and the cancelled-call metering reuse it.
  - A `BadRequestError` whose text names reasoning is retried once, the same request with the `reasoning` block removed, logged by model and tier. A second refusal raises as before, classed `recoverable`.
  - The fallback and the transient retry are separate, each at most once, in either order, so one call sends at most three requests.
  - The fallback is per call and never remembered. One stray 400 must not take the reasoning dial away from every later call in the process; the measured cost of reasoning on this product's synth tier was 20 to 45 seconds and timeouts (`_TIER_REASONING`'s own comment). Reading `supported_parameters` once per process, the review's other option, stays open.
  - `elapsed_s` covers the whole call, retries included, since the person waited for them. It is kept per trace and tier for `last_call_elapsed_s`, and not recorded for a call that failed or was cancelled.
- `contracts/events.py`: `CostPayload.call_elapsed_s: float | None`, default None, at least 0. Additive within v1; every existing payload still validates.
- `harness/cost_control.py`, outside the lead's file list (K-12): `build_cost_event_payload` fills `call_elapsed_s` from `harness.last_call_elapsed_s(trace_id, tier)`, read defensively so a stand-in harness leaves it None. The end-user filter is untouched and still drops every `cost` event.
- Not changed: `_TIER_REASONING`, `_TIER_MAX_TOKENS`, the budgets, `_price_per_token` and its message, `core/graph.py`.

Tests, all passing: `test_harness.py` (49, 12 new), `test_cost_control.py` and `contracts/test_events.py` (247 together, 7 new).

- C4: the W6 text replayed through `litellm.BadRequestError` is retried once without the block and logged, with the same messages and `max_tokens`, and only the answer is metered. A second refusal is not retried and keeps the provider's words. A 400 that does not name reasoning is not retried. The fallback and the transient retry are separate, in both orders. The next call sends the block again.
- C6: an unpriced model raises `unexpected` from `harness.harness._price_per_token`, with the same message, before `acompletion` is called, and nothing is metered. A priced model is priced, then called.
- C5: `elapsed_s` matches a 0.2-second fake call, is kept per tier and per query, includes a retry, and is not recorded for a failed call. The cost event carries it, is None for a tier with no completed call, still builds from a harness that has no timing, and is still dropped by the end-user filter. The contract accepts the field, defaults it, rejects a negative value and still forbids unknown fields.

Break-it checks, each on a scratch copy under `/private/tmp`, restored byte for byte after every run. The copy lacks the repository's alembic migrations and a shipped-defaults file, so 3 `test_cost_control.py` tests fail and 6 error in every row including the baseline; the counts below are the tests that went red beyond those:

| Guarantee broken | New red tests |
| --- | --- |
| No fallback on a reasoning refusal | 5 |
| The fallback repeats without limit | 1 |
| The retry keeps the reasoning block | 3 |
| The fallback uses up the transient retry | 1 |
| Any bad request counts as a reasoning refusal | 2, including the pre-existing recoverable-without-retry test |
| The price is looked up after the call again | 2 |
| The call's time is not kept for the cost event | 1 |
| The response carries no time | 2 |
| The time starts after a retry | 1 |
| The cost event drops the time | 2 |
| The contract accepts a negative time | 1 |

## T-8.6-09

Added by the lead from the same review (C5, the golden client half).

## Tests and gates

Run after T-8.6-03's commit, on this worktree:

| Gate | Result |
| --- | --- |
| `python3 -m pytest -m "not integration" -q -p no:cacheprovider tests/system_03_search_agent/harness tests/system_03_search_agent/synthesis` | 820 passed, 10 skipped, 1 xfailed |
| The same over `tests/system_03_search_agent/core` and `guardrail`, the callers of `decide()`, outside the fence | 1391 passed, 56 skipped, 1 deselected |
| `ruff check .` over the whole repository | All checks passed |
| `isort --check-only` on every changed Python file | clean |
| `check_style.py` on `docs/architecture/Model_architecture.md` | 0 hard, 0 advisory |
| `check_style.py` on this report and on `classifier_comparison.md` | 0 hard, 1 advisory each (no Mermaid diagram) |
| `tests/system_03_search_agent/test_debugging_guide_coverage.py` | red on `harness/decide.py`, by design until the lead applies the rows below (K-05) |

Live spend by this builder, all metered: probes $0.0019 (K-02 to K-04), the final sentence check $0.0014 (K-06), the comparison script $0.0194 over two runs (K-07, K-08). About $0.023 in total.

## Follow-ups for the lead

Each is outside this builder's fence:

- Apply `sentence_check_wiring.patch` (this folder) once builder L's `core/graph.py` has merged: `git apply testing/Developer/reports/2026-09-26_phase_8.6/sentence_check_wiring.patch`, or the one hunk by hand if the context moved. Until then the reworded-sentence check stays on the guard tier. After it lands, `docs/architecture/Model_architecture.md`'s sentence-check row and Jev bullet can drop their "until then" clauses.
- Paste the three rows below into `docs/build/Debugging_guide.md`, then regenerate the manifest once for both builders' changes (K-05).
- `contracts/events.py`: `DecisionRecord`'s docstring still says the guard tier decides "alongside" Jev "purely for this record". Since T-8.6-01 the live seam fills `guard_choice` only on a fallback and `agreed` never; the comparison lives in the script's report now.
- `harness/task_tiers.py`: the comment on the "classifier" tier still says `decide` dispatches the guard tier and Jev concurrently, and the `write.sentence_check` row names the guard tier; it becomes Jev-first once the wiring patch lands.
- `docs/architecture/Model_architecture.md` outside the Jev section and table rows: the sequence diagram's participant "Sentence check: guard" and the guard tier's list of jobs still name the sentence check as guard-only.
- For the product owner (K-04, K-06): whether a Jev approval of a reworded sentence should need more than even odds. Measured across the Jev probes (K-03, K-04, K-06): 7 of 113 unfaithful sentences approved, most near even odds, and none of 113 faithful ones refused.
- For the product owner (K-10): the golden set cannot exercise `think.ask_back`; comparing it needs short opening questions the guardrail admits.

## Debugging guide rows for the lead

Replacements for the rows in `docs/build/Debugging_guide.md`, outside this builder's fence (finding K-05). Paste each over the row with the same path, then regenerate the manifest once after merging.

`harness/decide.py`:

```text
| `src/system_03_search_agent/harness/decide.py` | The classifier seam: `decide()` answers one closed-option question and returns a `DecisionRecord`. With `CLASSIFIER_PROVIDER=jev` Jev is asked alone and the guard tier only when Jev fails (timeout, HTTP error, malformed reply, an option outside the set, the cost cap), with Jev's reason in `fallback_reason` (build phase 8.6); with the code default `guard` the guard tier decides alone. Each caller passes a fixed description of the decision (`instructions`, `criteria`) that either model receives. Wired in `core/graph.py`'s "classifier seam, wired" section, which lists every decision point. Also holds `compare_models`, the offline side-by-side comparison, which no live path calls (its caller is `testing/Developer/scripts/compare_classifiers.py`). | A decision point's chosen option looks wrong (check that its description in `core/graph.py` says what is being decided), a fallback fired when it should not have (read `fallback_reason` on the `done` event's `decisions`), or the cost cap did not stop a decision call |
```

`harness/jev_client.py`, whose summary line did not change, so the coverage test does not flag it; the row no longer mentions the batch call:

```text
| `src/system_03_search_agent/harness/jev_client.py` | The HTTP calls to OpenRouter's alpha decisions endpoint (Jev): `call_jev` asks one question, `call_jev_batch` asks up to 30 over one shared state in one call (build phase 8.6). Request and response shapes pinned live on 2026-09-25 and 2026-09-26, a 3-second total timeout a caller may shorten but never lengthen, no retries, strict validation of every answer. The caller's description of a decision rides in the endpoint's own `instructions` and `criteria` fields, never in `state`. | A Jev call raises, times out, or a response fails schema validation |
```

`synthesis/sentence_check.py`, whose summary line did not change either; the row calls the check guard-tier only:

```text
| `src/system_03_search_agent/synthesis/sentence_check.py` | 2026-09-23, items 12.9 and 12.10: the model check on REWORDED answer sentences, the one bounded exception to deterministic acceptance, approved by the product owner. `check_reworded_sentences` is the entry point: the guard tier by default, and with `CLASSIFIER_PROVIDER=jev` one Jev call per answer with a yes-or-no question per sentence, falling back to the guard tier only when Jev fails and 2 seconds remain (build phase 8.6). Open it when a reworded sentence ships that says more than its quote (the prompt, or Jev's question text), or when prose that should survive is stripped (look for `sentence check approved nothing` in the logs: an unreadable reply, a failed call, the cost cap or too little budget all fail closed). The exact checks in front of it are `grounding.exact_synthesis_checks_pass`; the two-pass wiring is `core/graph.py`'s `_ground_with_sentence_check` |
```
