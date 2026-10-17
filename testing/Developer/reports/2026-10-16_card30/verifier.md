# Card 30 step 1 fresh verifier

Pull request #261, branch `fix/card30-unclassified-variants-say-so`, build commit `3d8988ca`, fix commit `cbe6f623`, on develop `78c68c1c`. Fresh verifier after the one fix round, 2026-10-16. Worktree `<worktrees>/card30-ver`, detached at `cbe6f623`. Probes under `<scratchpad>/card30_ver/`.

## Table of contents

- [Findings](#findings)
- [The shared read in Write](#the-shared-read-in-write)
- [Unchanged by the fix](#unchanged-by-the-fix)
- [Documents](#documents)
- [Earlier findings](#earlier-findings)
- [Clinical features answers, offline against develop](#clinical-features-answers-offline-against-develop)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

(Filed as established.)

### V-30-01, minor: queries 66, 72 and 22 do not say what a person now sees

- Where: `testing/Test_queries_and_workflows.md`, query 66 (`:587` onward) and query 72 (`:1513` onward), both asking `What phenotypic features are associated with Marfan syndrome?`. Query 66's entry records develop's Plain language answer as "Found 1 disease record, 37 sequence variant records and 3 gene records for Marfan syndrome". When the answer lists graph variants like these, the branch adds card 30's line to its Notes (offline A/B below: one line in each of the 8 cases with graph variants, nothing else changed). Neither entry mentions it, which is the gap J-30-04 closed for query 79. Query 22's last bullet still says the answer must "keep working exactly as it did last time", beside the new bullets saying its verdict changes.
- Live, tonight's query 66 run listed no graph variants and showed no line, so a retester may or may not see it.
- Worse than develop: no. The line is true wherever it shows, and no record or sentence is lost. Fixable with one clause in each entry.

## The shared read in Write

The fix replaces two sequential reads with one `asyncio.gather` (`src/system_03_search_agent/core/graph.py:14078` to `:14081`). `_read_late_decision`, `_clinical_features_asked`, `_usable_choice`, `_run_decisions`, `_cancel_if_pending` and `_drop_features_decision` are byte for byte develop's (function bodies hashed on both trees: all `same`), and `_LATE_DECISION_GRACE_S` is 1.0 on both (`graph.py:1252`, develop `:1222`). So develop's read is `_clinical_features_asked` alone, and the probe compares it with the branch's exact gather line.

Probe `<scratchpad>/card30_ver/probe_shared_read.py`: nine states per decision (absent, done early with the pick, done early with `not_applicable`, done early with None, late but inside the grace, still running past the grace, failed early, failed inside the grace, cancelled), every pairing (81), each under three deadlines (none, 0.2 s, already passed), run twice.

| Check | Result |
|---|---|
| The features read returns what develop's returns | 486 of 486 pairings across both runs: `f == dev_f` |
| The classification read returns what it returns alone | 486 of 486: `c == alone_c`. A failed or cancelled features decision never changes it, and the reverse |
| Neither read raises when the other decision fails or is cancelled | No exception in any pairing. `_read_late_decision` returns None for a raising or cancelled task (`graph.py:1535`) and `_decide_point` never raises (`:1336` to `:1345`), so `gather` has nothing to propagate |
| Both tasks popped from the run's record, none left running | `popped=True`, `left=0` in every pairing |
| Worst wait, no deadline | Branch 1.00 to 1.06 s, develop 1.00 s. The excess is one loop tick plus jitter on a machine at load average 16 to 23 (the few rows flagged by my 50 ms tolerance moved between runs, and only by timing, never by result) |
| Worst wait, deadline 0.2 s | Branch 0.23 to 0.25 s, develop 0.21 s. Both reads are cut by the same step deadline |
| Deadline already passed | Branch 0.00 to 0.01 s, develop 0.00 s |
| Write itself cancelled during the read | `CancelledError` raised, as on develop's single await |
| Write under an `asyncio.timeout` that fires during the read | `TimeoutError` raised cleanly |

What the person can wait for that develop never made them wait for: when the features decision has finished and the classification decision is still running, the features value is used up to 1 s later, because both are awaited together (probe row `features=early_yes class=late_past_grace_yes t=1.00 dev_t=0.00`). That is the 1 s the diagnosis accepted ("the worst case adds 1 second, normally 0") and the brief's bar; the worst total wait stays develop's 1 s, where the build commit's was 2 s.

Evidence, not a finding, and the same on develop: when Write is cancelled during the read (a stop mid answer), the decision tasks have already been taken off the run's record, so `write_node`'s `finally` cannot cancel them, and they run on to `decide()`'s own bound (probe: `features decision still running: True classification still running: True`; develop: `features decision still running after cancel: True`). The branch adds the classification decision to a gap develop already has for the features decision; the cost is at most one classifier call.

## Unchanged by the fix

`git show cbe6f623 -- src/` touches two files only:

- `core/graph.py`, one hunk at `:14073`: the two `await` lines become the `asyncio.gather`, plus a two line comment.
- `harness/task_tiers.py`: the new `think.asks_classification` row.

The note's condition (`variant_classification_note`, `synthesis/answer_layout.py`), the floor's rule (`graph.py:14998` to `:14999`, `if classification_note is not None and classification_asked and trust_outcome != "refuse": trust_outcome = aggregate([trust_outcome, "ask"])`) and `_ASKS_CLASSIFICATION`'s instructions and criteria (`graph.py:1214` to `:1237`) are exactly the build commit's. `answer_layout.py` has no change in the fix commit at all.

## Documents

| Edit | True? | Evidence |
|---|---|---|
| Query 79, Plain language now "carries card 30's line that ClinVar's classification was not retrieved" | Yes | The selector fires on graph `SequenceVariant` findings with no classification field, and Plain language builds no variant table, so card 23's line is absent and the skip does not apply. The adversary's live run 6 (query 79, Plain language) shows the line once |
| `docs/architecture/Model_architecture.md:210`, the `think.asks_classification` bullet | Yes | "Only on asks_classification, and only when the variants listed carry no ClinVar classification, is the answer's verdict floored at ask; any other outcome leaves the verdict as computed" matches `graph.py:14998` and `_classification_asked`'s fail open read. A refusal is also never floored, which the bullet does not say but does not contradict |
| `harness/task_tiers.py:178` to `:187`, the new row | Yes | `call_site="think.asks_classification"`, `step="think"`, `tier="classifier"`, as `_ASKS_CLASSIFICATION.point` and its start in `think_node` (`graph.py:4192` to `:4195`) |
| `test_task_tiers.py`, 16 rows | Yes | `grep -c 'call_site=' task_tiers.py` prints 16; `test_all_sixteen_call_sites_are_present` passes. The module's own docstring says nothing reads the table at runtime (`task_tiers.py:20` to `:22`) |

## Earlier findings

Mutations by `<scratchpad>/card30_ver/mutate.py`, one property each, every symbol kept, over seven test files (`test_graph`, `test_write_answer_structure`, `test_bare_topic_clarification`, `test_write_answers_sooner`, `test_run_registry_stop_mid_write`, `test_answer_layout`, `test_first_sentence_gap`), file restored after each; `git status --short` empty afterwards.

| Mutation | Result |
|---|---|
| V1 sequential reads in place of the gather | RED, `test_card30_two_late_decisions_share_one_grace` |
| V2 the gather's two results swapped | RED, `test_a_features_question_reserves_the_diseases_features_in_the_prompt` |
| V3 the features read loses Write's step deadline | GREEN, 557 passed. The same mutation on develop's single read is also green (358 passed over `test_graph`, `test_write_answers_sooner`, `test_bare_topic_clarification`, `test_first_sentence_gap`), so this is develop's gap, not the fix's |
| V4 floor without the note's shape check | RED, `test_card30_no_floor_when_the_answer_shows_a_classification` |
| V5 `_answer_parts` card 23 skip removed | RED, `test_card30_answer_parts_skips_its_line_beside_card_23s_table` |
| V6 Think stops cancelling the classification decision | RED, `test_card30_think_ending_the_search_stops_the_classification_decision[ends0]` |
| V7 the floor applied on a refusal too | GREEN, 557 passed. The code guards it (`trust_outcome != "refuse"`, `graph.py:14998`), and develop's three neighbouring floors carry the same guard. A test gap, not a defect |
| V8 Write's `listing_tokens` card 23 skip removed | RED, `test_card30_beside_the_variant_table_only_card_23s_line_shows` |

| Finding | Closed? | Evidence |
|---|---|---|
| J-30-01, A-30-01 (2 s worst case wait) | Closed | The shared read probe above: worst 1.00 to 1.06 s against develop's 1.00 s; V1 turns the new test red |
| J-30-02 (query 79's verdict could move) | Not a code fix; measured | The fix round did not touch it. Live decision probe below |
| J-30-03 M1 (floor shape check unpinned) | Closed | V4 red |
| J-30-03 M5, A-30-02 (`_answer_parts` skip unpinned) | Closed | V5 red. The test's populate check (`assert seen`) proves the final `_answer_parts` call was reached with `reads_placement=False` |
| J-30-03 M8 (Think's cancel unpinned) | Closed | V6 red. The test calls `think_node` alone, so Write's own drop cannot mask it |
| J-30-04 (three documents) | Closed | See "Documents" |

## Clinical features answers, offline against develop

Probe `<scratchpad>/card30_ver/test_zz_card30_ver_ab.py`, run from the scratchpad against each tree in turn (nothing copied into either tree). It builds the Marfan answer that query 66 and query 72 ask for: the disease's MedGen record with 70 clinical features, 43 graph rows and, in half the cases, four graph sequence variants (the live Plain language answer lists "37 sequence variant records"). It writes the answer at both depths, with the features decision picked `asks_features` or `not_applicable`, and the classification decision absent or `not_applicable`: 16 cases. It compares every token the reader sees, the done event's verdict, every claim's trust and the clinical feature lines in the writer's prompt.

| Case | Result, branch against develop |
|---|---|
| No graph variants (8 cases) | Every token identical, verdict identical (`answer`), claim trust identical, feature prompt lines identical (10 with `asks_features`, 0 without) |
| With graph variants (8 cases) | Identical once card 30's one line is set aside; exactly one card 30 line in the Notes; verdict, claim trust and feature prompt lines identical |

So the features decision's effect on the answer is unchanged at both depths. The only change on a features answer is card 30's line, and only when graph variants are listed, which is the card's designed behaviour (see V-30-01 for the documents).

## Tests and lint

| Command | Result |
|---|---|
| `pytest -q` over `test_bare_topic_clarification`, `test_graph`, `test_run_registry_stop_mid_write`, `test_write_answers_sooner`, `harness/test_task_tiers`, `synthesis/test_first_sentence_gap`, `test_write_answer_structure`, `synthesis/test_answer_layout`, `harness/test_decide` (every file that names `features_task`, `asks_features`, `_read_late_decision` or the new decision, plus the touched files) | `633 passed in 54.18s` |
| `ruff check` (gate 03, no path) | `All checks passed!` |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 02) | exit 0, `Skipped 2 files` |
| `gh pr checks 261` at head `cbe6f623` | Accessibility, Frontend gates, Integration suite, Python gates (1, 2, 3, 4, 6, 9): all `pass` |

## Live runs

Four runs through `core.run.run_streaming()` on the branch tree, `reads_placement=True`, session ids `card30-ver-<label>`, settings as card 115's adversary (`CLASSIFIER_PROVIDER=jev`, guard and plan models `deepseek/deepseek-v4-flash`, `PER_QUERY_COST_CAP_USD=0.25`, the writer from the local env). Script `<scratchpad>/card30_ver/live.py`; it wraps both late reads to time them.

| Run | Question | Depth | Features pick | Classification pick | Card 30 line | Trust outcome and line | Both reads waited | Done at | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Which BRCA1 variants are pathogenic? | Researcher | not_applicable (jev) | asks_classification (jev) | Yes, once | ask, "Based on 57 sources cited, not yet confirmed" | 0 ms, both done on entry | 12.62 s | $0.0071 |
| 2 | Query 22, CFTR clinically significant | Plain language | not_applicable (jev) | asks_classification (jev) | Yes, once | ask, "Based on 71 sources cited, not yet confirmed" | 1 ms and 0 ms, both done on entry | 12.94 s | $0.0104 |
| 3 | Query 66, Marfan phenotypic features | Plain language | asks_features (jev) | not_applicable (jev) | No (no graph variants this run) | answer, "Based on 12 sources cited" | 0 ms, both done on entry | 10.42 s | $0.0074 |
| 4 | What variants are in GCK? | Researcher | not_applicable (jev) | not_applicable (jev) | Yes, once | ask, "Based on 68 sources cited, not yet confirmed" | 0 ms, both done on entry | 11.01 s | $0.0090 |

What each shows:

- Run 1 also carries "Note: no written summary could be checked against the records", develop's own structured fallback floor, so its "ask" would be "ask" on develop too. The only token naming "pathogenic" is card 30's line.
- Run 2 is the floor proved live: 72 of 72 claim verdicts `answer`, no fallback, incomplete, partial or failed search note (the truncation note is not a floor; `graph.py:10990` has no `aggregate`), so only card 30's floor moves it to "ask", as the owner's row for query 22 says.
- Run 3: the features answer carries "Clinical features MedGen lists for Marfan syndrome" with `asks_features` read in 0 ms; 83 of 83 claims `answer`.
- Run 4's "ask" is again develop's structured fallback floor (the note is present); the classification pick was `not_applicable`, so card 30 did not floor it. The line shows, true, as designed (A-30-04).

Decision probe `<scratchpad>/card30_ver/decide_probe.py`, the new decision alone, five calls per wording: query 79 "What diseases are caused by variants in the HNF1A gene?" read `not_applicable` 5 of 5, and query 66's wording read `not_applicable` 5 of 5, all by jev. With the adversary's 1 of 1, query 79 has 6 of 6 (J-30-02's risk not seen).

Spend: $0.034 for the four runs plus about $0.001 for the ten decision calls, under $0.04 of the $0.60 allowed.

## Verdict

Nothing on this branch shows any person something worse than develop:

- The fix's shared read returns the same features value as develop in every state tested (486 pairings), never raises or loses one decision through the other, and keeps the worst total wait at develop's 1 s.
- The clinical features answers are identical to develop's at both depths, except card 30's one true line when graph variants are listed.
- Every earlier finding is closed or measured. Every new test goes red under its mutation.
- The fix did not touch the note, the floor or the description. CI and both lint gates pass.

The one finding, V-30-01, is a minor gap in the test queries document.

VERDICT: PASS
