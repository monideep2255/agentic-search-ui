# System 3 technical specification

The build blueprint for System 3. It translates the locked PRD and the Phase 4 core-architecture decisions into implementation decisions and a build order.

Status: Step 4.1 outline, drafted 2026-07-25. This is the section skeleton with a scope note and a traceability line per section. Step 4.2 expands each section into full content, Step 4.3 locks it. It references the evaluation playbook (requirements/Evaluation_playbook.md) and the eval-harness and dev-standards skills rather than restating them.

Traceability: every section traces back to a PRD outcome and to the core-architecture decisions in DECISIONS.md (Decisions A, C, D, E, F, G, and the cost amendment, all 2026-07-25) and to the verified API capability sheet (requirements/phase_4/API_capability_sheet.md).

## Table of contents

- [How to read this](#how-to-read-this)
- [1. System architecture overview](#1-system-architecture-overview)
- [2. The core service contract](#2-the-core-service-contract)
- [3. Model orchestration and the harness](#3-model-orchestration-and-the-harness)
- [4. Caching](#4-caching)
- [5. Three-layer data access](#5-three-layer-data-access)
- [6. Tool specifications](#6-tool-specifications)
- [7. Data freshness and conflict resolution](#7-data-freshness-and-conflict-resolution)
- [8. Synthesis and the trust signal](#8-synthesis-and-the-trust-signal)
- [9. Provenance and citation model](#9-provenance-and-citation-model)
- [10. Guardrail implementation](#10-guardrail-implementation)
- [11. Security implementation](#11-security-implementation)
- [12. Frontend architecture](#12-frontend-architecture)
- [13. Delivery surfaces](#13-delivery-surfaces)
- [14. Personalization and memory](#14-personalization-and-memory)
- [15. Auth and user data model](#15-auth-and-user-data-model)
- [16. Feedback loop pipeline](#16-feedback-loop-pipeline)
- [17. Competency question routing](#17-competency-question-routing)
- [18. Model selection and the A/B mechanism](#18-model-selection-and-the-ab-mechanism)
- [19. Cost control](#19-cost-control)
- [20. Observability](#20-observability)
- [21. Rate limiting and concurrency](#21-rate-limiting-and-concurrency)
- [22. Edge cases and failure states](#22-edge-cases-and-failure-states)
- [23. Testing strategy](#23-testing-strategy)
- [24. Deployment](#24-deployment)
- [25. Build order](#25-build-order)
- [Parked-thread resolution index](#parked-thread-resolution-index)

## How to read this

The spine is one agent core that exposes a single typed event stream, with four delivery surfaces (UI, REST plus SSE API, MCP server, CLI) as thin adapters over that stream. Retrieval feeds structured results into the core, the Write step synthesizes and grounds them, and the stream carries the cited result out to whichever surface asked. Sections 1 to 4 set the core, 5 to 7 the data and tools, 8 to 11 answer quality and trust, 12 to 14 the surfaces and experience, 15 to 21 data, learning, and operations, and 22 to 25 quality and delivery.

## 1. System architecture overview

Scope: the agent core (the Guardrail, Think, Plan, Act, Write loop), the three data layers, and the one-core-with-adapters model. A system diagram, the request path from a surface through the core to retrieval and back, and the boundaries between components.
Draws from: Decision A (one core, adapters filter), the PRD architecture section, the Phase 1 synthesis.

## 2. The core service contract

Scope: the single internal interface every surface calls, `run(query, context)` returning a typed event stream. The event taxonomy (guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done), the versioning (v1), inline citation binding, and the rule that reasoning is a curated plan-step narrative, never raw chain-of-thought. Defines which surface consumes which events.
Draws from: Decision A and the cost amendment.

## 3. Model orchestration and the harness

Scope: the three tiers (guard, plan, synth) over LiteLLM and OpenRouter, and the coordinator-worker split (non-LLM code executes tool calls; a cheap isolated reader extracts structured findings from untrusted free text; Synth never sees a raw payload). The reader is scoped to untrusted free text only. Model per tier is deferred to Phase 6 model-bench. The harness is an in-process module in v1 and owns the cost caps.
Draws from: Decision C, DECISIONS.md rows on the harness and coordinator-worker, the capability sheet's tool-layer implications.

## 4. Caching

Scope: prompt caching via OpenRouter (a stable cache-hot prefix of system instructions, tool schemas, and the graph and BioLink schema, then a dynamic suffix, with the tool list frozen and deterministically sorted), and response caching for Layer 2 and Layer 3 (Redis, with the verified TTLs: gene one week, variant one week, publication one day). Cache efficiency is a first-class metric.
Draws from: the prompt-cache-discipline rule, the capability sheet TTLs, the Phase 1 caching decision.

## 5. Three-layer data access

Scope: how the core reaches each layer. Layer 1 (the graph) through the cypher_query tool over the transport-per-phase path (SSH tunnel or co-location for the prototype, a thin read-only HTTPS query service for v1, database port never opened, transport hidden inside the tool). Layer 2 and Layer 3 as HTTPS calls through the API-caller pattern that returns structured, schema-validated results. One tool, one layer.
Draws from: Decision D, the capability sheet, the three-layer data architecture doc, system-design-patterns rule 3.

## 6. Tool specifications

Scope: one subsection per tool, cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, each with its input and output JSONSchema (maxLength on strings, maxItems on arrays, host-pinned source_url), the endpoints and fields it uses, its error and empty behavior, and its per-call timeout. The per-competency-question required-IDs-and-fields spec (reference/.../02_Tier1_eval_spec.md) is the input-output contract. The dbVar coordinate-overlap tool implements the two-step prefilter-then-placement-filter.
Draws from: the capability sheet (the direct source), the multi-agent pipeline gate in production-standards, the Q1 finding.

## 7. Data freshness and conflict resolution

Scope: the acceptable-staleness threshold per layer, and layer priority when the graph snapshot and a live API disagree (live API wins for currency, the graph for traversal breadth, both cited). How freshness and assembly or version context is surfaced on coordinate and sequence answers.
Draws from: Decision on data freshness (Step 1.10), the eval rubric freshness criterion. Resolves the parked acceptable-staleness threshold.

## 8. Synthesis and the trust signal

Scope: the Write step. Deterministic synthesis over structured tool_result findings, deterministic cite-or-refuse grounding (exact or substring match after normalization, never fuzzy), and the deterministic trust signal (a rule over risk-tier, grounded, and triangulated yielding answer, flag, ask, or refuse). The refuse path emits a URL-encoded, host-pinned NCBI cross-database search link.
Draws from: Decision E, the AI answer grounding gate in production-standards, the assemble-not-classify boundary in the playbook.

## 9. Provenance and citation model

Scope: the provenance type carried on every citation event, source, source_id, source_url, layer, plus the four added fields (evidence-kind, assertion-confidence, population and ancestry context, license). The host-pinned source_url regex per layer. How inline citation markers bind to citation events, and the exportable citation format for the paper-writing use.
Draws from: Decision A citation event, Decision F (paper-facing export), the provenance decision (Step 1.12). Resolves the parked four-provenance-fields thread.

## 10. Guardrail implementation

Scope: the Guardrail step. Input validation with Pydantic at the FastAPI boundary, prompt-injection rejection, forbidden query types, read-only enforcement, and the rate and cost pre-checks that gate what reaches Think.
Draws from: the PRD guardrails, ai-security-standards, production-standards input handling.

## 11. Security implementation

Scope: prompt-injection defense across the loop (untrusted Layer 2 and Layer 3 content is data, never instructions), the untrusted-source reader tier separation (Read plus one API, no Write, no other tools), PII handling on captured interactions, secrets in env only, and the audit trail of tool calls.
Draws from: ai-security-standards, production-standards multi-agent gate, supply-chain-security, Decision C reader isolation.

## 12. Frontend architecture

Scope: the React UI as an adapter over the event stream. SSE consumption, streaming of the curated Think and Plan narrative with a stop button, inline citation chips, loading and empty states, the guardrail and cap messages (no dollar figures), and the named scientist persona rendered at this layer. Accessibility to Section 508 and WCAG 2.1 AA.
Draws from: Decision A, Decision F persona, the cost amendment (builder-only), the PRD UI section.

## 13. Delivery surfaces

Scope: the other three adapters. The REST plus SSE API (the event stream over HTTP), the MCP server (outbound-only, wrapping the contract as tools for agent and LLM consumers, persona 11), and the CLI (a thin client over the REST API). Each filters the event stream to what it needs; the operator dashboard adapter renders the cost event, the end-user surfaces filter it out.
Draws from: Decision A, Decision 24 (MCP outbound-only), the cost amendment.

## 14. Personalization and memory

Scope: personalization lives in orchestration and memory, never in grounding. The stable named persona (presentation), in-conversation session memory as a bounded running summary (resolved entities, compressed prior findings with trace references, open threads) injected into Think and Plan in the live tail under a hard cap, and audience-level depth as an explicit control. Persistent cross-session memory and store-plus-retrieval are marked fast-follow.
Draws from: Decision F, Decision G, the bounded-context rule in production-standards.

## 15. Auth and user data model

Scope: the auth service and the PostgreSQL user-data schema. The interactions table (query, normalized entities, route, rubric outcome, citations, coverage tags, feedback, trace_id) and the cq_candidates table, which are the shared substrate for the feedback loop and for persistent memory. Separate from the read-only graph.
Draws from: Decision G, the playbook data-storage section.

## 16. Feedback loop pipeline

Scope: the five-stage loop (capture, mine and cluster, human-gated review, trigger, few-shot promotion). v1 ships capture plus a manual review ritual plus hand-promotion; stage-2 automated mining is a fast-follow. Where the LLM-judge sits (a filter upstream of the human, never the final say). Privacy and retention on captured interactions.
Draws from: Decision G, the evaluation playbook online-feedback-loop section (referenced, not restated).

## 17. Competency question routing

Scope: few-shot routing in the orchestrator now, and the upgrade path later. How a promoted competency question becomes a few-shot example plus an eval case, and how Think routes by query shape (single-hop to Layer 2, multi-hop to Layer 1, dynamic multi-source to the full loop), defaulting to exact ID and CURIE retrieval.
Draws from: the Phase 0 few-shot decision, the Step 1.11 routing decision, the playbook.

## 18. Model selection and the A/B mechanism

Scope: model-bench offline as the primary tier-selection method (deferred to Phase 6), and the online A/B mechanism (randomized routing across orchestrator-plus-planner combinations, output capture, comparison, LangSmith experiment tracking). How the two compose.
Draws from: the model-selection section of the playbook, the parked A/B thread. Resolves the parked A/B model-combination mechanism.

## 19. Cost control

Scope: the hard caps (per-query, per-user daily, system-wide daily, per-step timeout), enforced in the harness. The cost event on the contract, the builder-only live meter and aggregate dashboard, and the graceful user-facing cap message with no dollar figure.
Draws from: the cost-control decision (safety-critical), the cost amendment, system-design-patterns rule 4.

## 20. Observability

Scope: LangSmith for per-run traces (linked by trace_id), PostHog for behavioral analytics, and the tool-call audit log. How traces feed the offline eval graders and the cost dashboard.
Draws from: the Phase 1 stack decisions (LangSmith, PostHog), the playbook.

## 21. Rate limiting and concurrency

Scope: per-layer throttling (E-utilities 3 or 10 per second, Variation Services about 1 per second, the enrichment and Datasets limits), the shared cap across concurrent users, and the concurrency queue strategy (who gets throttled, queued, prioritized, or failed fast). The at-most-20-API-calls-per-query budget.
Draws from: the capability sheet limits, the rate-limiting decision (Step 1.10). Resolves the parked concurrency queue strategy.

## 22. Edge cases and failure states

Scope: empty results, partial-layer failures, ambiguous queries, guardrail rejections, timeouts, mid-stream errors (partial result plus error, never a blank screen), and retry safety (idempotent tool calls, actionable errors). Ties each to the event stream so the surfaces render it.
Draws from: Decision A error event, the PRD edge-cases section, production-standards retry-safety gate, the verified API error and empty behavior.

## 23. Testing strategy

Scope: unit tests, integration tests against a real graph and live APIs where feasible, the eval harness (pass@k, pass^k, the pass/fail/abstain model), and the 50-query golden dataset. The cite-or-refuse and zero-retrieval refusal tests are required paths. References the eval-harness skill and the evaluation playbook rather than restating the metrics.
Draws from: the evaluation playbook, the eval-harness skill, production-standards testing bar.

## 24. Deployment

Scope: Railway hosting, the environment configuration (the env surface in env.example), CI and CD with the merge-blocking gates and the security-scan milestone, and the read-only HTTPS graph query service on the Hetzner box for v1.
Draws from: the Phase 1 hosting decision, Decision D, the release-workflow skill, env.example.

## 25. Build order

Scope: the phased build with dependencies, refining the CLAUDE.md build order against these decisions. The order in which the core, the tools, the surfaces, and the feedback loop come online, and which capabilities are v1 versus fast-follow.
Draws from: all decisions above, the CLAUDE.md build order, Plan.md Phase 6.

## Parked-thread resolution index

The four threads carried into Phase 4 resolve in these sections:

| Parked thread | Resolved in |
|---------------|-------------|
| A/B model-combination mechanism | Section 18 |
| Acceptable-staleness threshold | Section 7 |
| Concurrency queue strategy | Section 21 |
| Provenance type's four added fields | Section 9 |

Last updated: 2026-07-25. This is the Step 4.1 outline; Step 4.2 expands each section into full content.
