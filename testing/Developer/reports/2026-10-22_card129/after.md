# Card 129: live runs before and after

`How many genes are associated with breast cancer?` answered "Found 1 medgen record for breast cancer: Seen by breast cancer nurse". After Fix C (bind disease-typed MedGen records before Findings) and Fix D (a genes count over several disease records takes the gene-list template), it answers with 22 genes, each cited to its NCBI Gene record, on 5 of 5 runs.

## Table of contents

- [How the runs were made](#how-the-runs-were-made)
- [Breast cancer, before and after](#breast-cancer-before-and-after)
- [Controls](#controls)
- [What the graph holds](#what-the-graph-holds)
- [What is still open](#what-is-still-open)
- [Spend](#spend)

## How the runs were made

| Setting | Value |
|---|---|
| Entry point | `core.run.run_streaming()`, the web app's path |
| Context | `RequestContext(surface="web_ui", reads_placement=True)` |
| Cost cap | `PER_QUERY_COST_CAP_USD=0.25` |
| Classifier | `CLASSIFIER_PROVIDER=jev` |
| Models | the local env's guard, plan and synth tiers |
| Depth | Researcher for breast cancer and MODY, Plain language for bronchiolitis |
| Before | develop's `src` (origin/develop 34406a31) unpacked to a scratch folder outside the worktree |
| After | this branch's `src` |

## Breast cancer, before and after

| Run | Code | Time to done | Count line | Records cited | Finding-typed record cited | Note |
|---|---|---|---|---|---|---|
| 1 | develop | 7.2 s | "Found 1 medgen record for breast cancer: Seen by breast cancer nurse [1]." | 1, MedGen 729095 (C1320450) | yes, the nurse visit | lists 8 upper-case Finding titles as "entities named in the question" |
| 2 | develop | 5.7 s | the same | the same | yes | the same, plus "no written summary could be checked" |
| 1 | branch | 11.4 s | "Found 22 gene records for breast cancer [...], linked to 3 diseases: Familial cancer of breast [2], Partial androgen insensitivity syndrome [6] and Hereditary diffuse gastric adenocarcinoma [25]." | 22 genes, 4 MedGen, PubMed, trials: 38 | no | names 3 disease records with no gene in the graph |
| 2 | branch | 8.5 s | the same | 22 genes: 36 | no | the same, plus "no written summary could be checked" |
| 3 | branch | 9.2 s | the same | 22 genes: 38 | no | the same 3 records |
| 4 | branch | 5.6 s | the same | 22 genes: 37 | no | the same 3 records |
| 5 | branch | 7.7 s | the same | 22 genes: 37 | no | the same 3 records |

One earlier branch run, made as a smoke check before the five, gave the same 22 genes in 10.9 s.

What every branch run shared:

- Think bound the same 6 records on 5 of 5: C4016951, C0006142, C0268301, C0346153, C0677776, C1708349. No Finding.
- The graph search took the `disease_genes_many` template: "25 row(s) of 25", 22 genes and the 3 disease records they link to, not truncated.
- The same 22 genes every run, BRCA1, BRCA2, TP53, ATM, CDH1, PIK3CA, RAD51 and BARD1 among them.
- The count line sits in the `summary` placement, the answer's opening block on the web page.
- The note now reads: "this answer does not address the following entities named in the question: Early-onset breast cancer, Malignant tumor of breast, Hereditary breast ovarian cancer syndrome". Those three records have no gene link in the graph (below).

## Controls

| Question | Code | Runs | Records bound | Answer |
|---|---|---|---|---|
| `What genes are associated with MODY?` (query 78) | branch | 2 | the same 8 MedGen records as develop | "Found 6 gene records for MODY: ..." with the same 6 genes (APPL1, GCK, HNF4A, PDX1, KCNJ11, HNF1A), 9.9 to 11.2 s |
| the same | develop | 1 | 8 | the same 6 genes, the same sentence, 8.6 s |
| `What causes bronchiolitis in babies, and how is it usually treated?` | branch | 5 | the same 8 records as develop on 4 runs; none on 1 | 4 answered "I found 8 conditions related to bronchiolitis" with a cited sentence on how common it is in infants, 5.4 to 9.8 s; 1 asked "which gene, variant or condition do you mean?" in 4.5 s |
| the same | develop | 3 | 8 | 3 answered, the same sentence shape, 7.0 to 7.7 s |

The one bronchiolitis ask-back is card 145, not this change. On that run Think's narrative carries no "(bronchiolitis: N of at least 20 MedGen records matched)" clause, so the model extracted no disease span and the MedGen resolver had nothing to rank. Fix C cannot bind nothing when MedGen matched something: it narrows to disease-typed records only when at least one exists. Card 145's diagnosis records the same ask-back on develop.

No run of any question took longer than 11.4 s.

## What the graph holds

A read-only count over `gene_associated_with_condition`, run the same day:

| Record | Genes linked |
|---|---|
| C0346153 Familial cancer of breast | 21 |
| C0268301 Partial androgen insensitivity syndrome | 1 (AR) |
| C1708349 Hereditary diffuse gastric adenocarcinoma | 1 (CDH1) |
| C0006142 Malignant tumor of breast | 0 |
| C4016951 Breast cancer, early-onset | 0 |
| C0677776 Hereditary breast ovarian cancer syndrome | 0 |
| The 6 together, distinct | 22 |
| The 8 Findings develop bound, together | 0 |

So the 22 is the graph's whole answer for these records, not a capped list: no "at least" was needed on these runs.

## What is still open

For the owner or a later card, none of them a confident wrong record:

- The note's wording: it calls the three records with no gene link "entities named in the question". The person named one condition. Its text lives in the write step (`graph.py` around 10216), outside this card's fence.
- Two of the six bound records reach breast cancer only through a synonym: partial androgen insensitivity ("with or without breast cancer") and hereditary diffuse gastric cancer ("lobular breast cancer syndrome"). Each gene is cited beside the record it is linked to, so AR shows "Partial androgen insensitivity syndrome". An exact-synonym rule would bind C0006142 alone; see `ncbi_check.md`, "Synonyms".
- The Plan narrative names the first bound record: "searching 3 layers for breast cancer, early-onset" (develop said "for seen by breast cancer nurse").
- A capped list: when several disease records link to more genes than the row limit (100), the template's two-column fold cannot fetch a true total, so the count line would read "Found 100 gene records" and the existing truncation note would add "the exact total that matched this question is not available". That is honest but is not the "at least" wording. Adding it means changing `synthesis/answer_layout.py` or `cypher_query`'s total for fold templates, both outside this card's fence. Not reached by this question.

## Spend

| Measure | Value |
|---|---|
| Key usage before the first run | $0.5228 |
| Key usage after the last run | $0.6676 |
| Difference, as the key reports it | $0.1448 |
| Sum of the 19 runs' own `total_cost_usd`, the loop's estimate | $0.17 |
| Most expensive run | $0.0115 |
