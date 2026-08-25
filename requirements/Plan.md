# System 3 planning roadmap

From background research to working product. This document defines every step between where we are now (raw research collected) and where we need to be (a running search agent + UI backed by a solid PRD and technical specification).

Kick-off: 2026-05-06. Last updated: 2026-08-25.

## Status at a glance

| Phase | Status |
|-------|--------|
| Phase 0: foundation | Complete (2026-05-06) |
| Phase 1: source review and architecture decisions | Complete, all 13 steps (2026-07-21) |
| Phase 2: competency questions and evaluation playbook | Complete, all 5 steps (2026-07-22) |
| Phase 3: PRD | Complete, PRD locked (2026-07-22) |
| Phase 4: technical specification | Complete, all steps 4.0 to 4.4 done (2026-07-25) |
| Phase 5: system and tooling updates | Complete, all steps 5.1 to 5.4 (2026-07-26) |
| Phase 6: build (bossman execution) | In progress. Step 6.1 (prototype) COMPLETE. Step 6.3 (build v1) has merged build phases 3.0 through 3.5 and 4.0 through 4.12. THE PRODUCT IS DEPLOYED AND ANSWERING as of 2026-08-24 (PR #61), live at https://search-agent-web-production.up.railway.app with CD watching `develop`. BUILD PHASE 4.16, the seven UI defects the live demo surfaced, MERGED as PR #63 on 2026-08-25 and is LIVE on the demo, verified on the deployed product rather than asserted. Next: build phase 4.14 (CI, inserted 2026-08-24 and still not started), then 4.13 (durable history) and 4.15 (the two-environment release flow). Per-phase status: `tracker/BOARD.md` |
| Phase 7: iteration and new information | Not started |

Decisions logged: 414 (DECISIONS.md). Deliverables produced: the Phase 1 synthesis, the evaluation playbook, the PRD (locked), the verified API capability sheet, the technical specification (locked), and the strategic memo. The dated change log is in Revision history at the end of this document.

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
- [Phase 8: NCBI infrastructure migration](#phase-8-ncbi-infrastructure-migration)
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

Four items, all recorded with evidence in `tracker/phase_2.2.md`. Two were spec decisions, resolved at Step 6.2 on 2026-08-10 by absorbing both into `Technical_specification.md` Section 8.2 as new steps 5a and 5b, per the product owner's decision to keep the spec text describing what actually ships. Two remain open defects.

| Item | Status | What the reconciliation decided |
|------|--------|--------------------------------------|
| Section 8.2's matching rule | RESOLVED, Step 6.2, 2026-08-10 | The substring branch answered whether a clause MENTIONS the cited value and had no mechanism for whether it is TRUE about it, so a negation, an invented drug regimen, or a fabricated statistic grounded cleanly against a matched identifier. The prototype's two additions, `numbers_are_supported` and `claim_introduces_no_new_content`, are now written into Section 8.2 as steps 5a and 5b, since both only ever reject claims step 5 would have accepted and never accept one step 5 would reject |
| F-2.2-05, thousands-separator normalization | RESOLVED, Step 6.2, 2026-08-10 | Widened Section 8.2 step 4 beyond its listed operations: it equates two spellings of one number and nothing else, and without it a correct, well-cited answer was refused. Step 4's spec text now describes it |
| F-2.2-T-01-residual | OPEN, deliberately not fixed this session | The one known hole in the shipped gate: a declarative injected as a comma-spliced clause inside a single wh-question still licenses its own words. It needs clause-level rather than sentence-level filtering, real engineering work, not a documentation change. Product-owner decision, 2026-08-10: keep tracking rather than fix inline during the Step 6.2 reconciliation pass. Pinned by a strict xfail so it fails loudly when that lands |
| F-2.2-A-05 | CLOSED, build phase 3.4 | Was: the flagship gene-disease claim classified `low` risk, because a `Disease` endpoint row was byte-identical to an identifier-lookup row at `risk_tier_for`'s boundary and Section 8.3.1 called the second case low risk. Closed by build phase 3.4 (PR #28, 2026-08-10): the traversed `gene_associated_with_condition` edge label, read straight off the already-generated Cypher text, is now plumbed through `Finding` and `SynthFinding`, so the claim classifies `high` risk via the traversed relationship rather than the bare endpoint node type. Not fixed by widening the tier tables, which would have broken the protected identifier-lookup case |

#### Process decisions to make here

Section 23's offline gate, DECIDED at Step 6.2, 2026-08-10: stays scheduled for build phase 5.1, not run early.

- Its v1 must-pass set (Q1, Q3, Q4, Q5, Q6, Q8, Q10) spans PubMed, ClinVar, GTR, MedGen, SRA, BioProject and ClinicalTrials.
- None of those had a tool until build phases 3.1 to 3.5, all now merged, so this is the first point the full gate is even runnable.
- Build phase 2.2 ran the citation-synthesizer component gate instead of the full v1 gate, and said so explicitly rather than claiming the full gate had passed; that framing holds through every answer-shipping phase since.
- Product-owner decision: do not spend the real LLM-call cost running the 7-question version now. Build phase 5.1 already exists specifically to build the full 50-query golden dataset and wire real grading against it (Section 25); running the smaller 7-question version early would be setup work redone at 5.1, not saved work. The wait for 3.1 to 3.5 to land was correct, not a compliance gap: the gate could not have run any earlier.

The build-velocity post-mortem's recommendations, `docs/build/Build_velocity_post_mortem.md`:

- Its measured finding is that autonomous execution is not the cost driver, since the same harness shipped four phases in under two days.
- The addressable waste is environmental, meaning network loss, plus one ownerless requirement.
- That requirement, DECIDED at Step 6.2, 2026-08-10: `release-workflow` was marked mandatory in `bossman-mode.md` with a 0-of-6 real dispatch rate across every phase through 3.4. Product-owner decision: rewrite the rule to state the real practice (judge round, adversary round, and the gates in `docs/build/Build_workflow_cadence.md` stage 10) rather than start dispatching a skill nothing has needed. The real practice caught real defects at 0-of-6 dispatch; keeping an unenforced rule on the books erodes trust in every other rule, per this repo's own `attack-the-constraint` standard on ownerless requirements.

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

Everything from build phase 3.0 onward is v1. There is no separate later "v1 phase": Step 6.3 IS v1, and it spans build phases 3.0 through 7.1, twenty-one phases in all (twenty at the original count, plus build phase 4.8, inserted 2026-08-11 as a product-owner-directed exception to the locked build order).

#### Which numbered phases belong to which step

The three Step 6.x labels and the numbered build phases are two different numbering schemes, and conflating them has caused real confusion. The mapping, stated once here:

| Step | Numbered build phases | Status as of 2026-08-03 |
|------|------------------------|--------------------------|
| 6.1, the prototype | 1.0, 1.1, 1.2, 2.0, 2.1, 2.2 | Complete, all six merged |
| 6.2, reconcile the documents | none, it is a documentation pause | Moved to run after the 3.x tool phases |
| 6.3, build v1 | 3.0 through 7.1, twenty-one phases (4.8 added 2026-08-11) | Starting at 3.0 |

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

## Phase 8: NCBI infrastructure migration

Status: NOT STARTED. Opened 2026-08-18 as a parking list, not a schedule.

Why this section exists. Step 1.8 locked a build-first-then-migrate hosting strategy: build the Track 1 prototype on Railway and our own stack, then migrate to NCBI or OCCS infrastructure after the proof of concept. That decision has been carried in Phase 1's synthesis and in the technical specification's fast-follow triggers ever since, but it was never a phase in this document, so the work it implies had nowhere to accumulate. Items were being remembered in conversation instead. This section is where they land from now on.

What it is not. This is not a plan with an order or a date. Everything here is blocked on one event, the move from this laptop to an NCBI Linux machine, and the sequencing question cannot be answered usefully before then. Treat it as the list to read on the first day on that machine.

### What triggers it

One event: the working environment moves to NCBI infrastructure. Nothing in this section starts earlier, and nothing in it is a reason to change v1. The two existing fast-follow rows in `Technical_specification.md` Section 25 whose trigger column reads "Migration to the NCBI or OCCS production track" fire on this same event, and they are not restated here.

### The list

| Item | What it means | What it blocks on |
|------|---------------|-------------------|
| Adopt the NCBI or NWS design system in the frontend | Replace the hand-transcribed token chain with the real system. Confirmed 2026-08-18: it is reachable only from NCBI infrastructure, so no part of this can start on this laptop | Environment move. See the design-system note below |
| Migrate the codebase to P2 | Move off Railway onto NCBI's P2 platform. Needs its own environment, secrets, and deployment story, none of which are written down yet | Environment move, plus access approvals |
| Move the repository under NWS experimental | Relocate from the personal GitHub remote to the NWS experimental repository, which changes the review and merge process, not just the remote URL | Environment move, plus whatever the NWS repository's own onboarding requires |
| Section 508 and WCAG 2.1 AA formal audit | Already a fast-follow row in Section 25, listed here so the migration list is complete in one place | Same trigger |
| Enterprise IAM, session expiry, access review | Already deferred to the production track by the PRD, same reason for the pointer | Same trigger |
| FedRAMP, FISMA, ATO authorization path | Binds the production path only, per Step 1.13 | Same trigger |

### The design-system note, since it is the item most likely to be misread

The frontend today has a working three-link token chain: the design system's own `colors.html` holds the values, `frontend/src/theme.ts` transcribes them, and a premise gate asserts the transcription so a nudged colour fails the build. Every value in that chain already claims to be USWDS, the system NCBI is built on, so the migration is expected to be a swap of the source rather than a re-design of the product.

Two things follow, and both matter for not wasting effort before the move:

- Do not adopt the NCBI design system early by hand-copying values out of it. That would create a second unmirrored source, which is the exact failure already recorded in `LEARNINGS.md` for 2026-08-14, where a token push reached 21 mirrored cards and left two unmirrored copies stale.
- The premise gate is the thing that makes the swap cheap. It already pins every colour to a named source, so replacing the source is a contained change with a test that fails loudly if the swap is partial. Keep that gate healthy through v1 for this reason, not only for its own phase.

### Open questions to resolve on the NCBI machine, in this order

1. How is the design system actually distributed there: an internal npm registry, a Git remote, or a vendored copy? The answer decides whether the swap is a dependency change or a file mirror.
2. Does P2 support the current stack as built (FastAPI, LangGraph, a React single-page application, PostgreSQL, and an outbound connection to the graph host), or does something have to change shape?
3. Does the read-only graph connection survive the move, or does the graph itself also need to relocate? This is the one item that could turn a migration into a re-architecture, so it is worth answering early rather than late.
4. What does the NWS experimental repository require before a first push: review process, branch protection, CI, secret handling?

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

- 2026-08-25: BUILD PHASE 4.16, THE UI DEFECTS FROM THE LIVE DEMO, MERGED as PR #63 and LIVE on the demo. Verified on the deployed product after the merge rather than asserted: the SSE trace now reads guard 2.21s, think 4.77s, plan 5.53s, tool_start 5.53s, tool_result 8.35s, tool_start 8.35s, tool_result 8.61s, answer 15.02s, so the 10.9-second silence is gone and the Act step reports itself twice; the live answer screen reads `2 tools`, `Single source, not independently confirmed`, and `MedGen C0346153`. ONE RESIDUAL is named rather than glossed: 6.4 seconds still pass between the last tool result and the answer, because the Write step emits nothing while it synthesises, which is T-4.16-08. Inserted 2026-08-25 by product-owner decision, the fifth such exception after 4.8, 4.10, 4.11/4.12 and 4.14/4.15, and ranked ahead of build phase 4.14 because the product is live at a public URL and every visitor was watching a frozen stepper. All SEVEN reported defects closed. THE TOP DEFECT WAS BACKEND, NOT FRONTEND, and was measured before a ticket was written: timestamping each SSE frame off the deployed API gave guard at 0.15s, think at 0.15s, plan at 1.41s, then 10.9 SECONDS OF SILENCE, then the whole answer inside 10ms. `sink.emit` was never called with `tool_start` or `tool_result`, both of which are in the contract and handled by the CLI, MCP and GraphQL adapters, so only the producer was missing and the Act step was invisible everywhere. `useRunView`'s own docstring had predicted the consequence in 2026-08-12 and it was read as a design principle rather than a live symptom. THE CONSTRAINT WAS THE NODE BOUNDARY, NOT THE MISSING EMIT: `_EventSink` accumulates and `astream` yields per completed node, so the obvious fix would have flushed every tool frame in one burst before the answer and left the silence exactly as long; the fix writes to LangGraph's custom stream at dispatch AND still returns through `sink.result()`, de-duplicated on `seq`.

  WHAT ELSE SHIPPED: a conversation thread that keeps earlier turns on screen collapsed, per the prototype's own `archiveCurrent()`; client-side routing with no router dependency; the integrations page corrected to the five surfaces that actually shipped, guarded by a Python test cross-checking every command against `pyproject.toml` and every path against the FastAPI route table; a citation chip that no longer repeats its own source; an `ask` outcome that no longer blames the reader for single-source evidence; and a feedback thumb that renders inside its own button.

  WHAT IT COST, and it is not the features. SIX assertions that could not fail, FIVE written by the lead in this phase, every one caught by mutation or by a screenshot and NONE by reading. The deepest is not on that list: both existing second-turn arms were CORRECT, honest, and blind, asking "can a second turn be taken" and answering yes on every path in two environments, while the real defect was that the previous turn vanished. A test can be right and measuring the wrong property, which is why the reported defect survived two direct investigations. THREE HARNESS GAPS were found and recorded with owners: the guest path had never been exercisable in the browser suite because the e2e mock omits `ANON_DAILY_RUN_CAP`; the browser suite cannot reach a real tool dispatch at all, which also explains the standing `answer-cap` failure; and two live diagnostic specs claimed "skipped by default" with no skip and would have fired at the public demo on every CI run. A DESIGN-SYSTEM GAP is recorded rather than worked around: the follow-up field and the conversation thread exist only in the prototype and in no component card, and the trust-pills card has no `ask` state, so surfaces the cards cannot grade are exactly where these defects shipped. Release gate: Python 3947 passed with zero failures, frontend 216, Playwright 46 passed with 2 gated live diagnostics and 1 pre-existing failure proven at the branch point, ruff clean on `src/`, typecheck and production build clean, doc drift 0 stale and 0 structural. Four decisions logged. Full record: `tracker/phase_4.16.md`.

- 2026-08-24: BUILD PHASE 4.12, THE DEMO DEPLOYMENT, MERGED as PR #61, and THE PRODUCT IS LIVE AND ANSWERING at https://search-agent-web-production.up.railway.app. Measured on the deployed API rather than asserted: a grounded answer with five citations in 15.8 seconds. What shipped: the Railway project with two services and the Postgres and Redis addons, 20 variables mapped from Section 24's table, the Layer 1 cutover (visible as an ABSENCE, since no `GRAPH_PG_*` is set), the Caddyfile `X-Forwarded-For` fix closing F-4.11-RV-02 on build phase 4.11's own stated condition, the Caddyfile brought inside `check_drift.sh`'s reach, and the eight stale tunnel gates retired onto one shared probe. THE STANDING SIX-FAILURE SUITE BASELINE IS GONE and was never six broken tests: all six sat in one file, all six pass under `RUN_PREMISE_GATE=1`, and the file FAILED where it should have SKIPPED because its mark gated on a credential EXISTING rather than on outbound HTTP being PERMITTED. FIVE DEFECTS had to be fixed before the demo answered at all, every one found by RUNNING it: no database schema, missing environment variables (found by DIFFING `env.example` against the service rather than one 500 at a time), an unset `ANON_DAILY_RUN_CAP`, the plan step timing out on every query, and an alias-ambiguous symbol refused as unknown. THE MOST TRANSFERABLE RESULT IS NOT THE DEPLOYMENT: a green status field is not evidence. `Online` was true of a service running a second copy of the wrong application, and three separate "the fix did not work" readings were really "the config was never applied", because Railway snapshots a start command on first deploy and `railway logs --build` lags the newest deployment. The phase also CAUSED a regression while fixing its own scope, then fixed the CATEGORY rather than the instance: correcting the tunnel probe made it answer truthfully, so arms that had been silently skipping began to RUN offline and FAIL, and the fix requires BOTH facts, that the dependency answers and that this process may talk to it. It merged with six UI defects open, recorded in the product owner's own words, and one production-only symbol refusal recorded as an unproven HYPOTHESIS rather than a finding, because its traceback could not be read. Build phase 4.14, CI, was inserted the same day: CD now auto-deploys a merge to a public URL and nothing runs the 3930-test suite on a pull request. Full record: `tracker/phase_4.12.md`.
- 2026-08-24: BOTH of build phase 4.7's open criticals CLOSED, on their own branches with triggers exactly as that phase filed them, `develop` at 4b7e4fc. Merged in order: PR #59 (`fix/a02-discontinued-gene-record`), then PR #60 (`fix/a01-injection-guardrail`), the second merging `develop` in first to resolve a conflict that existed only in three documents' test-count lines. No source or test file conflicted; the two fixes touch disjoint code. Both were HARD BLOCKERS on build phase 4.12 before any public URL, so 4.12 is now unblocked apart from the security scan it already owns and the product owner's own Railway provisioning.

  What PR #59 fixed: a gene symbol resolving to a discontinued NCBI record (`status=1`) contributed a CURIE, so "Which diseases are associated with BRCA3?" answered "The knowledge graph search returned a gene record for BRCA2 [1]" with `trust_outcome: answer`, `grounded: true`, a real citation and no disclosure. A withdrawn record now contributes NO CURIE, so no answer about a substituted gene is REACHABLE, and the refusal names the successor. Product-owner decision over refusing silently or answering with a disclosure, both logged in `DECISIONS.md`.

  What PR #60 fixed: a plain-English parenthetical, no tags and no operator framing, chose which gene the retrieval ran on. The primary control is now DETERMINISTIC, in `guardrail/prefilter.py` ahead of any model call, and NOT in the Guard-tier prompt, because that prompt already carried the abstract rule in almost the finding's own words and admitted the payload 6 of 6 anyway. Two patterns, each with a discriminator chosen for precision rather than coverage: the colon on a forged processing header, and the underscore on this system's own control vocabulary. It also closes F-4.7-A-05's `guardrail/classifier.py` half with a per-request unforgeable query tag.

  Verified, measured rather than asserted: premise gates 12 of 12 and 24 of 24 live with none skipped; mutation harnesses 15 of 15 and 16 of 16; Guard-tier admission for the three injection payloads fell from the adversary's measured 12/18 to 0/18; suite `6 failed, 3887 passed, 152 skipped, 1 xfailed` against a baseline RE-MEASURED in a throwaway worktree at `4d759da` (`6 failed, 3826 passed`), the same six pre-existing failures; `ruff` clean; drift 0 stale 0 structural. End to end and live: the injection payload is refused as `injection` at $0.00 with NO model call reached, BRCA3 refuses naming `NCBIGene:675`, and both controls still answer normally.

  WHAT THESE TWO COST, and it is the reason to read `LEARNINGS.md`'s 2026-08-24 entries before opening 4.12. First, A TICKET'S STATED PREMISE IS AN ASSEMBLY STEP: the board and the adversary report agreed with each other that the F-4.7-A-02 fix was single-site because `status` and `currentid` were already in the response the resolver retrieves, and both were wrong, because the `summary` action's allowlist stripped both fields. A fix written on that premise would have read `None` for every gene and refused nothing while looking correct. It was caught by calling the real tool and printing the fields before writing any code, which took one command. Second, A MUTATION THAT FINDS NOTHING IS EVIDENCE ABOUT THE GATE: the one mutation that produced no red arm anywhere had found a hole in the gate's own control set, not proof the control was unnecessary, and three questions were added to close it. Third, FOUR mutations across the two branches did not actually mutate, each surfacing as pytest's "DID NOT RAISE", which is indistinguishable from a control that failed to break; every mutation now carries its own populate-check.

  Also recorded rather than left to be rediscovered: the suite's standing 6-failure baseline is not six broken tests. All six are build phase 3.4's citation-trust premise gate, and all six PASS under `RUN_PREMISE_GATE=1` (verified 2026-08-24, `8 passed, 2 skipped`). That file FAILS where it should SKIP in the offline unit run, which is the same defect as the seven pre-4.11 gates that skip with a false reason, in the other direction. Carried to build phase 4.12, which already owns that class.

- 2026-08-23, last of the day: the board's flag reporting MERGED as PR #58, `develop` at 564995e. Prompted by a product-owner question rather than by a review round, and the question was the finding: "83 open flags and they keep increasing, are those features to be worked on?" They were not. The flags table is a LEDGER, not a queue, so a closed finding keeps its row and the total only ever grows, and 26 of the 83 were already closed. Nothing was broken; a ledger was wearing a queue's labels in three places. The summary now reads `flags: 57 open, 26 closed`, the stat tile counts open rows only, and the column is "Owner, or how it closed" rather than "Resolve before". Reconciliation is deliberately unchanged and still counts every row, since a flag named on a phase must have exactly one row whether open or closed. THE LOAD-BEARING DETAIL: the classifier anchors with `match` rather than `search`, because live rows say "Not closed until build phase 6.0 revisits it" and others describe how a RELATED finding closed. Measured, not assumed: a substring test moves the split to 54 open / 29 closed, hiding three live findings behind a done count, and that error direction is asymmetric because nothing prompts a re-read of a row already reported finished. Added `tests/tracker/`, the first tests for `tracker/`, pinning both traps and mutation-proven: flipping to `search` turns exactly those two arms red. Its live-board arm carries a populate-check asserting both groups are non-empty, since a classifier returning False for everything would leave every other arm green and silently restore the number the change removed.

- 2026-08-23, later the same day: post-merge cleanup MERGED as PR #57, `develop` at 08c0ea5. Three things, and the first is the only one with a general lesson. `EVALUATION_BOUNDARY.md` moved to `requirements/Evaluation_boundary.md` beside the playbook it partners with, but the location was the smaller half of the problem: a search found ZERO inbound references anywhere in the repository, so a document whose own stated purpose is "a form that can be linked rather than remembered" was reachable from nothing. Three inbound links were added in the same change, from the playbook, `README.md` and the `eval-harness` skill, and that is the half that matters. F-4.7-04, the 1-in-32 flake in `test_persona.py`, was FIXED rather than carried, and its lesson is kept in the file: the unstable line was the arm's OWN anti-vacuity check, comparing against a random uuid over a 32-element codomain, so a populate-check written that way trades one failure mode for another and must be deterministic. And four carried ownership calls were settled, recorded in `DECISIONS.md`. Branched rather than pushed direct because it touches `.claude/`, which `git-workflow` requires a branch and MR for regardless of phase.

- 2026-08-23: build phase 4.7, competency-question routing, MERGED as PR #56, `develop` at 6a6d60c, phase branch deleted, both builder worktrees removed. It is `think_node`'s real home, and it closes F-2.0-15, the finding that survived twelve phases and two weeks of green premise gates with an owner field reading "unassigned".

  What shipped: real query-shape classification into Section 17's five shapes via a Plan-tier call whose response is READ rather than discarded; real entity resolution in Section 17's exact-ID-first order, deterministic pre-pass then typed model extraction that must be live-confirmed before contributing a CURIE; the few-shot pool seeded with the seven must-pass moat questions, loaded once at process start into the stable prefix; and the removal of `plan_node`'s capitalized-token gene guess and its hand-maintained stopword list with NO fallback. Closes F-4.6-A-08, and DISSOLVES F-3.1-41 and F-3.1-42 rather than deciding them, since both were questions about how to tune a list that no longer exists.

  Measured, not asserted: live premise gate `16 passed in 370.86s` with none skipped and none open; suite `6 failed, 3813 passed, 146 skipped, 1 xfailed`, the six being the identical pre-existing `test_citation_trust_full_premise.py` arms from a baseline re-measured at this branch point rather than carried forward; `ruff check src/` clean; `check_doc_drift.py --check` 10 facts, 0 stale, 0 structural; concurrency proven by 8 processes by 6 appends run twice, 0 lost of 96 across 239,899 concurrent reads.

  What the review cost: FOUR rounds against a two-round cap, one Rule 4 stop, and THREE separate product-owner escalations, each taken through the escalation the cap exists to force rather than by the lead.

  THE MOST TRANSFERABLE RESULT IS NOT THE FEATURE. This phase produced THREE separate vacuous-gate-arm findings, every one written by the lead, in a file whose own docstring quotes build phase 4.11's lesson against writing them. Three of the flagship arm's four cases asserted a token absent from the question, so they could not fail. The repair for that then SURVIVED ITS OWN FIX, because the populate-check added to make the defect mechanical verified that the token was in the question and said nothing about the codomain of the value being asserted on, which is the same safety-by-proxy shape build phase 4.3 shipped twice three rounds apart. Reading an assertion has now been demonstrated three times in one phase not to be a method for validating it, and only mutation has ever caught these. So the durable output is a permanent offline mutation harness, 43 cases over 11 of 13 arms, which breaks each control and asserts the arm goes red. Vacuity is now a build failure rather than a review finding, verified by making an arm vacuous and observing 20 of 43 cases turn red.

  Two criticals merge OPEN, each on a dedicated branch with a trigger rather than a phase number, and both hard blockers on build phase 4.12 before any public URL exists: a crafted plain-English parenthetical can still steer which gene the agent looks up, which is Guard-tier injection classification failing and therefore build phase 3.0's control rather than this phase's code, and a retired gene name is answered as its replacement with no disclosure, which was established as PRE-EXISTING by the retired regex matching it, rather than counted against this phase. A third critical, a question naming a non-human organism silently answered about the human gene, WAS caused here and was fixed here, because the retired regex could not match a mixed-case symbol so the old code refused honestly and this phase converted that refusal into a confident, fully cited wrong answer.

  Full record: `tracker/phase_4.7.md` (16 findings), `tracker/phase_4.7_judge_report.md`, `_adversary_report.md`, `_reverify_report.md`.

- 2026-08-22: build phase 4.11, the read-only HTTPS graph query service, MERGED as PR #55, `develop` at 13f6e81.

  What shipped, per Section 24, which specifies the service in full: one authenticated HTTPS endpoint co-located on the Hetzner CPX42 box in front of the AGE graph, behind Caddy with a Let's Encrypt certificate on the box's reverse-DNS hostname, running as a systemd unit under its own non-login user with the systemd hardening Section 24 implies. The client half is a transport swap INSIDE `graph_connection.execute_cypher`, dispatching on `GRAPH_QUERY_URL`, leaving `cypher_query`'s schema and all three of its call sites unchanged, which demonstrates Decision D's two-way door rather than asserting it. Server-side re-validation reuses this repository's own `validate_cypher` and `execute_cypher`, copied to the box by the deploy script and asserted byte-identical by `check_drift.sh`, so the two validators cannot drift apart. Three budget controls per `.claude/rules/tool-call-budgets.md`: a hard row limit, a per-call timeout matching Section 6.1's 30 seconds, and rate limits both per caller and per source.

  What it deletes, and this is why it jumped the queue: the hand-opened SSH tunnel that had gated every live test in this repository since build phase 2.1. Verified rather than claimed, 59 of 59 live premise arms pass against the deployed service with no tunnel open anywhere, and `tracker/preflight.py` reports `graph ok, HTTPS query service` where it previously reported a refused socket. Build phase 4.6 had measured that tunnel failing twice in one week and merged with three live arms unrun.

  It also closes a dangling reference between two locked sections. Section 24 said `GRAPH_QUERY_TOKEN` is populated "when the service is built (Section 25 build order)" and Section 25 never assigned it to any phase.

  What it cost, and the review is the transferable part. FOUR rounds against a two-round cap, 26 findings, THREE separate Rule 4 stops, each escalated to the product owner rather than decided by the lead. What justified continuing past the cap was that the findings changed in KIND each round: round 1 found two reachable majors in the original code, round 2's review found an unbounded resource inside round 1's fix, round 3's found a diagnostic regression and a CPU cost inside round 2's fix. Severity fell monotonically, and that, rather than the round number, is the stopping rule that actually applied.

  The round 1 headline: the endpoint was `async` and called blocking psycopg2 directly, so one legal slow query serialised every caller and stalled the unauthenticated health endpoint, measured at 10.97 seconds while a 12 second query was in flight. Because `tracker/preflight.py` reads that endpoint to decide whether the graph is up, the service reported the graph DOWN during any slow query, which is the exact failure the phase was pulled forward to delete. It is build phase 2.1's already-fixed event-loop defect resurfacing one layer down, in code whose gate named concurrency as a stated omission.

  THE MOST TRANSFERABLE RESULT: the lead wrote THREE VACUOUS GATE ARMS in this phase, and all three were caught by a mutation run and NONE by reading. One was vacuous twice in two different ways, while quoting the lesson against vacuous arms in its own docstring, which is direct evidence that knowing a failure mode by name does not prevent committing it. The durable fix generalises past this phase and is now applied to every bound arm: the populate-check, an assertion that the arm produced the state it is about to measure, because otherwise every way the setup can silently fail reads as the control working perfectly. The single arm that carried that self-check from the start was never vacuous.

  Round 4 was run GATE FIRST by product-owner decision, arms written and watched failing before the fixes they grade. In one round the ordering caught the real defect, caught TWO WRONG PREMISES IN THE LEAD'S OWN ARMS, and caught a tension introduced minutes earlier where amortising a sweep also deferred the cap inside it. Two of the three findings the round set out to fix turned out to be gate gaps over already-correct code, so acting on the review report alone would have meant changing working code.

  One process failure is recorded rather than quietly dropped: a wrong blocker was reported to the product owner and a Hetzner API credential requested to open firewall ports that were never closed. This harness renders "nothing listening" and "filtered" identically, as an eight second timeout, and the control probe that made the inference feel safe only exercised destinations that had listeners. A control that can only come back green is not a control. The credential was never used and was revoked. The same ambiguity had already been written into the phase's own premise gate, where the arm asserting the database port stays closed would have passed with that port wide open.


- 2026-08-21: build phase 4.6, feedback capture, MERGED as PR #54, `develop` at 108e19d.

  What shipped, per Section 25's line and Section 16's v1 scope of stages 1, 3 and 5: interaction capture writing exactly one `interactions` row per completed query on every surface and at all four trust outcomes, attributed to the namespaced principal rather than to `user_id`; a deterministic rubric outcome computed with zero model calls; coverage tags, the `concept:` half only; an owner-scoped idempotent writer; dispatch from the run epilogue; a feedback endpoint and the frontend control build phase 4.8 left stubbed; the weekly human-gated review ritual and few-shot promotion as real scripts; and a runbook. It closes F-2.0-04 and F-2.0-10, and takes F-4.10-A-14 and F-4.1-A-15 with it. The two daily caps that had read an always-empty table since build phase 2.0 can finally fire.

  What it cost, and this is the part worth carrying forward. THREE review rounds against a two-round budget, thirty findings, two criticals both reachable in the shipped product, one Rule 4 stop, one rejected ticket, and one reverted fix.

  - BOTH CRITICALS DEFEATED THE DAILY CAPS, which is the exact capability this phase existed to deliver. One NUL byte appended to a question, or simply pressing Stop, made a query free and uncounted: twelve queries against a cap of three, twelve answers, zero refusals. Neither underlying control was wrong. Section 16 requires capture to be best-effort and never block an answer a user already received; the caps count captured rows. Composed, anything that prevents a row raises that caller's cap to infinity. The fix agent rejected both principles the lead offered and chose a better one: a caller's own input must never be able to decide whether their query is counted, which splits capture's failures by who controls them rather than by severity.
  - ONE TICKET WAS REJECTED BECAUSE ITS PREMISE WAS FALSE. T-4.6-02 asked for a server-minted `trace_id` per Section 20.1. Every callable surface already minted one and had since build phase 1.2, and `CreateRunRequest` forbids extra fields so a caller cannot supply one at all. Building it produced a second mint that broke Section 13.1's "same identifier under two names" and forced a builder to rewrite a test that was correctly encoding the spec. The locked specification contradicts itself here, filed as F-4.6-07 for reconciliation.
  - ONE FIX WAS REVERTED BY PRODUCT-OWNER DECISION. F-4.6-04 added a field to `CitationPayload` to make predicate coverage tags derivable, broke build phase 4.1's blocking MCP premise gate in two arms, and bypassed `_ALLOWED_RESPONSE_KEYS`, the hand-maintained anti-leak allowlist that both prior widenings updated only with explicit approval. A finding inside the phase's own fix is a Rule 4 stop, and the judge showed the feature had zero verification anywhere. Reverted; coverage tags ship with the `concept:` half only and the known-bad prose heuristic was NOT restored.
  - FOUR DEFECTS WERE FOUND IN THE LEAD'S OWN PREMISE GATE. Three vacuous arms in three distinct shapes: one that grepped its own assertions and so could never fail, one naming an ON CONFLICT control that three separate layers masked, and one that declared its control and never installed it. The fourth is sharper because the arm is not vacuous at all: it plants a secret in the environment and greps every column, which tests whether the assembler leaks configuration, when the likely source is a user pasting a credential into the question they are asking about. That forced a correction to the phase's own goal contract, whose constraint "no column ever holds a secret" is false and cannot be made true while Section 16 requires `query_text` be captured.
  - THE ROUND-2 BLOCKER WAS A ROUND-1 FINDING NOBODY OWNED. Control characters in a question forged the weekly reviewer's terminal. The adversary filed it in round 1 with a reachability argument; the lead acted on the adversary's two criticals through agent briefs and never entered ANY of its fifteen findings in the ledger, so nine had no severity and no owner. It surfaced in round 2 as the single blocker, stopped the phase, and cost an authorised third round. Filed as R-01 and transcribed. Acting on a finding is not recording it.

  Measurement notes, both instructive. The suite baseline was re-measured rather than carried forward, per build phase 4.4's lesson, and the first two attempts were both wrong: a single-file comparison against a full-suite result, and then a full-suite baseline contaminated by this phase's own migration, which stamped the shared development database at a revision no earlier commit can resolve and produced 25 phantom errors pointing in the direction of a regression. A phase that adds a migration silently destroys its own ability to re-measure a baseline. Final: 6 failed, 3626 passed, 130 skipped, 1 xfailed, the 6 pre-existing. Separately, `tracker/check_learnings_coverage.py` returned a false pass against a ledger of thirty findings, because it parses for states this ledger does not use.

  Not verified: the three live premise arms, the graph tunnel being down. They are unverified rather than passed. Two product-owner decisions remain open, durable cross-reload history and the Section 20.1 versus 13.1 contradiction. Full record: `tracker/phase_4.6.md` and the three review reports beside it.

- 2026-08-21: build phase 4.5's independent review, and the fixes it produced, merged as PR #53. This is the round build phase 4.5 shipped without, run after the fact against the merged code, and it is now the reference case in this repository for why the maker-checker split in `.claude/rules/self-eval-loop.md` is not optional.

  Why it ran at all: PR #52 completed stages 1 to 7 and 10 of the cadence. Stages 8 and 9, the judge round and the adversary round, did not, so every fix and every test on that branch was written by the same agent that wrote the code. That mattered more than usual, since two criticals had already surfaced in the phase after the work looked finished.

  What the two rounds returned: 22 judge findings (2 critical, 11 major, 7 minor, 2 latent) in `tracker/phase_4.5_judge_report.md`, and 26 adversary findings (3 critical, 9 major, 11 minor, 3 latent, 19 of them established by executing code) in `tracker/phase_4.5_adversary_report.md`. Roughly 35 unique after overlap. They ran with separate briefs and separate contexts and converged independently on the same three worst defects, which is the strongest verification signal available short of a live exploit.

  The two criticals, both checked by the lead rather than accepted on an agent's report:

  - Session memory defeated the unresolved-entity refusal. An `elif` let a remembered CURIE win whenever the current turn named a gene that does not resolve, so a question about a mistyped symbol was answered about a DIFFERENT gene: grounded, correctly cited, terminal outcome `answer`, with nothing saying the question had been substituted. Mistyped and obsolete gene symbols are the single most common thing a user gets wrong in this domain, and that refusal exists for exactly them. It is now an early return, placed before any memory consideration, because a control that must hold whatever else is true does not belong in a chain where a later reader can add one more branch above it.
  - Every guest shared one ownership identity. `(owner_id or None) != (user_id or None)` is False for every guest pair, because `user_id` is NULL for a caller with no account, so any anonymous caller could read and overwrite any other guest's session memory. Reachable without guessing a UUID, since `--session-id` is a documented CLI flag and the other surfaces accept any string. The distinguishing identity already existed and was handed to `create_run` on the line after the Query was built; it simply was not the field the check read. Isolation is now by owner-scoped row key rather than by comparison, so a second guest reaches its own row instead of being refused at someone else's, which also closes the oracle a refusal message would have opened.

  The third finding was the gate itself. It ran `1 failed, 1 passed, 14 skipped in 0.06s`, meaning most of it did not run in ordinary CI at all, and it now runs `12 passed, 6 skipped`, with the six that skip being exactly the six that drive the real loop. Four arms were rebuilt rather than repaired: one asserted a constant equalled itself, two were held up by build phase 2.2's grounding pass rather than by anything build phase 4.5 built, and one could not tell the real tokenizer from a character count. A fifth arm is new, since the prompt-cache criterion had a depth half and no session-memory half.

  A finding this round filed and then WITHDREW, kept in the record rather than quietly dropped, because the failure is more useful than the finding was. A blocking regression was reported on 2026-08-20 claiming the fix for the completeness repair's budget had starved it, on a twelve-run live measurement showing its second Synth call finishing 7 of 7 times before and 1 of 7 after. It was withdrawn on 2026-08-21. There was no regression: the repair runs with 29 to 43 seconds of its 45-second budget spare. The instrument counted calls to `unreported_findings`, and the strict-superset fix short-circuits that call when a regeneration grounds nothing, where the previous code always made it, so the measurement recorded a change in how often a function is CALLED and reported it as a change in what the product DOES. Two narrower probes had already disagreed on an identical tree, with `git log` showing no Write-path change between them, and that was the moment to suspect the instrument rather than the code.

  Two results from that measurement do stand. Both review rounds derived the repair's firing rate arithmetically from the shipped prompt, reasoning that a two-to-five-sentence instruction cannot ground up to twenty findings; only 0 or 1 findings ever reach synthesis, so the conclusion was right and the reasoning that produced it was not. And the first answer grounds nothing against its single finding in roughly half of live runs, at both commits, which is a retrieval and synthesis quality question for the eval harness at build phase 5.1 rather than a defect this branch introduced.

  Also in the round: the eleven-CURIE crash that made a long session permanently unanswerable, a pronoun binding to every entity a session had ever resolved rather than to one antecedent, the completeness repair accepting a regeneration on a smaller omission count rather than a strict superset, retrieved Layer 1 values sitting in instruction position, `merge_turn` losing idempotence at the first compaction, a token budget accepting 8000 against a hard cap of 1500, a persona draw that would have reassigned every existing user on any list extension, four surfaces disagreeing about the persona with the frontend racing two of them, MCP gaining the persona it never had, and audience depth being resolved by the web client only. `tracker/preflight.py` was also corrected to load `.env`, so the graph transport is actually verified rather than reported `skipped` while the run prints READY; it caught a real dropped tunnel the same day.

  Gates: 3449 Python passing with 6 failing, shown to be pre-existing by running that same file at the pre-branch commit with the same environment and getting an identical result; 188 frontend passing; `ruff check src/` clean; doc drift clean. The live premise-gate arms did NOT run, because the graph transport was down, and the pull request says so rather than implying a green board.

  A new `/standup` skill merged in the same pull request, called out separately there so a `.claude/` change is not skimmed past inside a large defect diff. NEXT: build phase 4.6, feedback capture, which must read `core/session_memory.py` before writing `interactions.session_id`, since it inherits both the ownership model and the uuid5 row mapping this round changed.

- 2026-08-20: build phase 4.5, personalization and session memory, merged as PR #52. The sixth of the six delivery-surface-group phases to close, and the first to merge WITHOUT a judge or adversary round.

  What shipped, per Section 14 in full: bounded in-conversation session memory (the `SessionMemorySummary` contract, a token cap counted with the receiving tier's real tokenizer, compaction in Section 14.3's exact order, injection into Think and Plan only, and per-session persistence via alembic revision 0007, verified up and down against the live user database); audience-level depth control, which finally reaches synthesis after riding the contract unused since build phase 1.0; and the stable named scientist persona, 32 curated names in a versioned data file wired to all four surfaces from one source.

  Three long-open findings closed: F-4.1-A-15 (a caller-supplied `session_id` unbound to its owner, boarded at build phase 4.1 and deferred to whichever phase first read that field), F-4.8-A-22 (the unresolvable follow-up pronoun), and F-4.2-03 (the CLI persona prefix, open since build phase 4.2 because no event carried a name to prefix with).

  What needed a decision and what did not. The continuation prompt named three things as requiring the product owner. Two were already specified in the locked technical specification: Section 14.3 gives the memory bound in full and Section 14.5 gives the depth levels. Only the persona list was genuinely open, and both halves of it were settled and logged: roughly 30 names with the mechanism sized for 100, and deceased scientists only, because a living scientist's name rendered above a generated biomedical answer reads as an endorsement they never gave. Reading the locked documents before asking turned three questions into one.

  What the phase cost, and the reason to read `tracker/phase_4.5.md` before building anything with a premise gate. Ten findings were filed, three of them defects in the gate itself and one in the harness. Two were CRITICAL, both in the lead's own code, and both surfaced after the work looked finished:

  - F-4.5-06, caught by the premise gate on the first real implementation. The `clinical_brief` directive told the model not to print identifiers in prose. Build phase 2.2's grounding pass accepts a claim only when it substring-matches its finding, and a Layer 1 finding's value IS the identifier, so a PRESENTATION instruction made that depth refuse outright while `researcher` answered from identical findings. Four directive versions were needed, each breaking the answer a different way, before the rule emerged: depth may change register and length, never which tokens may appear.
  - F-4.5-09, caught by nothing. The read side of session memory shipped complete and correct and NOTHING EVER WROTE A SUMMARY, so the feature was inert on the real path while eight gate arms passed. Every one of those arms hands the memory in on `RequestContext`, so all of them are structurally blind to whether anything produces one. This is build phase 4.4's lesson in a new costume, committed while quoting it in the gate's own coverage note: there five of six cases passed an explicit edge-label list, here the injected fixture was the explicit list. Found by asking what populates memory, not by a test.

  Evidence at close: premise gate 15 passed and 1 xfailed, full backend suite 3408 passed with 10 failures, all of them the recorded pre-existing baseline (seven in `test_citation_trust_full_premise.py`, three in `test_cypher_query_e2e.py`), frontend 181, typecheck clean, alembic 0007 up and down against the live database. Three suspected regressions were investigated rather than assumed and all three proved to be flakes, one of them by running the offline eval gate at the pre-phase commit in a throwaway worktree and finding it passed there too.

  What this phase did NOT get, stated because it is the first phase in this build to merge without it: stages 8 and 9 never ran. There was no judge round and no adversary round, and every fix and every test on the branch was written by the same agent that wrote the code. That matters more here than it would elsewhere, because two criticals surfaced after the phase looked complete, which is the argument for independent review rather than against it. The change most in need of it is the completeness repair in `core/graph.py`'s `write_node`: it sits on the most safety-critical path in the product and fires a second Synth call when an answer omits a finding.

- 2026-08-19: build phase 4.4, the KGX export, merged as PR #51. The fifth of the six delivery surfaces, and the first phase to run under the review cap introduced the day before.

  What shipped: a query-scoped subgraph export. Seed CURIEs, bounded hops over Layer 1 through the existing read-only path, writing `nodes.tsv`, `edges.tsv` and a manifest. Not a full-graph snapshot, which the merge pipeline in the data-engineering repository already produces at roughly 144 GB.

  Two things had to be decided before any code, and both went to the product owner. Section 25 and the PRD scope this phase only negatively, so its shape was genuinely undecided at open rather than merely unwritten. And the deliverable was forbidden outright by the `file-protection` rule's ban on KGX exporters, so the rule was amended by direction of data flow rather than crossed silently: writing KGX into the graph is still Systems 1 and 2 and still banned here, while reading a scoped subgraph out is a delivery surface.

  The phase's central result, and the reason it is worth reading rather than summarizing. The adversary found a CRITICAL the premise gate could not see: the default invocation, with no edge-label list, spent its whole node budget on the highest-cardinality edge label and returned 500 Articles and ZERO of the twelve disease edges the gate itself pinned as ground truth, with a manifest certifying it had traversed all fourteen labels. Five of the gate's six cases passed an explicit single-label list, so none of them touched the default path, and the gate's own coverage statement had NAMED that omission from the day it was written. Writing a blind spot down makes it arguable; it does not make it safe. A stated omission covering the DEFAULT path is not an omission, it is a hole. Fixed by giving every work item an equal quota before any item gets a second helping, never by reordering the label list or special-casing the offending label, and pinned by two new gate cases both seen failing first.

  What review cost: three rounds against a budget of two. Round 1 returned judge FAIL with three blocking majors and twelve adversary findings including the critical, the two converging on the same central defect from different angles. Round 2 fixed six defect categories, split by file so no agent was blind to a sibling editing the same function, and disputed two findings with reasoning rather than complying; both disputes were upheld by the lead. Round 3 was authorized by the product owner, scoped to the output-directory category alone: a bundle now lands whole or not at all, published by a single atomic rename, with the destination validated before the traversal is paid for.

  The cap worked as designed. It did not prevent a third round; it prevented the lead from taking one unilaterally, which is the failure mode build phase 4.3's six rounds demonstrated.

  Release gate: premise gate 8 of 8 live against the real graph with zero skips and the gate file unmodified across all three rounds, export suite 176 passed, full Python suite 3404 passed with 10 failures, `ruff check src/` clean, doc drift 0 stale 0 structural, board renders. All 10 suite failures were proven pre-existing by re-running both affected files at commit `4d067d0`, before the phase opened, in a throwaway worktree, which produced the identical sets. That check also caught a documentation defect worth more than the phase: the recorded baseline said 6 known failures when the real figure was 10, and had been wrong for some time. A baseline nobody re-measures is where a real regression hides.

  Two findings carried forward with owners: the console script cannot be verified end to end until `pip install .` is fixed (build phase 6.1, shared with build phase 4.2's `s3`), and the export CLI classifies an input problem by catching `ValueError`, a proxy rather than a declaration, verified latent today.

  Nine `LEARNINGS.md` entries were written from this phase. Appending them also surfaced that three build phase 4.3 rows had been stranded outside the Lessons table since 2026-08-17, rendering as loose text and invisible to anyone scanning it; they were moved back verbatim.

- 2026-08-18: two harness changes and one new phase, all from the product owner's observation that a build day runs long and still does not land well.

  Capped the review loop, after establishing where the day actually goes. Across build phases 2.1 (five rounds) and 4.2 (six rounds), every round found its worst defect inside the previous round's fix, and five rounds of rising scrutiny did not lower the recurrence rate, so the loop was not a scrutiny problem. The measured cause is in `LEARNINGS.md` for 2026-08-16: a parallel fix agent is individually correct and structurally blind to the sibling editing the same function, so two correct fixes compose into a defect no reviewer of either one can see. Build phase 4.2's round 5, run deliberately as one agent holding every finding at once, closed its assigned findings and found a sixth defect on a fallback path four parallel rounds had walked past. `bossman-mode` now carries four rules: fan out on files but go serial on findings inside one file, fix by category rather than by enumerating instances, stop after two rounds and hand the product owner a written decision instead of opening a third, and stop mid-round the moment a finding sits inside an earlier fix. `task-tracker` gained the two ledger fields those rules need, `Round` and `Regression of`, without which the round count could only be reconstructed by counting report files afterwards, which is how 4.2 reached six before the shape was noticed.

  Deleted rather than added, per this repository's own `attack-the-constraint` order. Growth-path levels 3 and 4 described multi-phase autonomy and simultaneous teams that nobody had asked for and nothing had scheduled; the three-session provider-split table collapsed to two sentences. Level 2 stays, because it carries a real dated deferral. Also corrected the one principle that contradicted the measurement: "workers do not coordinate with each other" is right for disjoint files and wrong for a shared seam, and builders now read the board's Findings section before starting and before reporting, since isolation is about write access and never about awareness.

  Opened Phase 8, NCBI infrastructure migration, as a parking list rather than a schedule. Step 1.8's build-first-then-migrate decision has been carried in Phase 1's synthesis and in Section 25's fast-follow triggers since July, but it was never a phase here, so the work it implies was being remembered in conversation. It now holds six items, three named by the product owner (adopt the NCBI or NWS design system, migrate to P2, move under the NWS experimental repository) and three that already existed as fast-follow rows and are listed for completeness. Everything in it blocks on one event, the move to an NCBI Linux machine. Confirmed the same day that the NCBI design system is reachable only from NCBI infrastructure, which settles it as post-migration work and means nothing changes in `frontend/` now. Recorded the reason not to adopt it early: hand-copying values across would create a second unmirrored token source, the exact failure `LEARNINGS.md` records for 2026-08-14.

  Built the transport preflight, closing the priority-1 recommendation that had been open in `docs/build/Build_velocity_post_mortem.md` since 2026-08-03. `tracker/preflight.py` probes one endpoint per transport before anything expensive is dispatched and exits 1 when one is down. The reason it is one probe per transport rather than one probe is that the version shipped at build phase 3.0 probed the product's model provider, returned 200, and two researcher agents dispatched on that evidence died anyway against the harness's own provider, one closing mid-response and one stalling for 600 seconds. That second probe existed nowhere in the repository until now, and it gates the more expensive failure mode at 15 to 25 minutes per dead dispatch against 6 to 10 for a premise-gate run. The graph is a third transport, since a tool-phase gate dies against it the same way. Wired into `bossman-mode` Step 1 and stage 4 of the cadence, with a re-probe before any review-agent dispatch. It was mutation-tested rather than trusted for being green: four arms driven deliberately, including a blackholed address bounded at 3.09 seconds against a 3-second timeout, which is the stall class from the original incident. 344 decisions logged.

  Also settled that the new `/design` canvas skill is not adopted. This repository already has a working design-to-code chain, a Claude Design project mirrored through `DesignSync` into 21 component cards that the premise gates assert against. The canvas produces `.dc.html` artboards with no code-facing contract and no path back into `frontend/`, so introducing it would add a second design source that no gate checks.

- 2026-08-14: the design-system contrast and focus-nesting pass, merged as PR #45. Three times across two build phases a token or markup pattern taken faithfully from the approved design had failed WCAG 2.1 AA, so the code deviated, filed it, and worked around it at one call site. An axe sweep over all 21 design-system cards found seven violations, FOUR OF THE SIX contrast failures being a single token: `--ok` #2E8540 passes on white at 4.62 and fails on `surfaceSunk` (4.35) and `--l2-wash` (4.01). Moved to #276E34 at source, which cleared all four and turned two code deviations back into transcriptions. It also found a card that contradicts the prototype (depth-control drops the label's colour scoping, giving 1.54:1), which matters because this repository's own workflow has builders build against the cards. `e2e/design-system-audit.spec.ts` now holds the design system to the same bar as the app, with a coverage statement naming what it cannot see: the prototype card renders one screen and its other six are hidden. Its own first version could not fail, asserting nothing and only writing a JSON report; a mutation caught that, and the cause was a silent no-op replace.

- 2026-08-17: build phase 4.3 (the GraphQL surface via Strawberry) completed and merged as PR #48. A typed request/response surface at `/graphql`, served from the same FastAPI process, sharing the REST surface's auth and tools: four operations over the one agent core, wrapping it rather than exposing the seven tools, registered accounts only, no live stream. The locked spec names this surface and then explicitly declines to specify it, so three scope readings were recorded before any code: "shared tools" means through the one core (Section 13.2 had already ruled on that phrase for MCP), no guest path, and no subscriptions.

  SIX independent review rounds, every one returning FAIL, every one finding its worst defect inside the previous round's fix. This is build phase 4.2's measured pattern reproducing on a second phase. TWO CRITICALS, both in the same decision (may the caller see this exception?) and both with the same cause: the code answered it with a PROXY for safety rather than by checking the message text. The proxies were, in order, the package a class was declared in, its class family, and the phase the error came from; the first two each returned a live database DSN with credentials to a caller. The fourth attempt checks the text itself against shapes captured from the installed library, and a coverage arm now fails if any authored shape matches nothing.

  The phase did not converge until it was given a MERGE BAR, which it had run five rounds without: a critical or a REACHABLE major blocks, minors and latent findings are tracked with an owner. Five rounds had been briefed as "find anything", which on a surface this size always has an answer, so the loop had no terminating condition; a done-when had been written for the build and never for the review. The second change was applying the maker-checker split to FIXES rather than only to reviews: five of six fix rounds had been run by the lead, who then wrote the tests pinning them, and six of the phase's FOURTEEN vacuous gate arms came from that. The final round was fixed by a fresh agent with the lead verifying, and it closed both blockers, found a second half of one finding nobody had filed, and correctly disputed the review on a third.

  Release gate: 3308 Python tests (3188 passing, the same six live-network-gated cases carried since build phase 4.0), the GraphQL package alone 206 to 300, 181 frontend, ruff clean, doc drift 0 stale 0 structural. Five findings carried open with owners. Five decisions logged. Three LEARNINGS.md entries, which are the phase's most transferable output.

- 2026-08-16: build phase 4.2 (the CLI adapter) completed and merged as PR #47. `system3-cli`, command `s3`, with `ask`, `stop` and a `login` that is a documented substitution rather than an addition, since Section 13.3 assumed a pasteable API key and no API-key entity exists anywhere in this codebase. Six review rounds: a premise gate written first and watched failing, a judge round (FAIL, 10 findings), an adversary round (30 findings, 4 critical), an independent verification (DO NOT MERGE, 2 of 5 criticals still open), a Depth-tier regression review (FAIL, 3 critical), and a round-4 verification (FAIL, 1 critical). 56 findings, five critical, all closed and independently probed by the lead rather than accepted on report. Gates at merge: full suite 2871 passing with only the six known live-network cases failing, CLI suite 243, premise gate 28 of 28 with every clause mutation-proven, ruff clean, doc drift 0 stale and 0 structural. The phase closed a repo-wide flag it had itself made live: `F-3.4-A-06`, the unterminated citation URL pattern, had been correctly judged not exploitable for two phases because every surface rendered to a browser, and this phase built the first surface where the content is executed by a terminal instead. Two product decisions were escalated rather than settled in the phase, on Section 13.3 requirements the shipped contract cannot satisfy. THE TRANSFERABLE RESULT IS A PROCESS FINDING: five of the six rounds found their worst defect inside the previous round's fix, caused every time by parallel agents editing one file in one round, each individually correct and blind to the other; round 5 run deliberately as a single serial agent immediately found a sixth site that five parallel rounds had walked past. Fix rounds now partition by file and run serially within one, logged in `DECISIONS.md`. Full account: `tracker/phase_4.2.md`, plus the judge, adversary and re-review reports beside it.
- 2026-08-15: build phase 4.10 (the anonymous run path and the server-side guest allowance) completed and merged as PR #46. Split out of build phase 6.0 and pulled ahead of 4.2 to 4.7 by product-owner directive on 2026-08-14, because until it existed nobody could use the product without creating an account first. A visitor with no account now completes five real cited runs, counted server-side.

  Seven review rounds ran, four of them FAIL: a judge round, an adversary round, three fix rounds, a re-review and an independent verification. 30 findings closed, five critical. Every critical was a defect in the phase's own design or its premise gate rather than in a builder's code, and three of the five were introduced by the fix for the previous one.

  The sequence is the phase's real output, because each bound was defeated the same way. Bounding runs per principal fell to 40 mints at 157 paid pipelines per second, since minting a principal is free. A system-wide daily ceiling held the money but not the distribution. A per-identity attempt ceiling fell to 20 identities taking the whole day in 1.56 seconds. Only the fourth bound, a source's share of the day, is keyed on something minting does not increase: 20 identities or 200 buy the same 20 runs. Tightening the mint throttle instead was structurally closed off, since refusing 20 mints needs a limit below the 25 consecutive mints the gate's admit arm requires from one shared office address.

  Five transferable lessons, all measured, all in `LEARNINGS.md`:

  - A premise gate can be green while the property it claims is absent, and this phase produced five distinct instances: a clause whose asserted 401 came from the wrong code path, a clause masked by a second cap of the same numeric value, a clause hollowed out without being edited when the state the code reached before it changed, a clause importing the very constant it was meant to pin, and a mutation that did not fire and read exactly like a pass.
  - A lead's brief can be factually wrong and a builder will implement it faithfully. The worst finding traces to a cost claim asserted in a brief without being checked against `core/graph.py`, where a pre-filter refusal passes `charged=False` and makes no model call at all.
  - A real accepted risk can be used to wave through a much larger unaccepted one on the strength of the two sounding similar. The product owner accepted that clearing browser storage yields a fresh allowance; a code comment then used that to justify no mint throttle at all, and the two differ by 157 paid pipelines per second.
  - A control with no safe direction of failure needs both arms. The mint throttle's first version refused the gate's own admit arm, one screen below where that rule is written in the same file.
  - Verifying a property out of band is not the same as the gate verifying it. A builder proved the domain-separation property by hand with a real guest id and left the clause forging one for a random UUID; the clause is what ships.

  Release gate at close: Python 2747 collected with 2627 passing and the 6 known live-network-gated failures carried since build phase 4.0, this phase's own gate 36 of 36 with every clause mutation-proven, frontend 180, Playwright 30 of 30 including the full axe sweep, typecheck and production build clean, `ruff` at its 5 pre-existing errors, doc drift 0 stale and 0 structural, alembic revisions 0003 through 0006 each applied and rolled back against the live database. Five decisions logged. Ten findings carried with a named owner each, plus one accepted residual: a caller with genuinely many source addresses gets one share of the day per address and is bounded only by the day, which is the honest floor after four rounds. The money stays bounded by `ANON_DAILY_RUN_CAP` throughout and signed-in users are unaffected.

- 2026-08-14: build phase 4.9 (answer-screen and chrome fidelity) completed and merged as PR #44. Nine gaps against the approved prototype closed, plus the account menu: the nav order, the status strip with its outcome word and `Show work` disclosure, a reasoning log shared between the run screen and that disclosure, collapsible sources with a count, each source's layer named in words, citation chips carrying their source identity, the follow-up moved above the rating, and the trust pill stating a layer count.

  Four of the nine were found by screenshotting the running app beside the prototype in the same four states, a comparison never run before in this repository. It also found a live bug in the same pass, an anonymous visitor being shown the whole stored-searches rail.

  Three review rounds, all three FAIL, 47 findings, and the sequence is the lesson. The adversary found product-level lies: a fatally failed run rendered the backend's raw error text, cost figures included, directly under the pills "Grounded, every claim cited". The judge found the phase's own GATE could not fail: deleting the sources count badge left it green, because the assertion read the whole disclosure element and one source id contained the digit being matched, and sixteen of the lead's own mutations had missed it. The re-review found that THREE OF THE FOUR critical fixes were themselves wrong, which is the pattern this repository has now measured across five consecutive phases.

  All four criticals, all five re-review majors and both gate defects are closed. Every remaining finding carries a named owner in `tracker/phase_4.9.md`, including two that need a product decision rather than a fix: the source collapse put the off-host citation warning two disclosures deep, and a stopped run gives no terminal signal because the client aborts the stream before the backend's `cancelled` event can arrive.

  Gates: gate 21 of 21, 15 mutations all red, vitest 155, Playwright 30, typecheck clean, production build succeeds, doc drift clean.


- 2026-08-13, after the merge: a visual pass on `develop` found two major layout defects by starting the application and looking at it. Build phase 1.2's `#root { max-width: 720px }` scaffold had survived the restyle, so the whole redesigned application rendered in a 720px strip with the app bar's own wordmark wrapped onto three lines; and the provenance spine's segments and the prose ran as two independently laid out columns that drifted apart cumulatively, so by the third claim the grey uncited segment sat beside the wrong sentence. Both fixed with mutation-tested guards, commit `e08c656`. The generalization worth keeping: nothing in this repository looks at the rendered page, so both defects coexisted with 147 unit tests, 19 end-to-end tests, a clean production build and a full WCAG 2.1 AA pass. The phase's own premise gate had declared that gap in writing before either defect existed, and it predicted both.

- 2026-08-13: build phase 4.8 (Web UI visual design) completed and merged to `develop` as PR #41. MUI 9.3.1 adopted with exact pins and a theme generated from the design system's own tokens, which the premise gate asserts value by value. Every screen in the approved prototype built: landing, run, answer, sign-in wall, integrations, docs, about, plus the persona, the audience-depth control, the provenance spine, the feedback surface with its per-citation flag, follow-ups, the history rail and the disclaimer gate.

  Three review rounds, all FAIL, 56 findings, 48 closed and 8 carried. Every round found at least one critical, and rounds 2 and 3 each found theirs INSIDE the previous round's fix, which is this repository's documented pattern holding for a sixth phase.

  The transferable lesson is not any single defect but their shape: three of the four criticals were the interface asserting something the agent never established, and all three came from the same habit of building a plausible model and then writing tests against that model rather than against the contract. `marker_ids` is the sharpest instance: the correct token-to-citation binding was on the wire, validated, documented in `_narrative_chunks`'s own docstring, and the UI invented a substring heuristic instead. Every premise-gate fixture then set `marker_ids: []`, so the gate confirmed the invention. That is `attack-the-constraint`'s own rule, missed: read what the component was GIVEN before debugging what it produced.

  Five assertions in this phase could not fail, three written by the lead. The last two were caught by deliberately breaking the code and watching the check stay green, not by reading them, and one was moved out of vitest entirely once it was proven that no mocked harness could make it fail. Mutation-testing every new gate clause is now the practice.

  Two long-standing repository defects unmasked and fixed. The Playwright webServer timeout carried since build phase 3.3 as "a pre-existing environment quirk" was Vite binding to [::1] while the probe waited on 127.0.0.1; the earlier diagnosis had queried `localhost`, which resolves to ::1 on macOS, and so confirmed a different address than the failing one. Behind it sat a second: the e2e mock backend's Guard-tier response had not matched `guardrail/classifier.py`'s schema since build phase 3.0 replaced the passthrough guardrail. No browser test in this repository had run green for five phases, and the outer defect hid the inner one.

- 2026-08-12: build phase 4.8 entered a design review that runs outside the build cadence and gates the phase. A visual deliverable has no natural failing test to gate on, so the design system serves as the premise gate's fixture, and a fixture that moves mid-build is not a fixture; the design therefore settles first and the phase opens afterwards. Six-step loop, recorded in DECISIONS.md: the product owner works on a clickable prototype in the Claude Design project "NCBI Agentic Search", asks for a pull, the lead pulls it with DesignSync into `docs/build/design/design-system/` and reports what changed and what the backend cannot actually deliver, the lead pushes corrections back, the product owner approves explicitly, and only then is the design frozen, the phase opened and everything built at once. The pull step is what keeps the backend and frontend in sync rather than diverging: on its first run it caught three tool names (`medgen_lookup`, `alfa_frequency`, `pubmed_search`) shown in the prototype that are not in the seven-tool roster and that a builder would otherwise have built as real. Artifacts created this review: a clickable prototype, an 18-card component library mirrored to Claude Design, `docs/build/design/Design_to_build_workflow.md`, and a design argument page, all under a new `docs/build/design/` segment split out when `docs/build/` hit its own nine-file revisit trigger. Three design decisions settled: the provenance spine kept and always rendered, the navy hero kept as the single saturated surface, and the monospace-identifier rule kept but narrowed so gene symbols stay proportional. Eight decisions logged. The phase remains unopened; the component cards are still behind the prototype, tracked in `docs/build/design/README.md` under "Open reconciliation".

- 2026-08-11, later the same day: build phase 4.8 (Web UI visual design) inserted into `Technical_specification.md` Section 25's locked build order, a deliberate, product-owner-directed exception to the 2026-07-24 build-phase doc-review-cadence decision that the PRD, tech spec, and strategic memo are frozen through the build and edited only at the Step 6.2 reconciliation (already closed 2026-08-10). Deliverable: MUI (Material UI) adoption as the component library, a real theme, restyling the existing screens (auth, chat/search, live streaming progress, citations) built in phase 1.2, rather than a layout or navigation restructure. Trigger: the shipped UI, built as scaffolding in phase 1.2, was found too unstyled for the product owner to demo, and the original plan already named the fix (this document's 2026-07-21 Step 1.10 entry, "adopt or adapt the reference React components... a strong component library") without execution ever carrying it through past the interaction-pattern half. Depends only on 1.2 (already merged); numbered as the next open slot in the delivery-surfaces group, it runs immediately after 4.1, before 4.2 through 4.7, per this project's own precedent that build-order numbers are not strictly execution-sequential (phase 1.2 itself built after 2.0). Two decisions logged.

- 2026-08-11: build phase 4.1 (the outbound-only MCP server wrapping the same tool functions, Section 13.2) closed, merged to `develop` as PR #40. Adds `adapters/mcp/server.py`, exposing a single advertised tool, `ask_biomedical_question`, that folds the same `RunRegistry`/`run_streaming` core build phase 4.0 finalized into one JSON result, never the seven internal tools directly and never a stream. Three judge rounds: round 1 FAILED on a gate-integrity bug in the premise gate's own leak-detection assertions (two test assertions compared a key name against a list of values, so they could never fail); round 2 PASSED after a fix round closed it; round 3 PASSED, independently re-deriving both criticals and the two structural surface guarantees fresh against the code rather than trusting either prior round's report, including live counterfactual mutation testing. One adversary round against the live mounted app filed 16 findings (2 critical, 4 major, 4 moderate, 6 minor); 13 closed outright, and 2 carried open as genuine product-level calls with a named owner each on `tracker/BOARD.md`: F-4.1-A-10 (whether relaying untrusted third-party source text to an autonomous agent consumer needs a provenance-labeling field the locked contract does not have) and F-4.1-A-15 (a caller-supplied `session_id` unbound to its owner, latent until build phase 4.5 or 4.6 wires a consumer). `/verify` READY, `dev-standards` READY with 0 blocking issues, `eval-harness` determined not applicable in full (reasoning in `tracker/phase_4.1.md`). Full account: `tracker/phase_4.1.md`.

- 2026-08-10, later still the same day: LEARNINGS.md restructured (PR #38), on the product owner's request that the file be "better organized, especially the long prose section." Every entry from build phase 1.0 onward (57 of 63) had grown a table cell of 100 to 500-plus words; each is now a 1 to 2 sentence summary row ending "Full account below," with the original text moved verbatim into a new Entry detail section, one subsection per entry. The `learnings` skill already named this exact fix ("add a detailed section below the table... keep the table row as the index pointing to it"); this is the first time it was applied across the whole file. Four parallel fresh-context agents split the 57 entries by build-phase era and relocated text only, verified afterward against the original with byte-for-byte spot checks; nothing was reworded or dropped. The six 2026-07-26 (Phase 5) entries, short enough already, were left untouched, and the F-2.0-15 entry's short row and detail section were updated in the same pass to reflect its build-phase-4.7 assignment (the entry above), via an appended update note rather than an edit to the original sentences. Added a table of contents (the file never had one) and a `## Recurring patterns` section with a mermaid diagram tracing two lessons, composition defects invisible to per-component tests and needing to review a fix harder than new code, that each had to be learned more than once across this build before becoming a structural gate.

- 2026-08-10, later still the same day: F-2.0-15's disposition decided, in a follow-up exchange after Step 6.2's own checkpoint and `/ship` had already landed (see the entry below). Product-owner decision: build phase 4.7 is now formally F-2.0-15's home (real query-intent classification and entity resolution), not just its closest candidate, rather than block build phase 4.0 or open a new, unscheduled phase. Build phases 4.0 through 4.6 proceed as planned, none of them depend on real question-understanding. `tracker/BOARD.md`'s flag for F-2.0-15 moved from phase 2.0's row (already closed) to phase 4.7's row.

- 2026-08-11: Build phase 4.0 (the REST plus SSE adapter finalized as the public API surface) closed, merged to `develop` as PR #39. Rebuilt `core/run_registry.py`'s abandonment check mid-phase after an adversary round found the original resettable-timer version bypassable by reconnect churn (F-4.0-A-01), replacing it with cumulative-unwatched-time tracking. Four judge rounds and one adversary round: round 1 FAILED on two blocking findings (no SSE `id:` line, an unverifiable premise-gate claim), rounds 2 through 4 PASSED after fix rounds closed what each prior round found, and the adversary round filed 14 findings (4 major, 5 moderate, 5 minor), of which 8 are fixed and judge-confirmed, 2 resolved by documenting them as intentional design decisions, and 4 carried open with a named owner each on `tracker/BOARD.md`'s Open flags table (three to build phase 6.0's rate-limiting work, one to whichever phase next touches `write_node`'s `DonePayload`, one to a future abandonment-logic revisit). Full account: `tracker/phase_4.0.md`. Four new decisions logged.

- 2026-08-10, later the same day: Step 6.2, the one reconciliation pause, ran immediately after build phase 3.4's merge and closed the same day, across eight PRs (#29 through #36) merged to `develop`. Measured against this document's own Step 6.2 section, the authoritative scope:
  - Default branch renamed `main` to `develop` (PR #29), every genuine branch reference swept across 8 rule/skill files, README, and Section 24 of the tech spec.
  - All 4 of build phase 2.2's carried grounding findings resolved (PR #30): Section 8.2's matching rule and F-2.2-05's number-formatting fix absorbed into the tech spec as new steps 5a/5b; F-2.2-A-05 confirmed already closed by build phase 3.4, a stale tracker entry corrected; F-2.2-T-01-residual kept open by explicit product-owner decision.
  - Build phase 2.1's premise-gate cadence folded into the tech spec as a new Section 23 subsection (PR #31).
  - The two remaining process decisions resolved (PR #32): Section 23's offline gate stays scheduled for build phase 5.1; the `release-workflow` phase-end mandate (0-of-6 real dispatches) rewritten to name the judge round, adversary round, and stage-10 gates as the real requirement.
  - All 14 items explicitly tagged "Step 6.2" as owner in the continuation prompt's Open items table closed (PR #34), researched with parallel read-only agents before any edit: four pure spec corrections plus real fixes spanning a live safety gap (F-3.1-50), a new `write_seeking` guardrail category (F-3.0-01, also catching a second hand-maintained copy of the category set in the frontend that would have silently rejected the event), two Layer 3 citation schema widenings (F-3.3-J-06, F-3.3-A-05), a `pathogen_detection` status split (F-3.5-A-09), and a live-probed 14-value `overall_status` enum widen (F-3.5-A-12, the live count differed from the 12 previously estimated). F-3.4-A-06 scheduled as its own dedicated task rather than rushed.
  - The new-intake folder swept (PR #35): 19 notes triaged into `personal-os-work`'s permanent Reference folders. 3 phase-relevant suggestions (MCP server statelessness, signal-based feedback-loop review sampling, a semantic guardrail layer) got a one-line pointer in the continuation prompt rather than only living in the note.
  - An informal manual smoke test run against the live system (PR #36), deliberately not the formal graded eval-harness gate: the 7 v1 must-pass moat questions asked directly, real LLM calls, real NCBI APIs, answers read by hand. The live graph was unreachable from the session that ran it (the SSH tunnel cannot be opened from a sandboxed coding session). Surfaced F-2.0-15: `think_node`'s real query classification was never built past its build-phase-2.0 stub, causing 4 of 7 must-pass questions to refuse outright and a 5th to answer near-empty. Filed unowned in `tracker/BOARD.md`; no phase in the current build order claims this scope.
  - The whole-repository security scan stays PAUSED INDEFINITELY on cost, unchanged by this reconciliation.
  - Also reconciled `tracker/BOARD.md`'s own staleness (items closed in PR #34 that were never removed from the Open flags table) and the doc-drift counts across `CLAUDE.md`, `AGENTS.md`, this document, `PROGRESS.md`, and the continuation prompt.

- 2026-08-10: Build phase 3.4 (citation trust extended to Layers 2 and 3, the two-tier risk gate, data freshness and conflict resolution), the last of the six Step 6.3 tool-and-trust phases, closed on `phase/3.4-citation-trust-full`, merged as PR #28. Extends Section 9.1/9.2 provenance (the four `CitationPayload` fields) to all six Layer 2/3 tools via a shared per-tool default table and one citation-building function per tool; fixes F-2.2-A-05 (the flagship gene-disease claim now classifies `high` risk via the traversed edge label, not the bare `Disease` node type); folds in T-3.1-28, wiring `act_node` to dispatch `ncbi_efetch` as a second answer-bearing tool alongside `cypher_query`, this repo's first dual-layer dispatch; wires Section 7.1 (live-wins-for-currency), Section 7.4 (staleness auto-cross-verify), and Section 7.2 (code-level conflict detection, flooring a genuine cross-layer disagreement at the `flag` trust outcome). Section 7.3's `as_of` wire marker was deliberately scoped out, needing a new SSE event type and a contract-version bump this phase's time budget could not safely absorb.
  - Ten review rounds before close: a blocking premise gate written first and watched failing (4 of 10 on real missing behavior, 6 on `ModuleNotFoundError`), a first judge round (5 of 7 tickets closed, 2 held against two new findings), a fix round closing both, a judge confirmation round (all 7 of 7 `done`), an adversary round against the live system (7 findings, 1 critical, 2 majors, 3 moderate, 1 informational), a fix round closing the critical and both majors, and a final judge round that independently live-verified that fix round rather than trusting its own report.
  - The critical: a query naming two genes silently dropped the second one under a confident `answer` outcome, no citation, no disclosure that half the question went unanswered (F-3.4-A-01). Fixed with a `write_node` completeness check that floors `trust_outcome` at `ask` and discloses the unaddressed entity whenever surviving citations cover a strict subset of a multi-entity question's own entities.
  - The two majors: a realistic two-hop query shape reopened F-2.2-A-05's own risk-misclassification for a Disease row touched by more than one edge, where the correct "never guess a single label" backoff had the side effect of losing the high-risk signal entirely (F-3.4-A-02, closed with a second, independent ambiguous-high-risk-touch signal that never guesses a specific wrong edge); and the exact-field-name pairing every Section 7 mechanism depends on never fired for this system's own most common dual-layer citation pair, Gene `name` versus `symbol` (F-3.4-A-03, closed with one explicit alias table entry plus a containment-based compatibility check, closing a false negative without manufacturing a false conflict on every normal dual-layer answer).
  - A fourth, unfiled defect surfaced and was closed in the same fix round: the F-3.4-A-03 alias fix, once it made field-name pairing reachable in practice for the first time, exposed that the pairing had never verified "same subject entity", and could pair two different genes' facts as if they were the same fact. Closed with a same-entity gate comparing normalized `source_url`.
  - Three real defects were found and fixed while live re-verifying the dual-layer dispatch mechanism itself during the ticket work, none caused by a mistake in the dispatch code: a dict-collision bug let a "derived" sibling row silently overwrite a real row's traversed edge type; a Layer 2 finding's normal `total_available=None` poisoned a known Layer 1 total; a heuristic tuned for a MedGen ETL leak false-positived on the legitimate gene symbol "BRCA1". A fourth was two things at once: a real, separately-confirmed crash risk (an uncaught `pydantic.ValidationError` on an OMIM-sourced citation URL, fixed) and genuine Synth sampling variance in how reliably the model cites both layers in one narrative, not a code defect, mitigated by grading that one premise-gate case pass@8 rather than on a single run.
  - Final gate: full non-live suite 2406 passed, 66 skipped, 1 xfailed, 3 pre-existing failures confirmed present on the unmodified base commit, zero new failures. Live premise gate 10 of 10, no tunnel-gated skip. `ruff check` clean on every touched file. Four items carried open, each with its own named reason in `tracker/phase_3.4.md`: F-3.4-T06-01 (the staleness check is real and wired but has no field to fire against on this graph's current ingest, a System 1/2 gap), F-3.4-A-04 (the premise gate's own coverage claim overclaims a triangulation verdict it cannot yet produce with only one second origin wired), F-3.4-A-05 (dormant, depends on F-3.4-T06-01), F-3.4-A-06 (a URL-pattern end-anchor gap, not currently exploitable through this phase's own code).
  - The transferable lesson: a fix round is exactly where a regression hides best, since the fixer's attention is on the finding named, not on every call site sharing the same shape. The judge's insistence on independently live-verifying the fix round rather than trusting its report, and the fix round's own investigation surfacing a second, unfiled defect inside its own other fix, both caught what a same-session self-check would have missed, the same pattern the prior phase already named.

- 2026-08-08, later the same day: Build phase 3.5 (`pathogen_detection` and `clinicaltrials_search`), completing the seven-tool roster, closed on `phase/3.5-pathogen-clinicaltrials-tools`. `pathogen_detection` covers bulk isolate, cluster, and AMR-genotype access over the NCBI Pathogen Detection FTP snapshot tree; `clinicaltrials_search` covers the disease-to-trials path over ClinicalTrials.gov API v2. A new `"clinicaltrials"` rate-limit family (5 req/s provisional) landed in `ncbi_transport.py`, and a new streaming-only FTP transport module (`pathogen_ftp_transport.py`) was built for the pathogen tool, since bulk FTP retrieval shares no HTTP-status-coded convention with any prior tool. Registered into the tool schema at `TOOL_REGISTRY_VERSION` v5.
  - Pre-build live probing found the phase's own binding constraint before any tool code existed: the Salmonella `SNP_distances.tsv` snapshot file measured roughly 411 GB, three orders of magnitude past a normal bulk TSV, ruling out a full download and forcing a wall-clock-bounded streamed scan instead.
  - A dispatch-ordering gap cost a real fix-and-reconcile pass: two worktree-isolated builders were dispatched before the lead's own shared prerequisites (the transport module, both premise gates) were committed to the phase branch, so neither builder's worktree could see them. One builder worked around it by reading outside its own worktree; the other correctly refused to fabricate the missing dependency and flagged every resulting assumption instead, which the lead then reconciled against the real, now-committed files and live data.
  - A judge round found one critical defect: the streaming transport's early-exit logic assumed a filter key is always unique per row, so a shared cluster id stopped the scan after its first matching row and reported an incomplete 4-member cluster as a complete 2-member one. Closed alongside three majors (an unbounded 120-second wait on an optional enrichment step, three of four network read sites reporting a routine snapshot rotation as an unclassified tool defect, and stale module docstrings still describing the dispatch-ordering accident as the shipped state) and two minors, lead-verified with a live premise gate pass, 8 of 8.
  - An adversary round dispatched immediately after found that the judge-round fix had itself introduced two NEW critical regressions of the identical discard-real-data shape, both coexisting with the green judge verdict and the passing premise gate: `cluster_snp_neighbors` could no longer ever return a successful result at all, since the fix's own early-exit removal had no fallback and discarded whatever a cutoff scan had already found; and `clinicaltrials_search` pagination errored on every second page, since ClinicalTrials.gov omits its total-count field from every paginated response regardless of what the first fix assumed.
  - Both were fixed in two more rounds, the second only surfacing after a first live re-verification against the adversary's own exact repro case proved the initial fix incomplete: an upstream scan step was consuming the entire shared deadline, starving its own mandatory follow-up read of any budget one call downstream. Every fix in both rounds was re-verified live against the real APIs, not trusted from the mocked unit suite, which stayed green through every round including both regressions.
  - Two majors and five moderate-or-minor adversary findings were deliberately carried open rather than fixed this round (a query-syntax-parsing risk, an undisclosed weak-match shape reproducing phase 3.3's own finding, a spec-locked enum narrower than the live API, among others), each with its own named reason in `tracker/phase_3.5.md` rather than silently dropped.
  - Final gate: 2331 Python tests (2220 passed, 110 skipped, 1 xfailed), up from the phase's 2140 baseline. Live premise gates, pathogen_detection 5 of 5 and clinicaltrials_search 3 of 3, both re-confirmed multiple times against the real APIs across both fix rounds. `ruff check` clean on every file this phase touched. Frontend suite unaffected (no frontend files touched); Playwright's webServer orchestration hit the same pre-existing, already-documented timeout from build phase 3.3, confirmed unrelated by starting the dev server directly (HTTP 200).
  - The transferable lesson: a fix for a discard-real-data defect is exactly the kind of change most likely to reintroduce the identical defect one layer over, since the fixer's attention is on the one call site the finding named, not on every other call site sharing the same resource-exhaustion shape. Only live re-verification against the adversary's own repro case, re-run after every round of changes, caught both regressions; a fully green mocked test suite caught neither.

- 2026-08-08, later the same day: Build phase 3.3 (`pubtator_annotate` and `litvar2_lookup`), the first two Layer 3 enrichment tools, closed on `phase/3.3-enrichment-tools`, merged as PR #26. `pubtator_annotate` covers entity normalization for free text and entity annotation on publications via PubTator3; `litvar2_lookup` covers variant-to-literature evidence via LitVar2. Both are the first tools whose retrieved content is genuinely untrusted external text rather than a structured API record. Two new rate-limit families (`"pubtator"`, `"litvar2"`, 5 req/s provisional throttle each) landed in `ncbi_transport.py`. Registered into the tool schema at `TOOL_REGISTRY_VERSION` v4.
  - Ten review rounds before close: a blocking premise gate written first and watched failing (12 of 12, `ModuleNotFoundError`, the correct direction), a judge round (FAIL, two majors), a fix round, an independent fresh-context re-review of that fix round (FAIL, found a real regression the fix round itself introduced), a second fix round, an adversary round against the live APIs (13 findings, 1 critical, 6 major), a third fix round, a fourth fix round closing several findings originally left as documented product decisions that turned out addressable without one (an `entity_lookup` citation, a real dbSNP citation replacing LitVar2's own unverifiable client-rendered UI, disclosure parity between the two tools), an independent re-review of that round (found a real regression: a multi-match result citing only its first, unrelated match as if it covered the whole answer, and a regression test that could not fail on the bug it was named for), and a fifth fix round closing both.
  - The critical, and its two majors: both tools silently discarded the upstream API's own match-relevance signal (a `match` field on every autocomplete row, e.g. LitVar2's `"Matched on synonyms <m>334C</m>"`), so `variant_search(query="334")` returned five confidently cited, wholly unrelated variants, and `entity_lookup(query="the")` returned ten confidently normalized MeSH and Gene entities, both under `status: "ok"` with nothing marking either as weak.
  - The fix-round regression, caught only by an independent re-review dispatched specifically because this repo's history predicts a same-session fix hides a defect its own author cannot see: closing the "fabricated ok on zero matches" finding discarded the disclosure notes already computed for the excluded rows, so a wholly-excluded response became byte-identical to a genuine no-match, and the same commit removed the one test that would have caught it.
  - Resolved without deviating from the locked spec: an additive, optional `matched_on` field on each tool's result items discloses the raw upstream relevance signal (disclosure only, no auto-refusal heuristic built, deliberately deferred to its own review round); a PMID identity diff normalized before comparison closes a disclosure-field-lies-about-its-own-data bug; `min_length` added to two under-constrained schema fields closes two gaps a prior "closed" finding had missed.
  - Two provenance gaps carried to Step 6.2 as decisions, not bugs: `pubtator_annotate`'s `entity_lookup` mode ships no citation at all (Section 6.4's entity schema names no `source_url` field), and `litvar2_lookup`'s single top-level citation points at a search UI rather than a per-record page (Section 6.5 provides one top-level field only). A third decision, a disclosure-policy asymmetry between the two sibling tools (one discloses withheld fields, one does not), surfaced for the product owner rather than resolved unilaterally.
  - Final gate: 2140 Python tests passing (2037 passed, 102 skipped, 1 xfailed), up from the phase's 1969 baseline at the judge round. Live combined premise gate 12 of 12, no tunnel-gated skip. `ruff check` clean on every file this phase touched (16 pre-existing, unrelated whole-repo findings confirmed untouched by this phase via `git log`). Two decisions logged. Two LEARNINGS.md entries added by hand after `tracker/check_learnings_coverage.py` returned a false "nothing to cover", a parsing gap (it only recognizes a narrative finding format, not this phase's table-row format) flagged on `tracker/BOARD.md` rather than silently trusted. The Playwright end-to-end suite could not be verified in this session (a webServer-orchestration timeout unrelated to any file this phase touched; the backend itself starts and answers `/health` correctly when run directly). Full per-finding detail, all 13 adversary findings and 6 judge findings: `tracker/phase_3.3.md`.
  - The transferable lesson: an autocomplete or search-style upstream API's own relevance signal is exactly the kind of "not named in the locked output schema, therefore never considered" gap the additive-field pattern already used for `fields_withheld`/`pmids_not_found` exists to close, and two prior review rounds passed both tools without ever asking what the API sent that the schema had no room for.

- 2026-08-08: Build phase 3.2 (`ncbi_dbsnp`), the second Layer 2 tool, merged as PR #25. Variation Services normalization (rsid/spdi/hgvs) sequenced before a dbSNP ESummary clinical and population fetch, keyed on the resolved canonical id, never the caller's raw input. A new `variation` rate-limit family (~1 req/s) landed in `ncbi_transport.py`. Registered into the tool schema at `TOOL_REGISTRY_VERSION` v3.
  - Six full review passes before close: a blocking premise gate written first and watched failing (8 of 8, `ModuleNotFoundError`, the correct direction), an adversary round (14 findings, 2 critical), a judge round (FAIL, independently reproduced both criticals plus 6 more findings), a fix round (all 5 confirmed-blocking findings closed), an independent fresh-context re-review (2 new findings inside the fix round's own code), and a second fix round (both closed). Every finding across the whole phase was real; zero rejected.
  - The two criticals: `_cap()` silently truncated over-length values and shipped them as `status: "ok"` (a dropped ClinVar term, a wrong-length variant SPDI), and a bare numeric identifier from any namespace, sent as `query_type: "rsid"`, resolved to a confident, cited, unrelated variant, since every integer is valid input to `refsnp/{id}`.
  - The re-review's own two findings were more subtle: the fix for the first critical (refuse the whole call on any over-cap field) turned out to hard-error on roughly 10.4 percent of real clinically-cited variants, including flagship ones (APOE ε4, Factor V Leiden, BRCA2), because two standard ClinVar vocabulary terms exceed the locked spec's 40-char cap; and the fix for a related retry-safety finding confidently told the agent to retry a deterministic, permanent input error (a reference-sequence mismatch), the exact opposite of the truth.
  - Resolved without deviating from the locked spec: field-level withholding (`fields_withheld`, naming what was dropped) replaced whole-call refusal for every field except `spdi_canonical`, the one field without which there is no variant identity to attach anything else to.
  - Three spec-versus-reality gaps carried to Step 6.2, none fixed unilaterally: Section 25's build-order line for this phase names a dbVar coordinate-overlap sub-tool that already shipped in build phase 3.1; Section 6.3 names a Variation Services endpoint confirmed live-broken server-side, substituted with a live-working sibling; and the locked `clinical_significance` cap itself, too tight for real ClinVar vocabulary.
  - Final gate: 1830 Python tests passing, 90 skipped, 1 xfailed. Live premise gate 8 of 8, no tunnel-gated skip, since this tool never touches Layer 1. `ruff check` clean on every file this phase touches. Two decisions logged. Full per-finding detail, all 16 adversary findings and 6 judge findings: `tracker/phase_3.2.md`.
  - The transferable lesson: pre-build live probing before any fixture is written catches a defect class (compound-string fields, comma-joined arrays) a fixture authored from documentation cannot, and a fix round's own fixes need the same adversarial scrutiny as the code they repair, since both of the re-review's findings lived inside code the fix round itself had just written.

- 2026-08-07, later the same day: F-2.1-C15's generation half closed on `fix/c15-generation-bound`, merged as PR #24 (commit `15efe57`). This is the finding where a generated query with an unbounded relationship traversal took the graph server down for every user; `validate_cypher` now rejects a generated variable-length relationship pattern (`[:orthologous_to*]` or similar) before execution, since AGE materializes `DISTINCT` before `LIMIT` ever applies. The existing session-level memory guard is unchanged.
  - Analysis written first, per the lesson from the previous, reverted attempt at this same ticket (`LEARNINGS.md`, 2026-08-04), which had skipped it and shipped a rule rejecting a legitimate query, `[:orthologous_to {weight: 2*3}]`, as unbounded.
  - The fix's own first version, correctly avoiding that exact regression by slicing the existing relationship-hop regex's captured bracket interior, was itself found bypassable by a fresh-context adversarial review before merge: a nested bracket (a list-valued property) alongside the variable-length spec defeated it, because that regex's non-nesting bracket capture never matches a hop shaped that way, the same defect class already fixed once in this file for node patterns (F-2.1-A9) and never generalized to relationship hops.
  - Rebuilt as a standalone, wildcard-free pattern matched directly against the quote-masked query string, independent of the hop regex entirely. A second independent review confirmed the bypass closed, found no new one, checked for ReDoS (none, linear scaling across six adversarial timing inputs), and found one narrow, non-blocking gap against full Cypher grammar unreachable by this system's actual generation, documented rather than fixed.
  - F-2.2-01 (a separate, lower-severity generation flake, roughly 1 run in 10) was deliberately left open rather than folded into the same branch, per the ticket's own allowed alternative; a retry would have touched `cypher_query.py`'s error-handling path in the same review pass as a critical safety fix.
  - Final gate: 1729 Python tests passing (up from 1715), 82 skipped, 1 xfailed, `ruff check` clean except one pre-existing, unrelated finding, doc drift clean. Three decisions logged in `DECISIONS.md`. Full account: `tracker/fix_c15_generation_bound.md`.
  - The transferable lesson: this exact non-nesting-regex defect class had already cost one review round in this same file, for a different pattern. Fixing it once did not generalize it; a new check built on a sibling pattern with the same shape reintroduced the identical defect, and only a fresh-context review, not the same session that wrote the fix, caught it.

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
