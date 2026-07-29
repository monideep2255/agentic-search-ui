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
detection for forbidden clauses does not parse string literals, so a
property value that happens to contain a forbidden keyword is not
specially excluded. Given this system's contract that caller-supplied
values travel as parameters, not literals, this is an acceptable
conservative bias, not a correctness gap this ticket needs to close.

Known limitation on the literal-interpolation check (F-2.1-A17), narrowed
rather than removed: a literal bound directly in the query text is
allowed only when the field it is bound to is one of a small, explicit
allowlist of BioLink discriminator fields this graph's own schema defines
(`source`, `category`, `predicate`), never an open-ended, caller-facing
identifying field such as `id`, `symbol`, `name`, or `term`. This is a
field-name heuristic, not a proof of provenance: nothing in the string
tells the validator whether a given literal was written by the generator
itself or smuggled in from caller input. The allowlist is deliberately
short and reviewed by hand, not grown ad hoc, because every field added
to it is a field this validator can no longer catch a literal-bound
caller value through.

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
# New for F-08 / bypass 4: row_limit itself is not a caller-trusted int
# until this validator says so, even though the input schema (T-2.1-01)
# already bounds it. A validator that trusts an un-type-checked argument
# is not a safety gate.
REASON_INVALID_ROW_LIMIT = "invalid_row_limit"

# A relationship "hop": optional leading <, a dash, an optional bracket
# group (the typed or untyped part), a dash, an optional trailing >.
# Group 1 is the bracket interior when brackets are present at all; when a
# hop has no brackets whatsoever (bare --, -->, <--) group 1 is None, which
# is itself the untyped signal. Cypher permits whitespace around every one
# of these tokens (`- [x] ->` is identical to `-[x]->` to the parser), so
# every join point here tolerates `\s*`: after the optional `<`, on both
# sides of each dash, and before the optional trailing `>`. Without this,
# a single inserted space defeats the untyped-edge gate entirely (F-2.1-A4):
# AGE still compiles the spaced form to the same all-edge-table scan, but
# the old tight-spacing-only pattern never matched it, so it was never
# classified as a relationship hop at all.
_RELATIONSHIP_HOP_PATTERN = re.compile(r"<?\s*-\s*(?:\[([^\[\]]*)\]\s*)?-\s*>?")

# A variable-length relationship spec, e.g. *1..3, *2, *. Stripped before
# splitting a bracket interior into labels so it is never mistaken for one.
_VAR_LENGTH_SPEC_PATTERN = re.compile(r"\*\d*(?:\.\.\d*)?")

# A genuine, top-level trailing LIMIT: the keyword and its digits anchored
# to the very end of a (rstripped) query or UNION branch. Deliberately not
# a bare "LIMIT anywhere" search (see _split_on_union and _normalize_limit):
# a mid-query `WITH g LIMIT 1` is a legitimate scoping clause, not the
# caller-facing cap this validator injects, and must never be mistaken
# for one (F-2.1-A8).
_TRAILING_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.IGNORECASE)

# A top-level UNION or UNION ALL keyword. Cypher scopes a trailing LIMIT
# to the query part immediately before it, never to the whole UNION result
# set, so every branch must be normalized independently (F-2.1-A8).
_UNION_PATTERN = re.compile(r"\bUNION\s+ALL\b|\bUNION\b", re.IGNORECASE)

# A field name (optionally `variable.field`) directly followed by `:` or
# `=` and a quote character marks a literal value bound in place of a
# parameter, e.g. `symbol: 'BRCA1'` or `n.name = "BRCA1"`. Per
# production-standards, every caller-supplied value must travel through a
# parameter, never a literal interpolated into the Cypher text. The field
# name is captured so the allowlist below can exempt a genuine internal
# constant (F-2.1-A17) without reopening the door to a caller-supplied
# entity value bound the same way.
_LITERAL_VALUE_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*['\"]"
)

# Fields whose value set is a small, system-defined vocabulary describing
# what kind of record or edge something is (a BioLink-style discriminator:
# categories, predicates, CURIEs, per
# docs/architecture/Biolink_repos_explained.md), never an open-ended
# identifying value for one specific entity. A literal bound to one of
# these is the generator's own fixed constant, not a caller-supplied value
# that should have traveled as a parameter. This is a judgment call, not a
# provenance proof: see the module docstring's F-2.1-A17 note.
_INTERNAL_CONSTANT_FIELDS = frozenset({"source", "category", "predicate"})

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


def _strip_comments(cypher: str) -> str:
    """Return cypher with every `//` line comment and `/* */` block comment
    removed, without touching either kind of marker when it occurs inside
    a single- or double-quoted string literal.

    This runs before every other check, not only before LIMIT analysis.
    F-2.1-A8 demonstrated a comment hiding a fake LIMIT from the injector;
    the same trick works against the paren-balance check and the
    forbidden-clause check (a stray `)` or a keyword tucked inside a
    comment can flip either verdict), so comments are stripped once, up
    front, and every check downstream operates on the same
    comment-free string.

    Quote-aware because a legitimate internal constant can itself contain
    `//`, for example a URL. A blind text-based strip would corrupt that
    literal; this walks the string tracking whether it is currently inside
    a string literal and only treats `//` or `/*` as a comment marker
    outside of one. A backslash-escaped quote inside a string is copied
    through verbatim so it is never mistaken for the string's closing
    quote.
    """
    result: list[str] = []
    index = 0
    length = len(cypher)
    open_quote: str | None = None
    while index < length:
        char = cypher[index]
        if open_quote is not None:
            result.append(char)
            if char == "\\" and index + 1 < length:
                result.append(cypher[index + 1])
                index += 2
                continue
            if char == open_quote:
                open_quote = None
            index += 1
            continue
        if char in ("'", '"'):
            open_quote = char
            result.append(char)
            index += 1
            continue
        if cypher[index:index + 2] == "//":
            newline_index = cypher.find("\n", index)
            index = length if newline_index == -1 else newline_index
            continue
        if cypher[index:index + 2] == "/*":
            close_index = cypher.find("*/", index + 2)
            if close_index == -1:
                index = length
            else:
                result.append(" ")
                index = close_index + 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _iter_paren_contents(cypher: str) -> list[str]:
    """Return the content of every parenthesized region, at every nesting
    depth, not only the outermost, non-nested ones.

    A single-level `\\(([^()]*)\\)` regex cannot cross a nested `(`, so a
    node pattern whose property map contains a function call, such as
    `(n:TotallyFakeLabel {name: coalesce($a, $b)})`, is never matched at
    all: the outer paren's content includes the inner `coalesce(` open
    paren, so the non-nesting regex skips straight past the real node
    pattern to the inner call's own parens instead, and the hallucinated
    label is never checked (F-2.1-A9). A label spec always sits directly
    after a node pattern's opening `(`, before any `{` and before any
    nested call, so once the full, correctly balanced content is in hand,
    the existing `_extract_node_labels` logic (which already only looks at
    the portion before the first `{`) needs no change at all.

    Only called after `_is_malformed` has already confirmed the brackets
    balance, but written defensively regardless: an unmatched closer is
    simply ignored rather than raising.
    """
    contents: list[str] = []
    stack: list[int] = []
    for index, char in enumerate(cypher):
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            start = stack.pop()
            contents.append(cypher[start + 1:index])
    return contents


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


def _find_suspect_literal(cypher: str) -> bool:
    """Return True when a literal is bound to a field outside the small
    internal-constant allowlist (F-2.1-A17).

    Every match is checked, not only the first: a query can legitimately
    contain one allowlisted literal (`a.source = 'PubMed'`) and one
    caller-facing one in the same string, and the whole query must still
    be rejected for the second.
    """
    for match in _LITERAL_VALUE_PATTERN.finditer(cypher):
        field = match.group(1).lower()
        if field not in _INTERNAL_CONSTANT_FIELDS:
            return True
    return False


def _run_safety_checks(cypher: str) -> ValidationResult | None:
    """Run every accept-or-reject check and return the first rejection, or
    None when the string clears all of them.

    Fixed order: malformed shape first, since nothing downstream can be
    evaluated on an unparseable string; forbidden write clauses next,
    since that is the highest-severity rejection; then edge label typing,
    then vertex label typing, then the literal-interpolation heuristic.

    Split out of `validate_cypher` so the exact same checks can run twice
    (F-08 / bypass 4): once on the comment-stripped input, and again on
    the final LIMIT-normalized string, so what gets executed is what was
    actually validated, not just what was validated before normalization
    ran.
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

    for content in _iter_paren_contents(cypher):
        for label in _extract_node_labels(content):
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

    if _find_suspect_literal(cypher):
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

    return None


def _coerce_row_limit(row_limit: object) -> int | None:
    """Return row_limit as a bounds-checked int, or None if it cannot be
    trusted (F-08 / bypass 4).

    This validator is the query-safety gate for Layer 1, so it never
    assumes an upstream caller already validated row_limit, even though
    `CypherQueryInput.row_limit` (T-2.1-01) is a Pydantic `Field(ge=1,
    le=500)` int today. Any type other than `int` is rejected outright
    rather than parsed: parsing a caller-controlled string (for example
    with `int()` after stripping non-digit characters) is itself the
    injection surface this check exists to close. A bool is rejected too,
    even though `bool` is an `int` subclass in Python: it is never a
    meaningful row_limit.
    """
    if isinstance(row_limit, bool) or not isinstance(row_limit, int):
        return None
    if row_limit < 1 or row_limit > MAX_ROW_LIMIT:
        return None
    return row_limit


def _split_on_union(cypher: str) -> list[str]:
    """Split cypher on every top-level UNION / UNION ALL keyword.

    The returned list alternates branch, separator, branch, ..., branch:
    even indices are query branches, odd indices are the matched
    separator token itself (preserved verbatim, casing included). Cypher
    scopes a trailing LIMIT to the query part immediately before it, never
    to the whole UNION result set, so capping only the final branch (as a
    single whole-string LIMIT search does) leaves every earlier branch
    unbounded (F-2.1-A8). Normalizing each branch independently closes
    that gap.
    """
    parts: list[str] = []
    last_end = 0
    for match in _UNION_PATTERN.finditer(cypher):
        parts.append(cypher[last_end:match.start()])
        parts.append(match.group(0))
        last_end = match.end()
    parts.append(cypher[last_end:])
    return parts


def _normalize_branch_limit(branch: str, row_limit: int) -> str:
    """Inject a missing top-level LIMIT into one query branch, or cap an
    existing genuine trailing one at MAX_ROW_LIMIT.

    Only a LIMIT anchored to the very end of the (rstripped) branch counts
    as genuine (see `_TRAILING_LIMIT_PATTERN`). A `LIMIT` keyword found
    anywhere else in the branch, inside a comment (already stripped by
    the time this runs), inside a mid-query `WITH ... LIMIT n` scoping
    clause, or on an earlier UNION branch, is not this branch's trailing
    limit and must not be mistaken for one (F-2.1-A8).
    """
    stripped = branch.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].rstrip()

    existing = _TRAILING_LIMIT_PATTERN.search(stripped)
    if existing is None:
        return stripped + " LIMIT " + str(row_limit)

    requested = int(existing.group(1))
    if requested > MAX_ROW_LIMIT:
        start, end = existing.span(1)
        return stripped[:start] + str(MAX_ROW_LIMIT) + stripped[end:]
    return stripped


def _normalize_limit(cypher: str, row_limit: int) -> str:
    """Inject a missing LIMIT, or cap an existing one, independently on
    every top-level UNION branch."""
    parts = _split_on_union(cypher)
    normalized_parts: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            normalized_parts.append(part.strip())
        else:
            normalized_parts.append(_normalize_branch_limit(part, row_limit))
    return " ".join(piece for piece in normalized_parts if piece)


def validate_cypher(cypher: str, row_limit: int = DEFAULT_ROW_LIMIT) -> ValidationResult:
    """Validate a generated Cypher body deterministically.

    Coerces and bounds-checks row_limit first (F-08 / bypass 4): a
    row_limit this validator cannot trust as a plain int between 1 and
    MAX_ROW_LIMIT is rejected before any Cypher analysis runs at all.
    Strips comments next (F-2.1-A8), since a comment can otherwise hide a
    fake LIMIT, an unbalancing bracket, or a forbidden keyword from every
    check that follows. Runs the full safety-check suite on the
    comment-stripped string, normalizes the LIMIT clause, and then runs
    the exact same safety-check suite again on the normalized string
    before returning it: normalization is itself a string transformation,
    and this validator never hands back a string it has not itself
    verified.

    Args:
        cypher: the generated Cypher body, with no markdown fence, no
            prose, and no `SELECT * FROM cypher(...)` wrapper.
        row_limit: the caller's requested row limit, already validated by
            the input schema (T-2.1-01) to be between 1 and MAX_ROW_LIMIT,
            but re-validated here rather than trusted.

    Returns:
        A ValidationResult. ok is True only when the query is safe to hand
        to `graph_connection.execute_cypher` (T-2.1-06) as-is.
    """
    bounded_row_limit = _coerce_row_limit(row_limit)
    if bounded_row_limit is None:
        return ValidationResult(
            ok=False,
            reason=REASON_INVALID_ROW_LIMIT,
            message=(
                "row_limit must be a plain int between 1 and "
                + str(MAX_ROW_LIMIT)
                + ". This is a defect in the caller, not the generated "
                "Cypher; do not retry generation, fix the caller's "
                "row_limit value instead."
            ),
            normalized_cypher=None,
        )

    working = _strip_comments(cypher)

    rejection = _run_safety_checks(working)
    if rejection is not None:
        return rejection

    normalized = _normalize_limit(working, bounded_row_limit)

    post_rejection = _run_safety_checks(normalized)
    if post_rejection is not None:
        return ValidationResult(
            ok=False,
            reason=post_rejection.reason,
            message=(
                "Generated Cypher failed re-validation after LIMIT "
                "normalization, so it was never executed: "
                + str(post_rejection.message)
            ),
            normalized_cypher=None,
        )

    return ValidationResult(
        ok=True,
        reason=None,
        message="Validation passed.",
        normalized_cypher=normalized,
    )
