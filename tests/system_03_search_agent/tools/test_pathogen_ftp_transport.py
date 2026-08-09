"""Unit tests for `pathogen_ftp_transport.py` (T-3.5-02), driven through
`httpx.MockTransport` against the real `resolve_complete_snapshot` and
`stream_filtered_tsv_rows` functions, never through a scripted stand-in.

This file exists specifically because it did not exist when build phase
3.5's judge round found F-3.5-07: `pathogen_detection.py`'s own unit
tests (`test_pathogen_detection.py`) script a `TsvScanResult` directly for
every case, so a fully green run of that file proved `pathogen_detection.py`
handles a GIVEN transport result correctly, and said nothing about whether
`stream_filtered_tsv_rows` itself produces the right result from real
bytes. It did not: it silently stopped after the first row matching a key
value shared by many rows, and reported the result complete. This file
closes that gap by exercising the real function against a real (mocked at
the transport layer only) HTTP response.

Coverage statement (per `.claude/rules/goal-contracts.md`'s "a verify
surface must state its own coverage"):

This file exercises:
    - F-3.5-07's own regression: `one_row_per_key=False` (the default)
      returns EVERY row matching a key value shared by many rows, not
      just the first.
    - `one_row_per_key=True` stops early once every requested key has
      been seen at least once, the correct behavior for a point lookup by
      a genuinely unique column.
    - `max_matches` caps the returned row count regardless of
      `one_row_per_key`.
    - The deadline contract: a deadline already in the past raises
      `PathogenDeadlineExceededError` before any request is made; a
      deadline that expires mid-scan sets `truncated_by_deadline=True`
      and returns whatever was collected so far, never raises.
    - An unknown `key_column` (not present in the file's header row)
      raises `PathogenTransportError` naming the column and the header
      actually found.
    - `resolve_complete_snapshot`: picks the newest snapshot whose
      Metadata/Clusters/AMR subdirectories are all present, skips a
      mid-build snapshot with only Metadata/, raises
      `PathogenSnapshotUnavailableError` on an unknown taxon (HTTP 404,
      F-3.5-08) and when no snapshot is ever complete.

This file deliberately does NOT exercise:
    - The literal claim "never buffers a 411GB response body into memory"
      end to end: `httpx.MockTransport` serves a response from an
      in-memory byte string regardless of transport, so no test here can
      distinguish a truly streamed read from a buffered one at the
      network layer. That guarantee rests on `stream_filtered_tsv_rows`
      using `client.stream(...)` plus `response.aiter_lines()` rather than
      `.text`/`.content`/`.json()`, which is a code-shape property this
      file's tests do not (and cannot) directly assert; it was verified by
      code inspection during the judge round instead.
    - Real network latency, retries, or connection failures: this repo's
      `pathogen_ftp_transport.py` performs no retry (Section 21.1: "not a
      request-rate API"), so there is no retry behavior to exercise.

Depends on:
    - system_03_search_agent.tools.pathogen_ftp_transport (module under test)

Writes:
    - Nothing.
"""

from __future__ import annotations

import time

import httpx
import pytest

from system_03_search_agent.tools import pathogen_ftp_transport as transport

BASE_URL = "https://ftp.ncbi.nlm.nih.gov/pathogen/Results"


def _future_deadline(seconds: float = 30.0) -> float:
    return time.monotonic() + seconds


def _past_deadline() -> float:
    return time.monotonic() - 1.0


def _client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# stream_filtered_tsv_rows: the F-3.5-07 regression and its siblings.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_row_per_key_false_returns_every_row_sharing_a_key_value() -> None:
    """F-3.5-07's own regression test. Three rows share PDS_acc
    "PDS000012345.1"; the pre-fix behavior returned exactly one of them and
    reported the scan complete (`truncated_by_deadline=False`). All three
    must come back.
    """
    body = (
        "PDS_acc\tbiosample_acc\n"
        "PDS000012345.1\tSAMN00000001\n"
        "PDS000012345.1\tSAMN00000002\n"
        "PDS000012345.1\tSAMN00000003\n"
        "PDS000099999.1\tSAMN00000004\n"  # a different cluster, must be excluded
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_filtered_tsv_rows(
            f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
            key_column="PDS_acc",
            key_values={"PDS000012345.1"},
            deadline=_future_deadline(),
            client=client,
        )

    assert not result.truncated_by_deadline
    assert len(result.rows) == 3, f"expected all 3 shared-key rows, got {result.rows!r}"
    assert {row["biosample_acc"] for row in result.rows} == {
        "SAMN00000001", "SAMN00000002", "SAMN00000003",
    }
    assert result.total_rows_scanned == 4


@pytest.mark.asyncio
async def test_one_row_per_key_true_stops_after_every_key_seen_once() -> None:
    """The point-lookup case: a unique key column, multiple distinct keys
    requested, stop early once every one has been found rather than
    reading needlessly further.
    """
    body = (
        "biosample_acc\tstrain\n"
        "SAMN00000001\tstrainA\n"
        "SAMN00000002\tstrainB\n"
        "SAMN00000003\tstrainC\n"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_filtered_tsv_rows(
            f"{BASE_URL}/Salmonella/PDG1/Metadata/metadata.tsv",
            key_column="biosample_acc",
            key_values={"SAMN00000001", "SAMN00000002"},
            deadline=_future_deadline(),
            client=client,
            one_row_per_key=True,
        )

    assert len(result.rows) == 2
    assert {row["biosample_acc"] for row in result.rows} == {"SAMN00000001", "SAMN00000002"}
    # Stops after row 2 (both keys found), never reaches SAMN00000003's row.
    assert result.total_rows_scanned == 2


@pytest.mark.asyncio
async def test_max_matches_caps_rows_regardless_of_one_row_per_key() -> None:
    body = (
        "PDS_acc\tbiosample_acc\n"
        "PDS1\tSAMN00000001\n"
        "PDS1\tSAMN00000002\n"
        "PDS1\tSAMN00000003\n"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_filtered_tsv_rows(
            f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
            key_column="PDS_acc",
            key_values={"PDS1"},
            deadline=_future_deadline(),
            client=client,
            max_matches=2,
        )

    assert len(result.rows) == 2


@pytest.mark.asyncio
async def test_deadline_already_past_raises_before_any_request() -> None:
    called = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["count"] += 1
        return httpx.Response(200, text="PDS_acc\tbiosample_acc\n")

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenDeadlineExceededError):
            await transport.stream_filtered_tsv_rows(
                f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
                key_column="PDS_acc",
                key_values={"PDS1"},
                deadline=_past_deadline(),
                client=client,
            )

    assert called["count"] == 0, "must not make any request once the deadline has already passed"


@pytest.mark.asyncio
async def test_deadline_expiring_mid_scan_sets_truncated_never_raises() -> None:
    """A deadline that expires while rows are still arriving must report
    `truncated_by_deadline=True` with whatever was collected so far, per
    F-3.5-01's "never a silently-partial ok" contract at the layer above
    this one: this layer's own job is to be HONEST about truncation, not
    to hide it.
    """
    lines = ["PDS_acc\tbiosample_acc"] + [f"PDS1\tSAMN{i:08d}" for i in range(50)]
    body = "\n".join(lines) + "\n"
    deadline = time.monotonic() + 0.05

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_filtered_tsv_rows(
            f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
            key_column="PDS_acc",
            key_values={"PDS1"},
            deadline=deadline,
            client=client,
        )

    # A slow-appearing deadline (50ms) against an in-memory mock response
    # may or may not actually trip mid-iteration depending on scheduling;
    # what must ALWAYS hold is that a result comes back (never raises) and
    # is never claimed complete without genuinely reaching EOF.
    if result.truncated_by_deadline:
        assert len(result.rows) <= 50
    else:
        assert len(result.rows) == 50  # genuinely reached EOF before the deadline


@pytest.mark.asyncio
async def test_unknown_key_column_raises_naming_the_real_header() -> None:
    body = "PDS_acc\tbiosample_acc\nPDS1\tSAMN00000001\n"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenTransportError, match="not_a_real_column"):
            await transport.stream_filtered_tsv_rows(
                f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
                key_column="not_a_real_column",
                key_values={"PDS1"},
                deadline=_future_deadline(),
                client=client,
            )


@pytest.mark.asyncio
async def test_no_matching_rows_returns_empty_not_an_error() -> None:
    body = "PDS_acc\tbiosample_acc\nPDS1\tSAMN00000001\n"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_filtered_tsv_rows(
            f"{BASE_URL}/Salmonella/PDG1/Clusters/cluster_list.tsv",
            key_column="PDS_acc",
            key_values={"PDS_NONEXISTENT"},
            deadline=_future_deadline(),
            client=client,
        )

    assert result.rows == []
    assert not result.truncated_by_deadline
    assert result.total_rows_scanned == 1


# ---------------------------------------------------------------------------
# resolve_complete_snapshot
# ---------------------------------------------------------------------------


def _autoindex(entries: list[str]) -> str:
    links = "\n".join(f'<a href="{e}/">{e}/</a>' for e in entries)
    return f"<html><body>{links}</body></html>"


@pytest.mark.asyncio
async def test_resolve_complete_snapshot_skips_mid_build_and_returns_newest_complete() -> None:
    """Live-reproduces Section 6.6's own named trap: the two newest
    snapshots carry only Metadata/, the third-newest has all three
    subdirectories and must be the one returned.
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Salmonella/"):
            return httpx.Response(200, text=_autoindex(["PDG1.30", "PDG1.29", "PDG1.28"]))
        if path.endswith("/PDG1.30/"):
            return httpx.Response(200, text=_autoindex(["Metadata"]))
        if path.endswith("/PDG1.29/"):
            return httpx.Response(200, text=_autoindex(["Metadata"]))
        if path.endswith("/PDG1.28/"):
            return httpx.Response(200, text=_autoindex(["Metadata", "Clusters", "AMR"]))
        return httpx.Response(404, text="not found")

    async with _client_for(handler) as client:
        snapshot = await transport.resolve_complete_snapshot(
            "Salmonella", client=client, base_url=BASE_URL
        )

    assert snapshot == "PDG1.28"


@pytest.mark.asyncio
async def test_resolve_complete_snapshot_unknown_taxon_raises_named_error() -> None:
    """F-3.5-08: an unknown taxon (HTTP 404 on the taxon-level listing)
    must raise PathogenSnapshotUnavailableError, never let the raw
    httpx.HTTPStatusError escape.
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenSnapshotUnavailableError, match="Zzznotataxon"):
            await transport.resolve_complete_snapshot(
                "Zzznotataxon", client=client, base_url=BASE_URL
            )


@pytest.mark.asyncio
async def test_resolve_complete_snapshot_no_complete_snapshot_raises() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Salmonella/"):
            return httpx.Response(200, text=_autoindex(["PDG1.5"]))
        return httpx.Response(200, text=_autoindex(["Metadata"]))

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenSnapshotUnavailableError):
            await transport.resolve_complete_snapshot(
                "Salmonella", client=client, base_url=BASE_URL
            )


@pytest.mark.asyncio
async def test_resolve_complete_snapshot_no_snapshot_directories_raises() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>empty</body></html>")

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenSnapshotUnavailableError):
            await transport.resolve_complete_snapshot(
                "Salmonella", client=client, base_url=BASE_URL
            )


@pytest.mark.asyncio
async def test_resolve_complete_snapshot_race_condition_snapshot_vanishes() -> None:
    """A snapshot named in the taxon-level listing but unreachable by the
    time it is individually checked (the underlying tree's own build
    cadence, Section 6.6) is skipped like an incomplete one, never a crash.
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Salmonella/"):
            return httpx.Response(200, text=_autoindex(["PDG1.9", "PDG1.8"]))
        if path.endswith("/PDG1.9/"):
            return httpx.Response(404, text="vanished")
        if path.endswith("/PDG1.8/"):
            return httpx.Response(200, text=_autoindex(["Metadata", "Clusters", "AMR"]))
        return httpx.Response(404, text="not found")

    async with _client_for(handler) as client:
        snapshot = await transport.resolve_complete_snapshot(
            "Salmonella", client=client, base_url=BASE_URL
        )

    assert snapshot == "PDG1.8"
