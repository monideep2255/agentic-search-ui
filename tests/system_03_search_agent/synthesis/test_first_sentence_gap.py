"""Build phase 8.7, T-8.7-01: the opening line says what the records do not
give, and only once code has checked that none of them gives it.

The owner's words: "The first sentence answers what I asked, or tells me the
records do not say." When the loop has been told what kind of fact the
question asks for (`AskedField`, supplied from a decision already made, never
read off the question), and no record in the answer carries it, the
code-built line ends by saying so. A record that does carry it keeps the line
silent about a gap, so the line can never claim an absence its own records
disprove.
"""

from __future__ import annotations

from system_03_search_agent.synthesis.answer_layout import (
    AskedField,
    answer_summary_sentence,
    records_lack_field,
)
from system_03_search_agent.synthesis.findings import (
    CLINICAL_FEATURES_FIELD,
    NO_CLINICAL_FEATURES_PREFIX,
    SynthFinding,
)

ORGANISM = AskedField(label="the organism", field_names=("organism",))
FEATURES = AskedField(label="clinical features", field_names=(CLINICAL_FEATURES_FIELD,))


def _gene(ref: int) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value="tumor protein p53",
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{7000 + ref}",
        entity_type="Gene",
        curie=f"NCBIGene:{7000 + ref}",
    )


GENES = [_gene(ref) for ref in range(1, 4)]
SLOTS = {finding.citation_id: finding.ref_index for finding in GENES}


def _rows(organism_on: int | None = None):
    def row_for(finding: SynthFinding) -> dict:
        fields = {"name": finding.field_value, "symbol": "TP53"}
        if organism_on == finding.ref_index:
            fields["organism"] = "Mus musculus"
        return {"fields": fields}

    return row_for


def test_the_line_names_what_no_record_gives() -> None:
    sentence = answer_summary_sentence(
        GENES, SLOTS, "TP53", 715, _rows(), asked_field=ORGANISM, all_findings=GENES
    )
    assert sentence == (
        "Found 3 gene records for TP53, of 715 available: tumor protein p53 [1], "
        "tumor protein p53 [2] and tumor protein p53 [3], none of which gives the organism."
    ), sentence


def test_the_plain_language_line_names_the_same_gap() -> None:
    sentence = answer_summary_sentence(
        GENES,
        SLOTS,
        "TP53",
        715,
        _rows(),
        audience_depth="plain_language",
        asked_field=ORGANISM,
        all_findings=GENES,
    )
    assert sentence == (
        "I found 3 genes related to TP53, out of 715 available [1][2][3], "
        "none of which gives the organism."
    ), sentence


def test_one_record_reads_in_the_singular() -> None:
    one = GENES[:1]
    sentence = answer_summary_sentence(
        one, {"c-1": 1}, "TP53", None, _rows(), asked_field=ORGANISM, all_findings=one
    )
    assert sentence == (
        "Found 1 gene record for TP53: tumor protein p53 [1], which does not give the organism."
    ), sentence


def test_one_record_carrying_the_field_keeps_the_gap_unsaid() -> None:
    """The loop may name the field; only code decides the records lack it."""
    sentence = answer_summary_sentence(
        GENES, SLOTS, "TP53", 715, _rows(organism_on=2), asked_field=ORGANISM, all_findings=GENES
    )
    assert sentence is not None
    assert "organism" not in sentence, sentence


def test_no_asked_field_leaves_todays_line_byte_for_byte() -> None:
    with_none = answer_summary_sentence(GENES, SLOTS, "TP53", 715, _rows())
    assert with_none == (
        "Found 3 gene records for TP53, of 715 available: tumor protein p53 [1], "
        "tumor protein p53 [2] and tumor protein p53 [3]."
    ), with_none


def _disease() -> SynthFinding:
    return SynthFinding(
        ref_index=1,
        citation_id="c-1",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="title",
        field_value="Marfan syndrome",
        source_url="https://www.ncbi.nlm.nih.gov/medgen/44792",
        entity_type="Disease",
    )


def _feature(ref: int, value: str) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=CLINICAL_FEATURES_FIELD,
        field_value=value,
        source_url="https://www.ncbi.nlm.nih.gov/medgen/44792",
        entity_type="Disease",
    )


def test_a_real_feature_anywhere_in_the_answer_keeps_the_gap_unsaid() -> None:
    disease = _disease()
    feature = _feature(2, "Arachnodactyly")
    assert not records_lack_field([disease], [disease, feature], lambda _f: None, FEATURES)


def test_the_lists_none_statement_is_not_a_feature() -> None:
    disease = _disease()
    none_stated = _feature(2, f"{NO_CLINICAL_FEATURES_PREFIX}Marfan syndrome")
    assert records_lack_field([disease], [disease, none_stated], lambda _f: None, FEATURES)
    sentence = answer_summary_sentence(
        [disease],
        {"c-1": 1},
        "Marfan syndrome",
        None,
        lambda _f: None,
        asked_field=FEATURES,
        all_findings=[disease, none_stated],
    )
    assert sentence == (
        "Found 1 disease record for Marfan syndrome: Marfan syndrome [1], "
        "which does not give clinical features."
    ), sentence
