# Card 146 build: a retracted paper carries a "Retracted" tag beside its title

The card, in the person's words: "A retracted paper is listed by its full title with no mark that it was retracted (the Wakefield paper, PMID 9500320)." Source: card 134's adversary, A-134-02.

The owner's decision (DECISIONS.md, 2026-10-25): "Card 146: a retracted paper keeps its row with a "Retracted" tag beside its title, read from PubMed's own publication type, and the writer is told not to state its findings as fact."

## Table of contents

- [Diagnosis](#diagnosis)
- [What PubMed returns for PMID 9500320](#what-pubmed-returns-for-pmid-9500320)
- [Every path a paper row takes to the screen](#every-path-a-paper-row-takes-to-the-screen)
- [Where the writer and the sentence check get their records](#where-the-writer-and-the-sentence-check-get-their-records)
- [Plan](#plan)
- [Build](#build)
- [Tests and results](#tests-and-results)
- [Paths left without the tag](#paths-left-without-the-tag)

## Diagnosis

Written before any code changed.

- `grep -rni retract src frontend/src` finds one comment (`synthesis/grounding.py`). Nothing reads a retraction today.
- `tools/ncbi_eutils_actions.py`, ESummary (`summary`): `_SUMMARY_FIELDS_BY_DB["pubmed"]` already keeps `pubtype`, so a PubMed ESummary record carries the publication types. No paper row on screen is built from a PubMed ESummary record today: the paper rows come from EFetch.
- `tools/ncbi_eutils_actions.py`, EFetch (`fetch`, `_extract_pubmed_articles`): reads `PMID`, `ArticleTitle` and `AbstractText` only. `PublicationTypeList` is in the body and is dropped.
- The knowledge graph's `Article` vertex carries no publication type (`tools/graph_schema_constants.py` lists `Article` with its PMID only; no template reads one).
- PubTator3's export carries no publication type (A-134-02 measured this).

## What PubMed returns for PMID 9500320

Read live on 2026-10-30, one ESummary and one EFetch.

| Call | What it says |
|---|---|
| ESummary `db=pubmed&id=9500320,20137807` | 9500320 `pubtype`: `['Journal Article', "Research Support, Non-U.S. Gov't", 'Retracted Publication']`. 20137807 (the notice): `['Retraction Notice']` |
| EFetch `db=pubmed&id=9500320&rettype=abstract&retmode=xml` | `<PublicationTypeList>` holds `<PublicationType UI="D016441">Retracted Publication</PublicationType>`; `CommentsCorrections RefType="RetractionIn"` points at 15016483 and 20137807 |

So both calls the tool already makes carry PubMed's own mark. The notice itself is a "Retraction Notice", not a "Retracted Publication", so it is not tagged: it is not a retracted paper.

## Every path a paper row takes to the screen

| Path | Where it is built | Publication type available? |
|---|---|---|
| Live PubMed paper (title row and abstract row) | `breadth_plan.plan_literature_follow_up` plans an EFetch (`pubmed_abstracts`); `core/graph.py` `_ncbi_efetch_output_to_structured_fields` and `_pubmed_abstract_rows` shape the rows | Yes, in the same EFetch body |
| PubTator3 publication row (card 134 title) | `core/graph.py` `_layer_tool_output_to_structured_fields("pubtator_annotate")` | Not in PubTator3's response. The same PMIDs are fetched by the paired PubMed EFetch (`plan_literature_follow_up` plans both on one id list), so the type is known when that fetch returned. When it did not, the title lookup below can read it |
| Knowledge graph `Article` paper | the graph row, title quarantined; `synthesis/article_titles.py` reads the title over EFetch (card 38 slice C) | Not in the graph. Yes in the EFetch the title lookup already makes |
| Graph paper on a page that already has a live PubMed title row | left on its PMID by `apply_resolved_article_titles`, folded into one row with the live row | Yes, through the live row on the same page |

Then each finding becomes a listing row in `core/graph.py` `_answer_parts`:

- `record_label` / `plain_record_label` (`synthesis/answer_layout.py`) give the row's first cell, the title.
- `sentence_token` writes a `list_item` or `table_row` token: `cells` hold the title, `text` holds the grounded sentence ("Pubmed title: ... [2].").
- Live web answer: `frontend/src/components/screens/AnswerScreen.tsx` shows `cells[0]`.
- Reopened saved answer: `feedback/capture.py` `answer_markdown_from` writes the markdown from `cells`; `savedAnswerMarkdown.tsx` renders it.
- MCP, GraphQL and the command line: each joins token `text` (`contracts/token_order.joined_text`, `adapters/cli/render.py`).
- Sources (citation cards) name a paper as "pubmed 9500320", never by title, so they are not a title surface.

The event schema already carries what is needed: the tag rides in the existing `cells` and `text` of the row's token. No new event field.

## Where the writer and the sentence check get their records

- The writer: `synthesis/findings.py` `build_synth_messages` renders the prompt slice of `synth_findings` through `render_findings_block`; per-query directives (card 38's ARTICLE TITLES line is the model) sit in the user message, so the cached system block never changes.
- The per-sentence check (`synthesis/sentence_check.py`) is asked only whether a reworded sentence says more than its quoted record words. It is not the place to judge retraction, and the owner's decision names the writer, so it is not changed.

## Plan

1. EFetch reads `PublicationType`; a record PubMed types "Retracted Publication" gets `fields["retracted"] = True`. A normal record's fields are unchanged.
2. The row carries `retracted: True` beside `fields` (never inside it), for the title and abstract rows; `build_synth_findings` copies it to a new `SynthFinding.retracted` (not on the wire schema).
3. Write marks every finding on a retracted paper's page, from the live rows and from the title lookup's EFetch. A PubTator3 paper whose PubMed record this question did not read joins the title lookup (same two requests at most, same cache, same call ceiling, same Act prefetch).
4. The listing's row for a marked finding shows "(Retracted)" after the title in its first cell, and its text opens "Retracted: ", so every surface carries it.
5. The writer's message gets one line, only when a marked finding is in its prompt, naming the markers and saying a record marked retracted is never stated as fact.

## Build

What the person sees now: a paper PubMed marks retracted keeps its row, and the row reads "<title> (Retracted)". On the command line, MCP and GraphQL the row reads "Retracted: Pubmed title: <title> [n]." The writer is told, by marker, never to state a retracted paper's findings as fact. Every other paper reads exactly as before.

| File | Change |
|---|---|
| `src/system_03_search_agent/tools/ncbi_eutils_actions.py` | `_extract_pubmed_articles` reads `PublicationType`; a record typed "Retracted Publication" gets `fields["retracted"] = True`, no other record gets the key. New `record_is_retracted(fields)` reads that flag or ESummary's `pubtype` |
| `src/system_03_search_agent/core/graph.py` | `_ncbi_efetch_output_to_structured_fields` puts `retracted: True` beside the row's fields (title row and, in `_pubmed_abstract_rows`, abstract row) and keeps it out of a generic row's fields. `_pubmed_pages_read` and `_paper_lookup_curies` add PubTator3 papers whose PubMed record was not read to the card 38 title lookup, in Write and in the Act prefetch. Write calls `mark_retracted_papers`. `_answer_parts` tags a listing row whose own markers cite a retracted finding, after rows are merged |
| `src/system_03_search_agent/synthesis/findings.py` | `SynthFinding.retracted` (not on the wire schema); `build_synth_findings` copies the row flag; `build_retracted_directive` gives the writer one line, only when a flagged finding is in the prompt |
| `src/system_03_search_agent/synthesis/article_titles.py` | the lookup remembers which records PubMed types retracted (same request, same cache lifetime); `publication_curies_to_check`, `retracted_article_curies`, `mark_retracted_papers` |
| `src/system_03_search_agent/synthesis/answer_layout.py` | `retracted_row_label` and `retracted_row_text`, the tag's two forms |
| `tests/system_03_search_agent/core/test_retracted_papers.py` | new, 15 tests |

No event schema change: the tag rides in the row token's existing `cells` and `text`. No frontend change: the live answer shows `cells[0]`, and the saved answer's markdown is written from `cells`.

The writer's line, as sent when a retracted record is in the prompt:

> RETRACTED PAPERS: [2], [3], [5] come from papers PubMed marks as retracted. Never state what a retracted paper found or reported as fact.

It names markers from each finding's flag, never a paper, title or question.

## Tests and results

Live check, 2026-10-30, the tool's own `fetch` on 9500320, 20137807 and 28340353: 9500320 carries `retracted: True`; the notice and the CFTR paper carry no such key.

| Check | Result |
|---|---|
| `test_retracted_papers.py` | 15 passed |
| core, synthesis, feedback, adapters, contracts suites | 4407 passed, 66 skipped, 1 xfailed |
| tools suite plus title and prompt tests | 2267 passed, 99 skipped (before the cache-shape fix two `test_article_titles.py` cache tests failed; fixed by keeping `_cache`'s shape and storing retraction beside it) |
| A sound paper against develop 4eda8ca5 (`git archive` copy) | the two sound-paper tests pass on develop unchanged; a full write-node probe (tokens, citations, prompts, both depths) is byte-identical to develop |
| `npx vitest run src/components/screens src/hooks` | 32 files, 331 tests passed |
| `npx tsc --noEmit -p .` | clean |
| `ruff check .` | clean |
| gate02 isort command | clean |

Mutations, each restored after:

| Mutation | Result |
|---|---|
| EFetch reads no publication type | red, 10 tests |
| Title row carries no flag | red, 5 |
| Abstract row carries no flag | red, 1 |
| Finding drops the flag | red, 1 |
| Writer not told | red, 7 |
| Listing row not tagged | red, 7 |
| Row text not tagged | red, 7 |
| PubTator3 papers not looked up | red, 3 |
| Lookup forgets the retraction | red, 4 |
| Nothing marked in Write | red, 4 |
| A "Retraction Notice" taken for retracted | red, 1 |
| A PMID PubMed did not return taken for retracted | red, 1 (the first run survived; a test was added) |
| Writer's line sent for every answer | red, 4 |

## Paths left without the tag

- A paper whose PubMed record could not be read: the lookup failed, timed out, hit the 20-call ceiling or the two-request bound, or PubMed returned no record. Its status is unknown and it is shown as today, with no tag. Unknown is never taken for retracted.
- The knowledge graph has no publication type. A graph paper is tagged only through the title lookup's EFetch; a graph paper beyond the lookup's 100 PMIDs stays on its PMID with no tag, as before.
- Sources (citation cards) name a paper as "pubmed 9500320", never by title, so they carry no tag.
- The writer is told; nothing in code strips a sentence that states a retracted paper's finding. The owner's decision names the instruction, and the per-sentence check judges only rewording.
- One new request: a PubTator3 paper whose PubMed record the question did not read (the background PubMed fetch did not finish) now joins the title lookup, at most the same two requests, under the same call ceiling. When the PubMed fetch returned, no request is added.
- The tag is text, not a styled pill. A styled pill would need the web to parse the cell's text or a new event field (dial position 3, the owner's).
