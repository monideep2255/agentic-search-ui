# Product check of cards 121 and 123 on develop, 2026-10-29

A pre-screen before the owner retests. It closes nothing; the owner's verdict closes.

- Target: develop web `https://search-agent-web-develop-2aeb.up.railway.app`, API `/health` read `{"status":"ok","app_env":"develop"}` before the first capture.
- Deployed commit: b5690f98 (merge of #311, on top of #310), as stated in the brief.
- Asked as a guest, no sign-in. No golden run, by the brief.
- Capture: a Playwright script run from `frontend/`, one fresh browser per question; it saves the answer text, a full-page screenshot at 1280 and 390, every visible "About ..." info card opened with its bounding box, and `scrollWidth - innerWidth`.

## Table of contents

- [Findings](#findings)
- [Summary](#summary)

## Findings

### PR-121-123-01: The variant table heading names "record" once
- Kind: screen
- Verdict: pass
- Card: 121
- What: query 119 in Researcher shows the heading "Variant records found", rendered uppercase as "VARIANT RECORDS FOUND", at 1280 and 390.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q119_researcher_1280_full.png`, `q119_researcher_390_full.png`, `q119_researcher_log.json` (headings: "Variant records found", text-transform uppercase).
- Why a person would care: the heading no longer reads "Variant record records found".
- NOT CLOSED

### PR-121-123-02: Query 119's count line does not match the test queries document
- Kind: answer
- Verdict: fail
- Card: earlier (card 131's count line); card 121 changed only the heading string in `_answer_parts`
- What: expected "Found 2 variant records for rs334 and rs6025: rs334 [1] and rs6025 [2]." The answer reads "The literature name c.20A>T corresponds to rs334.3 Found 2 literature variant records for rs334 and rs6025: c.20A>T and c.1691G>A.3, 4". The count line names the literature HGVS names, not the rs ids, and it is not the first sentence. One run only.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q119_researcher_answer.txt`, `q119_researcher_1280_full.png`.
- Why a person would care: someone asking "what are rs334 and rs6025" is told first that "the literature name c.20A>T corresponds to rs334", which does not say what either variant is.
- NOT CLOSED

### PR-121-123-03: Citation markers 3 and 4 appear while the answer says 2 sources were cited
- Kind: answer
- Verdict: needs your eye
- Card: earlier
- What: the opening sentences carry markers 3 and 4; the table carries 1 and 2; the meta line says "2 sources cited from 2 layers", the Sources disclosure shows 2, and the line under the answer says "Based on 2 sources cited, all from dbSNP". "From 2 layers" beside "all from dbSNP" also reads as a contradiction. I did not open markers 3 and 4.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q119_researcher_1280_full.png`, `q119_researcher_answer.txt`.
- Why a person would care: a reader counting sources sees four numbers but is told there are two, and is told two layers and one database in the same answer.
- NOT CLOSED

### PR-121-123-04: Query 23 in Researcher meets every "What you should see" line
- Kind: answer
- Verdict: pass
- Card: 121 (heading) and earlier (the other lines)
- What: heading "Variant records found" (uppercase), "record" once. No note listing conditions never mentioned; no "Patient condition unchanged" or "Condition of fetal membrane". Only rs334 is listed, no rs334348 or similar. The row reads "rs334 | rs334 | HBB | not-provided, protective, likely-benign, pathogenic, other" under a column headed "CLINICAL SIGNIFICANCE". No horizontal overflow at 390 (0 px).
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q23_researcher_answer.txt`, `q23_researcher_1280_full.png`, `q23_researcher_390_full.png`, `q23_researcher_log.json`.
- Why a person would care: the record is named rs334 and the table heading reads cleanly.
- NOT CLOSED

### PR-121-123-05: Query 23 never says what condition rs334 is associated with, and its summary says one thing twice
- Kind: answer
- Verdict: fail
- Card: earlier (rubric lines 1 and 2; card 147's summaries that open mid-thought is related)
- What: the first sentence is "Found 1 literature variant record for rs334: c.20A>T." The summary is "The variant rs334 corresponds to the literature variant name c.20A>T." followed by "The variant rs334 is identified in the literature by the name c.20A>T." Sickle cell disease is never named; the only hint is the dbSNP significance list in the table.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q23_researcher_answer.txt`.
- Why a person would care: they asked which condition rs334 is linked to and the answer tells them its HGVS name, twice, which any chatbot would beat.
- NOT CLOSED

### PR-121-123-06: Query 23 cites marker 2 while saying 1 source was cited
- Kind: answer
- Verdict: needs your eye
- Card: earlier, same pattern as PR-121-123-03
- What: the opening and summary sentences carry marker 2; the table carries 1; the meta line reads "1 source cited from 2 layers" and the line under the answer "Based on 1 source cited, from dbSNP".
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q23_researcher_answer.txt`, `q23_researcher_1280_full.png`.
- Why a person would care: a numbered source 2 that the count says does not exist makes the citations look unreliable.
- NOT CLOSED

### PR-121-123-07: Query 23 in Plain language has no "records found" heading at all, so the card 121 heading is not exercised there
- Kind: answer
- Verdict: pass, with a note
- Card: 121 (not reached in this mode) and earlier
- What: Plain language shows "WHERE THIS ANSWER COMES FROM" over the line "Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other", which matches query 23's Plain language line. "record" appears in no heading, so it is never doubled. No invented condition note, only rs334. No overflow at 390 (0 px).
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q23_plain_answer.txt`, `q23_plain_1280_full.png`, `q23_plain_390_full.png`.
- Why a person would care: the Plain language reader sees the record described in words, with nothing repeated.
- NOT CLOSED

### PR-121-123-08: Query 23 in Plain language writes no summary and names no condition
- Kind: answer
- Verdict: fail
- Card: earlier
- What: the whole answer is "I found 1 genetic variant related to rs334." plus the record line and the note "Note: no written summary could be checked against the records, so this answer lists the records found with their sources". One run only.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q23_plain_answer.txt`, `q23_plain_390_full.png`.
- Why a person would care: a student asking what condition rs334 is linked to gets no answer to that question, only a list of significance labels such as "not-provided, protective".
- NOT CLOSED

### PR-121-123-09: At 390 every info card opened stays on screen and the page never scrolls sideways
- Kind: screen
- Verdict: pass
- Card: 123
- What: at 390x844, `scrollWidth - innerWidth` was 0 with each card open, and each card box lay inside 16 to 374 px. Trust signals "i" under the answer: x 16, width 358, overflow 0 (query 5 Researcher, and the same box on queries 119 and 23). Persona caption "i" on the run screen (About Ochoa): x 16, width 358, overflow 0. Answer modes "i" on the landing screen: x 16, width 358, overflow 0. The header persona chip is hidden below 900 px, so at 390 the persona card is only reachable on the run screen, which is where it was opened.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_390_info_about_trust_signals.png`, `q5_researcher_390_run_info_persona.png`, `q5_researcher_390_landing_info_about_answer_modes.png`, `q5_researcher_log.json`.
- Why a person would care: on a phone the explanation of how sources are counted opens fully readable, with no sideways drag.
- NOT CLOSED

### PR-121-123-10: At 1280 the info cards still hang from their icon, unchanged
- Kind: screen
- Verdict: pass
- Card: 123
- What: at 1280 the Trust signals card is 280 px wide at x 341, directly under its "i" beside "High-risk claim"; the header persona card is 280 px at x 907. Overflow 0. No transform is applied above 720 px per the diff, and the screenshot shows the card where it sat before.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_1280_info_about_trust_signals.png`, `q5_researcher_1280_info_about_ochoa.png`.
- Why a person would care: the desktop look did not move.
- NOT CLOSED

### PR-121-123-11: The Trust signals card text reads "A Based on line names the databases"
- Kind: screen
- Verdict: needs your eye
- Card: earlier (copy, not touched by card 123)
- What: the card says "Confirmed means two or more independent databases agree on the same high-stakes fact. A Based on line names the databases the cited pages come from". The stray "A" before the quoted phrase reads as a typo because "Based on" is not in quotes.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_390_info_about_trust_signals.png`.
- Why a person would care: the one card that explains trust reads like a typing slip.
- NOT CLOSED

### PR-121-123-12: Query 5 Researcher meets the "What you should see" lines the run reached
- Kind: answer
- Verdict: pass
- Card: earlier
- What: first sentence answers: "BRCA1 is associated with four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." One trust line: "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared" with "High-risk claim" in red; status reads "Answered"; "21 sources cited from 2 layers". On the phone the tables are stacked rows, name with citation number first, identifier underneath; overflow 0 at 390 and 1280.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_answer.txt`, `q5_researcher_390_full.png`, `q5_researcher_1280_full.png`.
- Why a person would care: the answer names the four diseases first and says how far to trust it.
- NOT CLOSED

### PR-121-123-13: Query 5 Researcher carries a sentence fragment and states the disease count twice
- Kind: answer
- Verdict: needs your eye
- Card: earlier
- What: "The associated diseases familial cancer of breast and familial breast-ovarian cancer susceptibility 1." has no verb. The opening sentence is followed at once by "Found 4 disease records for BRCA1: Familial cancer of breast, ..." which repeats the same four names. The citation range shows as "1", a dash, "4" in the text layer (the document expects "1 to 13" style); on screen it is a raised range.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_answer.txt`, `q5_researcher_1280_full.png`.
- Why a person would care: a broken sentence and a repeated list make a careful answer look sloppy.
- NOT CLOSED

### PR-121-123-14: Query 5 Plain language keeps every info card on screen at 390 and reads differently from Researcher
- Kind: screen
- Verdict: pass
- Card: 123 (cards) and earlier (answer)
- What: at 390 the Trust signals card (x 16, width 358), the run screen persona card (About Florey, x 16, width 358) and the Answer modes card (x 16, width 358) all measured overflow 0; at 1280 the Trust signals card sits at x 341, width 280, overflow 0. The answer opens "Changes in this gene are responsible for about 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers." and lists sources in a paged list ("Showing 1 [dash] 10 of 21"), where Researcher shows typed tables; the two modes read differently.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_plain_390_info_about_trust_signals.png`, `q5_plain_390_run_info_persona.png`, `q5_plain_390_landing_info_about_answer_modes.png`, `q5_plain_1280_info_about_trust_signals.png`, `q5_plain_answer.txt`, `q5_plain_log.json`.
- Why a person would care: a phone reader in Plain language gets the same on-screen card as a researcher.
- NOT CLOSED

### PR-121-123-15: Query 5 Plain language never names the four diseases in its prose
- Kind: answer
- Verdict: needs your eye
- Card: earlier
- What: the prose says "I found 4 conditions related to BRCA1." and never names them; the names appear only in the "Where this answer comes from" list. The first sentence is a statistic about inherited breast cancer, not the list asked for.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q5_plain_answer.txt`, `q5_plain_390_full.png`.
- Why a person would care: a student asking "which diseases" must read a source list to find them.
- NOT CLOSED

### PR-121-123-16: Full-page screenshots show the fixed footer band across the middle of the answer
- Kind: screen
- Verdict: needs your eye
- Card: earlier, likely a capture artifact
- What: in every full-page capture the "NCBI Agentic Search" footer band is drawn across the content (for example over the rs6025 row at 390), and at 390 the app bar sits partway down when the page was scrolled. This is how a full-page capture draws fixed elements; in the viewport-sized captures the footer sits at the screen bottom and covers nothing that cannot be scrolled past. I did not confirm on a real phone.
- Evidence: `testing/Developer/reports/2026-10-29_product_check_121_123/q119_researcher_390_full.png`, `q5_plain_390_full.png`, against `q5_researcher_390_info_about_trust_signals.png`.
- Why a person would care: only if a real phone shows the band over text; read these full-page shots with that in mind.
- NOT CLOSED

## Summary

| Card | Verdict | At 1280 | At 390 |
|---|---|---|---|
| 121, heading names "record" once | pass | "Variant records found" (queries 119, 23 Researcher) | same, stacked rows, overflow 0 |
| 123, info card stays on screen | pass | cards unchanged, hang from the icon | overflow 0 with every card open, every card inside 16 to 374 px |

Answer times, from clicking search to the answer, with the app's own figure in brackets:

| Question | Mode | Seconds |
|---|---|---|
| 119, What are rs334 and rs6025? | Researcher | 10.4 (9.8) |
| 23, rs334 and its condition | Researcher | 14.9 (14.1) |
| 23, rs334 and its condition | Plain language | 7.5 (6.9) |
| 5, diseases with BRCA1 | Researcher | 15.2 (14.4) |
| 5, diseases with BRCA1 | Plain language | 10.7 (9.8) |

All five under 20 seconds and none over 25. One run per question per mode; no second ask was spent.

What the owner should look at first:

1. Fails, all from earlier work: PR-121-123-02 (query 119's count line names c.20A>T, not rs334 [1]), PR-121-123-05 and PR-121-123-08 (query 23 never names sickle cell or any condition, in either mode).
2. Needs your eye: PR-121-123-03 and PR-121-123-06 (markers 3, 4 and 2 beyond the stated source count), PR-121-123-11 (stray "A" in the Trust signals card), PR-121-123-13, PR-121-123-15, PR-121-123-16.

Overflow at 390: none. Every screen and every open card measured 0.

What was not captured, and why:

- No golden run, by the brief.
- No side-by-side with the design prototype: the changes are a heading string and the info card's position; I judged the card against the brief's measurable rule (inside 0 to 390, overflow 0), not against the prototype.
- The header persona chip is hidden below 900 px, so at 390 its card was opened from the run screen's persona caption instead.
- Query 5 lines not reached: hovering or tabbing to a citation number, Escape, "Show work", and the EGFR trials question.
- Citation markers 3 and 4 on query 119 and marker 2 on query 23 were not opened, so where they point is unknown.

Which verdicts rest on what: every verdict above rests on a screenshot or saved answer text I read myself, plus the measured numbers in each `_log.json`. None rests only on a summary.
