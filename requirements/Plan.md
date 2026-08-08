# System 3 planning roadmap

From background research to working product. This document defines every step between where we are now (raw research collected) and where we need to be (a running search agent + UI backed by a solid PRD and technical specification).

Kick-off: 2026-05-06. Last updated: 2026-08-07.

## Status at a glance

| Phase | Status |
|-------|--------|
| Phase 0: foundation | Complete (2026-05-06) |
| Phase 1: source review and architecture decisions | Complete, all 13 steps (2026-07-21) |
| Phase 2: competency questions and evaluation playbook | Complete, all 5 steps (2026-07-22) |
| Phase 3: PRD | Complete, PRD locked (2026-07-22) |
| Phase 4: technical specification | Complete, all steps 4.0 to 4.4 done (2026-07-25) |
| Phase 5: system and tooling updates | Complete, all steps 5.1 to 5.4 (2026-07-26) |
| Phase 6: build (bossman execution) | In progress. Step 6.1 (prototype) COMPLETE, all six build phases merged. Step 6.3 (build v1) underway. Build phases 1.0 to 3.0 merged as PRs #5, #6, #9, #12, #15, #18, #19. Build phase 3.1 (`ncbi_efetch`, the first Layer 2 tool) merged as PR #22, with the premise restated and the answer-path half (Act-step wiring, Layer 2 citation, trust gate) carried to T-3.1-28. It merged without the adversarial pass over its own fix round; that debt was fully closed via three independent re-review rounds and a fix round, merged as PR #23. 40 of 42 numbered findings closed, two left open on genuine product decisions (F-3.1-41, F-3.1-42). Next up, in this order: F-2.1-C15, then open build phase 3.2, `ncbi_dbsnp`. Step 6.2 moved to run after the 3.x tool phases, and its security scan is paused indefinitely on cost |
| Phase 7: iteration and new information | Not started |

Decisions logged: 226 (DECISIONS.md). Deliverables produced: the Phase 1 synthesis, the evaluation playbook, the PRD (locked), the verified API capability sheet, the technical specification (locked), and the strategic memo. The dated change log is in Revision history at the end of this document.

## Table of contents

- [Status at a glance](#status-at-a-glance)
- [Goal](#goal)
- [How we work](#how-we-work)
- [Phase 0: foundation (complete)](#phase-0-foundation-complete)
- [Phase 1: source review and architecture decisions](#phase-1-source-review-and-architecture-decisions)
- [Phase 2: competency questions and user research](#phase-2-competency-questions-and-user-research)
- [Phase 3: PRD creation](#phase-3-prd-creation)
- [Phase 4: technical specification](#phase-4-technical-specification)
- [Phase 5: system and tooling updates](#phase-5-system-and-tooling-updates)
- [Phase 6: build (bossman execution)](#phase-6-build-bossman-execution)
- [Phase 7: iteration and new information](#phase-7-iteration-and-new-information)
- [Documents we will create](#documents-we-will-create)
- [How new information gets incorporated](#how-new-information-gets-incorporated)
- [Revision history](#revision-history)

---

## Goal

Build System 3: an ever-evolving UI + agent system where a user asks a question in plain English, the agent queries across three data layers (knowledge graph, NCBI APIs, enrichment APIs) through hard guardrails, and returns a cited answer. Over time, the system collects user interactions, generates competency questions from them, and feeds those back into the orchestrator to improve query routing.

This is not just building a product. This is two of us (human + agent) working as a team in a new format, using agent tools as teammates, with me as orchestrator. The process of building is as important as the output.

---

## How we work

We are a team. Not a vending machine. Every phase follows this pattern:

1. Discuss: debate the inputs, question assumptions, surface blind spots
2. Decide: make choices together, log them in DECISIONS.md
3. Build: execute with agent teams (bossman-mode) once decisions are locked
4. Review: check what we built against what we agreed on

My tasks (Monideep):

- Competency question research
- Confluence/Jira data scraping
- Stakeholder input
- Architecture sign-off
- PR reviews
- New reference material collection (KGC, Nodes AI, red teaming)

Agent tasks (Claude):

- Document analysis
- Technical drafting
- Code implementation
- Testing
- Sub-agent coordination
- Execution via bossman-mode

We discuss before we draft. We draft before we build. We build one phase at a time.

---

## Phase 0: foundation (complete)

Status: DONE (2026-05-06)

What we did:
- Assessed System 3 readiness across all dimensions
- Discussed the high-level vision: query system, guardrails, three-layer data access, competency question feedback loop
- Agreed on starting with few-shot routing (not classification layer, not fine-tuned model) for competency question-based orchestrator improvement
- Collected all background material into a single reference index

Output: `requirements/context/Background_requirements.md` (24 sources indexed, all paths verified)

---

## Phase 1: source review and architecture decisions

Status: COMPLETE (all 13 steps done as of 2026-07-21)

Goal: go through every source in `Background_requirements.md`, debate what to use, what to skip, and what needs adaptation. Lock the architecture decisions before writing the PRD.

### Phase 1 output structure

Phase 1 produces three types of output that together feed Phase 2:

1. Session notes (`requirements/phase_1/Session_*.md`): chronological record of what we discussed, debated, and why. One file per session. These are the raw record and also serve as a personal learning log.
2. Decision log (`DECISIONS.md`): every confirmed choice in a flat, searchable table with rationale. Append-only.
3. Phase 1 synthesis document (`requirements/phase_1/Phase_1_synthesis.md`): written after all Phase 1 steps complete. Organizes all decisions and discussion outcomes by topic into a single narrative. This becomes the primary input for Phase 2 (competency questions) and Phase 3 (PRD).

The synthesis document fills the gap between chronological session notes and a flat decision table.

- Session notes answer: "what did we discuss and when?"
- DECISIONS.md answers: "what did we choose?"
- The synthesis answers: "what does it all mean together, organized by topic, ready for downstream phases?"

### Step 1.1: review strategic foundation (3 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| Innovation proposal | Which scope elements apply to our build vs. the official NCBI track? | Discuss together |
| NCBI strategic alignment (FY26, Gold Standard, AI Action Plan) | Which constraints are real requirements vs. nice-to-have alignment? | Discuss together |
| Two-track plan + personal build plan | Confirm: we are building Track 1 (personal, 2 months, ~$100). What from Track 2 do we borrow? | Monideep decides |

### Step 1.2: review architecture design (4 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| System 3 architecture brainstorming | Lock the agent loop (5 steps), multi-tier LLM routing, deployment modes. Any changes? | Discuss together |
| Three-layer data architecture | Confirm layer boundaries. Any new data sources to add? | Discuss together |
| Initial brainstorming (system-3-brainstorming/) | Compare early thinking to current. What evolved? What got dropped? | Claude reviews, flags differences |
| Architecture QA | Any unanswered questions remaining? | Claude reviews, surfaces open items |

### Step 1.3: review reference implementations (2 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| NCBI KG repo (ncbi-kg branch) | Which patterns to adopt directly (NL-to-Cypher pipeline, 4-layer guardrails, React components)? Which to adapt? | Claude analyzes, Monideep approves |
| Contractor 8-layer architecture | Typed query-plan IR: adopt or simplify? GraphQL as public surface: adopt or stay REST? Context-pack builder: adopt fully? | Discuss together |

### Step 1.4: review data handoff (2 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| System 1+2 data engineering repo | Confirm node types, edge predicates, CURIE conventions, connection pattern. Any schema changes needed? | Claude verifies against live graph |
| V1 shoring-up recommendations | Which fixes are blockers for System 3 vs. nice-to-have? | Discuss together |

### Step 1.5: review agent and harness research (22 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| All 22 docs in Reference/system/ | Extract the 5-10 most actionable ideas for System 3. Skip what is theoretical-only. | Claude reviews all, presents top picks |

### Step 1.6: review user psychology and product design (4 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| Hook model, adoption gap, build-to-learn, NLM lessons | Which psychological design principles make it into the PRD as requirements? | Discuss together |

### Step 1.7: review contractor documents (7 sources) - COMPLETE (2026-07-21)

| Source | What to decide | Owner |
| --- | --- | --- |
| NFR baseline (10 categories) | Which NFRs apply to our POC? Tag each as must-have or defer. | Discuss together |
| NLQ approach (6 ranked options) | DECIDED (2026-07-21): confidence-layered hybrid. POC leads with schema-aware Cypher generation plus a validate-and-repair pipeline; verified templates layered on for the ~10 tier-1 must-pass CQs while hardening to v1 (not rigid rank-2 templates). Query language sealed inside the tool for backend agnosticism | Done, see DECISIONS.md |
| Meeting decisions (D1-D5) | Federation scope: how much for v1? Template vs. NL: confirm NL from day 1. | Monideep decides |
| Contractor's latest documents | What changed since the last handoff? Which updates affect our architecture or the PRD? | Discuss together |
| The evaluation playbook | Which outcome definitions and evaluation criteria become requirements? Which stakeholders does each outcome serve? | Discuss together |

### Step 1.8: review tools and infrastructure - COMPLETE (2026-07-21)

| Source | What to decide | Owner |
| --- | --- | --- |
| Tools list (section 10 of background) | DECIDED (2026-07-21): Railway (hosting), PostHog (analytics), LangSmith over Arize (tracing), self-maintained in-repo tracker over Linear, REST+SSE+GraphQL (Decision 4). Build on our own stack first, migrate to NCBI/OCCS after the PoC | Done, see DECISIONS.md |

### Step 1.9: resolve open questions - COMPLETE (2026-07-21)

The 10 open questions from section 12 of `Background_requirements.md` must each get a decision or an explicit "defer to tech spec" tag.

### Step 1.10: review cross-cutting concerns - COMPLETE (2026-07-21)

Topics that cut across multiple sources and need explicit architecture decisions before the PRD.

| Concern | What to decide | Owner |
| --- | --- | --- |
| Security and threat model | Prompt injection defense, forbidden query types, PII handling, audit logging. Use "Agents of Chaos" red-teaming findings (section 8 of Background_requirements.md) as the threat catalog. What does the NCBI KG reference implementation do? What does the NIH context require? | Discuss together |
| Data freshness and conflict resolution | Graph is a periodic snapshot; APIs are live. When they disagree, which wins? What staleness is acceptable? | Discuss together |
| Rate limiting strategy | NCBI E-utilities at 100 req/sec (upgraded), Variation Services at 1 req/sec (separate). With concurrent users, who gets throttled? Queue? Prioritize? Fail fast? | Discuss together |
| UI patterns and user experience | Review reference implementation React components. What interaction patterns to adopt (streaming, citations, error states)? What to redesign? Parked (2026-07-21): stream the agent's Think and Plan reasoning in real time with a stop button, so the user can abort a query heading the wrong way. Extends Decision 11 (streaming plus stop-button); the open sub-decision is how much to surface, raw chain-of-thought versus a curated plan-step narrative. Also (parked 2026-07-21): the named scientist persona (Step 1.9) surfaces here, streamed to the user; keep it subtle and serious, not a gimmick, so it does not undercut the provenance-forward positioning. | Claude reviews, Monideep approves |
| Accessibility and compliance | Section 508 is not optional for NIH-adjacent work. What level of compliance for v1? | Discuss together |

### Step 1.11: review new intake research (30 sources) - COMPLETE (2026-07-21)

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/new-intake/` (harnesses, model routing, KV cache, OpenRouter fusion, prototype to production).

| What to decide | Owner |
| --- | --- |
| Orchestration style: strong model plans and thinks, cheaper models fetch where the task is bounded. Which tiers, which boundaries? | Discuss together |
| Model providers: OpenRouter and open-source models, with cost as a first-class constraint. Which models per tier? | Discuss together |
| model-bench as the model-selection method (blind generation, judge plus human scoring, open and closed leaderboard). Adopt it for tier selection? | Discuss together |
| Caching: KV cache and prompt caching in the architecture. Where does it apply, what does it save? | Discuss together |
| Value is in how you wrap the model (UX, retrieval, memory, tools). Which wrapping investments become requirements? | Discuss together |
| Harness and prototype-to-production patterns: which become architecture requirements, which stay reference only? | Claude reviews all, presents top picks |

### Step 1.12: review conference learnings (3 sources) - COMPLETE (2026-07-21)

Source: `reference/personal-os-work/NIH/Conference-notes/` (ISMB-2026, KGC-2026, Nodes-AI).

| What to decide | Owner |
| --- | --- |
| Which learnings from each conference must feed the PRD? Which are reference only for v2? | Claude reviews, Monideep confirms |

### Step 1.13: review LLM legal and compliance obligations - COMPLETE (2026-07-21)

Source: `requirements/context/ncbi_ai_models_control_first_summary.md` (control-first hosting analysis, extended with a legal and compliance section). The strongest open coding models today are Chinese-origin (GLM, MiniMax, DeepSeek, Kimi, Qwen), which is exactly what US federal policy is moving to restrict. Legal obligations are a separate gate from the control-first ranking: a hosting path can be highly controlled and still involve a model or provider that federal policy bars.

| What to decide | Owner |
| --- | --- |
| Country-of-origin restrictions: which models are usable for the Track 1 prototype, and which are barred from the production track? DeepSeek is already blocked at NASA, the Pentagon, Commerce, and the Navy; the No Adversarial AI Act would extend this. | Discuss together |
| Model licensing: permissive (MIT, Apache 2.0) versus use-restricted versus research-only versus capped commercial (Llama 700M MAU). Which license classes do we allow, and how do we track obligations that flow into fine-tunes? | Discuss together |
| Federal authorization: FedRAMP, FISMA, ATO, OMB M-25-21 and M-26-04. Which bind the production path, and what do we design the prototype toward so it does not build on a barred model or provider? | Discuss together |
| Data-handling contracts: HIPAA and BAA, zero data retention, SOC 2 Type II, data residency. Which are must-haves for v1 and which defer? | Discuss together |
| Track 1 versus production line: decide explicitly which legal constraints apply to the personal prototype now and which defer to the official NCBI track. | Monideep decides |

This composes with Step 1.10 (security and compliance cross-cutting concerns) and Step 1.11 (model routing and providers). Keep the legal decisions here so model choice and hosting are not locked before their legal constraints are cleared.

Phase 1 output: session notes, decision log (DECISIONS.md), and Phase 1 synthesis document (see output structure above).

---

## Phase 2: competency questions and user research

Status: COMPLETE (all five steps 2.1 to 2.5 done as of 2026-07-22; deliverable requirements/Evaluation_playbook.md, graded 5/5)

Goal: finalize the competency questions that define what System 3 must answer. These feed directly into the PRD as acceptance criteria and into the orchestrator as routing intelligence.

Prerequisites: Phase 1 synthesis document complete (`requirements/phase_1/Phase_1_synthesis.md`). The synthesis organizes all architecture decisions, tool mappings, and design patterns by topic, providing the foundation for evaluating which competency questions the system can answer and how.

### Step 2.1: review existing competency questions

Source: `Reference/system-3-brainstorming/01_Consolidated_findings.md` (65 questions, 11 personas, 3 tiers)

Task (Claude): present the current CQ set with the tiering and persona coverage. Flag any gaps.
Task (Monideep): review and confirm. Are these the right questions?

### Step 2.2: scrape real user data (Monideep's task)

Task (Monideep): scrape Confluence, Jira, and app logs via MCP to identify what people actually search for at NCBI. Data never lies. Compare to the CQ set.

Deliverable: raw data dump of real search patterns, categorized by intent type.

### Step 2.3: refine competency questions

Combine the existing CQ set with real user data. Identify:
- Questions users ask that the CQ set misses
- CQ questions that nobody actually asks (remove or deprioritize)
- New tier 1 candidates from real usage

Task (Discuss together): finalize the CQ set. Lock the tiers:

- Tier 1: must-answer for v1
- Tier 2: should-answer
- Tier 3: stretch/future

Decision to make here (discuss): cap the v1 competency-question set to a small, testable number even though we have far more candidates. Start small, prove the loop, then expand. Lock the cap before finalizing tiers.

Discussion topic (discuss): what makes a competency question worth including, the moat test. Beyond persona coverage and real-usage frequency, discuss a sharper bar for selecting and tiering competency questions: prioritize questions a user cannot answer well with a general search engine or a general AI tool. Compare and contrast each candidate question against that bar along five dimensions:

1. Cannot just Google: the answer needs synthesis across the knowledge graph and the NCBI or enrichment APIs, not a single web result. If a general search engine or AI tool already answers it directly, it is weak differentiation for System 3.
2. Is deterministic: the same question returns the same verifiable answer every time, not a plausible generation that varies run to run.
3. Provenance: every claim links back to its source record, per the citations-non-negotiable rule. A question whose answer cannot be cited fails the bar.
4. Learn from the system: the answer surfaces something the system is uniquely positioned to show, such as cross-database relationships or structured evidence, so the user gets insight a generic summary cannot give. To discuss: does this mean the user learns from the system, the system learns from usage, or both?
5. Loop human behavior: the question, and how users follow up on it, feeds the interaction-to-competency-question loop (Step 2.5), so real human behavior sharpens the CQ set over time.

Task (Discuss together): decide whether these five become explicit selection or tiering criteria for the CQ set, how to weigh them against persona coverage and real-usage frequency, and test the idea by scoring a few concrete tier 1 candidates against all five.

### Step 2.4: define the offline evaluation gate

Confirm or update the 8-point scoring rubric from `02_Tier1_eval_spec.md`. Does the rubric match our architecture?

The competency-question set is the offline eval set. Score the agent against it with the `eval-harness` skill (pass@k, pass^k, and the pass/fail/abstain outcome model). This is the baseline gate: it runs before any answer-generation feature ships. model-bench sits alongside for model selection (which model or tier is good enough for a step, at what cost), a separate target from answer quality.

### Step 2.5: design the feedback loop mechanism

The vision says user interactions become competency questions that improve routing. Define the mechanism:
- How are user interactions captured and stored?
- Who reviews them: automated, semi-automated, or manual?
- What triggers a new competency question vs. reinforcing an existing one?
- How do new CQs get promoted into the orchestrator's routing?

Task (Discuss together): design the feedback pipeline. This feeds into the tech spec.

This is the online feedback loop, the second half of the evaluation approach. Offline gate first (Step 2.4) for a baseline, online loop second, once the system is live. Design it here, but mark it to discuss and lock before the PRD is finalized.

Phase 2 output: the evaluation playbook, a standalone living document in `requirements/`. It holds:

- The final competency-question set with tiers and personas
- The CQ count cap
- The offline evaluation gate (rubric plus eval-harness metrics)
- The model-selection method (model-bench)
- The online feedback-loop design

The tech spec references this playbook rather than restating it. It is updated as the evaluation approach evolves.

---

## Phase 3: PRD creation

Status: COMPLETE (PRD locked 2026-07-22; deliverable requirements/PRD.md)

Goal: write the PRD. Single source of truth for what System 3 does, for whom, and how we measure success.

Prerequisites: Phase 1 decisions locked. Phase 2 competency questions finalized.

### Step 3.1: outline the PRD

Use the template from `reference/personal-os-work/NIH/Agentic-Search/Specs/` as starting structure. Adapt to our scope. The PRD is outcome-focused: every section ties back to an outcome a named stakeholder needs, not to features for their own sake.

Sections (expected):
- Problem statement
- Outcomes and stakeholders (the outcome each user segment needs, and the named stakeholders each serves, e.g. the evaluation stakeholder)
- Users and personas (from CQ analysis)
- Core user flows
- UI experience (end-to-end user flow, error states, streaming UX, citation interaction, loading/empty states, what happens when guardrails fire)
- Cost control UX (what the user sees when caps are hit, usage visibility)
- Edge cases and failure states (empty results, partial-layer failures, ambiguous queries, guardrail rejections, timeouts)
- Competency questions as acceptance criteria (tier 1 = must-pass, tier 2 = should-pass)
- Guardrails (hard constraints, non-negotiable)
- Security requirements (threat model, forbidden queries, audit logging)
- Accessibility and compliance (Section 508, NIH requirements)
- Delivery formats (web UI primary, API, MCP server)
- Success metrics (accuracy, latency, cost, adoption)
- Out of scope for v1
- Open items and future iterations

### Step 3.2: draft the PRD

Task (Claude): write the first draft based on all Phase 1 and Phase 2 outputs.
Task (Monideep): review, challenge, refine. Multiple rounds if needed.

### Step 3.3: lock the PRD

Both agree on the PRD. It becomes the reference for everything that follows.

Phase 3 output: `requirements/PRD.md`

---

## Phase 4: technical specification

Status: COMPLETE (opened 2026-07-24, closed 2026-07-25; all steps 4.0 to 4.4 done)

Goal: write the tech spec. Translates PRD requirements into implementation decisions: what to build, how, in what order.

Prerequisites: PRD locked.

### Step 4.0: NCBI and enrichment API current-state deep dive - COMPLETE (2026-07-25)

System 3 depends heavily on the NCBI E-utilities, the Datasets API v2, Variation Services, and the Layer 3 enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov). Before writing the tool specifications, deep dive the current state of each:

- Live endpoints
- Request and response schemas
- The exact fields each competency question needs
- Rate limits
- Auth
- Empty-result and error behavior
- Any drift since the Phase 1 survey in `docs/ncbi/NCBI_databases_and_APIs_reference.md`

Output: a per-API capability sheet that every tool specification in Step 4.1 is written against. This converts the lightweight Phase 2 feasibility notes (the "can we answer this today" checks taken during CQ tiering) into verified API behavior. Discuss and confirm scope before drafting.

Deliverable: `requirements/phase_4/API_capability_sheet.md` (365 lines), live-verified 2026-07-25 against production NCBI and enrichment endpoints, fresh-context graded per self-eval-loop with six grade fixes applied. All three Phase 2 feasibility flags resolved:

- Q1: dbVar interval-overlap via a two-step tool
- Q5: Pathogen Detection via the FTP results tree
- Q6: SRA metadata via two-tier access

The moat cap holds at seven with no demotions. Layer 1 stays trusted from its gate-verified server doc, re-verified live in Phase 6.

### Step 4.1: outline the tech spec - COMPLETE (2026-07-25)

Complete: outlined once the Step 4.1 core-architecture decisions locked. The outline below became `requirements/Technical_specification.md`'s table of contents, expanded to 25 sections through Steps 4.2 and 4.3 as the tool roster grew from five to seven and the delivery surfaces reconciled to six.

Sections (expected):
- System architecture (agent loop, three-layer data, multi-model harness)
- Model orchestration and routing (tiers, strong model plans and cheaper models fetch where bounded, OpenRouter and open-source models, cost per tier)
- Caching (KV cache and prompt caching: where applied, what it saves)
- API design (endpoints, request/response schemas, streaming)
- Data access patterns (Cypher queries, API calls, response caching)
- Data freshness and conflict resolution (staleness thresholds, layer priority when graph and live API disagree)
- Tool specifications (one section per tool: cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup)
- Guardrail implementation (input validation, read-only enforcement, rate limits, cost caps)
- Security implementation (prompt injection defense, PII handling, forbidden query types, audit trail)
- Frontend architecture (React components, state management, streaming UX, error states, citation chips, loading/empty states)
- Edge cases and failure states (empty results, partial-layer failures, ambiguous queries, guardrail rejections, timeouts, retry safety)
- Auth and user data model
- Observability (tracing, analytics, audit logging)
- Cost control (per-query caps, per-user daily caps, system-wide caps, UX when caps are hit)
- Rate limiting and concurrency (per-layer throttling, queue strategy for concurrent users)
- Testing strategy (unit, integration, eval harness, golden dataset)
- Deployment (Railway, environment config, CI/CD)
- Build order (phased, with dependencies)
- Competency question routing (few-shot now, upgrade path later)
- Feedback loop pipeline (interaction capture, CQ generation, routing updates)

The tech spec stays traditional (the build blueprint). It references the evaluation playbook (Phase 2 output) and the `eval-harness` and `dev-standards` skills for the evaluation and production-readiness detail, rather than restating them.

### Step 4.2: draft the tech spec - COMPLETE (2026-07-25)

Task (Claude): write the first draft. Reference the PRD for every requirement, traced back to the outcome it serves.
Task (Monideep): review, challenge, refine.

Complete: drafted to implementation level by a parallel drafting pass across seven sections, each traced to a PRD outcome.

### Step 4.3: lock the tech spec - COMPLETE (2026-07-25)

Both agree. This is the build blueprint.

Complete: reconciled the draft (unified the citation, cost, and error event schemas against the canonical Section 2 and Section 9 definitions, expanded the tool roster from five to seven, and reconciled the delivery surfaces to six against the locked PRD), graded twice fresh-context per self-eval-loop with the schema-consistency failure cleared and verified on the re-grade, then locked. Deliverable: `requirements/Technical_specification.md` (25 sections).

### Step 4.4: draft the strategic memo - COMPLETE (2026-07-25)

Write the 1 to 2 page strategic memo, distilled from the locked PRD and tech spec. It is the executive-facing summary:

- The problem
- The approach
- The outcomes
- The cost
- What v1 delivers

It lets a stakeholder who needs the decision, not the detail, skip the full PRD and tech spec. It gets updated after the prototype runs (see Phase 6).

Complete: drafted as a one-read, six-section memo (what it is, why it exists, how it works, what v1 delivers, how we know it works, where it goes) distilled from the locked PRD and the locked tech spec, for a future collaborator or future-me to hold the whole system in their head at a glance. Deliverable: `requirements/Strategic_memo.md`.

Phase 4 output: `requirements/phase_4/API_capability_sheet.md` (Step 4.0), `requirements/Technical_specification.md` (locked 2026-07-25), and `requirements/Strategic_memo.md` (2026-07-25). Phase 4 is now COMPLETE. These three deliverables serve as the phase synthesis; unlike Phase 1, no separate synthesis document is produced.

---

## Phase 5: system and tooling updates

Status: COMPLETE (opened and closed 2026-07-26, branch phase/5.0-system-tooling-updates; all steps 5.1 to 5.4 done)

Goal: update all project infrastructure to reflect the locked PRD and tech spec. Every skill, agent, rule, and root document should be consistent with what we decided.

### Method: the coverage map

Phase 5 scope was set by evidence rather than by the candidate list this document originally carried. Ten parallel agents extracted every enforceable obligation from the three locked documents and mapped each to the rule or skill that already owns it:

| Source | Obligations extracted | Unowned |
|--------|----------------------|---------|
| Technical_specification.md | 226 | 35 |
| PRD.md | 45 | 8 |
| Evaluation_playbook.md | 32 | 14 |
| Total | 303 | 57 |

Three findings shaped the work:

- The unowned 57 wanted rules and documentation, not skills. Rules load automatically every session; a skill has to be remembered and invoked. A tool-build skill, the strongest of the four candidates below, would have been roughly 70 percent restatement of rules that already load.
- The real defects were wiring, not absence. Skills that existed were never invoked at the moment they were needed, and the two skills that actually execute a build phase created branches named against the convention every rule states.
- One existing skill had drifted badly against a locked document. `eval-harness` never referenced `Evaluation_playbook.md` and was missing 13 of its 17 demands, while being the gate that decides whether an answer-generation feature may ship.

### Step 5.1: update bossman-mode skill - COMPLETE (2026-07-26)

Reviewed `.claude/skills/bossman-mode/SKILL.md` against the tech spec build order. Delivered:

- A live defect fixed: the skill created `feature/description` branches against the `phase/N.M-description` convention that `git-workflow.md`, the `bossman-mode` rule, and tech spec Section 25 all state. `release-workflow` had the same bug. The cascade mattered more than the names: `ship` only offers the MR when the branch matches `phase/*`, so a real run would have created the wrong branch and then silently skipped the pull request.
- Phase definitions now read tech spec Section 25's 26 numbered build phases, with dependency verification before a phase opens.
- Worktree isolation promoted from a post-collision fallback to the default for concurrent file-mutating builders, with read-only agents in the shared checkout and teardown at phase close (per the 2026-07-21 decision).
- A product owner role, per-phase product-owner-required marking, a v1 scope check, and a Playwright gate for UI phases.
- The phase-end chain grew from two skills to six: `verify`, `eval-harness`, `dev-standards`, `release-workflow`, `ship`, `task-tracker`. The first three had never been invoked by anything, despite the spec requiring all three.

### Step 5.2: update or create skills - COMPLETE (2026-07-26)

The four candidates this document originally floated (API development, React component, tool testing, Cypher query development) were written in Phase 0 as open questions before the spec existed. None was built. The coverage map showed the gaps were rules and documentation, not workflows.

Built instead, from the team operating model rather than the product spec:

- `task-tracker`: the in-repo board at `tracker/`, giving bossman-mode's already-specified ledger state machine a file to write to.
- `learnings`: `LEARNINGS.md`, written at the moment of failure and read before every phase, adopted from the personal-os per-skill memory pattern.

Rewritten: `eval-harness`, which had never referenced `Evaluation_playbook.md` and was missing 13 of its 17 demands.

Rules: added `tool-call-budgets` and `v1-scope-boundary`, adopted `prompt-cache-discipline` from personal-os, extended `production-standards` and `system-design-patterns`, narrowed `dependency-tracking` to hooks only.

### Step 5.3: update root documents - COMPLETE (2026-07-26)

19 stale statements corrected, across four files:

- CLAUDE.md: the four-week build order replaced with a pointer to tech spec Section 25, the tool roster corrected from five to seven, and three documented slash commands fixed that did not match their skills' names and would not have resolved.
- README.md: the claim that a build phase was in progress removed, since no application code exists, along with its stale `.claude/` tracking claim. A new link to the planning documents added.
- AGENTS.md: regenerates from CLAUDE.md via the sync hook.
- `.github/pull_request_template.md`: rewritten off the BioLink and KGX gates inherited from the System 1 and 2 template repo.

### Step 5.4: create any new reference docs - COMPLETE (2026-07-26)

`docs/ncbi/Tool_implementation_mechanics.md`: 19 per-tool API traps from tech spec Section 6, six identified during the coverage map and 13 more found reading the section in full. The document holds API facts; the rules hold policy, and it says so explicitly so the boundary survives future edits.

Phase 5 output: all project infrastructure aligned with the PRD and tech spec. Deliverables are `requirements/phase_5/Coverage_map.md` (the 303-obligation gate list), `requirements/phase_5/Phase_5_synthesis.md`, the rewritten harness under `.claude/`, `docs/ncbi/Tool_implementation_mechanics.md`, and `LEARNINGS.md`.

---

## Phase 6: build (bossman execution)

Status: IN PROGRESS. Five build phases done and merged:

- 1.0 (PR #5, 2026-07-27)
- 1.1 (PR #6, 2026-07-28)
- 2.0 (PR #9, 2026-07-28)
- 1.2 (PR #12, 2026-07-28)
- 2.1 (PR #15, 2026-08-01)
- 2.2 (PR #18, 2026-08-03)
- 3.0 (PR #19, 2026-08-04)

Next up, in this order and not the build-order order: re-review build phase 3.1's fix round, then F-2.1-C15 on `fix/c15-generation-bound`, then open build phase 3.2, `ncbi_dbsnp`. Build phase 3.1 (`ncbi_efetch`) merged as PR #22 on 2026-08-05, but merged without the adversarial pass over its own fix round, so twenty-six of its twenty-seven findings sit at `fix-landed` rather than closed. The re-review is what converts them, and it runs before 3.2 opens because 3.2 depends on 3.1. Build phase 3.0 (the full Section 10 guardrail) merged as PR #19 on 2026-08-04. Build phase 2.2 closed 2026-08-03 and completed the Step 6.1 prototype group. Step 6.2 moved on 2026-08-03 to run after the 3.x tool phases, since its own reasoning names 3.x as the code its security scan most exists for, and reconciling the frozen documents after the tool phases is better input than reconciling before them. That scan is separately paused indefinitely on cost, with exposure as the one condition that turns it back on. Continuation prompt at `requirements/phase_6/Continuation_prompt.md`

Goal: build System 3 using bossman-mode. Agent teams execute, I orchestrate.

Prerequisites: PRD locked, tech spec locked, bossman-mode updated.

### Step 6.1: build the prototype

Build a running prototype from the locked PRD and tech spec. Goal: something you can see and feel end to end, one real query through the agent loop with a real answer and citations. Decide here: a Claude-designed look and feel for the UI, or a fast standard setup. Optimize for learning, not polish.

### Step 6.2: reconcile the documents

Position changed 2026-08-03: this step now runs AFTER the 3.x tool phases, not immediately after build phase 2.2. The build continues from 3.0 in Section 25 order and returns here once the tool roster is in.

Why, and the argument is this step's own: the security-scan rationale below explains that scanning per phase would pay repeatedly for the cheap half of the surface "while the genuinely dangerous code (Cypher generation against the live graph in 2.1, LLM calls and the agent loop in 2.0, untrusted NCBI payloads reaching synthesis in 3.x) had not landed yet." That names 3.x as the dangerous code. Scanning before 3.x scans everything except the thing the scan is most for. The reconciliation half moves for the same reason: this step exists to update the frozen documents from what the prototype taught, and the tool phases teach more.

Two conditions, stated rather than implied:

- The whole-repository security scan runs before anything is deployed or before a real user touches the system. Its trigger is exposure, not a position in the sequence.
- The frozen-spec findings stay logged in `tracker/phase_2.2.md` and in this step's own list, so deferral cannot quietly become forgetting.

What made the move safe rather than merely convenient, checked rather than assumed: the blocking risk was agents building against known-wrong documentation, and the two documents an agent actually reads, `.claude/rules/production-examples.md` and `docs/ncbi/Tool_implementation_mechanics.md`, are both already corrected. The one document still carrying the wrong claim is the locked tech spec's Section 6.1, which describes `cypher_query`, a tool already built. Build phase 3.1 reads Section 6.2 instead.

Reconcile the docs with what the build taught us. Five groups of work. The security scan that used to gate Step 6.3 is paused indefinitely, see below.

#### The document reconciliation

- PRD, tech spec, strategic memo: update wherever the prototype changed our thinking. This is the one planned spec update before those three lock at v1 (see the Phase 7 carve-out).
- Evaluation playbook: reconcile here too, but note it differs. It is a living document, not frozen at v1, since the online feedback loop keeps updating the competency-question set and the evaluation approach keeps evolving. Phase 6.2 is one notable update point for it, not its last.
- The input: the running LEARNINGS.md, captured throughout the Phase 6 build. It collects what each build step taught us, so these documents get updated from a captured record rather than memory.
- Log any decision that changed.

#### The new-intake sweep

Folder: `reference/personal-os-work/NIH/Agentic-Search/Reference/new-intake/`.

- This is the one scheduled point during the build to review everything that landed there since Phase 4 locked.
- Triage each note: architecture or product material feeds this reconciliation, harness or process material routes to the skills and rules.
- Then clear the inbox.
- Between Phase 4 lock and here the folder is parked and unreviewed, so no one has to watch it in the meantime.

#### Carried from build phase 2.1: the premise-gate change

Section 25's build order is locked and cannot gain a ticket mid-build, so the change lives in `docs/build/Build_workflow_cadence.md` stage 5 and the `task-tracker` skill until this reconciliation folds it back in.

What needs to land: every phase whose deliverable is model-generated output opens with a premise gate that

- does not mock the model,
- asserts on the meaning of the answer,
- pins ground truth from the live source,
- runs the way production runs,
- states its own coverage,
- and has been seen failing before any other ticket opens.

Evidence: `LEARNINGS.md`'s phase 2.1 retrospective. Decision: `DECISIONS.md`, dated 2026-08-01.

#### Carried from build phase 2.2: the grounding findings

Four items, all recorded with evidence in `tracker/phase_2.2.md`. Two are spec decisions, two are open defects.

| Item | Status | What the reconciliation must decide |
|------|--------|--------------------------------------|
| Section 8.2's matching rule | Exploitable as written | The substring branch answers whether a clause MENTIONS the cited value and has no mechanism for whether it is TRUE about it, so a negation, an invented drug regimen, or a fabricated statistic grounds cleanly against a matched identifier. The prototype closes this with two additions the spec does not describe, `numbers_are_supported` and `claim_introduces_no_new_content`, both of which only ever reject claims Section 8.2 would accept. Either the spec text absorbs them or it states why not |
| F-2.2-05, thousands-separator normalization | Widens the spec | It widens Section 8.2 step 4 beyond its listed operations. It equates two spellings of one number and nothing else, and without it a correct, well-cited answer was refused |
| F-2.2-T-01-residual | OPEN | The one known hole in the shipped gate: a declarative injected as a comma-spliced clause inside a single wh-question still licenses its own words. It needs clause-level rather than sentence-level filtering. Pinned by a strict xfail so it fails loudly when that lands |
| F-2.2-A-05 | OPEN | The flagship gene-disease claim classifies `low` risk, because a `Disease` endpoint row is byte-identical to an identifier-lookup row at `risk_tier_for`'s boundary and Section 8.3.1 calls the second case low risk. Closing it needs the traversed edge label plumbed through `Finding` and `SynthFinding`. Deliberately not fixed by widening the tier tables, which would have broken the protected case |

#### Process decisions to make here

Section 23's offline gate: decide whether it can be claimed at all before Layer 2 and 3 exist.

- Its v1 must-pass set (Q1, Q3, Q4, Q5, Q6, Q8, Q10) spans PubMed, ClinVar, GTR, MedGen, SRA, BioProject and ClinicalTrials.
- None of those have a tool until build phases 3.1 to 3.5.
- Build phase 2.2 ran the citation-synthesizer component gate instead, and said so explicitly rather than claiming the full gate had passed.
- The reconciliation should either sequence the full gate to a phase where it is runnable, or record that the component gate is what "before shipping an answer-generation feature" means for a graph-only phase.

The build-velocity post-mortem's recommendations, `docs/build/Build_velocity_post_mortem.md`:

- Its measured finding is that autonomous execution is not the cost driver, since the same harness shipped four phases in under two days.
- The addressable waste is environmental, meaning network loss, plus one ownerless requirement.
- That requirement: `release-workflow` is marked mandatory in `bossman-mode.md` and has a 0-of-5 real dispatch rate. Either run it or rewrite the rule to state the real practice.

The default-branch rename, `main` to `develop`, on GitHub and across the docs, as one change. Deferred to here on 2026-08-03 rather than done at build phase 2.2's close.

- Reason one: `requirements/Technical_specification.md` Section 24 states that Railway's GitHub integration watches `main` only and that a merge to `main` triggers the deploy. That document is locked until this reconciliation, so correcting it earlier would mean either editing a frozen doc or knowingly leaving three wrong lines in it.
- Reason two: this checkpoint is already sweeping the spec and the rules, so the branch sweep costs almost nothing folded in, and would be a second full pass if done separately.
- Nothing is live on the old name. There is no `railway.json`, no `.github/workflows/`, and no connected deploy, so the rename breaks no running integration today.
- Use GitHub's branch-rename API rather than a delete-and-recreate, since it retargets open pull requests and preserves redirects: `gh api -X POST repos/monideep2255/agentic-search-ui/branches/main/rename -f new_name=develop`
- The sweep covers 8 genuine branch references: `.claude/rules/git-workflow.md`, `.claude/rules/bossman-mode.md`, `.claude/rules/system-design-patterns.md`, `.claude/skills/bossman-mode/SKILL.md`, `.claude/skills/best-practices/SKILL.md`, `.claude/skills/ship/SKILL.md`, `.claude/skills/release-workflow/SKILL.md`, and `.claude/skills/phase-checkpoint/SKILL.md`. Plus `README.md`'s status table and Section 24's three lines.
- What NOT to sweep: every other match on the word is `maintain`, `domain`, `main agent` or `main loop`, and must be left alone.

#### The whole-repository security scan: PAUSED INDEFINITELY

Paused 2026-08-03 by the product owner, on cost. The multi-agent scan is token-expensive and is not being funded for prototype code. It is no longer a hard prerequisite for starting Step 6.3.

The one condition that survives the pause, and the only thing that turns it back on:

- Exposure re-triggers it. If this is ever deployed, given a public URL, or shown to a user who is not the product owner, the scan runs first. The scan's real trigger was always exposure rather than a position in the sequence, so pausing it while nothing is exposed changes the schedule and not the guarantee.

What still holds while it is paused, which is why this is a deferral rather than dropping security:

- The five hooks stay armed: secret scanning on Bash commands and on config writes, the deletion block, the sensitive-read block, and the context-injection scan. These are the only structural enforcement in the repo and they cost nothing.
- `production-standards` and `ai-security-standards` still gate every line written.
- Layer 1 access is read-only by credential rather than by instruction, so no input can mutate the graph.
- `pip-audit` and `ruff` are already installed and free to run, and cover the dependency and static-analysis half of what the scan would have found.

When it does run, whenever that is:

- Scope it to the ENTIRE repository, not a commit range, so there is no baseline commit to carry forward and no range anyone has to remember to widen.
- The only run in `security/` is dated 2026-07-25 and predates every line of build-phase code, so treat it as a first scan rather than an incremental one.

Why the scan was already deferred repeatedly before this pause, decided by the product owner on 2026-07-27 and again on 2026-07-28:

- The Step 6.1 prototype is deliberately throwaway. It holds no real user data and is never exposed, so a defect found in it costs a rewrite that was already planned.
- Scanning per phase would pay repeatedly for the cheap half of the surface while the genuinely dangerous code had not landed yet: Cypher generation against the live graph in 2.1, LLM calls and the agent loop in 2.0, untrusted NCBI payloads reaching synthesis in 3.x.
- The trade is explicit and accepted: phases 1.0 through 2.2 stay unscanned while they are being built, and nothing from that track ships toward v1 until this gate clears.

### Step 6.3: build v1

Everything from build phase 3.0 onward is v1. There is no separate later "v1 phase": Step 6.3 IS v1, and it spans build phases 3.0 through 7.1, twenty phases in all.

#### Which numbered phases belong to which step

The three Step 6.x labels and the numbered build phases are two different numbering schemes, and conflating them has caused real confusion. The mapping, stated once here:

| Step | Numbered build phases | Status as of 2026-08-03 |
|------|------------------------|--------------------------|
| 6.1, the prototype | 1.0, 1.1, 1.2, 2.0, 2.1, 2.2 | Complete, all six merged |
| 6.2, reconcile the documents | none, it is a documentation pause | Moved to run after the 3.x tool phases |
| 6.3, build v1 | 3.0 through 7.1, twenty phases | Starting at 3.0 |

Current sequence after the 2026-08-03 resequencing: the 3.x tool phases, then Step 6.2, then 4.0 and everything beyond.

#### Order inside the 3.x block is not linear

Section 25's dependency graph is the source of truth. Its shape for 3.x:

- 3.0, the guardrail, depends on 2.0 only.
- 3.1, `ncbi_efetch`, depends on 3.0.
- 3.2, 3.3 and 3.5 each depend on 3.1 and are independent of each other, so they can run in parallel.
- 3.4, the full citation-trust surface, depends on 2.2, 3.1, 3.2, 3.3 AND 3.5, so it is LAST in the block despite its number.

Two consequences worth stating rather than rediscovering:

- 3.1 is the phase that makes the system demonstrable to someone other than the product owner. See the note below.
- Build phase 2.2's two open findings, F-2.2-T-01-residual and F-2.2-A-05, are closed at 3.4, not earlier. F-2.2-A-05 in particular needs the traversed edge label plumbed through provenance, which is Layer 2 and 3 work. They stay open through the whole 3.x block, and that is expected rather than drift.

#### The demo bar is separate from Step 6.1's written goal

Step 6.1's goal is "something you can see and feel end to end, one real query through the agent loop with a real answer and citations". That bar is met and the premise gate proves it.

"A working prototype you can show people" is a different bar, and it is NOT met. Measured 2026-08-03: `core/graph.py`'s `_KNOWN_GENE_SYMBOL_CURIES` holds exactly one entry, `BRCA1`.

| What a visitor would type | Resolves |
|----------------------------|----------|
| "Which diseases are associated with BRCA1?" | Yes |
| "What diseases are linked to TP53?" | No |
| "What genes cause breast cancer?" | No |
| "Tell me about cystic fibrosis" | No |
| "Which diseases are associated with NCBIGene:672?" | Yes |

So a visitor can ask about one gene, or type raw NCBI CURIEs. The loop works and the product does not yet. The fix is finding F-2.1-07, gene symbol resolution beyond the seed table, which needs the Layer 2 lookup and is owned by build phase 3.1.

#### The per-phase ritual

Execution follows the build order from the tech spec. Each phase:
1. Create feature branch
2. Dispatch agent teams (builders in parallel, judge, test writer)
3. Skill chain: release-workflow, ship
4. PR for review
5. Merge, then next phase

Phase 6 output: working System 3 (v1).

---

## Phase 7: iteration and new information

Status: NOT STARTED

Goal: incorporate new learnings and evolve the system after v1 ships.

### How new information enters the system

I am attending KGC and Nodes AI conferences. I will encounter new ideas about:
- Knowledge graph patterns
- Red teaming and guardrail approaches
- Agent architectures
- UI/UX for AI systems

New information flow:
1. Collect: save reference material to `reference/personal-os-work/NIH/Agentic-Search/Reference/`
2. Index: add to `requirements/context/Background_requirements.md` (new section or append to existing)
3. Evaluate: does this change anything in the PRD or tech spec?
4. If yes: update the PRD/tech spec, tag the change, rebuild affected components
5. If no: keep as future reference

### Hard stop rule

We do NOT update the PRD or tech spec mid-build. v1 ships based on what we locked in Phase 3 and 4. New information collected during the build goes into the reference folder and gets evaluated for v2.

Exception: if new information reveals a fundamental flaw (security vulnerability, wrong architectural assumption), we pause the build, discuss, and update.

Prototype carve-out: the Step 6.2 reconciliation is the one planned exception. The prototype is built from the docs specifically to test them, so updating the PRD, tech spec, and memo from what the prototype teaches is expected, not a violation. Once v1 locks after that reconciliation, the hard stop applies as written.

### Post-v1 iteration cycle

After v1 ships:
1. Review all collected reference material from conferences and ongoing research
2. Analyze real user data from v1 (queries, tool usage, feedback)
3. Generate new competency questions from real usage
4. Update PRD and tech spec for v2
5. Build v2

This cycle repeats. The system evolves.

---

## Documents we will create

| Document | Created in | Location | Purpose |
| --- | --- | --- | --- |
| Background_requirements.md | Phase 0 (done) | `requirements/context/` | Index of all source material |
| Plan.md | Phase 0 (done) | `requirements/` | This document. Roadmap from research to product. |
| Phase 1 session notes | Phase 1 (done) | `requirements/phase_1/Session_*.md` | Chronological discussion record per session. Also serves as personal learning log. |
| Phase 1 decisions | Phase 1 (done) | `DECISIONS.md` (append) | Architecture choices from source review |
| Phase 1 synthesis | Phase 1 (end) | `requirements/phase_1/Phase_1_synthesis.md` | All decisions organized by topic into a single narrative. Primary input for Phase 2 and Phase 3. |
| Evaluation_playbook.md | Phase 2 | `requirements/` | Living doc: CQ set with tiers and personas, CQ count cap, offline eval gate (rubric plus eval-harness metrics), model-selection method (model-bench), online feedback-loop design. Referenced by the tech spec. |
| PRD.md | Phase 3 | `requirements/` | Product requirements. Single source of truth. Outcome-focused. |
| Technical_specification.md | Phase 4 | `requirements/` | Implementation blueprint. References the evaluation playbook and skills. |
| Strategic_memo.md | Phase 4 | `requirements/` | 1 to 2 page distillation of the PRD and tech spec. Updated after the prototype. |
| Updated skills/agents | Phase 5 (done) | `.claude/skills/`, `.claude/rules/` | Aligned with PRD and tech spec. bossman-mode rewritten, task-tracker and learnings added, eval-harness rewritten against the playbook, three rules added or adopted, two extended, one narrowed |
| Coverage_map.md | Phase 5 (done) | `requirements/phase_5/` | 303 obligations extracted from the three locked docs, each mapped to the rule or skill that enforces it. The gate list Phase 6 builds against |
| Phase 5 synthesis | Phase 5 (done) | `requirements/phase_5/Phase_5_synthesis.md` | What the harness now guarantees, organized by topic, ready for Phase 6 |
| Reference docs (as needed) | Phase 5 (done) | `docs/` | `Tool_implementation_mechanics.md`, 19 per-tool API traps from tech spec Section 6 |
| tracker/ | Phase 5 (created), populated in Phase 6 | repo root | The in-repo build board. `BOARD.md` indexes the phases, `phase_N.M.md` holds each phase's tickets with acceptance criteria, evidence, and append-only history. Maintained by the `task-tracker` skill |
| LEARNINGS.md | Phase 5 (started), running through Phase 6 | repo root | Running capture of build-time learnings during prototype and v1 execution. Maintained by the `learnings` skill: written at the moment of failure, read before every build phase opens. Started in Phase 5 with the first two entries from that session. The input to the Step 6.2 reconciliation: it collects what each build step taught us so the PRD, tech spec, strategic memo, and the living evaluation playbook get updated from a captured record, not memory. Also seeds Phase 7 iteration. |
| Phase 6 continuation prompt | Phase 6 (kickoff prep, 2026-07-26) | `requirements/phase_6/Continuation_prompt.md` | The paste-in kickoff prompt for the first Phase 6 build session: what to read first, the rules that bind the build, the build phase 1.0 detail, and the open items to resolve during the build |

---

## How new information gets incorporated

```
Conference / research / new tool
        |
        v
Save to reference/personal-os-work/NIH/Agentic-Search/Reference/
        |
        v
Add entry to requirements/context/Background_requirements.md
        |
        v
Is the build in progress?
   |              |
   YES            NO
   |              |
   v              v
  Park it.       Evaluate for PRD/tech spec update.
  Review         Discuss. Decide. Update if warranted.
  post-v1.
```

This keeps the build stable while allowing continuous learning. Parked does not mean untouched until v1: Step 6.2 is the single scheduled mid-build sweep where accumulated new-intake and LEARNINGS.md fold into the one planned reconciliation, and everything after that waits for the post-v1 cycle.

---

## Revision history

- 2026-08-07: Build phase 3.1's outstanding re-review debt closed, merged as PR #23 (commit `97aec83`). PR #22 (2026-08-05) had merged without the adversarial pass over its own fix round, the stated pre-merge condition; this is that gap closed, across three independent re-review rounds run the same day.
  - Round 1, six fresh-context reviewers (five by file cluster, one adversary): FAIL. 11 of 26 fix-landed findings closed clean, 15 reopened, and 9 new defects the fix round introduced itself, two CRITICAL: gene-symbol resolution completely broken (a taxon-aware refactor left the cache key on the wire instead of the symbol) and a field-tag fix using invalid Entrez syntax that actively unscoped searches.
  - Fix round: six parallel builders in isolated worktrees closed nearly all of round 1's findings. Integrating their branches surfaced two cross-file seams no single builder could see alone (a `retry_after` value neither side wired up; an HTTP-status guard that landed in one file but not its sibling).
  - Round 2, three more fresh-context reviewers live against NCBI: found a soundness gap neither round caught, the most serious finding of the day. NCBI's `[sym]` tag and the Datasets symbol endpoint both match on gene ALIASES, not only the exact approved symbol, so an "unambiguous" single-id match could silently return a confidently WRONG gene (`HG38[sym]` resolved to a real but wrong gene, `LGR5`). Also found a pre-existing bug that left one round-1 critical fix unreachable in production (EInfo's real response shape was never handled), a second URL-encoding gap in a sibling file, and a regression in round 2's own wait-budget fix. All fixed the same day; the two highest-stakes fixes were mutation-tested, reverted to confirm the new test fails, then restored, rather than trusted on a single pass.
  - Final round, one more fresh-context reviewer dispatched specifically because every fix so far had only been checked in the same session that wrote it: APPROVE. Independently re-verified both critical fixes and the alias-matching fix live against NCBI, confirmed `main` was genuinely broken pre-merge, re-ran the full gate suite, confirmed no test assertion was weakened across the whole round, spot-checked ten closed findings, and confirmed the two deliberately-open findings were genuinely still open. Filed three new minor, non-blocking findings, none reachable in production since `ncbi_efetch` is not yet wired into `act_node`.
  - Net: 40 of 42 numbered findings closed, F-3.1-04 correctly carried, two left open on genuine product decisions rather than resolved unilaterally (F-3.1-41: should acronym-shaped gene symbols stay stopword-blocked; F-3.1-42: should a lowercase gene mention get a fallback). Final gate: 1798 Python tests (1715 passed, 82 skipped, 1 xfailed), doc drift clean, premise gate 19 of 20 live (1 skip, tunnel-gated). Four decisions logged in `DECISIONS.md`. Full per-finding detail: `tracker/phase_3.1.md`.
  - The transferable lesson: a same-session self-check is not an independent review, however thorough. Measured 3-for-3 this same day, the original merge, the six-builder fix round, and two of the lead's own individual patches each had a real defect only a fresh pass caught.

- 2026-08-04, later the same day: Added a metered alternate model backend to the build harness, scoped by role. A build-process change only. No product code, no requirement, and no locked document is affected.
  - Why: the primary provider's weekly limit stops the build outright, and build phase 3.1 is open with the innovation-board date on 2026-08-26. Swapping the model behind an unchanged Claude Code CLI keeps the five security hooks, the permission engine, the rules, the skills and the sub-agents intact, since all of those belong to the CLI rather than to the model. `CLAUDE.md`'s portability section is about losing the CLI, which this deliberately does not do.
  - The load-bearing constraint, and the reason this is a cadence change rather than a configuration note: the alternate backend sets a session-wide subagent model that overrides both per-invocation model parameters and subagent frontmatter. A single-session swap therefore puts the judge and adversary on the builder's model, silently. So the fallback is scoped by role: Depth-tier stages (decomposition, premise gate design, judge, adversary) do not fail over, a review run on the fallback records findings and closes nothing, and no phase reaches the product owner until those stages have run on the primary provider. Same evidence that put those roles on Depth on 2026-08-02: build phase 2.1 failed four consecutive reviews behind a green suite, so a weaker review costs whole rounds rather than latency.
  - Corrected an assumption with measurement rather than carrying it: against the live provider catalogue read this date, the frontier-class open model assumed to be the cheap option for the review band costs about 60 percent of the primary provider's top model through the same gateway, so the depth band stayed on the stronger model and the 40 percent gap bought removal of a tool-use risk both vendors document. The middle band moved to a cheaper model that undercuts both prior candidates on input and output with a larger context. Two rows in DECISIONS.md.
  - Documents touched: `docs/build/Build_workflow_cadence.md` (an alternate-backend column on the provider mapping table plus the role-scoping rule), `.claude/skills/bossman-mode/SKILL.md` (per-dispatch model choice is inert on that backend, and a phase is never opened there), `requirements/phase_6/Continuation_prompt.md` (which session to open for which stage), and a new `docs/build/README.md`. Model identifiers, prices, launch commands and the credential path are deliberately in a local uncommitted note, since they name products and go stale in weeks.
  - Not touched, and stated so nobody goes looking: `requirements/PRD.md` and `requirements/Technical_specification.md` are locked and describe the product, not the harness that builds it. The product's own Guard, Plan and Synth runtime tiers are a separate concept and are unchanged; they are still chosen by the build phase 7.0 model-bench.

- 2026-08-05: Build phase 3.1 (`ncbi_efetch`), the first Layer 2 tool, merged as PR #22. Seven actions across three API families, both error conventions, and live gene-symbol resolution replacing the one-entry seed table, which closes F-2.1-07 and is what made the system demonstrable to someone other than the product owner. The phase premise was restated to what 3.1 actually delivers: the answer-path half (Act-step wiring, Layer 2 citation, trust gate) is carried to T-3.1-28 by product owner decision. 1571 Python tests passing, 82 skipped, 1 xfailed. Premise gate: 19 passed, 1 skipped (tunnel). Doc drift clean.
  - Merged WITHOUT the adversarial pass over its own fix round, which was the stated pre-merge condition. Recorded rather than hidden, because the gap is the phase's most important carried risk. Twenty-seven findings were raised across one judge round and one adversary round; twenty-six are `fix-landed`, meaning commit 59944bc landed 669 insertions and 32 tests claiming the fix and no independent role confirmed any of them, and one is `carried`. None is `closed`. Six of the twenty-six were filed critical, including F-3.1-13, where `summary` returned a schema-valid citation for a record that does not exist, a direct cite-or-refuse breach.
  - The product owner's reasoning, logged in `DECISIONS.md`: the weekly primary budget was at 97 percent, and a review run on the metered backend executes on the builder's own model, so it closes nothing. Merging kept the tool roster moving at the cost of twenty-six unverified fixes. Tracked as the `3.1 re-review outstanding` flag on `tracker/BOARD.md`, resolved before F-2.1-C15 and before 3.2 opens.
  - The transferable lesson, and the reason the finding table gained a three-state vocabulary: a green suite is not evidence a fix round holds. Build phase 2.1 held a green suite through four consecutive failing reviews, and this phase's own judge and adversary rounds each found criticals behind a green suite.
- 2026-08-04: Build phase 3.0, the full Section 10 guardrail, merged as PR #19. Build phase 3.1 opened.
  - What shipped: the phase 2.0 passthrough stub, which made a throwaway model call and emitted a hardcoded `passed=True` for every query, replaced by Section 10.1's pipeline. The cheap non-LLM pre-filter (10.2), boundary validation closed to spec (10.3), Guard-tier classification of injection and off-topic (10.4), and the forbidden-type and read-only screen (10.5). New `guardrail/` package, 148 unit tests across six files.
  - Release gate: premise gate 20 of 20, re-run after every fix round. Python suite 1261 passed, 62 skipped, 1 xfailed. `ruff check src/` clean. Doc drift 0 stale, 0 structural.
  - The design decision worth carrying: the premise gate has TWO arms. A guardrail has no safe direction of failure, since `return refuse` scores one hundred percent on every attack test and destroys the product, so nine of eighteen cases are legitimate questions that must be admitted, anchored on the v1 must-pass moat questions.
  - Judge round 1 returned FAIL with all 34 acceptance criteria individually passing, which is the argument for having a premise rather than a checklist. "What is the capital of the USA?" was fully admitted: the pre-filter's deliberately over-broad symbol pattern was excused by a code comment claiming the classifier would refuse it, and the classifier judged only injection. Section 10.1 step 3 names this step as handling injection AND off-topic, so the fix was spec compliance rather than hardening.
  - Adversary round 1 filed eight findings, two critical. Four third-person clinical questions ("Should this patient be started on tamoxifen given her BRCA1 status?") passed every layer, because the pre-filter keyed on first-person framing, the forbidden screen on narrow literals, and the classifier on injection alone, so nothing owned advice about a third party. A composition defect, invisible to 148 per-layer unit tests. Separately, `normalize` was `[^a-z0-9]+`, which deleted every non-Latin character and refused a genuine Spanish clinical-trials question as off-topic.
  - Two tickets did not land and are carried with dated positions on `tracker/BOARD.md`: T-3.0-07, where clearing the F-2.1-J4-02 xfail needs the graph tunnel that cannot be opened from this environment, and T-3.0-08, F-2.1-C15's generation half, now dated to immediately after 3.1 merges rather than left as an open slot.
  - Process: three of the four carried findings had been given a phase number that would never have fired, which is the ownerless-requirement shape `attack-the-constraint` names and which `release-workflow`'s 0-of-6 dispatch rate already demonstrates live. All four re-homed to owners with real triggers. Two decisions logged.
  - Also created: `PROGRESS.md` at the repo root, a plain-language project update for a reader who has never seen the code, and a new Step 5b in the `phase-checkpoint` skill that refreshes it at every checkpoint.
  - Build phase 3.1, `ncbi_efetch`, opened on branch `phase/3.1-ncbi-efetch` at stage 3: twelve tickets decomposed, no tool code written, stage 5's blocking premise gate not started. It owns finding F-2.1-07, the one-entry gene-symbol table, which is the single thing standing between this repo and a prototype that can be shown to a person.

- 2026-08-03, later the same day: Resequenced Step 6.2 and paused the security scan. Three product-owner decisions, logged in DECISIONS.md.
  - Step 6.2 now runs AFTER the 3.x tool phases rather than between 2.2 and 3.0. The argument is that step's own: its security-scan rationale names 3.x as the genuinely dangerous code, so scanning before 3.x scans everything except the thing the scan is most for. Reconciling the frozen documents after the tool phases is also better input than before them.
  - Checked before moving it rather than assumed: the blocking risk was agents building against known-wrong documentation, and the two documents an agent actually reads, `.claude/rules/production-examples.md` and `docs/ncbi/Tool_implementation_mechanics.md`, are both already corrected. The one still carrying the wrong claim is the locked spec's Section 6.1, which describes a tool already built.
  - The whole-repository security scan is PAUSED INDEFINITELY on cost, and is no longer a prerequisite for Step 6.3. The system has never been tested with a real user and the query set still needs refinement, so hardening a surface that is still moving pays twice. One condition survives and is written into both Plan.md and `tracker/BOARD.md`: exposure re-triggers it, meaning a deploy, a public URL, or first contact with a user who is not the product owner. The five hooks stay armed, `production-standards` and `ai-security-standards` still gate every line, and `pip-audit` and `ruff` remain installed and free.
  - Recorded separately: "a working prototype you can show people" is a different bar from Step 6.1's written goal, and only the written goal was met. `_KNOWN_GENE_SYMBOL_CURIES` holds one entry, so "What diseases are linked to TP53?" resolves to nothing, as does every plain-language question. Build phase 3.1 owns the fix, finding F-2.1-07.
  - Stale-status sweep prompted by the product owner catching one the drift checker could not: `Plan.md` still said "Step 6.1 (prototype) underway", and `CLAUDE.md`, `AGENTS.md` and `README.md` all still named Step 6.2 as next. The checker passed clean throughout, since it verifies counts and phase statuses rather than free-text claims about what comes next.
  - Next up: build phase 3.0, the full guardrail.
- 2026-08-03: Build phase 2.2 (deterministic cite-or-refuse, Layer 1 provenance, the first trust signal) merged as PR #18, closing the Step 6.1 prototype group. At merge time Step 6.2 was next; that was resequenced later the same day, see the entry above.
  - What shipped: the Write step's deterministic half, Sections 8 and 9 plus the two required tests from Section 23. Before this, `write_node` made a synth-tier model call with a bare user question and discarded the response entirely, so no narrative reached any surface and `trust_outcome` was derived from whether a fetched row happened to carry a `source_url`. A citation now means a specific sentence was checked against a specific field value, rather than that a row was fetched. New `synthesis/` package: `findings.py` (8.1), `grounding.py` (8.2), `trust.py` (8.3), `refuse.py` (8.4). Contract additions to `TrustSignalPayload` are additive within v1 per Section 2.6.
  - Release gate outcome: premise gate 11 passed, 1 xfailed by design, 0 failed. Eval gate passed 12 of 12 runs, and 23 of 24 across both runs of the day. Python suite 1154 passed. Frontend 120 passed. `ruff check src/` clean. Doc drift 0 stale, 0 structural. `eval-harness` ran for the first time in this project.
  - Three independent review rounds, two of which returned a failing verdict, and each round's worst defect was in the previous round's fix. That is the pattern `LEARNINGS.md`'s build phase 2.1 retrospective predicts, now confirmed three times in one phase. What they caught, all closed and mutation-tested: a negation grounding as support for the record it denies, a framing prefix smuggling uncited fabrications including a treatment-discontinuation instruction, question-seeding licensing its own affirmation, an ASCII-only tokenizer that made every non-Latin script invisible to both new gates, and non-renderable values shipping as facts.
  - Closed with two findings deliberately OPEN, a recorded product-owner decision rather than an oversight: F-2.2-T-01-residual (a comma-spliced injection inside a single wh-question still licenses its own words, pinned by a strict xfail) and F-2.2-A-05 (the flagship gene-disease claim classifies low risk, since a Disease endpoint row is byte-identical to an identifier lookup at that boundary). Both are the safe direction of failure: the system withholds or under-classifies rather than shipping a false claim. A fourth review round was declined on the reasoning that Step 6.2 already exists as a scheduled pause and is the right place to weigh a residual against the rest of the plan.
  - Six items added to Step 6.2's list, the sharpest being whether Section 8.2's matching rule survives contact with the spec as written: its substring branch answers whether a clause MENTIONS the cited value and has no mechanism for whether it is TRUE about it.
  - Also merged: `docs/build/Build_velocity_post_mortem.md`, answering why one phase now takes a day. Measured finding: autonomous execution is not the cost driver, since the same harness shipped four phases in under two days. The addressable waste is environmental network loss plus one ownerless requirement, `release-workflow`, marked mandatory with a 0-of-6 dispatch rate.
  - 4 decisions logged (198 total), 3 learnings added (43 total).
- 2026-08-02: Fixed repository-wide documentation drift and removed its cause, merged as PR #17. Not a build phase, so build phase 2.2 remains next up and unstarted.
  - What was wrong: `requirements/phase_6/Continuation_prompt.md` described build phase 2.1 in five contradictory sections, and its copy-paste block, the one block designed to be lifted verbatim into a fresh session, instructed the next agent to re-review a closed phase and NOT to open build phase 2.2, which is the next phase. The same append-instead-of-correct failure was found in nine more files.
  - The root cause was mechanical, not a lapse of attention. `.claude/skills/phase-checkpoint/SKILL.md` had an exit-checklist item forbidding any existing content from being rewritten, while step 4 of the same skill required refreshing the continuation prompt's status. Five consecutive build-phase checkpoints resolved that contradiction the safe-looking way and appended a new section rather than correcting the false one above it. Two other checklist items demanding current status and no stale counts were unsatisfiable for that entire period.
  - The evidence that named the cause: `CLAUDE.md` and `AGENTS.md` are the only pair in this repository that never diverged, and they are the only pair with a sync hook behind them. Every pair kept in sync by a person remembering had drifted.
  - Three live hazards were fixed, each of which would have cost real work. `.claude/skills/verify/SKILL.md` instructed the pre-commit gate to treat zero collected tests as a pass, which would have reported READY on a broken test runner against a 977-test suite. `.claude/rules/production-examples.md` and `docs/ncbi/Tool_implementation_mechanics.md` taught the `%s` Cypher parameter mechanism that finding F-2.1-02 proved cannot work, and build phases 3.1 to 3.5 were scheduled to follow it. `requirements/Plan.md` itself named build phase 2.1 as next up while its own status table recorded it merged.
  - Counts corrected against measurement rather than against another document: 977 Python tests (968 was stale in six places), 27 findings closed in build phase 2.1 (26 was wrong), 246 owned obligations (191 was arithmetically impossible against 303 total and 57 unowned), and 11 concept labels in the editable files.
  - The durable outcome is `tracker/check_doc_drift.py`, stdlib only, which computes every tracked count from source and fails when any document states a stale value. It is gated in the `phase-checkpoint` exit checklist and is check 6 of `/verify`. It found four stale spots on its first run that the manual passes had missed, including one in `CLAUDE.md`, and it caught the DECISIONS.md count twice more during this session's own work.
  - The one-owner convention was adopted and recorded in `phase-checkpoint`: every fact has exactly one owner file, and every other mention is a pointer. `CHANGELOG.md` was deleted under it, returning at the v1.0.0 release, since a changelog records releases and none has been cut. This Revision history is now the project's change record.
  - Verified by five no-loss blockers, all passing at close. Two independent fresh-context auditors returned FAIL on the first run, finding one weakened requirement, five orphaned facts, five dangling cross-references, and a stale count the drift script itself could not see. Every finding was fixed at source, and the script was widened rather than its tolerance loosened. Zero lines changed under `src/`, `tests/`, or `frontend/`.
  - Measured negative result, recorded rather than rounded off: consolidating seven never-cited rules cut `.claude/rules/` from 28 files to 22 and saved no context at all, 132,181 bytes before and 134,463 after. Consolidation moves content rather than removing it. The context saving that did land is the continuation prompt, 281 lines to 89. The larger lever proved to be reasoning effort, dropped to medium for every cadence role except the judge, the adversary, the decomposition and the premise gate, on a 76 percent output-token reduction at equal task completion externally and this repository's own measured 27x latency multiple at identical correctness. That saving is projected and unmeasured until build phase 2.2 runs under it.

- 2026-08-01: Closed build phase 2.1, merged as PR #15, after FIVE judge passes and FIVE adversary passes. All 9 tickets `done`, 27 findings `closed`, 3 `deferred` with a named reason. Final gates: 968 Python tests passing (up from 798), premise gate 9 of 9 on three consecutive runs, 120 frontend tests, ruff clean, pip-audit and npm audit clean.
  - The load-bearing fact about this phase, and the reason it took five rounds: it failed four consecutive reviews while its test suite was green. At the fourth review the suite stood at 879 passing and the judge's live run answered 3 of 8 real questions correctly. The worst case returned twenty-five non-human orthologs for "which diseases are associated with BRCA1?", `status="ok"`, every row carrying a real and resolving NCBI citation.
  - The root cause was a COMPOSITION defect between two individually correct components. Think emits a hardcoded `query_class="lookup"` stub, and `lookup` mapped to a 0-hop schema slice, which for a Gene anchor renders exactly one edge, `orthologous_to`. The generator was asked about diseases and handed a schema containing no disease at all. Neither component was wrong, which is why every component-level review passed it. The fifth judge proved it with a controlled A/B: at hop floor 0 the model returns 25 orthologs, at floor 1 it returns the correct 4 diseases, same model and same question.
  - Roughly 25 real defects were fixed across rounds two to four in the parameter binder and the citation layer. Every one was genuine. None was causal. The same wrong-entity invariant was defeated three separate times, each time by its own replacement.
  - The durable outcome is `tests/system_03_search_agent/tools/test_cypher_query_premise.py`, which does not mock the model and asserts on the MEANING of the answer against ground truth pinned from the live graph. Every other test in the suite, outside this one file, mocks the model call, so none of them could see a generation defect. It landed failing at 3 of 9 and now passes 9 of 9. It has already caught two regressions from the phase's own late fixes, before a reviewer found them.
  - Process changes merged separately as PR #16, so the lesson binds on later phases rather than depending on recall. The build cadence gained a twelfth stage: write the premise gate and WATCH IT FAIL, blocking all builder work, mandatory for any phase whose deliverable is model-generated. `task-tracker` makes it the first ticket at phase open. Three rules gained sections: read the model's INPUT before debugging its output, review a fix harder than new code, and a verify surface must state its own coverage.
  - Deferred with named triggers, not silently: prompt injection steering entity selection (mitigated, `xfail` with the reason recorded, closes in build phase 3.0's Guardrail); constraining generation so an unbounded traversal cannot be produced, and a second exhaustion shape, both to 2.2; a fourth `status` value for "matched plenty, cited none", to 2.2; the `vocabulary_artifact_fields` marker's consumer, to 2.2's Write step; and gene symbol resolution beyond a one-entry seed table, which is Layer 2 work in build phase 3.1.
  - A generated query OOM-killed the live graph database mid-phase and it was restarted by hand. Mitigated with a session-level memory cap, and the hop-floor fix removed the query shape that caused it.

- 2026-07-29: Shipped build phase 2.1 on branch phase/2.1-cypher-tool, WITH ONE RECORDED GAP. Delivered `cypher_query` over Layer 1: the Section 6.1 three-step internal pipeline (schema slice, plan-tier generation, validate then execute) with one repair retry, edge-label enforcement, agtype interpretation, host-pinned Layer 1 citations, and the Act-step wiring that makes the loop actually reach the graph. 798 Python tests passing, up from 539. All 9 tickets, T-2.1-01 through T-2.1-09.
  - The recorded gap, and it is the load-bearing fact about this phase: the judge and the adversary both FAILED it on the pre-rework code, filing roughly 27 findings including 2 critical and 5 high. Every blocker was fixed and the live end-to-end gate went green. None of that rework has been reviewed by any independent agent. Merged on an explicit product-owner decision against a weekly budget limit, recorded rather than glossed. A fresh judge and adversary pass over the phase 2.1 surface is build phase 2.2's first task. Full detail in `tracker/phase_2.1.md`'s "Phase close status" section.
  - Why the gap is worth stating this loudly: this phase produced a false green first. Every ticket read green, 716 tests passed, and the judge still found the phase premise unmet while the adversary found 17 defects. The dominant cause was that `execute_cypher` was mocked in every `cypher_query` test and the one live test bypassed `cypher_query` entirely, so no test ever crossed the module seam against reality. The fix was T-2.1-09, a 9-test end-to-end suite that runs against the live 115M-node graph with only the model call mocked. It cannot be satisfied by mocks, which is why it is now the phase gate.
  - Layer 1 access established: an SSH local port-forward, since Postgres binds 127.0.0.1 only and port 5432 is refused externally. This is Decision D phase one, and it was reachable all along; an empty `.env` had been read as missing credentials rather than as an unopened tunnel. Nothing in the repo opens the tunnel, so a fresh clone cannot run the live tests until someone does it by hand.
  - Security decision, product-owner approved: created a least-privilege `kg_reader` role (non-superuser, `pg_read_all_data`, `default_transaction_read_only`, 30s `statement_timeout`) rather than connecting as the `postgres` superuser, which was the only pre-existing login role. Verified it can read and provably cannot write, with graph integrity re-checked afterwards. A non-superuser cannot run `LOAD 'age'`, so AGE is made available via `session_preload_libraries` set on the role, avoiding a restart of the production database.
  - Harness defect surfaced from phase 2.0 and fixed here: no real model call had ever completed through the harness. The fallback price table was empty and none of the three tier defaults appears in litellm's price map, so every call was billed by OpenRouter and then discarded because it could not be priced. Invisible until now because every test mocks litellm.
  - Two spec defects filed for the Step 6.2 reconciliation. Section 6.1 states a parameter-passing mechanism that cannot work, since psycopg2 interpolates `%s` client-side and AGE requires a genuine bind parameter; the same claim propagates into `docs/ncbi/Tool_implementation_mechanics.md` and `.claude/rules/production-examples.md` example 1, whose "correct" sample uses the non-working form. Separately, Section 24's env-var table names `PER_USER_DAILY_CAP_USD` where the code deliberately renamed it to `PER_USER_DAILY_QUERY_CAP`, so provisioning from the spec instead of `env.example` yields a broken config.
  - Still open: F-06, 2 of 6 model calls per query bypass the stable prompt prefix, a cost inefficiency rather than a correctness defect.
- 2026-07-28: Shipped build phase 1.2 on branch phase/1.2-react-shell-sse, merged as PR #12. Delivered the React shell (Vite plus React 19 plus TypeScript), incremental SSE streaming (`core/run_streaming()`, `core/run_registry.py`, three new endpoints alongside the untouched buffered `/query`), the full chat UI, and Playwright end-to-end testing. All 8 tickets done, including T-1.2-08, added mid-phase to wire `ChatPage` end to end after the lead caught that the built-and-tested chat components were never assembled into a working page. 539 Python tests passing, up from 483, plus 120 frontend unit tests and 3 Playwright end-to-end tests.
  - Judge-reviewed (all 8 tickets passed on the code; the review also caught that 4 tickets' tracker records were never backfilled at build time and a dead-code defect in `ChatShell.tsx`, both fixed before close) and adversary-tested against the real running system (6 findings: 1 fixed in-phase, an unvalidated empty or whitespace-only query; 4 deferred with named triggers on `tracker/BOARD.md` against build phases 4.0 and 6.1; 1 rejected as spec-conformant behavior, not a defect).
  - Scope decision, mid-phase: added T-1.2-08 to the original 7-ticket decomposition after the lead found `ChatPage.tsx` was still a placeholder and no ticket owned wiring the six already-built chat components together, closing the gap before the E2E ticket needed a real page to test against.
  - Supply-chain decision: `@playwright/test` and `@axe-core/playwright` installed pinned exact after a live re-verification at install time, honoring an explicit product-owner instruction that any doubt at all blocks the install.
  - Release gate outcome: the whole-repository security scan was deferred again, consistent with build phases 1.0, 1.1, and 2.0, all in the Step 6.1 prototype group awaiting the Step 6.2 reconciliation.
  - Phase close was independently re-confirmed by a fresh-context agent rather than the same judge resuming to close its own findings, per this repo's own `LEARNINGS.md` rule against that pattern.
- 2026-07-28: Shipped build phase 2.0 on branch phase/2.0-langgraph-agent-loop, merged as PR #9. Delivered the real five-node LangGraph Guardrail, Think, Plan, Act, Write loop, replacing the phase 1.0 stub; the three-tier harness wired to LiteLLM and OpenRouter with per-model cost accounting; all four Section 19.1 cost caps enforced end to end where the two daily caps are wired but not yet fed real data; the coordinator-worker split scaffold; the prompt-cache stable-prefix scaffold. 483 tests passing, up from 314.
  - Judge-reviewed (all 8 tickets passed, phase-level premise independently verified) and adversary-tested (8 findings filed, all confirmed by a second judge triage; 4 fixed in-phase, 4 deferred with named triggers against build phases 2.1, 4.6, and 7.0).
  - Product-owner decision on a judge-filed finding (F-2.0-05): cost and token usage are internal-only, never shown to the end user, resolving a conflict between two spec sections on whether the final cost figure may reach an end-user surface.
  - Release gate outcome: the whole-repository security scan was deferred again, staying consistent with build phases 1.0 and 1.1.
- 2026-07-28: Shipped build phase 1.1 on branch phase/1.1-auth-service, merged as PR #6. Delivered minimal v1 auth (argon2id password hashing, HS256 access tokens with the algorithm pinned, opaque SHA-256-hashed refresh tokens, a 15-minute access TTL, a 30-day sliding refresh TTL, a 90-day absolute ceiling), five endpoints at `/auth`, and all six Section 15 user-data tables via SQLAlchemy models and two Alembic migrations with working downgrades. 314 tests passing, up from 191. Six decisions logged, three learnings recorded.
  - Closed the ecdsa CVE carried forward from build phase 1.0 by replacing `python-jose[cryptography]` with `PyJWT`. Researcher verification established that `ecdsa` is a core requirement of `python-jose`, not gated behind the `[cryptography]` extra, so it could not be excluded in place.
  - Scope decision: built all six Section 15 tables rather than the three named in Section 25's parenthetical, since `interactions`, `saved_queries`, and `auth_sessions` are foreign-key interdependent and three tables alone do not form a loadable schema.
  - Release gate outcome: 18 findings raised, 9 closed with re-verified fixes, 2 rejected, 7 deferred to named later phases (1.2, 2.0, 4.x, 6.0). The two most serious were found only by the unscripted adversary pass after the scripted judge had passed the phase clean. First, the migration test ran `alembic downgrade base` against the database named by `USER_DB_URL`, destroying every row on each run while restoring the schema on teardown so nothing looked wrong; canary-proven, 11 users before and 0 after. Second, refresh rotation shipped correctly but delivered none of the security property Section 15 claims for it, since nothing acted on the replay it detected; now fixed with RFC 6819 reuse detection that revokes the whole session family.
  - `dev-standards` six-lens pass returned safe to open, and caught that the README still listed `python-jose` under Auth, so a developer following it would have reinstalled the removed vulnerability.
  - The whole-repository security scan was deferred again by product-owner decision and scheduled once at Step 6.2, where it is now a hard prerequisite for starting Step 6.3. Build phases 1.0 and 1.1 remain entirely unscanned.
- 2026-07-27: Opened Phase 6 (build) and shipped build phase 1.0 on branch phase/1.0-fastapi-skeleton, merged as PR #5: the FastAPI app skeleton, the health endpoint, the Pydantic event contract (Query, RequestContext, the Event envelope, all eleven Section 2.3 payload types), and a typed run() stub wired to a query endpoint. Judge rejected once (an open-dict payload not bound to its declared type, an unbounded session_memory field), both fixed and independently re-verified by a separate agent per task-tracker's raiser-never-closes rule. 191 tests passing. Two supply-chain items resolved: setuptools upgraded to 83.0.0, clearing three known CVEs (a path traversal in `PackageIndex`, a remote code execution in the download functions, and a Unicode-normalization bypass in `MANIFEST.in` exclusions), ecdsa's unfixable CVE accepted as a risk deferred to phase 1.1. The full multi-agent security scan was deliberately skipped for this phase (no auth, database, LLM, or external-API surface yet), relying on the judge's gates and two independent adversarial-probe passes instead.
- 2026-07-26: Opened Phase 5 on branch phase/5.0-system-tooling-updates and completed Steps 5.1 to 5.4. Scope was set by a coverage map: 303 obligations extracted from the three locked documents by ten parallel agents, 57 of which had no owner.
  - Step 5.1: overhauled bossman-mode. Fixed the branch-naming defect (both executing skills created `feature/description` against the `phase/N.M-description` convention every rule states, which also silently disabled ship's MR step). Made tech spec Section 25 the source of truth for the 26 build phases. Made worktree isolation the default for concurrent file-mutating builders with read-only agents in the shared checkout. Added the product owner role, per-phase product-owner-required marking, a scope check, and a Playwright gate for UI phases. Wired `verify`, `eval-harness`, and `dev-standards` into the phase-end chain, none of which the skill had ever invoked.
  - Step 5.2: added two skills, `task-tracker` and `learnings`. Rewrote `eval-harness`, which never referenced the evaluation playbook and was missing 13 of its 17 demands. Added rules `tool-call-budgets` and `v1-scope-boundary`, adopted `prompt-cache-discipline` from the personal-os reference, extended `production-standards` and `system-design-patterns`, and narrowed `dependency-tracking` to hooks only. Zero of the four skills this document originally floated were built, because the coverage map showed the gaps were rules and docs.
  - Step 5.3: corrected 19 stale statements across the root documents, rewrote the pull request template off the inherited BioLink and KGX gates, and fixed three documented slash commands that did not resolve.
  - Step 5.4: added `docs/ncbi/Tool_implementation_mechanics.md`, 19 per-tool API traps taken from tech spec Section 6.
  - Deferred by the product owner: unattended overnight execution. The standing deny on proceeding past a phase without approval holds. 124 decisions logged.
- 2026-07-25: Completed Phase 4 Step 4.4, the strategic memo, and closed Phase 4. Deliverable: `requirements/Strategic_memo.md`, a one-to-two-page executive distillation of the locked PRD and the locked technical specification, written for a future collaborator or future-me. Phase 4 is now COMPLETE: the verified API capability sheet, the locked technical specification, and the strategic memo are the phase's three deliverables, which together serve as the phase synthesis (no separate synthesis document, unlike Phase 1). Phase 5 (system and tooling updates) is next. 113 decisions logged.
- 2026-07-25: Completed Phase 4 Steps 4.1 to 4.3 and locked the tech spec.
  - Step 4.1: outlined the tech spec's 25 sections once the core-architecture decisions locked, expanded from the original 19-section list.
  - Step 4.2: drafted the tech spec to implementation level, seven sections drafted in parallel against the PRD.
  - Step 4.3: reconciled the draft (the citation, cost, and error event schemas unified against the canonical Section 2 and Section 9 definitions; the tool roster expanded from five to seven with `pathogen_detection` and `clinicaltrials_search`; the delivery surfaces reconciled to six against the locked PRD), graded twice fresh-context per self-eval-loop with the schema-consistency failure cleared and verified on the re-grade, then locked.
  - Deliverable: `requirements/Technical_specification.md` (25 sections, seven tools, six delivery surfaces). Step 4.4 (the strategic memo) is next. 113 decisions logged.
- 2026-07-25: Logged the Step 4.1 core-architecture decisions: the core service contract and versioned event stream (Decision A) with builder-only cost visibility, the coordinator-worker harness with the reader scoped to untrusted free text only (Decision C), transport-per-phase for Layer 1 (Decision D), the deterministic Write-step trust signal with a refuse fallback link (Decision E), personalization kept out of the grounding path (Decision F), and the feedback-loop and session-memory mechanism (Decision G). Step 4.1 remaining work: the tech-spec outline plus the parked threads (the A/B model-combination mechanism, the acceptable-staleness threshold, the concurrency queue strategy, the provenance type's four added fields). 109 decisions logged.
- 2026-07-25: Completed Phase 4 Step 4.0, the NCBI and enrichment API current-state deep dive. Deliverable: `requirements/phase_4/API_capability_sheet.md`, live-verified against production endpoints, fresh-context graded with six fixes applied. All three Phase 2 feasibility flags resolved (Q1, Q5, Q6); the moat cap holds at seven. Opened the Step 4.1 architecture discussion (core-outward frame accepted); flagged Layer 1 reachability from the deployed agent as an open decision. Added the plan-then-fan-out rule. 102 decisions logged.
- 2026-07-24: Opened Phase 4 (technical specification), Step 4.0 next. Set the build-phase doc-review cadence: the PRD, tech spec, and strategic memo freeze after Phase 4 and update only at the Step 6.2 reconciliation, and new-intake is swept once at Step 6.2 rather than continuously (Step 6.2 and the how-new-information-gets-incorporated section updated). Declined three third-party NCBI MCP servers as inbound dependencies, kept as reference only. 94 decisions logged.
- 2026-07-22: Completed Phase 2 (Steps 2.1 to 2.5) and produced the evaluation playbook (the moat test with the no-general-tool-equivalent bar, the seven-question v1 must-pass set plus the fast-follow and expansion pool, the coverage metric, the offline eval gate, model selection, and the online feedback loop). Completed Phase 3: drafted and locked the PRD. 90 decisions logged.
- 2026-07-21: Completed Phase 1 (Steps 1.7 to 1.13) and wrote the Phase 1 synthesis.
  - Step 1.7: tagged the contractor package as Track 2, bucketed the NFR baseline, set a generation-first NLQ hybrid with verified templates for the tier-1 competency questions, scoped v1 federation to the three data layers, and adopted the milestone ladder as a PRD success requirement.
  - Step 1.8: locked the stack (Railway, PostHog, LangSmith, and a self-maintained in-repo tracker) and the build-first-then-migrate hosting strategy.
  - Step 1.9: dispositioned the ten open questions.
  - Step 1.10: settled the five cross-cutting concerns (forbidden-output boundary, data freshness, rate limiting, UI architecture, accessibility).
  - Step 1.11: surveyed 45 new-intake documents and locked the adopt batch (coordinator/worker cost mechanism, prompt caching, model-bench, opinionated tools, provenance-gated memory) plus the cost-cap starter values and the deferral calls.
  - Step 1.12: surveyed three conferences (ISMB, KGC, Nodes-AI) and locked the PRD-feeding batch (NL-to-Cypher discipline, provenance schema expansion, grounding gates, eval-harness redesign).
  - Step 1.13: split the LLM legal obligations into the Track 1 versus production framework (country-of-origin Option A).
- 2026-07-20: Added new Phase 1 sources (Steps 1.11 and 1.12), turned the Phase 2 output into a living evaluation playbook, added the strategic memo deliverable, and restructured Phase 6 to build the prototype from the docs first, then reconcile, then build v1.
- 2026-05-07: Extended the plan beyond the kick-off outline. Steps 1.1 to 1.5 locked.
- 2026-05-06: Kick-off. Phase 0 completed: all background material collected, vision aligned, and plan agreed.
