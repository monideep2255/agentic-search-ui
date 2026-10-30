# Card 119 build: ten papers listed, five abstracts read

After picking a "How far back" window, an answer lists up to ten papers from that window, each with its title. The writer still reads five abstracts. A question with no window runs unchanged code.

## Table of contents

- [What changed](#what-changed)
- [Where this disagrees with the diagnosis](#where-this-disagrees-with-the-diagnosis)
- [Why the five abstracts still reach the writer](#why-the-five-abstracts-still-reach-the-writer)
- [Which five papers get abstracts](#which-five-papers-get-abstracts)
- [Tests](#tests)
- [Fix round](#fix-round)

## What changed

Round one, as built. The fix round changed the abstract choice, the quota and the row cut: see [Fix round](#fix-round).

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

Superseded in the fix round: the five are now the best-ranked papers that have an abstract. Round one's text follows.

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

## Fix round

2026-10-30, one round. In the person's words: "When I pick a window, the summary draws on the best-matching papers from that window that have an abstract, the same way it does today, and the list shows up to ten."

### What changed in this round

| File | Change |
|---|---|
| `src/system_03_search_agent/core/breadth_plan.py` | New `search_rank(ids)`: the valid PMIDs in the search's own order, normalised as `select_ids` does (shared helper `normalise_uid`). New `LITERATURE_FOLLOW_UP_MAX_IDS = 20`; `plan_literature_follow_up` trims its cap to it. |
| `src/system_03_search_agent/core/graph.py` | `_PlannedNcbiEfetchToolCall.row_cap` is now `None` by default and `search_rank` is new; both are set only on a windowed search's abstracts call. Act passes `_BREADTH_ROW_CAP` when `row_cap` is None, and passes `search_rank`. `_best_ranked_abstract_urls` walks the title rows in search rank and keeps the first five with a non-empty abstract. `_lead_findings_quota` removed; both sites use `_LEAD_FINDINGS_QUOTA` again. `_pubmed_search_retmax` trims to 20. |
| `tests/system_03_search_agent/core/test_window_paper_cap.py` | Rewritten, 22 tests. |

### The search's sort

The windowed PubMed search is sorted by relevance. `_search_call` (`breadth_plan.py`) passes no `sort`, and `NcbiEfetchInput.sort` is `Literal["relevance"]` with that default (`ncbi_efetch_schemas.py`, the field after `retmax`). ESearch's id list keeps that order through `ncbi_eutils_actions` (the `idlist` is kept as returned, then capped) and `_search_ids`. `select_ids` still sorts the fetch's ids by PMID, numerically; the fetch request is unchanged, and the rank travels beside it on the planned call.

### Each finding

| Id | Outcome | Why |
|---|---|---|
| J-119-01 | Fixed | A paper with no abstract never takes a reading slot: the walk skips it and moves to the next ranked paper. |
| J-119-02 | Fixed | Three tests drive the compiled graph (picked window, no window, and the cystic fibrosis shape) and read the writer's own prompt: ten titles, exactly the expected abstracts, "Found 10 papers". Five more drive `_execute_planned_call`. Act ignoring the planned `row_cap` (mutation M1) turns seven tests red, both graph tests included. |
| J-119-03 | Fixed, removed | No test could show the quota of 15 was needed. The function is gone and both sites pass `_LEAD_FINDINGS_QUOTA` (10). At 10, the writer's first 30 findings still hold ten titles and five abstracts beside 50 context rows (test). |
| J-119-04 | Moot | Search rank decides, not PMID. The tests use PMIDs of four, six, seven and eight digits, so rank, number order and text order each pick a different five (mutations M5, M6). The remaining PMID sort, `select_ids`, was already numeric. |
| J-119-05 | Left | Not in this round: PubTator3 rows. |
| J-119-06 | Left | Not in this round: count line wording. |
| J-119-07 | Fixed | The cap is trimmed to 20, PubTator3's `pmids` bound, both in `plan_literature_follow_up` and in the carried cap. A cap of 25 now plans 20 ids for both calls instead of raising. |
| J-119-08 | Fixed | Every call except a windowed abstracts call carries `row_cap=None`, and Act cuts it at `_BREADTH_ROW_CAP`, as develop. A test sets `_BREADTH_ROW_CAP` to 3 and sees a GEO summary cut to 3. An unwindowed abstracts call carries no cap either. |
| A-119-01 | Fixed | The cystic fibrosis shape, ranks 1 to 5 with no abstract and rank 6 with one: the writer reads rank 6 (Act test and graph test). |
| A-119-02 | Fixed | The five read are the best-ranked five with an abstract, as develop's five are the top five of the same relevance order. |
| A-119-03 | Left | True on develop; not in this round. |
| A-119-04 | Left | True on develop; not in this round. |
| A-119-07 | Left | True on develop; not in this round. |

### Unwindowed is develop's code

- The unwindowed abstracts call carries `row_cap=None` and no rank, so Act calls the shaping function exactly as develop does, and `_pubmed_abstract_rows` gets `limit=None`.
- Seven records, two without an abstract, were shaped by develop (b5690f98, exported with `git archive`) and by this branch: the JSON output is byte-identical. The test pins develop's captured rows and checks them both through the shaping function and through `_execute_planned_call`.
- The graph test with the same words typed and no click plans `retmax` 5, and the writer gets five titles and their five abstracts.

### Mutations

Each mutation was applied, the card's test file run, and the file restored from an in-memory copy.

| Mutation | Result |
|---|---|
| M1 Act ignores the planned `row_cap` | 7 failed |
| M2 Act drops `search_rank` | 4 failed |
| M3 follow-up builder carries no rank | 5 failed |
| M4 abstract presence not checked in the walk | 4 failed |
| M5 highest PMID number decides | 4 failed |
| M6 PMID text order decides | 4 failed |
| M7 no abstract limit | 6 failed |
| M8 planner clamp removed | 1 failed |
| M9 carried-cap clamp removed | 1 failed |
| M10 other calls cut by `PUBMED_RESULT_CAP` | 1 failed |
| M11 unwindowed abstracts call carries a cap | 1 failed |
| M12 follow-up planner not given the cap | 8 failed |
| M13 `search_rank` sorted by PMID | 6 failed |
| M14 windowed gene search back to `retmax` 5 | 4 failed |

### Tests and gates

- The card's file plus `test_breadth_plan.py`, `test_breadth_wiring.py`, `test_topic_search.py`, `test_window_graph_papers.py`, `test_bare_topic_clarification.py`, `test_disease_breadth.py`, `test_paper_links_wiring.py`, `test_write_answer_structure.py` and `synthesis/test_pubmed_abstract_grounding.py`: 438 passed.
- `ruff check .`: all checks passed. Gate02's `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0.
- Not run: any live call. The lead's live checks own the cystic fibrosis, caffeine and Marfan questions.
