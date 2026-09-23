"""Fix-plan item 12.1 (2026-09-23): a disease question searches every layer.

What this file grades, offline, with every tool and the model replaced by
fakes whose bytes the test controls:

    THE DEFECT. A question anchored on a disease with no gene resolved
    planned ONE call, its graph lookup, and refused when the graph did not
    hold that Disease vertex. Measured: `Any trials for GERD?` resolved
    `MedGen:C5563728` at confidence 1.0, ran `MATCH (a:Disease {id:
    $e_MedGen_C5563728}) RETURN a`, got zero rows and refused, while
    ClinicalTrials.gov holds thousands of GERD trials and
    `clinicaltrials_search` was built, tested and never called. The pair
    of synonyms is the proof it was one point of failure rather than a
    ranking problem: `reflux disease` resolves to eight concepts the graph
    DOES hold, so the identical call answered.

    THE STABLE TEXT. The disease text three different calls search on is
    the MedGen record's own preferred name, read live from the resolved
    CURIE, never the user's phrasing and never a model-extracted span.
    That is what lets item 11.21's rule stand: the same question shows the
    same number and set of sources every run.

    THE GENE PATH IS UNTOUCHED. A question that resolves a gene plans
    byte-identical calls whether or not a disease title is also offered.

    THE MEDGEN RECORD. NCBI returns `definition` and `semantictype` as
    one-key wrapper objects. The definition is unwrapped to the string it
    holds, so `grounding.ground_claim` can match a clause against it, and
    an empty one is dropped rather than shown as `{}`.

Every arm that asserts a value is absent is paired with a populate check
that proves the same code path produces it when it should, so an arm
cannot pass because nothing ran.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import breadth_plan
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run import run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    ClinicalTrialsSearchOutput,
    ClinicalTrialsStudy,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput
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

# The measured case, verbatim. `C5563728` is the concept `GERD` resolves
# to, and `Gastroesophageal reflux (GERD)` is the preferred name MedGen
# returned on three separate live runs on 2026-09-23.
_TRIALS_QUESTION = "Any trials for GERD?"
_BARE_QUESTION = "GERD"
_GERD_CURIE = "MedGen:C5563728"
_GERD_TITLE = "Gastroesophageal reflux (GERD)"
_GERD_TEXT = "gastroesophageal reflux"
_GERD_UID = "1795938"
_GERD_URL = f"https://www.ncbi.nlm.nih.gov/medgen/{_GERD_UID}"
_TRIAL_URL = "https://clinicaltrials.gov/study/NCT00141960"
_PMID = "29132520"
_PMID_URL = f"https://pubmed.ncbi.nlm.nih.gov/{_PMID}/"
_DEFINITION = (
    "Gastroesophageal reflux is characterized by the retrograde movement of "
    "stomach contents into the esophagus."
)


# ---------------------------------------------------------------------------
# breadth_plan: the stable text and the MedGen record planners.
# ---------------------------------------------------------------------------


def test_a_parenthesised_gloss_is_dropped_whole_not_unbracketed() -> None:
    """The measured reason this exists: deleting only the brackets leaves
    `gastroesophageal reflux gerd`, which is not a phrase any paper or
    trial record contains, so the search that was supposed to be fixed
    would have found nothing and looked fixed."""
    assert breadth_plan.disease_search_text(_GERD_TITLE) == _GERD_TEXT
    # Populate check: the same function keeps a title that has no gloss,
    # so the arm above cannot pass by returning nothing at all.
    assert breadth_plan.disease_search_text("Alzheimer disease") == "alzheimer disease"
    # An unbalanced bracket is still removed as a character, so nothing
    # that carries meaning in a PubMed term survives either path.
    assert breadth_plan.disease_search_text("cancer (of the lung") == "cancer of the lung"
    assert breadth_plan.disease_search_text("(GERD)") is None
    assert breadth_plan.disease_search_text(None) is None


def test_the_pubmed_term_for_a_disease_is_the_cleaned_title_quoted() -> None:
    assert (
        breadth_plan.build_pubmed_term(None, _GERD_TITLE)
        == f'"{_GERD_TEXT}"[Title/Abstract]'
    )


def test_the_first_stage_for_a_disease_is_the_pubmed_search_alone() -> None:
    """ClinVar, OMIM and GEO stay gene-only: each term is a gene field or a
    bare symbol, and there is no disease equivalent returning that record."""
    calls = breadth_plan.plan_first_stage(None, _GERD_TITLE)
    assert [c.purpose for c in calls] == ["pubmed_search"], calls
    # Populate check: the same function plans all four for a symbol, so
    # the one-item list above is a property of the disease path.
    gene = breadth_plan.plan_first_stage("BRCA1", None, datasets=True)
    assert [c.purpose for c in gene] == [
        "pubmed_search", "clinvar_search", "omim_search", "gds_search",
    ], gene


@pytest.mark.parametrize(
    "curie",
    ["MedGen:C5563728", "MedGen:CN123", " MedGen:c5563728 "],
)
def test_the_medgen_term_is_built_from_a_concept_curie(curie: str) -> None:
    term = breadth_plan.build_medgen_term(curie)
    assert term is not None and term.endswith("[ConceptId]"), term
    assert term.split("[")[0].isalnum()


@pytest.mark.parametrize(
    "curie",
    ["NCBIGene:672", "C5563728", "MedGen:", "MedGen:not-an-id", "MeSH:D005764", "", None, 672],
)
def test_anything_that_is_not_a_medgen_curie_plans_no_record_call(curie: Any) -> None:
    assert breadth_plan.build_medgen_term(curie) is None
    assert breadth_plan.plan_disease_search(curie) == ()


def test_the_disease_record_search_is_one_medgen_esearch_on_the_concept_id() -> None:
    (call,) = breadth_plan.plan_disease_search(_GERD_CURIE)
    assert call.tool == "ncbi_efetch" and call.layer == "layer_2_api"
    assert call.purpose == "medgen_search"
    payload = call.tool_input.root.model_dump()
    assert payload["action"] == "search" and payload["db"] == "medgen"
    assert payload["term"] == "C5563728[ConceptId]"
    assert payload["retmax"] == breadth_plan.MEDGEN_RESULT_CAP


def test_the_medgen_follow_up_sorts_dedupes_and_caps_its_uids() -> None:
    (call,) = breadth_plan.plan_medgen_follow_up(["11", 13, "12", "12", "nope", "0"])
    payload = call.tool_input.root.model_dump()
    assert call.purpose == "medgen_summary"
    assert payload["action"] == "summary" and payload["db"] == "medgen"
    assert payload["ids"] == ["13", "12", "11"], payload
    assert breadth_plan.plan_medgen_follow_up([]) == ()
    assert breadth_plan.plan_medgen_follow_up(["nope"]) == ()


# ---------------------------------------------------------------------------
# graph.py: picking the disease, and reading its name.
# ---------------------------------------------------------------------------


def test_the_first_medgen_curie_is_the_disease_the_question_is_about() -> None:
    assert graph_module._first_disease_curie(["NCBIGene:672", _GERD_CURIE]) == _GERD_CURIE
    assert graph_module._first_disease_curie([_GERD_CURIE, "MedGen:C0017168"]) == _GERD_CURIE
    assert graph_module._first_disease_curie(["NCBIGene:672"]) is None
    assert graph_module._first_disease_curie([]) is None


@pytest.mark.asyncio
async def test_the_disease_text_is_the_medgen_name_and_never_the_users_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole answer to 'where does a stable disease text come from'.
    The resolver is asked for the CURIE and returns the record's name; the
    question's own wording never reaches the search."""
    asked: list[list[str]] = []

    async def _resolve(curies: Any) -> dict[str, str | None]:
        asked.append(list(curies))
        return {_GERD_CURIE: _GERD_TITLE}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    assert await graph_module._disease_search_text(_GERD_CURIE) == _GERD_TEXT
    assert asked == [[_GERD_CURIE]], asked


@pytest.mark.asyncio
async def test_an_unresolvable_disease_plans_what_it_planned_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`resolve_concept_ids` maps an id MedGen does not hold, a transport
    failure and a rate-limit refusal all to None, and never raises. None
    here must degrade to the single graph call, never to a search on a
    name that was not read."""

    async def _resolve(curies: Any) -> dict[str, str | None]:
        return {_GERD_CURIE: None}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    assert await graph_module._disease_search_text(_GERD_CURIE) is None
    assert await graph_module._disease_search_text(None) is None
    assert graph_module._build_breadth_calls(None, disease_title=None, disease_curie=_GERD_CURIE) == []
    assert graph_module._build_layer_tool_calls(_TRIALS_QUESTION, None, [], None) == []


# ---------------------------------------------------------------------------
# graph.py: what a disease question plans.
# ---------------------------------------------------------------------------


def _inputs(calls: list[Any]) -> list[tuple[str, str, str, Any]]:
    """The planned calls without their call_ids, which are fresh uuids per
    run by design and so say nothing about what was planned."""
    shaped: list[tuple[str, str, str, Any]] = []
    for call in calls:
        payload: Any = None
        for attr in ("ncbi_efetch_input", "tool_input", "cypher_input"):
            value = getattr(call, attr, None)
            if value is not None:
                payload = json.dumps(
                    value.model_dump() if hasattr(value, "model_dump") else repr(value),
                    sort_keys=True,
                    default=str,
                )
                break
        shaped.append(
            (
                call.tool_call.tool,
                call.tool_call.layer,
                getattr(call, "purpose", "") or getattr(call, "source_purpose", ""),
                payload,
            )
        )
    return shaped


def test_a_disease_earns_the_literature_index_and_the_trials_registry() -> None:
    calls = graph_module._build_layer_tool_calls(_TRIALS_QUESTION, None, [], _GERD_TEXT)
    assert [c.tool_call.tool for c in calls] == [
        "pubtator_annotate", "clinicaltrials_search",
    ], calls
    lookup, trials = calls
    assert lookup.tool_input.root.query == _GERD_TEXT
    assert trials.tool_input.query_cond == _GERD_TEXT
    # The registry condition is the MedGen name, so two runs of `GERD` and
    # a run of `reflux disease` that resolve the same concept search the
    # same condition.
    assert trials.tool_input.query_cond != "GERD"


def test_a_recruiting_disease_question_still_narrows_to_recruiting() -> None:
    calls = graph_module._build_layer_tool_calls(
        "Any recruiting trials for GERD?", None, [], _GERD_TEXT
    )
    (trials,) = [c for c in calls if c.tool_call.tool == "clinicaltrials_search"]
    assert trials.tool_input.overall_status == "RECRUITING"
    # Populate check: the plain question leaves the status unset, so the
    # arm above is reading the question rather than a constant.
    plain = graph_module._build_layer_tool_calls(_TRIALS_QUESTION, None, [], _GERD_TEXT)
    (plain_trials,) = [c for c in plain if c.tool_call.tool == "clinicaltrials_search"]
    assert plain_trials.tool_input.overall_status is None


def test_a_disease_plans_its_own_record_then_the_literature() -> None:
    calls = graph_module._build_breadth_calls(
        None, disease_title=_GERD_TITLE, disease_curie=_GERD_CURIE
    )
    assert [getattr(c, "purpose", "") for c in calls] == [
        "medgen_search",
        "pubmed_search",
        "pubmed_abstracts",
        "pubtator_publications",
        "medgen_summary",
    ], calls
    (search,) = [c for c in calls if getattr(c, "purpose", "") == "medgen_search"]
    assert search.ncbi_efetch_input.root.term == "C5563728[ConceptId]"
    (follow_up,) = [c for c in calls if getattr(c, "purpose", "") == "medgen_summary"]
    assert follow_up.source_purpose == "medgen_search"
    # ClinVar, OMIM and GEO are gene-only and must not appear.
    purposes = {getattr(c, "purpose", "") for c in calls}
    assert not purposes & {"clinvar_search", "omim_search", "gds_search"}, purposes


def test_a_disease_with_no_resolvable_curie_still_searches_the_literature() -> None:
    """The title and the CURIE are separate inputs on purpose. A title with
    no concept id behind it plans the PubMed leg and simply no record leg,
    rather than planning nothing."""
    calls = graph_module._build_breadth_calls(
        None, disease_title=_GERD_TITLE, disease_curie=None
    )
    assert [getattr(c, "purpose", "") for c in calls] == [
        "pubmed_search", "pubmed_abstracts", "pubtator_publications",
    ], calls


def test_a_gene_question_plans_exactly_what_it_planned_before() -> None:
    """A symbol wins outright. Narrowing a gene question's literature
    search by a disease as well would change every gene question's source
    set, which is a separate decision with its own evidence to gather."""
    before = _inputs(graph_module._build_breadth_calls("BRCA1"))
    after = _inputs(
        graph_module._build_breadth_calls(
            "BRCA1", disease_title=_GERD_TITLE, disease_curie=_GERD_CURIE
        )
    )
    assert before == after, (before, after)
    layer_before = _inputs(graph_module._build_layer_tool_calls(_TRIALS_QUESTION, "BRCA1", []))
    layer_after = _inputs(
        graph_module._build_layer_tool_calls(_TRIALS_QUESTION, "BRCA1", [], _GERD_TEXT)
    )
    assert layer_before == layer_after, (layer_before, layer_after)
    # Populate check: the disease arguments DO change the plan when no gene
    # resolved, so the equality above is a property of the symbol winning
    # rather than of the arguments being ignored everywhere.
    assert _inputs(
        graph_module._build_breadth_calls(
            None, disease_title=_GERD_TITLE, disease_curie=_GERD_CURIE
        )
    ) != before


def test_a_disease_question_stays_far_inside_the_layer_call_ceiling() -> None:
    """Section 21.3 allows 20 Layer 2 and 3 calls per query. A gene question
    spends 14 to 16 of them. This counts what a disease question plans,
    plus the two calls `_disease_search_text` spends reading the name and
    the two Think already spent resolving the mention."""
    planned = graph_module._build_layer_tool_calls(
        _TRIALS_QUESTION, None, [], _GERD_TEXT
    ) + graph_module._build_breadth_calls(
        None, disease_title=_GERD_TITLE, disease_curie=_GERD_CURIE
    )
    layer_2_or_3 = [c for c in planned if c.tool_call.layer != "layer_1_graph"]
    assert len(layer_2_or_3) == 7, _inputs(planned)
    assert len(layer_2_or_3) + 2 + 2 <= 20


# ---------------------------------------------------------------------------
# graph.py: the MedGen record's wrapped fields.
# ---------------------------------------------------------------------------


def test_a_medgen_definition_is_unwrapped_to_the_string_it_holds() -> None:
    unwrapped = graph_module._unwrap_medgen_fields(
        {"title": "Alzheimer disease", "definition": {"value": _DEFINITION}}
    )
    assert unwrapped["definition"] == _DEFINITION
    assert unwrapped["title"] == "Alzheimer disease"


def test_an_empty_medgen_definition_is_dropped_rather_than_shown_as_an_object() -> None:
    unwrapped = graph_module._unwrap_medgen_fields(
        {"title": _GERD_TITLE, "definition": {}, "semantictype": {"value": "Finding"}}
    )
    assert "definition" not in unwrapped, unwrapped
    assert unwrapped["semantictype"] == "Finding"
    # Populate check: the same call keeps a definition that has one, so the
    # absence above is the empty wrapper being dropped rather than the
    # function dropping the field whatever it holds.
    assert graph_module._unwrap_medgen_fields({"definition": {"value": "x"}})["definition"] == "x"


def test_unwrapping_leaves_a_plain_value_alone() -> None:
    fields = {"title": _GERD_TITLE, "definition": _DEFINITION, "semantictype": "Finding"}
    assert graph_module._unwrap_medgen_fields(fields) == fields


def test_a_medgen_summary_row_carries_the_name_and_the_definition() -> None:
    output = NcbiEfetchOutput(
        status="ok",
        action="summary",
        records=[
            NcbiEfetchRecord(
                id=_GERD_UID,
                db="medgen",
                fields={
                    "conceptid": "C5563728",
                    "title": _GERD_TITLE,
                    "definition": {"value": _DEFINITION},
                    "semantictype": {"value": "Finding"},
                },
                source_url=_GERD_URL,
            )
        ],
        record_count=1,
        total_available=1,
        truncated=False,
    )
    shaped = graph_module._ncbi_efetch_output_to_structured_fields(output, "medgen_summary")
    (row,) = shaped["rows"]
    assert row["source_url"] == _GERD_URL
    assert list(row["fields"]) == ["title", "definition", "semantictype"], row["fields"]
    assert row["fields"]["definition"] == _DEFINITION
    # The concept id identifies the record rather than saying anything
    # about it, and the question already resolved it.
    assert "conceptid" not in row["fields"], row["fields"]


# ---------------------------------------------------------------------------
# End to end: the seven-question defect, offline.
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
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)


def _install_model(monkeypatch: pytest.MonkeyPatch, mention: str) -> None:
    from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        joined = "\n".join(m.get("content") or "" for m in (kwargs.get("messages") or []))
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(
                json.dumps(
                    {
                        "query_class": "exploratory",
                        "narrative": "stand-in classification",
                        "entities": [{"text": mention, "entity_type": "disease"}],
                    }
                )
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(kwargs.get("messages") or []))
        return fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


class _DiseaseToolSpy:
    """Every tool faked. The graph answers EMPTY, which is the measured
    defect: the graph holds no Disease vertex for this concept, so if the
    other layers are not searched the run has nothing to cite."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, medgen_uids: list[str] | None = None,
                 pubmed_ids: list[str] | None = None) -> None:
        self.efetch_inputs: list[dict[str, Any]] = []
        self.trials_inputs: list[dict[str, Any]] = []
        self.pubtator_inputs: list[dict[str, Any]] = []
        self.medgen_uids = [_GERD_UID] if medgen_uids is None else medgen_uids
        self.pubmed_ids = [_PMID] if pubmed_ids is None else pubmed_ids

        async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
            return CypherQueryOutput(
                status="empty", row_count=0, total_available=0, truncated=False,
                rows=[], error=None, template=None,
            )

        async def _efetch(tool_input: Any, **kwargs: Any) -> NcbiEfetchOutput:
            root = tool_input.root
            self.efetch_inputs.append(root.model_dump())
            if root.action == "search":
                ids = self.medgen_uids if root.db == "medgen" else self.pubmed_ids
                return NcbiEfetchOutput(
                    status="ok", action="search",
                    records=[
                        NcbiEfetchRecord(
                            db=root.db,
                            fields={"idlist": list(ids), "idlist_count": len(ids)},
                        )
                    ],
                    record_count=1, total_available=len(ids), truncated=False,
                )
            if root.action == "summary" and root.db == "medgen":
                records = [
                    NcbiEfetchRecord(
                        id=uid, db="medgen",
                        fields={
                            "conceptid": "C5563728",
                            "title": _GERD_TITLE,
                            "definition": {"value": _DEFINITION},
                            "semantictype": {"value": "Finding"},
                        },
                        source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{uid}",
                    )
                    for uid in root.ids
                ]
                return NcbiEfetchOutput(
                    status="ok", action="summary", records=records,
                    record_count=len(records), total_available=len(records), truncated=False,
                )
            if root.action == "fetch":
                records = [
                    NcbiEfetchRecord(
                        id=pmid, db="pubmed",
                        fields={"title": f"Gastroesophageal reflux disease {pmid}",
                                "abstract": _DEFINITION},
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
            self.trials_inputs.append(tool_input.model_dump())
            return ClinicalTrialsSearchOutput(
                status="ok",
                studies=[
                    ClinicalTrialsStudy(
                        nct_id="NCT00141960",
                        brief_title="A study of reflux therapy",
                        overall_status="COMPLETED",
                        conditions=["Gastroesophageal Reflux"],
                        source_url=_TRIAL_URL,
                    )
                ],
                study_count=1,
                total_count=1,
            )

        monkeypatch.setattr(graph_module, "cypher_query", _cypher)
        monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
        monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)
        monkeypatch.setattr(graph_module, "clinicaltrials_search", _trials)


def _install_disease_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mention(mention: str) -> tuple[list[str], int]:
        return [_GERD_CURIE], 1

    async def _concepts(curies: Any) -> dict[str, str | None]:
        return {curie: _GERD_TITLE for curie in curies}

    monkeypatch.setattr(graph_module, "resolve_disease_mention_to_curies", _mention)
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _concepts)


async def _events(text: str, session_id: str = "d-1") -> list[Any]:
    query = Query(
        text=text, session_id=session_id, trace_id=f"trace-{session_id}",
        user_id=None, audience_depth="researcher",
    )
    context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)
    return [event async for event in run_streaming(query, context)]


def _plan_tools(events: list[Any]) -> list[tuple[str, str]]:
    plan = next(e for e in events if e.type == "plan")
    return [(c["tool"], c["layer"]) for c in plan.payload["tool_calls"]]


def _sources(events: list[Any]) -> set[str]:
    return {e.payload["source_url"] for e in events if e.type == "citation"}


@pytest.mark.asyncio
async def test_a_trials_question_about_a_disease_returns_cited_trials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch, "GERD")
    _install_disease_resolution(monkeypatch)
    spy = _DiseaseToolSpy(monkeypatch)
    events = await _events(_TRIALS_QUESTION)

    tools = _plan_tools(events)
    assert ("clinicaltrials_search", "layer_3_enrichment") in tools, tools
    assert tools.count(("ncbi_efetch", "layer_2_api")) == 4, tools

    assert [i["query_cond"] for i in spy.trials_inputs] == [_GERD_TEXT], spy.trials_inputs
    sources = _sources(events)
    assert _TRIAL_URL in sources, sources
    assert _GERD_URL in sources, sources
    assert _PMID_URL in sources, sources

    # The graph found nothing, and the run answered anyway. Before this
    # fix that same empty graph result was the whole search.
    graph_results = [
        e.payload for e in events
        if e.type == "tool_result" and e.payload["tool"] == "cypher_query"
    ]
    assert [r["status"] for r in graph_results] == ["empty"], graph_results
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] != "refuse", done.payload


@pytest.mark.asyncio
async def test_the_bare_disease_name_answers_rather_than_refusing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_model(monkeypatch, "GERD")
    _install_disease_resolution(monkeypatch)
    _DiseaseToolSpy(monkeypatch)
    events = await _events(_BARE_QUESTION, session_id="d-bare")
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] != "refuse", done.payload
    assert _GERD_URL in _sources(events), _sources(events)


@pytest.mark.asyncio
async def test_three_runs_of_one_disease_question_plan_and_cite_the_same_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 11.21's rule: the same question must always show the same
    number and set of sources. The fake returns its ids in a DIFFERENT
    ORDER on each run, so an arm that passed only because the inputs never
    moved would fail here."""
    _install_model(monkeypatch, "GERD")
    _install_disease_resolution(monkeypatch)
    orders = [["1795938"], ["1795938"], ["1795938"]]
    pmid_orders = [
        ["29132520", "33351044"],
        ["33351044", "29132520"],
        ["29132520", "33351044"],
    ]
    plans: list[list[tuple[str, str]]] = []
    citations: list[set[str]] = []
    for index, (uids, pmids) in enumerate(zip(orders, pmid_orders, strict=True)):
        _DiseaseToolSpy(monkeypatch, medgen_uids=uids, pubmed_ids=pmids)
        events = await _events(_TRIALS_QUESTION, session_id=f"d-run{index}")
        plans.append(_plan_tools(events))
        citations.append(_sources(events))
    assert plans[0] == plans[1] == plans[2], plans
    assert citations[0] == citations[1] == citations[2], citations
    # Populate check: the runs actually cited something, so identical
    # empty sets cannot pass this.
    assert _TRIAL_URL in citations[0] and _GERD_URL in citations[0], citations[0]


@pytest.mark.asyncio
async def test_two_names_for_one_condition_search_the_same_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The measured pair. `GERD` refused and `reflux disease` answered,
    because the graph happened to hold one concept and not the other and
    nothing else was searched. Both now search the MedGen name, so what
    the registry is asked is the same string for both."""
    conditions: list[str] = []
    for index, mention in enumerate(("GERD", "reflux disease")):
        _install_model(monkeypatch, mention)
        _install_disease_resolution(monkeypatch)
        spy = _DiseaseToolSpy(monkeypatch)
        await _events(f"Any trials for {mention}?", session_id=f"d-pair{index}")
        conditions.extend(i["query_cond"] for i in spy.trials_inputs)
    assert conditions == [_GERD_TEXT, _GERD_TEXT], conditions
