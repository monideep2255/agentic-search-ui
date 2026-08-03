"""Finding F-2.2-R-06: every degenerate representative value routes to the
row's CURIE, never ships as a claim.

A previous fix (finding J-10) added an explicit `field_value is None`
check to `_citable_value_for_row`, because a literal null shipped as the
string "None" at full confidence. A re-review found that fix caught only
the literal `None`, and it shipped with 977 tests green and no test
covering the gap; the J-10 mutant survived the whole suite. This file
exists so the next mutant does not.

Two things are asserted for every value below, matching the module
docstring's "Degenerate values, finding F-2.2-R-06" section:

1. Nothing degenerate reaches a claim: the returned `field_value` is
   never the raw degenerate input, never its Python repr, and never a
   string that would normalize to nothing.
2. The routing is to the CURIE fallback: `field_name == "curie"`,
   `field_value == <the row's curie>`, `curie_fallback is True`.

Also covered, per the module docstring's "be careful not to reject
legitimate values" instruction: `0` and a short real-looking string are
NOT degenerate and must ship as themselves, unchanged.

Depends on:
    - system_03_search_agent.synthesis.findings (_citable_value_for_row,
      build_synth_findings, SynthFinding)
    - system_03_search_agent.harness.coordinator_worker (Finding)

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    _citable_value_for_row,
    build_synth_findings,
)

_CURIE = "MedGen:C0346153"
_SOURCE_URL = "https://www.ncbi.nlm.nih.gov/medgen/C0346153"


def _stub(field_name: str, field_value: Any, is_suspect: bool = False) -> Any:
    """A `pick_representative_field` stand-in that ignores the row's real
    `fields` dict and always returns the fixed tuple under test, the same
    injection pattern `test_required_paths.py` already uses.
    """
    return lambda fields: (field_name, field_value, is_suspect)


def _row(curie: str = _CURIE) -> dict[str, Any]:
    return {"curie": curie, "fields": {"name": "irrelevant, the stub ignores this"}}


# ---------------------------------------------------------------------------
# The defect table, reproduced one row per case.
# ---------------------------------------------------------------------------


class TestDegenerateValuesRouteToCurieFallback:
    """Every value in finding F-2.2-R-06's verified table."""

    def test_a_bare_boolean_false_does_not_ship_as_a_named_claim(self) -> None:
        """The exact symptom quoted in the finding: ships "is named False"."""
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", False)
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert suspect is True
        assert value != "False"

    def test_a_bare_boolean_true_does_not_ship_as_a_named_claim(self) -> None:
        """Not in the finding's table verbatim, but the same defect shape as
        `False`: a bare flag is never a name, whichever way it points.
        """
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", True)
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert value != "True"

    def test_the_string_none_reproduces_the_original_j_10_symptom(self) -> None:
        """The exact J-10 symptom, from an ETL string rather than a literal
        null: `field_value is None` never catches this, because the value
        here is the four-character string "None", not Python's `None`.
        """
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "None")
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert value != "None"

    def test_the_string_null_is_also_a_sentinel(self) -> None:
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "null")
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert value != "null"

    def test_the_string_n_slash_a_is_also_a_sentinel(self) -> None:
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "N/A")
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert value != "N/A"

    def test_sentinel_matching_is_case_insensitive_and_strips_whitespace(self) -> None:
        """A real ETL export is not guaranteed to write the sentinel in one
        exact case or with no surrounding whitespace.
        """
        for raw in ("NONE", "  None  ", "Null", "n/a", "  N/A"):
            field, value, _suspect, fallback = _citable_value_for_row(
                _row(), _stub("name", raw)
            )
            assert (field, fallback) == ("curie", True), f"failed for {raw!r}"
            assert value == _CURIE

    def test_a_populated_list_does_not_ship_as_a_python_repr(self) -> None:
        """"a Python repr injected into the model's prompt" from the finding."""
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", [{"a": 1}])
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert "{" not in value and "'a'" not in value

    def test_an_empty_list_does_not_ship_and_silently_normalize_to_nothing(self) -> None:
        """The worse half of the finding: `str([])` is the non-blank text
        "[]", so the pre-fix blank check let it through, and it then
        normalized away to "" downstream, so a claim built from it could
        never ground. The fix must stop it here, before it becomes a claim
        at all.
        """
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", [])
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)

    def test_an_empty_dict_does_not_ship_and_silently_normalize_to_nothing(self) -> None:
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", {})
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)

    def test_a_lone_dash_is_a_sentinel(self) -> None:
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "-")
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert value != "-"

    def test_a_literal_none_still_falls_back_the_original_j_10_case(self) -> None:
        """The original fix, still exercised so a regression on the already
        -fixed case is caught here too, not only by inference from the new
        checks.
        """
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", None)
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)


class TestDegenerateFallbackIsHedged:
    """A degenerate value is evidence the row's own data is unreliable, the
    same signal `is_suspect` already carries for a vocabulary artifact
    (module docstring: "Why field_value sometimes falls back to the row's
    CURIE"). Every degenerate route above hedges, regardless of what
    `pick_representative_field` itself reported.
    """

    @pytest.mark.parametrize(
        "value",
        [False, True, "None", "null", "N/A", "-", [], {}, [{"a": 1}]],
    )
    def test_every_degenerate_shape_sets_value_is_suspect(self, value: Any) -> None:
        _field, _value, suspect, _fallback = _citable_value_for_row(
            _row(), _stub("name", value, is_suspect=False)
        )
        assert suspect is True


class TestDegenerateValueWithNoCurieIsNotCitableAtAll:
    """When the row carries no CURIE either, a degenerate value cannot
    fall back to anything, and `_citable_value_for_row` must say so by
    returning an empty field, not by inventing a value.
    """

    def test_a_degenerate_value_with_no_curie_returns_nothing_citable(self) -> None:
        field, value, _suspect, fallback = _citable_value_for_row(
            _row(curie=""), _stub("name", "None")
        )
        assert (field, value, fallback) == ("", "", False)


# ---------------------------------------------------------------------------
# Guard against over-rejection: not everything falsy or short is degenerate.
# ---------------------------------------------------------------------------


class TestLegitimateValuesAreNotRejected:
    """The module docstring is explicit: "Be careful NOT to reject
    legitimate values: 0 may be a genuine count, and a short string may be
    a real gene symbol." These tests pin that the fix did not overreach.
    """

    def test_the_integer_zero_ships_as_itself(self) -> None:
        """A zero-valued count or measurement (an exon count, a mutation
        count) is real data, not an absence. `isinstance(0, bool)` is
        False, so this must never be caught by the boolean check.
        """
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("mutation_count", 0)
        )
        assert (field, value, suspect, fallback) == ("mutation_count", "0", False, False)

    def test_a_nonzero_integer_ships_as_itself(self) -> None:
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("exon_count", 7)
        )
        assert (field, value, suspect, fallback) == ("exon_count", "7", False, False)

    def test_a_float_zero_ships_as_itself(self) -> None:
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("expression_level", 0.0)
        )
        assert (field, value, suspect, fallback) == (
            "expression_level",
            "0.0",
            False,
            False,
        )

    def test_a_short_real_looking_string_ships_as_itself(self) -> None:
        """A real gene symbol, not a sentinel. Must not collide with the
        sentinel set on length or shape alone.
        """
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("symbol", "P53")
        )
        assert (field, value, suspect, fallback) == ("symbol", "P53", False, False)

    def test_the_bare_string_na_without_a_slash_is_not_a_sentinel(self) -> None:
        """"na" (no slash) is deliberately excluded from the sentinel set,
        per the module docstring: it is also a plausible real value (an
        ISO country code, an abbreviation), unlike the slashed "N/A" the
        finding actually observed.
        """
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("region_code", "NA")
        )
        assert (field, value, suspect, fallback) == ("region_code", "NA", False, False)

    def test_an_ordinary_clean_string_is_unaffected(self) -> None:
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "BRCA1 DNA repair associated")
        )
        assert (field, value, suspect, fallback) == (
            "name",
            "BRCA1 DNA repair associated",
            False,
            False,
        )

    def test_an_upstream_suspect_string_still_falls_back_as_before(self) -> None:
        """The pre-existing vocabulary-artifact path (build phase 2.1,
        module docstring) must keep working unchanged: a clean-looking
        string that `pick_representative_field` itself flagged suspect
        still routes to the CURIE, hedged.
        """
        field, value, suspect, fallback = _citable_value_for_row(
            _row(), _stub("name", "MeSH", is_suspect=True)
        )
        assert (field, value, fallback) == ("curie", _CURIE, True)
        assert suspect is True


# ---------------------------------------------------------------------------
# End to end through build_synth_findings: the degenerate raw value must
# never reach the object that gets rendered into the Synth prompt.
# ---------------------------------------------------------------------------


def _finding_with_row(row: dict[str, Any]) -> Finding:
    return Finding(
        call_id="call-1",
        tool="cypher_query",
        layer="layer_1_graph",
        source="structured_pass_through",
        structured_fields={"status": "ok", "row_count": 1, "rows": [row]},
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


class TestBuildSynthFindingsNeverShipsADegenerateValue:
    def test_a_populated_list_value_becomes_a_curie_finding_end_to_end(self) -> None:
        row = {
            "curie": _CURIE,
            "source_url": _SOURCE_URL,
            "node_or_edge_type": "Disease",
            "fields": {"name": [{"a": 1}]},
        }
        findings, capped = build_synth_findings(
            [_finding_with_row(row)], _stub("name", [{"a": 1}])
        )
        assert capped is False
        assert len(findings) == 1
        result: SynthFinding = findings[0]
        assert result.field == "curie"
        assert result.field_value == _CURIE
        assert result.curie_fallback is True
        assert result.value_is_suspect is True
        # The raw degenerate value must not survive anywhere on the finding.
        assert "{" not in result.field_value
        assert "a" != result.field_value

    def test_an_empty_dict_value_becomes_a_curie_finding_end_to_end(self) -> None:
        row = {
            "curie": _CURIE,
            "source_url": _SOURCE_URL,
            "node_or_edge_type": "Disease",
            "fields": {"name": {}},
        }
        findings, _capped = build_synth_findings(
            [_finding_with_row(row)], _stub("name", {})
        )
        assert len(findings) == 1
        assert findings[0].field_value == _CURIE
        assert findings[0].curie_fallback is True

    def test_the_string_none_value_becomes_a_curie_finding_end_to_end(self) -> None:
        """The J-10 symptom, verified through the same public entry point
        the harness actually calls, not only through the private helper.
        """
        row = {
            "curie": _CURIE,
            "source_url": _SOURCE_URL,
            "node_or_edge_type": "Gene",
            "fields": {"name": "None"},
        }
        findings, _capped = build_synth_findings(
            [_finding_with_row(row)], _stub("name", "None")
        )
        assert len(findings) == 1
        assert findings[0].field_value == _CURIE
        assert findings[0].field_value != "None"

    def test_a_genuine_zero_count_ships_unchanged_end_to_end(self) -> None:
        row = {
            "curie": _CURIE,
            "source_url": _SOURCE_URL,
            "node_or_edge_type": "Gene",
            "fields": {"mutation_count": 0},
        }
        findings, _capped = build_synth_findings(
            [_finding_with_row(row)], _stub("mutation_count", 0)
        )
        assert len(findings) == 1
        assert findings[0].field == "mutation_count"
        assert findings[0].field_value == "0"
        assert findings[0].curie_fallback is False
