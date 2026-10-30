# Card 149 diagnosis: a human GCK answer cites the rat Gck record

Card 149, in the person's words: "A question about the human GCK gene cites "Gck", linked to NCBI Gene 24385, which is the rat gene, not human GCK (2645): a confident wrong record." Read-only diagnosis, 2026-10-30, source read as on `origin/develop` (`fa37d18c`). No model call was made. The live evidence is free PubTator3 and NCBI E-utilities GETs, at most 3 a second.

## Table of contents

- [Summary](#summary)
- [Where the "@GENE_GCK" source comes from](#where-the-gene_gck-source-comes-from)
- [Evidence](#evidence)
- [Why no species check stops it](#why-no-species-check-stops-it)
- [How often it happens](#how-often-it-happens)
- [Recommended fix](#recommended-fix)
- [Options not recommended](#options-not-recommended)
- [Owner decision](#owner-decision)
- [Overlap with other cards](#overlap-with-other-cards)

## Summary

| Question | Answer |
|---|---|
| Which layer | Layer 3, `pubtator_annotate` in `entity_lookup` mode, planned for every question that resolves a gene. Not the graph, not the PubMed search. |
| Cause | PubTator3's entity index answers `GCK` with one cross-species entry, `@GENE_GCK`, "All Species", whose representative NCBI Gene id is 24385, the rat gene. The tool turns that id into `https://www.ncbi.nlm.nih.gov/gene/24385`, and the only filter downstream is a case-insensitive name match, which "Gck" passes. |
| Cause clear | Yes. Reproduced offline through the shaping function and live against PubTator3 and NCBI Gene. |
| How common | 6 of 18 common gene symbols sampled cite another species' record today, including KRAS (rat), INS (dog) and SHH (mouse). |
| Fix | Keep a PubTator3 gene entity only when its NCBI Gene id is the gene the question resolved. Pure verification, no model call, no network call. |
| Fix small | Yes, about 25 source lines in `core/graph.py`, one area. |
| Owner decision needed | No. |
| Build tonight | Yes: the cause is clear, the fix is small and deterministic, and it only removes rows that cite the wrong record. |

## Where the "@GENE_GCK" source comes from

| Step | Code (on `origin/develop`) | What happens for `Which diseases are associated with GCK?` |
|---|---|---|
| 1 | `core/graph.py:7338` | Think resolves the gene to `NCBIGene:2645`, the human record. |
| 2 | `core/graph.py:7351` to `7357` | The symbol is read back from the mention, `GCK`. The numeric id 2645 is not passed on. |
| 3 | `core/graph.py:5245` to `5306`, `_build_layer_tool_calls` | Plans `pubtator_annotate` with `{"mode": "entity_lookup", "query": "GCK"}`. Only the symbol text travels. |
| 4 | `tools/pubtator_annotate.py:485` to `536`, `_parse_entity` | Reads PubTator3's autocomplete reply: `_id` "@GENE_GCK", `db` "ncbi_gene", `db_id` "24385", `name` "Gck". |
| 5 | `tools/pubtator_annotate.py:439` to `482`, `_entity_source_url` | Builds `https://www.ncbi.nlm.nih.gov/gene/24385` from `db_id`. |
| 6 | `core/graph.py:5068` to `5090`, `_layer_tool_output_to_structured_fields` | Keeps entities whose name equals the queried symbol after casefolding. "Gck" equals "gck", so the rat entity becomes a "Literature entity" row. |
| 7 | `core/graph.py:12827` to `12835`, `_layer3_citation_for_synth_finding` | The citation's `source` is the entity's `db` ("ncbi_gene") and its `source_id` is the row's `pubtator_id`, "@GENE_GCK". The screen renders this as "NCBI Gene @GENE_GCK", linking to gene 24385. |

## Evidence

- The answer: `testing/Developer/reports/2026-10-30_product_check_135_parts_2_3/q21_live_answer_sources_open.txt`, line 77 ("Gck | @GENE_GCK | 10"), lines 369 and 382 (source 10, "NCBI Gene @GENE_GCK", `https://www.ncbi.nlm.nih.gov/gene/24385`). The same answer cites the human record as gene 2645 (line 57 and line 175).
- PubTator3 live, `entity/autocomplete/?query=GCK&limit=10`: first entry `{"_id": "@GENE_GCK", "db": "ncbi_gene", "db_id": "24385", "name": "Gck", "description": "All Species"}`. No entry carries 2645.
- NCBI Gene ESummary live: 24385 is "Gck, Rattus norvegicus, taxid 10116"; 2645 is "GCK, Homo sapiens, taxid 9606".
- Offline reproduction: the shaping function on `origin/develop` code, fed the rat entity and the `GCK` input, returns one row, `{'name': 'Gck', 'pubtator_id': '@GENE_GCK'}`, source `https://www.ncbi.nlm.nih.gov/gene/24385`.

## Why no species check stops it

- The filter at `core/graph.py:5070` to `5085` was written for a frog homonym: `BRCA1` also returns `brca1.L`. It compares names, not records, and casefolds both sides, so "Gck", "Kras" and "Shh" (rodent symbol style) pass as the human symbols.
- PubTator3's gene entity is a symbol group across species, labelled "All Species". Its `db_id` is one representative record, and that record is often not the human one. The human record is then absent from the reply altogether, so no ordering or ranking could pick it.
- The planned call carries only the symbol text (step 3). The shaping step never sees the resolved Gene id, so it has nothing to compare against.
- When no entity's name matches exactly, the same filter keeps every citeable entity (`exact or citeable`), so a symbol with no exact match cites other genes outright (for `GCK` that would include GCKR and MAP4K2).

## How often it happens

Live PubTator3 autocomplete, exact-name gene entity only, with each non-human id confirmed by NCBI Gene ESummary:

| Symbol | Entity id PubTator3 returns | Species of that record |
|---|---|---|
| GCK | 24385 | Rat |
| KRAS | 24525 | Rat |
| PAH | 24616 | Rat |
| INS | 483665 | Dog |
| SHH | 20423 | Mouse |
| GBA1 | 449571 | Chimpanzee |
| BRCA1, TP53, CFTR, EGFR, APOE, MTHFR, LDLR, HBB, PTEN | 672, 7157, 1080, 1956, 348, 4524, 3949, 3043, 5728 | Human |

So a third of the sample, including KRAS and INS, shows a person a non-human gene record labelled as NCBI Gene in a human gene answer.

## Recommended fix

From the person's chair: a question about a human gene never cites another species' gene record as if it were the human one.

The rule: when the question resolved a gene, keep a PubTator3 gene entity only if its NCBI Gene id is the resolved gene's own id. This is verification, not a decision: it compares two record ids, the strongest form of the taxonomy check, and needs no network call. No list of symbols or species.

| Part | File and place | Change | Lines |
|---|---|---|---|
| 1 | `core/graph.py`, `_PlannedLayerToolCall` (line 4839) | Add a field, `expected_gene_id: str = ""`. | 3 |
| 2 | `core/graph.py`, `_build_layer_tool_calls` and `_layer_call` (lines 5238 to 5306) and its caller (line 7380) | Pass the numeric id from `gene_curie` (`NCBIGene:2645` gives `2645`) and set it on the `pubtator_annotate` call only when the search text is the gene symbol. A disease question passes nothing and is unchanged. | 8 |
| 3 | `core/graph.py`, the Act call site (line 8712) | Pass `expected_gene_id=planned.expected_gene_id` to the shaper. | 1 |
| 4 | `core/graph.py`, the `pubtator_annotate` branch (lines 5068 to 5090) | When `expected_gene_id` is set, keep only entities with `db == "ncbi_gene"` and `db_id == expected_gene_id`; otherwise keep today's name rule. Rewrite the comment to state the rule. | 12 |

What the person sees after: the GCK answer no longer lists "Gck | @GENE_GCK" or source "NCBI Gene @GENE_GCK". The human record, gene 2645, is still cited from the gene summary and the graph. For TP53, BRCA1 and other symbols whose entity is human, nothing changes. The PubTator3 call that keeps no row reports `empty`, the same state as a symbol PubTator3 does not know, so no "search did not finish" note appears.

Tests (all offline, in `tests/system_03_search_agent/core/test_layer_handoff.py`, beside the existing frog test at line 340):

- A rat `Gck` entity (24385) shaped with expected id 2645 yields no row and status `empty`.
- A human `TP53` entity (7157) with expected id 7157 is kept; the frog `brca1.L` and a different human gene (GCKR, 2646) with expected id 672 or 2645 are dropped.
- With no expected id (the disease path), today's behaviour holds, including the frog test as it stands.
- A plan test: `_build_layer_tool_calls` for a resolved `NCBIGene:2645` sets `expected_gene_id` "2645" on the `pubtator_annotate` call, and a disease-only call sets none.
- Mutation check: removing the id comparison turns the rat test red.

Cost: about 25 source lines and about 40 test lines, no model spend, no new network call, no prompt change. Verification after deploy: query 21 on develop shows no 24385 link; a KRAS question shows no 24525 link.

## Options not recommended

| Option | Why not |
|---|---|
| Fetch each entity's taxonomy from NCBI Gene and keep taxid 9606 | One extra network call per answer for a weaker check: the entity rows are already name-matched, so the only thing a taxonomy check adds over id equality is accepting a different human gene of the same name, which is not wanted. |
| Ask a classifier whether the entity is the right gene | A model call to decide something two record ids already settle. The project rule puts judgement in a classifier and verification in code; this is verification. |
| Drop the PubTator3 entity row for every gene question | Loses nothing today but removes the row for the human cases too; the id check keeps it where it is correct. |
| Search PubTator3 by the Gene id instead of the symbol | The autocomplete endpoint takes text, and the human id is absent from its reply for GCK, so there is nothing to search for. |

Adjacent, not in this card: PR-135B-04's label "NCBI Gene @GENE_..." names the record by PubTator3's tag rather than the Gene id. After this fix every kept entity's `db_id` equals the resolved id, so a later change could carry `db_id` on the row and show "NCBI Gene 7157". That is a label change for card 135's follow-up, not a wrong record.

## Owner decision

None needed. The fix only removes rows that cite a record other than the gene the question resolved, which is the product's stated rule ("a confident wrong record is worse than a missing one"), and it adds no spend.

## Overlap with other cards

| Card | Overlap |
|---|---|
| 122 (RS1 papers about other things) | Same family, a symbol's text standing in for the gene's identity, but a different call: card 122 is the PubMed search `RS1[Title/Abstract]`; this card is the PubTator3 entity row. No shared code. Card 122's diagnosis already noted PubTator3 maps genuine papers' genes to mouse ids, so PubTator3's gene normalisation cannot be the species check. |
| 135 (source names) | PR-135B-04 is the label of the same row. This fix removes the wrong rows; the label for correct rows stays card 135's. |
| 37 (LitVar2 near-miss variants) | Same family, different tool. No shared code. |
