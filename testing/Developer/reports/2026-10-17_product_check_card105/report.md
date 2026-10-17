# Product check, card 105, on deployed develop

Pre-screen before the owner's retest of card 105 (pull request #268, merge commit `dc566429`). It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before capture, and each capture recorded it again (`run1/*.json`, field `health`).
- Asked as a guest, in the browser, at the default answer mode (Plain language), each question once at 1280 and once at 390.
- Step 2, the golden run, was skipped by the owner's choice for tonight.
- Capture: a short Playwright script (kept outside the repository), one fresh browser per width. It records the "How far back" choices, clicks one, and saves the full-page screenshot, the answer text, the PubMed links and the overflow at each width into `run1/`.
- Paper years come from PubMed's own esummary record for each PMID the answer cited, looked up after capture.

## Table of contents

- [Findings](#findings)
- [Result](#result)
- [Per answer](#per-answer)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)

## Findings

### PR-card105-01: A 1993 paper is listed under the "last 5 years" window
- Kind: answer
- Verdict: fail
- What: after picking "Recent papers on BRCA1 from the last 5 years?", the "Where this answer comes from" list shows row 10, "Published paper", which is PubMed 20301425 (GeneReviews, "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer", PubMed date 1993). It comes from the enrichment layer ("L3 · literature", "literature_mention"), not the knowledge graph, so the card's graph filter does not reach it. The four papers that lead the answer are inside the window: 35432218 (2022), 38266640 (2024), 39052257 (2024), 39510841 (2025).
- Evidence: `run1/brca1_5y_1280.png`, `run1/brca1_5y_1280.txt`: "Published paper	⁠10" and "[10] pubmed 20301425 L3 · literature".
- Why a person would care: "I asked for the last five years and one of the papers listed is from 1993, with no title."
- NOT CLOSED

### PR-card105-02: The windowed BRCA1 answer took 28.2 s at 1280
- Kind: answer
- Verdict: needs your eye
- What: the app's own figure after the pick reads "Answered 28.2s · 13 tool calls · 17 sources cited from 2 layers", over the owner's 20 s target and over 25 s.
- Evidence: `run1/brca1_5y_1280.json`, field `meta`.
- Why a person would care: "I clicked a choice and waited almost half a minute."
- NOT CLOSED

### PR-card105-03: The windowed answer's first sentence does not name the window
- Kind: answer
- Verdict: needs your eye
- What: the first sentence is "I found 4 published papers related to BRCA1." It counts the windowed papers correctly but neither it nor the answer body says "from the last 5 years"; only the echoed question heading does. It then turns to the gene's summary ("The BRCA1 gene is a tumor suppressor ...") cited to the Gene record, not to papers.
- Evidence: `run1/brca1_5y_1280.txt`.
- Why a person would care: "Four papers from when? I have to trust that my click was applied."
- NOT CLOSED

### PR-card105-04: The 1993 paper is listed at 390 too
- Kind: answer
- Verdict: fail
- What: the separate run at 390 lists the same four in-window papers (35432218, 38266640, 39052257, 39510841) and the same row 10, "Published paper", PubMed 20301425 (1993). Two of two windowed BRCA1 runs show it, so it is not a one-off.
- Evidence: `run1/brca1_5y_390.png`, `run1/brca1_5y_390.txt`: "Published paper⁠10"; `run1/brca1_5y_390.json`, field `links`.
- Why a person would care: same as PR-card105-01, on a phone.
- NOT CLOSED

### PR-card105-05: The empty-window answer leads with variants, and the window line sits at the bottom under Notes
- Kind: answer
- Verdict: needs your eye
- What: for "recent papers on C9orf43" with "the last 12 months" picked, the owner's line appears word for word: "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." No paper is listed, so no graph paper leaks. But the answer opens with "I found 1 gene and 5 genetic variants related to C9orf43.", lists five ClinVar variants, and puts the window line under "NOTES" after the list, beside "Note: no written summary could be checked against the records". The trust line reads "? Answered" with "Based on 6 sources cited from ClinVar and NCBI Gene".
- Evidence: `run1/c9orf43_short_1280.png`, `run1/c9orf43_short_1280.txt`.
- Why a person would care: "I asked for recent papers and got a list of variants; the answer to my question is a footnote."
- NOT CLOSED

### PR-card105-06: The "How far back" ask-back and the Notes line have no design
- Kind: missing design
- Verdict: needs your eye
- What: the prototype (`docs/build/design/design-system/prototype/app.html`) has no ask-back state and no "Notes" block; its answer screen goes straight from question to cited answer. The live ask-back ("One more detail needed", "How far back should I search?", three pill choices) and the Notes block that carries the card's empty-window line were judged for overflow and placement only, not against a look.
- Evidence: `run1/brca1_5y_390_picker.png`, `run1/c9orf43_short_390.png`, `run1/prototype_answer_390.png`.
- Why a person would care: the one sentence that answers "were there any recent papers?" sits in a block nobody designed.
- NOT CLOSED

### PR-card105-07: The unpicked control at 390 carries garbled sentences
- Kind: answer
- Verdict: needs your eye
- What: the BRCA1 control at 390 reads "BRCA1, and the gene name is BRCA1." and "One is double-strand break repair via homologous recombination. Another is DNA repair." The first sentence is unchanged and right. The card touched only the windowed path, so this is likely older, but a person sees it on the control.
- Evidence: `run1/brca1_control_390.txt`.
- Why a person would care: "The second paragraph reads like it was cut up."
- NOT CLOSED

## Result

Card 105 does most of what the owner decided, and fails one line of it.

- Holds, at both widths: after "the last 5 years" the four papers that lead the BRCA1 answer are PubMed papers from 2022 to 2025, and the count line counts them ("I found 4 published papers related to BRCA1."). No knowledge graph paper is cited: both windowed answers cite from 2 layers, live NCBI and enrichment, none from the graph.
- Holds, at both widths: for C9orf43 with "the last 12 months", the owner's empty-window line appears word for word and no paper is listed.
- Holds, at both widths: the unpicked control has no window line and opens with the same disease sentence as the card 38 check of 2026-10-17.
- Fails, at both widths: under the 5-year window the source list still shows a 1993 PubMed paper, row 10 "Published paper", from the enrichment layer (PR-card105-01, PR-card105-04). It is not the graph paper the card targeted, but the owner's words were "only PubMed papers from that window".
- Horizontal overflow at 390 is 0 px on all three questions, with the ask-back shown and with every source opened.

What else would produce the same picture: the absence of a graph paper could also be the graph returning no Article rows for these questions tonight; there is no capture from before the merge to compare, so the 1999 graph paper's disappearance is not shown to be this change's doing.

Golden result: not run tonight (owner's decision). Answered against the floor, and answered well of the fixed ten, are not reported.

## Per answer

All asked as a guest in Plain language, the default. Times are the app's own "Answered" figure for the run after the pick; the ask-back itself came back in about 2 s every time.

| Question | Picked | Width | Papers listed, with PubMed year | Window line | Trust line | Time |
|---|---|---|---|---|---|---|
| recent papers on BRCA1 | the last 5 years | 1280 | 35432218 (2022), 38266640 (2024), 39052257 (2024), 39510841 (2025); and row 10, 20301425 (1993) | none | "✓ Answered"; "Based on 17 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 2 other databases" | 28.2 s |
| recent papers on BRCA1 | the last 5 years | 390 | the same five | none | the same | 12.9 s |
| recent papers on C9orf43 | the last 12 months, the shortest offered | 1280 | none | "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." | "? Answered"; "Based on 6 sources cited from ClinVar and NCBI Gene" | 13.1 s |
| recent papers on C9orf43 | the last 12 months | 390 | none | the same | the same | 11.0 s |
| Which diseases are associated with BRCA1? | none, control | 1280 | 28976962, 35432218, 36914836, 39261728, 39265497 cited as sources | none | "? Answered"; "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared · High-risk claim" | 10.6 s |
| Which diseases are associated with BRCA1? | none, control | 390 | the same five | none | the same | 7.7 s |

The choices offered were the same for both genes: "from the last 12 months?", "from the last 5 years?", "from the last 10 years?". Time to answer over the six: median 12.0 s, worst 28.2 s; one over 25 s (BRCA1, 5 years, 1280), four of six under the owner's 20 s.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Needs your eye for BRCA1 windowed, fail for C9orf43, pass for the control | "I found 4 published papers related to BRCA1." names no window; "I found 1 gene and 5 genetic variants related to C9orf43." answers a papers question with variants; "BRCA1 is associated with familial cancer of breast, ..." |
| 2. Teaches what a chatbot would not | Pass for BRCA1 windowed, fail for C9orf43, pass for the control | "BRCA1-mutated tumors show higher EXO1 expression and more genomic scarring compared with BRCA1-proficient tumors." cited to a 2024 paper; C9orf43 has "no written summary"; the control names four MedGen conditions including "Fanconi anemia complementation group S". |
| 3. Plain language and Researcher differ | Not read | Researcher was not asked; spend went to the two widths. |
| 4. Seconds to answer | Needs your eye | 28.2 s for BRCA1 windowed at 1280; the rest 7.7 to 13.1 s. |
| 5. Screens match design | Pass for the answer screen at both widths, gap for the ask-back and Notes | `run1/brca1_control_390.png` beside `run1/prototype_answer_390.png`: same card, heading with "New search", meta line, body, sources, "Continue this conversation", in that order. The ask-back and Notes have no design (PR-card105-06). |

## What to look at first

1. Fail, PR-card105-01 and PR-card105-04: a 1993 paper, row 10 "Published paper", listed under the 5-year window, at both widths (`run1/brca1_5y_1280.png`, `run1/brca1_5y_390.png`).
2. Needs your eye, PR-card105-05: the empty-window line is right but sits under Notes after a list of variants (`run1/c9orf43_short_1280.png`).
3. Needs your eye, PR-card105-03: the windowed answer never says which window it used (`run1/brca1_5y_1280.txt`).
4. Needs your eye, PR-card105-02: 28.2 s for the windowed BRCA1 answer at 1280 (`run1/brca1_5y_1280.json`).
5. Needs your eye, PR-card105-06: no design for the ask-back or Notes.
6. Needs your eye, PR-card105-07: garbled control sentences at 390, likely older than this card.

Passed at both widths, 1280 and 390: no. The empty-window line and the control pass at both; the 5-year window fails at both on the 1993 paper.

## Overflow and missing design

- Overflow at 390: 0 px on every live capture, with the ask-back shown, with the answer shown and with all sources opened (`run1/*_390.json`, fields `overflow_picker`, `overflow`, `overflow_sources_open`). The prototype's own answer screen measured 4 px at 390.
- No design: the "How far back" ask-back and the Notes block (PR-card105-06).

## Not captured

- The golden run, Step 2: skipped by the owner's choice for tonight.
- Researcher mode: not asked, so rubric line 3 is unread; six of the eight allowed questions were used.
- A capture from before the merge: none, so whether a graph paper of about 1999 used to appear on these exact questions is not shown here.
- The 10-year window and BRCA1's 12-month window: not picked.
- Every verdict above rests on a screenshot or answer text read directly in this check: `run1/brca1_5y_1280.png` and `.txt`, `run1/brca1_5y_390_picker.png`, `run1/brca1_5y_390.txt`, `run1/c9orf43_short_1280.txt`, `run1/c9orf43_short_390.png` and `.txt`, `run1/brca1_control_1280.txt`, `run1/brca1_control_390.txt`, `run1/prototype_answer_390.png`. The screenshots `run1/brca1_5y_390.png`, `run1/c9orf43_short_1280.png`, the control screenshots and `run1/prototype_answer_1280.png` were captured but only their text was read. Paper years rest on PubMed esummary, not on the app, which shows no year.
