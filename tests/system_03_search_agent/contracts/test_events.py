"""Tests for the Event envelope and the Section 2.3 payload taxonomy."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ResolvedEntity,
    ThinkPayload,
    ToolCall,
    ToolResultPayload,
    ToolStartPayload,
    TokenPayload,
    TrustSignalPayload,
)

EVENT_TYPES = [
    "guard",
    "think",
    "plan",
    "tool_start",
    "tool_result",
    "token",
    "citation",
    "trust_signal",
    "cost",
    "error",
    "done",
]


def _envelope_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "type": "guard",
        "version": "v1",
        "trace_id": "trace-1",
        "seq": 0,
        "ts": datetime.now(timezone.utc),
        "payload": {"passed": True, "category": "ok", "reason": None},
    }
    base.update(overrides)
    return base


# One known-valid payload per taxonomy member. Since Event.payload is now
# bound to the model matching Event.type (F-1.0-01), any test that builds an
# Event for a given type must pass a payload actually shaped for that type;
# an arbitrary or mismatched payload (as several pre-fix tests below used to
# assume was fine) now correctly raises ValidationError.
VALID_PAYLOAD_BY_TYPE: dict[str, dict[str, object]] = {
    "guard": {"passed": True, "category": "ok", "reason": None},
    "think": {
        "narrative": "Resolving BRCA1 to its Gene CURIE",
        "query_class": "lookup",
        "resolved_entities": [],
        "clarifying_question": None,
    },
    "plan": {"narrative": "Querying Gene", "tool_calls": []},
    "tool_start": {
        "call_id": "c1",
        "tool": "ncbi_efetch",
        "layer": "layer_2_api",
        "status": "ok",
    },
    "tool_result": {
        "call_id": "c1",
        "tool": "ncbi_efetch",
        "layer": "layer_2_api",
        "status": "ok",
        "summary": "ok",
        "result_count": 1,
        "truncated": False,
    },
    "token": {"text": "BRCA1 is a tumor suppressor gene", "marker_ids": []},
    "citation": {
        "citation_id": "c_1",
        "display_index": 1,
        "source": "NCBI Gene",
        "source_id": "672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "description",
        "claim_text": "BRCA1 is a tumor suppressor gene",
        "evidence_kind": "primary_assertion",
        "assertion_confidence": "asserted",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
    },
    "trust_signal": {
        "outcome": "answer",
        "risk_tier": "low",
        "grounded": True,
        "triangulated": None,
    },
    "cost": {
        "query_cost_usd": 0.0234,
        "query_cap_usd": 0.10,
        "cap_fraction": 0.234,
        "model_tier": "guard",
    },
    "error": {
        "fatal": False,
        "scope": "tool",
        "source": "ncbi_efetch",
        "error_class": "transient",
        "message": "ncbi_efetch timed out after 15s, retry with backoff",
        "retry_after_s": 2,
    },
    "done": {
        "total_cost_usd": 0.021,
        "total_tool_calls": 4,
        "elapsed_ms": 6200,
        "trust_outcome": "answer",
    },
}


class TestEventEnvelopeRequiredFields:
    @pytest.mark.parametrize(
        "missing_field", ["type", "version", "trace_id", "seq", "ts", "payload"]
    )
    def test_omitting_a_required_field_raises(self, missing_field: str) -> None:
        kwargs = _envelope_kwargs()
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            Event(**kwargs)

    def test_full_envelope_succeeds(self) -> None:
        event = Event(**_envelope_kwargs())
        assert event.type == "guard"
        assert event.version == "v1"


class TestEventType:
    @pytest.mark.parametrize("event_type", EVENT_TYPES)
    def test_every_taxonomy_value_accepted(self, event_type: str) -> None:
        # payload must be shaped for event_type now that Event binds payload
        # to its declared type (F-1.0-01); see TestEventPayloadBoundToDeclaredType.
        event = Event(
            **_envelope_kwargs(
                type=event_type, payload=VALID_PAYLOAD_BY_TYPE[event_type]
            )
        )
        assert event.type == event_type

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Event(**_envelope_kwargs(type="unknown_type"))

    def test_eleven_taxonomy_values_exactly(self) -> None:
        assert len(EVENT_TYPES) == 11


class TestEventVersion:
    def test_v1_accepted(self) -> None:
        event = Event(**_envelope_kwargs(version="v1"))
        assert event.version == "v1"

    def test_other_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Event(**_envelope_kwargs(version="v2"))


class TestEventSeq:
    def test_negative_seq_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Event(**_envelope_kwargs(seq=-1))

    def test_zero_seq_accepted(self) -> None:
        event = Event(**_envelope_kwargs(seq=0))
        assert event.seq == 0


class TestEventTraceId:
    def test_trace_id_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(**_envelope_kwargs(trace_id="t" * 65))

    def test_trace_id_at_max_length_succeeds(self) -> None:
        event = Event(**_envelope_kwargs(trace_id="t" * 64))
        assert len(event.trace_id) == 64


class TestEventExtraForbid:
    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Event(**_envelope_kwargs(unexpected="nope"))


class TestGuardPayload:
    def test_example_from_spec(self) -> None:
        payload = GuardPayload(passed=True, category="ok", reason=None)
        assert payload.passed is True

    @pytest.mark.parametrize(
        "category",
        ["ok", "off_topic", "medical_advice", "injection", "rate_limited", "cost_capped"],
    )
    def test_every_category_accepted(self, category: str) -> None:
        payload = GuardPayload(passed=False, category=category, reason=None)
        assert payload.category == category

    def test_unknown_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GuardPayload(passed=False, category="unknown", reason=None)

    def test_reason_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GuardPayload(passed=False, category="off_topic", reason="x" * 257)


class TestThinkPayload:
    def test_example_from_spec(self) -> None:
        payload = ThinkPayload(
            narrative="Resolving BRCA1 to its Gene CURIE",
            query_class="multi_hop",
            resolved_entities=[
                ResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=0.98)
            ],
            clarifying_question=None,
        )
        assert payload.query_class == "multi_hop"

    def test_narrative_at_max_length_accepted(self) -> None:
        payload = ThinkPayload(
            narrative="n" * 500,
            query_class="lookup",
            resolved_entities=[],
            clarifying_question=None,
        )
        assert len(payload.narrative) == 500

    def test_narrative_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ThinkPayload(
                narrative="n" * 501,
                query_class="lookup",
                resolved_entities=[],
                clarifying_question=None,
            )

    @pytest.mark.parametrize(
        "query_class",
        ["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"],
    )
    def test_every_query_class_accepted(self, query_class: str) -> None:
        payload = ThinkPayload(
            narrative="ok",
            query_class=query_class,
            resolved_entities=[],
            clarifying_question=None,
        )
        assert payload.query_class == query_class

    def test_unknown_query_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ThinkPayload(
                narrative="ok",
                query_class="unknown",
                resolved_entities=[],
                clarifying_question=None,
            )

    def test_resolved_entities_at_max_items_accepted(self) -> None:
        entities = [
            ResolvedEntity(text="x", curie=f"NCBIGene:{i}", confidence=0.5)
            for i in range(20)
        ]
        payload = ThinkPayload(
            narrative="ok",
            query_class="lookup",
            resolved_entities=entities,
            clarifying_question=None,
        )
        assert len(payload.resolved_entities) == 20

    def test_resolved_entities_over_max_items_rejected(self) -> None:
        entities = [
            ResolvedEntity(text="x", curie=f"NCBIGene:{i}", confidence=0.5)
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            ThinkPayload(
                narrative="ok",
                query_class="lookup",
                resolved_entities=entities,
                clarifying_question=None,
            )

    def test_resolved_entity_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.5)


class TestPlanPayload:
    def test_example_from_spec(self) -> None:
        payload = PlanPayload(
            narrative="Querying Gene, PubMed, ClinVar, GTR, MedGen",
            tool_calls=[
                ToolCall(tool="cypher_query", call_id="c1", layer="layer_1_graph"),
                ToolCall(tool="ncbi_efetch", call_id="c2", layer="layer_2_api"),
            ],
        )
        assert len(payload.tool_calls) == 2

    def test_tool_calls_at_max_items_accepted(self) -> None:
        calls = [
            ToolCall(tool="cypher_query", call_id=f"c{i}", layer="layer_1_graph")
            for i in range(20)
        ]
        payload = PlanPayload(narrative="ok", tool_calls=calls)
        assert len(payload.tool_calls) == 20

    def test_tool_calls_over_max_items_rejected(self) -> None:
        calls = [
            ToolCall(tool="cypher_query", call_id=f"c{i}", layer="layer_1_graph")
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            PlanPayload(narrative="ok", tool_calls=calls)

    def test_tool_enum_pinned_to_seven_registered_tools(self) -> None:
        with pytest.raises(ValidationError):
            ToolCall(tool="blast_search", call_id="c1", layer="layer_1_graph")

    @pytest.mark.parametrize(
        "tool",
        [
            "cypher_query",
            "ncbi_efetch",
            "ncbi_dbsnp",
            "pubtator_annotate",
            "litvar2_lookup",
            "pathogen_detection",
            "clinicaltrials_search",
        ],
    )
    def test_every_registered_tool_accepted(self, tool: str) -> None:
        call = ToolCall(tool=tool, call_id="c1", layer="layer_1_graph")
        assert call.tool == tool

    @pytest.mark.parametrize(
        "layer", ["layer_1_graph", "layer_2_api", "layer_3_enrichment"]
    )
    def test_every_layer_accepted(self, layer: str) -> None:
        call = ToolCall(tool="cypher_query", call_id="c1", layer=layer)
        assert call.layer == layer

    def test_unknown_layer_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolCall(tool="cypher_query", call_id="c1", layer="layer_4_unknown")


class TestToolStartAndResultPayload:
    def test_tool_start_example_from_spec(self) -> None:
        payload = ToolStartPayload(
            call_id="c2", tool="ncbi_efetch", layer="layer_2_api", status="ok"
        )
        assert payload.status == "ok"

    @pytest.mark.parametrize("status", ["ok", "empty", "error"])
    def test_every_status_accepted(self, status: str) -> None:
        payload = ToolStartPayload(
            call_id="c2", tool="ncbi_efetch", layer="layer_2_api", status=status
        )
        assert payload.status == status

    def test_unknown_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolStartPayload(
                call_id="c2", tool="ncbi_efetch", layer="layer_2_api", status="pending"
            )

    def test_tool_result_adds_summary_result_count_truncated(self) -> None:
        payload = ToolResultPayload(
            call_id="c2",
            tool="ncbi_efetch",
            layer="layer_2_api",
            status="ok",
            summary="s" * 1000,
            result_count=5,
            truncated=False,
        )
        assert payload.result_count == 5

    def test_tool_result_summary_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolResultPayload(
                call_id="c2",
                tool="ncbi_efetch",
                layer="layer_2_api",
                status="ok",
                summary="s" * 1001,
                result_count=5,
                truncated=False,
            )

    def test_tool_result_negative_result_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolResultPayload(
                call_id="c2",
                tool="ncbi_efetch",
                layer="layer_2_api",
                status="ok",
                summary="ok",
                result_count=-1,
                truncated=False,
            )


class TestTokenPayload:
    def test_example_from_spec(self) -> None:
        payload = TokenPayload(
            text="BRCA1 is a tumor suppressor gene", marker_ids=["c_1"]
        )
        assert payload.marker_ids == ["c_1"]

    def test_text_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenPayload(text="t" * 1001, marker_ids=[])

    def test_marker_ids_over_max_items_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenPayload(text="ok", marker_ids=[f"c_{i}" for i in range(21)])


class TestCitationPayload:
    def _valid_kwargs(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "citation_id": "c_1",
            "display_index": 1,
            "source": "NCBI Gene",
            "source_id": "672",
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
            "layer": "layer_1_graph",
            "field": "description",
            "claim_text": "BRCA1 is a tumor suppressor gene",
            "evidence_kind": "primary_assertion",
            "assertion_confidence": "asserted",
            "population_ancestry_context": None,
            "license": "public_domain_us_gov",
        }
        base.update(overrides)
        return base

    def test_example_from_spec(self) -> None:
        payload = CitationPayload(**self._valid_kwargs())
        assert payload.display_index == 1

    def test_display_index_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(**self._valid_kwargs(display_index=0))

    @pytest.mark.parametrize(
        "layer", ["layer_1_graph", "layer_2_api", "layer_3_enrichment"]
    )
    def test_every_layer_accepted(self, layer: str) -> None:
        payload = CitationPayload(**self._valid_kwargs(layer=layer))
        assert payload.layer == layer

    def test_unknown_layer_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(**self._valid_kwargs(layer="layer_9_unknown"))

    def test_non_ncbi_source_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(
                **self._valid_kwargs(source_url="https://evil.example.com/gene/672")
            )

    def test_http_scheme_source_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(
                **self._valid_kwargs(source_url="http://www.ncbi.nlm.nih.gov/gene/672")
            )

    def test_ncbi_subdomain_source_url_accepted(self) -> None:
        payload = CitationPayload(
            **self._valid_kwargs(source_url="https://pubmed.ncbi.nlm.nih.gov/12345")
        )
        assert "ncbi.nlm.nih.gov" in payload.source_url

    def test_claim_text_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(**self._valid_kwargs(claim_text="c" * 1001))

    def test_population_ancestry_context_optional(self) -> None:
        payload = CitationPayload(
            **self._valid_kwargs(population_ancestry_context="European")
        )
        assert payload.population_ancestry_context == "European"


class TestTrustSignalPayload:
    def test_example_from_spec(self) -> None:
        payload = TrustSignalPayload(
            outcome="answer", risk_tier="low", grounded=True, triangulated=None
        )
        assert payload.outcome == "answer"

    @pytest.mark.parametrize("outcome", ["answer", "flag", "ask", "refuse"])
    def test_every_outcome_accepted(self, outcome: str) -> None:
        payload = TrustSignalPayload(
            outcome=outcome, risk_tier="low", grounded=True, triangulated=None
        )
        assert payload.outcome == outcome

    def test_unknown_outcome_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrustSignalPayload(
                outcome="unknown", risk_tier="low", grounded=True, triangulated=None
            )

    def test_risk_tier_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrustSignalPayload(
                outcome="answer",
                risk_tier="r" * 17,
                grounded=True,
                triangulated=None,
            )


class TestCostPayload:
    def test_example_from_spec(self) -> None:
        payload = CostPayload(
            query_cost_usd=0.0234,
            query_cap_usd=0.10,
            cap_fraction=0.234,
            model_tier="guard",
        )
        assert payload.model_tier == "guard"

    @pytest.mark.parametrize("model_tier", ["guard", "plan", "synth"])
    def test_every_model_tier_accepted(self, model_tier: str) -> None:
        payload = CostPayload(
            query_cost_usd=0.01,
            query_cap_usd=0.10,
            cap_fraction=0.1,
            model_tier=model_tier,
        )
        assert payload.model_tier == model_tier

    def test_unknown_model_tier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CostPayload(
                query_cost_usd=0.01,
                query_cap_usd=0.10,
                cap_fraction=0.1,
                model_tier="unknown",
            )

    def test_negative_query_cost_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CostPayload(
                query_cost_usd=-0.01,
                query_cap_usd=0.10,
                cap_fraction=0.1,
                model_tier="guard",
            )


class TestErrorPayload:
    def test_example_from_spec(self) -> None:
        payload = ErrorPayload(
            fatal=False,
            scope="tool",
            source="ncbi_efetch",
            error_class="transient",
            message="ncbi_efetch timed out after 15s, retry with backoff",
            retry_after_s=2,
        )
        assert payload.scope == "tool"

    @pytest.mark.parametrize("scope", ["tool", "step", "run"])
    def test_every_scope_accepted(self, scope: str) -> None:
        payload = ErrorPayload(
            fatal=False,
            scope=scope,
            source="ncbi_efetch",
            error_class="transient",
            message="ok",
            retry_after_s=0,
        )
        assert payload.scope == scope

    def test_unknown_scope_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ErrorPayload(
                fatal=False,
                scope="unknown",
                source="ncbi_efetch",
                error_class="transient",
                message="ok",
                retry_after_s=0,
            )

    @pytest.mark.parametrize(
        "error_class", ["transient", "recoverable", "unexpected"]
    )
    def test_every_error_class_accepted(self, error_class: str) -> None:
        payload = ErrorPayload(
            fatal=False,
            scope="tool",
            source="ncbi_efetch",
            error_class=error_class,
            message="ok",
            retry_after_s=0,
        )
        assert payload.error_class == error_class

    def test_unknown_error_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ErrorPayload(
                fatal=False,
                scope="tool",
                source="ncbi_efetch",
                error_class="unknown",
                message="ok",
                retry_after_s=0,
            )

    def test_source_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ErrorPayload(
                fatal=False,
                scope="tool",
                source="s" * 65,
                error_class="transient",
                message="ok",
                retry_after_s=0,
            )

    def test_message_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ErrorPayload(
                fatal=False,
                scope="tool",
                source="ncbi_efetch",
                error_class="transient",
                message="m" * 257,
                retry_after_s=0,
            )

    def test_negative_retry_after_s_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ErrorPayload(
                fatal=False,
                scope="tool",
                source="ncbi_efetch",
                error_class="transient",
                message="ok",
                retry_after_s=-1,
            )


class TestDonePayload:
    def test_example_from_spec(self) -> None:
        payload = DonePayload(
            total_cost_usd=0.021,
            total_tool_calls=4,
            elapsed_ms=6200,
            trust_outcome="answer",
        )
        assert payload.total_tool_calls == 4

    @pytest.mark.parametrize("trust_outcome", ["answer", "flag", "ask", "refuse"])
    def test_every_trust_outcome_accepted(self, trust_outcome: str) -> None:
        payload = DonePayload(
            total_cost_usd=0.0,
            total_tool_calls=0,
            elapsed_ms=0,
            trust_outcome=trust_outcome,
        )
        assert payload.trust_outcome == trust_outcome

    def test_unknown_trust_outcome_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DonePayload(
                total_cost_usd=0.0,
                total_tool_calls=0,
                elapsed_ms=0,
                trust_outcome="unknown",
            )

    def test_negative_elapsed_ms_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DonePayload(
                total_cost_usd=0.0,
                total_tool_calls=0,
                elapsed_ms=-1,
                trust_outcome="answer",
            )


class TestEventPayloadBoundToDeclaredType:
    """F-1.0-01: Event.payload must conform to the model matching Event.type.

    Regression coverage for the judge's two rejecting probes on ticket
    T-1.0-01, plus a positive check that a correctly-shaped payload for
    every one of the eleven taxonomy members still validates.
    """

    def test_eleven_valid_payloads_declared(self) -> None:
        assert set(VALID_PAYLOAD_BY_TYPE) == set(EVENT_TYPES)

    @pytest.mark.parametrize("event_type", EVENT_TYPES)
    def test_correctly_shaped_payload_still_validates(self, event_type: str) -> None:
        event = Event(
            **_envelope_kwargs(
                type=event_type, payload=VALID_PAYLOAD_BY_TYPE[event_type]
            )
        )
        assert event.type == event_type

    def test_judge_probe_1_arbitrary_oversized_blob_under_guard_rejected(self) -> None:
        # Original judge probe: an arbitrary, oversized, unrelated blob with
        # none of GuardPayload's required fields, passed as a guard payload.
        # Previously ACCEPTED; must now raise ValidationError.
        with pytest.raises(ValidationError):
            Event(
                **_envelope_kwargs(
                    type="guard",
                    payload={
                        "totally": "unknown",
                        "blob": "x" * 200000,
                        "nested": {"deep": {"deeper": "value"}},
                    },
                )
            )

    def test_judge_probe_2_guard_shaped_payload_under_done_rejected(self) -> None:
        # Original judge probe: a guard-shaped payload ({"passed": ...,
        # "category": ...}) accepted under type="done". Previously ACCEPTED;
        # must now raise ValidationError since it doesn't match DonePayload.
        with pytest.raises(ValidationError):
            Event(
                **_envelope_kwargs(
                    type="done", payload={"passed": True, "category": "ok"}
                )
            )
