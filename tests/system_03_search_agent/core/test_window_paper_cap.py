"""Card 119: after a "How far back" window is picked, an answer lists up to
ten papers from it, each with its title, while the writer still reads five
abstracts. A question with no window runs as before.

The trap this file guards: ten title rows plus ten abstract rows are twenty
lead rows, and the writer's 30-finding slice would then hold all ten
abstracts. Ten titles plus five abstracts fill the lead quota of 15 exactly.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from system_03_search_agent.core import breadth_plan as bp
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import build_synth_findings
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

_WINDOW = bp.PublicationWindow(start=date(2021, 9, 25), end=None, label="the last 5 years")
_PMIDS = [str(30000 + n) for n in range(10)]


def _retmax(call: Any) -> int:
    return call.tool_input.model_dump()["retmax"]


def _ids_of(planned: tuple[Any, ...]) -> list[str]:
    fetch = next(c for c in planned if c.purpose == "pubmed_abstracts")
    return fetch.tool_input.model_dump()["ids"]


def test_a_windowed_gene_question_plans_ten_and_follows_up_on_ten() -> None:
    (pubmed, *_) = bp.plan_first_stage("BRCA1", None, window=_WINDOW)
    assert pubmed.purpose == "pubmed_search" and _retmax(pubmed) == 10
    assert len(_ids_of(bp.plan_literature_follow_up(_PMIDS, _retmax(pubmed)))) == 10


def test_an_unwindowed_gene_question_still_plans_five() -> None:
    (pubmed, *_) = bp.plan_first_stage("BRCA1", None)
    assert _retmax(pubmed) == 5
    assert len(_ids_of(bp.plan_literature_follow_up(_PMIDS))) == 5


def test_a_windowed_topic_question_plans_ten_and_an_unwindowed_one_five() -> None:
    (windowed,) = bp.plan_topic_search("papers on statins", window=_WINDOW)
    (plain,) = bp.plan_topic_search("papers on statins")
    assert _retmax(windowed) == 10 and _retmax(plain) == 5


def test_the_follow_up_carries_the_search_s_own_cap() -> None:
    windowed = graph_module._build_breadth_calls("BRCA1", window=_WINDOW)
    plain = graph_module._build_breadth_calls("BRCA1")

    def caps(calls: list[Any]) -> set[int]:
        return {
            c.result_cap
            for c in calls
            if isinstance(c, graph_module._PlannedFollowUpCall) and c.source_purpose == "pubmed_search"
        }

    assert caps(windowed) == {10}
    assert caps(plain) == {5}


def _output(count: int, *, abstracts: bool = True) -> NcbiEfetchOutput:
    records = [
        NcbiEfetchRecord(
            id=pmid,
            db="pubmed",
            fields={"title": f"Paper {pmid}", **({"abstract": f"Abstract of {pmid}."} if abstracts else {})},
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )
        for pmid in _PMIDS[:count]
    ]
    return NcbiEfetchOutput(
        status="ok", action="fetch", records=records, record_count=count, total_available=count, truncated=False
    )


def _shape(count: int, row_cap: int) -> list[dict[str, Any]]:
    return graph_module._ncbi_efetch_output_to_structured_fields(
        _output(count), "pubmed_abstracts", None, row_cap
    )["rows"]


def _fields(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [r for r in rows if name in r["fields"]]


def test_a_windowed_answer_lists_ten_titles_and_keeps_five_abstracts() -> None:
    rows = _shape(10, 10)
    assert len(_fields(rows, "title")) == 10
    abstracts = _fields(rows, "abstract")
    assert len(abstracts) == 5
    # The five newest papers (highest PMIDs) are the ones read.
    assert sorted(r["source_url"] for r in abstracts) == [
        f"https://pubmed.ncbi.nlm.nih.gov/{p}/" for p in _PMIDS[5:]
    ]


def test_an_unwindowed_answer_keeps_five_titles_and_five_abstracts_as_before() -> None:
    rows = _shape(10, 5)
    assert len(_fields(rows, "title")) == 5
    assert len(_fields(rows, "abstract")) == 5
    # Byte-identical to the call that never passes a cap.
    baseline = graph_module._ncbi_efetch_output_to_structured_fields(_output(10), "pubmed_abstracts")["rows"]
    assert rows == baseline


def _finding(call_id: str, structured: dict[str, Any]) -> Finding:
    return Finding(
        call_id=call_id,
        tool="ncbi_efetch",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=structured,
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _context(call_id: str) -> Finding:
    rows = [
        {
            "curie": "",
            "node_or_edge_type": "Disease",
            "fields": {"name": f"{call_id} {n}"},
            "source_url": f"https://example.org/{call_id}/{n}",
        }
        for n in range(25)
    ]
    return _finding(call_id, {"status": "ok", "rows": rows, "row_count": 25})


def _writer_slice(row_cap: int, quota: int) -> list[Any]:
    structured = graph_module._ncbi_efetch_output_to_structured_fields(
        _output(10), "pubmed_abstracts", None, row_cap
    )
    findings = [_context("ctx1"), _finding("abs", structured), _context("ctx2")]
    synth, _ = build_synth_findings(
        findings,
        graph_module._pick_representative_field,
        max_findings=graph_module._MAX_FINDINGS_FOR_DISPLAY,
        lead_call_ids=frozenset({"abs"}),
        lead_quota=quota,
    )
    return synth[: graph_module._MAX_FINDINGS_FOR_MODEL_PROMPT]


def _planned_abstracts_follow_up(cap: int) -> Any:
    return graph_module._PlannedFollowUpCall(
        tool_call=graph_module.ToolCall(tool="ncbi_efetch", call_id="ne-abs", layer="layer_2_api"),
        purpose="pubmed_abstracts",
        source_purpose="pubmed_search",
        result_cap=cap,
    )


def test_the_lead_quota_is_fifteen_when_windowed_and_ten_otherwise() -> None:
    assert graph_module._lead_findings_quota([_planned_abstracts_follow_up(10)]) == 15
    assert graph_module._lead_findings_quota([_planned_abstracts_follow_up(5)]) == 10
    assert graph_module._lead_findings_quota([]) == 10


def test_the_writer_s_first_thirty_findings_hold_exactly_five_abstracts_when_windowed() -> None:
    quota = graph_module._lead_findings_quota([_planned_abstracts_follow_up(10)])
    window = _writer_slice(10, quota)
    mine = [f for f in window if f.call_id == "abs"]
    assert sum(f.field == "title" for f in mine) == 10
    assert sum(f.field == "abstract" for f in mine) == 5


def test_the_unwindowed_writer_slice_still_holds_five_titles_and_five_abstracts() -> None:
    quota = graph_module._lead_findings_quota([_planned_abstracts_follow_up(5)])
    mine = [f for f in _writer_slice(5, quota) if f.call_id == "abs"]
    assert sum(f.field == "title" for f in mine) == 5
    assert sum(f.field == "abstract" for f in mine) == 5


def test_a_windowed_topic_question_also_reads_at_most_five_abstracts() -> None:
    topic = bp.plan_topic_search("papers on statins", window=_WINDOW)
    calls = [graph_module._planned_from_breadth(c) for c in topic]
    follow = [c for c in graph_module._follow_up_calls_for(calls, gene_symbol=None) if c.purpose == "pubmed_abstracts"]
    (fu,) = follow
    assert fu.result_cap == 10
    concrete = graph_module._follow_up_planned_call(fu, _PMIDS)
    assert concrete.row_cap == 10 and len(concrete.ncbi_efetch_input.model_dump()["ids"]) == 10
    rows = graph_module._ncbi_efetch_output_to_structured_fields(
        _output(10), "pubmed_abstracts", None, concrete.row_cap
    )["rows"]
    assert len(_fields(rows, "title")) == 10 and len(_fields(rows, "abstract")) == 5
