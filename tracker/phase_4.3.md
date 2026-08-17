# Phase 4.3: the GraphQL surface, a typed request/response client of the one core

Build phase 4.3 delivers a GraphQL API served by Strawberry from the same FastAPI process as the REST plus SSE surface, sharing its auth and its tools. It constructs no second agent path: every guarantee it appears to make (grounding, cite-or-refuse, cost suppression, the trust signal, the concurrent-run cap) is already made by the core, and this phase adds a typed schema and a resolver layer over it, never a weaker second route to any of them.

Depends on: build phase 4.0 (done, PR #39, merged), the only dependency Section 25 names. It also reads build phase 4.1 (the MCP server), which is the controlling precedent for a non-streaming surface that folds the event stream into one response, and build phase 4.2 (the CLI), whose review history is the reason this phase's fix rounds are partitioned by file rather than by finding.
Branch: `phase/4.3-graphql-api`
Spec: `requirements/Technical_specification.md` Section 13 (delivery surfaces, and the note that GraphQL's design is deliberately not restated there), Section 13.1 (the REST endpoints whose behavior this surface mirrors), Section 13.2 (the MCP surface, the controlling precedent for reading "the same Python tools"), Section 24 (a router mounted in the same FastAPI process), Section 25 (the build order row), Section 2.2 (the event envelope), Section 9.1 (`CitationPayload`, referenced not restated)
Reference: `docs/build/Build_workflow_cadence.md`, `LEARNINGS.md` filtered to adapter and premise-gate territory, `tracker/phase_4.1.md` and `tracker/phase_4.2.md`

## Three scope readings, stated before any code

The locked documents say less about this surface than about any other. Section 13 names GraphQL and then explicitly declines to specify it: its design "lives with Section 24's deployment topology (GraphQL, a router mounted in the same FastAPI process) and Section 25's build order (build phases 4.3, 4.4), not restated here." Section 13.5's per-surface summary table has no GraphQL row. The PRD contributes one sentence: "structured programmatic access to nested biomedical data, served via Strawberry from the same FastAPI app with shared auth and shared tools."

That leaves three real questions. Each is answered here, before any ticket, per `.claude/rules/v1-scope-boundary.md`'s instruction to name a substitution rather than quietly make one. None is a silent choice.

### 1. "Shared tools" means through the one core, not around it

The tempting reading of "shared tools" is a resolver per tool: a `gene` field backed by `ncbi_efetch`, a `variant` field backed by `ncbi_dbsnp`, and so on, which is what a GraphQL developer would build by reflex and what would most literally deliver "nested biomedical data."

Section 13.2 already ruled on this exact phrase, for MCP, and the ruling controls here:

> A raw per-tool passthrough would let an external agent bypass cite-or-refuse and the cost caps entirely, which is exactly the control the one-core, adapters-filter model (Decision A) exists to hold. The PRD's delivery-formats section describes MCP as wrapping "the same Python tools," which this section reads as wrapping them through the one core, not around it, since Decision A postdates and supersedes any looser reading.

The PRD uses the same phrase for GraphQL that Section 13.2 quotes and resolves for MCP, so the same resolution applies. A per-tool resolver layer would be a third entry point into the tool layer with no guardrail, no cite-or-refuse, no trust signal and no cost cap, reachable by any credential that can reach the schema. It is rejected on that basis, not on effort.

What "nested biomedical data" therefore means on this surface: the typed answer graph. A caller selects exactly the fields it wants from a cited answer, its citations, and each citation's provenance, which is genuine nested selection over biomedical data and is the thing GraphQL is actually better at than REST. It is not a tool passthrough.

### 2. The surface is registered-account only, with no guest path

Build phase 4.10 shipped an anonymous run path with a server-side guest allowance, and `get_caller` (the dependency every REST `/v1/*` route uses) resolves a guest token as happily as a user token. Wiring it into GraphQL would take one import.

This phase does not. GraphQL requires a registered account, matching both existing programmatic surfaces: MCP authenticates through `resolve_user_from_bearer_token` and has no guest path, and the CLI never holds a guest token at all. Three reasons, in order of weight:

- The guest allowance is not one function. It is an ordering: the free concurrent-run-cap precheck, then `spend_one_anonymous_run` with its four simultaneous bounds, then `create_run`, plus a refund callback wired into the registry for a guardrail refusal. `requirements/phase_6/Continuation_prompt.md` already records that the anonymous path's residual, after four review rounds, is a caller with many source addresses being bounded only by the day. Reproducing that ordering on a second surface doubles a surface the product owner has already accepted a known residual on.
- A guest token exists so a first-time visitor to a web page does not have to sign up before asking one question. A GraphQL client is a developer integration by construction. There is no first-contact anonymous visitor to serve here.
- The direction of the error is safe. Refusing a guest is a recoverable inconvenience with a clear next step; letting guest allowance be spent through an unhardened second path is not.

A guest token presented to this surface is therefore refused with a message that names the reason and the fix, never a generic 401 that reads as a broken credential.

### 3. It is request/response, and it does not carry a live stream

Section 13 puts GraphQL among the surfaces that "do not subscribe to the event stream." Strawberry supports subscriptions, and the run registry's `subscribe()` is multi-consumer and would serve one, so building it is available and is not built.

The reason is the same one Section 13.2 gives for MCP: this surface folds the stream into one structured response after `done`. A subscription would be a second live-stream transport with its own abandonment, resumption and cost-filtering semantics to keep in step with the SSE one, and Section 13 assigns live streaming to the surfaces that already have it. `run_registry.subscribe()` is still what the resolver consumes internally to build the folded response; nothing else may read a run's events.

## Phase premise (the done-when)

A caller with a registered account and a valid bearer access token POSTs a GraphQL document to `/graphql` and gets back the same cited answer the REST surface produces for the same question, as typed fields it selected, with an HTTP 200 and no `errors` array.

The answer carries its `trustSignal` (outcome, grounded, risk tier), its `citations` as full `CitationPayload` field-for-field with `sourceUrl` validated by the identical host-pinned, end-anchored `NCBI_SOURCE_URL_PATTERN` the REST surface uses, and the `runId` that names the run. A guardrail refusal is a successful response carrying a refusal outcome, never a transport error, because a refusal is the system working.

No cost figure ever reaches this surface. `sanitize_event_for_end_user` runs over every event before folding, exactly as REST does, and this surface additionally pins `operator_mode=False` in code the way the MCP surface does, so the schema has no field a cost figure could be selected into even if a future regression let one through.

Anything the surface drops or shortens, it says so. An answer truncated at the cap, a citation list cut at the cap, and a citations export that the server already marked truncated all carry an explicit disclosure field. This closes on a new surface the gap `X-Citations-Export-Truncated` currently fills with an HTTP response header, which GraphQL has no channel for.

The schema is bounded against a hostile document, not only against a hostile value. A query deeper than the configured limit, wider than the configured complexity budget, or repeating a field under many aliases is rejected before execution, and introspection and the interactive playground are off outside development. An unbounded GraphQL endpoint over an agent loop that spends real money on every call is the failure this phase most has to avoid: one document must never be able to start many runs.

A run created through GraphQL is owned by its creator. Reading or stopping a run through this surface enforces the identical 404-before-403 ordering `_get_owned_run` enforces for REST, so a run id is never an authorization bypass and never an existence oracle.

Every run this surface starts is attributed to it: `RequestContext.surface` gains a `"graphql"` member, and no GraphQL-originated run is ever recorded as `rest_sse`.

The verify surface is `tests/system_03_search_agent/adapters/graphql/test_phase_4_3_premise.py`, never a suite total, per `tracker/phase_3.1.md`'s standing rule and LEARNINGS.md's 2026-08-01 row. It drives the real schema through the real router mounted on the real FastAPI app, over `ASGITransport` in-process, asserting on real GraphQL response bodies. Every clause is mutation-proven: for each, the mutation that turns it red is named in the test file beside the clause.

### What this gate deliberately does NOT cover

Stated per `.claude/rules/goal-contracts.md`'s coverage-declaration discipline, and because build phase 3.2 measured that a gate's own coverage statement can be incomplete in exactly the direction that matters most.

- A live model and a live graph. The gate fakes the run's event production, as every adapter gate before it has, because the graph tunnel is unreachable from this environment. It proves the surface folds and bounds a stream correctly; it does not re-prove grounding, which is build phase 2.2's and 3.4's gate territory.
- A real socket. Every arm runs in-process over `ASGITransport`, so genuine network behavior, TCP resets and slow-client backpressure are not exercised.
- Load. The depth, complexity and alias bounds are proven by rejection of a crafted document, not by measuring resource use under many concurrent documents. Whether the configured numbers are the right numbers under real load is build phase 6.0's territory.
- Persisted queries and an operation allowlist. Not built, not claimed.
- Any client library's behavior. The gate speaks raw HTTP with a GraphQL body; it does not exercise Apollo, Relay, or any other client's assumptions.
- Subscriptions. Not built by decision 3 above, so not covered.

## Pre-build source read, done before any ticket

Per this repository's standing pre-build-probe pattern (phases 3.2, 3.3, 3.5, 4.0, 4.1, 4.2) and `.claude/rules/attack-the-constraint.md`'s "read the input first". Three parallel read-only researchers mapped the terrain before this file was written.

| Read | Finding that changes the build |
|------|-------------------------------|
| `adapters/web_sse/app.py`, `auth/dependencies.py` | `get_caller` resolves users AND guests; `get_current_user` and `resolve_user_from_bearer_token` are the registered-only paths. Decision 2 above turns on this distinction |
| `contracts/query.py` | `RequestContext.surface` is a closed 4-value `Literal` with no `"graphql"` member. Adding one is additive and v1-legal, and reusing `"rest_sse"` would misattribute every run this surface starts |
| `adapters/web_sse/app.py` citations route | Two facts reach the caller as HTTP response headers, `X-Run-Cancelled` and `X-Citations-Export-Truncated`. GraphQL has no header channel, so both need explicit schema fields or the disclosure silently vanishes on this surface |
| `core/run_registry.py` | The REST ordering is precheck the concurrent-run cap, then spend, then `create_run`. `create_run` is authoritative; the precheck exists so a refused creation never spends an allowance |
| `adapters/mcp/server.py` | The precedent for folding: `create_run` then `subscribe` on the same run, `operator_mode` hard-pinned `False` in code, caps applied twice (as a field constraint and defensively while folding), truncation disclosed by name, and a wall-clock bound on the whole fold loop independent of the harness's own step timeouts |
| `adapters/cli/render.py` | `_sanitize_untrusted` is CLI-local, not shared. Nothing to import. Whether this surface needs an equivalent depends on what consumes it, which is finding F-4.1-A-10's open question arriving on a third surface |
| `tracker/phase_4.2.md` | Exception catches by enumerated subclass list drifted out of sync with the raiser three separate times in one phase. Any error-mapping layer here catches the base class from day one |

## Two carried decisions folded into this phase

Both are already decided, need no product decision, and sit directly in the code this phase touches. Folding them in here rather than deferring again is deliberate: `requirements/phase_6/Continuation_prompt.md` records that eight such items accumulated across six phases before being cleared in one session, and the way they accumulated was each phase deciding it was somebody else's next ticket.

- Report `risk_tier` as `unknown` rather than a hardcoded `low` when no assessment ran. Decided, owner "next backend ticket". It is in this phase's path because `trustSignal.riskTier` is a field this surface exposes, and F-4.1-J3-02 ("synthetic risk_tier still asserted from nothing") is the same defect already open on the MCP surface. Exposing a known-wrong value through a third surface is not a neutral deferral. Blast radius checked before folding it in rather than assumed: both hardcoded sites (`core/graph.py:3961`, `core/graph.py:4229`) are refusal paths, emitting `outcome="refuse", grounded=False`, so no assessment ran at either and `outcome` already carries the meaning a consumer needs. `synthesis/trust.py:224`'s `if self.risk_tier == "low"` reads a computed trust dataclass, not the emitted payload, so it is not on this path.
- The concurrent-run cap no longer equal to the free allowance, and its message branching on which bound was hit. Decided, owner "next backend ticket". It is in this phase's path because this surface must perform the same cap precheck, and a message that cannot say which of two bounds was hit is exactly the non-actionable error `tool-call-budgets.md` forbids. Today `DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 5` (`core/run_registry.py:204`) and `FREE_RUN_ALLOWANCE = 5` (`data/guest_sessions.py:60`) are the same number, so a guest who hits a wall cannot be told which wall it was.

The third decided backend item, the one withholding rule for `pubtator_annotate` and `clinicaltrials_search`, is NOT folded in. This phase touches no tool code, and pulling it in would mean editing tool modules in a delivery-surface phase for no reason but proximity. It stays with its named owner.

## The library, verified against the installed version rather than the docs

`strawberry-graphql==0.324.0`, pinned exactly. Supply-chain checks ran before install, per `.claude/rules/supply-chain-security.md`: no compromise report (the only hits were OSV false-positive malware reports withdrawn in May 2026, which named Strawberry among many packages), MIT licensed, the wheel carries no `.data/scripts`, no compiled extension and no `.pth`, so it has no install-time execution surface.

One transitive dependency is worth naming rather than absorbing silently: `cross-web>=0.6.0` is a required (non-extra) dependency, published first in 2026, six releases, authored by the same maintainer as Strawberry itself, depending only on `typing-extensions`. Its wheel is likewise free of any install-time execution surface. It is a young, single-maintainer package entering the backend, which is a real if small supply-chain widening, and it is unavoidable without avoiding Strawberry, which Section 25 names by product.

The published docs available to research were a 0.282 mirror, forty-odd releases behind the pinned version, so every API name this phase depends on was probed directly against the installed 0.324.0 rather than trusted from documentation. All confirmed present: `DisableIntrospection`, `QueryDepthLimiter(max_depth, callback, should_ignore)`, `MaxAliasesLimiter(max_alias_count)`, `MaxTokensLimiter(max_token_count)`, `MaskErrors(should_mask_error, error_message)`, `AddValidationRules`, and `SchemaExtension` with the hooks `on_execute`, `on_operation`, `on_parse`, `on_stream_result`, `on_validate`. Introspection blocking was confirmed working, not assumed.

Four `GraphQLRouter` and `StrawberryConfig` defaults are wrong for this surface, and each is a ticket below rather than a note:

| Default | Verified value | Why it is wrong here |
|---------|----------------|----------------------|
| `graphql_ide` | `'graphiql'` | Serves an interactive IDE. Off outside development |
| `allow_queries_via_get` | `True` | A GET-able operation is cacheable, referrer-loggable and CSRF-reachable, and on this surface an operation spends real money |
| `subscription_protocols` | `('graphql-transport-ws', 'graphql-ws')` | This phase builds no subscriptions by scope reading 3, so the surface must not advertise or accept a WebSocket upgrade path nobody designed |
| `disable_field_suggestions` | `False` | GraphQL's "Did you mean ...?" suggestions enumerate the schema field by field even with introspection fully disabled. Disabling introspection without this is a lock on the front door and an open window |

Two bounds this repository's own rules require do NOT exist in the library and must be built: a per-request timeout (`tool-call-budgets.md` requires a declared timeout on every call path) and a cost-or-complexity budget beyond depth, alias and token counts (`system-design-patterns.md` pattern 4). Both build on `SchemaExtension`. Persisted-query allowlisting also does not exist and is explicitly not built.

## Ticket map

Partitioned by FILE, not by concern, and no two tickets name the same file. This is build phase 4.2's central finding applied at dispatch time rather than at fix time: two agents editing one file are each individually correct and structurally blind to the other, so two correct changes compose into a defect no reviewer of either one can see.

The integration seam is deliberately NOT parallelized. `schema.py`, `router.py` and the `app.py` mount are held by the lead and written after the builders return, because F-4.2-08 was exactly a seam defect: two builders each satisfied their own ticket, and the interface between them was never wired, so every typed error fell through to a generic message.

| Ticket | Deliverable | Files it may touch | Depends on |
|--------|-------------|--------------------|------------|
| T-4.3-01 | The GraphQL type layer: one type per payload this surface exposes, mirroring `contracts/events.py` field for field, `sourceUrl` carrying the identical host-pinned end-anchored pattern, every string bounded and every list capped | `src/system_03_search_agent/adapters/graphql/types.py` | fixed interfaces below |
| T-4.3-02 | The fold: a run's event stream folded into one typed result after `done`, with the caps applied twice (as a field constraint and defensively while folding), truncation disclosed by name, grounding and claim-scoped trust aggregated, a fixed literal per fatal `error_class`, and a wall-clock bound on the whole loop | `src/system_03_search_agent/adapters/graphql/fold.py` | T-4.3-01's interface |
| T-4.3-03 | Auth and context: a `context_getter` that runs the registered-only auth path, puts the resolved principal on the context, and refuses a guest token with a message naming the reason and the fix | `src/system_03_search_agent/adapters/graphql/context.py` | fixed interfaces below |
| T-4.3-04 | The security layer: the four hardened settings above, the depth, alias and token limiters, `MaskErrors` with an allowlist for this surface's own exception base class, a per-request timeout extension, and a complexity budget extension | `src/system_03_search_agent/adapters/graphql/security.py` | fixed interfaces below |
| T-4.3-05 | Shared-contract edits: `"graphql"` added to `RequestContext.surface`; `risk_tier="unknown"` at both refusal sites plus every hand-maintained consumer copy including the frontend's runtime type guard; the concurrent-run cap decoupled from the free allowance and its error carrying which bound was hit, with each existing surface's catch site updated to branch on it | `src/system_03_search_agent/contracts/query.py`, `src/system_03_search_agent/core/graph.py`, `src/system_03_search_agent/core/run_registry.py`, `src/system_03_search_agent/data/guest_sessions.py`, `src/system_03_search_agent/adapters/mcp/server.py`, `frontend/src/` type guards | none |
| T-4.3-06 | Packaging: the pinned dependency in both `pyproject.toml` and `requirements.txt`, and the new package in the setuptools package list | `pyproject.toml`, `requirements.txt` | none |
| T-4.3-07 | The integration seam, LEAD-OWNED, written after 01 to 06 land: the `Query` and `Mutation` roots and their resolvers, the hardened router, and the mount on the existing app | `src/system_03_search_agent/adapters/graphql/schema.py`, `src/system_03_search_agent/adapters/graphql/router.py`, `src/system_03_search_agent/adapters/web_sse/app.py` | 01 to 06 |

### The interfaces, fixed by the lead before dispatch

Builders write against these names and do not negotiate them, so a module can be written and unit-tested before its siblings exist on disk. Cross-module imports are lazy or `TYPE_CHECKING`-only, the pattern build phase 4.2 used for the same reason.

The operation set, four operations, each mirroring an existing REST behavior and adding no new capability:

```graphql
type Query {
  run(runId: ID!): RunResult!            # the folded state of a run this caller owns
  citations(runId: ID!): CitationsExport! # mirrors GET /v1/query/{run_id}/citations
}

type Mutation {
  ask(input: AskInput!): AskResult!      # create a run, fold it to completion
  stopRun(runId: ID!): StopRunResult!    # mirrors POST /v1/query/{run_id}/stop, idempotent
}
```

Module contracts:

- `types.py` exposes `Citation`, `TrustSignal`, `AskResult`, `RunResult`, `CitationsExport`, `StopRunResult`, `AskInput`, and `Disclosures`. Every field name derives from the Pydantic payload field it mirrors; nothing is renamed, invented, or dropped.
- `fold.py` exposes `async def fold_run(run_id: str, *, operator_mode: bool = False) -> AskResult`, subscribing through `default_registry.subscribe`, and `def fold_citations(entry) -> CitationsExport`. It never calls `core.run.run_streaming`.
- `context.py` exposes `class GraphQLContext(BaseContext)` carrying `principal` and `request`, and `async def get_context(...) -> GraphQLContext` as the `context_getter`. It raises this surface's own `GraphQLAuthError`.
- `security.py` exposes `SCHEMA_EXTENSIONS`, `ROUTER_SETTINGS`, `STRAWBERRY_CONFIG`, `RequestTimeoutExtension`, `ComplexityBudgetExtension`, and every bound as a named module constant.
- Every module defines its own exception base class and every catch dispatches on that base, never on an enumerated subclass list. This is not stylistic: an enumerated catch list drifted out of sync with its raiser three separate times inside build phase 4.2 alone.

### Two duplications accepted, with reasons

- The fold logic duplicates the MCP server's, which earned its correctness across three judge rounds and an adversary pass (uncited-answer grounding, claim-scoped trust aggregation, truncation disclosure, fixed-literal fatal-error disclosure). Extracting a shared fold would be the better architecture and is NOT done here, because it would refactor a shipped, heavily-reviewed surface inside a phase whose review attention belongs on a new one. The mitigation is that each of those four hard-won MCP findings becomes a clause of this phase's blocking gate, so they are front-loaded rather than rediscovered. Filed below as a finding with an owner, since an unconsolidated duplication is a real future divergence risk, not a closed matter.
- The bounds constants are surface-local, matching how MCP and the CLI each hold their own. Only `contracts/events.py`'s payload models and `NCBI_SOURCE_URL_PATTERN` are shared, and those are reused verbatim.

## Premise gate design

The gate is `tests/system_03_search_agent/adapters/graphql/test_phase_4_3_premise.py`, landed alone and first, watched failing with a uniform `ModuleNotFoundError` through an autouse import-guard fixture, the pattern both prior adapter phases used. Every clause names, beside itself in the file, the mutation that turns it red; a clause that cannot be made to fail is not evidence.

| Arm | What it proves | Mutation that must turn it red |
|-----|----------------|-------------------------------|
| Golden path | A registered caller's `ask` returns the answer, its citations, its trust signal and the run id, HTTP 200, no `errors` | Drop any field from the fold |
| Refusal is a success | A guardrail refusal returns 200 with a refusal outcome, never a transport error and never an empty `data` | Route refusals through the error array |
| Cost can never appear | No cost figure in any response, with `operator_mode` pinned `False` in code and the sanitizer run over every event | Unpin `operator_mode`, or skip the sanitizer |
| Guest refused, actionably | A valid guest token is refused with a message naming the reason and the fix, distinguishable from an invalid credential | Swap the registered-only path for `get_caller` |
| Ownership, 404 before 403 | Another caller's run id yields the same answer as an unknown run id, so a run id is neither a bypass nor an existence oracle | Reverse the ordering, or drop the owner check |
| Depth bound | A document nested past the limit is rejected before execution | Raise the limit, or drop the extension |
| Alias bound | A document repeating a field under many aliases is rejected | Drop `MaxAliasesLimiter` |
| Token bound | An oversized document is rejected | Drop `MaxTokensLimiter` |
| Complexity bound | A document within depth and alias bounds but demanding many folds is rejected, so one document can never start many runs | Drop the complexity extension |
| Timeout bound | A request exceeding the per-request budget is bounded and returns an actionable error | Drop the timeout extension |
| Introspection off | An introspection query is refused, AND a misspelled field name returns no "did you mean" suggestion | Re-enable either introspection or field suggestions |
| No IDE, no GET, no WS | The IDE is absent, a query over GET is refused, and no subscription protocol is advertised | Restore any of the three defaults |
| Errors are masked | An internal exception surfaces as a stable masked message with a code, never as internal text | Remove `MaskErrors` |
| Every disclosure survives | A truncated answer, an over-cap citation list, a truncated export and a cancelled run each carry an explicit field, since GraphQL has no response-header channel | Drop any disclosure field |
| Surface attribution | A run started here records `surface="graphql"`, never `rest_sse` | Reuse an existing surface value |
| `sourceUrl` is host-pinned | A citation whose URL is off-host or carries a control byte cannot be returned | Loosen the pattern to `^https://` |
| The four MCP fold findings | Uncited-answer grounding, claim-scoped trust aggregation, truncation disclosed by name, and a fixed literal per fatal `error_class` | Each has its own named mutation |

## Findings

| ID | Severity | Description | State | Reason | Raised by |
|----|----------|-------------|-------|--------|-----------|

## History

| When | Who | What |
|------|-----|------|
| 2026-08-17 | Lead | Phase opened. Branch cut. Three researchers dispatched. Three scope readings recorded before any ticket, since the locked spec deliberately does not specify this surface |
