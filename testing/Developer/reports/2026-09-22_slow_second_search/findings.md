# The slow second graph search, read from the graph server's own logs

Why "I am a student. Explain in plain terms what the BRCA1 gene does and why it matters" (G-039) takes about 100 seconds on develop and usually loses one of its two graph searches. Read on 2026-09-22 from the Hetzner box's own Caddy, uvicorn and PostgreSQL logs for the exact windows of the develop consistency run, plus three bounded read-only queries through the repository's own `execute_cypher`. Nothing was changed, in the repository or on the server.

## Table of contents

- [Verdict](#verdict)
- [Two corrections to the premise](#two-corrections-to-the-premise)
- [Which call is which](#which-call-is-which)
- [What the second-emitted call actually runs](#what-the-second-emitted-call-actually-runs)
- [How long it takes on the graph, measured](#how-long-it-takes-on-the-graph-measured)
- [Why it is slow](#why-it-is-slow)
- [What the 86 seconds is made of, and the part still open](#what-the-86-seconds-is-made-of-and-the-part-still-open)
- [G-033 and G-037 are a different fault](#g-033-and-g-037-are-a-different-fault)
- [The smallest change, proposed and not applied](#the-smallest-change-proposed-and-not-applied)
- [Levers measured and rejected](#levers-measured-and-rejected)
- [What the user would notice](#what-the-user-would-notice)
- [Method and evidence](#method-and-evidence)

## Verdict

| Question | Answer |
|---|---|
| Which query does the slow graph call run? | No template. `select_template` returns `None` for G-039, so the question's own `cypher_query` takes the model path and the plan tier writes the Cypher. The template that finishes fast is the other call, `gene_go_processes_one` |
| How long does it take on the graph? | 86.24 s, 86.51 s and 85.17 s on the three develop passes, measured from Caddy's own per-request `duration` field. The fixed GO template on the same gene in the same run took 0.08 s |
| Why is it slow? | A row-count estimate. PostgreSQL believes `properties @> '{"id": "NCBIGene:672"}'` on the `Gene` label matches 67,521 rows where the truth is 1, so under a `LIMIT` it prefers a fast-start plan that drives the join from the edge table and filters the gene afterwards. Only one gene matches, the early exit never happens, and the plan walks a whole edge index: 17.4 million rows for `orthologous_to`, 124 million for `mentioned_in` |
| Smallest change | `src/system_03_search_agent/tools/cypher_templates.py`, `select_template`, lines 677 to 680: fall back to `_record_template` on any query class when no shape matched, not only on `lookup`. Measured: 0.745 s and the same one row the 85-second call produced |
| What the user notices | The plain-terms BRCA1 answer arrives in about 15 seconds instead of about 100, with the same sources, and stops losing a search |

## Two corrections to the premise

Both are recorded because each changes what the fix is.

- The brief says the second search is dropped because it does not finish inside the act step's 120-second budget. It is not. The act budget for an exploratory query is 120 s and was never reached. The call is killed by `kg_reader`'s own `statement_timeout = 30s` on the graph server, which surfaces as a 504 from the query service. The 120-second budget is not the constraint and raising it would not help.
- The brief says all three questions lose their second graph search the same way. They do not. Only G-039 is a slow query. G-033 and G-037 lose their call in 2.5 to 17 seconds without ever reaching the graph at all, which is a generation or validation failure, not a latency one. See [G-033 and G-037 are a different fault](#g-033-and-g-037-are-a-different-fault).

## Which call is which

The 2026-09-22 L-01 report calls the failing call "the breadth follow-up". Read from the `plan` event's own ordering, it is the opposite way round, and this matters because the two calls have entirely different code paths.

`plan_node` plans eleven calls for a gene question. The question's own `cypher_query` is index 0 (`core/graph.py` line 3940, `_build_planned_call`). The gene's GO terms are index 10, planned last (line 4118, `_build_planned_go_terms_call`). Act dispatches them concurrently, so the GO call, being fast, returns first and the question's own call returns second.

| Run | Call planned at index 0 (the question's own) | Call planned at index 10 (the GO template) |
|---|---|---|
| G-039 pass 1 | `cq-80932725a1b8`, emitted second at 17:30:43.80, `error`, 0 rows | `cq-92689e5c78a5`, emitted first at 17:29:14.51, `ok`, 40 rows |
| G-039 pass 2 | `cq-6520e65143dd`, emitted second at 17:18:53.70, `error`, 0 rows | `cq-e5271ec8ac48`, emitted first at 17:17:24.39, `ok`, 40 rows |
| G-039 pass 3 | `cq-6b1b9d65ed98`, emitted second at 17:27:15.14, `ok`, 1 row | `cq-01a0792ddf4c`, emitted first at 17:25:47.64, `ok`, 40 rows |

So the call that is lost is the question's own graph search, and the call that survives is the code-chosen context call. The 40 GO rows are context beside the answer (`context_only=True`); the row the question's own call is trying to fetch is the answer.

## What the second-emitted call actually runs

It runs no template. `select_template` was run locally as a pure function against the three questions' real `query_intent` and the `query_class` Think emitted on each pass:

| Question | Gene shapes matched | Template selected |
|---|---|---|
| G-039, "Explain in plain terms what the BRCA1 gene does and why it matters" | none | `None` |
| G-033, "Compare what is known about MLH1 and MSH2 in colorectal cancer risk" | none | `None` |
| G-037, "Find GEO expression datasets studying TP53 in human tumour samples" | none | `None` |

The reason is `cypher_templates.py` lines 677 to 680. No shape word ("variants", "diseases", "processes", "publications" and so on) appears in any of the three questions, and the fallback to the record template is gated on `query_class is QueryClass.LOOKUP`. Think classified G-039 as `exploratory` on all three passes, so the gate is closed and the function returns `None`.

`None` means the model path: `cypher_generation` asks the plan tier to write the Cypher, and whatever it writes is what runs. That is why the same question produces a different query on every pass. On develop the bound parameter was the same every time, `{"e_NCBIGene_672": "NCBIGene:672"}`, read from the PostgreSQL log's `STATEMENT` line for the cancelled executions.

For comparison, the fast call is fixed in code: `gene_go_processes_one` (`cypher_templates.py` line 583), `MATCH (a:Gene {id: $e})-[:participates_in]->(x:BiologicalProcess) RETURN x ORDER BY x.id`.

## How long it takes on the graph, measured

Caddy fronts the query service and records a `duration` for every request in `/var/log/caddy/graph-query-service.log`. These are the three G-039 passes, each showing both of the run's graph requests:

| Pass | Request | Start (UTC) | Duration | Status | Body |
|---|---|---|---|---|---|
| 1 | GO template | 17:29:14.213 | 0.08 s | 200 | 18,684 bytes, 40 rows |
| 1 | the question's own | 17:29:18.498 | 86.24 s | 504 | 150 bytes, 0 rows |
| 2 | GO template | 17:17:24.092 | 0.08 s | 200 | 18,684 bytes, 40 rows |
| 2 | the question's own | 17:17:28.047 | 86.51 s | 504 | 150 bytes, 0 rows |
| 3 | GO template | 17:25:47.338 | 0.08 s | 200 | 18,684 bytes, 40 rows |
| 3 | the question's own | 17:25:49.748 | 85.17 s | 200 | 67,721 bytes, 1 row |

Three facts follow directly.

- The graph is the whole wait. Between the `tool_start` event and the request arriving at Caddy there are 2.8 to 4.7 seconds, which is schema slicing and Cypher generation. Everything after that is the graph.
- Pass 3 is the one that succeeded, and it took 85 seconds to return exactly one row. Diffing pass 3's citations against pass 1's shows the single row it added: `NCBIGene:672`, the BRCA1 gene record itself, the only Layer 1 citation present in pass 3 and absent from the passes that lost the call.
- The rest of the run is not slow. Across the whole 43-minute consistency window the graph served 189 requests with a median of 0.081 s and a p90 of 2.02 s. Five exceeded 60 s. Three of those five are these G-039 passes; a fourth is another `NCBIGene:672` query at 17:00:15 (83.28 s, 504) and the fifth an Article anchor, `PMID:11237011`, at 17:00:58 (64.66 s, 504).

The PostgreSQL log confirms how the 504s end. Six statements have ever been cancelled on this server, four of them on BRCA1 and three of those inside this run window:

```
2026-09-22 17:18:54.105 UTC kg_reader@ncbi_kg ERROR:  canceling statement due to statement timeout
2026-09-22 17:18:54.105 UTC kg_reader@ncbi_kg STATEMENT:  EXECUTE cq_130481500dee4bb2b29234dc946ac51c('{"e_NCBIGene_672": "NCBIGene:672"}');
2026-09-22 17:30:44.210 UTC kg_reader@ncbi_kg ERROR:  canceling statement due to statement timeout
2026-09-22 17:30:44.210 UTC kg_reader@ncbi_kg STATEMENT:  EXECUTE cq_e8886f23692f454c833ba2a4a7e5738f('{"e_NCBIGene_672": "NCBIGene:672"}');
```

`kg_reader`'s role configuration carries `statement_timeout=30s`, and `graph_connection.execute_cypher` re-sets it per connection from the caller's `timeout_s`, which the service clamps to `CYPHER_QUERY_TIMEOUT_SECONDS`, 30 seconds. So the executing statement ran its full 30 seconds and was killed.

## Why it is slow

A row-count estimate, of the same family as the 42,034 ms to 108 ms case already recorded in `graph_connection.py` lines 110 to 139, but in its join-order form rather than its scan form, which is why `SET enable_seqscan = off` does not touch it.

`EXPLAIN` was run on the server as `postgres`, plan only with no `ANALYZE`, under exactly the session settings `execute_cypher` applies (`enable_seqscan = off`, `max_parallel_workers_per_gather = 0`, `work_mem = '32MB'`). The anchor estimate is the root of it:

```
->  Bitmap Index Scan on idx_gene_props_gin  (cost=0.00..553.71 rows=67521 width=0)
      Index Cond: (properties @> '{"id": "NCBIGene:672"}'::agtype)
```

The planner expects 67,521 gene rows. The true answer is 1. A GIN index on a whole `properties` column carries no per-key selectivity, so the estimate falls back to a fixed fraction of the label's 67.5 million rows.

With that estimate and a `LIMIT`, the planner prefers the plan with the cheapest start-up cost, which is to drive the join from the edge table and check the gene afterwards. Two measured examples, both real plans for a single bound gene:

| Generated shape | Plan chosen | Rows the driving scan must walk |
|---|---|---|
| `(g:Gene {id})-[:orthologous_to]->(o:Gene)` | `Index Scan using idx_orth_start on orthologous_to`, then a memoized `Gene` lookup with the id filter | 17,421,812 |
| `(g:Gene {id})-[:mentioned_in]->(a:Article)-[:has_mesh_annotation]->(m:OntologyClass)` | `Index Scan using idx_mentin_start on mentioned_in`, then a memoized `Gene` lookup with the id filter | 124,032,424 |

The planner prices this as cheap because it assumes it will hit 100 matching rows almost immediately, having been told 67,521 genes match. One gene matches. The early exit never fires and the scan runs to the end of the index.

The cost scales with the edge table, and the measurement matches the arithmetic. One bounded execution through `execute_cypher` of the ortholog shape as an aggregate, which removes the early exit entirely, walked the full 17.4 million rows in 4.14 seconds. At that rate `mentioned_in`, at 124 million rows, is about 30 seconds and `has_mesh_annotation`, at 349 million, about 83. The 85 to 86 seconds observed sits in that band, and the plan above shows exactly that shape being chosen.

Not the cause, checked and excluded:

- Not a missing index. Every vertex label has a GIN index on `properties` and a btree on `id`; every edge label has btree indexes on both `start_id` and `end_id`.
- Not a sequential scan. `enable_seqscan = off` is already set on every connection and no plan above contains one.
- Not stale statistics. `pg_class.reltuples` is populated and correct for every table (`Gene` 67,521,208, `mentioned_in` 124,032,424, `has_mesh_annotation` 349,158,784). `pg_stat_user_tables.last_analyze` is null because the statistics collector was reset, not because `ANALYZE` never ran.
- Not the act step's 120-second budget, and not `cypher_query`'s own 30-second budget either. The graph server kills the statement first.

## What the 86 seconds is made of, and the part still open

Of the 86.24 seconds, the final 30 are the cancelled `EXECUTE`, which is pinned exactly: the cancellation is stamped at 17:30:44.210 and `statement_timeout` is 30 s, so the statement began at 17:30:14.2, which is 55.7 seconds after the request reached Caddy.

What those 55.7 seconds are cannot be resolved from the box. `PREPARE` cannot be all of it, because pass 3 completed in 85.17 seconds with no cancellation at all, which means every statement in that request stayed under 30 seconds. The remainder is connection acquisition plus whatever the service does before it executes, and the deployed service (installed 2026-08-24) predates the `logger.info("graph_query_service call ... cypher=%s ...")` line that `services/graph_query_service/app.py` line 1062 now carries, so no request in this window recorded the Cypher it ran or a phase breakdown.

This is recorded as open rather than guessed at. It does not change the proposal, because the proposal removes the request rather than tuning it, and it does not change the headline number, which is measured end to end. The cheapest next step, if anyone wants the exact generated text, is to redeploy the current service so that line is live, then re-ask G-039 once.

## G-033 and G-037 are a different fault

Their second-emitted call never reaches the graph. Reading Caddy's log for each question's act window shows only the GO call's request:

| Run | Act window | Graph requests in the window |
|---|---|---|
| G-033 pass 1 | 16:59:07 to 16:59:24 | 0.08 s (200, 3,042 bytes) and 0.52 s (200, 2,089 bytes) |
| G-033 pass 2 | 17:16:28 to 17:16:36 | 0.07 s (200, 3,042 bytes) |
| G-037 pass 1 | 16:59:51 to 16:59:55 | 0.08 s (200, 34,851 bytes), 0.07 s, 1.47 s, 0.08 s |
| G-037 pass 2 | 17:17:05 to 17:17:10 | 0.08 s (200, 34,851 bytes) and 0.07 s |

Their errored call takes 2.5 to 17 seconds and issues no graph request, so it failed inside `cypher_query` before the transport: generation failing after its one repair, or the validator rejecting what the model wrote. Both are the model path again, and the proposal below removes the model path for G-033 too (no shape matched, so the record template applies). G-037 resolves nine entities on one pass and one on another, so it needs its own reading. Neither is a graph latency problem and neither belongs in this report's fix.

## The smallest change, proposed and not applied

File: `src/system_03_search_agent/tools/cypher_templates.py`
Function: `select_template`
Lines: 677 to 680

Today:

```python
    if not shapes:
        if tool_input.query_class is QueryClass.LOOKUP:
            return _record_template(anchor_label, param_names)
        return None
```

Proposed: drop the `query_class` gate, so a question that names an entity but no shape always gets the record template rather than the model path.

Why this one and not another:

- It is one condition, in a pure function, with no network and no model call, and it is already the behaviour for the same question on a `lookup` classification. Think's class is a model's guess, and `select_template`'s own docstring already states that the class does not gate shape selection elsewhere in the same function. This makes the no-shape branch agree with the rest.
- It gives the reader the same row. The template produces `gene_record_one`, `MATCH (a:Gene {id: $e}) RETURN a`, whose single row is `NCBIGene:672`, exactly the row pass 3 spent 85 seconds producing and the only Layer 1 row the successful pass added.
- It is measured. One bounded execution through `execute_cypher` on the HTTPS service: `MATCH (a:Gene {id: $curie}) RETURN a LIMIT 100` returned 1 row in 0.745 seconds wall from this laptop, against 85 to 86 seconds for what the model writes. The plan is the `idx_gene_props_gin` bitmap scan, which the bad estimate does not hurt because there is no join for it to mis-order.
- It removes the whole class of fault rather than one query. A template never fails generation and never fails validation, which is also G-033's fault above.

What it costs, stated plainly rather than buried. Some no-shape questions on non-lookup classes would have had a richer model-written query answered from the graph, and they now get the record instead. On the evidence here that trade is strongly positive: across the three G-039 passes the model path returned one row once and nothing twice, at 85 seconds a time, and the rows it did return on a local reproduction were five non-human orthologs, which is finding F-2.1-01's known-wrong shape. This is a product decision, so it is written as a proposal and not applied.

Two smaller changes that are not proposed, and why:

- Lowering the act budget at `core/graph.py` line 4805 would cut the wait but still lose the search, so the reader trades a slow thin answer for a fast thin one.
- Raising the budget, or raising `statement_timeout`, makes the answer slower and reaches the same one row.

## Levers measured and rejected

Both were tested by `EXPLAIN` on the server, plan only, no execution.

| Lever | Effect on the ortholog plan | Effect on the two-hop plan | Verdict |
|---|---|---|---|
| `SET enable_memoize = off` | Fixed. Drives from the `Gene` GIN bitmap into `idx_orth_start` with an index condition | Made worse. Drives from a full `idx_gene_pk` scan of all 67.5 million gene rows with the id as a filter | Rejected, it trades one bad plan for another |
| `SET join_collapse_limit = 1` and `from_collapse_limit = 1` | No change | No change | Rejected, AGE's generated SQL is already collapsed |

The durable repair for the estimate itself is server-side statistics on the anchor property, which is a write to the graph database and therefore Systems 1 and 2 work, not this repository's. It is named here so the next reader knows the client-side fix above is a bypass of the bad estimate rather than a cure for it.

## What the user would notice

Today, a student asks what BRCA1 does and why it matters. The page streams for roughly a minute and a half with nothing new appearing, and the answer lands at about 100 seconds. On two runs in three, one of the two knowledge-graph searches has been thrown away by then, and nothing in the answer says so: the sources list is shorter, the trust line reads exactly as it does on a good run, and the reader has no way to tell the difference. The one time the search does finish, it has spent 85 seconds fetching a single record the answer barely uses.

If the proposal lands, the same student asks the same question and the answer arrives in roughly fifteen seconds. Both knowledge-graph searches finish, every time, because both are now fixed queries that the graph answers in well under a second. The sources are the same ones they already get today, including the BRCA1 gene record that currently arrives only on a lucky run. Nothing is silently dropped, so the shorter wait is not bought with a thinner answer.

The plainest version: the wait stops being a minute and a half, and the answer stops quietly losing a search.

## Method and evidence

Read-only throughout. No file under `src/`, `frontend/` or `tests/` was touched, nothing was committed, and nothing on the server was written, restarted or reconfigured.

| Source | What it gave |
|---|---|
| `testing/Developer/reports/2026-09-22_10.3_consistency/raw/G-0{39,33,37}_run{1,2,3}.json` | The `plan` event's `tool_calls` in order, both `cypher_query` `tool_result` events in emission order, and the citation diff that identified pass 3's single extra row |
| `testing/Developer/reports/2026-09-22_L01_cause/raw/G-039_run{1,2,3}.json` | The local reproduction, whose primary call returned 8 rows once (five non-human orthologs, the gene, one PMID) and 1 row once |
| `/var/log/caddy/graph-query-service.log` on 46.225.128.133 | Per-request `duration`, status and body size for all 189 graph requests in the run window. This is where every timing in this report comes from |
| `journalctl -u graph-query-service` | The 504 on the two lost G-039 calls, and confirmation that the deployed service logs no Cypher |
| `/var/log/postgresql/postgresql-15-main.log` | The `canceling statement due to statement timeout` lines and their `STATEMENT` text, which gave the bound parameter |
| `psql` as `postgres`, `SELECT` and `EXPLAIN` only | `kg_reader`'s `statement_timeout=30s`, the full index inventory, `pg_class.reltuples`, and eleven query plans |
| `select_template` run locally as a pure function | That all three questions select no template |
| `execute_cypher` over the HTTPS query service, three executions, each once and each with a `LIMIT` | `...-[:orthologous_to]->(o:Gene) RETURN DISTINCT o LIMIT 100`: 5.18 s, 100 rows. `...-[:orthologous_to]->(o:Gene) RETURN count(DISTINCT o) LIMIT 1`: 4.14 s, 514. `MATCH (a:Gene {id: $curie}) RETURN a LIMIT 100`: 0.745 s, 1 row |

One limitation, stated rather than left implied: the exact Cypher the plan tier wrote on develop could not be recovered, because the deployed query service predates the line that would have logged it and PostgreSQL logs statement text only on error. Everything above about the query's shape is inferred from the bound parameter, the rows it returned, the plans the planner chooses for the candidate shapes, and the local reproduction. The timings are not inferred; they are the server's own.
