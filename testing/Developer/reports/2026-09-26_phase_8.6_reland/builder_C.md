# Builder C report, R-05 to R-09, phase 8.6 re-land follow-up

Builder C worked the re-land follow-up's tickets R-05 to R-08. The lead added R-09 during the run, from the product owner's decision "Back to 30 seconds". Each ticket was reproduced with the reviewers' probes before it was fixed and measured again after. Each got tests, and each fix was broken once to show the tests go red.

## Table of contents

- [Summary](#summary)
- [Base and commits](#base-and-commits)
- [R-07: every unreadable Jev reply is charged inside its ceiling](#r-07-every-unreadable-jev-reply-is-charged-inside-its-ceiling)
- [R-05: the classifier's second attempt waits, and a provider's Retry-After is honoured](#r-05-the-classifiers-second-attempt-waits-and-a-providers-retry-after-is-honoured)
- [R-06: a refusal is not held for a failing Jev decision](#r-06-a-refusal-is-not-held-for-a-failing-jev-decision)
- [R-08: the documents and the parse-failure message](#r-08-the-documents-and-the-parse-failure-message)
- [R-09: the graph search's time limit is 30 seconds again](#r-09-the-graph-searchs-time-limit-is-30-seconds-again)
- [What must stay true, with its evidence](#what-must-stay-true-with-its-evidence)
- [Checks](#checks)
- [Left for the lead](#left-for-the-lead)

## Summary

| Ticket | What the person using the product notices | Status |
|---|---|---|
| R-07 | Nothing directly: a Jev reply the provider billed is never charged $0 on their question, so the cost cap sees it | done |
| R-05 | A provider error of a second or two no longer ends their question; they get an answer about two seconds later | done, with one acceptance gap named below |
| R-06 | During a Jev outage, an off-topic or injection refusal arrives in under four seconds instead of up to fifteen | done, with one category difference named below |
| R-08 | Two unusable classifier replies now say "Retrying the query may succeed" instead of naming an internal part | done inside the fence; three files left outside it |
| R-09 | A graph search that is going to fail now fails at 30 seconds, not 90 | done |

Live spend: $0. Every probe stubbed the model and HTTP seams.

## Base and commits

Base: `a5c89bb`, branch `feat/8.6f-c`, cut from `phase/8.6-followup`. Nothing was pushed.

- `8e0098d` fix(harness): charge every unreadable Jev reply inside its ceiling (R-07)
- `a57230d` fix(guardrail): wait before the classifier's second attempt, and honour a provider's Retry-After (R-05)
- `94c82bc` fix(guardrail): do not hold a refusal for a failing Jev decision that cannot change it (R-06)
- `41b19f3` fix(guardrail): tell the person what to do when the classifier gives no usable verdict, and correct the documents (R-08)
- `dd300cb` fix(cypher-query): bring the graph search's time limit back to 30 seconds (R-09)
- `a73f89f` test(harness): a non-JSON 200 from Jev is charged the ceiling, as R-07 requires. Outside the fence, see [Left for the lead](#left-for-the-lead)
- `833055c` test(harness): satisfy ruff in the R-07 cost tests
- `3614808` test(cypher-query): keep P12b's floor mutation able to fail at the 30 s floor (R-09)
- `ee6a5c4` test(guardrail): give R-05's budget arms room for a loaded machine

## R-07: every unreadable Jev reply is charged inside its ceiling

The fix, in `harness/jev_client.py`:

- `call_jev` and `call_jev_batch` catch `OverflowError` with their other malformed-reply errors, so an integer too large for a float in `cost`, `confidence` or a probability no longer escapes as `unexpected_error` charged $0.
- The body is read by `_json_payload`, which charges `MAX_JEV_COST_USD` for a 200 whose body is empty or not JSON, and logs that amount.

Before and after, the judge's `r04.py` (all three charge sites):

```text
before 10**400           | decide: charged=4.89216e-06 by=guard fb=unexpected_error guard_calls=1 | injection_pick: charged=0.0 result=unexpected_error | sentence_check: charged=0.0 raised=OverflowError:
after  10**400           | decide: charged=0.01000489216 by=guard fb=malformed_reply guard_calls=1 | injection_pick: charged=0.01 result=malformed_reply | sentence_check: charged=0.01 raised=JevCallError:malformed_reply
before 200 non-JSON body | decide: charged=4.89216e-06 by=guard fb=malformed_reply guard_calls=1 | injection_pick: charged=0.0 result=malformed_reply | sentence_check: charged=0.0 raised=JevCallError:malformed_reply
after  200 non-JSON body | decide: charged=0.01000489216 by=guard fb=malformed_reply guard_calls=1 | injection_pick: charged=0.01 result=malformed_reply | sentence_check: charged=0.01 raised=JevCallError:malformed_reply
```

The `200 empty body` line changed the same way. The adversary's `p_r04_shapes.py`:

```text
before inj  huge int 10**400         result=unexpected_error charged=0.0
after  inj  huge int 10**400         result=malformed_reply charged=0.01
before inj  huge confidence          result=unexpected_error charged=0.0
after  inj  huge confidence          result=malformed_reply charged=0.001
```

A reading the ticket's words do not settle: the acceptance says a reply whose confidence overflows is charged the ceiling. The code's rule, stated in `JevCallError`'s docstring, is that a reply stating a usable cost within the ceiling is charged that cost. So a reply whose confidence overflows but whose cost reads $0.001 is charged $0.001, the same as a reply whose confidence is the string "abc". I kept the code's rule, which RJ05 asked for (two unreadable replies priced alike). A huge confidence with an unusable cost is charged the ceiling.

Tests: `tests/system_03_search_agent/harness/test_jev_followup_costs.py`, 24 tests, through `call_jev`, `call_jev_batch` and the three charge sites on a real `Harness`, plus the warning's text.

Broken three ways, each red:

- `OverflowError` removed from `call_jev`: 6 failed;
- `OverflowError` removed from `call_jev_batch`: 3 failed;
- the non-JSON charge set to 0.0: 12 failed.

## R-05: the classifier's second attempt waits, and a provider's Retry-After is honoured

The fix, in `core/graph.py`, applies with `CLASSIFIER_PROVIDER` unset and with Jev, since R-01's second attempt did:

- After an error, the second attempt waits 2 s (`_CLASSIFIER_RETRY_BACKOFF_S`), shortened so it keeps at least 3 s (`_CLASSIFIER_MIN_SECOND_ATTEMPT_S`), and 0 when even that is not left.
- After a 429 whose `Retry-After` the provider stated, it waits that long, at least the backoff, when 3 s still remain after. When they do not, there is no second attempt and the step error comes at once.
- After a first attempt that ran out of its own time (a hang, G-005), there is no wait, as R-01 made it.

Before and after, the judge's `pg.py` plus three `Retry-After` scenarios, provider unset:

```text
before blip 1.0 s        wall=  0.01s step_error=transient requests=4 gaps=[0.0, 0.0, 0.0]
after  blip 1.0 s        wall=  2.02s guard=passed ok      requests=3 gaps=[0.0, 2.0]
before 429 storm         wall=  0.02s step_error=transient requests=4 gaps=[0.0, 0.0, 0.0]
after  429 storm         wall=  2.06s step_error=transient requests=4 gaps=[0.01, 2.0, 0.01]
before 429, Retry-After 20  requests=4 gaps=[0.0, 0.0, 0.0]
after  429, Retry-After 20  wall= 0.01s requests=2 gaps=[0.0]
```

The adversary's `p_r01.py` on the final tree: `429 on every request  wall=  2.00s requests=4 gaps=[0.0, 2.002, 0.0]`, against `wall=  0.00s requests=4 gaps=[0.0, 0.0, 0.0]` on base. Every other `p_r01.py` line kept its outcome.

The acceptance gap, named: "a rate-limited provider receives fewer requests than today's four back-to-back ones".

- A persistent 429 now reaches the provider as two requests, a gap of at least 2 s, then two more. Never more than two go back to back, but the total is still four.
- The pair inside each attempt is `call_tier`'s own immediate transient retry in `harness/harness.py`, outside this fence. Four only drops to two when the provider's stated wait does not fit.
- To reach fewer than four, `call_tier` must stop retrying a 429 at once, which is a harness change.

Why a 429 that names no wait is retried after the backoff rather than not at all:

- From the person's chair, a rate limit that clears in two seconds then gets them an answer.
- `test_reland_guardrail.py`, outside this fence, pins that a rate-limited first attempt is retried.

Tests, in `tests/system_03_search_agent/guardrail/test_followup_guardrail.py`:

- the wait for every failure shape;
- `Retry-After` read from each place litellm keeps it, and as a date;
- three real-budget arms: the one-second blip, the storm's spacing, and `Retry-After` 3 and 20;
- a hang still retried at once;
- seven failure shapes that end in the step error inside the budget.

Broken twice, each red:

- the backoff set to 0.0: 12 failed, the blip arm among them;
- `Retry-After` ignored: 10 failed.

## R-06: a refusal is not held for a failing Jev decision

The fix, in `core/graph.py`, applies in Jev mode only. Two refusals now wait for the relevancy decision only within Jev's own window, `_JEV_OWN_PICK_WINDOW_S` (3.75 s), from the moment the decision began:

- the classifier's off-topic refusal, which only Jev's own on_topic pick can set aside (RJ03);
- an admitted question Jev called injection (RJ09).

`decide()` waits for Jev at most `JEV_TOTAL_TIMEOUT_S` plus half a second, then returns a Jev pick with no further wait. So a decision still running past the window can only end in the guard tier's pick or in none. A test pins the window above `decide()`'s own wait. Another, through the real `decide()` and the real constants, shows a Jev pick arriving 2.8 s in still sets the refusal aside with no fallback asked.

Before and after, the judge's `pg.py`, "Tell me about the tree of life.", Jev mode:

```text
SAME q='Tell me about the tree o' off_jev_hang jev       base  15.01s off_topic | fix   3.76s off_topic
SAME q='Tell me about the tree o' ok_jevinj_relhang jev  base  15.02s injection | fix   3.76s injection
```

Two limits, named:

- Jev's failure is inferred from its bound, because `decide()` gives no signal when Jev fails and `harness/decide.py` is outside the fence. A Jev that fails fast is therefore still refused at about 3.75 s, not "at once".
- One refusal's category can differ, for RJ09 only. When Jev's relevancy call failed and the guard fallback would have said off topic after the window, the question is refused as injection where before it was refused as off topic. It is refused either way. Measured: `DECIDE_REPLY=off_topic`, fallback 2 s and 5 s after Jev's 3 s timeout, gave off_topic at 5.06 s and 8.16 s on base and injection at 3.76 s and 3.76 s here. RA05 argued the other way round is the misleading one.

Tests, in the same file:

- the RJ03 and RJ09 shapes;
- Jev's own pick inside the window deciding exactly as before;
- the late real Jev pick through `decide()`;
- the default provider unchanged.

Broken twice, each red:

- the R-03 branch read against the step deadline again: 2 failed, at 3.00 s;
- the RJ09 read taken off the window: 1 failed, at 3.00 s.

## R-08: the documents and the parse-failure message

Changed:

- `JevBatchResult`'s docstring and `_jev_injection_pick`'s comment now say an unusable reply is charged within the ceiling.
- `DecisionRecord`'s docstring: on guardrail.injection, `agreed` is set only when Jev made a pick. When Jev made none, `agreed` stays None and `decided_by` is "guard" because Jev failed. It also names `_jev_injection_pick` as the caller of `call_jev`.
- Two unusable classifier replies now send "A step in this query could not complete. Retrying the query may succeed." The judge's RJ10 probe, `FULL=1`, Jev mode, a hang then an unusable reply:

```text
before error= {'fatal': True, 'scope': 'step', 'source': 'guardrail', 'error_class': 'recoverable', 'message': 'the guard tier did not return valid JSON', 'retry_after_s': 0}
after  error= {'fatal': True, 'scope': 'step', 'source': 'guardrail', 'error_class': 'recoverable', 'message': 'A step in this query could not complete. Retrying the query may succeed.', 'retry_after_s': 0}
```

- Builder A's report now states the request ceiling as six, not four.

Test: `test_no_usable_verdict_says_what_to_do_next`, two arms; the old message put back turns both red.

## R-09: the graph search's time limit is 30 seconds again

`CYPHER_QUERY_TIMEOUT_SECONDS` goes from 90.0 to 30.0. The history the comment and commit now carry: commit 9a3f50a widened 30 to 90 because the plan tier's reasoning effort `high` made writing Cypher slow. DECISIONS.md of 2026-07-31 dropped that effort to `none` and left 90 only because tightening it then would have been unmeasured. The plan tier still runs at `none`.

Measured from the two golden runs of 2026-09-26, `tool_start` to `tool_result`:

```text
calls 290 median 0.71 p90 3.58
between 30 and 90 s and ok: []
over 30 s: [('phase_8.6_golden', 'G-005_run2.json', 90.0, 'error'), ('phase_8.6_golden', 'G-006_run2.json', 90.0, 'error'), ('phase_8.6_golden', 'G-006_run3.json', 90.0, 'error'), ('phase_8.6-reland_golden', 'G-006_run3.json', 90.0, 'error')]
```

The lead's figure for the 90th percentile was 3.7 s; this computation gives 3.58.

Before and after, a real-time probe with the pipeline stubbed:

```text
r09 base budget=90s call=35s wall= 35.00s status=ok error=''
r09 fix  budget=30s call=35s wall= 30.01s status=error error='cypher_query exceeded its 30s overall budget before returning a result. That budget covers Cypher generation, '
r09 base budget=90s call=3s  wall=  3.00s status=ok error=''
r09 fix  budget=30s call=3s  wall=  3.01s status=ok error=''
```

Everything that reads the constant:

- `cypher_query`'s outer bound and its count and probe budgets follow it.
- Act's wait is `max(class budget, constant)` in `act_node`, so it now waits 30 s for lookup, single_hop, aggregate and multi_hop, and 120 for exploratory. The brief named `_LAYER_TOOL_ACT_TIMEOUT_SECONDS`, but that dictionary has no `cypher_query` entry, so nothing there moved. Trusting the code.
- `graph_http_transport`'s default and the graph query service's clamp read the same constant. The service clamps at 30 once it is next deployed.

Tests: `tests/system_03_search_agent/tools/test_cypher_query_budget.py`, time scaled a thousandfold with the real 30 s value captured. The constant put back to 90.0 turns all 8 red. One existing arm, `test_p12b_goes_red_when_the_graph_timeout_floor_is_destroyed`, went green-when-it-should-be-red: at 30 the floor equals multi_hop's own budget, so destroying it changed nothing. It now routes as lookup (15 s), where the floor decides Act's wait.

## What must stay true, with its evidence

| Constraint | Evidence |
|---|---|
| With the provider unset, refusals and admissions are develop's | The judge's `cases.txt` comparison, full event dumps (events, state, calls, charge), 17 cases with each relevancy reply: 16 of 17 identical for each. The one difference is `bad_bad`, whose guard events, calls and charge match and whose step error carries R-08's new message. R-05's backoff applies in both modes, on failure paths only |
| No question answered without the guard classifier's verdict | Every failure shape in the probes ends in the step error; `test_with_jev_a_classifier_that_never_answers_is_never_an_admission` |
| Forged transcripts refused, A10 and two variants | `test_reland_guardrail.py`'s forged-transcript arms pass in the full suite; the probes' A10 cases keep their verdicts |
| The 15 s budget does not change, no path passes it | The final probe set, 78 cases on each tree including a 429 storm, both attempts hung, the one-second blip and a provider slow on every request: worst wall 15.07 s on base and 15.24 s here, both on `steady_11`, where R-05 adds no wait. Rerun three times per tree at load average 39 to 48, `steady_11` and `steady_14` ended at 15.00 to 15.03 s on base and 15.00 to 15.02 s here. The overrun is scheduling lag, the same on base |
| R-06 changes only when a refusal arrives | The final probe set: 70 of 78 cases keep their verdict. Six differences are R-05's blip admissions; the other two are the named RJ09 category case. Every case of the judge's R-02 and R-03 set (G-043, the tree of life, A10) is unchanged |
| No decision read from a question's wording | Nothing added reads the question's text |
| Cite-or-refuse, sentence check, stable prefix untouched | `git diff a5c89bb -- src/system_03_search_agent/synthesis/` is empty; `STABLE_PREFIX 0a8c5ba26b987427` on base and on the final tree |

## Checks

```text
tests/system_03_search_agent: 5747 passed, 166 skipped, 1 xfailed, 7 warnings in 238.89s (0:03:58)
tests/services:               53 passed in 2.13s
ruff check .:                 All checks passed!
isort --check-only src tests: Skipped 2 files (no errors)
```

One earlier full-suite run, on a machine at load average 21 to 28 on 8 cores, failed three timing arms. Two were mine and one was `test_reland_guardrail.py`'s `test_the_two_attempts_share_the_step_budget`, on a path this work adds no wait to. All passed three runs of three in isolation. Commit `ee6a5c4` gives my two arms room; the pre-existing arm keeps its 0.05 s tolerance and can flake the same way on a loaded runner.

## Left for the lead

- `tests/system_03_search_agent/harness/test_jev_client.py`, outside my fence. One assertion pinned the old $0.0 charge for a non-JSON 200, which R-07's acceptance changes. The brief says a needed file outside the fence means stop and report, and the lead's later message says the full suite must pass. I made the one-value change in its own commit, `a73f89f`, so it can be kept or dropped; without it the suite has that one failure.
- Out of fence, still saying an unusable reply is charged its reported cost (RJ07): `harness/decide.py` lines 270 and 299, and its claim that `_injection_record` calls `call_jev`. Also `synthesis/sentence_check.py` lines 353 and 369, which must stay untouched, and `tests/system_03_search_agent/synthesis/test_sentence_check.py` line 927.
- Out of fence, still saying the graph budget is 90 s: `visualizations/Architecture_diagram.md` lines 130, 164 and 172; `visualizations/System_3_deep_dive.md` lines 358 and 362; and `export/traversal.py`'s comment near line 150.
- R-05's "fewer than four requests" needs `call_tier` in `harness/harness.py` to stop retrying a 429 at once.
- R-06's "at once" needs a signal from `harness/decide.py` that Jev has failed.
- Act's wait for the graph call and the tool's own bound are both 30 s. At equal deadlines Act's `enforce_timeout` can fire first and replace the tool's actionable message with the Act step's. This was true at 90 and 90 as well. A margin like the Layer 2 and 3 tools' +5 s would let the tool's message win, but the brief allowed only the dictionary entry.
