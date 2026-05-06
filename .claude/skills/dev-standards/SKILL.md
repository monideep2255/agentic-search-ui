---
name: dev-standards
description: "Apply production coding standards to the agentic search system. Reviews code against 6 lenses (security, testing, quality, PR readiness, deployment, production hardening), generates readiness checklists, and guides prototype-to-production quality."
scope: project
depends_on:
  - .claude/rules/system-design-patterns.md
  - .claude/rules/dependency-tracking.md
  - .claude/skills/best-practices/SKILL.md
depended_by:
  - CLAUDE.md
  - AGENTS.md
  - .claude/skills/bossman-mode/SKILL.md
  - .claude/skills/release-workflow/SKILL.md
---

# Dev standards skill

Use this skill when building, reviewing, or preparing to deploy any code in the agentic search system. It applies the production quality bar adapted from NCBI Web Platform (NWS) enterprise standards for the System 3 stack: FastAPI, LangGraph, React, PostgreSQL, and the multi-model LLM harness.

## When to invoke

- Before calling a feature "ready" or merging a PR
- When writing new API endpoints, agent nodes, or tools
- When adding a new dependency or external service integration
- When preparing a PR for review
- When moving from prototype to production quality
- Say `/dev-standards` or ask "is this production ready?"

## What this skill does

It runs through six lenses on the code or feature being discussed: security, testing, code quality, PR readiness, deployment readiness, and production hardening. Not all lenses apply to every change. Identify which lenses are relevant, then run only those.

Apply [attack-the-constraint](../../rules/attack-the-constraint.md): if the PR has a Critical security issue, do not spend time flagging a missing type hint. Report the bottleneck first.

---

## Lens 1: Security checklist

Run through these checks on any API endpoint, agent node, tool, or data-handling code:

Input validation:
- [ ] FastAPI endpoints use Pydantic models for request bodies (not raw dicts)
- [ ] Path and query parameters are typed (int, str with constraints, enums)
- [ ] User input is never interpolated into Cypher queries (use parameterized `$variable` syntax only)
- [ ] User input is never passed raw into LLM system prompts (guardrail node sanitizes first)

Prompt injection defense:
- [ ] Guardrail node runs before any LLM call on user input
- [ ] User messages are clearly delimited from system instructions in prompts
- [ ] Tool outputs are treated as untrusted (not injected into system prompts without sanitization)
- [ ] No user-controlled strings in tool names, function calls, or schema definitions

API and transport safety:
- [ ] API keys, tokens, and secrets never appear in log messages, error responses, or LLM context
- [ ] CORS configured with explicit origin allowlist (no wildcard `*` in production)
- [ ] JWT tokens have expiry, are validated on every request, and use secure algorithms (HS256 minimum)
- [ ] SSE streams do not leak PII, internal IDs, or debug information to the client
- [ ] Rate limiting configured on public-facing endpoints

Query safety:
- [ ] Cypher queries use AGE parameter binding (`$param`), never f-string or .format() interpolation
- [ ] NCBI API calls validate response status before parsing (no blind JSON access on error responses)
- [ ] Redis keys are namespaced and never constructed from raw user input

---

## Lens 2: Testing checklist

For any new feature, tool, or endpoint:

Backend:
- [ ] Unit tests cover the happy path and at least one error/edge case
- [ ] Async FastAPI endpoints tested with `httpx.AsyncClient` (not sync TestClient for async routes)
- [ ] Each tool has a test fixture with known input/output and schema validation
- [ ] Agent loop changes tested with mocked LLM responses (verify tool selection, state transitions)
- [ ] Integration tests against a real PostgreSQL+AGE instance via Docker fixture (`@pytest.mark.docker`)
- [ ] Existing tests still pass; coverage has not decreased

Frontend:
- [ ] React components tested with Vitest + React Testing Library
- [ ] SSE streaming behavior tested (connection, data events, error events, reconnection)
- [ ] Accessibility: WCAG 2.1 AA check on any user-facing UI (axe or Lighthouse)

Performance:
- [ ] Load test (k6) for SSE endpoint under concurrent connections before production
- [ ] NCBI API tool tests include timeout handling (what happens when NCBI is slow or down?)
- [ ] Large result set handling tested (truncation works, count is accurate)

---

## Lens 3: Code quality checklist

- [ ] Python: snake_case for functions, variables, modules. TypeScript/React: camelCase
- [ ] ruff passes with no errors (line-length 100, project config in pyproject.toml)
- [ ] Type hints on all function signatures and dataclass fields (Python)
- [ ] TypeScript strict mode for frontend (no `any` without explicit justification)
- [ ] Pydantic models for all API request/response schemas (no raw dicts crossing API boundaries)
- [ ] Tool schemas are typed JSON with explicit field descriptions (no untyped dicts)
- [ ] `async` used only for I/O-bound operations (httpx calls to NCBI, Redis ops); sync for psycopg2 graph queries
- [ ] No hardcoded model names; all LLM calls go through the multi-model harness tier routing
- [ ] Semantic versioning follows `v1.2.3` pattern (lowercase v)
- [ ] CHANGELOG updated with `## UNRELEASED` entry if applicable

---

## Lens 4: PR readiness checklist

- [ ] PR title is descriptive and includes phase reference (e.g., "Phase 2: add cypher_query tool")
- [ ] Description explains what changed, why, and how to test locally
- [ ] All GitHub Actions CI checks pass (tests, ruff, type check, bandit)
- [ ] No unresolved review comments
- [ ] No secrets, .env files, or large binaries in the diff
- [ ] Feature branch will be deleted after merge
- [ ] If the change affects agent prompts, tool definitions, or cost thresholds: logged in DECISIONS.md

Security scanning (CI):
- [ ] bandit passes (no High or Critical findings)
- [ ] safety/pip-audit passes (no known CVEs in dependencies)
- [ ] semgrep rules pass (if configured)

---

## Lens 5: Deployment and production readiness

Before any production promotion:

- [ ] Docker Compose runs cleanly for local dev (FastAPI + Redis + PostgreSQL user DB)
- [ ] Dockerfile passes hadolint (minimal base image, non-root user, multi-stage build)
- [ ] All environment variables documented in env.example with descriptions
- [ ] Health check endpoint (`/health`) returns 200 with dependency status (DB, Redis, graph connectivity)
- [ ] Full test suite passes in a clean environment (fresh venv, no local state)
- [ ] Rollback plan documented (standard: redeploy prior Docker image tag; unique plan for schema migrations)
- [ ] No production deploys without running the complete test suite first
- [ ] Post-deploy smoke test defined (minimum: one end-to-end query that exercises all three data layers)

---

## Lens 6: Production hardening checklist

Before flagging a gap, confirm it is the bottleneck for this specific change. Apply [attack-the-constraint](../../rules/attack-the-constraint.md): if the code has a Critical security issue, do not spend time flagging a missing ADR.

Supply chain:
- [ ] New dependencies vetted (maintained, license compatible, no known CVEs)
- [ ] Lockfile updated and committed (requirements.txt pinned, package-lock.json committed)
- [ ] `pip-audit` / `npm audit` passes (no Critical or High findings)

CI gates:
- [ ] All merge-blocking gates pass (tests, ruff, bandit, type check)
- [ ] Coverage has not dropped more than 2%

Cost control (safety-critical):
- [ ] Per-query cost cap enforced (kill agent loop if exceeded)
- [ ] Per-user daily cap enforced (reject queries after quota)
- [ ] System-wide daily cap enforced (pause accepting new queries)
- [ ] Per-step timeout configured (abort stuck LLM calls)
- [ ] Changes to cost thresholds require explicit user approval

Agent loop integrity:
- [ ] Changes to one step (Guardrail/Think/Plan/Act/Write) tested against downstream steps
- [ ] Tool schema changes reflected in both the tool definition and agent system prompt
- [ ] Guardrail changes tested with edge cases (injection attempts, off-topic queries)

Provenance:
- [ ] Every citation includes `source`, `source_id`, `source_url`, and `layer`
- [ ] Functions producing citations require provenance fields (cannot produce a citation without them)
- [ ] Graph results link to NCBI source records via stored `source_url`

Streaming:
- [ ] Mid-stream errors show partial result + error message (not blank screen)
- [ ] Stop button cleanly aborts the agent loop
- [ ] Time-to-first-token under 1 second for the guard tier response
- [ ] Citation chips emitted inline as the model references sources

Rate limiting and external APIs:
- [ ] NCBI API rate limits respected (3 req/sec without key, 10/sec with key)
- [ ] Retry logic with exponential backoff for transient NCBI failures
- [ ] Large result sets truncated to first N relevant results with total count included

Migration safety:
- [ ] PostgreSQL user DB schema migrations are backward-compatible (expand-contract pattern)
- [ ] Rollback script or procedure documented and tested locally

Secrets:
- [ ] No secrets in code, config files, logs, LLM context, or streaming responses
- [ ] Environment-specific credentials (dev != prod)
- [ ] API keys rotatable without code changes

---

## How to apply during code review

When asked to review code:

1. Read the code and identify which lenses apply (not all apply to every change)
2. Run through the relevant checklists above
3. Report findings in this format:

```
PRODUCTION READINESS REVIEW
============================
Security:       PASS / N issues found
Testing:        PASS / N gaps found
Code quality:   PASS / N issues found
PR readiness:   PASS / N items missing
Deployment:     PASS / N items missing
Prod hardening: PASS / N gaps found (constraint: [bottleneck identified])

Overall: READY / NOT READY
Constraint: [the one thing blocking production readiness right now]

Issues to fix before production:
- [Critical/High/Medium/Low] description
```

4. For each issue, cite the specific lens and checklist item
5. Identify the constraint: the single highest-severity issue that blocks readiness

---

## Reference

Source standards: NWS production coding standards (adapted from `reference/personal-os-work/NIH/NWS/Technical-development-workflow/NWS_dev_workflow_standards.md`)

Deployment pipeline: LOCAL (Docker Compose) -> Staging -> Production
Security tools: bandit (SAST), safety/pip-audit (dependency audit), semgrep (patterns)
Testing tools: pytest, pytest-asyncio, httpx, Vitest, Playwright, k6
Monitoring: LangSmith (tracing), application logs, health endpoint
Cost control: multi-model harness with hard caps at every tier
