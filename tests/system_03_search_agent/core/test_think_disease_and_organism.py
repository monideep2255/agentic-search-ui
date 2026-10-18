"""Think's disease-span resolver (decision D3) and the GCK refusal fix, both
2026-09-14. No network: NCBI's `search` and `summary` actions and the gene
resolver are replaced by fakes that answer with recorded live shapes.

Mutations that turn each arm red (each run by hand before the arm was kept):

- `test_an_exact_title_binds_that_record_alone`: make the exact rule fall
  through to containment (delete the `if exact:` branch): the mention then
  binds every hit and the single-CURIE assertion is red.
- `test_a_name_index_match_binds_a_capped_stable_set`: drop the
  `[:_MAX_DISEASE_CURIES_PER_MENTION]` slice: the count assertion is red;
  reverse the sort: the order assertion is red.
- `test_a_placeholder_title_is_never_bound`: remove the
  `is_placeholder_condition_title` guard: "not provided" is bound (red).
- `test_operators_and_brackets_never_reach_the_term`: remove the stopword
  filter: "OR" reaches the term (red).
- `test_a_transport_failure_binds_nothing_and_is_not_cached`: cache the
  failure: the second call no longer hits the fake (red).
- `test_a_disease_span_never_refuses_on_its_own`: append an unconfirmed
  disease mention to `unresolved_symbols`: red.
- `test_a_mistyped_gene_still_refuses_by_name`: clear `unresolved_symbols`
  in the disease branch: red.
- `test_an_organism_taxonomy_rejects_does_not_change_the_taxon`: bypass
  `_confirmed_taxon_for_extraction` (call `_taxon_for_extraction`
  directly): GCK is looked up against "MODY" and the taxon assertion is
  red. This is the GCK refusal's cause, reproduced from the 2-of-20 Think
  runs where the model tagged MODY as an organism.
- `test_an_organism_the_check_cannot_run_for_is_kept`: treat None as
  False: the mouse question resolves against human (red).
- `test_the_fallback_runs_when_every_model_span_failed`: restore the
  `not model_named_a_gene` gate: no fallback lookup happens (red).
- `test_a_generic_word_is_never_searched_as_a_disease_name` (2026-09-22,
  the call-ceiling measurement): take the `_is_generic_disease_mention`
  guard out: "condition" reaches the term and binds the fake's hits (red).
- `test_a_named_disease_with_a_generic_word_is_still_searched`: widen the
  guard to "any generic word": "Lynch syndrome" is no longer searched
  (red). This is the populate check for the arm above.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.tools import ncbi_eutils_actions

MEDGEN_TITLES = {
    "908119": ("C4225299", "Maturity-onset diabetes of the young type 14"),
    "897640": ("C4225365", "Maturity-onset diabetes of the young type 13"),
    "863399": ("C4014962", "Fanconi renotubular syndrome 4 with maturity-onset diabetes of the young"),
    "543472": ("C0271653", "Impaired glucose tolerance in MODY (maturity onset diabetes in the young)"),
    "377589": ("C1852093", "Maturity-onset diabetes of the young type 1"),
    "324942": ("C1838100", "Maturity-onset diabetes of the young type 3"),
    "318863": ("C1833382", "Maturity-onset diabetes of the young type 4"),
    "87434": ("C0342277", "Maturity-onset diabetes of the young type 2"),
    "1392102": ("C3888631", "Monogenic diabetes"),
    "1381352": ("C4331425", "Transcription Factor-Associated Monogenic Diabetes"),
    "999001": ("C3661900", "not provided"),
    "999002": ("C0342276", "Maturity-onset diabetes of the young"),
}


class _Record:
    def __init__(self, fields: dict) -> None:
        self.fields = fields


def _install_medgen(monkeypatch: pytest.MonkeyPatch, hits_by_term: dict[str, list[str]], *, fail: bool = False):
    terms: list[str] = []

    async def _search(params):
        terms.append(params.term)
        if fail:
            raise RuntimeError("boom")
        if params.db == "taxonomy":
            known = params.term.split("[")[0].strip().casefold() in {"mouse", "mus musculus", "human"}
            return SimpleNamespace(status="ok" if known else "empty", records=[_Record({"idlist": ["10090"]})] if known else [])
        uids = hits_by_term.get(params.term, [])
        return SimpleNamespace(status="ok" if uids else "empty", records=[_Record({"idlist": uids})] if uids else [])

    async def _summary(params):
        return SimpleNamespace(
            status="ok",
            records=[
                _Record({"conceptid": MEDGEN_TITLES[uid][0], "title": MEDGEN_TITLES[uid][1]})
                for uid in params.ids
                if uid in MEDGEN_TITLES
            ],
        )

    monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", _summary)
    graph_module._DISEASE_CURIE_CACHE.clear()
    graph_module._ORGANISM_KNOWN_CACHE.clear()
    return terms


MODY_HITS = ["908119", "897640", "863399", "543472", "377589", "324942", "318863", "87434"]


@pytest.mark.asyncio
async def test_an_exact_title_binds_that_record_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_medgen(monkeypatch, {"Monogenic[title] AND diabetes[title]": ["1392102", "1381352"]})
    curies, matched = await graph_module.resolve_disease_mention_to_curies("Monogenic diabetes")
    assert curies == ["MedGen:C3888631"] and matched == 2


@pytest.mark.asyncio
async def test_a_name_index_match_binds_a_capped_stable_set(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = MODY_HITS + ["1392102", "1381352"]  # ten hits, cap is eight
    _install_medgen(monkeypatch, {"MODY[title]": hits})
    curies, matched = await graph_module.resolve_disease_mention_to_curies("MODY")
    assert matched == 10
    assert len(curies) == graph_module._MAX_DISEASE_CURIES_PER_MENTION
    # The title that carries the literal acronym comes first, then the
    # name-index hits in concept-id order.
    assert curies[0] == "MedGen:C0271653"
    assert curies[1:] == sorted(curies[1:])
    assert "MedGen:C4331425" not in curies, "the ninth and tenth hits fall outside the cap"


@pytest.mark.asyncio
async def test_a_placeholder_title_is_never_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_medgen(monkeypatch, {"MODY[title]": ["999001", "324942"]})
    curies, matched = await graph_module.resolve_disease_mention_to_curies("MODY")
    assert curies == ["MedGen:C1838100"] and matched == 1


@pytest.mark.asyncio
async def test_operators_and_brackets_never_reach_the_term(monkeypatch: pytest.MonkeyPatch) -> None:
    terms = _install_medgen(monkeypatch, {})
    await graph_module.resolve_disease_mention_to_curies("MODY[all] OR x NOT y")
    assert terms == ["MODY[title] AND all[title]"], terms
    assert not any("OR" in term.split() or "NOT" in term.split() for term in terms)


@pytest.mark.asyncio
async def test_a_hyphenated_phrase_is_sent_as_anded_words(monkeypatch: pytest.MonkeyPatch) -> None:
    terms = _install_medgen(
        monkeypatch,
        {"maturity[title] AND onset[title] AND diabetes[title] AND young[title]": ["999002", "324942"]},
    )
    curies, _ = await graph_module.resolve_disease_mention_to_curies("maturity-onset diabetes of the young")
    assert terms and "of[title]" not in terms[0] and "the[title]" not in terms[0]
    assert curies == ["MedGen:C0342276"], "the exact umbrella title wins over the subtype"


@pytest.mark.asyncio
async def test_a_transport_failure_binds_nothing_and_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    terms = _install_medgen(monkeypatch, {}, fail=True)
    assert await graph_module.resolve_disease_mention_to_curies("MODY") == ([], 0)
    assert "mody" not in graph_module._DISEASE_CURIE_CACHE
    await graph_module.resolve_disease_mention_to_curies("MODY")
    assert len(terms) == 2, "a failed lookup must be retried on the next call, not replayed"


@pytest.mark.asyncio
async def test_a_disease_span_binds_through_confirmation_and_is_disclosed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_medgen(monkeypatch, {"MODY[title]": MODY_HITS})

    async def _no_gene(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    spans = [graph_module._ThinkExtractedEntity(text="MODY", entity_type="disease")]
    resolution = await graph_module._confirm_extracted_entities(spans)
    assert len(resolution.curies) == 8 and all(c.startswith("MedGen:") for c in resolution.curies)
    assert resolution.confirmed[0] == ("MODY", "MedGen:C0271653")
    assert resolution.disclosures == ("MODY: 8 MedGen records matched by name",)
    assert resolution.unresolved_symbols == []


@pytest.mark.asyncio
async def test_a_disease_span_never_refuses_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_medgen(monkeypatch, {})
    spans = [graph_module._ThinkExtractedEntity(text="Nonexistent syndrome", entity_type="disease")]
    resolution = await graph_module._confirm_extracted_entities(spans)
    assert resolution.curies == [] and resolution.unresolved_symbols == []


@pytest.mark.asyncio
async def test_a_mistyped_gene_still_refuses_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_medgen(monkeypatch, {"MODY[title]": MODY_HITS})

    async def _no_gene(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    spans = [
        graph_module._ThinkExtractedEntity(text="BRCA9", entity_type="gene"),
        graph_module._ThinkExtractedEntity(text="MODY", entity_type="disease"),
    ]
    resolution = await graph_module._confirm_extracted_entities(spans)
    assert resolution.unresolved_symbols == ["BRCA9"]
    # Plan's rule 1 reads `target_curies` and `unresolved_symbols`: with a
    # disease bound beside the failed gene the answer is about the disease;
    # with nothing else bound it is the refusal by name, exactly as before.
    lone = await graph_module._confirm_extracted_entities(spans[:1])
    assert lone.curies == [] and lone.unresolved_symbols == ["BRCA9"]
    decision = await graph_module._select_planned_tool_call(
        "Which diseases are associated with BRCA9?", "single_hop", [], ["BRCA9"]
    )
    assert isinstance(decision, graph_module._UnresolvedEntityRefusal)


@pytest.mark.asyncio
async def test_an_organism_taxonomy_rejects_does_not_change_the_taxon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The GCK refusal's cause, reproduced: the model tags MODY as an
    ORGANISM; Taxonomy has no such name; the taxon must stay human and GCK
    must resolve against it."""
    _install_medgen(monkeypatch, {})
    looked_up: list[tuple[str, str]] = []

    async def _gene(symbol: str, *, taxon: str = "human") -> str | None:
        looked_up.append((symbol, taxon))
        return "NCBIGene:2645" if (symbol, taxon) == ("GCK", "human") else None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _gene)
    spans = [
        graph_module._ThinkExtractedEntity(text="GCK", entity_type="gene"),
        graph_module._ThinkExtractedEntity(text="MODY", entity_type="organism"),
    ]
    assert await graph_module._confirmed_taxon_for_extraction(spans) == "human"
    resolution = await graph_module._confirm_extracted_entities(spans)
    assert looked_up == [("GCK", "human")], looked_up
    assert resolution.curies == ["NCBIGene:2645"] and resolution.unresolved_symbols == []


@pytest.mark.asyncio
async def test_a_real_organism_still_sets_the_taxon(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_medgen(monkeypatch, {})
    spans = [
        graph_module._ThinkExtractedEntity(text="Tp53", entity_type="gene"),
        graph_module._ThinkExtractedEntity(text="mouse", entity_type="organism"),
    ]
    assert await graph_module._confirmed_taxon_for_extraction(spans) == "mouse"


@pytest.mark.asyncio
async def test_an_organism_the_check_cannot_run_for_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Taxonomy outage must never turn a mouse question into a human one
    (F-4.7-A-03 in the other direction)."""
    _install_medgen(monkeypatch, {}, fail=True)
    spans = [
        graph_module._ThinkExtractedEntity(text="Tp53", entity_type="gene"),
        graph_module._ThinkExtractedEntity(text="mouse", entity_type="organism"),
    ]
    assert await graph_module._organism_is_known("mouse") is None
    assert await graph_module._confirmed_taxon_for_extraction(spans) == "mouse"


@pytest.mark.asyncio
async def test_the_fallback_runs_when_every_model_span_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through `think_node` with a scripted classification: the model names
    GCK, the first confirmation fails, and the gene-shaped fallback confirms
    it on the second attempt, so the turn resolves instead of refusing."""
    _install_medgen(monkeypatch, {})
    attempts: list[str] = []

    async def _gene(symbol: str, *, taxon: str = "human") -> str | None:
        attempts.append(symbol)
        return "NCBIGene:2645" if len(attempts) > 1 and symbol.upper() == "GCK" else None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _gene)

    classification = graph_module._ThinkClassification(
        query_class="single_hop",
        entities=[graph_module._ThinkExtractedEntity(text="GCK", entity_type="gene")],
        narrative="Variants in GCK linked to MODY.",
    )

    async def _fake_dispatch(*args, **kwargs):
        return SimpleNamespace(content=classification.model_dump_json())

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    from system_03_search_agent.contracts.query import Query
    from system_03_search_agent.harness import harness as harness_module

    query = Query(text="Variants in GCK causing MODY", session_id="s", trace_id="t", user_id=None)
    state = {
        "query": query,
        "harness": harness_module.Harness(trace_id="t"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }
    result = await graph_module.think_node(state)
    assert attempts[:2] == ["GCK", "GCK"], attempts
    assert [e.curie for e in result["resolved_entities"]] == ["NCBIGene:2645"]
    assert result.get("unresolved_entity_refusal") is None


@pytest.mark.asyncio
async def test_a_failed_gene_span_that_medgen_confirms_binds_as_a_disease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured live 2026-09-14: the model tagged "MODY" as a gene on 1 of 5
    runs and the answer refused by name. A failed gene span that MedGen
    confirms leaves the refusal path as a bound disease; one it does not
    confirm (BRCA9) stays unresolved. Mutation that turns this red: delete
    the `if not curies and unresolved:` block in
    `_confirm_extracted_entities` (MODY then stays in `unresolved_symbols`).
    """
    _install_medgen(monkeypatch, {"MODY[title]": MODY_HITS})

    async def _no_gene(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    resolution = await graph_module._confirm_extracted_entities(
        [graph_module._ThinkExtractedEntity(text="MODY", entity_type="gene")]
    )
    assert resolution.unresolved_symbols == []
    assert len(resolution.curies) == 8 and resolution.confirmed[0] == ("MODY", "MedGen:C0271653")
    assert resolution.disclosures == ("MODY: 8 MedGen records matched by name",)
    mixed = await graph_module._confirm_extracted_entities(
        [
            graph_module._ThinkExtractedEntity(text="BRCA9", entity_type="gene"),
            graph_module._ThinkExtractedEntity(text="MODY", entity_type="gene"),
        ]
    )
    assert mixed.unresolved_symbols == ["BRCA9"] and len(mixed.curies) == 8


@pytest.mark.asyncio
async def test_a_generic_word_is_never_searched_as_a_disease_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Measured live 2026-09-22: "condition" bound "Patient condition
    unchanged" and seven more, "tumour" bound eight mouse tumour records, and
    each answer then listed them as entities the person had named."""
    terms = _install_medgen(
        monkeypatch,
        {"condition[title]": MODY_HITS, "tumour[title]": MODY_HITS, "human[title] AND tumour[title]": MODY_HITS},
    )
    for mention in ("condition", "tumour", "human tumour samples", "genetic disease", "Rare hereditary condition"):
        curies, matched = await graph_module.resolve_disease_mention_to_curies(mention)
        assert curies == [] and matched == 0, mention
    assert terms == [], terms
    assert graph_module._DISEASE_CURIE_CACHE == {}, "nothing was looked up, so nothing is remembered"


@pytest.mark.asyncio
async def test_a_named_disease_with_a_generic_word_is_still_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    terms = _install_medgen(monkeypatch, {"Lynch[title] AND syndrome[title]": ["324942"]})
    curies, matched = await graph_module.resolve_disease_mention_to_curies("Lynch syndrome")
    assert terms == ["Lynch[title] AND syndrome[title]"], terms
    assert curies == ["MedGen:C1838100"] and matched == 1


@pytest.mark.asyncio
async def test_a_generic_disease_span_binds_nothing_and_discloses_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rs334 question's "condition" span, end to end through confirmation:
    no CURIE, no disclosure, and never an unresolved symbol (a disease the
    model mis-read must not become a gene refusal)."""
    terms = _install_medgen(monkeypatch, {"condition[title]": MODY_HITS})

    async def _no_gene(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _no_gene)
    spans = [graph_module._ThinkExtractedEntity(text="condition", entity_type="disease")]
    resolution = await graph_module._confirm_extracted_entities(spans)
    assert resolution.curies == [] and resolution.disclosures == ()
    assert resolution.unresolved_symbols == []
    assert terms == [], terms
