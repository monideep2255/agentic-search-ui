"""Read-only Layer 1 timing probes through the repository's own execute_cypher.

What the graph answers, and how fast, for the shapes fix-plan item 1 chooses
between. Each query runs once, bounded by LIMIT and the tool's 30-second
timeout, through the validator first so what is timed is what the tool would
run. Results as measured on 2026-09-22 are in `findings.md`; re-run from the
repository root with the graph credentials in `.env`.
"""
import os
import pathlib
import sys
import time

root = pathlib.Path(".")
sys.path.insert(0, str(root / "src"))
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from system_03_search_agent.tools.cypher_query import _build_as_clause
from system_03_search_agent.tools.cypher_validator import validate_cypher
from system_03_search_agent.tools.graph_connection import execute_cypher

MLH1, MSH2, TP53 = "NCBIGene:4292", "NCBIGene:4436", "NCBIGene:7157"
COLORECTAL = "MedGen:C0346629"  # the concept Think resolved for "colorectal cancer" on every G-033 pass
TWO = {"g1": MLH1, "g2": MSH2}
EIGHT = {
    f"d{i}": d
    for i, d in enumerate(
        [
            "MedGen:C1321489", "MedGen:C0346629", "MedGen:C0205770", "MedGen:C0346153",
            "MedGen:C0585442", "MedGen:C1835398", "MedGen:C1859972", "MedGen:C2239176",
        ]
    )
}
PROBES: list[tuple[str, str, dict[str, str]]] = [
    # The question's own search for G-033, three candidate shapes.
    (
        "genes_diseases_many (chosen for G-033)",
        (
            "MATCH (a:Gene)-[:gene_associated_with_condition]->(x:Disease) "
            "WHERE a.id IN [$g1, $g2] RETURN a, x ORDER BY a.id, x.id"
        ),
        TWO,
    ),
    (
        "link narrowed to the bound disease (rejected: zero rows)",
        (
            "MATCH (a:Gene)-[:gene_associated_with_condition]->(x:Disease {id: $d}) "
            "WHERE a.id IN [$g1, $g2] RETURN x"
        ),
        {**TWO, "d": COLORECTAL},
    ),
    ("tp53 diseases (one gene)", "MATCH (a:Gene {id: $g})-[:gene_associated_with_condition]->(x:Disease) RETURN x ORDER BY x.id", {"g": TP53}),
    # The several-record forms: only the inline match uses the id index.
    ("record, inline one", "MATCH (a:Gene {id: $g1}) RETURN a", {"g1": MLH1}),
    ("record, IN list of one (times out)", "MATCH (a:Gene) WHERE a.id IN [$g1] RETURN a ORDER BY a.id", {"g1": MLH1}),
    ("record, IN list of two (times out; the old many form)", "MATCH (a:Gene) WHERE a.id IN [$g1, $g2] RETURN a ORDER BY a.id", TWO),
    ("record, OR of two (times out)", "MATCH (a:Gene) WHERE a.id = $g1 OR a.id = $g2 RETURN a ORDER BY a.id", TWO),
    ("record, UNWIND then inline (fast, but fails the anchoring gate)", "UNWIND [$g1, $g2] AS gid MATCH (a:Gene {id: gid}) RETURN a ORDER BY a.id", TWO),
    (
        "record, UNION ALL of inline matches (chosen)",
        "MATCH (a:Gene {id: $g1}) RETURN a ORDER BY a.id UNION ALL MATCH (a:Gene {id: $g2}) RETURN a ORDER BY a.id",
        TWO,
    ),
    (
        "record, UNION ALL of eight Disease matches",
        " UNION ALL ".join(f"MATCH (a:Disease {{id: ${k}}}) RETURN a ORDER BY a.id" for k in EIGHT),
        EIGHT,
    ),
    (
        "record, IN list of eight Disease ids (fast: the Disease label is small)",
        "MATCH (a:Disease) WHERE a.id IN [" + ", ".join(f"${k}" for k in EIGHT) + "] RETURN a ORDER BY a.id",
        EIGHT,
    ),
]
print("transport:", "HTTPS" if os.environ.get("GRAPH_QUERY_URL") else "psycopg2")
for name, cypher, params in PROBES:
    verdict = validate_cypher(cypher, 100)
    if not verdict.ok:
        print(f"{name}: validator rejected it, {verdict.reason}")
        continue
    normalized = verdict.normalized_cypher or cypher
    started = time.monotonic()
    try:
        rows, total = execute_cypher(
            normalized, params, row_limit=100, timeout_s=30.0, as_clause=_build_as_clause(normalized)
        )
        print(f"{name}: {time.monotonic() - started:.3f} s, rows={len(rows)} total={total}")
    except Exception as exc:  # noqa: BLE001 - one-off probe, every failure is printed
        print(f"{name}: {time.monotonic() - started:.3f} s, {type(exc).__name__}: {str(exc)[:160]}")
