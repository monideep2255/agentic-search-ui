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

A SPEC GAP, NOW CLOSED WITH LIVE-PROBED FIELD LISTS RATHER THAN A RAW
PASSTHROUGH: Section 6.2's `SummaryDb` enum (`ncbi_efetch_schemas.py`) names
12 databases, but its own verified-fields table (line 946-957) names field
sets for only 8 of them. `bioproject`, `biosample`, `assembly`, `gds` are
schema-legal `summary` targets with no documented field list at all.
Separately, the table's `sra` row ("22 ESearch-indexed fields... plus EFetch
sample attributes") describes ESearch field TAGS and EFetch attributes, not
ESummary JSON response keys, so it cannot be read as an ESummary extraction
list either.

All five used to fall through to `_generic_summary_fields`, which copied
every response key. F-3.1-10 (reopened) closed that: each now carries a real
allowlist in `_SUMMARY_FIELDS_BY_DB`, chosen from the keys a live ESummary
call actually returns for that db, probed while writing the fix. A count cap
of 40 keys was never a field filter, and four of the five return fewer than
40 keys anyway, so the cap never engaged and the passthrough was total. The
allowlists are live-probed for key presence and shape, not semantically
verified field by field, which puts them at the same trust tier as the
`dbvar`/`omim`/`medgen`/`gtr` rows above rather than at the `gene` row's.

As a result every one of `SummaryDb`'s 12 databases is allowlisted, and the
`summary` action never reaches `_generic_summary_fields`. That function's
one remaining caller is `_extract_generic_fetch_records`, the unverified
EFetch fallback, where the response shape is unknown by definition and there
is nothing to allowlist against.

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

# Bounds for `_cap_value`'s walk through nested dicts and lists. A nested
# container beyond this depth is collapsed to a capped string rather than
# walked further, so a deeply self-nested payload can neither exhaust the
# stack nor carry uncapped text past the per-value cap.
_MAX_NESTING_DEPTH: Final[int] = 6
_MAX_NESTED_ITEMS: Final[int] = 100


class EInfoUnavailableError(Exception):
    """The EInfo field list for a db could not be fetched or parsed.

    Raised only inside this module and always caught before it can escape a
    public function; field_tags validation treats this as "could not
    validate", which fails closed to status: "error" rather than silently
    admitting an unvalidated tag.
    """


class EInfoStatusError(EInfoUnavailableError):
    """EInfo answered with a transient or client-error HTTP status.

    F-3.1-19 remainder: `_get_einfo_fields` never read `response.status_code`,
    so a 429 or 503 on the EInfo hop surfaced as "could not validate
    field_tags", which points the next agent step at rewriting the request
    when the correct next action is a backoff and retry. This subclass
    carries the already-actionable message built by
    `ncbi_transport.http_status_error_message`, so `_reject_unknown_field_tags` can pass it
    through verbatim instead of burying it inside a validation wrapper.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.actionable_message = message


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


# Re-review round 1 (2026-08-07): tags live-verified to work against real
# Entrez that EInfo's own fieldlist does not list for that db. Keyed by db,
# lowercased. `db=gene`'s "sym" is the only entry today because it is the
# only tag this module's code and docs actually use; this is not an
# attempt to enumerate every hidden tag EInfo omits for every database.
# Extend it only after live-verifying a new tag the same way: confirm the
# querytranslation echoes the tag back (not silently dropped to All
# Fields) and the result count matches a known-good control.
_EINFO_HIDDEN_VALID_FIELDS: Final[dict[str, frozenset[str]]] = {
    "gene": frozenset({"sym"}),
}


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
        # F-3.1-19 remainder: the EInfo hop reads its status code through the
        # same mapping every other call site uses. Without this a 429 or 503
        # here fell through to the JSON parse below and surfaced as "could
        # not validate field_tags", which tells the next agent step to rewrite
        # its request when the correct action is to back off and retry.
        status_message = ncbi_transport.http_status_error_message("EInfo", response)
        if status_message is not None:
            raise EInfoStatusError(status_message)
        try:
            body = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise EInfoUnavailableError(
                f"EInfo response for db {db!r} is not valid JSON, cannot validate field_tags"
            ) from exc
        # Re-review round 1, adversarial pass (2026-08-07): live EInfo
        # returns `einforesult.dbinfo` as a ONE-ELEMENT LIST, not a dict,
        # for every db probed (gene, pubmed, clinvar). The dict check
        # below rejected every real EInfo response unconditionally, so
        # `_reject_unknown_field_tags` never validated a single field tag
        # against a live field list; every `field_tags` call failed
        # closed on "cannot validate", including this module's own
        # canonical `[sym]` example. `field_tags` has no production
        # caller as of this fix, so the practical exposure was zero, but
        # the premise gate's own field_tags case (15) was passing for the
        # wrong reason: the rejection it asserts was true, just not
        # because of the property it claims to test.
        einforesult = body.get("einforesult", {}) if isinstance(body, dict) else {}
        dbinfo_raw = einforesult.get("dbinfo")
        if isinstance(dbinfo_raw, list):
            dbinfo = dbinfo_raw[0] if dbinfo_raw else None
        else:
            dbinfo = dbinfo_raw
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
        # EInfo's own fieldlist is not a complete list of every tag NCBI's
        # query parser accepts. Live-verified: `BRCA1[sym] AND human[orgn]`
        # scopes correctly (querytranslation echoes `[sym]` back verbatim,
        # count 1, matching `BRCA1[gene]`), but no entry in `db=gene`'s
        # EInfo fieldlist has abbreviation SYM; the closest entries are
        # GENE ("Gene Name", description "Symbol or symbols of the gene")
        # and PREF ("Preferred Symbol"). `sym` is a real, working, legacy
        # Entrez tag EInfo simply does not advertise. Validating against
        # EInfo alone would over-reject it, the exact "no safe direction
        # of failure" mistake build phase 3.0's guardrail premise gate
        # was built to catch, just at the field-tag layer instead of the
        # admission layer. Supplement with a small, explicitly-labeled
        # allowlist of tags known to work despite EInfo's silence on
        # them. This is deliberately NOT a general fix for every hidden
        # Entrez tag EInfo might omit for every db; it closes the one gap
        # this module's own code and docs actually depend on.
        names = names | (_EINFO_HIDDEN_VALID_FIELDS.get(db, frozenset()))
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
    except EInfoStatusError as exc:
        # Already actionable and already names the correct next action
        # (back off and retry, or fix the request). Do not re-wrap it in the
        # "could not validate" language below, which would bury it.
        return (
            f"{exc.actionable_message} field_tags could not be validated against "
            f"the EInfo field list for db {db!r}, so this request was never sent."
        )
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


# An ATOMIC Entrez term: one token carrying no whitespace, no parenthesis,
# no square bracket and no quote. Entrez only applies a field tag correctly
# to a term of this shape (see `_apply_field_tags`). Excluding `[` and `]`
# also closes the escape route where a term ends its own scoping construct
# and opens a new one, e.g. `BRCA1] OR cancer[titl`.
_ATOMIC_TERM_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[^\s()\[\]\"']+$")

# A field tag is an EInfo field NAME (`SYM`, `ORGN`, `TITL`), already
# validated against the live field list before this function runs. Re-checked
# here as defense in depth, so a tag can never carry a bracket that would
# break out of the `term[tag]` construct it is being placed into.
_FIELD_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{1,20}$")

_FIELD_TAG_SCOPING_ERROR: Final[str] = (
    "field_tags scoping is only supported for a single-token term, because "
    "Entrez applies a field tag to an atomic term and NOT to a parenthesized "
    "boolean group: `(BRCA1 AND cancer)[sym]` is parsed as `BRCA1[All Fields] "
    "AND sym[All Fields] AND cancer[All Fields]`, which silently unscopes the "
    "search instead of narrowing it. This request was never sent. Retry with "
    "field_tags omitted and the tags written inline in the term itself "
    "(e.g. `BRCA1[sym] AND cancer[titl]`), or with a single-token term."
)


def _apply_field_tags(term: str, field_tags: list[str]) -> tuple[str | None, str | None]:
    """Scope `term` to specific ESearch fields, or refuse. Returns (term, error).

    Exactly one element of the returned pair is ever non-None: a scoped term
    on success, an actionable error message on refusal. An empty field_tags
    list, the common case (see premise gate case 1, whose term already embeds
    its own `[sym]`/`[orgn]` tags directly), returns `term` untouched.

    F-3.1-29 / F-3.1-23, and why the previous two attempts were both wrong.

    The original code appended the tag bare: `_apply_field_tags("BRCA1 AND
    cancer", ["sym"])` produced `"BRCA1 AND cancer[sym]"`, scoping only the
    last token while `BRCA1` ran unscoped. F-3.1-23's fix wrapped the term in
    parentheses instead, `"(BRCA1 AND cancer)[sym]"`. That is not valid Entrez
    syntax and is strictly worse, because it unscopes the ONE token that had
    been scoped before. Live-verified against real ESearch on db=gene:

        term=BRCA1[sym] AND human[orgn]    -> count 1,     idlist ["672"]
            querytranslation: BRCA1[sym] AND "Homo sapiens"[Organism]
        term=(BRCA1)[sym] AND human[orgn]  -> count 190,   first id "1956"
            querytranslation: BRCA1[All Fields] AND sym[All Fields] AND ...

    Entrez does not apply a tag to a parenthesized group. It reads the group
    and the tag as two separate unscoped ANDed terms, and the literal word
    "sym" becomes a free-text search term of its own. The flagship symbol
    lookup then ranks a wrong gene (1956, EGFR) above the intended one (672,
    BRCA1). An unscoped wrong answer that still cites cleanly is exactly the
    failure class this repo treats as worse than a crash.

    The root fix, therefore, is that Entrez scopes a field tag correctly ONLY
    against an atomic term. Both correct forms are live-verified:

        _apply_field_tags("BRCA1", ["sym"])          -> "BRCA1[sym]"
            live count 660, querytranslation: BRCA1[sym]        (scoped)
        _apply_field_tags("BRCA1", ["sym", "gene"])  -> "(BRCA1[sym] OR BRCA1[gene])"
            live count 660, querytranslation: BRCA1[sym] OR BRCA1[gene]  (scoped)

    For a genuinely multi-token or boolean term there is no way to scope the
    whole expression to one field without tagging each atomic sub-term
    individually, which means parsing the caller's Boolean structure. Getting
    that subtly wrong reproduces the same silent-misscoping wrong answer, so
    this fails closed instead of guessing: `field_tags` is populated nowhere
    in production code today (only `NcbiEfetchSearchInput` declares it), so
    refusing costs no shipped behavior, while guessing costs correctness on
    the one query shape this tool exists to get right.
    """
    if not field_tags:
        return term, None
    if _ATOMIC_TERM_PATTERN.match(term) is None:
        return None, _FIELD_TAG_SCOPING_ERROR
    unsafe = [tag for tag in field_tags if _FIELD_TAG_PATTERN.match(tag) is None]
    if unsafe:
        return None, (
            f"field_tags {unsafe!r} are not well-formed EInfo field names "
            f"(letters, digits, underscore and hyphen only), so they cannot be "
            f"safely placed into a `term[tag]` construct. This request was never "
            f"sent. Retry with a real field name for this db, or omit field_tags."
        )
    if len(field_tags) == 1:
        return f"{term}[{field_tags[0]}]", None
    clauses = " OR ".join(f"{term}[{tag}]" for tag in field_tags)
    return f"({clauses})", None


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
    # UI fix set 11 (search breadth, 2026-09-14). A PMC uid from ESearch or
    # ELink is the bare number; the record page prefixes it with `PMC`.
    # Live-verified the same day: this exact shape answers HTTP 301 to
    # `https://pmc.ncbi.nlm.nih.gov/articles/PMC{id}/`, NCBI's current PMC
    # host. The `www.` form is kept rather than the `pmc.` host because
    # `NCBI_EFETCH_RECORD_URL_PATTERN` is Section 6.2 line 921 copied
    # verbatim and does not admit `pmc.`; widening a locked pattern is a
    # Step 6.2 item, a same-host redirect is not.
    "pmc": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{id}/",
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


def _cap_value(value: Any, depth: int = 0) -> Any:
    """Apply `_cap_text` recursively through nested dicts and lists.

    F-3.1-10 (reopened): the previous fix capped TOP-LEVEL string values
    only, so a hostile 50,000-character string nested one level down inside
    a dict or a list bypassed the cap entirely and flowed to the model
    uncapped. Every ESummary response this module passes through carries
    nested structure (clinvar's `variation_set` and `germline_classification`
    are objects, assembly's `busco` and `synonym` are objects, gds's
    `samples` is a list of objects), so nesting is the normal shape here,
    not an exotic one. `production-standards`'s bounded-context-items gate
    requires the cap to be enforced before injection, which means it has to
    follow the data wherever it actually lives.

    Three bounds, all fail-closed:
        - every string, at any depth, is capped by `_cap_text`
        - a nested dict keeps at most `_MAX_RECORD_FIELDS` keys, a nested
          list at most `_MAX_NESTED_ITEMS` items
        - recursion stops at `_MAX_NESTING_DEPTH` and collapses whatever
          remains to a capped string, so a deeply self-nested payload can
          neither exhaust the stack nor smuggle uncapped text past the cap
    """
    if isinstance(value, str):
        return _cap_text(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if depth >= _MAX_NESTING_DEPTH:
        return _cap_text(str(value))
    if isinstance(value, dict):
        return {
            str(key): _cap_value(item, depth + 1)
            for key, item in list(value.items())[:_MAX_RECORD_FIELDS]
        }
    if isinstance(value, (list, tuple)):
        return [_cap_value(item, depth + 1) for item in list(value)[:_MAX_NESTED_ITEMS]]
    return _cap_text(str(value))


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
    The status check runs BEFORE the body classifier, so a transient status
    code produces an actionable error message with the correct next action.
    """
    try:
        response = await ncbi_transport.execute_get(
            url, params, family="eutils", include_api_key=True
        )
    except ncbi_transport.TransportError as exc:
        return _error_output(action, str(exc))
    status_message = ncbi_transport.http_status_error_message("E-utilities", response)
    if status_message is not None:
        return _error_output(action, status_message)
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

    scoped_term, scoping_error = _apply_field_tags(params.term, params.field_tags)
    if scoping_error is not None:
        # F-3.1-29: fail closed rather than send a term whose field tag would
        # silently unscope the search. No request is issued.
        return _error_output("search", scoping_error)

    request_params: dict[str, Any] = {
        "db": params.db,
        "term": scoped_term,
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

    # F-3.1-25 (adversary finding 13, MINOR): cap the idlist to the same
    # _MAX_RECORDS_RETURNED bound records uses, so a 500-id search result
    # cannot bypass the NcbiEfetchRecord list's max_length=100 cap through
    # the single aggregate record's fields. `retmax` is caller-controlled and
    # accepts up to 500 (ncbi_efetch_schemas.py), so this is reachable with
    # ordinary input, not only a hostile server.
    capped_idlist = idlist[:_MAX_RECORDS_RETURNED]
    id_count = len(capped_idlist)
    # `idlist_count` states the ID-population size inside this record
    # explicitly, so the two units in this output can never be confused for
    # one another (see the record_count note below).
    fields: dict[str, Any] = {"idlist": capped_idlist, "idlist_count": id_count}
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

    truncated = total_available is not None and total_available > id_count

    # F-3.1-26 (adversary finding 14, MINOR): a non-zero count with an empty
    # idlist means the ESearch index disagrees with itself. This can happen
    # when the count is stale or a filter excluded every id after the count
    # was computed. Returning status ok with record_count 0 is consumed by
    # resolution as a confirmed non-resolution, permanently poisoning the
    # symbol cache. Fail closed to error instead.
    if not capped_idlist and total_available is not None and total_available > 0:
        return _error_output(
            "search",
            f"ESearch returned count {total_available} but an empty idlist. "
            f"The ESearch index may be inconsistent. Retry; if this recurs, "
            f"the search term or database may need narrowing.",
        )

    # F-3.1-25 (reopened): `record_count` now means the same thing in every
    # action of this module, "how many record objects are in `records`". It
    # previously reported `len(idlist)` here while `len(records)` was 1, so
    # the one action that returns an aggregate record was also the one action
    # measuring `record_count` in a different unit from the other three. A
    # consumer comparing `record_count` against `len(output.records)` across
    # actions read a phantom 24-record discrepancy on any multi-id search.
    #
    # The ID population is still reported, in its own units and never mixed
    # with the record units: `total_available` is ESearch's own total-hit
    # count, `truncated` compares it against the ids actually returned, and
    # `fields["idlist_count"]` states how many ids this record carries.
    records = [NcbiEfetchRecord(db=params.db, fields=_cap_fields(fields))]
    return NcbiEfetchOutput(
        status="ok",
        action="search",
        records=records,
        record_count=len(records),
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
    # F-4.7-A-02 (CRITICAL, build phase 4.7 adversary round): `status` and
    # `currentid` are ADDITIONS to Section 6.2's table, which names the seven
    # fields above and no more. Stated as a deliberate deviation rather than
    # left for a reader to notice, since every other row here is verbatim.
    #
    # Why the deviation is necessary: NCBI marks a discontinued gene record
    # with `status=1` and points at its replacement with `currentid`. Without
    # both fields, `core.graph._resolve_symbol_to_curie_uncached` cannot tell
    # a live record from a withdrawn one, so "Which diseases are associated
    # with BRCA3?" resolved NCBIGene:60500 (withdrawn, currentid 675) and the
    # system answered about BRCA2, cited and grounded, with no disclosure.
    # The two fields were sitting in the raw ESummary body the whole time and
    # this allowlist was stripping them before the resolver was handed the
    # record. The ticket's own premise said the fix was single-site for that
    # reason; measured, it was not.
    #
    # Why the deviation is SAFE, checked rather than assumed: `action=
    # "summary"` with `db="gene"` has exactly ONE production caller in this
    # repository, that resolver. `act_node`'s answer-bearing Layer 2 call
    # uses `dataset_report`, a different action, so widening this row cannot
    # put either field into a citation a user sees. Both are small scalars
    # and go through `_cap_value` like every other allowlisted field.
    "gene": (
        "name", "description", "chromosome", "maplocation", "genomicinfo", "mim", "organism",
        "status", "currentid",
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
    # ------------------------------------------------------------------
    # F-3.1-10 (reopened): the five databases below had NO allowlist at all
    # and fell through to `_generic_summary_fields`, which copied every
    # response key. A count cap of 40 keys is not a field filter: it bounds
    # how much untrusted external content reaches the model, not WHICH
    # content, and four of these five return fewer than 40 keys anyway, so
    # the cap never engaged and the passthrough was total.
    #
    # Section 6.2's table documents no field list for these (the module
    # docstring's "spec gap" note), so each set below was chosen from the
    # keys a LIVE ESummary call actually returns for that db, probed against
    # eutils.ncbi.nlm.nih.gov while writing this fix. They are selected for
    # being identifying or descriptive, and deliberately EXCLUDE the large
    # opaque blobs each db carries (assembly's `meta`, ~1.9 KB of packed
    # markup, and biosample's `sampledata`, ~2 KB of submitter-authored XML),
    # which are the highest-volume untrusted-content fields in the response
    # and carry the least citable value.
    #
    # Trust level: live-probed for KEY PRESENCE and shape in this ticket, on
    # one representative uid per db. Not semantically verified field by
    # field, and not promised stable by any locked spec. Treat as the same
    # trust tier as the `dbvar`/`omim`/`medgen`/`gtr` rows above.
    # ------------------------------------------------------------------
    "bioproject": (
        "project_acc", "project_title", "project_description", "project_type",
        "project_data_type", "project_target_scope", "organism_name",
        "sequencing_status", "registration_date", "submitter_organization",
        "taxid",
    ),
    "biosample": (
        "accession", "title", "organism", "taxonomy", "infraspecies",
        "sourcesample", "package", "organization", "publicationdate",
        "modificationdate",
    ),
    "assembly": (
        "assemblyaccession", "assemblyname", "assemblystatus", "assemblytype",
        "organism", "speciesname", "taxid", "biosampleaccn", "coverage",
        "refseq_category", "releaselevel", "submitterorganization",
        "submissiondate", "lastupdatedate",
    ),
    "gds": (
        "accession", "title", "summary", "taxon", "entrytype", "gdstype",
        "gpl", "gse", "pdat", "n_samples", "bioproject",
    ),
    # sra packs its payload into a handful of markup-bearing string fields
    # rather than flat scalars. They are the only substantive content the
    # response carries, so they are allowlisted and lean entirely on
    # `_cap_value` for their bound.
    "sra": ("expxml", "runs", "createdate", "updatedate"),
}


def _generic_summary_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Last-resort passthrough for a payload with no allowlist at all.

    After the F-3.1-10 reopen, every one of `SummaryDb`'s 12 databases has
    an entry in `_SUMMARY_FIELDS_BY_DB`, so the `summary` action never
    reaches this function. Its one remaining caller is
    `_extract_generic_fetch_records`, the unverified EFetch fallback, where
    the response shape is by definition unknown and there is nothing to
    allowlist against.

    Values are capped with `_cap_value`, which recurses through nested dicts
    and lists. The previous fix used `_cap_text` on top-level strings only,
    so a hostile 50,000-character value nested one level down bypassed the
    cap completely.
    """
    result: dict[str, Any] = {}
    for key, value in entry.items():
        if key == "uid":
            continue
        result[str(key)] = _cap_value(value)
    return result


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
        if "error" in entry:
            # F-3.1-13 (adversary finding 1, CRITICAL): ESummary signals a
            # per-uid error as a dict carrying only "uid" and "error" keys,
            # e.g. {"uid":"999999999","error":"cannot get document summary"}.
            # The classifier sees envelope "result" and no top-level ERROR,
            # so it returns ok. The extractor must NOT build a record for
            # this entry: a record with a real host-pinned source_url but
            # empty fields is a fabricated citation indistinguishable from a
            # genuine one. Only skip when the entry genuinely carries no
            # allowlisted fields at all (a mixed batch of one real uid and
            # one nonexistent one must keep the real record and drop the
            # error entry).
            if known_fields is not None:
                has_content = any(name in entry for name in known_fields)
            else:
                has_content = any(key not in ("uid", "error") for key in entry)
            if not has_content:
                continue
        if known_fields is not None:
            # F-3.1-10 (reopened): the allowlisted path needs the per-value
            # cap too, not just the generic fallback. Several allowlisted
            # fields are nested objects built from untrusted external content
            # (clinvar's `variation_set` and `germline_classification`,
            # assembly's `busco` and `synonym`, gds's `samples`), so an
            # allowlisted KEY is not the same as a bounded VALUE.
            extracted = {
                name: _cap_value(entry[name]) for name in known_fields if name in entry
            }
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
        # The leading "./" is load-bearing and must not be "simplified" away.
        # `harness/tiers.py`'s repo-wide guard scans every string constant for
        # a provider/model slug, and a bare two-segment XPath like
        # "MedlineCitation/PMID" matches that shape exactly. Three-segment
        # paths below do not, which is why only this one carries the prefix.
        # "./X/Y" is exactly equivalent to "X/Y" for ElementTree.find, so this
        # keeps the guard intact rather than adding an exclusion to it.
        pmid_el = article_el.find("./MedlineCitation/PMID")
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


def _is_unextractable_summary_body(body: Any, rettype: str, retmode: str) -> bool:
    """True when an EFetch body is ESummary-shaped and cannot be split per record.

    F-3.1-20 (reopened): the original guard was scoped to `params.db ==
    "pubmed"`, but `FetchDb` names eight databases and every one of them
    reproduces the identical defect on the SCHEMA DEFAULTS
    (`rettype="docsum"`, `retmode="json"`). Live-verified against real EFetch
    while writing this fix: `db=pubmed&id=21376230`, `db=gene&id=672` and
    `db=clinvar&id=12345` all return the same envelope,
    `{"header": ..., "result": {"uids": [...], "<uid>": {...}}}`. On the
    seven non-pubmed databases that body fell through to
    `_extract_generic_fetch_records`, producing ONE record holding the entire
    multi-record payload with `id=None`, `source_url=None`, and
    `record_count` misreported as 1, all at `status="ok"`. An uncited blob
    presented as a successful answer is precisely what the cite-or-refuse
    gate exists to stop.

    Two independent arms, so neither has to be exactly right on its own:

    1. Shape: a dict body whose `result` is a dict carrying `uids`. This is
       the ESummary envelope itself, and it catches the case regardless of
       which db, rettype or retmode produced it, including a server that
       answers with a summary body for parameters that did not ask for one.
    2. Parameters: the `rettype="docsum"`, `retmode="json"` default pair with
       any dict body. This catches a docsum JSON response whose envelope
       drifts from the shape above, so an upstream rename of `uids` degrades
       to a refusal rather than back to a fabricated blob.
    """
    if not isinstance(body, dict):
        return False
    if rettype == "docsum" and retmode == "json":
        return True
    result = body.get("result")
    return isinstance(result, dict) and "uids" in result


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
    elif _is_unextractable_summary_body(result.body, params.rettype, params.retmode):
        return _error_output(
            "fetch",
            f"fetch db={params.db} rettype={params.rettype} retmode={params.retmode} "
            f"returned an ESummary-shaped multi-record JSON body, which this tool "
            f"cannot split into per-record citations: the generic extractor would "
            f"collapse every record into one aggregate blob with no id and no "
            f"source_url. Retry with the summary action for ESummary fields, or, "
            f"for db=pubmed only, with rettype=abstract retmode=xml (the one "
            f"live-verified per-id EFetch path).",
        )
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


# The (dbfrom, db) pairs for which ONLY the direct `<dbfrom>_<db>` linkset
# contributes, because the other same-dbto linknames were live-verified to
# be computed sets rather than cross-references (review F-03, 2026-09-14).
# (pubmed, pmc): `pubmed_pmc` is the article's own PMC copy;
# `pubmed_pmc_refs` is the set of PMC articles citing it. Add a pair here
# only after reading its live linknames; a pair absent from this table keeps
# every matching linkset, and that is the safe default.
_DIRECT_LINKNAME_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset({("pubmed", "pmc")})


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
    matching: list[dict[str, Any]] = []
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
                matching.append(linksetdb)

    # UI fix set 11 (search breadth, 2026-09-14): trap 3's second half. ELink
    # can answer the SAME target db under two linknames, and only one of them
    # is the cross-reference the caller asked for. Live-verified the same
    # day: `dbfrom=pubmed&db=pmc` returns `pubmed_pmc` (the article's own
    # PMC copy, one id) beside `pubmed_pmc_refs` (every PMC article that
    # CITES it, hundreds of ids), both with `dbto: "pmc"`. Merging them
    # would ship a citing paper as if it were the article's full text.
    #
    # Review F-03 (2026-09-14): the first version preferred `<dbfrom>_<db>`
    # for EVERY pair, and that dropped ids for pairs where the other
    # linknames are real cross-references, not computed sets: live, gene
    # 2645 to pubmed went from 477 ids to 357, losing all 120 from
    # `gene_pubmed_citedinomim`. So the preference applies only to the
    # pairs in `_DIRECT_LINKNAME_PAIRS`, each added after a live check of
    # what the other linknames for that pair actually are. Every other
    # pair keeps the original behaviour: every matching-dbto linksetdb
    # contributes.
    pair = (params.dbfrom, params.db)
    contributing = matching
    if pair in _DIRECT_LINKNAME_PAIRS:
        direct_linkname = f"{params.dbfrom}_{params.db}"
        direct = [
            linksetdb for linksetdb in matching if linksetdb.get("linkname") == direct_linkname
        ]
        contributing = direct

    linked_ids: list[str] = []
    for linksetdb in contributing:
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
