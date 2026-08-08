"""Unit tests for `ncbi_dbsnp` (T-3.2-04).

No live network anywhere in this file. Every case mocks at the transport
boundary, `ncbi_transport.execute_get`, patched to return a canned
`httpx.Response` or raise a canned `ncbi_transport.TransportError`, the
same `_ScriptedTransport` pattern `test_ncbi_eutils_actions.py` already
established. Live network coverage of the real endpoints is
`test_ncbi_dbsnp_premise.py`'s job, not this file's.

Fixture bodies below are trimmed, hand-shaped copies of the ACTUAL live
responses captured while writing `ncbi_dbsnp.py` (2026-08-08), not
fixtures authored from a reading of documentation: rs334's
`primary_snapshot_data.placements_with_allele` shape, rs3168321's
`merged_snapshot_data.merged_into` shape, and dbSNP ESummary's
`global_mafs`/`clinical_significance`/`fxn_class` shapes all match what
the real endpoints returned, per LEARNINGS.md row 60's discipline.

Covers, per the ticket's explicit requirements:
    - Successful rsid, spdi, and hgvs resolution.
    - global_mafs parsing (F-3.2-01): valid, and a malformed freq string
      failing the WHOLE call closed, plus the genuine live "0." edge case.
    - clinical_significance/fxn_class comma-split (F-3.2-02), including the
      empty-string-becomes-[] edge case.
    - The sequential-ordering property: the ESummary call is keyed on the
      NORMALIZED numeric rsid, never the caller's raw input, proven with a
      scripted transport that would return the WRONG gene if called with
      the raw input's numeric id.
    - The merge-follow trap: a refsnp response with no
      primary_snapshot_data but a merged_snapshot_data.merged_into is
      followed, not treated as an error.
    - Three error paths (404 rsid, 400 SPDI, 400 HGVS) surfacing an
      actionable message from Variation Services' nested
      {"error": {"message": ...}} body shape, never the generic
      "HTTP N with no structured error body" fallback (proving
      ncbi_transport._extract_status_coded_error_message's new third
      branch actually reaches this tool's output).
    - include_clinical=False skips the ESummary call entirely.
    - A transport failure on the clinical fetch, after normalization
      already succeeded, fails the WHOLE call closed rather than returning
      a partial "ok".

Covers, per the judge round 1 fix pass (2026-08-08, tracker/phase_3.2.md):
    - F-3.2-A-01/A-14/J-05: spdi_canonical, the sole remaining whole-call-
      refuse field, still fails the WHOLE call closed on overflow, status
      "error", never silently truncated.
    - F-3.2-A-02/J-03: a bare numeric query (no "rs" prefix) with
      query_type "rsid" is rejected at the schema layer (pydantic
      ValidationError), before any network call.
    - F-3.2-A-03: population_frequencies rows carry allele_role
      ("variant"/"reference"/"other"), attributing each row to
      spdi_canonical's own alleles.
    - F-3.2-A-06: spdi/hgvs resolution returns "empty", not an uncited
      "ok", when no rsid (and therefore no source_url) is available.
    - F-3.2-A-07/J-02: a withdrawn rsid (withdrawn_snapshot_data) is a
      distinct, non-retrying error, and includes withdrawn_time when NCBI
      provides it.

Covers, per the independent re-review of fix round 1 (2026-08-08,
tracker/phase_3.2.md "Independent re-review, fix round 1"):
    - F-3.2-A-15: an over-length string field (clinical_significance item)
      and an over-length list field (clinical_significance list) are now
      WITHHELD (status stays "ok", the field is emptied, its name is
      appended to fields_withheld), never refused (round 1's own fix) and
      never truncated (the original F-3.2-A-01 defect). The rest of a
      genuinely successful fetch, gene linkage, SPDI, other in-cap fields,
      still ships.
    - F-3.2-A-16: a Variation Services 5xx whose message names a specific
      input-shaped problem (a reference-sequence mismatch) is reported as a
      permanent, non-retrying rejection, never round 1's blanket "this is
      transient, retry" claim; a genuinely generic 5xx gets hedged
      "may be transient" language instead of a confident assertion.

Depends on:
    - system_03_search_agent.tools.ncbi_dbsnp (module under test)
    - system_03_search_agent.tools.ncbi_transport, monkeypatched at
      execute_get
    - system_03_search_agent.tools.ncbi_dbsnp_schemas, for constructing
      valid inputs
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pydantic
import pytest

from system_03_search_agent.tools import ncbi_dbsnp as ncbi_dbsnp_module
from system_03_search_agent.tools.ncbi_dbsnp import ncbi_dbsnp
from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpInput


def _json_response(body: dict[str, Any], *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


class _ScriptedTransport:
    """Replaces ncbi_transport.execute_get with a scripted sequence of responses.

    Each entry is either an httpx.Response (returned) or an Exception
    (raised), popped in call order. Records every call's URL so a test can
    assert not just what came back, but which id each call was actually
    keyed on (the sequential-ordering property this module exists to get
    right).
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
    monkeypatch.setattr(ncbi_dbsnp_module.ncbi_transport, "execute_get", scripted)
    return scripted


# ---------------------------------------------------------------------------
# Fixture bodies: trimmed, live-shaped copies of real responses (see module
# docstring). Only the fields ncbi_dbsnp.py actually reads are kept.
# ---------------------------------------------------------------------------


def _refsnp_body(
    refsnp_id: str = "334",
    *,
    seq_id: str = "NC_000011.10",
    position: int = 5227001,
    ref: str = "T",
    alts: tuple[str, ...] = ("A", "C", "G"),
) -> dict[str, Any]:
    alleles = [
        {
            "allele": {"spdi": {"seq_id": seq_id, "position": position, "deleted_sequence": ref, "inserted_sequence": ref}},
            "hgvs": f"{seq_id}:g.{position + 1}=",
        }
    ]
    for alt in alts:
        alleles.append(
            {
                "allele": {"spdi": {"seq_id": seq_id, "position": position, "deleted_sequence": ref, "inserted_sequence": alt}},
                "hgvs": f"{seq_id}:g.{position + 1}{ref}>{alt}",
            }
        )
    return {
        "refsnp_id": refsnp_id,
        "primary_snapshot_data": {
            "placements_with_allele": [
                {"seq_id": seq_id, "is_ptlp": True, "alleles": alleles},
                {"seq_id": "NC_000011.9", "is_ptlp": False, "alleles": alleles},
            ]
        },
    }


def _merged_refsnp_body(merged_into: str) -> dict[str, Any]:
    return {
        "refsnp_id": "3168321",
        "create_date": "2002-05-29T11:21Z",
        "merged_snapshot_data": {"merged_into": [merged_into]},
    }


def _esummary_body(
    numeric_id: str,
    *,
    gene_name: str = "HBB",
    gene_id: str = "3043",
    global_mafs: list[dict[str, str]] | None = None,
    clinical_significance: str = "not-provided,protective,likely-benign,pathogenic,other",
    fxn_class: str = "coding_sequence_variant,missense_variant",
    chrpos: str = "11:5227002",
) -> dict[str, Any]:
    if global_mafs is None:
        global_mafs = [{"study": "1000Genomes", "freq": "A=0.027356/137"}]
    return {
        "header": {"type": "esummary", "version": "0.3"},
        "result": {
            "uids": [numeric_id],
            numeric_id: {
                "uid": numeric_id,
                "snp_id": int(numeric_id),
                "global_mafs": global_mafs,
                "clinical_significance": clinical_significance,
                "genes": [{"name": gene_name, "gene_id": gene_id}],
                "acc": "NC_000011.10",
                "chr": "11",
                "spdi": "NC_000011.10:5227001:T:A,NC_000011.10:5227001:T:C",
                "fxn_class": fxn_class,
                "chrpos": chrpos,
            },
        },
    }


def _rsid_input(query: str, *, include_clinical: bool = True) -> NcbiDbsnpInput:
    return NcbiDbsnpInput.model_validate(
        {"query": query, "query_type": "rsid", "include_clinical": include_clinical}
    )


def _spdi_input(query: str, *, include_clinical: bool = True) -> NcbiDbsnpInput:
    return NcbiDbsnpInput.model_validate(
        {"query": query, "query_type": "spdi", "include_clinical": include_clinical}
    )


def _hgvs_input(query: str, *, include_clinical: bool = True) -> NcbiDbsnpInput:
    return NcbiDbsnpInput.model_validate(
        {"query": query, "query_type": "hgvs", "include_clinical": include_clinical}
    )


# ---------------------------------------------------------------------------
# Happy path: rsid, spdi, hgvs.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rsid_resolves_with_clinical_and_population_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [_json_response(_refsnp_body()), _json_response(_esummary_body("334"))],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.rsid == "rs334"
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"
    assert "T" in output.alleles and "A" in output.alleles
    gene_names = [g.name for g in output.genes]
    assert "HBB" in gene_names
    assert output.source_url == "https://www.ncbi.nlm.nih.gov/snp/rs334"

    entry = next(p for p in output.population_frequencies if p.population == "1000Genomes")
    assert entry.allele == "A"
    assert entry.frequency == pytest.approx(0.027356, abs=1e-6)


@pytest.mark.asyncio
async def test_spdi_resolves_via_contextual_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _install(
        monkeypatch,
        [
            _json_response(
                {
                    "data": {
                        "seq_id": "NC_000011.10",
                        "position": 5227001,
                        "deleted_sequence": "T",
                        "inserted_sequence": "A",
                    }
                }
            )
        ],
    )

    output = await ncbi_dbsnp(_spdi_input("NC_000011.10:5227001:T:A"))

    # F-3.2-A-06: normalization succeeded, but a query_type="spdi" query
    # never resolves an rsid, so there is nothing citable. "empty", not a
    # permanent uncited "ok", per production-standards.md's grounding gate.
    assert output.status == "empty", output.error
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"
    assert output.rsid == ""
    assert output.source_url is None
    assert output.error, "an empty status must still explain why there is nothing to cite"
    # The spec names canonical_representative; this tool deliberately calls
    # /contextual instead (see ncbi_dbsnp.py's module docstring, trap 1).
    assert len(scripted.calls) == 1
    assert scripted.calls[0]["url"].endswith("/contextual")
    assert "canonical_representative" not in scripted.calls[0]["url"]


@pytest.mark.asyncio
async def test_hgvs_resolves_via_contextuals_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _install(
        monkeypatch,
        [
            _json_response(
                {
                    "data": {
                        "spdis": [
                            {
                                "seq_id": "NM_000518.5",
                                "position": 69,
                                "deleted_sequence": "A",
                                "inserted_sequence": "T",
                            }
                        ],
                        "input_hgvs_validity": "valid",
                    }
                }
            )
        ],
    )

    output = await ncbi_dbsnp(_hgvs_input("NM_000518.5:c.20A>T"))

    # F-3.2-A-06: same reasoning as the spdi case above. query_type="hgvs"
    # never resolves an rsid either.
    assert output.status == "empty", output.error
    assert output.spdi_canonical == "NM_000518.5:69:A:T"
    assert output.source_url is None
    assert output.error, "an empty status must still explain why there is nothing to cite"
    # Section 6.3's percent-encoding requirement: '>' (and, live-confirmed,
    # ':') must not reach the URL unencoded.
    assert ">" not in scripted.calls[0]["url"]
    assert "%3E" in scripted.calls[0]["url"]


@pytest.mark.asyncio
async def test_include_clinical_false_skips_esummary_call(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _install(monkeypatch, [_json_response(_refsnp_body())])

    output = await ncbi_dbsnp(_rsid_input("rs334", include_clinical=False))

    assert output.status == "ok", output.error
    assert output.rsid == "rs334"
    assert output.genes == []
    assert output.population_frequencies == []
    assert len(scripted.calls) == 1, "ESummary must not be called when include_clinical is False"


# ---------------------------------------------------------------------------
# F-3.2-01: global_mafs parsing.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_global_mafs_malformed_freq_fails_the_whole_call_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(
                _esummary_body("334", global_mafs=[{"study": "Bogus", "freq": "not-a-freq-string"}])
            ),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "error"
    assert "F-3.2-01" in output.error
    # The successfully normalized values are still carried, not blanked.
    assert output.rsid == "rs334"
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"


@pytest.mark.asyncio
async def test_global_mafs_bare_trailing_decimal_point_is_valid_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live-confirmed on rs334 itself: PRJEB36033's freq is "A=0./0", a
    genuine zero with no digits after the decimal point, not malformed.
    """
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(
                _esummary_body(
                    "334",
                    global_mafs=[
                        {"study": "1000Genomes", "freq": "A=0.027356/137"},
                        {"study": "PRJEB36033", "freq": "A=0./0"},
                    ],
                )
            ),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    zero_entry = next(p for p in output.population_frequencies if p.population == "PRJEB36033")
    assert zero_entry.frequency == pytest.approx(0.0)
    assert zero_entry.allele == "A"


@pytest.mark.asyncio
async def test_global_mafs_empty_list_is_ok_not_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        [_json_response(_refsnp_body()), _json_response(_esummary_body("334", global_mafs=[]))],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.population_frequencies == []


# ---------------------------------------------------------------------------
# F-3.2-02: clinical_significance / fxn_class comma-split.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clinical_significance_and_fxn_class_are_split(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        [_json_response(_refsnp_body()), _json_response(_esummary_body("334"))],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.clinical_significance == [
        "not-provided", "protective", "likely-benign", "pathogenic", "other",
    ]
    assert output.functional_consequence == ["coding_sequence_variant", "missense_variant"]


@pytest.mark.asyncio
async def test_empty_clinical_significance_string_becomes_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(_esummary_body("334", clinical_significance="", fxn_class="")),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.clinical_significance == []
    assert output.functional_consequence == []


# ---------------------------------------------------------------------------
# The sequential-ordering property, mocked: the ESummary call must be keyed
# on the NORMALIZED numeric rsid, never the caller's raw input.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_esummary_call_is_keyed_on_the_normalized_id_not_the_raw_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rs3168321 merged into rs334 (mirrors the premise gate's live case 8).

    A tool keyed on the RAW input would call ESummary with id=3168321. This
    scripted transport only has a correct response for id=334 queued
    second; if `ncbi_dbsnp` ever called ESummary with "3168321" the params
    assertion below would fail, proving the ordering property directly
    rather than merely asserting the final output looks right by luck.
    """
    scripted = _install(
        monkeypatch,
        [
            _json_response(_merged_refsnp_body("334")),
            _json_response(_refsnp_body("334")),
            _json_response(_esummary_body("334")),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs3168321"))

    assert output.status == "ok", output.error
    assert output.rsid == "rs334", (
        "expected the CANONICAL id rs334 (proving normalize-before-fetch ran), "
        f"got {output.rsid!r}"
    )
    esummary_call = scripted.calls[-1]
    assert esummary_call["params"]["id"] == "334", (
        f"ESummary must be keyed on the normalized id '334', not the raw "
        f"input '3168321'; got params {esummary_call['params']!r}"
    )


@pytest.mark.asyncio
async def test_merge_chain_exceeding_the_hop_limit_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pathological/circular merge chain must not loop forever."""
    _install(
        monkeypatch,
        [
            _json_response(_merged_refsnp_body("2")),
            _json_response(_merged_refsnp_body("3")),
            _json_response(_merged_refsnp_body("4")),
            _json_response(_merged_refsnp_body("5")),
            _json_response(_merged_refsnp_body("6")),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs1"))

    assert output.status == "error"
    assert "merge chain" in output.error


# ---------------------------------------------------------------------------
# Error paths: 404 rsid, 400 SPDI, 400 HGVS. Actionable, not the generic
# fallback ("HTTP N with no structured error body"), proving
# ncbi_transport._extract_status_coded_error_message's new nested-{"error":
# {"message": ...}} branch actually reaches this tool's output.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_rsid_is_error_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [_json_response({"error": {"code": 404, "message": "RefSNP not found"}}, status_code=404)],
    )

    output = await ncbi_dbsnp(_rsid_input("rs999999999999"))

    assert output.status == "error"
    assert "RefSNP not found" in output.error
    assert "no structured error body" not in output.error


@pytest.mark.asyncio
async def test_malformed_spdi_is_error_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [
            _json_response(
                {"error": {"code": 400, "message": "Invalid SPDI: 'not-a-real-spdi'"}},
                status_code=400,
            )
        ],
    )

    output = await ncbi_dbsnp(_spdi_input("not-a-real-spdi"))

    assert output.status == "error"
    assert "Invalid SPDI" in output.error
    assert "no structured error body" not in output.error


@pytest.mark.asyncio
async def test_malformed_hgvs_is_error_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [_json_response({"error": {"code": 400, "message": "Invalid HGVS expression"}}, status_code=400)],
    )

    output = await ncbi_dbsnp(_hgvs_input("not-real-hgvs"))

    assert output.status == "error"
    assert "Invalid HGVS expression" in output.error
    assert "no structured error body" not in output.error


# ---------------------------------------------------------------------------
# Partial-failure behavior: normalization succeeds, clinical fetch fails.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_esummary_transport_failure_fails_the_whole_call_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            ncbi_dbsnp_module.ncbi_transport.TransportTimeoutError(
                "eutils.ncbi.nlm.nih.gov timed out after 15.0s"
            ),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "error"
    assert "rs334" in output.error
    # The successfully normalized values are still carried on the error.
    assert output.rsid == "rs334"
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"


@pytest.mark.asyncio
async def test_variation_services_transport_failure_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [ncbi_dbsnp_module.ncbi_transport.TransportConnectionError("api.ncbi.nlm.nih.gov connection failed")],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "error"
    assert output.rsid == "rs334"
    assert output.error


# ---------------------------------------------------------------------------
# F-3.2-A-01/A-14/J-05, revised by F-3.2-A-15 (round 2): WITHHOLD, don't
# truncate and don't refuse the whole call, when a value assembled from
# live upstream content on the success path would need it to fit its
# schema cap. Only spdi_canonical itself still refuses the whole call.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overlength_clinical_significance_item_is_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A string-field cap: one clinical_significance term over 40 chars.

    Round 1's OLD `_cap()` would have truncated
    "conflicting-interpretations-of-pathogenic" (42 chars) into
    "conflicting-interpretations-of-pathogeni" (40 chars), a DIFFERENT real
    term, and shipped it under status "ok" (the original F-3.2-A-01 live
    repro). Round 1's own fix then refused the WHOLE call instead, which
    F-3.2-A-15 measured to discard an otherwise fully successful fetch for
    ~10.4 percent of real clinically-cited variants. The current behavior
    withholds only clinical_significance and ships everything else.
    """
    overlong_term = "conflicting-interpretations-of-pathogenic"
    assert len(overlong_term) > 40, "fixture must actually exceed the cap to test anything"
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(_esummary_body("334", clinical_significance=overlong_term)),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.clinical_significance == [], (
        "an over-length item must never appear, truncated or otherwise"
    )
    assert output.fields_withheld == ["clinical_significance"]
    # The rest of the genuinely successful fetch still ships.
    assert output.rsid == "rs334"
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"
    assert output.source_url == "https://www.ncbi.nlm.nih.gov/snp/rs334"
    assert any(g.name == "HBB" for g in output.genes)
    assert output.population_frequencies, "population data must not be discarded either"


@pytest.mark.asyncio
async def test_overlength_clinical_significance_list_is_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A list-field cap: 11 distinct clinical_significance entries, cap is 10.

    Live-reconfirmed on the real rs429358 (11 real entries, including a
    44-char item, the exact shape F-3.2-A-15's independent re-review
    measured across a live 800-record sample). The current behavior
    withholds the list and ships everything else under status "ok".
    """
    eleven_terms = ",".join(f"term-{i}" for i in range(11))
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(_esummary_body("334", clinical_significance=eleven_terms)),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.clinical_significance == []
    assert output.fields_withheld == ["clinical_significance"]
    assert output.rsid == "rs334"
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"


@pytest.mark.asyncio
async def test_overlength_spdi_canonical_fails_closed_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spdi_canonical itself, computed from a real (if pathological) large insertion.

    F-3.2-A-01's own live repro: a 150bp insertion truncated into a
    syntactically valid but WRONG 128bp one naming a different variant.
    spdi_canonical is the ONE field F-3.2-A-15 (round 2) deliberately did
    NOT convert to withhold-with-signal: without a citable spdi_canonical
    there is no variant identity left to attach any other field to, so this
    is still a whole-call refusal, unchanged from round 1.
    """
    huge_insertion = "A" * 130
    _install(monkeypatch, [_json_response(_refsnp_body(alts=(huge_insertion,)))])

    output = await ncbi_dbsnp(_rsid_input("rs334", include_clinical=False))

    assert output.status == "error"
    assert "spdi_canonical" in output.error
    # The over-length value must never appear, truncated or otherwise, on a
    # status "ok"/ "error" response's spdi_canonical field.
    assert output.spdi_canonical == ""
    assert output.fields_withheld == [], "spdi_canonical overflow refuses the call, never withholds"


@pytest.mark.asyncio
async def test_overlength_alleles_are_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """alleles list-length cap: more than 10 distinct alleles at one position.

    spdi_canonical itself stays well within its own cap here (only the
    variant allele is long-ish), but the alleles LIST collects 11 distinct
    sequences, one per alt plus the reference, exceeding _MAX_ALLELES (10).
    """
    many_alts = tuple(f"A{i}" for i in range(11))
    _install(monkeypatch, [_json_response(_refsnp_body(alts=many_alts))])

    output = await ncbi_dbsnp(_rsid_input("rs334", include_clinical=False))

    assert output.status == "ok", output.error
    assert output.alleles == []
    assert output.fields_withheld == ["alleles"]
    # spdi_canonical names the FIRST alt (A0), well within its own cap, and
    # must still ship: only the alleles collection overflowed.
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A0"


@pytest.mark.asyncio
async def test_overlength_population_frequencies_are_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """population_frequencies item cap: one allele over 10 chars.

    A malformed freq string (F-3.2-01) still fails the whole call closed,
    unchanged; this is the DIFFERENT, cap-overflow condition, which must
    now withhold instead.
    """
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(
                _esummary_body(
                    "334",
                    global_mafs=[{"study": "1000Genomes", "freq": "AAAAAAAAAAAA=0.01/10"}],
                )
            ),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.population_frequencies == []
    assert output.fields_withheld == ["population_frequencies"]
    # Everything else still ships.
    assert output.clinical_significance
    assert any(g.name == "HBB" for g in output.genes)


@pytest.mark.asyncio
async def test_overlength_gene_name_is_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """genes item cap: one gene name over 30 chars."""
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(_esummary_body("334", gene_name="A" * 31)),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.genes == []
    assert output.fields_withheld == ["genes"]
    # Everything else still ships.
    assert output.clinical_significance
    assert output.population_frequencies


@pytest.mark.asyncio
async def test_overlength_chrpos_is_withheld_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chrpos cap: over 30 chars."""
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(_esummary_body("334", chrpos="1" * 31)),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.chrpos is None
    assert output.fields_withheld == ["chrpos"]
    assert output.clinical_significance


@pytest.mark.asyncio
async def test_fields_withheld_is_empty_when_nothing_overflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal happy path must never populate fields_withheld."""
    _install(
        monkeypatch,
        [_json_response(_refsnp_body()), _json_response(_esummary_body("334"))],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.fields_withheld == []


# ---------------------------------------------------------------------------
# F-3.2-A-02/J-03: a bare numeric query with query_type "rsid" is rejected
# at the schema layer, before any network call.
# ---------------------------------------------------------------------------


def test_bare_numeric_rsid_is_rejected_by_the_schema() -> None:
    """The exact live repro: HBB's own Gene ID ("3043") sent as an rsid.

    Without this fix, refsnp/3043 is a genuine 200 for a real but UNRELATED
    ALDH1B1 variant: the fabricated-citation shape this system exists to
    prevent, reached with no malformed input at all (F-3.2-A-02).
    """
    with pytest.raises(pydantic.ValidationError) as exc_info:
        NcbiDbsnpInput.model_validate({"query": "3043", "query_type": "rsid"})
    assert "rs" in str(exc_info.value).lower()


def test_rs_prefixed_rsid_still_validates() -> None:
    """The narrowing must not reject genuinely well-formed rsid input."""
    validated = NcbiDbsnpInput.model_validate({"query": "rs3043", "query_type": "rsid"})
    assert validated.query == "rs3043"


def test_bare_numeric_query_still_validates_for_spdi_and_hgvs() -> None:
    """The rsid-only carve-out must not spill over into the other two query types."""
    spdi_validated = NcbiDbsnpInput.model_validate(
        {"query": "NC_000011.10:5227001:T:A", "query_type": "spdi"}
    )
    assert spdi_validated.query_type == "spdi"


# ---------------------------------------------------------------------------
# F-3.2-A-03: population_frequencies rows are attributed back to
# spdi_canonical's own alleles.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_population_frequency_allele_role_distinguishes_variant_reference_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rs334's own reference (T) and variant (A) alleles, plus a third
    allele (C) at the same multiallelic position that spdi_canonical does
    NOT name, must be labeled distinctly.
    """
    _install(
        monkeypatch,
        [
            _json_response(_refsnp_body()),
            _json_response(
                _esummary_body(
                    "334",
                    global_mafs=[
                        {"study": "SGDP_PRJ", "freq": "T=0.5/10"},
                        {"study": "1000Genomes", "freq": "A=0.027356/137"},
                        {"study": "TOPMED", "freq": "C=0.001/500"},
                    ],
                )
            ),
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "ok", output.error
    assert output.spdi_canonical == "NC_000011.10:5227001:T:A"
    roles = {p.population: p.allele_role for p in output.population_frequencies}
    assert roles["SGDP_PRJ"] == "reference", (
        f"the reference allele T's frequency must be labeled 'reference', "
        f"got {roles!r}"
    )
    assert roles["1000Genomes"] == "variant", (
        f"the variant allele A's frequency (the one spdi_canonical names) "
        f"must be labeled 'variant', got {roles!r}"
    )
    assert roles["TOPMED"] == "other", (
        f"a third allele C, present at the locus but not the one "
        f"spdi_canonical names, must be labeled 'other', got {roles!r}"
    )


# ---------------------------------------------------------------------------
# F-3.2-A-07/J-02: a withdrawn rsid is a distinct, non-retrying error.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_withdrawn_rsid_is_a_distinct_non_retrying_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live-shaped fixture (rs100, confirmed live 2026-08-08): a refsnp
    response with `withdrawn_snapshot_data` and no `primary_snapshot_data`.
    """
    _install(
        monkeypatch,
        [
            _json_response(
                {
                    "refsnp_id": "100",
                    "create_date": "2000-09-19T17:02Z",
                    "withdrawn_snapshot_data": {
                        "withdrawn_time": "2016-06-17T16:22Z",
                        "support": [],
                    },
                }
            )
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs100"))

    assert output.status == "error"
    assert "withdrawn" in output.error.lower()
    assert "2016-06-17T16:22Z" in output.error, (
        f"expected the live withdrawn_time surfaced in the message, got "
        f"{output.error!r}"
    )
    assert "retry" not in output.error.lower() or "do not retry" in output.error.lower()


# ---------------------------------------------------------------------------
# F-3.2-A-08/J-02, revised by F-3.2-A-16: retry guidance matches what the
# HTTP status, and for a 5xx, the reason text itself, actually means. A 429
# is unambiguous and always transient. A 5xx is NOT unambiguous: it can
# also be a permanent, deterministic input error wearing a 5xx status
# (live-reproduced: a reference-sequence mismatch), so a 5xx whose message
# names a specific input-shaped problem is reported as non-retrying, and a
# genuinely generic 5xx is hedged rather than confidently claimed transient.
# A 404/400 is never worth retrying, unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generic_5xx_hedges_the_transient_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5xx with no input-shaped language in its message: retry is REASONABLE, not asserted as fact.

    Round 1 asserted "This is a transient, server-side condition, not a bad
    request" as settled fact for ANY 5xx. F-3.2-A-16 live-reproduced that
    claim false for at least one real 5xx shape (see the next test), so a
    generic 5xx now gets hedged language instead of a confident claim.
    """
    _install(
        monkeypatch,
        [
            _json_response(
                {"error": {"code": 503, "message": "Service Unavailable"}}, status_code=503
            )
        ],
    )

    output = await ncbi_dbsnp(_rsid_input("rs999999999999"))

    assert output.status == "error"
    assert "Service Unavailable" in output.error
    assert "retrying after a backoff is reasonable" in output.error.lower()
    assert "may be a transient" in output.error.lower()
    # The old, now-disproven confident claim must not appear.
    assert "this is a transient, server-side condition, not a bad request" not in output.error.lower()
    assert "will not help" not in output.error.lower()


@pytest.mark.asyncio
async def test_5xx_reference_mismatch_is_a_permanent_input_error_not_a_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real, live-reproduced F-3.2-A-16 repro: a reference-mismatch SPDI 500s.

    Live body, captured against the real endpoint 2026-08-08:
    `NC_000011.10:5227000:AT:AA` (the true reference at that position is
    CT, not AT) returns HTTP 500 with a message describing the mismatch,
    not a real server-side failure. This is a deterministic, PERMANENT
    client input error; retrying it can never succeed, and doing so wastes
    a call against Variation Services' roughly 1 req/s pool.
    """
    _install(
        monkeypatch,
        [
            _json_response(
                {
                    "error": {
                        "code": 500,
                        "message": (
                            "The reference sequence for 'NC_000011.10' at position "
                            "'5227000' ('CT'), is not equal to variant's asserted "
                            "reference ('AT')"
                        ),
                    }
                },
                status_code=500,
            )
        ],
    )

    output = await ncbi_dbsnp(_spdi_input("NC_000011.10:5227000:AT:AA"))

    assert output.status == "error"
    assert "reference sequence" in output.error.lower()
    assert "permanent" in output.error.lower()
    assert "will not help" in output.error.lower()
    # Must NOT claim this is transient or encourage a retry.
    assert "retrying after a backoff is reasonable" not in output.error.lower()
    assert "may be a transient" not in output.error.lower()


@pytest.mark.asyncio
async def test_429_error_message_still_encourages_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 is NCBI's own unambiguous rate-limit signal; always transient, unchanged by F-3.2-A-16."""
    _install(
        monkeypatch,
        [_json_response({"error": {"code": 429, "message": "Too Many Requests"}}, status_code=429)],
    )

    output = await ncbi_dbsnp(_rsid_input("rs999999999999"))

    assert output.status == "error"
    assert "Too Many Requests" in output.error
    assert "retry after a backoff" in output.error.lower()
    assert "rate-limit" in output.error.lower()


@pytest.mark.asyncio
async def test_404_error_message_does_not_encourage_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        [_json_response({"error": {"code": 404, "message": "RefSNP not found"}}, status_code=404)],
    )

    output = await ncbi_dbsnp(_rsid_input("rs999999999999"))

    assert output.status == "error"
    assert "RefSNP not found" in output.error
    assert "will not help" in output.error.lower()
    assert "retry after a backoff" not in output.error.lower()


# ---------------------------------------------------------------------------
# Never raises, even on a genuinely unexpected exception.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_exception_is_caught_and_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(*args: Any, **kwargs: Any) -> httpx.Response:
        raise KeyError("boom")

    monkeypatch.setattr(ncbi_dbsnp_module.ncbi_transport, "execute_get", _boom)

    output = await ncbi_dbsnp(_rsid_input("rs334"))

    assert output.status == "error"
    assert "KeyError" in output.error
