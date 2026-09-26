"""Does an `s3` built from an older commit still read today's event stream?

For each older commit, extract that commit's `contracts/events.py` with
`git show`, import it standalone, and validate frames shaped exactly like the
ones develop emitted today (field values from runs/rest_01 and rest_05). The
CLI client calls `Event.model_validate_json` on every frame
(adapters/cli/client.py line 883); a ValidationError on a known type becomes a
synthesized fatal decode-failure error, so the run shows as failed.
No live question is spent.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "int_tree"
OUT = HERE.parent / "int_secrets" / "old_contracts"
OUT.mkdir(parents=True, exist_ok=True)

rest01 = json.loads((HERE / "runs/rest_01_brca1_page_snippet.json").read_text())
rest05 = json.loads((HERE / "runs/rest_05_gerd.json").read_text())

done_today = {
    "type": "done", "version": "v1", "trace_id": "t" * 36, "seq": 99, "ts": "2026-09-26T21:40:00Z",
    "payload": {
        "total_cost_usd": 0.0, "total_tool_calls": 13, "elapsed_ms": 14000, "trust_outcome": "ask",
        "trust_line": rest01["done_trust_line"], "layer_calls_used": 9,
        "next_step": None, "next_step_query": None,
        "decisions": [
            {"name": d["name"], "options": ["a", "b"], "chosen": d["chosen"], "decided_by": d["decided_by"]}
            for d in rest01["done_decisions"]
        ],
    },
}
think_today = {
    "type": "think", "version": "v1", "trace_id": "t" * 36, "seq": 2, "ts": "2026-09-26T21:40:00Z",
    "payload": {"narrative": rest05["think_narratives"][0], "query_class": "lookup", "resolved_entities": [],
                "clarifying_question": rest05["clarifying_question"], "clarifying_options": rest05["clarifying_options"]},
}
step_today = {"type": "step", "version": "v1", "trace_id": "t" * 36, "seq": 5, "ts": "2026-09-26T21:40:00Z",
              "payload": {"step": "write", "status": "started"}}

commits = {
    "cd26a7a": "2026-09-22, the CLI adapter's last change",
    "537377d": "2026-09-14, the GraphQL adapter's last change",
    "20a8688": "2026-09-13, the MCP adapter's last change",
    "HEAD": "develop today",
}
rows = []
for commit, label in commits.items():
    src = subprocess.run(["git", "-C", str(TREE), "show", f"{commit}:src/system_03_search_agent/contracts/events.py"],
                         capture_output=True, text=True, check=True).stdout
    path = OUT / f"events_{commit}.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location(f"events_{commit}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    for name, frame in (("done", done_today), ("think with options", think_today), ("step", step_today)):
        try:
            mod.Event.model_validate_json(json.dumps(frame))
            verdict = "accepted"
        except Exception as exc:  # noqa: BLE001 - the verdict is the point
            first = str(exc).splitlines()
            verdict = "REJECTED: " + " | ".join(line.strip() for line in first[1:4])[:220]
        rows.append((commit, label, name, verdict))
        print(f"{commit} ({label}): {name}: {verdict}")
(HERE / "runs/old_client_compat.json").write_text(json.dumps(rows, indent=2))
