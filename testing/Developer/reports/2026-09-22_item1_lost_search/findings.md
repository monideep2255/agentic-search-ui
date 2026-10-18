# Item 1: the two questions that lost their own graph search, and what a person gets now

Fix-plan item 1 as rewritten at the close of 2026-09-22: "Compare what is known about MLH1 and MSH2 in colorectal cancer risk" (golden G-033) and "Find GEO expression datasets studying TP53 in human tumour samples" (G-037) both answered from NCBI records and the literature, then ended with the line saying a background search did not finish. Their own graph search never reached the graph: with no recognisable shape the question took the model path, and the generated query failed the product's own validation on every pass. This folder holds what was measured before anything was written, the decision taken from the user's chair, and the live verification on develop.

## Table of contents

- [Verdict](#verdict)
- [What the person typing each question sees](#what-the-person-typing-each-question-sees)
- [Where the two searches were lost](#where-the-two-searches-were-lost)
- [What the graph holds for the two genes, measured](#what-the-graph-holds-for-the-two-genes-measured)
- [A third way of losing a search, found by probe](#a-third-way-of-losing-a-search-found-by-probe)
- [Which questions take which path, offline](#which-questions-take-which-path-offline)
- [GEO, the half the graph cannot answer](#geo-the-half-the-graph-cannot-answer)
- [What changed in the code](#what-changed-in-the-code)
- [Live verification on develop](#live-verification-on-develop)
- [Method and evidence](#method-and-evidence)

## Verdict

| Question | Before | After |
|---|---|---|
| Compare what is known about MLH1 and MSH2 in colorectal cancer risk | Its own graph search errored on 3 of 3 passes: no template matched, the model wrote a query naming a vertex label the graph does not have, and the reader was told a search did not finish | Each gene's disease edges, side by side, from a fixed template: six rows in 0.8 s, measured live |
| Find GEO expression datasets studying TP53 in human tumour samples | Its own graph search errored on 3 of 3 passes (a generated query binding a literal value), and no GEO dataset was ever searched for, so the person asking for datasets got none | The TP53 gene record from a fixed template in under a second, and a GEO DataSets search on the symbol with its summary, cited to NCBI's own record pages |
| Which diseases are associated with BRCA1 and BRCA2 (G-011) | Lost its search on the pass where Think resolved the word "diseases" to eight MedGen concepts beside the two genes | Takes the same two-gene disease template as its clean passes |
| Any question naming two genes with no shape word, on a lookup or exploratory class | Would have timed out at 30 s on the graph (the IN-list record form never finishes on the Gene label) | A UNION of single matches, 0.4 s |

Nothing else changed its path. The count class and the disease- or article-anchored questions with no shape keep the model path, each for a measured reason recorded in the code.

## What the person typing each question sees

Decided from the user's chair, the standing rule since the morning of 2026-09-22.

- A researcher comparing two genes in a disease context wants each gene's disease associations beside each other. Today they got an answer from NCBI records and papers with a line saying a search did not finish. Now the graph contributes both genes' condition records, cited, and the line is gone because the search finished.
- A researcher asking for GEO datasets wants dataset records they can open. Today they got a TP53 answer with no dataset in it and the same lost-search line, because the product never searched GEO. Now the answer carries GEO series for the symbol, each cited to NCBI's record page, and the graph search that used to fail returns the gene record instead.
- Honesty is preserved, not traded: no template here returns a record the question did not name. The two-gene template returns edges from the named genes; the record template returns the named gene; the GEO search is issued only when the question's own words ask for datasets, and its rows carry the organism so a mouse question is not silently answered with human data.

## Where the two searches were lost

Both failures were in `select_template` returning None. The consistency run's captures (`testing/Developer/reports/2026-09-22_10.3_consistency/raw/`) carry Think's resolved entities and class on every pass:

| Question | Pass | Class | Entities Think bound | Path | Own graph call |
|---|---|---|---|---|---|
| G-033 | 1, 2, 3 | exploratory | MLH1, MSH2, colorectal cancer (MedGen:C0346629) | mixed gene-plus-disease chooser, two genes, no shape word: None | error, 0 rows, every pass |
| G-037 | 1 | single_hop | TP53 | one Gene, no shape word, hop class: None | error, 0 rows |
| G-037 | 2 | multi_hop | TP53 | same | error, 0 rows |
| G-037 | 3 | exploratory | TP53 and eight MedGen concepts for "tumour" | mixed chooser, one gene beside several diseases, no shape: None | error, 0 rows |

The reasons the stream now carries (since the morning's change to `_execute_planned_call`) are the validator's: "Generated Cypher references vertex label" for G-033 and "appears to bind a literal value directly" for G-037. Following `attack-the-constraint`, the model was not the constraint and its generated text was not debugged: what it was given was a question with no shape word and no template, and the fix removes the model from both paths rather than instructing it better, the same move that made the plain-terms BRCA1 explanation fast that morning.

Also read: the record in `cypher_templates.py` gave G-011 as the reason to keep multi-hop questions on the model path ("a generated search finds rows the record would lose"). The captures show G-011's two answered passes bound two genes with the word "diseases" and took the `gene_diseases_many` template; only its lost pass reached the model, through the mixed chooser. The reason was mistaken and is corrected in the code.

## What the graph holds for the two genes, measured

Read-only probes through the repository's own `execute_cypher` over the HTTPS query service, each query passed through the validator first (`probe_record_forms.py`):

| Query shape | Rows | Time |
|---|---|---|
| Each gene's disease edges over MLH1 and MSH2 (`gene_diseases_many`) | 6 (MLH1: MedGen:C1321489, C1333991, C5399763; MSH2: C1321489, C2936783, C5436806) | 0.8 s |
| The link from either gene narrowed to the concept Think resolved for "colorectal cancer", MedGen:C0346629 | 0 | 0.55 s |
| TP53's disease edges | 12 | 0.47 s |

So the narrowed link, which is what the one-gene-one-disease form returns and what a naive generalisation would have produced, answers "nothing" for a question the graph can answer: MedGen carries dozens of colorectal cancer concepts, and the one Think happened to resolve is on neither gene's edges. The open hop over the named genes is the honest comparison material, and it is what the template now returns.

## A third way of losing a search, found by probe

The several-record form the record template used, `MATCH (a:Gene) WHERE a.id IN [...]`, never finishes on the live graph. Only the inline property match uses the id index on the Gene label; every WHERE on `a.id` walks the whole vertex table and dies at the reader role's 30-second statement timeout:

| Form | Result |
|---|---|
| `MATCH (a:Gene {id: $g1}) RETURN a` | 1 row, 0.68 s |
| `MATCH (a:Gene) WHERE a.id IN [$g1] RETURN a` (ONE id) | timeout, 30.5 s |
| `MATCH (a:Gene) WHERE a.id IN [$g1, $g2] RETURN a` (the old many form) | timeout, 30.5 s |
| `MATCH (a:Gene) WHERE a.id = $g1 OR a.id = $g2 RETURN a` | timeout, 30.5 s |
| `UNWIND [$g1, $g2] AS gid MATCH (a:Gene {id: gid}) RETURN a` | 2 rows, 0.84 s, but the tool's anchoring gate rejects it: the returned variable traces to an alias, not to a bound entity (`unanchored_result`) |
| `MATCH (a:Gene {id: $g1}) RETURN a ORDER BY a.id UNION ALL MATCH (a:Gene {id: $g2}) RETURN a ORDER BY a.id` | 2 rows, 0.42 s; validator and anchoring gate both accept it, each branch normalized with its own LIMIT |
| The same UNION over eight Disease ids | 8 rows, 0.44 s |
| `MATCH (a:Disease) WHERE a.id IN [eight ids]` | 8 rows, 0.95 s: the Disease label is small enough to scan, which is why `disease_record_many` had worked live |

No golden question reached `gene_record_many` in the consistency run, so this was never a measured failure there; it would meet anyone who typed "tell me about BRCA1 and BRCA2". The many-record form is now the UNION ALL of single matches, branches sorted by parameter name so Think's listing order cannot change the query or the row order. The hop templates keep their IN list: they join through the edge table, and the two-gene disease hop above ran in 0.8 s with it.

## Which questions take which path, offline

`offline_paths.py` replays every recorded Think output through the template chooser as it stands, beside what the question's own graph call returned on develop that morning. Before the change, 24 of 154 recorded runs took the model path, and on the single-hop and multi-hop classes it produced, in total: 8 errors (G-033 and G-037 on every pass, one pass each of G-006 and G-011), 11 empty results, and exactly one success with one row (G-006). Its only rich results were counts on the aggregate class (G-034). After the change, 17 runs take the model path, all of them the count class, a Disease or Article anchor with no shape, or a single entity of another label; the seven that moved are G-033 (three passes), G-037 (three) and G-011's junk-resolution pass. The full table is `offline_paths.md`.

What deliberately still takes the model path, with the measured reason:

- An aggregate question with no shape, because a count is something a record cannot give (G-034, one row on every pass).
- A Disease or Article anchor with no shape on the hop classes, because a disease list Think resolved from a common noun ("diseases", "tumour") would turn a correct refusal into a page of unrelated records (G-014, pass 3, eight MedGen concepts for a gene that does not exist). A gene symbol is live-confirmed before it is ever bound, which is why the widening is safe for genes and not yet for diseases.

## GEO, the half the graph cannot answer

The graph has no dataset vertex, so no template can return a GEO series, and the breadth plan searched PubMed, ClinVar and OMIM only. The person asking G-037 wants datasets. `ncbi_efetch` already accepts `gds` as a search and summary database and already carries a field allowlist and a record URL for it, so the addition is a plan, not a tool.

The search term was verified live against ESearch's own `querytranslation` (`probe_gds_search.py`):

| Term | Translation | Hits |
|---|---|---|
| `TP53[All Fields] AND gse[Entry Type]` (the term the plan issues) | identical | 1,569 series |
| `TP53[Gene Symbol] AND Homo sapiens[Organism]` | `TP53[All Fields] AND "Homo sapiens"[Organism]` (GDS has no symbol field) | 19,092 entries, most of them single samples |
| `BRCA1[All Fields] AND gse[Entry Type]` | MeSH-expanded, as PubMed does | 639 series |

Restricting to series (`gse[Entry Type]`) is what makes the hits datasets a person can open rather than the samples inside them. No organism clause, deliberately: a mouse question would be silently narrowed to human, and the summary rows carry `taxon` for the reader. The top three TP53 hits at the time were GSE346694, GSE346344 and GSE315234, each a human expression series with its sample count. The search is planned only when the question's own words ask for datasets (GEO, GDS, GSE, dataset, expression profiling, microarray, RNA-seq), so an ordinary gene question plans nothing new and stays at its measured 14 to 16 of 20 allowed calls; a dataset question reaches at most 18.

## What changed in the code

- `tools/cypher_templates.py`: `_mixed_gene_disease_template` returns each gene's disease hop for several genes with no shape or the diseases shape, and the gene record for one gene beside several disease concepts; `select_template` step 3 sends a gene question with no shape on the single-hop and multi-hop classes to the record; `_record_template`'s several-record form is a UNION ALL of single matches in parameter order. The comment that gave G-011 as the reason for the old gate is corrected.
- `core/breadth_plan.py`: `wants_dataset_search`, `build_gds_term`, a `datasets` keyword on `plan_first_stage`, and `plan_gds_follow_up`.
- `core/graph.py`: the `gds_search` to `gds_summary` follow-up, the `datasets` flag set from the question text at plan time, the follow-up dispatch branch, and the `gds_summary` row fields (title, accession, dataset type, organism, sample count).
- Tests moved with the behaviour and say so: the two rows that pinned the model path for these shapes now pin the templates; the three call-count arms in `test_graph.py` and the unknown-shape arm in `test_cypher_query_templates.py` exercise the model path on the aggregate class instead; new arms pin the UNION form, the two-gene template, the one-gene-many-diseases record, the count refusal, the dataset words, the GEO term, the planned pair and a dataset question reaching the answer with GEO series cited.

## Live verification on develop

Twelve signed-in runs against develop at `b6cd025` (deployed 21:41 UTC), one worker, the laptop held awake, through `run_consistency.py` from the consistency run: three passes each of the three questions whose path changed, and of G-012 as a control whose path did not change (a disease anchor with no shape word, left on the model path by the decision above). The first six runs used one of the morning's accounts; the next six came back `capped`, that account's daily allowance having been spent by the morning's 150-run measurement. Those six records are kept in `runs_capped.jsonl` with their captures in `raw_capped/`, and the six (question, pass) pairs were re-run on a fresh test account, which is what `runs.jsonl` holds.

| id | pass | outcome | seconds | own graph call | graph calls errored | trust | sources by layer | GEO cited |
|---|---|---|---|---|---|---|---|---|
| G-011 | 1 | answered | 22.2 | ok 13 rows | 0 | ask | L1 42, L2 30, L3 10 | 0 |
| G-011 | 2 | answered | 18.1 | ok 13 rows | 0 | ask | L1 42, L2 30, L3 10 | 0 |
| G-011 | 3 | answered | 18.0 | ok 13 rows | 0 | ask | L1 42, L2 30, L3 10 | 0 |
| G-012 | 1 | refused_no_evidence | 27.8 | empty 0 rows | 0 | refuse | none | 0 |
| G-012 | 2 | refused_no_evidence | 14.2 | empty 0 rows | 0 | refuse | none | 0 |
| G-012 | 3 | refused_no_evidence | 95.1 | error 0 rows: call did not complete within its per-step timeout budget | 1 | refuse | none | 0 |
| G-033 | 1 | answered | 30.2 | ok 7 rows | 0 | ask | L1 8, L2 24, L3 10 | 0 |
| G-033 | 2 | answered | 18.1 | ok 7 rows | 0 | ask | L1 8, L2 24, L3 10 | 0 |
| G-033 | 3 | answered | 30.3 | ok 7 rows | 0 | ask | L1 8, L2 24, L3 10 | 0 |
| G-037 | 1 | answered | 22.1 | ok 1 rows | 0 | ask | L1 60, L2 24, L3 10 | 5 |
| G-037 | 2 | answered | 13.3 | ok 1 rows | 0 | flag | L1 60, L2 24, L3 10 | 5 |
| G-037 | 3 | answered | 19.8 | ok 1 rows | 0 | flag | L1 60, L2 24, L3 10 | 5 |

Read against the verdict:

- G-033, the two-gene comparison: 3 of 3 answered, the question's own graph call returning the `gene_diseases_many` rows every pass (seven rows live: each gene beside each of its conditions), zero errored graph calls, so no lost-search line and no trust floor from a failed search. The same source set on every pass, 8 graph, 24 live NCBI, 10 literature and trials. 18 to 30 seconds.
- G-037, the dataset question: 3 of 3 answered, the own call returning the TP53 record, and five GEO series cited on every pass, the same five (GEO DataSets uids 200305791, 200310906, 200315234, 200346344 and 200346694, each cited by its title to `ncbi.nlm.nih.gov/gds/{uid}`), with 15 tool calls in the plan where the plain gene question has 13. 13 to 22 seconds.
- G-011, the two-gene disease question: 3 of 3 with 13 rows on its own call and an identical source set each pass; its junk-resolution shape did not recur in these three passes, and the offline table shows where it now lands when it does.
- G-012, the control, is unchanged from the morning: 0 of 3 answered here against 1 of 3 then, on a disease anchor with no shape word that still takes the model path by decision. Its third pass lost the generated query to the per-step timeout after 95 seconds, which is the variance half of L-01 on the class this change deliberately did not touch, and it is the next place the same fix would apply once Think's resolution of a common noun into a list of concepts is handled.
- Item 11.22, checked on the same captures with `check_1122.py`: abstract text of 220, 433 and 220 characters from three papers appears verbatim in the answer, each cited to its paper (PMIDs 28976962, 34421362, 35432218). The check reads the abstract from NCBI, not from the product.
- Zero rate-limit signals across the twelve runs.

Not verified live here, and said so: the UNION ALL record form was exercised by the probes above and by the unit suite, not by a golden question in these runs, because none of the twelve passes classified a several-record question as lookup or exploratory.

CI did not run on the two pushes: GitHub reports every job "was not started because recent account payments have failed or your spending limit needs to be increased", a billing setting for the product owner, after a green run on `02063b0` twenty minutes earlier. The four gates CI would have run were run locally with CI's own commands before the push: `ruff check` over the whole repository, `isort` per gate 2, and the full unit suite, 5176 passed and 0 failed.

## Method and evidence

| File | What it is |
|---|---|
| `offline_paths.py`, `offline_paths.md` | The replay of every recorded Think output through the current template chooser, beside the morning's outcome |
| `probe_record_forms.py` | The read-only timing probes above, re-runnable with the graph credentials in `.env` |
| `probe_gds_search.py` | The live GEO term check, three E-utilities requests a second apart |
| `runs.jsonl`, `raw/` | The twelve live verification runs, written first as they end, and every event but tokens of each |
| `runs_capped.jsonl`, `raw_capped/` | The six runs the morning account's daily allowance declined, kept rather than dropped, and re-run on a fresh account into `runs.jsonl` |
| `summarize_live.py` | The table above, computed from the two files |
| `check_1122.py` | The item 11.22 check: abstract text fetched from NCBI, matched against the captured answers |
