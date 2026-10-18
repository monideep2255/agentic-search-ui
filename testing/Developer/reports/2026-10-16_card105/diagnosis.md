# Card 105 diagnosis: a picked window limits only the PubMed search

Card 105, from card 36's product check (PR-36-01, `testing/Developer/reports/2026-10-09_product_check_37_36/product_review.md`). Diagnosed read-only against develop `78c68c1c` on 2026-10-16. Code paths are under `src/system_03_search_agent/` unless written in full.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause, link by link](#the-cause-link-by-link)
- [The options, from the user's chair](#the-options-from-the-users-chair)
- [The smallest fix](#the-smallest-fix)
- [Tests](#tests)
- [Overlap with tonight's other cards](#overlap-with-tonights-other-cards)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

Still happens on develop `78c68c1c`.

| Check | Result |
|---|---|
| Code changed since the product check of 2026-10-09 | No commit since then touches `core/breadth_plan.py`, `core/clarify.py` or `tools/cypher_templates.py`, and none adds or removes `publication_window` (`git log --since=2026-10-09`) |
| Phase 8.7 | Rewrote parts of `write_node` and `_answer_tokens`, not the window path; every line below was re-found by name |
| Was it true before card 36 | Yes. Card 36 only added the "could not be applied" note for a lost offer (`testing/Developer/reports/2026-10-08_card36/build.md`); the window's reach was set in build phase 8.2, card 4 |
| The years of the papers shown | One free ESummary call: PMID 10026184 is 1999 Feb, 10417300 is 1999 Aug, 10972993 is 2000 Aug |

## What a person sees

A researcher asks "recent papers on BRCA1", is offered "How far back should I search?", and clicks "from the last 5 years".

- The heading reads "Recent papers on BRCA1 from the last 5 years?".
- The answer opens "Found 41 article records for BRCA1, of 3487 available."
- The first table, "Article records found", lists PMID:10026184 to PMID:10417300 on page 1 of 5, numbers only, no titles. They are papers from 1999 and 2000.
- Only further down, under "PubMed records found", sit four titled papers from 2022 to 2024.
- A note says the answer was truncated because only 140 of the 3487 matching records were retrieved.
- In the researcher's words: "I picked the last five years and the first 41 papers it shows me are from the 1990s, listed as bare numbers with no titles."

## The cause, link by link

| Link | What happens | Evidence |
|---|---|---|
| 1. The pick travels to Plan | The clicked option text is the next question. `_picked_publication_window` looks it up among this session's stored offers and turns its months into a `PublicationWindow` | `core/graph.py:3956` (`_picked_publication_window`), `core/breadth_plan.py:556` (`recent_publication_window`) |
| 2. The window reaches only PubMed ESearch | `PublicationWindow.clause()` builds `("YYYY/MM/DD"[dp] : "3000"[dp])` and `plan_first_stage` ANDs it onto the PubMed term and nothing else; its docstring says ClinVar, OMIM and GEO keep no publication date. The topic path does the same | `core/breadth_plan.py:516`, `:752`, `:702`; `core/graph.py:6893` and `:7283` |
| 3. The gene path still plans the question's own graph call, unlimited | "Recent papers on BRCA1 ..." resolves BRCA1, so the gene path keeps the graph call at index 0 (`planned_tool_calls = [planned]`). `cypher_query` picks the `gene_articles_one` template from the word "papers" | `core/graph.py:7203`; `tools/cypher_templates.py:217` (the `articles` keyword), `:268` (`("Gene", "articles")` hop over `mentioned_in`) |
| 4. The graph returns the oldest-numbered papers | The hop template ends `RETURN x ORDER BY x.id`. `id` is the string `PMID:<n>`, so the first rows are the PMIDs whose text sorts first, here 1999 and 2000 | `tools/cypher_templates.py:614` (`_hop_template`) |
| 5. The graph cannot be limited by date | An Article vertex carries no publication date. The System 1 parser writes `id`, `name` (the title), `source`, `source_url` and, when present, `description` (the abstract). No System 1 or System 2 file reads a publication date | `reference/agentic-search-data-engineering/system-01-data-pipelines/pubmed/parse_pubmed_xml.py:101` to `:126`; a search for `pubdate`, `pub_year` and `publication_date` over both systems finds nothing |
| 6. The graph rows are the answer and lead the page | `_answer_call_ids` counts every non-context graph call as answering the question; the windowed PubMed papers are context. So the 40-odd graph papers take the first `_LEAD_FINDINGS_QUOTA` (10) slots, the count line counts them, and the truncation note quotes the graph's 3487 | `core/graph.py:12667` (`_answer_call_ids`), `:5327`, `:13884`, `:14041`, `:14068`; `synthesis/answer_layout.py:1780` ("of N available") |
| 7. They show as bare ids | An Article row's `fields` are emptied as untrusted third-party text, so the row is cited by its id alone | `core/graph.py:7539` (`_UNTRUSTED_FREE_TEXT_NODE_TYPES`), `:7584` (`_sanitized_citeable_row`), applied at `:8569` to `:8576` |
| 8. The heading "repeats the window" | The heading is the person's own question, the option they clicked, rendered as is. It is not code claiming the window; it is right once the list beneath it honours it | `frontend/src/components/screens/AnswerScreen.tsx:2934` |

Two side observations, not this card's cause:

- PMID:20301425 under "Publication records found" is a GeneReviews book chapter whose PubMed date is its 2026 revision (ESummary `sortpubdate` 2026/03/25), so it plausibly belongs to the window. It sits under its own heading because only the PubTator3 follow-up cited it. Not verified against the run's own ESearch.
- The five clinical trials are from 2007 to 2008. Trials are not papers and the plan line says only "PubMed papers published in the last 5 years only", so nothing claims they were limited.

## The options, from the user's chair

The person picked a window and wants papers from that window, first, with titles.

| Option | What the person sees | Cost | What it could make worse |
|---|---|---|---|
| (a) Limit the graph's papers by year | Only if the graph knew a year. It does not (link 5). Adding one is System 1 and 2 work, out of this repository. Dating the graph's PMIDs live (one ESummary for 40 ids) would remove all 40, since the template returns the oldest-numbered first; to find recent graph papers the template would also have to sort by number, newest first | A live call per question, a template change in `tools/cypher_templates.py` (cards 37 and 38's fence), an unmeasured sort over a gene's whole paper list (3487 for BRCA1, more for TP53). Size L | Speed on every windowed gene question; a guess if a PMID threshold were used instead, which would be a confident wrong record |
| (b1) Leave the graph's papers out of a windowed answer | The windowed PubMed papers lead, with titles; the count line reads "Found 4 PubMed records for BRCA1"; no 1999 paper, no "of 3487" | `core/graph.py` only. Size M. The graph's undated gene-paper links are not shown when a window is picked | A windowed gene question whose PubMed search finds nothing in the window shows no papers at all, where develop shows 41 off-window ones; it must say so plainly (see the fix) |
| (b2) Show the graph's papers under their own heading, after PubMed | "Papers linked to BRCA1 in the knowledge graph (any year)", below the windowed list | Heading and ordering code in `_answer_tokens` (card 18's fence) and the lead ordering. Size M | The writing model is still handed 40 off-window papers and can call them "recent"; the page stays long with bare ids until card 38 lands |
| (c) A sentence under the heading | "Papers from the knowledge graph are not limited to the last 5 years" over the same 41 papers | Copy. Size S | Nothing gets better for the person: the first 41 papers are still from 1999, the count line still counts them, the writer still leads with them |

Recommendation: (b1). It is the only option where what the person picked is what the papers list shows, and it costs no new call. A picked window is a request for recent papers, and the graph cannot tell which of its papers are recent. Honesty beats polish, and a confident wrong record is worse than a missing one.

## The smallest fix

| Part | What changes, in the person's words | File fence | Answer path | Dial | Size | Migration, package, event schema, setting |
|---|---|---|---|---|---|---|
| 1 | "When I pick a window, the papers I am shown are only from that window" | `core/graph.py`: a new field on `_PlannedToolCall` (`:4688`), default False, for example `undated_papers_left_out`; `plan_node` sets it with `dataclasses.replace` on the gene path's own graph call (`:7203`) only when `publication_window is not None`. `_execute_planned_call`'s cypher branch (`:8569` to `:8603`), when the flag is set, removes Article rows from `output.rows` before both the structured pair and the quarantine pair, and recomputes `row_count`, `total_available` and `truncated` from the rows kept | Yes | 2, runnable behaviour | M | None of the four. `GraphState.tool_calls` is `list[Any]`, so no state or event field changes |
| 2 | "The recent papers lead the answer and the count line counts them" | `core/graph.py`, `_answer_call_ids` (`:12667`): when the question's graph call carries the flag, the `pubmed_abstracts` follow-up call of the windowed `pubmed_search` also answers | Yes | 2 | S | None |
| 3 | "If nothing in the window was found, it says so" | Where the gene path closes a follow-up as `empty` (`_PlannedFollowUpCall`, `:4785`), a windowed search with no ids already discloses an empty follow-up; the builder must confirm the answer then says no papers from the window were found, rather than listing only ClinVar and trials in silence | Yes | 2 | S | None |

Why it cannot change any other question:

- The flag is set only when `_picked_publication_window(query)` returns a window, which needs a click on a stored offer this session. Every question without a pick, including the same words typed (card 36's lost-window path), plans the graph call with the flag False and runs byte-identical code.
- Only Article rows are removed. A windowed question whose graph shape is variants, diseases or GO terms has no Article rows, so its graph answer is unchanged.
- The disease path's graph call (`Disease` anchors hop only to genes) and the topic path (no graph call) return no Article rows today.

Ways it could make an answer develop gives today worse, and the test that catches each:

| Risk | Caught by |
|---|---|
| A graph result that was all Article rows becomes empty and the answer refuses silently, the exact failure `_sanitized_citeable_row`'s docstring records (`:7584`) | The end-to-end test below asserts the windowed BRCA1 answer still ships with the PubMed papers cited and a non-refuse trust outcome |
| The flag leaks onto an unwindowed question | The control test: "recent papers on BRCA1" with `think.recent_years` not asking keeps PMID:10026184 in the citations, as develop does |
| `row_count` and `total_available` disagree after the drop (F-2.1-C07) | The Act unit test asserts both equal the kept rows |
| The quarantine reader still receives the dropped titles | The Act unit test asserts no `-articles` quarantine pair when every Article row was removed |
| A windowed question that also asks for variants loses its variant rows | The Act unit test includes a non-Article row and asserts it is kept |

What the person gains besides the right papers: the guard-tier reader pass over 40 quarantined titles no longer runs on a windowed question, and the "truncated, 140 of 3487" note disappears.

## Tests

| Test | File | Fails on develop because | Passes on the fix because |
|---|---|---|---|
| `test_a_picked_window_leaves_the_graph_s_undated_papers_out` | `tests/system_03_search_agent/core/test_bare_topic_clarification.py`, beside `test_a_picked_window_reaches_a_gene_question_s_pubmed_search` (`:726`) | With the cypher stub returning Article rows (PMID:10026184, PMID:10417300) for BRCA1, picking `options[1]` cites PMID:10026184 and the count line opens "Found 2 article records" | No citation or token names PMID:10026184; the count line counts the PubMed records; trust outcome is not refuse |
| `test_an_unpicked_window_keeps_the_graph_s_papers` | Same file | Passes on develop too; it is the byte-identity guard | Same assertion as develop: PMID:10026184 is cited |
| `test_undated_papers_left_out_drops_only_article_rows` | a new `tests/system_03_search_agent/core/test_window_graph_papers.py` | The new field does not exist | One Article and one Gene row in, flag True: only the Gene row in `structured_fields`, `row_count == total_available == 1`, no quarantine pair; flag False: identical to today |

Mutation checks for the builder: remove the flag check in Act (the first test fails); set the flag unconditionally in Plan (the control fails).

## Overlap with tonight's other cards

| Card | Its fence | Overlap with 105 |
|---|---|---|
| 30 | `synthesis/answer_layout.py` note beside `variant_to_disease_source_note`; `core/graph.py` a Think classifier decision and `_write_answer` | None in functions. 105 stays out of `_write_answer`; `_answer_call_ids` is its own function, called from `_write_answer` (`:13884`) but not edited there. Both edit `core/graph.py`, so merge one after the other |
| 37 and 38 | `tools/cypher_templates.py`, `tools/cypher_query.py`, `synthesis/answer_layout.py` labels, `synthesis/findings.py`, new `synthesis/article_titles.py`, `core/graph.py` `_layer_tool_output_to_structured_fields` and `write_node` | No shared function. 105 touches neither `cypher_templates.py` nor the quarantine functions, which 38 keeps byte-identical. The interaction is behavioural, below |
| 18 | `core/graph.py` `_answer_tokens` merge | None. 105 does not touch `_answer_tokens`; option (b2) would, which is one more reason to prefer (b1) tonight |
| 8 | The trust-line wording | None in code. After 105 a windowed answer cites PubMed instead of the graph for papers, so the trust line's source names may differ on that one question, through existing wording |

How 105 and 38 interact on the "bare ids":

- Card 38 step 2 gives graph Article rows their titles from PubMed EFetch in `write_node`. It would turn the 41 bare ids into 41 titled papers from 1999. It does not fix 105: the papers would still be from outside the window.
- 105 removes graph Article rows only on a windowed question. Card 38's resolver then has nothing to resolve there and spends none of its EFetch calls; on every unwindowed question 105 changes nothing and 38 works as designed.
- Either can land first. If 38 lands first, its tests on unwindowed questions stay green under 105. If the owner later wants graph papers dated (option a), 38's EFetch already fetches the PubMed XML, but `_extract_pubmed_articles` reads only the title and abstract today (`tools/ncbi_eutils_actions.py:1256` to `:1267`).

## Needs the owner

Two choices, each the owner's because two kinds of reader weigh them differently.

1. Graph papers on a windowed question. Recommendation first.
   - (b1) Leave them out. Cost: the person sees only the window's papers, about four or five today, and never the graph's undated gene-paper links on that question. Recommended: it is what they picked, and nothing shown is off-window.
   - (b2) Show them below, under "Papers linked to BRCA1 in the knowledge graph (any year)". Cost: a longer page, bare ids until card 38, the writing model still sees off-window papers, and card 18's fence.
   - (c) A sentence only. Cost: nothing improves for the person. Not recommended.
2. How many papers a picked window returns. Recommendation first.
   - Keep five (`PUBMED_RESULT_CAP`, `core/breadth_plan.py:121`) in card 105, and file a separate card to raise the cap for a picked window. Cost: after 105 a windowed answer lists about four or five papers where an unwindowed one lists 40 or more, which can read as fewer results for asking more precisely. Recommended, to keep 105 narrow and measured.
   - Raise it to 20 inside 105. Cost: one larger abstract fetch and PubTator3 call, more prompt slots for papers, a little more time on a question that already took 34.9 s.

## Test query

Query 108 covers the lost offer, and its third line ("the same click still limits to the last 10 years and says so") checks only the plan line, not the list. A new entry is proposed, at the next free number (115 is proposed by card 38's diagnosis, so 116 here). Not edited into the file.

```
### 116. A picked window limits every paper in the answer (card 105)

Queries to try:

- Ask `recent papers on BRCA1`, wait for the three "How far back" choices, then click "from the last 5 years".
- Then ask `recent papers on BRCA1` again and click "from the last 12 months".

What you should see:

- Every paper listed is from the window you picked, each with its title.
- The answer does not open "Found 41 article records" and lists no paper from the 1990s.
- If no paper in the window was found, the answer says so instead of listing older ones.
- Asked without picking a window, the answer is the same as before.
- Why it matters: you chose how recent; a list that ignores your choice is worse than a shorter one that keeps it.
```
