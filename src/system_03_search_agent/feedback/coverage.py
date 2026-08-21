"""`coverage_tags` derivation: what a run's citations actually named (T-4.6-05).

Depends on:
    - system_03_search_agent.tools.graph_schema_constants (EDGE_LABELS,
      LABEL_CURIE_PREFIXES): the graph's own fixed vertex-label and
      edge-label vocabulary. Every tag this module ever emits is a member
      of one of these two closed sets, never an invented string.

Reads:
    - Nothing. Pure function over an already-assembled citations list.

Writes:
    - Nothing.

Section 15: "`concept:<Label>` and `predicate:<edge_type>` strings, feeding
the coverage metric's planned move from hand-mapping to dynamic
instrumentation." `Evaluation_playbook.md`'s coverage metric section names
the same move: "Hand-mapped now, replaced by dynamic instrumentation once
the agent runs and its Cypher is observable." This module is build phase
4.6's slice of that dynamic instrumentation: it derives tags from what a
finished run actually cited, never from what a query planned to do or from
a fixed per-query-type table.

## `predicate:<edge_type>` is DEFERRED, by product-owner decision, 2026-08-21

This module currently emits `concept:<Label>` tags only. It does not emit
`predicate:<edge_type>` tags, and that is a deliberate, recorded scope
reduction, not an oversight. Read this section before touching this file.

`tracker/phase_4.6.md`'s "What the code actually looks like at open" named
the intended source: `synthesis/trust.py` already reads traversed edge
labels off the generated Cypher through
`cypher_query._traversed_edge_type_by_column`, and pairs each citation with
a `node_or_edge_type`, inside `core/graph.py`'s
`_node_or_edge_type_by_citation_id`, computed during `write_node`. That
pairing is real and computed, but it is consumed by exactly one caller,
`synthesis.trust.risk_tier_for`, to choose `high` versus `low` risk. It was
never attached to any field on `CitationPayload`
(`contracts/events.py`), so it never reaches the wire event stream
`feedback/capture.py`'s `assemble_interaction(query, events)` reads
(finding F-4.6-04).

Two things were tried against that gap, in order, and both were retired:

1. A prose-matching fallback: searching a citation's `field` and
   `claim_text` for a literal, word-bounded match against
   `graph_schema_constants.EDGE_LABELS`. This was a closed-vocabulary
   membership check, never narrative parsing, but it could only ever fire
   when a model-written sentence happened to contain the exact snake_case
   edge label, which in practice was almost never. It found nothing real
   and is not being restored: emitting no predicate tag is honest, and
   emitting a heuristic one that almost never fires is not, since a
   feature that appears to work but silently returns nothing is worse than
   one that is visibly absent. `tracker/phase_4.6.md`'s F-4.6-04 finding is
   the record of this approach being tried and retired.
2. T-4.6-04's fix: adding `node_or_edge_type` as a third, additive,
   optional field on `CitationPayload`, populated in `core/graph.py` from
   the `row_types` dict `write_node` already computes, with no
   recomputation and no second `cypher_query` call. This closed the gap at
   its source. It also broke build phase 4.1's BLOCKING MCP premise gate in
   two arms (verified: `test_phase_4_1_premise.py` returned
   `2 failed, 47 passed`) and widened a payload guarded by
   `_ALLOWED_RESPONSE_KEYS`, a hand-maintained anti-leak allowlist, without
   the explicit product-owner approval both prior widenings of that payload
   (build phases 4.10 and 4.5) required (finding F-4.6-J-02). The judge
   round also found the feature carried zero real verification: premise
   gate arm P12, the only test that exercises it, needs the live graph and
   was never run. The product owner decided on 2026-08-21 to REVERT this
   fix rather than repair it in place, and that revert is what removed
   `node_or_edge_type` from `CitationPayload` and from `core/graph.py`.

The path back to a real `predicate:` tag is still `node_or_edge_type` (or
an equivalently-scoped field) landing additively on `CitationPayload`, with
`_ALLOWED_RESPONSE_KEYS` updated under the same explicit product-owner
approval build phases 4.10 and 4.5 obtained for their own widenings of this
payload. Until that lands and premise gate arm P12 (marked `xfail` pending
this work, see `tests/system_03_search_agent/core/
test_feedback_capture_premise.py`) passes for real against the live graph,
this module stays `concept:`-only. Do not reintroduce the prose-matching
heuristic to fill the gap in the meantime: it was tried, it does not work,
and this section exists so the next reader does not have to rediscover
that the hard way.

## What this module actually does

- `concept:<Label>`: from each citation's `source` (the CURIE prefix, e.g.
  `NCBIGene`, `MONDO`), reverse-mapped through
  `graph_schema_constants.LABEL_CURIE_PREFIXES`. A prefix such as `MedGen`
  is genuinely ambiguous between `Disease` and `PhenotypicFeature` in that
  table, and this module tags BOTH candidates rather than guessing a
  single one: naming every label a record could honestly be is not the
  same claim as naming which one it is, and the second claim is not
  available from a CURIE prefix alone.
- `predicate:<edge_type>`: not emitted. See the deferral section above.

A citation with no mappable prefix contributes no tag. A citation list
with nothing in it returns an empty list. Nothing here is ever a
placeholder tag standing in for "traversed something": that is exactly the
shape build phase 4.4's manifest took when it certified traversing all
fourteen edge labels while returning none of them, and this module does
not repeat it.
"""

from __future__ import annotations

from typing import Any

from system_03_search_agent.tools.graph_schema_constants import (
    LABEL_CURIE_PREFIXES,
)

# Inverted once at import time: CURIE prefix -> every vertex label that
# prefix can name (per `graph_schema_constants.LABEL_CURIE_PREFIXES`, Section
# D's "Typical CURIE prefix" column). More than one label per prefix is a
# real property of the graph's own schema (`MedGen` names both `Disease` and
# `PhenotypicFeature`), not a defect in this inversion.
_PREFIX_TO_LABELS: dict[str, tuple[str, ...]] = {}
for _label, _prefixes in LABEL_CURIE_PREFIXES.items():
    for _prefix in _prefixes:
        _PREFIX_TO_LABELS[_prefix] = _PREFIX_TO_LABELS.get(_prefix, ()) + (_label,)


def coverage_tags_for(citations: list[dict[str, Any]]) -> list[str]:
    """`concept:<Label>` for what actually fired. `predicate:` is deferred.

    `citations` is the list of citation event payloads a finished run
    produced (`feedback/capture.py` passes `event.payload` for every
    `citation`-type event, dumped as-is per Section 9.1's shape). Derived
    from what FIRED: a citation that was never emitted contributes nothing,
    and a query that traversed nothing (a Guardrail refusal, a lookup that
    returned zero rows) returns an empty list rather than a placeholder tag.

    `predicate:<edge_type>` tags are not emitted by this function. See the
    module docstring's deferral section: the traversed edge label never
    reaches `CitationPayload` on this branch, and the module deliberately
    does not fall back to the retired prose-matching heuristic.

    Deterministic and free of model calls, the same zero-cost property
    `rubric_outcome_for` has: this is a dictionary lookup per citation,
    nothing else.
    """
    tags: set[str] = set()
    for citation in citations:
        source = str(citation.get("source", ""))
        for label in _PREFIX_TO_LABELS.get(source, ()):
            tags.add(f"concept:{label}")

    return sorted(tags)
