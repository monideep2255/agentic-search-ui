# Product check on develop: answer cards 131 (part 1) and 128

Pre-screen before the owner's retest, on 2026-10-22. It files findings and closes nothing. The owner's verdict closes.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Per query results](#per-query-results)
- [Summary](#summary)

## Target

- Web: https://search-agent-web-develop-2aeb.up.railway.app
- API /health, read before the first capture: `{"status":"ok","app_env":"develop"}`
- Deployed commit named in the brief: bae47b6e
- Guest sessions only, no sign-in, no accounts created. Every run is a fresh browser context loaded at the width named in its file name; a file ending `_390resized` is the same page resized after the answer landed.
- Times are on my clock from the Search click: first records is the first moment the records list or table is on screen, done is when the answer meta line appears.

## Findings

### PR-answers-01: The Researcher table heading still reads "Variant record records found"
- Kind: answer
- Verdict: fail
- What: for "What are rs334 and rs6025?" in Researcher, the heading above the table reads "VARIANT RECORD RECORDS FOUND". The brief says the answer must never read "variant record records". The count line itself is fixed ("Found 2 variant records for rs334 and rs6025").
- Evidence: `c131_rs334_rs6025_researcher_1280.png`, text in `c131_rs334_rs6025_researcher_1280.txt`: "VARIANT RECORD RECORDS FOUND".
- Why a person would care: "It says record records. Nobody proofread this."
- NOT CLOSED

### PR-answers-02: The variant count line puts both citations at the end instead of one per variant
- Kind: answer
- Verdict: needs your eye
- What: the count line reads "Found 2 variant records for rs334 and rs6025: rs334 and rs6025." with both chips, 1 and 2, after the full stop. The brief's expected form is "rs334 [1] and rs6025 [2]". In the same line the first "rs334" is bold and the others are not.
- Evidence: `c131_rs334_rs6025_researcher_1280.png`, "Found 2 variant records for rs334 and rs6025: rs334 and rs6025.1, 2".
- Why a person would care: "Which link is for which variant? And why is the name said twice in one sentence?"
- NOT CLOSED

### PR-answers-03: The Researcher papers table heading still reads "PubMed records found"
- Kind: answer
- Verdict: fail
- What: for query 108 (recent papers on BRCA1, last 10 years) in Researcher the count line is fixed ("Found 5 papers for BRCA1.", five papers listed, counts equal), but the table heading under it reads "PUBMED RECORDS FOUND". The brief says the answer must never read "pubmed records". Same at both widths.
- Evidence: `c131_q108_brca1_researcher_1280.png` and `c131_q108_brca1_researcher_390.txt`: "PUBMED RECORDS FOUND".
- Why a person would care: "The first line says papers, the heading underneath says PubMed records. Which is it?"
- NOT CLOSED

### PR-answers-04: Query 108 took 24 s after the window was picked at 1280, over the 20 s promise
- Kind: answer
- Verdict: fail
- What: at 1280, the answer landed 24.4 s after "from the last 10 years" was clicked (28.3 s from the first Search click; meta line 24.1 s). First records appeared 17.6 s after the click. The fresh 390 run of the same question landed in 17.5 s after the click. One run each, so this is a single observation, not a rate.
- Evidence: `c131_q108_brca1_researcher_1280.json` (after_pick done 24.39), meta "Answered 24.1s · 13 tool calls · 17 sources cited from 2 layers".
- Why a person would care: "I already told it how far back; then it still made me wait half a minute."
- NOT CLOSED

### PR-answers-05: Summary sentences cite chips 19, 20 and 21 when the answer says it cites 17 sources
- Kind: answer
- Verdict: needs your eye
- What: in query 108 the summary sentences carry chips 19 (1280: "HSP90 is estimated to buffer 18% of known human BRCA1-BRCT missense mutations.") and 19, 20, 21 (390), while the meta line and Sources header say 17 sources. Not checked whether those chips open a source; likely the numbering skips the listed rows, but a person cannot tell.
- Evidence: `c131_q108_brca1_researcher_1280.png`, `c131_q108_brca1_researcher_390.txt`.
- Why a person would care: "It says 17 sources, so where is source 21?"
- NOT CLOSED

### PR-answers-06: CFTR papers count line says 54 papers while the answer lists 59 papers in two tables
- Kind: answer
- Verdict: fail
- What: query 117 in Researcher opens "Found 54 papers for CFTR, of 1962 available." The "ARTICLE RECORDS FOUND" table pages through 54, and a second table, "PUBMED RECORDS FOUND", lists 5 more papers (PMID:28340353, 36207272, 36220763, 36264792, 38388235). The count does not equal the papers listed. The same answer's note says "only 117 of the 1962 records that matched this question in the graph were retrieved", so "1962 available" counts records, not papers.
- Evidence: `c128_q117_cftr_researcher_run1_1280.txt` and `.png`; run 2 at 390 is the same (`c128_q117_cftr_researcher_run2_390.txt`).
- Why a person would care: "It says 54 papers, then shows me a second list of papers, and 1962 of what?"
- NOT CLOSED

### PR-answers-07: The CFTR answer shows papers under two headings, "Article records" and "PubMed records"
- Kind: answer
- Verdict: fail
- What: the Researcher CFTR answer has both "ARTICLE RECORDS FOUND" and "PUBMED RECORDS FOUND", both tables of papers with PMIDs. The brief says the answer must never read "pubmed records".
- Evidence: `c128_q117_cftr_researcher_run1_1280.txt`.
- Why a person would care: "Are articles and PubMed records different things? They both look like papers."
- NOT CLOSED

### PR-answers-08: The CFTR written summary is one sentence that restates the first paper's title
- Kind: answer
- Verdict: needs your eye
- What: run 1 and run 2 each showed a written summary (so card 128's note was not needed). Run 1's whole summary is "The Hdj-2/Hsc70 chaperone pair facilitates early steps in CFTR biogenesis, the Hsc70 co-chaperone CHIP targets immature CFTR for proteasomal degradation." Its first clause is paper 1's title, joined by a comma splice. Rubric line 1 (answers "what do they cover?"): fail; line 2 (learn something a chatbot would not say): fail, one paper of 54 is summarised.
- Evidence: `c128_q117_cftr_researcher_run1_1280.png`.
- Why a person would care: "I asked what 54 papers cover and got one paper's title back."
- NOT CLOSED

### PR-answers-09: CFTR run 3 showed the records with no written summary and no note saying why
- Kind: answer
- Verdict: fail
- What: the third Researcher run of query 117 shows "Found 54 papers for CFTR, of 1962 available." then goes straight to the tables. There is no written summary, and the Notes block holds only "Note: this answer was truncated because only 117 of the 1962 records that matched this question in the graph were retrieved". Neither card 128 note appears ("no written summary could be checked against the records" or "no written summary is shown, because the sentences written only repeated the records listed above"). The brief names exactly this as a fail. Runs 1 and 2 each had a summary, so 1 of 3 runs hit the gap.
- Evidence: `c128_q117_cftr_researcher_run3_1280.png` (read myself), `c128_q117_cftr_researcher_run3_1280.txt` (the only "Note" line is the truncation note), `c128_q117_cftr_researcher_run3_390resized.png`.
- Why a person would care: "I asked what the papers cover and got only a list. Did it fail, or is that all it does?"
- NOT CLOSED

### PR-answers-10: CFTR run 3 took 22.9 s, over the 20 s promise
- Kind: answer
- Verdict: fail
- What: first records at 10.8 s, done at 22.9 s (meta line 22.1 s), for an answer that ended up showing no summary at all. Runs 1 and 2 were done in 16.1 s and 15.1 s.
- Evidence: `c128_q117_cftr_researcher_run3_1280.json`.
- Why a person would care: "It thought for twelve more seconds after the list appeared, then showed me nothing extra."
- NOT CLOSED

### PR-answers-11: The control question in Plain language answered once with no summary and no note
- Kind: answer
- Verdict: needs your eye
- What: query 1 in Plain language at 1280 showed only "I found 4 conditions related to BRCA1." then the source list; no written summary and no note. The fresh 390 run of the same question opened "BRCA1 is associated with four diseases: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." followed by a three-sentence plain summary. Query 1's entry allows either opening, so the opening passes; the missing summary with no note is the card 128 gap, seen here in Plain language. Whether card 128 was meant to cover Plain language is for the owner.
- Evidence: `control_q1_brca1_plain_1280.png` and `.txt`; `control_q1_brca1_plain_390.txt`.
- Why a person would care: "Same question, one time I get an explanation, the next time just a list with nothing saying why."
- NOT CLOSED

### PR-answers-12: Citation chips number past the source count in Plain language and Researcher summaries
- Kind: answer
- Verdict: needs your eye
- What: "What are rs334 and rs6025?" in Plain language shows "I found 2 genetic variants related to rs334 and rs6025." with chips 3 and 4, and "One variant is known in the literature as c.20A>T, and another is known as c.1691G>A." with chips 3 and 4, while the list below holds chips 1 and 2 and the Sources header says 2 ("Based on 2 sources cited, all from dbSNP"; the meta line says "from 2 layers"). The same pattern is in PR-answers-05 (chips 19 to 21 against 17 sources). Chip targets not opened.
- Evidence: `c131_rs334_rs6025_plain_390resized.png`, `c131_rs334_rs6025_plain_1280.txt`.
- Why a person would care: "Two sources, but the sentence cites 3 and 4. Where are they?"
- NOT CLOSED

### PR-answers-13: The "no written summary" note says the records are listed below, but it sits under them
- Kind: answer
- Verdict: needs your eye
- What: in Researcher for rs334 and rs6025 the note reads "Note: no written summary could be checked against the records, so the records found are listed below with their sources", placed after the table. Both widths.
- Evidence: `c131_rs334_rs6025_researcher_390.png`, `c131_rs334_rs6025_researcher_1280.png`.
- Why a person would care: "Below where? The list is above this."
- NOT CLOSED

## Per query results

Times from the Search click on my clock: first records, then done. For query 108 the times run from the "from the last 10 years" click (the ask-back itself came in 1.6 to 3.4 s). Overflow at 390 was 0 on every deployed capture, fresh or resized.

| Run | Width | First records | Done | Gate entry | Brief check | Screenshot |
|---|---|---|---|---|---|---|
| 131: query 108, Researcher | 1280 fresh | 17.6 s | 24.4 s | pass | count line pass, heading fail, time fail | `c131_q108_brca1_researcher_1280.png` |
| 131: query 108, Researcher | 390 fresh | 8.9 s | 17.5 s | pass | count line pass, heading fail | `c131_q108_brca1_researcher_390.png` |
| 131: query 108, Plain language | 1280, then resized | 11.6 s | 22.8 s | pass | count line names no records, pass; time over 20 s | `c131_q108_brca1_plain_1280.png`, `_390resized.png` |
| 131: rs334 and rs6025, Researcher | 1280 fresh | 10.8 s | 12.8 s | not in the gate document | count line pass (2 equals 2), citation form needs eye, heading fail | `c131_rs334_rs6025_researcher_1280.png` |
| 131: rs334 and rs6025, Researcher | 390 fresh | 7.5 s | 8.8 s | not in the gate document | same as 1280 | `c131_rs334_rs6025_researcher_390.png` |
| 131: rs334 and rs6025, Plain language | 1280, then resized | 10.7 s | 12.2 s | not in the gate document | count line names no records, pass; chips 3 and 4 against 2 sources | `c131_rs334_rs6025_plain_1280.png`, `_390resized.png` |
| 128: query 117, Researcher run 1 | 1280 fresh | 13.3 s | 16.1 s | pass | summary shown (one sentence), no note needed | `c128_q117_cftr_researcher_run1_1280.png` |
| 128: query 117, Researcher run 2 | 390 fresh | 10.3 s | 15.1 s | pass | full summary shown, no note needed | `c128_q117_cftr_researcher_run2_390.png` |
| 128: query 117, Researcher run 3 | 1280, then resized | 10.8 s | 22.9 s | pass | fail: no summary and no note; time fail | `c128_q117_cftr_researcher_run3_1280.png`, `_390resized.png` |
| Control: query 1, Plain language | 1280, then resized | 14.1 s | 17.9 s | pass | no summary and no note, needs eye | `control_q1_brca1_plain_1280.png`, `_390resized.png` |
| Control: query 1, Plain language | 390 fresh | 4.4 s | 6.7 s | pass | answering sentence plus summary | `control_q1_brca1_plain_390.png` |

Gate entries, what each rests on:

- Query 108: the heading reads "Recent papers on BRCA1 from the last 10 years?" and the five papers listed are PMIDs from 2020 onward. No restart was done, so this checks only the "without a restart, the same click still limits to the last 10 years and says so" line.
- Query 117 (Researcher only, as briefed): every paper is listed by its PubMed title with its PMID, no bare "Article record PMID" or "Published paper" row and no PMID listed twice, in all three runs (checked in the saved text). Links not clicked.
- Query 1: the opening at 390 answers the question then gives the "found" line, which the entry allows; the 1280 run opens on the "found" line, also allowed. Disease names read naturally ("Familial breast-ovarian cancer susceptibility 1"). Links not clicked.

## Summary

- Golden result: not run. The brief named no accounts file and no floor, and asked for a product check of named questions only. Answered well of the fixed ten: not read. Both cards change the answer path, so the golden run is still owed before the owner accepts them.
- What to look at first, fails: PR-answers-09 (CFTR run 3, list with no summary and no note), PR-answers-01 and PR-answers-03 and PR-answers-07 (headings still read "Variant record records" and "PubMed records"), PR-answers-06 (54 papers counted, 59 listed), PR-answers-04 and PR-answers-10 (24.4 s and 22.9 s, over 20 s). Query 108 in Plain language also took 22.8 s.
- Needs your eye: PR-answers-02 (citations bunched at the end of the variant line), PR-answers-05 and PR-answers-12 (chip numbers past the source count), PR-answers-08 (CFTR run 1 summary repeats one title), PR-answers-11 (control once had no summary and no note), PR-answers-13 ("listed below" in a note that sits below the list).
- Overflow at 390: 0 on every deployed capture. The prototype itself measured 322 px at 390 on its finished answer screen (`prototype_answer_390.png`); that is the design file, not the app.
- Design: the answer screen has a design (`prototype_answer_1280.png`); the deployed layout keeps its order (question, meta line, answer, sources, follow-up) at both widths. The prototype has no state for a count line over record tables, or for a "no written summary" note, so those were judged on wording, not against a design.
- Not captured: the golden run (above); the "How far back" restart path of query 108; chip and link targets were not opened; Plain language for query 117; each question ran once per width except query 117 (three runs), so the times are single observations.
- Read myself: the screenshots `c131_rs334_rs6025_researcher_1280.png`, `c131_rs334_rs6025_researcher_390.png`, `c131_rs334_rs6025_plain_390resized.png`, `c131_q108_brca1_researcher_1280.png`, `c131_q108_brca1_researcher_390_fold.png`, `c128_q117_cftr_researcher_run3_1280.png`, `c128_q117_cftr_researcher_run2_390_fold.png`, `prototype_answer_1280.png`, `prototype_answer_390.png`. Every other verdict rests on the saved page text (`.txt`) and timing (`.json`) from the same runs, which I read, not on a summary.
