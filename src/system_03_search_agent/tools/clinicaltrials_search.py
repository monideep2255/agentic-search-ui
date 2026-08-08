"""clinicaltrials_search: the disease-to-trials path over ClinicalTrials.gov API v2 (T-3.5-06).

Section 6.7's single call: `GET https://clinicaltrials.gov/api/v2/studies`,
`query.cond`/`query.term`/`query.intr`/`filter.overallStatus`/`pageSize`/
`pageToken` in, a page of studies plus `totalCount` and `nextPageToken` out.
Genuinely HTTP-status-coded (`ncbi_transport.classify_status_coded_response`),
the same convention as Datasets v2, PubChem, and Variation Services, never
E-utilities' 200-with-body convention: confirmed for this host by this
phase's pre-build probes (`tracker/phase_3.5.md`), which never observed a
non-2xx-with-success-body or 2xx-with-error-body shape.

## F-3.5-02: totalCount is opt-in, not default (the phase's own load-bearing finding)

Live-confirmed 2026-08-08: a default `GET /studies` call, with no
`countTotal` parameter, OMITS the `totalCount` key from its response body
entirely, not `0` or `null`, the key is simply absent. Section 6.7's own
locked output schema requires `total_count` on every response
(`ClinicalTrialsSearchOutput.total_count`, required, not `Optional`).
`_clinicaltrials_search_impl` below therefore sends `countTotal=true` on
EVERY request unconditionally: it is not exposed as a caller-configurable
input field (`ClinicalTrialsSearchInput` has no `count_total` field), since
the locked schema requires the output field on every response and there is
never a reason to omit it. `_extract_total_count` additionally treats a
missing or non-integer `totalCount` as a defensive failure (`status:
"error"`) rather than guessing `0`, on the theory that this tool always
sends the parameter that is documented to guarantee the key's presence, so
its absence anyway is a genuine, reportable contract surprise, not a
routine empty-result shape (a genuine empty result still carries
`totalCount: 0`, confirmed live, and is handled by the ordinary `status:
"empty"` path below, not this defensive branch).

## designModule.phases is an array, never a scalar phase string

Also live-confirmed 2026-08-08: `designModule.phases` is a JSON array
(`["NA"]`, or `["PHASE2", "PHASE3"]` for a multi-phase study). Section
6.7's own locked output schema names `phase` as a `string`, so `_join_phases`
below joins the array (`", ".join(phases)`) before it ever reaches
`ClinicalTrialsStudy`; `clinicaltrials_search_schemas.py` only enforces the
resulting string's `maxLength: 30` cap, it does not perform the join
itself (see that module's design decision 5).

## eligibility_summary: truncate cleanly, never withhold

Unlike this repo's other Layer 2/3 tools (`ncbi_dbsnp`'s
`clinical_significance`, `litvar2_lookup`'s `clinical_significance`/
`matched_on`), which WITHHOLD an over-length field rather than truncate it
(F-3.2-A-01, F-3.3-03: a truncated ClinVar term reads as a real, different,
shorter term), `eligibility_summary` is deliberately truncated, per this
ticket's own explicit instruction. The two cases are not the same shape of
risk: `clinical_significance` is a short, closed-vocabulary controlled
term where a truncated prefix looks like a DIFFERENT real term (silently
wrong, not obviously partial); `eligibilityCriteria` is free-flowing prose
with no controlled vocabulary to collide with, and `eligibility_summary`
is already documented, by this repo's own design (Section 6.7's field
description, `clinicaltrials_search_schemas.py`'s design decision 4), as a
BOUNDED PROJECTION of the full text, not a verbatim field ClinicalTrials.gov
itself returns pre-summarized. Cutting it further to fit the schema's own
500-char cap is the same kind of operation the projection already performs,
not a new failure mode. `_build_eligibility_summary` cuts at the last word
boundary inside budget and appends an explicit `" [truncated]"` marker, so
a reader can tell at a glance that the field is a partial view rather than
the complete criteria block, and the marker itself is included in the
500-char budget so the field never exceeds its schema cap.

## Untrusted content (ai-security-standards.md)

`brief_title`, `eligibility_summary`, every `conditions` entry, and
`overall_status`/`phase` are content submitted by, or derived from data
submitted by, a TRIAL SPONSOR, not vetted or authored by ClinicalTrials.gov
or NCBI (Section 6.7's own "Untrusted content" note; `docs/ncbi/
Tool_implementation_mechanics.md`'s clinicaltrials_search trap section).
Nothing in this module ever evaluates, formats-as-a-template, or executes
any of it: every value is either passed through Pydantic's own typed,
length-capped fields unmodified (after this module's own client-side
capping, applied BEFORE construction so pydantic never raises on a value
this module itself produced), or excluded entirely (a study whose identity
field, `nct_id`, overflows its cap). This module has no other-tool calling
capability and no write access of any kind, the isolated-reader-pass tier
separation `ai-security-standards.md` requires: it only ever calls
`ncbi_transport.execute_get` against the one ClinicalTrials.gov host.

## Never raises

`clinicaltrials_search` (the public entry point) wraps
`_clinicaltrials_search_impl` in a `try`/`except`, the same outer-boundary
pattern `ncbi_dbsnp.py`'s and `litvar2_lookup.py`'s dispatchers use, per
`.claude/rules/production-standards.md`'s retry-safety gate: an error
message must say what to do next, not just what failed.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (the `"clinicaltrials"`
      rate-limit family, `execute_get`, `classify_status_coded_response`,
      `TransportError`)
    - system_03_search_agent.tools.clinicaltrials_search_schemas
      (T-3.5-04; `ClinicalTrialsSearchInput`, `ClinicalTrialsSearchOutput`,
      `ClinicalTrialsStudy`, `CLINICALTRIALS_HOST`)

Reads:
    - Nothing directly. No API key: ClinicalTrials.gov API v2 needs none
      (Section 6.7).

Writes:
    - Nothing. Outbound HTTPS requests only, via `ncbi_transport`.

Depended by:
    - system_03_search_agent.harness.cache (T-3.5-07, tool registration,
      out of this ticket's scope)
    - tests/system_03_search_agent/tools/test_clinicaltrials_search_premise.py,
      via its `_run` helper, which imports `clinicaltrials_search` from
      this module by name
    - tests/system_03_search_agent/tools/test_clinicaltrials_search.py
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Final

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    CLINICALTRIALS_HOST,
    ClinicalTrialsSearchInput,
    ClinicalTrialsSearchOutput,
    ClinicalTrialsStudy,
)

_STUDIES_URL: Final[str] = "https://clinicaltrials.gov/api/v2/studies"
_STUDY_RECORD_BASE: Final[str] = "https://clinicaltrials.gov/study/"

# Field length/count caps, mirroring clinicaltrials_search_schemas.py's own
# Field(max_length=...) constraints exactly. Every value that could
# plausibly come from untrusted upstream sponsor content is capped here,
# BEFORE construction, per production-standards.md's bounded-context-items
# gate: pydantic raises on an over-cap value rather than truncating it, so
# an uncapped value reaching a model constructor would turn a legitimate
# result into a fabricated status="error" refusal instead of a clean,
# honest truncation.
_MAX_NCT_ID_CHARS: Final[int] = 15
_MAX_BRIEF_TITLE_CHARS: Final[int] = 300
_MAX_STATUS_CHARS: Final[int] = 30
_MAX_CONDITION_CHARS: Final[int] = 100
_MAX_CONDITIONS_ITEMS: Final[int] = 10
_MAX_PHASE_CHARS: Final[int] = 30
_MAX_ELIGIBILITY_CHARS: Final[int] = 500
_MAX_SOURCE_URL_CHARS: Final[int] = 200
_MAX_PAGE_TOKEN_CHARS: Final[int] = 200
_MAX_ERROR_CHARS: Final[int] = 500

_MAX_STUDIES: Final[int] = 50

_ELIGIBILITY_TRUNCATION_MARKER: Final[str] = " [truncated]"


def _cap(value: str, limit: int) -> str:
    """Slice `value` to `limit` characters. Never raises on an over-length input."""
    return value[:limit]


def _build_eligibility_summary(raw_criteria: Any) -> str | None:
    """A bounded, client-side projection of `eligibilityModule.eligibilityCriteria`.

    See the module docstring's "eligibility_summary: truncate cleanly,
    never withhold" section for why this field is deliberately truncated
    rather than withheld, unlike this repo's other Layer 2/3 free-text
    fields. Cuts at the last whitespace boundary inside budget so the
    summary does not end mid-word, then appends an explicit truncation
    marker; the marker's own length is reserved out of the budget up
    front, so the returned string never exceeds `_MAX_ELIGIBILITY_CHARS`
    regardless of where the word boundary falls. Returns `None` for a
    missing, non-string, or blank value: an absent field is a fact, not a
    failure.
    """
    if not isinstance(raw_criteria, str):
        return None
    text = raw_criteria.strip()
    if not text:
        return None
    if len(text) <= _MAX_ELIGIBILITY_CHARS:
        return text

    budget = _MAX_ELIGIBILITY_CHARS - len(_ELIGIBILITY_TRUNCATION_MARKER)
    cut = text[:budget]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut + _ELIGIBILITY_TRUNCATION_MARKER


def _join_phases(raw_phases: Any) -> str | None:
    """`designModule.phases` (an array) joined into this schema's own `phase` string.

    See the module docstring's "designModule.phases is an array" section.
    A non-list, empty, or all-non-string value returns `None` rather than
    an empty string: an absent phase is a fact, not a failure. The joined
    result is capped at `_MAX_PHASE_CHARS`, matching
    `ClinicalTrialsStudy.phase`'s own `max_length=30`.
    """
    if not isinstance(raw_phases, list):
        return None
    phases = [item for item in raw_phases if isinstance(item, str) and item]
    if not phases:
        return None
    return _cap(", ".join(phases), _MAX_PHASE_CHARS)


def _parse_conditions(raw_conditions: Any) -> list[str]:
    """`conditionsModule.conditions` capped to item length and list-count limits."""
    if not isinstance(raw_conditions, list):
        return []
    kept: list[str] = []
    for item in raw_conditions:
        if not isinstance(item, str) or not item:
            continue
        kept.append(_cap(item, _MAX_CONDITION_CHARS))
        if len(kept) >= _MAX_CONDITIONS_ITEMS:
            break
    return kept


def _build_source_url(nct_id: str) -> str | None:
    """The study's own citable record page, `https://clinicaltrials.gov/study/{nctId}`.

    Fails closed to `None` (never raises) if the resulting URL would
    exceed its own schema cap or, defensively, fails
    `CLINICALTRIALS_HOST`'s own pattern: should never actually fire since
    `_STUDY_RECORD_BASE` is a fixed, already-verified constant and `nct_id`
    is already checked by the caller, the same defense-in-depth discipline
    `litvar2_lookup._build_source_url` uses for its own fixed base
    constant.
    """
    url = _STUDY_RECORD_BASE + urllib.parse.quote(nct_id, safe="")
    if len(url) > _MAX_SOURCE_URL_CHARS:
        return None
    if re.match(CLINICALTRIALS_HOST, url) is None:
        return None
    return url


def _parse_study(raw: Any) -> ClinicalTrialsStudy | None:
    """Build one `ClinicalTrialsStudy` from a raw `/studies` array entry, or exclude it.

    Returns `None` when the entry is not an object, carries no
    `protocolSection`, has no usable `nctId`, or `nctId` overflows its
    identity-field cap: without a trustworthy identity there is nothing to
    attach a citation to, or to distinguish this study from any other, the
    same "an identity field is never silently truncated" discipline
    `litvar2_lookup.py`'s `_parse_variant_match` applies to `litvar_id`/
    `rsid`. Every other field is capped and passed through inertly per the
    module docstring's "untrusted content" section; none of them can cause
    a study to be excluded.
    """
    if not isinstance(raw, dict):
        return None
    protocol = raw.get("protocolSection")
    if not isinstance(protocol, dict):
        return None

    identification = protocol.get("identificationModule")
    if not isinstance(identification, dict):
        return None
    nct_id_raw = identification.get("nctId")
    if not isinstance(nct_id_raw, str) or not nct_id_raw:
        return None
    if len(nct_id_raw) > _MAX_NCT_ID_CHARS:
        return None
    nct_id = nct_id_raw

    brief_title_raw = identification.get("briefTitle")
    brief_title = _cap(brief_title_raw, _MAX_BRIEF_TITLE_CHARS) if isinstance(brief_title_raw, str) else None

    status_module = protocol.get("statusModule")
    overall_status_raw = status_module.get("overallStatus") if isinstance(status_module, dict) else None
    overall_status = (
        _cap(overall_status_raw, _MAX_STATUS_CHARS) if isinstance(overall_status_raw, str) else None
    )

    conditions_module = protocol.get("conditionsModule")
    conditions = _parse_conditions(
        conditions_module.get("conditions") if isinstance(conditions_module, dict) else None
    )

    design_module = protocol.get("designModule")
    phase = _join_phases(design_module.get("phases") if isinstance(design_module, dict) else None)

    eligibility_module = protocol.get("eligibilityModule")
    eligibility_summary = _build_eligibility_summary(
        eligibility_module.get("eligibilityCriteria") if isinstance(eligibility_module, dict) else None
    )

    return ClinicalTrialsStudy(
        nct_id=nct_id,
        brief_title=brief_title,
        overall_status=overall_status,
        conditions=conditions,
        phase=phase,
        eligibility_summary=eligibility_summary,
        source_url=_build_source_url(nct_id),
    )


def _extract_total_count(body: dict[str, Any]) -> int | None:
    """F-3.5-02: `totalCount` is always requested; its absence here is a defensive
    fail-closed case, not a guessed default. See the module docstring's
    F-3.5-02 section for why this branch does not default to `0`.

    `isinstance(x, bool)` is checked before `isinstance(x, int)` because
    `bool` is a subclass of `int` in Python; a stray boolean here must not
    be silently accepted as a count.
    """
    raw_total = body.get("totalCount")
    if isinstance(raw_total, bool):
        return None
    if isinstance(raw_total, int) and raw_total >= 0:
        return raw_total
    return None


def _extract_next_page_token(body: dict[str, Any]) -> str | None:
    raw = body.get("nextPageToken")
    if not isinstance(raw, str) or not raw:
        return None
    if len(raw) > _MAX_PAGE_TOKEN_CHARS:
        # Fail closed: an over-length token cannot be truncated and still
        # be a valid token a caller could pass back to page_token, so
        # shipping a truncated one would be worse than omitting it.
        return None
    return raw


def _error_output(message: str) -> ClinicalTrialsSearchOutput:
    return ClinicalTrialsSearchOutput(
        status="error",
        studies=[],
        study_count=0,
        total_count=0,
        next_page_token=None,
        truncated=False,
        error=_cap(message, _MAX_ERROR_CHARS),
    )


def _clinicaltrials_error_message(http_status: int, reason: str | None) -> str:
    """An actionable message per production-standards.md's retry-safety gate.

    A 429 or 5xx is reported as possibly transient (retry after a
    backoff); any other non-2xx status (a malformed query parameter or an
    otherwise rejected request) is reported as a permanent, client-side
    rejection that retrying will not fix. Mirrors `litvar2_lookup.
    _litvar2_error_message`'s own shape.
    """
    text = reason or "unknown error"
    if http_status == 429:
        return (
            f"ClinicalTrials.gov returned HTTP 429 ({text}). This is a rate-limit "
            "signal, likely transient; retry after a backoff."
        )
    if http_status >= 500:
        return (
            f"ClinicalTrials.gov returned HTTP {http_status} ({text}). This may be a "
            "transient, server-side condition; retry after a backoff."
        )
    return (
        f"ClinicalTrials.gov rejected the studies search: {text}. This is a "
        f"client-side rejection (HTTP {http_status}, likely a malformed query "
        "parameter), not a transient condition; retrying the same request will not "
        "help. Verify the input is correct before retrying."
    )


async def _clinicaltrials_search_impl(
    tool_input: ClinicalTrialsSearchInput,
) -> ClinicalTrialsSearchOutput:
    params: dict[str, Any] = {
        "query.cond": tool_input.query_cond,
        # F-3.5-02: always requested, never a caller-configurable option.
        # See the module docstring's F-3.5-02 section for why.
        "countTotal": "true",
        "pageSize": tool_input.page_size,
    }
    if tool_input.query_term:
        params["query.term"] = tool_input.query_term
    if tool_input.query_intr:
        params["query.intr"] = tool_input.query_intr
    if tool_input.overall_status:
        params["filter.overallStatus"] = tool_input.overall_status
    if tool_input.page_token:
        params["pageToken"] = tool_input.page_token

    try:
        # ncbi_transport.execute_get URL-encodes every parameter itself
        # (production-standards.md's query-safety gate), so no value here
        # needs a separate urllib.parse.quote pass before this call.
        response = await ncbi_transport.execute_get(_STUDIES_URL, params, family="clinicaltrials")
    except ncbi_transport.TransportError as exc:
        return _error_output(
            f"ClinicalTrials.gov studies search failed: {exc}. Retry once; if this "
            "recurs, ClinicalTrials.gov may be degraded."
        )

    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers
    )
    if classification.status == "error":
        return _error_output(
            _clinicaltrials_error_message(response.status_code, classification.error_message)
        )

    body = classification.body
    if not isinstance(body, dict):
        return _error_output(
            "ClinicalTrials.gov returned an unrecognized response shape (expected a "
            "JSON object), refusing to guess its meaning. Retry once; if this recurs, "
            "report it."
        )

    studies_raw = body.get("studies")
    if not isinstance(studies_raw, list):
        return _error_output(
            "ClinicalTrials.gov response omitted a studies array, refusing to guess "
            "its meaning. Retry once; if this recurs, report it."
        )

    total_count = _extract_total_count(body)
    if total_count is None:
        return _error_output(
            "ClinicalTrials.gov omitted totalCount even though countTotal=true was "
            "sent (F-3.5-02), refusing to guess the true total. Retry once; if this "
            "recurs, ClinicalTrials.gov may have changed its response contract."
        )

    next_page_token = _extract_next_page_token(body)

    if not studies_raw:
        # Section 6.7: a genuine no-match returns studies: [] with
        # totalCount: 0, HTTP 200, mapped to status: "empty", never
        # fabricated as "ok". This is the Layer 3 cite-or-refuse trigger.
        return ClinicalTrialsSearchOutput(
            status="empty",
            studies=[],
            study_count=0,
            total_count=total_count,
            next_page_token=next_page_token,
            truncated=False,
        )

    kept_raw = studies_raw[:_MAX_STUDIES]
    truncated = len(studies_raw) > len(kept_raw)

    studies: list[ClinicalTrialsStudy] = []
    for raw_study in kept_raw:
        parsed = _parse_study(raw_study)
        if parsed is not None:
            studies.append(parsed)

    if not studies:
        # The response body was non-empty, but every entry either failed
        # to parse as an object or had its identity field (nctId) excluded
        # for missing or overflowing its cap. Shipping status="ok" here
        # with an empty studies list would be a confident success over
        # zero usable content, the same fabricated-success shape
        # litvar2_lookup.py's own "F-3.3-J-02" guard and
        # pubtator_annotate.py's entity_lookup guard both exist to avoid.
        # Treat it as a genuine no-match instead.
        return ClinicalTrialsSearchOutput(
            status="empty",
            studies=[],
            study_count=0,
            total_count=total_count,
            next_page_token=next_page_token,
            truncated=truncated,
        )

    return ClinicalTrialsSearchOutput(
        status="ok",
        studies=studies,
        study_count=len(studies),
        total_count=total_count,
        next_page_token=next_page_token,
        truncated=truncated,
    )


async def clinicaltrials_search(input_data: ClinicalTrialsSearchInput) -> ClinicalTrialsSearchOutput:
    """The disease-to-trials search over ClinicalTrials.gov API v2. Never raises.

    See the module docstring for F-3.5-02 (`countTotal=true` always sent)
    and the `designModule.phases` array-to-string join. This public entry
    point is a thin wrapper around `_clinicaltrials_search_impl`: every
    expected failure (a transport error, a rejected upstream shape, a
    malformed field) is already classified and returned as a `status:
    "error"` output by the functions above. This wrapper's own
    `try`/`except` is the last-resort boundary for an UNEXPECTED exception,
    the same outer-boundary pattern `ncbi_dbsnp.py`'s and
    `litvar2_lookup.py`'s dispatchers use, per
    `.claude/rules/production-standards.md`'s retry-safety gate.
    """
    try:
        return await _clinicaltrials_search_impl(input_data)
    except Exception as exc:  # noqa: BLE001 - the module's deliberate last-resort catch
        return _error_output(
            f"clinicaltrials_search raised an unexpected {type(exc).__name__} instead "
            f"of returning a classified result: {exc}. Retry once; if this recurs, "
            "this tool has a defect that needs fixing before it can be trusted."
        )
