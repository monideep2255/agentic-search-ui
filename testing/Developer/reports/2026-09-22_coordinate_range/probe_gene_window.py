"""Live E-utilities check of three candidate Gene ESearch terms for one window.

For the BRCA1 locus window (chromosome 17, GRCh38, 43,044,295-43,125,364,
Entrez Gene uid 672), tries three candidate coordinate-search terms against
db=gene, reads back ESearch's own `querytranslation`, `count` and `idlist`
for each, then runs ONE ESummary on db=gene for whichever term's idlist
contains uid 672 (ids capped at 10), printing uid, name, description,
chromosome and the genomicinfo entries (chrstart, chrstop, chraccver) per
record. Four requests total, a second apart, keyed when the repository's
`.env` carries a key. Run from the repository root.
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

CHROMOSOME = "17"
START = 43044295
END = 43125364
BRCA1_UID = "672"


def call(endpoint: str, **params: str) -> dict:
    params = {**params, "retmode": "json", "tool": "system3-probe"}
    if KEY:
        params["api_key"] = KEY
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    started = time.monotonic()
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.load(resp)
    elapsed = time.monotonic() - started
    print(f"   [{endpoint} elapsed_s={elapsed:.3f}]")
    return data


TERMS = [
    ("a_CHR_CPOS_human", f"{CHROMOSOME}[CHR] AND {START}:{END}[CPOS] AND human[ORGN]"),
    (
        "b_Chromosome_BasePosition_HomoSapiens",
        f'{CHROMOSOME}[Chromosome] AND {START}:{END}[Base Position] AND "Homo sapiens"[Organism]',
    ),
    ("c_chr_chrpos_taxid", f"{CHROMOSOME}[chr] AND {START}:{END}[chrpos] AND 9606[taxid]"),
]

term_ids: dict[str, list[str]] = {}
for label, term in TERMS:
    result = call("esearch.fcgi", db="gene", term=term, retmax="20").get("esearchresult", {})
    ids = result.get("idlist", [])
    term_ids[label] = ids
    print("TERM:", label)
    print("   raw term:", term)
    print("   count:", result.get("count"), "| translation:", result.get("querytranslation"))
    print("   ids:", ids)
    time.sleep(1.0)

winning_label = None
for label, ids in term_ids.items():
    if BRCA1_UID in ids:
        winning_label = label
        break

if winning_label:
    summary_ids = term_ids[winning_label][:10]
    print("WINNING TERM:", winning_label, "| summary ids (capped at 10):", summary_ids)
    summaries = call("esummary.fcgi", db="gene", id=",".join(summary_ids)).get("result", {})
    for uid in summary_ids:
        record = summaries.get(uid, {})
        genomicinfo = record.get("genomicinfo", [])
        print(
            uid,
            "|",
            record.get("name"),
            "|",
            record.get("description"),
            "| chr:",
            record.get("chromosome"),
        )
        if genomicinfo:
            for g in genomicinfo:
                print(
                    "    genomicinfo: chrstart=",
                    g.get("chrstart"),
                    "chrstop=",
                    g.get("chrstop"),
                    "chraccver=",
                    g.get("chraccver"),
                )
        else:
            print("    genomicinfo: (none present)")
else:
    print("No term's idlist contained uid", BRCA1_UID, "- skipping the esummary call.")
