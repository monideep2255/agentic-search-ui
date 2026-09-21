"""Re-run of the four probes whose parser was wrong in probe_apis.py, plus
two ways of checking PMC open-access status. Same pacing. Output appended to
`api_probe.jsonl` with probe names prefixed "FIX".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_apis as p
from defusedxml import ElementTree as DET

EUTILS = p.EUTILS


def parse_abstracts(resp):
    root = DET.fromstring(resp.text)
    recs = []
    for art in root.findall("PubmedArticle"):
        pmid = art.findtext("./MedlineCitation/PMID") or ""
        t = art.find("MedlineCitation/Article/ArticleTitle")
        title = "".join(t.itertext()) if t is not None else ""
        abstract = " ".join("".join(n.itertext()) for n in art.findall("MedlineCitation/Article/Abstract/AbstractText"))
        year = art.findtext("MedlineCitation/Article/Journal/JournalIssue/PubDate/Year") or ""
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        recs.append({"pmid": pmid, "year": year, "title": title[:120], "abstract_chars": len(abstract),
                     "sentences": abstract.count(". ") + (1 if abstract else 0), "abstract_head": abstract[:220],
                     "source_url": url, "citeable": p.citeable(url)})
    return {"records": len(recs), "with_abstract": sum(1 for r in recs if r["abstract_chars"]),
            "abstract_chars_total": sum(r["abstract_chars"] for r in recs), "sample": recs}


def parse_clinvar(resp):
    body = resp.json()["result"]
    recs = []
    for uid in body.get("uids", []):
        r = body[uid]
        gc = r.get("germline_classification") or {}
        conditions = []
        for ts in gc.get("trait_set", []) or []:
            if ts.get("trait_name"):
                conditions.append(ts["trait_name"])
        url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/"
        recs.append({"uid": uid, "accession": r.get("accession"), "title": (r.get("title") or "")[:90],
                     "germline": gc.get("description"), "review_status": gc.get("review_status"),
                     "last_evaluated": gc.get("last_evaluated"), "conditions": conditions[:4],
                     "genes": [g.get("symbol") for g in (r.get("genes") or [])][:3],
                     "source_url": url, "citeable": p.citeable(url)})
    first = body[body["uids"][0]] if body.get("uids") else {}
    return {"records": len(recs), "with_conditions": sum(1 for r in recs if r["conditions"]),
            "first_record_keys": sorted(first.keys())[:30],
            "germline_keys": sorted((first.get("germline_classification") or {}).keys()), "sample": recs}


def parse_datasets_gene(resp):
    body = resp.json()
    reports = body.get("reports") or body.get("genes") or []
    g = reports[0].get("gene", reports[0]) if reports else {}
    summary = g.get("summary")
    if isinstance(summary, list):
        text = " ".join(s.get("description", "") for s in summary if isinstance(s, dict))
    else:
        text = summary or ""
    go = g.get("gene_ontology") or {}
    url = f"https://www.ncbi.nlm.nih.gov/gene/{g.get('gene_id')}"
    return {"symbol": g.get("symbol"), "summary_chars": len(text), "summary_head": text[:300],
            "go_counts": {k: len(v or []) for k, v in go.items()} if isinstance(go, dict) else None,
            "omim_ids": g.get("omim_ids"), "synonyms": (g.get("synonyms") or [])[:8],
            "transcript_count": g.get("transcript_count"), "protein_count": g.get("protein_count"),
            "source_url": url, "citeable": p.citeable(url), "top_keys": sorted(g.keys())}


def parse_oa2(resp):
    return {"status": resp.status_code, "head": resp.text[:200].replace("\n", " ")}


def parse_esearch(resp):
    return p.parse_esearch(resp)


if __name__ == "__main__":
    for symbol, pmids, gid in (
        ("BRCA1", ["42393830", "41693691", "42235864", "42474165", "42348942"], "672"),
        ("GCK", ["42438052", "42600891", "42468610", "42115781", "42470517"], "2645"),
    ):
        p.record(f"FIX {symbol} EFetch abstracts for top 5 PMIDs", "eutils", EUTILS + "efetch.fcgi",
                 p.eutils_params(db="pubmed", id=",".join(pmids), rettype="abstract", retmode="xml"), parse_abstracts)
        p.record(f"FIX {symbol} Datasets v2 gene/id/{gid}", "datasets", f"https://api.ncbi.nlm.nih.gov/datasets/v2/gene/id/{gid}", None,
                 parse_datasets_gene)
    for symbol, uids in (
        ("BRCA1", ["4887763", "4887537", "4884209", "4882953", "4876137", "4876067", "4876022", "4876014", "4876004", "4875788"]),
        ("GCK", ["4871742", "4857269", "4856685", "4856682", "4856677", "4856671", "4856667", "4853506", "4853505", "4845620"]),
    ):
        p.record(f"FIX {symbol} ClinVar ESummary top 10 with conditions", "eutils", EUTILS + "esummary.fcgi",
                 p.eutils_params(db="clinvar", id=",".join(uids), retmode="json"), parse_clinvar)
    # ClinVar with a deterministic sort and a review-status filter, the shape a plan would use.
    p.record("FIX BRCA1 ClinVar ESearch pathogenic, reviewed, MODY-style condition filter absent", "eutils", EUTILS + "esearch.fcgi",
             p.eutils_params(db="clinvar", term='BRCA1[gene] AND "clinsig pathogenic"[Properties] AND "reviewed by expert panel"[Review status]',
                             retmax=10, retmode="json"), parse_esearch)
    p.record("FIX GCK ClinVar ESearch pathogenic AND MODY condition", "eutils", EUTILS + "esearch.fcgi",
             p.eutils_params(db="clinvar", term='GCK[gene] AND "clinsig pathogenic"[Properties] AND "maturity onset diabetes"[Disease/Phenotype]',
                             retmax=10, retmode="json"), parse_esearch)
    # PMC open access: the OA web service under its current host, and the ESearch filter.
    p.record("FIX PMC OA service (pmc host) for PMC13336260", "oa", "https://pmc.ncbi.nlm.nih.gov/tools/oa-service/",
             {"id": "PMC13336260"}, parse_oa2)
    p.record("FIX PMC OA service (www host, oa.fcgi) for PMC13336260", "oa", "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
             {"id": "PMC13336260"}, parse_oa2)
    p.record("FIX PMC ESearch open access filter for PMC13336260", "eutils", EUTILS + "esearch.fcgi",
             p.eutils_params(db="pmc", term="13336260[uid] AND open access[filter]", retmode="json"), parse_esearch)
    p.record("FIX PMC ESearch open access filter for PMC12912221", "eutils", EUTILS + "esearch.fcgi",
             p.eutils_params(db="pmc", term="12912221[uid] AND open access[filter]", retmode="json"), parse_esearch)
    # How many of the BRCA1 gene AND disease PubMed hits have any PMC full text at all, and how many are open access.
    p.record("FIX PMC ESearch BRCA1 AND breast cancer, open access, 5 years", "eutils", EUTILS + "esearch.fcgi",
             p.eutils_params(db="pmc", term='BRCA1[Title] AND "breast cancer"[Title] AND open access[filter] AND 2021:2026[pdat]',
                             retmax=5, sort="pub date", retmode="json"), parse_esearch)
