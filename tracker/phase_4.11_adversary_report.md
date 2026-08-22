# Build phase 4.11 adversary report

Round 0 adversary, unscripted. Target: the read-only HTTPS graph query service
deployed live at `https://static.133.128.225.46.clients.your-server.de`, and the
`cypher_query` transport swap in `graph_connection.execute_cypher`.

Method: raw `httpx` calls with the real bearer credential against the deployed
service, direct psycopg2 comparison over a temporary SSH tunnel for the fidelity
attack, read-only `ssh` inspection of the box, and source reading of the client,
service, validator, and the KGX export path that also consumes `execute_cypher`.

SSH tunnel state: I opened `ssh -N -L 15432:127.0.0.1:5432 root@46.225.128.133`
for the byte-equality fidelity comparison only, and closed it before writing this
report (verified closed). Every other test, including all attacks against the
service, ran with NO tunnel open, over HTTPS, which is the phase's own claim
about routine work and it held: routine querying needs no tunnel.

I file findings. I do not fix, triage, or close them. Ordered worst-first.

Severity legend: critical = corrupts an answer or breaches read-only/auth;
major = defeats a stated guarantee or degrades a delivery surface; minor = a
smaller leak or gap; latent = not reachable today but one config change away.

---

## F-4.11-08 (major, and it defeats this phase's own stated purpose): the service blocks its event loop, so one slow query freezes the whole service including the unauthenticated `healthz` preflight uses

Where: `services/graph_query_service/app.py:460` (`async def cypher_endpoint`) calling
`execute_cypher(...)` synchronously at `app.py:545`, on a single-worker uvicorn
(`services/graph_query_service/deploy/graph-query-service.service`, `ExecStart` has no
`--workers`, confirmed live: one process, pid 3331869, `--host 127.0.0.1 --port 8080`).

What I observed, live, with three requests and no tunnel:

- I started one legal slow query (`MATCH (g:Gene) WHERE g.name CONTAINS $n RETURN g`,
  `timeout_s=12`), and 1.5s later probed `GET /healthz`.
- `healthz` returned 200 but took 10.97 seconds. It was blocked until the slow query
  finished (the slow query returned its 504 at 12.47s). A `healthz` on an idle service
  returns in ~0.13s.
- A second authenticated query issued alongside only returned quickly because by then
  the slow query had already completed; it was serialized behind it, not concurrent.

Root cause: `cypher_endpoint` is `async def`, and it calls the synchronous,
blocking `execute_cypher` (blocking psycopg2 I/O) directly on the event loop,
with no `asyncio.to_thread`. FastAPI only offloads to a threadpool for plain
`def` handlers, not `async def` ones. With a single uvicorn worker there is one
event loop, so one blocking query stalls every other request, `healthz` included,
for up to the clamped ceiling of `CYPHER_QUERY_TIMEOUT_SECONDS = 90` seconds.

This is the exact bug F-2.1-06 already found and fixed one layer up:
`cypher_query.py:1838` wraps `execute_cypher` in `asyncio.to_thread` precisely so
one graph query "no longer freezes every concurrent SSE stream". The service
reintroduces the identical defect one layer down, and its own gate never tested
concurrency so it did not catch it. This is the "stated omission covering the
default path" ancestor the board named, in a new place.

Why it is the worst finding: the phase was pulled ahead of 4.7 specifically
because the SSH tunnel kept going down and taking live verification with it
(`tracker/phase_4.11.md`, "Why this phase jumped the queue"). `tracker/preflight.py`
declares the transport READY by probing `healthz`. During ANY slow query, `healthz`
now hangs for up to 90 seconds, so preflight will report the graph transport DOWN
while it is merely busy. The phase reintroduces the very "transport looks down"
symptom it exists to remove, through a different mechanism the goal contract's
"changed nothing observable" claim does not cover.

Reachability: fully reachable, by the single legitimate caller (the product),
with one ordinary query that happens to run long. No hostile input required. A
deliberately slow-but-legal query weaponizes it: hold the service (and preflight)
down for up to 90s per request.

What would prove the fix: `healthz` latency stays flat while a max-budget query is
in flight, i.e. the blocking call is moved off the event loop
(`await asyncio.to_thread(execute_cypher, ...)`) or the handler is made `def`.

---

## F-4.11-09 (major): the transport swap changes a graph timeout's ERROR TYPE, turning KGX export's graceful partial result into a total abort

Where: `src/system_03_search_agent/tools/graph_http_transport.py:333-353`
(the client's httpx timeout equals the service budget, so a real slow query is
caught as `GraphConnectionError`, not `GraphTimeoutError`), consumed at
`src/system_03_search_agent/export/traversal.py:714` and `:809`
(only `GraphTimeoutError` is caught; `GraphConnectionError` propagates).

What I observed, same query, same `timeout_s=3.0`, both transports:

- psycopg2 path (over the tunnel): raised `GraphTimeoutError` at ~5.1s.
- HTTPS path: raised `GraphConnectionError` ("graph query service request failed
  (ReadTimeout)...") at ~3.3s.

Root cause: `execute_cypher_over_http` sets the httpx request `timeout=timeout_s`
and also forwards the same `timeout_s` to the service as its budget. The service
sets `statement_timeout = timeout_s` and only returns its clean `504 timeout`
AFTER the query is killed, plus a network round trip. The client's deadline is
measured from send and is the same `timeout_s`, so the client's `ReadTimeout`
structurally always fires first. The broad `except Exception` at
`graph_http_transport.py:340` classifies that `ReadTimeout` as
`GraphConnectionError`. The `504 -> GraphTimeoutError` mapping at
`graph_http_transport.py:235` is therefore effectively dead for a genuine slow
query; it only fires if the client is given MORE time than the service, which the
real transport never arranges. I confirmed the 504 path only by decoupling the
timeouts myself (client patient at 35s, service budget 3s), which the product
never does.

Downstream consequence, and why it is not cosmetic: `export/traversal.py` (KGX
export, build phase 4.4, a locked v1 delivery surface) deliberately catches
`GraphTimeoutError` to mean "budget exhausted, stop and return what we have", and
deliberately lets `GraphConnectionError`/`GraphAuthError` propagate as a hard
transport failure (its own docstring, `traversal.py:636-643`). The CLI then
converts that propagation into `EXIT_RUNTIME_ERROR` with no output
(`export/cli.py:331`). So in v1 (`GRAPH_QUERY_URL` set), one slow hop query makes
the whole KGX export fail and discard every node and edge already collected,
whereas on psycopg2 the same slow hop stops gracefully and writes a partial
export. `production-standards`' degradation gate ("partial-layer failure degrades
gracefully ... a blank failure is not acceptable") is violated by the transport
swap, not by the KGX code.

Reachability: reachable in v1 whenever any single traversal hop exceeds
`_per_call_timeout`. On the fragile-under-load transport this phase itself
records, that is not a corner case.

What would prove the fix: give the client's httpx timeout headroom over the
service budget (e.g. `timeout_s + a few seconds`) so the service's `504` wins the
race, OR map httpx `TimeoutException`/`ReadTimeout` to `GraphTimeoutError` in the
transport. Then assert both transports raise the same type for the same slow
query, and that a KGX export with one slow hop still writes a partial result.

---

## F-4.11-10 (minor, and it contradicts the service's own docstring): failed-auth attempts are not rate limited, and each one is logged, on a box already 92% full

Where: `services/graph_query_service/app.py:461-498`. Auth (step 1) raises before
the rate limiter (step 2) is ever consulted, and the limiter is keyed on the
PRESENTED token only after auth succeeds.

What I observed: eight wrong-token requests in a tight loop all returned `401`,
never `429`. The rate limit does nothing against unauthenticated traffic. Caddy
carries no rate limit either (I read `/etc/caddy/Caddyfile`: no `rate_limit`, and
the box has no firewall, per F-4.11-02). So credential guessing is unthrottled at
every layer. The token is 64 hex chars (256-bit), so brute force is not the real
risk; the reachable risk is that every failed attempt emits a `logger.warning`
(the F-4.11-03 fix, `app.py:476`) with no throttle, and the box is at 92% disk
(263G/301G used, 26G free, confirmed live via `df`). An attacker can drive
unbounded failed-auth requests to grow journald and the Caddy access log with no
app-side limit, on a disk that is already nearly full. I did not run the flood;
two handfuls of requests were enough to prove no throttle exists.

Secondary, same code path: the service's docstring and `_check_auth` claim a
missing/malformed header, an empty bearer, a wrong scheme, and a wrong value "all
take the same path so the response cannot leak which kind of failure occurred"
(`app.py:288-297`). They do not: a missing/malformed header returns "missing or
malformed bearer credential" while a well-formed wrong token returns "invalid
bearer credential" (both confirmed live). An attacker learns when they have the
header FORMAT right versus the token wrong. This is the claim-vs-behavior gap
`self-eval-loop` warns about: a confident comment sitting above code that does not
do what it says.

Reachability: reachable now (unauthenticated). Low individual severity; the disk
angle raises it because the precondition (nearly-full disk) already holds.

What would prove the fix: throttle by source before or independently of auth
success, and either unify the two 401 messages or accept and document the
distinction as intended.

---

## F-4.11-11 (minor/latent): behind Caddy the service sees every caller as 127.0.0.1, so the "per-caller" rate limit and the audit "caller" identity have no source component

Where: `services/graph_query_service/app.py:472` (`request.client.host`), keyed
into `_caller_digest` at `app.py:481` and `:277-285`; Caddy config has no
`trusted_proxies`/X-Forwarded-For handling (confirmed: no such directive in
`/etc/caddy/Caddyfile`, and `ss` shows the service on `127.0.0.1:8080` behind the
proxy).

What this means: the reverse proxy is the direct peer, so `request.client.host`
is `127.0.0.1` for every external caller. The rate-limit key and the audit-log
`caller=` digest are `sha256(token | "127.0.0.1")`. For the single v1 credential
this collapses to one global bucket and one log identity. The docstring's stated
design intent, "keyed on the token plus the client host, so a second credential
gets its own independent budget" (`app.py:88-94`), is only half-true: the host
half is inert behind the proxy, and the log can never record the real source IP
of an abusive or brute-forcing caller (compounding F-4.11-10). It is not wrong for
one caller today, which is why this is minor/latent, but the log's source
attribution the F-4.11-03 fix was meant to provide is weaker than it reads.

What would prove the fix: set Caddy `trusted_proxies` and read a validated
`X-Forwarded-For`, or state explicitly that source-IP attribution is out of scope
and the token digest is the only caller identity.

---

## F-4.11-12 (minor): `/openapi.json` is served unauthenticated, partially defeating `docs_url=None`

Where: `services/graph_query_service/app.py:410`. `docs_url=None, redoc_url=None`
disable the Swagger/ReDoc UIs but leave `openapi_url` at its default `/openapi.json`.

What I observed: `GET /openapi.json` returns 200 unauthenticated and enumerates
the two paths `/healthz` and `/v1/cypher`. Because the endpoint takes a raw
`Request` rather than a Pydantic body parameter, the `CypherRequest` schema is NOT
in the document, so the disclosure is limited to the endpoint inventory rather
than the payload contract. Still, the intent of disabling docs was clearly to
reveal nothing beyond `healthz` ("Unauthenticated reachability probe. Reveals
nothing else", `app.py:456`), and the OpenAPI endpoint quietly reveals the
`/v1/cypher` surface to any unauthenticated visitor.

Reachability: reachable now, unauthenticated. Low impact.

What would prove the fix: `FastAPI(..., openapi_url=None)`, then `GET /openapi.json`
returns 404 like `/docs` already does.

---

## What I tried that did NOT work (defenses that held under a real attempt)

These are recorded because a defense that survives a genuine attack is evidence.

- Byte fidelity, the phase's central claim: HELD. I compared the psycopg2 path
  (over the tunnel) against the HTTPS path for the same Cypher/params on the same
  live graph, byte-for-byte on the raw agtype strings (not parsed values), across:
  a single-vertex lookup, a multi-column return, a null property, a literal int
  (`RETURN 42` -> `"42"` on both), a list (`RETURN [1,2,3]` -> `"[1, 2, 3]"` on
  both), an empty result, a no-params query, and 150 rows across Gene, Disease,
  and SequenceVariant. Every case matched exactly, including `total_available`. I
  could not find a query whose result the HTTPS path mangles, drops, reorders,
  re-encodes, or truncates differently. The `_encode_rows` non-string branch
  appears unreachable in practice because AGE renders every value as an agtype
  string or SQL NULL; that is a defensive check, not a live divergence.

- Writing to the graph: could not. `CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`,
  `DROP` are rejected server-side by the re-run validator even via raw curl-shaped
  payloads that never touch the client. `CALL db.labels()`, a subquery `CALL`, and
  arbitrary functions (`pg_read_file(...)`) pass the validator but are rejected by
  AGE itself (`SyntaxError`/`UndefinedFunction`), and the role is read-only, so
  none reached a write. Note for the record: the validator ACCEPTS `CALL` and
  arbitrary function calls; only AGE's own grammar and the read-only role stop
  them. That is a thin second barrier, worth knowing but not a reachable defect.

- `$$` dollar-quote breakout: could not. A payload trying to close the AGE
  `cypher('...', $$ ... $$)` body is rejected (`graph_connection._validate_cypher_and_as_clause`
  rejects a literal `$$`, and the unbalanced parens trip the malformed check).

- `as_clause` injection: could not. The service re-validates `as_clause` against
  `^\([A-Za-z_][A-Za-z0-9_ ,]*\)$` server-side; `(x agtype) UNION SELECT ...` and
  `() ; DROP` are both rejected `invalid_payload`.

- Budget bypass on `row_limit`: could not. `row_limit` outside `[1, 5000]` is
  rejected; inside it is clamped to `MAX_ROW_LIMIT`. Extra body fields are rejected
  by `extra="forbid"`; a `validated: true` flag is refused, so there is no
  client-trust flag to spoof.

- Exposure: HELD, and I verified it the right way. From this machine the public
  `443` and `80` connect while `5432` and `8080` time out, but this sandbox renders
  "nothing listening" identically to "filtered" (my control probe to
  `github.com:12345` also timed out), so an external probe alone is not proof. Read
  directly on the box, `ss -ltn` shows Postgres on `127.0.0.1:5432` and `[::1]:5432`
  only and the service on `127.0.0.1:8080` only; nothing binds either to a public
  interface, and there is no firewall. The Postgres port is genuinely closed to the
  internet.

- Credential recovery by timing or error body: could not. `hmac.compare_digest`
  is used, rejection bodies never carry the token or its length, and response
  headers leak nothing (`-Server`, HSTS, nosniff set). The only auth-response
  distinction is the two 401 messages noted in F-4.11-10, which leaks header-format
  correctness, not the token.

---

## Single most important finding, restated

The service blocks its own event loop (F-4.11-08): `cypher_endpoint` is `async def`
but calls the blocking `execute_cypher` synchronously on a single-worker uvicorn,
so one legal slow query serializes every other request and stalls the
unauthenticated `healthz` probe for up to the 90-second clamp. I measured `healthz`
taking 10.97s while a 12s query was in flight. This matters more than a clever
injection because it is reachable by the ordinary product with an ordinary query,
and because it silently reintroduces the exact failure this phase was pulled
forward to eliminate: `tracker/preflight.py` reads `healthz` to declare the
transport up, so during any slow query preflight will report the graph DOWN while
it is only busy. It is F-2.1-06's already-fixed event-loop-blocking bug, resurfaced
one layer down in code whose gate never tested concurrency. The fix is to move the
blocking call off the loop (`asyncio.to_thread`) and to prove it with a flat
`healthz` latency while a max-budget query runs.

## What I would attack next given more time

Two threads. First, resource exhaustion via the concurrency gap and the timeout
math together: because failed auth is unthrottled (F-4.11-10) and each authenticated
query can hold a psycopg2 connection for up to 90 clamped seconds with no concurrency
cap, I would carefully characterize (without a real DoS) how many concurrent
long-running-but-legal queries it takes to exhaust the graph's Postgres connection
pool or the box's memory, and whether the rolling-60s/90s-query mismatch lets a
single caller keep more than 60 queries alive at once. Second, the deploy surface:
`check_drift.sh` proves the five committed files are byte-identical on the box, but
nothing pins the vendored third-party deps that `deploy.sh` installs unpinned
(`pip install fastapi uvicorn psycopg2-binary pydantic httpx`, no versions, no
hashes) into the service venv that runs against the live graph credential. An
attacker who could influence that install, or a hijacked release of any of those
packages, would run with the `kg_reader` credential and the bearer token in the
service env; per `supply-chain-security` that unpinned install on the credential-
bearing box is worth a finding of its own, which I would develop next.
