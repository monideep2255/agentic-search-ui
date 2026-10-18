"""Card 56 (2026-10-05): an organism named in a question is the person's
subject, never a source of gene or disease guesses.

Drives the real `think_node` with only the Plan-tier model, NCBI's `search`
and `summary` actions and the gene resolver faked. No network.

Measured live before this file (testing/Developer/reports/2026-10-05_card56/
diagnosis.md): on 3 of 3 runs of a SARS-CoV-2 SRA question the token
fallback cut "SARS" out of "SARS-CoV-2", MedGen matched it to three disease
records, and the answer was about the disease SARS; a Mycobacterium
tuberculosis question was asked "which gene, variant or condition do you
mean?".

Each arm was run against the old code and went red there:

- `test_a_token_inside_an_organism_span_is_never_a_candidate`: the old
  `_gene_shaped_fallback_candidates` takes no organism spans (red).
- `test_an_organism_name_is_never_bound_as_a_disease`: on the old code the
  disease fallback sends "SARS[title]" to MedGen and binds three records
  (red).
- `test_an_organism_question_asks_which_kind_of_record`: on the old code
  the question asked back is `CLARIFICATION_QUESTION`, the gene question
  (red).

- `test_an_organism_span_resolves_to_its_taxonomy_record_with_a_citation`
  and the arms after it: the old code has no organism resolver, no
  `record_type`, and no organism route in Plan (red).

Populate checks, so no arm passes on an empty result: the same question
with no organism span still yields "SARS"; a span Taxonomy rejects
("MODY", the 2-of-20 GCK runs) still yields its token; a question with no
organism still gets the gene question; a name Taxonomy files under two taxa,
or two organisms, resolves nothing; a gene question with the same record
type and organism plans the graph call first, exactly as before.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions

SRA_QUESTION = "List SRA runs of SARS-CoV-2 from hospital samples and say why each one matched."
ASSEMBLY_QUESTION = "Which Mycobacterium tuberculosis genome assemblies exist, and how do I get them?"
REFERRING_GENE_QUESTION = "What diseases is it linked to?"

#: NCBI Taxonomy, as recorded live in the diagnosis's `raw/ncbi_lookups.json`.
TAXONOMY = {
    "sars-cov-2": ["2697049"],
    "mycobacterium tuberculosis": ["1773"],
    "human": ["9606"],
    "mouse": ["10090", "10088"],
}
#: MedGen, the three records "SARS" bound live on 2026-10-05.
SARS_UIDS = ["1001", "1002", "1003"]
MEDGEN_TITLES = {
    "1001": ("C1519126", "SARS Coronavirus Protease Pathway"),
    "1002": ("C4302012", "Probable SARS"),
    "1003": ("C4302019", "SARS (severe acute respiratory syndrome) confirmed"),
}


class _Record:
    def __init__(self, fields: dict[str, Any]) -> None:
        self.fields = fields


def _install_ncbi(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Fake ESearch and ESummary; returns every (db, term) searched."""
    searched: list[tuple[str, str]] = []

    async def _search(params: Any) -> Any:
        searched.append((params.db, params.term))
        if params.db == "taxonomy":
            ids = TAXONOMY.get(params.term.split("[")[0].strip().casefold(), [])
        elif params.db == "medgen":
            ids = SARS_UIDS if params.term == "SARS[title]" else []
        else:
            ids = []
        return SimpleNamespace(
            status="ok" if ids else "empty",
            records=[_Record({"idlist": ids})] if ids else [],
        )

    async def _summary(params: Any) -> Any:
        return SimpleNamespace(
            status="ok",
            records=[
                _Record({"conceptid": MEDGEN_TITLES[uid][0], "title": MEDGEN_TITLES[uid][1]})
                for uid in params.ids
                if uid in MEDGEN_TITLES
            ],
        )

    async def _no_gene(symbol: str, *, taxon: str = "human") -> str | None:
        return None

    monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", _summary)
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    graph_module._DISEASE_CURIE_CACHE.clear()
    graph_module._ORGANISM_KNOWN_CACHE.clear()
    return searched


def _install_model(
    monkeypatch: pytest.MonkeyPatch, entities: list[tuple[str, str]], **fields: Any
) -> None:
    classification = graph_module._ThinkClassification(
        query_class="exploratory",
        entities=[graph_module._ThinkExtractedEntity(text=t, entity_type=k) for t, k in entities],
        narrative="Asks for records about an organism.",
        **fields,
    )

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(content=classification.model_dump_json())

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")


def _state(text: str, **extra: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "query": Query(text=text, session_id="s-org", trace_id="t-org", user_id=None),
        "harness": harness_module.Harness(trace_id="t-org"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }
    state.update(extra)
    return state


# ---------------------------------------------------------------------------
# The fallback never cuts a token out of an organism's name
# ---------------------------------------------------------------------------


def test_a_token_inside_an_organism_span_is_never_a_candidate() -> None:
    with_span = graph_module._gene_shaped_fallback_candidates(SRA_QUESTION, [], ["SARS-CoV-2"])
    assert "SARS" not in with_span, with_span
    # Populate check: the same question with no organism span still yields it.
    without = graph_module._gene_shaped_fallback_candidates(SRA_QUESTION, [])
    assert "SARS" in without, without
    # Matched whatever case the model wrote the span in.
    assert "SARS" not in graph_module._gene_shaped_fallback_candidates(
        SRA_QUESTION, [], ["sars-cov-2"]
    )


@pytest.mark.asyncio
async def test_a_span_taxonomy_rejects_keeps_its_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model tagged "MODY" as an organism on 2 of 20 GCK runs; Taxonomy
    has no such name, so it is not an organism and its token stays a
    candidate for the disease fallback, exactly as before."""
    _install_ncbi(monkeypatch)
    spans = await graph_module._organism_spans_not_rejected(
        [
            graph_module._ThinkExtractedEntity(text="MODY", entity_type="organism"),
            graph_module._ThinkExtractedEntity(text="SARS-CoV-2", entity_type="organism"),
        ]
    )
    assert spans == ["SARS-CoV-2"]
    candidates = graph_module._gene_shaped_fallback_candidates(
        "Variants in GCK causing MODY in SARS-CoV-2", [], spans
    )
    assert "MODY" in candidates and "SARS" not in candidates, candidates


@pytest.mark.asyncio
async def test_an_organism_name_is_never_bound_as_a_disease(monkeypatch: pytest.MonkeyPatch) -> None:
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, [("SARS-CoV-2", "organism")])
    result = await graph_module.think_node(_state(SRA_QUESTION))
    curies = [entity.curie for entity in result.get("resolved_entities") or []]
    assert not any(curie.startswith("MedGen:") for curie in curies), curies
    assert ("medgen", "SARS[title]") not in searched, searched


# ---------------------------------------------------------------------------
# The question asked back names the organism and asks for the kind of record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_organism_question_asks_which_kind_of_record(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_ncbi(monkeypatch)
    _install_model(monkeypatch, [("Mycobacterium tuberculosis", "organism")])
    result = await graph_module.think_node(_state(ASSEMBLY_QUESTION))
    asked = result.get("clarification_needed")
    assert asked is not None and asked != graph_module.CLARIFICATION_QUESTION
    assert "which kind of record about Mycobacterium tuberculosis" in asked, asked
    assert "gene" not in asked.lower(), asked


@pytest.mark.asyncio
async def test_a_question_with_no_organism_still_gets_the_gene_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_ncbi(monkeypatch)
    _install_model(monkeypatch, [])
    result = await graph_module.think_node(_state(REFERRING_GENE_QUESTION))
    assert result.get("clarification_needed") == graph_module.CLARIFICATION_QUESTION


def test_the_organism_question_quotes_only_name_characters() -> None:
    asked = graph_module._organism_record_question("<b>Mus musculus</b>")
    assert "<" not in asked and ">" not in asked
    assert "Mus musculus" in asked
    assert len(asked) < 500


# ---------------------------------------------------------------------------
# An organism resolves through NCBI Taxonomy, with its citation
# ---------------------------------------------------------------------------


def _organism(text: str) -> graph_module._ThinkExtractedEntity:
    return graph_module._ThinkExtractedEntity(text=text, entity_type="organism")


@pytest.mark.asyncio
async def test_an_organism_span_resolves_to_its_taxonomy_record_with_a_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched = _install_ncbi(monkeypatch)
    organism = await graph_module.resolve_organism([_organism("SARS-CoV-2")])
    assert organism is not None
    assert (organism.mention, organism.taxid, organism.curie) == (
        "SARS-CoV-2",
        "2697049",
        "NCBITaxon:2697049",
    )
    assert organism.source_url == "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=2697049"
    assert searched == [("taxonomy", "SARS-CoV-2[All Names]")]
    # The gene path's check reads the same answer: one search, not two.
    assert await graph_module._organism_is_known("SARS-CoV-2") is True
    assert len(searched) == 1, searched


@pytest.mark.asyncio
async def test_no_basis_to_pick_one_organism_resolves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_ncbi(monkeypatch)
    # A name NCBI files under two taxa.
    assert await graph_module.resolve_organism([_organism("mouse")]) is None
    # Two organisms NCBI knows: a cross-species question, never a guess.
    assert await graph_module.resolve_organism([_organism("SARS-CoV-2"), _organism("human")]) is None
    # A name NCBI does not know, and no organism at all.
    assert await graph_module.resolve_organism([_organism("MODY")]) is None
    assert await graph_module.resolve_organism([]) is None
    # Populate check: a span NCBI rejects beside one it knows still resolves the one.
    both = await graph_module.resolve_organism([_organism("MODY"), _organism("human")])
    assert both is not None and both.taxid == "9606"


@pytest.mark.asyncio
async def test_a_failed_taxonomy_lookup_resolves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fail(params: Any) -> Any:
        raise RuntimeError("transport down")

    monkeypatch.setattr(ncbi_eutils_actions, "search", _fail)
    graph_module._ORGANISM_KNOWN_CACHE.clear()
    assert await graph_module.resolve_organism([_organism("SARS-CoV-2")]) is None
    assert graph_module._ORGANISM_KNOWN_CACHE == {}, "a failure is never remembered"


# ---------------------------------------------------------------------------
# Think hands Plan the organism and the record kind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_think_resolves_the_organism_for_a_record_question(monkeypatch: pytest.MonkeyPatch) -> None:
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, [("SARS-CoV-2", "organism")], record_type="sra")
    result = await graph_module.think_node(_state(SRA_QUESTION))
    assert [(e.text, e.curie) for e in result["resolved_entities"]] == [("SARS-CoV-2", "NCBITaxon:2697049")]
    records = result["organism_records"]
    assert records.organism.taxid == "2697049" and records.record_type == "sra"
    assert result.get("clarification_needed") is None
    assert not any(db == "medgen" for db, _ in searched), searched
    think = next(e for e in result["events"] if e.type == "think")
    assert "NCBI Taxonomy 2697049" in think.payload["narrative"]
    assert "not applied" in think.payload["narrative"]


@pytest.mark.asyncio
async def test_with_no_record_type_the_organism_question_is_asked_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Populate check for the arm above: the classifier's record type, not
    the organism alone, is what routes the question."""
    _install_ncbi(monkeypatch)
    _install_model(monkeypatch, [("Mycobacterium tuberculosis", "organism")], record_type="none")
    result = await graph_module.think_node(_state(ASSEMBLY_QUESTION))
    assert "organism_records" not in result
    assert result["resolved_entities"] == []
    assert "which kind of record about Mycobacterium tuberculosis" in result["clarification_needed"]


@pytest.mark.parametrize("record_type", ["none", "sra"])
@pytest.mark.asyncio
async def test_a_gene_question_is_unchanged(monkeypatch: pytest.MonkeyPatch, record_type: str) -> None:
    """A gene that resolves keeps the question a gene question, whatever
    organism and record type the classifier read: no organism anchor, and
    the graph call is planned first, exactly as before this card."""
    _install_ncbi(monkeypatch)

    async def _gene(symbol: str, *, taxon: str = "human") -> str | None:
        return "NCBIGene:672" if symbol == "BRCA1" else None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _gene)
    fields = {"record_type": record_type} if record_type != "none" else {}
    _install_model(monkeypatch, [("BRCA1", "gene"), ("human", "organism")], **fields)
    result = await graph_module.think_node(_state("Which SRA runs study BRCA1 in human?"))
    assert [e.curie for e in result["resolved_entities"]] == ["NCBIGene:672"]
    assert "organism_records" not in result
    plan = await graph_module.plan_node(
        _state(
            "Which SRA runs study BRCA1 in human?",
            resolved_entities=result["resolved_entities"],
            query_class="single_hop",
        )
    )
    assert isinstance(plan["tool_calls"][0], graph_module._PlannedToolCall)
    assert not any(getattr(c, "purpose", "") == "sra_search" for c in plan["tool_calls"])


# ---------------------------------------------------------------------------
# Plan routes the organism to its records
# ---------------------------------------------------------------------------


async def _plan_for(question: str, mention: str, taxid: str, record_type: str) -> dict[str, Any]:
    organism = graph_module.ResolvedOrganism(mention=mention, taxid=taxid)
    state = _state(
        question,
        resolved_entities=[EventResolvedEntity(text=mention, curie=organism.curie, confidence=1.0)],
        query_class="exploratory",
        organism_records=graph_module._OrganismRecords(organism=organism, record_type=record_type),
    )
    return await graph_module.plan_node(state)


@pytest.mark.asyncio
async def test_an_organism_and_sra_runs_plan_the_sra_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    result = await _plan_for(SRA_QUESTION, "SARS-CoV-2", "2697049", "sra")
    calls = result["tool_calls"]
    search = calls[0]
    assert isinstance(search, graph_module._PlannedNcbiEfetchToolCall)
    assert search.purpose == "sra_search"
    assert search.ncbi_efetch_input.root.db == "sra"
    assert search.ncbi_efetch_input.root.term == "txid2697049[Organism:exp]"
    taxonomy = calls[1]
    assert taxonomy.purpose == "taxonomy_summary" and taxonomy.ncbi_efetch_input.root.ids == ["2697049"]
    follow_ups = [c for c in calls if isinstance(c, graph_module._PlannedFollowUpCall)]
    assert [(f.source_purpose, f.purpose) for f in follow_ups] == [("sra_search", "sra_summary")]
    assert not any(isinstance(c, graph_module._PlannedToolCall) for c in calls), "no graph call"
    plan = next(e for e in result["events"] if e.type == "plan")
    assert "SARS-CoV-2" in plan.payload["narrative"] and "2697049" in plan.payload["narrative"]
    assert [r["curie"] for r in plan.payload["resolved_entities"]] == ["NCBITaxon:2697049"]


@pytest.mark.asyncio
async def test_an_organism_and_assemblies_plan_the_assembly_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    result = await _plan_for(ASSEMBLY_QUESTION, "Mycobacterium tuberculosis", "1773", "assembly")
    calls = result["tool_calls"]
    assert calls[0].purpose == "assembly_search"
    assert calls[0].ncbi_efetch_input.root.db == "assembly"
    assert calls[0].ncbi_efetch_input.root.term == "txid1773[Organism:exp]"
    follow_ups = [c for c in calls if isinstance(c, graph_module._PlannedFollowUpCall)]
    assert [(f.source_purpose, f.purpose) for f in follow_ups] == [("assembly_search", "assembly_summary")]
    assert not any(getattr(c, "purpose", "") == "sra_search" for c in calls)
    assert not any(isinstance(c, graph_module._PlannedToolCall) for c in calls), "no graph call"


def test_the_follow_ups_fetch_the_ids_the_search_returned() -> None:
    for source, purpose, db in (("sra_search", "sra_summary", "sra"), ("assembly_search", "assembly_summary", "assembly")):
        follow_up = graph_module._PlannedFollowUpCall(
            tool_call=graph_module.ToolCall(tool="ncbi_efetch", call_id="ne-abc", layer="layer_2_api"),
            purpose=purpose,
            source_purpose=source,
        )
        concrete = graph_module._follow_up_planned_call(follow_up, ["5", "40", "300", "40"])
        assert concrete is not None and concrete.purpose == purpose
        assert concrete.ncbi_efetch_input.root.db == db
        assert concrete.ncbi_efetch_input.root.ids == ["300", "40", "5"]
        assert concrete.tool_call.call_id == "ne-abc"
