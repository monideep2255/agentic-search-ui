"""Client seconds for answered runs in every golden run, oldest first.

The 2026-09-12 baseline kept no raw events, so only its client seconds are
comparable; the step split for the other runs is in golden_timing.md.
Output: baseline_trend_output.txt.
"""
import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parent.parent
RUNS = [
    ("09-12 baseline", "2026-09-12_consistency_baseline"),
    ("10.3 (09-22)", "2026-09-22_10.3_consistency"),
    ("8.1 (09-25)", "2026-09-25_phase_8.1_golden"),
    ("8.2 floor (09-25)", "2026-09-25_phase_8.2_golden"),
    ("8.6 first (09-26)", "2026-09-26_phase_8.6_golden"),
    ("8.6 re-land (09-26)", "2026-09-26_phase_8.6-reland_golden"),
]


def pct(v, q):
    v = sorted(v)
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


lines = ["| Run | Commit | Start (UTC) | Answered | Median s | p90 s | Max s | Over 20 s |", "|---|---|---|---|---|---|---|---|"]
for label, folder in RUNS:
    rows = [json.loads(line) for line in (REPORTS / folder / "runs.jsonl").read_text().splitlines() if line.strip()]
    ans = [r["seconds"] for r in rows if r.get("outcome") == "answered" and r.get("seconds") is not None]
    start = min((r.get("started_at") or "") for r in rows) or "n/a"
    commit = rows[0].get("deployed_commit", "n/a")
    lines.append(f"| {label} | {commit} | {start[:16]} | {len(ans)} | {pct(ans, .5):.1f} | {pct(ans, .9):.1f} | {max(ans):.1f} | {sum(1 for s in ans if s > 20)} |")
(Path(__file__).parent / "baseline_trend_output.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
