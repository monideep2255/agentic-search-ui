# Live measurement on develop, 30 runs, 2026-09-20

Thirty live runs against the deployed develop app on commit `6e4aae1`, five questions asked six times each, every run in a fresh guest session. Run with `testing/Developer/reports/2026-09-19_verification/measure_with_errors.py 6`. Raw per-run detail is in `baseline_6e4aae1.json`, the console record in `baseline_6e4aae1.log`.

## Table of contents

- [Summary](#summary)
- [Reliability](#reliability)
- [Finding L-01: the same question returns three different source sets](#finding-l-01-the-same-question-returns-three-different-source-sets)
- [Latency](#latency)
- [What this measurement does not cover](#what-this-measurement-does-not-cover)

## Summary

Two results, one good and one a defect.

- Reliability is fixed, or at least is not reproducing. 30 of 30 runs answered with no fatal `error` event and no transport error. Added to the 15 of 15 measured on 2026-09-19, that is 45 consecutive live runs with no failure, against 48 of 53 on 2026-09-14.
- Determinism is NOT met, and this is a live defect against UI fix 11.21's own requirement that "the same question must always show the same number and set of sources". One of the five questions returned three different source sets across its six runs.

## Reliability

| Question | Depth | Answered | Median | Slowest |
|---|---|---|---|---|
| Which diseases are associated with BRCA1? | researcher | 6 of 6 | 12.9s | 27.3s |
| What diseases are caused by variants in the HNF1A gene? | researcher | 6 of 6 | 13.9s | 23.8s |
| Variants in GCK causing MODY | researcher | 6 of 6 | 16.1s | 30.3s |
| What genes are associated with MODY? | researcher | 6 of 6 | 9.7s | 21.9s |
| Which diseases are associated with BRCA1? | plain_language | 6 of 6 | 7.8s | 26.8s |

No `error` event was emitted on any run, so there is still no captured payload for the 1 in 10 failure seen on 2026-09-14. The instrumentation that would capture it is in place and ran; it had nothing to capture. The failure is not reproducing rather than diagnosed, and that distinction matters: nothing has been fixed that is known to have caused it.

Outcome tiers across the 30 runs: 27 `ask`, 3 `answer`. Both are answered states. `ask` is the trust tier rendered as "Based on N sources, not yet confirmed", not a clarifying question put back to the reader. That was established and corrected on 2026-09-19 in `../2026-09-19_verification/live_check.md`.

## Finding L-01: the same question returns three different source sets

Severity: major. Live on develop now, before any of tonight's changes. Owner: the 11.21 broad-search wiring, since determinism is half that ticket.

"What diseases are caused by variants in the HNF1A gene?" at researcher depth returned three distinct source sets across six identical runs:

| Runs | Sources | What is present | What is missing |
|---|---|---|---|
| 2, 3, 5, 6 | 18 | Gene 6927, `@GENE_HNF1A`, 5 ClinVar rows, 6 MedGen concepts, 5 trials | Nothing, this is the full set |
| 1 | 13 | Gene, `@GENE_HNF1A`, 6 MedGen concepts, 5 trials | All 5 ClinVar rows |
| 4 | 8 | Gene, `@GENE_HNF1A`, 1 MedGen concept, 5 trials | All 5 ClinVar rows and 5 of 6 MedGen concepts |

Two things are worth separating, because they point at different causes.

- The ClinVar rows and most MedGen concepts vanish entirely on two runs of six. That is a whole Layer 1 result going missing, which graceful degradation then hides: the answer still ships, cited, with no visible gap.
- On run 1 the MedGen set is not a subset of the full set. It carries `MedGen:C1840646` and `MedGen:CN074294`, which appear in none of the four full runs, and lacks `MedGen:C0342276` and `MedGen:C3888631`, which appear in all four. A different six were selected, not a truncation of the same six. That is the signature of an unordered result feeding a cap: the graph returns rows in whatever order the planner produced them, and the cap keeps a different six each time.

The constant part across all six runs is the gene record, the PubTator gene annotation and the five ClinicalTrials.gov identifiers. Every varying source is graph-derived. So the variance is in the Layer 1 path, not in Layer 2 or Layer 3.

The other four questions each returned exactly one source set across six runs, so this is not a general nondeterminism across the whole product. HNF1A is the question with the largest graph result, which fits both hypotheses above.

This was measured before the broad-search wiring landed, so it is a pre-existing defect that the wiring must fix rather than one the wiring introduced. A stable sort on the graph result before the cap is the obvious candidate, and the missing-ClinVar shape needs its own cause found rather than assumed.

## Latency

Medians run from 7.8 to 16.1 seconds and the slowest single run was 30.3 seconds. That is at or better than the 2026-09-14 figures the plan records (median 19.7, slowest 53). Any change that adds calls to the hot path is measured against these numbers.

## What this measurement does not cover

Stated so a green result is not read as wider than it is.

- Only five questions, all gene-centred or disease-centred. No variant-first, no literature-first, no off-topic, no injection attempt.
- Guest sessions only. No signed-in user, no session memory, no follow-up turn.
- The web app is never loaded. This drives the API directly, so it proves nothing about rendering, pacing or bold.
- Thirty runs cannot measure a 1 in 10 failure to a tight bound. Zero failures in 30 is consistent with a true rate anywhere below roughly 1 in 10, so this says the failure is not reproducing, never that it is gone.
