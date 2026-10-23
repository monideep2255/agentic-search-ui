"""Card 134: a paper from the literature index is listed by its title.

Seen on deployed develop, 2026-10-18 (`testing/Developer/reports/
2026-10-18_browser_retest/report.md`, rows 2 and 3): when the background
PubMed search did not finish, or did not return the paper, the papers under
"Publication records found" read "28340353 PMID:28340353". The PubTator3
publication row carried only `pmid` and `annotation_count`, so its label
fell back to the number while the Identifier cell beside it showed the same
number again.

The PubTator3 response already holds each paper's PubMed title, as its
`title` passage. The fix keeps that title on the row and labels the row by
it. With no title held, the row reads "Title not retrieved" beside its PMID,
never the number twice and never an invented title. The row's cited fact,
what the writer is shown and the per-page fold do not move.

The document shapes below are PubTator3's own, read live on 2026-10-22 for
PMIDs 28340353 and 20301425 (the two papers in the report), trimmed to the
title passage and the start of the abstract.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.contracts.token_order import in_reading_order
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.answer_layout import (
    UNTITLED_PAPER_LABEL,
    summary_label,
)
from system_03_search_agent.synthesis.findings import (
    SYNTH_SYSTEM_INSTRUCTION,
    build_synth_findings,
)
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord
from system_03_search_agent.tools.pubtator_annotate import _parse_publication
from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateOutput

CFTR_PMID = "28340353"
CFTR_TITLE = "Molecular Structure of the Human CFTR Ion Channel."
HBOC_PMID = "20301425"
HBOC_RAW_TITLE = "<i>BRCA1-</i> and <i>BRCA2</i>-Associated Hereditary Breast and Ovarian Cancer"
HBOC_TITLE = "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer"


def _doc(pmid: str, title: str | None) -> dict:
    """One `.PubTator3[i]` document in the live shape: `id`, then passages
    whose `infons.type` names them, each with its own annotations."""
    passages = []
    if title is not None:
        passages.append(
            {
                "infons": {"type": "title"},
                "offset": 0,
                "text": title,
                "annotations": [
                    {
                        "id": "1",
                        "infons": {
                            "identifier": "1080",
                            "type": "Gene",
                            "valid": True,
                            "normalized_id": 1080,
                            "database": "ncbi_gene",
                            "name": "CFTR",
                            "biotype": "gene",
                        },
                        "text": "CFTR",
                        "locations": [{"offset": 28, "length": 4}],
                    }
                ],
            }
        )
    passages.append(
        {
            "infons": {"type": "abstract"},
            "offset": 52,
            "text": (
                "The cystic fibrosis transmembrane conductance regulator (CFTR) is an "
                "ATP-binding cassette (ABC) transporter that uniquely functions as an ion channel."
            ),
            "annotations": [],
        }
    )
    return {"_id": f"{pmid}|None", "id": pmid, "passages": passages}


def _publication(pmid: str, title: str | None):
    publication, _notes = _parse_publication(_doc(pmid, title), 0)
    assert publication is not None, "populate-check: the parser kept no publication"
    return publication


def _pubtator_finding(*publications) -> Finding:
    output = PubtatorAnnotateOutput(
        status="ok", mode="annotate_publications", publications=list(publications)
    )
    return Finding(
        call_id="pt-card134",
        tool="pubtator_annotate",
        layer="layer_3_enrichment",
        source="structured_pass_through",
        structured_fields=graph_module._layer_tool_output_to_structured_fields(
            "pubtator_annotate", output
        ),
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _pubmed_finding(pmid: str, title: str) -> tuple[Finding, NcbiEfetchOutput]:
    """The background PubMed search when it finishes: its live title row."""
    output = NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=[
            NcbiEfetchRecord(
                id=pmid,
                db="pubmed",
                fields={"title": title},
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        ],
        record_count=1,
        total_available=1,
        truncated=False,
    )
    finding = Finding(
        call_id="ne-card134",
        tool="ncbi_efetch",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
            output, "pubmed_abstracts"
        ),
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )
    return finding, output


# ------------------------------------------------------------ the tool


def test_the_parser_keeps_the_title_passage_as_written() -> None:
    assert _publication(CFTR_PMID, CFTR_TITLE).title == CFTR_TITLE


def test_the_parser_removes_only_pubmeds_formatting_tags() -> None:
    assert _publication(HBOC_PMID, HBOC_RAW_TITLE).title == HBOC_TITLE
    notation = "The CFTR c.3140-26A>G variant in children <5 years"
    assert _publication(CFTR_PMID, notation).title == notation


def test_a_document_without_a_title_passage_has_no_title() -> None:
    assert _publication(CFTR_PMID, None).title is None
    assert _publication(CFTR_PMID, "   ").title is None


def test_an_over_long_title_is_withheld_and_disclosed_never_clipped() -> None:
    publication, notes = _parse_publication(_doc(CFTR_PMID, "word " * 120), 0)
    assert publication is not None and publication.title is None
    assert notes and notes[0].startswith("publications[0].title: ")


# ------------------------------------------------------------ the row


def test_the_row_keeps_its_cited_fact_and_carries_the_title_last() -> None:
    finding = _pubtator_finding(_publication(CFTR_PMID, CFTR_TITLE))
    row = finding.structured_fields["rows"][0]
    assert list(row["fields"]) == ["pmid", "annotation_count", "title"]
    assert row["fields"]["title"] == CFTR_TITLE
    synth, _ = build_synth_findings([finding], graph_module._pick_representative_field)
    assert [(f.field, f.field_value) for f in synth] == [("pmid", CFTR_PMID)]


def test_a_placeholder_title_is_not_kept_on_the_row() -> None:
    finding = _pubtator_finding(_publication(CFTR_PMID, "[Not Available]."))
    assert "title" not in finding.structured_fields["rows"][0]["fields"]


def test_the_summary_names_an_untitled_paper_by_its_pmid() -> None:
    finding = _pubtator_finding(_publication(CFTR_PMID, None))
    row = finding.structured_fields["rows"][0]
    synth, _ = build_synth_findings([finding], graph_module._pick_representative_field)
    assert summary_label(synth[0], row) == f"PMID:{CFTR_PMID}"


# ------------------------------------------------------------ the page


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


def _install(monkeypatch: pytest.MonkeyPatch, prompts: list[str]) -> None:
    """The writer is faked with a sentence that grounds nothing, so the
    code-built list of records is the page."""

    async def _dispatch(*_args: object, **kwargs: object):
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


async def _page(
    monkeypatch: pytest.MonkeyPatch,
    depth: str,
    findings: list[Finding],
    layer2_raw_outputs: dict | None = None,
) -> tuple[list[dict], list[str]]:
    prompts: list[str] = []
    _install(monkeypatch, prompts)
    query = Query(
        text="What is the structure of the CFTR protein?",
        session_id="session-card134",
        trace_id="trace-card134",
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
    if layer2_raw_outputs:
        state["layer2_raw_outputs"] = layer2_raw_outputs
    result = await graph_module.write_node(state)
    tokens = in_reading_order([e.payload for e in result["events"] if e.type == "token"])
    return tokens, prompts


def _rows(tokens: list[dict]) -> list[list[str]]:
    return [t["cells"] for t in tokens if t["kind"] in ("table_row", "list_item")]


def _no_doubled_number(rows: list[list[str]]) -> None:
    for cells in rows:
        for pmid in (CFTR_PMID, HBOC_PMID):
            assert cells[:2] != [pmid, f"PMID:{pmid}"], cells
            assert cells[:1] != [pmid], cells


@pytest.mark.asyncio
async def test_researcher_lists_a_held_title_beside_its_pmid(monkeypatch) -> None:
    findings = [
        _pubtator_finding(
            _publication(CFTR_PMID, CFTR_TITLE), _publication(HBOC_PMID, HBOC_RAW_TITLE)
        )
    ]
    tokens, prompts = await _page(monkeypatch, "researcher", findings)
    rows = _rows(tokens)
    assert sorted(rows) == sorted(
        [[CFTR_TITLE, f"PMID:{CFTR_PMID}"], [HBOC_TITLE, f"PMID:{HBOC_PMID}"]]
    ), rows
    _no_doubled_number(rows)
    assert prompts, "populate-check: the writer was never shown the findings"
    # What the writer is shown does not move: the row's cited fact is its
    # PMID, and the title is the list's label only.
    assert CFTR_TITLE not in prompts[0]


@pytest.mark.asyncio
async def test_plain_language_lists_a_held_title(monkeypatch) -> None:
    findings = [_pubtator_finding(_publication(CFTR_PMID, CFTR_TITLE))]
    tokens, _ = await _page(monkeypatch, "plain_language", findings)
    assert _rows(tokens) == [[CFTR_TITLE]], _rows(tokens)


@pytest.mark.asyncio
async def test_with_no_title_held_the_row_says_so_and_keeps_its_number(monkeypatch) -> None:
    findings = [_pubtator_finding(_publication(CFTR_PMID, None))]
    tokens, _ = await _page(monkeypatch, "researcher", findings)
    rows = _rows(tokens)
    assert rows == [[UNTITLED_PAPER_LABEL, f"PMID:{CFTR_PMID}"]], rows
    _no_doubled_number(rows)
    plain_tokens, _ = await _page(monkeypatch, "plain_language", findings)
    assert _rows(plain_tokens) == [["Published paper"]], _rows(plain_tokens)


@pytest.mark.asyncio
async def test_when_the_background_search_finishes_the_paper_is_listed_once_by_title(
    monkeypatch,
) -> None:
    """As today: the live PubMed title row and the literature-index row
    share the paper's page, and the paper is one row named by its title."""
    pubmed, output = _pubmed_finding(CFTR_PMID, CFTR_TITLE)
    for title in (CFTR_TITLE, None):
        findings = [pubmed, _pubtator_finding(_publication(CFTR_PMID, title))]
        tokens, _ = await _page(
            monkeypatch, "researcher", findings, {"ne-card134": output}
        )
        rows = _rows(tokens)
        named = [cells for cells in rows if CFTR_TITLE in cells]
        assert len(named) == 1, rows
        assert not any(UNTITLED_PAPER_LABEL in cells for cells in rows), rows
        _no_doubled_number(rows)
