"""Do OntologyClass vertices carry real MeSH terms, or identifiers?

Worker D, 2026-09-23, found `{"id": "MeSH:D000595", "name": "[MeSH] D000595"}`
in a probe file already in this repository and flagged it as UNVERIFIED. It
matters because golden question G-019, "What MeSH terms are assigned to PMID
11237011?", returns 26 Layer 1 rows and answers two passes of three, so every
instrument in this project reads it as working. If the names are identifiers,
the person asking gets identifiers where terms should be, and that is the exact
shape of the disease-name defect one label over.

This settles it graph-wide rather than from one vertex, the same way the
Disease check was settled: if no OntologyClass name anywhere contains a lowercase
letter run that looks like a word, the field is identifiers everywhere.

READ ONLY, every value a parameter, every relationship labelled.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_overnight/probe_ontology_names.py
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

PMID_11237011 = "PMID:11237011"

PROBES: list[tuple[str, str, dict[str, object] | None]] = [
    (
        "Sample any five OntologyClass vertices",
        "MATCH (o:OntologyClass) RETURN o AS result LIMIT 5",
        None,
    ),
    (
        "The MeSH terms G-019 actually reaches, through has_mesh_annotation",
        ("MATCH (a:Article {id: $pmid})-[:has_mesh_annotation]->(o) "
        "RETURN o AS result LIMIT 26"),
        {"pmid": PMID_11237011},
    ),
    (
        "Does ANY OntologyClass name contain a spelled-out word (lowercase run of 4+)",
        "MATCH (o:OntologyClass) WHERE o.name =~ $pattern RETURN o AS result LIMIT 10",
        {"pattern": ".*[a-z]{4,}.*"},
    ),
    (
        "Does ANY OntologyClass name contain 'neoplasm', a common MeSH word",
        "MATCH (o:OntologyClass) WHERE o.name =~ $pattern RETURN o AS result LIMIT 10",
        {"pattern": "(?i).*neoplasm.*"},
    ),
    (
        "Control: Article vertices, to show a name field that IS populated",
        "MATCH (a:Article {id: $pmid}) RETURN a AS result LIMIT 1",
        {"pmid": PMID_11237011},
    ),
]


def _full(value: object) -> str:
    parsed = parse_agtype(value)
    if isinstance(parsed, dict):
        props = parsed.get("properties")
        if isinstance(props, dict):
            keep = {k: props.get(k) for k in ("id", "name", "source") if k in props}
            return str(keep)
    return str(parsed)[:300]


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
        for row in rows[:26]:
            print("    " + _full(row.get("result")))


if __name__ == "__main__":
    main()
