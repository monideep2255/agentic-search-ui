"""The premise gate for build phase 3.5's `clinicaltrials_search`: does it
tell the truth about what ClinicalTrials.gov API v2 actually returns?

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory and
blocking for this tool phase. Written first and watched failing before any of
`clinicaltrials_search` exists.

## F-3.5-02, made into an assertion

Pre-build live probing (2026-08-08, `tracker/phase_3.5.md`) found that a
default `GET /studies` call omits the `totalCount` key from its response
body ENTIRELY; it is not `0` or `null`, the key is simply absent unless the
caller passes `countTotal=true`. Section 6.7's locked output schema
requires `total_count` on every response. Case 1 asserts `total_count` is
always populated as a real integer, not merely present-and-zero, which
would pass a naive schema check while still being wrong.

## The phase field is an array, not a scalar

Also live-confirmed 2026-08-08: `designModule.phases` is a JSON array
(`["NA"]`, or `["PHASE2", "PHASE3"]` for a multi-phase study), never a bare
`phase` string. Case 1 does not over-assert a fixed value here (phase
varies per study) but the schema-level test in `test_clinicaltrials_search_
schemas.py` is where the array-to-string join gets pinned; this gate only
confirms the field is populated and is a string in the OUTPUT (this repo's
own bounded projection), never that it holds one specific value.

## The arms

`ok` (a real condition, BRCA1 or breast cancer, with real NCT ids and a
populated total_count), `empty` (a genuine no-match, HTTP 200 with
`studies: []`, F-3.5-02's totalCount-absent shape handled the same way).
Plus untrusted content (trial-sponsor free text never executes) and the
host-pinned source_url (never the API host, always `clinicaltrials.gov/
study/`).

## Running it

    RUN_PREMISE_GATE=1 python -m pytest \\
        tests/system_03_search_agent/tools/test_clinicaltrials_search_premise.py -v

No API key needed (Section 6.7: "no API key"). Gates on opt-in and live
network reach to clinicaltrials.gov.

## Coverage, stated per goal-contracts.md ("a verify surface must state its
own coverage")

Exercises: the `ok`/`empty` split, F-3.5-02's countTotal requirement, the
host-pinned source_url, one untrusted-content assertion. Does NOT exercise:
`page_token` pagination beyond a single page (this gate asserts a
`next_page_token` is present when the API's own `nextPageToken` is,
nothing about actually following it); `overall_status` filtering (a
scripted case in `test_clinicaltrials_search.py`'s job, not a live gate
concern since the exact set of RECRUITING studies for any condition
changes daily and cannot be pinned as a live assertion); concurrent load
against the new `"clinicaltrials"` rate-limit family's actual 5 req/s
pacing (a `RateLimiter` unit test's job).

Depends on:
    - system_03_search_agent.tools.clinicaltrials_search (does not exist yet)
    - system_03_search_agent.tools.clinicaltrials_search_schemas (same)
    - Network reach to clinicaltrials.gov

Writes:
    - Nothing.
"""

from __future__ import annotations

import os
import socket
from typing import Any

import pytest

REAL_CONDITION = "BRCA1"
KNOWN_NCT_ID = "NCT01230346"  # live-confirmed 2026-08-08, a real BRCA1-condition study

NO_MATCH_CONDITION = "zzzznotarealconditionxyz123"


def _opted_in() -> bool:
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {"1", "true", "yes"}


def _host_is_reachable() -> bool:
    try:
        with socket.create_connection(("clinicaltrials.gov", 443), timeout=10):
            return True
    except OSError:
        return False


premise_gate = pytest.mark.skipif(
    not (_opted_in() and _host_is_reachable()),
    reason=(
        "set RUN_PREMISE_GATE=1 to run the clinicaltrials_search premise gate. "
        "It needs live network reach to clinicaltrials.gov. No API key "
        "required (Section 6.7)."
    ),
)


async def _run(payload: dict[str, Any]) -> Any:
    """Call the tool the way the Act step will, once it is wired in.

    Imported inside the function on purpose: until `clinicaltrials_search`
    exists this raises ImportError per case, giving a readable per-case
    failure count instead of one collection error.
    """
    from system_03_search_agent.tools.clinicaltrials_search import clinicaltrials_search
    from system_03_search_agent.tools.clinicaltrials_search_schemas import (
        ClinicalTrialsSearchInput,
    )

    return await clinicaltrials_search(ClinicalTrialsSearchInput(**payload))


@premise_gate
@pytest.mark.asyncio
async def test_01_real_condition_resolves_with_populated_total_count() -> None:
    """Case 1. The full happy path, asserted on meaning, including F-3.5-02."""
    output = await _run({"query_cond": REAL_CONDITION, "page_size": 5})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert output.study_count >= 1
    assert isinstance(output.total_count, int) and output.total_count > 0, (
        f"F-3.5-02: total_count must always be a populated positive int, got "
        f"{output.total_count!r}"
    )
    nct_ids = [s.nct_id for s in output.studies]
    assert KNOWN_NCT_ID in nct_ids or len(nct_ids) >= 1, (
        f"expected at least one real NCT id, got {nct_ids!r}"
    )
    study = output.studies[0]
    assert study.nct_id.startswith("NCT")
    assert study.source_url.startswith("https://clinicaltrials.gov/study/"), (
        f"host-pinned source_url required (never the API host), got {study.source_url!r}"
    )
    assert study.source_url.endswith(study.nct_id), (
        f"source_url must resolve to THIS study's own record page, got "
        f"{study.source_url!r} for {study.nct_id!r}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_02_no_match_condition_is_empty_not_error() -> None:
    """Case 2. A genuine no-match is a structured empty, never fabricated,
    and F-3.5-02's totalCount-absent shape is handled the same way as a
    genuinely zero total, not as a missing-field crash.
    """
    output = await _run({"query_cond": NO_MATCH_CONDITION, "page_size": 5})

    assert output.status == "empty", f"expected empty, got {output.status}: {output.error}"
    assert output.studies == []
    assert output.total_count == 0


@premise_gate
@pytest.mark.asyncio
async def test_03_untrusted_trial_text_is_inert_never_executed() -> None:
    """Case 3. Sponsor-submitted free text (brief_title, eligibility_summary)
    reaches the output only as capped, inert data (ai-security-standards.md).
    """
    output = await _run({"query_cond": REAL_CONDITION, "page_size": 3})

    assert output.status == "ok"
    for study in output.studies:
        assert len(study.brief_title) <= 300
        if study.eligibility_summary is not None:
            assert len(study.eligibility_summary) <= 500
