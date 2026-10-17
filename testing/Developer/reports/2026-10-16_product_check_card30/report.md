# Product check, card 30 step 1, on deployed develop

Pre-screen before the owner's retest of card 30 (pull request #261, merge commit `ec30edb4`). It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before capture, and the capture recorded `app_env` develop and deployed commit `ec30edb4` (`run1/results.json`).
- Asked as a guest, in the browser, each question once at 1280 and once at 390: 8 questions, the spend cap.
- Step 2, the golden run, was skipped: the owner chose "No, test queries only" for tonight (DECISIONS.md, 2026-10-16).
- Capture: `.claude/skills/verify/scripts/capture.mjs`, spec in `run1/spec.json`. Every verdict below rests on an answer text (`run1/*.txt`) or screenshot I read myself, unless it says otherwise.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

Card 30 passes at both widths, 1280 and 390, on what it promised. The line shows once, in Notes, on all six BRCA1 and CFTR answers; no answer is marked confirmed; no sentence calls the listed variants pathogenic; the rs334 control carries no such line. Horizontal overflow is 0 px on all eight captures. Two answer-quality fails sit beside it, neither caused by card 30 as far as these captures show: the CFTR answer at 1280 opens mid-thought, and rs334 never names its condition.

Golden result: not run tonight (owner's decision). Answered against the floor and answered well of the fixed ten are not reported.

## Per answer

| Question | Width | Line in Notes | Trust line | Calls listed variants pathogenic | Time to answer |
|---|---|---|---|---|---|
| BRCA1, Plain language | 1280 | Yes, once | "? Answered", "Based on 57 sources cited, not yet confirmed" | No | 12.9 s |
| BRCA1, Plain language | 390 | Yes, once | same | No | 20.6 s |
| BRCA1, Researcher | 1280 | Yes, once | same | No | 11.1 s |
| BRCA1, Researcher | 390 | Yes, once | same | No | 14.8 s |
| CFTR (query 22) | 1280 | Yes, once | "? Answered", "Based on 71 sources cited, not yet confirmed" | No, but see PR-card30-02 | 14.7 s |
| CFTR (query 22) | 390 | Yes, once | same | No | 14.1 s |
| rs334 control (query 23) | 1280 | No, correctly | "Based on 1 source cited, not yet confirmed · High-risk claim" | Not applicable | 14.5 s |
| rs334 control (query 23) | 390 | No, correctly | same | Not applicable | 4.7 s |

Times are the app's own "Answered" figure in each answer's status line. Median 14.6 s, worst 20.6 s; none over 25 s; one over the owner's 20 s target (BRCA1 Plain language at 390).

The only other occurrence of the word "pathogenic" in any answer is the question itself, and in rs334 the dbSNP clinical significance label "not-provided, protective, likely-benign, pathogenic, other", which is the expected control behaviour.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Needs your eye for BRCA1, fail for CFTR at 1280 and rs334 | BRCA1: "I found 40 genetic variants related to BRCA1, out of 15350 available." It is honest that it cannot say which are pathogenic, but only in Notes. CFTR 1280: "Four additional named variants are ClinVar:1018653, ...". rs334: "I found 1 genetic variant related to rs334." |
| 2. Teaches what a chatbot would not | Needs your eye | BRCA1 and CFTR give cited ClinVar record lists, which a chatbot would not; neither says which variants matter. rs334 names no condition. |
| 3. Plain language and Researcher differ | Pass | Plain: "I found 40 genetic variants related to BRCA1"; Researcher: "Found 40 sequence variant records for BRCA1", with tables per record type. Both carry the same Notes line once. |
| 4. Seconds to answer | Pass, one needs your eye | 4.7 s to 20.6 s; 20.6 s is over the 20 s target. |
| 5. Screens match design | Pass, with a named gap | Live answer at 1280 keeps the prototype's card, question header, status strip, sources and follow-up in the same order (`run1/q115_brca1_plain_1280.png` beside `run1/prototype_q115_brca1_plain_1280.png`). The Notes list has no design. |

## What to look at first

1. Fail, PR-card30-02: the CFTR answer at 1280 opens "Four additional named variants are", before the sentence it is additional to (`run1/q22_cftr_1280.txt`, `run1/q22_cftr_1280_fold.png`).
2. Fail, PR-card30-03: rs334 never names sickle cell disease (`run1/q23_rs334_control_1280.txt`).
3. Needs your eye, PR-card30-01: BRCA1's counts disagree, 40 found, 57 sources, 140 retrieved (`run1/q115_brca1_plain_1280.txt`).
4. Needs your eye, PR-card30-04: the same question gives different text and notes at the two widths (paired `run1/*.txt`).
5. Needs your eye, PR-card30-05: BRCA1 Plain language at 390 took 20.6 s.
6. Needs your eye, PR-card30-06: the Notes list has no design.

## Overflow and missing design

- Overflow at 390: 0 px on all four screens (`run1/results.json`).
- No design: the Notes list under an answer, and the "not yet confirmed" trust text, appear in no prototype screen; `docs/build/design/README.md`'s coverage table lists the answer screen and trust pills, not a Notes list.

## Not captured

- The golden run: skipped by the owner's decision.
- The prototype at 390 and for the other three answers: the prototype has four canned questions and none of these, so one prototype answer at 1280 was captured for layout only. I did not open the 390 prototype shot.
- Screenshots I read myself: BRCA1 Plain language at 1280 and 390, the prototype at 1280, CFTR at 1280 (first screen). Every other verdict rests on the saved answer text, which I read in full, not on a screenshot.
- Each question once per width: one sample each, so a pass here is not proof of stability.

## Findings

### PR-card30-01: BRCA1 opening line lists what was found instead of answering, and its three counts disagree
- Kind: answer
- Verdict: needs your eye
- What: the Plain language BRCA1 answer at 1280 opens "I found 40 genetic variants related to BRCA1, out of 15350 available." The sources pager reads "Showing 1-10 of 57", and a note reads "only 140 of the 15350 records that matched this question in the graph were retrieved". Three numbers (40, 57, 140) for one list.
- Evidence: run1/q115_brca1_plain_1280.txt
- Why a person would care: "Did it find 40, 57 or 140 variants? And it still has not told me which are pathogenic, only that it does not know."
- NOT CLOSED

### PR-card30-02: CFTR answer at 1280 opens with "Four additional named variants are", before the sentence it is additional to
- Kind: answer
- Verdict: fail
- What: the first sentence of the CFTR answer at 1280 is "Four additional named variants are ClinVar:1018653, named NM_000492.4(CFTR):c.364T>A (p.Tyr122Asn), ...", and only after it comes "I found 54 genetic variants related to CFTR, out of 6047 available." The next paragraph starts "Further named variants include". Under a question about clinically significant variants, a prose list of named variants reads as the clinically significant ones; only the Notes line says otherwise.
- Evidence: run1/q22_cftr_1280.txt, run1/q22_cftr_1280.png
- Why a person would care: "Additional to what? And these read like the significant ones, unless I scroll to the notes."
- NOT CLOSED

### PR-card30-03: the rs334 control never names the condition it was asked about
- Kind: answer
- Verdict: fail
- What: asked "What is rs334 and what condition is it associated with?", the answer at 1280 says only "I found 1 genetic variant related to rs334." and lists one record titled "not-provided, protective, likely-benign, pathogenic, other". At 390 it adds "The variant known as rs334 is also identified by the name c.20A>T." Neither names sickle cell disease or HBB. The card 30 line is correctly absent at both widths.
- Evidence: run1/q23_rs334_control_1280.txt, run1/q23_rs334_control_390.txt
- Why a person would care: "I asked what condition it is linked to and got a list of classification words with no condition. Any chatbot says sickle cell."
- NOT CLOSED

### PR-card30-04: the same question gives different answers and notes from one run to the next
- Kind: answer
- Verdict: needs your eye
- What: BRCA1 in Plain language carries the note "no written summary could be checked against the records" at 1280 but not at 390. CFTR at 1280 opens with two prose paragraphs of named variants; at 390 it opens "I found 54 genetic variants related to CFTR, out of 6047 available." with no prose. rs334 at 1280 cites "1 source cited from 1 layer" with marker 1; at 390 "1 source cited from 2 layers" with its sentences marked 2 while the one record is marked 1.
- Evidence: run1/q115_brca1_plain_1280.txt against run1/q115_brca1_plain_390.txt; run1/q22_cftr_1280.txt against run1/q22_cftr_390.txt; run1/q23_rs334_control_1280.txt against run1/q23_rs334_control_390.txt
- Why a person would care: "I asked the same thing twice and got two different answers."
- NOT CLOSED

### PR-card30-05: BRCA1 in Plain language at 390 took 20.6 seconds
- Kind: answer
- Verdict: needs your eye
- What: the status line reads "Answered20.6s · 13 tool calls"; the other seven answers took 4.7 to 14.8 s.
- Evidence: run1/q115_brca1_plain_390.txt
- Why a person would care: "Twenty seconds for a list I still have to check record by record."
- NOT CLOSED

### PR-card30-06: the Notes list carrying card 30's line has no design
- Kind: missing design
- Verdict: needs your eye
- What: card 30's line sits in a "NOTES" bullet list below the sources pager; no prototype screen shows a Notes list.
- Evidence: run1/q115_brca1_plain_390.png, run1/prototype_q115_brca1_plain_1280.png
- Why a person would care: the one sentence that says the list is not the answer sits below the list, where a reader may not reach it.
- NOT CLOSED
