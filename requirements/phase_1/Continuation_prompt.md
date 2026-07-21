# Phase 1 continuation prompt

Use this to resume Phase 1 source review in a new chat session.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 1 of System 3 planning (source review and architecture decisions). Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap, Phase 1 structure with all 10 steps
2. `requirements/phase_1/Session_May_07.md` - complete record of Steps 1.1 through 1.5 discussions
3. `DECISIONS.md` - all decisions logged so far (7 from May 5, 31 from May 7)
4. `requirements/context/Background_requirements.md` - index of all 24 source materials

Steps 1.1 through 1.5 are complete. 38 total decisions in DECISIONS.md.

Resume with Step 1.6: review user psychology and product design (4 sources).

Sources:
1. Hook model for adoption (`Reference/user-side/Hook_model_and_belief_design_Nir_Eyal.md`)
2. AI adoption gap (`Reference/user-side/Bridging_the_AI_adoption_gap_enterprise.md`)
3. Build to learn vs. build to earn (`Reference/user-side/Build_to_learn_vs_build_to_earn.md`)
4. Board session notes (`Reference/thoughts/`)

Decide: which psychological design principles make it into the PRD as requirements?

Rules:
- Append to `requirements/phase_1/Session_May_07.md` (or create a new session file if this is a different day). Never delete existing content.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- This documentation serves dual purpose: project record AND my personal learning. Capture all discussion details, diagrams, and rationale.
- We discuss before we draft. Ask me one question at a time.

After Step 1.6, continue through Steps 1.7-1.10 as defined in Plan.md.

---

## Progress tracker

| Step | Status | Session file |
|------|--------|-------------|
| 1.1 strategic foundation (3 sources) | COMPLETE | Session_May_07.md |
| 1.2 architecture design (6 sources) | COMPLETE | Session_May_07.md |
| 1.3 reference implementations (2 sources) | COMPLETE | Session_May_07.md |
| 1.4 data handoff (2 sources) | COMPLETE | Session_May_07.md |
| 1.5 agent and harness research (22 sources) | COMPLETE | Session_May_07.md |
| 1.6 user psychology and product design (4 sources) | NOT STARTED | - |
| 1.7 contractor documents (7 sources) | NOT STARTED | - |
| 1.8 tools and infrastructure | NOT STARTED | - |
| 1.9 open questions (10 items) | NOT STARTED | - |
| 1.10 cross-cutting concerns (5 topics) | NOT STARTED | - |

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
