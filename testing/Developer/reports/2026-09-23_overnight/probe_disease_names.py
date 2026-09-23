"""What is actually stored on a Disease vertex, and who carries has_phenotype?

Round two, 2026-09-23. Round one (`probe_g022.py`) was aimed at G-022 and found
something larger by accident, so this probe exists to confirm or kill it before
a word of it is written down as fact.

What round one returned, and why it needs confirming rather than believing:

- No Disease vertex anywhere matches the name "marfan". Zero rows.
- No Disease vertex anywhere carries an outgoing `has_phenotype` edge. Zero
  rows with NO filter at all, which is the strong form of the claim.
- FBN1 does resolve, as `NCBIGene:2200`, "fibrillin 1", so the graph is
  reachable and the gene half is fine.
- FBN1 has 8 `gene_associated_with_condition` edges to MedGen diseases, and
  their `name` property read "GARD", "MONDO", "MedGen". Those are SOURCE
  VOCABULARY names, not disease names.

The last one is the reason for this file. If a Disease vertex really carries its
source in `name`, then no disease lookup by name can ever match in this graph,
and that is a much bigger fact than one golden row failing. It is also exactly
the kind of thing a summarising helper can fabricate, since round one's printer
kept only three keys. So this probe dumps whole property bags and counts label
pairs instead of trusting a filtered view.

READ ONLY, and every value travels as a parameter.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py
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

FBN1 = "NCBIGene:2200"
MARFAN_MEDGEN = "MedGen:C0024796"

PROBES: list[tuple[str, str, dict[str, object] | None]] = [
    (
        "FULL property bag of the 8 diseases FBN1 is associated with",
        ("MATCH (g:Gene {id: $gene})-[:gene_associated_with_condition]->(d) "
        "RETURN d AS result LIMIT 8"),
        {"gene": FBN1},
    ),
    (
        "FULL property bag of one named MedGen disease, fetched by id",
        "MATCH (d {id: $disease}) RETURN d AS result LIMIT 3",
        {"disease": MARFAN_MEDGEN},
    ),
    (
        "FULL property bag of any three Disease vertices at all",
        "MATCH (d:Disease) RETURN d AS result LIMIT 3",
        None,
    ),
    (
        "Do ANY Disease vertices have a name that is not a source vocabulary",
        "MATCH (d:Disease) WHERE d.name =~ $pattern RETURN d AS result LIMIT 10",
        {"pattern": "(?i).*syndrome.*"},
    ),
    (
        "has_phenotype: what is on the FROM side, sampled",
        "MATCH (a)-[:has_phenotype]->(b) RETURN a AS result LIMIT 5",
        None,
    ),
    (
        "has_phenotype: what is on the TO side, sampled",
        "MATCH (a)-[:has_phenotype]->(b) RETURN b AS result LIMIT 5",
        None,
    ),
    (
        "Does PhenotypicFeature exist as a label at all",
        "MATCH (p:PhenotypicFeature) RETURN p AS result LIMIT 5",
        None,
    ),
]


def _full(value: object) -> str:
    parsed = parse_agtype(value)
    if isinstance(parsed, dict):
        label = parsed.get("label")
        props = parsed.get("properties")
        if isinstance(props, dict):
            return f"label={label!r} props={props}"
    return str(parsed)[:400]


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
        for row in rows[:8]:
            print("    " + _full(row.get("result")))


if __name__ == "__main__":
    main()
