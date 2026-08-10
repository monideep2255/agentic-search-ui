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

CORRECTED, F-3.5-A-02 (adversary round, 2026-08-08): the theory above was
wrong for one real request shape. `countTotal=true` guarantees `totalCount`
on a FIRST page (no `pageToken`), live-confirmed, but ClinicalTrials.gov
omits it from EVERY page-2-and-later response regardless, live-confirmed
across multiple real cursors. The original fail-closed branch could not
tell that apart from a genuine contract anomaly, so it fired on every
paginated call and made every `next_page_token` this tool ever emitted
unusable. `_clinicaltrials_search_impl` now treats a missing `totalCount`
as the defensive failure above ONLY when `page_token` was not supplied;
on a continuation call it falls back to that page's own `study_count` as
`total_count`, a deliberately conservative floor ("at least this many"),
never a fabricated number.

## F-3.5-A-04: pageSize sent to the API is capped at _MAX_STUDIES, not the caller's raw page_size

`ClinicalTrialsSearchInput.page_size` allows up to 100 (Section 6.7), but
`_MAX_STUDIES` (50) is this tool's own output cap. The first version of
this tool requested the caller's raw `page_size` from the API but only
returned the first `_MAX_STUDIES` of them, while the API's own
`nextPageToken` pointed past the FULL requested page, so studies between
`_MAX_STUDIES` and the raw `page_size` were silently unreachable forever
(live-confirmed: `page_size=100` dropped studies 51 to 100, and the
returned cursor resumed at study 101). Sending `min(page_size,
_MAX_STUDIES)` to the API keeps its cursor and this tool's own truncation
point identical.

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

import hashlib
import re
import urllib.parse
from typing import Any, Final

from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.synthesis.provenance_defaults import defaults_for_tool
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
    """`conditionsModule.conditions` capped to item length and list-count limits.

    F-3.5-10 (minor, judge round 2026-08-08, deliberately carried open
    rather than fixed here): an over-length condition name is silently
    TRUNCATED (`_cap`), not withheld-and-disclosed the way
    `ncbi_dbsnp`/`litvar2_lookup` treat an over-cap controlled-vocabulary
    term (F-3.2-A-01, F-3.3-03). A truncated condition name can still read
    as a real, different, shorter term. This is a smaller-blast-radius
    case than those two: `conditions` is a display/context field on a
    citation whose own identity (`nct_id`) and link (`source_url`) are
    unaffected, never the sole fact a claim rests on the way a variant's
    `clinical_significance` was. Whether to spend a new schema field
    (`fields_withheld`) on this tool for a lower-stakes field is a product
    decision this fix round's own scope does not cover; recorded here so
    the gap is visible rather than silently absent, per
    `goal-contracts.md`'s "a verify surface must state its own coverage".
    """
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

    F-3.5-A-08 (adversary round, 2026-08-08), disclosed honestly rather
    than left silent: `clinicaltrials.gov/study/{nctId}` is a
    client-rendered SPA. Live-confirmed, a real NCT id and a fabricated
    one (`NCT99999999`) both return HTTP 200 with byte-identical bodies
    containing neither id nor server-rendered study content. HTTP 200
    confirms the study page itself is reachable, not that this specific
    `nctId` renders on load; whether the client-side app pre-populates
    from the path segment was not verified. Same property, same
    disclosure discipline `pathogen_detection.py` documents for its own
    isolate citation (F-3.5-04) and `tracker/phase_3.3.md` filed as
    F-3.3-A-09 for LitVar2's UI citation; this tool shipped the identical
    property undocumented in its first version.
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
        # F-3.5-A-04 (adversary round, 2026-08-08): never ask the API for
        # more studies than this tool will actually return. The schema
        # allows page_size up to 100, but `_MAX_STUDIES` caps the output
        # at 50; requesting the caller's raw page_size let the API's own
        # cursor (`nextPageToken`) advance past studies this tool silently
        # dropped, permanently skipping them on the next page. Capping the
        # REQUEST at `_MAX_STUDIES` keeps the API's cursor and this tool's
        # own truncation point identical, so `truncated: true` plus
        # `next_page_token` always resumes exactly where the returned
        # `studies` list left off.
        "pageSize": min(tool_input.page_size, _MAX_STUDIES),
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

    raw_total_count = _extract_total_count(body)
    # F-3.5-A-02 (adversary round, 2026-08-08): ClinicalTrials.gov omits
    # totalCount from every page-2-and-later response even with
    # countTotal=true sent on every request, live-confirmed. F-3.5-02's
    # original fail-closed branch treated ANY missing totalCount as a
    # genuine contract anomaly, which made every paginated call return
    # status: "error", so a next_page_token the tool itself emitted was
    # never actually usable. A missing totalCount on a first-page call
    # (no page_token supplied) is still a genuine anomaly, since that is
    # exactly the request shape F-3.5-02 verified guarantees the field;
    # only a CONTINUATION call (page_token supplied) gets the documented,
    # expected-missing treatment below.
    if raw_total_count is None and not tool_input.page_token:
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
            total_count=raw_total_count if raw_total_count is not None else 0,
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
            total_count=raw_total_count if raw_total_count is not None else 0,
            next_page_token=next_page_token,
            truncated=truncated,
        )

    # F-3.5-A-02: on a continuation call where the API omitted totalCount,
    # fall back to this page's own study_count rather than erroring. This
    # is a deliberately conservative floor, never a fabricated number
    # larger than what is actually returned: `total_count` on a page-2+
    # response therefore means "at least this many", not "exactly this
    # many", the same honest-degradation shape F-3.5-10 documents for
    # `conditions` truncation.
    total_count = raw_total_count if raw_total_count is not None else len(studies)

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


# ---------------------------------------------------------------------------
# T-3.4-04: citation-building. Section 9.2's per-tool `CitationPayload`.
# ---------------------------------------------------------------------------


def _mint_citation_id(prefix: str, seed: str, display_index: int) -> str:
    """A short, deterministic-shaped citation id, mirroring `core/graph.py`'s
    `_citation_for_row` pattern (a stable id plus a display-index suffix),
    adapted for a tool with no `call_id` of its own: the id is minted from a
    short hash of the real source id instead. Only needs to be non-colliding
    within one tool's own output, not globally unique across a whole answer.
    """
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"{prefix}-{digest}-{display_index}"[:64]


def build_citation(study: ClinicalTrialsStudy, display_index: int = 1) -> CitationPayload:
    """Build a Section 9.2 `CitationPayload` from ONE real `clinicaltrials_search` study.

    `study` is a single item from `ClinicalTrialsSearchOutput.studies`, not
    the whole output object: a `clinicaltrials_search` result can carry
    several studies, and each is its own citable record with its own
    `nct_id` and `source_url`, unlike `litvar2_lookup`'s single
    whole-result `source_url`. Raises `ValueError` with an actionable
    message, never returns a placeholder, when `study` carries no
    `source_url`.

    `evidence_kind` and `license` come from
    `provenance_defaults.defaults_for_tool("clinicaltrials_search")`, which
    resolves to `"external_annotation"`/`"public_domain_us_gov"`: a trial
    registry record, not a primary NCBI-native assertion. `assertion_
    confidence` is always `"asserted"`: a trial's status, phase, and
    condition list are structured registry fields set by the study's own
    sponsor, not a hedged literature claim. `population_ancestry_context`
    is always `None`: this tool has no population or ancestry field.
    """
    if not study.source_url:
        raise ValueError(
            f"clinicaltrials_search study {study.nct_id!r} has no source_url; "
            "refusing to build a citation rather than fabricate one."
        )

    defaults = defaults_for_tool("clinicaltrials_search")
    source_id = (study.nct_id or "unknown")[:128]

    detail_parts: list[str] = []
    if study.brief_title:
        detail_parts.append(study.brief_title)
    if study.overall_status:
        detail_parts.append(f"status={study.overall_status}")
    if study.phase:
        detail_parts.append(f"phase={study.phase}")
    claim_text = (
        f"{source_id}: " + "; ".join(detail_parts) if detail_parts else source_id
    )[:1000]

    return CitationPayload(
        citation_id=_mint_citation_id("ctgov", source_id, display_index),
        display_index=display_index,
        source="clinicaltrials.gov"[:128],
        source_id=source_id,
        source_url=study.source_url,
        layer="layer_3_enrichment",
        field="overall_status",
        claim_text=claim_text,
        evidence_kind=defaults["evidence_kind"],
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license=defaults["license"],
    )
