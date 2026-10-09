# Card 15 build: no model-written graph search except a true count

Build report for card 15's second step, 2026-10-08. Decision D5 (`testing/Board_plan.md`): no model-written graph search except true count questions. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card15_diagnosis.md` (night documents).

## Table of contents

- [Base](#base)
- [Live read-only check](#live-read-only-check)
- [The rule](#the-rule)
- [Each path and what it does now](#each-path-and-what-it-does-now)
- [Tests](#tests)
- [Mutation checks](#mutation-checks)
- [Paths kept and why](#paths-kept-and-why)
- [Deviations](#deviations)
- [Learnings](#learnings)

## Base

Branch `fix/card15-checked-graph-searches`, base `c916cfa30f59802dfd85c81ef7ba39bdcfc2b263` (`git rev-parse HEAD` at start).

## Live read-only check

The diagnosis asks for a read-only check that a ClinVar variant and an organism record carry what the record template returns. Run through `cypher_query` with the record template forced, read-only role, no model call:

| Anchor | Status | Rows | Time | Source link |
|---|---|---|---|---|
| ClinVar:17661 | ok | 1 | 0.42 s | ClinVar variation page |
| ClinVar:12345 | ok | 1 | 0.42 s | ClinVar variation page |
| NCBITaxon:9606 | ok | 1 | 0.44 s | NCBI Taxonomy browser page |
| NCBITaxon:562 | ok | 1 | 0.43 s | NCBI Taxonomy browser page |
| ClinVar:999999999 (absent) | empty | 0 | 0.42 s | none |
| NCBITaxon:999999999 (absent) | empty | 0 | 0.41 s | none |

Every row carried `id`, `name`, `source`, `source_url`, `xrefs`. The inline id match is indexed on both labels, as on Gene and Disease, so the record template is safe to extend to them.

The variant's conditions, through the `has_phenotype` edge from a SequenceVariant to a Disease, read-only, same method:

| Anchor | Template | Status | Rows | Time |
|---|---|---|---|---|
| ClinVar:17661 | records | ok | 12 | 0.42 s |
| ClinVar:17661 | count | ok | 1 | 0.48 s |
| ClinVar:12345 | records | ok | 1 | 0.44 s |
| ClinVar:1179956 | records | ok | 1 | 0.42 s |
| ClinVar:999999999 (absent) | records | empty | 0 | 0.44 s |
| ClinVar:999999999 (absent) | count | empty | 0 | 4.45 s |
| ClinVar:17661 and ClinVar:12345 | records, IN list | ok | 15 | 5.21 s |

## The rule

One routing rule over every path, in `select_template` and the model-path branch of `cypher_query._run_pipeline`:

1. A shaped template that fits runs, as before (`_shaped_template`, the old `select_template` body, unchanged in logic).
2. When none fits and the question is a true count (`written_search_allowed`, which is the existing `_wants_count` test), the model may still write the search. D5 allows this.
3. When none fits and it is not a true count, the one named entity's own record runs (`_record_fallback`), on any label a template may anchor on.
4. With several entities or a label mix, no graph search runs. `cypher_query` returns `status: "empty"`, no plan-tier call, no graph call, and `NO_CHECKED_SEARCH_MESSAGE` in `error`. `empty`, never `error`, so the Act step does not add the line "One of the background searches did not finish". The answer rests on Layers 2 and 3, as when the graph holds nothing.

The question's kind comes from Think's class and the existing count test; no new word list was added. `core/graph.py` was not touched.

## Each path and what it does now

| Path (diagnosis table) | Example | Before | Now |
|---|---|---|---|
| Anchor is a ClinVar variant, no shape | "Tell me about ClinVar:17661" | model-written | `sequencevariant_record_one` |
| Anchor is a ClinVar variant, conditions asked | "What conditions is ClinVar:17661 linked to?" | model-written | `sequencevariant_diseases_one` (count: `_count`; several: `_many`) |
| Anchor is an organism | "Tell me about NCBITaxon:562" | model-written | `organismtaxon_record_one` |
| Anchor is a MeSH, GO or phenotype term, or an id the graph does not hold | "Which genes take part in GO:0006281?" | model-written | no graph search |
| Labels mixed other than Gene with Disease | "Does PMID 11237011 discuss BRCA1?" | model-written | no graph search |
| One Disease, no shape, `single_hop` or `multi_hop` | "What is linked to Marfan syndrome?" | model-written | `disease_record_one` |
| Several Diseases, no shape, hop class | "What is linked to these diseases?" | model-written | no graph search (G-014) |
| One Disease, no shape, `aggregate`, no count | "Summarise what the graph holds on Marfan syndrome" | model-written | `disease_record_one` |
| Several Diseases, no shape, `aggregate`, no count | same, two diseases | model-written | no graph search |
| Several Articles, no shape, not a lookup | "Compare PMID 11237011 and PMID 11237012" | model-written | no graph search |
| Gene with Disease: variants shape with several genes, or another shape | "Variants in MLH1 and MSH2 causing Lynch syndrome" | model-written | no graph search |
| Two shapes, several anchors, outside lookup, single-hop and aggregate | "Variants and orthologs for BRCA1 and BRCA2" on `multi_hop` | model-written | no graph search |
| A count over several anchors | "How many variants do BRCA1 and BRCA2 have?" | model-written | model-written (D5 allows) |
| An aggregate count on a Disease or Article with no shape | "How many records mention Marfan syndrome?" | model-written | model-written (D5 allows) |

## Tests

New and changed arms:

| File | Arm | Closed paths covered |
|---|---|---|
| `tests/system_03_search_agent/tools/test_cypher_templates.py` | `test_a_question_no_checked_template_fits_takes_no_written_search`, 15 cases | every "no graph search" row above |
| same | `test_one_named_entity_no_shaped_template_fits_takes_its_own_record`, 8 cases | one Disease on hop and aggregate classes, the phenotype question, organism, variant |
| same | `test_a_variant_conditions_question_takes_the_checked_has_phenotype_hop`, 4 cases | variant conditions, one, several, count |
| same | `test_a_true_count_no_template_fits_may_take_a_written_search`, 9 cases | the two count rows stay open |
| same | `test_anchor_label_for_requires_one_known_label`, updated | ClinVar and NCBITaxon are anchors; GO and HP are not |
| `tests/system_03_search_agent/tools/test_cypher_query_templates.py` | `test_a_question_no_checked_search_fits_runs_no_written_search`, 6 cases | no plan-tier call, no graph call, `empty`, message set |
| same | `test_one_named_entity_with_no_shaped_template_runs_its_record_not_a_written_search`, 3 cases | variant, organism, one Disease through the pipeline |
| `tests/system_03_search_agent/tools/test_cypher_query.py` | autouse fixture also opens `written_search_allowed` | keeps that file testing the generated path's mechanics |

Pass counts, pasted from output:

| Run | Result |
|---|---|
| The four cypher test files, base `c916cfa3` | 137 passed, 1 skipped in 6.74s |
| The four cypher test files, after commit 1 | 162 passed, 1 skipped in 6.63s |
| The four cypher test files, after commit 2 | 166 passed, 1 skipped in 6.99s |
| `tests/system_03_search_agent/tools` | 1688 passed, 99 skipped in 26.60s |
| `tests/system_03_search_agent/core` | 1385 passed, 56 skipped in 64.17s (0:01:04) |
| `ruff check` and `isort --check-only` on touched files | All checks passed, isort exit 0 |

## Mutation checks

Each broken by hand, run, then restored from a copy; `git diff --stat` confirmed the restore each time.

| Mutation | Result |
|---|---|
| M1: the gate in `_run_pipeline` disabled (`if False and ...`) | 6 failed, 9 passed, 1 skipped: every no-written-search pipeline case |
| M2: `select_template` returns None instead of `_record_fallback` | 9 failed, 89 passed, 1 skipped: every record-fallback case (the two `lookup` cases stay green, they already took the record) |
| M3: `written_search_allowed` always True | 30 failed, 68 passed, 1 skipped |
| M4: SequenceVariant and OrganismTaxon removed from `_TEMPLATED_LABELS` | 7 failed, 91 passed, 1 skipped |
| M5: the `("SequenceVariant", "diseases")` hop removed | 4 failed, 83 passed |

## Paths kept and why

No non-count path keeps a model-written search. Paths closed to "no graph search" lose any graph rows the written search may have returned; how often that happened is not measured. The checked template each would need:

| Path | Template it would need |
|---|---|
| A GO term anchor | the term's genes, `(x:Gene)-[:participates_in]->(a:BiologicalProcess {id: $e})` and the two sibling GO edges, after a live timing check from the term end |
| A MeSH term anchor | the term's papers through `has_mesh_annotation` from the term end, after a live timing check |
| Several Articles, no shape | `article_record_many` (the existing record template), if the owner wants several named papers treated like one |
| A Gene with an Article | the link `(a:Gene {id})-[:mentioned_in]->(x:Article {id})`, both ends inline |
| Several genes, variants shape, beside a disease | `gene_variant_disease_link` over each gene, as UNION ALL branches |

## Deviations

- The variant conditions hop is a new row in `_HOPS`, built by the existing `_hop_template`, not only an existing template. Without it the diagnosis's own example question would have lost its conditions. It is its own commit and can be reverted alone; the question then takes the variant's record.
- The several-variant form uses the IN list (5.2 s live), like the other hop `_many` forms.
- Read-only graph queries were run, as the diagnosis asks, through `cypher_query` with a forced template. No write, no model call.
- `NO_CHECKED_SEARCH_MESSAGE` reaches the structured fields Write reads, so it is plain words with no decision ids.
- The test query entry is 110, the number the diagnosis proposed, leaving 108 and 109 free.

## Learnings

None cost more than five minutes.
