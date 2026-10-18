"""Item 11.22, abstracts as citeable context: does text from a PubMed abstract
reach the answer, cited to the paper?

Reads the live captures in `raw/`, finds every citation whose `field` is the
paper's abstract, fetches that paper from E-utilities in plain-text mode (no
XML parser involved; one request per distinct PMID, capped at three, a second
apart, keyed when `.env` carries a key), takes the longest paragraph as the
abstract, and reports two things per paper: how many whole abstract sentences
appear verbatim in the captured answer, and the longest verbatim run shared by
the abstract and the answer. The grounding gate accepts a claim on contiguous
containment, so a grounded quote from an abstract can be a clause rather
than a whole sentence; a shared run of 60 characters or more is treated as a
quote, a shorter one is not. Verified off the agent's own path: the abstract
comes from NCBI here, not from the product. Run from the repository root.
"""
import difflib
import glob
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

root = pathlib.Path(".")
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
KEY = os.environ.get("NCBI_API_KEY", "")
FOLDER = root / "testing" / "Developer" / "reports" / "2026-09-22_item1_lost_search"
QUOTE_CHARS = 60


def fetch_abstract(pmid: str) -> str:
    params = {"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "text", "tool": "system3-probe"}
    if KEY:
        params["api_key"] = KEY
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as resp:
        text = resp.read().decode("utf-8", "replace")
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    return max(paragraphs, key=len) if paragraphs else ""


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]


def longest_shared_run(a: str, b: str) -> str:
    match = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[match.a : match.a + match.size]


checked: dict[str, tuple[str, int, int, int]] = {}
for path in sorted(glob.glob(str(FOLDER / "raw" / "G-*_run*.json"))):
    with open(path) as handle:
        capture = json.load(handle)
    events = capture.get("events", capture)
    answer = " ".join((capture.get("answer_text") or "").split())
    abstract_citations = [
        e.get("payload", e)
        for e in events
        if (e.get("type") or e.get("event")) == "citation" and e.get("payload", e).get("field") == "abstract"
    ]
    name = os.path.basename(path)[:-5]
    print(f"{name}: {len(abstract_citations)} abstract citations, answer {len(answer.split())} words")
    for citation in abstract_citations:
        match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", citation.get("source_url") or "")
        if not match or len(checked) >= 3 or match.group(1) in checked:
            continue
        pmid = match.group(1)
        abstract = fetch_abstract(pmid)
        time.sleep(1.0)
        whole = [s for s in sentences(abstract) if s in answer]
        run = longest_shared_run(abstract, answer)
        checked[pmid] = (name, len(sentences(abstract)), len(whole), len(run))
        print(
            f"   PMID {pmid}: {len(whole)} of {len(sentences(abstract))} whole sentences verbatim in the answer; "
            f"longest shared run {len(run)} chars"
        )
        if len(run) >= QUOTE_CHARS:
            print("      quoted:", run[:160])
print()
quoted = [pmid for pmid, (_, _, whole, run) in checked.items() if whole or run >= QUOTE_CHARS]
print(
    "verdict:",
    f"PASS, abstract text reaches the answer cited to its paper ({', '.join(quoted)})"
    if quoted
    else "FAIL, no abstract text of 60 characters or more appears verbatim in any answer",
)
