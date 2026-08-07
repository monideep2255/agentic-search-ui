"""The `pubchem_property` action of `ncbi_efetch`: PubChem PUG REST (T-3.1-09).

Technical_specification.md Section 6.2, the `pubchem_property` branch. Two
endpoints under `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/`:

    GET compound/cid/{cid}/property/{list}/JSON
    GET compound/name/{name}/cids/JSON

`lookup_type` selects which one starts the request: `"cid"` calls the
property endpoint directly; `"name"` calls the CID-resolution endpoint
first, then fans out to the property endpoint for each resolved CID.

## The defining constraint: status-coded, not body-coded

PubChem returns proper HTTP status codes, the opposite convention from
E-utilities, the same as `ncbi_datasets_actions.dataset_report`. This
module classifies exclusively with
`ncbi_transport.classify_status_coded_response`, never
`classify_eutils_response`. See that module's file docstring for why the
two classifiers have deliberately incompatible signatures, and
`docs/ncbi/Tool_implementation_mechanics.md:117-122` for why a shared code
path across both conventions gets one family right and the other silently
wrong.

## Live-verified ground truth, 2026-08-05

    GET compound/cid/2244/property/MolecularFormula,MolecularWeight/JSON
        -> 200, {"PropertyTable": {"Properties": [{"CID": 2244,
           "MolecularFormula": "C9H8O4", "MolecularWeight": "180.16"}]}}

    GET compound/cid/999999999999/property/MolecularFormula/JSON
        -> 400, {"Fault": {"Code": "PUGREST.BadRequest",
           "Message": "Invalid ID, must be positive integer"}}

    GET compound/name/aspirin/cids/JSON
        -> 200, {"IdentifierList": {"CID": [2244]}}

    GET compound/name/notarealchemicalnamexyzzy/cids/JSON
        -> 404, {"Fault": {"Code": "PUGREST.NotFound", "Message":
           "No CID found", "Details": ["No CID found that matches the
           given name"]}}

Both fault shapes classify as `"error"` under `classify_status_coded_response`
(400 and 404 are both outside the 2xx range), and both are the same
`{"Fault": {"Code", "Message"}}` envelope `ncbi_transport`'s error-message
extractor already knows how to read.

## Design decision: name lookup chains two independently-verified calls

Section 6.2's endpoint table lists both PubChem endpoints under the single
`pubchem_property` action but does not specify how a name resolves to a
property set. The composition implemented here, resolve name to CID(s) via
`compound/name/{name}/cids/JSON`, then fetch properties for each resolved
CID via the same `compound/cid/{cid}/property/{list}/JSON` call the `"cid"`
path already uses, is a builder decision, not a documented endpoint. Each
half of the chain is independently live-verified above; the COMPOSITION of
the two has not been separately exercised against a name that resolves to
more than one CID. Fan-out is capped at `_MAX_NAME_RESOLVED_CIDS` (5) and
run concurrently (`asyncio.gather`), per production-standards.md's "async
when fanning out to 2 or more concurrent Layer 2 or Layer 3 API calls".
Flagged here rather than silently shipped, per ai-security-standards.md's
"verify that every API call a generated snippet makes actually exists": the
calls exist and are verified individually; the multi-CID fan-out path is
the part a human should confirm before this ships past this ticket.

## source_url: a real, encoded, host-pinned PubChem record URL

`NCBI_EFETCH_RECORD_URL_PATTERN` (`ncbi_efetch_schemas.py`) is:

    ^https://((www\\.|pubmed\\.|pubchem\\.)?ncbi\\.nlm\\.nih\\.gov|(www\\.)?omim\\.org)/

PubChem's real record page lives at `pubchem.ncbi.nlm.nih.gov/compound/{cid}`,
and the shared pattern now names `pubchem.` alongside `www.` and `pubmed.`
as an accepted subdomain (finding F-3.1-08). So every `pubchem_property`
record carries a genuine, clickable `source_url`, not `None`. Three
properties hold on every URL this module emits:

- Encoded: the `CID` comes from the PubChem response body, which is
  untrusted external content. It is passed through `_quote_path_segment`
  before interpolation, exactly like the caller-supplied `value` and
  `properties` segments, so whitespace, a newline, a `/`, or literal markup
  inside a hostile or malformed `CID` cannot reach the citation URL raw
  (findings F-3.1-08-residual and F-3.1-36).
- Host-pinned: the schema's `pattern` constraint is the second gate. A URL
  this module built that somehow fell outside the allowed hosts is rejected
  by `NcbiEfetchRecord`, never silently shipped.
- Fail-closed: a record that fails that validation raises
  `pydantic.ValidationError`, which is caught at the record-assembly
  boundary and converted into this tool's `status: "error"` output, never
  allowed to escape the tool's public boundary as an exception
  (finding F-3.1-34).

Depends on:
    - system_03_search_agent.tools.ncbi_transport (execute_get,
      classify_status_coded_response)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchPubchemPropertyInput, NcbiEfetchOutput, NcbiEfetchRecord)
    - httpx (pinned in pyproject.toml, >=0.27), for the optional test-only
      `client` injection point

Reads:
    - Nothing at import time. PubChem needs no API key (Section 6.2,
      "Rate limits": "Datasets v2 and PubChem require no key").

Writes:
    - Nothing. Outbound HTTPS requests only.

Depended by:
    - system_03_search_agent.tools.ncbi_efetch (the dispatcher, not yet
      written; T-3.1-06/07 or later)
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from typing import Any, Final

import httpx
import pydantic

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NCBI_EFETCH_RECORD_URL_PATTERN,
    NcbiEfetchOutput,
    NcbiEfetchPubchemPropertyInput,
    NcbiEfetchRecord,
)

_PUBCHEM_BASE: Final[str] = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"

# The human-facing record page, the citation target. Distinct from the REST
# base above: that one is the fetch host, this one is what a reader clicks.
_PUBCHEM_RECORD_URL_PREFIX: Final[str] = "https://pubchem.ncbi.nlm.nih.gov/compound/"

# Fail at import time, not at first citation, if the prefix above ever drifts
# off the schema's allowed citation hosts. Same guard, same reason, as
# `ncbi_eutils_actions`'s loop over `_RECORD_URL_TEMPLATES`.
assert re.match(NCBI_EFETCH_RECORD_URL_PATTERN, _PUBCHEM_RECORD_URL_PREFIX + "2244") is not None, (
    "_PUBCHEM_RECORD_URL_PREFIX produces a URL that "
    "NCBI_EFETCH_RECORD_URL_PATTERN would reject"
)

# Section 6.2 line 944's extracted field list. Requested when the caller
# supplies no explicit `properties`, matching what the spec names as the
# default extraction set for this action.
_DEFAULT_PROPERTIES: Final[tuple[str, ...]] = (
    "MolecularFormula",
    "MolecularWeight",
    "ConnectivitySMILES",
    "IUPACName",
)

# A name lookup can resolve to several CIDs (stereoisomer salts, mixtures).
# Capped and fanned out concurrently rather than fetched one at a time or
# left unbounded. See the module docstring's "Design decision" section.
_MAX_NAME_RESOLVED_CIDS: Final[int] = 5

# Per-value character cap on free text copied out of a PubChem response
# body. `NcbiEfetchRecord.fields` caps the property COUNT (maxProperties 40)
# and nothing else, so the cap on any single value's LENGTH lives here, the
# same split, and the same 4000-character bound, `ncbi_eutils_actions._cap_text`
# already uses. Part of the multi-agent pipeline gate's "bounded context
# items" requirement (finding F-3.1-12): an `IUPACName` on a hostile or
# malformed record must not be able to crowd out a prompt on its own.
_MAX_FIELD_VALUE_CHARS: Final[int] = 4000

# Depth bound on the recursive value cap below. PubChem property entries are
# flat in every live-verified shape; the recursion exists only so a nested
# value in an undocumented shape is still capped, and the bound stops a
# deeply nested hostile body from recursing without limit.
_MAX_FIELD_VALUE_DEPTH: Final[int] = 6

# A resolution body where MOST entries are non-scalar is a malformed
# response, not a well-formed list with a few odd members, so it fails
# closed to `error` rather than silently resolving to fewer CIDs
# (finding F-3.1-34). Below this ratio the dropped entries are disclosed
# through `total_available`/`truncated` instead of discarded silently.
_MAX_NON_SCALAR_CID_RATIO: Final[float] = 0.5


def _cap_text(value: str) -> str:
    """Hard character cap on one untrusted free-text value.

    Mirrors `ncbi_eutils_actions._cap_text`. Duplicated locally rather than
    imported so neither Layer 2 module reaches across into the other's
    extraction path; the two caps are deliberately the same number.
    """
    if len(value) <= _MAX_FIELD_VALUE_CHARS:
        return value
    return value[:_MAX_FIELD_VALUE_CHARS] + " [truncated]"


def _cap_field_value(value: Any, depth: int = 0) -> Any:
    """Apply `_cap_text` to every string inside one extracted field value.

    A PubChem property value is usually a scalar, but the endpoint is free to
    return a list or an object for an undocumented property, so lists and
    dicts are walked to the depth bound rather than passed through uncapped.
    """
    if isinstance(value, str):
        return _cap_text(value)
    if depth >= _MAX_FIELD_VALUE_DEPTH:
        return value
    if isinstance(value, list):
        return [_cap_field_value(item, depth + 1) for item in value]
    if isinstance(value, dict):
        return {key: _cap_field_value(item, depth + 1) for key, item in value.items()}
    return value


def _quote_path_segment(value: str) -> str:
    """URL-encode one path segment. See the sibling function's docstring in
    `ncbi_datasets_actions.py`: `value` is caller-supplied (`value` for a
    `cid` lookup, `value` for a `name` lookup) and lands in the URL PATH,
    not a query string, so every reserved character is encoded, not just
    the query-string-safe subset `ncbi_transport._build_query_string` uses.
    """
    return urllib.parse.quote(value, safe="")


def _build_property_list_segment(properties: list[str]) -> str:
    """Encode each property name individually, then join with a literal comma.

    PubChem expects one path segment shaped `Prop1,Prop2,Prop3`. Encoding
    the whole joined string at once would also encode the separating comma
    and break the endpoint's expected path shape; encoding each caller-
    supplied token first and joining with an un-encoded comma keeps the
    comma as a genuine path separator while still closing the injection
    surface on each individual token.
    """
    return ",".join(_quote_path_segment(p) for p in properties)


def _error_output(message: str) -> NcbiEfetchOutput:
    # `NcbiEfetchOutput.error` caps at 500 characters. An upstream fault
    # message, or a pydantic validation summary, can exceed that, and an
    # over-long error string must never itself raise out of the error path.
    return NcbiEfetchOutput(
        status="error",
        action="pubchem_property",
        records=[],
        record_count=0,
        truncated=False,
        error=message[:500],
    )


def _empty_output() -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="empty",
        action="pubchem_property",
        records=[],
        record_count=0,
        truncated=False,
    )


def _record_from_property_entry(entry: dict[str, Any]) -> NcbiEfetchRecord:
    """Build one record from one `PropertyTable.Properties[]` entry.

    F-3.1-08 (judge finding 8, MAJOR): `source_url` resolves to
    pubchem.ncbi.nlm.nih.gov, since the record URL pattern names the
    `pubchem.` subdomain.

    F-3.1-08-residual and F-3.1-36 (re-review, CRITICAL): the `CID` is read
    out of the PubChem response body, which is untrusted external content,
    so it goes through `_quote_path_segment` before it lands in the URL path
    exactly like every caller-supplied segment in this module. A raw
    f-string interpolation here would let whitespace, a newline, a path
    separator, or literal markup inside a malformed `CID` reach a citation
    URL verbatim.

    May raise `pydantic.ValidationError` (an over-long `id`, an over-long or
    off-host `source_url`, more than 40 properties). Callers convert that
    into this tool's `error` output; see `_records_from_property_entries`.
    """
    cid_value = entry.get("CID")
    source_url: str | None = None
    if cid_value is not None:
        source_url = _PUBCHEM_RECORD_URL_PREFIX + _quote_path_segment(str(cid_value))
    return NcbiEfetchRecord(
        id=str(cid_value) if cid_value is not None else None,
        db="pubchem",
        fields={key: _cap_field_value(value) for key, value in entry.items()},
        source_url=source_url,
    )


def _records_from_property_entries(
    entries: list[dict[str, Any]],
) -> tuple[list[NcbiEfetchRecord], str | None]:
    """Build every record for one property-table body, failing closed.

    Returns `(records, None)` on success, or `([], message)` when any entry
    fails `NcbiEfetchRecord`'s own validation.

    F-3.1-34 (re-review, MINOR): before this, a response carrying more than
    `NcbiEfetchRecord.fields`' 40-property bound, an over-long `id`, or a
    `source_url` the schema's host pattern rejects raised
    `pydantic.ValidationError` straight out of `pubchem_property`, the
    tool's public boundary, unlike every sibling module, which catches it
    and returns a structured error. The whole request fails closed rather
    than shipping a partial record set, because a response that violates the
    output contract is an anomalous response, not a partially-good one.
    """
    records: list[NcbiEfetchRecord] = []
    for entry in entries:
        try:
            records.append(_record_from_property_entry(entry))
        except pydantic.ValidationError as exc:
            return [], (
                "PubChem returned a property entry that fails this tool's own "
                f"output schema ({exc.error_count()} validation error(s); first: "
                f"{exc.errors()[0].get('msg', 'unknown')!r}). Refusing to emit a "
                "partial or unvalidated record; retry with a narrower "
                "`properties` list."
            )
    return records, None


async def _fetch_properties_for_cid(
    cid: str,
    properties: list[str],
    *,
    client: httpx.AsyncClient | None,
) -> ncbi_transport.ClassificationResult:
    """One property fetch for one CID. Shared by the `cid` and `name` paths."""
    url = (
        _PUBCHEM_BASE
        + "cid/"
        + _quote_path_segment(cid)
        + "/property/"
        + _build_property_list_segment(properties)
        + "/JSON"
    )
    response = await ncbi_transport.execute_get(url, {}, family="pubchem", client=client)
    return ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text
    )


def _properties_from_body(body: Any) -> list[dict[str, Any]] | None:
    """Extract `PropertyTable.Properties`, or `None` for an unrecognized shape.

    `None` (as opposed to an empty list) signals "this 2xx body did not
    match the one known-good PubChem property-table envelope", which the
    caller fails closed to `"error"` on, the same allowlist discipline
    `ncbi_transport`'s E-utilities classifier already applies to its own
    envelopes.
    """
    if not isinstance(body, dict):
        return None
    table = body.get("PropertyTable")
    if not isinstance(table, dict):
        return None
    properties = table.get("Properties")
    if not isinstance(properties, list):
        return None
    return [p for p in properties if isinstance(p, dict)]


async def _pubchem_property_by_cid(
    action_input: NcbiEfetchPubchemPropertyInput,
    *,
    client: httpx.AsyncClient | None,
) -> NcbiEfetchOutput:
    properties = list(action_input.properties) or list(_DEFAULT_PROPERTIES)
    result = await _fetch_properties_for_cid(action_input.value, properties, client=client)

    if result.status == "error":
        return _error_output(
            result.error_message or "PubChem request failed with no structured error body"
        )

    entries = _properties_from_body(result.body)
    if entries is None:
        return _error_output(
            "PubChem returned a 2xx response with an unrecognized body shape, "
            "refusing to guess its meaning"
        )
    if not entries:
        return _empty_output()

    records, validation_error = _records_from_property_entries(entries)
    if validation_error is not None:
        return _error_output(validation_error)
    return NcbiEfetchOutput(
        status="ok",
        action="pubchem_property",
        records=records[:100],
        record_count=min(len(records), 100),
        truncated=len(records) > 100,
        total_available=len(records) if len(records) > 100 else None,
    )


def _cids_from_body(body: Any) -> tuple[list[str], int] | None:
    """Extract `IdentifierList.CID`, or `None` for an unrecognized shape.

    Returns `(usable_cids, raw_entry_count)`. Same `None`-means-unrecognized
    allowlist discipline as `_properties_from_body` above.

    F-3.1-34 (re-review, MINOR): the raw entry count is returned alongside
    the usable CIDs because a non-scalar entry (a dict, a null, a nested
    list) used to be dropped with no signal at all, so a partially malformed
    2xx body simply reported fewer CIDs than it carried, the same fail-open
    shape F-3.1-07 closed on the Datasets side. The count feeds this tool's
    `total_available`/`truncated` disclosure, so a dropped entry is
    reported rather than swallowed.
    """
    if not isinstance(body, dict):
        return None
    identifier_list = body.get("IdentifierList")
    if not isinstance(identifier_list, dict):
        return None
    cids = identifier_list.get("CID")
    if not isinstance(cids, list):
        return None
    usable = [
        str(cid) for cid in cids if isinstance(cid, (int, str)) and not isinstance(cid, bool)
    ]
    return usable, len(cids)


async def _pubchem_property_by_name(
    action_input: NcbiEfetchPubchemPropertyInput,
    *,
    client: httpx.AsyncClient | None,
) -> NcbiEfetchOutput:
    resolve_url = _PUBCHEM_BASE + "name/" + _quote_path_segment(action_input.value) + "/cids/JSON"
    response = await ncbi_transport.execute_get(resolve_url, {}, family="pubchem", client=client)
    resolve_result = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text
    )

    if resolve_result.status == "error":
        return _error_output(
            resolve_result.error_message
            or "PubChem name resolution failed with no structured error body"
        )

    extraction = _cids_from_body(resolve_result.body)
    if extraction is None:
        return _error_output(
            "PubChem name resolution returned a 2xx response with an "
            "unrecognized body shape, refusing to guess its meaning"
        )
    cids, resolved_total = extraction

    # F-3.1-34 (re-review, MINOR): a body where most `CID` entries are not
    # scalars is malformed, not merely odd. Fail closed rather than proceed
    # on the minority that happen to parse.
    dropped_non_scalar = resolved_total - len(cids)
    if resolved_total and dropped_non_scalar > resolved_total * _MAX_NON_SCALAR_CID_RATIO:
        return _error_output(
            f"PubChem name resolution returned {resolved_total} CID entries of "
            f"which {dropped_non_scalar} are not integers or strings. A majority "
            "of unusable entries means a malformed response, not a few odd "
            "members; refusing to answer from the remainder. Retry, and if this "
            "recurs, this module's resolution parsing needs updating."
        )
    if not cids:
        return _empty_output()

    bounded_cids = cids[:_MAX_NAME_RESOLVED_CIDS]
    properties = list(action_input.properties) or list(_DEFAULT_PROPERTIES)
    fetch_results = await asyncio.gather(
        *(_fetch_properties_for_cid(cid, properties, client=client) for cid in bounded_cids)
    )

    records: list[NcbiEfetchRecord] = []
    any_fetch_succeeded = False
    for result in fetch_results:
        if result.status == "error":
            # One resolved CID failing its property fetch does not sink the
            # whole request; the surviving records are still real, cited
            # data. Per production-standards.md's partial-failure gate,
            # this degrades gracefully rather than discarding everything.
            continue
        entries = _properties_from_body(result.body)
        if entries is None:
            # F-3.1-21 (re-review, MAJOR): an unrecognized 2xx body is the
            # SAME shape on both paths and must fail closed the same way.
            # Before this fix the cid path returned `error` here while the
            # name path treated it as an ordinary empty result, so the one
            # response shape that means "this API no longer looks like what
            # we verified" was reported as "nothing matched" on one path
            # only.
            return _error_output(
                "PubChem returned a 2xx property response with an unrecognized "
                "body shape during name resolution, refusing to guess its "
                "meaning"
            )
        any_fetch_succeeded = True
        if not entries:
            continue
        entry_records, validation_error = _records_from_property_entries(entries)
        if validation_error is not None:
            return _error_output(validation_error)
        records.extend(entry_records)

    if not records:
        # F-3.1-21 (adversary finding 9, MAJOR): distinguish "every
        # property fetch failed" (error) from "CID resolved but no
        # properties matched" (empty). Before this fix, both cases
        # returned empty, so a total failure was indistinguishable from
        # a clean no-result answer.
        if not any_fetch_succeeded:
            return _error_output(
                "PubChem name resolved to one or more CIDs but every "
                "property fetch returned an error. The properties may be "
                "invalid for these CIDs, or the PubChem service may be "
                "degraded. Retry with different properties."
            )
        return _empty_output()

    # F-3.1-21 (re-review, MAJOR): truncation disclosure must cover the
    # name-resolution cap, not only the 100-record output bound. Before this
    # fix, 40 resolved CIDs fetched down to `_MAX_NAME_RESOLVED_CIDS` (5)
    # reported `truncated=False, total_available=None`, so the caller had no
    # way to learn that 35 CIDs were dropped. `resolved_total` counts every
    # entry the resolution body carried, including entries dropped as
    # non-scalar above, so both kinds of loss are disclosed through one
    # number.
    cids_truncated = resolved_total > len(bounded_cids)
    records_truncated = len(records) > 100
    if cids_truncated:
        total_available: int | None = resolved_total
    elif records_truncated:
        total_available = len(records)
    else:
        total_available = None
    return NcbiEfetchOutput(
        status="ok",
        action="pubchem_property",
        records=records[:100],
        record_count=min(len(records), 100),
        truncated=cids_truncated or records_truncated,
        total_available=total_available,
    )


async def pubchem_property(
    action_input: NcbiEfetchPubchemPropertyInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> NcbiEfetchOutput:
    """Execute the `pubchem_property` action: PubChem PUG REST.

    `lookup_type == "cid"` fetches properties for that CID directly.
    `lookup_type == "name"` resolves the name to up to
    `_MAX_NAME_RESOLVED_CIDS` CIDs first, then fetches properties for each,
    concurrently. Both paths classify with
    `classify_status_coded_response`, branching on HTTP status, never body
    content: a 400 or 404 is always `"error"`, and only a body shape this
    module explicitly recognizes (`PropertyTable.Properties` or
    `IdentifierList.CID`) is trusted for a 2xx response.

    Never raises for a bad response. Every failure, including a response
    that violates this tool's own output schema, comes back as
    `status: "error"` with an actionable message. When the name path's
    fan-out cap drops resolved CIDs, `truncated` is `True` and
    `total_available` carries the number the resolution actually returned.
    """
    if action_input.lookup_type == "cid":
        return await _pubchem_property_by_cid(action_input, client=client)
    return await _pubchem_property_by_name(action_input, client=client)
