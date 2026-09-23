"""Is PhenotypicFeature reachable from anywhere in the graph?

Worker F removed the dead `("Disease", "phenotypes")` template and corrected
`EDGE_ENDPOINTS["has_phenotype"]` to its measured pair. That turned
`test_schema_slice.py::test_build_schema_slice_lookup_stays_bounded_but_reaches_two_hops`
red, because it asserted PhenotypicFeature is reachable two hops from Gene via
Disease, which was true only because of the constant that was wrong.

Before editing a red test I have to establish which of three things is true
(`.claude/rules/goal-contracts.md`): the subject is wrong, the check is wrong, or
both are right about different things. Editing a test so a check passes, when the
test was right, is the same failed run as weakening the check.

So: does ANY edge reach a PhenotypicFeature vertex? If nothing does, the label is
orphaned, the assertion was never describing the real graph, and the check is the
thing that is wrong. If something does reach it, F's removal needs revisiting and
that is a much more serious finding.

READ ONLY, every value a parameter, every relationship labelled.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_overnight/probe_phenotype_reachability.py
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("src").resolve()))

for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.graph_connection import execute_cypher
from system_03_search_agent.tools.graph_schema_constants import (
    EDGE_LABELS,
)


def _full(value: object) -> str:
    parsed = parse_agtype(value)
    if isinstance(parsed, dict):
        props = parsed.get("properties")
        if isinstance(props, dict):
            return str({k: props.get(k) for k in ("id", "name", "source") if k in props})
    return str(parsed)[:200]


def main() -> None:
    print("=" * 78)
    print("PhenotypicFeature vertices exist at all")
    print("-" * 78)
    rows, _total = execute_cypher(
        "MATCH (p:PhenotypicFeature) RETURN p AS result LIMIT 3", None
    )
    for row in rows:
        print("    " + _full(row.get("result")))
    if not rows:
        print("  ZERO ROWS")

    print()
    print("=" * 78)
    print("Every edge label, INCOMING to a PhenotypicFeature")
    print("-" * 78)
    for label in EDGE_LABELS:
        cypher = f"MATCH (a)-[:{label}]->(p:PhenotypicFeature) RETURN p AS result LIMIT 1"
        try:
            rows, _ = execute_cypher(cypher, None)
        except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
            print(f"  {label:<34} FAILED: {str(exc)[:80]}")
            continue
        print(f"  {label:<34} {'ROWS FOUND' if rows else 'zero'}")

    print()
    print("=" * 78)
    print("Every edge label, OUTGOING from a PhenotypicFeature")
    print("-" * 78)
    for label in EDGE_LABELS:
        cypher = f"MATCH (p:PhenotypicFeature)-[:{label}]->(b) RETURN p AS result LIMIT 1"
        try:
            rows, _ = execute_cypher(cypher, None)
        except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
            print(f"  {label:<34} FAILED: {str(exc)[:80]}")
            continue
        print(f"  {label:<34} {'ROWS FOUND' if rows else 'zero'}")


if __name__ == "__main__":
    main()
