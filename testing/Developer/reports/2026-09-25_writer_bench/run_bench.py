"""Writer-tier (synth) bench runner for card 10, 2026-09-25.

Product-owner decision (DECISIONS.md, 2026-09-25): bench the writing tier
locally on golden questions against GLM 5.2 (develop's current writer) plus
two open-weight models and one closed frontier model, with the per-query
cost cap raised for this local bench only.

Modeled on
testing/Developer/reports/2026-09-25_phase_8.1/builder_a_live_run.py, but
runs against the MAIN CHECKOUT's own src/ (this is a bench of develop's
current code, not a worktree fix), loads .env without ever printing a
value, and runs one model x one question per invocation, sequentially
across every (model, question) pair, appending one JSON line per run to
results.jsonl in this same directory.

Usage:
    python3 run_bench.py <model_id> <question_id>

GUARD_MODEL and PLAN_MODEL are pinned to develop's deepseek/deepseek-v4-flash
in this process only. PER_QUERY_COST_CAP_USD is raised to 0.50 in this
process only. Nothing here edits .env or any product file.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

MAIN_REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent

# Load .env from the main checkout without ever printing a value.
for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Bench-only overrides, this process only. Never written to .env or any
# other file.
os.environ["GUARD_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PLAN_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.50"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

model_id = sys.argv[1]
question_id = sys.argv[2]
question_text = sys.argv[3]

os.environ["SYNTH_MODEL"] = model_id

# The main checkout's own src, since this benches develop's current code.
sys.path.insert(0, str(MAIN_REPO / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext  # noqa: E402
from system_03_search_agent.core.run import run  # noqa: E402

query = Query(
    text=question_text,
    session_id=f"writer-bench-{question_id}",
    trace_id=f"trace-writer-bench-{question_id}-{model_id.replace('/', '-')}",
    user_id=None,
    audience_depth="researcher",
)
context = RequestContext(surface="rest_sse", session_memory=None)


async def main() -> None:
    result = {
        "model": model_id,
        "question_id": question_id,
        "question": question_text,
        "outcome": None,
        "trust_outcome": None,
        "errors": [],
        "citation_count": 0,
        "citation_sources": [],
        "cost_usd": None,
        "elapsed_s": None,
        "answer_text": "",
    }
    started = time.monotonic()
    async for e in run(query, context):
        if e.type == "error":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            result["errors"].append(p.get("message"))
        elif e.type == "citation":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            result["citation_count"] += 1
            result["citation_sources"].append(p.get("source"))
        elif e.type == "cost":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            result["cost_usd"] = p.get("query_cost_usd")
        elif e.type == "token":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            result["answer_text"] += p.get("text") or ""
        elif e.type == "done":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            result["trust_outcome"] = p.get("trust_outcome")
            result["outcome"] = "answered" if p.get("trust_outcome") == "answer" else p.get("trust_outcome")
    result["elapsed_s"] = round(time.monotonic() - started, 1)
    with open(OUT_DIR / "results.jsonl", "a") as f:
        f.write(json.dumps(result, default=str) + "\n")
    print(
        f"[DONE] model={model_id} q={question_id} outcome={result['outcome']} "
        f"cost={result['cost_usd']} elapsed={result['elapsed_s']}s "
        f"citations={result['citation_count']} chars={len(result['answer_text'])}"
    )


asyncio.run(main())
