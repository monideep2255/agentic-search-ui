# Card 130 after: the writer is given the column the table shows

The same 24 runs as `before.md` (six questions, both depths, two repeats, the same settings and scripts), on 2026-10-22, after card 130's change to `synthesis/findings.py`. Raw output: `raw/after/*.jsonl`.

## Table of contents

- [The change](#the-change)
- [Before and after](#before-and-after)
- [What the writer was given, and what it cost](#what-the-writer-was-given-and-what-it-cost)
- [Does every summary sentence have a record behind it](#does-every-summary-sentence-have-a-record-behind-it)
- [Risk tier changes](#risk-tier-changes)
- [Verdict against the goal contract](#verdict-against-the-goal-contract)
- [What the measured set does not cover](#what-the-measured-set-does-not-cover)
- [Per run, after](#per-run-after)

## The change

| Row type | Column given to the writer | Example |
|---|---|---|
| Graph `Gene` (an ortholog) | `organism` | "Gene NCBIGene:100009292, organism: Oryctolagus cuniculus" |
| dbSNP `Variant record` | `genes` | "Variant record genes: HBB" |
| `Pathogen Detection isolate` | `amr_genotypes` | "Pathogen Detection isolate amr_genotypes: mcr-1.1, blaCTX-M-55" |

- Each column is a second finding, numbered right behind its row and cited to the same record page, the way the gene `summary` already was. It is read from the row's own field through a closed table keyed on the exact row type (`ROW_COLUMN_FIELDS`), never from the question.
- A column finding is a detail of its record (`SynthFinding.row_detail`). It takes no display slot, so the table lists exactly the records it listed before. It is never a listing entry, never makes two records that share a page read as one, and is never reported missing on its own. The listing's text is byte for byte what it was.
- The 30 prompt slots: a row and its column now take two slots, so a long list shows the writer 15 records with their columns instead of 30 bare names. Every record is still in the table. For a list whose 30 names were identical ("tumor protein p53" thirty times) or bare strain codes, 15 named species or gene sets are worth more to the writer than 15 more copies of the name. A short list such as rs334 and rs6025 loses nothing.
- Not built: a variant's condition. The variant row carries only MedGen CURIEs, and `core/graph.py` turns them into titles after `findings.py` has run, so that column needs a change in `core/graph.py`, which is outside this card's fence.

## Before and after

| Question | Depth | Summary shown, before | Summary shown, after | Note, before | Note, after | Trust, before | Trust, after | Tier, before | Tier, after | Median s, before | Median s, after | Slowest s, before | Slowest s, after |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q116_orthologs | researcher | 0 of 2 | 0 of 2 | 2 of 2 | 2 of 2 | ask, ask | ask, ask | low, low | low, low | 26.4 | 17.1 | 28.5 | 18.1 |
| q116_orthologs | plain_language | 0 of 2 | 1 of 2 | 1 of 2 | 1 of 2 | ask, answer | answer, ask | low, low | low, low | 20.9 | 16.8 | 22.9 | 17.1 |
| q022_cftr_variants | researcher | 1 of 2 | 0 of 2 | 1 of 2 | 2 of 2 | ask, ask | ask, ask | low, low | low, low | 15.7 | 14.4 | 16.1 | 17.5 |
| q022_cftr_variants | plain_language | 1 of 2 | 0 of 2 | 1 of 2 | 0 of 2 | ask, ask | ask, ask | low, low | low, low | 14.4 | 8.4 | 14.4 | 9.3 |
| q078_mody_genes | researcher | 0 of 2 | 0 of 2 | 2 of 2 | 1 of 2 | ask, ask | ask, ask | high, high | high, high | 9.7 | 8.4 | 10.0 | 8.5 |
| q078_mody_genes | plain_language | 1 of 2 | 2 of 2 | 0 of 2 | 0 of 2 | ask, ask | ask, ask | high, high | high, high | 10.2 | 11.1 | 11.2 | 11.7 |
| q104_pmid_data | researcher | 1 of 2 | 0 of 2 | 1 of 2 | 2 of 2 | ask, answer | ask, ask | low, low | low, low | 8.5 | 6.5 | 10.3 | 7.2 |
| q104_pmid_data | plain_language | 0 of 2 | 0 of 2 | 2 of 2 | 1 of 2 | ask, ask | answer, ask | low, low | low, low | 10.1 | 5.4 | 13.5 | 6.1 |
| rs334_rs6025 | researcher | 1 of 2 | 0 of 2 | 1 of 2 | 2 of 2 | ask, ask | ask, ask | high, high | high, high | 13.2 | 12.4 | 14.2 | 14.6 |
| rs334_rs6025 | plain_language | 0 of 2 | 0 of 2 | 2 of 2 | 2 of 2 | ask, ask | ask, ask | high, high | high, high | 7.6 | 9.1 | 9.1 | 11.6 |
| q037_colistin | researcher | 0 of 2 | 0 of 2 | 2 of 2 | 2 of 2 | ask, ask | ask, ask | low, low | low, low | 37.9 | 28.9 | 53.9 | 31.8 |
| q037_colistin | plain_language | 0 of 2 | 0 of 2 | 2 of 2 | 2 of 2 | ask, ask | ask, ask | low, low | low, low | 37.2 | 41.6 | 53.3 | 42.2 |

"Summary shown" counts runs with any written sentence besides the count line, whether or not it says more than the names. The runs that do say more than the names:

| | Before | After |
|---|---|---|
| Runs whose written summary says something beyond the record names | 0 of 24 | 1 of 24 |
| Which | none | Orthologs, Plain language, run 1: "The species include Oryctolagus cuniculus [59], Oryzias latipes [60], Equus caballus [61], ... and Sarcophilus harrisii [73]." (15 species, each cited to its own ortholog record) |

Every other written sentence, before and after, only repeats names: CFTR HGVS names, MODY gene names, assembly names, trial titles.

The control: CFTR variants, MODY genes and the PMID data question have no column, and the writer was given byte-identical findings before and after (table below). Their swings (CFTR Researcher summary 1 of 2 to 0 of 2, notes moving between paths) are therefore the writer model's run-to-run variation, not this change. Two repeats is too few to separate a small effect from that variation.

## What the writer was given, and what it cost

| Question | Depth | Writer input identical | Column findings given | Second draft started, before | after | Median write s, before | after | Median cost USD, before | after |
|---|---|---|---|---|---|---|---|---|---|
| q116_orthologs | researcher | no | 15 | 0 of 2 | 2 of 2 | 9.4 | 2.5 | 1.0 c | 0.8 c |
| q116_orthologs | plain_language | no | 15 | 0 of 2 | 2 of 2 | 4.7 | 3.3 | 0.8 c | 0.7 c |
| q022_cftr_variants | researcher | yes | 0 | 0 of 2 | 0 of 2 | 6.9 | 6.8 | 1.5 c | 1.1 c |
| q022_cftr_variants | plain_language | yes | 0 | 0 of 2 | 0 of 2 | 7.2 | 2.5 | 1.1 c | 0.6 c |
| q078_mody_genes | researcher | yes | 0 | 0 of 2 | 0 of 2 | 5.3 | 3.7 | 0.8 c | 0.6 c |
| q078_mody_genes | plain_language | yes | 0 | 0 of 2 | 0 of 2 | 3.6 | 4.1 | 0.6 c | 0.6 c |
| q104_pmid_data | researcher | yes | 0 | 0 of 2 | 0 of 2 | 3.1 | 3.1 | 0.4 c | 0.5 c |
| q104_pmid_data | plain_language | yes | 0 | 0 of 2 | 0 of 2 | 2.6 | 2.4 | 0.4 c | 0.5 c |
| rs334_rs6025 | researcher | no | 2 | 1 of 2 | 2 of 2 | 2.6 | 2.7 | 0.5 c | 0.5 c |
| rs334_rs6025 | plain_language | no | 2 | 1 of 2 | 2 of 2 | 1.4 | 1.4 | 0.4 c | 0.4 c |
| q037_colistin | researcher | no | 15 | 0 of 2 | 2 of 2 | 5.0 | 4.3 | 0.6 c | 1.0 c |
| q037_colistin | plain_language | no | 15 | 0 of 2 | 2 of 2 | 3.1 | 2.5 | 0.5 c | 0.6 c |

- Write time is from the first listing token to the `done` event. The second-draft spy was added during the before batch, so the before count covers repeat 2 only.
- A column the code-built listing does not cite by its own number counts as uncitable in `core/graph.py`'s `_listing_uncitable`, so every list with columns now starts the completeness draft beside the first draft. The draft runs in parallel and is kept only when the existing repair rule needs it, so it adds cost, not time: no write step got slower, and the ortholog write step fell from a median of 9.4 s to 2.5 s in Researcher. Colistin Researcher's median cost rose from 0.6 to 1.0 cents. Every run stayed far under the 25 cent cap.

## Does every summary sentence have a record behind it

- The grounding pass, the sentence check and the restatement drop are unchanged, so every written sentence that ships still passed them.
- `raw/check_backing.py` reads each run's screen: for every written claim citing a column finding, it checks that the value shown in the table row of the record it cites appears in the claim. After: 15 such claims, 0 that do not match their own record. A claim naming another record's species would show as a mismatch.
- The count line still names records by their own labels. In the rs334 runs it reads "rs334 [1] and rs6025 [2]", never the gene.
- No summary states anything a cited record does not back.

## Risk tier changes

None. Every run's answer-scope tier is the same as before for its question: orthologs, CFTR variants, PMID data and colistin low; MODY genes and rs334 with rs6025 high (the high tier comes from the clinical significance and gene-condition rows, as before). The three new column fields all score low (`synthesis/trust.py`'s `risk_tier_for`), and no clinical value (significance, condition) was added to the writer's input, so no tier could change from this card.

## Verdict against the goal contract

| Done when | Result |
|---|---|
| More list answers show a written summary that says something beyond the names | Met, narrowly: 0 of 24 runs before, 1 of 24 after (orthologs, Plain language). Orthologs Researcher, rs334 with rs6025 and colistin still fall to the code-built list in every run |
| No summary states anything a cited record does not back | Met: 15 of 15 column claims match their own record; every sentence passed the unchanged gate |
| No answer slows past 20 s that was under it before | Met: every question under 20 s before stays under it (slowest after: 17.5 s). Orthologs went from over 20 s in 3 of 4 runs to under 18.2 s in all 4. Colistin was over 20 s before (21.1 to 53.9 s) and after (25.9 to 42.2 s); the isolate scan dominates, and its write step did not grow |
| Every risk tier change listed and explained | None occurred; see above |

## What the measured set does not cover

- Two repeats per question and depth: enough to see a large change, not to measure a small one against the writer's own variation.
- The variant-to-condition column (CFTR variants, HNF1A variants): not built, needs `core/graph.py`.
- Why the columns often do not survive: colistin's resistance gene lists are long, and a sentence naming one gene from a list is not a whole copy of the value, so the exact check strips it; rs334 and rs6025 fell to the fallback in all four runs. The writer's replies and the grounding pass's candidates were not logged, so which check removed each sentence is not confirmed.
- Ortholog Researcher answers: no column sentence survived in either run.
- Other row types that carry a table column (a trial's status, a gene's condition list), and papers (card 117): out of scope.
- One build of develop's models, on one evening; the graph service and NCBI timings vary between runs.

## Per run, after

| Question | Depth | Run | Written summary shown | No-summary note | Trust | Tier | Restatements dropped | Fallback | Seconds |
|---|---|---|---|---|---|---|---|---|---|
| q116_orthologs | researcher | 1 | none | yes | ask | low | not run | yes | 16.13 |
| q116_orthologs | researcher | 2 | none | yes | ask | low | not run | yes | 18.13 |
| q116_orthologs | plain_language | 1 | The species include Oryctolagus cuniculus [59], Oryzias latipes [60], Equus caballus [61], Ornithorhynchus anatinus [62], Oncorhynchus mykiss [63], Ictalurus punctatus [64], Cavia porcellus [65], Callithrix jacchus [66], Pongo abelii [67], Ailuropoda melanoleuca [68], Nomascus leucogenys [69], Loxodonta africana [70], Cricetulus griseus [71], Oreochromis niloticus [72], and Sarcophilus harrisii [73]. | no | answer | low | 0 | no | 17.06 |
| q116_orthologs | plain_language | 2 | none | yes | ask | low | not run | yes | 16.54 |
| q022_cftr_variants | researcher | 1 | none | yes | ask | low | not run | yes | 11.35 |
| q022_cftr_variants | researcher | 2 | none | yes | ask | low | not run | yes | 17.47 |
| q022_cftr_variants | plain_language | 1 | none | no | ask | low | 8 | no | 9.3 |
| q022_cftr_variants | plain_language | 2 | none | no | ask | low | 1 | no | 7.53 |
| q078_mody_genes | researcher | 1 | none | no | ask | high | 1 | no | 8.54 |
| q078_mody_genes | researcher | 2 | none | yes | ask | high | not run | yes | 8.36 |
| q078_mody_genes | plain_language | 1 | PDX1, named "pancreatic and duodenal homeobox 1" [8]. KCNJ11, named "potassium inwardly rectifying channel subfamily J member 11" [10]. APPL1, named "adaptor protein, phosphotyrosine interacting with PH domain and leucine zipper 1" [1]. | no | ask | high | 0 | no | 10.48 |
| q078_mody_genes | plain_language | 2 | Health Effects of Liposuction in Overweight Women With Elevated Insulin Levels, Impaired Glucose Tolerance and/or Type 2 Diabetes [15], Lifestyle Interventions to Reduce Diabetes Risk [16], Effects of Rosiglitazone on the Metabolic Phenotype of Impaired Glucose Tolerance in Youth [17], Additional Glucose Lowering and Anti-Inflammatory Effects by Acarbose and Alcohol in Subjects With Impaired Glucose Tolerance or Mild Type 2 Diabetes [18], and Effects of Colesevelam HCl On Bile Acid Kinetics [19]. | no | ask | high | 0 | no | 11.66 |
| q104_pmid_data | researcher | 1 | none | yes | ask | low | not run | yes | 7.23 |
| q104_pmid_data | researcher | 2 | none | yes | ask | low | not run | yes | 5.78 |
| q104_pmid_data | plain_language | 1 | none | no | answer | low | 9 | no | 4.78 |
| q104_pmid_data | plain_language | 2 | none | yes | ask | low | not run | yes | 6.06 |
| rs334_rs6025 | researcher | 1 | none | yes | ask | high | not run | yes | 10.32 |
| rs334_rs6025 | researcher | 2 | none | yes | ask | high | not run | yes | 14.58 |
| rs334_rs6025 | plain_language | 1 | none | yes | ask | high | not run | yes | 6.58 |
| rs334_rs6025 | plain_language | 2 | none | yes | ask | high | not run | yes | 11.59 |
| q037_colistin | researcher | 1 | none | yes | ask | low | not run | yes | 25.93 |
| q037_colistin | researcher | 2 | none | yes | ask | low | not run | yes | 31.78 |
| q037_colistin | plain_language | 1 | none | yes | ask | low | not run | yes | 42.2 |
| q037_colistin | plain_language | 2 | none | yes | ask | low | not run | yes | 41.04 |

Runs: 24. Model spend the runs report: 0.1571 USD.
