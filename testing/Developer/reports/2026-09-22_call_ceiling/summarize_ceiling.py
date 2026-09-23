"""The call-ceiling measurement, fix-plan item 1 (2026-09-22, night).

For every live run in this folder: the question, the pass, the outcome, and
how many Layer 2 and 3 calls the query spent, read from the done event's
`layer_calls_used`, which counts at the transports and so includes Think's
own lookups. Then, per question, the minimum and maximum across passes
against the ceiling of twenty, and how much of each count is fixed (the
planned calls on the stream) versus outside the plan (Think's lookups and Write's disease-name resolution, the
difference). Reads `runs.jsonl` and `raw/`, writes nothing; run from the
repository root and paste the tables into `findings.md`.
"""
import collections
import json
import pathlib

CEILING = 20
folder = pathlib.Path(".") / "testing" / "Developer" / "reports" / "2026-09-22_call_ceiling"
runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]

rows = []
for run in sorted(runs, key=lambda r: (r["id"], int(r["pass"]))):
    capture = folder / "raw" / f"{run['id']}_run{run['pass']}.json"
    used = planned_layer23 = None
    refused_by_ceiling = 0
    if capture.exists():
        with capture.open() as handle:
            events = json.load(handle).get("events", [])
        for e in events:
            kind = e.get("type") or e.get("event")
            payload = e.get("payload", e)
            if kind == "done":
                used = payload.get("layer_calls_used")
            elif kind == "plan":
                planned_layer23 = sum(
                    1 for c in payload.get("tool_calls", []) if c.get("layer") in ("layer_2_api", "layer_3_enrichment")
                )
            elif kind == "tool_result" and "call ceiling" in (payload.get("summary") or ""):
                refused_by_ceiling += 1
    rows.append(
        {
            "id": run["id"], "pass": run["pass"], "outcome": run["outcome"], "seconds": run.get("seconds"),
            "used": used, "planned": planned_layer23, "refused": refused_by_ceiling,
            "question": (run.get("question") or "")[:70],
        }
    )

print("| id | pass | outcome | seconds | Layer 2 and 3 calls spent | planned on the stream | outside the plan: Think's lookups and Write's name resolution (difference) | refused by the ceiling |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    think = "-" if r["used"] is None or r["planned"] is None else r["used"] - r["planned"]
    print(f"| {r['id']} | {r['pass']} | {r['outcome']} | {r['seconds']} | {r['used']} | {r['planned']} | {think} | {r['refused']} |")

print()
print("| id | question | passes | spent, min to max | headroom under 20 at the worst pass |")
print("|---|---|---|---|---|")
by_id = collections.defaultdict(list)
for r in rows:
    by_id[r["id"]].append(r)
for gid, group in sorted(by_id.items()):
    used = [r["used"] for r in group if r["used"] is not None]
    if not used:
        print(f"| {gid} | {group[0]['question']} | {len(group)} | no count on the stream | - |")
        continue
    print(f"| {gid} | {group[0]['question']} | {len(group)} | {min(used)} to {max(used)} | {CEILING - max(used)} |")
