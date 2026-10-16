# Card 15 build: four checked graph searches

Built exactly to `design.md`, with the lead's decision of 2026-10-15 (`DECISIONS.md`): four checked graph searches, one per slice, smallest first. Papers' records from typed PMIDs, a gene in one paper, several genes' variants for a condition, and a disease's variants walked from the disease end. The GO-term and MeSH-term shapes are not built.

## Table of contents

- [Base](#base)
- [Slices at a glance](#slices-at-a-glance)
- [Slice A: papers named](#slice-a-papers-named)
- [Slice B: a gene in one paper](#slice-b-a-gene-in-one-paper)
- [Slice C: several genes' variants for a condition](#slice-c-several-genes-variants-for-a-condition)
- [Slice D: a disease's variants](#slice-d-a-diseases-variants)
- [Live budget](#live-budget)
- [Findings for the lead](#findings-for-the-lead)
- [Gates](#gates)
- [Learnings](#learnings)

## Base

- Worktree `asu-wt/card15`, branch `fix/card15-checked-templates`, HEAD `f78ffda318221224ba3cd3e15a91c2da55ee58ca` (develop `7626fe85` plus the design commit). Working tree was clean at the start.
- Nothing committed. Each slice's files are staged by name in the index as one cumulative state, and one patch per slice was written outside the repository so the lead can commit them in order.

## Slices at a glance

| Slice | Shape | Template | Decision option | Query |
|---|---|---|---|---|
| A | Records of two to ten named papers | `article_record_many` (existing record form) | `papers_named` | 115 |
| B | Whether one named paper mentions one named gene | `gene_article_link` | `gene_in_paper` | 116 |
| C | Variants in two to ten genes for one or more conditions | `gene_variant_disease_link_many` | `genes_variants_for_condition` | 117 |
| D | One condition's variants, walked from the disease end | `disease_variants_one` | `disease_variants` | 118 |

How it works, for all four:

- Plan builds the graph call exactly as develop does. Develop's `select_template` runs first. Any template, no decision is asked and nothing changes.
- With no template, `possible_graph_shapes` reads the bound identifiers' prefixes and counts only. None possible, no decision.
- Otherwise one decision, `plan.graph_shape`, is asked with only the possible shapes plus `none_of_these` (fail open `none_of_these`), bounded by Plan's step deadline. A pick forces that shape's template through the existing `template=` seam. `none_of_these`, no usable pick, a failed seam or a timeout leave the planned call as develop has it.
- Code: `tools/cypher_templates.py` (`possible_graph_shapes`, `graph_shape_template`, the three new templates), `core/graph.py` (`_GRAPH_SHAPE` spec, `_graph_shape_spec`, `_checked_graph_shape`, one call in `plan_node`).

## Slice A: papers named

Files staged for the slice:

- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/tools/cypher_templates.py`
- `tests/system_03_search_agent/core/test_graph_shape_wiring.py` (new)
- `tests/system_03_search_agent/tools/test_cypher_shape_templates.py` (new)
- `testing/Test_queries_and_workflows.md` (query 115)

Tests: 21 new (12 on templates and the pipeline, 9 on Plan's decision seam), including `none_of_these`, no usable pick and a failed seam each leave the planned call equal to develop's (cypher input, template, flags), a two-paper lookup that develop already templates never asks, and one paper or a gene question never asks.

A change the live check forced: with a papers pick, Plan's topic search (`plan.literature`) used to replace the graph call anyway. `Compare PMID 11237011 and PMID 11237012` was read as wanting papers and planned a PubMed search for the words "compare, pmid", which showed four unrelated papers. The topic path now skips a call that carries a forced template (`planned.template is None` added to its condition; every call develop plans there has no template, so develop is unchanged). Two tests pin it: a pick survives a "wants literature" decision, and without the pick the literature search is planned as before.

Mutation, one property, red and restored: ignoring the pick (always returning the unforced call) turned `test_a_papers_named_pick_forces_the_checked_record_template` red (1 failed, 6 passed), then 7 passed after restore. A second check on the topic guard: removing it turned the displacement test red.

Held-out phrasings through the real decision seam (classifier provider `jev`, ten shape phrasings and ten near misses written after the criteria and kept out of them): 20 of 20 agree. Near misses covered counts, cited-by, genes mentioned, MeSH terms, sequence data, authors, treatment, trials and variants.

Live check, question `Compare PMID 11237011 and PMID 11237012`, develop's settings, through `run_streaming` with `reads_placement=True`:

| Run | Branch | Seconds | Graph call | Sources |
|---|---|---|---|---|
| A1 | first batch, run 1 | 15.2 | guardrail transient error, no answer | 0 |
| A2 | first batch, run 2 | 7.8 | `article_record_many`, 2 rows | PMID:11237011, PMID:11237012 |
| A3 | first batch, run 3 | 6.6 | `article_record_many`, 2 rows | same two |
| A4 | first batch, run 4 | 7.2 | `article_record_many`, 2 rows | same two |
| A5 | first batch, run 5 | 7.5 | none: Think read it as a lookup, develop's record template applied, then the literature search replaced it | four unrelated papers |
| A2-1 to A2-5 | second batch | 13.1, 12.9, 6.4, 5.3, 9.7 | `article_record_many`, 2 rows, 5 of 5 | same two, 5 of 5 |
| Develop 1 to 5 | shape step switched out | 6.1, 7.9, 9.9, 6.1, 6.4 | none, literature search 5 of 5 | four unrelated papers, 5 of 5 |

- Pass: second batch 5 of 5 same two sources under 20 s, no lost-search line. First batch 3 of 5 (one infrastructure error, one lookup-class run, see findings).
- Reading the answers: no record about an entity the person did not type on the checked runs. Develop's answers name four papers the person never asked for.

## Slice B: a gene in one paper

Files staged for the slice:

- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/tools/cypher_templates.py`
- `tests/system_03_search_agent/core/test_graph_shape_wiring.py`
- `tests/system_03_search_agent/tools/test_cypher_shape_templates.py`
- `testing/Test_queries_and_workflows.md` (query 116)

Template: `MATCH (a:Gene {id: $g})-[:mentioned_in]->(x:Article {id: $p}) RETURN x ORDER BY x.id`, both ends inline, walked from the gene end, edge documented at import. Eligible only for exactly one gene and one paper.

Tests: 10 new template and pipeline tests and 5 new wiring tests. Includes eligibility rows, the template text, develop having no template for the pair, an unlinked pair returning status `empty` with no rows and no error (the graph says only that it holds no link), and a linked pair returning the paper cited.

Mutation, one property, red and restored: reversing the edge direction turned `test_the_gene_in_paper_template_anchors_both_ends_inline_from_the_gene_end` red (1 failed, 21 passed), then 22 passed.

Held-out: 19 of 20 agree. Miss: `How many times is BRCA1 cited by PMID 11237011?` picked `gene_in_paper`. The result would be the link row or none, not a record about another entity.

Live check, `Does PMID 11237011 discuss BRCA1?` (the design's example; the graph holds no link for this pair):

| Run | Seconds | Branch graph call | Develop graph call (seconds) |
|---|---|---|---|
| 1 | 14.6 | `gene_article_link`, empty | written search, empty (13.1) |
| 2 | 12.7 | `gene_article_link`, empty | written search, empty (10.6) |
| 3 | 10.7 | `gene_article_link`, empty | written search, empty (9.6) |
| 4 | 9.6 | `gene_article_link`, empty | written search, error (11.7) |
| 5 | 10.3 | `gene_article_link`, empty | written search, empty (10.6) |

- Sources 17 on every run, both sides. No answer says the paper does not discuss BRCA1. The full answers (two runs, read in full) carry the note that the answer does not address PMID 11237011, then BRCA1 records from other databases.
- A linked pair, `Does PMID 10026184 discuss BRCA1?`, three branch runs (11.8, 15.0, 10.7 seconds): `gene_article_link` returned PMID:10026184 on 3 of 3 and the answer lists it first as Article record [1], cited to its PubMed page.

## Slice C: several genes' variants for a condition

Files staged for the slice:

- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/tools/cypher_templates.py`
- `src/system_03_search_agent/tools/cypher_query.py` (a `branch_row_cap` check, below)
- `tests/system_03_search_agent/tools/test_cypher_templates.py` (the ordering rule gains a bounded-template case)
- `tests/system_03_search_agent/core/test_graph_shape_wiring.py`
- `tests/system_03_search_agent/tools/test_cypher_shape_templates.py`
- `testing/Test_queries_and_workflows.md` (query 117)

Template: one branch per gene in parameter-name order, joined by `UNION ALL`. Each branch is the one-gene fold pattern with `ORDER BY v.id LIMIT <100 divided by the genes>` taken before its `RETURN`. Several conditions use the `IN` clause the one-gene template uses. Eligible for two to ten genes with one to ten conditions, nothing else.

A defect found while building, fixed in this slice: the design relied on the overall cap to report a capped result. With a per-gene share of 50, one gene with hundreds of variants and another with 30 returns 80 rows, under the overall limit of 100, and `cypher_query` would have said the result was complete. `CypherTemplate` gains `branch_row_cap`; `cypher_query` reports a result of at least that many raw rows as capped with the total unknown (a UNION is never counted). It claims less than is true at most, never more. The existing ordering test now allows a scoping `LIMIT` inside a bounded template and still requires none at the end.

Tests: 15 new template and pipeline tests and 5 new wiring tests. Includes the exact two-gene text and its share of 50, a share of 33 for three genes, the `IN` clause for two conditions, develop returning None only with a variants word, each variant row carrying its condition ids through the fold, 80 rows reporting capped with the total unknown and exactly one statement executed, and 49 rows not reporting capped.

Mutation, one property, red and restored: setting `branch_row_cap=None` turned three tests red, including `test_a_result_as_large_as_one_genes_share_reports_capped_with_the_total_unknown` (3 failed, 34 passed), then 37 passed.

Held-out: 19 of 20 agree. Miss: `How many variants in MLH1 and MSH2 cause Lynch syndrome?` picked the shape; the person gets a capped list, not a number.

Probe of the final template on the live graph (read-only, through the reader helper): 2.28 s, 100 rows, 50 MLH1 and 50 MSH2.

Live check, `Variants in MLH1 and MSH2 causing Lynch syndrome`:

| Run | Branch seconds | Branch graph call | Develop seconds | Develop graph call |
|---|---|---|---|---|
| 1 | 13.0 | `gene_variant_disease_link_many`, 100 rows, capped, total unknown | 41.7 | written search errored, no rows |
| 2 | 13.6 | same | 40.0 | written search errored, no rows |
| 3 | 10.3 | same | 15.4 | written search, 100 rows, capped |
| 4 | 11.4 | same | 15.6 | written search, 100 rows, capped |
| 5 | 12.4 | same | 39.6 | written search, 100 rows, capped |

- Branch: the same 100 graph rows in the same order on 5 of 5, under 20 s on every run, no lost-search line. Develop: 3 of 5 over 20 s and 2 of 5 with no graph rows.
- The branch answer lists variants of both genes (47 MLH1 and 10 MSH2 names in the displayed part) with the line "this answer was truncated before every matching record could be retrieved, and the exact total ... is not available".

## Slice D: a disease's variants

Files staged for the slice:

- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/tools/cypher_templates.py`
- `tests/system_03_search_agent/core/test_graph_shape_wiring.py`
- `tests/system_03_search_agent/tools/test_cypher_shape_templates.py`
- `testing/Test_queries_and_workflows.md` (query 118)

Template: `MATCH (x:SequenceVariant)-[:has_phenotype]->(a:Disease {id: $e}) RETURN x ORDER BY x.id`. Eligible for exactly one condition and nothing else (several MedGen concepts bound from a common noun is a different, riskier question). One match, so the count rewrite applies and a capped result reports its true total.

Probes (read-only, reader helper, written into this report as the lead asked): 100 rows in 0.73 s and its count 0.62 s (5,230) for MedGen:C0010674; 100 rows in 0.93 s and its count 0.96 s (46,028) for MedGen:C0346153.

Tests: 11 new template and pipeline tests and 5 new wiring tests. Includes eligibility rows, the template text, develop having no template on the aggregate, single hop and multi hop classes, and a capped result reporting `total_available` 5,230 through the count query (two statements executed).

Mutation, one property, red and restored: reversing the edge turned `test_the_disease_variants_template_walks_from_the_disease_end_with_one_inline_match` red (1 failed, 47 passed), then 48 passed.

Held-out: 19 of 20 agree. Miss: `Show me the pathogenic changes behind cystic fibrosis.` picked `none_of_these`, which is the safe direction (develop's path).

Live check, `What variants cause cystic fibrosis?`:

| Run | Branch seconds | Think class | Branch graph call | Develop seconds | Develop graph call |
|---|---|---|---|---|---|
| 1 | 8.3 | exploratory | `disease_record_one`, 1 row | 6.9 | `disease_record_one`, 1 row |
| 2 | 7.1 | exploratory | `disease_record_one`, 1 row | 9.8 | written search, 100 rows, capped |
| 3 | 10.9 | multi_hop | `disease_variants_one`, 100 rows, capped, total 5,831 | 16.7 | written search, 100 rows, capped |
| 4 | 15.0 | none | guardrail transient error, no answer | 8.8 | `disease_record_one`, 1 row |
| 5 | 6.9 | exploratory | `disease_record_one`, 1 row | 6.6 | `disease_record_one`, 1 row |

- Honest reading: the shape fired on 1 of 4 usable branch runs. On the exploratory reading develop's own record template applies, so by the decision's rule no decision is asked and the person sees the disease record and live PubMed records, not variants. See the findings.

## Live budget

- Every live run, branch and develop, all four shapes plus the extra checks, summed from the runs' own cost events: $0.37 against the $0.80 allowance.
- Per run $0.0001 to $0.0164. Classifier calls for the held-out checks (80 decisions) cost cents and are not in that sum.
- Develop's settings throughout: `CLASSIFIER_PROVIDER=jev`, guard and plan models `deepseek/deepseek-v4-flash`, synth model `z-ai/glm-5.2`, `PER_QUERY_COST_CAP_USD=0.25`. No Opus.

## Findings for the lead

- Develop shows unrelated papers for a named paper. `What is PMID 11237011?` on develop planned a PubMed search for the question's words and answered with five unrelated papers; the same happens to a two-paper question Think reads as a lookup (first-batch run A5). The cause is the topic search replacing develop's own record template. This card fixed it only where a checked shape is forced. A fix for the lookup case is outside the design's fences and the lead's call.
- Shape D is reached rarely. Think calls "What variants cause cystic fibrosis?" exploratory in most runs, develop's record template then applies, and the decision is never asked. Asking the decision when develop's only candidate is the disease record, and the planned class is open, would reach it. That changes what a plain condition question shows, so it is the owner's call; query 115 says so.
- Test query numbers collide. This slice uses 112 to 115 (the highest in this worktree is 111). Other worktrees hold 112 (card 24) and 113 (card 17). The lead renumbers on merge.
- A false "does not address" note. For slice C the answer says it does not address MSH2 although MSH2 variants are listed, and for slice B it says it does not address the paper. This is the existing entity coverage note; it is not changed here.
- Article rows read by id. Slice A's answer lists "Article record PMID:11237011" and not the title. The title is on the source card. Not changed here.
- No plain "the graph shows no link" sentence for an unlinked gene and paper (slice B). The answer never denies, but it does not say it either. Not changed here.
- Count questions. A near miss in the held-out checks for slices B and C picked the shape for a "how many" question. The result is a capped list, never a number or a record about another entity.
- Guardrail transient errors. Two of about 40 live runs ended with the guardrail's transient error (A first batch run 1, D branch run 4). Both are the provider, not these changes.
- Not written: the `DECISIONS.md` row and any frontend decision list; `plan.graph_shape` is not in `harness/task_tiers.py`, as `plan.paper_links` is not.

## Gates

- `ruff check` (no path): All checks passed.
- isort gate 2 command (`isort --check-only --diff src tests services tracker alembic .claude .github`): exit 0.
- `pytest tests/system_03_search_agent -m "not integration" -q`: 7021 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 260.77 s.
- `ruff format` was not run.

## Learnings

- A replace on `return shapes` hit `matched_shapes` first and broke 35 tests with a `NameError`. Fixed in under five minutes; edit by a unique anchor, not a common line.
- The shared machine ran at a load of 10 to 16 while other builders ran suites. Single live runs took 6 to 16 s but a five-run batch took many minutes of wall time. Run batches in the background and wait on the result file.
- A shell `sed -i` needs an empty backup argument on this machine; use a short Python replace for edits.
