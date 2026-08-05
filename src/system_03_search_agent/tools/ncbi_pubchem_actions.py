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

## source_url: PubChem's own record host does not satisfy the schema pattern

`NCBI_EFETCH_RECORD_URL_PATTERN` (`ncbi_efetch_schemas.py`) is:

    ^https://((www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov|(www\\.)?omim\\.org)/

PubChem's real record page lives at `pubchem.ncbi.nlm.nih.gov/compound/{cid}`.
That hostname does not match the pattern: the pattern's only accepted
subdomains ahead of `ncbi.nlm.nih.gov` are an empty string, `www.`, or
`pubmed.`, and `pubchem.` is none of those. This is a genuine conflict, not
an oversight to route around quietly. Per this ticket's explicit
instruction, the fix is NOT to loosen the shared pattern (a citation-URL
regex getting wider to accommodate one tool's convenience is exactly the
kind of change that widens what a fabricated citation can point at, the
same risk class `production-standards.md`'s host-pinned regex requirement
exists to close) and NOT to emit a URL that would fail the schema's own
validator. Every `pubchem_property` record in this module is emitted with
`source_url=None`. The record is still fully cited by its `id` (the CID)
and `fields` (`CID`, `MolecularFormula`, etc.), just without a clickable
link, until this conflict is resolved at the spec or schema level.

FINDING for the product owner / Step 6.2 reconciliation: either Section 6.2's
citation pattern needs a PubChem-specific carve-out distinct from the shared
NCBI record pattern (`pubchem.ncbi.nlm.nih.gov` is a real, resolvable,
`ncbi.nlm.nih.gov`-suffixed host, live-verified reachable 2026-08-05), or
`pubchem_property` citations are accepted as permanently URL-less. Not
resolved silently here.

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
import urllib.parse
from typing import Any, Final

import httpx

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchOutput,
    NcbiEfetchPubchemPropertyInput,
    NcbiEfetchRecord,
)

_PUBCHEM_BASE: Final[str] = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"

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
    return NcbiEfetchOutput(
        status="error",
        action="pubchem_property",
        records=[],
        record_count=0,
        truncated=False,
        error=message,
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

    `source_url` is deliberately always `None` here. See the module
    docstring's "source_url" section: PubChem's record host does not
    satisfy `NCBI_EFETCH_RECORD_URL_PATTERN`, and this module never emits a
    URL that would fail the schema's own validator.
    """
    cid_value = entry.get("CID")
    return NcbiEfetchRecord(
        id=str(cid_value) if cid_value is not None else None,
        db="pubchem",
        fields=dict(entry),
        source_url=None,
    )


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

    records = [_record_from_property_entry(entry) for entry in entries]
    return NcbiEfetchOutput(
        status="ok",
        action="pubchem_property",
        records=records[:100],
        record_count=min(len(records), 100),
        truncated=len(records) > 100,
        total_available=len(records) if len(records) > 100 else None,
    )


def _cids_from_body(body: Any) -> list[str] | None:
    """Extract `IdentifierList.CID`, or `None` for an unrecognized shape.

    Same `None`-means-unrecognized allowlist discipline as
    `_properties_from_body` above.
    """
    if not isinstance(body, dict):
        return None
    identifier_list = body.get("IdentifierList")
    if not isinstance(identifier_list, dict):
        return None
    cids = identifier_list.get("CID")
    if not isinstance(cids, list):
        return None
    return [str(cid) for cid in cids if isinstance(cid, (int, str))]


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

    cids = _cids_from_body(resolve_result.body)
    if cids is None:
        return _error_output(
            "PubChem name resolution returned a 2xx response with an "
            "unrecognized body shape, refusing to guess its meaning"
        )
    if not cids:
        return _empty_output()

    bounded_cids = cids[:_MAX_NAME_RESOLVED_CIDS]
    properties = list(action_input.properties) or list(_DEFAULT_PROPERTIES)
    fetch_results = await asyncio.gather(
        *(
            _fetch_properties_for_cid(cid, properties, client=client)
            for cid in bounded_cids
        )
    )

    records: list[NcbiEfetchRecord] = []
    for cid, result in zip(bounded_cids, fetch_results):
        if result.status == "error":
            # One resolved CID failing its property fetch does not sink the
            # whole request; the surviving records are still real, cited
            # data. Per production-standards.md's partial-failure gate,
            # this degrades gracefully rather than discarding everything.
            continue
        entries = _properties_from_body(result.body)
        if not entries:
            continue
        records.extend(_record_from_property_entry(entry) for entry in entries)

    if not records:
        return _empty_output()

    return NcbiEfetchOutput(
        status="ok",
        action="pubchem_property",
        records=records[:100],
        record_count=min(len(records), 100),
        truncated=len(records) > 100,
        total_available=len(records) if len(records) > 100 else None,
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
    """
    if action_input.lookup_type == "cid":
        return await _pubchem_property_by_cid(action_input, client=client)
    return await _pubchem_property_by_name(action_input, client=client)
