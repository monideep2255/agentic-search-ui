# Cards 37 and 36 product check: rs334 lists only rs334, and a date range that could not be applied says so

The product reviewer's pre-screen of cards 37 (pull request #213) and 36 (pull request #215) on deployed develop, merge d5dcc02c, at 1280 and 390. It files findings and closes nothing; the owner's retest decides. Card 32 (pull request #214) has no live trigger and was not exercised. No golden run tonight, by the owner's choice.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result per step](#result-per-step)
- [Time to answer](#time-to-answer)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health` at 01:56 UTC: `{"status":"ok","app_env":"develop"}`.
- Railway deployment list, read only: search-agent-api and search-agent-web both SUCCESS at d5dcc02c, created 2026-10-09 01:50 UTC; the 9cca68c7 and 44d83f92 deployments REMOVED.
- Web bundle served: `index-DB6gWcmy.js`. Cards 36, 37 and 32 change no frontend file (git diff 6ebaa4e3..d5dcc02c on `frontend/` is empty), so the bundle cannot prove the commit; the Railway list is the proof.
- Signed in with the second test account; the account email is masked in every capture.

## Findings

### PR-37-01: The rs334 answer never names a condition, and lists clinical significances where the variant's name belongs
- Kind: answer
- Verdict: fail
- What: asked "What is rs334 and what condition is it associated with?" in Researcher at 1280, the whole answer is one sentence, "Found 1 variant record record for rs334: not-provided, protective, likely-benign, pathogenic, other." The table under "VARIANT RECORD RECORDS FOUND" has one row whose VARIANT column reads "not-provided, protective, likely-benign, pathogenic, other" and whose IDENTIFIER reads "rs334". Sickle cell, or any condition, is named nowhere. The note says "no written summary could be checked against the records, so the records found are listed below with their sources". Card 37's own promise (only rs334 listed) holds; this is rubric lines 1 and 2, and it may predate card 37.
- Evidence: screenshot `S1_rs334_1280.png`; capture log `S1_rs334_log.json`, step "answer texts", `answerBody`.
- Why a person would care: "I asked what condition rs334 is linked to and got a list of review labels, one of which is 'protective', with no disease named. Any chatbot tells me sickle cell."
- NOT CLOSED

### PR-37-02: "variant record record" and "VARIANT RECORD RECORDS FOUND" read as broken English
- Kind: answer
- Verdict: needs your eye
- What: the first sentence says "Found 1 variant record record for rs334", and the table heading says "VARIANT RECORD RECORDS FOUND". The word is doubled in both.
- Evidence: screenshot `S1_rs334_1280.png`; `S1_rs334_log.json`, `answerBody`.
- Why a person would care: "The first line of the answer has a typo, so I trust the rest less."
- NOT CLOSED

### PR-37-03: The RS1 gene answer cites papers about "radial spoke 1" and a viral enzyme
- Kind: answer
- Verdict: needs your eye
- What: "What does the RS1 gene do?" is answered about the gene, "Found 1 gene record for RS1: retinoschisin 1." (NCBIGene:6247), never the variant rs1, so card 37's regression case passes. But two of the five papers under "PUBMED RECORDS FOUND" are about other things that share the letters: "Differential requirements of IQUB for the assembly of radial spoke 1 and the motility of mouse cilia and flagella." (PMID:36417862) and "Heterogeneity of radial spoke components in Tetrahymena cilia." (PMID:40886204); a third, "A viral ADP-ribosyltransferase attaches RNA chains to host proteins." (PMID:37587340), names no retinal gene in its title. Not checked against an older build; card 37 matched rs ids only, so this probably predates it.
- Evidence: screenshot `S2_RS1_1280.png`; capture log `S2_RS1_log.json`, step "answer texts".
- Why a person would care: "I asked about the retinoschisis gene and a third of the papers are about cilia and viruses."
- NOT CLOSED

### PR-37-04: The RS1 answer reached the screen 21 seconds after the server says it finished
- Kind: answer
- Verdict: needs your eye
- What: the answer header reads "Answered 16.3s", but the script, timing from the click on search to the trust line on screen, measured 37.651 seconds. For rs334 the two agreed (header "14.6s", screen 15.064 s). The same gap was filed as PR-05 in the card 59 check.
- Evidence: `S2_RS1_log.json`, step "landed" `"secs":37.651`, `answerMeta` "Answered16.3s"; `S1_rs334_log.json`, "landed" `"secs":15.064`.
- Why a person would care: "It says it took 16 seconds; I waited nearly 40." The standing goal is every answer within 20 seconds.
- NOT CLOSED

### PR-37-05: Narrowing the window to 390 leaves the searches panel covering the whole answer
- Kind: screen
- Verdict: needs your eye
- What: with the searches rail open at 1280, setting the viewport to 390 turned the rail into an overlay over the answer, so the top of the 390 view showed only "YOUR SEARCHES" and a greyed answer. A phone user who opens the app at 390 may never see this; it bites a desktop user who narrows the window. The later captures close the panel before shooting.
- Evidence: screenshots `S1_rs334_390_top.png` and `S1_rs334_390_full.png`.
- Why a person would care: "I made the window narrow and my answer vanished behind a list of my searches."
- NOT CLOSED

### PR-36-01: A picked "last 5 years" window limits only the PubMed list; the 41 papers shown first are from the late 1990s
- Kind: answer
- Verdict: fail
- What: asked "recent papers on BRCA1", the app offered "Recent papers on BRCA1 from the last 12 months?", "... from the last 5 years?" and "... from the last 10 years?". Clicking "from the last 5 years" at once, the plan line reads "...; PubMed papers published in the last 5 years only", and it does not say the range could not be applied, as card 36 promises. But the answer's first sentence is "Found 41 article records for BRCA1, of 3487 available." Its table lists bare ids from PMID:10026184 to PMID:10417300 on page 1, and the knowledge graph sources run [1] PMID 10026184 to [41] PMID 10972993, ids issued around 1999 and 2000. Under "PUBLICATION RECORDS FOUND" sits PMID:20301425 (about 2010). Only the four papers under "PUBMED RECORDS FOUND" (PMID:35432218 to PMID:39510841) fall inside the window. The heading still says "Recent papers on BRCA1 from the last 5 years?". The PMID-to-year reading is mine, from the PMID ranges; the screen shows no years.
- Evidence: screenshots `S3_window_offer_1280.png` and `S3_window_1280.png`; capture log `S3_window_log.json`, steps "offer" and "answer texts".
- Why a person would care: "I picked the last five years and the first 41 papers it shows me are from the 1990s, listed as bare numbers with no titles."
- NOT CLOSED

### PR-37-06: The same rs334 question, asked again 12 minutes later, failed after 15 seconds with no answer
- Kind: answer
- Verdict: needs your eye
- What: the sixth question repeated step 1 exactly (Researcher, "What is rs334 and what condition is it associated with?") so the 390 capture could run without the searches panel in the way. It came back after 15.396 seconds with "0 tool calls · 0 sources cited", "This run could not be completed. Try asking again in a moment." and "Not verified · the run did not finish". The API log, read only, shows the guard model call timing out twice: `point=guardrail.classify ... elapsed_ms=9994 outcome=timeout attempt=1`, then `elapsed_ms=4996 outcome=timeout attempt=2`. This is the guard step, not card 37's code. The question cap meant it was not retried.
- Evidence: screenshots `S1b_rs334_1280.png` and `S1b_rs334_390_top.png`; capture log `S1b_rs334_log.json`, steps "landed" (`answer-failure`) and "answer texts".
- Why a person would care: "I asked the exact question that worked a few minutes ago, waited 15 seconds, and got nothing but 'try again'."
- NOT CLOSED

### PR-36-02: The "How far back" question stays in history as a search with 0 sources
- Kind: screen
- Verdict: needs your eye
- What: after the window was picked, the answer page keeps the first turn collapsed above the answer as "recent papers on BRCA1 0 tool calls · 0 sources cited Show answer". The searches rail lists it as its own row, "recent papers on BRCA1 0 tool calls · 0 sources cited", next to "Recent papers on BRCA1 from the last 5 years? 13 tool calls · 58 sources cited from 3 layers". Not checked whether this predates card 36.
- Evidence: screenshots `S3_window_390_top.png` (collapsed turn) and `S3_window_1280.png` (rail).
- Why a person would care: "My history shows a search that found nothing, when all that happened was the app asked me how far back to look."
- NOT CLOSED

### PR-36-03: The "could not be applied" sentence appears only inside the closed "Show work" panel
- Kind: answer
- Verdict: needs your eye
- What: typed as a new search, "Recent papers on BRCA1 from the last 10 years?" gives a plan line ending "the date range in your question could not be applied, so papers from any year were searched", which is exactly card 36's promise. The plan line only shows after "Show work ▾" is pressed; the capture script pressed it. The answer itself says nothing about the range: it opens "Found 40 article records for BRCA1, of 3487 available." and lists PMID:10026184 onward. This is the verifier's A-36-03, left open as no worse than develop.
- Evidence: screenshots `S4_typed_1280.png` and `S4_typed_390_planline.png`; capture log `S4_typed_log.json`, step "answer texts".
- Why a person would care: "I asked for the last ten years, got papers from 1999, and the only place it admits that is behind a 'Show work' link I never open."
- NOT CLOSED

## Result per step

| Step | 1280 | 390 | Rests on |
|---|---|---|---|
| 1. rs334 in Researcher: no near misses | Pass: one row only, IDENTIFIER "rs334"; no rs334348, rs334353, rs334558 or rs334773 anywhere | Not captured with the answer visible: the first run's 390 shot is covered by the searches panel (PR-37-05), and the repeat run failed (PR-37-06). Overflow 0 on both | Screenshot `S1_rs334_1280.png`, read myself |
| 1. What the rs334 row and its citation say | Row: "not-provided, protective, likely-benign, pathogenic, other" / rs334, citation 1, under "LIVE NCBI APIS 1". No condition named (PR-37-01). The citation card was collapsed in the capture, so its own text was not read | Not captured | `S1_rs334_1280.png`, `S1_rs334_log.json` |
| 2. RS1 is the gene, not rs1 | Pass: "Found 1 gene record for RS1: retinoschisin 1." NCBIGene:6247; off-topic papers filed as PR-37-03 | Overflow 0 | Screenshot `S2_RS1_1280.png`, read myself |
| 3. Pick a window at once | Plan line pass: "PubMed papers published in the last 5 years only", no "could not be applied". Answer limited to the window: fail, the 41 graph articles listed first are ids from about 1999 (PR-36-01) | Plan line pass, same wording; overflow 0 | Screenshots `S3_window_1280.png`, `S3_window_390_top.png`, `S3_window_390_planline.png`, read myself |
| 4. Typed option wording, new search | Pass: plan line "the date range in your question could not be applied, so papers from any year were searched" | Pass, same wording; overflow 0 | Screenshot `S4_typed_390_planline.png` read myself; 1280 from the log text |

Horizontal overflow at 390: 0 on all five captures (`S1_rs334`, `S1b_rs334`, `S2_RS1`, `S3_window`, `S4_typed`, the "answer 390" step of each log). No screen changed in these cards, so there was no prototype comparison and no design gap to name.

## Time to answer

Seconds from the click to the answer on screen (the answer header's own figure in brackets): rs334 15.1 (14.6); RS1 37.7 (16.3); "from the last 5 years" pick 37.7 (34.9), after an offer that came back in 3.9; typed "from the last 10 years" 34.0 (21.5). The repeat rs334 failed at 15.4. Answered median 35.8, worst 37.7. Over 25 seconds: RS1, the 5-year pick and the typed 10-year question. The gap between screen and header is filed as PR-37-04.

## What was not captured

- No golden run, by the owner's choice; no answered or answered-well count, no floor comparison.
- The rs334 citation card's own text: the source group was collapsed in the first run, and the repeat run that would have opened it failed (PR-37-06). So "rs334's citation says what rs334's own record says" is not verified.
- Step 1 at 390 with the answer visible, for the same two reasons.
- Card 32: no live trigger.
- Test query 108's restart path (offer lost after a redeploy): not triggerable from the browser; step 4 covers the same sentence through typed text.
- Plain language: not asked; every question ran in Researcher (step 1) or the default mode.
- Questions spent: 6 of 6 (the offer and the click count as two).
- Verdicts resting on screenshots I read myself: PR-37-01, PR-37-02, PR-37-03, PR-37-05, PR-37-06, PR-36-01, PR-36-02, and the step 4 plan line at 390. Resting on capture logs only: PR-37-04 (timings) and the step 4 plan line at 1280. Resting on the API log: the guard timeout cause in PR-37-06.
