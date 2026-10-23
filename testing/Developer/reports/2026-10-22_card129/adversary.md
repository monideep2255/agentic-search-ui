# Card 129 adversary, round 1

Pull request #295, branch fix/card129-bind-disease-records-first. Findings are filed as they are found. Ids A-129-NN.

## Findings

### Method

- 24 read-only MedGen calls (12 mentions, one ESearch plus one ESummary each) through the repository's own `ncbi_eutils_actions.search` and `summary`, with the exact term `resolve_disease_mention_to_curies` builds, recorded to a scratch file. Then four rules simulated offline on the same recorded data: develop (no type rule), the branch (graph.py:3455 to 3456, exclusion), R1 "disease-typed first, Findings after" (type tier above phrase tier) and R2 "phrase tier first, type inside each tier". Both R1 and R2 keep the exact rule first and the cap of 8 (graph.py:3260), sort by concept id inside a tier, as the code does.
- Mentions: breast cancer, ovarian cancer, prostate cancer, lung cancer, colon cancer, diabetes, asthma, autism, obesity, alzheimer disease, heart attack, hypertension.

### A-129-01: under a ranking with the cap of 8, "breast cancer" binds "Seen by breast cancer nurse" again and still drops "Breast cancer, susceptibility to"
- Severity: major (aims at the planned fix round, not the branch as built)
- What: "breast cancer" matches 6 disease-typed records and 14 Findings, no exact title. With 6 disease records ahead, 2 slots remain for Findings, and concept-id order inside the Finding tier hands them to the two lowest ids.
- Reproduction, live MedGen data of 2026-10-22, simulated:
  - R1 (type then phrase): C4016951 Breast cancer, early-onset; C0006142 Malignant tumor of breast; C0268301 Partial androgen insensitivity syndrome; C0346153 Familial cancer of breast; C0677776 Hereditary breast ovarian cancer syndrome; C1708349 Hereditary diffuse gastric adenocarcinoma; C1320450 Seen by breast cancer nurse; C1861471 Paraneoplastic SPS is associated with breast cancer.
  - R2 (phrase then type): C4016951; C1320450 Seen by breast cancer nurse; C1861471 Paraneoplastic SPS ...; C1968974; C2675521; C2676677; C3469522 Breast cancer, susceptibility to; C4016360. Here the nurse visit is the second record bound.
  - C3469522 "Breast cancer, susceptibility to", the record J-129-04 shows carries CHEK2, PALB2, PTEN, STK11, NBN, RAD50, RAD51D, is 13th of 14 under R1 and is not bound.
- Why it matters: the planned fix restores the exact record card 129 was filed to remove, and under R1 still loses the genes J-129-04 names. A ranking alone does not separate "Seen by breast cancer nurse" (a clinical event) from "Breast cancer, susceptibility to" (OMIM susceptibility): both are typed Finding, and concept id is the only tie-break. Nothing in the record type tells them apart.
- NOT FIXED

### A-129-02: "What genes are associated with hypertension?" now answers with pulmonary arterial hypertension genes (BMPR2, CAV1, KCNK3, SMAD9), and a ranking keeps them
- Severity: critical (inside this phase's Fix C; a confident answer about a different disease, and the planned ranking does not change it)
- What: "hypertension" has no exact title in its 20 hits; 7 are disease-typed. Fix C (graph.py:3455 to 3456) drops the 13 Findings, and the phrase tier (graph.py:3457) then puts four "Pulmonary hypertension, primary, N" records ahead of the general record C0020538 "Hypertensive disorder", which is synonym-only because its title says "Hypertensive". Pulmonary arterial hypertension is a different disease from high blood pressure.
- Reproduction:
  - Live MedGen, simulated: develop binds C0085580 Essential hypertension; C1853226, C1858497, C1858967, C1970244, C1970439 (Hypertension, essential, susceptibility to, N); C1857175 Episodic hypertension; C2748577 No hypertension. The branch binds C0085580; C3809192, C3809198, C3888002, C4552070 (Pulmonary hypertension, primary, 3, 4, 2, 1); CN305331 Essential hypertension, genetic; C0020538 Hypertensive disorder. R1 and R2 both bind the same four pulmonary records too, since they are disease-typed and in-title.
  - Graph, `cypher_query(None, CypherQueryInput(query_intent="What genes are associated with hypertension?", query_class="single_hop", target_entities=<set>, row_limit=100))`, template `disease_genes_many`. Branch set: `rows 17 total 17 trunc False`, 12 genes, among them `('bone morphogenetic protein receptor type 2', 'NCBIGene:659', ['MedGen:C4552070'])`, `('caveolin 1', 'NCBIGene:857', ['MedGen:C3809192'])`, `('potassium two pore domain channel subfamily K member 3', 'NCBIGene:3777', ['MedGen:C3809198'])`, `('SMAD family member 9', 'NCBIGene:4093', ['MedGen:C3888002'])`. Develop set: `rows 6 total 6`, 5 genes, all on C0085580 Essential hypertension through the variant path: CYP3A5, AGTR1, NOS3, PTGIS, UMOD.
- Why it matters: a clinician asking about hypertension is shown BMPR2, the best-known pulmonary arterial hypertension gene, cited to a record that is honestly about pulmonary hypertension, inside an answer framed as hypertension. This is the confident wrong record the owner ranks worse than a missing one. The branch also loses NOS3 and UMOD, which develop returned, the same all-or-nothing fallback mechanism as J-129-05. A type ranking cannot fix this one: every wrong record is disease-typed and names the phrase in its title. The tie-break among in-title disease records is concept id, so lower ids win, whatever they are.
- NOT FIXED

### A-129-03: the breast cancer gene answer is "linked to 3 diseases", two of which are not breast cancer, and a ranking keeps both ahead of every breast cancer Finding
- Severity: major (inside this phase's Fix C; survives the planned ranking)
- What: C0268301 "Partial androgen insensitivity syndrome" and C1708349 "Hereditary diffuse gastric adenocarcinoma" match "breast cancer" only through a MedGen synonym (the `[title]` index ANDs the words, graph.py:3388 to 3389), are disease-typed, and so bind under the branch and under R1. Under R1 they rank above C3469522 "Breast cancer, susceptibility to" and every other in-title breast cancer Finding.
- Reproduction: `cypher_query(None, CypherQueryInput(query_intent="How many genes are associated with breast cancer?", query_class="aggregate", target_entities=[C4016951, C0006142, C0268301, C0346153, C0677776, C1708349], row_limit=100))`: template `disease_genes_many`, `rows 25 total 25 trunc False`, 22 genes; 20 linked only to C0346153, `('androgen receptor', 'NCBIGene:367', ['MedGen:C0268301'])` linked only to Partial androgen insensitivity syndrome, `('cadherin 1', 'NCBIGene:999', ['MedGen:C0346153', 'MedGen:C1708349'])`. The live count line in the builder's after.md, line 33: "Found 22 gene records for breast cancer [...], linked to 3 diseases: Familial cancer of breast [2], Partial androgen insensitivity syndrome [6] and Hereditary diffuse gastric adenocarcinoma [25]."
- Why it matters: the opening sentence of a breast cancer answer names an androgen insensitivity syndrome and a gastric cancer as two of the three diseases its genes are linked to. AR is in the answer only because of PAIS. A reader reads "linked to 3 diseases" as three breast cancer records. The ranking the fix round plans orders disease-typed synonym hits above in-title Findings, so this stays; under R2 (phrase tier first) it would fall out, so which ranking is built decides it.
- NOT FIXED

### A-129-04: Fix D answers "How many genes are associated with both breast cancer and ovarian cancer?" with the union, 26, where 2 genes are linked to both
- Severity: critical (inside this phase's Fix D; a confident wrong number for a common question shape)
- What: Fix D's arm (src/system_03_search_agent/tools/cypher_templates.py:920 to 925) sends every genes count over two or more Disease anchors to `_disease_genes_template`, which matches `a.id IN [...]`, the union. It does not distinguish anchors from one mention (six breast cancer records) from anchors of two different diseases the person asked to intersect. Develop sent this to the model path (select_template returned None), which could at least write an intersection.
- Reproduction: `cypher_query(None, CypherQueryInput(query_intent="How many genes are associated with both breast cancer and ovarian cancer?", query_class="aggregate", target_entities=[the branch's 6 breast cancer records, MedGen:C1140680 "Ovarian cancer" (its exact-title binding, live MedGen)], row_limit=100))`: template `disease_genes_many`, `rows 30 total 30 trunc False`, `genes 26`. Genes whose fold lists both a breast cancer record and C1140680: 2, AKT1 and PIK3CA (`multi-anchor genes 3`, the third CDH1 being C0346153 plus C1708349, not ovarian). The count line would open "Found 26 gene records for ...".
- Why it matters: a researcher asking for genes shared by two cancers gets 26, a number thirteen times the true shared count, every gene honestly cited, so nothing on the page signals the error. Same for "and" read as intersection ("genes associated with obesity and diabetes"). The anchor grouping per mention exists in Think; the template throws it away.
- NOT FIXED

### A-129-05: "How many genes are associated with breast cancer and intellectual disability?" counts breast cancer's 22 and silently drops intellectual disability's genes
- Severity: major (inside this phase's Fix D route; same all-or-nothing fallback as J-129-05, now reached by a count)
- What: C3714756 "Intellectual disability" (exact title) has no `gene_associated_with_condition` row but at least 99 genes on the variant path. With the six breast cancer records in the same anchor set, the primary returns rows, so the variant fallback (cypher_templates.py:551 to 579) never runs for any anchor.
- Reproduction: `cypher_query`, target_entities = 6 breast cancer records plus MedGen:C3714756, "How many genes are associated with breast cancer and intellectual disability?", aggregate: `disease_genes_many rows 25 total 25 trunc False genes 22`, the identical 22 breast cancer genes, no gene linked to C3714756. The same record alone, "What genes are associated with intellectual disability?": `disease_genes_one rows 100 total None trunc True genes 99`.
- Why it matters: the count reads as the answer for both conditions and is the answer for one. A broad anchor does not swamp here; it vanishes. If the fix round makes the fallback per anchor, the opposite happens: ID's 99-plus capped rows swamp breast cancer's 22 and the count line says "Found 99" (J-129-09). Either way the number is wrong for the question asked.
- NOT FIXED

### A-129-06: Fix D keeps the one-anchor genes count, which answers 0 for intellectual disability while the list answers 99
- Severity: major (pre-existing on develop, but Fix D's comment at cypher_templates.py:919 makes "one anchor keeps the count form, which cites its count to that record" a stated design, and the branch now gives the two counts different semantics)
- What: `disease_genes_one_count` counts the gene edge only; the list templates fall back to the variant path. Over several anchors the branch now counts through the list (fallback included); over one anchor it counts the edge alone.
- Reproduction: `cypher_query`, "How many genes are associated with intellectual disability?", [MedGen:C3714756], aggregate: `template disease_genes_one_count`, row `('derived', 'MedGen:C3714756', {'genes_count': 0})`. "What genes are associated with intellectual disability?", same record: `disease_genes_one rows 100 total None trunc True genes 99`. "How many genes are associated with ovarian cancer?", [C1140680]: `{'genes_count': 7}`.
- Why it matters: "How many genes are associated with intellectual disability?" gets a cited 0 for one of the most gene-rich phenotypes in the graph, while "What genes ..." lists 99. Over several records ("developmental delay" on develop's binding) the same question would get 99 through the list. The count a person sees depends on how many MedGen records their words matched, not on the graph. I did not render the answer for the 0; unsure whether a 0 count is shown or turned into a refusal.
- NOT FIXED

### A-129-07: "exact title first" binds the Finding "Diabetes" alone, so "What genes are associated with diabetes?" answers 3 genes where type 1 and type 2 records hold 28
- Severity: major (pre-existing on develop and the branch alike; recorded because the fix round's ranking keeps "exact title first" above "disease-typed first", so it carries this forward by design)
- What: the exact rule (graph.py:3437 to 3438) runs before any type consideration. MedGen's C1320657 "Diabetes" is typed Finding; the 9 disease-typed hits (C0011854 Diabetes mellitus type 1, C0011860 Type 2 diabetes mellitus, ...) never bind.
- Reproduction: live MedGen "diabetes": 20 hits, 9 disease-typed, exact = [C1320657] (Finding). All four rules simulated bind C1320657 alone. Graph through `cypher_query`, "What genes are associated with diabetes?": [C1320657] gives `disease_genes_one rows 4`, 3 genes (KCNJ11, CELA2A, WFS1), all variant path; [C0011854, C0011860] gives `disease_genes_many rows 30 total 30`, 28 genes.
- Why it matters: the most common disease word a user will type answers with three genes, cited to a Finding record. The judge's controls (tall stature, hearing loss, seizure) show "exact Finding wins" is right for phenotype words; diabetes shows it is wrong for a disease word whose bare-title record happens to be a Finding. A rule ordering exact above type cannot tell these apart.
- NOT FIXED

### A-129-08: with no disease-typed hit, "heart attack" binds "Fear of having a heart attack", "Anxiety about having a heart attack" and a CHADS2 score record
- Severity: minor (pre-existing; the graph returns nothing for them, so the harm is the note and the "what was looked up" disclosure, not a wrong gene)
- What: MedGen's `[title]` index returns 3 hits for "heart AND attack", all Findings; "Myocardial infarction" is not among them. The branch's fallback "Finding binds only when no disease record matched" (graph.py:3454 to 3456) binds all three, and so would any type ranking.
- Reproduction: live MedGen "heart attack": C0424154 Fear of having a heart attack, C0457037 Anxiety about having a heart attack, C4706244 CHADS2 (congestive heart failure, hypertension, ...), all Finding; develop, branch, R1, R2 all bind those three. Graph: "What genes are associated with heart attack?" and the "How many" form: `disease_genes_many status empty rows 0`.
- Why it matters: per J-129-10's mechanism the note would tell the person their answer "does not address ... Fear of having a heart attack", the same class of wrong record card 129 exists to stop. Not verified end to end (no model calls).
- NOT FIXED

### A-129-09: on the branch every breast cancer question searches PubMed, trials and PubTator for "breast cancer, early-onset", and a ranking keeps it
- Severity: major (a consequence of Fix C's new first record; better than develop's "seen by breast cancer nurse", still the wrong disease text)
- What: with no gene resolved, the literature, trials and PubTator calls all take the title of the FIRST MedGen CURIE in target_entities (`_first_disease_curie`, graph.py:6409; used at graph.py:7352 to 7357; `breadth_plan.disease_search_text`). The resolver orders the in-title tier first by concept id, and for "breast cancer" the only disease-typed record whose title holds the phrase is C4016951 "Breast cancer, early-onset". C0006142 "Malignant tumor of breast" is in the synonym tier.
- Reproduction: live MedGen "breast cancer", branch, R1 and R2 all put C4016951 first (develop put C1320450 first). Offline through the repository's own functions: `breadth_plan.build_pubmed_term(None, "Breast cancer, early-onset")` gives `"breast cancer, early-onset"[Title/Abstract]`; develop's first title gives `"seen by breast cancer nurse"[Title/Abstract]`. Same mechanism elsewhere on the branch: hypertension's first is C0085580, text `essential hypertension`; short stature's first is C1845118, text `shox-related short stature` (develop: `disproportionate short stature`).
- Why it matters: "Any trials for breast cancer?" or "Recent papers on breast cancer" are searched as early-onset breast cancer, and the trials and papers shown are cited to real records, so nothing on the page shows that the search was narrowed. Not run end to end (no model calls, no PubMed or trials calls in my budget); the term is computed by the code's own function on the branch's live binding.
- NOT FIXED

### A-129-10: addendum to A-129-04, the count line names both diseases, so the union reads as the shared answer
- Severity: major (supports A-129-04)
- What: the summary subject joins every mention Think resolved, "breast cancer and ovarian cancer" (graph.py:12810 to 12825), and the technical line opens `Found {n} gene records for {subject}` (answer_layout.py:1949 to 1950); plain language, `I found {n} genes related to {subject}` (answer_layout.py:1921 to 1926).
- Reproduction: read, combined with A-129-04's measured 26 genes. Not rendered end to end.
- Why it matters: "Found 26 gene records for breast cancer and ovarian cancer" answers "both ... and ..." with the union in the user's own words.
- NOT FIXED

### A-129-11: the Think disclosure says "6 of at least 20 MedGen records matched by name" when the cap did not cut anything, the type rule did
- Severity: minor
- What: `matched` counts every titled hit including the Findings Fix C drops (graph.py:3435), and `_disease_binding_disclosure` (graph.py:3606 to 3616) words `matched > bound` as a cap.
- Reproduction: the branch resolver on the recorded live data: breast cancer returns `(6 CURIEs, 20)`, hypertension `(7 CURIEs, 20)`, both under the cap of 8 (graph.py:3260), so the disclosure reads "breast cancer: 6 of at least 20 MedGen records matched by name" and "hypertension: 7 of at least 20 ...".
- Why it matters: the disclosure says a limit cut the list; the person cannot tell that 14 records were left out by kind, and "at least 20" invites them to think more breast cancer records exist that were simply not shown.
- NOT FIXED

### Checks on my own method
- The offline simulator was confirmed against the branch's real `resolve_disease_mention_to_curies`, run with `ncbi_eutils_actions.search` and `summary` replaced by the recorded responses: identical bindings for all 12 mentions (for example `breast cancer (['MedGen:C4016951', 'MedGen:C0006142', 'MedGen:C0268301', 'MedGen:C0346153', 'MedGen:C0677776', 'MedGen:C1708349'], 20)` and the hypertension list in A-129-02).
- MedGen calls used: 24 of 25. Graph reads: `cypher_query(None, ...)` only, read-only. No model calls. Worktree left with `git diff HEAD` empty.

## Verdict

FAIL against the card's goal ("a question about a disease binds the disease, and a count answers the count").

- Verified by my own probes: A-129-01 (ranking simulation on live MedGen data, simulator checked against the real function), A-129-02 (PAH genes for hypertension, graph read), A-129-03 (AR via PAIS, graph read), A-129-04 (union 26 against 2 shared, graph read), A-129-05 and 06 (graph reads), A-129-07 (diabetes, graph read), A-129-08, A-129-09 (search term computed by the code's own function), A-129-11.
- Read only, not run end to end: every rendered sentence (count line, Plain language wording, note, trust line, sources count against card 133). The 22-gene trust line and risk tier: read only; by `trust.DECISION_TABLE` 22 graph-only high-risk claims triangulate "insufficient" and go to "ask", the same as any gene list, not verified rendered.
- Inside this phase's fixes, so the stop condition fires: A-129-02 and A-129-03 sit inside Fix C, and A-129-04, A-129-05 and A-129-10 inside Fix D. A-129-01, 02, 03, 07 and 09 survive the planned ranking (disease-typed first, Findings after, exact title first).
