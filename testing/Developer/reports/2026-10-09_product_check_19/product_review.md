# Card 19 product check: Write lights only after the searches finish

The product reviewer's pre-screen of card 19 (pull request #224, merge 3e2c3420) on deployed develop. It files findings and closes nothing; the owner's retest decides. No golden run: the change is to the progress display only (`frontend/src/hooks/useRunView.ts`), not the answer path.

## Table of contents

- [Which app answered](#which-app-answered)
- [How the check was measured](#how-the-check-was-measured)
- [Findings](#findings)
- [Result per run](#result-per-run)
- [What was not captured](#what-was-not-captured)

## Which app answered

- Web bundle: `index-BUMzWQlH.js` before, `index-rs6flCQ-.js` at the first poll (05:19 UTC), and the same bundle in the signed-in page of both runs (`egfr_log.json`, `brca1_log.json`, step "bundle"). The reviewer did not read the deploy's commit from Railway, so that the new bundle is 3e2c3420 rests on it being the only frontend change merged since b01dee92.
- API `/health` at the same moment: `{"status":"ok","app_env":"develop"}`.

## How the check was measured

- The capture script polled the five progress steps (`data-testid="step-*"`, `data-state` live, done or pending), the search chips under "Querying" and the helper lines every 100 ms from pressing Search until the answer line showed.
- A page observer also logged every change of the steps the instant it rendered, with the chips on screen in the frame just before it (`stepChanges`, field `chipsJustBefore`).
- A copy of the event stream was logged beside it (`events`), so each step change can be set against which searches had started and returned (`analysis`, field `openCalls`).
- One caveat, from the code: while Write is live the chips and helper lines are not drawn at all (`RunProgress.tsx`, `!writingNow`). So "a chip reads running while Write is lit" cannot happen on screen by construction; what the screen can show is whether the chips showed a result before Write lit.

## Findings

### PR-19-01: Write never lit with a search still out, and the steps never went back (EGFR, Researcher, 1280)
- Kind: screen
- Verdict: pass
- What: the live step went Guard, Think, Plan, Act, Write and never back. All 13 searches started at 17.26 s and the last returned at 20.94 s; Write lit at 20.97 s with 13 of 13 returned and none open. No search started after Write lit. Overflow 0 at every poll.
- Evidence: `egfr_log.json`, "verdict inputs" (`"liveSequence":["Guard","Think","Plan","Act","Write"]`, `"wentBack":false`, `"writeLitWithOpenCalls":[]`, `"toolStartsAfterWriteLit":0`) and `analysis` at 20.966 (`"started":13,"closed":13,"openCalls":[]`); screenshots `egfr_1280_1_act.png`, `egfr_1280_2_write.png`.
- Why a person would care: "It said it was writing only once it had everything back." That is what card 19 promised.
- NOT CLOSED

### PR-19-02: No search chip ever showed a result; the screen went from every chip "running" straight to Write
- Kind: screen
- Verdict: needs your eye
- What: on screen the chips appeared one by one (cypher_query at 18.63 s, ncbi_efetch at 19.58 s, pubtator_annotate at 20.51 s) and each read "running" until the frame before Write lit, though by then the stream had returned every search (the cypher_query whose result came at 18.09 s still read "running" at 18.63 s). In the frame just before Write lit the chips read "cypher_query running", "ncbi_efetch running", "pubtator_annotate running", and the helper lines all read working. Then Write lit and the chips disappeared, in one render. The cause, read in `frontend/src/hooks/usePacedEvents.ts`: the screen replays the searches at a reading pace, and the first answer word flushes everything that arrived, so the results and Write show together. So card 19's line "lights only after the last running search shows a result" holds in the stream but is never seen on the screen: no chip shows a result before Write.
- Evidence: `egfr_log.json`, `stepChanges` at 20.966 (`"chipsJustBefore":["cypher_queryrunning","ncbi_efetchrunning","pubtator_annotaterunning"]`), `poll` from 18.63 to 20.95, `events` (results from 17.45 to 20.94 s); screenshot `egfr_1280_1_act.png` (both chips "running" at 19 s while the stream had 8 of 13 back).
- Why a person would care: "Every search said running, then it jumped to writing. I never saw one finish." Whether the chips should show their row counts before Write lights is yours to say; the brief's own test (Write never lit while a chip reads running) passes.
- NOT CLOSED

### PR-19-03: The EGFR answer took 27.7 seconds, 17 of them on the Guard step
- Kind: answer
- Verdict: needs your eye
- What: answer line "Answered27.7s · 13 tool calls · 55 sources cited from 3 layers". Guard stayed lit from 0.03 s to 17.22 s; the stream's guard event came at 8.34 s and its think event at 17.22 s. Over the 20 second goal and over 25 seconds. Not caused by card 19, which changes only when Write lights.
- Evidence: `egfr_log.json`, "answer landed (meta shown)" and `events`; the reasoning log in `egfr_1280_1_act.png` reads "8.9s THINK".
- Why a person would care: "Nothing seemed to happen for 17 seconds after I pressed Search."
- NOT CLOSED

### PR-19-04: Write never lit with a search still out, and the steps never went back (BRCA1, Plain language, 390)
- Kind: screen
- Verdict: pass
- What: the live step went Guard, Think, Plan, Act, Write and never back. All 13 searches started at 6.79 to 6.81 s and the last returned at 7.80 s; Act lit at 8.16 s and Write at 8.19 s, with 13 of 13 returned. No search started after Write lit. Horizontal overflow 0 at every one of 149 polls and on the final page.
- Evidence: `brca1_log.json`, "verdict inputs" (`"wentBack":false`, `"writeLitWithOpenCalls":[]`, `"toolStartsAfterWriteLit":0`, `"maxOverflow":0`) and `analysis` at 8.188 (`"started":13,"closed":13,"openCalls":[]`); screenshots `brca1_390_2_write.png`, `brca1_390_3_final.png`.
- Why a person would care: "On my phone it also only said writing once the searches were back."
- NOT CLOSED

### PR-19-05: On the phone run Act was lit for 26 milliseconds, one chip, then Write
- Kind: screen
- Verdict: needs your eye
- What: the searches all returned while the screen was still replaying Think and Plan. Act lit at 8.162 s with one chip, "cypher_query running", and Write lit at 8.188 s. A person sees Plan, then Write; the searches step is skipped to the eye and no chip ever shows a result. Same mechanism as PR-19-02.
- Evidence: `brca1_log.json`, `stepChanges` at 8.162 (`"chipsNow":["cypher_queryrunning"]`) and 8.188 (`"Write=live"`, `"chipsJustBefore":["cypher_queryrunning"]`). The 100 ms poll caught Act only as "Act=done" (step change at 8.2 s), so it is not in any screenshot.
- Why a person would care: "It went from planning to writing; I never saw it search."
- NOT CLOSED

### PR-19-06: The BRCA1 Plain language answer carries two sentences that make no sense alone
- Kind: answer
- Verdict: fail
- What: a paragraph opens "One is double-strand break repair via homologous recombination." with nothing before it saying what "one" is, and the last summary sentence is "BRCA1, and its gene symbol is BRCA1." The first sentence does answer the question (rubric line 1 passes). Not caused by card 19.
- Evidence: `brca1_log.json`, "final", `claimsStart`: "One is double-strand break repair via homologous recombination.⁠24 Another is DNA repair.⁠25 ..." and "BRCA1, and its gene symbol is BRCA1.⁠8, 5"; screenshot `brca1_390_3_final.png` (the sticky footer bar drawn across the middle of the full-page shot is a capture artifact and hides part of the first of these sentences).
- Why a person would care: "One is what? And then it tells me BRCA1's symbol is BRCA1. That makes me doubt the rest."
- NOT CLOSED

### PR-19-07: The EGFR answer opens by counting records rather than answering
- Kind: answer
- Verdict: needs your eye
- What: rubric line 1. The question asks what is known about EGFR mutations in lung cancer and which trials are recruiting; the first sentence is a count. Five recruiting trials do follow straight after it, so the second half of the question is answered. Not caused by card 19.
- Evidence: `egfr_log.json`, "final", `claimsStart`: "Found 5 clinical trial records and 38 sequence variant records for EGFR, of 4002 available." The reviewer read this text, not the full-page screenshot `egfr_1280_3_final.png`.
- Why a person would care: "I asked what is known about these mutations and it told me how many records it found."
- NOT CLOSED

## Result per run

| Run | Card 19 result | Live steps on screen (seconds from Search) | Answer line | Rests on |
|---|---|---|---|---|
| EGFR question, Researcher, 1280 | Pass (PR-19-01), with PR-19-02 | Guard 0.03, Think 17.22, Plan 17.92, Act 18.62, Write 20.97; last search back 20.94 | Answered27.7s · 13 tool calls · 55 sources cited from 3 layers | `egfr_log.json` read; screenshots `egfr_1280_1_act.png`, `egfr_1280_2_write.png` read |
| Query 98, BRCA1, Plain language, 390 | Pass (PR-19-04), with PR-19-05 | Guard 0.04, Think 6.76, Plan 7.46, Act 8.16, Write 8.19; last search back 7.80 | Answered13.0s · 13 tool calls · 21 sources cited from 3 layers | `brca1_log.json` read; screenshots `brca1_390_2_write.png`, `brca1_390_3_final.png` read |

Horizontal overflow at 390: 0 throughout. At 1280: 0 throughout.

Wider-screen note, not filed: in `egfr_1280_2_write.png` the window is scrolled with a blank band above the app bar and the records drawn faint; the faint records are the fade-in already measured in phase 8.7's check (PR-87-02), caught mid-way by the capture.

## What was not captured

- Questions spent: two of the three allowed. The third was not needed.
- The case where some planned searches are skipped: not produced by either question (13 planned, 13 started in both); the test queries document says the frontend test covers it.
- A visible "Write going back to Act" could only be seen if a search started after Write lit; none did, so the never-back rule was observed, not stressed.
- The prototype comparison at both widths and the design coverage check: not in this brief. The chips and the Write step are designed (`docs/build/design/design-system/prototype/app.html` `.pcap` captions); the helper lines have no design, as their own code comment says.
- No golden run: card 19 changes only the progress display.
- Screenshots at the Write moment were taken while the page faded in, so they are faint; the step states rest on the logs, which were read directly. Every verdict above rests on a log or screenshot the reviewer read, none on a summary, except PR-19-07, which rests on the captured answer text and not the full-page screenshot.
