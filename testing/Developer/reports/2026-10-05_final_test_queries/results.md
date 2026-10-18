# Final test queries on develop, 2026-10-05

Target: develop web app, guest session, fresh per question, headless Chrome at 1280 wide. Runner: `run.mjs` in this folder, run from `<repo-root>/frontend`. API health returned ok (app_env develop) after the 6 minute wait. 10 questions asked, within the budget of 11. No run showed "This run could not be completed", so no reruns. Each run has a .png and a .txt (answer text plus link list). Only page 1 of each paged table is in the text (tables show 10 of 20 per page).

## Item 1, Query 33 E. coli ESBL, Plain language (q33_run1 29.6 s, q33_run2 24.5 s)

- PASS (both runs): table headed "ISOLATES AND THEIR AMR GENES" with isolate, identifier and AMR genes per row, for example "C236-11 SAMN00715300 acrF, aph(3'')-Ib, ... blaCTX-M-15, blaEC, blaTEM-1 ...".
- PASS: note names what was searched: "Searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaCTX-M; blaTEM and blaSHV alleles were not searched: most are not ESBLs and the name alone cannot tell an ESBL allele from a narrow-spectrum one ..."
- Observation, not asked: the count line reads "141,055 Escherichia coli isolates" where the document says 140,476 (the snapshot count moves). Collected column reads "Not recorded" for the first 10 rows. E. coli links to https://www.ncbi.nlm.nih.gov/taxonomy/562.

## Item 2, Query 37 colistin (q37, 31.0 s)

- PASS: isolates with mcr genes in the table, for example KTE156 "acrF, blaEC, mcr-9.1, ..." and 10 of 10 visible rows carry mcr-9.1.
- PASS: note "Searching Escherichia coli isolates ... for AMR genotypes starting mcr." and "Pathogen Detection lists 12,563 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."

## Item 3, Query 24 MLH1 and MSH2 (q24, 15.6 s)

- PASS: "Muir-Torré syndrome" spelled correctly, one row (source 5).
- PASS on page 1: no duplicated row among the 10 visible. Pages 2 and 3 (of 24 rows) were not opened.
- Observation: a note reads "this answer does not address the following entities named in the question: Colorectal cancer. Ask about them individually for a complete answer." It is not a "did not finish" line. The trust line reads "Based on 24 sources, not yet confirmed" with "High-risk claim".

## Item 4, SARS-CoV-2 SRA runs (sars, 8.8 s)

- FAIL: answer is about the disease SARS. Text: "I found 3 conditions related to SARS." Sources: "SARS Coronavirus Protease Pathway", "Probable SARS (severe acute respiratory syndrome)", "SARS (severe acute respiratory syndrome) confirmed". No SRA runs, no SARS-CoV-2 records. Same wrong entity as the card 56 diagnosis.

## Item 5, PMID 11237011 linked data (pmid, 23.0 s)

- PASS: linked records listed with NCBI links (nuccore, bioproject, assembly records; "I found 5 records, 2 research projects, 1 sequencing dataset and 5 genome assemblies related to PMID 11237011.").
- PASS: plain sentences "NCBI lists no linked BioSamples for PMID 11237011." and "NCBI lists no linked GEO records for PMID 11237011."
- Observation: counts sentences "NCBI lists 1587 sequence records linked to PMID 11237011; this answer shows 10." The "direct, inferred, or absent" marking asked for in the question text is not shown on the page.

## Item 6, Mediterranean, Plain language (med_run1 12.0 s, med_run2 11.2 s)

- PASS (both): names Familial Mediterranean fever. Run 1: "Familial Mediterranean fever is a condition caused by mutations in the MEFV gene ...". Run 2: "Another set of studies focuses on Familial Mediterranean fever, a condition caused by mutations in the MEFV gene ...".
- PASS (both): a written answer with sentences above the paper list, opening "I found 5 published papers on this topic."

## Item 7, Query 75 GERD at Researcher (gerd_researcher, 12.5 s after the ask-back pick "What are the symptoms and treatments for GERD?")

- PASS: written prose above the tables, under "SYMPTOMS AND DIAGNOSIS" and "COMPLICATIONS", then the PubMed, MedGen, literature entity and trial tables. The bare GERD was asked back first, as the document says.

## Item 8, Query 25 TP53 GEO datasets (q25, 16.1 s)

- PASS: no "did not finish" line. The only note reads "Note: this answer was truncated because only 60 of the 125 records that matched this question in the graph were retrieved".
- Observation: the visible sources are a gene, papers and variants, plus two GEO titles (HCT116 CRISPR screen, HCT116 TP53 KO RNA-seq). The trust line reads "Sources disagree on at least one claim". The answer says "I found 1 gene related to TP53" and does not describe the GEO series.

## Summary

| Item | Question | Result | Time |
|---|---|---|---|
| 1 | Query 33, twice | PASS, PASS | 29.6 s, 24.5 s |
| 2 | Query 37 | PASS | 31.0 s |
| 3 | Query 24 | PASS (page 1 only) | 15.6 s |
| 4 | SARS-CoV-2 SRA runs | FAIL, answered about the disease SARS | 8.8 s |
| 5 | PMID 11237011 | PASS | 23.0 s |
| 6 | Mediterranean, twice | PASS, PASS | 12.0 s, 11.2 s |
| 7 | Query 75 GERD Researcher | PASS | 12.5 s |
| 8 | Query 25 TP53 GEO | PASS | 16.1 s |

Housekeeping: stdout logs l1.log to l10.log are in this folder; a delete was blocked by a hook, so they remain.
