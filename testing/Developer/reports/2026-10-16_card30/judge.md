# Card 30 step 1 judge

Pull request #261, branch `fix/card30-unclassified-variants-say-so`, commit `3d8988ca` on develop `78c68c1c`. Code, tests and local probes only; no live run, no spend.

## Table of contents

- [Findings](#findings)
- [Checks](#checks)
- [Break it](#break-it)
- [Verdict](#verdict)

## Findings

(Filed as established.)

### J-30-01, minor: the two late decision reads in Write run one after the other

- Where: `src/system_03_search_agent/core/graph.py:14076` and `:14077`, `clinical_features_asked = await _clinical_features_asked(...)` then `classification_asked = await _classification_asked(...)`. Each waits up to `_LATE_DECISION_GRACE_S` (1.0 s, `:1252`) from the moment it starts.
- Evidence: probe `<scratchpad>/card30_judge/probe_wait.py` hands both tasks a 30 s sleep and runs the two reads exactly as Write does. Output: `features read done at 1.00s, classification read done at 2.00s`. Develop's worst case is the first line alone, 1.0 s.
- Effect: only when Jev is failing over on both decisions at once, which the two share since they start at the same moment in `think_node` (`:4187` to `:4196`). Normally both have finished long before Write and the read is free.
- Worse than develop: by exactly the 1 s the diagnosis named ("the worst case adds 1 second"), which sits at the brief's "more than about a second" bar, not over it. Not counted as worse. Reading both under one grace (one `asyncio.wait` on both tasks) would make the worst case 1.0 s, the same as develop.

### J-30-02, minor: query 79's verdict can move to "ask", and nobody decided that

- Where: `_ASKS_CLASSIFICATION`'s criterion for `asks_classification`, `src/system_03_search_agent/core/graph.py:1225` to `:1229`: "It asks which variants, or whether a variant, are pathogenic, harmful, disease causing, benign, clinically significant or of uncertain significance". Query 79 reads "What diseases are caused by variants in the HNF1A gene?" (`testing/Test_queries_and_workflows.md:620`). Its `not_applicable` criterion says "which conditions a variant is linked to" (`:1231`), so the two criteria pull opposite ways on that wording.
- Why it matters: the floor's shape condition holds on query 79's answer (graph `SequenceVariant` rows, no classification field), and the floor does not look at whether card 23's line is shown (`:14994`). So if the classifier reads "caused by" as "disease causing", the HNF1A table answer goes from "answer" to "ask". The diagnosis's floor row names exactly this as the wrong outcome: flooring on shape alone "would turn every variant listing (for example ... query 79's HNF1A table) from answer to ask when nothing about them asked for a classification". Query 79's entry pins no verdict, and I could not measure the pick (no model calls in this review).
- The builder's open point, answered: applying the floor where card 23's line shows is right under D15. The diagnosis's floor condition is "the note's condition holds", which is the selector's condition, not whether the line is emitted; card 23's line says the same fact, so a real classification question over that table is the same case D15 decided. The only risk is a misread of 79's wording, which is this finding.
- Worse than develop: no. An "ask" there says less than the answer bears, never more, and the table, its sources and card 23's line are unchanged. It is a verdict change on a gate query that the owner did not name, so the lead should either run the decision on 79's wording a few times before merge (about $0.0001 a call) or tell the owner it may move.

### J-30-03, minor: three properties of the change are not pinned by any test

Mutate one property, run the four touched test files (`<scratchpad>/card30_judge/mutate.py`), restore:

| Mutation | Result | What is unpinned |
|---|---|---|
| M1: the floor drops `classification_note is not None` (`graph.py:14994`) | GREEN, `478 passed` | No Write test hands the decision `asks_classification` to an answer that shows a classification (the rs334 shape) and asserts no floor. The diagnosis's risk table promised "a Write test asserts no note and no floor"; only the selector test exists (`test_answer_layout.py`). The code is correct today; nothing stops a later edit floors every classification question |
| M5: `_answer_parts` drops its own card 23 check (`graph.py:13740` to `:13742`) | GREEN, `478 passed` | The check that matters for a request that does not read `placement` (an older command line or web bundle, `_request_reads_placement`, `:10293`). The Write tests all set `reads_placement=True` (`test_write_answer_structure.py:145`), so only the `listing_tokens` check is exercised |
| M8: `think_node`'s `finally` stops cancelling `classification_task` (`graph.py:4207` to `:4208`) | GREEN, `478 passed` | The Think early-end path (ask back, cap hit, step error). Develop has no such test for `features_task` either, so this is parity, but the diagnosis's risk table asked for it. By reading, the code cancels on every non-search result and on an exception (`result is None`) |

- Worse than develop: no. Each is a test gap over code that reads correctly.

### J-30-04, minor: three documents do not yet name the change

- Query 79's entry still says "Plain language shows no table, so no line." (`testing/Test_queries_and_workflows.md`, query 79's third bullet). With this branch, Plain language shows card 30's line in the Notes for that answer (the diagnosis's "Test query" section says so). An owner retest could read the new line as a failure of 79. One clause fixes it.
- `docs/architecture/Model_architecture.md:209` lists `think.asks_features` among the classifier decisions and has no row for `think.asks_classification`; `src/system_03_search_agent/harness/task_tiers.py` has rows for every other decision point (`call_site="think.asks_features"`, `:170`) and none for it. The module says nothing reads it at runtime, so this is documentation drift only.
- Worse than develop: no.

## Checks

| Check | Result | Evidence |
|---|---|---|
| The note's condition | Holds on every answer it fires on. It fires only when a finding is a graph `SequenceVariant` and no finding's field is `clinical_significance` or `germline_classification` | `answer_layout.py`, `variant_classification_note`. `synth_findings` is the full display list (`graph.py:14096` comment), the same list the listing is built from. `SequenceVariant` comes only from graph rows (`graph_schema_constants.py:47`, `:140`); no table column shows a classification today (`TABLE_COLUMNS`, `answer_layout.py:307` to `:317`); a ClinVar row's finding is its `title` (diagnosis, cause link 2) |
| Never where a classification shows | Query 23: the dbSNP finding's field is `clinical_significance`, so the selector returns None and the floor cannot fire (it needs the note). LitVar2's finding is also `clinical_significance` (`tools/litvar2_lookup.py:1081`), which only suppresses the line, develop's state | Selector test `test_card30_no_line_when_a_shown_record_gives_a_classification`; mutation M6 turns it red |
| Once, both depths, after the list | Yes | `test_card30_the_line_shows_in_both_depths_once_after_the_list[plain_language]` and `[researcher]` pass; M13 (emit twice) turns it red |
| Not beside card 23's line | Yes on the web path; unpinned on the non-placement path (J-30-03) | `test_card30_beside_the_variant_table_only_card_23s_line_shows`; M4 turns it red, M5 stays green |
| The floor changes only the answer outcome | Yes. Only `trust_outcome` is reassigned (`graph.py:14995`), with the same `aggregate([trust_outcome, "ask"])` the other floors use (`:14958`, `:14977`); `claim_trusts` is not touched after `:14863`. Card 8 reads `claim_trusts` | `test_card30_a_classification_question_over_unclassified_variants_is_ask` asserts claim outcomes equal the baseline; M14 (floor to "flag") turns it red |
| A late, failed or `not_applicable` decision never floors | Yes. `_classification_asked` returns True only on a usable `asks_classification` pick; `_read_late_decision` returns None for a task still running past the grace, cancelled, or raising (`graph.py:1512` to `:1533`) | `test_card30_no_floor_without_the_decision[not_applicable]`, `[None]`, and the no decision arm; `test_card30_a_decision_still_running_past_the_grace_is_not_a_floor`; M2 turns the floor test red |
| Started, cancelled and dropped like `features_task` | Yes, line for line: started in `think_node` behind the same `not small_talk` guard (`:4192`), cancelled in Think's `finally` on every non-search result (`:4207`), read once in Write (`:14077`), dropped in `write_node`'s `finally` (`:13767`). Every route after Think reaches Write (`graph.py:15531` to `:15533`). A guardrail refusal ends before Think, so the decision is never started there | M9 and M10 turn their tests red; M8 stays green (J-30-03) |
| Never spends after a refusal | Yes, by the paths above. A Write refusal reads the decision at `:14077` before the writer call, and the `finally` drops anything left | as above |
| `DonePayload.decisions` bound | Fits. Decision points in a run: relevancy, injection, ask back, recent years, literature, paper links, asks features, asks classification, lead sentence, nine against `_MAX_DONE_DECISIONS` 16 (`:1242`), and `_done_decisions` truncates at the bound (`:1318`). The record fits `DecisionRecord` (name 26 characters against 64, two options against 12) | `grep -n '_DecisionSpec(\|_decide_point(' graph.py`; probe below |
| Description holds no test question | Yes. The instructions and both criteria are category rules; no query from `Test_queries_and_workflows.md` or the golden set appears. Lengths 271, 180 and 245 against `decide()`'s 1,000 | `<scratchpad>/card30_judge/probe_spec.py`: `check_description ok; instructions 271 criteria {'asks_classification': 180, 'not_applicable': 245}`, `fail_open in options: True` |
| One second worst case wait | Adds at most 1.0 s over develop, only when both decisions are still running at Write (J-30-01) | `probe_wait.py`: `features read done at 1.00s, classification read done at 2.00s` |
| `_SAFE_PICKS` edit | Correct and loosens nothing. The fake `decide` returns `_SAFE_PICKS.get(point)` (`test_bare_topic_clarification.py:297`); without an entry the new point gets a no pick record decided by the guard, which fails the existing "every decision is Jev" test. The added pick is the decision's own fail open side | file read |
| Tests | All pass | The four touched files plus every file that pins Think's decisions (`test_write_answers_sooner`, `test_breadth_plan`, `test_think_retry`, `test_topic_search`, `test_run_registry_stop_mid_write`, `harness/test_task_tiers`, `harness/test_decide`, `guardrail/test_guardrail_node_integration`, `guardrail/test_followup_guardrail`, `guardrail/test_reland_guardrail`, `synthesis/test_first_sentence_gap`): `995 passed in 125.07s (0:02:05)` |
| Worktree clean after mutations | Yes | `git status --short` printed nothing |

## Break it

`<scratchpad>/card30_judge/mutate.py`, one property per run over the four touched test files, the file restored after each:

| Mutation | Result |
|---|---|
| M1 floor without the shape check | GREEN (J-30-03) |
| M2 floor without the decision | RED, `test_card30_a_classification_question_over_unclassified_variants_is_ask` |
| M4 no `listing_tokens` card 23 check | RED, `test_card30_beside_the_variant_table_only_card_23s_line_shows` |
| M5 no `_answer_parts` card 23 check | GREEN (J-30-03) |
| M6 selector ignores classification fields | RED, `test_card30_no_line_when_a_shown_record_gives_a_classification` |
| M7 selector ignores the layer | GREEN, but equivalent today: only graph rows carry `SequenceVariant` |
| M8 Think keeps the decision running after an early end | GREEN (J-30-03) |
| M9 Write's `finally` keeps it running | RED, `test_card30_a_write_that_ends_early_stops_the_classification_decision` |
| M10 asked for small talk | RED, `test_card30_small_talk_is_never_asked_about_classification` |
| M13 the note emitted twice | RED, `test_card30_the_line_shows_in_both_depths_once_after_the_list[plain_language]` |
| M14 the floor through "flag" | RED, `test_card30_a_classification_question_over_unclassified_variants_is_ask` |

## Verdict

Nothing on this branch shows any person something worse than develop. The line is true wherever it fires and absent where a classification is shown; the floor moves only the answer level verdict and only toward caution; every path stops the new decision as `features_task` is stopped. The four findings are minor: a worst case wait at the one second bar, an unmeasured verdict risk on query 79 that is more cautious rather than less, three unpinned properties, and three documents to update.

VERDICT: PASS
