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
    - `source_url` is always `None`, per the documented host-pattern
      conflict: PubChem's own record host does not satisfy
      `NCBI_EFETCH_RECORD_URL_PATTERN`.

Depends on:
    - system_03_search_agent.tools.ncbi_pubchem_actions (module under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchPubchemPropertyInput)
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

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
    assert record.source_url is None, "PubChem's host does not satisfy the schema pattern"
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
