# Retest runner A results

- Time run: 2026-09-29 (started with develop /health check)
- Develop /health: `{"status":"ok","app_env":"develop"}`
- Account: s3-retest-a-20260929@example.com
- Evidence folder: `<repo-root>/testing/Developer/reports/2026-09-29_retest/runner_A/` (screenshots are full page at 1280 wide; each .txt is the saved answer text plus its link list)

## Query 3. The answer-modes info button explains who each mode is for (11.36)

- PASS: the "i" beside the mode selector opens a card "Answer modes" describing Plain language ("the answer in simple terms, easy to understand") and Researcher ("the answer in technical terms, with the specifics and the records listed or in tables"). Evidence: q3_info_card.png, q3_info_card.txt
- PASS: the card describes who each mode is for, as above (wording is about the kind of answer each gives, not a named audience). Evidence: q3_info_card.txt
- PASS: no word count or paragraph count promised anywhere in the card. Evidence: q3_info_card.txt

## Query 4. The mode locks once a search starts (9.12)

- PASS: after clicking Search on `Which diseases are associated with BRCA1?`, the running screen has no answer mode control at all (no Researcher or Plain language button could be found or clicked, click timed out). The answer then landed normally in Plain language, not a mix. Evidence: q4_running.png, q4_after_click_attempt.png, q4_notes.txt, q4_q6_answer_brca1.png
- PASS (note): the selector is removed on the run screen rather than shown greyed out, and the `depth-locked` marker did not appear (count 0). The lock holds in effect. Evidence: q4_notes.txt
- NOT TESTABLE: "a change only applies to the next question", since no change can be made mid-search; the info card says "A change applies to your next question." Evidence: q3_info_card.txt

## Query 6. Copying an answer carries no citation-card text (11.14)

- PASS: selecting the whole answer area and reading the selection string (3,175 characters) gave prose and table text with citation digits only (for example "...group S.1–4", "6"). Zero matches for "Source N", "Sources N" or "layer N". Evidence: q6_selection.txt, q6_selected.png
- NOT TESTABLE: screen reader announcement of each citation (needs a screen reader). Citation aria labels are captured in the .txt link/aria sections of later queries where present.

## Query 9. Two visits show different scientists but the same answer (8.4)

- PASS: the persona is chosen per visit and did not change what was found (both visits found the same records, see the third line). Evidence: q9_visit1.txt, q9_visit2.txt
- PASS: two separate fresh browser contexts showed different scientists, "Working as Crick" and "Working as Chase". Evidence: q9_visit1.png, q9_visit2.png
- PASS (note): both visits found the same four disease records (Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, Fanconi anemia complementation group S) and the same gene, ClinVar and OMIM records. The wording differed, visit 1 cited 22 sources and visit 2 cited 23, and one PubMed paper differed (PMID 19168207 in visit 1, 35432218 in visit 2). This matches the doc's "Known" entry that the same PubMed search can return a slightly different set. Evidence: q9_visit1.txt, q9_visit2.txt

## Query 23. rs334 without invented conditions

- PASS: the question's own words were not mistaken for a disease name; no condition list appears. Evidence: q23.png, q23.txt
- PASS: the answer ends with sources and no note listing conditions: no "Patient condition unchanged", no "Condition of fetal membrane". Evidence: q23.txt
- Note (not a bullet): the answer says "Found 1 variant record record and 4 literature variant records for rs334: not-provided, protective, likely-benign, pathogenic, other, rs334348, rs334353, c.-50T>C and rs334773" and never says sickle cell or a condition name. Not graded, science is outside the bullet. Evidence: q23.txt

## Query 24. Comparing two genes in a disease context (G-033)

- PASS: both genes' records are present: mutL homolog 1 NCBIGene:4292 and mutS homolog 2 NCBIGene:4436. Evidence: q24.png, q24.txt
- PASS: both genes' condition records are among the sources: Lynch syndrome 1 (MedGen C2936783), Mismatch repair cancer syndrome 1 (C5399763) and 2 (C5436806), Colorectal cancer hereditary nonpolyposis type 2 (C1333991), Muir-Torre syndrome. Evidence: q24.txt
- PASS: no line saying a background search did not finish. Evidence: q24.txt
- Note (not a bullet): the Notes section says "this answer does not address the following entities named in the question: Colorectal cancer. Ask about them individually for a complete answer." Evidence: q24.txt

## Query 25. GEO expression datasets for TP53 (G-037), run twice

- PASS (both runs): a dataset question searched GEO and cited real series (GSE288828, GSE303273, GSE308433, GSE308434, GSE308435), and the answer never says the question's wording is a disease. Evidence: q25_run1.png, q25_run2.png
- PASS (both runs): GEO series are among the sources and each links to an NCBI page of the form https://www.ncbi.nlm.nih.gov/gds/2002888xx (links not clicked). Evidence: q25_run1.txt, q25_run2.txt
- FAIL (both runs): a background-search line is shown. Exact text seen: "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry." Evidence: q25_run1.txt, q25_run2.txt
- PASS (both runs): no closing note listing mouse tumour records. The Notes section holds only the truncation note ("only 59 of the 124 records that matched this question in the graph were retrieved") and the background line above. Evidence: q25_run1.txt, q25_run2.txt

## Query 27. The same window, with genes and overlapping records asked for by name

- PASS: the window resolved to real genes and records (BRCA1 NCBIGene:672 plus 37 ClinVar sequence variant records and 8 ClinVar records) instead of asking for a gene. Evidence: q27.png, q27.txt
- PASS: BRCA1 is named without the person naming it. Evidence: q27.txt
- FAIL: dbVar records are not among the sources. ClinVar records are, with NCBI links (not clicked), but the text and link list hold no dbVar record (the only "dbVar" hits are the question echoed back). Evidence: q27.txt
- PASS: no request to name a gene and no classification of the variant. Evidence: q27.txt
- Note (not a bullet): Notes says "this answer does not address the following entities named in the question: RPL21P4, LOC127886930, LOC129664047, ..." although the question named none of them. Evidence: q27.txt

## Query 28. A window with no assembly named

- PASS: asked which assembly instead of guessing. Exact text: "These coordinates could be on GRCh38 or GRCh37, and the two put different genes under the same numbers. Add the assembly to the question, for example "on GRCh38", and I will search." Evidence: q28.png, q28.txt
- PASS: one question back naming GRCh38 or GRCh37 and why it matters (different genes under the same numbers). Evidence: q28.txt

## Query 29. A CFTR-locus window

- PASS: the chr7 window resolved to CFTR (NCBIGene:1080). Evidence: q29.png, q29.txt
- PASS: CFTR is named first, with CFTR-AS1 and CFTR-AS2 beside it in the opening sentence. Evidence: q29.txt
- PASS: the literature (for example "Molecular Structure of the Human CFTR Ion Channel", PMID 28340353) and OMIM (omim 602421, CFTR) content is about CFTR. Evidence: q29.txt
- FAIL: ClinVar records are among the sources, but no dbVar record is (the only "dbVar" hit is the question text of another search in the history list). Evidence: q29.txt
- Note (not a bullet): Notes says "this answer does not address the following entities named in the question: CFTR-AS1, CFTR-AS2, LOC111674463, ..." although the question named none of them and the opening sentence already names CFTR-AS1 and CFTR-AS2. Evidence: q29.txt

## Query 30. A BioProject accession with everything it links to (G-007)

- PASS: answered with the actual project record and its links, no request for a gene. Evidence: q30.png, q30.txt
- PASS: the project record "The Human Genome Project, currently maintained by the Genome Reference Consortium (GRC)" (PRJNA31257) is among the sources. Evidence: q30.txt
- PASS: BioSample SAMN12121739, SRA run SRR9496657 and assembly GRCh38.p14 (GCF_000001405.40) are each cited with an NCBI page link (bioproject/31257, biosample/12121739, sra/8317276, assembly/11968211; not clicked). The answer does not add a written "how to retrieve" sentence beyond those links. Evidence: q30.txt
- PASS: no request to name a gene. Evidence: q30.txt

## Query 31. An accession NCBI does not have

- PASS: an honest not-found. Exact text: "BioProject PRJNA999999999 was not found in NCBI. Check the accession and ask again." Evidence: q31.png, q31.txt
- PASS: one line back, as above. Evidence: q31.txt
- PASS: no request to name a gene. Evidence: q31.txt

## Query 32. A BioSample accession and its runs

- PASS on the second try: the first attempt ended with "This run could not be completed. Try asking again, or rephrase the question. Not verified · the run did not finish" (q32.png). The retry resolved to the BioSample record and its SRA runs. Evidence: q32_retry.png, q32_retry.txt
- PASS: the BioSample record (SAMN12121739) and five SRA runs (SRR9504670 to SRR9504674) are among the sources (the bullet allows up to ten). Evidence: q32_retry.txt
- PASS: no "which gene, variant or condition do you mean?" request. Evidence: q32_retry.txt
- Note: the first-attempt failure is worth a look, since a person would see it as a dead end. Evidence: q32.png

## Query 33. The flagship question: E. coli and ESBL genes (G-035, isolate query 1)

Run in the default Plain language mode (wf1_ecoli_esbl_then_2023), and once in Researcher mode as a probe (q33_researcher_probe).

- FAIL: in the default mode there is no table headed "Isolates and their AMR genes". Seen: "I found 20 pathogen samples and 1 organism related to Escherichia coli" and a list of names only (C236-11, 11-3677, ...) with no genes and no collection details. In Researcher mode the table appears with 20 rows (10 per page), AMR genes listed (blaCTX-M-15 in every visible row), each row linking to Pathogen Detection, but the Collected column is empty in those rows. Evidence: wf1_ecoli_esbl_then_2023.png, q33_researcher_probe.png
- FAIL: the count line has the right shape but a different number. Seen: "Pathogen Detection lists 140,867 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." The doc expects 140,476 (possibly a newer snapshot). Evidence: wf1_ecoli_esbl_then_2023.txt
- FAIL: no note that only the blaCTX-M family was searched for "extended-spectrum beta-lactamase", in either mode. Evidence: wf1_ecoli_esbl_then_2023.txt, q33_researcher_probe.txt
- PASS: E. coli is linked to its NCBI Taxonomy record (NCBITaxon:562 in Researcher mode, a taxonomy link in the default mode). Evidence: q33_researcher_probe.txt, wf1_ecoli_esbl_then_2023.txt
- PASS: the answer arrived in 29.6 s (34.3 s including submit; Researcher mode 32 s). Evidence: wf1_ecoli_esbl_then_2023.txt

## Query 35. An exact gene, one allele only (isolate query 3)

- NOT TESTABLE: whether every isolate shown carries blaCTX-M-15, since this answer lists 20 isolate names (8891, A54560, ...) and shows no gene lists. Evidence: q35.png
- PASS: the "first 20 shown" note is present. Evidence: q35.txt
- FAIL: the count reads 2,684, the doc expects 2,678 (possibly a newer snapshot). Exact text: "Pathogen Detection lists 2,684 Salmonella isolates with these genes; the first 20 in the snapshot are shown." Evidence: q35.png
- PASS: no mention of other ESBL families. Evidence: q35.txt

## Query 36. Carbapenemase genes in Klebsiella (isolate query 4)

- PASS: real isolates are returned (20 isolates, KPNIH4, KPNIH5, ...), each linked to a Pathogen Detection page. Evidence: q36.png, q36.txt
- FAIL: no full gene lists are shown, and the answer does not name which gene prefixes it searched. Evidence: q36.png
- FAIL: count reads 88,213, the doc expects 88,025 (possibly a newer snapshot). The first-20 note is present. Evidence: q36.txt

## Query 38. A gene nothing in this organism carries (isolate query 6)

- PASS: an honest zero, not a refusal. Exact text: "Pathogen Detection lists 0 Listeria isolates with these genes, all shown." Evidence: q38.png, q38.txt
- PASS: no isolate rows. Evidence: q38.txt
- PASS: no suggestion the search failed, and no request for a gene name. Evidence: q38.txt
- PASS: Listeria is cited to NCBI Taxonomy (https://www.ncbi.nlm.nih.gov/taxonomy/1637). Evidence: q38.txt

## Query 39. An organism Pathogen Detection does not cover (isolate query 7)

- PASS: honest explanation, no empty or invented result. Evidence: q39.png, q39.txt
- PASS: one question back. Exact text: "Pathogen Detection is searched one organism at a time. Which organism do you mean? For example Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae or Campylobacter." Evidence: q39.txt
- PASS: it does not claim whether tomato is or is not covered. Evidence: q39.txt
- PASS: no isolate rows, no invented data. Evidence: q39.txt

## Query 40. An organism named with no gene (isolate query 8)

- PASS: a clarifying question instead of a dump. Evidence: q40.png, q40.txt
- PASS: it asks which gene or family, with ESBL, carbapenemase, colistin (mcr) and a gene name (blaCTX-M-15) offered. Exact text: "Which resistance gene or gene family should the isolates carry? For example ESBL (the blaCTX-M family), carbapenemase (blaKPC, blaNDM, blaOXA-48, blaVIM, blaIMP), colistin resistance (mcr), or a gene name such as blaCTX-M-15." Evidence: q40.txt
- PASS: no isolate list and no total shown. Evidence: q40.txt

## Query 44. The shortest version a person would type (isolate query 12)

- PASS: the terse question was understood as an E. coli ESBL isolate search (20 isolates listed). Evidence: q44.png, q44.txt
- FAIL: not the same shape as query 33: no genes shown per isolate and no blaCTX-M-only disclosure. Present: isolate list with links, "Pathogen Detection lists 140,867 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown.", and a taxonomy link. Evidence: q44.png, q44.txt
- PASS: the phrasing was understood the same way as query 33 (same isolates, same count). Evidence: q44.txt, wf1_ecoli_esbl_then_2023.txt

## Extra: isolate document workflow (only some of its twelve queries fit the budget; its queries 1, 3, 4, 6, 7, 8 and 12 are queries 33, 35, 36, 38, 39, 40 and 44 above; query 11 was not run)

### Isolate 2. The same question on Salmonella

- PASS on the second try: the first attempt ended "This run could not be completed" (wf2_salmonella_esbl.png). Retry: table "Isolates and their AMR genes" with 20 rows (10 shown per page), genes, links, "Pathogen Detection lists 20,346 Salmonella isolates with these genes; the first 20 in the snapshot are shown.", and Salmonella cited as NCBITaxon:590. Evidence: wf2b_salmonella_esbl.png, wf2b_salmonella_esbl.txt
- FAIL: no note that only the blaCTX-M family was searched. Evidence: wf2b_salmonella_esbl.txt
- Note: this run used the same default mode as the E. coli run, yet showed the gene table, so the answer shape varies from run to run in the default mode.

### Isolate 5. Colistin resistance in E. coli

- FAIL: no isolates, and the answer says "Pathogen Detection lists 0 Escherichia coli isolates with these genes, all shown." The doc expects isolates carrying an mcr gene with their gene sets. A zero here looks wrong, since the Salmonella table above lists isolates carrying mcr-9.1. No mcr prefixes are named. Evidence: wf5_ecoli_colistin.png, wf5_ecoli_colistin.txt

### Isolate 9. A follow-up asking to filter by year

- FAIL: after the E. coli answer, `Show me the ones from 2023` ended with "This run could not be completed. Try asking again, or rephrase the question. Not verified · the run did not finish". The doc expects a question back asking which organism or gene. A second try started from a first turn that itself failed, so its follow-up got "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question." Evidence: wf1_ecoli_esbl_then_2023_followup.png, wf1b_ecoli_esbl_then_2023_followup.png

### Isolate 10. The existing single-isolate lookup

- FAIL: the answer says "The isolate SAMN02147118 is a pathogen sample from Salmonella enterica" with a source "SRR863221". It shows no strain, no collection place or date, no resistance genes and no Pathogen Detection link, all of which the doc expects. PASS on the other bullet: no "first 20" note or isolate count. Evidence: wf10_single_isolate.png, wf10_single_isolate.txt

## Summary table

| Query | Bullets passed of testable | Verdict |
|-------|----------------------------|---------|
| 3 | 3 of 3 | PASS |
| 4 | 2 of 2 (1 not testable) | PASS |
| 6 | 2 of 2 (2 not testable) | PASS |
| 9 | 3 of 3 | PASS |
| 23 | 2 of 2 | PASS |
| 24 | 3 of 3 | PASS |
| 25 | 3 of 4 (both runs) | FAIL |
| 27 | 3 of 4 | FAIL |
| 28 | 2 of 2 | PASS |
| 29 | 3 of 4 | FAIL |
| 30 | 4 of 4 | PASS |
| 31 | 3 of 3 | PASS |
| 32 | 3 of 3 (passed on second try) | PASS |
| 33 | 2 of 5 | FAIL |
| 35 | 2 of 3 (1 not testable) | FAIL |
| 36 | 1 of 3 | FAIL |
| 38 | 4 of 4 | PASS |
| 39 | 4 of 4 | PASS |
| 40 | 3 of 3 | PASS |
| 44 | 2 of 3 | FAIL |
| Isolate 2 | 1 of 2 | FAIL |
| Isolate 5 | 0 of 1 | FAIL |
| Isolate 9 | 0 of 1 | FAIL |
| Isolate 10 | 1 of 2 | FAIL |
