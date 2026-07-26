# Build board

The index of every phase. Maintained by the `task-tracker` skill. Per-phase tickets live in `tracker/phase_N.M.md`, created when a phase opens.

Build phases and their dependencies come from `requirements/Technical_specification.md` Section 25, which is the source of truth. This board never invents a phase.

Last updated: 2026-07-26.

## Status counts

| Status | Count |
|--------|-------|
| Done | 5 |
| In progress | 0 |
| Blocked | 0 |
| To do | 26 |

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

| Phase | Branch | Delivers | Depends on | Group | Status | Flags |
|-------|--------|----------|------------|-------|--------|-------|
| 1.0 | `phase/1.0-fastapi-skeleton` | FastAPI skeleton, health endpoint, the `run()` contract stub with the v1 event taxonomy typed, Pydantic boundary validation | none | prototype | todo | |
| 1.1 | `phase/1.1-auth-service` | Minimal v1 auth, the PostgreSQL user-data schema | 1.0 | prototype | todo | |
| 1.2 | `phase/1.2-react-shell-sse` | React shell, SSE consumption, empty chat endpoint wired end to end, the stop button | 1.0 | prototype | todo | product owner required, Playwright gate |
| 2.0 | `phase/2.0-langgraph-agent-loop` | LangGraph loop with stub nodes, the three-tier harness on LiteLLM and OpenRouter, coordinator-worker scaffold, cost caps from day one | 1.0 | prototype | todo | |
| 2.1 | `phase/2.1-cypher-tool` | `cypher_query` over Layer 1, schema slicing, validate-then-execute generation, edge-label enforcement | 2.0 | prototype | todo | |
| 2.2 | `phase/2.2-write-step-grounding` | Deterministic cite-or-refuse, provenance for Layer 1 citations, the first trust signal, the two required tests | 2.1 | prototype | todo | eval-harness gate |
| 3.0 | `phase/3.0-guardrail-node` | Full guardrail replacing the stub: validation, prompt-injection rejection, forbidden types, rate and cost pre-checks | 2.0 | v1 | todo | |
| 3.1 | `phase/3.1-ncbi-efetch` | `ncbi_efetch` over E-utilities and Datasets API v2 | 2.0, 3.0 | v1 | todo | |
| 3.2 | `phase/3.2-ncbi-dbsnp` | `ncbi_dbsnp` over Variation Services, plus the dbVar two-step coordinate-overlap sub-tool | 3.1 | v1 | todo | |
| 3.3 | `phase/3.3-enrichment-tools` | `pubtator_annotate` and `litvar2_lookup`, each with untrusted-source-reader separation | 3.1 | v1 | todo | PubTator3 relations endpoint needs live verification before ship |
| 3.5 | `phase/3.5-pathogen-clinicaltrials-tools` | `pathogen_detection` and `clinicaltrials_search`, completing the seven-tool roster | 3.1 | v1 | todo | |
| 3.4 | `phase/3.4-citation-trust-full` | Provenance extended to Layers 2 and 3, the two-tier risk gate, freshness and conflict resolution | 2.2, 3.1, 3.2, 3.3, 3.5 | v1 | todo | eval-harness gate |
| 4.0 | `phase/4.0-rest-sse-hardening` | The REST plus SSE adapter finalized as the public API surface | 2.2 | v1 | todo | |
| 4.1 | `phase/4.1-mcp-server` | Outbound-only MCP server wrapping the same tool functions | 3.4 | v1 | todo | |
| 4.2 | `phase/4.2-cli-adapter` | Thin CLI client over the REST API | 4.0 | v1 | todo | |
| 4.3 | `phase/4.3-graphql-api` | GraphQL surface via Strawberry, sharing auth and tools with REST | 4.0 | v1 | todo | |
| 4.4 | `phase/4.4-kgx-export` | KGX export utility, a batch job over the existing graph | none in-repo | v1 | todo | |
| 4.5 | `phase/4.5-personalization-memory` | Bounded session memory, audience-level depth control, the named scientist persona | 1.2, 2.2 | v1 | todo | product owner required, Playwright gate |
| 4.6 | `phase/4.6-feedback-capture` | Interaction capture, the manual review ritual, hand-promotion into few-shot examples | 1.1, 3.4 | v1 | todo | |
| 4.7 | `phase/4.7-cq-routing` | Few-shot routing seeded with the seven must-pass questions, query-shape routing | 3.4 | v1 | todo | |
| 5.0 | `phase/5.0-observability` | LangSmith per-run tracing on `trace_id`, PostHog analytics, the tool-call audit log | 2.0 | v1 | todo | |
| 5.1 | `phase/5.1-golden-dataset-eval` | The 50-query golden dataset, eval-harness grading, the cost dashboard | 3.4, 5.0 | v1 | todo | needs a named domain sign-off owner for the clinical fixtures |
| 6.0 | `phase/6.0-rate-limit-concurrency` | Per-layer throttling, the concurrency queue, the 20-calls-per-query budget | 3.1, 3.2, 3.3, 3.5 | v1 | todo | |
| 6.1 | `phase/6.1-hardening-release` | The full dev-standards six-lens pass, CI and CD gates, the security scan, accessibility | everything above | v1 | todo | |
| 7.0 | `phase/7.0-model-bench` | Benchmark candidate models per tier against the golden dataset, pick the winners | 5.1 | v1 | todo | |
| 7.1 | `phase/7.1-ab-mechanism` | The online A and B randomized-routing mechanism | 7.0, 5.0 | v1 | todo | |

## Open flags

| Flag | Detail | Resolve before |
|------|--------|----------------|
| Golden fixture domain sign-off | Nobody is named to verify the clinical and human-variation expected answers. A wrong expected answer makes a wrong agent pass, which is the failure the gate exists to catch | Build phase 5.1 |
| PubTator3 relations endpoint | Path and fields not live-verified | Build phase 3.3 ship |
| Playwright not installed | The UI gate has no tool behind it yet, and it must clear `supply-chain-security` first | Build phase 1.2 |

## Visualizing this board

`/task-tracker --publish` renders this file as a kanban page in two places:

- `tracker/board.html`, a standalone file. Open it directly in a browser, no server and no network needed.
- A published artifact, for sharing a link with someone who should not have to clone the repo.

Both are generated from this file and are never hand-edited. Editing a generated view is a defect, since the next regeneration discards it silently.
