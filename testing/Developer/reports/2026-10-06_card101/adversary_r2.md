# Card 101 round 2 adversary report

Fresh-context adversary for branch `fix/card101-check-every-rewording`. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [What held](#what-held)
- [What I did not cover](#what-i-did-not-cover)
- [Spend](#spend)
- [Verdict](#verdict)

## Findings

### A2-101-01: a copied cut that drops "There is no evidence that" shows the opposite of its paper, with no check, on develop and on this branch

- Blocking for card 101: no. It sits outside the change (the owner kept copied record words showing without a call), and develop behaves identically. Severity as a product defect: critical. It needs its own card.
- What: the strict copy test (`ground_claim`, containment after lowercasing) accepts any contiguous run of record words. A run that begins after a negating or hedging lead-in, written with a capital so the fragment rule (`_opens_on_record_fragment`, lowercase only) does not fire, reaches the screen with no sentence check and no negation parity check. Attaching the writer's own quote does not help: the strict path wins first and the quote is ignored.
- Input, offline through the real `run_grounding_pass` (`raw/adversary_r2/probe_paths_r2.py`), record sentence "There is no evidence that aspirin prevents colorectal cancer in adults.":
  - writer: "Aspirin prevents colorectal cancer in adults [1]." Shown with no check, develop and branch.
  - writer: the same with `[1#0]` and quote "aspirin prevents colorectal cancer in adults". Shown with no check, develop and branch.
  - record "Earlier studies suggested that montelukast improves symptoms, but this trial found no benefit."; writer "Montelukast improves symptoms [1]." Shown with no check, develop and branch.
  - control, lowercase "aspirin prevents ...": stripped by the fragment rule, both.
- What the person sees, develop and branch alike: "Aspirin prevents colorectal cancer in adults [1]", cited to a paper that says there is no evidence it does.
- Why it matters: this is a reversal, not a dropped limit. The diagnosis described P1 only as dropping a limiting clause and the build report treats it as low value ("the check approved that cut 3 of 3"). A confident wrong record is the worst outcome the product names.
- Suggested fix (own card): the diagnosis's option D, widened: a copy that starts or ends inside a record sentence goes to the sentence check, whatever its first letter's case; at minimum apply `exact_synthesis_checks_pass`'s negation parity against the whole record sentence the cut sits in.
- NOT FIXED

### A2-101-02: a copied cut that drops a tail limit, and two copied clauses composed into a new claim, still show unchecked

- Blocking for card 101: no (outside the change, identical on develop). Severity: major.
- What: a cut that starts at a record sentence's start and stops before its limiting tail passes the strict test and no rule looks at the tail. Separately, each clause of a sentence is grounded on its own, so two copied runs, each contained in a record, compose into a claim neither record makes.
- Input and output, offline, both trees identical:
  - record "Antibiotics are effective only when a bacterial infection is confirmed."; writer "Antibiotics are effective [1]." Shown, no check.
  - record "Bronchiolitis is a self-limited disease in healthy infants and children."; writer "Bronchiolitis is a self-limited disease [1]." Shown, no check (this is the "healthy" limit card 101 says it now sends to the check; it only does so when the writer rewords, not when it cuts).
  - record "Drug X reduces mortality in women but not in men."; writer "Drug X reduces mortality [1] in men [1]." Shown as "Drug X reduces mortality [1] in men [1].", no check. A reversal by composition.
  - writer "Use of a high-flow nasal cannula is becoming common [1] in infants with bronchiolitis [4]." with [4] a different paper ("Nebulized hypertonic saline is used in infants with bronchiolitis."). Shown, no check: the population comes from a different paper.
- Why it matters: the build report says, in the user's words, that a dropped "usually" or "healthy" "now meets card 99's dropped-limit check like every other rewording". That holds only when the writer rewords. The same dropped limit written as a cut skips every check.
- Suggested fix (own card): as A2-101-01; and treat a sentence whose clauses are each a partial cut as one rewording for the check.
- NOT FIXED

### A2-101-03: a short record value wrapped in an open question's words still shows unchecked, and the build report's user-words promise says otherwise

- Blocking for card 101: unsure. The owner's decision row reads "code ... never approves a rewording on its own", and this is code approving a sentence that is all the app's words around one record value. The diagnosis scoped it out as option E and the build report lists it under Not covered, so whether it is inside the decision is the owner's call. Severity as a product defect: major.
- What: the strict path's `b in a` direction (`ground_claim`, record value inside the claim) plus the open question's licence (`_licensed_question_content`) plus function words ("all", "only", "every", "known" are exempt) lets a sentence assert a new fact around a short value, with no check.
- Input and output, offline, develop and branch identical:
  - question "Which drugs can cure bronchiolitis in babies?", record [3] `name: Ribavirin`; writer "Ribavirin can cure bronchiolitis in babies [3]." Shown with no check.
  - the same with "in all babies": shown with no check.
  - question "What causes bronchiolitis in babies, and how is it usually treated?", title "Acute bronchiolitis."; writer "Acute bronchiolitis is usually treated in babies [2]." Shown with no check (the diagnosis's P2 probe, reproduced).
  - Control: a closed question ("Is ...?") licenses nothing, so the same shape is stripped. The hole is open questions only.
- What the person sees: a cure claim, cited to a record that only names the drug.
- The build report, "The change in the user's words": "No sentence the app writes in its own words reaches the screen unless the sentence check has read it." False for this path and for A2-101-01 and 02. The sentence should say "no reworded sentence" and name the two exceptions, or the owner will read it as wider than it is.
- Suggested fix: correct the build report's sentence before merge; give P2 its own card with a measurement, as the diagnosis proposed, and include the "can cure" shape.
- NOT FIXED

### A2-101-04: when the check holds back a sentence code used to approve, its neighbours can leave with it, so the cost told to the owner undercounts

- Blocking: no. Severity: minor. Inside this phase's change (the sentence-level rules are untouched, but this change is what now exposes the moved sentences to them).
- What: three existing sentence rules key off whether the previous clause or sentence survived: the middle-strip rule, the bare-pronoun rule and the record-switch rule (item 12.16 part 4). On develop a code-approved sentence always survived; on this branch a held-back one does not, so the next copied clause, a following "It ..." sentence, or a following approved rewording that does not name its record can go too.
- Input, offline, mocked check that approves every candidate except the sentence code used to approve (`raw/adversary_r2/probe_cascade.py`), record "Bronchiolitis is a self-limited disease in healthy infants and children. It usually lasts about two weeks. Treatment is usually symptomatic, ...":

| Writer's text after "Bronchiolitis is a self-limited disease in infants and children [1#0]" | Develop shows | Branch shows |
|---|---|---|
| ". It usually lasts about two weeks [1]." (copied) | both sentences | nothing |
| ". Care mainly treats the symptoms and keeps oxygen and fluids adequate [1#1]." (approved rewording) | both sentences | nothing |
| ", and treatment is usually symptomatic [1]." (copied clause) | the whole sentence | nothing |

- In these probes the held sentence really is widened (it drops "healthy"), so holding it is right; the point is the size of the cost. The decision row and the build report state the cost as "about 1 faithful sentence in 80 shown". Each hold can take one more, and a short answer can fall to the bare record list (in the real flow an empty grounding goes to the repair or the structured fallback).
- Not seen in the recorded live answers: in round 2's two held-back G6PD sentences (Mediterranean 1 and 5) no neighbour was lost to these rules. So this is a mechanism with no measured frequency yet, not a measured regression.
- Suggested fix: none needed for merge; state the cascade in the build report's cost line so the owner's accepted cost is the real one, and count lost neighbours in the next live measurement.
- NOT FIXED

### Evidence for A2-101-01 to 03: the check would stop every one of these if it were asked

- Offline (`raw/adversary_r2/exact_on_cuts.py`, `exact_on_cuts.txt`): with the whole record sentence as the quote, code's own exact checks (negation parity) already reject the three reversals: "Aspirin prevents colorectal cancer in adults", "Montelukast improves symptoms", "Drug X reduces mortality in men". No model needed. The two tail cuts ("Antibiotics are effective", "Bronchiolitis is a self-limited disease") pass the exact checks and would reach the model.
- Live, Jev through the shipped `check_reworded_sentences` with card 99's pair calls, 3 repetitions, 2 Jev calls each, 6 calls, $0.00067 (`raw/adversary_r2/live_cuts.py`, `live_cuts.jsonl`): the two tail cuts and "Ribavirin can cure bronchiolitis in babies" (quote "Ribavirin") were held back 3 of 3; the faithful control ("Treatment usually focuses on symptoms, aiming to keep oxygen and fluids adequate") was approved 3 of 3.
- So the remaining holes are routing, not judgement: these sentences reach the screen only because they never reach the check.

### A2-101-05: on the code default (`CLASSIFIER_PROVIDER=guard`, which production runs) the moved sentences meet no dropped-limit pair check, but the build report says they do

- Blocking: no. Severity: minor (report accuracy; the behaviour is still a tightening over develop).
- What: card 99's pair check exists only in Jev mode (`sentence_check.check_reworded_sentences`: in guard mode one `ask_guard` call, parsed by `approved_keys`, no pairs). `docs/architecture/Model_architecture.md` line 148 says develop runs `CLASSIFIER_PROVIDER=jev` and production keeps the code default `guard`.
- The build report, "The change in the user's words": "a dropped 'usually' or 'healthy' now meets card 99's dropped-limit check like every other rewording." True on develop's deployment; false on production after release, where the moved sentences meet only the guard tier's single item judgement. The guard-tier mode was not measured on the moved sentences by the build or by this round (it is not a Jev call).
- Also in guard mode: an answer that had no candidate on develop but had a code-approved sentence now makes one guard-tier call it did not make before. The build's "0 new calls" was measured on Jev-mode traces; a guard-tier call is slower and dearer than Jev's 0.3 s.
- Suggested fix: qualify the sentence ("on develop, where the check runs on Jev"), and measure guard mode before the next release carries this change to production.
- NOT FIXED

### A2-101-06: three comments and one architecture row still describe the old acceptance rule

- Blocking: no. Severity: minor (doc drift; the builder flagged the two `graph.py` ones and left them).
- What, on the branch:
  - `core/graph.py:9671-9674`: below the 4 s floor "the answer is what code alone accepts, exactly as before the check existed". No longer true: before the check existed, code approved rewordings it could license; now below the floor every rewording is dropped.
  - `core/graph.py:9696-9697`: candidates "failed only the word check". Now they include sentences that passed it.
  - `docs/architecture/Model_architecture.md`, the "Write, sentence check" row (line 69): "for sentences that already passed every code-only check but the wording itself". Now every rewording that passes the exact checks, wording or not.
- Why it matters: the next builder reading `graph.py` will believe the below-floor answer still carries code-approved rewordings, which is the exact assumption card 101 removed.
- Suggested fix: three one-line edits in this branch.
- NOT FIXED

## What held

Each line is from my own probe, not from the builder's tests.

| Claim | How I tested it | Result |
|---|---|---|
| hb4's "For babies with severe bronchiolitis" is no longer shown on code alone | `probe_paths_r2.py` on develop and on the branch | Develop: shown, no check. Branch: a check candidate, not shown on the first pass |
| A dropped "usually" in a rewording goes to the check | same | Develop: shown, no check. Branch: candidate; the copied lead sentence still shows |
| A copy with only its letter case changed still shows with no call | same | Shown on both; the meaning is unchanged |
| A copy with punctuation changed ("high flow" for "high-flow") goes to the check | same | Candidate on both |
| Answers near their time budget lose the moved sentences | `budget_scan.py` over 120 recorded first passes with candidates (wave 3 both arms, card 101 build, fix round and round 2 live) | 120 of 120 checks ran; the smallest check budget was 10.3 s against the 4 s floor. 0 answers would have lost a moved sentence to time |
| The moved sentences add Jev calls (each one a chance for the whole check to fail closed) | `pair_calls_added.py`, the 22 recorded checks the moved sentences join | 50 Jev calls before, 52 after; 2 checks gained one pair call. No recorded check failed (0 `CHECK_RAISED` in 120) and the slowest Jev call was 1.56 s against a 3 s timeout |
| The completeness repair was not triggered by a held-back moved sentence | Round 2 live traces, per draft: code-approvable sentences and whether the check held them | The two holds (Mediterranean 1 and 5) were both in the repair draft itself; no first draft that went on to a repair had a held moved sentence. Matches the build report |
| The check, when asked, holds back what the remaining skip paths let through | `live_cuts.py`, 6 Jev calls | Held 3 of 3 for both tail cuts and the wrapped "can cure" sentence; faithful control approved 3 of 3 |
| The branch's own test files | Ran `test_check_every_rewording.py` and `test_quote_anchored_synthesis.py` | 35 passed. Reported, not relied on |

## What I did not cover

- Guard-tier mode of the check, the production default: no guard-tier call was made (the brief allowed Jev calls only). See A2-101-05.
- Code-approved clauses inside sentences that other rules then dropped: the traces log kept sentences and not the writer's quotes, so I could not replay whole first passes. Such a clause now costs a place in the check and shows nothing; on develop it also showed nothing.
- No live answers, no database, Researcher depth not exercised.
- The three widened sentences the build report found the check approving (GERD 2's dropped "transient" and "Clostridium difficile", Bronchiolitis 4's moved "usually") are misses of the check itself, not of this change; I did not re-measure them.

## Spend

| Item | Calls | Cost |
|---|---|---|
| `live_cuts.py`, 3 repetitions | 6 Jev calls | $0.00067 |
| Everything else | 0 | $0 |

## Verdict

PASS against card 101's goal contract, with one owner question and two report corrections.

- Verified by my own probes: hb4's sentence and a dropped "usually" now go to the check on the branch and not on develop; copies still show without a call; the time floor was never reached in 120 recorded checks; the change adds 2 Jev calls across 22 affected checks; the remaining skip paths are routing holes the check itself would close (6 live Jev calls).
- Read only, not probed: guard-tier behaviour; the build report's live answer counts and its hand judgements of widening.
- No blocking defect sits inside this phase's fix. A2-101-04 (a held sentence can take its neighbours) is a consequence of the change, non-blocking, with no measured frequency.
- A2-101-03 is for the owner: whether "every reworded sentence" includes a sentence that wraps a short record value in the question's words ("Ribavirin can cure bronchiolitis in babies"), which still shows with no check.
- A2-101-01 (a capitalised cut that drops "There is no evidence that" shows the reverse of its paper) is the most serious item in this report. It predates the branch and is outside the owner's decision, so it does not block card 101, but it should become its own card before the next release.
