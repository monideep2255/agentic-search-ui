# Cards 119 and 124 diagnosis: the papers a picked "How far back" window lists

Read-only diagnosis against develop `a997892e` (the docs branch `chore/overnight-2026-10-29` equals develop for every source file) on 2026-10-29. Code paths are under `src/system_03_search_agent/` unless written in full. No live model or API call was made: the evidence is the code, the captures in `testing/Developer/reports/2026-10-17_product_check_card105/run1/`, card 105's diagnosis and two small local runs of pure functions. The three test files on this path pass on the branch (154 passed).

## Table of contents

- [Summary](#summary)
- [The owner's decisions that bind these cards](#the-owners-decisions-that-bind-these-cards)
- [How a picked window reaches the papers](#how-a-picked-window-reaches-the-papers)
- [Card 119: at most 5 papers](#card-119-at-most-5-papers)
- [Card 124: the GeneReviews chapter under the window](#card-124-the-genereviews-chapter-under-the-window)
- [Overlap and order](#overlap-and-order)
- [What was checked and what was not](#what-was-checked-and-what-was-not)

## Summary

| Card | Cause | Recommended fix | Size | Owner first | Build tonight |
|---|---|---|---|---|---|
| 119 | One constant, `PUBMED_RESULT_CAP = 5`, is applied four times on the paper path: the PubMed search's `retmax`, the follow-up's id selection, the abstract rows' cut and the PubTator3 rows' cut. A picked window narrows the search but never widens the cap | On a picked window, list up to 10 papers from the window, each with its title; the writer still reads five abstracts, as today, so the prompt and the answer time barely move | About 30 to 45 source lines in `core/breadth_plan.py` and `core/graph.py`, one area (the windowed paper path) | No. The owner already decided to raise it (2026-10-16); the number is the team's call from the person's chair | Yes, if tonight's approval covers five live runs of the windowed BRCA1 question for the speed and no-loss gate |
| 124 | Not a window leak. PubMed 20301425 is the GeneReviews chapter on BRCA1 and BRCA2, a book record. The windowed PubMed search itself returned it (PubMed dates its current version 2026/03/25; "1993" is the GeneReviews series' start year). The abstract fetch's parser skips every PubMed book record, so only PubTator3 lists it, as an enrichment row with no date | The owner picks one of three: keep the chapter and say what it is and when it was last updated (recommended), leave book records out of a windowed search, or close the card | Keep: M, about 60 to 90 lines over three files. Leave out: S. Close: none | Yes: the card's premise ("from 1993") does not hold, and what a window means for a living review serves clinicians and researchers differently | No, the owner's call comes first |

## The owner's decisions that bind these cards

Quoted word for word from `DECISIONS.md`.

| Date | Words | What it settles here |
|---|---|---|
| 2026-09-25 | "A publication-date limit applies only from the window the reader picks in the "How far back should I search?" ask-back, never from the question's wording" | Both fixes act only after a click on a stored offer; typed words never change the cap or the filter |
| 2026-10-16 | "Card 105: when a "How far back" window is picked, the knowledge graph's Article rows are left out of the answer and the PubMed papers inside the window lead it; a question with no window runs unchanged code. The windowed answer keeps its cap of 5 PubMed papers tonight, and raising it for windowed questions becomes a card of its own. Decided by the product owner before sleeping" | Card 119 raises the cap for windowed questions only; an unwindowed question must run unchanged code. The owner's answers recorded in the same row: "Leave them out" and "Keep 5, new card" |
| 2026-10-17 | "Card 105's product check found a 1993 paper from the enrichment layer listed under a picked window; the owner's decision covered graph papers only and develop lists it too, so it is card 124." | The card 105 decision does not settle card 124. Read literally ("the PubMed papers inside the window lead it"), it would keep the chapter, since PubMed places it inside the window; but the card was filed on the belief that it is a 1993 paper, so the owner should decide with the corrected fact |

Card 30's row in `testing/UI_fix_plan.md` adds a constraint on both: the text-only answer of MCP and GraphQL is cut at 8000 characters, and card 30's step 2b was closed because added row text pushed answers past it.

## How a picked window reaches the papers

| Link | What happens | Where |
|---|---|---|
| 1. The pick | A click on a stored "How far back" offer becomes a `PublicationWindow` | `core/graph.py:4016` (`_picked_publication_window`), `core/breadth_plan.py:556` |
| 2. The search | The window is ANDed onto the PubMed term only, `retmax` 5, `sort=relevance`. Local run for BRCA1 on 2026-10-17: `BRCA1[Title/Abstract] AND ("2021/10/17"[dp] : "3000"[dp])` | `core/breadth_plan.py:516` (`clause`), `:752` (gene and disease path), `:702` (topic path) |
| 3. The graph | On the gene path the graph's Article rows are removed (card 105, flag `undated_papers_left_out`), because an Article vertex has no date | `core/graph.py:12953` and the Act branch card 105 added |
| 4. The follow-ups | The search's PMIDs feed two follow-ups on the same capped id list: the abstract fetch (Layer 2) and the PubTator3 `annotate_publications` call (Layer 3) | `core/graph.py:5349` (`_BREADTH_FOLLOW_UPS`), `:8791`; `core/breadth_plan.py:846` (`plan_literature_follow_up`) |
| 5. The rows | Abstract fetch: one title row per `PubmedArticle`, sorted by URL, cut to 5, then one abstract row per title. PubTator3: one "Publication" row per annotated PMID, sorted by URL, cut to 5 | `core/graph.py:8307` to `:8312`; `:5084` to `:5107` |
| 6. The writer | The windowed abstract call answers the question (card 105), so its rows take the first 10 lead slots; the model reads the first 30 admitted findings in an 18,000-character block | `core/graph.py:12956`, `:5409`, `:8924`, `:14299`, `:14449`; `synthesis/findings.py:158`, `:679` |

The window applies at link 2 and nowhere else. Every paper that links 4 to 6 list is one of link 2's PMIDs, so on the windowed path no paper reaches the answer without passing PubMed's own date filter. LitVar2 lists variants, not papers (`core/graph.py:5135`), and PubTator3's `entity_lookup` lists entities, not papers.

## Card 119: at most 5 papers

### Where the cap of 5 is set, and why

`core/breadth_plan.py:117` to `:121`: "Five papers is the audit's measured sweet spot (0.22 s for five abstracts, 1,000 to 1,300 characters each)". It was sized for a breadth fan-out beside a graph answer, before a window existed. The same five are enforced in four places, so raising one alone changes nothing the person sees.

| Place | What it caps | Where |
|---|---|---|
| Search `retmax` | PMIDs PubMed returns | `core/breadth_plan.py:753`; topic path `:601`, `:703` |
| Follow-up selection | PMIDs fetched and annotated (`select_ids(pmids, PUBMED_RESULT_CAP)`) | `core/breadth_plan.py:846`. Local run: 10 ids in, 5 out |
| Abstract title rows | Papers listed from Layer 2 (`_BREADTH_ROW_CAP`, equal to `_LAYER_TOOL_ROW_CAP`, 5) | `core/graph.py:8311`, `:5399`, `:4924` |
| PubTator3 rows | Enrichment rows, entities and publications together | `core/graph.py:5107` |

Two more limits decide what the writer reads, not what is listed:

- The lead quota of 10 (`core/graph.py:5409`). Today 5 title rows and 5 abstract rows fill it exactly.
- The findings block of 18,000 characters, sized for 5 abstracts at the 2,000-character field cap (`synthesis/findings.py:92`, `:158`; pinned by `test_a_thirty_finding_prompt_with_long_abstracts_reaches_the_model_whole` in `tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py:433`).

### What the person sees today

"I picked the last five years and got four papers. Without a window I get dozens." The windowed BRCA1 answer of 2026-10-17 opens "I found 4 published papers related to BRCA1." (`run1/brca1_5y_1280.txt`); the fifth PMID was the GeneReviews chapter (card 124).

### A trap a naive raise falls into

Raising the four caps to 10 and nothing else makes the answer worse. Ten title rows fill the lead quota of 10, so the ten abstract rows move to the back of the queue (`_allot_with_lead_quota`, `synthesis/findings.py:679`), behind about 25 context rows (Gene, ClinVar, OMIM, trials, PubTator3). The model's slice of 30 would then hold ten titles and no abstract, and the summary would lose the "From the paper ..." sentences it writes today.

### Recommended fix: ten listed, five read

What the person sees after it: "When I pick a window I get up to ten papers from that window, each with its title, and the summary still draws on several of them."

| Part | Change | Where |
|---|---|---|
| 1 | A constant, for example `PUBMED_WINDOW_RESULT_CAP = 10`, used as `retmax` only when `window is not None`, on the gene and disease path and the topic path | `core/breadth_plan.py`, `plan_first_stage` and `plan_topic_search` |
| 2 | `plan_literature_follow_up(pmids, cap=PUBMED_RESULT_CAP)`, called with the source search's own `retmax`, carried on `_PlannedFollowUpCall` as a new field with default 5 | `core/breadth_plan.py:846`; `core/graph.py:4858`, `:5532` onward, `:8791` |
| 3 | The `pubmed_abstracts` title-row cut uses the same carried cap instead of `_BREADTH_ROW_CAP` | `core/graph.py:8311` |
| 4 | On a windowed question the lead quota is 15, ten titles and five abstracts, through one helper called at both `lead_quota=` sites | `core/graph.py:8924`, `:14299` |
| 5 | PubTator3's row cut stays at 5. The papers are listed from the abstract call; PubTator3 adds annotations, and its Publication rows fold into the same PubMed URLs | `core/graph.py:5107`, unchanged |

Why an unwindowed question runs unchanged code: every new value is set only when `_picked_publication_window` returned a window; without one the search plans `retmax` 5, the follow-up carries 5 and the quota stays 10.

Costs, measured or bounded from the code:

| Cost | Ten listed, five read (recommended) | Ten listed, ten read | Twenty listed |
|---|---|---|---|
| Live calls | Same count. One abstract fetch of 10 ids instead of 5 (the audit measured 0.22 s for five) and one PubTator3 call on 10 PMIDs, both in parallel with the other follow-ups | Same | Same count, larger bodies |
| Writer prompt | About five more title findings, roughly 500 to 1,500 characters, under 400 tokens | About five more abstracts, up to 10,000 more characters (about 2,500 tokens); the 18,000-character block then cuts ClinVar, OMIM and trials out of the model's text unless it is raised | Over the 30-finding slice; not workable without raising both caps |
| Answer time | Little change expected: the writer reads the same five abstracts | Longer writer input and likely longer output, a few seconds | Not estimated |
| MCP and GraphQL 8000-character cut | Five more listed rows, about 1,000 characters at worst (PubMed titles run to about 300 characters); the windowed BRCA1 prose today is about 1,100 characters | Also more prose | Up to 3,000 more characters of rows alone |
| The 20 s budget | The windowed BRCA1 answer already took 28.2 s once and 12.9 s once on develop (PR-card105-02); the fix must not move the median or the worst of five runs | At risk | At risk |

One side effect to state: the abstract rows are ordered by URL text (`core/graph.py:8310`), so the five abstracts the writer reads are the five lowest-sorting PMIDs of the ten, roughly the older half of the window. The builder may order windowed title rows newest first; that is a choice inside the same lines, not a new area.

Tests the builder adds (each fails on develop):

- `core/breadth_plan`: a windowed `plan_first_stage` and `plan_topic_search` plan `retmax` 10; an unwindowed one plans 5; the follow-up with 10 ids and cap 10 keeps 10, with the default keeps 5.
- `tests/system_03_search_agent/core/test_bare_topic_clarification.py`, beside `test_a_picked_window_leaves_the_graph_s_undated_papers_out` (`:902`): a stubbed windowed search returning 10 PMIDs cites all 10 papers, puts five abstracts inside the model's 30-finding slice, and its joined text stays under 8000 characters with 300-character titles; the unpicked control plans `retmax` 5 and cites as develop does.
- Mutations: drop the window check in part 1 (the control fails); leave the quota at 10 (the abstract-in-slice assertion fails).

Owner decision: none required. The owner decided on 2026-10-16 to raise the cap for windowed questions on its own card, and the number is the team's to choose from the person's chair. If the lead wants the number confirmed, the question is: "Card 119: after picking a "How far back" window, how many papers should the answer list? 10 (recommended): a page of papers with titles, the summary still reads five, answer time about the same. 20: a longer reading list, but the summary can read only some of them and long answers risk the 8000-character cut on MCP and GraphQL. Keep 5: no change."

## Card 124: the GeneReviews chapter under the window

### Which layer lists PMID 20301425, and why the window does not drop it

| Step | Finding | Evidence |
|---|---|---|
| 1. The record | PubMed 20301425 is the GeneReviews chapter "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer", a PubMed book record, not a journal paper | Product check PR-card105-01 |
| 2. Its dates | Two dates on one record. ESummary `pubdate` reads 1993, the year the GeneReviews series began; ESummary `sortpubdate` reads 2026/03/25, its current revision | Product check (1993); card 105's diagnosis, one ESummary call of 2026-10-16 (2026/03/25) |
| 3. How it entered | The only code that makes a PubTator3 "Publication" row is `annotate_publications`, and its only caller is the follow-up of the windowed PubMed search. So the windowed search returned 20301425: PubMed's own `[dp]` filter placed it inside "the last 5 years" | `core/breadth_plan.py:870`; `core/graph.py:5084`, `:8791`; a search of `src/` for `annotate_publications` finds no other caller |
| 4. Why only the enrichment layer lists it | The abstract fetch's parser reads `PubmedArticle` elements only. A book record arrives as `PubmedBookArticle` and is skipped, so Layer 2 has no title, no abstract and no row for it, and the count line says "4 published papers" though the search found 5. PubTator3 annotates it, so it is listed as "L3 · literature", `literature_mention`, field `pmid` | `tools/ncbi_eutils_actions.py:1232` to `:1243`. Local run: a set with one `PubmedArticle` and one `PubmedBookArticle` returns only the first PMID |
| 5. Why it showed "Published paper" | PubTator3's row had no title on 2026-10-17. Card 134 (#299, live since) reads the title from the same response, so develop now lists it by its title | `core/graph.py:5091` to `:5101`; `testing/Retest_product_owner.md` row 2 |

So the window was applied, and PubMed says the chapter is inside it. Nothing about it is undated: the enrichment layer never lists a paper the windowed search did not return. The graph exemption (card 105) is not involved; no graph paper is listed on this answer.

### What the person sees

Today on develop: under "the last 5 years", a row titled "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer", with no date and no sign that it is a book chapter. In the person's words: "I asked for the last five years; one of these is a GeneReviews chapter, and its PubMed page shows dates from the 1990s, so did my window work?" A clinician would usually want this chapter: it is the field's maintained clinical summary for the gene. A researcher scanning new primary work may not.

### Options, from the person's chair

| Option | What the person sees | Cost | Could make worse |
|---|---|---|---|
| (a) Keep it and say what it is (recommended) | The chapter is listed as a book chapter with its last update, for example "GeneReviews chapter, last updated March 2026", it is counted with the papers and its summary is read like theirs | M, about 60 to 90 lines: `tools/ncbi_eutils_actions.py` reads `PubmedBookArticle` (PMID, title, abstract, revision date; element names confirmed with one live EFetch before building); `core/graph.py` lets the date field through for `pubmed_abstracts`; `synthesis/answer_layout.py` labels the row | Every paper answer, windowed or not, can now list such chapters in full instead of as an enrichment row; a book-record parser is new code on untrusted text and needs its own adversary probes |
| (b) Leave book records out when a window is picked | Only journal papers from the window are listed | S: one more clause on the windowed PubMed term in `core/breadth_plan.py`, its exact form confirmed with one live search | The person loses the chapter on exactly the "recent" questions, and with it often the best clinical summary of the gene |
| (c) Close the card as not a defect | As today: the chapter, titled since card 134, undated | None | A reader who opens it sees older dates and may think the window was ignored |

Recommendation: (a). It is honest about what the record is and when it was last revised, and it keeps a source most clinicians would want; the defect the person feels is that nothing says what the row is or how recent it is, not that the row is there. It also fixes the count line ("4 published papers" when 5 were found). It is not tonight's work: it touches three files and every paper answer, so it needs the owner's choice, then a judge and an adversary.

### The owner question

Card 124: the "BRCA1, the last 5 years" answer lists PubMed 20301425. It is not a 1993 paper: it is the GeneReviews chapter on BRCA1 and BRCA2, a living review whose current version PubMed dates 25 March 2026, and PubMed's own window search returned it ("1993" is the year the GeneReviews series began). What should a picked window do with a chapter like this?

- Keep it and say what it is (recommended): the row reads as a GeneReviews chapter with its last update date, and it is counted and summarised like the papers. Cost: a medium change, about three files; every paper answer can then list such chapters in full, not only under a window.
- Leave book chapters out when a window is picked: only journal papers from the window are listed. Cost: a small change; the person loses GeneReviews, often the best clinical summary of a gene, on exactly the "recent" questions.
- Close the card: since card 134 the row already shows the chapter's title. Cost: none; a reader who opens it sees older dates and may think the window was ignored.

## Overlap and order

| File | Card 119 | Card 124 (a) | Card 124 (b) |
|---|---|---|---|
| `core/breadth_plan.py` | `plan_first_stage`, `plan_topic_search`, `plan_literature_follow_up`, a new constant | No | `plan_first_stage`, `plan_topic_search`: the same functions |
| `core/graph.py` | `_PlannedFollowUpCall`, the follow-up planning loop, `_follow_up_planned_call`, the `pubmed_abstracts` row cut, the lead quota sites | `_BREADTH_FIELDS_BY_PURPOSE` for `pubmed_abstracts`, near the same row cut | No |
| `tools/ncbi_eutils_actions.py` | No | `_extract_pubmed_articles` | No |
| `synthesis/answer_layout.py` | No | The row label | No |

Both options for card 124 share a file with card 119, and (b) shares functions. Build card 119 first, then card 124 on top of it once the owner has chosen. Card 105's code (`undated_papers_left_out`, `_answer_call_ids`) is read by card 119's lead-quota helper and edited by neither card.

## What was checked and what was not

- Checked in code: every place the cap of 5 applies on the paper path; that the only caller of `annotate_publications` is the windowed search's follow-up; that the EFetch parser skips book records (local run on a two-record XML set); the windowed term built for BRCA1 on 2026-10-17 (local run).
- Checked in evidence: `run1/brca1_5y_1280.txt` and `.json` (five PubMed links, row 10 "pubmed 20301425 L3 · literature", "literature_mention", "I found 4 published papers").
- Not checked live: that the run's own ESearch returned 20301425 (the capture kept no tool trace), and the chapter's two dates (taken from the product check and card 105's diagnosis). One free ESearch, the windowed term above with `AND 20301425[pmid]`, would confirm it if the lead allows a call.
- Not measured: the windowed BRCA1 answer's full joined text length on MCP and GraphQL, and the answer time after card 119's fix. Both belong to the builder's gate.
