"""ONE read-only Layer 1 query through the repository's own execute_cypher.

Measures the ortholog traversal shape that graph_connection.py's F-2.1-C15
note records as what the plan model writes for a BRCA1 (NCBIGene:672)
question. Read-only, bounded by LIMIT, one execution.
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

from system_03_search_agent.tools.graph_connection import execute_cypher

CYPHER = (
    "MATCH (g:Gene {id: $curie})-[:orthologous_to]->(o:Gene) "
    "RETURN DISTINCT o LIMIT 100"
)
print("transport:", "HTTPS" if os.environ.get("GRAPH_QUERY_URL") else "psycopg2")
print("cypher:", CYPHER)
t0 = time.monotonic()
try:
    rows, total = execute_cypher(CYPHER, {"curie": "NCBIGene:672"}, row_limit=100, timeout_s=30.0)
    print(f"elapsed_s={time.monotonic()-t0:.3f} rows={len(rows)} total={total}")
except Exception as exc:  # noqa: BLE001 - one-off probe, every failure is printed
    print(f"elapsed_s={time.monotonic()-t0:.3f} ERROR {type(exc).__name__}: {str(exc)[:400]}")
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
from system_03_search_agent.tools.graph_connection import execute_cypher

CYPHER = ("MATCH (g:Gene {id: $curie})-[:orthologous_to]->(o:Gene) "
          "RETURN count(DISTINCT o) AS n LIMIT 1")
print("cypher:", CYPHER)
t0 = time.monotonic()
try:
    rows, total = execute_cypher(CYPHER, {"curie": "NCBIGene:672"}, row_limit=1, timeout_s=30.0)
    print(f"elapsed_s={time.monotonic()-t0:.3f} rows={rows}")
except Exception as exc:  # noqa: BLE001 - one-off probe, every failure is printed
    print(f"elapsed_s={time.monotonic()-t0:.3f} {type(exc).__name__}: {str(exc)[:300]}")
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
from system_03_search_agent.tools.graph_connection import execute_cypher

# gene_record_one, exactly as _record_template builds it, LIMIT added by the validator.
CYPHER = "MATCH (a:Gene {id: $curie}) RETURN a LIMIT 100"
print("cypher:", CYPHER)
t0 = time.monotonic()
rows, total = execute_cypher(CYPHER, {"curie": "NCBIGene:672"}, row_limit=100, timeout_s=30.0)
print(f"elapsed_s={time.monotonic()-t0:.3f} rows={len(rows)} total={total}")
