"""Streaming HTTPS transport for the NCBI Pathogen Detection FTP tree (Technical_specification.md Section 6.6).

`pathogen_detection` (T-3.5-05) is a genuinely different access pattern from
every other tool in the roster: versioned bulk TSV retrieval over
`https://ftp.ncbi.nlm.nih.gov/pathogen/Results/<Taxon>/PDG*/`, not a
parameterized Entrez/Datasets/PubChem/ClinicalTrials call. `ncbi_transport`'s
`execute_get`/`RateLimiter` machinery is for interactive, rate-limited APIs
and does not apply here: per Section 21.1, this is "not a request-rate API,
a bulk file transfer", so there is no rate-limit family in this module.

## Why a stream, never a full-body GET

Pre-build live probing (2026-08-08, `tracker/phase_3.5.md`, F-3.5-01) found
`Clusters/*.reference_target.SNP_distances.tsv` at roughly 411 GB for the
`Salmonella` snapshot, three orders of magnitude past what Section 6.6's
"bulk TSV" framing implies. `system-design-patterns` rule 7 already forbids
inlining a large result set into agent context; this module enforces the
stronger requirement underneath that one, that the file body itself is never
fully buffered in this process either, success or failure. Every read in
this module streams the response body line by line (`httpx`'s
`aiter_lines()` under a `stream=True` GET) and filters as it goes; nothing
here ever calls `.text` or `.content` on a response that could be a bulk
TSV.

## The wall-clock deadline, not a fixed row cap

The server confirmed `Accept-Ranges: bytes`, but three widely-spaced `Range`
samples showed rows grouped into contiguous per-`PDS_acc` blocks that are
NOT globally sorted by cluster id, so a byte-offset binary search cannot
jump directly to an arbitrary cluster's block without a prior index this
tree does not publish. The only correct approach within the tool's own
60-second-or-more budget (`.claude/rules/tool-call-budgets.md`) is a
streamed scan bounded by a shared wall-clock deadline, passed in by the
caller as an absolute `time.monotonic()` value so multiple calls within one
tool invocation (a snapshot-listing check, then a metadata read, then a
cluster read) all draw against the same total budget rather than each
getting its own fresh clock. `stream_filtered_tsv_rows` returns whether it
was cut off by the deadline (`truncated_by_deadline`) or genuinely reached
end of file, so the caller can tell "found everything there is" from "ran
out of time looking", and never reports the second as the first.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Final

import httpx

logger = logging.getLogger(__name__)

PATHOGEN_FTP_BASE: Final[str] = "https://ftp.ncbi.nlm.nih.gov/pathogen/Results"

# Section 6.6: "60 seconds or more... the binding constraint is transfer
# time and snapshot pinning, not requests per second." This is the default
# for a single streamed read; callers doing multiple reads within one tool
# invocation pass an explicit deadline (see the module docstring) rather
# than relying on this default for the whole invocation.
DEFAULT_TIMEOUT_S: Final[float] = 60.0

REQUIRED_SNAPSHOT_SUBDIRS: Final[tuple[str, ...]] = ("Metadata", "Clusters", "AMR")

_SNAPSHOT_DIR_PATTERN: Final[re.Pattern[str]] = re.compile(r'href="(PDG\d+\.\d+)/"')
_SUBDIR_PATTERN: Final[re.Pattern[str]] = re.compile(r'href="([A-Za-z]+)/"')

# A directory index page is small (a few KB of HTML), never a bulk TSV, so
# reading it in full with .text is safe and is the only practical way to
# parse an Apache autoindex listing.
_DIRECTORY_LISTING_TIMEOUT_S: Final[float] = 15.0


class PathogenTransportError(Exception):
    """Base class for every error this module raises."""


class PathogenSnapshotUnavailableError(PathogenTransportError):
    """No COMPLETE snapshot (Metadata+Clusters+AMR all present) was found for a taxon."""


class PathogenDeadlineExceededError(PathogenTransportError):
    """The caller's wall-clock deadline had already passed before this call could start."""


@dataclass(frozen=True)
class TsvScanResult:
    rows: list[dict[str, str]] = field(default_factory=list)
    truncated_by_deadline: bool = False
    total_rows_scanned: int = 0


async def _get_directory_listing(
    url: str, *, client: httpx.AsyncClient
) -> str:
    response = await client.get(url, timeout=_DIRECTORY_LISTING_TIMEOUT_S)
    response.raise_for_status()
    return response.text


async def resolve_complete_snapshot(
    taxon: str,
    *,
    client: httpx.AsyncClient,
    base_url: str = PATHOGEN_FTP_BASE,
) -> str:
    """Return the newest snapshot directory name (e.g. "PDG000000002.4177") whose
    Metadata/, Clusters/, and AMR/ subdirectories are all present.

    Never returns a snapshot with only Metadata/ populated (Section 6.6's
    own named trap, live-reproduced 2026-08-08 on the Salmonella tree: the
    two newest snapshots at the time carried Metadata/ alone). Walks
    newest-to-oldest by the numeric suffix, checking each candidate's
    subdirectories, and returns the first complete one found.
    """
    taxon_url = f"{base_url}/{taxon}/"
    try:
        listing = await _get_directory_listing(taxon_url, client=client)
    except httpx.HTTPStatusError as exc:
        # F-3.5-08 (judge round, 2026-08-08): an unknown taxon is a routine,
        # expected condition (a caller-supplied string that does not name a
        # real FTP folder), not a transport defect. Classify it as the
        # named condition Section 6.6 itself expects ("the snapshot
        # directory is unreachable... for taxon") instead of letting an
        # httpx exception escape uncaught to the tool's last-resort catch,
        # which reported it as "an unexpected error" rather than a
        # structured, actionable one.
        raise PathogenSnapshotUnavailableError(
            f"No taxon directory found at {taxon_url} "
            f"(HTTP {exc.response.status_code}). Confirm '{taxon}' matches the "
            "FTP tree's folder name exactly, including case."
        ) from exc
    candidates = sorted(
        set(_SNAPSHOT_DIR_PATTERN.findall(listing)),
        key=lambda name: tuple(int(part) for part in name.split(".")[1:] or ["0"]),
        reverse=True,
    )
    if not candidates:
        raise PathogenSnapshotUnavailableError(
            f"No PDG snapshot directory found under {taxon_url}. "
            "Confirm the taxon folder name matches the FTP tree exactly (case-sensitive)."
        )

    for snapshot in candidates:
        try:
            snapshot_listing = await _get_directory_listing(
                f"{taxon_url}{snapshot}/", client=client
            )
        except httpx.HTTPStatusError:
            # A snapshot directory named in the taxon-level listing but
            # unreachable by the time it is checked (a race with the
            # underlying tree's own build cadence, Section 6.6): treat it
            # the same as an incomplete snapshot, never a crash.
            logger.info(
                "pathogen_detection: snapshot %s for taxon %s listed but "
                "unreachable, skipping",
                snapshot, taxon,
            )
            continue
        present = set(_SUBDIR_PATTERN.findall(snapshot_listing))
        if all(subdir in present for subdir in REQUIRED_SNAPSHOT_SUBDIRS):
            return snapshot
        logger.info(
            "pathogen_detection: skipping incomplete snapshot %s for taxon %s "
            "(present: %s, required: %s)",
            snapshot, taxon, sorted(present), REQUIRED_SNAPSHOT_SUBDIRS,
        )

    raise PathogenSnapshotUnavailableError(
        f"No COMPLETE snapshot (Metadata+Clusters+AMR all present) found for taxon "
        f"'{taxon}' among {len(candidates)} candidate(s). The newest snapshots may "
        "still be mid-build; retry later or check the taxon's own FTP tree directly."
    )


async def stream_filtered_tsv_rows(
    url: str,
    *,
    key_column: str,
    key_values: Collection[str],
    deadline: float,
    client: httpx.AsyncClient,
    max_matches: int | None = None,
    one_row_per_key: bool = False,
) -> TsvScanResult:
    """Stream a tab-separated file, yielding every row whose `key_column` value is
    in `key_values`. Never buffers the full response body: reads line by line
    via a streaming GET, and stops at whichever comes first: `max_matches`
    rows have been collected, `deadline` (an absolute `time.monotonic()`
    value) passes, or (only when `one_row_per_key` is True) every value in
    `key_values` has been seen at least once.

    `deadline` is a shared budget across however many calls the caller
    makes within one tool invocation, not a fresh per-call timeout: pass
    `time.monotonic() + tool_budget_s` once per tool invocation and reuse
    the same value across every `stream_filtered_tsv_rows` call it makes.

    `one_row_per_key`: this file's `key_column` is NOT necessarily unique
    per value; a single value can legitimately head many rows (every
    isolate in a PDS cluster shares one `PDS_acc`, every pairwise
    SNP-distance comparison within that cluster shares it too). The
    default, `False`, collects EVERY matching row regardless of how many
    rows share a key value, bounded only by `max_matches`/`deadline`/EOF.
    Set `True` only when the caller knows `key_column` is genuinely unique
    per row (a point lookup by an id column such as `biosample_acc` in
    Metadata, where each accession appears at most once) and wants the
    scan to stop early once every requested id has been found, rather
    than reading needlessly further into the file. Getting this backwards
    is silent and dangerous in exactly one direction: `True` on a
    non-unique column returns the FIRST matching row and calls the
    (incomplete) result complete. This was a real, live-confirmed defect
    (`tracker/phase_3.5.md`'s F-3.5-06, 2026-08-08 judge round): both
    cluster-scoped reads in `pathogen_detection.py` were filtering
    `PDS_acc`, a column many rows share, through what was then unconditional
    one-row-per-key behavior, so `cluster_snp_neighbors` reported a cluster
    of 4 real isolates as 2, with `truncated: false`.
    """
    if time.monotonic() >= deadline:
        raise PathogenDeadlineExceededError(
            f"Wall-clock deadline already exceeded before starting a read of {url}."
        )

    remaining_keys = set(key_values)
    key_values_set = set(key_values)
    matched: list[dict[str, str]] = []
    total_scanned = 0
    truncated = False
    header: list[str] | None = None
    key_index: int | None = None

    remaining_s = max(deadline - time.monotonic(), 0.1)
    async with client.stream("GET", url, timeout=remaining_s) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if time.monotonic() >= deadline:
                truncated = True
                break
            if header is None:
                header = line.split("\t")
                try:
                    key_index = header.index(key_column)
                except ValueError as exc:
                    raise PathogenTransportError(
                        f"Column '{key_column}' not found in {url}'s header: {header}"
                    ) from exc
                continue
            if not line:
                continue
            total_scanned += 1
            fields = line.split("\t")
            if key_index >= len(fields):
                continue
            value = fields[key_index]
            if value not in key_values_set:
                continue
            matched.append(dict(zip(header, fields, strict=False)))
            if max_matches and len(matched) >= max_matches:
                break
            if one_row_per_key:
                remaining_keys.discard(value)
                if not remaining_keys:
                    break

    return TsvScanResult(
        rows=matched, truncated_by_deadline=truncated, total_rows_scanned=total_scanned
    )
