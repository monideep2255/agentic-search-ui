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

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
import strawberry
from graphql import GraphQLError

from system_03_search_agent.adapters.graphql import schema as schema_module
from system_03_search_agent.adapters.graphql import security as security_module
from system_03_search_agent.adapters.graphql import types as types_module
from system_03_search_agent.contracts.events import CitationPayload, TrustSignalPayload
from system_03_search_agent.contracts.query import Query as CoreQuery


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
    def test_disclosures_carries_its_four_fields(self) -> None:
        # Mutation that turns this red: drop a field from Disclosures.
        # `run_failed` was added at the fifth review round (F-R5-07): the
        # fatal-error disclosure had been carried ONLY as a note, and notes
        # are capped, so on a busy run it was evicted and the fact that the
        # run had died survived nowhere at all.
        disclosures = types_module.Disclosures(
            answer_truncated=True, citations_omitted=3, run_failed=True, notes=["a note"]
        )
        assert disclosures.answer_truncated is True
        assert disclosures.citations_omitted == 3
        assert disclosures.run_failed is True
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
                answer_truncated=False, citations_omitted=0, run_failed=False, notes=[]
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

    def test_citations_export_carries_its_five_fields(self) -> None:
        # Mutation that turns this red: drop export_truncated or
        # run_cancelled, the two facts REST sends as response headers, or
        # drop `disclosures`, the field that says WHY the export is short
        # (judge J-06, premise clause C5).
        citation = types_module.Citation.from_payload(_citation_payload())
        disclosures = types_module.Disclosures(
            answer_truncated=False, citations_omitted=2, run_failed=False,
            notes=["two were dropped"]
        )
        export = types_module.CitationsExport(
            run_id="r1",
            export_truncated=True,
            run_cancelled=False,
            citations=[citation],
            disclosures=disclosures,
        )
        assert export.export_truncated is True
        assert export.run_cancelled is False
        assert export.citations == [citation]
        assert export.disclosures.citations_omitted == 2
        assert export.disclosures.notes == ["two were dropped"]

    @pytest.mark.asyncio
    async def test_the_export_actually_says_why_a_citation_was_dropped(self) -> None:
        # The field existing is not the fix; the field being POPULATED is.
        # Mutation that turns this red: build `disclosures` in
        # `fold.fold_citations` from an empty notes list rather than from
        # `collector.disclosure_notes()`, which leaves every other arm here
        # green while the caller learns nothing about a short export.
        # `export_truncated` alone (the pre-fix state) cannot distinguish a
        # citation dropped for failing validation from one dropped at the
        # 50-citation cap, which is the distinction J-06 is about.
        from datetime import UTC, datetime

        from system_03_search_agent.adapters.graphql import fold as fold_module
        from system_03_search_agent.contracts.events import Event
        from system_03_search_agent.core.run_registry import RunEntry

        good = _citation_payload()
        rejected = _citation_payload(citation_id="c2", display_index=2).model_dump()
        rejected["source_url"] = "https://evil.example/gene/672"

        def _make(seq: int, payload: dict[str, object]) -> Event:
            return Event.model_construct(
                type="citation",
                version="v1",
                trace_id="t1",
                seq=seq,
                ts=datetime.now(UTC),
                payload=payload,
            )

        async def _noop() -> None:
            return None

        task = asyncio.create_task(_noop())
        await task
        entry = RunEntry(
            run_id="r-disclosures",
            user_id="u1",
            # T-4.6-06: required field, holding the `Query` the run is
            # actually using (F-4.6-J-01). Nothing here reads it.
            query=CoreQuery(
                text="what is this",
                session_id="types-test",
                trace_id="r-disclosures",
                owner_id="user:u1",
            ),
            owner_id="user:u1",
            queue=asyncio.Queue(),
            task=task,
            events=[_make(0, good.model_dump()), _make(1, rejected)],
            finished=True,
        )

        export = fold_module.fold_citations(entry)

        assert len(export.citations) == 1
        assert export.export_truncated is True
        assert export.disclosures.citations_omitted == 1
        assert export.disclosures.notes, "a short export must say why it is short"
        assert export.disclosures.answer_truncated is False

    def test_citations_export_cannot_be_built_without_saying_what_it_dropped(self) -> None:
        # The arm that makes `disclosures` REQUIRED rather than defaulted.
        # Mutation that turns this red: give the field a default (or a
        # `strawberry.field(default_factory=...)`), after which every
        # construction site keeps compiling while reporting "nothing to
        # disclose" about an export that just dropped a citation. A
        # defaulted field here would be worse than no field: it would put a
        # false statement on the trust surface instead of an absent one.
        with pytest.raises(TypeError):
            types_module.CitationsExport(
                run_id="r1", export_truncated=True, run_cancelled=False, citations=[]
            )

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

    def test_ask_input_publishes_both_bounded_scalars_on_the_real_schema(self) -> None:
        # Mutation that turns this red: revert either AskInput field to a
        # bare `str`, which is exactly the F-4.3-A-16 / J-10 defect. Every
        # other arm in TestAskInputBounds below runs against a stub schema
        # that mounts the real AskInput; this one arm is what ties those
        # results to the SHIPPED schema, so a bounded type used only in the
        # test harness cannot pass for a bounded surface.
        printed = str(schema_module.schema)
        ask_input_block = printed.split("input AskInput {", 1)[1].split("}", 1)[0]
        assert "text: AskText!" in ask_input_block
        assert "sessionId: AskSessionId!" in ask_input_block

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


# ---------------------------------------------------------------------------
# AskInput's INPUT bounds: the F-4.3-A-16 / J-10 regression surface.
#
# The defect these arms pin: AskInput declared no bound, so an over-long,
# empty or whitespace-only question and an over-long sessionId all reached
# the `ask` resolver, raised a Pydantic ValidationError there, and came back
# as "This request could not be completed due to an internal error." with no
# code. Four caller-fixable mistakes reported as a server fault, which a
# well-behaved client retries forever.
#
# WHY A STUB SCHEMA AND NOT THE REAL ONE: these arms have to observe what
# happens BEFORE any resolver runs, and they have to observe the accept
# direction as well as the refuse direction. Driving the real `ask` resolver
# would start a real run and need a real principal, which is the premise
# gate's job, not this file's. The stub below mounts the REAL `AskInput` type
# behind the REAL `security.SCHEMA_EXTENSIONS` and `security.
# STRAWBERRY_CONFIG` (MaskErrors included, which is the extension that turned
# the original defect into a generic message), so everything except the
# resolver body is production code. `test_ask_input_publishes_both_bounded_
# scalars_on_the_real_schema` above ties the stub's AskInput to the shipped
# schema's.
#
# WHAT THESE ARMS DELIBERATELY DO NOT COVER: the HTTP layer. Whether a body
# large enough to matter is refused before parsing is J-11, an unbounded
# request body, which belongs to router.py and is not fixed here.
# ---------------------------------------------------------------------------

_resolver_reached: list[types_module.AskInput] = []


@strawberry.type
class _BoundsQuery:
    @strawberry.field
    def ping(self) -> str:
        return "pong"


@strawberry.type
class _BoundsMutation:
    # Named `ask` on purpose: security.py's one-run-per-document bound counts
    # a field by that exact name, so the stub exercises the same validation
    # rules the real document does.
    @strawberry.mutation
    def ask(self, input: types_module.AskInput) -> str:
        _resolver_reached.append(input)
        return "reached"


_bounds_schema = strawberry.Schema(
    query=_BoundsQuery,
    mutation=_BoundsMutation,
    extensions=list(security_module.SCHEMA_EXTENSIONS),
    config=security_module.STRAWBERRY_CONFIG,
)

_ASK_WITH_VARIABLES = "mutation A($input: AskInput!) { ask(input: $input) }"


def _execute(document: str, variables: dict[str, Any] | None = None) -> Any:
    """Run one document against the stub schema.

    Async rather than `execute_sync` because `security.SCHEMA_EXTENSIONS`
    includes `RequestTimeoutExtension`, whose `on_execute` hook is a
    coroutine: `execute_sync` refuses it outright rather than skipping it, so
    a synchronous harness here would be testing a DIFFERENT extension stack
    than the one that ships.
    """
    _resolver_reached.clear()
    return asyncio.run(_bounds_schema.execute(document, variable_values=variables))


def _run_ask(**fields: Any) -> Any:
    """Execute the stub `ask` with `fields` as a query VARIABLE."""
    return _execute(_ASK_WITH_VARIABLES, {"input": fields})


def _errors(result: Any) -> list[tuple[str, Any]]:
    return [(error.message, (error.extensions or {}).get("code")) for error in (result.errors or [])]


class TestAskInputBounds:
    def test_a_question_at_the_maximum_length_is_accepted(self) -> None:
        # The accept arm, and it is the load-bearing one: a bound that
        # refuses everything passes every attack test and destroys the
        # product. Mutation that turns this red: make the scalar reject at
        # `>=` instead of `>`, or hardcode a smaller maximum than the core
        # model's.
        result = _run_ask(text="q" * types_module.ASK_TEXT_MAX_LENGTH, sessionId="s1")
        assert result.errors is None
        assert result.data == {"ask": "reached"}
        assert len(_resolver_reached) == 1

    def test_a_one_character_question_is_accepted(self) -> None:
        # The other accept boundary. Mutation that turns this red: invent a
        # minimum length larger than the core model's `min_length=1`.
        result = _run_ask(text="q", sessionId="s1")
        assert result.errors is None
        assert len(_resolver_reached) == 1

    def test_a_question_one_character_over_the_maximum_is_refused(self) -> None:
        # THE headline regression. Mutation that turns this red: delete the
        # length check from `_parse_ask_text`, or revert `AskInput.text` to a
        # bare `str`. Either way the value reaches the resolver and the
        # Pydantic failure comes back masked, which is what the four
        # assertions below each independently detect.
        result = _run_ask(text="q" * (types_module.ASK_TEXT_MAX_LENGTH + 1), sessionId="s1")
        assert _resolver_reached == [], "the resolver must never see an out-of-bounds question"
        messages = _errors(result)
        assert len(messages) == 1
        message, code = messages[0]
        assert code == types_module.ASK_INPUT_ERROR_CODE
        assert "text" in message
        assert str(types_module.ASK_TEXT_MAX_LENGTH) in message
        assert security_module._MASKED_ERROR_MESSAGE not in message

    def test_an_empty_question_is_refused_with_an_actionable_message(self) -> None:
        # Mutation that turns this red: drop the `len(value) <
        # ASK_TEXT_MIN_LENGTH` check, which is the core's own `min_length=1`.
        result = _run_ask(text="", sessionId="s1")
        assert _resolver_reached == []
        message, code = _errors(result)[0]
        assert code == types_module.ASK_INPUT_ERROR_CODE
        assert "text" in message
        assert security_module._MASKED_ERROR_MESSAGE not in message

    def test_a_whitespace_only_question_is_refused(self) -> None:
        # Mutation that turns this red: drop the `not value.strip()` check,
        # which is the half `min_length` alone admits (a question of three
        # spaces has length three and asks nothing). This mirrors
        # `Query._reject_whitespace_only_text`, including its Unicode
        # awareness, which the second value below exercises.
        for blank in ("   ", "　 \t\n"):
            result = _run_ask(text=blank, sessionId="s1")
            assert _resolver_reached == [], blank
            message, code = _errors(result)[0]
            assert code == types_module.ASK_INPUT_ERROR_CODE
            assert "text" in message

    def test_a_question_is_never_silently_stripped_or_rewritten(self) -> None:
        # The refusal arms above would also pass if the scalar STRIPPED the
        # question instead of refusing it. Mutation that turns this red:
        # return `value.strip()` from `_parse_ask_text`. A boundary validator
        # accepts or refuses; it never edits the user's question before the
        # guardrail classifies it (contracts/query.py states this rule, and
        # this arm is what holds this surface to it).
        result = _run_ask(text="  BRCA1?  ", sessionId="s1")
        assert result.errors is None
        assert _resolver_reached[0].text == "  BRCA1?  "

    def test_a_session_id_at_the_maximum_length_is_accepted(self) -> None:
        # The accept arm for the second bound. Mutation that turns this red:
        # reject at `>=`, or hardcode a maximum below the core model's 64.
        result = _run_ask(text="q", sessionId="s" * types_module.ASK_SESSION_ID_MAX_LENGTH)
        assert result.errors is None
        assert len(_resolver_reached) == 1

    def test_a_session_id_one_character_over_the_maximum_is_refused(self) -> None:
        # Mutation that turns this red: delete the length check from
        # `_parse_ask_session_id`, or revert `AskInput.session_id` to `str`.
        result = _run_ask(text="q", sessionId="s" * (types_module.ASK_SESSION_ID_MAX_LENGTH + 1))
        assert _resolver_reached == []
        message, code = _errors(result)[0]
        assert code == types_module.ASK_INPUT_ERROR_CODE
        assert "sessionId" in message
        assert str(types_module.ASK_SESSION_ID_MAX_LENGTH) in message
        assert security_module._MASKED_ERROR_MESSAGE not in message

    def test_an_empty_session_id_is_still_accepted(self) -> None:
        # The anti-over-correction arm. `contracts.query.Query.session_id`
        # declares `max_length` only, so a minimum here would be a bound no
        # other surface enforces, and this surface would start refusing
        # requests REST accepts: the same cross-surface divergence the whole
        # fix exists to remove, pointing the other way. Mutation that turns
        # this red: add a `min_length` to `_parse_ask_session_id`.
        result = _run_ask(text="q", sessionId="")
        assert result.errors is None
        assert len(_resolver_reached) == 1

    def test_a_non_string_question_is_refused_rather_than_masked(self) -> None:
        # A custom scalar does its own type check: graphql-core applies no
        # String coercion of its own once the field's type is this scalar,
        # so `parse_value` can be handed an int, a bool, or a dict. Mutation
        # that turns this red: drop the `isinstance(value, str)` check, after
        # which `len(5)` raises TypeError, which is NOT a GraphQLError and
        # NOT marker-declared, so it comes back masked with no code, exactly
        # the original defect in a new costume.
        for hostile in (5, True, {"text": "q"}, ["q"]):
            result = _run_ask(text=hostile, sessionId="s1")
            assert _resolver_reached == [], hostile
            message, code = _errors(result)[0]
            assert code == types_module.ASK_INPUT_ERROR_CODE, hostile
            assert security_module._MASKED_ERROR_MESSAGE not in message, hostile

    def test_the_refusal_survives_as_an_inline_literal_too_and_carries_the_code(self) -> None:
        # The variable path and the inline-literal path are DIFFERENT code
        # paths in graphql-core: a variable is coerced with
        # `coerce_input_value` (which rebuilds the error, so the code is
        # attached by security._should_mask_error from the class name), while
        # a literal is checked by the ValuesOfCorrectTypeRule during
        # validation (which reports the raised error as-is, with no
        # `original_error`, so the code survives only because
        # `_refuse` sets `extensions` at construction). Mutation that turns
        # this red: drop `extensions={"code": ...}` from `_refuse`; the
        # variable arms above all stay green, and only this one goes red.
        too_long = "q" * (types_module.ASK_TEXT_MAX_LENGTH + 1)
        result = _execute(f'mutation {{ ask(input: {{text: "{too_long}", sessionId: "s1"}}) }}')
        assert _resolver_reached == []
        message, code = _errors(result)[0]
        assert code == types_module.ASK_INPUT_ERROR_CODE
        assert "text" in message
        assert security_module._MASKED_ERROR_MESSAGE not in message

    def test_a_legitimate_inline_literal_still_works(self) -> None:
        # The paired accept arm for the literal path. Mutation that turns it
        # red: make `_parse_ask_text` refuse unconditionally, which would
        # leave every refusal arm above green.
        result = _execute('mutation { ask(input: {text: "BRCA1?", sessionId: "s1"}) }')
        assert result.errors is None
        assert len(_resolver_reached) == 1


class TestAskInputBoundsCannotDriftFromTheCoreContract:
    def test_every_bound_is_the_core_models_own(self) -> None:
        # Mutation that turns this red: replace any
        # `_bound_from_core_query(...)` call with a restated literal and then
        # change `contracts/query.py`. This arm reads the model directly, so
        # the two can only agree by being the same number.
        text_metadata = CoreQuery.model_fields["text"].metadata
        session_metadata = CoreQuery.model_fields["session_id"].metadata
        assert types_module.ASK_TEXT_MIN_LENGTH == next(
            item.min_length for item in text_metadata if hasattr(item, "min_length")
        )
        assert types_module.ASK_TEXT_MAX_LENGTH == next(
            item.max_length for item in text_metadata if hasattr(item, "max_length")
        )
        assert types_module.ASK_SESSION_ID_MAX_LENGTH == next(
            item.max_length for item in session_metadata if hasattr(item, "max_length")
        )

    def test_a_bound_that_vanishes_from_the_core_is_an_import_time_crash(self) -> None:
        # Mutation that turns this red: make `_bound_from_core_query` return
        # a default (say 0, or None) instead of raising when the core stops
        # declaring the bound. A default would silently unbound this
        # surface's field while every other arm here stayed green.
        with pytest.raises(RuntimeError):
            types_module._bound_from_core_query("trace_id", "min_length")

    def test_a_value_the_gate_accepts_is_a_value_the_core_accepts(self) -> None:
        # The end-to-end anti-drift arm, and the one that would have caught
        # the original defect from the other side: whatever the GraphQL layer
        # lets through must survive the model the resolver builds a moment
        # later. Mutation that turns this red: raise ASK_TEXT_MAX_LENGTH
        # above the core's own, which is the masked-internal-error bug
        # reintroduced.
        accepted = _run_ask(
            text="q" * types_module.ASK_TEXT_MAX_LENGTH,
            sessionId="s" * types_module.ASK_SESSION_ID_MAX_LENGTH,
        )
        assert accepted.errors is None
        core = CoreQuery(
            text=_resolver_reached[0].text,
            session_id=_resolver_reached[0].session_id,
            trace_id="t1",
        )
        assert len(core.text) == types_module.ASK_TEXT_MAX_LENGTH


class TestInvalidAskInputIsDeclaredPublicAndStablyCoded:
    def test_it_declares_the_public_marker_that_security_py_requires(self) -> None:
        # Mutation that turns this red: stop descending from SchemaError (or
        # drop the marker from SchemaError). security.py masks by DEFAULT and
        # discloses only a class that declares the marker, so without this
        # the whole fix reverts to a generic internal error.
        assert issubclass(types_module.InvalidAskInput, types_module.SchemaError)
        assert (
            getattr(types_module.InvalidAskInput, security_module.PUBLIC_ERROR_MARKER, False)
            is True
        )

    def test_it_is_a_graphql_error_so_the_marker_is_actually_reachable(self) -> None:
        # Mutation that turns this red: drop the GraphQLError base. A plain
        # exception raised from a scalar's parse_value gets wrapped by
        # graphql-core in an intermediate GraphQLError, and THAT wrapper, not
        # this class, is what security.py's allowlist inspects, so the marker
        # would never be seen and the refusal would be masked. The
        # behavioural proof is the arms above; this arm names the mechanism
        # so a future refactor cannot remove the base "because nothing uses
        # it".
        assert issubclass(types_module.InvalidAskInput, GraphQLError)

    def test_the_published_code_matches_the_one_security_py_derives(self) -> None:
        # Mutation that turns this red: rename the class (the class name IS
        # the wire contract on this surface) or change
        # ASK_INPUT_ERROR_CODE. Either would make the variable path and the
        # literal path publish two different codes for one refusal.
        derived = security_module._error_code_for(types_module.InvalidAskInput("m"))
        assert derived == types_module.ASK_INPUT_ERROR_CODE == "INVALID_ASK_INPUT"

    def test_the_citation_error_is_still_masked(self) -> None:
        # The anti-over-correction arm for the error hierarchy. Mutation that
        # turns this red: hang GraphQLTypeError off SchemaError "for
        # consistency". InvalidCitationPayloadError's message names a
        # citation id taken from internal data, so it must stay masked
        # (F-4.3-A-12).
        assert not issubclass(types_module.GraphQLTypeError, types_module.SchemaError)
        assert (
            getattr(types_module.GraphQLTypeError, security_module.PUBLIC_ERROR_MARKER, False)
            is not True
        )

    def test_schema_py_re_exports_this_exact_base(self) -> None:
        # Mutation that turns this red: declare a SECOND SchemaError in
        # schema.py instead of importing this one. The two would look
        # identical, publish identical codes, and silently fail every
        # `isinstance` check across the seam.
        assert schema_module.SchemaError is types_module.SchemaError
        assert issubclass(schema_module.RunNotFound, types_module.SchemaError)


class TestTheResolverSideHalfOfTheInputFix:
    """`schema.py` builds `contracts.query.Query` from fields this surface
    does not all own, so a ValidationError is still reachable inside the
    resolver even with both scalars in place. These arms cover that half.
    """

    def test_a_caller_supplied_field_selects_a_published_message(self) -> None:
        # Mutation that turns this red: delete a key from
        # ASK_INPUT_MESSAGES_BY_CORE_FIELD, or key the table on the wire
        # name (`sessionId`) rather than the core model's field name
        # (`session_id`), which is what a ValidationError's `loc` actually
        # carries.
        with pytest.raises(Exception) as caught:
            CoreQuery(text="", session_id="s", trace_id="t")
        message = schema_module._caller_fixable_ask_input_message(caught.value)
        assert message == types_module.ASK_INPUT_MESSAGES_BY_CORE_FIELD["text"]
        assert "text" in message

    def test_a_server_supplied_field_is_left_masked(self) -> None:
        # The anti-over-correction arm, and the one that keeps the fix
        # honest. Mutation that turns this red: return a generic
        # caller-facing message for ANY ValidationError. `trace_id` is
        # server-minted, so telling the caller to fix it would be a second
        # wrong error message dressed up as a fix for the first, and it
        # would disclose that an internal field failed.
        with pytest.raises(Exception) as caught:
            CoreQuery(text="q", session_id="s", trace_id="t" * 500)
        assert schema_module._caller_fixable_ask_input_message(caught.value) is None

    def test_no_published_message_carries_anything_from_the_exception(self) -> None:
        # F-4.3-A-12's rule, held for this new error family: a Pydantic
        # ValidationError's string embeds the rejected `input_value`, so a
        # message built from it would carry the caller's rejected content,
        # and in the server-field case internal state, straight back out.
        # Mutation that turns this red: interpolate `exc` into any message.
        hostile = "SECRETSENTINEL" * 200
        with pytest.raises(Exception) as caught:
            CoreQuery(text=hostile, session_id="s", trace_id="t")
        message = schema_module._caller_fixable_ask_input_message(caught.value)
        assert message is not None
        assert "SECRETSENTINEL" not in message
        assert message in types_module.ASK_INPUT_MESSAGES_BY_CORE_FIELD.values()


# ---------------------------------------------------------------------------
# stopRun honesty: F-4.3-A-20.
# ---------------------------------------------------------------------------


class _FakeTask:
    def __init__(self, done: bool) -> None:
        self._done = done

    def done(self) -> bool:
        return self._done


class _FakeRegistry:
    def __init__(self, entry: object) -> None:
        self.entry = entry
        self.cancel_calls: list[str] = []

    def resolve_owned_run(self, run_id: str, owner_id: str) -> object:
        return self.entry

    def cancel_run(self, run_id: str) -> None:
        self.cancel_calls.append(run_id)


def _stop_run(monkeypatch: pytest.MonkeyPatch, *, task_done: bool) -> Any:
    entry = SimpleNamespace(run_id="r1", task=_FakeTask(task_done))
    registry = _FakeRegistry(entry)
    monkeypatch.setattr(schema_module, "default_registry", registry)
    info = SimpleNamespace(context=SimpleNamespace(principal=SimpleNamespace(id="u1")))
    result = asyncio.run(schema_module.Mutation().stop_run(info, "r1"))
    return result, registry


class TestStopRunReportsWhatActuallyHappened:
    def test_stopping_an_in_flight_run_reports_stopped_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The accept arm. Mutation that turns this red: hardcode
        # `stopped=False`, or invert the `not entry.task.done()` read, either
        # of which would make the mutation useless while leaving the honesty
        # arm below green.
        result, registry = _stop_run(monkeypatch, task_done=False)
        assert result.stopped is True
        assert result.run_id == "r1"
        assert registry.cancel_calls == ["r1"]

    def test_stopping_an_already_finished_run_reports_stopped_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE F-4.3-A-20 regression. Mutation that turns this red: restore
        # `stopped=True` as a fixed literal. `cancel_run` is a documented
        # no-op on a run whose task has already finished, so the literal
        # claimed a stop that never happened and contradicted
        # `citations.runCancelled` on this same surface for the same run.
        result, _registry = _stop_run(monkeypatch, task_done=True)
        assert result.stopped is False

    def test_stopping_a_finished_run_is_still_not_an_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second half of the same requirement, and the reason the field
        # was a fixed literal in the first place. Mutation that turns this
        # red: raise on an already-finished run "because stopped is now
        # false". Idempotency requires that a repeated stop not ERROR; it
        # never required saying something untrue.
        result, registry = _stop_run(monkeypatch, task_done=True)
        assert result.run_id == "r1"
        assert registry.cancel_calls == ["r1"]
