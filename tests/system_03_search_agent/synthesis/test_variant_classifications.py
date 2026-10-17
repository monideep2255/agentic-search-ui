"""Card 30 step 2b: ClinVar's classification of each listed graph variant.

The resolver reads `germline_classification.description` from one ESummary
per 50 `ClinVar:` CURIEs and joins it back by the record's own id. Every
failure class leaves the CURIE out, so the caller keeps today's row. The fake
transport stands in for `ncbi_eutils_actions.summary`, which is where the
rate pool and the 20-call ceiling live.
"""

from __future__ import annotations

import asyncio

import pytest

from system_03_search_agent.harness import call_budget
from system_03_search_agent.synthesis import variant_classifications as vc
from system_03_search_agent.synthesis.answer_layout import (
    VARIANT_CLASSIFICATION_NOTE,
    variant_classification_note,
    with_variant_classification,
)
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord


def _record(uid: str, description: object = "Pathogenic") -> NcbiEfetchRecord:
    fields = (
        {} if description is None else {"germline_classification": {"description": description}}
    )
    return NcbiEfetchRecord(id=uid, db="clinvar", fields=fields)


def _ok(*records: NcbiEfetchRecord) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="ok",
        action="summary",
        records=list(records),
        record_count=len(records),
        truncated=False,
    )


class _Transport:
    def __init__(self, reply) -> None:
        self.reply = reply
        self.calls: list[list[str]] = []

    async def __call__(self, params):
        self.calls.append(list(params.ids))
        reply = self.reply
        if callable(reply):
            reply = reply(params.ids)
        if isinstance(reply, BaseException):
            raise reply
        if asyncio.iscoroutine(reply):
            return await reply
        return reply


def _install(monkeypatch, reply) -> _Transport:
    fake = _Transport(reply)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", fake)
    return fake


def _run(curies):
    return asyncio.run(vc.resolve_variant_classifications(curies))


def test_classification_joins_by_record_id_with_records_shuffled(monkeypatch) -> None:
    fake = _install(
        monkeypatch,
        _ok(
            _record("3", "Uncertain significance"),
            _record("1", "Pathogenic"),
            _record("2", "Benign"),
        ),
    )
    got = _run(["ClinVar:1", "ClinVar:2", "ClinVar:3"])
    assert got == {
        "ClinVar:1": "Pathogenic",
        "ClinVar:2": "Benign",
        "ClinVar:3": "Uncertain significance",
    }
    assert len(fake.calls) == 1


def test_a_dropped_record_is_absent_not_shifted(monkeypatch) -> None:
    _install(monkeypatch, _ok(_record("3", "Benign"), _record("1", "Pathogenic")))
    got = _run(["ClinVar:1", "ClinVar:2", "ClinVar:3"])
    assert got == {"ClinVar:1": "Pathogenic", "ClinVar:3": "Benign"}
    assert "ClinVar:2" not in got


def test_two_records_with_one_id_and_different_values_are_ambiguous(monkeypatch) -> None:
    _install(monkeypatch, _ok(_record("1", "Pathogenic"), _record("1", "Benign"), _record("2")))
    got = _run(["ClinVar:1", "ClinVar:2"])
    assert got == {"ClinVar:2": "Pathogenic"}


def test_two_records_with_one_id_and_one_value_are_kept(monkeypatch) -> None:
    _install(monkeypatch, _ok(_record("1", "Pathogenic"), _record("1", "Pathogenic")))
    assert _run(["ClinVar:1"]) == {"ClinVar:1": "Pathogenic"}


def test_the_value_is_verbatim_apart_from_surrounding_space(monkeypatch) -> None:
    text = "Conflicting classifications of pathogenicity"
    _install(monkeypatch, _ok(_record("1", f"  {text} ")))
    assert _run(["ClinVar:1"]) == {"ClinVar:1": text}


@pytest.mark.parametrize(
    "reply",
    [
        TimeoutError("slow"),
        RuntimeError("boom"),
        ncbi_eutils_actions._error_output("summary", "bad"),
        ncbi_eutils_actions._empty_output("summary"),
    ],
    ids=["timeout", "exception", "error", "empty"],
)
def test_every_failure_class_leaves_the_row_alone(monkeypatch, reply) -> None:
    _install(monkeypatch, reply)
    assert _run(["ClinVar:1", "ClinVar:2"]) == {}


@pytest.mark.parametrize(
    "description",
    [None, "", "   ", 7, ["Pathogenic"], {"a": 1}, "x" * 101, "Patho\ngenic", "Patho\x00genic"],
)
def test_an_empty_or_odd_value_is_unread(monkeypatch, description) -> None:
    _install(monkeypatch, _ok(_record("1", description), _record("2", "Benign")))
    assert _run(["ClinVar:1", "ClinVar:2"]) == {"ClinVar:2": "Benign"}


def test_a_block_that_is_not_a_mapping_is_unread(monkeypatch) -> None:
    odd = NcbiEfetchRecord(id="1", db="clinvar", fields={"germline_classification": "Pathogenic"})
    _install(monkeypatch, _ok(odd))
    assert _run(["ClinVar:1"]) == {}


def test_a_hung_request_is_cut_off(monkeypatch) -> None:
    async def _hang():
        await asyncio.sleep(30)

    monkeypatch.setattr(vc, "_REQUEST_TIMEOUT_S", 0.05)
    _install(monkeypatch, lambda ids: _hang())
    assert _run(["ClinVar:1"]) == {}


def test_one_request_per_fifty_and_no_more_than_two(monkeypatch) -> None:
    fake = _install(monkeypatch, lambda ids: _ok(*(_record(i, "Benign") for i in ids)))
    got = _run([f"ClinVar:{n}" for n in range(1, 41)])
    assert len(fake.calls) == 1 and len(got) == 40
    fake.calls.clear()
    got = _run([f"ClinVar:{n}" for n in range(1, 52)])
    assert sorted(len(c) for c in fake.calls) == [1, 50] and len(got) == 51
    fake.calls.clear()
    _run([f"ClinVar:{n}" for n in range(1, 400)])
    assert len(fake.calls) == 2


def test_duplicates_and_other_vocabularies_cost_nothing(monkeypatch) -> None:
    fake = _install(monkeypatch, _ok(_record("1")))
    assert _run(["ClinVar:1", "ClinVar:1", "dbSNP:rs1", "ClinVar:abc", ""]) == {
        "ClinVar:1": "Pathogenic"
    }
    assert fake.calls == [["1"]]


def test_no_variants_makes_no_request(monkeypatch) -> None:
    fake = _install(monkeypatch, _ok())
    assert _run([]) == {}
    assert _run(["MedGen:C0346153"]) == {}
    assert fake.calls == []


def test_at_the_ceiling_no_request_is_made(monkeypatch) -> None:
    fake = _install(monkeypatch, _ok(_record("1")))

    async def _at_ceiling():
        with call_budget.query_budget_scope("lookup"):
            for _ in range(call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY):
                call_budget.charge_one_call(tool="t", layer=2)
            return await vc.resolve_variant_classifications(["ClinVar:1"])

    assert asyncio.run(_at_ceiling()) == {}
    assert fake.calls == []


def test_one_call_under_the_ceiling_still_asks(monkeypatch) -> None:
    fake = _install(monkeypatch, _ok(_record("1")))

    async def _below():
        with call_budget.query_budget_scope("lookup"):
            for _ in range(call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY - 1):
                call_budget.charge_one_call(tool="t", layer=2)
            return await vc.resolve_variant_classifications(["ClinVar:1"])

    assert asyncio.run(_below()) == {"ClinVar:1": "Pathogenic"}
    assert len(fake.calls) == 1


# ---------------------------------------------------------------- the note


def _finding(curie: str, *, field: str = "name", layer: str = "layer_1_graph") -> SynthFinding:
    return SynthFinding(
        ref_index=1,
        citation_id=f"c-{curie}",
        layer=layer,
        tool="t",
        field=field,
        field_value="v",
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
        entity_type="SequenceVariant" if layer == "layer_1_graph" else "ClinVar record",
        curie=curie,
    )


def test_the_line_stays_until_every_shown_variant_has_a_classification() -> None:
    findings = [_finding("ClinVar:1"), _finding("ClinVar:2")]
    assert variant_classification_note(findings) == VARIANT_CLASSIFICATION_NOTE
    assert variant_classification_note(findings, set()) == VARIANT_CLASSIFICATION_NOTE
    assert variant_classification_note(findings, {"ClinVar:1"}) == VARIANT_CLASSIFICATION_NOTE
    assert variant_classification_note(findings, {"ClinVar:1", "ClinVar:2"}) is None


def test_a_classified_curie_that_is_not_shown_does_not_count() -> None:
    findings = [_finding("ClinVar:1"), _finding("ClinVar:2")]
    assert variant_classification_note(findings, {"ClinVar:1", "ClinVar:9"}) == (
        VARIANT_CLASSIFICATION_NOTE
    )


def test_a_variant_without_a_curie_keeps_the_line() -> None:
    findings = [_finding("ClinVar:1"), _finding("")]
    assert variant_classification_note(findings, {"ClinVar:1", ""}) == VARIANT_CLASSIFICATION_NOTE


def test_row_fields_gain_the_classification_only_for_a_graph_variant() -> None:
    row = {"name": "c.1A>G"}
    graph = _finding("ClinVar:1")
    live = _finding("ClinVar:1", layer="layer_2_api")
    got = with_variant_classification(graph, row, {"ClinVar:1": "Pathogenic"})
    assert got == {"name": "c.1A>G", vc.CLASSIFICATION_ROW_FIELD: "Pathogenic"}
    assert row == {"name": "c.1A>G"}
    assert with_variant_classification(live, row, {"ClinVar:1": "Pathogenic"}) is row
    assert with_variant_classification(graph, row, {"ClinVar:2": "Benign"}) is row
    assert with_variant_classification(graph, row, None) is row
