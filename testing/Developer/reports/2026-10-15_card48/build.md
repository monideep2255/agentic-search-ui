# Card 48 redesign build report, 2026-10-15

Base: branch fix/card48-ask-which-aspect at 36b5747d (pull request #230), clean tree, today's develop merged in. Owner decision of 2026-10-15: the classifier also judges whether a message names a record, and a message that does is always searched, never asked which aspect.

## Table of contents

- [What changed](#what-changed)
- [Live results](#live-results)
- [Guard tier measurement](#guard-tier-measurement)
- [Tests and mutations](#tests-and-mutations)
- [Gates](#gates)
- [Learnings](#learnings)

## What changed

- `core/graph.py`, `_ASK_BACK`: a third option, `names_a_record`, with its own criterion. The instructions end with one sentence: if the message points at one specific record (identifier, accession, variant in any notation, DOI or paper number), choose it. Only an `ask_back` pick asks; `proceed` and `names_a_record` both search. `fail_open` stays `proceed`. No word list, no test text in the prompt.
- `_names_a_record` is unchanged in behaviour: it still only turns an `ask_back` pick into a search (docstring now says so).
- Unchanged: first message of a conversation only, the 1.0 s bound, a late or failed decision searches.
- `tests/.../test_bare_topic_clarification.py`: five new tests. `testing/Test_queries_and_workflows.md` query 112: one query bullet and one "what you should see" bullet.

## Live results

Setup: CLASSIFIER_PROVIDER=jev, GUARD_MODEL and PLAN_MODEL deepseek/deepseek-v4-flash, SYNTH_MODEL z-ai/glm-5.2, PER_QUERY_COST_CAP_USD=0.25. "Asked" means the live pick was ask_back and `_names_a_record` was False (the gate as built). Five runs per text through `_decide_point`.

| Set | Texts | Calls | Asked back | Notes |
|---|---|---|---|---|
| V-48-04 table (14 texts incl. 2 controls) | 14 | 70 | 0 | 70 of 70 picked `names_a_record` by the classifier, not by the code check |
| Ten own record questions (c.dup, NM_ HGVS, p.Arg change, rs id alone, RCV, PMCID, DOI, GEO, SRR, gene plus V600E) | 10 | 50 | 0 | 50 of 50 picked `names_a_record` |
| Broad: query 112's two plus five own | 7 | 35 | 35 (100 %) | same as the as-built spec on the same texts (35 of 35) |
| Ordinary (query 1 and nine more) | 10 | 50 | 5 (`ESBL E. coli isolates?`, 5 of 5) | the as-built spec asks that text 5 of 5 too, so not caused by this change |
| Ordinary, five more | 5 | 25 | 0 | |

Decision latency in the final runs: median 0.21 to 0.24 s, maximum 0.96 s (v4, own), 1.54 s once.

End to end through `run_streaming` (14 runs, three rounds, `think` event and tool_start counted):

| Text kind | Runs | Asked back | Searched (tools ran, done) |
|---|---|---|---|
| Record: c.dup change, RCV accession, PMCID, DOI, GEO dataset, HGVS delAG, BRAF V600E | 7 | 0 | 7 |
| Broad: tree of life x3, apple trees, photosynthesis | 5 | 5 | 0 |
| Ordinary: BRCA1 diseases, Salmonella blaCTX-M-15 | 2 | 0 | 2 |

Spend: not read from the account; about 1,000 decision calls plus 14 full runs, estimated well under the $0.80 budget.

## Guard tier measurement

CLASSIFIER_PROVIDER=guard, 20 texts, 2 runs each (40 calls, six in flight at once). Decisions in time (at or under 1.0 s): 5 of 40 (12.5 %); 35 of 40 over the bound, latency median 1.44 s, p90 2.63 s, max 2.84 s. The verifier's figure before this change was 7 of 55 in time (12.7 %). The bound is unchanged. Guard picks over all 40 calls: `names_a_record` 14, ask_back 1 (`tree of life`, 1 of 2), the rest `proceed`. Asked back: 1 of 40, and all 20 texts that are not broad subjects were searched.

## Tests and mutations

| Test | Mutation (one property, then restored) | Result |
|---|---|---|
| `test_a_names_a_record_pick_searches_and_never_asks` (2 cases) | long path asks on any pick but `proceed` | red (2 tests) |
| same | short path asks on any pick but `proceed` | red (3 tests) |
| `test_the_ask_back_decision_offers_a_names_a_record_judgement` | option removed from the spec | red (2 tests) |
| `test_the_ask_back_description_passes_the_seams_own_check` | 200 characters added to the instructions | red (1 test) |

Also added: `test_a_names_a_record_pick_writes_no_choices_on_the_longer_path`, `test_the_record_check_still_never_forces_an_ask_back`. The file: 78 passed.

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed |
| `isort --check-only src tests services tracker alembic .claude .github` | exit 0 |
| `pytest tests/system_03_search_agent/core tests/system_03_search_agent/harness -m "not integration" -q` | 2132 passed, 56 skipped, 1 deselected |

## Learnings

- `decide` rejects instructions or a criterion over 1,000 characters. My first wording was 1,008: every live decision raised ValueError and the loop read it as no decision, while all stubbed tests stayed green. Now pinned by a test that calls the seam's own check.
- The first wording (a record check placed first, with "title" and "any other single named record") made `Tell me about the tree of life.` proceed 5 of 5 and the other broad texts drift to 0 to 5 of 5. Keeping the as-built instructions untouched and appending the one record sentence restored 35 of 35. Two rounds, about 10 minutes.
- Pre-existing, not changed: `ESBL E. coli isolates?` (a test queries document text, three words) is asked back by the as-built spec on every run.
