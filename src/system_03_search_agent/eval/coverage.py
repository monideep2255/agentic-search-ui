"""The coverage metric: a diagnostic, never a gate (T-5.1-07).

Depends on:
    - system_03_search_agent.tools.graph_schema_constants (VERTEX_LABELS,
      EDGE_LABELS)
    - system_03_search_agent.eval.trace_source (RunRecord)

Reads / Writes:
    - Nothing.

## Why this imports the schema instead of listing it

The denominator is the deployed graph's enumerable schema, and this project
already has exactly one place that states it:
`tools/graph_schema_constants.py`. A second hand-maintained copy here would
be the defect F-3.0-01 filed, where a category set existed in two places and
the frontend copy silently rejected a value the backend had just added. A
metric whose denominator can drift from the graph reports a coverage figure
about a schema that no longer exists.

## Why it never gates

`requirements/Evaluation_playbook.md`: "It is a diagnostic, never a gate.
The moat set is engineered to be narrow and cross-database-biased, so by
construction it scores low on breadth. Gating a deliberately narrow set on
breadth would contradict its design and pressure set-padding."

That last clause is the operative one. A breadth gate does not make the eval
broader, it makes someone add questions until the number goes up, and those
questions are by construction the ones nobody thought were worth asking.

## Why two ratios and never one

Concept coverage and predicate coverage are different kinds of thing, and a
blended number hides which of the two is low. The first pass on the seven
must-pass questions is roughly 50 percent concepts against roughly 21
percent predicates; averaged into one figure that reads as "about a third
covered" and loses the actionable half, which is that ten predicates are
untouched.

`NamedThing` is excluded from the concept denominator. It is the
dangling-endpoint stub label the five-database merge produces, so it is a
real label the graph contains (which is why it stays in the stable prefix,
finding F-2.1-01) and not a concept any question can meaningfully exercise.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from system_03_search_agent.eval.trace_source import RunRecord
from system_03_search_agent.tools.graph_schema_constants import (
    EDGE_LABELS,
    VERTEX_LABELS,
)

_MERGE_STUB_LABEL = "NamedThing"

CONCEPT_DENOMINATOR: tuple[str, ...] = tuple(
    label for label in VERTEX_LABELS if label != _MERGE_STUB_LABEL
)
PREDICATE_DENOMINATOR: tuple[str, ...] = tuple(EDGE_LABELS)

_LABEL_RE = re.compile(r":([A-Z][A-Za-z0-9_]*)")
_PREDICATE_RE = re.compile(r"\[\s*[A-Za-z0-9_]*\s*:\s*([a-z][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class CoverageReport:
    """Two ratios and the sets behind them.

    Deliberately carries NO combined figure. The premise gate asserts the
    absence of one, because a later convenience property averaging the two
    would quietly undo the reason there are two.
    """

    concepts_exercised: frozenset[str]
    predicates_exercised: frozenset[str]
    concept_denominator: tuple[str, ...] = CONCEPT_DENOMINATOR
    predicate_denominator: tuple[str, ...] = PREDICATE_DENOMINATOR
    is_diagnostic_only: bool = True
    unknown_tokens: frozenset[str] = field(default_factory=frozenset)
    # Whether ANY record carried Cypher at all. False means the ratios below
    # are 0.0 because nothing could be observed, not because the set covers
    # nothing, and those are different facts. `ToolResultPayload` carries no
    # Cypher field today, so this is False on every trace-derived run.
    # Reporting "0 percent coverage" for a quantity nothing can measure is a
    # measurement that was never taken (F-5.1-J-13).
    is_measurable: bool = False

    @property
    def concept_coverage(self) -> float:
        if not self.concept_denominator:
            return 0.0
        return len(self.concepts_exercised) / len(self.concept_denominator)

    @property
    def predicate_coverage(self) -> float:
        if not self.predicate_denominator:
            return 0.0
        return len(self.predicates_exercised) / len(self.predicate_denominator)

    @property
    def untouched_predicates(self) -> tuple[str, ...]:
        """The actionable half: what set growth should aim at next."""
        return tuple(
            p for p in self.predicate_denominator if p not in self.predicates_exercised
        )

    @property
    def untouched_concepts(self) -> tuple[str, ...]:
        return tuple(
            c for c in self.concept_denominator if c not in self.concepts_exercised
        )


def coverage_report(*, records: Sequence[RunRecord]) -> CoverageReport:
    """Concept and predicate coverage from the Cypher the agent ACTUALLY emitted.

    The playbook's first pass was hand-mapped and said so: "Hand-mapped now,
    replaced by dynamic instrumentation once the agent runs and its Cypher is
    observable." The agent runs now, and build phase 5.0's tracing makes the
    emitted Cypher observable, so this reads the real thing.

    A hand-mapped figure and an observed figure can differ, and where they do
    the observed one is right about what happened while the hand-mapped one
    is right about what was intended. Neither is corrected to match the
    other here.
    """
    concepts: set[str] = set()
    predicates: set[str] = set()
    unknown: set[str] = set()

    known_concepts = set(CONCEPT_DENOMINATOR)
    known_predicates = set(PREDICATE_DENOMINATOR)

    for record in records:
        for statement in record.cypher_emitted:
            for label in _LABEL_RE.findall(statement):
                if label in known_concepts:
                    concepts.add(label)
                elif label != _MERGE_STUB_LABEL:
                    unknown.add(label)
            for predicate in _PREDICATE_RE.findall(statement):
                if predicate in known_predicates:
                    predicates.add(predicate)
                else:
                    unknown.add(predicate)

    return CoverageReport(
        concepts_exercised=frozenset(concepts),
        predicates_exercised=frozenset(predicates),
        unknown_tokens=frozenset(unknown),
        is_measurable=any(record.cypher_emitted for record in records),
    )
