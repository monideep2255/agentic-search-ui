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

Every `source_url` this module writes is BUILT by
`cypher_provenance.source_url_for_curie`, the same host-pinned builder
`cypher_query`'s own citation path uses, from a CURIE that verified first.
A row whose citation cannot be verified is written with an empty
`source_url` and counted, never given a guessed path.

The citation POLICY around that builder is `cypher_provenance`'s too, not
a second one invented here (finding F-4.4-03, reversing F-2.1-B06,
F-2.1-C04 and F-2.1-C05). Three properties carry over, and
`_edge_citation` below is where they live:

- A stored graph URL is never passed through as the citation. It is first
  reverse-derived back to a real CURIE (`_curie_for_source_url`), and the
  canonical URL is then rebuilt from that CURIE, so a stored value's own
  formatting never leaks into the citation and two differently-formatted
  stored URLs for the same record cannot produce two different citations.
  This also closes a prefix-match hole: the host pattern is anchored only
  at the start, so `https://www.ncbi.nlm.nih.gov/gene/7157 https://
  elsewhere.example/x` used to pass a bare `re.match` check and be written
  whole into the column.
- An edge carries no CURIE of its own (F-2.1-B06 verified this live), so
  its citation is always some other record's. The edge's OWN stored URL is
  tried first because that is edge-intrinsic, and only then the subject
  endpoint and then the object endpoint, rather than the subject alone.
- Either way the row is marked, in a `cited_via_endpoint_curie` column,
  as citing an endpoint's record rather than the edge's own identity.

Depends on:
    - system_03_search_agent.export.traversal (traverse_subgraph,
      TraversalResult, DEFAULT_MAX_NODES, DEFAULT_MAX_EDGES,
      DEFAULT_TIME_BUDGET_S)
    - system_03_search_agent.export.manifest (build_manifest,
      write_manifest)
    - system_03_search_agent.tools.cypher_provenance (source_url_for_curie,
      and the two private helpers `_curie_for_source_url` and
      `_matches_host_pattern`. Imported rather than restated on purpose:
      re-implementing the reverse-derivation table here is exactly the
      "second policy" this finding was filed for, and a copy would drift
      the first time `cypher_provenance` gained a seventh CURIE prefix)
    - system_03_search_agent.tools.graph_connection (ConnectionFactory,
      the type only, for pass-through injection in tests)

Reads:
    - Layer 1 graph, through `traversal.traverse_subgraph`, read-only.

Writes:
    - `nodes.tsv`, `edges.tsv`, `manifest.json`, the three files named in
      `BUNDLE_FILENAMES`, all inside the caller-supplied `output_dir`,
      resolved.
    - One temporary directory NEXT TO that destination while an export
      runs, named with the `.kgx-export-staging-` prefix, plus, when an
      occupied destination is being replaced, one named with the
      `.kgx-export-replaced-` prefix. The bundle is assembled in the first
      and moved into place with a single atomic rename, which is what
      keeps a reader from ever seeing half a bundle or two runs' files
      mixed together (finding F-4.4-53). Both are renamed into place or
      removed before the call returns; neither survives a successful
      export, and a failed export removes its own on a best-effort basis.
      That is a deliberate narrowing of "writes nothing outside
      `output_dir`": nothing outside it SURVIVES, but the guarantee is no
      longer that nothing outside it is ever created, because a same-
      filesystem sibling is what makes the move atomic rather than a copy.

Depended by:
    - system_03_search_agent.export.cli (T-4.4-05, a different builder's
      file, the batch entry point that calls `export_subgraph`)
"""

from __future__ import annotations

import csv
import errno
import os
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

from system_03_search_agent.export.manifest import build_manifest, write_manifest
from system_03_search_agent.export.traversal import (
    DEFAULT_MAX_EDGES,
    DEFAULT_MAX_NODES,
    DEFAULT_TIME_BUDGET_S,
    TraversalResult,
    traverse_subgraph,
)
from system_03_search_agent.tools.cypher_provenance import (
    _curie_for_source_url,
    _matches_host_pattern,
    source_url_for_curie,
)
from system_03_search_agent.tools.graph_connection import ConnectionFactory

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

# The column that marks an edge row's citation as belonging to an
# endpoint's record rather than to the edge itself. Named for the field
# `cypher_provenance._shape_entity` sets for the same purpose
# (`_cited_via_endpoint_curie`), without the leading underscore, since
# this is a published TSV column rather than an internal field.
EDGE_CITED_VIA_COLUMN: Final[str] = "cited_via_endpoint_curie"

# The three files one export produces, as one named set. The publish step
# below moves the whole set into place together, so a file this tuple
# forgets is a file that never lands.
BUNDLE_FILENAMES: Final[tuple[str, ...]] = ("nodes.tsv", "edges.tsv", "manifest.json")

# Where a bundle is assembled before it is published. A SIBLING of the
# destination, never a subdirectory of it, for two reasons: a sibling is on
# the same filesystem as the destination, which is what makes the publishing
# move a rename rather than a copy, and a subdirectory would be a stale entry
# inside the bundle for as long as it existed. The leading dot keeps a
# half-written bundle out of an ordinary directory listing.
_STAGING_PREFIX: Final[str] = ".kgx-export-staging-"

# Where an occupied destination's contents are moved so the new bundle can
# take its place in one rename, instead of being deleted entry by entry
# underneath a reader.
_RETIRED_PREFIX: Final[str] = ".kgx-export-replaced-"

# How many times the publish step retries when a concurrent export moves the
# destination out from under it. Bounded on purpose: retrying forever against
# another writer is a livelock, not a fix.
_PUBLISH_ATTEMPTS: Final[int] = 8

# The errno values POSIX `rename` reports when the destination path is
# occupied by something a plain rename cannot replace. Any other errno is a
# real failure and is re-raised untouched rather than retried.
_DESTINATION_OCCUPIED_ERRNOS: Final[frozenset[int]] = frozenset(
    {errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR, errno.EISDIR}
)

# How many existing entries a refusal message names before it stops listing
# and says how many more there are.
_MAX_LISTED_ENTRIES: Final[int] = 3


@dataclass
class ExportResult:
    """What one `export_subgraph` call produced.

    `output_dir` is the RESOLVED directory the bundle actually landed in,
    which is not necessarily the path the caller typed: a symlinked or
    `..`-bearing argument resolves to somewhere else, and a caller that is
    never told where its files went cannot check them (finding F-4.4-59).
    The three paths are all inside it.
    """

    output_dir: Path
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


def _curie_from_stored_url(stored_url: object) -> str | None:
    """Reverse-derive a verified CURIE from a stored graph URL, or None.

    Two checks, both required. The host pin
    (`cypher_provenance._matches_host_pattern`) rejects a foreign host.
    The reverse derivation (`cypher_provenance._curie_for_source_url`)
    then matches the WHOLE string against one of the six documented
    record-page templates and re-validates the extracted local id, which
    is what makes this a verification of the value rather than a check of
    its prefix. A stored value that is host-valid at the front and
    arbitrary afterwards, the shape `re.match` on the host pattern alone
    used to accept, fails here.
    """
    if not isinstance(stored_url, str) or not stored_url:
        return None
    if not _matches_host_pattern(stored_url):
        return None
    return _curie_for_source_url(stored_url)


def _resolve_source_url(curie: str | None, stored_url: object) -> str | None:
    """Resolve the source_url for one KGX NODE row.

    A vertex carries its own CURIE, so its citation is its own record. A
    stored URL already on the vertex (data carried over from Systems 1 and
    2) is preferred, the same order `cypher_provenance._resolve_source_url`
    uses, but it is verified back to a CURIE and the canonical URL is then
    rebuilt from that CURIE rather than the stored string being passed
    through. When no stored URL verifies, the URL is built from the
    vertex's own CURIE. Returns None, never a guessed or unverified URL,
    when neither succeeds.
    """
    stored_curie = _curie_from_stored_url(stored_url)
    if stored_curie:
        return source_url_for_curie(stored_curie)
    if not curie:
        return None
    return source_url_for_curie(curie)


def _edge_citation(
    stored_url: object, subject_curie: str, object_curie: str
) -> tuple[str | None, str | None]:
    """Resolve the citation for one KGX EDGE row.

    Returns `(source_url, attributed_curie)`, both None when nothing
    verifies. This is `cypher_provenance._attributed_endpoint_curie`'s
    policy, applied to the two CURIEs this module's traversal already
    attached to the edge:

    1. The edge's own stored `source_url`, reverse-derived to a CURIE.
       Edge-intrinsic, so the same edge cites the same record no matter
       which endpoints a given traversal happened to collect (F-2.1-C05).
    2. Failing that, the subject endpoint, then the object endpoint. Both,
       in that order, never the subject alone, which is the asymmetry
       F-2.1-B06 filed and finding F-4.4-03 found reintroduced here.

    An AGE edge carries no `properties["id"]` of its own (verified live
    under F-2.1-B06), so whichever branch succeeds, the citation belongs
    to some other record and the caller marks the row as such. The URL is
    always rebuilt from the verified CURIE, never the stored string.
    """
    stored_curie = _curie_from_stored_url(stored_url)
    if stored_curie:
        return source_url_for_curie(stored_curie), stored_curie
    for candidate in (subject_curie, object_curie):
        if not candidate:
            continue
        url = source_url_for_curie(candidate)
        if url:
            return url, candidate
    return None, None


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

    The `cited_via_endpoint_curie` column names the record the citation
    actually points at. It is never presented as the edge's own identity,
    which is the misattribution F-2.1-B06 described as "a citation that
    survives inspection while pointing at the wrong thing": for a
    `mentioned_in` edge the column reads `NCBIGene:7157` beside a
    `source_url` for the gene page, so a consumer can see at a glance that
    the citation is the subject's record and not the article that
    evidences the mention.
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

    resolved_url, attributed_curie = _edge_citation(
        properties.get("source_url"), subject_curie, object_curie
    )
    row["source_url"] = resolved_url or ""
    row[EDGE_CITED_VIA_COLUMN] = attributed_curie or ""
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


def _describe_entries(entries: list[str]) -> str:
    """Name the first few entries of a non-empty destination, then the count.

    Kept short on purpose: the refusal message exists to tell the caller
    which directory it is looking at, not to print the directory.
    """
    shown = ", ".join(entries[:_MAX_LISTED_ENTRIES])
    remaining = len(entries) - _MAX_LISTED_ENTRIES
    if remaining > 0:
        shown += f", and {remaining} more"
    return shown


def _resolve_destination(output_dir: Path, overwrite: bool) -> Path:
    """Resolve the export destination and decide whether it may be written.

    Every check here runs BEFORE the traversal, so a destination this
    export cannot use costs no graph work at all (finding F-4.4-59, whose
    read-only-directory case paid for a whole traversal before the first
    write failed).

    Returns the resolved absolute path: symlinks followed, `..` segments
    collapsed. That resolved path is what the export writes and what
    `ExportResult.output_dir` reports, so a caller who typed a symlink or a
    relative path with `..` in it is told where the files actually landed
    rather than left to assume (finding F-4.4-59).

    A destination that already holds anything is refused unless `overwrite`
    is true. An export replaces a destination wholesale and never merges
    into one, because merging is what left a previous run's file sitting
    inside a bundle whose manifest does not mention it (finding F-4.4-58).

    This is a check of the destination as it stands right now, not a
    reservation of it. Another export can create or fill the destination
    afterwards, and the publish step below settles that case by replacing
    it wholesale rather than by failing after the traversal is paid for.

    Raises:
        ValueError: the destination is the filesystem root, exists as
            something that is not a directory, or is a non-empty directory
            while `overwrite` is false. Each message names the resolved
            path and what to do next.
        OSError: the destination exists but its contents cannot be listed.
    """
    destination = Path(output_dir).resolve()
    if destination.parent == destination:
        raise ValueError(
            f"the export destination {destination} is a filesystem root; an "
            "export replaces its destination directory wholesale, so point "
            "--output-dir at a directory of its own"
        )
    if destination.exists() and not destination.is_dir():
        raise ValueError(
            f"the export destination {destination} exists and is not a "
            "directory; remove it or point --output-dir at a directory"
        )
    if destination.is_dir():
        entries = sorted(entry.name for entry in destination.iterdir())
        if entries and not overwrite:
            raise ValueError(
                f"the export destination {destination} is not empty; it holds "
                f"{_describe_entries(entries)}. An export replaces its "
                "destination wholesale rather than merging into it, so choose "
                "an empty or new directory, or re-run with overwrite=True "
                "(the --force flag on s3-kgx-export) to replace everything "
                "that is there"
            )
    return destination


def _create_staging_dir(destination: Path) -> Path:
    """Create the sibling directory this export assembles its bundle in.

    Doubles as the export's write probe. It is created before the traversal
    runs, so a destination whose parent cannot be written to fails at the
    cost of one directory creation instead of a whole traversal (finding
    F-4.4-59).

    Raises:
        OSError: the parent directory could not be created or written to.
    """
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging_dir = parent / (_STAGING_PREFIX + uuid4().hex)
    staging_dir.mkdir()
    return staging_dir


def _remove_tree(path: Path) -> None:
    """Remove a retired bundle, whatever kind of entry it turned out to be."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _publish_bundle(staging_dir: Path, destination: Path) -> None:
    """Move one fully written bundle into `destination` as a single step.

    This is the whole of finding F-4.4-53's fix. `os.rename` of a directory
    is atomic within a filesystem, and `staging_dir` is a sibling of
    `destination` so both are on one filesystem. A reader of `destination`
    therefore observes either no directory, or one complete bundle from one
    run. It cannot observe a partly written bundle, and it cannot observe
    `nodes.tsv` from one run beside `edges.tsv` and `manifest.json` from
    another, which is the torn, self-certifying bundle two concurrent
    exports used to produce.

    An occupied destination is retired to a sibling path and removed only
    after the new bundle is in place, rather than being emptied entry by
    entry while the new bundle is written over it. Emptying in place is the
    interleaving this function exists to prevent.

    Between the retire and the move the destination does not exist. That is
    deliberate and is the one observable state besides a complete bundle: a
    reader sees the bundle, or sees nothing, never a mixture.

    Two exports racing to publish into one destination both succeed and the
    destination ends up holding one of them, entire. Last writer wins is the
    chosen outcome, not an accident of scheduling.

    Removing the retired copy afterwards is the one step allowed to fail
    without failing the export, since by then the new bundle is already in
    place and the export has succeeded. It warns instead of raising, so a
    caller is told what was left behind and where, rather than reading a
    landed export as a failed one.

    Raises:
        OSError: the move failed. When the destination had been retired
            first, its previous contents are moved back before the error is
            re-raised, and if even that fails the raised message names where
            they were left.
    """
    for _attempt in range(_PUBLISH_ATTEMPTS):
        try:
            os.rename(staging_dir, destination)
            return
        except OSError as exc:
            if exc.errno not in _DESTINATION_OCCUPIED_ERRNOS:
                raise

        retired = destination.parent / (_RETIRED_PREFIX + uuid4().hex)
        try:
            os.rename(destination, retired)
        except FileNotFoundError:
            # The destination went away between the two calls above, which
            # only a concurrent export or an outside deletion can do. There
            # is nothing retired to undo, so retry the direct move.
            continue

        try:
            os.rename(staging_dir, destination)
        except OSError:
            try:
                os.rename(retired, destination)
            except OSError as restore_error:
                raise OSError(
                    f"the export could not be published to {destination}, and "
                    "what was already there could not be put back; it is at "
                    f"{retired}; move that directory back to {destination} by "
                    "hand before re-running"
                ) from restore_error
            # Bare, so the caller sees the failure that actually happened
            # to their export, with the restore treated as the cleanup it
            # is rather than as the error worth reporting.
            raise

        try:
            _remove_tree(retired)
        except OSError:
            warnings.warn(
                f"the export landed at {destination}, but what it replaced "
                f"could not be removed and is still at {retired}; remove that "
                "directory by hand",
                stacklevel=2,
            )
        return

    raise OSError(
        f"the export could not be published to {destination} after "
        f"{_PUBLISH_ATTEMPTS} attempts because another export kept replacing "
        "it; re-run against a destination no other export is writing to"
    )


def export_subgraph(
    seeds: list[str],
    output_dir: Path,
    hops: int = 1,
    edge_labels: tuple[str, ...] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    connection_factory: ConnectionFactory | None = None,
    overwrite: bool = False,
) -> ExportResult:
    """Export a query-scoped subgraph from Layer 1 as KGX plus a manifest.

    Traverses outward from `seeds` (`traversal.traverse_subgraph`), shapes
    the result into `nodes.tsv` and `edges.tsv` under the KGX column
    contract, writes `manifest.json` alongside them
    (`manifest.build_manifest`, `manifest.write_manifest`), and returns
    the three file paths plus the counts and truncation state a caller
    needs without having to re-open the manifest itself.

    The three files are assembled in a temporary sibling directory and
    moved into `output_dir` as one step (`_publish_bundle`), so a reader
    of `output_dir` sees one complete bundle from one run, or nothing.
    They used to be written straight into `output_dir` as three separate
    overwrites, which two concurrent exports interleaved into a bundle
    holding one run's nodes beside another run's edges and manifest, with
    both calls returning success (finding F-4.4-53).

    The destination is resolved and checked before the traversal starts,
    never after it (findings F-4.4-58 and F-4.4-59).

    What this does NOT guarantee, stated so the gap is arguable: nothing
    here is fsynced, so the atomicity is against a concurrent reader and a
    concurrent export, not against a machine losing power mid-write.

    Args:
        seeds: one or more CURIEs to start the traversal from. Must be
            non-empty.
        output_dir: the directory to write `nodes.tsv`, `edges.tsv`, and
            `manifest.json` into. Created if it does not already exist,
            and resolved before use, so `ExportResult.output_dir` reports
            where the files actually landed. While the export runs, one
            temporary directory sits beside it, named with the
            `.kgx-export-staging-` prefix; it is renamed into place or
            removed before this call returns.
        hops: the maximum number of edge traversals from any seed.
        edge_labels: the edge labels to traverse, or `None` for every
            label in `graph_schema_constants.EDGE_LABELS`.
        max_nodes: the maximum number of distinct vertices to collect.
        max_edges: the maximum number of distinct edges to collect.
        time_budget_s: the wall-clock budget for the whole traversal.
        connection_factory: forwarded to the traversal's graph calls.
            Tests inject a fake factory here; production code leaves this
            None.
        overwrite: whether a destination that already holds anything may
            be replaced. False by default, which refuses such a
            destination before any graph work rather than merging a new
            bundle in beside whatever was there (finding F-4.4-58). True
            replaces the destination wholesale: every file already in it
            is gone once the new bundle lands.

    Returns:
        An ExportResult naming the resolved destination and the three
        written files. `nodes.tsv` and `edges.tsv` always carry their
        header row, even when the traversal found nothing to export.

    Raises:
        ValueError: `seeds` is empty, `edge_labels` names a label the
            graph does not have, or the destination is unusable (it is not
            a directory, or it is a non-empty one and `overwrite` is
            false).
        OSError: the destination's parent could not be written to, or the
            finished bundle could not be moved into place. The parent is
            probed before the traversal, so an unwritable one costs no
            graph work.
        GraphConnectionError, GraphAuthError: the graph is unreachable or
            the credential was rejected. Not caught here; the caller
            (T-4.4-05's batch entry point) is responsible for turning
            this into an actionable, non-crashing message.
    """
    if not seeds:
        raise ValueError("export_subgraph requires at least one seed CURIE")

    destination = _resolve_destination(Path(output_dir), overwrite=overwrite)
    staging_dir = _create_staging_dir(destination)
    published = False
    try:
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

        _write_tsv(node_rows, staging_dir / "nodes.tsv", NODE_REQUIRED_COLUMNS)
        _write_tsv(edge_rows, staging_dir / "edges.tsv", EDGE_REQUIRED_COLUMNS)

        manifest = _build_export_manifest(
            seeds=seeds,
            hops=hops,
            result=result,
            max_nodes=max_nodes,
            max_edges=max_edges,
            time_budget_s=time_budget_s,
            node_count=len(node_rows),
            edge_count=len(edge_rows),
            empty_source_url_count=empty_source_url_count,
        )
        write_manifest(manifest, staging_dir)

        _publish_bundle(staging_dir, destination)
        published = True
    finally:
        if not published:
            # Best effort: a failing export must not leave its half-written
            # bundle beside the destination, and it must not replace the
            # failure the caller needs to see with a cleanup error.
            shutil.rmtree(staging_dir, ignore_errors=True)

    return ExportResult(
        output_dir=destination,
        nodes_path=destination / "nodes.tsv",
        edges_path=destination / "edges.tsv",
        manifest_path=destination / "manifest.json",
        node_count=len(node_rows),
        edge_count=len(edge_rows),
        truncated=result.truncated,
        manifest=manifest,
    )


def _build_export_manifest(
    *,
    seeds: list[str],
    hops: int,
    result: TraversalResult,
    max_nodes: int,
    max_edges: int,
    time_budget_s: float,
    node_count: int,
    edge_count: int,
    empty_source_url_count: int,
) -> dict[str, Any]:
    """Assemble the manifest for one finished export.

    Split out of `export_subgraph` when the write path moved to staging
    plus an atomic publish, purely so that function reads as the five
    steps it now is (resolve, stage, traverse, write, publish) rather than
    burying the publish under twenty lines of manifest arguments. Every
    argument forwarded here is the same one that was forwarded before.
    """
    # `edge_labels_traversed`, never the requested set. Finding F-4.4-50
    # and the judge's F-4.4-02: filling a field documented as "the labels
    # actually traversed" from the labels the caller ASKED for is a value
    # decided by a proxy for that value, and it made a default export
    # certify fourteen-label coverage after querying one label.
    return build_manifest(
        seeds=list(seeds),
        hops=hops,
        edge_labels_traversed=tuple(result.edge_labels_traversed),
        edge_labels_requested=tuple(result.edge_labels_requested),
        max_nodes=max_nodes,
        max_edges=max_edges,
        time_budget_s=time_budget_s,
        per_query_row_limit=result.per_query_row_limit,
        node_count=node_count,
        edge_count=edge_count,
        truncated=result.truncated,
        truncation=result.truncation,
        empty_reason=result.empty_reason,
        rows_with_empty_source_url=empty_source_url_count,
        seeds_resolved=result.seeds_resolved,
        elapsed_s=result.elapsed_s,
        dropped_rows=result.dropped,
        rows_fetched_not_exported=result.rows_fetched_not_exported,
        hop_limit_reached=result.hop_limit_reached,
        unexpanded_frontier_nodes=result.unexpanded_frontier_nodes,
    )
