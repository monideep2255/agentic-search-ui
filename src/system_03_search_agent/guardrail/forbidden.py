"""Section 10.5: forbidden query types and read-only enforcement.

Step 4 of the Section 10.1 pipeline, running after Guard-tier classification
clears. Two families of forbidden intent:

    1. Verdict-seeking. A diagnosis, a treatment recommendation, a
       pathogenicity classification, or a variant prioritization. This system
       assembles evidence; it does not render verdicts.
    2. Write-seeking. Any attempt to create, mutate, or delete graph data,
       including hypothetical and indirect phrasings.

## This is one of three read-only layers, not the guarantee

Section 10.5 is explicit that read-only is defended at three independent
points, and this module is only the first:

    Guardrail (here)   Rejects a write-seeking request before it reaches
                       Think, Plan, or Act at all.
    Tool level         `cypher_query`'s validator rejects any write-shaped
                       clause (CREATE, MERGE, SET, DELETE, REMOVE) before
                       execution. See `tools.graph_schema_constants`'
                       FORBIDDEN_CYPHER_CLAUSES.
    Connection level   The connection uses the `kg_reader` role, which holds
                       no write grant in Postgres or AGE, so even a validator
                       bug cannot produce a write.

No single layer carries the whole guarantee, and this one is the weakest of
the three by design: it reasons about English, which is ambiguous, while the
other two reason about SQL grants and Cypher clauses, which are not. A gap
here is a defense-in-depth gap, never an open path to a write.

That ordering matters for how aggressive this module should be. Because the
credential itself cannot write, the cost of missing a write-seeking phrasing
is bounded, while the cost of over-matching is refusing a real question. So
this module requires TWO signals before refusing, not one.

## The two-factor rule, and the trap it exists to avoid

A write verb alone is not evidence of a write request. "Which pathogenic
variants in DMD are whole-exon deletions?" contains `deletion`, which is both
a Cypher write clause and the most common structural variant type in human
genetics. A one-factor rule refuses it, and that question is pinned as an
admit-arm case in the phase 3.0 premise gate.

So a refusal here needs a write VERB and a data-store OBJECT in the same
query: `add ... node`, `update ... record`, `delete ... from the graph`. A
variant deletion has no data-store object anywhere near it.

Depends on:
    - system_03_search_agent.guardrail.verdict
    - system_03_search_agent.guardrail.prefilter (normalize, so both modules
      agree on what the query text is)

Reads:
    - Nothing. No model call, no network.

Writes:
    - Nothing.
"""

from __future__ import annotations

import re
from typing import Final

from system_03_search_agent.guardrail.prefilter import normalize
from system_03_search_agent.guardrail.verdict import GuardVerdict, refused

__all__ = ["screen", "seeks_verdict", "seeks_write"]


# ---------------------------------------------------------------------------
# Write-seeking: the two-factor rule.
# ---------------------------------------------------------------------------

# Verbs that describe changing stored state. Written as verb forms rather than
# stems so that the noun `deletion` and the noun `duplication` do not match:
# `delete`/`deleting` is an instruction, `deletions` is a variant class.
_WRITE_VERBS: Final[tuple[str, ...]] = (
    "add", "adding", "insert", "inserting", "create", "creating",
    "update", "updating", "modify", "modifying", "change", "changing",
    "delete", "deleting", "remove", "removing", "drop", "dropping",
    "merge", "merging", "overwrite", "overwriting", "set", "setting",
    "write", "writing", "edit", "editing", "rename", "renaming",
    "populate", "populating", "load", "loading", "upsert", "patch",
)

# Objects that identify the target as the data store rather than biology.
# `node`, `edge`, and `record` are the load-bearing entries: no biological
# question refers to a "node" or a "record" as something to be altered.
_STORE_OBJECTS: Final[tuple[str, ...]] = (
    "node", "nodes", "edge", "edges", "relationship", "relationships",
    "record", "records", "row", "rows", "entry", "entries",
    "graph", "database", "table", "tables", "index", "schema",
    "knowledge graph", "triple", "triples", "property", "properties",
    "field", "fields", "status", "value",
)

_WRITE_VERB_PATTERN: Final = re.compile(
    r" (" + "|".join(_WRITE_VERBS) + r") "
)
_STORE_OBJECT_PATTERN: Final = re.compile(
    r" (" + "|".join(_STORE_OBJECTS) + r") "
)

_WRITE_REFUSAL_REASON: Final = (
    "I have read-only access to the knowledge graph and can't create, "
    "change, or delete anything in it. I can show you what it already "
    "contains, with citations."
)


def seeks_write(text: str) -> bool:
    """Whether the query asks to change stored data.

    Two factors required. See the module docstring for why one is not enough,
    and `tracker/phase_3.0.md`'s premise-gate notes for the specific question
    a one-factor rule refuses.
    """
    normalized = normalize(text)
    return bool(
        _WRITE_VERB_PATTERN.search(normalized)
        and _STORE_OBJECT_PATTERN.search(normalized)
    )


# ---------------------------------------------------------------------------
# Verdict-seeking.
# ---------------------------------------------------------------------------

# Section 10.5's forbidden intents, minus the ones `prefilter` already
# catches. This module is the backstop for phrasings that survive step 1,
# which is why the patterns here are shaped differently: they look for an
# explicit request for a judgement rather than for first-person framing.
_VERDICT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r" (tell|advise) me (whether|if) i "),
    re.compile(r" (what|which) (treatment|therapy|drug|medication) should "),
    re.compile(r" (diagnose|diagnosis) (of|for) (me|my|this patient) "),
    re.compile(r" (is|are) (this|these|it|they) (patient|person) "),
    re.compile(r" (acmg|amp) (classification|criteria) (for|of) "),
    re.compile(r" (call|report) (this|it) as (pathogenic|benign|likely) "),
    re.compile(r" clinical (decision|recommendation) for "),
    re.compile(r" what would you (do|recommend|advise) if (i|my) "),
)

_VERDICT_REFUSAL_REASON: Final = (
    "I can show you the cited evidence on this, but I can't render a "
    "diagnosis or a classification."
)


def seeks_verdict(text: str) -> bool:
    """Whether the query asks for a classification rather than for evidence."""
    normalized = normalize(text)
    return any(pattern.search(normalized) for pattern in _VERDICT_PATTERNS)


# ---------------------------------------------------------------------------
# The screen.
# ---------------------------------------------------------------------------


def screen(text: str) -> GuardVerdict | None:
    """Section 10.5's checks. Returns a refusal, or `None` if nothing matched.

    Like `prefilter.screen`, this never returns an admitting verdict. Passing
    Section 10.5 is one condition of admission, not admission itself.

    ## A known contract gap, recorded rather than papered over

    Section 10.5 requires refusing a write-seeking request but names no
    `GuardPayload.category` for it, and the contract's six members
    (`contracts/events.py`) contain nothing write-shaped. `off_topic` is used
    below because it is the closest member the contract can actually express
    and because a write request genuinely is outside what this system does.

    It is not a good fit. The user-facing reason string carries the real
    explanation, so nothing misleading reaches a reader, but a caller
    switching on `category` alone cannot distinguish "ask me about biology
    instead" from "I cannot write to the graph". Resolving this needs either
    a new enum member (an additive, v1-legal contract change per
    `system-design-patterns` rule 10) or a spec amendment, and that decision
    belongs to the Step 6.2 reconciliation rather than to this module.
    Tracked as a finding in `tracker/phase_3.0.md`.
    """
    if seeks_write(text):
        return refused("off_topic", _WRITE_REFUSAL_REASON)
    if seeks_verdict(text):
        return refused("medical_advice", _VERDICT_REFUSAL_REASON)
    return None
