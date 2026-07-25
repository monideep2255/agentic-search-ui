# Phase 4 session, July 24

Phase 4 of System 3 planning opens here: the technical specification and the strategic memo. This first session did not run a numbered Step 4.0 to 4.4 task. It opened the phase and settled three process questions that sat between Phase 3 (PRD locked) and the start of Step 4.0. This file is the project record and a personal learning log.

## Table of contents

- [Where we started](#where-we-started)
- [MCP servers evaluated and declined](#mcp-servers-evaluated-and-declined)
- [Testing strategy: when](#testing-strategy-when)
- [Doc-review cadence and the new-intake sweep](#doc-review-cadence-and-the-new-intake-sweep)
- [Phase 4 opened](#phase-4-opened)

## Where we started

Phase 3 ended with the PRD locked (2026-07-22). Before starting Step 4.0 (the API deep dive), a few process questions came up that were worth settling so the build phase does not churn. A background security scan (the claude-security whole-repository scan, medium effort) ran during the session and is unrelated to the planning work here.

## MCP servers evaluated and declined

Reviewed three third-party NCBI and bioinformatics MCP servers found on mcpservers.org: QuentinCody/entrez-mcp-server, vitorpavinato/ncbi-mcp-server, and AiAgentKarl/bioinformatics-mcp-server. Declined all three as inbound runtime dependencies. They reaffirm Decision 24 and the 2026-07-22 sequencing decision: the agent reaches NCBI through direct Python tool functions, and MCP is an outbound delivery format only.

Reasons captured:

- Supply-chain risk: single-maintainer projects, unpinned uvx or npx execution surfaces (per supply-chain-security).
- Token cost and hallucination risk: off-the-shelf servers return unbounded API payloads, where our tool pattern truncates and shapes results (Decision 24, system-design-patterns rule 7).
- Control: adopting them hands away the schema, validation, cost-cap, and truncation discipline the direct-tool pattern exists to keep.

Kept as reference only: vitorpavinato's tool decomposition (search_pubmed, get_article_details, get_related_articles) is a clean template for the ncbi_efetch and PubMed tool specs in Step 4.1.

## Testing strategy: when

Confirmed the testing strategy is a Phase 4 deliverable, not earlier. It is a named section of the Step 4.1 tech-spec outline (unit, integration, eval harness, golden dataset). Code test suites are designed in Phase 4 and built in Phase 6, since no application code exists yet. The eval side is more mature: the Evaluation playbook already holds the offline eval gate and acceptance criteria, and the 50-query golden dataset is the Phase 4 expansion of the moat-seven eval set.

## Doc-review cadence and the new-intake sweep

Settled the going-forward doc-review cadence so the build phase does not churn on the PRD, tech spec, and memo:

- Phase 4: author and lock the tech spec and memo (the PRD is already locked).
- During the build: the three docs are frozen.
- Step 6.2: the single reconciliation window. Fold in prototype learnings, the accumulated new-intake, and LEARNINGS.md, then re-lock at v1.
- Post-v1 (Phase 7): the iteration cycle for v2.
- Exception: a fundamental flaw (security or a wrong architectural assumption) pauses the build.
- The evaluation playbook is exempt: it stays a living doc.

The new-intake folder is a drained staging inbox. Its 43-note backlog was triaged out on 2026-07-21 in Step 1.11. The one note that has landed since, the personal-space autonomous build harness, was already applied to bossman-mode and self-eval-loop (the two most recent commits). To keep the folder from needing manual watching, the new-intake review is now pinned to a scheduled sweep at Step 6.2. Plan.md Step 6.2 and the "How new information gets incorporated" section were edited to record it.

## Phase 4 opened

Phase 4 is now open. Next is Step 4.0, the NCBI and enrichment API current-state deep dive, which produces the per-API capability sheet that the Step 4.1 tool specifications are written against. The Phase 4 continuation prompt (`requirements/phase_4/Continuation_prompt.md`) carries the resume state.
