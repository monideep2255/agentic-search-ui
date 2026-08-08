"""Tests for litvar2_lookup_schemas.py (T-3.3-04).

No network. Covers, for the input side, both `mode` branches validating
through `Litvar2LookupInput(**payload)` and `Litvar2LookupInput.model_validate`,
the `minLength: 1` carve-out on `query` and `litvar_id` (F-3.3-02's sibling
concern), `extra="forbid"` rejecting an unknown key on both branches, the
`maxLength` boundaries, and an unrecognized `mode` value being rejected. For
the output side: every `maxLength`/`maxItems` cap actually enforced (not
just declared) on the top-level model and the nested `Litvar2VariantMatch`
item model, the two required fields (`status`, `mode`), the `status` enum,
`extra="forbid"` at every level, `fields_withheld`'s `list[str] | None`
shape and its own caps, the additive `Litvar2VariantMatch.matched_on` field
(F-3.3-A-01/F-3.3-A-02, fix round 3: defaults to `None`, accepts a real
value, `max_length=200`), and `NCBI_LITVAR2_RECORD_URL_PATTERN` accepting a
real LitVar2/PubMed URL while rejecting a non-NCBI host and a plain-HTTP
scheme.

What this file deliberately does NOT cover, per `goal-contracts`'s "a
verify surface must state its own coverage": how `litvar2_lookup.py`
(T-3.3-06) parses a live LitVar2 response into these shapes, including the
F-3.3-03 withhold-not-truncate behavior. This file only proves the shapes
themselves are correctly typed and bounded; `test_litvar2_lookup.py`'s job
is the parsing correctness.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.litvar2_lookup_schemas import (
    NCBI_LITVAR2_RECORD_URL_PATTERN,
    Litvar2LookupInput,
    Litvar2LookupOutput,
    Litvar2PublicationsLookupInput,
    Litvar2VariantMatch,
    Litvar2VariantSearchInput,
)

# ---------------------------------------------------------------------------
# Input: both mode branches, from the spec's documented shape.
# ---------------------------------------------------------------------------


def test_variant_search_mode_validates_via_kwargs() -> None:
    """The exact construction path the premise gate's `_run` helper uses."""
    validated = Litvar2LookupInput(mode="variant_search", query="rs334")
    assert isinstance(validated.root, Litvar2VariantSearchInput)
    assert validated.root.query == "rs334"


def test_variant_search_mode_validates_via_model_validate() -> None:
    validated = Litvar2LookupInput.model_validate({"mode": "variant_search", "query": "rs334"})
    assert validated.root.mode == "variant_search"


def test_publications_lookup_mode_validates() -> None:
    validated = Litvar2LookupInput(mode="publications_lookup", litvar_id="litvar@rs334##")
    assert isinstance(validated.root, Litvar2PublicationsLookupInput)
    assert validated.root.litvar_id == "litvar@rs334##"


def test_unrecognized_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="entity_lookup", query="rs334")


def test_variant_search_missing_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="variant_search")


def test_publications_lookup_missing_litvar_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="publications_lookup")


def test_variant_search_empty_query_is_rejected_by_min_length() -> None:
    """F-3.3-02's sibling concern: an empty query must never reach the network."""
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="variant_search", query="")


def test_publications_lookup_empty_litvar_id_is_rejected_by_min_length() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="publications_lookup", litvar_id="")


def test_variant_search_query_max_length_boundary() -> None:
    ok = Litvar2LookupInput(mode="variant_search", query="q" * 100)
    assert len(ok.root.query) == 100
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="variant_search", query="q" * 101)


def test_publications_lookup_litvar_id_max_length_boundary() -> None:
    ok = Litvar2LookupInput(mode="publications_lookup", litvar_id="x" * 60)
    assert len(ok.root.litvar_id) == 60
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="publications_lookup", litvar_id="x" * 61)


def test_variant_search_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="variant_search", query="rs334", bogus="nope")


def test_publications_lookup_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="publications_lookup", litvar_id="litvar@rs334##", bogus="nope")


def test_variant_search_cannot_carry_litvar_id() -> None:
    """A payload naming the WRONG branch's own required field, per its mode, is rejected."""
    with pytest.raises(ValidationError):
        Litvar2LookupInput(mode="variant_search", litvar_id="litvar@rs334##")


# ---------------------------------------------------------------------------
# Output: required fields, status enum, extra="forbid".
# ---------------------------------------------------------------------------

MINIMAL_OUTPUT_DICT = {"status": "ok", "mode": "variant_search"}


def test_output_minimal_required_fields_validate() -> None:
    validated = Litvar2LookupOutput.model_validate(MINIMAL_OUTPUT_DICT)
    assert validated.status == "ok"
    assert validated.mode == "variant_search"
    assert validated.variant_matches == []
    assert validated.pmids == []
    assert validated.total_pmids == 0
    assert validated.source_url is None
    assert validated.error is None
    assert validated.fields_withheld is None


def test_output_missing_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({"mode": "variant_search"})


def test_output_missing_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({"status": "ok"})


@pytest.mark.parametrize("status", ["ok", "empty", "error"])
def test_output_status_enum_accepts_documented_values(status: str) -> None:
    validated = Litvar2LookupOutput.model_validate({"status": status, "mode": "variant_search"})
    assert validated.status == status


def test_output_status_rejects_undocumented_value() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({"status": "partial", "mode": "variant_search"})


def test_output_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "bogus": "nope"})


def test_output_mode_max_length_boundary() -> None:
    ok = Litvar2LookupOutput.model_validate({"status": "ok", "mode": "m" * 25})
    assert len(ok.mode) == 25
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({"status": "ok", "mode": "m" * 26})


def test_output_variant_matches_max_items_boundary() -> None:
    ten = [{"litvar_id": f"litvar@rs{i}##"} for i in range(10)]
    ok = Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "variant_matches": ten})
    assert len(ok.variant_matches) == 10

    eleven = [{"litvar_id": f"litvar@rs{i}##"} for i in range(11)]
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "variant_matches": eleven})


def test_output_pmids_max_items_boundary() -> None:
    fifty = [str(i) for i in range(50)]
    ok = Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "pmids": fifty})
    assert len(ok.pmids) == 50

    fifty_one = [str(i) for i in range(51)]
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "pmids": fifty_one})


def test_output_pmids_item_max_length_boundary() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "pmids": ["1" * 16]})


# ---------------------------------------------------------------------------
# total_variant_matches: additive, F-3.3-A-12.
# ---------------------------------------------------------------------------


def test_output_total_variant_matches_defaults_to_zero() -> None:
    validated = Litvar2LookupOutput.model_validate(MINIMAL_OUTPUT_DICT)
    assert validated.total_variant_matches == 0


def test_output_total_variant_matches_accepts_a_count_above_the_cap() -> None:
    """The whole point of this field: it can legitimately exceed len(variant_matches)."""
    ten = [{"litvar_id": f"litvar@rs{i}##"} for i in range(10)]
    validated = Litvar2LookupOutput.model_validate(
        {**MINIMAL_OUTPUT_DICT, "variant_matches": ten, "total_variant_matches": 37}
    )
    assert validated.total_variant_matches == 37
    assert len(validated.variant_matches) == 10


def test_output_total_variant_matches_negative_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "total_variant_matches": -1})


def test_output_source_url_accepts_matching_pattern() -> None:
    validated = Litvar2LookupOutput.model_validate(
        {**MINIMAL_OUTPUT_DICT, "source_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334"}
    )
    assert validated.source_url is not None


def test_output_source_url_rejects_non_ncbi_host() -> None:
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "source_url": "https://evil.example.com/"})


def test_output_error_max_length_boundary() -> None:
    ok = Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "error": "e" * 500})
    assert len(ok.error) == 500
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "error": "e" * 501})


# ---------------------------------------------------------------------------
# fields_withheld: additive, list[str] | None, F-3.3-03.
# ---------------------------------------------------------------------------


def test_fields_withheld_defaults_to_none() -> None:
    validated = Litvar2LookupOutput.model_validate(MINIMAL_OUTPUT_DICT)
    assert validated.fields_withheld is None


def test_fields_withheld_accepts_a_real_note() -> None:
    validated = Litvar2LookupOutput.model_validate(
        {
            **MINIMAL_OUTPUT_DICT,
            "fields_withheld": [
                "variant_matches[0].clinical_significance: conflicting-interpretations-of-pathogenicity"
            ],
        }
    )
    assert validated.fields_withheld is not None
    assert len(validated.fields_withheld) == 1


def test_fields_withheld_item_max_length_boundary() -> None:
    ok = Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "fields_withheld": ["n" * 150]})
    assert len(ok.fields_withheld[0]) == 150
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "fields_withheld": ["n" * 151]})


def test_fields_withheld_max_items_boundary() -> None:
    twenty = [f"note-{i}" for i in range(20)]
    ok = Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "fields_withheld": twenty})
    assert len(ok.fields_withheld) == 20

    twenty_one = [f"note-{i}" for i in range(21)]
    with pytest.raises(ValidationError):
        Litvar2LookupOutput.model_validate({**MINIMAL_OUTPUT_DICT, "fields_withheld": twenty_one})


# ---------------------------------------------------------------------------
# Litvar2VariantMatch: nested item model, caps and extra="forbid".
# ---------------------------------------------------------------------------


def test_variant_match_full_shape_validates() -> None:
    match = Litvar2VariantMatch.model_validate(
        {
            "litvar_id": "litvar@rs334##",
            "rsid": "rs334",
            "gene": ["HBB"],
            "name": "c.20A>T",
            "hgvs": "c.20A>T",
            "pmids_count": 590,
            "clinical_significance": ["protective", "pathogenic"],
        }
    )
    assert match.rsid == "rs334"
    assert match.pmids_count == 590


def test_variant_match_all_fields_optional() -> None:
    match = Litvar2VariantMatch.model_validate({})
    assert match.litvar_id is None
    assert match.rsid is None
    assert match.gene == []
    assert match.pmids_count == 0


def test_variant_match_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        Litvar2VariantMatch.model_validate({"litvar_id": "litvar@rs334##", "bogus": "nope"})


def test_variant_match_gene_max_items_boundary() -> None:
    five = ["G1", "G2", "G3", "G4", "G5"]
    ok = Litvar2VariantMatch.model_validate({"gene": five})
    assert len(ok.gene) == 5
    with pytest.raises(ValidationError):
        Litvar2VariantMatch.model_validate({"gene": [*five, "G6"]})


def test_variant_match_clinical_significance_item_max_length_boundary() -> None:
    ok = Litvar2VariantMatch.model_validate({"clinical_significance": ["c" * 30]})
    assert len(ok.clinical_significance[0]) == 30
    with pytest.raises(ValidationError):
        Litvar2VariantMatch.model_validate({"clinical_significance": ["c" * 31]})


# ---------------------------------------------------------------------------
# matched_on: additive, F-3.3-A-01/F-3.3-A-02 (fix round 3).
# ---------------------------------------------------------------------------


def test_variant_match_matched_on_defaults_to_none() -> None:
    match = Litvar2VariantMatch.model_validate({})
    assert match.matched_on is None


def test_variant_match_matched_on_accepts_a_real_value() -> None:
    match = Litvar2VariantMatch.model_validate(
        {"matched_on": "Matched on all_hgvs <m>3344|p.V66M</m>"}
    )
    assert match.matched_on == "Matched on all_hgvs <m>3344|p.V66M</m>"


def test_variant_match_matched_on_max_length_boundary() -> None:
    ok = Litvar2VariantMatch.model_validate({"matched_on": "m" * 200})
    assert len(ok.matched_on) == 200
    with pytest.raises(ValidationError):
        Litvar2VariantMatch.model_validate({"matched_on": "m" * 201})


# ---------------------------------------------------------------------------
# NCBI_LITVAR2_RECORD_URL_PATTERN, directly.
# ---------------------------------------------------------------------------


def test_pattern_accepts_real_litvar2_ui_url() -> None:
    import re

    assert re.match(
        NCBI_LITVAR2_RECORD_URL_PATTERN,
        "https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334",
    )


def test_pattern_accepts_real_pubmed_url() -> None:
    import re

    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, "https://pubmed.ncbi.nlm.nih.gov/33593344/")


def test_pattern_accepts_the_dbsnp_record_url() -> None:
    """F-3.3-J-06, design decision 7: the pattern is host-only, so the new
    /snp/{rsid} citation target litvar2_lookup.py now prefers needs no
    change here; confirmed directly rather than assumed.
    """
    import re

    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, "https://www.ncbi.nlm.nih.gov/snp/rs334")


def test_pattern_rejects_non_ncbi_host() -> None:
    import re

    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, "https://evil.example.com/ncbi.nlm.nih.gov/") is None


def test_pattern_rejects_plain_http() -> None:
    import re

    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, "http://www.ncbi.nlm.nih.gov/research/litvar2/") is None
