"""The row shape capture assembles and the writer persists (Section 15).

Depends on:
    - system_03_search_agent.contracts.events (CitationPayload's field set)

Reads:
    - Nothing. This module is types only.

Writes:
    - Nothing.

## Why this type exists rather than a dict

It is the seam between the two halves of build phase 4.6's capture path.
`feedback/capture.py` builds one of these from a finished run and touches no
database; `feedback/writer.py` persists one and reads no events. Fixing the
shape here is what lets the two be written independently without either one
guessing at the other's field names.

It is also the one place the eight Decision G fields are named together, so
"is every field populated" is a question that can be asked of a type rather
than of a table.

## What it is NOT

Not an ORM model. `data/models.py`'s `Interaction` is the table, and it
stays the only thing that knows about SQLAlchemy. A capture path that
imported the ORM to build a payload would drag a database dependency into a
pure function, and the assembler's whole value is that it can be tested
without one.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from system_03_search_agent.contracts.events import CitationPayload

#: Section 15's `query_class` check constraint, restated as a type so an
#: assembler cannot produce a value the table will reject at insert time.
#: A CHECK violation on a background write is invisible: the row is simply
#: never there, which is F-2.0-04's failure mode arriving by a new route.
QueryClass = Literal["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"]

#: Section 8's four trust outcomes, and the same constraint reasoning.
TrustSignal = Literal["answer", "flag", "ask", "refuse"]

#: The playbook's outcome model, computed deterministically per Section 15.
RubricOutcome = Literal["pass", "fail", "abstain"]


def _bound_each_item(values: list[str], *, field: str, limit: int) -> list[str]:
    """Reject any item in a list of strings longer than `limit`.

    The identical helper `contracts.query._bound_each_item` defines, copied
    rather than imported: that function is private to its own module (a
    single-underscore name, not part of `contracts.query`'s public surface),
    and this module already keeps its cross-module dependencies to
    `contracts.events` per its own docstring. The two are one line of logic
    each and drift-free by inspection; if a third module ever needs this,
    that is the signal to promote it to a shared, public helper instead of
    a third private copy.
    """
    for item in values:
        if len(item) > limit:
            raise ValueError(
                f"each {field} is capped at {limit} characters, got {len(item)}"
            )
    return values


class _NormalizedEntityShape(BaseModel):
    """Bounds one `InteractionRow.normalized_entities` entry (F-4.6-11).

    Not stored anywhere; used only inside `InteractionRow`'s own validator
    to check and re-serialize each entry. Mirrors exactly what
    `feedback.capture._normalized_entities_from` builds, field for field, so
    this can never reject a real capture output:

    - `surface_form` is `entity.text` off `contracts.events.ResolvedEntity`
      verbatim, already bounded to `max_length=200` there and validated when
      the `plan` event carrying it was constructed
      (`Event._payload_matches_declared_type`). Matched here, not widened.
    - `curie` is `entity.curie` off the same model, already bounded to
      `max_length=128` there. Matched here.
    - `entity_type` is the literal string `"Unknown"` (7 characters) every
      row carries today, per `_normalized_entities_from`'s own docstring:
      the event contract carries no entity type, so nothing derives a real
      one yet. Bounded at 50, matching `contracts.query.ResolvedEntity.
      entity_type`, the one place in this codebase a *real* entity type
      already has a declared bound, so this field has headroom the day
      build phase 4.7 (F-2.0-15) starts populating it for real instead of
      widening blind.
    - `resolution_confidence` is `entity.confidence`, already bounded to
      `[0.0, 1.0]` on `ResolvedEntity`. Matched here.
    """

    model_config = ConfigDict(extra="forbid")

    surface_form: str = Field(..., max_length=200)
    curie: str = Field(..., max_length=128)
    entity_type: str = Field(..., max_length=50)
    resolution_confidence: float = Field(..., ge=0.0, le=1.0)


class _RouteShape(BaseModel):
    """Bounds `InteractionRow.route` (F-4.6-11).

    Not stored anywhere; used only inside `InteractionRow`'s own validator.
    `feedback.capture._route_from` builds exactly these three keys from
    three closed, small vocabularies, deduplicated and sorted before
    `InteractionRow` ever sees them, so a real row can never approach these
    bounds:

    - `layers`: `contracts.events.Layer`, a 3-member `Literal`, longest
      member `"layer_3_enrichment"` (18 characters).
    - `tools`: `contracts.events.ToolName`, a 7-member `Literal`, longest
      member `"clinicaltrials_search"` (21 characters).
    - `model_tiers`: `contracts.events.CostPayload.model_tier`, a 3-member
      `Literal` (`"guard"`, `"plan"`, `"synth"`), longest 5 characters.

    List caps are double each vocabulary's real member count (6, 14, 6) so
    an eighth tool or a fourth tier does not need a matching edit here to
    avoid becoming an unbounded-list defect of its own; the per-item cap of
    32 characters is real headroom over the longest real value today (21).
    """

    model_config = ConfigDict(extra="forbid")

    layers: list[str] = Field(default_factory=list, max_length=6)
    tools: list[str] = Field(default_factory=list, max_length=14)
    model_tiers: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("layers", "tools", "model_tiers")
    @classmethod
    def _bound_each_route_value(cls, value: list[str]) -> list[str]:
        return _bound_each_item(value, field="route entry", limit=32)


class InteractionRow(BaseModel):
    """One `interactions` row, assembled and not yet written.

    Every field maps to a column in Section 15's table. `id` and `created_at`
    are deliberately absent: both carry server defaults, and a client-chosen
    timestamp on a row whose whole purpose is retention and clustering is a
    value that can be wrong.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity. `trace_id` is server-minted at the Guardrail step (T-4.6-02)
    # and is the UNIQUE key the idempotent insert conflicts on.
    trace_id: str = Field(..., min_length=1, max_length=64)
    #: The account behind the principal, or None for a guest. NEVER the
    #: ownership key: it is NULL for every guest, so a check that read it
    #: would make all guests one principal (F-4.5-A-02).
    user_id: uuid.UUID | None = None
    #: `session_row_key(session_id, owner_id=...)` and nothing else. The
    #: owner-scoped uuid5 `core/session_memory` already uses, so capture and
    #: memory agree about which row a conversation is.
    session_id: uuid.UUID | None = None
    #: The exact namespaced principal (`user:<uuid>` or `guest:<uuid>`)
    #: capture computed this row for (F-4.6-01, alembic 0008). Required: the
    #: assembler always has a valid `owner_id` in hand by the time it builds
    #: a row, because `session_row_key` above it already raised
    #: `CallerIdentityRequired` on anything else, so a row with no owner_id
    #: would mean the assembler silently swallowed that guarantee rather
    #: than propagating it. `write_feedback` compares this field directly
    #: against a caller's own `owner_id`; it is the fact the check now
    #: reads, replacing the two-branch proxy check (`user_id`, then a
    #: session-memory envelope) the previous shape needed. Bounded the same
    #: as `Query.owner_id` (`max_length=128`), since this is that exact
    #: value, stored rather than re-derived.
    owner_id: str = Field(..., min_length=1, max_length=128)

    # Decision G's eight fields.
    query_text: str = Field(..., min_length=1, max_length=2000)
    #: Each entry bounded per-field by `_bound_each_normalized_entity` below
    #: (F-4.6-11), not only the list itself. The list-level `max_length=20`
    #: mirrors `feedback.capture._MAX_NORMALIZED_ENTITIES`, which already
    #: truncates before this model is ever constructed.
    normalized_entities: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    query_class: QueryClass
    #: `{layers, tools, model_tiers}`, bounded by `_bound_route` below
    #: (F-4.6-11) rather than left as an open dict.
    route: dict[str, Any] = Field(default_factory=dict)
    trust_signal: TrustSignal
    rubric_outcome: RubricOutcome
    #: NULL on every live row. Section 15 scopes it to offline golden-dataset
    #: replay, which is build phase 5.1, so nothing on the live path may set
    #: it. Present here so the shape is complete rather than so it is filled.
    rubric_score: int | None = Field(None, ge=0, le=16)
    #: Each entry bounded per-field by `_bound_each_citation` below
    #: (F-4.6-11), not only the list itself. The list-level `max_length=50`
    #: mirrors `feedback.capture._MAX_CITATIONS`, which already truncates
    #: before this model is ever constructed.
    citations: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    #: Each item bounded per-string by `_bound_each_coverage_tag` below
    #: (F-4.6-11), not only the list itself.
    coverage_tags: list[str] = Field(default_factory=list, max_length=100)
    #: Null until the user acts. Capture never writes it; `record_feedback`
    #: does, on a row that already exists. Bounded by `_bound_user_feedback`
    #: below (F-4.6-11) when it is not None.
    user_feedback: dict[str, Any] | None = None

    # Implementation columns Section 15 names as required to make the table
    # usable, inherited from the parent session or the harness.
    experiment_id: uuid.UUID | None = None
    experiment_arm: str | None = Field(None, max_length=64)
    cost_usd: float | None = Field(None, ge=0.0)
    latency_ms: int | None = Field(None, ge=0)

    # F-4.6-11: the unbounded-container-inside-a-bounded-one defect, fixed
    # below in five per-field validators. Each one re-validates its entry
    # or value against the SAME model or the SAME field bounds the value
    # was already validated against upstream, before it ever reached this
    # row, rather than against a re-derived copy of those bounds that could
    # drift out of sync with the original. That is deliberate: it means
    # none of the five validators below can ever reject a value real
    # capture output produces, because that value was already proven to
    # satisfy the identical schema at the point the upstream `Event` (or,
    # for `user_feedback`, the `FeedbackPayload` a caller submitted) was
    # constructed. Read each validator's own docstring for its specific
    # upstream source.
    #
    # This is why raising `ValueError` here, rather than truncating with a
    # withheld-field disclosure the way `ncbi_dbsnp` does for genuinely
    # open-ended external content, is the right call for these five fields
    # specifically. None of them is a raw string a caller typed: all five
    # are computed server-side from already-bounded, already-validated
    # typed events (or, for `user_feedback`, an already-validated
    # `FeedbackPayload`), so a caller cannot repeatedly trigger a rejection
    # here at will the way a hostile `query_text` could threaten to defeat
    # a too-tight bound on raw input (F-4.6-A-01's shape). If one of these
    # validators ever does raise on real traffic, that is proof one of the
    # upstream schemas it mirrors has drifted out of sync with it, which is
    # a genuine internal contract violation this row should NOT paper over
    # by manufacturing content the row never actually had. It surfaces the
    # same way any other `InteractionRow` construction failure already
    # does: `core.run._capture_interaction`'s existing catch logs a
    # warning and that one row is dropped (Section 16's "best-effort"
    # already accepts this outcome for a database write failure; this is
    # the identical acceptance one step earlier, for a genuine schema
    # mismatch rather than an outage). No new fallback machinery is added
    # here, because none is needed for a class of failure that cannot be
    # provoked by a caller's own input.

    @field_validator("normalized_entities")
    @classmethod
    def _bound_each_normalized_entity(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Validate each entry against `_NormalizedEntityShape`, unchanged.

        See that model's docstring for the field-by-field derivation. The
        entry this validator runs against is always a dict that
        `feedback.capture._normalized_entities_from` built moments earlier
        from an already-validated `contracts.events.ResolvedEntity`, so
        this can only ever reject real capture output if that function's
        own shape drifted out of sync with `_NormalizedEntityShape`.

        Validates and discards the constructed model rather than returning
        its `model_dump()`, so the value stored is byte-identical to what
        `assemble_interaction` passed in. `_NormalizedEntityShape` has no
        optional field, so the two would be identical here regardless; the
        same validate-then-return-the-original shape is used for `route`,
        `citations` and `user_feedback` below for a reason that DOES matter
        there, where `.model_dump()` would silently introduce a field an
        omitted-optional-key input never carried (see `_bound_each_citation`
        below).
        """
        for item in value:
            _NormalizedEntityShape.model_validate(item)
        return value

    @field_validator("route")
    @classmethod
    def _bound_route(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Validate the whole `route` dict against `_RouteShape`, unchanged.

        See that model's docstring for the field-by-field derivation. The
        value this validator runs against is always the dict
        `feedback.capture._route_from` built moments earlier from three
        closed `Literal` vocabularies, so this can only ever reject real
        capture output if that function's own shape drifted out of sync
        with `_RouteShape`.
        """
        _RouteShape.model_validate(value)
        return value

    @field_validator("citations")
    @classmethod
    def _bound_each_citation(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate each entry against `contracts.events.CitationPayload`.

        Every entry is `event.payload` for a `citation`-type
        `contracts.events.Event`, already validated against this exact
        model at `Event` construction time
        (`Event._payload_matches_declared_type`), before it was ever
        appended to the `events` list `feedback.capture.
        assemble_interaction` reads. Validating against the SAME model,
        imported rather than re-derived as a second copy of its field
        bounds, means this can never drift out of sync with
        `CitationPayload`'s own fields as that model changes, and can never
        reject a real citation: by the time a `citation` event exists in
        `events`, its payload already satisfies this exact schema.

        Returns `value` unchanged rather than each item's `model_dump()`.
        `CitationPayload` carries optional fields (`population_ancestry_
        context`, `snapshot_date`, `entity_name`); a dict that omits one of
        those keys entirely still validates (the model fills the default),
        but `.model_dump()` on the validated model would then ADD that key
        back with an explicit `None`, changing the stored shape from what
        capture actually produced. `test_citations_are_dumped_verbatim`
        (`tests/system_03_search_agent/feedback/test_capture.py`) pins the
        exact opposite property, that a citation is stored exactly as the
        event carried it, so this validator only checks, never rewrites.
        """
        for item in value:
            CitationPayload.model_validate(item)
        return value

    @field_validator("coverage_tags")
    @classmethod
    def _bound_each_coverage_tag(cls, value: list[str]) -> list[str]:
        """Bound each tag `feedback.coverage.coverage_tags_for` produces.

        Today it emits only `concept:<Label>` tags, one per vertex label in
        the closed, 11-member `tools.graph_schema_constants.
        LABEL_CURIE_PREFIXES` dict; the longest is
        `"concept:BiologicalProcess"` (25 characters). The
        `predicate:<edge_type>` half was deleted at F-4.6-04's revert but
        is drawn, when it returns, from the same module's closed 14-member
        `EDGE_LABELS` tuple, whose longest member,
        `"gene_associated_with_condition"`, produces
        `"predicate:gene_associated_with_condition"` (40 characters). 50 is
        real headroom over both, computed rather than guessed
        (`python3 -c` over the literal label lists gave 25 and 40), not a
        round number picked for looking generous.
        """
        return _bound_each_item(value, field="coverage_tag", limit=50)

    @field_validator("user_feedback")
    @classmethod
    def _bound_user_feedback(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Validate against `FeedbackPayload` when feedback is present.

        `feedback.capture.assemble_interaction` always leaves this `None`;
        capture never writes feedback (see the field's own comment above).
        The only real shape this column is ever assigned is
        `FeedbackPayload.model_dump(mode="json")`
        (`feedback.writer.write_feedback`, which writes it directly onto
        the SQLAlchemy `Interaction` row rather than through this Pydantic
        model, so this validator never actually runs on the live feedback
        path today; it exists for any future caller that constructs an
        `InteractionRow` with feedback already attached). Validating
        against the SAME model here, defined later in this file and
        referenced by name rather than by a re-derived copy of its bounds,
        keeps `InteractionRow`'s declared type honest about the one real
        shape this column ever holds.

        Returns `value` unchanged for the identical reason
        `_bound_each_citation` above does: `FeedbackPayload` carries
        optional fields, and re-dumping would add back a key an
        omitted-optional-key input never carried.
        """
        if value is None:
            return None
        FeedbackPayload.model_validate(value)
        return value


#: A citation id is an identifier, not prose. Bounded at the same 64
#: characters `contracts/query.py`'s `MAX_CITATION_ID_LENGTH` already uses
#: for a citation id elsewhere in this codebase (`CompressedFinding.
#: citation_ids`), chosen deliberately rather than borrowed blind:
#: F-4.6-09 (`tracker/phase_4.6.md`) notes that `citation_id` currently
#: receives a display index (`FeedbackSurface.tsx`'s `String(n)`, a small
#: integer) rather than a real citation id, and that gap is NOT closed
#: here. 64 characters comfortably fits either shape, a one- or two-digit
#: index today or a real marker such as a `source_id` once F-4.6-09 is
#: resolved, so this bound does not assume which one is correct.
MAX_CITATION_FLAG_ID_LENGTH = 64

#: Short prose, not a document. The one value the shipped frontend sends
#: today is `CITATION_FLAG_REASON`, "Citation does not support the claim"
#: (36 characters, `FeedbackSurface.tsx`), so this matches
#: `FeedbackPayload.flagged_reason` below, the sibling free-text field this
#: one is closest to in shape and in the same request body.
MAX_CITATION_FLAG_REASON_LENGTH = 200


class FeedbackCitationFlag(BaseModel):
    """One entry in `FeedbackPayload.citation_flags`: which citation, and why.

    Exists for the same reason `CompressedFinding.citation_ids` in
    `contracts/query.py` needed its own per-item validator (F-4.5-J-19): a
    `max_length` on the surrounding list bounds how MANY entries arrive and
    says nothing about how big one entry is, or what keys it carries.
    `citation_flags` used to be a bare `list[dict[str, str]]` with
    `max_length=50` on the list only, so fifty entries of two megabytes
    each, or fifty entries carrying arbitrary keys instead of
    `citation_id`/`reason`, both validated cleanly and were accepted with a
    204 (F-4.6-A-07, the adversary round that found this: 100 MB of caller
    JSON accepted). This model closes both holes: only the two named keys
    are accepted (`extra="forbid"`), and each is bounded on its own.
    """

    model_config = ConfigDict(extra="forbid")

    citation_id: str = Field(..., min_length=1, max_length=MAX_CITATION_FLAG_ID_LENGTH)
    reason: str = Field(..., min_length=1, max_length=MAX_CITATION_FLAG_REASON_LENGTH)


class FeedbackPayload(BaseModel):
    """What a caller may attach to their own row (Section 15, `user_feedback`).

    Section 15 names three fields: `rating`, `comment`, `flagged_reason`.
    `citation_flags` is the fourth, and it is additive rather than a
    redefinition, per `system-design-patterns` pattern 10. It exists because
    build phase 4.8 styled a per-citation "does not support" control and
    named 4.6 as the phase that wires it (`frontend/src/stubs/registry.ts`),
    and because a flag saying WHICH citation failed is worth more to the
    weekly review ritual than a rating saying the answer was bad.
    """

    model_config = ConfigDict(extra="forbid")

    rating: Literal["up", "down"] | None = None
    comment: str | None = Field(None, max_length=2000)
    flagged_reason: str | None = Field(None, max_length=200)
    #: `FeedbackCitationFlag` per entry (`citation_id`, `reason`), each
    #: bounded on its own, not just the list. Worst case with every bound
    #: maxed: 50 entries * (64 + 200) = 13,200 characters, plus the 2000 of
    #: `comment` and the 200 of `flagged_reason`, 15,400 characters of
    #: content in total (roughly 15 KB, more under UTF-8 multibyte input,
    #: plus a few KB of JSON structural overhead for keys and punctuation).
    #: That is small enough on its own that no additional total-payload
    #: guard was added at the endpoint on top of these per-field bounds;
    #: see the endpoint-level comment in `adapters/web_sse/app.py` for the
    #: reasoning written out in full.
    citation_flags: list[FeedbackCitationFlag] = Field(
        default_factory=list, max_length=50
    )


class FeedbackOwnershipError(Exception):
    """A caller tried to attach feedback to a row that is not theirs.

    Raised rather than returned, and never softened into a no-op. A surface
    that refuses loudly and writes anyway passes a status-code assertion,
    which is why the premise gate asserts on the stored value instead.
    """


class InteractionNotFound(Exception):
    """No row exists yet for this `trace_id`.

    A real and expected state, not a defect: capture runs as a background
    task after the `done` event, so feedback submitted the instant an answer
    finishes can genuinely arrive first. The surface decides what to do about
    it; this type exists so the surface can tell that case apart from a
    caller naming a run that never existed.
    """
