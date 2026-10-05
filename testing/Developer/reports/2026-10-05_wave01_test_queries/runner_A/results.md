# Wave 01 test queries, runner A

Target: develop web and API (API /health reported app_env develop). Guest session, fresh browser context per question, 1280 wide, Chrome channel via Playwright from `<repo-root>/frontend/node_modules`. Driver: `run_one.mjs` in this folder. Each run has `<label>.png` (full page), `<label>.txt` (answer text, answer meta line, link list) and `<label>.meta.txt` (timing, clarifying options, pick made).

Questions used: 13 of 16 (one probe of `GERD` at Researcher, `probe.*`, plus 12 scored runs). No run showed "This run could not be completed", so no guard-issue rerun was needed.

## Table of contents

- Deviation that affects queries 75 and 68
- Query 75
- Query 68
- Query 27
- Query 29
- Query 25
- Query 24
- Other things seen
- Summary

## Deviation that affects queries 75 and 68

The pick "What are the typical symptoms and risk factors of GERD?" was never offered. The classifier writes the choices each time. Across the probe and six runs the four choices were variants of: what is GERD, which genes, clinical trials, recent research. Query 68 run 1 and run 2 offered "What are the common symptoms and complications of GERD?", which the script picked. Everywhere else the script picked the closest option, "What is GERD?" (or its longer variant). Options offered per run are in each `.meta.txt`.

## Query 75, GERD at Researcher (3 runs)

Bullets: (a) no paragraph starts lowercase or with a stray quote, (b) no "Another is titled" with no first paper, (c) no restatement paragraph, each paper at most twice, (d) Researcher answer has prose on symptoms, complications and treatment above the list and is longer than Plain language, (e) bare GERD is asked back first. Key check: a written answer above the tables.

| Run | Pick made | Time (answer line) | a | b | c | d | e | Key check |
|---|---|---|---|---|---|---|---|---|
| 1 | What is GERD and its associated conditions? | 22.9 s | PASS | PASS | PASS | PARTIAL | PASS | PASS |
| 2 | What is GERD? | 19.3 s | PASS | PASS | PASS | PASS | PASS | PASS |
| 3 | What is GERD? | 14.1 s | PASS | PASS | PASS | PARTIAL | PASS | PASS |

Evidence: `q75_run1`, `q75_run2`, `q75_run3`.

- Run 1: prose has a definition, "ASSOCIATED COMPLICATIONS" (erosive esophagitis, strictures, Barrett esophagus) and treatment (PPIs). Symptoms appear only as "producing symptoms or complications". Marked PARTIAL.
- Run 2: "Clinical manifestations in young children are varied and nonspecific", complications, and "TREATMENT AND MANAGEMENT". All three topics present.
- Run 3: prose is "In young children, clinical manifestations are varied and nonspecific", "GERD is a clinical diagnosis." under PATHOGENESIS, and a treatment paragraph. No complications. PARTIAL.
- Researcher versus Plain language length: Researcher prose about 143, 150 and 101 words; Plain language (query 68) about 62, 110 and 117. Researcher is longer on average but not in every pairing, and the picks differ.
- Bullet c: the titles "Gastroesophageal Reflux Disease." repeat in the list, but each row has its own PMID, so no paper is restated.

## Query 68, GERD in Plain language (3 runs)

Bullets: (a) answers with cited records, not "could not find grounded evidence", (b) the bare name is asked back, then a pick answers, (c) trials question returns ClinicalTrials.gov studies each with its own page (checked through the five trials in this answer), (d) the abbreviation works. The `reflux disease` and `Any trials for GERD?` runs were not in my assignment.

| Run | Pick made | Time | a | b | c | d | Notes |
|---|---|---|---|---|---|---|---|
| 1 | What are the common symptoms and complications of GERD? | 17.1 s | PASS | PASS | PASS | PASS | Prose is one sentence: "GERD can affect a person's quality of life." |
| 2 | What are the common symptoms and complications of GERD? | 12.9 s | PASS | PASS | PASS | PASS | Names heartburn and regurgitation, cites 14 sources |
| 3 | What is GERD? | 13.2 s | PASS | PASS | PASS | PASS | Definition, complications, children note |

Evidence: `q68_run1`, `q68_run2`, `q68_run3`. Each answer lists 5 papers, 1 condition, 1 literature entry and 5 NCT trials, each with a study link. Run 1 answers a symptoms question without naming a single symptom, so as an answer to the question picked it is thin, although the bullets as written pass.

## Query 27, chr17 window (1 run)

Bullets: (a) the window resolves to real genes and records, (b) BRCA1 named without the person naming it, (c) dbVar and ClinVar records among the sources, working links, (d) no request to name a gene, no classification of the variant. Key check: dbVar records with NCBI links.

| a | b | c | d | Key check | Time |
|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | 15.2 s |

Evidence: `q27_run1`. Seen: "Found 1 gene record and 34 sequence variant records for BRCA1, RPL21P4, ..."; "DBVAR RECORDS FOUND" with 5 rows such as "copy number variation overlapping NBR2, BRCA1 (chr17:43120665-43127881, GRCh38)"; links of the form `https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv7897034/`; ClinVar links to `/clinvar/variation/...`. No gene request and no pathogenicity class.

## Query 29, CFTR window (1 run)

Bullets: (a) right gene and surrounding records, (b) CFTR first with CFTR-AS1 and CFTR-AS2 beside it, (c) literature and OMIM about CFTR, (d) ClinVar and dbVar among the sources. Key check: dbVar records with NCBI links.

| a | b | c | d | Key check | Time |
|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | 18.3 s |

Evidence: `q29_run1`. Seen: "Found 1 gene record and 43 sequence variant records for CFTR, CFTR-AS1, CFTR-AS2, LOC111674463, ..."; PubMed papers on CFTR (PMID:28340353 and others); OMIM 602421 CFTR; 5 dbVar rows ("copy number variation overlapping CFTR, CFTR-AS1 ...") linking to `https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv7559356/`.

## Query 25, TP53 GEO datasets (3 runs)

Bullets: (a) searches GEO and cites real series, wording not mistaken for a disease, (b) GEO series among the sources each linking to an NCBI GEO DataSets page, (c) no "background search did not finish" line, (d) no closing note listing mouse tumour records. Key check: (c).

| Run | Time | a | b | c | d | Key check |
|---|---|---|---|---|---|---|
| 1 | 14.6 s | PASS | PASS | PASS | PASS | PASS |
| 2 | 14.9 s | PASS | PASS | PASS | PASS | PASS |
| 3 | 12.5 s | PASS | PASS | PASS | PASS | PASS |

Evidence: `q25_run1`, `q25_run2`, `q25_run3`. Each shows "GDS RECORDS FOUND" with 5 series (GSE300999, GSE301000, GSE301001, GSE315988, GSE349532) linking to `https://www.ncbi.nlm.nih.gov/gds/2003...`. A text search for "did not finish" and "background search" over all files found nothing. The only note in each is "this answer was truncated because only 60 of the 125 records that matched this question in the graph were retrieved". Caveat on (a): the series are HCT116 cell line and leukemia studies, not obviously "human tumour samples", and the answer's own lead is about the TP53 gene. The bullet as written passes.

## Query 24, MLH1 and MSH2 (1 run)

Bullets: (a) both genes' records, not a note that a search did not finish, (b) both genes' condition records among the sources, (c) no line saying a background search did not finish.

| a | b | c | Time |
|---|---|---|---|
| PASS | PASS | PASS | 19.0 s |

Evidence: `q24_run1`. Gene rows for mutL homolog 1 (NCBIGene:4292) and mutS homolog 2 (NCBIGene:4436); disease rows include "Lynch syndrome 1", "Colorectal cancer, hereditary nonpolyposis, type 2", "Mismatch repair cancer syndrome 1" and "2". Only note: "does not address the following entities named in the question: Colorectal cancer". The papers, ClinVar and OMIM rows are all MLH1 only, with nothing for MSH2 beyond its gene and condition rows, so the comparison is lopsided though the bullets pass.

## Other things seen

- Raw bracket markers in the lead sentence of queries 27 and 29: "...LOC111589215[21][22][23]...[35].⁠1–20". Not covered by a bullet.
- OMIM row repeated twice in queries 27, 29, 25 and 24 (same record, same marker).
- Query 24 shows "Muir-TorrÃ© syndrome", a character encoding defect in a disease name.
- Header icon is "?" instead of a check on q27, q29, q25 run 2 and q24, with "Based on N sources, not yet confirmed". Query 25 runs 1 and 3 show "Sources disagree on at least one claim".
- Query 68 and 75 clarifying choices vary per run and never included the symptoms and risk factors question the test names.

## Summary

| Query | Runs | Bullets passed | Verdict |
|---|---|---|---|
| 75 | 3 | 15 of 15 on a, b, c, e and the key check; bullet d PASS 1 of 3, PARTIAL 2 of 3 | PASS on key check, bullet d partial; the named pick was not offered |
| 68 | 3 | 12 of 12 | PASS (run 1 prose is thin) |
| 27 | 1 | 5 of 5 | PASS |
| 29 | 1 | 5 of 5 | PASS |
| 25 | 3 | 15 of 15 | PASS |
| 24 | 1 | 3 of 3 | PASS |
