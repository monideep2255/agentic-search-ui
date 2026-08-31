# Build phase 6.0: rate limiting and concurrency

Branch: `phase/6.0-rate-limit-concurrency`. Opened 2026-08-31.

Delivers technical specification Section 21: per-layer throttling, the shared cap across
concurrent users, the at-most-20-API-calls-per-query budget, and the concurrency queue
strategy. Depends on build phases 3.1, 3.2, 3.3 and 3.5, all merged.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [Everything measured before any change was made](#everything-measured-before-any-change-was-made)
- [The finding that reframes the phase](#the-finding-that-reframes-the-phase)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [History](#history)

## What this phase is for

Section 21 bounds how fast this system may call somebody else's API, and how many times one
question may do it. Two of those bounds protect a third party rather than this system: the
E-utilities pool and the Variation Services pool belong to NCBI per host, not to any one
user, so ten concurrent users draw from one budget. The third bound protects the user: a
question that fans out without limit spends a person's latency budget on retrieval and
arrives at synthesis with nothing left.

None of this is new ground in this repository. Seven rate-limit families, their token
buckets and their bounded wait queues were built incrementally across the tool phases, 3.1
through 3.5, because each tool needed its own pool the day it shipped. What this phase owns
is what could not be built from inside a single tool: the per-query call ceiling, which is a
property of the loop rather than of any tool, and the wait ceiling that reads the calling
query's own remaining budget, which needs a caller that knows the query class.

## Everything measured before any change was made

Measured 2026-08-31 by reading the shipped source, before any ticket was written. Stated as
a table rather than a paragraph so a later reader can check each row independently.

| Section | What it requires | State today | Evidence |
|---|---|---|---|
| 21.1 | Per-layer throttling, one pool per API family, live-verified figures where they exist and a provisional 5 requests/second where they do not | BUILT | `tools/ncbi_transport.py:334`, seven families: `eutils` 3.0, `datasets` 5.0, `pubchem` 5.0, `variation` 1.0, `pubtator` 5.0, `litvar2` 5.0, `clinicaltrials` 5.0, each with its own env override |
| 21.1 | The 3-versus-10-versus-100 E-utilities conflict is not silently split | HONORED | `DEFAULT_EUTILS_REQUESTS_PER_SECOND = 3.0` at `tools/ncbi_transport.py:298`, with a comment stating it is the conservative floor and not a resolution of the conflict |
| 21.2 | One token bucket per family, shared process-wide across every concurrent query, no per-user sub-allocation | BUILT | `get_rate_limiter` at `tools/ncbi_transport.py:1083` is a lazily created process-wide registry keyed by family. NEVER MEASURED under actual concurrency, which is T-6.0-03 |
| 21.3 | At most 20 Layer 2 and Layer 3 tool calls per query. Plan drafts against the ceiling, Act enforces it as a hard stop, the loop moves to Write with whatever results exist | NOT BUILT | No constant, no counter and no enforcement anywhere in `src/`. `act_node` at `core/graph.py:3012` bounds cost (`cap_exceeded`) and nothing bounds call count |
| 21.4 | A bounded FIFO wait queue per family, a queue depth cap, and fail-fast carrying `rate_limited`, a `retry_after` estimate and the saturated family name | BUILT | `RateLimiter.acquire` at `tools/ncbi_transport.py:1002`; depths at `tools/ncbi_transport.py:1052`, a 5x multiple of each family's rate; `TransportRateLimitedError` at `tools/ncbi_transport.py:400` carries `family` and `retry_after` |
| 21.4 | The wait ceiling is tied to the calling query's own remaining latency budget, not one fixed number across every query class | NOT WIRED | The parameter exists: `execute_get(wait_ceiling_s=...)` at `tools/ncbi_transport.py:1217`, defaulting to `timeout_s` at line 1280. No caller in `core/graph.py` supplies a query-class-derived value, so every call in the shipped loop takes the per-call default. The only non-default call sites are inside `tools/ncbi_coordinate_overlap.py`, which passes its own parameter through unchanged |
| 21.4 | FIFO within a family, no user-tier prioritization in v1 | BUILT by construction | `RateLimiter` holds no priority concept |
| 21.4 | Single-instance v1, buckets in-process, moving to a shared store only if the deployment scales out | BUILT by construction | The registry is a module-level dict |
| 21.4 | Open question, named rather than silently settled: whether any call class jumps the FIFO queue | UNSETTLED | Nothing in the code implements a jump, which matches the spec's own stated v1 assumption. It stays an assumption until the product owner confirms it |
| Section 24 | The graph query service carries a hard row limit, a per-call timeout matching `cypher_query`'s 30 seconds, and a rate limit per caller | BUILT server-side | `tools/graph_http_transport.py` sends `row_limit` and `timeout_s` and raises `GraphRateLimitedError` on the service's own `rate_limited` code. Layer 1 has no client-side bucket by design: the graph is not an NCBI API and its limit is enforced at the service |

The short version: five of the eight Section 21 requirements are already shipped, one is
unsettled by the spec's own admission, and TWO are genuinely missing. This phase is smaller
than its board row implies, and the board row is not wrong: it names "per-layer throttling,
the bounded queue per API family, the 20-calls-per-query budget", and the first two of those
three arrived early because each tool phase needed its own pool to ship at all.

## The finding that reframes the phase

Reading the source for the 20-call ceiling turned up a comment asserting it exists.
`adapters/web_sse/app.py:231`, in the justification for `_MAX_CITATIONS_PER_RUN = 50`:

> a run's own citation count is already implicitly bounded by Section 21's
> at-most-20-tool-calls-per-query cap, so this is defense in depth, not the primary bound

There is no such cap. The sentence describes the bound this phase exists to build, in the
present tense, as the reason a neighbouring bound may be weaker than it looks. Filed as
F-6.0-01.

This is the fifth instance in this repository of one shape: a confident sentence describing
a check that is not there. Build phase 4.15 found four of them in one phase and its
conclusion was that the fix is DELETION rather than a better sentence, because a confident
sentence is where the next reader stops looking. Here the correct repair is not deletion,
since the claim becomes true once T-6.0-01 lands. It is ordering: the comment is corrected
in the same edit that makes it true, and never before.

## Goal contract

Written before any ticket was dispatched, per `.claude/rules/goal-contracts.md`.

Done when:

- A query may issue at most 20 Layer 2 and Layer 3 tool calls, the 21st is refused rather
  than issued, and the loop reaches Write with whatever results already exist rather than
  failing the run.
- A tool call's willingness to wait in its family's queue is read from the calling query's
  own remaining latency budget, so a `lookup` query waits less than a `deep_research` query
  for the same saturated pool.
- The process-wide sharing of each family's bucket is proven under real concurrency rather
  than asserted from the shape of the registry.
- Every claim in `adapters/web_sse/app.py:231` and in any docstring this phase touches is
  true at the moment it is written.

Verify:

- A premise gate that drives the real loop and asserts the 21st call never fires, written
  first and WATCHED FAILING before any implementation exists.
- A mutation case added in the same edit as every gate arm, per build phase 4.15's rule.
- A concurrency arm that runs N queries against one family and measures the observed
  request rate against that family's configured figure, so 21.2 is measured rather than read.
- The full Python suite, `ruff check` over the whole repository (no path, matching CI gate
  3), `isort --check-only` (matching CI gate 2, which `/verify` does not run), and
  `python tracker/check_doc_drift.py --check`.

Output: the tickets below, this file, and a pull request into `develop` with all four CI
gates green.

Constraints:

- No cost cap, timeout or queue-depth value changes without product-owner approval
  (`system-design-patterns` pattern 4, `tool-call-budgets`).
- The E-utilities throttle constant stays at the conservative live-verified 3.0 floor. The
  3-versus-10-versus-100 conflict is not resolved here, and `tool-call-budgets` requires
  asking before locking a different figure.
- Additive contract changes only, per `system-design-patterns` pattern 10.

Blocked-stop:

- If the 20-call ceiling cannot be enforced without changing an event-contract field's
  meaning, stop and report rather than shipping a breaking change under a v1 envelope.

## Tickets

| Ticket | Wave | Deliverable | Files it may touch | Status |
|---|---|---|---|---|
| T-6.0-00 | 0 | The premise gate for this phase, written first and watched failing | `tests/system_03_search_agent/core/test_rate_limit_concurrency_premise.py` | todo |
| T-6.0-01 | 1 | Section 21.3: the at-most-20 Layer 2 and Layer 3 calls per query budget. Plan drafts against the ceiling, Act enforces it as a hard stop and moves to Write with what exists. Corrects `adapters/web_sse/app.py:231` in the same edit that makes it true | `core/graph.py`, `adapters/web_sse/app.py` | todo |
| T-6.0-02 | 1 | Section 21.4: wire `wait_ceiling_s` to the calling query's remaining latency budget rather than the per-call timeout default | `core/graph.py`, `harness/harness.py`, `tools/*` call sites | todo |
| T-6.0-03 | 2 | Measure 21.2 rather than assert it: a concurrency arm proving one family's bucket is shared across concurrent queries, plus the mutation case that proves the arm can fail | `tests/system_03_search_agent/tools/` | todo |
| T-6.0-04 | 2 | Settle Section 21.4's own named open question on jump-the-queue behaviour, as a recorded decision rather than as code | `DECISIONS.md`, this file | todo |

## Coverage: what this phase does not cover

Stated in advance, per `.claude/rules/goal-contracts.md`: a verify surface must state its own
coverage, so a gap is arguable rather than invisible.

- Layer 1 has no client-side rate limiter and this phase does not add one. The graph query
  service enforces its own per-caller limit, and a second client-side bucket would bound the
  same call twice with two figures that can drift.
- Multi-instance rate limiting is out of scope by the spec's own words (21.4, single-instance
  v1). The buckets stay in-process.
- The E-utilities 3-versus-10-versus-100 conflict is not resolved here.
- Inbound rate limiting on `POST /v1/query`, per caller, is build phase 4.10's per-principal
  concurrent-run cap and is not re-opened here.
- F-4.0-A-14, the idle-socket abandonment bypass, was carried with "or build phase 6.0 if
  delivery-based liveness turns out to compose with rate limiting". It does not: it is a
  subscriber-liveness problem in `RunRegistry`, not a rate-limit problem, and folding it in
  would put a second redesign of concurrency-sensitive code in one round, which build phase
  2.1's retrospective measured as where the worst regressions hide.

## Findings

| ID | Severity | What | Found by | Status | Evidence |
|---|---|---|---|---|---|
| F-6.0-01 | minor | `adapters/web_sse/app.py:231` asserts in the present tense that Section 21's at-most-20-tool-calls-per-query cap already bounds a run's citation count, and uses that claim to justify `_MAX_CITATIONS_PER_RUN = 50` being defense in depth rather than the primary bound. No such cap exists anywhere in `src/`. The fifth instance in this repository of a confident sentence describing a check that is not there | lead, at phase open, 2026-08-31 | open | Grep for the cap across `src/` and `tests/` returns only this comment. `act_node` at `core/graph.py:3012` bounds cost and not call count. Owned by T-6.0-01, which corrects the comment in the same edit that makes it true |

## History

- 2026-08-31: Phase opened. Stages 1 and 2 of the cadence run: Section 25 dependencies (3.1,
  3.2, 3.3, 3.5) confirmed merged, `LEARNINGS.md` read filtered to rate limiting, concurrency
  and queue topics. The whole of Section 21 was measured against the shipped source before
  any ticket was written, which is what found F-6.0-01 and what established that five of
  eight requirements were already shipped by the tool phases.
