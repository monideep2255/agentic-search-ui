"""Deterministic validator for generated Cypher, T-2.1-04.

This module never calls a model and never scores anything by similarity.
Given the same Cypher string and the same row_limit, `validate_cypher`
always returns the same `ValidationResult`. That determinism is a hard
requirement, not a style preference: `.claude/rules/production-standards.md`
requires a citation or query-safety gate to accept or reject by deterministic
rule, never a fuzzy threshold, and this validator is the query-safety gate
for Layer 1.

The checks here are regex and string based, not a full Cypher parser. That
is a deliberate scope choice: the Cypher this validator sees is always the
output of the internal generation step (T-2.1-03), a narrow, predictable
shape, not arbitrary user-authored Cypher. The checks are conservative in
the safe direction: a construct this module cannot confidently classify as
safe is rejected, never silently passed through.

Known limitation, documented rather than silently accepted: keyword
detection for forbidden clauses and the literal-interpolation check do not
parse string literals, so a property value that happens to contain a
forbidden keyword or a quote character inside quotes is not specially
excluded. Given this system's contract that caller-supplied values travel
as parameters, not literals, this is an acceptable conservative bias, not a
correctness gap this ticket needs to close.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants (VERTEX_LABELS,
      EDGE_LABELS, FORBIDDEN_CYPHER_CLAUSES, DEFAULT_ROW_LIMIT, MAX_ROW_LIMIT)

Reads:
    - Nothing at import time. Pure function over its string argument.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_query (T-2.1-07, the integration
      ticket, not written by this builder)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from system_03_search_agent.tools.graph_schema_constants import (
    DEFAULT_ROW_LIMIT,
    EDGE_LABELS,
    FORBIDDEN_CYPHER_CLAUSES,
    MAX_ROW_LIMIT,
    VERTEX_LABELS,
)

# Reason codes, exact strings per the phase 2.1 contract. Never renamed
# without a corresponding tracker and contract-version update.
REASON_MISSING_EDGE_LABEL = "missing_edge_label"
REASON_UNKNOWN_EDGE_LABEL = "unknown_edge_label"
REASON_UNKNOWN_VERTEX_LABEL = "unknown_vertex_label"
REASON_WRITE_CLAUSE_FORBIDDEN = "write_clause_forbidden"
REASON_MALFORMED_CYPHER = "malformed_cypher"
REASON_LITERAL_INTERPOLATION_SUSPECTED = "literal_interpolation_suspected"

# A relationship "hop": optional leading <, a dash, an optional bracket
# group (the typed or untyped part), a dash, an optional trailing >.
# Group 1 is the bracket interior when brackets are present at all; when a
# hop has no brackets whatsoever (bare --, -->, <--) group 1 is None, which
# is itself the untyped signal.
_RELATIONSHIP_HOP_PATTERN = re.compile(r"<?-(?:\[([^\[\]]*)\])?-\>?")

# A top-level node pattern's parenthesized interior. Cypher property maps
# use braces, never parens, so this does not need to worry about nested
# parens inside a property map.
_NODE_PATTERN = re.compile(r"\(([^()]*)\)")

# A variable-length relationship spec, e.g. *1..3, *2, *. Stripped before
# splitting a bracket interior into labels so it is never mistaken for one.
_VAR_LENGTH_SPEC_PATTERN = re.compile(r"\*\d*(?:\.\.\d*)?")

# An existing LIMIT clause, any casing, any amount of surrounding whitespace.
_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)

# A colon or equals sign directly followed by a quote character marks a
# literal value bound in place of a parameter, e.g. `symbol: 'BRCA1'` or
# `n.name = "BRCA1"`. Per production-standards, every caller-supplied value
# must travel through a parameter, never a literal interpolated into the
# Cypher text, so any such literal is suspicious on sight.
_LITERAL_VALUE_PATTERN = re.compile(r"[:=]\s*['\"]")

# One compiled, case-insensitive, word-bounded pattern per forbidden clause.
# The word boundary is what keeps `dataset_id` from tripping the `SET`
# check: `\b` only fires at a transition between a word character and a
# non-word character, and `_` counts as a word character, so `set` embedded
# inside `dataset_id` has no boundary on either side.
_FORBIDDEN_CLAUSE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (clause, re.compile(r"\b" + re.escape(clause) + r"\b", re.IGNORECASE))
    for clause in FORBIDDEN_CYPHER_CLAUSES
)


@dataclass(frozen=True)
class ValidationResult:
    """The verdict `validate_cypher` returns.

    ok is the accept-or-reject bit. reason is a machine-readable code from
    the fixed set the phase 2.1 contract names, present only on rejection.
    message is a human-readable, actionable explanation, present on both
    acceptance (informational) and rejection. normalized_cypher is the
    Cypher body with its LIMIT clause injected or capped, present only when
    ok is True; a rejected query has no normalized form to execute.
    """

    ok: bool
    reason: str | None
    message: str | None
    normalized_cypher: str | None


def _is_malformed(cypher: str) -> bool:
    """Return True when the string cannot be a well-formed Cypher body.

    Checks balance of parens, brackets, and braces, and rejects an empty or
    whitespace-only string. This is not a parser; it only screens out
    strings a parser could never accept, so a downstream execution failure
    on a syntactically balanced but semantically wrong query is not this
    function's concern.
    """
    if not cypher or not cypher.strip():
        return True
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = {v: k for k, v in pairs.items()}
    stack: list[str] = []
    for char in cypher:
        if char in pairs:
            stack.append(char)
        elif char in closers:
            if not stack or stack[-1] != closers[char]:
                return True
            stack.pop()
    return bool(stack)


def _find_forbidden_clause(cypher: str) -> str | None:
    """Return the first forbidden clause keyword found, or None."""
    for clause, pattern in _FORBIDDEN_CLAUSE_PATTERNS:
        if pattern.search(cypher):
            return clause
    return None


def _split_label_spec(label_spec: str) -> list[str]:
    """Split a `:Label1:Label2` or `:LabelA|LabelB` spec into label tokens."""
    cleaned = _VAR_LENGTH_SPEC_PATTERN.sub("", label_spec)
    return [token.strip() for token in re.split(r"[:|]", cleaned) if token.strip()]


def _extract_node_labels(content: str) -> list[str]:
    """Extract vertex labels from one node pattern's parenthesized content.

    Only the portion before any property map (the first `{`) is examined,
    and only when a colon appears in that portion. A bare variable such as
    `(n)`, or a property map with no label such as `(n {name: 'x'})`, has
    no colon in its pre-brace portion and yields no labels, which is
    correct: an unlabeled node pattern is legal Cypher and is not this
    validator's concern.
    """
    head = content.split("{", 1)[0]
    if ":" not in head:
        return []
    label_spec = head[head.index(":"):]
    return _split_label_spec(label_spec)


def _extract_edge_labels(bracket_content: str | None) -> list[str] | None:
    """Extract edge labels from one relationship hop's bracket interior.

    Returns None when the hop is untyped: no brackets at all, empty
    brackets, or a bracket interior carrying only a variable name and no
    colon-prefixed label. Returns a (possibly multi-entry, for `|`
    alternation) list of label tokens when a colon is present.
    """
    if bracket_content is None:
        return None
    head = bracket_content.split("{", 1)[0]
    if ":" not in head:
        return None
    label_spec = head[head.index(":"):]
    return _split_label_spec(label_spec)


def validate_cypher(cypher: str, row_limit: int = DEFAULT_ROW_LIMIT) -> ValidationResult:
    """Validate a generated Cypher body deterministically.

    Runs the checks in a fixed order: malformed shape first, since nothing
    downstream can be evaluated on an unparseable string; forbidden write
    clauses next, since that is the highest-severity rejection; then edge
    label typing, then vertex label typing, then the literal-interpolation
    heuristic. A query that clears every check is returned with its LIMIT
    normalized: injected if absent, capped at MAX_ROW_LIMIT if the
    generated query asked for more.

    Args:
        cypher: the generated Cypher body, with no markdown fence, no
            prose, and no `SELECT * FROM cypher(...)` wrapper.
        row_limit: the caller's requested row limit, already validated by
            the input schema (T-2.1-01) to be between 1 and MAX_ROW_LIMIT.

    Returns:
        A ValidationResult. ok is True only when the query is safe to hand
        to `graph_connection.execute_cypher` (T-2.1-06) as-is.
    """
    if _is_malformed(cypher):
        return ValidationResult(
            ok=False,
            reason=REASON_MALFORMED_CYPHER,
            message=(
                "Generated Cypher is empty or has unbalanced parentheses, "
                "brackets, or braces. Retry generation with a narrower "
                "query_intent."
            ),
            normalized_cypher=None,
        )

    forbidden = _find_forbidden_clause(cypher)
    if forbidden is not None:
        return ValidationResult(
            ok=False,
            reason=REASON_WRITE_CLAUSE_FORBIDDEN,
            message=(
                "Generated Cypher contains the write clause '"
                + forbidden
                + "'. Layer 1 access is read-only; retry generation with a "
                "read-only query_intent."
            ),
            normalized_cypher=None,
        )

    for match in _RELATIONSHIP_HOP_PATTERN.finditer(cypher):
        bracket_content = match.group(1)
        edge_labels = _extract_edge_labels(bracket_content)
        if edge_labels is None:
            return ValidationResult(
                ok=False,
                reason=REASON_MISSING_EDGE_LABEL,
                message=(
                    "Generated Cypher has an untyped relationship pattern. "
                    "Every relationship must carry an explicit edge label, "
                    "or AGE compiles it to a scan across all "
                    + str(len(EDGE_LABELS))
                    + " edge tables. Retry generation with an explicit "
                    "edge label."
                ),
                normalized_cypher=None,
            )
        for label in edge_labels:
            if label not in EDGE_LABELS:
                return ValidationResult(
                    ok=False,
                    reason=REASON_UNKNOWN_EDGE_LABEL,
                    message=(
                        "Generated Cypher references edge label '"
                        + label
                        + "', which is not one of the graph's known edge "
                        "labels. Retry generation constrained to the "
                        "sliced schema."
                    ),
                    normalized_cypher=None,
                )

    for match in _NODE_PATTERN.finditer(cypher):
        for label in _extract_node_labels(match.group(1)):
            if label not in VERTEX_LABELS:
                return ValidationResult(
                    ok=False,
                    reason=REASON_UNKNOWN_VERTEX_LABEL,
                    message=(
                        "Generated Cypher references vertex label '"
                        + label
                        + "', which is not one of the graph's known vertex "
                        "labels. Retry generation constrained to the "
                        "sliced schema."
                    ),
                    normalized_cypher=None,
                )

    if _LITERAL_VALUE_PATTERN.search(cypher):
        return ValidationResult(
            ok=False,
            reason=REASON_LITERAL_INTERPOLATION_SUSPECTED,
            message=(
                "Generated Cypher appears to bind a literal value directly "
                "instead of a parameter. Every caller-supplied value must "
                "travel through a parameter, never a string or number "
                "written into the Cypher text. Retry generation using "
                "parameter references."
            ),
            normalized_cypher=None,
        )

    normalized = _normalize_limit(cypher, row_limit)
    return ValidationResult(
        ok=True,
        reason=None,
        message="Validation passed.",
        normalized_cypher=normalized,
    )


def _normalize_limit(cypher: str, row_limit: int) -> str:
    """Inject a missing LIMIT, or cap an existing one at MAX_ROW_LIMIT."""
    existing = _LIMIT_PATTERN.search(cypher)
    if existing is None:
        stripped = cypher.rstrip()
        if stripped.endswith(";"):
            stripped = stripped[:-1].rstrip()
        return stripped + " LIMIT " + str(row_limit)

    requested = int(existing.group(1))
    if requested > MAX_ROW_LIMIT:
        start, end = existing.span(1)
        return cypher[:start] + str(MAX_ROW_LIMIT) + cypher[end:]
    return cypher
