"""Unit tests for `ncbi_pubchem_actions.pubchem_property` (T-3.1-09).

No live network anywhere in this file. Every case mocks at the HTTP client
boundary with the same `_FakeClient` shape `test_ncbi_transport.py` and
`test_ncbi_datasets_actions.py` already established. Live-network coverage
of the real PubChem endpoint is `test_ncbi_efetch_premise.py`'s job (cases 6
and 11), not this file's.

The canned response bodies below are the exact shapes recorded in
`ncbi_pubchem_actions.py`'s own module docstring, live-probed 2026-08-05
against `pubchem.ncbi.nlm.nih.gov/rest/pug/`.

What this file proves, mapped to the ticket's acceptance:

    - Happy path per endpoint: `cid` lookup (direct property fetch) and
      `name` lookup (resolve to CID, then fetch properties).
    - A 400 (bad CID) and a 404 (name not found) both classify as `error`
      by HTTP STATUS, using each response's own `{"Fault": {...}}` message.
    - An error-shaped `Fault` body under a 200 still classifies `ok` when
      real property data is also present: status decides, body content
      that merely resembles an error is not enough on its own. The mirror
      image of the E-utilities family.
    - Incoherent input is not reachable here (both `lookup_type` values are
      schema-required and mutually exclusive by construction), so this
      file instead covers the schema-adjacent case: an unrecognized 2xx
      body shape fails closed to `error` rather than a fabricated `ok`.
    - A hostile `value` (for both `cid` and `name` lookups) and a hostile
      `properties` entry are URL-encoded before reaching the request path.
    - `source_url` is a real PubChem record URL, not `None`:
      `NCBI_EFETCH_RECORD_URL_PATTERN` names the `pubchem.` subdomain, and
      the CID is URL-encoded on its way into the path, so a hostile or
      malformed CID from the response body cannot put whitespace, a
      newline, a path separator, or literal markup into a citation URL.
    - A response that violates this tool's own output schema (an over-long
      id, more than 40 properties) fails closed to `error`, never raising
      `pydantic.ValidationError` out of the tool's public boundary.
    - Truncation is disclosed honestly on the name path: resolved CIDs
      dropped by the fan-out cap, or by being non-scalar, are reported via
      `truncated` and `total_available`.
    - An unrecognized 2xx property body fails closed to `error` on BOTH the
      cid path and the name path, not just one.
    - Free-text values extracted from a record body carry a per-value
      character cap.

Depends on:
    - system_03_search_agent.tools.ncbi_pubchem_actions (module under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchPubchemPropertyInput)
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_pubchem_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchPubchemPropertyInput


class _FakeClient:
    """Same shape as the sibling test files' `_FakeClient`: a scripted
    sequence of canned `httpx.Response` objects, no real network. Supports
    multiple queued responses for the `name` lookup's two-call chain.
    """

    def __init__(self, items: list[httpx.Response]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
        self.calls.append({"url": url, "timeout": timeout})
        return self._items.pop(0)


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch):
    from system_03_search_agent.tools import ncbi_transport

    monkeypatch.delenv("NCBI_PUBCHEM_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


# ===========================================================================
# Happy path per endpoint, live-verified response shapes.
# ===========================================================================


@pytest.mark.asyncio
async def test_cid_lookup_returns_aspirin_chemistry() -> None:
    """compound/cid/{cid}/property/{list}/JSON. Live-verified 2026-08-05."""
    body = (
        '{"PropertyTable":{"Properties":[{"CID":2244,'
        '"MolecularFormula":"C9H8O4","MolecularWeight":"180.16"}]}}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property",
        lookup_type="cid",
        value="2244",
        properties=["MolecularFormula", "MolecularWeight"],
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    assert output.action == "pubchem_property"
    assert output.record_count == 1
    record = output.records[0]
    assert record.id == "2244"
    assert record.db == "pubchem"
    assert record.fields["MolecularFormula"] == "C9H8O4"
    assert record.source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/2244", (
            "F-3.1-08: PubChem now emits a valid source_url"
        )
    assert (
        "cid/2244/property/MolecularFormula%2CMolecularWeight/JSON"
        in client.calls[0]["url"]
        or "cid/2244/property/MolecularFormula,MolecularWeight/JSON" in client.calls[0]["url"]
    )


@pytest.mark.asyncio
async def test_cid_lookup_with_no_properties_uses_the_default_set() -> None:
    """Section 6.2's default extraction set: CID, MolecularFormula,
    MolecularWeight, ConnectivitySMILES, IUPACName.
    """
    body = '{"PropertyTable":{"Properties":[{"CID":2244,"MolecularFormula":"C9H8O4"}]}}'
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    called_url = client.calls[0]["url"]
    assert "MolecularFormula" in called_url
    assert "ConnectivitySMILES" in called_url
    assert "IUPACName" in called_url


@pytest.mark.asyncio
async def test_name_lookup_resolves_then_fetches_properties() -> None:
    """compound/name/{name}/cids/JSON then compound/cid/{cid}/property/{list}/JSON.

    Live-verified 2026-08-05: "aspirin" resolves to CID 2244.
    """
    resolve_body = '{"IdentifierList":{"CID":[2244]}}'
    property_body = '{"PropertyTable":{"Properties":[{"CID":2244,"MolecularFormula":"C9H8O4"}]}}'
    client = _FakeClient([httpx.Response(200, text=resolve_body), httpx.Response(200, text=property_body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property",
        lookup_type="name",
        value="aspirin",
        properties=["MolecularFormula"],
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    assert output.records[0].fields["MolecularFormula"] == "C9H8O4"
    assert output.records[0].id == "2244"
    assert len(client.calls) == 2
    assert "name/aspirin/cids/JSON" in client.calls[0]["url"]
    assert "cid/2244/property/" in client.calls[1]["url"]


@pytest.mark.asyncio
async def test_name_lookup_with_no_matching_cid_is_empty() -> None:
    """A 2xx resolve response whose CID list is empty. Fails closed to empty,
    not ok (nothing to cite) and not error (nothing broke).
    """
    resolve_body = '{"IdentifierList":{"CID":[]}}'
    client = _FakeClient([httpx.Response(200, text=resolve_body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="notarealchemical"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "empty"
    assert not output.records
    assert len(client.calls) == 1, "no property fetch should fire for zero resolved CIDs"


# ===========================================================================
# 400 / 404 classify as error, by STATUS, using each envelope's own message.
# ===========================================================================


@pytest.mark.asyncio
async def test_bad_cid_400_is_error_with_the_faults_message() -> None:
    """Live-verified 2026-08-05: an out-of-range CID returns 400 with
    {"Fault": {"Code","Message"}}.
    """
    body = '{"Fault":{"Code":"PUGREST.BadRequest","Message":"Invalid ID, must be positive integer"}}'
    client = _FakeClient([httpx.Response(400, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property",
        lookup_type="cid",
        value="999999999999",
        properties=["MolecularFormula"],
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert "Invalid ID" in output.error
    assert not output.records


@pytest.mark.asyncio
async def test_name_not_found_404_is_error() -> None:
    """Live-verified 2026-08-05: an unmatched name returns 404, not 200.

    Distinct from the Datasets v2 finding (unmatched symbol is a 200 with
    an empty body): PubChem's name resolution genuinely 404s. Both are
    still branched on STATUS, and both still land correctly.
    """
    body = (
        '{"Fault":{"Code":"PUGREST.NotFound","Message":"No CID found",'
        '"Details":["No CID found that matches the given name"]}}'
    )
    client = _FakeClient([httpx.Response(404, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="notarealchemicalnamexyzzy"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert "No CID found" in output.error
    assert len(client.calls) == 1, "a failed resolve must never fan out to a property fetch"


# ===========================================================================
# The mirror-image proof: status decides, not body content.
# ===========================================================================


@pytest.mark.asyncio
async def test_fault_shaped_key_under_a_200_does_not_force_error_status() -> None:
    """The single most important test in this file.

    A body carrying a `Fault` key (PubChem's own error envelope shape)
    served under HTTP 200 must NOT be classified `error` when real property
    data is also present. `PropertyTable.Properties` is what decides `ok`
    here; the stray `Fault` key is not inspected, because status already
    decided the outer verdict. The opposite of the E-utilities family.
    """
    body = (
        '{"PropertyTable":{"Properties":[{"CID":2244,"MolecularFormula":"C9H8O4"}]},'
        '"Fault":{"Code":"irrelevant","Message":"this must be ignored, status already said 200"}}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok", (
        f"a Fault-shaped body under HTTP 200 must still classify ok when "
        f"real property data is present, got {output.status!r}: {output.error}"
    )
    assert output.records[0].fields["MolecularFormula"] == "C9H8O4"


@pytest.mark.asyncio
async def test_unrecognized_2xx_body_fails_closed_to_error() -> None:
    """A 2xx body matching neither PropertyTable nor IdentifierList must not
    be silently treated as ok. Allowlist discipline, fail closed.
    """
    client = _FakeClient([httpx.Response(200, text='{"somethingUnexpected": true}')])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None


# ===========================================================================
# URL-encoding of a hostile path segment.
# ===========================================================================


@pytest.mark.asyncio
async def test_hostile_name_value_is_url_encoded() -> None:
    """A `name` value carrying a path-breaking character must not alter the
    request path. `/../` in a raw segment could redirect to a different
    endpoint entirely.
    """
    client = _FakeClient([httpx.Response(200, text='{"IdentifierList":{"CID":[]}}')])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="aspirin/../../admin"
    )

    await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    called_url = client.calls[0]["url"]
    assert "/../" not in called_url, f"raw path traversal survived encoding: {called_url!r}"
    assert "%2F" in called_url


@pytest.mark.asyncio
async def test_hostile_property_name_is_url_encoded() -> None:
    """A caller-supplied `properties` entry carrying a `/` must not be
    concatenated raw into the comma-joined property-list path segment.
    """
    client = _FakeClient([httpx.Response(200, text='{"PropertyTable":{"Properties":[]}}')])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property",
        lookup_type="cid",
        value="2244",
        properties=["MolecularFormula", "../admin"],
    )

    await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    called_url = client.calls[0]["url"]
    assert "/../" not in called_url
    assert "%2F" in called_url
    assert "MolecularFormula" in called_url


@pytest.mark.asyncio
async def test_hostile_cid_value_is_url_encoded() -> None:
    client = _FakeClient([httpx.Response(200, text='{"PropertyTable":{"Properties":[]}}')])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property",
        lookup_type="cid",
        value="2244/../../admin",
        properties=["MolecularFormula"],
    )

    await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    called_url = client.calls[0]["url"]
    assert "/../" not in called_url
    assert "%2F" in called_url


# ===========================================================================
# F-3.1-08-residual / F-3.1-36: the CID inside source_url is untrusted
# response-body content and must be encoded, not f-string interpolated.
# ===========================================================================


@pytest.mark.parametrize(
    ("hostile_cid", "forbidden"),
    [
        ("22/../../../evil", "/../"),
        ("22 44", " "),
        ("22\n44", "\n"),
        ("<script>x</script>", "<script>"),
        ("22?next=https://evil.example", "?"),
        ("22#frag", "#"),
    ],
)
@pytest.mark.asyncio
async def test_hostile_cid_in_response_body_is_encoded_in_source_url(
    hostile_cid: str, forbidden: str
) -> None:
    """A malformed or hostile `CID` in the PubChem RESPONSE must not reach
    the citation URL raw. The value comes from the network, not the caller,
    so encoding it is not optional.
    """
    body = json.dumps(
        {"PropertyTable": {"Properties": [{"CID": hostile_cid, "MolecularFormula": "C9H8O4"}]}}
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    source_url = output.records[0].source_url
    assert source_url is not None
    assert source_url.startswith("https://pubchem.ncbi.nlm.nih.gov/compound/")
    assert forbidden not in source_url, (
        f"raw hostile content survived into the citation URL: {source_url!r}"
    )
    assert hostile_cid not in source_url


@pytest.mark.asyncio
async def test_wellformed_cid_still_produces_a_readable_source_url() -> None:
    """Encoding must not mangle the ordinary case."""
    body = '{"PropertyTable":{"Properties":[{"CID":2244,"MolecularFormula":"C9H8O4"}]}}'
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.records[0].source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/2244"


# ===========================================================================
# F-3.1-34: a schema-violating response fails closed, never raises out of
# the tool's public boundary.
# ===========================================================================


@pytest.mark.asyncio
async def test_over_forty_properties_fails_closed_instead_of_raising() -> None:
    """`NcbiEfetchRecord.fields` caps at 40 properties. A response carrying
    41 used to raise `pydantic.ValidationError` straight out of
    `pubchem_property`.
    """
    entry: dict[str, Any] = {"CID": 2244}
    entry.update({f"Prop{index}": "x" for index in range(45)})
    body = json.dumps({"PropertyTable": {"Properties": [entry]}})
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert not output.records


@pytest.mark.asyncio
async def test_over_long_cid_fails_closed_instead_of_raising() -> None:
    """`NcbiEfetchRecord.id` caps at 30 characters, and `source_url` at 300."""
    body = json.dumps({"PropertyTable": {"Properties": [{"CID": "9" * 400}]}})
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert len(output.error) <= 500


# ===========================================================================
# F-3.1-12: per-value character cap on extracted free text.
# ===========================================================================


@pytest.mark.asyncio
async def test_over_long_property_value_is_capped() -> None:
    body = json.dumps({"PropertyTable": {"Properties": [{"CID": 2244, "IUPACName": "a" * 9000}]}})
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="cid", value="2244"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    value = output.records[0].fields["IUPACName"]
    assert len(value) < 9000
    assert value.endswith("[truncated]")


# ===========================================================================
# F-3.1-21 (re-review): honest truncation disclosure on the name path.
# ===========================================================================


@pytest.mark.asyncio
async def test_name_lookup_discloses_cids_dropped_by_the_fanout_cap() -> None:
    """40 resolved CIDs, only `_MAX_NAME_RESOLVED_CIDS` fetched. The caller
    must be able to see that the rest were dropped.
    """
    resolve_body = json.dumps({"IdentifierList": {"CID": list(range(1, 41))}})
    property_bodies = [
        httpx.Response(
            200,
            text=json.dumps({"PropertyTable": {"Properties": [{"CID": cid}]}}),
        )
        for cid in range(1, ncbi_pubchem_actions._MAX_NAME_RESOLVED_CIDS + 1)
    ]
    client = _FakeClient([httpx.Response(200, text=resolve_body), *property_bodies])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="ambiguouschemical"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    assert output.record_count == ncbi_pubchem_actions._MAX_NAME_RESOLVED_CIDS
    assert output.truncated is True, "40 resolved CIDs, 5 fetched, must not report truncated=False"
    assert output.total_available == 40


@pytest.mark.asyncio
async def test_name_lookup_within_the_cap_reports_no_truncation() -> None:
    """The disclosure must not fire when nothing was actually dropped."""
    resolve_body = json.dumps({"IdentifierList": {"CID": [2244, 2245]}})
    property_bodies = [
        httpx.Response(200, text=json.dumps({"PropertyTable": {"Properties": [{"CID": cid}]}}))
        for cid in (2244, 2245)
    ]
    client = _FakeClient([httpx.Response(200, text=resolve_body), *property_bodies])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="aspirin"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    assert output.truncated is False
    assert output.total_available is None


@pytest.mark.asyncio
async def test_name_lookup_discloses_a_silently_dropped_non_scalar_cid() -> None:
    """A minority of non-scalar entries is tolerated but must be counted in
    the disclosure, never silently swallowed (F-3.1-34, part 2).
    """
    resolve_body = json.dumps({"IdentifierList": {"CID": [2244, {"nested": 1}, 2245]}})
    property_bodies = [
        httpx.Response(200, text=json.dumps({"PropertyTable": {"Properties": [{"CID": cid}]}}))
        for cid in (2244, 2245)
    ]
    client = _FakeClient([httpx.Response(200, text=resolve_body), *property_bodies])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="partlymalformed"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "ok"
    assert output.truncated is True
    assert output.total_available == 3, "the dropped non-scalar entry must be disclosed"


@pytest.mark.asyncio
async def test_majority_non_scalar_cid_list_fails_closed() -> None:
    """A body where most entries are unusable is malformed, not odd."""
    resolve_body = json.dumps({"IdentifierList": {"CID": [2244, {"a": 1}, None, [1], {"b": 2}]}})
    client = _FakeClient([httpx.Response(200, text=resolve_body)])
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="malformed"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert len(client.calls) == 1, "a malformed resolution must not fan out to property fetches"


# ===========================================================================
# F-3.1-21 (re-review): the unrecognized-body verdict is the same on both
# paths.
# ===========================================================================


@pytest.mark.asyncio
async def test_unrecognized_2xx_property_body_on_the_name_path_is_error() -> None:
    """The cid path already fails closed on this exact shape. The name path
    used to report it as `empty`, which reads to the caller as "nothing
    matched" instead of "this API no longer looks like what we verified".
    """
    resolve_body = '{"IdentifierList":{"CID":[2244]}}'
    client = _FakeClient(
        [
            httpx.Response(200, text=resolve_body),
            httpx.Response(200, text='{"somethingUnexpected": true}'),
        ]
    )
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="aspirin"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "error", (
        f"the name path must fail closed on an unrecognized 2xx body exactly "
        f"as the cid path does, got {output.status!r}"
    )
    assert output.error is not None
    assert not output.records


@pytest.mark.asyncio
async def test_genuinely_empty_property_table_on_the_name_path_is_still_empty() -> None:
    """The fix above must not turn a well-formed zero-result answer into an
    error: `{"PropertyTable": {"Properties": []}}` is recognized and empty.
    """
    resolve_body = '{"IdentifierList":{"CID":[2244]}}'
    client = _FakeClient(
        [
            httpx.Response(200, text=resolve_body),
            httpx.Response(200, text='{"PropertyTable":{"Properties":[]}}'),
        ]
    )
    action_input = NcbiEfetchPubchemPropertyInput(
        action="pubchem_property", lookup_type="name", value="aspirin"
    )

    output = await ncbi_pubchem_actions.pubchem_property(action_input, client=client)

    assert output.status == "empty"
    assert not output.records
