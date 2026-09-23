"""Map every row count L-01 measured onto the template that produces it.

The 2026-09-21 run measured these Layer 1 row counts for two questions:
HNF1A 100, 12 and 0 on the unstable call and 25 on the stable one; BRCA1 4
and 8 on the unstable call and 40 on the stable one. probe_selection_grid.py
already matched HNF1A's 100 and BRCA1's 4. This probe runs every remaining
template a Gene or Disease anchor can reach, for both genes and for the
diseases those genes actually link to, and prints the count each returns, so
every measured number is either accounted for or explicitly is not.

READ ONLY.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_all_shapes.py
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
from system_03_search_agent.tools.cypher_query import (
    _build_as_clause,
    _build_params,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import select_template
from system_03_search_agent.tools.cypher_validator import validate_cypher
from system_03_search_agent.tools.graph_connection import execute_cypher

GENES = {"HNF1A": "NCBIGene:6927", "BRCA1": "NCBIGene:672"}
ROW_LIMIT = 100

# One question per Gene shape, phrased the way a Think rewrite plausibly
# would be, so select_template reaches each shape through its real path.
SHAPE_QUESTIONS = [
    ("diseases", "diseases associated with {sym}"),
    ("variants", "variants in {sym}"),
    ("orthologs", "orthologs of {sym}"),
    ("processes", "biological processes {sym} participates in"),
    ("activities", "molecular activities of {sym}"),
    ("components", "cellular components where {sym} is located"),
    ("taxon", "what taxon is {sym} from"),
    ("articles", "articles mentioning {sym}"),
    ("variant_diseases", "diseases caused by variants in {sym}"),
    ("record", "what is known about the {sym} gene"),
    ("count_variants", "how many variants are in {sym}"),
    ("count_diseases", "how many diseases are associated with {sym}"),
]


def run(cypher: str, bindings: dict[str, str]) -> str:
    validation = validate_cypher(cypher, ROW_LIMIT)
    if not validation.ok or validation.normalized_cypher is None:
        return f"REJECTED: {validation.message}"
    normalized = validation.normalized_cypher
    try:
        rows, _total = execute_cypher(
            normalized,
            params=_build_params(normalized, bindings),
            row_limit=ROW_LIMIT,
            timeout_s=30.0,
            as_clause=_build_as_clause(normalized),
        )
    except Exception as exc:  # noqa: BLE001 - a probe reports every outcome
        return type(exc).__name__
    return f"{len(rows)} rows"


def linked_disease_ids(gene_curie: str) -> list[str]:
    """The Disease CURIEs this gene links to through the gene edge."""
    cypher = (
        "MATCH (a:Gene {id: $e_one})-[:gene_associated_with_condition]->(x:Disease) "
        "RETURN x AS result ORDER BY x.id"
    )
    validation = validate_cypher(cypher, ROW_LIMIT)
    normalized = validation.normalized_cypher or cypher
    rows, _ = execute_cypher(
        normalized,
        params={"e_one": gene_curie},
        row_limit=ROW_LIMIT,
        timeout_s=30.0,
        as_clause="(result agtype)",
    )
    ids: list[str] = []
    for row in rows:
        parsed = parse_agtype(row["result"])
        if isinstance(parsed, dict):
            props = parsed.get("properties") or {}
            curie = props.get("id")
            if isinstance(curie, str):
                ids.append(curie)
    return ids


def main() -> int:
    for symbol, curie in GENES.items():
        print(f"=== {symbol} ({curie}) gene-anchored shapes ===")
        bindings = {"e_one": curie}
        for shape, pattern in SHAPE_QUESTIONS:
            question = pattern.format(sym=symbol)
            tool_input = CypherQueryInput(
                query_intent=question, query_class="single_hop", target_entities=[]
            )
            template = select_template(tool_input, bindings)
            if template is None:
                print(f"  {shape:18s} MODEL PATH")
                continue
            print(f"  {shape:18s} {template.name:28s} {run(template.cypher, bindings)}")

        diseases = linked_disease_ids(curie)
        print(f"--- {symbol} linked diseases: {diseases} ---")
        for disease in diseases:
            mixed_bindings = {"e_one": curie, "e_two": disease}
            tool_input = CypherQueryInput(
                query_intent=f"link between {symbol} and this disease",
                query_class="single_hop",
                target_entities=[],
            )
            template = select_template(tool_input, mixed_bindings)
            if template is None:
                print(f"  mixed {disease:22s} MODEL PATH")
                continue
            print(
                f"  mixed {disease:22s} {template.name:28s} "
                f"{run(template.cypher, mixed_bindings)}"
            )
            # The disease anchored on its own, which is the other call the
            # plan step can issue for the same question.
            solo = {"e_one": disease}
            d_input = CypherQueryInput(
                query_intent="genes associated with this disease",
                query_class="single_hop",
                target_entities=[],
            )
            d_template = select_template(d_input, solo)
            if d_template is not None:
                print(
                    f"        disease genes {d_template.name:22s} "
                    f"{run(d_template.cypher, solo)}"
                )
                if d_template.fallback is not None:
                    print(
                        f"        fallback      {d_template.fallback.name:22s} "
                        f"{run(d_template.fallback.cypher, solo)}"
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
