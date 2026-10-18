# Adversary report: card 38 slice B, orthologs with species

Pull request #265, branch `fix/card38-orthologs-with-species`, commit `dfdc27c0` on develop `655e9dfe`. Adversary worktree `<worktrees>/card38b-adv` (detached), develop comparison worktree `<worktrees>/card38b-adv-dev`. Probes in `<scratchpad>/card38b_adv/`. Every graph query below was a read.

The lead's decision under test: TP53's orthologs carry their species through an `in_taxon` fold, keeping the 591 total; every other answer unchanged.

## Table of contents

- [Findings](#findings)
- [Spend](#spend)
- [Verdict](#verdict)

## Findings

### A-38B-01: The branch's ortholog query runs on the live graph, keeps 591 and 514, and adds no row or wrong species in the first 100

- Severity: none (evidence; holds)
- Worse than develop: no
- What: `<scratchpad>/card38b_adv/tool_probe.py` calls `cypher_query` (the product's tool, template path, plan tier refused) on each tree, with `execute_cypher` wrapped only to time each call. Pasted, branch then develop then branch again:
  ```
  branch NCBIGene:7157 ok gene_orthologs_one rows 100 total 591 trunc True t 13.93 ['orthologous_to']   (main 8.38 s cold, count 5.47 s)
  branch NCBIGene:672  ok gene_orthologs_one rows 100 total 514 trunc True t 10.95 ['orthologous_to']   (main 5.88, count 5.05)
  dev    NCBIGene:7157 ok gene_orthologs_one rows 100 total 591 trunc True t 10.32 ['orthologous_to']   (main 5.35, count 4.95)
  dev    NCBIGene:672  ok gene_orthologs_one rows 100 total 514 trunc True t 10.1  ['orthologous_to']   (main 5.10, count 4.98)
  branch NCBIGene:7157 ok gene_orthologs_one rows 100 total 591 trunc True t 10.33 ['orthologous_to']   (main 5.20, count 5.11)
  branch NCBIGene:672  ok gene_orthologs_one rows 100 total 514 trunc True t 10.62 ['orthologous_to']   (main 5.28, count 5.31)
  ```
  The count query the branch sends: `MATCH (a:Gene {id: $e_NCBIGene_7157})-[:orthologous_to]->(x:Gene) OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count LIMIT 1`, returned 591. The 100 row CURIEs and names are identical, in order, to develop's for both genes; every row carries one organism, 100 distinct species per gene, none "Homo sapiens", edge type still `orthologous_to`.
- First ten TP53 rows, branch tool output: 100009292 Oryctolagus cuniculus; 100049321 Oryzias latipes; 100062044 Equus caballus; 100092821 Ornithorhynchus anatinus; 100136737 Oncorhynchus mykiss; 100304476 Ictalurus punctatus; 100379269 Cavia porcellus; 100415710 Callithrix jacchus; 100435218 Pongo abelii; 100468516 Ailuropoda melanoleuca. The species come from the graph's own `in_taxon` edge; I did not check them against NCBI Gene's pages.
- Time: on a warm connection the two queries add 0.0 to 0.5 s over develop (10.33 against 10.32 s for TP53, 10.62 against 10.1 s for BRCA1). The first branch call, 8.38 s, was a cold connection; the second branch pass did not repeat it.
- Holds

### A-38B-02: Graph facts behind the species: every TP53 and BRCA1 ortholog has exactly one `in_taxon` edge, to an `OrganismTaxon` at species or subspecies rank, never human, never the gene itself

- Severity: none (evidence; holds)
- Worse than develop: no
- What: `<scratchpad>/card38b_adv/graph_facts.py` and `graph_facts2.py`, read-only aggregates over ALL orthologs, not just the first 100. Pasted:
  ```
  NCBIGene:7157 edges_vs_distinct [[591, 591]]  taxon_edge_hist [[1, 591]]  organismtaxon_hist [[1, 591]]
                sapiens_or_self []  one_word_names []  tail_after_500: 91 rows, null names 0, sapiens []
                anchor_taxon [['NCBITaxon:9606', 'Homo sapiens']]
  NCBIGene:672  edges_vs_distinct [[514, 514]]  taxon_edge_hist [[1, 514]]  organismtaxon_hist [[1, 514]]
                sapiens_or_self []  one_word_names []  tail_after_500: 14 rows, null names 0, sapiens []
  first 500 of each: labels ['OrganismTaxon'] only; longest name 43 characters, "Neophocaena asiaeorientalis asiaeorientalis"
  ```
  So no ortholog has two taxa, no taxon is a genus or a class such as "Mammalia" (no one-word name), the human anchor never appears as its own ortholog, and `count(e) == count(DISTINCT x)`, so the branch's grouped count (one per ortholog) and develop's raw `count(*)` (one per edge) agree on these genes.
- Other genes through the tool on the branch: mouse Trp53 (NCBIGene:22059), MIR21 (406991) and XIST (7503) return `empty`, 0 rows, total 0, in 5.0 to 5.1 s, one query each, no error. CFTR (1080) returns 100 rows, total 785, every row with one species ("Gallus gallus" for 100049619).
- Holds

### A-38B-03: Live end to end, TP53 and BRCA1 ortholog questions show each ortholog's species at both depths, keep develop's count line, and stay within a second of develop

- Severity: none (evidence; holds)
- Worse than develop: no
- What: `<scratchpad>/card38b_adv/live.py` through `core.run.run_streaming()`, web surface, develop's settings (classifier provider jev, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`), session ids `card38b-adv-<label>`. Five runs on the branch tree, one on develop's. Summaries by `summ.py`, pasted:

| Run | First ten listed orthologs | Count line | Trust line | Done at |
|---|---|---|---|---|
| Branch, TP53, Researcher | Table header `Gene, Identifier, Organism`. tumor protein p53: NCBIGene:100009292 Oryctolagus cuniculus; 100049321 Oryzias latipes; 100062044 Equus caballus; 100092821 Ornithorhynchus anatinus; 100136737 Oncorhynchus mykiss; 100304476 Ictalurus punctatus; 100379269 Cavia porcellus; 100415710 Callithrix jacchus; 100435218 Pongo abelii; 100468516 Ailuropoda melanoleuca | "Found 41 gene records for TP53, of 715 available" and "Note: this answer was truncated because only 159 of the 715 records ..." | "Based on 58 sources cited" (answer) | 22.01 s |
| Develop, TP53, Researcher | Header `Gene, Identifier`; the same ten ids in the same order, no species | "Found 40 gene records for TP53, of 715 available", the same truncation note | "Based on 57 sources cited, not yet confirmed" (ask) | 21.28 s |
| Branch, TP53, Plain language | "tumor protein p53 (Oryctolagus cuniculus)", "(Oryzias latipes)", "(Equus caballus)", "(Ornithorhynchus anatinus)", "(Oncorhynchus mykiss)", "(Ictalurus punctatus)", "(Cavia porcellus)", "(Callithrix jacchus)", "(Pongo abelii)", "(Ailuropoda melanoleuca)" | "I found 41 genes related to TP53, out of 715 available", truncation note 159 of 715 | "Based on 58 sources cited, not yet confirmed" (ask) | 18.99 s |
| Branch, BRCA1, Researcher | BRCA1 DNA repair associated: 100049662 Sus scrofa; 100051990 Equus caballus; 100224649 Taeniopygia guttata; 100347269 Oryctolagus cuniculus; 100388186 Callithrix jacchus; 100439533 Pongo abelii; 100480891 Ailuropoda melanoleuca; 100553919 Anolis carolinensis; 100580360 Nomascus leucogenys; 100653763 Loxodonta africana | "Found 40 gene records for BRCA1, of 554 available", truncation note 140 of 554 | "Based on 57 sources cited, not yet confirmed" (ask) | 22.91 s |
| Branch, BRCA1, Plain language | "BRCA1 DNA repair associated (Sus scrofa)" and the same nine species as Researcher, same order | "I found 40 genes related to BRCA1, out of 554 available", truncation note 140 of 554 | "Based on 57 sources cited, not yet confirmed" (ask) | 18.39 s |
| Branch, control "Which diseases are associated with BRCA1?", Researcher | Disease table `Disease, Identifier`: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, Fanconi anemia complementation group S; Gene table `Gene, Identifier` (no Organism column) | "Found 4 disease records for BRCA1: ..." plus a written sentence for each | "Based on 21 sources cited, not yet confirmed" (ask) | 9.68 s |

- No listed ortholog reads "Homo sapiens" in any run; no row reads "of unknown"; no run errored.
- The "of 715" and "of 554" are develop's own totals for the whole answer (each run made two graph calls; 715 and 554 exceed the ortholog totals 591 and 514); develop shows the identical 715. The branch keeps it, which is what the count gate change was for. A person still never sees "591" on either tree (pre-existing, not this card's).
- Time: the ortholog graph call took 10.10 s on develop (tool start 3.94 s, result 14.04 s) and 10.44 s, 10.49 s, 10.21 s, 10.46 s on the four branch ortholog runs. Done event 22.01 s against develop's 21.28 s on the same question and depth, +0.73 s, inside "about a second"; the tool level probe in A-38B-01 gives 0.0 to 0.5 s warm.
- Rows: branch TP53 Researcher listed 40 orthologs plus human TP53 (41 gene records), develop 39 plus TP53 (40). The extra row is NCBIGene:102101491, Pseudopodoces humilis, a real ortholog from the same 100. The PubMed rows differ by one paper between the runs (live API variance). Nothing develop listed is lost apart from that live paper.
- Holds

### A-38B-04: The branch TP53 Researcher run reached "answer" with no written sentence on screen, but the writer never sees a species, so this is the writer's run to run variance on develop's own path, not the card

- Severity: unsure (evidence; holds)
- Worse than develop: no
- What: in the first branch run (before my prompt spy was added) the writer's sentences grounded and were then all dropped as one record restatements (`core/graph.py:14731` to `:14735`), so no fallback note fired and the trust line read "Based on 58 sources cited" with only the list on screen. Develop's run of the same question took the structured fallback (note plus "not yet confirmed"), and so did the branch's Plain language TP53 run and both BRCA1 ortholog runs. Both paths exist on develop.
- Why it is not the card: from the second run on, `live.py` wraps `build_synth_messages` and logs whether the writer's prompt carries any species word. Pasted, all eight prompt builds across the four instrumented runs: `"mentions_species": []` (checked words "Oryctolagus", "Oryzias", "Equus caballus", "Sus scrofa", "organism"). `build_synth_findings` emits one finding per row from `name` (`_EXPLANATORY_FIELDS` is only `summary`, `synthesis/findings.py:128`), so the organism field never reaches the writer, the grounding gate or the trust verdict. One run per tree cannot show a rate; it shows the branch cannot steer it.
- Holds

### A-38B-05: Human TP53's own row now sits in a table with an Organism column and shows that cell blank

- Severity: minor
- Worse than develop: no (develop has no Organism column at all, so the human row's species was never shown; nothing develop showed is lost)
- What: branch TP53 Researcher, Gene table row 41: `['TP53', 'NCBIGene:7157', '']`, between the orthologs and the papers. This is the Layer 2 gene record (citation layer `layer_2_api`, source `gene`, NCBI Gene 7157), not a graph `Gene` row, and the closed table keys on the exact graph type `Gene` (`synthesis/answer_layout.py:629`), so its Organism cell is blank. A researcher scanning a species column sees every ortholog named and the one human record with no species. Not wrong, only silent where "Homo sapiens" would help. Plain language reads just "TP53" for it, as on develop.
- Not a finding against the decision: the lead's decision covers orthologs only.

### A-38B-06: Routing and shape hunts: homolog questions share the template as on develop, paralog questions never reach it, two gene questions keep develop's species free template

- Severity: none (evidence; holds)
- Worse than develop: no
- What: the shape regex `"orthologs": r"\b(ortholog|orthologs|orthologous|homolog|homologs|homologous)\b"` (`tools/cypher_templates.py:222`) is outside the diff (`git diff origin/develop...HEAD -- src/system_03_search_agent/tools/cypher_templates.py` touches only lines 134 to 175 and the new branch at `:623`). So "homologs of TP53" already took `gene_orthologs_one` on develop and now gains species, which is correct for orthologs listed as homologs; "paralogs" matches no alternative and is routed as on develop. A two gene ortholog question takes `gene_orthologs_many`, which the branch leaves byte-identical (the builder's hash test over the other 45 templates), so it lists no species, as on develop.
- The worst case Plain language label is CFTR's ortholog in "Neophocaena asiaeorientalis asiaeorientalis": 97 characters, shorter than the paper titles the same Plain language lists already wrap (for example the 145 character title "New surveillance guidelines for Li-Fraumeni ..." in the TP53 run). TP53's longest shown Plain language label is 50 characters, "tumor protein p53 (Trichechus manatus latirostris)". No phone layout risk beyond what develop already wraps.
- Tests on the branch: `PYTHONPATH=src python -m pytest -q tests/system_03_search_agent/tools/test_cypher_ortholog_organism.py tests/system_03_search_agent/synthesis/test_answer_layout.py` gives `131 passed in 7.02s`.
- Holds

## Spend

Six live runs, total reported by the done events: $0.0108 + $0.0105 (develop) + $0.0063 + $0.0094 + $0.0048 + $0.0099 = about $0.052, under the $0.75 allowance. The tool and graph probes call no model. Four first attempts failed in argument parsing before any import of the product (a shell quoting slip), so they spent nothing.

## Verdict

Nothing on the branch shows a person anything worse than develop. Every TP53 and BRCA1 ortholog in the graph has exactly one species level taxon, none human; the query runs live in the same time as develop's within half a second at the tool and 0.73 s end to end; the totals 591 and 514 survive at the tool and the screen's count line is develop's own; other questions keep develop's tables. One minor gap (A-38B-05, a blank Organism cell on the human gene's own row) is not a loss.

VERDICT: PASS
