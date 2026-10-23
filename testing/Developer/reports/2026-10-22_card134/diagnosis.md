# Card 134 diagnosis: enrichment papers listed by number twice

What the person saw on deployed develop (`testing/Developer/reports/2026-10-18_browser_retest/report.md`, rows 2 and 3): under "Publication records found", papers read "28340353 PMID:28340353" when the background PubMed search did not finish (query 117, Researcher), and "20301425 PMID:20301425" when the windowed PubMed search did not return that paper (BRCA1, last 5 years). Diagnosed from code and the report, with no model calls; two read-only NCBI calls checked the record shapes.

## Table of contents

- [Cause](#cause)
- [What the run already holds](#what-the-run-already-holds)
- [Options](#options)
- [The fix](#the-fix)
- [Before and after](#before-and-after)
- [Fix round](#fix-round)

## Cause

Line numbers are the branch base, `b902d80a`.

| Step | Where | What happens |
|---|---|---|
| 1 | `tools/pubtator_annotate.py:687-760`, `_parse_publication` | Reads only `id` and each passage's `annotations`. The `title` passage's `text`, the paper's PubMed title, is discarded. |
| 2 | `core/graph.py:5081-5095`, the `pubtator_annotate` branch of `_layer_tool_output_to_structured_fields` | The `Publication` row carries `pmid` and `annotation_count` only. |
| 3 | `synthesis/answer_layout.py:941-982`, `record_label` | No `name` or `title` on the row, so the label falls through to the cited value, the PMID: "28340353". |
| 4 | `synthesis/answer_layout.py:539` and `:558`, `record_identifier` | The Identifier cell reads the same `pmid` field and prefixes it: "PMID:28340353". |
| 5 | `core/graph.py:13737-13742` | The Researcher row is `[label, identifier]`, so the number shows twice. |

Why it looks fine when the background search finishes: the live PubMed title row (`ncbi_efetch`, `pubmed_abstracts`) cites the same PubMed page, and `findings.one_finding_per_record` (`synthesis/findings.py:1245`) folds the two into one row named by the live title. Card 38 slice C's title lookup does not help either: `article_titles.article_curies_to_name` (`synthesis/article_titles.py:196-213`) picks graph `Article` rows only, so a PubTator3 `Publication` row is never looked up.

## What the run already holds

| Source | Holds the title? | Checked |
|---|---|---|
| The PubTator3 response itself | Yes, as the document's `title` passage | Live, 2026-10-22: 28340353 "Molecular Structure of the Human CFTR Ion Channel." and 20301425 "`<i>BRCA1-</i>` and `<i>BRCA2</i>`-Associated Hereditary Breast and Ovarian Cancer", the same words as PubMed's ESummary title once the formatting tags are removed |
| `article_titles` cache | Only for graph papers, never for these | Code |
| The background PubMed search | Only when it finishes and returns that paper | Report rows 2 and 3 |

PubTator3 keeps PubMed's inline formatting as markup (`<i>...</i>`), so the title needs those exact tags removed before it is shown.

## Options

| Option | Cost per answer | Calls | Honest when it fails? | Chosen |
|---|---|---|---|---|
| A. Keep the PubTator3 title the response already carries | 0 s | 0 new | Yes: with no title passage the row says so | Yes |
| B. One batched PubMed ESummary for untitled enrichment papers, inside Write, timeout 2 s | Up to 2 s, about 0.3 to 0.8 s typical (card 38 slice C measured 0.78 s median for 50 PMIDs over EFetch) | 1, counted against the per-query Layer 2 and 3 ceiling | Yes if it fails closed to the honest label | No, not needed: A covers every case the report shows. Kept here for a paper whose PubTator3 document has no title passage |
| C. Honest label only | 0 s | 0 | Yes | Part of A, as its fallback |

## The fix

- `tools/pubtator_annotate_schemas.py`: `PubtatorPublication.title`, an additive optional field (design decision 11), at most 500 characters.
- `tools/pubtator_annotate.py`: `_publication_title` reads the first passage whose `infons.type` is exactly "title", removes only the exact formatting tags `i`, `b`, `u`, `em`, `strong`, `sup` and `sub`, and collapses whitespace. Variant notation such as "c.3140-26A>G" and "<5 years" is kept as written. A title over 500 characters is withheld with a `fields_withheld` note, never clipped.
- `core/graph.py`, the `pubtator_annotate` branch only: the row gains `title`, cleaned by `article_titles.clean_article_title` (the graph paper's rule, so a "[Not Available]." placeholder is dropped). It sits after `pmid`, so the row's cited fact, what the writer is shown and the per-page fold are unchanged; only the list label reads it.
- `synthesis/answer_layout.py`: with no title on a `Publication` row, `record_label` returns the PMID with its system, "PMID:42477928", as card 38 slice C names a graph paper with a placeholder title; Plain language keeps "Published paper".
- `synthesis/findings.py`, `_listing_rank` (fix round): in the per-page fold, a `Publication` row's PMID view ranks after a view that names the paper, so PubMed's own title row names the paper whichever finding came first.

## Before and after

| Case | Before | After |
|---|---|---|
| Researcher, title held | 28340353 · PMID:28340353 | Molecular Structure of the Human CFTR Ion Channel. · PMID:28340353 |
| Researcher, title held with markup | 20301425 · PMID:20301425 | BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer · PMID:20301425 |
| Plain language, title held | Published paper | Molecular Structure of the Human CFTR Ion Channel. |
| Researcher, no usable title held (none, or a bracketed translated title the shared rule withholds) | 42477928 · PMID:42477928 | PMID:42477928 · PMID:42477928 |
| Plain language, no title held | Published paper | Published paper |
| Background search finishes, PubMed finding first | One row, the live PubMed title | Unchanged |
| Background search finishes, PubTator3 finding first | 42477928 · PMID:42477928 | PubMed's title · PMID:42477928 |

Time cost: none. No new call, no new wait; the title comes from a response the run already received.

Tests: `tests/system_03_search_agent/core/test_enrichment_paper_titles.py`, from the live PubTator3 document shapes. Removing the row's `title` or the honest-label branch turns them red with the reported "28340353 PMID:28340353" row.

Seen and not fixed here: a graph `Article` whose PubMed title is only a bracketed placeholder still reads "PMID:n" in both the Paper and the Identifier cells (card 38 slice C's "keeps its number"). Changing it would move a row waiting on the owner's retest, so it is left as it is.

## Fix round

Findings from `judge.md` and `adversary.md`, 2026-10-22, fixed in one round:

| Finding | Change |
|---|---|
| A-134-01, 04, 09 | "Title not retrieved" is gone: it was false for a non-English paper whose bracketed English title the shared `_BRACKETED_ONLY` rule withholds. The row is named "PMID:42477928" instead. The shared rule is unchanged. The fold now lets PubMed's title row name the paper whichever finding comes first (also J-134-04) |
| J-134-07 | Tests with "Lep <ob> mice", "p.(Arg<Ter>)" and "children <5 years and adults >60", which a greedy `<[^>]*>` rule turns red (checked by mutation) |
| A-134-06 | The `summary_label` branch is removed: papers are counted in the summary, never named, so it could not run |

Left as they are, on the coordinator's word: A-134-02 (retractions, a new card), A-134-03, 05, 07, 08 and J-134-01, 02, 03, 06.
