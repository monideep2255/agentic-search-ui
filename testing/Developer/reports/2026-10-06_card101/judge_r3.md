# Card 101 round 3 judge report

Judge, round 3, fresh context, branch `fix/card101-copied-cuts`, base develop d8179c4e. Findings are appended as they are established; the checklist and verdict come last.

## Findings

### J3-101-01: a cut after a colon label shows unchecked, including a hypothesis or a myth stated as fact
- Blocking. Severity: critical. Sits inside this round's fix.
- Where: `src/system_03_search_agent/synthesis/grounding.py:932` (`_WHOLE_SENTENCE_START` counts a colon as a sentence start) used by `is_whole_record_sentence`, `grounding.py:959-991`.
- In the user's words: a paper that says "Hypothesis: aspirin prevents colorectal cancer in adults. Results: no effect was found." can be shown as "Aspirin prevents colorectal cancer in adults [1]." with no check reading it. A patient leaflet saying "Myth: vaccines cause autism." can be shown as "Vaccines cause autism [1]."
- Evidence, my probe (`run_grounding_pass` with a candidate sink, offline), each line `whole`, `grounded`, candidates, shown:
  - record "Background: Many believe a link exists. Hypothesis: aspirin prevents colorectal cancer in adults. Results: no effect was found.", writer "Aspirin prevents colorectal cancer in adults [1]." -> whole=True grounded=True candidates=0 shown ('Aspirin prevents colorectal cancer in adults [1].',)
  - record "Myth: vaccines cause autism. Fact: large studies found no link.", writer "Vaccines cause autism [1]." -> whole=True grounded=True candidates=0 shown ('Vaccines cause autism [1].',)
  - record "A common misconception is the following: antibiotics cure viral bronchiolitis.", writer "Antibiotics cure viral bronchiolitis [1]." -> whole=True candidates=0 shown ('Antibiotics cure viral bronchiolitis [1].',)
  - record "Not recommended: antibiotics for bronchiolitis. Recommended: supportive care.", writer "Antibiotics for bronchiolitis [1]." -> whole=True candidates=0, shown.
- Why it matters: the owner's rule allows only first-letter case, trailing punctuation, whitespace and surrounding quotes or brackets to differ. A label before a colon is words of the record sentence; dropping it is a cut, the same shape as the aspirin head cut this round closes ("There is no evidence that" dropped).
- Suggested fix: a colon is not a start for text the writer produced. Keep it only for code-built rows (see the suggestion in J3-101-02), or send a clause that starts after a colon to the check (it costs a check item, not the sentence).
- NOT FIXED

### J3-101-02: a cut before a semicolon shows unchecked, dropping the "however" that limits it
- Blocking. Severity: major. Sits inside this round's fix (a deliberate choice the build named, `build_r3.md` "Choices", but outside the owner's stated exceptions).
- Where: `grounding.py:932` and `grounding.py:935` (`;` is both a start and an end).
- In the user's words: a paper saying "Aspirin reduced colorectal cancer incidence; however, this was not seen in randomized trials." can be shown as "Aspirin reduced colorectal cancer incidence [1]." with no check, the limit gone.
- Evidence, my probe: record as above, writer "Aspirin reduced colorectal cancer incidence [1].", question "Does aspirin reduce colorectal cancer incidence?" -> whole=True grounded=True candidates=0 shown ('Aspirin reduced colorectal cancer incidence [1].',). The list-item shape is the same: "Contraindications: aspirin in children; ibuprofen in asthma." and writer "Aspirin in children [1]." -> whole=True, shown.
- Why it matters: the owner's exceptions are first-letter case, trailing punctuation, whitespace, quotes or brackets; a clause before "; however" is not a whole sentence. The build measured 3 of 133 recorded record sentences with a semicolon, but a rare hole that shows the opposite of a paper is the class this card exists to close.
- Suggested fix: the semicolon split is needed only by the code-built rows (structured fallback, findings tail, completeness probe: `core/graph.py:9813`, `:13214`, `:13318`), which are cut from the value by code itself and never by the writer. Pass a flag from those callers (or match each code-built row against `split_into_sentences(field_value)` directly) and drop `;` and `:` from the writer's whole-sentence test, so a writer's cut at a semicolon goes to the check.
- NOT FIXED

### J3-101-03: an abbreviation's full stop ends or starts a "whole sentence", so a cut at "e.g.", "U.S." or "yrs." shows unchecked
- Blocking. Severity: major. Sits inside this round's fix.
- Where: `grounding.py:932` and `grounding.py:935`; `is_whole_record_sentence` treats any ". " as a record sentence boundary, `grounding.py:979-990`.
- In the user's words: a paper saying "Several popular claims lack support, e.g. aspirin prevents colorectal cancer." can be shown as "Aspirin prevents colorectal cancer [1]." with no check, the paper's opposite. A paper saying "Mortality fell in the U.S. but rose sharply in every other country studied." can be shown as "Mortality fell in the U.S. [1]."
- Evidence, my probe (`run_grounding_pass` with a candidate sink):
  - record "Several popular claims lack support, e.g. aspirin prevents colorectal cancer.", writer "Aspirin prevents colorectal cancer [1].", question "Does aspirin prevent colorectal cancer?" -> grounded=True cands=[] shown ('Aspirin prevents colorectal cancer [1].',)
  - record "Mortality fell in the U.S. but rose sharply in every other country studied.", writer "Mortality fell in the U.S.[1]" -> grounded=True cands=[] shown ('Mortality fell in the U.S. [1].',); writer "Mortality fell in the U.S [1]." -> shown ('Mortality fell in the U.S [1].',)
  - record "Benefit was seen in patients aged 50 to 70 yrs. but not in older adults.", writer "Benefit was seen in patients aged 50 to 70 yrs [1]." -> grounded=True cands=[] shown.
  - Faithful cases also pass as whole ("i.e. aspirin did not reduce mortality"), so the test cannot tell them apart.
- Why it matters: the owner's rule is a whole record sentence. An abbreviation's full stop is not the end of one; card 89's own widener (`_RECORD_SENTENCE_BOUNDARY`, `grounding.py:806`) at least requires a capital after the break, and this test does not.
- Suggested fix: require what follows a start mark to open a sentence (a capital, a digit, a quote or bracket), as `_RECORD_SENTENCE_BOUNDARY` does, and require the text after an end mark to be the value's end or whitespace then such an opener; anything else goes to the check. This does not catch "U.S. Army" style breaks, so the check stays the safety, which is the fail-closed direction.
- NOT FIXED

### J3-101-04: the code-built listing now drops a record sentence that opens on "But", "And", "Then" or "Or"
- Non-blocking. Severity: minor. Sits inside this round's fix.
- Where: `_clean_claim` (`grounding.py:1319-1335`) strips a leading connective before `is_whole_record_sentence` (`grounding.py:1593-1597`) runs, so the claim no longer starts at a record sentence start; the structured fallback and the findings tail (`core/graph.py:13214`, `:13318`) pass no candidate sink, so the row is stripped.
- In the user's words: when the answer falls back to the record list, a paper's sentence "But bleeding increased in older adults." disappears from the list.
- Evidence, `build_structured_fallback_narrative` then `run_grounding_pass`, same input on both trees:
  - value "Aspirin was well tolerated. But bleeding increased in older adults." -> develop d8179c4e: ('Aspirin was well tolerated [1].', 'Bleeding increased in older adults [1].') stripped 0; branch: ('Aspirin was well tolerated [1].',) stripped 1.
  - "And bleeding did not increase.", "Then patients were followed for ten years.", "Or so the authors claimed." -> each shown on develop, each stripped on the branch.
- Why it matters: the listing is the floor when the writer's prose fails; losing a limiting sentence ("But bleeding increased") from it is a quiet loss on the fallback path, and develop showed it (with "But" dropped, itself a small rewording).
- Suggested fix: run the whole-sentence test on the segment text before `_clean_claim` strips the connective, or allow a whole match when the stripped connective sits at a record sentence start. Add a fallback row opening on "But" to `test_the_code_built_listing_still_grounds_whole`.
- NOT FIXED

### J3-101-05: the check approves a cut read alone, then a clause after it that skips the check is appended to it on screen
- Non-blocking (the trailing clause is a wrapped value, which the owner's decision keeps on today's path), but it contradicts this round's claim that joined clauses are read joined. Severity: major. Sits inside this round's fix.
- Where: `_copied_clause_candidate`, `grounding.py:1014-1053`, reads the sentence only up to the clause being asked about; a later clause in the same sentence that passes as a wrap (`grounding.py:1593-1595`) or as a whole short value is never added to what the check reads. The docstring's "whatever is shown ending at this clause is what was read" is true only for the last clause that was asked about.
- In the user's words: the check reads "Drug X reduces mortality", approves it, and the person then sees "Drug X reduces mortality [1] in children [2]." although the paper is about adults with heart failure.
- Evidence, my probe (first pass with a sink, every candidate approved, second pass):
  - records 1 "Drug X reduces mortality in adults with heart failure." and 2 population "Children", question "Does drug X reduce mortality in children?", writer "Drug X reduces mortality [1] in children [2]." -> check read ['Drug X reduces mortality']; shown after approval ('Drug X reduces mortality [1] in children [2].',)
  - records 1 "Ribavirin reduced viral load in adults with hepatitis C." and 2 title "Bronchiolitis in infants", writer "Ribavirin reduced viral load [1] in bronchiolitis in infants [2]." -> check read ['Ribavirin reduced viral load']; shown ('Ribavirin reduced viral load [1] in bronchiolitis in infants [2].',)
  - Two whole record sentences joined skip the check entirely: records "Drug X was given to all patients. Mortality fell." and "In men. Survival did not change.", writer "Mortality fell [1] in men [2]." -> cands=[] shown ('Mortality fell [1] in men [2].',). Contrived, filed for completeness.
- Why it matters: develop showed the same sentence unchecked, so this is not a regression; but the round's stated property ("two copied clauses joined go to the check") does not hold when the second clause is a wrap, and the approved item is the one that gives the cut its licence.
- Suggested fix: when a sentence sends any clause to the check, build that clause's item from the sentence up to its last marked clause, not up to this clause, so the check reads what will be shown. The build's own "Not covered" names this; it should be owned by the wrap card rather than left implicit.
- NOT FIXED

### J3-101-05: the check approves a sentence up to the cut, then a later copied clause is joined on unchecked
- Blocking. Severity: major. Sits inside this round's fix (`_copied_clause_candidate`, `grounding.py:1014-1053`, and the routing at `grounding.py:1593-1608`).
- In the user's words: a paper says "Drug X reduces mortality in adults with heart failure." The writer writes "Drug X reduces mortality [1] in children [2]." citing a record whose value is "Children". The check is asked only about "Drug X reduces mortality"; once it approves that, the reader sees "Drug X reduces mortality in children", which no check read and no record says.
- Evidence, my probe (first pass with a sink, then the pass again with every collected key approved, which is what an approving check does):
  - "Drug X reduces mortality [1] in children [2]." with record 1 as above and record 2 field `population` value "Children", question "Does drug X reduce mortality in children?" -> check read ['Drug X reduces mortality'] -> shown ('Drug X reduces mortality [1] in children [2].',)
  - "Ribavirin reduced viral load [1] in bronchiolitis in infants [2]." with record 1 "Ribavirin reduced viral load in adults with hepatitis C." and record 2 title "Bronchiolitis in infants", question "Does ribavirin help bronchiolitis in infants?" -> check read ['Ribavirin reduced viral load'] -> shown ('Ribavirin reduced viral load [1] in bronchiolitis in infants [2].',)
  - The same holds for a whole record sentence joined after an approved cut ("Aspirin lowers the risk of colorectal adenoma [1] and it does not prevent cancer in children [1]." -> check read only the first clause, both shown).
- Why it matters: the brief's intent is that "two copied clauses joined go to the check". The prefix design is sound only when nothing after the cut survives unchecked; the docstring's own claim "whatever is shown ending at this clause is what was read" is false once a later clause passes on code alone. The build lists the wrap half of this under "Not covered", but the shown sentence is a cut joined to a copied clause, which is this round's own promise, and the whole-sentence tail is not listed at all. Develop showed these sentences unchecked too, so this is not worse than develop; it is a hole in the closure this round claims.
- Suggested fix: once any clause in a sentence has gone to the check, every later clause the code would pass (whole sentence or wrap) also becomes a candidate read as the sentence up to it, so the last item asked is the whole shown sentence. Add the "in children" join to `test_two_copied_clauses_are_read_joined`.
- NOT FIXED

### J3-101-06: three of the round's stated properties are not pinned by any test
- Non-blocking. Severity: minor. Sits inside this round's fix (its tests).
- Where: `tests/system_03_search_agent/synthesis/test_copied_cuts.py`; the code at `grounding.py:951-956`, `grounding.py:1047`, `grounding.py:1599`.
- In the user's words: a later edit could quietly let the check read a joined claim without the first record's sentence, let "Yes, ..." cuts reach the check, or let a copy with different capitals mid-sentence count as the record's own words, and every test would stay green.
- Evidence, my mutations, each applied to `grounding.py`, then `pytest -m "not integration"` over `tests/system_03_search_agent/synthesis/` plus `core/test_write_findings_tail.py`, `core/test_write_grounding_premise.py` and `core/test_graph.py`, then restored with `git checkout --` (git status clean of tracked changes after each):
  - M3, the joined candidate keeps only the last clause's record text (`quotes = tuple(dict.fromkeys(spans[-1:]))`): 863 passed, 0 failed. `test_two_copied_clauses_are_read_joined` uses one record for both clauses, so it cannot see this.
  - M4, a cut opening on a bare verdict is no longer held by code (`held_by_code = False`): 863 passed, 0 failed.
  - M5, the whole-sentence test compares everything after the first letter case-insensitively (`claim[1:].lower() == record[1:].lower()`), contradicting the docstring's "no lowercasing": 863 passed, 0 failed.
  - For contrast, M2 (any start position is whole whatever follows) turned 9 arms red, so the core arms do bite.
- Suggested fix: a joined case across two records asserting both record sentences are in the candidate's quotes; a "Yes, <cut>" case asserting no candidate and nothing shown; a mid-sentence case change asserting a candidate.
- NOT FIXED

### J3-101-07: gate 03 fails on the round 3 adversary's untracked scripts in this worktree
- Non-blocking for the branch as committed. Severity: minor (process).
- Where: `testing/Developer/reports/2026-10-06_card101/raw/adversary_r3/` (untracked: `cm4_detail.py`, `crowding.py`, `crowding_synthetic.py`, `crowding_synthetic_n.py`, `replay_cost.py`, `replay_traces.py`).
- In the user's words: nothing a reader sees; if these scripts are committed as they are, CI's lint gate goes red and the pull request cannot merge.
- Evidence: `gate03_lint.sh` (`ruff check`, whole worktree) -> "Found 14 errors.", all 14 in those six files; `ruff check --extend-exclude testing/Developer/reports/2026-10-06_card101/raw/adversary_r3` -> "All checks passed!" exit 0. Gate 02 passes (exit 0).
- Suggested fix: run `ruff check --fix` and fix the rest on those scripts before the lead stages them, or leave them out of the commit.
- NOT FIXED

### Note added to J3-101-01, from mutation M1
Removing the colon from `_WHOLE_SENTENCE_START` turns exactly one existing arm red: `test_pubmed_abstract_grounding.py::test_a_verbatim_abstract_excerpt_grounds_and_cites_its_own_paper`, which copies "pathogenic BRCA1 variants abolish homologous recombination in this cohort" from after "Results:" and expects it to ground with no check. So the colon start buys the structured-abstract label case and nothing else the suite measures. Without it, that copy becomes a check item (approved live in round 3's measurements for faithful cuts, 12 of 12) rather than lost; with it, "Hypothesis:" and "Myth:" cuts show unchecked. A word list of safe labels would break the owner's "no hardcoded decisions" rule, so the check is the place to decide.

### J3-101-08: the sentence check's caller still describes its items as reworded sentences that failed only the word check
- Non-blocking. Severity: minor (doc drift, continues A2-101-06).
- Where: `src/system_03_search_agent/core/graph.py:9695-9697` (`_ground_with_sentence_check` step 1: "collecting every reworded sentence that passed all of code's exact checks ... and failed only the word check") and `graph.py:9670-9673` ("the answer is what code alone accepts, exactly as before the check existed"). Not touched by this branch.
- In the user's words: none on screen. The next builder reading the caller will not know copied cuts now ride the same call and are dropped below the 4 s floor.
- Evidence: `git diff origin/develop...HEAD -- src/system_03_search_agent/core/graph.py` is empty; my probe shows below the floor (budget 3.9 s) no call is made and the aspirin cut and the joined clauses are not shown, only the whole sentence is.
- Suggested fix: two comment lines naming copied cuts as check items and saying below the floor they are not shown.
- NOT FIXED

## Checklist

| Item | Verdict | Evidence, own probe or read |
|---|---|---|
| 1. Whole-sentence test | FAIL | Own probes (`is_whole_record_sentence` and `run_grounding_pass` with a sink). Shows unchecked: a colon label cut (J3-101-01, `grounding.py:932`), a semicolon cut (J3-101-02, `grounding.py:932`, `:935`), an abbreviation cut at "e.g.", "U.S." or "yrs." (J3-101-03). Held correctly: a value with no sentence punctuation cut short (whole=False, a candidate), a bulleted list item (whole=False), a pipe table row (whole=False), a mid-sentence case change (whole=False), a quoted sentence inside a longer one (whole=False, a candidate), a "Yes, ..." opener (whole=False and held by code). A quote spanning two record sentences cannot be one clause: the narrative splitter (`grounding.py:57`) ends the clause at the first ". ". Whole sentences in brackets or quotes and a whole short value pass, as intended |
| 2. The rendered-row exception | PASS | Own probe: the row matches only at equal length after the first letter (`grounding.py:976-977`, `:951-956`). "Publication pubmed:1, abstract: There is no evidence" whole=False strict=False; "Disease name: Familial cancer" whole=False strict=False; a label glued to a cut ("Abstract: aspirin prevents ...") whole=False strict=False. A cut cannot match a row because the row carries the whole value. The widened text the check reads (`_copied_record_span`, `grounding.py:1001-1011`) never decides a pass on its own. Found no way through |
| 3. Fail closed | PASS for the listed failures; time and cost on real answers read only | Own probe of `_ground_with_sentence_check` with a fake `_dispatch_tier_call` on "Treatment is usually symptomatic [1]. Aspirin prevents colorectal cancer in adults [1]. Drug X reduces mortality [1] in men [1].": approves none, unreadable reply, `HarnessCallError`, cost cap, budget 3.9 s (0 calls), out-of-range and string indices: each shows only the whole sentence. Approves all: 1 call, 3 sentences. One call carries every cut. An unexpected `RuntimeError` or bare `TimeoutError` from dispatch propagates out (`graph.py:9746` catches three classes); this predates the branch, and `harness.enforce_timeout` turns timeouts into `HarnessCallError`. The build's live seconds and spend ($0.124, 0 to 2 new calls in 66 answers) I read and did not reproduce (no live calls) |
| 4. No regression | PASS with one minor loss (J3-101-04) | Own differential probe, the same script on develop d8179c4e (`git archive`) and on the branch: gene answers (BRCA1 with two diseases, the identifier form, ClinVar significance, the code-built listing), isolate answers, paper links ("Publication pmid 111 is included"), whole abstract copies, a follow-up, and every structured fallback give identical output. The only difference is the intended one (an abstract cut becomes a candidate). Wrapped names are pinned by `test_a_wrapped_record_value_keeps_todays_path_for_now` (the build's M6 turned it red; I did not re-run that mutation). Researcher and Plain language share these passes; the depth switch itself was not exercised live |
| 5. Tests | PASS, with gaps (J3-101-06) | Own run: `tests/system_03_search_agent/synthesis/` plus all of `tests/system_03_search_agent/core/` -> 1966 passed, 66 skipped, 1 deselected, 1 xfailed, 0 failed. Mutations: M1, colon not a start -> 1 red (`test_pubmed_abstract_grounding`); M2, end not required -> 9 red; M3, joined quotes truncated -> 0 red; M4, verdict hold off -> 0 red; M5, case-insensitive whole test -> 0 red. Each restored with `git checkout --`; `git status --short -- src` empty after each |
| 6. Gates and leak scan | Gate 02 PASS; gate 03 PASS on the committed tree, FAIL on the worktree as it stands (J3-101-07); leak scan PASS | `gate02_import_order.sh` exit 0. `gate03_lint.sh` "Found 14 errors", all in the untracked `raw/adversary_r3/` scripts; with that folder excluded "All checks passed!". `check_public_leaks.py --base origin/develop`: "0 finding(s)", "PASS" |

## What I verified with my own probes, and what I only read

- Own probes: every row of checklist items 1, 2, 4 and 5; fail-closed behaviour for seven failure shapes; the join hole (J3-101-05) through a first pass and an approving second pass; the develop comparison; gates 02 and 03; the leak scan.
- Read only: the build's live numbers (15 of 15 attacks held, 12 of 12 faithful cuts kept, six live answers, timing, spend), the offline rescan of 66 recorded answers (its traces are outside the repository), the build's M6 on the wrap pin, and the DECISIONS.md row's account of 40 failing tests when wraps go to the check.

## Not covered

- No live model call: whether the guard tier (production's code default, A2-101-05) holds the attack cuts and keeps faithful ones is not measured by anyone.
- Time on real answers: not reproduced. My probes only show one check call carries all cuts and none is made below the 4 s floor.
- Researcher and Plain language end to end through `write_node`. I covered the grounding passes they share, not the depth switch.
- Answers with a wrapped name that later joins a check-approved cut, beyond J3-101-05's three constructed cases.
- Doc drift outside `graph.py` (architecture rows) since round 2.

## Verdict

FAIL. Blocking items, all inside this round's fix (the review loop's stop condition):

- J3-101-01: a cut after a colon label ("Hypothesis:", "Myth:") shows unchecked, so a reader can see a hypothesis or a myth stated as the paper's finding.
- J3-101-02: a cut before "; however" shows unchecked, dropping the limit.
- J3-101-03: a cut at an abbreviation's full stop ("e.g.", "U.S.", "yrs.") shows unchecked, including the paper's opposite.
- J3-101-05: the check approves a sentence up to a cut, and a later copied clause (a wrapped value or a whole sentence) is joined on unchecked.
