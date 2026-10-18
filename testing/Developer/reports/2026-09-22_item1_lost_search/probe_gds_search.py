"""Live E-utilities check of the GEO DataSets search term the breadth plan
now issues for a gene symbol, read back through ESearch's own
`querytranslation`, then ESummary on the first three hits so the fields the
allowlist keeps can be seen. Three requests, a second apart, keyed when the
repository's `.env` carries a key. Run from the repository root.
"""
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

root = pathlib.Path(".")
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
KEY = os.environ.get("NCBI_API_KEY", "")


def call(endpoint: str, **params: str) -> dict:
    params = {**params, "retmode": "json", "tool": "system3-probe"}
    if KEY:
        params["api_key"] = KEY
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


TERMS = [
    "TP53[All Fields] AND gse[Entry Type]",  # the term the plan issues for TP53
    "TP53[Gene Symbol] AND Homo sapiens[Organism]",  # rejected: GDS has no symbol field; 19,092 hits, mostly samples
    "BRCA1[All Fields] AND gse[Entry Type]",
]
first_ids: list[str] = []
for term in TERMS:
    result = call("esearch.fcgi", db="gds", term=term, retmax="5", sort="relevance").get("esearchresult", {})
    print("TERM:", term)
    print("   count:", result.get("count"), "| translation:", result.get("querytranslation"))
    print("   ids:", result.get("idlist"))
    if not first_ids and result.get("idlist"):
        first_ids = result["idlist"][:3]
    time.sleep(1.0)
if first_ids:
    summaries = call("esummary.fcgi", db="gds", id=",".join(first_ids)).get("result", {})
    for uid in first_ids:
        record = summaries.get(uid, {})
        print(uid, "|", record.get("accession"), "|", record.get("entrytype"), "|", record.get("gdstype"))
        print("   ", (record.get("title") or "")[:100], "| taxon:", record.get("taxon"), "| n_samples:", record.get("n_samples"))
