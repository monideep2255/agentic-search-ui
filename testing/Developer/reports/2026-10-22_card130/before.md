# Card 130 before: develop's writer input on the measured set

Develop at `25235e98`, before card 130's change to `synthesis/findings.py`. 24 runs on 2026-10-22: six questions, both depths, two repeats each, one process per run.

## Table of contents

- [How the runs were made](#how-the-runs-were-made)
- [Per run](#per-run)
- [What the before runs show](#what-the-before-runs-show)

## How the runs were made

| Setting | Value |
|---|---|
| Entry point | `core.run.run_streaming`, the path the web app uses, timed from the call to the `done` event |
| Client settings | `RequestContext(surface="web_ui", reads_placement=True)` |
| Models | Develop's API as recorded in `docs/build/Handoff_history.md`: guard and plan `deepseek/deepseek-v4-flash`, synth `z-ai/glm-5.2` (the local settings file's plan model differs, so it was pinned) |
| Classifier | `CLASSIFIER_PROVIDER=jev` |
| Cost cap | `PER_QUERY_COST_CAP_USD=0.25` |
| Scripts | `raw/measure.py` (one run), `raw/run_batch.py` (the batch, with the spend check), `raw/make_report.py` (this table), `raw/key_usage.py` (key usage, value never printed) |
| Raw output | `raw/before/*.jsonl`: every token, citation, trust signal and the `done` event, plus spies on the restatement drop, the no-summary note builders and the writer's findings |

Questions, exact text from `testing/Test_queries_and_workflows.md`:

| Key | Question |
|---|---|
| q116_orthologs | What are the known orthologs of TP53 in other species? |
| q022_cftr_variants | Which clinically significant variants have been reported in CFTR? |
| q078_mody_genes | What genes are associated with MODY? |
| q104_pmid_data | What sequence data is linked to PMID 11237011? |
| rs334_rs6025 | What are rs334 and rs6025? |
| q037_colistin | Which E. coli isolates in Pathogen Detection carry colistin resistance genes? |

Column meanings: "Written summary shown" is every summary-placed sentence other than the code-built count line ("Found N ..." or "I found N ..."). "Restatements dropped" is "not run" when the structured fallback ran instead. "Fallback" is `structured_fallback_used`, read from which note builder fired. "Tier" is the answer-scope risk tier.

## Per run

| Question | Depth | Run | Written summary shown | No-summary note | Trust | Tier | Restatements dropped | Fallback | Seconds |
|---|---|---|---|---|---|---|---|---|---|
| q116_orthologs | researcher | 1 | none | yes | ask | low | not run | yes | 28.49 |
| q116_orthologs | researcher | 2 | none | yes | ask | low | not run | yes | 24.3 |
| q116_orthologs | plain_language | 1 | none | yes | ask | low | not run | yes | 22.92 |
| q116_orthologs | plain_language | 2 | none | no | answer | low | 29 | no | 18.93 |
| q022_cftr_variants | researcher | 1 | none | yes | ask | low | not run | yes | 15.19 |
| q022_cftr_variants | researcher | 2 | Further variants are NM_000492.4(CFTR):c.3498C>G (p.Phe1166Leu) at ClinVar:1036122 [21], NM_000492.4(CFTR):c.3508C>T (p.Pro1170Ser) at ClinVar:1003660 [3], and NM_000492.4(CFTR):c.3590A>G (p.His1197Arg) at ClinVar:1037208 [23]. | no | ask | low | 0 | no | 16.13 |
| q022_cftr_variants | plain_language | 1 | none | yes | ask | low | not run | yes | 14.45 |
| q022_cftr_variants | plain_language | 2 | Others include ClinVar:1003660, named NM_000492.4(CFTR):c.3508C>T (p.Pro1170Ser) [3], ClinVar:1007213, named NM_000492.4(CFTR):c.2131T>C (p.Phe711Leu) [4], and ClinVar:1009171, named NM_000492.4(CFTR):c.1051A>G (p.Thr351Ala) [5]. Additional named variants are ClinVar:1009391, which is NM_000492.4(CFTR):c.2950G>A (p.Asp984Asn) [6]. Further variants are ClinVar:1029874, named NM_000492.4(CFTR):c.389T>C (p.Leu130Pro) [17]. | no | ask | low | 17 | no | 14.42 |
| q078_mody_genes | researcher | 1 | none | yes | ask | high | not run | yes | 10.0 |
| q078_mody_genes | researcher | 2 | none | yes | ask | high | not run | yes | 9.43 |
| q078_mody_genes | plain_language | 1 | The genes are NCBIGene:26060, named adaptor protein, phosphotyrosine interacting with PH domain and leucine zipper 1 [1]. | no | ask | high | 5 | no | 11.24 |
| q078_mody_genes | plain_language | 2 | none | no | ask | high | 5 | no | 9.18 |
| q104_pmid_data | researcher | 1 | none | yes | ask | low | not run | yes | 10.33 |
| q104_pmid_data | researcher | 2 | The assembly records associated with the linked data include GRCh38.p11 [7], GRCh38.p14 [8], GRCh38.p12 [9], GRCh38.p13 [10], and GRCh37.p12 [11]. | no | answer | low | 0 | no | 6.76 |
| q104_pmid_data | plain_language | 1 | none | yes | ask | low | not run | yes | 13.53 |
| q104_pmid_data | plain_language | 2 | none | yes | ask | low | not run | yes | 6.68 |
| rs334_rs6025 | researcher | 1 | The literature variant name c.20A>T [3] and the literature variant name c.1691G>A [4]. | no | ask | high | 0 | no | 14.2 |
| rs334_rs6025 | researcher | 2 | none | yes | ask | high | not run | yes | 12.15 |
| rs334_rs6025 | plain_language | 1 | none | yes | ask | high | not run | yes | 9.06 |
| rs334_rs6025 | plain_language | 2 | none | yes | ask | high | not run | yes | 6.05 |
| q037_colistin | researcher | 1 | none | yes | ask | low | not run | yes | 53.85 |
| q037_colistin | researcher | 2 | none | yes | ask | low | not run | yes | 21.91 |
| q037_colistin | plain_language | 1 | none | yes | ask | low | not run | yes | 53.32 |
| q037_colistin | plain_language | 2 | none | yes | ask | low | not run | yes | 21.09 |

Runs: 24. Model spend the runs report: 0.1703 USD.

The spies `REPAIR_CHECK`, `LISTING_UNCITABLE` and `SECOND_DRAFT_STARTED` were added during the batch, so they are in some repeat 1 files and every repeat 2 file only. They log; they change nothing a run does.

## What the before runs show

- Written summary: 5 of 24 runs show a written sentence, and every one only repeats record names or codes (CFTR HGVS names, GRCh38 assembly names, two LitVar2 names, one MODY gene).
- The no-summary note: 17 of 24 runs carry it (the fallback path). 2 runs reach the other path, a summary dropped whole as restatements with no note: the ortholog Plain language repeat 2 (29 sentences dropped) and the MODY Plain language repeat 2 (5 dropped).
- What the writer was given: one finding per record, its name. 30 ortholog findings all read "tumor protein p53"; each dbSNP record read only its significance or consequence, never its gene; each isolate read only its strain name.
- Time: the ortholog question took 18.9 to 28.5 s, over 20 s in 3 of 4 runs. The colistin question took 21.1 to 53.9 s, every run over 20 s, the isolate scan alone ending about 47 s in on the slow runs. Every other question finished under 17 s.
- Spend: 0.18 USD of model use for the batch and one smoke run, read from the key's usage.
