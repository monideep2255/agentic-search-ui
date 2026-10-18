# Card 87 diagnosis: recent-onset diabetes treatment asked back

Read-only diagnosis, 2026-10-05, against the develop API as a guest. Raw responses are in `raw/run01.json` to `raw/run10.json`; the runner is `run_card87.py`. Ten live questions, within the budget of 12.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Reproduction](#reproduction)
- [Root cause](#root-cause)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [Confidence](#confidence)
- [Not covered](#not-covered)

## What the person sees

- They type `recent-onset diabetes treatment`, a question that names a subject and the kind of thing they want (treatment).
- They get "What would you like to know about recent-onset diabetes treatment?" with four chips, and no search runs (about 4 to 8 seconds, 0 tools, 0 sources).
- Query 84 says this must be answered. The recency rule did not misfire. The "How far back should I search?" question never appeared for it.

## Reproduction

| Run | Question | Asked back | Decision that asked | Classifier | Seconds |
|---|---|---|---|---|---|
| 1 | recent-onset diabetes treatment | no, answered | ask_back chosen, but choices not usable, so it searched | jev | 41.5 |
| 2 | recent-onset diabetes treatment | yes | think.ask_back | jev | 5.8 |
| 3 | recent-onset diabetes treatment | yes | think.ask_back | jev | 4.3 |
| 4 | recent-onset diabetes treatment | yes | think.ask_back | jev | 4.6 |
| 5 | recent-onset diabetes treatment | yes | think.ask_back | jev | 3.7 |
| 6 | recent-onset diabetes treatment | yes | think.ask_back | jev | 7.8 |
| 7 | recent papers on statins (control) | yes, how far back | think.recent_years = recent_unbounded | jev | 2.3 |
| 8 | papers on statins since 2022 (control) | no, answered | recent_years = not_applicable | jev | 33.0 |
| 9 | reflux disease (query 76, should ask) | yes | think.ask_back | jev | 3.8 |
| 10 | Any trials for GERD? (query 76, should not) | no, answered | not reached (4 words) | jev | 42.9 |

- Runs 1 to 6: think.ask_back picked ask_back every time, confidence 0.99 to 1.0, 127 to 261 ms. think.recent_years picked not_applicable every time, confidence 0.93 to 0.95.
- The Think narrative on runs 2 to 6 reads "the ask-back classifier read a one-to-three-word opening question", not the recent-work narrative.
- Wording of the asked question varies a little between runs ("What aspect of ... would you like to explore?"), because a guard-tier writer composes it each time.
- Run 1 is stable evidence of the same pick: the classifier said ask_back, but the writer's choices were unusable, so the code fell open and searched. Its answer was slow (41.5 s).

## Root cause

The ask-back is the short-question rule (query 76, card 12.3), not the recency rule.

- File `src/system_03_search_agent/core/graph.py`, line 3335: `_MAX_CLARIFY_TRIGGER_WORDS = 3`. Line 3711 to 3729: when the session has no memory, `query.text.strip().split()` gives three tokens for `recent-onset diabetes treatment` (the hyphen is not a separator), so the question enters the short-question path.
- Lines 959 to 979: the `think.ask_back` spec gives the classifier only the question text and two options. ask_back means "only names a subject, a bare noun or short phrase with no request in it". proceed means "asks something or names the kind of answer wanted, such as a definition, papers, trials, variants, symptoms or a cause".
- The classifier (Jev, `CLASSIFIER_PROVIDER=jev`, confirmed by `decided_by: jev` on every record) reads `X treatment` as a noun phrase with no request, so it picks ask_back at near full confidence, 6 of 6 times. The criteria list does not name "treatment" or "therapy" as a kind of answer wanted, and a noun phrase like this is the exact shape the first option describes. Query 76 deliberately asks back `reflux disease` for the same reason, so the two outputs are consistent with the spec.
- The recency decision (lines 982 to 1008) is correct: not_applicable, with its criteria naming "a disease of recent onset". It is not the cause.
- Query 84 and query 76 therefore disagree about this input. Query 84 expects an answer. Query 76 expects any bare phrase of one to three words to be asked back. Nothing in the spec or the test document says how a phrase with an implied request ("treatment") is to be treated.
- Stable: yes, 6 of 6 picks, so the owner's retest was not a fluke.

## Fix options

| Option | What changes | Risk | Answer path | Golden gate |
|---|---|---|---|---|
| A. Tune the ask_back criteria | Reword the `proceed` criterion so a subject plus the kind of thing wanted (treatment, therapy, causes, genes, trials) counts as already stating the request. Description only, no word list, no test question lifted in. | `reflux disease` must still be asked back (query 76), so it needs a repeated live check on both sides. Jev may be a trained classifier that takes the criteria as input, so wording may move it only a little. | Yes, it changes which questions are searched | Golden run must hold at least 101 of 150 |
| B. Change the product rule in query 76 | Decide that "subject plus a request noun" is answered, and edit the query 84 and 76 expectations to say so. No code. | Needs the owner, since it is a product call. | No | None |
| C. Pass the recency decision's reading into the ask-back call | Give ask_back a second signal, for example the Think classification (which already ran for query 84 and read it as "broad open-ended question about treatment"). | Adds latency, because ask_back would wait on Think, and breaks the "overlap three calls" speed design (card 6). | Yes | At least 101 of 150 |

## Recommendation

Option A first, a wording change to the `proceed` criterion in `_ASK_BACK` (graph.py lines 959 to 979), because the classifier decides and code only verifies, and no word list is added. Check it with at least five repeated live runs on both sides: `recent-onset diabetes treatment` and similar subject-plus-request phrases should proceed, and `reflux disease`, `GERD`, `BRCA1` and `Marfan` should still be asked back. If Jev does not move on a wording change, the owner must choose between B (accept) and a retrain or different classifier, since option C costs speed.

Separate small finding: when the writer's choices fail, the code searches (run 1), which is correct fail-open, but that run took 41.5 s.

## Confidence

- High that the short-question ask-back is the decision that fired, and that Jev made it (6 of 6 records, plus the Think narrative text).
- Medium on whether a criteria rewording alone will flip Jev, because I could not run the classifier offline and tested no wording.

## Not covered

- No wording change was tried, so no fix is proven.
- No golden run was made.
- Jev's training or internals were not read; only its picks and confidences.
- Inside a conversation (with memory) the short-question path is skipped, so that case was not tested.
- Four-word phrases such as `recent-onset diabetes treatment options` were not run, and the check that "recent papers" still asks was one run (run 7).
- The earlier retest's `q84b_since2022` was not re-read in detail; run 8 stands in for it.
