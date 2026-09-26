"""Re-land answered runs over 20 s: which step carries them, and when Write starts.

Reads golden_timing.json (written by analyze_golden_timing.py). Prints the
per-run stage split for every answered run over 20 client seconds, and the
distribution of the server's time at which Write starts, the moment every
record behind the answer is already in hand.
"""
import json
import statistics
from pathlib import Path

d = json.loads((Path(__file__).parent / "golden_timing.json").read_text())


def pct(v, q):
    v = sorted(v)
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


for label in ("8.2 floor (09-25)", "8.6 re-land (09-26)"):
    runs = [r for r in d[label]["runs"] if r["outcome"] == "answered"]
    over = [r for r in runs if (r["seconds"] or 0) > 20]
    print(f"== {label}: {len(over)} of {len(runs)} answered runs over 20 s")
    biggest = {}
    for r in sorted(over, key=lambda r: -r["seconds"]):
        st = {k: r.get(k) or 0 for k in ("guardrail", "think", "act", "act_tail", "write")}
        top = max(st, key=st.get)
        biggest[top] = biggest.get(top, 0) + 1
        if label.startswith("8.6"):
            print(f"  {r['id']} p{r['pass']} {r['seconds']:5.1f}s  guard {st['guardrail']:4.1f} think {st['think']:4.1f} "
                  f"act {st['act']:5.1f} tail {st['act_tail']:4.1f} write {st['write']:5.1f}  withdrawn={r['withdrawn']}")
    print("  largest stage in those runs:", biggest)
    ws = [r["guardrail"] + r["think"] + (r.get("plan") or 0) + r["act"] + r["act_tail"] for r in runs if r.get("guardrail") is not None]
    print(f"  server time at which Write starts: median {statistics.median(ws):.1f}, p90 {pct(ws, .9):.1f}, max {max(ws):.1f}; "
          f"over 3 s: {sum(1 for w in ws if w > 3)} of {len(ws)}")
    need = [r["seconds"] - 20 for r in over]
    if need:
        print(f"  seconds each over-20 run must lose: median {statistics.median(need):.1f}, max {max(need):.1f}")
