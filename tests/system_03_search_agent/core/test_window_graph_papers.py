"""Card 105: a picked "How far back" window leaves the graph's Article rows out.

An Article vertex has no publication date, so when the person picked a window
the graph cannot say which of its papers are inside it. Act removes them from
the question's graph call (only when the planned call carries the flag), and
`_answer_call_ids` lets the windowed PubMed abstracts call answer instead.

The end-to-end check (a picked window through the real graph) lives in
`test_bare_topic_clarification.py`; this file grades Act's row handling and the
answer-call set in isolation.
"""

from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)


class _DirectHarness:
    async def enforce_timeout(self, step: str, coro: Any, budget_s: float) -> Any:
        return await coro


def _row(kind: str, curie: str) -> CypherQueryRow:
    return CypherQueryRow(
        node_or_edge_type=kind,
        curie=curie,
        fields={"name": f"{kind} {curie}"},
        source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        graph_snapshot_version="v1",
    )


def _planned(flag: bool) -> graph_module._PlannedToolCall:
    return graph_module._PlannedToolCall(
        tool_call=ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
        cypher_input=CypherQueryInput(
            query_intent="recent papers on BRCA1",
            query_class="single_hop",
            target_entities=["NCBIGene:672"],
        ),
        undated_papers_left_out=flag,
    )


def _install_graph(monkeypatch: pytest.MonkeyPatch, rows: list[CypherQueryRow], total: int) -> None:
    async def _cypher(harness: object, cypher_input: object, **kwargs: object) -> CypherQueryOutput:
        return CypherQueryOutput(
            status="ok",
            row_count=len(rows),
            total_available=total,
            truncated=total > len(rows),
            rows=list(rows),
        )

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)


_MIXED = [_row("Article", "PMID:10026184"), _row("Gene", "NCBIGene:672")]


@pytest.mark.asyncio
async def test_undated_papers_left_out_drops_only_article_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_graph(monkeypatch, _MIXED, total=3487)

    on = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", _planned(True))  # type: ignore[arg-type]
    fields = on.pairs[0][1].structured_fields
    assert [r["curie"] for r in fields["rows"]] == ["NCBIGene:672"], fields
    assert fields["row_count"] == fields["total_available"] == 1, fields
    assert fields["truncated"] is False
    assert on.result_count == 1 and on.truncated is False
    assert len(on.pairs) == 1, "no quarantine pair when every Article row was removed"
    assert "1 row(s) of 1" in on.summary, on.summary

    off = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", _planned(False))  # type: ignore[arg-type]
    off_fields = off.pairs[0][1].structured_fields
    assert [r["curie"] for r in off_fields["rows"]] == ["PMID:10026184", "NCBIGene:672"]
    assert off_fields["row_count"] == 2 and off_fields["total_available"] == 3487
    assert off_fields["truncated"] is True
    assert [call.call_id for call, _ in off.pairs] == ["cq-1", "cq-1-articles"]


@pytest.mark.asyncio
async def test_a_result_of_only_articles_becomes_empty_not_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_graph(monkeypatch, [_row("Article", "PMID:10026184")], total=40)

    outcome = await graph_module._execute_planned_call(
        _DirectHarness(), "single_hop", _planned(True)
    )  # type: ignore[arg-type]
    fields = outcome.pairs[0][1].structured_fields
    assert fields["rows"] == [] and fields["row_count"] == fields["total_available"] == 0
    assert fields["status"] == "empty"
    assert len(outcome.pairs) == 1


def test_the_flag_defaults_to_false() -> None:
    assert (
        graph_module._PlannedToolCall.__dataclass_fields__["undated_papers_left_out"].default
        is False
    )


def _follow_up(purpose: str, source: str, call_id: str) -> graph_module._PlannedFollowUpCall:
    return graph_module._PlannedFollowUpCall(
        tool_call=ToolCall(tool="ncbi_efetch", call_id=call_id, layer="layer_2_api"),
        purpose=purpose,
        source_purpose=source,
    )


def test_the_windowed_abstracts_call_answers_only_when_the_flag_is_set() -> None:
    abstracts = _follow_up("pubmed_abstracts", "pubmed_search", "ne-abs")
    clinvar = _follow_up("clinvar_summary", "clinvar_search", "ne-cv")
    for flag, expected in ((True, {"cq-1", "ne-abs"}), (False, {"cq-1"})):
        calls = [_planned(flag), abstracts, clinvar]
        assert graph_module._answer_call_ids(calls, "recent papers on BRCA1") == expected


def _line_state(
    flag: bool,
    resolved_text: str | None = "C9orf43",
    targets: list[str] | None = None,
    entities: list[Any] | None = None,
    dropped: bool = True,
) -> dict[str, Any]:
    from types import SimpleNamespace

    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    graph = graph_module._PlannedToolCall(
        tool_call=ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
        cypher_input=CypherQueryInput(
            query_intent="recent papers on C9orf43",
            query_class="single_hop",
            target_entities=targets or ["NCBIGene:119"],
        ),
        undated_papers_left_out=flag,
    )
    search = SimpleNamespace(
        tool_call=ToolCall(tool="ncbi_efetch", call_id="ne-s", layer="layer_2_api"),
        purpose="pubmed_search",
    )
    abstracts = graph_module._PlannedFollowUpCall(
        tool_call=ToolCall(tool="ncbi_efetch", call_id="ne-a", layer="layer_2_api"),
        purpose="pubmed_abstracts",
        source_purpose="pubmed_search",
        gene_symbol="C9ORF43",
    )
    empty = NcbiEfetchOutput(
        status="empty",
        action="search",
        records=[],
        record_count=0,
        total_available=None,
        truncated=False,
    )
    if entities is None:
        entities = [SimpleNamespace(text=resolved_text, curie="NCBIGene:119")] if resolved_text else []
    return {
        "tool_calls": [graph, search, abstracts],
        "layer2_raw_outputs": {"ne-s": empty},
        "layer3_raw_outputs": {"cq-1" + graph_module._ARTICLES_DROPPED_SUFFIX: True} if dropped else {},
        "resolved_entities": entities,
    }


def _window(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import breadth_plan

    monkeypatch.setattr(
        graph_module,
        "_picked_publication_window",
        lambda query: breadth_plan.recent_publication_window(60, "the last 5 years"),
    )


def test_the_line_writes_the_symbol_as_the_count_line_does(monkeypatch: pytest.MonkeyPatch) -> None:
    _window(monkeypatch)
    line = graph_module._window_no_papers_line(_line_state(True), object())  # type: ignore[arg-type]
    assert line is not None and "for C9orf43." in line, line
    assert "C9ORF43" not in line


def test_the_line_falls_back_to_the_search_symbol_when_nothing_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _window(monkeypatch)
    line = graph_module._window_no_papers_line(_line_state(True, None), object())  # type: ignore[arg-type]
    assert line is not None and "for C9ORF43." in line, line


def test_the_line_needs_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """J-105-03: the same empty windowed search, flag off (graph papers were
    not left out): no line."""
    _window(monkeypatch)
    assert graph_module._window_no_papers_line(_line_state(False), object()) is None  # type: ignore[arg-type]
    assert graph_module._window_no_papers_line(_line_state(True), object()) is not None  # type: ignore[arg-type]


def _ent(text: str, curie: str) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(text=text, curie=curie)


def test_an_rs_id_typed_before_the_gene_does_not_become_the_searched_gene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-105-01: only the gene was searched, so the line names the gene."""
    _window(monkeypatch)
    state = _line_state(
        True,
        targets=["dbSNP:rs80357906", "NCBIGene:672"],
        entities=[_ent("rs80357906", "dbSNP:rs80357906"), _ent("BRCA1", "NCBIGene:672")],
    )
    line = graph_module._window_no_papers_line(state, object())  # type: ignore[arg-type]
    assert line is not None and "for BRCA1." in line and "rs80357906" not in line, line


def test_a_pmid_typed_before_the_gene_does_not_become_the_searched_gene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _window(monkeypatch)
    state = _line_state(
        True,
        targets=["PMID:12345678", "NCBIGene:672"],
        entities=[_ent("PMID:12345678", "PMID:12345678"), _ent("BRCA1", "NCBIGene:672")],
    )
    line = graph_module._window_no_papers_line(state, object())  # type: ignore[arg-type]
    assert line is not None and "for BRCA1." in line and "12345678" not in line, line


def test_the_plain_gene_case_names_the_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    _window(monkeypatch)
    state = _line_state(True, targets=["NCBIGene:672"], entities=[_ent("BRCA1", "NCBIGene:672")])
    line = graph_module._window_no_papers_line(state, object())  # type: ignore[arg-type]
    assert line is not None and "for BRCA1." in line, line


def test_the_second_sentence_shows_only_when_graph_papers_were_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-105-02: the sentence about undated graph papers needs rows removed."""
    _window(monkeypatch)
    sentence = "carry no publication date"
    on = graph_module._window_no_papers_line(_line_state(True, dropped=True), object())  # type: ignore[arg-type]
    off = graph_module._window_no_papers_line(_line_state(True, dropped=False), object())  # type: ignore[arg-type]
    assert on is not None and sentence in on, on
    assert off is not None and sentence not in off and off.endswith("for C9orf43."), off


@pytest.mark.asyncio
async def test_act_records_the_left_out_papers_only_when_articles_were_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_graph(monkeypatch, _MIXED, total=2)
    removed = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", _planned(True))  # type: ignore[arg-type]
    assert removed.undated_articles_dropped is True
    _install_graph(monkeypatch, [_row("Gene", "NCBIGene:672")], total=1)
    none_removed = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", _planned(True))  # type: ignore[arg-type]
    assert none_removed.undated_articles_dropped is False
