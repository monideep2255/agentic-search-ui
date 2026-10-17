# Product check, card 8, on deployed develop

Pre-screen before the owner's retest of card 8, the line under an answer that names its databases (pull request #266, merge commit `ec547c2a`). It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before the first capture; `origin/develop` was at `ec547c2a`.
- Asked as a guest, in the browser, each question once at 1280 and once at 390: 6 questions, the spend cap.
- Step 2, the golden run, was skipped by the owner's choice for tonight.
- Capture: a short Playwright script per question and width (fresh browser, reduced motion), which saved the full page, the line, the opened "Trust signals" card, the answer text, the Sources list and the measurements, one `.json` per capture. Prototype: `prototype_q01_brca1_*.png`.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Line against Sources](#line-against-sources)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

Card 8's words pass at both widths: every line names the right databases, "not yet confirmed" appears nowhere, the clause shows only on the one answer resting on several databases with a high-stakes fact, and the info card carries the new sentence word for word.

The card fails at 390. Opening the "Trust signals" card under the line runs it off the right edge on all three answers: 107 px on BRCA1, 3 px on CFTR, 97 px on rs334 (PR-card8-02, 04, 06). With the card closed every page is 0 px over at 390. At 1280 nothing overflows.

Golden result: not run tonight (owner's choice). Answered against the floor, and answered well of the fixed ten, are not reported.

## Per answer

| Question | Mode | Width | Line, exactly | Wraps | Time | Overflow closed / card open |
|---|---|---|---|---|---|---|
| Query 1, BRCA1 | Researcher | 1280 | "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared · High-risk claim" | "·" ends row 1, "High-risk claim" on row 2 | 10.1 s | 0 / 0 px |
| Query 1, BRCA1 | Researcher | 390 | same | Database text on 3 rows between words, then "· High-risk claim" | 7.3 s | 0 / 107 px |
| Query 22, CFTR | Researcher | 1280 | "Based on 71 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases" | One row | 12.5 s | 0 / 0 px |
| Query 22, CFTR | Researcher | 390 | same | 2 rows between words, info icon alone on row 3 | 13.3 s | 0 / 3 px |
| Query 23, rs334 | Plain language | 1280 | "Based on 1 source cited, from dbSNP · High-risk claim" | One row | 7.5 s | 0 / 0 px |
| Query 23, rs334 | Plain language | 390 | same | "from dbSNP ·" then "High-risk claim" | 30.2 s | 0 / 97 px |

Times are the app's own "Answered" figure. Median 11.3 s, worst 30.2 s (rs334 at 390, over 25 s, PR-card8-08). No word is broken mid-word; the only wrap defect is the stranded separator (PR-card8-03).

Every opened card read, word for word, ending: "When an answer rests on two or more databases and the values behind one of its high-stakes facts could not be compared, the line adds "their values could not be compared"." (`*_explainer.png`, `explainer_text` in each `.json`).

## Line against Sources

Counted from the opened Sources list in each `.json` (`sources_html_tags`).

| Question | Sources by database | Line says | Matches |
|---|---|---|---|
| BRCA1 | ClinicalTrials.gov 5, ClinVar 5, PubMed 5, MedGen 4, NCBI Gene 1, OMIM 1 (21) | ClinicalTrials.gov, ClinVar, PubMed and 3 other databases | Yes; the top three tie at 5 and read alphabetical; MedGen, the source of all four diseases, is one of the "3 other" (PR-card8-01) |
| CFTR | ClinVar 59 (54 graph, 5 live), ClinicalTrials.gov 5, PubMed 5, NCBI Gene 1, OMIM 1 (71) | ClinVar, ClinicalTrials.gov, PubMed and 2 other databases | Yes |
| rs334 | dbSNP 1 | 1 source cited, from dbSNP | Yes |

The clause "their values could not be compared" showed only on BRCA1, six databases with a high-risk claim. CFTR rests on five databases with no high-risk claim and no clause; rs334 rests on one database with a high-risk claim and no clause, as the rule says. Whether the backend's comparison was right is not visible from the screen.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Pass for BRCA1; fail for CFTR and rs334 | BRCA1: "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." CFTR: "Found 54 sequence variant records for CFTR, of 6047 available." rs334: "I found 1 genetic variant related to rs334." |
| 2. Teaches what a chatbot would not | Needs your eye for BRCA1; fail for CFTR and rs334 | BRCA1 gives cited MedGen records and "approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers", but the lede repeats itself as "Found 4 disease records for BRCA1: ...". CFTR: "this list does not say which are pathogenic" (PR-card8-05). rs334 names no condition (PR-card8-07). |
| 3. Plain language and Researcher differ | Not read | Each question was asked in one mode only, inside the 6-question cap. |
| 4. Seconds to answer | Pass, except rs334 at 390 | 7.3 s to 13.3 s; rs334 at 390 30.2 s. |
| 5. Screens match design | Needs your eye; fail at 390 for the info card | The line sits where the prototype puts its trust pills, under Sources and above the follow-up (`q01_brca1_researcher_1280_trustline.png` beside `prototype_q01_brca1_1280.png`). The prototype shows pills ("Grounded · every claim cited", "High-risk claim · gene to disease"); the app shows a plain text line, a choice made before card 8 (UI fix 11.27). |

## What to look at first

1. Fail, PR-card8-02: at 390 the "Trust signals" card runs 107 px off the screen on BRCA1 (`q01_brca1_researcher_390_explainer.png`).
2. Fail, PR-card8-06: the same on rs334, 97 px (`q23_rs334_plain_390_explainer.png`).
3. Fail, PR-card8-04: the same on CFTR, 3 px (`q22_cftr_researcher_390_explainer.png`).
4. Fail, PR-card8-07: rs334 still names no condition (`q23_rs334_plain_1280.txt`), not caused by card 8.
5. Fail, PR-card8-05: CFTR cannot say which variants are significant (`q22_cftr_researcher_1280.txt`), not caused by card 8.
6. Needs your eye, PR-card8-01: BRCA1's line names trials, ClinVar and PubMed, and MedGen is hidden in "3 other databases" (`q01_brca1_researcher_1280.png`).
7. Needs your eye, PR-card8-03: the "·" separator is stranded when the line wraps (`q01_brca1_researcher_1280_trustline.png`, `q01_brca1_researcher_390_trustline.png`).
8. Needs your eye, PR-card8-08: rs334 took 30.2 s at 390.

## Overflow and missing design

- Overflow at 390 with the info card closed: 0 px on all three answers.
- Overflow at 390 with the info card open: 107 px (BRCA1), 3 px (CFTR), 97 px (rs334). The prototype's BRCA1 answer itself overflows 4 px at 390.
- No design: the database-naming line's wording and the "Trust signals" info card under it appear in no design file. `components/trust-pills.html` and the prototype design pills ("Grounded", "High-risk claim", "3 layers agreed") and no info card, so the card's placement at 390 is judged only by the overflow measurement, not against a design.

## Not captured

- The golden run: skipped by the owner's choice.
- Rubric line 3: each question asked in one mode only, within the 6-question cap.
- A "Confirmed by N independent databases" or "Sources disagree on at least one claim" line, and a line resting on four sources all from one database: none of the three questions produced one, so "read as before" is not checked.
- The prototype for CFTR and rs334: it has a canned BRCA1 answer only.
- The 1280 BRCA1 capture did not open the source groups; its Sources count is taken from the 390 capture of the same question, which listed the same 21 records.
- Screenshots I opened myself: `q01_brca1_researcher_390_explainer.png`, `q01_brca1_researcher_390_trustline.png`, `q01_brca1_researcher_1280_trustline.png`, `q01_brca1_researcher_390.png` (too small to read detail), `q22_cftr_researcher_390_explainer.png`, `q22_cftr_researcher_1280_trustline.png`, `q23_rs334_plain_390_explainer.png`, `q23_rs334_plain_1280.png`, `prototype_q01_brca1_390.png`. Every other verdict rests on the saved answer text or the `.json` measurements, read in full, not on a summary. In the full-page 1280 shots the pinned footer band is drawn across the page where the first screen ends; it is pinned to the bottom of the screen, not covering the line.
- Each question once per width: one sample each, so a pass here is not proof of stability.

## Findings

### PR-card8-01: BRCA1's line names trials, ClinVar and PubMed, not the disease database the answer rests on
- Kind: answer
- Verdict: needs your eye
- What: For "Which diseases are associated with BRCA1?" in Researcher at 1280 the line reads "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared". The four diseases in the first sentence are all MedGen records (citations 1 to 4). By the answer's own record tables, ClinicalTrials.gov, ClinVar and PubMed carry five records each and MedGen four, so the three named are the most cited, tied, and the order reads alphabetical. The count is right: six databases (MedGen, NCBI Gene, PubMed, ClinVar, OMIM, ClinicalTrials.gov), three named plus "3 other databases".
- Evidence: `q01_brca1_researcher_1280.txt`, `q01_brca1_researcher_1280.png`
- Why a person would care: a researcher asking about diseases reads that the answer rests on trials and papers, and MedGen, where the diseases come from, is hidden in "3 other databases".
- NOT CLOSED

### PR-card8-02: at 390 the "Trust signals" card runs 107 px off the right edge of the screen
- Kind: screen
- Verdict: fail
- What: On BRCA1 in Researcher at 390, opening the info card under the line widens the page from 390 to 497 px. The card is 358 px wide and starts at x 139, beside the info icon that follows "High-risk claim" on the line's third row, so it ends at x 497. With the card closed the page is 0 px over.
- Evidence: `q01_brca1_researcher_390_explainer.png` (the page has shifted sideways and the card's right edge is past the screen), `q01_brca1_researcher_390.json` ("overflow_explainer_open": scroll width 497, client width 390; "explainer_box" left 139, right 497)
- Why a person would care: on a phone, tapping the info icon to learn what the line means slides the page sideways and cuts the explanation off at the right; they have to scroll sideways to read it.
- NOT CLOSED

### PR-card8-03: the longer line pushes "High-risk claim" to its own row, leaving the "·" separator stranded
- Kind: screen
- Verdict: needs your eye
- What: On BRCA1 in Researcher, the database line is long enough that "High-risk claim" no longer fits beside it. At 1280 the line ends "...their values could not be compared ·" and "High-risk claim" starts the next row. At 390 the database line takes three rows and the next row starts with the separator: "· High-risk claim". The words themselves wrap between words; nothing is cut or overlaps.
- Evidence: `q01_brca1_researcher_1280_trustline.png`, `q01_brca1_researcher_390_trustline.png`; `q01_brca1_researcher_390.json` (the database span is 62 px tall at a 20.6 px line height, three rows; the line box is 89 px tall)
- Why a person would care: a dot at the end of a line or the start of the next looks like a stray mark, and the red "High-risk claim" reads as a separate note rather than part of the same verdict.
- NOT CLOSED

### PR-card8-04: on CFTR at 390 the "Trust signals" card also passes the right edge, by 3 px
- Kind: screen
- Verdict: fail
- What: Same card as PR-card8-02, a second answer. Here the line is two rows with the info icon alone on a third row at x 35, so the card starts at x 35 and, at 358 px wide, ends at x 393 on a 390 px screen. With the card closed the page is 0 px over. The card is 280 px wide at 1280 and stays on screen there (left 775, right 1055).
- Evidence: `q22_cftr_researcher_390.json` ("overflow_explainer_open": scroll width 393, client width 390; "explainer_box" left 35, right 393), `q22_cftr_researcher_390_explainer.png` (the card's right border touches the screen edge)
- Why a person would care: small here, but it shows the card is sized to the screen while being placed at the icon, so wherever the icon lands the card can run off the screen (107 px on BRCA1).
- NOT CLOSED

### PR-card8-05: CFTR's answer never says which variants are clinically significant
- Kind: answer
- Verdict: fail
- What: Asked "Which clinically significant variants have been reported in CFTR?", the first sentence is "Found 54 sequence variant records for CFTR, of 6047 available." and the notes say "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this list does not say which are pathogenic." The first rows are rare missense changes such as "c.1384G>A (p.Ala462Thr)"; F508del is not named in the answer text. Not caused by card 8; recorded because the brief asks for the rubric read.
- Evidence: `q22_cftr_researcher_1280.txt`, `q22_cftr_researcher_390.txt`
- Why a person would care: a clinician asking for the significant CFTR variants gets a list that says outright it cannot tell them which are significant.
- NOT CLOSED

### PR-card8-06: on rs334 at 390 the "Trust signals" card runs 97 px off the right edge
- Kind: screen
- Verdict: fail
- What: Third answer with the card past the screen at 390. The info icon follows "High-risk claim" on the line's second row, the card starts at x 129 and ends at x 487 on a 390 px screen. The line itself wraps as "Based on 1 source cited, from dbSNP ·" then "High-risk claim", the same stranded separator as PR-card8-03, at 390 only; at 1280 it is one row.
- Evidence: `q23_rs334_plain_390.json` ("overflow_explainer_open": scroll width 487, client width 390; "explainer_box" left 129, right 487), `q23_rs334_plain_390_explainer.png`, `q23_rs334_plain_1280.png`
- Why a person would care: as PR-card8-02; on all three answers at phone width the explanation is cut off or touches the edge.
- NOT CLOSED

### PR-card8-07: rs334 still names no condition
- Kind: answer
- Verdict: fail
- What: Asked "What is rs334 and what condition is it associated with?" in Plain language, the answer is "I found 1 genetic variant related to rs334." and one row, "Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other". Sickle cell disease is never named. Same at both widths. Not caused by card 8; carried from PR-card37-02.
- Evidence: `q23_rs334_plain_1280.txt`, `q23_rs334_plain_390.txt`, `q23_rs334_plain_1280.png`
- Why a person would care: the one thing the question asks, the condition, is missing, and a general chatbot would say sickle cell disease at once.
- NOT CLOSED

### PR-card8-08: rs334 took 30.2 seconds at 390
- Kind: answer
- Verdict: needs your eye
- What: The app's own figure read "Answered30.2s" for rs334 in Plain language at 390; the same question took 7.5 s at 1280. Three tool calls both times. One sample, so it cannot say whether this is the answer path or a slow moment.
- Evidence: `q23_rs334_plain_390.txt` (meta line "? Answered30.2s · 3 tool calls · 1 source cited from 1 layer")
- Why a person would care: half a minute for a one-record answer is past the owner's 20 second target and past 25 seconds.
- NOT CLOSED
