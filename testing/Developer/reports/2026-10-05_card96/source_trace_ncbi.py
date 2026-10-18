"""Read-only: MedGen esummary for C1321489 via the app's transport; raw bytes vs response.text."""
import asyncio
import binascii
import sys

from dotenv import load_dotenv

load_dotenv()  # values are never printed
sys.path.insert(0, "src")
from system_03_search_agent.tools import ncbi_transport as nt


async def main():
    for params in ({"db": "medgen", "term": "C1321489", "retmode": "json"},):
        r = await nt.execute_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params, family="eutils", include_api_key=True)
        print("esearch:", r.headers.get("content-type"), r.text[:200])
    r = await nt.execute_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        {"db": "medgen", "id": "231157", "retmode": "json"}, family="eutils", include_api_key=True)
    raw = r.content
    print("content-type:", r.headers.get("content-type"), "| httpx encoding:", r.encoding)
    i = raw.find(b"Torr")
    print("raw bytes:", raw[i-5:i+30]); print("hex:", binascii.hexlify(raw[i-5:i+30]).decode())
    j = r.text.find("Torr"); print("response.text:", ascii(r.text[j-5:j+30]))
    print("utf-8 decode:", ascii(raw.decode("utf-8")[i-5:i+30]))
asyncio.run(main())
