# Phase 2 continuation prompt

> Superseded. Phase 2 and Phase 3 are complete and the PRD is locked. The current resume pointer is `requirements/phase_3/Continuation_prompt.md` (Phase 4 is next). This file is kept as the Phase 2 record.

Use this to resume Phase 2 (competency questions and the evaluation playbook) in a new chat session. Living document, updated as Phase 2 progresses.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 2 of System 3 planning: competency questions and the evaluation playbook. Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap; Phase 2 is Steps 2.1 to 2.5.
2. `requirements/phase_1/Phase_1_synthesis.md` - the primary input: all Phase 1 decisions organized by topic.
3. `requirements/phase_2/Session_July_22.md` - the Phase 2 discussion record so far.
4. `DECISIONS.md` - all decisions (90 as of 2026-07-22).
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
| 2.3 refine the CQ set | COMPLETE | Bar locked; v1 must-pass set locked at 7 (Q1 held after the feasibility check); coverage metric defined (diagnostic); Tier 2/3 disposition rule locked |
| 2.4 offline eval gate | COMPLETE | 8-point rubric wired to eval-harness (rubric grades run to pass/fail/abstain; pass@k and pass^k aggregate); three hard-fails; two-level targets; pinned fixtures |
| 2.5 feedback loop | COMPLETE | Five-stage loop; v1 = capture + manual review + hand-promotion, mining deferred; Postgres system-of-record; LLM-judge upstream of the human gate |
| Deliverable | COMPLETE | `requirements/Evaluation_playbook.md` assembled and graded 5/5 |

## Decisions so far (Phase 2)

1. Moat test is the primary selection and tiering bar, above persona coverage and raw usage frequency.
2. Moat test is a structured bar: provenance and deterministic are pass/fail gates; the one design-time ranking dimension is cannot-just-Google, scored by an external test (run the question against a general tool; if it cannot produce the cited answer, it passes); learn-from-the-system and loop-human-behavior both defer to the Step 2.5 online loop; cross-database span was rejected because it imposes our bias. Deterministic means reproducible and verifiable given the data state at query time. Tier mapping among gate-passers: cannot-just-Google high = Tier 1, partial = Tier 2, none = handled but outside the moat set.
3. The PoC moat CQ set is a deliberately small, cross-database-biased subset that proves the wedge, separate from the full set of queries the system handles. Simple single-source fetches are handled but sit outside the moat eval set.
4. Assemble-not-classify: moat CQs surface cited evidence and never render a clinical verdict (the Phase 1 forbidden-outputs boundary at the CQ level). Q1 and Q2 reworded to evidence-assembly.
5. No compute tools in v1: the three execution-heavy questions (Q2 VCF, Q7 SRA similarity, Q9 BLAST) defer to a fast-follow set, added later with pinned fixtures.
6. v1 must-pass moat set locked at seven: Q1 (reworded), Q3, Q4, Q5, Q6, Q8, Q10. Covers all three wedge types and personas 1, 2, 3, 4, 6, 8, 10, 11. Q1 carries a coordinate-range feasibility flag; drops to six if infeasible.
7. Refine CQs now; the API and tool study is Phase 4 (with a mandated current-state API deep dive, the new Step 4.0); Phase 2 folds in only a lightweight feasibility check.
8. No local MCP servers for inbound data; the agent uses direct Python tools; MCP is an outbound delivery format only.
9. Q1 coordinate-range feasibility resolved: Q1 holds at seven. The CNV region query is feasible via Layer 2 (dbVar, ClinVar with an explicit GRCh37 position field so no liftover, overlapping genes, OMIM by gene, and a Variation Viewer citation link). Segmental duplications are not in the NCBI three-layer API set (a UCSC genomicSuperDups track) and move to fast-follow with a later UCSC integration. Two items flagged for Phase 4 Step 4.0: interval-overlap semantics for large SVs, and the UCSC source design. Layer 1 has no coordinate node properties, so Q1 is API-driven.
10. Coverage metric (PoC, diagnostic only, never a gate): denominator is the graph's enumerable schema (10 concepts after dropping NamedThing, 14 predicates); numerator is the distinct concepts and predicates the CQ set exercises (hand-mapped now, dynamically instrumented later); reports two ratios plus a secondary Layer 2 API-reach checklist. First pass on the seven: about 50 percent concept coverage, about 21 percent predicate coverage. Low graph coverage is by design (the set is Layer 2 heavy), so the metric guides set growth, not v1 gating.
11. Tier 2/3 disposition rule locked, full per-question re-score deferred to set-expansion time: old Tier 2 is the expansion candidate pool; old Tier 3 splits into fast-follow (compute tools), reframe-or-out (clinical verdict), and handled-but-outside-the-moat-set (single-source fetches). Framing that settles it: the seven are the eval gate, not the menu (the system is a general agent, cite-or-refuse protects the untested long tail at runtime, the feedback loop grows the eval set), so the 55 are an expansion pool, not discards.
12. Offline eval gate (2.4): the 8-point rubric grades each run to pass, fail, or abstain; eval-harness pass@k and pass^k aggregate across k samples. Three hard-fails checked every run (provenance = 0, safety verdict on a clinical question, missing assembly/version on a coordinate/sequence question). Two-level targets: hard-fails pass^k = 100%, quality pass@3 floor and pass^3 >= 90%. Determinism via pinned fixtures with a freshness window. Domain sign-off for the golden fixtures flagged for Phase 4.
13. Online feedback loop (2.5): five stages (capture, mine and cluster, human-gated review, trigger rule, promote to a few-shot routing example plus a new eval case). v1 ships stages 1, 3, and 5 with a human in the loop (capture, manual review, hand-promotion); automated mining (stage 2) deferred to a fast-follow.
14. Feedback-loop storage and LLM-judge (2.5): PostgreSQL is the system-of-record (interactions, cq_candidates tables), LangSmith holds traces (linked by trace_id), PostHog holds behavioral analytics. The LLM-judge is always upstream of the human; the human is the terminal promotion gate.
15. Moat-bar refinement (2.3): renamed "cannot just Google" to "no general-tool equivalent"; the test runs against a panel of the strongest general tools (a frontier LLM, Perplexity, plain search) and passes only if none produces the correct answer with verifiable citations. Scored on grounding, not fluency.

## Parked threads

- A/B test selected questions across model combinations (orchestrator plus planner), randomly assigned, comparing outputs. The online complement to the offline model-bench. Name it in the evaluation playbook's model-selection section; design the mechanism in the Phase 4 tech spec.

## Next up

Phase 2 is complete. All five steps (2.1 to 2.5) are decided and logged, and the deliverable `requirements/Evaluation_playbook.md` is assembled and graded (5 of 5). Next is Phase 3, the PRD (see Plan.md Phase 3):

1. Run `/ship` to commit and push this session's planning documents.
2. Step 3.1: outline the PRD from the template in `reference/personal-os-work/NIH/Agentic-Search/Specs/`, adapted to scope. The PRD is outcome-focused; the evaluation playbook supplies the competency questions as acceptance criteria and the personas.
3. Step 3.2: draft the PRD from all Phase 1 and Phase 2 outputs.
4. Step 3.3: lock the PRD.
5. Create `requirements/phase_3/Continuation_prompt.md` when Phase 3 work begins.
