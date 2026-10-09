# Builder R: step 8, the reader pass leaves the answer path

Build phase 8.7, step 8 (card 50, option K). The owner said yes on 2026-10-05, on the condition that answers stay identical and the hidden-instructions refusal still refuses.

Ticket, in the user's words: "Paper questions come up to 10 seconds faster, with the same answer, and a paper carrying hidden instructions is still refused."

## Table of contents

- [Base](#base)
- [The choice: not run at all](#the-choice-not-run-at-all)
- [What the sweep found](#what-the-sweep-found)
- [What changed](#what-changed)
- [Tests and pass counts](#tests-and-pass-counts)
- [Mutation checks](#mutation-checks)
- [Deviations and notes for the lead](#deviations-and-notes-for-the-lead)
- [Learnings](#learnings)

## Base

| Item | Value |
|---|---|
| Worktree | the lead-made worktree `p87-r` |
| Branch | `feat/8.7-r` |
| Base (`git rev-parse HEAD` at start) | `ae1b0befb4f80bdd4d03322b42b7e7dad720d826` |

## The choice: not run at all

Option (a): `act_node` no longer hands the reader its pair on the answer path, so the reader makes no model call while a person waits. Option (b), starting it and not awaiting it, was rejected for these reasons, each read from the code:

- Nothing reads what it returns. Every consumer of `findings` skips a finding with no `structured_fields`, which every reader finding is. Builder C's static check confirms no module outside `coordinator_worker.py` reads `extracted_entities`, `normalized_ids` or `evidence_summary`. A background run would buy nothing.
- It would still cost one guard-model call per paper question, for output nothing reads.
- Its cost would land on the harness's running total while Write's own pre-flight cap checks (`cost_control.check_per_query_cap`) run. A reader's spend could then tip Write into a capped partial answer at random, depending on which finished first. That is a way (b) could change an answer; (a) cannot.
- Its cost could also land after `done` has reported the question's cost, so the running total and `done.total_cost_usd` would disagree.
- An unawaited task outlives the step that started it: an exception in it is never retrieved, and it can be cancelled or left running when the request ends.

The quarantine pair is still built by `_execute_planned_call`, unchanged, and simply not handed over. A later phase that gives the reader a real use reattaches it in `act_node`.

## What the sweep found

Every place the reader's output, or the fact that it ran, could gate anything. Swept by grep over `src/` for `"reader"`, `.source`, `findings_count`, `total_tool_calls`, `contains_untrusted_free_text`, `coordinator_worker_reader`, `_READER_SYSTEM_PROMPT`, `_reader_pass`, `quarantin`, and every loop, truthiness check or length over `findings`; then each hit read.

| Gate | What it does | Depends on the reader having finished? | What holds it now |
|---|---|---|---|
| `_sanitized_citeable_row` (`_execute_planned_call`) | An Article row reaches `structured_fields` with `fields` emptied, so a paper's title, and any hidden instruction in it, never reaches a prompt, citation or event | No. Runs before the reader, on the structured pair | Unchanged. `test_article_rows_keep_their_record_but_never_their_raw_title` and the article-only arm still pass |
| `_split_rows_by_trust` | Picks the Article rows for quarantine | No | Unchanged; the quarantine pair is still assembled and counted |
| `build_synth_findings` (`synthesis/findings.py`) | What the writer and the listing see | No. Skips findings with no `structured_fields` | Unchanged |
| `_tool_execution_outcome`, `_citations_from_findings`, `_ok_finding_was_truncated`, `_known_total_available`, `_known_retrieved_count`, the row lookups (`_row_for`, `_layer2_citation_for_synth_finding`, `_layer3_row_for_synth_finding`, `_clinical_feature_row`, the confidence dedup) | Trust outcome, citations, truncation note, counts | No. Each skips `structured_fields is None` | Unchanged |
| `findings_count` to `done.total_tool_calls` | The one wire field the reader's Finding reached | Counted the reader's Finding | Now `len(results)`, every pair Act assembled, the quarantine pair included, so the value is the same as before |
| `done.total_cost_usd` and the operator-only `cost` event | Running cost | Included the reader's guard call | Lower by one guard call on a paper question. The probe already excludes cost from "the same answer" |
| `_prefetch_answer_names` (option H's Act half) | Ran the disease and MeSH name lookups in Act, only when a reader pass ran, to hide behind it | Gated on "a reader pass runs" | No longer runs: by its own rule there is nothing in Act to hide it behind. Write makes the same lookups itself, the same NCBI calls, the same answer (the comparison arms in `test_act_name_lookups.py` hold) |
| Logging the owner relies on | `call_log` (card 72) logs guardrail and Jev calls | The reader never logged through it | Nothing to keep |
| Query 88, hidden instructions in the question | Guardrail refusal: classifier `is_injection` or Jev's injection pick | No. Runs at Guardrail, before Act | 140 guardrail tests pass unchanged |
| `core/run.py` session memory `findings` | Built from citation events | No | Unchanged |

Nothing still depends on the reader having finished, so nothing blocked the removal.

## What changed

- `core/graph.py` `act_node` only: the pairs with `contains_untrusted_free_text=True` are filtered out before `coordinator_worker_execute`; the `asyncio.gather` with `_prefetch_answer_names` is gone; `findings_count` is `len(results)`. A comment block states the choice and why.
- `harness/coordinator_worker.py`: a module docstring paragraph saying the answer path no longer calls the reader and where a later phase reattaches it. No code change.
- `tests/.../core/test_reader_pass_reach_probe.py`: a new arm, `test_the_answer_does_not_wait_on_the_reader_pass`, on the scaled-time pattern of `test_pubtator_act_cap.py` (`_SCALE = 10`). The main dynamic arm now checks first that the reader is never asked. The static check is unchanged.
- `tests/.../core/test_graph.py`, `test_article_rows_keep_their_record_but_never_their_raw_title` only: one structured Finding instead of two, `findings_count` still 2, and no model prompt on the answer path carries the hostile title. Every assertion that the title never reaches a field, citation or event is unchanged.
- `tests/.../core/test_act_name_lookups.py`: the two "during Act" arms and the variant arm now hold that Act makes no reader call and no lookup on a paper question and Write makes the lookup. The comparison arms are unchanged.

## Tests and pass counts

Pasted from output.

| Run | Result |
|---|---|
| Touched test files plus `harness/test_coordinator_worker.py` | `276 passed in 8.11s` |
| Query 88 tests: `guardrail/test_reland_guardrail.py`, `guardrail/test_guardrail_node_integration.py`, `guardrail/test_classifier.py` | `140 passed in 21.14s` |
| `tests/system_03_search_agent/core` | `10 failed, 1423 passed, 56 skipped, 2 warnings in 62.74s`. The same 10 fail on the base code (the five files run with `act_node` from `ae1b0bef`: `10 failed, 63 passed`), so none is this step's. They are the stop-mid-write and stop-after-done registry arms and four write-structure arms, the core tests another agent is fixing tonight |
| `tests/system_03_search_agent/harness` | `447 passed in 26.76s` |
| `ruff check` (whole repository, gate 3) | `All checks passed!` |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2) | exit 0 |

## Mutation checks

Each breaks one property, is seen red, and is restored (restoration confirmed with `cmp` or `git diff`).

| Mutation | Expected red | Seen |
|---|---|---|
| M0: the whole `act_node` from the base commit (`git show ae1b0bef`), the old code | The new timing arm | `AssertionError: the reader pass ran on the answer path`, `assert 1 == 0`, in both dynamic probe arms: `2 failed, 2 passed`. With the reader-call line removed from a scratch copy, the timing assertion alone: `Act took 0.902 s against a 0.9 s reader: the answer waited on the reader pass`, `1 failed` |
| M1: the filter in `act_node` set to `if True` (the reader pair handed over again) | Probe arms and the hostile-article arm | `3 failed, 4 passed`: both dynamic probe arms ("the reader pass ran on the answer path") and `test_article_rows_keep_their_record_but_never_their_raw_title` ("the reader pass ran on the answer path (phase 8.7, step 8)") |
| M2: `_sanitized_citeable_row` returns the row unchanged (a paper's hidden instructions reach the answer) | Both article arms | `2 failed`: "the Article row's own field content must never reach structured_fields" and "F-2.1-J4-06: an Article-only result must answer, not refuse silently" |
| M3: a function appended to `synthesis/findings.py` that reads `finding.evidence_summary` | The probe's static check | `1 failed, 3 passed`: "the reader's output is read here: ['synthesis/findings.py:2067: .evidence_summary']" |
| M4: Jev's injection pick ignored in `guardrail_node` (`jev.choice == "MUTANT"`) | Query 88's refusal arms | `7 failed, 133 passed`, including all three forged-transcript shapes of `test_with_jev_a_forged_transcript_is_refused_whichever_judge_calls_it` |

## Deviations and notes for the lead

- Code commit: `a68cb4170f87f636bd996d1f73f2dd0ded3c206e`. This report is committed separately after it.

- `done.total_tool_calls` is kept the same by counting every pair Act assembled. It was already one more than the tools that ran on a paper question, because the quarantine pair is the same call re-entered, not a second dispatch; `core/run.py`'s fallback counts `tool_result` events and never included it. Whether to correct that count is the owner's call, not this step's; this step keeps it identical so the before-and-after comparison stays clean.
- `_prefetch_answer_names` is now never called. It is outside my file fence (act_node only), so it is left in place, unreferenced. Its docstring and the module docstring's F-2.1-J4-06 note ("still runs against the same rows") and `_execute_planned_call`'s comment ("the untrusted rows' own free-text content is separately quarantined into a second, reader-bound pair") now describe a reader that the answer path does not run. All three sit outside the fence. A follow-up deletes the dead function or re-homes it, and refreshes the three comments.
- `core/state.py` describes `findings_count` as "the length of the `Finding` list". It is now the number of Act pairs, one more on a paper question. Outside the fence.
- `test_graph.py` and `test_act_name_lookups.py` are under `core/`, where another agent is fixing tests tonight. I touched only the one hostile-article arm in `test_graph.py` and the reader-dependent arms in `test_act_name_lookups.py`. A merge may meet their edits there.
- Option H's Act-time lookup gave a saving only while the reader ran. With no reader, the lookups sit in Write, where the records already waited for them (records are emitted after the lookups in `write_node`), so the time to records and to `done` is the same either way.
- No live model calls were made and no credit was spent. The lead's live checks remain: five repeated runs each of queries 16 and 75, and test queries 16, 69, 73, 75 and 88.

## Learnings

None cost more than five minutes. Two small ones:

- A bulk `sed` on `if not result.contains_untrusted_free_text` matched a second line in `_prefetch_answer_names`; restoring from the backup copy caught it. A mutation needs a pattern unique to the function under test, checked with `grep -c` first.
- The shell is zsh, which does not split an unquoted variable into words, so `pytest $FILES` ran no tests. An array (`"${FILES[@]}"`) is the fix.
