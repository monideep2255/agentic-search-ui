# Build phase 8.1: good questions stop failing

Branch: `phase/8.1-good-questions-answer`. Opened 2026-09-25 05:05 UTC.

The first phase of the overnight plan, `testing/Overnight_build_plan_2026-09-25.md`. It fixes the failures a person hits on a good question: a refusal where the product answers on other runs, a citation check that fails, a verdict or a paper list that changes between identical runs, a phenotype question answered with the wrong kind of record, and the source ceiling that tells most answers they are incomplete.

This phase is not in Section 25. Phases 8.1 to 8.5 are the product owner's To do column (`testing/UI_fix_plan.md`), numbered after Section 25's last phase, 7.1, by the product owner's approval of the overnight plan on 2026-09-25 (`DECISIONS.md`).

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [History](#history)
- [Findings](#findings)

## Goal contract

- Done when: every ticket below meets its acceptance, the pull request's CI is green, one judge round and one adversary round leave no blocking finding after one fix-and-verify, and the golden run on develop after merge answers at least 86 of 150.
- Verify: each ticket's named test command; five repeated live runs for every answer-path ticket, per the product owner's rule of 2026-09-13; the golden consistency run after merge.
- Output: one pull request from this branch; this file's Evidence and Findings; entries in `testing/Test_queries_and_workflows.md` and Retest cards for what goes live.
- Constraints: every rule under `.claude/rules/`; the cite-or-refuse gate stays exact; no database migration; no model swap; no edit to a locked document; no hardcoded decision (a decision is a classifier's call, code only verifies); no test question or its answer text used as a prompt example.
- Blocked-stop: a ticket whose fix needs a file outside its builder's fence, a locked-document edit, a migration, or a product choice nobody made stops, writes its finding here, and the builder moves to its next ticket.

## Budget

- Wall clock: 8 hours from 05:05 UTC.
- Dispatches: 8. Planned: 3 builders, 1 judge, 1 adversary, 1 fix agent, 1 product reviewer, 1 spare.
- Golden floor: 86 answered of 150, the 2026-09-22 run at `63ec316`.
- Answer path: yes. The golden run blocks.

## Tickets

### T-8.1-01: A good question never comes back as a refusal because the think step's reply was malformed

Status: in-review, builder A, `0020941`: a mislabelled key is repaired and a failed validation is retried with the error, never defaulted; 10 of 10 live runs answered
Card: 2, item 12.17
Builder: A
Files: `src/system_03_search_agent/core/graph.py` and its tests

Acceptance:
- `Does coffee help make exercise more effective?` and `is there a trial recruiting for melanoma`, at researcher depth, answer on 5 of 5 local live runs each
- A plan-tier reply that does not match the think classification schema is repaired or retried with the validation error, and never turned into a default classification
- A unit test replays the malformed replies that caused the two refusals

### T-8.1-02: An answer can cite up to 30 sources, and a question about papers can reach 30

Status: in-review, builder A, `b843ba0`: `_MAX_CITATIONS_PER_ANSWER` and `_MAX_FINDINGS_FOR_MODEL_PROMPT` 20 to 30, `_MAX_FINDING_TOTAL_BYTES` 50,000 to 70,000; about $0.017 per paper question, cap $0.10
Cards: 6 and 43
Builder: A
Files: `src/system_03_search_agent/core/graph.py` (`_MAX_CITATIONS_PER_ANSWER`), `src/system_03_search_agent/harness/coordinator_worker.py` (`_MAX_FINDING_TOTAL_BYTES`), and their tests

Acceptance:
- `_MAX_CITATIONS_PER_ANSWER` is 30 and `_MAX_FINDING_TOTAL_BYTES` is 70,000, and every value derived from the old 20 is found and either follows or is stated as deliberately independent
- A paper question with long abstracts reaches more than 22 cited sources on a local live run
- The per-question cost stays under the $0.10 per-query cap on 3 local live runs of a paper question, with the measured cost recorded here

### T-8.1-03: No search takes two minutes when the median is fourteen seconds, or the cause is written down

Status: diagnosed, not fixed (F-8.1-05); card 22 stays in To do
Card: 22
Builder: A
Files: `src/system_03_search_agent/core/graph.py` if the cause is there; otherwise none

Acceptance:
- The 127-second run of 2026-09-20 is diagnosed from the record and, if needed, a local reproduction, and the cause is written under Findings with its evidence
- If the cause is already fixed by a later commit (for example `2bc8ec0`), that is shown, not assumed; if it is a small fix in `core/graph.py`, it is fixed with a test

### T-8.1-04: `What genes are associated with MODY?` passes its citation check

Status: in-review, builder B, commit `49edfd0`: stacked citations checked against the union of the findings they cite, still exact; 5 of 6 live runs answer
Card: 21
Builder: B
Files: `src/system_03_search_agent/synthesis/grounding.py` and its tests

Acceptance:
- The question answers with cited genes on at least 5 of 6 local live runs
- The gate is not weakened: every accepted sentence still traces to exact record text, or passes the approved model check of 2026-09-23
- A unit test replays the failing case

### T-8.1-05: The trust line stays the same when the evidence is the same

Status: in-review, builder A, `a61d894`: the conflict flag is computed over the full retrieval, not the grounded subset; 3 live runs gave one verdict; builder B's determinism test `2a32799`
Card: 20
Builder: B
Files: `src/system_03_search_agent/synthesis/trust.py` and its tests

Acceptance:
- The verdict for byte-identical evidence is identical on every run, shown by a unit test that computes it five times from one fixture, and by the cause being named under Findings
- The tier logic's meaning is unchanged: only the instability is removed

### T-8.1-06: A phenotype question names phenotypes

Status: in-review: builder C's parser `888016d`, builder A's wiring `a41c20b` and listing preference `e4a8b85`; all 30 of Marfan syndrome's clinical features show in the code-built listing, cited to MedGen, at both depths (2 live runs); the model's own prose does not name them (F-8.1-06)
Card: 1, item 12.14
Builder: C
Files: `src/system_03_search_agent/tools/ncbi_eutils_actions.py`, `src/system_03_search_agent/tools/ncbi_efetch.py`, `src/system_03_search_agent/tools/ncbi_efetch_schemas.py`, and their tests

Acceptance:
- `What phenotypic features are associated with Marfan syndrome?` names at least five phenotypic features, each cited to its MedGen record, at both depths, on 5 of 5 local live runs
- The features come from the `ClinicalFeature` entries of MedGen's ESummary `conceptmeta` block (70 for Marfan syndrome, measured live 2026-09-25), parsed with external entities disabled, capped in count and length
- When MedGen lists no clinical features, the answer says so rather than substituting another record type
- The field is recorded under Findings as a Section 6.2 reconciliation item, as the gene summary was

### T-8.1-07: The same question returns the same papers each time

Status: deferred: not reproducible tonight, fix reverted (F-8.1-03); card 19 stays in To do
Card: 19
Builder: C
Files: `src/system_03_search_agent/core/breadth_plan.py` and its tests

Acceptance:
- The cause of six identical PubMed searches returning two result sets (2026-09-23) is named under Findings
- Six identical local runs of the GERD question return one set of papers
- No decision is hardcoded: a search term built from resolved entities is code composing, a routing choice stays a classifier's call

### T-8.1-08: An NCBI outage no longer turns the build red

Status: in-review, builder C, `55c389a`: the unit gate deselects the live test, the integration gate selects it
Card: 38
Builder: C
Files: `tests/system_03_search_agent/core/test_answer_readability_premise.py`

Acceptance:
- The live NCBI call in that file is behind the `integration` marker, and the unit gate as `.github/gates/` runs it makes no live call from this file

## Coverage: what this phase does not cover

- Moving any decision to Jev: phase 8.2.
- The check-and-adjust step, the empty-graph answer, the drafted-search disclosure: phase 8.3.
- The trust line's wording (card 16): phase 8.4. T-8.1-05 changes stability only.
- The golden run measures default depth only; the product reviewer asks three answered questions at each depth.

## History

- 2026-09-25 05:05 UTC: phase opened by the lead; eight tickets written; builders A, B and C dispatched in parallel, each in its own worktree.
- 2026-09-25 07:20 UTC: builder A's follow-ups merged (T-8.1-05b, 06b, 06c); gates run for the pull request.
- 2026-09-25: builders B, C and A merged in that order; T-8.1-07's fix reverted (F-8.1-03); builder A resumed for T-8.1-05b and T-8.1-06b in `core/graph.py`.

## Findings

Written the moment a finding is established. Each: ID, status, raised by, severity, round.

### F-8.1-03: The same-papers fix changed which papers are shown, and the variance did not reproduce

Status: closed by the lead: fix reverted (`e911956`), card 19 stays open
Raised by: the lead, reviewing builder C's T-8.1-07
Severity: medium: an unasked change to which papers every literature answer cites
Round: 0 (build)

Builder C's fix (`2f0c4e0`) fetched 30 PubMed ids and kept the 5 highest PMIDs, where before the 5 shown were the 5 most relevant. Its own evidence showed no variance to remove: 6 full-pipeline runs before the fix and 18 direct ESearch probes (immediate, 72 seconds apart, unauthenticated) each returned one set. Reverted, since relevance should not be traded for a stability nobody could show was missing. What builder C established stands: the PubMed term is a pure function of the resolved entity and ESearch sorts by relevance, so the 2026-09-23 variance, if it recurs, sits in NCBI's ranking boundary or in entity resolution (the `reflux disease` half is a Think-step model call). Card 19 stays in To do with this diagnosis.

### F-8.1-04: MedGen's clinical features are parsed but dropped before the writing model

Status: routed to builder A as T-8.1-06b
Raised by: builder C, T-8.1-06, confirmed with a live end-to-end run
Severity: high: without it card 1 is not fixed

`_parse_medgen_clinical_features` (commit `888016d`) returns 30 capped features for Marfan syndrome, but `core/graph.py`'s `_BREADTH_FIELDS_BY_PURPOSE["medgen_summary"]` (about line 5330) does not list `clinical_features`, so the field never reaches the writing model. The exact change is in `testing/Developer/reports/2026-09-25_phase_8.1/builder_C.md`.

### F-8.1-06: The writing model does not name the clinical features in its own prose

Status: open, for the product review's rubric line 1
Raised by: builder A, T-8.1-06b
Severity: medium: the features are on the page, in the code-built listing, but the answer's first sentences talk about something else

In 2 of 2 live runs the writing model grounded a different true fact (the genetic cause or the inheritance pattern) instead of the features. The lead ruled out changing `SYNTH_SYSTEM_INSTRUCTION` tonight: five earlier depth directives failed, and one instruction change touches every answer. The code-built listing now prefers a record's clinical features over its bare title (`e4a8b85`), so the reader sees them at both depths.

### F-8.1-05: The 127-second run outlived two 30-second timeouts

Status: open, card 22 stays in To do
Raised by: builder A, T-8.1-03
Severity: medium: one run in the 2026-09-20 set, and a timeout that does not stop its work is a latent risk on every query

Commit `2bc8ec0` does not explain it: that fix excludes the multi-hop class, which the HNF1A question belongs to, and lives in `tools/cypher_templates.py`. Two independent 30-second timeouts sat on the run's path, yet it took 127.1 seconds and succeeded, which points at a timeout that cancels the wait but not the work running in its thread. The fix is outside `core/graph.py`. Evidence: `testing/Developer/reports/2026-09-25_phase_8.1/builder_A.md`.

### F-8.1-01: The trust verdict varies because it is computed over whichever sentences the model's prose grounded that run

Status: confirmed; fix decided by the lead, routed to builder A (T-8.1-05b)
Raised by: builder B, T-8.1-05
Severity: high: an identical question shows a different trust line
Round: 0 (build)

`synthesis/trust.py` is deterministic, proven by `tests/system_03_search_agent/synthesis/test_trust_outcome_determinism.py` (five computations from one fixture, byte-identical). The variance is upstream in `core/graph.py`: the claims handed to `trust_for_claims` are the ones the model's prose grounded that run, and `_apply_conflict_flags_to_claim_trusts` floors a claim to `flag` from whichever Layer 1 and Layer 2 pairs land in that subset. Two live runs of one question gave different claim sets. Evidence: `testing/Developer/reports/2026-09-25_phase_8.1/builder_B.md`.

Decision, the lead's, from the reader's chair: builder B's option 2. The downstream floors (the conflict flag and the completeness and cap floors) are computed over `synth_findings`, the full retrieval, not over `grounding.claims`. The same evidence then gives the same trust line, and a real conflict in the evidence is flagged every time rather than on some runs. Option 1 (trust over every prepared finding) was rejected because the verdict would rest on records the answer does not state; option 3 (accept the variance) because an inconsistent trust badge on an identical question is what a reader would feel deceived by.

### F-8.1-02: A clause that abbreviates a disease name is rejected by the exact-match gate

Status: open, not fixed in this phase
Raised by: builder B, T-8.1-04, live run 4 of 7
Severity: low: the gate is right to reject it; the answer falls back to the code-built list for that clause

The writing model abbreviated a disease name in one MODY run, and the exact-match gate correctly rejected the clause. The fix is in the writing instruction, outside builder B's fence, and is not taken tonight.
