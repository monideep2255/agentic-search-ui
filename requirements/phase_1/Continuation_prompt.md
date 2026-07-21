# Phase 1 continuation prompt

Use this to resume Phase 1 source review in a new chat session.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 1 of System 3 planning (source review and architecture decisions). Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap, Phase 1 structure with all steps (1.1 through 1.13)
2. `requirements/phase_1/Session_May_07.md` (Steps 1.1 through 1.5) and `requirements/phase_1/Session_July_21.md` (Steps 1.6 through 1.13) - complete discussion records
3. `DECISIONS.md` - all decisions logged so far (75 as of 2026-07-21)
4. `requirements/context/Background_requirements.md` - index of all 24 source materials

All Phase 1 steps (1.1 through 1.13) are complete. Phase 1 is done, with 75 total decisions in DECISIONS.md.

Next is Phase 2: competency questions and user research. Finalize the competency-question set (tiers, personas, and a v1 cap), apply the moat test and the added coverage metric, scrape real user data (Confluence, Jira, app logs) via MCP, and design the interaction-to-competency-question feedback loop, producing the evaluation playbook. See Plan.md Phase 2.

Primary input: `requirements/phase_1/Phase_1_synthesis.md` (all Phase 1 decisions organized by topic).

Rules:
- Append to `requirements/phase_1/Session_May_07.md` (or create a new session file if this is a different day). Never delete existing content.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- This documentation serves dual purpose: project record AND my personal learning. Capture all discussion details, diagrams, and rationale.
- We discuss before we draft. Ask me one question at a time.

Phase 1 is complete. Phase 2 is next; it produces the evaluation playbook.

---

## Progress tracker

| Step | Status | Session file |
|------|--------|-------------|
| 1.1 strategic foundation (3 sources) | COMPLETE | Session_May_07.md |
| 1.2 architecture design (6 sources) | COMPLETE | Session_May_07.md |
| 1.3 reference implementations (2 sources) | COMPLETE | Session_May_07.md |
| 1.4 data handoff (2 sources) | COMPLETE | Session_May_07.md |
| 1.5 agent and harness research (22 sources) | COMPLETE | Session_May_07.md |
| 1.6 user psychology and product design (3 sources) | COMPLETE | Session_July_21.md |
| 1.7 contractor documents (7 sources) | COMPLETE | Session_July_21.md |
| 1.8 tools and infrastructure | COMPLETE | Session_July_21.md |
| 1.9 open questions (10 items) | COMPLETE | Session_July_21.md |
| 1.10 cross-cutting concerns (5 topics) | COMPLETE | Session_July_21.md |
| 1.11 new intake research (45 sources) | COMPLETE | Session_July_21.md |
| 1.12 conference learnings (3 sources) | COMPLETE | Session_July_21.md |
| 1.13 LLM legal and compliance | COMPLETE | Session_July_21.md |

## Key decisions already made (for quick reference)

1. Innovation proposal is starting ground for V1, all scope elements apply
2. All 5 delivery formats in scope (web UI, GraphQL API, MCP server, KGX export, CLI agent)
3. FastAPI over Django for V1 (async-native, porting to Django is bounded)
4. Hybrid API: REST + SSE for chat, GraphQL (Strawberry) for programmatic access
5. NCBI strategic directives are hard requirements, not aspirational
6. Open-source LLMs preferred; commercial for debugging only
7. OpenRouter as inference provider via LiteLLM
8. Budget: ~$100/month (relative marker, not hard cap)
9. Single orchestrator with 3-tier model routing (not multi-agent)
10. Model selection deferred to Phase 6 (golden dataset ablation)
11. Streaming with typed SSE events + hard latency budgets
12. Three-layer data architecture confirmed
13. Parallel tool execution via asyncio.gather
14. Result compression before re-injecting into agent context
15. NCBI API rate limit upgraded to 100 req/sec
16. Two-API strategy: E-utilities + Datasets API v2 + Variation Services
17. PubTator3 REST API replaces all local NER/normalization
18. NCBI KG repo as infrastructure template, not architecture blueprint
19. Simplified query classification (not full typed IR)
20. NL-to-Cypher separation: Plan step produces structured output, tools compile to Cypher
21. Layer 2 as authoritative fallback when Layer 1 data is suspect
22. User must never see nothing: graceful degradation always
23. LLM is narrative controller only; harness handles citations deterministically
24. Tools are direct Python functions; MCP wraps them as a separate delivery format
25. SOUL.md behavioral directives for agent domain rules
26. Verification loop: in-memory rules-based checks before user sees output
27. Cypher generation: dedicated LLM call inside cypher_query tool with validation pipeline
28. Budget clarified as ~$100/month, not total
29. Adoption frame: habit is the goal, trust is the engine; success metric is default-first-stop (1.6)
30. Investment loop full in v1: saved queries plus feedback-driven personalization (1.6)
31. Contractor package treated as Track 2: mine patterns, NFRs, eval criteria, not its RDF/SPARQL/GraphQL/federation architecture (1.7)
32. NFR three-bucket filter; security posture: trust-guardrails in POC, enterprise IAM deferred, basic auth for v1 (1.7)
33. Query generation: generation-first hybrid (schema-aware Cypher plus validator), verified templates for the ~10 tier-1 CQs; backend-agnostic, query language sealed inside the tool (1.7)
34. v1 federation = the three data layers; external non-NCBI KG federation to v2 (1.7)
35. Evaluation milestone ladder (4 gates, stakeholder-mapped) as a hard PRD success requirement; operational numbers live in the Phase 2 playbook (1.7)
36. Hosting: build individually first on our stack (Railway, PostHog, LangSmith over Arize), migrate to NCBI/OCCS after PoC; self-maintained in-repo tracker over Linear (1.8)
37. Model distillation: tiered orchestration is the v1 cost lever; distillation proper deferred to v2; model-per-tier to 1.11, legal to 1.13 (1.9)
38. Agent naming: top 100 biomedical scientists, streamed persona; mechanism stays one orchestrator plus parallel tools, not autonomous subagents (1.9, 1.10)
39. Streaming-thinking: curated named-step narrative default, stop button throughout, optional show-full-reasoning expander (1.10)
40. Security forbidden outputs: no personal medical advice, off-topic refuse-and-redirect, jailbreak reject; adopt the reference build's pre-LLM guardrail and double read-only enforcement (1.10)
41. Accessibility and Section 508 deferred to the production and v1 track; PoC does reasonable-effort accessibility (1.10)
42. New-intake adopt batch: coordinator/worker cost mechanism (cite-or-refuse as an architectural boundary), route-by-query-shape plus exact-ID retrieval, prompt caching via a stable prefix (1.11)
43. Model-bench adopted: frozen per-tier tasks, deterministic correctness, GeneBench-Pro style for biomedical judgment; open-source candidate set benched in Phase 6 (1.11)
44. Cost caps: $0.10/query, 100/user/day, $10/day system-wide, timeouts inherit the latency budgets, tunable Phase 4 (1.11)
45. Fusion deferred to v2 (triggered escalation lever); no separate router step; risk-tier pass deferred to Phase 3 (1.11)
46. Conference NL-to-Cypher discipline: entity-to-CURIE resolution with ask-back, scoped subgraph schema injection, schema-restricted reasoning, glossary supplements, split validation/summarization, full-sliced-schema cached upfront (1.12)
47. Provenance expanded (evidence-kind, assertion-confidence, population/ancestry, license) plus citation-substantiation and cross-source-triangulation grounding gates; eval-harness redesigned (contamination-resistant, concept-scored, human-baseline, inductive splits) (1.12)
48. Vector retrieval via Layer 3 LitSense (no bespoke index for PoC); single orchestrator with a written v2 graduation trigger; moat test kept plus a separate coverage metric (1.12)
49. Track 1 vs production two-lane split; country-of-origin Option A (Track 1 uses the strongest models now including Chinese-origin, compliant substitute benched, config-swap migration) (1.13)
50. Licensing permissive default (research-only barred); no PHI so no BAA for v1 (zero-retention a should-have); federal authorization (FedRAMP, FISMA, ATO) deferred to the production track (1.13)
