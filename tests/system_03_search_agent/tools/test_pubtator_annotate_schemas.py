"""Tests for pubtator_annotate_schemas.py (T-3.3-03).

No network. Covers, for the input side, both `mode` branches validating
through both `PubtatorAnnotateInput.model_validate` and
`PubtatorAnnotateInput(**payload)` (the exact construction the premise gate's
own `_run` helper uses), `extra="forbid"` rejecting an unknown key on each
branch, the `entity_lookup.query` `min_length: 1` boundary (F-3.3-02), the
`entity_lookup.limit` 1-20 boundary, the `annotate_publications.pmids`
maxItems/maxLength boundaries, an invalid `mode` value, and a missing
required field on each branch. For the output side: every maxLength and
maxItems cap actually enforced (not just declared) on the top-level model
and all three nested item models (`PubtatorEntity`, `PubtatorAnnotation`,
`PubtatorPublication`), the two required fields (`status`, `mode`), the
`status` enum, `extra="forbid"` at every level, the additive
`pmids_not_found` field (F-3.3-01: defaults to `[]`, accepts real PMID
strings, bounded the same as the input's own `pmids`), the additive
`PubtatorEntity.matched_on` field (F-3.3-A-01/F-3.3-A-02/F-3.3-A-03,
fix round 3: defaults to `None`, accepts a real value, `max_length=200`),
`pmids.min_length=1` rejecting an empty list (F-3.3-A-06, fix round 3),
`NCBI_PUBTATOR_RECORD_URL_PATTERN` accepting a real
`pubmed.ncbi.nlm.nih.gov` record URL while rejecting the PubTator3 API
fetch host and two right-host-wrong-kind-of-record NCBI URLs, the
additive `PubtatorEntity.source_url` field and
`NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN` (F-3.3-A-05, fix round 4:
accepts a real gene/mesh record URL, rejects a pubmed/snp/fetch-host
URL), the additive `PubtatorPublication.total_annotations` field
(F-3.3-A-12, fix round 4: defaults to 0, accepts a count above
`len(annotations)`, rejects a negative value), and the additive
`PubtatorAnnotateOutput.fields_withheld` field (F-3.3-J-04, fix round 4:
defaults to `None`, mirrors `Litvar2LookupOutput.fields_withheld`'s own
20-item/150-char bounds exactly).

What this file deliberately does NOT cover, per `goal-contracts`'s "a verify
surface must state its own coverage": how `pubtator_annotate.py` (T-3.3-05)
parses a live PubTator3 response into these shapes, or the withhold-not-
truncate behavior at the tool layer. That is `test_pubtator_annotate.py`'s
job, not this file's; this file only proves the shapes themselves are
correctly typed and bounded.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.pubtator_annotate_schemas import (
    NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN,
    NCBI_PUBTATOR_RECORD_URL_PATTERN,
    PubtatorAnnotateInput,
    PubtatorAnnotateOutput,
    PubtatorAnnotation,
    PubtatorEntity,
    PubtatorPublication,
)

# ---------------------------------------------------------------------------
# Input: both mode branches, from the spec's documented shape.
# ---------------------------------------------------------------------------


def test_entity_lookup_validates_via_model_validate() -> None:
    validated = PubtatorAnnotateInput.model_validate(
        {"mode": "entity_lookup", "query": "BRCA1", "limit": 5}
    )
    assert validated.root.mode == "entity_lookup"
    assert validated.root.query == "BRCA1"
    assert validated.root.limit == 5


def test_entity_lookup_validates_via_kwargs_construction() -> None:
    """The exact construction the premise gate's `_run` helper uses."""
    validated = PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    assert validated.root.query == "BRCA1"


def test_entity_lookup_limit_defaults_to_ten_when_omitted() -> None:
    validated = PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1")
    assert validated.root.limit == 10


def test_annotate_publications_validates_via_kwargs_construction() -> None:
    validated = PubtatorAnnotateInput(
        mode="annotate_publications", pmids=["34083286", "999999999999"]
    )
    assert validated.root.mode == "annotate_publications"
    assert validated.root.pmids == ["34083286", "999999999999"]


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="relation_lookup", query="BRCA1")


def test_entity_lookup_missing_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup")


def test_annotate_publications_missing_pmids_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="annotate_publications")


def test_entity_lookup_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", bogus="x")


def test_annotate_publications_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["1"], bogus="x")


# ---------------------------------------------------------------------------
# Input boundaries.
# ---------------------------------------------------------------------------


def test_entity_lookup_empty_query_is_rejected() -> None:
    """F-3.3-02: minLength: 1 closes the empty-query path at the schema layer."""
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup", query="")


def test_entity_lookup_query_at_max_length_validates() -> None:
    validated = PubtatorAnnotateInput(mode="entity_lookup", query="Q" * 200)
    assert len(validated.root.query) == 200


def test_entity_lookup_query_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup", query="Q" * 201)


def test_entity_lookup_limit_below_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=0)


def test_entity_lookup_limit_above_twenty_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=21)


def test_entity_lookup_limit_at_twenty_validates() -> None:
    validated = PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=20)
    assert validated.root.limit == 20


def test_annotate_publications_pmids_empty_list_is_rejected() -> None:
    """F-3.3-A-06: min_length=1 mirrors query's own minLength for the same
    reason (an empty pmids list reaches the live API and lands on F-3.3-02's
    undocumented bare-array error shape).
    """
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="annotate_publications", pmids=[])


def test_annotate_publications_pmids_empty_list_is_rejected_via_model_validate() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput.model_validate({"mode": "annotate_publications", "pmids": []})


def test_annotate_publications_pmids_at_max_items_validates() -> None:
    validated = PubtatorAnnotateInput(
        mode="annotate_publications", pmids=[str(i) for i in range(20)]
    )
    assert len(validated.root.pmids) == 20


def test_annotate_publications_pmids_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(
            mode="annotate_publications", pmids=[str(i) for i in range(21)]
        )


def test_annotate_publications_pmid_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["1" * 16])


def test_annotate_publications_pmid_at_max_length_validates() -> None:
    validated = PubtatorAnnotateInput(mode="annotate_publications", pmids=["1" * 15])
    assert validated.root.pmids == ["1" * 15]


# ---------------------------------------------------------------------------
# Output: required fields, status enum, extra="forbid".
# ---------------------------------------------------------------------------


def test_output_minimal_required_fields_validates() -> None:
    output = PubtatorAnnotateOutput(status="ok", mode="entity_lookup")
    assert output.entities == []
    assert output.publications == []
    assert output.error is None
    assert output.pmids_not_found == []


def test_output_missing_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(mode="entity_lookup")


def test_output_missing_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(status="ok")


def test_output_invalid_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(status="partial", mode="entity_lookup")


@pytest.mark.parametrize("status", ["ok", "empty", "error"])
def test_output_status_enum_accepts_every_documented_value(status: str) -> None:
    output = PubtatorAnnotateOutput(status=status, mode="entity_lookup")
    assert output.status == status


def test_output_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(status="ok", mode="entity_lookup", bogus="x")


def test_output_mode_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(status="ok", mode="m" * 26)


def test_output_error_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(status="error", mode="entity_lookup", error="e" * 501)


# ---------------------------------------------------------------------------
# Output: pmids_not_found (F-3.3-01, additive).
# ---------------------------------------------------------------------------


def test_pmids_not_found_defaults_to_empty_list() -> None:
    output = PubtatorAnnotateOutput(status="ok", mode="annotate_publications")
    assert output.pmids_not_found == []


def test_pmids_not_found_accepts_real_pmid_strings() -> None:
    output = PubtatorAnnotateOutput(
        status="ok", mode="annotate_publications", pmids_not_found=["999999999999"]
    )
    assert output.pmids_not_found == ["999999999999"]


def test_pmids_not_found_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok",
            mode="annotate_publications",
            pmids_not_found=[str(i) for i in range(21)],
        )


def test_pmids_not_found_item_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok", mode="annotate_publications", pmids_not_found=["1" * 16]
        )


# ---------------------------------------------------------------------------
# Output: nested item models.
# ---------------------------------------------------------------------------


def test_entity_all_fields_are_optional() -> None:
    entity = PubtatorEntity()
    assert entity.pubtator_id is None
    assert entity.name is None


def test_entity_name_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorEntity(name="n" * 101)


def test_entity_description_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorEntity(description="d" * 301)


def test_entity_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorEntity(bogus="x")


# ---------------------------------------------------------------------------
# matched_on: additive, F-3.3-A-01/F-3.3-A-02/F-3.3-A-03 (fix round 3).
# ---------------------------------------------------------------------------


def test_entity_matched_on_defaults_to_none() -> None:
    entity = PubtatorEntity()
    assert entity.matched_on is None


def test_entity_matched_on_accepts_a_real_value() -> None:
    entity = PubtatorEntity(matched_on="Matched on name <m>BRCA1</m>")
    assert entity.matched_on == "Matched on name <m>BRCA1</m>"


def test_entity_matched_on_max_length_boundary() -> None:
    ok = PubtatorEntity(matched_on="m" * 200)
    assert len(ok.matched_on) == 200
    with pytest.raises(ValidationError):
        PubtatorEntity(matched_on="m" * 201)


def test_output_entities_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok", mode="entity_lookup", entities=[PubtatorEntity()] * 21
        )


def test_annotation_all_fields_are_optional() -> None:
    annotation = PubtatorAnnotation()
    assert annotation.type is None
    assert annotation.valid is None


def test_annotation_identifier_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotation(identifier="i" * 61)


def test_annotation_normalized_id_accepts_string_or_null() -> None:
    a = PubtatorAnnotation(normalized_id="672")
    assert a.normalized_id == "672"
    b = PubtatorAnnotation(normalized_id=None)
    assert b.normalized_id is None


def test_annotation_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotation(bogus="x")


def test_publication_annotations_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(annotations=[PubtatorAnnotation()] * 101)


def test_publication_pmid_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(pmid="1" * 16)


def test_publication_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(bogus="x")


def test_output_publications_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok",
            mode="annotate_publications",
            publications=[PubtatorPublication()] * 21,
        )


# ---------------------------------------------------------------------------
# source_url: host-pinned pattern, on the model field and standalone.
# ---------------------------------------------------------------------------


def test_publication_source_url_accepts_pubmed_host() -> None:
    pub = PubtatorPublication(
        pmid="34083286", source_url="https://pubmed.ncbi.nlm.nih.gov/34083286/"
    )
    assert pub.source_url == "https://pubmed.ncbi.nlm.nih.gov/34083286/"


def test_publication_source_url_rejects_the_fetch_host() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(
            pmid="34083286",
            source_url="https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?pmids=34083286",
        )


def test_publication_source_url_rejects_a_wrong_kind_of_ncbi_record() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(pmid="34083286", source_url="https://www.ncbi.nlm.nih.gov/gene/7157")


@pytest.mark.parametrize(
    "url",
    [
        "https://pubmed.ncbi.nlm.nih.gov/34083286/",
        "https://pubmed.ncbi.nlm.nih.gov/32942285/",
    ],
)
def test_ncbi_pubtator_record_url_pattern_accepts_pubmed_urls(url: str) -> None:
    assert re.match(NCBI_PUBTATOR_RECORD_URL_PATTERN, url) is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/?query=BRCA1",
        "https://www.ncbi.nlm.nih.gov/gene/7157",
        "https://www.ncbi.nlm.nih.gov/snp/rs334",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=34083286",
    ],
)
def test_ncbi_pubtator_record_url_pattern_rejects_non_pubmed_urls(url: str) -> None:
    assert re.match(NCBI_PUBTATOR_RECORD_URL_PATTERN, url) is None


# ---------------------------------------------------------------------------
# PubtatorEntity.source_url: F-3.3-A-05, additive, deliberately partial
# (ncbi_gene/ncbi_mesh only).
# ---------------------------------------------------------------------------


def test_entity_source_url_defaults_to_none() -> None:
    entity = PubtatorEntity()
    assert entity.source_url is None


def test_entity_source_url_accepts_a_gene_record_url() -> None:
    entity = PubtatorEntity(
        db="ncbi_gene", db_id="672", source_url="https://www.ncbi.nlm.nih.gov/gene/672"
    )
    assert entity.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"


def test_entity_source_url_accepts_a_mesh_record_url() -> None:
    entity = PubtatorEntity(
        db="ncbi_mesh",
        db_id="D001943",
        source_url="https://www.ncbi.nlm.nih.gov/mesh/D001943",
    )
    assert entity.source_url == "https://www.ncbi.nlm.nih.gov/mesh/D001943"


def test_entity_source_url_rejects_a_pubmed_url() -> None:
    """The wrong kind of citation for an entity (a publication, not a gene/mesh page)."""
    with pytest.raises(ValidationError):
        PubtatorEntity(source_url="https://pubmed.ncbi.nlm.nih.gov/34083286/")


def test_entity_source_url_rejects_the_fetch_host() -> None:
    with pytest.raises(ValidationError):
        PubtatorEntity(
            source_url="https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/?query=BRCA1"
        )


def test_entity_source_url_rejects_a_snp_record() -> None:
    """A real NCBI record, but the wrong record type for this pattern."""
    with pytest.raises(ValidationError):
        PubtatorEntity(source_url="https://www.ncbi.nlm.nih.gov/snp/rs334")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ncbi.nlm.nih.gov/gene/672",
        "https://www.ncbi.nlm.nih.gov/mesh/D001943",
    ],
)
def test_ncbi_pubtator_entity_record_url_pattern_accepts_gene_and_mesh_urls(url: str) -> None:
    assert re.match(NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN, url) is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://pubmed.ncbi.nlm.nih.gov/34083286/",
        "https://www.ncbi.nlm.nih.gov/snp/rs334",
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/?query=BRCA1",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=672",
    ],
)
def test_ncbi_pubtator_entity_record_url_pattern_rejects_other_urls(url: str) -> None:
    assert re.match(NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN, url) is None


# ---------------------------------------------------------------------------
# PubtatorPublication.total_annotations: F-3.3-A-12, additive.
# ---------------------------------------------------------------------------


def test_publication_total_annotations_defaults_to_zero() -> None:
    pub = PubtatorPublication()
    assert pub.total_annotations == 0


def test_publication_total_annotations_accepts_a_count_above_the_cap() -> None:
    """The whole point of this field: it can legitimately exceed len(annotations)."""
    pub = PubtatorPublication(annotations=[PubtatorAnnotation()] * 5, total_annotations=250)
    assert pub.total_annotations == 250
    assert len(pub.annotations) == 5


def test_publication_total_annotations_negative_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorPublication(total_annotations=-1)


# ---------------------------------------------------------------------------
# PubtatorAnnotateOutput.fields_withheld: F-3.3-J-04, additive, mirrors
# Litvar2LookupOutput.fields_withheld exactly (20 items, 150 chars each).
# ---------------------------------------------------------------------------


def test_output_fields_withheld_defaults_to_none() -> None:
    output = PubtatorAnnotateOutput(status="ok", mode="entity_lookup")
    assert output.fields_withheld is None


def test_output_fields_withheld_accepts_a_note_list() -> None:
    output = PubtatorAnnotateOutput(
        status="ok",
        mode="entity_lookup",
        fields_withheld=["entities[0].description: some withheld value"],
    )
    assert output.fields_withheld == ["entities[0].description: some withheld value"]


def test_output_fields_withheld_over_max_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok",
            mode="entity_lookup",
            fields_withheld=[f"entities[{i}].name: x" for i in range(21)],
        )


def test_output_fields_withheld_item_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PubtatorAnnotateOutput(
            status="ok", mode="entity_lookup", fields_withheld=["n" * 151]
        )


def test_output_fields_withheld_item_at_max_length_validates() -> None:
    output = PubtatorAnnotateOutput(
        status="ok", mode="entity_lookup", fields_withheld=["n" * 150]
    )
    assert len(output.fields_withheld[0]) == 150
