"""Unit tests for `ncbi_datasets_actions.dataset_report` (T-3.1-08).

No live network anywhere in this file. Every case mocks at the HTTP client
boundary with the same `_FakeClient` shape `test_ncbi_transport.py` already
established (canned `httpx.Response` objects, no real socket). Live-network
coverage of the real Datasets v2 endpoint is
`test_ncbi_efetch_premise.py`'s job (cases 3 and 10), not this file's.

The canned response bodies below are not invented: they are the exact
shapes recorded in `ncbi_datasets_actions.py`'s own module docstring,
live-probed 2026-08-04/08-05 against `api.ncbi.nlm.nih.gov/datasets/v2/`.

What this file proves, mapped to the ticket's acceptance:

    - Happy path per endpoint: gene by symbol+taxon, gene by id, genome by
      accession.
    - A 400 (malformed gene_id) classifies as `error` by HTTP STATUS.
    - An error-shaped body under a 200 (`error`/`code`/`message` keys, the
      Datasets error envelope) still classifies `ok`/`empty` on its own
      terms, never forced to `error` by the presence of those keys. This is
      the mirror image of the E-utilities family: status decides, body
      content that merely resembles an error is not enough on its own.
    - Incoherent input combinations (`report_type="gene"` with only an
      `accession`, `report_type="genome"` with no `accession`, `symbol`
      with no `taxon`) return an actionable error WITHOUT a network call.
    - A hostile path segment (`symbol` carrying `/` and other reserved
      characters) is URL-encoded before it reaches the request path, never
      concatenated raw.
    - The live-verified finding: a well-formed but unmatched symbol or
      accession returns HTTP 200 with an empty `{}` body, and this module
      collapses that to `status: "empty"`, never `"ok"` and never `"error"`.
    - Finding 9 (MAJOR, re-review): that collapse-to-`empty` rule is an
      ALLOWLIST on the one live-verified not-found shape (the literal
      empty `{}`), not a blanket rule for "any 2xx body lacking
      `reports`". A renamed key, an unrecognized non-empty 2xx body, or a
      `reports` field of the wrong type now fails closed as `error`,
      never silently reported as "no results".

Depends on:
    - system_03_search_agent.tools.ncbi_datasets_actions (module under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchDatasetReportInput)
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_datasets_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchDatasetReportInput


class _FakeClient:
    """Same shape as `test_ncbi_transport.py`'s `_FakeClient`: a scripted
    sequence of canned `httpx.Response` objects, no real network.
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

    monkeypatch.delenv("NCBI_DATASETS_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


# ===========================================================================
# Happy path per endpoint, live-verified response shapes.
# ===========================================================================


@pytest.mark.asyncio
async def test_gene_by_symbol_and_taxon_returns_the_right_gene() -> None:
    """gene/symbol/{symbol}/taxon/{taxon}. Live-verified 2026-08-04."""
    body = (
        '{"reports":[{"gene":{"gene_id":"7157","symbol":"TP53",'
        '"description":"tumor protein p53","tax_id":"9606",'
        '"taxname":"Homo sapiens","chromosomes":["17"],'
        '"omim_ids":["191170"]}}]}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", symbol="TP53", taxon="human"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    assert output.action == "dataset_report"
    assert output.record_count == 1
    record = output.records[0]
    assert record.id == "7157"
    assert record.db == "gene"
    assert record.fields["gene_id"] == "7157"
    assert record.fields["taxname"] == "Homo sapiens"
    assert record.fields["description"] == "tumor protein p53"
    assert record.source_url == "https://www.ncbi.nlm.nih.gov/gene/7157/"
    assert "gene/symbol/TP53/taxon/human" in client.calls[0]["url"]


@pytest.mark.asyncio
async def test_gene_by_id_returns_the_right_gene() -> None:
    """gene/id/{gene_id}. Live-verified 2026-08-05."""
    body = (
        '{"reports":[{"gene":{"gene_id":"7157","symbol":"TP53",'
        '"description":"tumor protein p53","taxname":"Homo sapiens"}}]}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    assert output.records[0].id == "7157"
    assert "gene/id/7157" in client.calls[0]["url"]
    # gene_id takes priority even if symbol/taxon are also (incoherently)
    # present, per _select_endpoint's documented priority order.


@pytest.mark.asyncio
async def test_genome_by_accession_returns_the_right_genome() -> None:
    """genome/accession/{accession}/dataset_report. Live-verified 2026-08-05.

    Note the genome report has NO "genome" wrapper key, unlike the gene
    report's {"gene": {...}} wrapper: fields sit directly on the report.
    """
    body = (
        '{"reports":[{"accession":"GCF_000001405.40",'
        '"current_accession":"GCF_000001405.40",'
        '"paired_accession":"GCA_000001405.29",'
        '"assembly_info":{"assembly_level":"Chromosome",'
        '"assembly_name":"GRCh38.p14"},'
        '"assembly_stats":{"total_sequence_length":"3099734149"}}]}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="genome", accession="GCF_000001405.40"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    record = output.records[0]
    assert record.id == "GCF_000001405.40"
    assert record.db == "genome"
    assert record.fields["current_accession"] == "GCF_000001405.40"
    assert record.fields["assembly_info.assembly_level"] == "Chromosome"
    assert record.fields["assembly_info.assembly_name"] == "GRCh38.p14"
    assert record.fields["assembly_stats"] == {"total_sequence_length": "3099734149"}
    assert record.source_url == (
        "https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000001405.40/"
    )
    assert "genome/accession/GCF_000001405.40/dataset_report" in client.calls[0]["url"]


# ===========================================================================
# A 400 classifies as error, by STATUS.
# ===========================================================================


@pytest.mark.asyncio
async def test_malformed_gene_id_400_is_error_with_the_bodys_message() -> None:
    """Live-verified 2026-08-05: a malformed gene_id (wrong argument TYPE,
    not merely a nonexistent one) is the one Datasets v2 path that returns
    a genuine 4xx with the {"error","code","message"} envelope.
    """
    body = (
        '{"error":"Bad Request","code":400,"message":'
        '"Invalid argument type (\'parameter: gene_ids\') provided."}'
    )
    client = _FakeClient([httpx.Response(400, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="notanumber"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert "Invalid argument type" in output.error
    assert not output.records


@pytest.mark.asyncio
async def test_unmatched_symbol_is_empty_not_error_not_ok() -> None:
    """The load-bearing live finding: a well-formed but unmatched symbol
    returns HTTP 200 with a literal empty body `{}`, not a 4xx. This must
    collapse to `empty`. Mirrors premise gate case 10.
    """
    client = _FakeClient([httpx.Response(200, text="{}")])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report",
        report_type="gene",
        symbol="notarealgenesymbolxyzzy",
        taxon="human",
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "empty", (
        f"expected empty (live-verified 200-with-empty-body), got {output.status!r}"
    )
    assert not output.records
    assert output.record_count == 0


@pytest.mark.asyncio
async def test_unmatched_accession_is_empty_not_error() -> None:
    """Same live finding, genome path. Live-verified 2026-08-05."""
    client = _FakeClient([httpx.Response(200, text="{}")])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="genome", accession="GCF_00000000X"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "empty"
    assert not output.records


# ===========================================================================
# Finding 9 (MAJOR, re-review): an unrecognized 2xx shape must fail closed
# as `error`, never be silently collapsed to `empty` the way any 2xx body
# lacking a `reports` key used to be. Only the literal empty body `{}`,
# the one live-verified not-found shape, allowlists to `empty`.
# ===========================================================================


@pytest.mark.asyncio
async def test_unrecognized_2xx_body_without_reports_is_error_not_empty() -> None:
    """A 2xx body that is NOT the live-verified empty `{}` shape and does
    NOT carry a `reports` key: a renamed key, a schema change, or a 2xx
    proxy/error page. Before this fix this was indistinguishable from
    "nothing matched" and silently reported as `empty`. It must fail
    closed as `error` instead.
    """
    client = _FakeClient(
        [httpx.Response(200, text='{"results": [{"gene": {"gene_id": "7157"}}]}')]
    )
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error", (
        f"an unrecognized 2xx shape without a 'reports' key must fail closed as "
        f"'error', not be silently reported as 'empty' (no results), got "
        f"{output.status!r}"
    )
    assert output.error is not None
    assert "reports" in output.error


@pytest.mark.asyncio
async def test_2xx_body_with_extra_unrelated_keys_and_no_reports_is_error() -> None:
    """Same shape of gap, a body carrying OTHER real-looking content
    (not the E-utilities error envelope this module deliberately ignores
    per the mirror-image test below, just an unrelated non-empty
    payload) but still no 'reports' key.
    """
    client = _FakeClient([httpx.Response(200, text='{"status": "processing", "job_id": "42"}')])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="genome", accession="GCF_000001405.40"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None


@pytest.mark.asyncio
async def test_reports_present_but_not_a_list_is_error() -> None:
    """`reports` present but the wrong TYPE (an object instead of a list)
    is just as unrecognized as a missing key, and must not be silently
    treated as zero matches either.
    """
    client = _FakeClient([httpx.Response(200, text='{"reports": {"unexpected": "shape"}}')])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None


@pytest.mark.asyncio
async def test_reports_present_as_an_empty_list_is_still_empty_not_error() -> None:
    """The documented empty-list shape (`{"reports": []}`) is a genuine,
    well-formed zero-match answer, distinct from an unrecognized shape,
    and must still classify `empty`, not `error`.
    """
    client = _FakeClient([httpx.Response(200, text='{"reports": []}')])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="999999999"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "empty"
    assert not output.records


# ===========================================================================
# The mirror-image proof: status decides, not body content.
# ===========================================================================


@pytest.mark.asyncio
async def test_error_shaped_keys_under_a_200_do_not_force_error_status() -> None:
    """The single most important test in this file.

    A body carrying `error`/`code`/`message` keys (the Datasets ERROR
    envelope shape) served under HTTP 200 must NOT be classified `error`.
    The real `reports` array is what decides `ok` here; the stray
    error-shaped keys are simply not inspected, because status decided the
    outer verdict already. This is the opposite of the E-utilities family,
    where an ERROR key under a 200 IS the error signal.
    """
    body = (
        '{"reports":[{"gene":{"gene_id":"7157","symbol":"TP53",'
        '"description":"tumor protein p53"}}],'
        '"error":"this key must be ignored",'
        '"code":400,'
        '"message":"this message must be ignored, status already said 200"}'
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok", (
        f"an error-shaped body under HTTP 200 must still classify ok when "
        f"real records are present, got {output.status!r}: {output.error}"
    )
    assert output.records[0].fields["gene_id"] == "7157"


# ===========================================================================
# Incoherent input combinations: rejected locally, no network call.
# ===========================================================================


@pytest.mark.asyncio
async def test_gene_report_type_with_only_accession_is_rejected_locally() -> None:
    """The ticket's own example of an incoherent combination."""
    client = _FakeClient([])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", accession="GCF_000001405.40"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert output.error is not None
    assert "gene_id" in output.error or "symbol" in output.error
    assert client.calls == [], "an incoherent request must never reach the network"


@pytest.mark.asyncio
async def test_genome_report_type_with_no_accession_is_rejected_locally() -> None:
    client = _FakeClient([])
    action_input = NcbiEfetchDatasetReportInput(action="dataset_report", report_type="genome")

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert "accession" in (output.error or "")
    assert client.calls == []


@pytest.mark.asyncio
async def test_symbol_without_taxon_is_rejected_locally() -> None:
    """symbol alone is not enough; the endpoint needs both symbol and taxon."""
    client = _FakeClient([])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", symbol="TP53"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "error"
    assert client.calls == []


# ===========================================================================
# URL-encoding of a hostile path segment.
# ===========================================================================


@pytest.mark.asyncio
async def test_hostile_symbol_is_url_encoded_not_concatenated_raw() -> None:
    """A symbol carrying a path-breaking character must not alter the request path.

    `/../` in a raw, unencoded path segment could redirect the request to a
    different endpoint entirely. Encoded, it is inert.
    """
    client = _FakeClient([httpx.Response(200, text="{}")])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report",
        report_type="gene",
        symbol="TP53/../../admin",
        taxon="human",
    )

    await ncbi_datasets_actions.dataset_report(action_input, client=client)

    called_url = client.calls[0]["url"]
    assert "/../" not in called_url, f"raw path traversal survived encoding: {called_url!r}"
    assert "%2F" in called_url, f"expected the '/' in the hostile symbol to be percent-encoded, got {called_url!r}"


@pytest.mark.asyncio
async def test_hostile_accession_is_url_encoded() -> None:
    client = _FakeClient([httpx.Response(200, text="{}")])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="genome", accession="GCF/000001405.40"
    )

    await ncbi_datasets_actions.dataset_report(action_input, client=client)

    called_url = client.calls[0]["url"]
    assert "%2F" in called_url
    assert called_url.count("genome/accession/") == 1


# ===========================================================================
# F-3.1-12: per-value character cap on extracted free text.
# ===========================================================================


@pytest.mark.asyncio
async def test_over_long_gene_description_is_capped() -> None:
    """`NcbiEfetchRecord.fields` caps the property COUNT, not any one
    value's length, so an unbounded free-text `description` would otherwise
    flow downstream whole. See `_cap_text` in the module under test.
    """
    body = json.dumps(
        {"reports": [{"gene": {"gene_id": "7157", "symbol": "TP53", "description": "d" * 9000}}]}
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    description = output.records[0].fields["description"]
    assert len(description) < 9000
    assert description.endswith("[truncated]")


@pytest.mark.asyncio
async def test_over_long_string_inside_a_nested_gene_field_is_capped() -> None:
    """The cap walks lists and nested objects, not only top-level strings:
    `synonyms` is a string list and `gene_ontology` is a nested object.
    """
    body = json.dumps(
        {
            "reports": [
                {
                    "gene": {
                        "gene_id": "7157",
                        "synonyms": ["s" * 9000],
                        "gene_ontology": {"molecular_functions": [{"name": "m" * 9000}]},
                    }
                }
            ]
        }
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    fields = output.records[0].fields
    assert fields["synonyms"][0].endswith("[truncated]")
    nested = fields["gene_ontology"]["molecular_functions"][0]["name"]
    assert nested.endswith("[truncated]")


@pytest.mark.asyncio
async def test_over_long_nested_list_is_item_count_capped() -> None:
    """F-3.1-50 (Step 6.2, 2026-08-10): `_cap_field_value` capped every
    string's LENGTH at any depth but never a nested list's item COUNT, so a
    `gene_ontology.biological_processes`-shaped list (real, live-measured
    at 117 items for TP53) reached `output.records[0].fields` uncapped.
    Regression pinned at `_MAX_FIELD_VALUE_ITEMS` (100), mirroring
    `ncbi_eutils_actions._MAX_NESTED_ITEMS`.
    """
    body = json.dumps(
        {
            "reports": [
                {
                    "gene": {
                        "gene_id": "7157",
                        "gene_ontology": {
                            "biological_processes": [{"name": f"process {i}"} for i in range(117)]
                        },
                    }
                }
            ]
        }
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="gene", gene_id="7157"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    processes = output.records[0].fields["gene_ontology"]["biological_processes"]
    assert len(processes) == 100


@pytest.mark.asyncio
async def test_over_long_genome_assembly_name_is_capped() -> None:
    body = json.dumps(
        {
            "reports": [
                {
                    "accession": "GCF_000001405.40",
                    "assembly_info": {
                        "assembly_name": "a" * 9000,
                        "assembly_level": "Chromosome",
                    },
                }
            ]
        }
    )
    client = _FakeClient([httpx.Response(200, text=body)])
    action_input = NcbiEfetchDatasetReportInput(
        action="dataset_report", report_type="genome", accession="GCF_000001405.40"
    )

    output = await ncbi_datasets_actions.dataset_report(action_input, client=client)

    assert output.status == "ok"
    assert output.records[0].fields["assembly_info.assembly_name"].endswith("[truncated]")
    assert output.records[0].fields["assembly_info.assembly_level"] == "Chromosome"
