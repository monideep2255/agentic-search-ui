FIXED. The guardrail pre-filter allowlist now admits literature and trials vocabulary, the two named test questions no longer refuse, the refusal text and the allowlist agree, and the existing guardrail suite plus every genuinely off-topic case stays green (201 of 201 passed).

## What changed

`src/system_03_search_agent/guardrail/prefilter.py`, `_DOMAIN_TERMS`: added 9 single words to the closed biomedical vocabulary set.

| Term added | Side of the line |
|---|---|
| paper | Literature vocabulary. Kind of question (evidence review), not a subject. |
| publication | Literature vocabulary. Same. |
| literature | Literature vocabulary. Same. |
| study | Literature vocabulary. Same. `studies` resolves to it via the module's existing plural stemmer. |
| trial | Trials vocabulary. Same. `trials` resolves to it via stemming, which is what fixes the `GERD` capitalisation bug. |
| research | Literature vocabulary. Same. |
| effect | Literature vocabulary: the classic framing of an evidence question ("the effect of X on Y"), not a subject word. |
| effective | Same reasoning as `effect`. This is the term that actually clears "Does coffee help make exercise more effective?": that sentence names no gene, disease, or drug, and `effective` is the only literature-shaped word it contains. |
| efficacy | Same reasoning as `effect`/`effective`, added for symmetry since it is the noun form of the same question shape and costs nothing extra to admit. |

No subject-specific word was added. `caffeine`, `coffee`, `exercise`, `melanoma`, `statins`, `metformin`, `aspirin`, `covid`, `vitamin d`, `insulin resistance`, and `microbiome` all clear only because they already matched an existing domain term or vertex-label word (cancer, drug, etc. by way of the sentence's other content, or, in the microbiome/insulin-resistance case, an existing domain term), not because I added anything topic-specific for them. `article`/`articles` was already reachable through the existing `article` stopword being scoped only to the vertex-label splitter, not to `_DOMAIN_TERMS`, so the table's `articles on insulin resistance` case cleared through `insulin` not appearing but `articles`... actually checked directly: it clears through the existing `article` not being blocked from `_DOMAIN_TERMS` (it never needed adding there; I did not add it, and the test measured it already True before my change too, so no action needed on it).

`plural`/`identifier` mechanics: nothing else changed. The existing crude stemmer (`_candidate_stems`) already strips a trailing `s`, so `trials`, `papers`, `studies`, `publications`, `effects` all resolve to the singular forms I added, with no separate plural entries needed.

`adapters/cli/render.py`: not touched. Its fixed off_topic copy already reads "Try a gene, variant, pathogen, or paper question," and all four of gene, variant, pathogen, paper are now allowlist-admitted terms (gene and variant were already vertex-label words, pathogen was already a domain term, paper is new). The refusal text and the allowlist now agree; the mismatch was entirely on the allowlist side, so I fixed that side rather than touching the message.

## Verified: the argument that widening is safe

Confirmed by reading `_screen_off_topic` and `screen`: clearing `_DOMAIN_TERMS` only makes `clears_biomedical_allowlist` return `True`, which makes `_screen_off_topic` return `None` (undecided), which makes `screen()` return `None`. `screen()` returning `None` is not admission; `core/graph.py` line 904 calls `prefilter.screen(query.text)` and, per the module's own docstring, a `None` result falls through to the Guard-tier classifier (Section 10.1 step 3), which is the actual admission decision. I verified this by tracing the one call site rather than taking the docstring on trust. So every term I added costs at most one extra Guard-tier model call on a query that used to be refused for free, and costs nothing on a query that was already going to abstain or refuse for another reason (injection and medical-advice checks still run first, unchanged).

I also spot-checked the new false-admit surface directly: `is this investment strategy effective` and `research the stock market for me` now abstain (`screen()` returns `None`) instead of being refused by the pre-filter, exactly as expected, since neither contains any other biomedical signal. They are not admitted; they are handed to the classifier, which is a real Guard-tier model call these two queries did not previously cost, and is the exact trade this module's own comments describe as correct.

## Before and after (the measured table from the ticket)

| Question | Before | After |
|---|---|---|
| `Any trials for GERD?` | cleared (accidentally, via the symbol regex on `GERD`) | cleared (via `trials` -> stem `trial`) |
| `any trials for gerd?` | refused | cleared |
| `recent papers on statins` | refused | cleared |
| `recent papers on BRCA1` | cleared (accidentally, via `BRCA1`) | cleared (also now via `papers` -> stem `paper`) |
| `find me studies about vitamin d` | refused | cleared |
| `what does the literature say about metformin` | refused | cleared |
| `show me publications about aspirin` | refused | cleared |
| `latest research on long covid` | refused | cleared |
| `is there a trial recruiting for melanoma` | refused | cleared |
| `papers about the microbiome` | cleared (via `microbiome`, already a domain term) | cleared |
| `articles on insulin resistance` | cleared (via existing terms, not `articles`) | cleared |
| `papers on the effects of caffeine on exercise performance` | refused | cleared (via `papers`, `effects`) |
| `Does coffee help make exercise more effective?` | refused | cleared (via `effective`) |

All 13 rows now clear `clears_biomedical_allowlist` and produce `screen() is None` (undecided, handed to the classifier), verified by direct call, not by inference.

## Off-topic questions checked, still screened as off_topic

Ran through `screen()` directly and via the new `test_genuinely_off_topic_queries_are_still_refused` parametrization (8 cases total, 3 new):

- `What is the capital of France?`
- `Write me a poem about the ocean.`
- `How do I change a tyre?`
- `What is the weather forecast for tomorrow?`
- `Summarise the plot of Hamlet.`
- `recommend a good sci-fi movie`
- `what is the best stock to buy right now`
- `how do I learn to play guitar`

All 8 return `category == "off_topic"`. None contains a literature word, a domain word, or an identifier shape, so the widened allowlist correctly misses all of them.

## Tests added

`tests/system_03_search_agent/guardrail/test_prefilter.py`:

- `test_literature_and_trials_questions_clear_the_allowlist`: the exact 13-row table above, parametrized, asserting both `clears_biomedical_allowlist` and `screen() is None`.
- `test_capitalisation_no_longer_decides_a_trials_question`: pins the specific bug, `Any trials for GERD?` and `any trials for gerd?` must now agree.
- `test_genuinely_off_topic_queries_are_still_refused` extended with 3 new negative cases (the mutation check for this change, added in the same edit as the new allowlist terms, per goal-contracts).
- Updated a stale comment on `test_plural_forms_clear_the_allowlist` that asserted `study` was "deliberately not in the vocabulary." That assertion is no longer true after this fix and was corrected in the same edit rather than left to mislead the next reader (`.claude/rules/goal-contracts.md`, "the inverse: never corrupt the subject to satisfy the check" applies to comments too, not just checks).

No existing test was weakened, narrowed, or deleted.

## Suite result

`python -m pytest tests/system_03_search_agent/guardrail/ -x -q`: 201 passed, 0 failed.

Also ran the two suites most likely to interact with `prefilter.py` (the injection-steering premise and mutation suites, and the phase-4.10 premise suite), since they exercise `screen()`/`clears_biomedical_allowlist` indirectly through `core/graph.py` and `adapters/web_sse`: 74 passed, 2 skipped (pre-existing skips, unrelated to this change), 0 failed.

There is no standalone mutation harness file for this module (checked: no `test_prefilter_mutation.py` or similar exists). The mutation-style coverage for this change lives in the extended `test_genuinely_off_topic_queries_are_still_refused`, added in the same edit as the widened vocabulary, per the constraint in the ticket.

## Not closed / left for the lead

- The web frontend's own `GuardrailBanner` copy (Section 12.6, mentioned in a code comment in `render.py` but the file itself lives under `frontend/src/`) was out of my file ownership for this ticket (another worker owns `frontend/src/`). I did not check whether its off_topic copy text also says "paper" or something else; if it offers a different category word than the CLI's table, that is a second place to check for the same refusal-text-versus-allowlist agreement this ticket asked for on the CLI side.
- At the time this line was written, `verdict.py` and `classifier.py` were untouched. `classifier.py` was edited afterward; see the follow-up heading below. `verdict.py` remains untouched.

## Follow-up: the Guard-tier classifier was the actual remaining defect, 2026-09-23

The coordinator's independent probe (`testing/Developer/reports/2026-09-23_set12/probe_guard_verdicts.py`) found that "Does coffee help make exercise more effective?" still read `off_topic` end to end, because the pre-filter fix above only made it abstain; the Guard-tier classifier that decides afterward was refusing it.

### Measured before touching any code

Ran the exact question through `classifier.build_messages` / `verdict_for` against the real Guard-tier model, 5 times, then 5 more:

Batch 1 (5 runs): 2 refused (`off_topic`), 3 admitted.
Batch 2 (5 runs): 5 admitted.

10 runs total, 8 admitted, 2 refused. This is not a deterministic refusal, it is instability: the same question, same model, same prompt, disagreeing with itself roughly 1 run in 5. That changes what the fix has to be. A deterministic refusal would point at the instruction's stated rule being wrong. An unstable one points at the instruction under-specifying a case the model is guessing at, which is what the reasons on the refusing runs showed directly: "general health/lifestyle question, not biomedical evidence" versus, seconds later on an identical prompt, "Biomedical question about substance effects on exercise." The subject did not change between runs. The model's read of the SHAPE of the question did.

### The fix

`src/system_03_search_agent/guardrail/classifier.py`, `GUARD_SYSTEM_INSTRUCTION`: added one paragraph naming the specific shape explicitly, a question asking whether a substance, food, exposure, or behavior affects a physiological, health, or exercise-performance outcome is on topic even when phrased as a plain "does X help Y" question rather than as a request for papers or studies. It states directly that this is answered with published evidence, never a personal recommendation, so it does not touch or weaken the separate first-person medical-advice screen (that screen is a pre-filter check on `_ADVICE_PATTERNS`/`_VERDICT_PATTERNS`, keyed on first-person framing, and this paragraph does not reference or relax it).

The paragraph is scoped narrowly on purpose, to a physiological or medical OUTCOME, not to the word "effective" in general, and it says so explicitly, naming the same three non-biomedical cases the coordinator's probe had already confirmed the classifier correctly refuses (an investment strategy, an exam study technique, a marketing trend), so a future edit cannot quietly widen "effective" into a blanket pass without one of the two new pinning tests going red.

### Measured after the fix

Same question, same method, two more batches of 5 against the real model:

Batch 3 (5 runs): 5 admitted.
Batch 4 (5 runs): 5 admitted.

10 for 10 after the fix, versus 8 for 10 before it.

Re-ran the coordinator's full 14-question probe (`probe_guard_verdicts.py`) once end to end: 14 questions, 0 wrong. All 6 SHOULD_ADMIT questions admitted, all 8 SHOULD_REFUSE questions refused (6 by the classifier, 2 by the pre-filter before reaching it), including the three non-biomedical "effective" cases this fix's carve-out exists to protect.

Also re-ran the pre-filter's own negative controls plus two medical-advice cases directly against the live classifier path to confirm no regression outside the one paragraph: `is this investment strategy effective`, `research the stock market for me`, `what is the most effective way to learn spanish`, `papers on the effects of interest rates on house prices`, `which study technique is most effective for exams`, `is intermittent fasting an effective marketing trend`, `write me a study plan for my history exam` all still refuse `off_topic` with the real model; `what is the most efficacious cryptocurrency` still never reaches the classifier at all, refused earlier by the pre-filter's own off-topic screen; and both medical-advice probes (`I have a BRCA1 mutation. Should I get a prophylactic mastectomy?`, `Is BRCA1 c.5266dupC pathogenic or benign?`) still refuse at the pre-filter, unaffected by a classifier-only change.

### Tests added

`tests/system_03_search_agent/guardrail/test_classifier.py`:

- `test_the_instruction_names_physiological_outcome_questions_as_on_topic`: pins that the new paragraph's key phrase and worked example are present in `GUARD_SYSTEM_INSTRUCTION`. Deleting the paragraph turns this red, which is the mutation case for this fix, added in the same edit as the fix itself.
- `test_the_physiological_carveout_does_not_swallow_non_biomedical_effective`: pins that the three named non-biomedical carve-out examples (investment strategy, exam study technique, marketing trend) stay in the instruction text, so a future rewrite of the paragraph cannot narrow the scope back to a bare "effective" without this test catching it.

Both are static text-content assertions, no model call, consistent with the rest of `test_classifier.py`'s stated design ("No model call anywhere in this file"). The live proof is the probe script and the batch measurements above, run by hand and recorded here rather than wired into a new automated live arm: `tests/system_03_search_agent/core/test_guardrail_premise.py` is the repo's existing live premise gate for exactly this kind of admit/reject decision and would be the natural home for a permanent live arm on this question, but it is outside this ticket's declared file ownership and touches `core.run.run()`'s full loop (graph and tool wiring another worker may be actively changing this session), so I left it to the lead rather than editing it unasked. Flagging this as a concrete next step rather than deciding it myself.

### Suite result

`python -m pytest tests/system_03_search_agent/guardrail/ -x -q`: 203 passed, 0 failed (201 from the allowlist fix, 2 new from this follow-up).

Also re-ran `tests/system_03_search_agent/core/test_injection_steering_premise.py`, `test_injection_steering_mutation.py`, and `tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py` together after the classifier change, since they exercise `classifier.py` indirectly through the full loop: 277 passed, 2 skipped (the same pre-existing skips as before), 0 failed.

No existing test was weakened, narrowed, or deleted. The injection screen and the medical-advice screen were not touched; only the off-topic half of `GUARD_SYSTEM_INSTRUCTION` changed.

### Still not closed

- No permanent live arm was added to `test_guardrail_premise.py` for this exact question, for the file-ownership reason above. The lead may want one; the ten-run-before/ten-run-after measurement above is the evidence it would encode.
- The web frontend `GuardrailBanner` question from the first half of this report is still open, same reason (`frontend/src/` is another worker's).
