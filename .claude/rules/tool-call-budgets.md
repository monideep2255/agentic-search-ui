---
paths:
  - "src/system_03_search_agent/tools/**/*"
  - "src/system_03_search_agent/harness/call_budget.py"
  - "services/graph_query_service/**/*"
  - "tests/system_03_search_agent/tools/**/*"
  - "tests/system_03_search_agent/harness/test_call_budget*.py"
  - "tests/services/graph_query_service/**/*"
  - ".github/gates/gate05_integration.sh"
  - "docs/ncbi/Tool_implementation_mechanics.md"
---

## Tool call budgets

Every tool in the seven-tool roster (`requirements/Technical_specification.md` Section 6) carries a locked per-call timeout, and several carry a rate-limit pool they must respect. A tool without a declared timeout is not finished. A timeout that exists in the spec but not in the code is a defect, not a detail: the multi-agent pipeline gate in `production-standards` requires a schema for every tool, and a timeout is as load-bearing as `maxLength` or a host-pinned `source_url` regex. Apply this rule whenever writing, reviewing, or reasoning about any tool in `system_03_search_agent/tools/`, the read-only HTTPS graph query service, or the integration test suite that exercises live APIs.

### Per-tool timeout table

| Tool | Timeout | Rate-limit pool |
|------|---------|-------------------|
| cypher_query | 30 seconds per call (Section 6.1) | Not rate-limited by NCBI, the graph is not an NCBI API |
| ncbi_efetch | 15 seconds per call, one backoff retry on transient failure (Section 6.2) | E-utilities: 3 requests/second unauthenticated, 10 requests/second with an API key |
| ncbi_dbsnp | 15 seconds per call, up to 30 seconds worst case for one invocation, since Variation Services normalization and the dbSNP clinical fetch run sequentially (Section 6.3) | Variation Services: roughly 1 request/second, a separate pool from E-utilities |
| pubtator_annotate | 15 seconds per call (Section 6.4) | No documented rate limit, subject to the shared per-query call budget |
| litvar2_lookup | 15 seconds per call (Section 6.5) | No documented rate limit, subject to the shared per-query call budget |
| pathogen_detection | 60 seconds or more, a bulk FTP transfer, not an interactive API call (Section 6.6) | Not a request-rate API. Bound by transfer time and snapshot pinning, not requests per second |
| clinicaltrials_search | 15 seconds per call (Section 6.7) | No documented rate limit, provisional throttle of about 5 requests per second (Section 21.1) |

### The verified-limit gap: E-utilities

Two conflicting E-utilities rate-limit figures exist in the source material: a 2026-05-07 decision recorded an NCBI admin key raising the ceiling to 100 requests/second, while the 2026-07-25 live verification in the capability sheet found 3 requests/second unauthenticated and 10 requests/second with a standard API key on the endpoints actually probed that session (Section 21.1). The technical specification follows the live-verified figures, not the admin-key figure, because they are the more recent, directly tested source. This is not settled: confirm which figure is actually live before locking the throttle constants into code. Do not silently split the difference between the two, and do not pick whichever number is more convenient for a given feature.

### Provisional throttle for undocumented APIs

The Datasets API v2 and each of the four enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov v2) have no published numeric rate limit in the capability sheet. Until a published figure is confirmed, treat each as an interactive HTTPS API and apply the same provisional throttle used for PubChem: about 5 requests per second (Section 21.1). A tool for one of these APIs that ships with no throttle at all is not honoring this rule, even though no vendor-published number exists yet to violate.

### Wait queues and fail-fast

Each API family's token bucket sits behind a bounded FIFO wait queue, not an unbounded one. Queue depth is capped at roughly 15 to 30 queued calls, a small multiple of the family's per-second rate (Section 21.4). A queued call's wait ceiling is tied to the query's own remaining latency budget, not one fixed constant across every query class: a lookup-class query with a short total budget tolerates only a short queue wait before failing fast, while a multi-hop or deep-research query with a longer budget tolerates a longer wait. A call that would exceed either the queue depth cap or the wait ceiling must fail fast with a `rate_limited` error carrying a `retry_after` estimate and the saturated family name, never join an unbounded queue and never fail silently.

### Live integration tests must not trip their own rate limits

Layer 2 and Layer 3 integration tests hit real public HTTPS endpoints and are CI-native from day one (Section 23). They must run at a pace that respects each API's verified limit from the table above, most tightly Variation Services at roughly 1 request per second. An integration suite that fires faster than the limit it is testing against is a self-inflicted failure, and it can trip a shared rate-limit bucket that then fails an unrelated PR, since the limit belongs to the API per host, not to any one test run (Section 21.2).

### The read-only HTTPS graph query service

The Section 24 graph query service that fronts Layer 1 over HTTPS carries its own three-part budget: a hard row limit, a per-call timeout matching the `cypher_query` tool's own 30-second budget, and a rate limit per caller. All three bound a runaway query on both sides of the hop, the tool's own validator and the service itself, not just one.

### Relationship to other rules

These are call-level budgets: how long one tool call may run and how often it may fire. They compose with, and never substitute for, the dollar cost caps `system-design-patterns` pattern 4 already owns (per-query cap, per-user daily cap, system-wide daily cap, per-step timeout). A tool call can be within its timeout and rate-limit pool and still be killed by a cost cap, and a tool call that respects every cost cap is not exempt from its own timeout. Do not restate the cost caps here; read pattern 4 for those.

A `rate_limited` or timeout error is not just a failure signal, it is an instruction to the next agent step. This connects directly to the retry-safety gate in `production-standards`: an error message must say what to do next, not just what failed, because the Act step reads the error and decides whether to retry, wait, or move on with partial results. "Timed out" is not actionable. "Graph query exceeded 30s, retry with a narrower query_intent or a smaller query_class" is.

### Three-state permissions

Allow:
- Writing a tool implementation that enforces the timeout and, where one exists, the rate-limit pool from the table above, without asking
- Applying the provisional 5 requests/second throttle to an API with no published limit, without asking
- Flagging a tool that ships with no declared timeout or no rate-limit handling during any review

Ask:
- Before locking a specific E-utilities throttle constant into code while the 3/10-per-second versus 100-per-second conflict remains unconfirmed
- Before changing a queue depth cap, a wait ceiling, or a provisional throttle value away from what this rule and the technical specification state

Deny:
- Never ship a tool with no per-call timeout
- Never let a queued call join an unbounded wait, or wait past its query class's latency budget, instead of failing fast
- Never let an integration test against a live API run at a pace that risks tripping that API's own rate limit
- Never return a bare "failed" or "timed out" message from a rate-limited or timed-out call when an actionable next step is available

The test: does every tool call in this system carry a declared timeout, does every rate-limited API family have an enforced pool and a bounded fail-fast queue, and does a timeout or rate-limit error tell the next agent step what to do about it?
