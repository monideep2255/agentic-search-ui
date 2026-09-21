"""Supplementary probe, not part of the 35-run measurement: per-tool wall
time inside the Act step, so a "slowest tool" speed proposal is measured
rather than guessed.

Same event-timestamp technique as measure_write2.py, one level deeper:
every `tool_start` and its matching `tool_result` (paired by `call_id`)
gives one tool call's own wall time, `ts(tool_result) - ts(tool_start)`.
Run AFTER the main 35-run batch finishes, never concurrently with it: two
concurrent streams already respect the NCBI rate limits per the task
brief, and a third pulls the same live APIs the main batch is measuring
and would contaminate both.

Usage: python measure_tools.py --depth researcher --runs 3 "question" out.jsonl
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

root = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")
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
from system_03_search_agent.core.run import run


async def one(question: str, depth: str) -> dict:
    query = Query(text=question, session_id=f"mt-{os.urandom(3).hex()}", trace_id=f"mt-{os.urandom(4).hex()}",
                  user_id=None, audience_depth=depth)
    starts: dict[str, tuple[str, datetime]] = {}
    tool_calls: list[dict] = []
    errors = []
    done = None
    started = time.monotonic()
    async for event in run(query, RequestContext(surface="rest_sse")):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        if event.type == "tool_start":
            starts[payload["call_id"]] = (payload.get("tool"), event.ts)
        elif event.type == "tool_result":
            call_id = payload.get("call_id")
            tool, ts_start = starts.get(call_id, (payload.get("tool"), event.ts))
            tool_calls.append({
                "tool": tool, "status": payload.get("status"),
                "wall_s": round((event.ts - ts_start).total_seconds(), 3),
            })
        elif event.type == "done":
            done = payload
        elif event.type == "error":
            errors.append({k: payload.get(k) for k in ("fatal", "scope", "source", "error_class")})
    elapsed = round(time.monotonic() - started, 1)
    return {
        "question": question, "depth": depth, "elapsed_s": elapsed,
        "outcome": (done or {}).get("trust_outcome"), "errors": errors,
        "tool_calls": tool_calls,
    }


def _append_line(out: str, line: str) -> None:
    with open(out, "a") as handle:
        handle.write(line + "\n")


async def main(question: str, depth: str, runs: int, out: str) -> None:
    for _ in range(runs):
        result = await one(question, depth)
        _append_line(out, json.dumps(result))
        print(json.dumps(result)[:500])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out")
    parser.add_argument("--depth", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.question, args.depth, args.runs, args.out))
