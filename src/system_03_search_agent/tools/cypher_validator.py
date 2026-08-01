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

Known limitation surfaced by the adversary as F-2.1-B08, fixed here: the
literal check used to key off named comparison operators one at a time,
`=` or `:` immediately followed by a quote. Cypher's other comparison and
predicate forms (`STARTS WITH`, `CONTAINS`, `ENDS WITH`, `=~`, `IN [...]`,
`<>`, and a bare unquoted numeric literal such as `{taxon: 9606}`) walked
straight through, because the old pattern only recognized a quote right
after `=` or `:`. Four bypasses of this same shape were already fixed in
this phase's rework before this one; the fix here does not add a sixth
enumerated operator, it inverts the default. `_LITERAL_VALUE_PATTERN` now
matches a field name followed by any run of comparison symbol characters
(`=`, `<`, `>`, `~`, `!`, `:`) or one of openCypher's fixed keyword
predicates (`IN`, `STARTS WITH`, `CONTAINS`, `ENDS WITH`, a small closed
set the language itself defines, not an open-ended list of operators
someone might invent), followed directly by a literal. A comparison
operator this validator has never seen before is still recognized as
some connector between a field and a literal, because the symbol class
matches by character, not by naming the operator.

An earlier version of this paragraph claimed more than that: it said a
further bypass of this same shape needed no further code change here,
full stop. That claim was false, and the adversary proved it as
F-2.1-C08, reproduced live against the graph. The fixed part held: no
new comparison operator defeats detection when a literal genuinely sits
next to a field name. What the claim ignored is that the adjacency
requirement itself, a field name directly next to the connector and the
literal, is exactly the thing a caller can route around without
inventing a new operator at all. Bind the literal to a `WITH` or
`UNWIND` alias first, then use the alias where the literal would have
gone, and no field is ever adjacent to a literal anywhere in the query
text. What this paragraph's fix actually guarantees, precisely: given a
literal sitting directly next to a field name and a connector, no
comparison operator shape defeats detection. It says nothing about a
literal reached through an alias, a function call, or any other
indirection. The alias case is fixed separately below (F-2.1-C08). A
literal with no field name adjacent to it at all for another reason, for
example one wrapped inside a function call (`toLower(g.name) = 'x'`),
remains open; that gap is the same documented, conservative scope
boundary the rest of this module already lives with, not one this fix
or the one below introduces or closes.

Known limitation surfaced by the adversary as F-2.1-C08, fixed here: the
literal check was also not quote-aware. It matched a field-connector-
literal shape against the raw query string, so a literal's own quoted
content could accidentally satisfy that same shape purely by coincidence
(the literal `'NCBIGene:672'` contains a colon followed by digits, which
the old pattern read as a field-connector-literal match even though
none of it sits outside the string), while splitting that same content
across two literals (`'NCBIGene' + ':7157'`) stopped the accidental
match from firing at all. Neither behavior reflected anything about the
query's real structure. `_mask_string_literals` now walks the string
quote-aware, exactly like `_strip_comments` already does, and replaces
every single- or double-quoted literal, quotes included, with one opaque
placeholder token before any structural regex runs. Every check in this
function now reasons about where a literal sits in the query's actual
syntax, never about what a literal's own content happens to spell out.

The second half of F-2.1-C08 is the alias-indirection bypass itself:
`WITH 'NCBIGene' AS p, '7157' AS n WITH p + ':' + n AS target MATCH
(g:Gene {id: target}) RETURN g`, and the simpler `WITH 'BRCA1 DNA repair
associated' AS t MATCH (g:Gene) WHERE g.name = t RETURN g`, both executed
live against the graph and returned results for an entity the caller
never asked about. `_find_tainted_aliases` tracks every alias a `WITH`
or `UNWIND` clause binds to a value built solely from literals, directly,
through string concatenation (`p + ':' + n`), or through a chain of
earlier tainted aliases across multiple `WITH` clauses in sequence. The
same field-connector shape used for a direct literal is then run a
second time with a tainted alias standing in for the literal, split
independently per `UNION` branch so an alias name is never treated as
tainted outside the branch that actually taints it. This closes the
alias, concatenation, and `UNWIND`-list forms the adversary demonstrated.
It does not close every indirection: an alias passed through a further
function call before use (`WITH 'BRCA1' AS t WITH toUpper(t) AS t2
MATCH (g:Gene {symbol: t2})`) is not tracked as tainted, because the
value inside the call is no longer a bare literal or a bare tainted
identifier once a function wraps it, and this module does not evaluate
functions. That is a known, open gap, not a claim of completeness this
fix makes and later breaks.

The paragraph above was wrong to leave that gap open, and a judge proved
it as F-2.1-J4-01, reproducing it live alongside four further bypasses
of the same overall check, three of them executed live against the
graph and returning results for an entity the caller never asked about,
the same shape of failure as F-2.1-B01 and F-2.1-C08 before it, arriving
through a third door. Fixed here, five bypasses at once:

- Function-call and other opaque wrapping (`WITH 'NCBIGene:7157' AS t
  WITH toString(t) AS t2 ...`, and the same shape through `substring`).
  `_is_tainted_expr` no longer gives up the moment an expression stops
  being a bare literal, a bare numeric literal, or a bare tainted
  identifier. Any further atom it cannot decompose into a list or a
  `+`-chain, a function call, a `CASE` expression, anything, is now
  treated as tainted the moment a literal token or a whole-word
  reference to an already-tainted alias appears anywhere inside its
  text. A function wrapper does not remove a literal from the value it
  produces, it only obscures how, so this fix does not need to know
  what any specific function does.
- List literals (`WITH ['NCBIGene:7157'] AS l MATCH (g:Gene {id: l[0]})
  ...`). `_is_tainted_expr` previously recognized no bracketed shape at
  all; a list literal is now tainted when every one of its top-level
  comma-separated elements is.
- Reversed operand order (`WITH 'NCBIGene:7157' AS t ... WHERE t =
  g.id ...`). Both the direct-literal pattern and the tainted-alias
  pattern only ever recognized field-connector-value, never
  value-connector-field, even though Cypher's comparison operators
  carry no direction. Both patterns now run in both orders.
- A literal reached through a `CASE` expression with no alias involved
  at all (`WHERE g.id = CASE WHEN true THEN 'NCBIGene:7157' ELSE ''
  END`). This one is a regression, not a new gap: it was rejected before
  the F-2.1-C08 alias-taint rework and passed afterward. A `CASE ...
  END` block immediately following a field and a connector is now
  scanned for a literal token anywhere inside it, not only directly
  adjacent to the connector; the same allowlist exemption for a known
  internal-constant field still applies.

What this fix does not claim, stated precisely rather than asserted
closed: an opaque atom containing neither a literal token nor a
reference to an already-tainted alias is still left untainted, because
this module does not evaluate what a function actually computes, only
what literal text flows into it. A `CASE` expression reached through
further indirection, behind a further function call, or compared to a
field only after being routed through its own alias first, is not
provably covered: the `CASE` check here is adjacency-based, the same
family of gap the alias-taint mechanism closes for a plain alias but
that this fix does not extend to a `CASE` block sitting behind one.
That is a known, open gap. The three corrections stacked in this
docstring now, this one and the two above it, are the record of what
"closed" has actually meant each time it was claimed, not a promise
this is the last one.

Known limitation surfaced by the adversary as F-2.1-B09, fixed here: LIMIT
normalization only ever recognized `LIMIT <digits>` anchored to the very
end of a branch. A LIMIT followed by a trailing `SKIP <digits>` in
non-standard order, or a parameterized `LIMIT $name`, was invisible to
that check, so a second LIMIT got appended after it and the validator
handed back Cypher it had just made syntactically invalid (confirmed
against the live graph: AGE raises a genuine syntax error on `LIMIT
<digits> SKIP <digits>`, and raises `UndefinedParameter` on `LIMIT
$name` called with no bound parameter, since this validator has no way
to know at validation time what value a parameter will carry, so it
cannot verify the value is within the row cap). Every LIMIT occurrence is
now classified as scoping (more query structure follows, the legitimate
`WITH ... LIMIT n MATCH ...` shape from F-2.1-A8, left untouched),
terminal and safe (plain digits, nothing meaningful follows, capped as
before), or terminal and unsafe (anything else meant to be the query's
final LIMIT: a parameter reference, a trailing SKIP in the wrong order,
or any other tail this validator cannot verify). A terminal-unsafe LIMIT
rejects the whole query with `unsafe_limit_clause` rather than silently
producing a second, broken LIMIT clause.

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
# New for F-2.1-B09: a LIMIT clause that is meant to be the query's final,
# caller-facing cap, but is not a single plain integer with nothing but
# the query's own results following it. Appending a second LIMIT after it
# would produce syntactically invalid Cypher, so this rejects instead of
# guessing.
REASON_UNSAFE_LIMIT_CLAUSE = "unsafe_limit_clause"

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

# Every LIMIT keyword and its immediate argument token, wherever it occurs
# in a (rstripped) query or UNION branch, not only at the very end
# (F-2.1-B09). Group 1 is the argument token itself: plain digits, a
# parameter reference, or anything else a generator might emit. Finding
# every occurrence, rather than only a trailing one, is what lets
# `_classify_limit_occurrence` tell a legitimate mid-query scoping LIMIT
# apart from a final LIMIT this validator cannot safely normalize.
_LIMIT_OCCURRENCE_PATTERN = re.compile(r"\bLIMIT\s+(\S+)", re.IGNORECASE)

# Clause-starting keywords that indicate a LIMIT occurrence is a
# legitimate intra-query scoping LIMIT (F-2.1-A8: `WITH g LIMIT 1 MATCH
# ...`), not the query's final, caller-facing LIMIT. When one of these
# keywords is the next word after a LIMIT clause's argument, more query
# structure continues, so that LIMIT is left untouched and the
# validator's own cap is still appended at the true end of the branch.
_CLAUSE_CONTINUATION_KEYWORDS = frozenset({
    "MATCH", "OPTIONAL", "WITH", "WHERE", "UNWIND", "CALL", "RETURN",
    "MERGE", "CREATE", "SET", "DELETE", "REMOVE", "DETACH",
})

# A top-level UNION or UNION ALL keyword. Cypher scopes a trailing LIMIT
# to the query part immediately before it, never to the whole UNION result
# set, so every branch must be normalized independently (F-2.1-A8).
_UNION_PATTERN = re.compile(r"\bUNION\s+ALL\b|\bUNION\b", re.IGNORECASE)

# The opaque placeholder every quoted string literal is replaced with
# before any structural regex in this module runs (F-2.1-C08). A single
# Unicode private-use character, never a character that can appear in
# generated Cypher on its own, so it can never be confused with an
# identifier, a digit, a connector, or a quote once substituted in.
_LITERAL_TOKEN = ""

# A bare numeric literal, signed or unsigned, integer or decimal. Used
# only to decide whether a `WITH`/`UNWIND` expression is wholly built out
# of literals for alias-taint tracking (F-2.1-C08); the digit itself was
# never inside a string, so masking never touches it.
_NUMERIC_LITERAL_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")

# A connector between a field and a literal value, matched by shape
# rather than enumerated operator-by-operator (F-2.1-B08). Two kinds:
#
# - A run of comparison symbol characters (`=`, `<`, `>`, `~`, `!`, `:`).
#   This is a character class, not a list of named operators, so it
#   already matches `=`, `:`, `<>`, `=~`, and any future symbol-based
#   comparison this validator has never been told about by name.
# - One of openCypher's own fixed keyword predicates for string and list
#   membership tests: `IN`, `STARTS WITH`, `CONTAINS`, `ENDS WITH`. This
#   is enumerated, but it is enumerating the language's own closed
#   grammar, not an open-ended set of operators someone might invent;
#   openCypher defines exactly these four.
_CONNECTOR_PATTERN = (
    r"(?:[=<>~!:]+|\bIN\b|\bSTARTS\s+WITH\b|\bCONTAINS\b|\bENDS\s+WITH\b)"
)

# A field name (optionally `variable.field`) followed by one or more
# connectors (see above), an optional `[` for an `IN [...]` list, and then
# a literal: the masked placeholder standing in for a string literal (see
# `_mask_string_literals`, F-2.1-C08), or a bare digit for an unquoted
# numeric literal such as `{taxon: 9606}`. Matched against the masked
# string, never the raw one: matching the placeholder instead of a raw
# quote character is what makes this quote-aware, since a quote character
# can no longer appear anywhere except as part of the query's own
# unquoted text once every literal is masked out, so a match can only
# ever fire on the query's actual syntax, never on a literal's own
# content (F-2.1-C08). Per production-standards, every caller-supplied
# value must travel through a parameter, never a literal interpolated
# into the Cypher text, whatever comparison form carries it. The field
# name is captured so the allowlist below can exempt a genuine internal
# constant (F-2.1-A17) without reopening the door to a caller-supplied
# entity value bound the same way. Because the connector is matched by
# shape rather than by naming every operator that might carry a literal,
# a comparison form this validator has never seen before is still
# recognized as *some* connector: it is caught by the same pattern, not
# by a new one (F-2.1-B08).
_LITERAL_VALUE_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)"
    r"\s*(?:" + _CONNECTOR_PATTERN + r"\s*)+\[?\s*"
    r"(?:" + re.escape(_LITERAL_TOKEN) + r"|-?\d)"
)

# The same field-connector-literal shape as `_LITERAL_VALUE_PATTERN`,
# operands swapped: a literal on the left, the field on the right
# (F-2.1-J4-01). `_LITERAL_VALUE_PATTERN` alone only ever recognized
# field-connector-literal; `literal-connector-field` (`WHERE 'BRCA1' =
# g.symbol`) walked straight through it, the same order-sensitivity bug
# the reversed alias pattern below closes for the aliased case. The
# captured group is the field name, same position convention as the
# forward pattern, so callers read `match.group(1)` identically either
# way.
_REVERSED_LITERAL_VALUE_PATTERN = re.compile(
    r"(?:" + re.escape(_LITERAL_TOKEN) + r"|-?\d)"
    r"\s*(?:" + _CONNECTOR_PATTERN + r"\s*)+"
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)"
)

# A `CASE ... END` block, non-greedy so consecutive CASE blocks in one
# query are each captured on their own rather than one match swallowing
# everything from the first CASE to the last END (F-2.1-J4-01). A CASE
# expression nested inside another CASE's WHEN/THEN/ELSE branch is not
# specially handled: the non-greedy match stops at the first END it
# finds, which is the inner one, not the outer one. That is a known,
# narrow gap in this one detection, not a claim every CASE shape is
# covered.
_CASE_BLOCK_PATTERN = re.compile(r"\bCASE\b.*?\bEND\b", re.IGNORECASE | re.DOTALL)

# A field name, a connector, and an optional `[`, immediately followed by
# a CASE block, matched against the masked string so only the query's
# real syntax can trigger it (F-2.1-J4-01). This is what lets
# `_find_suspect_case_literal` apply the same F-2.1-A17 internal-constant
# allowlist to a literal reached through a CASE expression that it
# already applies to a literal reached directly or through a tainted
# alias: the field immediately before the CASE block is the field this
# validator checks against the allowlist, not the CASE block's own
# content.
_FIELD_BEFORE_CASE_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)"
    r"\s*(?:" + _CONNECTOR_PATTERN + r"\s*)+\[?\s*(?=CASE\b)",
    re.IGNORECASE,
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


def _mask_string_literals(cypher: str) -> str | None:
    """Return cypher with every single- or double-quoted string literal,
    quotes included, replaced by the single opaque `_LITERAL_TOKEN`
    placeholder. Returns None when a quote is left open at the end of the
    string.

    This is what makes `_find_suspect_literal` quote-aware (F-2.1-C08).
    The old literal check was a blind regex over the raw string, so a
    field-connector-literal shape could match purely because of a
    literal's own quoted content, with nothing outside the quotes
    involved at all: the literal `'NCBIGene:672'` contains a colon
    followed by digits, which reads exactly like a field name, a
    connector, and a numeric literal to a regex that does not know it is
    inside a string. Masking every literal down to one token before any
    structural regex runs means a match can only ever fire on the
    query's actual syntax, since a real quote character cannot appear
    anywhere in the masked string except as part of a token this
    function has already fully accounted for.

    Uses the same quote-tracking walk as `_strip_comments`, deliberately:
    both need to know, character by character, whether the parser is
    currently inside a string literal, and a backslash-escaped quote
    inside one is copied straight through so it is never mistaken for
    the literal's closing quote. Called only after `_strip_comments` has
    already run, so no comment marker is a factor here.

    An unterminated literal is not silently passed through as raw,
    unmasked text: this module never hands back a verdict on a string it
    could not fully account for (the same conservative posture
    `_is_malformed` already takes on unbalanced brackets), so the caller
    treats a None return as itself a suspect construct.
    """
    result: list[str] = []
    index = 0
    length = len(cypher)
    open_quote: str | None = None
    while index < length:
        char = cypher[index]
        if open_quote is not None:
            if char == "\\" and index + 1 < length:
                index += 2
                continue
            if char == open_quote:
                open_quote = None
                result.append(_LITERAL_TOKEN)
            index += 1
            continue
        if char in ("'", '"'):
            open_quote = char
            index += 1
            continue
        result.append(char)
        index += 1
    if open_quote is not None:
        return None
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


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split text on every occurrence of separator that sits outside any
    `()`, `[]`, or `{}` nesting (F-2.1-C08).

    Used for splitting a `WITH`/`UNWIND` projection list on its top-level
    commas and an alias-bound expression on its top-level `+` operators,
    so a comma or `+` inside a nested function call or list is never
    mistaken for one of these boundaries. Operates on an already
    quote-masked string, so a literal's own content can never contain a
    stray bracket character that would throw the depth count off.
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    length = len(text)
    sep_length = len(separator)
    while index < length:
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if depth == 0 and text[index:index + sep_length] == separator:
            parts.append("".join(current))
            current = []
            index += sep_length
            continue
        current.append(char)
        index += 1
    parts.append("".join(current))
    return parts


def _is_fully_parenthesized(expr: str) -> bool:
    """Return True when expr is wrapped in one matching outer `(...)` pair
    that spans the whole string, not two separate parenthesized pieces
    such as `(a) + (b)` that merely start with `(` and end with `)`.
    """
    if not (expr.startswith("(") and expr.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(expr) - 1:
                return False
    return True


def _is_fully_bracketed(expr: str, open_char: str, close_char: str) -> bool:
    """Return True when expr is wrapped in one matching outer bracket pair
    that spans the whole string, the same guarantee `_is_fully_parenthesized`
    gives for `(...)`, generalized to any single open/close character pair
    (F-2.1-J4-01, used here for `[...]`).
    """
    if not (expr.startswith(open_char) and expr.endswith(close_char)):
        return False
    depth = 0
    for index, char in enumerate(expr):
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0 and index != len(expr) - 1:
                return False
    return True


def _is_tainted_expr(expr: str, tainted: frozenset[str]) -> bool:
    """Return True when expr can only ever carry a value built from a
    literal, directly or through indirection this module can see through
    (F-2.1-C08, widened by F-2.1-J4-01).

    Three structural shapes are decomposed and checked recursively: a
    fully-parenthesized wrapper is unwrapped, a list literal (`[...]`) is
    tainted when every one of its top-level comma-separated elements is,
    and a `+`-chain is tainted when every top-level part is. Neither
    shape was recognized before F-2.1-J4-01; a list literal fell straight
    through to "not tainted" with no check at all, which is what let a
    literal wrapped in a one-element list and pulled back out by index
    (`l[0]`) go undetected.

    Anything left over after those three shapes are ruled out is a
    single, non-decomposable atom. A bare literal, a bare numeric
    literal, or a bare identifier already in `tainted` is classified
    directly, unchanged from before this fix. Everything else, a real
    field access (`g.name`), a parameter reference (`$symbol`), a
    function call (`toString(t)`, `substring(t, 1)`), a `CASE`
    expression, or any other construct this module does not parse, used
    to fall through to "not tainted" unconditionally. That was the
    F-2.1-J4-01 gap: a function or `CASE` wrapper does not remove a
    literal from the value it produces, it only obscures how, so an
    opaque atom is now tainted the moment a literal token or a whole-word
    reference to an already-tainted alias appears anywhere inside its
    text, not only when the atom is nothing but that literal or that
    alias. An opaque atom with neither is still left untainted: this
    module does not evaluate what a function or a `CASE` branch actually
    computes, only what literal text visibly flows into it, so an atom
    that clears both scans is a known, open gap, not a proof of safety.
    """
    expr = expr.strip()
    while _is_fully_parenthesized(expr):
        expr = expr[1:-1].strip()
    if not expr:
        return False

    if _is_fully_bracketed(expr, "[", "]"):
        items = _split_top_level(expr[1:-1], ",")
        return bool(items) and all(
            item.strip() and _is_tainted_expr(item, tainted) for item in items
        )

    parts = _split_top_level(expr, "+")
    if len(parts) > 1:
        if any(not part.strip() for part in parts):
            return False
        return all(_is_tainted_expr(part, tainted) for part in parts)

    if expr == _LITERAL_TOKEN:
        return True
    if _NUMERIC_LITERAL_PATTERN.match(expr):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
        return expr in tainted

    # An opaque atom: a function call, a CASE expression, or any other
    # construct this module cannot decompose further. See the docstring
    # above (F-2.1-J4-01) for why this scans the atom's text for a
    # literal or a tainted reference anywhere, rather than requiring the
    # whole atom to be one.
    if _LITERAL_TOKEN in expr:
        return True
    return any(
        re.search(r"\b" + re.escape(name) + r"\b", expr) for name in tainted
    )


# The `AS` keyword binding an expression to an alias in a `WITH` or
# `UNWIND` projection item, e.g. `p + ':' + n AS target`.
_AS_KEYWORD_PATTERN = re.compile(r"\bAS\b", re.IGNORECASE)


def _split_alias_binding(item: str) -> tuple[str, str] | None:
    """Split one `WITH`/`UNWIND` projection item on its `AS` keyword.

    Returns (expr, alias), splitting on the last `AS` in the item since
    Cypher allows only one per projection item. Returns None for a plain
    passthrough variable with no `AS` at all (`WITH g`), which introduces
    no new alias and is not this function's concern, or when the text
    after the last `AS` is not a bare identifier.
    """
    matches = list(_AS_KEYWORD_PATTERN.finditer(item))
    if not matches:
        return None
    last = matches[-1]
    expr = item[:last.start()].strip()
    alias = item[last.end():].strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        return None
    return expr, alias


# Every top-level clause-boundary keyword this module recognizes, used
# only to isolate the projection body of a `WITH` or `UNWIND` clause for
# alias-taint analysis (F-2.1-C08). Not a general parser and not used by
# any other check in this module.
_CLAUSE_BOUNDARY_PATTERN = re.compile(
    r"\bOPTIONAL\s+MATCH\b|\bMATCH\b|\bWITH\b|\bWHERE\b|\bUNWIND\b|\bCALL\b|"
    r"\bRETURN\b|\bMERGE\b|\bCREATE\b|\bSET\b|\bDELETE\b|\bREMOVE\b|"
    r"\bDETACH\b|\bORDER\s+BY\b|\bSKIP\b|\bLIMIT\b",
    re.IGNORECASE,
)


def _iter_clause_bodies(cypher: str) -> list[tuple[str, str]]:
    """Split cypher into (keyword, body) pairs at every top-level clause
    boundary keyword (F-2.1-C08).

    Each body runs from just after one boundary keyword to just before
    the next, or to the end of the string for the last one. This is what
    lets `_find_tainted_aliases` isolate the projection list of one
    `WITH` or `UNWIND` clause at a time, in the order they appear, so a
    later `WITH` clause's alias-taint check sees the aliases an earlier
    one already bound.
    """
    matches = list(_CLAUSE_BOUNDARY_PATTERN.finditer(cypher))
    clauses: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cypher)
        keyword = re.sub(r"\s+", " ", match.group(0).strip().upper())
        clauses.append((keyword, cypher[start:end]))
    return clauses


def _tainted_aliases_from_with_body(
    body: str, tainted: frozenset[str]
) -> set[str]:
    """Return every alias one `WITH` clause's projection list binds to a
    literal-or-tainted expression (F-2.1-C08).

    Every item is checked against the tainted set as it stood before this
    `WITH` clause, never against aliases this same clause is in the
    middle of binding: Cypher does not let one projection item reference
    a sibling bound in the same `WITH`, so neither does this check.
    """
    newly_tainted: set[str] = set()
    for item in _split_top_level(body, ","):
        binding = _split_alias_binding(item)
        if binding is None:
            continue
        expr, alias = binding
        if _is_tainted_expr(expr, tainted):
            newly_tainted.add(alias)
    return newly_tainted


def _tainted_aliases_from_unwind_body(
    body: str, tainted: frozenset[str]
) -> set[str]:
    """Return the alias one `UNWIND` clause binds, when every item in its
    list is itself literal-or-tainted, or when its whole expression is
    (F-2.1-C08).

    An `UNWIND ['a', 'b'] AS x` iterates over a list built solely from
    literals, so x carries a literal value on every row and is tainted
    the same way a direct `WITH` binding is. A list with even one item
    this function cannot classify as literal-or-tainted, for example a
    genuine parameter alongside a literal, is not tainted at all: this is
    a known, deliberately conservative gap rather than a partial-taint
    heuristic this module does not have the structure to reason about
    safely.
    """
    binding = _split_alias_binding(body)
    if binding is None:
        return set()
    expr, alias = binding
    expr = expr.strip()
    if expr.startswith("[") and expr.endswith("]"):
        items = _split_top_level(expr[1:-1], ",")
        if items and all(_is_tainted_expr(item, tainted) for item in items):
            return {alias}
        return set()
    if _is_tainted_expr(expr, tainted):
        return {alias}
    return set()


def _find_tainted_aliases(masked_cypher: str) -> frozenset[str]:
    """Return every alias masked_cypher binds, directly or through a
    chain of earlier tainted aliases, to a value built solely from
    literals (F-2.1-C08).

    This closes the alias-indirection bypass: `_LITERAL_VALUE_PATTERN`
    only ever sees a literal that sits directly next to a field name and
    a connector in the query text. Binding the literal to a `WITH ... AS`
    or `UNWIND ... AS` alias first, then using the alias in the match
    position, defeats that adjacency requirement with no literal ever
    appearing next to a field at all. `WITH` and `UNWIND` clauses are
    walked in the order they occur so a later `WITH` clause that
    references an earlier one's alias, the exact shape of the adversary's
    `WITH 'NCBIGene' AS p, '7157' AS n WITH p + ':' + n AS target`
    reproduction, is tracked correctly.

    Expects an already quote-masked string (see `_mask_string_literals`);
    every literal in it is the opaque placeholder token, never raw quoted
    text, which is what lets `_is_tainted_expr` recognize a literal by
    exact token match instead of by re-parsing quotes itself.
    """
    tainted: set[str] = set()
    for keyword, body in _iter_clause_bodies(masked_cypher):
        if keyword == "WITH":
            tainted |= _tainted_aliases_from_with_body(body, frozenset(tainted))
        elif keyword == "UNWIND":
            tainted |= _tainted_aliases_from_unwind_body(body, frozenset(tainted))
    return frozenset(tainted)


def _alias_alternation(tainted: frozenset[str]) -> str:
    """Build a `|`-joined, escaped regex alternation over tainted alias
    names, longest name first (F-2.1-J4-01).

    Longest-first is not load-bearing for correctness, since a regex
    alternation backtracks across alternatives to satisfy the rest of a
    pattern including a `\\b` boundary, but it avoids relying on that
    backtracking at all: with "t2" listed before "t", a search for "t2"
    matches on the first alternative tried, not the second.
    """
    return "|".join(
        re.escape(alias) for alias in sorted(tainted, key=lambda a: (-len(a), a))
    )


def _build_tainted_alias_value_pattern(tainted: frozenset[str]) -> re.Pattern[str]:
    """Build the same field-connector-literal shape as
    `_LITERAL_VALUE_PATTERN`, with a tainted alias standing in for the
    literal (F-2.1-C08).

    The trailing `(?!\\s*\\.)` excludes a tainted alias immediately
    followed by `.`, since `x.foo` reads a property off of x rather than
    comparing a field directly to the tainted value x itself; a bare
    literal-derived scalar is never something a real query would then
    access a further property on, so this is a narrow, deliberate
    exclusion, not a loophole this pattern leaves open on purpose for any
    other reason.
    """
    return re.compile(
        r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)"
        r"\s*(?:" + _CONNECTOR_PATTERN + r"\s*)+\[?\s*"
        r"\b(?:" + _alias_alternation(tainted) + r")\b(?!\s*\.)"
    )


def _build_reversed_tainted_alias_value_pattern(
    tainted: frozenset[str],
) -> re.Pattern[str]:
    """The same shape as `_build_tainted_alias_value_pattern`, operands
    swapped: a tainted alias on the left, the field on the right
    (F-2.1-J4-01).

    `WITH 'NCBIGene:7157' AS t MATCH (g:Gene) WHERE t = g.id RETURN g`
    defeated the field-first pattern with nothing more than writing the
    same comparison backwards; Cypher's comparison operators carry no
    direction, so this validator's detection of them should not either.
    The captured group is still the field name, the last one in the
    pattern here, so callers read `match.group(1)` the same way for both
    directions.
    """
    return re.compile(
        r"\b(?:" + _alias_alternation(tainted) + r")\b(?!\s*\.)"
        r"\s*(?:" + _CONNECTOR_PATTERN + r"\s*)+"
        r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)"
    )


def _find_suspect_case_literal(masked: str) -> bool:
    """Return True when a `CASE ... END` block immediately following a
    field and a connector contains a literal token anywhere inside it,
    and that field is outside the F-2.1-A17 internal-constant allowlist
    (F-2.1-J4-01).

    `g.id = CASE WHEN true THEN 'NCBIGene:7157' ELSE '' END` has no
    literal directly adjacent to the `=` connector, `_LITERAL_VALUE_PATTERN`
    requires exactly that adjacency, so this shape walked straight
    through it. This check widens the window from "directly adjacent" to
    "anywhere inside the CASE block that follows", without widening it
    all the way to "anywhere in the query": the field immediately before
    the CASE block is still the field checked against the allowlist,
    matching the same convention `_find_suspect_literal`'s other two
    passes already use.

    This is adjacency-based like the checks around it, not a general
    scan: a CASE expression reached only through further indirection (a
    further function call, or compared to a field through its own alias
    first) is not covered here. See the module docstring's F-2.1-J4-01
    paragraph for what remains open.
    """
    for field_match in _FIELD_BEFORE_CASE_PATTERN.finditer(masked):
        case_match = _CASE_BLOCK_PATTERN.match(masked, field_match.end())
        if case_match is None:
            continue
        if _LITERAL_TOKEN not in case_match.group(0):
            continue
        field = field_match.group(1).lower()
        if field not in _INTERNAL_CONSTANT_FIELDS:
            return True
    return False


def _find_suspect_literal(cypher: str) -> bool:
    """Return True when a literal is bound to a field outside the small
    internal-constant allowlist (F-2.1-A17), directly, through a
    literal-derived alias (F-2.1-C08), or through a CASE expression
    (F-2.1-J4-01).

    Runs on a quote-masked copy of cypher (see `_mask_string_literals`),
    never the raw string, so a match can only ever fire on the query's
    actual syntax. An unterminated literal fails masking outright and is
    itself treated as suspect, the same conservative posture
    `_mask_string_literals` documents.

    Three passes, all over every match, not only the first: a query can
    legitimately contain one allowlisted literal (`a.source = 'PubMed'`)
    and one caller-facing one, direct or aliased, in the same string, and
    the whole query must still be rejected for the second.

    - The direct pass is the field-connector-literal shape, run in both
      operand orders (F-2.1-J4-01: a comparison written backwards,
      literal-connector-field, is exactly as unsafe as the forward
      order), checked once over the whole query: a field-adjacent
      literal is unsafe regardless of which `UNION` branch it sits in,
      so there is no scoping concern for this pass.
    - The CASE pass (`_find_suspect_case_literal`) is also checked once
      over the whole query, for the same reason.
    - The alias pass repeats the field-connector shape, also in both
      operand orders, with a tainted alias (see `_find_tainted_aliases`)
      standing in for the literal, run independently per top-level
      `UNION` branch. Cypher scopes a `WITH` or `UNWIND` alias to the
      branch that defines it, so an alias name tainted in one branch must
      never be treated as tainted in another branch that happens to
      reuse the same name for something else.
    """
    masked = _mask_string_literals(cypher)
    if masked is None:
        return True

    for pattern in (_LITERAL_VALUE_PATTERN, _REVERSED_LITERAL_VALUE_PATTERN):
        for match in pattern.finditer(masked):
            field = match.group(1).lower()
            if field not in _INTERNAL_CONSTANT_FIELDS:
                return True

    if _find_suspect_case_literal(masked):
        return True

    for index, branch in enumerate(_split_on_union(masked)):
        if index % 2 == 1:
            continue  # the UNION / UNION ALL separator token itself
        tainted = _find_tainted_aliases(branch)
        if not tainted:
            continue
        for builder in (
            _build_tainted_alias_value_pattern,
            _build_reversed_tainted_alias_value_pattern,
        ):
            alias_pattern = builder(tainted)
            for match in alias_pattern.finditer(branch):
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


def _classify_limit_occurrence(branch: str, match: re.Match[str]) -> str:
    """Classify one LIMIT occurrence in `branch` (F-2.1-B09).

    Returns one of three labels:

    - "scoping": a recognized clause keyword (`_CLAUSE_CONTINUATION_KEYWORDS`)
      immediately follows this LIMIT's argument, so more query structure
      continues. This is the legitimate `WITH g LIMIT 1 MATCH ...`
      mid-query cap from F-2.1-A8. Left untouched.
    - "terminal_safe": nothing but optional trailing whitespace follows
      the argument, and the argument is plain digits. The one shape this
      validator can verify and cap.
    - "terminal_unsafe": this LIMIT is meant to be the branch's final
      clause (no recognized further query structure follows it), but the
      argument is not a plain digit literal, or something this validator
      does not recognize follows it (a parameter reference, a `SKIP`
      clause tacked on in the wrong order, or anything else). Confirmed
      against the live graph that both of these actually fail at
      execution: `LIMIT <digits> SKIP <digits>` is a genuine AGE syntax
      error, and `LIMIT $name` cannot be verified as within the row cap
      at validation time, since a parameter's value is not known until
      execution. Appending a second LIMIT after either would only make
      matters worse, so this validator rejects instead.
    """
    rest = branch[match.end():]
    stripped_rest = rest.strip()
    if not stripped_rest:
        return "terminal_safe" if match.group(1).isdigit() else "terminal_unsafe"
    first_word = re.match(r"[A-Za-z_]+", stripped_rest)
    if first_word is not None and first_word.group(0).upper() in _CLAUSE_CONTINUATION_KEYWORDS:
        return "scoping"
    return "terminal_unsafe"


def _normalize_branch_limit(branch: str, row_limit: int) -> str | None:
    """Inject a missing top-level LIMIT into one query branch, cap an
    existing genuine trailing one at MAX_ROW_LIMIT, or signal that the
    branch cannot be safely normalized by returning None (F-2.1-B09).

    Every LIMIT occurrence in the branch is classified (see
    `_classify_limit_occurrence`). A single "terminal_unsafe" occurrence
    rejects the whole branch rather than being silently normalized into a
    second, syntactically invalid LIMIT clause. A "scoping" occurrence,
    such as a mid-query `WITH ... LIMIT n` clause, is left untouched
    (F-2.1-A8); a "terminal_safe" occurrence is the one this function caps
    as before. When no occurrence is terminal at all, the caller-facing
    LIMIT is injected fresh, exactly as when no LIMIT was present.
    """
    stripped = branch.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].rstrip()

    terminal_safe_match: re.Match[str] | None = None
    for match in _LIMIT_OCCURRENCE_PATTERN.finditer(stripped):
        classification = _classify_limit_occurrence(stripped, match)
        if classification == "terminal_unsafe":
            return None
        if classification == "terminal_safe":
            terminal_safe_match = match

    if terminal_safe_match is None:
        return stripped + " LIMIT " + str(row_limit)

    requested = int(terminal_safe_match.group(1))
    if requested > MAX_ROW_LIMIT:
        start, end = terminal_safe_match.span(1)
        return stripped[:start] + str(MAX_ROW_LIMIT) + stripped[end:]
    return stripped


def _normalize_limit(cypher: str, row_limit: int) -> str | None:
    """Inject a missing LIMIT, or cap an existing one, independently on
    every top-level UNION branch. Returns None when any branch carries a
    LIMIT clause this validator cannot safely normalize (F-2.1-B09), so
    the caller rejects the query instead of executing a corrupted one.
    """
    parts = _split_on_union(cypher)
    normalized_parts: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            normalized_parts.append(part.strip())
        else:
            normalized_branch = _normalize_branch_limit(part, row_limit)
            if normalized_branch is None:
                return None
            normalized_parts.append(normalized_branch)
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
    if normalized is None:
        return ValidationResult(
            ok=False,
            reason=REASON_UNSAFE_LIMIT_CLAUSE,
            message=(
                "Generated Cypher has a LIMIT clause that is not a single "
                "plain integer with nothing but the query's own results "
                "following it. A parameterized LIMIT, or a LIMIT followed "
                "by SKIP in the wrong order, cannot be verified or capped "
                "by this validator. Retry generation with a plain integer "
                "LIMIT, or omit LIMIT entirely and let the row cap be "
                "injected."
            ),
            normalized_cypher=None,
        )

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
