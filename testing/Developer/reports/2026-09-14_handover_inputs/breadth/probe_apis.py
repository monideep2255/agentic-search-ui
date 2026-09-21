"""Live Layer 2 and Layer 3 probes for the breadth audit, 2026-09-14.

Read-only GET calls, paced under the rules' limits: E-utilities at most 2.5
per second (the key raises the ceiling to 10 but the rule says the figure is
unconfirmed, so the unauthenticated 3 per second is what this script never
exceeds), Datasets, PubTator3 and ClinicalTrials.gov at most 2 per second
(rule: provisional 5), LitSense at 1 per second, the PMC OA service at 1 per
second. Three latency samples per call. Output: `api_probe.jsonl`.

Citeability is checked against the repository's own host-pinned patterns,
imported rather than copied.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import httpx
from defusedxml import ElementTree

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")
sys.path.insert(0, str(REPO / "src"))
for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    CLINICALTRIALS_HOST as CLINICALTRIALS_RECORD_URL_PATTERN,
)
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NCBI_EFETCH_RECORD_URL_PATTERN,
)

OUT = HERE / "api_probe.jsonl"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
API_KEY = os.environ.get("NCBI_API_KEY", "")
SAMPLES = 3
PACE = {"eutils": 0.45, "datasets": 0.5, "pubtator": 0.5, "litsense": 1.0, "ct": 0.5, "oa": 1.0}
_last_call: dict[str, float] = {}
client = httpx.Client(timeout=15.0, headers={"User-Agent": "agentic-search-ui breadth audit (read-only)"})


def _pace(family: str) -> None:
    last = _last_call.get(family)
    if last is not None:
        wait = PACE[family] - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_call[family] = time.monotonic()


def get(family: str, url: str, params: dict | None = None) -> tuple[httpx.Response, float]:
    _pace(family)
    started = time.monotonic()
    resp = client.get(url, params=params)
    return resp, round(time.monotonic() - started, 3)


def eutils_params(**kw: object) -> dict:
    params = {k: v for k, v in kw.items() if v is not None}
    if API_KEY:
        params["api_key"] = API_KEY
    return params


def record(name: str, family: str, url: str, params: dict | None, parse) -> dict:
    """Three samples; the first response is parsed for content."""
    elapsed: list[float] = []
    out: dict = {"probe": name, "family": family, "url": url,
                 "params": {k: v for k, v in (params or {}).items() if k != "api_key"}}
    for i in range(SAMPLES):
        try:
            resp, dt = get(family, url, params)
            elapsed.append(dt)
            if i == 0:
                out["http_status"] = resp.status_code
                try:
                    out.update(parse(resp))
                except Exception as exc:  # noqa: BLE001
                    out["parse_error"] = f"{type(exc).__name__}: {exc}"[:200]
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"{type(exc).__name__}: {exc}"[:200]
            break
    out["elapsed_s"] = elapsed
    out["median_s"] = round(statistics.median(elapsed), 3) if elapsed else None
    with OUT.open("a") as fh:
        fh.write(json.dumps(out) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("url", "params", "sample")})[:600])
    return out


def citeable(url: str) -> bool:
    return bool(re.match(NCBI_EFETCH_RECORD_URL_PATTERN, url) or re.match(CLINICALTRIALS_RECORD_URL_PATTERN, url))


# ---- parsers -------------------------------------------------------------

def parse_esearch(resp: httpx.Response) -> dict:
    body = resp.json()["esearchresult"]
    ids = body.get("idlist", [])
    return {"count": int(body.get("count", 0)), "ids_returned": len(ids), "ids": ids[:10],
            "error": body.get("ERROR")}


def parse_pubmed_abstracts(resp: httpx.Response) -> dict:
    root = ElementTree.fromstring(resp.text)
    recs = []
    for art in root.findall("PubmedArticle"):
        pmid = art.findtext("./MedlineCitation/PMID") or ""
        title = "".join(t for t in (art.find("MedlineCitation/Article/ArticleTitle") or ElementTree.Element("x")).itertext())
        abstract = " ".join("".join(n.itertext()) for n in art.findall("MedlineCitation/Article/Abstract/AbstractText"))
        year = art.findtext("MedlineCitation/Article/Journal/JournalIssue/PubDate/Year") or ""
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        recs.append({"pmid": pmid, "year": year, "title_chars": len(title), "abstract_chars": len(abstract),
                     "sentences": abstract.count(". ") + (1 if abstract else 0),
                     "source_url": url, "citeable": citeable(url), "title": title[:120]})
    return {"records": len(recs), "with_abstract": sum(1 for r in recs if r["abstract_chars"]),
            "abstract_chars_total": sum(r["abstract_chars"] for r in recs), "sample": recs}


def parse_elink_ids(resp: httpx.Response) -> dict:
    body = resp.json()
    result: dict = {"linksets": []}
    for ls in body.get("linksets", []):
        for ldb in ls.get("linksetdbs", []):
            result["linksets"].append({"from": ls.get("ids"), "linkname": ldb.get("linkname"),
                                       "links": len(ldb.get("links", [])), "first": ldb.get("links", [])[:5]})
    return result


def parse_clinvar_summary(resp: httpx.Response) -> dict:
    body = resp.json()["result"]
    recs = []
    for uid in body.get("uids", []):
        r = body[uid]
        gc = r.get("germline_classification") or {}
        traits = []
        for vs in r.get("variation_set", []) or []:
            pass
        for ts in r.get("trait_set", []) or []:
            if ts.get("trait_name"):
                traits.append(ts["trait_name"])
        url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/"
        recs.append({"uid": uid, "accession": r.get("accession"), "title": (r.get("title") or "")[:80],
                     "germline": gc.get("description"), "review_status": gc.get("review_status"),
                     "conditions": traits[:4], "source_url": url, "citeable": citeable(url)})
    return {"records": len(recs), "with_conditions": sum(1 for r in recs if r["conditions"]), "sample": recs}


def parse_datasets_gene(resp: httpx.Response) -> dict:
    body = resp.json()
    genes = body.get("genes") or body.get("reports") or []
    g = (genes[0].get("gene") if genes and isinstance(genes[0], dict) and "gene" in genes[0] else (genes[0] if genes else {})) or {}
    go = g.get("gene_ontology") or {}
    url = f"https://www.ncbi.nlm.nih.gov/gene/{g.get('gene_id')}" if g.get("gene_id") else ""
    return {"records": len(genes), "symbol": g.get("symbol"), "summary_chars": len(g.get("summary") or ""),
            "summary_head": (g.get("summary") or "")[:200],
            "go_counts": {k: len(v or []) for k, v in go.items()} if isinstance(go, dict) else None,
            "omim_ids": g.get("omim_ids"), "synonyms": (g.get("synonyms") or [])[:6],
            "transcript_count": g.get("transcript_count"), "source_url": url, "citeable": citeable(url) if url else None,
            "top_keys": sorted(g.keys())[:40]}


def parse_datasets_product(resp: httpx.Response) -> dict:
    body = resp.json()
    reports = body.get("reports") or []
    r0 = reports[0] if reports else {}
    prod = r0.get("product") or {}
    transcripts = prod.get("transcripts") or []
    return {"records": len(reports), "top_keys": sorted(r0.keys())[:20], "transcripts": len(transcripts),
            "first_transcript": {k: transcripts[0].get(k) for k in ("accession_version", "name", "type", "length")} if transcripts else None}


def parse_pubtator(resp: httpx.Response) -> dict:
    body = resp.json()
    docs = body.get("PubTator3", [])
    out = []
    for d in docs:
        ann = 0
        types: dict[str, int] = {}
        rel = 0
        text_chars = 0
        for p in d.get("passages", []):
            text_chars += len(p.get("text") or "")
            for a in p.get("annotations", []):
                ann += 1
                t = (a.get("infons") or {}).get("type", "?")
                types[t] = types.get(t, 0) + 1
            rel += len(p.get("relations", []) or [])
        rel += len(d.get("relations", []) or [])
        pmid = str(d.get("pmid") or d.get("id") or "")
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        out.append({"pmid": pmid, "annotations": ann, "types": types, "relations": rel, "text_chars": text_chars,
                    "source_url": url, "citeable": citeable(url)})
    return {"records": len(out), "sample": out}


def parse_litsense(resp: httpx.Response) -> dict:
    body = resp.json()
    items = body if isinstance(body, list) else body.get("results", body.get("data", []))
    out = []
    for it in items[:5]:
        pmid = str(it.get("pmid") or "")
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        out.append({"pmid": pmid, "pmcid": it.get("pmcid"), "score": it.get("score"), "section": it.get("section"),
                    "text": (it.get("text") or "")[:160], "source_url": url, "citeable": citeable(url) if url else False})
    return {"records": len(items) if isinstance(items, list) else None, "sample": out,
            "top_keys": sorted(items[0].keys()) if isinstance(items, list) and items else None}


def parse_oa(resp: httpx.Response) -> dict:
    text = resp.text
    return {"oa_record": "<record " in text, "error": re.search(r'<error code="([^"]+)"', text).group(1) if "<error" in text else None,
            "license": (re.search(r'license="([^"]+)"', text) or [None, None])[1] if "license=" in text else None}


def parse_ct(resp: httpx.Response) -> dict:
    body = resp.json()
    studies = body.get("studies", [])
    out = []
    for s in studies[:5]:
        ident = s.get("protocolSection", {}).get("identificationModule", {})
        nct = ident.get("nctId")
        url = f"https://clinicaltrials.gov/study/{nct}"
        out.append({"nct": nct, "title": (ident.get("briefTitle") or "")[:80], "source_url": url, "citeable": citeable(url)})
    return {"records": len(studies), "total_count": body.get("totalCount"), "sample": out}


def parse_generic_summary(resp: httpx.Response) -> dict:
    body = resp.json().get("result", {})
    uids = body.get("uids", [])
    first = body.get(uids[0], {}) if uids else {}
    return {"records": len(uids), "first_keys": sorted(first.keys())[:25],
            "first_title": (first.get("title") or first.get("testname") or "")[:100]}


# ---- the plan ---------------------------------------------------------------

CASES = {
    "BRCA1": {"gene_id": "672", "pubmed_gene": "BRCA1[tiab]", "pubmed_gene_disease": "BRCA1[tiab] AND breast cancer[tiab]",
              "clinvar": 'BRCA1[gene] AND "clinsig pathogenic"[Properties]', "litsense": "BRCA1 breast cancer risk",
              "omim": "BRCA1", "gtr": "BRCA1[gene]", "ct_cond": "BRCA1"},
    "GCK": {"gene_id": "2645", "pubmed_gene": "GCK[tiab] AND glucokinase[tiab]", "pubmed_gene_disease": "GCK[tiab] AND MODY[tiab]",
            "clinvar": 'GCK[gene] AND "clinsig pathogenic"[Properties]', "litsense": "GCK variants maturity onset diabetes of the young",
            "omim": "GCK", "gtr": "GCK[gene]", "ct_cond": "MODY"},
}


def run_case(symbol: str, c: dict) -> None:
    gid = c["gene_id"]
    # Layer 2: PubMed
    r1 = record(f"{symbol} PubMed ESearch gene only, sort=pub_date", "eutils", EUTILS + "esearch.fcgi",
                eutils_params(db="pubmed", term=c["pubmed_gene"], retmax=10, sort="pub_date", retmode="json"), parse_esearch)
    r2 = record(f"{symbol} PubMed ESearch gene AND disease, sort=pub_date", "eutils", EUTILS + "esearch.fcgi",
                eutils_params(db="pubmed", term=c["pubmed_gene_disease"], retmax=10, sort="pub_date", retmode="json"), parse_esearch)
    record(f"{symbol} PubMed ESearch gene AND disease AND review[pt], sort=pub_date", "eutils", EUTILS + "esearch.fcgi",
           eutils_params(db="pubmed", term=c["pubmed_gene_disease"] + " AND review[pt]", retmax=10, sort="pub_date", retmode="json"), parse_esearch)
    record(f"{symbol} ELink gene to pubmed (gene_pubmed, curated)", "eutils", EUTILS + "elink.fcgi",
           eutils_params(dbfrom="gene", db="pubmed", id=gid, linkname="gene_pubmed", retmode="json"), parse_elink_ids)
    pmids = (r2.get("ids") or r1.get("ids") or [])[:5]
    record(f"{symbol} EFetch abstracts for top 5 PMIDs (rettype=abstract, retmode=xml)", "eutils", EUTILS + "efetch.fcgi",
                eutils_params(db="pubmed", id=",".join(pmids), rettype="abstract", retmode="xml"), parse_pubmed_abstracts)
    # PMC availability
    r4 = record(f"{symbol} ELink pubmed to pmc for those 5 PMIDs", "eutils", EUTILS + "elink.fcgi",
                eutils_params(dbfrom="pubmed", db="pmc", id=",".join(pmids), linkname="pubmed_pmc", retmode="json"), parse_elink_ids)
    pmcids = []
    for ls in r4.get("linksets", []):
        pmcids.extend(ls.get("first", []))
    for pmc in pmcids[:2]:
        record(f"{symbol} PMC OA service for PMC{pmc}", "oa", "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi", {"id": f"PMC{pmc}"}, parse_oa)
    # Layer 3: PubTator3 on the same PMIDs
    record(f"{symbol} PubTator3 annotate_publications on top 5 PMIDs", "pubtator",
           "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson", {"pmids": ",".join(pmids)}, parse_pubtator)
    record(f"{symbol} PubTator3 search by text", "pubtator",
           "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/", {"text": c["pubmed_gene_disease"].replace("[tiab]", ""), "page": 1},
           lambda r: {"records": len(r.json().get("results", [])), "total": r.json().get("total_results") or r.json().get("count"),
                      "top_keys": sorted(r.json().keys())[:12]})
    # LitSense
    record(f"{symbol} LitSense sentences", "litsense", "https://www.ncbi.nlm.nih.gov/research/litsense-api/api/",
           {"query": c["litsense"], "limit": 5}, parse_litsense)
    # ClinVar
    r5 = record(f"{symbol} ClinVar ESearch pathogenic", "eutils", EUTILS + "esearch.fcgi",
                eutils_params(db="clinvar", term=c["clinvar"], retmax=10, retmode="json"), parse_esearch)
    uids = r5.get("ids") or []
    record(f"{symbol} ClinVar ESummary top 10 with conditions", "eutils", EUTILS + "esummary.fcgi",
           eutils_params(db="clinvar", id=",".join(uids), retmode="json"), parse_clinvar_summary)
    # Datasets v2
    record(f"{symbol} Datasets v2 gene/id/{gid}", "datasets", f"https://api.ncbi.nlm.nih.gov/datasets/v2/gene/id/{gid}", None, parse_datasets_gene)
    record(f"{symbol} Datasets v2 gene/id/{gid}/product_report", "datasets",
           f"https://api.ncbi.nlm.nih.gov/datasets/v2/gene/id/{gid}/product_report", None, parse_datasets_product)
    # OMIM, GTR, MedGen through ESearch plus ESummary
    r6 = record(f"{symbol} OMIM ESearch", "eutils", EUTILS + "esearch.fcgi",
                eutils_params(db="omim", term=c["omim"] + "[gene symbol]", retmax=5, retmode="json"), parse_esearch)
    if r6.get("ids"):
        record(f"{symbol} OMIM ESummary", "eutils", EUTILS + "esummary.fcgi",
               eutils_params(db="omim", id=",".join(r6["ids"][:5]), retmode="json"), parse_generic_summary)
    r7 = record(f"{symbol} GTR ESearch", "eutils", EUTILS + "esearch.fcgi",
                eutils_params(db="gtr", term=c["gtr"], retmax=5, retmode="json"), parse_esearch)
    if r7.get("ids"):
        record(f"{symbol} GTR ESummary", "eutils", EUTILS + "esummary.fcgi",
               eutils_params(db="gtr", id=",".join(r7["ids"][:5]), retmode="json"), parse_generic_summary)
    record(f"{symbol} MedGen ESearch by gene", "eutils", EUTILS + "esearch.fcgi",
           eutils_params(db="medgen", term=c["omim"] + "[gene]", retmax=10, retmode="json"), parse_esearch)
    # ClinicalTrials.gov as planned today (query.cond = the symbol) and by disease
    record(f"{symbol} ClinicalTrials.gov query.cond={symbol} (as planned today)", "ct", "https://clinicaltrials.gov/api/v2/studies",
           {"query.cond": symbol, "pageSize": 50, "countTotal": "true"}, parse_ct)
    record(f"{symbol} ClinicalTrials.gov query.term={symbol} AND cond={c['ct_cond']}", "ct", "https://clinicaltrials.gov/api/v2/studies",
           {"query.term": symbol, "query.cond": c["ct_cond"], "pageSize": 50, "countTotal": "true"}, parse_ct)


if __name__ == "__main__":
    OUT.unlink(missing_ok=True)
    print("api key set:", bool(API_KEY))
    for symbol, case in CASES.items():
        run_case(symbol, case)
