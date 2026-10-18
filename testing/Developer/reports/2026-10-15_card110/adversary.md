# Card 110 adversary, round 1 (second attempt, commit 06d7b73d)

Adversary at dial position 2. One round. Hunts the confident wrong opening. Files findings, closes nothing. Branch tree at 06d7b73d, develop tree at 7626fe85, both detached worktrees in the session scratchpad.

## Findings

### A2-110-01: Tier B's pick is told it is reading "the first one or two sentences of the written answer" when it reads the third and fourth
- Severity: minor, unsure (inside this phase's change; effect on picks not separately measured)
- What: `_lead_sentence_choice` builds the `write.lead_later_sentence` spec with `instructions=LEAD_SENTENCE_INSTRUCTIONS`, the text written for tier A. It says: "The state is a question a person typed into a biomedical evidence search engine, then the first one or two sentences of the written answer ...". Tier B's state holds the third and fourth cited sentences, labelled "Sentence 1" and "Sentence 2". The classifier is told no earlier sentence exists, which is the one thing the "neither" criterion's "needs an earlier sentence to make sense" clause depends on. The stands-alone check is then the only guard against a pointer sentence (mechanism M1 of the design), so a check slip is not caught by a second line.
- Reproduction: `git diff 7626fe85...06d7b73d -- src/system_03_search_agent/core/graph.py`, the `task_b = _start(_DecisionSpec(point=LEAD_LATER_POINT, ..., instructions=LEAD_SENTENCE_INSTRUCTIONS, ...)` block; `LEAD_SENTENCE_INSTRUCTIONS` in `harness/decide.py` unchanged from develop.
- Why it matters: the tier B pick is asked a question with a false premise; whether it changes picks is not measured by the builder, the design or this round.
- NOT FIXED

### A2-110-02: A paper title wrapped in quotation marks passes the title filter and the stands-alone check, and opens the BRCA1 answer in bold
- Severity: major (inside this phase's change: the title filter and tier B are new)
- What: `_repeats_one_label` compares the sentence with the cited record's label after stripping only end punctuation and `_clean_claim` glue. Curly quotation marks around the title are not stripped, so "“Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [19]." is not flagged as a title (`_repeats_one_label` printed `False`; the same sentence without the quotes printed `True`). The grounding pass keeps it: `run_grounding_pass` on live run dbrca_1's synth findings returned it whole as `'“Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [1].'`. The stands-alone check passes it because a title names everything it talks about (the design's own mechanism M3), and the tier B pick takes it for "Which diseases are associated with BRCA1?" because it mentions breast tumorigenesis.
- Reproduction (live Jev, `_lead_sentence_choice` only, budget 40 s, label map {19: the record's title}): question "Which diseases are associated with BRCA1?", sentences "BRCA1 is a gene that makes a protein helping keep our DNA stable and acting as a tumor suppressor [23]." / "The protein works in transcription, DNA repair of double-stranded breaks, and recombination [23]." / "“Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [19]."
  - branch 06d7b73d, 5 runs: run 3 `2 187 ms` and run 4 `2 245 ms`, both opening on the quoted title, records `lead_later first, lead_stands_alone stands_alone, lead_sentence neither`. Runs 0 and 2: count line by a 1 s timeout (1003 ms each). Run 1: count line, tier B "neither".
  - the same sentence without quotes (case T5), 5 runs: count line 5 of 5, tier B never asked (the filter emptied it).
- Why it matters: the design's own bar item 2 says a record's title never opens the answer. A person asking which diseases BRCA1 is linked to sees a paper's title as the bold first line, the exact V-110-03 / A-110-02 failure the redesign was built to end, back through a pair of quotation marks. Other one-character disguises also pass the filter structurally (printed `False`): an en dash for the title's hyphen, a doubled space, a typographic apostrophe, "Also, " before the title (the grounding pass keeps that one too; the check said `needs_earlier` on it 3 of 3 times it was asked).
- NOT FIXED

- A2-110-02 addendum, more runs (same setup): with the question as typed plus a trailing space (case T6, so Jev does not reuse a cached answer), the branch opened on the curly-quoted title 4 of 5 (records `lead_later first, lead_stands_alone stands_alone, lead_sentence neither`, 356 to 397 ms), develop count line 5 of 5. With straight quotes (case T7) the branch opened on it 3 of 5, develop count line 5 of 5; the grounding pass strips the straight-quoted form on dbrca_1's findings, so only the curly form is shown reachable end to end. With the title's hyphen changed to an en dash (case T9): branch 1 of 5, develop 0 of 5 (the grounding pass strips that form too). Total for the reachable curly form: branch 6 of 10 opened on a paper's title, develop 0 of 10.

### A2-110-03: A verbless two-item fragment, "Ectopia lentis [19] and glaucoma [27].", opens the Marfan features answer in bold
- Severity: major (inside this phase's change; tier B and the stands-alone check are new)
- What: the grounding pass turns a writer's "Ectopia lentis [19] and glaucoma [27] are listed." into the fragment "Ectopia lentis [1] and glaucoma [2]." (run_grounding_pass on live run d66_2's synth findings, printed `KEPT ... -> ('Ectopia lentis [1] and glaucoma [2].',)`). That fragment has no verb and no subject: two of Marfan syndrome's dozens of MedGen features, cited to two different records, so the title filter does not match it (two labels, and `clinical_features` is not a label field). The stands-alone check passes it ("every thing it talks about is named"), and the tier B pick takes it as "at least one part" of the answer.
- Reproduction (live Jev, `_lead_sentence_choice`, budget 40 s, empty label map), question "What phenotypic features are associated with Marfan syndrome?", sentences "Marfan syndrome is a multisystem connective tissue disease with autosomal dominant inheritance [83]." / "It is mainly caused by FBN1 gene mutation and often has different clinical manifestations [83]." / "Ectopia lentis [19] and glaucoma [27]."
  - branch, 5 runs: opened on "Ectopia lentis [19] and glaucoma [27]." 4 of 5 (298, 250, 245, 292 ms; records `lead_sentence neither, lead_later_sentence first, lead_stands_alone stands_alone`); run 3 count line by the 1 s bound (1004 ms, the check cancelled at 1003).
  - develop, 5 runs: count line 5 of 5 (`lead_sentence neither`, 209 to 300 ms).
- Why it matters: a person asking what features Marfan syndrome has sees, as the bold first line, two words joined by "and" with no sentence around them, and that line names 2 of the features while the record lists about a dozen; the count line develop shows at least says how many records there are. It is the "answers only a minor part" shape the criteria's "or at least one part of it" lets through, now reachable from third place, where only a check about pronouns stands guard.
- NOT FIXED

### A2-110-04: When nothing in the first two sentences answers, the count line now waits on tier B and its check, up to the full 1 s
- Severity: minor (inside this phase's change; a speed cost on the most common path, not a wrong opening)
- What: on develop, a "neither" from tier A releases the count line the moment it lands. On the branch, the count line waits for tier B's pick and then the picked sentence's check, inside the same 1 s bound. When tier B or the check is slow, the count line, which develop would have shown at once, is held to the bound. Across my replays the count line followed a tier A "neither" in most groundings (it was the opening in most live runs too: cystic fibrosis treatments, rs429358, EGFR drugs, losartan, Duchenne trials).
- Reproduction (live Jev replays of `_lead_sentence_choice`, 340 per tree, the hand cases plus every grounding from this round's 46 live runs, wall time of the whole call, replays where tier A said "neither" and the count line opened):
  - develop: n 251, median 214 ms, p90 290, p95 349, max 993, at or over 1000 ms: 0.
  - branch: n 235, median 253 ms, p90 377, p95 570, max 1004, at or over 1000 ms: 5. Extra wait after tier A's own "neither" landed: median 1 ms, p90 70 ms, max 828 ms, 7 replays waited 300 ms or more.
- Why it matters: in about 2 of every 100 answers where nothing early answers, the person waits about 0.8 s longer for the first line than on develop, to receive the same count line. The owner's rule is no degradation on speed; this is small, bounded, and measured here only on the lead decision, not end to end.
- NOT FIXED

- A2-110-02 addendum, reach: no curly-quoted sentence appears in any saved live grounding (a search for the curly open-quote character over this round's 46 live runs, the first attempt's 28, the builder's 20, the verifier's 21 and the fix round's 10 found none). So the shape is accepted by the grounding pass and opens the answer when it comes, but this round has no live run where the writer produced it; its rate is unmeasured. Other prefixed titles the grounding pass keeps did not open the answer: "Further, <title> [19]." (tier B "neither" 5 of 5, the check `needs_earlier` 2 of 2 asked) and "Title: <title> [19]." (tier B "neither" 5 of 5, though the check said `stands_alone` 4 of 4 asked, so only tier B's pick stood between it and the opening). A title cited with a second marker of the same paper ("<title> [19] [22].") is reduced by the grounding pass to one marker and then caught by the filter.
- A2-110-03 addendum, a control: a bare list of three of the four BRCA1 diseases in third place ("Familial cancer of breast [1], familial breast-ovarian cancer susceptibility 1 [2] and pancreatic cancer susceptibility 4 [3].") opened 5 of 5 on the branch; the design says a list of names may answer a "which" question, so that one is intended. The difference in A2-110-03 is that two items out of about a dozen listed features is a minor part of the answer. Severity is my judgement; the owner may read it as the intended "at least one part".

### A2-110-05: The trace can show a later sentence picked and passed while the answer opened on something else
- Severity: minor (trace only; inside this phase's change)
- What: every tier B pick and stands-alone check that finishes before the return is appended to the run's decisions (`_decide_point` appends each record to `_run_decisions(harness).records`), whether or not it decided the opening. Nothing in the record says "not used". When tier A is late, the trace holds `write.lead_later_sentence first` and `write.lead_stands_alone stands_alone` and no `write.lead_sentence` record at all, while the answer opened on the count line.
- Reproduction: case T1 (the quoted title, A2-110-02), branch run 0, my spy on `_decide_point` in finish order: `lead_later_sentence first 255 ms`, `lead_stands_alone stands_alone 269 ms`, `lead_sentence CANCELLED 1002 ms`; result None, the count line. A cancelled call never returns a record, so only the first two reach the run's decisions. The builder's own live table shows the same mix on runs that opened on tier A ("two checks (yes, needs_earlier), tier A first"). The `done` payload itself was read in code, not captured in this round.
- Why it matters: anyone reading a trace to learn why an answer opened as it did (the review loop, the owner's retests) sees a later sentence chosen and cleared, and may file a defect against the wrong path or miss a real one.
- NOT FIXED

## What did not break

- Pointer and leaning sentences in third place, 23 shapes, 5 runs each on the branch: "As does ...", "The latter is ...", "Such patients ...", "... are the others.", "Changes in the gene ...", "Both are ...", "... is one too.", "However, it is also ...", "MFS" defined only in an earlier sentence, "Features of the syndrome include ...", "In these patients, ...", "The second trial ...", "The drug ...", "A third tests ... / A fourth looks at ...", "The same holds for ...", "... is the fourth.", "Of these, ...", "... of them.", "Two more are ...", "The remaining ones are ...", "Respectively, these are ...", "Above all, ...", "... follow.", and from live run hcm_genes_2 "The gene NCBIGene:1756, named dystrophin, is also associated [13]." and "... is another linked gene [17].". Count line in every one of those runs; where the check was asked it said `needs_earlier` every time.
- Minor-part or wrong-part answers: PARP inhibitor sensitivity for a diseases question, cause instead of features, the Ghent criteria for a features question: count line 5 of 5 each. "Clinical features include glaucoma [27]." for the features question: count line 5 of 5.
- The gain, replayed myself on the builder's five gain groundings: branch opened on the answering sentence 23 of 25 (the other two the 1 s bound), develop 0 of 25.
- Losing develop's opening: tier A is the same call. Across 340 replays per tree, tier A was late (cancelled at the bound) 2 times on the branch and 6 on develop. One live branch run (brca_dis_1) lost a tier A opening to the bound; replaying its grounding gave the same opening 5 of 5 on both trees, so that was a Jev tail, and the sentence lost was "Changes in this gene ...", develop's own known weakness.

## Time to first sentence

| Measure | Develop | Branch |
|---|---|---|
| Tier A's own call, 340 replays, median / p90 / p95 ms | 215 / 295 / 387 | 224 / 313 / 381 |
| Whole lead call, median / p95 ms, at or over 1000 | 215.5 / 477, 6 | 245 / 486, 7 |
| Whole lead call when the count line follows tier A's "neither", median / p95 / max ms | 214 / 349 / 993 | 253 / 570 / 1004 (A2-110-04) |
| Live runs, lead call median / max ms | 214 / 637 (23 runs) | 208 / 1002 (23 runs) |
| Live runs, lead start to first summary line, median / max s | 0.24 / 0.66 | 0.23 / 1.08 |
| Live runs, first summary line from query start, median s | 10.47 | 11.04 (writer and tool variance; the lead call is under 0.3 s of it) |

## Live runs, branch against develop

Setup: `core/run.py` `run_streaming`, `reads_placement=True`, `CLASSIFIER_PROVIDER=jev`, `GUARD_MODEL` and `PLAN_MODEL` deepseek/deepseek-v4-flash, `SYNTH_MODEL` z-ai/glm-5.2, `PER_QUERY_COST_CAP_USD=0.25`; interaction capture, session memory load and remember-turn stubbed; user database, Redis and database URLs unset. One live run per question, depth and tree (cost), then every grounding with sentences replayed 5 times through `_lead_sentence_choice` on both trees with live Jev. "Live" is what that run opened on; "replay" is opens per 5 on develop / branch for that grounding.

| Question | Depth | Live runs | Develop opened on | Branch opened on |
|---|---|---|---|---|
| Which diseases are associated with BRCA1? | Plain | 1 + 1 | count line (replay 5 of 5 count line on both) | count line, tier A late at 1002 ms (replay of its grounding: "Changes in this gene ..." 5 of 5 on both trees, tier A) |
| Which diseases are associated with BRCA1? | Researcher | 1 + 1 | "BRCA1 mutations are responsible for approximately 40% ..." (replay 5/5 both) | "BRCA1 is associated with four diseases: ..." (replay 5/5 both) |
| What phenotypic features are associated with Marfan syndrome? | Plain | 1 + 1 | features sentence (5/5 both) | features sentence (5/5 both) |
| same | Researcher | 1 + 1 | features sentence, second (5/5 both) | features sentence (5/5 both) |
| Which clinical trials have tested drugs for Marfan syndrome? | Plain | 1 + 1 | count line (5/5 both) | "Five clinical trials have tested drugs for Marfan syndrome: ..." (5/5 both) |
| same | Researcher | 1 + 1 | count line (5/5 both) | count line; its grounding "Another tested losartan versus atenolol ..." opens 4/5 develop, 5/5 branch in replay, tier A, older weakness |
| What treatments are available for cystic fibrosis? | Plain, Researcher | 2 + 2 | count line, no grounded prose | count line, no grounded prose |
| How does the CFTR F508del variant cause disease? | Researcher, Plain | 2 + 2 | count line | count line (replay 5/5 both) |
| What are the clinical features of Huntington disease? | Plain | 1 + 1 | features sentence, second (replay 4/5 develop, one late; 5/5 branch) | features sentence, second (5/5 both) |
| same | Researcher | 1 + 1 | features sentence (5/5 both) | features sentence, second (5/5 both) |
| Which genes are associated with hypertrophic cardiomyopathy? | Researcher | 1 + 1 | "NCBIGene:1674 (desmin) [12], ..." (replay 1/5 both) | count line (replay 0/5 both) |
| same | Plain | 1 + 1 | count line, no grounded prose | "Associated is NCBIGene:10142, named A-kinase anchoring protein 9 [4]." tier A first (replay 5/5 both) |
| Is rs429358 associated with Alzheimer disease? | Researcher, Plain | 2 + 2 | count line (5/5 both) | count line (5/5 both) |
| What drugs target EGFR in lung cancer? | Plain, Researcher | 2 + 2 | count line (5/5 both) | count line (5/5 both) |
| Which clinical trials are recruiting for Duchenne muscular dystrophy? | Researcher | 1 + 1 | "Six clinical trials are listed for Duchenne muscular dystrophy: ..." (5/5 both) | code-built listing line, no grounded prose |
| same | Plain | 1 + 1 | count line (5/5 both) | count line (5/5 both) |
| How does losartan work in Marfan syndrome? | Plain, Researcher | 2 + 2 | count line (5/5 both) | count line (5/5 both) |
| How does ivacaftor work in cystic fibrosis? | Plain | 1 + 1 | count line, no grounded prose | count line, no grounded prose |

No live run on either tree opened on a sentence from tier B: the writer put an answer in the first two cited sentences or nowhere in these 46 runs. The tier B openings this round came only from the hand cases and the builder's gain groundings.

Spend: live runs 0.3997 USD (48 runs including two setup runs), plus about 800 replays of the lead decision at up to four Jev calls each, about 0.04 USD. Under the 0.60 USD budget.

## Verified by my own probes, and only read

- Probed: every finding above; the title filter on 17 disguised titles (pure code); which disguises and leaning shapes the grounding pass keeps (`run_grounding_pass` on saved findings); 800 live Jev replays on both trees; 46 live runs; tier A and whole-call latency; the builder's gain groundings.
- Only read: that a decision record reaches the `done` payload (A2-110-05, code and the builder's table); the builder's unit tests and mutations (not run this round); behaviour with the guard tier as classifier (not exercised).

## Verdict

FAIL: A2-110-02 (major, a paper title opens the answer through a pair of curly quotation marks, 6 of 10 against develop's 0 of 10, inside the new title filter) and A2-110-03 (major by my reading, a verbless two-feature fragment opens the features answer, 4 of 5 against 0 of 5, inside the new tier B path). Minor: A2-110-01, A2-110-04, A2-110-05. All five sit inside this phase's own change, which fires the review loop's stop condition.
