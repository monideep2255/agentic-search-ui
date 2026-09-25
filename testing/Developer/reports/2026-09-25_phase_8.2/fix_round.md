# Build phase 8.2: the fix-and-verify round

The phase's one fix round, working the lead's triage of round 1 (`tracker/phase_8.2.md`, "Lead triage of round 1"). Each result is written here the moment it is established; the summary table sits above the log.

## Table of contents

- [Summary](#summary)
- [Item log](#item-log)
- [Findings left open, and why](#findings-left-open-and-why)

## Summary

Filled in as each item closes.

## Item log

- Base: `git merge --no-edit origin/phase/8.2-classifier-seam` into this worktree, clean. Baseline suite (harness, guardrail, core): 1602 passed, 56 skipped, 1 deselected.

### Item 1, F-8.2-A01: a follow-up is judged for relevancy like any other question

What the person notices: after an answered BRCA1 question, "and what about it in children?" is still answered, and "What is the best pizza in Chicago and is it cheap?" is refused with the usual off-topic sentence instead of running a paid search.

What changed, all in `core/graph.py`:

- `_relevancy_state` hands `guardrail.relevancy` the previous question when the new one is a memory-bound follow-up (a referring word and a remembered entity): `Previous question in this conversation: <open thread>` then `New question: <text>`. Any other question is judged on its own text, byte for byte as before. The previous question is the person's own earlier words, bounded at 200 characters by the memory contract, and `decide` caps the whole state again.
- The relevancy decision's instructions and criteria say a follow-up may point back at the previous question and that a follow-up about something unrelated is off topic.
- A real `off_topic` refuses a follow-up exactly as a first question (the `and not _is_memory_bound_follow_up` exemption is gone).
- Choice made from the user's chair: when the injection classifier's own off-topic verdict was set aside ONLY by the referring-word rule and the relevancy decision then has no usable pick (both models down), the classifier's verdict stands and the question is refused. Nothing that saw the conversation said it was on topic, and develop refused every allowlist miss outright, so this is never worse than develop. Where the classifier admitted the question, no usable pick still fails open, unchanged.
- `test_personalization_premise.py`'s list of functions allowed to read session memory gains `_relevancy_state`, with the reason.

Tests (`tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`, `decide` mocked): the pizza, football, weather and movie follow-ups are refused; a follow-up the classifier calls off topic and the decision calls on topic is admitted; the follow-up's state carries the previous question; a question with no referring word is judged on its own text; a set-aside verdict stands with no usable pick (two arms); a follow-up the classifier admits still fails open. The old arm that asserted the set-aside was replaced, since it pinned the defect.

Break-it checks, each on the worktree file copied aside and restored byte for byte (`cmp`):

- Restoring the follow-up exemption on the relevancy refusal: 4 failed (the four off-topic follow-ups).
- Sending the bare question instead of `_relevancy_state`: 1 failed (the state test).

Suite: harness, guardrail and core, 1611 passed, 56 skipped, 1 deselected.

Live, `CLASSIFIER_PROVIDER=jev`, real guard model and real Jev, real `guardrail_node`, memory holding a BRCA1 question (`probe_fix_round_live.py guardrail ... --memory`):

| Run | Question | Result | Relevancy record | Cost, time |
| --- | --- | --- | --- | --- |
| 1 | and what about it in children? | admitted, ok | Jev on_topic 1.0, guard on_topic | $0.00008, 2.7 s |
| 2 | What is the best pizza in Chicago and is it cheap? | refused, off_topic | Jev off_topic 1.0, guard off_topic | $0.00008, 2.1 s |

Live runs spent so far: 2 of 14.

### Item 4, F-8.2-J03, J04 and A12: a real total timeout on Jev, and no waiting on the comparison

What the person notices: with Jev switched on, a slow Jev can hold a decision for at most about 3 seconds, not 16; once Jev has answered, nobody waits for the guard model's comparison pick for more than one second; and when Jev fails, the guard model's answer is used whenever it has arrived.

What changed:

- `harness/jev_client.py`: `call_jev` wraps the whole POST, body read included, in `asyncio.wait_for(..., 3.0)`. httpx's timeout float is four per-phase limits, and its read limit is the gap between two chunks, which is why a trickling body lasted 14 seconds. `JEV_TOTAL_TIMEOUT_S` names the bound for `decide`.
- `harness/decide.py`: the `asyncio.gather` under a 16-second `wait_for` is replaced by two tasks waited on separately.
  - Jev is waited for up to `_JEV_WAIT_S` (its own 3-second bound plus 0.5 s, an outer net only).
  - Jev decided: the guard's comparison pick gets `GUARD_COMPARISON_GRACE_S = 1.0` second. One not ready by then is cancelled and the record says `fallback_reason: "guard_not_ready"` with `guard_choice` None. A dedicated field would be plainer, but `DecisionRecord` lives in `contracts/`, outside this fence, so the existing free-text field carries it and the constant documents the value.
  - Jev failed: the guard's pick decides, waited for within `_GUARD_FALLBACK_WAIT_S` (its own 15-second budget plus 1). The pick is read from the task itself, so one that has arrived is never discarded by an outer limit.
  - Anything still running when `decide` returns or is cancelled is cancelled in a `finally`, and every child task's exception is marked read, so no asyncio "never retrieved" ERROR is logged (this also fixes F-8.2-A05, see item 7).

Measured wall time of `decide()`, from `pytest --durations` on the new tests (`tests/system_03_search_agent/harness/test_decide.py`):

| Case | Fake Jev | Fake guard | decide() wall time | Decided by, record |
| --- | --- | --- | --- | --- |
| Jev in time, guard slow | answers at once | 5 s | 1.00 s | jev; `guard_not_ready`; the guard call cancelled |
| Jev in time, guard inside the grace | answers at once | 0.3 s | 0.30 s | jev; guard pick recorded, `agreed` false |
| Jev slow (real `call_jev`) | 5 s | 0.2 s | 3.00 s | guard; its 0.2 s pick used; `timeout` |
| Jev slow, guard slow | 5 s | 4 s | 4.00 s | guard; its 4 s pick used |
| Jev ignores its own bound and hangs | 30 s | 0.2 s | 3.50 s | guard; the arrived pick used, not discarded |

`call_jev` alone, `tests/system_03_search_agent/harness/test_jev_client.py`: a 5-second fake endpoint and a real httpx client fed a body in four pieces 1.5 s apart both end in `JevCallError(reason="timeout")` at 3.00 s.

Checked against the pre-fix `decide.py` (the committed file swapped in, then restored and `cmp`-verified): the slow-guard, hanging-Jev and cancellation tests all failed on it, 3 failed.

Suite: 1620 passed, 56 skipped, 1 deselected. The new timing tests add about 21 seconds to the run.

## Findings left open, and why

Filled in at the end.
