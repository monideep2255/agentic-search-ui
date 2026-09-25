"""Tabulate Jev against the guard tier from a golden run's saved done events."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

raw = Path(sys.argv[1]) / "raw"
by_point = defaultdict(Counter)
disagreements = defaultdict(list)
for f in sorted(raw.glob("*.json")):
    data = json.loads(f.read_text())
    events = data.get("events") if isinstance(data, dict) else data
    if not isinstance(events, list):
        continue
    for e in events:
        if not isinstance(e, dict) or e.get("type") != "done":
            continue
        for d in (e.get("payload") or {}).get("decisions") or []:
            name = d.get("name")
            c = by_point[name]
            c["decisions"] += 1
            c[f"decided_by_{d.get('decided_by')}"] += 1
            if d.get("fallback_reason"):
                c["reason:" + str(d.get("fallback_reason")).split(":")[0]] += 1
            g, j = d.get("guard_choice"), d.get("jev_choice")
            if g is not None and j is not None:
                c["both_picked"] += 1
                if g == j:
                    c["agreed"] += 1
                else:
                    disagreements[name].append((f.stem, j, d.get("jev_confidence"), g))
for name, c in sorted(by_point.items()):
    print(name, dict(c))
    for row in disagreements[name][:6]:
        print("   disagree:", row)
