"""The GraphQL type layer: build phase 4.3, ticket T-4.3-01.

Spec: `tracker/phase_4.3.md`'s "Module contracts" and "The interfaces, fixed
by the lead before dispatch" sections, `requirements/Technical_
specification.md` Section 9.1 (`CitationPayload`, referenced not restated).

Every type here mirrors a Section 2.3 payload model field for field: the
same names, nothing renamed, invented, or dropped. Field values stay plain
`str` even where the source payload types a field as a `Literal` (`outcome`,
`risk_tier`, `layer`, `scope`, ...): GraphQL's own type system carries no
enum-vs-string distinction that changes wire behavior for these fields, and
`AskInput.audience_depth` is the one field `tracker/phase_4.3.md` names
explicitly as needing a real Strawberry enum (an INPUT field, where GraphQL
enum validation actually rejects a bad value before it ever reaches this
surface's core).

Strawberry's default `StrawberryConfig(auto_camel_case=True)` converts every
snake_case field declared below into camelCase on the wire (`source_url`
becomes `sourceUrl`), so nothing here hand-writes a camelCase name.

A hard rule this module holds itself to: no `@strawberry.type`, `@strawberry.
input`, or `@strawberry.enum` class carries a docstring, and no field uses
`strawberry.field(description=...)`. Strawberry prints a class or field
docstring into the GraphQL SDL as that type's or field's description, and
the phase 4.3 premise gate's `test_the_schema_has_no_field_a_cost_figure_
could_be_selected_into` arm greps the ENTIRE printed schema (`str(schema)`)
for the substrings "cost", "usd", and "spend", case-insensitively. A type
docstring that merely explains why no cost field exists would itself contain
one of those words and would fail that arm by the exact mechanism it exists
to catch. Every explanation below therefore lives in a plain `#` comment
(never printed into the schema), never in a class or field docstring.

Depends on:
    - system_03_search_agent.contracts.events (CitationPayload,
      NCBI_SOURCE_URL_PATTERN, TrustSignalPayload): the Section 2.3 payload
      models this module's types mirror, and the host-pinned URL pattern
      `Citation.from_payload` re-validates against.
    - system_03_search_agent.contracts.query (Query): read at import time
      for the two INPUT bounds `AskInput` publishes, so the GraphQL layer
      and the core contract cannot drift (F-4.3-A-16 / J-10).
    - graphql (GraphQLError): the base `InvalidAskInput` must carry so a
      scalar's `parse_value` failure reaches the caller as a located,
      coded, caller-fixable error instead of a masked internal one.

Reads:
    - Nothing directly.

Writes:
    - Nothing directly.
"""

from __future__ import annotations

import enum
import re
from typing import Any, NewType, NoReturn

import strawberry
from graphql import GraphQLError

from system_03_search_agent.contracts.events import (
    NCBI_SOURCE_URL_PATTERN,
    CitationPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query as CoreQuery

# ---------------------------------------------------------------------------
# Exception base. Every exception this module raises subclasses this one,
# and every catch of one of this module's exceptions (in this module or in
# fold.py) dispatches on this base, never on an enumerated subclass list.
# tracker/phase_4.3.md's module contract calls this out by name: an
# enumerated catch list drifted out of sync with its raiser three separate
# times inside build phase 4.2 alone. Subclasses `ValueError` so a plain
# `except ValueError:` at a call site (the same class Pydantic's own
# `ValidationError` already subclasses) also catches it, without that being
# the primary way a caller is expected to catch it.
# ---------------------------------------------------------------------------


class GraphQLTypeError(ValueError):
    pass


class InvalidCitationPayloadError(GraphQLTypeError):
    pass


# ---------------------------------------------------------------------------
# The caller-facing error base, and the one caller-facing error this module
# raises.
#
# `SchemaError` LIVES HERE rather than in schema.py, where it was first
# written, and the move is load-bearing rather than cosmetic. `security.py`
# discloses an exception to the caller only when its class sets
# `PUBLIC_ERROR_MARKER` (F-4.3-A-12 replaced the old "trusted because of the
# package it lives in" rule with this declared one), and this module now
# needs to raise a caller-facing error of its own for an out-of-bounds
# `AskInput` field. schema.py imports types.py, so types.py can never import
# schema.py; one shared base for the whole surface therefore has to sit on
# this side of that edge. schema.py re-exports it, so `schema.SchemaError`
# still names this exact class and every existing subclass there is
# unchanged. `_error_code_for` derives the wire code from the CLASS NAME
# alone, so moving the definition changes no published code.
#
# The discipline the marker buys is unchanged and still binding: every
# message raised through a `SchemaError` is a fixed module-level literal,
# never interpolated from a caught exception, a host, a path, or an internal
# bound. `GraphQLTypeError` above deliberately does NOT descend from this
# base: `InvalidCitationPayloadError`'s message names a citation id taken
# from internal data, so it stays masked.
# ---------------------------------------------------------------------------


class SchemaError(Exception):
    """The one base every caller-facing exception on this surface descends
    from, so a catch site dispatches on a base class rather than an
    enumerated list of subclasses. That list drifted out of sync with its
    raiser three separate times inside build phase 4.2 alone.

    Declares itself caller-safe (F-4.3-A-12's marker). That is defensible
    only while every message raised through it is a fixed literal. Adding a
    message that interpolates anything internal withdraws that guarantee,
    so change the marker if that ever happens.
    """

    __graphql_public__ = True


class InvalidAskInput(GraphQLError, SchemaError):
    # Publishes code INVALID_ASK_INPUT (derived from this class name by
    # security._error_code_for; the name is the wire contract, as it is for
    # every error class on this surface).
    #
    # WHY IT SUBCLASSES `GraphQLError` AND NOT ONLY `SchemaError`, which is
    # the whole mechanism of the F-4.3-A-16 / J-10 fix and is not obvious:
    # this error is raised from a SCALAR's `parse_value`, during input
    # coercion, before any resolver runs. graphql-core keeps a raised
    # `GraphQLError` as the direct `original_error` of the error it reports
    # (`coerce_input_value`'s `except GraphQLError` branch); a raised plain
    # exception instead gets wrapped in an intermediate `GraphQLError`, and
    # THAT wrapper, not the raised class, becomes what `security.py`'s
    # allowlist inspects. A plain exception with the marker on it would
    # therefore still be masked. Verified by probe against the real
    # extension stack, not assumed.
    #
    # Both entry paths are covered and both were measured:
    #   - as a query VARIABLE, graphql-core rebuilds the error with this
    #     instance as `original_error`, so `security._should_mask_error`
    #     finds the marker and attaches `extensions.code` itself;
    #   - as an INLINE LITERAL, the raised error is reported as-is with no
    #     `original_error` at all, which `_should_mask_error` already
    #     declines to mask, and the `extensions` set at construction survive.
    # Setting the code explicitly at every raise is what makes the two paths
    # publish the identical code rather than one of them publishing none.
    pass


# ---------------------------------------------------------------------------
# Bounds. Declared as named module constants per production-standards.md's
# multi-agent pipeline gate ("every string field bounded and every list
# capped"). GraphQL's own schema language has no maxLength/maxItems
# constraint to attach to a field (unlike JSONSchema), so these constants
# are what fold.py actually enforces at construction time; this module only
# names the numbers once so fold.py never invents its own.
# ---------------------------------------------------------------------------

# Mirrors adapters/mcp/server.py's _MAX_ANSWER_LENGTH (Section 13.2's
# locked value for the sibling non-streaming surface). Kept as this
# surface's own constant rather than imported, per tracker/phase_4.3.md's
# "two duplications accepted" note: the bounds constants are surface-local,
# matching how MCP and the CLI each hold their own.
MAX_ANSWER_LENGTH = 8000

# Mirrors adapters/mcp/server.py's _MAX_CITATIONS and adapters/web_sse/
# app.py's _MAX_CITATIONS_PER_RUN. Same value, same reasoning, held locally
# for the same surface-local-constants reason above.
MAX_CITATIONS = 50

# This surface's own bound, since neither REST nor MCP carries a Disclosures
# type: caps how many distinct disclosure sentences one AskResult/RunResult
# can accumulate (a truncated answer, an over-cap citation list, and a
# fatal-error disclosure are the three that exist today), so a future
# disclosure source cannot make this field unbounded.
MAX_DISCLOSURE_NOTES = 10

# Mirrors TrustSignalPayload.message's own max_length (contracts/events.py).
# A disclosure note is folded into trust_signal.message downstream in
# fold.py, so a single note must fit inside that field's own bound.
MAX_DISCLOSURE_NOTE_LENGTH = 500

# ---------------------------------------------------------------------------
# Citation: CitationPayload's fourteen fields, field for field.
# ---------------------------------------------------------------------------

_SOURCE_URL_PATTERN = re.compile(NCBI_SOURCE_URL_PATTERN)


@strawberry.type
class Citation:
    citation_id: str
    display_index: int
    source: str
    source_id: str
    source_url: str
    layer: str
    field: str
    claim_text: str
    evidence_kind: str
    assertion_confidence: str
    population_ancestry_context: str | None
    license: str
    snapshot_date: str | None
    entity_name: str | None

    @classmethod
    def from_payload(cls, payload: CitationPayload) -> Citation:
        """Build a `Citation` from a `CitationPayload`, re-validating
        `source_url` against `NCBI_SOURCE_URL_PATTERN` rather than trusting
        that the payload was built through ordinary Pydantic construction.

        `CitationPayload.model_copy(update=...)` bypasses field validation
        entirely; this is Pydantic's own documented behavior, not a bug in
        this codebase. The phase 4.3 premise gate's
        `test_an_off_host_source_url_can_never_be_returned` arm constructs
        exactly such a payload (`_citation(1).model_copy(update={"source_
        url": hostile})`) to prove this method does not trust a `Citation
        Payload` instance merely because the caller already holds one.

        Re-runs the WHOLE payload through `CitationPayload.model_validate`
        as a second, independent check (every `max_length` and every
        `pattern` constraint on the model, not `source_url` alone), the
        same "applied twice" belt-and-suspenders pattern
        `adapters/mcp/server.py`'s own citation cap already uses.

        Raises:
            InvalidCitationPayloadError: `source_url` fails the host-pinned,
                end-anchored pattern, or any other field fails
                re-validation.
        """
        if not _SOURCE_URL_PATTERN.fullmatch(payload.source_url):
            raise InvalidCitationPayloadError(
                f"citation {payload.citation_id!r} carries a source_url "
                "that fails the host-pinned NCBI_SOURCE_URL_PATTERN; "
                "refusing to construct a Citation from it"
            )
        try:
            validated = CitationPayload.model_validate(payload.model_dump())
        except ValueError as exc:
            # The caught exception is deliberately NOT interpolated. A
            # Pydantic `ValidationError`'s string embeds `input_value`, so
            # this message would carry the rejected field's actual content
            # onward (F-4.3-A-12). The `from exc` chain keeps the detail for
            # a server-side log without putting it in the message.
            raise InvalidCitationPayloadError(
                f"citation {payload.citation_id!r} failed re-validation "
                "against CitationPayload"
            ) from exc
        return cls(
            citation_id=validated.citation_id,
            display_index=validated.display_index,
            source=validated.source,
            source_id=validated.source_id,
            source_url=validated.source_url,
            layer=validated.layer,
            field=validated.field,
            claim_text=validated.claim_text,
            evidence_kind=validated.evidence_kind,
            assertion_confidence=validated.assertion_confidence,
            population_ancestry_context=validated.population_ancestry_context,
            license=validated.license,
            snapshot_date=validated.snapshot_date,
            entity_name=validated.entity_name,
        )


# ---------------------------------------------------------------------------
# TrustSignal: TrustSignalPayload's eight fields, field for field.
# ---------------------------------------------------------------------------


@strawberry.type
class TrustSignal:
    outcome: str
    risk_tier: str
    grounded: bool
    triangulated: bool | None
    citation_id: str | None
    scope: str | None
    message: str | None
    fallback_link: str | None

    @classmethod
    def from_payload(cls, payload: TrustSignalPayload) -> TrustSignal:
        """Build a `TrustSignal` from a `TrustSignalPayload`, re-running it
        through `TrustSignalPayload.model_validate` first (defense in
        depth, the same "applied twice" pattern `Citation.from_payload`
        uses; every value fold.py passes here is already bounded before
        this call, so this never rejects a real fold output, only a
        payload that reached this method some other way).
        """
        validated = TrustSignalPayload.model_validate(payload.model_dump())
        return cls(
            outcome=validated.outcome,
            risk_tier=validated.risk_tier,
            grounded=validated.grounded,
            triangulated=validated.triangulated,
            citation_id=validated.citation_id,
            scope=validated.scope,
            message=validated.message,
            fallback_link=validated.fallback_link,
        )


# ---------------------------------------------------------------------------
# Disclosures: this surface's own type. GraphQL has no response-header
# channel, so the two facts REST discloses as X-Citations-Export-Truncated
# and X-Run-Cancelled, plus the answer/citation truncation disclosures MCP
# folds into trust_signal.message, all become explicit fields here instead.
# ---------------------------------------------------------------------------


@strawberry.type
class Disclosures:
    answer_truncated: bool
    citations_omitted: int
    # F-R5-07, a CRITICAL found at the fifth review round. "This run died
    # before finishing" was carried ONLY as a note, and `_cap_notes` keeps
    # just the first `MAX_DISCLOSURE_NOTES`, so on a run with enough other
    # disclosures the fatal note was evicted and the fact survived NOWHERE.
    # The caller then saw an answer, citations, and an `outcome`/`riskTier`
    # combination reachable on a perfectly healthy run, with nothing
    # anywhere saying the run had failed. That is the worst possible
    # instance of this surface's own premise failing: not a shortened
    # disclosure, a deleted one.
    #
    # A structured field rather than a reordering, and the distinction is
    # the point. Reordering would make the note survive TODAY's cap; a
    # field cannot be evicted by any future cap, ordering change, or new
    # disclosure source, because it does not live in the capped list at
    # all. The note is still emitted for a human reader; this is what a
    # machine reads, and it is the one disclosure that must never be
    # droppable.
    run_failed: bool
    notes: list[str]


# ---------------------------------------------------------------------------
# The four operation-root result types and the one input type, per
# tracker/phase_4.3.md's locked operation set.
# ---------------------------------------------------------------------------


@strawberry.type
class AskResult:
    run_id: str
    persona_name: str
    answer: str
    trust_signal: TrustSignal
    citations: list[Citation]
    disclosures: Disclosures


@strawberry.type
class RunResult:
    run_id: str
    finished: bool
    answer: str
    trust_signal: TrustSignal
    citations: list[Citation]
    disclosures: Disclosures


# `disclosures` is REQUIRED, with no default, and that is the point (judge
# J-06, premise clause C5). This export used to carry `export_truncated`
# alone, a bare boolean that says SOMETHING was dropped and never why, so a
# citation dropped for failing validation was indistinguishable from one
# dropped at the 50-citation cap, and a caller reading a short export could
# not tell a data-quality problem from a volume one. A defaulted field would
# have been worse than no field: every existing construction site would keep
# compiling while reporting "nothing to disclose" about an export that had
# just dropped something. Required means a construction site has to say what
# it dropped, checked by the compiler rather than by review.
@strawberry.type
class CitationsExport:
    run_id: str
    export_truncated: bool
    run_cancelled: bool
    citations: list[Citation]
    disclosures: Disclosures


# `stopped` reports whether THAT CALL actually cancelled a run that was
# still in flight, not whether the call was accepted (F-4.3-A-20). A second
# stop of the same run, or a stop of a run that already finished, is still a
# success rather than an error (the mutation is idempotent) and reports
# `stopped: false`, which is what `citations.runCancelled` on this same
# surface would also say about that run.
@strawberry.type
class StopRunResult:
    run_id: str
    stopped: bool


# contracts.query.Query.audience_depth's three literal values, restated as
# a real Strawberry enum for AskInput. This is the one field tracker/
# phase_4.3.md names explicitly as needing enum treatment: it is an INPUT
# field, so a real GraphQL enum rejects an out-of-set value before it ever
# reaches this surface's core, the same protection Query's own Pydantic
# Literal already gives every other surface.
@strawberry.enum
class AudienceDepth(enum.Enum):
    CLINICAL_BRIEF = "clinical_brief"
    RESEARCHER = "researcher"
    DEEP_TECHNICAL = "deep_technical"


# contracts.query.Query.audience_depth's own default, restated here so
# schema.py's `ask` resolver has one place to read it from rather than
# hardcoding the string a second time.
DEFAULT_AUDIENCE_DEPTH = "researcher"


def resolve_audience_depth(value: AudienceDepth | None) -> str:
    """Map an optional `AudienceDepth` enum value to the plain literal
    string `contracts.query.Query.audience_depth` expects, defaulting to
    `DEFAULT_AUDIENCE_DEPTH` when the caller omitted it (AskInput's own
    field is optional, matching Query's own default-carrying field).
    """
    return value.value if value is not None else DEFAULT_AUDIENCE_DEPTH


# ---------------------------------------------------------------------------
# AskInput's INPUT bounds (F-4.3-A-16, J-10).
#
# Until this section existed, `AskInput` declared no bound at all: `text` and
# `session_id` were bare `str`, the real bounds lived one layer inward on
# `contracts.query.Query`, and a violating value therefore reached the `ask`
# resolver, raised a Pydantic `ValidationError` there, and was masked into
# "This request could not be completed due to an internal error." with no
# code. Four entirely caller-fixable mistakes (an over-long question, an
# empty one, a whitespace-only one, an over-long sessionId) were all reported
# as a server fault, so a well-behaved client retries forever on input that
# can never succeed. That breaks production-standards.md's retry-safety gate
# ("an error must say what to do next"), and it made this surface strictly
# worse than the REST surface it mirrors, which answers 422 naming the field.
#
# EVERY NUMBER BELOW IS READ OFF `contracts.query.Query` AT IMPORT TIME
# rather than restated, which is the opposite of the surface-local-constants
# choice the OUTPUT bounds above make, deliberately. An output cap is this
# surface's own policy and may legitimately differ per surface. An input
# bound is not a policy: it is the same contract the core will enforce a
# moment later, and the only failure mode that matters is the two disagreeing
# (a GraphQL layer that accepts 3000 characters the core then rejects is
# exactly the masked-internal-error bug this section closes, reintroduced).
# Reading them from the model makes that disagreement unrepresentable, and a
# bound that disappears from the model is an import-time crash rather than a
# silently unbounded field.
# ---------------------------------------------------------------------------


def _bound_from_core_query(field_name: str, attribute: str) -> int:
    """Read one length bound off `contracts.query.Query`'s own field
    metadata (`annotated_types.MinLen` / `MaxLen`, which Pydantic stores
    there for a `Field(min_length=..., max_length=...)`).

    Duck-typed on the attribute name rather than importing
    `annotated_types` so this module gains no new dependency, direct or
    transitive, for a two-line lookup.

    Raises:
        RuntimeError: the named bound is absent from the core model, which
            means the core stopped enforcing it and this surface must not
            silently keep publishing a bound nobody else holds.
    """
    for item in CoreQuery.model_fields[field_name].metadata:
        value = getattr(item, attribute, None)
        if value is not None:
            return int(value)
    raise RuntimeError(
        f"contracts.query.Query.{field_name} declares no {attribute}, so this "
        "surface cannot mirror it; the two would drift"
    )


ASK_TEXT_MIN_LENGTH = _bound_from_core_query("text", "min_length")
ASK_TEXT_MAX_LENGTH = _bound_from_core_query("text", "max_length")
ASK_SESSION_ID_MAX_LENGTH = _bound_from_core_query("session_id", "max_length")

# The wire code every `InvalidAskInput` publishes. Pinned as a literal here
# and cross-checked against `security._error_code_for` by a test rather than
# imported, so this module gains no import edge to `security.py` (which
# imports nothing from here today, and the one-directional edge is worth
# keeping).
ASK_INPUT_ERROR_CODE = "INVALID_ASK_INPUT"

# Every message is a FIXED module-level literal, assembled once at import
# time from this module's own constants and never from a caught exception, a
# caller value, a host, or any runtime state (F-4.3-A-12). The numbers they
# quote are the caller's own published input bounds, which is precisely what
# an actionable input error has to say; that is the opposite of schema.py's
# concurrency-cap message, which deliberately omits the internal cap value.
_TEXT_NOT_A_STRING_MESSAGE = (
    "ask input field 'text' must be a string; send the question as a GraphQL "
    "String and retry"
)
_TEXT_BLANK_MESSAGE = (
    "ask input field 'text' must contain at least one non-whitespace "
    "character; send a question and retry"
)
_TEXT_TOO_LONG_MESSAGE = (
    "ask input field 'text' must be at most "
    f"{ASK_TEXT_MAX_LENGTH} characters; shorten the question and retry"
)
_SESSION_ID_NOT_A_STRING_MESSAGE = (
    "ask input field 'sessionId' must be a string; send it as a GraphQL "
    "String and retry"
)
_SESSION_ID_TOO_LONG_MESSAGE = (
    "ask input field 'sessionId' must be at most "
    f"{ASK_SESSION_ID_MAX_LENGTH} characters; shorten it and retry"
)

# The resolver-side half of the fix, keyed by the CORE model's field name.
# `schema.py` builds `contracts.query.Query` inside the `ask` resolver from
# fields this surface does not all own (`trace_id` and `user_id` are
# server-supplied), so a `ValidationError` can still be raised there even
# with both scalars in place. schema.py selects a message from this table by
# the offending field's `loc`, a structural token, and re-raises; a failure
# on any field NOT in this table is a server fault and stays masked, because
# telling a caller to fix input they never sent would be a second wrong
# error message rather than a fix for the first.
#
# Selecting a fixed message by a structural token off an exception is the
# same shape schema.py's own `_CONCURRENCY_CAP_MESSAGES_BY_BOUND` already
# uses with `exc.bound`: the table is the message source, the exception only
# picks a key.
ASK_INPUT_MESSAGES_BY_CORE_FIELD: dict[str, str] = {
    "text": (
        "ask input field 'text' must be a non-whitespace string of "
        f"{ASK_TEXT_MIN_LENGTH} to {ASK_TEXT_MAX_LENGTH} characters; correct "
        "it and retry"
    ),
    "session_id": _SESSION_ID_TOO_LONG_MESSAGE,
    "audience_depth": (
        "ask input field 'audienceDepth' must be one of the schema's declared "
        "AudienceDepth values; correct it and retry"
    ),
}


def _refuse(message: str) -> NoReturn:
    raise InvalidAskInput(message, extensions={"code": ASK_INPUT_ERROR_CODE})


def _parse_ask_text(value: Any) -> str:
    # A custom scalar does its OWN type check: graphql-core hands
    # `parse_value` whatever the variable held, having applied no String
    # coercion of its own once the field's type is this scalar.
    if not isinstance(value, str):
        _refuse(_TEXT_NOT_A_STRING_MESSAGE)
    if len(value) > ASK_TEXT_MAX_LENGTH:
        _refuse(_TEXT_TOO_LONG_MESSAGE)
    # Mirrors BOTH of the core's emptiness rules in one check: `min_length=1`
    # and `Query._reject_whitespace_only_text`. Refuses rather than strips,
    # for the reason that validator states: a boundary validator accepts or
    # refuses, it never edits the user's question before the guardrail sees
    # it.
    if len(value) < ASK_TEXT_MIN_LENGTH or not value.strip():
        _refuse(_TEXT_BLANK_MESSAGE)
    return value


def _parse_ask_session_id(value: Any) -> str:
    if not isinstance(value, str):
        _refuse(_SESSION_ID_NOT_A_STRING_MESSAGE)
    if len(value) > ASK_SESSION_ID_MAX_LENGTH:
        _refuse(_SESSION_ID_TOO_LONG_MESSAGE)
    # No minimum: `contracts.query.Query.session_id` declares `max_length`
    # only. A bound this surface invented would be a bound no other surface
    # enforces, which is the drift this whole section exists to prevent.
    return value


# Input-only scalars, so `serialize` is unreachable in practice; it is the
# identity rather than something that raises, because a scalar that explodes
# on an unexpected call is a worse failure than one that passes the value
# through. No `description=` on either: Strawberry prints a description into
# the SDL, and this module's schema-print discipline (see the module
# docstring) keeps every explanation in `#` comments.
AskText = strawberry.scalar(
    NewType("AskText", str),
    serialize=lambda value: value,
    parse_value=_parse_ask_text,
)

AskSessionId = strawberry.scalar(
    NewType("AskSessionId", str),
    serialize=lambda value: value,
    parse_value=_parse_ask_session_id,
)


@strawberry.input
class AskInput:
    text: AskText
    session_id: AskSessionId
    audience_depth: AudienceDepth | None = None
