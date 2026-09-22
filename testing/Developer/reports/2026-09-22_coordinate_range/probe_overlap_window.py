"""Live `coordinate_overlap` probe for one genomic window, both databases.

Calls `system_03_search_agent.tools.ncbi_coordinate_overlap.coordinate_overlap`
directly, the same function `ncbi_efetch.py` dispatches the
`coordinate_overlap` action to with no wrapping harness or transport object
(`return await coordinate_overlap(resolved)`, ncbi_efetch.py), for chromosome
17, GRCh38 43,044,295-43,125,364 (the BRCA1 locus window `probe_gene_window.py`
also uses), once against db="clinvar" and once against db="dbvar", both at
the tool's own default `max_candidates`. Each invocation makes two live
requests internally (one ESearch, one batched ESummary), so this script makes
four requests total; the two top-level calls are a second apart. Keyed when
the repository's `.env` carries NCBI_API_KEY, read the same way the live
premise test (`test_ncbi_efetch_premise.py`) reads it. Run from the
repository root.
"""
import asyncio
import os
import pathlib
import sys
import time

root = pathlib.Path(".")
sys.path.insert(0, str(root / "src"))
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from system_03_search_agent.tools.ncbi_coordinate_overlap import coordinate_overlap
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchCoordinateOverlapInput

WINDOW = {"chromosome": "17", "start": 43044295, "end": 43125364, "assembly": "GRCh38"}


async def probe(db: str) -> None:
    input_model = NcbiEfetchCoordinateOverlapInput.model_validate(
        {"action": "coordinate_overlap", "db": db, **WINDOW}
    )
    started = time.monotonic()
    output = await coordinate_overlap(input_model)
    elapsed = time.monotonic() - started
    print(f"DB: {db}")
    print(f"   elapsed_s: {elapsed:.3f}")
    print(f"   status: {output.status}")
    print(f"   record_count: {output.record_count}")
    print(f"   total_available: {output.total_available}")
    print(f"   truncated: {output.truncated}")
    print(f"   candidates_checked: {output.candidates_checked}")
    if output.error:
        print(f"   error: {output.error}")
    for record in output.records[:3]:
        print(f"   record id={record.id} source_url={record.source_url}")
        for key, value in record.fields.items():
            text = str(value)
            if len(text) > 80:
                text = text[:80] + "...[cut]"
            print(f"      {key}: {text}")


async def main() -> None:
    await probe("clinvar")
    await asyncio.sleep(1.0)  # ASYNC251: time.sleep is blocking, asyncio.sleep is the async form
    await probe("dbvar")


if __name__ == "__main__":
    asyncio.run(main())
