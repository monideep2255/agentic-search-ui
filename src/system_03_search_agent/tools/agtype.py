"""AGE agtype text parser (phase 2.1 defect fix, findings F-2.1-A1/F-01/A2).

psycopg2 has no registered typecaster for AGE's `agtype` column type, so
every `agtype` column comes back from the driver as raw text carrying
whatever suffix AGE attached to mark its dynamic type: `{...}::vertex`,
`{...}::edge`, `{...}::path`, or a bare JSON scalar (a quoted string, a
number, `true`, `false`, `null`) with no suffix at all. Nothing upstream of
this module ever parsed that text before this fix:
`cypher_provenance.to_output_row` looked for keys such as `label` and
`curie` at the top level of the raw row dict and found none, because the
value at each column was still this opaque agtype string, not the parsed
dict it assumed. The tool then reported `status: "ok"` over empty, uncited
rows.

This module's only job is turning one agtype column value, whatever shape
it arrives in, into the underlying Python value: a dict for a vertex or an
edge, a list for a path, or a bare scalar for anything else. Malformed
input is handled deterministically and never raises into the caller's
happy path, per this repo's retry-safety gate: a parse failure here must
degrade to "could not parse" for that one value, never crash the whole
query.

Depends on:
    - Nothing beyond the standard library (json, re).

Reads:
    - Nothing.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_provenance (to_output_rows)
    - system_03_search_agent.tools.cypher_query (the true-total count query
      result is itself one bare agtype scalar, parsed the same way)
"""

from __future__ import annotations

import json
import re
from typing import Any

# AGE suffixes its dynamically-typed output with `::vertex`, `::edge`, or
# `::path` after the JSON payload. A bare scalar (a quoted string, a
# number, true, false, null) carries no suffix at all, so this pattern
# matching nothing is itself a valid, expected outcome, not an error.
_TYPE_SUFFIX_PATTERN = re.compile(r"::(vertex|edge|path)\s*$")

VERTEX = "vertex"
EDGE = "edge"
PATH = "path"


def strip_agtype_suffix(text: str) -> tuple[str, str | None]:
    """Split `text` into its JSON payload and its agtype type suffix.

    Args:
        text: the raw agtype wire text, already stripped of surrounding
            whitespace by the caller if that matters to it.

    Returns:
        A tuple of (payload, suffix). `suffix` is one of the module-level
        constants `VERTEX`, `EDGE`, `PATH`, or None when no suffix is
        present, which is the bare-scalar case.
    """
    match = _TYPE_SUFFIX_PATTERN.search(text)
    if match is None:
        return text, None
    return text[: match.start()], match.group(1)


def parse_agtype(value: Any) -> Any:
    """Parse one agtype column value into the Python value it represents.

    Handles every shape AGE emits, in this order:

    - None: returned as-is, the SQL NULL case.
    - A value that is already a dict, list, bool, int, or float: some
      caller (a unit test fixture, or a future upstream step) may hand
      this function pre-parsed data. It is returned unchanged, never
      re-encoded and re-decoded, so a caller that already parsed a value
      never gets it silently mangled by a second pass.
    - A str: the real AGE wire-format case. A trailing `::vertex`,
      `::edge`, or `::path` suffix, if present, is stripped, and the
      remaining text is decoded as JSON. This also covers the bare-scalar
      case (`"a string"`, `42`, `true`, `null`), since those are valid
      JSON on their own with no suffix to strip.

    Never raises. A string that is not valid JSON after suffix-stripping,
    or any other type this function does not recognize, returns None
    rather than propagating a `json.JSONDecodeError` or a `TypeError`, so
    one malformed column value degrades to "could not parse" instead of
    failing the whole row.

    Args:
        value: one raw value read from an `agtype` column, or an
            already-parsed Python value.

    Returns:
        The decoded Python value, or None when `value` is None, empty, or
        could not be parsed.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list, bool, int, float)):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    payload, _suffix = strip_agtype_suffix(stripped)
    payload = payload.strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, ValueError, RecursionError):
        return None


def is_vertex_or_edge(parsed: Any) -> bool:
    """Return True when `parsed` has the shape of an AGE vertex or edge.

    Both vertices and edges are decoded as a dict carrying at least a
    `label` key; an edge additionally carries `start_id` and `end_id`,
    which this function does not require, since a caller that needs to
    tell the two apart reads those keys directly off `parsed`.
    """
    return isinstance(parsed, dict) and "label" in parsed
