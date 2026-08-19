"""Manifest construction, writing, and summary text for the KGX export (T-4.4-04).

Every export writes a `manifest.json` alongside its two TSV files. This
module owns that manifest's shape: what the caller asked for (seeds, hop
limit, cap values), what actually happened (row counts, which caps were
hit, whether the export is empty and why), and the standing Layer 1 only
limitation every export carries regardless of what it found.

Silent truncation is this project's most-filed defect class
(`tracker/phase_4.4.md` names F-3.3-A-12, F-4.0-A-12, F-3.5-10, F-2.2-06).
This module's whole reason to exist is to make that impossible for the
KGX export: `truncated` and `truncation` are always present, computed from
the traversal's own bookkeeping, never left implicit by omission.

Depends on:
    - Nothing beyond the standard library (json, os, datetime, pathlib).
      Deliberately has no import of system_03_search_agent.tools.
      cypher_query: that module's own `_graph_snapshot_version` reads the
      same environment variable this module reads, but is private to its
      module and outside this ticket's file scope, so the same small
      amount of logic (read GRAPH_SNAPSHOT_VERSION, fall back to the last
      verified snapshot label, cap at 40 characters) is restated here
      rather than imported.

Reads:
    - Environment variable: GRAPH_SNAPSHOT_VERSION, optional. Falls back
      to the last verified snapshot name recorded in
      docs/data-engineering/Knowledge_graph_on_server_reference.md when
      unset, the same fallback `cypher_query.py` uses.

Writes:
    - `manifest.json` in the caller-supplied output directory only.

Depended by:
    - system_03_search_agent.export.kgx (T-4.4-03, calls build_manifest
      and write_manifest once the TSV files are written)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

# Same env var name, default, and character cap as
# `cypher_query._ENV_GRAPH_SNAPSHOT_VERSION` /
# `cypher_query._DEFAULT_GRAPH_SNAPSHOT_VERSION` /
# `cypher_query._MAX_SNAPSHOT_VERSION_CHARS`, restated here rather than
# imported since that module is private and outside this ticket's file
# scope. Kept in sync by naming the same source doc both read from.
_ENV_GRAPH_SNAPSHOT_VERSION: Final[str] = "GRAPH_SNAPSHOT_VERSION"
_DEFAULT_GRAPH_SNAPSHOT_VERSION: Final[str] = "ncbi_kg_v1_2026-04-22"
_MAX_SNAPSHOT_VERSION_CHARS: Final[int] = 40

# Section 25 (4.4)'s own framing: "scoped to the existing Hetzner graph,
# not a full graph export". This is the sentence every manifest carries so
# a consumer of nodes.tsv/edges.tsv cannot mistake a query-scoped export
# for the three-layer picture the live search agent actually answers
# with. Deliberately names Layer 2 and Layer 3 by their own live sources,
# not just by number, so the statement is checkable against
# docs/architecture/Three_layer_data_architecture.md.
_LAYER_NOTE: Final[str] = (
    "This export covers Layer 1, the pre-ingested knowledge graph, only. "
    "Layer 2 (live NCBI E-utilities calls: EFetch, ELink, the dbSNP REST "
    "API) and Layer 3 (enrichment APIs: PubTator3, LitVar2, LitSense, "
    "ClinicalTrials.gov) are fetched live at query time by the search "
    "agent and are not present in this file."
)


def graph_snapshot_version() -> str:
    """Read the graph snapshot label, falling back to the last verified one.

    Never empty: a missing environment variable falls back to
    `_DEFAULT_GRAPH_SNAPSHOT_VERSION` rather than an empty string, so this
    field is never blank in a written manifest.
    """
    value = os.environ.get(_ENV_GRAPH_SNAPSHOT_VERSION, _DEFAULT_GRAPH_SNAPSHOT_VERSION)
    if not value:
        value = _DEFAULT_GRAPH_SNAPSHOT_VERSION
    return value[:_MAX_SNAPSHOT_VERSION_CHARS]


def build_manifest(
    seeds: list[str],
    hops: int,
    edge_labels_used: tuple[str, ...],
    max_nodes: int,
    max_edges: int,
    time_budget_s: float,
    node_count: int,
    edge_count: int,
    truncated: bool,
    truncation: list[dict[str, Any]],
    empty_reason: str | None,
    rows_with_empty_source_url: int,
    seeds_resolved: list[str],
    elapsed_s: float,
) -> dict[str, Any]:
    """Assemble the manifest dict for one export, before it is written.

    Args:
        seeds: the seed CURIEs exactly as the caller supplied them, in
            order, never deduplicated or reordered, so a consumer can
            compare this list against what they asked for.
        hops: the hop limit the traversal was bounded to.
        edge_labels_used: the edge labels actually traversed. Every label
            in `graph_schema_constants.EDGE_LABELS` when the caller asked
            for "every label" (`edge_labels=None` at the traversal layer).
        max_nodes: the configured node cap.
        max_edges: the configured edge cap.
        time_budget_s: the configured wall-clock budget, in seconds.
        node_count: the number of node rows actually written.
        edge_count: the number of edge rows actually written.
        truncated: whether any cap was hit before the traversal could
            reach a natural stopping point.
        truncation: the list of `{"cap": str, "value": int}` entries
            naming which cap(s) were hit and at what configured value.
            Empty when `truncated` is False.
        empty_reason: why the export carries zero nodes and zero edges,
            or None when it is not empty.
        rows_with_empty_source_url: the count of node and edge rows,
            combined, written with an empty `source_url` because no
            host-pinned NCBI record page could be verified for that row.
        seeds_resolved: the subset of `seeds` that actually matched a
            vertex in the graph.
        elapsed_s: the traversal's own measured wall-clock time.

    Returns:
        A JSON-serializable dict. Every key this phase's premise gate
        reads is present unconditionally: `truncated`, `truncation`,
        `empty_reason`, `layers`, `layer_note`, `seeds`, `hops`, `counts`
        (with `nodes` and `edges`), `graph_snapshot_version`,
        `exported_at`.
    """
    return {
        "seeds": list(seeds),
        "seeds_resolved": list(seeds_resolved),
        "hops": hops,
        "edge_labels": list(edge_labels_used),
        "caps": {
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "time_budget_s": time_budget_s,
        },
        "counts": {"nodes": node_count, "edges": edge_count},
        "truncated": truncated,
        "truncation": list(truncation),
        "empty_reason": empty_reason,
        "layers": ["layer_1"],
        "layer_note": _LAYER_NOTE,
        "rows_with_empty_source_url": rows_with_empty_source_url,
        "graph_snapshot_version": graph_snapshot_version(),
        "exported_at": datetime.now(UTC).isoformat(),
        "elapsed_s": round(elapsed_s, 3),
    }


def write_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    """Write `manifest.json` into `output_dir` and return its path.

    Writes only inside `output_dir`, never elsewhere, and never logs or
    includes any credential value: nothing in the manifest shape above
    carries a secret, and this function adds nothing beyond what
    `build_manifest` already assembled.
    """
    path = Path(output_dir) / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def summary_lines(manifest: dict[str, Any]) -> list[str]:
    """Render the manifest's limitation and truncation statements as plain text.

    Exists so a caller that also prints to the command's own output
    (T-4.4-05's batch entry point, a different builder's file) states the
    same facts the manifest file states, worded identically, rather than
    re-deriving a summary that could drift from what the file actually
    says. Never includes a credential value or a file path outside the
    caller's own output directory.
    """
    lines = [manifest["layer_note"]]
    if manifest["truncated"]:
        caps_text = ", ".join(
            entry["cap"] + "=" + str(entry["value"]) for entry in manifest["truncation"]
        )
        lines.append(
            "This export is INCOMPLETE: it hit the following cap(s): " + caps_text + "."
        )
    else:
        lines.append("This export hit no cap; it is the complete requested subgraph.")
    if manifest["empty_reason"]:
        lines.append("Empty export: " + str(manifest["empty_reason"]))
    if manifest["rows_with_empty_source_url"]:
        lines.append(
            str(manifest["rows_with_empty_source_url"])
            + " row(s) were written with an empty source_url."
        )
    return lines
