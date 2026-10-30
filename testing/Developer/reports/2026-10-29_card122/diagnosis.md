# Card 122 diagnosis: RS1 papers about other things named RS1

Card 122, in the person's words: `What does the RS1 gene do?` lists papers that are not about the RS1 gene, a "radial spoke 1" paper and a viral enzyme paper among its sources. Read-only diagnosis, 2026-10-29, on `chore/overnight-2026-10-29` (identical to develop for source). No model call was made; the live evidence is free NCBI E-utilities and PubTator3 GETs.

## Table of contents

- [Summary](#summary)
- [How a gene question finds its papers](#how-a-gene-question-finds-its-papers)
- [Evidence: the two wrong papers](#evidence-the-two-wrong-papers)
- [Cause, with code lines](#cause-with-code-lines)
- [Fix options measured](#fix-options-measured)
- [Recommended fix](#recommended-fix)
- [Owner decision](#owner-decision)
- [Overlap with other cards](#overlap-with-other-cards)

## Summary

| Question | Answer |
|---|---|
| Which layer added the wrong papers | Layer 2, the live PubMed search planned for every gene question (purpose `pubmed_search`). PubTator3 then annotates the same PMIDs, so the papers also arrive as Layer 3 "Publication" rows. Not the graph, not LitVar2. |
| Cause | The search is free text on the symbol, `RS1[Title/Abstract]`, relevance sorted, top 5. PubMed matches any "RS1" or "rS1" in any title or abstract, case-insensitive. Nothing ties the search to Gene ID 6247. |
| Reproducible | Yes, every run. Live today the two wrong papers are the first and second relevance hits. |
| Predates card 37 | Yes. The term shape dates from 2026-09-14 (`4f73f027`) and the relevance sort from 2026-09-20 (`70a6c4ed`). |
| Fix small | No. The clean fix is about 80 to 100 source lines across two areas (the ELink tool input and the breadth planner), plus tests. |
| Owner decision first | Yes: anchoring on the Gene ID trades the newest papers for certainty, and it changes every gene answer's paper list. |
| Build tonight | No, unless the owner answers the decision below before the run. |

## How a gene question finds its papers

A gene question plans these paper-bearing calls (`src/system_03_search_agent/core/graph.py`, Plan step, lines 7306 to 7367):

| Step | Call | Input | Anchored on the Gene ID? |
|---|---|---|---|
| 1 | Think resolves the gene | `NCBIGene:6247` | Yes |
| 2 | The symbol is read back from the mention | `gene_symbol = mention.strip().upper()` (graph.py:7325), "RS1" | Text only |
| 3 | PubMed ESearch, purpose `pubmed_search` | `RS1[Title/Abstract]`, `sort=relevance`, `retmax=5` (`breadth_plan.build_pubmed_term`, `plan_first_stage`) | No |
| 4 | Abstract fetch and PubTator3 `annotate_publications` | The same five PMIDs (`plan_literature_follow_up`, graph.py:8790) | Inherits step 3 |
| 5 | PubTator3 `entity_lookup` | "RS1"; rows kept only where the entity name equals the symbol (graph.py:5053 to 5083) | Name match; gives record 2, "RS1", correct |
| 6 | Gene ESummary | uid 6247 (`plan_gene_summary`) | Yes; gives the gene facts, correct |

Step 4's PubTator3 "Publication" rows (graph.py:5084) carry the paper titles the person saw. The papers are chosen once, in step 3.

## Evidence: the two wrong papers

The product check (`testing/Developer/reports/2026-10-17_product_check_card37/report.md`, PR-card37-06; text in `run1/rs1_gene_control_1280.txt`) names titles, not PMIDs. Looked up read-only:

| Record | Title | PMID | Why it matched "RS1" |
|---|---|---|---|
| 3 | Differential requirements of IQUB for the assembly of radial spoke 1 and the motility of mouse cilia and flagella. | 36417862 | "RS1" is the abbreviation for radial spoke 1 in sperm flagella |
| 7 | A viral ADP-ribosyltransferase attaches RNA chains to host proteins. | 37587340 | The abstract says phage ModB "RNAylates the ribosomal proteins rS1 and rL2"; the search is case-insensitive |

The planned search, run live today exactly as the tool sends it (`esearch db=pubmed term=RS1[Title/Abstract] sort=relevance retmax=5`), 1,269 hits, translated as `"RS1"[Title/Abstract]`:

| Rank | PMID | Title (shortened) | About retinoschisin? |
|---|---|---|---|
| 1 | 37587340 | A viral ADP-ribosyltransferase attaches RNA chains to host proteins | No |
| 2 | 36417862 | Differential requirements of IQUB for the assembly of radial spoke 1 | No |
| 3 | 41093192 | Dual delivery ... HITI knock-in ... X-linked juvenile retinoschisis | Yes |
| 4 | 40253584 | Intravitreal adenine base editing of RS1 ... retinoschisis | Yes |
| 5 | 42169001 | The role of the RS1-NEDD4-YAP1 axis ... in COPD | Doubtful: PubTator3 maps this "RS1" to mouse gene 20147, and the topic is lung |

Without the relevance sort the result is worse: the five newest "RS1" papers today include a plantain food-science review, a phonon physics paper and a "remote synchronization" network paper.

## Cause, with code lines

The gene question's literature search is a free-text match on the symbol, not a search anchored on the resolved Gene ID.

`src/system_03_search_agent/core/breadth_plan.py`:

```python
# line 291, in build_pubmed_term
clauses.append(f"{symbol}[Title/Abstract]")
# line 753, in plan_first_stage
calls.append(_search_call("pubmed_search", "pubmed", term, PUBMED_RESULT_CAP))
```

- The symbol arrives uppercased (line 232), but PubMed's `[Title/Abstract]` match ignores case, so "rS1" (ribosomal protein S1) matches too.
- `_build_breadth_calls` (`core/graph.py`, line 5432, called at 7359) receives only `gene_symbol`. The resolved `gene_curie` is in scope at line 7306 but never reaches the literature search.
- The relevance sort (`tools/ncbi_efetch_schemas.py`, line 258; `tools/ncbi_eutils_actions.py`, line 740) ranks by how prominent "RS1" is in a paper, and a paper whose whole subject is radial spoke 1 ranks above one where RS1 is a mention.
- Nothing downstream checks a paper against the gene. PubTator3's own gene normalisation cannot serve as that check: it maps the IQUB paper's "RS1" to human 6247 and mouse 20147, and maps the genuine retinoschisis base-editing paper (40253584) to mouse 20147 only.

The disease path (title search) and the topic path (`build_topic_term`) are separate and not part of this card.

## Fix options measured

Each option keeps the decision with NCBI's own records: it anchors on the Gene ID Think already resolved. None uses a list of ambiguous symbols. All timings are single live runs today.

| Option | What the person sees | Speed | Measured quality | Verdict |
|---|---|---|---|---|
| A. ELink from the Gene ID to PubMed, GeneRIF links only (`dbfrom=gene&db=pubmed&id=6247&linkname=gene_pubmed_rif`), newest five | Only papers NCBI's gene record cites as describing this gene | 0.23 s RS1, 0.35 s BRCA1, 0.54 s TP53 (110 KB); ESearch today 0.23 s | RS1: five retinoschisis papers, 2023 to 2024. GCK: five GCK papers. TP53: five p53 papers, newest 2024 | Recommended |
| A with the person's "how far back" window | The same, limited to the picked years | 1.13 s TP53 with `datetype=pdat&mindate&maxdate` | TP53 since 2024: 122 papers | ELink takes the window natively, so card 4's ask-back keeps working |
| B. ELink history, then ESearch `#key AND RS1[Title/Abstract]`, relevance sorted | The most relevant of the gene's linked papers | RS1 0.8 s; BRCA1 5.0 s; TP53 7.8 to 13.6 s | Best set (cryo-EM of retinoschisin, RS1 variant papers) | Rejected: breaks the 20 second answer rule on well-studied genes |
| C. Keep the text search, keep only hits linked to the gene | Fewer papers, all right | Plus one call; TP53's full link set is 343 KB | Of RS1's top 20 relevance hits only 3 are linked to 6247; the 2025 and 2026 gene-therapy papers drop | Rejected: loses most good papers |
| D. All gene-to-PubMed links, not only GeneRIF | Papers tied to the gene by any NCBI route | As A | Includes large interactome screens: RS1's second newest is a PARP interactor dataset; TP53's newest five are all such papers | Rejected: off-topic in a different way |
| E. PubTator3 search on `@GENE_RS1` | Papers PubTator3 tagged with the gene | Not timed | Top six include a sotalol chemistry paper and a Wnt bone paper | Rejected |

## Recommended fix

Option A: for a question whose gene resolved to an `NCBIGene:` CURIE, find its papers through NCBI's own GeneRIF links from that Gene ID, newest first, instead of a text search on the symbol.

What the person sees after, in their words: a question about one gene never lists a paper about a different thing that shares its name. Every listed paper is one NCBI's gene record itself cites for what that gene does. The newest papers may be missing, and a gene NCBI has no such papers for shows none rather than wrong ones.

Shape of the change:

- `tools/ncbi_efetch_schemas.py`, `NcbiEfetchLinkInput`: optional `linkname` (bounded, `<dbfrom>_<db>` prefix), optional `mindate` and `maxdate`.
- `tools/ncbi_eutils_actions.py`, `link`: send those parameters when given. The GeneRIF list was measured highest PMID first for RS1, BRCA1 and TP53, so the tool's cap of 100 ids keeps the newest; sort before the cap anyway, so the newest five never depend on ELink's order.
- `core/breadth_plan.py`: a planner for the gene literature link with purpose `pubmed_search`, so the abstract fetch and PubTator3 follow-ups run unchanged (`_search_ids` already reads ELink results, graph.py line 8756). `PublicationWindow` gives the dates.
- `core/graph.py`: pass the resolved `gene_curie` to `_build_breadth_calls` and plan the link in place of the symbol text search when one exists. A gene typed only as a symbol that did not resolve keeps today's path.

Size: about 80 to 100 source lines in four files, two areas (the ELink tool input and the breadth planner).

Tests that prove it:

| Test file | What it proves |
|---|---|
| `tests/system_03_search_agent/core/test_breadth_plan.py` | A gene CURIE plans `dbfrom=gene, db=pubmed, linkname=gene_pubmed_rif` on its own uid and never a `[Title/Abstract]` term; a window becomes `mindate` and `maxdate`; the disease and topic paths are byte-identical |
| The ELink tool tests next to `ncbi_eutils_actions` | `linkname` and the dates reach the request; ids are sorted highest first before the cap |
| A Plan-step test in `tests/system_03_search_agent/core/` | A resolved gene question plans no symbol text search; the follow-ups still run on the linked PMIDs |
| Live check, five runs, per the owner's rule | `What does the RS1 gene do?` lists no radial spoke or ribosomal S1 paper; TP53, BRCA1 and GCK still list papers, inside 20 seconds |

The live check spends money (model calls), so it belongs to the build, not this diagnosis.

## Owner decision

Asked first: for a gene question, which papers should the answer list?

| Option | What it costs the person |
|---|---|
| 1. Recommended: only papers NCBI's gene record cites for that gene (GeneRIF), newest first | No namesake paper ever. The newest papers lag: RS1's newest is from 2024 though 2025 and 2026 gene-therapy papers exist; TP53's newest is 2024. A gene with no GeneRIF shows no papers and says so. About 0.1 to 0.9 seconds slower on that one call, inside the parallel fan-out. |
| 2. Keep the symbol text search and drop papers not linked to the gene | No namesake paper, but most new, correct papers drop too (3 of RS1's top 20 survive), and one extra call. |
| 3. Leave the search as it is | Fast and fresh, but a symbol shared with something else keeps showing its papers; for RS1 they are the top two. |

Why this is the owner's call: it changes the paper list of every gene answer, which `_build_breadth_calls`' docstring already names as "a separate decision with its own evidence to gather", and it trades freshness against certainty. The standing rule "a confident wrong record is worse than a missing one" points to option 1.

## Overlap with other cards

| Card | Overlap |
|---|---|
| 37 (rs334 near-miss variants from LitVar2) | Same family of fault, a text match standing in for an identity, but a different tool (`tools/litvar2_lookup.py`) and the variant path. No shared code. |
| 129 (breast cancer genes read wrongly) | None in code. Card 129 is how a disease question is read, folded into card 56's redesign; this card is the gene path's literature search. If card 56 redesigns `breadth_plan`'s searches, build this fix first or inside it. |
| 145 (bronchiolitis not recognised) | None. Question reading, not search. |

Seen while tracing, not in this card's scope: the trials search (`query_cond` = the symbol) and the GEO DataSets search are also symbol text searches and can carry the same namesake risk.
