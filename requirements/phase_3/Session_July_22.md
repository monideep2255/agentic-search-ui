# Phase 3 session, July 22

Phase 3 of System 3 planning: the PRD. Completed in one working session on 2026-07-22, directly after Phase 2. This file is the project record and a personal learning log.

## Table of contents

- [Where we started](#where-we-started)
- [Step 3.1: outline](#step-31-outline)
- [Step 3.2: draft](#step-32-draft)
- [Step 3.3: lock](#step-33-lock)

## Where we started

Phase 2 finished the evaluation playbook. Phase 3 turns the locked Phase 1 synthesis and the Phase 2 playbook into the PRD, the single source of truth for what System 3 does, for whom, and how success is measured.

Framing question settled first: who is the primary reader? Confirmed the primary reader is Anne and the NCBI stakeholders who decide whether the wedge is real and worth backing, with the build team as the secondary reader who inherits the PRD as the build contract. So the PRD leans on outcomes, the wedge, and success criteria up front.

## Step 3.1: outline

Pulled the spec template (`reference/personal-os-work/NIH/Agentic-Search/Specs/_templates/PRODUCT.md`) and the milestone-ladder spine from the synthesis. Key structural decision, already made in Phase 1: the outcomes-and-stakeholders section is the logic model, built on Anne's four gates (G1 tools work alone and G2 cross-layer join serve the build team; G3 cited SME-credible answers serves the researcher and SME reviewer; G4 reuse-ready formats serves external adopters and NCBI leadership; Bart's leadership-explainability test is served by the strategic memo, not a code gate).

Confirmed the 15-section outline, ordered for the stakeholder reader: the case first (problem and wedge, outcomes, success, personas, acceptance criteria), then the build contract (flows, UI, cost UX, edge cases, guardrails, security, accessibility, delivery formats), then the boundaries (out of scope, open items).

## Step 3.2: draft

Read the full Phase 1 synthesis to ground the build-contract sections in real decisions rather than memory, then drafted `requirements/PRD.md` against the confirmed outline. Operational eval numbers are referenced to the playbook, not restated.

Operationalized the risk-tier classification pass that Phase 1 deferred to Phase 3: low-risk answers (lookups, cross-database assembly) enforce standard cite-or-refuse; higher-stakes answers (clinical-adjacent, mechanistic claims) additionally require a citation-substantiation check and a cross-source triangulation gate, surfaced through an answer, flag, or ask trust signal.

Graded the draft with a fresh-context agent against a decision-fidelity, arc, milestone-ladder, playbook-discipline, completeness, no-fabrication, and writing-style checklist. Result: 7 of 7 pass. Three minor fixes applied: grounded the epidemiologist ranking to the Jira and roadmap evidence, named the three model tiers in open items, and made the Q1 seven-versus-six contingency explicit.

## Step 3.3: lock

Monideep reviewed the PRD and locked it. The PRD status is locked (2026-07-22), and Plan.md marks Phase 3 complete. The PRD is now the reference for Phase 4 (the tech spec), and does not reopen except under the Phase 7 hard-stop exception. Phase 3 is complete.
