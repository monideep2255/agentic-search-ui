# Card 59 product check: Stop before and after the server finishes

The product reviewer's pre-screen of card 59 (pull request #208, merge 29d8d8a0) on deployed develop, at 1280 and 390. It files findings and closes nothing; the owner's retest decides.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result per step](#result-per-step)
- [Time to answer](#time-to-answer)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health`: `{"status":"ok","app_env":"develop"}`.
- Railway deployment list, read only: search-agent-api and search-agent-web both SUCCESS at 29d8d8a0, created 2026-10-08 06:44 UTC.
- The web bundle `index-Dt7_zOF3.js` carries the string "Stopping…", which only card 59 added.

## Findings

### PR-01: Stop cannot be pressed in the first seconds of a follow-up
- Kind: screen
- Verdict: needs your eye
- What: 1.5 seconds after asking the follow-up "Which diseases are associated with BRCA1?" at 1280, Playwright read the Stop button as disabled, and the click timed out after 1.5 seconds. At 10 seconds the same button was dark and the run was in Act. The search kept going because the stop never registered.
- Evidence: capture log `A_1280_log.json`, step "A3_early_brca1 early-press": `"enabled":false`, `"click-failed: TimeoutError"`, `pressSeconds 1.513`. Screenshot at 10 s (scratch, not committed) shows "10s Stop" with Think and Plan already done at 1.5 s.
- Why a person would care: "I asked the wrong follow-up and hit Stop straight away, and nothing happened." Whether Stop is meant to be grey before the first step is a design question for card 58 rather than card 59, so this asks for your eye, not a fail.
- NOT CLOSED

### PR-02: Stop on a follow-up stays grey for about six seconds
- Kind: screen
- Verdict: needs your eye
- What: second measurement of PR-01, in a fresh conversation at 1280. After the follow-up "Which diseases are associated with BRCA1?" was asked, Stop first became pressable 5.9 seconds later, polled every 50 ms. Once pressed it worked as card 59 describes: "Stopping…" for about 0.3 seconds, then "Search stopped".
- Evidence: capture log `C_1280_log.json`, step "C2_early_brca1 early-press": `"stopFirstPressableSeconds":5.939`; step "C2 screen right after press": two samples `stopping:true`, then `stopped:true`.
- Why a person would care: "Stop is right there but greyed out for the first few seconds, so I cannot cancel a follow-up I just mistyped." Query 98 promises Stop works "until the first sentence of the answer is on screen"; it says nothing about the start of a run.
- NOT CLOSED

### PR-03: After stopping a follow-up there is no box to continue the conversation
- Kind: screen
- Verdict: needs your eye
- What: after "Search stopped" on a follow-up at 1280, the screen shows the earlier HNF1A turn collapsed, the stopped question, "Search stopped", "No answer was produced. Run the same question again, or start a new one.", and only "Run again" and "New search". The follow-up box is gone, so the reader cannot ask "what about it?" in the same conversation. Not checked whether this predates card 59.
- Evidence: screenshot `C_fatal_1280.png` (scratch); capture log `C_1280_log.json`, step "C3 follow-up field visible at once": `"fieldReady":false`, and the script's wait for the follow-up box timed out after 15 seconds.
- Why a person would care: "I stopped one follow-up and now I have to rerun it or start over; I cannot just ask a different follow-up about the answer I already have."
- NOT CLOSED

### PR-04: A stopped search sits in history looking like a refusal, and opening it re-runs it
- Kind: screen
- Verdict: needs your eye
- What: after a reload at 1280, the rail lists the stopped follow-up as "Which diseases are associated with BRCA1? 0 sources cited · Oct 8". That is the same wording the rail uses for refused questions ("Delete the BRCA1 node from the knowledge graph. 0 sources cited · Oct 7"), and nothing says it was stopped. The API row behind it reads `trust_signal "refuse"`, `citation_count 0`, `has_saved_answer false`, so it is not recorded as answered, which is what card 59 promises. Clicking the row started a new run of the question straight away ("4s Stop", "Guard step running"), with no prompt.
- Evidence: capture log `R_1280_log.json`, steps "R reload only rail text", "R api history" and "R opened stopped row".
- Why a person would care: "I stopped that search, but my history shows it as if it had been refused, and tapping it just ran the whole search again." The re-run on open is probably older behaviour for any row without a saved answer; not checked against an older build.
- NOT CLOSED

### PR-05: Answers land 5 to 10 seconds after the server has finished, and four of five took over 25 seconds
- Kind: answer
- Verdict: needs your eye
- What: on the three questions left to answer on their own, the screen showed the answer 4.7 to 10.3 seconds after the server sent its final event: "what about it?" 21.1 s server, 31.2 s screen; HNF1A 23.0 s and 33.3 s; HBB 26.0 s and 30.7 s. When Stop was pressed after the server finished, the answer landed about 0.1 s after the press (CFTR 27.3 s, TP53 20.8 s). Card 59 did not cause the gap; it makes it visible, because pressing Stop now gets the answer sooner than waiting does.
- Evidence: capture logs `A_1280_log.json` ("A2 followup after late stop" `doneSeconds 21.104`, `answeredSeconds 31.204`), `C_1280_log.json` ("C1 base question"), `B2_390_log.json` ("B4 new question after stop", and "B1_late_tp53 after late press": answer present 104 ms after the press).
- Why a person would care: "The answer was ready, and I still sat through ten seconds of animation. Pressing Stop got it faster than waiting." The standing goal is every answer within 20 seconds.
- NOT CLOSED

## Result per step

| Step | 1280 | 390 | Rests on |
|---|---|---|---|
| 1. Stop early ends on "Search stopped" | Pass, but Stop was pressable only from 5.9 s (PR-02) | Pass, Stop pressable from 2.2 s | Screenshots C2 (1280) and B3 (390): "Search stopped. No answer was produced. Run the same question again, or start a new one." "Stopping…" showed for 0.2 to 0.3 s first |
| 1. After reload, not listed as answered | Pass: rail "0 sources cited", API `refuse`, no saved answer (PR-04) | Pass: same, from the API rows and the rail text | `R_1280_log.json`, `B2_390_log.json` step B5 |
| 1. A later "what about it?" does not refer to it | Not captured: no follow-up box after a stopped follow-up (PR-03), and the API probe failed | Not captured | Logs C3 and B6 |
| 2. Stop late shows the whole answer | Pass: pressed 48 ms after `done`, no stop request sent, answer in full with "Based on 21 sources cited, not yet confirmed" | Pass: pressed 29 ms after `done`, answer in full with "Sources disagree on at least one claim" | Screenshot B1 (390) read; text A1 (1280) read |
| 2. History holds it with the same sources | Pass: rail "21 sources cited", API 21, screen 21 | Pass: rail "17 sources cited", API 17, screen 17 | Rail text and API rows in the logs |
| 2. A follow-up can refer to it | Pass: "Found 1 gene record for CFTR: CF transmembrane conductance regulator." | Not asked at 390 | Text A2 (1280) read |
| 3. Stop, then a new question at once | Not captured at 1280 | Pass: New search clicked as soon as "Search stopped" showed; HBB answered in 30.7 s, "Found 1 gene record for HBB: hemoglobin subunit beta." | Screenshot B4 and text read |

Horizontal overflow at 390: 0 on every screen measured (late answer, stopped, new answer, after reload).

## Time to answer

Seconds from asking to the answer on screen: CFTR 27.3 (Stop pressed late), "what about it?" 31.2, HNF1A 33.3, TP53 20.8 (Stop pressed late), HBB 30.7. Median 30.7, worst 33.3. Over 25 seconds: CFTR, "what about it?", HNF1A and HBB.

## What was not captured

- Memory after an early stop: there is no follow-up box after a stopped follow-up, and the API probe sent the wrong field name (422, no run started). Its session id was lost with the page, so redoing it would have taken two more questions and gone past the cap of ten.
- Step 3 at 1280, for the same reason. J-59-04's race, where a failed stop comes back after a new question has started, cannot be triggered on live.
- The prototype comparison and the golden run were not in this brief. Captures are text and logs only; the screenshots stay in scratch.
- Questions spent: 9 of 10, one of them the accidental re-run in PR-04.
