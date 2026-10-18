# Card 101 judge round 1

Judge, fresh context, 2026-10-06. Branch `fix/card101-keep-limit-words` from develop f5729ec5. Findings are appended as they are established.

## Findings

### J-101-01: an "ly" limit word is no longer asked about when the sentence uses its adjective anywhere
- Severity: blocking
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:467` (the `("ly", "")` ending) with `:520-524` (a quote word counts as used when any sentence word shares a form)
- What: a quote word counts as used when ANY word of the sentence, anywhere in it, shares a form with it. A limiting adverb ("partially", "generally", "commonly", "relatively", "usually", "largely", "frequently", "moderately", "severely", "typically", "potentially") shares a form with its adjective, and the adjective is often an ordinary term somewhere else in the sentence ("partial seizures", "general practice", "a common disease", "a first-degree relative", "usual care", "severe sepsis", "clinical trials"). The writer can drop the limit and the pair check proposes no pair at all for it, where develop proposed two.
- In the user's words: a reader can be told "the drug was effective in patients with partial seizures" when the paper says it was only partially effective, and the check never asks about the missing "partially".
- Reproduction: `check_phrases(sentence, [quote])` on develop f5729ec5 (`git show origin/develop:...sentence_check.py`) and on this branch, scratch probe `probe1.py`:
  - quote "The drug was partially effective in patients with partial seizures", sentence "The drug was effective in patients with partial seizures": develop `['was partially', 'partially effective']`, branch `[]`
  - quote "In general practice the drug is generally well tolerated", sentence "In general practice the drug is well tolerated": develop `['is generally', 'generally well']`, branch `[]`
  - quote "The disease commonly affects older adults", sentence "This common disease affects older adults": develop `['disease commonly', 'commonly affects']`, branch `[]`
  - quote "The variant is relatively rare in a first-degree relative", sentence "The variant is rare in a first-degree relative": develop 2 pairs, branch `[]`
  - quote "The drug is potentially fatal in overdose", sentence "The drug is fatal in overdose, a potential concern": develop `['is potentially', 'potentially fatal']`, branch `[]`
  - quote "In certain patients the drug reduces stroke risk", sentence "The drug certainly reduces stroke risk in patients" (drops the who-limit "certain"): develop `['in certain', 'certain patients']`, branch `[]`
  - also lost entirely, same pattern: monthly/month, largely/large, usually/usual, frequently/frequent, moderately/moderate, transiently/transient, severely/severe, significantly/significant, clinically/clinical, locally/local, typically/typical, sometimes/sometime, elderly/elder (quote "Falls in elderly patients cause fractures", sentence "Falls in patients cause fractures, said an elder").
  - control: "young" against "younger" and the exact "young children" case keep both pairs on the branch, as the build claims.
- Why it matters: card 99 measured that the item question alone approves dropped qualifiers (8 and 7 "young children" as "children", 3 and 2 dropped "potentially" in the replay); the pair is the only veto. The build report's last bullet under "What is not covered" names "large" for "largely" and says "this holds for exact matches already". It does not hold to the same degree: an exact repeat of "partially" elsewhere in a sentence is rare, while the adjective of a limiting adverb is a common biomedical term. The labelled set (205 items) has no item of this shape, so "0 of 18 A items get fewer pairs" cannot see it.
- Suggested fix: let a form match suppress a pair only when the sentence keeps the whole phrase in form, that is, some adjacent sentence pair (x, y) has x a form of the first word and y a form of the second. "most effectively treated" against "the most effective treatment" and "specific variant" against "specific variants" are still suppressed; "partially effective" against "effective ... partial seizures" is asked. Alternatively drop "ly" from the endings and re-measure; the build's own data says "ly" recovered no sentence on its own except through "effective treatment", which the phrase rule would also cover.
- NOT FIXED
### J-101-02: one patient or one study widened to "patients" or "studies" is no longer asked about
- Severity: blocking (unsure on how often the writer does this; the mechanism is certain)
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:467-470` (the "es" and "s" endings) with the symmetric match at `:520-524`
- What: the plural ending is symmetric, so a sentence that turns a single case or a single study into a general plural now carries the quote's word "in another form" and no pair is proposed. On develop the noun beside the dropped article was the only proposed pair for these, because "a" and "one" are below `PAIR_MISSING_WORD_MIN_CHARS` and are never the missing word. The new test `WORD_FORM_CASES` "studies and study" asserts the narrowing direction (several studies written as one study) is not asked; the rule is symmetric, so the widening direction is not asked either, and no test covers it.
- In the user's words: a case report about one patient can be shown as "in patients with lupus, the drug caused liver failure", and a single study as "studies found the drug reduces symptoms", with no pair asked about either.
- Reproduction: scratch probe `probe2.py`, develop f5729ec5 against this branch:
  - quote "In a patient with lupus, the drug caused liver failure", sentence "In patients with lupus, the drug caused liver failure": develop `['patient with']`, branch `[]`
  - quote "One study found the drug reduced symptoms", sentence "Studies found the drug reduces symptoms": develop `['study found', 'drug reduced', 'reduced symptoms']`, branch `[]`
  - quote "One trial showed the vaccine prevented infection", sentence "Trials showed the vaccine prevents infection": develop 3 pairs, branch `[]`
  - quote "In a mouse model, the gene caused tumors", sentence "In mouse models, the gene causes tumors": develop 4 pairs including "mouse model", branch keeps only "gene caused" and "caused tumors"
- Why it matters: a single-case or single-study finding stated as a general one is the widening ("how surely", "who") card 99 exists to stop, and the pair check is its only veto after the item question. Whether Jev's pair question would have caught "patient with" is not known; the point is that the branch stops asking.
- Suggested fix: the phrase-level rule in J-101-01 does not cover this ("patients with" is the whole phrase in form). Either keep "s" and "es" out of a match when the quote side is the singular and the word before it in the quote is a determiner shorter than `PAIR_MISSING_WORD_MIN_CHARS` (a code rule on position, not a word list), or accept and record it as the owner's call. I am unsure which is better; it needs a measured look at the labelled set's F items this would bring back.
- NOT FIXED
### J-101-03: all four examples in the new rule 3a line are phrases from the GERD test answers' records
- Severity: blocking against the owner's standing rule; the owner may overrule it, the brief described the examples as "general categories plus the measured words"
- Where: `src/system_03_search_agent/synthesis/findings.py:908-910`
- What: the line's examples are "young", "potentially", "transient" and "in the outpatient setting". Each is a word or phrase from a record quoted in the GERD answers of the owner's test queries (GERD is query 68 in `testing/Test_queries_and_workflows.md`): "young children", "symptoms potentially caused by GERD", "abnormal transient relaxations of the lower esophageal sphincter", and "in the outpatient setting" (5 occurrences in `2026-10-05_wave3/sentence_check_raw/gp1.jsonl`, the GERD plain-language run; card 99's `measurement.md:54-55` names it on items `w-gp1-c1-i5` and `w-gp3-c1-i6`). The owner's rule (`no-hardcoded-decisions`, 2026-09-24): "Never put a test question, or a phrase from its answer, into a prompt as an example. Use neutral examples outside the test set." The house already does this right one function away: `PERPAIR_INSTRUCTIONS` uses "elderly patients", "may reduce", "rarely severe", "most common", and says "Every example is a general category, none is from a test sentence".
- My view on "transient": yes, it is a lifted test word. "How long" is a general category, and "transient" is a common medical word, but it was chosen because it is the word the GERD risk-factor sentence loses, and it is the one example with no other source than that sentence. It also bought nothing: the build's own live table shows "transient" kept in 0 of 6 plain rewordings (against 0 of 9 before). "young" and "potentially" did move (1 of 12 to 7 of 8, 9 of 11 to 7 of 7), but on the very question they were lifted from, so the gate that measures them is the gate they were shaped on.
- In the user's words: the plain-language GERD answer looks better on the owner's test question because the prompt was written around that question's own records; a reader asking about another disease gets an instruction tuned for GERD papers, and the test cannot tell whether it generalises.
- Reproduction: `SYNTH_SYSTEM_INSTRUCTION.split("3a. ",1)[1]` contains `such as "young", "potentially", "transient" or "in the outpatient setting"`; the grep above finds "in the outpatient setting" in the GERD run's raw candidates; the build report's "What is not covered" says the Mediterranean question was not run live and no held-out question was run.
- Suggested fix: neutral examples outside the test set, such as "elderly", "may", "rarely", "for up to a week", "in mice"; then measure the young-children and hedge rates on a question that is not GERD, and on GERD as the regression check.
- NOT FIXED
- Correction to J-101-03, checked by grep: the GERD record says "symptoms potentially attributable to gastroesophageal reflux", not "caused by". All four examples appear in every one of the ten 2026-10-05 GERD runs (gp1 to gp5, gr1 to gr5), which strengthens the point.

### J-101-04: a past-tense finding restated in the present tense is no longer asked about
- Severity: non-blocking, unsure
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:467-469` ("ed", "es", "s" with the final "e" step)
- What: "reduced" and "reduces" now share "reduc", "prevented" and "prevents" share "prevent", "suggested" and "suggests" share "suggest". A trial's past result stated as a general present-tense fact ("the drug reduced symptoms" in one study, written "the drug reduces symptoms") loses the pairs develop proposed on the verb.
- In the user's words: "in one trial the vaccine prevented infection" can be shown as "the vaccine prevents infection" without the pair check asking.
- Reproduction: scratch probe `probe2.py`: quote "One trial showed the vaccine prevented infection", sentence "Trials showed the vaccine prevents infection": develop `['trial showed', 'vaccine prevented', 'prevented infection']`, branch `[]`. Quote "The data suggested a possible link", sentence "The data suggests a link": develop 4 pairs, branch keeps only "a possible" and "possible link" (the hedge is still asked, so this one is safe).
- Why it matters: the tense shift is a "how surely" widening that the pair question's own definition covers; develop asked about it only by accident of exact matching, so this is a lost incidental catch, not a lost designed one. Unsure whether Jev ever vetoed on it; the replay's per-pair data could answer that.
- Suggested fix: measure in the replay how many "vaccine prevented"-type verb pairs Jev answered "yes" on card 99; if any, keep "ed" out of a match against a present-tense "s" form.
- NOT FIXED

### J-101-05: two bounds of the word-form rule are untested
- Severity: non-blocking
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:500` (the final "e" step's length bound) and `:520` (the sentence read only to `MAX_SENTENCE_CHARS`, a line this card rewrote)
- What: mutating either away leaves the whole synthesis suite green.
- In the user's words: if a later edit lets very short stems match ("use" as "us") or reads past the sentence bound the checker is shown, no test notices, and a pair Jev should have been asked could silently disappear.
- Reproduction, each applied alone, run with `pytest tests/system_03_search_agent/synthesis/`, then restored with `git checkout --`:
  - Ma, `if form.endswith("e") and len(form) - 1 >= PAIR_WORD_FORM_MIN_CHARS:` changed to `if form.endswith("e"):`: 600 passed, 0 failed
  - Mc, `_words(sentence[:MAX_SENTENCE_CHARS])` changed to `_words(sentence)`: 600 passed, 0 failed (the sentence-side bound was already untested on develop; `test_check_phrases_reads_only_the_bounded_text` pads only the quote)
- Suggested fix: one test each: `_word_forms("dose")` has no 3-letter member; a sentence whose only shared word sits past `MAX_SENTENCE_CHARS` proposes the pair as if the word were absent.
- NOT FIXED

