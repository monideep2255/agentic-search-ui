"""Unit tests for `ncbi_coordinate_overlap`, the dbVar/ClinVar five-step
placement procedure (T-3.1-10).

No live network anywhere in this file. Every case mocks at the HTTP client
boundary, the same `_FakeClient` pattern `test_ncbi_transport.py` uses, or
monkeypatches `execute_get` directly to exercise this module's own
rate-limit/timeout/connection-error handling without reproducing the
transport layer's retry machinery. Live-network coverage of the real
endpoints, including the exact proven-bug fixture this module's docstring
describes, is `test_ncbi_efetch_premise.py` cases 17 and 18, not this
file's job.

What this file proves, per the ticket's explicit requirements:

    - A candidate whose resolved placement fails the overlap predicate is
      dropped (test_candidate_failing_predicate_is_dropped_from_a_mixed_batch,
      test_exact_proven_bug_shape_is_rejected).
    - A candidate with no placement at all for the requested assembly is
      dropped, never given a guessed placement
      (test_candidate_with_no_placement_for_requested_assembly_is_dropped).
    - The exact GRCh37-start-paired-with-GRCh38-end shape from the proven
      live bug is rejected (test_exact_proven_bug_shape_is_rejected).
    - The predicate's boundary conditions: touching intervals on both
      edges, a placement fully contained in the window, a window fully
      contained in the placement, and a 0bp point insertion exactly on a
      boundary (the "touching" tests and
      test_zero_bp_insertion_exactly_on_window_boundary_overlaps).

Also covered, because the module's own docstring makes claims this file
must test rather than merely document (self-eval-loop's "a comment that
claims a property is a claim to be tested"):

    - ClinVar's actual live-verified field shape
      (`variation_set[].variation_loc[]`), not the flat C37/CPOS scalars
      Section 6.2 describes.
    - The assembly-match is a prefix match (`GRCh38.p12` matches a
      `GRCh38` request), not an exact match.
    - A candidate with two placements for the SAME assembly is kept if
      EITHER one overlaps.
    - Exactly one ESearch call and one BATCHED ESummary call per
      invocation, never one ESummary call per candidate.
    - `truncated`/`total_available` are set honestly when ESearch's
      `count` exceeds the number of ids actually returned.
    - The correct Entrez field tags per db (`CH`/`BASE`/`ASSM` for dbVar,
      `CHR`/`C37`/`CPOS` for ClinVar), read off the captured request URL.
    - Rate-limit, timeout, and connection failures on either the ESearch
      or the ESummary call produce an actionable `error` output rather
      than propagating an exception.
    - A record that fails output-schema validation is dropped with a
      logged warning rather than crashing the whole batch.

Depends on:
    - system_03_search_agent.tools.ncbi_coordinate_overlap (the module
      under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchCoordinateOverlapInput)
    - system_03_search_agent.tools.ncbi_transport (TransportRateLimitedError,
      TransportTimeoutError, TransportConnectionError, for the error-path
      tests)
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_coordinate_overlap, ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchCoordinateOverlapInput

# ---------------------------------------------------------------------------
# Shared fixtures and helpers.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch):
    """Fresh rate-limiter state and clean NCBI_* env vars for every test.

    Mirrors test_ncbi_transport.py's own fixture. The rate limiter is
    process-global state (`ncbi_transport._rate_limiters`), so a test in
    this file left unreset could see a saturated pool from an unrelated
    test run earlier in the same session.
    """
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EUTILS_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


class _FakeClient:
    """Scripted `httpx.AsyncClient.get` stand-in. Same shape as
    test_ncbi_transport.py's `_FakeClient`, duplicated locally rather than
    imported, since it is test-only fixture code and this module's ticket
    scopes edits to this file plus the module under test.
    """

    def __init__(self, items: list[httpx.Response | Exception]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
        self.calls.append({"url": url, "timeout": timeout})
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _input(*, db: str = "dbvar", chromosome: str = "1", start: int = 1_000_000,
           end: int = 1_100_000, assembly: str = "GRCh38") -> NcbiEfetchCoordinateOverlapInput:
    validated = NcbiEfetchCoordinateOverlapInput.model_validate(
        {
            "action": "coordinate_overlap",
            "db": db,
            "chromosome": chromosome,
            "start": start,
            "end": end,
            "assembly": assembly,
        }
    )
    return validated


def _esearch_response(*, count: int, ids: list[str]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "header": {"type": "esearch", "version": "0.3"},
            "esearchresult": {
                "count": str(count),
                "retmax": str(len(ids)),
                "retstart": "0",
                "idlist": ids,
            },
        },
    )


def _esearch_empty_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "header": {"type": "esearch", "version": "0.3"},
            "esearchresult": {"count": "0", "retmax": "0", "retstart": "0", "idlist": []},
        },
    )


def _esearch_error_response(message: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "header": {"type": "esearch", "version": "0.3"},
            "esearchresult": {"ERROR": message, "count": "0"},
        },
    )


def _dbvar_record(
    *,
    uid: str,
    sv: str,
    placements: list[tuple[int, int, str]] | list[tuple[int, int, str, str]],
    variant_type: str = "copy number variation",
    gene_name: str | None = None,
) -> dict[str, Any]:
    """One dbVar ESummary record. `placements` is `(chr_start, chr_end, assembly)`,
    or `(chr_start, chr_end, assembly, chromosome)` when a test needs a
    placement on a chromosome other than the "1" default (Finding 1's
    cross-chromosome and multi-placement cases).

    Shape verified live 2026-08-05 against real dbVar ESummary responses;
    see the module docstring for the exact records this mirrors.
    """
    entries = []
    for placement in placements:
        start, end, assembly = placement[0], placement[1], placement[2]
        chromosome = placement[3] if len(placement) > 3 else "1"
        entries.append({"chr": chromosome, "chr_start": start, "chr_end": end, "assembly": assembly})
    return {
        "uid": uid,
        "sv": sv,
        "dbvarplacementlist": entries,
        "dbvarvarianttypelist": [variant_type],
        "dbvargenelist": [{"id": 1, "name": gene_name}] if gene_name else [],
    }


def _dbvar_esummary_response(records: dict[str, dict[str, Any]]) -> httpx.Response:
    result = {"uids": list(records.keys())}
    result.update(records)
    return httpx.Response(200, json={"header": {"type": "esummary"}, "result": result})


def _clinvar_record(
    *,
    uid: str,
    accession: str,
    title: str,
    placements: list[tuple[int, int, str]],
    gene_symbol: str | None = None,
) -> dict[str, Any]:
    """One ClinVar ESummary record, in its ACTUAL live-verified shape:
    `variation_set[].variation_loc[]`, not the flat `C37`/`CPOS` scalars
    Section 6.2 describes. See the module docstring for the live record
    this mirrors (uid 4865884, TP53 c.1035T>C, verified 2026-08-05).
    """
    return {
        "uid": uid,
        "accession": accession,
        "title": title,
        "variation_set": [
            {
                "variation_loc": [
                    {"assembly_name": assembly, "chr": "17", "start": str(start), "stop": str(end)}
                    for start, end, assembly in placements
                ],
            }
        ],
        "genes": [{"symbol": gene_symbol}] if gene_symbol else [],
        "germline_classification": {"description": "Likely benign"},
    }


def _clinvar_esummary_response(records: dict[str, dict[str, Any]]) -> httpx.Response:
    result = {"uids": list(records.keys())}
    result.update(records)
    return httpx.Response(200, json={"header": {"type": "esummary"}, "result": result})


def _query_of(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}


# ===========================================================================
# The core predicate: overlap kept, non-overlap dropped, missing placement
# dropped. This is the module's entire reason for existing.
# ===========================================================================


@pytest.mark.asyncio
async def test_candidate_with_genuine_overlap_is_returned_ok() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["57691674"]),
            _dbvar_esummary_response(
                {
                    "57691674": _dbvar_record(
                        uid="57691674",
                        sv="nsv7850635",
                        placements=[(1_056_628, 1_056_713, "GRCh38")],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    assert output.record_count == 1
    record = output.records[0]
    assert record.id == "nsv7850635"
    assert record.fields["chr_start"] == 1_056_628
    assert record.fields["chr_end"] == 1_056_713
    assert record.fields["assembly"] == "GRCh38"
    assert record.source_url == "https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv7850635/"


@pytest.mark.asyncio
async def test_candidate_failing_predicate_is_dropped_from_a_mixed_batch() -> None:
    """A batch with one genuine overlap and one candidate whose resolved
    placement does not overlap: the survivor is kept, the failure is
    dropped, and the output status reflects the survivor, never the
    failure.
    """
    client = _FakeClient(
        [
            _esearch_response(count=2, ids=["57691674", "57696443"]),
            _dbvar_esummary_response(
                {
                    "57691674": _dbvar_record(
                        uid="57691674",
                        sv="nsv7850635",
                        placements=[(1_056_628, 1_056_713, "GRCh38")],
                    ),
                    "57696443": _dbvar_record(
                        uid="57696443",
                        sv="nsv7855404",
                        # GRCh38 placement is 50kb outside the window; the
                        # GRCh37 placement (which is why ESearch matched
                        # this candidate at all) is irrelevant to a GRCh38
                        # request.
                        placements=[
                            (1_149_604, 1_149_683, "GRCh38"),
                            (1_084_984, 1_085_063, "GRCh37.p13"),
                        ],
                    ),
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    ids = {r.id for r in output.records}
    assert ids == {"nsv7850635"}, (
        f"nsv7855404's GRCh38 placement does not overlap the window and must be "
        f"dropped, got {ids!r}"
    )


@pytest.mark.asyncio
async def test_exact_proven_bug_shape_is_rejected() -> None:
    """The capability sheet's exact bug, reproduced: a candidate whose
    GRCh37 unplaced-scaffold-style start falls inside the window and whose
    GRCh38 end also happens to sit outside it, a 0bp point insertion on
    both assemblies. If step 4 is skipped, this candidate is a false
    positive. This is a standalone version of the batch case above,
    isolating the ONE dangerous candidate with nothing else in the batch
    to accidentally save the assertion.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["57735186"]),
            _dbvar_esummary_response(
                {
                    "57735186": _dbvar_record(
                        uid="57735186",
                        sv="nsv7894147",
                        placements=[
                            (248_800_147, 248_800_147, "GRCh38"),
                            (44_815, 44_815, "GRCh37.p13"),
                            (249_094_346, 249_094_346, "GRCh37.p13"),
                        ],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "empty", (
        "nsv7894147 has no GRCh38 placement inside the window; a naive tool "
        "trusting the raw ESearch match would return it as a hit"
    )
    assert output.record_count == 0
    assert not output.records


@pytest.mark.asyncio
async def test_candidate_with_no_placement_for_requested_assembly_is_dropped() -> None:
    """A candidate whose ONLY placements are for a different assembly than
    requested must be dropped, never given a guessed or nearest placement.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv0000001",
                        # Only a GRCh37 placement. The request below asks
                        # for GRCh38.
                        placements=[(1_050_000, 1_050_100, "GRCh37")],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "empty"
    assert output.record_count == 0


# ===========================================================================
# Finding 1 (CRITICAL, re-review): the candidate filter must compare the
# chromosome, not just the assembly and the overlap predicate. Before the
# fix, `chromosome` was extracted onto `_Placement`, written to output, and
# never compared, so a record whose ONLY placement was on a DIFFERENT
# chromosome than requested, but numerically inside the window, was
# returned as a genuine overlap.
# ===========================================================================


@pytest.mark.asyncio
async def test_candidate_on_a_different_chromosome_is_dropped_even_with_numeric_overlap() -> None:
    """A record whose only placement is chr2, numerically inside a chr1
    query window, on the requested assembly, must be dropped. This is the
    judge's exact repro: chr1:1,000,000-1,100,000 GRCh38 must never return
    a chr2:1,000,500-1,000,600 GRCh38 placement.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv1",
                        placements=[(1_000_500, 1_000_600, "GRCh38", "2")],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "empty", (
        "a chr2 placement answering a chr1 query is a confident, cited, WRONG "
        "answer and must never be returned"
    )
    assert output.record_count == 0


@pytest.mark.asyncio
async def test_multi_placement_record_where_only_the_wrong_chromosome_overlaps_is_dropped() -> None:
    """A record with placements on TWO chromosomes, same requested assembly:
    the chr2 placement overlaps the window numerically, the chr1 placement
    (the requested chromosome) does not. The record must be dropped, since
    no placement satisfies BOTH the requested chromosome AND the overlap
    predicate.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv1",
                        placements=[
                            (1_000_500, 1_000_600, "GRCh38", "2"),  # wrong chromosome, overlaps
                            (5_000_000, 5_000_100, "GRCh38", "1"),  # right chromosome, no overlap
                        ],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "empty"
    assert output.record_count == 0


@pytest.mark.asyncio
async def test_multi_placement_record_the_matching_chromosome_placement_is_selected() -> None:
    """Same shape as above, except the requested-chromosome placement DOES
    overlap: the record must be kept, and the output fields must reflect
    the chr1 placement, never the chr2 one.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv1",
                        placements=[
                            (5_000_000, 5_000_100, "GRCh38", "2"),  # wrong chromosome, no overlap
                            (1_050_000, 1_050_100, "GRCh38", "1"),  # right chromosome, overlaps
                        ],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    assert output.record_count == 1
    assert output.records[0].fields["chr"] == "1"
    assert output.records[0].fields["chr_start"] == 1_050_000


@pytest.mark.asyncio
async def test_chromosome_match_is_case_and_chr_prefix_insensitive() -> None:
    """A request for chromosome "X" must match a placement carrying "chrX",
    and lowercase "x" must match too, the same normalization the module
    docstring's chromosome-casing note requires.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv1",
                        placements=[(1_050_000, 1_050_100, "GRCh38", "chrX")],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="x", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    assert output.record_count == 1


# ===========================================================================
# Predicate boundary conditions.
# ===========================================================================


@pytest.mark.asyncio
async def test_placement_touching_the_right_edge_of_the_window_overlaps() -> None:
    """placement.chr_start == window end: the predicate is <=, inclusive."""
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_100_000, 1_150_000, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1


@pytest.mark.asyncio
async def test_placement_touching_the_left_edge_of_the_window_overlaps() -> None:
    """placement.chr_end == window start: the predicate is >=, inclusive."""
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(950_000, 1_000_000, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1


@pytest.mark.asyncio
async def test_placement_one_base_outside_the_right_edge_does_not_overlap() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_100_001, 1_150_000, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "empty"


@pytest.mark.asyncio
async def test_placement_one_base_outside_the_left_edge_does_not_overlap() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(900_000, 999_999, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "empty"


@pytest.mark.asyncio
async def test_placement_fully_contained_in_the_window_overlaps() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1


@pytest.mark.asyncio
async def test_window_fully_contained_in_the_placement_overlaps() -> None:
    """A placement much larger than the query window (a whole-arm CNV, for
    example) still overlaps, even though neither endpoint sits inside the
    window.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(500_000, 2_000_000, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1


@pytest.mark.asyncio
async def test_zero_bp_insertion_exactly_on_window_boundary_overlaps() -> None:
    """A 0bp point insertion (chr_start == chr_end) sitting exactly on the
    window's start coordinate is a genuine boundary overlap, distinct from
    the proven-bug shape where the 0bp insertion sits nowhere near the
    window at all.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_000_000, 1_000_000, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1


@pytest.mark.asyncio
async def test_zero_bp_insertion_just_outside_the_window_does_not_overlap() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(999_999, 999_999, "GRCh38")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "empty"


# ===========================================================================
# Assembly matching: prefix match for patched dbVar assembly strings, and
# multiple placements for the same assembly.
# ===========================================================================


@pytest.mark.asyncio
async def test_patched_assembly_string_matches_a_bare_assembly_request() -> None:
    """dbVar mixes 'GRCh38' and 'GRCh38.p12' within and across records
    (verified live). A request for 'GRCh38' must match a 'GRCh38.p12'
    placement, or a real overlap is silently missed.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38.p12")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.records[0].fields["assembly"] == "GRCh38.p12"


@pytest.mark.asyncio
async def test_unrelated_assembly_prefix_does_not_false_match() -> None:
    """'GRCh381' must NOT match a request for 'GRCh38'. The prefix match is
    anchored on a literal dot, not a bare startswith.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh381")])}
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "empty"


@pytest.mark.asyncio
async def test_candidate_with_two_placements_for_same_assembly_kept_if_either_overlaps() -> None:
    """Verified live: uid 57735186 (nsv7894147) carries two GRCh37.p13
    placements. Requiring ALL matching placements to overlap would drop a
    genuinely overlapping record; this asserts the any-of semantics.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv1",
                        placements=[
                            (5_000_000, 5_000_100, "GRCh38"),  # does not overlap
                            (1_050_000, 1_050_100, "GRCh38"),  # does overlap
                        ],
                    )
                }
            ),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )
    assert output.status == "ok"
    assert output.record_count == 1
    assert output.records[0].fields["chr_start"] == 1_050_000


# ===========================================================================
# ClinVar: the actual live-verified nested placement shape, not Section
# 6.2's flat C37/CPOS scalars.
# ===========================================================================


@pytest.mark.asyncio
async def test_clinvar_true_overlap_uses_the_nested_variation_loc_shape() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["4865884"]),
            _clinvar_esummary_response(
                {
                    "4865884": _clinvar_record(
                        uid="4865884",
                        accession="VCV004865884",
                        title="NM_000546.6(TP53):c.1035T>C (p.Asn345=)",
                        placements=[(7_670_674, 7_670_674, "GRCh38"), (7_573_992, 7_573_992, "GRCh37")],
                        gene_symbol="TP53",
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="clinvar", chromosome="17", start=7_670_670, end=7_670_680, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    assert output.record_count == 1
    record = output.records[0]
    assert record.id == "VCV004865884"
    assert record.fields["chr_start"] == 7_670_674
    assert record.fields["assembly"] == "GRCh38"
    assert record.fields["gene_symbol"] == ["TP53"]
    assert record.source_url == "https://www.ncbi.nlm.nih.gov/clinvar/variation/4865884/"


@pytest.mark.asyncio
async def test_clinvar_grch37_placement_selected_when_grch37_requested() -> None:
    """Same record as above, opposite assembly: the GRCh37 placement
    (7,573,992) is nowhere near the GRCh38 window used above, proving the
    assembly selection genuinely switches placement rather than reusing
    whichever one happened to overlap.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["4865884"]),
            _clinvar_esummary_response(
                {
                    "4865884": _clinvar_record(
                        uid="4865884",
                        accession="VCV004865884",
                        title="NM_000546.6(TP53):c.1035T>C (p.Asn345=)",
                        placements=[(7_670_674, 7_670_674, "GRCh38"), (7_573_992, 7_573_992, "GRCh37")],
                    )
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="clinvar", chromosome="17", start=7_573_990, end=7_574_000, assembly="GRCh37"),
        client=client,
    )

    assert output.status == "ok"
    assert output.records[0].fields["assembly"] == "GRCh37"


# ===========================================================================
# Malformed and missing placement data: skipped, never fabricated.
# ===========================================================================


@pytest.mark.asyncio
async def test_placement_entry_missing_a_required_key_is_skipped_not_crashed() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            httpx.Response(
                200,
                json={
                    "header": {"type": "esummary"},
                    "result": {
                        "uids": ["1"],
                        "1": {
                            "uid": "1",
                            "sv": "nsv1",
                            # Missing chr_end entirely.
                            "dbvarplacementlist": [{"chr": "1", "chr_start": 1_050_000, "assembly": "GRCh38"}],
                        },
                    },
                },
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "empty"
    assert output.record_count == 0


@pytest.mark.asyncio
async def test_candidate_absent_from_esummary_result_is_dropped_not_fabricated() -> None:
    """ESearch returned a candidate id that ESummary's result envelope
    never populated (a deleted or merged uid). Must never fabricate a
    placement for it.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["999"]),
            httpx.Response(
                200,
                json={"header": {"type": "esummary"}, "result": {"uids": ["999"]}},
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "empty"
    assert output.record_count == 0


@pytest.mark.asyncio
async def test_record_failing_output_validation_is_dropped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An accession too long for NcbiEfetchRecord.id's maxLength must not
    crash the whole batch; it is dropped and logged.
    """
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(
                        uid="1",
                        sv="nsv" + "9" * 40,  # far past id's max_length of 30
                        placements=[(1_050_000, 1_050_100, "GRCh38")],
                    )
                }
            ),
        ]
    )

    with caplog.at_level(logging.WARNING):
        output = await ncbi_coordinate_overlap.coordinate_overlap(
            _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
        )

    assert output.status == "empty"
    assert output.record_count == 0
    assert any("dropping candidate" in record.message for record in caplog.records)


# ===========================================================================
# ESearch/ESummary status handling: empty and error.
# ===========================================================================


@pytest.mark.asyncio
async def test_zero_hit_esearch_is_empty_with_no_esummary_call() -> None:
    client = _FakeClient([_esearch_empty_response()])

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "empty"
    assert output.record_count == 0
    assert len(client.calls) == 1, "a zero-hit ESearch must never trigger an ESummary call"


@pytest.mark.asyncio
async def test_esearch_error_body_under_http_200_is_error() -> None:
    client = _FakeClient([_esearch_error_response("Invalid db name specified: dbvar")])

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "error"
    assert output.error is not None
    assert "Invalid db name specified" in output.error


@pytest.mark.asyncio
async def test_esummary_error_body_is_error() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            httpx.Response(
                200,
                json={"header": {"type": "esummary"}, "result": {"ERROR": "id does not exist"}},
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "error"
    assert output.error is not None


# ===========================================================================
# Truncation and candidate-count honesty.
# ===========================================================================


@pytest.mark.asyncio
async def test_truncated_and_total_available_are_set_when_more_candidates_exist() -> None:
    """F-3.1-24 (reopened): `total_available` reports what the coarse
    ESearch prefilter matched (500), `candidates_checked` reports how many
    were actually place-checked (1), and `truncated` says matches exist
    that this call never looked at.

    The previous fix collapsed both into the checked count, which threw
    away a meaningful ClinVar figure and made `total_available ==
    record_count` reachable alongside `truncated is True`.
    """
    client = _FakeClient(
        [
            _esearch_response(count=500, ids=["1"]),  # count vastly exceeds ids returned
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")])}
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client, max_candidates=1
    )

    assert output.total_available == 500, (
        "total_available must report how many the coarse prefilter matched, "
        "which is the same meaning the `search` action gives the field"
    )
    assert output.candidates_checked == 1, (
        "candidates_checked must report how many were actually place-checked"
    )
    assert output.record_count == 1
    assert output.truncated is True
    assert output.total_available != output.record_count, (
        "truncated must never coexist with total_available == record_count"
    )


@pytest.mark.asyncio
async def test_truncated_is_false_when_every_match_was_checked_and_returned() -> None:
    """F-3.1-24 (reopened), the self-contradiction reproduction.

    Live shape that exposed it: 20 matched, 20 checked, 20 returned, and
    the output still said `truncated is True` while `total_available ==
    record_count`. Nothing was truncated, so nothing may say it was.
    """
    ids = [str(n) for n in range(1, 21)]
    client = _FakeClient(
        [
            _esearch_response(count=20, ids=ids),
            _dbvar_esummary_response(
                {
                    uid: _dbvar_record(
                        uid=uid,
                        sv=f"nsv{uid}",
                        placements=[(1_050_000, 1_050_100, "GRCh38", "2")],
                    )
                    for uid in ids
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(chromosome="2", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
        max_candidates=20,
    )

    assert output.record_count == 20
    assert output.candidates_checked == 20
    assert output.total_available == 20
    assert output.truncated is False, (
        "everything the prefilter matched was checked and returned, so "
        "nothing was truncated"
    )


@pytest.mark.asyncio
async def test_truncated_never_coexists_with_total_available_equal_to_record_count() -> None:
    """The invariant itself, exercised across every count relationship the
    procedure can produce: no candidates dropped, some dropped by the
    overlap predicate, and more matched than checked.
    """
    scenarios = [
        # (esearch count, ids returned, overlapping placement per record)
        (3, ["1", "2", "3"], True),
        (3, ["1", "2", "3"], False),
        (99, ["1", "2", "3"], True),
        (99, ["1", "2", "3"], False),
    ]
    for count, ids, overlapping in scenarios:
        placement = (1_050_000, 1_050_100, "GRCh38") if overlapping else (9_000_000, 9_000_100, "GRCh38")
        client = _FakeClient(
            [
                _esearch_response(count=count, ids=ids),
                _dbvar_esummary_response(
                    {uid: _dbvar_record(uid=uid, sv=f"nsv{uid}", placements=[placement]) for uid in ids}
                ),
            ]
        )

        output = await ncbi_coordinate_overlap.coordinate_overlap(
            _input(start=1_000_000, end=1_100_000, assembly="GRCh38"),
            client=client,
            max_candidates=len(ids),
        )

        assert not (output.truncated and output.total_available == output.record_count), (
            f"self-contradictory output for count={count} ids={len(ids)} "
            f"overlapping={overlapping}: total_available="
            f"{output.total_available} record_count={output.record_count} "
            f"truncated={output.truncated}"
        )
        assert output.candidates_checked is not None
        assert output.record_count <= output.candidates_checked <= (output.total_available or 0)


@pytest.mark.asyncio
async def test_not_truncated_when_all_candidates_were_examined() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")])}
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.total_available == 1
    assert output.candidates_checked == 1
    assert output.truncated is False


# ===========================================================================
# One ESearch call, one BATCHED ESummary call, never one per candidate.
# ===========================================================================


@pytest.mark.asyncio
async def test_esummary_is_a_single_batched_call_for_multiple_candidates() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=3, ids=["1", "2", "3"]),
            _dbvar_esummary_response(
                {
                    "1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")]),
                    "2": _dbvar_record(uid="2", sv="nsv2", placements=[(1_060_000, 1_060_100, "GRCh38")]),
                    "3": _dbvar_record(uid="3", sv="nsv3", placements=[(1_070_000, 1_070_100, "GRCh38")]),
                }
            ),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.record_count == 3
    assert len(client.calls) == 2, "exactly one ESearch call plus one batched ESummary call"
    assert client.calls[1]["url"].count("id=1%2C2%2C3") == 1 or "id=1,2,3" in urllib.parse.unquote(
        client.calls[1]["url"]
    )


@pytest.mark.asyncio
async def test_retmax_is_capped_at_max_candidates() -> None:
    client = _FakeClient(
        [
            _esearch_response(count=100, ids=["1"]),
            _dbvar_esummary_response(
                {"1": _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")])}
            ),
        ]
    )

    await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client, max_candidates=5
    )

    query = _query_of(client.calls[0]["url"])
    assert query["retmax"] == "5"


# ===========================================================================
# Entrez field-tag correctness per db, read off the actual request URL.
# ===========================================================================


@pytest.mark.asyncio
async def test_dbvar_search_term_uses_ch_base_and_assm_tags() -> None:
    client = _FakeClient([_esearch_empty_response()])

    await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="dbvar", chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"),
        client=client,
    )

    term = urllib.parse.unquote_plus(_query_of(client.calls[0]["url"])["term"])
    assert "1[CH]" in term
    assert "1000000:1100000[BASE]" in term
    assert "GRCh38[ASSM]" in term


@pytest.mark.asyncio
async def test_clinvar_search_term_uses_chr_and_cpos_for_grch38() -> None:
    client = _FakeClient([_esearch_empty_response()])

    await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="clinvar", chromosome="17", start=7_661_779, end=7_687_538, assembly="GRCh38"),
        client=client,
    )

    term = urllib.parse.unquote_plus(_query_of(client.calls[0]["url"])["term"])
    assert "17[CHR]" in term
    assert "7661779:7687538[CPOS]" in term


@pytest.mark.asyncio
async def test_clinvar_search_term_uses_c37_for_grch37() -> None:
    client = _FakeClient([_esearch_empty_response()])

    await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="clinvar", chromosome="17", start=43_044_295, end=43_125_483, assembly="GRCh37"),
        client=client,
    )

    term = urllib.parse.unquote_plus(_query_of(client.calls[0]["url"])["term"])
    assert "43044295:43125483[C37]" in term


# ===========================================================================
# Rate-limit, timeout, and connection failures: actionable errors, never a
# propagated exception.
# ===========================================================================


@pytest.mark.asyncio
async def test_esearch_rate_limited_returns_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise_rate_limited(*args: Any, **kwargs: Any) -> httpx.Response:
        raise ncbi_transport.TransportRateLimitedError(
            "eutils rate pool queue is full", family="eutils", retry_after=1.5
        )

    monkeypatch.setattr(ncbi_coordinate_overlap, "execute_get", _raise_rate_limited)

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38")
    )

    assert output.status == "error"
    assert output.error is not None
    assert "rate limited" in output.error
    assert "retry" in output.error.lower()


@pytest.mark.asyncio
async def test_esearch_server_side_429_is_a_rate_limit_not_a_body_parse_failure() -> None:
    """Re-review round 1 (2026-08-07), cross-file gap: `classify_eutils_response`
    is deliberately status-blind (body only), and `ncbi_eutils_actions.py`
    grew a status-code guard in front of it for exactly this reason. This
    module shares the same transport and the same classifier at the same
    kind of hop and had no such guard, so a real NCBI 429 (an HTTP status,
    not a `TransportRateLimitedError` the client-side limiter raises) fell
    straight through `classify_eutils_response` as an unparseable body and
    was reported as "returned an error ... refusing to guess its meaning",
    which tells the next agent step to rewrite the chromosome and
    coordinate window when the correct action is to back off and retry.
    Live-reproduced with the real live-shaped body before this fix landed.
    """
    def _make_429() -> httpx.Response:
        return httpx.Response(
            429,
            content=b"API rate limit exceeded",
            headers={"content-type": "text/plain", "retry-after": "30"},
        )

    # ncbi_transport retries a transient status (429/500/502/503/504) once
    # automatically; both attempts return the same 429 here so the retry
    # exhausts and the final response is still the one under test.
    client = _FakeClient([_make_429(), _make_429()])

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "error"
    assert output.error is not None
    assert "429" in output.error
    assert "rate limited" in output.error
    assert "Retry after 30 seconds" in output.error
    assert "verify the chromosome" not in output.error, (
        "a 429 must not surface as a request-was-malformed message; that "
        "tells the next agent step to rewrite its query instead of backing off"
    )


@pytest.mark.asyncio
async def test_esummary_server_side_503_is_a_server_error_not_a_body_parse_failure() -> None:
    """Same gap as the ESearch hop above, on the ESummary placement fetch."""
    def _make_503() -> httpx.Response:
        return httpx.Response(
            503, content=b"Service Unavailable", headers={"content-type": "text/plain"}
        )

    esearch_response = _esearch_response(count=1, ids=["12345"])
    # One automatic retry on a transient status, same reasoning as the 429
    # test above.
    client = _FakeClient([esearch_response, _make_503(), _make_503()])

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "error"
    assert output.error is not None
    assert "503" in output.error
    assert "server error" in output.error
    assert "verify the chromosome" not in output.error
    # The candidate count already known before the failure is still
    # reported, per this module's own error-output contract.
    assert output.candidates_checked == 1


@pytest.mark.asyncio
async def test_esearch_timeout_returns_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise_timeout(*args: Any, **kwargs: Any) -> httpx.Response:
        raise ncbi_transport.TransportTimeoutError("eutils.ncbi.nlm.nih.gov timed out after 15.0s")

    monkeypatch.setattr(ncbi_coordinate_overlap, "execute_get", _raise_timeout)

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38")
    )

    assert output.status == "error"
    assert output.error is not None
    assert "retry" in output.error.lower()


@pytest.mark.asyncio
async def test_esummary_connection_error_returns_an_actionable_error_and_keeps_total_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    async def _sequenced(*args: Any, **kwargs: Any) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _esearch_response(count=1, ids=["1"])
        raise ncbi_transport.TransportConnectionError("eutils.ncbi.nlm.nih.gov connection failed")

    monkeypatch.setattr(ncbi_coordinate_overlap, "execute_get", _sequenced)

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38")
    )

    assert output.status == "error"
    assert output.total_available == 1, (
        "the ESearch count is already known when the ESummary call fails and must "
        "not be discarded"
    )


# ===========================================================================
# Chromosome normalization (F-3.1-15, CRITICAL)
# ===========================================================================


class TestChromosomeNormalization:
    """F-3.1-15: _normalize_chromosome and _build_search_term must normalize
    chr-prefixed, zero-padded, and MT/M variants before the ESearch query,
    and _chromosome_matches must compare the normalized forms.

    What this class exercises: `chr`-prefixed spellings in every casing,
    zero-padded numeric spellings, the M/MT mitochondrial pair, the empty
    and whitespace-only degenerate cases, and the `"chr"`-with-no-suffix
    edge. What it deliberately does not exercise: non-human chromosome
    labels, unplaced-scaffold accessions such as `GL000192.1`, and the
    `chrUn_*` family, none of which the dbVar/ClinVar `[CH]`/`[CHR]`
    indexes were verified against in this ticket.

    The zero-padded rows exist because the original parametrization
    omitted exactly the spelling that was broken, which is how the
    regression survived a green suite. Live 2026-08-07 on dbVar chr1
    GRCh38 1,000,000 to 1,100,000: `"1"` and `"chr1"` each returned 17
    genuine overlaps, `"01"` returned status=empty.
    """

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("1", "1"),
            ("chr1", "1"),
            ("Chr1", "1"),
            ("CHR1", "1"),
            ("X", "X"),
            ("chrX", "X"),
            ("MT", "MT"),
            ("chrMT", "MT"),
            ("mt", "MT"),
            ("M", "MT"),
            ("chrM", "MT"),
            ("chr", "CHR"),       # edge case: "chr" with nothing after
            ("CHR", "CHR"),       # "CHR" is not the prefix "chr" (different case)
            # F-3.1-15 (reopened): zero-padded numeric spellings.
            ("01", "1"),
            ("001", "1"),
            ("007", "7"),
            ("017", "17"),
            ("chr01", "1"),
            ("CHR017", "17"),
            (" 01 ", "1"),
            ("0", "0"),           # a lone zero must not collapse to ""
            ("000", "0"),
            ("22", "22"),         # an unpadded multi-digit label is untouched
            ("0X", "0X"),         # non-numeric: leading zero is NOT stripped
        ],
    )
    def test_normalize_chromosome(self, raw: str, expected: str) -> None:
        from system_03_search_agent.tools.ncbi_coordinate_overlap import (
            _normalize_chromosome,
        )
        assert _normalize_chromosome(raw) == expected

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("1", "1", True),
            ("1", "chr1", True),
            ("chr1", "1", True),
            ("MT", "M", True),
            ("M", "MT", True),
            ("chrMT", "mt", True),
            ("1", "2", False),
            ("X", "Y", False),
            # F-3.1-15 (reopened): zero-padded spellings compare equal.
            ("01", "1", True),
            ("1", "01", True),
            ("chr01", "1", True),
            ("017", "17", True),
            ("007", "7", True),
            ("01", "2", False),
            # F-3.1-35: a blank on either side fails CLOSED.
            ("", "1", False),
            ("1", "", False),
            ("", "", False),
            ("   ", "", False),
            ("", "   ", False),
        ],
    )
    def test_chromosome_matches(self, a: str, b: str, expected: bool) -> None:
        from system_03_search_agent.tools.ncbi_coordinate_overlap import (
            _chromosome_matches,
        )
        assert _chromosome_matches(a, b) == expected

    @pytest.mark.parametrize(
        "chromosome, expected_chromosome_in_term",
        [
            ("1", "1[CH]"),
            ("chr1", "1[CH]"),
            ("Chr1", "1[CH]"),
            ("chrM", "MT[CH]"),
            ("M", "MT[CH]"),
            # F-3.1-15 (reopened): the padded spelling must NOT reach the
            # wire. Live: `01[CH] AND ...` counts 0, `1[CH] AND ...` counts
            # 1892.
            ("01", "1[CH]"),
            ("001", "1[CH]"),
            ("chr01", "1[CH]"),
        ],
    )
    def test_build_search_term_normalizes_chromosome(
        self, chromosome: str, expected_chromosome_in_term: str
    ) -> None:
        from system_03_search_agent.tools.ncbi_coordinate_overlap import (
            _build_search_term,
        )
        term = _build_search_term(
            db="dbvar",
            chromosome=chromosome,
            start=1_000_000,
            end=1_100_000,
            assembly="GRCh38",
        )
        # startswith, not `in`: `"1[CH]" in "01[CH] AND ..."` is True, so a
        # substring check would pass on exactly the zero-padded spelling
        # this parametrization was extended to catch.
        assert term.startswith(expected_chromosome_in_term), (
            f"search term for chromosome {chromosome!r} must START with "
            f"{expected_chromosome_in_term!r}, got {term!r}"
        )

    @pytest.mark.asyncio
    async def test_zero_padded_chromosome_reaches_the_same_records_as_the_bare_form(
        self,
    ) -> None:
        """F-3.1-15 (reopened), end to end: '1', 'chr1' and '01' must all
        produce the same non-empty result for the same window.

        The dbVar ESummary placement below is tagged chromosome '1'. Before
        the leading-zero strip, '01' went on the wire un-normalized (live:
        `01[CH] AND ...` counts 0 while `1[CH] AND ...` counts 1892), and
        even had the search returned candidates, `_chromosome_matches('1',
        '01')` was False, so the post-filter would have dropped every one.
        """
        outputs = []
        for spelling in ("1", "chr1", "01"):
            client = _FakeClient(
                [
                    _esearch_response(count=1, ids=["1"]),
                    _dbvar_esummary_response(
                        {
                            "1": _dbvar_record(
                                uid="1",
                                sv="nsv1",
                                placements=[(1_050_000, 1_050_100, "GRCh38", "1")],
                            )
                        }
                    ),
                ]
            )
            output = await ncbi_coordinate_overlap.coordinate_overlap(
                _input(chromosome=spelling, start=1_000_000, end=1_100_000, assembly="GRCh38"),
                client=client,
            )
            assert client.calls[0]["url"].count("term=1%5BCH%5D") == 1, (
                f"spelling {spelling!r} must send the bare '1' on the wire, "
                f"got {client.calls[0]['url']!r}"
            )
            outputs.append(output)

        assert all(o.status == "ok" for o in outputs), [o.status for o in outputs]
        assert all(o.record_count == 1 for o in outputs), [o.record_count for o in outputs]
        assert len({tuple(r.id for r in o.records) for o in outputs}) == 1, (
            "'1', 'chr1' and '01' must return the identical record set"
        )

    @pytest.mark.asyncio
    async def test_zero_padded_clinvar_chromosome_matches_the_bare_form(self) -> None:
        """F-3.1-15 (reopened), the ClinVar half. Live: '17' returned 20
        records for the TP53 window, '017' returned status=empty.
        """
        outputs = []
        for spelling in ("17", "017"):
            client = _FakeClient(
                [
                    _esearch_response(count=1, ids=["9"]),
                    _clinvar_esummary_response(
                        {
                            "9": _clinvar_record(
                                uid="9",
                                accession="VCV000000009",
                                title="NM_000546.6(TP53):c.1035T>C (p.Thr345=)",
                                placements=[(7_670_670, 7_670_680, "GRCh38")],
                            )
                        }
                    ),
                ]
            )
            output = await ncbi_coordinate_overlap.coordinate_overlap(
                _input(
                    db="clinvar",
                    chromosome=spelling,
                    start=7_670_000,
                    end=7_671_000,
                    assembly="GRCh38",
                ),
                client=client,
            )
            assert client.calls[0]["url"].count("term=17%5BCHR%5D") == 1, (
                f"spelling {spelling!r} must send the bare '17' on the wire, "
                f"got {client.calls[0]['url']!r}"
            )
            outputs.append(output)

        assert all(o.status == "ok" for o in outputs), [o.status for o in outputs]
        assert len({tuple(r.id for r in o.records) for o in outputs}) == 1


# ===========================================================================
# Blank chromosome fails CLOSED (F-3.1-35).
# ===========================================================================


@pytest.mark.asyncio
async def test_placement_with_no_chromosome_never_matches_a_blank_request() -> None:
    """F-3.1-35: a placement whose `chr` key is missing and a caller
    chromosome of "" both normalize to "". Comparing those for equality
    reported a match, reopening F-3.1-02's failure shape (a match asserted
    without any real chromosome comparison). The request must be refused
    before the wire, and even if it were not, the post-filter must not
    match.
    """
    from system_03_search_agent.tools.ncbi_coordinate_overlap import _chromosome_matches

    placement_without_chr = {"chr_start": 1_050_000, "chr_end": 1_050_100, "assembly": "GRCh38"}
    record = {
        "uid": "1",
        "sv": "nsv1",
        "dbvarplacementlist": [placement_without_chr],
        "dbvarvarianttypelist": ["copy number variation"],
        "dbvargenelist": [],
    }
    extracted = ncbi_coordinate_overlap._extract_placements("dbvar", record)
    assert extracted, "the placement must still be extracted, only the MATCH may fail"
    assert extracted[0].chromosome == ""
    assert _chromosome_matches(extracted[0].chromosome, "") is False, (
        "a placement with no chromosome must never match a blank request"
    )

    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response({"1": record}),
        ]
    )
    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(chromosome="", start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "error"
    assert output.record_count == 0
    assert output.error is not None
    assert "blank chromosome" in output.error
    assert not client.calls, "a blank chromosome must never reach the network"


@pytest.mark.asyncio
async def test_placement_with_no_chromosome_is_dropped_for_a_real_request() -> None:
    """The same fail-closed rule from the other side: a real chromosome was
    requested and the placement carries none, so it is dropped rather than
    admitted on its coordinates alone.
    """
    record = {
        "uid": "1",
        "sv": "nsv1",
        "dbvarplacementlist": [
            {"chr": "", "chr_start": 1_050_000, "chr_end": 1_050_100, "assembly": "GRCh38"}
        ],
        "dbvarvarianttypelist": ["copy number variation"],
        "dbvargenelist": [],
    }
    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response({"1": record}),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(chromosome="1", start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "empty"
    assert output.record_count == 0


# ===========================================================================
# Per-value character cap on untrusted free text (F-3.1-12).
# ===========================================================================


@pytest.mark.asyncio
async def test_clinvar_free_text_fields_are_length_capped() -> None:
    """F-3.1-12: `NcbiEfetchRecord.fields` caps the field COUNT, never any
    one value's length, so a hostile or merely enormous ClinVar `title` or
    germline classification `description` would flow into the Write step's
    context uncapped. Same `_cap_text` bound the other five actions use.
    """
    from system_03_search_agent.tools.ncbi_coordinate_overlap import _MAX_FIELD_VALUE_CHARS

    record = _clinvar_record(
        uid="9",
        accession="VCV000000009",
        title="T" * (_MAX_FIELD_VALUE_CHARS * 3),
        placements=[(7_670_670, 7_670_680, "GRCh38")],
        gene_symbol="TP53",
    )
    record["germline_classification"] = {"description": "D" * (_MAX_FIELD_VALUE_CHARS * 2)}

    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["9"]),
            _clinvar_esummary_response({"9": record}),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(db="clinvar", chromosome="17", start=7_670_000, end=7_671_000, assembly="GRCh38"),
        client=client,
    )

    assert output.status == "ok"
    fields = output.records[0].fields
    for key in ("title", "germline_classification"):
        assert len(fields[key]) <= _MAX_FIELD_VALUE_CHARS + len(" [truncated]"), (
            f"{key} was not length-capped: {len(fields[key])} chars"
        )
        assert fields[key].endswith(" [truncated]")


@pytest.mark.asyncio
async def test_dbvar_free_text_list_fields_are_capped_on_both_axes() -> None:
    """A list is capped on item count and per-item length alike: a thousand
    short strings blows the context budget exactly as one long string does.
    """
    from system_03_search_agent.tools.ncbi_coordinate_overlap import (
        _MAX_FIELD_LIST_ITEMS,
        _MAX_FIELD_VALUE_CHARS,
    )

    record = _dbvar_record(uid="1", sv="nsv1", placements=[(1_050_000, 1_050_100, "GRCh38")])
    record["dbvarvarianttypelist"] = ["V" * (_MAX_FIELD_VALUE_CHARS * 2)] * (
        _MAX_FIELD_LIST_ITEMS * 3
    )
    record["dbvargenelist"] = [{"id": n, "name": "G" * 10} for n in range(_MAX_FIELD_LIST_ITEMS * 3)]

    client = _FakeClient(
        [
            _esearch_response(count=1, ids=["1"]),
            _dbvar_esummary_response({"1": record}),
        ]
    )

    output = await ncbi_coordinate_overlap.coordinate_overlap(
        _input(start=1_000_000, end=1_100_000, assembly="GRCh38"), client=client
    )

    assert output.status == "ok"
    fields = output.records[0].fields
    assert len(fields["variant_type"]) == _MAX_FIELD_LIST_ITEMS
    assert all(
        len(item) <= _MAX_FIELD_VALUE_CHARS + len(" [truncated]") for item in fields["variant_type"]
    )
    assert len(fields["gene_name"]) == _MAX_FIELD_LIST_ITEMS
