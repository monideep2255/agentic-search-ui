# Card 14 diagnosis: one search took 127 seconds against a median of 14

Base: develop at c916cfa3. Read-only diagnosis, no model calls made, nothing run live.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap](#overlap)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Cannot tell without a live run. The one run is not reproduced: the raw evidence is a single run of 3 on one question (HNF1A diseases, researcher depth), 29 of 30 runs in that set took 7 to 23 seconds (`testing/Developer/reports/2026-09-20_verification_rate/findings.md`, builder A's T-8.1-03 in `testing/Developer/reports/2026-09-25_phase_8.1/builder_A.md`). No per-step timing was kept, so the slow step is not known.

The card's stated cause ("a timeout that stops the wait but not the work") is only a hypothesis, and for the graph call it is mostly closed on develop:

| Part of the hypothesis | State on develop |
|---|---|
| The graph call runs in a worker thread that `asyncio.wait_for` cannot stop | True: `tools/cypher_query.py:2015` uses `asyncio.to_thread(execute_cypher, ...)`. |
| So the thread could run on after the wait gives up | Bounded by the database itself: `tools/graph_connection.py:620` runs `SET statement_timeout` with the call's remaining budget before every query, and `connect_timeout=10` (line 353). The database cancels the statement, so the thread ends near the budget. |
| The two 30 s wraps | Still there: `cypher_query` wraps its pipeline at `cypher_query.py:2365`, and Act wraps again at `core/graph.py:8323`. |

The git log since 2026-09-20 shows no commit that changes the timeout design except dd300cba (graph limit back to 30 seconds) and dfb6ffad (memory guard). Neither is a fix for a 127 s run.

## What a person sees

- They ask a graph question and the page stays on "working" for about two minutes, where it usually takes 14 seconds.
- The answer, when it arrives, is a normal answer (the run succeeded with 16 sources and the "could not be verified" note).

## The cause

Cause unknown. Two candidates fit the code:

| Candidate | Evidence |
|---|---|
| No cap on the whole run, only on each step | Budgets are per step: `harness/harness.py:479` guard 15 s, plan and synth 45 s each; Act by query class (30 s for multi_hop, 120 s for exploratory, line 414). Think retries once (`graph.py` `_run_think_classification`), and the grounding repair path adds a write call. Worst case adds to well over 127 s. A stated latency budget of 53 s is not enforced by any whole-run limit; no run-level deadline exists in `core/run.py` or `core/run_registry.py`. |
| One slow model call | A slow plan or synth call inside its own 45 s budget, then a retry, would reach about 100 to 130 s without any timeout failing. |

The cheapest check: run the HNF1A question at researcher depth ten times against develop and log elapsed time per node (the `call_log` and node events already carry timestamps). A run over 60 s shows which step. Zero spend on the diagnosis is not possible, since it needs live calls: about 2 cents a run, 20 cents in all. That is a cost decision for the owner only if no live budget is set for diagnosis.

## The smallest fix

Cannot be sized until the slow step is known. If the cause is the missing whole-run cap, the fix is a single deadline checked between steps in `core/graph.py` (each node reads the time left and skips a retry or a repair call when under a threshold, and Write explains an early finish). That is size M, dial position 2, answer path yes.

| Item | Value |
|---|---|
| File fence (if whole-run cap) | `core/graph.py` node entry points and `harness/harness.py` budget helper. |
| Answer path | Yes. |
| Dial position | 2. |
| Size | M, after the check. The check itself is S. |
| Migration | No. |

## Overlap

- A whole-run cap in `core/graph.py` overlaps phase 8.7 (`write_node`, `act_node`) and `harness/decide.py` if decisions are also capped. Wait for 8.7 before building.
- The check itself touches nothing.

## Needs the owner

Yes, a cost decision only: approval of about 20 cents of live runs for the check. The cap, if built, changes how long a person may wait, which the owner has already set at 20 seconds per answer (no degradation on any surface), so the target is not a new choice.

## Proposed test query

Existing coverage is the speed line in query 1 (basic search), which does not exercise this tail. Add to section 1 of `testing/Test_queries_and_workflows.md`:

### A search never takes minutes (card 14)

Queries to try:

- Ask `What diseases are caused by variants in the HNF1A gene?` at Researcher depth, five times in a row.

What you should see:

- Every run finishes in under about 40 seconds on screen. None sits on "working" for minutes.
- If a run is cut short, the answer says what it could not finish.
- Why it matters: a person who waits two minutes assumes the product is broken and leaves.
