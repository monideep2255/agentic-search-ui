"""Card 119: after a "How far back" window is picked, an answer lists up to
ten papers from it, each with its title, while the writer still reads five
abstracts. A question with no window runs as before.

Fix round (2026-10-30), in the person's words: "When I pick a window, the
summary draws on the best-matching papers from that window that have an
abstract, the same way it does today, and the list shows up to ten." The
five abstracts go to the first five papers, in the PubMed search's own
order (relevance), that HAVE an abstract; never to the highest PMIDs, which
on a live cystic fibrosis question were five editorials with none
(A-119-01) and on caffeine and Marfan questions were the least on-topic
papers (A-119-02).

Exercised: the planner's caps; the abstract choice by rank, through Act's
own `_execute_planned_call`; the same choice end to end through the
compiled graph, read from the writer's prompt; the unwindowed rows against
develop's captured output; the clamp to PubTator3's bound; every other
efetch call's row cut.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from system_03_search_agent.core import breadth_plan as bp
from system_03_search_agent.core import clarify
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import build_synth_findings
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchInput,
    NcbiEfetchOutput,
    NcbiEfetchRecord,
)
from tests.system_03_search_agent.core.test_bare_topic_clarification import (  # noqa: F401
    _env,
    _install_decide,
    _install_models,
    _install_tools,
    _no_offered_windows,
    _payload,
    _run,
)

_WINDOW = bp.PublicationWindow(start=date(2021, 9, 25), end=None, label="the last 5 years")
_PMIDS = [str(30000 + n) for n in range(10)]

#: A PubMed search's own order (relevance), mixed-length PMIDs, so search
#: rank, number order and text order each pick a different five.
_RANKED = [
    "9000001",
    "39100000",
    "38000002",
    "35000000",
    "123456",
    "39000010",
    "38500000",
    "34000000",
    "36000003",
    "37000005",
]


def _url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _abstract_text(pmid: str) -> str:
    return f"Abstract about paper {pmid} only."


def _retmax(call: Any) -> int:
    return call.tool_input.model_dump()["retmax"]


def _ids_of(planned: tuple[Any, ...]) -> list[str]:
    fetch = next(c for c in planned if c.purpose == "pubmed_abstracts")
    return fetch.tool_input.model_dump()["ids"]


# ---------------------------------------------------------------------------
# Planning: ten windowed, five otherwise.
# ---------------------------------------------------------------------------


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


def test_a_cap_above_pubtator_s_bound_is_trimmed_not_refused() -> None:
    """J-119-07: PubTator3 takes at most 20 PMIDs. A larger cap trims both
    calls to 20 instead of failing validation at planning."""
    many = [str(40000000 + n) for n in range(30)]
    planned = bp.plan_literature_follow_up(many, 25)
    assert len(_ids_of(planned)) == bp.LITERATURE_FOLLOW_UP_MAX_IDS == 20
    annotate = next(c for c in planned if c.purpose == "pubtator_publications")
    assert len(annotate.tool_input.model_dump()["pmids"]) == 20


def test_a_search_s_retmax_above_the_bound_is_carried_trimmed() -> None:
    search = graph_module._planned_from_breadth(
        bp.PlannedCall(
            tool="ncbi_efetch",
            layer="layer_2_api",
            prefix="ne",
            purpose="pubmed_search",
            tool_input=NcbiEfetchInput.model_validate(
                {"action": "search", "db": "pubmed", "term": "x", "retmax": 200}
            ),
        )
    )
    follow = graph_module._follow_up_calls_for([search], gene_symbol=None)
    assert {f.result_cap for f in follow} == {bp.LITERATURE_FOLLOW_UP_MAX_IDS}


def test_search_rank_keeps_the_search_s_order_and_normalises_as_select_ids() -> None:
    assert bp.search_rank(["0038", "5", "38", "x", "0", 7, "5"]) == ("38", "5", "7")


# ---------------------------------------------------------------------------
# Act: the abstract choice, driven through `_execute_planned_call`.
# ---------------------------------------------------------------------------


class _DirectHarness:
    trace_id = "t-card119"

    async def enforce_timeout(self, step: str, coro: Any, budget_s: float) -> Any:
        return await coro


def _fetch_stub(monkeypatch: pytest.MonkeyPatch, *, no_abstract: set[str] | None = None) -> None:
    """`ncbi_efetch` answering a PubMed fetch with one record per requested
    id, a title on each and an abstract unless the id is in `no_abstract`."""
    missing = no_abstract or set()

    async def _efetch(tool_input: Any, **kwargs: object) -> NcbiEfetchOutput:
        ids = list(tool_input.model_dump().get("ids") or [])
        records = [
            NcbiEfetchRecord(
                id=pmid,
                db="pubmed",
                fields={
                    "title": f"Paper {pmid}",
                    **({} if pmid in missing else {"abstract": _abstract_text(pmid)}),
                },
                source_url=_url(pmid),
            )
            for pmid in ids
        ]
        return NcbiEfetchOutput(
            status="ok",
            action="fetch",
            records=records,
            record_count=len(records),
            total_available=len(records),
            truncated=False,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)


def _abstracts_follow_up(cap: int) -> graph_module._PlannedFollowUpCall:
    return graph_module._PlannedFollowUpCall(
        tool_call=graph_module.ToolCall(tool="ncbi_efetch", call_id="ne-abs", layer="layer_2_api"),
        purpose="pubmed_abstracts",
        source_purpose="pubmed_search",
        result_cap=cap,
    )


async def _act_rows(cap: int, ranked_ids: list[str]) -> list[dict[str, Any]]:
    concrete = graph_module._follow_up_planned_call(_abstracts_follow_up(cap), ranked_ids)
    assert isinstance(concrete, graph_module._PlannedNcbiEfetchToolCall)
    outcome = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", concrete)  # type: ignore[arg-type]
    (pair,) = outcome.pairs
    return pair[1].structured_fields["rows"]


def _titles(rows: list[dict[str, Any]]) -> list[str]:
    return [r["source_url"] for r in rows if "title" in r["fields"]]


def _abstract_urls(rows: list[dict[str, Any]]) -> set[str]:
    return {r["source_url"] for r in rows if "abstract" in r["fields"]}


@pytest.mark.asyncio
async def test_rank_not_pmid_decides_which_five_abstracts_are_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every paper has an abstract. The five read are search ranks 1 to 5,
    not the five highest PMIDs and not the five last in text order."""
    _fetch_stub(monkeypatch)
    rows = await _act_rows(10, _RANKED)
    assert len(_titles(rows)) == 10
    read = _abstract_urls(rows)
    assert read == {_url(p) for p in _RANKED[:5]}, read
    by_number = sorted(_RANKED, key=int, reverse=True)[:5]
    by_text = sorted(_RANKED, reverse=True)[:5]
    assert read != {_url(p) for p in by_number} and read != {_url(p) for p in by_text}


@pytest.mark.asyncio
async def test_the_same_ten_papers_in_another_search_order_read_other_abstracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fetch_stub(monkeypatch)
    reversed_rank = list(reversed(_RANKED))
    rows = await _act_rows(10, reversed_rank)
    assert _abstract_urls(rows) == {_url(p) for p in reversed_rank[:5]}


@pytest.mark.asyncio
async def test_papers_with_no_abstract_never_use_up_a_reading_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The A-119-01 shape, cystic fibrosis: the five best-ranked papers are
    editorials with no abstract and the sixth has one. The writer gets
    that one."""
    _fetch_stub(monkeypatch, no_abstract=set(_RANKED[:5]) | set(_RANKED[6:]))
    rows = await _act_rows(10, _RANKED)
    assert len(_titles(rows)) == 10
    assert _abstract_urls(rows) == {_url(_RANKED[5])}


@pytest.mark.asyncio
async def test_a_paper_with_no_abstract_hands_its_slot_to_the_next_ranked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fetch_stub(monkeypatch, no_abstract={_RANKED[1], _RANKED[3]})
    rows = await _act_rows(10, _RANKED)
    expected = [p for p in _RANKED if p not in {_RANKED[1], _RANKED[3]}][:5]
    assert _abstract_urls(rows) == {_url(p) for p in expected}
    assert len(_abstract_urls(rows)) == 5


@pytest.mark.asyncio
async def test_act_lists_ten_titles_only_when_the_planned_call_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-119-02 at the Act seam: the windowed concrete call carries ten and
    Act lists ten; the unwindowed one lists five."""
    _fetch_stub(monkeypatch)
    assert len(_titles(await _act_rows(10, _RANKED))) == 10
    assert len(_titles(await _act_rows(5, _RANKED[:5]))) == 5


# ---------------------------------------------------------------------------
# Unwindowed: develop's rows, byte for byte.
# ---------------------------------------------------------------------------

#: Captured from develop (b5690f98): `_ncbi_efetch_output_to_structured_
#: fields` on these seven records, two without an abstract, purpose
#: `pubmed_abstracts`. Title rows by URL text, cut to five; then one
#: abstract row per title row that has one, in the same order.
_DEV_INPUT = ["9000001", "39100000", "38000002", "35000000", "39000010", "38500000", "123456"]
_DEV_NO_ABSTRACT = {"39100000", "35000000"}
_DEV_TITLE_ORDER = ["123456", "35000000", "38000002", "38500000", "39000010"]
_DEV_ABSTRACT_ORDER = ["123456", "38000002", "38500000", "39000010"]


def _dev_expected_rows() -> list[dict[str, Any]]:
    titles = [
        {
            "curie": "",
            "fields": {"title": f"Paper {p}"},
            "node_or_edge_type": "pubmed",
            "source_url": _url(p),
        }
        for p in _DEV_TITLE_ORDER
    ]
    abstracts = [
        {
            "curie": "",
            "fields": {"abstract": _abstract_text(p)},
            "node_or_edge_type": "pubmed",
            "source_url": _url(p),
        }
        for p in _DEV_ABSTRACT_ORDER
    ]
    return titles + abstracts


def _dev_output() -> NcbiEfetchOutput:
    records = [
        NcbiEfetchRecord(
            id=p,
            db="pubmed",
            fields={
                "title": f"Paper {p}",
                **({} if p in _DEV_NO_ABSTRACT else {"abstract": _abstract_text(p)}),
            },
            source_url=_url(p),
        )
        for p in _DEV_INPUT
    ]
    return NcbiEfetchOutput(
        status="ok", action="fetch", records=records, record_count=7, total_available=7, truncated=False
    )


def test_an_unwindowed_answer_s_rows_equal_develop_s() -> None:
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(_dev_output(), "pubmed_abstracts")
    assert shaped["rows"] == _dev_expected_rows()
    assert shaped["row_count"] == 9 and shaped["total_available"] == 7


@pytest.mark.asyncio
async def test_an_unwindowed_abstracts_call_runs_develop_s_code_through_act(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unwindowed concrete call carries no cap and no rank, so Act
    shapes it with `_BREADTH_ROW_CAP` and no abstract choice, as develop."""
    concrete = graph_module._follow_up_planned_call(_abstracts_follow_up(5), _DEV_INPUT)
    assert isinstance(concrete, graph_module._PlannedNcbiEfetchToolCall)
    assert concrete.row_cap is None and concrete.search_rank == ()

    async def _efetch(tool_input: Any, **kwargs: object) -> NcbiEfetchOutput:
        return _dev_output()

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    outcome = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", concrete)  # type: ignore[arg-type]
    assert outcome.pairs[0][1].structured_fields["rows"] == _dev_expected_rows()


# ---------------------------------------------------------------------------
# J-119-08: every other efetch call keeps the breadth row cap.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_efetch_calls_take_their_row_cut_from_the_breadth_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph_module, "_BREADTH_ROW_CAP", 3)
    gds = graph_module._PlannedNcbiEfetchToolCall(
        tool_call=graph_module.ToolCall(tool="ncbi_efetch", call_id="ne-gds", layer="layer_2_api"),
        ncbi_efetch_input=NcbiEfetchInput.model_validate({"action": "summary", "db": "gds", "ids": ["1"]}),
        purpose="gds_summary",
    )

    async def _efetch(tool_input: Any, **kwargs: object) -> NcbiEfetchOutput:
        records = [
            NcbiEfetchRecord(
                id=str(n),
                db="gds",
                fields={"title": f"Dataset {n}", "accession": f"GDS{n}"},
                source_url=f"https://www.ncbi.nlm.nih.gov/sites/GDSbrowser?acc=GDS{n}",
            )
            for n in range(6)
        ]
        return NcbiEfetchOutput(
            status="ok", action="summary", records=records, record_count=6, total_available=6, truncated=False
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    outcome = await graph_module._execute_planned_call(_DirectHarness(), "single_hop", gds)  # type: ignore[arg-type]
    assert len(outcome.pairs[0][1].structured_fields["rows"]) == 3

    clinvar = graph_module._follow_up_planned_call(
        graph_module._PlannedFollowUpCall(
            tool_call=graph_module.ToolCall(tool="ncbi_efetch", call_id="ne-cv", layer="layer_2_api"),
            purpose="clinvar_summary",
            source_purpose="clinvar_search",
        ),
        ["11", "12"],
    )
    assert isinstance(clinvar, graph_module._PlannedNcbiEfetchToolCall) and clinvar.row_cap is None


# ---------------------------------------------------------------------------
# The writer's 30-finding slice, at develop's lead quota (J-119-03).
# ---------------------------------------------------------------------------


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


def _ten_paper_output() -> NcbiEfetchOutput:
    records = [
        NcbiEfetchRecord(
            id=pmid,
            db="pubmed",
            fields={"title": f"Paper {pmid}", "abstract": _abstract_text(pmid)},
            source_url=_url(pmid),
        )
        for pmid in _PMIDS
    ]
    return NcbiEfetchOutput(
        status="ok", action="fetch", records=records, record_count=10, total_available=10, truncated=False
    )


def _writer_slice(row_cap: int) -> list[Any]:
    structured = graph_module._ncbi_efetch_output_to_structured_fields(
        _ten_paper_output(), "pubmed_abstracts", None, row_cap, tuple(_PMIDS)
    )
    findings = [_context("ctx1"), _finding("abs", structured), _context("ctx2")]
    synth, _ = build_synth_findings(
        findings,
        graph_module._pick_representative_field,
        max_findings=graph_module._MAX_FINDINGS_FOR_DISPLAY,
        lead_call_ids=frozenset({"abs"}),
        lead_quota=graph_module._LEAD_FINDINGS_QUOTA,
    )
    return synth[: graph_module._MAX_FINDINGS_FOR_MODEL_PROMPT]


def test_the_lead_quota_is_develop_s() -> None:
    assert graph_module._LEAD_FINDINGS_QUOTA == 10
    assert not hasattr(graph_module, "_lead_findings_quota")


def test_the_writer_s_first_thirty_findings_hold_exactly_five_abstracts_when_windowed() -> None:
    mine = [f for f in _writer_slice(10) if f.call_id == "abs"]
    assert sum(f.field == "title" for f in mine) == 10
    assert sum(f.field == "abstract" for f in mine) == 5


def test_the_unwindowed_writer_slice_still_holds_five_titles_and_five_abstracts() -> None:
    mine = [f for f in _writer_slice(5) if f.call_id == "abs"]
    assert sum(f.field == "title" for f in mine) == 5
    assert sum(f.field == "abstract" for f in mine) == 5


def test_a_windowed_topic_question_also_reads_at_most_five_abstracts() -> None:
    topic = bp.plan_topic_search("papers on statins", window=_WINDOW)
    calls = [graph_module._planned_from_breadth(c) for c in topic]
    follow = [
        c
        for c in graph_module._follow_up_calls_for(calls, gene_symbol=None)
        if c.purpose == "pubmed_abstracts"
    ]
    (fu,) = follow
    assert fu.result_cap == 10
    concrete = graph_module._follow_up_planned_call(fu, _PMIDS)
    assert isinstance(concrete, graph_module._PlannedNcbiEfetchToolCall)
    assert concrete.row_cap == 10 and len(concrete.ncbi_efetch_input.model_dump()["ids"]) == 10
    assert concrete.search_rank == tuple(_PMIDS)
    rows = graph_module._ncbi_efetch_output_to_structured_fields(
        _ten_paper_output(), "pubmed_abstracts", None, concrete.row_cap, concrete.search_rank
    )["rows"]
    assert len(_titles(rows)) == 10 and len(_abstract_urls(rows)) == 5


# ---------------------------------------------------------------------------
# J-119-02: end to end through the compiled graph, read from the writer's
# own prompt.
# ---------------------------------------------------------------------------


def _install_windowed_papers(
    monkeypatch: pytest.MonkeyPatch, *, ranked: list[str], no_abstract: set[str]
) -> list[dict[str, Any]]:
    """BRCA1's graph call answers the Gene row; the PubMed search answers up
    to its own `retmax` ids in `ranked` order; the fetch answers one record
    per requested id. Returns every ncbi_efetch input, in order."""
    from system_03_search_agent.tools.clinicaltrials_search_schemas import (
        ClinicalTrialsSearchOutput,
    )
    from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput, CypherQueryRow
    from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateOutput

    calls: list[dict[str, Any]] = []

    async def _cypher(harness: object, cypher_input: object, **kwargs: object) -> CypherQueryOutput:
        if kwargs.get("template") is not None:
            return CypherQueryOutput(
                status="empty", row_count=0, total_available=0, truncated=False, rows=[]
            )
        return CypherQueryOutput(
            status="ok",
            row_count=1,
            total_available=1,
            truncated=False,
            rows=[
                CypherQueryRow(
                    node_or_edge_type="Gene",
                    curie="NCBIGene:672",
                    fields={"name": "BRCA1 DNA repair associated"},
                    source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                    graph_snapshot_version="v1",
                )
            ],
        )

    async def _efetch(tool_input: Any, **kwargs: object) -> NcbiEfetchOutput:
        dumped = tool_input.model_dump()
        calls.append(dumped)
        action = dumped.get("action", "search")
        if action == "search" and dumped.get("db") == "pubmed":
            found = ranked[: dumped["retmax"]]
            return NcbiEfetchOutput(
                status="ok",
                action="search",
                records=[
                    NcbiEfetchRecord(
                        db="pubmed", fields={"idlist": found, "idlist_count": len(found)}
                    )
                ],
                record_count=1,
                total_available=len(found),
                truncated=False,
            )
        if action == "fetch" and dumped.get("db") == "pubmed":
            records = [
                NcbiEfetchRecord(
                    id=pmid,
                    db="pubmed",
                    fields={
                        "title": f"Paper {pmid}",
                        **({} if pmid in no_abstract else {"abstract": _abstract_text(pmid)}),
                    },
                    source_url=_url(pmid),
                )
                for pmid in dumped["ids"]
            ]
            return NcbiEfetchOutput(
                status="ok",
                action="fetch",
                records=records,
                record_count=len(records),
                total_available=len(records),
                truncated=False,
            )
        return NcbiEfetchOutput(
            status="empty",
            action=action,
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
        )

    async def _pubtator(tool_input: Any, **kwargs: object) -> PubtatorAnnotateOutput:
        return PubtatorAnnotateOutput(status="empty", mode="entity_lookup")

    async def _trials(tool_input: Any, **kwargs: object) -> ClinicalTrialsSearchOutput:
        return ClinicalTrialsSearchOutput(status="empty")

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)
    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)
    monkeypatch.setattr(graph_module, "clinicaltrials_search", _trials)
    return calls


def _spy_writer(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Wrap the stubbed completion call and keep every writer prompt."""
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    prompts: list[str] = []
    stubbed = harness_module.litellm.acompletion

    async def _spy(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])  # type: ignore[call-overload]
        joined = "\n".join(str(m.get("content") or "") for m in messages)
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            prompts.append(joined)
        return await stubbed(*args, **kwargs)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _spy)
    return prompts


async def _ask_brca1(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ranked: list[str],
    no_abstract: set[str],
    pick_window: bool = True,
) -> tuple[list[Any], list[str], list[dict[str, Any]]]:
    _install_tools(monkeypatch)
    calls = _install_windowed_papers(monkeypatch, ranked=ranked, no_abstract=no_abstract)
    _install_models(monkeypatch, clarify_reply=None)
    prompts = _spy_writer(monkeypatch)
    _install_decide(monkeypatch, {"think.recent_years": "recent_unbounded"})
    asked = await _run("recent papers on BRCA1")
    _install_decide(monkeypatch)
    if not pick_window:
        # The same words typed again with no click: an unpicked question.
        clarify.clear_offered_windows()
        text = "recent papers on BRCA1 from the last 5 years?"
    else:
        text = _payload(asked, "think")["clarifying_options"][1]  # type: ignore[index]
    prompts.clear()
    calls.clear()
    return await _run(text), prompts, calls


def _papers_in(prompt: str) -> tuple[set[str], set[str]]:
    titles = {p for p in _RANKED if f"Paper {p}" in prompt}
    abstracts = {p for p in _RANKED if _abstract_text(p) in prompt}
    return titles, abstracts


def _answer_text(events: list[Any]) -> str:
    return "\n".join(
        e.payload["text"] for e in events if e.type == "token" and "text" in e.payload
    )


def _pubmed_search(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return next(c for c in calls if c.get("action") == "search" and c.get("db") == "pubmed")


@pytest.mark.asyncio
async def test_a_picked_window_lists_ten_and_the_writer_reads_the_five_best_ranked_with_an_abstract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real graph: search rank 2 has no abstract, so the writer reads
    ranks 1, 3, 4, 5 and 6, and the answer lists all ten papers."""
    events, prompts, calls = await _ask_brca1(monkeypatch, ranked=_RANKED, no_abstract={_RANKED[1]})
    assert _pubmed_search(calls)["retmax"] == 10
    assert prompts, "the writer was never called"
    for prompt in prompts:
        titles, abstracts = _papers_in(prompt)
        assert titles == set(_RANKED), titles
        assert abstracts == {_RANKED[0], _RANKED[2], _RANKED[3], _RANKED[4], _RANKED[5]}, abstracts
    text = _answer_text(events)
    assert "Found 10 papers" in text, text


@pytest.mark.asyncio
async def test_a_picked_window_whose_best_ranked_papers_have_no_abstract_still_reads_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-119-01 end to end: ranks 1 to 5 and 7 to 10 have no abstract."""
    no_abstract = set(_RANKED) - {_RANKED[5]}
    _, prompts, _ = await _ask_brca1(monkeypatch, ranked=_RANKED, no_abstract=no_abstract)
    assert prompts
    for prompt in prompts:
        titles, abstracts = _papers_in(prompt)
        assert titles == set(_RANKED) and abstracts == {_RANKED[5]}, (titles, abstracts)


@pytest.mark.asyncio
async def test_the_same_words_typed_with_no_window_list_five_and_read_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, prompts, calls = await _ask_brca1(
        monkeypatch, ranked=_RANKED, no_abstract=set(), pick_window=False
    )
    assert _pubmed_search(calls)["retmax"] == 5
    assert prompts
    for prompt in prompts:
        titles, abstracts = _papers_in(prompt)
        assert titles == abstracts == set(_RANKED[:5]), (titles, abstracts)
