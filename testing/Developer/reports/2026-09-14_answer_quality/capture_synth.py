"""Run one question live and record the EXACT synthesis messages handed to
the Synth tier, plus the reply, plus the rendered answer tokens.

Usage: python capture_synth.py --depth plain_language "question" out.json
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

captured: dict = {"synth_calls": []}
_orig_dispatch = graph_module._dispatch_tier_call


async def _spy(harness, trace_id, tier, step, messages, **kwargs):
    response = await _orig_dispatch(harness, trace_id, tier, step, messages, **kwargs)
    if tier == "synth":
        captured["synth_calls"].append(
            {"messages": messages, "reply": graph_module._response_text(response)}
        )
    return response


graph_module._dispatch_tier_call = _spy


async def main(question: str, depth: str, out: str) -> None:
    query = Query(
        text=question,
        session_id=f"cap-{depth}",
        trace_id=f"cap-{os.urandom(4).hex()}",
        user_id=None,
        audience_depth=depth,
    )
    tokens = []
    citations = []
    done = None
    async for event in run(query, RequestContext(surface="rest_sse")):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        if event.type == "token":
            tokens.append(payload)
        elif event.type == "citation":
            citations.append(payload)
        elif event.type == "done":
            done = payload
    captured["tokens"] = tokens
    captured["citations"] = citations
    captured["done"] = done
    Path(out).write_text(json.dumps(captured, indent=1, default=str))
    print("tokens", len(tokens), "citations", len(citations), "synth_calls", len(captured["synth_calls"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out")
    parser.add_argument("--depth", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.question, args.depth, args.out))
