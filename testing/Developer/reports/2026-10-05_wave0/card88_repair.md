# Card 88 repair draft: a better second draft is no longer thrown away

Build report, 2026-10-05, branch `fix/card88-repair-draft`, stacked on pull request 161 (`044f834b`). Paths are relative to `<repo-root>`. The previous report, `testing/Developer/reports/2026-10-05_wave0/card88.md`, found that in two of four short GERD answers a repair draft grounded more sentences on the same record and was discarded.

Verdict: the bar is not met at Researcher. Plain language reached 2 or more grounded sentences on 5 of 5 valid runs. Researcher reached 4 of 5. The one miss is the sentence check approving almost nothing, which this change does not touch. The two unrelated questions are no worse than baseline.

## Table of contents

- [The change in plain words](#the-change-in-plain-words)
- [What F-4.5-J-13 protects, and how it is kept](#what-f-45-j-13-protects-and-how-it-is-kept)
- [Live traces](#live-traces)
- [Tests](#tests)
- [Gate results](#gate-results)
- [Found on the way](#found-on-the-way)
- [What this verification does not cover](#what-this-verification-does-not-cover)

## The change in plain words

In the reader's words: "When the writer's second try at my GERD answer gives three checked sentences about the same paper, I see those three, not the first try's one."

`write_node` in `core/graph.py` runs a repair draft when the first answer left findings out. It used to keep the repair only when the repair cited a strictly larger set of records. It now also keeps the repair when both of these hold:

- The repair cites every record the first draft cited, possibly no new ones.
- The repair shows more grounded sentences than the first draft.

Nothing in the grounding, number, negation or quote checks changed, and the sentence check model is unchanged. Both drafts pass through the same `_ground_with_sentence_check` before the choice, so every sentence shown is a grounded sentence either way.

## What F-4.5-J-13 protects, and how it is kept

F-4.5-J-13 and F-4.5-A-06 (build phase 4.5's judge and adversary rounds, the tests in `tests/system_03_search_agent/core/test_write_completeness.py`) found that the old rule compared omission COUNTS. A repair that added two records while dropping one was accepted. The dropped record took its citation, its per-claim trust signal and any conflict flag with it, and the answer-level trust did not fall, so the loss was hard to see. The fix made acceptance a strict-superset test on the cited record set.

The new condition keeps that property. `reported_after >= reported_before` is still a superset test, so a repair that drops any record the first draft cited is still discarded, however many sentences it grounds. Only the case of an equal record set with more sentences is newly accepted, and it cannot lose a record, a citation or a trust signal.

## Live traces

Local traces with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, run with the card 88 diagnosis's write-step spies. "Model sentences" counts the claim tokens below the code-built "Found N" line.

| Question | Depth | Code | Model sentences per run | Runs with 2 or more | Seconds |
|---|---|---|---|---|---|
| GERD symptoms and risk factors | Researcher | PR 161, earlier report | 7, 3, 5, 3, 1, 4, 3, 3, 4, 1 | 8 of 10 | 13.3 to 26.3 |
| GERD symptoms and risk factors | Researcher | this change | 1, 4, 3, 3, 4 | 4 of 5 | 13.2 to 31.3 |
| GERD symptoms and risk factors | Plain language | PR 161, earlier report | 5, 3, 4, 3, 1 | 4 of 5 | 13.3 to 21.2 |
| GERD symptoms and risk factors | Plain language | this change | 2, 2, 4, 2, 2 | 5 of 5 | 12.6 to 20.2 |
| Diseases associated with BRCA1 | Researcher | PR 161 | 2, 0, 2 | 2 of 3 | 17.3 to 21.6 |
| Diseases associated with BRCA1 | Researcher | this change | 2, 2, 3 | 3 of 3 | 21.4 to 24.5 |
| Mediterranean beneficial variants | Plain language | PR 161 | 6, 0, 0 | 1 of 3 | 9.4 to 25.7 |
| Mediterranean beneficial variants | Plain language | this change | 1, 1, 0 | 0 of 3 | 13.1 to 31.1 |

Notes on the runs:

- The PR 161 rows for BRCA1 and the Mediterranean question were run on this worktree with `core/graph.py` set to `044f834b`'s version, just before this change.
- One more plain GERD run crashed in the guardrail after 5.4 seconds, before any tool or writing step ran. It is excluded, and a replacement run was made: the last 2 in the plain row. The crash is described under "Found on the way".
- Every BRCA1 run, before and after, ended at outcome `ask`, as on develop today (board plan W1, run `brca1_dis`).

Why the Researcher miss and the Mediterranean spread are not this change:

- By construction, this change cannot cost a sentence. Given the same two drafts and the same sentence-check verdicts, it keeps the old choice unless the repair shows MORE grounded sentences on at least the same records. Any run that is shorter is shorter because the writer or the sentence check behaved differently that run.
- The Researcher miss (run 1, 1 sentence): the sentence check approved 0 of 5 reworded sentences in the first draft and 1 of 10 in the repair. Both drafts showed one sentence, so neither rule would have changed the answer.
- The Mediterranean runs: the sentence check approved 0 sentences in all six of its calls across the three after runs. The baseline's 6-sentence run came from a repair whose sentence check approved 3 of 10. This is the variance card 89 already describes.

## Tests

Both new tests are in `tests/system_03_search_agent/core/test_write_completeness.py`. They serve two hand-written drafts through the real harness, grounding pass and `write_node`, and record which draft's grounded sentences reach the restatement step. That step is the first thing downstream of the choice. The record-value sentences these fixtures use are dropped there as restatements of the listing, so the shipped prose alone cannot show which draft won.

| Test | Proves | Red on |
|---|---|---|
| `test_a_repair_on_the_same_records_with_more_sentences_is_kept` | A repair on records 1 and 2 with three grounded sentences beats a first draft on records 1 and 2 with two | the code before this change, `044f834b`'s `core/graph.py` |
| `test_a_repair_with_more_sentences_that_drops_a_record_still_loses` | A repair with three sentences, all on record 2, loses to a first draft on records 1 and 2 | a rule that accepts on the sentence count alone |

The red proofs swapped `core/graph.py` for a scratch copy taken with `git show`; `git stash` was not used. The existing arm `test_a_repair_that_drops_a_reported_finding_is_discarded` still passes. It does not catch the count-only mutation on its own, because its repair has a smaller cited set and a code-built listing that carries record 1 back in.

## Gate results

| Gate | Command | Result |
|---|---|---|
| 2, import order | `isort --check-only --diff src tests services tracker alembic .claude .github` | pass |
| 3, lint | `ruff check` over the whole repository | pass |
| 4, unit suite | `pytest -m "not integration" -q -rs` | 6817 passed, 0 failed, 143 skipped, 1 xfailed |

## Found on the way

- The guardrail crashes when the guard model's reply has no text. `parse_classification` (`guardrail/classifier.py:370`) calls `content.strip()` on a `None` content, raising `AttributeError`.
- The run then ends as "This query failed unexpectedly", outcome `refuse`, after 5.4 seconds with no tool called. Every other unreadable reply in that function raises a typed error and fails closed as a transient error, which tells the person to retry.
- This happened once in 17 runs. It is not this card's, so it was left untouched; it is a candidate for its own card.
- The earlier card 88 builds used `git stash push` and `git stash pop` for their red proofs, before the instruction not to use the shared stash. Each pop restored only this worktree's three source files, and `git status` showed nothing else, so no other session's entry appears to have been taken.

## What this verification does not cover

- The deployed `develop` behaviour. Every run here was local, against this worktree's code.
- The 150-question golden run, which must hold at least 101 of 150 answered. The lead runs it after merge.
- Speed. The change adds no model call: the repair draft was already made and grounded, and only which one ships changes.
- The Researcher miss, which belongs to the sentence check's rejection of faithful rewordings, the same cause card 89 has.
