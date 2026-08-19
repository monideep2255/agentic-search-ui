"""KGX serialization for the query-scoped subgraph export (T-4.4-03).

Shapes a `traversal.TraversalResult` into `nodes.tsv`, `edges.tsv`, and
`manifest.json` inside a caller-supplied output directory. The column
contract this module writes to is the same one `reference/
agentic-search-data-engineering/system-01-data-pipelines/shared/
kgx_exporter.py` writes for the System 1 bulk pipelines: required columns
first and in a fixed order, additional columns sorted alphabetically after
them, list and tuple values pipe-joined, every row provenance-bearing.
That module is read-only reference material for this ticket (`.claude/
rules/file-protection.md`); its column contract is replicated here, never
imported, since a System 3 module must not depend on System 1 code at
runtime.

Every `source_url` this module writes comes from
`cypher_provenance.source_url_for_curie`, the same host-pinned builder
`cypher_query`'s own citation path uses, or from a stored graph value that
independently matches the same host-pinned pattern
(`graph_schema_constants.NCBI_RECORD_URL_PATTERN`). A row whose URL cannot
be verified either way is written with an empty `source_url` and counted,
never given a guessed path.

Depends on:
    - system_03_search_agent.export.traversal (traverse_subgraph,
      TraversalResult, DEFAULT_MAX_NODES, DEFAULT_MAX_EDGES,
      DEFAULT_TIME_BUDGET_S)
    - system_03_search_agent.export.manifest (build_manifest,
      write_manifest)
    - system_03_search_agent.tools.cypher_provenance (source_url_for_curie)
    - system_03_search_agent.tools.graph_schema_constants (EDGE_LABELS,
      NCBI_RECORD_URL_PATTERN)
    - system_03_search_agent.tools.graph_connection (ConnectionFactory,
      the type only, for pass-through injection in tests)

Reads:
    - Layer 1 graph, through `traversal.traverse_subgraph`, read-only.

Writes:
    - `nodes.tsv`, `edges.tsv`, `manifest.json`, all directly inside the
      caller-supplied `output_dir`. Nothing outside it.

Depended by:
    - system_03_search_agent.export.cli (T-4.4-05, a different builder's
      file, the batch entry point that calls `export_subgraph`)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from system_03_search_agent.export.manifest import build_manifest, write_manifest
from system_03_search_agent.export.traversal import (
    DEFAULT_MAX_EDGES,
    DEFAULT_MAX_NODES,
    DEFAULT_TIME_BUDGET_S,
    TraversalResult,
    traverse_subgraph,
)
from system_03_search_agent.tools.cypher_provenance import source_url_for_curie
from system_03_search_agent.tools.graph_connection import ConnectionFactory
from system_03_search_agent.tools.graph_schema_constants import (
    EDGE_LABELS,
    NCBI_RECORD_URL_PATTERN,
)

# The upstream column contract, restated here (not imported, see the
# module docstring). Column ORDER is part of the contract: a shifted
# column is a valid-looking TSV that is silently wrong, the failure this
# phase's premise gate specifically checks for.
NODE_REQUIRED_COLUMNS: Final[list[str]] = ["id", "category", "name", "source", "source_url"]
EDGE_REQUIRED_COLUMNS: Final[list[str]] = [
    "subject",
    "predicate",
    "object",
    "source",
    "source_url",
    "knowledge_level",
    "agent_type",
]

_HOST_PATTERN = re.compile(NCBI_RECORD_URL_PATTERN)


@dataclass
class ExportResult:
    """What one `export_subgraph` call produced."""

    nodes_path: Path
    edges_path: Path
    manifest_path: Path
    node_count: int
    edge_count: int
    truncated: bool
    manifest: dict[str, Any]


def serialize_value(value: object) -> str:
    """Serialize one field value for TSV output.

    A list or tuple is pipe-joined, matching the upstream reader every
    downstream KGX consumer already expects. `None` becomes an empty
    string rather than the literal text "None". Everything else is
    stringified as-is.
    """
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _build_fieldnames(records: list[dict[str, Any]], required: list[str]) -> list[str]:
    """Derive the ordered column list: required columns first, then extras sorted.

    Extras are the union of every key present across `records` that is
    not already one of `required`, sorted alphabetically. A record that
    lacks a given extra key simply has no value for that column; the
    writer fills it in as an empty field rather than shifting the row.
    """
    extra: set[str] = set()
    for record in records:
        extra.update(record.keys())
    extra -= set(required)
    return required + sorted(extra)


def _write_tsv(records: list[dict[str, Any]], path: Path, required_columns: list[str]) -> Path:
    """Write `records` to `path` as a tab-separated file with a header row.

    Column order is required columns first, then any additional columns
    found in the data, sorted alphabetically. A missing key is written as
    an empty field. Written UTF-8, with a header row even when `records`
    is empty, so a zero-row export still produces a well-formed file a
    downstream KGX reader can open.

    Relies on Python's `csv` module's default quoting (QUOTE_MINIMAL) to
    keep a field containing a tab, a newline, or a double quote from
    shifting or splitting a row: any of those three characters in a field
    value causes that field to be quoted, and the corresponding
    `csv.DictReader` on the same delimiter reverses that transparently.
    This module never overrides that quoting behavior.
    """
    fieldnames = _build_fieldnames(records, required_columns)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()
        for record in records:
            row = {name: serialize_value(record.get(name, "")) for name in fieldnames}
            writer.writerow(row)
    return path


def _resolve_source_url(curie: str | None, stored_url: object) -> str | None:
    """Resolve the source_url for one KGX row: keep a valid stored URL, else derive.

    A stored URL already on the vertex or edge (data carried over from
    Systems 1 and 2) is kept only when it matches the host-pinned
    pattern. Otherwise this falls back to `source_url_for_curie(curie)`,
    the same verified builder `cypher_query`'s own citation path uses.
    Returns None, never a guessed or unverified URL, when neither check
    succeeds.
    """
    if isinstance(stored_url, str) and stored_url and _HOST_PATTERN.match(stored_url):
        return stored_url
    if not curie:
        return None
    return source_url_for_curie(curie)


def _node_row(curie: str, entity: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Shape one parsed AGE vertex entity into a KGX node row.

    Returns the row dict and whether its `source_url` came back empty
    (no host-pinned record page could be verified), so the caller can
    fold that into the manifest's `rows_with_empty_source_url` count.

    Every raw property the graph carries (for example `xrefs`,
    `agent_type`, `knowledge_level`) passes through unchanged as an extra
    column; this module never hardcodes which extra properties a vertex
    label happens to carry, since that set is graph data, not a KGX
    contract this ticket owns.
    """
    label = str(entity.get("label") or "")
    properties = entity.get("properties")
    if not isinstance(properties, dict):
        properties = {}

    row: dict[str, Any] = dict(properties)
    row["id"] = curie
    row["category"] = "biolink:" + label
    row.setdefault("name", "")
    row.setdefault("source", "")

    resolved_url = _resolve_source_url(curie, properties.get("source_url"))
    row["source_url"] = resolved_url or ""
    return row, not resolved_url


def _edge_row(edge_entity: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Shape one parsed AGE edge entity (with subject/object CURIEs attached) into a KGX edge row.

    `edge_entity` is expected to already carry `subject_curie` and
    `object_curie`, the keys `traversal.traverse_subgraph` adds once it
    has resolved both endpoints from data already collected during the
    same traversal. Returns the row dict and whether its `source_url`
    came back empty, the same convention `_node_row` uses.
    """
    label = str(edge_entity.get("label") or "")
    properties = edge_entity.get("properties")
    if not isinstance(properties, dict):
        properties = {}

    subject_curie = str(edge_entity.get("subject_curie") or "")
    object_curie = str(edge_entity.get("object_curie") or "")

    row: dict[str, Any] = dict(properties)
    row["subject"] = subject_curie
    row["predicate"] = "biolink:" + label
    row["object"] = object_curie
    row.setdefault("knowledge_level", "")
    row.setdefault("agent_type", "")

    resolved_url = _resolve_source_url(subject_curie, properties.get("source_url"))
    row["source_url"] = resolved_url or ""
    return row, not resolved_url


def rows_from_traversal(
    result: TraversalResult,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Shape a TraversalResult's raw entities into KGX node and edge rows.

    Returns (node_rows, edge_rows, rows_with_empty_source_url). Kept as
    its own function, separate from `export_subgraph`, so it can be unit
    tested directly against a hand-built TraversalResult without needing
    a graph connection.
    """
    node_rows: list[dict[str, Any]] = []
    empty_source_url_count = 0
    for curie, entity in result.nodes.items():
        row, is_empty = _node_row(curie, entity)
        node_rows.append(row)
        if is_empty:
            empty_source_url_count += 1

    edge_rows: list[dict[str, Any]] = []
    for edge_entity in result.edges:
        row, is_empty = _edge_row(edge_entity)
        edge_rows.append(row)
        if is_empty:
            empty_source_url_count += 1

    return node_rows, edge_rows, empty_source_url_count


def export_subgraph(
    seeds: list[str],
    output_dir: Path,
    hops: int = 1,
    edge_labels: tuple[str, ...] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    connection_factory: ConnectionFactory | None = None,
) -> ExportResult:
    """Export a query-scoped subgraph from Layer 1 as KGX plus a manifest.

    Traverses outward from `seeds` (`traversal.traverse_subgraph`), shapes
    the result into `nodes.tsv` and `edges.tsv` under the KGX column
    contract, writes `manifest.json` alongside them
    (`manifest.build_manifest`, `manifest.write_manifest`), and returns
    the three file paths plus the counts and truncation state a caller
    needs without having to re-open the manifest itself.

    Args:
        seeds: one or more CURIEs to start the traversal from. Must be
            non-empty.
        output_dir: the directory to write `nodes.tsv`, `edges.tsv`, and
            `manifest.json` into. Created if it does not already exist.
            Nothing is ever written outside this directory.
        hops: the maximum number of edge traversals from any seed.
        edge_labels: the edge labels to traverse, or `None` for every
            label in `graph_schema_constants.EDGE_LABELS`.
        max_nodes: the maximum number of distinct vertices to collect.
        max_edges: the maximum number of distinct edges to collect.
        time_budget_s: the wall-clock budget for the whole traversal.
        connection_factory: forwarded to the traversal's graph calls.
            Tests inject a fake factory here; production code leaves this
            None.

    Returns:
        An ExportResult naming the three written files. `nodes.tsv` and
        `edges.tsv` always carry their header row, even when the
        traversal found nothing to export.

    Raises:
        ValueError: `seeds` is empty, or `edge_labels` names a label the
            graph does not have.
        GraphConnectionError, GraphAuthError: the graph is unreachable or
            the credential was rejected. Not caught here; the caller
            (T-4.4-05's batch entry point) is responsible for turning
            this into an actionable, non-crashing message.
    """
    if not seeds:
        raise ValueError("export_subgraph requires at least one seed CURIE")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = traverse_subgraph(
        seeds=seeds,
        hops=hops,
        edge_labels=edge_labels,
        max_nodes=max_nodes,
        max_edges=max_edges,
        time_budget_s=time_budget_s,
        connection_factory=connection_factory,
    )

    node_rows, edge_rows, empty_source_url_count = rows_from_traversal(result)

    nodes_path = _write_tsv(node_rows, output_dir / "nodes.tsv", NODE_REQUIRED_COLUMNS)
    edges_path = _write_tsv(edge_rows, output_dir / "edges.tsv", EDGE_REQUIRED_COLUMNS)

    effective_edge_labels = edge_labels if edge_labels is not None else EDGE_LABELS
    manifest = build_manifest(
        seeds=list(seeds),
        hops=hops,
        edge_labels_used=tuple(effective_edge_labels),
        max_nodes=max_nodes,
        max_edges=max_edges,
        time_budget_s=time_budget_s,
        node_count=len(node_rows),
        edge_count=len(edge_rows),
        truncated=result.truncated,
        truncation=result.truncation,
        empty_reason=result.empty_reason,
        rows_with_empty_source_url=empty_source_url_count,
        seeds_resolved=result.seeds_resolved,
        elapsed_s=result.elapsed_s,
    )
    manifest_path = write_manifest(manifest, output_dir)

    return ExportResult(
        nodes_path=nodes_path,
        edges_path=edges_path,
        manifest_path=manifest_path,
        node_count=len(node_rows),
        edge_count=len(edge_rows),
        truncated=result.truncated,
        manifest=manifest,
    )
