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

Populate checks, so no arm passes on an empty result: the same question
with no organism span still yields "SARS"; a span Taxonomy rejects
("MODY", the 2-of-20 GCK runs) still yields its token; a question with no
organism still gets the gene question.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions

SRA_QUESTION = "List SRA runs of SARS-CoV-2 from hospital samples and say why each one matched."
ASSEMBLY_QUESTION = "Which Mycobacterium tuberculosis genome assemblies exist, and how do I get them?"
REFERRING_GENE_QUESTION = "What diseases is it linked to?"

#: NCBI Taxonomy, as recorded live in the diagnosis's `raw/ncbi_lookups.json`.
TAXONOMY = {"sars-cov-2": ["2697049"], "mycobacterium tuberculosis": ["1773"]}
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


def _state(text: str) -> dict[str, Any]:
    return {
        "query": Query(text=text, session_id="s-org", trace_id="t-org", user_id=None),
        "harness": harness_module.Harness(trace_id="t-org"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }


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
