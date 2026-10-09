# Card 101 last slices, judge round

Base: 7d63b145f7f30fc6c6dfa63580856c11ceaa9346 on fix/card101-last-slices. Diff: `git diff origin/develop...HEAD`, four commits.

## Findings

### Replay, rerun by the judge

Rerun of the builder's own scripts against trees exported with `git archive` (develop c916cfa3, fdc30a5d, 1c05a2b4, HEAD 7d63b145), over the in-repository trace folders plus the six scratchpad trace folders of the earlier rounds:

- `replay_r6.py`: "168 distinct recorded writer drafts"; every tree "items 34, not sent for length 0; shown none 52, all 59"; head vs develop, both modes: "shown that develop does not show 0; develop sentences dropped 0; drafts emptied 0".
- `exposure.py`: "distinct record values 55; develop breaks 77 / values with a break removed 0; removed after an abbreviation 0; inside an open mark 0 / record sentences newly over 600 characters 0".
- `corpus_records.py`: "distinct prose values 33; develop record sentences 179 / develop record sentences no longer whole 0".

The builder's numbers reproduce. They are not evidence about these slices: the exposure line shows no recorded value contains a single break the new code removes, so a tree with the three slices reverted produces the identical counts. See J-101N-03.

### J-101N-01: a stray quote mark or bracket makes the check read only the writer's cut quote, where develop gave it the paper's denial

- Severity: critical. This sits inside slice 3 (07169e94), a fix made in this phase; it also applies to slice 2's joins (J-101N-04). Escalation per the review loop's stop condition.
- What: `_record_sentence_breaks` removes every break after an unclosed opening mark, so the rest of the record is one unit. Past 600 characters `widen_to_record_sentences` falls back to the writer's own quote, and the reworded path (`run_grounding_pass`, grounding.py:1783, card 89's fallback, unchanged) sends the check that quote alone. On develop the same item carried the whole record sentence the quote sits in. The slice comment's claim "Fails closed: ... a copy of one goes to the check or, past what the check reads, is held" (grounding.py:874-877) is true for copied clauses only; the reworded path is not held, it is sent with less context.
- Reproduction (judge probe `p_regress.py`, scratchpad, offline, real `run_grounding_pass`, no model call). Record [1], 662 characters: 'Each clinic used a 5" tablet for questionnaires.' then three filler sentences, then "There is no evidence that aspirin prevents colorectal cancer in adults.", three filler sentences, "Treatment is usually symptomatic." Writer: `Aspirin lowers the risk of colorectal cancer in adults [1: "aspirin prevents colorectal cancer in adults"].`
  - develop: "items=[('Aspirin lowers the risk of colorectal cancer in adults', ['There is no evidence that aspirin prevents colorectal cancer in adults...'])]"
  - head: "items=[('Aspirin lowers the risk of colorectal cancer in adults', ['aspirin prevents colorectal cancer in adults'])]"
  - Same with a stray "(" ("Outcomes were recorded (see the online supplement for details."): develop sends the denial sentence, head sends only the cut.
  - The exact checks do not catch it: the negation check compares the claim with the quote (grounding.py:761), and neither negates.
- Why it matters: this is the card's own reversal, "There is no evidence that ..." shown as its opposite, and card 89 widened quotes because the check approves a span read alone. One inch mark, a mixed curly and straight quote, or an unclosed bracket anywhere early in an abstract now strips that protection from every reworded sentence citing a later part of it. Before the slice it did not. The builder's note says "Slices 2 and 3 can only lengthen runs; the corpora show 0 newly past 600", but the corpora contain no stray mark at all (exposure: "inside an open mark 0").
- Smallest fix: the reworded path must not fall back to the writer's quote when the run is None: hold the sentence (as J5-101-01 now does for the quoted copied branch), or give the check the run cut down to the record sentence under the old boundary rather than the bare quote. Separately bound the open-mark reach (J-101N-02).
- NOT FIXED

### J-101N-02: one stray mark early in a record drops every faithful whole copy after it, the paper's own denial included

- Severity: major (answer quality; fails closed, but silently and on any abstract of ordinary length)
- What: an unclosed "(", "[", "“" or an odd straight double quote holds every later break open to the value's end (`_open_marks` has no reach limit). A whole copy of any later sentence is no longer a whole record sentence, so it is a cut; its run is the rest of the record, past 600 characters, so `record_sentence_run` is None and the clause is held without being sent to the check.
- Reproduction (same probe and records as J-101N-01):
  - stray straight quote, develop: "whole copy, last sentence: shown=['Treatment is usually symptomatic [1].'] items=[]" and "whole copy, the denial: shown=['There is no evidence that aspirin prevents colorectal cancer in adults [1].'] items=[]"
  - stray straight quote, head: "whole copy, last sentence: shown=[] items=[]" and "whole copy, the denial: shown=[] items=[]"; "record sentences 1" where develop counts 9.
  - stray open bracket: identical, develop shows both, head shows neither and sends nothing.
- Why it matters: a word-for-word copy of the paper, which develop showed, disappears with no check asked, including the denial that protects the reader. A PubMed abstract is typically 1,500 to 2,500 characters, so one inch mark, an unpaired curly quote, or a half-open interval "[0.5, 1.2)" makes nearly every whole copy from that record vanish. The builder's "0 faithful dropped" corpora contain no such mark (J-101N-03), so this cost is unmeasured, not zero.
- Smallest fix: bound what one open mark can hold, by category not list, for example close an open mark at the next paragraph or after N record sentences, or treat a mark still open at the value's end as no mark (re-run the split with that mark ignored). Add a test with a stray mark and a later whole copy that must still show.
- NOT FIXED

### J-101N-04: the abbreviation shape joins real sentence ends common in biomedical abstracts, and a chain of them reaches the same 600-character fallback as J-101N-01

- Severity: critical for the reworded half (same mechanism as J-101N-01, inside slice 2, 1c05a2b4, a fix made in this phase); major for the faithful drops
- What: `_ABBREVIATION_SHAPE` treats any one capital letter before a full stop as an abbreviation. Sentences that really end "vitamin D.", "hepatitis B.", "phase I.", "group A.", "complex I.", "protein C.", "chromosome X.", "influenza A.", "factor V.", "type B." are joined to the next, as are domain and "i.e." tokens ("www.clinicaltrials.gov.", "i.e."). In abstracts on vitamin D, hepatitis, phase I trials or streptococcal disease these endings repeat, so units chain.
- Reproduction (judge probes `p_shape.py`, `p_shape600b.py`, offline, no model call):
  - "The cohort was tested for {end}. The drug cured nobody." gives "sentences=2" on develop for every end, and "sentences=1" on head for vitamin D, hepatitis B, phase I, group A, complex I, protein C, chromosome X, influenza A, factor V, type B, www.clinicaltrials.gov and i.e. "Dr", "et al" and "E. coli" still give 2 on head.
  - A 663-character abstract, six sentences ending "hepatitis B." (twice), "hepatitis A.", "hepatitis C.", "vitamin D." (twice), then "There is no evidence that aspirin prevents colorectal cancer in adults." and "Treatment is usually symptomatic.", no quote mark or bracket anywhere. develop: "record sentences 8, longest 104"; head: "record sentences 2, longest 629".
  - Whole copy of the denial, develop: "shown=['There is no evidence that aspirin prevents colorectal cancer in adults [1].'] items=[]"; head: "shown=[] items=[]".
  - Reworded `Aspirin lowers the risk of colorectal cancer in adults [1: "aspirin prevents colorectal cancer in adults"].`, develop: "items=[(..., ['There is no evidence that aspirin prevents colorectal cancer'])]"; head: "items=[(..., ['aspirin prevents colorectal cancer in adults'])]".
  - Below 600 (546-character abstract, `p_shape.py`), each previously whole copy becomes a check item: develop "shown=['Deficiency was common in adults with low levels of vitamin D [1].'] items=[]", head "shown=[] items=[('Deficiency was common in adults with low levels of vitamin D', [...])]": an extra model item and a faithful sentence that now depends on the check's approval.
- Why it matters: the comment's "Fails closed: a sentence that really ends on one capital letter ... is read joined to the next, so a copy of either half is a cut and goes to the check, or is held" (grounding.py:818-820) is false on the reworded path, which neither holds nor sends the run. On the copied path it is true, at a cost the builder's corpora cannot see. The checklist's "one check covers two sentences and a false one rides with a true one" does not occur: the writer's splitter (`_SENTENCE_BOUNDARY`, grounding.py:57) still splits at every ". ", so each writer sentence is its own item (probe: "Deficiency ... vitamin D. The trial was stopped early during phase I [1]." gives one item for the second sentence only, the first stripped as unmarked).
- Smallest fix: the J-101N-01 fix (no fallback to the writer's quote) removes the safety half. For the cost half, prefer the narrower shape the failure needs: join only when the token after the full stop is lowercase-continuing or the single capital is preceded by no word it could close (for example only when the next word is a capitalised word immediately following a one-letter token that itself follows a capital-initial word, as "S. Typhimurium", "J. Smith"), and measure it on a corpus that contains these endings before shipping.
- NOT FIXED

Correction to J-101N-04's smallest fix: the shape suggestion in parentheses is wrong ("S. Typhimurium" follows "of", a lowercase word). The fix that stands is J-101N-01's (never send the bare writer quote, hold instead) plus a corpus measurement that contains these endings; the shape itself is the builder's and owner's call.

### J-101N-03: the "0 faithful dropped" replay cannot see any of the three slices

- Severity: minor (evidence, not code)
- What: every corpus the builder measured, and that I reran, contains no record break the new boundary removes, so the slices are never exercised and the counts are the counts of a tree with all three slices reverted.
- Reproduction: `exposure.py` rerun over the same folders: "values with a break removed 0; removed after an abbreviation 0; inside an open mark 0". `replay_r6.py`: develop, slice1, slice2 and head all print "items 34, not sent for length 0; shown none 52, all 59". `corpus_records.py`: "breaks removed: after an abbreviation 0; inside an open mark 0".
- Why it matters: the build note's verdict row "0 sentences develop shows are dropped" reads as a measurement of the change; it measures nothing the change touches. J-101N-02 and J-101N-04 show faithful sentences develop showed and head drops, on short synthetic abstracts of ordinary shape. The builder does state the gap under "What this does not cover"; the verdict table does not.
- Smallest fix: measure on a corpus that contains single-capital sentence ends and stray marks, for example the PubMed abstracts behind the owner's test queries fetched offline once, and report breaks removed and whole copies lost.
- NOT FIXED

### J-101N-05: slice 3 enumerates three bracket and quote pairs, so a claim inside single curly quotes, guillemets or low-high quotes still shows unchecked

- Severity: major (the slice's own hole, open by other marks; inside slice 3, 07169e94)
- What: `_OPENING_MARKS = {"(": ")", "[": "]", "“": "”"}` plus straight double quotes by parity (grounding.py:839-857) is a list, not the category the ticket asks for ("fix by category, never by enumeration"). Opening punctuation and initial quotes are a Unicode category (`unicodedata.category` Ps/Pe, Pi/Pf). The comment's reason for leaving single quotes out, "an apostrophe looks the same", holds for "'" and "’" but not for "‘" (U+2018), which is only ever an opener; and with the existing clamp a closing "’" used as an apostrophe opens nothing anyway.
- Reproduction (judge probe `p_marks.py`, offline, real `run_grounding_pass`, writer "Drug X cures cancer [1].", question "Does drug X cure cancer?"):
  - Record "Advertisers claimed that ‘this drug is a miracle. Drug X cures cancer. It is safe.’ Regulators found every claim false.", head: "shown=['Drug X cures cancer [1].'] items=0".
  - Same with «...»: "shown=['Drug X cures cancer [1].'] items=0"; with „...“: same; with {...}: same.
  - Control, straight double quotes, head: "shown=[] items=1" (develop: "shown=['Drug X cures cancer [1].'] items=0").
- Why it matters: the claim a paper quotes in order to reject it is shown as the paper's finding with no check, exactly A4-101-02, whenever the record uses British-style single quotes or a non-English quote style. The tests cover only the three listed pairs and straight double quotes, so they cannot go red for this.
- Smallest fix: classify by `unicodedata.category`: Ps and Pi open, Pe and Pf close (a close with nothing open opens nothing, as now), straight double quote by parity as now. Add a test arm for "‘...’" and «...».
- NOT FIXED

### J-101N-06: the shape covers one capital and dotted tokens only, so "St. Jude", "et al.", "vs.", "Staph." still split a record sentence and the tail shows unchecked as the paper's opposite

- Severity: major (the A4-101-01 failure, still open for a wider class; the builder names "Dr. Smith" and "et al. Smith" as accepted, the reproduction shows what the reader sees)
- What: `_ABBREVIATION_SHAPE` matches "S." and "U.S." but not a multi-letter abbreviation with no inner full stop. A writer's faithful copy is split by the writer's splitter at "St. ", the head is stripped as unmarked, and the tail is a whole record sentence under the record boundary, so it shows with no check.
- Reproduction (judge probe `p_twoletter.py`, offline, the writer copies the record faithfully, e.g. "No children treated at St. Jude developed the infection [1]."), head:
  - "No children treated at St. Jude developed the infection." gives "shown=['Jude developed the infection [1].'] items=0"
  - "No isolates of Staph. Aureus carried the gene." gives "shown=['Aureus carried the gene [1].'] items=0"
  - "Survival was not improved with drug X vs. Placebo arms showed the same." gives "shown=['Placebo arms showed the same [1].'] items=0"
  - "Unlike the cohort of Smith et al. Ribavirin did not shorten the illness." gives "shown=['Ribavirin did not shorten the illness [1].'] items=0"
  - Develop shows the same four; only "i.e. Ribavirin failed" moved to the check ("items=1").
- Why it matters: the ticket's sentence, "A sentence the writer reworded never reaches the screen without passing the sentence check", is not met for a record cut the writer did not choose: "Jude developed the infection", cited to a paper that says no child did. The build note frames it as "such a cut reaches the screen only as the whole of what follows", which is the defect, not a mitigation.
- Smallest fix, by category: the writer's reply already shows the cut. When a copied clause is immediately preceded in the writer's reply by unmarked text that was stripped and the two joined still sit in the same record value as one run, the copy is a cut (adjacency in the reply, no word list). Test with "St. Jude" and "Staph. Aureus".
- NOT FIXED

### J-101N-07: the code-built record list still prints "Typhimurium carried the blaCTX-M gene [1]." as its own row (deviation confirmed, unchanged from develop)

- Severity: minor (outside this card's statement, the row is code's, not the writer's; confirmed as the builder describes it)
- What: `findings.build_structured_fallback_narrative` splits a value with the writer's splitter, so a record with "S." prints two rows, and the grounding pass keeps both through `_is_code_built_row`.
- Reproduction (judge probe `p_listing.py`, record "No isolates of S. Typhimurium carried the blaCTX-M gene. Resistance was rare."), develop and head identical: "listing='No isolates of S [1]. Typhimurium carried the blaCTX-M gene [1]. Resistance was rare [1].'" and "shown=['No isolates of S [1].', 'Typhimurium carried the blaCTX-M gene [1].', 'Resistance was rare [1].']". Note the listing also drops the full stop after "S", so the first row reads "No isolates of S".
- Why it matters: on the fallback page a reader sees a row stating the paper's opposite, cited. Both rows are adjacent, so the "No" is on the screen, but the second reads as a claim.
- Smallest fix: split listing rows with `_record_sentences` (the record boundary this card now owns) rather than the writer's splitter, keeping the semicolon split the listing needs.
- NOT FIXED

## Checks that held

- Fail closed on the copied path, by my own differential fuzz (`p_fuzz.py`, seed 11, 4,000 random records built from quote marks, brackets, "S.", "U.S.", "e.g.", "Dr.", "vitamin D.", "?", ";", ":" and a faithful writer copy of a random span or sentence; first pass, no approvals): "{'cases': 4000, 'head shows more': 0, 'develop shows more': 99}". Head never shows a sentence develop does not; the 99 are sentences head sends to the check or holds. By reading: breaks are only ever removed, and the writer's splitter (grounding.py:57) splits at every ". ", so no joined unit can become a writer's whole sentence.
- "One check covers two sentences and a false one rides with a true one": not observed. Each writer sentence is its own check item; a joined unit only lengthens the quote the check reads (J-101N-04, `p_shape.py`).
- Slice 1 holds a quoted copied cut whose run is past 600 characters: the builder's two cases pass, and my mutation M1 turns them red (below). It does not cover the reworded path (J-101N-01).
- Bounded work: `_record_sentence_breaks` is one pass (`_open_marks` advances `counted`), `_ends_on_abbreviation` reads at most 64 characters. Timing (`p_shape600.py`), `record_sentence_run` with an absent quote on an 8,289-character, 150-sentence record: develop "0.941s", head "1.013s"; with a stray "(" head "0.001s" (one unit). The quadratic width loop in `record_sentence_run` is pre-existing and unchanged.
- No logging, secret or prompt change in the diff (`git diff origin/develop...HEAD -- src/` touches only grounding.py's boundary, widener and copied-clause code). Cite-or-refuse: a held sentence is stripped and counted, the refusal path is unchanged.

## Break it, does a test go red

One property broken by hand, `test_copied_cuts.py` run, the file restored from a copy and its sha256 compared. After all five: `git diff --stat HEAD` printed nothing.

| Mutation | Result, from output |
|---|---|
| M1 slice 1: quoted branch falls back to the quote | "2 failed, 81 passed", "restored sha-match" |
| M2 slice 2: `_ends_on_abbreviation` returns False | "5 failed, 78 passed", "restored sha-match" |
| M3 slice 3: `_still_open` returns False | "5 failed, 78 passed", "restored sha-match" |
| M4 slice 3: `counted` never advanced (marks recounted from the start) | "3 failed, 80 passed", "restored sha-match" |
| M5 slice 2: abbreviation window 3 characters | "3 failed, 80 passed", "restored sha-match" |

No test goes red for J-101N-01, 02, 04, 05 or 06: there is no arm for the reworded path past 600 characters, a stray mark with a later whole copy, a single-capital sentence end, a single curly quote or guillemet, or a multi-letter abbreviation.

## Test runs

- `tests/system_03_search_agent/synthesis/test_copied_cuts.py`: "83 passed in 2.79s".
- `tests/system_03_search_agent/synthesis`: "750 passed, 10 skipped, 1 xfailed in 4.81s".

## Verified by my own probes versus only read

- Probed: J-101N-01 to 07, the fuzz, the five mutations, the replay reruns, the timings.
- Read only: that no joined unit can ever equal a writer sentence (argued from grounding.py:57 and 806, supported by the fuzz but not proven); that the refusal path is unchanged (no diff there). No live model call was made, so how the check judges a 600-character joined quote, and whether it approves the bare cut "aspirin prevents colorectal cancer in adults" for the reworded sentence, is inferred from card 89's and A4-101-07's recorded measurements, not re-measured.

## Verdict

FIX FIRST: J-101N-01 (critical), J-101N-04 (critical, reworded half), J-101N-02 (major), J-101N-05 (major), J-101N-06 (major). J-101N-03 and J-101N-07 are minor and may ride.

J-101N-01 and J-101N-04 sit inside fixes made in this phase (slices 3 and 2): the review loop's stop condition fires and this goes to the product owner. Both reduce what the check reads for a reworded sentence below what develop gives it, the reversal card 101 exists to stop.
