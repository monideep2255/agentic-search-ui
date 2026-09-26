# Builder K, build phase 8.6: Jev decides, the guard tier only steps in when Jev fails

Tickets T-8.6-01, T-8.6-02 and T-8.6-03 (`tracker/phase_8.6.md`). Each finding is written here the moment it is established.

## Table of contents

- [Findings](#findings)
- [T-8.6-01](#t-86-01)
- [T-8.6-02](#t-86-02)
- [T-8.6-03](#t-86-03)
- [Tests and gates](#tests-and-gates)
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
  | Jev, one call, 30 two-option questions | 4 | 5 of 60, all "in children" rows, four at 0.51 to 0.54 and one at 0.79 | 0 of 60 | 340 to 450 ms, $0.00033 |
  | Guard tier today (deepseek/deepseek-v4-flash, today's exact prompt and parser) | 3 | 15 of 45: one call approved every item | 7 of 45: one call refused every hand-washing row | not timed, about $0.00007 |

  What the person reading an answer would notice:

  - With Jev, a sentence that adds something its source does not say slips through less often than with today's checker.
  - A faithful plain-language sentence was never refused by Jev.
  - Jev's slips sit near even odds. The sentence check follows the product owner's rule of 2026-09-25, no confidence threshold on Jev's decisions, so Jev's pick decides. Whether an approval should need more than even odds is the owner's call, and these numbers are the evidence for it.
  - A fifth, first run of the Jev probe had 2 wrong of 30 with the direction not printed.

- K-05 (fence, established running `tests/system_03_search_agent/test_debugging_guide_coverage.py`): the coverage test goes red on this branch, `test_no_repurposed_file_keeps_a_stale_row`, naming `harness/decide.py`. It is right to: `decide.py`'s docstring summary changed because the file's job changed, and `docs/build/Debugging_guide.md`'s row still says `decide()` "asks Jev and the guard tier the same closed-option question concurrently". The guide and `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json` are outside this builder's fence, and builder L's docstring changes will need the same two files, so the lead should apply the rows below once both branches are merged, then regenerate the manifest once with `python tests/system_03_search_agent/test_debugging_guide_coverage.py`. Keeping the old summary line to turn the test green would have hidden a stale row, so it was not done. The replacement rows are in [Debugging guide rows for the lead](#debugging-guide-rows-for-the-lead).

## T-8.6-01

What the person asking notices: with Jev switched on, each small choice the loop makes (is this on topic, ask back, how recent, papers or records) takes Jev's own time, 218 to 499 ms in every single-question live probe so far (builder D's three and this report's K-02), instead of Jev's time plus up to one second spent waiting on a second model whose pick was only written down. When Jev fails, the guard tier still answers, so the question is never held up by a Jev outage beyond Jev's 3-second limit plus the guard's own call.

What changed, `harness/decide.py` only; `decide()`'s signature is unchanged:

- `CLASSIFIER_PROVIDER=jev`: Jev is asked alone, through `_jev_attempt`, inside the same outer net as before (`_JEV_WAIT_S`, Jev's 3-second total bound plus 0.5 s). A valid pick returns at once with `decided_by="jev"`, `guard_choice` None, `agreed` None, `fallback_reason` None and Jev's latency.
- The guard tier is asked only after Jev failed, through `_guard_fallback_pick`, within its own 15-second step budget. The record names Jev's reason: `timeout`, `http_error`, `malformed_reply`, `invalid_option`, `cost_cap` or `unexpected_error`. Both failing still records `no_usable_pick:<reason>` with the caller's fail-open default, exactly as in build phase 8.2.
- Removed: the concurrent guard task, `GUARD_COMPARISON_GRACE_S`, `GUARD_NOT_READY` and the three task-reading helpers. `asyncio.wait_for` replaces the two tasks, so a caller that cancels a decision cancels Jev's call with it and nothing is left running.
- `CLASSIFIER_PROVIDER=guard`, the code default: the code path is byte for byte the one before this ticket.
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

Tests, all in `test_decide.py`, 53 in the file:

- New: Jev alone with the guard never called, even in the background; the three wall-time arms above; every failure path raised from the Jev pick itself, six arms including `cost_cap` refused for Jev while the guard's own check passes, and `unexpected_error`; an option outside the set and a reply missing its fields through the real `call_jev`; the guard asked after Jev (its start time is at least 2.9 s into a Jev timeout); the removed constants stay removed.
- Changed: each of the four `JevCallError` fallback arms now also asserts the guard was called exactly once; the state-cap arm reaches the guard through a Jev failure, since a Jev success no longer calls it; the cost arm asserts Jev's charge exactly.
- Kept unchanged: guard mode never calls Jev, the description tests, the parse tests, both-failing records, cancellation leaves no unretrieved asyncio error.

Break-it checks, each in a scratch copy of `src/` and `tests/` under `/private/tmp`, never in this worktree's `src/`:

- The pre-ticket `decide.py` (`git show HEAD:...`) against the new tests: 7 failed, including all three wall-time arms and "never asks the guard".
- The new `decide.py` with one background guard call put back beside Jev: 17 failed.

Regression: `tests/system_03_search_agent/core` and `tests/system_03_search_agent/guardrail`, outside the fence but the callers of `decide()`: 1391 passed, 56 skipped, 1 deselected.

## T-8.6-02

## T-8.6-03

## Tests and gates

## Debugging guide rows for the lead

Replacements for the rows in `docs/build/Debugging_guide.md`, outside this builder's fence (finding K-05). Paste each over the row with the same path, then regenerate the manifest once after merging.

`harness/decide.py`:

```text
| `src/system_03_search_agent/harness/decide.py` | The classifier seam: `decide()` answers one closed-option question and returns a `DecisionRecord`. With `CLASSIFIER_PROVIDER=jev` Jev is asked alone and the guard tier only when Jev fails (timeout, HTTP error, malformed reply, an option outside the set, the cost cap), with Jev's reason in `fallback_reason` (build phase 8.6); with the code default `guard` the guard tier decides alone. Each caller passes a fixed description of the decision (`instructions`, `criteria`) that either model receives. Wired in `core/graph.py`'s "classifier seam, wired" section, which lists every decision point. | A decision point's chosen option looks wrong (check that its description in `core/graph.py` says what is being decided), a fallback fired when it should not have (read `fallback_reason` on the `done` event's `decisions`), or the cost cap did not stop a decision call |
```
