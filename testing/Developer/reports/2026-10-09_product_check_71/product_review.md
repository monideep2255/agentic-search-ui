# Card 71 product check: A reopened answer keeps its trust line and High-risk claim tag

The product reviewer's pre-screen of card 71's last part (pull request #212, merge 6ebaa4e3) on deployed develop, at 1280 and 390. It files findings and closes nothing; the owner's retest decides. The golden run did not run: a card alone, test queries only, the owner's choice for tonight.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result per step](#result-per-step)
- [Time to answer](#time-to-answer)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health` at 01:30 UTC: `{"status":"ok","app_env":"develop"}`.
- Railway deployment list, read only: search-agent-api (deployment 5f0c4a2e) and search-agent-web (deployment 22963d90) both SUCCESS at 6ebaa4e3, created 2026-10-09 01:25:57 UTC.
- The web bundle `index-DB6gWcmy.js` carries the test id `saved-answer-trust-fallback`, which only commit 52267651 (card 71 fix round) added.

## Findings

### PR-71-01: Query 5's EGFR question did not show "High-risk claim" live tonight, so the tag's reopen path was not seen on a real answer
- Kind: answer
- Verdict: needs your eye
- What: signed in at 1280, the EGFR question's live trust line read only "Based on 55 sources cited, not yet confirmed", one span (`trust-plain`), with no risk span. The stored row behind it reads `risk_tier "low"`. Query 67 names this question as the example of an answer that shows "High-risk claim"; tonight it did not, so the reopened answer correctly showed no tag, and no real answer with the tag was reopened. Whether a high-tier answer reopens with its red tag rests on the build's tests only.
- Evidence: `egfr_live_1280.png` (trust line above "Continue this conversation"); `egfr_log.json`, step "live answer 1280": `"spans":[{"id":"trust-plain","text":"Based on 55 sources cited, not yet confirmed"}]`; the history answer endpoint read by script: `risk_tier 'low'`.
- Why a person would care: "Your test sheet tells me the EGFR question carries a High-risk claim tag, and it does not, so I cannot check the thing this card fixed." Either the example in queries 5 and 67 is stale or the risk tier for this question changed; not checked which.
- NOT CLOSED

### PR-71-02: The reopened answer shows raw bracket numbers where the live answer showed citation chips
- Kind: screen
- Verdict: needs your eye
- What: the live EGFR answer's first sentence ended in one raised range, "of 4002 available.¹⁻²⁰", and every table row carried a small coloured citation number in its own column. Reopened, the same sentence reads "of 4002 available [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19][20]." and every table cell ends in a bracket, such as "Treatment [1]" and "EGFR [44][48]". The rail entry also changed from "13 tool calls · 55 sources cited from 3 layers" to "55 sources cited · Oct 8". Card 71's diff did not touch how the saved answer's text renders (`SavedAnswerMarkdown`), so this predates the card.
- Evidence: `egfr_live_1280.png` beside `egfr_reopened_1280.png` (top of the answer card) and `egfr_reopened_390.png`.
- Why a person would care: "The answer I reopen looks like a rough draft of the one I read, with a wall of [1][2][3] across the first line." Query 5 says no raw bracket numbers such as `[1][2]` show on the answer.
- NOT CLOSED

### PR-71-03: The saved answer screen has no design
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table has no row for the saved answer screen (its "Saved answer, asked" marker, Run again button, trust line position and expanded Sources list), and `prototype/app.html` has no saved answer state. Its trust line is judged here only against the live answer's trust line and the prototype's `.verdict` row, not against a designed saved screen.
- Evidence: coverage table rows read in `docs/build/design/README.md`; `grep -i saved` in `app.html` finds only the sign-in copy "save answers with their sources attached".
- Why a person would care: no designer has said where the trust line and tag belong on a reopened answer. On the live answer the line sits under a collapsed "Sources 55" toggle; reopened, it sits above a fully open list of 55 sources (`egfr_reopened_1280.png`).
- NOT CLOSED

### PR-71-04: The EGFR answer lists records instead of answering, and took 37 seconds to land
- Kind: answer
- Verdict: needs your eye
- What: rubric line 1 fails on the live EGFR answer: its first sentence is "Found 5 clinical trial records and 38 sequence variant records for EGFR, of 4002 available." and a note says "no written summary could be checked against the records, so the records found are listed below with their sources". Nothing says what is known about EGFR mutations in lung cancer. One PubMed row is off topic for lung cancer: "Three-tiered EGFr domain risk stratification for individualized NOTCH3-small vessel disease prediction." Rubric line 4: the trust line appeared 36.98 seconds after Search was pressed, while the status line reads "20.4s". Not caused by card 71, which changes no answer text.
- Evidence: `egfr_live_1280.png`; `egfr_log.json`, step "live answer 1280": `"secondsToTrustLine":36.976`, main text "Answered20.4s · 13 tool calls · 55 sources cited from 3 layers".
- Why a person would care: "I asked what is known about EGFR mutations and got a list of tables with no summary, after waiting over half a minute." The standing goal is every answer within 20 seconds.
- NOT CLOSED

### PR-71-05: On a phone the reopened "High-risk claim" tag breaks across two lines at its hyphen
- Kind: screen
- Verdict: needs your eye
- What: the reopened BRCA1 answer at 390 renders its trust line as "Based on 21 sources cited, not yet confirmed · High-" on the first line and "risk claim" on the second, both parts red. The words and colour match the live answer (see Result per step); only the break is wrong. The live answer at 390 was not captured, so it is not known whether the live line breaks the same way; the live line builds each signal as its own span in a wrapping row, the saved line as one run of text.
- Evidence: `brca1_reopened_390_trustline.png`; `brca1_log.json`, step "reopened 390": `"text":"Based on 21 sources cited, not yet confirmed·High-risk claim"`, risk span colour `rgb(152, 27, 30)`, overflow 0.
- Why a person would care: "On my phone the warning reads 'High-' and then 'risk claim' on the next line, so the one red word that matters is split in two."
- NOT CLOSED

### PR-71-06: The reopened trust line has no "i" explaining how sources are counted
- Kind: screen
- Verdict: needs your eye
- What: at 1280 the live BRCA1 trust line ends in an "i" info button after "High-risk claim"; the reopened line, with the same words and the same red tag, ends at "High-risk claim" with no "i". Not checked whether this predates card 71.
- Evidence: `brca1_live_1280.png` beside `brca1_reopened_1280.png`, the trust line in each (above "Continue this conversation" live, above "Sources" reopened).
- Why a person would care: "When I reopen an answer I cannot find out what 'not yet confirmed' means any more." Query 5 promises the line comes with an "i".
- NOT CLOSED

Beside the prototype (`prototype_answer_1280.png`, `prototype_answer_390.png`, `prototype_verdict_390.png`, its BRCA1 seed answer): the design puts the trust signals directly under a collapsed "Sources 3" toggle and above "Continue this conversation", which is where the live answer puts its line at 1280. The reopened answer puts its line above a fully open Sources list (PR-71-03). The prototype draws signals as pills, which item 9.9 replaced with one plain line by the owner's decision, so the pill shape is not judged. At 390 the prototype keeps "High-risk claim · gene to disease" whole on one row; the reopened answer splits it (PR-71-05). The prototype itself overflows 4 pixels at 390 on its answer screen; the app measured 0.

## Result per step

| Step | 1280 | 390 | Rests on |
|---|---|---|---|
| 1. EGFR live: tag and trust line | No tag. Trust line "Based on 55 sources cited, not yet confirmed" (PR-71-01) | Not captured live | `egfr_live_1280.png` read; `egfr_log.json` |
| 2. EGFR reopened matches live | Pass: "Saved answer · asked Oct 8, 2026, 9:30 PM", trust line "Based on 55 sources cited, not yet confirmed", no tag, no tick, opened in 0.82 s | Pass: same line, no tag, opened in 0.24 s, overflow 0 | `egfr_reopened_1280.png`, `egfr_reopened_390.png`, `egfr_reopened_390_trustline.png` read; `egfr_log.json`, `egfr_reopen_log.json` |
| 3. BRCA1 live, then reopened | Pass: live "Based on 21 sources cited, not yet confirmed · High-risk claim", red `rgb(152, 27, 30)`; reopened the same words in the same red, opened in 0.31 s. Stored `risk_tier "high"` | Words and colour pass, overflow 0; the tag breaks as "High-" / "risk claim" (PR-71-05) | `brca1_live_1280.png`, `brca1_reopened_1280.png`, `brca1_reopened_390_trustline.png` read; `brca1_log.json` |
| 3. No-tag case | Covered by EGFR instead: live showed no tag and reopened shows none | Same | Step 2 rows |
| 4. An answer saved before 6ebaa4e3 | Not possible: the account's history was empty before tonight's first question (history endpoint read by script at 01:30 UTC) | Not possible | Script output, not a screenshot |
| Never more confident than live | Pass on both answers: neither reopened line carries a tick, and both keep "not yet confirmed" | Pass | Screenshots above |

Step 3 ran on the default depth (Researcher), as the stored row's `depth "researcher"` shows. BRCA1 showed the High-risk tag live, so the positive path PR-71-01 could not see on EGFR was seen on BRCA1: the reopened tag matches the live one exactly at 1280.

Horizontal overflow at 390: 0 on all four reopened captures (EGFR twice, BRCA1 once in the main run, EGFR once in the re-capture).

## Time to answer

Seconds from pressing Search to the trust line on screen, signed in at 1280: EGFR 36.98 (status line "20.4s"), BRCA1 39.12 (status line "20.5s"). Median 38.0, worst 39.12. Both over 25 seconds. Both status lines read about 20 seconds while the screen took 37 to 39, a gap of 16 to 19 seconds, the same gap PR-05 of card 59's check measured. Reopening a saved answer took 0.23 to 0.82 seconds.

## What was not captured

- The live answer at 390: the brief asks the live answer at 1280 only, and a third question was not spent. So PR-71-05 does not say whether the live line splits the same way.
- A real answer saved before 6ebaa4e3: none exists on this account (step 4).
- An answer stopped by the per-question cost limit ("Not verified" live): cannot be triggered on demand; rests on the build's tests only.
- Plain language depth: both questions ran at Researcher.
- Cost: two questions asked of the three allowed; the spend per question was not read.
- The golden run: not run, the owner's choice for a card alone tonight.
- Capture note: the first EGFR reopened screenshot at 1280 showed the test account's address in the rail footer, because the page redrew it after the mask ran. It was overwritten in place by a re-capture with a mask that holds through redraws (`egfr_reopen_log.json`); every image now in this folder shows "[account]" there. Logs were scrubbed of the address by script.

Which verdicts rest on what: every verdict above rests on a screenshot or capture log I read myself, except step 4 and the stored `risk_tier` values, which rest on the history endpoint's reply printed by script.
