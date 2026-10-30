# Card 119 build: ten papers listed, five abstracts read

After picking a "How far back" window, an answer lists up to ten papers from that window, each with its title. The writer still reads five abstracts. A question with no window runs unchanged code.

## Table of contents

- [What changed](#what-changed)
- [Where this disagrees with the diagnosis](#where-this-disagrees-with-the-diagnosis)
- [Why the five abstracts still reach the writer](#why-the-five-abstracts-still-reach-the-writer)
- [Which five papers get abstracts](#which-five-papers-get-abstracts)
- [Tests](#tests)

## What changed

| File | Change |
|---|---|
| `src/system_03_search_agent/core/breadth_plan.py` | New `PUBMED_WINDOW_RESULT_CAP = 10`, used as the PubMed search's `retmax` only when a window is passed, on the gene path (`plan_first_stage`) and the topic path (`plan_topic_search`). `plan_literature_follow_up(pmids, cap=5)` takes its cap from the caller. |
| `src/system_03_search_agent/core/graph.py` | `_PlannedFollowUpCall.result_cap` carries the planned search's own `retmax` (read by `_pubmed_search_retmax`). `_PlannedNcbiEfetchToolCall.row_cap` carries it to the `pubmed_abstracts` title-row cut. `_lead_findings_quota` returns 10, plus the carried cap minus 5, at both `lead_quota=` sites. `_pubmed_abstract_rows` takes a `limit`. |
| `tests/system_03_search_agent/core/test_window_paper_cap.py` | New, ten tests. |

PubTator3's row cut is untouched.

## Where this disagrees with the diagnosis

The diagnosis says a quota of 15 keeps the five abstracts in the writer's slice. That holds only if there are exactly five abstract rows. `_pubmed_abstract_rows` emitted one abstract row per title row, so ten titles gave up to ten abstracts, twenty lead rows. `_allot_with_lead_quota` admits 15, queues the other five lead rows last, and still admits them under the display cap of 100. The final sort moves all lead-call rows to the front, so the writer's first 30 held all ten abstracts. Measured with the real row shaping and `build_synth_findings`:

| Row cap, lead quota | Abstracts in the first 30 |
|---|---|
| 5, 10 (today) | 5 |
| 10, 15 (the diagnosis alone) | 10 |
| 10, 10 | 10 |

The fix adds a limit inside `_pubmed_abstract_rows`: abstract rows exist for only five title rows. Ten titles plus five abstracts is 15 lead rows, equal to the quota, so nothing is left over.

## Why the five abstracts still reach the writer

- The limit applies only when the row cap is above 5, so an unwindowed answer passes `limit=None` and its rows are identical to develop's (a test compares them).
- The quota of 15 equals the lead row count, so every lead row is admitted ahead of the context rows.
- A test builds ten title rows, 50 context rows and the real quota, and counts exactly five abstracts and ten titles in the first 30 findings.

## Which five papers get abstracts

The five highest PMIDs, the newest. Search order could not be used: `plan_literature_follow_up` sorts ids by PMID before they reach the fetch, and the fetched records carry no search rank, so the order cannot reach `_pubmed_abstract_rows` inside the allowed files. The abstract rows keep the title rows' own order (by URL).

The topic path has no graph call, so no lead call exists and the quota is not used there. A windowed topic question still plans ten, lists ten titles and emits five abstract rows, covered by a test.

## Tests

- Windowed gene question plans `retmax` 10 and follows up on 10 ids; unwindowed plans 5 and 5.
- Windowed topic question plans 10; unwindowed 5.
- The follow-up carries the search's own cap (10 windowed, 5 not).
- Windowed rows: 10 titles, 5 abstracts, the 5 newest. Unwindowed rows equal develop's.
- Quota is 15 windowed, 10 otherwise.
- Writer's first 30: exactly 5 abstracts and 10 titles windowed; 5 and 5 unwindowed.
- Windowed topic question reads at most 5 abstracts.

Mutations, each turned a test red and was restored: the window check in the gene search, in the topic search, the follow-up id cap, the carried cap in the follow-up call, the row cut, the abstract limit, the quota. A first version read the search's `retmax` from the wrong attribute (the input is a root model), and the tests caught it.

Run: the new file plus `test_breadth_plan.py`, `test_breadth_wiring.py`, `test_topic_search.py`, `test_window_graph_papers.py`, `test_bare_topic_clarification.py`, `test_disease_breadth.py` and `test_pubmed_abstract_grounding.py`: 328 passed, including the 18,000-character block test unchanged. `ruff check` passes on the touched files. `isort --check-only` flags `graph.py` for the `contracts.events` import block at line 476, which this change does not touch.

Not measured (the lead's paid live checks): the windowed answer time, and the joined text length on MCP and GraphQL.
