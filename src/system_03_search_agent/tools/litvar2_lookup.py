"""litvar2_lookup: variant-to-literature evidence over LitVar2 (T-3.3-06).

Section 6.5's two independent modes, each a single GET call, never
sequential the way `ncbi_dbsnp`'s two calls are:

    variant_search: `GET /variant/autocomplete/?query=...`, an rsid, an
    HGVS expression, or a free-text variant name in, a list of variant
    matches out (or `[]` for a genuine no-match, HTTP 200 either way).

    publications_lookup: `GET /variant/get/{litvar_id}/publications`, a
    LitVar2 variant id in (e.g. `litvar@rs334##`), that variant's linked
    PMIDs out, capped at `maxItems: 50` with an honest `total_pmids`.

Both endpoints are genuinely HTTP-status-coded (`ncbi_transport.
classify_status_coded_response`), unlike E-utilities' 200-with-body
convention: confirmed live for both modes during this phase's pre-build
probes (`tracker/phase_3.3.md`), the reason this module never needs
`classify_eutils_response` at all.

## Two live-probed traps this module resolves, neither guessable from the
## locked spec alone (LEARNINGS.md row 60's discipline: fixtures and
## assumptions come from the real endpoint, not a reading of what it
## should do)

1. THE UNENCODED-LITVAR_ID TRAP. A LitVar2 id like `litvar@rs334##`
   contains `@` and `#`, neither URL-safe. Sending it unencoded does not
   crash; LitVar2 silently treats the string up to the first `#` as the
   whole id and 400s with a WRONG "not found" message
   (`{"detail": "Variant not found: litvar@rs334"}`, missing the `##`
   suffix entirely), live-confirmed 2026-08-08. A caller that forgot to
   encode would see a real, resolvable variant reported as not found: a
   wrong-answer risk, not a crash, and therefore easy to miss without a
   live behavioral test (`test_litvar2_lookup_premise.py`'s case 5 pins
   this directly). `_encode_litvar_id` below is called UNCONDITIONALLY on
   every `publications_lookup` request, regardless of whether the caller's
   `litvar_id` looks already-encoded, so this tool never trusts the
   caller to have done its own encoding. `Litvar2PublicationsLookupInput.
   litvar_id` is documented (its own schema docstring) as the RAW,
   unencoded form, the same shape `Litvar2VariantMatch.litvar_id` itself
   returns, so encoding here exactly once is correct by construction: a
   caller who copies a `variant_search` result's own `litvar_id` straight
   into a `publications_lookup` call never needs to encode it themselves,
   and a caller who DID encode it first would get a wrong (double-encoded)
   URL, which is why this module treats "raw, unencoded" as the one
   accepted input shape rather than trying to detect and skip re-encoding
   an already-encoded string.

2. THE FETCH-HOST-EQUALS-UI-HOST TRAP. Unlike `ncbi_dbsnp` (Variation
   Services at `api.ncbi.nlm.nih.gov`, dbSNP ESummary at
   `eutils.ncbi.nlm.nih.gov`, both genuinely different hosts from the
   citable `www.ncbi.nlm.nih.gov/snp/` page), LitVar2's fetch API
   (`www.ncbi.nlm.nih.gov/research/litvar2-api/...`) and this tool's
   chosen human-facing citation target
   (`www.ncbi.nlm.nih.gov/research/litvar2/...`) share the exact same
   hostname. `litvar2_lookup_schemas.NCBI_LITVAR2_RECORD_URL_PATTERN` is
   Section 6.5's own locked pattern, unscoped beyond host (see that
   file's design decision 3), so it CANNOT by itself reject a `source_url`
   that accidentally points at the `-api` fetch path instead of the UI
   path: both validate. `_build_source_url` and
   `_build_source_url_for_litvar_id` below are therefore the sole gate
   against ever citing the fetch host: they build only from `_UI_BASE`
   (`/research/litvar2/`), never `_LITVAR2_BASE`
   (`/research/litvar2-api/`), and there is no code path anywhere in this
   module that constructs a `source_url` from `_LITVAR2_BASE`. This is a
   correctness-by-construction guarantee, not a regex one, and is called
   out explicitly because the usual defense (a tighter URL pattern) is not
   available here the way it is for `ncbi_dbsnp`.

## source_url mapping, a judgment call since Section 6.5 names no specific
## human-facing LitVar2 record page

Section 6.5's `source_url` is a single top-level output field (not
per-match), and neither the spec nor `Tool_implementation_mechanics.md`
names a documented per-variant LitVar2 web page. Live-probed 2026-08-08:
`https://www.ncbi.nlm.nih.gov/research/litvar2/` (LitVar2's own interactive
search UI) returns HTTP 200 and accepts a `?query=` parameter the same
shape `/variant/autocomplete/` itself takes, so this module cites that UI
page, parameterized by the identifier the call actually resolved, as the
closest live-working analog to a per-variant record page: a human
following it lands on LitVar2's own search results for that exact
identifier, not a generic landing page. `variant_search` cites the
caller's own `query` (the term that produced whatever matches shipped, or
`None` on a genuine no-match, since there is nothing to cite there).
`publications_lookup` cites the rsid embedded in `litvar_id` when the id
matches the documented `litvar@rs.../##` shape (`_RSID_FROM_LITVAR_ID`),
falling back to the raw `litvar_id` itself when it does not, so the URL
stays meaningful even for a non-rsid-keyed LitVar2 id. This is a
deliberate, documented substitution, not a silent guess: if LitVar2 ever
publishes a per-variant permalink, this should be reconsidered.

## Withholding, not truncating (F-3.3-03)

`_parse_clinical_significance` drops (never truncates) any individual
`clinical_significance` term exceeding its 30-char schema cap and records
the drop in the output-level `fields_withheld`, naming the withheld
`variant_matches[i]` index and the full original term, following the exact
precedent `ncbi_dbsnp.py`'s `_cap_or_withhold` set: a truncated
`"conflicting-interpretations-of"` looks like a real, different, shorter
ClinVar term, exactly the failure `ncbi_dbsnp`'s F-3.2-A-01 shipped once
already on a sibling tool. This module extends the same discipline one
level further than `ncbi_dbsnp` needed to: because the overflow happens
INSIDE an array item rather than at a top-level scalar field,
`_parse_variant_match` also treats an over-length IDENTITY field
(`litvar_id` or `rsid`) as cause to exclude the WHOLE match from
`variant_matches` rather than shipping it with a truncated identity, the
item-scoped analog of `ncbi_dbsnp.py`'s whole-call refusal for
`spdi_canonical`: without a trustworthy identity there is nothing left to
attach the rest of that match's fields to.

F-3.3-RR-02, a known, deliberately uncovered gap: the `if not matches:`
guard in `_variant_search` (below) that decides `empty` versus `ok` is
COUNT-based, not content-based. A raw row that parses as a dict but
carries no `_id`/`rsid`/`name`/anything else recognizable (e.g. `{}`)
still produces a kept `Litvar2VariantMatch` with every field `None` or
empty, so a body of several such rows ships `status: "ok"` with content-
free matches and a `source_url`, the same "confident success over
nothing useful" shape F-3.3-J-02 was filed against, reached by a route
that guard does not cover. This is NOT reachable on live LitVar2 today
(the pre-build probes never observed a `_id`-less autocomplete row; see
`test_litvar2_lookup_premise.py`'s coverage statement), the same
reachability argument F-3.3-J-02 itself was filed against, and it is left
undefended rather than fixed: tightening this guard a second time, after
its first version already shipped one regression (F-3.3-RR-01), is a
risk this ticket declines to take on an unreachable path. If live LitVar2
is ever observed returning a genuinely content-free row, revisit this
guard with a live fixture, not a guessed one, per LEARNINGS.md row 60.

`pmids` truncation (`maxItems: 50`, Section 6.5) is a DIFFERENT, spec-
authorized kind of truncation, never confused with the withhold-not-
truncate policy above: the spec explicitly caps the array and explicitly
provides `total_pmids` to carry the true count, so dropping items 51+ from
`pmids` while reporting the honest total is the INTENDED design, not a
silent-truncation bug. `variant_matches` (`maxItems: 10`) is capped the
same authorized way, though Section 6.5 provides no companion
"total_variant_matches" field for it; this module does not invent one
outside its ticket's authorized additive fields (`fields_withheld` only).

Never raises: `litvar2_lookup` (the public entry point) wraps
`_litvar2_lookup_impl` in a `try`/`except`, the same outer-boundary pattern
`ncbi_dbsnp.py`'s and `ncbi_efetch.py`'s dispatchers use, per
`.claude/rules/production-standards.md`'s retry-safety gate.

## Untrusted content (ai-security-standards.md)

Every free-text field this module reads from LitVar2 (`name`, `hgvs`,
`gene` entries, `clinical_significance` entries) is untrusted external
content fetched at query time. Nothing in this module ever evaluates,
formats-as-a-template, or executes any of it; every value is either passed
through Pydantic's own typed, length-capped fields unmodified, or dropped
entirely per the withholding policy above. This module has no other-tool
calling capability and no write access of any kind, the isolated-reader-
pass tier separation `tracker/phase_3.3.md`'s phase premise requires: it
only ever calls `ncbi_transport.execute_get` against the one LitVar2 host.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (T-3.3-02's `"litvar2"`
      rate-limit family and the `{"detail": ...}` error-message branch;
      `execute_get`, `classify_status_coded_response`, `TransportError`)
    - system_03_search_agent.tools.litvar2_lookup_schemas (T-3.3-04;
      `Litvar2LookupInput`, `Litvar2LookupOutput`, `Litvar2VariantMatch`,
      `Litvar2VariantSearchInput`, `Litvar2PublicationsLookupInput`,
      `NCBI_LITVAR2_RECORD_URL_PATTERN`)

Reads:
    - Nothing directly. No API key: LitVar2 needs none (Section 6.5).

Writes:
    - Nothing. Outbound HTTPS requests only, via `ncbi_transport`.

Depended by:
    - system_03_search_agent.harness.cache (T-3.3-07, tool registration)
    - tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py,
      via its `_run` helper, which imports `litvar2_lookup` from this
      module by name
    - tests/system_03_search_agent/tools/test_litvar2_lookup.py
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Final

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.litvar2_lookup_schemas import (
    NCBI_LITVAR2_RECORD_URL_PATTERN,
    Litvar2LookupInput,
    Litvar2LookupOutput,
    Litvar2PublicationsLookupInput,
    Litvar2VariantMatch,
    Litvar2VariantSearchInput,
)

_LITVAR2_BASE: Final[str] = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"
# The human-facing UI host, deliberately distinct from _LITVAR2_BASE above
# even though both share the same hostname. See the module docstring's
# "fetch-host-equals-UI-host trap": every source_url in this module is
# built from THIS constant, never from _LITVAR2_BASE.
_UI_BASE: Final[str] = "https://www.ncbi.nlm.nih.gov/research/litvar2/"

# Field length/count caps, mirroring litvar2_lookup_schemas.py's own
# Field(max_length=...) (string) and Field(max_length=...) (list)
# constraints exactly, including _MAX_FIELDS_WITHHELD_ITEMS below (added
# closing F-3.3-J-01/F-3.3-J-05: this was the one list this module built
# with no matching pre-construction cap, so an output withholding more
# than 20 fields raised pydantic.ValidationError, via
# Litvar2LookupOutput.fields_withheld's own max_length=20, instead of
# shipping a capped, honest list. Every other list already had one:
# _MAX_VARIANT_MATCHES, _MAX_GENE_ITEMS, _MAX_CLINICAL_SIG_ITEMS,
# _MAX_PMIDS).
# Pydantic raises on an over-cap value rather than truncating it, so every
# value that could plausibly come from untrusted upstream content is
# checked here, before construction, per production-standards.md's
# bounded-context-items gate.
_MAX_LITVAR_ID_CHARS: Final[int] = 60
_MAX_RSID_CHARS: Final[int] = 20
_MAX_GENE_CHARS: Final[int] = 30
_MAX_NAME_CHARS: Final[int] = 60
_MAX_HGVS_CHARS: Final[int] = 80
_MAX_CLINICAL_SIG_CHARS: Final[int] = 30
_MAX_PMID_CHARS: Final[int] = 15
_MAX_SOURCE_URL_CHARS: Final[int] = 200
_MAX_ERROR_CHARS: Final[int] = 500
_MAX_WITHHELD_NOTE_CHARS: Final[int] = 150

_MAX_VARIANT_MATCHES: Final[int] = 10
_MAX_GENE_ITEMS: Final[int] = 5
_MAX_CLINICAL_SIG_ITEMS: Final[int] = 10
_MAX_PMIDS: Final[int] = 50
_MAX_FIELDS_WITHHELD_ITEMS: Final[int] = 20

# `litvar@rs334##` -> `rs334`. Used only to build a more specific UI
# citation for publications_lookup; a litvar_id that does not match this
# shape falls back to being cited by its own raw text, never an error.
_RSID_FROM_LITVAR_ID: Final[re.Pattern[str]] = re.compile(r"^litvar@(.+?)##$")


def _quote_path_segment(value: str) -> str:
    """URL-encode one path segment. Matches `ncbi_dbsnp._quote_path_segment`.

    `value` lands in the URL PATH, not a query string, so every reserved
    character is encoded (`safe=""`). This is also the mechanism that
    closes the module docstring's encoding trap: `@` and `#` both encode
    (`%40`, `%23`) under `safe=""`, called unconditionally on every
    `publications_lookup` request regardless of the caller's own input
    shape.
    """
    return urllib.parse.quote(value, safe="")


def _cap(value: str, limit: int) -> str:
    return value[:limit]


def _withheld_note(text: str) -> str:
    """Cap a diagnostic fields_withheld entry to its schema limit.

    This truncates a NOTE describing what was withheld, never the withheld
    DATA itself (which is dropped entirely, not shipped in any form). A
    truncated note is a cosmetic limitation on a diagnostic string, not a
    wrong-answer risk the way truncating an actual citable field would be.
    """
    return _cap(text, _MAX_WITHHELD_NOTE_CHARS)


def _cap_fields_withheld(notes: list[str]) -> list[str]:
    """Cap `fields_withheld` at the schema's own `max_length=20` (F-3.3-J-01).

    Every other list this module builds (`_MAX_VARIANT_MATCHES`,
    `_MAX_GENE_ITEMS`, `_MAX_CLINICAL_SIG_ITEMS`, `_MAX_PMIDS`) is capped
    BEFORE it reaches an output constructor. `fields_withheld` was the one
    exception: `Litvar2LookupOutput.fields_withheld` enforces
    `max_length=20` and pydantic RAISES on an over-cap list rather than
    truncating it, so an uncapped `fields_withheld` could turn a fully
    successful upstream response into a fabricated `status: "error"` (the
    outer never-raises wrapper in `litvar2_lookup` catches the resulting
    `ValidationError` and reports it as an unexpected-exception refusal,
    the more the tool legitimately withholds the more likely it is to
    refuse everything).

    Silently dropping the overflow notes here would be a second instance
    of the exact silent-truncation failure class this whole ticket exists
    to avoid (F-3.2-A-01, F-3.3-03): the fact that MORE than 20 fields
    were withheld would be lost with no signal at all. So when there are
    more than `_MAX_FIELDS_WITHHELD_ITEMS` notes, the first
    `_MAX_FIELDS_WITHHELD_ITEMS - 1` notes ship unchanged and the final
    slot is replaced with a summary naming how many additional notes did
    not fit, rather than simply cutting the list at the cap and staying
    silent about the rest.
    """
    if len(notes) <= _MAX_FIELDS_WITHHELD_ITEMS:
        return notes
    kept = notes[: _MAX_FIELDS_WITHHELD_ITEMS - 1]
    overflow = len(notes) - len(kept)
    kept.append(
        _withheld_note(
            f"...and {overflow} more fields withheld (the withholding count "
            f"exceeded the {_MAX_FIELDS_WITHHELD_ITEMS}-item disclosure cap)"
        )
    )
    return kept


def _build_source_url(identifier: str | None) -> str | None:
    """The LitVar2 search UI page for `identifier`, or `None` when there is
    nothing to cite. See the module docstring's "source_url mapping"
    section for the full reasoning behind citing this page.
    """
    if not identifier:
        return None
    url = _UI_BASE + "?query=" + urllib.parse.quote(identifier, safe="")
    if len(url) > _MAX_SOURCE_URL_CHARS:
        return None
    if re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, url) is None:
        # Defense in depth, matching ncbi_dbsnp._build_source_url's own
        # "fail closed to no citation rather than raise" discipline: should
        # never actually fire since _UI_BASE is a fixed, already-verified
        # constant, but a wrong URL here must never surface as a
        # pydantic.ValidationError out of a tool call.
        return None
    return url


def _build_source_url_for_litvar_id(litvar_id: str) -> str | None:
    """Same as `_build_source_url`, but derives the rsid from `litvar_id` first when possible."""
    match = _RSID_FROM_LITVAR_ID.match(litvar_id)
    identifier = match.group(1) if match else litvar_id
    return _build_source_url(identifier)


def _error_output(mode: str, message: str) -> Litvar2LookupOutput:
    return Litvar2LookupOutput(status="error", mode=mode, error=_cap(message, _MAX_ERROR_CHARS))


def _litvar2_error_message(action: str, identifier: str, http_status: int, reason: str | None) -> str:
    """An actionable message per production-standards.md's retry-safety gate.

    A 429 or 5xx is reported as possibly transient (retry after a backoff);
    any other non-2xx status (LitVar2's documented not-found/malformed-
    input shape, `{"detail": ...}`) is reported as a permanent, client-side
    rejection that retrying will not fix. Unlike `ncbi_dbsnp.py`'s own
    `_variation_error_message`, this does not attempt to distinguish an
    input-shaped 5xx from a genuine server condition (F-3.2-A-16's own
    finding): that distinction was live-reproduced specifically for
    Variation Services and has no equivalent live evidence for LitVar2 in
    this phase's pre-build probes, so this module does not assert a
    narrower claim than what was actually confirmed.
    """
    text = reason or "unknown error"
    if http_status == 429:
        return (
            f"LitVar2 {action} for {identifier!r} returned HTTP 429 ({text}). "
            "This is a rate-limit signal, likely transient; retry after a backoff."
        )
    if http_status >= 500:
        return (
            f"LitVar2 {action} for {identifier!r} returned HTTP {http_status} ({text}). "
            "This may be a transient, server-side condition; retry after a backoff."
        )
    return (
        f"LitVar2 rejected {action} for {identifier!r}: {text}. This is a client-side "
        f"rejection (HTTP {http_status}, a malformed input or a nonexistent record), not "
        "a transient condition; retrying the same request will not help. Verify the "
        "input is correct before retrying."
    )


# ---------------------------------------------------------------------------
# variant_search: GET /variant/autocomplete/?query=...
# ---------------------------------------------------------------------------


def _parse_clinical_significance(raw: Any, match_index: int) -> tuple[list[str], list[str]]:
    """F-3.3-03: drop (never truncate) any over-length clinical_significance term.

    Returns `(kept_terms, withheld_notes)`. A non-list or absent `raw`
    (LitVar2's own `data_clinical_significance` field is present on some
    autocomplete rows and absent on others, live-confirmed) returns `([],
    [])`, never an error: an absent field is a fact, not a failure.

    `match_index` (F-3.3-J-03) is the OUTPUT position this match will
    occupy in the final `variant_matches` list, never the raw response
    array's own enumeration index: see `_parse_variant_matches`'s
    docstring for why the two can differ once any match is excluded.
    """
    if not isinstance(raw, list):
        return [], []
    kept: list[str] = []
    withheld: list[str] = []
    for term in raw:
        if not isinstance(term, str):
            continue
        if len(term) > _MAX_CLINICAL_SIG_CHARS:
            withheld.append(
                _withheld_note(
                    f"variant_matches[{match_index}].clinical_significance: {term}"
                )
            )
            continue
        kept.append(term)
    if len(kept) > _MAX_CLINICAL_SIG_ITEMS:
        # Spec-authorized array-level cap (Section 6.5's own maxItems: 10),
        # the same "truncate to the array cap" treatment as pmids/
        # variant_matches, not the withhold-not-truncate policy above: this
        # only fires on the COUNT of already in-cap-length terms, never on
        # a term's own content, so no term is ever shortened.
        kept = kept[:_MAX_CLINICAL_SIG_ITEMS]
    return kept, withheld


def _parse_gene(raw: Any, match_index: int) -> tuple[list[str], list[str]]:
    """Cap `gene` to its item-length and list-count limits. Same withhold-per-item policy as clinical_significance.

    `match_index` (F-3.3-J-03) is the OUTPUT position this match will
    occupy in `variant_matches`, not the raw response array's index. See
    `_parse_variant_matches`'s docstring.
    """
    if not isinstance(raw, list):
        return [], []
    kept: list[str] = []
    withheld: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        if len(entry) > _MAX_GENE_CHARS:
            withheld.append(_withheld_note(f"variant_matches[{match_index}].gene: {entry}"))
            continue
        kept.append(entry)
    if len(kept) > _MAX_GENE_ITEMS:
        kept = kept[:_MAX_GENE_ITEMS]
    return kept, withheld


def _parse_variant_match(
    raw: Any, raw_index: int, output_index: int
) -> tuple[Litvar2VariantMatch | None, list[str]]:
    """Build one `Litvar2VariantMatch` from a raw autocomplete row, or exclude it.

    Returns `(match_or_None, withheld_notes)`. `match` is `None` only when
    an IDENTITY field (`litvar_id` or `rsid`) overflows its schema cap: see
    the module docstring's "Withholding, not truncating" section for why
    that excludes the whole match rather than shipping a truncated
    identity. Every other over-cap field (`gene`, `name`, `hgvs`,
    `clinical_significance`) is withheld at the field or item level while
    the rest of the match still ships.

    F-3.3-J-03: `raw_index` and `output_index` are deliberately two
    different numbers. `raw_index` is this row's position in the raw
    response array, used ONLY to describe an excluded match (one that
    never occupies any position in `variant_matches`, since it was never
    appended). `output_index` is the position this match WILL occupy in
    the final `variant_matches` output list if it is kept, i.e. how many
    matches have already been kept before this one; every field-level
    note about a KEPT match (`gene`, `name`, `hgvs`,
    `clinical_significance`) is keyed to `output_index`, so
    `variant_matches[i]` in a `fields_withheld` note always refers to a
    position that actually exists in the returned array, even after an
    earlier row was excluded and every later kept match shifted down.
    """
    if not isinstance(raw, dict):
        return None, [_withheld_note(f"raw response entry {raw_index}: not an object, excluded")]

    withheld: list[str] = []

    litvar_id_raw = raw.get("_id")
    litvar_id = str(litvar_id_raw) if litvar_id_raw is not None else None
    if litvar_id is not None and len(litvar_id) > _MAX_LITVAR_ID_CHARS:
        return None, [
            _withheld_note(
                f"raw response entry {raw_index}: excluded, litvar_id "
                f"{len(litvar_id)} chars exceeds {_MAX_LITVAR_ID_CHARS} cap"
            )
        ]

    rsid_raw = raw.get("rsid")
    rsid = str(rsid_raw) if rsid_raw is not None else None
    if rsid is not None and len(rsid) > _MAX_RSID_CHARS:
        return None, [
            _withheld_note(
                f"raw response entry {raw_index}: excluded, rsid "
                f"{len(rsid)} chars exceeds {_MAX_RSID_CHARS} cap"
            )
        ]

    gene, gene_withheld = _parse_gene(raw.get("gene"), output_index)
    withheld.extend(gene_withheld)

    name_raw = raw.get("name")
    name: str | None = None
    if isinstance(name_raw, str):
        if len(name_raw) > _MAX_NAME_CHARS:
            withheld.append(_withheld_note(f"variant_matches[{output_index}].name: {name_raw}"))
        else:
            name = name_raw

    hgvs_raw = raw.get("hgvs")
    hgvs: str | None = None
    if isinstance(hgvs_raw, str):
        if len(hgvs_raw) > _MAX_HGVS_CHARS:
            withheld.append(_withheld_note(f"variant_matches[{output_index}].hgvs: {hgvs_raw}"))
        else:
            hgvs = hgvs_raw

    pmids_count_raw = raw.get("pmids_count")
    pmids_count = pmids_count_raw if isinstance(pmids_count_raw, int) and pmids_count_raw >= 0 else 0

    clinical_significance, cs_withheld = _parse_clinical_significance(
        raw.get("data_clinical_significance"), output_index
    )
    withheld.extend(cs_withheld)

    match = Litvar2VariantMatch(
        litvar_id=litvar_id,
        rsid=rsid,
        gene=gene,
        name=name,
        hgvs=hgvs,
        pmids_count=pmids_count,
        clinical_significance=clinical_significance,
    )
    return match, withheld


def _parse_variant_matches(raw_list: list[Any]) -> tuple[list[Litvar2VariantMatch], list[str]]:
    """Build `variant_matches` from the raw autocomplete array, capped at `maxItems: 10`.

    The cap itself is spec-authorized truncation (Section 6.5's own
    `maxItems: 10`), the same kind `pmids` uses, not the withhold-not-
    truncate policy: unlike `pmids`, Section 6.5 provides no companion
    total-count field for `variant_matches`, so results beyond the cap are
    silently not returned. This module does not invent an unauthorized
    additive field for that count; only `fields_withheld` (F-3.3-03) is
    this ticket's authorized addition.

    F-3.3-J-03: `output_index`, the position a match will occupy in
    `matches` if kept, is computed as `len(matches)` BEFORE that match is
    appended, i.e. the count of matches already kept. This is what lets
    `_parse_variant_match`'s field-level notes stay correct after an
    earlier row is excluded: the row's `raw_index` in the source array and
    its eventual `output_index` in `variant_matches` diverge the moment
    any row is excluded, and only `output_index` is ever a valid position
    to cite in a `fields_withheld` note about `variant_matches[i]`.
    """
    matches: list[Litvar2VariantMatch] = []
    withheld: list[str] = []
    for raw_index, item in enumerate(raw_list[:_MAX_VARIANT_MATCHES]):
        output_index = len(matches)
        match, item_withheld = _parse_variant_match(item, raw_index, output_index)
        withheld.extend(item_withheld)
        if match is not None:
            matches.append(match)
    return matches, withheld


async def _variant_search(query: str) -> Litvar2LookupOutput:
    url = f"{_LITVAR2_BASE}/variant/autocomplete/"
    try:
        response = await ncbi_transport.execute_get(url, {"query": query}, family="litvar2")
    except ncbi_transport.TransportError as exc:
        return _error_output(
            "variant_search",
            f"LitVar2 variant_search for {query!r} failed: {exc}. Retry once; if this "
            "recurs, LitVar2 may be degraded.",
        )

    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers
    )
    if classification.status == "error":
        return _error_output(
            "variant_search",
            _litvar2_error_message(
                "variant_search", query, response.status_code, classification.error_message
            ),
        )

    body = classification.body
    if not isinstance(body, list):
        return _error_output(
            "variant_search",
            f"LitVar2 variant_search for {query!r} returned an unrecognized response shape "
            "(expected a JSON array), refusing to guess its meaning. Retry once; if this "
            "recurs, report it.",
        )

    if not body:
        return Litvar2LookupOutput(status="empty", mode="variant_search")

    matches, withheld = _parse_variant_matches(body)
    if not matches:
        # F-3.3-J-02: the API body was non-empty, but every row either
        # failed to parse as an object or had its identity field
        # (litvar_id/rsid) excluded for exceeding its cap, so nothing
        # usable actually survived. Shipping status="ok" here with an
        # empty variant_matches would be a confident success over zero
        # content, exactly the fabricated-success shape the phase premise
        # forbids (line 12 of tracker/phase_3.3.md: "A no-match query is
        # classified `empty`, not fabricated as `ok`"). Treat it as a
        # genuine no-match instead, mirroring pubtator_annotate.py's
        # identical guard for entity_lookup ("Every element failed to
        # parse as an object: treat the same as a genuine no-match rather
        # than a confident ok with an empty list").
        #
        # F-3.3-RR-01: this "empty" classification must NOT come at the
        # cost of the disclosure `_parse_variant_matches` already computed
        # for exactly these rows. `withheld` is non-empty whenever every
        # row was excluded rather than simply absent (a genuine `[]` body
        # never reaches this branch at all, see the `if not body:` return
        # above), so dropping it here would make a total-withholding
        # response byte-identical to a genuine no-match, the same silent-
        # loss failure class `_cap_fields_withheld`'s own docstring names
        # for the overflow case, now closed for the all-excluded case too.
        return Litvar2LookupOutput(
            status="empty",
            mode="variant_search",
            fields_withheld=_cap_fields_withheld(withheld) if withheld else None,
        )

    return Litvar2LookupOutput(
        status="ok",
        mode="variant_search",
        variant_matches=matches,
        source_url=_build_source_url(query),
        fields_withheld=_cap_fields_withheld(withheld) if withheld else None,
    )


# ---------------------------------------------------------------------------
# publications_lookup: GET /variant/get/{litvar_id}/publications
# ---------------------------------------------------------------------------


def _parse_pmids(raw: Any) -> tuple[list[str], int]:
    """`pmids` truncated to `maxItems: 50`, `total_pmids` carrying the TRUE count.

    `total_pmids` is computed over every well-formed entry in `raw`, before
    any truncation, per the module docstring's "spec-authorized" truncation
    policy; it never merely echoes `len(pmids)` after capping.
    """
    if not isinstance(raw, list):
        return [], 0
    all_pmids = [str(p) for p in raw if isinstance(p, (int, str))]
    total = len(all_pmids)
    truncated = all_pmids[:_MAX_PMIDS]
    # Defensive: a real PMID is always a small integer, well under the
    # 15-char item cap; this guard exists so a pathological value cannot
    # raise a pydantic.ValidationError deep inside output construction
    # rather than being handled here. Filtering here does not change
    # total_pmids, which was already computed above from the unfiltered
    # count.
    safe = [p for p in truncated if len(p) <= _MAX_PMID_CHARS]
    return safe, total


async def _publications_lookup(litvar_id: str) -> Litvar2LookupOutput:
    encoded_id = _quote_path_segment(litvar_id)
    url = f"{_LITVAR2_BASE}/variant/get/{encoded_id}/publications"
    try:
        response = await ncbi_transport.execute_get(url, {}, family="litvar2")
    except ncbi_transport.TransportError as exc:
        return _error_output(
            "publications_lookup",
            f"LitVar2 publications_lookup for {litvar_id!r} failed: {exc}. Retry once; if "
            "this recurs, LitVar2 may be degraded.",
        )

    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers
    )
    if classification.status == "error":
        return _error_output(
            "publications_lookup",
            _litvar2_error_message(
                "publications_lookup", litvar_id, response.status_code, classification.error_message
            ),
        )

    body = classification.body
    if not isinstance(body, dict):
        return _error_output(
            "publications_lookup",
            f"LitVar2 publications_lookup for {litvar_id!r} returned an unrecognized "
            "response shape (expected an object with a pmids array), refusing to guess "
            "its meaning. Retry once; if this recurs, report it.",
        )

    pmids, total = _parse_pmids(body.get("pmids"))
    if total == 0:
        # Section 6.5: a zero-linked-PMID variant is "expected to return
        # {"pmids": []}, consistent with LitVar2's other verified empty
        # behavior", but this specific shape was not independently live-
        # verified in this phase's pre-build probes (every reachable
        # litvar_id has at least one publication, since LitVar2's own
        # corpus is built from literature mining). Mapped the same way as
        # variant_search's own live-verified no-match case for consistency,
        # not fabricated certainty about an unobserved shape.
        return Litvar2LookupOutput(status="empty", mode="publications_lookup", total_pmids=0)

    return Litvar2LookupOutput(
        status="ok",
        mode="publications_lookup",
        pmids=pmids,
        total_pmids=total,
        source_url=_build_source_url_for_litvar_id(litvar_id),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def _litvar2_lookup_impl(tool_input: Litvar2LookupInput) -> Litvar2LookupOutput:
    """The real implementation. See `litvar2_lookup` below for the never-raises wrapper."""
    action = tool_input.root
    if isinstance(action, Litvar2VariantSearchInput):
        return await _variant_search(action.query)
    if isinstance(action, Litvar2PublicationsLookupInput):
        return await _publications_lookup(action.litvar_id)
    # Defensive, not assumed reachable: `Litvar2Action` is a closed,
    # discriminator-validated union pydantic has already checked at
    # construction time, so every real branch is handled above. Matches
    # ncbi_dbsnp.py's own trailing-branch discipline for its query_type
    # dispatch.
    return _error_output(
        "error",
        f"litvar2_lookup has no branch for input {action!r}. This is a tool defect, not "
        "a caller error; report it rather than retrying.",
    )


async def litvar2_lookup(input_data: Litvar2LookupInput) -> Litvar2LookupOutput:
    """Variant-to-literature evidence lookup over LitVar2. Never raises.

    See the module docstring for the two independent modes. This public
    entry point is a thin wrapper around `_litvar2_lookup_impl`: every
    expected failure (a transport error, a rejected input, a malformed
    upstream field) is already classified and returned as a `status:
    "error"` output by the functions above. This wrapper's own
    `try`/`except` is the last-resort boundary for an UNEXPECTED exception,
    the same outer-boundary pattern `ncbi_dbsnp.py`'s and `ncbi_efetch.py`'s
    dispatchers use, per `.claude/rules/production-standards.md`'s
    retry-safety gate: an error message must say what to do next, not just
    what failed.
    """
    try:
        return await _litvar2_lookup_impl(input_data)
    except Exception as exc:  # noqa: BLE001 - the module's deliberate last-resort catch
        mode = getattr(getattr(input_data, "root", None), "mode", "error")
        return _error_output(
            str(mode),
            f"litvar2_lookup raised an unexpected {type(exc).__name__} instead of "
            f"returning a classified result: {exc}. Retry once; if this recurs, this "
            "tool has a defect that needs fixing before it can be trusted.",
        )
