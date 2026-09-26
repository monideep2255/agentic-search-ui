"""P01: what written prose the floor run kept where the re-land shows the withdrawn note.

Offline, over the saved answer texts. For every answered run, the prose is the
text after the code-built opening line and before the first code-built
listing heading ("... records found") or note. A run is "withdrawn" when its
answer carries the structured-fallback note. For each question whose
withdrawn count rose, prints the floor run's kept prose sentences, so each
loss can be classed: the "MedGen lists no clinical features" sentence that
T-8.6-06 removed on purpose, or other written prose.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

REPORTS = Path(__file__).resolve().parent.parent
RUNS = {"floor": "2026-09-25_phase_8.2_golden", "reland": "2026-09-26_phase_8.6-reland_golden"}
NOTE = "could not be verified against them"


def prose(answer):
    paras = [p.strip() for p in answer.split("\n\n") if p.strip()]
    out = []
    for p in paras[1:]:
        if re.search(r"records found$", p) or p.startswith(("Note:", "Where this answer")):
            break
        out.append(p)
    return " ".join(out)


data = {}
for key, folder in RUNS.items():
    per = defaultdict(list)
    for f in (REPORTS / folder / "raw").glob("G-*_run*.json"):
        d = json.loads(f.read_text())
        r = d["record"]
        if r.get("outcome") != "answered":
            continue
        a = d.get("answer_text") or ""
        per[r["id"]].append({"pass": r.get("pass") or r.get("run"), "withdrawn": NOTE in a, "prose": prose(a)})
    data[key] = per

rose, fell = [], []
for qid in sorted(set(data["floor"]) | set(data["reland"])):
    f = sum(x["withdrawn"] for x in data["floor"].get(qid, []))
    r = sum(x["withdrawn"] for x in data["reland"].get(qid, []))
    if r > f:
        rose.append((qid, f, r))
    elif r < f:
        fell.append((qid, f, r))
print("withdrawn totals: floor", sum(x["withdrawn"] for v in data["floor"].values() for x in v),
      "reland", sum(x["withdrawn"] for v in data["reland"].values() for x in v))
print("rose:", rose)
print("fell:", fell)
classes = defaultdict(int)
for qid, f, r in rose:
    print(f"\n== {qid}: floor {f} withdrawn, re-land {r}")
    for x in sorted(data["floor"].get(qid, []), key=lambda x: x["pass"]):
        if not x["withdrawn"]:
            s = x["prose"]
            only_features = bool(s) and all("lists no clinical features" in t for t in re.split(r"(?<=\])\s+", s) if t.strip())
            cls = "features sentence only (T-8.6-06)" if only_features else ("no prose" if not s else "other written prose")
            classes[cls] += 1
            print(f"  floor pass {x['pass']} kept [{cls}]: {s[:260]}")
print("\nfloor runs that kept a summary on the rising questions, by what they kept:", dict(classes))
