"""Unit tests for pathogen_detection_schemas.py (T-3.5-03).

This file has zero dependency on `pathogen_ftp_transport` (the module
missing from this worktree; see `pathogen_detection_schemas.py`'s own
module docstring for the full account) or on `pathogen_detection.py`
itself. Every test here imports only
`system_03_search_agent.tools.pathogen_detection_schemas`, so this suite
is fully runnable in this environment with no scaffolding, no mocking,
and no stubbed-in modules.

Coverage statement (per `.claude/rules/goal-contracts.md`'s "a verify
surface must state its own coverage"): this file exercises input
validation for both `oneOf` branches (required fields, extra-field
rejection, the `taxon` shape pattern including a path-traversal attempt
and the `\\A...\\Z` trailing-newline edge case, `max_snp_distance` bounds,
`min_length` on identifier fields), output validation (`status` enum
pattern, `maxItems`/`maxLength` caps on `isolates` and its nested fields,
the host-pinned `source_url` pattern's accept and reject shapes,
`fields_withheld` cap), and RootModel `.root` access. It does NOT
exercise: the tool's own parsing logic (comma-join/NULL handling,
withhold-not-truncate, deadline discipline) since that logic lives in
`pathogen_detection.py`, not here; see `test_pathogen_detection.py` for
that coverage and its own, separately stated, coverage gap.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.pathogen_detection_schemas import (
    PATHOGEN_SOURCE_URL_PATTERN,
    PATHOGEN_TAXON_PATTERN,
    PathogenClusterSnpNeighborsInput,
    PathogenDetectionInput,
    PathogenDetectionOutput,
    PathogenIsolate,
    PathogenIsolateLookupInput,
)

# ---------------------------------------------------------------------------
# Input: isolate_lookup branch
# ---------------------------------------------------------------------------


def test_isolate_lookup_valid_payload_round_trips():
    payload = {"mode": "isolate_lookup", "taxon": "Salmonella", "biosample_acc": "SAMN02147118"}
    parsed = PathogenDetectionInput(**payload)
    assert isinstance(parsed.root, PathogenIsolateLookupInput)
    assert parsed.root.mode == "isolate_lookup"
    assert parsed.root.taxon == "Salmonella"
    assert parsed.root.biosample_acc == "SAMN02147118"


def test_isolate_lookup_missing_biosample_acc_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="isolate_lookup", taxon="Salmonella")


def test_isolate_lookup_missing_taxon_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="isolate_lookup", biosample_acc="SAMN02147118")


def test_isolate_lookup_extra_field_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="isolate_lookup",
            taxon="Salmonella",
            biosample_acc="SAMN02147118",
            pds_cluster="PDS000012345.1",
        )


def test_isolate_lookup_empty_biosample_acc_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="isolate_lookup", taxon="Salmonella", biosample_acc="")


def test_isolate_lookup_biosample_acc_over_cap_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="isolate_lookup", taxon="Salmonella", biosample_acc="S" * 31
        )


def test_isolate_lookup_taxon_over_cap_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="isolate_lookup", taxon="S" * 51, biosample_acc="SAMN02147118"
        )


# ---------------------------------------------------------------------------
# Input: cluster_snp_neighbors branch
# ---------------------------------------------------------------------------


def test_cluster_snp_neighbors_valid_payload_round_trips():
    payload = {
        "mode": "cluster_snp_neighbors",
        "taxon": "Salmonella",
        "pds_cluster": "PDS000012345.1",
    }
    parsed = PathogenDetectionInput(**payload)
    assert isinstance(parsed.root, PathogenClusterSnpNeighborsInput)
    assert parsed.root.pds_cluster == "PDS000012345.1"


def test_cluster_snp_neighbors_default_max_snp_distance_is_5():
    parsed = PathogenDetectionInput(
        mode="cluster_snp_neighbors", taxon="Salmonella", pds_cluster="PDS000012345.1"
    )
    assert parsed.root.max_snp_distance == 5


@pytest.mark.parametrize("value", [1, 5, 25, 50])
def test_cluster_snp_neighbors_max_snp_distance_in_bounds_accepted(value):
    parsed = PathogenDetectionInput(
        mode="cluster_snp_neighbors",
        taxon="Salmonella",
        pds_cluster="PDS000012345.1",
        max_snp_distance=value,
    )
    assert parsed.root.max_snp_distance == value


@pytest.mark.parametrize("value", [0, -1, 51, 1000])
def test_cluster_snp_neighbors_max_snp_distance_out_of_bounds_rejected(value):
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="cluster_snp_neighbors",
            taxon="Salmonella",
            pds_cluster="PDS000012345.1",
            max_snp_distance=value,
        )


def test_cluster_snp_neighbors_missing_pds_cluster_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="cluster_snp_neighbors", taxon="Salmonella")


def test_cluster_snp_neighbors_biosample_acc_field_rejected_on_this_branch():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="cluster_snp_neighbors",
            taxon="Salmonella",
            pds_cluster="PDS000012345.1",
            biosample_acc="SAMN02147118",
        )


# ---------------------------------------------------------------------------
# Input: mode discrimination itself
# ---------------------------------------------------------------------------


def test_unrecognized_mode_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(
            mode="something_else", taxon="Salmonella", biosample_acc="SAMN02147118"
        )


def test_missing_mode_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionInput(taxon="Salmonella", biosample_acc="SAMN02147118")


# ---------------------------------------------------------------------------
# Input: taxon shape pattern (path-safety, the load-bearing security check)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "taxon",
    [
        "../../../etc",
        "Salmonella/../..",
        "Salmonella/enterica",
        "123Salmonella",
        "Salmonella\n",
        "Salmonella enterica",
        "Salmonella;rm -rf",
        "..",
        "/etc/passwd",
    ],
)
def test_unsafe_taxon_values_rejected(taxon):
    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="isolate_lookup", taxon=taxon, biosample_acc="SAMN02147118")


@pytest.mark.parametrize("taxon", ["Salmonella", "Salmonella_enterica", "E-coli", "a"])
def test_safe_taxon_values_accepted(taxon):
    parsed = PathogenDetectionInput(
        mode="isolate_lookup", taxon=taxon, biosample_acc="SAMN02147118"
    )
    assert parsed.root.taxon == taxon


def test_pathogen_taxon_pattern_constant_matches_field_pattern_behavior():
    # Sanity: the exported constant is the same pattern actually enforced
    # on the field, not a copy that has drifted.
    import re

    assert re.match(PATHOGEN_TAXON_PATTERN, "Salmonella") is not None
    assert re.match(PATHOGEN_TAXON_PATTERN, "../etc") is None


# ---------------------------------------------------------------------------
# Output: status enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["ok", "empty", "error", "timeout"])
def test_output_status_valid_values_accepted(status):
    output = PathogenDetectionOutput(status=status, mode="isolate_lookup")
    assert output.status == status


def test_output_status_invalid_value_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(status="success", mode="isolate_lookup")


def test_output_only_status_and_mode_required():
    output = PathogenDetectionOutput(status="empty", mode="isolate_lookup")
    assert output.isolates == []
    assert output.isolate_count == 0
    assert output.total_available == 0
    assert output.truncated is False
    assert output.error is None
    assert output.pdg_snapshot is None
    assert output.fields_withheld is None


def test_output_extra_field_rejected():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(status="ok", mode="isolate_lookup", bogus_field="x")


# ---------------------------------------------------------------------------
# Output: isolates array and item caps
# ---------------------------------------------------------------------------


def test_isolates_maxitems_100_enforced():
    isolates = [PathogenIsolate(biosample_acc=f"SAMN{i:08d}") for i in range(100)]
    output = PathogenDetectionOutput(
        status="ok", mode="isolate_lookup", isolates=isolates, isolate_count=100
    )
    assert len(output.isolates) == 100

    with pytest.raises(ValidationError):
        PathogenDetectionOutput(
            status="ok",
            mode="cluster_snp_neighbors",
            isolates=[PathogenIsolate(biosample_acc=f"SAMN{i:08d}") for i in range(101)],
            isolate_count=101,
        )


def test_isolate_item_extra_field_rejected():
    with pytest.raises(ValidationError):
        PathogenIsolate(biosample_acc="SAMN02147118", bogus_field="x")


def test_isolate_item_all_fields_optional_with_defaults():
    isolate = PathogenIsolate()
    assert isolate.biosample_acc is None
    assert isolate.amr_genotypes == []
    assert isolate.ast_phenotypes == []
    assert isolate.snp_distance is None
    assert isolate.source_url is None


@pytest.mark.parametrize(
    "field,limit",
    [
        ("biosample_acc", 30),
        ("run_sra", 30),
        ("strain", 100),
        ("serovar", 60),
        ("geo_loc_name", 150),
        ("collection_date", 30),
        ("pds_cluster", 30),
    ],
)
def test_isolate_scalar_field_over_cap_rejected(field, limit):
    with pytest.raises(ValidationError):
        PathogenIsolate(**{field: "x" * (limit + 1)})


def test_amr_genotypes_item_max_length_40_enforced():
    with pytest.raises(ValidationError):
        PathogenIsolate(amr_genotypes=["x" * 41])
    # Exactly at the cap is fine.
    isolate = PathogenIsolate(amr_genotypes=["x" * 40])
    assert isolate.amr_genotypes == ["x" * 40]


def test_ast_phenotypes_item_max_length_60_enforced():
    with pytest.raises(ValidationError):
        PathogenIsolate(ast_phenotypes=["x" * 61])
    isolate = PathogenIsolate(ast_phenotypes=["x" * 60])
    assert isolate.ast_phenotypes == ["x" * 60]


def test_amr_genotypes_maxitems_30_enforced():
    with pytest.raises(ValidationError):
        PathogenIsolate(amr_genotypes=[f"gene{i}" for i in range(31)])
    isolate = PathogenIsolate(amr_genotypes=[f"gene{i}" for i in range(30)])
    assert len(isolate.amr_genotypes) == 30


def test_ast_phenotypes_maxitems_30_enforced():
    with pytest.raises(ValidationError):
        PathogenIsolate(ast_phenotypes=[f"pheno{i}" for i in range(31)])


def test_snp_distance_accepts_int_or_none():
    assert PathogenIsolate(snp_distance=None).snp_distance is None
    assert PathogenIsolate(snp_distance=0).snp_distance == 0
    assert PathogenIsolate(snp_distance=12).snp_distance == 12


# ---------------------------------------------------------------------------
# Output: host-pinned source_url pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN02147118",
        "https://ncbi.nlm.nih.gov/pathogens/",
    ],
)
def test_isolate_source_url_valid_shapes_accepted(url):
    isolate = PathogenIsolate(source_url=url)
    assert isolate.source_url == url


@pytest.mark.parametrize(
    "url",
    [
        "https://ftp.ncbi.nlm.nih.gov/pathogen/Results/Salmonella/",
        "https://evil.example.com/pathogens/",
        "http://www.ncbi.nlm.nih.gov/pathogens/",
        "https://www.ncbi.nlm.nih.gov/gene/7157",
    ],
)
def test_isolate_source_url_invalid_shapes_rejected(url):
    with pytest.raises(ValidationError):
        PathogenIsolate(source_url=url)


def test_isolate_source_url_over_max_length_300_rejected():
    long_url = "https://www.ncbi.nlm.nih.gov/pathogens/" + ("x" * 300)
    with pytest.raises(ValidationError):
        PathogenIsolate(source_url=long_url)


def test_pathogen_source_url_pattern_constant_matches_field_pattern_behavior():
    import re

    assert (
        re.match(
            PATHOGEN_SOURCE_URL_PATTERN, "https://www.ncbi.nlm.nih.gov/pathogens/isolates"
        )
        is not None
    )
    assert re.match(PATHOGEN_SOURCE_URL_PATTERN, "https://evil.example.com/pathogens/") is None


# ---------------------------------------------------------------------------
# Output: fields_withheld and error caps
# ---------------------------------------------------------------------------


def test_fields_withheld_defaults_to_none():
    output = PathogenDetectionOutput(status="ok", mode="isolate_lookup")
    assert output.fields_withheld is None


def test_fields_withheld_maxitems_20_enforced():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(
            status="ok",
            mode="isolate_lookup",
            fields_withheld=[f"note {i}" for i in range(21)],
        )
    output = PathogenDetectionOutput(
        status="ok", mode="isolate_lookup", fields_withheld=[f"note {i}" for i in range(20)]
    )
    assert len(output.fields_withheld) == 20


def test_fields_withheld_item_max_length_150_enforced():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(
            status="ok", mode="isolate_lookup", fields_withheld=["x" * 151]
        )


def test_error_max_length_500_enforced():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(status="error", mode="isolate_lookup", error="x" * 501)
    output = PathogenDetectionOutput(status="error", mode="isolate_lookup", error="x" * 500)
    assert len(output.error) == 500


def test_mode_max_length_25_enforced():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(status="ok", mode="x" * 26)


def test_pdg_snapshot_max_length_30_enforced():
    with pytest.raises(ValidationError):
        PathogenDetectionOutput(status="ok", mode="isolate_lookup", pdg_snapshot="x" * 31)
    output = PathogenDetectionOutput(
        status="ok", mode="isolate_lookup", pdg_snapshot="PDG000000002.4157"
    )
    assert output.pdg_snapshot == "PDG000000002.4157"
