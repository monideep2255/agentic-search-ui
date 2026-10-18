"""Does the model path draft a different query, and a different row count, each run?

This is L-01's reproduction attempt. Everything else is now ruled out: the
graph answers the same query identically on repeat, the HTTPS transport turns
every failure into a typed error rather than an empty result, and the
execution path never reports a failure as `empty`.

What is left is the query itself. When `select_template` matches nothing, the
tool asks the plan-tier model to write the Cypher. This probe runs that path
on the two measured questions, N times each, and prints the drafted query and
the row count it returns. If the count moves between runs of an identical
question, and especially if any run returns zero, L-01's signature is
reproduced on demand.

Costs real plan-tier model calls, one or two per run. Keep N small.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_model_path_spread.py [runs]
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path("src").resolve()))

for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import select_template

# The model path is reached when `select_template` matches no shape. A Think
# rewrite that keeps the question's meaning but uses none of the eight shape
# keywords (diseases, variants, orthologs, processes, activities, components,
# taxon, articles) does exactly that. `aggregate` is the class that still
# takes the model path with no shape on today's code; before 2026-09-22 a
# shapeless GENE question took it on `single_hop` and `multi_hop` too, which
# is the build L-01 was measured on.
CASES = [
    ("HNF1A", "NCBIGene:6927", "what is the clinical relevance of HNF1A", "aggregate"),
    ("BRCA1", "NCBIGene:672", "what is the clinical relevance of BRCA1", "aggregate"),
]


async def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for symbol, curie, question, klass in CASES:
        print(f"=== {symbol}: {question!r} ({klass}) ===")
        tool_input = CypherQueryInput(
            query_intent=question,
            query_class=klass,
            target_entities=[curie],
            row_limit=100,
        )
        chosen = select_template(tool_input, {"e_x": curie})
        print(f"  select_template on today's code: {chosen.name if chosen else 'MODEL PATH'}")
        for index in range(1, runs + 1):
            harness = Harness(trace_id="l01-" + uuid.uuid4().hex[:8])
            # template=None forces the model path, which is what a question
            # whose Think rewrite matched no shape took before 2026-09-22.
            out = await cypher_query(harness, tool_input)
            print(
                f"  run {index}: status={out.status} row_count={out.row_count} "
                f"template={out.template}"
            )
            print(f"      cypher={out.cypher_executed}")
            if out.error:
                print(f"      error={out.error[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
