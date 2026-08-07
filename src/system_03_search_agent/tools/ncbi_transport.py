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

The wait ceiling is a budget for the WHOLE `execute_get` call, not for
each attempt inside it (F-3.1-37). `execute_get` acquires the pool once
per attempt, so a naive per-attempt ceiling would let one call wait up to
twice its declared budget across the first attempt and its retry.
`_execute_with_retry` therefore converts the ceiling into a single
deadline at call start and hands each acquisition only what is left of
it, so the total scheduling wait for one call never exceeds the ceiling
the caller declared, however many attempts it took.

There are two independent sources of a `retry_after` value, and both are
surfaced (F-3.1-19):

    Client-side: this module's own limiter refused to schedule the call.
    `TransportRateLimitedError.retry_after` carries the estimate.

    Server-side: NCBI itself answered 429 or 503 and may state a
    `Retry-After` response header. `parse_retry_after` and
    `retry_after_for_response` read it (numeric seconds, or the rarer
    HTTP-date form), `classify_status_coded_response` puts it on
    `ClassificationResult.retry_after` for the status-coded families,
    and `_execute_with_retry` prefers it over the fixed backoff when
    deciding how long to wait before its one retry.

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
    hook is really pointing at. It requires an ENTITY declaration to
    exist at all (general or parameter), which can only appear inside a
    DOCTYPE's internal subset or an external DTD subset, so rejecting any
    `<!ENTITY` occurrence and any DOCTYPE internal subset before
    `ElementTree.fromstring` ever sees the body closes both vectors, not
    only the external-entity one `resolve_entities=False` would have
    addressed.

    CORRECTION, filed against this module's own premise gate
    (T-3.1-11/12, live-caught 2026-08-05): an earlier version of this
    reject blocked every `<!DOCTYPE`, full stop, and its comment here
    claimed "no known false positive against real NCBI traffic". That
    claim was live-disproven on the first real PubMed EFetch response
    fetched: EVERY genuine PubMed record begins with a DOCTYPE line
    naming the public NLM DTD, so the blanket reject made this tool
    unable to parse a single real PubMed record. This is build phase
    3.0's lesson recurring at the XML-parsing layer instead of the
    guardrail layer: a security check with no safe direction of failure.
    Over-blocking is invisible to every attack-only test (rejecting
    everything scores 100% against XXE payloads) and it destroys the
    product; under-blocking is a real XXE/billion-laughs hole. Both
    directions must be satisfied, so the reject now distinguishes a bare
    DOCTYPE (a declaration with no internal subset, i.e. no `[...]`
    block) from one that declares entities:

        A DOCTYPE with NO internal subset (regardless of an external
        SYSTEM/PUBLIC identifier) is PERMITTED. This is exactly the real
        PubMed shape above. ElementTree never fetches the referenced
        external DTD, so naming one is inert.

        A DOCTYPE that declares an internal subset (`<!DOCTYPE x [ ... ]>`)
        is REJECTED outright, regardless of what the subset contains,
        because that is the only place an internal ENTITY (or a
        parameter entity, which also starts `<!ENTITY %`) can live.

        `<!ENTITY` anywhere in the body, inside or outside a detected
        DOCTYPE span, is REJECTED. This is a second, independent check
        so an entity declaration cannot survive by appearing somewhere
        the DOCTYPE scan does not look.

    The DOCTYPE scan itself (`_doctype_declares_internal_subset` below)
    is quote-aware: it walks the declaration from `<!DOCTYPE` looking for
    the first unquoted `[` or unquoted `>`, so a PUBLIC/SYSTEM literal
    containing a stray bracket character cannot be mistaken for the start
    of an internal subset, and an attacker cannot hide a subset opener
    inside a quoted identifier either, since quotes are tracked, not
    trusted. An unterminated/truncated DOCTYPE fails closed (treated as
    carrying a subset) rather than being assumed safe.

    Residual, narrow, deliberately accepted gap: a literal `<!ENTITY`
    substring inside a CDATA section (`<![CDATA[<!ENTITY x "y">]]>`) is a
    valid, non-executing way to include that text in a PubMed field, and
    this reject has no way to distinguish it from a real declaration
    short of a real XML parser. No such CDATA content has been observed
    in the documented Section 6.2 shapes; this reject would false-positive
    on it if one ever appeared. That is a known, named trade, not a
    silent one.

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
import email.utils
import json
import logging
import math
import os
import time
import urllib.parse
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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

# The two statuses for which HTTP defines a `Retry-After` response header.
_RETRY_AFTER_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 503})

_RETRY_AFTER_HEADER: Final[str] = "retry-after"

# A server-stated `Retry-After` is surfaced to the caller in full, however
# large it is, because that is the honest estimate the next agent step
# needs. What this module will itself SLEEP on before its one retry is
# capped here: a call carries a 15s per-call timeout budget
# (`.claude/rules/tool-call-budgets.md`), so honoring an unbounded, or
# hostile, header value inside the call would blow that budget rather than
# fail fast. Beyond the cap the retry uses the cap and the caller is left
# to decide from the surfaced value whether to come back later.
_MAX_BACKOFF_FROM_RETRY_AFTER_S: Final[float] = 5.0

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

    `retry_after` is the server-stated wait in seconds, populated only when
    the response was a 429 or 503 that carried a parseable `Retry-After`
    header (F-3.1-19). It is `None` on every other outcome, including a
    429 or 503 with no such header: `None` means "the server did not say",
    never "retry immediately". Its client-side twin is
    `TransportRateLimitedError.retry_after`, which this module produces on
    its own when a call cannot be scheduled at all.
    """

    status: Literal["ok", "empty", "error"]
    error_message: str | None = None
    body: Any = None
    retry_after: float | None = None


# ---------------------------------------------------------------------------
# Server-stated Retry-After. The other half of `retry_after` (F-3.1-19).
# ---------------------------------------------------------------------------


def parse_retry_after(
    headers: Mapping[str, str], *, default: float | None = None
) -> float | None:
    """Read a `Retry-After` response header into a wait in seconds.

    F-3.1-19 (adversary finding 7, reopened): before this, the only
    `retry_after` this module could ever produce came from its OWN
    client-side throttle. A real NCBI 429 or 503, the case where the
    server is the authority on how long to wait, produced no numeric
    estimate anywhere, so a `rate_limited` error reaching the Act step
    carried no actionable number, which
    `.claude/rules/tool-call-budgets.md` requires.

    Two header forms are accepted, per RFC 9110 section 10.2.3:

        delay-seconds: the common form NCBI sends, a bare integer such as
            `Retry-After: 30`. Parsed as a float so a fractional value
            (non-standard, but harmless) is not silently dropped.

        HTTP-date: the rarer absolute form, parsed with the stdlib's
            `email.utils.parsedate_to_datetime` and converted to a delay
            relative to now. A date already in the past clamps to 0.0
            rather than going negative.

    Returns `default` (itself `None` unless the caller supplies one) when
    the header is absent, empty, or unparseable. Never raises: an
    unreadable header from an upstream this module does not control is a
    missing hint, not a failure of the call it belongs to.
    """
    raw: str | None = None
    for key, value in headers.items():
        if key.lower() == _RETRY_AFTER_HEADER:
            raw = value
            break
    if raw is None:
        return default

    candidate = raw.strip()
    if not candidate:
        return default

    try:
        seconds = float(candidate)
    except (TypeError, ValueError):
        seconds = None
    if seconds is not None:
        # Reject nan/inf, which float() happily accepts from "nan"/"inf"
        # and which would poison every downstream min()/max() comparison.
        if not math.isfinite(seconds):
            return default
        return max(0.0, seconds)

    try:
        when = email.utils.parsedate_to_datetime(candidate)
    except (TypeError, ValueError):
        return default
    if when is None:
        return default
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def retry_after_for_response(
    response: httpx.Response, *, default: float = DEFAULT_BACKOFF_S
) -> float:
    """The caller-facing form of `parse_retry_after`: always returns a number.

    This is the interface an action module uses on the E-utilities path,
    where `classify_eutils_response` deliberately never sees an HTTP
    status and so can never populate `ClassificationResult.retry_after`
    itself. A caller that has already decided a response is a 429 or a 503
    calls this to turn it into an actionable wait:

        if response.status_code == 429:
            wait = ncbi_transport.retry_after_for_response(response)

    `default` is this module's own backoff budget, the same value the
    retry itself would have used, so an absent or unparseable header
    yields a sane number rather than `None` for a caller that must state
    one.
    """
    parsed = parse_retry_after(response.headers)
    return default if parsed is None else parsed


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
# docstring's "XML parsing and external entities" section, including the
# CORRECTION subsection: a bare DOCTYPE (no internal subset) is NOT itself
# the attack and must be permitted, since real PubMed EFetch responses
# always carry one. `<!ENTITY` (general or parameter) is what must never
# reach the parser, wherever it appears.
_DOCTYPE_MARKER: Final[str] = "<!doctype"
_ENTITY_MARKER: Final[str] = "<!entity"


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

    # F-3.1-16 (adversary finding 4, CRITICAL): ELink errors carry ERROR
    # at the TOP level of the body, not inside the envelope. The real
    # shape is {"linksets":[],"ERROR":"Invalid db name specified: ..."},
    # where linksets is a LIST (not a dict) and ERROR is a sibling of the
    # envelope key. The per-envelope ERROR check below only fires when the
    # envelope itself is a dict, so a list-envelope ERROR was silently
    # skipped and classified as ok. Check the body-level ERROR FIRST,
    # before the envelope type check, so it fires regardless of what the
    # envelope type is.
    if isinstance(body, dict) and "ERROR" in body:
        return ClassificationResult(status="error", error_message=str(body["ERROR"]), body=body)

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


def _doctype_declares_internal_subset(text: str, doctype_index: int) -> bool:
    """Quote-aware scan from a `<!DOCTYPE` occurrence to its closing `>`.

    Returns True the moment an UNQUOTED `[` appears before an unquoted `>`,
    meaning the declaration opens an internal subset (the only place an
    internal `<!ENTITY>` can live). A DOCTYPE naming only an external
    SYSTEM/PUBLIC identifier, the real PubMed shape, has no `[` at all and
    returns False. Quote-tracking stops a PUBLIC/SYSTEM literal from being
    mistaken for subset syntax, and stops a `[` hidden inside a quoted
    string from being ignored. An unterminated declaration (the text ends
    before an unquoted `>`) fails closed: treated as carrying a subset
    rather than assumed safe.
    """
    quote: str | None = None
    i = doctype_index
    n = len(text)
    while i < n:
        ch = text[i]
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "[":
            return True
        elif ch == ">":
            return False
        i += 1
    return True


def _classify_eutils_xml(text: str) -> ClassificationResult:
    lowered = text.lower()

    # Independent of the DOCTYPE scan below: an ENTITY declaration is
    # rejected wherever it appears in the body, not only inside a detected
    # DOCTYPE span, so it cannot survive by appearing somewhere the scan
    # does not look (billion-laughs and classic XXE both require one).
    if _ENTITY_MARKER in lowered:
        return ClassificationResult(
            status="error",
            error_message=(
                "E-utilities XML body carries an ENTITY declaration, refusing to parse it"
            ),
        )

    doctype_index = lowered.find(_DOCTYPE_MARKER)
    if doctype_index != -1 and _doctype_declares_internal_subset(text, doctype_index):
        return ClassificationResult(
            status="error",
            error_message=(
                "E-utilities XML body's DOCTYPE declares an internal subset, "
                "refusing to parse it"
            ),
        )
    # A DOCTYPE with no internal subset (e.g. real PubMed's public NLM DTD
    # reference) reaches ElementTree.fromstring below unmodified. See the
    # module docstring's CORRECTION subsection: rejecting every DOCTYPE
    # outright made this tool unable to parse a single real PubMed record.

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


def classify_status_coded_response(
    *, http_status: int, text: str, headers: Mapping[str, str] | None = None
) -> ClassificationResult:
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

    `headers` is optional and never supplies the verdict either: its only
    job is to carry a server-stated `Retry-After` onto the result for a
    429 or 503, so a rate-limited or overloaded upstream reaches the Act
    step with an actionable number attached (F-3.1-19). Omitting it
    leaves `retry_after` as `None`, exactly as before.
    """
    body = _try_parse_json(text)
    if 200 <= http_status < 300:
        return ClassificationResult(status="ok", body=body)
    retry_after: float | None = None
    if headers is not None and http_status in _RETRY_AFTER_STATUS_CODES:
        retry_after = parse_retry_after(headers)
    return ClassificationResult(
        status="error",
        error_message=_extract_status_coded_error_message(body, http_status),
        body=body,
        retry_after=retry_after,
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

# Client lifetime, not a singleton. A module-level `httpx.AsyncClient`
# singleton was tried first and failed live (T-3.1-11, premise gate cases
# 2, 5, 18, 2026-08-05): `httpx.AsyncClient` builds event-loop-bound
# primitives (an httpcore connection pool backed by anyio/asyncio locks)
# on first use, and reusing that same client from a DIFFERENT running
# event loop than the one it was built on raises `RuntimeError: Event
# loop is closed`, intermittently, because it depends on which loop
# happened to be running the first time any call was made. This is
# exactly the shape every pytest-asyncio test hits by default (a fresh
# event loop per test function), and it is also a real production risk
# anywhere a process legitimately runs more than one event loop over its
# lifetime.
#
# Tradeoff chosen: correctness over connection-pool reuse. When no caller
# supplies a `client` (true for every call the Act step actually makes;
# only this module's own tests inject one), `execute_get` opens a fresh
# `httpx.AsyncClient` scoped to that single call with `async with`, and
# it is closed before the call returns. This gives up cross-call
# keep-alive reuse within one query, a real and accepted cost, a fresh
# TCP+TLS handshake per Layer 2 call instead of a shared connection, in
# exchange for a client that structurally cannot outlive or cross the
# event loop it was created on: there is no longer a module-level
# reference for a second loop to inherit. Each family's rate limiter
# already paces calls to roughly one per second or slower
# (`tool-call-budgets.md`), so the relative cost of a fresh handshake
# against that pacing interval is small. A caller that wants pooling
# across several calls within a single event loop (a future action
# module issuing more than one request in a tight loop) passes its own
# long-lived `client` explicitly; this module does not manage that
# lifetime on its behalf, only its own default path.


def _build_query_string(params: Mapping[str, Any]) -> str:
    """URL-encode every parameter per production-standards.md's query-safety gate.

    F-3.1-18 (adversary finding 6, a security finding): the previous `safe`
    pattern left `&` and `=` unencoded, so any caller-supplied value could
    inject arbitrary parameters into the URL. Live-confirmed: a term
    containing `&retstart=500` changed the returned record set, and ids
    containing `&linkname=gene_pubmed_rif` silently swapped the link set.
    Every query-string value is now fully encoded (`safe=""`), matching the
    discipline the Datasets and PubChem path-segment builders already use.
    """
    pairs: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        encoded_key = urllib.parse.quote(str(key), safe="")
        encoded_value = urllib.parse.quote(str(value), safe="")
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

    Rate limiting happens before EVERY attempt, per `family`'s pool
    (`get_rate_limiter`), so a retry can never escape the throttle its
    first attempt was subject to (F-3.1-22). On the first attempt a
    saturated pool therefore raises `TransportRateLimitedError` without
    ever reaching the network; on the retry it raises after the first
    request has already gone out and failed transiently, so this error
    does not by itself imply zero network contact. When it fires on a
    retry, the failure that triggered that retry is attached as the
    exception's `__cause__` and named in the accompanying log line, so
    the original timeout or connection error is not lost.

    Wait budget: `wait_ceiling_s` (defaulting to `timeout_s`) bounds the
    total time this call may spend WAITING for its pool, across both
    attempts together, not per attempt (F-3.1-37). It is converted to a
    single deadline at call start, and each acquisition gets only what is
    left of it, so two attempts can never wait twice the declared
    ceiling.

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

    Client lifetime: when the caller does not supply `client` (the normal
    production path), this function opens a fresh `httpx.AsyncClient`
    scoped to this one call and closes it before returning, rather than
    reusing a module-level singleton across calls. See the "Client
    lifetime, not a singleton" comment above `_build_query_string` for
    why: a shared client can outlive, and be reused from a different
    event loop than, the one it was created on. A caller-supplied
    `client` (tests, or a future caller that wants pooling) is used as
    given and its lifetime stays the caller's responsibility.

    Raises:
        TransportRateLimitedError: the call's family pool could not
            schedule it, or its retry, within its queue depth or its
            remaining share of the whole call's wait ceiling.
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

    if client is not None:
        return await _execute_with_retry(
            client, url, family=family, timeout_s=timeout_s, backoff_s=backoff_s,
            sleep_fn=sleep_fn, limiter=limiter, wait_budget_s=effective_ceiling,
            time_fn=time_fn,
        )

    # No caller-supplied client: build one scoped to exactly this call,
    # bound to whichever event loop is running THIS await, and close it
    # before returning. Never stored at module level, so no later call
    # from a different loop can ever inherit it.
    async with httpx.AsyncClient() as fresh_client:
        return await _execute_with_retry(
            fresh_client, url, family=family, timeout_s=timeout_s, backoff_s=backoff_s,
            sleep_fn=sleep_fn, limiter=limiter, wait_budget_s=effective_ceiling,
            time_fn=time_fn,
        )


async def _execute_with_retry(
    active_client: httpx.AsyncClient,
    url: str,
    *,
    family: RateLimitFamily,
    timeout_s: float,
    backoff_s: float,
    sleep_fn: Callable[[float], Awaitable[None]],
    limiter: RateLimiter,
    wait_budget_s: float,
    time_fn: Callable[[], float],
) -> httpx.Response:
    """The timeout/retry loop itself, factored out of `execute_get`.

    Takes an already-resolved client so `execute_get` can decide, once,
    whether that client is caller-supplied or freshly opened for this
    call, without duplicating the retry logic across both branches.

    F-3.1-22 (adversary finding 10, MAJOR): the rate limiter is
    acquired BEFORE each attempt, not once before the first attempt.
    Before that fix, a retry issued a second HTTP request without a
    second rate-limiter acquisition, so the retry escaped the throttle
    pool entirely. The moment NCBI sent a 429, the code would issue a
    second unpaced request into the pool it was being throttled out of.

    F-3.1-37 (a regression introduced BY that fix, MAJOR): moving the
    acquisition inside the loop gave each attempt its own full copy of
    `wait_budget_s`, so one call could wait up to twice the ceiling it
    declared. `.claude/rules/tool-call-budgets.md` ties the wait ceiling
    to the calling query's remaining latency budget, and a budget that
    silently doubles under retry is not a budget. The ceiling is
    therefore converted here into ONE deadline for the whole call, and
    each acquisition is handed only `deadline - now`. A first attempt
    that waits 1.0s against a 1.5s ceiling leaves the retry 0.5s, and a
    retry that cannot be scheduled inside what remains fails fast rather
    than waiting a second full ceiling.
    """
    host = _host_of(url)
    last_exc: Exception | None = None
    deadline = time_fn() + wait_budget_s

    for attempt_index in range(2):
        remaining_wait_budget = max(0.0, deadline - time_fn())
        try:
            await limiter.acquire(remaining_wait_budget, time_fn=time_fn, sleep_fn=sleep_fn)
        except TransportRateLimitedError as rate_exc:
            if last_exc is None:
                raise
            # A retry that cannot be scheduled inside the call's remaining
            # budget. Name the failure that caused the retry, and chain it,
            # so "it timed out and then could not be retried in budget" is
            # still recoverable from the raised error rather than replaced
            # by it.
            logger.warning(
                "%s retry to %s could not be scheduled within the call's remaining "
                "%.1fs wait budget after a %s on the first attempt",
                family, host, remaining_wait_budget, type(last_exc).__name__,
            )
            raise rate_exc from last_exc
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
                # F-3.1-19: when the server states a Retry-After, it is the
                # authority on how long to wait, not this module's fixed
                # backoff constant. Honor it, floored at the fixed backoff
                # (never retry sooner than we would have anyway) and capped
                # at _MAX_BACKOFF_FROM_RETRY_AFTER_S so a huge or hostile
                # header value cannot park the call past its timeout budget.
                # The FULL parsed value stays reachable by the caller via
                # `retry_after_for_response(response)`; only what this module
                # itself sleeps on is capped.
                effective_backoff = backoff_s
                stated_retry_after = parse_retry_after(response.headers)
                if stated_retry_after is not None:
                    effective_backoff = min(
                        max(stated_retry_after, backoff_s), _MAX_BACKOFF_FROM_RETRY_AFTER_S
                    )
                logger.warning(
                    "%s call to %s returned HTTP %d, retrying once after %.1fs backoff",
                    family, host, response.status_code, effective_backoff,
                )
                await sleep_fn(effective_backoff)
                continue
            return response

    # Unreachable in practice: the loop above always either returns or
    # raises on its second iteration. Kept as a typed fail-closed exit
    # rather than letting a silent None propagate if that ever changes.
    raise TransportConnectionError(host + " request failed with no response") from last_exc
