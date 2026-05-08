# Phase 1 continuation prompt

Use this to resume Phase 1 source review in a new chat session.

## Context to provide

Paste the following into your new chat:

---

We are in Phase 1 of System 3 planning (source review and architecture decisions). Read these files to get up to speed:

1. `requirements/Plan.md` - overall roadmap, Phase 1 structure with all 10 steps
2. `requirements/phase_1/Session_May_07.md` - complete record of Steps 1.1 and 1.2 discussions
3. `DECISIONS.md` - all decisions logged so far (7 from May 5, 17 from May 7)
4. `requirements/Background_requirements.md` - index of all 24 source materials

Steps 1.1 (strategic foundation, 3 sources) and 1.2 (architecture design, 6 sources) are complete. 18 decisions logged to DECISIONS.md from today's session.

Resume with Step 1.3: review reference implementations (2 sources).

Source 1: NCBI KG repo, ncbi-kg branch (`reference/ncbi_ai_agents-ncbi-kg/`). Analyze which patterns to adopt directly (NL-to-Cypher pipeline, 4-layer guardrails, React components) and which to adapt.

Source 2: Contractor 8-layer architecture (`reference/personal-os-work/NIH/KG/Contractor/`). Decide on: typed query-plan IR (adopt or simplify?), GraphQL as public surface (adopt or stay REST?), context-pack builder (adopt fully?).

Rules:
- Append to `requirements/phase_1/Session_May_07.md` (or create a new session file if this is a different day). Never delete existing content.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- This documentation serves dual purpose: project record AND my personal learning. Capture all discussion details, diagrams, and rationale.
- We discuss before we draft. Ask me one question at a time.

After Step 1.3, continue through Steps 1.4-1.10 as defined in Plan.md.

---

## Progress tracker

| Step | Status | Session file |
|------|--------|-------------|
| 1.1 strategic foundation (3 sources) | COMPLETE | Session_May_07.md |
| 1.2 architecture design (6 sources) | COMPLETE | Session_May_07.md |
| 1.3 reference implementations (2 sources) | NOT STARTED | - |
| 1.4 data handoff (2 sources) | NOT STARTED | - |
| 1.5 agent and harness research (22 sources) | NOT STARTED | - |
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
8. Budget: ~$100 total for 2-month build
9. Single orchestrator with 3-tier model routing (not multi-agent)
10. Model selection deferred to Phase 6 (golden dataset ablation)
11. Streaming with typed SSE events + hard latency budgets
12. Three-layer data architecture confirmed
13. Parallel tool execution via asyncio.gather
14. Result compression before re-injecting into agent context
15. NCBI API rate limit upgraded to 100 req/sec
16. Two-API strategy: E-utilities + Datasets API v2 + Variation Services
17. PubTator3 REST API replaces all local NER/normalization
