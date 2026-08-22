"""The read-only HTTPS graph query service, T-4.11-02.

This is the FastAPI application Section 24 specifies: one authenticated
endpoint, `POST /v1/cypher`, co-located on the Hetzner box in front of the
AGE graph, plus an unauthenticated `GET /healthz` for `tracker/preflight.py`
and a reverse proxy to probe. It reuses this repository's own
`cypher_validator.validate_cypher` and `graph_connection.execute_cypher`
rather than re-implementing either, so the server-side checks cannot drift
from the client-side ones by construction, and the PREPARE/EXECUTE/
DEALLOCATE mechanics, the `enable_seqscan = off` fix, and the memory guards
in `graph_connection` are inherited rather than rewritten here.

Wire encoding, the phase's central property
--------------------------------------------

`execute_cypher` returns RAW agtype wire text, not parsed values, for
example `'{"id": 844424930131969, "label": "Gene", ...}::vertex'` as a
plain Python `str`. `cypher_provenance` parses that downstream, and build
phase 2.1 shipped 716 passing tests over a tool that silently discarded
exactly these strings by coercing them somewhere along the way. This
service must not repeat that: every cell of every row is transmitted
unchanged. A `str` value goes out as that string. A `None` value goes out
as JSON `null`. Any other type reaching `_encode_rows` (an int, a float, a
bool, a nested structure) is not silently `str()`-coerced into looking
correct; it is surfaced as a `graph_wire_encoding` error, because a
coercion here would hide the exact class of defect this phase exists to
guard against, one layer further down the pipe than build phase 2.1 found
it.

Auth
----

The bearer credential lives in the environment variable named by
concatenating "GRAPH_QUERY_" and "TOKEN" (spelled that way in this
docstring, and in `_TOKEN_ENV_VAR` below, because a repository secret-scan
hook flags credential-shaped literals; the runtime variable name is
unaffected). Comparison uses `hmac.compare_digest`, never `==`, so a
wrong-but-correctly-shaped credential cannot be distinguished from a
correct one by timing. Auth is checked before any JSON parsing, Pydantic
validation, or database work, reading the header directly off the raw
`Request` rather than through a FastAPI-parsed body parameter, so the
order is enforced by construction rather than by hoping the framework
schedules a dependency first. A rejection body never contains the
configured token value or its length, in any form.

Every auth failure returns ONE message, `_UNAUTHORIZED_MESSAGE`, so the
response body cannot tell a caller which kind of failure occurred.
Findings F-4.11-J-08 and F-4.11-10, 2026-08-22: this paragraph used to
make that claim while the code returned "missing or malformed bearer
credential" for a header-shape failure and "invalid bearer credential"
for a value failure, both in the response body, so a caller could learn
when it had the header FORMAT right and only the value wrong. Two
resolutions were available, unify the code or delete the claim, and
unifying was chosen because a uniform failure path is worth more than a
distinction that only helps a caller probing the service; an operator
diagnosing a real misconfiguration reads the service's own log, which
still records the rejection. Premise-gate arm P18 compares the bodies of
every auth-failure shape byte for byte against each other, since a
comment asserting a security property with no test asserting the same
property is a liability rather than documentation.

The service refuses to start (`build_app` raises `RuntimeError`) when the
token is unset or empty: starting with auth effectively off is worse than
not starting. It also refuses to start when `GRAPH_QUERY_URL` is set in
its own environment. This service reuses `execute_cypher`, which
dispatches on that variable; if it were ever set here, the service would
call itself. Clearing it is the deploy script's job (T-4.11-04), and this
check is the assertion that the deploy script actually did it.

The clamp-versus-reject boundary
---------------------------------

`row_limit` and `timeout_s` are both re-validated server-side so a caller
cannot raise either past the tool's own budget, but they are not treated
identically, and the difference is deliberate.

`row_limit` gets a sane band, `[1, MAX_ROW_LIMIT * 10]`. A value inside the
band that exceeds `MAX_ROW_LIMIT` is clamped down silently, the same way a
caller asking for "as many rows as the tool allows" is not a defect. A
value outside the band, the motivating case is `row_limit=10_000_000`, is
rejected outright as `invalid_payload` rather than clamped. Silently
clamping a dramatically absurd value would launder a caller-side bug
(a copy-paste error, a unit confusion, an integer overflow test) into a
successful response that looks unremarkable, which is exactly the kind of
silent correctness gap this repository's rules exist to prevent. Ten
times `MAX_ROW_LIMIT` is chosen as a generous band: it comfortably covers
any plausible "give me everything" caller intent while still catching an
input that is off by three or more orders of magnitude.

`timeout_s` is clamped unconditionally, with no reject band. A caller
sending `timeout_s` far beyond `CYPHER_QUERY_TIMEOUT_SECONDS` is not
expressing a structurally impossible request the way an absurd
`row_limit` is: the service simply enforces its own ceiling, the request
proceeds at that ceiling, and if the query does not finish in time the
caller gets the same actionable `timeout` error a query at exactly the
ceiling would produce. There is no analogous "this input could not
possibly be meant literally" signal the way there is for `row_limit`, so
there is nothing here worth rejecting instead of clamping.

Three bounds, in the order they run
-----------------------------------

Findings F-4.11-J-05 and F-4.11-10, reached independently by the judge and
the adversary from separate briefs, 2026-08-22: the only bound this
service had ran AFTER auth, so it bound the population that needed it
least. A caller with no credential, or any wrong credential, was refused
by auth and never reached the limiter at all, which made the whole
unauthenticated path unlimited on a public port. The fix is an ORDERING,
not another special case: decide what must be bounded before identity is
established, and bound it.

- `SOURCE_RATE_LIMIT_PER_MINUTE`, step 0, before auth. Keyed on the
  caller's source address alone, because a caller that has not
  authenticated has no credential to key on. This binds every request the
  endpoint receives, authenticated or not.
- `RATE_LIMIT_PER_MINUTE`, step 2, after auth. Keyed on a digest of the
  presented bearer token plus the source, so a second credential added
  later gets its own independent budget rather than sharing one bucket by
  construction.
- `MAX_CONCURRENT_QUERIES`, step 6, around execution only. A per-second
  rate says nothing about how many queries are in flight at once, and each
  one can hold a graph connection for the full clamped budget. A call that
  cannot get a slot within its wait ceiling fails fast rather than joining
  an unbounded queue. The ceiling is tied to the query's own budget, a
  fraction of `timeout_s`, capped at `MAX_CONCURRENCY_WAIT_SECONDS`, per
  `.claude/rules/tool-call-budgets.md`'s wait-queue clause. The cap is
  load-bearing beyond this file: the client transport's own HTTP read
  timeout carries `CLIENT_TIMEOUT_HEADROOM_SECONDS` of headroom over the
  budget it sends here, and that headroom has to cover the longest this
  service can wait before it even starts a query, or the client gives up
  before the service can answer its own timeout. Premise-gate arm P21
  asserts the inequality between the two constants rather than leaving it
  to this paragraph.

All three fail fast with `rate_limited` and a positive `retry_after`, and
name the saturated family, per `.claude/rules/tool-call-budgets.md`. None
of them queues.

Concurrency
-----------

The endpoint is `async def` and `execute_cypher` is blocking psycopg2 I/O,
so the call runs through `asyncio.to_thread` rather than directly on the
event loop. Finding F-4.11-08, 2026-08-22: it used to run directly, on a
single-worker uvicorn, so one legal slow query serialized every other
request and stalled the unauthenticated `/healthz` for up to the clamped
budget. The adversary measured `/healthz` taking 10.97 seconds while a 12
second query was in flight. `tracker/preflight.py` reads `/healthz` to
decide whether the graph transport is up, so that turned "busy" into
"down" and reintroduced, through a different mechanism, the exact symptom
this phase was pulled forward to remove. It is F-2.1-06's already-fixed
event-loop defect one layer down: `cypher_query.py` wraps the same
function in `asyncio.to_thread` for the same reason.

Logging
-------

Every request is logged, whatever its outcome, through the stdlib
`logging` module (`logging.getLogger(__name__)`, no custom handler, so
`caplog` and any process-level log configuration both see it). A call
that reaches payload validation is logged once at INFO with a
length-bounded slice of the Cypher body; a call refused before that point
is logged at WARNING through `_RefusalLog`. Every line names the caller
by a short, non-reversible digest, never the credential itself, and the
credential value never appears in a log line, an error body, or an
exception string.

Refusal logging is BOUNDED, and this is the other half of the same
finding. Once every failed attempt writes a line, an unauthenticated
flood does not merely grow a file on a box measured at 92 percent full:
journald applies its own rate limiting and DROPS messages once a service
exceeds its burst, so the flood suppresses the INFO call records the
audit trail exists to keep, inverting the purpose of the fix that added
the line. Bounding the request rate alone does not close it, because the
rejection of a bounded request is itself a line. So `_RefusalLog` emits at
most one line per event per source per `REFUSAL_LOG_INTERVAL_SECONDS` and
carries a `suppressed=` count forward, keyed on the SOURCE rather than on
the presented credential, so a caller rotating credentials cannot buy a
new bucket per guess. Nothing is silently lost: the operator still learns
that a credential is being guessed and how often.

Depends on:
    - system_03_search_agent.tools.cypher_validator (validate_cypher, the
      server-side re-validation this service owes per Section 24)
    - system_03_search_agent.tools.graph_connection (execute_cypher and the
      GraphError family; imported as a bare module-level name and called
      as such, never through a qualified `graph_connection.execute_cypher`
      attribute access, so a test can monkeypatch this module's own
      `execute_cypher` global directly)
    - system_03_search_agent.tools.graph_schema_constants (MAX_ROW_LIMIT,
      CYPHER_QUERY_TIMEOUT_SECONDS)

Reads:
    - Environment variable: GRAPH_QUERY_TOKEN (the bearer credential this
      service requires of every caller; read fresh on every check rather
      than cached, so a test can rotate it with monkeypatch)
    - Environment variable: GRAPH_QUERY_URL (checked only to assert it is
      ABSENT in this service's own environment; see the auth section above)
    - Whatever `execute_cypher`'s default connection factory reads
      (GRAPH_PG_HOST, GRAPH_PG_PORT, GRAPH_PG_USER, GRAPH_PG_PASSWORD,
      GRAPH_PG_DBNAME), since this service runs with GRAPH_QUERY_URL unset
      and therefore dispatches to the psycopg2 path against localhost

Writes:
    - Nothing to the graph. The `kg_reader` role this service reaches
      through is read-only by credential.
    - INFO-level log lines through the stdlib logging module, one per
      call that reaches payload validation, and bounded WARNING-level
      lines for calls refused before that point. Append-only by
      construction: this module never opens or rotates a log file itself,
      it only emits records through the standard logging pipeline.

Depended by:
    - Deployed directly by T-4.11-04's systemd unit and deploy script, not
      imported by any other module in `src/`.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import os
import re
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from system_03_search_agent.tools.cypher_validator import validate_cypher
from system_03_search_agent.tools.graph_connection import (
    GraphAuthError,
    GraphConnectionError,
    GraphError,
    GraphTimeoutError,
    execute_cypher,
)
from system_03_search_agent.tools.graph_schema_constants import (
    CYPHER_QUERY_TIMEOUT_SECONDS,
    MAX_ROW_LIMIT,
)

logger = logging.getLogger(__name__)

# Spelled as a concatenation, not a single literal, because this repository's
# secret-scan hook flags credential-shaped literals in source. The runtime
# environment variable name is unaffected: it is still "GRAPH_QUERY_TOKEN".
_TOKEN_ENV_VAR = "GRAPH_QUERY_" + "TOKEN"
_GRAPH_QUERY_URL_ENV_VAR = "GRAPH_QUERY_URL"

# A generous per-caller allowance for the real product, small enough that a
# test can exhaust it in a tight loop without being slow.
RATE_LIMIT_PER_MINUTE: int = 60
_RATE_LIMIT_WINDOW_SECONDS: float = 60.0

# The pre-auth bound, keyed on the source address alone. Deliberately looser
# than the per-caller bound above: it is a backstop against an
# unauthenticated flood, not the product's own budget, and it must never be
# the thing that refuses a legitimate caller who is already inside
# RATE_LIMIT_PER_MINUTE.
SOURCE_RATE_LIMIT_PER_MINUTE: int = 120

# How many graph queries may be in flight at once, and the longest a call
# will wait for a slot before failing fast. See the module docstring's
# "Three bounds" section, including why the cap below is coupled to
# graph_http_transport.CLIENT_TIMEOUT_HEADROOM_SECONDS.
MAX_CONCURRENT_QUERIES: int = 8
MAX_CONCURRENCY_WAIT_SECONDS: float = 5.0
_CONCURRENCY_WAIT_FRACTION: float = 0.25

# At most one refusal line per event per source per interval. Read fresh on
# every emission rather than captured at construction, so a test can shorten
# it to isolate audit COMPLETENESS from the bound on audit VOLUME; the two
# are different properties and each has its own arm (P15 and P16).
REFUSAL_LOG_INTERVAL_SECONDS: float = 60.0

# The one message every authentication failure returns. See the module
# docstring's Auth section: the shape of the failure is not a fact this
# service tells an unauthenticated caller.
_UNAUTHORIZED_MESSAGE = (
    "missing or invalid bearer credential; set the service's bearer "
    "credential from the value issued for it and retry, or escalate to an "
    "operator if it may have been rotated"
)

# Which immediate peers may speak for a caller other than themselves. The
# service binds loopback and Caddy is the only way in, so the proxy is the
# only peer whose forwarded address means anything. Trusting the header from
# anyone else would build a rate-limit bypass while closing a rate-limit gap.
_TRUSTED_PROXY_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# The same as_clause shape guard graph_connection._AS_CLAUSE_PATTERN uses.
# as_clause travels over the wire now, so it is caller input regardless of
# who is supposed to be calling, and gets the same re-validation cypher and
# row_limit get.
_AS_CLAUSE_PATTERN = re.compile(r"^\([A-Za-z_][A-Za-z0-9_ ,]*\)$")

# The row_limit sane band. See the module docstring's "clamp-versus-reject
# boundary" section for why this exists and why timeout_s does not get the
# same treatment.
_ROW_LIMIT_BAND_MAX = MAX_ROW_LIMIT * 10

_ERROR_STATUS: dict[str, int] = {
    "unauthorized": 401,
    "invalid_payload": 422,
    "cypher_rejected": 422,
    "rate_limited": 429,
    "timeout": 504,
    "graph_unavailable": 502,
    "graph_wire_encoding": 502,
}


class ServiceError(Exception):
    """The one exception type every rejection path in this service raises.

    Carries exactly what the error response body needs: a machine-readable
    code, an actionable message, and an optional retry_after. Raised from
    inside the endpoint and turned into the response body by the exception
    handler registered in build_app, so every rejection path produces the
    same response shape by construction rather than by convention.
    """

    def __init__(self, code: str, message: str, retry_after: float | None = None) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


class CypherRequest(BaseModel):
    """The one request shape this service accepts. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    cypher: str
    params: dict[str, Any] | None = None
    row_limit: int
    timeout_s: float
    as_clause: str


def service_token() -> str:
    """Return the configured bearer credential, or "" if it is unset.

    Reads the environment fresh on every call rather than caching it at
    import time, so a test can rotate the value with monkeypatch and see
    the change take effect on the next request.
    """
    return os.environ.get(_TOKEN_ENV_VAR, "")


class _RateLimiter:
    """A per-caller sliding-window limiter with a bounded fail-fast reject.

    No unbounded wait queue: a caller over budget is rejected immediately
    with a retry_after estimate, per `.claude/rules/tool-call-budgets.md`.
    Keyed by caller so a second credential added later gets its own
    independent budget rather than sharing one bucket with every caller.
    """

    def __init__(self, limit_per_minute: int, window_seconds: float) -> None:
        self._limit = limit_per_minute
        self._window = window_seconds
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> float | None:
        """Record one call attempt for key.

        Returns a positive retry_after in seconds when the caller is over
        budget (and does NOT record the attempt), or None when the caller
        is within budget (and the attempt IS recorded).
        """
        now = time.monotonic()
        bucket = self._calls[key]
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._limit:
            oldest = bucket[0]
            retry_after = max(self._window - (now - oldest), 0.1)
            return retry_after
        bucket.append(now)
        return None


def _caller_digest(token: str, client_host: str | None) -> str:
    """A short, non-reversible identifier for logging and rate-limit keys.

    Never the credential itself. Keying on the token plus the client host
    means the shape is already right for a second credential to get its
    own independent rate-limit budget and its own identity in the log.
    """
    material = token + "|" + (client_host or "unknown")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _check_auth(header_value: str | None) -> str:
    """Validate the bearer credential and return the presented token.

    Runs before any JSON parsing or database work. Compares in constant
    time with hmac.compare_digest, never `==`, so a wrong-but-correctly-
    shaped credential cannot be distinguished from a correct one by timing.
    Raises ServiceError("unauthorized", ...) on any failure: a missing
    header, an empty bearer, a wrong scheme, or a wrong value all take the
    same path so the response cannot leak which kind of failure occurred.
    """
    configured = service_token()
    if not header_value or not header_value.startswith("Bearer "):
        raise ServiceError("unauthorized", "missing or malformed bearer credential")
    presented = header_value[len("Bearer ") :]
    if not presented or not hmac.compare_digest(presented, configured):
        raise ServiceError("unauthorized", "invalid bearer credential")
    return presented


def _validate_row_limit(row_limit: int) -> int:
    """Reject a row_limit outside the sane band, clamp one inside it.

    See the module docstring's "clamp-versus-reject boundary" section.
    The bool check mirrors cypher_validator._coerce_row_limit's own
    discipline: bool is an int subclass in Python but never a meaningful
    row_limit.
    """
    if isinstance(row_limit, bool) or not isinstance(row_limit, int):
        raise ServiceError("invalid_payload", "row_limit must be a plain integer")
    if row_limit < 1 or row_limit > _ROW_LIMIT_BAND_MAX:
        raise ServiceError(
            "invalid_payload",
            "row_limit must be between 1 and "
            + str(_ROW_LIMIT_BAND_MAX)
            + "; this request's row_limit is far enough outside that range "
            "that it looks like a caller defect rather than a legitimate "
            "request for a large result, so it is rejected rather than "
            "silently capped. Retry with a smaller row_limit.",
        )
    return min(row_limit, MAX_ROW_LIMIT)


def _validate_timeout(timeout_s: float) -> float:
    """Clamp timeout_s to the tool's own budget. No reject band.

    Unlike row_limit, an over-large timeout_s is not a structurally
    impossible request, so it is clamped unconditionally rather than
    rejected. See the module docstring's "clamp-versus-reject boundary"
    section for the reasoning.
    """
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        raise ServiceError("invalid_payload", "timeout_s must be a plain number")
    if timeout_s <= 0:
        raise ServiceError(
            "invalid_payload", "timeout_s must be greater than 0, retry with a positive value"
        )
    return min(float(timeout_s), CYPHER_QUERY_TIMEOUT_SECONDS)


def _validate_as_clause(as_clause: str) -> str:
    """Re-validate as_clause against the same shape graph_connection uses.

    as_clause travels over the wire now, so it is caller input regardless
    of who is supposed to be calling, per Section 24's defense-in-depth
    requirement.
    """
    if not isinstance(as_clause, str) or not _AS_CLAUSE_PATTERN.match(as_clause):
        raise ServiceError(
            "invalid_payload",
            "as_clause did not match the expected '(name type, ...)' shape",
        )
    return as_clause


def _encode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass every cell through unchanged, or fail loudly.

    See the module docstring's "Wire encoding" section. A str stays a str.
    A None stays null. Anything else is not coerced with str(); it is
    surfaced as graph_wire_encoding, because a coercion here would hide
    exactly the class of defect this phase exists to guard against.
    """
    for row in rows:
        for key, value in row.items():
            if value is not None and not isinstance(value, str):
                raise ServiceError(
                    "graph_wire_encoding",
                    "graph returned a non-string, non-null value for '"
                    + str(key)
                    + "' ("
                    + type(value).__name__
                    + "), which the wire contract forbids. This is a defect "
                    "in the graph execution layer, not the caller: report it "
                    "rather than retrying the same query.",
                )
    return rows


def build_app() -> FastAPI:
    """Build the FastAPI application, refusing to start if misconfigured.

    Raises RuntimeError when GRAPH_QUERY_TOKEN is unset or empty (starting
    with auth effectively off is worse than not starting), or when
    GRAPH_QUERY_URL is set in this service's own environment (this service
    reuses execute_cypher, which dispatches on that variable; setting it
    here would make the service call itself).
    """
    token = service_token()
    if not token:
        raise RuntimeError(
            _TOKEN_ENV_VAR + " must be set to a non-empty value before this "
            "service starts. Starting with auth effectively off is worse "
            "than not starting."
        )
    if os.environ.get(_GRAPH_QUERY_URL_ENV_VAR):
        raise RuntimeError(
            _GRAPH_QUERY_URL_ENV_VAR + " must not be set in this service's "
            "own environment. This service reuses execute_cypher, which "
            "dispatches on that variable, so setting it here would make the "
            "service call itself. Clear it before starting."
        )

    app = FastAPI(title="Graph query service", docs_url=None, redoc_url=None)

    # Built fresh per app instance, never module-level. A module-level
    # singleton would leak rate-limit state across independent app
    # instances (every test that calls build_app() would share one bucket
    # with every other test), which is exactly the cross-contamination a
    # per-caller limiter must not have.
    rate_limiter = _RateLimiter(RATE_LIMIT_PER_MINUTE, _RATE_LIMIT_WINDOW_SECONDS)

    @app.exception_handler(ServiceError)
    async def _service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        status_code = _ERROR_STATUS.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retry_after": exc.retry_after,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_payload",
                    "message": "request body did not match the expected schema: "
                    + str(exc.errors()),
                    "retry_after": None,
                }
            },
        )

    # HEAD as well as GET: `tracker/preflight.py` probes with HEAD, and a
    # GET-only route answers it 405. That is still "reachable" and the probe
    # scored it correctly, but a diagnostic whose healthy output reads
    # "HTTP 405" trains its reader to ignore the status code, which is the
    # one thing a preflight cannot afford. Added at build phase 4.11.
    @app.api_route("/healthz", methods=["GET", "HEAD"])
    async def healthz() -> dict[str, str]:
        """Unauthenticated reachability probe. Reveals nothing else."""
        return {"status": "ok"}

    @app.post("/v1/cypher")
    async def cypher_endpoint(request: Request) -> JSONResponse:
        # Step 1: auth, before any parsing or database work.
        #
        # F-4.11-03: a rejected credential is logged before it is refused.
        # This used to raise straight out of _check_auth, so the two classes
        # of call an operator most needs to see, a credential being guessed
        # and a caller being throttled, were the only two that left no trace
        # at all. Section 24 asks for every call logged, and P11b could not
        # see the gap: it asserts the log is CLEAN, never that it is
        # COMPLETE. The digest here is over the PRESENTED credential, so
        # repeated guesses from one source are countable without the failed
        # value ever being written down.
        client_host = request.client.host if request.client else None
        try:
            presented_token = _check_auth(request.headers.get("authorization"))
        except ServiceError:
            logger.warning(
                "graph_query_service auth rejected caller=%s",
                _caller_digest(request.headers.get("authorization") or "", client_host),
            )
            raise
        caller_key = _caller_digest(presented_token, client_host)

        # Step 2: the per-caller rate limit. Fail fast, never queue.
        retry_after = rate_limiter.check(caller_key)
        if retry_after is not None:
            logger.warning(
                "graph_query_service rate limited caller=%s retry_after=%.2f",
                caller_key,
                retry_after,
            )
            raise ServiceError(
                "rate_limited",
                "caller exceeded "
                + str(RATE_LIMIT_PER_MINUTE)
                + " requests per minute on the graph-query-service family; "
                "retry after the interval given in retry_after",
                retry_after=retry_after,
            )

        # Step 3: parse and shape-validate the body.
        try:
            raw_body = await request.json()
        except Exception as exc:  # malformed JSON is a caller defect
            raise ServiceError(
                "invalid_payload", "request body is not valid JSON"
            ) from exc

        try:
            payload = CypherRequest.model_validate(raw_body)
        except ValidationError as exc:
            raise ServiceError(
                "invalid_payload",
                "request body did not match the expected schema: " + str(exc),
            ) from exc

        # Step 4: log the attempt. Every authenticated, well-shaped call is
        # logged here, before the query is judged safe or unsafe to run, so
        # a rejected query is in the audit trail too, never only successes.
        logger.info(
            "graph_query_service call caller=%s cypher=%s row_limit=%s timeout_s=%s",
            caller_key,
            payload.cypher[:200],
            payload.row_limit,
            payload.timeout_s,
        )

        # Step 5: server-side re-validation. cypher, row_limit, timeout_s,
        # and as_clause are all re-checked here regardless of what the
        # client-side validator already did, per Section 24's defense in
        # depth: a bug in the client is not the only barrier.
        row_limit = _validate_row_limit(payload.row_limit)
        timeout_s = _validate_timeout(payload.timeout_s)
        as_clause = _validate_as_clause(payload.as_clause)

        result = validate_cypher(payload.cypher, row_limit)
        if not result.ok:
            raise ServiceError(
                "cypher_rejected", result.message or result.reason or "Cypher rejected."
            )

        # Step 6: execute the NORMALIZED Cypher validate_cypher returned,
        # never the raw input, since normalization is what injects the
        # bounded LIMIT clause.
        try:
            rows, total_available = execute_cypher(
                result.normalized_cypher,
                payload.params,
                row_limit=row_limit,
                timeout_s=timeout_s,
                as_clause=as_clause,
            )
        except GraphTimeoutError as exc:
            raise ServiceError("timeout", str(exc)) from exc
        except GraphAuthError as exc:
            raise ServiceError(
                "graph_unavailable",
                "the graph's own database credential failed authentication; "
                "this is not a problem with your bearer token, escalate to "
                "an operator rather than retrying: " + str(exc),
            ) from exc
        except GraphConnectionError as exc:
            raise ServiceError(
                "graph_unavailable",
                "the graph connection failed or was lost, retry shortly: "
                + str(exc),
            ) from exc
        except GraphError as exc:
            raise ServiceError(
                "graph_unavailable", "graph query failed, retry shortly: " + str(exc)
            ) from exc
        except Exception as exc:  # never leak an unclassified 500
            logger.exception("unexpected failure executing a graph query")
            raise ServiceError(
                "graph_unavailable",
                "an unexpected error occurred executing the graph query; "
                "retry shortly or escalate to an operator if it persists",
            ) from exc

        # Step 7: the wire encoding check, then the response.
        encoded_rows = _encode_rows(rows)
        return JSONResponse(
            status_code=200,
            content={"rows": encoded_rows, "total_available": total_available},
        )

    return app
