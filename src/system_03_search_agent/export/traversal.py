"""Bounded subgraph traversal over Layer 1, for the KGX export (T-4.4-02).

Walks outward from a seed set of CURIEs, one edge label at a time, and
returns the raw vertices and edges collected along the way. This module
never generates a Cypher query with an unbounded pattern and never asks
AGE for more rows than the caller's caps allow: every relationship
pattern names one explicit edge label from `graph_schema_constants.
EDGE_LABELS`, every pattern is a single fixed hop (`[r:label]`, never
`[r:label*]`), and every traversal query carries a literal `LIMIT` sized
from the caller's own `max_nodes` and `max_edges` budget, computed in
Python from validated integers, never from caller-supplied text.

Why per-label, not a bare pattern: `docs/build/Build_workflow_cadence.md`
and this phase's own premise gate both record the same live measurement.
An unscoped one-hop read off BRCA1 (`MATCH (g:Gene {id: $seed})-[r]->(n)
RETURN [r, n] LIMIT 10`) took 23.2 seconds, and the same read in the
reverse direction exceeded a 25 second budget. The identical hop scoped to
one edge label returned in 2.3 seconds. So every query this module builds
carries an explicit edge label, and anchors at least one end with a known
vertex label whenever `graph_schema_constants.EDGE_ENDPOINTS` names one.

Why a literal LIMIT in the Cypher text, not only a client-side truncation
after fetch: `graph_connection.execute_cypher`'s own `row_limit` parameter
truncates AFTER `cursor.fetchall()`, so a query with no LIMIT clause in its
own text can still make AGE materialize an unbounded result set server
side before a single row is dropped. That is exactly the memory-pressure
shape `graph_connection._MEMORY_GUARD_SQL` documents for finding
F-2.1-C15. A hub vertex's `mentioned_in` edge count can run into the tens
of thousands, so every traversal query here carries its own `LIMIT n`,
computed from the remaining node and edge budget, where `n` is always a
validated Python int from this module's own counters, concatenated with
plain string addition, never an f-string or `.format()` call and never a
value that could carry attacker-controlled text.

Every CURIE value that reaches a query (the seed id) is bound through
`graph_connection.execute_cypher`'s existing PREPARE and EXECUTE
mechanism, via the `params` argument. Every vertex label, edge label, and
LIMIT integer that appears in the Cypher text itself is validated against
`graph_schema_constants.VERTEX_LABELS` / `EDGE_LABELS`, or is a Python int
this module computed, before it is concatenated into the query string.

Depends on:
    - system_03_search_agent.tools.graph_connection (execute_cypher,
      GraphError, GraphTimeoutError, GraphConnectionError, GraphAuthError,
      ConnectionFactory)
    - system_03_search_agent.tools.graph_schema_constants (VERTEX_LABELS,
      EDGE_LABELS, EDGE_ENDPOINTS, LABEL_CURIE_PREFIXES, MAX_ROW_LIMIT)
    - system_03_search_agent.tools.agtype (parse_agtype)

Reads:
    - Layer 1 graph, read-only, through execute_cypher's existing
      credential and connection path. Adds no second connection factory
      and no second credential.

Writes:
    - Nothing. Pure traversal over the graph, returned to the caller as
      an in-memory TraversalResult.

Depended by:
    - system_03_search_agent.export.kgx (T-4.4-03, the KGX serialization
      step that shapes this module's output into nodes.tsv and edges.tsv)
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.graph_connection import (
    ConnectionFactory,
    GraphTimeoutError,
    execute_cypher,
)
from system_03_search_agent.tools.graph_schema_constants import (
    EDGE_ENDPOINTS,
    EDGE_LABELS,
    LABEL_CURIE_PREFIXES,
    MAX_ROW_LIMIT,
    VERTEX_LABELS,
)

# Defaults for the three caps a traversal respects. None of the three is
# pinned by the phase's tickets, so this module states and documents its
# own choice rather than leaving it implicit.
#
# DEFAULT_MAX_NODES reuses graph_schema_constants.MAX_ROW_LIMIT (500),
# the same ceiling a single cypher_query call already respects, so a
# default-configured export and a default-configured cypher_query call
# describe the same order of magnitude of "a bounded batch, not a dump".
#
# DEFAULT_MAX_EDGES is set above DEFAULT_MAX_NODES, not equal to it,
# because a KGX subgraph is expected to carry more edges than nodes once
# more than one hop or more than one edge label is in play (a single Gene
# node can be the subject of several edge labels at once).
#
# DEFAULT_TIME_BUDGET_S is twice the single-call 30 second budget
# (`.claude/rules/tool-call-budgets.md`'s cypher_query row), leaving room
# for a handful of per-label calls while still returning control to the
# caller inside a batch job's own reasonable wall-clock expectation,
# rather than letting an unattended export run for as long as its seed's
# neighbourhood happens to take.
DEFAULT_MAX_NODES: int = 500
DEFAULT_MAX_EDGES: int = 1000
DEFAULT_TIME_BUDGET_S: float = 60.0

# The per-call budget for one traversal query. Deliberately not
# graph_schema_constants.CYPHER_QUERY_TIMEOUT_SECONDS (90.0): that figure
# bakes in headroom for a plan-tier model's own generation latency, which
# has no part in this module's path since every query here is built
# deterministically in Python, never generated by a model call. The 30
# second figure is `.claude/rules/tool-call-budgets.md`'s own stated
# per-call budget for a graph query.
_PER_CALL_TIMEOUT_S: float = 30.0

# Cap names used in TraversalResult.truncation entries, in the fixed
# order they are reported when more than one is hit in the same run.
_CAP_MAX_NODES = "max_nodes"
_CAP_MAX_EDGES = "max_edges"
_CAP_TIME_BUDGET = "time_budget_s"
_CAP_ORDER: tuple[str, ...] = (_CAP_MAX_NODES, _CAP_MAX_EDGES, _CAP_TIME_BUDGET)

_SEED_AS_CLAUSE = "(n agtype)"
_HOP_AS_CLAUSE = "(r agtype, b agtype)"


def _invert_label_curie_prefixes() -> dict[str, tuple[str, ...]]:
    """Build a CURIE prefix -> candidate vertex label(s) map.

    Inverted from `graph_schema_constants.LABEL_CURIE_PREFIXES` (label ->
    prefixes), the same shape of index `cypher_query._PREFIX_TO_LABELS`
    builds for the same reason: a seed CURIE names a prefix, and this
    module needs to know which vertex label(s) to anchor a lookup query
    with. Two labels can share the same prefix (MedGen appears under both
    Disease and PhenotypicFeature), so the value is always a tuple, never
    assumed to be exactly one label.
    """
    mapping: dict[str, tuple[str, ...]] = {}
    for label, prefixes in LABEL_CURIE_PREFIXES.items():
        for prefix in prefixes:
            mapping[prefix] = mapping.get(prefix, ()) + (label,)
    return mapping


_PREFIX_TO_LABELS: dict[str, tuple[str, ...]] = _invert_label_curie_prefixes()


@dataclass
class TraversalResult:
    """The bounded subgraph a `traverse_subgraph` call collected.

    `nodes` is keyed by CURIE so a vertex reached by more than one path is
    naturally deduplicated. `edges` is a list, each entry the parsed AGE
    edge dict plus two keys this module adds: `subject_curie` and
    `object_curie`, the CURIEs of the edge's real start and end vertices,
    resolved from data already collected during this same traversal, never
    guessed and never fetched separately.
    """

    nodes: dict[str, dict[str, Any]]
    edges: list[dict[str, Any]]
    seeds_requested: list[str]
    seeds_resolved: list[str]
    hops: int
    max_nodes: int
    max_edges: int
    time_budget_s: float
    elapsed_s: float
    truncated: bool
    truncation: list[dict[str, Any]] = field(default_factory=list)
    empty_reason: str | None = None


class _Budget:
    """Mutable bookkeeping for the three caps, shared across one traversal call.

    Kept as a small stateful helper, not scattered across local variables
    in `traverse_subgraph`, because the same three checks (room left, time
    left, which cap was hit) are needed at every one of the traversal's
    nested loop levels: per seed, per hop, per edge label, per direction.
    """

    def __init__(self, max_nodes: int, max_edges: int, time_budget_s: float) -> None:
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.time_budget_s = time_budget_s
        self.start = time.monotonic()
        self.caps_hit: dict[str, int] = {}
        self.stop = False

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def time_remaining(self) -> float:
        return self.time_budget_s - self.elapsed()

    def mark(self, cap: str, value: int) -> None:
        self.caps_hit.setdefault(cap, value)

    def check_time(self) -> bool:
        """Return True and mark the time cap when the budget is exhausted."""
        if self.elapsed() >= self.time_budget_s:
            self.mark(_CAP_TIME_BUDGET, round(self.time_budget_s))
            self.stop = True
            return True
        return False

    def node_room(self, node_count: int) -> int:
        """The number of new nodes still affordable under max_nodes alone.

        Used for seed resolution, which only ever adds nodes and never
        edges: checking the combined `fetch_limit` there would let an
        exhausted `max_edges` (for example a caller-configured `0`)
        incorrectly block every seed lookup, even though a seed vertex on
        its own never touches the edge budget at all.
        """
        remaining = self.max_nodes - node_count
        if remaining <= 0:
            self.mark(_CAP_MAX_NODES, self.max_nodes)
        return remaining

    def fetch_limit(self, node_count: int, edge_count: int) -> int:
        """The number of new rows still affordable under both caps.

        Zero or negative means neither cap has room left; the caller must
        not issue another query for this round. Marks whichever cap (or
        both, when they tie) is currently the binding constraint, so a
        query that ends up returning more than this limit has a specific,
        named reason recorded before it is even issued.
        """
        remaining_nodes = self.max_nodes - node_count
        remaining_edges = self.max_edges - edge_count
        if remaining_nodes <= remaining_edges and remaining_nodes <= 0:
            self.mark(_CAP_MAX_NODES, self.max_nodes)
        if remaining_edges <= remaining_nodes and remaining_edges <= 0:
            self.mark(_CAP_MAX_EDGES, self.max_edges)
        return min(remaining_nodes, remaining_edges)

    def mark_binding_cap(self, node_count: int, edge_count: int) -> None:
        """Record which cap(s) are exhausted right now, without querying again."""
        remaining_nodes = self.max_nodes - node_count
        remaining_edges = self.max_edges - edge_count
        if remaining_nodes <= remaining_edges and remaining_nodes <= 0:
            self.mark(_CAP_MAX_NODES, self.max_nodes)
        if remaining_edges <= remaining_nodes and remaining_edges <= 0:
            self.mark(_CAP_MAX_EDGES, self.max_edges)

    def truncation_list(self) -> list[dict[str, Any]]:
        return [{"cap": cap, "value": self.caps_hit[cap]} for cap in _CAP_ORDER if cap in self.caps_hit]


def _validate_edge_labels(edge_labels: tuple[str, ...] | None) -> tuple[str, ...]:
    """Resolve `edge_labels` to the concrete tuple this traversal will use.

    `None` means every label in `graph_schema_constants.EDGE_LABELS`, in
    that module's own fixed order. A caller-supplied tuple is checked
    against the same fixed set; a label outside it is rejected before any
    query is built; this is defense in depth, since every caller in this
    repository is expected to pass either `None` or a subset of
    `EDGE_LABELS`, never raw external text.
    """
    if edge_labels is None:
        return EDGE_LABELS
    unknown = [label for label in edge_labels if label not in EDGE_LABELS]
    if unknown:
        raise ValueError(
            "edge_labels contains a label the graph does not have: "
            + ", ".join(unknown)
            + ". Valid labels are: "
            + ", ".join(EDGE_LABELS)
        )
    return tuple(edge_labels)


def _seed_lookup_cypher(label: str) -> str:
    """Build the seed vertex lookup query for one candidate label.

    `label` must already be a member of `graph_schema_constants.
    VERTEX_LABELS`; this is checked by the caller before this function is
    ever reached, and re-asserted here as defense in depth. Built with
    plain string concatenation, never an f-string or `.format()` call, per
    this phase's query-safety constraint. The seed CURIE itself is never
    concatenated: it is bound through the `$seed_id` named parameter.
    """
    if label not in VERTEX_LABELS:
        raise ValueError("refusing to build a query for an unknown vertex label: " + label)
    return "MATCH (n:" + label + " {id: $seed_id}) RETURN n LIMIT 1"


def _directions_for(seed_label: str, edge_label: str) -> list[tuple[str, str | None]]:
    """Which direction(s) to query `edge_label` from a vertex labelled `seed_label`.

    Returns a list of (direction, far_label) pairs, `direction` one of
    "out" or "in", `far_label` the vertex label to anchor the far end
    with, or None when `graph_schema_constants.EDGE_ENDPOINTS` records the
    pair as mixed (`close_match`, `exact_match`).

    - Mixed endpoints: both directions, far end unlabelled. The edge label
      itself is still explicit, which is the property that keeps this
      query fast; only the far vertex label is unknown.
    - `seed_label` matches only the start of the documented pair: outbound
      only, far end anchored with the documented end label.
    - `seed_label` matches only the end of the documented pair: inbound
      only, far end anchored with the documented start label.
    - `seed_label` matches both start and end (a self pair such as
      `orthologous_to`'s Gene-Gene): both directions, since the graph's
      own edges are directed and this module does not assume every
      relevant edge happens to have been stored outbound from any given
      vertex.
    - `seed_label` matches neither end: no directions at all. This is the
      "skip label pairs that cannot match" case T-4.4-02 names explicitly.
    """
    endpoints = EDGE_ENDPOINTS.get(edge_label)
    if endpoints is None:
        return [("out", None), ("in", None)]
    start_label, end_label = endpoints
    if start_label == seed_label and end_label == seed_label:
        return [("out", end_label), ("in", start_label)]
    if start_label == seed_label:
        return [("out", end_label)]
    if end_label == seed_label:
        return [("in", start_label)]
    return []


def _hop_cypher(
    seed_label: str,
    edge_label: str,
    far_label: str | None,
    direction: str,
    limit_n: int,
) -> str:
    """Build one bounded, single-hop, explicitly-labelled traversal query.

    Every label is checked against the fixed constants before it is
    concatenated. `limit_n` is a Python int this module computed from the
    caller's own caps, never a value derived from external text; it is
    converted with `str()` and concatenated the same way `GRAPH_NAME` is
    concatenated in `graph_connection.py`, never through an f-string or
    `.format()` call. The seed CURIE is never concatenated here either: it
    reaches the query through the `$seed_id` named parameter, bound by
    `execute_cypher`'s existing PREPARE and EXECUTE mechanism.

    Never emits a variable-length relationship pattern (`[r:label*]`):
    every pattern here is the single fixed hop `[r:edge_label]`, per the
    F-2.1-C15 bound `cypher_validator.validate_cypher` already enforces
    elsewhere in this codebase.
    """
    if seed_label not in VERTEX_LABELS:
        raise ValueError("refusing to build a query for an unknown vertex label: " + seed_label)
    if edge_label not in EDGE_LABELS:
        raise ValueError("refusing to build a query for an unknown edge label: " + edge_label)
    if far_label is not None and far_label not in VERTEX_LABELS:
        raise ValueError("refusing to build a query for an unknown vertex label: " + far_label)
    if limit_n < 1:
        raise ValueError("refusing to build a query with a non-positive LIMIT")
    if direction not in ("out", "in"):
        raise ValueError("direction must be 'out' or 'in'")

    far_pattern = "(b:" + far_label + ")" if far_label is not None else "(b)"
    seed_pattern = "(a:" + seed_label + " {id: $seed_id})"

    if direction == "out":
        match_clause = seed_pattern + "-[r:" + edge_label + "]->" + far_pattern
    else:
        match_clause = far_pattern + "-[r:" + edge_label + "]->" + seed_pattern

    return "MATCH " + match_clause + " RETURN r, b LIMIT " + str(limit_n)


def _lookup_seed(
    curie: str,
    timeout_s: float,
    connection_factory: ConnectionFactory | None,
) -> tuple[str, dict[str, Any]] | None:
    """Resolve one seed CURIE to (label, parsed vertex entity), or None.

    Tries each candidate vertex label for the CURIE's prefix in turn,
    anchored, indexed lookups (`graph_connection._ENABLE_SEQSCAN_OFF_SQL`
    applies to every call this module makes, since it is set per session
    inside `execute_cypher` itself). Returns as soon as one label matches.
    A CURIE with an unrecognised prefix, or one that matches no vertex
    under any of its candidate labels, returns None: the caller treats
    that as "this seed did not resolve", never as an exception.
    """
    prefix = curie.split(":", 1)[0] if ":" in curie else ""
    candidate_labels = _PREFIX_TO_LABELS.get(prefix, ())
    for label in candidate_labels:
        cypher = _seed_lookup_cypher(label)
        rows, _ = execute_cypher(
            cypher,
            params={"seed_id": curie},
            row_limit=1,
            timeout_s=timeout_s,
            connection_factory=connection_factory,
            as_clause=_SEED_AS_CLAUSE,
        )
        if not rows:
            continue
        parsed = parse_agtype(rows[0].get("n"))
        if isinstance(parsed, dict) and "label" in parsed:
            return label, parsed
    return None


def traverse_subgraph(
    seeds: Sequence[str],
    hops: int = 1,
    edge_labels: tuple[str, ...] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    connection_factory: ConnectionFactory | None = None,
) -> TraversalResult:
    """Walk outward from `seeds` over Layer 1, bounded by three caps.

    Breadth-first by hop. At each hop, every vertex discovered in the
    previous hop (or the seed set itself, for hop 1) is expanded one edge
    label at a time, in `graph_schema_constants.EDGE_LABELS`'s own fixed
    order (or `edge_labels`'s order, when the caller narrows the set). A
    label whose documented endpoints (`EDGE_ENDPOINTS`) cannot include the
    expanding vertex's own label is skipped without a query.

    Every traversal query carries a literal `LIMIT`, sized from whatever
    room remains under `max_nodes` and `max_edges`, plus one extra row: a
    query that returns the extra row proves more results exist than this
    call can afford, and the relevant cap is recorded in `truncation`
    without guessing at how much more there might be. The moment either
    cap reaches zero remaining room, or `time_budget_s` elapses, the
    traversal stops and returns whatever it collected so far; it never
    hangs and never raises for having run out of budget.

    A `GraphTimeoutError` from any single call is treated as the time
    budget having been effectively exhausted for this run: it is caught,
    recorded as the `time_budget_s` cap, and the traversal stops there. A
    `GraphConnectionError` or `GraphAuthError`, which mean the graph
    itself is unreachable or the credential is rejected rather than one
    query having run long, is not caught here and propagates to the
    caller, since that is a transport failure for the caller to handle,
    not a traversal-budget event.

    Args:
        seeds: one or more CURIEs to start from. A seed with an
            unrecognised prefix, or one that matches no vertex, does not
            raise; it is simply absent from `TraversalResult.
            seeds_resolved`.
        hops: the maximum number of edge traversals from any seed. `0`
            returns only the seeds that resolved, with no edges.
        edge_labels: the edge labels to traverse. `None` means every
            label in `graph_schema_constants.EDGE_LABELS`.
        max_nodes: the maximum number of distinct vertices (including
            resolved seeds) this call will collect.
        max_edges: the maximum number of distinct edges this call will
            collect.
        time_budget_s: the wall-clock budget for the whole call, checked
            before every query this function issues.
        connection_factory: forwarded to every `execute_cypher` call.
            Tests inject a fake factory here; production code leaves this
            None and gets the real environment-backed connection.

    Returns:
        A TraversalResult. `empty_reason` is set only when the result
        carries zero nodes and zero edges, and states why: either no seed
        resolved, or the time budget was exhausted before any seed could
        be looked up.
    """
    if hops < 0:
        raise ValueError("hops must be zero or greater")
    effective_edge_labels = _validate_edge_labels(edge_labels)
    budget = _Budget(max_nodes=max_nodes, max_edges=max_edges, time_budget_s=time_budget_s)

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edge_ids: set[Any] = set()
    curie_by_internal_id: dict[Any, str] = {}
    seeds_resolved: list[str] = []

    frontier: list[tuple[str, str]] = []  # (curie, label)

    for curie in seeds:
        if budget.check_time():
            break
        if budget.node_room(len(nodes)) <= 0:
            break
        remaining_call_time = max(min(_PER_CALL_TIMEOUT_S, budget.time_remaining()), 1.0)
        try:
            found = _lookup_seed(curie, remaining_call_time, connection_factory)
        except GraphTimeoutError:
            budget.mark(_CAP_TIME_BUDGET, round(time_budget_s))
            budget.stop = True
            break
        if found is None:
            continue
        label, entity = found
        properties = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
        resolved_curie = str(properties.get("id") or curie)
        internal_id = entity.get("id")
        nodes[resolved_curie] = entity
        if internal_id is not None:
            curie_by_internal_id[internal_id] = resolved_curie
        seeds_resolved.append(curie)
        frontier.append((resolved_curie, label))

    visited: set[str] = set(nodes.keys())

    depth = 0
    while depth < hops and frontier and not budget.stop:
        depth += 1
        next_frontier: list[tuple[str, str]] = []
        for seed_curie, seed_label in frontier:
            if budget.stop:
                break
            if budget.check_time():
                break
            if budget.fetch_limit(len(nodes), len(edges)) <= 0:
                budget.mark_binding_cap(len(nodes), len(edges))
                budget.stop = True
                break

            for edge_label in effective_edge_labels:
                if budget.stop:
                    break
                for direction, far_label in _directions_for(seed_label, edge_label):
                    if budget.stop:
                        break
                    if budget.check_time():
                        break
                    limit_n = budget.fetch_limit(len(nodes), len(edges))
                    if limit_n <= 0:
                        budget.stop = True
                        break
                    requested = min(limit_n + 1, MAX_ROW_LIMIT)
                    cypher = _hop_cypher(seed_label, edge_label, far_label, direction, requested)
                    remaining_call_time = max(
                        min(_PER_CALL_TIMEOUT_S, budget.time_remaining()), 1.0
                    )
                    try:
                        rows, _ = execute_cypher(
                            cypher,
                            params={"seed_id": seed_curie},
                            row_limit=requested,
                            timeout_s=remaining_call_time,
                            connection_factory=connection_factory,
                            as_clause=_HOP_AS_CLAUSE,
                        )
                    except GraphTimeoutError:
                        budget.mark(_CAP_TIME_BUDGET, round(time_budget_s))
                        budget.stop = True
                        break

                    got_more = len(rows) > limit_n or (
                        requested == MAX_ROW_LIMIT and len(rows) == MAX_ROW_LIMIT
                    )
                    if got_more:
                        caps_before = set(budget.caps_hit)
                        budget.mark_binding_cap(len(nodes), len(edges))
                        if set(budget.caps_hit) == caps_before:
                            # requested was capped by MAX_ROW_LIMIT below
                            # limit_n + 1; neither max_nodes nor max_edges
                            # read as exhausted by remaining-room alone,
                            # but this call could not prove there is no
                            # more, so both are recorded as the honest,
                            # conservative disclosure. Compared against a
                            # snapshot of caps_hit taken just before this
                            # call, not against "caps_hit is empty": an
                            # earlier, unrelated cap hit earlier in this
                            # same traversal must never suppress this
                            # query's own disclosure.
                            budget.mark(_CAP_MAX_NODES, max_nodes)
                            budget.mark(_CAP_MAX_EDGES, max_edges)
                    rows = rows[:limit_n]

                    for row in rows:
                        if len(nodes) >= max_nodes and len(edges) >= max_edges:
                            break
                        edge_entity = parse_agtype(row.get("r"))
                        vertex_entity = parse_agtype(row.get("b"))
                        if not isinstance(edge_entity, dict) or "label" not in edge_entity:
                            continue
                        edge_id = edge_entity.get("id")
                        if edge_id is not None and edge_id in seen_edge_ids:
                            continue

                        far_curie = None
                        far_props = None
                        if isinstance(vertex_entity, dict) and "label" in vertex_entity:
                            far_props = (
                                vertex_entity.get("properties")
                                if isinstance(vertex_entity.get("properties"), dict)
                                else {}
                            )
                            far_curie = str(far_props.get("id") or "") or None

                        if far_curie and far_curie not in nodes and len(nodes) < max_nodes:
                            nodes[far_curie] = vertex_entity
                            far_internal_id = vertex_entity.get("id")
                            if far_internal_id is not None:
                                curie_by_internal_id[far_internal_id] = far_curie
                            if far_curie not in visited:
                                next_frontier.append((far_curie, str(vertex_entity.get("label"))))
                                visited.add(far_curie)
                        elif far_curie and far_curie not in nodes:
                            # No room left for a new node; this edge is
                            # kept only if both its endpoints are already
                            # known, otherwise it is dropped along with
                            # the node it would have introduced.
                            continue

                        start_id = edge_entity.get("start_id")
                        end_id = edge_entity.get("end_id")
                        subject_curie = curie_by_internal_id.get(start_id)
                        object_curie = curie_by_internal_id.get(end_id)
                        if not subject_curie or not object_curie:
                            continue
                        if len(edges) >= max_edges:
                            budget.mark(_CAP_MAX_EDGES, max_edges)
                            continue

                        shaped_edge = dict(edge_entity)
                        shaped_edge["subject_curie"] = subject_curie
                        shaped_edge["object_curie"] = object_curie
                        edges.append(shaped_edge)
                        if edge_id is not None:
                            seen_edge_ids.add(edge_id)

        frontier = next_frontier

    elapsed_s = budget.elapsed()
    truncation = budget.truncation_list()
    truncated = bool(truncation)

    empty_reason: str | None = None
    if not nodes and not edges:
        if truncated:
            # Named generically over whichever cap(s) actually stopped the
            # traversal before anything could be collected, rather than
            # assuming it was always the time budget: a max_nodes or
            # max_edges cap configured at 0 stops the traversal before a
            # single seed lookup is even issued, the same empty-with-no-
            # results shape as a genuinely exhausted time budget, and the
            # reason text must name the real cap, not guess at time.
            caps_text = ", ".join(
                entry["cap"] + "=" + str(entry["value"]) for entry in truncation
            )
            empty_reason = (
                "the traversal hit a configured cap (" + caps_text + ") before any "
                "seed CURIE could be resolved or included: " + ", ".join(seeds)
            )
        else:
            empty_reason = (
                "0 of " + str(len(list(seeds))) + " requested seed CURIE(s) resolved to a "
                "vertex in the graph: " + ", ".join(seeds)
            )

    return TraversalResult(
        nodes=nodes,
        edges=edges,
        seeds_requested=list(seeds),
        seeds_resolved=seeds_resolved,
        hops=hops,
        max_nodes=max_nodes,
        max_edges=max_edges,
        time_budget_s=time_budget_s,
        elapsed_s=elapsed_s,
        truncated=truncated,
        truncation=truncation,
        empty_reason=empty_reason,
    )
