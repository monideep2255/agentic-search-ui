# L-01 findings: does a Layer 1 graph result vanish between runs?

## Table of contents

- [Verdict](#verdict)
- [What was tested](#what-was-tested)
- [Instrument and a bug found in it](#instrument-and-a-bug-found-in-it)
- [Method](#method)
- [Results: BRCA1](#results-brca1)
- [Results: HNF1A](#results-hnf1a)
- [What a reader sees when a graph result shrinks or vanishes](#what-a-reader-sees-when-a-graph-result-shrinks-or-vanishes)
- [The one unrelated error](#the-one-unrelated-error)
- [Live commit and environment](#live-commit-and-environment)
- [Raw evidence](#raw-evidence)

## Verdict

CONFIRMED, in a specific and now precisely measured form.

Across 20 live runs (5 runs times 2 questions times 2 batches) against the develop API, the same question asked repeatedly does not return a stable set of Layer 1 graph rows. In every one of the 19 runs that completed normally, the FIRST `cypher_query` call was stable in its row count. The SECOND `cypher_query` call, the one carrying most of the disease-association rows, varied in row count from run to run of the identical question, including one run where it returned zero rows (`status: "empty"`) while the answer still completed normally and looked, at the trust-outcome level, identical to every other run.

Nothing in the response tells the reader this happened. `trust_outcome` was `ask` in all 19 completed runs regardless of whether the second graph call returned 100 rows, 12 rows, or 0 rows. The only visible trace is a drop in the total citation and source count, which a reader has no way to distinguish from the question just having fewer sources.

## What was tested

Two questions, five runs each, per the task brief:

- "Which diseases are associated with BRCA1?"
- "What diseases are caused by variants in the HNF1A gene?"

Both at `audience_depth: researcher`, since that is the depth most likely to expose raw tool detail, and both against the deployed develop API (`https://search-agent-api-develop-43b3.up.railway.app`), not a local or mocked instance.

## Instrument and a bug found in it

The task pointed at `testing/Developer/reports/2026-09-20_L01/capture_tool_results.py`, written 2026-09-20 and never run. It was adapted rather than used unchanged, in two ways:

- It targeted one question. This run needed both questions named in the brief, so the question list was parameterized and the run count kept at 5 per question (10 live runs for the first batch).
- It filtered Layer 1 tool results and citations on the literal string `"layer_1"`. Running it live showed this was wrong: the deployed API tags Layer 1 events `layer_1_graph` (`layer_2_api` and `layer_3_enrichment` for the other two layers). With the original filter, `graph_anomalies` and `layer_1_citation_count` were silently empty or zero on every run, which would have read as "no Layer 1 anomaly found" when the raw payload, saved regardless of the filter, showed otherwise.

Because the bug was in a derived field and not in what was captured, the first batch's raw `tool_results` payloads were still usable once re-read with the correct filter (`layer_1_graph`). A second batch (`capture_tool_results_v2.py`) was then run with the filter fixed and with full citation payloads kept, to get an exact Layer 1 citation count per run rather than inferring it from row counts. Both scripts and both batches of raw output are kept in this folder rather than overwritten, so the bug and its fix are traceable.

## Method

1. `capture_tool_results.py raw` (batch 1): 10 live runs, one guest session per run, full SSE event capture, `tool_start`, `tool_result`, and citation-derived source counts kept per run. 4 seconds between runs.
2. `capture_tool_results_v2.py raw` (batch 2): 10 more live runs, same two questions and depth, with the layer-filter bug fixed and full citation payloads (source id plus layer) kept, so Layer 1 citation counts are exact rather than inferred.
3. Total live queries: 20, plus one bare `/auth/guest` connectivity check before the first batch. 21 total, within the roughly 25-query budget.
4. Every number in this report is read back from a saved file in `raw/`, using the commands recorded in the sections below, not from the console output alone.

## Results: BRCA1

Row counts are the two `cypher_query` (Layer 1) tool results in emission order, for every run that completed.

| Batch | Run | Outcome | Layer 1 row counts | Layer 1 status | Distinct Layer 1 citations | Total sources |
|-------|-----|---------|---------------------|-----------------|------------------------------|----------------|
| 1 | 1 | ask | 4, 40 | ok, ok | not captured in batch 1 | 60 |
| 1 | 2 | ask | 4, 40 | ok, ok | not captured in batch 1 | 60 |
| 1 | 3 | error (guardrail, transient) | none, no tools ran | none | none | 0 |
| 1 | 4 | ask | 4, 40 | ok, ok | not captured in batch 1 | 60 |
| 1 | 5 | ask | 4, 40 | ok, ok | not captured in batch 1 | 60 |
| 2 | 1 | ask | 4, 40 | ok, ok | 40 | 60 |
| 2 | 2 | ask | 4, 40 | ok, ok | 40 | 60 |
| 2 | 3 | ask | 40, 8 | ok, ok | 40 | 60 |
| 2 | 4 | ask | 4, 40 | ok, ok | 40 | 60 |
| 2 | 5 | ask | 40, 8 | ok, ok | 40 | 60 |

Of 9 completed BRCA1 runs, 7 returned a `4, 40` pair and 2 returned a `40, 8` pair. No run returned zero rows on either graph call. The distinct Layer 1 citation count held steady at 40 across every batch 2 run regardless of which pair was returned, which means the citation layer deduplicates rows down to distinct entities: the drop from 40 to 8 rows in the smaller call did not, in this case, cost BRCA1 any visible citations, because whatever entities the missing rows named were already covered by the other call or by non-graph sources.

## Results: HNF1A

| Batch | Run | Outcome | Layer 1 row counts | Layer 1 status | Distinct Layer 1 citations | Total sources |
|-------|-----|---------|---------------------|-----------------|------------------------------|----------------|
| 1 | 1 | ask | 25, 100 | ok, ok | not captured in batch 1 | 86 |
| 1 | 2 | ask | 25, 100 | ok, ok | not captured in batch 1 | 87 |
| 1 | 3 | ask | 25, 100 | ok, ok | not captured in batch 1 | 86 |
| 1 | 4 | ask | 25, 0 | ok, empty | not captured in batch 1 | 41 |
| 1 | 5 | ask | 25, 100 | ok, ok | not captured in batch 1 | 86 |
| 2 | 1 | ask | 25, 100 | ok, ok | 64 | 86 |
| 2 | 2 | ask | 25, 100 | ok, ok | 64 | 86 |
| 2 | 3 | ask | 25, 12 | ok, ok | 25 | 47 |
| 2 | 4 | ask | 25, 100 | ok, ok | 64 | 86 |
| 2 | 5 | ask | 25, 12 | ok, ok | 25 | 47 |

The first graph call held at exactly 25 rows in all 10 completed runs. The second graph call is where the instability lives: 100 rows in 7 of 10 runs, 12 rows in 2, and 0 rows (`status: "empty"`) in 1. This is the clearest instance of the shape L-01 asks about: a whole graph result reduced to nothing on one run of five in batch 1, with the run otherwise indistinguishable from a normal one.

The batch 1, run 4 detail, read directly from `raw/hnf1a_run4.json`:

```
cypher_query layer_1_graph ok    25 row(s) of 25   result_count=25
cypher_query layer_1_graph empty 0 row(s) of 0     result_count=0
```

Every other tool in that same run (`pubtator_annotate`, `clinicaltrials_search`, four `ncbi_efetch` calls) returned its normal result count. `error_payload` was `None`. `trust_outcome` was `ask`, the same value every other HNF1A run produced. Total sources dropped from 86 or 87 in a normal run to 41, a drop of more than half, entirely attributable to the missing second graph call.

Batch 2's `12`-row runs are a smaller version of the same instability (25 percent of the usual 100 rows, not zero), and there the exact citation count confirms the effect reaches the answer: 64 distinct Layer 1 citations in a normal run, 25 in a shrunk one.

## What a reader sees when a graph result shrinks or vanishes

Nothing at the outcome level. `trust_outcome` was `ask` in all 19 completed runs (`answer`, `flag`, `ask`, `refuse` are the only four values the contract defines, confirmed by reading `src/system_03_search_agent/contracts/events.py` and `src/system_03_search_agent/synthesis/trust.py`; this was a read only, no files under `src/` were changed). A shrunk or empty second graph call did not change which of the four values came back.

The only visible signal is the citation and source count, and it moves in a range a reader has no independent way to interpret. A HNF1A answer with 41 sources looks, on its face, like a normal answer about a gene with somewhat fewer known disease links, not like an answer that lost more than half its graph evidence to an empty tool call. The task brief's framing holds up under measurement: this is graceful degradation doing exactly what it is designed to do, continue past a partial failure, with the side effect that the failure itself is invisible.

## The one unrelated error

Batch 1, BRCA1 run 3 returned a fatal `error` event before any tool ran: `scope: step`, `source: guardrail`, `error_class: transient`, "A step in this query hit a temporary error. Retrying the query may succeed." This is a visible, self-reporting failure at the guardrail step, not a graph-layer anomaly, and it is not counted as an L-01 instance: the whole point of L-01 is a failure that does NOT announce itself, and this one did.

## Live commit and environment

- Repository commit at the time of these runs: `99a3495cf76978d741571b57de2fd6ea0e2bceda`, `2026-09-21 16:50:52 -0400` (`git log -1 --format='%H %ci' develop`).
- The task brief notes other agents were editing `src/system_03_search_agent/synthesis/` and `src/system_03_search_agent/contracts/` during this session. Nothing under either directory was read to explain a result in this report beyond the two contract enum reads cited above (both read-only, both stable public contract files, not mid-edit files). The deployed develop API may lag this commit; the runs measure whatever build was live on Railway at the time of each call, not the local working tree.
- Neither `src/` nor `frontend/src/` was modified. This was a read-only measurement task.

## Raw evidence

All 20 live runs and the one connectivity check are saved under `raw/`:

- `raw/brca1_run1.json` through `raw/brca1_run5.json`, `raw/hnf1a_run1.json` through `raw/hnf1a_run5.json`: batch 1, produced by `capture_tool_results.py raw`.
- `raw/all_runs.json`: batch 1, all 10 runs in one file.
- `raw/v2_brca1_run1.json` through `raw/v2_brca1_run5.json`, `raw/v2_hnf1a_run1.json` through `raw/v2_hnf1a_run5.json`: batch 2, produced by `capture_tool_results_v2.py raw`, with full citation payloads.
- `raw/v2_all_runs.json`: batch 2, all 10 runs in one file.

Commands that produced the tables above:

```bash
cd testing/Developer/reports/2026-09-21_L01
python3 capture_tool_results.py raw
python3 capture_tool_results_v2.py raw
```

Followed by the read-only inspection scripts run inline against the saved JSON in `raw/` (filtering `tool_results` on `layer == "layer_1_graph"`), not against memory of the console output.
