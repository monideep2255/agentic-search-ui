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
