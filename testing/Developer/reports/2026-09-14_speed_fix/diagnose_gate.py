"""Why does the repair still fire on some Researcher runs after the gate?

Wraps `_code_built_lines_will_cite` on a real run and prints, for each call,
the omitted findings the probe could NOT cite (their rendered code-built
sentence and value), so the case is stated from evidence rather than
guessed. One real run per question given on the command line.

Usage: python3 diagnose_gate.py --depth researcher "question" [...]
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

root = Path("<repo-root>")
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(root / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run import run
from system_03_search_agent.synthesis.findings import (
    build_structured_fallback_narrative,
    render_finding_body,
)
from system_03_search_agent.synthesis.grounding import run_grounding_pass

_orig = graph_module._code_built_lines_will_cite
report = []


def _spy(omitted, synth, **kw):
    result = _orig(omitted, synth, **kw)
    rendered = synth if kw["lists_every_finding"] else omitted
    probe = run_grounding_pass(build_structured_fallback_narrative(rendered), synth, core_ask_required=True, question=kw["question"])
    cited = {c.finding.citation_id for c in probe.claims}
    uncovered = [f for f in omitted if f.citation_id not in cited]
    report.append({
        "result": result, "tool_outcome": kw["tool_outcome"], "model_grounded": kw["model_grounded"],
        "omitted": len(omitted), "prepared": len(synth), "probe_claims": len(probe.claims), "probe_stripped": probe.stripped_count,
        "uncovered": [{"ref": f.ref_index, "tool": f.tool, "field": f.field, "value": f.field_value[:160], "sentence": (render_finding_body(f) + f" [{f.ref_index}].")[:200]} for f in uncovered],
    })
    return result


graph_module._code_built_lines_will_cite = _spy


async def one(question, depth):
    report.clear()
    q = Query(text=question, session_id=f"dg-{os.urandom(3).hex()}", trace_id=f"dg-{os.urandom(4).hex()}", user_id=None, audience_depth=depth)
    async for _ in run(q, RequestContext(surface="rest_sse")):
        pass
    return {"question": question, "depth": depth, "gate_calls": list(report)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("questions", nargs="+"); p.add_argument("--depth", default="researcher")
    a = p.parse_args()
    for qtext in a.questions:
        print(json.dumps(asyncio.run(one(qtext, a.depth)), indent=1))
