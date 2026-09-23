"""What row_count does the TOOL report, which is the number the UI shows?

Every earlier probe counted graph rows. The `tool_result` event carries
`result_count`, which is `CypherQueryOutput.row_count`, and the tool can emit
more than one output row per graph row (one per RETURN column that decodes to
a node or an edge). So the measured 8 and 12 may be the same template as the
measured 4 and 6, counted after row shaping.

This probe calls the real `cypher_query` with a template chosen in code, so
no model is involved and the number printed is exactly the number a run would
report.

READ ONLY.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/probe_tool_row_count.py
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

from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import select_template

GENES = {"HNF1A": "NCBIGene:6927", "BRCA1": "NCBIGene:672"}

QUESTIONS = [
    "diseases associated with {sym}",
    "diseases caused by variants in {sym}",
    "what is known about the {sym} gene",
    "articles mentioning {sym}",
    "variants in {sym}",
]


class _NoHarness:
    """The template path makes no model call. If one is attempted this
    raises rather than quietly returning something, so a probe result can
    never be mistaken for a template-only run."""

    async def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("the template path must not call a model")


async def main() -> int:
    harness = _NoHarness()
    for symbol, curie in GENES.items():
        print(f"=== {symbol} ({curie}) ===")
        for pattern in QUESTIONS:
            question = pattern.format(sym=symbol)
            tool_input = CypherQueryInput(
                query_intent=question, query_class="single_hop", target_entities=[curie]
            )
            # The pipeline derives the parameter name from the CURIE itself,
            # so a template built against "e_one" is rejected as unbound.
            # This mirrors the real binding exactly.
            param = "e_" + curie.replace(":", "_").replace(".", "_").replace("-", "_")
            template = select_template(tool_input, {param: curie})
            if template is None:
                print(f"  {question!r}: MODEL PATH, skipped")
                continue
            out = await cypher_query(harness, tool_input, template=template)
            print(
                f"  {question!r}\n"
                f"      template={out.template} status={out.status} "
                f"row_count={out.row_count} total_available={out.total_available} "
                f"truncated={out.truncated}\n"
                f"      error={out.error}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
