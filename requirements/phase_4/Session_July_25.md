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
