# Card 101: where a record sentence ends

Designer, 2026-10-15, branch `fix/card101-record-sentence-end` at develop 7626fe85. Design only: no source file changed, no model called. Offline probes ran the tag's replay scripts and a standalone prototype of the recommended boundary on every reproduction the 8 October judge and adversary gave. Paths are relative to `<repo-root>` unless stated.

The card's open part: its last three slices (tag `parked/card101-last-slices-2026-10-08`) were parked after both reviews found the new sentence splitter worse than develop. This document says what those slices were for, why they were worse, and designs where a record sentence ends so that the check never reads a quote without its negation, hedge or qualifier, and no sentence develop shows is dropped.

## Table of contents

- [What the three slices were meant to fix](#what-the-three-slices-were-meant-to-fix)
- [Why the 8 October splitter was worse than develop](#why-the-8-october-splitter-was-worse-than-develop)
- [The bar](#the-bar)
- [Four principles any design must keep](#four-principles-any-design-must-keep)
- [Three designs compared](#three-designs-compared)
- [The recommended design: graded breaks](#the-recommended-design-graded-breaks)
- [Prototype results on the reviews' reproductions](#prototype-results-on-the-reviews-reproductions)
- [Residuals, named](#residuals-named)
- [The replay bench](#the-replay-bench)
- [Build steps as slices](#build-steps-as-slices)
- [Live check](#live-check)
- [Risks and how each is prevented](#risks-and-how-each-is-prevented)
- [The owner trade-off](#the-owner-trade-off)

## What the three slices were meant to fix

In the person's words: a paper that says a thing is not so must never be cited as saying it is so. Three ways that still happened on develop at #204 (`testing/Developer/reports/2026-10-08_overnight/card101_diagnosis.md`):

| Slice | What the paper says | What the answer showed, cited to it | Why code let it through |
|---|---|---|---|
| J5-101-01 | "There was no evidence that azithromycin shortened the illness in infants", in an abstract whose sentences run past 600 characters | "Azithromycin shortened the illness", when the writer quoted its own copied words | The check was shown the writer's quote as the record text, since the widener falls back to the quote when the record sentence is longer than the check reads (`widen_to_record_sentences`, card 89) |
| A4-101-01 | "No isolates of S. Typhimurium carried the gene" | "Typhimurium carried the gene", with no check | The record boundary (`_RECORD_SENTENCE_BOUNDARY`: full stop, space, capital) breaks after "S.", so the tail counts as a whole record sentence and shows unchecked. The writer's own splitter cut the same copy at "S." and stripped the head as unmarked |
| A4-101-02 | 'Advertisers claimed that "this drug is a miracle. Drug X cures cancer. It is safe." Regulators found every claim false.' | "Drug X cures cancer", with no check | A sentence inside a quotation or bracket starts after a full stop and a capital and ends at the next, so it reads as whole; nothing asks whether a mark is still open around it |

Each is the same defect: the words the check reads, or the words that skip the check, are cut where the paper's sentence is not cut. Card 101's promise, "a sentence the writer reworded never reaches the screen without passing the sentence check", needs one more clause: the check must read the paper's whole sentence, and "whole" must mean what the paper means.

## Why the 8 October splitter was worse than develop

The slices moved the record boundary itself: a break after a token shaped like an abbreviation was removed (`_ends_on_abbreviation`), and so was every break while a quote mark or bracket was open (`_still_open`). Both only ever join units, so the builder reasoned that nothing could be added. Every critical finding came from what a longer unit does downstream, not from the join itself.

| Finding | What a person would see | Mechanism, traced | Develop |
|---|---|---|---|
| J-101N-01, A-101N-07 (critical) | A reworded sentence cited to a paper that found no evidence of it, with the check shown only the writer's quote | One stray `(`, `[`, `“` or an odd `"` anywhere early in an abstract leaves a mark open to the value's end, so every later break is removed and the rest of the record is one unit. The unit passes 600 characters, `record_sentence_run` returns None, and the reworded path (`run_grounding_pass`, `widen_to_record_sentences(pair_quote, ...)`) falls back to the bare writer quote. The negation is no longer in what the check reads. Slice 1 closed this fallback on the quoted copied branch only | Develop's units are short, so the same quote was widened to the sentence with "There was no evidence that" |
| J-101N-04, A-101N-08 (critical for the reworded half) | The same reversal, with no stray mark at all | The one-capital shape counts "vitamin D.", "hepatitis B.", "arm A.", "phase I." as abbreviations. An abstract that names its arms by letter, or repeats "hepatitis B.", chains into one unit past 600 characters and reaches the same fallback | Fourteen units, the quote widened to its sentence |
| J-101N-02, A-101N-06, A-101N-13 (major) | A word-for-word copy of the paper, which develop showed, vanishes with no check asked, the paper's own denial included | The same open-mark join makes a whole copy a cut (no unit equals it), its run is the rest of the record, past 600, so `_copied_record_span` is None and the clause is held without being sent. A 654-character abstract with one unclosed mark is enough | Shown, 11 units |
| A-101N-05, J-101N-04 (major) | A true whole copy becomes a check item, and is lost if the check holds it or cannot run | Every join turns a whole copy into a cut below 600 characters too: an extra item, and a sentence that now depends on the check's approval | Shown with no item |
| A-101N-01 (major) | The quoted claim shows unchecked again | Straight double quotes were counted by parity, so an inch mark (`5"`) earlier in the abstract makes the quotation's opening mark read as a closing one | Same as develop, but the slice claimed to close it |
| J-101N-05, A-101N-02, A-101N-03, A-101N-04 (major) | A claim quoted in single, curly single, guillemet, German or Swedish quotes still shows unchecked; a German closing `“` opens a unit that never closes and drops every later copy | `_OPENING_MARKS` enumerated three pairs. A list, where the ticket asked for a category | Same hole as develop for the first; the drop is new |
| J-101N-06, A-101N-15 (major) | "Jude developed the infection", "Placebo-treated patients improved by 20%", cited to papers saying the opposite | The shape covers one capital or a dotted token; "St.", "vs.", "Fig.", "Dr." still break, and the tail is a whole record sentence | Same as develop |
| A-101N-09, A-101N-11 (minor) | Units opening on a stray initial | "Dr. A. Smith": the break after "Dr." stays, the one after "A." goes, so a unit starts "A. Smith." | Develop splits "A." and "Smith." apart too |
| J-101N-03, A-101N-14 (minor, evidence) | The build's "0 faithful sentences dropped" | The corpora carry no break the new code removes (`exposure.txt`: 0 of 77), so develop and every slice print the same counts; the replay passes no writer quotes, so the reworded path was never measured | |
| A-101N-10 (major, pre-existing) | The check judges an infant claim against an adult sentence and never sees the denial | On the copied-cut path a valid writer quote wins over the clause's own words, and `record_sentence_run` takes the first unit containing the quote | Same |
| J-101N-07, A-101N-12 (minor, pre-existing) | The fallback record list prints "Typhimurium carried the blaCTX-M gene [1]." as a row | `findings.build_structured_fallback_narrative` splits a value with the writer's splitter, outside the card's fence | Same |

In one sentence: the slices lengthened units, and a longer unit falls off two cliffs develop already had, the 600-character fallback to a bare quote on the reworded path and the 600-character hold on the copied path. The slices' own rules then added a parity flip and an enumerated list. Nothing in the reviews says the idea (do not break inside an abbreviation or a quotation) is wrong; the implementation made the unit the thing that changed, and the unit's length is what everything downstream keys on.

## The bar

| Half | What it means | How it is measured |
|---|---|---|
| No quote through without its negation, hedge or qualifier | The check never reads a writer's quote, or a cut, as the record text behind a sentence; it reads the paper's whole sentence or unit around it, or the sentence is held | On the reproduction set, every case gives the check a run that contains the paper's negation or attribution, or holds; no case gives a bare quote. On the trace replay, nothing shown that develop does not show |
| No sentence develop shows is dropped | A copy or rewording develop shows with no check still shows with no check; a sentence develop sends to the check is still sent, with a run at least as wide | On the trace replay and the repository corpus, 0 develop sentences dropped under "approves none" and "approves all"; on the reproduction set, every later whole copy after a stray mark still shows |

The two halves can only conflict in one place: a record unit develop already reads as longer than 600 characters, where develop sends a bare quote and the design holds. That is the owner trade-off at the end of this document, measured at 0 of 53 real record values.

## Four principles any design must keep

Drawn from the mechanisms above. The rejected option fails at least one; the recommended one keeps all four.

1. A unit never grows. Develop's units stay the units, so no join can push a run past 600 characters, and whole copies develop shows stay whole copies.
2. No bare quote, ever. When the run of record text the check should read cannot be given to it, the sentence is held. The copied path has done this since round 5 (A4-101-07); the reworded path still falls back. A boundary change that keeps the fallback is not safe, whatever the boundary.
3. Every rule reads the record's own characters or the writer's own reply. Unicode categories, token shapes and adjacency are structure; a list of abbreviations or of quote marks is not. "Would this still work for a phrasing nobody listed?" (`.claude/rules/decide-from-the-users-chair.md`, the no-hardcoded-decisions rule).
4. Ambiguity falls back to develop's reading, never past it. An opener the record never closes, a quote style whose marks do not pair, a two-letter word before a full stop: the record is read as develop reads it. Worse than develop is impossible by construction; the residual is develop's residual.

## Three designs compared

| | 1. Develop's splitter plus a narrow rule for the specific cases | 2. A structural boundary from the record's own punctuation, graded breaks | 3. Ask the sentence check whether the quoted unit keeps its qualifiers |
|---|---|---|---|
| What it is | The parked code: remove the break after an abbreviation-shaped token and every break inside an open mark, so units join. Add the fallback fix and a reach limit on open marks | Keep develop's units exactly. Grade each break hard, soft after an abbreviation shape, or soft inside a balanced mark. A copy is whole only after a hard break. The run the check reads is glued across soft breaks, bounded. No fallback to a bare quote. Marks by Unicode category, straight quotes by their shape, an unmatched opener ignored. The writer's own reply tells a cut the shape cannot see | Leave the boundary; send the check a wider window (the sentence plus its neighbours, or the record) and ask whether the sentence keeps every qualifier the window carries |
| Quote without its negation | Closed only with the fallback fix (principle 2). Chains still make long units, so the fix turns reversals into holds | Closed: the run always includes the glued neighbour or the quoted unit, or the sentence is held. Verified on every reproduction below | Not closed for unchecked whole copies, which never reach the check; for reworded sentences card 89's design measured the wider window approving 2 of 6 additions (`testing/Developer/reports/2026-10-05_sentence_check/design.md`, jev_context) |
| Sentences develop shows dropped | Yes: every faithful whole copy after a one-letter sentence end or inside a long quotation becomes a cut; past 600 it is held unsent (J-101N-02, A-101N-13, J-101N-04). A reach limit needs a number nobody can justify | None on the corpora and the reproduction set: units are develop's, so a whole copy is whole unless the break before it is soft, and then it is sent with a two-unit run far below 600 | Sending every copy to the check holds gene answers (round 3: every gene sentence held live) |
| No-hardcoded-decisions rule | A shape, not a list, for abbreviations; marks were a list | Shapes and Unicode categories only; the one judgement, whether the sentence says more than the unit, stays with the check | The decision sits with a model, which the rule prefers, but the boundary is a structural fact, and a model cannot read what it is not shown (`LEARNINGS.md`, 2026-09-24: a per-unit check certifies units) |
| Cost and latency | None | None: one pass over the value for marks, the widener's loop unchanged; a two-unit run instead of one for a copy after a soft break | One wider state per item, and more approvals of widened claims |
| Verdict | Rejected: principle 1 broken, and the review budget showed where that leads | Recommended | Rejected as the boundary; the existing check and pair check remain the decision-maker on what the glued run supports |

Option 2 is option 1 turned inside out: the same two facts (an abbreviation shape, an open mark) are read, but they grade a break instead of removing it. The unit, which everything downstream keys on, stays develop's. Option 3 answers a different question; the owner already chose the sentence-wide window on 2026-10-05 and the pair check on 2026-10-06, and both stay as they are.

## The recommended design: graded breaks

Everything lives in `src/system_03_search_agent/synthesis/grounding.py` beside the code it replaces. Names are proposals.

| Piece | Rule | Replaces |
|---|---|---|
| `_RECORD_SENTENCE_BOUNDARY` | Unchanged: full stop, question or exclamation mark, whitespace, then a capital, a double quote or an opening bracket | Itself |
| `_record_breaks(value) -> list[(end, start, grade)]` | Every develop break, graded: `mark` when it sits strictly inside a balanced quotation or bracket (`_mark_spans`); else `abbrev` when the token before it is one capital letter or letters with an inner full stop (`_ends_on_abbreviation`, the tag's shape, kept); else `hard` | The tag's `_record_sentence_breaks`, which removed breaks |
| `_mark_spans(value)` | One pass over the value. An opener is a character of Unicode category Ps or Pi, or a straight `"` or `'` in opening shape (after whitespace or an opener, before a non-space). A closer is Pe or Pf, or a straight quote in closing shape (after a non-space, before whitespace, a closer or punctuation). A closer pairs with the nearest open mark of its class (bracket or quote); a closer with nothing open pairs with nothing. An opener still open at the value's end is ignored and the value re-read without it, so an unclosed mark holds nothing | The tag's `_open_marks`, `_still_open`, `_OPENING_MARKS` |
| `_record_units(value) -> list[(text, grade of the break before)]`; `_record_sentences` keeps returning the texts | Develop's units, each with the grade of the break before it (`start` for the first) | `_record_sentences` |
| `is_whole_record_sentence` | A copy is whole when it equals a unit, as today, and the break before that unit is `hard` or `start`. A unit after a soft break is a cut: "Typhimurium carried the gene" after "S.", "Drug X cures cancer" inside a quotation. The head before a soft break stays whole, as develop (the danger is the tail) | The equality test alone |
| `record_sentence_run(quote, record)` | The smallest run of develop units containing the quote, as today; then glued: backward across every `mark` break to the mark's opening unit, and across one `abbrev` break; forward likewise. Longer than 600 characters, None. An abbreviation joins only its two neighbours, so a "hepatitis B." abstract never chains | The same loop with no glue |
| The reworded path in `run_grounding_pass` (about line 1674) | `record_sentence_run` in place of `widen_to_record_sentences`; None for any pair means the sentence is held, not sent, exactly as the copied path since round 5 | The fallback to the bare writer quote |
| `_copied_clause_candidate`, quoted branch (about line 1130) | The tag's slice 1, kept: `record_sentence_run`, None means held | `widen_to_record_sentences` |
| `widen_to_record_sentences` | Deleted once both callers use `record_sentence_run`; the tests that pin it move to `record_sentence_run` | Itself |
| The adjacency rule, in the sentence loop of `run_grounding_pass` (line 1507 onward) | A copied clause that `is_whole_record_sentence` calls whole is still a cut when the reply sentence just before it carried no marker, was stripped, and its words joined to this copy with a space are one contiguous span of the same record value (`normalize`, as `_starts_inside_record_sentence` matches). The writer copied one paper sentence and the writer's splitter cut it at "St.", "vs." or "Dr."; the record says so. The cut's run is `record_sentence_run` of the joined text, so the check reads "No children treated at St. Jude developed the infection." | Nothing: develop shows the tail |
| The clause's own run first (A-101N-10), copied path | In `_copied_clause_candidate`, when the clause's own words are in the record (`ground_claim`), its span is `_copied_record_span(claim)`; the writer's quote is used only when they are not. The check then reads the sentence the cut dropped a clause from | A valid quote winning over the clause |

What a person gets, in their words:

- A paper's "no" or "no evidence that" always reaches the check with the sentence it belongs to, or the sentence is left out. Never a sentence checked against its own words.
- A sentence a paper only quotes or brackets is never printed as the paper's finding without the check reading the quotation it sits in.
- A sentence copied word for word from a paper still shows exactly when it showed before. A stray bracket or quote mark earlier in the abstract changes nothing.
- A copy cut at "S. Typhimurium" or "St. Jude" is read by the check with the paper's whole sentence, so a reversed tail is held.

What stays as develop, on purpose: the writer's splitter (`_SENTENCE_BOUNDARY`; the tag's builder measured a writer-side join and it broke a disclosure count, `test_required_paths.py`), the code-built listing in `findings.py` (J-101N-07 is its own small follow-on: split rows with `_record_sentences`), and `sentence_check.py` entire.

## Prototype results on the reviews' reproductions

`proto_soft_breaks.py` in the session scratchpad (card101-design folder): pure string functions carrying the rules above, nothing imported from the product. Each line asserts the graded unit count equals develop's and prints the longest unit on both. Every case held the assertion; the longest unit never changed.

| Case | Copy or quote | Whole, unchecked | The run the check reads |
|---|---|---|---|
| A4-101-01 "No isolates of S. Typhimurium carried the blaCTX-M gene." | copy "Typhimurium carried the blaCTX-M gene" | No | "No isolates of S. Typhimurium carried the blaCTX-M gene." |
| A4-101-01 "the U.S. FDA-approved vaccine" | copy "FDA-approved vaccine prevents bronchiolitis in infants" | No | The whole sentence with "It is unproven that" |
| A4-101-02 quotation | copy "Drug X cures cancer" | No | The whole quotation with "Advertisers claimed that" |
| A4-101-02 bracket | copy "Ribavirin cured every infant" | No | The bracket with "since retracted" |
| A-101N-01 inch mark `5"` before the quotation | copy "Drug X is safe in children" | No | The quotation with "The company claimed" |
| A-101N-02 straight single, curly single; A-101N-03 guillemets; curly double | the same copy | No, all four | The quotation, all four; the later whole copy "Mortality was unchanged in the trial" still shows in every case |
| A-101N-03 German „…“ and Swedish ”…” | the same copy | Yes, as develop | Residual, see below |
| A-101N-13 unclosed `(`, `"` or `“` then nine sentences | copy "Mortality was unchanged in the treated group" | Yes, 11 units as develop | Shown; the unmatched opener holds nothing |
| J-101N-04 six "hepatitis B." and "vitamin D." sentence ends, then the denial | copy of the denial; quote "aspirin prevents colorectal cancer in adults" | No (after a soft break) | "The cohort lacked vitamin D. There is no evidence that aspirin prevents colorectal cancer in adults.", 8 units as develop, longest 71 |
| J-101N-04 faithful half | copy "Levels were low for vitamin D" | No | A three-unit run of 95 characters, sent, not held |
| A-101N-08 twelve "arm A." to "arm L." sentences then the denial | quote "azithromycin shortened the illness in infants with bronchiolitis" | | "... treatment arm L. There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.", 14 units as develop |
| A-101N-08 | copy "Mortality was unchanged in the treated group" after "arm L." | No | A two-unit run, sent |
| "vitamin D. Then the drug cured nobody." | copy "Then the drug cured nobody" | No | Both units, 60 characters |
| A-101N-11 "Dr. A. Smith." | copy "Results were negative" | Yes | As develop, 4 units |
| Apostrophes, possessives, 'gold standard' | copy "Children's doses were lower" | Yes | No quote opened by "patients'" or "didn't" |
| Half-open interval "[0.5, 1.2)" | copy "Mortality was unchanged in the trial" | Yes | The `[` never closes and is ignored |
| J5-101-01 one unit of 715 characters | quote "azithromycin shortened the illness ..." | | None: held, never a bare quote |

The cost the judge measured for the tag (A-101N-05: a true whole copy after "vitamin D." waits on the check) remains, but bounded: one extra item with a two-unit run, never a hold past 600 and never a chain. On the trace corpus the shape fires 0 times in 56 develop breaks (the only short tokens before a break are "16.98%)." and "0.5%).", which the shape does not match).

## Residuals, named

Each is develop's own behaviour, kept on purpose rather than fixed with a list.

| Residual | Why it stays | What covers it |
|---|---|---|
| German „…“ and Swedish ”…” quote styles: the quoted claim shows as on develop | „ is category Ps and “ is Pi, both openers; ” is Pf twice. No pairing without naming the style | The sentence check for a reworded copy; nothing for a whole copy, as today |
| A tail-only copy after a two-or-more-letter abbreviation ("vs. Placebo-treated patients improved by 20%", "Jude developed the infection") when the writer never wrote the head | No shape tells "St." from a sentence's last word; a list is forbidden | The adjacency rule covers the case the diagnosis reproduced, a faithful whole copy the writer's splitter cut. The tail-only case is the writer starting mid-sentence, which develop also shows |
| A closing quote after the full stop (`safe."`) blocks develop's break, so the unit after it joins the quotation's tail | Develop's regex requires the full stop right before the whitespace | Harmless: the unit is longer by one sentence, within 600 |
| A record unit develop already reads as over 600 characters: the reworded sentence is held instead of checked against its bare quote | Principle 2 | The owner trade-off below |

## The replay bench

What the tag left, and what it can and cannot see:

| Piece | Where | What it measures | Limit |
|---|---|---|---|
| `raw/replay_r6.py` | `git show parked/card101-last-slices-2026-10-08:testing/Developer/reports/2026-10-08_card101/raw/replay_r6.py` | Every recorded writer draft beside its findings, run through `run_grounding_pass` on each tree with the check approving nothing and everything; sentences shown that develop does not show, develop sentences dropped, drafts emptied | No writer quotes are recorded, so the reworded path is stripped alike on every tree and never measured |
| `raw/exposure.py` | Same tag path | Record values in the traces: develop breaks a new tree removes or regrades, units newly over 600 | Calls `_record_sentence_breaks` and `_ends_on_abbreviation`; the builder renames to `_record_breaks` and counts grades instead of removals |
| `raw/corpus_records.py` | Same tag path | Every record value over 150 characters in the repository's recorded JSON: develop record sentences no longer whole | Same rename |
| Trace folders | `testing/Developer/reports/2026-10-05_sentence_check/raw`, `testing/Developer/reports/2026-10-05_wave3/sentence_check_raw` and its `develop_control` | 69 distinct drafts, 32 distinct record values, 56 develop breaks. The 168 drafts of 8 October included six scratchpad folders that no longer exist, so counts differ from the tag's text files | Carries no abbreviation break, no open mark and no unit over 600 (J-101N-03): it proves no loss, never a gain |
| Repository corpus | `corpus_records.py` over `<repo-root>`: 53 prose values over 150 characters | 0 values with a develop unit over 600 characters (probe `probe_long_units.py`, scratchpad) | Same |

Rerun on 2026-10-15, develop against the parked tag, from the worktree with the three in-repository folders passed as separate arguments:

- `replay_r6.py`: "69 distinct recorded writer drafts"; develop and parked both "items 5, not sent for length 0; shown none 9, all 12"; parked versus develop, both modes, "shown that develop does not show 0; develop sentences dropped 0; drafts emptied 0".
- `exposure.py`: "distinct record values 32; develop breaks 56; values with a break removed 0".

Note for the builder: in zsh, a variable holding three paths must be expanded with `${=VAR}` or the paths written out, or the script receives one argument and reports 0 drafts.

How to run it on develop and on the design:

```
S=<scratch folder>
for p in replay_r6.py exposure.py corpus_records.py; do
  git show parked/card101-last-slices-2026-10-08:testing/Developer/reports/2026-10-08_card101/raw/$p > $S/raw/$p
done
git archive develop src | tar -x -C $S/develop      # the baseline tree
A=testing/Developer/reports/2026-10-05_sentence_check/raw
B=testing/Developer/reports/2026-10-05_wave3/sentence_check_raw
C=$B/develop_control
python -I $S/raw/replay_r6.py $S/replay.txt develop=$S/develop/src design=src -- $A $B $C
python -I $S/raw/exposure.py $S/develop/src src $A $B $C
python -I $S/raw/corpus_records.py $S/develop/src src .
```

`python` is the project venv's interpreter, quoted, as the build brief says. The scripts take `<develop-src> <new-src>` and import `system_03_search_agent.synthesis.grounding` from each.

What the bench must gain, because the real corpora cannot see the change:

| Addition | Form | Why |
|---|---|---|
| A reproduction set | `tests/system_03_search_agent/synthesis/test_record_sentence_end.py`, parametrised over every row of the prototype table above, each case run through the real `run_grounding_pass` with a `candidate_sink` and no model, asserting what is shown, what is sent and the exact run each item carries | The judge's and adversary's own cases are the only text with exposure. They are fixtures, not prompts, so no test question reaches a prompt |
| A reworded-path replay | The same drafts with a synthetic quote per reworded sentence: the longest contiguous span of the sentence found in a cited record (as `_quote_is_valid` finds it), so `pairs` is non-empty; compare each item's quotes on develop and the design, asserting the design's quote contains develop's quote text, or the item is held with develop's run over 600 | The 8 October build left the reworded path unmeasured (A-101N-14); this is the path both criticals crossed |
| A differential fuzz | The judge's `p_fuzz.py` scheme: 4,000 random records from quote marks, brackets, "S.", "U.S.", "e.g.", "Dr.", "vitamin D.", "?", ";", ":" and a faithful writer copy of a random span or unit, first pass, no approvals. Assert: unit count equals develop's on every record; "design shows more than develop" is 0; every item's quotes contain develop's | Principle 1 and the first half of the bar, over shapes nobody listed |

The bar as numbers, every slice:

- Replay, both modes: shown that develop does not show 0; develop sentences dropped 0; drafts emptied 0.
- Reworded-path replay: items whose quote lost text develop's carried 0; items held where develop's run was within 600 characters 0.
- Reproduction set: every "no", "no evidence that", "claimed that", "since retracted" reaches the check inside its run, or the sentence is held; no item carries a bare quote; every later whole copy after a stray mark shows.
- Fuzz: unit count equal on 4,000 of 4,000; design shows more 0.
- Exposure: breaks regraded on the trace corpus reported with examples; units newly over 600 is 0 by construction and asserted.

## Build steps as slices

Dial position 2 for each (answer path, fresh judge and adversary after the set). One branch, `fix/card101-record-sentence-end`, one pull request into develop. Fence for the whole card: `src/system_03_search_agent/synthesis/grounding.py` and `tests/system_03_search_agent/synthesis/` only. Not touched: `sentence_check.py`, `findings.py`, `core/graph.py`, the writer's splitter and any prompt.

| Slice | Change | Tests, red first | Done when |
|---|---|---|---|
| 1. No bare quote | The reworded path uses `record_sentence_run` and holds the sentence when any pair's run is None; the quoted copied branch likewise (the tag's slice 1, fdc30a5d, re-applied); `widen_to_record_sentences` removed and `test_sentence_check.py`'s widener tests (lines 1313 to 1330) moved to `record_sentence_run` | In `test_copied_cuts.py`: the judge's 662-character record with a reworded azithromycin sentence sends no item and shows nothing; the tag's two quoted-cut cases. Mutation: restore the fallback, both red | Replay 0 and 0; the reworded-path replay shows 0 held where develop's run was within 600 |
| 2. Graded breaks for marks | `_mark_spans`, `_record_breaks` with grades `mark` and `hard`, `_record_units`, the whole test's "hard break before" clause, the run's glue across `mark` breaks | Reproduction rows A4-101-02, A-101N-01, A-101N-02, A-101N-03 (all six styles, the German and Swedish rows asserting develop's behaviour so a later change is seen), A-101N-13 (all four heads), apostrophes, the interval. Mutations: category check removed (quotes open nothing), unmatched opener not ignored (A-101N-13 red), straight-quote shape replaced by parity (inch mark red) | Unit count equals develop's on the fuzz; replay 0 and 0 |
| 3. Graded breaks for abbreviations | Grade `abbrev` by the tag's shape (`_ends_on_abbreviation`, 1c05a2b4's regex and 64-character window, kept); the run glues one unit each side; the whole test treats a unit after an `abbrev` break as a cut | Rows A4-101-01 (both), J-101N-04 (chain stays 8 units, the denial's run carries "no evidence", the faithful half is sent not held), A-101N-08 (14 units, the quote's run carries the negation), "vitamin D. Then", A-101N-11. Mutations: glue iterated instead of once (the chain case's run grows, red), shape widened to any token (A-101N-11 red) | Exposure reports every regraded break on the trace corpus with its text; replay 0 and 0 |
| 4. The writer's reply names the cut | In the sentence loop, remember the previous reply sentence's text and whether it carried no marker and was stripped; a whole copy whose predecessor joins to it as one contiguous span of the same record value is a cut with the joined text's run | Rows J-101N-06 ("St. Jude") and A-101N-15 ("vs. Placebo") as faithful whole copies the writer's splitter cuts: the tail is sent with the whole sentence, not shown; a control where the previous reply sentence is framing not in the record keeps the whole copy shown; a control where the previous sentence is itself a marked whole copy of the preceding record sentence keeps both shown. Mutation: contiguity test removed (the framing control red) | `test_required_paths.py` and every `stripped_count` pin unchanged; replay 0 and 0 |
| 5. The clause's own run first | `_copied_clause_candidate`: a clause whose words are in the record takes `_copied_record_span(claim)`; the writer's quote only otherwise | Row A-101N-10: the item's quotes include the infant sentence with "There was no evidence that". Mutation: order swapped, red | Replay 0 and 0 |

Every slice: `ruff check` with no path, `isort --check-only` per gate02, the synthesis test folder green, the four card 101 files' mutation table in `build.md` with sha256 restores, the bench numbers in `raw/`. The tag's `test_copied_cuts.py` additions (lines 1043 to 1130) are the starting point for slices 1 and 3; their expected unit counts change to develop's.

## Live check

After the set merges to develop, on deployed develop, no fewer than five runs each:

| Question | Mode | Runs | What to see |
|---|---|---|---|
| `What are the typical symptoms and risk factors of GERD?` (query 106) | Plain language | 5 | About two to three sentences above the records; where a paper says young children the answer never says children; no run loses all its prose |
| `What causes bronchiolitis in babies, and how is it usually treated?` (query 106) | Plain language | 5 | Never "babies" where the record says children; sentences above the records |
| `What do studies say about Salmonella Typhimurium and extended-spectrum beta-lactamase genes?` (the tag's addition to query 106) | Researcher | 3 | No sentence begins with a name cut from the middle of the paper's sentence ("Typhimurium carried ..."); no sentence drops the paper's "no" |
| `Is the U.S. FDA-approved RSV vaccine shown to prevent bronchiolitis in infants?` | Researcher | 3 | No sentence opens "FDA-approved vaccine ..." with the paper's "unproven" gone |
| `Does azithromycin shorten bronchiolitis in infants?` | Researcher | 3 | A sentence from a long abstract shows only with the paper's whole sentence read; "no evidence that" is never dropped |
| `Does ribavirin cure bronchiolitis in infants?` | Researcher | 3 | A claim a paper quotes or brackets in order to reject it is never printed as the paper's finding |

Count per run: sentences shown, items sent, items held unsent, and whether any run answered with the record list alone. If any of the four Researcher questions answers with the list alone on every run, report it as the cost and let the owner weigh it; the plain-language sentence counts must not fall below query 106's two to three. Spend stays under the usual check cost (round 5 measured $0.0023 for 20 runs). The test-queries lines the tag added to query 106 are re-added with the merge, with their "What you should see" as above.

## Risks and how each is prevented

| Risk | How it would show | Prevention |
|---|---|---|
| A rule lengthens a unit after all | A run past 600 where develop had none; a held sentence develop checked | Units are develop's by construction (`_record_units` splits at the unchanged regex); the fuzz asserts the count on 4,000 records; exposure asserts "newly over 600" is 0 |
| The glue chains | A "hepatitis B." abstract gives a long run | Abbreviation glue is one unit each side, tested on the chain case with a mutation that iterates it |
| A mark never closes and swallows the record | Whole copies after a stray mark held unsent (A-101N-13) | An opener open at the value's end is ignored and the value re-read; tested with all four heads |
| Parity flips on an inch mark | The quoted claim shows unchecked | Straight quotes pair by shape, not parity; the inch mark is a closer with nothing open |
| An enumerated mark list | A quote style nobody listed shows the claim | Unicode categories Ps, Pi, Pe, Pf; the two styles that cannot pair are named residuals with tests pinning develop's behaviour |
| The adjacency rule holds a legitimate pair of whole copies | Two cited whole sentences in a row, the second held | The rule fires only when the previous reply sentence carried no marker and was stripped; a marked predecessor is a control test |
| The adjacency rule fires on framing | "Here is what the study found. Whole copy [1]." held | Contiguity in the record decides; framing is not in the record; a control test |
| The writer's strip count changes | `test_required_paths.py::test_a_framing_prefix_cannot_smuggle_an_uncited_claim` red | The writer's splitter is outside the fence; the test is run every slice |
| The corpora show 0 because they cannot see the change | A "0 dropped" verdict that measures nothing (J-101N-03) | The reproduction set, the reworded-path replay and the fuzz are part of the bar; exposure prints every regraded break with its text |
| A sixth review round repeats the pattern | The owner's review budget spent again | The reproduction set is written before the code, from the reviewers' own cases; the fresh judge and adversary get the prototype table to break, not a replay that cannot see the change |
| The listing still prints the cut row | "Typhimurium carried the blaCTX-M gene [1]." in the fallback list | Outside the fence, stated; a one-line follow-on in `findings.py` to split rows with `_record_sentences`, its own card |

## The owner trade-off

One, and it is already covered by a standing decision, so the build can take it:

- The case: a record whose develop unit is already longer than 600 characters (text with no capital after a full stop, such as a run-on list or a 2,000-character value with no sentence breaks). Today a reworded sentence quoting it is checked against the writer's bare quote and can show. Under principle 2 it is held.
- The exposure: 0 of 53 record values in the repository's recorded JSON, 0 of 32 in the trace corpus, longest develop unit 330 characters.
- The standing decision: the owner chose "a missing sentence is better than a wider one" on 2026-10-06, and round 5 applied exactly this hold to the copied path on the owner's yes of 2026-10-07 (A4-101-07: a cut sent with its own words as its quote was approved 3 of 3 from a record that said there was no evidence for it). The reworded path is the same shape; the judge and the adversary each named leaving it open as the card's own reversal.

In the person's words: a sentence rewritten from a paper whose text runs on without sentence breaks is left out rather than checked against its own words. If the owner would rather keep such a sentence, the design holds everything else and only that fallback stays, with the bare quote named in the trust line; not recommended.
