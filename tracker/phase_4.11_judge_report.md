# Build phase 4.11 judge report, round 1 of 2

Branch: `phase/4.11-graph-query-service`, four commits `da97612`, `fdaca8e`, `bf26bda3`, `0f1d5bf`
Reviewed: 2026-08-22, read-only. No source was edited. Every mutation applied below was restored and `git status` was re-checked clean after each batch.
Service state at review time: DEPLOYED AND LIVE. `python tracker/preflight.py` reported `graph ok HTTPS query service HTTP 200 in 383ms`, all three transports READY, with no SSH tunnel opened at any point during this review.

## Verdict

FAIL.

Merge bar, as stated in the brief: a critical or a reachable major blocks the merge; minors and latent findings are tracked, not blocking. This round files four reachable majors and one critical, so the phase does not merge as it stands.

Two of the five blocking findings sit INSIDE a fix filed and closed during this phase (F-4.11-03 and F-4.11-02). Per Rule 4 as the brief states it, that is a stop: the phase should stop mid-round rather than continue to an adversary round, and the fixes should be re-opened rather than patched forward.

The product itself is in better shape than the verify surface around it. Everything Section 24 asks the running service to do, I confirmed directly against the deployed endpoint over HTTPS with a raw client, and it does it. What fails here is the gate: it has silently stopped exercising its own central premise, and the runbook documents a control this phase itself proved does not exist.

## A. The premise check, answered directly

The goal contract's done-when has five clauses. Taking them one at a time against what I could measure:

- "`cypher_query` reaches the live Layer 1 graph over HTTPS with no SSH tunnel open anywhere": MET. `RUN_PREMISE_GATE=1 pytest ...test_graph_query_service_premise.py` returned `23 passed, 12 skipped in 15.60s` with no tunnel, and P2 (the real `cypher_query` pipeline end to end, asserted on citations) is among the 23 that passed. I also read the live graph directly over HTTPS and got the pinned ground truth: `total_available 12` TP53 `gene_associated_with_condition` edges to Disease vertices, and `'"BRCA1 DNA repair associated"'` for the scalar query, every cell arriving as a raw agtype `str`.
- "returning results byte-identical to what the psycopg2 path returns for the same query": NOT REPRODUCIBLE, and this is the phase's real premise failure. The arm that proves it, P1, needs BOTH transports in one process. The psycopg2 half needs `GRAPH_PG_HOST:GRAPH_PG_PORT` to answer, which is the SSH local port-forward this phase exists to retire. Commit `bf26bda3` reports it passed once with the tunnel still open, and I have no reason to doubt that. But in the configuration the phase actually ships, P1 does not run, and it reports `skipped`, not `failed`. The phase's central premise is now unverifiable without undoing the phase.
- "the service rejects, server-side, every class of payload the client-side validator rejects, plus an absent or wrong bearer token, an over-large row limit": MET IN THE PRODUCT, NOT IN THE GATE. I verified all five rejection classes and all three auth classes against the DEPLOYED service with a raw HTTP client (output pasted under F-4.11-J-01). The five gate arms that are supposed to prove this, P3, skip in the shipped configuration.
- "a caller over its rate limit": MET for an authenticated caller (P5 passes, mutation-proven). NOT MET for an unauthenticated one, which has no rate limit at all. See F-4.11-J-06.
- "the graph's Postgres port is still unreachable from the internet, and `tracker/preflight.py` can verify the graph transport without a person opening an SSH session": MET. P10, P10b and P10c all passed live and all three are mutation-proven red (M13, M14, M15 below). Preflight reports the HTTPS transport as a distinct transport.

So the direct answer: no, the set of completed work does not satisfy the done-when. Each ticket did its own job, the service works, and the outcome clause that distinguishes this phase from "an HTTP endpoint that answers", byte-equality between the two transports, is the one clause that cannot be re-demonstrated on the shipped configuration. That is the shape the brief warned about, arriving through the gate rather than through the code.

The second-order effect is worse than the first. `requires_graph` is applied to twelve arms, and the cutover retired the socket it reads, so twelve arms went dark in the same act that made the phase succeed. Seven of them never needed a graph in the first place; I proved that below. Build phase 4.6 merged with three live arms unrun and this repository recorded that as a cost. This phase merges with twelve, and unlike 4.6's the condition is permanent rather than transient.

## Findings

### F-4.11-J-01, critical: seven arms are gated on a live graph they never touch, and the cutover turned them off

Where: `tests/system_03_search_agent/tools/test_graph_query_service_premise.py:388` (`@requires_graph` on P3), `:409` (P3b), `:537` (P6), `:837` (P11), `:884` (P11b), and the marker definition at `:172`.

What is wrong: `requires_graph` skips on `not _graph_is_reachable()`, which opens a socket to `GRAPH_PG_HOST:GRAPH_PG_PORT` (`:107` to `:123`). T-4.11-05 cut the local `.env` over to `GRAPH_QUERY_URL`, and the psycopg2 forward is closed, so that socket is dead. Every arm carrying the marker now skips. Among them are all five server-side rejection arms, which are the entire evidence for Section 24's defense-in-depth clause and for the board's own "second trap this phase can most easily ship".

How I proved it. The live run with no tunnel:

```
$ RUN_PREMISE_GATE=1 ./venv/bin/python -m pytest tests/.../test_graph_query_service_premise.py -q -rs
sss.ssssss......s.............s.s..
SKIPPED [2] ...:258: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [1] ...:296: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [5] ...:368: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [1] ...:410: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [1] ...:537: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [1] ...:838: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
SKIPPED [1] ...:885: needs RUN_PREMISE_GATE=1 and a reachable AGE graph
23 passed, 12 skipped in 15.60s
```

Line 368 is P3's five parameters, 410 is P3b, 537 is P6, 838 is P11, 885 is P11b, 258 and 296 are P1 and P1b.

Then I proved seven of the twelve never needed the graph. Setting `GRAPH_PG_HOST=46.225.128.133 GRAPH_PG_PORT=443`, a socket that is emphatically not Postgres but does accept a connection, satisfies `_graph_is_reachable()` and the arms run:

```
$ RUN_PREMISE_GATE=1 GRAPH_PG_HOST=46.225.128.133 GRAPH_PG_PORT=443 \
  ./venv/bin/python -m pytest ...premise.py -q -k "p3 or p11 or p6"
1 failed, 9 passed, 25 deselected in 1.53s
```

The nine that pass are P3's five, P3b, P11, P11b and P11c. They use an in-process `TestClient` and either reject before execution or trip a monkeypatched `execute_cypher`, so a real graph is irrelevant to every one of them. The one failure is P6, discussed separately at F-4.11-J-09.

Reachable in the deployed service as it stands: the CONTROL is sound; the GATE is blind. I verified every rejection class directly against the deployed endpoint with a raw `httpx` client and the credential from `.env`:

```
write_clause       -> 422 {"error":{"code":"cypher_rejected","message":"Generated Cypher contains the write clause 'DELETE'. ..."}}
unknown_edge_label -> 422 {"error":{"code":"cypher_rejected","message":"... edge label 'not_a_real_predicate', which is not one of the graph's known edge labels. ..."}}
missing_edge_label -> 422 {"error":{"code":"cypher_rejected","message":"... untyped relationship pattern. ..."}}
row_limit_absurd   -> 422 {"error":{"code":"invalid_payload","message":"row_limit must be between 1 and 5000; ..."}}
as_clause_injection-> 422 {"error":{"code":"invalid_payload","message":"as_clause did not match the expected '(name type, ...)' shape"}}
extra_field        -> 422 {"error":{"code":"invalid_payload","message":"... Extra inputs are not permitted ..."}}
no_header          -> 401 {"error":{"code":"unauthorized","message":"missing or malformed bearer credential"}}
wrong_same_length  -> 401 {"error":{"code":"unauthorized","message":"invalid bearer credential"}}
wrong_scheme       -> 401 {"error":{"code":"unauthorized","message":"missing or malformed bearer credential"}}
```

So nothing is broken in front of the graph today. What is broken is that the gate would not tell anyone if it were. It is graded critical rather than major because a green premise gate that has silently stopped testing the property it was written for is the single most expensive failure shape this repository has recorded, and because this one turned itself off as a direct consequence of the phase succeeding, which is the version nobody looks for.

Also note: no arm anywhere hits the DEPLOYED endpoint for a rejection class. Every P3 arm builds the app in process from this repository's own source. The deployed copy's identity is asserted only by `check_drift.sh`, which needs SSH and which I could not run. The probe above is currently the only evidence that the thing on the box rejects anything, and it was run by the judge, not by the gate.

### F-4.11-J-02, major: the byte-equality arm is structurally unrunnable on the shipped configuration, and reports green

Where: `tests/system_03_search_agent/tools/test_graph_query_service_premise.py:256` to `:296` (P1 and P1b), and the goal contract's Verify clause in `tracker/phase_4.11.md:38`.

What is wrong: P1 calls `execute_cypher` twice, once with `GRAPH_QUERY_URL` deleted (`:279` to `:281`) and once with it set. The first call requires the psycopg2 transport to reach a live graph. After T-4.11-05, nothing on a developer machine can satisfy that without reopening the SSH forward the phase deleted. The arm therefore skips permanently, and a skip is indistinguishable from a pass in the run's headline (`23 passed, 12 skipped`).

How I proved it: the `-rs` output above shows `:258` skipped for both parameters. Forcing the marker true with a non-Postgres socket makes it fail rather than pass, confirming it genuinely needs psycopg2 and is not merely mis-marked the way P3 is.

Reachable: yes. This is the state of the repository right now.

The honest part of the record, which I want to state because it is to the phase's credit: commit `bf26bda3` reports `Live gate, tunnel open: 33 passed, 1 failed, 1 skipped` and explicitly reports the closed-tunnel run as `23 passed, 12 skipped`. Nothing was hidden. The defect is that no artifact makes the byte-equality property re-checkable by the next person, and the goal contract names it as a Verify item, so the contract's verify surface has a hole in it that only opens after the phase closes. I did independently confirm the wire format and the pinned ground truth over HTTPS alone (12 TP53 disease edges, `'"BRCA1 DNA repair associated"'`, every cell a `str`), which is most of what P1b asserts, but that is not byte-equality against psycopg2 and I am not claiming it as such.

### F-4.11-J-03, major, Regression of: F-4.11-03

Where: `services/graph_query_service/app.py:486` to `:490`, the rate-limit log line added by the F-4.11-03 fix.

What is wrong: F-4.11-03 found that TWO classes of call left no trace, a rejected credential and a rate-limited caller, and the fix added a `logger.warning` for each. The auth half got a new arm, P11c, and it is genuinely mutation-proven. The rate-limit half got no arm at all, in either the premise gate or the service unit suite.

How I proved it. Replacing the `logger.warning(` at `:486` with an inert assignment and running BOTH suites:

```
--- M16 rate-limit log line removed ---
GREEN (only baseline failures: test_p1_..., test_p6_...)
```

For contrast, the same mutation applied to the auth line (`:476`) and to the step-4 call line (`:519`):

```
--- M12 F-4.11-03 auth-failure log removed ---   RED  new failures: test_p11c_a_refused_call_is_logged_too
--- M17 step-4 call log removed ---              RED  new failures: test_the_logged_caller_identity_is_a_digest_not_the_token
```

I also confirmed the control itself works, so this is an unverified control rather than a broken one. Flooding the in-process app past `RATE_LIMIT_PER_MINUTE` with a stubbed executor emitted `WARNING:services.graph_query_service.app:graph_query_service rate limited caller=16a2c23a79727c32 retry_after=59.91`.

Reachable: the log line fires correctly today. The defect is that half of a fix filed and closed this phase shipped with no verify surface, in a phase whose finding text explicitly named both halves. This is the Rule 4 shape: the defect is inside the fix, and the fix's own arm covers the half the fix's author happened to write a test for.

### F-4.11-J-04, major, Regression of: F-4.11-02

Where: `docs/data-engineering/Graph_query_service_runbook.md`, the "What this service must never do" list and the "Diagnose an outage" list, both shipped in `bf26bda3`.

What is wrong: the runbook states, as one of two deliberate halves of the exposure defense, "It is filtered at the Hetzner firewall and bound to `127.0.0.1`, and both halves are deliberate." F-4.11-02, filed by the lead in this same phase and recorded in `tracker/phase_4.11.md:183` in state `confirmed`, established that there is no firewall: "The Hetzner API shows zero firewalls in the project and none attached to the server, and the box carries no filtering at all: empty `iptables`, empty `ip6tables`, empty `nftables`."

The same document then instructs an operator, under "A caller times out and SSH works", to "Check the firewall first, because a rule can be removed from the console without touching the box", pointing them at a console with no rules during an outage.

How I proved it: `tracker/phase_4.11.md:183` against the runbook text, both on this branch. Nothing else is needed; the two documents in one commit series contradict each other on a security control.

Reachable: yes, and the practical consequence is that the exposure claim is single-barrier, not double. Section 24's clause ("the database port itself never opens to the internet") is still satisfied by the loopback bind alone, and P10c reads that bind directly, so the property holds. What does not hold is the phase's own account of WHY it holds. This repository's `attack-the-constraint` and `self-eval-loop` rules both name a confidently stated but false property as the place the next reader stops checking.

A second false claim sits in the same document's "The credential" section: "The premise gate asserts this rather than trusting it: it plants the real value and greps every response body and every log line for it." The arms that do that are P11 and P11b, both of which skip in the shipped configuration per F-4.11-J-01.

### F-4.11-J-05, major, reachable: the unauthenticated path has no rate limit

Where: `services/graph_query_service/app.py:461` to `:498`, the endpoint's step order, and `tests/services/graph_query_service/test_app.py:448` to `:466`, which pins the behaviour as intended.

What is wrong: auth is step 1 and raises; the rate limiter is step 2 and is never reached for a failed credential. So a caller with no credential, or any wrong credential, is unlimited. The service's own unit test documents this in its docstring: "Auth is checked before the rate limiter is ever consulted, so a wrong token is rejected with 401 and never reaches `_rate_limiter.check` at all."

Section 24 asks for "a rate limit per caller", and `.claude/rules/tool-call-budgets.md` restates it for this service as one of three parts of its budget. As shipped, that limit binds only callers who already hold the credential, which is the population that needs it least.

Two consequences, and the second is the one that interacts with a fix from this phase:

- Availability: an anonymous caller can drive unbounded request handling (TLS handshake, header parse, a SHA-256 over the header) against the box that holds the graph, with no throttle, no lockout, and no backoff.
- Audit integrity: since F-4.11-03, every one of those attempts writes a `logger.warning` line. journald applies its own rate limiting and DROPS messages once a service exceeds the burst within an interval. A flood on the unauthenticated path can therefore suppress the INFO call records the audit trail exists to keep, which inverts the purpose of the fix that added the line.

How I proved it: read the step order at `:461` to `:498`; the ordering is also directly observable, since a request with no credential and a malformed body returns 401 rather than 422, meaning auth ran before parsing (`no auth + malformed body -> 401 {"error":{"code":"unauthorized",...}}`). I did not flood the live service, deliberately: the source and the phase's own unit test are unambiguous and a flood would have been the destructive way to learn the same thing.

Reachable: yes, from the public internet, with no credential. Grading it major rather than critical because the credential is a CSPRNG value compared in constant time, so this is not a path to the graph; it is a path to degrading availability and the audit trail.

### F-4.11-J-06, major, reachable: a client-side timeout arrives as `GraphConnectionError`, not `GraphTimeoutError`

Where: `src/system_03_search_agent/tools/graph_http_transport.py:333` to `:353`.

What is wrong: the `try` around `_post` catches `Exception` and classifies every transport-level failure as `GraphConnectionError` with the message "verify GRAPH_QUERY_URL is reachable and retry". `httpx` raises `ReadTimeout` when the client's own `timeout=timeout_s` fires, so the one failure mode the Act step most needs to distinguish, a query that burned its whole budget, is presented as a connectivity blip worth retrying immediately.

T-4.11-03's acceptance criterion is explicit and unmet: "a connection refusal and a DNS failure to `GraphConnectionError`, a 401 or 403 to `GraphAuthError`, a timeout or a service timeout body to `GraphTimeoutError`".

How I proved it:

```
$ PYTHONPATH=src ./venv/bin/python   # _post monkeypatched to raise httpx.ReadTimeout
type: GraphConnectionError
is GraphTimeoutError: False
is GraphConnectionError: True
message: graph query service request failed (ReadTimeout), verify GRAPH_QUERY_URL is reachable and retry
```

Why it is the dominant path rather than a corner case, which is what makes it major: `execute_cypher_over_http` passes the SAME `timeout_s` to `httpx.post` (`:338`) that the service then clamps its own budget to (`app.py:344`). The service needs that full duration plus TLS and HTTP overhead before it can emit its 504. So the client's timeout fires FIRST essentially every time, and the service's `timeout -> 504 -> GraphTimeoutError` mapping is effectively dead code in production. The gate covers only the 504 body path (P9's `504, "timeout"` case at `:696`) and the bare `OSError` path (P9b), so the shape that actually happens is the one nothing tests.

Reachable: yes, on any query that outruns its budget over HTTPS, which is the path build phase 2.1's own history says is common on this graph.

### F-4.11-J-07, minor, reachable: `/openapi.json` is served unauthenticated on the public internet

Where: `services/graph_query_service/app.py:410`, `FastAPI(title="Graph query service", docs_url=None, redoc_url=None)`. `openapi_url=None` is not set, so FastAPI keeps `/openapi.json` mounted.

How I proved it, against the deployed service, no credential:

```
/openapi.json   200 | {"openapi":"3.1.0","info":{"title":"Graph query service","version":"0.1.0"},"paths":{"/healthz":{"get":{...
/docs           404
/redoc          404
/healthz        200 | {"status":"ok"}
/               404
```

The `healthz` route's own docstring at `:456` says "Unauthenticated reachability probe. Reveals nothing else." Its sibling reveals the whole schema. The intent to shrink the unauthenticated surface is visible in `docs_url=None, redoc_url=None`; one keyword was missed.

Impact is small, the schema describes one endpoint whose shape is already in this repository, so this is a minor. It is worth fixing in the same edit as the docstring, because the docstring is what will stop the next reader from checking.

### F-4.11-J-08, minor, reachable: the auth-failure path is not uniform, and the docstring says it is

Where: `services/graph_query_service/app.py:299` to `:303`, and the claim at `:42` to `:44` and `:293` to `:296`.

The docstring states: "a missing header, an empty bearer, a wrong scheme, or a wrong value all take the same path so the response cannot leak which kind of failure occurred." The code raises two different messages, and the message is returned in the response body:

```
no_header          -> 401 "missing or malformed bearer credential"
wrong_scheme       -> 401 "missing or malformed bearer credential"
wrong_same_length  -> 401 "invalid bearer credential"
```

So a caller can distinguish "your credential is the wrong SHAPE" from "your credential is the wrong VALUE". That is a weak oracle, it does not separate a near-miss value from a far-miss one and the comparison itself is `hmac.compare_digest`, so it is a minor rather than a major. What earns it a finding is the shape: a security property asserted in a comment above code that does not hold it, which `self-eval-loop`'s "review a fix harder than new code" section names as exactly where review stops. P4c asserts only that the token and its length are absent from the body, so nothing tests the uniformity claim.

### F-4.11-J-09, minor: the gate's stated coverage overstates what it measures, on all three budget controls

Where: `tests/system_03_search_agent/tools/test_graph_query_service_premise.py:36` to `:40` (the coverage statement) and `:538` to `:562` (P6).

The gate's own coverage statement claims: "The three budget controls this service owes per `.claude/rules/tool-call-budgets.md`: the hard row limit, the per-call timeout matching `cypher_query`'s own 30 seconds, and the per-caller rate limit, each asserted at the SERVICE rather than at the client." Measured, one of the three is asserted there.

- The row-limit CLAMP is not asserted by the gate. Removing `return min(row_limit, MAX_ROW_LIMIT)` leaves the premise gate GREEN; only the service unit suite catches it (M6 and M6b below). P3's `row_limit_over_max` case asserts the outer band REJECT, a different control.
- The per-call timeout is not asserted by the gate at all. P6 posts the ordinary pinned query with `timeout_s = CYPHER_QUERY_TIMEOUT_SECONDS * 100`, then at `:557` does `if response.status_code == 200: pytest.skip(...)`. The pinned query answers in well under the budget (my own live probe returned 12 rows promptly), so the arm has never reached its assertions. It also never asserts the clamp: it checks only that the status is not 500. Removing the timeout clamp entirely leaves the premise gate GREEN (M5).
- The rate limit IS asserted at the service and is mutation-proven (M7).

`.claude/rules/goal-contracts.md` requires a verify surface to state its own coverage so that a gap is arguable rather than discovered. This statement makes a gap unarguable by asserting coverage that does not exist. The controls themselves are covered by `tests/services/graph_query_service/test_app.py`, so this is a documentation-of-coverage defect rather than a hole in the product, hence minor.

### F-4.11-J-10, minor: the phase states the service's timeout is 30 seconds; it is 90

Where: `tracker/phase_4.11.md:19` ("a per-call timeout matching `cypher_query`'s own 30 seconds"), `:40` ("the per-call timeout matches Section 6.1's 30 seconds rather than being invented here"), the gate docstring at `:38`, and P6's docstring at `:542`. The shipped value is `src/system_03_search_agent/tools/graph_schema_constants.py:170`, `CYPHER_QUERY_TIMEOUT_SECONDS: Final[float] = 90.0`, which is what `app.py:344` clamps to.

The 30-versus-90 divergence itself is pre-existing and honestly recorded in the constants file: "Section 6.1 still states 30 seconds and is a Step 6.2 reconciliation item, filed with the other spec-versus-code divergences this phase found." Section 24 says "matching the tool's own budget", and the service does match the tool's own budget, so the SERVICE is conformant. What this phase newly did is restate 30 seconds as a fact in four places, including in the goal contract's Constraints, where it reads as a verified property. `.claude/rules/tool-call-budgets.md` also names 30 seconds for this service, so the rule and the code now disagree with a new document asserting the rule's number.

### F-4.11-J-11, minor: the deployment installs its dependencies unpinned, and the drift check does not cover them

Where: `services/graph_query_service/deploy/deploy.sh:59`:

```
ssh "$HOST" "$TARGET/venv/bin/pip install --quiet --upgrade pip"
ssh "$HOST" "$TARGET/venv/bin/pip install --quiet fastapi uvicorn psycopg2-binary pydantic httpx"
```

Five packages, no version constraints, installed on the box that holds the graph and the bearer credential, on every deploy. `.claude/rules/supply-chain-security.md` requires exact-version pinning for anything that executes on a credential-bearing surface and treats an unpinned install as equivalent to a global one. `check_drift.sh` verifies the five repository FILES are byte-identical and says nothing about the environment they run in, so a redeploy that pulls a different or hijacked `fastapi` still prints `ok 5 of 5`.

The script's own header says "Idempotent: running it twice leaves the same state, and it is the ONLY way code reaches the box." Line 59 is the sentence that is not true: running it twice can leave a different state.

### F-4.11-J-12, minor: four error messages state only what failed

Where: `services/graph_query_service/app.py:300`, `:303` (`unauthorized`), `:355` to `:358` (`as_clause` shape), `:504` to `:506` (malformed JSON), and `:441` to `:446` (the Pydantic echo).

T-4.11-02's acceptance criterion: "Errors are actionable per the retry-safety gate: each says what the next step is, never a bare 'failed'." `.claude/rules/production-standards.md`'s retry-safety gate says the same. Measured against the deployed service, the `cypher_rejected`, `invalid_payload` for `row_limit`, `rate_limited` and `timeout` messages all carry a next step. These four do not: "missing or malformed bearer credential", "invalid bearer credential", "as_clause did not match the expected '(name type, ...)' shape", "request body is not valid JSON".

Nothing in the gate asserts actionability. The only arm that inspects message text is P6 (`assert "narrower" in error["message"] or "smaller" in ...`), which skips.

### F-4.11-J-13, minor: a server-side `cypher_rejected` reaches the Act step as a connection failure

Where: `src/system_03_search_agent/tools/graph_http_transport.py:255` to `:268`, and pinned as intended by `tests/.../test_graph_http_transport.py:145` (`400_cypher_rejected_maps_to_connection_error`) and by P9's sixth parameter.

A deterministic server-side rejection, the exact case Section 24's defense-in-depth clause exists to produce, arrives as `GraphConnectionError` with "verify the request and retry". The Act step cannot distinguish it from the graph being down, and retrying identical input produces the identical rejection. T-4.11-03 did authorise "everything else to `GraphConnectionError`", so this is spec-conformant and I am filing it as an error-contract observation rather than a violation. It is worth a `cypher_rejected` type or at least a message that says "do not retry this query unchanged", since the whole reason the server-side re-validation exists is that the client-side one may be buggy, and a buggy client that retries forever is the failure this rejection is meant to stop.

### F-4.11-J-14, latent: the systemd unit's own comment claims a property no property in it enforces

Where: `services/graph_query_service/deploy/graph-query-service.service:41` to `:59`.

The comment reads: "The service reads three files and talks to a local socket; it has no reason to write anywhere or to see the rest of the filesystem."

Read against what the unit sets: the write half is enforced (`ProtectSystem=strict`, `ProtectHome=true`). The "see the rest of the filesystem" half is not. `ProtectSystem=strict` makes the hierarchy READ-ONLY, not invisible, and the unit sets no `ProtectProc`, `PrivateMounts`, `TemporaryFileSystem=/`, `RestrictAddressFamilies`, `CapabilityBoundingSet`, `PrivateDevices` or `SystemCallFilter`.

Which of the declared properties are load-bearing, since the brief asks: `User=kgquery` and `Group=kgquery` (a compromise yields a non-root, non-login user), `--host 127.0.0.1` combined with `IPAddressAllow=localhost` plus `IPAddressDeny=any` (the service can neither be reached from the public interface nor reach out to one, which independently closes the recursion hazard the startup check also closes), `NoNewPrivileges=true`, and `ProtectSystem=strict` plus `ProtectHome=true`. `MemoryDenyWriteExecute`, `LockPersonality`, `RestrictSUIDSGID`, `RestrictNamespaces`, `SystemCallArchitectures` and `ProtectControlGroups` are cheap and correct but have little to bite on in a read-only FastAPI process.

One thing the unit does not contradict but the deploy script weakens: `deploy.sh:66` runs `chown -R kgquery:kgquery /opt/graph-query-service`, which makes the service user the owner of its own code, its venv, and the credential file. `ProtectSystem=strict` prevents the service process itself from writing them, so this is latent rather than open, but any other process running as `kgquery` could.

I could not verify that ANY of these properties are actually applied on the running unit. See "What I could not verify".

### F-4.11-J-15, latent: the transport does not require `GRAPH_QUERY_URL` to be HTTPS

Where: `src/system_03_search_agent/tools/graph_http_transport.py:320` to `:339`. The module reads the URL, checks only that it is non-empty, and posts the bearer credential to it. `tracker/preflight.py:176` checks the scheme and P10b checks the scheme, so the two things that do NOT carry the credential validate it, and the one that does not. An `http://` value, or a value pointed at a different host, sends `GRAPH_QUERY_TOKEN` in cleartext to whatever answers. Latent because the value is operator-controlled and correct today.

### F-4.11-J-16, latent: the rate limiter is per-process

Where: `services/graph_query_service/app.py:417`, built per app instance. The comment correctly explains why it is not module-level. Nothing records the other half: with more than one uvicorn worker, the effective per-caller limit becomes `RATE_LIMIT_PER_MINUTE` times the worker count. `graph-query-service.service:31` to `:36` runs a single default worker, so the shipped configuration is correct, and the constraint is undocumented in both the unit and the runbook.

### F-4.11-J-17, minor: the goal contract's whole-suite Verify item is unmet, and no baseline exists

The contract's Verify names "the Python suite against a re-measured baseline". Commit `bf26bda3`'s Evidence block reports `Gate plus service tests: 70 passed, 12 skipped`, which is this phase's own two files, never a whole-suite figure.

I ran the whole suite twice on this branch and got two different answers:

```
run 1: 29 failed, 3724 passed, 117 skipped, 1 xfailed, 1 xpassed in 773.94s
run 2:  6 failed, 3719 passed, 146 skipped, 1 xfailed        in 111.45s
```

Every failure in run 2 is in `tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py` and every one is `LiveHttpCallInUnitSuiteError`, a conftest guard firing on Layer 2 and Layer 3 tools. Run 1's visible failures were in `test_cypher_query_premise.py`, build phase 2.1's live gate. Neither set touches this phase's files, and `tests/system_03_search_agent/tools` alone is clean (`1332 passed, 96 skipped`), as is `tests/services/graph_query_service`. So I am NOT attributing these failures to build phase 4.11. What I am filing is that the contract names a baseline comparison that neither the phase nor I can perform, because the suite is not reproducible run to run.

## Mutation table

Every mutation was applied to the real file, run, and reverted; `git status --porcelain` was re-checked clean after each batch and is clean now. The premise gate was run with `RUN_PREMISE_GATE=1` and with `GRAPH_PG_HOST=46.225.128.133 GRAPH_PG_PORT=443` so that `requires_graph`-marked arms would actually execute; P1 and P6 fail under that instrumentation for reasons unrelated to any mutation, so they form a fixed baseline that is subtracted from every result below.

| # | Arm(s) under test | Control broken | Result | Verdict |
|---|---|---|---|---|
| M1b | P4, P4b | `app.py:302` `hmac.compare_digest` gate to `if False` | RED (`test_p4_...`, `test_p4b_...`) | sound |
| M20 | P4 | `app.py:299` bearer-shape gate disabled | RED (`test_p4_...`) | sound |
| M19 | P4c | `app.py:303` message made to disclose `len(configured)` | RED (`test_p4c_...`) | sound |
| M2 | P3 write clause | `app.py:536` `if not result.ok` to `if False` | RED | sound |
| M2b | P3b | same | RED (`test_p3b_...`) | sound |
| M3 | P3 `row_limit_over_max` | `app.py:317` band reject disabled | RED | sound |
| M4 | P3 `malformed_as_clause` | `app.py:354` `_AS_CLAUSE_PATTERN` check disabled | RED | sound |
| M6 | premise gate, whole file | `app.py:327` row-limit clamp removed | GREEN | GAP, see J-09 |
| M6b | service unit suite | same | RED (`test_row_limit_inside_the_band_but_over_max_is_clamped_not_rejected`) | covered elsewhere |
| M5 | premise gate, whole file | `app.py:344` timeout clamp removed | GREEN | GAP, see J-09 |
| M5b | service unit suite | same | RED (`test_timeout_far_over_budget_is_clamped_not_rejected`) | covered elsewhere |
| M7 | P5 | `app.py:269` limiter comparison to `if False` | RED (`test_p5_...` and `test_rate_limit_fires_with_a_positive_retry_after`) | sound, F-4.11-06 fix holds |
| M8 | premise gate + unit suite | `app.py:372` wire-encoding check disabled (silently coerce) | RED (`test_a_non_string_non_null_cell_is_rejected_not_coerced`) only; premise gate green | covered by the unit suite only |
| M18 | P7 | `graph_connection.py:493` HTTP dispatch branch never taken | RED (`test_p7_...`) | sound |
| M21 | P7b | `graph_connection.py:508` `connection_factory` ignored | RED (`test_p7b_...`) | sound |
| M9 | P8 + `test_connection_factory_with_url_set_raises_graph_error` | `graph_connection.py:496` conflict check to `if False` | RED (both) | sound, F-4.11-04 fix holds |
| M10 | P12 | `app.py:396` missing-token startup refusal disabled | RED (`test_p12_...`) | sound |
| M11 | P12b | `app.py:402` recursion startup refusal disabled | RED (`test_p12b_...`) | sound |
| M12 | P11c | `app.py:476` auth-rejected log line removed | RED (`test_p11c_...`) | sound, F-4.11-03 fix half holds |
| M16 | (none found) | `app.py:486` rate-limited log line removed | GREEN in BOTH suites | DEFECT, F-4.11-J-03 |
| M17 | unit suite | `app.py:519` step-4 call log removed | RED (`test_the_logged_caller_identity_is_a_digest_not_the_token`) | sound |
| M13 | P10 | `premise.py:100` `GRAPH_PG_PUBLIC_PORT` to 443, simulating an open database port | RED (`test_p10_...`) | sound, F-4.11-01 rebuild holds |
| M14 | P10c | `premise.py:812` expected binding flipped to `0.0.0.0:` | RED (`test_p10c_...`) | sound, reads real remote output |
| M15 | P10b | `premise.py:829` scheme assertion flipped to `ftp://` | RED (`test_p10b_...`) | sound |

Every arm whose control is security- or budget-relevant was mutated except the two the brief's own instructions make untestable from here (P1's byte-equality, which cannot run at all, and P6, which skips). Both are findings above rather than gaps in this table.

Reading of the three arms the lead reported as already mutation-proven: I re-derived all three (M7 for the limiter, M12 for the auth logging, M9 for the dispatch rule) and all three hold. The lead's reports were accurate. What the lead's reports did not cover is the OTHER half of the same fix (M16), which is how the gap survived.

Reading of the class the brief flagged, an arm that passes for a reason other than the control it names: I found no third instance of the P8/P10 shape. The two arms that pass for the wrong reason now are P6 (passes by skipping) and the whole `requires_graph` family (passes by skipping), which is a different and larger failure of the same family.

## D. Section 24 conformance, clause by clause

| Clause (quoted from Section 24) | Where it is satisfied | Verdict |
|---|---|---|
| "co-located on the Hetzner CPX42 box itself, alongside the AGE Postgres instance. The hop from the service to Postgres stays on localhost" | `graph-query-service.service:31` to `:36` (`--host 127.0.0.1`), `:58` to `:59` (`IPAddressAllow=localhost`, `IPAddressDeny=any`), `deploy.sh:20` targeting `46.225.128.133` | MET by construction; the deployed unit's actual state is UNVERIFIED (no SSH) |
| "a single endpoint that accepts an already-validated, already-parameterized Cypher payload ... never free-form Cypher text over the wire" | `app.py:459` (`@app.post("/v1/cypher")`), `app.py:222` to `:231` (`CypherRequest`, `extra="forbid"`) | MET. One POST route plus an unauthenticated `GET/HEAD /healthz` at `:454`, and, unintentionally, `/openapi.json` (F-4.11-J-07) |
| "the service re-runs the same forbidden-keyword and edge-label checks the tool already ran, on the server side" | `app.py:535` `validate_cypher(payload.cypher, row_limit)`, importing the real validator at `:157`; `as_clause` re-checked at `:533`; verified live against the DEPLOYED endpoint by raw HTTP (three `cypher_rejected` classes) | MET in the product. Its gate arms do not run: F-4.11-J-01 |
| "the existing `kg_reader` read-only role ... so a validator bug still cannot produce a write" | `graph_connection.py` reads `GRAPH_PG_USER` from the service's own `service.env`; `graph-query-service.service:20` | MET by inheritance; the role actually configured on the box is UNVERIFIED |
| "a bearer token or API key header, because Railway does not guarantee a static egress IP" | `app.py:288` to `:304`, `hmac.compare_digest` at `:302`, checked before parsing (proven: no-auth plus malformed body returns 401, not 422) | MET. The uniformity claim in the docstring is false: F-4.11-J-08 |
| "a hard row limit" | `app.py:307` to `:327`, band reject plus clamp to `MAX_ROW_LIMIT` (5000, confirmed live in the rejection message) | MET. Not asserted by the premise gate: F-4.11-J-09 |
| "a per-call timeout matching the tool's own budget" | `app.py:330` to `:344`, clamps to `CYPHER_QUERY_TIMEOUT_SECONDS` | MET against the tool's own constant. That constant is 90.0, not the 30 this phase's documents state four times: F-4.11-J-10. Never asserted by any arm: F-4.11-J-09 |
| "plus a rate limit per caller, so a runaway query on either side is bounded twice" | `app.py:244` to `:274`, `:484` to `:498` | PARTIALLY MET. Authenticated callers only; the unauthenticated path is unlimited: F-4.11-J-05 |
| "TLS via an automatic-HTTPS reverse proxy (for example Caddy) in front of the service" | `deploy/Caddyfile:16` to `:38`; verified live, `/healthz` answered 200 over HTTPS with a system-trust-store certificate and `strict-transport-security` and `x-content-type-options` headers set and no `Server` header | MET |
| "the database port itself never opens to the internet" | P10 (443 connects from this machine, 5432 refuses in the same seconds) and P10c (`ss` reads the loopback binding on the box) both pass live, both mutation-proven red | MET. The runbook's account of WHY, naming a Hetzner firewall, is false: F-4.11-J-04 |
| "a systemd service or a small container on the Hetzner box, stateless" | `graph-query-service.service`; the only in-process state is the rate-limit deque (`app.py:417`) | MET, with the single-worker constraint undocumented: F-4.11-J-16 |
| "logging every call (what was queried, when, and the caller)" | `app.py:519` to `:525` (the call line), `:476` (auth-rejected), `:486` (rate-limited), caller by SHA-256 digest at `:277` to `:285` | MET as code. The rate-limited half has no verify surface: F-4.11-J-03 |
| "swaps the tool's internal transport with no change to its schema or callers, proving Decision D's two-way door" | the swap is entirely inside `graph_connection.execute_cypher:490` to `:520`; `cypher_query.py`'s three call sites are unchanged in the diff | MET, and this is the phase's cleanest result |
| "its real value is populated when the service is built" (`GRAPH_QUERY_TOKEN`) | `env.example` Layer 1 block rewritten; the runbook's "The credential" section | MET; the dangling reference Section 24 left is closed |

## E. The security surface

Can any input reach the database without passing server-side `validate_cypher`? No. I traced every path into `execute_cypher`:

- `/v1/cypher` is the only route that touches the graph. `/healthz` returns a literal and `/openapi.json` is static.
- The order in `app.py:461` to `:551` is auth, rate limit, JSON parse, Pydantic, log, `_validate_row_limit`, `_validate_timeout`, `_validate_as_clause`, `validate_cypher`, and only then `execute_cypher(result.normalized_cypher, ...)`. It executes the NORMALIZED text, not the input, so the bounded `LIMIT` injection cannot be skipped.
- `params` is the one field that does not pass a validator, and it does not need to: it crosses as a bound `agtype` parameter through the `PREPARE`/`EXECUTE` mechanics in `graph_connection`, never spliced into Cypher text.
- `as_clause` IS interpolated into SQL by `graph_connection._build_prepare_sql`, and it now arrives over the network. It is checked twice, by `app.py:187` and independently by `graph_connection.py:180` and `:316`, against the same tight pattern (`^\([A-Za-z_][A-Za-z0-9_ ,]*\)$`: no quotes, no semicolons, no parentheses). The live probe confirmed `"(result agtype); DROP TABLE users"` is refused.
- P3b proves rejection precedes execution with a tripwire, and it is mutation-proven (M2b).

Can the bearer credential leak into a response body, a log line, an exception string, a systemd status line, or the Caddy access log?

- Response body: no. Verified live, the probe script scanned every response for the token and found none. `app.py`'s error handler emits only `code`, `message`, `retry_after`.
- Log line: no in the code I can read. `_caller_digest` (`:277`) is a truncated SHA-256 and is what every log line carries. I confirmed the emitted lines directly: `graph_query_service auth rejected caller=09f9d01b0bbd0da4`, `graph_query_service rate limited caller=16a2c23a79727c32 retry_after=59.91`, `graph_query_service call caller=... cypher=... row_limit=... timeout_s=...`.
- Exception string: the transport routes every raised message through `graph_connection._redact` against the token (`graph_http_transport.py:214`, `:230`, `:239`, `:249`, `:263`, `:348`) and `test_graph_http_transport.py:346` to `:414` covers it.
- systemd status line: the credential lives in `EnvironmentFile=`, not in `ExecStart=`, so it does not appear in `systemctl status` or in the process command line. Correct by construction.
- Caddy access log: UNVERIFIED. `deploy/Caddyfile:35` to `:38` enables a JSON access log with no explicit `log_credentials` setting. Caddy's default is to redact `Authorization`, but I could not read the deployed Caddy version, the effective config, or the log file to confirm, and no gate arm checks it. Stated as a fail per the evidence rules.

Is the auth comparison constant-time, and is the failure path uniform? The comparison is `hmac.compare_digest` (`app.py:302`), correct. The failure path is NOT uniform: F-4.11-J-08.

Does the systemd unit contradict its own claims? Partly: F-4.11-J-14.

Testing the lead's judgment that the security scan stays with build phase 4.12. The judgment holds. I looked for a reachable path from this port to anything user-facing or to any user data and found none:

- `deploy.sh:42` to `:51` copies exactly `services/__init__.py`, `services/graph_query_service/{__init__,app,README}`, `src/system_03_search_agent/__init__.py`, `tools/__init__.py`, and four tool modules (`cypher_validator`, `graph_schema_constants`, `graph_connection`, `graph_http_transport`). None of the API, auth, session-memory, feedback, or user-database code is deployed at all.
- `app.py`'s imports are those three tool modules and nothing else from `src/`. There is no route, import, or credential on the box that reaches `USER_DB_URL`, `interactions`, `auth_sessions`, or any model provider.
- The credential the service holds is `kg_reader`, read-only at the connection level, against a graph containing already-public NCBI content.
- The unit's `IPAddressDeny=any` (`:59`) means the service process cannot reach any non-loopback address even if it wanted to.

So the exposure this port creates is: one authenticated read-only endpoint, one unauthenticated liveness probe, and one unauthenticated schema document. The scan's trigger, a surface a non-owner can reach the PRODUCT through, is still 4.12's. Recorded as tested and upheld.

What the judgment does not cover, and what I am filing separately, is that opening the port also opened an unauthenticated, unthrottled request path against the box (F-4.11-J-05). That is an availability and audit concern rather than a data-exposure one, and it does not change where the scan belongs.

## F. The retry-safety and error contract

Reading each error a caller can provoke as the Act step would:

| Error | Message says what to do next? | Note |
|---|---|---|
| `cypher_rejected` (write clause, unknown label, missing label) | Yes, "Retry generation with a read-only query_intent" / "constrained to the sliced schema" / "with an explicit edge label" | Good. Verified live |
| `invalid_payload`, absurd `row_limit` | Yes, "Retry with a smaller row_limit" | Good |
| `invalid_payload`, `timeout_s <= 0` | Yes, "retry with a positive value" | Good |
| `invalid_payload`, bad `as_clause` | No | F-4.11-J-12 |
| `invalid_payload`, malformed JSON | No | F-4.11-J-12 |
| `unauthorized` | No | F-4.11-J-12 |
| `rate_limited` | Yes, names the interval and the saturated family, and carries a numeric `retry_after` | Good, and it is the clause `tool-call-budgets` is most specific about |
| `timeout` | Yes, "retry with a narrower query_intent or a smaller query_class" | Good in the service; but a real client almost never sees it, F-4.11-J-06 |
| `graph_unavailable` from `GraphAuthError` | Yes, and unusually well: "this is not a problem with your bearer token, escalate to an operator rather than retrying" | The best error message in the phase |
| `graph_wire_encoding` | Yes, "report it rather than retrying the same query" | Good |
| Client-side timeout | Wrong advice: "verify GRAPH_QUERY_URL is reachable and retry" after a full budget burn | F-4.11-J-06 |
| Server-side `cypher_rejected` as seen by the Act step | Arrives as `GraphConnectionError`, indistinguishable from an outage | F-4.11-J-13 |

Idempotency holds trivially: every path is a read through a read-only role, so retrying is safe in the sense the retry-safety gate means. Nothing in this service writes.

## What I could NOT verify

Stated plainly, because an unverified claim is a fail rather than a silence. Each of these is a check this round did not pass.

1. Anything on the box itself. Direct `ssh` was refused by this session's permission classifier ("Blocked by classifier"), and I declined to route ssh commands through the pytest arm that runs one, since that would be using a test to execute a non-test action. The consequence is that ALL of the following are unverified: that `check_drift.sh` currently returns 5 of 5; that the deployed `app.py` and validator are the ones I reviewed; that `service.env` is mode 0600; that the systemd unit on the box is the one in this repository; that any of its hardening properties actually applied (`systemd-analyze security` was not run); that Caddy's effective config is `deploy/Caddyfile`; that journald's rate-limit and retention settings are the defaults I reasoned about; that the Caddy access log does not contain `Authorization` values; that the service survives a reboot (T-4.11-04's last criterion); and that `kg_reader` is the role the deployed service actually connects as. The gate covers exactly one on-box property, P10c's Postgres binding, and it passes.
2. Byte-equality between the two transports. See F-4.11-J-02. I verified the HTTPS side's wire format and ground truth independently, which is not the same claim.
3. That the per-call timeout is enforced at the service. P6 has never asserted it, and I did not construct a query engineered to outrun a 90-second budget against a live production graph.
4. The E-utilities-style question of whether the rate limit resets correctly across a real 60-second window boundary against the deployed service. I tested the limiter in process only, deliberately, rather than firing 62 requests at production.
5. A whole-suite regression baseline. F-4.11-J-17: two runs of the same tree disagreed (29 failed, then 6 failed), and neither set touches this phase's files, so I can state that this phase's own files are clean (`tests/system_03_search_agent/tools`: 1332 passed, 96 skipped; `tests/services/graph_query_service`: passes) but cannot certify the suite.
6. Whether the deployed service rejects an over-large request body. `deploy/Caddyfile:23` to `:25` caps it at 256KB and nothing else does; the app itself calls `await request.json()` with no size guard (`app.py:502`). I did not send a large body to production to find out. If Caddy is ever bypassed or reconfigured, there is no second bound.

## Notes for the lead

- Transcribe these as `F-4.11-J-01` through `F-4.11-J-17`. I file, I do not close.
- The two Rule 4 items are F-4.11-J-03 (`Regression of: F-4.11-03`) and F-4.11-J-04 (`Regression of: F-4.11-02`). Per the brief, the phase stops mid-round on either.
- The cheapest high-value fix in the list is F-4.11-J-01: removing `@requires_graph` from P3, P3b, P11 and P11b makes nine arms run everywhere, and I have already proven they pass without a graph. That does not fix F-4.11-J-02, which needs a decision rather than an edit: either the byte-equality property gets a durable artifact (a pinned fixture of psycopg2 rows captured while the tunnel was open, compared against a live HTTPS read), or the gate should say out loud, in its coverage statement, that its central premise is now a one-time historical measurement.
- `ruff check` on this phase's new files is clean. The three findings under `tracker/preflight.py` (one `EXE001`, two `UP041`) are all present on `develop` and are not this phase's.
- `python tracker/check_doc_drift.py --check` returns `ok: 10 facts computed | 0 stale | 0 structural`.
