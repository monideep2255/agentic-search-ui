"""Bounded subgraph traversal over Layer 1, for the KGX export (T-4.4-02).

Walks outward from a seed set of CURIEs and returns the raw vertices and
edges collected along the way. This module never generates a Cypher query
with an unbounded pattern and never asks AGE for more rows than a fixed,
code-controlled ceiling: every relationship pattern names one explicit
edge label from `graph_schema_constants.EDGE_LABELS`, every pattern is a
single fixed hop (`[r:label]`, never `[r:label*]`), and every traversal
query carries a literal `LIMIT` that is a validated Python int, never a
value derived from caller-supplied text.

Why per-label, not a bare pattern: `docs/build/Build_workflow_cadence.md`
and this phase's own premise gate both record the same live measurement.
An unscoped one-hop read off BRCA1 (`MATCH (g:Gene {id: $seed})-[r]->(n)
RETURN [r, n] LIMIT 10`) took 23.2 seconds, and the same read in the
reverse direction exceeded a 25 second budget. The identical hop scoped to
one edge label returned in 2.3 seconds. So every query this module builds
carries an explicit edge label, and anchors at least one end with a known
vertex label whenever `graph_schema_constants.EDGE_ENDPOINTS` names one.

Why the query LIMIT is a fixed constant rather than the caller's own
remaining budget, which is what this module did before review round 2.
Two measurements taken on 2026-08-19 against the live graph, seed
`NCBIGene:7157`:

- Sizing the LIMIT from a small remaining budget makes the query planner
  unstable, not merely slower. `MATCH (a:Gene {id})-[r:in_taxon]->
  (b:OrganismTaxon) RETURN r, b LIMIT 5` exceeded the 30 second per-call
  budget and was killed, while the identical query at LIMIT 1, 13, 39,
  100 and 500 returned in 8.7, 2.0, 1.8, 1.8 and 2.0 seconds. This is the
  same row-count-estimate pathology `.claude/rules/attack-the-constraint.
  md` already records for a small-LIMIT CURIE lookup.
- A constant LIMIT is also cheaper overall. One full pass of the 13
  direction-scoped queries a default Gene export issues cost 34.4 seconds
  at LIMIT 500 and 50.2 seconds at LIMIT 39.

So the Cypher text now always says `LIMIT 500`
(`graph_schema_constants.MAX_ROW_LIMIT`), the caller's caps are enforced
in Python over the returned rows, and the server-side result set stays
bounded at 500 rows per query, which is the memory-pressure property the
literal LIMIT existed for in the first place.

Why a literal LIMIT in the Cypher text at all, not only a client-side
truncation after fetch: `graph_connection.execute_cypher`'s own
`row_limit` parameter truncates AFTER `cursor.fetchall()`, so a query with
no LIMIT clause in its own text can still make AGE materialize an
unbounded result set server side before a single row is dropped. That is
exactly the memory-pressure shape `graph_connection._MEMORY_GUARD_SQL`
documents for finding F-2.1-C15. A hub vertex's `mentioned_in` edge count
runs into the tens of thousands.

Why the caps are shared out by quota rather than spent first-come, first
-served (finding F-4.4-50, the phase's only critical). Walking the edge
labels in order against one shared node budget lets the first
high-cardinality label consume all of it: a default export of TP53
returned 500 Articles over `mentioned_in` and none of the 12 disease
neighbours the graph holds, because `gene_associated_with_condition` is
thirteenth in `EDGE_LABELS` and the budget was gone by then. The fix is a
scheduling property, not an ordering: every (vertex, edge label,
direction) work item in a hop is given an equal quota of the remaining
budget before any item is allowed a second helping, so no label can starve
another out of the export. The one case where an item can still get
nothing is a budget smaller than the number of work items, and that case
is disclosed rather than implied: `TraversalResult.edge_labels_traversed`
records the labels a query was actually issued for, never the labels the
caller asked for.

Every CURIE value that reaches a query (the seed id) is bound through
`graph_connection.execute_cypher`'s existing PREPARE and EXECUTE
mechanism, via the `params` argument. Every vertex label, edge label, and
LIMIT integer that appears in the Cypher text itself is validated against
`graph_schema_constants.VERTEX_LABELS` / `EDGE_LABELS`, or is a Python int
this module computed, before it is concatenated into the query string. No
f-string and no `.format()` call appears anywhere in this module.

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
# DEFAULT_TIME_BUDGET_S was 60.0 through review round 1 and is raised to
# 300.0 here, on a measurement rather than a feel. A default one-hop Gene
# export issues one query per (edge label, direction) pair its seed label
# can match: thirteen of them for a Gene, measured at 34.4 seconds of
# wall-clock in total on 2026-08-19. A 60 second budget left four seconds
# of headroom on the single commonest invocation, so ordinary transport
# variance would expire the budget mid-pass and silently cost whichever
# labels had not been reached yet. This is a batch export, not an
# interactive tool call, so the wall-clock ceiling is sized for the job
# rather than for a user waiting on a response. The per-call budget
# (`_PER_CALL_TIMEOUT_S`) is unchanged at the 30 seconds
# `.claude/rules/tool-call-budgets.md` states for a graph query.
DEFAULT_MAX_NODES: int = 500
DEFAULT_MAX_EDGES: int = 1000
DEFAULT_TIME_BUDGET_S: float = 300.0

# The per-call budget for one traversal query. Deliberately not
# graph_schema_constants.CYPHER_QUERY_TIMEOUT_SECONDS (90.0): that figure
# bakes in headroom for a plan-tier model's own generation latency, which
# has no part in this module's path since every query here is built
# deterministically in Python, never generated by a model call. The 30
# second figure is `.claude/rules/tool-call-budgets.md`'s own stated
# per-call budget for a graph query.
_PER_CALL_TIMEOUT_S: float = 30.0

# The literal LIMIT every hop query carries. Constant by design; see the
# module docstring's measurements for why it is not sized from the
# caller's remaining budget.
_QUERY_ROW_LIMIT: int = MAX_ROW_LIMIT

# Cap names used in TraversalResult.truncation entries, in the fixed
# order they are reported when more than one is hit in the same run.
#
# `per_query_row_limit` is the constant above, disclosed as itself.
# Finding F-4.4-51: an export bounded by that constant used to report the
# caller's own max_nodes and max_edges as the caps it hit, naming values
# it had provably not reached (501 nodes "hitting" a cap of 1200). A limit
# that bounds a result is disclosed as that limit, never attributed to a
# different one.
_CAP_MAX_NODES = "max_nodes"
_CAP_MAX_EDGES = "max_edges"
_CAP_TIME_BUDGET = "time_budget_s"
_CAP_PER_QUERY_ROW_LIMIT = "per_query_row_limit"
_CAP_ORDER: tuple[str, ...] = (
    _CAP_MAX_NODES,
    _CAP_MAX_EDGES,
    _CAP_TIME_BUDGET,
    _CAP_PER_QUERY_ROW_LIMIT,
)

# Named reasons a fetched row was discarded instead of exported. Finding
# F-4.4-08: this module used to drop such a row with a bare `continue`,
# counted nowhere and disclosable nowhere. Every discard path increments
# one of these, and the whole counter dict reaches the manifest whether or
# not any count is non-zero, so "nothing was dropped" is stated rather
# than inferred from silence.
DROP_MALFORMED_EDGE = "malformed_edge_row"
DROP_UNRESOLVED_ENDPOINT = "unresolved_edge_endpoint"
DROP_DUPLICATE_EDGE = "duplicate_edge_row"
_DROP_REASONS: tuple[str, ...] = (
    DROP_MALFORMED_EDGE,
    DROP_UNRESOLVED_ENDPOINT,
    DROP_DUPLICATE_EDGE,
)

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

    This index is a HINT that orders the search, never the set of labels a
    seed is allowed to have. See `_seed_candidate_labels`.
    """
    mapping: dict[str, tuple[str, ...]] = {}
    for label, prefixes in LABEL_CURIE_PREFIXES.items():
        for prefix in prefixes:
            mapping[prefix] = mapping.get(prefix, ()) + (label,)
    return mapping


_PREFIX_TO_LABELS: dict[str, tuple[str, ...]] = _invert_label_curie_prefixes()


def _seed_candidate_labels(curie: str) -> tuple[str, ...]:
    """Every vertex label a seed CURIE could resolve under, best guess first.

    Finding F-4.4-52: resolving a seed only through `LABEL_CURIE_PREFIXES`
    makes a whole region of the graph unreachable as a seed while the
    export reports it as absent. `NamedThing`, the dangling-endpoint stub
    label the five-database merge produces, maps to the EMPTY prefix tuple
    there, so no CURIE could ever select it, and `OMIM:100070` (read live
    off the graph on 2026-08-19, a real `NamedThing` vertex) came back as
    "did not resolve to a vertex in the graph" with exit code 0. A false
    negative about Layer 1 contents, from a tool whose whole job is being
    a faithful window onto Layer 1.

    The fix is not another prefix table entry, which would only move the
    hole to the next unlisted prefix. `LABEL_CURIE_PREFIXES` is a
    documented convention about which prefixes a label TYPICALLY carries,
    and this module must not treat a convention as an exhaustive index.
    So the prefix map orders the search and every remaining vertex label
    follows it: a seed that exists is findable whatever its label. Each
    attempt is an anchored, indexed lookup on `id`, measured live at
    roughly 1.8 seconds; the full 11-label sweep for a seed that is
    genuinely absent measured 20.1 seconds, and only a seed that the
    prefix hint failed to resolve ever pays for it.
    """
    prefix = curie.split(":", 1)[0] if ":" in curie else ""
    hinted = tuple(_PREFIX_TO_LABELS.get(prefix, ()))
    rest = tuple(label for label in VERTEX_LABELS if label not in hinted)
    return hinted + rest


@dataclass
class TraversalResult:
    """The bounded subgraph a `traverse_subgraph` call collected.

    `nodes` is keyed by CURIE so a vertex reached by more than one path is
    naturally deduplicated. `edges` is a list, each entry the parsed AGE
    edge dict plus two keys this module adds: `subject_curie` and
    `object_curie`, the CURIEs of the edge's real start and end vertices,
    resolved from data already collected during this same traversal, never
    guessed and never fetched separately.

    Three fields exist so a consumer is never left inferring what happened
    from silence:

    - `edge_labels_traversed`: the labels a query was actually ISSUED for,
      in the order they were first issued. Never the labels requested.
    - `dropped`: one counter per named discard reason, always present,
      including the zero counts.
    - `rows_fetched_not_exported`: rows this traversal read from the graph
      and did not export, because a cap stopped it first.
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
    edge_labels_requested: tuple[str, ...] = ()
    edge_labels_traversed: tuple[str, ...] = ()
    dropped: dict[str, int] = field(default_factory=dict)
    rows_fetched_not_exported: int = 0
    hop_limit_reached: bool = False
    unexpanded_frontier_nodes: int = 0
    per_query_row_limit: int = _QUERY_ROW_LIMIT


@dataclass
class _WorkItem:
    """One (frontier vertex, edge label, direction) query this hop will make.

    Buffering the rows on the item is what makes the fair quota possible
    with exactly one graph call per item: the whole result is fetched once
    under the constant `_QUERY_ROW_LIMIT`, the item's quota is taken from
    the buffer, and whatever is left stays buffered for the leftover pass
    rather than costing a second query.
    """

    seed_curie: str
    seed_label: str
    edge_label: str
    far_label: str | None
    direction: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    clipped: bool = False


class _Budget:
    """Mutable bookkeeping for the caps, shared across one traversal call.

    Kept as a small stateful helper, not scattered across local variables
    in `traverse_subgraph`, because the same three checks (room left, time
    left, which cap was hit) are needed at every one of the traversal's
    nested loop levels: per seed, per hop, per work item, per row.

    Every `mark` this class makes is provable at the moment it is made: a
    cap is recorded only when its own remaining count is at or below zero,
    or when the wall clock has genuinely elapsed. Nothing here marks a cap
    as a stand-in for "something else stopped us"; that is finding
    F-4.4-51, and the distinct `per_query_row_limit` entry exists so the
    honest answer has a name to be reported under.
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
        edges: checking the combined `room` there would let an exhausted
        `max_edges` (for example a caller-configured `0`) incorrectly
        block every seed lookup, even though a seed vertex on its own
        never touches the edge budget at all.
        """
        remaining = self.max_nodes - node_count
        if remaining <= 0:
            self.mark(_CAP_MAX_NODES, self.max_nodes)
        return remaining

    def room(self, node_count: int, edge_count: int) -> int:
        """The number of further rows affordable under both caps. Pure.

        One ingested row costs at most one node and at most one edge, so
        the smaller of the two remaining counts is the number of rows that
        is certainly affordable. Deliberately marks nothing: marking is
        `mark_binding_cap`'s job, so that a caller reading the room and a
        caller recording a stop are two separate, separately testable
        acts.
        """
        return min(self.max_nodes - node_count, self.max_edges - edge_count)

    def mark_binding_cap(self, node_count: int, edge_count: int) -> None:
        """Record which cap(s) are exhausted right now, without querying again."""
        remaining_nodes = self.max_nodes - node_count
        remaining_edges = self.max_edges - edge_count
        if remaining_nodes <= remaining_edges and remaining_nodes <= 0:
            self.mark(_CAP_MAX_NODES, self.max_nodes)
        if remaining_edges <= remaining_nodes and remaining_edges <= 0:
            self.mark(_CAP_MAX_EDGES, self.max_edges)

    def truncation_list(self) -> list[dict[str, Any]]:
        return [
            {"cap": cap, "value": self.caps_hit[cap]}
            for cap in _CAP_ORDER
            if cap in self.caps_hit
        ]


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
      itself stays explicit; only the far vertex label is unknown. Finding
      F-4.4-09 correctly objected that the previous wording ("which is the
      property that keeps this query fast") extrapolated from a
      measurement taken on a query with BOTH ends labelled. Measured
      directly on 2026-08-19, seed `NCBIGene:7157`, at LIMIT 500: the four
      unlabelled-far-end queries (`close_match` and `exact_match`, both
      directions) returned in 2.20, 2.09, 1.82 and 1.81 seconds, against
      1.82 to 7.36 seconds for the nine labelled-far-end queries in the
      same pass. The structural property the speed depends on, an explicit
      edge label on every emitted pattern, is asserted by
      `test_kgx_traversal.py`; the latency figures above are a recorded
      measurement, not a claim this module makes about future runs.
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
    concatenated. `limit_n` is a Python int this module controls (in the
    traversal itself it is always the `_QUERY_ROW_LIMIT` constant), never
    a value derived from external text; it is converted with `str()` and
    concatenated the same way `GRAPH_NAME` is concatenated in
    `graph_connection.py`, never through an f-string or `.format()` call.
    The seed CURIE is never concatenated here either: it reaches the query
    through the `$seed_id` named parameter, bound by `execute_cypher`'s
    existing PREPARE and EXECUTE mechanism.

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
    budget: _Budget,
    connection_factory: ConnectionFactory | None,
) -> tuple[str, dict[str, Any]] | None:
    """Resolve one seed CURIE to (label, parsed vertex entity), or None.

    Tries each candidate vertex label from `_seed_candidate_labels` in
    turn, as anchored, indexed lookups (`graph_connection.
    _ENABLE_SEQSCAN_OFF_SQL` applies to every call this module makes,
    since it is set per session inside `execute_cypher` itself). Returns
    as soon as one label matches. A CURIE that matches no vertex under ANY
    vertex label returns None: the caller treats that as "this seed did
    not resolve", never as an exception.

    The wall-clock budget is checked between label attempts, not only
    before the first one, because the sweep is now up to eleven calls and
    a budget checked once at the top would be a budget the sweep can
    silently overrun.
    """
    for label in _seed_candidate_labels(curie):
        if budget.check_time():
            return None
        cypher = _seed_lookup_cypher(label)
        timeout_s = _per_call_timeout(budget)
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


def _per_call_timeout(budget: _Budget) -> float:
    """The per-call timeout for the next graph call.

    Never above `_PER_CALL_TIMEOUT_S` (T-4.4-02's fifth criterion), never
    above whatever wall-clock the traversal has left, and never below one
    second, so a nearly-exhausted budget asks for a short call rather than
    a zero or negative one.
    """
    return max(min(_PER_CALL_TIMEOUT_S, budget.time_remaining()), 1.0)


def _far_curie_of(vertex_entity: Any) -> str | None:
    """The far vertex's own CURIE, or None when the payload cannot supply one."""
    if not isinstance(vertex_entity, dict) or "label" not in vertex_entity:
        return None
    properties = vertex_entity.get("properties")
    if not isinstance(properties, dict):
        return None
    return str(properties.get("id") or "") or None


def traverse_subgraph(
    seeds: Sequence[str],
    hops: int = 1,
    edge_labels: tuple[str, ...] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    connection_factory: ConnectionFactory | None = None,
) -> TraversalResult:
    """Walk outward from `seeds` over Layer 1, bounded by the caps below.

    Breadth-first by hop. At each hop, every vertex discovered in the
    previous hop (or the seed set itself, for hop 1) is paired with every
    requested edge label and every direction that label's documented
    endpoints (`EDGE_ENDPOINTS`) allow for that vertex's own label. A
    label whose endpoints cannot include the expanding vertex's label is
    skipped without a query.

    Those pairs are the hop's WORK ITEMS, and they are scheduled fairly
    rather than in list order (finding F-4.4-50):

    1. Each item gets an equal quota of the room remaining under
       `max_nodes` and `max_edges`, so no single high-cardinality label
       can consume the whole budget before a low-cardinality one is
       reached.
    2. Each item is queried exactly once, under the constant
       `_QUERY_ROW_LIMIT`, and the rows beyond its quota stay buffered.
    3. Whatever room is left once every item has taken its quota is then
       handed out one row at a time, round robin over the items that still
       have buffered rows, so a budget is never left unspent just because
       the fair share happened to be small.

    The traversal stops the moment either count cap has no room left, or
    `time_budget_s` elapses, and returns whatever it collected; it never
    hangs and never raises for having run out of budget. Every stop is
    attributed to the bound that actually caused it: `max_nodes` and
    `max_edges` only when their own remaining count is zero,
    `per_query_row_limit` when a query was clipped at `_QUERY_ROW_LIMIT`
    and its whole buffer was exported, `time_budget_s` when the wall clock
    ran out.

    A `GraphTimeoutError` from any single call is treated as the time
    budget having been effectively exhausted for this run: it is caught,
    recorded as the `time_budget_s` cap, and the traversal stops there. A
    `GraphConnectionError` or `GraphAuthError`, which mean the graph
    itself is unreachable or the credential is rejected rather than one
    query having run long, is not caught here and propagates to the
    caller, since that is a transport failure for the caller to handle,
    not a traversal-budget event.

    Args:
        seeds: one or more CURIEs to start from. A seed that matches no
            vertex under any vertex label does not raise; it is simply
            absent from `TraversalResult.seeds_resolved`.
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
        resolved, or a cap stopped the traversal before any seed could be
        looked up.

    Known bound, stated rather than left to be discovered: when the room
    remaining is smaller than the number of work items in a hop, the quota
    floors at one row and only that many items can be queried at all. The
    items that were never queried are visible in
    `TraversalResult.edge_labels_traversed`, which lists exactly the
    labels a query was issued for.
    """
    if hops < 0:
        raise ValueError("hops must be zero or greater")
    requested_edge_labels = _validate_edge_labels(edge_labels)
    budget = _Budget(max_nodes=max_nodes, max_edges=max_edges, time_budget_s=time_budget_s)

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edge_ids: set[Any] = set()
    curie_by_internal_id: dict[Any, str] = {}
    seeds_resolved: list[str] = []
    visited: set[str] = set()
    dropped: dict[str, int] = dict.fromkeys(_DROP_REASONS, 0)
    traversed_labels: list[str] = []
    next_frontier: list[tuple[str, str]] = []
    rows_fetched_not_exported = 0

    frontier: list[tuple[str, str]] = []  # (curie, label)

    # Finding F-4.4-60: the same CURIE passed twice used to cost a second
    # full round of lookup queries and a second expansion, on a transport
    # this phase has already recorded as fragile under load. The same raw
    # string can only ever resolve to the same vertex, so the lookup is
    # memoised, and `visited` below keeps the duplicate out of the
    # frontier. `seeds_resolved` still lists both occurrences, matching
    # the manifest's `seeds`, which is deliberately never deduplicated.
    seed_lookups: dict[str, tuple[str, dict[str, Any]] | None] = {}

    for curie in seeds:
        if budget.check_time():
            break
        if budget.node_room(len(nodes)) <= 0:
            break
        try:
            if curie in seed_lookups:
                found = seed_lookups[curie]
            else:
                found = _lookup_seed(curie, budget, connection_factory)
                seed_lookups[curie] = found
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
        if resolved_curie not in visited:
            visited.add(resolved_curie)
            frontier.append((resolved_curie, label))

    def _ingest(row: dict[str, Any]) -> None:
        """Fold one fetched row into the collected nodes and edges.

        Every path that discards the row increments a named counter in
        `dropped` (finding F-4.4-08). There is no bare `continue` here and
        no unreachable defence-in-depth arm: the caller guarantees room
        before calling, so a cap check inside this function would be a
        branch that cannot fire, which is exactly the dead-guard shape
        findings F-4.4-06 and F-4.4-07 were filed for.
        """
        edge_entity = parse_agtype(row.get("r"))
        vertex_entity = parse_agtype(row.get("b"))
        if not isinstance(edge_entity, dict) or "label" not in edge_entity:
            dropped[DROP_MALFORMED_EDGE] += 1
            return

        edge_id = edge_entity.get("id")
        if edge_id is not None and edge_id in seen_edge_ids:
            dropped[DROP_DUPLICATE_EDGE] += 1
            return

        far_curie = _far_curie_of(vertex_entity)
        if far_curie and far_curie not in nodes:
            nodes[far_curie] = vertex_entity
            far_internal_id = vertex_entity.get("id")
            if far_internal_id is not None:
                curie_by_internal_id[far_internal_id] = far_curie
            if far_curie not in visited:
                visited.add(far_curie)
                next_frontier.append((far_curie, str(vertex_entity.get("label"))))

        subject_curie = curie_by_internal_id.get(edge_entity.get("start_id"))
        object_curie = curie_by_internal_id.get(edge_entity.get("end_id"))
        if not subject_curie or not object_curie:
            dropped[DROP_UNRESOLVED_ENDPOINT] += 1
            return

        shaped_edge = dict(edge_entity)
        shaped_edge["subject_curie"] = subject_curie
        shaped_edge["object_curie"] = object_curie
        edges.append(shaped_edge)
        if edge_id is not None:
            seen_edge_ids.add(edge_id)

    def _consume(item: _WorkItem, allowance: int) -> None:
        """Take up to `allowance` buffered rows from `item` and ingest them.

        Fairness is measured in rows OFFERED, not rows that happened to
        add a node: two items that each get twenty rows have been treated
        equally whether or not the graph gave them twenty distinct new
        neighbours.
        """
        taken = 0
        while taken < allowance and item.rows:
            if budget.check_time():
                return
            if budget.room(len(nodes), len(edges)) <= 0:
                budget.mark_binding_cap(len(nodes), len(edges))
                budget.stop = True
                return
            _ingest(item.rows.pop(0))
            taken += 1

    def _query(item: _WorkItem) -> bool:
        """Fetch the item's rows. Returns False when the traversal must stop."""
        cypher = _hop_cypher(
            item.seed_label, item.edge_label, item.far_label, item.direction, _QUERY_ROW_LIMIT
        )
        try:
            rows, _ = execute_cypher(
                cypher,
                params={"seed_id": item.seed_curie},
                row_limit=_QUERY_ROW_LIMIT,
                timeout_s=_per_call_timeout(budget),
                connection_factory=connection_factory,
                as_clause=_HOP_AS_CLAUSE,
            )
        except GraphTimeoutError:
            budget.mark(_CAP_TIME_BUDGET, round(time_budget_s))
            budget.stop = True
            return False
        if item.edge_label not in traversed_labels:
            traversed_labels.append(item.edge_label)
        item.rows = list(rows)
        item.clipped = len(item.rows) >= _QUERY_ROW_LIMIT
        return True

    depth = 0
    while depth < hops and frontier and not budget.stop:
        depth += 1
        next_frontier = []
        items = [
            _WorkItem(
                seed_curie=seed_curie,
                seed_label=seed_label,
                edge_label=edge_label,
                far_label=far_label,
                direction=direction,
            )
            for seed_curie, seed_label in frontier
            for edge_label in requested_edge_labels
            for direction, far_label in _directions_for(seed_label, edge_label)
        ]
        if not items:
            # No requested edge label can attach to any vertex in this
            # frontier, so there is nothing further this request could
            # ever reach. The frontier is cleared rather than left
            # standing, because leaving it would make the traversal report
            # the hop limit as the reason vertices went unexpanded when
            # the real reason is that the requested labels do not apply.
            frontier = []
            break

        room_at_hop_start = budget.room(len(nodes), len(edges))
        if room_at_hop_start <= 0:
            budget.mark_binding_cap(len(nodes), len(edges))
            budget.stop = True
            break
        quota = max(1, room_at_hop_start // len(items))

        queried: list[_WorkItem] = []
        for item in items:
            if budget.stop or budget.check_time():
                break
            if budget.room(len(nodes), len(edges)) <= 0:
                budget.mark_binding_cap(len(nodes), len(edges))
                budget.stop = True
                break
            if not _query(item):
                break
            queried.append(item)
            _consume(item, quota)

        # The leftover pass. Anything the fair quota did not spend is
        # handed out one row at a time, round robin, so an item whose
        # neighbourhood was smaller than its quota releases the remainder
        # to the items that still have rows buffered.
        pending = [item for item in queried if item.rows]
        while pending and not budget.stop:
            progressed = False
            for item in list(pending):
                if budget.stop or budget.check_time():
                    break
                if budget.room(len(nodes), len(edges)) <= 0:
                    budget.mark_binding_cap(len(nodes), len(edges))
                    budget.stop = True
                    break
                _consume(item, 1)
                progressed = True
                if not item.rows:
                    pending.remove(item)
            if not progressed:
                break

        # `per_query_row_limit` is disclosed only where it is provably the
        # binding constraint: the query came back holding exactly the
        # constant's worth of rows (so the graph had at least that many
        # and possibly more), and every one of those rows was exported (so
        # no count cap stopped the export short). Any other stop belongs
        # to whichever cap `mark_binding_cap` or `check_time` recorded.
        for item in queried:
            if item.clipped and not item.rows:
                budget.mark(_CAP_PER_QUERY_ROW_LIMIT, _QUERY_ROW_LIMIT)
                break

        rows_fetched_not_exported += sum(len(item.rows) for item in queried)
        frontier = next_frontier

    # A frontier still holding vertices when the loop ends, with no cap
    # having stopped it, means the hop limit is what bounded the export.
    # Reported as its own explicit field rather than folded into
    # `truncation` (finding F-4.4-10 asked for the hop limit to be
    # reported as a bound, and T-4.4-02's fourth criterion names it
    # alongside the two count caps). It is deliberately NOT a truncation
    # entry: `truncated` means "this export is smaller than what was asked
    # for", and the hop limit is part of what was asked for, so counting
    # it as truncation would set the flag on almost every ordinary export
    # and cost the flag its meaning. Stated explicitly and
    # unconditionally instead, so a consumer reads the bound rather than
    # inferring it from silence.
    #
    # `unexpanded_frontier_nodes` counts vertices left unexpanded for ANY
    # reason and is therefore reported on its own, not gated on this flag:
    # when a cap stopped the traversal first, that cap is the reason to
    # read and it is already named in `truncation`, while the count still
    # says how much was left on the table.
    hop_limit_reached = bool(frontier) and not budget.stop

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
                "0 of " + str(len(list(seeds))) + " requested seed CURIE(s) matched a "
                "vertex under any of the " + str(len(VERTEX_LABELS)) + " vertex labels "
                "this graph carries: " + ", ".join(seeds)
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
        edge_labels_requested=tuple(requested_edge_labels),
        edge_labels_traversed=tuple(traversed_labels),
        dropped=dropped,
        rows_fetched_not_exported=rows_fetched_not_exported,
        hop_limit_reached=hop_limit_reached,
        unexpanded_frontier_nodes=len(frontier),
        per_query_row_limit=_QUERY_ROW_LIMIT,
    )
