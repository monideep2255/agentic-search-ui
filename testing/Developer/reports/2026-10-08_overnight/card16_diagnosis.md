# Card 16 diagnosis: three golden questions get nothing from the graph

Read on develop at `c916cfa3`, 2026-10-08. Code reading and saved run files only; no live run, no model call.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

The card's frame is out of date. The graph holds no SRA runs, no genome assemblies and no disease-to-feature edges, so "nothing from the graph" is correct and permanent for all three. What matters is whether the person gets an answer from NCBI's live records. Two later builds gave each question a Layer 2 route.

| Question | Status | Evidence |
|---|---|---|
| G-022, Marfan syndrome's phenotypic features | Already fixed on develop: item 12.14, approved 2026-09-29. The features come from MedGen's live record, not the graph | Golden run of 2026-09-29, G-022 answered 3 of 3 (`testing/Developer/reports/2026-09-29_card63_golden/summary.md`); `testing/UI_fixes_done.md:204` |
| G-005, SARS-CoV-2 SRA runs | Partly fixed by card 56 (#173, #186). Still happens in more than half the runs: 9 of 20 live runs on develop's plan model took the SRA route; 7 refused naming "Illumina", 3 asked back, 1 bound "respiratory" as a disease | `testing/Developer/reports/2026-10-06_card56/build_r3.md:71` to `:83`; `testing/UI_fix_plan.md:29` |
| G-036, Mycobacterium tuberculosis assemblies | Cannot tell without a live run. The route exists and Think and Plan chose it 3 of 3 locally; Act and Write were never run end to end, and not on develop's plan model | `testing/Developer/reports/2026-10-05_wave3/card56.md`, live runs table and "Not covered"; `testing/Developer/reports/2026-10-06_card56/build_r3.md:90` and `:119` |

## What a person sees

- G-022: Marfan syndrome's clinical features named from MedGen, each cited.
- G-005, about 9 runs in 20: SARS-CoV-2 runs from NCBI's SRA, up to 10, each linked, with SARS-CoV-2's Taxonomy record. The search is by organism alone, so the runs are not filtered to Illumina or to clinical respiratory samples, and nothing explains why each one matched. The golden row's own note calls that explanation "the differentiator".
- G-005, about 7 runs in 20: no search runs, and the refusal names "Illumina" as the thing it could not recognise. About 3 in 20 are asked "which gene, variant or condition do you mean?". About 1 in 20 answers about respiratory disease records.
- G-036: expected, from the code, up to 10 M. tuberculosis assemblies with their Taxonomy record. Not seen on screen by anyone yet. Nothing in the code tells the person how to retrieve them, which the question asks.

## The cause

The original cause (Think resolved no organism, so G-005 bound the disease "SARS" and G-036 was asked "which gene, variant or condition") is fixed. What remains:

1. The graph cannot answer these. Its vertex labels are Article, Gene, SequenceVariant, OrganismTaxon, Disease, three GO labels, OntologyClass, PhenotypicFeature and NamedThing (`src/system_03_search_agent/tools/graph_schema_constants.py:43` to `:55`). No SRA or assembly label exists.
2. The organism route is blocked by any failed gene span. `think_node` takes the route only when `not model_resolution.unresolved_symbols` (`src/system_03_search_agent/core/graph.py:4273`). When the plan model tags "Illumina" as a gene, the live gene lookup rejects it, it becomes an unresolved symbol, and the route is skipped. Measured: 4 of 26 runs on develop's plan model before #186 (`testing/Developer/reports/2026-10-06_card56/findings.md`), 7 of 20 after it (`build_r3.md:76`). The owner kept this refusal on 2026-10-06 and left it "for a design with the owner" (`DECISIONS.md:851`).
2a. The plan model sometimes tags nothing, or tags the organism only as a disease (3 of 20), and is then asked back; once it tagged "respiratory" as a disease (1 of 20). Both are the model's habit, not a code path this card can close alone.
3. The search uses the organism only. `plan_organism_records` searches `txid<taxid>[Organism:exp]` and nothing else (`src/system_03_search_agent/core/breadth_plan.py:1002` to `:1025`). The platform and the sample type in G-005 are dropped by design, and the Plan narrative says so (`core/graph.py:6941` to `:6943`).
4. No retrieval guidance. A search for "datasets download", "how to retrieve" and the genomes FTP path in `src/` finds only a docstring in `core/accession.py:4`. G-036's second half has no source to answer from.

## The smallest fix

Card 16 needs no build of its own. Its remaining causes are card 56's open items. Recommendation: close card 16 into card 56 after one live check of G-036.

| Step | What changes, in the person's words | Fence | Answer path | Dial | Size |
|---|---|---|---|---|---|
| 1, a check, not a build | Ask G-036's exact question once on develop and read the answer | None | No | none | S |
| 2, card 56's "Illumina" part | A sequencing platform or sample type in an SRA question is set aside and named as not applied, rather than stopping the search | `core/graph.py` `think_node`, the organism-route gate at `:4269` to `:4278`; one classifier decision registered in `harness/decide.py` (the 2026-10-06 diagnosis, fix part 4) | Yes | 2, runnable behaviour | M |
| 3, optional | G-036 says how to fetch the listed assemblies, as one fixed sentence naming NCBI's Datasets download page for the organism | Write's organism-records note, beside `_build_failed_search_note`'s notes in `core/graph.py` | Yes | 1, copy | S |

## Overlap with phase 8.7 and the guardrail

| Step | Phase 8.7 overlap | Guardrail overlap |
|---|---|---|
| 1 | None | None |
| 2 | Yes: `harness/decide.py`, which phase 8.7 rewrites, for the new decision point. `think_node` itself is not on 8.7's list | None |
| 3 | Likely yes: the note is assembled under `write_node` | None |

## Needs the owner

No for card 16 itself: closing it into card 56 is a board move. Yes for step 2, a design choice: the owner kept the "Illumina" refusal on 2026-10-06 and asked for a design first (`DECISIONS.md:851`; `testing/UI_fix_plan.md:29`). The question for that design: should a word that fails the gene lookup on an SRA or assembly question be set aside with a "not applied" note, decided by the classifier, or keep refusing? No package, migration or security change either way.

## Test query

Covered by query 103 (`testing/Test_queries_and_workflows.md`, "An organism's records, not a disease with a similar name") for G-005 and the assembly route, and by query 66 for G-022. One gap: query 103 asks "Which genome assemblies are available for Mycobacterium tuberculosis?", without "how do I retrieve them". Proposed addition to query 103's "Queries to try", same shape:

```markdown
- `Which Mycobacterium tuberculosis genome assemblies are available, and how do I retrieve them?`: the golden question G-036 as written.
```

and to its "What you should see":

```markdown
- For the assemblies question, up to 10 M. tuberculosis assemblies, each linked to its NCBI Assembly page, with the organism's Taxonomy record; the answer says how many NCBI holds against how many are shown. If it does not say how to download them, report it: that half is not built yet.
```
