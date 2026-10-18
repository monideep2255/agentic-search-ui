"""Card 74 (2026-10-05), golden G-006: a question about one PubMed paper's linked
data records ("sequence data for PMID 11237011") plans live ELink calls from
`pubmed` to explicit target databases, and says plainly when NCBI links none.

The knowledge graph holds no edge from a paper to sequence data, BioProjects, GEO
series or assemblies, so only ELink can answer. Drives the real `plan_node`,
`act_node` and `write_node` with only the classifier and the NCBI tool faked.
No network anywhere.

Coverage statement, per `goal-contracts`: Plan with the classifier saying
"sequences" (three ELink calls with explicit targets, three summary follow-ups,
no graph call, state key set), with "not_linked_data" and with no usable pick
(the graph call first, as before, the populate check), with a gene question
(the classifier is never asked); Act (links feed the summaries, the rows carry
the linked records' own NCBI pages); Write (every link empty gives the plain
"no linked records" sentence, one kind empty beside a kind that answered gives
a note, more records than shown gives the count). What this file does NOT
exercise: the live ELink and ESummary responses, read for PMID 11237011 in
`testing/Developer/reports/2026-10-05_wave3/card74.md`.
"""
from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core import paper_links
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

QUESTION = "sequence data for PMID 11237011"
PAPER = EventResolvedEntity(text="PMID 11237011", curie="PMID:11237011", confidence=1.0)
GENE = EventResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.0)


def _stub_decisions(monkeypatch: pytest.MonkeyPatch, pick: str | None) -> list[str]:
    """`plan.paper_links` answers `pick` (None: no usable pick). Returns the points asked."""
    asked: list[str] = []

    async def _decide(harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any) -> Any:
        asked.append(point)
        if point != "plan.paper_links" or pick is None:
            return DecisionRecord(
                name=point, options=list(options), chosen=next(iter(options)),
                decided_by="guard", fallback_reason="timeout",
            )
        assert pick in options
        return DecisionRecord(
            name=point, options=list(options), chosen=pick, decided_by="jev",
            jev_choice=pick, guard_choice=pick, agreed=True,
        )

    monkeypatch.setattr(graph_module, "decide", _decide)
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    return asked


def _state(text: str, entities: list[EventResolvedEntity], **extra: Any) -> dict[str, Any]:
    query = Query(text=text, session_id="s-pl", trace_id="t-pl", user_id=None)
    state: dict[str, Any] = {
        "query": query,
        "harness": harness_module.Harness(trace_id="t-pl"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
        "resolved_entities": entities,
        "query_class": "single_hop",
    }
    state.update(extra)
    return state


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_one_paper_linked_data_question_plans_elink_with_explicit_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _stub_decisions(monkeypatch, "sequences")
    result = await graph_module.plan_node(_state(QUESTION, [PAPER]))
    calls = result["tool_calls"]
    assert "plan.paper_links" in asked
    assert not any(isinstance(c, graph_module._PlannedToolCall) for c in calls), "no graph call"
    links = [c for c in calls if isinstance(c, graph_module._PlannedNcbiEfetchToolCall)]
    assert [c.purpose for c in links] == [
        "paper_link_nuccore", "paper_link_sra", "paper_link_assembly",
    ]
    for call in links:
        root = call.ncbi_efetch_input.root
        assert (root.action, root.dbfrom, root.ids) == ("link", "pubmed", ["11237011"])
    assert [c.ncbi_efetch_input.root.db for c in links] == ["nuccore", "sra", "assembly"]
    follow_ups = [c for c in calls if isinstance(c, graph_module._PlannedFollowUpCall)]
    assert [(f.source_purpose, f.purpose) for f in follow_ups] == [
        ("paper_link_nuccore", "nuccore_summary"),
        ("paper_link_sra", "sra_summary"),
        ("paper_link_assembly", "assembly_summary"),
    ]
    assert result["paper_link_plan"].pmid == "11237011"
    plan = next(e for e in result["events"] if e.type == "plan")
    assert "PMID 11237011" in plan.payload["narrative"]


@pytest.mark.asyncio
async def test_all_data_plans_every_kind_within_the_call_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_decisions(monkeypatch, "all_data")
    result = await graph_module.plan_node(_state(QUESTION, [PAPER]))
    assert len(result["tool_calls"]) == 12
    assert len(result["tool_calls"]) <= 20


@pytest.mark.asyncio
@pytest.mark.parametrize("pick", ["not_linked_data", None])
async def test_a_paper_question_the_classifier_does_not_read_as_linked_data_keeps_its_plan(
    monkeypatch: pytest.MonkeyPatch, pick: str | None
) -> None:
    """Populate check for the arm above: the same paper, the same question, and
    only the classifier's pick differs."""
    _stub_decisions(monkeypatch, pick)
    result = await graph_module.plan_node(_state("What MeSH terms are assigned to PMID 11237011?", [PAPER]))
    assert isinstance(result["tool_calls"][0], graph_module._PlannedToolCall)
    assert "paper_link_plan" not in result


@pytest.mark.asyncio
async def test_a_gene_question_is_unchanged_and_never_asks_the_paper_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _stub_decisions(monkeypatch, "sequences")
    result = await graph_module.plan_node(
        _state("Which diseases are associated with BRCA1?", [GENE])
    )
    assert isinstance(result["tool_calls"][0], graph_module._PlannedToolCall)
    assert "plan.paper_links" not in asked
    assert "paper_link_plan" not in result
    assert not any(
        str(getattr(c, "purpose", "")).startswith("paper_link_") for c in result["tool_calls"]
    )


@pytest.mark.asyncio
async def test_two_papers_are_not_a_one_paper_question(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _stub_decisions(monkeypatch, "sequences")
    other = EventResolvedEntity(text="PMID 12345", curie="PMID:12345", confidence=1.0)
    result = await graph_module.plan_node(_state(QUESTION, [PAPER, other]))
    assert "plan.paper_links" not in asked
    assert "paper_link_plan" not in result


# ---------------------------------------------------------------------------
# Act: links feed summaries, and the rows cite the linked records' own pages
# ---------------------------------------------------------------------------


def _link_output(db: str, ids: list[str], total: int | None = None) -> NcbiEfetchOutput:
    if not ids:
        return NcbiEfetchOutput(status="empty", action="link", records=[], record_count=0, truncated=False)
    return NcbiEfetchOutput(
        status="ok", action="link", record_count=len(ids), total_available=total,
        truncated=total is not None and total > len(ids),
        records=[
            NcbiEfetchRecord(id=i, db=db, source_url=f"https://www.ncbi.nlm.nih.gov/{db}/{i}")
            for i in ids
        ],
    )


def _install_ncbi(monkeypatch: pytest.MonkeyPatch, links: dict[str, NcbiEfetchOutput]) -> list[Any]:
    seen: list[Any] = []

    async def _efetch(tool_input: Any, **kwargs: Any) -> NcbiEfetchOutput:
        root = tool_input.root
        seen.append(root)
        if root.action == "link":
            return links.get(root.db, _link_output(root.db, []))
        fields = {"nuccore": {"title": "A sequence", "accessionversion": "NM_1.1"}}.get(
            root.db, {"title": f"A {root.db} record"}
        )
        return NcbiEfetchOutput(
            status="ok", action="summary", record_count=len(root.ids), total_available=len(root.ids), truncated=False,
            records=[
                NcbiEfetchRecord(
                    id=i, db=root.db, fields=fields,
                    source_url=f"https://www.ncbi.nlm.nih.gov/{root.db}/{i}",
                )
                for i in root.ids
            ],
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    return seen


@pytest.mark.asyncio
async def test_links_feed_the_summaries_and_an_empty_kind_costs_no_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_decisions(monkeypatch, "sequences")
    plan_result = await graph_module.plan_node(_state(QUESTION, [PAPER]))
    seen = _install_ncbi(
        monkeypatch,
        {
            "nuccore": _link_output("nuccore", ["2449300375", "1519499605"]),
            "assembly": _link_output("assembly", ["11968211"]),
        },
    )
    state = _state(
        QUESTION, [PAPER], tool_calls=plan_result["tool_calls"],
        paper_link_plan=plan_result["paper_link_plan"],
    )
    act = await graph_module.act_node(state)
    summaries = [r for r in seen if r.action == "summary"]
    assert sorted(r.db for r in summaries) == ["assembly", "nuccore"], "sra had no links, so no summary"
    nuccore = next(r for r in summaries if r.db == "nuccore")
    assert nuccore.ids == ["2449300375", "1519499605"]
    urls = {
        row["source_url"]
        for finding in act["findings"]
        for row in (finding.structured_fields or {}).get("rows", [])
    }
    assert "https://www.ncbi.nlm.nih.gov/nuccore/2449300375" in urls
    assert "https://www.ncbi.nlm.nih.gov/assembly/11968211" in urls

    # Write's notes over the same state: sra is named as empty.
    write_state = _state(
        QUESTION, [PAPER], tool_calls=plan_result["tool_calls"],
        paper_link_plan=plan_result["paper_link_plan"],
        layer2_raw_outputs=act["layer2_raw_outputs"],
    )
    assert graph_module._paper_link_notes(write_state) == [
        "NCBI lists no linked SRA run records for PMID 11237011."
    ]
    assert graph_module._paper_link_none_message(write_state) is None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_link_empty_says_plainly_that_no_linked_records_are_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.system_03_search_agent.core.test_write_answer_structure import _install
    from tests.system_03_search_agent.core.test_write_answer_structure import _state as _write_state

    _stub_decisions(monkeypatch, "assemblies")
    _install(monkeypatch, lambda _lines: "ok")
    plan_result = await graph_module.plan_node(_state(QUESTION, [PAPER]))
    _install_ncbi(monkeypatch, {})
    act = await graph_module.act_node(
        _state(QUESTION, [PAPER], tool_calls=plan_result["tool_calls"],
               paper_link_plan=plan_result["paper_link_plan"])
    )
    assert act["findings"] == [] or all(
        not (f.structured_fields or {}).get("rows") for f in act["findings"]
    )
    state = _write_state("researcher")
    state.update(
        tool_calls=plan_result["tool_calls"],
        paper_link_plan=plan_result["paper_link_plan"],
        layer2_raw_outputs=act["layer2_raw_outputs"],
        findings=act["findings"],
        findings_count=len(act["findings"]),
        failed_searches=[],
    )
    result = await graph_module.write_node(state)
    text = " ".join(e.payload["text"] for e in result["events"] if e.type == "token")
    assert "NCBI lists no linked genome assemblies for PMID 11237011." in text
    done = next(e for e in result["events"] if e.type == "done")
    assert done.payload["trust_outcome"] == "refuse"


def test_a_failed_link_search_makes_no_claim_that_none_are_listed() -> None:
    plan = graph_module._PaperLinkPlan(pmid="11237011", targets=("assembly",))
    planned = graph_module._planned_from_breadth(paper_links.link_calls("11237011", ("assembly",))[0])
    failed = NcbiEfetchOutput(status="error", action="link", records=[], record_count=0, truncated=False, error="x")
    state: dict[str, Any] = {
        "paper_link_plan": plan,
        "tool_calls": [planned],
        "layer2_raw_outputs": {planned.tool_call.call_id: failed},
    }
    assert graph_module._paper_link_none_message(state) is None
    state["layer2_raw_outputs"] = {planned.tool_call.call_id: _link_output("assembly", [])}
    assert graph_module._paper_link_none_message(state) == (
        "NCBI lists no linked genome assemblies for PMID 11237011."
    )


def test_more_linked_records_than_are_shown_says_how_many_NCBI_lists() -> None:
    plan = graph_module._PaperLinkPlan(pmid="11237011", targets=("nuccore",))
    planned = graph_module._planned_from_breadth(paper_links.link_calls("11237011", ("nuccore",))[0])
    big = _link_output("nuccore", [str(i) for i in range(1, 6)], total=1533)
    state: dict[str, Any] = {
        "paper_link_plan": plan,
        "tool_calls": [planned],
        "layer2_raw_outputs": {planned.tool_call.call_id: big},
    }
    assert graph_module._paper_link_notes(state) == [
        "NCBI lists 1533 sequence records linked to PMID 11237011; this answer shows 10."
    ]
    state["layer2_raw_outputs"] = {planned.tool_call.call_id: _link_output("nuccore", ["1", "2"])}
    assert graph_module._paper_link_notes(state) == []
