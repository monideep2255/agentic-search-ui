# Phase 4 continuation prompt

Phase 4 is open: the technical specification and the strategic memo. Phase 3 is complete (PRD locked). Step 4.0 (the API deep dive) is complete; Step 4.1 (outline the tech spec) is next. Use this to resume Phase 4 in a new chat. Living document, updated as Phase 4 progresses.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 4 of System 3 planning: the technical specification and the strategic memo. Step 4.0 is complete; Step 4.1 is next. Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap; Phase 4 is Steps 4.0 to 4.4. The status table shows Phases 1 to 3 complete and Phase 4 in progress.
2. `requirements/PRD.md` - the locked PRD. Every tech-spec requirement traces back to an outcome here.
3. `requirements/Evaluation_playbook.md` - the evaluation approach the tech spec references (competency questions, eval gate, coverage metric, feedback loop).
4. `requirements/phase_1/Phase_1_synthesis.md` - the architecture decisions the tech spec implements.
5. `requirements/phase_4/API_capability_sheet.md` - the Step 4.0 deliverable; every Step 4.1 tool spec is written against this.
6. `DECISIONS.md` - all decisions (102 as of 2026-07-25).

Phases 1, 2, and 3 are complete. Phase 4 produces `requirements/Technical_specification.md` and `requirements/Strategic_memo.md`.

Rules:
- Discuss before drafting. Ask one question at a time.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- Maintain the phase session doc (`requirements/phase_4/Session_<Month>_<Day>.md`) and the meeting-note cadence in `requirements/meetings/`.
- At a sub-phase or phase boundary, run `/phase-checkpoint` to sync the planning docs, then `/ship` to commit and push.
- This documentation is both the project record and a personal learning log.

---

## What Phase 4 produces

- `requirements/Technical_specification.md`: the build blueprint. It translates PRD requirements into implementation decisions and a build order. It references the evaluation playbook and the eval-harness and dev-standards skills rather than restating them.
- `requirements/Strategic_memo.md`: the one-to-two-page executive distillation of the PRD and tech spec, for a stakeholder who needs the decision, not the detail. It serves Bart's leadership-explainability test. It gets updated after the Phase 6 prototype.

## Phase 4 steps

| Step | What it does | Status |
|------|--------------|--------|
| 4.0 | NCBI and enrichment API current-state deep dive: live endpoints, request and response schemas, the exact fields each competency question needs, rate limits, auth, and empty-result behavior. Output: a per-API capability sheet. | Complete (2026-07-25), deliverable `requirements/phase_4/API_capability_sheet.md` |
| 4.1 | Outline the tech spec (the section list in Plan.md Phase 4). | Next |
| 4.2 | Draft the tech spec against the PRD, tracing each requirement to its outcome. | Not started |
| 4.3 | Lock the tech spec. | Not started |
| 4.4 | Draft the strategic memo, distilled from the locked PRD and tech spec. | Not started |

## Start here

Step 4.0 is done: all three Phase 2 feasibility flags resolved, moat cap holds at seven. Q1 (dbVar interval-overlap) needs a two-step tool (ESearch coordinate-range prefilter, then a placement-level post-filter); Q5 (Pathogen Detection) is reached via the FTP results tree (versioned PDG snapshots), no public JSON API exists; Q6 (SRA metadata) is a two-tier access pattern (ESearch fields plus EFetch attributes with tag-name normalization across submitters). Layer 1 (the graph) is trusted from its gate-verified server doc and re-verified live in Phase 6.

Begin Step 4.1 with two open items:

- Layer 1 reachability from the deployed agent (co-locate, a secured remote Postgres role, an SSH tunnel, or a read-only HTTPS query service). The read-only HTTPS query service is the leaning option; the env template blanks the graph host until this is decided.
- The core-outward architecture frame is accepted: one agent core exposing a single service contract (a query in, a cited event stream out), with the UI, the REST plus SSE API, the MCP server, and the CLI as thin adapters over that contract.

The five roadmap tool integrations the tech spec specifies, one section each: cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, each written against the Step 4.0 capability sheet. Apply the supply-chain-security and ai-security-standards rules before wiring any of them.

## Decisions carried in

- The PRD is locked (2026-07-22). It is the reference for every tech-spec requirement; do not reopen it mid-Phase-4 except under the Phase 7 hard-stop exception (a fundamental flaw).
- Build-phase doc-review cadence (2026-07-24): the PRD, tech spec, and memo are authored and locked in Phase 4, frozen through the build, and edited only at the Step 6.2 reconciliation, then re-locked at v1. New-intake is parked during the build and swept once at Step 6.2, not continuously. The evaluation playbook stays a living doc.
- Third-party NCBI MCP servers declined (2026-07-24): the agent uses direct Python tool functions; MCP is outbound-only (reaffirms Decision 24). The three surveyed servers are reference only for the tool specs.
- The risk-tier classification pass was folded into the PRD guardrails (low-risk cite-or-refuse; higher-stakes citation-substantiation plus cross-source triangulation with an answer, flag, or ask trust signal). The tech spec implements it.
- The three-tier harness (guard, plan, synth over LiteLLM and OpenRouter) is specified here in Phase 4; the model per tier is decided in Phase 6 by model-bench.
- Step 4.0 feasibility flags resolved (2026-07-25): Q1 (dbVar interval-overlap, two-step tool), Q5 (Pathogen Detection, FTP results tree), Q6 (SRA metadata, two-tier access) all resolved; the moat cap holds at seven.
- Step 4.1 architecture frame accepted (2026-07-25): build from the agent core outward, one service contract (query in, cited event stream out) with UI, REST plus SSE API, MCP server, and CLI as thin adapters.
- The plan-then-fan-out rule (2026-07-25): the reasoning model plans and decomposes fan-out work, cheaper models execute the bounded pieces in parallel.

## Parked threads for the tech spec

- The A/B test of model combinations (orchestrator plus planner), the online complement to the offline model-bench: design the mechanism (randomized routing, output capture, comparison, LangSmith experiment tracking) here.
- The provenance type's four added fields (evidence-kind, assertion-confidence, population and ancestry context, license) and the answer, flag, ask trust signal: specify here.
- The acceptable-staleness threshold and the concurrency queue strategy: decide here.
- Layer 1 reachability from the deployed agent (co-locate, secured remote Postgres role, SSH tunnel, or a read-only HTTPS query service): open Step 4.1 decision, leaning read-only HTTPS query service.
