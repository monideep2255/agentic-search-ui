"""Unit tests for `system_03_search_agent.adapters.graphql.types`.

Covers T-4.3-01's own acceptance surface directly, ahead of and
independent from `tests/.../test_phase_4_3_premise.py` (which drives the
full schema through the real router and is out of this ticket's reach,
since `schema.py` and `router.py` do not exist yet). Every assertion below
names, in a comment beside it, the mutation that turns it red, matching
this repository's mutation-proof discipline for a gate file
(`tracker/phase_4.3.md`'s "Premise gate design" section).
"""

from __future__ import annotations

import pytest
import strawberry

from system_03_search_agent.adapters.graphql import types as types_module
from system_03_search_agent.contracts.events import CitationPayload, TrustSignalPayload


def _citation_payload(**overrides: object) -> CitationPayload:
    base: dict[str, object] = {
        "citation_id": "c1",
        "display_index": 1,
        "source": "NCBI Gene",
        "source_id": "672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "gene_symbol",
        "claim_text": "BRCA1 is a protein-coding gene.",
        "evidence_kind": "curated_assertion",
        "assertion_confidence": "high",
        "population_ancestry_context": None,
        "license": "public_domain",
        "snapshot_date": "2026-07-01",
        "entity_name": "BRCA1",
    }
    base.update(overrides)
    return CitationPayload(**base)


def _trust_signal_payload(**overrides: object) -> TrustSignalPayload:
    base: dict[str, object] = {
        "outcome": "answer",
        "risk_tier": "low",
        "grounded": True,
        "triangulated": None,
        "citation_id": "c1",
        "scope": "answer",
        "message": None,
        "fallback_link": None,
    }
    base.update(overrides)
    return TrustSignalPayload(**base)


# ---------------------------------------------------------------------------
# Citation.from_payload: the fourteen-field mirror, and the source_url
# re-validation gate.
# ---------------------------------------------------------------------------


class TestCitationFromPayload:
    def test_every_field_round_trips(self) -> None:
        # Mutation that turns this red: drop, rename, or fail to copy any
        # of the fourteen CitationPayload fields inside from_payload.
        payload = _citation_payload()
        citation = types_module.Citation.from_payload(payload)

        assert citation.citation_id == payload.citation_id
        assert citation.display_index == payload.display_index
        assert citation.source == payload.source
        assert citation.source_id == payload.source_id
        assert citation.source_url == payload.source_url
        assert citation.layer == payload.layer
        assert citation.field == payload.field
        assert citation.claim_text == payload.claim_text
        assert citation.evidence_kind == payload.evidence_kind
        assert citation.assertion_confidence == payload.assertion_confidence
        assert citation.population_ancestry_context == payload.population_ancestry_context
        assert citation.license == payload.license
        assert citation.snapshot_date == payload.snapshot_date
        assert citation.entity_name == payload.entity_name

    def test_optional_fields_stay_none_when_absent(self) -> None:
        # Mutation that turns this red: coerce a None field to an empty
        # string or invent a placeholder instead of passing None through.
        payload = _citation_payload(population_ancestry_context=None, entity_name=None)
        citation = types_module.Citation.from_payload(payload)
        assert citation.population_ancestry_context is None
        assert citation.entity_name is None

    @pytest.mark.parametrize(
        "hostile_url",
        [
            "https://evil.example/gene/672",
            "https://www.ncbi.nlm.nih.gov.evil.example/gene/672",
            "https://www.ncbi.nlm.nih.gov/gene/672 https://evil.example",
            "https://www.ncbi.nlm.nih.gov/gene/672\nSource: evil",
        ],
    )
    def test_a_hostile_source_url_bypassing_pydantic_is_rejected(
        self, hostile_url: str
    ) -> None:
        # Mutation that turns this red: loosen the check to `startswith`,
        # or drop the explicit source_url re-validation entirely and rely
        # only on the model_copy'd payload's own (bypassed) constraint.
        # `model_copy(update=...)` is what a payload built this way looks
        # like: Pydantic's own documented behavior is that model_copy does
        # NOT re-run field validation, so a payload built this way carries
        # no guarantee its source_url was ever checked.
        payload = _citation_payload().model_copy(update={"source_url": hostile_url})
        with pytest.raises(types_module.GraphQLTypeError):
            types_module.Citation.from_payload(payload)

    def test_a_real_ncbi_source_url_is_accepted(self) -> None:
        # The second arm. Mutation that turns it red: reject every URL,
        # which would make the arm above pass while no citation can ever
        # be returned. A control that refuses everything destroys the
        # product just as surely as one that refuses nothing is unsafe.
        payload = _citation_payload()
        citation = types_module.Citation.from_payload(payload)
        assert citation.source_url.startswith("https://www.ncbi.nlm.nih.gov/")

    def test_a_clinicaltrials_source_url_is_also_accepted(self) -> None:
        # Mutation that turns this red: narrow the pattern check to an
        # ncbi.nlm.nih.gov-only match, which would wrongly reject a real
        # clinicaltrials_search citation (NCBI_SOURCE_URL_PATTERN's second
        # host alternative, widened at build phase 3.4).
        payload = _citation_payload(
            source="ClinicalTrials.gov",
            source_url="https://clinicaltrials.gov/study/NCT00000000",
        )
        citation = types_module.Citation.from_payload(payload)
        assert citation.source_url == "https://clinicaltrials.gov/study/NCT00000000"

    def test_an_oversized_field_bypassing_pydantic_is_rejected(self) -> None:
        # Mutation that turns this red: drop the defense-in-depth
        # `CitationPayload.model_validate` re-run inside from_payload,
        # relying only on the explicit source_url check above and trusting
        # every other field of a model_copy'd payload unchecked.
        payload = _citation_payload().model_copy(update={"claim_text": "x" * 5000})
        with pytest.raises(types_module.GraphQLTypeError):
            types_module.Citation.from_payload(payload)


# ---------------------------------------------------------------------------
# TrustSignal.from_payload: the eight-field mirror.
# ---------------------------------------------------------------------------


class TestTrustSignalFromPayload:
    def test_every_field_round_trips(self) -> None:
        # Mutation that turns this red: drop, rename, or fail to copy any
        # of the eight TrustSignalPayload fields.
        payload = _trust_signal_payload(
            triangulated=True,
            scope="claim",
            message="a second source disagrees",
            fallback_link="https://www.ncbi.nlm.nih.gov/gene/672",
        )
        trust_signal = types_module.TrustSignal.from_payload(payload)

        assert trust_signal.outcome == payload.outcome
        assert trust_signal.risk_tier == payload.risk_tier
        assert trust_signal.grounded == payload.grounded
        assert trust_signal.triangulated == payload.triangulated
        assert trust_signal.citation_id == payload.citation_id
        assert trust_signal.scope == payload.scope
        assert trust_signal.message == payload.message
        assert trust_signal.fallback_link == payload.fallback_link

    def test_a_null_scoped_refusal_round_trips_its_none_fields(self) -> None:
        # Mutation that turns this red: coerce a None triangulated/
        # citation_id/message/fallback_link into some non-None default.
        payload = _trust_signal_payload(
            outcome="refuse",
            risk_tier="unknown",
            grounded=False,
            triangulated=None,
            citation_id=None,
            message=None,
            fallback_link=None,
        )
        trust_signal = types_module.TrustSignal.from_payload(payload)
        assert trust_signal.triangulated is None
        assert trust_signal.citation_id is None
        assert trust_signal.message is None
        assert trust_signal.fallback_link is None
        assert trust_signal.risk_tier == "unknown"


# ---------------------------------------------------------------------------
# The remaining types: basic shape and field presence.
# ---------------------------------------------------------------------------


class TestRemainingTypesConstruct:
    def test_disclosures_carries_its_three_fields(self) -> None:
        # Mutation that turns this red: drop a field from Disclosures.
        disclosures = types_module.Disclosures(
            answer_truncated=True, citations_omitted=3, notes=["a note"]
        )
        assert disclosures.answer_truncated is True
        assert disclosures.citations_omitted == 3
        assert disclosures.notes == ["a note"]

    def test_ask_result_carries_all_six_fields(self) -> None:
        # Mutation that turns this red: drop persona_name (the one field
        # AskResult carries that RunResult does not) or any other field.
        citation = types_module.Citation.from_payload(_citation_payload())
        trust_signal = types_module.TrustSignal.from_payload(_trust_signal_payload())
        result = types_module.AskResult(
            run_id="r1",
            persona_name="Assistant",
            answer="BRCA1 is a gene.",
            trust_signal=trust_signal,
            citations=[citation],
            disclosures=types_module.Disclosures(
                answer_truncated=False, citations_omitted=0, notes=[]
            ),
        )
        assert result.run_id == "r1"
        assert result.persona_name == "Assistant"
        assert result.citations == [citation]

    def test_run_result_has_no_persona_name_field(self) -> None:
        # Mutation that turns this red: add persona_name to RunResult,
        # which the locked operation set (tracker/phase_4.3.md) never asks
        # for on the `run` query.
        field_names = {f.python_name for f in types_module.RunResult.__strawberry_definition__.fields}
        assert "persona_name" not in field_names
        assert {"run_id", "finished", "answer", "trust_signal", "citations", "disclosures"} == (
            field_names
        )

    def test_citations_export_carries_its_four_fields(self) -> None:
        # Mutation that turns this red: drop export_truncated or
        # run_cancelled, the two facts REST sends as response headers.
        citation = types_module.Citation.from_payload(_citation_payload())
        export = types_module.CitationsExport(
            run_id="r1", export_truncated=True, run_cancelled=False, citations=[citation]
        )
        assert export.export_truncated is True
        assert export.run_cancelled is False
        assert export.citations == [citation]

    def test_stop_run_result_carries_its_two_fields(self) -> None:
        # Mutation that turns this red: drop stopped or run_id.
        result = types_module.StopRunResult(run_id="r1", stopped=True)
        assert result.run_id == "r1"
        assert result.stopped is True


# ---------------------------------------------------------------------------
# AskInput / AudienceDepth.
# ---------------------------------------------------------------------------


class TestAskInputAndAudienceDepth:
    def test_audience_depth_has_exactly_querys_three_values(self) -> None:
        # Mutation that turns this red: add, drop, or misspell a member,
        # which would desync from contracts.query.Query.audience_depth's
        # own Literal.
        values = {member.value for member in types_module.AudienceDepth}
        assert values == {"clinical_brief", "researcher", "deep_technical"}

    def test_resolve_audience_depth_defaults_to_researcher(self) -> None:
        # Mutation that turns this red: default to a different literal, or
        # raise on None instead of defaulting.
        assert types_module.resolve_audience_depth(None) == "researcher"
        assert types_module.resolve_audience_depth(None) == types_module.DEFAULT_AUDIENCE_DEPTH

    def test_resolve_audience_depth_maps_every_member(self) -> None:
        # Mutation that turns this red: map a member to the wrong literal
        # string (e.g. swap clinical_brief and deep_technical).
        assert (
            types_module.resolve_audience_depth(types_module.AudienceDepth.CLINICAL_BRIEF)
            == "clinical_brief"
        )
        assert (
            types_module.resolve_audience_depth(types_module.AudienceDepth.RESEARCHER)
            == "researcher"
        )
        assert (
            types_module.resolve_audience_depth(types_module.AudienceDepth.DEEP_TECHNICAL)
            == "deep_technical"
        )

    def test_ask_input_constructs_with_and_without_audience_depth(self) -> None:
        # Mutation that turns this red: make audience_depth required,
        # breaking the "optional" contract tracker/phase_4.3.md states.
        without = types_module.AskInput(text="q", session_id="s1")
        assert without.audience_depth is None
        with_depth = types_module.AskInput(
            text="q", session_id="s1", audience_depth=types_module.AudienceDepth.RESEARCHER
        )
        assert with_depth.audience_depth is types_module.AudienceDepth.RESEARCHER


# ---------------------------------------------------------------------------
# The schema-printability check: this module's own defense against the
# documented Strawberry failure mode (a class or field docstring becomes a
# printed GraphQL description). This is a local, ahead-of-time check of
# exactly what the phase 4.3 premise gate's
# `test_the_schema_has_no_field_a_cost_figure_could_be_selected_into` arm
# asserts against the REAL schema (schema.py, not built by this ticket);
# this test derisks this file's own contribution to that arm before
# schema.py exists to assemble the whole schema.
# ---------------------------------------------------------------------------


@strawberry.type
class _StubQuery:
    @strawberry.field
    def ask_result(self) -> types_module.AskResult:
        raise NotImplementedError

    @strawberry.field
    def run_result(self) -> types_module.RunResult:
        raise NotImplementedError

    @strawberry.field
    def citations_export(self) -> types_module.CitationsExport:
        raise NotImplementedError

    @strawberry.field
    def stop_run_result(self) -> types_module.StopRunResult:
        raise NotImplementedError


@strawberry.type
class _StubMutation:
    @strawberry.field
    def ask(self, input: types_module.AskInput) -> bool:
        raise NotImplementedError


class TestNoCostSubstringReachesTheSchema:
    def test_the_printed_schema_carries_no_cost_usd_or_spend_substring(self) -> None:
        # Mutation that turns this red: add a docstring to any
        # @strawberry.type/@strawberry.input/@strawberry.enum class in
        # types.py, or a `strawberry.field(description=...)` on any field,
        # that happens to contain "cost", "usd", or "spend" (for example,
        # an explanatory docstring on Disclosures saying "no cost figure
        # is ever exposed here" would itself contain the word it is trying
        # to explain the absence of). Strawberry prints a class or field
        # docstring into the GraphQL SDL as that type's/field's
        # description, so the explanation would leak into exactly the
        # surface this check inspects.
        schema = strawberry.Schema(query=_StubQuery, mutation=_StubMutation)
        printed = str(schema).lower()
        for forbidden in ("cost", "usd", "spend"):
            assert forbidden not in printed, f"{forbidden!r} leaked into the printed schema"

    def test_the_printed_schema_actually_contains_real_field_names(self) -> None:
        # The second arm. Mutation that turns it red: make the schema
        # fail to build at all (e.g. by breaking a type), which would make
        # the arm above pass vacuously over an empty or error string.
        schema = strawberry.Schema(query=_StubQuery, mutation=_StubMutation)
        printed = str(schema)
        assert "sourceUrl" in printed
        assert "riskTier" in printed
        assert "citationsOmitted" in printed
