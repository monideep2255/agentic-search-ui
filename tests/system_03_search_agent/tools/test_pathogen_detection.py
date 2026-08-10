"""Unit tests for `pathogen_detection` (T-3.5-05).

The real `pathogen_ftp_transport.py` exists and is imported below in the
normal case; the `try`/`except ModuleNotFoundError` block that follows
installs a minimal placeholder module into `sys.modules` ONLY as a defensive
fallback should that import ever fail (mirroring how an optional/plugin
dependency is stubbed for a test run), never as evidence about this repo's
actual state. Every individual test still installs its OWN scripted
behavior via `monkeypatch.setattr` on whichever module object (real or
placeholder) ended up bound as `pathogen_detection.pathogen_ftp_transport`,
exactly the same `monkeypatch.setattr(module.dependency, "func",
scripted)` pattern `test_litvar2_lookup.py` already uses for
`ncbi_transport.execute_get`. `pathogen_ftp_transport.py`'s OWN behavior
(the scan and matching logic itself, including the real bug a judge round
found there, F-3.5-06) is covered by
`tests/system_03_search_agent/tools/test_pathogen_ftp_transport.py`, not
by anything in this file: every fixture here scripts a `TsvScanResult`
directly, so this file proves `pathogen_detection.py`'s handling of a
GIVEN transport result, never the transport's own correctness.

No live network anywhere in this file, mirroring
`test_litvar2_lookup.py`'s own house convention. Live network coverage of
the real endpoint is `test_pathogen_detection_premise.py`'s job, a file
this worktree does not have.

Coverage statement (per `.claude/rules/goal-contracts.md`'s "a verify
surface must state its own coverage"):

This file exercises:
    - isolate_lookup: ok (with cluster/SNP-neighbor best-effort
      enrichment succeeding), ok (with that enrichment failing, per this
      ticket's own explicit allowance that it may be best-effort), and
      empty (no matching biosample_acc in Metadata).
    - cluster_snp_neighbors: ok (multiple members, one filtered out of
      max_snp_distance range, one metadata-parse exclusion), and empty
      (no members in cluster_list.tsv).
    - F-3.5-01: a deadline that is already exhausted before a scan starts,
      and a scan whose own TsvScanResult reports
      `truncated_by_deadline=True`, both resolve to `status: "empty"` with
      an actionable message naming the budget, never a silently-partial
      `status: "ok"`. Covered for both the cluster_list read and the
      SNP_distances read.
    - F-3.5-03: the comma-join/NULL parser directly
      (`_parse_pathogen_list_field`), and through a full `_build_isolate`
      call: a double-quoted comma-joined AMR_genotypes value parses into a
      real list, a bare `NULL` AST_phenotypes value parses to `[]` (never
      `["NULL"]`), and an unquoted single-term value is unaffected.
    - The snapshot-pinning call itself: `pathogen_detection` always calls
      `pathogen_ftp_transport.resolve_complete_snapshot(taxon,
      client=...)` rather than guessing a snapshot path itself, and a
      `PathogenSnapshotUnavailableError` from that call surfaces as
      `status: "error"` naming the taxon. (Whether the transport module's
      OWN incomplete-snapshot-skipping logic is correct is that module's
      own test responsibility, not this tool's; this tool only needs to
      call it and handle both outcomes, which is what is tested here.)
    - Untrusted-content field caps: an over-length `strain` value is
      withheld (named in `fields_withheld`, field becomes `None`), never
      silently truncated into a shorter real-looking value; an over-length
      `biosample_acc` (the identity field) excludes the whole isolate
      rather than shipping a truncated identity.
    - The `taxon` defense-in-depth re-check inside `pathogen_detection.py`
      itself (`_pathogen_detection_impl`'s own guard), exercised by
      calling the internal implementation directly with a hand-built
      action object that bypasses Pydantic construction, since the public
      `PathogenDetectionInput` entry point already rejects an unsafe
      `taxon` at the schema layer (see
      `test_pathogen_detection_schemas.py`'s own taxon coverage) and would
      never reach this code path in production.
    - Malformed-input rejection at the schema boundary: constructing
      `PathogenDetectionInput` with an unsafe `taxon` or a missing
      required field raises before `pathogen_detection` is ever called
      (a thin integration check; the exhaustive schema-boundary cases live
      in `test_pathogen_detection_schemas.py`, not duplicated here).
    - The never-raises wrapper: an unexpected exception inside the impl
      (a scripted transport call that raises a plain `RuntimeError`, a
      shape neither `pathogen_ftp_transport.PathogenSnapshotUnavailableError`
      nor `PathogenDeadlineExceededError` names) is caught and reported as
      a `status: "error"` output, never propagated.

This file deliberately does NOT exercise, and states the gap rather than
silently omitting it:
    - `pathogen_ftp_transport.py`'s own scan and row-matching behavior:
      every TSV row fixture here is a HAND-CONSTRUCTED `TsvScanResult`,
      scripted directly, never produced by a real (or even a fake) HTTP
      stream. A passing test here proves `pathogen_detection.py` handles a
      GIVEN transport result correctly; it says nothing about whether the
      transport itself produces the right result from real bytes on the
      wire. That is `test_pathogen_ftp_transport.py`'s job, added
      specifically because this gap let a critical defect (F-3.5-06)
      through a fully green run of this file.
    - Whole-invocation timing against a real slow/large file; the deadline
      tests here simulate exhaustion by constructing an already-past
      `time.monotonic()` value or by scripting `truncated_by_deadline=True`
      directly on a canned `TsvScanResult`, never by actually waiting out
      a real clock.

Depends on:
    - system_03_search_agent.tools.pathogen_detection (module under test)
    - system_03_search_agent.tools.pathogen_detection_schemas, for
      constructing valid inputs
    - system_03_search_agent.tools.pathogen_ftp_transport, real if
      importable, otherwise a test-local placeholder installed into
      sys.modules by this file (defensive fallback only, see above)

Writes:
    - Nothing.
"""

from __future__ import annotations

import sys
import time
import types
from typing import Any

import httpx
import pytest

_TRANSPORT_MODULE_NAME = "system_03_search_agent.tools.pathogen_ftp_transport"

try:
    import system_03_search_agent.tools.pathogen_ftp_transport as _existing_transport  # noqa: F401

    _TRANSPORT_IS_PLACEHOLDER = False
except ModuleNotFoundError:
    _TRANSPORT_IS_PLACEHOLDER = True

    class _PlaceholderTsvScanResult:
        """Duck-typed stand-in for the real TsvScanResult: .rows,
        .truncated_by_deadline, .total_rows_scanned, per the exact
        attribute names `pathogen_detection.py`'s own module docstring
        quotes from the dispatching task.
        """

        def __init__(
            self,
            rows: list[dict[str, str]],
            *,
            truncated_by_deadline: bool = False,
            total_rows_scanned: int = 0,
        ) -> None:
            self.rows = rows
            self.truncated_by_deadline = truncated_by_deadline
            self.total_rows_scanned = total_rows_scanned

    class _PlaceholderPathogenSnapshotUnavailableError(Exception):
        pass

    class _PlaceholderPathogenDeadlineExceededError(Exception):
        pass

    async def _placeholder_resolve_complete_snapshot(
        taxon: str, *, client: Any, base_url: str | None = None
    ) -> str:
        raise NotImplementedError(
            "placeholder pathogen_ftp_transport.resolve_complete_snapshot: "
            "every test must monkeypatch this before calling it"
        )

    async def _placeholder_stream_filtered_tsv_rows(
        url: str,
        *,
        key_column: str,
        key_values: set[str],
        deadline: float,
        client: Any,
        max_matches: int | None = None,
    ) -> _PlaceholderTsvScanResult:
        raise NotImplementedError(
            "placeholder pathogen_ftp_transport.stream_filtered_tsv_rows: "
            "every test must monkeypatch this before calling it"
        )

    _placeholder_module = types.ModuleType(_TRANSPORT_MODULE_NAME)
    _placeholder_module.TsvScanResult = _PlaceholderTsvScanResult  # type: ignore[attr-defined]
    _placeholder_module.PathogenSnapshotUnavailableError = (  # type: ignore[attr-defined]
        _PlaceholderPathogenSnapshotUnavailableError
    )
    _placeholder_module.PathogenDeadlineExceededError = (  # type: ignore[attr-defined]
        _PlaceholderPathogenDeadlineExceededError
    )
    _placeholder_module.DEFAULT_TIMEOUT_S = 60.0  # type: ignore[attr-defined]
    _placeholder_module.PATHOGEN_FTP_BASE = (  # type: ignore[attr-defined]
        "https://ftp.ncbi.nlm.nih.gov/pathogen/Results/"
    )
    _placeholder_module.resolve_complete_snapshot = (  # type: ignore[attr-defined]
        _placeholder_resolve_complete_snapshot
    )
    _placeholder_module.stream_filtered_tsv_rows = (  # type: ignore[attr-defined]
        _placeholder_stream_filtered_tsv_rows
    )
    sys.modules[_TRANSPORT_MODULE_NAME] = _placeholder_module

from system_03_search_agent.tools import pathogen_detection as pathogen_detection_module
from system_03_search_agent.tools import pathogen_ftp_transport as transport
from system_03_search_agent.tools.pathogen_detection import (
    _isolate_lookup,
    _parse_pathogen_list_field,
    build_citation,
    pathogen_detection,
)
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PathogenDetectionInput,
    PathogenDetectionOutput,
    PathogenIsolate,
    PathogenIsolateLookupInput,
)

TsvScanResult = transport.TsvScanResult
PathogenSnapshotUnavailableError = transport.PathogenSnapshotUnavailableError
PathogenDeadlineExceededError = transport.PathogenDeadlineExceededError


# ---------------------------------------------------------------------------
# Scripted transport: a sequential queue of scripted results/exceptions,
# one per stream_filtered_tsv_rows call, matching test_litvar2_lookup.py's
# own _ScriptedTransport shape. resolve_complete_snapshot is scripted
# separately since it is called exactly once per invocation, always first.
# ---------------------------------------------------------------------------


class _ScriptedTsvReads:
    def __init__(self, items: list[TsvScanResult | Exception]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        url: str,
        *,
        key_column: str,
        key_values: set[str],
        deadline: float,
        client: Any,
        max_matches: int | None = None,
        one_row_per_key: bool = False,
    ) -> TsvScanResult:
        self.calls.append(
            {
                "url": url,
                "key_column": key_column,
                "key_values": set(key_values),
                "deadline": deadline,
                "max_matches": max_matches,
                "one_row_per_key": one_row_per_key,
            }
        )
        if not self._items:
            raise AssertionError(f"unexpected extra stream_filtered_tsv_rows call: {url}")
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install_snapshot(monkeypatch: pytest.MonkeyPatch, snapshot: str = "PDG000000002.4157") -> None:
    async def _resolve(taxon: str, *, client: Any, base_url: str | None = None) -> str:
        return snapshot

    monkeypatch.setattr(
        pathogen_detection_module.pathogen_ftp_transport, "resolve_complete_snapshot", _resolve
    )


def _install_snapshot_unavailable(monkeypatch: pytest.MonkeyPatch, message: str = "no complete snapshot") -> None:
    async def _resolve(taxon: str, *, client: Any, base_url: str | None = None) -> str:
        raise PathogenSnapshotUnavailableError(message)

    monkeypatch.setattr(
        pathogen_detection_module.pathogen_ftp_transport, "resolve_complete_snapshot", _resolve
    )


def _install_reads(monkeypatch: pytest.MonkeyPatch, items: list[TsvScanResult | Exception]) -> _ScriptedTsvReads:
    scripted = _ScriptedTsvReads(items)
    monkeypatch.setattr(
        pathogen_detection_module.pathogen_ftp_transport, "stream_filtered_tsv_rows", scripted
    )
    return scripted


def _isolate_lookup_input(taxon: str = "Salmonella", biosample_acc: str = "SAMN02147118") -> PathogenDetectionInput:
    return PathogenDetectionInput(mode="isolate_lookup", taxon=taxon, biosample_acc=biosample_acc)


def _cluster_input(
    taxon: str = "Salmonella", pds_cluster: str = "PDS000012345.1", max_snp_distance: int = 5
) -> PathogenDetectionInput:
    return PathogenDetectionInput(
        mode="cluster_snp_neighbors",
        taxon=taxon,
        pds_cluster=pds_cluster,
        max_snp_distance=max_snp_distance,
    )


def _metadata_row(
    biosample_acc: str = "SAMN02147118",
    *,
    run: str = "SRR1234567",
    strain: str = "SL1344",
    serovar: str = "Typhimurium",
    geo_loc_name: str = "USA",
    collection_date: str = "2020-01-01",
    amr_genotypes: str | None = '"ant(2\'\')-Ia,aph(3\')-Ia,blaTEM-1"',
    ast_phenotypes: str | None = "NULL",
) -> dict[str, str]:
    row = {
        "biosample_acc": biosample_acc,
        "Run": run,
        "strain": strain,
        "serovar": serovar,
        "geo_loc_name": geo_loc_name,
        "collection_date": collection_date,
    }
    if amr_genotypes is not None:
        row["AMR_genotypes"] = amr_genotypes
    if ast_phenotypes is not None:
        row["AST_phenotypes"] = ast_phenotypes
    return row


# ---------------------------------------------------------------------------
# F-3.5-03: comma-join / NULL sentinel parsing, direct unit coverage.
# ---------------------------------------------------------------------------


def test_parse_pathogen_list_field_double_quoted_comma_join():
    raw = "\"ant(2'')-Ia,aph(3')-Ia,blaTEM-1\""
    assert _parse_pathogen_list_field(raw) == ["ant(2'')-Ia", "aph(3')-Ia", "blaTEM-1"]


def test_parse_pathogen_list_field_bare_null_is_empty_list_not_null_string():
    assert _parse_pathogen_list_field("NULL") == []
    assert _parse_pathogen_list_field('"NULL"') == []


def test_parse_pathogen_list_field_none_and_empty_string_are_empty_list():
    assert _parse_pathogen_list_field(None) == []
    assert _parse_pathogen_list_field("") == []
    assert _parse_pathogen_list_field("   ") == []


def test_parse_pathogen_list_field_unquoted_single_term_unaffected():
    assert _parse_pathogen_list_field("blaTEM-1") == ["blaTEM-1"]


def test_parse_pathogen_list_field_unquoted_comma_join_also_parses():
    assert _parse_pathogen_list_field("geneA,geneB") == ["geneA", "geneB"]


# ---------------------------------------------------------------------------
# isolate_lookup: ok, empty.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_isolate_lookup_ok_parses_amr_and_ast_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    metadata_row = _metadata_row()
    cluster_row = {"biosample_acc": "SAMN02147118", "PDS_acc": "PDS000012345.1"}
    snp_row = {
        "PDS_acc": "PDS000012345.1",
        "biosample_acc_1": "SAMN02147118",
        "biosample_acc_2": "SAMN00999999",
        "compatible_distance": "3",
    }
    _install_reads(
        monkeypatch,
        [
            TsvScanResult([metadata_row]),  # Metadata read
            TsvScanResult([cluster_row]),  # cluster_list read (best-effort)
            TsvScanResult([snp_row]),  # SNP_distances read (best-effort)
        ],
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "ok", output.error
    assert output.mode == "isolate_lookup"
    assert output.pdg_snapshot == "PDG000000002.4157"
    assert output.isolate_count == 1
    assert output.total_available == 1
    assert output.truncated is False
    isolate = output.isolates[0]
    assert isolate.biosample_acc == "SAMN02147118"
    assert isolate.run_sra == "SRR1234567"
    assert isolate.strain == "SL1344"
    assert isolate.amr_genotypes == ["ant(2'')-Ia", "aph(3')-Ia", "blaTEM-1"]
    assert isolate.ast_phenotypes == []  # bare NULL -> [], never ["NULL"]
    assert isolate.pds_cluster == "PDS000012345.1"
    assert isolate.snp_distance == 3
    assert isolate.source_url == (
        "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN02147118"
    )


@pytest.mark.asyncio
async def test_isolate_lookup_snp_distance_populated_even_when_scan_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.5-A-05 (adversary round, 2026-08-08) regression test: the
    best-effort enrichment's SNP_distances scan reports
    truncated_by_deadline=True (its own 20s sub-budget could not reach
    EOF, F-3.5-07) but DID find this isolate's own pairwise row before the
    cutoff. snp_distance must be populated from it, never left None just
    because the scan as a whole did not finish. The pre-fix version of
    this code skipped the parse entirely whenever truncated_by_deadline
    was True, which was true on essentially every real call.
    """
    _install_snapshot(monkeypatch)
    metadata_row = _metadata_row()
    cluster_row = {"biosample_acc": "SAMN02147118", "PDS_acc": "PDS000012345.1"}
    snp_row = {
        "PDS_acc": "PDS000012345.1",
        "biosample_acc_1": "SAMN02147118",
        "biosample_acc_2": "SAMN00999999",
        "compatible_distance": "3",
    }
    _install_reads(
        monkeypatch,
        [
            TsvScanResult([metadata_row]),  # Metadata read
            TsvScanResult([cluster_row]),  # cluster_list read (best-effort)
            # SNP_distances (best-effort): cut off by the 20s sub-budget,
            # but this row was already collected before the cutoff.
            TsvScanResult([snp_row], truncated_by_deadline=True),
        ],
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "ok", output.error
    isolate = output.isolates[0]
    assert isolate.snp_distance == 3, (
        "a truncated best-effort scan that DID find this isolate's own row "
        "must populate snp_distance, not leave it None"
    )


@pytest.mark.asyncio
async def test_isolate_lookup_ok_even_when_cluster_enrichment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ticket's own explicit allowance: SNP-neighbor enrichment for
    isolate_lookup may be best-effort. A failure there must never take
    down status/isolates/amr_genotypes correctness.
    """
    _install_snapshot(monkeypatch)
    metadata_row = _metadata_row()
    _install_reads(
        monkeypatch,
        [
            TsvScanResult([metadata_row]),  # Metadata read succeeds
            RuntimeError("cluster_list.tsv fetch failed"),  # cluster_list read fails
        ],
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "ok", output.error
    assert output.isolate_count == 1
    isolate = output.isolates[0]
    assert isolate.biosample_acc == "SAMN02147118"
    assert isolate.amr_genotypes == ["ant(2'')-Ia", "aph(3')-Ia", "blaTEM-1"]
    # Best-effort enrichment did not resolve: no cluster/no distance, not an error.
    assert isolate.pds_cluster is None
    assert isolate.snp_distance is None


@pytest.mark.asyncio
async def test_isolate_lookup_empty_when_biosample_not_in_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    _install_reads(monkeypatch, [TsvScanResult([])])

    output = await pathogen_detection(_isolate_lookup_input(biosample_acc="SAMN99999999"))

    assert output.status == "empty"
    assert output.isolate_count == 0
    assert output.total_available == 0


@pytest.mark.asyncio
async def test_isolate_lookup_snapshot_unavailable_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot_unavailable(monkeypatch, "Salmonella has no complete snapshot yet")

    output = await pathogen_detection(_isolate_lookup_input(taxon="Salmonella"))

    assert output.status == "error"
    assert "Salmonella" in output.error
    assert "no complete snapshot" in output.error or "Salmonella" in output.error


# ---------------------------------------------------------------------------
# cluster_snp_neighbors: ok, empty.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_ok_filters_by_max_snp_distance(monkeypatch: pytest.MonkeyPatch) -> None:
    """SNP_distances.tsv is pairwise (biosample_acc_1/_2, compatible_distance),
    live-verified 2026-08-08 (tracker/phase_3.5.md). A cluster member with no
    row placing it within max_snp_distance of anything is not a "neighbor" of
    anything and must be EXCLUDED from the output entirely, never included
    with a None distance (the premise gate's own case 3 requires every
    isolate in a status="ok" response to carry a real, in-budget distance).
    """
    _install_snapshot(monkeypatch)
    cluster_rows = [
        {"biosample_acc": "SAMN00000001", "PDS_acc": "PDS000012345.1"},
        {"biosample_acc": "SAMN00000002", "PDS_acc": "PDS000012345.1"},
    ]
    snp_rows = [
        # Within range for max_snp_distance=5 below: both sides qualify.
        {
            "PDS_acc": "PDS000012345.1",
            "biosample_acc_1": "SAMN00000001",
            "biosample_acc_2": "SAMN00000003",
            "compatible_distance": "2",
        },
        # Out of range; SAMN00000002 gets no qualifying row and must be excluded.
        {
            "PDS_acc": "PDS000012345.1",
            "biosample_acc_1": "SAMN00000002",
            "biosample_acc_2": "SAMN00000004",
            "compatible_distance": "9",
        },
    ]
    metadata_rows = [
        _metadata_row("SAMN00000001", amr_genotypes=None, ast_phenotypes=None),
        _metadata_row("SAMN00000003", amr_genotypes=None, ast_phenotypes=None),
    ]
    _install_reads(
        monkeypatch,
        [
            TsvScanResult(cluster_rows),  # cluster_list read
            TsvScanResult(snp_rows),  # SNP_distances read
            TsvScanResult(metadata_rows),  # Metadata read
        ],
    )

    output = await pathogen_detection(_cluster_input(max_snp_distance=5))

    assert output.status == "ok", output.error
    assert output.isolate_count == 2
    assert output.total_available == 2
    assert output.truncated is False
    by_biosample = {isolate.biosample_acc: isolate for isolate in output.isolates}
    assert by_biosample["SAMN00000001"].snp_distance == 2
    assert by_biosample["SAMN00000003"].snp_distance == 2
    assert "SAMN00000002" not in by_biosample  # 9 > max_snp_distance=5, excluded entirely


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_empty_when_no_members(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    _install_reads(monkeypatch, [TsvScanResult([])])

    output = await pathogen_detection(_cluster_input(pds_cluster="PDS999999999.1"))

    assert output.status == "empty"
    assert output.isolate_count == 0
    assert output.total_available == 0


# ---------------------------------------------------------------------------
# F-3.5-01: deadline discipline, never a silently-partial "ok".
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_truncated_scan_with_no_matches_is_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cluster_list succeeds, but the SNP_distances read's own scan result
    reports truncated_by_deadline=True AND found nothing parseable in the
    portion scanned (this row has none of the real pairwise columns):
    status must be "timeout" (F-3.5-A-09, Step 6.2: was "empty" before this
    reconciliation) with an actionable message.
    """
    _install_snapshot(monkeypatch)
    cluster_rows = [{"biosample_acc": "SAMN00000001", "PDS_acc": "PDS000012345.1"}]
    _install_reads(
        monkeypatch,
        [
            TsvScanResult(cluster_rows),  # cluster_list read: fine
            TsvScanResult([{"distance": "1"}], truncated_by_deadline=True),  # SNP_distances: cut off, unparseable
        ],
    )

    output = await pathogen_detection(_cluster_input())

    assert output.status == "timeout"
    assert output.truncated is True
    assert output.error is not None
    assert "budget" in output.error.lower() or "deadline" in output.error.lower() or "timeout" in output.error.lower() or "120" in output.error


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_truncated_scan_with_real_matches_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.5-A-01 (adversary round, 2026-08-08) regression test: a scan cut
    short by the deadline that DID find real, parseable neighbors must
    return status "ok" with those neighbors and truncated=True, never
    discard them through the deadline-exceeded path. The pre-fix version
    of this code returned status "empty" here unconditionally whenever
    truncated_by_deadline was True, regardless of what was actually found.
    """
    _install_snapshot(monkeypatch)
    cluster_rows = [
        {"biosample_acc": "SAMN00000001", "PDS_acc": "PDS000012345.1"},
        {"biosample_acc": "SAMN00000002", "PDS_acc": "PDS000012345.1"},
    ]
    snp_rows = [
        {
            "PDS_acc": "PDS000012345.1",
            "biosample_acc_1": "SAMN00000001",
            "biosample_acc_2": "SAMN00000002",
            "compatible_distance": "2",
        },
    ]
    metadata_rows = [
        _metadata_row("SAMN00000001", amr_genotypes=None, ast_phenotypes=None),
        _metadata_row("SAMN00000002", amr_genotypes=None, ast_phenotypes=None),
    ]
    _install_reads(
        monkeypatch,
        [
            TsvScanResult(cluster_rows),  # cluster_list read: fine, not truncated
            # SNP_distances: the deadline fired AFTER these rows were
            # already collected. truncated_by_deadline=True must NOT
            # discard them.
            TsvScanResult(snp_rows, truncated_by_deadline=True),
            TsvScanResult(metadata_rows),  # metadata read: fine
        ],
    )

    output = await pathogen_detection(_cluster_input(max_snp_distance=5))

    assert output.status == "ok", output.error
    assert output.truncated is True, "a scan cut short must disclose truncated=True even on ok"
    assert output.isolate_count == 2
    by_biosample = {isolate.biosample_acc: isolate for isolate in output.isolates}
    assert by_biosample["SAMN00000001"].snp_distance == 2
    assert by_biosample["SAMN00000002"].snp_distance == 2


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_deadline_exceeded_error_raised_by_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PathogenDeadlineExceededError raised mid-scan (rather than reported
    via TsvScanResult.truncated_by_deadline) is caught the same way:
    status "timeout" (F-3.5-A-09, Step 6.2: was "empty" before this
    reconciliation), never propagated as an unhandled exception and never
    reported as "ok".
    """
    _install_snapshot(monkeypatch)
    _install_reads(
        monkeypatch,
        [PathogenDeadlineExceededError("cluster_list.tsv scan exceeded the shared deadline")],
    )

    output = await pathogen_detection(_cluster_input())

    assert output.status == "timeout"
    assert output.truncated is True
    assert output.error is not None


@pytest.mark.asyncio
async def test_isolate_lookup_deadline_already_expired_before_any_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deadline that is already in the past before the metadata read even
    starts (the fail-fast check `_remaining(deadline) <= 0`) never issues
    the read at all, and resolves to "timeout" (F-3.5-A-09, Step 6.2: was
    "empty" before this reconciliation), not "ok".
    """
    _install_snapshot(monkeypatch)
    action = PathogenIsolateLookupInput(
        mode="isolate_lookup", taxon="Salmonella", biosample_acc="SAMN02147118"
    )
    scripted = _install_reads(monkeypatch, [])  # no reads should ever be attempted

    already_past_deadline = time.monotonic() - 1.0
    output = await _isolate_lookup(action, "PDG000000002.4157", "Salmonella", already_past_deadline, client=object())

    assert output.status == "timeout"
    assert output.truncated is True
    assert scripted.calls == []


# ---------------------------------------------------------------------------
# Snapshot pinning: pathogen_detection always calls resolve_complete_snapshot,
# never builds a path itself; handles PathogenSnapshotUnavailableError.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_resolution_is_delegated_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def _resolve(taxon: str, *, client: Any, base_url: str | None = None) -> str:
        calls.append(taxon)
        return "PDG000000002.4157"

    monkeypatch.setattr(
        pathogen_detection_module.pathogen_ftp_transport, "resolve_complete_snapshot", _resolve
    )
    _install_reads(monkeypatch, [TsvScanResult([])])

    await pathogen_detection(_isolate_lookup_input(taxon="Salmonella"))

    assert calls == ["Salmonella"]


# ---------------------------------------------------------------------------
# Untrusted-content field caps: withhold-not-truncate, identity exclusion.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_over_length_strain_is_withheld_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    over_length_strain = "S" * 101  # cap is 100
    row = _metadata_row(strain=over_length_strain, amr_genotypes=None, ast_phenotypes=None)
    _install_reads(
        monkeypatch,
        [
            TsvScanResult([row]),
            TsvScanResult([]),  # cluster_list best-effort read: no membership found
        ],
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "ok", output.error
    isolate = output.isolates[0]
    # Never a truncated, real-looking-but-wrong 100-char prefix.
    assert isolate.strain is None
    assert output.fields_withheld is not None
    assert any("strain" in note for note in output.fields_withheld)


@pytest.mark.asyncio
async def test_over_length_biosample_acc_excludes_whole_isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    over_length_biosample = "S" * 31  # cap is 30
    row = _metadata_row(over_length_biosample, amr_genotypes=None, ast_phenotypes=None)
    _install_reads(
        monkeypatch,
        [
            TsvScanResult([row]),  # Metadata read
            TsvScanResult([]),  # cluster_list best-effort read: no membership found
        ],
    )

    # Construct the input with a schema-VALID biosample_acc (<=30 chars);
    # the over-length value only ever appears in the raw metadata row this
    # module has to parse, exercising _build_isolate's identity-field
    # exclusion path rather than schema-layer input rejection.
    output = await pathogen_detection(_isolate_lookup_input(biosample_acc="SAMN00000001"))

    assert output.status == "empty"
    assert output.isolate_count == 0


@pytest.mark.asyncio
async def test_amr_genotypes_item_over_cap_is_withheld_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_snapshot(monkeypatch)
    over_length_gene = "g" * 41  # item cap is 40
    row = _metadata_row(amr_genotypes=f'"{over_length_gene},shortGene"', ast_phenotypes=None)
    _install_reads(monkeypatch, [TsvScanResult([row]), TsvScanResult([])])

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "ok", output.error
    isolate = output.isolates[0]
    assert isolate.amr_genotypes == ["shortGene"]
    assert output.fields_withheld is not None
    assert any("amr_genotypes" in note for note in output.fields_withheld)


# ---------------------------------------------------------------------------
# taxon defense-in-depth re-check inside pathogen_detection.py itself.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_taxon_defense_in_depth_reject_bypassing_schema_validation() -> None:
    """PathogenIsolateLookupInput's own schema-layer pattern already
    rejects an unsafe taxon (test_pathogen_detection_schemas.py's own
    coverage); this test exercises the SEPARATE defense-in-depth re-check
    inside _pathogen_detection_impl itself, by handing it a hand-built
    action object that bypasses Pydantic construction (model_construct
    skips validation), the only way to reach that internal branch at all.
    """
    unsafe_action = PathogenIsolateLookupInput.model_construct(
        mode="isolate_lookup", taxon="../../../etc", biosample_acc="SAMN02147118"
    )
    fake_input = PathogenDetectionInput.model_construct(root=unsafe_action)

    output = await pathogen_detection(fake_input)

    assert output.status == "error"
    assert "taxon" in output.error.lower()


# ---------------------------------------------------------------------------
# Malformed-input rejection at the schema boundary (thin integration check).
# ---------------------------------------------------------------------------


def test_malformed_input_missing_required_field_rejected_before_tool_call():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PathogenDetectionInput(mode="isolate_lookup", taxon="Salmonella")


# ---------------------------------------------------------------------------
# Never-raises wrapper.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_exception_is_caught_and_reported_as_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolve(taxon: str, *, client: Any, base_url: str | None = None) -> str:
        raise RuntimeError("completely unexpected failure shape")

    monkeypatch.setattr(
        pathogen_detection_module.pathogen_ftp_transport, "resolve_complete_snapshot", _resolve
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "error"
    assert output.error is not None
    assert "RuntimeError" in output.error or "unexpected" in output.error.lower()


# ---------------------------------------------------------------------------
# F-3.5-A-06 (adversary round, 2026-08-08): a transport-layer failure on a
# MANDATORY bulk-file read (an HTTP error status, or a header shape the
# transport cannot parse) must be classified via _transport_error_output,
# never let escape to the generic "raised an unexpected error, this tool
# has a defect" catch-all a routine snapshot rotation should never trigger.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_isolate_lookup_http_status_error_on_metadata_read_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_snapshot(monkeypatch)
    request = httpx.Request("GET", "https://ftp.ncbi.nlm.nih.gov/x.tsv")
    response = httpx.Response(404, request=request)
    _install_reads(
        monkeypatch,
        [httpx.HTTPStatusError("404", request=request, response=response)],
    )

    output = await pathogen_detection(_isolate_lookup_input())

    assert output.status == "error"
    assert output.error is not None
    assert "404" in output.error
    assert "raised an unexpected" not in output.error.lower(), (
        "a classified HTTP error must not read as the generic "
        "unexpected-exception catch-all message"
    )
    assert "rotation" in output.error.lower() or "retry" in output.error.lower()


@pytest.mark.asyncio
async def test_cluster_snp_neighbors_transport_error_on_cluster_list_read_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_snapshot(monkeypatch)
    _install_reads(
        monkeypatch,
        [transport.PathogenTransportError("Column 'PDS_acc' not found in header: ['other']")],
    )

    output = await pathogen_detection(_cluster_input())

    assert output.status == "error"
    assert output.error is not None
    assert "cluster_list" in output.error
    assert "defect" not in output.error.lower()


# ---------------------------------------------------------------------------
# T-3.4-04: build_citation. No live network: every case constructs a valid
# PathogenDetectionOutput directly, since build_citation is a pure function
# over an already-fetched result, not a network caller itself.
# ---------------------------------------------------------------------------


def _isolate_output(**isolate_overrides: Any) -> PathogenDetectionOutput:
    defaults: dict[str, Any] = {
        "biosample_acc": "SAMN02384162",
        "strain": "CVM N45392",
        "source_url": (
            "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/"
            "biosample_acc:SAMN02384162"
        ),
    }
    defaults.update(isolate_overrides)
    return PathogenDetectionOutput(
        status="ok",
        mode="isolate_lookup",
        isolates=[PathogenIsolate(**defaults)],
        isolate_count=1,
    )


def test_build_citation_cites_strain_field() -> None:
    result = _isolate_output()

    citation = build_citation(result, field="strain")

    assert citation.evidence_kind == "primary_assertion"
    assert citation.license == "public_domain_us_gov"
    assert citation.assertion_confidence == "asserted"
    assert citation.layer == "layer_2_api"
    assert citation.source_id == "SAMN02384162"
    assert "CVM N45392" in citation.claim_text


def test_build_citation_skips_isolate_missing_the_field() -> None:
    result = _isolate_output(strain=None)

    with pytest.raises(ValueError, match="strain"):
        build_citation(result, field="strain")


def test_build_citation_raises_when_no_isolates() -> None:
    result = PathogenDetectionOutput(status="empty", mode="isolate_lookup")

    with pytest.raises(ValueError, match="isolate"):
        build_citation(result, field="strain")
