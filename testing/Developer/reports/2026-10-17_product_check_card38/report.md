# Product check, card 38 slice B, on deployed develop

Pre-screen before the owner's retest of card 38 slice B (pull request #265, merge commit `0bb341c7`). It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before capture, and the capture recorded `app_env` develop and deployed commit `0bb341c7` (`run1/results.json`).
- Asked as a guest, in the browser, each question once at 1280 and once at 390: 6 questions, the spend cap.
- Step 2, the golden run, was skipped by the owner's choice for tonight.
- Capture: `.claude/skills/verify/scripts/capture.mjs`, spec in `run1/spec.json`.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

Card 38 slice B does what it promised where the question ran: the Researcher table has an ORGANISM column at 1280, the rows carry the species at 390, and Plain language reads "tumor protein p53 (Oryctolagus cuniculus)". Horizontal overflow is 0 px on all six captures, including the long Plain language labels at 390.

It does not pass as a whole. Two of the six questions searched nothing and showed "We could not finish checking your question" (PR-card38-01, TP53 in Plain language at 1280; PR-card38-02, the BRCA1 control at 1280). The scripted capture still marked both as passing (PR-card38-03). Where the orthologs question ran, it has no written answer, only a count and a list (PR-card38-04).

Golden result: not run tonight (owner's decision). Answered against the floor, and answered well of the fixed ten, are not reported.

## Per answer

First ten rows in all three TP53 answers that ran, in this order: Oryctolagus cuniculus (NCBIGene:100009292), Oryzias latipes (100049321), Equus caballus (100062044), Ornithorhynchus anatinus (100092821), Oncorhynchus mykiss (100136737), Ictalurus punctatus (100304476), Cavia porcellus (100379269), Callithrix jacchus (100415710), Pongo abelii (100435218), Ailuropoda melanoleuca (100468516). Every gene name is "tumor protein p53". Researcher shows them as Gene, Identifier, Organism; Plain language as "tumor protein p53 (Oryctolagus cuniculus)".

| Question | Mode | Width | Count line | Pager | Trust line | Time |
|---|---|---|---|---|---|---|
| TP53 orthologs | Researcher | 1280 | "Found 41 gene records for TP53, of 715 available." | "Showing 1–10 of 42", 5 pages | "? Answered"; "Based on 58 sources cited from NCBI Gene, ClinicalTrials.gov, ClinVar and 2 other databases" | 22.3 s |
| TP53 orthologs | Researcher | 390 | "Found 40 gene records for TP53, of 715 available." | "Showing 1–10 of 41", 5 pages | "? Answered"; same, 57 sources | 23.0 s |
| TP53 orthologs | Plain language | 1280 | none: the run searched nothing | none | "Not verified · the run did not finish" | no answer |
| TP53 orthologs | Plain language | 390 | "I found 41 genes related to TP53, out of 715 available." | "Showing 1–10 of 58", 6 pages | "? Answered"; same, 58 sources | 23.4 s |
| BRCA1 control | Researcher | 1280 | none: the run searched nothing | none | "Not verified · the run did not finish" | no answer |
| BRCA1 control | Researcher | 390 | "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." then "Found 4 disease records for BRCA1" | 4 disease rows: MedGen C0346153, C2676676, C3280442, C4554406; then gene, PubMed, ClinVar, OMIM and trial rows, no Organism column | "? Answered"; "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared · High-risk claim" | 10.4 s |

Times are the app's own "Answered" figure. Of the four that answered: median 22.7 s, worst 23.4 s; three over the owner's 20 s target, none over 25 s.

The BRCA1 control, where it ran, reads as an unchanged disease answer with no species column, so the card did not leak into it. One sample, not proof.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Fail for TP53, pass for BRCA1 at 390 | TP53: "Found 41 gene records for TP53, of 715 available." and "no written summary could be checked against the records". BRCA1: "BRCA1 is associated with familial cancer of breast, ..." |
| 2. Teaches what a chatbot would not | Needs your eye for TP53, pass for BRCA1 | TP53: about 40 cited ortholog gene ids with their species is checkable detail a chatbot would not give, but there is no sentence, the names are Latin only, and human papers and trials are mixed in. BRCA1: four MedGen-cited conditions including "Fanconi anemia complementation group S". |
| 3. Plain language and Researcher differ | Pass | Researcher "Found 41 gene records ..." with a three-column table and per-source sections; Plain "I found 41 genes related to TP53 ..." with one "Where this answer comes from" list. |
| 4. Seconds to answer | Needs your eye | 22.3, 23.0 and 23.4 s for TP53; 10.4 s for BRCA1; two runs never answered. |
| 5. Screens match design | Pass at 1280, needs your eye at 390 | `run1/tp53_orthologs_researcher_1280_fold.png`: bordered table inside the answer card, uppercase heads, as the prototype's result table (`run1/prototype_tp53_orthologs_researcher_1280.png`). At 390 the live rows stack without labels where the prototype's table keeps its columns and runs off the screen (`run1/prototype_tp53_orthologs_researcher_390.png`). |

## What to look at first

1. Fail, PR-card38-01: TP53 orthologs in Plain language at 1280 searched nothing (`run1/tp53_orthologs_plain_1280.txt`).
2. Fail, PR-card38-02: the BRCA1 control at 1280 searched nothing; 2 of 6 runs failed tonight (`run1/brca1_control_researcher_1280.txt`).
3. Fail, PR-card38-04: the orthologs answer has no written answer, only "Found 41 gene records" (`run1/tp53_orthologs_researcher_1280.txt`).
4. Needs your eye, PR-card38-03: the capture marked both failed runs as passing (`run1/results.json`).
5. Needs your eye, PR-card38-05: the count says 41 and the pager 42, 40 against 41, 41 against 58 (`run1/tp53_orthologs_plain_390.txt`).
6. Needs your eye, PR-card38-08: species are unlabelled Latin names at 390, mouse and zebrafish not on page 1 (`run1/tp53_orthologs_researcher_390_fold.png`).
7. Needs your eye, PR-card38-06: human papers, variants and trials under an orthologs question (`run1/tp53_orthologs_researcher_1280.txt`).
8. Needs your eye, PR-card38-07: 22 to 23 seconds per TP53 answer.
9. Needs your eye, PR-card38-09: no phone design for a result table.

## Overflow and missing design

- Overflow at 390: 0 px on all three live screens (`run1/results.json`). The prototype's rs334 result table runs past the screen at 390 (`run1/prototype_tp53_orthologs_researcher_390.png`).
- No design: an orthologs answer, an Organism column, the stacked phone form of a record table, the Notes list and the "could not finish checking" error screen appear in no prototype screen.

## Not captured

- The golden run: skipped by the owner's decision.
- A second try of the two failed runs: over the 6-question cap, so TP53 in Plain language at 1280 and BRCA1 at 1280 have no answer to judge.
- Pages 2 to 5 of the ortholog list: not paged, so whether human TP53 (NCBIGene:7157), mouse or zebrafish appear, and what pages 5 and 6 of the Plain list hold, is not known.
- The prototype has no orthologs answer: its rs334 answer stands in as the result-table reference, and its BRCA1 answer as the control's (`run1/prototype_brca1_control_researcher_*.png`, not opened).
- The API logs for the two failed runs: not read, so their cause is not established.
- What I read myself: every answer text in `run1/` in full, and the screenshots `tp53_orthologs_researcher_1280_fold.png`, `tp53_orthologs_researcher_390_fold.png`, `tp53_orthologs_plain_390_fold.png` and `prototype_tp53_orthologs_researcher_390.png`. The BRCA1 verdicts and the Plain language 1280 verdict rest on the answer text alone, not a screenshot. Overflow numbers rest on the script's measurement in `results.json`. Nothing rests on a summary.
- Each question once per width: one sample each, so neither a pass nor a fail here is proof of stability.

## Findings

### PR-card38-01: the TP53 orthologs question in Plain language at 1280 ran nothing and showed an error
- Kind: answer
- Verdict: fail
- What: asked once in Plain language at 1280 on deployed develop, the run stopped before searching. The screen shows "0 tool calls · 0 sources cited" and no ortholog, no species, no count line.
- Evidence: `run1/tp53_orthologs_plain_1280.txt`, "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again." and the trust line "Not verified · the run did not finish".
- Why a person would care: the person who picked Plain language to read about TP53 in other species gets an apology and nothing else, on the exact question this card fixed. One sample; cause not established from the browser (guardrail step, the model call, or a rate limit all give this screen).
- NOT CLOSED

### PR-card38-02: the BRCA1 control also ran nothing at 1280; two of six questions failed the same way
- Kind: answer
- Verdict: fail
- What: `Which diseases are associated with BRCA1?` in Researcher at 1280 stopped before searching, with the same screen as PR-card38-01. The same question at 390 answered in 10.4 s. Two of the six questions asked tonight (the third and fifth in run order) failed this way; both were at 1280, which with one sample each says nothing about width.
- Evidence: `run1/brca1_control_researcher_1280.txt`, "0 tool calls · 0 sources cited" and "We could not finish checking your question, so nothing was searched."; `run1/brca1_control_researcher_390.txt` answered.
- Why a person would care: one question in three tonight got an apology instead of an answer, including the golden first question. This may not be card 38's doing; the captures cannot say, and the API logs for these two runs would.
- NOT CLOSED

### PR-card38-03: the capture script counted both failed runs as "screen reached, PASS"
- Kind: answer
- Verdict: needs your eye
- What: the scripted check waits for `answer-meta`, which the error screen also shows, so the two runs that searched nothing passed every scripted check (24 pass, 0 fail).
- Evidence: `run1/results.json`, "PASS | tp53_orthologs_plain at 1280 | screen reached | 16.2 s" beside `run1/tp53_orthologs_plain_1280.txt`, "nothing was searched".
- Why a person would care: a green capture summary would have said all six answered. Anyone reading only the summary would miss PR-card38-01 and 02.
- NOT CLOSED

### PR-card38-04: the orthologs answer has no written answer; its first sentence is a count
- Kind: answer
- Verdict: fail
- What: in all three TP53 answers that ran, there is no prose. The first sentence counts records and a note says no summary could be checked. Nothing says how many species, which model organisms (mouse, zebrafish, fly) carry TP53, or that the human gene is the reference.
- Evidence: `run1/tp53_orthologs_researcher_1280.txt`, "Found 41 gene records for TP53, of 715 available." and "Note: no written summary could be checked against the records, so the records found are listed below with their sources"; `run1/tp53_orthologs_plain_390.txt`, "I found 41 genes related to TP53, out of 715 available."
- Why a person would care: they asked which species have TP53 and got a list to page through, five pages of it, with no sentence telling them the answer. Note also says "listed below" while sitting below the records.
- NOT CLOSED

### PR-card38-05: the count line disagrees with the list it heads
- Kind: answer
- Verdict: needs your eye
- What: the count sentence and the pager under it give different totals in every TP53 answer, and "of 715 available" counts every TP53 record of any kind, not orthologs.
- Evidence: Researcher 1280, "Found 41 gene records" then "Showing 1–10 of 42"; Researcher 390, "Found 40 gene records" then "Showing 1–10 of 41"; Plain 390, "I found 41 genes related to TP53" then "Showing 1–10 of 58" (`run1/tp53_orthologs_*_*.txt`). The brief says the count line is as before, so this may be old.
- Why a person would care: a researcher who counts the species gets a different number from the one the answer states, and "715 available" reads as 715 orthologs exist.
- NOT CLOSED

### PR-card38-06: an orthologs question lists human cancer papers, ClinVar variants and trials
- Kind: answer
- Verdict: needs your eye
- What: beneath the ortholog table, the Researcher answer lists PubMed, ClinVar, OMIM and clinical trial records about human TP53. In Plain language these sit in the same "Where this answer comes from" list as the orthologs, so its pager reads "of 58" and pages 5 and 6 are presumably papers and trials under an orthologs heading (not paged through tonight).
- Evidence: `run1/tp53_orthologs_researcher_1280.txt`, "CLINICAL TRIAL RECORDS FOUND ... The p53 Colorectal Cancer Trial NCT03149679 TERMINATED"; `run1/tp53_orthologs_plain_390.txt`, "Showing 1–10 of 58".
- Why a person would care: they asked about other species and half the screen is human disease records. The follow-ups, "What variants cause it?" and "Which trials are recruiting?", point the same wrong way.
- NOT CLOSED

### PR-card38-07: the TP53 orthologs answer takes 22 to 23 seconds
- Kind: answer
- Verdict: needs your eye
- What: every TP53 answer that ran took more than the owner's 20 second target, none above 25.
- Evidence: the app's own figure, "Answered22.3s" (Researcher 1280), "Answered23.0s" (Researcher 390), "Answered23.4s" (Plain 390) in `run1/tp53_orthologs_*.txt`. The BRCA1 control took 10.4 s.
- Why a person would care: a person waits over twenty seconds for a list with no written answer.
- NOT CLOSED

### PR-card38-08: species show as bare Latin names, unlabelled at 390, in gene-id order
- Kind: screen
- Verdict: needs your eye
- What: at 1280 the Researcher table has a GENE, IDENTIFIER, ORGANISM head and the species sit in their own column, as promised. At 390 the same rows stack as three unlabelled lines, so the species line has no "Organism" label. In both modes the species are scientific names only, ordered by gene id, so the first ten are rabbit, medaka, horse, platypus, trout, catfish, guinea pig, marmoset, orangutan and panda; mouse, zebrafish and fly are not on page 1. Every row's gene name is the same, "tumor protein p53".
- Evidence: `run1/tp53_orthologs_researcher_1280_fold.png` (column head ORGANISM, row 1 "Oryctolagus cuniculus"); `run1/tp53_orthologs_researcher_390_fold.png` (row 1 "tumor protein p53", "NCBIGene:100009292", "Oryctolagus cuniculus", no labels); `run1/tp53_orthologs_plain_390_fold.png` ("tumor protein p53 (Ornithorhynchus anatinus)" wraps to two lines, fits).
- Why a person would care: a student does not know Oryctolagus cuniculus is a rabbit, and a researcher looking for the mouse or zebrafish ortholog has to page through five pages to find it.
- NOT CLOSED

### PR-card38-09: no design for a result table at phone width, and none for an orthologs answer
- Kind: missing design
- Verdict: needs your eye
- What: the prototype's only result table (rs334 genotype table) keeps three columns at 390 and runs past the screen edge; it has no stacked phone form, so the live stacked rows are judged against nothing. The prototype has no canned orthologs answer and no Organism column.
- Evidence: `run1/prototype_tp53_orthologs_researcher_390.png` (the genotype table's SOURCE column extends past 390 px) beside `run1/tp53_orthologs_researcher_390.png`.
- Why a person would care: whether the phone list of species should carry labels is a choice nobody has made yet.
- NOT CLOSED

