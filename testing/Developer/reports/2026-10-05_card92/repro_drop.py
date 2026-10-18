"""Offline replay of the write step's row handling on live dbVar and ClinVar records (read-only NCBI)."""
import asyncio

from system_03_search_agent.core import graph as g
from system_03_search_agent.synthesis.findings import _citable_value_for_row
from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput


async def main():
    for db, purpose in (("clinvar", "clinvar_overlap"), ("dbvar", "dbvar_overlap")):
        inp = NcbiEfetchInput.model_validate({"action": "coordinate_overlap", "db": db, "chromosome": "17", "start": 43044295, "end": 43125364, "assembly": "GRCh38"})
        out = await ncbi_efetch(inp)
        sf = g._ncbi_efetch_output_to_structured_fields(out, purpose)
        print(db, "rows built:", sf["row_count"])
        for row in sf["rows"]:
            name, value, _suspect, _fb = _citable_value_for_row(row, g._pick_representative_field, apply_vocabulary_artifact_check=False)
            print("  ", row["source_url"].rsplit("/", 2)[-2], "| field keys:", list(row["fields"])[:2], "| citable:", repr(name), repr(value)[:50])
asyncio.run(main())
