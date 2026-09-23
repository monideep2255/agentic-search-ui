"""Does the graph actually hold phenotype edges for Marfan syndrome?

Worker D's finding, 2026-09-23: G-022 ("What phenotypic features are associated
with Marfan syndrome?") refused "no evidence" on all three consistency passes,
while the graph holds 6,076,735 `has_phenotype` rows. That is either a real
shipped defect, a question the product should answer and does not, or the edges
simply are not there for this disease. One read-only probe settles it, and a
guess does not.

READ ONLY. Layer 1 is read-only at the connection level, so nothing here can
write even if it tried.

TWO THINGS THIS PROBE LEARNED THE HARD WAY, kept because they cost time and
will cost the next person the same time:

- Every probe written with values inline was REFUSED, status 422
  `cypher_rejected`, "appears to bind a literal value directly instead of a
  parameter", and a second family was refused for untyped relationship patterns
  because AGE would compile them to a scan across all 14 edge tables. Both are
  the service's own validator working as designed, on a caller holding a
  read-only credential with no bad intent.
- `execute_cypher` returns `(rows, total_available)`, and its `as_clause`
  defaults to `"(result agtype)"`, which declares exactly ONE returned column.
  A `RETURN a AS x, b AS y` against that default fails server side with
  `DatatypeMismatch`, which surfaces as a 502 `graph_unavailable` and reads
  exactly like the graph being down. It is not. Every probe below returns a
  single column, or passes a matching `as_clause`.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_overnight/probe_g022.py
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

MARFAN_PATTERN = "(?i).*marfan.*"
FBN1 = "NCBIGene:2200"

PROBES: list[tuple[str, str, dict[str, object] | None]] = [
    (
        "Is there a Marfan disease vertex at all",
        "MATCH (d:Disease) WHERE d.name =~ $pattern RETURN d AS result LIMIT 10",
        {"pattern": MARFAN_PATTERN},
    ),
    (
        "Does FBN1 exist as a Gene vertex",
        "MATCH (g:Gene {id: $gene}) RETURN g AS result LIMIT 5",
        {"gene": FBN1},
    ),
    (
        "has_phenotype edges OUT of any Marfan disease vertex",
        ("MATCH (d:Disease)-[:has_phenotype]->(p) WHERE d.name =~ $pattern "
        "RETURN p AS result LIMIT 25"),
        {"pattern": MARFAN_PATTERN},
    ),
    (
        "has_phenotype edges out of FBN1 itself",
        "MATCH (g:Gene {id: $gene})-[:has_phenotype]->(p) RETURN p AS result LIMIT 25",
        {"gene": FBN1},
    ),
    (
        "gene_associated_with_condition out of FBN1, the gene-to-disease edge",
        ("MATCH (g:Gene {id: $gene})-[:gene_associated_with_condition]->(d) "
        "RETURN d AS result LIMIT 25"),
        {"gene": FBN1},
    ),
    (
        "ANY Disease vertex carrying has_phenotype, proving the edge is reachable at all",
        "MATCH (d:Disease)-[:has_phenotype]->(p) RETURN d AS result LIMIT 5",
        None,
    ),
    (
        "PhenotypicFeature vertices whose name mentions Marfan",
        "MATCH (p:PhenotypicFeature) WHERE p.name =~ $pattern RETURN p AS result LIMIT 10",
        {"pattern": MARFAN_PATTERN},
    ),
]


def _describe(value: object) -> str:
    parsed = parse_agtype(value)
    if isinstance(parsed, dict):
        props = parsed.get("properties", parsed)
        if isinstance(props, dict):
            keep = {k: props[k] for k in ("id", "name", "category") if k in props}
            return str(keep or props)
    return str(parsed)[:200]


def main() -> None:
    for title, cypher, params in PROBES:
        print("=" * 78)
        print(title)
        print("-" * 78)
        try:
            rows, total = execute_cypher(cypher, params)
        except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
            print(f"  FAILED: {type(exc).__name__}: {str(exc)[:260]}")
            continue
        if not rows:
            print("  ZERO ROWS")
            continue
        print(f"  {len(rows)} row(s), total_available={total}")
        for row in rows[:25]:
            print("    " + _describe(row.get("result")))


if __name__ == "__main__":
    main()
