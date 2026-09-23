"""Fix-plan item 2 (2026-09-22): an NCBI accession in the question is resolved
live with the records it links to, its summaries are planned with no graph
call, and an accession NCBI does not have is answered with "not found".

Drives the real `think_node`, `plan_node` and `write_node` with only the
model and the NCBI actions faked, the way `test_coordinate_window_wiring.py`
does, and the real act-side row shaping. No network anywhere.

Coverage statement, per `goal-contracts`: Think with a BioProject NCBI has
(the uid and the three link lists on the state, the disclosure in the
narrative, the model's spans not confirmed, no clarification), with one NCBI
does not have (the not-found answer as the clarification, nothing on the
state), and with a plain gene question (untouched); Plan with an accession
plan (four NCBI summaries in order, no graph call, the plan event naming the
accession) and without one (the graph call first, as before); Write's
refusal branch with a plan whose first call is an NCBI call, which used to
assume a graph call there; the row shaping for the four summary purposes.
What this file does NOT exercise: the live NCBI term and link names,
verified in `testing/Developer/reports/2026-09-22_bioproject_accession/`.

Populate checks: every positive arm has a sibling input on the same fake
that must NOT appear (a question with no accession, a link database with no
ids), so an arm cannot pass on an empty result.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import accession as accession_module
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

PROJECT_QUESTION = (
    "For BioProject PRJNA31257, list the BioSamples, the SRA runs and any genome "
    "assemblies, and tell me how to retrieve each."
)
UNKNOWN_QUESTION = "What is in BioProject PRJNA999999999?"
GENE_QUESTION = "Which diseases are associated with BRCA1?"

# The probe's real ids: uid 31257, one BioSample, one SRA run, one assembly.
LINKS = {"biosample": ["12121739"], "sra": ["8317276"], "assembly": ["11968211"]}


class _Spy:
    """Fakes for the NCBI search and link actions, recording every input."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, known: bool = True) -> None:
        self.searches: list[Any] = []
        self.links: list[Any] = []

        async def _search(tool_input: Any, **kwargs: Any) -> Any:
            self.searches.append(tool_input)
            if tool_input.db == "bioproject" and known:
                return SimpleNamespace(
                    status="ok", records=[SimpleNamespace(id="", fields={"idlist": ["31257"], "idlist_count": 1})]
                )
            return SimpleNamespace(status="empty", records=[])

        async def _link(tool_input: Any, **kwargs: Any) -> Any:
            self.links.append(tool_input)
            ids = LINKS.get(tool_input.db, [])
            if not ids:
                return SimpleNamespace(status="empty", records=[])
            return SimpleNamespace(status="ok", records=[SimpleNamespace(id=i, db=tool_input.db) for i in ids])

        monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
        monkeypatch.setattr(ncbi_eutils_actions, "link", _link)


def _install_model(monkeypatch: pytest.MonkeyPatch, entities: list[tuple[str, str]] | None = None) -> list[str]:
    classification = graph_module._ThinkClassification(
        query_class="multi_hop",
        entities=[graph_module._ThinkExtractedEntity(text=t, entity_type=k) for t, k in (entities or [])],
        narrative="Asks for the records under a project.",
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
    query = Query(text=text, session_id="s-acc", trace_id="t-acc", user_id=None)
    state: dict[str, Any] = {
        "query": query,
        "harness": harness_module.Harness(trace_id="t-acc"),
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
async def test_a_known_bioproject_is_resolved_with_its_links_and_the_models_spans_are_not_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _install_model(monkeypatch, entities=[("BioSamples", "gene"), ("SRA", "gene")])
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state(PROJECT_QUESTION))
    plan = result["accession_plan"]
    assert plan.uid == "31257"
    assert plan.record.kind == "bioproject" and plan.record.value == "PRJNA31257"
    assert plan.linked == LINKS
    assert result["resolved_entities"] == []
    assert result.get("clarification_needed") is None
    assert asked == [], asked
    assert [s.db for s in spy.searches] == ["bioproject"]
    assert [link.db for link in spy.links] == ["biosample", "sra", "assembly"]
    think = next(e for e in result["events"] if e.type == "think")
    assert "PRJNA31257" in think.payload["narrative"] and "1 BioSample" in think.payload["narrative"]


@pytest.mark.asyncio
async def test_an_accession_ncbi_does_not_have_is_answered_with_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch)
    spy = _Spy(monkeypatch, known=False)
    result = await graph_module.think_node(_state(UNKNOWN_QUESTION))
    assert "was not found" in (result.get("clarification_needed") or "")
    assert "accession_plan" not in result
    assert spy.links == [], "no link is asked for a record that was not found"


@pytest.mark.asyncio
async def test_a_question_without_an_accession_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model(monkeypatch)
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state(GENE_QUESTION))
    assert "accession_plan" not in result
    assert [s for s in spy.searches if s.db == "bioproject"] == []


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _accession_plan() -> Any:
    record = accession_module.parse_accession(PROJECT_QUESTION)
    assert record is not None
    return graph_module._AccessionPlan(record=record, uid="31257", linked=dict(LINKS))


@pytest.mark.asyncio
async def test_an_accession_plans_the_four_summaries_and_no_graph_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    state = _state(PROJECT_QUESTION, resolved_entities=[], query_class="multi_hop", accession_plan=_accession_plan())
    result = await graph_module.plan_node(state)
    calls = result["tool_calls"]
    assert all(isinstance(c, graph_module._PlannedNcbiEfetchToolCall) for c in calls), calls
    assert [c.purpose for c in calls] == [
        "bioproject_summary", "biosample_summary", "sra_summary", "assembly_summary",
    ]
    assert [c.ncbi_efetch_input.root.action for c in calls] == ["summary"] * 4
    assert calls[1].ncbi_efetch_input.root.ids == ["12121739"]
    plan = next(e for e in result["events"] if e.type == "plan")
    assert "PRJNA31257" in plan.payload["narrative"]
    assert [c["tool"] for c in plan.payload["tool_calls"]] == ["ncbi_efetch"] * 4
    assert all(c.get("persona") for c in plan.payload["tool_calls"]), "helpers are stamped as on any plan"


@pytest.mark.asyncio
async def test_without_an_accession_the_graph_call_is_still_first(
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
# Write: the refusal branch no longer assumes a graph call at index 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_refusal_with_an_ncbi_call_first_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from tests.system_03_search_agent.core.test_write_answer_structure import _install
    from tests.system_03_search_agent.core.test_write_answer_structure import _state as _write_state

    _install(monkeypatch, lambda _lines: "ok")
    state = _write_state("researcher")
    planned = graph_module._planned_from_breadth(
        accession_module.plan_summary_calls(_accession_plan().record, "31257", {})[0]
    )
    state["tool_calls"] = [planned]
    state["findings"] = [
        Finding(
            call_id=planned.tool_call.call_id, tool="ncbi_efetch", layer="layer_2_api",
            source="structured_pass_through",
            structured_fields={"status": "error", "row_count": 0, "total_available": 0, "truncated": False, "rows": [], "error": "summary: 0 record(s)"},
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        )
    ]
    state["findings_count"] = 1
    state["failed_searches"] = [{"tool": "ncbi_efetch", "layer": "layer_2_api", "reason": "summary: 0 record(s)"}]
    result = await graph_module.write_node(state)
    done = next(e for e in result["events"] if e.type == "done")
    assert done.payload["trust_outcome"] == "refuse"


# ---------------------------------------------------------------------------
# Act: the row shaping for the four summary purposes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("db", "purpose", "fields", "leading", "withheld"),
    [
        ("bioproject", "bioproject_summary", {"project_acc": "PRJNA31257", "project_title": "Homo sapiens", "project_type": "Primary submission", "project_data_type": "Genome sequencing", "organism_name": "Homo sapiens", "registration_date": "2009/01/01"}, "project_title", "project_type"),
        ("biosample", "biosample_summary", {"accession": "SAMN12121739", "title": "Human reference", "organism": "Homo sapiens", "package": "Generic", "publicationdate": "2019/06/26"}, "title", "package"),
        ("sra", "sra_summary", {"runs": "<Run acc=\"SRR9496657\" total_spots=\"1\"/>", "createdate": "2019/06/26", "expxml": "<Summary/>"}, "runs", "expxml"),
        ("assembly", "assembly_summary", {"assemblyaccession": "GCF_000001405.40", "assemblyname": "GRCh38.p14", "assemblystatus": "Chromosome", "organism": "Homo sapiens", "coverage": "0", "submissiondate": "2022/02/03"}, "assemblyname", "coverage"),
    ],
)
def test_a_summary_record_becomes_a_row_led_by_the_field_a_person_recognises(
    db: str, purpose: str, fields: dict[str, Any], leading: str, withheld: str
) -> None:
    record = NcbiEfetchRecord(id="1", db=db, fields=fields, source_url=f"https://www.ncbi.nlm.nih.gov/{db}/1")
    output = NcbiEfetchOutput(status="ok", action="summary", records=[record], record_count=1, total_available=1, truncated=False)
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(output, purpose)
    (row,) = shaped["rows"]
    assert next(iter(row["fields"])) == leading, row["fields"]
    assert withheld not in row["fields"]
    assert set(row["fields"]) <= set(graph_module._BREADTH_FIELDS_BY_PURPOSE[purpose])
    assert row["source_url"].endswith(f"/{db}/1")


def test_an_sra_summary_row_shows_the_run_accessions_not_the_markup() -> None:
    """Measured live on the first accession run: the answer read
    `<Run acc="SRR9496657" total_spots="118" .../>` where a person wants
    the accession."""
    markup = (
        '<Run acc="SRR9496657" total_spots="118" total_bases="95317" load_done="true"/>'
        '<Run acc="SRR9496658" total_spots="2"/><Run acc="SRR9496657"/>'
    )
    record = NcbiEfetchRecord(id="1", db="sra", fields={"runs": markup, "createdate": "2019/06/26"}, source_url="https://www.ncbi.nlm.nih.gov/sra/1")
    output = NcbiEfetchOutput(status="ok", action="summary", records=[record], record_count=1, total_available=1, truncated=False)
    (row,) = graph_module._ncbi_efetch_output_to_structured_fields(output, "sra_summary")["rows"]
    assert row["fields"]["runs"] == "SRR9496657, SRR9496658"
    assert graph_module._sra_run_accessions("   no markup here  ") == "no markup here"
    plain = NcbiEfetchRecord(id="2", db="sra", fields={"runs": markup}, source_url="https://www.ncbi.nlm.nih.gov/sra/2")
    other = NcbiEfetchOutput(status="ok", action="summary", records=[plain], record_count=1, total_available=1, truncated=False)
    (untouched,) = graph_module._ncbi_efetch_output_to_structured_fields(other, "")["rows"]
    assert untouched["fields"]["runs"] == markup, "only the sra_summary purpose reshapes the field"
