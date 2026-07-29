"""cypher_query: the only path to Layer 1 (Technical_specification.md
Section 6.1), assembled from the six sibling modules this ticket
integrates: schema_slice, cypher_generation, cypher_validator,
cypher_provenance, graph_connection, and cypher_schemas.

The three-step pipeline, run in this order, never reordered:

    1. Slice the schema (`schema_slice.build_schema_slice`) to the labels
       and predicates plausibly relevant to this call's `query_class` and
       `target_entities`.
    2. Generate Cypher with a plan-tier call (`cypher_generation.
       generate_cypher`), constrained by that slice.
    3. Validate the generated Cypher (`cypher_validator.validate_cypher`),
       then execute it (`graph_connection.execute_cypher`), then map each
       raw row to the output shape (`cypher_provenance.to_output_row`).

Exactly one repair retry: a validation failure, or an unrecoverable
generation response (`cypher_generation.CypherGenerationError`), feeds the
validator's error text back into a second `generate_cypher` call as
`prior_error`. A second failure returns `status: "error"`; there is never
a third attempt.

The main agent never sees raw Cypher. The generated string appears only
in `CypherQueryOutput.cypher_executed`, an audit-trail field, and this
module never places it anywhere else: not in `error`, not in a row, not
in any structure a caller might render to an end user
(production-standards.md's cite-or-refuse gate and the ticket's own
constraint).

Known, documented scope limitation: `cypher_generation`'s prompt instructs
the model to reference every caller-supplied value as a named Cypher
parameter ($param_name) rather than a literal, but no ticket in this
phase defines a naming contract between a parameter's name and which
`target_entities` value it should bind to. `_build_params` resolves this
pragmatically: the first parameter name encountered in the generated
Cypher binds to the first `target_entities` value, the second to the
second, and so on (see its own docstring). A future phase that gives the
generation prompt an explicit positional or named binding contract can
replace that one function without touching the rest of this pipeline.

This module does not itself enforce `cost_control`'s per-query cost cap
around its own (up to two) plan-tier `generate_cypher` calls; that
enforcement lives at the Act step's dispatch of the tool call as a whole
(`core.graph.act_node`, T-2.1-08), which checks the cap once before
calling this function at all. A cap breach discovered only mid-retry,
inside this module's own second `generate_cypher` call, is not caught
here; this is a documented, narrow gap, not a silent one.

Depends on:
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput,
      CypherQueryOutput, CypherQueryRow)
    - system_03_search_agent.tools.schema_slice (build_schema_slice)
    - system_03_search_agent.tools.cypher_generation (generate_cypher,
      CypherGenerationError, HarnessLike)
    - system_03_search_agent.tools.cypher_validator (validate_cypher,
      ValidationResult)
    - system_03_search_agent.tools.cypher_provenance (to_output_row)
    - system_03_search_agent.tools.graph_connection (execute_cypher,
      GraphError and its subclasses)
    - system_03_search_agent.tools.graph_schema_constants
      (CYPHER_QUERY_TIMEOUT_SECONDS)

Reads:
    - Environment variable: GRAPH_SNAPSHOT_VERSION, optional. Falls back
      to the last verified snapshot name recorded in
      docs/data-engineering/Knowledge_graph_on_server_reference.md when
      unset.

Writes:
    - Nothing. Layer 1 access is read-only end to end.

Depended by:
    - system_03_search_agent.core.graph (act_node, T-2.1-08, the
      integration point that calls this function for a real query)
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

from pydantic import ValidationError

from system_03_search_agent.tools.cypher_generation import (
    CypherGenerationError,
    HarnessLike,
    generate_cypher,
)
from system_03_search_agent.tools.cypher_provenance import to_output_row
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.cypher_validator import ValidationResult, validate_cypher
from system_03_search_agent.tools.graph_connection import GraphError, execute_cypher
from system_03_search_agent.tools.graph_schema_constants import CYPHER_QUERY_TIMEOUT_SECONDS
from system_03_search_agent.tools.schema_slice import build_schema_slice

# Section 6.1's row_limit output cap; CypherQueryRow already enforces this
# via its own field_validator, this is a defensive pre-cap so a hostile
# raw row is shaped down before it ever reaches Pydantic construction,
# rather than relying solely on catching the resulting ValidationError.
_MAX_ROW_FIELDS = 30
_MAX_NODE_OR_EDGE_TYPE_CHARS = 50
_MAX_CURIE_CHARS = 100
_MAX_SNAPSHOT_VERSION_CHARS = 40
_MAX_CYPHER_EXECUTED_CHARS = 2000
_MAX_ERROR_CHARS = 500

# The env var read for the graph's current snapshot label. Falls back to
# the last verified snapshot recorded in docs/data-engineering/
# Knowledge_graph_on_server_reference.md so this field is never empty
# even before a snapshot-refresh runbook wires the env var into
# deployment configuration.
_ENV_GRAPH_SNAPSHOT_VERSION = "GRAPH_SNAPSHOT_VERSION"
_DEFAULT_GRAPH_SNAPSHOT_VERSION = "ncbi_kg_v1_2026-04-22"

# One Cypher named parameter, e.g. $gene_id. AGE dollar-quoting ($$) is
# excluded implicitly: a bare "$" not immediately followed by an
# identifier character never matches this pattern.
_PARAM_NAME_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _graph_snapshot_version() -> str:
    """Return the graph snapshot version to stamp onto every returned row."""
    return os.environ.get(_ENV_GRAPH_SNAPSHOT_VERSION, _DEFAULT_GRAPH_SNAPSHOT_VERSION)[
        :_MAX_SNAPSHOT_VERSION_CHARS
    ]


def _ordered_unique_param_names(cypher: str) -> list[str]:
    """Return every `$param_name` reference in `cypher`, in first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _PARAM_NAME_PATTERN.finditer(cypher):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _build_params(cypher: str, target_entities: list[str]) -> dict[str, Any]:
    """Bind the generated Cypher's named parameters to `target_entities`
    values, positionally. See the module docstring for why this is a
    documented, pragmatic resolution rather than a named binding contract.
    A parameter name with no corresponding `target_entities` value at its
    position is left unbound; `execute_cypher` then either receives fewer
    bound names than the Cypher references (AGE raises a bind-time error,
    classified as a `GraphError` and surfaced as `status: "error"`, never
    a crash) or, when there is nothing to bind at all, an empty params
    dict, which `execute_cypher` treats as "no params" and omits the
    third `cypher()` argument entirely.
    """
    names = _ordered_unique_param_names(cypher)
    return dict(zip(names, target_entities))


async def _generate_and_validate(
    harness: HarnessLike,
    tool_input: CypherQueryInput,
    schema_slice: str,
    prior_error: str | None,
) -> tuple[str | None, ValidationResult]:
    """Run one generate-then-validate attempt.

    An unrecoverable generation response (`CypherGenerationError`) is
    folded into the same `ValidationResult` shape as a validator
    rejection, so the caller has exactly one failure shape to branch on
    regardless of which step actually failed.
    """
    try:
        raw_cypher = await generate_cypher(harness, tool_input, schema_slice, prior_error)
    except CypherGenerationError as exc:
        return None, ValidationResult(
            ok=False,
            reason="malformed_cypher",
            message=str(exc),
            normalized_cypher=None,
        )
    return raw_cypher, validate_cypher(raw_cypher, tool_input.row_limit)


def _cap_shaped_row(shaped: dict[str, Any]) -> dict[str, Any]:
    """Defensively cap one `to_output_row` result to the Section 6.1 output
    row's field-length and field-count bounds before constructing a
    `CypherQueryRow`, so an oversized raw graph value is shaped down
    rather than rejected outright (production-standards.md's multi-agent
    pipeline gate: maxLength and maxItems/maxProperties are enforced
    before the payload reaches a typed boundary, not only by that
    boundary's own validators).
    """
    fields = shaped.get("fields") or {}
    if len(fields) > _MAX_ROW_FIELDS:
        fields = dict(list(fields.items())[:_MAX_ROW_FIELDS])
    return {
        "node_or_edge_type": str(shaped.get("node_or_edge_type", ""))[
            :_MAX_NODE_OR_EDGE_TYPE_CHARS
        ],
        "curie": str(shaped.get("curie", ""))[:_MAX_CURIE_CHARS],
        "fields": fields,
        "source_url": shaped.get("source_url"),
        "graph_snapshot_version": str(shaped.get("graph_snapshot_version", ""))[
            :_MAX_SNAPSHOT_VERSION_CHARS
        ],
    }


def _error_output(cypher_executed: str | None, error: str) -> CypherQueryOutput:
    capped_cypher = cypher_executed[:_MAX_CYPHER_EXECUTED_CHARS] if cypher_executed else None
    return CypherQueryOutput(
        status="error",
        rows=[],
        row_count=0,
        total_available=None,
        truncated=False,
        cypher_executed=capped_cypher,
        error=error[:_MAX_ERROR_CHARS],
    )


async def _run_pipeline(harness: HarnessLike, tool_input: CypherQueryInput) -> CypherQueryOutput:
    start = time.monotonic()
    schema_slice = build_schema_slice(tool_input.query_class.value, tool_input.target_entities)

    raw_cypher, validation = await _generate_and_validate(harness, tool_input, schema_slice, None)
    if not validation.ok:
        # Exactly one repair retry, informed by the first attempt's error.
        raw_cypher, validation = await _generate_and_validate(
            harness, tool_input, schema_slice, validation.message
        )
        if not validation.ok:
            return _error_output(
                raw_cypher,
                validation.message or "Cypher generation failed after one repair retry.",
            )

    normalized_cypher = validation.normalized_cypher
    if normalized_cypher is None:
        # Defensive: validate_cypher's own contract guarantees a
        # normalized_cypher whenever ok is True. This branch exists so a
        # violation of that contract fails loudly with an actionable
        # message instead of crashing on a None passed into
        # execute_cypher.
        return _error_output(
            raw_cypher,
            "internal error: Cypher validation reported success with no normalized query",
        )

    params = _build_params(normalized_cypher, tool_input.target_entities)
    elapsed = time.monotonic() - start
    remaining_budget = max(1.0, CYPHER_QUERY_TIMEOUT_SECONDS - elapsed)

    try:
        rows, total_available = execute_cypher(
            normalized_cypher,
            params=params,
            row_limit=tool_input.row_limit,
            timeout_s=remaining_budget,
        )
    except GraphError as exc:
        return _error_output(normalized_cypher, str(exc))

    if not rows:
        return CypherQueryOutput(
            status="empty",
            rows=[],
            row_count=0,
            total_available=total_available,
            truncated=False,
            cypher_executed=normalized_cypher[:_MAX_CYPHER_EXECUTED_CHARS],
            error=None,
        )

    truncated = total_available > len(rows)
    snapshot_version = _graph_snapshot_version()
    mapped_rows: list[CypherQueryRow] = []
    for raw_row in rows:
        shaped = _cap_shaped_row(to_output_row(raw_row, snapshot_version))
        try:
            mapped_rows.append(CypherQueryRow(**shaped))
        except ValidationError:
            # One malformed row must never fail the whole query
            # (production-standards.md's multi-agent pipeline gate); it is
            # dropped, not raised.
            continue

    return CypherQueryOutput(
        status="ok" if mapped_rows else "empty",
        rows=mapped_rows,
        row_count=len(mapped_rows),
        total_available=total_available,
        truncated=truncated,
        cypher_executed=normalized_cypher[:_MAX_CYPHER_EXECUTED_CHARS],
        error=None,
    )


async def cypher_query(harness: HarnessLike, tool_input: CypherQueryInput) -> CypherQueryOutput:
    """Run Section 6.1's three-step Layer 1 pipeline and return a
    `CypherQueryOutput`.

    Bounded at `CYPHER_QUERY_TIMEOUT_SECONDS` (30 seconds) total, however
    the internal steps (schema slicing, up to two generation calls,
    validation, execution, and row mapping) divide that budget. A timeout
    at this outer level, or a `GraphTimeoutError` raised by
    `execute_cypher` itself, both surface as `status: "error"` with the
    Section 6.1 actionable message; neither ever raises out of this
    function.

    Never raises. Every failure path (a `CypherGenerationError`, a
    validation rejection after the one repair retry, a `GraphError` from
    execution, or this function's own outer timeout) is folded into a
    `status: "error"` `CypherQueryOutput`, never an unhandled exception,
    per the retry-safety gate's "an error message must say what to do
    next" requirement.
    """
    try:
        return await asyncio.wait_for(
            _run_pipeline(harness, tool_input), timeout=CYPHER_QUERY_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return _error_output(
            None,
            f"graph query exceeded {CYPHER_QUERY_TIMEOUT_SECONDS:g}s, retry with a "
            "narrower query_intent or a smaller query_class",
        )
