"""Fix-plan item 1 (2026-09-22): a chromosome window in the question is
resolved to the genes under it, asked about when its assembly is missing,
and answered with the dbVar and ClinVar records that overlap it.

Drives the real `think_node` and `plan_node` with only the model and the
NCBI actions faked, the way `test_think_disease_and_organism.py` does, and
the real act-side row shaping. No network anywhere.

Coverage statement, per `goal-contracts`: Think with GRCh38 (genes resolved,
the non-overlapping gene dropped, the disclosure in the narrative, the window
on the state), with no assembly (the assembly question, no lookup issued),
with GRCh37 (no gene lookup, the window still on the state), and with a
failing transport (empty, no crash); Plan with and without a window (the two
overlap calls at index 1 and 2, or none); the row shaping for both overlap
purposes (allowlisted fields only, the record URL kept). What this file does
NOT exercise: the live NCBI term, verified in
`testing/Developer/reports/2026-09-22_coordinate_range/`, and Write, which
sees these rows as it sees any breadth result.

Populate checks: every positive arm has a sibling input on the same fake
that must NOT appear (a gene outside the window, a question without a
window), so an arm cannot pass on an empty result.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import coordinate_window
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

BRCA1_WINDOW = "chr17:43,044,295-43,125,364"
GRCH38_QUESTION = (
    "What ACMG-relevant evidence is available for a copy number variant spanning "
    f"{BRCA1_WINDOW} on GRCh38? List the overlapping genes, dbVar records and ClinVar entries."
)
NO_ASSEMBLY_QUESTION = f"What is under {BRCA1_WINDOW}?"
GRCH37_QUESTION = "What is under chr17:41,196,312-41,277,500 on GRCh37?"

# Two Gene ESummary records as `ncbi_eutils_actions` shapes them: BRCA1, whose
# GRCh38 placement overlaps the window, and TP53, on the same chromosome and
# outside it, which a range search may still return.
GENE_SUMMARIES = {
    "672": {
        "name": "BRCA1",
        "description": "BRCA1 DNA repair associated",
        "chromosome": "17",
        "genomicinfo": [
            {"chraccver": "NC_000017.11", "chrstart": 43044294, "chrstop": 43125482}
        ],
    },
    "7157": {
        "name": "TP53",
        "description": "tumor protein p53",
        "chromosome": "17",
        "genomicinfo": [
            {"chraccver": "NC_000017.11", "chrstart": 7687537, "chrstop": 7661778}
        ],
    },
}


class _Spy:
    """Fakes for the NCBI search and summary actions, recording every input."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> None:
        self.searches: list[Any] = []
        self.summaries: list[Any] = []

        async def _search(tool_input: Any, **kwargs: Any) -> Any:
            self.searches.append(tool_input)
            if fail:
                raise RuntimeError("transport down")
            if tool_input.db == "gene":
                ids = list(GENE_SUMMARIES)
                return SimpleNamespace(
                    status="ok",
                    records=[SimpleNamespace(id="", fields={"idlist": ids, "idlist_count": len(ids)})],
                )
            return SimpleNamespace(status="empty", records=[])

        async def _summary(tool_input: Any, **kwargs: Any) -> Any:
            self.summaries.append(tool_input)
            if fail:
                raise RuntimeError("transport down")
            return SimpleNamespace(
                status="ok",
                records=[
                    SimpleNamespace(id=uid, fields=dict(GENE_SUMMARIES[uid]))
                    for uid in tool_input.ids
                    if uid in GENE_SUMMARIES
                ],
            )

        monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
        monkeypatch.setattr(ncbi_eutils_actions, "summary", _summary)


def _install_model(monkeypatch: pytest.MonkeyPatch, query_class: str = "multi_hop") -> None:
    classification = graph_module._ThinkClassification(
        query_class=query_class,
        entities=[],
        narrative="Asks for the evidence under a chromosome window.",
    )

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(content=classification.model_dump_json())

    async def _no_gene(symbol: str, *, taxon: str = "human") -> str | None:
        return None

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")


def _state(text: str, **extra: Any) -> dict[str, Any]:
    query = Query(text=text, session_id="s-window", trace_id="t-window", user_id=None)
    state: dict[str, Any] = {
        "query": query,
        "harness": harness_module.Harness(trace_id="t-window"),
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
async def test_a_grch38_window_resolves_the_genes_under_it_and_only_those(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch)
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state(GRCH38_QUESTION))
    entities = result["resolved_entities"]
    assert [(e.text, e.curie) for e in entities] == [("BRCA1", "NCBIGene:672")], entities
    # Populate check: TP53 was returned by the range search and is outside
    # the window, so it must be absent.
    assert "NCBIGene:7157" not in [e.curie for e in entities]
    assert result.get("clarification_needed") is None
    window = result["coordinate_window"]
    assert (window.chromosome, window.start, window.end, window.assembly) == (
        "17", 43044295, 43125364, "GRCh38"
    )
    # One search on the gene database with the module's own term, one
    # summary on the ids it returned.
    gene_searches = [s for s in spy.searches if s.db == "gene"]
    assert len(gene_searches) == 1
    assert gene_searches[0].term == coordinate_window.gene_search_term(window)
    assert [s.ids for s in spy.summaries if s.db == "gene"] == [["672", "7157"]]
    think = next(e for e in result["events"] if e.type == "think")
    assert "BRCA1" in think.payload["narrative"], think.payload["narrative"]


@pytest.mark.asyncio
async def test_a_window_without_an_assembly_is_asked_which_and_nothing_is_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch)
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state(NO_ASSEMBLY_QUESTION))
    assert result.get("clarification_needed") == coordinate_window.ASSEMBLY_QUESTION
    assert "coordinate_window" not in result
    assert [s for s in spy.searches if s.db == "gene"] == []
    assert result["resolved_entities"] == []


@pytest.mark.asyncio
async def test_a_grch37_window_plans_the_overlap_but_looks_up_no_genes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch)
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state(GRCH37_QUESTION))
    assert [s for s in spy.searches if s.db == "gene"] == []
    assert result["coordinate_window"].assembly == "GRCh37"
    assert result.get("clarification_needed") is None


@pytest.mark.asyncio
async def test_a_failing_gene_lookup_leaves_the_window_with_no_genes_and_no_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch)
    _Spy(monkeypatch, fail=True)
    result = await graph_module.think_node(_state(GRCH38_QUESTION))
    assert result["resolved_entities"] == []
    assert result["coordinate_window"].assembly == "GRCh38"


@pytest.mark.asyncio
async def test_a_question_without_a_window_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model(monkeypatch, query_class="single_hop")
    spy = _Spy(monkeypatch)
    result = await graph_module.think_node(_state("Which diseases are associated with BRCA1?"))
    assert "coordinate_window" not in result
    assert [s for s in spy.searches if s.db == "gene"] == []


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _plan_state(text: str, window: coordinate_window.CoordinateWindow | None) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "resolved_entities": [EventResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.0)],
        "query_class": "multi_hop",
    }
    if window is not None:
        extra["coordinate_window"] = window
    return _state(text, **extra)


@pytest.mark.asyncio
async def test_a_window_plans_the_clinvar_and_dbvar_overlap_calls_right_after_the_graph_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    window = coordinate_window.parse_coordinate_window(GRCH38_QUESTION)
    assert window is not None
    result = await graph_module.plan_node(_plan_state(GRCH38_QUESTION, window))
    calls = result["tool_calls"]
    assert isinstance(calls[0], graph_module._PlannedToolCall), "the graph call stays at index 0"
    overlap = [
        c for c in calls
        if isinstance(c, graph_module._PlannedNcbiEfetchToolCall)
        and c.ncbi_efetch_input.root.action == "coordinate_overlap"
    ]
    assert [c.purpose for c in overlap] == ["clinvar_overlap", "dbvar_overlap"], overlap
    assert calls[1] is overlap[0] and calls[2] is overlap[1]
    for call in overlap:
        root = call.ncbi_efetch_input.root
        assert (root.chromosome, root.start, root.end, root.assembly) == ("17", 43044295, 43125364, "GRCh38")
        assert call.tool_call.tool == "ncbi_efetch" and call.tool_call.layer == "layer_2_api"
    plan = next(e for e in result["events"] if e.type == "plan")
    assert [c["tool"] for c in plan.payload["tool_calls"]][:3] == ["cypher_query", "ncbi_efetch", "ncbi_efetch"]


@pytest.mark.asyncio
async def test_a_question_without_a_window_plans_no_overlap_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    result = await graph_module.plan_node(_plan_state("Which diseases are associated with BRCA1?", None))
    actions = [
        c.ncbi_efetch_input.root.action
        for c in result["tool_calls"]
        if isinstance(c, graph_module._PlannedNcbiEfetchToolCall)
    ]
    assert actions, "the gene question still plans its NCBI calls"
    assert "coordinate_overlap" not in actions


# ---------------------------------------------------------------------------
# Act: the row shaping for an overlap record
# ---------------------------------------------------------------------------


def _overlap_output(db: str) -> NcbiEfetchOutput:
    if db == "clinvar":
        fields = {
            "chr": "17", "chr_start": 43045000, "chr_end": 43045100, "assembly": "GRCh38",
            "requested_assembly": "GRCh38", "title": "NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs)",
            "germline_classification": "Pathogenic", "gene_symbol": ["BRCA1"],
        }
        record = NcbiEfetchRecord(
            id="VCV000017677", db="clinvar", fields=fields,
            source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/17677/",
        )
    else:
        fields = {
            "chr": "17", "chr_start": 43000000, "chr_end": 43200000, "assembly": "GRCh38",
            "requested_assembly": "GRCh38", "variant_type": ["copy number loss"],
            "gene_name": ["BRCA1", "NBR2"],
        }
        record = NcbiEfetchRecord(
            id="nsv1234567", db="dbvar", fields=fields,
            source_url="https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv1234567/",
        )
    return NcbiEfetchOutput(
        status="ok", action="coordinate_overlap", records=[record], record_count=1,
        total_available=1, truncated=False,
    )


@pytest.mark.parametrize(
    ("db", "purpose", "leading_field", "withheld"),
    [
        ("clinvar", "clinvar_overlap", "title", "requested_assembly"),
        ("dbvar", "dbvar_overlap", "variant_type", "chr"),
    ],
)
def test_an_overlap_record_becomes_a_row_with_its_allowlisted_fields_and_its_url(
    db: str, purpose: str, leading_field: str, withheld: str
) -> None:
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(_overlap_output(db), purpose)
    assert shaped["status"] == "ok" and shaped["row_count"] == 1
    (row,) = shaped["rows"]
    assert row["source_url"].startswith(f"https://www.ncbi.nlm.nih.gov/{db}/")
    assert next(iter(row["fields"])) == leading_field, row["fields"]
    assert withheld not in row["fields"]
    assert set(row["fields"]) <= set(graph_module._BREADTH_FIELDS_BY_PURPOSE[purpose])
    assert row["fields"]["assembly"] == "GRCh38"
