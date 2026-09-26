# Build phase 8.6, builder L report

Builder L's record for tickets T-8.6-06 (the stray "no clinical features" sentence), T-8.6-04 (the guardrail's injection verdict) and T-8.6-05 (the question class). Findings are written here the moment they are established, newest section last.

## Table of contents

- [Baseline, before any change](#baseline-before-any-change)
- [Findings](#findings)

## Baseline, before any change

Live runs on the unchanged worktree (develop at 2c6374f), `CLASSIFIER_PROVIDER=jev` set in the run's own process only, researcher depth, no session memory. Script: the builder's scratchpad copy of `testing/Developer/reports/2026-09-25_phase_8.1/builder_a_live_run.py`, extended to record each event's own timestamp. Times are seconds from the start of the run to each event.

| Question | Guard event | Think event | Plan event | Think step (think minus guard) | Outcome | Cost |
|----------|-------------|-------------|------------|--------------------------------|---------|------|
| How many genes are associated with breast cancer? | 1.01 | 2.73 | 3.02 | 1.72 | ask | $0.0171 |
| What is Marfan syndrome? | 1.24 | 2.87 | 3.18 | 1.63 | answer | $0.0179 |
| does coffee help exercise performance | 2.84 | 5.04 | 5.06 | 2.20 | answer | $0.0217 |

What a person saw before the change:

- Breast cancer: the answer lists "Medgen title: Seen by breast cancer nurse [2]. Medgen clinical_features: MedGen lists no clinical features for Seen by breast cancer nurse [3]." and never gives a count of genes. The stray sentence reproduces.
- What is Marfan syndrome?: the definition from a PubMed abstract comes second, then a "Clinical Features" heading with ten features the question did not ask for.

The tracebacks the script prints come from session memory and interaction capture refusing a run with no owner id; the script passes `user_id=None`, as builder A's did. They do not touch the answer.

## Findings

Written as established.

### L-01: isort's single-file form fails `core/graph.py` on HEAD too; the CI gate's form passes

- `isort --check-only src/system_03_search_agent/core/graph.py` reports an ordering change on the `ResolvedEntity as EventResolvedEntity` import, a line this work does not touch. The same command on HEAD's copy fails identically.
- `isort --check-only src tests` (CI gate 2's own form) passes: `graph.py` is in isort's skip list in directory mode ("Skipped 1 files" for `src/system_03_search_agent/core`).
- Every other changed file passes the single-file form.

### L-02: T-8.6-06 live, the Marfan phenotype question at researcher depth

Worktree with T-8.6-06 only (before the T-8.6-04 and T-8.6-05 changes), `CLASSIFIER_PROVIDER=jev`, $0.0346, outcome `answer`.

- Decision: `think.asks_features` picked `asks_features` by Jev at confidence 1.0.
- The prose names 11 features, each with its own marker, all cited to MedGen record 44287: Aortic regurgitation, Arachnodactyly, Congestive heart failure, Pes planus, Micrognathia, Ectopia lentis, Astigmatism, Glaucoma, Esotropia, Exotropia, Hypertropia. Acceptance (at least five) met.
- Rough edge a reader will notice: one grounded fragment reads "Pes planus [5] and Micrognathia [6]." as its own sentence.
- Elapsed 83.7 s with the guard event at 5.4 s. The unit suite was running on the same machine at the time, so these timings are not used for the speed comparison.

### L-03: T-8.6-06 live, the Marfan phenotype question at plain-language depth, with Jev timing out

Same worktree state, $0.0187, trust outcome `ask`.

- Jev timed out on all three decisions of this run (`fallback_reason: timeout`), so the guard tier decided each one. `think.asks_features` went to `asks_features` by the guard. This is the fallback path working live, not a planned test of it.
- The prose names 11 features in one sentence, each with its own MedGen marker: "MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], ... Hypertropia [11] and Micrognathia [12]." Acceptance (at least five, at both depths) met.
- The Think step took 16.1 s on this run, against 1.6 to 2.2 s at baseline. The cause is the pre-existing `think.recent_years` read inside Think, which waits for the guard's fallback pick once Jev has timed out. `think.asks_features` is not awaited in Think, so it adds nothing here. Builder K's T-8.6-01 owns how long a fallback may take.

### L-04: T-8.6-04 asks the injection decision only when Jev is the classifier; with the default provider the guardrail is unchanged

The brief asks for two things that cannot both hold if the decision is asked under every provider:

- The injection verdict becomes `decide(point="guardrail.injection")`.
- Every existing test in `tests/system_03_search_agent/guardrail` still passes.

Why they collide: those tests run with the provider at its code default ("guard"), where `decide()` asks the guard tier through its own generic prompt. Their model mock answers every call with the classifier's JSON, which names neither option, so the decision would have no usable pick and every admitted question would fail closed. `test_the_guardrail_makes_exactly_one_model_call` would also see two calls. The Playwright backend (`tests/e2e_support/mock_llm_backend.py`, outside this fence) answers the same way, so the whole end-to-end suite would die at the guardrail, the failure its own docstring records twice.

What was built, decided from the chair of the person typing a question:

- `CLASSIFIER_PROVIDER=jev` (develop): the injection verdict is Jev's pick, asked beside the classifier call after the unchanged pre-filter. The classifier still runs, for its off-topic field only. The forbidden screen still runs after, in the same place. No usable pick from either model is today's classifier failure path, a `recoverable` step error from the guardrail, never an admission.
- Provider at its default (production): the guard tier decides injection through the existing classifier call alone, one model call, byte for byte as before. Asking the guard tier the same question again through `decide()` would add a model call to every question and replace an instruction measured against real injection payloads (F-4.7-A-01) with an unmeasured generic one.
- What a person notices: on develop, whether their question is treated as an attack is Jev's call. On production, nothing changes until the product owner switches the provider.
- The gate is `core.graph._jev_decides()`, which reads `CLASSIFIER_PROVIDER` exactly as `harness/decide.py` does. If builder K renames that variable, this line must follow.

Break-it check: removing the line that applies the decision's pick turned both "Jev decides" arms red, and letting a missing pick through turned the fail-closed arms red. Restored after.

For the lead: `docs/architecture/Model_architecture.md` (outside this fence) still describes the guardrail's injection verdict as the guard tier's classifier alone, and lists the decisions on develop without `guardrail.injection`, `think.asks_features` or `think.query_class`.
