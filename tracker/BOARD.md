# Build board

The index of every phase. Maintained by the `task-tracker` skill. Per-phase tickets live in `tracker/phase_N.M.md`, created when a phase opens.

Build phases and their dependencies come from `requirements/Technical_specification.md` Section 25, which is the source of truth. This board never invents a phase.

Last updated: 2026-07-29.

## Status counts

Listed in flow order. Work moves left to right on the board, from `todo` to `done`.

| Status | Count | Who may set it |
|--------|-------|----------------|
| To do | 21 | Lead |
| In progress | 0 | The builder that claimed it |
| Blocked | 0 | The builder that hit the block, reason required |
| In review | 1 | The builder that finished |
| Done | 9 | Judge only, never the builder |

`blocked` sits mid-flow rather than on the way to done, because it is where work stalls, not a step toward finishing.

## Planning phases

| Phase | Delivered | Status | Closed |
|-------|-----------|--------|--------|
| P1 | Source review and architecture decisions, 13 steps | done | 2026-07-21 |
| P2 | Competency questions and the evaluation playbook | done | 2026-07-22 |
| P3 | The PRD, locked | done | 2026-07-22 |
| P4 | The technical specification and strategic memo, locked | done | 2026-07-25 |
| P5 | System and tooling updates, the build harness | done | 2026-07-26 |

## Build phases

Group P is the prototype, Plan.md Step 6.1. Everything else is v1, Step 6.3. Step 6.2, the one reconciliation pause, sits between 2.2 and 3.0.

This table is parsed by `tracker/render_board.py`. Keep the ten columns and their order.

- Refinement: one of `tech_refine`, `product_refine`, `team_refine`, `refined`. Never empty. A phase with no refinement label gets lost in the backlog, so the renderer refuses to build the page without one.
- Owner: `product owner` or empty.
- Gates and Flags: comma separated, or empty.

The renderer enforces two rules here. A phase cannot leave `todo` unless its refinement is `refined`, because work does not start on something nobody has finished thinking about. And the flag count on phases must match the rows in the Open flags table, or the summary count would lie.

| Phase | Branch | Delivers | Depends on | Group | Status | Refinement | Owner | Gates | Flags |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| 1.0 | `phase/1.0-fastapi-skeleton` | FastAPI skeleton, health endpoint, the run() contract stub with the v1 event taxonomy typed, Pydantic boundary validation | | prototype | done | refined | | | |
| 1.1 | `phase/1.1-auth-service` | Minimal v1 auth, the PostgreSQL user-data schema | 1.0 | prototype | done | refined | | | |
| 1.2 | `phase/1.2-react-shell-sse` | React shell, SSE consumption of the event stream, empty chat endpoint wired end to end, the stop button | 1.0 | prototype | done | refined | | | |
| 2.0 | `phase/2.0-langgraph-agent-loop` | LangGraph loop with stub nodes, the three-tier harness on LiteLLM and OpenRouter, coordinator-worker scaffold, cost caps from day one | 1.0 | prototype | done | refined | | | |
| 2.1 | `phase/2.1-cypher-tool` | cypher_query over Layer 1, schema slicing, validate-then-execute generation, edge-label enforcement | 2.0 | prototype | in-review | refined | | | reworked not re-reviewed |
| 2.2 | `phase/2.2-write-step-grounding` | Deterministic cite-or-refuse, provenance for Layer 1 citations, the first trust signal, the two required tests | 2.1 | prototype | todo | tech_refine | | eval-harness | whole-repo security scan not yet run |
| 3.0 | `phase/3.0-guardrail-node` | Full guardrail replacing the stub: validation, prompt-injection rejection, forbidden types, rate and cost pre-checks | 2.0 | v1 | todo | tech_refine | | | |
| 3.1 | `phase/3.1-ncbi-efetch` | ncbi_efetch over E-utilities and Datasets API v2 | 2.0, 3.0 | v1 | todo | tech_refine | | | |
| 3.2 | `phase/3.2-ncbi-dbsnp` | ncbi_dbsnp over Variation Services, plus the dbVar two-step coordinate-overlap sub-tool | 3.1 | v1 | todo | tech_refine | | | |
| 3.3 | `phase/3.3-enrichment-tools` | pubtator_annotate and litvar2_lookup, each with untrusted-source-reader separation | 3.1 | v1 | todo | tech_refine | | | relations endpoint unverified |
| 3.5 | `phase/3.5-pathogen-clinicaltrials-tools` | pathogen_detection and clinicaltrials_search, completing the seven-tool roster | 3.1 | v1 | todo | tech_refine | | | |
| 3.4 | `phase/3.4-citation-trust-full` | Provenance extended to Layers 2 and 3, the two-tier risk gate, freshness and conflict resolution | 2.2, 3.1, 3.2, 3.3, 3.5 | v1 | todo | tech_refine | | eval-harness | |
| 4.0 | `phase/4.0-rest-sse-hardening` | The REST plus SSE adapter finalized as the public API surface | 2.2 | v1 | todo | tech_refine | | | F-1.2-01, F-1.2-02, F-1.2-03 |
| 4.1 | `phase/4.1-mcp-server` | Outbound-only MCP server wrapping the same tool functions | 3.4 | v1 | todo | tech_refine | | | |
| 4.2 | `phase/4.2-cli-adapter` | Thin CLI client over the REST API | 4.0 | v1 | todo | tech_refine | | | |
| 4.3 | `phase/4.3-graphql-api` | GraphQL surface via Strawberry, sharing auth and tools with REST | 4.0 | v1 | todo | tech_refine | | | |
| 4.4 | `phase/4.4-kgx-export` | KGX export utility, a batch job over the existing graph. No in-repo dependency, so it can land any time | | v1 | todo | tech_refine | | | |
| 4.5 | `phase/4.5-personalization-memory` | Bounded session memory, audience-level depth control, the named scientist persona. Never touches grounding | 1.2, 2.2 | v1 | todo | product_refine | product owner | playwright | |
| 4.6 | `phase/4.6-feedback-capture` | Interaction capture, the manual review ritual, hand-promotion into few-shot examples | 1.1, 3.4 | v1 | todo | tech_refine | | | F-2.0-04, F-2.0-10 |
| 4.7 | `phase/4.7-cq-routing` | Few-shot routing seeded with the seven must-pass questions, query-shape routing | 3.4 | v1 | todo | tech_refine | | | |
| 5.0 | `phase/5.0-observability` | LangSmith per-run tracing on trace_id, PostHog analytics, the append-only tool-call audit log | 2.0 | v1 | todo | tech_refine | | | |
| 5.1 | `phase/5.1-golden-dataset-eval` | The 50-query golden dataset, eval-harness grading, the cost dashboard | 3.4, 5.0 | v1 | todo | product_refine | | eval-harness | needs domain sign-off owner |
| 6.0 | `phase/6.0-rate-limit-concurrency` | Per-layer throttling, the bounded queue per API family, the 20-calls-per-query budget | 3.1, 3.2, 3.3, 3.5 | v1 | todo | tech_refine | | | |
| 6.1 | `phase/6.1-hardening-release` | The full dev-standards six-lens pass, CI and CD gates, the security scan, accessibility | everything | v1 | todo | tech_refine | | dev-standards | F-1.2-04 |
| 7.0 | `phase/7.0-model-bench` | Benchmark candidate models per tier against the golden dataset, pick the winners | 5.1 | v1 | todo | tech_refine | | | |
| 7.1 | `phase/7.1-ab-mechanism` | The online A and B randomized-routing mechanism, human-gated | 7.0, 5.0 | v1 | todo | tech_refine | | | |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
## Open flags

| Flag | Detail | Resolve before |
|------|--------|----------------|
| Golden fixture domain sign-off | Nobody is named to verify the clinical and human-variation expected answers. A wrong expected answer makes a wrong agent pass, which is the failure the gate exists to catch | Build phase 5.1 |
| PubTator3 relations endpoint | Path and fields not live-verified | Build phase 3.3 ship |
| Whole-repo security scan not yet run | No build-phase code has ever been security scanned. The only run in `security/` is dated 2026-07-25 and predates phase 1.0. Deferred twice by product-owner decision (2026-07-27, 2026-07-28) on the reasoning that the Step 6.1 prototype is throwaway and the scan earns its cost once the code is meant to survive. The agreed shape is ONE deep dive over the ENTIRE repository, not a commit range, so there is no baseline SHA to carry forward and nothing to forget to widen | The Step 6.2 reconciliation, after build phase 2.2 closes and before any Step 6.3 v1 work starts |
| Reworked not re-reviewed | Build phase 2.1's judge and adversary both FAILED the phase, then every blocker was fixed and the 9-test live end-to-end gate went green (798 tests passing overall). No independent agent has reviewed any of that rework: agtype parsing, the true-total count, entity extraction, the cite-or-refuse enforcement path, four validator bypass fixes, the recursive payload caps, the in-tool cost cap, or the Seq Scan planner fix. This phase has already produced one false green, where every ticket passed and the judge still found the premise unmet plus 17 adversary defects, so a green suite here has a track record of being wrong. Merged on an explicit, informed product-owner decision against a weekly budget limit, recorded rather than glossed. Detail in `tracker/phase_2.1.md`'s "Phase close status" section | Build phase 2.2's first task, since 2.2 depends directly on this code |
| F-2.0-04 | Nothing in `src/` writes an `Interaction` row, so `get_user_daily_query_count` and `get_system_daily_cost_usd` read live but always return zero; the per-user and system-wide daily caps cannot fire in production today | Build phase 4.6, feedback capture, the first ticket that writes `interactions` rows |
| F-2.0-10 | `Query.trace_id` is client-supplied and never server-overwritten (Section 20.1 says it should be minted at Guardrail). Live today as a spec-conformance gap; compounds with F-2.0-04 once caps read from `interactions`, since a client that reuses one `trace_id` writes at most one row/day and evades the 100-query cap. Deliberately not fixed alongside F-2.0-09/11/12/13 in phase 2.0, since `trace_id` is a phase 1.0 contract field threading through every `Event`, not a contained fix | Build phase 4.6, taken together with F-2.0-04 so the daily cap is not shipped silently defeatable |
| F-1.2-01 | `RunRegistry._runs` never evicts a completed or abandoned run; every `RunEntry` (queue, buffered events, finished `Task`) is retained for the process lifetime, with no per-user rate limit. Reproduced: 400 runs from one account in 32 seconds, zero rejections | Build phase 4.0, the phase whose own Section 25 line makes this system a public surface for the first time |
| F-1.2-02 | An abandoned client SSE connection does not cancel the server-side run; it executes to completion regardless. React `<StrictMode>` doubles run creation per submit in dev, and the abandoned run is never reclaimed. Compounds F-1.2-01 directly | Build phase 4.0, alongside F-1.2-01 |
| F-1.2-03 | The per-run event queue is destructively single-consumer: a second concurrent or reconnecting SSE client for the same run silently gets zero events and a clean 200, indistinguishable from a run that produced nothing. The concrete, reproduced shape of the `Last-Event-ID` resumability gap the phase 1.2 Scope note already named as deferred | Build phase 4.0, alongside F-1.2-01/02 |
| F-1.2-04 | `POST /auth/signup`'s `409` response on an already-registered email undermines `POST /auth/login`'s own verified anti-enumeration guarantee (identical status and body for wrong-password versus nonexistent-email); `AuthGate.tsx` puts "Sign up" next to "Log in" on the same screen, making the oracle one click away | Build phase 6.1's hardening pass and security scan, or an earlier explicit product-owner decision if judged urgent before then |

## Visualizing this board

`/task-tracker --publish` renders this file as a kanban page in two places:

- `tracker/board.html`, a standalone file. Open it directly in a browser, no server and no network needed.
- A published artifact, for sharing a link with someone who should not have to clone the repo.

Both are generated from this file and are never hand-edited. Editing a generated view is a defect, since the next regeneration discards it silently.
