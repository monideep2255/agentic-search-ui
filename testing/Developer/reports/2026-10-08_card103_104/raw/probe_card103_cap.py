"""Card 103, second probe: could the 25-id MedGen lookup cap leave a cell blank?

READ ONLY. Runs the repository's own `gene_variant_diseases_one` template
text for HNF1A (NCBIGene:6927) through `execute_cypher`, parameters bound,
and counts the distinct Disease CURIEs the first N variant rows fold, after
`MAX_FOLD_ITEMS`. Usage as `probe_card103_graph.py`.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("src").resolve()))
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.cypher_templates import MAX_FOLD_ITEMS
from system_03_search_agent.tools.graph_connection import execute_cypher

CYPHER = (
    "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene}) "
    "MATCH (v)-[:has_phenotype]->(d:Disease) "
    "WITH v, collect(DISTINCT d.id) AS ds "
    "RETURN {variant: v.id, diseases: ds} AS result ORDER BY v.id"
)
rows, total = execute_cypher(CYPHER, {"gene": "NCBIGene:6927"}, row_limit=100)
folded = []
for row in rows:
    parsed = parse_agtype(row.get("result"))
    if isinstance(parsed, dict):
        folded.append(sorted(str(d) for d in parsed.get("diseases") or [])[:MAX_FOLD_ITEMS])
print("rows", len(rows), "total_available", total)
for n in (38, 50, 100):
    ids = {d for ds in folded[:n] for d in ds}
    print(f"first {n} variant rows: {len(ids)} distinct condition CURIEs (lookup cap 25)")
