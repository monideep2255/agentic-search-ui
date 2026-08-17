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

Reads:
    - Nothing directly.

Writes:
    - Nothing directly.
"""

from __future__ import annotations

import enum
import re

import strawberry

from system_03_search_agent.contracts.events import (
    NCBI_SOURCE_URL_PATTERN,
    CitationPayload,
    TrustSignalPayload,
)

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


@strawberry.type
class CitationsExport:
    run_id: str
    export_truncated: bool
    run_cancelled: bool
    citations: list[Citation]


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


@strawberry.input
class AskInput:
    text: str
    session_id: str
    audience_depth: AudienceDepth | None = None
