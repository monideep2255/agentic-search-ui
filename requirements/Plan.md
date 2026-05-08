# System 3 planning roadmap

From background research to working product. This document defines every step between where we are now (raw research collected) and where we need to be (a running search agent + UI backed by a solid PRD and technical specification).

Kick-off: 2026-05-06. Phase 0 completed in the kick-off session. All background material collected, vision aligned, plan agreed.

Last updated: 2026-05-07

## Table of contents

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

My tasks (Monideep): competency question research, Confluence/Jira data scraping, stakeholder input, architecture sign-off, PR reviews, new reference material collection (KGC, Nodes AI, red teaming)

Agent tasks (Claude): document analysis, technical drafting, code implementation, testing, sub-agent coordination, execution via bossman-mode

We discuss before we draft. We draft before we build. We build one phase at a time.

---

## Phase 0: foundation (complete)

Status: DONE (2026-05-06)

What we did:
- Assessed System 3 readiness across all dimensions
- Discussed the high-level vision: query system, guardrails, three-layer data access, competency question feedback loop
- Agreed on starting with few-shot routing (not classification layer, not fine-tuned model) for competency question-based orchestrator improvement
- Collected all background material into a single reference index

Output: `requirements/Background_requirements.md` (24 sources indexed, all paths verified)

---

## Phase 1: source review and architecture decisions

Status: IN PROGRESS (Steps 1.1 through 1.5 complete as of 2026-05-07)

Goal: go through every source in `Background_requirements.md`, debate what to use, what to skip, and what needs adaptation. Lock the architecture decisions before writing the PRD.

### Phase 1 output structure

Phase 1 produces three types of output that together feed Phase 2:

1. Session notes (`requirements/phase_1/Session_*.md`): chronological record of what we discussed, debated, and why. One file per session. These are the raw record and also serve as a personal learning log.
2. Decision log (`DECISIONS.md`): every confirmed choice in a flat, searchable table with rationale. Append-only.
3. Phase 1 synthesis document (`requirements/phase_1/Phase_1_synthesis.md`): written after all 10 steps complete. Organizes all decisions and discussion outcomes by topic into a single narrative. This becomes the primary input for Phase 2 (competency questions) and Phase 3 (PRD).

The synthesis document fills the gap between chronological session notes and a flat decision table. Session notes answer "what did we discuss and when?" DECISIONS.md answers "what did we choose?" The synthesis answers "what does it all mean together, organized by topic, ready for downstream phases?"

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

### Step 1.7: review contractor documents (7 sources)

| Source | What to decide | Owner |
| --- | --- | --- |
| NFR baseline (10 categories) | Which NFRs apply to our POC? Tag each as must-have or defer. | Discuss together |
| NLQ approach (6 ranked options) | Confirm: we are building toward rank 1 (typed IR) while operating like rank 2 (CQ templates + slot filling) for POC | Discuss together |
| Meeting decisions (D1-D5) | Federation scope: how much for v1? Template vs. NL: confirm NL from day 1. | Monideep decides |

### Step 1.8: review tools and infrastructure

| Source | What to decide | Owner |
| --- | --- | --- |
| Tools list (section 10 of background) | Lock: Railway? PostHog? Arize vs LangSmith? Linear? GraphQL vs REST? | Discuss together |

### Step 1.9: resolve open questions

The 10 open questions from section 12 of `Background_requirements.md` must each get a decision or an explicit "defer to tech spec" tag.

### Step 1.10: review cross-cutting concerns

Topics that cut across multiple sources and need explicit architecture decisions before the PRD.

| Concern | What to decide | Owner |
| --- | --- | --- |
| Security and threat model | Prompt injection defense, forbidden query types, PII handling, audit logging. Use "Agents of Chaos" red-teaming findings (section 8 of Background_requirements.md) as the threat catalog. What does the NCBI KG reference implementation do? What does the NIH context require? | Discuss together |
| Data freshness and conflict resolution | Graph is a periodic snapshot; APIs are live. When they disagree, which wins? What staleness is acceptable? | Discuss together |
| Rate limiting strategy | NCBI E-utilities at 100 req/sec (upgraded), Variation Services at 1 req/sec (separate). With concurrent users, who gets throttled? Queue? Prioritize? Fail fast? | Discuss together |
| UI patterns and user experience | Review reference implementation React components. What interaction patterns to adopt (streaming, citations, error states)? What to redesign? | Claude reviews, Monideep approves |
| Accessibility and compliance | Section 508 is not optional for NIH-adjacent work. What level of compliance for v1? | Discuss together |

Phase 1 output: session notes, decision log (DECISIONS.md), and Phase 1 synthesis document (see output structure above).

---

## Phase 2: competency questions and user research

Status: NOT STARTED

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

Task (Discuss together): finalize the CQ set. Lock tier 1 (must-answer for v1), tier 2 (should-answer), tier 3 (stretch/future).

### Step 2.4: define evaluation rubric

Confirm or update the 8-point scoring rubric from `02_Tier1_eval_spec.md`. Does the rubric match our architecture?

### Step 2.5: design the feedback loop mechanism

The vision says user interactions become competency questions that improve routing. Define the mechanism:
- How are user interactions captured and stored?
- Who reviews them: automated, semi-automated, or manual?
- What triggers a new competency question vs. reinforcing an existing one?
- How do new CQs get promoted into the orchestrator's routing?

Task (Discuss together): design the feedback pipeline. This feeds into the tech spec.

Phase 2 output: final competency question set with tiers, personas, evaluation rubric, and feedback loop design. This becomes a standalone document in `requirements/`.

---

## Phase 3: PRD creation

Status: NOT STARTED

Goal: write the PRD. Single source of truth for what System 3 does, for whom, and how we measure success.

Prerequisites: Phase 1 decisions locked. Phase 2 competency questions finalized.

### Step 3.1: outline the PRD

Use the template from `reference/personal-os-work/NIH/Agentic-Search/Specs/` as starting structure. Adapt to our scope.

Sections (expected):
- Problem statement
- Users and personas (from CQ analysis)
- Core user flows
- UI experience (end-to-end user flow, error states, streaming UX, citation interaction, loading/empty states, what happens when guardrails fire)
- Cost control UX (what the user sees when caps are hit, usage visibility)
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

Status: NOT STARTED

Goal: write the tech spec. Translates PRD requirements into implementation decisions: what to build, how, in what order.

Prerequisites: PRD locked.

### Step 4.1: outline the tech spec

Sections (expected):
- System architecture (agent loop, three-layer data, multi-model harness)
- API design (endpoints, request/response schemas, streaming)
- Data access patterns (Cypher queries, API calls, caching)
- Data freshness and conflict resolution (staleness thresholds, layer priority when graph and live API disagree)
- Tool specifications (one section per tool: cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup)
- Guardrail implementation (input validation, read-only enforcement, rate limits, cost caps)
- Security implementation (prompt injection defense, PII handling, forbidden query types, audit trail)
- Frontend architecture (React components, state management, streaming UX, error states, citation chips, loading/empty states)
- Auth and user data model
- Observability (tracing, analytics, audit logging)
- Cost control (per-query caps, per-user daily caps, system-wide caps, UX when caps are hit)
- Rate limiting and concurrency (per-layer throttling, queue strategy for concurrent users)
- Testing strategy (unit, integration, eval harness, golden dataset)
- Deployment (Railway, environment config, CI/CD)
- Build order (phased, with dependencies)
- Competency question routing (few-shot now, upgrade path later)
- Feedback loop pipeline (interaction capture, CQ generation, routing updates)

### Step 4.2: draft the tech spec

Task (Claude): write the first draft. Reference the PRD for every requirement traced.
Task (Monideep): review, challenge, refine.

### Step 4.3: lock the tech spec

Both agree. This is the build blueprint.

Phase 4 output: `requirements/Technical_specification.md`

---

## Phase 5: system and tooling updates

Status: NOT STARTED

Goal: update all project infrastructure to reflect the locked PRD and tech spec. Every skill, agent, rule, and root document should be consistent with what we decided.

### Step 5.1: update bossman-mode skill

Review `.claude/skills/bossman-mode/SKILL.md` against the tech spec build order. Update:
- Phase definitions to match the tech spec phases
- Team composition per phase
- Skill chain and quality gates
- Any new agent roles needed

### Step 5.2: update or create skills

Evaluate whether we need new skills for System 3 development:
- API development skill?
- React component skill?
- Tool testing skill?
- Cypher query development skill?

Only create what is actually needed. Do not over-engineer.

### Step 5.3: update root documents

| Document | What changes |
| --- | --- |
| CLAUDE.md | Update build order, current focus, add any new reference docs |
| AGENTS.md | Update for any new tools, patterns, or adapter specs from tech spec |
| DECISIONS.md | Should already be current from Phase 1. Verify. |
| README.md | Update project status, add link to requirements/ folder |

### Step 5.4: create any new reference docs

If the tech spec identified gaps in documentation (e.g., a deployment guide, a Cypher patterns reference), create those in `docs/`.

Phase 5 output: all project infrastructure aligned with PRD and tech spec.

---

## Phase 6: build (bossman execution)

Status: NOT STARTED

Goal: build System 3 using bossman-mode. Agent teams execute, I orchestrate.

Prerequisites: PRD locked, tech spec locked, bossman-mode updated.

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
2. Index: add to `requirements/Background_requirements.md` (new section or append to existing)
3. Evaluate: does this change anything in the PRD or tech spec?
4. If yes: update the PRD/tech spec, tag the change, rebuild affected components
5. If no: keep as future reference

### Hard stop rule

We do NOT update the PRD or tech spec mid-build. v1 ships based on what we locked in Phase 3 and 4. New information collected during the build goes into the reference folder and gets evaluated for v2.

Exception: if new information reveals a fundamental flaw (security vulnerability, wrong architectural assumption), we pause the build, discuss, and update.

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
| Background_requirements.md | Phase 0 (done) | `requirements/` | Index of all source material |
| Plan.md | Phase 0 (done) | `requirements/` | This document. Roadmap from research to product. |
| Phase 1 session notes | Phase 1 (in progress) | `requirements/phase_1/Session_*.md` | Chronological discussion record per session. Also serves as personal learning log. |
| Phase 1 decisions | Phase 1 (in progress) | `DECISIONS.md` (append) | Architecture choices from source review |
| Phase 1 synthesis | Phase 1 (end) | `requirements/phase_1/Phase_1_synthesis.md` | All decisions organized by topic into a single narrative. Primary input for Phase 2 and Phase 3. |
| Competency_questions.md | Phase 2 | `requirements/` | Final CQ set with tiers, personas, rubric |
| PRD.md | Phase 3 | `requirements/` | Product requirements. Single source of truth. |
| Technical_specification.md | Phase 4 | `requirements/` | Implementation blueprint. |
| Updated skills/agents | Phase 5 | `.claude/skills/`, `.claude/agents/` | Aligned with PRD and tech spec |
| Reference docs (as needed) | Phase 5 | `docs/` | Fill gaps identified during tech spec |

---

## How new information gets incorporated

```
Conference / research / new tool
        |
        v
Save to reference/personal-os-work/NIH/Agentic-Search/Reference/
        |
        v
Add entry to requirements/Background_requirements.md
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

This keeps the build stable while allowing continuous learning.

---

## Summary of what happens next

Phase 1 is next. We go through the 24 sources in `Background_requirements.md` one section at a time. We debate. We decide. We log decisions. Once all sources are reviewed, we move to competency questions (Phase 2), then PRD (Phase 3), then tech spec (Phase 4), then we update our tools (Phase 5), then we build (Phase 6).

One phase at a time. No skipping.
