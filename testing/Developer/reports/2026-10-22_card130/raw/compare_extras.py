"""Extra comparisons for card 130's after report.

Usage: python compare_extras.py <before batch> <after batch>

Per question and depth: whether the writer's findings were identical before
and after (the control: a question with no column finding must be given the
same input), how many column findings the writer was given, how many runs
started a second draft, the median write time (from the first listing
token to done), and the median model cost the runs report.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DETAIL = {"organism", "genes", "amr_genotypes"}
ORDER = [
    "q116_orthologs",
    "q022_cftr_variants",
    "q078_mody_genes",
    "q104_pmid_data",
    "rs334_rs6025",
    "q037_colistin",
]


def read(path: Path) -> dict:
    out = {"findings": None, "second": False, "listing_t": None, "done_t": None, "cost": None}
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        tag, data = entry["tag"], entry["data"]
        if tag == "WRITER_FINDINGS":
            out["findings"] = data
        elif tag == "SECOND_DRAFT_STARTED":
            out["second"] = True
        elif tag == "TOKEN" and data.get("placement") == "listing" and out["listing_t"] is None:
            out["listing_t"] = data.get("t")
        elif tag in ("DONE", "ERROR"):
            out["done_t"] = data.get("t")
            out["cost"] = data.get("total_cost_usd")
    return out


def group(batch: str, key: str, depth: str) -> list[dict]:
    return [read(p) for p in sorted((HERE / batch).glob(f"{key}_{depth}_*.jsonl"))]


def median(values: list[float]) -> str:
    values = [v for v in values if v is not None]
    return f"{statistics.median(values):.1f}" if values else ""


def main() -> None:
    before_batch, after_batch = sys.argv[1], sys.argv[2]
    print(
        "| Question | Depth | Writer input identical | Column findings given | "
        "Second draft started, before | after | Median write s, before | after | "
        "Median cost USD, before | after |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    for key in ORDER:
        for depth in ("researcher", "plain_language"):
            b, a = group(before_batch, key, depth), group(after_batch, key, depth)

            def strip(findings):
                return [row for row in (findings or []) if row[2] not in DETAIL]

            identical = all(x["findings"] == y["findings"] for x, y in zip(b, a, strict=False))
            same_without = all(
                strip(x["findings"]) == strip(y["findings"]) for x, y in zip(b, a, strict=False)
            )
            columns = sorted({sum(1 for r in (y["findings"] or []) if r[2] in DETAIL) for y in a})
            write_b = [x["done_t"] - x["listing_t"] for x in b if x["listing_t"] and x["done_t"]]
            write_a = [y["done_t"] - y["listing_t"] for y in a if y["listing_t"] and y["done_t"]]
            verdict = "yes" if identical else ("yes, apart from the columns" if same_without else "no")
            print(
                f"| {key} | {depth} | {verdict} | {', '.join(map(str, columns))} "
                f"| {sum(x['second'] for x in b)} of {len(b)} | {sum(y['second'] for y in a)} of {len(a)} "
                f"| {median(write_b)} | {median(write_a)} "
                f"| {median([x['cost'] * 100 for x in b if x['cost']])} c | "
                f"{median([y['cost'] * 100 for y in a if y['cost']])} c |"
            )


if __name__ == "__main__":
    main()
