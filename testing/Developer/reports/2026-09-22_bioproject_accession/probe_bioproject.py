"""Live E-utilities check of BioProject PRJNA31257 for golden question G-007.

For BioProject accession PRJNA31257, tries two ESearch terms against
db=bioproject, resolves the winning uid, runs one ESummary on db=bioproject
for it, then runs three ELink calls (bioproject to biosample, sra, and
assembly) and one batched ESummary per target db on its first three linked
ids (skipped for a target db with zero links). Up to nine requests total, a
second apart, keyed when the repository's `.env` carries a key. Run from the
repository root.
"""
import json
import os
import pathlib
import time
import urllib.error
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

ACCESSION = "PRJNA31257"
LINK_TARGETS = ["biosample", "sra", "assembly"]
SUMMARY_FIELDS = {
    "biosample": ["accession", "title", "organism"],
    "sra": ["runs", "createdate"],
    "assembly": ["assemblyaccession", "assemblyname", "assemblystatus", "organism"],
}

TIMINGS: list[tuple[str, float]] = []


def cut(value: object, limit: int) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + " [truncated]"


def call(endpoint: str, **params: str) -> tuple[dict, float]:
    query = {**params, "retmode": "json", "tool": "system3-probe"}
    if KEY:
        query["api_key"] = KEY
    url = BASE + endpoint + "?" + urllib.parse.urlencode(query)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        elapsed = time.monotonic() - started
        print(f"BLOCKED: {endpoint} failed after {elapsed:.3f}s: {exc!r}")
        raise
    elapsed = time.monotonic() - started
    print(f"   [{endpoint} elapsed_s={elapsed:.3f}]")
    return data, elapsed


# ---------------------------------------------------------------------------
# Step 1: ESearch on db=bioproject, two terms, then ESummary on the winner.
# ---------------------------------------------------------------------------

SEARCH_TERMS = [
    ("accn", f"{ACCESSION}[ACCN]"),
    ("plain", ACCESSION),
]

term_results: dict[str, dict] = {}
for label, term in SEARCH_TERMS:
    data, elapsed = call("esearch.fcgi", db="bioproject", term=term, retmax="20")
    TIMINGS.append((f"esearch bioproject term={label}", elapsed))
    result = data.get("esearchresult", {})
    idlist = result.get("idlist", [])
    term_results[label] = {
        "term": term,
        "count": result.get("count"),
        "translation": result.get("querytranslation"),
        "idlist": idlist,
    }
    print("ESEARCH TERM:", label)
    print("   raw term:", term)
    print("   querytranslation:", result.get("querytranslation"))
    print("   count:", result.get("count"))
    print("   idlist:", idlist)
    time.sleep(1.0)

bioproject_uid = None
for label in ("accn", "plain"):
    ids = term_results[label]["idlist"]
    if ids:
        bioproject_uid = ids[0]
        break

if bioproject_uid is None:
    print("BLOCKED: neither ESearch term returned an id for", ACCESSION)
    raise SystemExit(1)

print("BIOPROJECT UID:", bioproject_uid)

BIOPROJECT_FIELDS = [
    "project_acc",
    "project_title",
    "project_type",
    "project_data_type",
    "organism_name",
    "registration_date",
]

data, elapsed = call("esummary.fcgi", db="bioproject", id=bioproject_uid)
TIMINGS.append(("esummary bioproject", elapsed))
result = data.get("result", {})
entry = result.get(bioproject_uid, {})
print("ESUMMARY bioproject uid", bioproject_uid)
for field in BIOPROJECT_FIELDS:
    print("  ", field, "=", cut(entry.get(field), 100))
time.sleep(1.0)

# ---------------------------------------------------------------------------
# Step 2: ELink from bioproject to biosample, sra, assembly.
# ---------------------------------------------------------------------------

linked_ids_by_db: dict[str, list[str]] = {}
linknames_by_db: dict[str, list[tuple[str, int, list[str]]]] = {}

for target in LINK_TARGETS:
    data, elapsed = call("elink.fcgi", dbfrom="bioproject", db=target, id=bioproject_uid)
    TIMINGS.append((f"elink bioproject->{target}", elapsed))
    linksets = data.get("linksets", [])
    print("ELINK bioproject ->", target)
    all_ids: list[str] = []
    seen_linknames: list[tuple[str, int, list[str]]] = []
    for linkset in linksets:
        for linksetdb in linkset.get("linksetdbs", []) or []:
            linkname = linksetdb.get("linkname")
            links = [str(x) for x in linksetdb.get("links", [])]
            print("   linkname:", linkname, "| count:", len(links), "| first five:", links[:5])
            seen_linknames.append((linkname, len(links), links[:5]))
            all_ids.extend(links)
    if not seen_linknames:
        print("   (no linksetdbs present, zero links)")
    seen: set[str] = set()
    deduped: list[str] = []
    for linked_id in all_ids:
        if linked_id not in seen:
            seen.add(linked_id)
            deduped.append(linked_id)
    linked_ids_by_db[target] = deduped
    linknames_by_db[target] = seen_linknames
    time.sleep(1.0)

# ---------------------------------------------------------------------------
# Step 3: ESummary on the first three linked ids of each target db.
# ---------------------------------------------------------------------------

for target in LINK_TARGETS:
    ids = linked_ids_by_db.get(target, [])
    if not ids:
        print("ESUMMARY", target, ": skipped, ELINK returned no links for this target database")
        continue
    first_three = ids[:3]
    data, elapsed = call("esummary.fcgi", db=target, id=",".join(first_three))
    TIMINGS.append((f"esummary {target} (first 3)", elapsed))
    result = data.get("result", {})
    print("ESUMMARY", target, "first three ids:", first_three)
    for uid in first_three:
        entry = result.get(uid, {})
        print("  uid", uid)
        for field in SUMMARY_FIELDS[target]:
            limit = 150 if (target == "sra" and field == "runs") else 300
            print("    ", field, "=", cut(entry.get(field), limit))
    time.sleep(1.0)

# ---------------------------------------------------------------------------
# Summary block: everything probes.md's tables are transcribed from.
# ---------------------------------------------------------------------------

print("\n=== SUMMARY ===")
print("bioproject_uid:", bioproject_uid)
for target in LINK_TARGETS:
    names = [ln for ln, _count, _sample in linknames_by_db.get(target, [])]
    print(
        target,
        "| linked_id_count:", len(linked_ids_by_db.get(target, [])),
        "| linknames:", names,
    )

print("\n=== TIMINGS (label, elapsed_s) ===")
for call_label, call_elapsed in TIMINGS:
    print(f"{call_label}: {call_elapsed:.3f}s")

print("\n=== TOTAL REQUESTS ===", len(TIMINGS))
