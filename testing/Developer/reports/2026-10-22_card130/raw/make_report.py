"""Summarise one batch of card 130 runs as Markdown table rows.

Usage: python make_report.py <batch> [<baseline batch>]

Reads `<batch>/*.jsonl` beside this script and prints, per run: the written
summary sentences shown (every summary-placed claim that is not the
code-built count line), whether a "no written summary" note shows, the
answer's trust outcome and risk tier, the restatement drop, whether the
structured fallback ran, and the time to done. With a baseline batch it also
prints the per question and depth comparison.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNT_LINE = re.compile(r"^(Found|I found) (at least )?\d")
NO_SUMMARY_NOTES = ("no written summary", "written summary could not be finished")
FALLBACK_BUILDERS = {
    "_build_structured_fallback_note",
    "_build_writer_failed_note",
    "_build_cap_list_note",
}
ORDER = [
    "q116_orthologs",
    "q022_cftr_variants",
    "q078_mody_genes",
    "q104_pmid_data",
    "rs334_rs6025",
    "q037_colistin",
]


def read_run(path: Path) -> dict:
    run: dict = {
        "written": [],
        "count_line": "",
        "note": False,
        "trust": "",
        "tier": "",
        "dropped": None,
        "drop_ran": False,
        "fallback": False,
        "t": None,
        "cost": None,
        "detail_findings": 0,
        "cited_details": [],
        "repair": None,
    }
    details: dict[int, str] = {}
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        tag, data = entry["tag"], entry["data"]
        if tag == "WRITER_FINDINGS":
            run["detail_findings"] = sum(
                1 for _i, _t, field, _v in data if field in ("organism", "genes", "amr_genotypes")
            )
        elif tag == "TOKEN":
            text = (data.get("text") or "").strip()
            if data.get("kind") == "note" and any(n in text for n in NO_SUMMARY_NOTES):
                run["note"] = True
            if data.get("placement") == "summary" and data.get("kind") == "claim" and text:
                if COUNT_LINE.match(text) and not run["count_line"]:
                    run["count_line"] = text
                else:
                    run["written"].append(text)
        elif tag == "CITATION":
            if data.get("field") in ("organism", "genes", "amr_genotypes"):
                details[data["display_index"]] = data.get("claim_text") or ""
        elif tag == "TRUST" and data.get("scope") == "answer":
            run["tier"] = data.get("risk_tier") or ""
        elif tag == "RESTATEMENT_DROP":
            run["drop_ran"] = True
            run["dropped"] = data["dropped"]
        elif tag == "FALLBACK_NOTE" and data in FALLBACK_BUILDERS:
            run["fallback"] = True
        elif tag == "REPAIR_CHECK":
            run["repair"] = not data["code_lines_cite_all"]
        elif tag in ("DONE", "ERROR"):
            run["trust"] = data.get("trust_outcome") or tag.lower()
            run["t"] = data.get("t")
            run["cost"] = data.get("total_cost_usd")
    run["cited_details"] = list(details.values())
    return run


def load(batch: str) -> dict[tuple[str, str, str], dict]:
    runs = {}
    for path in sorted((HERE / batch).glob("*.jsonl")):
        key, rest = path.stem.split("_researcher_") if "_researcher_" in path.stem else path.stem.split("_plain_language_")
        depth = "researcher" if "_researcher_" in path.stem else "plain_language"
        runs[(key, depth, rest)] = read_run(path)
    return runs


def cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")[:600]


def per_run_table(runs: dict) -> list[str]:
    lines = [
        "| Question | Depth | Run | Written summary shown | No-summary note | Trust | Tier | Restatements dropped | Fallback | Seconds |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key in ORDER:
        for depth in ("researcher", "plain_language"):
            for rep in ("1", "2"):
                run = runs.get((key, depth, rep))
                if run is None:
                    continue
                written = " ".join(run["written"]) or "none"
                dropped = "not run" if not run["drop_ran"] else str(run["dropped"])
                lines.append(
                    f"| {key} | {depth} | {rep} | {cell(written)} | {'yes' if run['note'] else 'no'} "
                    f"| {run['trust']} | {run['tier']} | {dropped} | {'yes' if run['fallback'] else 'no'} "
                    f"| {run['t']} |"
                )
    return lines


def comparison(before: dict, after: dict) -> list[str]:
    lines = [
        "| Question | Depth | Summary shown, before | Summary shown, after | Note, before | Note, after | Trust, before | Trust, after | Tier, before | Tier, after | Median s, before | Median s, after | Slowest s, before | Slowest s, after |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key in ORDER:
        for depth in ("researcher", "plain_language"):
            pair = []
            for runs in (before, after):
                group = [runs[k] for k in sorted(runs) if k[0] == key and k[1] == depth]
                times = [r["t"] for r in group if r["t"] is not None]
                pair.append(
                    {
                        "shown": f"{sum(1 for r in group if r['written'])} of {len(group)}",
                        "note": f"{sum(1 for r in group if r['note'])} of {len(group)}",
                        "trust": ", ".join(r["trust"] for r in group),
                        "tier": ", ".join(r["tier"] for r in group),
                        "median": round(statistics.median(times), 1) if times else "",
                        "max": round(max(times), 1) if times else "",
                    }
                )
            b, a = pair
            lines.append(
                f"| {key} | {depth} | {b['shown']} | {a['shown']} | {b['note']} | {a['note']} "
                f"| {b['trust']} | {a['trust']} | {b['tier']} | {a['tier']} | {b['median']} | {a['median']} "
                f"| {b['max']} | {a['max']} |"
            )
    return lines


def main() -> None:
    runs = load(sys.argv[1])
    print("\n".join(per_run_table(runs)))
    cost = sum(r["cost"] or 0 for r in runs.values())
    print(f"\nRuns: {len(runs)}. Model spend the runs report: {cost:.4f} USD.")
    if len(sys.argv) > 2:
        print()
        print("\n".join(comparison(load(sys.argv[2]), runs)))
        print()
        for k in sorted(runs):
            if runs[k]["cited_details"]:
                print(f"- {k[0]} {k[1]} run {k[2]}: " + " / ".join(runs[k]["cited_details"]))


if __name__ == "__main__":
    main()
