"""Tests for the Query and RequestContext models (Section 2.1)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from system_03_search_agent.contracts.query import (
    MAX_COMPRESSED_FINDINGS,
    MAX_OPEN_THREADS,
    MAX_RESOLVED_ENTITIES,
    SESSION_MEMORY_TOKEN_BUDGET,
    CompressedFinding,
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)


def _summary(**overrides: object) -> SessionMemorySummary:
    """A minimal valid SessionMemorySummary, overridable per test."""
    base: dict[str, object] = {
        "session_id": "session-1",
        "last_updated": datetime(2026, 8, 20, tzinfo=UTC),
    }
    base.update(overrides)
    return SessionMemorySummary(**base)  # type: ignore[arg-type]


def _query_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "text": "What gene is BRCA1?",
        "session_id": "session-1",
        "trace_id": "trace-1",
    }
    base.update(overrides)
    return base


class TestQueryRequiredFields:
    def test_missing_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(session_id="session-1", trace_id="trace-1")

    def test_missing_session_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(text="hello", trace_id="trace-1")

    def test_missing_trace_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(text="hello", session_id="session-1")

    def test_minimal_construction_succeeds_with_defaults(self) -> None:
        query = Query(**_query_kwargs())
        assert query.user_id is None
        assert query.audience_depth == "researcher"


class TestQueryMaxLength:
    def test_text_at_max_length_succeeds(self) -> None:
        query = Query(**_query_kwargs(text="a" * 2000))
        assert len(query.text) == 2000

    def test_text_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(text="a" * 2001))

    def test_session_id_at_max_length_succeeds(self) -> None:
        query = Query(**_query_kwargs(session_id="s" * 64))
        assert len(query.session_id) == 64

    def test_session_id_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(session_id="s" * 65))

    def test_trace_id_at_max_length_succeeds(self) -> None:
        query = Query(**_query_kwargs(trace_id="t" * 64))
        assert len(query.trace_id) == 64

    def test_trace_id_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(trace_id="t" * 65))

    def test_user_id_at_max_length_succeeds(self) -> None:
        query = Query(**_query_kwargs(user_id="u" * 64))
        assert query.user_id is not None
        assert len(query.user_id) == 64

    def test_user_id_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(user_id="u" * 65))

    def test_no_silent_truncation(self) -> None:
        # A ValidationError, never a truncated string, is the contract.
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(text="a" * 2500))


class TestQueryAudienceDepth:
    @pytest.mark.parametrize(
        "value", ["clinical_brief", "researcher", "deep_technical"]
    )
    def test_valid_values_accepted(self, value: str) -> None:
        query = Query(**_query_kwargs(audience_depth=value))
        assert query.audience_depth == value

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(audience_depth="expert"))


class TestQueryExtraForbid:
    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Query(**_query_kwargs(unexpected_field="nope"))


class TestRequestContextSurface:
    @pytest.mark.parametrize(
        "surface", ["web_ui", "rest_sse", "mcp", "cli", "graphql"]
    )
    def test_valid_surfaces_accepted(self, surface: str) -> None:
        # "graphql" added at T-4.3-05 (build phase 4.3): additive within
        # v1 per system-design-patterns.md pattern 10. This is an EXISTING
        # test whose old parametrize list ["web_ui", "rest_sse", "mcp",
        # "cli"] asserted the closed set BEFORE this phase; updated here
        # rather than left to assert a set the contract no longer matches.
        context = RequestContext(surface=surface)
        assert context.surface == surface

    def test_invalid_surface_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RequestContext(surface="desktop_app")

    def test_missing_surface_raises(self) -> None:
        with pytest.raises(ValidationError):
            RequestContext()

    def test_defaults(self) -> None:
        context = RequestContext(surface="web_ui")
        assert context.session_memory is None
        assert context.operator_mode is False

    def test_session_memory_accepts_a_real_summary(self) -> None:
        # T-4.5-02: the placeholder `Any | None` is gone. This used to accept
        # an arbitrary dict, `{"turns": []}`, which is now a validation error.
        summary = _summary()
        context = RequestContext(surface="web_ui", session_memory=summary)
        assert context.session_memory is not None
        assert context.session_memory.session_id == "session-1"


class TestRequestContextSessionMemoryBound:
    """F-1.0-02: session_memory is never an unbounded payload.

    This class predates the typed model. It used to pin a placeholder
    serialized-length cap of 5000 characters on an `Any`-typed field, and the
    original regression it covers is the judge's probe: a 500,000-character
    nested payload posted to `context.session_memory` and accepted with HTTP
    200.

    T-4.5-02 replaced the placeholder with `SessionMemorySummary`. The
    property under test is UNCHANGED and the coverage is strictly stronger,
    which is the only direction `.claude/rules/goal-contracts.md` permits: the
    probe payload is still rejected, and now it is rejected because it is not
    a valid summary at all rather than because it is long. An attacker can no
    longer stay under a byte count and send arbitrary structure.
    """

    def test_the_original_oversized_probe_is_still_rejected(self) -> None:
        # The exact shape from F-1.0-02, kept verbatim so the regression this
        # class exists for stays covered across the retyping.
        oversized = {"notes": "n" * 500_000, "turns": [{"role": "user"}] * 100}
        with pytest.raises(ValidationError):
            RequestContext(surface="web_ui", session_memory=oversized)

    def test_an_arbitrary_dict_is_now_rejected_outright(self) -> None:
        # Strictly stronger than the old cap: this payload is SMALL and was
        # accepted before, because the placeholder only measured length.
        with pytest.raises(ValidationError):
            RequestContext(surface="web_ui", session_memory={"turns": []})

    def test_each_list_is_capped(self) -> None:
        with pytest.raises(ValidationError):
            _summary(
                resolved_entities=[
                    ResolvedEntity(
                        mention="m", curie=f"NCBIGene:{i}", entity_type="Gene"
                    )
                    for i in range(MAX_RESOLVED_ENTITIES + 1)
                ]
            )
        with pytest.raises(ValidationError):
            _summary(
                compressed_findings=[
                    CompressedFinding(claim_summary="c", trace_id="t")
                    for _ in range(MAX_COMPRESSED_FINDINGS + 1)
                ]
            )
        with pytest.raises(ValidationError):
            _summary(open_threads=["t"] * (MAX_OPEN_THREADS + 1))

    def test_one_open_thread_cannot_be_unbounded(self) -> None:
        # The list cap bounds HOW MANY threads arrive and says nothing about
        # how long one may be. Without the per-item validator, ten threads of
        # a megabyte each satisfy every declared cap on the model.
        _summary(open_threads=["t" * 200])
        with pytest.raises(ValidationError):
            _summary(open_threads=["t" * 201])

    def test_the_token_budget_cannot_be_disabled_or_unbounded(self) -> None:
        assert _summary().token_budget == SESSION_MEMORY_TOKEN_BUDGET
        # Zero would silently disable memory; a huge value would defeat the
        # cap the field exists to impose. Both are refused.
        with pytest.raises(ValidationError):
            _summary(token_budget=0)
        with pytest.raises(ValidationError):
            _summary(token_budget=100_000)

    def test_a_valid_summary_is_accepted(self) -> None:
        context = RequestContext(surface="web_ui", session_memory=_summary())
        assert context.session_memory is not None
