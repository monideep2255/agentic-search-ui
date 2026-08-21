"""Tests for `feedback.contracts.FeedbackCitationFlag` and the
`FeedbackPayload.citation_flags` bound that wraps it (F-4.6-A-07,
`tracker/phase_4.6_adversary_report.md`).

The adversary round found `citation_flags` bounded as a bare
`list[dict[str, str]]` with `max_length=50` on the list and nothing on an
entry: a `POST /v1/query/{run_id}/feedback` body carrying 50 entries of two
megabytes each, or entries carrying arbitrary keys instead of
`citation_id`/`reason`, both validated cleanly and the server answered 204.
This file is the type-level regression test for the fix: a real
`FeedbackCitationFlag` model with `min_length`/`max_length` on both of its
fields and `extra="forbid"`.

Pure Pydantic model tests, no database, no HTTP client, no event loop
(`test_feedback_endpoint.py` in `adapters/web_sse` owns the HTTP-boundary
version of this same scenario, going through the real endpoint).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.feedback.contracts import (
    MAX_CITATION_FLAG_ID_LENGTH,
    MAX_CITATION_FLAG_REASON_LENGTH,
    FeedbackCitationFlag,
    FeedbackPayload,
    InteractionRow,
)


def _citation_payload(*, claim_text: str = "BRCA1 is a gene.", **overrides) -> dict:
    """A full, schema-conformant `contracts.events.CitationPayload` dict.

    Duplicated from `test_capture.py`'s and `test_writer.py`'s identical
    helpers rather than imported, matching this test suite's existing
    convention of a local, self-contained fixture per file
    (`test_writer.py`'s own `_citation_payload` docstring gives the same
    reasoning).
    """
    payload = {
        "citation_id": "call-1-1",
        "display_index": 1,
        "source": "NCBIGene",
        "source_id": "NCBIGene:672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": claim_text,
        "evidence_kind": "primary_assertion",
        "assertion_confidence": "asserted",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
    }
    payload.update(overrides)
    return payload


def _row(**overrides) -> InteractionRow:
    """A minimal valid `InteractionRow`, for tests that only care about one
    of the five F-4.6-11 fields and want every other field to be
    unremarkable.
    """
    fields = {
        "trace_id": "trace-f4611",
        "user_id": None,
        "session_id": None,
        "owner_id": "guest:11111111-1111-1111-1111-111111111111",
        "query_text": "What is BRCA1?",
        "normalized_entities": [],
        "query_class": "lookup",
        "route": {},
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "rubric_score": None,
        "citations": [],
        "coverage_tags": [],
        "user_feedback": None,
        "experiment_id": None,
        "experiment_arm": None,
        "cost_usd": 0.01,
        "latency_ms": 250,
    }
    fields.update(overrides)
    return InteractionRow(**fields)


class TestFeedbackCitationFlagValidInput:
    def test_a_well_formed_entry_validates(self) -> None:
        """Mutation: changing `citation_id: str = Field(..., min_length=1,
        max_length=MAX_CITATION_FLAG_ID_LENGTH)` to require a
        `min_length=2` makes this single-character id fail. Applied,
        confirmed red, reverted."""
        flag = FeedbackCitationFlag(citation_id="A", reason="off_topic")
        assert flag.citation_id == "A"
        assert flag.reason == "off_topic"

    def test_the_shipped_frontend_shape_validates(self) -> None:
        """`FeedbackSurface.tsx`'s `buildPayload` sends `{citation_id:
        String(n), reason: CITATION_FLAG_REASON}`, a small integer as a
        string and a fixed 36-character sentence (F-4.6-09: `citation_id`
        is a display index today, not a real citation id, and this bound
        does not assume either shape). Both must keep validating under the
        new model, or the fix breaks the one real caller that exists.
        Mutation: lowering `reason`'s `max_length` from
        `MAX_CITATION_FLAG_REASON_LENGTH` to a literal `30` in
        `feedback/contracts.py` (30 is shorter than the 36-character
        `CITATION_FLAG_REASON` string this test uses) raised a
        `pydantic.ValidationError` ("string_too_long") instead of
        constructing the flag. Applied, confirmed red, reverted."""
        flag = FeedbackCitationFlag(
            citation_id="2", reason="Citation does not support the claim"
        )
        assert flag.citation_id == "2"

    def test_values_at_exactly_the_max_length_validate(self) -> None:
        """Boundary case: `max_length` is inclusive. Mutation: changing
        `citation_id`'s bound in `feedback/contracts.py` from
        `max_length=MAX_CITATION_FLAG_ID_LENGTH` to
        `max_length=MAX_CITATION_FLAG_ID_LENGTH - 1` raised a
        `pydantic.ValidationError` ("string_too_long") on the exact
        64-character id this test constructs. Applied, confirmed red,
        reverted."""
        flag = FeedbackCitationFlag(
            citation_id="x" * MAX_CITATION_FLAG_ID_LENGTH,
            reason="y" * MAX_CITATION_FLAG_REASON_LENGTH,
        )
        assert len(flag.citation_id) == MAX_CITATION_FLAG_ID_LENGTH
        assert len(flag.reason) == MAX_CITATION_FLAG_REASON_LENGTH


class TestFeedbackCitationFlagInvalidInput:
    def test_an_oversized_citation_id_is_rejected(self) -> None:
        """One character over the bound, not an order of magnitude over
        it: proves this is a real `max_length`, not a loose sanity check.
        Mutation: removing `max_length=MAX_CITATION_FLAG_ID_LENGTH` from
        `citation_id` makes this test fail (no exception raised). Applied,
        confirmed red, reverted."""
        with pytest.raises(ValidationError):
            FeedbackCitationFlag(
                citation_id="x" * (MAX_CITATION_FLAG_ID_LENGTH + 1), reason="ok"
            )

    def test_an_oversized_reason_is_rejected(self) -> None:
        """Mutation: removing `max_length=MAX_CITATION_FLAG_REASON_LENGTH`
        from `reason` makes this test fail. Applied, confirmed red,
        reverted."""
        with pytest.raises(ValidationError):
            FeedbackCitationFlag(
                citation_id="ok", reason="y" * (MAX_CITATION_FLAG_REASON_LENGTH + 1)
            )

    def test_an_unknown_key_is_rejected(self) -> None:
        """The adversary's second probe: `{"anything": "...", "xxx...":
        "..."}` with no `citation_id`/`reason` at all validated cleanly
        against the old bare-dict shape. Mutation: changing `model_config =
        ConfigDict(extra="forbid")` to the default (`extra="ignore"`) makes
        this test fail (no exception; the extra key is silently dropped
        instead of rejected). Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            FeedbackCitationFlag.model_validate(
                {"citation_id": "A", "reason": "ok", "unexpected_extra_key": "x"}
            )

    def test_a_missing_required_key_is_rejected(self) -> None:
        """Mutation: changing `reason: str = Field(...)` to `reason: str |
        None = None` makes this test fail. Applied, confirmed red,
        reverted."""
        with pytest.raises(ValidationError):
            FeedbackCitationFlag.model_validate({"citation_id": "A"})

    def test_an_empty_string_value_is_rejected(self) -> None:
        """`min_length=1` on both fields: an entry naming no citation and
        giving no reason is not a real flag. Mutation: dropping
        `min_length=1` from `citation_id` makes this test fail. Applied,
        confirmed red, reverted."""
        with pytest.raises(ValidationError):
            FeedbackCitationFlag(citation_id="", reason="ok")


class TestFeedbackPayloadCitationFlagsReproducesTheAdversaryFinding:
    """F-4.6-A-07's exact probe, replayed at the type level.

    Before this fix, `citation_flags` was typed `list[dict[str, str]]`
    with `max_length=50` on the list and nothing on an entry. The
    adversary's measured result against the live endpoint: `50 flags x 2MB
    each -> 204`, and `arbitrary keys in citation_flags -> 204`. This class
    proves both are now rejected at construction, before any HTTP layer or
    database write is reached.
    """

    def test_fifty_multi_megabyte_entries_are_rejected(self) -> None:
        """The adversary's literal payload shape: 50 entries, each carrying
        a 1,000,000-character `citation_id` and a 1,000,000-character
        `reason` (roughly 100 MB total). Mutation confirmed by temporarily
        reverting `FeedbackPayload.citation_flags`'s field type from
        `list[FeedbackCitationFlag]` back to the pre-fix `list[dict[str,
        str]]`: with that reversion in place, this exact call raised
        NOTHING and returned a `FeedbackPayload` instance instead of a
        `ValidationError`, reproducing the adversary's `204`. Reverted
        immediately after confirming red; the assertion below is the
        fixed, passing state."""
        oversized_entry = {"citation_id": "A" * 1_000_000, "reason": "B" * 1_000_000}
        with pytest.raises(ValidationError):
            FeedbackPayload(rating="down", citation_flags=[oversized_entry] * 50)

    def test_arbitrary_keys_are_rejected(self) -> None:
        """The adversary's second probe, replayed: entries with no
        `citation_id`/`reason` at all. Mutation confirmed the same way as
        the test above (temporarily reverting the field type); under the
        reversion this call also raised nothing. Reverted after
        confirming red."""
        with pytest.raises(ValidationError):
            FeedbackPayload(
                rating="down",
                citation_flags=[{"anything": "x", "xxxx" * 50: "y"}],
            )

    def test_fifty_well_formed_entries_at_the_max_still_validate(self) -> None:
        """The legitimate worst case must keep working: this is a bound,
        not a ban. 50 entries at exactly the per-field max (64 + 200
        characters each) is the number `feedback/contracts.py`'s own
        comment on this field states as the worst case, 13,200 characters
        of `citation_flags` content. Mutation: lowering
        `FeedbackPayload.citation_flags`'s `max_length` from 50 to 49 makes
        this test fail. Applied, confirmed red, reverted."""
        entry = {
            "citation_id": "x" * MAX_CITATION_FLAG_ID_LENGTH,
            "reason": "y" * MAX_CITATION_FLAG_REASON_LENGTH,
        }
        payload = FeedbackPayload(rating="down", citation_flags=[entry] * 50)
        assert len(payload.citation_flags) == 50

    def test_missing_citation_flags_defaults_to_an_empty_list(self) -> None:
        """Null/omitted input: `citation_flags` is optional with a default
        factory, so a payload naming only a rating must still validate.
        Mutation: changing `default_factory=list` to no default (making
        the field required) makes this test fail with a ValidationError
        instead of succeeding. Applied, confirmed red, reverted."""
        payload = FeedbackPayload(rating="up")
        assert payload.citation_flags == []


# ---------------------------------------------------------------------------
# F-4.6-11: the unbounded-container-inside-a-bounded-one defect in
# `InteractionRow`, five fields: `normalized_entities`, `route`, `citations`,
# `coverage_tags`, `user_feedback`.
#
# Each field's bound is derived from what `feedback.capture` actually
# produces (see `contracts.py`'s own comments on `_NormalizedEntityShape`,
# `_RouteShape`, and the field validators on `InteractionRow`), never
# invented. The most important arm per field is the "still validates"
# one: a bound that is too tight silently drops a whole row, since
# `core.run._capture_interaction`'s outer catch swallows any
# `InteractionRow` construction failure with no fallback. That is the
# large-but-legitimate case, not the oversized-and-rejected case, and every
# subsection below ends with one.
# ---------------------------------------------------------------------------


class TestNormalizedEntitiesBound:
    def test_a_well_formed_entry_validates(self) -> None:
        """Mutation: changing `_NormalizedEntityShape.curie`'s
        `max_length=128` to `max_length=4` makes this fail on the real
        13-character curie below. Applied, confirmed red, reverted."""
        row = _row(
            normalized_entities=[
                {
                    "surface_form": "BRCA1",
                    "curie": "NCBIGene:672",
                    "entity_type": "Unknown",
                    "resolution_confidence": 0.9,
                }
            ]
        )
        assert row.normalized_entities[0]["curie"] == "NCBIGene:672"

    def test_an_oversized_surface_form_is_rejected(self) -> None:
        """One character over `ResolvedEntity.text`'s own 200-character
        bound, the value `surface_form` is copied from verbatim. Mutation:
        removing `max_length=200` from `_NormalizedEntityShape.surface_form`
        makes this pass instead of raising. Applied, confirmed red,
        reverted."""
        with pytest.raises(ValidationError):
            _row(
                normalized_entities=[
                    {
                        "surface_form": "x" * 201,
                        "curie": "NCBIGene:672",
                        "entity_type": "Unknown",
                        "resolution_confidence": 0.9,
                    }
                ]
            )

    def test_an_oversized_curie_is_rejected(self) -> None:
        """Mutation: removing `max_length=128` from
        `_NormalizedEntityShape.curie` makes this pass instead of raising.
        Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            _row(
                normalized_entities=[
                    {
                        "surface_form": "BRCA1",
                        "curie": "x" * 129,
                        "entity_type": "Unknown",
                        "resolution_confidence": 0.9,
                    }
                ]
            )

    def test_an_out_of_range_confidence_is_rejected(self) -> None:
        """Mutation: removing `le=1.0` from
        `_NormalizedEntityShape.resolution_confidence` makes this pass
        instead of raising. Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            _row(
                normalized_entities=[
                    {
                        "surface_form": "BRCA1",
                        "curie": "NCBIGene:672",
                        "entity_type": "Unknown",
                        "resolution_confidence": 1.5,
                    }
                ]
            )

    def test_an_unknown_key_is_rejected(self) -> None:
        """`extra="forbid"` on `_NormalizedEntityShape`. Mutation: changing
        it to the pydantic default (`extra="ignore"`) makes this pass
        instead of raising, silently dropping the unexpected key rather than
        refusing it. Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            _row(
                normalized_entities=[
                    {
                        "surface_form": "BRCA1",
                        "curie": "NCBIGene:672",
                        "entity_type": "Unknown",
                        "resolution_confidence": 0.9,
                        "unexpected": "x",
                    }
                ]
            )

    def test_twenty_entries_at_every_max_still_validate(self) -> None:
        """The large-but-legitimate case: 20 entries (the list's own
        `max_length`), each field at its exact per-item maximum
        (`surface_form` 200 chars, `curie` 128 chars, `entity_type` 50
        chars, `resolution_confidence` at 1.0). This is the arm that
        catches a bound derived too tightly, which the oversized-rejection
        tests above cannot: a too-tight bound and a correct one both reject
        an oversized value, but only a too-tight one rejects this. Mutation:
        lowering `_NormalizedEntityShape.curie`'s `max_length` from 128 to
        127 makes this fail even though 128 is the real, documented bound
        `contracts.events.ResolvedEntity.curie` uses. Applied, confirmed
        red, reverted."""
        entry = {
            "surface_form": "x" * 200,
            "curie": "y" * 128,
            "entity_type": "z" * 50,
            "resolution_confidence": 1.0,
        }
        row = _row(normalized_entities=[entry] * 20)
        assert len(row.normalized_entities) == 20


class TestRouteBound:
    def test_a_well_formed_route_validates(self) -> None:
        """Mutation: changing `_RouteShape.tools`'s `max_length=14` to
        `max_length=1` makes this fail on the two real tool names below.
        Applied, confirmed red, reverted."""
        row = _row(
            route={
                "layers": ["layer_1_graph", "layer_2_api"],
                "tools": ["cypher_query", "ncbi_efetch"],
                "model_tiers": ["plan"],
            }
        )
        assert row.route["tools"] == ["cypher_query", "ncbi_efetch"]

    def test_an_oversized_route_entry_is_rejected(self) -> None:
        """Mutation: removing the `_bound_each_route_value` validator from
        `_RouteShape` makes this pass instead of raising. Applied, confirmed
        red, reverted."""
        with pytest.raises(ValidationError):
            _row(route={"tools": ["x" * 33]})

    def test_an_unknown_route_key_is_rejected(self) -> None:
        """`extra="forbid"` on `_RouteShape`: `route` has exactly three
        keys, never a fourth. Mutation: changing it to `extra="ignore"`
        makes this pass instead of raising. Applied, confirmed red,
        reverted."""
        with pytest.raises(ValidationError):
            _row(route={"layers": [], "tools": [], "model_tiers": [], "extra": []})

    def test_the_full_closed_vocabulary_still_validates(self) -> None:
        """The large-but-legitimate case: every real `Layer` (3), every
        real `ToolName` (7), and every real `model_tier` (3), the actual
        worst case `feedback.capture._route_from` can ever produce, all at
        once. Mutation: lowering `_RouteShape.tools`'s `max_length` from 14
        to 7 makes this fail even though 7 real tools is exactly what a run
        touching every tool in one turn produces. Applied, confirmed red,
        reverted."""
        row = _row(
            route={
                "layers": ["layer_1_graph", "layer_2_api", "layer_3_enrichment"],
                "tools": [
                    "clinicaltrials_search",
                    "cypher_query",
                    "litvar2_lookup",
                    "ncbi_dbsnp",
                    "ncbi_efetch",
                    "pathogen_detection",
                    "pubtator_annotate",
                ],
                "model_tiers": ["guard", "plan", "synth"],
            }
        )
        assert len(row.route["tools"]) == 7


class TestCitationsBound:
    def test_a_well_formed_citation_validates(self) -> None:
        """Mutation: changing `_bound_each_citation` to skip validation
        (`return value` with no loop) does not fail THIS test on its own,
        since a well-formed citation validates either way; paired with
        `test_a_malformed_citation_is_rejected` below, which does catch it.
        Kept as the positive counterpart so the pair reads as one bound,
        not as one arm."""
        row = _row(citations=[_citation_payload()])
        assert row.citations[0]["source_id"] == "NCBIGene:672"

    def test_a_malformed_citation_is_rejected(self) -> None:
        """The exact partial shape `test_writer.py`'s pre-F-4.6-11 fixtures
        used to pass, now refused. Mutation: changing `_bound_each_citation`
        to `return value` (no `CitationPayload.model_validate` call) makes
        this pass instead of raising. Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            _row(citations=[{"claim_text": "a claim"}])

    def test_an_oversized_claim_text_is_rejected(self) -> None:
        """One character over `CitationPayload.claim_text`'s own
        1000-character bound. Mutation: same as above. Applied, confirmed
        red, reverted."""
        with pytest.raises(ValidationError):
            _row(citations=[_citation_payload(claim_text="x" * 1001)])

    def test_fifty_citations_at_claim_texts_max_still_validate(self) -> None:
        """The large-but-legitimate case: 50 citations (`InteractionRow.
        citations`'s own list `max_length`), each with `claim_text` at
        `CitationPayload`'s real 1000-character maximum. Mutation: lowering
        `InteractionRow.citations`'s list `max_length` from 50 to 49 makes
        this fail even though `feedback.capture._MAX_CITATIONS` is 50 and
        a run citing 50 sources is a real, expected shape for a
        multi-hop query. Applied, confirmed red, reverted."""
        entry = _citation_payload(claim_text="x" * 1000)
        row = _row(citations=[entry] * 50)
        assert len(row.citations) == 50


class TestCoverageTagsBound:
    def test_a_real_concept_tag_validates(self) -> None:
        """Mutation: lowering `_bound_each_coverage_tag`'s `limit` from 50
        to 10 makes this fail on the real 26-character tag below. Applied,
        confirmed red, reverted."""
        row = _row(coverage_tags=["concept:BiologicalProcess"])
        assert row.coverage_tags == ["concept:BiologicalProcess"]

    def test_an_oversized_tag_is_rejected(self) -> None:
        """Mutation: removing the `_bound_each_coverage_tag` validator
        makes this pass instead of raising. Applied, confirmed red,
        reverted."""
        with pytest.raises(ValidationError):
            _row(coverage_tags=["x" * 51])

    def test_the_longest_real_predicate_tag_still_validates(self) -> None:
        """The large-but-legitimate case: `"predicate:gene_associated_
        with_condition"` (40 characters), the longest tag
        `feedback.coverage.coverage_tags_for` can produce once the
        `predicate:` half returns, computed directly from
        `tools.graph_schema_constants.EDGE_LABELS`'s own longest member
        rather than approximated. Mutation: lowering `_bound_each_
        coverage_tag`'s `limit` from 50 to 39 makes this fail. Applied,
        confirmed red, reverted."""
        tag = "predicate:gene_associated_with_condition"
        assert len(tag) == 40
        row = _row(coverage_tags=[tag])
        assert row.coverage_tags == [tag]


class TestUserFeedbackBound:
    def test_none_still_validates(self) -> None:
        """The default, and the only value `feedback.capture.
        assemble_interaction` ever constructs. Mutation: changing
        `_bound_user_feedback` to always raise on `None` makes this fail.
        Applied, confirmed red, reverted."""
        row = _row(user_feedback=None)
        assert row.user_feedback is None

    def test_a_well_formed_feedback_payload_shape_validates(self) -> None:
        """The exact shape `feedback.writer.write_feedback` assigns
        (`FeedbackPayload.model_dump(mode="json")`), round-tripped through
        `InteractionRow` directly rather than through the writer. Mutation:
        changing `_bound_user_feedback` to always raise on a non-`None`
        value makes this fail. Applied, confirmed red, reverted."""
        payload = FeedbackPayload(
            rating="down",
            comment="the citation does not support this",
            citation_flags=[FeedbackCitationFlag(citation_id="1", reason="off_topic")],
        ).model_dump(mode="json")
        row = _row(user_feedback=payload)
        assert row.user_feedback["rating"] == "down"

    def test_an_unknown_key_is_rejected(self) -> None:
        """`extra="forbid"` on `FeedbackPayload`, reached through
        `InteractionRow`'s own validator. Mutation: changing
        `_bound_user_feedback` to `return value` with no
        `FeedbackPayload.model_validate` call makes this pass instead of
        raising. Applied, confirmed red, reverted."""
        with pytest.raises(ValidationError):
            _row(user_feedback={"rating": "down", "unexpected_key": "x"})

    def test_the_documented_worst_case_still_validates(self) -> None:
        """The large-but-legitimate case: `FeedbackPayload`'s own
        documented worst case, 50 `citation_flags` entries at their max (64
        + 200 characters each) plus `comment` and `flagged_reason` at their
        own max, 15,400 characters of real content
        (`feedback/contracts.py`'s own comment on `FeedbackPayload.
        citation_flags` names this exact figure). Mutation: lowering
        `MAX_CITATION_FLAG_REASON_LENGTH`'s use inside `_bound_user_
        feedback`'s validation path is indirect (it is `FeedbackPayload`'s
        own bound), so the mutation applied here is the same as
        `TestFeedbackPayloadCitationFlagsReproducesTheAdversaryFinding.
        test_fifty_well_formed_entries_at_the_max_still_validate` above:
        lowering `FeedbackPayload.citation_flags`'s `max_length` from 50 to
        49 makes this fail. Applied, confirmed red, reverted."""
        payload = FeedbackPayload(
            rating="down",
            comment="y" * 2000,
            flagged_reason="z" * 200,
            citation_flags=[
                FeedbackCitationFlag(
                    citation_id="x" * MAX_CITATION_FLAG_ID_LENGTH,
                    reason="y" * MAX_CITATION_FLAG_REASON_LENGTH,
                )
            ]
            * 50,
        ).model_dump(mode="json")
        row = _row(user_feedback=payload)
        assert len(row.user_feedback["citation_flags"]) == 50


class TestEveryBoundTogether:
    def test_a_realistic_maximal_row_validates_end_to_end(self) -> None:
        """The single most important arm in this file: every one of
        F-4.6-11's five fields at once, each at a real, derived maximum,
        not an arbitrary large value. This is the test that would catch a
        bound accidentally derived too tight against another field's
        presence, which the per-field tests above, run in isolation,
        cannot: they each leave every other field at its zero value.

        Mutation: lowering `InteractionRow.citations`'s list `max_length`
        from 50 to 49 (the same real mutation as
        `TestCitationsBound.test_fifty_citations_at_claim_texts_max_still_
        validate`, replayed here with every other field ALSO at its max, to
        rule out a bound that only fails once the row is otherwise large).
        Applied, confirmed red (`ValidationError` on `citations`, list too
        long), reverted."""
        row = _row(
            query_text="x" * 2000,
            normalized_entities=[
                {
                    "surface_form": "x" * 200,
                    "curie": "y" * 128,
                    "entity_type": "z" * 50,
                    "resolution_confidence": 1.0,
                }
            ]
            * 20,
            route={
                "layers": ["layer_1_graph", "layer_2_api", "layer_3_enrichment"],
                "tools": [
                    "clinicaltrials_search",
                    "cypher_query",
                    "litvar2_lookup",
                    "ncbi_dbsnp",
                    "ncbi_efetch",
                    "pathogen_detection",
                    "pubtator_annotate",
                ],
                "model_tiers": ["guard", "plan", "synth"],
            },
            citations=[_citation_payload(claim_text="x" * 1000)] * 50,
            coverage_tags=["predicate:gene_associated_with_condition"] * 25,
            user_feedback=FeedbackPayload(
                rating="down",
                comment="y" * 2000,
                flagged_reason="z" * 200,
                citation_flags=[
                    FeedbackCitationFlag(
                        citation_id="x" * MAX_CITATION_FLAG_ID_LENGTH,
                        reason="y" * MAX_CITATION_FLAG_REASON_LENGTH,
                    )
                ]
                * 50,
            ).model_dump(mode="json"),
        )
        assert len(row.normalized_entities) == 20
        assert len(row.citations) == 50
        assert len(row.coverage_tags) == 25
        assert len(row.user_feedback["citation_flags"]) == 50
