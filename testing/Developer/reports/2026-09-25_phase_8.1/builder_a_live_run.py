"""Builder A's local live-run script for phase 8.1, T-8.1-01 and T-8.1-02.

Modeled on `testing/Developer/scripts/local_loop_run.py`, but that script
hardcodes the MAIN repository as `root` and would import the main
checkout's `src/`, not this worktree's fixed code. This copy loads
environment variables (never prints them) from the main repository's
`.env`, and puts THIS WORKTREE's `src/` first on `sys.path` so the fix
under test is the one that actually runs.

Usage: python3 builder_a_live_run.py "<question text>" [--plain]
Depth is always researcher (what the ticket asks us to prove), no session
memory (a bare first-turn question, exactly how the two failing questions
were run live).
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

MAIN_REPO = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")  # local-refs: allow
WORKTREE_SRC = Path(__file__).resolve().parents[4] / "src"

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

# This worktree's src FIRST, so the fixed code under test runs, not the
# main checkout's.
sys.path.insert(0, str(WORKTREE_SRC))

from system_03_search_agent.contracts.query import Query, RequestContext  # noqa: E402
from system_03_search_agent.core.run import run  # noqa: E402

text = sys.argv[1] if len(sys.argv) > 1 else "What variants cause it?"
query = Query(
    text=text,
    session_id="builder-a-local",
    trace_id="trace-builder-a-local",
    user_id=None,
    audience_depth="researcher",
)
context = RequestContext(surface="rest_sse", session_memory=None)


async def main() -> None:
    summary = {
        "question": text,
        "outcome": None,
        "errors": [],
        "citation_count": 0,
        "cost_usd": None,
        "elapsed_s": None,
    }
    started = time.monotonic()
    async for e in run(query, context):
        if e.type == "error":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            summary["errors"].append(p.get("message"))
            print("[error]", json.dumps(p, default=str)[:500])
        elif e.type == "citation":
            summary["citation_count"] += 1
        elif e.type == "cost":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            summary["cost_usd"] = p.get("query_cost_usd")
        elif e.type == "done":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            summary["outcome"] = p.get("trust_outcome")
    summary["elapsed_s"] = round(time.monotonic() - started, 1)
    print("[RUN_SUMMARY]", json.dumps(summary, default=str))


asyncio.run(main())
