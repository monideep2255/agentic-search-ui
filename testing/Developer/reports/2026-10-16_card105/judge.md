# Card 105 judge report

Card 105, pull request #260, branch `fix/card105-window-leaves-undated-papers-out`, commits `4e6c44b9` and `952a7ea9` on develop `78c68c1c`. Read in a detached worktree at the head, compared against a second detached worktree at `origin/develop`. No live runs: code, tests and local probes with every tool stubbed. Paths are under `src/system_03_search_agent/` unless written in full; line numbers are the branch's. Probes and their output are in `<scratchpad>/card105_judge/`.

## Table of contents

- [Tests and gates run](#tests-and-gates-run)
- [Checks](#checks)
- [What the person sees, branch beside develop](#what-the-person-sees-branch-beside-develop)
- [Break it](#break-it)
- [Findings](#findings)
- [Verdict](#verdict)

## Tests and gates run

| Run | Result |
|---|---|
| The two touched files and every file under `tests/system_03_search_agent/core/` naming `publication_window`, `_answer_call_ids`, `_PlannedToolCall` or `_execute_planned_call`, 16 files | `587 passed in 41.66s` |
| `ruff check` with no path, from the worktree root | `All checks passed!` |
| `isort --check-only src tests services tracker alembic .claude .github` | exit 0 |

## Checks

| Check | Result | Evidence |
|---|---|---|
| The flag is set only on a picked window | Pass | One setter in the whole of `src/`: `core/graph.py:7209` `if publication_window is not None:` then `:7212` `dataclasses.replace(planned, undated_papers_left_out=True)`. `publication_window` is `_picked_publication_window(query)` (`:6899`), which needs a click on a stored offer (`:3956` to `:3969`). Default `False` (`:4718`) |
| Only the gene path's own graph call | Pass, with a note | The setter sits in plan_node's final `else` branch on `planned`, index 0, before any other call is appended. That branch also carries the disease anchor and an unresolved graph call; only `("Gene", "articles")` hops to Article (`tools/cypher_templates.py:268`), so on those the filter finds nothing and returns `output` unchanged (`:7591`). The GO context call is built separately (`_build_planned_go_terms_call`) and never carries the flag. The topic path (`:7165`) has no graph call |
| Same words typed without a pick (card 36's lost window) run develop's code | Pass | Probe "S1 typed words, no offer": the branch and develop print the same answer, "Found 2 article records for BRCA1, of 3487 available: PMID:10026184 [1] and PMID:10417300 [2]" with the same truncation note. Also `test_an_unpicked_window_keeps_the_graph_s_papers`, which goes red under mutation M14 |
| Article rows removed before both pairs | Pass | `:8605` to `:8606` replace `output` before `_split_rows_by_trust(output.rows)` (`:8607`) and before `_cypher_output_to_structured_fields(output, ...)`; mutation M6 (quarantine reads the unfiltered rows) goes red |
| `row_count`, `total_available`, `truncated`, `status` agree | Pass | `:7593` to `:7602`: all three counts from `kept`, `truncated=False`, `ok` with nothing kept becomes `empty`; the summary line reads the new output (`"1 row(s) of 1"` asserted). Mutations M3, M4, M5 each go red |
| A non-Article row in the same result is kept | Pass | `test_undated_papers_left_out_drops_only_article_rows` asserts `["NCBIGene:672"]`; mutation M2 (drop every row) goes red |
| `_answer_call_ids` cannot change another question's ids | Pass | The added block (`:12765` to `:12773`) runs only when a planned call carries the flag, and the flag has the single setter above. A plan is built per run from `state["tool_calls"]`; no other code copies the flag. Mutation M7 (block ignores the flag) goes red |
| Empty window line, exact text per label | Pass | The labels are `clarify.py:254` to `:256`: "the last 12 months", "the last 5 years", "the last 10 years"; none begins with "from", so no "from from". Probe output: "No PubMed papers from the last 12 months were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here." and the same with "the last 5 years" and "the last 10 years", each 150 characters or fewer |
| Its gene symbol source | Pass | `:10024` to `:10031`: the `pubmed_abstracts` follow-up's `gene_symbol`, set at Plan from Think's resolved mention, uppercased (`:7248` to `:7253`), never read from a response |
| Never shows on a failed search or one that returned papers | Pass in code, half untested | `:10022` returns None on `error` or on any id. Probe S5 (search error): only "The background search of PubMed did not finish ..." shows. Probe S3 (ids): no line. A search that ended with status `empty` (what `ncbi_eutils_actions.py:750` returns) shows the line (probe S6), which is right. The failed-search half has no test: J-105-02 |
| Window finds nothing and everything else is empty | Refuses, without the line | Probe S1, see the table below and J-105-01 |

## What the person sees, branch beside develop

Every question is "recent papers on BRCA1", the person clicks a "How far back" choice, and the graph returns only its two undated 1999 papers (as the real `gene_articles_one` template does: it returns Article vertices only).

| Probe | Develop shows | The branch shows |
|---|---|---|
| S3: PubMed finds one paper | Two 1999 papers first, "of 3487 available", then the 2024 paper, a truncation note | "Found 1 pubmed record for BRCA1: BRCA1 and a recent finding [1]." and nothing older |
| S2 and S6: PubMed finds none, the gene record is there | Two 1999 papers, then the gene record, a truncation note | "Found 1 gene record for BRCA1: BRCA1 [1]." then the line "No PubMed papers from the last 5 years were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here." |
| S1: PubMed finds none and every other source is empty | Answer: the two 1999 papers | Refuse: "I could not find grounded evidence for this. Try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=NCBIGene%3A672". No window line |
| S4: PubMed fails and every other source is empty | Ask: the two 1999 papers and "The background search of PubMed did not finish ..." | Refuse: "One of my searches did not finish, so I could not find grounded evidence this time. Ask again to retry, or try NCBI's cross-database search: ..." |
| A gene typed as `NCBIGene:672` | The two 1999 papers | The gene record only, no line; with no gene record, the S1 refusal |

Every lost record in this table is a graph Article row on a picked window, the loss the owner's decision names and accepts. No answer gains a call, so nothing is slower; the guard tier reader pass over quarantined titles no longer runs on these questions.

## Break it

One property mutated at a time in `core/graph.py`, the two touched test files run, the file restored with `git checkout`. `git status --short` is empty after.

| Mutation | Result |
|---|---|
| M1 the filter keeps Article rows | red: `test_undated_papers_left_out_drops_only_article_rows` |
| M2 the filter drops every row | red: the same test |
| M3 `total_available` not recomputed | red: the same test |
| M4 `truncated` not reset | red: the same test |
| M5 an all-Article result stays `ok` | red: `test_a_result_of_only_articles_becomes_empty_not_ok` |
| M6 the quarantine split reads the unfiltered rows | red: `test_undated_papers_left_out_drops_only_article_rows` |
| M7 the answer ids block ignores the flag | red: `test_the_windowed_abstracts_call_answers_only_when_the_flag_is_set` |
| M8 the answer ids block never adds | red: the same test |
| M9 the line ignores a failed search | green, 57 passed. With it, probe S5 shows "No PubMed papers from the last 5 years were found for BRCA1" directly above "The background search of PubMed did not finish". J-105-02 |
| M10 the line ignores papers found | red: `test_a_picked_window_with_papers_in_it_carries_no_such_line` |
| M11 the line drops the gene symbol | red: `test_a_picked_window_with_no_papers_in_it_says_so` |
| M12 the line ignores the flag | green, 57 passed. J-105-03 |
| M13 Plan never sets the flag | red: `test_a_picked_window_leaves_the_graph_s_undated_papers_out` |
| M14 Plan sets the flag with no window | red: `test_an_unpicked_window_keeps_the_graph_s_papers` |

## Findings

### J-105-01, minor: the empty window line is missing where the answer refuses or no PubMed search ran

- Evidence: probe S1 on the branch prints `trust_outcome: refuse` and the single token "I could not find grounded evidence for this. Try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=NCBIGene%3A672"; the line rides `write_node`'s notes tuple (`:15202`), which the refusal does not emit. For a gene typed as a CURIE no `pubmed_search` is planned, so `:10018` returns None and the answer is the gene record alone, while the plan narrative (develop's, unchanged) still says "PubMed papers published in the last 5 years only".
- What the person sees: on these two rare paths they are not told that no paper from their window was found, and the refusal points at a cross-database link rather than at a longer window or the same question without one.
- Reach: S1 needs the gene's own live record and every other source to come back empty at once; the CURIE case needs a gene typed as `NCBIGene:<n>`. A plain "recent papers on BRCA1" takes S2, where the line shows.
- Worse than develop: no. Develop shows only off-window graph papers there, the loss the owner accepted, and develop has no such line on any path. It is a gap against the lead's widening, not a regression. The refusal text is develop's own.

### J-105-02, minor (instrument): no test holds the "never on a failed search" property

- Evidence: mutation M9 removes `output.status == "error"` from `:10022`; all 57 tests in the two files stay green, and probe S5 then prints "No PubMed papers from the last 5 years were found for BRCA1" directly above "The background search of PubMed did not finish, so this answer may be missing sources from it." The docstring (`:10003` to `:10009`) claims the property; no test asserts it.
- Worse than develop: no, the code is right today. A later edit could make the line claim "none found" over a search that failed, with nothing going red.

### J-105-03, minor (instrument): no test holds the line's flag guard

- Evidence: mutation M12 removes the flag check at `:10011` to `:10012`; 57 passed. Without it, a topic question ("recent papers on coffee and exercise", no graph call) whose picked window finds nothing would carry "Papers in the knowledge graph carry no publication date, so they are not listed here" when no graph paper existed to leave out.
- Worse than develop: no, the code is right today.

## Verdict

Nothing on this branch shows any person something worse than develop. Every record it removes is a graph Article row on a picked window, which the owner's decision accepts; no question without a pick takes a changed line of code; no call is added. The three findings are minor: one gap against the lead's widening on two rare paths, and two untested guards on the new line.

VERDICT: PASS
