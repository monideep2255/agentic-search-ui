"""Card 23: check each live answer recorded by `live_run.py`.

For each answer: whether the variant-to-disease table shows, whether the
source note shows, where the note sits relative to that table, and whether
the note is true for the rows shown:

- each variant row's own citation (its first marker) is a ClinVar variation
  record;
- each disease a row's mapping cell names is backed by a cited MedGen
  record among that row's other markers.

Also prints which surface the note lands in on the answer screen: in place
(a claim follows it, so `useRunView` attaches it to that claim) or in the
trailing Notes list (nothing follows it).

Usage: python3 analyse_live.py <OUT_DIR> <label> [<label> ...]
Prints counts and record identifiers only, no record text beyond names.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NOTE = (
    "Variant-to-disease links are ClinVar assertions, each cited to its "
    "variation record. Disease names are MedGen titles read live from NCBI."
)


def analyse(path: Path) -> None:
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    tokens = [line for line in lines if line["type"] == "token"]
    citations = {line["citation_id"]: line for line in lines if line["type"] == "citation"}
    done = next((line for line in lines if line["type"] == "done"), {})
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    note_at = [i for i, t in enumerate(tokens) if t["kind"] == "note" and t["text"] == NOTE]
    print(f"== {path.stem}: cost ${done.get('total_cost_usd')}, {done.get('elapsed_ms')} ms")
    print(f"   headings: {headings}")
    print(f"   variant table shown: {'Variant-to-disease mapping' in headings}; source notes: {len(note_at)}")
    if "Variant-to-disease mapping" not in headings:
        return
    start = next(
        i for i, t in enumerate(tokens) if t["kind"] == "heading" and t["text"].strip() == "Variant-to-disease mapping"
    )
    header = tokens[start + 1]
    rows = []
    for t in tokens[start + 2 :]:
        if t["kind"] != "table_row":
            break
        rows.append(t)
    last_row = start + 1 + len(rows)
    print(f"   table header: {header.get('cells')}, rows: {len(rows)}")
    if note_at:
        between = [t["kind"] for t in tokens[last_row + 1 : note_at[0]]]
        print(f"   tokens between last row and note: {between}")
        after = [t for t in tokens[note_at[0] + 1 :] if t["kind"] not in ("paragraph_break", "note", "heading")]
        print(
            "   on screen the note shows: "
            + ("in place, before the next block" if after else "in the Notes list after the answer, first item")
        )
    disease_column = (header.get("cells") or []).index("Associated disease(s)")
    variant_ok = 0
    disease_names_backed = 0
    disease_names_total = 0
    for row in rows:
        ids = row.get("marker_ids") or []
        own = citations.get(ids[0]) if ids else None
        if own and "/clinvar/variation/" in (own.get("source_url") or ""):
            variant_ok += 1
        else:
            print(f"   ROW NOT CITED TO A CLINVAR VARIATION RECORD: {row.get('cells')} -> {own}")
        others = [citations.get(i) for i in ids[1:]]
        medgen = [c for c in others if c and "/medgen/" in (c.get("source_url") or "")]
        names = [n for n in (row["cells"][disease_column] or "").split("; ") if n]
        disease_names_total += len(names)
        disease_names_backed += min(len(names), len(medgen))
        if len(names) > len(medgen):
            print(f"   names {names} but only {len(medgen)} MedGen markers on the row")
    print(f"   rows whose own citation is a ClinVar variation record: {variant_ok} of {len(rows)}")
    print(f"   disease names with a MedGen record cited on the row: {disease_names_backed} of {disease_names_total}")
    sources = sorted({(citations.get(r['marker_ids'][0]) or {}).get('source') for r in rows if r.get('marker_ids')})
    print(f"   variant row citation sources: {sources}")


def main() -> None:
    out = Path(sys.argv[1])
    for label in sys.argv[2:]:
        analyse(out / f"{label}.jsonl")


main()
