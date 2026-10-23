"""UI fix set 9: answer structure, readable names, the trust line, item 9.7.

Every control below has a populate-check: an arm that patches the control out
and asserts the defect comes back. An arm that cannot go red is not an arm
(build phase 4.11's lesson), so each property is asserted twice, once with the
control and once without it.
"""

from __future__ import annotations

import re

import pytest

from system_03_search_agent.synthesis import answer_layout, grounding
from system_03_search_agent.synthesis.answer_layout import (
    LEAD_IN_MAX_TITLE_CHARS,
    SENTENCE_TOKEN_LIMIT,
    LeadInPage,
    emphasis_for,
    grounding_input,
    heading_is_supported,
    key_terms,
    lead_in_for,
    lead_in_title,
    name_switched_records,
    parse_synth_layout,
    table_second_cell,
)
from system_03_search_agent.synthesis.disease_names import readable_disease_name
from system_03_search_agent.synthesis.findings import SynthFinding, apply_resolved_disease_names
from system_03_search_agent.synthesis.grounding import (
    GroundedClaim,
    GroundingResult,
    run_grounding_pass,
)
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
    assert line == "Based on 1 source cited, from MedGen"


def test_trust_line_based_on_counts_visible_citations_not_databases() -> None:
    """Fix-plan item 12.8 (2026-09-23). Renamed and re-asserted: this test
    used to lock in the opposite behaviour under the name
    `test_trust_line_counts_databases_not_records`, asserting "Based on 2
    sources" for three distinct citations sharing two databases. That was
    measured to be the defect itself: a reader looking at three clickable
    citations was told there were two. `DISEASE` and `other` both carry a
    MedGen CURIE (one database, two distinct citation_ids); `GENE` carries
    an NCBIGene CURIE. Three chips, two databases. The "Based on" line
    must report the three chips.
    """
    other = _finding(3, "pancreatic cancer", curie="MedGen:C3")
    line = answer_trust_line(
        "ask", [_trust("c-2", "high", "insufficient", "ask")], _claims(DISEASE, other, GENE)
    )
    assert line == "Based on 3 sources cited, all from MedGen"


def _significance(ref_index: int, url: str, *, tool: str = "cypher_query") -> SynthFinding:
    """A record stating one variant's clinical significance, "Pathogenic"."""
    return SynthFinding(
        ref_index=ref_index,
        citation_id=f"c-{ref_index}",
        layer="layer_1_graph" if tool == "cypher_query" else "layer_3_enrichment",
        tool=tool,
        field="clinical_significance",
        field_value="Pathogenic",
        source_url=url,
        entity_type="Variant",
    )


# One variant's records (card 22 last round, V-22-04): its ClinVar variation
# record, a ClinVar condition record for the same variant, and its dbSNP
# page, which is also the link `litvar2_lookup` builds for a LitVar2 record
# with a significance (`tools/litvar2_lookup.py`, `_snp_url_for_rsid`).
CLINVAR_A = _significance(1, "https://www.ncbi.nlm.nih.gov/clinvar/variation/17661")
CLINVAR_B = _significance(2, "https://www.ncbi.nlm.nih.gov/clinvar/RCV000019240")
LITVAR = _significance(3, "https://www.ncbi.nlm.nih.gov/snp/rs80357713", tool="litvar2_lookup")


def test_trust_line_confirmed_still_counts_independent_databases() -> None:
    """The "Confirmed by" line is a claim about corroboration, not about
    how many chips are on screen, so it must keep counting distinct
    databases even where `test_trust_line_based_on_counts_visible_
    citations_not_databases` just proved the "Based on" line does not.
    Three records of one variant state its significance, two in ClinVar
    and one on its dbSNP page (cited by LitVar2): three pages, two
    databases. Reporting "Confirmed by 3" would claim a third, nonexistent,
    independent database agreed.

    Card 22 fix round: rebuilt with records that state the same fact about
    the same variant (last round, V-22-04). The old version marked a claim
    concordant with nothing agreeing with it and still read "Confirmed by 2",
    because the count then ran over every claim in the answer (A-22-02).
    """
    trusts = [_trust("c-1", "high", "concordant", "answer")]
    claims = _claims(CLINVAR_A, CLINVAR_B, LITVAR)
    assert answer_trust_line("answer", trusts, claims) == "Confirmed by 2 independent databases"


def test_trust_line_confirmed_only_on_concordance() -> None:
    trusts = [_trust("c-1", "high", "concordant", "answer")]
    assert answer_trust_line("answer", trusts, _claims(CLINVAR_A, LITVAR)) == (
        "Confirmed by 2 independent databases"
    )
    low = [_trust("c-1", "low", "insufficient", "answer")]
    assert answer_trust_line("answer", low, _claims(CLINVAR_A, LITVAR)) == (
        "Based on 2 sources cited from ClinVar and dbSNP"
    )


def test_trust_line_five_papers_one_database_reads_five_not_one() -> None:
    """The measured field defect (fix-plan item 12.8): five clickable
    papers, all from PubMed (one database), used to read "Based on 1
    source". A reader looking at five citations must be told five.
    """
    papers = [
        _finding(n, f"paper {n}", field="title", entity_type="Publication", curie=f"pubmed:{n}", tool="ncbi_efetch")
        for n in range(1, 6)
    ]
    line = answer_trust_line("answer", [], _claims(*papers))
    assert line == "Based on 5 sources cited, all from MedGen"


def test_trust_line_counts_pages_the_source_list_shows() -> None:
    """Item 12.11 (2026-09-23), a regression from 12.8 the same day.

    Measured on develop: `GERD` showed SOURCES 12 beside "Based on 14
    sources". A paper cited for its title and for its abstract is two
    citation ids and ONE row in the page's source list, which merges by
    exact URL. The line must count what the list shows.
    """
    from dataclasses import replace

    title = _finding(1, "paper one", field="title", entity_type="Publication", tool="ncbi_efetch")
    abstract = replace(
        _finding(2, "paper one abstract", field="abstract", entity_type="Publication", tool="ncbi_efetch"),
        source_url=title.source_url,
    )
    other = _finding(3, "paper two", field="title", entity_type="Publication", tool="ncbi_efetch")
    claims = _claims(title, abstract, other)
    assert len({c.finding.citation_id for c in claims}) == 3, (
        "populate-check: three citation ids, or the old count could not be told apart"
    )
    assert answer_trust_line("answer", [], claims) == "Based on 2 sources cited, all from MedGen"


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
        "('not provided', 'not specified' or 'see cases') are not listed as diseases."
    )
    assert placeholder_links_note(0) is None


# ---------------------------------------------------------------------------
# Item 12.9 (2026-09-23): what each depth's reader is shown. The names are
# imported inside each arm so a revert of the change fails the arm rather
# than the whole module's collection. Mutations run by hand before these
# were kept are named per arm.
# ---------------------------------------------------------------------------

_MARKER = r"\[(\d+)\]"


def _fold_summary(**kwargs) -> str:
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
        [v1, v2, d1],
        {"cq-1": 1, "cq-2": 2, "cq-3": 3},
        "HNF1A",
        1212,
        lambda f: rows[f.citation_id],
        _NAMES,
        **kwargs,
    )
    assert sentence is not None
    return sentence


def test_12_9_the_plain_opening_cites_exactly_what_the_technical_one_does() -> None:
    """Rule 1: everyday nouns and no titles inline, over the same count, the
    same total and the same markers in the same order. Mutation: routing the
    plain depth through the technical branch makes the first assertion red."""
    import re

    plain = _fold_summary(audience_depth="plain_language")
    technical = _fold_summary()
    assert plain == (
        "I found 2 genetic variants related to HNF1A, out of 1212 available [1][2], "
        "linked to 2 conditions [3]."
    ), plain
    assert technical.startswith("Found 2 sequence variant records for HNF1A, of 1212 available")
    assert re.findall(_MARKER, plain) == re.findall(_MARKER, technical) == ["1", "2", "3"]
    for title in ("NM_1", "NM_2", "Maturity-onset diabetes of the young"):
        assert title not in plain, (title, plain)
    # The other three depths the contract accepts keep the technical form.
    for depth in ("researcher", "clinical_brief", "deep_technical"):
        assert _fold_summary(audience_depth=depth) == technical


def test_12_9_a_plain_opening_with_no_subject_says_on_this_topic() -> None:
    from system_03_search_agent.synthesis.answer_layout import answer_summary_sentence

    papers = [
        SynthFinding(
            ref_index=index, citation_id=f"ne-{index}", layer="layer_2_api", tool="ncbi_efetch",
            field="title", field_value=f"Paper title {index}",
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{index}/", entity_type="pubmed",
        )
        for index in (1, 2)
    ]
    slots = {"ne-1": 1, "ne-2": 2}
    assert answer_summary_sentence(
        papers, slots, "", None, lambda f: None, audience_depth="plain_language"
    ) == "I found 2 published papers on this topic [1][2]."
    assert answer_summary_sentence(papers, slots, "", None, lambda f: None) == (
        "Found 2 papers [1][2]."
    )


def test_12_9_plain_nouns_are_everyday_words() -> None:
    from system_03_search_agent.synthesis.answer_layout import plain_noun

    assert plain_noun("Disease", 2) == "conditions"
    assert plain_noun("medgen", 1) == "condition"
    assert plain_noun("pubmed", 1) == "published paper"
    assert plain_noun("Publication", 3) == "published papers"
    assert plain_noun("Clinical trial", 2) == "clinical trials"
    assert plain_noun("SequenceVariant", 2) == "genetic variants"
    assert plain_noun("Gene", 1) == plain_noun("gene", 1) == "gene"
    assert plain_noun("SomethingNew", 2) == "records", "an unknown type is never guessed at"


@pytest.mark.parametrize(
    ("row", "source", "source_id", "expected"),
    [
        # A row field that IS the identifier, verbatim.
        ({"curie": "", "fields": {"name": "t", "nct_id": "NCT00590109"}}, "", "", "NCT00590109"),
        ({"curie": "", "fields": {"rsid": "rs80357906"}}, "", "", "rs80357906"),
        ({"curie": "", "fields": {"pubtator_id": "@GENE_BRCA1"}}, "", "", "@GENE_BRCA1"),
        ({"curie": "", "fields": {"accession": "VCV000017661"}}, "", "", "VCV000017661"),
        # A bare PMID field names its system.
        ({"curie": "", "fields": {"pmid": "33388079"}}, "", "", "PMID:33388079"),
        # A graph row's CURIE.
        ({"curie": "MedGen:C0346153", "fields": {"name": "x"}}, "", "", "MedGen:C0346153"),
        # A live record whose row keeps only its title: the id its citation carries.
        ({"curie": "", "fields": {"title": "t"}}, "pubmed", "33388079", "PMID:33388079"),
        ({"curie": "", "fields": {"symbol": "BRCA2"}}, "gene", "675", "NCBIGene:675"),
        # A MedGen UID is not a concept id, so it is never written "MedGen:".
        ({"curie": "", "fields": {"title": "t"}}, "medgen", "9346", "medgen 9346"),
        # Nothing to read: an empty cell, never a guess.
        ({"curie": "", "fields": {"title": "t"}}, "ncbi_efetch", "unknown", ""),
        (None, "", "", ""),
    ],
)
def test_12_9_the_identifier_is_read_from_the_record(row, source, source_id, expected) -> None:
    """Rule 2's identifier column. Mutation: dropping the citation fallback
    turns the PubMed and gene cases red; dropping `_LAYER2_CURIE_PREFIXES`
    turns them "pubmed 33388079" and "gene 675"."""
    from system_03_search_agent.synthesis.answer_layout import record_identifier

    assert record_identifier(row, source, source_id) == expected


@pytest.mark.parametrize(
    ("entity_type", "fields", "expected"),
    [
        # A trial's status is already its table's mapping column: not twice.
        ("Clinical trial", {"overall_status": "RECRUITING"}, None),
        ("assembly", {"assemblystatus": "Complete Genome"}, ("Status", "Complete Genome")),
        ("gds", {"pdat": "2019/03/15"}, ("Published", "2019")),
        ("Pathogen Detection isolate", {"collection_date": "2013-03-05"}, ("Collected", "2013")),
        ("gds", {"pdat": "not dated"}, None),
        ("Disease", {"name": "x"}, None),
        ("Disease", None, None),
    ],
)
def test_12_9_status_or_year_comes_only_from_the_records_own_fields(
    entity_type, fields, expected
) -> None:
    from system_03_search_agent.synthesis.answer_layout import record_status_or_year

    assert record_status_or_year(entity_type, fields) == expected


def test_12_9_a_trial_keeps_its_status_when_its_group_shows_no_status_column() -> None:
    """When some trials in a group carry no status, the mapping column is
    not on the table, so the status must reach the status column instead of
    being dropped. Mutation: ignoring `mapping_shown` makes this red."""
    from system_03_search_agent.synthesis.answer_layout import record_status_or_year

    fields = {"overall_status": "RECRUITING"}
    assert record_status_or_year("Clinical trial", fields, mapping_shown=False) == (
        "Status",
        "RECRUITING",
    )
    assert record_status_or_year("Clinical trial", fields, mapping_shown=True) is None


def test_12_9_a_plain_label_is_a_title_and_never_a_code() -> None:
    """Rule 2, plain: titles only. Mutation: returning `record_label`
    unchanged makes the two code cases red."""
    from system_03_search_agent.synthesis.answer_layout import plain_record_label

    named = _finding(1, "Familial cancer of breast", curie="MedGen:C0346153")
    assert plain_record_label(named, {"name": "Familial cancer of breast"}, "MedGen:C0346153") == (
        "Familial cancer of breast"
    )
    # No name at all: the label falls back to the CURIE, a code.
    nameless = _finding(2, "MedGen:C0346153", field="curie", curie="MedGen:C0346153")
    assert plain_record_label(nameless, {}, "MedGen:C0346153") == "Condition"
    # G-019: the graph's MeSH name is the identifier wearing a name.
    mesh = _finding(3, "MeSH:D999999", field="curie", entity_type="OntologyClass", curie="MeSH:D999999")
    assert plain_record_label(mesh, {"name": "[MeSH] D999999"}, "MeSH:D999999") == "Medical topic"
    # A real title that happens to carry a short number keeps its words.
    gene = _finding(4, "BRCA1 and 53BP1 in repair", entity_type="Gene", curie="NCBIGene:672")
    assert plain_record_label(gene, {"name": "BRCA1 and 53BP1 in repair"}, "NCBIGene:672") == (
        "BRCA1 and 53BP1 in repair"
    )


# ---------------------------------------------------------------- card 32


def test_the_variant_to_disease_table_names_its_two_sources() -> None:
    """Card 32 (2026-09-25): the note is pinned, code-built and shown only
    under the "Variant-to-disease mapping" table."""
    from system_03_search_agent.synthesis.answer_layout import (
        VARIANT_TO_DISEASE_SOURCE_NOTE,
        variant_to_disease_source_note,
    )

    assert VARIANT_TO_DISEASE_SOURCE_NOTE == (
        "Each row lists the conditions the variant's ClinVar record names; the "
        "record's classification (for example pathogenic, benign or uncertain) "
        "is not shown here. Disease names are MedGen titles looked up from NCBI."
    )
    assert variant_to_disease_source_note("SequenceVariant", True) == VARIANT_TO_DISEASE_SOURCE_NOTE


def test_card23_the_note_never_implies_the_variant_causes_the_disease() -> None:
    """Card 23's fix round, A-23-05. The table lists every variant whose
    ClinVar record names a condition, likely benign and uncertain ones
    included (live HNF1A: c.1011C>T, Likely benign, beside "Maturity-onset
    diabetes of the young"), and the table has no classification column. So
    the line under it must say the classification is not shown, and must
    not call a row an assertion or a cause.

    Red when the line goes back to "ClinVar assertions" (the mutation run),
    when it drops the "not shown" clause, or when the table starts showing a
    variant's classification without the line being revisited."""
    from system_03_search_agent.synthesis.answer_layout import (
        VARIANT_TO_DISEASE_SOURCE_NOTE,
        record_status_or_year,
    )

    note = VARIANT_TO_DISEASE_SOURCE_NOTE.lower()
    assert "classification" in note and "is not shown here" in note
    for word in ("assertion", "cause", "caused", "responsible for", "pathogenic variant"):
        assert word not in note, word

    # "is not shown here" stays true only while the table shows no
    # classification for a variant row, even when a row carries one.
    variant_row = {
        "clinical_significance": "Likely benign",
        "ClinicalSignificance": "Likely benign",
        "germline_classification": "Likely benign",
        "clinvar_condition_ids": ["MedGen:C0342276"],
    }
    assert record_status_or_year("SequenceVariant", variant_row) is None


def test_card23_the_note_makes_no_freshness_claim_about_disease_names() -> None:
    """Card 23's fix round, the owner's wording decision of 2026-10-06
    (J-23-02, A-23-02): a MedGen title is kept for up to a week per server
    process (`disease_names._CACHE_TTL_S`), so a repeated question shows a
    title looked up days earlier with no NCBI call. The line says "looked up
    from NCBI" and never "read live", or any other word promising the name
    was fetched for this answer.

    Red when "read live" comes back (the mutation run)."""
    from system_03_search_agent.synthesis import disease_names
    from system_03_search_agent.synthesis.answer_layout import VARIANT_TO_DISEASE_SOURCE_NOTE

    note = VARIANT_TO_DISEASE_SOURCE_NOTE.lower()
    assert "disease names are medgen titles looked up from ncbi." in note
    # The reason the line carries no timing word: titles are cached.
    assert disease_names._CACHE_TTL_S > 0
    for word in ("live", "real time", "real-time", "current", "today", "just now"):
        assert word not in note, word


def test_card23_query_79_quotes_the_line_that_ships() -> None:
    """Card 23's fix round: the test-queries document is the owner's gate,
    so query 79's expected line must be the shipped text, word for word.
    Card 23's second part (J-23-01, A-23-01) keeps the line directly under
    its table on screen even when the table ends the answer
    (`frontend/src/answerLayout.test.tsx`, `e2e/card23-source-note.spec.ts`),
    so query 79 promises "directly under that table" and never the Notes list.

    Red when the document quotes an older wording (the mutation run), drops
    the placement promise, or sends the line to the Notes list again."""
    from pathlib import Path

    from system_03_search_agent.synthesis.answer_layout import VARIANT_TO_DISEASE_SOURCE_NOTE

    document = Path(__file__).resolve().parents[3] / "testing" / "Test_queries_and_workflows.md"
    text = document.read_text(encoding="utf-8")
    start = text.index("### 79. ")
    end = text.index("\n### ", start + 1)
    section = text[start:end]
    assert f'"{VARIANT_TO_DISEASE_SOURCE_NOTE}"' in section
    assert "directly under that table" in section.lower()
    assert "never in the notes list" in section.lower()
    assert "shows first in the notes list" not in section.lower()


def test_card23_the_screen_finds_the_line_by_the_words_that_ship() -> None:
    """Card 23's second part (J-23-01, A-23-01): the web screen keeps the
    line directly under its table by matching its opening words,
    `VARIANT_TABLE_SOURCE_NOTE_PREFIX` in `frontend/src/hooks/useRunView.ts`,
    because no field on the wire tells it apart from an answer-wide note.

    Red when the backend line is reworded without the frontend prefix (the
    mutation run: the old "Each row is a condition" opening), which would
    send the line back to the Notes list when the table ends the answer."""
    import re
    from pathlib import Path

    from system_03_search_agent.synthesis.answer_layout import VARIANT_TO_DISEASE_SOURCE_NOTE

    hook = Path(__file__).resolve().parents[3] / "frontend" / "src" / "hooks" / "useRunView.ts"
    match = re.search(
        r'export const VARIANT_TABLE_SOURCE_NOTE_PREFIX = "([^"]+)";',
        hook.read_text(encoding="utf-8"),
    )
    assert match is not None
    prefix = match.group(1)
    assert len(prefix) >= 40, prefix
    assert VARIANT_TO_DISEASE_SOURCE_NOTE.startswith(prefix)


@pytest.mark.parametrize(
    ("entity_type", "mapped"),
    [
        ("SequenceVariant", False),  # a variant list with no mapping table shown
        ("Gene", True),  # the gene-to-disease table, a different pairing
        ("Clinical trial", True),
        ("Pathogen Detection isolate", True),
        ("", False),
    ],
)
def test_the_variant_to_disease_note_is_silent_off_its_own_table(
    entity_type: str, mapped: bool
) -> None:
    from system_03_search_agent.synthesis.answer_layout import variant_to_disease_source_note

    assert variant_to_disease_source_note(entity_type, mapped) is None


# ---------------------------------------------------------------------------
# Card 95 (2026-10-05): a token carries at most 20 marker ids, so a lead
# sentence writing 35 markers showed 21 to 35 as raw bracketed text. Red on
# the old code: the sentence carried 35 markers.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("depth", ["researcher", "plain"])
def test_the_lead_sentence_never_writes_more_markers_than_a_token_can_carry(depth: str) -> None:
    import re

    from system_03_search_agent.synthesis.answer_layout import (
        MAX_SUMMARY_MARKERS,
        answer_summary_sentence,
    )

    findings = [_fold_finding(n, "SequenceVariant", f"ClinVar:{n}", f"NM_{n}") for n in range(1, 36)]
    slots = {f.citation_id: f.ref_index for f in findings}
    sentence = answer_summary_sentence(
        findings, slots, "BRCA1", None, lambda f: None, audience_depth=depth
    )
    assert sentence is not None
    markers = [int(n) for n in re.findall(r"\[(\d+)\]", sentence)]
    assert 0 < len(markers) <= MAX_SUMMARY_MARKERS == 20, sentence
    assert "35" in sentence, "the count still tells the truth about all records"


# ---------------------------------------------------------------------------
# Card 17 (2026-10-15): a sentence that switches papers names its paper.
# Every record below is neutral and built here, never a test question.
# ---------------------------------------------------------------------------

_LAKE_TITLE = "Alpine lakes and glacier melt."
_CORE_TITLE = "Lake sediment cores from northern valleys."


def _row(
    ref: int,
    page: int,
    field: str,
    value: str,
    *,
    entity_type: str = "Publication",
    host: str = "https://pubmed.ncbi.nlm.nih.gov",
) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=f"{host}/{page}/",
        entity_type=entity_type,
    )


def _result(*pairs: tuple[str, list[tuple[SynthFinding, str | None]]]) -> GroundingResult:
    """A grounded result built by hand: each pair is a sentence and the
    (finding, evidence quote) of each marker in it, in order."""
    claims = [
        GroundedClaim(claim_text=sentence, finding=finding, evidence_quote=quote)
        for sentence, cited in pairs
        for finding, quote in cited
    ]
    sentences = tuple(sentence for sentence, _ in pairs)
    return GroundingResult(
        narrative=" ".join(sentences),
        claims=claims,
        stripped_count=3,
        refused=False,
        sentences=sentences,
        sentence_origins=tuple(range(len(sentences))),
    )


_LAKE = _row(1, 1, "title", _LAKE_TITLE)
_LAKE_TEXT = _row(2, 1, "abstract", "Glacier melt feeds the high lakes each summer.")
_CORE = _row(3, 2, "title", _CORE_TITLE)
_CORE_TEXT = _row(4, 2, "abstract", "Cores show valleys filled with fine silt.")
_FIRST = ("Glacier melt feeds the high lakes [1].", [(_LAKE, None)])
_SWITCH = ("Valleys like these hold fine silt [2].", [(_CORE, "Cores show valleys filled with fine silt")])


def test_a_switched_sentence_on_one_shared_word_gets_the_lead_in_and_nothing_else_changes() -> None:
    """Fires: reworded, other page, one shared title word, no short form."""
    before = _result(_FIRST, _SWITCH)
    after, named = name_switched_records(before, [_LAKE, _LAKE_TEXT, _CORE, _CORE_TEXT])

    assert named == 1
    assert after.sentences[0] == before.sentences[0]
    assert after.sentences[1] == f'From the paper "{_CORE_TITLE[:-1]}": ' + before.sentences[1]
    assert after.claims == before.claims
    assert after.stripped_count == before.stripped_count == 3
    assert after.sentence_origins == before.sentence_origins
    assert after.narrative == " ".join(after.sentences)


def test_a_pass_that_does_nothing_leaves_the_sentence_bare() -> None:
    """Mutation proof: the sentence of the first test has no lead-in until
    the pass runs. Mutation that turns the first test red: make
    `name_switched_records` return its input."""
    before = _result(_FIRST, _SWITCH)
    assert not before.sentences[1].startswith("From the")
    after, _ = name_switched_records(before, [_LAKE, _CORE])
    assert after.sentences[1].startswith("From the paper")


def test_the_first_sentence_of_the_prose_never_gets_a_lead_in() -> None:
    """There is no sentence above it for a pointing word to be misread against."""
    reworded_first = ("Glacier melt feeds the high lakes [1].", [(_LAKE, "Glacier melt feeds the high lakes")])
    after, named = name_switched_records(_result(reworded_first, _FIRST), [_LAKE, _CORE])

    assert named == 0
    assert after.sentences[0] == reworded_first[0]


def test_a_move_from_a_papers_title_to_its_abstract_is_no_switch() -> None:
    """One page under two refs: the reader is already in that paper."""
    title_sentence = ("Lakes and glacier melt [1].", [(_LAKE, None)])
    same_page = ("A glacier feeds the valleys [2].", [(_LAKE_TEXT, "A glacier feeds the valleys")])
    after, named = name_switched_records(_result(title_sentence, same_page), [_LAKE, _LAKE_TEXT])

    assert named == 0
    assert after.sentences[1] == same_page[0]


def test_two_shared_title_words_or_a_defined_short_form_name_the_paper_already() -> None:
    two_words = (
        "Sediment cores from valleys hold fine silt [2].",
        [(_CORE, "Cores show valleys filled with fine silt")],
    )
    _, named = name_switched_records(_result(_FIRST, two_words), [_LAKE, _CORE])
    assert named == 0

    # One cited page anchored by two words and another by one: the sentence
    # already names a paper, so it is not led in.
    glacial = _row(5, 4, "title", "Glacial history.")
    mixed = (
        "Sediment cores hold silt [2] and the ice is glacial [5].",
        [(_CORE, "Cores show valleys filled with fine silt"), (glacial, "The ice is glacial")],
    )
    _, named_mixed = name_switched_records(_result(_FIRST, mixed), [_LAKE, _CORE, glacial])
    assert named_mixed == 0

    copd_title = _row(5, 3, "title", "Chronic obstructive pulmonary disease.")
    copd_text = _row(
        6, 3, "abstract", "Chronic obstructive pulmonary disease (COPD) is common in older adults."
    )
    short_form = (
        "COPD is a disease of older adults [5].",
        [(copd_title, "Chronic obstructive pulmonary disease")],
    )
    findings = [_LAKE, copd_title, copd_text]
    _, named_short = name_switched_records(_result(_FIRST, short_form), findings)
    assert named_short == 0

    one_word = (
        "A disease of older adults [5].",
        [(copd_title, "Chronic obstructive pulmonary disease")],
    )
    _, named_one = name_switched_records(_result(_FIRST, one_word), findings)
    assert named_one == 1


def test_a_copied_sentence_gets_no_lead_in() -> None:
    copied = ("Valleys like these hold fine silt [2].", [(_CORE, None)])
    after, named = name_switched_records(_result(_FIRST, copied), [_LAKE, _CORE])

    assert named == 0
    assert after.sentences[1] == copied[0]


def test_a_translated_title_is_quoted_without_brackets_and_markers_stay_the_sentences_own() -> None:
    assert lead_in_title("[Translated title].") == "Translated title"
    assert lead_in_title('What\'s "new" now?') == "What's 'new' now?"
    bracketed = _row(3, 2, "title", "[Valley cores].")
    after, named = name_switched_records(_result(_FIRST, _SWITCH_FOR(bracketed)), [_LAKE, bracketed])

    assert named == 1
    assert after.sentences[1].startswith('From the paper "Valley cores": Valleys')
    assert re.findall(r"\[[^\]]*\]", after.sentences[1]) == ["[2]"]


def _SWITCH_FOR(finding: SynthFinding) -> tuple[str, list[tuple[SynthFinding, str | None]]]:
    return ("Valleys like these hold fine silt [2].", [(finding, "Valleys hold fine silt")])


def test_a_long_title_is_cut_at_a_word_boundary_with_the_cut_mark_and_one_at_the_cap_is_whole() -> None:
    whole = "a" * (LEAD_IN_MAX_TITLE_CHARS - 1) + "b"
    assert lead_in_title(whole) == whole
    words = " ".join(["valley"] * 40)
    cut = lead_in_title(words)
    assert cut.endswith("…")
    assert len(cut) <= LEAD_IN_MAX_TITLE_CHARS
    assert cut[:-1].endswith("valley")
    exact = " ".join(["valley"] * 22)[:LEAD_IN_MAX_TITLE_CHARS].rstrip()
    assert lead_in_title(exact) == exact


def test_a_marker_digit_is_not_a_shared_word_with_a_title_that_carries_the_number() -> None:
    """A title ending "Older Than 18 Years" must not share the digit of a marker."""
    numbered = _row(3, 2, "title", "Results in people older than 18 years.")
    sentence = ("Valleys hold fine silt [18].", [(numbered, "Valleys hold fine silt")])
    after, named = name_switched_records(_result(_FIRST, sentence), [_LAKE, numbered])

    assert named == 0
    assert after.sentences[1] == sentence[0]


def test_a_trial_reads_the_trial_and_another_record_reads_its_noun() -> None:
    trial = _row(3, 2, "name", "Valley survey", entity_type="ClinicalTrial", host="https://clinicaltrials.gov/study")
    assert lead_in_for([LeadInPage("Valley survey", "ClinicalTrial")]).startswith('From the trial "')
    assert lead_in_for([LeadInPage("Aspergillus", "Disease")]).startswith('From the condition record "')
    assert lead_in_for([LeadInPage("Aspergillus", "")]).startswith('From the record "')
    after, named = name_switched_records(_result(_FIRST, _SWITCH_FOR(trial)), [_LAKE, trial])
    assert named == 1
    assert after.sentences[1].startswith('From the trial "Valley survey": ')


def test_two_switched_to_pages_are_both_named_in_display_order() -> None:
    third = _row(5, 4, "title", "Glacial history.")
    both = (
        "Valleys hold fine silt [2] and the ice is glacial [3].",
        [(_CORE, "Cores show valleys filled with fine silt"), (third, "The ice is glacial")],
    )
    after, named = name_switched_records(_result(_FIRST, both), [_LAKE, _CORE, third])

    assert named == 1
    assert after.sentences[1].startswith(
        f'From the papers "{_CORE_TITLE[:-1]}" and "Glacial history": '
    )


# ---------------------------------------------------------------------------
# Card 17 fix round (2026-10-16): findings A-17-01, A-17-02, A-17-08, J-17-01,
# J-17-02, J-17-04, J-17-05, J-17-06, J-17-08, J-17-12.
# ---------------------------------------------------------------------------


def test_the_sentence_that_opens_the_answer_never_gets_a_lead_in() -> None:
    """J-17-08a. With the reading order given, the lead sentence is first and
    has nothing above it; the same pair in the writer's order does fire."""
    before = _result(_FIRST, _SWITCH)
    findings = [_LAKE, _CORE]

    _, in_writer_order = name_switched_records(before, findings)
    after, led = name_switched_records(before, findings, reading_order=[1, 0])

    assert in_writer_order == 1
    assert led == 0
    assert after.sentences == before.sentences


def test_the_sentence_above_is_the_one_the_reader_sees_above() -> None:
    """A-17-01: a sentence left out of the prose is not 'the sentence above'.
    Sentences 0 and 1 cite the same page; 2 is read after 1 in writer order
    (same page, no switch) and after 0 once 1 is left out (a switch)."""
    same_page_text = _row(5, 1, "abstract", "Valleys hold fine silt too.")
    middle = ("Lakes freeze in winter [5].", [(same_page_text, None)])
    last = ("Valleys like these hold fine silt [2].", [(_CORE, "Cores show valleys filled with fine silt")])
    before = _result(
        _FIRST,
        middle,
        last,
    )
    findings = [_LAKE, same_page_text, _CORE]

    _, as_written = name_switched_records(before, findings)
    after, in_reading_order = name_switched_records(before, findings, reading_order=[0, 2])

    assert as_written == 1  # 1 is page 1, 2 is page 2: a switch even so
    assert in_reading_order == 1
    assert after.sentences[2].startswith('From the paper "Lake sediment cores from northern valleys": ')

    # The judge's shape: the middle sentence shares the switched-to page, so in
    # writer order the last one reads as "same paper" and ships bare.
    shares_page = ("Valley floors [3].", [(_CORE, None)])
    judge = _result(_FIRST, shares_page, _SWITCH)
    _, bare = name_switched_records(judge, [_LAKE, _CORE])
    after_judge, named = name_switched_records(judge, [_LAKE, _CORE], reading_order=[0, 2])
    assert bare == 0
    assert named == 1
    assert after_judge.sentences[2].startswith("From the paper")


def test_a_title_another_listed_paper_shares_carries_the_year_or_says_another() -> None:
    """A-17-02 and A-17-08: two papers with one title cannot be told apart by
    the title, so the lead-in adds the year when a record carries it and
    otherwise says 'another paper titled'."""
    twin = _row(6, 4, "title", _LAKE_TITLE)
    findings = [_LAKE, _LAKE_TEXT, twin]
    switched = ("Glacier retreat exposes bare rock [6].", [(twin, "Glacier retreat exposes bare rock")])
    before = _result(("Valleys hold fine silt [2].", [(_CORE, None)]), switched)

    no_year, named = name_switched_records(before, [*findings, _CORE])
    assert named == 1
    assert no_year.sentences[1].startswith(
        'From another paper titled "Alpine lakes and glacier melt": Glacier retreat'
    )

    dated = _row(7, 4, "pubdate", "2021 Mar 4")
    with_year, named = name_switched_records(before, [*findings, _CORE, dated])
    assert named == 1
    assert with_year.sentences[1].startswith(
        'From the paper "Alpine lakes and glacier melt" (2021): Glacier retreat'
    )

    # A title no other paper shares is quoted alone, year or not.
    other_title = _row(8, 4, "title", "Another study of glaciers.")
    alone, _ = name_switched_records(before, [_LAKE, _CORE, other_title, dated])
    assert alone.sentences[1].startswith('From the paper "Another study of glaciers": ')


def test_a_blank_or_punctuation_only_title_reads_another_record() -> None:
    """J-17-01: a page whose title finding is empty, or only punctuation, and
    whose name finding carries the shared word, is not quoted as ''."""
    for blank in ("", "   ", "[.]", ".", "--", "[;]", "( )"):
        empty_title = _row(3, 2, "title", blank)
        name = _row(4, 2, "name", "Valleys of canyons")
        sentence = ("Valleys like these hold fine silt [3].", [(empty_title, "Valleys hold fine silt")])
        after, named = name_switched_records(_result(_FIRST, sentence), [_LAKE, empty_title, name])
        assert named == 1, blank
        assert after.sentences[1].startswith("From the paper "), blank
        assert '""' not in after.sentences[1], blank
    assert lead_in_for([LeadInPage("[.]", "Publication")]) == "From another record: "
    assert lead_in_for([LeadInPage("", "")]) == "From another record: "
    assert lead_in_title("--") == "" and lead_in_title("[;]") == ""


def test_the_title_quoted_is_the_first_usable_label_of_the_page() -> None:
    """J-17-04, mutant 2: the quoted title is the first label finding with
    text, not the last."""
    first = _row(3, 2, "title", "Valley survey.")
    second = _row(4, 2, "name", "Valley census")
    sentence = ("Valleys hold fine silt [3].", [(first, "Valleys hold fine silt")])
    after, named = name_switched_records(_result(_FIRST, sentence), [_LAKE, first, second])
    assert named == 1
    assert after.sentences[1].startswith('From the paper "Valley survey": ')

    blank_first = _row(3, 2, "title", "[.]")
    after, _ = name_switched_records(
        _result(_FIRST, ("Valleys hold fine silt [3].", [(blank_first, "Valleys hold fine silt")])),
        [_LAKE, blank_first, second],
    )
    assert after.sentences[1].startswith('From the paper "Valley census": ')


def test_a_sentence_with_one_copied_and_one_reworded_claim_is_reworded() -> None:
    """J-17-04, mutant 1: the 'reworded' condition is any claim, not all."""
    mixed = (
        "Valleys hold fine silt [2] and the ice is glacial [5].",
        [(_CORE, "Cores show valleys filled with fine silt"), (_row(5, 4, "abstract", "The ice is glacial."), None)],
    )
    _, named = name_switched_records(_result(_FIRST, mixed), [_LAKE, _CORE])
    assert named == 1


def test_a_lead_in_over_mixed_record_types_says_records() -> None:
    """J-17-04, mutant 3."""
    lead = lead_in_for([LeadInPage("A", "Publication"), LeadInPage("B", "ClinicalTrial")])
    assert lead == 'From the records "A" and "B": '
    assert lead_in_for([LeadInPage("A", "Publication"), LeadInPage("B", "PubMed")]) == (
        'From the papers "A" and "B": '
    )


def test_a_short_form_several_papers_define_does_not_name_one_of_them() -> None:
    """J-17-12: 'COPD' written in a sentence names no paper when two papers in
    the answer define it; it does when only the cited paper does."""
    copd_title = _row(5, 3, "title", "Chronic obstructive pulmonary disease.")
    copd_text = _row(6, 3, "abstract", "Chronic obstructive pulmonary disease (COPD) is common.")
    twin_title = _row(7, 5, "title", "Chronic obstructive pulmonary disease in children.")
    twin_text = _row(8, 5, "abstract", "Chronic obstructive pulmonary disease (COPD) is rare in children.")
    sentence = ("COPD is a disease of older adults [5].", [(copd_title, "Chronic obstructive pulmonary disease")])

    _, alone = name_switched_records(_result(_FIRST, sentence), [_LAKE, copd_title, copd_text])
    _, with_twin = name_switched_records(
        _result(_FIRST, sentence), [_LAKE, copd_title, copd_text, twin_title, twin_text]
    )

    assert alone == 0
    assert with_twin == 1


def test_a_sentence_citing_a_titled_page_and_an_unlabelled_page_names_both() -> None:
    """J-17-05: the verdict comes from the unlabelled record, so the lead-in
    says 'and another record' instead of crediting the paper alone."""
    variant = _row(5, 6, "clinical_significance", "Benign", entity_type="SequenceVariant")
    both = (
        "Valleys like these hold fine silt and the variant is benign [2] [5].",
        [(_CORE, "Cores show valleys filled with fine silt"), (variant, "Benign")],
    )
    after, named = name_switched_records(_result(_FIRST, both), [_LAKE, _CORE, variant])
    assert named == 1
    assert after.sentences[1].startswith(f'From the paper "{_CORE_TITLE[:-1]}" and another record: ')


@pytest.mark.parametrize(
    ("entity_type", "expected"),
    [
        ("PubMed", "paper"),
        ("pubmed", "paper"),
        ("Publication", "paper"),
        ("Article", "paper"),
        ("PMC", "paper"),
        ("ClinicalTrial", "trial"),
        ("Clinical trial", "trial"),
        ("Disease", "condition record"),
        ("MedGen", "condition record"),
        ("medgen", "condition record"),
        ("Gene", "gene record"),
        ("SequenceVariant", "variant record"),
        ("ClinVar", "variant record"),
        ("LiteratureVariant", "variant record"),
        ("Literature entity", "literature record"),
        ("LiteratureEntity", "literature record"),
        ("Cellular component", "cell component record"),
        ("Biological process", "biological process record"),
        ("OMIM", "OMIM record"),
        ("omim", "OMIM record"),
        ("OntologyClass", "medical topic record"),
        ("Protein", "protein record"),
        ("ChemicalEntity", "chemical record"),
        ("Unknown", "record"),
        ("", "record"),
    ],
)
def test_the_record_noun_reads_naturally_and_ignores_case(entity_type: str, expected: str) -> None:
    """J-17-06: no 'literature index entry record', no 'part of the cell record',
    and 'PubMed' and 'pubmed' read the same."""
    assert lead_in_for([LeadInPage("X", entity_type)]).startswith(f'From the {expected} "X"')


def test_a_lead_in_never_cuts_the_end_of_a_sentence_at_the_token_limit() -> None:
    """J-17-08b. `sentence_token` keeps 1000 characters. A sentence that fits
    bare must still end whole with its lead-in, by a shorter title, then the
    title-less lead-in, then no lead-in."""
    long_title = _row(3, 2, "title", "Valleys " + "of canyons " * 30)

    def led(length: int) -> str:
        body = ("Valleys hold fine silt " + "x" * length)[:length]
        body = body[: length - 5] + " [3]."
        sentence = (body, [(long_title, "Valleys hold fine silt")])
        after, _ = name_switched_records(_result(_FIRST, sentence), [_LAKE, long_title])
        return after.sentences[1]

    for length in (700, 800, 900, 950, 975):
        text = led(length)
        assert len(text) + 1 <= SENTENCE_TOKEN_LIMIT, (length, len(text))
        assert text.endswith("[3].")
    assert led(700).startswith("From the paper ")
    assert led(975).startswith("From another record: ") or led(975).startswith("From the paper ")
    # Too long for any lead-in: left bare, whole.
    bare = led(995)
    assert not bare.startswith("From")
    assert bare.endswith("[3].")


# ---------------------------------------------------------------- card 30


def _card30_finding(*, layer: str, entity_type: str, field: str, value: str):
    from system_03_search_agent.synthesis.findings import SynthFinding

    return SynthFinding(
        ref_index=1,
        citation_id="c-1",
        layer=layer,
        tool="t",
        field=field,
        field_value=value,
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
        entity_type=entity_type,
    )


def test_card30_a_graph_variant_list_says_classification_was_not_retrieved() -> None:
    """Graph variant names beside live ClinVar titles: the pinned line."""
    from system_03_search_agent.synthesis.answer_layout import (
        VARIANT_CLASSIFICATION_NOTE,
        variant_classification_note,
    )

    findings = [
        _card30_finding(
            layer="layer_1_graph", entity_type="SequenceVariant", field="name", value="c.1A>G"
        ),
        _card30_finding(
            layer="layer_2_api", entity_type="ClinVar record", field="title", value="a title"
        ),
    ]
    assert variant_classification_note(findings) == VARIANT_CLASSIFICATION_NOTE
    assert VARIANT_CLASSIFICATION_NOTE == (
        "ClinVar's classification of these variants (for example pathogenic, benign or "
        "uncertain) was not retrieved, so this list does not say which are pathogenic. "
        "Each variant's ClinVar record shows its classification."
    )


def test_card30_no_line_when_a_shown_record_gives_a_classification() -> None:
    """An rs334 shaped answer cites dbSNP's clinical significance and lists no
    graph variant; and a graph variant list that does cite a classification
    field needs no line either."""
    from system_03_search_agent.synthesis.answer_layout import variant_classification_note

    rs334 = [
        _card30_finding(
            layer="layer_2_api",
            entity_type="Variant record",
            field="clinical_significance",
            value="Pathogenic",
        ),
        _card30_finding(
            layer="layer_3_enrichment", entity_type="Variant record", field="name", value="HbS"
        ),
    ]
    assert variant_classification_note(rs334) is None
    classified = [
        _card30_finding(
            layer="layer_1_graph", entity_type="SequenceVariant", field="name", value="c.1A>G"
        ),
        _card30_finding(
            layer="layer_2_api",
            entity_type="ClinVar record",
            field="germline_classification",
            value="Pathogenic",
        ),
    ]
    assert variant_classification_note(classified) is None
    assert variant_classification_note([]) is None


# Card 38, slice B: an ortholog gene row carries its organism.
def _ortholog_finding(entity_type: str = "Gene"):
    from system_03_search_agent.synthesis.findings import SynthFinding

    return SynthFinding(
        citation_id="NCBIGene:100009292",
        entity_type=entity_type,
        field="name",
        field_value="tumor protein p53",
        source_url="https://www.ncbi.nlm.nih.gov/gene/100009292",
        curie="NCBIGene:100009292",
        ref_index=1,
        layer=1,
        tool="cypher_query",
    )


def test_ortholog_row_shows_its_organism() -> None:
    from system_03_search_agent.synthesis.answer_layout import (
        plain_record_label,
        record_status_or_year,
    )

    fields = {"name": "tumor protein p53", "organism": "Oryctolagus cuniculus"}
    assert record_status_or_year("Gene", fields) == ("Organism", "Oryctolagus cuniculus")
    assert (
        plain_record_label(_ortholog_finding(), fields)
        == "tumor protein p53 (Oryctolagus cuniculus)"
    )


def test_gene_rows_without_an_organism_and_other_row_types_are_unchanged() -> None:
    from system_03_search_agent.synthesis.answer_layout import (
        plain_record_label,
        record_status_or_year,
    )

    plain = {"name": "tumor protein p53"}
    assert record_status_or_year("Gene", plain) is None
    assert plain_record_label(_ortholog_finding(), plain) == "tumor protein p53"
    # The Layer 2 `gene` type is a different key, and a list or dict value
    # is never rendered.
    layer2 = {"name": "tumor protein p53", "organism": "Homo sapiens"}
    assert record_status_or_year("gene", layer2) is None
    assert plain_record_label(_ortholog_finding("gene"), layer2) == "tumor protein p53"
    for odd in (["Mus musculus"], {"a": "b"}, 7, ""):
        odd_fields = {"name": "tumor protein p53", "organism": odd}
        assert record_status_or_year("Gene", odd_fields) is None
        assert plain_record_label(_ortholog_finding(), odd_fields) == "tumor protein p53"


def _count_finding(index: int, entity_type: str, value: str) -> SynthFinding:
    return SynthFinding(
        ref_index=index, citation_id=f"c-{index}", layer="layer_1_graph", tool="cypher_query",
        field="name", field_value=value, source_url=f"https://example.org/{index}/",
        entity_type=entity_type, name_resolved=True,
    )


def test_card_131_count_line_counts_papers_and_keeps_other_names() -> None:
    from system_03_search_agent.synthesis.answer_layout import answer_summary_sentence

    papers = [
        _count_finding(1, "PubMed", "BRCA1: An Endocrine and Metabolic Regulator."),
        _count_finding(2, "PubMed", "EXO1 protects BRCA1-deficient cells from lesions."),
    ]
    text = answer_summary_sentence(papers, {"c-1": 1, "c-2": 2}, "BRCA1", None, lambda _f: None)
    assert text == "Found 2 papers for BRCA1 [1][2].", text

    mixed = [
        _count_finding(1, "Gene", "BRCA1"),
        _count_finding(2, "Article", "A paper title."),
        _count_finding(3, "Disease", "Breast cancer"),
    ]
    slots = {"c-1": 1, "c-2": 2, "c-3": 3}
    text = answer_summary_sentence(mixed, slots, "BRCA1", None, lambda _f: None)
    assert text == (
        "Found 1 gene record, 1 paper and 1 disease record for BRCA1 [2]: BRCA1 [1] and Breast cancer [3]."
    ), text
    assert "A paper title" not in text
    plain = answer_summary_sentence(mixed, slots, "BRCA1", None, lambda _f: None, audience_depth="plain_language")
    assert plain.index("gene") < plain.index("paper") < plain.index("condition"), plain


def test_card_131_a_type_already_ending_in_record_takes_no_second_record() -> None:
    from system_03_search_agent.synthesis.answer_layout import answer_summary_sentence

    rows = [_count_finding(1, "VariantRecord", "rs334"), _count_finding(2, "VariantRecord", "rs6025")]
    text = answer_summary_sentence(rows, {"c-1": 1, "c-2": 2}, "rs334 and rs6025", None, lambda _f: None)
    assert text == "Found 2 variant records for rs334 and rs6025: rs334 [1] and rs6025 [2].", text
    assert "record records" not in text
