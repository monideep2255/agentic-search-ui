"""Shared HTTP transport for `ncbi_efetch` (Technical_specification.md Section 6.2).

This module owns exactly the plumbing every `ncbi_efetch` action shares:
request execution under a timeout with one backoff retry, a per-API-family
rate pool with a bounded fail-fast wait queue, API-key injection, and the
single most load-bearing fact in Section 6.2: E-utilities and Datasets
v2/PubChem use OPPOSITE conventions for signaling an error, and a shared
code path that tries to cover both gets one family right and the other
silently wrong (`docs/ncbi/Tool_implementation_mechanics.md:117-122`).

## The two classifiers, and why they cannot be one function with a flag

E-utilities returns HTTP 200 for a genuine empty result AND for several
distinct error classes. Measured live 2026-08-04:

    invalid db name    -> 200, esearchresult.ERROR = "Invalid db name
                          specified: notadatabase"
    nonexistent PMID   -> 200, empty <PubmedArticleSet></PubmedArticleSet>,
                          NO error node at all
    genuine zero hits  -> 200, count "0", empty idlist, NO ERROR key

The first and third differ by the presence of one JSON key, and only the
response BODY tells them apart; the HTTP status is 200 in all three cases.
Datasets v2 and PubChem are the exact opposite: proper HTTP status codes,
so those two actions must branch on status directly and must NOT be swayed
by whatever happens to be in the body.

So there are two classifiers, `classify_eutils_response` and
`classify_status_coded_response`, and they are given deliberately
DIFFERENT SIGNATURES rather than a shared one, so a misuse is a TypeError
at the call site rather than a silent logic bug:

    classify_eutils_response(content_type=..., text=...)
        Takes NO http_status parameter. It cannot branch on status even by
        accident, because status is never in scope.

    classify_status_coded_response(http_status=..., text=...)
        Takes NO content_type parameter. It always decides by status; body
        parsing only extracts a human-readable message, never the verdict.

Both classify by ALLOWLIST, not blocklist: a response body that matches
neither a known-good success shape nor a known error shape is `status:
"error"`, fail closed, rather than silently passing through as `ok`. This
is the direct lesson of LEARNINGS.md row 56 (a degenerate value shipped as
a citable fact four times, each through a shape the previous blocklist fix
had not enumerated, fixed only by inverting to an allowlist).

## Rate limiting

Per `.claude/rules/tool-call-budgets.md`, the E-utilities requests/second
ceiling is an unresolved conflict (3 vs 10 vs 100, depending on source) and
this module deliberately does NOT lock a specific constant into the
"correct" one. `DEFAULT_EUTILS_REQUESTS_PER_SECOND` is the conservative,
independently-verified floor (3/s), overridable via `NCBI_EUTILS_RPS`
without a code change once the real ceiling is confirmed. Datasets v2 and
PubChem get the rule's provisional ~5 req/s throttle for undocumented
interactive APIs, via `NCBI_DATASETS_RPS` / `NCBI_PUBCHEM_RPS`.

Each family's pool is a bounded FIFO wait queue (`RateLimiter`), not an
unbounded one. A call that would exceed the queue depth cap or its own
wait ceiling fails fast with `TransportRateLimitedError`, carrying
`retry_after` and the saturated family name, per the same rule.

## What this module deliberately does NOT do

It does not know the field names inside an ESearch, ESummary, ELink, or
EFetch payload, does not extract `source_url` citations, and does not
decide `ok` vs `empty` for a Datasets/PubChem 2xx body that logically
contains zero records; that record-count-to-status collapse belongs to the
per-action modules that call this one (`ncbi_eutils_actions`,
`ncbi_datasets_actions`, `ncbi_pubchem_actions`, T-3.1-03/04/05, not yet
written), the same way `cypher_query` decides "zero rows" is `empty` at
the tool layer rather than inside `graph_connection.execute_cypher`. This
module is deliberately dependency-free of those sibling files: it takes
and returns plain types (`str`, `int`, `dict`, `xml.etree.ElementTree`
elements), never an `ncbi_efetch`-specific schema.

## XML parsing and external entities

`.claude/rules/production-standards.md` requires `etree.XMLParser(
resolve_entities=False)` for NCBI EFetch XML, which is an `lxml` parameter.
`lxml` is not a dependency of this project (`pyproject.toml` lists none),
and neither is `defusedxml`. This module's own PostToolUse security hook
flags stdlib `xml.etree.ElementTree` for exactly this reason on write, and
that flag is correct as a general default: it does not know about the
mitigation below. This module does not add either package: this ticket
(T-3.1-02) is scoped to exactly two files, and a new dependency is a
`pyproject.toml` edit plus its own loud call-out and review
(`.claude/rules/supply-chain-security.md`), never a silent pull-in from one
parsing function. That tradeoff is a judgment call flagged in this
ticket's report for the product owner to confirm or override, not a
silent decision.

Instead this module uses the stdlib `xml.etree.ElementTree` (expat-backed)
plus an explicit pre-parse reject, and the reject is what carries the
actual security weight, not the choice of parser:

    External entity expansion (classic XXE): stdlib ElementTree does not
    resolve external entities or fetch external DTDs by default, so it is
    not subject to XXE the way an unconfigured `lxml.etree.XMLParser` is.

    Billion-laughs / internal entity expansion: stdlib ElementTree does
    NOT protect against this on its own, and this is the gap the security
    hook is really pointing at. It requires a DOCTYPE with internal
    ENTITY definitions to exist at all, so rejecting any body carrying a
    `<!DOCTYPE` or `<!ENTITY` declaration before `ElementTree.fromstring`
    ever sees it (`_XXE_MARKERS` below) closes both vectors at once, not
    only the external-entity one `resolve_entities=False` would have
    addressed. No legitimate EFetch response in Section 6.2's documented
    shapes carries either declaration, so this reject has no known false
    positive against real NCBI traffic.

Depends on:
    - httpx (pinned in pyproject.toml, >=0.27)

Reads:
    - Environment variables: NCBI_API_KEY (the E-utilities authenticated
      pool credential; value is never logged or placed in an exception
      string, only the fact of its presence), NCBI_EUTILS_RPS,
      NCBI_DATASETS_RPS, NCBI_PUBCHEM_RPS (rate overrides, optional)

Writes:
    - Nothing. Outbound HTTPS requests only; no local file or database
      writes.

Depended by:
    - system_03_search_agent.tools.ncbi_eutils_actions (T-3.1-03, not yet
      written)
    - system_03_search_agent.tools.ncbi_datasets_actions (T-3.1-04, not
      yet written)
    - system_03_search_agent.tools.ncbi_pubchem_actions (T-3.1-05, not yet
      written)
    - system_03_search_agent.tools.ncbi_efetch (T-3.1-06/07, not yet
      written)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.parse
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Budgets, per .claude/rules/tool-call-budgets.md and Section 6.2.
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_S: Final[float] = 15.0
DEFAULT_BACKOFF_S: Final[float] = 1.0

# See the module docstring's "Rate limiting" section: this is the
# conservative, independently-verified floor, not a resolution of the
# 3-vs-10-vs-100 conflict. Configurable via NCBI_EUTILS_RPS.
DEFAULT_EUTILS_REQUESTS_PER_SECOND: Final[float] = 3.0
# Datasets v2 and PubChem have no published numeric rate limit; both get
# the rule's provisional ~5 req/s throttle for undocumented interactive
# HTTPS APIs.
DEFAULT_DATASETS_REQUESTS_PER_SECOND: Final[float] = 5.0
DEFAULT_PUBCHEM_REQUESTS_PER_SECOND: Final[float] = 5.0

RateLimitFamily = Literal["eutils", "datasets", "pubchem"]
RATE_LIMIT_FAMILIES: Final[tuple[RateLimitFamily, ...]] = ("eutils", "datasets", "pubchem")

_ENV_NCBI_API_KEY: Final[str] = "NCBI_API_KEY"

_TRANSIENT_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

# httpx.TimeoutException is the base for all four; kept explicit for a
# clearer typed-error mapping (timeout vs connection failure) below.
_TRANSIENT_TIMEOUT_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)
_TRANSIENT_CONNECTION_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    httpx.ConnectError,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


class TransportError(Exception):
    """Base exception for every ncbi_transport failure."""


class TransportTimeoutError(TransportError):
    """The call exceeded its per-call timeout budget, after one retry."""


class TransportConnectionError(TransportError):
    """The connection failed (refused, reset, DNS) after one retry."""


class TransportRateLimitedError(TransportError):
    """The call could not be scheduled within its family's rate pool.

    Carries `family` and `retry_after` so the Act step can decide whether
    to wait and retry or move on, per the tool-call-budgets rule: a
    rate-limited error is an instruction to the next agent step, not just
    a failure signal.
    """

    def __init__(self, message: str, *, family: str, retry_after: float) -> None:
        super().__init__(message)
        self.family = family
        self.retry_after = retry_after


@dataclass(frozen=True)
class ClassificationResult:
    """The outcome of classifying one response body (or status).

    `body` is the parsed payload when classification got far enough to
    parse one: a `dict` for a JSON response, an `xml.etree.ElementTree`
    root `Element` for an XML response, or `None` when the body was
    unparseable or irrelevant to the verdict. Callers that need the parsed
    content (an action module extracting fields) read it from here instead
    of re-parsing the raw text a second time.
    """

    status: Literal["ok", "empty", "error"]
    error_message: str | None = None
    body: Any = None


# ---------------------------------------------------------------------------
# Classifier 1: E-utilities. Body only. Never looks at HTTP status.
# ---------------------------------------------------------------------------

# Known-good top-level JSON envelope keys. Only "esearchresult" is
# independently live-verified in this repo's capability sheet (premise
# gate cases 7 and 9). "result" (ESummary) and "linksets" (ELink) follow
# documented E-utilities convention but are NOT independently verified
# here; T-3.1-03 (ncbi_eutils_actions) should live-verify them before its
# summary and link actions ship, per the "Open verification gaps"
# convention in docs/ncbi/Tool_implementation_mechanics.md.
_EUTILS_JSON_ENVELOPES: Final[frozenset[str]] = frozenset({"esearchresult", "result", "linksets"})

# Known-good XML root tags. Only PubmedArticleSet (EFetch db=pubmed) is
# independently live-verified here (premise gate case 8). Extend this set
# only after live-verifying the corresponding db's EFetch root tag; an
# unrecognized root fails closed to "error" rather than being guessed at.
_EUTILS_XML_ALLOWED_ROOTS: Final[frozenset[str]] = frozenset({"PubmedArticleSet"})

# Defense in depth against XXE / entity-expansion payloads. See the module
# docstring's "XML parsing and external entities" section.
_XXE_MARKERS: Final[tuple[str, ...]] = ("<!doctype", "<!entity")


def classify_eutils_response(*, content_type: str, text: str) -> ClassificationResult:
    """Classify an E-utilities response body. Deliberately takes no status.

    E-utilities returns HTTP 200 for a genuine empty result and for
    several distinct error classes (Section 6.2, line 982;
    Tool_implementation_mechanics.md:82-87). There is no `http_status`
    parameter on this function on purpose: it cannot branch on status even
    by accident, because status is never in scope here. Every verdict
    comes from the body alone, decided by allowlist: a body matching
    neither a known-good success shape nor a recognized error shape is
    `status: "error"`, fail closed, never a silent `"ok"`.
    """
    sniffed_json = "json" in content_type or (
        not content_type and text.lstrip().startswith(("{", "["))
    )
    sniffed_xml = "xml" in content_type or (not content_type and text.lstrip().startswith("<"))

    if sniffed_json:
        return _classify_eutils_json(text)
    if sniffed_xml:
        return _classify_eutils_xml(text)
    return ClassificationResult(
        status="error",
        error_message=(
            "E-utilities response body is neither recognizable JSON nor XML "
            "(content-type " + repr(content_type) + "), refusing to guess its meaning"
        ),
    )


def _classify_eutils_json(text: str) -> ClassificationResult:
    try:
        body = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return ClassificationResult(
            status="error",
            error_message="E-utilities returned unparseable JSON, refusing to guess its meaning",
        )
    if not isinstance(body, dict):
        return ClassificationResult(
            status="error",
            error_message="E-utilities JSON body is not an object, refusing to guess its meaning",
            body=body,
        )

    matched_key = next((key for key in _EUTILS_JSON_ENVELOPES if key in body), None)
    if matched_key is None:
        return ClassificationResult(
            status="error",
            error_message=(
                "E-utilities JSON body matched no known-good envelope shape "
                "(expected one of " + ", ".join(sorted(_EUTILS_JSON_ENVELOPES)) + "), "
                "refusing to guess its meaning"
            ),
            body=body,
        )

    envelope = body[matched_key]
    if isinstance(envelope, dict) and "ERROR" in envelope:
        return ClassificationResult(status="error", error_message=str(envelope["ERROR"]), body=body)

    # The near-miss twin of the ERROR case above: a genuine zero-hit
    # ESearch carries no ERROR key at all, only count "0" and an empty
    # idlist. This is the one shape this module knows how to collapse to
    # "empty" itself; ESummary/ELink's empty shapes are unverified (see
    # the envelope allowlist comment above) and default to "ok" here,
    # left for the calling action module to re-check against its own
    # verified field set.
    if (
        matched_key == "esearchresult"
        and isinstance(envelope, dict)
        and str(envelope.get("count")) == "0"
    ):
        return ClassificationResult(status="empty", body=body)

    return ClassificationResult(status="ok", body=body)


def _classify_eutils_xml(text: str) -> ClassificationResult:
    lowered = text.lower()
    if any(marker in lowered for marker in _XXE_MARKERS):
        return ClassificationResult(
            status="error",
            error_message=(
                "E-utilities XML body carries a DOCTYPE or ENTITY declaration, "
                "refusing to parse it"
            ),
        )
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return ClassificationResult(
            status="error",
            error_message="E-utilities returned unparseable XML, refusing to guess its meaning",
        )

    if root.tag not in _EUTILS_XML_ALLOWED_ROOTS:
        return ClassificationResult(
            status="error",
            error_message=(
                "E-utilities XML root <" + str(root.tag) + "> is not a recognized shape "
                "(expected one of " + ", ".join(sorted(_EUTILS_XML_ALLOWED_ROOTS)) + "), "
                "refusing to guess its meaning"
            ),
            body=root,
        )

    if len(root) == 0:
        return ClassificationResult(status="empty", body=root)
    return ClassificationResult(status="ok", body=root)


# ---------------------------------------------------------------------------
# Classifier 2: Datasets v2 / PubChem. HTTP status only, the opposite
# convention. Never lets body content override a verdict already made from
# status.
# ---------------------------------------------------------------------------


def classify_status_coded_response(*, http_status: int, text: str) -> ClassificationResult:
    """Classify a Datasets v2 or PubChem response. Deliberately takes no content_type.

    Both APIs return proper HTTP status codes, the opposite convention
    from E-utilities, so this function always decides `ok` vs `error` from
    `http_status` alone. There is no `content_type` parameter on this
    function on purpose, matching `classify_eutils_response`'s inverse
    omission: body parsing here only ever extracts a human-readable error
    message for the `error` case, it never supplies the verdict.

    This function does not distinguish `ok` from `empty`: a 2xx body that
    logically contains zero records (an empty gene report list, for
    example) is still `"ok"` here. Collapsing a zero-record `ok` into the
    tool's `"empty"` output status is the calling action module's job, the
    same way `cypher_query` treats zero graph rows as `"empty"` at the
    tool layer rather than inside `graph_connection.execute_cypher`.
    """
    body = _try_parse_json(text)
    if 200 <= http_status < 300:
        return ClassificationResult(status="ok", body=body)
    return ClassificationResult(
        status="error",
        error_message=_extract_status_coded_error_message(body, http_status),
        body=body,
    )


def _try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_status_coded_error_message(body: Any, http_status: int) -> str:
    if isinstance(body, dict):
        # Datasets v2: {"error", "code", "message"}.
        if "message" in body:
            return str(body["message"])
        # PubChem: {"Fault": {"Code", "Message"}}.
        fault = body.get("Fault")
        if isinstance(fault, dict) and "Message" in fault:
            return str(fault["Message"])
    return "HTTP " + str(http_status) + " with no structured error body"


# ---------------------------------------------------------------------------
# Rate limiting: a bounded FIFO wait queue per family, fail-fast beyond it.
# ---------------------------------------------------------------------------


class RateLimiter:
    """Uniform-pacing limiter with a bounded, fail-fast wait queue.

    Not a bursting token bucket; each call is scheduled at least
    `1 / requests_per_second` after the previous one, which is the
    conservative, simple choice appropriate for a provisional throttle
    whose real ceiling is unresolved (see the module docstring's "Rate
    limiting" section). Per `.claude/rules/tool-call-budgets.md`, the wait
    queue is capped at `queue_depth` and a queued call's wait ceiling is
    supplied by the caller per call, not fixed once for every query class:
    a call that would exceed either cap raises `TransportRateLimitedError`
    rather than joining an unbounded wait.
    """

    def __init__(self, *, requests_per_second: float, queue_depth: int, family: str) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if queue_depth <= 0:
            raise ValueError("queue_depth must be positive")
        self._interval = 1.0 / requests_per_second
        self._queue_depth = queue_depth
        self._family = family
        self._lock = asyncio.Lock()
        self._next_available = 0.0
        self._waiting = 0

    @property
    def requests_per_second(self) -> float:
        """The effective pacing rate, for observability and tests."""
        return 1.0 / self._interval

    async def acquire(
        self,
        wait_ceiling_s: float,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Block until this call's turn, or raise TransportRateLimitedError.

        `wait_ceiling_s` is supplied by the caller per call so a
        short-budget lookup and a long-budget deep-research query get
        different fail-fast thresholds against the same shared pool,
        rather than one constant serving every query class.
        """
        async with self._lock:
            if self._waiting >= self._queue_depth:
                raise TransportRateLimitedError(
                    self._family + " rate pool queue is full (" + str(self._queue_depth)
                    + " already waiting), retry after the queue drains",
                    family=self._family,
                    retry_after=round(self._interval, 3),
                )
            now = time_fn()
            scheduled = max(now, self._next_available)
            wait = scheduled - now
            if wait > wait_ceiling_s:
                raise TransportRateLimitedError(
                    self._family + " rate pool wait (" + str(round(wait, 1))
                    + "s) exceeds this call's " + str(round(wait_ceiling_s, 1))
                    + "s budget, retry later or with a smaller query class",
                    family=self._family,
                    retry_after=round(wait, 3),
                )
            self._next_available = scheduled + self._interval
            self._waiting += 1
        try:
            if wait > 0:
                await sleep_fn(wait)
        finally:
            async with self._lock:
                self._waiting -= 1


@dataclass(frozen=True)
class _FamilyConfig:
    default_requests_per_second: float
    queue_depth: int
    env_var: str


_FAMILY_CONFIGS: Final[dict[str, _FamilyConfig]] = {
    "eutils": _FamilyConfig(DEFAULT_EUTILS_REQUESTS_PER_SECOND, 15, "NCBI_EUTILS_RPS"),
    "datasets": _FamilyConfig(DEFAULT_DATASETS_REQUESTS_PER_SECOND, 25, "NCBI_DATASETS_RPS"),
    "pubchem": _FamilyConfig(DEFAULT_PUBCHEM_REQUESTS_PER_SECOND, 25, "NCBI_PUBCHEM_RPS"),
}

_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(family: RateLimitFamily) -> RateLimiter:
    """Return the process-wide RateLimiter for `family`, creating it lazily.

    Lazily created (not at import time) so an env-var override is read
    only when a family is first used, and shared thereafter so pacing is
    actually enforced across calls rather than reset per call.
    """
    if family not in _rate_limiters:
        config = _FAMILY_CONFIGS.get(family)
        if config is None:
            raise ValueError(
                "unknown rate-limit family " + repr(family) + ", expected one of "
                + ", ".join(RATE_LIMIT_FAMILIES)
            )
        rps = float(os.environ.get(config.env_var, config.default_requests_per_second))
        _rate_limiters[family] = RateLimiter(
            requests_per_second=rps, queue_depth=config.queue_depth, family=family
        )
    return _rate_limiters[family]


def reset_rate_limiters_for_tests() -> None:
    """Clear cached RateLimiter instances. Test-only; production never calls this."""
    _rate_limiters.clear()


# ---------------------------------------------------------------------------
# Request execution: timeout, one backoff retry, URL encoding, api_key.
# ---------------------------------------------------------------------------

_default_client: httpx.AsyncClient | None = None


def _get_default_client() -> httpx.AsyncClient:
    global _default_client
    if _default_client is None:
        _default_client = httpx.AsyncClient()
    return _default_client


def _build_query_string(params: Mapping[str, Any]) -> str:
    """URL-encode every parameter per production-standards.md's query-safety gate.

    `urllib.parse.quote(value, safe=":/=?&|+")`, never an f-string or raw
    concatenation of an unencoded value into the URL.
    """
    pairs: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        encoded_key = urllib.parse.quote(str(key), safe="")
        encoded_value = urllib.parse.quote(str(value), safe=":/=?&|+")
        pairs.append(encoded_key + "=" + encoded_value)
    return "&".join(pairs)


def _append_api_key(query_string: str) -> str:
    """Append `&api_key=` from NCBI_API_KEY. Never logs or returns the value itself.

    Only the fact of the key's presence is ever logged, per
    production-standards.md: "log the key name as a string literal, never
    the value."
    """
    api_key = os.environ.get(_ENV_NCBI_API_KEY)
    if not api_key:
        logger.debug("NCBI_API_KEY not set, using the unauthenticated E-utilities pool")
        return query_string
    logger.debug("NCBI_API_KEY present, using the authenticated E-utilities pool")
    encoded_key = urllib.parse.quote(api_key, safe="")
    if query_string:
        return query_string + "&api_key=" + encoded_key
    return "api_key=" + encoded_key


def _host_of(url: str) -> str:
    """Extract only the hostname for diagnostics. Never the full URL.

    Once an api_key is appended, `url` carries the secret as a query
    parameter. Every diagnostic or error message in this module uses this
    helper instead of the raw `url`, so a credential can never reach a log
    line or an exception string through this path.
    """
    return urllib.parse.urlparse(url).hostname or "unknown-host"


async def execute_get(
    base_url: str,
    params: Mapping[str, Any],
    *,
    family: RateLimitFamily,
    include_api_key: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    backoff_s: float = DEFAULT_BACKOFF_S,
    wait_ceiling_s: float | None = None,
    client: httpx.AsyncClient | None = None,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    time_fn: Callable[[], float] = time.monotonic,
) -> httpx.Response:
    """Execute one GET against an NCBI-family host: rate-limited, timed out, retried once.

    Rate limiting happens before the request is attempted at all, per
    `family`'s pool (`get_rate_limiter`); a saturated pool raises
    `TransportRateLimitedError` without ever reaching the network.

    Retry: exactly one retry, and only for a TRANSIENT failure. Transient
    means a connection or timeout exception, or an HTTP 429/5xx response.
    A 400 (or any other non-transient 4xx) is never retried, and neither
    is any HTTP 200 response regardless of its body: this function never
    inspects the body, so a 200-with-ERROR-body response (the E-utilities
    near-miss case) is returned immediately on the first attempt, exactly
    like a genuine 200 success. Retrying either would just re-fetch the
    same wrong answer, per Section 6.2's transient/non-transient framing.

    Never inspects or embeds `NCBI_API_KEY`'s value in a log line or
    exception string; every diagnostic message here uses `_host_of(url)`.

    Raises:
        TransportRateLimitedError: the call's family pool could not
            schedule it within its queue depth or wait ceiling.
        TransportTimeoutError: the call timed out on both attempts.
        TransportConnectionError: the connection failed on both attempts.
    """
    query_string = _build_query_string(params)
    if include_api_key:
        query_string = _append_api_key(query_string)
    if query_string:
        url = base_url + ("&" if "?" in base_url else "?") + query_string
    else:
        url = base_url

    limiter = get_rate_limiter(family)
    effective_ceiling = wait_ceiling_s if wait_ceiling_s is not None else timeout_s
    await limiter.acquire(effective_ceiling, time_fn=time_fn, sleep_fn=sleep_fn)

    active_client = client or _get_default_client()
    host = _host_of(url)
    last_exc: Exception | None = None

    for attempt_index in range(2):
        try:
            response = await active_client.get(url, timeout=timeout_s)
        except _TRANSIENT_TIMEOUT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt_index == 0:
                logger.warning(
                    "%s call to %s timed out (%s), retrying once after %.1fs backoff",
                    family, host, type(exc).__name__, backoff_s,
                )
                await sleep_fn(backoff_s)
                continue
            raise TransportTimeoutError(
                host + " timed out after " + str(timeout_s) + "s (one retry already "
                "attempted), retry with fewer ids or a narrower request, or wait for the pool"
            ) from None
        except _TRANSIENT_CONNECTION_EXCEPTIONS as exc:
            last_exc = exc
            if attempt_index == 0:
                logger.warning(
                    "%s call to %s failed (%s), retrying once after %.1fs backoff",
                    family, host, type(exc).__name__, backoff_s,
                )
                await sleep_fn(backoff_s)
                continue
            raise TransportConnectionError(
                host + " connection failed after one retry (" + type(exc).__name__
                + "), verify network reach and retry"
            ) from None
        else:
            if response.status_code in _TRANSIENT_STATUS_CODES and attempt_index == 0:
                logger.warning(
                    "%s call to %s returned HTTP %d, retrying once after %.1fs backoff",
                    family, host, response.status_code, backoff_s,
                )
                await sleep_fn(backoff_s)
                continue
            return response

    # Unreachable in practice: the loop above always either returns or
    # raises on its second iteration. Kept as a typed fail-closed exit
    # rather than letting a silent None propagate if that ever changes.
    raise TransportConnectionError(host + " request failed with no response") from last_exc
