"""Check that every written claim citing a column finding names its own record's value.

Usage: python check_backing.py <batch>

For each run, maps each listing row (table row or list item) to the record
page its own marker cites, and takes the row's displayed column value: the
Researcher table's cells after the name and identifier, or the text inside
the Plain language label's brackets. Then, for every written claim whose
citation is a column field (organism, genes, amr_genotypes), checks that
the value shown in the table for THAT record appears in the claim. A claim
that names a value from a different record, or none, is printed as a
mismatch. Prints one line per run and a total.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DETAIL_FIELDS = {"organism", "genes", "amr_genotypes"}
MARKER = re.compile(r"\[(\d+)\]")
BRACKET = re.compile(r"\(([^()]*)\)")


def check(path: Path) -> tuple[int, list[str]]:
    rows: list[tuple[int, list[str]]] = []
    url_by_index: dict[int, str] = {}
    detail_claims: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        tag, data = entry["tag"], entry["data"]
        if tag == "TOKEN" and data.get("kind") in ("table_row", "list_item") and data.get("cells"):
            found = MARKER.findall(data.get("text") or "")
            if found:
                rows.append((int(found[0]), data["cells"]))
        elif tag == "CITATION":
            url_by_index[data["display_index"]] = data["source_url"]
            if data.get("field") in DETAIL_FIELDS:
                detail_claims.append((data["source_url"], data.get("claim_text") or ""))
    shown: dict[str, list[str]] = {}
    for index, cells in rows:
        url = url_by_index.get(index)
        if not url:
            continue
        values = [cell for cell in cells[2:] if cell]
        if len(cells) == 1:
            values = BRACKET.findall(cells[0])
        shown.setdefault(url, []).extend(values)
    problems = []
    for url, claim in detail_claims:
        values = shown.get(url, [])
        if not any(value.strip() and value.strip() in claim for value in values):
            problems.append(f"{url} | claim: {claim[:160]} | table shows: {values[:3]}")
    return len(detail_claims), problems


def main() -> None:
    total = 0
    bad = 0
    for path in sorted((HERE / sys.argv[1]).glob("*.jsonl")):
        count, problems = check(path)
        total += count
        bad += len(problems)
        print(f"{path.stem}: {count} column claims, {len(problems)} not matching their own row")
        for problem in problems:
            print("   ", problem)
    print(f"TOTAL: {total} column claims, {bad} not matching their own row")


if __name__ == "__main__":
    main()
