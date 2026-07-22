# Phase 2 continuation prompt

Use this to resume Phase 2 (competency questions and the evaluation playbook) in a new chat session. Living document, updated as Phase 2 progresses.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 2 of System 3 planning: competency questions and the evaluation playbook. Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap; Phase 2 is Steps 2.1 to 2.5.
2. `requirements/phase_1/Phase_1_synthesis.md` - the primary input: all Phase 1 decisions organized by topic.
3. `requirements/phase_2/Session_July_22.md` - the Phase 2 discussion record so far.
4. `DECISIONS.md` - all decisions (83 as of 2026-07-22).
5. `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/01_Consolidated_findings.md` - the collected 65-CQ set being refined.
6. `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/02_Tier1_eval_spec.md` - the 8-point rubric for Step 2.4.

Phase 1 is complete. Phase 2 produces `requirements/Evaluation_playbook.md`.

Rules:
- Append to `requirements/phase_2/Session_July_22.md` (or a new dated session file on a different day). Never delete existing content.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- Maintain the meeting-note cadence in `requirements/meetings/`.
- At a sub-phase or phase boundary, run `/phase-checkpoint` to sync all planning docs (decisions, session, meeting note, continuation prompt, synthesis, Plan status).
- This documentation is both the project record and a personal learning log. Capture discussion, rationale, and diagrams.
- We discuss before we draft. Ask one question at a time.

---

## Progress tracker

| Step | Status | Notes |
|------|--------|-------|
| 2.1 review existing CQ set | COMPLETE | 65 CQs reviewed; gaps and capability flags surfaced |
| 2.2 real user data | FOLDED IN | The consolidated findings are the collected user data; no separate scrape |
| 2.3 refine the CQ set | CORE DONE | Bar locked; 10 Tier 1 scored; v1 must-pass set locked at 7. Remaining: coverage metric, Tier 2/3 disposition |
| 2.4 offline eval gate | NOT STARTED | Confirm or update the 8-point rubric; wire in eval-harness metrics |
| 2.5 feedback loop | NOT STARTED | Design the interaction-to-CQ online loop |

## Decisions so far (Phase 2)

1. Moat test is the primary selection and tiering bar, above persona coverage and raw usage frequency.
2. Moat test is a structured bar: provenance and deterministic are pass/fail gates; the one design-time ranking dimension is cannot-just-Google, scored by an external test (run the question against a general tool; if it cannot produce the cited answer, it passes); learn-from-the-system and loop-human-behavior both defer to the Step 2.5 online loop; cross-database span was rejected because it imposes our bias. Deterministic means reproducible and verifiable given the data state at query time. Tier mapping among gate-passers: cannot-just-Google high = Tier 1, partial = Tier 2, none = handled but outside the moat set.
3. The PoC moat CQ set is a deliberately small, cross-database-biased subset that proves the wedge, separate from the full set of queries the system handles. Simple single-source fetches are handled but sit outside the moat eval set.
4. Assemble-not-classify: moat CQs surface cited evidence and never render a clinical verdict (the Phase 1 forbidden-outputs boundary at the CQ level). Q1 and Q2 reworded to evidence-assembly.
5. No compute tools in v1: the three execution-heavy questions (Q2 VCF, Q7 SRA similarity, Q9 BLAST) defer to a fast-follow set, added later with pinned fixtures.
6. v1 must-pass moat set locked at seven: Q1 (reworded), Q3, Q4, Q5, Q6, Q8, Q10. Covers all three wedge types and personas 1, 2, 3, 4, 6, 8, 10, 11. Q1 carries a coordinate-range feasibility flag; drops to six if infeasible.
7. Refine CQs now; the API and tool study is Phase 4 (with a mandated current-state API deep dive, the new Step 4.0); Phase 2 folds in only a lightweight feasibility check.
8. No local MCP servers for inbound data; the agent uses direct Python tools; MCP is an outbound delivery format only.

## Parked threads

- A/B test selected questions across model combinations (orchestrator plus planner), randomly assigned, comparing outputs. The online complement to the offline model-bench. Name it in the evaluation playbook's model-selection section; design the mechanism in the Phase 4 tech spec.

## Next up

1. Verify Q1's coordinate-range feasibility (dbVar and ClinVar by region, segmental-duplication overlap). If infeasible, Q1 drops to fast-follow and the cap is six.
2. Define the coverage metric (concepts and predicates exercised versus available) and dispose of the Tier 2 and Tier 3 set under the new bar.
3. Step 2.4: the offline eval gate, the 8-point rubric from `02_Tier1_eval_spec.md`, wired to the eval-harness metrics (pass@k, pass^k, pass/fail/abstain).
4. Step 2.5: the online feedback-loop design.
5. Assemble the evaluation playbook, the Phase 2 deliverable.
