"""Live E-utilities check of the topic search term fix-plan item 12.7 ships.

It calls the SHIPPED `breadth_plan.build_topic_term`, so re-running it
grades the code rather than a copy of the rule, and reads each term back
through ESearch's own `querytranslation`, the same way `build_pubmed_term`
and `build_gds_term` were verified. Then ESummary on the top hits, so a
person can judge relevance rather than trust a hit count.

Two requests per question, a second apart, keyed when the repository's
`.env` carries a key. Run from the repository root:

    PYTHONPATH=src python3 testing/Developer/reports/2026-09-23_set12/probe_topic_terms.py

Pass `--repeat N` to ask the SAME term N times and compare the id sets,
which is how finding F-12.7-01 (PubMed's `sort=relevance` is not stable
across identical requests) was established.
"""

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "src")

from system_03_search_agent.core import breadth_plan

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

QUESTIONS = [
    "papers on the effects of caffeine on exercise performance",
    "Does coffee help make exercise more effective?",
    "Are there any beneficial variants typically found in people of mediterranean descent?",
    "What positive and negative genes do ashkenazi jewish people have?",
]


def load_env() -> str:
    env = pathlib.Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return os.environ.get("NCBI_API_KEY", "")


def call(endpoint: str, key: str, **params: str) -> dict:
    params = {**params, "retmode": "json", "tool": "system3-probe", "db": "pubmed"}
    if key:
        params["api_key"] = key
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=25) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    key = load_env()

    for question in QUESTIONS:
        term = breadth_plan.build_topic_term(question)
        print("=" * 78)
        print("QUESTION:", question)
        print("TERM:    ", term)
        if term is None:
            continue
        sets = []
        result: dict = {}
        for _ in range(args.repeat):
            result = call(
                "esearch.fcgi",
                key,
                term=term,
                retmax=str(breadth_plan.TOPIC_RESULT_CAP),
                sort="relevance",
            ).get("esearchresult", {})
            sets.append(tuple(result.get("idlist", [])))
            time.sleep(1.0)
        print("COUNT:   ", result.get("count"))
        print("TRANSLATION:", (result.get("querytranslation") or "")[:300])
        if args.repeat > 1:
            same = len({frozenset(s) for s in sets}) == 1
            print("REPEATED ID SETS:", "IDENTICAL" if same else "*** NOT IDENTICAL ***")
            for index, ids in enumerate(sets):
                print("   run", index, ids)
        ids = list(sets[-1])
        if not ids:
            continue
        summaries = call("esummary.fcgi", key, id=",".join(ids)).get("result", {})
        for uid in ids:
            record = summaries.get(uid, {})
            year = (record.get("pubdate") or "")[:4]
            print(f"   {uid} ({year}) {(record.get('title') or '')[:110]}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
