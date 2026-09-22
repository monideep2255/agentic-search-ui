"""Summarise the live verification runs in this folder: for every run, what the
question's own graph call returned, whether any graph call errored (which is
what puts the lost-search line under an answer), the trust outcome, the
latency and the sources by layer, plus the GEO citations for the dataset
question. Reads `runs.jsonl` and `raw/`, writes nothing; run from the
repository root and paste the table into `findings.md`.
"""
import collections
import json
import pathlib

folder = pathlib.Path(".") / "testing" / "Developer" / "reports" / "2026-09-22_item1_lost_search"
runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]

print("| id | pass | outcome | seconds | own graph call | graph calls errored | trust | sources by layer | GEO cited |")
print("|---|---|---|---|---|---|---|---|---|")
by_id: dict[str, list[dict]] = collections.defaultdict(list)
for run in sorted(runs, key=lambda r: (r["id"], int(r.get("pass", r.get("pass_index", 0))))):
    capture = folder / "raw" / f"{run['id']}_run{run.get('pass', run.get('pass_index'))}.json"
    own = "no capture"
    errored = 0
    trust = ""
    geo = 0
    if capture.exists():
        with capture.open() as handle:
            events = json.load(handle)
        events = events.get("events", events)
        plan = next((e.get("payload", e) for e in events if (e.get("type") or e.get("event")) == "plan"), None)
        results = {}
        for e in events:
            kind = e.get("type") or e.get("event")
            payload = e.get("payload", e)
            if kind == "tool_result" and payload.get("tool") == "cypher_query":
                results[payload.get("call_id")] = payload
            elif kind == "done":
                trust = payload.get("trust_outcome", "")
            elif kind == "citation" and "/gds/" in (payload.get("source_url") or ""):
                geo += 1
        errored = sum(1 for p in results.values() if p.get("status") == "error")
        if plan:
            calls = [c for c in plan.get("tool_calls", []) if c.get("tool") == "cypher_query"]
            if calls and calls[0]["call_id"] in results:
                first = results[calls[0]["call_id"]]
                own = f"{first.get('status')} {first.get('result_count')} rows"
                if first.get("status") == "error":
                    own += ": " + (first.get("summary") or "")[:90]
    layers = run.get("citations_by_layer") or {}
    layer_text = ", ".join(f"{k.replace('layer_', 'L')[:2]} {v}" for k, v in sorted(layers.items())) or "-"
    seconds = run.get("seconds", "")
    print(
        f"| {run['id']} | {run.get('pass', run.get('pass_index'))} | {run['outcome']} | {seconds} | {own} "
        f"| {errored} | {trust} | {layer_text} | {geo} |"
    )
    by_id[run["id"]].append(run)

print()
for gid, group in sorted(by_id.items()):
    answered = sum(1 for r in group if r["outcome"] == "answered")
    print(f"- {gid}: answered {answered} of {len(group)}")
