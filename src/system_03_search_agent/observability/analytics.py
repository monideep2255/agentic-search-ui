"""T-5.0-04: PostHog behavioral analytics, tech spec Section 20.2.

Section 20.2 names six product-usage signals PostHog is meant to own: query
volume, feedback-button clicks, abstain rate, the follow-up-query funnel,
saved-query creation, and session length. Only three of those are honestly
producible from what this repository has actually built today, and this
module emits exactly those three and nothing else:

    - Query volume: every completed query already writes an `interactions`
      row from `core/run.py`'s epilogue, so a query finishing is a real,
      countable event.
    - Feedback submitted: `POST /v1/query/{run_id}/feedback` already exists
      in `adapters/web_sse/app.py` and already validates ownership before
      it writes anything.
    - Abstain rate, as a trust outcome: `interactions.rubric_outcome`
      (`pass|fail|abstain`) and `interactions.trust_signal`
      (`answer|flag|ask|refuse`) are populated on every captured row.

The other three are NOT built and this module does not approximate them:
saved-query creation has a table (`data/models.py`'s `SavedQuery`, line
311) and no endpoint that writes to it; the follow-up-query funnel has join
keys (`session_id`, `trace_id`) and no funnel logic that groups turns into
a session and measures continuation; session length has no live
start/end event anywhere in the codebase, only a `sessions` row created
lazily by session memory with no matching close event. Wiring an event for
any of the three before the feature it measures actually exists would ship
a metric that always reads zero or always reads the same placeholder
value, which is worse than no metric: it looks like real product signal to
whoever reads the PostHog dashboard next.

THE BINDING CONSTRAINT (Section 20.2, and Section 16's privacy line repeats
it): PostHog receives aggregates only, event names and counts. Never raw
query text, never citation content, never account PII. This module's
`build_properties` is the mechanism that makes that true by construction
rather than by every call site remembering it: see that function's own
docstring for the allowlist design.

Depends on:
    - system_03_search_agent.observability.config (analytics_enabled,
      posthog_api_key, posthog_host). Whether analytics runs at all, and
      where it sends to, are resolved there and nowhere else in this
      module, matching every other observability record's discipline.
    - system_03_search_agent.feedback.contracts (QueryClass, TrustSignal,
      RubricOutcome). These are the exact closed vocabularies
      `interactions.query_class`, `.trust_signal` and `.rubric_outcome`
      are already constrained to at the database layer (Section 15's CHECK
      constraints). Reusing them here, rather than re-deriving a second
      copy of the same three value sets, is what keeps this module's
      allowlist and the database's own constraint from silently drifting
      apart as either one changes.

Reads:
    - Nothing beyond what a caller passes in. This module holds no state
      of its own between calls and reads no table.

Writes:
    - An HTTPS POST to `posthog_host() + "/i/v0/e"`, and only when
      `analytics_enabled()` is true. No batch endpoint is implemented:
      PostHog's `/batch` path exists in the wire contract this ticket
      researched, but nothing in this repository yet calls `capture_event`
      often enough in one place to need batching, and building it ahead of
      that need is scope this ticket does not own.

## Best-effort by construction, matching `feedback/writer.py`

`capture_event` never raises. A caller (the eventual T-5.0-05 wiring, not
this module) calls it exactly like a fire-and-forget background task: an
analytics outage, a bad key, a network timeout, or a caller-supplied
property this module refuses to send must never fail, delay, or alter the
answer a user is waiting on. On any failure this function logs the
exception's CLASS NAME only, never `str(exc)` and never the property
values that were being sent, for the same reason `feedback/writer.py`
never logs `str(exc)`: a driver or client exception can carry request
detail in its own message text, and Section 16's secrets discipline
applies here exactly as it does to the interactions writer.

## What a 200 from PostHog does and does not prove (F-5.0-05)

F-5.0-05, filed in `tracker/phase_5.0.md`, measured that PostHog's capture
endpoint returns `200 {"status":"Ok"}` for a project key invented on the
spot, live, against both hosts. A 200 therefore proves only that a request
left this process and something answered; it proves nothing about whether
the key is valid, the project exists, or the event was ever ingested. This
module never branches on the response body for that reason: `capture_event`
does not parse, does not retry on a non-200, and does not treat a 200 as
confirmation of anything. It fires the request and returns, which is the
only posture consistent with what the response can actually tell it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, get_args

import httpx

from system_03_search_agent.feedback.contracts import QueryClass, RubricOutcome, TrustSignal
from system_03_search_agent.observability.config import (
    analytics_enabled,
    posthog_api_key,
    posthog_host,
)

__all__ = [
    "AnalyticsEvent",
    "UnsafePropertyError",
    "build_properties",
    "capture_event",
]

logger = logging.getLogger(__name__)

#: PostHog's single-event capture path (the wire contract this ticket
#: researched against PostHog's own documentation). The batch path,
#: `/batch`, is deliberately not used; see this module's own docstring.
_CAPTURE_PATH = "/i/v0/e"

#: A best-effort side channel, matching `feedback/writer.py`'s discipline:
#: this must never meaningfully delay the background task it runs inside.
#: Deliberately NOT httpx's own default (5.0s), so a test asserting this
#: value was actually passed to the request cannot pass by accident
#: against whatever httpx happens to default to.
CAPTURE_TIMEOUT_SECONDS = 4.0

#: PostHog's own documented limit on `distinct_id`; longer is silently
#: truncated by PostHog, so this module truncates first rather than
#: shipping a value PostHog would have cut at a boundary this module never
#: chose.
_DISTINCT_ID_MAX_LENGTH = 200

#: Sent when `capture_event` is called with no distinct id at all (a
#: defensive branch: every real caller in this codebase resolves an
#: `owner_id` of the form `user:<uuid>` or `guest:<uuid>` before an event
#: could exist to report, per `auth/dependencies.py`'s `Principal`, so a
#: `None` here should not occur in practice). The three events this module
#: emits are all simple counts, not per-user funnels, so bucketing an
#: identity-less event under one shared id keeps the count from being
#: silently dropped, at the cost of that one event not being separable by
#: caller. That cost is acceptable for a count; it would not be for a
#: metric that needed real per-user grouping, which is exactly why the
#: follow-up-query funnel and session length are not built here yet.
_ANONYMOUS_DISTINCT_ID = "anonymous"


class AnalyticsEvent(str, Enum):
    """The closed set of events this repository can honestly emit today.

    A `str` subclass so `AnalyticsEvent.QUERY_COMPLETED.value` and plain
    equality against the wire string both work without a second mapping.
    """

    #: One per completed query, fired from the run epilogue (T-5.0-05).
    #: This is Section 20.2's "query volume" signal.
    QUERY_COMPLETED = "query_completed"

    #: One per successful `POST /v1/query/{run_id}/feedback` call. This is
    #: Section 20.2's "feedback-button clicks" signal.
    FEEDBACK_SUBMITTED = "feedback_submitted"

    #: One per completed query, carrying that query's `trust_signal` and
    #: `rubric_outcome`. This is Section 20.2's "abstain rate" signal,
    #: named for the pair PostHog actually needs to compute an abstain
    #: rate rather than for the narrower word alone.
    TRUST_OUTCOME_RECORDED = "trust_outcome_recorded"


class UnsafePropertyError(ValueError):
    """Raised by `build_properties` for any property it will not send.

    Never carries the offending VALUE in a form a caller of `build_properties`
    could accidentally log whole; see that function's docstring for what
    each branch's message does and does not include.
    """


# ---------------------------------------------------------------------------
# The properties allowlist. See `build_properties` for the design rationale.
# ---------------------------------------------------------------------------

#: Reused from `feedback/contracts.py` rather than re-typed here, so this
#: allowlist and the database's own CHECK constraints on `query_class`,
#: `trust_signal` and `rubric_outcome` cannot silently drift apart.
_QUERY_CLASS_VALUES: frozenset[str] = frozenset(get_args(QueryClass))
_TRUST_SIGNAL_VALUES: frozenset[str] = frozenset(get_args(TrustSignal))
_RUBRIC_OUTCOME_VALUES: frozenset[str] = frozenset(get_args(RubricOutcome))

#: `feedback/contracts.py`'s `FeedbackPayload.rating` field, an inline
#: `Literal["up", "down"] | None`, not exported as a named type the way the
#: other three are, so this is the one value set in this module that is
#: hand-copied rather than imported. It is two literal characters wide and
#: owned by that field's own docstring; if it ever changes shape, the
#: correct fix is exporting a named `Rating` type there for this module to
#: import, the same as the other three.
_RATING_VALUES: frozenset[str] = frozenset({"up", "down"})

_SafePropertyKind = Literal["bool", "count", "enum"]


@dataclass(frozen=True)
class _PropertySpec:
    """One property's allowed shape. `allowed_values` is set only for `"enum"`."""

    kind: _SafePropertyKind
    allowed_values: frozenset[str] | None = None


#: The whole allowlist. A property name absent from this mapping is refused
#: outright, regardless of its value or type: see `build_properties`.
_PROPERTY_SCHEMA: dict[str, _PropertySpec] = {
    "query_class": _PropertySpec("enum", _QUERY_CLASS_VALUES),
    "trust_signal": _PropertySpec("enum", _TRUST_SIGNAL_VALUES),
    "rubric_outcome": _PropertySpec("enum", _RUBRIC_OUTCOME_VALUES),
    "rating": _PropertySpec("enum", _RATING_VALUES),
    "has_citations": _PropertySpec("bool"),
    "was_flagged": _PropertySpec("bool"),
    "has_comment": _PropertySpec("bool"),
    "citation_flag_count": _PropertySpec("count"),
    "citation_count": _PropertySpec("count"),
    "latency_ms": _PropertySpec("count"),
}


def build_properties(**properties: Any) -> dict[str, bool | int | float | str]:
    """Validate caller-supplied properties into the only shapes PostHog may receive.

    Design decision, stated once here because it is this module's whole
    reason to exist: this is an ALLOWLIST, not a blocklist. A blocklist
    would mean scanning each value for patterns that look like free text
    (spaces, sentence punctuation, a minimum length) and rejecting matches,
    which only ever catches the shapes of leak someone thought to write a
    rule for. This function instead permits nothing by default: a property
    name must be registered in `_PROPERTY_SCHEMA` with an explicit allowed
    shape, bool, a number, or a member of a named closed string set, before
    any value under that name can leave this process. A caller cannot
    invent a new property key and put free text behind it, because no key
    is safe until it is deliberately added here, and every key that is
    added here can only ever carry a bool, a number, or one of a fixed
    small set of short strings.

    RAISES rather than silently dropping the one bad property and sending
    the rest. Two reasons. First, a drop-and-continue design would still
    ship a partial event, and a partial event with an unexplained missing
    field is a worse debugging experience than no event at all for a
    caller trying to find out why their property never showed up in
    PostHog. Second, and more load-bearing: `capture_event` wraps this
    call in the same best-effort discipline `feedback/writer.py` uses for
    the database, catching the raise, logging only the exception's class
    name, and returning quietly. So raising here costs the caller nothing
    at the top of the stack; it only makes the failure loud enough to be
    caught and logged one frame up, instead of silent all the way through.

    The exception message itself is safe to log as a class name but NOT
    necessarily as text: the two branches below that report a rejected
    VALUE (`"enum"` and, implicitly, any caller passing a raw string under
    an enum-typed key) embed that value in the message via `!r}` so a
    developer debugging a `pytest.raises` failure can see what was
    rejected. `capture_event` never logs `str(exc)`, only
    `type(exc).__name__`, specifically because of this: the message text
    can carry exactly the caller-supplied content this function exists to
    keep out of PostHog, so it must never reach a log line that could
    itself be shipped or aggregated downstream. The one branch that omits
    the value entirely, an unregistered key, is deliberately the message
    every caller sees first when they mistype a property name, and it is
    always safe to log in full since it names only the KEY, never a value.
    """
    safe: dict[str, bool | int | float | str] = {}
    for key, value in properties.items():
        spec = _PROPERTY_SCHEMA.get(key)
        if spec is None:
            raise UnsafePropertyError(
                f"{key!r} is not a registered analytics property; register it in "
                "_PROPERTY_SCHEMA with an explicit allowed shape before sending it, "
                "this module never forwards an unrecognized property"
            )

        if spec.kind == "bool":
            if not isinstance(value, bool):
                raise UnsafePropertyError(
                    f"{key!r} must be a bool, got {type(value).__name__}"
                )
            safe[key] = value

        elif spec.kind == "count":
            # `bool` is a subclass of `int` in Python; excluded explicitly
            # so a stray `True`/`False` under a count-typed key is refused
            # rather than silently sent as `1`/`0`.
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise UnsafePropertyError(
                    f"{key!r} must be a number, got {type(value).__name__}"
                )
            safe[key] = value

        elif spec.kind == "enum":
            allowed = spec.allowed_values or frozenset()
            if not isinstance(value, str) or value not in allowed:
                raise UnsafePropertyError(
                    f"{key!r} must be one of {sorted(allowed)!r}, got {value!r}"
                )
            safe[key] = value

        else:  # pragma: no cover - exhaustive over _SafePropertyKind, defensive only
            raise UnsafePropertyError(f"{key!r} has an unhandled property kind {spec.kind!r}")

    return safe


def _bounded_distinct_id(distinct_id: str | None) -> str:
    """PostHog's `distinct_id`, truncated to its documented 200-char limit.

    `owner_id` (`auth/dependencies.py`'s `Principal.owner_id`,
    `feedback/writer.py`'s same-named column) is the value every real
    caller passes: an opaque namespaced identifier, `user:<uuid>` or
    `guest:<uuid>`, never an email address or another directly identifying
    value. It carries no PII by itself, which is what makes it safe to use
    here at all; this function only handles its LENGTH, not its content.

    An empty or missing id falls back to a fixed shared bucket rather than
    dropping the event; see `_ANONYMOUS_DISTINCT_ID`'s own comment for why
    that trade is acceptable for the three count-shaped events this module
    sends.
    """
    if not distinct_id:
        return _ANONYMOUS_DISTINCT_ID
    return distinct_id[:_DISTINCT_ID_MAX_LENGTH]


async def capture_event(
    event: AnalyticsEvent,
    *,
    distinct_id: str | None,
    properties: dict[str, Any] | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Best-effort PostHog capture. Never raises. A no-op when analytics is off.

    Makes NO outbound call at all when `analytics_enabled()` is false,
    which is `config.py`'s own on/off answer: no ambient flag, a
    provisioned `POSTHOG_API_KEY` is the whole signal. This function does
    not re-derive that decision; it defers to `config` entirely, matching
    every other observability record's discipline of one answer to "is
    this on" living in one place.

    `properties` is validated through `build_properties` before anything
    is sent. A property this module will not send causes the WHOLE event
    to be dropped, never a partially-populated one, and the caller is never
    told: this is the background side-channel, not a request the caller is
    waiting on, so there is nothing for it to react to. The failure is
    logged (exception class name only, per this module's own docstring),
    not silent to an operator, only silent to the code that called this
    function.

    `client` lets a caller (in practice, a test) supply an already-built
    `httpx.AsyncClient`, matching the pattern `tools/ncbi_transport.py`'s
    `execute_get` and `tools/pathogen_ftp_transport.py` already use: reuse
    a caller-supplied client when given one, otherwise open one scoped to
    exactly this call and close it before returning, never held at module
    level where a later call from a different event loop could inherit it.

    The declared timeout, `CAPTURE_TIMEOUT_SECONDS`, is passed explicitly
    on the POST call itself in both branches below, never left to
    whatever timeout the client happens to default to.
    """
    if not analytics_enabled():
        return

    api_key = posthog_api_key()
    if api_key is None:  # pragma: no cover - analytics_enabled() already guarantees this
        return

    try:
        safe_properties = build_properties(**(properties or {}))
    except UnsafePropertyError as exc:
        logger.warning(
            "analytics event %s dropped, a property failed the allowlist (%s)",
            event.value,
            type(exc).__name__,
        )
        return

    body: dict[str, Any] = {
        "api_key": api_key,
        "event": event.value,
        "distinct_id": _bounded_distinct_id(distinct_id),
        "properties": safe_properties,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    url = posthog_host() + _CAPTURE_PATH

    try:
        if client is not None:
            await client.post(url, json=body, timeout=CAPTURE_TIMEOUT_SECONDS)
        else:
            async with httpx.AsyncClient() as fresh_client:
                await fresh_client.post(url, json=body, timeout=CAPTURE_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - a best-effort side channel must catch any failure mode
        logger.warning(
            "analytics event %s failed to send (%s)",
            event.value,
            type(exc).__name__,
        )
        return
