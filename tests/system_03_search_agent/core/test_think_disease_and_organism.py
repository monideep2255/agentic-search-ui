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


# Card 129 (2026-10-22): MedGen's own record type ranks the candidates.
# The 20 ESummary records MedGen returned live that day for
# `breast[title] AND cancer[title]`, in its order, each with its
# `semantictype` in the wrapped shape ESummary sends
# (`testing/Developer/reports/2026-10-22_card129/ncbi_check.md`), and the
# same day's shapes for bronchiolitis and MODY, the two controls.
_F, _N, _D = "Finding", "Neoplastic Process", "Disease or Syndrome"
BREAST_CANCER_RECORDS = [
    ("382914", "C2676676", "Breast-ovarian cancer, familial, susceptibility to, 1", _F),
    ("382625", "C2675520", "Breast-ovarian cancer, familial, susceptibility to, 2", _F),
    ("87542", "C0346153", "Familial cancer of breast", _N),
    ("151793", "C0677776", "Hereditary breast ovarian cancer syndrome", _N),
    ("310839", "C1708349", "Hereditary diffuse gastric adenocarcinoma", _N),
    ("651", "C0006142", "Malignant tumor of breast", _N),
    ("82785", "C0268301", "Partial androgen insensitivity syndrome", _D),
    ("854012", "C3469522", "Breast cancer, susceptibility to", _F),
    ("865388", "C4016951", "Breast cancer, early-onset", _N),
    ("729095", "C1320450", "Seen by breast cancer nurse", _F),
    ("929799", "C4304130", "Breast cancer screening declined", _F),
    ("865018", "C4016581", "Androgen insensitivity, partial, with breast cancer", _F),
    ("865196", "C4016759", "BREAST CANCER, PROTECTION AGAINST", _F),
    ("880162", "CN235586", "bilateral breast cancer", _F),
    ("879372", "C4047698", "Breast cancer screening not done", _F),
    ("370568", "C1968974", "BREAST CANCER, INVASIVE, SUSCEPTIBILITY TO", _F),
    ("436751", "C2676677", "BREAST CANCER, FAMILIAL, SUSCEPTIBILITY TO, 1", _F),
    ("382626", "C2675521", "BREAST CANCER, FAMILIAL, SUSCEPTIBILITY TO, 2", _F),
    ("864797", "C4016360", "BREAST CANCER, SUSCEPTIBILITY TO, IN BRCA1 AND BRCA2 CARRIERS", _F),
    ("350032", "C1861471", "Paraneoplastic SPS is associated with breast cancer and other malignancies", _F),
]
BRONCHIOLITIS_RECORDS = [
    ("759730", "C3532617", "History of bronchiolitis", _F),
    ("1896790", "C6066561", "Bronchiolitis, acute and chronic", _F),
    ("1840786", "C5830150", "Postinfectious bronchiolitis obliterans", _F),
    ("14235", "C0006271", "Unusual bronchiolitis", _D),
    ("113", "C0001311", "Acute bronchiolitis", _D),
    ("547277", "C0276340", "Respiratory syncytial virus bronchiolitis", _D),
    ("1003213", "CN322574", "Toxic bronchiolitis", _D),
    ("390091", "C2350875", "Bronchiolitis, Constrictive", _D),
    ("863573", "C4015136", "Recurrent bronchiolitis", _D),
    ("1621902", "C0850742", "Chronic bronchiolitis", _D),
    ("547125", "C0276154", "Adenoviral bronchiolitis", _D),
    ("538515", "C0264366", "Necrotizing bronchiolitis", _D),
    ("385450", "C2350876", "Bronchiolitis exudativa", _D),
    ("696309", "C1272766", "Follicular bronchiolitis", _D),
    ("573503", "C0340047", "Drug-induced bronchiolitis obliterans", _D),
    ("1808244", "C5574736", "Transplant-related bronchiolitis obliterans", _D),
    ("666", "C0006274", "Bronchiolitis, Viral", _D),
    ("186356", "C5925142", "Non-transplant-related bronchiolitis obliterans", _D),
    ("1", "C2350988", "Bronchiolitis, Proliferative", _D),
    ("2", "C0264369", "Acute obliterating bronchiolitis", _D),
]
ARACHNODACTYLY_RECORDS = [
    ("1795", "C0003706", "Arachnodactyly", _F),
    ("2829", "C0220668", "Congenital contractural arachnodactyly", "Congenital Abnormality"),
]


def _install_typed_medgen(
    monkeypatch: pytest.MonkeyPatch, term: str, records: list[tuple[str, str, str, str]]
) -> None:
    """The live ESummary shape: `semantictype` wrapped as `{"value": ...}`."""
    by_uid = {uid: (cid, title, kind) for uid, cid, title, kind in records}

    async def _search(params):
        uids = [uid for uid, *_ in records] if params.term == term else []
        return SimpleNamespace(status="ok" if uids else "empty", records=[_Record({"idlist": uids})])

    async def _summary(params):
        return SimpleNamespace(
            status="ok",
            records=[
                _Record(
                    {
                        "conceptid": by_uid[uid][0],
                        "title": by_uid[uid][1],
                        "semantictype": {"value": by_uid[uid][2]},
                    }
                )
                for uid in params.ids
                if uid in by_uid
            ],
        )

    monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", _summary)
    graph_module._DISEASE_CURIE_CACHE.clear()


@pytest.mark.asyncio
async def test_breast_cancer_binds_disease_records_and_never_the_nurse_visit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card 129. Before the rule, the 8 phrase-in-title records were 7
    Findings led by C1320450 "Seen by breast cancer nurse", and C0006142
    was cut. Mutation: delete the `if disease_typed:` narrowing and this is
    red (C1320450 binds, C0006142 does not)."""
    _install_typed_medgen(monkeypatch, "breast[title] AND cancer[title]", BREAST_CANCER_RECORDS)
    curies, matched = await graph_module.resolve_disease_mention_to_curies("breast cancer")
    assert matched == 20
    assert curies == [
        "MedGen:C4016951",
        "MedGen:C0006142",
        "MedGen:C0268301",
        "MedGen:C0346153",
        "MedGen:C0677776",
        "MedGen:C1708349",
    ]
    findings = {f"MedGen:{cid}" for _, cid, _, kind in BREAST_CANCER_RECORDS if kind == _F}
    assert not findings & set(curies)


@pytest.mark.asyncio
async def test_findings_still_bind_when_no_disease_record_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rank, never drop: with only Finding records matched, they bind as
    before. Mutation: narrow to disease-typed records unconditionally and
    this is red (nothing binds)."""
    screening = [row for row in BREAST_CANCER_RECORDS if "screening" in row[2]]
    _install_typed_medgen(
        monkeypatch, "breast[title] AND cancer[title] AND screening[title]", screening
    )
    curies, _ = await graph_module.resolve_disease_mention_to_curies("breast cancer screening")
    assert curies == ["MedGen:C4047698", "MedGen:C4304130"]


@pytest.mark.asyncio
async def test_an_exact_finding_title_still_binds_over_a_disease_containing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A phenotype the person named exactly keeps its record, whatever its
    type. Mutation: apply the type narrowing before the exact rule and this
    is red (the congenital syndrome binds instead)."""
    _install_typed_medgen(monkeypatch, "Arachnodactyly[title]", ARACHNODACTYLY_RECORDS)
    curies, _ = await graph_module.resolve_disease_mention_to_curies("Arachnodactyly")
    assert curies == ["MedGen:C0003706"]


@pytest.mark.asyncio
async def test_bronchiolitis_binds_the_same_eight_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the 8 records bronchiolitis bound before the rule were all
    disease-typed, so they are unchanged."""
    _install_typed_medgen(monkeypatch, "bronchiolitis[title]", BRONCHIOLITIS_RECORDS)
    curies, matched = await graph_module.resolve_disease_mention_to_curies("bronchiolitis")
    assert matched == 20
    assert curies == [
        "MedGen:C0001311",
        "MedGen:C0006271",
        "MedGen:C0006274",
        "MedGen:C0264366",
        "MedGen:C0264369",
        "MedGen:C0276154",
        "MedGen:C0276340",
        "MedGen:C0340047",
    ]


@pytest.mark.asyncio
async def test_mody_binds_the_same_eight_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: all 8 MODY records are "Disease or Syndrome", so the order
    the earlier test pins is unchanged."""
    mody = [(uid, *MEDGEN_TITLES[uid], _D) for uid in MODY_HITS]
    _install_typed_medgen(monkeypatch, "MODY[title]", mody)
    curies, matched = await graph_module.resolve_disease_mention_to_curies("MODY")
    assert matched == 8
    assert curies[0] == "MedGen:C0271653"
    assert curies[1:] == sorted(f"MedGen:{MEDGEN_TITLES[uid][0]}" for uid in MODY_HITS if uid != "543472")
