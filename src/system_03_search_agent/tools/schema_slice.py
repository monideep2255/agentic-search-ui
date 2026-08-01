"""The graph schema text injected into the Cypher generation prompt.

Two shapes are exposed:

- `full_schema_text()`: the complete, static concept-level schema (all 11
  vertex labels, all 14 edge labels, all 9 CURIE prefixes, plus the three
  performance rules). This is the shape that belongs in the stable prompt
  prefix (`.claude/rules/prompt-cache-discipline.md`): it never changes
  within a session, so it is safe to cache.
- `build_schema_slice(query_class, target_entities)`: a per-query slice
  restricted to the labels and predicates plausibly relevant to that call.
  This shape varies per query and therefore belongs in the dynamic suffix
  of a prompt, never the stable prefix, exactly as
  `.claude/rules/prompt-cache-discipline.md` distinguishes "the static
  graph and BioLink schema at the concept level ... not the per-query
  slice."

Both functions are pure functions of the constants in
`graph_schema_constants`, so both are deterministic: the same arguments
always produce byte-identical output, proven in
`tests/system_03_search_agent/tools/test_schema_slice.py` with a SHA-256
equality assertion.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants (GRAPH_NAME,
      VERTEX_LABELS, EDGE_LABELS, EDGE_ENDPOINTS, CURIE_PREFIXES,
      LABEL_CURIE_PREFIXES). Every label, predicate, and prefix comes from
      that single source of truth; nothing here is a second copy.

Reads:
    - Nothing at import time or at call time. No live graph query, no
      database read: the label set is a static snapshot property
      (graph_schema_constants's own docstring explains why).

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_generation (T-2.1-03)
    - system_03_search_agent.tools.cypher_query (T-2.1-07, integration)
"""

from __future__ import annotations

from collections.abc import Sequence

from system_03_search_agent.tools.graph_schema_constants import (
    CURIE_PREFIXES,
    EDGE_ENDPOINTS,
    EDGE_LABELS,
    GRAPH_NAME,
    LABEL_CURIE_PREFIXES,
    VERTEX_LABELS,
)

__all__ = ["GRAPH_NAME", "build_schema_slice", "full_schema_text"]

# Reference section H's three performance rules, restated verbatim in
# substance so a generation prompt carries them wherever the schema text
# goes, whether the full text or a slice.
_PERFORMANCE_RULES: tuple[str, ...] = (
    (
        "Rule 1: always specify the edge label explicitly, for example "
        "[:is_sequence_variant_of]. An untyped relationship such as [r] or "
        "--> compiles to a UNION ALL across all 14 edge tables, which is "
        "always slow."
    ),
    (
        "Rule 2: match by id whenever possible, using the correct CURIE "
        "prefix. The id field is GIN-indexed on the four largest vertex "
        "labels; matching by name falls back to a sequential scan unless the "
        "result set is naturally tiny."
    ),
    (
        "Rule 3: keep regex matches narrow. A broad regex on a large label "
        "such as Article (40M rows) or Gene (67M rows) cannot use any index "
        "and is a death sentence on those labels."
    ),
)

# How many hops of neighbor-label expansion each query_class gets before
# the edge set is computed. `None` means "no filtering, use the full
# schema": exploratory queries need the whole taxonomy to explore, and any
# query class with no target_entities to anchor a slice has nothing to
# filter by in the first place.
_QUERY_CLASS_HOPS: dict[str, int | None] = {
    "lookup": 0,
    "single_hop": 1,
    "multi_hop": 2,
    "aggregate": 2,
    "exploratory": None,
}

# The floor below which `query_class` is not allowed to narrow the slice,
# for as long as the Think step's classification is a stub.
#
# This is the root cause the fourth judge's PREMISE failure came down to,
# and it is a composition defect: two components, each defensible alone.
#
# Think emits a hardcoded `query_class="lookup"` for every query
# (`core/graph.py`, T-2.0-07). Real classification is a later phase. So
# "lookup" is not a classification here, it is a placeholder.
#
# Meanwhile `lookup` maps to 0 hops, which for a Gene anchor renders a
# slice containing exactly one edge: `orthologous_to`, Gene to Gene. Zero
# hops is the right slice for a true lookup ("what is BRCA1's name"), and
# it is the whole schema the generator ever sees.
#
# Composed, the model is asked "which diseases are associated with BRCA1?"
# and handed a schema in which no disease exists and the only traversal
# available is gene-to-gene. It cannot express the correct query. It did
# the only thing the schema permitted and returned twenty-five non-human
# orthologs, `status="ok"`, every row carrying a resolving NCBI citation.
# That was recorded as a generation-quality failure through three review
# rounds. Generation was not the problem; it was answering the only
# question the schema left askable.
#
# The same defect drove the OOM: `orthologous_to` is the one traversal a
# `lookup` slice offers, so ortholog queries are what generation kept
# producing, and one of them exhausted the server.
#
# Slicing on a value that is always the same placeholder is narrowing on
# noise, so the floor holds until Think classifies for real. At that point
# this drops back to the per-class table, which is sound once its input is.
# F-2.1-A5-03. A floor of 1 made the floor the CEILING. Think emits a
# hardcoded `lookup` for every query, `lookup` maps to 0 hops, and
# `max(0, 1)` is 1, so every question the system will ever be asked got
# exactly one hop. `multi_hop` and `aggregate` map to 2 and Think never
# emits either.
#
# That is round four's root cause displaced by one hop rather than
# removed. A one-hop slice from a Gene anchor omits `PhenotypicFeature`,
# `OntologyClass`, `has_phenotype`, `has_mesh_annotation`, and
# `subclass_of`, because `_edges_for_labels` requires BOTH endpoints
# inside the label set. So "what phenotypic features are associated with
# the diseases linked to BRCA1" was handed a schema in which the answer
# does not exist, and the generator answered the only question the schema
# left askable. Confirmed live: a phenotypic-feature question returned
# four cited DISEASES, `status="ok"`, no flag.
#
# The floor is now the widest bounded depth in the per-class table, which
# is what `multi_hop` and `aggregate` already ask for. The principle is
# the same one that set the floor at all: a classification that is always
# the same placeholder carries no information, so slicing on it narrows on
# noise, and the safe default is the widest BOUNDED slice rather than the
# narrowest. `exploratory` still means the full schema, so this is not
# that.
#
# Measured cost, Gene anchor: 1809 characters at one hop, 2095 at two. The
# extra 286 characters buy every two-hop question in the system.
#
# This drops back to the per-class table when Think classifies for real,
# at which point the table is sound because its input finally is.
_STUB_CLASSIFIER_HOP_FLOOR = 2


def _endpoint_text(edge: str) -> str:
    """Render one edge's typical endpoint pair, or a mixed-pair note.

    A generator that knows the endpoint pair for every edge it is offered
    cannot invent a relationship the graph has no label for (T-2.1-02's
    acceptance criterion).
    """
    endpoints = EDGE_ENDPOINTS.get(edge)
    if endpoints is None:
        return "endpoints vary (mixed label pairs, verify before use)"
    source, target = endpoints
    return f"{source} to {target}"


def _prefix_text(label: str) -> str:
    prefixes = LABEL_CURIE_PREFIXES.get(label, ())
    if not prefixes:
        return "none (dangling-endpoint stub label)"
    return ", ".join(prefixes)


def _ordered_prefixes(labels: Sequence[str]) -> tuple[str, ...]:
    """The CURIE prefixes used by `labels`, in the canonical CURIE_PREFIXES
    order, so the emitted list is deterministic regardless of set
    iteration order.
    """
    used = {prefix for label in labels for prefix in LABEL_CURIE_PREFIXES.get(label, ())}
    return tuple(prefix for prefix in CURIE_PREFIXES if prefix in used)


def _render_slice(labels: Sequence[str], edges: Sequence[str]) -> str:
    """Render a schema text block for exactly `labels` and `edges`, in
    their canonical (graph-doc) order. Used by both `full_schema_text`
    (called with every label and edge) and `build_schema_slice` (called
    with a filtered subset).
    """
    lines: list[str] = [f"Graph: {GRAPH_NAME}", "", "Vertex labels:"]
    for label in labels:
        lines.append(f"  {label}: CURIE prefix {_prefix_text(label)}")

    lines.append("")
    lines.append("Edge labels (always specify the label explicitly, never an untyped edge):")
    for edge in edges:
        lines.append(f"  {edge}: typical endpoints {_endpoint_text(edge)}")

    prefixes_in_scope = _ordered_prefixes(labels)
    lines.append("")
    lines.append("CURIE prefixes in scope:")
    for prefix in prefixes_in_scope:
        lines.append(f"  {prefix}")

    lines.append("")
    lines.append("Performance rules:")
    for rule in _PERFORMANCE_RULES:
        lines.append(f"  {rule}")

    return "\n".join(lines)


def full_schema_text() -> str:
    """The complete, static concept-level schema: all 11 vertex labels, all
    14 edge labels, all 9 CURIE prefixes, plus the three performance
    rules. Deterministic and byte-identical across calls, since it is a
    pure function of the constants module.
    """
    return _render_slice(VERTEX_LABELS, EDGE_LABELS)


def _direct_labels(target_entities: Sequence[str]) -> set[str]:
    """The vertex labels directly implied by `target_entities`' CURIE
    prefixes, via the inverse of LABEL_CURIE_PREFIXES.
    """
    prefixes = {entity.split(":", 1)[0] for entity in target_entities if entity}
    labels: set[str] = set()
    for label, label_prefixes in LABEL_CURIE_PREFIXES.items():
        if any(prefix in label_prefixes for prefix in prefixes):
            labels.add(label)
    return labels


def _expand_labels(labels: set[str], hops: int) -> set[str]:
    """Expand `labels` outward by `hops` steps along EDGE_ENDPOINTS pairs.

    A mixed-endpoint edge (EDGE_ENDPOINTS value of None) never drives an
    expansion step, since it names no concrete label pair to expand along;
    it is still offered in the rendered edge list separately (see
    `_edges_for_labels`), just not used to grow the label set.
    """
    current = set(labels)
    for _ in range(hops):
        grown = set(current)
        for endpoints in EDGE_ENDPOINTS.values():
            if endpoints is None:
                continue
            source, target = endpoints
            if source in current:
                grown.add(target)
            if target in current:
                grown.add(source)
        current = grown
    return current


def _edges_for_labels(labels: set[str], *, include_mixed: bool) -> set[str]:
    """The edges whose typical endpoint pair lies entirely within `labels`.

    Mixed-endpoint edges (close_match, exact_match) are included only when
    `include_mixed` is set, which build_schema_slice ties to whether any
    hop expansion happened at all: a bare lookup (0 hops) gets the
    tightest possible slice, never the cross-cutting mixed edges.
    """
    edges: set[str] = set()
    for edge, endpoints in EDGE_ENDPOINTS.items():
        if endpoints is None:
            if include_mixed:
                edges.add(edge)
            continue
        source, target = endpoints
        if source in labels and target in labels:
            edges.add(edge)
    return edges


def build_schema_slice(query_class: str, target_entities: Sequence[str] | None = None) -> str:
    """Return the schema text sliced to what `query_class` and
    `target_entities` plausibly need, never the full 693M-edge topology
    dump.

    Raises:
        ValueError: if `query_class` is not one of the five values Section
            6.1's `query_class` enum defines.
    """
    if query_class not in _QUERY_CLASS_HOPS:
        raise ValueError(
            f"unknown query_class {query_class!r}; expected one of "
            f"{sorted(_QUERY_CLASS_HOPS)}"
        )

    hops = _QUERY_CLASS_HOPS[query_class]
    if hops is not None:
        hops = max(hops, _STUB_CLASSIFIER_HOP_FLOOR)
    entities = tuple(target_entities) if target_entities else ()

    if hops is None or not entities:
        # Exploratory queries, and any query class with no target entities
        # to anchor a slice, get the full label and predicate set. This is
        # still the compact name-and-endpoint form, never a row-count
        # topology dump.
        return _render_slice(VERTEX_LABELS, EDGE_LABELS)

    direct_labels = _direct_labels(entities)
    if not direct_labels:
        # No recognized CURIE prefix among target_entities: fall back to
        # the full schema rather than emit a slice with nothing in it.
        return _render_slice(VERTEX_LABELS, EDGE_LABELS)

    expanded_labels = _expand_labels(direct_labels, hops)
    include_mixed = hops > 0
    edge_names = _edges_for_labels(expanded_labels, include_mixed=include_mixed)

    ordered_labels = tuple(label for label in VERTEX_LABELS if label in expanded_labels)
    ordered_edges = tuple(edge for edge in EDGE_LABELS if edge in edge_names)
    return _render_slice(ordered_labels, ordered_edges)
