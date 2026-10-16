# Product review, 2026-10-15: cards 114, 35 and 111 on develop

Deployed commit f3950564. Reviewer: product reviewer agent, a pre-screen; nothing here closes a card.

- Health before the first capture: the API's /health returned `{"status":"ok","app_env":"develop"}` (search-agent-api-develop).
- Golden run: not run, by the product owner's standing rule that the test queries document is the gate. The golden floor is not applicable.
- Captures: `.claude/skills/verify/scripts/capture.mjs`, the lead's spec, two runs into `run1/` and `run2/` in this folder, 1280 and 390, each beside the prototype.

## Findings

### PR-1015-01: the follow-up field and its refusal have no design to judge against
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table lists "Follow-up field | NO | Shipped since build phase 4.8, never designed as its own card". The refusal of an off-topic follow-up appears under that field, so its position is judged only for overflow and breakage, never against an invented look. The prototype's first-question refusal (`prototype/app.html`, scopeRefusalHtml) is the nearest reference.
- Evidence: `<repo-root>/docs/build/design/README.md`, coverage table row "Follow-up field".
- Why a person would care: no one has decided what a refused follow-up should look like on a phone, so whatever ships is the design by default.
- NOT CLOSED

### PR-1015-02: an off-topic follow-up failed on our side instead of being refused, 1 of 4 tries
- Kind: answer
- Verdict: fail
- What: in run 2 at 1280, the follow-up "Which cell phone is it best to buy this year?" after the BRCA1 answer did not get the "Outside biomedical research" label. It showed an error instead, with no label, so the capture's wait for that label timed out at 60 s. The other three tries (run 1 at 1280 and 390, run 2 at 390) were refused correctly with 0 tool calls.
- Evidence: `run2/q111_offtopic_followup_1280.txt` and `run2/q111_offtopic_followup_1280.png`; `run2/results.json` "screen reached" fail, "locator.waitFor: Timeout 60000ms exceeded". Quoted: "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again." and "Not verified · the run did not finish".
- Why a person would care: someone who wanders off topic is told the app broke, not that the question is out of scope, and is invited to ask the same thing again. Card 35 adds a topic check beside the safety check for follow-ups; whether this failure is that new check timing out or failing is not visible from the screen and needs the API log for this request.
- NOT CLOSED

### PR-1015-03: the Marfan answer had written summary sentences in only 1 of 4 runs
- Kind: answer
- Verdict: fail
- What: card 114 restores the writer's summary sentences. BRCA1 had written sentences in 4 of 4 answers. The Marfan question (query 66) had them in 1 of 4: run 2 at 1280 adds "Marfan syndrome is a multisystem connective tissue disease with autosomal dominant inheritance." and two more sentences. The other three answers end at the built feature list and the count line, the same shape the card describes as the broken state.
- Evidence: `run1/q66_plain_1280.txt`, `run1/q66_plain_390.txt`, `run2/q66_plain_390.txt` each hold only "MedGen lists these clinical features: ..." and "I found 1 condition related to Marfan syndrome." (or "I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome."). With sentences: `run2/q66_plain_1280.txt`, `run2/q66_plain_1280.png`.
- Why a person would care: three times out of four, a student asking what Marfan syndrome looks like gets a list and a tally, nothing written. Whether the writer failed, was skipped or chose nothing is not visible on screen; the API log for these four requests says which.
- NOT CLOSED

### PR-1015-04: the Marfan answer opens on a record list, not on an answer
- Kind: answer
- Verdict: needs your eye
- What: rubric line 1. All four Marfan answers open "MedGen lists these clinical features: Aortic regurgitation, Arachnodactyly, Astigmatism, Ectopia lentis, Esotropia, Exotropia, Pes planus, Glaucoma, Congestive heart failure and Hypertropia." It names what a record holds rather than saying what the syndrome looks like, and puts three eye-alignment terms ahead of the hallmarks (tall stature, aortic root dilation are not in the first ten of 70). Rubric line 2: fail in the three answers without written sentences, since a general chatbot says more; pass in run 2 at 1280, which names FBN1 and the Ghent II nosology with citations.
- Evidence: `run1/q66_plain_1280.txt`, first sentence quoted above; `run2/q66_plain_1280.txt`, "It is mainly caused by FBN1 gene mutation and often has different clinical manifestations."
- Why a person would care: a clinician reads "Esotropia, Exotropia" before anything that defines Marfan syndrome.
- NOT CLOSED

### PR-1015-05: the count line says one condition while the sources list papers and trials
- Kind: answer
- Verdict: needs your eye
- What: in run 1 at 1280 and run 2 at 390 the Marfan answer says "I found 1 condition related to Marfan syndrome." while the same screen's "Where this answer comes from" list holds 13 sources, including "Comparison of Two Medications Aimed at Slowing Aortic Root Enlargement in Individuals With Marfan Syndrome" (a trial) and "[Latest advances in the diagnosis and treatment of Marfan syndrome]." (a paper). The other two runs counted "5 published papers, 1 condition, 1 literature index entry and 5 clinical trials" for the same question.
- Evidence: `run1/q66_plain_1280.txt`, `run2/q66_plain_390.txt`, against `run2/q66_plain_1280.txt`.
- Why a person would care: the summary and the list beneath it disagree about what was found, which reads as carelessness in a tool selling citations.
- NOT CLOSED

### PR-1015-06: citation numbers jump from 2 to 73 with 12 sources on screen
- Kind: answer
- Verdict: needs your eye
- What: the Marfan answer's source rows are numbered 1, 2, then 73 to 80, and the written sentences cite 83 and 84, while the meta line says "12 sources cited". The superscript reads "1 +11".
- Evidence: `run2/q66_plain_1280.png` (rows 1, 2, 73, 74 ... 80; sentences cite 83, 84); `run1/q66_plain_390_fold.png` ("Marfan syndrome.1", "Marfan syndrome2", "Marfan Syndrome73").
- Why a person would care: a reader looking for source 83 among 12 sources cannot find what the number means.
- NOT CLOSED

### PR-1015-07: three source rows read as the same title
- Kind: answer
- Verdict: needs your eye
- What: the first three Marfan source rows are "Marfan syndrome", "Marfan syndrome." and "Marfan syndrome" (or "Marfan Syndrome"), with nothing telling the reader which database each is from. Card 111 removed the summary sentence that repeated such a title; the list rows themselves still repeat. Not a regression of card 111; recorded so the owner sees it beside that card.
- Evidence: `run1/q66_plain_1280.txt`, "WHERE THIS ANSWER COMES FROM / Marfan syndrome 1 / Marfan syndrome. 2 / Marfan syndrome 3".
- Why a person would care: three identical lines look like a duplication bug.
- NOT CLOSED

### PR-1015-08: one BRCA1 answer opens without naming any disease
- Kind: answer
- Verdict: needs your eye
- What: rubric line 1. Three BRCA1 answers open "BRCA1 is associated with four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." (pass). Run 1 at 390 opens instead "When this gene is altered, it is responsible for about 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers." and names the four diseases only in the source list. In the three that pass, the next sentence "I found 4 conditions related to BRCA1." repeats the count just given.
- Evidence: `run1/brca1_plain_390.txt`, `run1/brca1_plain_390.png`; `run1/brca1_plain_1280.txt` for the repeat.
- Why a person would care: on a phone the reader asked which diseases and the summary never lists them.
- NOT CLOSED

### PR-1015-09: an error on a follow-up still offers BRCA1 follow-up chips and the helpful buttons
- Kind: screen
- Verdict: needs your eye
- What: in the failed follow-up (PR-1015-02) the screen shows "What variants cause it?", "Which trials are recruiting?", "What does the literature add?" and "Was this answer helpful?" under an error box, whereas the correct refusals show "Ask another question" without chips. The follow-up field has no design (PR-1015-01).
- Evidence: `run2/q111_offtopic_followup_1280.png` against `run2/q111_offtopic_followup_390.png`.
- Why a person would care: they asked about phones, got an error, and are offered suggestions about BRCA1 variants.
- NOT CLOSED

### PR-1015-10: at 390 one BRCA1 answer lands with the question hidden under the app bar
- Kind: screen
- Verdict: needs your eye
- What: on the BRCA1 answer at 390 in run 1 the first screen shows only "BRCA1?" of the question, the rest scrolled under the sticky app bar; the Marfan answer at 390 shows its full question. Overflow is 0 px. Not caused by today's cards as far as the screen shows; recorded for position.
- Evidence: `run1/brca1_plain_390_fold.png`, against `run1/q66_plain_390_fold.png`.
- Why a person would care: on a phone the answer appears without the question it answers.
- NOT CLOSED

## Checks that passed, each on a file read by the reviewer

- Card 111 repeat: no sentence of the form "X and X." in any of the eight answers (`run1/` and `run2/`, q66 and brca1, both widths).
- Card 111 list: every features sentence puts "and" only before the last name, for example "Congestive heart failure, Hypertropia and Micrognathia." (`run2/q66_plain_1280.txt`).
- Card 35: three of four off-topic follow-ups refused with "Outside biomedical research" and "0 tool calls · 0 sources cited" (`run1/q111_offtopic_followup_1280.txt`, `run1/q111_offtopic_followup_390.txt`, `run2/q111_offtopic_followup_390.txt`). The fourth is PR-1015-02.
- Overflow at 390: 0 px on every capture (`run1/results.json`, `run2/results.json`). Console errors 0, accessibility serious or critical 0.
- Position at 1280 and 390 against the prototype answer (`prototype_reference/prototype_answer_1280.png`, `prototype_answer_390.png`): centred card, question with New search on the right, meta line, summary, sources, follow-up, feedback, in the same order. Develop has no provenance spine and no trust pills row, a known gap the design README records for `screens/answer.html`, not a change of today.

## Time to answer

App's own "Answered" seconds, read from each text file; the capture's seconds_to_ready (whole steps, including the disclaimer and typing) in brackets.

| Question | Run 1, 1280 | Run 1, 390 | Run 2, 1280 | Run 2, 390 |
|---|---|---|---|---|
| Marfan features (q66) | 9.3 s (10.8) | 12.1 s (13.5) | 12.5 s (13.6) | 16.3 s (17.4) |
| BRCA1 diseases | 11.0 s (12.5) | 9.7 s (12.0) | 7.0 s (8.4) | 8.5 s (9.9) |
| Off-topic follow-up | 1.8 s | 2.9 s | error, no time shown | 1.5 s |

None over 20 s or 25 s.

Correction to the position line above: the design README (line 38) says `screens/answer.html` lacks the trace, tables and collapsed sources; it does not record the missing provenance spine and trust pills. That difference between develop and the prototype predates today's cards and is unjudged here.

## What was not captured, and why

- Golden run: not run, by the owner's standing rule; the floor does not apply, and "answered well of the fixed ten" was not read.
- The lead's spec had no prototype steps, so the prototype answer screen was captured separately with the repository's own `.claude/skills/verify/specs/home_and_answer.json` into `prototype_reference/` (it also asked develop "What does BRCA1 do?" once per width; those answers were not judged).
- Query 111's second off-topic follow-up (bitcoin) and its three on-topic controls ("and what about it in children?", "what about its symptoms", "tell me more about it") were not in the spec and were not captured, so "on-topic follow-ups are answered as before" is unverified.
- Rubric line 3 (Plain language against Researcher) was not captured: the spec asks in Plain language only.
- `run2_console.log` holds the refusal of a duplicate run2 start, not run 2's console; run 2's checks are in `run2/results.json`.
- No API log was read, so the cause of PR-1015-02 and PR-1015-03 is not established.

## Lead's triage, 2026-10-15

Notes beside the reviewer's findings; no finding is closed here, and the owner's retest decides.

- PR-1015-02: develop's API log for the failed follow-up (trace d34d824f) shows card 35's topic check answering in 255 ms; the step failed on the guard tier's classify call, which every question makes and made before today, timing out at 10.0 s and 5.0 s on its retry. Classify calls ran 0.6 to 9.1 s in the same window. Provider slowness, shown with the cards 84 and 72 message; not caused by today's merges.
- PR-1015-03: each Marfan answer's first sentence, "MedGen lists these clinical features: ...", is the writer's own grounded sentence, so all four answers have written prose and open on what was asked. On 9 October this question opened on its count line (`testing/Developer/reports/2026-10-09_product_check_8.7/diagnosis.md`, PR-87-04). Not a regression; whether a features answer should carry more than the list is the open question behind PR-1015-04.
