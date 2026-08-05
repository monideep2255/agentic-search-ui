"""E-utilities body-inspecting actions for `ncbi_efetch` (T-3.1-04/05/06/07).

Implements four of the tool's seven actions: `search` (ESearch), `summary`
(ESummary), `fetch` (EFetch), `link` (ELink). `coordinate_overlap`,
`dataset_report`, and `pubchem_property` belong to sibling modules
(`ncbi_coordinate_overlap`, `ncbi_datasets_actions`, `ncbi_pubchem_actions`),
built by other builders in this phase. This module never imports them and
they never import this one.

Each function takes the already-validated, action-specific pydantic model
from `ncbi_efetch_schemas` (the member of `NcbiEfetchInput`'s discriminated
union, i.e. what a caller reaches via `.root` after `model_validate`) and
returns an `NcbiEfetchOutput`. Nothing here raises for an expected failure:
a `ncbi_transport.TransportError` (timeout, connection failure, rate limit)
is caught and mapped to `status: "error"` with an actionable message, per
`.claude/rules/production-standards.md`'s retry-safety gate. The dispatcher
module (`ncbi_efetch.py`, a later ticket, not written here) is expected to
call these as plain async functions, one per `action` value:

    resolved = NcbiEfetchInput.model_validate(payload).root
    if resolved.action == "search":
        return await ncbi_eutils_actions.search(resolved)

## The four traps this module exists to not commit

1. UNKNOWN FIELD TAGS ARE SILENTLY IGNORED (Tool_implementation_mechanics.md
   :96-101, premise gate case 15). E-utilities does not error on an unknown
   ESearch `field_tags` entry; it silently falls back to a broad, unfiltered
   search. So every tag in `NcbiEfetchSearchInput.field_tags` is validated
   against a live-fetched, in-process-cached EInfo field list for that `db`
   BEFORE the ESearch call is ever made. An unvalidated tag returns
   `status: "error"` with zero network calls beyond whatever EInfo fetch the
   validation itself needed (cached after the first call per `db`, this
   process's lifetime; see `_get_einfo_fields` below). The list is never
   hardcoded: hardcoding it is exactly the "assumed field list" failure mode
   this trap exists to prevent, since NCBI adds and removes searchable
   fields over time (`docs/ncbi/NCBI_databases_and_APIs_reference.md`'s own
   re-verification notes record field counts drifting between two sessions
   three weeks apart).

2. THE FETCH HOST IS NOT THE RECORD HOST (Tool_implementation_mechanics.md
   :265-270, premise gate case 4). Every request in this module goes to
   `eutils.ncbi.nlm.nih.gov`. Every `source_url` this module emits goes
   through `_build_record_url`, which maps `db` to the human-facing record
   host (`pubmed.ncbi.nlm.nih.gov`, `www.ncbi.nlm.nih.gov`, `omim.org`),
   never the fetch host. `_build_record_url` also re-checks the built URL
   against `NCBI_EFETCH_RECORD_URL_PATTERN` before returning it, as defense
   in depth on top of `NcbiEfetchRecord`'s own schema-level pattern
   validator: a wrong template here fails closed (`None`, no citation)
   rather than raising a `pydantic.ValidationError` out of a tool call.

3. ELINK WITHOUT AN EXPLICIT TARGET DB (Tool_implementation_mechanics.md
   :89-94, premise gate case 5). `NcbiEfetchLinkInput.db` is already
   required at the schema level (`ncbi_efetch_schemas.py`), so this module
   never omits it from the ELink request. The mechanism trap continues past
   the request, though: ELink's JSON response can carry several
   `linksetdbs` entries under one `linkset` (direct references, GeneRIF-
   derived references, and more), each with its own `dbto`. `link` below
   filters to `linksetdb.dbto == params.db` before collecting any ids, so a
   linksetdb aimed at a different db (which explicit targeting is supposed
   to prevent from mattering, but a defensive filter costs nothing and
   catches a server-side surprise) can never leak into the result.

4. EMPTY IS NOT ERROR AND ERROR IS NOT EMPTY (Technical_specification.md
   Section 6.2, lines 973-982; premise gate cases 7, 8, 9a). This module
   never re-decides `ok`/`empty`/`error` for an E-utilities response; that
   verdict comes entirely from `ncbi_transport.classify_eutils_response`,
   which inspects the body and never the HTTP status. This module's own job
   is narrower and still load-bearing: on `status: "empty"`, always emit
   `records: []`, never a placeholder record. A blank `<PubmedArticleSet>`
   with a citation attached would be a citation to nothing (case 8's own
   language). `search`, `summary`, `fetch`, and `link` below each return
   `records: []` for `empty` before doing any field extraction at all.

## Trust table: which databases are live-verified versus taken on trust

Required by this ticket, and worth stating plainly rather than letting the
extraction code imply more certainty than it has.

Live-verified in THIS repository (premise gate assertions on content, not
merely presence):
    - `gene` ESummary fields `name`, `description`, `chromosome`
      (case 2). `maplocation`, `genomicinfo`, `mim`, `organism` are
      extracted at the same trust level as the rest of the per-db table
      below (present in Section 6.2's table, not independently
      re-verified field-by-field here).
    - `pubmed` EFetch XML shape, `rettype=abstract&retmode=xml`
      (`PubmedArticleSet`/`PubmedArticle`/`MedlineCitation`, cases 4, 8).
    - `gene` ESearch via `db=gene&term=...[sym] AND ...[orgn]` (case 1).
    - `gene`-to-`pubmed` ELink with an explicit target db (case 5).

TRUSTED FROM THE LOCKED SPEC, NOT INDEPENDENTLY LIVE-VERIFIED IN THIS
TICKET: the `pubmed`, `clinvar`, `dbvar`, `omim`, `medgen`, `gtr` ESummary
field lists in `_SUMMARY_FIELDS_BY_DB` below, copied verbatim from
Technical_specification.md Section 6.2's table (lines 946-957). ClinVar's
`germline_classification` is handled as an opaque object rather than a flat
scalar, per the one confirmed drift point in
`docs/ncbi/Tool_implementation_mechanics.md:110-115`; this module never
assumes a shape for it beyond "present or absent", it is passed through
unmodified.

A SPEC GAP, FLAGGED RATHER THAN SILENTLY WORKED AROUND: Section 6.2's
`SummaryDb` enum (`ncbi_efetch_schemas.py`) names 12 databases, but its own
verified-fields table (line 946-957) names field sets for only 8 of them.
`bioproject`, `biosample`, `assembly`, `gds` are schema-legal `summary`
targets with no documented field list at all. Separately, the table's
`sra` row ("22 ESearch-indexed fields... plus EFetch sample attributes")
describes ESearch field TAGS and EFetch attributes, not ESummary JSON
response keys, so it cannot be read as an ESummary extraction list either.
Both cases fall through to `_generic_summary_fields` below: the full raw
per-uid object, capped at the schema's `maxProperties: 40`, rather than
guessing a subset nobody has verified. This is a real, load-bearing
decision for this ticket's report, not a hypothetical: any `summary` call
against `bioproject`, `biosample`, `assembly`, `gds`, or `sra` runs on the
generic path, unverified.

Record-page URL templates (`_RECORD_URL_TEMPLATES`): only `pubmed` and
`gene` are exercised by the premise gate (case 4 checks `pubmed` directly by
host; no case checks `gene`'s `source_url` value, only that `search` and
`summary` return the right ids and fields). The remaining ten templates are
built from each database's well-known NCBI URL shape, not independently
live-verified against a real record page in this ticket.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (T-3.1-02, execute_get,
      classify_eutils_response, TransportError and its subclasses)
    - system_03_search_agent.tools.ncbi_efetch_schemas (T-3.1-03, every
      input model this module accepts and the single output shape)

Reads:
    - Nothing at import time. `NCBI_API_KEY` is read indirectly, inside
      `ncbi_transport.execute_get`, never by this module directly.

Writes:
    - Nothing. Outbound HTTPS requests only, via `ncbi_transport`.

Depended by:
    - system_03_search_agent.tools.ncbi_efetch (the dispatcher; not yet
      written, a later ticket in this phase)
    - tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py, via
      `ncbi_efetch.ncbi_efetch`, cases 1, 2, 4, 5, 7, 8, 9a, 15
    - tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from typing import Any, Final
from xml.etree import ElementTree

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NCBI_EFETCH_RECORD_URL_PATTERN,
    NcbiEfetchFetchInput,
    NcbiEfetchLinkInput,
    NcbiEfetchOutput,
    NcbiEfetchRecord,
    NcbiEfetchSearchInput,
    NcbiEfetchSummaryInput,
)

_EUTILS_BASE: Final[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_EINFO_ENDPOINT: Final[str] = _EUTILS_BASE + "einfo.fcgi"
_ESEARCH_ENDPOINT: Final[str] = _EUTILS_BASE + "esearch.fcgi"
_ESUMMARY_ENDPOINT: Final[str] = _EUTILS_BASE + "esummary.fcgi"
_EFETCH_ENDPOINT: Final[str] = _EUTILS_BASE + "efetch.fcgi"
_ELINK_ENDPOINT: Final[str] = _EUTILS_BASE + "elink.fcgi"

# Matches NcbiEfetchRecord.fields' own maxProperties: 40 (Section 6.2 line
# 917). Enforced here too, defensively, so a wide raw payload (only
# reachable via the unverified fallback paths below) fails closed to a
# capped dict rather than raising pydantic.ValidationError out of a tool
# call. See NcbiEfetchRecord._cap_fields_count in ncbi_efetch_schemas.py
# for the schema-level twin of this cap.
_MAX_RECORD_FIELDS: Final[int] = 40

# Free text pulled out of an EFetch record body (a title, an abstract) is
# untrusted external content per .claude/rules/ai-security-standards.md,
# and .claude/rules/production-standards.md's bounded-context-items gate
# requires a hard character cap on every context fragment injected into a
# prompt, not only a count cap on the number of fields. NcbiEfetchRecord's
# schema has no per-value maxLength on `fields` (only maxProperties on the
# dict), so the cap is applied here, at extraction time.
_MAX_FIELD_VALUE_CHARS: Final[int] = 4000

_MAX_RECORDS_RETURNED: Final[int] = 100


class EInfoUnavailableError(Exception):
    """The EInfo field list for a db could not be fetched or parsed.

    Raised only inside this module and always caught before it can escape a
    public function; field_tags validation treats this as "could not
    validate", which fails closed to status: "error" rather than silently
    admitting an unvalidated tag.
    """


# ---------------------------------------------------------------------------
# Trap 1: field_tags validated against a live, cached EInfo field list.
# ---------------------------------------------------------------------------

# db -> frozenset of lowercased EInfo field names. Populated lazily, once
# per db, for this process's lifetime. Never hardcoded: NCBI's field lists
# drift (docs/ncbi/NCBI_databases_and_APIs_reference.md's re-verification
# notes record field counts moving between two sessions three weeks apart),
# so a hardcoded guess is exactly the failure mode trap 1 exists to close.
_einfo_field_cache: dict[str, frozenset[str]] = {}
_einfo_cache_lock = asyncio.Lock()


def reset_einfo_cache_for_tests() -> None:
    """Clear the cached EInfo field lists. Test-only; production never calls this."""
    _einfo_field_cache.clear()


async def _get_einfo_fields(db: str) -> frozenset[str]:
    """Return the lowercased set of real EInfo field names for `db`.

    Cached after the first successful fetch for this `db`, this process's
    lifetime. A double-checked lock avoids two concurrent callers each
    issuing their own EInfo request for the same db on a cold cache.
    """
    cached = _einfo_field_cache.get(db)
    if cached is not None:
        return cached
    async with _einfo_cache_lock:
        cached = _einfo_field_cache.get(db)
        if cached is not None:
            return cached
        response = await ncbi_transport.execute_get(
            _EINFO_ENDPOINT,
            {"db": db, "retmode": "json"},
            family="eutils",
            include_api_key=True,
        )
        try:
            body = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise EInfoUnavailableError(
                f"EInfo response for db {db!r} is not valid JSON, cannot validate field_tags"
            ) from exc
        dbinfo = body.get("einforesult", {}).get("dbinfo") if isinstance(body, dict) else None
        if not isinstance(dbinfo, dict):
            raise EInfoUnavailableError(
                f"EInfo response for db {db!r} has no einforesult.dbinfo, "
                f"cannot validate field_tags"
            )
        field_list = dbinfo.get("fieldlist")
        if not isinstance(field_list, list):
            raise EInfoUnavailableError(
                f"EInfo response for db {db!r} has no fieldlist, cannot validate field_tags"
            )
        names = frozenset(
            str(entry["name"]).strip().lower()
            for entry in field_list
            if isinstance(entry, dict) and "name" in entry
        )
        _einfo_field_cache[db] = names
        return names


async def _reject_unknown_field_tags(db: str, field_tags: list[str]) -> str | None:
    """Return an error message if any tag is not a real EInfo field for `db`, else None.

    The request that would have used an invalid tag is never sent: this is
    called, and must return None, before any ESearch call is issued. On a
    validation failure this fails closed (an inability to validate is
    treated the same as an invalid tag), rather than letting an unverified
    tag through.
    """
    if not field_tags:
        return None
    try:
        valid_fields = await _get_einfo_fields(db)
    except (EInfoUnavailableError, ncbi_transport.TransportError) as exc:
        return (
            f"could not validate field_tags against the EInfo field list for db {db!r} "
            f"({exc}); refusing to guess whether they are real fields, retry once EInfo "
            f"is reachable"
        )
    unknown = [tag for tag in field_tags if tag.strip().lower() not in valid_fields]
    if unknown:
        return (
            f"field_tags {unknown!r} are not real EInfo fields for db {db!r}; "
            f"E-utilities would silently broaden the search instead of erroring on them, "
            f"so this request was never sent. Retry with a tag from the {len(valid_fields)} "
            f"real fields for {db!r}, or omit field_tags"
        )
    return None


def _apply_field_tags(term: str, field_tags: list[str]) -> str:
    """Scope `term` to specific ESearch fields, once every tag has validated clean.

    Builder decision, not pinned by the premise gate (case 15 only pins the
    rejection path; no case exercises a valid, non-empty field_tags list).
    Each tag becomes `term[tag]`, OR-joined and parenthesized when more than
    one is given, so the caller's free-text term is matched only within the
    named field(s) rather than E-utilities' own default (a broad, unscoped
    search across every indexed field). An empty field_tags list, the
    common case (see case 1, whose term already embeds its own `[sym]`/
    `[orgn]` tags directly), leaves `term` untouched.
    """
    if not field_tags:
        return term
    if len(field_tags) == 1:
        return f"{term}[{field_tags[0]}]"
    clauses = " OR ".join(f"{term}[{tag}]" for tag in field_tags)
    return f"({clauses})"


# ---------------------------------------------------------------------------
# Trap 2: fetch host versus record host. One mapping, reused by every action.
# ---------------------------------------------------------------------------

# Only "pubmed" and "gene" are exercised by the premise gate (case 4 checks
# pubmed's source_url directly; case 1/2 check gene's ids and fields, not
# its source_url). The remaining templates follow each database's
# documented NCBI record-page URL shape and are not independently
# live-verified in this ticket. Every value here is checked against
# NCBI_EFETCH_RECORD_URL_PATTERN at module import time (see the assertion
# loop below), so a wrong template fails at import, not silently at
# citation time.
_RECORD_URL_TEMPLATES: Final[dict[str, str]] = {
    "pubmed": "https://pubmed.ncbi.nlm.nih.gov/{id}/",
    "gene": "https://www.ncbi.nlm.nih.gov/gene/{id}",
    "clinvar": "https://www.ncbi.nlm.nih.gov/clinvar/variation/{id}/",
    "dbvar": "https://www.ncbi.nlm.nih.gov/dbvar/variants/{id}/",
    "omim": "https://omim.org/entry/{id}",
    "medgen": "https://www.ncbi.nlm.nih.gov/medgen/{id}",
    "gtr": "https://www.ncbi.nlm.nih.gov/gtr/tests/{id}/",
    "sra": "https://www.ncbi.nlm.nih.gov/sra/{id}",
    "bioproject": "https://www.ncbi.nlm.nih.gov/bioproject/{id}",
    "biosample": "https://www.ncbi.nlm.nih.gov/biosample/{id}",
    "assembly": "https://www.ncbi.nlm.nih.gov/assembly/{id}",
    "gds": "https://www.ncbi.nlm.nih.gov/gds/{id}",
    "taxonomy": "https://www.ncbi.nlm.nih.gov/taxonomy/{id}",
    "mesh": "https://www.ncbi.nlm.nih.gov/mesh/{id}",
}


def _build_record_url(db: str, record_id: str) -> str | None:
    """Map a fetch-host result to its human-facing record-page URL, or None.

    Defense in depth on top of NcbiEfetchRecord's own schema-level pattern
    validator: a template that somehow produced a URL outside the allowed
    hosts fails closed here (returns None, so the record ships with no
    citation) rather than raising pydantic.ValidationError out of a tool
    call.
    """
    template = _RECORD_URL_TEMPLATES.get(db)
    if template is None or not record_id:
        return None
    url = template.format(id=urllib.parse.quote(record_id, safe=""))
    if re.match(NCBI_EFETCH_RECORD_URL_PATTERN, url) is None:
        return None
    return url


# Fail at import time, not at first citation, if a template above is wrong.
for _db_name, _template in _RECORD_URL_TEMPLATES.items():
    _sample_url = _template.format(id="1")
    assert re.match(NCBI_EFETCH_RECORD_URL_PATTERN, _sample_url) is not None, (
        f"_RECORD_URL_TEMPLATES[{_db_name!r}] produces a URL the schema's own "
        f"NCBI_EFETCH_RECORD_URL_PATTERN would reject: {_sample_url!r}"
    )
del _db_name, _template, _sample_url


# ---------------------------------------------------------------------------
# Shared helpers.
# ---------------------------------------------------------------------------


def _cap_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Defensive cap matching NcbiEfetchRecord.fields' maxProperties: 40.

    Every verified extraction path below selects a small, named subset (at
    most 12 keys, sra's row in Section 6.2's table), well under this bound.
    Only the unverified fallback paths (a summary db with no documented
    field list, a fetch db/retmode this ticket did not verify) can
    realistically exceed it, since they pass a raw upstream object through.
    """
    if len(fields) <= _MAX_RECORD_FIELDS:
        return fields
    return dict(list(fields.items())[:_MAX_RECORD_FIELDS])


def _cap_text(value: str) -> str:
    """Hard character cap on untrusted free text pulled from a record body.

    See the module docstring's "bounded context items" note: the schema
    caps field COUNT, not per-value length, so the cap on any one value's
    length lives here.
    """
    if len(value) <= _MAX_FIELD_VALUE_CHARS:
        return value
    return value[:_MAX_FIELD_VALUE_CHARS] + " [truncated]"


def _truncate_error(message: str | None) -> str:
    if not message:
        return "the upstream API returned an error with no message"
    return message[:500]


def _error_output(action: str, message: str | None) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="error",
        action=action,
        records=[],
        record_count=0,
        truncated=False,
        error=_truncate_error(message),
    )


def _empty_output(action: str) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="empty", action=action, records=[], record_count=0, truncated=False
    )


async def _get_or_error(
    action: str, url: str, params: dict[str, Any]
) -> ncbi_transport.ClassificationResult | NcbiEfetchOutput:
    """Issue the E-utilities GET and classify it, or return a ready error output.

    Callers check `isinstance(result, NcbiEfetchOutput)` to detect the
    transport-failure short circuit versus a genuine ClassificationResult.
    """
    try:
        response = await ncbi_transport.execute_get(
            url, params, family="eutils", include_api_key=True
        )
    except ncbi_transport.TransportError as exc:
        return _error_output(action, str(exc))
    return ncbi_transport.classify_eutils_response(
        content_type=response.headers.get("content-type", ""), text=response.text
    )


# ---------------------------------------------------------------------------
# search (ESearch).
# ---------------------------------------------------------------------------


async def search(params: NcbiEfetchSearchInput) -> NcbiEfetchOutput:
    """ESearch: `db=<db>&term=<term>`. Trap 1 (field_tags) and trap 4 (the near-miss pair)."""
    tag_error = await _reject_unknown_field_tags(params.db, params.field_tags)
    if tag_error is not None:
        return _error_output("search", tag_error)

    request_params: dict[str, Any] = {
        "db": params.db,
        "term": _apply_field_tags(params.term, params.field_tags),
        "retmode": "json",
        "retmax": params.retmax,
    }
    if params.use_history:
        request_params["usehistory"] = "y"

    result = await _get_or_error("search", _ESEARCH_ENDPOINT, request_params)
    if isinstance(result, NcbiEfetchOutput):
        return result
    if result.status == "error":
        return _error_output("search", result.error_message)
    if result.status == "empty":
        return _empty_output("search")

    envelope = result.body.get("esearchresult", {}) if isinstance(result.body, dict) else {}
    idlist = [str(uid) for uid in (envelope.get("idlist") or [])]

    fields: dict[str, Any] = {"idlist": idlist}
    if params.use_history:
        if "webenv" in envelope:
            fields["webenv"] = envelope["webenv"]
        if "querykey" in envelope:
            fields["query_key"] = envelope["querykey"]

    total_available: int | None = None
    count_raw = envelope.get("count")
    if count_raw is not None:
        try:
            total_available = int(count_raw)
        except (TypeError, ValueError):
            total_available = None

    record_count = len(idlist)
    truncated = total_available is not None and total_available > record_count

    return NcbiEfetchOutput(
        status="ok",
        action="search",
        records=[NcbiEfetchRecord(db=params.db, fields=_cap_fields(fields))],
        record_count=record_count,
        total_available=total_available,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# summary (ESummary), and the verified per-database field extraction.
# ---------------------------------------------------------------------------

# Section 6.2's verified ESummary field table (Technical_specification.md
# lines 946-957). See the module docstring's trust table for which of these
# are live-verified in THIS repo (gene's name/description/chromosome, case
# 2) versus taken on trust from the locked spec (everything else here).
_SUMMARY_FIELDS_BY_DB: Final[dict[str, tuple[str, ...]]] = {
    "pubmed": (
        "authors", "source", "fulljournalname", "pubdate", "elocationid",
        "articleids", "pubtype",
    ),
    "gene": (
        "name", "description", "chromosome", "maplocation", "genomicinfo", "mim", "organism",
    ),
    # variation_set carries canonical_spdi nested inside it (Section 6.2
    # names "variation_set.canonical_spdi"); passed through as one object
    # rather than flattened, since flattening an unverified nested shape
    # risks guessing a key that does not exist.
    "clinvar": ("accession", "title", "germline_classification", "variation_set", "genes"),
    "dbvar": (
        "CH", "BASE", "CHR_END", "VT", "VLEN", "CLIN", "PATHO_RNG",
        "AFR", "AMR", "EAS", "EUR", "SAS", "OTH", "FREQ",
        "OMIM", "GENE_NAME", "ASSM",
    ),
    "omim": ("oid", "title", "alttitles", "locus"),
    "medgen": ("conceptid", "title", "definition", "semantictype"),
    "gtr": (
        "accession", "testname", "genelist", "conditionlist",
        "analyticalvalidity", "clinicalvalidity", "offerer",
    ),
}


def _generic_summary_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Fallback for a db with no verified field list: bioproject, biosample,
    assembly, gds (undocumented in Section 6.2's table) and sra (the
    table's row describes ESearch field tags, not ESummary JSON keys; see
    the module docstring's "spec gap" note). Passes the raw per-uid object
    through, minus the redundant `uid` key, rather than guessing a subset
    nobody has verified.
    """
    return {key: value for key, value in entry.items() if key != "uid"}


async def summary(params: NcbiEfetchSummaryInput) -> NcbiEfetchOutput:
    """ESummary: `db=<db>&id=<ids>&retmode=json`. Case 2 live-verifies db=gene."""
    request_params = {"db": params.db, "id": ",".join(params.ids), "retmode": "json"}

    result = await _get_or_error("summary", _ESUMMARY_ENDPOINT, request_params)
    if isinstance(result, NcbiEfetchOutput):
        return result
    if result.status == "error":
        return _error_output("summary", result.error_message)
    if result.status == "empty":
        return _empty_output("summary")

    envelope = result.body.get("result", {}) if isinstance(result.body, dict) else {}
    uids = [str(uid) for uid in (envelope.get("uids") or [])]
    known_fields = _SUMMARY_FIELDS_BY_DB.get(params.db)

    records: list[NcbiEfetchRecord] = []
    for uid in uids[:_MAX_RECORDS_RETURNED]:
        entry = envelope.get(uid)
        if not isinstance(entry, dict):
            continue
        if known_fields is not None:
            extracted = {name: entry[name] for name in known_fields if name in entry}
        else:
            extracted = _generic_summary_fields(entry)
        records.append(
            NcbiEfetchRecord(
                id=uid,
                db=params.db,
                fields=_cap_fields(extracted),
                source_url=_build_record_url(params.db, uid),
            )
        )

    if not records:
        return _empty_output("summary")

    return NcbiEfetchOutput(
        status="ok",
        action="summary",
        records=records,
        record_count=len(records),
        truncated=False,
    )


# ---------------------------------------------------------------------------
# fetch (EFetch). Trap 2 (record host) and trap 4 (empty fabricates nothing).
# ---------------------------------------------------------------------------


def _extract_pubmed_articles(root: ElementTree.Element) -> list[NcbiEfetchRecord]:
    """Extract one record per <PubmedArticle> from a live-verified PubmedArticleSet.

    Only field extracted with any confidence: title and abstract text, both
    capped per `_cap_text` since they are untrusted free text pulled
    straight from a source publication (ai-security-standards.md). A
    PubmedArticle with no <PMID> is skipped rather than emitted with
    `id: None`, since an uncitable record with no identifier at all is
    worse than one fewer record.
    """
    records: list[NcbiEfetchRecord] = []
    for article_el in root.findall("PubmedArticle"):
        pmid_el = article_el.find("MedlineCitation/PMID")
        pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else None
        if not pmid:
            continue

        title_el = article_el.find("MedlineCitation/Article/ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        abstract_parts = [
            "".join(node.itertext()).strip()
            for node in article_el.findall("MedlineCitation/Article/Abstract/AbstractText")
        ]
        abstract = " ".join(part for part in abstract_parts if part)

        fields: dict[str, Any] = {}
        if title:
            fields["title"] = _cap_text(title)
        if abstract:
            fields["abstract"] = _cap_text(abstract)

        records.append(
            NcbiEfetchRecord(
                id=pmid,
                db="pubmed",
                fields=_cap_fields(fields),
                source_url=_build_record_url("pubmed", pmid),
            )
        )
    return records


def _extract_generic_fetch_records(db: str, body: Any) -> list[NcbiEfetchRecord]:
    """Fallback for a fetch db/retmode this ticket did not live-verify.

    Only db=pubmed, retmode=xml is verified (premise gate cases 4 and 8).
    Section 6.2 names no verified per-id JSON field shape for EFetch outside
    that path, so this returns one aggregate record with the raw body
    capped, rather than guessing a per-id split nobody has confirmed.
    """
    if not isinstance(body, dict):
        return []
    return [NcbiEfetchRecord(db=db, fields=_cap_fields(_generic_summary_fields(body)))]


async def fetch(params: NcbiEfetchFetchInput) -> NcbiEfetchOutput:
    """EFetch: `db=<db>&id=<ids>&rettype=&retmode=`."""
    request_params = {
        "db": params.db,
        "id": ",".join(params.ids),
        "rettype": params.rettype,
        "retmode": params.retmode,
    }

    result = await _get_or_error("fetch", _EFETCH_ENDPOINT, request_params)
    if isinstance(result, NcbiEfetchOutput):
        return result
    if result.status == "error":
        return _error_output("fetch", result.error_message)
    if result.status == "empty":
        # Trap 4: an empty <PubmedArticleSet> (or an unrecognized-but-empty
        # body) fabricates zero records. Never a placeholder with a
        # source_url, which would be a citation to nothing.
        return _empty_output("fetch")

    if params.db == "pubmed" and isinstance(result.body, ElementTree.Element):
        records = _extract_pubmed_articles(result.body)
    else:
        records = _extract_generic_fetch_records(params.db, result.body)

    if not records:
        return _empty_output("fetch")

    truncated = len(records) > _MAX_RECORDS_RETURNED
    kept = records[:_MAX_RECORDS_RETURNED]
    return NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=kept,
        record_count=len(kept),
        total_available=len(records) if truncated else None,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# link (ELink). Trap 3: explicit target db, never the ELink default.
# ---------------------------------------------------------------------------


async def link(params: NcbiEfetchLinkInput) -> NcbiEfetchOutput:
    """ELink: `dbfrom=<dbfrom>&db=<db>&id=<ids>`. `db` is always explicit (schema-required)."""
    request_params = {
        "dbfrom": params.dbfrom,
        "db": params.db,
        "id": ",".join(params.ids),
        "retmode": "json",
    }

    result = await _get_or_error("link", _ELINK_ENDPOINT, request_params)
    if isinstance(result, NcbiEfetchOutput):
        return result
    if result.status == "error":
        return _error_output("link", result.error_message)
    if result.status == "empty":
        return _empty_output("link")

    linksets = result.body.get("linksets") if isinstance(result.body, dict) else None
    linked_ids: list[str] = []
    if isinstance(linksets, list):
        for linkset in linksets:
            if not isinstance(linkset, dict):
                continue
            for linksetdb in linkset.get("linksetdbs") or []:
                if not isinstance(linksetdb, dict):
                    continue
                # Trap 3's enforcement point: only a linksetdb whose dbto
                # matches the caller's explicit target db ever contributes
                # ids. A computed neighbor set under a different dbto
                # (which explicit targeting is supposed to prevent from
                # appearing at all) is filtered out defensively here too.
                if linksetdb.get("dbto") != params.db:
                    continue
                for linked_id in linksetdb.get("links") or []:
                    linked_ids.append(str(linked_id))

    seen: set[str] = set()
    deduped_ids: list[str] = []
    for linked_id in linked_ids:
        if linked_id not in seen:
            seen.add(linked_id)
            deduped_ids.append(linked_id)

    if not deduped_ids:
        return _empty_output("link")

    truncated = len(deduped_ids) > _MAX_RECORDS_RETURNED
    kept_ids = deduped_ids[:_MAX_RECORDS_RETURNED]
    records = [
        NcbiEfetchRecord(id=lid, db=params.db, source_url=_build_record_url(params.db, lid))
        for lid in kept_ids
    ]

    return NcbiEfetchOutput(
        status="ok",
        action="link",
        records=records,
        record_count=len(records),
        total_available=len(deduped_ids) if truncated else None,
        truncated=truncated,
    )
