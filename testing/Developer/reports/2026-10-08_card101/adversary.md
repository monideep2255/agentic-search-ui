# Card 101 last slices: adversary round 1

Base: 7d63b145f7f30fc6c6dfa63580856c11ceaa9346 (fix/card101-last-slices). Findings appended as established.

## Findings

Method: one probe harness (`run_grounding_pass` first pass with a `candidate_sink`, no model), run against this branch's `src` and against `origin/develop` (c916cfa3) extracted with `git archive` into a scratch folder. "Shown" means `result.sentences` on the first pass, so shown with no check. Python 3 from the project venv.

### A-101N-01: a stray straight double quote (an inch mark) flips the parity and the quoted claim shows again with no check
- Severity: major. Sits inside this round's fix (A4-101-02, `_open_marks` straight-quote parity).
- What: straight double quotes are counted by parity, so any lone `"` before a quotation (an inch mark, a ditto mark, a stray quote in a title) makes the quotation's own opening mark read as a closing one. Every sentence inside the quotation then breaks as on develop, and a claim the record quotes in order to reject it is a whole record sentence again.
- Reproduction: record `A 5" needle was used. The company claimed "Drug X cures cancer. Drug X is safe in children. It is cheap" but trials disagreed.`, narrative `Drug X is safe in children [1].` Branch: `shown: ["Drug X is safe in children [1]."]`, `sink: []`, record sentences `['A 5" needle was used. The company claimed "Drug X cures cancer.', 'Drug X is safe in children.', 'It is cheap" but trials disagreed.']`. Control, the same record with no `5"`: shown `[]`, sent to the check with the whole unit. Develop shows it in both.
- What a person sees: "Drug X is safe in children [1]." cited to a paper that quotes it as the company's claim the trials disagreed with, with no check run, exactly the A4-101-02 defect, reachable by one inch mark earlier in the abstract.
- NOT FIXED

### A-101N-02: a claim quoted in single quotes, straight or curly, still shows with no check
- Severity: major
- What: `_open_marks` counts neither `'` nor `‘ ’` (the comment says an apostrophe looks the same). A record that quotes a rejected claim in single quotes, the house style of many British and European journals, splits inside the quotation exactly as develop.
- Reproduction: record `The company claimed 'Drug X cures cancer. Drug X is safe in children. It is cheap' but trials disagreed.`, narrative `Drug X is safe in children [1].` Branch: `shown: ["Drug X is safe in children [1]."]`, `sink: []`. Same with `‘ ’`: record sentences `["The company claimed ‘Drug X cures cancer.", "Drug X is safe in children.", "It is cheap’ but trials disagreed."]`, shown with no check.
- What a person sees: a claim the paper quotes to reject, shown as the paper's finding, unchecked. The slice "no record sentence breaks while a quotation mark is open" is not met for single quotation marks.
- NOT FIXED

### A-101N-03: guillemets, German low-high quotes and closing-closing quotes are not counted, and the quoted claim shows with no check
- Severity: major
- What: `_OPENING_MARKS` holds only `(`, `[`, `“`. `« »`, `„ “` and `” ”` (Swedish/Finnish style) open nothing.
- Reproduction: narrative `Drug X is safe in children [1].` against `The company claimed «Drug X cures cancer. Drug X is safe in children. It is cheap» but trials disagreed.`, against `The company claimed „Drug X cures cancer. Drug X is safe in children. It is cheap“ but trials disagreed. Mortality was unchanged.` and against `The company claimed ”Drug X cures cancer. Drug X is safe in children. It is cheap” but trials disagreed.` Branch, all three: `shown: ["Drug X is safe in children [1]."]`, `sink: []`. PubMed abstracts and ClinicalTrials.gov text translated from other languages carry these marks.
- What a person sees: the rejected claim as the paper's finding, unchecked.
- NOT FIXED

### A-101N-04: a German closing quote `“` is read as an opening one, and every later sentence of the record stops showing without a check
- Severity: minor (fails closed, but costs true sentences; see A-101N-05)
- What: in `„...“` the closing mark is `“`, which `_OPENING_MARKS` treats as an opener that never closes. The rest of the record becomes one unit.
- Reproduction: record `The company claimed „Drug X cures cancer“ but trials disagreed. Mortality was unchanged in the trial.`, narrative `Mortality was unchanged in the trial [1].` Develop: shown `["Mortality was unchanged in the trial [1]."]`. Branch: shown `[]`, sent to the check with the whole record as one unit; record sentences `["The company claimed „Drug X cures cancer“ but trials disagreed. Mortality was unchanged in the trial."]`.
- What a person sees: a true, whole record sentence develop showed now waits on the check, and is gone if the check holds it or cannot run.
- NOT FIXED

### A-101N-05: whole record sentences develop showed with no check now go to the check after an inch mark, an unmatched curly quote, a mixed quote pair or a sentence ending in one capital letter
- Severity: major (unsure: depends on how often the check approves, which I could not measure offline; owner's no-degradation rule)
- What: every fail-closed join turns a whole copy into a cut. On the first pass nothing shows, one more check item is spent, and when the check holds it, cannot run, or the run passes 600 characters (A-101N-06), a true sentence is lost.
- Reproduction, narrative then record, develop shown vs branch shown:
  - `Mortality was unchanged in the trial [1].` / `A 5" needle was used. Mortality was unchanged in the trial.`: develop `["Mortality was unchanged in the trial [1]."]`, branch `[]` (sink 1).
  - same / `Leaflets said “this drug is a miracle. Mortality was unchanged in the trial.`: develop shown, branch `[]`.
  - same / `Leaflets said “Drug X cures cancer" in every clinic. Mortality was unchanged in the trial.` (curly open, straight close): develop shown, branch `[]`.
  - `Supplementation reduced fractures in older adults [1].` / `Patients lacked vitamin D. Supplementation reduced fractures in older adults.`: develop shown, branch `[]`.
- What a person sees: a confident, word-for-word true answer replaced by a slower one, or by nothing.
- NOT FIXED

### A-101N-06: one early unmatched quote mark or bracket in a long abstract silently drops every true whole-sentence copy after it, with no check asked
- Severity: major. Sits inside this round's fix (A4-101-02 fail-closed join plus the 600-character run limit).
- What: an unmatched `"`, `(`, `[` or `“` near the start of a long value makes the rest of the value one record sentence. A word-for-word copy of any later sentence is then a cut, its run is the whole remainder (over `MAX_WIDENED_QUOTE_CHARS` = 600), `record_sentence_run` returns None, and the sentence is held: not shown, not even sent to the check.
- Reproduction: value = `Background: "the 2019 guideline. ` + 70 sentences of the form `Cohort i enrolled 100+i infants in the second phase of the trial.` + ` Mortality was unchanged in the treated group.` (4,618 characters). Narrative `Mortality was unchanged in the treated group [1].` Develop: `shown= ['Mortality was unchanged in the treated group [1].'] sink= []`, 72 record sentences. Branch: `shown= [] sink= []`, 1 record sentence. Same result with `Background (see the 2019 guideline. ` (4,621 chars) and with an inch mark `A 2" catheter was used. ` (4,609 chars). Control with no mark: branch shows it, 72 record sentences.
- What a person sees: a correct sentence copied word for word from the abstract, which develop showed, disappears with no explanation; the answer gets thinner. The trigger is ordinary text: an inch mark, a truncated parenthetical, a quoted guideline title that the abstract never closes, or a value cut short by a field limit.
- NOT FIXED

### A-101N-07: a reworded sentence's check reads only the writer's own quote, without the "There was no evidence that" develop showed it, once a stray bracket or quote mark joins the record
- Severity: critical. Sits inside this round's fix (A4-101-02 join, via the widener it shares). STOP CONDITION: a regression made by a fix in this phase.
- What: the reworded-sentence path (`run_grounding_pass`, about line 1783) still calls `widen_to_record_sentences`, whose fallback is the writer's own quote when the run passes 600 characters. J5-101-01 replaced that fallback with a hold on the copied-cut path only. This round's joins (an unmatched mark holds every later sentence inside one unit) make the run longer, so a quote develop widened to its record sentence now falls back to the bare quote. The check is then shown the writer's words as the record text, with the clause that reverses them cut off: the A4-101-07 and J5-101-01 defect on the reworded path, newly reachable.
- Reproduction: value = `Background (see the 2019 guideline. ` + 12 sentences `Cohort i enrolled 100+i infants in the second phase of the trial.` + ` There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. Results were consistent.` Narrative `Azithromycin shortens the illness in babies with bronchiolitis [1: "azithromycin shortened the illness in infants with bronchiolitis"].` Question `Does azithromycin help babies with bronchiolitis?`
  - Develop sink: sentence `Azithromycin shortens the illness in babies with bronchiolitis`, quote (92 chars) `There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.`
  - Branch sink: same sentence, quote (64 chars) `azithromycin shortened the illness in infants with bronchiolitis`
  - Control, the same value with `Background: see` (no bracket): branch sink quote is the 92-char sentence with "There was no evidence that".
- What a person sees: if the check approves what it is shown, and the text it is shown supports the sentence word for word, "Azithromycin shortens the illness in babies with bronchiolitis [1]" appears cited to a paper that found no evidence of it. The check cannot catch it: the negation is not in what it reads. Any unmatched `(`, `[`, `“` or odd `"` anywhere before the quoted span triggers it, for every reworded sentence after that point in a long abstract.
- NOT FIXED

### A-101N-08: the one-capital-letter rule alone chains ordinary sentences into one long unit, with the same two effects as A-101N-06 and A-101N-07
- Severity: critical for the reworded path (same STOP CONDITION as A-101N-07, inside this round's A4-101-01 fix); major for the whole-copy drop.
- What: every sentence that ends on a one-letter token ("arm A.", "vitamin D.", "hepatitis B.", "drug X.", "group C.") joins the next one. A trial abstract that names its arms by letter becomes one record sentence. No quotation mark or bracket is needed.
- Reproduction: chain = 12 sentences `Infants in cohort N were randomized to treatment arm A.` ... `arm L.`
  - Value chain + ` There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. Results were consistent.`, narrative `Azithromycin shortens the illness in babies with bronchiolitis [1: "azithromycin shortened the illness in infants with bronchiolitis"].` Develop: 14 record sentences, check quote (92 chars) `There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.` Branch: 2 record sentences, check quote (64 chars) `azithromycin shortened the illness in infants with bronchiolitis`, the negation gone from what the check reads.
  - Value chain + ` Mortality was unchanged in the treated group.`, narrative `Mortality was unchanged in the treated group [1].` Develop: shown `['Mortality was unchanged in the treated group [1].']`, 13 record sentences. Branch: shown `[]`, sink empty (held, never sent), 1 record sentence.
- What a person sees: as A-101N-07, a reversed claim that the check is shown no reason to reject; and a true whole copy develop showed, silently gone.
- NOT FIXED

### A-101N-09: "Dr. A. Smith" makes record sentences that start on an initial: "L. There was no evidence ..."
- Severity: minor (unsure of downstream harm)
- What: the shape rule breaks after "Dr." (two letters, no inner stop) but joins after the initial, so record units are cut in the middle of a name. The unit the check reads opens on a stray initial, and the sentence before it ends on "Dr.".
- Reproduction: value = 24 sentences `Samples N were sent to Dr. <letter>.` + ` There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. Results were consistent.` Branch record sentences: 26, the check quote for the reworded narrative above is `L. There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.` (95 chars). Develop: `There was no evidence that ...` (92 chars). Also `_record_sentences("Samples were sent to Dr. A. Smith. Results were negative.")` splits as "... Dr." / "A. Smith." / "Results ..." (by reading the code path; the 24-sentence output above is the observed one).
- What a person sees: nothing directly; the check reads a unit with a stray letter, and a writer copy "Samples were sent to Dr" is a whole record sentence.
- NOT FIXED

### A-101N-10: a copied cut with a short quote of its own words sends the check a different sentence, not the one the cut dropped a clause from (J5-101-01 variant, partial quote)
- Severity: major (pre-existing on develop, same output; in the J5-101-01 area this round touched)
- What: on the copied-cut path, a valid writer quote wins over the claim's own record span, and `record_sentence_run` takes the FIRST record sentence that contains the quote. A writer that quotes a short piece of its copy steers the check to an earlier sentence, so the check never reads the "There was no evidence that" its cut dropped.
- Reproduction: value `Azithromycin shortened the illness in adults with pneumonia. There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.`, narrative `Azithromycin shortened the illness in infants with bronchiolitis [1: "azithromycin shortened the illness"].` Branch and develop alike: sink sentence `Azithromycin shortened the illness in infants with bronchiolitis`, only quote `Azithromycin shortened the illness in adults with pneumonia.` The claim's own record sentence is not among the quotes.
- What a person sees: the check judges the infant claim against an adult pneumonia sentence and never sees the denial. If it generalises, "Azithromycin shortened the illness in infants with bronchiolitis [1]" shows, cited to a paper that says there was no evidence of it.
- NOT FIXED

### A-101N-11: confirmed by run, "Dr. A. Smith" on this branch splits as "Samples were sent to Dr." / "A. Smith." and the copy "Samples were sent to Dr [1]." shows with no check
- Severity: minor (also on develop, which splits "A." / "Smith." apart too)
- Reproduction: value `Samples were sent to Dr. A. Smith. Results were negative.`, narrative `Samples were sent to Dr [1].` Branch record sentences `['Samples were sent to Dr.', 'A. Smith.', 'Results were negative.']`, shown `['Samples were sent to Dr [1].']`. Develop record sentences `['Samples were sent to Dr.', 'A.', 'Smith.', 'Results were negative.']`, same shown. This replaces the "by reading" part of A-101N-09.
- What a person sees: a sentence cut off mid-name, shown as checked record text.
- NOT FIXED

### A-101N-12: the code-built listing still splits after one capital letter and shows "Typhimurium carried the blaCTX-M gene [1]." as its own sentence, with no check
- Severity: major (same on develop; the slice "a record sentence no longer ends after one capital letter" does not reach this surface)
- What: `build_structured_fallback_narrative` splits a value with `split_into_sentences` (every full stop), and `_is_code_built_row` accepts each piece as whole. The A4-101-01 shape rule changed only `_record_sentence_breaks`.
- Reproduction: one finding, value `No isolates of S. Typhimurium carried the blaCTX-M gene. The company claimed "Drug X cures cancer. Drug X is safe in children." Trials disagreed.` `build_structured_fallback_narrative([f])` = `No isolates of S [1]. Typhimurium carried the blaCTX-M gene [1]. The company claimed "Drug X cures cancer [1]. Drug X is safe in children." Trials disagreed [1].` `run_grounding_pass(..., code_built_listing=True).sentences` = `('No isolates of S [1].', 'Typhimurium carried the blaCTX-M gene [1].')`, branch and develop identical.
- What a person sees: when the writer fails and the app falls back to the listing, "Typhimurium carried the blaCTX-M gene [1]." reads as the paper's finding; the paper says no isolate carried it. "No isolates of S [1]." beside it does not read as its subject.
- NOT FIXED

### A-101N-13: A-101N-06 at a realistic size: a 654-character abstract with one unclosed mark is enough
- Severity: major (addendum to A-101N-06; values are clipped at `findings.MAX_FIELD_VALUE_CHARS` = 2000, so my 4,600-character case was larger than any real value; this one is well inside it)
- Reproduction: value = head + 9 sentences `Cohort i enrolled 100+i infants in the second phase of the trial.` + ` Mortality was unchanged in the treated group.`; narrative `Mortality was unchanged in the treated group [1].`
  - head `Background (see the 2019 guideline. ` (657 chars): develop shown `['Mortality was unchanged in the treated group [1].']`, 11 record sentences; branch shown `[]`, sink 0, 1 record sentence.
  - head `Background: "the 2019 guideline. ` (654): same split, develop shown, branch held.
  - head `Background: “the 2019 guideline. ` (654): same.
  - control `Background: the 2019 guideline. ` (653): both show it.
- Timing, for the brief's question: no slowdown. `run_grounding_pass` on the 4,600-character cases took 0.0021 to 0.0036 s on the branch, 0.0009 to 0.001 s on develop. The cost is not time; the sentence is skipped, not checked.
- NOT FIXED

### A-101N-14: the build's "no exposure" measurements cannot see this round's changes, so 0 is not evidence of no harm
- Severity: minor (evidence quality)
- What: `raw/exposure.txt` reports `values with a break removed 0` on 55 record values, and `raw/corpus_records.txt` `develop record sentences no longer whole 0` on 33. `build.md` line 100 itself says the corpora "carry no "S." or "U.S." before a capital, and no multi-sentence quotation". A corpus with no abbreviation-before-capital and no unclosed or multi-sentence quotation produces 0 for a broken and for a working boundary alike, and `replay_r6.txt` passes no writer quotes, so the reworded-path effect (A-101N-07, A-101N-08) is not measured at all. `build.md` line 115 names the reworded path's fallback and rules it out of scope on the strength of "the corpora show 0 newly past 600".
- Reproduction: A-101N-07 and A-101N-08 above: a stray bracket or a lettered-arm abstract makes the reworded path lose its negation, where those corpora report 0.
- NOT FIXED

### A-101N-15: a lowercase abbreviation before a capital ("vs.", "Fig.", "approx.", "cf.", "spp.") still ends a record sentence, and the tail shows with no check
- Severity: major (same on develop; outside the new shape by design, the code comment names only "Dr. Smith" and "et al. Smith" as the accepted gap, and the user-visible cost is a reversed meaning, not just a fragment)
- What: `_ABBREVIATION_SHAPE` covers one capital letter or letters with an inner full stop. A two-plus-letter abbreviation with no inner stop breaks before a capital, so the words after it are a whole record sentence and a copy of them shows with no check.
- Reproduction: value `Survival in patients given drug X vs. Placebo-treated patients improved by 20%. No other outcome differed.`, narrative `Placebo-treated patients improved by 20% [1].` Branch record sentences `['Survival in patients given drug X vs.', 'Placebo-treated patients improved by 20%.', 'No other outcome differed.']`, shown `['Placebo-treated patients improved by 20% [1].']`, sink `[]`. Develop identical. Also `Resistance was absent in the isolates shown in Fig. S2. Results ...` splits as `['... shown in Fig.', 'S2.', 'Results in Table 3 show no resistance to colistin.']` (harmless here, but "S2." is a record sentence of its own).
- What a person sees: "Placebo-treated patients improved by 20% [1]." cited to a trial where the drug, compared with placebo, improved survival: the opposite arm credited, no check run.
- Control: `No isolates of strain K. Pneumoniae carried the gene.` with narrative `Pneumoniae carried the gene [1].` is fixed on the branch (sent to the check with the whole sentence; develop showed it unchecked).
- NOT FIXED

### Arms the round's tests do pin (not a finding, for the record)
I mutated each new arm in my checkout and ran `test_copied_cuts.py` alone (unmutated: 83 passed): `“` removed from `_OPENING_MARKS` 1 failed; `[` removed 1 failed; straight-quote parity disabled 1 failed; `_ABBREVIATION_SHAPE` reduced to one capital letter 3 failed. File restored, `git status --short` clean.

## Verdict

FAIL against the ticket "a sentence the writer reworded never reaches the screen without passing the sentence check", on A-101N-07 and A-101N-08 (critical, inside this round's fixes: a stray bracket or a lettered-arm abstract makes the check read a reworded sentence's quote without the negation develop showed it) and on A-101N-01 to 03 (the quoted-claim slice is bypassed by an inch mark, single quotes, guillemets and German or Swedish quotes). Stop condition fires: A-101N-01, 06, 07 and 08 sit inside fixes made in this phase.

Verified with my own probes (offline `run_grounding_pass` first pass, branch against develop): A-101N-01 to 08, 10, 11, 12, 13, 15, timing, the four mutations. Read only, not run: the build report's corpus numbers (A-101N-14 is about what they can detect) and whether the live sentence check would approve the A-101N-07 / 10 items (no model calls were allowed).
