# Card 88 build: written answers survive the grounding pass

Build report, 2026-10-05, branch `fix/card88-89-answers-survive`. It covers card 88 causes A and B, plus card 57. Paths are relative to `<repo-root>`. Diagnosis: `testing/Developer/reports/2026-10-05_card88/diagnosis.md`.

Scope as finally decided by the lead:

- The card 17 guard, built first in `d9a8eabb`, is taken out of this change. Card 17 will be redesigned on its own.
- Card 89 leaves this change. Its cause is the sentence check rejecting sentences that add facts, not the grounding rules.

Verdict: the bar is not met. It asks for two or more grounded sentences on 5 of 5 runs at each depth.

- Researcher reached 8 of 10 across two batches of five, 4 of 5 in each.
- Plain language reached 4 of 5 valid runs. A sixth run stopped at the guardrail before any writing.

Each miss traces to a check this change does not loosen: the sentence check model, or the repair draft's strict-superset rule. Neither of them is the naming rule this change edits.

## Table of contents

- [The change in plain words](#the-change-in-plain-words)
- [Baseline against after](#baseline-against-after)
- [Why the remaining runs miss](#why-the-remaining-runs-miss)
- [Card 89 and the Mediterranean question](#card-89-and-the-mediterranean-question)
- [Tests](#tests)
- [Gate results](#gate-results)
- [What this verification does not cover](#what-this-verification-does-not-cover)

## The change in plain words

In the reader's words: "When I ask about the symptoms of GERD, the answer the writer wrote is no longer thrown away only because it says GERD, and a paper's citation shows the words behind every sentence that cites it."

| Card | What changed | Where |
|---|---|---|
| 88, cause A | The Researcher depth line now carries plain language's rule 3a clause: a sentence that puts an abstract, summary or description in the writer's own words carries the record's exact supporting words inside the marker. Reworded sentences now reach the sentence check instead of being stripped unseen. The line sits in the dynamic suffix, and the cached prompt prefix is unchanged. | `synthesis/findings.py`, `_DEPTH_DIRECTIVES["researcher"]` |
| 88, cause B | A record may be named by a short form its own retrieved text defines, such as "Gastroesophageal reflux disease (GERD)". The definition is read with the published Schwartz and Hearst abbreviation rule, from that record's text only. The short form must be mostly capitals, and its long form must share a word with that record's own title. A sentence names the record when it writes the short form exactly as the record did. Each record is judged on its own, so one paper's definition never names another paper. There is no word list, and no question or disease name appears in code or prompts. | `synthesis/grounding.py`, `defined_short_forms`, `_abbreviated_long_form`, `_names_its_record`, `run_grounding_pass` |
| 57 | A record cited by several sentences no longer shows only the first sentence. Its citation `claim_text` holds the record words each sentence was checked against, in reading order: a copied sentence's own text, or a reworded sentence's quote, numbers included. Entries stay whole within the 1000-character bound. `finding_by_citation_id`'s first-wins rule was left as it is, because every claim with one `citation_id` carries the same finding. | `core/graph.py`, `_citations_from_grounded_claims`, `_joined_checked_words` |

Unchanged on purpose:

- The substring check.
- The number, negation and quote checks.
- The sentence check model and its fail-closed rules.
- The repair draft's strict-superset rule.
- The existing record-naming rule, item 12.16 part 4. It now also accepts a defined short form, and nothing else about it changed.

## Baseline against after

Local traces with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, run with the card 88 diagnosis's write-step spies (`raw/local_write_trace.py` there, parameterised by question and depth). The question is "What are the typical symptoms and risk factors of GERD?". "Model sentences" counts the claim tokens below the code-built "Found N" line.

| Set | Code | Model sentences per run | Runs with 2 or more | Seconds |
|---|---|---|---|---|
| Researcher, baseline | develop at 9a13e983 | 2, 3, 0 | 2 of 3 | 12.6 to 23.7 |
| Researcher, after, batch 1 | this change | 7, 3, 5, 3, 1 | 4 of 5 | 13.3 to 22.5 |
| Researcher, after, batch 2 | this change | 4, 3, 3, 4, 1 | 4 of 5 | 13.8 to 26.3 |
| Plain language, baseline | develop, from the diagnosis | 1 and 0 live, 2 local | 1 of 3 | 14.6 to 28.5 |
| Plain language, after | this change | 5, 3, 4, 3, 1 | 4 of 5 | 13.3 to 21.2 |
| Researcher, earlier build | with the card 17 guard (`d9a8eabb`) | 5, 0, 2, 3, 1, 1, 2, 2, 1, 2 | 6 of 10 | 10.8 to 25.8 |
| Plain language, earlier build | with the card 17 guard (`d9a8eabb`) | 3, 3, 3, 3, 4, 4, 2, 3 | 8 of 8 | 14.6 to 22.2, one at 54.5 |

Notes on the runs:

- One more plain run in the after batch stopped at the guardrail with a transient error before any writing (outcome `refuse`, no tools called). It is excluded, as the diagnosis excluded one, and a replacement run was made. That replacement is the 1 in the plain row.
- The 54.5-second run in the earlier build had Jev HTTP errors on three Think and Plan decisions, which fell back to the guard tier. That happens before the write step.
- Plain language's earlier 8 of 8 and its 4 of 5 now differ only by the card 17 guard, which can only remove sentences. The gap is run-to-run variance in the sentence check and the writer, not this change.

## Why the remaining runs miss

All four short runs were read in the trace logs.

| Run | Sentences | Cause |
|---|---|---|
| Researcher batch 1, run 5 | 1 | The sentence check approved 0 of 4 reworded sentences in the first draft. The repair draft grounded 2 sentences, but both cited the same abstract as the first draft, so it was not a strict superset of the records covered and was discarded. |
| Researcher batch 2, run 5 | 1 | The sentence check approved 0 of 5 in the first draft. The repair grounded 1 sentence. |
| Plain language, run 5 | 1 | The sentence check approved 1 of 5 in the first draft. The repair draft grounded 3 sentences on the same record and was discarded by the strict-superset rule. |
| Plain language, excluded run | 0 | A transient guardrail error before the write step. |

The two levers that would close these gaps are both outside this card, and both are checks:

- The sentence check model rejects rewordings that add a word to their quote, such as "hallmark" where the quote says "typical". Changing that means loosening the one bounded model exception in `production-standards`. Not done.
- The repair draft's strict-superset rule (`core/graph.py`, the repair block in `write_node`, F-4.5-J-13) keeps a first draft with one sentence over a repair with three when both cite the same records. A rule that also keeps a repair covering the same records with more grounded sentences would have rescued three of the four misses. That is a draft-selection decision, not a grounding check, and it needs its own card.

## Card 89 and the Mediterranean question

Measured before the scope changed (3 baseline and 5 after-change runs of "Are there any beneficial variants typically found in people of mediterranean descent?" in plain language):

- Familial Mediterranean fever was named on screen in 0 of 3 baseline runs and 0 of 5 after.
- The writer names the disease. A draft named "Familial Mediterranean Fever" in 3 of 3 baseline runs and 3 of 5 after.
- The sentence check rejects that sentence because it says more than its quote. For example, it adds "an inherited inflammatory disease caused by mutations in the MEFV gene" over a quote that only says "mainly affects people of Mediterranean descent ...".
- The naming rule never sees it, so card 89 needs its own build.

## Tests

Every new test was run against develop's source (`origin/develop` checked out under the new tests). Eight fail there. The five rejection tests hold on develop by design, since develop already rejects those sentences. Each of them was run against a deliberate break of the new code and went red.

| Test | Proves | Red on |
|---|---|---|
| `test_sentence_check.py::test_a_short_form_is_read_only_where_the_text_defines_it` | "GERD" is read from "Gastroesophageal reflux disease (GERD)", not from text that never defines it, and not from "(Turkey)" or "(TBD)" | develop; a reader that takes any bracket |
| `::test_an_opening_sentence_names_its_record_by_the_short_form_the_record_defines` | An approved "GERD is when ..." opening sentence survives | develop |
| `::test_the_short_form_rule_can_fail` | Mutation proof: with no short forms read, it is dropped | develop |
| `::test_a_short_form_the_record_never_defines_does_not_name_it` | A record that never defines GERD is not named by it | the never-defines mutation proof below |
| `::test_the_never_defines_check_can_fail` | Mutation proof: a reader that ignores the record's text lets the sentence through | develop |
| `::test_a_short_form_another_record_defines_does_not_name_this_one` | Another record's definition does not carry over | pooling definitions across records |
| `::test_a_shared_title_does_not_carry_one_papers_short_form_to_another` | A same-title paper that never defines GERD is not named by it | pooling definitions across records |
| `::test_a_short_form_for_something_off_the_title_does_not_name_the_record` | A long form that shares nothing with the title names nothing | removing the title check |
| `::test_a_number_not_in_the_quote_still_fails_with_a_defined_short_form` | "GERD affects 20 percent of adults" over a quote with no number never reaches the model and is stripped | removing `numbers_are_supported` from the exact checks |
| `::test_the_number_check_can_fail` | Mutation proof for the test above | develop |
| `test_answer_quality.py::test_researcher_asks_for_the_quote_a_reworded_sentence_rests_on` | The Researcher line carries rule 3a's clause | develop |
| `test_graph.py::test_a_record_cited_by_two_sentences_shows_the_words_behind_each` | Card 57: the second sentence's quote, with "40%", is on the shared citation | develop |
| `test_graph.py::test_joined_checked_words_keep_each_entry_whole_within_the_bound` | Card 57: no entry is cut mid-number; the 1000-character bound holds | develop |

Dropped with the card 17 guard: the Tay-Sachs "patients" pair, the shared-title-words switch test, the every-title-the-same test and the card 17 mutation proof. They covered card 17 only, or passed on develop once the guard was gone.

## Gate results

| Gate | Command | Result |
|---|---|---|
| 2, import order | `isort --check-only --diff src tests services tracker alembic .claude .github` | pass |
| 3, lint | `ruff check` over the whole repository | pass |
| 4, unit suite | `pytest -m "not integration" -q -rs` | 6815 passed, 0 failed, 143 skipped, 1 xfailed |

The earlier build's suite run had one `TimeoutError` in `test_streaming_endpoints.py`. Eight parallel suites were sharing the machine then, and the file passes 36 of 36 alone. This run had no failures.

## What this verification does not cover

- The deployed `develop` behaviour. Every run here was local, against this worktree's code.
- The 150-question golden run, which must hold at least 101 of 150 answered. The lead runs it after merge.
- Live repeated runs of the owner's kind on `develop`, and test query 75's other questions (caffeine and exercise, statins) for the restatement rules.
- Speed against the 20-second ceiling across many questions. Write-step times here sit inside it, but rule 3a at Researcher sends more sentences to the sentence check on every Researcher answer, at 343 to 611 ms per check call as measured in the diagnosis.
- Card 17's wrong-paper risk. It is unchanged from develop: the short-form rule only adds a name a record defines for its own title's words.
- Card 57 on screen. The web app does not render `claim_text` today; the change shows in `s3 --json`, the API's citation events and session memory's claim summaries.
