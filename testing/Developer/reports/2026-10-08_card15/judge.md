# Card 15 judge report, round 1

Base: 24b20e7d307ad43483548d424ca7578fd7a1fbe3 on fix/card15-checked-graph-searches. Judge: independent, read and run only.

## Findings

### J-15-01: a graph-only question now gets the "nothing found" refusal for a search that never ran, and query 110 promises live answers the plan never asks for

- Severity: major
- What: for a question whose only planned call is the graph (a GO term, a MeSH term, two PMIDs with no gene, unless the literature classifier fires), the new `empty` result (`cypher_query.py:1973` to `1974`, `_no_checked_search_output`) is the only finding, so Write classifies the run `empty` (`core/graph.py:8924`) and refuses with `REFUSE_MESSAGE`, "I could not find grounded evidence for this", which `synthesis/refuse.py:44` documents as true only when "Nothing failed and nothing was found". Here nothing was searched. Query 110's third bullet says the GO term and two-paper questions "answer from the live NCBI sources"; the plan builder plans no live call for them.
- Evidence: my probe calling Plan's own builders on the branch, with the entities Think binds:
  - `Which genes take part in GO:0006281?`: first gene None, first disease None, layer calls [], breadth calls [], gene summary [].
  - `Compare PMID 11237011 and PMID 11237012`: the same, all [].
  - `Which papers are tagged with MeSH D001943?`: the same, all [].
  The topic path (`core/graph.py:6810`) runs only when no CURIE resolved or the literature classifier says `wants_literature`, so a GO question normally plans the graph call alone. Routing probe, branch: these three route `NO_SEARCH(empty)`; develop: `MODEL_WRITTEN`.
- Why it matters: a person asking which genes take part in a GO process is told no grounded evidence exists, which reads as "there is nothing on this"; the graph holds `participates_in` edges for that term. The test query added in this change will fail its own third bullet when the owner runs it. Not run live (no model calls), so the final screen text is inferred from code, not observed.
- Smallest fix: either give the no-search case its own Write wording that says the graph has no checked search for this kind of question and what to type next (the refusal rule), or correct query 110's third bullet to state what the person actually sees. Both are cheap; the second alone leaves the misleading refusal.
- NOT FIXED

### J-15-02: the several-variant conditions search uses the id IN list this module documents as a table scan

- Severity: minor
- What: `sequencevariant_diseases_many` is built by `_hop_template`'s several-anchor form, `MATCH (a:SequenceVariant)-[:has_phenotype]->(x:Disease) WHERE a.id IN [$e_ClinVar_17661, $e_ClinVar_12345] RETURN a, x ORDER BY a.id, x.id LIMIT 100` (printed by my probe). `_record_template`'s own docstring (`cypher_templates.py:702` onward) records that any WHERE on `a.id` walks the whole vertex table and that the inline match is the indexed form. The build note measured this one at 5.21 s against 0.42 s for the one-variant form, and an absent variant's count form at 4.45 s.
- Evidence: probe output above; build note table "The variant's conditions". Parameterized, read-only, LIMIT 100 and the shared timeout all hold (validator `ok True`, `execute_cypher` sets `statement_timeout`, `graph_connection.py:620`).
- Why it matters: a person comparing up to ten variants waits on a scan that grows with the label, against the 20 second answer guide; the indexed form is already written elsewhere in this file. Unsure whether it degrades under load; not measured.
- Smallest fix: a UNION ALL of one inline match per variant, the form `_record_template` uses, or leave it and record the measured ceiling.
- NOT FIXED

### J-15-03: the run's own record shows a graph search that returned nothing, for a search that never ran

- Severity: minor
- What: Act builds the call's stream summary from row counts and appends `output.error` only when `status == "error"` (`core/graph.py:8389` and `8399` to `8400`). The no-search result is `empty` with the reason in `error`, so the tool frame, the developer instrument and the deploy log read "0 row(s) of 0" and drop `NO_CHECKED_SEARCH_MESSAGE`. The comment at `cypher_query.py:1486` to `1491` says the reason is there "so a run log says why the graph returned nothing"; my sweep found no reader of the structured `error` field in `core/graph.py` or `synthesis/` (grep for `get("error")` and `["error"]` returned nothing), so no log carries it.
- Evidence: code read plus the grep above; not run end to end.
- Why it matters: anyone diagnosing a later report sees "the graph found nothing" where the truth is "the graph was not asked", the L-01 confusion this summary was fixed for, in the other direction.
- Smallest fix: append `output.error` to the summary for `empty` too when it is set, or give the summary its own "not searched" wording.
- NOT FIXED

### J-15-04: the gate on a model-written search is a regex over the question's words, so a count asked in other words or another language loses it

- Severity: minor (unsure)
- What: `written_search_allowed` is `_wants_count` (`cypher_templates.py:798`, `258` to `263`): "how many" anywhere in the raw question, or "count" or "number of" on an aggregate. It is the existing test, not a new list, which the brief asked; but it is now the only thing standing between a count question and no graph count. "Wie viele Varianten hat BRCA1 und BRCA2?" or "What is the total of variants in BRCA1 and BRCA2?" are counts that fail the regex, so with several anchors they now take no graph search where develop wrote one. G-050 already asks a question in German.
- Evidence: patterns at `cypher_templates.py:252` to `255`; my routing probe confirms "How many ..." routes `MODEL_WRITTEN` on the branch and non-matching phrasing routes `NO_SEARCH(empty)` for the same several-anchor shape.
- Why it matters: a person asking for a number in different words gets no graph count. The house rule is that decisions go to a classifier and code only verifies.
- Smallest fix: none needed for this card if the owner accepts D5's "true count" as the existing test; record it as a known limit in the build note.
- NOT FIXED

### J-15-05: three comments still say no template means the model path runs

- Severity: minor
- What: now false in code: `cypher_query.py:1955` to `1956` "When no template matches, the model path below runs exactly as before."; `cypher_templates.py:384` "so those go to the model path"; `cypher_templates.py:407` to `408` "More than that: None, the model path."; and `harness/task_tiers.py:91` "only when no fixed template matches".
- Evidence: grep output for "model path" in the two modules.
- Why it matters: the next builder reading the pipeline will believe a None template still writes a search.
- Smallest fix: one clause each naming the true-count gate.
- NOT FIXED

### J-15-04 correction: the examples that show it

- My first examples in J-15-04 were wrong: two GENES with a variants word route to `gene_variants_many` or `gene_record_many` on develop and on the branch alike, so they lose nothing. The shape that does lose its count is several Disease or Article anchors with no shape word on `aggregate`. Probe output, develop then branch:
  - `How many records mention Marfan syndrome and Ehlers-Danlos syndrome?` (two MedGen): `MODEL_WRITTEN`, then `MODEL_WRITTEN`.
  - `Wie viele Einträge erwähnen Marfan-Syndrom und Ehlers-Danlos-Syndrom?` (same two): `MODEL_WRITTEN`, then `NO_SEARCH(empty)`.
  - `What is the total of records mentioning PMID 11237011 and PMID 11237012?` (two PMID): `MODEL_WRITTEN`, then `NO_SEARCH(empty)`.
- Severity unchanged: minor, unsure.

### J-15-01 addendum: the refusal sentence, traced

- `write_node` picks the sentence with `refusal_message_for(failed_searches, topic_search_term, paper_link_none)` (`core/graph.py:13850` to `13854`). The no-search result is `empty`, so it is not in `failed_searches`, and with no topic term and no paper-link plan the function falls through to `return REFUSE_MESSAGE` (`synthesis/refuse.py:239`): "I could not find grounded evidence for this. Try NCBI's cross-database search:" plus the fallback link. On develop the same question either got rows from the written search or, when it failed, `FAILED_SEARCH_MESSAGE` ("One of my searches did not finish"), which was true. Read, not run live.

## What a person loses

From my routing probe over develop (`git archive origin/develop`) and the branch, with the entities Think would bind (assumed, not observed from a live Think):

| Question shape | Develop | Branch | Live calls still planned |
|---|---|---|---|
| A GO, MeSH or HP term alone (`Which genes take part in GO:0006281?`, `Which papers are tagged with MeSH D001943?`) | written search | none | none: refusal, J-15-01 |
| Two PMIDs, no shape, not lookup (`Compare PMID 11237011 and PMID 11237012`) | written search | none | none unless the literature classifier fires |
| A gene with a paper (`Does PMID 11237011 discuss BRCA1?`) | written search | none | the gene's full live fan-out |
| Several Disease concepts, hop class or no-count aggregate (`Any trials for reflux disease?` binding several MedGen ids) | written search | none | the disease's literature and trials |
| Several variants, no shape, hop class; a variant with an organism or a disease | written search | none | dbSNP and LitVar2 only when an rs id is typed |
| Two genes with a disease on the variants shape (`Variants in MLH1 and MSH2 causing Lynch syndrome`) | written search | none | both genes' live fan-out |
| One Disease, no shape (`What phenotypic features are associated with Marfan syndrome?`, `What is linked to Marfan syndrome?`) | written search | that disease's record | unchanged |
| One variant or one organism | written search | its record, or the new conditions hop | unchanged |

Unchanged on both (probe): queries 21 (`gene_diseases_one`), 24 (`gene_diseases_many`), 25 (`gene_record_one`), 64 (`article_mesh_one`), 78 (`disease_genes_one` and `_many`), 79 (`gene_variant_diseases_one`), 87's breast cancer count with one concept (`disease_genes_one_count`).

Test queries in `testing/Test_queries_and_workflows.md` at risk:

- Query 110, third bullet, added in this change: the GO term and two-paper questions will refuse rather than "answer from the live NCBI sources" (J-15-01).
- Query 66 (deliberately open): its recorded plain-language answer, "Found 1 disease record, 37 sequence variant records and 3 gene records", was the written search; it now gets the disease record only. Query 81 calls the old answer "a confident answer of the wrong kind", so this reads as a gain. No pass criterion flips.
- Query 68 (`reflux disease` after the ask-back): when Think binds several MedGen concepts on a hop class, the graph now contributes nothing, but the disease's literature and trials calls are still planned, so it should still answer with cited records. Not run live; could not verify.
- Query 87 (`Which syndromes feature arachnodactyly?`): if Think binds an HP id alone, the plan is graph only and it now refuses; if MedGen, the disease path plans live calls. Its pass criteria (no "MedGen lists no clinical features" sentence) still hold either way. Could not verify which binding Think makes.

## Security and production standards

- Parameterized only: the three new forms validated through `validate_cypher` and `_check_entity_binding` with `ok True`, every id a `$e_...` parameter (probe output in J-15-02). No string built from model text: `_pattern` interpolates only labels and edge names from `_HOPS`, which are asserted against the graph constants at import (`_assert_templates_name_real_labels`, mutation M5 below errors at import).
- Read-only: the validator's forbidden-clause list and the `kg_reader` role (`graph_connection.py:68`); unchanged by this branch.
- Timeout: the template path shares `remaining_budget` into `execute_cypher(timeout_s=...)` (`cypher_query.py`, unchanged), which sets `statement_timeout` (`graph_connection.py:620`); the outer `asyncio.wait_for` at `CYPHER_QUERY_TIMEOUT_SECONDS` wraps all of it.
- No new model call; the no-search path makes no plan-tier call and no graph call (pipeline tests, and M1 below).

## Sweep for model-written Cypher

`generate_cypher` has one caller, `_generate_and_validate` (`cypher_query.py:1272`), which has one caller, the `candidate is None` branch of `_run_pipeline` (`cypher_query.py:2002` onward), reached only past the new gate at `cypher_query.py:1973`. `cypher_query(` is called only from `core/graph.py:8320` and `8322`. The only other `execute_cypher(` callers are `export/traversal.py:558` and `801`, which run fixed code-built Cypher with `params={"seed_id": ...}`. No other path reaches a model-written query.

## Break it, does a test go red

Each mutation applied by script to the working tree, the three changed test files run, the file restored from a copy. Pasted:

| Mutation | Result |
|---|---|
| M1 gate off (`if False and ...`) | 6 failed, 147 passed, 1 skipped |
| M2 no-search status `error` | 6 failed, 147 passed, 1 skipped |
| M3 count test replaced by `query_class is AGGREGATE` | 5 failed, 148 passed, 1 skipped |
| M4 record fallback for several entities | 16 failed, 137 passed, 1 skipped |
| M5 variant hop direction `in` | 3 errors (import assertion) |
| M6 record fallback taken before the count check | 6 failed, 147 passed, 1 skipped |
| M7 OrganismTaxon removed from `_TEMPLATED_LABELS` | 4 failed, 149 passed, 1 skipped |
| M8 no-search `error=None` | 6 failed, 147 passed, 1 skipped |
| M9 count test reduced to "how many" only | 2 failed, 151 passed, 1 skipped |
| M10 gate on `forced_template is None` | 8 failed, 145 passed, 1 skipped |

`git diff --stat HEAD` after restore: empty (printed `[]`).

## Runs

| Run | Result, pasted |
|---|---|
| The three changed test files | 153 passed, 1 skipped in 6.94s |
| `tests/system_03_search_agent/tools` | 1688 passed, 99 skipped, 3 warnings in 29.27s |
| `tests/system_03_search_agent/core` | 1385 passed, 56 skipped, 2 warnings in 63.78s |
| `ruff check` on the five touched Python files | All checks passed! |

No live model call and no graph query was made by this judge.

## Verified by my own probes versus read

- Probed: routing on develop and branch for 39 question shapes; the new Cypher forms and their validation; that Plan plans no live call for GO, MeSH and two-PMID questions; every control's test goes red when broken; the suite counts.
- Read only: the refusal sentence Write picks (J-15-01 addendum); the Act summary dropping the reason (J-15-03); the read-only role and statement timeout; the build note's live timings (5.21 s, 0.42 s), which I did not re-measure.

## Verdict

FIX FIRST: J-15-01 (major). J-15-02 to J-15-05 are minor and may ride along or be filed.

