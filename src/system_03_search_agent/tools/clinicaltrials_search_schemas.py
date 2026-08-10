"""Pydantic v2 input and output schemas for the clinicaltrials_search tool (T-3.5-04).

Technical_specification.md Section 6.7 locks the JSON schema for both the
tool input and the tool output (see `tracker/phase_3.5.md`'s reproduction
and its pre-build live probes). These models are the typed, validated
implementation of that lock: every field, length cap, enum, and pattern
here mirrors the spec's `clinicaltrials_search.input` and
`clinicaltrials_search.output` JSON schemas exactly, plus `extra="forbid"`
on every model with its own field set so an unexpected field is rejected
rather than silently dropped or passed through
(production-standards.md's multi-agent pipeline gate).

Design decision 1, a flat input, not a discriminated union. Unlike
`litvar2_lookup_schemas.py` (a genuine `oneOf` on `mode`) or
`ncbi_efetch_schemas.py`, Section 6.7 names exactly one shape: a single
optional-heavy object with one required field (`query_cond`). There is no
`mode` or action discriminator anywhere in the locked schema, so
`ClinicalTrialsSearchInput` is a plain `BaseModel`, the same flat-shape
choice `ncbi_dbsnp_schemas.py`'s own design decision 1 documents for its
three `query_type` values that share one shape (this tool has no
`query_type` at all, an even simpler case).

Design decision 2, `query_cond` gets `min_length=1`, additive beyond
Section 6.7's own `maxLength: 200`. The locked schema's own `maxLength`
cap does not by itself reject an empty string, and an empty `query.cond`
sent to ClinicalTrials.gov's `/studies` endpoint is not a shape this
phase's pre-build probes verified (every probe used a real condition
string, `BRCA1` or a deliberately-nonsense one, never `""`). Rejecting an
empty value here, before any network call, closes the only realistic path
a caller could reach an unverified shape from in production, the same
reasoning `litvar2_lookup_schemas.py`'s design decision 2 states for its
own required fields.

Design decision 3, `CLINICALTRIALS_HOST`, a new host-pinned pattern, never
`NCBI_RECORD_HOST` or any NCBI-scoped pattern. `docs/ncbi/
Tool_implementation_mechanics.md`'s clinicaltrials_search section names
this as the phase's own explicit trap: ClinicalTrials.gov is a different
domain entirely from every other tool in the roster, so reusing an
`ncbi.nlm.nih.gov`-scoped regex would either reject every valid citation
outright or, loosened carelessly to compensate, defeat the purpose of
host-pinning at all. `CLINICALTRIALS_HOST` is Section 6.7's own locked
pattern (line 1411), copied verbatim: `^https://(www\\.)?clinicaltrials\\.
gov/study/`, scoped to the `/study/` path segment specifically, not just
the bare host, so a hypothetical future citation of the API's own fetch
path (`clinicaltrials.gov/api/v2/studies/...`) would NOT validate against
it either. This is a stronger guarantee than `litvar2_lookup_schemas.
NCBI_LITVAR2_RECORD_URL_PATTERN` can offer (that pattern is host-only,
unscoped by path, because LitVar2's fetch host and UI host share one
hostname): here, the fetch host (`clinicaltrials.gov/api/v2/studies`) and
the citable record host (`clinicaltrials.gov/study/{nctId}`) share a
domain but not a path, so the path requirement alone is enough to keep the
two apart.

Design decision 4, `eligibility_summary` is this repo's own bounded
projection of ClinicalTrials.gov's full free-text eligibility criteria
block, not a field the API itself returns pre-summarized. Confirmed live
2026-08-08 (`tracker/phase_3.5.md`'s pre-build probes): `eligibilityModule.
eligibilityCriteria` is the full, unsummarized criteria text, frequently
well over the schema's own 500-char cap. `clinicaltrials_search.py`
truncates it cleanly (never crashes on an over-length value, per this
ticket's own instruction), so `eligibility_summary` is always `str | None`
here rather than a value the schema can assume is already in range from
upstream.

Design decision 5, `phase` is a `str`, not the raw `designModule.phases`
array ClinicalTrials.gov actually returns. Confirmed live 2026-08-08:
`designModule.phases` is a JSON array (`["NA"]`, or `["PHASE2",
"PHASE3"]` for a multi-phase study), never a bare scalar. Section 6.7's
own locked output schema names `phase` as a `string`, so
`clinicaltrials_search.py` joins the array before this schema ever sees
it (`", ".join(phases)`); this file only enforces the resulting string's
own `maxLength: 30` cap, it does not itself perform the join.

Depends on:
    - Nothing repo-local. `CLINICALTRIALS_HOST` is defined here, not
      imported from any sibling tool schema file, per the same
      never-share-a-record-URL-pattern-across-tools discipline
      `litvar2_lookup_schemas.py`'s design decision 3 documents.

Reads:
    - Nothing at import time, beyond its own self-verification assertions
      against literal sample strings (no environment, no filesystem).

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.clinicaltrials_search (T-3.5-06)
    - system_03_search_agent.harness.cache, for tool schema registration
      (T-3.5-07, not yet written, out of this ticket's scope)
    - tests/system_03_search_agent/tools/test_clinicaltrials_search_premise.py,
      via `ClinicalTrialsSearchInput(**payload)` and
      `ClinicalTrialsSearchOutput` attribute access
    - tests/system_03_search_agent/tools/test_clinicaltrials_search.py
    - tests/system_03_search_agent/tools/test_clinicaltrials_search_schemas.py
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

# Section 6.7 line 1411, copied verbatim. Deliberately NOT
# ncbi_efetch_schemas.NCBI_RECORD_HOST or any other tool's NCBI-scoped
# pattern: see design decision 3 in the module docstring for why
# clinicaltrials.gov, a genuinely different domain, needs its own pattern,
# and why this one is additionally scoped to the /study/ path segment.
CLINICALTRIALS_HOST: Final = r"^https://(www\.)?clinicaltrials\.gov/study/"

_OverallStatus = Literal[
    "RECRUITING",
    "COMPLETED",
    "TERMINATED",
    "ACTIVE_NOT_RECRUITING",
    "NOT_YET_RECRUITING",
    "UNKNOWN",
]


# ---------------------------------------------------------------------------
# Input: one flat shape, Section 6.7's `clinicaltrials_search.input`.
# ---------------------------------------------------------------------------


class ClinicalTrialsSearchInput(BaseModel):
    """The tool's single input shape. Section 6.7 names no `mode` or action
    discriminator; see design decision 1 in the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    query_cond: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description=(
                "condition or disease phrase, maps to query.cond. Parsed by "
                "ClinicalTrials.gov as an Essie search expression, not a "
                "literal phrase: a condition name containing AND, OR, or NOT "
                "(e.g. \"Carcinoma NOT Otherwise Specified\") is interpreted "
                "as a boolean operator and can silently return the logical "
                "inverse of the intended search (F-3.5-A-03)."
            ),
        ),
    ]
    query_term: Annotated[
        str | None,
        Field(default=None, max_length=200, description="free text, maps to query.term"),
    ] = None
    query_intr: Annotated[
        str | None,
        Field(default=None, max_length=200, description="intervention, maps to query.intr"),
    ] = None
    overall_status: Annotated[_OverallStatus | None, Field(default=None)] = None
    page_size: Annotated[int, Field(default=20, ge=1, le=100)] = 20
    page_token: Annotated[str | None, Field(default=None, max_length=200)] = None


# ---------------------------------------------------------------------------
# Output: Section 6.7's `clinicaltrials_search.output`.
# ---------------------------------------------------------------------------


class ClinicalTrialsStudy(BaseModel):
    """One study from `GET /studies`. Section 6.7's item schema (lines
    ~1390-1408) carries no `required` list of its own, so every field here
    is schema-optional with a default, the same "only what the spec's own
    top-level `required` list names is required" discipline
    `ncbi_dbsnp_schemas.py`'s design decision 4/5 and
    `litvar2_lookup_schemas.py`'s `Litvar2VariantMatch` already document.

    `nct_id` is this item's identity field: `clinicaltrials_search.py`
    never truncates it to fit the 15-char cap (a real NCT id is always
    `NCT` plus 8 digits, well inside the cap; this is defense-in-depth
    against an unexpected upstream shape, not a live-observed overflow). An
    over-length `nct_id` excludes the whole study rather than shipping a
    truncated, real-looking-but-wrong identity, the same discipline
    `litvar2_lookup_schemas.py`'s `Litvar2VariantMatch` applies to its own
    `litvar_id`/`rsid` fields.
    """

    model_config = ConfigDict(extra="forbid")

    nct_id: Annotated[str | None, Field(default=None, max_length=15)] = None
    brief_title: Annotated[str | None, Field(default=None, max_length=300)] = None
    overall_status: Annotated[str | None, Field(default=None, max_length=30)] = None
    conditions: Annotated[
        list[Annotated[str, Field(max_length=100)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    phase: Annotated[str | None, Field(default=None, max_length=30)] = None
    eligibility_summary: Annotated[str | None, Field(default=None, max_length=500)] = None
    source_url: Annotated[
        str | None,
        Field(default=None, max_length=200, pattern=CLINICALTRIALS_HOST),
    ] = None


class ClinicalTrialsSearchOutput(BaseModel):
    """The tool's return value. Section 6.7's `clinicaltrials_search.output`.

    `status`, `studies`, `study_count`, `total_count`, and `truncated` are
    Section 6.7's own `required` list (line ~1379); every other field
    defaults to an empty collection, `None`, or `False`, the same
    discipline every sibling tool's output schema in this repo already
    follows.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    studies: Annotated[
        list[ClinicalTrialsStudy],
        Field(default_factory=list, max_length=50),
    ] = Field(default_factory=list)
    study_count: Annotated[int, Field(ge=0)] = 0
    total_count: Annotated[int, Field(ge=0)] = 0
    next_page_token: Annotated[str | None, Field(default=None, max_length=200)] = None
    truncated: bool = False
    error: Annotated[str | None, Field(default=None, max_length=500)] = None


# ---------------------------------------------------------------------------
# Self-verification: fail at import time, not at first citation, if
# CLINICALTRIALS_HOST stops matching the shapes it is supposed to accept or
# reject. Mirrors the import-time assertion idiom
# `litvar2_lookup_schemas.py` and `ncbi_dbsnp_schemas.py` already use for
# their own record-URL patterns.
# ---------------------------------------------------------------------------

_ACCEPT_SAMPLES: Final[tuple[str, ...]] = (
    "https://clinicaltrials.gov/study/NCT01230346",
    "https://www.clinicaltrials.gov/study/NCT01230346",
)
_REJECT_SAMPLES: Final[tuple[str, ...]] = (
    # The API's own fetch host/path, never a citable record page. This is
    # the specific case CLINICALTRIALS_HOST's /study/ path scoping exists
    # to reject, unlike litvar2_lookup's host-only pattern which cannot
    # make this distinction for its own tool.
    "https://clinicaltrials.gov/api/v2/studies/NCT01230346",
    "https://clinicaltrials.gov/api/v2/studies?query.cond=BRCA1",
    # An NCBI-hosted URL must never validate against this pattern, and vice
    # versa: this is the exact trap docs/ncbi/Tool_implementation_mechanics.md
    # names for this tool.
    "https://www.ncbi.nlm.nih.gov/clinicaltrials.gov/study/NCT01230346",
    # A different, unrelated host must never validate, regardless of path.
    "https://evil.example.com/clinicaltrials.gov/study/NCT01230346",
    # Plain HTTP, not HTTPS, must never validate.
    "http://clinicaltrials.gov/study/NCT01230346",
)

for _sample in _ACCEPT_SAMPLES:
    assert re.match(CLINICALTRIALS_HOST, _sample) is not None, (
        f"CLINICALTRIALS_HOST wrongly rejects a valid ClinicalTrials.gov record URL: "
        f"{_sample!r}"
    )
for _sample in _REJECT_SAMPLES:
    assert re.match(CLINICALTRIALS_HOST, _sample) is None, (
        f"CLINICALTRIALS_HOST wrongly accepts a non-record URL: {_sample!r}"
    )
del _sample
