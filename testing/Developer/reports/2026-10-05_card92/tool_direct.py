"""Call the coordinate_overlap action directly (live, read-only NCBI) for both windows, both dbs."""
import asyncio
import json

from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

W = {"q27": ("17", 43044295, 43125364), "q29": ("7", 117480025, 117668665)}
async def main():
    for q, (c, s, e) in W.items():
        for db in ("clinvar", "dbvar"):
            inp = NcbiEfetchInput.model_validate({"action": "coordinate_overlap", "db": db, "chromosome": c, "start": s, "end": e, "assembly": "GRCh38"})
            out = await ncbi_efetch(inp)
            print(q, db, out.status, "records", out.record_count, "esearch_total", out.total_available, "checked", out.candidates_checked, "truncated", out.truncated)
            for r in out.records:
                print("   ", r.id, r.source_url, json.dumps(r.fields)[:230])
            await asyncio.sleep(0.5)
asyncio.run(main())
