"""Tests for ncbi_efetch_schemas.py (T-3.1-03).

No network. Covers, for the input side, every one of the 7 discriminated
actions validating from its Technical_specification.md Section 6.2 documented
dict shape through `NcbiEfetchInput.model_validate` (the exact entry point
the premise gate's `_call_input` helper depends on), a missing required field
rejected per action, `extra="forbid"` rejecting an unknown key, an invalid
closed-vocabulary value rejected per action, and every maxLength/maxItems
boundary. For the output side: the `fields` maxProperties validator on
`NcbiEfetchRecord`, the `source_url` pattern accepting a real record URL and
rejecting both fetch hosts (`eutils.ncbi.nlm.nih.gov`,
`api.ncbi.nlm.nih.gov`), and `NcbiEfetchOutput`'s own required fields,
length caps, and `extra="forbid"`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchCoordinateOverlapInput,
    NcbiEfetchDatasetReportInput,
    NcbiEfetchFetchInput,
    NcbiEfetchInput,
    NcbiEfetchLinkInput,
    NcbiEfetchOutput,
    NcbiEfetchPubchemPropertyInput,
    NcbiEfetchRecord,
    NcbiEfetchSearchInput,
    NcbiEfetchSummaryInput,
)

# ---------------------------------------------------------------------------
# Section 6.2 documented dict shapes, one per action, used both as the
# "valid from spec dict" fixture and as the base a required-field or
# boundary test deletes/overrides a single key from.
# ---------------------------------------------------------------------------

SEARCH_DICT = {
    "action": "search",
    "db": "gene",
    "term": "TP53[sym] AND human[orgn]",
    "field_tags": ["sym", "orgn"],
    "retmax": 10,
    "use_history": False,
}

FETCH_DICT = {
    "action": "fetch",
    "db": "pubmed",
    "ids": ["21376230"],
    "rettype": "abstract",
    "retmode": "xml",
}

SUMMARY_DICT = {
    "action": "summary",
    "db": "gene",
    "ids": ["7157"],
}

LINK_DICT = {
    "action": "link",
    "dbfrom": "gene",
    "db": "pubmed",
    "ids": ["7157"],
}

COORDINATE_OVERLAP_DICT = {
    "action": "coordinate_overlap",
    "db": "clinvar",
    "chromosome": "17",
    "start": 7661779,
    "end": 7687538,
    "assembly": "GRCh38",
}

DATASET_REPORT_DICT = {
    "action": "dataset_report",
    "report_type": "gene",
    "symbol": "TP53",
    "taxon": "human",
}

PUBCHEM_PROPERTY_DICT = {
    "action": "pubchem_property",
    "lookup_type": "cid",
    "value": "2244",
    "properties": ["MolecularFormula", "MolecularWeight"],
}


# ---------------------------------------------------------------------------
# Each of the 7 actions validates from its spec dict shape through the
# discriminated-union entry point, and routes to the right sibling model.
# ---------------------------------------------------------------------------


def test_search_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(SEARCH_DICT)
    assert isinstance(validated.root, NcbiEfetchSearchInput)
    assert validated.root.db == "gene"
    assert validated.root.term == "TP53[sym] AND human[orgn]"
    assert validated.root.field_tags == ["sym", "orgn"]
    assert validated.root.retmax == 10


def test_fetch_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(FETCH_DICT)
    assert isinstance(validated.root, NcbiEfetchFetchInput)
    assert validated.root.db == "pubmed"
    assert validated.root.ids == ["21376230"]
    assert validated.root.rettype == "abstract"
    assert validated.root.retmode == "xml"


def test_summary_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(SUMMARY_DICT)
    assert isinstance(validated.root, NcbiEfetchSummaryInput)
    assert validated.root.db == "gene"
    assert validated.root.ids == ["7157"]


def test_link_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(LINK_DICT)
    assert isinstance(validated.root, NcbiEfetchLinkInput)
    assert validated.root.dbfrom == "gene"
    assert validated.root.db == "pubmed"
    assert validated.root.ids == ["7157"]


def test_coordinate_overlap_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(COORDINATE_OVERLAP_DICT)
    assert isinstance(validated.root, NcbiEfetchCoordinateOverlapInput)
    assert validated.root.db == "clinvar"
    assert validated.root.chromosome == "17"
    assert validated.root.start == 7661779
    assert validated.root.end == 7687538
    assert validated.root.assembly == "GRCh38"


def test_dataset_report_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(DATASET_REPORT_DICT)
    assert isinstance(validated.root, NcbiEfetchDatasetReportInput)
    assert validated.root.report_type == "gene"
    assert validated.root.symbol == "TP53"
    assert validated.root.taxon == "human"
    assert validated.root.gene_id is None
    assert validated.root.accession is None


def test_dataset_report_accepts_genome_variant_with_accession_only() -> None:
    validated = NcbiEfetchInput.model_validate(
        {"action": "dataset_report", "report_type": "genome", "accession": "GCF_000001405.40"}
    )
    assert isinstance(validated.root, NcbiEfetchDatasetReportInput)
    assert validated.root.accession == "GCF_000001405.40"
    assert validated.root.symbol is None


def test_pubchem_property_validates_from_spec_dict_via_ncbi_efetch_input() -> None:
    validated = NcbiEfetchInput.model_validate(PUBCHEM_PROPERTY_DICT)
    assert isinstance(validated.root, NcbiEfetchPubchemPropertyInput)
    assert validated.root.lookup_type == "cid"
    assert validated.root.value == "2244"
    assert validated.root.properties == ["MolecularFormula", "MolecularWeight"]


# ---------------------------------------------------------------------------
# Defaults: fields the spec marks optional with a stated default.
# ---------------------------------------------------------------------------


def test_search_defaults_retmax_and_use_history_and_field_tags() -> None:
    validated = NcbiEfetchInput.model_validate(
        {"action": "search", "db": "pubmed", "term": "cancer"}
    )
    root = validated.root
    assert isinstance(root, NcbiEfetchSearchInput)
    assert root.retmax == 100
    assert root.use_history is False
    assert root.field_tags == []


def test_fetch_defaults_rettype_and_retmode() -> None:
    validated = NcbiEfetchInput.model_validate(
        {"action": "fetch", "db": "pubmed", "ids": ["1"]}
    )
    root = validated.root
    assert isinstance(root, NcbiEfetchFetchInput)
    assert root.rettype == "docsum"
    assert root.retmode == "json"


def test_pubchem_property_defaults_properties_to_empty_list() -> None:
    validated = NcbiEfetchInput.model_validate(
        {"action": "pubchem_property", "lookup_type": "name", "value": "aspirin"}
    )
    root = validated.root
    assert isinstance(root, NcbiEfetchPubchemPropertyInput)
    assert root.properties == []


# ---------------------------------------------------------------------------
# The discriminator itself: unknown or missing `action`.
# ---------------------------------------------------------------------------


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({"action": "delete_everything", "db": "gene"})


def test_missing_action_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({"db": "gene", "term": "x"})


# ---------------------------------------------------------------------------
# A missing required field is rejected, once per action.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing_key", ["action", "db", "term"])
def test_search_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(SEARCH_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize("missing_key", ["action", "db", "ids"])
def test_fetch_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(FETCH_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize("missing_key", ["action", "db", "ids"])
def test_summary_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(SUMMARY_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize("missing_key", ["action", "dbfrom", "db", "ids"])
def test_link_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(LINK_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize(
    "missing_key", ["action", "db", "chromosome", "start", "end", "assembly"]
)
def test_coordinate_overlap_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(COORDINATE_OVERLAP_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize("missing_key", ["action", "report_type"])
def test_dataset_report_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(DATASET_REPORT_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


@pytest.mark.parametrize("missing_key", ["action", "lookup_type", "value"])
def test_pubchem_property_rejects_missing_required_field(missing_key: str) -> None:
    payload = dict(PUBCHEM_PROPERTY_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(payload)


# ---------------------------------------------------------------------------
# extra="forbid": an unknown key is rejected, one representative case per
# action model plus the two output models.
# ---------------------------------------------------------------------------


def test_search_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "unexpected_field": "nope"})


def test_fetch_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "unexpected_field": "nope"})


def test_summary_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SUMMARY_DICT, "unexpected_field": "nope"})


def test_link_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**LINK_DICT, "unexpected_field": "nope"})


def test_coordinate_overlap_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, "unexpected_field": "nope"})


def test_dataset_report_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**DATASET_REPORT_DICT, "unexpected_field": "nope"})


def test_pubchem_property_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**PUBCHEM_PROPERTY_DICT, "unexpected_field": "nope"})


# ---------------------------------------------------------------------------
# Closed vocabularies: an invalid enum-like value is rejected.
# ---------------------------------------------------------------------------


def test_search_rejects_an_invalid_db_name_before_any_request() -> None:
    """`db` is the spec's closed enum, and an unknown name never leaves here.

    This test asserted the OPPOSITE until 2026-08-05, and the reversal is
    worth recording rather than quietly rewriting.

    The premise gate's case 9 originally sent `db: "notadatabase"` and
    required it to reach the live ESearch endpoint, because only the response
    body distinguishes an invalid db name (HTTP 200 with
    `esearchresult.ERROR`) from a genuine zero-hit search (HTTP 200, no ERROR
    key). Satisfying that forced `db` open to a bounded string, which traded a
    real input-validation control for the ability to observe one error path.

    The gate was rewritten to trigger the SAME HTTP-200-with-an-ERROR body
    from a malformed term instead, which is schema-legal and leaves `db`
    closed. Verified live 2026-08-05, three consecutive requests. So body-based
    error classification is still tested end to end (gate case 9a) and the
    invalid db is now rejected here, before any request is sent (gate case 9b).

    Section 6.2 contradicts itself on this point: it constrains `db` to a
    closed enum and also documents an "Invalid db name" response the tool must
    classify. Both cannot hold. Filed as F-3.1-02 for Step 6.2, resolved here
    in favor of the enum, since a request never sent cannot be misclassified
    and cannot spend a rate-limit token.
    """
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "db": "notadatabase"})


def test_fetch_rejects_a_db_outside_its_documented_8_value_list() -> None:
    # "taxonomy" is valid for `search` (14 databases) and is deliberately NOT
    # in `fetch`'s narrower 8-database list. The per-action vocabularies are
    # genuinely different in Section 6.2, so a db legal for one action must
    # not be legal for another.
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "db": "taxonomy"})


def test_summary_rejects_a_db_outside_its_documented_12_value_list() -> None:
    # "mesh" is in search's 14 and not in summary's 12.
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SUMMARY_DICT, "db": "mesh"})


def test_each_action_accepts_every_db_its_spec_enum_lists() -> None:
    # The counterweight to the three rejections above. An enum that is too
    # narrow is a silent outage rather than a security control, so pin the
    # full documented vocabulary per action, not just one member.
    search_dbs = ("pubmed", "gene", "clinvar", "dbvar", "omim", "medgen",
                  "gtr", "sra", "bioproject", "biosample", "assembly", "gds",
                  "taxonomy", "mesh")
    fetch_dbs = ("pubmed", "gene", "clinvar", "dbvar", "omim", "medgen",
                 "gtr", "sra")
    summary_dbs = ("pubmed", "gene", "clinvar", "dbvar", "omim", "medgen",
                   "gtr", "sra", "bioproject", "biosample", "assembly", "gds")
    assert len(search_dbs) == 14
    assert len(fetch_dbs) == 8
    assert len(summary_dbs) == 12
    for db in search_dbs:
        assert NcbiEfetchInput.model_validate({**SEARCH_DICT, "db": db}).root.db == db
    for db in fetch_dbs:
        assert NcbiEfetchInput.model_validate({**FETCH_DICT, "db": db}).root.db == db
    for db in summary_dbs:
        assert NcbiEfetchInput.model_validate({**SUMMARY_DICT, "db": db}).root.db == db


def test_search_rejects_oversized_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "db": "x" * 21})


def test_fetch_rejects_oversized_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "db": "x" * 21})


def test_summary_rejects_oversized_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SUMMARY_DICT, "db": "x" * 21})


def test_coordinate_overlap_rejects_unknown_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, "db": "gene"})


def test_coordinate_overlap_rejects_unknown_assembly() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, "assembly": "GRCh39"})


def test_dataset_report_rejects_unknown_report_type() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**DATASET_REPORT_DICT, "report_type": "transcript"})


def test_pubchem_property_rejects_unknown_lookup_type() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**PUBCHEM_PROPERTY_DICT, "lookup_type": "inchikey"})


def test_fetch_rejects_unknown_rettype() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "rettype": "raw"})


def test_fetch_rejects_unknown_retmode() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "retmode": "csv"})


# ---------------------------------------------------------------------------
# maxLength / maxItems boundaries, per constrained field.
# ---------------------------------------------------------------------------


def test_search_rejects_oversized_term() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "term": "x" * 501})


def test_search_accepts_max_length_term() -> None:
    validated = NcbiEfetchInput.model_validate({**SEARCH_DICT, "term": "x" * 500})
    assert len(validated.root.term) == 500


def test_search_rejects_too_many_field_tags() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "field_tags": ["a", "b", "c", "d", "e", "f"]})


def test_search_accepts_max_field_tags() -> None:
    validated = NcbiEfetchInput.model_validate(
        {**SEARCH_DICT, "field_tags": ["a", "b", "c", "d", "e"]}
    )
    assert len(validated.root.field_tags) == 5


def test_search_rejects_oversized_field_tag() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "field_tags": ["x" * 21]})


@pytest.mark.parametrize("retmax", [0, 501, "abc", 1.5])
def test_search_rejects_bad_retmax(retmax: object) -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SEARCH_DICT, "retmax": retmax})


def test_search_accepts_boundary_retmax_values() -> None:
    low = NcbiEfetchInput.model_validate({**SEARCH_DICT, "retmax": 1})
    high = NcbiEfetchInput.model_validate({**SEARCH_DICT, "retmax": 500})
    assert low.root.retmax == 1
    assert high.root.retmax == 500


def test_fetch_rejects_too_many_ids() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "ids": [str(i) for i in range(51)]})


def test_fetch_accepts_max_ids() -> None:
    validated = NcbiEfetchInput.model_validate(
        {**FETCH_DICT, "ids": [str(i) for i in range(50)]}
    )
    assert len(validated.root.ids) == 50


def test_fetch_rejects_oversized_id() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**FETCH_DICT, "ids": ["x" * 31]})


def test_summary_rejects_too_many_ids() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**SUMMARY_DICT, "ids": [str(i) for i in range(51)]})


def test_link_rejects_oversized_dbfrom() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**LINK_DICT, "dbfrom": "x" * 21})


def test_link_rejects_oversized_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**LINK_DICT, "db": "x" * 21})


def test_link_rejects_too_many_ids() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**LINK_DICT, "ids": [str(i) for i in range(21)]})


def test_link_accepts_max_ids() -> None:
    validated = NcbiEfetchInput.model_validate(
        {**LINK_DICT, "ids": [str(i) for i in range(20)]}
    )
    assert len(validated.root.ids) == 20


def test_coordinate_overlap_rejects_oversized_chromosome() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, "chromosome": "x" * 6})


def test_dataset_report_rejects_oversized_gene_id() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(
            {"action": "dataset_report", "report_type": "gene", "gene_id": "x" * 21}
        )


def test_dataset_report_rejects_oversized_symbol() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**DATASET_REPORT_DICT, "symbol": "x" * 31})


def test_dataset_report_rejects_oversized_taxon() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**DATASET_REPORT_DICT, "taxon": "x" * 31})


def test_dataset_report_rejects_oversized_accession() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(
            {"action": "dataset_report", "report_type": "genome", "accession": "x" * 21}
        )


def test_pubchem_property_rejects_oversized_value() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**PUBCHEM_PROPERTY_DICT, "value": "x" * 201})


def test_pubchem_property_rejects_too_many_properties() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate(
            {**PUBCHEM_PROPERTY_DICT, "properties": [f"p{i}" for i in range(11)]}
        )


def test_pubchem_property_accepts_max_properties() -> None:
    validated = NcbiEfetchInput.model_validate(
        {**PUBCHEM_PROPERTY_DICT, "properties": [f"p{i}" for i in range(10)]}
    )
    assert len(validated.root.properties) == 10


def test_pubchem_property_rejects_oversized_property_name() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**PUBCHEM_PROPERTY_DICT, "properties": ["x" * 41]})


# ===========================================================================
# NcbiEfetchRecord
# ===========================================================================


def _record_kwargs(**overrides: object) -> dict[str, object]:
    base = {
        "id": "7157",
        "db": "gene",
        "fields": {"name": "TP53"},
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
    }
    base.update(overrides)
    return base


def test_record_valid_with_all_fields() -> None:
    record = NcbiEfetchRecord(**_record_kwargs())
    assert record.id == "7157"
    assert record.source_url == "https://www.ncbi.nlm.nih.gov/gene/7157"


def test_record_valid_with_no_fields_set() -> None:
    record = NcbiEfetchRecord()
    assert record.id is None
    assert record.db is None
    assert record.fields == {}
    assert record.source_url is None


def test_record_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(unexpected_field="nope"))


def test_record_rejects_oversized_id() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(id="x" * 31))


def test_record_rejects_oversized_db() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(db="x" * 21))


def test_record_rejects_too_many_fields() -> None:
    oversized_fields = {f"prop_{i}": i for i in range(41)}
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(fields=oversized_fields))


def test_record_accepts_max_fields() -> None:
    max_fields = {f"prop_{i}": i for i in range(40)}
    record = NcbiEfetchRecord(**_record_kwargs(fields=max_fields))
    assert len(record.fields) == 40


def test_record_rejects_oversized_source_url() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(
            **_record_kwargs(
                source_url="https://www.ncbi.nlm.nih.gov/gene/" + "7" * 280
            )
        )


# ---------------------------------------------------------------------------
# The load-bearing case: source_url must accept the record host and reject
# BOTH fetch hosts this tool actually calls. Premise gate case 4.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "record_url",
    [
        "https://www.ncbi.nlm.nih.gov/gene/7157",
        "https://pubmed.ncbi.nlm.nih.gov/21376230/",
        "https://ncbi.nlm.nih.gov/clinvar/variation/12345",
        "https://omim.org/entry/191170",
        "https://www.omim.org/entry/191170",
    ],
)
def test_record_source_url_accepts_documented_record_hosts(record_url: str) -> None:
    record = NcbiEfetchRecord(**_record_kwargs(source_url=record_url))
    assert record.source_url == record_url


@pytest.mark.parametrize(
    "fetch_url",
    [
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=1",
        "https://api.ncbi.nlm.nih.gov/datasets/v2/gene/id/7157",
    ],
)
def test_record_source_url_rejects_both_fetch_hosts(fetch_url: str) -> None:
    """The tool fetches from eutils/api hosts but must cite the record page.

    A pattern that merely allowed any `*.ncbi.nlm.nih.gov` subdomain would
    pass a raw fetch URL straight into a citation, which is exactly the
    cross-tool trap this ticket's instructions call out by name.
    """
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(source_url=fetch_url))


def test_record_source_url_rejects_unrelated_host() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(source_url="https://evil.example/gene/7157"))


def test_record_source_url_rejects_http_scheme() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchRecord(**_record_kwargs(source_url="http://www.ncbi.nlm.nih.gov/gene/7157"))


# ===========================================================================
# NcbiEfetchOutput
# ===========================================================================


def test_output_valid_ok() -> None:
    output = NcbiEfetchOutput(
        status="ok",
        action="search",
        records=[NcbiEfetchRecord(**_record_kwargs())],
        record_count=1,
        total_available=1,
        truncated=False,
    )
    assert output.status == "ok"
    assert output.record_count == 1


def test_output_valid_empty() -> None:
    output = NcbiEfetchOutput(
        status="empty", action="search", records=[], record_count=0, truncated=False
    )
    assert output.status == "empty"
    assert output.records == []


def test_output_valid_error() -> None:
    output = NcbiEfetchOutput(
        status="error",
        action="search",
        records=[],
        record_count=0,
        truncated=False,
        error="invalid db name specified: notadatabase",
    )
    assert output.status == "error"
    assert output.error is not None


def test_output_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="weird", action="search", records=[], record_count=0, truncated=False
        )


def test_output_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="ok",
            action="search",
            records=[],
            record_count=0,
            truncated=False,
            unexpected_field="nope",
        )


def test_output_rejects_too_many_records() -> None:
    records = [NcbiEfetchRecord(**_record_kwargs()) for _ in range(101)]
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="ok", action="search", records=records, record_count=101, truncated=True
        )


def test_output_accepts_max_records() -> None:
    records = [NcbiEfetchRecord(**_record_kwargs()) for _ in range(100)]
    output = NcbiEfetchOutput(
        status="ok", action="search", records=records, record_count=100, truncated=False
    )
    assert len(output.records) == 100


def test_output_rejects_oversized_action() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="ok",
            action="x" * 21,
            records=[],
            record_count=0,
            truncated=False,
        )


def test_output_rejects_oversized_error() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="error",
            action="search",
            records=[],
            record_count=0,
            truncated=False,
            error="x" * 501,
        )


@pytest.mark.parametrize("missing_key", ["status", "action", "record_count", "truncated"])
def test_output_rejects_missing_required_field(missing_key: str) -> None:
    """Section 6.2 lists `records` in the output schema's `required` array,
    but this model gives it `default_factory=list`, the same choice
    `cypher_schemas.CypherQueryOutput.rows` already makes for the identical
    situation: an empty list is a legitimate `ok`/`empty` response, so
    Pydantic-level omission (which fills the default) is not a rejection
    case here. `test_output_valid_empty` above already exercises the
    `records`-omitted-equivalent path via an explicit `records=[]`.
    """
    kwargs: dict[str, object] = {
        "status": "ok",
        "action": "search",
        "records": [],
        "record_count": 0,
        "truncated": False,
    }
    del kwargs[missing_key]
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(**kwargs)  # type: ignore[arg-type]


def test_output_rejects_null_truncated() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="ok",
            action="search",
            records=[],
            record_count=0,
            truncated=None,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# The coordinate window is constrained at the SCHEMA layer (F-3.1-12), so
# the plan tier reading the generated JSON schema sees the constraint
# instead of learning it from an error.
# ---------------------------------------------------------------------------


def test_coordinate_overlap_json_schema_declares_a_minimum_on_start_and_end() -> None:
    """The F-3.1-27 fix originally landed as an `if` inside the tool body,
    which left `start`/`end` completely unconstrained in the generated JSON
    schema. `ge=0` is expressible in JSON Schema and must appear.
    """
    schema = NcbiEfetchCoordinateOverlapInput.model_json_schema()
    for field in ("start", "end"):
        assert schema["properties"][field].get("minimum") == 0, (
            f"{field} carries no minimum in the generated JSON schema: "
            f"{schema['properties'][field]!r}"
        )


def test_coordinate_overlap_json_schema_states_the_start_le_end_relation() -> None:
    """`start <= end` is a cross-field relation standard JSON Schema cannot
    express, so it is stated in the field descriptions, which DO reach the
    generated schema the plan tier reads.
    """
    schema = NcbiEfetchCoordinateOverlapInput.model_json_schema()
    descriptions = " ".join(
        schema["properties"][field].get("description", "") for field in ("start", "end")
    )
    assert "<= end" in descriptions and ">= start" in descriptions, (
        f"the ordering constraint is not stated in the schema: {descriptions!r}"
    )


def test_coordinate_overlap_rejects_an_inverted_window() -> None:
    """The original F-3.1-27 reproduction: start=2000, end=1000."""
    with pytest.raises(ValidationError) as excinfo:
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, "start": 2000, "end": 1000})

    message = str(excinfo.value)
    assert "inverted window" in message, message
    assert "start <= end" in message, message


def test_coordinate_overlap_rejects_an_inverted_window_on_the_branch_model() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchCoordinateOverlapInput.model_validate(
            {**COORDINATE_OVERLAP_DICT, "start": 2000, "end": 1000}
        )


@pytest.mark.parametrize("field", ["start", "end"])
def test_coordinate_overlap_rejects_a_negative_coordinate(field: str) -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**COORDINATE_OVERLAP_DICT, field: -1})


def test_coordinate_overlap_accepts_a_zero_length_window() -> None:
    """`start == end` is a single-base window, not an inverted one, and
    stays valid: the overlap predicate itself is inclusive on both ends.
    """
    validated = NcbiEfetchInput.model_validate(
        {**COORDINATE_OVERLAP_DICT, "start": 1000, "end": 1000}
    )
    assert validated.root.start == validated.root.end == 1000


# ---------------------------------------------------------------------------
# candidates_checked (F-3.1-24, reopened): an additive optional output
# field, so every pre-existing output shape still validates unchanged.
# ---------------------------------------------------------------------------


def test_output_candidates_checked_defaults_to_none() -> None:
    output = NcbiEfetchOutput(
        status="ok", action="search", records=[], record_count=0, truncated=False
    )
    assert output.candidates_checked is None


def test_output_accepts_candidates_checked() -> None:
    output = NcbiEfetchOutput(
        status="ok",
        action="coordinate_overlap",
        records=[],
        record_count=0,
        total_available=500,
        candidates_checked=20,
        truncated=True,
    )
    assert output.candidates_checked == 20


def test_output_rejects_negative_candidates_checked() -> None:
    with pytest.raises(ValidationError):
        NcbiEfetchOutput(
            status="ok",
            action="coordinate_overlap",
            records=[],
            record_count=0,
            candidates_checked=-1,
            truncated=False,
        )


# ---------------------------------------------------------------------------
# UI fix set 11 (search breadth, 2026-09-14): `pmc` is an additive SearchDb
# value and nothing else widened.
# ---------------------------------------------------------------------------


def test_search_accepts_pmc() -> None:
    assert NcbiEfetchInput.model_validate({**SEARCH_DICT, "db": "pmc"}).root.db == "pmc"


def test_search_db_vocabulary_is_the_spec_fourteen_plus_pmc() -> None:
    from typing import get_args

    from system_03_search_agent.tools.ncbi_efetch_schemas import SearchDb

    values = get_args(SearchDb)
    assert len(values) == 15
    assert values[-1] == "pmc"


@pytest.mark.parametrize("payload", [FETCH_DICT, SUMMARY_DICT])
def test_fetch_and_summary_still_reject_pmc(payload: dict) -> None:
    """Neither path is live-verified for PMC, so neither enum widened."""
    with pytest.raises(ValidationError):
        NcbiEfetchInput.model_validate({**payload, "db": "pmc"})
