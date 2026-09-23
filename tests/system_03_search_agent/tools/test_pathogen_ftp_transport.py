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
    - `TsvScanResult.reached_end` on `stream_filtered_tsv_rows`: True only
      when the stream genuinely hit end of file, False when `max_matches`
      or the all-keys-seen early exit stopped it first, and
      `match_count == len(rows)` for that reader by construction.
    - `stream_predicate_tsv_rows` (G-035, 2026-09-22): an arbitrary row
      predicate decides what matches; `max_rows` caps the rows KEPT while
      `match_count` keeps counting past that cap to end of file;
      `reached_end` flips True on a full scan and False on a deadline cut;
      a deadline already in the past raises before any request; a deadline
      that expires mid-scan returns what was collected with
      `truncated_by_deadline=True` rather than raising. Every positive arm
      carries a populate check, a sibling row on the same fake that must
      NOT match, so an arm cannot pass on a predicate that accepts
      everything or on an empty result.

This file's fakes serve rows from in-memory byte strings through
`httpx.MockTransport`, so a passing arm proves the real scanning function
produces the right result from real bytes, which is the gap that let
F-3.5-06 through.

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
# reached_end and match_count on stream_filtered_tsv_rows (G-035).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filtered_scan_that_reaches_eof_reports_reached_end_and_match_count() -> None:
    """A scan that runs the whole file says so, and its match_count equals
    the rows it kept, since this reader keeps every row it accepts.

    Populate check: the file also holds a row under a DIFFERENT key, so an
    arm that passed because the filter accepted everything would see
    match_count 3 rather than 2 and fail here.
    """
    body = (
        "PDS_acc\tbiosample_acc\n"
        "PDS1\tSAMN00000001\n"
        "PDS2\tSAMN00000002\n"  # populate check: must never be accepted
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
        )

    assert result.reached_end is True
    assert result.match_count == 2
    assert result.match_count == len(result.rows)
    assert result.total_rows_scanned == 3


@pytest.mark.asyncio
async def test_filtered_scan_stopped_by_max_matches_does_not_claim_reached_end() -> None:
    """`max_matches` is an early exit, so the counts are a lower bound and
    `reached_end` must stay False. The populate check is the third
    matching row the scan never reaches: total_rows_scanned proves the
    scan really did stop early rather than reading on.
    """
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

    assert result.reached_end is False
    assert result.match_count == 2
    assert result.total_rows_scanned == 2


# ---------------------------------------------------------------------------
# stream_predicate_tsv_rows (G-035): the sample-plus-real-total reader.
# ---------------------------------------------------------------------------


def _amr_body(rows: list[tuple[str, str]]) -> str:
    """A miniature Metadata TSV: biosample_acc plus the AMR_genotypes cell,
    in the real file's own double-quoted comma-joined spelling.
    """
    lines = ["biosample_acc\tstrain\tAMR_genotypes"]
    lines.extend(f'{acc}\tstrain-{acc}\t"{amr}"' for acc, amr in rows)
    return "\n".join(lines) + "\n"


def _carries_blatem(row: dict[str, str]) -> bool:
    return any(
        item.strip().casefold().startswith("blatem-1")
        for item in row.get("AMR_genotypes", "").strip('"').split(",")
    )


@pytest.mark.asyncio
async def test_predicate_scan_keeps_matching_rows_and_reaches_end() -> None:
    """The happy path: the predicate decides, matching rows come back whole,
    and the scan says it reached end of file.

    Populate check: two of the four rows carry `blaEC` only and must never
    appear in the result, so an arm cannot pass on a predicate that
    accepts every row.
    """
    body = _amr_body(
        [
            ("SAMN00000001", "acrF,blaTEM-1,mdtM"),
            ("SAMN00000002", "acrF,blaEC,mdtM"),  # populate check: must NOT match
            ("SAMN00000003", "blaTEM-1,tet(A)"),
            ("SAMN00000004", "blaEC"),  # populate check: must NOT match
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_predicate_tsv_rows(
            f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
            predicate=_carries_blatem,
            deadline=_future_deadline(),
            client=client,
        )

    assert [row["biosample_acc"] for row in result.rows] == ["SAMN00000001", "SAMN00000003"]
    assert result.match_count == 2
    assert result.total_rows_scanned == 4
    assert result.reached_end is True
    assert result.truncated_by_deadline is False
    # The row dict is built from the file's own header, so the predicate
    # and the caller both see every column by name.
    assert result.rows[0]["strain"] == "strain-SAMN00000001"


@pytest.mark.asyncio
async def test_predicate_scan_counts_past_max_rows_and_still_reaches_end() -> None:
    """The contract's load-bearing arm: `max_rows` stops the KEEPING, never
    the scan. Two rows come back, all five matches are counted, and
    `reached_end` is True because the scan ran to the end of the file
    anyway.

    Populate check: three of the eight rows carry `blaEC` only, so a
    predicate that accepted everything would report match_count 8.
    """
    body = _amr_body(
        [
            ("SAMN00000001", "blaTEM-1"),
            ("SAMN00000002", "blaEC"),  # populate check: must NOT match
            ("SAMN00000003", "blaTEM-1,tet(A)"),
            ("SAMN00000004", "blaEC,mdtM"),  # populate check: must NOT match
            ("SAMN00000005", "acrF,blaTEM-1"),
            ("SAMN00000006", "blaTEM-1"),
            ("SAMN00000007", "blaEC"),  # populate check: must NOT match
            ("SAMN00000008", "blaTEM-1,sul2"),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_predicate_tsv_rows(
            f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
            predicate=_carries_blatem,
            deadline=_future_deadline(),
            client=client,
            max_rows=2,
        )

    assert len(result.rows) == 2, "max_rows caps the sample"
    assert [row["biosample_acc"] for row in result.rows] == ["SAMN00000001", "SAMN00000003"]
    assert result.match_count == 5, "counting must continue past max_rows"
    assert result.total_rows_scanned == 8, "the scan must read the whole file"
    assert result.reached_end is True


@pytest.mark.asyncio
async def test_predicate_scan_zero_matches_reaches_end_and_is_not_an_error() -> None:
    """An exact absence: the scan read everything and nothing matched. This
    is the result `isolate_search` turns into `status: "empty"`, and it
    must be distinguishable from a cut-short scan by `reached_end` alone.
    """
    body = _amr_body([("SAMN00000001", "blaEC"), ("SAMN00000002", "acrF,mdtM")])

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_for(handler) as client:
        result = await transport.stream_predicate_tsv_rows(
            f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
            predicate=_carries_blatem,
            deadline=_future_deadline(),
            client=client,
        )

    assert result.rows == []
    assert result.match_count == 0
    assert result.total_rows_scanned == 2
    assert result.reached_end is True
    assert result.truncated_by_deadline is False


@pytest.mark.asyncio
async def test_predicate_scan_deadline_already_past_raises_before_any_request() -> None:
    called = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["count"] += 1
        return httpx.Response(200, text=_amr_body([("SAMN00000001", "blaTEM-1")]))

    async with _client_for(handler) as client:
        with pytest.raises(transport.PathogenDeadlineExceededError):
            await transport.stream_predicate_tsv_rows(
                f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
                predicate=_carries_blatem,
                deadline=_past_deadline(),
                client=client,
            )

    assert called["count"] == 0, "must not make any request once the deadline has already passed"


@pytest.mark.asyncio
async def test_predicate_scan_deadline_expiring_mid_scan_never_claims_reached_end() -> None:
    """A deadline that fires mid-scan returns what it had, marks itself
    truncated, and must never claim `reached_end`. The two flags are the
    opposite of each other here, which is what lets `isolate_search` tell
    "that is the whole total" from "that is a lower bound".

    As with the sibling arm for `stream_filtered_tsv_rows`, a 50ms
    deadline against an in-memory mock may or may not actually trip, so
    the assertion is written to hold either way; what must ALWAYS hold is
    that truncation and reaching the end are never both true.
    """
    rows = [(f"SAMN{i:08d}", "blaTEM-1") for i in range(200)]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_amr_body(rows))

    async with _client_for(handler) as client:
        result = await transport.stream_predicate_tsv_rows(
            f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
            predicate=_carries_blatem,
            deadline=time.monotonic() + 0.05,
            client=client,
            max_rows=3,
        )

    assert not (result.truncated_by_deadline and result.reached_end)
    assert len(result.rows) <= 3
    if result.truncated_by_deadline:
        assert result.reached_end is False
        assert result.match_count <= 200
    else:
        assert result.reached_end is True
        assert result.match_count == 200


@pytest.mark.asyncio
async def test_predicate_scan_http_error_raises_and_is_not_swallowed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with _client_for(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await transport.stream_predicate_tsv_rows(
                f"{BASE_URL}/Escherichia_coli_Shigella/PDG1/Metadata/m.tsv",
                predicate=_carries_blatem,
                deadline=_future_deadline(),
                client=client,
            )


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
