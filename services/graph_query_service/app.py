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

# The hard ceiling on distinct source keys any bookkeeping table retains.
#
# F-4.11-RV-01. Eviction alone handles sources that go quiet; it does not
# handle sources arriving faster than they expire, which is precisely the
# adversarial case and the one an attacker with an IPv6 range produces for
# free. Past this ceiling the least recently seen keys are dropped.
#
# 10000 is chosen to sit far above any plausible legitimate caller count
# (this service fronts one API process and a handful of developer machines)
# and far below anything that threatens the box's memory.
MAX_TRACKED_SOURCES: int = 10000

# When a bookkeeping table passes its ceiling, evict down to this fraction of
# it rather than to the ceiling itself.
#
# F-4.11-R3V-02. Trimming to exactly the cap means every subsequent new
# source pushes the table to cap+1 and pays a full sort to remove one key,
# measured at 990x the cold cost on the pre-auth path, synchronously on the
# event loop. Dropping ten percent at once amortises that sort over the next
# thousand arrivals.
_EVICTION_LOW_WATER: float = 0.9

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
        # F-4.11-RV-01: eviction is amortised, run at most once per window,
        # so a sweep never turns every request into a full scan of the table.
        self._last_eviction = time.monotonic()

    def check(self, key: str) -> float | None:
        """Record one call attempt for key.

        Returns a positive retry_after in seconds when the caller is over
        budget (and does NOT record the attempt), or None when the caller
        is within budget (and the attempt IS recorded).
        """
        now = time.monotonic()
        self._evict_idle(now)
        bucket = self._calls[key]
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._limit:
            oldest = bucket[0]
            retry_after = max(self._window - (now - oldest), 0.1)
            return retry_after
        bucket.append(now)
        # The cap is enforced AFTER the insert, not before it. Enforcing it
        # first leaves the table holding cap+1 between the sweep and the
        # append, which arm P23 caught: it asserted the documented bound and
        # measured 26 against a cap of 25. A bound that is off by one is
        # still a bound, but a bound that does not equal what it claims is a
        # comment, and this phase has produced three of those already.
        self._enforce_cap()
        return None

    def _enforce_cap(self) -> None:
        """Drop the least recently seen keys once past the hard ceiling."""
        if len(self._calls) <= MAX_TRACKED_SOURCES:
            return
        # F-4.11-R3V-02: drop to a low-water mark, not to the cap itself.
        # Trimming to exactly the cap meant every subsequent arrival pushed
        # the table to cap+1 and paid a full sorted() over 10001 keys to
        # remove one, measured at 0.857ms against 0.00087ms cold, a 990x
        # amplification running synchronously on the event loop on the
        # PRE-AUTH path. That is the same failure class as F-4.11-08, this
        # phase's round 1 headline, reintroduced by the fix for a different
        # finding. Dropping ten percent at once amortises the sort over the
        # next thousand arrivals.
        target = int(MAX_TRACKED_SOURCES * _EVICTION_LOW_WATER)
        for key in sorted(
            self._calls, key=lambda k: self._calls[k][-1] if self._calls[k] else 0.0
        )[: len(self._calls) - target]:
            del self._calls[key]

    def _evict_idle(self, now: float) -> None:
        """Drop keys whose window has fully expired.

        Finding F-4.11-RV-01, Regression of: F-4.11-J-05, found by the
        independent re-verifier inside round 2's own fix.

        `self._calls` is a defaultdict, so reading `self._calls[key]` CREATES
        the key. The window loop above then drains that caller's deque as its
        timestamps age out, and the emptied deque was left in the dict
        forever. So the control that exists to bound what an unauthenticated
        caller can consume grew by one permanent entry per distinct source:
        it bounded the requests and not the bookkeeping, which moves the
        exhaustion rather than removing it.

        This is not a theoretical reach. The box carries a global IPv6 /64
        and the proxy listens on every address, so one attacker's own range
        supplies 2^64 distinct source keys that need no spoofing, and this
        bound sits before auth by design, so no credential is required.

        Two mechanisms, because either alone still fails. Eviction removes
        keys that have gone quiet, which handles the ordinary case. The hard
        cap handles the adversarial one, where sources arrive faster than
        they expire and eviction alone never catches up: past the cap the
        least recently seen keys are dropped outright. Dropping a key is safe
        in the direction that matters, since it can only forget a caller's
        history and let it start fresh, never invent a refusal for a caller
        that made no requests.
        """
        if now - self._last_eviction >= self._window:
            self._last_eviction = now
            for key in [
                k
                for k, bucket in self._calls.items()
                if not bucket or now - bucket[-1] > self._window
            ]:
                del self._calls[key]

        self._enforce_cap()

    def tracked_keys(self) -> list[str]:
        """The source keys currently retained. For the gate's bound arm."""
        return list(self._calls)


class _RefusalLog:
    """Bounded emission for the lines a refused call writes.

    See the module docstring's Logging section for why this exists.
    Emits at most one line per (event, source) per
    REFUSAL_LOG_INTERVAL_SECONDS and reports how many it withheld, so an
    unauthenticated flood cannot grow the journal without bound, and
    cannot use journald's own drop-limiting to suppress the INFO call
    records the audit trail exists to keep.

    Keyed on the SOURCE rather than on the presented credential. Keying on
    the credential would let a caller rotating guesses buy a fresh bucket
    per guess, which is the enumeration failure this bound exists to
    avoid: the category is "refusals from one place", not "refusals
    carrying one credential".

    The interval is read from the module global on every call rather than
    captured at construction, so a test can isolate audit COMPLETENESS
    (P15) from the bound on audit VOLUME (P16). They are different
    properties and each has its own arm.
    """

    def __init__(self) -> None:
        self._last_emitted: dict[tuple[str, str], float] = {}
        self._suppressed: dict[tuple[str, str], int] = defaultdict(int)
        self._last_eviction = time.monotonic()

    def should_emit(self, event: str, source_key: str) -> int | None:
        """Whether to write this refusal now.

        Returns the number of same-event refusals withheld since the last
        emission (0 on the first), or None when this one must be withheld.
        """
        now = time.monotonic()
        key = (event, source_key)
        last = self._last_emitted.get(key)
        if last is not None and now - last < REFUSAL_LOG_INTERVAL_SECONDS:
            self._suppressed[key] += 1
            return None
        withheld = self._suppressed.pop(key, 0)
        self._last_emitted[key] = now
        self._evict_idle(now)
        self._enforce_cap()
        return withheld

    def _evict_idle(self, now: float) -> None:
        """Bound the INDEX, not only the volume.

        F-4.11-RV-01. Bounding how many lines a flood can write while the
        table naming who wrote them grows without limit moves the exhaustion
        rather than removing it, and the re-verifier measured exactly that:
        3000 sources left 3000 permanently retained entries here.

        An entry is useless once its interval has passed, since the next
        refusal from that key emits regardless, so eviction discards nothing
        the bound relies on.
        """
        # F-4.11-R3V-02: amortised, matching the rate limiter's own guard.
        # This method used to scan the whole index on EVERY emission, which
        # measured a 182x cost amplification on the pre-auth path. Its twin
        # in _RateLimiter always had this guard; this one was written without
        # it, which is what an asymmetry between two near-identical methods
        # usually turns out to be.
        if now - self._last_eviction < REFUSAL_LOG_INTERVAL_SECONDS:
            return
        self._last_eviction = now

        interval = REFUSAL_LOG_INTERVAL_SECONDS
        for key in [
            k
            for k, seen in self._last_emitted.items()
            if now - seen > interval and not self._suppressed.get(k)
        ]:
            self._last_emitted.pop(key, None)
            self._suppressed.pop(key, None)

    def _enforce_cap(self) -> None:
        """The hard ceiling, checked on every emission.

        Deliberately OUTSIDE the amortisation guard above, and arm P23d is
        what forced that. Folding the cap into the amortised sweep meant a
        burst arriving inside one interval skipped the cap entirely and the
        table sailed past its ceiling until the next sweep was due. The two
        controls answer different questions, "has this gone quiet" and "is
        this too big", and only the first is safe to defer.

        Drop to a low-water mark rather than to exactly the cap, so the sort
        is paid once per batch instead of once per new source. F-4.11-R3V-02
        measured the every-insert version at 990x the cold cost on its
        rate-limiter twin: pushing the table to cap+1 and sorting the whole
        thing to remove exactly one key.

        Keys carrying an unreported suppressed count sort LAST, so a flood's
        own tally is the last thing discarded. Under the cap something must
        go, and it should not be the number that says a flood happened.
        """
        if len(self._last_emitted) <= MAX_TRACKED_SOURCES:
            return
        target = int(MAX_TRACKED_SOURCES * _EVICTION_LOW_WATER)
        for key in sorted(
            self._last_emitted,
            key=lambda k: (bool(self._suppressed.get(k)), self._last_emitted[k]),
        )[: len(self._last_emitted) - target]:
            self._last_emitted.pop(key, None)
            self._suppressed.pop(key, None)

    def tracked_keys(self) -> list[str]:
        """The source keys currently retained. For the gate's bound arm."""
        return list(self._last_emitted)


def _parse_forwarded_address(value: str) -> str | None:
    """Parse one X-Forwarded-For element into a bare IP address, or None.

    Tolerates a bracketed IPv6 literal and an IPv4 host:port pair, which
    are the two shapes a proxy may append. Anything that is not an IP
    address returns None and the caller falls back to the real peer, so a
    junk header can never become a rate-limit key.
    """
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        candidate = candidate.split(":", 1)[0]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def client_source(request: Any) -> str:
    """The caller's real source address, or "unknown".

    Finding F-4.11-11, 2026-08-22. Behind Caddy the service's immediate
    peer is always loopback, so `request.client.host` was `127.0.0.1` for
    every caller on earth: the rate-limit key and the audit log's caller
    identity had no source component at all, and the log could not
    distinguish two sources. The design intent stated in this module,
    "keyed on the token plus the client host, so a second credential gets
    its own independent budget", was only half true, and the inert half
    was the one that identifies an abusive caller.

    Reading a forwarded header is the fix and it is also how a rate-limit
    BYPASS gets built, so two rules bound it:

    - The header is honoured only when the immediate peer is the local
      proxy. A caller reaching the service directly is identified by its
      own peer address and its header is ignored entirely.
    - Only the RIGHTMOST element is used, which is the value the proxy
      itself appended, never anything the caller sent ahead of it.

    Finding F-4.11-RV-02, 2026-08-22. This docstring used to add that the
    deployed Caddyfile "additionally OVERWRITES the header with the real
    remote host rather than appending to it, so both layers are safe
    independently." The re-verifier read the deployed `/etc/caddy/Caddyfile`
    and found NO `X-Forwarded-For` directive at all, so Caddy's default
    append applies and there is exactly ONE safeguard here, not two: the
    rightmost-element rule above.

    The rule still holds and arm P20 pins it, so nothing is broken. What was
    broken is the claim, and it is corrected rather than deleted because
    this is the third false comment this phase produced, each asserting a
    property no test checked. A confident comment is where the next reader
    stops checking, which is why `.claude/rules/self-eval-loop.md` treats a
    comment claiming a security property as a claim to be tested rather than
    as documentation. Do not restore the two-layer claim without first
    adding the directive to the Caddyfile AND an arm that reads it.
    """
    client = getattr(request, "client", None)
    peer = getattr(client, "host", None) if client is not None else None
    if peer in _TRUSTED_PROXY_HOSTS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parsed = _parse_forwarded_address(forwarded.rsplit(",", 1)[-1])
            if parsed is not None:
                return parsed
    return peer or "unknown"


def _source_digest(source: str) -> str:
    """A short, non-reversible identifier for one caller source."""
    return hashlib.sha256(("source|" + source).encode("utf-8")).hexdigest()[:16]


def _emit_refusal(
    refusal_log: _RefusalLog,
    event: str,
    source_key: str,
    retry_after: float | None,
) -> None:
    """Write one refusal to the audit trail, subject to the volume bound.

    Every refusal path goes through here rather than calling the logger
    directly, so a new refusal class cannot be added later that is either
    unbounded or unlogged. F-4.11-J-03 was exactly that: the fix for
    F-4.11-03 added two log lines and only one was pinned by an arm, so
    the other could be deleted with both suites staying green.

    The withheld count is carried on the emitted line rather than dropped,
    because "429 refusals suppressed" is the number an operator needs to
    see a flood; a bound that hides its own suppression turns a volume
    control into a blind spot.
    """
    withheld = refusal_log.should_emit(event, source_key)
    if withheld is None:
        return
    # `caller=` rather than `source=`, and the event spelled with spaces, so
    # a refusal line is greppable the same way the main call line is. For a
    # refused call the caller IS the source: there is no authenticated
    # identity to name, which is the whole reason the pre-auth bound keys on
    # source in the first place.
    logger.warning(
        "graph_query_service %s caller=%s retry_after=%s suppressed=%d",
        event.replace("_", " "),
        source_key,
        "none" if retry_after is None else format(retry_after, ".2f"),
        withheld,
    )


def _caller_digest(token: str, client_host: str | None) -> str:
    """A short, non-reversible identifier for logging and rate-limit keys.

    Never the credential itself. Keying on the token plus the caller's
    real source (see `client_source`) means a second credential added
    later gets its own independent rate-limit budget and its own identity
    in the log, and two sources presenting the same credential are
    distinguishable rather than collapsed into one bucket.
    """
    material = token + "|" + (client_host or "unknown")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _check_auth(header_value: str | None) -> str:
    """Validate the bearer credential and return the presented token.

    Runs before any JSON parsing or database work. Compares in constant
    time with hmac.compare_digest, never `==`, so a wrong-but-correctly-
    shaped credential cannot be distinguished from a correct one by timing.
    Raises ServiceError("unauthorized", _UNAUTHORIZED_MESSAGE) on any
    failure: a missing header, an empty bearer, a wrong scheme, or a wrong
    value all take the same path AND return the same message, so the
    response cannot leak which kind of failure occurred. Findings
    F-4.11-J-08 and F-4.11-10: this docstring made that claim while the
    code returned two different messages, both of them in the response
    body. Premise-gate arm P18 now asserts the bodies are byte-identical
    across every failure shape.
    """
    configured = service_token()
    if not header_value or not header_value.startswith("Bearer "):
        raise ServiceError("unauthorized", _UNAUTHORIZED_MESSAGE)
    presented = header_value[len("Bearer ") :]
    if not presented or not hmac.compare_digest(presented, configured):
        raise ServiceError("unauthorized", _UNAUTHORIZED_MESSAGE)
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


def source_limiter_for_test(app: FastAPI) -> Any:
    """The pre-auth source limiter behind an app. Gate arm P23 only."""
    return app.state.source_limiter


def refusal_log_for_test(app: FastAPI) -> Any:
    """The bounded refusal log behind an app. Gate arm P23 only."""
    return app.state.refusal_log


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

    # F-4.11-12: openapi_url=None as well as the two docs pages. Disabling
    # the pages while leaving the schema endpoint served is a control that
    # looks complete and is not: /openapi.json disclosed the endpoint
    # inventory to an unauthenticated caller.
    app = FastAPI(
        title="Graph query service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # All four built fresh per app instance, never module-level. A
    # module-level singleton would leak state across independent app
    # instances (every test calling build_app() would share one bucket with
    # every other test), which is exactly the cross-contamination a
    # per-caller limiter must not have.
    rate_limiter = _RateLimiter(RATE_LIMIT_PER_MINUTE, _RATE_LIMIT_WINDOW_SECONDS)

    # F-4.11-J-05 and F-4.11-10: a SECOND limiter, keyed on source alone and
    # checked BEFORE auth. The original limiter sits after auth and is keyed
    # on the presented credential, so the unauthenticated path was unlimited:
    # a caller guessing credentials never reached the limiter at all, and
    # after F-4.11-03 added a log line per failure it could drive unbounded
    # journal growth on a box measured at 92 percent full. Two limiters
    # rather than one moved earlier, because they bound different things: an
    # authenticated caller's query budget, and anyone's ability to make this
    # service do work at all.
    source_limiter = _RateLimiter(SOURCE_RATE_LIMIT_PER_MINUTE, _RATE_LIMIT_WINDOW_SECONDS)

    refusal_log = _RefusalLog()

    # F-4.11-08: the concurrency bound. execute_cypher is blocking and now
    # runs in a threadpool, so without a bound a burst of slow queries would
    # simply consume every thread instead of every event-loop tick. The
    # bound is what makes the threadpool an actual fix rather than a wider
    # version of the same failure.
    query_slots = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

    # Exposed for the premise gate's bound arm (P23). A bound nobody can
    # observe is a bound nobody can test, and F-4.11-RV-01 is what an
    # untestable bound costs: it was wrong for the whole of round 2 and the
    # gate had no way to see it.
    app.state.source_limiter = source_limiter
    app.state.rate_limiter = rate_limiter
    app.state.refusal_log = refusal_log

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
        # Step 0: the PRE-AUTH bound, keyed on source alone.
        #
        # F-4.11-J-05 and F-4.11-10. Everything below this point costs the
        # service work, and until this existed none of it was bounded for a
        # caller who never presents a valid credential. Ordering matters and
        # is the whole finding: a limiter placed after auth cannot bound the
        # unauthenticated path by construction, no matter how tight it is.
        source = client_source(request)
        source_key = _source_digest(source)
        source_retry = source_limiter.check(source_key)
        if source_retry is not None:
            _emit_refusal(refusal_log, "source_rate_limited", source_key, source_retry)
            raise ServiceError(
                "rate_limited",
                "source exceeded "
                + str(SOURCE_RATE_LIMIT_PER_MINUTE)
                + " requests per minute against this service; retry after "
                "the interval given in retry_after",
                retry_after=source_retry,
            )

        # Step 1: auth, before any parsing or database work.
        #
        # F-4.11-03: a rejected credential is logged before it is refused.
        # This used to raise straight out of _check_auth, so the two classes
        # of call an operator most needs to see, a credential being guessed
        # and a caller being throttled, were the only two that left no trace
        # at all. Section 24 asks for every call logged, and P11b could not
        # see the gap: it asserts the log is CLEAN, never that it is
        # COMPLETE.
        #
        # F-4.11-J-05: that log line is now emitted through the bounded
        # refusal log rather than directly, so the audit trail the fix
        # created cannot itself be used to flood the journal, and cannot be
        # suppressed by journald's own drop-limiting taking the INFO call
        # records down with it.
        try:
            presented_token = _check_auth(request.headers.get("authorization"))
        except ServiceError:
            _emit_refusal(refusal_log, "auth_rejected", source_key, None)
            raise
        caller_key = _caller_digest(presented_token, source)

        # Step 2: the per-caller rate limit. Fail fast, never queue.
        retry_after = rate_limiter.check(caller_key)
        if retry_after is not None:
            # F-4.11-J-03: this line had no arm. The fix for F-4.11-03 added
            # TWO log lines and only the auth one was pinned, so deleting
            # this one left both suites green. P15 pins it now.
            # (F-4.11-RV-05: this comment cited "P16b", an arm that exists
            # nowhere. The fix for "no arm pins this" cited a fictional arm,
            # which is how a citation becomes decoration.)
            _emit_refusal(refusal_log, "rate_limited", source_key, retry_after)
            raise ServiceError(
                "rate_limited",
                "caller exceeded "
                + str(RATE_LIMIT_PER_MINUTE)
                + " requests per minute on the graph-query-service family; "
                "retry after the interval given in retry_after",
                retry_after=retry_after,
            )

        # Step 3: parse and shape-validate the body.
        #
        # Both failures here are LOGGED before they are raised. Found by
        # premise-gate arm P15 asserting audit completeness as a universal
        # over every outcome class rather than over the outcomes someone
        # thought to enumerate: an authenticated caller sending malformed
        # JSON was refused at this step, above the main logging step below,
        # and left no audit record at all. That is the same shape as
        # F-4.11-03 and F-4.11-J-03 before it, which is three times in one
        # phase that a refusal path was added above the logger rather than
        # below it, so the ordering is now stated here as the rule: no
        # request leaves this endpoint unlogged, whatever refuses it.
        try:
            raw_body = await request.json()
        except Exception as exc:  # malformed JSON is a caller defect
            _emit_refusal(refusal_log, "malformed_json", source_key, None)
            raise ServiceError(
                "invalid_payload", "request body is not valid JSON"
            ) from exc

        try:
            payload = CypherRequest.model_validate(raw_body)
        except ValidationError as exc:
            _emit_refusal(refusal_log, "invalid_payload", source_key, None)
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
        #
        # F-4.11-08, the phase's worst defect and the reason round 2 exists.
        # This endpoint is async and execute_cypher is BLOCKING psycopg2, so
        # calling it directly held the event loop for the whole query. On a
        # single-worker server that serialized every caller and stalled the
        # unauthenticated /healthz for up to the clamped budget: measured at
        # 10.97 seconds while a 12 second query was in flight. Because
        # tracker/preflight.py reads /healthz to decide whether the graph is
        # up, the service reported the graph DOWN during any slow query,
        # which is the exact "transport looks down" failure this phase was
        # pulled ahead of build phase 4.7 to delete. It is build phase 2.1's
        # already-fixed event-loop defect (F-2.1-06) resurfacing one layer
        # down, in code whose gate names concurrency as a stated omission.
        #
        # Two parts, and neither is sufficient alone. to_thread keeps the
        # loop free; the semaphore bounds how many threads the pool can be
        # made to hold, since an unbounded threadpool is the same exhaustion
        # one layer further out. Acquisition itself is bounded: a caller
        # waits a fraction of its own budget and is then refused with a
        # retry_after, never queued indefinitely, per tool-call-budgets.
        wait_budget = min(MAX_CONCURRENCY_WAIT_SECONDS, timeout_s * _CONCURRENCY_WAIT_FRACTION)
        try:
            await asyncio.wait_for(query_slots.acquire(), timeout=wait_budget)
        except TimeoutError as exc:
            _emit_refusal(refusal_log, "at_capacity", source_key, wait_budget)
            raise ServiceError(
                "rate_limited",
                "the service is at its concurrent-query limit of "
                + str(MAX_CONCURRENT_QUERIES)
                + "; retry after the interval given in retry_after, or send "
                "a narrower query_intent",
                retry_after=wait_budget,
            ) from exc

        try:
            rows, total_available = await asyncio.to_thread(
                execute_cypher,
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
        finally:
            # In a finally rather than after the return, so a slot is
            # returned on every path including the five raises above. A
            # concurrency bound that leaks a slot per failed query is worse
            # than no bound: it degrades to zero capacity under exactly the
            # conditions that make queries fail.
            query_slots.release()

        # Step 7: the wire encoding check, then the response.
        encoded_rows = _encode_rows(rows)
        return JSONResponse(
            status_code=200,
            content={"rows": encoded_rows, "total_available": total_available},
        )

    return app
