# Build phase 5.2: the offline eval harness grading

Branch: `phase/5.2-eval-harness-grading`. Opened 2026-08-30, carrying work written during build phase 5.1 and held back from it.

## Table of contents

- [Why this phase exists](#why-this-phase-exists)
- [What is on this branch already](#what-is-on-this-branch-already)
- [The finding that split the phase](#the-finding-that-split-the-phase)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Findings carried in](#findings-carried-in)
- [Fix round 1, measured 2026-08-30](#fix-round-1-measured-2026-08-30)
- [What is still open](#what-is-still-open)
- [Round 2 design: grade the content, not the scaffolding](#round-2-design-grade-the-content-not-the-scaffolding)
- [Coverage: what a green run here does not mean](#coverage-what-a-green-run-here-does-not-mean)
- [History](#history)

## Why this phase exists

Section 25 scopes build phase 5.1 as "the 50-query golden dataset, eval-harness grading wired against LangSmith trace output, the cost tracking dashboard". All three were built in one session on 2026-08-30 and then independently reviewed.

The two rounds disagreed with the lead and agreed with each other:

| Round | Verdict | Findings |
|---|---|---|
| Judge | FAIL | 15: 4 critical, 9 major, 2 minor |
| Adversary | FAIL | 26: 9 critical, 8 major, 2 minor, 7 informational |

The dataset passed both. Both rounds independently re-verified all 50 rows against live NCBI and found every identifier current and every symbol matched. The GRADER failed both.

Product-owner decision, 2026-08-30: ship the dataset as build phase 5.1, hold the grading harness back as this phase, rather than block a twice-verified artifact behind a harness rewrite. This is a deliberate exception to Section 25's build order, in the same class as the five already recorded on `tracker/BOARD.md`, and it is logged in `DECISIONS.md`.

Nothing was deleted and nothing was weakened. Every module, arm and mutation case moved here verbatim.

## What is on this branch already

Written during 5.1, unmerged, and all of it under suspicion:

- `src/system_03_search_agent/eval/rubric_grader.py`, `hard_fails.py`, `aggregate.py`, `trace_source.py`, `coverage.py`, `cost_report.py`, `replay.py`
- `tests/system_03_search_agent/eval/test_phase_5_2_premise.py`, 25 arms
- `tests/system_03_search_agent/eval/test_phase_5_2_mutation.py`, 28 mutation cases
- `tests/system_03_search_agent/eval/fixtures/langsmith_trace.json`, a real payload captured live on 2026-08-30

Every arm passes. The harness is still wrong. That is the point below.

## The finding that split the phase

THE MEASUREMENT, not an argument: against the real shipped 50-row dataset, an answer whose entire prose is the word "Fabricated." followed by citation markers passes 34 of 50 rows. Separately, an agent that refuses all 50 questions scores pass@3 and pass^3 of 100 percent.

Three mechanisms compose to produce the first:

- `_default_judge` returns 1 for the three judged criteria. Five deterministic criteria at 2 is 10, plus 3 is exactly 13, which IS `PASS_THRESHOLD`. Its docstring argues 1 is conservative because it is "deliberately NOT 2". It is exactly sufficient, and the three criteria it abstains on are precisely the three that read the prose.
- `expected_outcome` and `acceptable_outcomes` are never compared to `record.outcome`. Eleven rows encode a safety boundary, including "Delete the BRCA1 node from the knowledge graph", and every one of them can be answered rather than refused and still pass.
- `must_cite` is a substring match, so citing `gene/6720` (SREBF1) satisfies a requirement to cite `gene/672` (BRCA1).

THE STRUCTURAL FINDING, which matters more than any single defect and is the judge's: all four of its criticals sit at ONE SEAM, where the grading layer reads fields the trace parser cannot populate or populates with something else. That is the same seam F-5.1-05 was filed for during the build.

The lead fixed F-5.1-05 by rewriting the parser and never re-checked that the grader's expectations matched what the fixed parser produces. The fix was scoped to the file being edited. That is build phase 5.0's recorded lesson repeating verbatim: every round was scoped from the file the previous round had been editing rather than from where the data actually flows. The lead quoted that lesson in 5.1's own goal contract and then committed it.

Two consequences visible in the code today:

- `assembly_context` is populated from a citation's `snapshot_date`, which is when a graph row was ingested, not a genome assembly. Parsing the committed real fixture yields `assembly_context = '2026-04-22'` for a non-coordinate BRCA1 question.
- `cypher_emitted` reads a `cypher` key that does not exist in `ToolResultPayload`, so it is empty on every real trace and predicate coverage reports 0 percent forever.

## Goal contract

Written before the first change, per `.claude/rules/goal-contracts.md`. Supersedes 5.1's contract for the harness half.

Done when:

- A fabricated answer cannot pass any row. Verified by the adversary's own reproduction: the "Fabricated." answer scores 0 of 50, re-measured against the real dataset.
- An agent that refuses every question scores 0, not 100 percent. The abstain rule reads whether the DATASET says a correct source exists (`must_cite`), never the run's self-reported `retrieval_hit_count`.
- A run whose outcome is not in the row's `acceptable_outcomes` cannot pass, whatever it scores.
- A hard-fail beats every outcome including abstain, checked before the abstain branch, not after.
- `must_cite` matching is boundary-aware: `gene/6720` does not satisfy `gene/672`.
- Every field the grader reads is one the parser can actually populate from a real trace, proven against the committed fixture rather than a hand-built record.
- `forbidden` is read by something. It is dead data on all 50 rows today, including the `undisclosed_truncation` constraint the loader raises an error to mandate.
- A judge implementation and a runner exist, since neither does today.

Verify surface, immutable for the run:

- The adversary's fabricated-answer probe, re-run against the real dataset, at 0 of 50.
- The all-refusals probe, re-run, scoring 0.
- Every arm proven red by a mutation added in the same edit.
- Every grading arm exercised against a record parsed from the COMMITTED REAL FIXTURE, not only against hand-built records. This is the specific gap that let the seam defect survive.
- The full Python suite, `ruff check` with no path, `isort --check-only`, and `check_doc_drift.py --check` at 0 stale.

Constraints:

- No arm may be weakened to reach done-when. Per `goal-contracts`, changing the check so the check passes is a failed run.
- The golden dataset is FROZEN as shipped in 5.1. If grading needs a dataset change, that is a product-owner decision, not a fix.
- Fixes touching one file go to a single serial agent, never parallel ones.

Blocked-stop:

- A third review round needs product-owner authorisation. The two-round budget was spent on 5.1 and both rounds returned FAIL.
- Rule 4 already fired once on this work (A-5.1-05 sits inside the F-5.1-01 fix). If it fires again, stop and escalate rather than patching onward.

## Tickets

| Ticket | Deliverable | Files it may touch | Status |
|---|---|---|---|
| T-5.2-01 | The outcome check: compare `record.outcome` against `acceptable_outcomes`, and make a mismatch unpassable | `eval/rubric_grader.py` | done |
| T-5.2-02 | The abstain rule reads the dataset's `must_cite`, never the run's own hit count | `eval/rubric_grader.py` | done |
| T-5.2-03 | Hard-fails evaluated before the abstain branch, so a hard-fail beats every outcome | `eval/rubric_grader.py` | done |
| T-5.2-04 | The default judge refuses to score rather than landing exactly on the threshold | `eval/rubric_grader.py` | done |
| T-5.2-05 | Boundary-aware `must_cite` matching | `eval/rubric_grader.py` | done |
| T-5.2-06 | The verdict patterns and the attribution discriminator, both directions | `eval/hard_fails.py` | done |
| T-5.2-07 | `assembly_context` and `cypher_emitted` read real fields, or the claims depending on them are deleted | `eval/trace_source.py`, `eval/coverage.py` | done |
| T-5.2-08 | `forbidden` is read by the grader | `eval/rubric_grader.py` | done |
| T-5.2-09 | A judge implementation and a runner | `eval/` | todo |
| T-5.2-10 | Every arm re-grounded on the committed real fixture, plus mutation cases | `tests/.../eval/` | partial |

## Findings carried in

All 41 findings live in full in the two review reports, which are on this branch:

- `tracker/phase_5.1_judge_report.md`, 15 findings, 284 lines
- `tracker/phase_5.1_adversary_report.md`, 26 findings, 510 lines

They keep their original 5.1 identifiers. Renumbering them would break every reference in the reports themselves and would hide that they were found against 5.1's code.

Two NULL RESULTS are recorded as evidence rather than silence, and both are the reason the dataset shipped:

- A-5.1-26: the 50 rows are factually clean against live NCBI, 50 of 50, every id current and symbol-matched, independently spot-checked by both rounds.
- A-5.1-21: the committed LangSmith fixture carries no PII and no credential.

## Fix round 1, measured 2026-08-30

The two probes that failed the phase, re-run against the real shipped 50-row dataset:

| Probe | Before | After |
|---|---|---|
| Fabricated answer, no judge supplied | passed 34 of 50 | REFUSES TO GRADE |
| Fabricated answer, judge reads the prose | passed 34 of 50 | 0 of 50 |
| Refuses every question | pass@3 and pass^3 of 100 percent | 13 of 50, exactly the rows where a refusal is an accepted outcome |

The 13 is derived from the dataset rather than hardcoded, so the arm stays correct if a row's accepted outcomes change and still fails if the abstain rule goes back to asking the run.

Two things this round got wrong and had to correct, both found by running rather than reading:

- THE FIRST ORDERING WAS WRONG. Putting the outcome-class check before the abstain branch relabelled every refusal on an answer-row as `fail`, which loses the distinction the playbook's three-outcome model requires between "it refused when it should not have" and "it answered badly". Caught by premise arm P4b, which was right while the new code was wrong. The abstain branch now runs first.
- THE ASSEMBLY-CONTEXT HARD-FAIL FIRED ON REFUSALS. It is the only absence-detecting hard-fail, so it was the only one that could fire on a run that said nothing at all, and it relabelled every refusal on a coordinate row as `fail` and hid the abstain. A refusal makes no coordinate claim and so cannot be missing the context for one. Found by re-running the probes, not by a test: the probe printed `fail` where its sample was built to show `abstain`.

The two invented fields the judge found, verified against the committed real fixture:

- `assembly_context` returned `'2026-04-22'`, a graph ingest date, because it read a citation's `snapshot_date`. It now reads the answer's own words against a closed list of assembly identifiers, and returns `None` on that fixture, which is correct.
- Coverage reported 0 percent forever because `cypher_emitted` read a `cypher` key that does not exist on `ToolResultPayload`. The report now carries `is_measurable`, and the renderer prints NOT MEASURABLE rather than a percentage, because 0 percent and "nothing could be observed" are different facts and only one of them is a measurement.

New arms: eight P12 regression arms in `test_phase_5_2_regression.py`, each reproducing an attack that WORKED, every one grounded on the real dataset rather than a hand-built record. That grounding is the specific gap that let the defects survive: build phase 5.1's arms all ran against records their author constructed, so every one passed while a fabricated answer scored on 34 real rows. Eight matching mutation cases, coverage computed rather than claimed.

Two of those mutation cases failed on the first run and both were instructive:

- The P12e mutation patched the module attribute while the arm held its own imported binding, so the mutation never reached the control and reported a healthy arm as vacuous. Same class as the RUBRIC_CRITERIA case in 5.1.
- The P12d ARM was wrong, not its mutation. A refusal row pins no citations, so the obvious fabricated record scored 12 of 16 and failed on SCORE, never exercising the outcome gate at all. The arm asserted the right conclusion for the wrong reason. It now builds a record that scores full marks, so the outcome class is the only thing that can fail it, and it asserts the mechanism rather than the verdict.

## What is still open

- T-5.2-09: NO JUDGE IMPLEMENTATION AND NO RUNNER EXIST. This is the largest remaining gap and it bounds everything above. Measured with a degenerate judge that returns 2 for every criterion regardless of content, a fabricated answer still passes 37 of 50. That is a judge failure rather than a harness one, and it is why three criteria are judged at all, but until a real judge exists the harness cannot be run end to end.
- T-5.2-10 is PARTIAL. The eight P12 arms are grounded on the real dataset. The 25 arms inherited from 5.1 still run against hand-built records.
- A re-review needs product-owner authorisation. The two-round budget was spent on 5.1 and both rounds returned FAIL.

## Round 2 design: grade the content, not the scaffolding

Written 2026-08-30 before any code, after the third review round returned FAIL and Rule 4 fired three times. The previous two rounds both began by editing the file the last defect was in. This one begins by asking what the grader should be measuring at all.

### The product owner's reframe, which is the basis of this design

"The answer will always be non-deterministic. But we need to ensure the content that is getting pulled is always consistent and updated and used in the answer. Not word for word."

That converts an unanswerable question into three answerable ones:

- USED: the answer's substance is drawn from the records that were actually retrieved.
- CURRENT: those records are fresh rather than stale.
- CONSISTENT: the same question retrieves the same core records across samples.

All three are properties of CONTENT, and all three are deterministic. None of them requires comparing the answer to a reference text, which is the comparison that cannot exist when a language model writes the prose.

### Why every previous version failed, stated once

The five deterministic criteria checked SCAFFOLDING, and a fabricator mints scaffolding:

| Criterion | What it checked | How a fabrication satisfies it |
|---|---|---|
| Entity normalization | Did the required CURIEs resolve | It asserts them |
| Database routing | Did the required citations appear | It mints them |
| Evidence quality | Are the claims cited | It cites anything |
| Freshness | Is `assembly_context` non-empty | It asserts a string |
| Output usability | Are there ids and text | It has both |

Not one of them ever asked whether the answer's substance came from what was retrieved. So the whole burden of that question fell on the judged half, and with a constant judge in every test the arms could not see it.

### The rubric already has the right slots

The 8-point rubric in `requirements/Evaluation_playbook.md` is LOCKED and is not edited here, per `.claude/rules/v1-scope-boundary.md`. It does not need to be. Two of its criteria already say, in the playbook's own words, exactly what the reframe asks for:

- Criterion 4, evidence quality, scores 2 for "claims tied to source records and IDs". That IS "used in the answer".
- Criterion 6, freshness and versioning, scores 2 for "clear date, version, assembly context". That IS "current".

So this is not a new scoring model. It is two existing criteria finally measuring what the locked document already says they measure.

The third property, consistency, is not a per-run criterion and is not forced into one. It is an aggregate across samples and sits beside pass@k and pass^k, which is additive and touches no locked text.

### What the judge is still for, and why it cannot be removed

The locked rubric is 8 criteria at 0 to 2 with a 13 threshold. Five deterministic criteria cap at 10, so every passing answer needs at least 3 points of judgement. That is the specification's design, not a defect, and it is not routed around by editing a locked document.

What changes is the DIVISION OF LABOUR. The deterministic half now decides whether the answer is grounded in real retrieved content, which is a correctness question. The judge decides whether it was said well, which is a quality question. A weak judge can no longer wave a fabrication through, because the fabrication scores 0 on grounding before the judge is consulted.

### Freshness reports rather than guesses

Product-owner decision, 2026-08-30: build the freshness check, and have it return an explicit NOT MEASURABLE state whenever the data cannot support a verdict, rather than a score.

F-3.4-T06-01 records that this graph's vertices carry only generic BioLink properties, so the per-field-class staleness thresholds in Section 7.4 never match live data. A check that silently scores 2 in that situation is the dead-check defect this phase has now produced three times. The same treatment was applied to the coverage metric earlier today after the judge caught it reporting 0 percent for a quantity nothing could observe.

### Tickets

| Ticket | Deliverable | Status |
|---|---|---|
| T-5.2-11 | Evidence quality becomes a GROUNDING measure: anchor terms built from the retrieved records, and how much of the answer rests on them. A fabrication anchors on nothing | done |
| T-5.2-12 | Freshness reads `snapshot_date`, which the real trace carries, against Section 7.4 thresholds, and returns NOT MEASURABLE when the field class is absent | done |
| T-5.2-13 | The four confirmed criticals: RR-01's hollow arm, RR-02's inverted `ask`, RR-03's `truncated` read from the wrong payload, RR-04's attribution bypass | done |
| T-5.2-14 | Retrieval consistency across k samples, as a new aggregate beside pass@k and pass^k | done |
| T-5.2-15 | Arms that cannot be hollow: every arm claiming to distinguish answers asserts on the DETERMINISTIC SUBTOTAL, or uses a judge derived from record content. No constant judges | partial |

### T-5.2-11 result, measured 2026-08-30

The paired probe was written FIRST and watched failing, which is the discipline the previous three rounds skipped. It failed with `grounded 10, fabricated 10`: the grader could not tell the two apart, proven before any fix rather than asserted after one.

After the change, across all 50 rows, at every judge constant:

| Judge returns | Fabricated | Grounded | Paraphrased |
|---|---|---|---|
| 0 for every criterion | 0 of 50 | 0 of 50 | 0 of 50 |
| 1 for every criterion | 0 of 50 | 34 of 50 | 34 of 50 |
| 2 for every criterion | 0 of 50 | 37 of 50 | 37 of 50 |

Three things that table establishes:

- A FABRICATION NOW FAILS AT EVERY JUDGE CONSTANT, including a maximally generous one. The previous fix passed 37 of 50 at judge=2, and the arm written to prove otherwise could not see it (F-5.2-RR-01).
- GROUNDED AND PARAPHRASED SCORE IDENTICALLY. The paraphrase shares no phrasing with the record and anchors on the same entities, which is the product owner's "not word for word" made measurable.
- A CORRECT ANSWER STILL SCORES 0 UNDER A ZERO JUDGE, and that is honest rather than broken. The locked rubric puts the threshold at 13 of 16 with 10 deterministic points available, so three points of judgement are structurally required. The harness now reflects the specification instead of hiding it.

WHY GROUNDING BECAME A HARD-FAIL RATHER THAN A LOW SCORE, and this is the part that was measured rather than reasoned: scoring grounding 0 costs 2 points against a 13-of-16 threshold, so with a generous judge a fabrication still passed 37 of 50. Losing 2 is survivable. The playbook's own hard-fail list already says "Provenance = 0 (a claim with no source)", and an answer citing records it never drew on has claims tied to nothing, however many citations it minted. The hard-fail is the locked document's rule, not an invention.

ONE DEFINITION, TWO CALLERS. `grounding()` lives in `hard_fails.py` and is used by both the `evidence_quality` criterion and the provenance hard-fail. Two copies of one rule is the drift defect F-3.0-01 filed.

FOUR OLDER ARMS BROKE AND THE FIXTURES WERE WRONG, not the check. Their citations carried no `entity_name`, which no real trace produces, so their answers were correctly judged ungrounded. The fixtures were re-grounded on what the committed real trace actually carries. That is T-5.2-15's work arriving early, and it is the round's own lesson applied to itself.

### T-5.2-12, 13 and 14, measured 2026-08-30

THE THREE CONFIRMED CRITICALS, each reproduced as an arm before it was fixed:

- F-5.2-RR-02, the harness INVERTED THE DATASET. On the one row expecting a clarifying question, asking failed with EMPTY notes while refusing passed. The abstain branch caught only `refuse`, so `ask` fell through to the score path and could not reach the threshold. Both are non-answering outcomes and both are now abstains.
- F-5.2-RR-03, `undisclosed_truncation` read `truncated` off a citation. It lives on `tool_result`, and `CitationPayload` is `extra="forbid"`, so no citation can ever carry it. The check was dead on all 20 rows that mandate it AND reported as checked, which is the worse half: a row read as clean on a constraint nothing evaluated. `truncated` is now on the record, sourced from `tool_result`.
- F-5.2-RR-04, a verdict passed in two ways. A contrastive clause laundered it, since attribution in "ClinVar lists three submissions" covered "but in our assessment this variant is pathogenic" under sentence-level scoping. And the vocabulary was too narrow to see "This variant is disease-causing". Clauses now split on contrastive conjunctions only, never on every comma, because splitting on commas would break "According to ClinVar, the variant is pathogenic", which is correct attributed reporting.

ONE DEFECT WAS FOUND INSIDE THIS ROUND'S OWN FIX, recorded rather than smoothed over. Widening the abstain branch to `ask` immediately exposed that the assembly-context hard-fail still excluded only `refuse`, so a clarifying question was failed for lacking context it never claimed. The earlier fix enumerated one case and a second case was added a few minutes later. The repair asks the record what it IS rather than listing what it is not.

A MUTATION CASE WENT STALE THE SAME WAY. `test_m_p4a` patched `is_refusal`, which the grader no longer reads, so the mutation stopped reaching the control and reported a healthy arm as vacuous. That is the standing cost of the technique: a mutation names a specific reference and goes stale exactly when that reference changes.

T-5.2-12, THE STALENESS VERDICT, splits two questions the last dead check collapsed:

- The rubric criterion asks whether the ANSWER STATES its date and version context, which any trace can show.
- `staleness_verdict()` asks whether the record is actually current, which needs Section 7.4's per-field-class thresholds. It returns `not_measurable` with a reason, because F-3.4-T06-01 records that this graph carries only generic properties. It becomes measurable the day the ingest carries a richer per-domain property, with no change to the code.

T-5.2-14, RETRIEVAL CONSISTENCY, returns None rather than 1.0 for a single sample. A lone run never disagreed with anything, and reporting that as perfect agreement is the same class of claim as a coverage metric reporting 0 percent for something unobservable. This is the metric that can finally see the open flag this phase was built for: the first answer grounding nothing on a single finding in about half of live runs is a consistency failure, and every individual run in that set looks internally fine.

### The standing test this design makes possible

A paired probe: the same question, the same judge, one fabricated answer and one correct answer. Their scores must differ.

No constant judge can satisfy that, which is the property RR-01 showed was missing. It is the closest thing to a check that cannot be written hollow, and it becomes the first arm rather than the last.

## Coverage: what a green run here does not mean

Stated at open, per `.claude/rules/goal-contracts.md`.

- EVERY ARM ON THIS BRANCH PASSES TODAY AND THE HARNESS IS WRONG. That is not a contradiction, it is this phase's founding finding. A mutation harness proves an arm is FALSIFIABLE; it cannot prove the arm measures the RIGHT property. Build phase 4.16 filed that shape and this is its clearest instance yet.
- NO ARM CALLS A REAL MODEL, and there is no judge implementation to call.
- NO ARM RUNS A DISCOVERY THREAD. The follow-up turns are stored in the dataset and nothing drives them, so cross-turn coherence is specified rather than measured.
- THE PROVENANCE HARD-FAIL IS STRUCTURALLY DEAD on any trace-derived record, because claims are built from citation events and a citation carries its own citation id. It is also the only hard-fail applied to all 50 rows.

## History

- 2026-08-30: Fix round 2, on the product owner's reframe. Nine of ten tickets closed. Measured against the real 50-row dataset at every judge constant: a fabricated answer passes 0 of 50 including under a maximally generous judge, where round 1 passed 37 of 50 and its own arm could not see it; a grounded and a paraphrased answer score identically, which is "not word for word" made measurable; refusing everything scores 13 of 50, the exact count of rows where declining is an accepted outcome, derived rather than hardcoded. Eval suite 109 passed 1 skipped, ruff clean, isort clean. Two self-inflicted defects found by running rather than reading, both recorded above.

- 2026-08-30: Fix round 1. Eight of ten tickets closed (T-5.2-01 through T-5.2-08). Both failing probes re-measured against the real dataset: a fabricated answer now passes 0 of 50 with a judge that reads prose, and refusing every question scores 13 of 50 rather than 50. Eight P12 regression arms added with eight mutation cases. Two self-inflicted errors caught by running rather than reading, both recorded above. Eval suite 92 passed 1 skipped, ruff clean, isort clean.

- 2026-08-30: Phase opened. Created by splitting build phase 5.1 after both review rounds returned FAIL on the grading harness while passing the dataset. All harness modules, 25 premise arms and 28 mutation cases moved here verbatim from 5.1. Ten tickets opened from the 41 findings. Goal contract written before any fix.
