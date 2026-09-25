"""LitSense live probe for card 44 / item 13.1.

Depends on:
    - eval/golden/golden_dataset.json (read only, ten questions selected by hand)
    - https://www.ncbi.nlm.nih.gov/research/litsense-api/api/ (live NCBI endpoint, no key)

Reads:
    - eval/golden/golden_dataset.json

Writes:
    - testing/Developer/reports/2026-09-25_phase_8.4/litsense_probe/raw_results.json

This is a probe script only. It builds nothing that ships. One request per
second, per the tool-call-budgets rule's provisional throttle for an
undocumented API.
"""

import json
import time
import urllib.parse
import urllib.request

BASE = "https://www.ncbi.nlm.nih.gov/research/litsense-api/api/"

QUESTIONS = [
    ("G-002", "Give me everything NCBI knows about BRCA1: the gene record, associated conditions, clinically significant variants and literature evidence."),
    ("G-006", "For PMID 11237011, what sequence data, BioProjects, GEO series and assemblies are linked to it?"),
    ("G-019", "What MeSH terms are assigned to PMID 11237011?"),
    ("G-021", "Which papers in the graph mention the CFTR gene, and what do they cover?"),
    ("G-023", "Which clinically significant variants have been reported in CFTR?"),
    ("G-024", "What is rs334 and what condition is it associated with?"),
    ("G-025", "What does the MTHFR C677T variant do, and what is the evidence quality around it?"),
    ("G-028", "What is the evidence linking APOE to late-onset Alzheimer disease?"),
    ("G-030", "What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?"),
    ("G-033", "Compare what is known about MLH1 and MSH2 in colorectal cancer risk."),
]


def call_litsense(query, limit=10, extra_params=None):
    params = {"query": query, "rerank": "true", "limit": str(limit)}
    if extra_params:
        params.update(extra_params)
    url = BASE + "?" + urllib.parse.urlencode(params)
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-search-ui-litsense-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            elapsed = time.monotonic() - start
            data = json.loads(body)
            return {"ok": True, "latency_s": elapsed, "n": len(data), "results": data, "url": url}
    except (OSError, ValueError) as e:
        elapsed = time.monotonic() - start
        return {"ok": False, "latency_s": elapsed, "error": str(e), "url": url}


def main():
    out = []
    for qid, question in QUESTIONS:
        print(f"Querying {qid}...")
        result = call_litsense(question, limit=10)
        out.append({"id": qid, "question": question, "mode": "plain", "result": result})
        time.sleep(1.1)

    # PMID-restriction mode test, using G-006 / G-019's anchor PMID 11237011
    print("Testing PMID-restriction param guesses...")
    anchor_pmid = "11237011"
    for param_name in ["pmids", "pmid", "pmid_list", "restrict_pmid"]:
        r = call_litsense("MeSH terms sequence data", limit=5, extra_params={param_name: anchor_pmid})
        out.append({"id": "PMID-RESTRICT-TEST", "question": f"param={param_name}", "mode": "pmid_restrict_probe", "result": r})
        time.sleep(1.1)

    out_path = "testing/Developer/reports/2026-09-25_phase_8.4/litsense_probe/raw_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
