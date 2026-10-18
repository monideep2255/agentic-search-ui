# Product check, card 38 slice C, on deployed develop

Pre-screen before the owner's retest of card 38 slice C (pull request #267, merge commit `cf9be15d`): papers the knowledge graph found are listed by their PubMed title. It files findings and closes nothing. The owner's verdict closes.

- Target: develop. `/health` read `{"status":"ok","app_env":"develop"}` before capture; the capture recorded `app_env` develop and deployed commit `cf9be15d` (`run1/results.json`).
- Asked as a guest, in the browser, each question once at 1280 and once at 390: 6 questions, the spend cap.
- Step 2, the golden run, was skipped by the owner's choice for tonight.
- Capture: `.claude/skills/verify/scripts/capture.mjs`, spec in `run1/spec.json`.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Titles checked against PubMed](#titles-checked-against-pubmed)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

The slice does what it promised on the rows a person sees first. In all four CFTR answers, both depths and both widths, every one of the ten paper rows on page 1 carries its PubMed title; none reads "Article record PMID:..." or "Published paper"; no row repeats on page 1; the three titles checked match PubMed character for character, including "-20.9 kb" and PubMed's own typo "mutatations". Horizontal overflow is 0 px on all six captures, long titles at 390 included. The BRCA1 control is unchanged in shape.

It is not a clean pass for the question as a person asked it: three of the four CFTR answers have no written answer at all, only "Found 54 article records" and a list (PR-card38c-01), and three of four took over 20 seconds (PR-card38c-03). The Sources grouping the card promised was not captured, since the panel is collapsed and opening it would have cost a seventh question (PR-card38c-05).

Golden result: not run tonight (owner's decision). Answered against the floor, and answered well of the fixed ten, are not reported.

## Per answer

First ten paper rows, identical in all four CFTR answers, in this order: "The Hdj-2/Hsc70 chaperone pair facilitates early steps in CFTR biogenesis." (PMID:10075921); "Identification of a D579G homozygote cystic fibrosis patient with pancreatic sufficiency and minor lung involvement. Mutations in brief no. 221. Online." (10094564); "Genetic findings in congenital bilateral aplasia of vas deferens patients and identification of six novel mutatations. Mutations in brief no. 138. Online." (10200050); "Analysis of a DNase I hypersensitive site located -20.9 kb upstream of the CFTR gene." (10561583); "Differential function of the two nucleotide binding domains on cystic fibrosis transmembrane conductance regulator." (10581360); "A novel missense mutation D513G in exon 10 of the cystic fibrosis transmembrane conductance regulator (CFTR) gene identified in a French CBAVD patient. Mutations in brief no. 175. Online." (10651488); "Sodium 4-phenylbutyrate downregulates Hsc70: implications for intracellular trafficking of DeltaF508-CFTR." (10666020); "Splicing factors induce cystic fibrosis transmembrane regulator exon 9 skipping through a nonevolutionary conserved intronic element." (10766763); "Protein kinase A associates with cystic fibrosis transmembrane conductance regulator via an interaction with ezrin." (10799517); "The PDZ-interacting domain of cystic fibrosis transmembrane conductance regulator is required for functional expression in the apical plasma membrane." (10852925).

| Question | Mode | Width | First sentence | Bare rows on page 1 | Repeats on page 1 | Pager | Trust line | Time |
|---|---|---|---|---|---|---|---|---|
| CFTR papers | Researcher | 1280 | "Found 54 article records for CFTR, of 1962 available." | 0 of 10 | none | "Showing 1–10 of 54", 6 pages | "? Answered"; "Based on 71 sources cited from PubMed, ClinicalTrials.gov, ClinVar and 2 other databases" | 27.3 s |
| CFTR papers | Researcher | 390 | same | 0 of 10 | none | same | same | 23.4 s |
| CFTR papers | Plain language | 1280 | "I found 54 published papers related to CFTR, out of 1962 available." | 0 of 10 | none | "Showing 1–10 of 71", 8 pages | "? Answered"; same | 19.5 s |
| CFTR papers | Plain language | 390 | "A paper on gene regulation examines a control region upstream of the CFTR gene, and another explores how splicing factors cause a part of the CFTR genetic instructions to be skipped." | 0 of 10 | none | "Showing 1–10 of 71", 8 pages | "✓ Answered"; same | 27.7 s |
| BRCA1 control | Researcher | 1280 | "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." | n/a: 5 live PubMed rows, all titled | none | none | "? Answered"; "Based on 21 sources ... their values could not be compared · High-risk claim" | 14.1 s |
| BRCA1 control | Researcher | 390 | "Found 4 disease records for BRCA1: Familial cancer of breast, ..." | n/a: 5 live PubMed rows, all titled | none | none | same | 14.1 s |

Times are the app's own "Answered" figure. Median of the six 21.5 s, worst 27.7 s; over 25 s: CFTR Researcher 1280 (27.3 s) and CFTR Plain language 390 (27.7 s).

In Researcher, the graph's papers sit under "ARTICLE RECORDS FOUND" and five live PubMed papers under a separate "PUBMED RECORDS FOUND" (PMIDs 28340353, 35011616, 36220763 or 41235117, 37730207, 38388235). None of the five is on page 1 of the graph list; pages 2 to 6 were not paged, so a repeat across the two lists is not ruled out.

## Titles checked against PubMed

Fetched from E-utilities esummary on 2026-10-17, compared with the row text in `run1/cftr_papers_researcher_1280.txt`:

| PMID | PubMed title | Match |
|---|---|---|
| 10094564 | "Identification of a D579G homozygote cystic fibrosis patient with pancreatic sufficiency and minor lung involvement. Mutations in brief no. 221. Online." | exact |
| 10200050 | "Genetic findings in congenital bilateral aplasia of vas deferens patients and identification of six novel mutatations. Mutations in brief no. 138. Online." | exact, PubMed's typo kept |
| 10561583 | "Analysis of a DNase I hypersensitive site located -20.9 kb upstream of the CFTR gene." | exact |

No title on page 1 carries variant notation such as "c.3140-26A>G" or "<5 years", and none is a bracketed placeholder, so those two promises were not exercised by this question.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Fail in 3 of 4 CFTR answers; needs your eye in Plain 390; pass for BRCA1 | "Found 54 article records for CFTR, of 1962 available." with "Note: no written summary could be checked against the records"; Plain 390 opens on two papers before the count. BRCA1 1280: "BRCA1 is associated with familial cancer of breast, ...". |
| 2. Teaches what a chatbot would not | Needs your eye for CFTR; pass for BRCA1 | CFTR: 54 cited, correctly titled papers is checkable detail, but the first ten are 1998 to 2000 papers in PMID order and nothing says what the literature covers. BRCA1: four MedGen-cited conditions, including "Fanconi anemia complementation group S". |
| 3. Plain language and Researcher differ | Pass | Researcher "Found 54 article records" with per-source tables; Plain "I found 54 published papers" with one "Where this answer comes from" list, and at 390 a written summary. |
| 4. Seconds to answer | Needs your eye | 27.3, 23.4, 19.5 and 27.7 s for CFTR; 14.1 s for BRCA1. |
| 5. Screens match design | Pass at 1280 and 390 for the table itself | `run1/cftr_papers_researcher_1280.png`: bordered PAPER and IDENTIFIER table, uppercase heads, as the prototype's result table (`run1/prototype_cftr_papers_researcher_1280.png`); `run1/cftr_papers_researcher_390_fold.png`: titles wrap, PMID under each, nothing cut. The prototype answers in prose; the live CFTR answer mostly does not (PR-card38c-01). |

## What to look at first

1. Fail, PR-card38c-01: no written answer in 3 of 4 CFTR answers (`run1/cftr_papers_researcher_1280.txt`).
2. Needs your eye, PR-card38c-05: the Sources grouping was not seen; the card's "under the live NCBI group" promise is unverified.
3. Needs your eye, PR-card38c-03: 27.3 and 27.7 s answers.
4. Needs your eye, PR-card38c-02: the one written CFTR summary opens on two papers, not on the answer (`run1/cftr_papers_plain_390.txt`).
5. Needs your eye, PR-card38c-04: count, pager and source totals disagree (54, 71, "1–20", markers to 72).
6. Needs your eye, PR-card38c-06: the oldest papers come first.

## Overflow and missing design

- Overflow at 390: 0 px on all three live screens (`run1/results.json`).
- No design: a papers-list answer, the stacked phone form of a record table, the Notes list and the two separate paper sections ("ARTICLE RECORDS FOUND" and "PUBMED RECORDS FOUND") appear in no prototype screen. The prototype's rs334 answer stands in as the result-table reference.

## Not captured

- The golden run: skipped by the owner's decision.
- The Sources panel opened: it is collapsed by default, and a seventh question was over the cap.
- Pages 2 to 6 (Researcher) and 2 to 8 (Plain language): not paged, so bare rows, bracketed-placeholder rows and repeats beyond page 1 are not known.
- Variant-notation and bracketed-placeholder titles: none occurred on page 1.
- Each question once per width: one sample each.
- What I read myself: every answer text in `run1/` in full, and the screenshots `cftr_papers_researcher_1280.png`, `cftr_papers_researcher_390.png`, `cftr_papers_researcher_390_fold.png`, `cftr_papers_plain_390_fold.png` and `prototype_cftr_papers_researcher_1280.png`. The Plain 1280 and BRCA1 verdicts rest on the answer text alone, not a screenshot. Overflow rests on the script's measurement in `results.json`. Nothing rests on a summary.

## Findings

### PR-card38c-01: three of four CFTR answers have no written answer, only a count and a list
- Kind: answer
- Verdict: fail
- What: Researcher at both widths and Plain language at 1280 open on a record count and carry a note that no summary could be checked. Nothing says what the papers cover, which the question asks.
- Evidence: `run1/cftr_papers_researcher_1280.txt`, "Found 54 article records for CFTR, of 1962 available." and "Note: no written summary could be checked against the records, so the records found are listed below with their sources"; the same in `run1/cftr_papers_researcher_390.txt` and `run1/cftr_papers_plain_1280.txt`.
- Why a person would care: they asked what the papers cover and got six pages of titles to read themselves. Likely not slice C's doing (titles are a display change), but it is what the owner will see on this exact question.
- NOT CLOSED

### PR-card38c-02: the one written CFTR summary opens on two papers, not on an answer
- Kind: answer
- Verdict: needs your eye
- What: Plain language at 390 wrote a summary, but its first sentence describes two papers and the count sentence follows mid-paragraph; the topics named are four 1999 to 2000 papers and one about liver disease.
- Evidence: `run1/cftr_papers_plain_390.txt`, "A paper on gene regulation examines a control region upstream of the CFTR gene, and another explores how splicing factors cause a part of the CFTR genetic instructions to be skipped. I found 54 published papers related to CFTR, out of 1962 available."; `run1/cftr_papers_plain_390_fold.png`.
- Why a person would care: a student wants "these papers cover CFTR folding, mutations and splicing", not a tour of the first rows.
- NOT CLOSED

### PR-card38c-03: CFTR answers took 23 to 28 seconds
- Kind: answer
- Verdict: needs your eye
- What: three of four CFTR answers exceeded the owner's 20 second target; two exceeded 25.
- Evidence: "Answered27.3s" (Researcher 1280), "Answered23.4s" (Researcher 390), "Answered19.5s" (Plain 1280), "Answered27.7s" (Plain 390), in `run1/cftr_papers_*.txt`. BRCA1 took 14.1 s at both widths.
- Why a person would care: nearly half a minute for a list. Whether the title lookup added time is not established; there is no before-number for this question here.
- NOT CLOSED

### PR-card38c-04: the count, the pager and the source total disagree
- Kind: answer
- Verdict: needs your eye
- What: the count sentence says 54 papers and cites only 1 to 20; Plain language's pager says 71 rows because papers, variants and trials share one list; the trust line says 71 sources while the citation markers run to 72.
- Evidence: `run1/cftr_papers_plain_1280.txt`, "I found 54 published papers related to CFTR, out of 1962 available.⁠1–20" then "Showing 1–10 of 71"; `run1/cftr_papers_researcher_1280.txt`, "71 sources cited" and the last trial row cited "⁠72".
- Why a person would care: a reader who counts papers in Plain language finds 71 rows, not 54, and "of 1962 available" reads as 1962 CFTR papers when it counts every matched record.
- NOT CLOSED

### PR-card38c-05: whether graph papers sit under the live NCBI group in Sources was not seen
- Kind: screen
- Verdict: needs your eye
- What: the Sources panel is collapsed ("▶ SOURCES 71") in every capture, and opening it needed a seventh question, over the cap. The card's grouping promise is unverified.
- Evidence: `run1/cftr_papers_researcher_1280.png`, the collapsed "SOURCES 71" row.
- Why a person would care: a researcher who opens Sources to trace a paper is exactly who the grouping serves.
- NOT CLOSED

### PR-card38c-06: the graph's papers come oldest first, by PubMed number
- Kind: answer
- Verdict: needs your eye
- What: the ten rows on page 1 are PMIDs 10075921 to 10852925 in ascending order, papers from 1998 to 2000, in both depths; the newer reviews appear only in the separate live PubMed section.
- Evidence: `run1/cftr_papers_researcher_1280.txt`, row 1 "The Hdj-2/Hsc70 chaperone pair facilitates early steps in CFTR biogenesis. PMID:10075921"; PubMed dates 1998 and 1999 for 10200050 and 10094564.
- Why a person would care: a clinician asking about CFTR sees "Mutations in brief no. 221" before anything on modulators.
- NOT CLOSED
