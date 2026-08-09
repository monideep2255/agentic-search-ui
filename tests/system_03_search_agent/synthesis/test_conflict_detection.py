"""Unit tests for `synthesis.conflict_detection`. See that module's
docstring for the Section 7.2 rule this enforces."""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis.conflict_detection import detect_conflict


def test_identical_values_are_not_a_conflict() -> None:
    result = detect_conflict(
        field="official_symbol",
        graph_value="BRCA1",
        live_value="BRCA1",
        graph_source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        live_source_url="https://www.ncbi.nlm.nih.gov/datasets/gene/672",
    )
    assert result.is_conflict is False


def test_case_and_whitespace_differences_are_not_a_conflict() -> None:
    result = detect_conflict(
        field="official_symbol",
        graph_value="  brca1 ",
        live_value="BRCA1",
        graph_source_url=None,
        live_source_url=None,
    )
    assert result.is_conflict is False


def test_genuinely_different_values_are_a_conflict() -> None:
    result = detect_conflict(
        field="official_symbol",
        graph_value="BRCA1",
        live_value="TP53",
        graph_source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        live_source_url="https://www.ncbi.nlm.nih.gov/datasets/gene/672",
    )
    assert result.is_conflict is True


def test_a_conflict_result_always_carries_both_source_urls() -> None:
    result = detect_conflict(
        field="official_symbol",
        graph_value="BRCA1",
        live_value="TP53",
        graph_source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        live_source_url="https://www.ncbi.nlm.nih.gov/datasets/gene/672",
    )
    assert result.graph_source_url == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert result.live_source_url == "https://www.ncbi.nlm.nih.gov/datasets/gene/672"


def test_a_missing_source_url_is_carried_as_none_not_fabricated() -> None:
    result = detect_conflict(
        field="official_symbol",
        graph_value="BRCA1",
        live_value="TP53",
        graph_source_url=None,
        live_source_url=None,
    )
    assert result.graph_source_url is None
    assert result.live_source_url is None


@pytest.mark.parametrize("value", [None, 42, ["a", "b"]])
def test_non_string_values_are_normalized_without_raising(value: object) -> None:
    detect_conflict(
        field="x", graph_value=value, live_value=value,
        graph_source_url=None, live_source_url=None,
    )
