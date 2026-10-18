"""Probe every entry in `cypher_templates._HOPS`, plus the non-hop templates,
against the live graph, read only, to establish which can return a row at all.

Worker F, 2026-09-23. Built to answer one question honestly: which of the
roughly eleven hop templates in `tools/cypher_templates.py` are dead (can never
return a row given what the graph actually holds), following the planner's
G-022 finding that (Disease, phenotypes) is dead for two independent reasons.

Every value travels as a parameter. Every relationship names its label. Every
probe returns exactly one column, matching `execute_cypher`'s single-column
`as_clause` default (the second trap named in the brief).

Usage, from the repository root:

    venv/bin/python /path/to/probe_all_templates.py
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

BRCA1 = "NCBIGene:672"
GCK = "NCBIGene:2645"
HNF1A = "NCBIGene:6927"
FBN1 = "NCBIGene:2200"
MARFAN_MEDGEN = "MedGen:C0024796"
MODY_MEDGEN_1 = "MedGen:C0271653"

# (hop key, title, cypher, params)
PROBES: list[tuple[str, str, str, dict[str, object]]] = [
    (
        "Gene/diseases",
        "BRCA1 -[gene_associated_with_condition]-> Disease",
        ("MATCH (a:Gene {id: $g})-[:gene_associated_with_condition]->(x:Disease) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/variants",
        "SequenceVariant -[is_sequence_variant_of]-> HNF1A",
        ("MATCH (x:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $g}) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": HNF1A},
    ),
    (
        "Gene/orthologs",
        "BRCA1 -[orthologous_to]-> Gene",
        ("MATCH (a:Gene {id: $g})-[:orthologous_to]->(x:Gene) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/processes",
        "BRCA1 -[participates_in]-> BiologicalProcess",
        ("MATCH (a:Gene {id: $g})-[:participates_in]->(x:BiologicalProcess) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/activities",
        "BRCA1 -[actively_involved_in]-> MolecularActivity",
        ("MATCH (a:Gene {id: $g})-[:actively_involved_in]->(x:MolecularActivity) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/components",
        "BRCA1 -[located_in]-> CellularComponent",
        ("MATCH (a:Gene {id: $g})-[:located_in]->(x:CellularComponent) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/taxon",
        "BRCA1 -[in_taxon]-> OrganismTaxon",
        ("MATCH (a:Gene {id: $g})-[:in_taxon]->(x:OrganismTaxon) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Gene/articles",
        "BRCA1 -[mentioned_in]-> Article",
        ("MATCH (a:Gene {id: $g})-[:mentioned_in]->(x:Article) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"g": BRCA1},
    ),
    (
        "Disease/genes",
        "Gene -[gene_associated_with_condition]-> FBN1's disease MedGen:C0024796",
        ("MATCH (x:Gene)-[:gene_associated_with_condition]->(a:Disease {id: $d}) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"d": MARFAN_MEDGEN},
    ),
    (
        "Disease/phenotypes",
        "Marfan Disease -[has_phenotype]-> PhenotypicFeature",
        ("MATCH (a:Disease {id: $d})-[:has_phenotype]->(x:PhenotypicFeature) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"d": MARFAN_MEDGEN},
    ),
    (
        "Disease/phenotypes (no filter)",
        "ANY Disease -[has_phenotype]-> PhenotypicFeature, no filter",
        ("MATCH (a:Disease)-[:has_phenotype]->(x:PhenotypicFeature) "
        "RETURN x AS result LIMIT 5"),
        {},
    ),
    (
        "Article/mesh",
        "PMID:10026184 -[has_mesh_annotation]-> OntologyClass",
        ("MATCH (a:Article {id: $p})-[:has_mesh_annotation]->(x:OntologyClass) "
        "RETURN x AS result ORDER BY x.id LIMIT 25"),
        {"p": "PMID:10026184"},
    ),
]


def _describe(value: object) -> str:
    parsed = parse_agtype(value)
    if isinstance(parsed, dict):
        props = parsed.get("properties", parsed)
        if isinstance(props, dict):
            keep = {k: props[k] for k in ("id", "name", "source") if k in props}
            return str(keep or props)
    return str(parsed)[:200]


def main() -> None:
    for key, title, cypher, params in PROBES:
        print("=" * 78)
        print(f"[{key}] {title}")
        print("-" * 78)
        try:
            rows, total = execute_cypher(cypher, params or None)
        except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
            print(f"  FAILED: {type(exc).__name__}: {str(exc)[:260]}")
            continue
        if not rows:
            print("  ZERO ROWS")
            continue
        print(f"  {len(rows)} row(s), total_available={total}")
        for row in rows[:5]:
            print("    " + _describe(row.get("result")))


if __name__ == "__main__":
    main()
