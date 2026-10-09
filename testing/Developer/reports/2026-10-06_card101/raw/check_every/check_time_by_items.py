"""Check call duration against its item count, from the recorded traces."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diag101"))
import scan_unchecked as su

by = defaultdict(list)
for _, files in su.SOURCES:
    for path in files:
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        for i, r in enumerate(rows):
            if r["tag"] == "CHECK_IN":
                out = next((o for o in rows[i + 1:] if o["tag"] in ("CHECK_OUT", "CHECK_RAISED")), None)
                if out:
                    by[int(r["data"]["n"])].append(out["t"] - r["t"])
for n in sorted(by):
    v = by[n]
    print(f"items {n:2d}: calls {len(v):2d}, median {statistics.median(v):.3f} s, max {max(v):.3f} s")
