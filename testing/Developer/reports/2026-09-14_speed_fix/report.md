# Speed fix, measured, 2026-09-14

Fixer: the speed sub-agent, working alone on
`src/system_03_search_agent/core/graph.py` and its tests. The product owner
asked on 2026-09-14: "can we make the process quicker?". The Synth tier's
reasoning effort was already "none" by their decision, and this report does
not touch that line, any other tier, cap, timeout or budget. It removes the
two measured wastes the synth-effort-none report ranked first and second,
pins each with populate-checked, mutation-proven tests, and measures the
result live with the same 35 runs.

## Table of contents

- [Summary](#summary)
- [Change 1: the completeness repair is gated](#change-1-the-completeness-repair-is-gated)
- [Change 2: the discarded Plan-tier call is deleted](#change-2-the-discarded-plan-tier-call-is-deleted)
- [Tests: new, reworked, and what was not weakened](#tests-new-reworked-and-what-was-not-weakened)
- [Mutation proofs](#mutation-proofs)
- [The stable prefix, by SHA-256](#the-stable-prefix-by-sha-256)
- [Live measurement setup](#live-measurement-setup)
- [Before and after](#before-and-after)
- [Errors, out of 35](#errors-out-of-35)
- [Quality, unchanged on every run](#quality-unchanged-on-every-run)
- [Live-run table](#live-run-table)
- [Verify commands](#verify-commands)
- [Proposed DECISIONS.md rows](#proposed-decisionsmd-rows)
- [Files in this folder](#files-in-this-folder)

## Summary

- Median total elapsed over the same 35 runs: 16.6 seconds, down from 21.2
  (worst 46.5, down from 60.8; best answered run 6.7, down from 11.8). Both
  batches: the same five questions, the same two depths, 5 runs each, at
  most two questions in flight, real models and the real graph.
- Write step median 8.72 seconds over all 35 (9.06 over the 34 answered
  runs), down from 10.66. Plan step median 0.01 seconds, down from 1.40,
  with the 4-to-45-second tail gone (worst 0.17).
- The completeness repair fired on 14 of 34 answered runs (41 percent),
  down from 33 of 33, and it fired only where it has a job: on every one
  of those runs the model's FIRST reply had grounded nothing, so the
  repair was the alternative to the structured fallback and its `ask`
  floor. Six live diagnostic calls (`diagnose_gate_output*.json`) show the
  code-built probe citing every prepared finding every time; the gate kept
  the repair exactly twice, both with `model_grounded: false`. Time spent
  in repair calls fell from 216.5 seconds to 112.7.
- Errors: 0 of 35 (was 2 of 35, one plan-step timeout and one guard-step
  timeout). Write-step errors: 0 (was 0).
- Quality unchanged on every run: the first sentence is the code-built
  "Found N ... records" summary on all 34 answered runs, BRCA1 disease
  prose names diseases before any trial on all 15 BRCA1 disease runs, the
  source set per question is identical across runs AND identical to the
  previous batch (11, 20, 20, 20, 11), 0 unmarked claims on answered runs,
  0 "source URL" sentences, 0 raw `MedGen:C` codes.
- One refusal (was two): "Variants in GCK causing MODY", plain language,
  run 5, refused in Think with "NCBI has no record matching the name ...
  term=GCK", no tool having run and no Synth call made. That is AQ-09 from
  the answer-quality report, word for word, a Think-side live symbol lookup
  intermittently returning nothing for GCK, and neither change here runs
  before Think. It is not a new refusal class, but it is a refusal, so it
  is stated rather than netted against the two the previous batch had.
- The stable prefix is byte-identical, SHA-256
  `34a07a1a...26603e` over 28925 bytes before and after.
- The next lever, measured rather than proposed: on 14 of 25 Researcher
  runs the model's first reply grounded ZERO claims and only the repair
  rescued it. That is an answer-path finding for the Researcher directive
  or the grounding pass, outside this task, and it is now the whole of
  what the repair costs.

## Change 1: the completeness repair is gated

What triggered it before. `write_node` runs the first Synth call, grounds
the reply, and computes `omitted_findings` as every prepared finding the
MODEL'S OWN grounded claims do not cite (`unreported_findings`). If that
list is non-empty and at least 5 seconds of the Write budget remain, it
dispatches a second full Synth call carrying `build_completeness_directive`
("COMPLETENESS CORRECTION"). Only AFTER that does the code-built listing
(Researcher: every prepared finding, UI fix set 9) or the findings tail
(every other depth: the omitted findings, UI fix set 10) run, and both cite
in code every finding the model left out, through the same
`run_grounding_pass`. So the order was: model prose, repair, code-built
lines. The repair was deciding on a shortfall the next block was about to
close anyway, which is why it fired on 33 of 33 answered runs at a median
4.8 seconds and up to 22.9.

The gate. A new module-level helper, `_code_built_lines_will_cite`, runs the
tail's own computation ahead of the repair: `build_structured_fallback_
narrative` over exactly the findings the listing or tail will render (all of
them in Researcher, the omitted ones elsewhere), through
`run_grounding_pass` with the same `core_ask_required=True` and the same
question. If every omitted finding is among the claims that grounding
produced, the repair is skipped. The trigger condition in `write_node` is
now `omitted_findings and repair_budget_s >= 5 and not
_code_built_lines_will_cite(...)`. Nothing else moved: the shared budget,
the cap disclosure, the strict-superset acceptance rule, the `ask` floor and
the incompleteness note are untouched, and the tail and listing run
afterwards exactly as before.

Where the repair still has a job, and is kept:

- The model grounded nothing. The tail fires only on a grounded answer; the
  alternative is the structured fallback, which lists the records and
  floors the outcome at `ask`. A repair that grounds something turns that
  into an `answer` with prose, so it can change the outcome, and it runs.
- A code-built sentence the pass strips (a value carrying a sentence
  boundary, or one that fails the number check). The tail cannot cite it,
  so only the model's own phrasing can, and the repair runs.
- A tool outcome other than `ok` with findings present. The tail does not
  run there, so the repair keeps its old trigger.

Why the cited set is unchanged. In every case the gate skips, the merged
claims after the tail or listing are the model's claims plus a code-built
claim for each omitted finding, which is every prepared finding; that was
also the outcome when the repair ran, since the repair only ever moved a
finding from a code-built line into the model's prose. `trust_for_claims`,
`_citations_from_grounded_claims` and the conflict flags are computed per
finding, not per sentence, so the trust outcome and the citations are the
same set either way. `omitted_findings` is recomputed from the merged
claims after the tail, so the incompleteness note and the `ask` floor see
the same value they saw before. The summary sentence, the restatement drop
and grounding keep their meaning, since none of them reads the repair.

What the reader loses: nothing that is cited. What changes is only that a
finding the model's first reply left out now appears as a code-built line
rather than being rewritten into the model's prose by a second call.

## Change 2: the discarded Plan-tier call is deleted

What was there. `plan_node` opened with `_dispatch_tier_call(harness,
trace_id, "plan", "plan", [...], budget_s=budget_for_step("plan", ...),
max_tokens=16)`, sending "Reply with the single word: ok" plus the question
and the session-memory suffix, and never binding the result. The comment
above it recorded the whole history: build phase 4.7 moved entity resolution
to Think (F-4.5-A-09, "consumed by nothing"), F-4.12-01 capped it at 16
tokens after it killed queries at the 45-second plan budget on Railway, and
wrote "THE REAL FIX IS TO DELETE THIS CALL, and it is deliberately not done
here ... Filed rather than taken unilaterally", naming the per-query
cost-cap pre-flight as the one side effect that would move.

Proof that nothing read its output, by reading:

- The `await` bound no name. The two `except` clauses returned
  `cap_exceeded` or `step_error`; both are also returned by `think_node`'s
  own call immediately before and routed identically by `_route_after_plan`.
- Tool selection below reads `state["resolved_entities"]` (Think's),
  `unresolved_entity_symbols` (Think's), `_memory_curies(state)` and
  `_remembered_mention_for(...)`, all in code.
- The `plan` event's narrative and `tool_calls` are built from
  `_select_planned_tool_call` and `_build_layer_tool_calls`, pure functions
  of the question text and the resolved symbol.
- The `cost` event is `build_cost_event_payload(harness, trace_id, "plan")`,
  which reads the harness's running total, not the reply.
- No test read the reply: every test that named the call counted it
  (`test_graph.py`'s call counts and prefix counts), captured its prompt
  (`test_personalization_premise.py` P7b) or counted its cost pre-flight
  (the cap-breach threshold test). None asserted on its content.
- The trace: the call appeared in LangSmith as one more `call_tier` run
  joined on `trace_id`; nothing joined back from it.

Proof by execution: `test_plan_node_dispatches_no_model_call` wraps
`_dispatch_tier_call`, runs the compiled graph on a template-shaped question
("What gene is associated with BRCA1?"), and asserts no `(tier, step)` pair
with `step == "plan"` was dispatched while `("plan", "think")` and
`("synth", "write")` were, and the `plan` event still carries planned tool
calls. The full happy-path event sequence and outcomes are unchanged:
`test_happy_path_emits_the_expected_event_type_sequence`, the
`trust_outcome` arms and every other `test_graph.py` arm that does not count
calls are green without edit.

What moved, and where it went:

- The per-query cost-cap pre-flight. `_dispatch_tier_call` runs
  `check_per_query_cap` before every model call, so it fires at Think's
  classification call immediately before Plan, and `act_node` runs its own
  `check_per_query_cap(harness, trace_id, "plan")` before every dispatch
  immediately after. Nothing between them spends money, so no breach can
  go unseen. `test_cost_cap_breach_during_act_ships_partial_result_
  without_calling_the_tool` moved its threshold from the third plan-tier
  check to the second, and `test_per_query_cap_hit_on_plan_short_circuits_
  to_write_without_reaching_act` is green unchanged: the cap now fires at
  Think and still routes straight to Write's partial result.
- Session memory's Plan prompt. Memory used to ride the discarded call's
  user message; Plan's decisions never read that message. Plan still reads
  memory in code (`_memory_curies`, `_remembered_mention_for`), and
  `test_p10_memory_is_never_injected_into_the_act_or_write_step`'s negative
  control now pins those two sites for `plan_node` instead of
  `_memory_suffix`.

The comment that filed the fix is replaced by one recording that it was
taken, with the history, the 2026-09-14 measurement, and where each side
effect now lives. The module docstring's "every model-calling node
(guardrail, think, plan, write)" now names three.

## Tests: new, reworked, and what was not weakened

New arms in `tests/system_03_search_agent/core/test_write_completeness.py`:

- `test_the_repair_is_skipped_when_the_code_built_lines_cite_every_omission`,
  parametrized over `clinical_brief` (the tail) and `researcher` (the
  listing): exactly one Synth dispatch, none carrying the correction, the
  cited set equals the five prepared rows, outcome `answer`, every record
  name in the narrative, no incompleteness note. The populate check is the
  recorded first dispatch and the five citations.
- `test_the_repair_still_runs_when_a_code_built_line_cannot_ground`: with
  the builder returning an ungroundable sentence, two dispatches, the second
  carrying the correction, cited set still the prepared set.
- `test_the_repair_still_runs_when_the_model_grounded_nothing`: first reply
  grounds nothing, repair grounds everything, two dispatches, outcome
  `answer`, no structured-fallback note.
- `test_code_built_lines_will_cite_keeps_the_repair_off_the_ok_path`: the
  helper returns False on a non-ok tool outcome and on an empty omission
  list, True when the tail can cite.

New arm in `tests/system_03_search_agent/core/test_graph.py`:

- `test_plan_node_dispatches_no_model_call`, counting `_dispatch_tier_call`
  per `(tier, step)` on a template-shaped question.

Existing tests whose requirement changed, each named with why:

| Test | What changed | Why |
|---|---|---|
| `test_write_completeness.py::test_a_repair_that_drops_a_reported_finding_is_discarded` | The builder now skips finding 3's code-built line, so the repair fires; asserts finding 3 appears nowhere, the tail still cites 4 and 5, the note reads "one further disease record was found", outcome `ask` | Without an ungroundable line the repair no longer runs, and the arm would have passed without exercising the discard rule it pins |
| `test_write_completeness.py::test_a_repair_that_adds_without_dropping_is_kept` | The tail is made unable to ground, so the repair fires and its accepted prose is what cites 3 to 5 | Same reason; the negative control for the discard rule must reach the rule |
| `test_write_completeness.py::test_both_write_calls_share_the_steps_one_declared_budget` | The tail is made unable to ground before the two budgets are recorded | The second budget exists only when the repair runs |
| `test_write_completeness.py::test_a_cost_cap_hit_during_the_repair_is_disclosed` | First half now runs with the tail unable to ground and asserts "was not repaired" plus `ask`; second half drives the model-grounded-nothing case and asserts "listed below as found" | The old first half (repair capped while the tail covers everything) is unreachable by construction now, since the repair is not dispatched when the tail covers everything; the note's other clause is reached through the fallback path |
| `test_graph.py::test_plan_calls_the_plan_tier_model` | 2 plan-tier calls to 1 | plan_node's call is gone |
| `test_graph.py::test_plan_calls_the_plan_tier_model_when_a_tool_runs` | 4 to 3 | Same |
| `test_graph.py::test_every_model_call_carries_the_stable_prefix_as_its_leading_message` | 4 calls to 3, prefixed loop calls 2 to 1 | Same |
| `test_graph.py::test_every_model_call_carries_the_stable_prefix_as_its_leading_message_when_a_tool_runs` | 6 to 5, prefixed 2 to 1 | Same |
| `test_graph.py::test_exactly_four_model_calls_fire_on_the_happy_path`, renamed `test_exactly_three_model_calls_fire_on_the_happy_path` | 4 to 3 | Same |
| `test_graph.py::test_six_model_calls_fire_when_a_tool_runs`, renamed `test_five_model_calls_fire_when_a_tool_runs` | 6 to 5 | Same |
| `test_graph.py::test_stable_prefix_still_reaches_every_graph_node_call_when_a_tool_runs` | prefixed node-level calls 2 to 1 | Same |
| `test_graph.py::test_cost_cap_breach_during_act_ships_partial_result_without_calling_the_tool` | The cap is forced on the second plan-tier check, not the third | The pre-flight sequence is now Think, then Act |
| `test_personalization_premise.py::test_p7b_the_stable_prefix_is_byte_identical_as_session_memory_varies` | Loops over `think` only | There is no Plan prompt to hash; Plan reads memory in code |
| `test_personalization_premise.py::test_p10_memory_is_never_injected_into_the_act_or_write_step` | The plan_node negative control pins `_memory_curies` or `_session_memory` rather than `_memory_suffix` | Same |
| `test_run.py::TestRunStreamingIsGenuinelyIncremental::test_earlier_events_arrive_before_a_delayed_nodes_event_by_a_real_measurable_gap` | Delays the third `litellm` call as before, which is now Write's, and measures the gap between the `plan` and `done` arrivals instead of `think` and `plan`; also asserts the call count is 3 | The third call was plan_node's; with it gone the delay landed after `plan` and the old gap read near zero. Found by the full suite (1 failed, 4668 passed on the first run), not by reading, and the arm keeps its property on the node that now owns the third call |

Not weakened: no grounding, cite-or-refuse or tail arm changed its
assertion. `test_write_findings_tail.py` (every arm), `test_write_grounding_
premise.py`, `test_write_answer_quality.py`, the structured-fallback arms,
the refusal-message arms and `test_the_incomplete_note_counts_findings_
handed_to_synthesis` are green without edit. The reworked arms above add
setup (an ungroundable builder) and keep or tighten their assertions; none
drops one.

## Mutation proofs

Each mutation was applied to `src/system_03_search_agent/core/graph.py`,
the named arms run, the red output recorded below, and the file restored;
`grep -n "MUTATION M" src/system_03_search_agent/core/graph.py` returns
nothing afterwards, and the prefix SHA-256 was re-checked byte-identical
after the last revert.

| Mutation | What was changed | Arms that went red | Red output |
|---|---|---|---|
| M1 | The trigger's `and not _code_built_lines_will_cite(...)` replaced by `and True` | `test_the_repair_is_skipped_when_the_code_built_lines_cite_every_omission[clinical_brief]`, `[researcher]` | `AssertionError: [False, True]` on both |
| M2 | `_code_built_lines_will_cite` returns True unconditionally | `test_the_repair_still_runs_when_a_code_built_line_cannot_ground`, `test_the_repair_still_runs_when_the_model_grounded_nothing`, `test_code_built_lines_will_cite_keeps_the_repair_off_the_ok_path` | `assert [False] == [False, True]` twice; `assert not True` |
| M3 | `or not model_grounded` dropped from the helper's early return | `test_the_repair_still_runs_when_the_model_grounded_nothing` only | `assert [False] == [False, True]` |
| M4 | A `_dispatch_tier_call(harness, trace_id, "plan", "plan", ...)` restored at the top of `plan_node` | `test_plan_node_dispatches_no_model_call`, `test_plan_calls_the_plan_tier_model`, `test_plan_calls_the_plan_tier_model_when_a_tool_runs`, `test_exactly_three_model_calls_fire_on_the_happy_path`, `test_five_model_calls_fire_when_a_tool_runs` | `plan_node dispatched a model call: [('plan', 'plan')]`; `assert 2 == 1`; `assert 4 == 3`; `assert 4 == 3`; `assert 6 == 5` |
| M5 | The strict-superset acceptance rule replaced by the pre-F-4.5-J-13 count rule | `test_a_repair_that_drops_a_reported_finding_is_discarded` | `the discarded repair's own content must not leak into the answer` |

M1 and M3 each turned red exactly one property's arms and nothing else,
which is the populate check on the arms themselves: the skip arm cannot be
satisfied by a build that never calls Synth (its first dispatch and five
citations are asserted), and the still-runs arms cannot be satisfied by a
build that always repairs (M2 shows they see the second dispatch
disappear, not merely appear).

## The stable prefix, by SHA-256

`prefix_sha256.py` builds `_STABLE_PREFIX` twice, once from a copy of `src/`
whose `core/graph.py` is the committed version at `HEAD` (ffb5b0d) and once
from the working tree, and prints both digests:

```
before (HEAD graph.py): 34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e 28925
after  (working tree):   34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e 28925
BYTE-IDENTICAL
```

Neither change touches the prefix's inputs (`build_stable_prefix` over the
registered tool schemas); change 2 removes one CALLER of the prefix, the
Plan call, which `test_p7b` and the `test_graph.py` prefix counts now
reflect.

## Live measurement setup

Scripts: `measure_write2.py` and `analyze.py` are copies of the
synth-effort-none report's scripts, unchanged except that `analyze.py`
reads `r1.jsonl` where the earlier folder had `smoke_test.jsonl`. The
per-run fields are the same: outcome, errors, elapsed, every Synth call's
wall time and word count with whether it was the repair, first sentence,
words, headings, list rows, sources, unmarked claims, `step_seconds`.

`python3 tracker/preflight.py`: READY (product model, harness model and
graph all answered) before the batch. No session memory, real models and
the real graph. Two queues, at most two questions in flight:

- Queue A (researcher): "Which diseases are associated with BRCA1?" (5,
  `r1.jsonl`), "What variants cause disease in BRCA1?" (5, `r2.jsonl`),
  "Variants in GCK causing MODY" (5, `r3.jsonl`).
- Queue B: "Which diseases are associated with BRCA1 and BRCA2?" (5,
  researcher, `r4.jsonl`), "what diseases are linked to brca1?" (5,
  researcher, `r5.jsonl`), "Which diseases are associated with BRCA1?" (5,
  plain_language, `p1.jsonl`), "Variants in GCK causing MODY" (5,
  plain_language, `p2.jsonl`).

35 runs, one JSON line each. Nothing else CPU-heavy ran on the machine
during the batch: the full test suite that had been started earlier was
stopped before the queues began, so the elapsed figures are not
contended, the same condition the previous batch measured under.

Six supplementary diagnostic runs (`diagnose_gate.py`, NOT part of the
35) wrapped `_code_built_lines_will_cite` on real runs and recorded, per
call, whether the model had grounded anything, how many findings the
code-built probe cited, and which omitted findings it could not cite.
Output: `diagnose_gate_output.json` (2 runs), `diagnose_gate_output_2.json`
(4 runs).

## Before and after

Before is the synth-effort-none report's batch (35 runs, 2026-09-14,
after the Synth tier moved to effort "none"); after is this batch. Same
questions, depths, counts and concurrency.

| Measure | Before | After |
|---|---|---|
| Median total elapsed, all runs | 21.2 s | 16.6 s |
| Worst total elapsed | 60.8 s | 46.5 s |
| Best total elapsed (answered) | 11.8 s | 6.7 s |
| Write step median (answered runs) | 10.66 s (n=33) | 9.06 s (n=34); 8.72 s over all 35 |
| Write step worst | 44.69 s | 36.21 s |
| Plan step median | 1.40 s | 0.01 s |
| Plan step worst | 45.20 s (a timeout that refused the query) | 0.17 s |
| Guard step median / worst | 2.45 s / 15.08 s | 1.98 s / 24.13 s |
| Think step median / worst | 2.59 s / 14.15 s | 2.59 s / 12.72 s |
| Act step median / worst | 1.04 s / 3.04 s | 0.69 s / 3.21 s |
| First Synth call median / worst | 5.0 s / 22.0 s | 5.55 s / 25.5 s |
| Repair call fire rate | 33 of 33 answered (100 percent) | 14 of 34 answered (41 percent); Researcher 14 of 25, Plain language 0 of 9 |
| Repair call median / worst / total | 4.8 s / 22.9 s / 216.5 s | 7.7 s / 12.1 s / 112.7 s |
| Errors (any step) | 2 (plan transient, guard transient) | 0 |
| Write-step errors | 0 | 0 |
| Refusals | 2 (both the errors above) | 1 (Think-side AQ-09, GCK unresolved) |

Two things about that table are worth saying plainly. Guard's worst case
rose (24.1 s on r1 run 1) and the first Synth call's worst case rose (25.5
s on r2 run 2); both are provider latency on tiers and calls this change
does not touch, and both sit inside their step budgets. And the repair's
median rose from 4.8 to 7.7 seconds because the cheap firings are gone:
what remains are the runs where the first reply grounded nothing and the
repair is writing the whole answer.

## Errors, out of 35

None. 35 of 35 runs reached a `done` event with no `error` event. The
previous batch's two errors were a plan-step timeout at the 45-second plan
budget (the discarded call this change deletes, so that failure mode no
longer exists) and a guard-step timeout (untouched here; this batch's worst
guard call was 24.1 seconds, under its budget).

One run refused without an error: p2 run 5, "Variants in GCK causing MODY",
plain language. `tools: []`, `synth_calls: []`, and the answer text is the
unresolved-gene refusal with its NCBI search link for `term=GCK`. That is
AQ-09 in `testing/Developer/reports/2026-09-14_answer_quality/report.md`
("Two GCK runs in ten refused with the unresolved-symbol refusal ... `think_
node`'s live symbol lookup for GCK returned nothing on those runs"). It
happens in Think, before either change here runs, and it is the same
question and the same wording. Rate this batch: 1 of 10 GCK runs; the
answer-quality report measured 2 of 10.

## Quality, unchanged on every run

Checked programmatically over all 35 lines, against the blocked-stop
conditions the brief names:

| Check | Result |
|---|---|
| Summary sentence first | Yes: all 34 answered runs open on "Found N ... records" (`first_sentence` starts with "Found" on every one) |
| Disease prose before trials for BRCA1 | Yes: on all 15 BRCA1 disease runs (r1, r5, p1) the claim after the summary names the diseases ("BRCA1 is linked to familial cancer of breast [1], ..."); the first trial-bearing claim, where one exists, is index 3 to 7, never before the disease claim |
| Identical source set per question | Yes: exactly one distinct source set per question across its 5 or 10 runs, and the counts match the previous batch exactly: BRCA1 diseases 11 (both phrasings, both depths), BRCA1 and BRCA2 20, GCK MODY 20 (both depths), BRCA1 variants 20 |
| 0 unmarked claims | Yes on answered runs. The one `unmarked_claims: 1` in the batch is the refusal run, whose only token is the refusal text with no marker, the same shape the previous batch's two refusals had |
| 0 "source URL" sentences | Yes, 0 of 35 |
| No raw `MedGen:C` code in the words | Yes, 0 of 35 |
| No new refusals | One refusal, of the pre-existing AQ-09 class, in Think; none from Plan or Write, and none of a class the previous batches had not already recorded. Stated above rather than claimed away |
| Outcomes | 24 `ask`, 10 `answer`, 1 `refuse` (before: 24 `ask`, 9 `answer`, 2 `refuse`) |

## Live-run table

Words, headings, list rows, sources, the two Synth columns and `step_seconds` read exactly as in the synth-effort-none report's table (`g`uard `t`hink `p`lan `a`ct `w`rite, seconds each).

| Case | Mode | Run | Outcome | First sentence | Words | Headings | List rows | Sources | Synth1 s/w | Repair s/w | Elapsed | step_seconds | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRCA1 diseases | researcher | 1 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 129 | 4 | 11 | 11 | 5.6/221 | none | 36.4 | g24.133 t5.078 p0.057 a0.605 w6.348 | none |
| BRCA1 diseases | researcher | 2 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 133 | 4 | 11 | 11 | 2.1/151 | 10.2/215 | 25.2 | g8.502 t3.124 p0.083 a0.74 w12.57 | none |
| BRCA1 diseases | researcher | 3 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 150 | 4 | 11 | 11 | 2.8/235 | none | 11.2 | g5.743 t2.043 p0.031 a0.592 w2.779 | none |
| BRCA1 diseases | researcher | 4 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 154 | 4 | 11 | 11 | 9.4/227 | none | 16.6 | g1.754 t4.801 p0.011 a0.57 w9.412 | none |
| BRCA1 diseases | researcher | 5 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 133 | 4 | 11 | 11 | 2.3/220 | none | 6.9 | g1.913 t2.116 p0.013 a0.535 w2.326 | none |
| BRCA1 variants (disease-cause) | researcher | 1 | ask | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 | 5.3/208 | 7.9/255 | 35.2 | g14.711 t4.691 p0.045 a2.46 w13.282 | none |
| BRCA1 variants (disease-cause) | researcher | 2 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 | 25.5/170 | 10.6/233 | 43.4 | g2.308 t2.391 p0.004 a2.519 w36.206 | none |
| BRCA1 variants (disease-cause) | researcher | 3 | ask | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 | 5.8/186 | 7.5/197 | 18.6 | g1.978 t0.853 p0.003 a2.358 w13.349 | none |
| BRCA1 variants (disease-cause) | researcher | 4 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 115 | 4 | 20 | 20 | 10.9/210 | 11.4/266 | 30.9 | g2.201 t3.02 p0.025 a3.213 w22.424 | none |
| BRCA1 variants (disease-cause) | researcher | 5 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 107 | 4 | 20 | 20 | 10.1/176 | none | 14.7 | g1.048 t1.14 p0.004 a2.344 w10.115 | none |
| GCK MODY variants | researcher | 1 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 9.8/187 | 10.8/284 | 30.0 | g2.951 t3.979 p0.005 a2.356 w20.716 | none |
| GCK MODY variants | researcher | 2 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 13.1/203 | none | 19.8 | g2.115 t2.092 p0.009 a2.472 w13.133 | none |
| GCK MODY variants | researcher | 3 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 11.0/204 | none | 17.9 | g1.746 t2.593 p0.025 a2.421 w11.071 | none |
| GCK MODY variants | researcher | 4 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 4.3/228 | 12.1/249 | 20.8 | g1.169 t0.748 p0.005 a2.363 w16.459 | none |
| GCK MODY variants | researcher | 5 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 6.3/222 | 11.2/244 | 22.2 | g0.679 t1.566 p0.008 a2.435 w17.511 | none |
| BRCA1 and BRCA2 diseases | researcher | 1 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 11.9/331 | 6.3/289 | 46.5 | g12.674 t12.723 p0.173 a1.174 w19.277 | none |
| BRCA1 and BRCA2 diseases | researcher | 2 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 140 | 5 | 20 | 20 | 4.5/206 | none | 14.2 | g3.306 t4.663 p0.097 a0.865 w5.169 | none |
| BRCA1 and BRCA2 diseases | researcher | 3 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 6.2/320 | 5.2/237 | 23.0 | g7.412 t3.503 p0.015 a0.576 w11.454 | none |
| BRCA1 and BRCA2 diseases | researcher | 4 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 5.7/300 | 5.0/169 | 17.6 | g2.124 t4.072 p0.013 a0.618 w10.726 | none |
| BRCA1 and BRCA2 diseases | researcher | 5 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 5.4/257 | 6.0/268 | 17.5 | g1.623 t3.732 p0.044 a0.608 w11.471 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 1 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 141 | 5 | 11 | 11 | 2.6/243 | none | 7.5 | g2.785 t1.127 p0.003 a0.523 w3.087 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 2 | ask | Found 4 disease records for brca1: Familial cancer of breast, Familial | 147 | 4 | 11 | 11 | 4.3/252 | none | 6.7 | g1.166 t0.73 p0.011 a0.523 w4.272 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 3 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 141 | 4 | 11 | 11 | 15.8/185 | 5.3/176 | 23.9 | g1.243 t0.933 p0.004 a0.54 w21.193 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 4 | ask | Found 4 disease records for brca1: Familial cancer of breast, Familial | 143 | 4 | 11 | 11 | 8.7/238 | none | 13.7 | g1.956 t2.288 p0.009 a0.693 w8.717 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 5 | ask | Found 4 disease records for brca1: Familial cancer of breast, Familial | 188 | 5 | 11 | 11 | 5.4/213 | 3.2/208 | 17.4 | g6.049 t2.209 p0.005 a0.511 w8.574 | none |
| BRCA1 diseases | plain_language | 1 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 138 | 0 | 0 | 11 | 5.4/196 | none | 14.3 | g4.123 t3.621 p0.005 a0.553 w5.974 | none |
| BRCA1 diseases | plain_language | 2 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 141 | 0 | 0 | 11 | 1.4/119 | none | 7.3 | g1.976 t3.378 p0.017 a0.508 w1.427 | none |
| BRCA1 diseases | plain_language | 3 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 151 | 0 | 0 | 11 | 2.4/115 | none | 7.4 | g1.726 t2.639 p0.003 a0.534 w2.442 | none |
| BRCA1 diseases | plain_language | 4 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 137 | 0 | 0 | 11 | 3.0/153 | none | 7.5 | g1.794 t2.186 p0.006 a0.523 w2.996 | none |
| BRCA1 diseases | plain_language | 5 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial | 133 | 0 | 0 | 11 | 5.9/159 | none | 10.9 | g1.785 t2.623 p0.003 a0.539 w5.965 | none |
| GCK MODY variants | plain_language | 1 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 143 | 0 | 0 | 20 | 5.6/164 | none | 13.9 | g2.413 t3.532 p0.008 a2.315 w5.618 | none |
| GCK MODY variants | plain_language | 2 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 138 | 0 | 0 | 20 | 3.8/194 | none | 8.6 | g0.989 t1.41 p0.002 a2.311 w3.848 | none |
| GCK MODY variants | plain_language | 3 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 144 | 0 | 0 | 20 | 3.9/196 | none | 9.5 | g1.048 t2.057 p0.006 a2.428 w3.982 | none |
| GCK MODY variants | plain_language | 4 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 160 | 0 | 0 | 20 | 5.5/192 | none | 11.8 | g1.798 t1.607 p0.002 a2.815 w5.601 | none |
| GCK MODY variants | plain_language | 5 | refuse | I could not identify that gene. NCBI has no record matching the name i | 23 | 0 | 0 | 0 | none | none | 5.1 | g1.786 t3.356 p0.002 a0.0 w0.002 | none |

## Verify commands

Each on its own exit code, from the repository root, on the finished code
with every mutation reverted:

```
$ python -m pytest tests/system_03_search_agent -q -p no:cacheprovider
4669 passed, 176 skipped, 1 xfailed, 8 warnings in 439.12s (0:07:19)
PYTEST_EXIT=0

(The first full run after the edits read `1 failed, 4668 passed`; the
failure was `test_run.py`'s streaming-gap arm, whose delayed third call had
been plan_node's. It is reworked above and the suite was re-run in full.)

$ ruff check .
All checks passed!
RUFF_EXIT=0

$ isort --check-only src tests
Skipped 2 files
ISORT_EXIT=0

$ python3 tracker/check_doc_drift.py --check
DRIFT_EXIT=1
AGENTS.md:32: says 5044 python tests (computed: 5052)
AGENTS.md:32: says 541 decisions.md rows (computed: 545)
CLAUDE.md:32: says 5044 python tests (computed: 5052)
CLAUDE.md:32: says 541 decisions.md rows (computed: 545)
requirements/Plan.md:20: says 541 decisions.md rows (computed: 545)
error: 8 facts computed (2 skipped) | 5 stale | 0 structural
```

The drift check is red on five stale counts and zero structural, reported
and not edited, per the brief: the Python test count moved from 5044 to
5052 (this task adds 5 arms, one of them parametrized twice, so 6 of the
8; the other 2 are another agent's `test_harness.py` additions in the same
working tree), and the DECISIONS.md row count moved from 541 to 545 through
rows other agents appended today. `CLAUDE.md`, `AGENTS.md` and
`requirements/Plan.md` carry those numbers and are left for whoever
checkpoints.

`ruff check .` covers the whole repository, so the two scripts new in this
folder were linted too and fixed once (an import block and a bare `open`).

## Proposed DECISIONS.md rows

Two rows, in the existing `<details>` shape, for the main agent to append.

```
| 2026-09-14 | THE COMPLETENESS REPAIR IS SKIPPED WHEN THE CODE-BUILT LINES WILL CITE EVERY FINDING THE MODEL LEFT OUT: `write_node` runs the tail's own grounding ahead of the repair (`_code_built_lines_will_cite`, the same `build_structured_fallback_narrative` over the findings the Researcher listing or the tail will render, through the same `run_grounding_pass`), and dispatches the second Synth call only when the tool outcome is not ok, the first reply grounded nothing, or a code-built line cannot ground | Delete the repair; gate it on depth alone; raise `_WRITE_REPAIR_MIN_BUDGET_S`; leave it firing on every run | <details><summary>why</summary>Measured on 2026-09-14 after the Synth tier moved to effort none: the repair fired on 33 of 33 answered runs, a median 4.8 seconds and a worst 22.9, 216.5 seconds in the batch, while the findings tail and the Researcher listing already cited every finding it was regenerating for, so it could not change the cited set, the trust outcome or the notes. Deleting it would lose the one case where it changes the outcome, a first reply that grounds nothing, which the structured fallback answers with an `ask` floor; gating on depth would miss that case in both directions; the budget floor does not describe the waste. The probe is deterministic and costs no model call. Re-measured over the same 35 runs: median elapsed 21.2 to 16.6 seconds, repair 14 of 34, every remaining firing on a run whose first reply grounded nothing, one source set per question and the same sets as before.</details> |
| 2026-09-14 | `plan_node` MAKES NO MODEL CALL: the Plan-tier dispatch whose reply had been discarded since build phase 4.7 (F-4.5-A-09, capped at 16 tokens by F-4.12-01 with "THE REAL FIX IS TO DELETE THIS CALL ... filed rather than taken unilaterally") is deleted, and Plan selects tools in code from Think's resolved entities and session memory's `_memory_curies` | Keep the call as the per-query cost pre-flight's trigger; keep it for the session-memory prompt suffix; replace it with a cheaper call | <details><summary>why</summary>Nothing read the reply, proven by reading (no binding, tool selection reads Think's state, the plan and cost events read code and the harness total) and by execution (`test_plan_node_dispatches_no_model_call`, counting `_dispatch_tier_call` per tier and step on a template-shaped question). Its only side effects live elsewhere: `_dispatch_tier_call` runs the cost pre-flight at Think immediately before, `act_node` runs its own immediately after, and memory reaches Plan's decisions in code. Measured 2026-09-14: a median 1.40 seconds, 4 of 34 runs at 4 to 27 seconds, and one run refused at the full 45-second plan budget; after deletion the Plan step is 0.01 seconds median, 0.17 worst, over 35 runs with zero errors.</details> |
```

## Files in this folder

- `report.md`: this report.
- `measure_write2.py`: the measurement script, a copy of the
  synth-effort-none report's, unchanged.
- `analyze.py`: the table and per-step breakdown script, a copy with
  `smoke_test.jsonl` renamed `r1.jsonl`.
- `queueA.sh`, `queueB.sh`, `queueA.log`, `queueB.log`: the two batch
  drivers and their stdout.
- `r1.jsonl` to `r5.jsonl`, `p1.jsonl`, `p2.jsonl`: the 35 measured runs,
  one JSON line each.
- `analysis_output.txt`: `analyze.py`'s raw stdout, the source of every
  number in the live-run table and the per-step medians.
- `prefix_sha256.py`: builds the stable prefix from HEAD's `graph.py` and
  the working tree's and compares the two digests.
- `diagnose_gate.py`, `diagnose_gate_output.json`,
  `diagnose_gate_output_2.json`: the six supplementary live runs that
  record why the gate kept or skipped the repair, not part of the 35.
