"""Golden question G-035 (2026-09-22): a Pathogen Detection isolate question is
recognised in Think, planned as the isolate search plus the organism's
Taxonomy record with no graph call, shaped into isolate rows at Act, and
told to the reader with its count under the answer at Write.

Drives the real `think_node`, `plan_node`, `act_node` and `write_node` with
only the model and the tools faked, the way `test_accession_wiring.py` does.
No network anywhere.

Coverage statement, per `goal-contracts`: Think with the golden question (the
organism on the state as NCBITaxon:562, the disclosure in the narrative, the
model's spans not confirmed, no clarification), with an organism and no gene
(the gene question, nothing on the state), with a gene and no organism (the
organism question), and with a plain gene question (untouched, the populate
check); Plan with an isolate question (the isolate search at index 0, the
Taxonomy summary at index 1, no graph call, the plan event naming the
organism) and without one (the graph call first, as before); Act's row
shaping (strain leads, the accession beside it, the genotype list joined, the
tool's own count and cut carried, twenty rows at most); Write's count
sentence under an answer, exact when the scan finished and "at least" when
it did not, and absent on a question that is not this shape. What this file
does NOT exercise: the tool's own scan (`test_pathogen_detection.py`) and the
live snapshot (`test_pathogen_detection_premise.py`).

Populate checks: every positive arm has a sibling input on the same fake
that must NOT produce the result (a question with no isolate word, a state
with no isolate question), so an arm cannot pass on an empty result.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core import isolate_search
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PathogenDetectionOutput,
    PathogenIsolate,
)

GOLDEN_QUESTION = (
    "What Escherichia coli isolates in Pathogen Detection carry extended-spectrum "
    "beta-lactamase genes?"
)
NO_GENE_QUESTION = "Which E. coli isolates are in Pathogen Detection?"
NO_ORGANISM_QUESTION = "Which isolates in Pathogen Detection carry blaKPC?"
GENE_QUESTION = "Which diseases are associated with BRCA1?"

ISOLATE_URL = "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:{acc}"


def _isolate(acc: str, strain: str | None, genes: list[str]) -> PathogenIsolate:
    return PathogenIsolate(
        biosample_acc=acc,
        strain=strain,
        geo_loc_name="USA:AZ",
        collection_date="2013-03-05",
        amr_genotypes=genes,
        source_url=ISOLATE_URL.format(acc=acc),
    )


def _search_output(
    isolates: list[PathogenIsolate], total: int, *, complete: bool = True
) -> PathogenDetectionOutput:
    return PathogenDetectionOutput(
        status="ok" if isolates else "empty",
        mode="isolate_search",
        pdg_snapshot="PDG000000004.6314",
        isolates=isolates,
        isolate_count=len(isolates),
        total_available=total,
        truncated=len(isolates) < total or not complete,
        rows_scanned=584_433,
        scan_complete=complete,
    )


def _install_model(
    monkeypatch: pytest.MonkeyPatch, entities: list[tuple[str, str]] | None = None
) -> list[str]:
    classification = graph_module._ThinkClassification(
        query_class="exploratory",
        entities=[graph_module._ThinkExtractedEntity(text=t, entity_type=k) for t, k in (entities or [])],
        narrative="Asks for isolates carrying a gene family.",
    )
    asked: list[str] = []

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(content=classification.model_dump_json())

    async def _no_gene(symbol: str, *, taxon: str = "human") -> str | None:
        asked.append(symbol)
        return None

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    return asked


def _state(text: str, **extra: Any) -> dict[str, Any]:
    query = Query(text=text, session_id="s-iso", trace_id="t-iso", user_id=None)
    state: dict[str, Any] = {
        "query": query,
        "harness": harness_module.Harness(trace_id="t-iso"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }
    state.update(extra)
    return state


# ---------------------------------------------------------------------------
# Think
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_golden_question_resolves_the_organism_and_confirms_none_of_the_models_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _install_model(monkeypatch, entities=[("ESBL", "gene"), ("Pathogen Detection", "gene")])
    result = await graph_module.think_node(_state(GOLDEN_QUESTION))
    question = result["isolate_question"]
    assert question.organism.curie == "NCBITaxon:562"
    assert question.prefixes == ("blaCTX-M",)
    assert [e.curie for e in result["resolved_entities"]] == ["NCBITaxon:562"]
    assert result["resolved_entities"][0].text == "Escherichia coli"
    assert result.get("clarification_needed") is None
    assert asked == [], "the model's gene-shaped spans are not confirmed live on this shape"
    think = next(e for e in result["events"] if e.type == "think")
    assert "blaCTX-M" in think.payload["narrative"]
    assert "blaTEM and blaSHV alleles were not searched" in think.payload["narrative"]


@pytest.mark.asyncio
async def test_an_organism_with_no_gene_is_asked_which_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model(monkeypatch)
    result = await graph_module.think_node(_state(NO_GENE_QUESTION))
    assert result.get("clarification_needed") == isolate_search.GENE_QUESTION
    assert "isolate_question" not in result


@pytest.mark.asyncio
async def test_a_gene_with_no_organism_is_asked_which_organism(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model(monkeypatch)
    result = await graph_module.think_node(_state(NO_ORGANISM_QUESTION))
    assert result.get("clarification_needed") == isolate_search.ORGANISM_QUESTION
    assert "isolate_question" not in result
    assert result["resolved_entities"] == []


@pytest.mark.asyncio
async def test_a_plain_gene_question_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _install_model(monkeypatch, entities=[("BRCA1", "gene")])
    result = await graph_module.think_node(_state(GENE_QUESTION))
    assert "isolate_question" not in result
    assert "BRCA1" in asked, "the model's spans ARE confirmed on an ordinary question"


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _question() -> isolate_search.IsolateQuestion:
    question = isolate_search.parse_isolate_question(GOLDEN_QUESTION)
    assert question is not None
    return question


@pytest.mark.asyncio
async def test_an_isolate_question_plans_the_search_then_the_taxonomy_record_and_no_graph_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    state = _state(
        GOLDEN_QUESTION,
        resolved_entities=[EventResolvedEntity(text="Escherichia coli", curie="NCBITaxon:562", confidence=1.0)],
        query_class="exploratory",
        isolate_question=_question(),
    )
    result = await graph_module.plan_node(state)
    calls = result["tool_calls"]
    assert isinstance(calls[0], graph_module._PlannedLayerToolCall)
    assert calls[0].tool_call.tool == "pathogen_detection" and calls[0].purpose == "isolate_search"
    assert calls[0].tool_input.root.taxon == "Escherichia_coli_Shigella"
    assert calls[0].tool_input.root.amr_gene_prefixes == ["blaCTX-M"]
    assert isinstance(calls[1], graph_module._PlannedNcbiEfetchToolCall)
    assert calls[1].purpose == "taxonomy_summary"
    assert calls[1].ncbi_efetch_input.root.db == "taxonomy"
    assert calls[1].ncbi_efetch_input.root.ids == ["562"]
    assert len(calls) == 2
    assert not any(isinstance(c, graph_module._PlannedToolCall) for c in calls), "no graph call"
    plan = next(e for e in result["events"] if e.type == "plan")
    assert "Escherichia coli" in plan.payload["narrative"] and "blaCTX-M" in plan.payload["narrative"]
    assert [c["tool"] for c in plan.payload["tool_calls"]] == ["pathogen_detection", "ncbi_efetch"]
    assert all(c.get("persona") for c in plan.payload["tool_calls"])


@pytest.mark.asyncio
async def test_without_an_isolate_question_the_graph_call_is_still_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    state = _state(
        GENE_QUESTION,
        resolved_entities=[EventResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.0)],
        query_class="single_hop",
    )
    result = await graph_module.plan_node(state)
    assert isinstance(result["tool_calls"][0], graph_module._PlannedToolCall)


# ---------------------------------------------------------------------------
# Act: the row shaping
# ---------------------------------------------------------------------------


def test_an_isolate_becomes_a_row_led_by_its_strain_with_the_tools_own_count() -> None:
    output = _search_output(
        [
            _isolate("SAMN02442784", "AZ-TG59983", ["acrF", "blaCTX-M-15", "mdtM"]),
            _isolate("SAMN02442782", None, ["blaCTX-M-27"]),
            _isolate("SAMN00000001", "NOURL", ["blaCTX-M-1"]).model_copy(update={"source_url": None}),
        ],
        total=21_004,
    )
    shaped = graph_module._layer_tool_output_to_structured_fields("pathogen_detection", output)
    assert shaped["status"] == "ok"
    assert [r["fields"]["biosample_acc"] for r in shaped["rows"]] == ["SAMN02442782", "SAMN02442784"]
    first, second = shaped["rows"]
    assert first["fields"]["name"] == "SAMN02442782", "no strain: the accession leads"
    assert second["fields"]["name"] == "AZ-TG59983"
    assert second["fields"]["amr_genotypes"] == "acrF, blaCTX-M-15, mdtM"
    assert second["source_url"].endswith("biosample_acc:SAMN02442784")
    assert second["node_or_edge_type"] == "Pathogen Detection isolate"
    assert shaped["row_count"] == 2
    assert shaped["total_available"] == 21_004
    assert shaped["truncated"] is True


def test_the_row_cap_is_twenty_and_a_full_scan_of_twenty_is_not_a_cut() -> None:
    twenty = [_isolate(f"SAMN{i:08d}", f"S{i}", ["blaCTX-M-15"]) for i in range(20)]
    shaped = graph_module._layer_tool_output_to_structured_fields(
        "pathogen_detection", _search_output(twenty, total=20)
    )
    assert shaped["row_count"] == 20 and shaped["truncated"] is False
    more = twenty + [_isolate("SAMN99999999", "S99", ["blaCTX-M-15"])]
    shaped = graph_module._layer_tool_output_to_structured_fields(
        "pathogen_detection", _search_output(more, total=21)
    )
    assert shaped["row_count"] == 20 and shaped["truncated"] is True


def test_a_search_that_found_nothing_is_empty_not_error() -> None:
    shaped = graph_module._layer_tool_output_to_structured_fields(
        "pathogen_detection", _search_output([], total=0)
    )
    assert shaped["status"] == "empty" and shaped["rows"] == [] and shaped["total_available"] == 0


# ---------------------------------------------------------------------------
# Write: the count under the answer
# ---------------------------------------------------------------------------


def test_the_count_note_is_exact_when_the_scan_finished_and_at_least_when_it_did_not() -> None:
    kept = [_isolate(f"SAMN{i:08d}", f"S{i}", ["blaCTX-M-15"]) for i in range(20)]
    state: dict[str, Any] = {
        "isolate_question": _question(),
        "layer3_raw_outputs": {"pd-1": _search_output(kept, total=21_004)},
    }
    assert graph_module._isolate_count_note(state) == (
        "Pathogen Detection lists 21,004 Escherichia coli isolates with these genes; "
        "the first 20 in the snapshot are shown."
    )
    state["layer3_raw_outputs"] = {"pd-1": _search_output(kept, total=500, complete=False)}
    assert graph_module._isolate_count_note(state).startswith("Pathogen Detection lists at least 500 ")
    state["layer3_raw_outputs"] = {"pd-1": _search_output([], total=0)}
    assert graph_module._isolate_count_note(state) == (
        "Pathogen Detection lists 0 Escherichia coli isolates with these genes, all shown."
    )


def test_the_count_note_is_absent_off_this_shape_and_on_a_failed_search() -> None:
    kept = [_isolate("SAMN00000001", "S1", ["blaCTX-M-15"])]
    assert graph_module._isolate_count_note({"layer3_raw_outputs": {"pd-1": _search_output(kept, 1)}}) is None
    failed = _search_output([], total=0).model_copy(update={"status": "timeout", "error": "cut"})
    assert graph_module._isolate_count_note(
        {"isolate_question": _question(), "layer3_raw_outputs": {"pd-1": failed}}
    ) is None


@pytest.mark.asyncio
async def test_write_puts_the_count_under_an_isolate_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from tests.system_03_search_agent.core.test_write_answer_structure import _install
    from tests.system_03_search_agent.core.test_write_answer_structure import _state as _write_state

    _install(monkeypatch, lambda lines: " ".join(f"Isolate {body}." for body in lines.values()))
    kept = [_isolate("SAMN02442784", "AZ-TG59983", ["acrF", "blaCTX-M-15"])]
    output = _search_output(kept, total=21_004)
    shaped = graph_module._layer_tool_output_to_structured_fields("pathogen_detection", output)
    state = _write_state("researcher")
    state["query"] = Query(text=GOLDEN_QUESTION, session_id="s-iso", trace_id="t-iso", user_id=None)
    state["isolate_question"] = _question()
    state["layer3_raw_outputs"] = {"pd-1": output}
    state["findings"] = [
        Finding(
            call_id="pd-1", tool="pathogen_detection", layer="layer_2_api",
            source="structured_pass_through", structured_fields=shaped,
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        )
    ]
    state["findings_count"] = 1
    result = await graph_module.write_node(state)
    tokens = [e.payload["text"] for e in result["events"] if e.type == "token"]
    assert any("Pathogen Detection lists 21,004 Escherichia coli isolates" in t for t in tokens), tokens
    done = next(e for e in result["events"] if e.type == "done")
    assert done.payload["trust_outcome"] != "refuse"
