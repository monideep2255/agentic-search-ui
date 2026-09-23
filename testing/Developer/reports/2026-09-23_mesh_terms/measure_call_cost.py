"""How many Layer 2/3 calls does MeSH term resolution actually cost?

Counted at `harness/call_budget.py`, which is where the 20-per-query ceiling
is charged, and NOT from `tool_start` events, which miss exactly this kind of
call. Worker D established on 2026-09-22 that the two measurements disagree
and that this is the one that binds: the worst observed cold pass is 17 of
20, not the 10 the event stream reports.

Every call below is real. Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_mesh_terms/measure_call_cost.py
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

from system_03_search_agent.harness.call_budget import (
    MAX_LAYER_2_3_CALLS_PER_QUERY,
    calls_made,
    query_budget_scope,
)
from system_03_search_agent.synthesis import mesh_terms

# G-019's 26 real ids, exactly as the graph returns them.
G019 = [
    "MeSH:D000818", "MeSH:D002874", "MeSH:D017124", "MeSH:D018899",
    "MeSH:D004251", "MeSH:D016208", "MeSH:D004345", "MeSH:D019143",
    "MeSH:D005544", "MeSH:D020862", "MeSH:D020440", "MeSH:D005796",
    "MeSH:D030342", "MeSH:D005826", "MeSH:D015894", "MeSH:D016045",
    "MeSH:D006801", "MeSH:D009154", "MeSH:D017149", "MeSH:D011506",
    "MeSH:D020543", "MeSH:D017150", "MeSH:D012313", "MeSH:D012091",
    "MeSH:D017422", "MeSH:D013045",
]

WORST_OBSERVED_COLD_PASS = 17  # testing/Developer/reports/2026-09-22_call_ceiling


async def _measure(label: str, curies: list[str], *, warm: bool) -> int:
    if not warm:
        mesh_terms.reset_cache_for_tests()
    with query_budget_scope("single_hop"):
        before = calls_made()
        resolved = await mesh_terms.resolve_descriptor_ids(curies)
        after = calls_made()
    cost = (after or 0) - (before or 0)
    named = sum(1 for value in resolved.values() if value)
    print(f"{label}")
    print(f"    ids asked about : {len(curies)}")
    print(f"    headings back   : {named}")
    print(f"    calls charged   : {cost}")
    print(f"    sample          : {resolved.get(curies[0])!r}")
    return cost


async def main() -> None:
    print(f"ceiling = {MAX_LAYER_2_3_CALLS_PER_QUERY}, "
          f"worst observed cold pass before this change = {WORST_OBSERVED_COLD_PASS}")
    print("=" * 74)
    cold_26 = await _measure("G-019, all 26 ids, cold cache", G019, warm=False)
    print("-" * 74)
    warm_26 = await _measure("G-019, all 26 ids, warm cache", G019, warm=True)
    print("-" * 74)
    mesh_terms.reset_cache_for_tests()
    cold_1 = await _measure("One id, cold cache", ["MeSH:D000818"], warm=True)
    print("-" * 74)
    medgen = await _measure(
        "A MedGen-only question (what a disease query looks like)",
        ["MedGen:C0346153", "MedGen:C2676676"],
        warm=False,
    )
    print("=" * 74)
    print(f"worst case added by this change : {max(cold_26, cold_1)}")
    print(f"against the ceiling             : "
          f"{WORST_OBSERVED_COLD_PASS + max(cold_26, cold_1)} of "
          f"{MAX_LAYER_2_3_CALLS_PER_QUERY}")
    print(f"cost on a question with no MeSH rows : {medgen}")
    print(f"cost on a repeat in one process      : {warm_26}")


if __name__ == "__main__":
    asyncio.run(main())
