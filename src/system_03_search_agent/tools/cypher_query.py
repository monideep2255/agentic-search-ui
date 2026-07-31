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

F-04 closure: this module used to not enforce `cost_control`'s per-query
cost cap around its own (up to two) plan-tier `generate_cypher` calls,
relying solely on the Act step's one check before dispatching the tool
call as a whole (`core.graph.act_node`, T-2.1-08). Two of this pipeline's
three model calls per invocation were uncapped. `_generate_and_validate`
now runs `cost_control.check_per_query_cap` immediately before every
`generate_cypher` call it makes, the same pattern `harness/
coordinator_worker.py`'s `_reader_pass` already applies to its own
isolated call: a cap breach is never issued as a call, and degrades to
this pipeline's existing `status: "error"` shape rather than raising
`cost_control.QueryCapExceededError` out of the tool. This is additional
to, never a replacement for, the Act step's own single check before
dispatching `cypher_query` as a whole.

F-06, open and not fixed here: `generate_cypher` (`cypher_generation.py`)
has no `cache_prefix` parameter on its own signature, only its
`HarnessLike.call_tier` Protocol accepts one, so there is currently no
seam this module can call to pass `harness.cache.build_stable_prefix()`
through to the underlying `call_tier` invocation without editing
`cypher_generation.py` itself, a file this ticket's builder does not own
(see the module's file-scope note in `tracker/phase_2.1.md`). Threading
the stable prefix through both of this module's `generate_cypher` calls
needs a small, additive `cache_prefix: str | None = None` parameter added
to `generate_cypher` and forwarded to its `harness.call_tier` call; that
one-line addition belongs to `cypher_generation.py`'s owner, coordinated
with this module's own call sites once it lands.

Defect fix (findings F-2.1-A1, F-01, A2, phase 2.1 review): three bugs in
this pipeline's handling of what the graph actually returns.

- F-2.1-A1: nothing anywhere parsed AGE's `agtype` wire text, so every
  mapped row came back empty and uncited while still reporting
  `status: "ok"`. Fixed by routing every raw row through
  `cypher_provenance.to_output_rows`, which parses each column's agtype
  text (`system_03_search_agent.tools.agtype`) before shaping it.
- F-01: `as_clause` was never derived from the generated Cypher's `RETURN`
  clause, so a multi-column `RETURN` died live with `DatatypeMismatch`.
  Fixed by `_build_as_clause`, which counts the RETURN clause's top-level
  comma-separated items and builds a matching `(c0 agtype, c1 agtype, ...)`
  declaration, passed to `execute_cypher` on every call this module makes.
- A2: `total_available` was computed after the validator's own `LIMIT`
  injection had already capped what the graph could return, so a
  genuinely truncated result could never report more than the row limit
  and `truncated` was always False. Fixed by `_fetch_true_total`, which
  issues a second, count-only query, built from the same validated
  MATCH/WHERE prefix, only when the first query returned exactly
  `row_limit` rows (the only case truncation is even possible).

A row whose entity parses but resolves no `source_url` (an unmapped CURIE
prefix, or a stored URL on a foreign host) is omitted from `rows` rather
than emitted as an uncitable content row, per CLAUDE.md's citation rule
and the cite-or-refuse gate in `production-standards.md`. This omission
happens in `_run_pipeline`, not in `to_output_rows`, so the shaping layer
stays a faithful transform and the cite-or-refuse policy stays visible
here, at the one place this module already drops a malformed row.

Depends on:
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput,
      CypherQueryOutput, CypherQueryRow)
    - system_03_search_agent.tools.schema_slice (build_schema_slice)
    - system_03_search_agent.tools.cypher_generation (generate_cypher,
      CypherGenerationError, HarnessLike)
    - system_03_search_agent.tools.cypher_validator (validate_cypher,
      ValidationResult)
    - system_03_search_agent.tools.cypher_provenance (to_output_rows)
    - system_03_search_agent.tools.agtype (parse_agtype, used only to read
      back the scalar `total_count` value from the count-only query)
    - system_03_search_agent.tools.graph_connection (execute_cypher,
      GraphError and its subclasses)
    - system_03_search_agent.tools.graph_schema_constants
      (CYPHER_QUERY_TIMEOUT_SECONDS)
    - system_03_search_agent.harness.cost_control (check_per_query_cap,
      QueryCapExceededError; finding F-04's fix)

Reads:
    - Environment variable: GRAPH_SNAPSHOT_VERSION, optional. Falls back
      to the last verified snapshot name recorded in
      docs/data-engineering/Knowledge_graph_on_server_reference.md when
      unset.
    - Environment variable: PER_QUERY_COST_CAP_USD, read indirectly via
      `cost_control.check_per_query_cap`, never read directly here.

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

from system_03_search_agent.harness import cost_control
from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.cypher_generation import (
    CypherGenerationError,
    HarnessLike,
    generate_cypher,
)
from system_03_search_agent.tools.cypher_provenance import to_output_rows
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

# The RETURN keyword that starts the item list this module derives an
# as_clause from, and the clause keywords that can legally follow it
# (ORDER BY, SKIP, LIMIT), all case-insensitive and word-bounded so
# "returned" or a property named "skipped" never trip a false match.
_RETURN_KEYWORD_PATTERN = re.compile(r"\bRETURN\b", re.IGNORECASE)
_TRAILING_CLAUSE_PATTERN = re.compile(r"\b(ORDER\s+BY|SKIP|LIMIT)\b", re.IGNORECASE)

# Finding F-01's fix: derive as_clause from the RETURN clause's own item
# count instead of hardcoding a single column. This caps how many output
# columns one query can declare, matching the input schema's own
# target_entities/row shape bounds, so a pathological RETURN with an
# unbounded item count cannot grow the AS clause without limit.
_MAX_RETURN_COLUMNS = 30


def _return_items_segment(cypher: str) -> str:
    """Extract the comma-separated item list following the RETURN keyword.

    Stops at the first depth-0 ORDER BY, SKIP, or LIMIT keyword, or at the
    end of the string, whichever comes first. Depth tracks `()`, `[]`, and
    `{}`, and a quoted string is skipped over entirely, so a boundary
    keyword or a comma appearing inside a property map, a list literal, a
    function call's argument list, or a string literal is never mistaken
    for a top-level item separator or the start of a following clause.

    Returns an empty string when no RETURN keyword is found at all; the
    caller treats that defensively as "assume one column" rather than as
    an error, since this function's job is deriving an as_clause, not
    re-validating Cypher that `cypher_validator.validate_cypher` already
    accepted.
    """
    match = _RETURN_KEYWORD_PATTERN.search(cypher)
    if match is None:
        return ""
    rest = cypher[match.end() :]

    depth = 0
    quote_char: str | None = None
    end_index = len(rest)
    i = 0
    while i < len(rest):
        ch = rest[i]
        if quote_char is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote_char:
                quote_char = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote_char = ch
            i += 1
            continue
        if ch in "([{":
            depth += 1
            i += 1
            continue
        if ch in ")]}":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            boundary = _TRAILING_CLAUSE_PATTERN.match(rest, i)
            if boundary is not None:
                end_index = i
                break
        i += 1

    return rest[:end_index]


def _count_top_level_items(segment: str) -> int:
    """Count comma-separated items in `segment` at depth 0, outside quotes.

    An empty or whitespace-only segment counts as one item, the same
    defensive floor `_return_items_segment` applies when no RETURN keyword
    was found at all: this function never returns zero, since a RETURN
    clause with no items is not valid Cypher and this module's job is
    deriving a column count, not detecting that malformation.
    """
    if not segment.strip():
        return 1
    depth = 0
    quote_char: str | None = None
    count = 1
    i = 0
    while i < len(segment):
        ch = segment[i]
        if quote_char is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote_char:
                quote_char = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote_char = ch
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
        i += 1
    return count


def _build_as_clause(cypher: str) -> str:
    """Derive the AGE `as_clause` output column declaration from `cypher`.

    Counts the top-level comma-separated items in `cypher`'s RETURN
    clause and builds a matching `(c0 agtype, c1 agtype, ...)`
    declaration, one column per RETURN item. This is finding F-01's fix:
    the wrapper previously always passed `execute_cypher`'s single-column
    default, so any multi-column RETURN, which a multi-hop query
    naturally produces, failed live with AGE's `DatatypeMismatch`.

    This is code-generated from a column count only, an integer this
    function itself computes, never from caller-supplied text spliced
    into the declaration string. `graph_connection._AS_CLAUSE_PATTERN`
    stays satisfied because the only variable part of the output is a
    small integer used as a column-name suffix (`c0`, `c1`, ...), never
    arbitrary text.

    Args:
        cypher: the normalized (LIMIT-injected) Cypher body this module is
            about to execute.

    Returns:
        A string of the shape `(c0 agtype, c1 agtype, ...)`, with at
        least one column and never more than `_MAX_RETURN_COLUMNS`.
    """
    segment = _return_items_segment(cypher)
    column_count = _count_top_level_items(segment)
    column_count = max(1, min(column_count, _MAX_RETURN_COLUMNS))
    columns = ", ".join(f"c{i} agtype" for i in range(column_count))
    return f"({columns})"


def _build_count_cypher(cypher: str) -> str | None:
    """Build a count-only variant of `cypher`'s match pattern.

    Takes everything before the RETURN keyword, the MATCH and WHERE
    clauses, already validated and already binding every caller-supplied
    value through a named parameter rather than a literal, and appends
    its own `RETURN count(*) AS total_count`, discarding the original
    RETURN items, ORDER BY, SKIP, and LIMIT entirely. The result returns
    exactly one row: the true number of matches for the same pattern,
    uncapped by the row_limit that shaped the first query.

    Only the code-controlled suffix (`RETURN count(*) AS total_count`) is
    ever appended here; the prefix this function reuses is exactly the
    substring of an already-validated query, never caller text assembled
    fresh, so this stays inside the same query-safety guarantees the
    original query already satisfied.

    Returns:
        The count-only Cypher body, or None when no RETURN keyword is
        found (defensive: should not happen for cypher that already
        passed `validate_cypher`, which requires the query be well-formed
        enough to execute, and is handled as "cannot compute a true
        total" rather than assumed impossible).
    """
    match = _RETURN_KEYWORD_PATTERN.search(cypher)
    if match is None:
        return None
    prefix = cypher[: match.start()].rstrip()
    if not prefix:
        return None
    return prefix + " RETURN count(*) AS total_count"


_COUNT_AS_CLAUSE = "(total_count agtype)"


def _fetch_true_total(
    cypher: str, params: dict[str, Any], timeout_s: float
) -> int | None:
    """Fetch the true total match count for `cypher`'s pattern, uncapped.

    Finding A2's fix: called only when the first query returned exactly
    `row_limit` rows, the one case where more rows might exist beyond
    what was fetched. Issues a second `execute_cypher` call against a
    count-only rewrite of the same validated MATCH/WHERE pattern
    (`_build_count_cypher`), with the same bound params, so the count
    reflects the same filter the first query used.

    Never raises. A `GraphError` on the count query (a timeout, a lost
    connection) or an unparseable or missing count value all return None,
    the "cannot determine a true total" signal the caller must respect:
    reporting the row limit itself as if it were the total is exactly the
    finding this function exists to prevent, so a failure here must never
    fall back to a fabricated number.
    """
    count_cypher = _build_count_cypher(cypher)
    if count_cypher is None:
        return None
    try:
        count_rows, _ = execute_cypher(
            count_cypher,
            params=params,
            row_limit=1,
            timeout_s=timeout_s,
            as_clause=_COUNT_AS_CLAUSE,
        )
    except GraphError:
        return None
    if not count_rows:
        return None
    raw_value = next(iter(count_rows[0].values()), None)
    parsed = parse_agtype(raw_value)
    if isinstance(parsed, bool):
        # bool is an int subclass in Python; count(*) never legitimately
        # returns a boolean, so this guards against silently accepting one.
        return None
    if isinstance(parsed, int):
        return parsed
    return None


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


_PARAM_NAME_SAFE = re.compile(r"[^A-Za-z0-9]+")


def entity_param_bindings(target_entities: list[str]) -> dict[str, str]:
    """Assign each target entity a deterministic Cypher parameter name.

    This is one half of the naming contract that closes F-2.1-B01. The
    caller decides the names, tells the generation step exactly which name
    holds which entity, and binds by that name on the way back. Nothing
    anywhere guesses from position.

    A CURIE is not a legal Cypher identifier (`NCBIGene:672` contains a
    colon), so the name is derived by replacing every non-alphanumeric run
    with an underscore and prefixing `e_`: `NCBIGene:672` becomes
    `e_NCBIGene_672`. Readable in a generated query and in a log, which
    matters when someone is reading the `cypher_executed` audit field to
    work out which entity a row came from.

    Two distinct CURIEs could in principle sanitize to the same name if
    they differ only in punctuation, so a collision gets a numeric suffix
    rather than silently overwriting, which would reintroduce exactly the
    wrong-value binding this contract exists to prevent.
    """
    bindings: dict[str, str] = {}
    for entity in target_entities:
        base = "e_" + _PARAM_NAME_SAFE.sub("_", entity).strip("_")
        name = base
        suffix = 2
        while name in bindings and bindings[name] != entity:
            name = f"{base}_{suffix}"
            suffix += 1
        bindings[name] = entity
    return bindings


def _build_params(cypher: str, entity_bindings: dict[str, str]) -> dict[str, Any]:
    """Bind the generated Cypher's parameters BY NAME, never by position.

    Returns only the bindings the Cypher actually references, so a query
    using one of three supplied entities does not carry two unused values
    into the graph call.

    This replaces a positional `zip` of parameter names against
    `target_entities`, which produced F-2.1-B01: a query naming two genes
    bound the wrong one, returned real rows about it, and cited them
    correctly. Every gate was green while the answer was about an entity
    the user had not asked about. Position was never a contract, only a
    coincidence that held whenever exactly one entity was in play, which
    is the only case the tests covered.

    A parameter the model invented outside the supplied names is NOT bound
    here. `_unknown_param_names` is what rejects it, before execution.
    """
    referenced = _ordered_unique_param_names(cypher)
    return {name: entity_bindings[name] for name in referenced if name in entity_bindings}


def _unknown_param_names(cypher: str, entity_bindings: dict[str, str]) -> list[str]:
    """Parameter names the generated Cypher references but nothing binds.

    An unbound parameter used to reach AGE and fail there as an opaque
    `UndefinedParameter`, which the tool reported as a graph error and
    which read as though the graph were at fault. Catching it here makes
    the repair retry informed: the validator error names the invented
    parameter and lists the legal ones, so the second generation attempt
    can actually fix it.
    """
    return [name for name in _ordered_unique_param_names(cypher) if name not in entity_bindings]


# Finding F-04's own reason code: a cap breach detected here, before any
# generate_cypher call is even issued. Not one of cypher_validator.py's
# reason codes (this rejection never reaches the validator at all), so it
# is named distinctly rather than borrowing "malformed_cypher" for a
# condition that has nothing to do with the Cypher's shape.
_REASON_COST_CAP_EXCEEDED = "cost_cap_exceeded"

# F-2.1-B01: the generated Cypher referenced a $parameter the caller
# never bound. Distinct from the validator's own reason codes because
# the Cypher's shape is fine; it is the binding contract that was
# broken, and the repair retry needs to be told which names are legal.
_REASON_UNBOUND_PARAM = "unbound_param_name"


async def _generate_and_validate(
    harness: HarnessLike,
    tool_input: CypherQueryInput,
    schema_slice: str,
    prior_error: str | None,
    entity_bindings: dict[str, str],
) -> tuple[str | None, ValidationResult]:
    """Run one generate-then-validate attempt.

    Finding F-04's fix: `core.graph.act_node` checks
    `cost_control.check_per_query_cap` exactly once before dispatching
    `cypher_query` as a whole, but this pipeline can itself issue up to
    two plan-tier `generate_cypher` calls (this attempt, plus one repair
    retry), and neither was cap-checked on its own. `harness/
    coordinator_worker.py`'s `_reader_pass` is the pattern this mirrors:
    check the cap immediately before the call, and if dispatching would
    breach it, never issue the call at all. This check runs before every
    call this function makes (both the first attempt and the retry), so
    a cap that is already breached before the retry blocks that call too,
    rather than only ever being checked once at the top of the pipeline.

    A cap breach here is folded into the same `ValidationResult` failure
    shape a validator rejection or an unrecoverable generation response
    already use, so `_run_pipeline` has exactly one failure shape to
    branch on. It never raises `cost_control.QueryCapExceededError` out
    of this function; the caller's existing one-repair-retry-then-error
    handling applies unchanged, and a cap breach on the first attempt
    surfaces as a normal `status: "error"` result, never an exception
    escaping the tool (this is the same "an error message must say what
    to do next" retry-safety gate the module docstring's F-01/F-2.1-A1/A2
    fixes already follow).

    An unrecoverable generation response (`CypherGenerationError`) is
    folded into the same `ValidationResult` shape as a validator
    rejection, so the caller has exactly one failure shape to branch on
    regardless of which step actually failed.
    """
    trace_id = getattr(harness, "trace_id", "") or ""
    try:
        cost_control.check_per_query_cap(harness, trace_id, "plan")
    except cost_control.QueryCapExceededError as exc:
        return None, ValidationResult(
            ok=False,
            reason=_REASON_COST_CAP_EXCEEDED,
            message=str(exc),
            normalized_cypher=None,
        )

    try:
        raw_cypher = await generate_cypher(
            harness, tool_input, schema_slice, prior_error, entity_bindings
        )
    except CypherGenerationError as exc:
        return None, ValidationResult(
            ok=False,
            reason="malformed_cypher",
            message=str(exc),
            normalized_cypher=None,
        )

    result = validate_cypher(raw_cypher, tool_input.row_limit)
    if not result.ok:
        return raw_cypher, result

    # F-2.1-B01's second half. The validator checks the Cypher's shape; it
    # has no view of which parameter names the caller actually bound, so a
    # name the model invented passes it and used to reach AGE as an opaque
    # UndefinedParameter. Reject it here instead, naming both the invented
    # parameter and the legal ones, so the one repair retry is an informed
    # fix rather than a blind resample.
    unknown = _unknown_param_names(result.normalized_cypher or raw_cypher, entity_bindings)
    if unknown:
        legal = ", ".join("$" + name for name in entity_bindings) or "(none)"
        return raw_cypher, ValidationResult(
            ok=False,
            reason=_REASON_UNBOUND_PARAM,
            message=(
                "generated Cypher references unbound parameter(s) "
                + ", ".join("$" + name for name in unknown)
                + "; the only bound parameter names are: "
                + legal
                + ". Rewrite the query using only those names."
            ),
            normalized_cypher=None,
        )
    return raw_cypher, result


def _cap_shaped_row(shaped: dict[str, Any]) -> dict[str, Any]:
    """Defensively cap one `to_output_rows` result to the Section 6.1 output
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

    # F-2.1-B01: assign each entity its parameter name ONCE, up front, and
    # use the same mapping for both the generation prompt and the bind on
    # the way back. One source of truth is the whole point: the defect was
    # two halves each deciding independently, generation naming freely and
    # binding zipping positionally.
    entity_bindings = entity_param_bindings(tool_input.target_entities)

    raw_cypher, validation = await _generate_and_validate(
        harness, tool_input, schema_slice, None, entity_bindings
    )
    if not validation.ok:
        # Exactly one repair retry, informed by the first attempt's error.
        raw_cypher, validation = await _generate_and_validate(
            harness, tool_input, schema_slice, validation.message, entity_bindings
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

    params = _build_params(normalized_cypher, entity_bindings)
    elapsed = time.monotonic() - start
    remaining_budget = max(1.0, CYPHER_QUERY_TIMEOUT_SECONDS - elapsed)

    # Finding F-01's fix: derive the AGE output column declaration from the
    # RETURN clause's own item count, instead of always passing
    # execute_cypher's single-column default. A multi-hop query naturally
    # binds several variables (RETURN v, g), and the hardcoded default
    # failed that shape live with DatatypeMismatch.
    as_clause = _build_as_clause(normalized_cypher)

    try:
        rows, returned_total = execute_cypher(
            normalized_cypher,
            params=params,
            row_limit=tool_input.row_limit,
            timeout_s=remaining_budget,
            as_clause=as_clause,
        )
    except GraphError as exc:
        return _error_output(normalized_cypher, str(exc))

    if not rows:
        return CypherQueryOutput(
            status="empty",
            rows=[],
            row_count=0,
            total_available=returned_total,
            truncated=False,
            cypher_executed=normalized_cypher[:_MAX_CYPHER_EXECUTED_CHARS],
            error=None,
        )

    # Finding A2's fix: the LIMIT clause is already baked into
    # normalized_cypher, so execute_cypher can never return more rows than
    # tool_input.row_limit in the first place, and comparing against that
    # same-bounded count could never detect a truncation. Only when the
    # first query returned exactly the limit is more data even possible;
    # in that case only, issue the count-only query for the true total.
    # Reporting the row limit itself as if it were the total is exactly
    # the wrong answer this fix exists to prevent, so a count-query
    # failure reports total_available as unknown (None), never a number.
    if len(rows) >= tool_input.row_limit:
        true_total = _fetch_true_total(normalized_cypher, params, remaining_budget)
        if true_total is None:
            total_available = None
            truncated = True
        else:
            total_available = true_total
            truncated = true_total > len(rows)
    else:
        total_available = len(rows)
        truncated = False

    snapshot_version = _graph_snapshot_version()
    mapped_rows: list[CypherQueryRow] = []
    for raw_row in rows:
        for shaped_row in to_output_rows(raw_row, snapshot_version):
            if not shaped_row.get("source_url"):
                # Finding F-2.1-A1's cite-or-refuse corollary: an entity
                # that parsed but resolves no source_url (an unmapped
                # CURIE prefix, or a stored URL discarded as a foreign
                # host) has no citation. CLAUDE.md: every fact must link
                # back to its source, so this row is omitted, reflected
                # only in a smaller row_count, never emitted as an
                # uncitable content row.
                continue
            shaped = _cap_shaped_row(shaped_row)
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
