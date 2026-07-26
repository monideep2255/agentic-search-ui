# Phase 4 session, July 25

Step 4.0 of Phase 4 closes here: the NCBI and enrichment API current-state deep dive. This session produced the per-API capability sheet, resolved all three Phase 2 feasibility flags, mined the Agentic-Search reference repo for design intent, and opened the Step 4.1 architecture discussion. This file is the project record and a personal learning log.

## Table of contents

- [Where we started](#where-we-started)
- [The capability sheet](#the-capability-sheet)
- [Feasibility flags resolved](#feasibility-flags-resolved)
- [Layer 1 disposition](#layer-1-disposition)
- [Reference repo mining](#reference-repo-mining)
- [New rule: plan-then-fan-out](#new-rule-plan-then-fan-out)
- [Config surface updated](#config-surface-updated)
- [Fresh-context grading](#fresh-context-grading)
- [Step 4.1 opened](#step-41-opened)
- [Step 4.1 core-architecture decisions](#step-41-core-architecture-decisions)
- [Step 4.2 seven-agent draft](#step-42-seven-agent-draft)
- [Step 4.3 reconciliation and lock](#step-43-reconciliation-and-lock)

## Where we started

Phase 4 opened on 2026-07-24 with process questions settled and Step 4.0 next. Step 4.0 is the constraint step: the Step 4.1 tool specifications for cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, and litvar2_lookup are written against whatever this deep dive verifies, and it converts the Phase 2 feasibility flags (Q1, Q5, Q6) from lightweight notes into verified API behavior.

## The capability sheet

Produced `requirements/phase_4/API_capability_sheet.md` (365 lines). Scope decision: live-verify every Layer 2 and Layer 3 API surface the five roadmap tools touch, and document each tool-touched database at its general capability surface rather than only the fields the moat-seven competency questions need. The moat-seven serve as verification anchors, not the scope ceiling, because the tool specs must serve the general agent.

Verified live on 2026-07-25 against the production endpoints: eutils.ncbi.nlm.nih.gov, api.ncbi.nlm.nih.gov (Datasets API v2 and Variation Services), ftp.ncbi.nlm.nih.gov (Pathogen Detection), pubchem.ncbi.nlm.nih.gov, the Layer 3 enrichment APIs (PubTator3, LitVar2, LitSense), and clinicaltrials.gov. Every non-trivial claim in the sheet is backed by a live call made this session, not carried forward from the Phase 1 survey without re-checking.

A load-bearing finding for the cite-or-refuse gate: E-utilities returns HTTP 200 for empty results and for several error classes (invalid db name, an unknown field tag that silently falls back to a broad search). The tool layer must inspect the response body, keying the refusal path on `count = 0`, never on HTTP status.

## Feasibility flags resolved

All three Phase 2 feasibility flags resolve, and the moat-seven all hold: the cap stays at seven competency questions, no demotions.

| Flag | Question | Verdict |
|------|----------|---------|
| Q1 | dbVar interval-overlap for large structural variants | Resolved, conditional. ESearch coordinate-range is a coarse multi-valued prefilter, not true interval overlap; live probes proved false positives (a point insertion matched a 2.5Mb span query via cross-assembly coordinate mixing). True overlap needs a two-step tool: ESearch range as prefilter, then a placement-level post-filter in tool code. |
| Q5 | Pathogen Detection access | Resolved, feasible. No public JSON API exists (the isolates-browser path serves the HTML web app). The FTP results tree (versioned PDG snapshots: Metadata, Clusters, AMR, SNP_trees) is the only verified programmatic path, pinned to the latest complete snapshot and cached. |
| Q6 | SRA metadata field availability | Resolved, feasible. Two-tier access: 22 ESearch-indexed fields for filtering, plus EFetch sample attributes (serovar, isolation_source, geo_loc_name, collection_date) for the match rationale. Attribute tag names vary by submitter, so the tool must normalize them. |

## Layer 1 disposition

Layer 1 (the AGE knowledge graph) is SSH-only and firewalled, unreachable from the planning sandbox. Its schema (10 concept labels, 14 edge predicates), indexes, and smoke-test suite are already gate-verified (2026-04-22) in `docs/data-engineering/Knowledge_graph_on_server_reference.md`. The cypher_query tool spec is written against that doc, and Layer 1 is re-verified live in Phase 6 when the tool connects over the real DSN.

## Reference repo mining

Four Sonnet agents mined the Agentic-Search reference repository in parallel: API tool decomposition and prior-art patterns, architecture and orchestration design, harness and caching patterns, and prior proposals. Findings folded into the capability sheet's tool-layer design implications section: caching strategy, security patterns already proven in a working build, and prior-art tool decomposition to inform the Step 4.1 tool specs.

## New rule: plan-then-fan-out

Added `.claude/rules/plan-then-fan-out.md`: the reasoning model plans and decomposes fan-out work, cheaper models (Sonnet 5, Haiku 4.5) execute the bounded pieces in parallel. Logged as a decision: a fan-out of five reasoning-model agents hit a session limit together this session, and the re-run as scoped Sonnet tasks succeeded. Added to both this repo and personal-os-work.

## Config surface updated

`env.example` and `.env` were updated with the full config surface the capability sheet surfaced: the E-utilities API key, the Variation Services base URL, the Pathogen Detection FTP root, and the Layer 1 graph host, left blank pending the Step 4.1 reachability decision. `.env` stays gitignored throughout.

## Fresh-context grading

The capability sheet was graded by a fresh-context agent per self-eval-loop.md: the grading agent received only the sheet and a pass/fail checklist, no authoring context. Six fixes came back from the grading pass and were applied before the sheet was called done.

## Step 4.1 opened

Step 4.1 (outline the tech spec) discussion has started. Architecture frame accepted: build from the agent core outward. One agent core exposes a single service contract (a query in, a cited event stream out), with the UI, the REST plus SSE API, the MCP server, and the CLI as thin adapters over that contract. The four delivery surfaces become cheap once the core contract is right, and the frame avoids baking surface-specific logic into the core. Layer 1 reachability from the deployed agent (co-locate, a secured remote Postgres role, an SSH tunnel, or a read-only HTTPS query service) is an open Step 4.1 decision, with the read-only HTTPS query service the leaning option.

## Step 4.1 core-architecture decisions

Later in the same day, the Step 4.1 core-architecture discussion locked seven decisions (A, the cost amendment, C, D, E, F, G), building directly on the core-outward frame opened above. Together they answer what the core service contract carries, how the harness stays cheap while staying safe, where Layer 1 lives at each build stage, how the Write step decides to answer or refuse, and how personalization and memory attach without touching grounding.

- Decision A, the core service contract: the core exposes a single typed event stream (guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done), versioned v1. Every surface, the UI, the REST plus SSE API, the MCP server, the CLI, is a thin adapter that subscribes and filters this one stream rather than getting its own contract. Citations bind inline through a token-stream marker keyed to a citation event. Reasoning is surfaced as a curated plan-step narrative, never the raw chain-of-thought, so a crafted or injected field inside a retrieved document can never leak through as if it were the agent's own reasoning.
- Cost event and builder-only cost visibility, an amendment to Decision A: the harness emits a running per-query cost on a cost event and a total on the done event, but the live per-query meter and the per-user-daily and system-daily dashboard are an operator view only. The end-user UI adapter filters the cost event out entirely, so a capped-out user sees a graceful limit message with no dollar amount. This keeps the research-partner feel intact instead of turning every query into a billing display.
- Decision C, the harness: the coordinator-worker split from the 2026-07-21 Phase 1 decision stands as v1's harness, and the untrusted-content reader is scoped down to untrusted free text only. Structured graph rows and structured API fields go straight to the Synth model with no reader pass; only free-text payloads, abstracts, annotations, record bodies, get the cheap isolated reader. Fewer reader passes means lower latency, and the passes that remain run in parallel and overlap with streaming.
- Decision D, Layer 1 transport, transport-per-phase: the Phase 6 prototype reuses connection.py over an SSH tunnel or co-location (localhost, zero new build), and v1 moves to a thin read-only HTTPS query service on the box. The database port never opens to the internet at either stage, and the transport choice stays sealed inside the cypher_query tool, so swapping it later is a two-way door, not a rebuild.
- Decision E, the Write step and trust signal: a deterministic rule over risk-tier, grounded, and triangulated yields one of answer, flag, ask, or refuse. Grounding is an exact or substring match after normalization, never fuzzy. Risk tier is a deterministic intent classification. Triangulation is a structural concordance check that accepts some over-flagging rather than risk a false pass. When the outcome is refuse, the response carries a fallback deep-link to NCBI cross-database search, pre-filled with the URL-encoded, host-pinned query, so a dead end still hands the user a next step.
- Decision F, personalization: per-user context stays in scope and on the roadmap, but it lives in orchestration and memory, never in grounding, so the answer engine stays deterministic and user-independent at the claim level. V1 ships the grounded core, a stable named scientist persona that is presentation-only, and in-conversation session memory. Persistent cross-session per-user memory is a fast-follow built on the interaction capture. Audience-level depth is an explicit control, and paper-facing provenance and export are first-class.
- Decision G, feedback loop and memory: the Phase 2 five-stage loop (capture, mine, human-gated review, trigger, few-shot promotion) stands, with v1 shipping capture plus manual review plus hand-promotion and stage-2 automation deferred. The interactions table is the shared substrate for both the global routing loop and the later persistent per-user memory. V1 session memory itself is a bounded running summary, resolved entities, compressed prior findings with trace references, open threads, injected into Think and Plan in the live tail under a hard cap, and it never counts as grounding.

The through-line across all seven: keep the core contract, the harness, and the trust signal deterministic and cheap, push anything personalized or judgment-heavy (persona, memory, cost detail) into a filtered adapter layer that sits outside the grounding path. Parked from this discussion for the tech-spec outline: the A/B model-combination mechanism, the acceptable-staleness threshold, the concurrency queue strategy, and the provenance type's four added fields.

## Step 4.2 seven-agent draft

With the outline locked (Step 4.1) and the core-architecture decisions in hand (Decisions A, C, D, E, F, G, plus the cost amendment), Step 4.2 drafted the tech spec to implementation level. Per the plan-then-fan-out rule added in Step 4.0, the reasoning pass planned the section boundaries and dependencies, then seven scoped Sonnet agents (`ts-core`, `ts-data`, `ts-trust`, `ts-surfaces`, `ts-delivery`, `ts-ops1`, `ts-ops2`) drafted their assigned sections in parallel: the core service contract and harness, the three-layer data access and tool specifications, the provenance and trust-signal machinery, the frontend and delivery surfaces, the auth and feedback-loop model, and the two operations clusters (cost, rate limiting, observability, testing, deployment, build order). Every section traces back to a PRD outcome and to a Phase 4 core-architecture decision, per the traceability line at the top of the document. Output: 25 sections at implementation level (commit `f6bd667`).

Drafting in parallel left seams: the citation, cost, and error event schemas were specified slightly differently by the agents that touched them, the tool roster carried a gap (no tool for Pathogen Detection or ClinicalTrials.gov), and the delivery-surface framing still named four adapters instead of the six the locked PRD commits to. These became the Step 4.3 reconciliation's open items.

## Step 4.3 reconciliation and lock

`reconcile-techspec` unified the open items across the seven-agent draft: the citation, cost, and error event schemas now resolve against the canonical Section 2 and Section 9 definitions rather than each section's local variant; the tool roster grew from five to seven with `pathogen_detection` (Q5, the Pathogen Detection FTP results tree) and `clinicaltrials_search` (Q4, ClinicalTrials.gov v2) added as named tools, one tool per access path, with the Datasets API v2 folded in as an `ncbi_efetch` action; and the delivery surfaces reconciled to six thin adapters over the one core contract (Web UI, REST plus SSE API, GraphQL API, MCP server, KGX export, CLI), matching the five v1 delivery formats the PRD locks (commit `1bcfce8`). The four Phase 4 parked threads were also resolved in this pass: the acceptable-staleness threshold (Layer 1 graph-only, 30 days volatile with an auto live-API cross-check, 90 days stable, live APIs remain the source of truth for current values), the provenance type's four added fields (`evidence_kind`, `assertion_confidence`, `population_ancestry_context`, `license`, each a deterministically populated enum), the online A/B model-combination mechanism (session-level randomization over plan-plus-synth model pairs, human-gated), and the concurrency queue strategy (a bounded FIFO per API family with fail-fast on the latency budget).

The reconciled draft went through two fresh-context grading passes per self-eval-loop. The first grading pass (`grade-techspec`) found a schema-consistency failure: residual event and field definitions in a few sections still disagreed with the newly canonical Section 2 and Section 9 definitions. Those leftovers were fixed (commit `4ba8ddc`). A second, independent fresh-context pass (`regrade-techspec`) re-graded the corrected spec and verified the schema-consistency failure cleared, with no new failures surfaced.

With both grading passes clean, the user reviewed the reconciled spec and gave the Step 4.3 lock sign-off. `requirements/Technical_specification.md` is locked (2026-07-25): 25 sections, seven tools, six delivery surfaces, one canonical event and provenance schema. Per the build-phase doc-review cadence, it now freezes through the build and is edited only at the Step 6.2 reconciliation, then re-locked at v1. Step 4.4, the strategic memo, is next.
