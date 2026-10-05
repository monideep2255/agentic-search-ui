# Workstream W1 (writing): the step that writes and checks the answer

Scout `writing`, 2026-10-05. Read-only plan input for cards 88, 89, 2, 17, 22, 30, 46, 57, 13, 18, 12, 11. No code changed. Paths are relative to `<repo-root>`; code is under `src/system_03_search_agent/`.

## Table of contents

- [Method](#method)
- [Card table](#card-table)
- [Root causes shared by several cards](#root-causes-shared-by-several-cards)
- [Suggested order inside the workstream](#suggested-order-inside-the-workstream)
- [Owner decisions](#owner-decisions)
- [What I did not check](#what-i-did-not-check)

## Method

- Cards 88 and 89 rows come from `testing/Developer/reports/2026-10-05_card88/diagnosis.md` and `testing/Developer/reports/2026-10-05_cards89_90/diagnosis.md`.
- The other ten rows come from reading the board rows, `tracker/phase_8.1.md`, `tracker/phase_8.10.md`, `testing/UI_fixes_done.md`, the parked phase 8.4 builder reports (commits a2255cc5 and d3d44172, reachable in history but on no branch), and the code in `core/graph.py`, `synthesis/grounding.py` and `harness/cost_control.py`.
- Live: 6 guest questions on develop on 2026-10-05, summaries in `testing/Developer/reports/2026-10-05_board_plan/scripts_w1/out/` (script `run_w1.py`, `run_w1b.py`). No tokens saved.

Live results used below:

| Run | Question, depth | Outcome | What matters |
|---|---|---|---|
| mody_a | MODY genes, Plain | stream error, 3.7 s, no answer | One transient error, not repeated |
| mody_c | MODY genes, Plain | ask, 19 citations, 40.6 s | Six genes and seven diseases listed and cited; no written prose, "not yet confirmed" |
| mody_b | MODY genes, Researcher | ask, 19 citations, 14.2 s | Same six genes, a written sentence naming them with citations; "not yet confirmed" |
| brca1_path | Which BRCA1 variants are pathogenic?, Researcher | answer, 36.2 s | 40 variants listed, no mention that classification was not retrieved, "Based on 58 sources" |
| brca1_dis | Diseases associated with BRCA1, Researcher | ask, 26.7 s | "Found 4 disease records", 22 sources in the trust line, 23 citations; citation 7 shows the wrong sentence |
| brca1_what | What is BRCA1?, Plain | answer, 15.7 s | "Based on 18 sources" beside 19 citations |

## Card table

Columns follow the brief: 1 card and feature, 2 impact, 3 status today, 4 root cause, 5 shared cause (card numbers), 6 code touched, 7 size, 8 depends on and blocks, 9 needs the owner.

| Card | Feature in plain words | Impact | Status today | Root cause | Shared with | Code touched | Size | Depends on / blocks | Owner decision |
|---|---|---|---|---|---|---|---|---|---|
| 88 | "I typed GERD and got only a count of records and tables, no written answer" | wrong or degraded answer | Still happens: 2 of 3 live Researcher runs and 1 of 2 Plain runs on 2026-10-05 had zero or one model sentence (diagnosis, `card88`) | Known. Cause A: the Researcher depth line never asks for quotes, so reworded sentences carry a bare marker and are stripped (`synthesis/findings.py` `_DEPTH_DIRECTIVES`, lines 1552 to 1562, against Plain's line 1543). Cause B: `_names_its_record` (`synthesis/grounding.py:1602`) needs a shared word with the record title, and "GERD" shares none with "Gastroesophageal Reflux Disease." | 89 (cause B and the fallback shape), 17 (same function, opposite direction), 2 (loss versus order), 13, 30 | `synthesis/findings.py` `_DEPTH_DIRECTIVES`; `synthesis/grounding.py` `run_grounding_pass` (labels_by_url, lines 1154 to 1158 and 1449 to 1455), `_names_its_record`; call site `core/graph.py` `_ground_with_sentence_check` | M, being built (options 1 and 2 together, one golden run of at least 101 of 150) | Blocks 2 (a classifier cannot lead with a sentence that was deleted), 17 (must be built with it). Needs the golden run | No. Standing owner proof rule applies: GERD pick at least 5 times per depth |
| 89 | "The Mediterranean question sometimes never names Familial Mediterranean fever" (card 90 folded in) | wrong or degraded answer | Still happens: named the disease in 2 of 9 runs, 3 of 9 gave no prose (diagnosis, `cards89_90`) | Known in part. The disease name sits in one abstract sentence the writing model may skip (`TOPIC_ANSWER_DIRECTIVE`, `synthesis/findings.py` about line 1909, gives no "name the condition" instruction). Nothing checks that the answer names the subject of the evidence. Bare-pronoun rule misses "This disease is" (`_opens_on_bare_pronoun`, `grounding.py:1642`). The 3 empty runs are not explained: the pre-grounding draft was not seen | 88 (empty runs are the same fallback shape; the pre-grounding draft is not seen, so cause A or B may also be in play here), 17 (the record-naming rule is the one that tells the G6PD sentence apart) | `synthesis/findings.py` `TOPIC_ANSWER_DIRECTIVE`, `build_synth_messages`; a new write-side classifier call near `core/graph.py` write step (about line 12030) with a verify-and-retry like the completeness repair; `grounding.py` `_opens_on_bare_pronoun` | M, being built (option B, A as its first half) | Land after or with 88 so the pre-grounding drops from 88's causes are gone before judging the rest. Option C (pronoun rule) only after B | No |
| 2 | "Every answer opens with 'Found N records for X', so the first sentence never answers my question" | wrong or degraded answer (the answer is there but second) | Still happens: every live answer today opened with the code-built line (brca1_dis, brca1_path, mody_b) | Known. The lead sentence is built in code (`synthesis/answer_layout.py` lead builders, assembled in `core/graph.py` write step); design C of phase 8.7 lets a classifier move a grounded model sentence to the top (`testing/Developer/reports/2026-09-26_phase_8.7/design.md`). Builder branches `feat/8.7-s1`, `feat/8.7-s3` are parked | 88 (when nothing survives grounding the code-built line leads whatever the order fix is), 50 (carried with it by decision) | `core/graph.py` write step assembly; `synthesis/answer_layout.py`; classifier in the style of `think.asks_features` | M to L (owner already said go, 2026-09-25; phase 8.7) | Depends on 88 and 89: nothing to promote when the prose was deleted. Blocks nothing | No: already decided. Re-confirm only that it follows 88 |
| 17 | "A reworded sentence can point at the wrong paper when the only title word shared is generic, like 'patients'" | wrong or degraded answer (a wrong paper behind a cited sentence) | Still happens by reading: develop's `_names_its_record(sentence, labels)` has no other-records argument (`grounding.py:1602`). The fix (Card 25 in builder F's report) exists only in unreachable commit a2255cc5, not on any branch | Known. One shared stemmed word licenses the switch, however generic | 88 (same function, same call site; tightening here can undo 88's loosening), 89 (run 3 and 7 lead with the G6PD paper) | `synthesis/grounding.py` `_names_its_record` and its call in `run_grounding_pass` (lines 1449 to 1455); tests in `tests/system_03_search_agent/synthesis/test_sentence_check.py` | S (fix written and tested in a2255cc5; port plus reconcile with 88) | Must be built in sequence with 88: same function. See the collision in the shared causes section | No |
| 22 | "One answer shows several different totals and never says which is which" | screen or wording only | Still happens: brca1_dis says "Found 4 disease records", 22 sources in the trust line, 23 citations; brca1_what says 18 sources beside 19 citations | Known in part. Counts come from different units: records found, distinct records cited (trust line, `synthesis/trust.py` `answer_trust_line`), citation markers (frontend meta line, `frontend/src/hooks/useRunView.ts`). Screen half exists in unreachable commit d3d44172 (builder G); backend wording ("of N available", `synthesis/answer_layout.py` lines 1056 and 1080) unbuilt | 57 (the 22 versus 23 in its row), 8 (trust-line wording) | `synthesis/trust.py` `answer_trust_line`; `synthesis/answer_layout.py`; `frontend/src/hooks/useRunView.ts`, `AnswerScreen.tsx` | S to M | Independent of 88. Pairs with card 8 (trust wording). Frontend half must be re-applied from d3d44172 | Yes: say one unit (recommend "N sources" meaning distinct records everywhere, and the code-built line stops saying "available") |
| 30 | "Which BRCA1 variants are pathogenic? gives 40 unclassified variants and drops the model's honest caveat" | wrong or degraded answer, confident and wrong | Still happens, and worse: brca1_path today returned outcome `answer`, "Based on 58 sources", 40 variant names, nothing saying classification was not retrieved. On 2026-09-25 it was `ask` | Known. The retrieval carries no clinical significance; the writing model says so, and that caveat cannot ground against a variant name, so it is stripped (F-8.1-A16). The listing is shown with no disclosure, and the trust floor does not know the question's key property is missing | 88 (grounding deletes a faithful sentence), 12 (verdict rests on the surviving subset), 13 | `synthesis/grounding.py` (absence sentences have nothing to ground on); `core/graph.py` write step fallback and listing; ClinVar breadth call in the plan or act step (retrieving significance is the real fix) | M to L; the honest-disclosure half is S to M, retrieving significance is L | Disclosure half independent. Retrieval half belongs to W-tools (ClinVar breadth). Related to 88's fallback fix | Yes: when the data cannot answer the asked property, recommend show the list with one plain sentence "ClinVar's classification of these variants was not retrieved, so this list is not the pathogenic ones", and floor the trust to `ask` |
| 46 | "When my question hits its limit I see 'partial result below' and nothing below" | blocks an answer (a promise of content, none delivered) | Still happens by reading: `_partial_result_for_cap` (`core/graph.py:12967`) emits only the note and `done` with `trust_outcome="flag"`; no findings or citations. Not reproduced live (needs a cap hit) | Known. Both cap paths (routed in at line 11694, inline at line 12048) return before any grounding or fallback listing | 88, 30, 13 (the code-built fallback listing is the shared landing) | `core/graph.py` `_partial_result_for_cap`, `write_node` early returns at 11694 and 12048; `harness/cost_control.py` `PER_QUERY_CAP_PARTIAL_RESULT_NOTE` | S to M | Needs the fallback listing builder to accept state with partial findings. Independent of 88 | No: decide from the user's chair, show what was gathered with its citations under the note, and keep `flag` (recommend). Escalate only if the gathered set can be partly wrong |
| 57 | "A cited sentence shows a quote that does not contain its own numbers" | wrong or degraded answer (the reader cannot verify the claim) | Still happens, root cause confirmed on today's run: brca1_dis sentence "Mutations in this gene are responsible for approximately 40% ... [7]" shows citation 7's text as "The encoded protein participates in transcription, DNA repair of double-stranded breaks, and recombination", the sentence before it | Known: `core/graph.py` the citation builder, `claim_text_by_citation_id.setdefault(citation_id, claim.claim_text)` (about line 9881) keeps the first clause that cited a record. Its comment says either clause is true because both are checked against the same field value; on the quote path each sentence is checked against its own quote, so a record cited by two sentences shows the first sentence for both | 22 (the 22 versus 23 count in this card's row), 88 (Researcher quotes will make more records cited by several sentences, so this shows more often) | `core/graph.py` the citation builder around lines 9870 to 9940 (`_citations_for_grounding`-shaped function) and its two Layer 2 and 3 variants | S | Land with or just before 88 option 1. No dependency on others | No |
| 13 | "What genes are associated with MODY? failed its citation check on 5 of 6 runs" | wrong or degraded answer (was a refusal) | Largely superseded. Set 11.20 (2026-09-22) rebuilt it as a MedGen lookup with 5 of 5 live runs. Today: 2 of 2 runs answered the six genes with 19 citations; both at outcome `ask` ("not yet confirmed"), one with a written sentence (Researcher), one list only (Plain). 1 of 3 runs hit a transient stream error | Known for the old failure: the model abbreviated the disease name and the exact gate rejected it (F-8.1-02), plus the stacked-marker pairing risk (F-8.1-J01). The "ask" floor today is the same no-surviving-prose fallback as card 88 | 88 (fallback shape), 12 (verdict variance) | None to close. If kept open: `synthesis/grounding.py`; `synthesis/findings.py` writing instruction (abbreviations) | S (close, or fold the residual into 88) | Close after 88 re-measures. Do not rebuild the stacked-marker fix: it was reverted because it licensed wrong gene-disease pairings | No. Recommend close as superseded by 11.20, with the `ask` residual noted under 88 |
| 18 | "A record with several sentences shows as several list rows under one heading" | screen or wording only | Still happens by reading: `core/graph.py` `listing()` and `plain_listing()` add one row per surviving sentence with no merge. Helper `merge_sentences_by_citation` exists only in unreachable commit a2255cc5 (`synthesis/answer_layout.py`, 4 tests); wiring never built. Not reproduced live today | Known. `build_structured_fallback_narrative` marks each sentence of one record with the same citation; the listing does not merge them | 88 (more multi-sentence records will survive grounding once 88 lands), 57 | `core/graph.py` `listing()` and `plain_listing()` (about lines 9260 to 9330 on the 8.4 branch's numbering); `synthesis/answer_layout.py` | S | Same file as 88, different functions: build after 88 merges to avoid conflicts. Add a test (the row says none exists) | No |
| 12 | "The trust verdict under an answer changes with nothing else changed: flag four times, ask once" | wrong or degraded answer (a trust signal that wobbles) | Likely still happens, not freshly measured. Today's observed `answer` versus `ask` on the same evidence (89's 9 runs, 88's runs) is the same upstream wobble. `synthesis/trust.py` itself is proven deterministic | Known (F-8.1-01, `tracker/phase_8.1.md` line 185): the verdict is computed over the claims the model's prose grounded that run, and `_apply_conflict_flags_to_claim_trusts` floors a claim from whichever Layer 1 and Layer 2 pairs land in that subset. The earlier fix (floors over the full retrieval) was reverted because the conflict check pairs a GO process name with a gene symbol and labels correct answers "Sources disagree" (F-8.1-A13) | 88, 89, 13, 30 (all feed it by changing which sentences ground) | `core/graph.py` `_apply_conflict_flags_to_claim_trusts`, `trust_for_claims` callers; `synthesis/trust.py` `detect_conflict` | M | Depends on fixing `detect_conflict` comparability (compare like fields only), then redoing the full-retrieval floor. Also easier to measure after 88 and 89 stabilise the grounded set | Yes: confirm the rule "the verdict rests on the whole retrieval, not on which sentences the writer chose" (recommend yes: this is what the reverted fix tried, and a wobbling verdict is the more dishonest of the two failures) |
| 11 | "The same question does not always return the same papers; `reflux disease` found nothing once in six" | wrong or degraded answer (rare) | Not reproducible: 6 full runs and 18 direct searches returned one set (F-8.1-03, 2026-09-25); 9 of 9 Mediterranean runs returned the same 5 PubMed records (89's diagnosis, 2026-10-05). The `reflux disease` half is a Think-step entity-resolution call | Unknown. Reasoning: the PubMed term is a pure function of the resolved entity and results sort by relevance, so variance would sit in NCBI's ranking boundary or in the model-based entity step | none in this workstream (not a write-step defect) | none identified; if pursued, Think's entity resolution in `core/think.py`-area code (not read) | S to investigate, no fix known | None | No. Recommend park: moved to the Think and retrieval workstream, with a trigger (reopen on a captured empty-result run) |

## Root causes shared by several cards

### Cause 1: the grounding pass deletes faithful sentences, then the code falls to a count and tables

- Cards: 88, 89 (the 3 of 9 empty runs), 13 (the `ask` residual), 30 (the honest caveat), 12 (the verdict follows the surviving subset), 2 (cannot lead with a sentence that was deleted).
- Mechanisms, all in `synthesis/grounding.py` `run_grounding_pass` and its call in `core/graph.py` `_ground_with_sentence_check`:
  - No quote on a reworded sentence (Researcher depth line, 88 cause A).
  - The record-naming rule (88 cause B, and 89 if its empty runs are the same).
  - A sentence that states absence ("not retrieved") has no record to ground on (30).
- One change that closes the family: make the exact checks the only judge, but stop the three losses at their source. That is 88's options 1 and 2, plus for the empty case a visible reason. The structured fallback note ("could not be verified against them") is sent and then hidden by the web app (`frontend/src/components/screens/AnswerScreen.tsx:457`, owner decision 2026-09-21). Showing it, or a plain "I could not write a checked summary; here are the records" line, tells the person why there is no prose on cards 88, 89, 13 and 30. That is a one-line owner decision to revisit.
- Evidence for the claim that 89's empty runs share it: 89's own diagnosis could not see the draft. The cheap proof is one local trace with the 88 spies (`raw/local_write_trace.py` under `testing/Developer/reports/2026-10-05_card88/raw/`) on the Mediterranean question. I did not run it.

### Cause 2: `_names_its_record` is pulled two ways

- Cards: 88 (loosen: "GERD" must name its record), 17 (tighten: a generic word must not name a record), 89 (it is what separates the FMF sentence from the G6PD sentence).
- Collision to plan for: the card 17 fix in a2255cc5 only counts a shared word that is absent from every other cited record's title. On the GERD question many papers are titled "Gastroesophageal Reflux Disease", so "reflux" and "disease" appear in all of them and would count for nothing. The 17 fix alone would make 88 worse for any question where the cited records share a topic title. 88's option 2 (a record is also named by a short form its own text defines, "long form (SHORT)") is the way out: the licence comes from the record, not from the title overlap.
- One fix: build 88 option 2 and card 17 as one change to this one function with tests for both: GERD (must pass), generic "patients" (must fail), G6PD under FMF (must fail).

### Cause 3: a citation shows only the first sentence that cited it

- Cards: 57 (confirmed on today's run), 22 in part (the 22 versus 23 counts), and 88 widens it.
- Where: the `setdefault` on `claim_text_by_citation_id` in `core/graph.py` (about line 9881). Fix: when a record is cited by more than one sentence, the citation carries the sentence that holds the checked quote for the clause shown, or all of them joined, never silently the first. Small. Land it with 88 option 1, which makes Researcher sentences carry quotes and so share records more often.

### Cause 4: no landing for "the writer produced nothing usable" or "the budget ran out"

- Cards: 46 (nothing below the note), 88 and 89 (count line and tables only), 30 (a list presented as an answer).
- One fix: a single fallback builder that always renders what was gathered with its citations, with an honest reason line, and floors trust. 46 uses it from the cap path; 30 adds the "property not retrieved" line to it.

### Cause 5: counts of three kinds with no labels

- Cards: 22, 57's trust line (22 versus 23), card 8.
- One fix: one named unit across code-built lines, trust line and meta line.

## Suggested order inside the workstream

1. 88 and 17 together, option 1 plus option 2: the grounding losses are the largest user-felt defect, and 17's fix would otherwise regress it.
2. 57 with it: Researcher quotes will multiply multi-sentence citations, and the first-sentence rule gets worse.
3. 89, option B with A first, after 88's draft is traced: some of its empty runs may already be closed by step 1, so measure first.
4. 46: small, a blank page after a promise is the worst screen in this workstream, and it reuses the fallback builder.
5. 2: only meaningful once model sentences survive; phase 8.7 design C.
6. 30: disclosure half now (a person can act on a wrong confident list), retrieval half goes to the tools workstream.
7. 22: wording and the frontend half re-applied, after the trust wording card 8 is settled.
8. 18: after 88 merges, same file.
9. 12: after `detect_conflict` is fixed; measure with 5 repeated runs after steps 1 to 3 shrink the variance.
10. 13 and 11: close 13 as superseded; park 11 until a failing run is captured.

## Owner decisions

- 22: which single unit do the totals use? Recommend "N sources" meaning distinct records everywhere.
- 30: recommend the list stays but carries one plain line saying classification was not retrieved, and trust floors to `ask`.
- 12: recommend "the verdict rests on the whole retrieval", with the conflict check fixed first.
- Hidden fallback note (relates to 88, 89, 13): recommend showing a short plain reason when no written summary survives. Reverses the 2026-09-21 decision for this one case, so the owner decides.
- 13 and 11: recommend close 13, park 11.

## What I did not check

- The pre-grounding draft on the Mediterranean question, so whether 89's empty runs are cause 1 or something else.
- Card 46 live: a cap hit was not reproduced, so what findings exist in state at each cap path is unread.
- Card 18 live: not reproduced today, status is by reading the code and the 8.4 builder report.
- Card 12: no fresh repeated runs; only today's incidental `answer` versus `ask` observations.
- Card 11: `reflux disease` was not re-run (6 live questions used); the Think entity-resolution code was not read.
- Whether the commits a2255cc5 and d3d44172 apply cleanly to develop; they predate several merges.
- Develop's deployed commit against 9a13e983.
- The first MODY run's transient stream error cause (not repeated on the next run).
