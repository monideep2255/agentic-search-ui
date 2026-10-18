"""Card 56 probe: Guardrail, Think and Plan only, for one question, N runs,
under a chosen PLAN_MODEL. Prints what Think's classification tagged and
where the run ended. No Act, no Write, nothing written anywhere."""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]  # the checkout root
QUESTION = sys.argv[1]
PLAN_MODEL = sys.argv[2]
RUNS = int(sys.argv[3])

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "testing/Developer/scripts"))

import compare_classifiers as cc

# This checkout's .env, else the main checkout's for a git worktree; no value printed.
cc._load_env()
os.environ["PLAN_MODEL"] = PLAN_MODEL
os.environ["CLASSIFIER_PROVIDER"] = os.environ.get("PROBE_CLASSIFIER", "jev")
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.harness.call_budget import query_budget_scope
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.observability.audit import trace_id_scope

captured = {}
orig = g._run_think_classification


async def wrapped(*a, **kw):
    out = await orig(*a, **kw)
    captured["c"] = out
    return out


g._run_think_classification = wrapped


async def main():
    steps = cc._guardrail_think_plan(g)
    for i in range(RUNS):
        captured.clear()
        tid = f"probe56-{uuid.uuid4().hex[:8]}"
        h = Harness(trace_id=tid)
        q = Query(text=QUESTION, session_id=f"probe56-{i}", trace_id=tid, user_id=None,
                  audience_depth="researcher")
        st = {"query": q, "context": RequestContext(surface="rest_sse", session_memory=None),
              "harness": h, "seq": 0, "events": [], "start_monotonic": time.monotonic()}
        t0 = time.monotonic()
        with trace_id_scope(tid), query_budget_scope("lookup"):
            try:
                fs = await steps.ainvoke(st)
                ended = cc._ended(fs)
            except Exception as exc:  # noqa: BLE001
                fs, ended = {}, f"error {type(exc).__name__}: {exc}"[:200]
        c = captured.get("c")
        ents = [(e.text, e.entity_type) for e in getattr(c, "entities", [])] if c is not None else None
        calls = [
            f"{getattr(tc, 'tool_name', getattr(tc, 'tool', '?'))}" for tc in (fs.get("tool_calls") or [])
        ]
        resolved = [getattr(r, "curie", str(r)) for r in (fs.get("resolved_entities") or [])]
        print(json.dumps({
            "run": i + 1, "model": PLAN_MODEL, "secs": round(time.monotonic() - t0, 1),
            "class": getattr(c, "query_class", None), "record_type": getattr(c, "record_type", None),
            "entities": ents, "resolved": resolved, "ended": ended, "tools": calls,
            "cost": round(h.get_query_cost_usd(tid), 4), "step_error": str(fs.get("step_error"))[:300],
            # Round 2: what the person is told when nothing is planned, and
            # whether any MedGen record was bound.
            "unresolved": fs.get("unresolved_entity_symbols"),
            "clarification": (fs.get("clarification_needed") or "")[:120] or None,
            "medgen": [r for r in resolved if r.startswith("MedGen:")],
            "conditions_not_applied": list(
                getattr(fs.get("organism_records"), "conditions_not_applied", ()) or ()
            ),
        }), flush=True)


asyncio.run(main())
