"""Which template each golden question's own graph call takes, computed
offline from the Think output recorded in the 2026-09-22 consistency run,
beside what that call actually returned on develop that morning.

Pure functions only: no model, no graph, no network. Run from the repository
root; it writes `offline_paths.md` beside itself. The template column is
computed by the CURRENT `select_template`, so re-running it after a template
change shows the new path against the old outcome, which is how the change
in this folder was sized before it was written.
"""
import collections
import glob
import json
import os
import pathlib
import sys

root = pathlib.Path(".")
sys.path.insert(0, str(root / "src"))
os.environ.setdefault("APP_ENV", "test")

from system_03_search_agent.tools.cypher_query import (
    CypherQueryInput,
    entity_param_bindings,
)
from system_03_search_agent.tools.cypher_templates import (
    anchor_label_for,
    matched_shapes,
    select_template,
)

RUN = root / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "raw"
OUT = root / "testing" / "Developer" / "reports" / "2026-09-22_item1_lost_search" / "offline_paths.md"

golden = json.loads((root / "eval" / "golden" / "golden_dataset.json").read_text())
rows = golden if isinstance(golden, list) else next(v for v in golden.values() if isinstance(v, list))
question_by_id = {r["id"]: r["question"] for r in rows}

records: list[dict] = []
for path in sorted(glob.glob(str(RUN / "G-*_run*.json"))):
    name = os.path.basename(path)[:-5]
    gid, run = name.split("_run")
    with open(path) as handle:
        events = json.load(handle)
    events = events.get("events", events)
    think = plan = None
    results: dict[str, tuple] = {}
    for e in events:
        kind = e.get("type") or e.get("event")
        payload = e.get("payload", e)
        if kind == "think":
            think = payload
        elif kind == "plan":
            plan = payload
        elif kind == "tool_result" and payload.get("tool") == "cypher_query":
            results[payload.get("call_id")] = (payload.get("status"), payload.get("result_count"))
    if think is None:
        records.append({"id": gid, "run": run, "class": "(guardrail)", "template": "", "own": ""})
        continue
    curies = [x["curie"] for x in think.get("resolved_entities", [])]
    qclass = think.get("query_class")
    own = ""
    if plan:
        calls = [c for c in plan.get("tool_calls", []) if c.get("tool") == "cypher_query"]
        if calls and calls[0]["call_id"] in results:
            status, count = results[calls[0]["call_id"]]
            own = f"{status} {count}"
    if not curies:
        records.append({"id": gid, "run": run, "class": qclass, "template": "(no entity)", "own": own})
        continue
    tool_input = CypherQueryInput(
        query_intent=question_by_id[gid][:1000], query_class=qclass, target_entities=curies, row_limit=100
    )
    anchor = anchor_label_for(curies)
    shapes = ", ".join(matched_shapes(question_by_id[gid], anchor)) if anchor else "(mixed labels)"
    template = select_template(tool_input, entity_param_bindings(curies))
    records.append(
        {
            "id": gid, "run": run, "class": qclass, "n": len(curies), "anchor": anchor or "mixed",
            "shapes": shapes or "none", "template": template.name if template else "None (model path)",
            "own": own,
        }
    )

lines = [
    "# Template path per golden question, offline, from the 2026-09-22 consistency run",
    "",
    "Computed by `offline_paths.py` with the template chooser as it stands when the",
    "script runs; the last column is what the question's own graph call returned on",
    "develop during the morning run, before any change in this folder.",
    "",
    "| id | run | class | entities | anchor | shapes | template now | own call then |",
    "|---|---|---|---|---|---|---|---|",
]
for r in records:
    lines.append(
        f"| {r['id']} | {r['run']} | {r.get('class', '')} | {r.get('n', '')} | {r.get('anchor', '')} "
        f"| {r.get('shapes', '')} | {r.get('template', '')} | {r.get('own', '')} |"
    )
by_template = collections.Counter(r.get("template", "") for r in records)
lines += ["", "Runs per template path:", ""]
for template, count in sorted(by_template.items(), key=lambda kv: -kv[1]):
    lines.append(f"- {template or '(guardrail refusal)'}: {count}")
OUT.write_text("\n".join(lines) + "\n")
print(f"wrote {OUT} with {len(records)} runs")
