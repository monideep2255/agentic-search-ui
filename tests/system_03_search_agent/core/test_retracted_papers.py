"""Card 146: a retracted paper keeps its row, with a "Retracted" tag beside its title.

The owner's decision (DECISIONS.md, 2026-10-25): "a retracted paper keeps its
row with a "Retracted" tag beside its title, read from PubMed's own
publication type, and the writer is told not to state its findings as fact."

PubMed's own mark, read live on 2026-10-30 for PMID 9500320: EFetch's
`PublicationTypeList` holds "Retracted Publication" and ESummary's `pubtype`
lists it. The notice of the retraction (PMID 20137807) is typed "Retraction
Notice" and is not itself a retracted paper. The XML below is that EFetch
body, trimmed to the elements the tool reads.

Every path a paper row takes is covered: the live PubMed row (title and
abstract), a PubTator3 paper whose PubMed record was read beside it, a
PubTator3 paper read only through the title lookup, and a knowledge graph
paper named by that lookup. Every surface is covered: the web and the saved
answer read `cells`, the command line, MCP and GraphQL read `text`.
A paper that was not retracted, and every prompt without one, is unchanged.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.contracts.token_order import in_reading_order, joined_text
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.feedback.capture import answer_markdown_from
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis import article_titles
from system_03_search_agent.synthesis.findings import (
    SYNTH_SYSTEM_INSTRUCTION,
    build_synth_findings,
    build_synth_messages,
)
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from system_03_search_agent.tools.pubtator_annotate import _parse_publication
from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateOutput

RETRACTED_PMID = "9500320"
RETRACTED_TITLE = (
    "Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive "
    "developmental disorder in children."
)
RETRACTED_ABSTRACT = "We investigated a consecutive series of children with chronic enterocolitis."
NOTICE_PMID = "20137807"
SOUND_PMID = "28340353"
SOUND_TITLE = "Molecular Structure of the Human CFTR Ion Channel."
QUESTION = "Is there a link between the gut and developmental disorders in children?"


def _article_xml(pmid: str, title: str, types: list[str], abstract: str = "") -> str:
    type_list = "".join(f"<PublicationType>{t}</PublicationType>" for t in types)
    abstract_xml = (
        f"<Abstract><AbstractText>{abstract}</AbstractText></Abstract>" if abstract else ""
    )
    return (
        '<PubmedArticle><MedlineCitation><PMID Version="1">'
        f"{pmid}</PMID><Article><ArticleTitle>{title}</ArticleTitle>{abstract_xml}"
        f"<PublicationTypeList>{type_list}</PublicationTypeList></Article>"
        "</MedlineCitation></PubmedArticle>"
    )


def _efetch_body(*articles: str) -> ElementTree.Element:
    return ElementTree.fromstring(f"<PubmedArticleSet>{''.join(articles)}</PubmedArticleSet>")


RETRACTED_XML = _article_xml(
    RETRACTED_PMID,
    RETRACTED_TITLE,
    ["Journal Article", "Research Support, Non-U.S. Gov't", "Retracted Publication"],
    RETRACTED_ABSTRACT,
)
NOTICE_XML = _article_xml(
    NOTICE_PMID, "Retraction--Ileal-lymphoid-nodular hyperplasia.", ["Retraction Notice"]
)
SOUND_XML = _article_xml(SOUND_PMID, SOUND_TITLE, ["Journal Article"])


# ------------------------------------------------------------------ the tool


def test_efetch_flags_only_the_record_pubmed_types_retracted() -> None:
    records = ncbi_eutils_actions._extract_pubmed_articles(
        _efetch_body(RETRACTED_XML, NOTICE_XML, SOUND_XML)
    )
    by_id = {record.id: record.fields for record in records}
    assert by_id[RETRACTED_PMID] == {
        "title": RETRACTED_TITLE,
        "abstract": RETRACTED_ABSTRACT,
        "retracted": True,
    }
    # The notice says "Retraction" only in its title and its own type: not flagged.
    assert "retracted" not in by_id[NOTICE_PMID]
    # A sound paper's fields are exactly what they were before card 146.
    assert by_id[SOUND_PMID] == {"title": SOUND_TITLE}


def test_esummary_pubtype_is_read_the_same_way() -> None:
    assert ncbi_eutils_actions.record_is_retracted(
        {
            "pubtype": [
                "Journal Article",
                "Research Support, Non-U.S. Gov't",
                "Retracted Publication",
            ]
        }
    )
    assert not ncbi_eutils_actions.record_is_retracted({"pubtype": ["Retraction Notice"]})
    assert not ncbi_eutils_actions.record_is_retracted({"title": "RETRACTED: a paper"})
    assert not ncbi_eutils_actions.record_is_retracted({"retracted": "yes"})


# ------------------------------------------------------------------ the rows


def _pubmed_output(*articles: str) -> NcbiEfetchOutput:
    records = ncbi_eutils_actions._extract_pubmed_articles(_efetch_body(*articles))
    return NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=records,
        record_count=len(records),
        total_available=len(records),
        truncated=False,
    )


def test_the_flag_rides_beside_the_row_fields_never_inside_them() -> None:
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(
        _pubmed_output(RETRACTED_XML, SOUND_XML), "pubmed_abstracts"
    )
    rows = shaped["rows"]
    retracted = [r for r in rows if r["source_url"].endswith(f"/{RETRACTED_PMID}/")]
    sound = [r for r in rows if r["source_url"].endswith(f"/{SOUND_PMID}/")]
    assert len(retracted) == 2, "populate-check: the title row and the abstract row"
    assert all(r.get("retracted") is True for r in retracted)
    assert all("retracted" not in r["fields"] for r in rows)
    assert sound == [
        {
            "curie": "",
            "node_or_edge_type": "pubmed",
            "fields": {"title": SOUND_TITLE},
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{SOUND_PMID}/",
        }
    ]
    generic = graph_module._ncbi_efetch_output_to_structured_fields(_pubmed_output(RETRACTED_XML))
    assert all("retracted" not in r["fields"] for r in generic["rows"])
    assert all(r.get("retracted") is True for r in generic["rows"])


def _finding(call_id: str, tool: str, layer: str, structured: dict[str, Any]) -> Finding:
    return Finding(
        call_id=call_id,
        tool=tool,
        layer=layer,
        source="structured_pass_through",
        structured_fields=structured,
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _pubmed_finding(*articles: str) -> Finding:
    return _finding(
        "ne-card146",
        "ncbi_efetch",
        "layer_2_api",
        graph_module._ncbi_efetch_output_to_structured_fields(
            _pubmed_output(*articles), "pubmed_abstracts"
        ),
    )


def _pubtator_finding(*pmid_titles: tuple[str, str]) -> Finding:
    publications = []
    for index, (pmid, title) in enumerate(pmid_titles):
        doc = {
            "_id": f"{pmid}|None",
            "id": pmid,
            "passages": [
                {"infons": {"type": "title"}, "offset": 0, "text": title, "annotations": []}
            ],
        }
        publication, _ = _parse_publication(doc, index)
        assert publication is not None
        publications.append(publication)
    output = PubtatorAnnotateOutput(
        status="ok", mode="annotate_publications", publications=publications
    )
    return _finding(
        "pa-card146",
        "pubtator_annotate",
        "layer_3_enrichment",
        graph_module._layer_tool_output_to_structured_fields("pubtator_annotate", output),
    )


# ------------------------------------------------------------------ the writer


def test_the_writer_is_told_by_marker_only_when_a_retracted_record_is_shown() -> None:
    synth, _ = build_synth_findings(
        [_pubmed_finding(RETRACTED_XML, SOUND_XML)], graph_module._pick_representative_field
    )
    flagged = [f.ref_index for f in synth if f.retracted]
    assert flagged, "populate-check: the flag reached the finding"
    prompt = build_synth_messages(QUESTION, synth)[1]["content"]
    line = next(line for line in prompt.splitlines() if line.startswith("RETRACTED PAPERS:"))
    assert all(f"[{index}]" in line for index in flagged)
    assert "Never state what a retracted paper found or reported as fact." in line
    # The line is about the flag: no title, no PMID, no word of the question.
    assert RETRACTED_TITLE[:20] not in line and RETRACTED_PMID not in line
    # The cached system block never changes.
    assert build_synth_messages(QUESTION, synth)[0]["content"] == SYNTH_SYSTEM_INSTRUCTION

    sound, _ = build_synth_findings(
        [_pubmed_finding(SOUND_XML)], graph_module._pick_representative_field
    )
    sound_prompt = build_synth_messages(QUESTION, sound)[1]["content"]
    assert "RETRACTED" not in sound_prompt


# ------------------------------------------------------------------ the page


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    article_titles.reset_cache_for_tests()


def _install_writer(monkeypatch: pytest.MonkeyPatch, prompts: list[str]) -> None:
    """A writer whose one sentence grounds nothing, so the listing is the page."""

    async def _dispatch(*_args: object, **kwargs: object) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            prompts.append(joined)
            content = "Nothing here matches any record at all."
        else:
            content = "ok"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


class _Lookup:
    """The title lookup's EFetch, answering from real-shaped XML."""

    def __init__(self, articles: dict[str, str], fail: bool = False) -> None:
        self.articles = articles
        self.fail = fail
        self.requested: list[list[str]] = []

    async def __call__(self, params: Any) -> NcbiEfetchOutput:
        self.requested.append(list(params.ids))
        if self.fail:
            return NcbiEfetchOutput(
                status="error",
                action="fetch",
                records=[],
                record_count=0,
                truncated=False,
                error="timeout",
            )
        wanted = [self.articles[pmid] for pmid in params.ids if pmid in self.articles]
        return _pubmed_output(*wanted)


async def _page(
    monkeypatch: pytest.MonkeyPatch, depth: str, findings: list[Finding]
) -> tuple[list[Any], list[dict[str, Any]], list[str]]:
    prompts: list[str] = []
    _install_writer(monkeypatch, prompts)
    query = Query(
        text=QUESTION,
        session_id="session-card146",
        trace_id="trace-card146",
        user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    state: dict[str, object] = {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "context": RequestContext(surface="web_ui", reads_placement=True),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": findings,
        "findings_count": len(findings),
    }
    result = await graph_module.write_node(state)
    events = result["events"]
    tokens = in_reading_order([e.payload for e in events if e.type == "token"])
    return events, tokens, prompts


def _rows(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tokens if t["kind"] in ("table_row", "list_item")]


def _row_for(tokens: list[dict[str, Any]], pmid: str) -> dict[str, Any]:
    rows = [t for t in _rows(tokens) if pmid in t["text"] or any(pmid in c for c in t["cells"])]
    assert len(rows) == 1, (pmid, _rows(tokens))
    return rows[0]


def _assert_tagged(row: dict[str, Any]) -> None:
    assert row["cells"][0].endswith(" (Retracted)"), row
    assert row["text"].startswith("Retracted: "), row


def _assert_untagged(row: dict[str, Any]) -> None:
    assert "Retracted" not in row["cells"][0], row
    assert not row["text"].startswith("Retracted"), row


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
async def test_a_live_pubmed_paper_is_tagged_on_every_surface(monkeypatch, depth) -> None:
    lookup = _Lookup({})
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    events, tokens, prompts = await _page(
        monkeypatch, depth, [_pubmed_finding(RETRACTED_XML, SOUND_XML)]
    )
    retracted_row = next(t for t in _rows(tokens) if RETRACTED_TITLE[:30] in t["cells"][0])
    sound_row = next(t for t in _rows(tokens) if SOUND_TITLE[:30] in t["cells"][0])
    _assert_tagged(retracted_row)
    _assert_untagged(sound_row)
    # The command line, MCP and GraphQL print the joined text.
    assert "Retracted: " in joined_text(tokens)
    # The saved answer is built from the cells.
    markdown = answer_markdown_from(events) or ""
    assert "(Retracted)" in markdown
    assert markdown.count("(Retracted)") == 1, markdown
    # The writer is told, by marker.
    assert prompts and "RETRACTED PAPERS:" in prompts[0]
    assert lookup.requested == [], "a live PubMed paper needs no lookup"


@pytest.mark.asyncio
async def test_a_pubtator_paper_read_beside_its_pubmed_record_needs_no_lookup(monkeypatch) -> None:
    lookup = _Lookup({RETRACTED_PMID: RETRACTED_XML})
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    _, tokens, _ = await _page(
        monkeypatch,
        "researcher",
        [
            _pubmed_finding(RETRACTED_XML, SOUND_XML),
            _pubtator_finding((RETRACTED_PMID, RETRACTED_TITLE), (SOUND_PMID, SOUND_TITLE)),
        ],
    )
    retracted_rows = [t for t in _rows(tokens) if RETRACTED_TITLE[:30] in t["cells"][0]]
    sound_rows = [t for t in _rows(tokens) if SOUND_TITLE[:30] in t["cells"][0]]
    assert retracted_rows and sound_rows, _rows(tokens)
    for row in retracted_rows:
        _assert_tagged(row)
    for row in sound_rows:
        _assert_untagged(row)
    assert lookup.requested == []


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
async def test_a_pubtator_paper_alone_is_tagged_from_the_lookup(monkeypatch, depth) -> None:
    """A-134-02: the background PubMed search did not finish, so the
    PubTator3 title names the row. Its publication type is read by the
    title lookup, one request."""
    lookup = _Lookup({RETRACTED_PMID: RETRACTED_XML, SOUND_PMID: SOUND_XML})
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    _, tokens, prompts = await _page(
        monkeypatch,
        depth,
        [_pubtator_finding((RETRACTED_PMID, RETRACTED_TITLE), (SOUND_PMID, SOUND_TITLE))],
    )
    assert len(lookup.requested) == 1
    assert sorted(lookup.requested[0]) == sorted([RETRACTED_PMID, SOUND_PMID])
    tagged = [t for t in _rows(tokens) if t["cells"][0].endswith(" (Retracted)")]
    assert len(tagged) == 1 and RETRACTED_TITLE[:30] in tagged[0]["cells"][0], _rows(tokens)
    assert tagged[0]["text"].startswith("Retracted: ")
    untagged = [t for t in _rows(tokens) if t is not tagged[0]]
    assert untagged and all("Retracted" not in t["cells"][0] for t in untagged)
    assert "RETRACTED PAPERS:" in prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [True, False], ids=["lookup_failed", "pubmed_returned_no_record"])
async def test_unknown_is_never_taken_for_retracted(monkeypatch, fail) -> None:
    lookup = _Lookup({}, fail=fail)
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    _, tokens, prompts = await _page(
        monkeypatch, "researcher", [_pubtator_finding((RETRACTED_PMID, RETRACTED_TITLE))]
    )
    assert lookup.requested, "populate-check: the lookup was tried"
    _assert_untagged(_row_for(tokens, RETRACTED_PMID))
    assert "RETRACTED" not in prompts[0]


def _graph_finding(pmids: list[str]) -> Finding:
    rows = [
        {
            "node_or_edge_type": "Article",
            "curie": f"PMID:{pmid}",
            "fields": {},
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "graph_snapshot_version": "v1",
        }
        for pmid in pmids
    ]
    return _finding(
        "cq-card146",
        "cypher_query",
        "layer_1_graph",
        {
            "status": "ok",
            "row_count": len(rows),
            "total_available": len(rows),
            "truncated": False,
            "rows": rows,
            "error": None,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
async def test_a_graph_paper_is_tagged_from_its_title_lookup(monkeypatch, depth) -> None:
    lookup = _Lookup({RETRACTED_PMID: RETRACTED_XML, SOUND_PMID: SOUND_XML})
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    _, tokens, prompts = await _page(
        monkeypatch, depth, [_graph_finding([RETRACTED_PMID, SOUND_PMID])]
    )
    assert len(lookup.requested) == 1
    rows = _rows(tokens)
    retracted_row = next(t for t in rows if RETRACTED_TITLE[:30] in t["cells"][0])
    sound_row = next(t for t in rows if SOUND_TITLE[:30] in t["cells"][0])
    _assert_tagged(retracted_row)
    _assert_untagged(sound_row)
    assert "RETRACTED PAPERS:" in prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
async def test_a_sound_paper_reads_exactly_as_before(monkeypatch, depth) -> None:
    """The row, its text and the writer's prompt, as develop produced them
    (measured on develop at 4eda8ca5 before card 146 changed any code)."""
    lookup = _Lookup({})
    monkeypatch.setattr(ncbi_eutils_actions, "fetch", lookup)
    _, tokens, prompts = await _page(monkeypatch, depth, [_pubmed_finding(SOUND_XML)])
    rows = _rows(tokens)
    expected_kind = "list_item"
    assert [(t["kind"], t["text"], t["cells"]) for t in rows] == [
        (
            expected_kind,
            "Pubmed title: Molecular Structure of the Human CFTR Ion Channel [1]. ",
            [SOUND_TITLE],
        )
    ]
    assert "RETRACTED" not in prompts[0]
    assert lookup.requested == []
