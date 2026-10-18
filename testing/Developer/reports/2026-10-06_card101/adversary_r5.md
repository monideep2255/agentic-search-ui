# Card 101 round 5: adversary report

Fresh-context adversary, branch fix/card101-copied-cuts at 41697cd9 (pull request #204), base develop 2182aff3. Findings are appended as they are established.

## Findings

Probes run against this worktree and a `git worktree add --detach` copy of develop in the session scratchpad (`adv101r5/`), through the real `run_grounding_pass` and `core.graph._ground_with_sentence_check`. Harness: the first pass with a candidate sink ("none"), the same pass again with every collected item approved ("all"), and every subset of the items ("partial"). Live calls, where made, go through the shipped `check_reworded_sentences` only.

### A5-101-01: the whole-sentence drop stops at the narrative splitter, so a writer sentence split at "e.g.", "i.e." or a semicolon still shows its head when its limiting tail is held
- Severity: minor. Unsure whether the owner reads "sentence" as the writer's or the splitter's.
- Regression against develop: no. Develop shows the same head with no check and drops the tail silently.
- Inside round 5's claim ("no part of that sentence shows"): yes, under the writer's reading of a sentence.
- What: `run_grounding_pass` walks `_split_sentences` units, which break at `[.;?!]` plus whitespace, so "e.g. ", "i.e. " and "; " split one writer sentence into two units. The held-copy drop (`held_for_check`) is per unit. When the head unit's cut is approved and the tail unit's cut (the record's limit) is held, the head shows alone.
- Reproduction (`p4_abbr.py`, branch, record [1] "Ribavirin is first-line care for bronchiolitis in infants with severe heart disease, but routine use is not recommended."):
  - writer "Ribavirin is first-line care for bronchiolitis in infants with severe heart disease [1], e.g. routine use is not recommended [1]." Items: the head cut and "routine use is not recommended", both with the whole record sentence as quote. Head approved, tail held: shown `['Ribavirin is first-line care for bronchiolitis in infants with severe heart disease [1].']`. Same with "i.e." and with "; but routine use ...".
  - record [2] "Drug X is safe in children; however, it caused deaths in infants.", writer the same words with a marker on each half. Head approved alone: shown `['Drug X is safe in children [1].']`.
  - Develop, both: the head shown with no check at all; the tail dropped.
- Why it matters: the reader sees the record's claim without the limit the writer copied beside it. The check is shown the whole record sentence as the quote, so this is only a loss when the check approves the head on its own; whether it does is a live question (see the live section).
- NOT FIXED

### A5-101-02: a held reworded tail after an approved copied cut still leaves the cut on screen
- Severity: minor. Filed as a boundary of the rule, not a defect against the brief, which says "copied cut".
- Regression against develop: no. Develop shows the same head.
- What: the drop fires on `held_for_check`, which only copied clauses populate. A reworded clause (a quoted clause with words outside its record) that the check holds is end-stripped as on develop, so the approved cut before it shows alone.
- Reproduction (`p4_abbr.py`, branch): writer 'Aspirin prevents colorectal cancer in adults [4], and infants were recruited at six sites [3: "142 infants were enrolled at six sites"].', records [4] "There is no evidence that aspirin prevents colorectal cancer in adults." and [3] "Methods: 142 infants were enrolled at six sites over three winters.". Items: the cut, and the reworded clause alone (not joined). Cut approved, reworded held: shown `['Aspirin prevents colorectal cancer in adults [1].']`.
- Why it matters: the owner's words were "for any reason" about a copied cut; this is a different clause type, but the reader's experience (half the writer's sentence) is the same as the shape round 5 set out to remove. Noted so the owner can decide whether the rule should cover it.
- NOT FIXED

Progress note (written as established, before the live section):

- Held: the 600-character edges (`p3_edges.py`): a joined item of 599 and 600 characters is sent and, approved, shows its sentence; 601 is not sent and the sentence shows nothing under "all". A quote of 599 and 600 characters is sent, 601 is not and the sentence shows nothing. Multibyte text (ö, β) counts by code point on both sides of the cap, consistently.
- Held: guard mode through the real `_ground_with_sentence_check` with the dispatch stubbed (`p5_guard.py`): RuntimeError, TimeoutError, asyncio.TimeoutError, KeyError, AttributeError and a broken reply object all approve nothing and the azithromycin sentence shows no part; CancelledError and KeyboardInterrupt propagate; "supported": [1] shows the whole sentence with its limit; an item number never sent, an empty list and a 3.9 s budget all show only the unchecked sentence.
- Held: the code-built listing (`p6_listing.py`, 19,778 distinct random values, seed 7, ". , ", "? : ", "; : " among the separators): branch and develop show the same rows in every case; 0 rows gained, 0 lost. A4-101-05 is closed by my own probe.
- Held: a dropped sentence contributes no claim (`claims` 0 in every dropped case above), so the trust line and the Sources list, which are built from `claims`, cannot count it. Read, not run: `trust.answer_trust_line` and `trust_for_claims` take `claims` only.

Live addition to A5-101-01 (`p7_live.py`, the shipped `check_reworded_sentences` through `core.graph._ground_with_sentence_check`, 3 runs each in Jev mode and with the guard tier, $0.00085 in all):

- "e.g." split: the head item "Ribavirin is first-line care for bronchiolitis in infants with severe heart disease" was approved 5 of 6 (Jev 3 of 3, guard 2 of 3) against the quote that carries "but routine use is not recommended"; in every one of those 5 runs the shown answer was the head alone, `['Ribavirin is first-line care for bronchiolitis in infants with severe heart disease [1].']`, and the tail unit "routine use is not recommended", approved too, did not reach the page (it opens lowercase in its own unit and is dropped by a later rule). The reader sees the record's claim with the limit the writer copied beside it gone. Develop shows the same head with no check.
- semicolon whole copy: "Drug X is safe in children" was held 6 of 6 and "however, it caused deaths in infants" approved 6 of 6; shown `[]` in all 6 runs (the approved tail unit opens lowercase and is dropped). Develop shows "Drug X is safe in children [1]." with no check. The branch is safer here.

### A5-101-03: a faithful whole copy of a record sentence is dropped when the record text around it runs past 600 characters, where develop shows it
- Severity: minor. A true sentence lost, not a false one shown.
- Regression against develop: yes, for this shape: develop shows the sentence, the branch shows nothing of it. Inside round 5's fix for A4-101-07 (`record_sentence_run` returning None).
- What: `_RECORD_SENTENCE_BOUNDARY` needs a capital, quote mark or bracket after the stop, so a record whose next sentences open on a digit, "p" or a lowercase gene name is one run. `is_whole_record_sentence` compares with that run, so the writer's faithful copy of its first sentence is a cut; `_copied_record_span` then finds the run longer than 600 characters, returns None, and round 5 holds the clause and drops the sentence. The reverse cut from the same run is held too, which is the fix's point.
- Reproduction (`p9_longrun.py`, record [1] the 618-character run beginning "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. 142 infants were enrolled ..."):
  - writer "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis [1]. Treatment is supportive [2]." Branch, none and all: `['Treatment is supportive [1].']`. Develop: both sentences.
  - writer "Azithromycin shortened the illness in infants with bronchiolitis [1]." Branch: `[]` under none and all, no item built. Develop: shown.
- Frequency: none of the recorded record values has such a run (my replay, `long_runs` 0 of the values behind 69 and then all drafts; the builder measured 0 of 55 distinct values). Trial abstracts whose sentences open on counts or p values are where it lives.
- Why it matters: from the user's chair, the paper's negative finding, copied word for word, disappears, while develop showed it. The trade is the builder's stated choice ("holding is the fail-closed reading"); the owner should know its cost is a true sentence, not only a false one.
- NOT FIXED

## What held, by my own probes

| Claim | How I tested it | Result |
|---|---|---|
| A held copied piece drops its whole sentence | `p1.py`, `p2.py`, `p9_longrun.py`, both trees: a name then a cut, a title then the limiting cut, two cuts, a cut then a whole copy, a whole copy then a cut, a reworded head then a cut, a verdict-opener cut, a cut after framing; none, all and every partial approval | On the branch every such sentence shows whole (every item approved) or not at all; no "Ribavirin [1].", no title without its limit. Develop shows all of them unchecked. The verdict-opener cut (held by code) drops its sentence too |
| Items past 600 characters are not sent or approved | `p3_edges.py`: joined item at 599, 600, 601 characters; quote at 599, 600, 601; multibyte text | 599 and 600 sent and, approved, shown; 601 not sent and nothing of the sentence shown under "all" |
| A cut with no record run is held, never sent as its own quote | `p9_longrun.py`, the 618-character run and a 715-character single sentence | No item built; nothing shown under none or all. Develop shows the reversal |
| The listing keeps develop's rows | `p6_listing.py`, 19,778 distinct random values on both trees, separators ". , ", "? : ", "; : " included | 0 rows gained, 0 lost, 0 errors |
| Guard mode: an unexpected failure approves nothing | `p5_guard.py`, `p10_cap.py` through the real `_ground_with_sentence_check` with `_dispatch_tier_call` stubbed | RuntimeError, TimeoutError, asyncio.TimeoutError, KeyError, AttributeError, a broken reply object, the cost cap and HarnessCallError all show only the unchecked sentence; CancelledError and KeyboardInterrupt propagate; "supported": [1] shows the sentence with its limit; a number never sent, an empty list and a 3.9 s budget approve nothing |
| Trust signals cannot count a dropped sentence | `claims` is 0 in every dropped case above; `drop_record_restatements` carries claims per kept sentence (read) | A dropped sentence leaves no claim for the trust line, the Sources list or the restatement drop to count |
| Recorded drafts | `p8_replay.py`, my own script, the 69 recorded drafts in the repository (the builder's 168 include files not in either checkout), none, all and every partial set | 0 sentences the branch shows that develop does not; 0 drafts emptied; 3 develop sentences dropped, all three the cuts themselves, the same as round 4; 5 items, 0 past the cap, 2 writer sentences over 600 characters with no item on them |
| A draft emptied by the rule refuses | `p9_longrun.py`, one cut sentence with `core_ask_required=True` | none: refused; all: shown. Develop shows it unchecked. By design, and none of the recorded drafts is emptied |

## Not covered

- The remaining 99 recorded drafts the builder replayed (`live/`, `out/`), which are not in the repository.
- Live answers end to end, Researcher and Plain language depths, gene questions.
- A draft with more than 30 check items or a Jev state past 30,000 characters: items past either cap are not sent, so their sentences drop (read, not run).
- The named residuals A4-101-01, A4-101-02, A4-101-06, J4-101-03 and J4-101-04 were not re-attacked beyond A5-101-01, which is their splitter mechanism seen from the round 5 rule.

## Spend

| Item | Calls | Cost |
|---|---|---|
| `p7_live.py`, Jev mode, 3 runs of 2 cases | item and pair calls | $0.00073 |
| `p7_live.py`, guard tier, 3 runs of 2 cases | 6 checks | $0.00012 |
| Everything else | 0 | $0 |
| Total | | $0.00085 |

## Verdict

PASS against round 5's claim and the merge bar. Every reproduction from A4-101-03, 04, 05 and 07 and J4-101-08 fails closed on the branch under my own probes, with no fragment and no approved-but-unread text, and the listing is byte for byte develop's. Nothing I found makes the branch show a sentence develop does not show.

Findings, none blocking:

- A5-101-01, minor, not a regression: the whole-sentence drop is per splitter unit, so a writer sentence split at "e.g.", "i.e." or ";" can still show its head alone; live, the check approved the "e.g." head 5 of 6 and the page showed it without its limit. Develop shows the same head unchecked.
- A5-101-02, minor, not a regression: a held reworded tail after an approved cut leaves the cut on screen, as on develop. A boundary of the rule's words, filed for the owner.
- A5-101-03, minor, a regression for a true sentence: a faithful copy of a negated record sentence is dropped when its record run is over 600 characters, where develop shows it. Inside round 5's fix for A4-101-07, and the builder's stated trade.

Worse than develop: no. The one loss against develop (A5-101-03) drops a true sentence; no false or widened sentence is shown that develop does not show.

Verified by my own probes: every shown or held output above, offline on both trees; the 600-character edges; the listing fuzz; the guard-mode failure modes through the real caller; the 69-draft replay; the 12 live runs. Read only: `trust.answer_trust_line`, `drop_record_restatements`, the Jev state and candidate caps, the builder's mutation and gate results.
