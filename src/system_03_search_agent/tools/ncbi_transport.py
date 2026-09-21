"""Shared HTTP transport for `ncbi_efetch` and `ncbi_dbsnp` (Technical_specification.md Section 6.2, 6.3).

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
ceiling was an unresolved conflict (3 vs 10 vs 100, depending on source)
and this module shipped with the conservative, independently-verified
floor (3/s) as its default. Settled 2026-09-14, UI fix set 11 (search
breadth): the ceiling was read off NCBI's own rate-limit response header
with the project's `NCBI_API_KEY` present and measured at 10 requests per
second, and the product owner confirmed locking that figure, which is the
rule's own "10 requests/second with an API key" row.
`DEFAULT_EUTILS_REQUESTS_PER_SECOND` is therefore 10.0, still overridable
via `NCBI_EUTILS_RPS` without a code change. A deployment that runs with
NO `NCBI_API_KEY` is on NCBI's unauthenticated pool, whose ceiling is 3,
and must set `NCBI_EUTILS_RPS=3` itself: the default states the
keyed figure because every deployment of this product carries the key,
and the bounded fail-fast queue (`RateLimiter`, queue depth 15) is
unchanged either way. Datasets v2 and
PubChem get the rule's provisional ~5 req/s throttle for undocumented
interactive APIs, via `NCBI_DATASETS_RPS` / `NCBI_PUBCHEM_RPS`.

NCBI Variation Services (`api.ncbi.nlm.nih.gov`, added for T-3.2-02, the
`ncbi_dbsnp` tool's primary normalization path) is a fourth family,
`"variation"`, with its own pool, separate from all three above. Unlike
the eutils/datasets/pubchem figures, this one is not part of the
unresolved 3-vs-10-vs-100 E-utilities conflict: Section 6.3 line 1078 and
Section 21.1 both state roughly 1 request/second plainly, with no
competing figure anywhere in the source material.
`DEFAULT_VARIATION_REQUESTS_PER_SECOND` is that verified figure,
overridable via `NCBI_VARIATION_RPS`. It is also the tightest pool in the
roster, which is why `ncbi_dbsnp` (Section 6.3) runs its Variation
Services normalization call and its dbSNP ESummary clinical fetch
strictly sequentially rather than in parallel: parallelizing against a
~1 req/s pool would mean the second call routinely queues behind the
first regardless, and sequential ordering is separately required anyway
because the clinical fetch is keyed on the canonical id the normalization
call produces.

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

## Resolved: classify_status_coded_response's message extraction and Variation Services

Originally flagged here rather than fixed by T-3.2-02, which was scoped to
adding the `"variation"` rate-limit family only and deliberately did not
touch either classifier function's body. `classify_status_coded_response`
(below) is the correct classifier for Variation Services calls, confirmed
live by T-3.2 pre-build probes (`tracker/phase_3.2.md`): Variation
Services returns proper HTTP status codes (404 for a nonexistent rsid,
400 for a malformed SPDI or HGVS expression), the same status-branching
convention as Datasets v2 and PubChem, never the E-utilities
200-with-body pattern. So `http_status < 300` always correctly decided
`ok` vs `error` for a Variation Services response; that half was never
broken.

What was NOT yet correct until T-3.2-04:
`_extract_status_coded_error_message`'s body parsing, which supplies only
the human-readable `error_message` on the `ClassificationResult`, not the
ok/error verdict itself. It read `body["message"]` (Datasets v2's shape, a
top-level sibling key) and fell back to `body["Fault"]["Message"]`
(PubChem's shape). Variation Services' live-confirmed error body is
`{"error": {"code": ..., "message": ...}}`, with `message` nested one
level down, inside the `error` object, not at the top level. Neither of
the first two branches matched that shape, so a Variation Services error
response fell through to the generic `"HTTP {status} with no structured
error body"` message: the ok/error classification was unaffected (still
correctly `"error"`), but the specific reason ("RefSNP not found",
"Invalid SPDI: '...'") was lost. T-3.2-04 (`ncbi_dbsnp.py`) closed this
gap with a third, additive branch on `_extract_status_coded_error_message`
for the nested `{"error": {"message": ...}}` shape, since a Variation-
Services-shaped API is not unique to `ncbi_dbsnp`, and fixing it in the
shared helper (rather than only in `ncbi_dbsnp.py`'s own code) keeps it
fixed for any future caller of this classifier against the same shape.

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
      NCBI_DATASETS_RPS, NCBI_PUBCHEM_RPS, NCBI_VARIATION_RPS (rate
      overrides, optional)

Writes:
    - Nothing. Outbound HTTPS requests only; no local file or database
      writes.

Depended by:
    - system_03_search_agent.tools.ncbi_eutils_actions (T-3.1-03)
    - system_03_search_agent.tools.ncbi_datasets_actions (T-3.1-04)
    - system_03_search_agent.tools.ncbi_pubchem_actions (T-3.1-05)
    - system_03_search_agent.tools.ncbi_efetch (T-3.1-06/07)
    - system_03_search_agent.tools.ncbi_dbsnp (T-3.2-04; the reason the
      `"variation"` rate-limit family exists in this module at all)
    - system_03_search_agent.tools.pubtator_annotate (T-3.3-05; the reason
      the `"pubtator"` rate-limit family and the `{"detail": ...}` error
      message branch exist in this module at all)
    - system_03_search_agent.tools.litvar2_lookup (T-3.3-06; the reason the
      `"litvar2"` rate-limit family exists in this module)
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

# Imported as a module rather than by name. `execute_get` already has a
# parameter called `wait_ceiling_s`, so a bare `from ... import
# wait_ceiling_s` would shadow it, and the alias that avoids the shadowing
# is the one form isort and ruff disagree about here (build phase 5.0's
# F-5.0-30 recorded that isort is not idempotent in this repository). The
# module-qualified call is unambiguous and settles both.
from system_03_search_agent.harness import call_budget
from system_03_search_agent.observability.audit import (
    UNEXPECTED_ERROR_CODE,
    record_tool_call,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Budgets, per .claude/rules/tool-call-budgets.md and Section 6.2.
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_S: Final[float] = 15.0
DEFAULT_BACKOFF_S: Final[float] = 1.0

# See the module docstring's "Rate limiting" section: the keyed E-utilities
# ceiling, measured from NCBI's own rate-limit header with the project key
# and confirmed by the product owner on 2026-09-14 (UI fix set 11). Was 3.0,
# the unauthenticated floor, from build phase 3.1 until then. Configurable
# via NCBI_EUTILS_RPS; a keyless deployment sets it to 3.
DEFAULT_EUTILS_REQUESTS_PER_SECOND: Final[float] = 10.0
# Datasets v2 and PubChem have no published numeric rate limit; both get
# the rule's provisional ~5 req/s throttle for undocumented interactive
# HTTPS APIs.
DEFAULT_DATASETS_REQUESTS_PER_SECOND: Final[float] = 5.0
DEFAULT_PUBCHEM_REQUESTS_PER_SECOND: Final[float] = 5.0
# NCBI Variation Services, api.ncbi.nlm.nih.gov. Unlike the eutils figure
# above, this is NOT part of the unresolved 3-vs-10-vs-100 conflict: Section
# 6.3 line 1078 and Section 21.1 both state roughly 1 request/second
# plainly, the tightest pool in the roster. Configurable via
# NCBI_VARIATION_RPS.
DEFAULT_VARIATION_REQUESTS_PER_SECOND: Final[float] = 1.0
# PubTator3 (T-3.3-02, ncbi_dbsnp's sibling tool for the two Layer 3
# enrichment tools) and LitVar2 have no published numeric rate limit
# (Section 21.1), so both get the rule's provisional ~5 req/s throttle for
# undocumented interactive HTTPS APIs, the same treatment Datasets v2 and
# PubChem already received. Separate pools, not shared with each other or
# with "datasets"/"pubchem": the hosts are unrelated
# (www.ncbi.nlm.nih.gov/research/pubtator3-api and .../litvar2-api), and a
# shared pool would let contention on one host's calls throttle the other's
# unnecessarily. Configurable via NCBI_PUBTATOR_RPS / NCBI_LITVAR2_RPS.
DEFAULT_PUBTATOR_REQUESTS_PER_SECOND: Final[float] = 5.0
DEFAULT_LITVAR2_REQUESTS_PER_SECOND: Final[float] = 5.0
# ClinicalTrials.gov API v2 (T-3.5-02, clinicaltrials_search's only Layer 3
# call). No published numeric rate limit (Section 21.1), same provisional
# ~5 req/s throttle as pubtator/litvar2/datasets/pubchem. Its own family,
# not shared with any NCBI-hosted family: clinicaltrials.gov is not an
# ncbi.nlm.nih.gov subdomain, so contention on an NCBI host must never
# throttle this call and vice versa. Configurable via NCBI_CLINICALTRIALS_RPS
# (named for consistency with this module's other env vars, even though the
# host itself is not NCBI).
DEFAULT_CLINICALTRIALS_REQUESTS_PER_SECOND: Final[float] = 5.0

RateLimitFamily = Literal[
    "eutils", "datasets", "pubchem", "variation", "pubtator", "litvar2", "clinicaltrials"
]
RATE_LIMIT_FAMILIES: Final[tuple[RateLimitFamily, ...]] = (
    "eutils", "datasets", "pubchem", "variation", "pubtator", "litvar2", "clinicaltrials",
)

# T-5.0-05: which Section 20.3 data-access layer each family belongs to
# (system-design-patterns.md pattern 3). "eutils", "datasets", "pubchem"
# and "variation" are NCBI's own on-demand APIs (Layer 2); "pubtator",
# "litvar2" and "clinicaltrials" are the non-NCBI-or-enrichment services
# named Layer 3 in the three-layer architecture doc.
_LAYER_BY_FAMILY: Final[dict[str, int]] = {
    "eutils": 2,
    "datasets": 2,
    "pubchem": 2,
    "variation": 2,
    "pubtator": 3,
    "litvar2": 3,
    "clinicaltrials": 3,
}

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


#: Maps this module's typed TransportError family onto
#: `audit.AUDIT_ERROR_CODES`. Every member of the family is defined in this
#: file, so unlike `graph_connection`'s equivalent this one binds class
#: OBJECTS: there is no circular import to route around, and a class object
#: cannot be defeated by a rename the way a name string can.
#:
#: The base `TransportError` maps to `unexpected` on purpose. It is the
#: catch-all, so a NEW direct subclass added without a row here inherits
#: `unexpected` by MRO rather than leaking anything, and `test_audit.py`'s
#: enumerating arm turns red because it asserts every direct subclass maps
#: to something other than the catch-all.
_AUDIT_ERROR_CODE_BY_CLASS: dict[type[BaseException], str] = {
    TransportTimeoutError: "timeout",
    TransportConnectionError: "connection",
    TransportRateLimitedError: "rate_limited",
    TransportError: UNEXPECTED_ERROR_CODE,
}


def audit_error_code(exc: BaseException) -> str:
    """Classify one exception into the audit log's closed vocabulary.

    Walks the MRO so a subclass of an already-mapped error inherits its
    parent's code rather than falling to the catch-all.

    Anything that is not a `TransportError`, an `httpx` exception that
    escaped `_execute_with_retry`'s own classification, or a failure while
    building the client, returns `unexpected`. That fail-closed branch is
    why `execute_get`'s `except Exception` needs no provenance argument:
    whatever arrives, the audit line records a code chosen here rather
    than anything derived from the exception's message, which for this
    module is the one place a URL carrying `_append_api_key`'s appended
    credential could otherwise have appeared.
    """
    for klass in type(exc).__mro__:
        code = _AUDIT_ERROR_CODE_BY_CLASS.get(klass)
        if code is not None:
            return code
    return UNEXPECTED_ERROR_CODE


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

    Available for a caller that has already decided a response is a 429
    or a 503 and needs a guaranteed wait estimate rather than an optional
    one, for example to actually schedule a retry:

        if response.status_code == 429:
            wait = ncbi_transport.retry_after_for_response(response)

    `default` is this module's own backoff budget, the same value the
    retry itself would have used, so an absent or unparseable header
    yields a sane number rather than `None` for a caller that must state
    one.

    As of re-review round 1 (2026-08-07) no production call site actually
    uses this function; `http_status_error_message`'s user-facing message
    deliberately uses `parse_retry_after` instead (see `_retry_after_hint`'s
    docstring for why: this function's guaranteed-a-number contract is
    wrong for rendering a message someone reads, where "the server did not
    say" must stay distinguishable from a real value). This function is
    kept for a caller that genuinely needs the guaranteed-number contract,
    such as computing an actual sleep duration; do not read its presence
    here as evidence it is wired into the request path.
    """
    parsed = parse_retry_after(response.headers)
    return default if parsed is None else parsed


def http_status_error_message(source: str, response: httpx.Response) -> str | None:
    """Map a non-success HTTP status to an actionable message, or None if fine.

    Re-review round 1 (2026-08-07): this function used to live in
    `ncbi_eutils_actions.py`, private and single-caller. A second,
    independent verification pass on that fix found the gap the first fix
    round left: `ncbi_coordinate_overlap.py` shares the same eutils
    transport and the same deliberately status-blind `classify_eutils_response`
    (below) at two of its own hops (ESearch and ESummary), and never
    picked up the status-code check `ncbi_eutils_actions.py` got. A 429 or
    503 there still told the next agent step to rewrite the chromosome and
    coordinate window, exactly the wrong-direction retry advice
    `production-standards.md`'s retry-safety gate forbids. Moving the
    check here, to the transport module every eutils-backed action already
    imports, is what lets every call site share ONE mapping instead of
    each file growing (or forgetting to grow) its own copy. This is the
    same lesson as `parse_retry_after` two functions above: a helper two
    files both need belongs in the shared module, not duplicated per
    caller.

    `source` names the caller for the message ("E-utilities", "EInfo",
    "coordinate_overlap ESearch prefilter", etc.); the mapping itself does
    not vary by caller.
    """
    status_code = getattr(response, "status_code", 200)
    if status_code == 429:
        return (
            f"{source} returned HTTP 429 (rate limited). Retry after a backoff; "
            f"if this recurs, reduce the request rate."
            f"{_retry_after_hint(response)}"
        )
    if status_code >= 500:
        return (
            f"{source} returned HTTP {status_code} (server error). Retry after a "
            f"backoff; if this recurs, the NCBI service may be degraded."
        )
    if status_code >= 400:
        return (
            f"{source} returned HTTP {status_code}. The request may be malformed; "
            f"verify the parameters and retry."
        )
    return None


def _retry_after_hint(response: httpx.Response) -> str:
    """Render the retry delay for a 429, or "" when the server didn't say.

    F-3.1-51 (Step 6.2, 2026-08-10): corrected from "429/503", which
    overclaimed coverage this function never had. Only the 429 branch of
    `http_status_error_message` calls this; the >=500 branch's message
    already gives an actionable direction ("retry after a backoff") without
    a specific number, which satisfies the retry-safety gate on its own.

    Deliberately calls `parse_retry_after` (which returns `None` on a
    missing or unparseable header), not `retry_after_for_response` (which
    always returns a number via `DEFAULT_BACKOFF_S`). An in-code retry uses
    that default because it has to sleep for SOME duration either way; a
    message shown to a caller must not present that fallback as if the
    server had stated it; "Retry after 1 seconds" when NCBI said nothing is
    a fabricated-looking number, not an actionable one. A caught bug during
    re-review round 1's own integration fix (2026-08-07): the first draft
    of this function called `retry_after_for_response` and silently turned
    "we don't know" into a confidently wrong "1 second" on every
    header-less 429, exactly the kind of small, plausible mistake this
    round's re-review process exists to catch before it ships a second
    time.
    """
    candidate = parse_retry_after(response.headers)
    if candidate is None:
        return ""
    # Render a whole-second value without a trailing ".0": the parser
    # always returns a float (it may need to represent a fractional wait),
    # but NCBI's own Retry-After header is almost always a bare integer,
    # and "Retry after 7.0 seconds" reads as a rendering artifact, not a
    # signal worth a decimal point.
    text = f"{candidate:g}"
    if len(text) > 40:
        return ""
    return f" Retry after {text} seconds."


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
        # NCBI Variation Services: {"error": {"code", "message"}}, with
        # "message" nested one level down inside the "error" object rather
        # than at the top level (Datasets v2's shape) or inside a "Fault"
        # sibling key (PubChem's shape). Confirmed live 2026-08-08
        # (tracker/phase_3.2.md's pre-build probes, T-3.2-04): a nonexistent
        # rsid returns {"error": {"code": 404, "message": "RefSNP not
        # found"}}, a malformed SPDI or HGVS expression returns {"error":
        # {"code": 400, "message": "Invalid SPDI: '...'"}}. This branch is
        # checked last, after the two existing ones, so it can only ever
        # fire when neither of their shapes matched, and it resolves the
        # "Known gap" this module's own docstring used to flag as left for
        # T-3.2-04: the ok/error verdict was always correct for Variation
        # Services (it comes from `http_status` alone, above), only the
        # human-readable reason was falling through to the generic
        # fallback string below.
        error_obj = body.get("error")
        if isinstance(error_obj, dict) and "message" in error_obj:
            return str(error_obj["message"])
        # PubTator3 (annotate_publications 400) and LitVar2 (both error
        # paths): {"detail": "..."}, a top-level string, not nested and not
        # named "message". Confirmed live 2026-08-08 (tracker/phase_3.3.md's
        # pre-build probes, T-3.3-02): a nonexistent-PMID biocjson export
        # returns {"detail": "Could not retrieve publications"}; a
        # not-found LitVar2 variant id returns {"detail": "Variant not
        # found: ..."}. Checked last, after the three existing branches, so
        # it only ever fires when none of their shapes matched. A caller
        # whose empty-query 400 comes back as a bare JSON array of strings
        # (F-3.3-02, PubTator3 entity_lookup with no query) still falls
        # through every branch here, including this one, to the generic
        # fallback below: that shape is deliberately not special-cased,
        # since T-3.3-03's schema-layer minLength closes the only path a
        # caller could reach it from in production, and a generic-but-safe
        # message is the correct behavior for a shape no production call
        # can trigger.
        if "detail" in body:
            return str(body["detail"])
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
    # `.claude/rules/tool-call-budgets.md`: queue depth is "a small multiple
    # of the family's per-second rate". The other three families each use
    # roughly a 5x multiple (eutils 3 req/s -> 15, datasets/pubchem 5 req/s
    # -> 25). Applying the same 5x reasoning at variation's ~1 req/s gives 5,
    # deliberately smaller than eutils' and datasets'/pubchem's depth: a
    # queue this shallow against a pool this tight (1 request/second) still
    # represents up to ~5 seconds of worst-case queued wait, which is
    # already a meaningful fraction of this tool's own 15s-per-call (30s
    # worst-case two-call) budget (Section 6.3), so a deeper queue here
    # would let a caller wait past what the tool's own timeout can absorb
    # before the pool even gets a turn.
    "variation": _FamilyConfig(DEFAULT_VARIATION_REQUESTS_PER_SECOND, 5, "NCBI_VARIATION_RPS"),
    # Same 5x-multiple reasoning as "datasets"/"pubchem" above (5 req/s ->
    # 25 queue depth): both new families share that provisional 5 req/s
    # figure, so they share its queue-depth reasoning too.
    "pubtator": _FamilyConfig(DEFAULT_PUBTATOR_REQUESTS_PER_SECOND, 25, "NCBI_PUBTATOR_RPS"),
    "litvar2": _FamilyConfig(DEFAULT_LITVAR2_REQUESTS_PER_SECOND, 25, "NCBI_LITVAR2_RPS"),
    # Same 5x-multiple reasoning again: the provisional 5 req/s figure gets
    # the same 25 queue depth as every other family sharing that figure.
    "clinicaltrials": _FamilyConfig(
        DEFAULT_CLINICALTRIALS_REQUESTS_PER_SECOND, 25, "NCBI_CLINICALTRIALS_RPS"
    ),
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


def _endpoint_for_audit(url: str) -> str:
    """Host plus path for an audit line, per F-5.0-08. Never the query string.

    `_host_of` alone drops the path, and the path is useful diagnostic
    context that carries no secret of its own; only the query string can
    carry `_append_api_key`'s appended credential, so this stops at the
    path and goes no further. `redact_params` in `observability/audit.py`
    is a second, independent layer against the same leak; this is the
    first and the one this ticket is directly responsible for.
    """
    parsed = urllib.parse.urlparse(url)
    return (parsed.hostname or "unknown-host") + (parsed.path or "")


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
    # T-6.0-02, Section 21.4: "The queue reads the caller's remaining
    # per-step time budget rather than applying one constant across every
    # query class." Resolution order, most specific first:
    #
    #   1. An explicit `wait_ceiling_s` from the caller. Unchanged, and it
    #      still wins, because a caller that names a ceiling knows something
    #      this function does not (`ncbi_coordinate_overlap` splits one
    #      budget across a two-step traversal).
    #   2. The running query's own class budget, when a query scope is bound.
    #      This is the branch Section 21.4 describes and the branch that did
    #      not exist before this ticket.
    #   3. `timeout_s`, the per-call default. Reached only outside a query,
    #      which is exactly where there is no query class to read.
    #
    # Step 2 is what makes a lookup fail fast against a saturated pool while
    # a deep-research query waits. Before it, every class took step 3 and
    # got the identical ceiling, which is the "one constant" 21.4 rules out.
    effective_ceiling = wait_ceiling_s
    if effective_ceiling is None:
        effective_ceiling = call_budget.wait_ceiling_s()
    if effective_ceiling is None:
        effective_ceiling = timeout_s

    # T-5.0-05: this is one of the three transport chokepoints (audit.py's
    # module docstring, tracker/phase_5.0.md finding one), so it and not
    # `act_node` is where every Layer 2/Layer 3 HTTPS access, including the
    # five call sites that bypass `act_node` entirely, gets its one audit
    # line. Timed around the actual await only, per this ticket's
    # instruction, never around URL/query-string assembly above.
    audit_started = time_fn()
    try:
        if client is not None:
            response = await _execute_with_retry(
                client, url, family=family, timeout_s=timeout_s, backoff_s=backoff_s,
                sleep_fn=sleep_fn, limiter=limiter, wait_budget_s=effective_ceiling,
                time_fn=time_fn,
            )
        else:
            # No caller-supplied client: build one scoped to exactly this
            # call, bound to whichever event loop is running THIS await, and
            # close it before returning. Never stored at module level, so no
            # later call from a different loop can ever inherit it.
            async with httpx.AsyncClient() as fresh_client:
                response = await _execute_with_retry(
                    fresh_client, url, family=family, timeout_s=timeout_s,
                    backoff_s=backoff_s, sleep_fn=sleep_fn, limiter=limiter,
                    wait_budget_s=effective_ceiling, time_fn=time_fn,
                )
    except Exception as exc:
        # `record_tool_call` never raises (best-effort by its own contract),
        # so this is not wrapped in a second try/except here; the audit line
        # is written and then the real failure propagates unchanged.
        record_tool_call(
            tool="ncbi_transport:" + family,
            layer=_LAYER_BY_FAMILY.get(family, 2),
            endpoint=_endpoint_for_audit(url),
            latency_ms=(time_fn() - audit_started) * 1000,
            authorization="ncbi_api_key" if include_api_key else "none",
            # `params` is the caller-supplied dict, never the built query
            # string, so it never carries the api_key `_append_api_key`
            # appends separately from `params`. `redact_params` still
            # applies its own key-name and value-scanning rules on top.
            params=dict(params),
            http_status=None,
            # Classified, never stringified. `str(exc)` used to go here.
            # `_host_of` keeps this module's OWN diagnostics free of the
            # api_key `_append_api_key` appends, but an exception raised
            # by httpx or by any future caller is not bound by that
            # convention, and `except Exception` is bounded by nothing. A
            # code from a closed vocabulary plus a class name are both
            # chosen by this repository's own code, so neither can carry
            # a URL, a query string, or a response body at all.
            error_code=audit_error_code(exc),
            error_class=type(exc).__name__,
        )
        raise
    record_tool_call(
        tool="ncbi_transport:" + family,
        layer=_LAYER_BY_FAMILY.get(family, 2),
        endpoint=_endpoint_for_audit(url),
        latency_ms=(time_fn() - audit_started) * 1000,
        authorization="ncbi_api_key" if include_api_key else "none",
        params=dict(params),
        http_status=response.status_code,
        error_code=None,
        error_class=None,
    )
    return response


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
    silently doubles under retry is not a budget.

    Re-review round 1, adversarial pass (2026-08-07): F-3.1-37's own fix
    shared the budget by wall-clock DEADLINE (`deadline = time_fn() +
    wait_budget_s`, each acquisition handed `deadline - now`), which
    charges the ceiling for the HTTP request's own elapsed time and the
    backoff sleep, not only time actually spent waiting for the pool.
    This function's docstring (and `tool-call-budgets.md`) both scope the
    ceiling to POOL wait specifically. With the common case
    `wait_ceiling_s == timeout_s`, a first attempt that times out has, by
    construction, already consumed the entire wall-clock deadline before
    the retry's acquisition ever runs, so the retry is handed
    approximately 0.0s of wait budget every time a timeout is exactly the
    reason a retry is needed - silently defeating the F-3.1-22 fix it was
    meant to preserve, in precisely the case that fix exists for. Fixed
    by tracking `wait_spent`, incremented only by the time actually spent
    inside `limiter.acquire`, never by the request or backoff time
    surrounding it. A first attempt that waits 1.0s against a 1.5s
    ceiling leaves the retry 0.5s of POOL wait regardless of how long the
    request itself then takes, and a retry that cannot be scheduled
    inside what remains fails fast rather than waiting a second full
    ceiling.
    """
    host = _host_of(url)
    last_exc: Exception | None = None
    wait_spent = 0.0

    for attempt_index in range(2):
        # T-6.0-01, Section 21.3's per-query Layer 2/3 call ceiling. Charged
        # here, inside the attempt loop, rather than once per `execute_get`,
        # because 21.3 names "a retry" first in its own list of where a 21st
        # call comes from. A charge hoisted out of this loop would let a
        # query issue 40 requests against a 20-call ceiling and report 20.
        #
        # Charged BEFORE `limiter.acquire`, so a refused call spends neither
        # a rate-limit token nor queue depth on its way to being refused,
        # and never reaches the network at all. Same ordering discipline as
        # `act_node`'s cost check: refuse before dispatch, never after.
        #
        # No-ops outside a query scope; see `charge_one_call`'s docstring
        # for why unscoped work (a KGX export batch) is deliberately not
        # bounded by a per-query ceiling.
        call_budget.charge_one_call(
            tool="ncbi_transport:" + family, layer=_LAYER_BY_FAMILY.get(family, 2)
        )

        remaining_wait_budget = max(0.0, wait_budget_s - wait_spent)
        acquire_started = time_fn()
        try:
            await limiter.acquire(remaining_wait_budget, time_fn=time_fn, sleep_fn=sleep_fn)
        except TransportRateLimitedError as rate_exc:
            wait_spent += time_fn() - acquire_started
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
        wait_spent += time_fn() - acquire_started
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
