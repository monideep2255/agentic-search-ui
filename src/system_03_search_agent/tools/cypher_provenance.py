"""Layer 1 provenance and source URL mapping, T-2.1-05.

Maps a graph CURIE to its human-facing NCBI record page and shapes a raw
graph row into the `CypherQueryRow` dict shape (Section 6.1, Section 9).
This module never fabricates a URL: a CURIE prefix with no verified,
host-pinned NCBI record page returns None rather than a guessed path, and
every URL this module emits, whether newly derived or an existing stored
value, is checked against `NCBI_RECORD_URL_PATTERN` before it is returned.

Six of the nine CURIE prefixes in `graph_schema_constants.CURIE_PREFIXES`
map to a documented NCBI record page and are handled below: NCBIGene,
ClinVar, MedGen, PMID, NCBITaxon, MeSH. MeSH (Medical Subject Headings)
is an NCBI-hosted controlled vocabulary in its own right, listed in
`docs/ncbi/NCBI_databases_and_APIs_reference.md`, so a `MeSH:D012345`
CURIE maps to `https://www.ncbi.nlm.nih.gov/mesh/?term=D012345`.

The remaining three, GO, HP, and MONDO, are not NCBI-hosted databases.
Gene Ontology, the Human Phenotype Ontology, and Mondo are maintained
outside NCBI entirely (the OBO Foundry and the Monarch Initiative), so no
host-pinned `ncbi.nlm.nih.gov` record page exists for them at all;
inventing one would be exactly the fabricated citation this module exists
to prevent. `source_url_for_curie` returns None for all three, not a
guessed external host and not a loosened pattern. This is a documented,
deliberate gap, not an oversight: if a verified NCBI-hosted or otherwise
host-pinned record page for one of these three is confirmed later, add it
here as a new mapping entry, never by loosening `NCBI_RECORD_URL_PATTERN`
itself.

`to_output_rows` (plural), added for finding F-2.1-A1/F-01/A2's fix, is the
real integration path: it takes one raw AGE result row keyed by column name
(`c0`, `c1`, ... or `result`), each value the unparsed agtype wire text
`graph_connection.execute_cypher` read off the socket, parses every column
with `agtype.parse_agtype`, and shapes each column that decodes to a
vertex or an edge into its own output row. `to_output_row` (singular)
stays as the pure, already-parsed-entity shaping function it always was,
used directly by this module's own unit tests and by any caller that has
already turned a raw agtype value into a plain dict.

Finding F-2.1-B06: a real AGE edge carries no `properties["id"]`, so it has
no CURIE and no record page of its own. A live probe of five edge labels
(`is_sequence_variant_of`, `gene_associated_with_condition`,
`has_mesh_annotation`, `in_taxon`, `orthologous_to`) found every edge still
carries a `source_url` property, and in every sampled case that URL was
the same page its start endpoint's own CURIE derives, not a citation the
edge earns on its own. Before this fix, an empty CURIE did not stop
`_resolve_source_url` from keeping that stored URL whenever it matched
the host pattern, so the row shipped `source_id="unknown"` next to a
link that resolves to a real but different record, a citation that
survives inspection while pointing at the wrong thing. `to_output_rows`
now collects every vertex and edge entity across all of a raw row's
columns first, so an edge with no CURIE of its own can be attributed to
a genuine endpoint vertex's CURIE when that vertex is present in the
same row (a sibling column, or an adjacent path element), verified from
data already in hand, never fabricated and never fetched. When no
endpoint vertex is present in the row, the honest outcome is no citation:
`source_url` is None, and the caller's cite-or-refuse gate drops the row.
See `_shape_entity`, `_endpoint_curies_by_internal_id`, and
`_attributed_endpoint_curie`.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants
      (NCBI_RECORD_URL_PATTERN)
    - system_03_search_agent.tools.agtype (parse_agtype, is_vertex_or_edge)

Reads:
    - Nothing at import time. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_query (T-2.1-07, the integration
      ticket, not written by this builder)
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from typing import Any

from system_03_search_agent.tools.agtype import is_vertex_or_edge, parse_agtype
from system_03_search_agent.tools.graph_schema_constants import (
    NCBI_RECORD_URL_PATTERN,
)

_HOST_PATTERN = re.compile(NCBI_RECORD_URL_PATTERN)

# One URL-building function per documented prefix. Each receives the
# already-quoted local id (the part of the CURIE after the first colon)
# and returns a URL string. Kept as callables, not an f-string template
# dict, so each prefix's path shape is explicit and independently
# reviewable.


def _ncbigene_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/gene/" + local_id


def _clinvar_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/clinvar/variation/" + local_id + "/"


def _medgen_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/medgen/" + local_id


def _pmid_url(local_id: str) -> str:
    return "https://pubmed.ncbi.nlm.nih.gov/" + local_id + "/"


def _ncbitaxon_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=" + local_id


def _mesh_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/mesh/?term=" + local_id


# GO, HP, and MONDO are intentionally absent from this table. See the
# module docstring for why: no verified NCBI-hosted record page exists for
# any of the three, so they fall through to the None-returning default in
# `source_url_for_curie` rather than appearing here with a guessed path.
_CURIE_URL_BUILDERS: dict[str, Callable[[str], str]] = {
    "NCBIGene": _ncbigene_url,
    "ClinVar": _clinvar_url,
    "MedGen": _medgen_url,
    "PMID": _pmid_url,
    "NCBITaxon": _ncbitaxon_url,
    "MeSH": _mesh_url,
}


def _matches_host_pattern(url: str) -> bool:
    return bool(_HOST_PATTERN.match(url))


def source_url_for_curie(curie: str) -> str | None:
    """Map a graph CURIE to its NCBI record page, or None.

    Args:
        curie: a compact identifier of the form `prefix:local_id`, e.g.
            `NCBIGene:672`. A string with no colon, an empty prefix, or an
            empty local id is treated as malformed and returns None.

    Returns:
        The record page URL when the prefix is one of the six documented
        mappings and the resulting URL matches `NCBI_RECORD_URL_PATTERN`.
        None for every other prefix, including the three CURIE_PREFIXES
        entries this module does not map (GO, HP, MONDO) and any prefix
        outside the nine entirely. Never a guessed or malformed URL.
    """
    if not curie or ":" not in curie:
        return None
    prefix, _, local_id = curie.partition(":")
    if not prefix or not local_id:
        return None

    builder = _CURIE_URL_BUILDERS.get(prefix)
    if builder is None:
        return None

    quoted_local_id = urllib.parse.quote(local_id, safe="")
    url = builder(quoted_local_id)

    if not _matches_host_pattern(url):
        # Defense in depth: a builder that ever produced a URL outside the
        # host-pinned pattern would be a bug in this module, not a valid
        # citation. Never pass such a URL through.
        return None
    return url


def _resolve_source_url(curie: str, stored_url: object) -> str | None:
    """Resolve the source_url for one row: keep a valid stored URL, else derive.

    A stored URL already on the node or edge (data carried over from
    Systems 1 and 2) is kept only when it matches the host-pinned pattern.
    A stored URL on a foreign host is discarded, never passed through, and
    this function then falls back to deriving a URL from the CURIE, the
    same path taken when no stored URL was present at all.
    """
    if isinstance(stored_url, str) and stored_url and _matches_host_pattern(stored_url):
        return stored_url
    return source_url_for_curie(curie)


def to_output_row(raw_row: dict, snapshot_version: str) -> dict:
    """Shape one raw graph row into the `CypherQueryRow` dict shape.

    `raw_row` is read defensively rather than assumed to carry one exact
    key set, since the graph connection module (T-2.1-06, a different
    builder's file) owns the raw row shape and this ticket is scoped to
    pure transforms only. Recognized keys, in lookup order:

    - node_or_edge_type: `node_or_edge_type`, then `label`, then `type`
    - curie: `curie`, then `id`
    - fields: `fields`, then `properties`, defaulting to an empty dict
    - source_url: `source_url`, an already-stored value if present

    Args:
        raw_row: one row as read from the graph, before output mapping.
        snapshot_version: the graph snapshot version string to stamp onto
            every row, e.g. from `docs/data-engineering/
            Knowledge_graph_on_server_reference.md`'s recorded snapshot.

    Returns:
        A dict with exactly the keys `node_or_edge_type`, `curie`,
        `fields`, `source_url`, `graph_snapshot_version`. `source_url` is
        None, never a fabricated link, when no valid URL could be
        resolved for the row's CURIE.
    """
    node_or_edge_type = (
        raw_row.get("node_or_edge_type")
        or raw_row.get("label")
        or raw_row.get("type")
        or ""
    )
    curie = raw_row.get("curie") or raw_row.get("id") or ""
    fields = raw_row.get("fields")
    if fields is None:
        fields = raw_row.get("properties", {})

    resolved_source_url = _resolve_source_url(curie, raw_row.get("source_url"))

    return {
        "node_or_edge_type": node_or_edge_type,
        "curie": curie,
        "fields": fields,
        "source_url": resolved_source_url,
        "graph_snapshot_version": snapshot_version,
    }


def _is_edge_entity(entity: dict[str, Any]) -> bool:
    """Return True when `entity` is an AGE edge, per `agtype.is_vertex_or_edge`'s
    own convention: a vertex carries only `label`, an edge additionally
    carries `start_id` and/or `end_id`.
    """
    return "start_id" in entity or "end_id" in entity


def _endpoint_curies_by_internal_id(entities: list[dict[str, Any]]) -> dict[Any, str]:
    """Map every vertex's own AGE-internal id to its own CURIE, for one raw row.

    Built once per raw graph row from every vertex entity that row's
    columns actually parsed (a plain multi-column `RETURN v, e, g`, or a
    path's flattened elements), never from a separate graph lookup: this
    module is a pure transform over its arguments and never queries the
    graph on its own (see the module docstring). This mapping is the
    input finding F-2.1-B06's fix depends on: it lets an edge with no
    CURIE of its own (`_shape_entity`, below) attribute its citation to a
    genuine endpoint vertex that is actually present in the same row,
    verified from data already in hand, never to a guessed or freshly
    fetched one.

    An edge entity never contributes to this mapping, only a vertex does,
    so an edge can never be attributed to another edge's identity.
    """
    mapping: dict[Any, str] = {}
    for entity in entities:
        if _is_edge_entity(entity):
            continue
        properties = entity.get("properties")
        if not isinstance(properties, dict):
            continue
        curie = str(properties.get("id") or "")
        internal_id = entity.get("id")
        if curie and internal_id is not None:
            mapping[internal_id] = curie
    return mapping


def _attributed_endpoint_curie(
    entity: dict[str, Any], endpoint_curies: dict[Any, str] | None
) -> str | None:
    """Find a verified endpoint CURIE for an edge entity with no CURIE of its own.

    Checks `entity`'s `start_id` first, then `end_id`, against
    `endpoint_curies` (built by `_endpoint_curies_by_internal_id` from the
    same raw row). The start endpoint is preferred only for determinism,
    not because it is more correct: a live probe of the graph
    (`is_sequence_variant_of`, `gene_associated_with_condition`,
    `has_mesh_annotation`, `in_taxon`, `orthologous_to`) found the edge's
    own stored `source_url` consistently equal to the start endpoint's own
    record page, so preferring `start_id` reconstructs the same URL the
    row used to carry, this time with a `curie` that actually matches it.
    Returns None when neither endpoint vertex is present in the same row,
    which is the honest "cannot attribute" case: an edge queried alone
    (`RETURN e`, finding F-2.1-B06's reproduction) carries no sibling
    vertex data at all, so nothing here is invented to fill the gap.
    """
    if not endpoint_curies:
        return None
    for key in ("start_id", "end_id"):
        internal_id = entity.get(key)
        if internal_id is None:
            continue
        candidate = endpoint_curies.get(internal_id)
        if candidate:
            return candidate
    return None


def _shape_entity(
    entity: dict[str, Any],
    snapshot_version: str,
    endpoint_curies: dict[Any, str] | None = None,
) -> dict:
    """Shape one parsed AGE vertex or edge dict into the output row shape.

    `entity` is the dict `agtype.parse_agtype` decoded from one `::vertex`
    or `::edge` payload: `label`, the graph-internal `id` (an integer AGE
    assigns, never the CURIE), `properties`, and for an edge, `start_id`
    and `end_id`. The CURIE this system cites lives inside
    `properties["id"]`, the identifier Systems 1 and 2 stamped onto every
    node and edge at ingest time. The top-level `id` on the entity itself
    is AGE's own internal graph id and is never treated as a CURIE.

    Finding F-2.1-B06: a real AGE edge carries no `properties["id"]` at
    all (verified live: `source`, `agent_type`, `source_url`, and
    `knowledge_level`, never `id`). Before this fix, an edge's empty
    `curie` still let `_resolve_source_url` pass through the edge's own
    stored `source_url` whenever it matched the host pattern, so the row
    shipped `source_id="unknown"` next to a URL for a genuine but
    different record, a citation that survives inspection while pointing
    at the wrong thing.

    An edge with no CURIE of its own (`is_edge` and `not curie`, below)
    never keeps its raw stored `source_url` unconditionally. It is
    attributed to a verified endpoint CURIE when one is present in the
    same raw row (`endpoint_curies`, built by
    `_endpoint_curies_by_internal_id` from every column of that row), and
    both `curie` and `source_url` are then set from that endpoint so the
    two agree; `fields["_cited_via_endpoint_curie"]` marks the row as an
    edge citing an endpoint's record, never presented as the edge's own
    identity. When no endpoint vertex is present in the row (an edge
    queried alone), `source_url` is None: the honest "no citation"
    outcome, which the caller's cite-or-refuse gate (`cypher_query.
    _run_pipeline`) drops rather than emitting an uncited or
    misattributed row.
    """
    node_or_edge_type = str(entity.get("label") or "")
    properties = entity.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    curie = str(properties.get("id") or "")
    is_edge = _is_edge_entity(entity)

    fields = dict(properties)
    if "start_id" in entity:
        fields.setdefault("_edge_start_id", entity["start_id"])
    if "end_id" in entity:
        fields.setdefault("_edge_end_id", entity["end_id"])

    if is_edge and not curie:
        attributed_curie = _attributed_endpoint_curie(entity, endpoint_curies)
        if attributed_curie:
            curie = attributed_curie
            fields["_cited_via_endpoint_curie"] = attributed_curie
            resolved_source_url = source_url_for_curie(attributed_curie)
        else:
            # No verified endpoint available in this row. The edge's own
            # stored source_url, if any, is never trusted here: it is not
            # this row's own record, and nothing in this call's inputs
            # can verify whose record it actually is.
            resolved_source_url = None
    else:
        resolved_source_url = _resolve_source_url(curie, properties.get("source_url"))

    return {
        "node_or_edge_type": node_or_edge_type,
        "curie": curie,
        "fields": fields,
        "source_url": resolved_source_url,
        "graph_snapshot_version": snapshot_version,
    }


def _iter_entities(parsed: Any) -> list[dict[str, Any]]:
    """Flatten one parsed agtype value into zero or more vertex/edge dicts.

    A vertex or an edge parses to a single dict and yields itself. A path
    parses to a list and yields every vertex/edge element it contains,
    since a path is a sequence of alternating vertices and edges. Any
    other shape, a bare scalar such as a count or a name, or a value that
    failed to parse, yields nothing: it carries no label and no
    properties, so no CURIE and no citation can be derived from it, and
    it must never be turned into a guessed content row.
    """
    if isinstance(parsed, dict):
        return [parsed] if is_vertex_or_edge(parsed) else []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict) and is_vertex_or_edge(item)]
    return []



def _shape_derived_value(
    derived: dict[str, Any],
    snapshot_version: str,
    source_curie: str | None,
    column_labels: dict[str, str] | None = None,
) -> dict:
    """Shape a scalar or projection result into one citable output row.

    Finding F-2.1-B05: a count, a projected property, or a `collect()` list
    is a real answer that carried no label, so it produced no row at all and
    the tool reported `status="empty"` for a query the graph had answered
    correctly.

    Provenance for a derived value is not the value's own record, because it
    has none. It is the entity the query was computed FROM: the count of
    BRCA1's variants is attributable to BRCA1's NCBI record, and that is a
    claim this system can stand behind. `source_curie` carries that entity
    down from the caller, which is the only place that knows it.

    `node_or_edge_type` is "derived" rather than a graph label, so a
    downstream consumer can tell a computed value from a retrieved record
    and never present one as the other. Without `source_curie` the row
    still carries no citation and the caller's cite-or-refuse gate drops
    it, which is the correct outcome: an uncitable computed number is
    exactly the fluent-but-ungrounded output this system must not emit.
    """
    # F-2.1-J09: key each value by its RETURN alias where the query gave
    # one, so `count(v) AS variant_count` reaches the Write step as
    # `variant_count` rather than the positional `c0`. A column with no
    # alias keeps its positional name; see `cypher_query.column_labels_for`
    # for why an unaliased expression is not paraphrased into a label.
    labels = column_labels or {}
    fields = {labels.get(column, column): value for column, value in derived.items()}
    return {
        "node_or_edge_type": "derived",
        "curie": source_curie or "",
        "fields": fields,
        "source_url": source_url_for_curie(source_curie) if source_curie else None,
        "graph_snapshot_version": snapshot_version,
    }

def to_output_rows(
    raw_row: dict[str, Any],
    snapshot_version: str,
    derived_source_curie: str | None = None,
    column_labels: dict[str, str] | None = None,
) -> list[dict]:
    """Shape one raw AGE result row into zero or more output row shapes.

    `raw_row` is a dict keyed by the AGE output column name(s) declared in
    `execute_cypher`'s `as_clause` (for example `result` for a single
    column, or `c0`, `c1`, ... for a multi-column `RETURN`), with each
    value the raw agtype wire text `graph_connection.execute_cypher` read
    off the socket, unparsed.

    Each column value is parsed independently with `agtype.parse_agtype`.
    A multi-column `RETURN v, g` therefore yields one output row per
    column that decodes to a vertex or an edge, not one row per raw graph
    row: `CypherQueryRow` has no shape for merging two distinct entities
    into a single row, so a `v`-and-`g` pair becomes two output rows, each
    carrying its own type, CURIE, and citation, which is more faithful to
    "every fact links back to its source" than collapsing them into one
    row that could only cite one of the two.

    A column whose parsed value is not a vertex, an edge, or a path
    containing one, a bare scalar such as a count, or a value that failed
    to parse, contributes no output row. That omission is deliberate, not
    a bug: such a value has no label and no CURIE, so it has no citation,
    and CLAUDE.md's citation rule means it must never be emitted as an
    empty content row instead. The caller, `cypher_query._run_pipeline`,
    applies the matching cite-or-refuse gate at the row level: an
    entity that does parse but still resolves no `source_url` (an
    unmapped CURIE prefix such as GO, HP, or MONDO, or an edge with no
    CURIE of its own and no endpoint vertex in the same row, finding
    F-2.1-B06) is also dropped there, for the same reason.

    Finding F-2.1-B06: entities are collected from every column of `raw_row`
    before any of them is shaped, specifically so that an edge column
    (which never carries its own CURIE on the live graph) can be
    attributed to a genuine endpoint vertex's CURIE when that vertex was
    also returned in this same row, whether as a sibling column
    (`RETURN v, e, g`) or as an adjacent element of the same path
    (`RETURN p`). See `_shape_entity` and `_endpoint_curies_by_internal_id`.

    Args:
        raw_row: one row as read from the graph connection, keyed by
            output column name, each value unparsed agtype wire text (or
            already a parsed dict/list/scalar, never double-parsed).
        snapshot_version: the graph snapshot version string to stamp onto
            every shaped row.

    Returns:
        A list of dicts, each with exactly the keys `node_or_edge_type`,
        `curie`, `fields`, `source_url`, `graph_snapshot_version`. Empty
        when no column in `raw_row` decoded to a citable vertex or edge.
    """
    all_entities: list[dict[str, Any]] = []
    derived: dict[str, Any] = {}

    for column, value in raw_row.items():
        parsed = parse_agtype(value)
        entities = _iter_entities(parsed)
        if entities:
            all_entities.extend(entities)
        elif parsed is not None:
            # F-2.1-B05. A scalar or a list is a real answer, not an absence.
            # `count(sv)`, `d.name`, `collect(m.id)` all parse to something
            # that is not a vertex, so every one of them used to contribute
            # zero rows and the tool reported `status="empty"` while
            # `total_available` sat non-zero: it knew the graph had answered
            # and said nothing was found. Five of the six query shapes the
            # real plan model actually produced were projections or scalars,
            # so this refused the correct answer most of the time, including
            # every "how many" question.
            #
            # These are collected per column and emitted as ONE derived row
            # below, rather than one row each, because a projection's columns
            # are fields of a single result, not separate findings.
            derived[column] = parsed

    endpoint_curies = _endpoint_curies_by_internal_id(all_entities)
    shaped_rows = [
        _shape_entity(entity, snapshot_version, endpoint_curies) for entity in all_entities
    ]

    if derived:
        # F-2.1-J03: this used to read `if derived and not shaped_rows`, so a
        # row mixing an entity and a scalar, `RETURN g, count(v)`, emitted the
        # gene and silently discarded the count. The result reported
        # `status="ok"` with a valid citation while the number the user
        # actually asked for was gone, which is worse than F-2.1-B05's
        # original symptom: that refused, this answers with the answer
        # removed.
        #
        # A derived value is emitted whether or not entities share the row.
        # It still carries a citation only when one can be stood behind, and
        # `cypher_query`'s cite-or-refuse gate still drops it otherwise.
        shaped_rows.append(
            _shape_derived_value(
                derived, snapshot_version, derived_source_curie, column_labels
            )
        )

    return shaped_rows
