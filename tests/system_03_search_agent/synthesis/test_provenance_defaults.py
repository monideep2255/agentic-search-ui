"""Unit tests for `synthesis.provenance_defaults`. See that module's
docstring for the Section 9.2 rules these enforce."""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis.provenance_defaults import (
    PER_TOOL_DEFAULTS,
    clinvar_term_confidence,
    defaults_for_tool,
    hedge_scan_confidence,
)

ALL_SEVEN_TOOLS = (
    "cypher_query", "ncbi_efetch", "ncbi_dbsnp", "pubtator_annotate",
    "litvar2_lookup", "pathogen_detection", "clinicaltrials_search",
)


def test_every_tool_has_a_registered_default() -> None:
    for tool_name in ALL_SEVEN_TOOLS:
        entry = defaults_for_tool(tool_name)
        assert entry["evidence_kind"]
        assert entry["license"]


def test_no_default_table_entry_is_unspecified() -> None:
    for tool_name, entry in PER_TOOL_DEFAULTS.items():
        assert entry["license"] != "unspecified", tool_name


def test_defaults_for_unknown_tool_raises_rather_than_guesses() -> None:
    with pytest.raises(KeyError):
        defaults_for_tool("not_a_real_tool")


@pytest.mark.parametrize(
    ("tool_name", "expected_evidence_kind"),
    [
        ("ncbi_efetch", "primary_assertion"),
        ("ncbi_dbsnp", "primary_assertion"),
        ("pubtator_annotate", "literature_mention"),
        ("litvar2_lookup", "literature_mention"),
        ("pathogen_detection", "primary_assertion"),
        ("clinicaltrials_search", "external_annotation"),
    ],
)
def test_per_tool_evidence_kind_matches_section_9_2(
    tool_name: str, expected_evidence_kind: str
) -> None:
    assert defaults_for_tool(tool_name)["evidence_kind"] == expected_evidence_kind


@pytest.mark.parametrize(
    ("tool_name", "expected_license"),
    [
        ("ncbi_efetch", "public_domain_us_gov"),
        ("ncbi_dbsnp", "public_domain_us_gov"),
        ("pathogen_detection", "public_domain_us_gov"),
        ("clinicaltrials_search", "public_domain_us_gov"),
        ("pubtator_annotate", "publisher_copyright_abstract_only"),
        ("litvar2_lookup", "publisher_copyright_abstract_only"),
    ],
)
def test_per_tool_license_matches_section_9_2(
    tool_name: str, expected_license: str
) -> None:
    assert defaults_for_tool(tool_name)["license"] == expected_license


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("Pathogenic", "asserted"),
        ("likely_pathogenic", "asserted"),
        ("Benign", "asserted"),
        ("Uncertain significance", "hedged"),
        ("uncertain-significance", "hedged"),
        ("conflicting_interpretations_of_pathogenicity", "contested"),
        ("no_classifications_from_unflagged_records", "contested"),
        ("some_totally_unrecognized_future_term", "hedged"),
    ],
)
def test_clinvar_term_confidence(term: str, expected: str) -> None:
    assert clinvar_term_confidence(term) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This variant is pathogenic in affected individuals.", "asserted"),
        ("This variant may be associated with increased risk.", "hedged"),
        ("The mutation possibly disrupts protein function.", "hedged"),
        ("Preliminary evidence suggests a functional role.", "hedged"),
        ("This unlikelier outcome was not observed.", "asserted"),
    ],
)
def test_hedge_scan_confidence(text: str, expected: str) -> None:
    assert hedge_scan_confidence(text) == expected
