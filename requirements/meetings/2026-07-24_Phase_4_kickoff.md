# Phase 4 kickoff: 2026-07-24

Date: 2026-07-24
Attendees: Monideep, Claude (agent teammate)
Type: Phase 4 opening and inter-phase process decisions
Context: Phase 3 closed with the PRD locked. This session opened Phase 4 and settled process questions before Step 4.0. No numbered Step 4.0 to 4.4 work ran.

## What we covered

- MCP servers:
    - Reviewed three third-party NCBI and bioinformatics MCP servers (QuentinCody/entrez, vitorpavinato/ncbi, AiAgentKarl/bioinformatics).
    - Declined all three as inbound dependencies; reaffirms Decision 24 (direct Python tools, MCP outbound-only).
    - Kept as reference only for the Phase 4 tool specs.
- Testing strategy timing:
    - Confirmed it is a Phase 4 deliverable (Step 4.1 tech-spec section: unit, integration, eval harness, golden dataset).
    - Code test suites built in Phase 6; the eval side is already partly designed in the Evaluation playbook.
- Doc-review cadence:
    - Locked the build-phase freeze: the PRD, tech spec, and memo freeze after Phase 4, update only at the Step 6.2 reconciliation, then re-lock at v1.
    - New-intake parked during the build and swept once at Step 6.2, not continuously.
    - Evaluation playbook stays a living doc; the fundamental-flaw exception still pauses the build.
    - Edited Plan.md Step 6.2 and the "How new information gets incorporated" section.
- Phase 4 opened; next is Step 4.0 (the API deep dive).

## Decisions (logged in DECISIONS.md, 2026-07-24, now 94 rows)

- Build-phase doc-review cadence: freeze the three docs after Phase 4, reconcile once at Step 6.2, sweep new-intake there rather than continuously.
- Declined three third-party NCBI MCP servers as inbound dependencies; reference only.

## Action items

1. Next: Phase 4 Step 4.0, the NCBI and enrichment API current-state deep dive (produces the per-API capability sheet).
2. Claude: run /ship to commit and push today's planning work (docs-sync reconciles the CLAUDE.md phase status and decision count).
3. Reminder: the background security scan report lands separately; review its findings when it completes.
