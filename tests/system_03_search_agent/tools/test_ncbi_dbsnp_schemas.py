"""Tests for ncbi_dbsnp_schemas.py (T-3.2-03).

No network. Covers, for the input side, all three `query_type` values
validating through `NcbiDbsnpInput.model_validate`, `include_clinical`'s
default and explicit values, `extra="forbid"` rejecting an unknown key, the
`query` maxLength boundary, and (added 2026-08-08, F-3.2-A-02/J-03) the
narrow rsid-shape carve-out to design decision 2: a bare numeric `query`
rejected for `query_type: "rsid"`, an `rs`/`RS`-prefixed one still
validating, and the carve-out confirmed NOT to spill over into `spdi`/
`hgvs`. Also covers NEW-4 (independent re-review, fix round 1): the
`_RSID_SHAPE_PATTERN` regex object itself, directly, correctly anchors on
end-of-string (`\\Z`) rather than before-a-trailing-newline (`$`). For the
output side: every maxLength and maxItems cap actually enforced (not just
declared) on the top-level model and both nested item models
(`NcbiDbsnpGene`, `NcbiDbsnpPopulationFrequency`, including `allele_role`,
added 2026-08-08 for F-3.2-A-03), `fields_withheld` (added 2026-08-08,
F-3.2-A-15 design decision 7: defaults to `[]`, accepts real field names,
and its own maxItems/max_length caps), the three required fields (`status`,
`rsid`, `spdi_canonical`), the `status` enum, `extra="forbid"` at every
level, and `NCBI_DBSNP_RECORD_URL_PATTERN` accepting a real `/snp/` record
URL on both allowed subdomains while rejecting both fetch hosts
(`api.ncbi.nlm.nih.gov`, `eutils.ncbi.nlm.nih.gov`) and a same-host,
wrong-path NCBI URL.

What this file deliberately does NOT cover, per `goal-contracts`'s "a
verify surface must state its own coverage": how `ncbi_dbsnp.py` (T-3.2-04,
not yet written) parses a live Variation Services or dbSNP ESummary
response into these shapes. This file only proves the shapes themselves are
correctly typed and bounded; F-3.2-01 and F-3.2-02's raw-to-structured
parsing correctness is that ticket's test's job, not this file's.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.ncbi_dbsnp_schemas import (
    NCBI_DBSNP_RECORD_URL_PATTERN,
    NcbiDbsnpGene,
    NcbiDbsnpInput,
    NcbiDbsnpOutput,
    NcbiDbsnpPopulationFrequency,
)

# ---------------------------------------------------------------------------
# A minimal valid output dict, matching Section 6.3's required fields only,
# used as the base a boundary test overrides a single key from.
# ---------------------------------------------------------------------------

MINIMAL_OUTPUT_DICT = {
    "status": "ok",
    "rsid": "rs334",
    "spdi_canonical": "NC_000011.10:5227002:T:A",
}

FULL_OUTPUT_DICT = {
    "status": "ok",
    "rsid": "rs334",
    "spdi_canonical": "NC_000011.10:5227002:T:A",
    "alleles": ["A", "T"],
    "chrpos": "11:5227003",
    "clinical_significance": ["pathogenic", "protective"],
    "functional_consequence": ["missense_variant"],
    "genes": [{"name": "HBB", "gene_id": "3043"}],
    "population_frequencies": [{"population": "1000Genomes", "allele": "A", "frequency": 0.027356}],
    "source_url": "https://www.ncbi.nlm.nih.gov/snp/rs334",
    "error": None,
}


# ---------------------------------------------------------------------------
# Input: all three query_type values, from the spec's documented shape.
# ---------------------------------------------------------------------------


def test_rsid_query_type_validates() -> None:
    validated = NcbiDbsnpInput.model_validate({"query": "rs334", "query_type": "rsid"})
    assert validated.query == "rs334"
    assert validated.query_type == "rsid"
    assert validated.include_clinical is True  # spec default: true


def test_hgvs_query_type_validates() -> None:
    validated = NcbiDbsnpInput.model_validate(
        {"query": "NM_000518.5:c.20A>T", "query_type": "hgvs", "include_clinical": False}
    )
    assert validated.query_type == "hgvs"
    assert validated.include_clinical is False


def test_spdi_query_type_validates() -> None:
    validated = NcbiDbsnpInput.model_validate(
        {"query": "NC_000011.10:5227001:T:A", "query_type": "spdi"}
    )
    assert validated.query_type == "spdi"


def test_include_clinical_defaults_true_when_omitted() -> None:
    validated = NcbiDbsnpInput.model_validate({"query": "rs334", "query_type": "rsid"})
    assert validated.include_clinical is True


def test_invalid_query_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query": "rs334", "query_type": "curie"})


def test_missing_required_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query_type": "rsid"})


def test_missing_required_query_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query": "rs334"})


def test_input_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate(
            {"query": "rs334", "query_type": "rsid", "unexpected_field": "x"}
        )


# ---------------------------------------------------------------------------
# F-3.2-A-02/J-03: the narrow rsid-shape carve-out to design decision 2.
# ---------------------------------------------------------------------------


def test_bare_numeric_query_is_rejected_for_query_type_rsid() -> None:
    """The exact live repro: HBB's own Gene ID sent with no 'rs' prefix."""
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query": "3043", "query_type": "rsid"})


def test_rs_prefixed_query_still_validates_for_query_type_rsid() -> None:
    validated = NcbiDbsnpInput.model_validate({"query": "rs3043", "query_type": "rsid"})
    assert validated.query == "rs3043"


def test_uppercase_rs_prefix_still_validates_for_query_type_rsid() -> None:
    """`_RSID_SHAPE_PATTERN` is case-insensitive, matching `_strip_rs_prefix`'s
    own `.lower()` check in `ncbi_dbsnp.py`.
    """
    validated = NcbiDbsnpInput.model_validate({"query": "RS3043", "query_type": "rsid"})
    assert validated.query == "RS3043"


def test_bare_numeric_query_still_validates_for_query_type_spdi_and_hgvs() -> None:
    """The rsid-only carve-out must not spill over: design decision 2's
    original reasoning (a live 400 already classifies malformed spdi/hgvs
    input) is unchanged for these two query types.
    """
    spdi_validated = NcbiDbsnpInput.model_validate({"query": "3043", "query_type": "spdi"})
    assert spdi_validated.query == "3043"
    hgvs_validated = NcbiDbsnpInput.model_validate({"query": "3043", "query_type": "hgvs"})
    assert hgvs_validated.query == "3043"


def test_rsid_with_no_digits_after_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query": "rs", "query_type": "rsid"})


def test_rsid_shape_pattern_anchors_on_end_of_string_not_before_a_trailing_newline() -> None:
    """NEW-4 (independent re-review, fix round 1): `$` vs `\\Z`.

    In Python, `$` matches immediately before a trailing newline as well as
    at the true end of a string, so a naive `$`-anchored pattern would treat
    "rs334\\n" as a full match. Tested directly against the compiled
    pattern object, not through `NcbiDbsnpInput`, because
    `_validate_rsid_shape` already calls `.strip()` before matching, which
    would mask this at the validator level even before this fix (the finding's
    own "not currently exploitable" note). `\\Z` is the correct anchor
    regardless of what a caller does before matching.
    """
    from system_03_search_agent.tools.ncbi_dbsnp_schemas import _RSID_SHAPE_PATTERN

    assert _RSID_SHAPE_PATTERN.match("rs334") is not None
    assert _RSID_SHAPE_PATTERN.match("rs334\n") is None
    assert _RSID_SHAPE_PATTERN.match("rs334\nrs335") is None


def test_query_max_length_200_is_enforced() -> None:
    """`query_type: "spdi"` deliberately, not "rsid": F-3.2-A-02/J-03 added a
    NARROW rs-prefix shape check for query_type "rsid" only (see
    `_validate_rsid_shape`), which a plain "r" * 200 fixture no longer
    satisfies. This test's own intent is the `query` field's max_length
    boundary, independent of that shape check, so it uses "spdi", the
    query_type design decision 2 still leaves entirely unvalidated by shape.
    """
    NcbiDbsnpInput.model_validate({"query": "r" * 200, "query_type": "spdi"})  # boundary: ok
    with pytest.raises(ValidationError):
        NcbiDbsnpInput.model_validate({"query": "r" * 201, "query_type": "spdi"})


# ---------------------------------------------------------------------------
# Output: required fields, status enum, extra="forbid".
# ---------------------------------------------------------------------------


def test_minimal_output_validates_with_only_the_three_required_fields() -> None:
    validated = NcbiDbsnpOutput.model_validate(MINIMAL_OUTPUT_DICT)
    assert validated.status == "ok"
    assert validated.rsid == "rs334"
    assert validated.spdi_canonical == "NC_000011.10:5227002:T:A"
    # Everything else defaults to an empty collection or None.
    assert validated.alleles == []
    assert validated.chrpos is None
    assert validated.clinical_significance == []
    assert validated.functional_consequence == []
    assert validated.genes == []
    assert validated.population_frequencies == []
    assert validated.source_url is None
    assert validated.error is None


def test_full_output_validates() -> None:
    validated = NcbiDbsnpOutput.model_validate(FULL_OUTPUT_DICT)
    assert validated.alleles == ["A", "T"]
    assert validated.genes[0].name == "HBB"
    assert validated.genes[0].gene_id == "3043"
    assert validated.population_frequencies[0].population == "1000Genomes"
    assert validated.population_frequencies[0].allele == "A"
    assert validated.population_frequencies[0].frequency == pytest.approx(0.027356)
    assert validated.source_url == "https://www.ncbi.nlm.nih.gov/snp/rs334"


@pytest.mark.parametrize("missing_key", ["status", "rsid", "spdi_canonical"])
def test_each_required_output_field_is_actually_required(missing_key: str) -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    del payload[missing_key]
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


@pytest.mark.parametrize("value", ["ok", "empty", "error"])
def test_status_accepts_only_the_three_spec_values(value: str) -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["status"] = value
    NcbiDbsnpOutput.model_validate(payload)  # must not raise


def test_status_rejects_a_value_outside_the_three_spec_values() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["status"] = "success"
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_output_extra_field_is_forbidden() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["unexpected_field"] = "x"
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


# ---------------------------------------------------------------------------
# Output: every maxLength / maxItems cap, actually enforced at the boundary,
# not merely declared. Each case validates the cap value (must pass) and
# cap+1 (must raise), per Section 6.3's printed schema.
# ---------------------------------------------------------------------------


def test_rsid_max_length_20_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["rsid"] = "r" * 20
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["rsid"] = "r" * 21
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_spdi_canonical_max_length_150_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["spdi_canonical"] = "s" * 150
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["spdi_canonical"] = "s" * 151
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_alleles_max_items_10_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["alleles"] = ["A"] * 10
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["alleles"] = ["A"] * 11
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_alleles_item_max_length_20_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["alleles"] = ["a" * 20]
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["alleles"] = ["a" * 21]
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_chrpos_max_length_30_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["chrpos"] = "c" * 30
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["chrpos"] = "c" * 31
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_clinical_significance_max_items_10_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["clinical_significance"] = ["pathogenic"] * 10
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["clinical_significance"] = ["pathogenic"] * 11
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_clinical_significance_item_max_length_40_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["clinical_significance"] = ["c" * 40]
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["clinical_significance"] = ["c" * 41]
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_functional_consequence_max_items_10_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["functional_consequence"] = ["missense_variant"] * 10
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["functional_consequence"] = ["missense_variant"] * 11
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_functional_consequence_item_max_length_60_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["functional_consequence"] = ["f" * 60]
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["functional_consequence"] = ["f" * 61]
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_genes_max_items_10_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["genes"] = [{"name": "HBB", "gene_id": "3043"}] * 10
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["genes"] = [{"name": "HBB", "gene_id": "3043"}] * 11
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_gene_name_max_length_30_is_enforced() -> None:
    NcbiDbsnpGene.model_validate({"name": "n" * 30})  # boundary: ok
    with pytest.raises(ValidationError):
        NcbiDbsnpGene.model_validate({"name": "n" * 31})


def test_gene_id_max_length_20_is_enforced() -> None:
    NcbiDbsnpGene.model_validate({"gene_id": "g" * 20})  # boundary: ok
    with pytest.raises(ValidationError):
        NcbiDbsnpGene.model_validate({"gene_id": "g" * 21})


def test_gene_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpGene.model_validate({"name": "HBB", "unexpected_field": "x"})


def test_gene_fields_are_schema_optional() -> None:
    """Section 6.3's `genes` item schema carries no `required` list."""
    validated = NcbiDbsnpGene.model_validate({})
    assert validated.name is None
    assert validated.gene_id is None


def test_population_frequencies_max_items_30_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    item = {"population": "1000Genomes", "allele": "A", "frequency": 0.5}
    payload["population_frequencies"] = [item] * 30
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["population_frequencies"] = [item] * 31
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_population_max_length_20_is_enforced() -> None:
    NcbiDbsnpPopulationFrequency.model_validate({"population": "p" * 20})  # boundary: ok
    with pytest.raises(ValidationError):
        NcbiDbsnpPopulationFrequency.model_validate({"population": "p" * 21})


def test_population_allele_max_length_10_is_enforced() -> None:
    NcbiDbsnpPopulationFrequency.model_validate({"allele": "a" * 10})  # boundary: ok
    with pytest.raises(ValidationError):
        NcbiDbsnpPopulationFrequency.model_validate({"allele": "a" * 11})


def test_population_frequency_accepts_a_plain_number() -> None:
    validated = NcbiDbsnpPopulationFrequency.model_validate({"frequency": 0.027356})
    assert validated.frequency == pytest.approx(0.027356)


def test_population_frequency_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpPopulationFrequency.model_validate({"population": "x", "unexpected_field": "y"})


def test_population_frequency_allele_role_is_optional_and_accepts_the_three_spec_values() -> None:
    """F-3.2-A-03 (design decision 6): `allele_role` defaults to `None` and
    accepts exactly the three documented values.
    """
    assert NcbiDbsnpPopulationFrequency.model_validate({}).allele_role is None
    for role in ("variant", "reference", "other"):
        validated = NcbiDbsnpPopulationFrequency.model_validate({"allele_role": role})
        assert validated.allele_role == role


def test_population_frequency_allele_role_rejects_an_unrecognized_value() -> None:
    with pytest.raises(ValidationError):
        NcbiDbsnpPopulationFrequency.model_validate({"allele_role": "not-a-real-role"})


def test_source_url_max_length_200_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    # A syntactically valid dbSNP URL padded to exactly 200 chars with a
    # long but harmless query suffix, so the pattern still matches at the
    # boundary and only the length cap is under test.
    base = "https://www.ncbi.nlm.nih.gov/snp/rs334?"
    payload["source_url"] = base + "x" * (200 - len(base))
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["source_url"] = base + "x" * (201 - len(base))
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_error_max_length_500_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["status"] = "error"
    payload["error"] = "e" * 500
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["error"] = "e" * 501
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


# ---------------------------------------------------------------------------
# fields_withheld (F-3.2-A-15, design decision 7): defaults to [], accepts
# real field names, and enforces its own maxItems/max_length caps.
# ---------------------------------------------------------------------------


def test_fields_withheld_defaults_to_empty_list() -> None:
    validated = NcbiDbsnpOutput.model_validate(MINIMAL_OUTPUT_DICT)
    assert validated.fields_withheld == []


def test_fields_withheld_accepts_real_field_names() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["fields_withheld"] = ["clinical_significance", "population_frequencies"]
    validated = NcbiDbsnpOutput.model_validate(payload)
    assert validated.fields_withheld == ["clinical_significance", "population_frequencies"]


def test_fields_withheld_max_items_10_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["fields_withheld"] = ["x"] * 10
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["fields_withheld"] = ["x"] * 11
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_fields_withheld_item_max_length_30_is_enforced() -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["fields_withheld"] = ["f" * 30]
    NcbiDbsnpOutput.model_validate(payload)  # boundary: ok
    payload["fields_withheld"] = ["f" * 31]
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


# ---------------------------------------------------------------------------
# NCBI_DBSNP_RECORD_URL_PATTERN: the host-pin regex, applied both directly
# and through NcbiDbsnpOutput.source_url.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ncbi.nlm.nih.gov/snp/rs334",
        "https://pubmed.ncbi.nlm.nih.gov/snp/rs334",
        "https://ncbi.nlm.nih.gov/snp/rs334",
    ],
)
def test_source_url_pattern_accepts_real_dbsnp_record_urls(url: str) -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["source_url"] = url
    validated = NcbiDbsnpOutput.model_validate(payload)
    assert validated.source_url == url


@pytest.mark.parametrize(
    "url",
    [
        # The Variation Services fetch host, never a valid citation target.
        "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/334",
        # The dbSNP ESummary fetch host, same reasoning.
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=snp&id=334",
        # Right host, wrong path: not a dbSNP record page. This is the exact
        # case NCBI_EFETCH_RECORD_URL_PATTERN would wrongly accept, since it
        # has no /snp/ path requirement; this tool's own pattern must reject
        # it (module docstring design decision 3).
        "https://www.ncbi.nlm.nih.gov/gene/7157",
    ],
)
def test_source_url_pattern_rejects_fetch_hosts_and_wrong_paths(url: str) -> None:
    payload = dict(MINIMAL_OUTPUT_DICT)
    payload["source_url"] = url
    with pytest.raises(ValidationError):
        NcbiDbsnpOutput.model_validate(payload)


def test_pattern_constant_itself_matches_the_accept_and_reject_cases() -> None:
    """Direct regex-level proof, independent of Pydantic's own matching."""
    import re

    assert re.match(NCBI_DBSNP_RECORD_URL_PATTERN, "https://www.ncbi.nlm.nih.gov/snp/rs334")
    assert re.match(NCBI_DBSNP_RECORD_URL_PATTERN, "https://pubmed.ncbi.nlm.nih.gov/snp/rs334")
    assert not re.match(
        NCBI_DBSNP_RECORD_URL_PATTERN, "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/334"
    )
    assert not re.match(NCBI_DBSNP_RECORD_URL_PATTERN, "https://www.ncbi.nlm.nih.gov/gene/7157")
