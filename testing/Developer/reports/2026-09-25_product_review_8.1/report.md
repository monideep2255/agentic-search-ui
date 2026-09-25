# Product review, build phase 8.1: good questions stop failing

Pre-screen for the product owner's retest of build phase 8.1, live on develop at 6bbe7f5 (product code from pull request #105, golden run against deployed commit 5bac18a). Reviewer: the product reviewer agent, 2026-09-25. It files, it closes nothing. Develop confirmed first: `/health` returned `{"status":"ok","app_env":"develop"}` at 10:25:25 UTC (health.json).

## Table of contents

- [Verdict](#verdict)
- [The golden result](#the-golden-result)
- [What to look at first](#what-to-look-at-first)
- [Rubric grades per question](#rubric-grades-per-question)
- [Screens and designs](#screens-and-designs)
- [What was not captured, and why](#what-was-not-captured-and-why)
- [What rests on my own read and what rests on a summary](#what-rests-on-my-own-read-and-what-rests-on-a-summary)
- [Findings log, written as each was established](#findings-log-written-as-each-was-established)

## Verdict

- Golden run: clear. 99 of 150 answered against the floor of 86, zero rate-limit signals. It does not block.
- The 99 is not 99 good answers. All 99 answered runs open with a record count ("Found ..."). Of the 17 golden questions whose answers I read, 11 fail rubric line 2. G-005 went from an honest refusal to a wrong-kind answer and supplies 3 of the 13 gained runs.
- Card 1, the Marfan phenotype question: at Researcher on develop it now names MedGen features, cited, with HPO ids as table cells. It went wrong 2 of the 6 times it was asked here: golden pass 1 answered with FBN1 variant records listed twice, and Plain language on develop gave no answer in 623 seconds.
- Card 3: sources are no longer held at 20, but the card's "up to 30" is not what a person sees. 28 of 99 answered runs show more than 30 sources, up to 75, and footnotes run to [84] under "Based on 13 sources".
- A new sentence from this phase, "MedGen lists no clinical features for X", now appears in 15 answers to questions that did not ask about features. One of them repeats "Seen by breast cancer nurse" twice.

## The golden result

- Answered: 99 of 150, floor 86 (the 2026-09-22 run at 63ec316). Clear, not blocked.
- Rate-limit signals: 0. The run counts.
- Questions that got worse than 2026-09-22:
  - G-004: 3 to 0. It now asks a clarifying question instead of the old wrong answer. Better for a person, but it asks the wrong thing (PR-8.1-21).
  - G-006: 2 to 0. Every pass waits 96 to 98 seconds for "One of my searches did not finish" (PR-8.1-20).
  - G-046 (1 to 0) and G-047 (2 to 0) are the BLAST and VCF requests. Their refusals are correct, and "worse" there is an improvement.
- Never answered: 17 questions. 13 are refusals the golden set expects. Four fall outside their acceptable outcomes on every pass: G-004, G-006, G-036 and G-038 ("Tell me about the tree of life.", refused as off topic). G-036 is a good question that gets a clarifier asking "which gene, variant or condition" (PR-8.1-25).
- A gain that is not an answer: G-005, 0 to 3, now answers an SRA question with "SARS Coronavirus Protease Pathway" (PR-8.1-04).
- Time to answer, answered runs: median 21.1 s, p90 33.6 s, worst 103.6 s (G-012 pass 3). All runs: 17.1 / 32.7 / 103.6.
- Answered questions over 25 seconds on at least one pass, 19 of them: G-002, G-005, G-010, G-011, G-012, G-013, G-016, G-017, G-018, G-021, G-022, G-025, G-030, G-031, G-032, G-033, G-035, G-039, G-040. Pass-by-pass seconds are in PR-8.1-22.
- Live on develop, eight asks: 21.5, 26.0, 21.5, 13.3, 25.8, 28.3, 10.8 seconds, plus one with no answer after 623 s. In every run that answered, the first answer text arrived with the last, so no text streams before the whole answer lands.

## What to look at first

Fails first, then "needs your eye", each with its question, depth, sentence and file.

1. Fail. Marfan phenotype, Plain language, live: no answer in 623 s, run_id fe226f3f-fbeb-48e1-bb90-85ab65c3fece. File: raw/MARFAN_plain_language.json. This is card 1's first check, so ask it yourself first (PR-8.1-28).
2. Fail. Marfan phenotype, Researcher, golden pass 1: "Found 23 sequence variant records and 23 derived records for Marfan syndrome", with every ClinVar id listed twice. Passes 2 and 3 answered well. File: 2026-09-25_phase_8.1_golden/raw/G-022_run1.json (PR-8.1-02).
3. Fail. G-005 SRA runs of SARS-CoV-2, Researcher: "Found 1 medgen record for SARS: SARS Coronavirus Protease Pathway [1]." It was an honest refusal before this phase. File: raw/G-005_run1.json (PR-8.1-04).
4. Fail. G-034 how many genes for breast cancer, Researcher: "MedGen lists no clinical features for Seen by breast cancer nurse [1]." printed twice, and no count of genes. File: raw/G-034_run1.json (PR-8.1-05).
5. Fail. G-006 PMID 11237011 links, Researcher: 96 to 98 s on every pass, then "One of my searches did not finish". File: raw/G-006_run1.json (PR-8.1-20).
6. Fail. G-024 rs334, Researcher: lists "rs334348 [2], rs334353 [3] ... rs334773 [5]" as rs334's records and never names sickle cell. This was already there before this phase. File: raw/G-024_run1.json (PR-8.1-06).
7. Fail. G-018 TP53 location, Researcher: "TP53 operates in the nucleus ... [1]", cited to the Gene 7157 summary, which never says nucleus. File: raw/G-018_run1.json (PR-8.1-08).
8. Fail. Answers that do not answer, Researcher, golden:
   - G-028 APOE and Alzheimer: no sentence on e4 or Alzheimer risk (PR-8.1-09).
   - G-039 the student BRCA1 question: answered with ferroptosis (PR-8.1-10).
   - G-025 MTHFR C677T: "The records include ClinVar:1004148 [1] and ClinVar:1042278 [2]." (PR-8.1-12).
   - G-021 CFTR papers: 54 bare PMIDs (PR-8.1-16).
   - G-030 EGFR in lung cancer: no written answer (PR-8.1-17).
9. Fail. G-033 MLH1 versus MSH2, both depths, live and golden: no comparison, MSH2 never in a sentence, and "Muir-TorrÃ© syndrome" in the product's own output. Files: raw/G-033_plain_language.json, raw/G-033_researcher.json (PR-8.1-13, PR-8.1-26).
10. Fail. G-036 M. tuberculosis assemblies, Researcher: "which gene, variant or condition do you mean?" Not new with this phase. File: raw/G-036_run1.json (PR-8.1-25).
11. Fail, systemic. 99 of 99 answered runs open with "Found ..." (PR-8.1-01).
12. Needs your eye. The new "MedGen lists no clinical features for X" sentence appears in 15 answers: Li-Fraumeni, Lynch, SARS, carcinoma NOS and breast cancer. It is true of the cited record, and off the question (PR-8.1-07).
13. Needs your eye. "Based on 13 sources" above footnotes numbered to [84] on the Marfan answer (PR-8.1-03). Card 3's "up to 30" against 28 answers showing more than 30, up to 75. 60 of 99 answered runs say "not yet confirmed" (PR-8.1-23).
14. Needs your eye. Marfan at Researcher on develop: the ten features named in the sentence include esotropia, exotropia and hypertropia, and no aortic root. Card 81 already lists this as known (PR-8.1-29).
15. Needs your eye. The answered golden runs over 25 seconds, and no text before the whole answer (PR-8.1-22). G-004's new clarifier asks for a resistance gene rather than the isolate (PR-8.1-21).
16. Needs your eye, lower:
   - G-029: TP53 called a "likely modifier" of Li-Fraumeni (PR-8.1-11).
   - G-035: isolate rows with no AMR gene in the text, possibly shown as table cells (PR-8.1-14).
   - G-011: the diseases appear only in the record list (PR-8.1-15).
   - G-007: records found, but no word on how to retrieve them (PR-8.1-18).
   - G-013 Researcher: "The gene symbol is BRCA1 [5] and the gene name is BRCA1 [6]." (PR-8.1-24).
   - The golden summary's comparison heading names the wrong floor run (PR-8.1-30).
17. Pass, for contrast:
   - G-032 PTEN at both depths, live (PR-8.1-27).
   - G-013 golden (PR-8.1-19).
   - Plain language and Researcher read differently on all three live pairs that answered.

## Rubric grades per question

Lines 1 and 2 are graded on golden pass 1 at the account default, researcher, unless stated. Line 3 is graded on the live pairs.

| Question | Category | Line 1, first sentence answers | Line 2, more than a chatbot | Sentence it rests on |
|---|---|---|---|---|
| G-013 diseases linked to brca1 | kiss | Pass | Pass | "Found 4 disease records for brca1: Familial cancer of breast [1], ..." |
| G-011 diseases for BRCA1 and BRCA2 | kiss | Needs your eye | Needs your eye | "Found 2 gene records and 11 disease records for BRCA1 and BRCA2" |
| G-018 TP53 location | kiss | Fail | Fail | "TP53 operates in the nucleus" cited to a summary without it |
| G-024 rs334 | kiss | Fail | Fail | "... rs334348 [2], rs334353 [3], c.-50T>C [4] and rs334773 [5]" |
| G-029 Li-Fraumeni genes | kiss | Pass | Needs your eye | "These likely reflect modifier or related-pathway contributions" |
| G-034 genes for breast cancer | kiss | Fail | Fail | "MedGen lists no clinical features for Seen by breast cancer nurse [1]." |
| G-003 Lynch syndrome across NCBI | kisses | Needs your eye | Fail | "The MedGen condition record is titled Lynch syndrome [1]. MedGen lists no clinical features for Lynch syndrome [2]." |
| G-005 SRA runs of SARS-CoV-2 | kisses | Fail | Fail | "Found 1 medgen record for SARS: SARS Coronavirus Protease Pathway [1]." |
| G-007 BioProject PRJNA31257 | kisses | Needs your eye | Needs your eye | "Found 1 bioproject record, 1 biosample record, 1 sra record and 1 assembly record" |
| G-021 CFTR papers | kisses | Fail | Fail | "Article record PMID:10075921 [1]. Article record PMID:10094564 [2]." |
| G-022 Marfan features, pass 1 | kisses | Fail | Fail | "Found 23 sequence variant records and 23 derived records for Marfan syndrome" |
| G-022 Marfan features, passes 2 and 3 | kisses | Needs your eye | Pass | "MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], ..." |
| G-030 EGFR in NSCLC | kisses | Fail | Fail | no written sentence after "Found 5 clinical trial records and 38 sequence variant records for EGFR" |
| G-035 E. coli ESBL isolates | kisses | Needs your eye | Needs your eye | "Isolate 11-3677 is also listed [1], as is isolate 11-4404 [2]." |
| G-025 MTHFR C677T | discovery | Fail | Fail | "The records include ClinVar:1004148 [1] and ClinVar:1042278 [2]." |
| G-028 APOE and late-onset Alzheimer | discovery | Fail | Fail | "The APOE gene encodes apolipoprotein E, a major chylomicron apoprotein ..." |
| G-033 MLH1 versus MSH2 | discovery | Fail | Fail | "Functional assays have been developed to assess variants of unknown significance in both MLH1 and MSH2" |
| G-039 student BRCA1 | discovery | Fail | Fail | "Mechanistic studies using patient-derived xenograft models have explored therapy resistance" |

Line 3, live on develop:

| Question | Plain language | Researcher | Verdict |
|---|---|---|---|
| G-013 | "I found 4 conditions related to brca1" then "BRCA1 is a gene that acts as a tumor suppressor, helping keep genetic material stable inside cells [5]." | "Found 4 disease records for brca1: ..." then "The gene symbol is BRCA1 [5] and the gene name is BRCA1 [6]." | Pass |
| G-033 | "The protein partners with another repair protein called PMS2 ..." | "The gene was identified as a locus frequently mutated in hereditary nonpolyposis colon cancer (HNPCC) ..." | Pass (both fail lines 1 and 2) |
| G-032 | "PTEN works as a tumor suppressor by turning down the AKT/PKB signaling pathway ..." | "PTEN is a tumor suppressor whose encoded protein functions as a phosphatidylinositol-3,4,5-trisphosphate 3-phosphatase ..." | Pass |
| Marfan features | no answer in 623 s | "MedGen lists these clinical features: Aortic regurgitation [2], ..." | Not comparable; the Plain language run is a fail on line 4 |

Line 4: see the golden result above. Line 5: not captured, see below.

## Screens and designs

- Overflow at 390: none measured. The brief says no screen layout changed in this phase, so no screen was captured at 1280 or 390, and no overflow was measured.
- Surfaces with no design: none assessed, for the same reason. Two things only a screen shows, and which this report cannot settle:
  - Whether the feature and isolate table rows render with their cells (HPO id, AMR gene).
  - Whether the SOURCES panel count agrees with the trust line.

## What was not captured, and why

- Screens: none. There was no layout change, and the brief made screenshots optional.
- The Marfan Plain language answer: it never arrived. My capture script discarded the partial events when the socket read timed out, which is my script's defect, so how far that run got is lost. I did not re-ask it because of the 8-question cap. The run_id is in PR-8.1-28.
- The card 80 questions ("Does coffee help make exercise more effective?" and "is there a trial recruiting for melanoma") were not asked, because of the 8-question cap. Card 2 is not tested here beyond the golden run, where no answered-path question was refused at the think step.
- `What is Marfan syndrome?` from query 81 was not asked, for the same cap.
- Records not fetched:
  - Whether SRR9496657 belongs to PRJNA31257 was not checked.
  - PMID 31691207, behind G-029's "These likely reflect" sentence, was not fetched.
- Checked against NCBI directly, esummary on 2026-09-25:
  - MedGen uids 44287, 88399 and 1633554.
  - Gene 7157 and Gene 348.
  - These are not saved in this folder.
- Housekeeping in this folder:
  - The develop test account s3-product-review-81-a6422fca87@example.com was created for the live asks. Its sign-in secret was generated in memory and never stored, so the account cannot be used again.
  - Compiling the capture script left a `__pycache__` folder here. I cannot delete files, so it stays for the lead to clear.

## What rests on my own read and what rests on a summary

- Read myself, answer text quoted from the file:
  - Every per-question verdict above and every quote in PR-8.1-02 to PR-8.1-29.
  - Golden raw files: G-003, G-005, G-007, G-011, G-013, G-018, G-021, G-022 (all three passes), G-024, G-025, G-028, G-029, G-030, G-033, G-034, G-035, G-036, G-039, plus G-004, G-006 and G-012 pass 3.
  - The 2026-09-22 raw files for G-004, G-005, G-006, G-024 and G-034.
  - All seven live answers in raw/.
- Counted by my own script over the saved files, not read one by one:
  - 99 of 99 answered runs open with "Found".
  - 15 of 99 carry the no-clinical-features sentence.
  - 28 of 99 show more than 30 sources.
  - 60 of 99 say "not yet confirmed".
  - The per-run list of answered runs over 25 seconds.
- Resting only on the golden summary.md and the brief:
  - 99 answered, the floor of 86, zero rate-limit signals.
  - Median, p90 and worst latency.
  - "Answered then" per question, including G-006 answering 2 of 3 on 2026-09-22.
- I did not rerun the golden run.
- Resting on nothing I saw: anything about the rendered page, including tables, the SOURCES panel, chips and layout.


## Findings log, written as each was established

Deployment check: GET https://search-agent-api-develop-43b3.up.railway.app/health at 2026-09-25 10:25:25 UTC returned {"status":"ok","app_env":"develop"}, saved as health.json in this folder. Golden run evidence read from testing/Developer/reports/2026-09-25_phase_8.1_golden/, deployed commit 5bac18a per its summary.md.

### PR-8.1-01: every answered golden run opens with a count of records, not an answer
- Kind: answer (rubric line 1)
- Verdict: fail
- What: all 99 of 99 answered runs in the golden run begin their answer text with "Found ". The golden run asks at the account default, researcher depth. Examples, pass 1: G-018 "Where in the cell is the TP53 protein located?" opens "Found 2 gene records, 5 pubmed records, 5 clinvar records, 1 omim record and 5 clinical trial records for TP53 [1]..."; G-031 "What molecular activity does the KRAS gene product have?" opens "Found 2 gene records, 5 pubmed records, 1 omim record, 1 literature entity record, 5 clinical trial records and 4 clinvar records for KRAS".
- Evidence: testing/Developer/reports/2026-09-25_phase_8.1_golden/raw/*.json, field answer_text, counted by script (99 answered, 99 start with "Found "). Read myself for G-018_run1.json and G-031_run1.json first sentences.
- Why a person would care: "I asked where TP53 sits in the cell and it told me how many records it found." This is the owner's item 12.10 wording, "list what was found instead of answering". Whether the sentences after the opener answer is graded per question below.
- NOT CLOSED

### PR-8.1-02: the Marfan phenotype question, the phase's own target, answered with variant records on 1 of 3 golden passes
- Kind: answer (rubric lines 1 and 2; Retest card 1, query 81)
- Verdict: fail
- What: G-022 "What phenotypic features are associated with Marfan syndrome?" at researcher depth. Pass 1 opens "Found 23 sequence variant records and 23 derived records for Marfan syndrome [1]...[46]." and ends "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead". Its body is 23 ClinVar variant rows, then a "Derived records found" section that repeats the same 23 ClinVar ids ("Derived record ClinVar:12502 [2]" after "SequenceVariant ClinVar:12502 ... [1]"). The MedGen feature list is present lower down, "(35 of 70 shown)". Passes 2 and 3 answer properly: pass 2 "Marfan syndrome is an autosomal dominant multisystem connective tissue disease primarily caused by FBN1 mutations ... [1]. MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], ... Ectopia lentis [5] ...". Pass 1 made a 100-row graph call; passes 2 and 3 made a 1-row call (summary L1 rows "100 / 1 / 1").
- Evidence: testing/Developer/reports/2026-09-25_phase_8.1_golden/raw/G-022_run1.json, G-022_run2.json, G-022_run3.json, answer_text, read myself in full for runs 1 and 2, first 1500 characters and last 600 for run 3.
- Why a person would care: "I asked what Marfan looks like in a patient and got a wall of FBN1 variant IDs, each listed twice, and a note saying the summary could not be checked." The answered count counts this as answered, so the golden number does not show it.
- NOT CLOSED

### PR-8.1-03: "Based on 13 sources" above citation markers numbered to [84] and [85]
- Kind: answer
- Verdict: needs your eye
- What: G-022 pass 3 trust line "Based on 13 sources"; its answer text carries citation markers up to [84] (84 citation events, the MedGen clinical features each cited separately, for example [1] to [10] all point to https://www.ncbi.nlm.nih.gov/medgen/44287). Pass 2: "Based on 13 sources", markers to [85]. Pass 1: "Based on 58 sources, not yet confirmed", markers to [93], the run record counting 35 distinct sources.
- Evidence: raw/G-022_run2.json and raw/G-022_run3.json, done event trust_line and citation events, counted by script. I did not see the page's SOURCES panel, so whether it shows 13 or 84 is not captured.
- Why a person would care: "It says 13 sources, but the last footnote is number 84. Which is it?" Retest card 5 promises the two agree; card 3 promises up to 30 sources.
- NOT CLOSED

### PR-8.1-04: G-005 moved from an honest refusal to a wrong-kind answer, and the golden count scores that as an improvement
- Kind: golden run, answer
- Verdict: fail
- What: G-005 "Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched." On 2026-09-22 all three passes refused ("I could not find grounded evidence for this. Try NCBI's cross-database search: ..."). Now all three count as answered. Pass 1 reads in full: "Found 1 medgen record for SARS: SARS Coronavirus Protease Pathway [1]." then "Medgen clinical_features: MedGen lists no clinical features for SARS Coronavirus Protease Pathway [2]." and the note "the written summary of these records could not be verified against them". Pass 2: "Found 3 disease records for SARS: SARS Coronavirus Protease Pathway [2], Probable SARS (severe acute respiratory syndrome) [3] and SARS (severe acute respiratory syndrome) confirmed [4]." No SRA run is named in any pass.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-005_run1.json and G-005_run2.json answer_text, read myself; 2026-09-22_10.3_consistency/raw/G-005_run1.json to run3.json for the old refusal.
- Why a person would care: "I asked for sequencing runs and got a pathway record for the 2003 SARS virus." The old answer sent them to NCBI search; the new one looks like an answer and is not. G-005 supplies 3 of the 13 answered runs the golden total gained over the floor, so the 99 overstates the gain by at least 3.
- NOT CLOSED

### PR-8.1-05: "How many genes are associated with breast cancer?" answers about "Seen by breast cancer nurse", with one sentence printed twice
- Kind: answer
- Verdict: fail
- What: G-034, pass 1: "Found 1 derived record for breast cancer: MedGen:C1320450 [2]. / MedGen lists no clinical features for Seen by breast cancer nurse [1]. / MedGen lists no clinical features for Seen by breast cancer nurse [1]." then "Derived MedGen:C1320450, n: 0 [2]." Pass 2 names a different concept, "MedGen:C2675521", same repeated sentence. The closing note says the answer "does not address the following entities named in the question: Paraneoplastic SPS is associated with breast cancer and other malignancies, BREAST CANCER, INVASIVE, SUSCEPTIBILITY TO, ...", none of which the question named. The question is never answered with a number of genes; the only number shown is "n: 0". The "no clinical features for Seen by breast cancer nurse" sentence is new with this phase: it was absent on 2026-09-22 (floor raw, G-034 runs 1 to 3).
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-034_run1.json and G-034_run2.json, read myself in full.
- Why a person would care: "It told me twice that a nurse visit has no clinical features, and never told me how many genes." A repeated sentence is the kind of broken text Retest card 6 says is gone.
- NOT CLOSED

### PR-8.1-06: "What is rs334?" lists four other variants as if they were rs334, and never names the condition
- Kind: answer
- Verdict: fail
- What: G-024, identical on all three passes: "Found 1 variant record record and 4 literature variant records for rs334: not-provided, protective, likely-benign, pathogenic, other [1], rs334348 [2], rs334353 [3], c.-50T>C [4] and rs334773 [5]." rs334348, rs334353 and rs334773 are different dbSNP ids that share the prefix. No condition is named; the note says the summary "could not be verified". "record record" is doubled. The same shape was already there on 2026-09-22 (floor raw G-024_run1.json), so this is not new with 8.1, but it counts as answered in both totals.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-024_run1.json and G-024_run2.json, read myself in full.
- Why a person would care: "rs334 is the sickle cell variant; any student knows that. This lists rs334348 as if it were the same thing." A confident wrong record, the worst kind of answer by the project's own rule.
- NOT CLOSED

### PR-8.1-07: a new sentence, "MedGen lists no clinical features for X", appears in answers that did not ask about features
- Kind: answer
- Verdict: needs your eye
- What: the sentence appears in 15 of 99 answered golden runs now and 0 of 84 answered runs on 2026-09-22 (counted by script over both raw folders). Questions: G-003 Lynch syndrome, G-005 SARS, G-012 carcinoma NOS ("Medullary Carcinoma, Not Otherwise Specified"), G-029 Li-Fraumeni, G-034 breast cancer. G-029 "Which genes are associated with Li-Fraumeni syndrome?" carries a heading "Clinical context" over the single sentence "MedGen lists no clinical features for Li-Fraumeni syndrome [2]." I checked the cited records myself: MedGen esummary for uid 88399 (C0085390, Li-Fraumeni) and uid 1633554 (C4552100, Lynch) each have an empty ClinicalFeatures element, so the sentence is literally true of the cited record. For Marfan, uid 44287 has 70 features, matching the answer's "35 of 70 shown".
- Evidence: raw/G-029_run1.json and raw/G-003_run1.json, read myself in full; esummary XML fetched 2026-09-25 from eutils (not saved in this folder).
- Why a person would care: "I asked which genes cause Li-Fraumeni. Why is it telling me there are no clinical features, under a heading called Clinical context? Li-Fraumeni certainly has features." True of the record, misleading to the reader, and off the question.
- NOT CLOSED

### PR-8.1-08: "Where is TP53 located?" answers "the nucleus", cited to a gene summary that never says nucleus
- Kind: answer (rubric lines 1 and 2; a claim its cited record does not say)
- Verdict: fail
- What: G-018 pass 1: "As a transcription factor regulating target gene expression, TP53 operates in the nucleus, where it binds DNA ... [1]" and "Its DNA-binding activity directly implicates nuclear localization, since regulation of target gene expression requires physical access to genomic DNA [1]." Citation [1] is https://www.ncbi.nlm.nih.gov/gene/7157, field summary. I fetched that summary (esummary, 2026-09-25): 774 characters, no occurrence of "nucle". The location is the model's inference presented as a cited fact. The cytoplasmic and mitochondrial localisation a researcher would expect are not mentioned. First sentence: "Found 2 gene records, 5 pubmed records, 5 clinvar records, 1 omim record and 5 clinical trial records for TP53".
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-018_run1.json answer_text and citation events, read myself.
- Why a person would care: "The footnote goes to the gene page, and the gene page does not say nucleus." The answer happens to be right, but the citation does not back it, which is the trust promise the product makes.
- NOT CLOSED

### PR-8.1-09: "What is the evidence linking APOE to late-onset Alzheimer disease?" never states the link
- Kind: answer (rubric line 2)
- Verdict: fail
- What: G-028 pass 1. The written part is two sentences: "The APOE gene encodes apolipoprotein E, a major chylomicron apoprotein essential for triglyceride-rich lipoprotein catabolism, and mutations in this gene cause familial dysbetalipoproteinemia [1]." and "APOE genotype also influences normal brain processes in the absence of AD hallmarks, with effects on hippocampal neuron structure and behavior [2]." No sentence mentions the e4 allele or Alzheimer risk. The closing note says the answer "does not address ... Non-familial Alzheimer disease of late onset", the disease the question is about, and "only 76 of the 131 records that matched this question in the graph were retrieved".
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-028_run1.json, read myself in full.
- Why a person would care: "Any chatbot tells me APOE e4 is the biggest genetic risk factor for late-onset Alzheimer. This told me about chylomicrons." The owner's 2026-09-20 verdict, "surface level", fits exactly.
- NOT CLOSED

### PR-8.1-10: the student question gets PARP-inhibitor resistance in xenografts, not what BRCA1 does
- Kind: answer (rubric lines 1 and 2)
- Verdict: fail
- What: G-039 "I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources." Pass 1, the whole written part: "Found 1 gene record for BRCA1: BRCA1 DNA repair associated [3]." then, under "Clinical Significance": "Mechanistic studies using patient-derived xenograft models have explored therapy resistance in BRCA1-deficient breast cancer, and ferroptosis-targeting strategies have been shown to sensitize BRCA1-deficient cancer cells to PARP inhibitors [1] [2]." No sentence says it repairs DNA or raises breast and ovarian cancer risk. The golden run asks at the account default, researcher, so this is not the Plain language path; the question itself asks for plain terms.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-039_run1.json, read myself in full.
- Why a person would care: "I said I am a student and asked what BRCA1 does. I got ferroptosis."
- NOT CLOSED

### PR-8.1-11: Li-Fraumeni genes answer calls all three genes, TP53 included, "likely modifier" contributions
- Kind: answer (rubric line 2)
- Verdict: needs your eye
- What: G-029 pass 1: "Found 3 gene records for Li-Fraumeni syndrome: cyclin dependent kinase inhibitor 2A [3], checkpoint kinase 2 [5] and tumor protein p53 [6] ..." followed by "These likely reflect modifier or related-pathway contributions, as phenotypic heterogeneity among carriers of the same pathogenic TP53 variant has been attributed to polymorphic variants in TP53-related genes, copy number variations, and epigenetic deregulation [1]." No sentence says germline TP53 variants are the cause. The genes are named in the first sentence, so line 1 is a partial pass.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-029_run1.json, read myself in full. I did not fetch PMID 31691207 to check the "These likely reflect" clause.
- Why a person would care: "A student reads that TP53 is a likely modifier of Li-Fraumeni. It is the cause."
- NOT CLOSED

### PR-8.1-12: "What does MTHFR C677T do?" answers "The records include ClinVar:1004148 and ClinVar:1042278"
- Kind: answer (rubric lines 1 and 2)
- Verdict: fail
- What: G-025 pass 1, the whole written part: "Found 58 sequence variant records for MTHFR, of 990 available [...]." then, under "Summary of Findings": "The records include ClinVar:1004148 [1] and ClinVar:1042278 [2]." The body is a list of other MTHFR variants. C677T is never named, nor its effect, nor the evidence quality the question asks about. Trust line "Based on 76 sources"; note "only 113 of the 990 records that matched this question in the graph were retrieved".
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-025_run1.json, read myself (first 1500 characters and the notes).
- Why a person would care: "The one MTHFR variant everyone asks about, and the summary is two accession numbers."
- NOT CLOSED

### PR-8.1-13: "Compare MLH1 and MSH2 in colorectal cancer risk" gets one sentence about functional assays, and "Muir-TorrÃ© syndrome"
- Kind: answer (rubric lines 1 and 2)
- Verdict: fail
- What: G-033 pass 1, the whole written part: "Functional assays have been developed to assess variants of unknown significance in both MLH1 and MSH2 to identify Lynch syndrome patients [1]." No comparison is made. The note says the answer "does not address ... Colorectal cancer". The disease list shows "Disease name: Muir-TorrÃ© syndrome [3]", the accent garbled. The garbling may be the golden capture's decoding rather than the product; checked on develop below.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-033_run1.json, read myself (first 1500 characters and the notes).
- Why a person would care: "I asked for a comparison and got neither gene's risk."
- NOT CLOSED

### PR-8.1-14: the E. coli ESBL answer's section "Isolates and their AMR genes" names no AMR gene, and its one written sentence says nothing
- Kind: answer
- Verdict: needs your eye
- What: G-035 pass 1: "Isolate 11-3677 is also listed [1], as is isolate 11-4404 [2]." Then the heading "Isolates and their AMR genes" over 20 lines of the form "Pathogen Detection isolate name: C236-11 [3]." with no gene on any line. It does say the list is cut: "Pathogen Detection lists 140,748 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." The page may render a table from structured data that the text does not carry; I did not capture the page.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-035_run1.json, read myself in full.
- Why a person would care: "Which ESBL gene does each isolate carry? The heading says it will tell me, and it does not."
- NOT CLOSED

### PR-8.1-15: "Which diseases are associated with BRCA1 and BRCA2?" names the diseases only in the record list; the written part is about BRCA1's function
- Kind: answer (rubric line 1)
- Verdict: needs your eye
- What: G-011 pass 1 opens "Found 2 gene records and 11 disease records for BRCA1 and BRCA2 [...]." The written paragraph, headed "BRCA1 Gene Identity and Function", reads "The encoded protein participates in transcription, DNA repair of double-stranded breaks, and recombination [1]. Mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers [1]." BRCA2 is not in the written part. The 11 diseases are listed under "Disease records found", including Fanconi anemia complementation group D1, Medulloblastoma and Wilms tumor 1, which is useful. Rubric line 2 partial pass on the list.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-011_run1.json, read myself (first 1500 characters).
- Why a person would care: "The answer is there, but I have to read the record list to find it."
- NOT CLOSED

### PR-8.1-16: the CFTR papers question lists 54 bare PMIDs and says nothing about what they cover
- Kind: answer (rubric lines 1 and 2; Retest card 3)
- Verdict: fail
- What: G-021 "Which papers in the graph mention the CFTR gene, and what do they cover?" Pass 1: "Found 54 article records for CFTR, of 1962 available [...]." then "Article record PMID:10075921 [1]. Article record PMID:10094564 [2]. ..." with no titles and no summary, and the note "the written summary of these records could not be verified against them, so this answer lists the records found instead". Trust line "Based on 72 sources, not yet confirmed".
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-021_run1.json, read myself (first 1100 characters and the notes).
- Why a person would care: "I asked what the papers cover. It gave me 54 numbers." Card 3's promise that a paper question reaches more sources is met in count and empty in content.
- NOT CLOSED

### PR-8.1-17: EGFR in lung cancer has no written answer at all, and the variants listed are not the ones anyone asks about
- Kind: answer (rubric lines 1 and 2)
- Verdict: fail
- What: G-030 "What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?" Pass 1 goes straight from "Found 5 clinical trial records and 38 sequence variant records for EGFR, of 4002 available [...]" to the trial list and then variants such as "NM_005228.5(EGFR):c.840C>A (p.Asn280Lys)". No written sentence; L858R and exon 19 deletions are not in the first 1100 characters; no trial is said to be recruiting.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-030_run1.json, read myself (first 1100 characters and the notes).
- Why a person would care: "A general chatbot names L858R, exon 19 deletions and osimertinib in its first line."
- NOT CLOSED

### PR-8.1-18: BioProject PRJNA31257 names one of each record but not how to retrieve them
- Kind: answer (rubric line 1)
- Verdict: needs your eye
- What: G-007 pass 1, in full: "Found 1 bioproject record, 1 biosample record, 1 sra record and 1 assembly record: The Human Genome Project, currently maintained by the Genome Reference Consortium (GRC) [1], Sample from Homo sapiens [2], SRR9496657 [3] and GRCh38.p14 [4]." then the record list and "the written summary of these records could not be verified". The question's second half, "tell me how to retrieve each", is not answered. I did not check that SRR9496657 belongs to PRJNA31257.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-007_run1.json, read myself in full.
- Why a person would care: "It found the records; it did not tell me how to get them."
- NOT CLOSED

### PR-8.1-19: "what diseases are linked to brca1?" answers in its first sentence and adds a useful number (pass)
- Kind: answer (rubric lines 1 and 2)
- Verdict: needs your eye (filed as a pass, for contrast)
- What: G-013 pass 1: "Found 4 disease records for brca1: Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]." then "mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers [5]." Line 1 pass, line 2 pass. The gene symbol is echoed in lower case, "brca1", from the question.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-013_run1.json, read myself (first 1100 characters).
- Why a person would care: this is what a good answer here looks like; most of the others above do not.
- NOT CLOSED

### PR-8.1-20: G-006 now makes a person wait 97 seconds, every time, for "One of my searches did not finish"
- Kind: golden run (a question that got worse), rubric line 4
- Verdict: fail
- What: G-006 "For PMID 11237011, what sequence data, BioProjects, GEO series and assemblies are linked to it? ..." took 98.0, 96.7 and 96.5 seconds on the three passes and ended "One of my searches did not finish, so I could not find grounded evidence this time. Ask again to retry, or try NCBI's cross-database search: ...". The tool error on each pass: cypher_query "call did not complete within its per-step timeout budget". On 2026-09-22 the same question answered 2 of 3 per the brief, and its refusal took 8.5 seconds (floor raw G-006_run1.json). The message is honest; the wait is not something a person sits through.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-006_run1.json (answer_text and record.tool_errors), summary.md "Runs over 60 seconds", read myself. I did not establish whether the graph timeout is caused by this phase's change or by the graph tonight.
- Why a person would care: "I waited a minute and a half and it told me to ask again."
- NOT CLOSED

### PR-8.1-21: G-004, counted as "got worse", now asks a clarifying question instead of a wrong answer
- Kind: golden run (a question that got worse)
- Verdict: needs your eye
- What: G-004 "For a Salmonella enterica isolate, what SNP cluster does it belong to, which AMR genes does it carry, and which isolates are within 5 SNPs of it?" On 2026-09-22 it counted as answered with "Found 1 gene record for AMR: alpha 2-HS glycoprotein [1], linked to 1 disease: Alopecia-intellectual disability syndrome 1 [2]." Now all three passes, about 5 seconds each, reply "Which resistance gene or gene family should the isolates carry? For example ESBL (the blaCTX-M family), carbapenemase (...), colistin resistance (mcr), or a gene name such as blaCTX-M-15." and count as refused_no_evidence. For a person this is better than the old wrong answer. The question offered does not ask the thing the question lacks, which isolate.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-004_run1.json and 2026-09-22_10.3_consistency/raw/G-004_run1.json, read myself.
- Why a person would care: "It asked me something instead of inventing an answer; but I never said which isolate, and that is what it should ask."
- NOT CLOSED

### PR-8.1-22: 19 answered golden questions took over 25 seconds on at least one pass; the slowest took 103.6
- Kind: golden run, rubric line 4
- Verdict: needs your eye
- What: answered runs: median 21.1 s, p90 33.6 s, worst 103.6 s (summary.md "By outcome", answered). All runs: median 17.1, p90 32.7, worst 103.6. 33 of 99 answered runs took over 25 seconds, across 19 questions, pass and seconds from runs.jsonl: G-002 (2, 28.2); G-005 (1, 26.5); G-010 (1, 25.6); G-011 (2, 25.5; 3, 31.4); G-012 (3, 103.6); G-013 (1, 27.7); G-016 (1, 33.4; 2, 36.6; 3, 33.0); G-017 (1, 37.2; 3, 30.8); G-018 (1, 30.8; 2, 27.6); G-021 (1, 36.1; 2, 27.8; 3, 31.6); G-022 (2, 28.4; 3, 33.9); G-025 (2, 29.8; 3, 39.8); G-030 (1, 27.4); G-031 (1, 33.6); G-032 (1, 28.2; 2, 32.7; 3, 34.1); G-033 (1, 27.9); G-035 (1, 39.1; 2, 28.2; 3, 33.8); G-039 (3, 32.2); G-040 (1, 25.9; 3, 31.2). G-012 pass 3 hit the same graph timeout as G-006 and then answered "carcinoma not otherwise specified" with five thyroid cancer trials ("Radioimmunotherapy ... in Treating Patients With Thyroid Cancer [2], Thalidomide in Treating Patients With Thyroid Cancer [3], ...").
- Evidence: 2026-09-25_phase_8.1_golden/runs.jsonl seconds field, computed by script; raw/G-012_run3.json, read myself.
- Why a person would care: "One answer in three makes me wait longer than half a minute."
- NOT CLOSED

### PR-8.1-23: Retest card 3 says sources go "up to 30"; 28 of 99 answered golden runs show more than 30, up to 75
- Kind: answer (Retest card 3, query 82)
- Verdict: needs your eye
- What: query 82 says "The count of sources can go past 20, up to 30". In the golden run, 28 of 99 answered runs have more than 30 distinct sources, the largest 75 (G-025 "Based on 76 sources"; G-021 "Based on 72 sources, not yet confirmed"; G-016, G-023, G-001, G-002, G-010 and G-040 are in the 56 to 71 range). The 30 appears to bound the written part only, while the record lists below it add more. Separately, 60 of 99 answered runs carry "not yet confirmed" in the trust line, including the clean G-013 answer ("Based on 22 sources, not yet confirmed").
- Evidence: 2026-09-25_phase_8.1_golden/runs.jsonl distinct_sources and trust_line, counted by script; summary.md "Per question" Sources column.
- Why a person would care: "The card told me to look for up to 30. The page says 76." And "not yet confirmed" on six answers in ten reads as "do not trust this".
- NOT CLOSED

### PR-8.1-24: G-013 on develop, Plain language and Researcher read differently (rubric line 3 pass), with a filler sentence at Researcher
- Kind: answer (rubric line 3), asked live on develop
- Verdict: needs your eye (line 3 itself passes)
- What: "what diseases are linked to brca1?" asked once at each depth on a fresh account. Plain language, 21.5 s: "I found 4 conditions related to brca1 [1][2][3][4]." then "BRCA1 is a gene that acts as a tumor suppressor, helping keep genetic material stable inside cells [5]. Changes in this gene account for roughly 40% of inherited breast cancers and over 80% of inherited breast and ovarian cancers combined [5]." Researcher, 26.0 s: "Found 4 disease records for brca1: Familial cancer of breast [1], ..." then the same four diseases restated in the next sentence, then "The gene symbol is BRCA1 [5] and the gene name is BRCA1 [6]." The two depths differ in wording and register, so line 3 passes. The Researcher answer restates its first sentence and carries a sentence that says nothing. Both show "Based on 22 sources, not yet confirmed". In both, no text arrived before the whole answer: first token at 21.5 s and 26.0 s, equal to the total.
- Evidence: testing/Developer/reports/2026-09-25_product_review_8.1/raw/G-013_plain_language.json and raw/G-013_researcher.json, read myself (first 1800 characters each); capture_depth_pairs.log.
- Why a person would care: "Plain language reads like a person explaining. Researcher tells me the gene symbol is BRCA1 and the gene name is BRCA1."
- NOT CLOSED

### PR-8.1-25: a question naming an organism is asked "which gene, variant or condition do you mean?"
- Kind: answer (a good question refused; not new with this phase)
- Verdict: fail
- What: G-036 "Which Mycobacterium tuberculosis genome assemblies are available, and how do I retrieve them?" All three passes reply "One more detail is needed: which gene, variant or condition do you mean? Ask again naming it, for example \"Which variants cause disease in BRCA1?\", and the follow-up will use it." The think step classified it exploratory with no resolved entity. It was 0 of 3 on 2026-09-22 too, so this phase did not cause it; Retest card 2 is about good questions not being refused, so it is worth the owner's eye beside that card.
- Evidence: 2026-09-25_phase_8.1_golden/raw/G-036_run1.json and G-036_run2.json, answer_text and think event, read myself.
- Why a person would care: "I named the organism and asked for assemblies. It asked me which gene, and suggested BRCA1."
- NOT CLOSED

### PR-8.1-26: G-033 on develop, both depths, never mentions MSH2 in a sentence; "Muir-TorrÃ© syndrome" is in what the product sends
- Kind: answer (rubric lines 1, 2 and 3), asked live on develop
- Verdict: fail (lines 1 and 2); line 3 passes
- What: "Compare what is known about MLH1 and MSH2 in colorectal cancer risk." Plain language, 21.5 s: "I found 2 genes and 5 conditions related to MLH1, MSH2 and colorectal cancer [...]." then "The protein partners with another repair protein called PMS2 to form a complex called MutL alpha ... [1]." and "This gene was found to be often mutated in a hereditary form of colon cancer [1]." without saying which gene. Researcher, 13.3 s: one paragraph headed "MLH1 and Colorectal Cancer Risk": "The gene was identified as a locus frequently mutated in hereditary nonpolyposis colon cancer (HNPCC), and its protein heterodimerizes with PMS2 to form MutL alpha ... [1]." Neither depth says one word about MSH2 in its written part, and neither compares. The two depths do read differently (line 3 pass). My capture decodes the stream as UTF-8, and both answers contain "Disease name: Muir-TorrÃ© syndrome", so the garbled accent is in the product's output, not a capture artifact (PR-8.1-13 left this open).
- Evidence: testing/Developer/reports/2026-09-25_product_review_8.1/raw/G-033_plain_language.json and raw/G-033_researcher.json, read myself (first 1500 characters each).
- Why a person would care: "I asked it to compare two genes; it described one, called it 'this gene', and misspelled a syndrome."
- NOT CLOSED

### PR-8.1-27: G-032 PTEN pathways on develop, the best pair read: depths differ and both teach something (pass), still opening with a count
- Kind: answer (rubric lines 1, 2 and 3), asked live on develop
- Verdict: needs your eye (lines 2 and 3 pass; line 1 fails only on the opener)
- What: "Which pathways does PTEN participate in?" Plain language, 25.8 s: opener "I found 2 genes, 5 published papers, 5 genetic variants, 1 genetics catalogue entry and 5 clinical trials related to PTEN [...]", then "PTEN works as a tumor suppressor by turning down the AKT/PKB signaling pathway, which cells use to grow and survive [1]." Later it uses "In the stroma" and "neddylated PTEN" without explaining them. Researcher, 28.3 s: "PTEN is a tumor suppressor whose encoded protein functions as a phosphatidylinositol-3,4,5-trisphosphate 3-phosphatase, directly opposing the PI3K/AKT/mTOR signaling network by dephosphorylating PIP3 [1] [2]." then specifics a general chatbot rarely gives: "PTEN can be secreted through the TMED10-channeled protein secretion pathway and binds to PLXDC2 on macrophages, triggering JAK2-STAT1 signaling ... [6]." Both "Based on 18 sources".
- Evidence: testing/Developer/reports/2026-09-25_product_review_8.1/raw/G-032_plain_language.json and raw/G-032_researcher.json, read myself (first 1600 to 1700 characters each).
- Why a person would care: this is the answer quality the owner is asking for, with the count sentence still in front of it.
- NOT CLOSED

### PR-8.1-28: the Marfan phenotype question at Plain language gave no answer in 623 seconds on develop
- Kind: answer (rubric line 4; Retest card 1, query 81), asked live on develop
- Verdict: fail, cause not established
- What: "What phenotypic features are associated with Marfan syndrome?" at plain_language, started 2026-09-25 10:35:51 UTC, run_id fe226f3f-fbeb-48e1-bb90-85ab65c3fece, session pr81-a12bfa16432e. The run was created, the event stream opened, and after 623.0 seconds the read failed with TimeoutError('The read operation timed out'). No done event and no answer text arrived. My script waits 200 seconds on a silent socket, so the stream went quiet for at least 200 seconds. The same question at researcher, asked 3 seconds later on the same account, answered in 10.8 seconds. My capture script dropped the partial events when the read raised, so I cannot show how far the run got, and I cannot tell a server stall from a dropped connection. I did not re-ask it: the brief caps this review at 8 questions, and this was the seventh.
- Evidence: testing/Developer/reports/2026-09-25_product_review_8.1/raw/MARFAN_plain_language.json (record only, zero events) and capture_depth_pairs.log.
- Why a person would care: this is the exact question and depth card 1 asks the owner to check first. If the page does what the stream did, they wait with no answer. The run_id lets the trace be looked up.
- NOT CLOSED

### PR-8.1-29: the Marfan phenotype question at Researcher on develop names features from MedGen with HPO ids; the ten it names first include four eye-movement findings and no aortic root
- Kind: answer (rubric lines 1 and 2; Retest card 1, query 81), asked live on develop
- Verdict: needs your eye (card 1 at Researcher largely met)
- What: 10.8 s, "Based on 13 sources". Opens "Found 1 disease record for Marfan syndrome: Marfan syndrome [12]." then "Marfan syndrome is a multisystem connective tissue disease with autosomal dominant inheritance, mainly caused by FBN1 gene mutation [1]." then "MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], Astigmatism [4], Ectopia lentis [5], Esotropia [6], Exotropia [7], Pes planus [8], Glaucoma [9], Congestive heart failure [10] and Hypertropia [11]." The section "Clinical features MedGen lists for Marfan syndrome" follows. The HPO id reaches the page as table cells, not in the text: each feature's token event carries kind "table_row" and cells such as ["Aortic regurgitation", "HP:0001659"] (70 table-row tokens carry an HP id). The names in the sentence are MedGen's first ten in record order, so aortic root aneurysm and aortic dissection are not in the sentence, which card 81 already lists as known. Citation markers again run to [84] under "Based on 13 sources" (PR-8.1-03).
- Evidence: testing/Developer/reports/2026-09-25_product_review_8.1/raw/MARFAN_researcher.json, answer text and token events, read myself; MedGen esummary uid 44287 has 70 features, fetched 2026-09-25.
- Why a person would care: "The first features it names for Marfan include esotropia, exotropia and hypertropia. The thing that kills Marfan patients is the aortic root, and it is not in the sentence." Known, but it is the first thing a clinician will see.
- NOT CLOSED

### PR-8.1-14, added evidence: the page may carry the AMR genes as table cells
- Kind: answer
- Verdict: needs your eye (unchanged; possibly a false alarm)
- What: the live Marfan run shows feature rows reach the page as token events with kind "table_row" and a cells array, and the plain text omits the cells. The golden raw files keep no token events (checked on G-022_run3.json: event types are citation, tool_start, tool_result, guard, think, plan, step, done), so I cannot see whether the G-035 isolate rows carry AMR genes in their cells. PR-8.1-14 rests on the text only.
- Evidence: raw/MARFAN_researcher.json token events; 2026-09-25_phase_8.1_golden/raw/G-022_run3.json event types.
- Why a person would care: the owner can settle it with one look at the isolate table on the page.
- NOT CLOSED

### PR-8.1-30: the golden summary's comparison is headed "2026-09-12 baseline" but compares against the 2026-09-22 floor run
- Kind: golden run
- Verdict: needs your eye (low)
- What: summary.md's section "Comparison with the 2026-09-12 baseline" lists "Answered then" values that match the 2026-09-22 run (G-004 3, G-006 2), and its closing command line reads "python3 testing/Developer/reports/2026-09-25_phase_8.1_golden testing/Developer/reports/2026-09-22_10.3_consistency/runs.jsonl", with the script name missing. Separately, the brief says every question gave the same outcome on all three passes; G-046 gave refused_compute_request, refused_offtopic, refused_compute_request. All three are refusals, so the answered count is unaffected. The 2026-09-22 floor folder holds 84 answered raw files against 86 answered rows in its runs.jsonl.
- Evidence: 2026-09-25_phase_8.1_golden/summary.md, sections "Comparison with the 2026-09-12 baseline", "Stability" and "Method"; counts by script over 2026-09-22_10.3_consistency/raw and runs.jsonl.
- Why a person would care: "Which run is this compared with?" The owner accepts or rejects against a floor, so the label should name it.
- NOT CLOSED

