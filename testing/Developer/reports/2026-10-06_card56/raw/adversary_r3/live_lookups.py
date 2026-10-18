"""Adversary round 3: live NCBI gene and taxonomy lookups for tokens and
spans in the attack questions. NCBI E-utilities only, no model."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))

from system_03_search_agent.core import graph as g


async def main():
    for sym in ["SARS", "SRA", "MERS", "COVID", "HIV", "IBD", "AML", "H5N1"]:
        print("gene", sym, await g.resolve_symbol_to_curie(sym))
        await asyncio.sleep(0.4)
    for name in [
        "SARS-CoV-2",
        "SARS CoV 2",
        "SARS CoV-2",
        "SARS-CoV 2",
        "SARS‐CoV‐2",
        "SARS­CoV­2",
        "SARS CoV2",
        "HIV-1",
        "COVID-19",
    ]:
        print("taxon", repr(name), await g._organism_is_known(name))
        await asyncio.sleep(0.4)


asyncio.run(main())
