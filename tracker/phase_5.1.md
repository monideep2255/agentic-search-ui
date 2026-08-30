# Build phase 5.1: the 50-query golden dataset

Branch: `phase/5.1-golden-dataset-eval`. Opened 2026-08-30.

Section 25's row: "The 50-query golden dataset (expanding the seven-question moat set per the playbook), eval-harness grading wired against LangSmith trace output, the cost tracking dashboard". Depends on 3.4 and 5.0, both merged.

SCOPE NARROWED 2026-08-30, after review. This phase now delivers the DATASET only. The grading harness and the cost report moved to build phase 5.2 (`tracker/phase_5.2.md`) because both independent review rounds returned FAIL on the harness while both passed the dataset. Product-owner decision, logged in `DECISIONS.md`. Nothing was deleted and nothing was weakened: every harness module, arm and mutation case moved verbatim.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [Everything measured before any change was made](#everything-measured-before-any-change-was-made)
- [What already exists, and what this phase must not rebuild](#what-already-exists-and-what-this-phase-must-not-rebuild)
- [The decision this phase could not start without, now settled](#the-decision-this-phase-could-not-start-without-now-settled)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Flags this phase owns](#flags-this-phase-owns)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [What review found, and what it changed](#what-review-found-and-what-it-changed)
- [History](#history)

## What this phase is for

This is the instrument, not a feature. Every earlier phase measured itself with tests it wrote about code it had just written. This phase builds the thing that measures whether the agent's ANSWERS are correct, honest and cited, against a fixed set of questions authored independently of the agent.

Two of the board's open flags name this phase as the place they become measurable, and both are quality problems no offline check in this repository can currently see:

- The first answer grounds nothing on a single finding in about half of live runs, measured across twelve live runs at two commits on 2026-08-20. Cite-or-refuse then correctly refuses. The refusal is right; needing to refuse that often is a retrieval and synthesis quality problem, and there is no instrument that reports it.
- Build phase 4.5's depth-fingerprint arm is xfailed because live runs return 0 or 1 findings to synthesis, so the two audience depths have nothing to diverge on.

Neither is fixed here. This phase builds what can see them.

## Everything measured before any change was made

Measured 2026-08-30 at the branch point, on `develop` at `f2035de`.

| Fact | Value | How |
|---|---|---|
| Branch point | `f2035de`, working tree clean | `git status --short` |
| Doc drift | 0 stale, 0 structural, 10 facts computed | `python tracker/check_doc_drift.py --check` |
| Transports | product-model ok 131ms, harness-model ok 112ms, graph ok 515ms via the HTTPS query service | `python3 tracker/preflight.py` |
| Python tests at the branch point | 4543 | `check_doc_drift.py` |
| Frontend tests at the branch point | 235 | `check_doc_drift.py` |
| Existing eval surface | `tests/system_03_search_agent/eval/test_write_step_eval_gate.py`, build phase 2.2's component gate | `find` |
| Existing rubric surface | `src/system_03_search_agent/feedback/rubric.py`, `rubric_outcome_for` only | `grep` |

THE GRAPH IS REACHABLE FROM THIS SESSION, which several earlier phases could not say. Live verification is available rather than deferred.

## What already exists, and what this phase must not rebuild

- `feedback/rubric.py` computes `rubric_outcome` (`pass`, `fail`, `abstain`) deterministically at zero LLM cost on every live row. Its own docstring states that `rubric_score` (0 to 16) "is populated only by build phase 5.1's offline replay". So this phase POPULATES a field an earlier phase deliberately left `None`; it does not redesign the outcome model.
- `tests/.../eval/test_write_step_eval_gate.py` is the CITATION SYNTHESIZER component gate, and its own header says the full 8-point gate over the must-pass questions "is NOT runnable today and is not run here. Claiming it as passed would be false." It became runnable when the seven tools merged. This phase is where that sentence stops being true.
- Build phase 5.0 shipped LangSmith per-run tracing joined on `trace_id`. Section 23 requires graders to be built against that trace output rather than blind re-runs, so a grading pass does not re-execute the agent loop.

## The decision this phase could not start without, now settled

HOW THE 50 EXPECTED ANSWERS ARE AUTHORED. Recorded before any code, because it is the one choice that cannot be corrected later: a wrong expected answer certifies a wrong agent forever, and it does so with a green gate.

SETTLED 2026-08-30 by product-owner decision, logged in `DECISIONS.md`. The dataset pins CONSTRAINT ASSERTIONS authored independently of the agent, never full reference prose and never the agent's own curated output.

What a row pins:

- Required CURIEs the answer must have resolved.
- Required source records that must appear as citations.
- Forbidden behaviours, such as rendering a pathogenicity verdict or omitting assembly context.
- The expected outcome class (`answer`, `refuse`, `ask`, `flag`).
- Provenance: the live source the constraint was read from, the date it was read, and the bound on the sign-off.

The two rejected options and why, kept because the reasons are the load-bearing part:

- Curating from the agent's own runs was rejected as CIRCULAR. Anything currently wrong that the reviewer does not personally catch becomes the certified correct answer permanently, behind a green gate.
- Full reference prose was rejected on MAINTAINABILITY rather than on rigour. Pinning prose for LLM-generated output breaks the fixture every time the agent rewords a CORRECT answer, and a fixture that fails on correct behaviour creates standing pressure to weaken the check, which `.claude/rules/goal-contracts.md` names as a failed run rather than a completed one.

The split this buys: the dataset pins what must be TRUE, the playbook's 8-point rubric grades how well it was said. Neither does the other's job.

STATE THE SIGN-OFF'S BOUND wherever the dataset's provenance is written: the expected answers are signed off by the product owner rather than by an external clinical or human-variation reviewer, so the sign-off's authority is bounded by that. This is the playbook's own flagged gap ("Domain sign-off: name who signs off the golden fixtures for clinical and human-variation questions"), narrowed rather than closed.

## Goal contract

Written before the first change, per `.claude/rules/goal-contracts.md`.

Done when:

- A versioned golden dataset file holds 50 queries, each carrying its question, wedge type, personas, query class, the assertions its answer must satisfy, its expected outcome class, its hard-fail applicability, and the PROVENANCE of its expected answer: who authored it, when, and against which live source record.
- The 8-point rubric from `requirements/Evaluation_playbook.md` scores a run 0, 1 or 2 per criterion, with the 13-of-16 threshold, and the three hard-fails are checked on every run regardless of total score.
- The outcome model composes as the playbook states: the rubric grades ONE run into pass, fail or abstain, and pass@k plus pass^k aggregate those across k samples. Abstain-as-pass holds: zero retrieval plus a correct refusal is a pass, never a fail.
- The harness grades against LangSmith trace output rather than re-executing the loop, per Section 23.
- The coverage metric reports concept and predicate coverage as TWO separate ratios, computed from the Cypher the agent actually emitted rather than hand-mapped, and it is reported as a diagnostic that gates nothing.
- The cost tracking dashboard reports per-query and per-run cost from the data build phase 5.0 already records.
- `rubric_score` is populated on replayed rows, closing the field `feedback/rubric.py` left for this phase.

Verify surface, immutable for the run:

- A premise gate whose every arm is proven red by a mutation, with the mutation case added IN THE SAME EDIT as the arm, per build phase 4.15's rule.
- Every bound arm carries the populate-check from build phase 4.11: an arm that cannot distinguish the control holding from nothing having happened is not an arm.
- The grader is proven against a KNOWN-BAD answer as well as a known-good one. A rubric that only ever sees good answers is the vacuous-arm shape this repository has filed in five separate phases.
- An arm proving abstain-as-pass and an arm proving abstain-as-FAIL are separate, since the playbook distinguishes them by whether a correct source existed, not by whether an answer appeared.
- The full Python suite against a baseline re-measured at this branch point.
- `ruff check` over the WHOLE repository with no path argument, per build phase 4.15's CI finding.
- `isort --check-only`, per F-5.0-30: `/verify` did not run it until PR #84, so it is named explicitly here.
- `python tracker/check_doc_drift.py --check` at 0 stale, 0 structural.

Constraints:

- The dataset is a VERSIONED FILE loaded from the repository, never a live database read, per `.claude/rules/prompt-cache-discipline.md`'s few-shot rule and for the same reason: a changing source defeats reproducibility even when it returns the same content.
- The eval gate is a MILESTONE gate, run before an answer-generation feature ships and before every release, never on every pull request. It makes real model calls and carries real cost and latency, per Section 23.
- Every live API call the dataset build makes respects its tool's rate-limit pool, per `.claude/rules/tool-call-budgets.md`. Variation Services at roughly 1 request per second is the tightest.
- No expected answer is authored by asking the agent under test what the answer is, whatever the final decision above, without that circularity being stated in the row's own provenance field.
- The coverage metric never becomes a gate. The moat set is engineered narrow and scores low on breadth by construction; gating it on breadth would pressure set-padding.
- Locked documents are not edited.

Blocked-stop:

- Any question in the 50 whose expected answer cannot be established from a live source record is recorded as UNVERIFIED and excluded from the gate rather than guessed at. This is the blocked-stop that matters now that the authoring decision has landed: an unverifiable constraint is dropped, never inferred, and never taken from the agent's own output.
- A live source needed to establish a constraint being unreachable stops that row, not the phase. The row is recorded UNVERIFIED with the reason and the gate reports its own reduced denominator rather than silently grading 49 as if it were 50.

## Tickets

All ten tickets are open as of 2026-08-30. T-5.1-02 was blocked on the dataset-authoring decision above and is unblocked by it.

| Ticket | Wave | Deliverable | Files it may touch | Status |
|---|---|---|---|---|
| T-5.1-01 | 1 | The golden dataset SCHEMA and loader: the versioned file format, per-row provenance and sign-off fields, and validation that refuses a row missing provenance | `src/system_03_search_agent/eval/dataset.py` | done |
| T-5.1-02 | 1 | The 50 questions themselves, expanding the seven must-pass moat set, including the LEARNINGS.md curation pass | `eval/golden/` | done |
| T-5.1-03 | 1 | The 8-point rubric grader: 0, 1 or 2 per criterion, 13 of 16, deterministic where the criterion allows it | `src/system_03_search_agent/eval/rubric_grader.py` | MOVED to 5.2 |
| T-5.1-04 | 1 | The three hard-fail checks, evaluated on every run regardless of total score | `src/system_03_search_agent/eval/hard_fails.py` | MOVED to 5.2 |
| T-5.1-05 | 2 | pass@k and pass^k aggregation over per-run outcomes, with the playbook's two target levels | `src/system_03_search_agent/eval/aggregate.py` | MOVED to 5.2 |
| T-5.1-06 | 2 | Grade against LangSmith trace output rather than re-running the loop, per Section 23 | `src/system_03_search_agent/eval/trace_source.py` | MOVED to 5.2 |
| T-5.1-07 | 2 | The coverage metric: concept and predicate ratios from observed Cypher, reported and never gating | `src/system_03_search_agent/eval/coverage.py` | MOVED to 5.2 |
| T-5.1-08 | 2 | The cost tracking dashboard over the data build phase 5.0 already records | `src/system_03_search_agent/eval/cost_report.py` | MOVED to 5.2 |
| T-5.1-09 | 3 | Populate `rubric_score` on replayed rows, closing the field `feedback/rubric.py` left open | `src/system_03_search_agent/feedback/` | MOVED to 5.2 |
| T-5.1-10 | 3 | The premise gate and its mutation harness for the DATASET arms (P1, P8, P9), one mutation case per arm added in the same edit. The 25 harness arms and 28 harness mutation cases moved to 5.2 | `tests/system_03_search_agent/eval/` | done |

## Flags this phase owns

Carried in from the board and the continuation prompt, each with the reason it landed here.

| Flag | What it is | Why 5.1 |
|---|---|---|
| Golden fixture domain sign-off | Nobody was named to verify the clinical and human-variation expected answers | Narrowed 2026-08-30: the product owner is the sign-off owner. The BOUND on that sign-off is stated rather than the gap closed |
| Curate LEARNINGS.md into the golden eval dataset | The bare-number and common-word weak-match cases from 3.3, the third-person clinical questions from 3.0, the two-gene dropped answer from 3.4, the `NOT`-in-query risk from 3.5. Real "a user could ask this and get a confidently wrong answer" cases, pinned only as narrative and scattered unit tests | Needs a real curation pass against the playbook rubric, not a bulk copy. Most LEARNINGS rows describe internal plumbing, not realistic user questions |
| F-4.5-07 depth fingerprint unmeasurable | The P2b arm asserts `deep_technical` surfaces a raw identifier and `clinical_brief` surfaces none. Correct property, unmeasurable while retrieval returns 0 or 1 findings | Becomes measurable when the harness measures retrieval quality across 50 questions |
| First answer grounds nothing on a single finding, about half of live runs | Measured 2026-08-20 across twelve live runs at two commits. Invisible to every offline check because it only appears against the live graph | This is the instrument built to measure exactly this |
| Section 23 offline gate | Deferred at Step 6.2 rather than run early, because running it before the tools merged would be setup work redone properly here | Scheduled here by product-owner decision, 2026-08-10 |

## Coverage: what this phase does not cover

Stated at open rather than discovered later, per `.claude/rules/goal-contracts.md`'s rule that a verify surface must state its own coverage. To be extended as arms are written.

- THE DATASET IS NOT A BREADTH INSTRUMENT. The moat set is engineered narrow: first-pass concept coverage is about 5 of 10 and predicate coverage about 3 of 14. A green gate here says the agent answers THESE questions correctly and says nothing about the other 10 predicates.
- THE RUBRIC GRADES ONE RUN. Reliability is the aggregate's job, and a single green run proves neither pass@3 nor pass^3.
- COMPUTE-TOOL QUESTIONS ARE OUT OF SCOPE by the PRD's v1 boundary: no BLAST, no sequence-similarity search, no VCF ingestion. Q2, Q7 and Q9 are the fast-follow set and are not in the 50.
- ACMG CLASSIFICATION IS OUT OF SCOPE. The system assembles evidence and renders no verdict, and "rendered a verdict" is a hard-fail rather than a scored criterion.

### P8's mutation, run by hand on 2026-08-30

Recorded here rather than automated, and the reason is stated rather than assumed: P8's subject is the shipped 50-row dataset on disk, so an automated mutation case would need write access to the very artifact the arm exists to protect. `tests/.../test_phase_5_1_mutation.py` names P8 in its `_EXEMPT_ARMS` mapping and points here.

The mutation: take the first row that pins a CURIE and flip its provenance to `authored_from: locked_requirements`, `source: Evaluation_playbook.md`, which is precisely the shape of a row asserting a fact about a specific NCBI record without anyone having read that record.

Result: `test_p8_... FAILED` at the `authored_from == "live_source"` assertion. The dataset was then restored from a backup taken before the mutation, and the full gate re-run green.

### The coverage claim is computed rather than written

Build phase 4.15 filed the same defect THREE times: a mutation harness asserting complete coverage in a comment, the second assertion written inside the fix for the first, naming an uncovered arm as covered. The first version of this phase's mutation harness did it a FOURTH time, claiming "twenty-two of thirty" when the truth was twenty-five, and listing four arms as unmutated that were mutated.

The fix is not a better sentence. `test_coverage_claim_is_computed_not_asserted` introspects both modules, derives which arms have a mutation case, and requires the difference to equal a declared exempt set carrying a reason per entry. Adding an arm without a mutation case fails the suite and names the arm. Proven by mutation: disabling the P7b case makes it fail with `arms with no mutation case: ['p1c', 'p3d', 'p7b', 'p8', 'p9e']`.

## Findings

| ID | Severity | What | Status |
|---|---|---|---|
| F-5.1-01 | major | THE VERDICT CHECK LAUNDERED A VERDICT USING THE VERDICT'S OWN WORD. `hard_fails.py`'s attribution list admitted a sentence containing the bare verb `reported`, on the theory that reporting implies a source. The premise gate's own P3b fixture is "This variant is pathogenic and should be reported as such", which attributes to nobody and contains `reported`, so the safety hard-fail would not have fired on the exact sentence it exists to catch. FIXED by narrowing attribution to mean NAMING A SOURCE: a citation marker, `according to`, or a named database. A bare reporting verb no longer qualifies. THE TRANSFERABLE PART: the laundering word was a substring of the verdict phrase itself, so the check's admit-list and its deny-list overlapped on the same token, and no amount of reading either list separately would show it | fixed |
| F-5.1-05 | CRITICAL | THE TRACE PARSER WAS WRITTEN AGAINST AN IMAGINED PAYLOAD AND RAISED ON THE FIRST REAL RECORD. `record_from_trace` read `outputs.answer`, `outputs.citations` and `metadata.cost_usd`. None of those exist. It had NO caller and NO test, so nothing in the phase distinguished it from working, while the goal contract asserted "the harness grades against LangSmith trace output". Proven by fetching a live run on 2026-08-30 from project `agentic-search-ui` and feeding it in: `ValueError: RunRecord requires a non-empty query_id`. TWO defects, and the second is structural: real `inputs` carries `query` not `question`, AND ONE TRACE IS NOT ONE RUN, it is a tree of per-node runs (`think`, `plan`, `act`, `write`, routers) sharing a `trace_id`, so no single run holds the answer. A field-name fix would have left the wrong premise intact. FIXED by parsing the system's OWN v1 typed event contract (`token`, `citation`, `trust_signal`, `tool_result`, `done`), which is versioned, additive-only and already what every other surface reads. Five P11 arms now parse a real captured payload, with five matching mutation cases. THE LESSON IS `attack-the-constraint`'s, learned the expensive way: when a component is fed by an assembly step, PRINT WHAT IT ACTUALLY RECEIVES before writing the code that consumes it. Found only because a coverage claim was being re-verified rather than trusted | fixed |
| F-5.1-04 | minor | THE LOADER HAD TWO PATHS TO A MISSING PROVENANCE AND ONLY ONE PRODUCED A USABLE ERROR. `_validate_row` reached the field with `raw["provenance"]`, so the required-field loop above it was the only thing standing between a caller and a bare `KeyError('provenance')` naming neither the row nor what was wrong. Not reachable through the shipped loader, since the loop runs first, which is exactly why reading the code would not surface it. FOUND BY THE MUTATION HARNESS: relaxing the first path to test whether the arm could fail exposed the second. Fixed with `raw.get(...)`, which the existing `isinstance` check already turns into a proper `DatasetValidationError`. THE TRANSFERABLE PART: a mutation harness looks for vacuous ARMS and also finds code whose only guard is an earlier guard | fixed |
| F-5.1-03 | major | THE PREMISE GATE WAS WRONG ABOUT THE DATASET AND THE DATASET WAS RIGHT. Arm P8 asserted every row's `authored_from` is `live_source`. When the real dataset existed, 17 rows were `locked_requirements`: a refusal row such as "What is the weather in San Francisco?" has no NCBI identifier to verify and draws its authority from Section 10.5 instead. This is `goal-contracts`' third case, where subject and check are each right about different things and the gate's output alone cannot distinguish it from an ordinary defect. RESOLVED by fixing the CHECK and making it STRONGER, not weaker: relaxing it to "authored_from is in the allowed set" would have removed its teeth entirely. P8 now asserts that no row is ever `agent_output`, that any row pinning a CURIE must be `live_source` AND must name a live lookup in its own provenance, and that at least 30 rows are live-verified so the arm cannot pass against a dataset that quietly stopped verifying. Proven red under mutation afterwards | fixed |
| F-5.1-02 | minor | THE P6 TRIPWIRE WOULD HAVE NAMED THE WRONG FUNCTION. Both tripwires closed over the loop variable rather than binding it, so either one firing would have appended the LAST name. The arm asserts an empty list so its verdict was unaffected, but its diagnostic was wrong: a real trip would have reported `run_streaming` even when `run` was what got called. Caught by `ruff` B023 over the whole repository, NOT by reading it. FIXED with a per-iteration binding. Recorded rather than dropped because it is the same class as build phase 4.13's finding: the arm was correct about the property and wrong about what it would tell you | fixed |

## What review found, and what it changed

Both rounds ran on 2026-08-30 with independent briefs and separate contexts.

| Round | Verdict | Findings | Report |
|---|---|---|---|
| Judge | FAIL | 15: 4 critical, 9 major, 2 minor | `tracker/phase_5.1_judge_report.md` |
| Adversary | FAIL | 26: 9 critical, 8 major, 2 minor, 7 informational | `tracker/phase_5.1_adversary_report.md` |

THE VERDICTS WERE AGAINST THE HARNESS, NOT THE DATASET, and that distinction is what the split rests on. Both rounds independently re-verified all 50 rows against live NCBI and found every identifier current and every symbol matched (A-5.1-26). The committed LangSmith fixture was confirmed free of PII and credentials (A-5.1-21).

Both rounds converged INDEPENDENTLY on the same worst defect, which is the strongest evidence this repository's review split can produce: `counts_as_pass` keys on `record.retrieval_hit_count`, a number the subject under test supplies, so an agent refusing all 50 questions scores pass@3 and pass^3 of 100 percent. Filed as F-5.1-J-08 by the judge and A-5.1-02 by the adversary, reached from different directions.

The measured headline: an answer whose entire prose is the word "Fabricated." passes 34 of the 50 rows.

Full detail, the ten fix tickets and the new goal contract are in `tracker/phase_5.2.md`. The findings keep their 5.1 identifiers deliberately, since renumbering would hide that they were found against this phase's code.

## History

- 2026-08-30: Phase opened. Branch cut from `develop` at `f2035de`. Preflight green on all three transports. Baseline measured. Goal contract written before any code. T-5.1-02 opened BLOCKED on the dataset-authoring decision.
- 2026-08-30: F-5.1-05 found and fixed, the phase's most serious finding. LangSmith now HAS a key (build phase 5.0 shipped with none and recorded "nothing is verified against live LangSmith" as its largest gap), so the claim was checkable for the first time and did not hold. A real payload was fetched, the parser raised on it, and the parser was rewritten against the v1 event contract. A PII-free fixture captured from the live service is committed at `tests/.../eval/fixtures/langsmith_trace.json`, with an arm asserting no account identifier survives in it. Gate now 35 arms, mutation harness 32 cases, 70 passed 1 skipped.
- 2026-08-30: PHASE SPLIT after review. Judge FAIL (15 findings), adversary FAIL (26), both against the grading harness and neither against the dataset. Rule 4 fired: A-5.1-05 sits inside the F-5.1-01 fix made earlier the same session. Escalated to the product owner rather than patched onward, per the review-loop rule. Decision: ship the dataset, hold the harness as build phase 5.2. This phase's deliverable is now the 50-query golden dataset, its loader, its builder and the method document, with 10 premise arms and 10 mutation cases covering them.
- 2026-08-30: T-5.1-09 and T-5.1-10 COMPLETE, which closes every ticket in the phase. `eval/replay.py` grades a set of trace-shaped records against the dataset and is the FIRST writer `interactions.rubric_score` has ever had, closing the field `feedback/rubric.py` left open since build phase 4.6. The write is an idempotent UPDATE keyed on `trace_id` and touches that one column, never `rubric_outcome`, which already has a live-path writer. The premise gate grew four P10 arms to 30, and the mutation harness covers 25 of them with the remaining 5 exempt for stated reasons. Suite for the phase: 60 passed, 1 skipped. F-5.1-04 filed, found BY the mutation harness rather than by review.
- 2026-08-30: T-5.1-02 COMPLETE. The 50-query golden dataset is built and every constraint is live-verified: 50 of 50 specs verified, 0 excluded, 43 live E-utilities calls in 6.4 seconds throttled to 8 requests per second. 24 KISS, 20 KISSES, 6 discovery carrying 18 follow-up turns, per the product owner's taxonomy of 2026-08-30. The verifier was proven able to REJECT before its 50-of-50 result was accepted as evidence: four rejections against two accepted controls, including a live re-confirmation of F-4.7-A-02 (gene 60500 BRCA3 returns status='1', currentid=675). Method written up in full at `docs/build/Golden_dataset_method.md`. Premise gate now 26 arms, all green. F-5.1-03 filed.
- 2026-08-30: Premise gate written at stage 5 and watched failing (collection error, no `eval` package). Then seven of ten tickets built: T-5.1-01, 03, 04, 05, 06, 07, 08. Gate now 20 of 21 arms green; the one red is P8, which asserts the real 50-row dataset loads and is T-5.1-02's job. `ruff check` clean over the whole repository, `isort --check-only` clean. Two findings filed, F-5.1-01 and F-5.1-02, both written by the lead and both caught by a check rather than by reading.
- 2026-08-30: Dataset-authoring decision SETTLED by the product owner: constraint assertions authored independently of the agent. Logged in `DECISIONS.md`. T-5.1-02 unblocked, all ten tickets open. The blocked-stop narrowed from the decision itself to the per-row case where a live source cannot be reached.
