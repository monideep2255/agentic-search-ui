"""Build phase 8.7, card 2: the opening line says what the records do not
give, and only when the product positively knows it.

The owner's words: "The first sentence answers what I asked, or tells me the
records do not say." When the loop has been told what kind of fact the
question asks for (`AskedField`, supplied from a decision already made, never
read off the question) the code-built line may end by saying the records do
not give it.

Fix round (F-8.7-J01, J02, A02, A03, A13), from the user's chair: a confident
wrong absence is worse than saying nothing. The clause is said only when the
field's source was searched, every search finished, the source read each
counted record and found none, and no record shown in the answer (row,
definition or citation) carries anything that might state the field.
Anything else leaves the line byte for byte as it is with no asked field.
Each finding below has an arm that fails on the code before the fix round.
"""

from __future__ import annotations

from system_03_search_agent.core.graph import _asked_field
from system_03_search_agent.synthesis.answer_layout import (
    answer_summary_sentence,
    records_lack_field,
)
from system_03_search_agent.synthesis.findings import (
    CLINICAL_FEATURES_FIELD,
    NO_CLINICAL_FEATURES_PREFIX,
    SynthFinding,
)

#: What the loop passes when `think.asks_features` picked "asks_features"
#: and every search finished, from the loop's own builder.
FEATURES = _asked_field(True, [])
MEDGEN_TIMEOUT = {
    "tool": "ncbi_efetch",
    "layer": "layer_2_ncbi",
    "reason": "search: timed out",
    "kind": "timeout",
    "source": "medgen",
}
MARFAN_DEFINITION = (
    "A systemic disorder of connective tissue with ocular features (ectopia "
    "lentis), skeletal features (arachnodactyly, tall stature) and aortic root "
    "dilatation."
)


def _url(concept: int) -> str:
    return f"https://www.ncbi.nlm.nih.gov/medgen/{concept}"


def _disease(ref: int, title: str, concept: int) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="title",
        field_value=title,
        source_url=_url(concept),
        entity_type="Disease",
    )


def _lists_none(ref: int, title: str, concept: int) -> SynthFinding:
    """The code-built statement that a record was read and lists none."""
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=CLINICAL_FEATURES_FIELD,
        field_value=f"{NO_CLINICAL_FEATURES_PREFIX}{title}",
        source_url=_url(concept),
        entity_type="Disease",
    )


def _rows(extra: dict[str, dict] | None = None):
    """Each finding's row as the loop dumps it: a MedGen title row carries
    its title and semantic type, a "lists none" row its statement, a total of
    zero and the disease's title. `extra` adds fields by citation id."""

    def row_for(finding: SynthFinding) -> dict:
        if finding.field == CLINICAL_FEATURES_FIELD:
            fields = {
                CLINICAL_FEATURES_FIELD: finding.field_value,
                "clinical_features_total": 0,
                "disease_title": finding.field_value.removeprefix(NO_CLINICAL_FEATURES_PREFIX),
            }
        else:
            fields = {finding.field: finding.field_value, "semantictype": "Disease or Syndrome"}
        fields.update((extra or {}).get(finding.citation_id, {}))
        return {"fields": fields}

    return row_for


MARFAN = _disease(1, "Marfan syndrome", 44792)
MARFAN_NONE = _lists_none(2, "Marfan syndrome", 44792)
LOEYS = _disease(3, "Loeys-Dietz syndrome", 335277)
LOEYS_NONE = _lists_none(4, "Loeys-Dietz syndrome", 335277)
WITHOUT_CLAUSE = "Found 1 disease record for Marfan syndrome: Marfan syndrome [1]."
PLAIN_WITHOUT_CLAUSE = "I found 1 condition related to Marfan syndrome [1]."


def _line(
    counted: list[SynthFinding],
    shown: list[SynthFinding],
    *,
    asked=FEATURES,
    rows=None,
    depth: str = "researcher",
    subject: str = "Marfan syndrome",
    condition_names: dict[str, str | None] | None = None,
) -> str | None:
    return answer_summary_sentence(
        counted,
        {f.citation_id: f.ref_index for f in shown},
        subject,
        None,
        rows or _rows(),
        condition_names,
        audience_depth=depth,
        asked_field=asked,
        all_findings=shown,
    )


# ---------------------------------------------------------------------------
# The clause, when the absence is known.
# ---------------------------------------------------------------------------


def test_a_record_read_and_listing_none_gets_the_clause_naming_its_record() -> None:
    assert _line([MARFAN], [MARFAN, MARFAN_NONE]) == (
        "Found 1 disease record for Marfan syndrome: Marfan syndrome [1], "
        "and its MedGen record lists no clinical features."
    )


def test_two_records_read_and_listing_none_read_in_the_plural() -> None:
    shown = [MARFAN, MARFAN_NONE, LOEYS, LOEYS_NONE]
    assert _line([MARFAN, LOEYS], shown, subject="") == (
        "Found 2 disease records: Marfan syndrome [1] and Loeys-Dietz syndrome [3], "
        "and none of their MedGen records lists clinical features."
    )


def test_no_asked_field_leaves_todays_line_byte_for_byte() -> None:
    assert _line([MARFAN], [MARFAN, MARFAN_NONE], asked=None) == WITHOUT_CLAUSE


def test_a_real_feature_anywhere_in_the_answer_keeps_the_clause_unsaid() -> None:
    feature = SynthFinding(
        ref_index=5,
        citation_id="c-5",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=CLINICAL_FEATURES_FIELD,
        field_value="Arachnodactyly",
        source_url=_url(335277),
        entity_type="Disease",
    )
    assert not records_lack_field([MARFAN], [MARFAN, MARFAN_NONE, feature], _rows(), FEATURES)


# ---------------------------------------------------------------------------
# F-8.7-J01: the record's own definition may describe the features.
# ---------------------------------------------------------------------------


def test_j01_a_definition_on_the_record_row_keeps_the_clause_unsaid() -> None:
    rows = _rows({"c-1": {"definition": MARFAN_DEFINITION}})
    assert _line([MARFAN], [MARFAN, MARFAN_NONE], rows=rows) == WITHOUT_CLAUSE


def test_j01_a_definition_finding_keeps_the_clause_unsaid() -> None:
    definition = SynthFinding(
        ref_index=5,
        citation_id="c-5",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="definition",
        field_value=MARFAN_DEFINITION,
        source_url=_url(44792),
        entity_type="Disease",
    )
    assert _line([MARFAN], [MARFAN, MARFAN_NONE, definition]) == WITHOUT_CLAUSE


def test_j01_an_abstract_shown_beside_the_record_keeps_the_clause_unsaid() -> None:
    abstract = SynthFinding(
        ref_index=5,
        citation_id="c-5",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="abstract",
        field_value="Patients present with lens dislocation and tall stature.",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        entity_type="Article",
    )
    assert _line([MARFAN], [MARFAN, MARFAN_NONE, abstract]) == WITHOUT_CLAUSE


# ---------------------------------------------------------------------------
# F-8.7-J02 and F-8.7-A02: features never read, or the search not finished.
# ---------------------------------------------------------------------------


def test_j02_a_record_whose_features_were_never_read_gets_no_clause() -> None:
    """The unreadable `conceptmeta` case, and a graph-only Disease row: no
    "lists none" statement exists, so nothing is known."""
    assert _line([MARFAN], [MARFAN]) == WITHOUT_CLAUSE
    assert _line([MARFAN], [MARFAN], depth="plain_language") == PLAIN_WITHOUT_CLAUSE


def test_j02_every_counted_record_needs_its_own_lists_none_statement() -> None:
    assert _line([MARFAN, LOEYS], [MARFAN, MARFAN_NONE, LOEYS], subject="") == (
        "Found 2 disease records: Marfan syndrome [1] and Loeys-Dietz syndrome [3]."
    )


def test_a02_a_search_that_did_not_finish_means_no_clause() -> None:
    asked = _asked_field(True, [MEDGEN_TIMEOUT])
    assert asked is not None and asked.every_search_finished is False
    assert _line([MARFAN], [MARFAN, MARFAN_NONE], asked=asked) == WITHOUT_CLAUSE
    assert (
        _line([MARFAN], [MARFAN, MARFAN_NONE], asked=asked, depth="plain_language")
        == PLAIN_WITHOUT_CLAUSE
    )


def test_the_loop_says_every_search_finished_only_when_none_failed() -> None:
    assert _asked_field(True, []).every_search_finished is True  # type: ignore[union-attr]
    assert _asked_field(False, []) is None


# ---------------------------------------------------------------------------
# F-8.7-A03: a record row beside it gives the features in another field.
# ---------------------------------------------------------------------------


def _gene(ref: int) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value="NCBIGene:2200",
        source_url="https://www.ncbi.nlm.nih.gov/gene/2200",
        entity_type="Gene",
        curie="NCBIGene:2200",
    )


FEATURE_WORDS = {
    "description": "Marfan syndrome features include tall stature and lens dislocation"
}


def test_a03_a_counted_gene_row_whose_description_gives_them_keeps_the_clause_unsaid() -> None:
    gene = _gene(5)
    rows = _rows({"c-5": FEATURE_WORDS})
    assert _line([MARFAN, gene], [MARFAN, MARFAN_NONE, gene], rows=rows) == (
        "Found 1 disease record and 1 gene record for Marfan syndrome: "
        "Marfan syndrome [1] and NCBIGene:2200 [5]."
    )


def test_a03_a_shown_record_that_is_not_counted_still_counts() -> None:
    gene = _gene(5)
    rows = _rows({"c-5": FEATURE_WORDS})
    assert not records_lack_field([MARFAN], [MARFAN, MARFAN_NONE, gene], rows, FEATURES)


# ---------------------------------------------------------------------------
# F-8.7-A13: after "linked to 3 conditions" the clause read as if the
# conditions had no symptoms.
# ---------------------------------------------------------------------------


def _variant_case(depth: str) -> str | None:
    variant = SynthFinding(
        ref_index=1,
        citation_id="c-1",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value="NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs)",
        source_url="https://www.ncbi.nlm.nih.gov/snp/rs80357906",
        entity_type="SequenceVariant",
        curie="dbSNP:rs80357906",
    )
    linked = ["MedGen:C0677776", "MedGen:C2676676", "MedGen:C0346153"]
    # Each linked condition's MedGen record read and listing none, so only
    # the counted record's own state can hold the clause back.
    shown = [variant] + [
        _lists_none(index, f"condition {index}", 100 + index) for index in range(2, 5)
    ]
    rows = _rows({"c-1": {"clinvar_condition_ids": linked}})
    names = {curie: f"condition {index}" for index, curie in enumerate(linked, start=2)}
    return _line([variant], shown, rows=rows, depth=depth, subject="", condition_names=names)


def test_a13_a_variant_linked_to_conditions_gets_no_clause_in_either_depth() -> None:
    researcher = _variant_case("researcher")
    plain = _variant_case("plain_language")
    assert researcher == (
        "Found 1 sequence variant record: NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs) [1], "
        "linked to 3 diseases."
    ), researcher
    assert plain == "I found 1 genetic variant on this topic [1], linked to 3 conditions.", plain


def test_a13_the_plain_language_clause_says_it_is_the_record_that_lists_none() -> None:
    plain = _line([MARFAN], [MARFAN, MARFAN_NONE], depth="plain_language")
    assert plain == (
        "I found 1 condition related to Marfan syndrome [1], "
        "and its MedGen record lists no clinical features."
    ), plain
    assert "does not give" not in plain and "none of which" not in plain
