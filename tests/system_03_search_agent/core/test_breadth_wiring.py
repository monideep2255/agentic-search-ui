"""UI fix 11.21, the wiring: the breadth plan runs beside the existing calls.

What this file grades, offline, with the model and every tool replaced by
fakes whose bytes the test controls (the same discipline as
`test_layer_handoff.py`: the loop's own nodes run their real bodies):

    THE PLAN. A resolved gene plans, beside the four calls set 8 already
    planned, a PubMed search and a ClinVar search (stage one), and declares
    the abstract fetch, the PubTator3 publication annotation and the
    the ClinVar summary as follow-ups whose ids come from those searches, plus
    a code-chosen GO template as a second, context-only graph call. Item 2b
    (2026-09-22) adds the OMIM search and the OMIM summary to that list.
    The plan event's tool list is fixed per question shape.

    THE SECOND STAGE. The follow-ups run AFTER the searches, with the ids
    the searches returned, sorted highest first and capped, and the
    abstract fetch and the publication annotation name the identical
    PMIDs. A search that fails or returns nothing closes its follow-ups as
    `empty` with a disclosure and no request; the run still answers from
    the graph.

    THE GO TEMPLATE. `gene_go_terms_one` traverses one bound gene's own GO
    edges and names that gene as `go_attribution_param`; `cypher_query`
    passes the bound CURIE to `to_output_rows`, so a GO vertex is cited to
    the gene page whose annotation it is, never to a gene that shares a
    row. Two bound genes never produce the template.

    DETERMINISM. Three runs of one question, with the fakes returning ids
    in a different order each time, produce the same plan, the same
    citation source set, and the same follow-up inputs.

    THE GRAPH ORDER (L-01, shape 2). A list column of collected vertices
    is emitted sorted by CURIE, whatever order the aggregate produced.

    THE LAYER 2 CITATION. A claim on the second record of a two-record
    `ncbi_efetch` output cites the second record's URL and id.

    ABSTRACTS (UI fix 11.22). The abstract text now reaches the synthesis
    prompt too, verbatim and alongside the title, never in place of it; a
    clause Synth writes that is not drawn verbatim from a retrieved
    abstract is stripped by the unmodified grounding pass rather than
    shipped. See `tests/system_03_search_agent/synthesis/test_pubmed_
    abstract_grounding.py` for the grounding-level proof; this file only
    proves the abstract is actually wired into the live prompt.

    THE ALLOTMENT. With a lead quota, the answer-shape rows are admitted
    first up to the quota and the context calls then share the remaining
    slots one row per call per round, so no source is crowded out.

    OMIM (item 2b, 2026-09-22). A question about one gene never shows an
    OMIM record for a different gene: OMIM's own search ranks `MAP4K2`
    first for `GCK`, and the record whose title does not name the asked
    symbol in a symbol field is dropped in the act shaping step, before it
    can become a row, a finding or a citation. With no resolved symbol,
    nothing is kept. The surviving record's `omim.org` citation passes the
    citation contract's own host pattern. One arm replaces
    `filter_omim_titles` with the identity function and asserts the
    wrong-gene record then DOES appear, so the drop is proven to be that
    filter's doing rather than an accident of the cap, the sort or a
    missing record URL.

EVERY ARM CARRIES A POPULATE-CHECK where a negative or comparative
assertion could otherwise pass on nothing.

Not exercised here, stated so the gap is arguable: the live APIs' own
answers and their latency, which the build report's live table measures;
the rendering of the new sources on screen; the count of transport calls,
which the fakes bypass (measured live in the report against the ceiling);
and whether OMIM's real titles for a given symbol take the `NAME; SYMBOL`
shape the filter reads, which only a live run can say and which
`testing/Developer/reports/2026-09-22_OMIM_live/findings.md` measures.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run import run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.synthesis.findings import SynthFinding, build_synth_findings
from system_03_search_agent.tools import cypher_provenance
from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.clinicaltrials_search_schemas import ClinicalTrialsSearchOutput
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.cypher_templates import (
    all_template_examples,
    gene_go_terms_template,
)
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    PubtatorAnnotateOutput,
    PubtatorPublication,
)
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    fake_response,
)

_GENE_QUESTION = "Which diseases are associated with BRCA1?"
_GCK_QUESTION = "Which diseases are associated with GCK?"
_KNOWN = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157", "GCK": "NCBIGene:2645"}
_ABSTRACT = "Loss of BRCA1 function abolishes homologous recombination in this cohort."

# Item 2b. Real OMIM entry numbers and the `NAME; SYMBOL` title shape OMIM
# publishes. `603166` is the MAP4K2 entry, the record OMIM's own search
# ranks FIRST for the symbol `GCK` (measured in the 2026-09-14 breadth
# audit), which is the wrong-gene case the filter exists to drop.
_OMIM_BRCA1 = ("113705", "BREAST CANCER 1 GENE; BRCA1")
_OMIM_GCK = ("138079", "GLUCOKINASE; GCK")
_OMIM_MAP4K2 = ("603166", "MITOGEN-ACTIVATED PROTEIN KINASE KINASE KINASE KINASE 2; MAP4K2")


def _omim_url(uid: str) -> str:
    return f"https://omim.org/entry/{uid}"


# ---------------------------------------------------------------------------
# Fixtures: environment, caps, model, tools.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    def _user_check(session: Any, user_id: Any, **kwargs: Any) -> None:
        return None

    def _system_check(session: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)


class _ModelSpy:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, entity: str = "BRCA1") -> None:
        from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
        from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
        from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

        self.synth_prompts: list[str] = []

        async def _dispatch(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages") or []
            joined = "\n".join(m.get("content") or "" for m in messages)
            if GUARD_SYSTEM_INSTRUCTION in joined:
                return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
            if _THINK_SYSTEM_INSTRUCTION in joined:
                return fake_response(
                    json.dumps(
                        {
                            "query_class": "single_hop",
                            "narrative": "stand-in classification",
                            "entities": [{"text": entity, "entity_type": "gene"}],
                        }
                    )
                )
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                self.synth_prompts.append(joined)
                return fake_response(compliant_synth_narrative(messages))
            return fake_response("ok")

        monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
        monkeypatch.setattr(
            harness_module.litellm,
            "get_model_info",
            lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
        )


def _install_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolve(symbol: str, **kwargs: Any) -> str | None:
        return _KNOWN.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _resolve)


def _disease_rows() -> list[CypherQueryRow]:
    return [
        CypherQueryRow(
            node_or_edge_type="Disease",
            curie=f"MedGen:C{n}",
            fields={"name": f"disease {n}"},
            source_url=f"https://www.ncbi.nlm.nih.gov/medgen/C{n}",
            graph_snapshot_version="v1",
        )
        for n in (1, 2, 3)
    ]


def _go_rows() -> list[CypherQueryRow]:
    return [
        CypherQueryRow(
            node_or_edge_type="BiologicalProcess",
            curie="GO:0006281",
            fields={"name": "DNA repair", cypher_provenance.CITED_VIA_GENE_FIELD: "NCBIGene:672"},
            source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            graph_snapshot_version="v1",
        )
    ]


class _ToolSpy:
    """Fakes for every tool, recording each input. `pubmed_ids` and
    `clinvar_ids` are what the two searches answer, in the order given, so
    a test can shuffle them between runs."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        pubmed_ids: list[str] | None = None,
        clinvar_ids: list[str] | None = None,
        omim_titles: dict[str, str] | None = None,
        search_status: str = "ok",
        summary_raises: bool = False,
    ) -> None:
        self.efetch_inputs: list[dict[str, Any]] = []
        self.pubtator_inputs: list[dict[str, Any]] = []
        self.cypher_templates: list[str | None] = []
        self.pubmed_ids = ["30000001", "30000003", "30000002"] if pubmed_ids is None else pubmed_ids
        self.clinvar_ids = ["12", "11", "13"] if clinvar_ids is None else clinvar_ids
        # Item 2b: what OMIM answers, uid to title. The default pairs the
        # right gene's entry with the wrong gene's, so the DEFAULT path of
        # every arm in this file runs the filter on a mixed result rather
        # than on a clean one.
        self.omim_titles = (
            dict([_OMIM_BRCA1, _OMIM_MAP4K2]) if omim_titles is None else dict(omim_titles)
        )

        async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
            template = kwargs.get("template")
            self.cypher_templates.append(template.name if template is not None else None)
            rows = _go_rows() if template is not None else _disease_rows()
            return CypherQueryOutput(
                status="ok", row_count=len(rows), total_available=len(rows), truncated=False,
                rows=rows, error=None, template=template.name if template else None,
            )

        async def _efetch(tool_input: Any, **kwargs: Any) -> NcbiEfetchOutput:
            root = tool_input.root
            self.efetch_inputs.append(root.model_dump())
            if root.action == "search":
                if search_status != "ok":
                    return NcbiEfetchOutput(
                        status="error", action="search", records=[], record_count=0,
                        total_available=None, truncated=False, error="ESearch failed",
                    )
                if root.db == "pubmed":
                    ids = list(self.pubmed_ids)
                elif root.db == "omim":
                    ids = list(self.omim_titles)
                else:
                    ids = list(self.clinvar_ids)
                return NcbiEfetchOutput(
                    status="ok", action="search",
                    records=[NcbiEfetchRecord(db=root.db, fields={"idlist": list(ids), "idlist_count": len(ids)})],
                    record_count=1, total_available=len(ids), truncated=False,
                )
            if root.action == "summary":
                if summary_raises:
                    raise RuntimeError("summary exploded")
                if root.db == "omim":
                    # An OMIM ESummary record, with the four fields the tool's
                    # own allowlist keeps (`ncbi_eutils_actions._SUMMARY_
                    # FIELDS["omim"]`) and OMIM's real `omim.org/entry/{id}`
                    # record URL.
                    omim_records = [
                        NcbiEfetchRecord(
                            id=uid, db="omim",
                            fields={
                                "oid": f"OMIM:{uid}",
                                "title": self.omim_titles[uid],
                                "alttitles": "",
                                "locus": "7p13",
                            },
                            source_url=_omim_url(uid),
                        )
                        for uid in root.ids
                        if uid in self.omim_titles
                    ]
                    return NcbiEfetchOutput(
                        status="ok", action="summary", records=omim_records,
                        record_count=len(omim_records), total_available=len(omim_records),
                        truncated=False,
                    )
                records = [
                    NcbiEfetchRecord(
                        id=uid, db="clinvar",
                        fields={
                            "accession": f"VCV{uid}", "title": f"NM_007294.4(BRCA1):c.{uid}del",
                            "germline_classification": {"description": "Pathogenic"},
                            "variation_set": [{"big": "nested"}], "genes": [{"symbol": "BRCA1"}],
                        },
                        source_url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
                    )
                    for uid in root.ids
                ]
                return NcbiEfetchOutput(
                    status="ok", action="summary", records=records, record_count=len(records),
                    total_available=len(records), truncated=False,
                )
            if root.action == "fetch":
                records = [
                    NcbiEfetchRecord(
                        id=pmid, db="pubmed",
                        fields={"title": f"BRCA1 paper {pmid}", "abstract": _ABSTRACT},
                        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    )
                    for pmid in root.ids
                ]
                return NcbiEfetchOutput(
                    status="ok", action="fetch", records=records, record_count=len(records),
                    total_available=len(records), truncated=False,
                )
            return NcbiEfetchOutput(
                status="empty", action=root.action, records=[], record_count=0,
                total_available=None, truncated=False, error=None,
            )

        async def _pubtator(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
            root = tool_input.root
            self.pubtator_inputs.append(root.model_dump())
            if root.mode == "annotate_publications":
                return PubtatorAnnotateOutput(
                    status="ok", mode="annotate_publications",
                    publications=[
                        PubtatorPublication(
                            pmid=pmid, total_annotations=3,
                            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        )
                        for pmid in root.pmids
                    ],
                )
            return PubtatorAnnotateOutput(status="empty", mode="entity_lookup")

        async def _trials(tool_input: Any, **kwargs: Any) -> ClinicalTrialsSearchOutput:
            return ClinicalTrialsSearchOutput(status="empty")

        monkeypatch.setattr(graph_module, "cypher_query", _cypher)
        monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
        monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)
        monkeypatch.setattr(graph_module, "clinicaltrials_search", _trials)


def _query(text: str, session_id: str = "s-1") -> Query:
    return Query(
        text=text, session_id=session_id, trace_id=f"trace-{session_id}",
        user_id=None, audience_depth="researcher",
    )


async def _events(text: str, session_id: str = "s-1") -> list[Any]:
    context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)
    return [event async for event in run_streaming(_query(text, session_id), context)]


def _plan_tools(events: list[Any]) -> list[tuple[str, str]]:
    plan = next(e for e in events if e.type == "plan")
    return [(c["tool"], c["layer"]) for c in plan.payload["tool_calls"]]


def _results(events: list[Any]) -> list[dict[str, Any]]:
    return [e.payload for e in events if e.type == "tool_result"]


def _sources(events: list[Any]) -> set[str]:
    return {e.payload["source_url"] for e in events if e.type == "citation"}


# ---------------------------------------------------------------------------
# The plan.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_resolved_gene_plans_the_breadth_calls_beside_the_existing_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    _ToolSpy(monkeypatch)
    events = await _events(_GENE_QUESTION)
    tools = _plan_tools(events)
    assert tools[0] == ("cypher_query", "layer_1_graph"), "the primary graph call stays first"
    assert tools.count(("cypher_query", "layer_1_graph")) == 2, "the GO template is a second graph call"
    # Set 8's four, unchanged, plus seven breadth calls (three searches and
    # four follow-ups, item 2b having added the OMIM pair on 2026-09-22),
    # plus item 11.31's Gene ESummary, which is planned DIRECTLY from the
    # resolved CURIE and is not a follow-up of any search.
    assert tools.count(("ncbi_efetch", "layer_2_api")) == 1 + 3 + 3 + 1, tools
    assert tools.count(("pubtator_annotate", "layer_3_enrichment")) == 2, tools
    assert tools.count(("clinicaltrials_search", "layer_3_enrichment")) == 1, tools
    assert len(tools) == 13, tools


def test_the_breadth_plan_dispatches_omim_with_the_symbol_and_needs_a_symbol() -> None:
    """INVERTED on 2026-09-22 (item 2b) rather than deleted: this arm used
    to pin that OMIM is never planned, which was true while its records
    could not be cited and then while nothing checked them against the
    asked gene. Both controls exist now, so the arm pins the opposite, and
    additionally pins the thing the earlier absence made unnecessary: the
    OMIM follow-up carries the resolved symbol, which is what lets Act drop
    a record for another gene."""
    calls = graph_module._build_breadth_calls("BRCA1")
    purposes = [getattr(c, "purpose", "") for c in calls]
    assert purposes == [
        "pubmed_search", "clinvar_search", "omim_search", "pubmed_abstracts",
        "pubtator_publications", "clinvar_summary", "omim_summary",
    ], purposes
    omim_follow_ups = [c for c in calls if getattr(c, "purpose", "") == "omim_summary"]
    assert len(omim_follow_ups) == 1, calls
    assert omim_follow_ups[0].gene_symbol == "BRCA1", omim_follow_ups
    assert omim_follow_ups[0].source_purpose == "omim_search", omim_follow_ups
    assert graph_module._build_breadth_calls(None) == []
    # A mention that is not symbol-shaped plans nothing rather than
    # searching for text the reader never typed.
    assert graph_module._build_breadth_calls("BRCA1 OR cancer") == []


def test_the_go_call_is_context_only_and_never_an_answer_call() -> None:
    go_call = graph_module._build_planned_go_terms_call("NCBIGene:672", "single_hop")
    assert go_call.context_only is True
    assert go_call.template is not None and go_call.template.name == "gene_go_processes_one"
    assert go_call.cypher_input.target_entities == ["NCBIGene:672"]
    primary = graph_module._PlannedToolCall(
        tool_call=graph_module.ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
        cypher_input=go_call.cypher_input,
    )
    ids = graph_module._answer_call_ids([primary, go_call], _GENE_QUESTION)
    assert ids == frozenset({"cq-1"}), ids


# ---------------------------------------------------------------------------
# The second stage.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_follow_ups_run_on_the_sorted_capped_ids_the_searches_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    spy = _ToolSpy(monkeypatch)
    events = await _events(_GENE_QUESTION)
    fetches = [i for i in spy.efetch_inputs if i["action"] == "fetch"]
    summaries = [i for i in spy.efetch_inputs if i["action"] == "summary"]
    # Three summaries now: ClinVar's and OMIM's, whose ids come from their
    # own searches, and item 11.31's Gene ESummary, whose id comes from the
    # resolved CURIE. Selected by db rather than by position, so a
    # planning-order change cannot make this arm assert the wrong call's ids.
    clinvar_summaries = [i for i in summaries if i["db"] == "clinvar"]
    gene_summaries = [i for i in summaries if i["db"] == "gene"]
    omim_summaries = [i for i in summaries if i["db"] == "omim"]
    assert len(fetches) == 1 and len(summaries) == 3, spy.efetch_inputs
    assert len(clinvar_summaries) == 1 and len(gene_summaries) == 1, summaries
    assert len(omim_summaries) == 1, summaries
    assert fetches[0]["ids"] == ["30000003", "30000002", "30000001"], fetches
    assert clinvar_summaries[0]["ids"] == ["13", "12", "11"], clinvar_summaries
    assert gene_summaries[0]["ids"] == ["672"], gene_summaries
    assert omim_summaries[0]["ids"] == ["603166", "113705"], omim_summaries
    annotations = [i for i in spy.pubtator_inputs if i["mode"] == "annotate_publications"]
    assert len(annotations) == 1 and annotations[0]["pmids"] == fetches[0]["ids"]
    # The searches ran before the follow-ups: the follow-up inputs are
    # built from the search answers, so they cannot be issued earlier.
    order = [i["action"] for i in spy.efetch_inputs]
    assert order.index("search") < order.index("fetch") and order.index("search") < order.index("summary")
    # Every planned call started and closed, the premise gate's A1 and A2.
    starts = [e for e in events if e.type == "tool_start"]
    results = _results(events)
    assert len(starts) == 13 == len(results), (len(starts), len(results))
    # The new sources reach the answer.
    sources = _sources(events)
    assert "https://www.ncbi.nlm.nih.gov/clinvar/variation/13/" in sources, sources
    assert "https://pubmed.ncbi.nlm.nih.gov/30000003/" in sources, sources
    assert "https://www.ncbi.nlm.nih.gov/gene/672" in sources, sources
    # Item 2b: OMIM's BRCA1 entry is cited, and the MAP4K2 entry the same
    # fake returned beside it is not.
    assert _omim_url(_OMIM_BRCA1[0]) in sources, sources
    assert _omim_url(_OMIM_MAP4K2[0]) not in sources, sources


@pytest.mark.asyncio
async def test_a_failed_search_closes_its_follow_ups_empty_and_the_run_still_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    spy = _ToolSpy(monkeypatch, search_status="error")
    events = await _events(_GENE_QUESTION)
    # Item 11.31's Gene ESummary is excluded by db, deliberately: it is NOT a
    # follow-up. Its id comes from the CURIE the question already resolved,
    # so it is correct for it to run when every search fails, which is the
    # whole reason it was planned from the CURIE rather than from a search.
    assert not any(
        i["action"] in ("fetch", "summary") and i.get("db") != "gene"
        for i in spy.efetch_inputs
    ), "a follow-up must never be issued without ids"
    results = _results(events)
    assert len(results) == 13, [r["tool"] for r in results]
    empties = [r for r in results if r["status"] == "empty" and "no ids" in r["summary"]]
    # Four now: the OMIM summary joins the three earlier follow-ups in being
    # closed `empty` when its own search fails.
    assert len(empties) == 4, [(r["tool"], r["status"], r["summary"]) for r in results]
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] in ("answer", "ask"), done.payload
    assert "https://www.ncbi.nlm.nih.gov/medgen/C1" in _sources(events)


@pytest.mark.asyncio
async def test_a_follow_up_that_raises_degrades_to_an_error_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    _ToolSpy(monkeypatch, summary_raises=True)
    events = await _events(_GENE_QUESTION)
    results = _results(events)
    errors = [r for r in results if r["status"] == "error"]
    # Three `ncbi_efetch` errors now: the raising ClinVar summary this test
    # induces, item 2b's OMIM summary, and item 11.31's Gene ESummary, all
    # three raised by the same stub because it keys on the action rather
    # than on the db.
    assert len(errors) == 3 and {e["tool"] for e in errors} == {"ncbi_efetch"}, errors
    assert "https://www.ncbi.nlm.nih.gov/medgen/C1" in _sources(events)
    assert "https://pubmed.ncbi.nlm.nih.gov/30000003/" in _sources(events)


@pytest.mark.asyncio
async def test_the_abstract_now_reaches_the_prompt_beside_the_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI fix 11.22 reverses the pre-11.22 premise this test used to pin
    (see the module docstring's ABSTRACTS section): the retrieved abstract
    text is now wired into the live prompt, additively, beside the title
    that was already there. The grounding-level proof that a fabricated
    sentence still cannot ride along on this new content lives in
    `tests/system_03_search_agent/synthesis/test_pubmed_abstract_
    grounding.py`; this test only proves the wiring reaches the real
    coordinator-worker to Write path, with every tool and the model faked.
    """
    spy = _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    _ToolSpy(monkeypatch)
    await _events(_GENE_QUESTION)
    assert spy.synth_prompts, "populate-check: no synthesis prompt was captured"
    joined = "\n".join(spy.synth_prompts)
    assert "BRCA1 paper 30000003" in joined, "the pre-existing title finding must be unaffected"
    assert _ABSTRACT in joined, "the retrieved abstract text must now reach the prompt"


# ---------------------------------------------------------------------------
# Determinism.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_runs_with_shuffled_ids_produce_one_plan_and_one_source_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch)
    _install_lookup(monkeypatch)
    rng = random.Random(11)
    plans: list[list[tuple[str, str]]] = []
    sources: list[set[str]] = []
    follow_up_ids: list[tuple[list[str], list[str]]] = []
    for run in range(3):
        pubmed = ["30000001", "30000003", "30000002", "30000005", "30000004", "30000006"]
        clinvar = [str(n) for n in range(1, 13)]
        rng.shuffle(pubmed)
        rng.shuffle(clinvar)
        spy = _ToolSpy(monkeypatch, pubmed_ids=pubmed, clinvar_ids=clinvar)
        events = await _events(_GENE_QUESTION, session_id=f"s-{run}")
        plans.append(_plan_tools(events))
        sources.append(_sources(events))
        fetch = next(i for i in spy.efetch_inputs if i["action"] == "fetch")["ids"]
        # By db, not by position: item 11.31 added a second `summary` call
        # (the Gene ESummary), and this arm is about the ClinVar follow-up's
        # ids being stable across shuffles.
        summary = next(
            i for i in spy.efetch_inputs
            if i["action"] == "summary" and i["db"] == "clinvar"
        )["ids"]
        follow_up_ids.append((fetch, summary))
    assert plans[0] == plans[1] == plans[2], plans
    assert sources[0] == sources[1] == sources[2], sources
    assert len(sources[0]) >= 8, sources[0]
    assert follow_up_ids[0] == follow_up_ids[1] == follow_up_ids[2], follow_up_ids
    assert follow_up_ids[0][0] == ["30000006", "30000005", "30000004", "30000003", "30000002"]
    assert follow_up_ids[0][1] == ["12", "11", "10", "9", "8", "7", "6", "5", "4", "3"]


# ---------------------------------------------------------------------------
# The GO template and its attribution.
# ---------------------------------------------------------------------------


def test_the_go_template_names_its_anchor_as_the_attribution_gene() -> None:
    template = gene_go_terms_template("e_one")
    assert template.name == "gene_go_processes_one"
    assert template.go_attribution_param == "e_one"
    assert "$e_one" in template.cypher and "ORDER BY" in template.cypher
    # One edge, measured live 2026-09-20: AGE rejects a relationship-type
    # alternation, so the template traverses `participates_in` alone.
    assert "-[:participates_in]->(x:BiologicalProcess)" in template.cypher
    assert "|" not in template.cypher
    assert any(t.name == "gene_go_processes_one" for t in all_template_examples())


@pytest.mark.asyncio
async def test_cypher_query_cites_a_go_vertex_to_the_bound_gene_under_the_forced_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    go_vertex = (
        '{"id": 2, "label": "BiologicalProcess", "properties": '
        '{"id": "GO:0006281", "name": "DNA repair"}}::vertex'
    )
    seen: dict[str, Any] = {}

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        seen["cypher"] = cypher
        seen["params"] = params
        return [{"c0": go_vertex}], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)
    monkeypatch.setattr(cypher_query_module, "_graph_snapshot_version", lambda: "v-test")
    tool_input = CypherQueryInput(
        query_intent="Gene Ontology terms annotated to the gene",
        query_class="single_hop",
        target_entities=["NCBIGene:672"],
        row_limit=100,
    )
    template = gene_go_terms_template(
        next(iter(cypher_query_module.entity_param_bindings(["NCBIGene:672"])))
    )
    async def _call_tier(tier: str, messages: Any, **kwargs: Any) -> Any:
        # The model path's control: the same one-hop GO traversal written
        # by a "model", which carries no attribution parameter.
        return SimpleNamespace(
            content=(
                f"MATCH (a:Gene {{id: ${template.go_attribution_param}}})-[:participates_in]->"
                "(x:BiologicalProcess) RETURN x ORDER BY x.id"
            )
        )

    harness = SimpleNamespace(
        trace_id="t-go", get_query_cost_usd=lambda *a, **k: 0.0, call_tier=_call_tier
    )
    output = await cypher_query(harness, tool_input, template=template)
    assert output.status == "ok", output
    assert output.template == "gene_go_processes_one"
    assert seen["params"] == {template.go_attribution_param: "NCBIGene:672"}
    [row] = output.rows
    assert row.curie == "GO:0006281"
    assert row.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row.fields[cypher_provenance.CITED_VIA_GENE_FIELD] == "NCBIGene:672"
    # Without the forced template the same vertex stays uncited (F-01).
    plain = await cypher_query(harness, tool_input)
    assert plain.status in ("empty", "error"), plain


def test_two_bound_genes_never_produce_a_go_template() -> None:
    bindings = cypher_query_module.entity_param_bindings(["NCBIGene:672", "NCBIGene:7157"])
    assert len(bindings) == 2
    assert graph_module._first_gene_curie(["NCBIGene:672", "NCBIGene:7157"]) == "NCBIGene:672"
    go_call = graph_module._build_planned_go_terms_call("NCBIGene:672", "single_hop")
    assert go_call.cypher_input.target_entities == ["NCBIGene:672"], (
        "the template binds exactly one gene, so N-04 stays dormant"
    )


# ---------------------------------------------------------------------------
# L-01 shape 2: a collected list is emitted in CURIE order.
# ---------------------------------------------------------------------------


def _medgen_vertex(n: int, internal: int) -> dict[str, Any]:
    return {
        "id": internal, "label": "Disease",
        "properties": {"id": f"MedGen:C{n}", "name": f"disease {n}"},
    }


def test_a_collected_list_column_is_emitted_in_curie_order_whatever_the_aggregate_order() -> None:
    forward = {"c0": [_medgen_vertex(1, 10), _medgen_vertex(2, 11), _medgen_vertex(3, 12)]}
    reverse = {"c0": [_medgen_vertex(3, 12), _medgen_vertex(2, 11), _medgen_vertex(1, 10)]}
    rows_forward = [r["curie"] for r in cypher_provenance.to_output_rows(forward, "v")]
    rows_reverse = [r["curie"] for r in cypher_provenance.to_output_rows(reverse, "v")]
    assert rows_forward == ["MedGen:C1", "MedGen:C2", "MedGen:C3"], rows_forward
    assert rows_reverse == rows_forward, rows_reverse


def test_the_fold_curies_are_in_curie_order_whatever_the_aggregate_order() -> None:
    cypher = "MATCH (v:SequenceVariant)-[:has_phenotype]->(x:Disease) WITH v, collect(DISTINCT x) AS xs RETURN v, xs ORDER BY v.id LIMIT 100"
    variant = {"id": 1, "label": "SequenceVariant", "properties": {"id": "ClinVar:1"}}
    raw = {"c0": variant, "c1": [_medgen_vertex(3, 12), _medgen_vertex(1, 10), _medgen_vertex(2, 11)]}
    anchor, curies = cypher_query_module._fold_curies(raw, cypher, ("v", "xs", "clinvar_condition_ids"))
    assert anchor == "ClinVar:1"
    assert curies == ["MedGen:C1", "MedGen:C2", "MedGen:C3"], curies


# ---------------------------------------------------------------------------
# The Layer 2 citation on a multi-record output.
# ---------------------------------------------------------------------------


def test_a_layer2_claim_on_the_second_record_cites_the_second_record() -> None:
    from system_03_search_agent.harness.coordinator_worker import Finding

    records = [
        NcbiEfetchRecord(
            id=uid, db="clinvar", fields={"title": f"variant {uid}"},
            source_url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
        )
        for uid in ("11", "12")
    ]
    output = NcbiEfetchOutput(
        status="ok", action="summary", records=records, record_count=2,
        total_available=2, truncated=False,
    )
    finding = Finding(
        call_id="ne-1", tool="ncbi_efetch", layer="layer_2_api", source="structured_pass_through",
        structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(output),
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )
    synth = SynthFinding(
        ref_index=1, citation_id="ne-1-1", layer="layer_2_api", tool="ncbi_efetch",
        field="title", field_value="variant 12",
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/12/",
        entity_type="clinvar", curie="", call_id="ne-1",
    )
    citation = graph_module._layer2_citation_for_synth_finding(
        synth, [finding], {"ne-1": output}, "ne-1-1", 1, "variant 12 [1]"
    )
    assert citation is not None
    assert citation.source_url == "https://www.ncbi.nlm.nih.gov/clinvar/variation/12/"
    assert citation.source_id == "12", citation


# ---------------------------------------------------------------------------
# The allotment.
# ---------------------------------------------------------------------------


def _finding(call_id: str, tool: str, layer: str, n: int, prefix: str) -> Any:
    from system_03_search_agent.harness.coordinator_worker import Finding

    rows = [
        {
            "curie": f"{prefix}:{i}", "node_or_edge_type": prefix,
            "fields": {"name": f"{prefix} {i}"},
            "source_url": f"https://www.ncbi.nlm.nih.gov/{prefix.lower()}/{call_id}-{i}",
        }
        for i in range(n)
    ]
    return Finding(
        call_id=call_id, tool=tool, layer=layer, source="structured_pass_through",
        structured_fields={"status": "ok", "row_count": n, "rows": rows},
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )


def test_the_lead_quota_admits_the_answer_first_then_one_row_per_context_call_per_round() -> None:
    findings = [
        _finding("ne-1", "ncbi_efetch", "layer_2_api", 1, "Gene"),
        _finding("ne-2", "ncbi_efetch", "layer_2_api", 10, "Clinvar"),
        _finding("ne-3", "ncbi_efetch", "layer_2_api", 5, "Pubmed"),
        _finding("pa-1", "pubtator_annotate", "layer_3_enrichment", 5, "Entity"),
        _finding("ct-1", "clinicaltrials_search", "layer_3_enrichment", 5, "Trial"),
        _finding("cq-1", "cypher_query", "layer_1_graph", 30, "Disease"),
    ]
    plain, _ = build_synth_findings(
        findings, graph_module._pick_representative_field, max_findings=20,
        lead_call_ids=frozenset({"cq-1"}),
    )
    # Populate-check: without the quota the graph answer is crowded out.
    assert sum(1 for f in plain if f.call_id == "cq-1") == 0
    led, capped = build_synth_findings(
        findings, graph_module._pick_representative_field, max_findings=20,
        lead_call_ids=frozenset({"cq-1"}), lead_quota=10,
    )
    assert capped
    assert len(led) == 20
    assert [f.call_id for f in led][:11] == ["cq-1"] * 11
    context = [f.call_id for f in led][11:]
    # Ten slots over five context calls plus the lead's leftover rows as
    # the last queue: two rounds, one row each per queue, in handoff
    # order, except the single-row gene record in round two. The lead
    # rows are numbered first by the presentation sort, so the leftover
    # lead row sits at the end of the lead block.
    assert context == ["ne-1", "ne-2", "ne-3", "pa-1", "ct-1", "ne-2", "ne-3", "pa-1", "ct-1"], context
    assert sum(1 for f in led if f.call_id == "cq-1") == 11
    assert [f.ref_index for f in led] == list(range(1, 21))
    # Deterministic: the same call twice is the same list.
    again, _ = build_synth_findings(
        findings, graph_module._pick_representative_field, max_findings=20,
        lead_call_ids=frozenset({"cq-1"}), lead_quota=10,
    )
    assert [f.source_url for f in again] == [f.source_url for f in led]


def test_without_a_lead_quota_admission_is_unchanged() -> None:
    findings = [
        _finding("ct-1", "clinicaltrials_search", "layer_3_enrichment", 2, "Trial"),
        _finding("cq-1", "cypher_query", "layer_1_graph", 3, "Disease"),
    ]
    plain, _ = build_synth_findings(findings, graph_module._pick_representative_field, max_findings=3)
    assert [f.entity_type for f in plain] == ["Trial", "Trial", "Disease"]


# ---------------------------------------------------------------------------
# Citation identity on the new rows (found live, 2026-09-20).
# ---------------------------------------------------------------------------


def test_a_go_citation_carries_the_go_curie_even_when_a_layer3_row_shares_its_url() -> None:
    """Live: three GO rows in the BRCA1 answer were cited with `source_id`
    `unknown` and `source` `cypher_query`. `_curie_for_citation` looked the
    row up by URL alone, and the PubTator3 entity row (Layer 3, empty CURIE,
    the same gene page URL) came first in the handoff order."""
    from system_03_search_agent.harness.coordinator_worker import Finding

    gene_url = "https://www.ncbi.nlm.nih.gov/gene/672"
    pubtator_row = {
        "curie": "", "node_or_edge_type": "Literature entity",
        "fields": {"name": "BRCA1"}, "source_url": gene_url,
    }
    go_row = {
        "curie": "GO:0006281", "node_or_edge_type": "BiologicalProcess",
        "fields": {"name": "DNA repair", cypher_provenance.CITED_VIA_GENE_FIELD: "NCBIGene:672"},
        "source_url": gene_url, "graph_snapshot_version": "v-2026",
    }
    findings = [
        Finding(
            call_id="pa-1", tool="pubtator_annotate", layer="layer_3_enrichment",
            source="structured_pass_through",
            structured_fields={"status": "ok", "row_count": 1, "rows": [pubtator_row]},
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        ),
        Finding(
            call_id="cq-go", tool="cypher_query", layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={"status": "ok", "row_count": 1, "rows": [go_row]},
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        ),
    ]
    synth = SynthFinding(
        ref_index=1, citation_id="cq-go-1", layer="layer_1_graph", tool="cypher_query",
        field="name", field_value="DNA repair", source_url=gene_url,
        entity_type="BiologicalProcess", curie="GO:0006281", call_id="cq-go",
    )
    # Populate-check: the Layer 3 row really does share the URL and comes first.
    assert findings[0].structured_fields["rows"][0]["source_url"] == gene_url
    assert graph_module._curie_for_citation("cq-go-1", findings, synth) == "GO:0006281"
    assert graph_module._graph_snapshot_version_for_citation("cq-go-1", findings, synth) == "v-2026"
    assert graph_module._entity_name_for_citation("cq-go-1", findings, synth) == "DNA repair"


def test_a_pubtator_publication_citation_carries_its_pmid_as_source_id() -> None:
    """Live: a PubTator3 publication row was cited with `source_id`
    `unknown`; the Layer 3 identity chain knew `nct_id`, `pubtator_id` and
    `rsid` but not a publication's `pmid`."""
    from system_03_search_agent.harness.coordinator_worker import Finding

    url = "https://pubmed.ncbi.nlm.nih.gov/42639261/"
    row = {
        "curie": "", "node_or_edge_type": "Publication",
        "fields": {"pmid": "42639261", "annotation_count": 3}, "source_url": url,
    }
    finding = Finding(
        call_id="pa-2", tool="pubtator_annotate", layer="layer_3_enrichment",
        source="structured_pass_through",
        structured_fields={"status": "ok", "row_count": 1, "rows": [row]},
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )
    output = PubtatorAnnotateOutput(
        status="ok", mode="annotate_publications",
        publications=[PubtatorPublication(pmid="42639261", total_annotations=3, source_url=url)],
    )
    synth = SynthFinding(
        ref_index=1, citation_id="pa-2-1", layer="layer_3_enrichment", tool="pubtator_annotate",
        field="pmid", field_value="42639261", source_url=url, entity_type="Publication",
        curie="", call_id="pa-2",
    )
    citation = graph_module._layer3_citation_for_synth_finding(
        synth, [finding], {"pa-2": output}, "pa-2-1", 1, "paper 42639261 [1]"
    )
    assert citation is not None
    assert citation.source_id == "42639261", citation
    assert citation.source_url == url
# ---------------------------------------------------------------------------
# OMIM (item 2b, 2026-09-22): never a record for a different gene.
# ---------------------------------------------------------------------------


def _gck_omim_titles() -> dict[str, str]:
    """What OMIM answers for `GCK`: the right entry and the wrong one OMIM's
    own search actually ranks first for that symbol."""
    return dict([_OMIM_GCK, _OMIM_MAP4K2])


def _omim_summary_output() -> NcbiEfetchOutput:
    """One real-shaped OMIM ESummary result holding both entries."""
    records = [
        NcbiEfetchRecord(
            id=uid, db="omim",
            fields={"oid": f"OMIM:{uid}", "title": title, "alttitles": "", "locus": "7p13"},
            source_url=_omim_url(uid),
        )
        for uid, title in (_OMIM_GCK, _OMIM_MAP4K2)
    ]
    return NcbiEfetchOutput(
        status="ok", action="summary", records=records, record_count=len(records),
        total_available=len(records), truncated=False,
    )


@pytest.mark.asyncio
async def test_an_omim_record_for_another_gene_never_reaches_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question about GCK shows OMIM's GCK entry and never OMIM's MAP4K2
    entry, which is the record OMIM's own search returns first for that
    symbol. Run through the real loop, so the drop is proven where it has
    to hold: in what the person asking actually gets back.
    """
    spy_model = _ModelSpy(monkeypatch, entity="GCK")
    _install_lookup(monkeypatch)
    _ToolSpy(monkeypatch, omim_titles=_gck_omim_titles())
    events = await _events(_GCK_QUESTION)
    sources = _sources(events)
    # Populate-check: OMIM was reached at all, so the absence below is a
    # drop rather than a call that never happened.
    assert _omim_url(_OMIM_GCK[0]) in sources, sources
    assert _omim_url(_OMIM_MAP4K2[0]) not in sources, sources
    # And it never reached the model either, so no sentence could be built
    # from it even uncited.
    prompt = "\n".join(spy_model.synth_prompts)
    assert "GLUCOKINASE" in prompt, prompt[:2000]
    assert "MAP4K2" not in prompt, prompt[:2000]
    assert _omim_url(_OMIM_MAP4K2[0]) not in prompt, prompt[:2000]


def test_the_act_shaping_step_drops_the_wrong_gene_and_keeps_the_right_one() -> None:
    """The same drop at the step that performs it, so a future change to
    the loop cannot hide which line is doing the work."""
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(
        _omim_summary_output(), "omim_summary", "GCK"
    )
    urls = [row["source_url"] for row in shaped["rows"]]
    assert urls == [_omim_url(_OMIM_GCK[0])], shaped
    assert shaped["row_count"] == 1, shaped
    # The kept row carries the entry title, which is what a reader sees.
    assert shaped["rows"][0]["fields"]["title"] == _OMIM_GCK[1], shaped
    # `oid` is withheld, like every other row-identity field.
    assert "oid" not in shaped["rows"][0]["fields"], shaped


def test_no_resolved_symbol_keeps_no_omim_record_at_all() -> None:
    """With nothing to check a title against, no OMIM title can be stood
    behind, so nothing survives. The populate-check is the same output
    shaped WITH a symbol, which does produce a row."""
    output = _omim_summary_output()
    with_symbol = graph_module._ncbi_efetch_output_to_structured_fields(
        output, "omim_summary", "GCK"
    )
    assert with_symbol["row_count"] == 1, with_symbol
    for missing in (None, "", "   "):
        shaped = graph_module._ncbi_efetch_output_to_structured_fields(
            output, "omim_summary", missing
        )
        assert shaped["rows"] == [], (missing, shaped)
        assert shaped["row_count"] == 0, (missing, shaped)


@pytest.mark.asyncio
async def test_the_omim_follow_up_is_planned_and_its_citations_pass_the_host_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gene question plans the OMIM search and the OMIM summary behind it,
    and the citations the surviving records produce are real `omim.org`
    citations that satisfy the citation contract's own host-pinned
    pattern, which is the control that decides whether a source can be
    cited at all."""
    import re

    from system_03_search_agent.contracts.events import NCBI_SOURCE_URL_PATTERN

    _ModelSpy(monkeypatch, entity="GCK")
    _install_lookup(monkeypatch)
    spy = _ToolSpy(monkeypatch, omim_titles=_gck_omim_titles())
    events = await _events(_GCK_QUESTION)
    searches = [i for i in spy.efetch_inputs if i["action"] == "search"]
    assert [i["db"] for i in searches].count("omim") == 1, searches
    assert next(i for i in searches if i["db"] == "omim")["term"] == "GCK", searches
    assert [i["db"] for i in spy.efetch_inputs if i["action"] == "summary"].count("omim") == 1
    omim_citations = [
        e.payload for e in events if e.type == "citation" and "omim.org" in e.payload["source_url"]
    ]
    assert len(omim_citations) == 1, [e.payload for e in events if e.type == "citation"]
    payload = omim_citations[0]
    assert payload["source_url"] == _omim_url(_OMIM_GCK[0]), payload
    assert re.match(NCBI_SOURCE_URL_PATTERN, payload["source_url"]), payload
    assert payload["layer"] == "layer_2_api", payload


@pytest.mark.asyncio
async def test_bypassing_filter_omim_titles_lets_the_wrong_gene_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION ARM. Replace `filter_omim_titles` with the identity
    function and the MAP4K2 record DOES reach the answer for a GCK
    question.

    Without this, the arm above could pass for a reason that has nothing to
    do with the filter: a record with no URL, a cap of one, a sort that
    happens to drop the second record. This proves the filter is on the
    path and is the thing doing the dropping, so deleting the call makes a
    test go red rather than quietly restoring the defect.
    """
    monkeypatch.setattr(
        graph_module.breadth_plan,
        "filter_omim_titles",
        lambda records, gene_symbol: list(records),
    )
    _ModelSpy(monkeypatch, entity="GCK")
    _install_lookup(monkeypatch)
    _ToolSpy(monkeypatch, omim_titles=_gck_omim_titles())
    events = await _events(_GCK_QUESTION)
    sources = _sources(events)
    assert _omim_url(_OMIM_MAP4K2[0]) in sources, sources
