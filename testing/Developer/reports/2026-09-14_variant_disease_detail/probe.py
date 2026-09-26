"""Read-only probes: does the graph link a SequenceVariant to a Disease?

Every query goes through the repository's own `graph_connection.execute_cypher`
with bound parameters. Nothing is written. Output is JSONL, one line per
probe, with the query, params, row count, elapsed and sample rows.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path("<repo-root>")
sys.path.insert(0, str(REPO / "src"))

for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.tools.graph_connection import execute_cypher

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("probe_out.jsonl")
HNF1A = "NCBIGene:6927"
GCK = "NCBIGene:2645"


def _as_clause(cypher: str) -> str:
    tail = cypher.rsplit("RETURN", 1)[1]
    tail = re.split(r"\bORDER\s+BY\b", tail)[0]
    n = tail.count(",") + 1
    return "(" + ", ".join(f"c{i} agtype" for i in range(n)) + ")"


def probe(name: str, cypher: str, params: dict | None = None, row_limit: int = 20, sample: int = 5):
    started = time.monotonic()
    try:
        rows, total = execute_cypher(cypher, params, row_limit=row_limit, timeout_s=30.0,
                                     as_clause=_as_clause(cypher))
        elapsed = time.monotonic() - started
        record = {
            "probe": name,
            "cypher": cypher,
            "params": params or {},
            "rows": len(rows),
            "total_available": total,
            "elapsed_s": round(elapsed, 3),
            "sample": [json.loads(json.dumps(r, default=str)) for r in rows[:sample]],
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started
        record = {
            "probe": name,
            "cypher": cypher,
            "params": params or {},
            "error": f"{type(exc).__name__}: {exc}"[:400],
            "elapsed_s": round(elapsed, 3),
        }
    with OUT.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    short = {k: v for k, v in record.items() if k not in ("sample", "cypher", "params")}
    print(json.dumps(short))
    if "sample" in record:
        for r in record["sample"][:3]:
            print("   ", json.dumps(r)[:400])
    return record


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    if which in ("all", "a"):
        probe("A1 hnf1a variants sample", (
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
            "RETURN v ORDER BY v.id"), {"g": HNF1A}, row_limit=5)
        probe("A2 hnf1a variant count", (
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
            "RETURN count(v) AS n"), {"g": HNF1A}, row_limit=1)
        probe("A3 hnf1a gene diseases", (
            "MATCH (g:Gene {id: $g})-[:gene_associated_with_condition]->(d:Disease) "
            "RETURN d.id, d.name ORDER BY d.id"), {"g": HNF1A}, row_limit=20, sample=20)
    if which in ("all", "b"):
        for label in ("close_match", "exact_match", "has_phenotype", "gene_associated_with_condition"):
            probe(f"B out {label} from hnf1a variants", (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
                f"MATCH (v)-[:{label}]->(n) RETURN v.id, v.name, labels(n) AS l, n.id, n.name "
                "ORDER BY v.id"), {"g": HNF1A}, row_limit=10, sample=10)
            probe(f"B in {label} to hnf1a variants", (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
                f"MATCH (n)-[:{label}]->(v) RETURN v.id, v.name, labels(n) AS l, n.id, n.name "
                "ORDER BY v.id"), {"g": HNF1A}, row_limit=10, sample=10)
    if which in ("all", "c"):
        probe("C1 mody disease names", (
            "MATCH (d:Disease) WHERE d.name =~ $pat RETURN d.id, d.name ORDER BY d.id"),
            {"pat": "(?i).*maturity-onset diabetes.*"}, row_limit=30, sample=30)
        probe("C2 mody genes via name pattern", (
            "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) WHERE d.name =~ $pat "
            "RETURN g.id, g.name, d.id, d.name ORDER BY g.id, d.id"),
            {"pat": "(?i).*maturity-onset diabetes.*"}, row_limit=30, sample=30)
    if which in ("all", "d"):
        probe("D1 any out edge from 20 hnf1a variants (untyped)", (
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
            "WITH v ORDER BY v.id LIMIT 20 MATCH (v)-[r]->(n) "
            "RETURN type(r) AS t, labels(n) AS l, count(*) AS n ORDER BY t"),
            {"g": HNF1A}, row_limit=20, sample=20)
        probe("D2 any in edge to 20 hnf1a variants (untyped)", (
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
            "WITH v ORDER BY v.id LIMIT 20 MATCH (n)-[r]->(v) "
            "RETURN type(r) AS t, labels(n) AS l, count(*) AS n ORDER BY t"),
            {"g": HNF1A}, row_limit=20, sample=20)
    if which in ("all", "e"):
        probe("E1 gck variants sample", (
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $g}) "
            "RETURN v ORDER BY v.id"), {"g": GCK}, row_limit=3)
        probe("E2 gck gene diseases", (
            "MATCH (g:Gene {id: $g})-[:gene_associated_with_condition]->(d:Disease) "
            "RETURN d.id, d.name ORDER BY d.id"), {"g": GCK}, row_limit=20, sample=20)
