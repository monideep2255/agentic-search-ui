"""Is the graph nondeterministic, or is the QUERY different run to run?

L-01 says the same question returned 100 Layer 1 rows on most runs, 12 on two
and 0 on one, with no error anywhere. Two candidate causes: the graph answers
the same query differently under load, or the agent sends a different query.

This probe settles the first half. It takes every template `select_template`
can choose for the two measured questions, runs each one through the tool's
OWN validate / bind / execute path, repeatedly, and prints the row count each
time. A count that never moves across repeats rules the graph out.

READ ONLY. Layer 1 is read-only at the connection level.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_template_counts.py [repeats]
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path("src").resolve()))

for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.tools.cypher_query import (
    _build_as_clause,
    _build_params,
)
from system_03_search_agent.tools.cypher_validator import validate_cypher
from system_03_search_agent.tools.graph_connection import execute_cypher

HNF1A = "NCBIGene:6927"
BRCA1 = "NCBIGene:672"

# The three templates select_template can reach for the two measured
# questions, written out here exactly as cypher_templates builds them, so
# this probe stays readable and does not depend on reconstructing a
# CypherTemplate object. Every value is a named parameter.
GENE_VARIANT_DISEASES = (
    "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e_one}) "
    "MATCH (v)-[:has_phenotype]->(x:Disease) "
    "WITH v, collect(DISTINCT x) AS xs "
    "RETURN v, xs ORDER BY v.id"
)
GENE_DISEASES_HOP = (
    "MATCH (a:Gene {id: $e_one})-[:gene_associated_with_condition]->(x:Disease) "
    "RETURN a, x ORDER BY x.id"
)
GENE_RECORD = "MATCH (a:Gene {id: $e_one}) RETURN a"

CASES: list[tuple[str, str, dict[str, str]]] = [
    ("HNF1A gene_variant_diseases_one", GENE_VARIANT_DISEASES, {"e_one": HNF1A}),
    ("HNF1A gene_diseases_one (hop)", GENE_DISEASES_HOP, {"e_one": HNF1A}),
    ("HNF1A gene record", GENE_RECORD, {"e_one": HNF1A}),
    ("BRCA1 gene_variant_diseases_one", GENE_VARIANT_DISEASES, {"e_one": BRCA1}),
    ("BRCA1 gene_diseases_one (hop)", GENE_DISEASES_HOP, {"e_one": BRCA1}),
    ("BRCA1 gene record", GENE_RECORD, {"e_one": BRCA1}),
]

ROW_LIMIT = 100


def main() -> int:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    for label, cypher, bindings in CASES:
        validation = validate_cypher(cypher, ROW_LIMIT)
        if not validation.ok or validation.normalized_cypher is None:
            print(f"{label}: REJECTED by validate_cypher: {validation.message}")
            continue
        normalized = validation.normalized_cypher
        params = _build_params(normalized, bindings)
        as_clause = _build_as_clause(normalized)
        counts: list[str] = []
        for _ in range(repeats):
            started = time.monotonic()
            try:
                rows, total = execute_cypher(
                    normalized,
                    params=params,
                    row_limit=ROW_LIMIT,
                    timeout_s=30.0,
                    as_clause=as_clause,
                )
                counts.append(f"{len(rows)}/{total} in {time.monotonic() - started:.1f}s")
            except Exception as exc:  # noqa: BLE001 - a probe reports every outcome
                counts.append(f"{type(exc).__name__} in {time.monotonic() - started:.1f}s")
        print(f"{label}\n    as_clause={as_clause}\n    {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
