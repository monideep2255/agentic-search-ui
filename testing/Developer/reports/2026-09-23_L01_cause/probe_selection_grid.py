"""Which template does each plausible Think output choose, and how many rows does it return?

L-01's row count moved between 100, 12 and 0 for one question. The graph is
deterministic (see probe_template_counts.py), so the query changed. The query
is chosen by `select_template`, whose inputs are all produced by a model:
`query_intent` (the rewritten question), `query_class` (one of five), and
`entity_bindings` (which CURIEs Think resolved). This probe holds the question
fixed and varies only those model-produced inputs, then runs whatever template
comes out against the live graph.

If the measured counts fall out of ordinary variation in those inputs, the
cause of L-01 is upstream of the graph and upstream of this tool's execution
path.

READ ONLY.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_selection_grid.py
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

from system_03_search_agent.tools.cypher_query import (
    _build_as_clause,
    _build_params,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import select_template
from system_03_search_agent.tools.cypher_validator import validate_cypher
from system_03_search_agent.tools.graph_connection import execute_cypher

HNF1A = "NCBIGene:6927"
BRCA1 = "NCBIGene:672"
ROW_LIMIT = 100

CLASSES = ["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"]

# Rewritings of the two measured questions that a Think step could plausibly
# produce for the SAME user question. None of these is exotic; each is a
# phrasing of the identical request.
INTENTS: dict[str, list[str]] = {
    "HNF1A": [
        "What diseases are caused by variants in the HNF1A gene?",
        "diseases caused by variants in HNF1A",
        "diseases associated with HNF1A",
        "HNF1A gene disease associations",
        "HNF1A variants and their clinical significance",
        "What is known about the HNF1A gene?",
    ],
    "BRCA1": [
        "Which diseases are associated with BRCA1?",
        "diseases associated with BRCA1",
        "BRCA1 disease associations",
        "What diseases are caused by variants in BRCA1?",
        "What is known about the BRCA1 gene?",
    ],
}
CURIES = {"HNF1A": HNF1A, "BRCA1": BRCA1}


def run_template(cypher: str, bindings: dict[str, str]) -> str:
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
        return f"{type(exc).__name__}"
    return f"{len(rows)} rows"


def main() -> int:
    counts: dict[str, str] = {}
    for gene, intents in INTENTS.items():
        bindings = {"e_one": CURIES[gene]}
        print(f"=== {gene} ({bindings['e_one']}) ===")
        for intent in intents:
            row: list[str] = []
            for klass in CLASSES:
                tool_input = CypherQueryInput(
                    query_intent=intent, query_class=klass, target_entities=[]
                )
                template = select_template(tool_input, bindings)
                if template is None:
                    row.append(f"{klass}=MODEL PATH")
                    continue
                # The cache key MUST carry the bound CURIE. The Cypher text is
                # identical for two genes (both bind $e_one), so a key on the
                # text alone made the second gene reuse the first gene's count.
                # That bug was in this probe's first run and is fixed here.
                key = template.name + "|" + template.cypher + "|" + bindings["e_one"]
                if key not in counts:
                    counts[key] = run_template(template.cypher, bindings)
                    if template.fallback is not None:
                        fb_key = (
                            template.fallback.name
                            + "|"
                            + template.fallback.cypher
                            + "|"
                            + bindings["e_one"]
                        )
                        if fb_key not in counts:
                            counts[fb_key] = run_template(template.fallback.cypher, bindings)
                row.append(f"{klass}={template.name}:{counts[key]}")
            print(f"  {intent!r}")
            for item in row:
                print(f"      {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
