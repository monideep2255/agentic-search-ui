"""Adversary round 3: what develop's D3 fallback would bind, live from
MedGen, for tokens the branch now skips. NCBI E-utilities only, no model."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.core import graph as g


async def main():
    for term in sys.argv[2:]:
        curies, matched = await g.resolve_disease_mention_to_curies(term)
        uids = list(curies)
        print(json.dumps({"term": term, "matched": matched, "curies": uids}))
        await asyncio.sleep(0.4)


asyncio.run(main())
