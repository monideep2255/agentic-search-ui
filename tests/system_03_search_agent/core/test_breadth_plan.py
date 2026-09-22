"""Tests for `core.breadth_plan`, the "search broad, cite exact" helpers.

No network and no model anywhere in this file: every function under test
is a pure function of its arguments, and that purity is itself one of the
properties pinned here (the determinism arms).

Coverage statement, per `goal-contracts`: each public function gets a valid,
an invalid and a null arm. The determinism arms compare two calls on equal
input and two calls on the same id set in different orders. What this file
does NOT exercise: whether the planned terms are accepted by live ESearch
(verified by hand on 2026-09-14 and recorded in the module docstring), and
the `plan_node` wiring in `core/graph.py`, which did not exist when this
file was written.

Depends on:
    - system_03_search_agent.core.breadth_plan (module under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import breadth_plan as bp

# ---------------------------------------------------------------------------
# build_pubmed_term
# ---------------------------------------------------------------------------


def test_pubmed_term_symbol_only() -> None:
    assert bp.build_pubmed_term("brca1", None) == "BRCA1[Title/Abstract]"


def test_pubmed_term_title_only_is_quoted_and_lowercased() -> None:
    assert (
        bp.build_pubmed_term(None, "Maturity-Onset Diabetes  of the\nYoung")
        == '"maturity-onset diabetes of the young"[Title/Abstract]'
    )


def test_pubmed_term_both_joined_with_and() -> None:
    assert (
        bp.build_pubmed_term("GCK", "maturity-onset diabetes of the young")
        == 'GCK[Title/Abstract] AND "maturity-onset diabetes of the young"[Title/Abstract]'
    )


def test_pubmed_term_strips_operator_characters_from_a_title() -> None:
    term = bp.build_pubmed_term(None, 'cancer" OR "[All Fields] (x)')
    assert term == '"cancer or all fields x"[Title/Abstract]'


def test_pubmed_term_null_inputs_plan_nothing() -> None:
    assert bp.build_pubmed_term(None, None) is None
    assert bp.build_pubmed_term("", "   ") is None
    assert bp.build_pubmed_term(None, '"[]"') is None


@pytest.mark.parametrize("bad", ["BRCA1 OR cancer", "BRCA1[sym]", 'x"y', "a" * 31, "(BRCA1)"])
def test_pubmed_term_rejects_a_symbol_that_is_not_symbol_shaped(bad: str) -> None:
    with pytest.raises(ValueError):
        bp.build_pubmed_term(bad, None)


def test_pubmed_term_rejects_non_string_inputs() -> None:
    with pytest.raises(TypeError):
        bp.build_pubmed_term(672, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bp.build_pubmed_term(None, ["title"])  # type: ignore[arg-type]


def test_pubmed_term_caps_a_long_title() -> None:
    term = bp.build_pubmed_term(None, "d" * 500)
    assert term is not None
    assert len(term) <= bp._MAX_TITLE_CHARS + len('""[Title/Abstract]')


# ---------------------------------------------------------------------------
# plan_first_stage
# ---------------------------------------------------------------------------


def test_first_stage_for_a_gene_plans_pubmed_clinvar_omim_in_fixed_order() -> None:
    calls = bp.plan_first_stage("gck", None)

    assert [call.purpose for call in calls] == ["pubmed_search", "clinvar_search", "omim_search"]
    assert all(call.tool == "ncbi_efetch" and call.layer == "layer_2_api" for call in calls)
    assert all(call.prefix == "ne" for call in calls)
    pubmed, clinvar, omim = (call.tool_input.root for call in calls)
    assert (pubmed.db, pubmed.term, pubmed.retmax) == ("pubmed", "GCK[Title/Abstract]", 5)
    assert (clinvar.db, clinvar.term, clinvar.retmax) == ("clinvar", "GCK[gene]", 10)
    assert (omim.db, omim.term, omim.retmax) == ("omim", "GCK", 10)


def test_first_stage_for_a_disease_title_alone_plans_only_pubmed() -> None:
    calls = bp.plan_first_stage(None, "breast cancer")

    assert [call.purpose for call in calls] == ["pubmed_search"]
    assert calls[0].tool_input.root.term == '"breast cancer"[Title/Abstract]'


def test_first_stage_null_inputs_plan_nothing() -> None:
    assert bp.plan_first_stage(None, None) == ()
    assert bp.plan_first_stage("", "") == ()


def test_first_stage_invalid_symbol_raises_before_any_call_is_planned() -> None:
    with pytest.raises(ValueError):
        bp.plan_first_stage("BRCA1 AND TP53", None)


def test_first_stage_is_deterministic() -> None:
    first = bp.plan_first_stage("BRCA1", "Breast cancer")
    second = bp.plan_first_stage("brca1", "breast  cancer")

    assert first == second
    assert [c.tool_input.model_dump() for c in first] == [
        c.tool_input.model_dump() for c in second
    ]


def test_first_stage_stays_under_the_per_query_call_ceiling() -> None:
    """Three searches plus at most four follow-ups (abstracts, PubTator,
    ClinVar summary, OMIM summary) is seven counted calls, under Section
    21.3's twenty even beside the four calls `plan_node` already makes.
    """
    assert len(bp.plan_first_stage("BRCA1", "breast cancer")) == 3


# ---------------------------------------------------------------------------
# select_ids
# ---------------------------------------------------------------------------


def test_select_ids_sorts_numerically_descending_and_caps() -> None:
    assert bp.select_ids(["9", "42733937", "33180404", "42470517"], 3) == [
        "42733937",
        "42470517",
        "33180404",
    ]


def test_select_ids_is_order_independent_and_dedupes() -> None:
    a = bp.select_ids(["1", "3", "2", "3"], 5)
    b = bp.select_ids(["3", "2", "1"], 5)
    assert a == b == ["3", "2", "1"]


def test_select_ids_drops_invalid_values() -> None:
    assert bp.select_ids(["abc", "", "12 OR 13", None, 3.5, True, "-1", "1" * 16], 5) == []


def test_select_ids_accepts_ints_and_normalises_leading_zeros() -> None:
    assert bp.select_ids([672, "0672"], 5) == ["672"]


def test_f06_zero_is_not_an_id() -> None:
    """Review F-06: `"0"` planned a fetch for PMID 0. A uid is a positive integer."""
    assert bp.select_ids(["0", "00", 0, "000"], 5) == []
    assert bp.plan_literature_follow_up(["0"]) == ()
    assert bp.plan_clinvar_follow_up([0]) == ()


def test_select_ids_null_input() -> None:
    assert bp.select_ids([], 5) == []


# ---------------------------------------------------------------------------
# plan_literature_follow_up
# ---------------------------------------------------------------------------


def test_literature_follow_up_fetches_and_annotates_the_same_pmids() -> None:
    calls = bp.plan_literature_follow_up(["33180404", "42470517", "42438052", "42329282", "42295651", "1"])

    assert [call.purpose for call in calls] == ["pubmed_abstracts", "pubtator_publications"]
    fetch, annotate = calls
    assert fetch.tool == "ncbi_efetch" and fetch.layer == "layer_2_api" and fetch.prefix == "ne"
    assert annotate.tool == "pubtator_annotate" and annotate.layer == "layer_3_enrichment"
    assert annotate.prefix == "pa"
    expected = ["42470517", "42438052", "42329282", "42295651", "33180404"]
    assert fetch.tool_input.root.ids == expected
    assert annotate.tool_input.root.pmids == expected
    assert fetch.tool_input.root.db == "pubmed"
    assert fetch.tool_input.root.rettype == "abstract"
    assert fetch.tool_input.root.retmode == "xml"


def test_literature_follow_up_is_deterministic_across_orderings() -> None:
    a = bp.plan_literature_follow_up(["3", "1", "2"])
    b = bp.plan_literature_follow_up(["2", "3", "1", "1"])
    assert a == b


def test_literature_follow_up_with_only_invalid_pmids_plans_nothing() -> None:
    assert bp.plan_literature_follow_up(["not-a-pmid", ""]) == ()


def test_literature_follow_up_null_input_plans_nothing() -> None:
    assert bp.plan_literature_follow_up([]) == ()


# ---------------------------------------------------------------------------
# plan_clinvar_follow_up / plan_omim_follow_up
# ---------------------------------------------------------------------------


def test_clinvar_follow_up_is_one_capped_summary() -> None:
    ids = [str(n) for n in range(1, 20)]
    calls = bp.plan_clinvar_follow_up(ids)

    assert len(calls) == 1
    call = calls[0]
    assert call.purpose == "clinvar_summary"
    assert call.tool_input.root.db == "clinvar"
    assert call.tool_input.root.ids == [str(n) for n in range(19, 9, -1)]


def test_omim_follow_up_is_one_capped_summary() -> None:
    calls = bp.plan_omim_follow_up(["618858", "618857"])

    assert len(calls) == 1
    assert calls[0].purpose == "omim_summary"
    assert calls[0].tool_input.root.db == "omim"
    assert calls[0].tool_input.root.ids == ["618858", "618857"]


def test_follow_ups_with_invalid_or_null_ids_plan_nothing() -> None:
    assert bp.plan_clinvar_follow_up(["x"]) == ()
    assert bp.plan_clinvar_follow_up([]) == ()
    assert bp.plan_omim_follow_up([None]) == ()
    assert bp.plan_omim_follow_up([]) == ()


# ---------------------------------------------------------------------------
# filter_omim_titles
# ---------------------------------------------------------------------------

_OMIM_RECORDS = [
    {"id": "138079", "fields": {"title": "GLUCOKINASE; GCK"}},
    {"id": "603166", "fields": {"title": "MITOGEN-ACTIVATED PROTEIN KINASE KINASE KINASE KINASE 2; MAP4K2"}},
    {"id": "600842", "fields": {"title": "GLUCOKINASE REGULATOR; GCKR"}},
    {"id": "125853", "fields": {"title": "Diabetes mellitus, noninsulin-dependent; gck related"}},
    {"id": "125851", "fields": {"title": "MATURITY-ONSET DIABETES OF THE YOUNG, TYPE 2; MODY2; GCK, INCLUDED"}},
]


def test_omim_filter_keeps_only_titles_whose_symbol_field_is_the_symbol() -> None:
    """Review F-07: the match is against the semicolon-separated symbol
    fields of the title, exactly, never a word anywhere in the title. So
    `GLUCOKINASE; GCK` passes, `gck related` and the first (name) field do
    not.
    """
    kept = bp.filter_omim_titles(_OMIM_RECORDS, "gck")
    assert [record["id"] for record in kept] == ["138079"]


@pytest.mark.parametrize(
    ("symbol", "title", "expected"),
    [
        ("T", "T-CELL RECEPTOR ALPHA LOCUS; TRA", False),
        ("T", "T BRACHYURY TRANSCRIPTION FACTOR; TBXT; T", True),
        # The first segment is the NAME, never a symbol field, even when it
        # happens to equal the symbol.
        ("T", "T; TBXT", False),
        ("A", "APOLIPOPROTEIN A; APOA", False),
        ("A", "HEMOGLOBIN, ALPHA; A", True),
        ("A", "A CELL DISORDER; XYZ", False),
    ],
)
def test_f07_one_letter_symbols_match_only_a_whole_symbol_field(
    symbol: str, title: str, expected: bool
) -> None:
    kept = bp.filter_omim_titles([{"title": title}], symbol)
    assert bool(kept) is expected


def test_omim_filter_reads_a_bare_fields_mapping_too() -> None:
    kept = bp.filter_omim_titles([{"title": "GLUCOKINASE; GCK"}, {"title": "x"}], "GCK")
    assert len(kept) == 1


def test_omim_filter_ignores_malformed_records() -> None:
    kept = bp.filter_omim_titles(
        [None, "GCK", {"fields": {"title": 5}}, {"fields": None}, {}], "GCK"  # type: ignore[list-item]
    )
    assert kept == []


def test_omim_filter_with_no_symbol_keeps_nothing() -> None:
    assert bp.filter_omim_titles(_OMIM_RECORDS, None) == []
    assert bp.filter_omim_titles(_OMIM_RECORDS, "") == []


def test_omim_filter_rejects_a_malformed_symbol() -> None:
    with pytest.raises(ValueError):
        bp.filter_omim_titles(_OMIM_RECORDS, "GCK OR TP53")


# ---------------------------------------------------------------------------
# GEO DataSets (2026-09-22, fix-plan item 1: G-037 answered with no dataset)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Find GEO expression datasets studying TP53 in human tumour samples.",
        "Is there a GEO dataset on BRCA1?",
        "expression profiling of GCK in islets",
        "any microarray data for TP53",
        "RNA-seq for BRCA1",
        "GSE12345 and TP53",
    ],
)
def test_dataset_words_ask_for_a_geo_search(question: str) -> None:
    assert bp.wants_dataset_search(question)


@pytest.mark.parametrize(
    "question",
    [
        "Which diseases are associated with BRCA1?",
        "What does the BRCA1 gene do, and how is its expression regulated?",
        "geological survey of MODY",
        "",
        None,
    ],
)
def test_ordinary_questions_do_not_ask_for_a_geo_search(question: str | None) -> None:
    assert not bp.wants_dataset_search(question)


def test_gds_term_is_the_symbol_restricted_to_series() -> None:
    assert bp.build_gds_term("tp53") == "TP53[All Fields] AND gse[Entry Type]"
    assert bp.build_gds_term(None) is None
    assert bp.build_gds_term("") is None
    with pytest.raises(ValueError):
        bp.build_gds_term("TP53 OR BRCA1")


def test_first_stage_plans_the_geo_search_last_and_only_when_asked() -> None:
    plain = bp.plan_first_stage("TP53", None)
    with_datasets = bp.plan_first_stage("TP53", None, datasets=True)
    assert [c.purpose for c in plain] == ["pubmed_search", "clinvar_search", "omim_search"]
    assert [c.purpose for c in with_datasets] == [
        "pubmed_search", "clinvar_search", "omim_search", "gds_search",
    ]
    gds = with_datasets[-1].tool_input.root
    assert (gds.db, gds.term, gds.retmax) == ("gds", "TP53[All Fields] AND gse[Entry Type]", 5)
    assert with_datasets[-1].tool == "ncbi_efetch" and with_datasets[-1].layer == "layer_2_api"
    # A dataset question with no resolved gene plans no GEO search: the
    # term needs a symbol, and the fan-out is gene-anchored like the rest.
    assert bp.plan_first_stage(None, "breast cancer", datasets=True) == bp.plan_first_stage(
        None, "breast cancer"
    )


def test_gds_follow_up_is_one_capped_summary() -> None:
    (call,) = bp.plan_gds_follow_up(["200346694", "200315234", "200346344", "x", "200346694"])
    assert call.purpose == "gds_summary"
    assert call.tool_input.root.db == "gds"
    assert call.tool_input.root.ids == ["200346694", "200346344", "200315234"]
    assert bp.plan_gds_follow_up([]) == ()
    assert bp.plan_gds_follow_up(["nope"]) == ()


def test_the_geo_pair_keeps_a_dataset_question_under_the_call_ceiling() -> None:
    """A gene question measured 14 to 16 of its 20 allowed Layer 2 and 3
    calls on 2026-09-22 with OMIM on. The GEO search and its summary add
    two, only on a question that asks for datasets, so the worst such
    question reaches 18 and never the ceiling."""
    assert len(bp.plan_first_stage("TP53", None, datasets=True)) == 4
