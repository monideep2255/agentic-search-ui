"""Section 7.2: conflict detection between a graph value and a live value.

"Comparison is code-done... never a free-text diff." This module is that
comparison: a normalized equality check between two values already resolved
for the same field on the same entity, one from Layer 1 and one from a live
Layer 2/3 call. A detected conflict routes to the `flag` trust outcome
(Section 8.3.3's decision table), never a silent pick of one side, which is
why `ConflictResult` always carries both source URLs regardless of outcome.

This is deliberately the narrowest possible comparison: it takes two already-
extracted values, not two raw tool results, and it does not decide WHICH
fields to compare or WHEN two calls share an identifier. That decision
belongs to whichever call site in `write_node` (T-3.4-07's own integration
half) determines that a `cypher_query` result and a Layer 2/3 result share
an identifier in the first place; this module only answers "given these two
values for the same field, do they conflict."

Depends on:
    - Nothing beyond the standard library.

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

from dataclasses import dataclass


def _normalize(value: object) -> str:
    """A conservative normalization: case-fold and collapse whitespace.

    Deliberately not a fuzzy or semantic comparison. Section 7.2 requires
    the comparison be code-done and exact after normalization, the same
    "no embedding similarity, no partial-credit scoring" discipline Section
    8.2's grounding rule already applies to claim matching. Two values that
    differ only in case or incidental whitespace are the same fact reported
    two ways, not a conflict; anything else is compared literally.
    """
    return " ".join(str(value).split()).casefold()


@dataclass(frozen=True)
class ConflictResult:
    is_conflict: bool
    field: str
    graph_value: object
    live_value: object
    graph_source_url: str | None
    live_source_url: str | None


def detect_conflict(
    *,
    field: str,
    graph_value: object,
    live_value: object,
    graph_source_url: str | None,
    live_source_url: str | None,
) -> ConflictResult:
    """Whether `graph_value` and `live_value` disagree on `field`.

    Both source URLs are always carried in the result, on both outcomes,
    so a caller routing a conflict to the `flag` trust outcome (or logging
    an agreement) never has to re-derive which citation backed which value.
    """
    return ConflictResult(
        is_conflict=_normalize(graph_value) != _normalize(live_value),
        field=field,
        graph_value=graph_value,
        live_value=live_value,
        graph_source_url=graph_source_url,
        live_source_url=live_source_url,
    )
