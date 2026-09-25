"""Smoke test for the narrow LitSense design: title query, filter by pmid.

Depends on:
    - https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi (ESummary, no key, <=3 req/s)
    - https://www.ncbi.nlm.nih.gov/research/litsense-api/api/ (LitSense, no key)

Reads:
    - A fixed list of 20 PMIDs, one from the golden dataset (11237011) and
      nineteen sampled from testing/Developer/reports/2026-09-22_10.3_consistency/raw/*.json
      cited PubMed URLs, spread from old (2000) to recent (2026) to test
      whether PMC full-text coverage changes the match rate.

Writes:
    - testing/Developer/reports/2026-09-25_phase_8.4/litsense_probe/raw_title_probe.json

Probe script only. Builds nothing that ships. ESummary at <=3 req/s,
LitSense at <=1 req/s per the tool-call-budgets rule's provisional throttle.
"""

import json
import re
import time
import urllib.parse
import urllib.request

PMIDS = [
    "11237011", "10651488", "10862786", "11104661", "11146634",
    "11243954", "11379874", "11524016", "11667976", "11707463",
    "11773581", "27328919", "30998989", "32249768", "34157306",
    "36150551", "36535904", "38266643", "39056802", "40373998",
]

ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
LITSENSE = "https://www.ncbi.nlm.nih.gov/research/litsense-api/api/"


def fetch_title(pmid):
    params = {"db": "pubmed", "id": pmid, "retmode": "json"}
    url = ESUMMARY + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-search-ui-litsense-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    result = data.get("result", {})
    doc = result.get(pmid, {})
    return doc.get("title", "")


def call_litsense(query, limit=10):
    params = {"query": query, "rerank": "true", "limit": str(limit)}
    url = LITSENSE + "?" + urllib.parse.urlencode(params)
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-search-ui-litsense-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            elapsed = time.monotonic() - start
            data = json.loads(body)
            return {"ok": True, "latency_s": elapsed, "n": len(data), "results": data}
    except (OSError, ValueError) as e:
        elapsed = time.monotonic() - start
        return {"ok": False, "latency_s": elapsed, "error": str(e)}


HAS_VERB_HINT = re.compile(
    r"\b(is|are|was|were|has|have|had|shows?|show|demonstrat\w+|indicat\w+|"
    r"suggest\w+|caus\w+|associat\w+|increas\w+|decreas\w+|reveal\w+|"
    r"found|identif\w+|report\w+|confirm\w+|link\w+|contribut\w+|regulat\w+|"
    r"encod\w+|express\w+|mutat\w+|predict\w+|reduc\w+|remain\w+|provid\w+|"
    r"result\w+|observ\w+|affect\w+|play\w+|acts?\b|binds?\b)\b",
    re.IGNORECASE,
)


def looks_like_sentence(text):
    words = text.strip().split()
    if len(words) < 8:
        return False
    return bool(HAS_VERB_HINT.search(text))


def main():
    out = []
    for i, pmid in enumerate(PMIDS):
        title = fetch_title(pmid)
        print(f"{pmid}: {title[:80]}")
        entry = {"pmid": pmid, "title": title}
        if not title:
            entry["error"] = "no title from esummary"
            out.append(entry)
            time.sleep(0.4)
            continue
        time.sleep(0.4)  # stay under 3 req/s for esummary

        ls = call_litsense(title, limit=10)
        entry["litsense"] = ls
        if ls["ok"]:
            matches = [r for r in ls["results"] if str(r.get("pmid")) == pmid]
            entry["same_pmid_matches"] = matches
            filtered = [
                r for r in matches
                if r.get("section") in ("abstract", "RESULTS", "DISCUSS")
                and looks_like_sentence(r.get("text", ""))
            ]
            entry["filtered_matches"] = filtered
        out.append(entry)
        time.sleep(1.1)  # stay at/under 1 req/s for litsense

    out_path = "testing/Developer/reports/2026-09-25_phase_8.4/litsense_probe/raw_title_probe.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
