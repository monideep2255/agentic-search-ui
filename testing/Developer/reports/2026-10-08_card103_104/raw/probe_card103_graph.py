"""Card 103: what do the five blank-cell HNF1A variants link to in the graph?

READ ONLY. One MATCH query through the repository's own `execute_cypher`,
every value bound as a parameter, then the repository's own
`resolve_concept_ids` (live NCBI E-utilities, MedGen) for the titles. Never
writes to the graph, never calls the deployed app.

Usage, from the worktree root, naming an environment file that holds the
graph credentials (it is read, never printed):

    <venv>/bin/python testing/Developer/reports/2026-10-08_card103_104/raw/probe_card103_graph.py <path-to-.env>
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("src").resolve()))

env_file = pathlib.Path(sys.argv[1])
for line in env_file.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.synthesis.disease_names import (
    is_placeholder_condition_title,
    resolve_concept_ids,
)
from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.graph_connection import execute_cypher

BLANK = ["ClinVar:1048822", "ClinVar:1051750", "ClinVar:1098821", "ClinVar:1104934", "ClinVar:1105252"]

CYPHER = (
    "MATCH (v:SequenceVariant)-[:has_phenotype]->(d:Disease) "
    "WHERE v.id IN $ids "
    "WITH v, collect(DISTINCT d.id) AS ds "
    "RETURN {variant: v.id, diseases: ds} AS result"
)


async def main() -> None:
    rows, _total = execute_cypher(CYPHER, {"ids": BLANK})
    links: dict[str, list[str]] = {}
    for row in rows:
        parsed = parse_agtype(row.get("result"))
        if isinstance(parsed, dict):
            links[str(parsed.get("variant"))] = sorted(str(d) for d in parsed.get("diseases") or [])
    all_ids = sorted({d for ds in links.values() for d in ds})
    titles = await resolve_concept_ids(all_ids)
    out = {}
    for variant in BLANK:
        ds = links.get(variant, [])
        out[variant] = [
            {
                "curie": d,
                "title": titles.get(d),
                "placeholder": is_placeholder_condition_title(titles.get(d)),
            }
            for d in ds
        ]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
