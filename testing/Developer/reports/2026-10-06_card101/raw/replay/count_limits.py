"""Card 101 replay: approved sentences that drop "young" from "young
children" or the hedge from "potentially attributable", in card 99's item
and pair runs and in this folder's pair runs. No model call. Usage, from the
repository root: python testing/Developer/reports/2026-10-06_card101/raw/replay/count_limits.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parents[2]
OLD = REPORTS / "2026-10-06_card99/raw/live_ab"
RAW = REPORTS / "2026-10-05_wave3/sentence_check_raw"
HEDGE = re.compile(r"\b(potential\w*|may|might|possibl\w*|could|suspect\w*|likely|can be|perhaps)\b", re.IGNORECASE)


def texts() -> dict:
    out = {}
    for path in sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl")):
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        for n, d in enumerate([r["data"] for r in rows if r["tag"] == "CHECK_IN"], start=1):
            for i, it in enumerate(d["items"], start=1):
                out[f"{path.stem}c{n}i{i}"] = it
    return out


def classes(it: dict) -> list[str]:
    s, q = it["sentence"].lower(), " ".join(it["quotes"]).lower()
    found = []
    if "young children" in q and re.search(r"\bchildren", s) and "young" not in s:
        found.append("young_dropped")
    if "potentially attributable" in q and not HEDGE.search(s):
        found.append("hedge_dropped")
    if "potentially attributable" in q and HEDGE.search(s):
        found.append("hedge_kept")
    return found


def main() -> None:
    t = texts()
    for name, folder, arm in (("card99 item", OLD, "item"), ("card99 pair", OLD, "pair"), ("card101 pair", HERE, "pair")):
        for rep in (1, 2):
            approved = set()
            for line in (folder / f"run_{arm}_{rep}.jsonl").read_text().splitlines():
                approved |= set(json.loads(line)["approved"])
            counts = {"young_dropped": [], "hedge_dropped": [], "hedge_kept": []}
            for cid in sorted(approved):
                for c in classes(t[cid]):
                    counts[c].append(cid)
            print(name, rep, {k: len(v) for k, v in counts.items()}, counts["young_dropped"] + counts["hedge_dropped"])


if __name__ == "__main__":
    main()
