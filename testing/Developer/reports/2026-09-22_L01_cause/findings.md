# L-01, the cause: why a graph call returns nothing, read from the tool itself

Item 3 of the fix plan's "Next, in order" as rewritten on 2026-09-22 asked for one L-01 cause to be read out of a trace before any disclosure decision. This is that reading, done the same day. The consistency run (`testing/Developer/reports/2026-09-22_10.3_consistency/`) had measured the rate, 12 of 119 eligible graph calls, and shown the mechanism's outer shape, a `tool_result` with `status: error` and the summary "0 row(s) of 0" and nothing else anywhere. This folder holds what was behind that summary.

## Table of contents

- [Verdict](#verdict)
- [Why no trace existed to read](#why-no-trace-existed-to-read)
- [Where the reason was being dropped](#where-the-reason-was-being-dropped)
- [Method](#method)
- [Cause one: no entity resolved, so no lookup was attempted](#cause-one-no-entity-resolved-so-no-lookup-was-attempted)
- [Cause two: the second graph call runs past the act step's budget](#cause-two-the-second-graph-call-runs-past-the-act-steps-budget)
- [How the 24 errored calls on develop split between the two](#how-the-24-errored-calls-on-develop-split-between-the-two)
- [What changed in the code](#what-changed-in-the-code)
- [What this hands the product owner](#what-this-hands-the-product-owner)
- [Raw evidence](#raw-evidence)

## Verdict

Two causes, both now visible on the stream, neither previously visible anywhere.

| Cause | Shape on the stream | Deterministic or variance | Message the tool had written all along |
|---|---|---|---|
| Think resolved no entity, and the plan dispatched `cypher_query` anyway | The only graph call errors, zero rows, the run refuses for no evidence | Deterministic for a question with no resolvable entity (a coordinate range, an isolate, a BioProject accession); variance where Think resolves the entity on some passes and not others (G-003) | "no entity could be identified in this query, so no graph lookup was attempted" |
| A second graph call, a breadth follow-up on a resolved entity, does not finish inside the act step's per-query-class budget | The first call returns rows, the second errors with zero rows, the answer completes with fewer sources and an identical trust line | Variance, since the same call finishes on other passes | "call did not complete within its per-step timeout budget" |

Neither message reached the stream, the developer instrument or the deploy log before today, because the act step built the `tool_result` summary from row counts alone and dropped the tool's error text at `core/graph.py`, in `_execute_planned_call`. That is fixed in this session's change set, and the reproduction below was run against the fixed code.

## Why no trace existed to read

The fix plan's item said to read the LangSmith trace joined on the run's trace id. There is none, and that is by design: tracing runs on production only, which the product owner confirmed the same day, so `LANGSMITH_API_KEY` is not set on the develop service and develop has never traced. The audit log on the develop container was the other place the cause could live, and it is not reachable from here. The consequence for method is the one worth keeping: a cause behind a develop measurement is read by local reproduction, never from a trace, and a next step written as "read the trace" against develop is wrong on its face.

So the cause was read by reproduction rather than by trace: the API run locally against the real graph and the real models, with the errored calls' messages carried into the event stream by the code change, and the audit log on this machine read alongside.

## Where the reason was being dropped

`cypher_query` writes an actionable message on every one of its error paths, bounded by its own 500-character cap: no entity bound, a template rejected by the validator, generation failing after its one repair, a `GraphError` from the transport, and its own 30-second overall timeout. The act step then summarised every outcome as `f"{row_count} row(s) of {total_available}"` and passed only that into the `ToolResultPayload`, so an errored call and an empty one were indistinguishable to everything downstream. The act step's own per-step timeout produced a fourth message of the same fate. No log line was written at INFO for any of them, and no Layer 1 audit line exists for a call that never reached the transport, which the no-entity path never does.

## Method

1. Three questions whose graph call errored on every develop pass, G-001, G-007 and G-035, were asked once each through a local API on this machine at commit `a868462`, before the code change, to confirm the shape reproduced. It did for G-001 and G-035: `status: error`, "0 row(s) of 0", no audit line. G-007 took a different path locally, no tool selected at all, after a think-classification retry; the local plan tier is a different model from develop's and that difference is recorded rather than smoothed over.
2. The summary change was made and its arm added to `tests/system_03_search_agent/core/test_graph.py`, red against the old code by construction since the old summary equals "0 row(s) of 0" exactly. The core file's 190 tests pass.
3. The local API was restarted on the changed code and G-001, G-003 and G-039 were asked three times each, single worker, in three passes, so both the deterministic and the intermittent shape had a chance to appear. G-039 is the question whose second call errored on two of three develop passes.
4. Every errored `tool_result` summary was read back from the saved captures in `raw/`.

The local run differs from develop in one named way: `PLAN_MODEL` is `moonshotai/kimi-k2.6` here and `deepseek/deepseek-v4-flash` on develop. The guard and synthesis tiers match. The two causes below are the tool's and the act step's, not the plan model's, so they carry over; how often each fires on develop is read from the develop run, not from here.

## Cause one: no entity resolved, so no lookup was attempted

Every G-001 pass, locally and on develop, ends the same way. Think returns `resolved_entities: []` for "What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38?", the plan still names `cypher_query`, and the tool's first check refuses to generate Cypher with nothing to bind:

    0 row(s) of 0: no entity could be identified in this query, so no graph lookup was attempted. Supply a CURIE such as NCBIGene:672, or wait for symbol resolution, which needs the Layer 2 NCBI lookup that build phase 3.1 adds. Retrying this query unchanged will not help.

That message was correct and stale at once: build phase 3.1 shipped on 2026-08-05, and the sentence still told the Act step to wait for it. It is reworded in this change set to name what a caller can actually do. The cause itself is upstream of the tool: nothing in Think turns a GRCh38 coordinate range, a Pathogen Detection isolate description or a BioProject accession into a graph entity, and the plan does not notice that the tool it is about to dispatch has nothing to run on. On develop this is the whole story for G-001, G-007, G-035 and G-048, and for the one G-003 pass where Think failed to resolve Lynch syndrome after resolving it on the other two.

## Cause two: the second graph call runs past the act step's budget

CORRECTED THE SAME EVENING by `testing/Developer/reports/2026-09-22_slow_second_search/findings.md`, which read the graph server's own request log: the call that is lost is the QUESTION'S OWN search, plan index 0, which merely arrives second because the fast GO-process template on the same gene finishes first. It is slow because, with no recognisable shape and a non-lookup class, template selection falls through to model-generated Cypher whose plan the database mis-estimates (67,521 expected Gene rows for an id match that returns 1), and the graph's own 30-second statement timeout kills it after 85 seconds of wall time. The act budget is the second line of defence, not the cause. The paragraph below is kept as first written.

G-039, "I am a student. Explain in plain terms what the BRCA1 gene does and why it matters", resolves `NCBIGene:672` every time and its first graph call returns 40 rows every time. Its second call returned zero rows on two of three develop passes and one of three local passes, and the local capture carries the reason:

    0 row(s) of 0: call did not complete within its per-step timeout budget

The act step bounds its whole tool fan-out by the query class: 15 seconds for a lookup, 20 for a single hop, 30 for a multi-hop or aggregate, 120 for an exploratory question. G-039 classifies as exploratory, so its budget is 120 seconds, and the pass that lost the second call took 280 seconds end to end locally and about 100 on develop. The call that is cut is the one that started last and had the least of the shared budget left. The answer then completes normally with the rows the first call found, the citation count drops from 88 to 56, and the trust line reads exactly as it does on a pass where both calls finished. This is the L-01 the 2026-09-21 report first described, now with its reason attached.

## How the 24 errored calls on develop split between the two

Read from `runs.jsonl` in the consistency run, using whether Think resolved any entity for the run and which call position errored:

| Cause | Calls | Questions | Note |
|---|---|---|---|
| No entity resolved, single errored call | 13 | G-001 (3), G-003 (1), G-007 (3), G-035 (3), G-048 (3) | G-048 refusing is correct: dbGaP controlled access is out of scope. The other four are gaps |
| Entity resolved, the second of two calls errored | 11 | G-006 (1), G-011 (1), G-012 (1), G-033 (3), G-037 (3), G-039 (2) | G-033 and G-037 lose the second call on every pass, so for those two shapes the budget is never enough rather than sometimes; both still answer from the first call and the other layers |

The develop stream did not carry the messages, so the second row's attribution rests on the local G-039 reproduction and the shape match, not on a develop message for each. The next consistency run against the changed code will carry every one.

## What changed in the code

- `core/graph.py`, `_execute_planned_call`: an errored `cypher_query` outcome's summary now reads `"<rows> row(s) of <total>: <the tool's error>"`. Nothing parses the row-count prefix, which is kept; the tool's 500-character cap keeps the whole under the event's 1000.
- `tools/cypher_query.py`: the no-entity message no longer tells the caller to wait for build phase 3.1.
- `tests/system_03_search_agent/core/test_graph.py`: one arm pinning that an errored cypher `tool_result` carries a non-empty reason after the prefix.

Not changed, on purpose: the act budgets, Think's entity extraction, and what the reader sees in the answer text. Each is a product decision this reading was meant to inform, not to take.

## What this hands the product owner

- Disclosure now has an attachment point and a text: the errored `tool_result` carries a reason a person can read. Whether the answer itself should say "one of the graph searches did not finish, so this answer may be missing sources" is the decision that was waiting on this reading.
- Four questions never answer because Think cannot turn a coordinate range, an isolate description or an accession into an entity. That is a Think gap with a fixed reproduction set, separate from L-01's variance.
- Two question shapes lose their second graph call on every pass to the act budget, and the plain-terms BRCA1 explanation loses it on most. Raising the exploratory budget past 120 seconds trades a slower answer for a fuller one; a more useful lever is to know why one breadth follow-up takes over a minute on a gene the first call answers in seconds, which the graph query service's own logs on the Hetzner box can say and this reading did not reach.

## Raw evidence

| File | What it is |
|---|---|
| `runs_local_before_fix.jsonl` | The three reproduction runs against `a868462`, before the summary change, showing the same "0 row(s) of 0" shape locally |
| `runs_local_after_fix.jsonl` | The nine runs against the changed code, three passes of G-001, G-003 and G-039 |
| `raw/G-NNN_runP.json` | Per run, every event except tokens and trust signals; the errored `tool_result` summaries are in G-001 passes 1 and 2 and G-039 pass 2 |
