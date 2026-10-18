"""Card 101 round 2 adversary: how often a recorded first grounding pass with
candidates met a check budget below the floor, or ran with a short budget.
No model call. Reads the recorded traces only."""
import json
import os
from pathlib import Path

SP = Path(os.environ["SCRATCH"])
REPO = Path(os.environ["MAIN_CHECKOUT"] + "/testing/Developer/reports")
SOURCES = {
    "wave3 branch": sorted((REPO / "2026-10-05_wave3/sentence_check_raw").glob("*.jsonl")),
    "wave3 develop": sorted((REPO / "2026-10-05_wave3/sentence_check_raw/develop_control").glob("*.jsonl")),
    "c101 build": sorted((SP / "live").glob("*.jsonl")),
    "c101 fix round": sorted((SP / "out").glob("*.jsonl")),
    "c101 round 2 live": sorted((SP / "card101b/live").glob("*.jsonl")),
}
budgets = []
skipped = []
for name, files in SOURCES.items():
    for p in files:
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        for i, r in enumerate(rows):
            if r["tag"] != "GROUNDING":
                continue
            cc = r["data"].get("candidates_collected")
            if cc in (None, "None") or int(cc) == 0:
                continue
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if nxt and nxt["tag"] == "CHECK_IN":
                budgets.append((float(nxt["data"]["budget_s"]), name, p.stem))
            else:
                skipped.append((name, p.stem, cc, nxt["tag"] if nxt else None))
print("first passes with candidates:", len(budgets) + len(skipped))
print("check ran:", len(budgets), " check skipped:", len(skipped))
for s in skipped:
    print("  skipped", s)
short = sorted(b for b in budgets if b[0] < 12.0)
print("check budgets below the 12 s cap (budget_s = write budget left - 1):")
for b in short:
    print("  ", b)
