"""Tests for clinicaltrials_search_schemas.py (T-3.5-04).

No network. Covers, for the input side: the required `query_cond` field,
its `min_length=1` carve-out (design decision 2), `maxLength` boundaries
on every string field, `page_size`'s bounds (1 to 100 inclusive) and its
default of 20, the `overall_status` enum accepting every documented value
and rejecting an unrecognized one, and `extra="forbid"` rejecting an
unknown key. For the output side: every `maxLength`/`maxItems` cap
actually enforced (not just declared) on the top-level model and the
nested `ClinicalTrialsStudy` item model, the top-level `required` fields
(`status`, `studies`, `study_count`, `total_count`, `truncated`), the
`status` enum, `extra="forbid"` at every level, and `CLINICALTRIALS_HOST`
accepting a real ClinicalTrials.gov record URL while rejecting the API's
own fetch host/path, an NCBI-hosted URL, an unrelated host, and plain
HTTP.

What this file deliberately does NOT cover, per `goal-contracts`'s "a
verify surface must state its own coverage": how `clinicaltrials_search.py`
(T-3.5-06) parses a live ClinicalTrials.gov response into these shapes,
including the F-3.5-02 countTotal handling, the `designModule.phases`
array-to-string join, and the eligibility_summary truncation logic. This
file only proves the shapes themselves are correctly typed and bounded;
`test_clinicaltrials_search.py`'s job is the parsing correctness.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    CLINICALTRIALS_HOST,
    ClinicalTrialsSearchInput,
    ClinicalTrialsSearchOutput,
    ClinicalTrialsStudy,
)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def test_minimal_input_validates_with_only_query_cond() -> None:
    validated = ClinicalTrialsSearchInput(query_cond="BRCA1")
    assert validated.query_cond == "BRCA1"
    assert validated.query_term is None
    assert validated.query_intr is None
    assert validated.overall_status is None
    assert validated.page_size == 20
    assert validated.page_token is None


def test_full_input_validates_via_kwargs() -> None:
    """The exact construction path the premise gate's `_run` helper uses."""
    validated = ClinicalTrialsSearchInput(
        query_cond="breast cancer",
        query_term="tamoxifen",
        query_intr="chemotherapy",
        overall_status="RECRUITING",
        page_size=5,
        page_token="abc123",
    )
    assert validated.query_term == "tamoxifen"
    assert validated.query_intr == "chemotherapy"
    assert validated.overall_status == "RECRUITING"
    assert validated.page_size == 5
    assert validated.page_token == "abc123"


def test_missing_query_cond_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput()


def test_empty_query_cond_is_rejected_by_min_length() -> None:
    """Design decision 2: an empty query_cond must never reach the network."""
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="")


def test_query_cond_at_max_length_is_accepted() -> None:
    validated = ClinicalTrialsSearchInput(query_cond="x" * 200)
    assert len(validated.query_cond) == 200


def test_query_cond_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="x" * 201)


def test_query_term_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", query_term="x" * 201)


def test_query_intr_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", query_intr="x" * 201)


def test_page_token_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", page_token="x" * 201)


@pytest.mark.parametrize(
    "status",
    [
        "RECRUITING",
        "COMPLETED",
        "TERMINATED",
        "ACTIVE_NOT_RECRUITING",
        "NOT_YET_RECRUITING",
        "UNKNOWN",
    ],
)
def test_every_documented_overall_status_value_is_accepted(status: str) -> None:
    validated = ClinicalTrialsSearchInput(query_cond="BRCA1", overall_status=status)
    assert validated.overall_status == status


def test_unrecognized_overall_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", overall_status="NOT_A_REAL_STATUS")


def test_page_size_minimum_boundary() -> None:
    assert ClinicalTrialsSearchInput(query_cond="BRCA1", page_size=1).page_size == 1
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", page_size=0)


def test_page_size_maximum_boundary() -> None:
    assert ClinicalTrialsSearchInput(query_cond="BRCA1", page_size=100).page_size == 100
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", page_size=101)


def test_input_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchInput(query_cond="BRCA1", not_a_real_field="x")


# ---------------------------------------------------------------------------
# Output: top level
# ---------------------------------------------------------------------------


def test_output_required_fields_only_validates() -> None:
    output = ClinicalTrialsSearchOutput(
        status="empty", studies=[], study_count=0, total_count=0, truncated=False
    )
    assert output.next_page_token is None
    assert output.error is None


def test_output_missing_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchOutput(studies=[], study_count=0, total_count=0, truncated=False)


def test_output_status_enum_rejects_unrecognized_value() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchOutput(
            status="not_a_real_status", studies=[], study_count=0, total_count=0, truncated=False
        )


@pytest.mark.parametrize("status", ["ok", "empty", "error"])
def test_output_status_enum_accepts_every_documented_value(status: str) -> None:
    output = ClinicalTrialsSearchOutput(
        status=status, studies=[], study_count=0, total_count=0, truncated=False
    )
    assert output.status == status


def test_output_studies_maxitems_enforced() -> None:
    studies = [ClinicalTrialsStudy(nct_id=f"NCT{i:08d}") for i in range(50)]
    output = ClinicalTrialsSearchOutput(
        status="ok", studies=studies, study_count=50, total_count=50, truncated=False
    )
    assert len(output.studies) == 50
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchOutput(
            status="ok",
            studies=[ClinicalTrialsStudy(nct_id=f"NCT{i:08d}") for i in range(51)],
            study_count=51,
            total_count=51,
            truncated=False,
        )


def test_output_error_over_max_length_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchOutput(
            status="error",
            studies=[],
            study_count=0,
            total_count=0,
            truncated=False,
            error="x" * 501,
        )


def test_output_next_page_token_accepts_string_or_none() -> None:
    with_token = ClinicalTrialsSearchOutput(
        status="ok",
        studies=[],
        study_count=0,
        total_count=1,
        truncated=False,
        next_page_token="abc123",
    )
    assert with_token.next_page_token == "abc123"
    without_token = ClinicalTrialsSearchOutput(
        status="empty", studies=[], study_count=0, total_count=0, truncated=False
    )
    assert without_token.next_page_token is None


def test_output_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsSearchOutput(
            status="empty",
            studies=[],
            study_count=0,
            total_count=0,
            truncated=False,
            not_a_real_field="x",
        )


# ---------------------------------------------------------------------------
# Output: ClinicalTrialsStudy item model
# ---------------------------------------------------------------------------


def test_study_all_fields_default_to_none_or_empty() -> None:
    study = ClinicalTrialsStudy()
    assert study.nct_id is None
    assert study.brief_title is None
    assert study.overall_status is None
    assert study.conditions == []
    assert study.phase is None
    assert study.eligibility_summary is None
    assert study.source_url is None


def test_study_nct_id_max_length_enforced() -> None:
    ClinicalTrialsStudy(nct_id="x" * 15)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(nct_id="x" * 16)


def test_study_brief_title_max_length_enforced() -> None:
    ClinicalTrialsStudy(brief_title="x" * 300)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(brief_title="x" * 301)


def test_study_overall_status_max_length_enforced() -> None:
    ClinicalTrialsStudy(overall_status="x" * 30)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(overall_status="x" * 31)


def test_study_phase_max_length_enforced() -> None:
    ClinicalTrialsStudy(phase="x" * 30)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(phase="x" * 31)


def test_study_eligibility_summary_max_length_enforced() -> None:
    ClinicalTrialsStudy(eligibility_summary="x" * 500)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(eligibility_summary="x" * 501)


def test_study_conditions_item_max_length_enforced() -> None:
    ClinicalTrialsStudy(conditions=["x" * 100])
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(conditions=["x" * 101])


def test_study_conditions_maxitems_enforced() -> None:
    ClinicalTrialsStudy(conditions=["cond"] * 10)
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(conditions=["cond"] * 11)


def test_study_source_url_pattern_accepts_valid_record_url() -> None:
    study = ClinicalTrialsStudy(source_url="https://clinicaltrials.gov/study/NCT01230346")
    assert study.source_url == "https://clinicaltrials.gov/study/NCT01230346"


def test_study_source_url_pattern_accepts_www_subdomain() -> None:
    study = ClinicalTrialsStudy(source_url="https://www.clinicaltrials.gov/study/NCT01230346")
    assert study.source_url is not None


@pytest.mark.parametrize(
    "bad_url",
    [
        # The API's own fetch host/path, never a citable record page.
        "https://clinicaltrials.gov/api/v2/studies/NCT01230346",
        # An NCBI-hosted URL, the exact host-confusion trap this tool's
        # own CLINICALTRIALS_HOST pattern exists to close.
        "https://www.ncbi.nlm.nih.gov/study/NCT01230346",
        # An unrelated host.
        "https://evil.example.com/study/NCT01230346",
        # Plain HTTP, not HTTPS.
        "http://clinicaltrials.gov/study/NCT01230346",
    ],
)
def test_study_source_url_pattern_rejects_non_record_urls(bad_url: str) -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(source_url=bad_url)


def test_study_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsStudy(not_a_real_field="x")


# ---------------------------------------------------------------------------
# CLINICALTRIALS_HOST, direct pattern checks (belt and suspenders on top of
# the module's own import-time self-verification block).
# ---------------------------------------------------------------------------


def test_clinicaltrials_host_pattern_is_never_ncbi_scoped() -> None:
    """The phase's own explicitly-named trap: never NCBI_RECORD_HOST reused here."""
    assert "ncbi" not in CLINICALTRIALS_HOST.lower()
    assert "clinicaltrials" in CLINICALTRIALS_HOST.lower()


def test_clinicaltrials_host_pattern_requires_study_path() -> None:
    import re

    assert re.match(CLINICALTRIALS_HOST, "https://clinicaltrials.gov/") is None
    assert re.match(CLINICALTRIALS_HOST, "https://clinicaltrials.gov/study/") is not None
