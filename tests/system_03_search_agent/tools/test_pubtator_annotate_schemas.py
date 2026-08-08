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
strings, bounded the same as the input's own `pmids`), and
`NCBI_PUBTATOR_RECORD_URL_PATTERN` accepting a real `pubmed.ncbi.nlm.nih.gov`
record URL while rejecting the PubTator3 API fetch host and two
right-host-wrong-kind-of-record NCBI URLs.

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
