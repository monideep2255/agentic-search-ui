# Build phase 4.11: the read-only HTTPS graph query service

Branch: `phase/4.11-graph-query-service`
Spec: `requirements/Technical_specification.md` Section 24 ("The read-only HTTPS graph query service", plus the Layer 1 row of the environment table), Section 6.1 (`cypher_query`'s own budget), Decision D (the v1 Layer 1 transport), `.claude/rules/tool-call-budgets.md` (the three-part service budget)
Depends on: 2.1 (`cypher_query` over Layer 1), merged since build phase 2.1
Opened: 2026-08-22

Not in Section 25. This is a board-level insertion, made 2026-08-21 by product-owner decision and logged in `DECISIONS.md`, the same deliberate exception build phases 4.8, 4.10 and 4.12 already set. It exists because Section 24 specifies the service in full and says `GRAPH_QUERY_TOKEN`'s real value is populated "when the service is built (Section 25 build order)", while Section 25 never assigns it to any phase. One locked section points at another for something that is not there, and this phase closes that dangling reference.

## What this phase delivers

A single read-only HTTPS endpoint co-located on the Hetzner CPX42 box in front of the AGE graph, and the client-side transport swap that makes `cypher_query` use it. Per Section 24:

- Location: on the Hetzner box itself. The hop to Postgres stays on localhost; the only network hop is Railway (or a developer machine) to Hetzner over HTTPS.
- Surface: one endpoint taking an already-validated, already-parameterized Cypher payload. Never free-form Cypher text over the wire in the sense of text nobody has checked.
- Defense in depth: the service re-runs the forbidden-keyword and edge-label checks server-side, so a bug in the client-side validator is not the only thing between a request and the database.
- Credential: the existing read-only `kg_reader` role, so a validator bug still cannot produce a write.
- Auth: a bearer credential, `GRAPH_QUERY_TOKEN`, because Railway does not guarantee a static egress IP so an IP allowlist alone is insufficient.
- Limits: a hard row limit, a per-call timeout matching `cypher_query`'s own 30 seconds, and a rate limit per caller.
- Transport: TLS through an automatic-HTTPS reverse proxy. The database port itself never opens to the internet.
- Runtime: a systemd service on the box, stateless, logging every call.

What it deletes: the hand-opened SSH local port-forward that has gated every live test in this repository since build phase 2.1.

## Why this phase jumped the queue

Measurement, not preference. The tunnel is a single point of failure for this project's entire live verification surface, and build phase 4.6 paid for it twice in one week: down for two days earlier in the week, then down again through all three of that phase's review rounds, so 4.6 merged with three live premise-gate arms UNRUN and accepted as such. The argument for taking 4.11 sooner was made and rejected once, on 2026-08-21; what changed is that 4.6 then demonstrated the cost instead of predicting it.

## Product-owner authorization, recorded because it is not a default

`.claude/rules/ai-security-standards.md` states that an agent never autonomously modifies infrastructure. This phase does: it installs a reverse proxy and a systemd unit on a live external box and opens a public port on the machine holding the graph. The product owner was asked before any ticket existed, given three scoped options, and chose "build and deploy live" on 2026-08-22. That authorization covers this phase's deployment steps and nothing beyond them.

## The goal contract

Written before any ticket, per `.claude/rules/goal-contracts.md`.

- Done when: `cypher_query` reaches the live Layer 1 graph over HTTPS with no SSH tunnel open anywhere, returning results byte-identical to what the psycopg2 path returns for the same query; the service rejects, server-side, every class of payload the client-side validator rejects, plus an absent or wrong bearer token, an over-large row limit, and a caller over its rate limit; the graph's Postgres port is still unreachable from the internet; and `tracker/preflight.py` can verify the graph transport without a person opening an SSH session.
- Verify: this phase's premise gate, every arm mutation-proven, run live against the deployed service with `RUN_PREMISE_GATE=1`; a byte-equality assertion comparing psycopg2 rows and HTTPS rows for the same query on the same graph; a probe from this machine proving `46.225.128.133:5432` is still refused while 443 answers; the Python suite against a re-measured baseline; `ruff check` on every file touched; `python tracker/check_doc_drift.py --check`; and an independent judge and adversary round before merge.
- Output: the branch `phase/4.11-graph-query-service`, one pull request, and a running service on the Hetzner box with a runbook that can rebuild it from nothing.
- Constraints: the service never acquires a write credential; `kg_reader` stays the only role it uses. `GRAPH_QUERY_TOKEN`'s value never appears in a log line, an exception string, a test fixture, a commit, or this file. `cypher_query`'s schema and its callers do not change, which is the two-way door Decision D promised. Every gate in `production-standards` holds, and the per-call timeout matches Section 6.1's 30 seconds rather than being invented here.
- Blocked-stop: anything that would require a write to the graph, a change to the `kg_reader` role's privileges, or opening a port other than 443. Any of those stops the phase and returns to the product owner.

## What the code actually looks like at open, measured rather than assumed

Six facts found by reading the source before decomposing. Three of them change a ticket.

- The swap point is ONE function. `graph_connection.execute_cypher` is the only I/O boundary, and `cypher_query.py` is its only caller in `src/` (three call sites, all passing it as a callable). So the transport swap happens inside `execute_cypher` itself and no caller changes, which is exactly the "no change to its schema or callers" Section 24 promises.
- `validate_cypher` is trivially deployable. Its only imports are `re`, `dataclasses`, and `graph_schema_constants`, which is pure constants. The service can run the REAL validator rather than a re-implementation that drifts.
- Therefore the service should reuse `graph_connection` too, not re-implement execution. The service becomes a thin HTTPS shell around the same execution core running against localhost, and the PREPARE/EXECUTE/DEALLOCATE mechanics, the `enable_seqscan = off` fix, the memory guards, and the agtype handling are all inherited rather than rewritten.
- That creates a recursion hazard worth naming before it is built: if `GRAPH_QUERY_URL` were ever set in the service's own environment, the service would call itself. The systemd unit must clear it and the app must assert it is unset at startup.
- `execute_cypher` returns RAW agtype wire text, not parsed values (`'{"id":..., "label":"Gene", ...}::vertex'`), and `cypher_provenance` parses it downstream. Build phase 2.1's worst defect was 716 passing tests over a tool that discarded exactly these strings. So the wire format is not "some JSON of the results", it is a byte-faithful carrier of what psycopg2 handed back, and that is the phase's central gate arm.
- The box at open: Ubuntu 24.04.3, Python 3.12.3, no Caddy, no nginx, no Docker, only ports 22 and 53 listening, Postgres bound to `127.0.0.1:5432` only, disk 92 percent full with 26G free. There is no domain name anywhere in the project, but the Hetzner rDNS name `static.133.128.225.46.clients.your-server.de` forward-resolves to the box, so automatic HTTPS has a real hostname without buying a domain.

## The trap this phase can most easily ship

Three, and each has a named ancestor in this repository.

The first is a gate that supplies the thing under test. Build phase 4.5's F-4.5-09 shipped an inert feature while eight arms passed, because every arm handed the feature its input. The identical shape here is a gate that asserts the service returns well-formed JSON for a payload the gate itself constructed. At least one arm must run the REAL `cypher_query` pipeline end to end over HTTPS against the real graph and compare the result to the psycopg2 path.

The second is defense in depth that is depth in name only. Section 24 asks the service to re-run the checks server-side precisely so a client bug is not the only barrier. A service that trusts a client-supplied `validated: true` flag, or that only re-checks payloads the client already rejected, has the shape and none of the property. The arms must send payloads that a compromised or buggy CLIENT would send, constructed to bypass the client entirely.

The third is a stated omission covering the default path. Build phase 4.4 shipped a critical because five of six gate cases passed an explicit edge-label list and nothing exercised the default invocation. Here the equivalent is testing the service only through the client transport, which normalizes everything before sending. Arms must also hit the endpoint directly with a raw HTTP client.

## Scope seam with build phase 4.12

4.12 is the Railway demo deployment and it owns cutting Railway's own environment over from `GRAPH_PG_*` to `GRAPH_QUERY_URL` plus `GRAPH_QUERY_TOKEN`. This phase owns the service, the client transport, and the local `.env` cutover that lets development and the premise gates stop using the tunnel. Setting Railway variables is 4.12's ticket, not this one, and there is no Railway project yet to set them on.

The security scan's trigger is exposure and this phase opens a public HTTPS port. It is not a public URL for the PRODUCT, and no user-facing surface is reachable through it: the endpoint serves one authenticated caller with a bearer credential, over a read-only role, in front of data that is already public NCBI content. The scan stays attached to 4.12, where a person who is not the product owner can first reach the product. This is recorded as a judgment made deliberately rather than an omission, and the adversary should test it.

## Tickets

### T-4.11-01: Premise gate for the HTTPS graph query service

Status: in-review
Refine: refined
Depends on: nothing
Spec: Section 24; `docs/build/Build_workflow_cadence.md` stage 5

Written first and watched failing. The gate's central premise is NOT that an HTTP endpoint answers. It is that swapping the transport changes nothing observable about what `cypher_query` returns, while adding a server-side barrier that holds against a caller that bypasses the client entirely.

Acceptance criteria:
- [ ] Byte-equality: the same Cypher and params, run through the psycopg2 path and through the HTTPS path against the same live graph, return identical rows and identical `total_available`. Compared on the raw agtype strings, not on parsed values, because parsing is what build phase 2.1 discovered was hiding the defect
- [ ] The full `cypher_query` pipeline runs end to end over HTTPS against the real graph and produces citations, asserted on the citations, never on the absence of an exception
- [ ] Server-side rejection is exercised by a RAW HTTP client that never touches the client-side validator, for each of: a write clause, an unknown edge label, a missing edge label, an over-large `row_limit`, and a malformed `as_clause`. A payload that the client would have rejected is not evidence for this arm
- [ ] Auth: no bearer header, a wrong bearer, and a correctly-shaped-but-wrong bearer each get a rejection, and the rejection body carries no detail about the token
- [ ] The rate limit fires for one caller and is asserted by a `rate_limited` response carrying `retry_after`, not by a bare non-200
- [ ] The per-call timeout is asserted at the SERVICE, by a query that outruns it, returning the actionable timeout message rather than a bare 500
- [ ] Transport dispatch: with `GRAPH_QUERY_URL` set, `execute_cypher` uses HTTP and does NOT open a psycopg2 connection; with it unset, it uses psycopg2. Asserted by observing which transport was used, not by the call succeeding
- [ ] Passing a `connection_factory` while `GRAPH_QUERY_URL` is set raises loudly rather than silently ignoring one of the two
- [ ] Every GraphError type still reaches the caller: connection, auth, timeout, and the generic query failure each map from an HTTPS-layer failure to the same typed error `cypher_query` already handles
- [ ] Exposure: `46.225.128.133:5432` is still refused from this machine while 443 answers, asserted by a live probe
- [ ] The token never appears in any log line, error body, or exception string, asserted by planting the real token value and grepping the service's own log output and every response body
- [ ] Every arm is mutation-proven: break the control the arm exists to catch and watch it go red, recorded in the ticket history
- [ ] The gate states its own coverage in its own file: which shapes it exercises and which it deliberately omits, per `.claude/rules/goal-contracts.md`

### T-4.11-02: The service application

Status: in-review
Refine: refined
Depends on: T-4.11-01
Spec: Section 24; `.claude/rules/tool-call-budgets.md`
Files: `services/graph_query_service/app.py`, `services/graph_query_service/README.md`, tests under `tests/services/graph_query_service/`

A FastAPI application exposing one POST endpoint. It reuses this repository's own `cypher_validator` and `graph_connection` rather than re-implementing either, so the server-side checks cannot drift from the client-side ones by construction.

Acceptance criteria:
- [ ] One endpoint, taking `cypher`, `params`, `row_limit`, `timeout_s`, `as_clause`, through a Pydantic model that forbids extra fields
- [ ] Bearer auth read from `GRAPH_QUERY_TOKEN` in the service's environment, compared in constant time, rejecting before any parsing or database work
- [ ] The service refuses to start when `GRAPH_QUERY_TOKEN` is unset or empty, rather than starting with auth effectively off
- [ ] The service refuses to start when `GRAPH_QUERY_URL` is set in its own environment, closing the recursion hazard
- [ ] `validate_cypher` is re-run server-side on the received `cypher` before execution, and its rejection reason is returned to the caller as a machine-readable code
- [ ] `as_clause` is re-validated server-side against the same pattern `graph_connection` uses
- [ ] `row_limit` is clamped server-side to `MAX_ROW_LIMIT` and `timeout_s` clamped to `CYPHER_QUERY_TIMEOUT_SECONDS`, so a caller cannot raise either past the tool's own budget
- [ ] A per-caller rate limit with a bounded FIFO wait and fail-fast, returning `rate_limited` with `retry_after` and the saturated family, per `tool-call-budgets`
- [ ] Every call is logged with what was queried, when, and the caller, and never with the token value. Append-only, one writer
- [ ] Errors are actionable per the retry-safety gate: each says what the next step is, never a bare "failed"
- [ ] Rows are returned exactly as psycopg2 produced them, with the wire encoding documented in the module docstring
- [ ] Tests for valid, invalid, and null input on the endpoint, per `production-standards`

### T-4.11-03: The client transport and the dispatch inside execute_cypher

Status: in-review
Refine: refined
Depends on: T-4.11-01
Spec: Section 24; Section 6.1
Files: `src/system_03_search_agent/tools/graph_http_transport.py`, `src/system_03_search_agent/tools/graph_connection.py`, tests under `tests/system_03_search_agent/tools/`

Acceptance criteria:
- [ ] A new module owning the HTTPS call: bearer header from `GRAPH_QUERY_TOKEN`, the 30-second budget from `CYPHER_QUERY_TIMEOUT_SECONDS`, and no retry that would double a caller's rate-limit spend
- [ ] `execute_cypher` keeps its exact signature and return type, and dispatches on `GRAPH_QUERY_URL` being non-empty
- [ ] Passing `connection_factory` while `GRAPH_QUERY_URL` is set raises a typed error rather than silently ignoring either
- [ ] Every HTTPS-layer failure maps into the existing `GraphError` family: a connection refusal and a DNS failure to `GraphConnectionError`, a 401 or 403 to `GraphAuthError`, a timeout or a service timeout body to `GraphTimeoutError`, everything else to `GraphConnectionError` with an actionable message
- [ ] A `rate_limited` response surfaces as a typed error carrying `retry_after`, so the Act step can decide rather than guess
- [ ] The token is redacted from every message this module can raise, reusing the existing `_redact` discipline rather than a second one
- [ ] The docstring's Depends on / Reads / Writes block is complete, per `.claude/rules/dependency-tracking.md`

### T-4.11-04: Deployment to the Hetzner box, and the runbook

Status: in-review
Refine: refined
Depends on: T-4.11-02
Spec: Section 24
Files: `services/graph_query_service/deploy/`, `docs/data-engineering/Graph_query_service_runbook.md`

The product owner authorized live deployment on 2026-08-22. Everything installed on the box is reproducible from files in this repository; nothing is hand-edited on the server without landing here too.

Acceptance criteria:
- [ ] A systemd unit running the service as a non-root user, bound to localhost only, with `GRAPH_QUERY_URL` explicitly cleared
- [ ] An automatic-HTTPS reverse proxy in front of it, terminating TLS on 443 and proxying to localhost. If certificate issuance fails on the rDNS hostname, the fallback is recorded as a decision rather than worked around silently
- [ ] `GRAPH_QUERY_TOKEN` generated on the box with a CSPRNG, readable only by the service user, never committed and never printed into this repository
- [ ] The Postgres port stays closed to the internet, verified after deployment rather than assumed
- [ ] A deploy script that copies the service and its two vendored dependencies from this repository, so a redeploy cannot drift from the committed source
- [ ] A drift check asserting the deployed validator and schema constants are byte-identical to this repository's copies
- [ ] A runbook that can rebuild the service from nothing: install, configure, start, verify, roll back, and read the logs
- [ ] The service survives a reboot, verified by restarting the unit rather than by reading the unit file

### T-4.11-05: Cutover, and preflight without a tunnel

Status: in-review
Refine: refined
Depends on: T-4.11-03, T-4.11-04
Spec: Section 24's environment table
Files: `env.example`, `tracker/preflight.py`, `.env` (local, uncommitted)

Acceptance criteria:
- [ ] `env.example`'s Layer 1 block documents which of the two transports is live and what setting `GRAPH_QUERY_URL` does to the other
- [ ] `tracker/preflight.py` probes the HTTPS service when `GRAPH_QUERY_URL` is set, and reports it as a distinct transport rather than reporting the old TCP port
- [ ] A `skipped` result stays distinguishable from a pass, which is the property F-4.5-01 restored and which must not regress
- [ ] The local `.env` is cut over and a full live premise-gate run passes with NO SSH tunnel open anywhere, which is the phase's whole point
- [ ] The three live arms build phase 4.6 merged unrun (P1b, P9, P12) are re-run over the new transport and their result recorded, since removing the reason they were skipped is what this phase was pulled forward to do

## Findings

The shared ledger for this phase, per `.claude/skills/bossman-mode/SKILL.md`'s shared-ledger coordination. The adversary files here, a fix agent triages, only the judge closes.

| ID | Round | Severity | Where | Finding | State | Reason | History |
|----|-------|----------|-------|---------|-------|--------|---------|
| F-4.11-01 | 0 | major | `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, arm P10, written by the lead | The exposure arm was VACUOUS in the environment it runs in. It asserted `pytest.raises(OSError)` on a connection to the public 5432, and this sandbox answers every unreachable destination with a timeout rather than a refusal, which is an OSError. Measured the same day: `github.com:12345`, a port GitHub neither serves nor drops, also times out here. So the arm passed on a sandbox denial and would have gone on passing with the database port wide open | fixed | Rebuilt so the two outcomes are distinguishable inside one run: the service's own 443 must CONNECT from the same machine first, which establishes the path to the host is open, so a timeout on 5432 in the same seconds is attributable to the host. A second arm, P10c, reads the binding directly on the box with `ss`, so the two fail for independent reasons | 2026-08-22 lead: filed and fixed the same session, before any builder finished. Found while diagnosing a supposed firewall blocker that did not exist |
| F-4.11-J-01 | 1 | CRITICAL | `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, the `requires_graph` marker | THE PHASE TURNED OFF ITS OWN GATE BY SUCCEEDING. `requires_graph` gates 12 arms on the psycopg2 socket, and the cutover in T-4.11-05 retired that socket, so those 12 arms now SKIP on the configuration this phase ships. Five of them are the defense-in-depth arms, the ones proving the service re-runs the validator server-side. Seven never needed a graph at all: the judge proved it by running them with `GRAPH_PG_PORT=443`, a socket that is not Postgres, where they pass | open | The lead reported "23 passed, 12 skipped with no tunnel" as evidence the phase was verified, and presented the skips as the transport-comparison arms only. That was wrong and the judge's proof is direct. A gate whose coverage silently shrinks when the product succeeds is worse than one that fails, because nothing reports the shrinkage | 2026-08-22 judge: filed with a mutation proof. 2026-08-22 lead: accepted, and the earlier evidence claim corrected to the product owner |
| F-4.11-J-02 | 1 | major | The same file, arm P1, the byte-equality arm | The arm that carries this phase's central premise, that swapping the transport changes nothing observable, is now structurally unrunnable on the shipped configuration and reports green by skipping. It needs both transports and the cutover retired one | open | Follows from F-4.11-J-01 and is listed separately because it is the ONE arm the whole phase rests on. It did pass live before the cutover, which is real evidence, but it cannot be re-demonstrated by anyone who checks out this branch | 2026-08-22 judge: filed |
| F-4.11-J-03 | 1 | major | `services/graph_query_service/app.py`, the fix for F-4.11-03 | Regression of: F-4.11-03. That fix added TWO log lines, for rejected auth and for rate limiting, and only the auth one got a gate arm. Mutation M16: deleting the rate-limit log line leaves BOTH the premise gate and the service unit suite green | open | A second Rule 4 stop, independent of the adversary's. The lead wrote the fix, wrote one arm for it, and did not notice the fix had two halves. This is the "fix by category, never by enumeration" rule failing in the smallest possible way: the category is "calls that are refused before reaching the logging step", and the fix enumerated one of the two | 2026-08-22 judge: filed with mutation evidence |
| F-4.11-J-04 | 1 | major | `docs/data-engineering/Graph_query_service_runbook.md` | Regression of: F-4.11-02. The runbook, written in the same commit series that filed F-4.11-02, names a Hetzner Cloud Firewall as one of two deliberate halves of the exposure defense, and tells an operator to check that firewall FIRST during an outage. There is no firewall anywhere: not on the box, not in the Hetzner project | fixed | The lead corrected the finding and never corrected the document it had already written. Worse than a stale doc: it sends someone debugging a live outage to a console page that does not exist, and it credits the exposure property to a control that is not there, so the loopback binding is carrying the whole load while the document says it carries half | 2026-08-22 judge: filed. 2026-08-22 lead: fixed on the spot, since it was the lead's own error and a documentation-only change |
| F-4.11-J-05 | 1 | major | `services/graph_query_service/app.py`, the endpoint's step order | The rate limiter sits AFTER auth, so the unauthenticated path is entirely unlimited, and since the F-4.11-03 fix every failed attempt writes a log line that journald will drop-limit, degrading the very audit trail that fix created | open | The judge and the adversary reached this independently from separate briefs and separate contexts, which is the split's whole justification. Overlaps the adversary's F-4.11-10 and is filed separately because the judge names the mechanism, journald drop-limiting, that turns log growth into audit loss | 2026-08-22 judge: filed |
| F-4.11-J-06 | 1 | major | `src/system_03_search_agent/tools/graph_http_transport.py` | A client-side timeout maps to `GraphConnectionError` rather than `GraphTimeoutError`, and because client and service share one budget value the client ALWAYS fires first, which makes the 504 mapping dead code in production | open | Independently reached by the adversary as F-4.11-09, which additionally traced the consequence into KGX export. Two separate reviewers converging on it from different directions is the strongest signal in this round | 2026-08-22 judge: filed |
| F-4.11-08 | 1 | major | `services/graph_query_service/app.py:460` and `:545` | The endpoint is `async def` and calls the BLOCKING `execute_cypher` with no threadpool, on a single-worker uvicorn, so one legal slow query serializes every caller and stalls the unauthenticated `/healthz` for up to the clamped budget. Measured by the adversary: `healthz` took 10.97s while a 12s query was in flight. `tracker/preflight.py` reads `healthz` to declare the transport up, so preflight will report the graph DOWN during any slow query, which is the exact "transport looks down" failure this phase was pulled forward to eliminate | open | CONFIRMED by the lead reading the source rather than taken on the report: line 460 is `async def`, line 545 calls `execute_cypher(...)` with no `await` and no `to_thread`. Reachable by the ordinary product with no hostile input. It is F-2.1-06's already-fixed event-loop defect resurfacing one layer down, in code whose gate never tested concurrency, and the gate's own coverage statement names concurrency as a deliberate omission | 2026-08-22 adversary: filed. 2026-08-22 lead: confirmed by reading, NOT fixed, phase escalated |
| F-4.11-09 | 1 | major | `src/system_03_search_agent/tools/graph_http_transport.py`, the client timeout versus the service budget | The transport swap CHANGES a graph timeout's error type, which contradicts this phase's central claim. The client's HTTP timeout equals the service's own budget, so a genuinely slow query always trips the client's read timeout first and is classified `GraphConnectionError`, where psycopg2 raised `GraphTimeoutError`. Measured by the adversary on the identical query against both transports. `export/traversal.py`, a v1 delivery surface, catches only `GraphTimeoutError` to return graceful partial results and lets `GraphConnectionError` propagate, so the swap turns a graceful partial KGX export into a total failure | open | Mechanism confirmed by the lead: the module docstring states the client timeout matches the per-call budget, so the two are equal and the client always wins the race. This defeats the `production-standards` degradation gate and the phase's own done-when. The premise gate's P9 arm maps a 504 correctly and never exercised the case where the client gives up before the service answers | 2026-08-22 adversary: filed. 2026-08-22 lead: mechanism confirmed, NOT fixed, phase escalated |
| F-4.11-10 | 1 | minor | `services/graph_query_service/app.py`, the auth path added as the fix for F-4.11-03 | Failed authentication attempts are never rate limited, because auth raises before the limiter runs, and each failure is now LOGGED, on a box measured at 92 percent full. So an unauthenticated caller can drive unbounded log growth. Separately, the two distinct 401 messages contradict the docstring's claim that every auth failure takes the same path | open | Regression of: F-4.11-03. The logging half is inside the lead's own fix from earlier in this phase, which is the Rule 4 condition in `.claude/skills/bossman-mode/SKILL.md`: a finding located inside an earlier fix stops the phase mid-round rather than being batched. The fix approach was not wrong, it was incomplete, and the rule triggers on LOCATION rather than on the lead's assessment of the approach, which is deliberate | 2026-08-22 adversary: filed. 2026-08-22 lead: recognised as Rule 4, phase stopped and escalated to the product owner rather than fixed |
| F-4.11-11 | 1 | minor | `services/graph_query_service/app.py`, `_caller_digest`, behind Caddy | Caddy does not forward the client address and the service does not read a forwarded header, so every caller appears as `127.0.0.1`. The rate-limit key and the audit log's caller identity therefore have no real source component, which makes "per caller" true only while exactly one credential exists | open | Latent today and live the moment a second credential is issued, which the digest was explicitly shaped to anticipate. The audit half is live now: the log cannot distinguish two sources | 2026-08-22 adversary: filed |
| F-4.11-12 | 1 | minor | `services/graph_query_service/app.py`, the FastAPI application construction | `/openapi.json` is served unauthenticated even though `docs_url` and `redoc_url` are disabled, disclosing the endpoint inventory. The payload schema is not exposed | open | Low value to an attacker who must still hold the bearer credential, but it is disclosure the service has no reason to offer, and disabling the docs pages while leaving the schema endpoint open is the shape of a control that looks complete and is not | 2026-08-22 adversary: filed |
| F-4.11-07 | 0 | major | `tests/system_03_search_agent/tools/`, surfaced by the cutover in T-4.11-05 | The moment the local `.env` was pointed at the HTTPS service, SEVENTEEN psycopg2 unit tests in `test_graph_connection.py` began failing on a machine where nothing was wrong. Two individually harmless facts compose into it: importing `litellm` anywhere calls `load_dotenv()` at import time, so the whole `.env` becomes ambient process state (F-2.1-04, known since build phase 2.1), and passing a `connection_factory` while `GRAPH_QUERY_URL` is set raises on purpose. Composed, every test injecting a factory inherits a transport from whoever ran it | fixed | Found by the full suite, not by the phase's own gate, and only because the suite was run AFTER the cutover rather than before it. The signature is the giveaway: the tests passed individually and failed together. Neither half is wrong, so neither half changed. A directory-scoped autouse fixture now clears the variable before each test in the Layer 1 directory, so a test states its transport rather than absorbing one; the dispatch arms already set it explicitly with monkeypatch. Deliberately not repository-wide: an autouse fixture that silently deletes an environment variable everywhere is the ambient behaviour this fixes, spread rather than removed | 2026-08-22 lead: found running the full suite after the cutover, fixed and re-verified at 1332 passed, 96 skipped in the Layer 1 directory with the live gate still green |
| F-4.11-06 | 0 | major | `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, arm P5 | The rate-limit arm FAILED against the live graph while the control it grades was working correctly. The limiter is a sliding 60 second window with a limit of 60, and a live query takes about two seconds, so 62 of them take over two minutes and the window empties from the front faster than the loop fills it from the back. The arm was measuring how fast the graph answers, not whether the limiter fires | fixed | Found by running the gate live rather than by reading it, which is the only way this one surfaces: it passes in every offline run. Fixed by stubbing the downstream execution so the loop runs in milliseconds. That is isolation of the control under test rather than the gate supplying its own answer, since the limiter itself runs unmodified and what was replaced is the graph behind it, which this arm never had reason to exercise. Mutation-proven after the change: disabling the limiter turns the arm red | 2026-08-22 lead: found on the first full live run, fixed and mutation-proven the same session |
| F-4.11-05 | 0 | minor | `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, the in-process fixtures | Five arms covering auth and the two startup refusals ERRORED at fixture setup on any machine with no configured credential, because `build_app()` correctly refuses to start without one. They are offline arms that need only SOME credential, so they were unrunnable precisely where they are cheapest to run, and five errors that read as defects is how a gate stops being trusted | fixed | Raised by the builder of the service, which had to set the credential transiently to verify its own work and noticed the gate could not. Fixed with a fixture supplying a synthetic credential rather than with a skip marker: skipping would have traded a confusing error for a silent hole, and these arms have no reason not to run | 2026-08-22 builder-service: raised in its completion report. 2026-08-22 lead: fixed, and the same fixture now clears `GRAPH_QUERY_URL` for the in-process app so a developer machine that has cut over does not trip the recursion guard P12b exists to pin |
| F-4.11-04 | 0 | major | `tests/system_03_search_agent/tools/test_graph_query_service_premise.py`, arm P8, written by the lead | The arm asserted only `pytest.raises(GraphError)` on a call naming both transports. Delete the conflict check it exists to prove and the call proceeds to a real HTTPS attempt against `example.invalid`, whose DNS failure classifies into `GraphConnectionError`, which IS a `GraphError`. The arm therefore stayed green with its control removed | fixed | Raised by the BUILDER of the code this arm grades, which is the finder-is-not-the-author direction that usually goes unrewarded, and it was correct. Tightened with two tripwires so neither transport can be entered, leaving the conflict check as the only path to the raise. The builder had already found and fixed the identical weakness in its own mirror test before reporting this one | 2026-08-22 builder-transport: raised in its completion report, explicitly declining to edit a file outside its scope. 2026-08-22 lead: fixed |
| F-4.11-03 | 0 | major | `services/graph_query_service/app.py`, the endpoint's step order | The only audit log line sits at step 4, AFTER auth (step 1) and after the rate limit (step 2), and both of those raise. So a rejected authentication attempt and a rate-limited caller are never logged at all. Section 24 requires the service log every call, and the two classes of call this omits are precisely the ones an operator needs: credential brute-forcing leaves no trace, and an abusive caller disappears at exactly the moment it starts being abusive | open | Found by the lead reading the merged code, not by a gate arm. P11b asserts the credential never appears in a log line and passes happily against a log that is missing entire categories of call, so the gate proves the log is clean rather than that it is complete | 2026-08-22 lead: filed on review of builder output, before the judge round |
| F-4.11-02 | 0 | major | The lead's own port probe, and the product-owner question built on it | The lead reported that a Hetzner Cloud Firewall was filtering ports 80 and 443, and asked the product owner for infrastructure credentials to change it. The inference was WRONG. The Hetzner API shows zero firewalls in the project and none attached to the server, and the box carries no filtering at all: empty `iptables`, empty `ip6tables`, empty `nftables`. Ports 80 and 443 were never blocked; nothing was listening on them, and this sandbox renders "nothing listening" identically to "filtered" | confirmed | The evidence offered at the time looked strong and was not: a control probe to `github.com:443` and `github.com:22` connected, which was read as proving egress worked generally, when it only proved those two destinations had something listening. The control that would have caught it, a probe to a port with nothing listening on an unrelated host, was not run until afterwards | 2026-08-22 lead: filed against itself after the API returned zero firewalls. Cost: one unnecessary credential grant, which the product owner is asked to revoke |

## History

- 2026-08-22: Phase opened. Preflight READY on all three transports after the SSH tunnel was reopened. Product owner authorized live deployment to the Hetzner box, choosing it over a build-only scope and a localhost-only deployment. Board written with five tickets.
