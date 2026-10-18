# Card 88 diagnosis: GERD at Researcher shows no written answer

Diagnosis only, 2026-10-05. No code was changed. Board card 88 in `testing/UI_fix_plan.md`, test query 75 in `testing/Test_queries_and_workflows.md`.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Reproduction](#reproduction)
- [Root cause](#root-cause)
- [Evidence](#evidence)
- [Relation to card 2 and phase 8.7](#relation-to-card-2-and-phase-87)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [Confidence](#confidence)
- [What this diagnosis did not cover](#what-this-diagnosis-did-not-cover)

## What the person sees

A person types `GERD` with the answer set to Researcher, is asked "What would you like to know about GERD?", and picks the symptoms and risk factors question. On some runs the answer is only "Found 5 pubmed records, 1 medgen record, 1 literature entity record and 5 clinical trial records for GERD." and four tables, with "Based on 12 sources, not yet confirmed". On other runs one sentence sits under that line, copied word for word from one abstract. On a good run, five sentences on symptoms, causes and complications appear.

The writing model did write a full answer each time. The answer checker deleted it before it reached the screen. The note that would say so ("the written summary of these records could not be verified against them, so this answer lists the records found instead") is sent by the server and hidden by the web app since the owner's decision of 2026-09-21 (`frontend/src/components/screens/AnswerScreen.tsx:457`), so the reader gets no hint why.

Plain language fails the same way. The 2026-09-29 retest compared Researcher's symptoms question with Plain's "What is GERD?" pick, a different question. Asked the same symptoms question today, Plain also came back with no prose once and with one sentence once.

## Reproduction

Develop API, guest sessions only, `/health` answered `{"status":"ok","app_env":"develop"}`. Each run is a fresh guest session: `GERD`, then the pick in the same session at the same depth, the way the web app's ask-back button sends it. Model sentences counts the sentences below the code-built "Found N" line, as streamed `token` events of kind `claim`.

| Run | Mode | Bare `GERD` | Pick outcome | Model sentences | Seconds (pick) |
|---|---|---|---|---|---|
| r1 | Researcher | asked back, 3.8 s | answer | 1, a copied abstract sentence | 27.1 |
| r2 | Researcher | asked back, 3.6 s | ask, structured fallback note | 0 | 13.0 |
| r3 | Researcher | asked back, 4.8 s | answer | 5 | 29.5 |
| p1 | Plain language | not asked back, answered, 32.6 s | answer | 1 | 26.1 |
| p2 | Plain language | asked back, 3.9 s | ask, structured fallback note | 0 | 28.5 |

The ask-back choices are written by a model and changed every run. The pick sent was the card's exact text, "What are the typical symptoms and risk factors of GERD?", in every run.

Local traces, same code as `develop` at 9a13e983, same synth-tier model, `CLASSIFIER_PROVIDER=jev` as on develop, with spies on the write step (`raw/local_write_trace.py`):

| Run | Mode | Outcome | Model sentences shown | Seconds |
|---|---|---|---|---|
| L1 | Researcher | answer | 1 of 9 written | 15.8 |
| L2 | Researcher | answer | 2 of 10 written | 21.7 |
| L3 | Plain language | answer | 2 of 5 written (after the repair draft) | 14.6 |

One further local attempt stopped at the guardrail with a transient error before any writing and is not counted. Questions used: 10 live and 4 local, 14 of the 15 allowed.

## Root cause

The prose is lost in the grounding pass, `synthesis/grounding.py`'s `run_grounding_pass`, called from `core/graph.py:12113` (`_ground_with_sentence_check`). Two separate checks delete faithful sentences.

Cause A, Researcher only. The Researcher depth line never tells the model to quote.

- Rule 3a of the system instruction (`synthesis/findings.py:885`) says to summarise an abstract in your own words and put the record's exact words inside the marker, `[4: "..."]`.
- The Plain language depth line repeats it: "with the exact supporting words inside the marker, as rule 3a says" (`synthesis/findings.py:1543`, added by 5d53f787 on 2026-09-23).
- The Researcher depth line (`synthesis/findings.py:1552` to `1562`) says only "Every sentence ends with the marker of the finding it rests on", which the model reads as a bare `[18]`.
- A reworded sentence with a bare marker has no quote, so it never becomes a candidate for the sentence check (`grounding.py:1314` to `1330`). The strict path then needs the claim to be a substring of the abstract, and a summary is not one, so it is stripped (`grounding.py:1335`).
- Only a sentence the model happened to copy word for word survives. When it copies none, nothing survives, `grounding.claims` is empty, and the structured fallback fires (`core/graph.py:12322` to `12331`): the code-built line and the tables, the outcome floored at ask, the note hidden.

Cause B, both depths. The record-naming rule deletes approved sentences that call the disease "GERD".

- A reworded sentence that cites a record the sentence before it did not cite must share a content word with that record's title (`grounding.py:1449` to `1455`, `_names_its_record` at `grounding.py:1602` to `1617`). It guards against a sentence silently switching disease (item 12.16 part 4).
- The opening sentence always counts as switching, since nothing came before it.
- The papers are titled "Gastroesophageal Reflux Disease." The model writes "GERD", the question's own word. "GERD" shares no token with the title, so the sentence is dropped even after Jev approved it.
- Once the opening sentence is dropped, the next one also counts as switching and needs the title words too. The loss cascades until a sentence happens to use "reflux", "disease" or "children".

Both causes run before any ordering of sentences, so the reader is left with the code-built "Found N" line on top and little or nothing under it.

## Evidence

Live, from the streamed events (`raw/r2_researcher_pick.jsonl`, `raw/p2_plain_pick.jsonl`):

- r2 and p2 carry exactly one `claim` token, the "Found N" line, then a `note` token reading "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead", and `done.trust_outcome: "ask"` with "Based on 12 sources, not yet confirmed". That note is emitted only by the structured fallback (`core/graph.py:9380`), which runs only when no model sentence survived grounding.
- r1's single surviving sentence, "GERD affects quality of life and may cause erosive esophagitis, esophageal strictures, and Barrett esophagus, a precursor to esophageal adenocarcinoma", is a word-for-word span of the PubMed abstract the run cited. Nothing reworded survived.
- The retest of 2026-09-29 (`q75r_gerd_pick.txt`) shows the same "not yet confirmed" line and no prose, the r2 shape.

Local, with the model's reply visible (`raw/L1_researcher.log`, `raw/L2_researcher.log`, `raw/L3_plain.log`):

| Run | What the model wrote | Grounding result | Why |
|---|---|---|---|
| L1 Researcher, first draft | 9 claims in 4 sections on symptoms, risk factors and complications, each faithful to an abstract, every marker bare (`[18]`, `[19]`) | 1 claim kept, 8 stripped, 0 sentence-check candidates | Cause A |
| L1 Researcher, repair draft | Quotes present this time (the repair directive differs) | 0 strict claims, 6 candidates, Jev approved 1, repair discarded by the strict-superset rule at `core/graph.py:12291` | Quote typo ("esagus"), Jev rejections, cause B |
| L2 Researcher, both drafts | Bare markers again, 0 candidates in both passes | 2 copied sentences kept, 8 and 23 stripped | Cause A |
| L3 Plain, first draft | 5 sentences, each with an exact quote | 4 candidates, Jev approved 2, still 0 claims kept, so `claims` empty | Cause B: the two approved sentences say "GERD" and "The typical symptoms are", neither shares a word with "Gastroesophageal Reflux Disease." |
| L3 Plain, repair draft | 6 sentences with quotes | Jev approved 3, 2 kept: the ones naming "children", the word in paper 19's title, and the sentence after it | Cause B |

Cause B checked with the real function, no model involved:

- `_names_its_record("GERD is a condition where stomach contents flow back ...", "Gastroesophageal Reflux Disease.")` returns False, shared stems none.
- The same sentence written with "gastroesophageal reflux disease" in place of "GERD" returns True.
- The record's own label stems are `diseas`, `gastroesophageal`, `reflux`.

## Relation to card 2 and phase 8.7

Card 88 is a distinct defect from card 2.

- Card 2 is about order: the code-built "Found N" line always leads, even when a good model sentence sits right below it. Card 88 is about loss: the model sentences are deleted before anything is ordered.
- Phase 8.7's design C (`testing/Developer/reports/2026-09-26_phase_8.7/design.md`) lets a classifier move an already-grounded model sentence to the top. It states that when no model sentence survived grounding, the code-built line leads as today. On r2, p2 and the retest nothing survived, so 8.7 would show the same page. On r1 it could lead with the one copied sentence, which still leaves the reader without the answer the model wrote.
- The parked builder branches (`feat/8.7-s1`, `feat/8.7-s3`) do not touch the Researcher depth line or `_names_its_record`. S1's second draft beside the first runs under the same depth line, so it would meet cause A too.
- Card 2's fix becomes visible only once card 88's is in: a classifier cannot pick a good first sentence that was deleted.

## Fix options

None of these hardcodes a question, a disease or a word list. Every option keeps the exact checks deciding acceptance, and Jev stays the only model judging reworded sentences.

### Option 1: the Researcher depth line asks for quotes, as Plain's does

- What changes: one clause in the Researcher entry of `_DEPTH_DIRECTIVES` (`synthesis/findings.py:1552`), the same instruction Plain already carries, pointing at rule 3a. The depth line sits in the user message, the dynamic suffix, so the stable prompt prefix stays byte-identical.
- Fixes: cause A. Reworded Researcher sentences become sentence-check candidates instead of being stripped unseen.
- Risk: every Researcher answer that cites an abstract or summary starts carrying quotes, so Jev runs on more sentences (measured at 343 to 611 ms per call) and more of each answer depends on its verdict. A Researcher answer could also get shorter where it now survives on copied sentences that a reworded version would lose.
- Answer path: yes. The golden run must hold at least 101 of 150 answered.

### Option 2: a record names what its own text abbreviates

- What changes: in `run_grounding_pass`, the labels a record is allowed to be named by (`labels_by_url`, `grounding.py:1154` to `1158`) also take any short form the same record defines in its own retrieved text, the pattern "long form (SHORT)" where the long form shares words with the record's title. Paper 18's abstract opens "Gastroesophageal reflux disease (GERD)", so "GERD" names paper 18. A paper that never defines "GERD" still cannot be named by it. Deterministic, read from retrieved data only.
- Fixes: cause B for any condition, gene or drug the records abbreviate (GERD, FMF, CF), at both depths.
- Risk: it loosens the guard against a silent switch of subject, but only to a term the cited record itself defines, so the G6PD-under-FMF case the rule was built for still fails. The definition matcher needs tests for a short form that is not an abbreviation of the title words.
- Answer path: yes. The golden run must hold at least 101 of 150.

### Option 3: the opening sentence may name the question's own subject

- What changes: `_names_its_record` accepts, for the first sentence only, a word from the licensed question content when the cited record came from a call the plan made for that question's resolved entity (`answer_call_ids`).
- Fixes: cause B for the opening sentence, and so the cascade, without parsing definitions.
- Risk: higher than option 2. A paper retrieved for the question but about something else could then be named by the question's subject, which is the switch the rule exists to stop. It also leaves a later sentence that switches papers exposed to the same deletion.
- Answer path: yes. The golden run must hold at least 101 of 150.

## Recommendation

Options 1 and 2 together, as one answer-path change with one golden run. Option 1 alone moves Researcher answers onto the checked quote path, and cause B then deletes them there, as L3 shows for Plain. Option 2 alone does nothing for Researcher while the model writes bare markers. Before merging, prove it the owner's way: the GERD pick at least five times at each depth on develop, each showing written prose under the records line, plus test query 75's other questions (`papers on the effects of caffeine on exercise performance`, `recent papers on statins`) for the restatement rules.

In the reader's words: "When I ask about the symptoms of GERD, I see a written answer about its symptoms, causes and complications, with each sentence linked to the paper it comes from, and not only a count of records."

## Confidence

- High that the prose is lost in the grounding pass and not by the writer: the live structured fallback note on r2 and p2, plus three local traces showing the full reply and each pass's result.
- High for cause A: two of two local Researcher runs wrote bare markers on every reworded sentence, with zero sentence-check candidates in four grounding passes, and the prompt text shows why.
- High for cause B: the real function returns False on the approved sentences and True when "GERD" is spelled out.
- Medium on how often each run shape occurs. Five live runs and three local runs show the spread (good, thin, empty) but not its rates. Jev rejecting some faithful sentences and occasional quote typos also cost sentences. Neither is a cause of card 88 on its own, and neither was measured beyond these runs.

## What this diagnosis did not cover

- The model's raw reply on the live develop runs. The event stream carries no stripped count or dropped sentences, so the mechanism was traced locally with the same code and models. That develop runs commit 9a13e983 was not checked against the deployment.
- Why r3 succeeded live. Likely the model quoted or copied that time, but its reply was not visible.
- Whether options 1 and 2 hold the golden run, and their effect on speed and cost. Nothing was built or measured.
- The Jev rejection rate on faithful reworded sentences, and the repair draft's strict-superset rule discarding a partial rescue (`core/graph.py:12291`).
- Run p1's bare `GERD` in Plain: the `think.ask_back` decision says `ask_back`, yet the run answered with records instead of asking back, in 32.6 seconds. Seen once. It belongs to query 76, not this card.
- Card 2's opening line itself, and whether the "not yet confirmed" trust line should still show when the note explaining it is hidden.
