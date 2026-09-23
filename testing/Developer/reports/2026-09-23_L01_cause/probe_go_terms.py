"""Is the stable second Layer 1 call the GO terms context call?

Every measured run carried two Layer 1 calls: one whose row count moved and
one that never did (40 for BRCA1, 25 for HNF1A, on 2026-09-21 and again on
2026-09-23). `core/graph.py`'s `_build_planned_go_terms_call` issues a
code-chosen `gene_go_terms_template` beside the question's own graph call.
If that template returns exactly 40 and 25, the stable call is identified and
only ONE call per run was ever unstable.

READ ONLY.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_go_terms.py
"""
from __future__ import annotations

import asyncio
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
    cypher_query,
    entity_param_bindings,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import (
    gene_go_terms_template,
)

GENES = {"HNF1A": "NCBIGene:6927", "BRCA1": "NCBIGene:672"}


class _NoHarness:
    async def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("the template path must not call a model")


async def main() -> int:
    for symbol, curie in GENES.items():
        bindings = entity_param_bindings([curie])
        [gene_param] = list(bindings)
        template = gene_go_terms_template(gene_param)
        tool_input = CypherQueryInput(
            query_intent="Gene Ontology terms annotated to the gene",
            query_class="single_hop",
            target_entities=[curie],
            row_limit=100,
        )
        out = await cypher_query(_NoHarness(), tool_input, template=template)
        print(
            f"{symbol} {curie}: template={out.template} status={out.status} "
            f"row_count={out.row_count} total_available={out.total_available} "
            f"truncated={out.truncated}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
