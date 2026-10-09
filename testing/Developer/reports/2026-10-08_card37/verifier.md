# Card 37 fresh verifier report

Verifier checkout: <repo-root>, HEAD 30db77c4 (git rev-parse HEAD matched the expected tip). Base: origin/develop. No live model calls; probes are local Python and targeted pytest runs.

## Findings

### V-37-01: the human gene RS1 is now read as the variant rs1, and its gene name is withheld from the model

- Severity: major
- Regression of: A-37-02 (inside the fix commit 30db77c4, `_RSID_PATTERN` made `re.IGNORECASE` at `src/system_03_search_agent/core/graph.py:5439`)
- What: RS1 (retinoschisin 1, the X-linked retinoschisis gene) is a real human gene symbol. With the pattern case-insensitive, "RS1" in a question is taken as the rs id rs1 by both `_rsids_in_text` (planner, `core/graph.py:5328`) and `resolve_exact_identifiers` (Think's exact pre-pass, `core/graph.py:4094`).
- Reproduction: probe script p37_rs1.py (scratchpad), printing `_rsids_in_text(q)` and the CURIEs of `resolve_exact_identifiers(q)`.

  HEAD 30db77c4:
  ```
  'What does the RS1 gene do?' ['rs1'] ['dbSNP:rs1']
  'RS1 mutations in X-linked retinoschisis' ['rs1'] ['dbSNP:rs1']
  'Rs1 and retinoschisis' ['rs1'] ['dbSNP:rs1']
  ```
  origin/develop c916cfa3, same script:
  ```
  'What does the RS1 gene do?' [] []
  'RS1 mutations in X-linked retinoschisis' [] []
  'Rs1 and retinoschisis' [] []
  ```
- Why it matters: on develop the text "RS1" reaches Think's model as an ordinary gene mention. On HEAD it is an exact-resolved entity, so `_build_think_messages` (`core/graph.py:2576` to `:2581`) tells the model "Already resolved exactly, do not re-extract: RS1", and `_gene_shaped_fallback_candidates` (`core/graph.py:3455` to `:3457`) excludes the token as claimed. The gene therefore cannot resolve by either path, and the plan gets a dbSNP and a LitVar2 lookup for rs1. A person asking about the RS1 gene gets an answer about a variant they never asked about, or none. Worse than develop. The A-37-02 gap (capital "RS334" planned nothing) was minor and pre-existing; the fix trades it for a wrong-entity answer on a real gene, the "confident wrong record" the product rules rank below a missing one.
- No test in the new file or the core directory covers a gene symbol of the form RS<digits>; the change went green.
- NOT FIXED
### V-37-02: the fix's comment "every use lowercases the matched text" is false for `_dbsnp_record_url`

- Severity: minor (unsure it is reachable)
- Regression of: A-37-02 (fix commit 30db77c4)
- What: the third use of `_RSID_PATTERN`, `_dbsnp_record_url` (`core/graph.py:9508` to `:9510`), fullmatches the CURIE's local id and returns it verbatim. With the pattern case-insensitive, a CURIE written with capitals now yields an upper-case dbSNP URL where develop returned None.
- Reproduction: p37_url.py, `_dbsnp_record_url(c)`.
  ```
  HEAD:    dbSNP:RS334 https://www.ncbi.nlm.nih.gov/snp/RS334   dbSNP:Rs334 https://www.ncbi.nlm.nih.gov/snp/Rs334
  develop: dbSNP:RS334 None                                     dbSNP:Rs334 None
  ```
- Why it matters: the expected URL would never byte-match the dbSNP tool's lowercase record URL, so such an entity would read as unaddressed. The only dbSNP CURIE producer I found (`core/graph.py:5513`) now lowercases, so I could not reach this from a question; filed because the comment states a property the code does not have.
- NOT FIXED
## Fix-round findings, re-derived

- A-37-01 and J-37-01 (citation label from a dropped near miss): FIXED. Own probe p37_cite.py drives the real shaper and `_layer3_citation_for_synth_finding` with a `Finding` built from the shaped rows.
  ```
  HEAD:    near miss first | rows: ['rs334'] | cite: litvar2 rs334 https://www.ncbi.nlm.nih.gov/snp/rs334 asserted
  HEAD:    near miss first, reverse sig | rows: ['rs334'] | cite: litvar2 rs334 https://www.ncbi.nlm.nih.gov/snp/rs334 hedged
  develop: near miss first | rows: ['rs334', 'rs334348'] | cite: litvar2 rs334 https://www.ncbi.nlm.nih.gov/snp/rs334 hedged
  develop: near miss first, reverse sig | rows: ['rs334', 'rs334348'] | cite: litvar2 rs334 https://www.ncbi.nlm.nih.gov/snp/rs334 asserted
  ```
  Mutation `if own:` to `if own and False:` at `core/graph.py:11819`: "1 failed, 8 passed", the failing test `test_citation_label_comes_from_the_cited_record_not_the_first_match`. Restored.
- A-37-02 (capital RS334 plans nothing): fixed as stated (`'What is RS334?' ['rs334'] ['dbSNP:rs334']`; removing IGNORECASE fails `test_rsid_in_capitals_is_found_in_the_question`, "1 failed, 8 passed", restored), but the fix introduces V-37-01, a wrong-entity regression for the RS1 gene, and V-37-02.
- J-37-02 (M5, M6 green): the two named tests exist and hold the stated sentences; not re-mutated by me beyond reading them, since neither path is reachable in production.

## Worse than develop

- rs334's own record and citation still show: yes, see the probe above (row `rs334`, citation `litvar2 rs334 .../snp/rs334`).
- Other variant questions: a non-rs query is unfiltered (`test_non_rsid_query_is_not_filtered`, `test_query_that_starts_with_an_rsid_but_is_not_a_bare_one_is_not_filtered`, both green).
- Worse: V-37-01, any question naming the RS1 gene in capitals or title case.

## Items left open

- A-37-03 (leading zero or merged id compared as strings) and A-37-04 (filter after the 10-match cap): both turn a wrong-variant listing on develop into an empty LitVar2 line. Under the product rule that a confident wrong record is worse than a missing one, no worse than develop. Neither probed live.

## Tests run

- `tests/system_03_search_agent/core/test_litvar2_exact_rsid.py`: "9 passed in 2.63s".
- `tests/system_03_search_agent/core`: "1394 passed, 56 skipped, 2 warnings in 64.67s". Green with V-37-01 present: no test covers an RS<digits> gene symbol.

## Verified by own probe versus read

- Own probe: V-37-01 (HEAD and develop), V-37-02, A-37-01 fix, A-37-02 fix, both mutations, the two test runs.
- Read only: J-37-02 tests, A-37-03 and A-37-04 live behaviour.

Verdict: DO NOT MERGE. Regression of: A-37-02. The case-insensitive rs id pattern makes the human gene RS1 resolve as the variant rs1 and hides it from gene resolution (V-37-01), worse than develop for any RS1 question.

### V-37-01, addendum: end to end through the real five-node graph

- Probe test (removed after the run) using `test_bare_topic_clarification.py`'s harness, models and `decide()` stubbed, the symbol resolver stubbed to `{"BRCA1": "NCBIGene:672", "RS1": "NCBIGene:6247"}`. Run once with HEAD's `src` and once with origin/develop's `src` extracted to the scratchpad.
  ```
  HEAD:    What does the RS1 gene do? | think entities: [('RS1', 'dbSNP:rs1')] | plan: Layer 1, the knowledge graph: cypher_query; Layer 2, live NCBI records: ncbi_dbsnp; Layer 3, literature and trials: litvar2_lookup
  develop: What does the RS1 gene do? | think entities: [('RS1', 'NCBIGene:6247')] | plan: searching 3 layers for NCBIGene:6247. Layer 1, the knowledge graph: cypher_query; Layer 2, live NCBI records: ncbi_efetch; Layer 3, literature and trials: pubtator_annotate, clinicaltrials_search
  ```
  Control, BRCA1, identical on both: `think entities: [('BRCA1', 'NCBIGene:672')] | plan: searching 3 layers for NCBIGene:672 ...`.
- So a person asking what the RS1 gene does gets, on HEAD, a dbSNP and LitVar2 lookup for a variant called rs1 and no gene record; on develop they get the RS1 gene. Confirmed worse than develop.

Verdict: DO NOT MERGE. Regression of: A-37-02. The case-insensitive rs id pattern turns a question about the RS1 gene into a lookup of the variant rs1 (V-37-01), worse than develop. The near-miss filter and the citation fix themselves hold.
