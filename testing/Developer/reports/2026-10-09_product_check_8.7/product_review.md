# Phase 8.7 product check: records sooner, summary above, Stop after records

The product reviewer's pre-screen of build phase 8.7 (pull request #218, merge b01dee92) on deployed develop. It files findings and closes nothing; the owner's retest decides. No golden run, at the owner's choice.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result per step](#result-per-step)
- [Time to answer](#time-to-answer)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health`, read 2026-10-09 before the first capture: `{"status":"ok","app_env":"develop"}`.
- The lead read both Railway services SUCCESS at b01dee92 at 04:46 UTC; not re-read here.
- Web bundle served by the develop web app: `index-BUMzWQlH.js` (from the page's script tag).

## Findings

### PR-87-01: The record table moves 149 pixels down when the summary lands
- Kind: screen
- Verdict: needs your eye
- What: query 1 in Researcher at 1280, page not scrolled. With the records on screen and the progress panel above them, the first record row ("Familial cancer of breast") sat 540 px from the top of the window. When the summary landed it sat at 689 px: the progress panel went away, the summary and its "Disease associations and inherited risk" section arrived above, and the table moved 149 px down. The code holds the records still only when the reader has already scrolled into them; with their top in view it lets them move by design.
- Evidence: `q1_log.json`, steps "first record row on screen" (`"top":540`, `scrollY 0`) and "first summary sentence on screen" (`"top":689`, `scrollY 0`); screenshots `q1_1280_1_records.png` and `q1_1280_2_summary.png`.
- Why a person would care: "I started reading the disease table and it slid down a hand's width when the text arrived." Whether a 149 px move with the top in view counts as the jump the change promised to remove is yours to say.
- NOT CLOSED

### PR-87-02: Records shown before the summary are drawn faint grey
- Kind: screen
- Verdict: needs your eye
- What: at 10 s, with Stop live and "Nirenberg is writing the answer", every record table on the page renders in very light grey text, headings and identifiers barely legible, under a "writing ..." line. After the summary lands the same tables are full black.
- Evidence: `q1_1280_1_records.png` against `q1_1280_2_summary.png`.
- Why a person would care: "The records showed up, but they looked disabled, so I waited instead of reading them." If the faint state is intentional it has no design: the code itself names records-before-summary as a design gap (no state in `docs/build/design/README.md`'s coverage table).
- NOT CLOSED

### PR-87-03: The first two sentences name the same four diseases twice
- Kind: answer
- Verdict: needs your eye
- What: the first sentence answers the question, and the count line straight after it repeats the same list.
- Evidence: `q1_log.json`, "final summary all": "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." then "Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S."; screenshot `q1_1280_2_summary.png`.
- Why a person would care: "It told me the four diseases, then told me the same four again in the next breath."
- NOT CLOSED

### PR-87-04: Marfan features question opens on the count line though a checked features sentence exists
- Kind: answer
- Verdict: fail
- What: query 66 in Plain language at 390. The first sentence lists what was found rather than answering; the sentence that does answer is the fourth. This is the same question the phase's own live check reported as opening on the features sentence in both modes.
- Evidence: `q66_log.json`, "final summary all": first sentence "I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome."; fourth sentence "MedGen lists these clinical features: Aortic regurgitation, Arachnodactyly and Astigmatism, Ectopia lentis, Esotropia, Exotropia and Pes planus, Glaucoma, Congestive heart failure, Hypertropia and Micrognathia."; screenshot `q66_390_3_final.png`.
- Why a person would care: "I asked what the features of Marfan syndrome are and it opened by counting papers and trials." Rubric line 1 fails. One run, so it may vary between runs; A07 (first-sentence pick timing) may be related, not checked.
- NOT CLOSED

### PR-87-05: A garbled sentence "Marfan syndrome and Marfan syndrome." ends the summary
- Kind: answer
- Verdict: fail
- What: the last summary sentence is a name repeated, carrying citations 79 and 81. The features sentence before it also reads oddly, with "and" inside the list twice ("Arachnodactyly and Astigmatism", "Exotropia and Pes planus").
- Evidence: `q66_log.json`, "final summary all": "Marfan syndrome and Marfan syndrome.⁠79, 81"; screenshot `q66_390_3_final.png`.
- Why a person would care: "The answer ends on a sentence that says nothing, which makes me doubt the rest." The test queries document lists a garbled sentence as still worth reporting.
- NOT CLOSED

### PR-87-06: On a phone the records move about 313 pixels down when the summary lands
- Kind: screen
- Verdict: needs your eye
- What: query 66 at 390. The first record row ("Marfan syndrome.") sat 610 px from the window's top at 12.1 s; when the summary arrived at 16.2 s it sat at 923 px, with the page scrolled 107 px (the script did not scroll; this is the browser's own adjustment). Same mechanism as PR-87-01, larger on a narrow screen.
- Evidence: `q66_log.json`, steps "first record row on screen" (`"top":610`) and "first summary sentence on screen" (`"top":923`, `scrollY 107`); screenshots `q66_390_1_records.png`, `q66_390_2_summary.png`.
- Why a person would care: "On my phone the list I was looking at slid most of a screen down."
- NOT CLOSED

### PR-87-07: A record shows "Source pending" while the summary is being written
- Kind: screen
- Verdict: needs your eye
- What: at the moment the records first appeared on the phone, the first row's text read "Marfan syndrome.·Source pending."; after the summary landed the same row read "Marfan syndrome." with citation 1.
- Evidence: `q66_log.json`, step "first record row on screen": `"text":"Marfan syndrome.·Source pending."`, then step "first summary sentence on screen": `"text":"Marfan syndrome.⁠1"`. Not legible in `q66_390_1_records.png`, which caught the records still fading in.
- Why a person would care: "The records were supposed to come with their citations; the first one said its source was pending." The brief promises records with their citations.
- NOT CLOSED

### PR-87-02 addendum: the faint records are at least partly a fade-in
- At the first record on the phone the records' combined opacity measured 0 (`q66_log.json`, `"fade":{"opacity":0}`), and the whole card, question and Stop included, looks washed out in `q66_390_1_records.png`. So PR-87-02's screenshot may have caught a fade-in rather than a lasting grey state; how long it lasts is measured in step 3 below.

### PR-87-02 second addendum: the fade lasts about half a second
- Query 72 at 1280, polled every 100 ms: the records' combined opacity read 0.01 at 12.75 s, 0.81 at 13.02 s, 0.96 at 13.12 s and 1 from 13.23 s (`q72_log.json`, `timeline`, field `fo`). So the faint tables in `q1_1280_1_records.png` are the fade-in caught mid-way, not a lasting grey state. Left for your eye only in case the fade itself is unwanted; the reviewer reads PR-87-02 as most likely a false alarm.

### PR-87-08: GERD records move 61 pixels down when the summary lands, with the page scrolled
- Kind: screen
- Verdict: needs your eye
- What: query 72 in Plain language at 1280. After the records appeared the script scrolled the page as far as it would go (172 px) to sit inside the records; the first row ("Famotidine in Subjects With Non-erosive Gastroesophageal Reflux Disease") was then at 327 to 329 px, still below the app bar, so the page could not be scrolled far enough to test the hold-in-place behaviour. When the summary landed at 20.31 s the row moved to 390 px, page scroll unchanged at 172.
- Evidence: `q72_log.json`, steps "scrolled into records" (`"scrollY":172,"listingFirstTop":329`) and "first summary sentence on screen" (`"top":390`, `scrollY 172`); screenshots `q72_1280_1_records.png`, `q72_1280_2_summary.png`.
- Why a person would care: "The trial I was reading nudged down when the text came in." The case the code protects, a reader scrolled past the top of the records, was not reached on any question tonight.
- NOT CLOSED

### PR-87-09: Three rows under "Where this answer comes from" read the same title
- Kind: answer
- Verdict: needs your eye
- What: the Plain language GERD answer lists the 5 trials, then literature rows 6, 9 and 10 each read "Gastroesophageal Reflux Disease." with no way to tell them apart in the list.
- Evidence: screenshot `q72_1280_3_final.png`; `q72_log.json`, "final claims text": "Gastroesophageal Reflux Disease.\t⁠6 ... Gastroesophageal Reflux Disease.\t⁠9\nGastroesophageal Reflux Disease.\t⁠10".
- Why a person would care: "Three sources with the same name: are they the same thing listed three times?" Probably three different records with one title; not opened to check, and not checked whether this predates 8.7.
- NOT CLOSED

### PR-87-10: Records kept under "Search stopped" are drawn faint grey, 25 seconds after the stop
- Kind: screen
- Verdict: fail
- What: query 1 in Researcher at 1280, Stop clicked 9 ms after the first record row appeared (18.69 s). "Stopping…" showed, then "Search stopped" with "No summary was written. The records found before you stopped are below." at 19.0 s, with all 21 records kept and no summary or answer line after it for the next 25 s. But in the screenshot taken 25 s after the stop, every record row (disease names, identifiers, citation numbers) is very light grey on white while the section headings are dark. The script's measure of the first row's opacity read 1 from 19.11 s on, so the faintness is not explained by that measure; a probe follows. This retracts PR-87-02's "most likely a false alarm": the same faint rows show in `q1_1280_1_records.png`.
- Evidence: screenshot `stop_1280_3_final.png`; `stop_log.json`, steps "stop pressed", "search stopped shown" and timeline field `fo`.
- Why a person would care: "I stopped it to read the records, and they are so pale I can hardly read them."
- NOT CLOSED

### PR-87-10 addendum: the probe found the kept records dark; the faint shot is most likely a capture artifact
- A third Stop run (the sixth and last question) pressed Stop 14 ms after the first record. "Search stopped" with the records-kept sentence showed 0.32 s after the press, 21 records kept, nothing new in the next 8 s. Eight seconds later the first record cell's colour read rgb(27, 27, 27), every ancestor's opacity 1, no filter, all 27 rise animations "finished", and the cell was the topmost element at its point.
- Evidence: `stopprobe_log.json`, step "deep style probe on first kept record"; screenshots `stopprobe_1280_viewport.png` and `stopprobe_1280_3_final.png`, both with the records in full black.
- So the reviewer moves PR-87-10 from fail to needs your eye: two full-page shots (`stop_1280_3_final.png`, `q1_1280_1_records.png`) drew the rows faint and one did not, and the cause was not found. Worth one look by hand after a Stop.

### PR-87-11: Stopped searches sit in history as "21 sources cited", and opening one ran the search again
- Kind: screen
- Verdict: fail
- What: after the step-1 answer, one answered Stop attempt and two stopped searches, the rail listed four identical rows "Which diseases are associated with BRCA1? 21 sources cited · Oct 9". Nothing tells a stopped search from an answered one. The script clicked the top row, the most recent, which was a stopped search: no saved answer opened, and 22.6 s later the screen showed a new full answer, "? Answered 16.9s · 13 tool calls · 21 sources cited from 2 layers", with a summary none of the earlier runs had ("Gene function context"). Read as a fresh run: the question was asked again with no prompt, and this spent a seventh question, one past the brief's cap of six.
- Evidence: `reopen_log.json`, steps "rail BRCA1 items" (four rows "21 sources cited · Oct 9" plus one "Oct 8") and "saved answer" (`"screen":false`, `"ms":22556`); screenshots `reopen_1280_0_rail.png`, `reopen_1280_1_saved.png`.
- Why a person would care: "I stopped that search, but history lists it exactly like an answered one, and tapping it quietly ran the whole search again." Card 59's product check filed the re-run on open as PR-04; what is new is that a stopped search now shows a source count, so the reader cannot pick out the answered one.
- NOT CLOSED

### PR-87-12: The saved BRCA1 answer's OMIM source is shown unlinked
- Kind: answer
- Verdict: needs your eye
- What: reopening the step-1 answer from "Your searches", source 8 reads "8. omim LIVE" and "Not linked: this URL is not on a recognised NCBI host." Every other source carries an NCBI or ClinicalTrials.gov link. Not checked whether this predates 8.7.
- Evidence: screenshot `reopen2_1280_1_saved.png`, Sources list, item 8.
- Why a person would care: "One of the citations has no link, so I cannot check that record."
- NOT CLOSED

## Result per step

| Step | Result | Rests on |
|---|---|---|
| 1. Query 1, Researcher, 1280 | Pass with notes. First record row at 10.10 s, first summary sentence at 14.69 s (answer line "Answered 14.4s"). The records moved 149 px down when the summary landed (PR-87-01). First sentence answers: "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S.", then repeats as the count line (PR-87-03) | Screenshots `q1_1280_1_records.png`, `q1_1280_2_summary.png` read; `q1_log.json` |
| 2. Query 66, Plain language, 390 | Fail. First sentence is the count line, "I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome.", though the features sentence exists (PR-87-04); garbled closing sentence (PR-87-05). Overflow 0 at every poll from asking to landing. Records 12.11 s, summary 16.18 s | Screenshot `q66_390_3_final.png` read; `q66_log.json` |
| 3. Query 72, Plain language, 1280 | Pass. Opens "I found 5 clinical trials related to GERD." with the trial titles under "Where this answer comes from", as query 72 expects. Records 12.75 s, summary 20.31 s. Notes PR-87-08, PR-87-09 | Screenshot `q72_1280_3_final.png` read; `q72_log.json` |
| 4. Stop after records | Pass. Stop pressed 9 ms after the first record (18.69 s): "Stopping…", then at 19.00 s "Search stopped" and "No summary was written. The records found before you stopped are below.", 21 records kept, no summary and no answer line in the next 25 s. Repeated on the probe run (pressed 14 ms after, stopped 0.32 s later, 21 kept). Possible faint rendering of kept records, PR-87-10 | Screenshots `stop_1280_3_final.png`, `stopprobe_1280_viewport.png` read; `stop_log.json`, `stopprobe_log.json` |
| 5. Reopen query 1 from "Your searches" | Pass for the answered row: the saved step-1 answer opened in 2.5 s, "Saved answer · asked Oct 9", summary paragraph first, then "Disease associations and inherited risk", then the record tables. Fail for the history list itself: stopped rows look the same as answered ones, and opening one re-ran the search (PR-87-11) | Screenshots `reopen2_1280_1_saved.png`, `reopen_1280_1_saved.png` read; `reopen_log.json`, `reopen1_log.json`, `history_api_rows.json` |

Horizontal overflow at 390: 0 throughout query 66 (188 polls). Every 1280 run also measured 0.

History rows as the API stores them, newest first (`history_api_rows.json`): the accidental re-run `ask` with a saved answer; the two stopped searches `refuse`, `citation_count 21`, `has_saved_answer false`; the first Stop attempt and step 1, both `ask` with a saved answer. So a stopped search is not recorded as answered, but it now carries the 21 records' count, which is what the rail shows.

## Time to answer

Seconds from pressing Search, measured on screen by the capture script.

| Run | First record row | First summary sentence | Answer line |
|---|---|---|---|
| Query 1, Researcher, 1280 | 10.10 | 14.69 | Answered 14.4s |
| Query 66, Plain, 390 | 12.11 | 16.18 | Answered 15.9s |
| Query 72, Plain, 1280 | 12.75 | 20.31 | Answered 19.9s |
| Query 1, first Stop attempt (Stop not pressed, see below) | 11.88 | 16.16 | Answered 15.8s |
| Query 1, Stop run | 18.68 | stopped | none |
| Query 1, Stop probe run | 20.61 | stopped | none |

Answers that landed (four): median 16.17 s, p90 and worst 20.31 s (query 72). None over 25 s; query 72 is 0.31 s over the 20-second goal. In every answered run the summary arrived in one piece with the answer line, at the same poll, so the first summary sentence and the whole answer landed together. First records ranged from 10.10 to 20.61 s.

## What was not captured

- Questions spent: seven, one past the brief's cap of six. Query 1, query 66, query 72, three Stop runs on query 1, and the accidental re-run from history (PR-87-11). The first Stop attempt did not press Stop: Playwright's click waited on the button while the records were fading in and timed out after 2 s, so that run answered in full (`attempt1_stop_log.json`). The next two used a mouse click at the button's centre after checking the button was the topmost element there, which is what a person does.
- The literature search giving up at 6 seconds: none of these questions showed a "gave up" note, so it was not seen either way.
- A04 (citation chip under a summary sentence showing the checked words) and A07 (summary waiting on the first-sentence pick): not tested, as the brief says they are known.
- The hold-in-place case for a reader scrolled past the top of the records: on query 72 the page could not scroll far enough (PR-87-08).
- The prototype comparison at both widths, and Plain language against Researcher on the same question: not in this brief. The record-listing-before-summary state has no design in `docs/build/design/README.md`'s coverage table; the code names it as a design gap.
- No golden run, at the owner's choice.
- Screenshots are full page; the sticky footer bar draws across the middle of each full-page shot, an artifact of the capture, not a defect. `q66_390_debug_after_resize.png` and `probe_log.json` are from a no-question probe of the phone layout (the history drawer covers the search box after resizing; Escape closes it).

What rests on a screenshot or saved text read by the reviewer: every finding above names its file, and all of PR-87-01 to PR-87-12 were read directly, screenshots or captured page text. Nothing rests only on a summary.
