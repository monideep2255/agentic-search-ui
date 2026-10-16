# Card 29 fix round, 2026-10-15

Fix agent, dial position 3, the one fix round. Base 9dfad8e3 on fix/card29-abstract-sentence. Nothing is committed; files are left staged by name for the lead.

The lead's design (DECISIONS.md, 2026-10-15): a paper PubMed marks retracted never gets a quoted sentence; a sentence cut short when an abstract is trimmed is never offered or shown; each of the five papers gets its own classifier decision, run in parallel, asked for a sentence that states a finding answering the question and reads on its own, or none; the MCP response keeps develop's citation keys.

## Table of contents

- [Findings closed](#findings-closed)
- [What changed](#what-changed)
- [Mutations](#mutations)
- [Live proof](#live-proof)
- [Gates](#gates)
- [Left open](#left-open)
- [Learnings](#learnings)

## Findings closed

| Finding | Closed | Test that holds it |
|---|---|---|
| A-29-01, A-29-12, A-29-05, A-29-10 (retracted papers) | Yes | `test_a_paper_pubmed_marks_retracted_is_never_asked_about_and_shows_nothing`, `test_an_abstract_carrying_a_retraction_notice_is_treated_as_retracted`, `test_a_retracted_paper_is_not_asked_and_holds_its_place`, `test_a_record_pubmed_marks_retracted_carries_that_flag`, `test_a_retraction_comment_marks_the_record_retracted` |
| J-29-10, A-29-02, A-29-13 (cut sentences) | Yes | `test_a_sentence_cut_short_by_the_trim_is_never_offered_or_shown`, `test_the_shown_sentence_is_checked_against_the_untrimmed_abstract`, `test_a_cut_tail_is_never_a_candidate`, `test_a_sentence_ending_in_a_trim_marker_is_never_verified` |
| A-29-16 (batch picks aims) | Yes, batch removed | `test_each_paper_gets_its_own_decision_and_each_is_recorded`, `test_the_decisions_run_together_not_one_after_another` |
| A-29-03, J-29-12 (aims, methods, scope, review coverage) | Partly: wording changed and live-measured, a model can still err | `test_the_instructions_and_criteria_fit_decides_limit_and_name_what_to_skip`; live table below |
| A-29-04 (pronoun subject) | Partly: the criteria ask for a sentence that reads on its own; two live sentences still open with "These" | live table below |
| J-29-03 (MCP allowlist) | Yes | `test_no_cost_and_auth.py` is back to develop's bytes; `test_citation_keys_card29.py` holds the keys |
| J-29-08 (null key on rollback) | Yes | `test_a_citation_with_no_sentence_has_no_snippet_key` (contract and write_node) |
| J-29-06 (cancel on every exit) | Yes | `test_the_pick_is_cancelled_when_the_answer_ends_without_reading_it`, `test_a_pick_still_running_when_the_answer_ends_is_cancelled` |
| J-29-07 (grace past the write budget) | Yes | `test_the_grace_never_waits_past_the_write_budget` |
| J-29-05 (accessibility) | Yes | `AnswerScreen.sourceSnippet.test.tsx`, two new tests |
| A-29-06, J-29-01 (the "every surface" claim) | Yes | build.md line 36 now says what is true |

## What changed

Retracted papers:

- The PubMed fetch already returns the record's publication types and its comment list. `ncbi_eutils_actions._extract_pubmed_articles` now sets `fields["retracted"] = True` when the types include "Retracted Publication" or "Retraction of Publication", or a comment has RefType RetractionIn. Time cost: none. It reads XML the same efetch call already returned, so there is no new network call.
- The flag is withheld from every citable row (`_NCBI_EFETCH_ROW_IDENTITY_FIELDS`), so it is never a fact the answer cites. A record that is not retracted is byte for byte what it was.
- `core/graph._snippet_papers` reads the flag from the held record and passes it on. A retracted paper keeps its place among the first five, is never asked about and shows no sentence.
- An abstract whose text carries a retraction or withdrawal notice is treated as retracted, whatever the record says. `snippets.has_retraction_notice` matches the shape of a notice about the paper itself ("this article has been retracted", "notice of retraction", "policy on article withdrawal"). It reads no topic word. A clinical use of the word ("opioid withdrawal", "the drug was withdrawn") is a tested non-match.

Cut sentences:

- The abstract the pick reads is now the fetched record's own text (up to 4,000 characters), not the 2,000-character copy the findings trim cuts. When only the trimmed copy is held, it is marked cut when it ends in the trim's ellipsis or sits at 2,000 characters.
- `snippets.abstract_candidates` drops the cut tail and any sentence ending in a trim marker (the ellipsis or "[truncated]"). `verified_sentence` also refuses a sentence ending in a marker, and checks the sentence against the untrimmed text, never the trimmed copy.
- A side gain: a conclusion past character 2,000 is now offered when it is complete.

What gets picked:

- The batched Jev call is gone, with its cap helper and its fallback. `pick_snippets` asks one `decide()` per paper (Jev first, the guard tier on failure) through `asyncio.gather`, inside the existing 1 s grace.
- Instructions are generic and under 1,000 characters (about 600), with a criteria line for "none" under 1,000. They ask for the one sentence that states a finding or result answering the question and can be read without the sentences before it. Aims, objectives, methods, scope, background and review-coverage sentences are "none". No word list and no test-question word; a test checks the wording for the test questions' topics.
- Each decision is appended to the run's records through an `on_decision` callback that `core/graph` passes in (`_run_decisions(harness).records.append`), so it reaches `done.decisions` as every other decide() point does. Live: 129 `write.snippet` records over 30 runs.

MCP and the wire:

- `CitationPayload.snippet` now leaves the key out when empty (`exclude_if`, the same pattern as `TokenPayload.placement`). A citation without a sentence has exactly develop's keys on every surface, so a rollback to develop reads every saved row.
- `adapters/mcp/server._citations_without_snippet` clears the sentence on both MCP outputs (a live answer and a reopened one). MCP's keys are exactly develop's, and the builder's allowlist widening is reverted.

Source card:

- The sentence stays in the card's summary, so it shows while the card is closed. The summary's accessible name is now the markers, the title and the layer only (`aria-labelledby`), set only when a sentence is present. Clicking or dragging on the sentence no longer opens or closes the card (`preventDefault` and `stopPropagation`), and its cursor is a text cursor.
- Accessibility check: no existing Playwright accessibility spec renders a source card with a sentence (the fake backend emits none), so none was run for this card. The two unit tests above hold the name and the click. A 1280 and 390 pixel look is still unchecked by eye.

## Mutations

Each mutation was applied to one line, the card 29 tests were run, and the line was restored byte for byte (the file diff was re-read after).

| Mutation | Result |
|---|---|
| Remove `_drop_snippet_pick(...)` from `write_node`'s `finally` | 1 failed (`test_the_pick_is_cancelled_when_the_answer_ends_without_reading_it`) |
| Replace the grace clamp with `pass` | 1 failed (`test_the_grace_never_waits_past_the_write_budget`) |
| Ignore the record's retracted flag | 1 failed (wiring retracted test) |
| Use the trimmed finding copy, never the record | 1 failed (`test_the_shown_sentence_is_checked_against_the_untrimmed_abstract`) |
| Keep the cut tail as a candidate | 2 failed |
| Ask a retracted paper | 4 failed |
| Ignore the abstract's own notice | 2 failed |
| Ask the papers one after another | 1 failed (`test_the_decisions_run_together_not_one_after_another`) |
| Drop the `on_decision` call | 2 failed |
| `verified_sentence` stops refusing a marker | 1 failed |
| Do not set the flag in the PubMed parse | 3 failed |
| Pass MCP citations through unchanged at the fold | 1 failed (`test_a_live_answer_leaves_the_abstract_sentence_out`) |
| Remove `exclude_if` from `snippet` | 2 failed |
| Remove the click guard on the sentence | 1 failed (vitest) |
| Remove `aria-labelledby` | 1 failed (vitest) |

Not caught by a mutation: clearing the sentence at the reopened-answer return only (the MCP reopen tool needs a database to run end to end; the helper it calls is tested).

## Live proof

Method: `core/run.py` `run_streaming`, `reads_placement=True`, `CLASSIFIER_PROVIDER=jev`, `GUARD_MODEL` and `PLAN_MODEL` `deepseek/deepseek-v4-flash`, `SYNTH_MODEL` `z-ai/glm-5.2`, `PER_QUERY_COST_CAP_USD=0.25`. No Opus. Total spend $0.615 against the $0.80 budget. 30 runs with the fix, 10 control runs (the same code with `_start_snippet_pick` turned off). "Retracted" and "in real abstract" come from an independent PubMed efetch of each shown PMID, publication types and comments included, not from the code under test. "Complete" is that check plus a terminal full stop and no ellipsis. "Answers" is the fix agent's reading of the sentence against the question.

Runs and times (wall seconds to the `done` event):

| Question | Runs | Papers asked | Papers with a sentence | Pick time | Time to answer |
|---|---|---|---|---|---|
| Hydroxychloroquine and COVID-19, Researcher | hcq1, hcq2, hcq4, hcq5, qhcq1 to 5 (hcq3 was a transient guardrail error at 10 s, no answer, not a fix result) | 3 to 4 of 5 | 1 each | 349 to 679 ms | 12.07, 13.02, 22.25, 23.34, 14.52, 14.86, 12.12, 13.02, 18.3 |
| Acute migraine, Clinical brief | mig1 to 5, qmig1 to 5 | 5 of 5 | 3 to 4 | 359 to 813 ms | 35.59, 12.95, 8.13, 11.35, 9.61, 7.17, 10.21, 11.91, 11.84, 10.9 |
| Ileal nodular hyperplasia, colitis and autism, Researcher | mmr1 to 5 | 3 of 5 | 2 each | 234 to 966 ms | 11.82, 13.16, 12.63, 8.74, 13.7 |
| Caffeine and exercise performance, Plain language | caf1 to 5 | 5 of 5 | 4 to 5 | 349 to 885 ms | 20.88, 16.18, 10.87, 12.03, 10.9 |

Time against the 20 s rule:

- 4 of 30 runs were over 20 s: hcq4 22.25, hcq5 23.34, caf1 20.88 and mig1 35.59. All four ran in the first sitting, while the 6-minute unit suite ran on the same machine (load average 32 to 41). In mig1 the guard step took 5.7 s, Think 3.2 s and the writer 25 s; the pick had finished in 0.51 s, in parallel, so it added nothing.
- The second sitting ran with nothing else of mine running, alternating fix and control. Hydroxychloroquine with the fix: 14.52, 14.86, 12.12, 13.02, 18.3 (mean 14.56, max 18.3). Control: 17.35, 12.52, 13.35, 12.3, 14.04 (mean 13.91, max 17.35). Migraine with the fix: 7.17, 10.21, 11.91, 11.84, 10.9 (mean 10.41, max 11.91). Control: 10.23, 10.64, 7.3, 9.38, 15.12 (mean 10.53, max 15.12). Every run was under 20 s, and the fix adds no measurable time (the pick is done long before the writer; no run waited out the grace).
- Retraction check: the retracted papers were in the cited five on every hydroxychloroquine run (1 each) and every autism run (2 each), and none was asked about or shown. Independent check of all 81 shown sentences: 0 on a paper PubMed marks retracted, 81 of 81 word for word in the real abstract, 0 incomplete, 0 cut.
- Cost: each paper's decision is about $0.00002 and runs 4 to 5 at a time; 129 `write.snippet` records were in `done.decisions` over the 30 runs.

Every distinct shown sentence (17 distinct over 81 shown; the count is how many of the 30 runs showed it):

| PMID | Sentence (start) | Runs | Answers | Retracted | Complete |
|---|---|---|---|---|---|
| 25355191 | Lower caffeine doses (1) do not alter the peripheral whole-body responses to exercise; (2) improve vigilance... | 5 | yes | no | yes |
| 33388079 | Caffeine appears to improve physical performance in both trained and untrained individuals. | 1 | yes | no | yes |
| 33388079 | Supplementation with caffeine has been shown to acutely enhance various aspects of exercise performance in many but not all studies. | 4 | yes | no | yes |
| 36615805 | The meta-analysis revealed that the time to exhaustion in running tests was improved with caffeine (g = 0.392...). | 5 | yes | no | yes |
| 34291426 | Consuming lower doses of caffeine (e.g., 2-3 mg/kg) appears to be comparably ergogenic to consuming high doses... | 2 | yes | no | yes |
| 34033621 | Caffeine increased VO2max in elite athletes, which contributed to improvement in high-intensity endurance performance. | 1 | yes | no | yes |
| 32589582 | Caffeine intake has also shown ergogenic effects, which are attributed to different factors... | 2 | partly (background, "also") | no | yes |
| 11583104 | It can be a powerful ergogenic aid at levels that are considerably lower than the acceptable limit of the International Olympic Committee... | 3 | partly ("It" needs the sentence before) | no | yes |
| 32373993 | These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections. | 7 | yes, but "These studies" needs the sentence before | no | yes |
| 32373993 | Hydroxychloroquine has been demonstrated to limit the replication of SARS-CoV-2 virus in vitro. | 3 | partly (in vitro only) | no | yes |
| 26178694 | For 2-hour headache relief, standard dose triptan achieved better outcomes (42 to 76% response) than ergots... | 6 | yes | no | yes |
| 26178694 | Standard dose triptans relieved headaches within 2 hours in 42 to 76% of patients... | 4 | yes | no | yes |
| 30681821 | Lasmiditan, ubrogepant, and rimegepant are currently emerging acute migraine therapies that may be added to the arsenal of current migraine management. | 10 | no (scope and background, not a finding) | no | yes |
| 38568487 | These new treatments have not been associated with vasospasm or increased cardiovascular risk... | 10 | partly (a finding, but "These new treatments" needs the sentence before) | no | yes |
| 34128998 | Compared with placebo, triptans and nonsteroidal anti-inflammatory drugs used individually were significantly associated with reduced pain at 2 hours and 1 day... | 8 | yes | no | yes |
| 11241044 | We have reported colitis with ileal lymphoid nodular hyperplasia (LNH) in children with regressive autism. | 5 | partly (the authors' own earlier report) | no | yes |
| 16003132 | The severity of ileal LNH was significantly greater in ASD children compared with controls... | 5 | yes | no | yes |

Reading of the table:

- Yes 11 of 17 distinct sentences, partly 5, no 1. The migraine answer shows the weak pair every time (30681821 and 38568487, 10 runs each): the classifier prefers them to the abstract's efficacy sentences, which it picked in the adversary's per-paper path. The criteria cannot force a model's reading; the next lever is a model or wording change, which is the owner's call.
- The three retracted papers the adversary found (32205204, 11007230, 9500320) are never shown. The autism and hydroxychloroquine answers show sentences only from papers that PubMed does not mark retracted.

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 (Skipped 2 files) |
| `pytest tests/system_03_search_agent -m "not integration" -q` (run twice, both before the MCP test file was split out) | 7020 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 252.87s (first run 371.29s, same counts) |
| `pytest tests/system_03_search_agent/adapters/mcp/test_citation_keys_card29.py -q` | 2 passed |
| `npm run build` | built, only the existing large-chunk warning |
| `npx vitest run --testTimeout=90000 --maxWorkers=2` | Test Files 71 passed (71), Tests 647 passed (647) |

## Left open

Not in this round, recorded as open: A-29-07, A-29-08, A-29-09, A-29-11, A-29-14, A-29-15, J-29-02, J-29-04, J-29-09, J-29-11.

Also open from this round:

- A-29-03 and A-29-04 are only partly closed (see the live table): the classifier still picks a "These ... " sentence and an "emerging therapies" sentence on the migraine papers.
- A pick that completes but is cancelled at the grace is still not charged (J-29-04), and the per-paper decisions now each run their own cost-cap check through `decide()` with no registered in-flight bound.
- 1280 and 390 pixel rendering of the card is unchecked by eye.

## Learnings

- A frontend suite that passes in 175 s on a quiet machine timed out in 7 to 10 tests at a load average of 32 to 41 (other agents running). `npx vitest run --testTimeout=90000 --maxWorkers=2` passed all 647. Judge a timeout failure under load by rerunning that way before reading it as a regression. Cost: about 10 minutes.
- A test that cancels a `write_node` task from outside does not raise `CancelledError`: `write_node` ran to the end of its 30 s stub. The cancel-on-exit property is therefore pinned through the failed-answer exit and the finished-answer exit instead. Whether `write_node` swallows a stop is not looked at here.
- A task cancelled before its first step never runs its body, so a test that checks a stub's `except CancelledError` sees nothing. Keep the task object and assert `task.cancelled()`.
- The first slow live runs (22 to 36 s) ran while the unit suite ran. Run live timing only on a quiet machine, and pair each run with a control.
