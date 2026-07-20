---
description: "Non-negotiable security, quality, and hardening gates for Python, FastAPI, LangGraph, Cypher/SQL, and React code in this repo."
scope: portable
alwaysApply: true
---

## Production standards

Apply when writing Python, FastAPI, LangGraph, Cypher, SQL, or React code anywhere in `src/system_03_search_agent/` or the frontend. These are the non-negotiables that block production deployment for System 3.

### Security: the critical checks

These are the same pattern classes any SAST tool flags as SQL injection, XSS, or sensitive data exposure. Apply them automatically whenever writing a FastAPI endpoint, an agent tool, or a query builder.

Input handling:
- Validate and type-coerce every input at the FastAPI boundary with a Pydantic model. Never pass a raw query param or request body straight into business logic. Pydantic's field types replace the manual `int(request.GET.get('key', '0'))` casting other frameworks need by hand.
- Never bypass Pydantic validation to accept an arbitrary dict or untyped payload on an endpoint that touches the graph, an NCBI API, or the agent loop.

Query safety:
- The `cypher_query` tool reaches the AGE graph via psycopg2. Building the Cypher string, or the wrapping SQL that invokes it, with an f-string or `.format()` is the exact same injection surface as SQL built the same way. All Cypher and SQL must use parameterized placeholders (`%s` via psycopg2). No f-strings or `.format()` in any query string, Cypher or SQL, anywhere in the codebase.
- URL-encode all URL parameters passed to NCBI or enrichment APIs: `urllib.parse.quote(value, safe=":/=?&|+")`. Decode first if the value may already be encoded.
- XML parsers must disable external entities. NCBI EFetch returns XML: `etree.XMLParser(resolve_entities=False)`.

Secrets and output:
- Never include API keys, tokens, or passwords in log messages or exception strings. Omit the variable value; log the key name as a string literal instead.
- FastAPI responses go out as JSON through Pydantic response models. Never hand-build a response string by concatenating user input, and never return raw HTML built from string concatenation.

React and JavaScript:
- JSX escapes content by default. `dangerouslySetInnerHTML` is the equivalent of disabling that auto-escaping, and it needs the same scrutiny as `|safe` in a server template: never pass unsanitized content through it.
- Encode all URLs before use: `encodeURI(url)`.
- Validate any redirect or link destination against an allowed host before navigating: `new URL(url).hostname.endsWith('ncbi.nlm.nih.gov')` (or whatever host the target is supposed to resolve to). Same principle as the host-pinned regex in the multi-agent pipeline gate below.

### Code quality: the defaults

- snake_case for all function arguments.
- Type hints on function signatures, dataclasses, and Pydantic models.
- Parameterized Cypher and SQL queries only (same rule as security above, reinforced).
- `isort` for Python imports.
- Sync patterns for a single request; async when fanning out to 2 or more concurrent Layer 2 or Layer 3 API calls.

### Testing: the minimum bar

- New FastAPI endpoints need tests for valid input, invalid input, and missing or null input. Use `httpx` and `pytest`.
- Integration tests hit a real database or graph connection where feasible. No mocked graph connection unless the test specifically targets the mock.
- Any UI change needs a WCAG 2.1 AA accessibility check.

### Hardening: no vibecoding defaults

Non-negotiables to apply before calling code production-ready. When multiple gaps exist in a single change, attack the constraint first: fix the gap that poses the highest real risk before addressing lower-priority items (see `attack-the-constraint` rule).

- No new dependency without a security review (maintained, license compatible, no known CVEs, more than one maintainer).
- No endpoint without input validation, tests (valid, invalid, null), and rate limiting consideration.
- No database or graph schema migration without a rollback plan and backward-compatibility verification (expand-contract pattern).
- No production claim without CI evidence (all merge-blocking gates pass).
- No architecture decision without a DECISIONS.md entry or equivalent note when it affects future work.

Retry-safety gate, for any code the agent loop may run more than once:
- Writes must be idempotent or repeat-safe. The Act step retries, so a tool that creates, appends, or mutates must produce the same end state whether it runs once or three times. Use upserts, check-then-write, or natural-key dedup, not blind inserts.
- Error messages must say what to do next, not just what failed. The agent loop reads the error and decides its next action, so "connection refused to host X, retry after backoff or check credentials" beats "Error 500". Actionable errors are a correctness feature when the reader is an agent.

Supply chain gate:
- Lockfiles committed. `pip-audit` and `npm audit` pass. No Critical or High CVEs in new dependencies.

Secrets gate:
- Secrets in env vars or a secrets manager only. No secrets in code, logs, or images. Dev and prod credentials are separate.

Multi-agent pipeline gate:
- Every tool and subagent in the agent loop must declare an output schema (JSONSchema). Validation runs at every hop, Guardrail to Think to Plan to Act to Write. An unvalidated payload flowing from one step to the next is how prompt injection moves laterally.
- `maxLength` on every string field and `maxItems` on every array are required, not optional. They cap the blast radius if a single upstream document, abstract, or API response goes hostile.
- Bounded context items: every context fragment injected into a model prompt, a retrieved passage, a prior tool result, carries a hard token or character cap enforced before injection, not only `maxLength` on a schema string. One oversized retrieved passage must not blow the context budget or crowd out the system instructions.
- URL fields use a host-pinned regex, for example `^https://([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/`, not just `^https://`. This applies directly to `source_url` on every citation: a citation URL that only checks for `https://` can be spoofed to point anywhere.
- Untrusted-source readers, any tool that ingests external documents (a Layer 3 enrichment fetch, a scraped abstract, an NCBI record body), get Read access and the relevant API tool only. Never Write, never the ability to call other tools directly. The orchestrator and the Write step never see a raw untrusted document unmediated; they only see what the reading tool returned through its schema.
- A malformed-but-parseable payload flowing downstream unchecked is a documented real-world failure mode in biomedical MCP servers: LLM output passed across pipeline stages with only `json.loads` and a couple of key checks, no JSONSchema, no `maxLength`, no `maxItems`. Treat that as the negative example to design against.

AI answer grounding gate:
- Cite-or-refuse: every answer the agent generates from sources must be tied to a specific retrieved passage, node, edge, or API result, or the agent must explicitly return "I could not find information on this" and stop. No answering from model priors when retrieval returns nothing. This is the direct implementation of CLAUDE.md's "Citations: non-negotiable" rule, and it is the single highest-leverage correctness gate for a biomedical search system, where a confident wrong answer is worse than no answer.
- Every claim in a generated answer carries an inline citation to its source, per the `source`, `source_id`, `source_url`, `layer` provenance type. An answer with an uncited sentence fails the gate.
- The "no source found" path is a tested path, not an afterthought: write a test that feeds a query with zero retrieval hits and asserts the refusal string, not a fabricated answer.
- Deterministic accept or reject: a citation-grounding or quote-match check decides accept or reject by deterministic rule (exact or substring match after normalization), never by a fuzzy similarity threshold, because a fuzzy accept silently passes a hallucinated quote. Fuzzy scoring may rank repair suggestions only; it never gates acceptance.
- Grade this with the `eval-harness` skill: add cite-or-refuse and citation-coverage as pass/fail acceptance criteria, measured with pass@k against the Phase 4 golden dataset (50 queries) before any answer-generation feature ships.

### When to invoke the full skill

For a complete production readiness review (6-lens checklist covering security, testing, code quality, PR readiness, deployment, and production hardening), invoke the `/dev-standards` skill. This rule covers the critical-path non-negotiables only.

The test: did I apply every security, supply-chain, secrets, multi-agent schema, and AI answer grounding gate before calling System 3 code production-ready?
