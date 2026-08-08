"""Unit tests for `pubtator_annotate` (T-3.3-05).

No live network anywhere in this file. Every case mocks at the transport
boundary, `ncbi_transport.execute_get`, patched to return a canned
`httpx.Response` or raise a canned `ncbi_transport.TransportError`, the same
`_ScriptedTransport` pattern `test_ncbi_dbsnp.py` already established. Live
network coverage of the real endpoints is `test_pubtator_annotate_premise.py`'s
job, not this file's.

Fixture bodies below are trimmed, hand-shaped copies of the ACTUAL live
responses captured while writing `pubtator_annotate.py` (2026-08-08), not
fixtures authored from a reading of documentation: the entity_lookup array
shape, the `{"PubTator3": [...]}` wrapper, and the `infons` annotation shape
(including the live int-typed `normalized_id`) all match what the real
endpoints returned, per LEARNINGS.md row 60's discipline.

Covers, per this ticket's explicit requirements:
    - entity_lookup: ok (a real match), empty (`[]` body), a non-list body
      (error, fail closed), a transport failure (error).
    - annotate_publications: ok (a real PMID, the `.PubTator3[i].passages[]
      .annotations[]` wrapper actually unwrapped), the F-3.3-01 mixed-batch
      drop (`pmids_not_found`), the documented all-invalid HTTP 400
      `{"detail": ...}` shape (error), a malformed body with no `PubTator3`
      key (error), a transport failure (error).
    - The withhold-not-truncate path: an over-length `entities[].name` and
      an over-length `annotations[].identifier` are withheld (`None`), never
      truncated into a real-looking-but-wrong value, and the call still
      ships `status: "ok"` for everything else.
    - `source_url` is always the human-facing PubMed page
      (`pubmed.ncbi.nlm.nih.gov`), URL-encoded, host-pinned, never the
      PubTator3 API host actually fetched.
    - `infons.normalized_id`'s live int-vs-string drift (fact 3) is coerced
      to `str`, never passed through as a raw int.
    - The dispatcher: `family="pubtator"` is the family every call uses, an
      unexpected exception from a mode branch is caught and reported as an
      actionable `status: "error"`, never propagated.

Depends on:
    - system_03_search_agent.tools.pubtator_annotate (module under test)
    - system_03_search_agent.tools.ncbi_transport, monkeypatched at
      execute_get
    - system_03_search_agent.tools.pubtator_annotate_schemas, for
      constructing valid inputs
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools import pubtator_annotate as pubtator_annotate_module
from system_03_search_agent.tools.pubtator_annotate import pubtator_annotate
from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateInput


def _json_response(body: Any, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


class _ScriptedTransport:
    """Replaces ncbi_transport.execute_get with a scripted sequence of responses.

    Each entry is either an httpx.Response (returned) or an Exception
    (raised), popped in call order. Records every call's URL, params, and
    kwargs so a test can assert not just what came back, but exactly what
    was requested (the family used, the query params sent).
    """

    def __init__(self, items: list[httpx.Response | Exception]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, url: str, params: dict[str, Any], **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, "params": dict(params), "kwargs": kwargs})
        if not self._items:
            raise AssertionError(f"unexpected extra transport call: {url}")
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install(monkeypatch: pytest.MonkeyPatch, items: list[httpx.Response | Exception]) -> _ScriptedTransport:
    scripted = _ScriptedTransport(items)
    monkeypatch.setattr(pubtator_annotate_module.ncbi_transport, "execute_get", scripted)
    return scripted


# ---------------------------------------------------------------------------
# Fixture bodies: trimmed, live-shaped copies of real responses (see module
# docstring). Only the fields pubtator_annotate.py actually reads are kept.
# ---------------------------------------------------------------------------


def _entity_autocomplete_body() -> list[dict[str, Any]]:
    return [
        {
            "_id": "@GENE_BRCA1",
            "biotype": "gene",
            "db_id": "672",
            "db": "ncbi_gene",
            "name": "BRCA1",
            "description": "All Species",
            "match": "Matched on name <m>BRCA1</m>",
        },
        {
            "_id": "@VARIANT_c.5382insC_BRCA1_human",
            "biotype": "variant",
            "db_id": "#672#c.5382insC",
            "db": "litvar",
            "name": "c.5382insC",
            "description": "BRCA1 (human)",
            "match": "Multiple matches",
        },
    ]


def _publication_doc(pmid: str = "34083286", *, gene_identifier: str = "672") -> dict[str, Any]:
    return {
        "_id": f"{pmid}|None",
        "id": pmid,
        "infons": {},
        "passages": [
            {
                "infons": {"type": "title"},
                "offset": 0,
                "text": "BRCA1-BRCT Mutations Alter the Subcellular Localization of BRCA1.",
                "annotations": [
                    {
                        "id": "2",
                        "infons": {
                            "identifier": gene_identifier,
                            "type": "Gene",
                            "valid": True,
                            "normalized_id": int(gene_identifier),
                            "database": "ncbi_gene",
                            "biotype": "gene",
                            "name": "BRCA1",
                            "accession": "@GENE_BRCA1",
                        },
                        "text": "BRCA1",
                        "locations": [{"offset": 0, "length": 5}],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# entity_lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_lookup_ok_parses_real_match(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _install(monkeypatch, [_json_response(_entity_autocomplete_body())])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    assert output.mode == "entity_lookup"
    assert len(output.entities) == 2
    gene = output.entities[0]
    assert gene.pubtator_id == "@GENE_BRCA1"
    assert gene.biotype == "gene"
    assert gene.db == "ncbi_gene"
    assert gene.db_id == "672"
    assert gene.name == "BRCA1"
    assert gene.description == "All Species"

    assert len(scripted.calls) == 1
    assert scripted.calls[0]["kwargs"]["family"] == "pubtator"
    assert scripted.calls[0]["params"] == {"query": "BRCA1", "limit": 5}


@pytest.mark.asyncio
async def test_entity_lookup_no_match_is_empty_not_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, [_json_response([])])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="zzznotarealtermxyz", limit=5)
    )

    assert output.status == "empty"
    assert output.entities == []


@pytest.mark.asyncio
async def test_entity_lookup_non_list_body_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 response whose body is not a JSON array is `error`, not a guess."""
    _install(monkeypatch, [_json_response({"unexpected": "shape"})])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "error"
    assert output.error


@pytest.mark.asyncio
async def test_entity_lookup_transport_failure_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        [ncbi_transport.TransportTimeoutError("www.ncbi.nlm.nih.gov timed out after 15.0s")],
    )

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "error"
    assert "timed out" in output.error


@pytest.mark.asyncio
async def test_entity_lookup_withholds_over_length_field_not_truncate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-length `name` is withheld (`None`), never a truncated real-looking value."""
    over_length_name = "X" * 150  # exceeds the 100-char cap
    body = [
        {
            "_id": "@GENE_TEST",
            "biotype": "gene",
            "db_id": "1",
            "db": "ncbi_gene",
            "name": over_length_name,
            "description": "fine",
        }
    ]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="test", limit=5)
    )

    assert output.status == "ok"
    assert len(output.entities) == 1
    assert output.entities[0].name is None, "over-length name must be withheld, not truncated"
    assert output.entities[0].description == "fine"
    assert output.entities[0].db_id == "1"


# ---------------------------------------------------------------------------
# annotate_publications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_annotate_publications_ok_unwraps_the_pubtator3_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"PubTator3": [_publication_doc("34083286")]}
    scripted = _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "ok"
    assert output.mode == "annotate_publications"
    assert len(output.publications) == 1
    pub = output.publications[0]
    assert pub.pmid == "34083286"
    assert pub.source_url == "https://pubmed.ncbi.nlm.nih.gov/34083286/"
    gene_annotations = [a for a in pub.annotations if a.type == "Gene"]
    assert gene_annotations
    assert gene_annotations[0].identifier == "672"
    assert gene_annotations[0].normalized_id == "672", "int normalized_id must coerce to str"
    assert gene_annotations[0].valid is True
    assert output.pmids_not_found == []

    assert scripted.calls[0]["kwargs"]["family"] == "pubtator"
    assert scripted.calls[0]["params"] == {"pmids": "34083286"}


@pytest.mark.asyncio
async def test_f_3_3_01_mixed_batch_reports_dropped_pmid_not_silent_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-01: PubTator3 silently drops a nonexistent PMID from a mixed batch."""
    body = {"PubTator3": [_publication_doc("34083286")]}
    scripted = _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(
            mode="annotate_publications", pmids=["34083286", "999999999999"]
        )
    )

    assert output.status == "ok", "a batch with at least one real PMID must still be ok"
    returned_pmids = [pub.pmid for pub in output.publications]
    assert "34083286" in returned_pmids
    assert "999999999999" not in returned_pmids
    assert output.pmids_not_found == ["999999999999"]
    assert scripted.calls[0]["params"] == {"pmids": "34083286,999999999999"}


@pytest.mark.asyncio
async def test_annotate_publications_all_invalid_batch_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented all-invalid-batch shape: HTTP 400, `{"detail": ...}`."""
    _install(
        monkeypatch,
        [_json_response({"detail": "Could not retrieve publications"}, status_code=400)],
    )

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["999999999999"])
    )

    assert output.status == "error"
    assert output.error == "Could not retrieve publications"
    assert output.publications == []


@pytest.mark.asyncio
async def test_annotate_publications_malformed_body_no_pubtator3_key_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, [_json_response({"unexpected": "shape"})])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "error"
    assert output.error


@pytest.mark.asyncio
async def test_annotate_publications_transport_failure_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [ncbi_transport.TransportConnectionError("www.ncbi.nlm.nih.gov connection failed")],
    )

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "error"
    assert "connection failed" in output.error


@pytest.mark.asyncio
async def test_annotate_publications_withholds_over_length_annotation_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-length `identifier` is withheld, not truncated; the rest still ships."""
    doc = _publication_doc("34083286")
    over_length_identifier = "Y" * 90  # exceeds the 60-char cap
    doc["passages"][0]["annotations"][0]["infons"]["identifier"] = over_length_identifier
    body = {"PubTator3": [doc]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "ok"
    annotation = output.publications[0].annotations[0]
    assert annotation.identifier is None, "over-length identifier must be withheld, not truncated"
    assert annotation.type == "Gene", "other in-cap fields on the same annotation still ship"


@pytest.mark.asyncio
async def test_annotate_publications_pmid_used_is_id_not_compound_underscore_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`id` (a plain string) is the reliable PMID field, not `_id` (compound)."""
    doc = _publication_doc("34083286")
    assert doc["_id"] == "34083286|None"
    body = {"PubTator3": [doc]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.publications[0].pmid == "34083286"


@pytest.mark.asyncio
async def test_annotate_publications_source_url_is_url_encoded_and_host_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"PubTator3": [_publication_doc("34083286")]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    source_url = output.publications[0].source_url
    assert source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/")
    assert "research/pubtator3-api" not in source_url, (
        "source_url must be the human-facing PubMed page, never the fetch host"
    )


# ---------------------------------------------------------------------------
# Dispatcher: family used, never raises.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_wraps_unexpected_exception_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected exception from a mode branch is caught, never propagated."""

    async def _boom(_input: Any) -> Any:
        raise RuntimeError("simulated defect")

    monkeypatch.setattr(pubtator_annotate_module, "_entity_lookup", _boom)

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "error"
    assert output.mode == "entity_lookup"
    assert "RuntimeError" in output.error
    assert "simulated defect" in output.error
