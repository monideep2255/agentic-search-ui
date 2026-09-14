"""UI fix set 9: answer structure, readable names, the trust line, item 9.7.

Every control below has a populate-check: an arm that patches the control out
and asserts the defect comes back. An arm that cannot go red is not an arm
(build phase 4.11's lesson), so each property is asserted twice, once with the
control and once without it.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis import answer_layout, grounding
from system_03_search_agent.synthesis.answer_layout import (
    emphasis_for,
    grounding_input,
    heading_is_supported,
    key_terms,
    parse_synth_layout,
    table_second_cell,
)
from system_03_search_agent.synthesis.disease_names import readable_disease_name
from system_03_search_agent.synthesis.findings import SynthFinding, apply_resolved_disease_names
from system_03_search_agent.synthesis.grounding import GroundedClaim, run_grounding_pass
from system_03_search_agent.synthesis.trust import ClaimTrust, answer_trust_line


def _finding(
    ref_index: int,
    value: str,
    *,
    field: str = "name",
    entity_type: str = "Disease",
    curie: str = "",
    tool: str = "cypher_query",
) -> SynthFinding:
    return SynthFinding(
        ref_index=ref_index,
        citation_id=f"c-{ref_index}",
        layer="layer_1_graph",
        tool=tool,
        field=field,
        field_value=value,
        source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{ref_index}",
        entity_type=entity_type,
        curie=curie,
    )


GENE = _finding(1, "BRCA1", field="symbol", entity_type="Gene", curie="NCBIGene:672")
DISEASE = _finding(2, "familial cancer of breast", curie="MedGen:C0346153")


# ---------------------------------------------------------------- item 9.7


EXACT_DEFECT = "BRCA1 (gene symbol BRCA1 [1]. These are familial cancer of breast [2]."
MODEL_SHAPED = (
    "BRCA1 (gene symbol BRCA1 [1]) is associated with the following diseases. "
    "These are familial cancer of breast [2]."
)


@pytest.mark.parametrize("narrative", [EXACT_DEFECT, MODEL_SHAPED])
def test_the_garbled_opening_never_ships(narrative: str) -> None:
    result = run_grounding_pass(narrative, [GENE, DISEASE], core_ask_required=False)
    assert "(gene symbol" not in result.narrative, result.narrative
    assert not result.narrative.startswith("These"), result.narrative
    assert result.narrative == "", result.narrative


def test_without_the_bracket_rule_the_fragment_ships(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grounding, "_is_unbalanced_fragment", lambda _text: False)
    result = run_grounding_pass(EXACT_DEFECT, [GENE, DISEASE], core_ask_required=False)
    assert "BRCA1 (gene symbol BRCA1 [1]." in result.narrative, result.narrative


def test_without_the_pronoun_rule_the_subjectless_opener_ships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(grounding, "_opens_on_bare_pronoun", lambda _text: False)
    result = run_grounding_pass(EXACT_DEFECT, [GENE, DISEASE], core_ask_required=False)
    assert result.narrative.startswith("These are familial cancer of breast"), result.narrative


def test_a_pronoun_after_a_surviving_sentence_is_kept() -> None:
    narrative = "The gene symbol is BRCA1 [1]. These are familial cancer of breast [2]."
    result = run_grounding_pass(narrative, [GENE, DISEASE], core_ask_required=False)
    assert result.narrative == narrative, result.narrative
    assert result.sentence_origins == (0, 1)


def test_a_balanced_parenthesis_is_kept() -> None:
    # The parenthesis opens and closes inside one grounded clause, so the
    # bracket rule has nothing to object to. (A first version of this control
    # used "is linked to", a word no finding carries, so the clause was
    # stripped by the content check before the bracket rule was ever reached:
    # the control was wrong, not the rule.)
    narrative = "The disease familial cancer of breast (MedGen:C0346153) [2]."
    result = run_grounding_pass(narrative, [GENE, DISEASE], core_ask_required=False)
    # The pass renumbers survivors densely, so finding 2 prints as [1].
    assert result.narrative == narrative.replace("[2]", "[1]"), result.narrative


def test_sentence_origins_skip_a_dropped_sentence() -> None:
    narrative = (
        "The gene symbol is BRCA1 [1]. BRCA1 cures scurvy [2]. "
        "The disease is familial cancer of breast [2]."
    )
    result = run_grounding_pass(narrative, [GENE, DISEASE], core_ask_required=False)
    assert result.sentence_origins == (0, 2)
    assert " ".join(result.sentences) == result.narrative


# ---------------------------------------------------------------- layout


def test_layout_reads_headings_paragraphs_and_bullets() -> None:
    blocks = parse_synth_layout(
        "Summary one [1].\nstill one [2].\n\n## Disease associations\n"
        "Para two [2].\n\n- bullet a [1]\n- bullet b [2]"
    )
    assert blocks == [
        ("paragraph", "Summary one [1]. still one [2]."),
        ("heading", "Disease associations"),
        ("paragraph", "Para two [2]."),
        ("paragraph", "bullet a [1]. bullet b [2]."),
    ]


def test_grounding_input_maps_every_sentence_to_its_paragraph() -> None:
    layout = grounding_input(
        parse_synth_layout("A [1]. B [2]\n\n## Topic\nC [1].\n\nD [2]")
    )
    assert layout.narrative == "A [1]. B [2]. C [1]. D [2]."
    assert layout.sentence_paragraph == (0, 0, 1, 2)
    assert layout.heading_before == {1: "Topic"}


def test_a_reply_with_no_structure_is_unchanged_prose() -> None:
    text = "BRCA1 is associated with familial cancer of breast [2]."
    assert grounding_input(parse_synth_layout(text)).narrative == text


@pytest.mark.parametrize(
    ("heading", "supported"),
    [
        ("Disease associations", True),
        ("Familial cancer of breast", True),
        ("Overview", True),
        ("Treatment options", False),
        ("BRCA1 causes Marfan syndrome", False),
        ("Disease associations [1]", False),
        ("A heading that is far too long to be a short topic label at all", False),
    ],
)
def test_heading_support(heading: str, supported: bool) -> None:
    question = "Which diseases are associated with BRCA1?"
    assert heading_is_supported(heading, [GENE, DISEASE], question) is supported


def test_without_the_vocabulary_a_topic_word_heading_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(answer_layout, "HEADING_VOCABULARY", frozenset())
    assert not heading_is_supported("Overview", [GENE, DISEASE], "")


def test_emphasis_names_only_the_runs_own_terms() -> None:
    terms = key_terms([GENE, DISEASE], ["BRCA1"])
    text = "BRCA1 is associated with Familial cancer of breast [2]. "
    assert emphasis_for(text, terms) == ["Familial cancer of breast", "BRCA1"]
    assert emphasis_for("Nothing named here [1]. ", terms) == []


def test_a_curie_fallback_value_is_never_a_key_term() -> None:
    fallback = SynthFinding(
        ref_index=3, citation_id="c-3", layer="layer_1_graph", tool="cypher_query",
        field="curie", field_value="MedGen:C9", source_url="https://www.ncbi.nlm.nih.gov/medgen/9",
        curie_fallback=True, curie="MedGen:C9",
    )
    assert key_terms([fallback], []) == []


# The real row shape read live from the graph for ClinVar:1179956 (GCK), which
# listed as its URL: every field ahead of `source_url` trips the vocabulary-
# artifact check, so `_pick_representative_field` chose the URL.
_URL_LISTED_ROW = {
    "id": "ClinVar:1179956",
    "name": "NM_000162.5(GCK):c.363+318G>A",
    "xrefs": "",
    "source": "ClinVar",
    "agent_type": "",
    "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
    "knowledge_level": "",
}


def _url_listed_finding() -> SynthFinding:
    return SynthFinding(
        ref_index=9, citation_id="c-9", layer="layer_1_graph", tool="cypher_query",
        field="source_url", field_value=_URL_LISTED_ROW["source_url"],
        source_url=_URL_LISTED_ROW["source_url"], entity_type="SequenceVariant",
        curie="ClinVar:1179956",
    )


def test_the_real_row_that_listed_a_url_picks_the_url_upstream() -> None:
    """Populate-check: the defect is real on this exact row, so the label arm
    below is not passing on a row that never produced a URL."""
    from system_03_search_agent.core.graph import _pick_representative_field

    assert _pick_representative_field(_URL_LISTED_ROW)[0] == "source_url"


def test_a_list_label_is_the_records_name_never_its_url() -> None:
    from system_03_search_agent.synthesis.answer_layout import record_label

    assert record_label(_url_listed_finding(), _URL_LISTED_ROW) == "NM_000162.5(GCK):c.363+318G>A"


def test_a_list_label_falls_back_to_the_record_id_then_never_a_url() -> None:
    from system_03_search_agent.synthesis.answer_layout import record_label

    no_name = dict(_URL_LISTED_ROW, name="")
    assert record_label(_url_listed_finding(), no_name) == "ClinVar:1179956"
    url_only = SynthFinding(
        ref_index=9, citation_id="c-9", layer="layer_1_graph", tool="cypher_query",
        field="source_url", field_value="https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
    )
    assert record_label(url_only, {"source_url": url_only.field_value, "name": "https://x"}) == "c-9"


def test_a_clean_name_finding_keeps_its_own_value() -> None:
    from system_03_search_agent.synthesis.answer_layout import record_label

    assert record_label(DISEASE, None) == "familial cancer of breast"


def test_the_table_second_cell_is_read_from_the_record() -> None:
    """Variant-to-disease detail (2026-09-14): the second cell is the
    resolved MedGen titles of the row's folded condition CURIEs, never a
    CURIE; a placeholder title is left out; a row with no fold has no cell
    (None) while a row whose links were all placeholders has an EMPTY one."""
    names = {
        "MedGen:C0342276": "Maturity-onset diabetes of the young",
        "MedGen:C3661900": "not provided",
    }
    row = {"name": "x", "clinvar_condition_ids": ["MedGen:C0342276", "MedGen:C3661900"]}
    assert table_second_cell("SequenceVariant", row, names) == "Maturity-onset diabetes of the young"
    assert table_second_cell("SequenceVariant", {"name": "x"}) is None
    only_placeholder = {"name": "x", "clinvar_condition_ids": ["MedGen:C3661900"]}
    assert table_second_cell("SequenceVariant", only_placeholder, names) == ""
    unresolved = {"name": "x", "clinvar_condition_ids": ["MedGen:C9"]}
    assert table_second_cell("SequenceVariant", unresolved, names) == ""
    assert "MedGen" not in (table_second_cell("SequenceVariant", unresolved, names) or "")
    assert table_second_cell("Disease", {"clinvar_condition_ids": ["MedGen:C0342276"]}) is None
    gene_row = {"name": "glucokinase", "medgen_condition_ids": ["MedGen:C0342276"]}
    assert table_second_cell("Gene", gene_row, names) == "Maturity-onset diabetes of the young"


# ---------------------------------------------------------------- item 9.8


@pytest.mark.parametrize(
    ("title", "readable"),
    [
        (
            "Breast-ovarian cancer, familial, susceptibility to, 1",
            "Familial breast-ovarian cancer susceptibility 1",
        ),
        ("Pancreatic cancer, susceptibility to, 4", "Pancreatic cancer susceptibility 4"),
        ("Fanconi anemia, complementation group S", "Fanconi anemia complementation group S"),
        ("Familial cancer of breast", "Familial cancer of breast"),
        ("MODY, type 3", "MODY type 3"),
        ("Cancer, not otherwise specified", "Cancer, not otherwise specified"),
    ],
)
def test_readable_disease_names(title: str, readable: str) -> None:
    assert readable_disease_name(title) == readable


def test_a_resolved_name_is_rewritten_in_reading_order_and_grounds() -> None:
    fallback = SynthFinding(
        ref_index=1, citation_id="c-1", layer="layer_1_graph", tool="cypher_query",
        field="curie", field_value="MedGen:C2676676", source_url="https://www.ncbi.nlm.nih.gov/medgen/C2676676",
        curie_fallback=True, curie="MedGen:C2676676", entity_type="Disease",
    )
    [resolved] = apply_resolved_disease_names(
        [fallback], {"MedGen:C2676676": "Breast-ovarian cancer, familial, susceptibility to, 1"}
    )
    assert resolved.field_value == "Familial breast-ovarian cancer susceptibility 1"
    assert "susceptibility to, 1" not in resolved.field_value
    result = run_grounding_pass(
        "BRCA1 is associated with familial breast-ovarian cancer susceptibility 1 [1].",
        [resolved],
        core_ask_required=False,
        question="Which diseases are associated with BRCA1?",
    )
    assert result.claims, result


# ---------------------------------------------------------------- item 9.9


def _trust(citation_id: str, tier: str, triangulation: str, outcome: str) -> ClaimTrust:
    return ClaimTrust(citation_id, tier, True, triangulation, outcome)  # type: ignore[arg-type]


def _claims(*findings: SynthFinding) -> list[GroundedClaim]:
    return [GroundedClaim(claim_text=f.field_value, finding=f) for f in findings]


def test_trust_line_single_source_not_confirmed() -> None:
    line = answer_trust_line("ask", [_trust("c-2", "high", "insufficient", "ask")], _claims(DISEASE))
    assert line == "Based on 1 source, not yet confirmed"


def test_trust_line_counts_databases_not_records() -> None:
    other = _finding(3, "pancreatic cancer", curie="MedGen:C3")
    line = answer_trust_line(
        "ask", [_trust("c-2", "high", "insufficient", "ask")], _claims(DISEASE, other, GENE)
    )
    assert line == "Based on 2 sources, not yet confirmed"


def test_trust_line_confirmed_only_on_concordance() -> None:
    trusts = [_trust("c-2", "high", "concordant", "answer")]
    assert answer_trust_line("answer", trusts, _claims(DISEASE, GENE)) == (
        "Confirmed by 2 independent sources"
    )
    low = [_trust("c-2", "low", "insufficient", "answer")]
    assert answer_trust_line("answer", low, _claims(DISEASE, GENE)) == "Based on 2 sources"


def test_trust_line_flag_and_refuse() -> None:
    assert answer_trust_line("flag", [], _claims(DISEASE)) == "Sources disagree on at least one claim"
    assert answer_trust_line("refuse", [], _claims(DISEASE)) is None
    assert answer_trust_line("answer", [], []) is None


# ---------------------------------------------------------------------------
# Variant-to-disease detail (2026-09-14): the fold clause of the summary
# sentence and the placeholder count under the table.
# Mutations run by hand before these were kept: removing the `anchors`
# branch from `answer_summary_sentence` drops the "linked to" clause (red);
# counting placeholders as titles in `condition_titles` makes the disease
# count 3 (red); dropping `placeholder_link_count`'s accumulation returns 0
# (red).
# ---------------------------------------------------------------------------


def _fold_finding(ref: int, entity_type: str, curie: str, value: str, *, resolved: bool = False) -> SynthFinding:
    return SynthFinding(
        ref_index=ref, citation_id=f"cq-{ref}", layer="layer_1_graph", tool="cypher_query",
        field="name", field_value=value, source_url=f"https://www.ncbi.nlm.nih.gov/x/{ref}",
        entity_type=entity_type, curie=curie, name_resolved=resolved, call_id="cq",
    )


_NAMES = {
    "MedGen:C0342276": "Maturity-onset diabetes of the young",
    "MedGen:C3888631": "Monogenic diabetes",
    "MedGen:C3661900": "not provided",
}


def test_the_summary_counts_variants_and_their_distinct_linked_diseases() -> None:
    from system_03_search_agent.synthesis.answer_layout import answer_summary_sentence

    v1 = _fold_finding(1, "SequenceVariant", "ClinVar:1", "NM_1")
    v2 = _fold_finding(2, "SequenceVariant", "ClinVar:2", "NM_2")
    d1 = _fold_finding(3, "Disease", "MedGen:C0342276", "Maturity-onset diabetes of the young", resolved=True)
    rows = {
        "cq-1": {"fields": {"name": "NM_1", "clinvar_condition_ids": ["MedGen:C0342276", "MedGen:C3661900"]}},
        "cq-2": {"fields": {"name": "NM_2", "clinvar_condition_ids": ["MedGen:C3888631", "MedGen:C0342276"]}},
        "cq-3": {"fields": {"name": "OMIM"}},
    }
    sentence = answer_summary_sentence(
        [v1, v2, d1], {"cq-1": 1, "cq-2": 2, "cq-3": 3}, "HNF1A", 1212, lambda f: rows[f.citation_id], _NAMES
    )
    assert sentence is not None
    assert sentence.startswith("Found 2 sequence variant records for HNF1A, of 1212 available"), sentence
    assert "linked to 2 diseases: Maturity-onset diabetes of the young [3] and 1 other." in sentence, sentence
    assert "disease records" not in sentence, "a linked disease is not counted as a record of its own"
    assert "MedGen:" not in sentence


def test_the_placeholder_count_is_the_real_number_of_excluded_links() -> None:
    from system_03_search_agent.synthesis.answer_layout import (
        placeholder_link_count,
        placeholder_links_note,
    )

    rows = [
        ("SequenceVariant", {"clinvar_condition_ids": ["MedGen:C0342276", "MedGen:C3661900"]}),
        ("SequenceVariant", {"clinvar_condition_ids": ["MedGen:C3661900"]}),
        ("Disease", {"name": "OMIM"}),
    ]
    assert placeholder_link_count(rows, _NAMES) == 2
    assert placeholder_links_note(2) == (
        "2 variant links to ClinVar placeholder conditions "
        "('not provided', 'not specified' or 'see cases') are not listed."
    )
    assert placeholder_links_note(0) is None
