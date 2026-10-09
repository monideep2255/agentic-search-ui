# Card 109 product check: a stopped search reads "No answer saved" in "Your searches"

The product reviewer's pre-screen of card 109 (pull request #225, merge d0319502) on deployed develop. It files findings and closes nothing; the owner's retest decides. No golden run: the change is to the wording of a history row (`frontend/src/App.tsx`, `formatHistoryMeta`), not the answer path.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result](#result)
- [What was not captured](#what-was-not-captured)

## Which app answered

- Web bundle: `index-rs6flCQ-.js` at 05:33:19 UTC, `index-NJO4wipr.js` at 05:33:49 UTC, and the same bundle in the signed-in page of both runs (`run_1280_log.json`, `run_390_log.json`, step "bundle"). The new bundle contains the string "No answer saved"; the old one was card 19's.
- API `/health` at the same moment: `{"status":"ok","app_env":"develop"}`.
- One throwaway develop account, its name masked as "account hidden" on every screenshot (log step "email visible unmasked": false).

## Findings

### PR-109-01: After a reload, the stopped search reads "No answer saved · Oct 9" and the answered rows keep their counts (1280)
- Kind: screen
- Verdict: pass
- What: asked "Which diseases are associated with BRCA1?" in Researcher; the first record rows showed at 8.70 s; Stop was the topmost element at its centre and was clicked at 8.75 s with 21 record rows on screen. 4.4 s later the page read "Search stopped" ("No summary was written. The records found before you stopped are below.") and all 21 record rows stayed, first "Familial cancer of breast MedGen:C0346153". After a reload the top row of "Your searches" read "No answer saved · Oct 9"; the answered rows below still read "21 sources cited · Oct 9", "55 sources cited · Oct 9", "12 sources cited · Oct 9" and so on. Two older stopped BRCA1 rows from earlier checks also now read "No answer saved · Oct 9". The stopped row was not clicked.
- Evidence: `run_1280_log.json`, steps "stop button" (`"topmostIsButton":true`), "4.4 s after Stop" (`"stopped":true`, `"listing":21`) and "rail after reload"; screenshots `1280_1_just_stopped.png`, `1280_2_stopped_full.png`, `1280_3_rail_after_reload.png`.
- Why a person would care: "The search I stopped no longer pretends to have an answer; the ones that answered still say how many sources."
- NOT CLOSED

### PR-109-02: Before a reload, the stopped row has no second line at all, and every earlier row with the same question vanished from the list
- Kind: screen
- Verdict: needs your eye
- What: straight after Stop, without a reload, the new row in "Your searches" showed only the question, no "No answer saved" and no date. In the same moment the list shrank from 11 searches to 5: every earlier "Which diseases are associated with BRCA1?" row (answered and stopped, Oct 8 and Oct 9) was gone, and the Oct 8 EGFR row stayed. After a reload all 12 were back. Card 109 changes only the restored rows, so the live row's blank line is outside its scope, and the vanished rows are most likely older behaviour; but a person sees both on the screen card 109 is about.
- Evidence: `run_1280_log.json`, "rail before asking" (11 search rows) and "rail after stop, before reload" (5 search rows; the BRCA1 row has `"meta":null`); screenshot `1280_2_stopped_full.png`.
- Why a person would care: "I stopped a search and my earlier BRCA1 searches disappeared from my list until I refreshed. And the new one does not say it has no answer."
- NOT CLOSED

### PR-109-03: The records kept after Stop are drawn so faint they are hard to read, 4.4 seconds after Stop
- Kind: screen
- Verdict: needs your eye
- What: in the full-page shot taken 4.4 s after Stop, every record row under "Disease records found", "Gene records found", "PubMed records found", "ClinVar records found", "OMIM records found" and "Clinical trial records found" is drawn in a very pale grey, while the "Search stopped" text above is normal ink. Stop was pressed 0.05 s after the first rows appeared, so this may be the records' fade-in (phase 8.7's PR-87-02) halted or still running when Stop landed. The reviewer did not measure the rows' opacity in this run, so whether they ever reach full ink is not known from this capture. Not caused by card 109.
- Evidence: screenshot `1280_2_stopped_full.png` (rows such as "Familial cancer of breast MedGen:C0346153" barely visible); `run_1280_log.json`, "first record row on screen" at 8.70 s and "stop clicked" at 8.75 s.
- Why a person would care: "I stopped it and the records it kept are greyed out, as if they were disabled."
- NOT CLOSED

### PR-109-04: Addendum to PR-109-03, the same rows were full ink 0.4 seconds after Stop
- Kind: screen
- Verdict: needs your eye
- What: the viewport shot taken 0.4 s after Stop shows the disease and gene rows in normal ink ("Familial cancer of breast", "BRCA1 NCBIGene:672", citation numbers in green). The pale rows appear only in the full-page shot 4 s later. So either the rows fade out after Stop, or the full-page capture (which resizes the page to its full height) restarts a fade-in and caught it mid-way. This capture cannot tell the two apart; the owner's own look at a stopped search after a few seconds settles it.
- Evidence: screenshots `1280_1_just_stopped.png` (full ink) and `1280_2_stopped_full.png` (pale).
- Why a person would care: only if the first explanation is true: "the records went grey a few seconds after I stopped."
- NOT CLOSED

### PR-109-05: At 390, "Your searches" reads the same rows, the stopped one "No answer saved · Oct 9", and nothing overflows
- Kind: screen
- Verdict: pass
- What: the same account, signed in without asking a question, page narrowed to 390. The rail opened as the slide-in panel, 248 px wide, every row inside it (right edge 236 px). Its 12 searches read exactly as at 1280 after the reload, in the same order: "No answer saved · Oct 9" on top, then "21 sources cited · Oct 9", "55 sources cited · Oct 9" and so on, with the two older stopped rows also reading "No answer saved · Oct 9". No row's second line is cut (each line's scroll width equals its width, 203 px). Horizontal overflow 0 on the landing page and 0 with the panel open.
- Evidence: `run_390_log.json`, "rail at 390", "overflow 390 landing" (`"doc":0`) and "overflow 390 with rail open" (`"doc":0`); screenshot `390_1_rail_open.png`.
- Why a person would care: "On my phone the list says the same thing: that one has no answer, the others say how many sources."
- NOT CLOSED

### PR-109-06: "Your searches" has no phone design
- Kind: missing design
- Verdict: needs your eye
- What: the slide-in panel at 390 is built from the desktop rail with no design behind it; the code says so ("NO PHONE DESIGN EXISTS FOR THIS RAIL", `frontend/src/components/answer/FollowUp.tsx`), citing `docs/build/design/README.md`. So PR-109-05 judges wording and overflow only, not the panel's look.
- Evidence: `390_1_rail_open.png`; the code comment named above.
- Why a person would care: only through the owner's own taste for the phone panel.
- NOT CLOSED

### PR-109-07: "No answer saved" also covers refusals and clarifying questions, by the code
- Kind: screen
- Verdict: needs your eye
- What: the code comment on the change says a row with no saved answer can be "a search stopped after its records appeared, a refusal, a clarifying question", and all three now read "No answer saved". This check produced only the stopped case; a refused question would read "No answer saved" too, which is true but says less than "Refused" or "Asked you to clarify" would. Not seen on screen in this check.
- Evidence: `frontend/src/App.tsx`, `formatHistoryMeta`, on develop at d0319502.
- Why a person would care: "Did it fail, did I stop it, or did it refuse? The list says the same for all three."
- NOT CLOSED

## Result

| Width | Card 109 result | Rests on |
|---|---|---|
| 1280 | Pass (PR-109-01): stopped row "No answer saved · Oct 9" after reload; answered rows keep "N sources cited" | `run_1280_log.json` and `1280_3_rail_after_reload.png`, both read |
| 390 | Pass (PR-109-05): same rows, overflow 0 | `run_390_log.json` and `390_1_rail_open.png`, both read |

## What was not captured

- Questions spent: one of the two allowed. The 390 check needed none.
- The stopped row was never clicked, as briefed (clicking re-runs the search, a known older issue).
- A refused or clarifying question's row (PR-109-07): not produced; the claim rests on the code, not a screen.
- The prototype comparison: not in this brief. The rail at 1280 is designed (`prototype/app.html`, `renderRail()`); at 390 it has no design (PR-109-06).
- The records' ink after Stop (PR-109-03, PR-109-04): opacity was not measured, so whether the pale rows are real or a capture artifact is open.
- No golden run: card 109 changes only the history row's wording.
- Every verdict above rests on a log or screenshot the reviewer read itself, except PR-109-07, which rests on the code alone. The 390 run began at 1280 and was narrowed to 390, so the panel was already open on arrival; a phone that loads at 390 directly was not tried.
