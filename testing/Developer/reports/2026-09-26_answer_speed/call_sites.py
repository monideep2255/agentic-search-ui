"""Per call site: how many calls, median, range, over the eight local traces.

Writer calls are split into the first reply and the repair by order within a
question. Output: call_sites_output.txt.
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

here = Path(__file__).parent
by = defaultdict(list)
for f in sorted((here / "local_traces").glob("G-*.json")):
    d = json.loads(f.read_text())
    n = 0
    for m in d["rec"]["model"]:
        site = m["site"]
        if site == "write: synth":
            n += 1
            site = "write: writer, first reply" if n == 1 else "write: writer, repair"
        by[site[:60]].append(m["dur"])
    for j in d["rec"]["jev"]:
        by["jev: " + j["kind"]].append(j["dur"])
    for x in d["rec"]["reader"]:
        by["act: reader pass"].append(x["dur"])
    for w in d["rec"]["write"]:
        if w["what"].startswith("resolve"):
            by["write: " + w["what"]].append(w["dur"])
    for g in d.get("guard_sentence_check") or []:
        by["comparison only: guard-tier sentence judge"].append(g["dur"])
lines = ["| Call site | Calls | Median s | Min s | Max s |", "|---|---|---|---|---|"]
for k, v in sorted(by.items()):
    lines.append(f"| {k} | {len(v)} | {statistics.median(v):.2f} | {min(v):.2f} | {max(v):.2f} |")
(here / "call_sites_output.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
