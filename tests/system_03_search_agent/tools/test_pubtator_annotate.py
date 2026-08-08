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
    - F-3.3-A-01/F-3.3-A-02/F-3.3-A-03: `matched_on` is populated from the
      upstream `match` field when present, `None` when absent, and
      withheld (not truncated) like any other over-length field.
    - F-3.3-A-04: `pmids_not_found` diffs on CANONICAL identity, not the
      raw requested string, so a leading-zero or whitespace-padded
      variant of a PMID that WAS returned never appears in
      `pmids_not_found`, while a genuinely missing PMID still does, in
      its original requested form.
    - F-3.3-A-06/F-3.3-A-07: an empty `pmids` list is rejected at the
      schema layer before any network call (see
      `test_pubtator_annotate_schemas.py`); the error message for a
      content-free transport fallback always carries actionable guidance,
      never ships the bare `"HTTP {status} with no structured error
      body"` string alone.
    - F-3.3-J-04 (fix round 4): a withheld `entities[]` or
      `publications[].annotations[]` field is disclosed in
      `fields_withheld`, named by its OUTPUT position (never a raw
      response index, even after an earlier row is skipped), and more
      than 20 notes cap at 20 with a summary rather than raising
      `pydantic.ValidationError` out of a fully successful call.
    - F-3.3-A-05 (fix round 4): `entities[].source_url` is populated for
      `db == "ncbi_gene"` and `db == "ncbi_mesh"`, `None` for every other
      `db` value, and `None` when the underlying `db_id` was itself
      withheld for exceeding its own cap.
    - F-3.3-A-12 (fix round 4): `publications[].total_annotations` carries
      the TRUE count of well-formed annotations before the `maxItems: 100`
      cap on `annotations`, never merely `len(annotations)`.

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


def _entity_autocomplete_body(*, include_match: bool = True) -> list[dict[str, Any]]:
    first: dict[str, Any] = {
        "_id": "@GENE_BRCA1",
        "biotype": "gene",
        "db_id": "672",
        "db": "ncbi_gene",
        "name": "BRCA1",
        "description": "All Species",
    }
    second: dict[str, Any] = {
        "_id": "@VARIANT_c.5382insC_BRCA1_human",
        "biotype": "variant",
        "db_id": "#672#c.5382insC",
        "db": "litvar",
        "name": "c.5382insC",
        "description": "BRCA1 (human)",
    }
    if include_match:
        first["match"] = "Matched on name <m>BRCA1</m>"
        second["match"] = "Multiple matches"
    return [first, second]


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
async def test_f_3_3_a_07_entity_lookup_content_free_fallback_gets_actionable_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-A-07: when PubTator3's error body falls through every recognized
    shape (here, a bare JSON array, the same F-3.3-02 shape reached live via
    an empty query), ncbi_transport's own generic fallback
    ("HTTP {status} with no structured error body") must never surface as
    the WHOLE message with no next-step guidance appended.
    """
    _install(
        monkeypatch,
        [_json_response(["query is a mandatory parameter."], status_code=400)],
    )

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="x", limit=5)
    )

    assert output.status == "error"
    assert output.error is not None
    assert output.error != "HTTP 400 with no structured error body", (
        "the bare transport fallback must never ship as the entire message"
    )
    assert "Retry once" in output.error, "the message must name an actionable next step"


@pytest.mark.asyncio
async def test_entity_lookup_withholds_over_length_field_not_truncate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-length `name` is withheld (`None`), never a truncated real-looking value."""
    # Exceeds the 100-char name cap, but the full "entities[0].name: <value>"
    # note itself still fits within the 150-char fields_withheld item cap
    # (19-char label + 110-char value = 129 chars), so this test can assert
    # the note's exact content below rather than a truncated fragment of it.
    over_length_name = "X" * 110
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
    assert output.fields_withheld == [f"entities[0].name: {over_length_name}"], (
        "F-3.3-J-04: withholding a field must disclose it, named by OUTPUT "
        "position, mirroring litvar2_lookup's fields_withheld"
    )


# ---------------------------------------------------------------------------
# F-3.3-A-01/F-3.3-A-02/F-3.3-A-03 regression: matched_on discloses
# PubTator3's own relevance signal instead of silently discarding it.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matched_on_is_populated_from_the_upstream_match_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, [_json_response(_entity_autocomplete_body())])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    assert output.entities[0].matched_on == "Matched on name <m>BRCA1</m>"
    assert output.entities[1].matched_on == "Multiple matches"


@pytest.mark.asyncio
async def test_matched_on_is_none_when_the_upstream_row_omits_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, [_json_response(_entity_autocomplete_body(include_match=False))])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    assert output.entities[0].matched_on is None


@pytest.mark.asyncio
async def test_over_length_matched_on_is_withheld_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    over_length_match = "Matched on synonyms <m>" + ("x" * 190) + "</m>"
    assert len(over_length_match) > 200
    body = _entity_autocomplete_body(include_match=False)
    body[0]["match"] = over_length_match
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    assert output.entities[0].matched_on is None, "over-length matched_on must be withheld, not truncated"
    assert output.entities[0].name == "BRCA1", "other in-cap fields on the same entity still ship"


# ---------------------------------------------------------------------------
# F-3.3-J-04: entities[] fields_withheld disclosure, index correctness, and
# the 20-item overflow cap (mirroring litvar2_lookup.py's F-3.3-J-01 fix).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f_3_3_j_04_fields_withheld_is_none_when_nothing_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, [_json_response(_entity_autocomplete_body())])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    assert output.fields_withheld is None


@pytest.mark.asyncio
async def test_f_3_3_j_04_withheld_note_index_matches_output_position_after_a_skipped_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raw row that fails to parse (not an object) is skipped entirely and
    never occupies an output position, so a later KEPT entity's withheld
    field must be labeled by its OUTPUT index, not its raw array index
    (F-3.3-J-03's discipline, applied here for pubtator_annotate).
    """
    over_length_name = "Z" * 110  # over the 100-char cap, still fits the 150-char note cap
    body = [
        "not-an-object",  # raw index 0, skipped entirely
        {
            "_id": "@GENE_TEST",
            "db": "ncbi_gene",
            "db_id": "1",
            "name": over_length_name,  # raw index 1, output index 0
        },
    ]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="test", limit=5)
    )

    assert output.status == "ok"
    assert len(output.entities) == 1
    assert output.fields_withheld == [f"entities[0].name: {over_length_name}"], (
        "the kept entity is at OUTPUT position 0, never raw position 1"
    )


@pytest.mark.asyncio
async def test_f_3_3_j_04_many_withheld_fields_are_capped_not_a_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """More than 20 withheld-field notes must not raise pydantic.ValidationError
    out of a fully successful call; the list caps at 20 with a summary note,
    mirroring litvar2_lookup._cap_fields_withheld exactly (F-3.3-J-01's
    precedent, applied here from the start).
    """
    over_length_name = "Q" * 150
    over_length_description = "R" * 400
    # 11 entities, each withholding both name and description: 22 notes,
    # exceeding the 20-item cap (20 notes exactly would NOT overflow: the
    # cap only replaces the final slot when there are MORE than 20).
    body = [
        {
            "_id": f"@GENE_{i}",
            "db": "ncbi_gene",
            "db_id": str(i),
            "name": over_length_name,
            "description": over_length_description,
        }
        for i in range(11)
    ]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="test", limit=20)
    )

    assert output.status == "ok", output.error
    assert len(output.entities) == 11
    assert output.fields_withheld is not None
    assert len(output.fields_withheld) == 20, "must cap at the schema's own max_length=20"
    assert "more fields withheld" in output.fields_withheld[-1]


# ---------------------------------------------------------------------------
# F-3.3-A-05: entities[].source_url, deliberately partial (ncbi_gene/
# ncbi_mesh only).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f_3_3_a_05_entity_source_url_for_ncbi_gene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, [_json_response(_entity_autocomplete_body())])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    gene = output.entities[0]
    assert gene.db == "ncbi_gene"
    assert gene.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"


@pytest.mark.asyncio
async def test_f_3_3_a_05_entity_source_url_for_ncbi_mesh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = [
        {
            "_id": "@DISEASE_D001943",
            "db": "ncbi_mesh",
            "db_id": "D001943",
            "name": "Breast Neoplasms",
        }
    ]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="breast cancer", limit=5)
    )

    assert output.status == "ok"
    assert output.entities[0].source_url == "https://www.ncbi.nlm.nih.gov/mesh/D001943"


@pytest.mark.asyncio
async def test_f_3_3_a_05_entity_source_url_none_for_unrecognized_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`db == "litvar"` (or any other value) is deliberately NOT covered:
    this tool does not guess a URL shape it has not verified live.
    """
    _install(monkeypatch, [_json_response(_entity_autocomplete_body())])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1", limit=5)
    )

    assert output.status == "ok"
    variant_entity = output.entities[1]
    assert variant_entity.db == "litvar"
    assert variant_entity.source_url is None


@pytest.mark.asyncio
async def test_f_3_3_a_05_entity_source_url_none_when_db_id_is_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source_url must never be built from a db_id that was itself
    withheld for exceeding its own cap: there is no valid identifier left
    to link to.
    """
    over_length_db_id = "1" * 40  # exceeds the 30-char db_id cap
    body = [{"_id": "@GENE_X", "db": "ncbi_gene", "db_id": over_length_db_id, "name": "X"}]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="x", limit=5)
    )

    assert output.status == "ok"
    entity = output.entities[0]
    assert entity.db_id is None, "over-length db_id must be withheld"
    assert entity.source_url is None, "source_url must not be built from a withheld db_id"


@pytest.mark.asyncio
async def test_f_3_3_rr2_03_entity_source_url_none_when_db_id_is_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-RR2-03 regression: `db_id=""` is falsy, not `None`, and the old
    `db_id is None` guard let it through, building
    `https://www.ncbi.nlm.nih.gov/gene/` (live-confirmed HTTP 200, the NCBI
    Gene database homepage, not a record) as if it were a real citation.
    `db_id=""` must produce `source_url=None`, matching
    `litvar2_lookup._build_source_url`'s own `if not identifier` guard for
    the sibling tool.
    """
    body = [{"_id": "@GENE_X", "db": "ncbi_gene", "db_id": "", "name": "X"}]
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query="x", limit=5)
    )

    assert output.status == "ok"
    entity = output.entities[0]
    assert entity.db_id == "", "an empty db_id is not itself withheld, only unusable for a URL"
    assert entity.source_url is None, "source_url must not be built from an empty db_id"


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
async def test_f_3_3_a_04_leading_zero_pmid_is_not_reported_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-A-04: PubTator3 normalizes a leading zero and answers with the
    canonical id; the diff must not report the requested (unnormalized)
    form as missing when its canonical form was actually returned.
    """
    body = {"PubTator3": [_publication_doc("34083286")]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["034083286"])
    )

    assert output.status == "ok", output.error
    returned_pmids = [pub.pmid for pub in output.publications]
    assert "34083286" in returned_pmids
    assert output.pmids_not_found == [], (
        f"a requested id whose canonical form WAS returned must never appear "
        f"in pmids_not_found, got {output.pmids_not_found!r}"
    )


@pytest.mark.asyncio
async def test_f_3_3_a_04_whitespace_padded_pmid_is_not_reported_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"PubTator3": [_publication_doc("34083286")]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=[" 34083286"])
    )

    assert output.status == "ok", output.error
    assert output.pmids_not_found == []


@pytest.mark.asyncio
async def test_f_3_3_a_04_genuinely_missing_pmid_still_reports_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The identity-normalization fix must not swallow a REAL drop: a
    nonexistent PMID with no canonical match anywhere in the response must
    still surface in pmids_not_found, the exact F-3.3-01 case this field
    exists for.
    """
    body = {"PubTator3": [_publication_doc("34083286")]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286", "999999999999"])
    )

    assert output.status == "ok", output.error
    assert output.pmids_not_found == ["999999999999"]


@pytest.mark.asyncio
async def test_f_3_3_a_04_pmids_not_found_reports_original_string_not_canonical_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonicalization is for identity comparison only; disclosure still
    names the caller's original requested string, never the normalized form.
    """
    _install(monkeypatch, [_json_response({"PubTator3": []})])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["099999999999"])
    )

    assert output.pmids_not_found == ["099999999999"], (
        "a genuine miss must be disclosed in its ORIGINAL requested form, "
        f"got {output.pmids_not_found!r}"
    )


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
async def test_f_3_3_a_06_and_a_07_empty_pmids_reaching_the_api_gets_actionable_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-A-06 closes this at the schema layer (pmids=[] now raises
    ValidationError before any network call, see
    test_pubtator_annotate_schemas.py). This test proves the OTHER half,
    F-3.3-A-07: even if this exact bare-array shape were ever reached
    (e.g. a future schema change reopened the gap, or PubTator3 changes
    what triggers it), the resulting message still carries actionable
    guidance rather than shipping the bare transport fallback verbatim.
    """
    _install(
        monkeypatch,
        [_json_response(["pmids is a mandatory parameter."], status_code=400)],
    )

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["1"])
    )

    assert output.status == "error"
    assert output.error is not None
    assert output.error != "HTTP 400 with no structured error body"
    assert "Retry once" in output.error


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
    assert output.fields_withheld == [
        f"publications[0].annotations[0].identifier: {'Y' * 90}"
    ], "F-3.3-J-04: the withholding must be disclosed, keyed to OUTPUT position"


@pytest.mark.asyncio
async def test_f_3_3_j_04_annotation_withheld_note_keys_to_output_positions_across_two_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two publications, each with one over-length annotation field: the
    disclosure note for the SECOND publication's annotation must name
    publications[1], not the raw PubTator3[] array index, and each
    publication's own annotation index must start over at 0.
    """
    # Over the 100-char annotation name cap, still fits the 150-char note cap.
    over_length_name = "N" * 105
    doc_a = _publication_doc("34083286")
    doc_b = _publication_doc("11111111", gene_identifier="99")
    doc_b["passages"][0]["annotations"][0]["infons"]["name"] = over_length_name
    body = {"PubTator3": [doc_a, doc_b]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286", "11111111"])
    )

    assert output.status == "ok", output.error
    assert len(output.publications) == 2
    assert output.publications[0].annotations[0].name == "BRCA1"
    assert output.publications[1].annotations[0].name is None
    assert output.fields_withheld == [f"publications[1].annotations[0].name: {over_length_name}"]


@pytest.mark.asyncio
async def test_f_3_3_rr2_02_pub_index_keys_to_output_position_when_first_document_is_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-RR2-02 regression. The test above cannot distinguish `pub_index`
    (the OUTPUT position) from a raw enumerate index, because both of its
    fixture documents are KEPT, so the two numbers are identical by
    construction. This fixture excludes the FIRST raw document (no
    extractable `id`) so the SECOND, kept document lands at raw array
    position 1 but OUTPUT position 0: the disclosure note must name
    `publications[0]`, never `publications[1]`.

    Verified this test actually fails on the bug it targets: temporarily
    reverting `pub_index = len(publications)` (pubtator_annotate.py) back
    to the raw `enumerate` index makes this test fail with
    `publications[1].annotations[0].name: ...`, confirmed by hand before
    this test was finalized (see the fix round's report for the exact
    revert-and-rerun transcript).
    """
    doc_a = _publication_doc("34083286")
    del doc_a["id"]  # no extractable pmid: _parse_publication excludes this document entirely
    over_length_name = "N" * 105  # exceeds the 100-char annotation name cap
    doc_b = _publication_doc("11111111", gene_identifier="99")
    doc_b["passages"][0]["annotations"][0]["infons"]["name"] = over_length_name
    body = {"PubTator3": [doc_a, doc_b]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286", "11111111"])
    )

    assert output.status == "ok", output.error
    assert len(output.publications) == 1
    assert output.publications[0].pmid == "11111111"
    assert output.publications[0].annotations[0].name is None
    assert output.fields_withheld == [f"publications[0].annotations[0].name: {over_length_name}"]
    # The excluded document is unidentifiable to the caller by pmid at all
    # (no extractable id), so it is not requested-but-missing in the
    # pmids_not_found sense either; the caller's actual "34083286" request
    # still resolved to nothing, which the transport-level pmids_not_found
    # diff reports separately.
    assert "34083286" in output.pmids_not_found


@pytest.mark.asyncio
async def test_f_3_3_rr2_02_ann_index_keys_to_output_position_when_first_annotation_row_is_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.3-RR2-02 regression, the `ann_index` half. Within ONE kept
    publication, the raw `annotations` array's first row is excluded (its
    `infons` is not an object, so `_parse_annotation` returns `None`), so
    the SECOND, kept annotation lands at raw array position 1 but OUTPUT
    position 0: the disclosure note must name `annotations[0]`, never
    `annotations[1]`.

    Verified this test actually fails on the bug it targets: temporarily
    reverting `ann_index = len(annotations)` back to the raw `enumerate`
    index makes this test fail with `annotations[1].name: ...`, confirmed
    by hand before this test was finalized (see the fix round's report for
    the exact revert-and-rerun transcript).
    """
    doc = _publication_doc("34083286")
    over_length_name = "N" * 105  # exceeds the 100-char annotation name cap
    excluded_row: dict[str, Any] = {"id": "x", "infons": "not-an-object"}
    kept_row = doc["passages"][0]["annotations"][0]
    kept_row["infons"]["name"] = over_length_name
    doc["passages"][0]["annotations"] = [excluded_row, kept_row]
    body = {"PubTator3": [doc]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "ok", output.error
    assert len(output.publications) == 1
    assert len(output.publications[0].annotations) == 1
    assert output.publications[0].annotations[0].name is None
    assert output.fields_withheld == [f"publications[0].annotations[0].name: {over_length_name}"]


# ---------------------------------------------------------------------------
# F-3.3-A-12: total_annotations, a companion count for the silent
# maxItems: 100 cap on `annotations`.
# ---------------------------------------------------------------------------


def _many_annotations_doc(pmid: str, count: int) -> dict[str, Any]:
    """A publication doc carrying `count` well-formed annotations, exceeding
    _MAX_ANNOTATIONS (100) when count > 100.
    """
    doc = _publication_doc(pmid)
    doc["passages"][0]["annotations"] = [
        {
            "id": str(i),
            "infons": {"identifier": str(i), "type": "Gene", "name": f"gene-{i}"},
            "text": f"gene-{i}",
            "locations": [{"offset": i, "length": 5}],
        }
        for i in range(count)
    ]
    return doc


@pytest.mark.asyncio
async def test_f_3_3_a_12_total_annotations_reflects_true_count_before_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"PubTator3": [_many_annotations_doc("34083286", 130)]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "ok", output.error
    pub = output.publications[0]
    assert len(pub.annotations) == 100, "annotations must still cap at maxItems: 100"
    assert pub.total_annotations == 130, "total_annotations must carry the TRUE pre-cap count"
    assert pub.total_annotations != len(pub.annotations)


@pytest.mark.asyncio
async def test_f_3_3_a_12_total_annotations_equals_len_when_under_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"PubTator3": [_publication_doc("34083286")]}
    _install(monkeypatch, [_json_response(body)])

    output = await pubtator_annotate(
        PubtatorAnnotateInput(mode="annotate_publications", pmids=["34083286"])
    )

    assert output.status == "ok"
    pub = output.publications[0]
    assert pub.total_annotations == len(pub.annotations) == 1


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
