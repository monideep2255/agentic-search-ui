# Phase 4 continuation prompt

Phase 4 is COMPLETE (closed 2026-07-25): the technical specification and the strategic memo are both done, all of Steps 4.0 to 4.4 complete. There is no remaining Phase 4 work. The next phase is Phase 5 (system and tooling updates); see `requirements/Plan.md` for its scope. This file is kept as the Phase 4 record.

## Context to provide

Paste the following into your new chat:

---

Phase 4 of System 3 planning is complete: the technical specification and the strategic memo are both done (Steps 4.0 to 4.4). Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap; the status table shows Phases 1 to 4 complete and Phase 5 next.
2. `requirements/PRD.md` - the locked PRD. Every tech-spec requirement traces back to an outcome here.
3. `requirements/Evaluation_playbook.md` - the evaluation approach the tech spec references (competency questions, eval gate, coverage metric, feedback loop).
4. `requirements/Technical_specification.md` - the locked tech spec (2026-07-25).
5. `requirements/Strategic_memo.md` - the executive distillation of the PRD and tech spec (2026-07-25).
6. `DECISIONS.md` - all decisions (113 as of 2026-07-25).

Phases 1, 2, 3, and 4 are complete. Phase 4 produced `requirements/Technical_specification.md` (locked) and `requirements/Strategic_memo.md` (done). Phase 5 (system and tooling updates) is next.

Rules:
- Discuss before drafting. Ask one question at a time.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- Maintain the phase session doc (`requirements/phase_4/Session_<Month>_<Day>.md`) and the meeting-note cadence in `requirements/meetings/`.
- At a sub-phase or phase boundary, run `/phase-checkpoint` to sync the planning docs, then `/ship` to commit and push.
- This documentation is both the project record and a personal learning log.

---

## What Phase 4 produces

- `requirements/Technical_specification.md`: the build blueprint. It translates PRD requirements into implementation decisions and a build order. It references the evaluation playbook and the eval-harness and dev-standards skills rather than restating them. Locked 2026-07-25.
- `requirements/Strategic_memo.md`: the one-to-two-page executive distillation of the PRD and tech spec, for a stakeholder who needs the decision, not the detail. It serves the leadership-explainability test. It gets updated after the Phase 6 prototype.

## Phase 4 steps

| Step | What it does | Status |
|------|--------------|--------|
| 4.0 | NCBI and enrichment API current-state deep dive: live endpoints, request and response schemas, the exact fields each competency question needs, rate limits, auth, and empty-result behavior. Output: a per-API capability sheet. | Complete (2026-07-25), deliverable `requirements/phase_4/API_capability_sheet.md` |
| 4.1 | Outline the tech spec (the section list in Plan.md Phase 4). | Complete (2026-07-25), core-architecture decisions (A, C, D, E, F, G, plus the cost amendment) locked, outline became the 25-section table of contents |
| 4.2 | Draft the tech spec against the PRD, tracing each requirement to its outcome. | Complete (2026-07-25), seven parallel agents drafted 25 sections at implementation level |
| 4.3 | Lock the tech spec. | Complete (2026-07-25), reconciled, graded twice fresh-context, locked. Deliverable `requirements/Technical_specification.md` |
| 4.4 | Draft the strategic memo, distilled from the locked PRD and tech spec. | Complete (2026-07-25), deliverable `requirements/Strategic_memo.md` |

## Start here

Phase 4 is complete. `requirements/Technical_specification.md` (25 sections, seven tools, six delivery surfaces, one canonical event and provenance schema) is the build blueprint and freezes through the build per the doc-review cadence, edited only at the Step 6.2 reconciliation. `requirements/Strategic_memo.md` is the executive distillation for a stakeholder who needs the decision, not the detail. There is no remaining Phase 4 work. Next: Phase 5 (system and tooling updates), see `requirements/Plan.md`.

The tech spec's seven tools, one section each: cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Apply the supply-chain-security and ai-security-standards rules before wiring any of them in Phase 6.

## Decisions carried in

- The PRD is locked (2026-07-22). It is the reference for every tech-spec requirement; do not reopen it mid-Phase-4 except under the Phase 7 hard-stop exception (a fundamental flaw).
- Build-phase doc-review cadence (2026-07-24): the PRD, tech spec, and memo are authored and locked in Phase 4, frozen through the build, and edited only at the Step 6.2 reconciliation, then re-locked at v1. New-intake is parked during the build and swept once at Step 6.2, not continuously. The evaluation playbook stays a living doc.
- Third-party NCBI MCP servers declined (2026-07-24): the agent uses direct Python tool functions; MCP is outbound-only (reaffirms Decision 24). The three surveyed servers are reference only for the tool specs.
- The risk-tier classification pass was folded into the PRD guardrails (low-risk cite-or-refuse; higher-stakes citation-substantiation plus cross-source triangulation with an answer, flag, or ask trust signal). The tech spec implements it.
- The three-tier harness (guard, plan, synth over LiteLLM and OpenRouter) is specified here in Phase 4; the model per tier is decided in Phase 6 by model-bench.
- Step 4.0 feasibility flags resolved (2026-07-25): Q1 (dbVar interval-overlap, two-step tool), Q5 (Pathogen Detection, FTP results tree), Q6 (SRA metadata, two-tier access) all resolved; the moat cap holds at seven.
- Step 4.1 core-architecture decisions locked (2026-07-25): Decision A, the core service contract (a single typed, versioned v1 event stream: guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done; every surface is a thin filtering adapter; reasoning surfaces as a curated plan-step narrative, never raw chain-of-thought), with a cost-event amendment (builder-only cost visibility). Decision C, the harness (coordinator-worker stands; the untrusted-content reader is scoped to untrusted free text only). Decision D, Layer 1 transport-per-phase (SSH tunnel or co-location for the Phase 6 prototype, a read-only HTTPS query service for v1). Decision E, the Write step and trust signal (a deterministic rule over risk-tier, grounded, and triangulated yields answer, flag, ask, or refuse). Decision F, personalization (in scope but lives in orchestration and memory, never in grounding). Decision G, feedback loop and memory (the Phase 2 five-stage loop stands, v1 ships capture plus manual review plus hand-promotion).
- Steps 4.2 and 4.3 (2026-07-25): the tech spec drafted (seven parallel agents, 25 sections at implementation level) and reconciled (citation, cost, and error event schemas unified against Section 2 and Section 9; tool roster expanded from five to seven with `pathogen_detection` and `clinicaltrials_search`; delivery surfaces reconciled to six against the locked PRD). Graded twice fresh-context per self-eval-loop, the schema-consistency failure cleared and verified on the re-grade, then locked. The four parked threads below all resolved in this pass.
- Tech spec locked (2026-07-25): `requirements/Technical_specification.md`, 25 sections, seven tools, six delivery surfaces. Freezes through the build, edited only at the Step 6.2 reconciliation. 113 decisions logged.

## Parked threads: resolved in the tech spec

All four threads carried into Phase 4 resolved during the Step 4.3 reconciliation:

- The A/B model-combination mechanism: session-level randomization over plan-plus-synth model pairs, human-gated.
- The provenance type's four added fields: `evidence_kind`, `assertion_confidence`, `population_ancestry_context`, `license`, each a deterministically populated enum.
- The acceptable-staleness threshold: Layer 1 graph-only (30 days volatile with an auto live-API cross-check, 90 days stable); live APIs remain the source of truth for current values.
- The concurrency queue strategy: a bounded FIFO per API family with fail-fast on the latency budget.
