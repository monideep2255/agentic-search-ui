# Fresh verifier report: card 38 slice B, orthologs with species

Pull request #265, branch `fix/card38-orthologs-with-species`, one commit `dfdc27c0` on develop `655e9dfe`. Verifier worktree `<worktrees>/card38b-ver` (detached at the head), develop comparison worktree `<worktrees>/card38b-ver-dev` (detached at `655e9dfe`, removed when done). Probes in `<scratchpad>/card38b_ver/`. Graph reads only, through the product's own `cypher_query` tool. Every verdict below is re-derived; the judge's and adversary's reports were read, not relied on.

The lead's decision: "B (TP53's orthologs carry their species through an `in_taxon` fold, keeping the 591 total)."

## Table of contents

- [Findings](#findings)
- [Evidence log](#evidence-log)
- [Verdict](#verdict)

## Findings

### V-38B-01: The acceptance line "the answer still says 591" is met at the tool, not on screen, on both trees

- Severity: minor
- Worse than develop: no
- What: `total_available` is 591 for TP53 and 514 for BRCA1 on the branch, equal to develop (tool probe, evidence log). On screen, both TP53 runs say "Found 40 gene records for TP53, of 715 available" (Researcher) and "I found 40 genes related to TP53, out of 715 available" (Plain language), and no "591" appears anywhere in either answer. The adversary's saved develop run of the same question reads the identical "of 715". So the branch keeps develop's count line exactly, which is what the count gate change protects, but a person never sees 591 on either tree.
- Why it matters for the lead: the diagnosis's proposed query 115 says "The answer still says how many orthologs the knowledge graph holds, 591 for TP53, against how many are shown." Filed as written, that line fails the owner's retest on this branch and on develop alike. Word it to what the screen shows, or queue the count line as its own card. Not a defect of this branch.

### V-38B-02: Two length caps can be exceeded in principle, far beyond anything the graph holds

- Severity: minor
- Worse than develop: no for any person today
- What: `cells` items are capped at 500 characters by the contract (`contracts/events.py:428`) and `sentence_token` does not clip them (`core/graph.py:13163` to `:13184`). The plain label `f"{label} ({organism.strip()[:100]})"` (`synthesis/answer_layout.py:1035`) exceeds 500 when the gene name is 477 characters or more; the Researcher Organism cell exceeds 500 for one taxon name over 500 characters, because `_clip_terms` keeps a first term whole and `_fold_value_names` (`tools/cypher_query.py:1843` to `:1879`) caps the item count but not a name's length. Offline probe output in the evidence log: 477 gives a ValidationError, 476 is valid. No test pins the 100 character suffix cut (mutation V3 stays green).
- Reach: 800 live ortholog rows over eight genes give a longest name of 51, a longest species of 30 and a longest plain label of 72 characters; the adversary's aggregate over every TP53 and BRCA1 ortholog gives 43 for the longest species. No question reaches either cap today. A cut of the label so the whole stays within 500, and a per name cut in `_fold_value_names`, would close it inside the card's fence if the lead wants it.

### V-38B-03: No test fails when the edge strip's `value_fold` guard is removed

- Severity: minor
- Worse than develop: no (the guard is present and correct; this is a missing pin)
- What: mutation V2 (strip the `OPTIONAL MATCH` clause for every query, model written included) leaves all 386 tests in the seven suites green. Today `value_fold` is True only for `gene_orthologs_one` and is False for model written Cypher (`tools/cypher_query.py:2076`, `:1987` to `:1997`), and the 45 other templates' edge maps equal develop's. Without a pin, a later edit could lower the risk reading of a model query that touches a high risk edge inside an `OPTIONAL MATCH`. One test that runs `_run_pipeline` with no template on such a query and asserts its ambiguous high risk flag would pin it.

### On the earlier reviews' findings

- A-38B-05 (human TP53's own row with a blank Organism cell): re-derived and agreed, minor, not worse. Absent data, not a wrong or lost record; reasons in the evidence log under "The closed tables, the mixed table and the caps".
- A-38B-04 (a Researcher TP53 run that reaches "answer" with no written sentence): my Researcher run did the same ("Based on 57 sources cited", outcome answer, only the count line and listing). The writer's prompt, findings and restatement inputs are byte identical with and without `organism` (`writer_input.py`), so the branch cannot steer it; develop's code path, writer variance.

## Evidence log

### Tests and CI's lint gates, on the branch head

```
PYTHONPATH=src venv/bin/python -m pytest -q tools/test_cypher_ortholog_organism.py tools/test_cypher_fold_templates.py tools/test_cypher_templates.py tools/test_cypher_query.py tools/test_cypher_query_templates.py tools/test_cypher_query_budget.py tools/test_cypher_query_e2e.py tools/test_cypher_query_premise.py tools/test_cypher_provenance.py tools/test_cypher_validator.py synthesis/test_answer_layout.py synthesis/test_variant_record_label.py
520 passed, 32 skipped in 17.32s
gate01 (compileall src services tests alembic, then the three module import): exit 0
gate02 (isort --check-only --diff src tests services tracker alembic .claude .github): Skipped 2 files, exit 0
gate03 (ruff check): All checks passed!, exit 0
```

### The other 45 templates are byte identical, and the edge strip touches only the value fold

Probe `<scratchpad>/card38b_ver/dump.py`, run in each tree, plus a hash over every non-ortholog template's (name, Cypher, fold, fallback Cypher, edge label, GO parameter):

```
46 templates on each tree; non-ortholog hash: branch 325fea4c37566a88, develop 325fea4c37566a88
differ: ['gene_orthologs_one']   value_fold True: ['gene_orthologs_one']
count Cypher, column count, edge map and ambiguous high risk map identical on the other templates
edge_used == edge_full on every other branch template: True
gene_orthologs_one: edge_full dev {'c0': 'orthologous_to'} branch {} | edge_used dev {'c0': 'orthologous_to'} branch {'c0': 'orthologous_to'} | amb dev [] branch []
```

Code reading for the model path:

- `value_fold` comes only from `active_template` (`tools/cypher_query.py:2076`), and `active_template` is `None` for the model written candidate (`:1987` builds `[template]` plus a fallback; the loop at `:1996` to `:1997` sets `active_template = candidate`). So model written Cypher reads `edge_text = normalized_cypher` (`:2188` to `:2192`), exactly develop's input to both edge functions.
- `all_template_examples` is called nowhere in `src` or `services` outside its own module (grep), so the template text never reaches a model prompt.
- The count gate change is `column_count == 1 or value_fold` (`:2150`); with `value_fold` False everywhere else, every other count path is develop's.

### Live graph, through the product's tool, branch against develop

Probe `<scratchpad>/card38b_ver/tool.py` (plan tier refused, so only templates run; reads only). The digest covers every field of every output row (CURIE, type, source URL, edge type, ambiguous high risk flag, snapshot version, fields) with only `organism` removed.

```
branch run 1
TP53 orthologs   ok gene_orthologs_one  rows 100 total 591 trunc True t 10.23 digest 3f43c6aa498337ba with_org 100 multi 0
  query 4.99 s rows 100 | ... OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN x, xs ORDER BY x.id LIMIT 100
  query 4.98 s rows 1   | ... WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count LIMIT 1
BRCA1 orthologs  ok gene_orthologs_one  rows 100 total 514 trunc True t 10.56 digest 64497c6b116e90c0 with_org 100 multi 0
BRCA1 diseases   ok gene_diseases_one   rows 4   total 4   trunc False t 0.45 digest 0e8e825ae4901f13 with_org 0
TP53 and BRCA1   ok gene_orthologs_many rows 100 total None trunc True t 6.95 digest 13545e326e6f3b95 with_org 0
develop
TP53 orthologs   ok gene_orthologs_one  rows 100 total 591 t 10.07 digest 3f43c6aa498337ba
BRCA1 orthologs  ok gene_orthologs_one  rows 100 total 514 t 10.24 digest 64497c6b116e90c0
BRCA1 diseases   ok gene_diseases_one   rows 4   total 4   t 0.43 digest 0e8e825ae4901f13
TP53 and BRCA1   ok gene_orthologs_many rows 100 total None t 6.95 digest 13545e326e6f3b95
branch run 2: TP53 t 10.23, BRCA1 t 10.26, diseases 0.52, two genes 7.54, the same digests and totals
```

- Rows, order, edge types, risk flags and totals equal develop's on all four questions; the only field the branch adds is `organism`, on the 200 single gene ortholog rows only, one species per row, none "Homo sapiens", longest 30 characters.
- Tool time: +0.16 s (TP53) and +0.02 to +0.32 s (BRCA1) over develop, inside the run to run noise.
- Species checked against NCBI Gene itself (one free `esummary` per gene list, all 200 rows): 199 of 200 equal NCBI's scientific name; the one difference is the same taxon under two names, the graph's "Tupaia chinensis" against NCBI Gene's "Tupaia belangeri chinensis" (`NCBIGene:102503238`, `NCBIGene:102494934`). Not a wrong species.

### The writer, the grounding gate and the restatement check see nothing new

Probe `<scratchpad>/card38b_ver/writer_input.py`: the 100 live TP53 rows from the branch, once as they are and once with `organism` removed (which is develop's row, digest equal above), through the real `build_synth_findings`, `build_synth_messages` and `_record_support_tokens`:

```
synth findings 25 25 equal: True
capped True True
prompt sha with organism c51e85cb863b4ee8 without c51e85cb863b4ee8 equal: True
species words in prompt: []
restatement support tokens equal: True
fields used: ['name']
```

So the writer's prompt, the findings the trust verdict is computed over and the restatement check are byte identical to develop's. The organism could reach a finding only if a row's `name` were blank or a vocabulary artifact and every earlier field too (`_pick_representative_field`, `core/graph.py:9530`, insertion order with `organism` last); no sampled row comes near that.

### Live end to end through `core.run.run_streaming()`, branch tree

Script `<scratchpad>/card38b_ver/live.py`, web surface, settings as card 115's adversary used them (classifier provider jev, guard and plan `deepseek/deepseek-v4-flash`, `PER_QUERY_COST_CAP_USD=0.25`), session ids `card38b-ver-tp53_res`, `card38b-ver-tp53_plain`, `card38b-ver-brca1d_res`. Summaries by `summ.py`.

| Run | First ten orthologs, with species | Count line | Trust line | Done event |
|---|---|---|---|---|
| TP53, Researcher | Header `Gene, Identifier, Organism`. tumor protein p53: NCBIGene:100009292 Oryctolagus cuniculus; 100049321 Oryzias latipes; 100062044 Equus caballus; 100092821 Ornithorhynchus anatinus; 100136737 Oncorhynchus mykiss; 100304476 Ictalurus punctatus; 100379269 Cavia porcellus; 100415710 Callithrix jacchus; 100435218 Pongo abelii; 100468516 Ailuropoda melanoleuca | "Found 40 gene records for TP53, of 715 available" and "Note: this answer was truncated because only 159 of the 715 records that matched this question in the graph were retrieved" | "Based on 57 sources cited" (outcome answer) | 30.31 s |
| TP53, Plain language | "tumor protein p53 (Oryctolagus cuniculus)", "(Oryzias latipes)", "(Equus caballus)", "(Ornithorhynchus anatinus)", "(Oncorhynchus mykiss)", "(Ictalurus punctatus)", "(Cavia porcellus)", "(Callithrix jacchus)", "(Pongo abelii)", "(Ailuropoda melanoleuca)" | "I found 40 genes related to TP53, out of 715 available", the same truncation note, and "no written summary could be checked against the records" | "Based on 57 sources cited, not yet confirmed" (ask) | 18.16 s |
| Control, "Which diseases are associated with BRCA1?", Researcher | Not an ortholog question. Tables `Disease, Identifier` (Familial cancer of breast MedGen:C0346153; Familial breast-ovarian cancer susceptibility 1; Pancreatic cancer susceptibility 4; Fanconi anemia complementation group S), `Gene, Identifier` (BRCA1 NCBIGene:672, no Organism column), `Paper`, `Variant`, `Record`, `Trial ... Status` | "Found 4 disease records for BRCA1: ..." plus a written sentence and a gene record quote | "Based on 21 sources cited, not yet confirmed" (ask) | 16.37 s |

- Researcher Gene table: 41 rows, 40 orthologs each with one species, none "Homo sapiens"; the 41st is human TP53's own Layer 2 record, `['TP53', 'NCBIGene:7157', '']`.
- "591" appears nowhere in either TP53 answer (`grep -c 591` gives 0 on both run files). The adversary's saved develop run of the same question (`<scratchpad>/card38b_adv/dev_tp53_res.jsonl`) reads the identical "Found 40 gene records for TP53, of 715 available" and "159 of the 715" and also has no "591". The 591 lives at the tool (`total_available` 591 on both trees, above); the screen's count line totals the answer's graph calls on both trees.
- Time, by stage (seconds into the run; develop from the adversary's saved run of the same question and depth):

| Run | Guard | Think | Ortholog graph call | Write starts | Done | Writer model call |
|---|---|---|---|---|---|---|
| Develop, TP53 Researcher (adversary) | 1.91 | 3.76 | 10.10 | 14.58 | 21.28 | 3.27 |
| Branch, TP53 Researcher (adversary) | 1.85 | 4.14 | 10.44 | 15.19 | 22.01 | not logged |
| Branch, TP53 Researcher (mine) | 1.96 | 10.69 | 10.25 | 21.52 | 30.31 | 3.37 |
| Branch, TP53 Plain language (mine) | 1.94 | 3.73 | 10.26 | 14.74 | 18.16 | 1.51 |
| Branch, BRCA1 diseases (mine) | 1.25 | 3.09 | 0.60 | 4.38 | 16.37 | 10.98 |
| Branch, BRCA1 diseases (adversary) | 1.61 | 3.79 | 0.59 | 4.91 | 9.68 | 3.60 |

  The only stage this card's code runs in is the graph call: 10.25 and 10.26 s against develop's 10.10 s live, and 10.23 against 10.07 s in the paired tool probe. My two slow runs lost their time elsewhere: the TP53 Researcher run's Think took 8.7 s (its plan model call 1.39 s; Think runs before any code this card touches), and the BRCA1 control's writer model call took 10.98 s against 3.60 s for the same branch code in the adversary's run, on a question whose rows carry no organism at all. Model latency, not the card. The adversary's paired branch run on the same question and depth finished 0.73 s after develop's.
- Spend: $0.010815 + $0.004588 + $0.010015 = $0.0254, under the $0.45 allowance. The tool probes and offline probes call no model; the NCBI check is two free E-utilities calls.

### The closed tables, the mixed table and the caps

- Keys: `("Gene", "organism")` in `_ROW_TYPE_COLUMNS` (`synthesis/answer_layout.py:629`) and `_ROW_TYPE_PLAIN_SUFFIXES` (`:644`). Only the value fold writes `organism` onto a row (grep: `FOLD_FIELD_ORGANISM` is the only producer in `tools`; the Layer 2 `organism` fields belong to rows typed by their database, `core/graph.py:8227`). The plain label checks `row_type == finding.entity_type` per finding (`:1027` to `:1035`), so a Layer 2 `gene` row never takes the suffix: live, human TP53 reads "TP53" in Plain language, as on develop.
- Mixed table (A-38B-05): the Researcher table's type is the first row's type (`core/graph.py:13482`, `type_for_group.setdefault`), and `record_status_or_year` is called with that group type (`:13531`). With the orthologs first, the column is "Organism", and human TP53's own row gets `collected_placeholder("Organism", ...)`, which is `""` for any column but "Collected". If the Layer 2 row ever came first, the group type would be `gene` and the column would not appear, which is develop's table exactly.
- My judgement on the blank cell, from the user's chair: develop shows that row as `TP53 | NCBIGene:7157` and the branch shows `TP53 | NCBIGene:7157 | (blank)`. Nothing develop showed is gone and nothing false is asserted; the blank is absent data, the same convention every other optional column already follows (a trial row with no status, a paper with no year). A researcher who asked "orthologs in other species" sees the one record that is not an ortholog with no species beside it, which if anything sets it apart. Not worse than develop. "Homo sapiens" there would be nicer, and is outside the lead's decision.
- Caps: four cells, the header is three (`Gene, Identifier, Organism`), within `cells` max 4 (`contracts/events.py:428`). Cell length max 500: the Researcher cell is `_clip_terms(value, MAX_LABEL_CHARS)` with `MAX_LABEL_CHARS = 500` (`answer_layout.py:889`); the plain label is `record_label` (up to 500) plus " (" + organism cut at 100 + ")". Offline probe, exact thresholds:

```
name 476 plain label 500 valid
name 477 plain label 501 ValidationError
taxon name 500 -> Researcher cell 500 valid
taxon name 501 -> Researcher cell 502 ValidationError
```

  Live data across 800 ortholog rows (TP53, BRCA1, EGFR, BRCA2, APOE, MTOR, TTN, CFTR, all via the tool, every row with one species): longest gene name 51 characters, longest species 30 (the adversary's aggregate over every TP53 and BRCA1 ortholog: 43), longest plain label 72. The breaking lengths are about seven times what the graph holds. Filed as V-38B-02 below.

### Break it, does a test go red (my own four, restored from memory after each)

Probe `<scratchpad>/card38b_ver/mutate.py`, the seven touched and neighbouring suites, `-x`:

```
V1 count gate ignores the value fold : RED | FAILED test_cypher_ortholog_organism.py::test_the_list_carries_species_and_the_total_stays_591
V2 edge strip runs on every query, model written included : GREEN | 386 passed, 1 skipped
V3 plain suffix cut raised from 100 to 1000 : GREEN | 386 passed, 1 skipped
V4 duplicates kept in the value fold : RED | FAILED test_cypher_ortholog_organism.py::test_the_list_carries_species_and_the_total_stays_591
```

`git status --short` after the probe: empty.

V2 matters. The guard `if value_fold` (`tools/cypher_query.py:2188` to `:2192`) is what keeps a model written query's `OPTIONAL MATCH ... WITH` clause in the text the edge type and ambiguous high risk functions read. Without the guard, a model query that touches a high risk edge only inside an `OPTIONAL MATCH` would have that touch removed from its risk reading. The guard is correct today (the template dump above and `:2076`), but no test fails when it is removed. Filed as V-38B-03.

## Verdict

Against the lead's acceptance:

| Acceptance | Result | Evidence |
|---|---|---|
| TP53's orthologs list their species, an Organism column in Researcher | Met | Live header `Gene, Identifier, Organism`, 40 of 40 orthologs with one species each; 199 of 200 tool rows equal NCBI Gene's scientific name, the 200th the same taxon under its other name |
| Plain language "tumor protein p53 (Oryctolagus cuniculus)" | Met | Live, first row exactly that |
| The answer still says 591 | Met at the tool (591 and 514, as develop); on screen both trees say "of 715" | V-38B-01, not worse |
| Every other answer exactly as on develop | Met | 45 templates, their counts and edge maps identical; four tool questions' rows digest equal; writer input byte identical; control answer shows no Organism column |
| Time within about a second of develop | Met | Graph call +0.15 s live, +0.16 s paired at the tool; the slow done events are model latency in Think and Write |

Nothing on this branch shows any person, for any question, something worse than develop shows today. The three findings are minor and none is worse than develop.

VERDICT: PASS
