"""Tests for the AGE agtype text parser (phase 2.1 defect fix, finding
F-2.1-A1).

Depends on:
    - system_03_search_agent.tools.agtype
      (parse_agtype, strip_agtype_suffix, is_vertex_or_edge)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.tools.agtype import (
    is_vertex_or_edge,
    parse_agtype,
    strip_agtype_suffix,
)

# ---------------------------------------------------------------------------
# strip_agtype_suffix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_payload", "expected_suffix"),
    [
        ('{"a": 1}::vertex', '{"a": 1}', "vertex"),
        ('{"a": 1}::edge', '{"a": 1}', "edge"),
        ("[1, 2]::path", "[1, 2]", "path"),
        ('{"a": 1}', '{"a": 1}', None),
        ("42", "42", None),
    ],
)
def test_strip_agtype_suffix_splits_payload_and_suffix(
    text: str, expected_payload: str, expected_suffix: str | None
) -> None:
    payload, suffix = strip_agtype_suffix(text)
    assert payload == expected_payload
    assert suffix == expected_suffix


# ---------------------------------------------------------------------------
# parse_agtype: the real wire-format shapes AGE emits.
# ---------------------------------------------------------------------------


def test_parse_agtype_parses_a_vertex() -> None:
    text = (
        '{"id": 1125899906858506, "label": "SequenceVariant", "properties": '
        '{"id": "ClinVar:17660", "name": "NM_007294.4(BRCA1):c.190T>G (p.Cys64Gly)"}}::vertex'
    )

    parsed = parse_agtype(text)

    assert parsed["label"] == "SequenceVariant"
    assert parsed["properties"]["id"] == "ClinVar:17660"


def test_parse_agtype_parses_an_edge() -> None:
    text = (
        '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
        '"end_id": 2, "properties": {}}::edge'
    )

    parsed = parse_agtype(text)

    assert parsed["label"] == "is_sequence_variant_of"
    assert parsed["start_id"] == 1
    assert parsed["end_id"] == 2


def test_parse_agtype_parses_a_path() -> None:
    text = '[{"id": 1, "label": "Gene", "properties": {}}]::path'

    parsed = parse_agtype(text)

    assert isinstance(parsed, list)
    assert parsed[0]["label"] == "Gene"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"a string"', "a string"),
        ("42", 42),
        ("3.14", 3.14),
        ("true", True),
        ("false", False),
        ("null", None),
    ],
)
def test_parse_agtype_parses_bare_scalars(text: str, expected: object) -> None:
    assert parse_agtype(text) == expected


# ---------------------------------------------------------------------------
# parse_agtype: pre-parsed input is never double-parsed.
# ---------------------------------------------------------------------------


def test_parse_agtype_returns_a_dict_input_unchanged() -> None:
    already_parsed = {"label": "Gene", "properties": {"id": "NCBIGene:672"}}

    assert parse_agtype(already_parsed) is already_parsed


def test_parse_agtype_returns_a_list_input_unchanged() -> None:
    already_parsed = [{"label": "Gene", "properties": {}}]

    assert parse_agtype(already_parsed) is already_parsed


def test_parse_agtype_returns_native_scalars_unchanged() -> None:
    assert parse_agtype(42) == 42
    assert parse_agtype(3.14) == 3.14
    assert parse_agtype(True) is True


def test_parse_agtype_returns_none_for_none() -> None:
    assert parse_agtype(None) is None


# ---------------------------------------------------------------------------
# parse_agtype: malformed input degrades deterministically, never raises.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not valid json at all {{{",
        "{unterminated::vertex",
        "{'single': 'quotes'}::vertex",
    ],
)
def test_parse_agtype_never_raises_on_malformed_input(value: str) -> None:
    assert parse_agtype(value) is None


def test_parse_agtype_never_raises_on_an_unsupported_type() -> None:
    class NotAgtype:
        pass

    assert parse_agtype(NotAgtype()) is None


# ---------------------------------------------------------------------------
# is_vertex_or_edge
# ---------------------------------------------------------------------------


def test_is_vertex_or_edge_true_for_a_dict_with_a_label() -> None:
    assert is_vertex_or_edge({"label": "Gene", "properties": {}}) is True


@pytest.mark.parametrize(
    "value",
    [
        {"properties": {}},
        {"symbol": "BRCA1"},
        "a string",
        42,
        None,
        [{"label": "Gene"}],
    ],
)
def test_is_vertex_or_edge_false_for_everything_else(value: object) -> None:
    assert is_vertex_or_edge(value) is False
