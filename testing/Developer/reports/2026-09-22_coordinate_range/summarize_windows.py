"""Summarise the live window runs in this folder: for every run, the outcome,
the entities Think resolved, the clarifying question if one was asked, what
each overlap call returned (status, records shown, total overlapping), the
trust outcome, the sources by layer and the latency. Reads `runs.jsonl` and
`raw/`, writes nothing; run from the repository root and paste the table
into `findings.md`.
"""
import json
import pathlib

folder = pathlib.Path(".") / "testing" / "Developer" / "reports" / "2026-09-22_coordinate_range"
runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]

print("| id | pass | outcome | seconds | resolved | asked | ClinVar overlap | dbVar overlap | own graph call | trust | sources by layer |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for run in sorted(runs, key=lambda r: (r["id"], int(r["pass"]))):
    capture = folder / "raw" / f"{run['id']}_run{run['pass']}.json"
    resolved = asked = clinvar = dbvar = own = trust = "-"
    if capture.exists():
        with capture.open() as handle:
            events = json.load(handle).get("events", [])
        plan = next((e.get("payload", e) for e in events if (e.get("type") or e.get("event")) == "plan"), None)
        starts: dict[str, dict] = {}
        results: dict[str, dict] = {}
        for e in events:
            kind = e.get("type") or e.get("event")
            payload = e.get("payload", e)
            if kind == "think":
                names = [x.get("text") for x in payload.get("resolved_entities", [])]
                resolved = ", ".join(names[:6]) + (" ..." if len(names) > 6 else "") if names else "none"
                if payload.get("clarifying_question"):
                    asked = "assembly question" if "assembly" in payload["clarifying_question"] else "other"
            elif kind == "tool_start":
                starts[payload.get("call_id")] = payload
            elif kind == "tool_result":
                results[payload.get("call_id")] = payload
            elif kind == "done":
                trust = payload.get("trust_outcome", "-")
        if plan:
            calls = plan.get("tool_calls", [])
            graph_calls = [c for c in calls if c.get("tool") == "cypher_query"]
            if graph_calls and graph_calls[0]["call_id"] in results:
                first = results[graph_calls[0]["call_id"]]
                own = f"{first.get('status')} {first.get('result_count')} rows"
            # The overlap calls are planned at index 1 and 2, both ncbi_efetch; their
            # summaries read "coordinate_overlap: N record(s)".
            overlap = [
                results[c["call_id"]]
                for c in calls[1:3]
                if c.get("tool") == "ncbi_efetch" and c["call_id"] in results
                and "coordinate_overlap" in (results[c["call_id"]].get("summary") or "")
            ]
            if len(overlap) == 2:
                clinvar = f"{overlap[0].get('status')} {overlap[0].get('result_count')}"
                dbvar = f"{overlap[1].get('status')} {overlap[1].get('result_count')}"
            elif overlap:
                clinvar = f"{overlap[0].get('status')} {overlap[0].get('result_count')}"
    layers = run.get("citations_by_layer") or {}
    layer_text = ", ".join(f"{k.replace('layer_', 'L')[:2]} {v}" for k, v in sorted(layers.items())) or "-"
    print(
        f"| {run['id']} | {run['pass']} | {run['outcome']} | {run.get('seconds', '')} | {resolved} | {asked} "
        f"| {clinvar} | {dbvar} | {own} | {trust} | {layer_text} |"
    )
