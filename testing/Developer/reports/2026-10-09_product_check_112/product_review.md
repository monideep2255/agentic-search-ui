# Card 112 product check: earlier searches stay in "Your searches" after a Stop

The product reviewer's pre-screen of card 112 (pull request #231, merge c5688270) on deployed develop. It files findings and closes nothing; the owner's retest decides. No golden run: the change is to the history list in `frontend/src/App.tsx`, not the answer path. One question spent, at 1280.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result](#result)
- [What was not captured](#what-was-not-captured)

## Which app answered

- Web bundle: `index-NJO4wipr.js` at 11:14:40 UTC, `index-Dc5jp6r8.js` at 11:15:10 UTC (polled every 30 s), and the same new bundle in the signed-in page of the run (`run_1280_log.json`, step "bundle").
- API `/health` at the same moment: `{"status":"ok","app_env":"develop"}`.
- The throwaway develop account card 109's check used, its name masked as "account hidden" on every screenshot (log step "signed in, email visible unmasked": false).

## Findings

### PR-112-01: Before any reload, every earlier row stays and the stopped row reads "No answer saved · Oct 9" on top (1280)
- Kind: screen
- Verdict: pass
- What: before asking, "Your searches" held 15 rows, 8 of them "Which diseases are associated with BRCA1?". Asked the same question in Researcher; the first record rows showed at 6.93 s; Stop was the topmost element at its centre ("topmostIsButton": true) and was clicked at 6.95 s with 21 record rows on screen. 0.4 s later, with no reload, the list held 16 rows, 9 of them BRCA1: the new row on top reading "No answer saved · Oct 9", and rows 2 to 16 identical in question, second line and order to the 15 rows before asking. The top row still read "No answer saved · Oct 9" in all eight samples from 7.9 s to 11.5 s. Card 109's check saw this list fall from 11 rows to 5, with the new row's second line blank.
- Evidence: `run_1280_log.json`, steps "rail before asking" (15 rows), "stop button", "stop clicked", "rail 0.4 s after Stop" and "rail after stop, before reload" (16 rows); screenshots `1280_0_rail_before.png`, `1280_1_just_stopped.png`, `1280_2_stopped_viewport.png`.
- Why a person would care: "I stopped a search and my earlier searches of the same question stayed put, and the new one says it has no answer."
- NOT CLOSED

### PR-112-02: After a reload, the list is the same 16 rows in the same order and text (1280)
- Kind: screen
- Verdict: pass
- What: after a reload the list held the same 16 rows, in the same order, each with the same second line, as just after Stop: "No answer saved · Oct 9" on top, then the three Escherichia coli rows, and so on down to "55 sources cited · Oct 8". 16 is under the 20-row limit, so the limit was not exercised. The stopped row was not clicked. Overflow at 1280 was 0 before and after the reload.
- Evidence: `run_1280_log.json`, "rail after reload" against "rail after stop, before reload"; "overflow 1280 after reload" (`"doc":0`); screenshot `1280_3_rail_after_reload.png`.
- Why a person would care: "Refreshing the page does not change my list; what I saw is what was saved."
- NOT CLOSED

### PR-112-03: Only the new stopped row is highlighted, not the earlier BRCA1 rows with the same text (1280)
- Kind: screen
- Verdict: pass
- What: card 112 also moved the rail's highlight from "the first row with this question text" to the row of this search. Just after Stop, only the top row carried the highlighted style (class `css-1hjyd8n`, blue text on a pale blue band); the eight earlier BRCA1 rows carried the plain style (`css-1s9wqtc`). After the reload, on the landing page, no row was highlighted. Opening an earlier row to read its saved answer (the other half of the highlight change) was not tried, since the brief allowed no click on a row.
- Evidence: `run_1280_log.json`, "rail 0.4 s after Stop" and "rail after reload" (field `cls`); screenshots `1280_2_stopped_viewport.png` and `1280_3_rail_after_reload.png`.
- Why a person would care: "The list marks the search I am looking at, not some older one with the same words."
- NOT CLOSED

### PR-112-04: The records kept after Stop were full ink 4.5 seconds later, which answers card 109's PR-109-03 and PR-109-04 for this run
- Kind: screen
- Verdict: pass
- What: card 109's check saw the kept record rows drawn pale grey in a full-page shot taken 4.4 s after Stop. This run measured the first three record rows' combined opacity at 11.5 s (4.5 s after Stop): 1, 1, 1. The full-page shot taken a moment later shows every record table in normal ink. So the pale rows in card 109's shot were most likely the full-page capture catching a fade-in, not rows fading out after Stop. One run; not caused by card 112.
- Evidence: `run_1280_log.json`, "record row opacity" (`[1,1,1]`); screenshot `1280_2_stopped_full.png`.
- Why a person would care: "The records I kept after stopping stay readable."
- NOT CLOSED

### PR-112-05: The citation numbers in the kept records jump around: disease 1 to 4, gene "5, 9", PubMed 11, 14, 17, 20, ClinVar 7, 12, 15, 18, 21
- Kind: screen
- Verdict: needs your eye
- What: after Stop the record tables number their rows out of reading order. The numbers are interleaved across tables ("Familial cancer of breast" 1, "BRCA1 NCBIGene:672" 5, 9, "Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis." 11, "NM_007294.4(BRCA1):c.5243_5277+2788del" 7, the trial "Germline BRCA1 and BRCA2 Mutations in Jewish Women Affected by Breast Cancer" 10). With no summary written there is nothing in the text that these numbers point from. Older behaviour, not card 112.
- Evidence: screenshot `1280_2_stopped_full.png`.
- Why a person would care: "Why does the list go 1, 2, 3, 4, then 5, 9, then 11, 14? Am I missing rows?"
- NOT CLOSED

### PR-112-06: The full-page shot shows the footer bar drawn across the PubMed table
- Kind: screen
- Verdict: needs your eye
- What: in the full-page shot the blue "NCBI Agentic Search" footer sits across the PubMed table at the old viewport's bottom edge, hiding its first rows. The viewport shot shows the footer pinned at the bottom of the window, as designed. This is most likely how a pinned footer renders in a full-page capture, not what a person sees while scrolling; the reviewer did not scroll to check.
- Evidence: screenshots `1280_2_stopped_full.png` (footer across the PubMed table) and `1280_2_stopped_viewport.png` (footer at the window's bottom).
- Why a person would care: only if it is real: "a bar covers some of the papers."
- NOT CLOSED

### PR-112-07: Three Escherichia coli searches in the list each read "21 sources cited", the same count as the answered BRCA1 rows
- Kind: screen
- Verdict: needs your eye
- What: the three newest rows before this check, "What Escherichia coli isolates in Pathogen Detection carry...", each read "21 sources cited · Oct 9", and every answered BRCA1 row also reads "21 sources cited". These rows came from other runs on this shared throwaway account, not from this check, and the count comes from the server after a reload too. It may be a real coincidence; the reviewer did not open those rows.
- Evidence: `run_1280_log.json`, "rail before asking", rows 1 to 3; screenshot `1280_0_rail_before.png`.
- Why a person would care: "Every search I make says 21 sources. Is that number real?"
- NOT CLOSED

### PR-112-08: At 390, "Your searches" reads the same 16 rows in the same order and text, and nothing overflows
- Kind: screen
- Verdict: pass
- What: the same account, signed in without asking a question, page narrowed to 390. The rail showed as the slide-in panel, 248 px wide, every row inside it (right edge 236 px). Its 16 rows, question and second line, equal the 1280 list after the reload, in the same order, "No answer saved · Oct 9" on top. No row's second line is cut. Horizontal overflow 0 on the landing page and 0 with the panel open.
- Evidence: `run_390_log.json`, "rail at 390", "overflow 390 landing" (`"doc":0`) and "overflow 390 with rail open" (`"doc":0`); screenshot `390_1_rail_open.png`, read.
- Why a person would care: "On my phone the list is the same as on my laptop."
- NOT CLOSED

### PR-112-09: A second deploy landed between the two captures
- Kind: screen
- Verdict: needs your eye
- What: the 1280 run saw bundle `index-Dc5jp6r8.js` (11:15 UTC); the 390 run at 11:16:55 UTC saw `index-Dp5DL01h.js`, still live at 11:17:08. Develop's head is b2514161, pull request #229 (phase 8.7 follow-ups), merged a minute after card 112 and descended from it, so both bundles carry card 112. #229 touches `frontend/src/hooks/useRunView.ts` (the run view), not the history list. The 1280 check of the Stop itself ran on the first bundle, so the owner's retest on today's develop will see #229 as well.
- Evidence: `run_1280_log.json` and `run_390_log.json`, step "bundle"; `git log origin/develop`.
- Why a person would care: only for the retest: what the owner sees now includes one more change than this check's Stop ran on.
- NOT CLOSED

### PR-112-10: "Your searches" has no phone design
- Kind: missing design
- Verdict: needs your eye
- What: as in card 109's PR-109-06, the slide-in panel at 390 is built from the desktop rail with no design behind it (`docs/build/design/README.md`; the code says "NO PHONE DESIGN EXISTS FOR THIS RAIL" in `frontend/src/components/answer/FollowUp.tsx`). PR-112-08 judges rows and overflow only, not the panel's look.
- Evidence: `390_1_rail_open.png`.
- Why a person would care: only through the owner's own taste for the phone panel.
- NOT CLOSED

## Result

| Width | Card 112 result | Rests on |
|---|---|---|
| 1280, before reload | Pass (PR-112-01): 15 rows became 16, the new row on top "No answer saved · Oct 9", no other row changed | `run_1280_log.json`, `1280_2_stopped_viewport.png`, both read |
| 1280, after reload | Pass (PR-112-02): same 16 rows, order and text | `run_1280_log.json`, `1280_3_rail_after_reload.png`, both read |
| 390 | Pass (PR-112-08): same 16 rows, overflow 0 | `run_390_log.json`, `390_1_rail_open.png`, both read |

## What was not captured

- Questions spent: one, at 1280. The 390 check needed none.
- The stopped row was never clicked, as briefed, so opening a saved answer and its highlight (the other half of PR-112-03) was not seen.
- The 20-row limit: the list held 16, so trimming the oldest row was not exercised.
- A Stop whose request fails (the code leaves the row without "No answer saved" then) was not produced.
- The prototype comparison was not in this brief. The rail at 1280 is designed; at 390 it has no design (PR-112-10).
- No golden run: card 112 changes only the history list.
- Every verdict rests on a log or screenshot the reviewer read itself. PR-112-06 rests on a full-page shot and was not checked by scrolling; PR-112-07 rests on rows from other runs that were not opened. The 390 run began at 1280 and was narrowed, so the panel was already open on arrival.
