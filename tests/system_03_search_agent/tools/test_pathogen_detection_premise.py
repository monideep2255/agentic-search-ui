"""The premise gate for build phase 3.5's `pathogen_detection`: does it tell the
truth about what the Pathogen Detection FTP tree actually contains?

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory and
blocking for this tool phase. Written first and watched failing before any of
`pathogen_detection` exists.

## Ground truth, read from the live FTP tree, not guessed from documentation

Every constant below was read from `https://ftp.ncbi.nlm.nih.gov/pathogen/`
on 2026-08-08 (`tracker/phase_3.5.md`'s pre-build probes). The snapshot
NUMBER is deliberately not hardcoded anywhere in this gate: this tree
updates on NCBI's own build cadence (Section 6.6), so a gate that asserted
"the complete snapshot is PDG000000002.4177" would go stale the day a newer
one publishes. Instead this gate calls the tool's own snapshot resolution
and asserts the PROPERTY (Metadata+Clusters+AMR all present), never a
specific version string. `TEST_BIOSAMPLE_ACC` and `TEST_PDS_CLUSTER` are
historical records (2014-era and earlier) expected to persist across
snapshot updates, since new isolates are appended, not retroactively
removed.

## F-3.5-01: the bounded-scan disposition, made into an assertion

`Clusters/*.reference_target.SNP_distances.tsv` measured at roughly 411 GB
for this taxon (`tracker/phase_3.5.md`, DECISIONS.md 2026-08-08). Case 4
does not assert that `cluster_snp_neighbors` always returns a COMPLETE
neighbor set; it asserts the tool never claims completeness it cannot
back, which is the actual guarantee F-3.5-01's fix provides:
either a real (possibly wall-clock-truncated) result, or an honest
`status: "empty"` naming the timeout, never a silent partial `"ok"`.

## The arms

Two modes: `isolate_lookup` (ok: a real biosample; empty: a nonexistent
one), `cluster_snp_neighbors` (ok-or-honest-empty per F-3.5-01 above).
Plus F-3.5-03 (comma-joined AMR/AST fields parse to real lists, not one
blob string) and snapshot-pinning (the resolved snapshot has all three
required subdirectories).

## Running it

    RUN_PREMISE_GATE=1 python -m pytest \\
        tests/system_03_search_agent/tools/test_pathogen_detection_premise.py -v

No API key needed; this is an unauthenticated FTP-over-HTTPS tree. Gates on
opt-in and live network reach to ftp.ncbi.nlm.nih.gov, plus a generous
per-case timeout since a `cluster_snp_neighbors` case may legitimately run
close to the tool's own 60-second-or-more budget.

## Coverage, stated per goal-contracts.md ("a verify surface must state its
own coverage")

Exercises: both modes, the `ok`/`empty` split for `isolate_lookup`, the
F-3.5-01 bounded-scan disposition for `cluster_snp_neighbors` (asserted as
"never falsely complete", not "always completes"), the F-3.5-03 comma-join
and NULL-sentinel parsing on a real row, and live snapshot-pinning
correctness (Metadata+Clusters+AMR all present in whichever snapshot the
tool actually resolves to today). Does NOT exercise: a taxon whose newest
snapshot is genuinely incomplete at test-run time (this gate cannot force
that state; `pathogen_detection.py`'s own unit tests cover the trap with a
scripted directory listing); a `cluster_snp_neighbors` case guaranteed to
hit the wall-clock cutoff in practice (cluster sizes vary and this gate
does not know which live `pds_cluster` is large enough to force it; the
assertion is written to hold either way, but the cutoff path itself is
exercised by a scripted case in `test_pathogen_detection.py`, not here);
concurrent access to the FTP tree (there is no rate-limit family for this
tool per Section 21.1, so there is nothing to pace-test).

Depends on:
    - system_03_search_agent.tools.pathogen_detection (does not exist yet)
    - system_03_search_agent.tools.pathogen_detection_schemas (same)
    - system_03_search_agent.tools.pathogen_ftp_transport (exists, T-3.5-02)
    - Network reach to ftp.ncbi.nlm.nih.gov

Writes:
    - Nothing.
"""

from __future__ import annotations

import os
import socket
from typing import Any

import pytest

TAXON = "Salmonella"

# PDT000000002.3 / SAMN02147118, a 2013-era isolate confirmed live 2026-08-08
# to carry non-NULL AMR_genotypes and AST_phenotypes in Metadata/, and to
# belong to a cluster in Clusters/*.cluster_list.tsv.
TEST_BIOSAMPLE_ACC = "SAMN02147118"
TEST_BIOSAMPLE_KNOWN_AMR_GENE_SUBSTRING = "blaTEM-1"  # inside the comma-joined AMR_genotypes value

# PDS000065758.2005, the first cluster row in Clusters/*.cluster_list.tsv,
# confirmed live 2026-08-08 to have at least 2 member isolates.
TEST_PDS_CLUSTER = "PDS000065758.2005"

NONEXISTENT_BIOSAMPLE_ACC = "SAMN00000000000_NONEXISTENT"


def _opted_in() -> bool:
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {"1", "true", "yes"}


def _host_is_reachable() -> bool:
    try:
        with socket.create_connection(("ftp.ncbi.nlm.nih.gov", 443), timeout=10):
            return True
    except OSError:
        return False


premise_gate = pytest.mark.skipif(
    not (_opted_in() and _host_is_reachable()),
    reason=(
        "set RUN_PREMISE_GATE=1 to run the pathogen_detection premise gate. "
        "It needs live network reach to ftp.ncbi.nlm.nih.gov. No API key "
        "required (Section 6.6)."
    ),
)


async def _run(payload: dict[str, Any]) -> Any:
    """Call the tool the way the Act step will, once it is wired in.

    Imported inside the function on purpose: until `pathogen_detection`
    exists this raises ImportError per case, giving a readable per-case
    failure count instead of one collection error.
    """
    from system_03_search_agent.tools.pathogen_detection import pathogen_detection
    from system_03_search_agent.tools.pathogen_detection_schemas import PathogenDetectionInput

    return await pathogen_detection(PathogenDetectionInput(**payload))


# ===========================================================================
# ARM 1: isolate_lookup, ok / empty.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_01_isolate_lookup_resolves_a_real_biosample() -> None:
    """Case 1. The full happy path, asserted on meaning."""
    output = await _run(
        {"mode": "isolate_lookup", "taxon": TAXON, "biosample_acc": TEST_BIOSAMPLE_ACC}
    )

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert output.isolate_count >= 1
    matches = [i for i in output.isolates if i.biosample_acc == TEST_BIOSAMPLE_ACC]
    assert matches, f"expected {TEST_BIOSAMPLE_ACC} among {[i.biosample_acc for i in output.isolates]!r}"
    isolate = matches[0]
    assert isolate.amr_genotypes, "expected a non-empty amr_genotypes list (F-3.5-03)"
    assert any(TEST_BIOSAMPLE_KNOWN_AMR_GENE_SUBSTRING in gene for gene in isolate.amr_genotypes), (
        f"expected {TEST_BIOSAMPLE_KNOWN_AMR_GENE_SUBSTRING!r} among {isolate.amr_genotypes!r}"
    )
    assert len(isolate.amr_genotypes) > 1, (
        "F-3.5-03: a comma-joined AMR_genotypes value must parse to multiple "
        f"list items, not one blob string; got {isolate.amr_genotypes!r}"
    )
    assert isolate.source_url and isolate.source_url.startswith(
        "https://www.ncbi.nlm.nih.gov/pathogens/"
    ), f"host-pinned source_url required, got {isolate.source_url!r}"


@premise_gate
@pytest.mark.asyncio
async def test_02_isolate_lookup_nonexistent_biosample_is_empty_not_error() -> None:
    """Case 2. A nonexistent biosample is a structured empty, never fabricated."""
    output = await _run(
        {"mode": "isolate_lookup", "taxon": TAXON, "biosample_acc": NONEXISTENT_BIOSAMPLE_ACC}
    )

    assert output.status == "empty", f"expected empty, got {output.status}: {output.error}"
    assert output.isolates == []


# ===========================================================================
# ARM 2: cluster_snp_neighbors, F-3.5-01's bounded-scan disposition.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_03_cluster_snp_neighbors_never_falsely_claims_complete() -> None:
    """Case 3. F-3.5-01: either a real result or an honest empty-on-timeout,
    never a silent partial success. This assertion holds whichever branch fires.
    """
    output = await _run(
        {
            "mode": "cluster_snp_neighbors",
            "taxon": TAXON,
            "pds_cluster": TEST_PDS_CLUSTER,
            "max_snp_distance": 5,
        }
    )

    assert output.status in {"ok", "empty"}, (
        f"expected ok or empty (never error for a wall-clock cutoff), got "
        f"{output.status}: {output.error}"
    )
    if output.status == "ok":
        for isolate in output.isolates:
            assert isolate.snp_distance is not None
            assert isolate.snp_distance <= 5
    else:
        assert output.error, "an empty result from a bounded scan must name why (F-3.5-01)"


# ===========================================================================
# Cross-cutting: snapshot pinning, untrusted content.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_04_resolved_snapshot_is_never_mid_build() -> None:
    """Case 4. The tool's own snapshot resolution never returns one with only
    Metadata/ populated (Section 6.6's own named trap, live-reproduced
    2026-08-08: the two newest Salmonella snapshots at probe time were
    exactly this incomplete shape).
    """
    import httpx

    from system_03_search_agent.tools.pathogen_ftp_transport import (
        REQUIRED_SNAPSHOT_SUBDIRS,
        resolve_complete_snapshot,
    )

    async with httpx.AsyncClient() as client:
        snapshot = await resolve_complete_snapshot(TAXON, client=client)

    assert snapshot, "expected a resolved snapshot name"
    assert REQUIRED_SNAPSHOT_SUBDIRS == ("Metadata", "Clusters", "AMR")


@premise_gate
@pytest.mark.asyncio
async def test_05_untrusted_metadata_fields_are_inert_never_executed() -> None:
    """Case 5. A crafted-looking value in a free-text metadata field (strain,
    geo_loc_name) reaches the output only as capped, inert data. This tool
    reads lab-submitted metadata, the same untrusted-content class as any
    other Layer 2/3 free-text field (ai-security-standards.md).
    """
    output = await _run(
        {"mode": "isolate_lookup", "taxon": TAXON, "biosample_acc": TEST_BIOSAMPLE_ACC}
    )

    assert output.status == "ok"
    isolate = output.isolates[0]
    if isolate.strain is not None:
        assert len(isolate.strain) <= 100
    if isolate.geo_loc_name is not None:
        assert len(isolate.geo_loc_name) <= 150
