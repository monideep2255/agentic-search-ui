"""Adversary round 3: MedGen titles for concept ids, NCBI only, no model."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))

from system_03_search_agent.tools import ncbi_eutils_actions as n
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchSearchInput,
    NcbiEfetchSummaryInput,
)


async def main():
    for cid in sys.argv[2:]:
        found = await n.search(
            NcbiEfetchSearchInput(action="search", db="medgen", term=cid, retmax=1)
        )
        uids = [u for r in found.records for u in (r.fields.get("idlist") or [])]
        if not uids:
            print(cid, "no hit")
            continue
        s = await n.summary(NcbiEfetchSummaryInput(action="summary", db="medgen", ids=uids[:1]))
        for r in s.records:
            print(cid, "|", r.fields.get("title"))
        await asyncio.sleep(0.35)


asyncio.run(main())
