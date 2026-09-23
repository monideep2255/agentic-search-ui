"""Item 12.9: trace one question through Write at both depths and print what
each stage RECEIVES and EMITS, so the first stage whose output does not change
with the depth can be named by execution rather than by reading.

Wraps, in `core.graph`'s own namespace:
- `build_synth_messages`, the depth directive's only assembly point
- `run_grounding_pass`, whose FIRST call receives the model's own narrative,
  which is how the model's reply is captured without wrapping the async
  dispatcher (wrapping that one crashed the run)
- `run_grounding_pass`, every call, so the strip is visible

Run from the repository root, ONE question at a time (shared NCBI rate pools):
    python testing/Developer/reports/2026-09-23_set12/probe_depth_stages.py "reflux disease"
"""
import asyncio
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as G
from system_03_search_agent.core.run import run

OUT = pathlib.Path(__file__).parent / "probe_depth_stages"
OUT.mkdir(exist_ok=True)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


async def trace_one(question: str, depth: str) -> dict:
    record: dict = {"question": question, "depth": depth, "stages": []}

    real_messages = G.build_synth_messages
    real_ground = G.run_grounding_pass

    def wrapped_messages(*args, **kwargs):
        messages = real_messages(*args, **kwargs)
        user = messages[1]["content"]
        record["stages"].append({
            "stage": "build_synth_messages",
            "depth_arg": args[2] if len(args) > 2 else kwargs.get("audience_depth"),
            "system_sha": digest(messages[0]["content"]),
            "user_sha": digest(user),
            "user_chars": len(user),
            "directive_first_line": user.split("\n", 1)[0][:160],
        })
        return messages

    def wrapped_ground(narrative, findings, **kwargs):
        result = real_ground(narrative, findings, **kwargs)
        record["stages"].append({
            "stage": "run_grounding_pass",
            "in_sha": digest(narrative or ""),
            "in_chars": len(narrative or ""),
            "in_text": narrative,
            "claims": len(result.claims),
            "stripped": result.stripped_count,
            "refused": result.refused,
            "out_sha": digest("".join(result.sentences)),
        })
        return result

    G.build_synth_messages = wrapped_messages
    G.run_grounding_pass = wrapped_ground
    try:
        query = Query(
            text=question,
            session_id=f"probe129-{depth}",
            trace_id=f"probe129-{os.urandom(4).hex()}",
            user_id=None,
            audience_depth=depth,
        )
        tokens = []
        async for event in run(query, RequestContext(surface="rest_sse")):
            payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
            if event.type == "token":
                tokens.append({"kind": payload.get("kind"), "text": payload["text"], "cells": payload.get("cells")})
            elif event.type in ("error", "done"):
                record.setdefault("tail_events", []).append({"type": event.type, "payload": payload})
        record["tokens"] = tokens
        rendered = "".join(
            (" / ".join(t["cells"] or []) if t["cells"] else t["text"]) for t in tokens
        )
        record["rendered_sha"] = digest(rendered)
        record["rendered_chars"] = len(rendered)
        record["rendered"] = rendered
    finally:
        G.build_synth_messages = real_messages
        G.run_grounding_pass = real_ground
    return record


async def main() -> None:
    question = sys.argv[1]
    slug = "".join(c if c.isalnum() else "_" for c in question)[:40]
    for depth in ("plain_language", "researcher"):
        record = await trace_one(question, depth)
        (OUT / f"{slug}_{depth}.json").write_text(json.dumps(record, indent=2, default=str))
        print(f"--- {depth}")
        for stage in record["stages"]:
            print("   ", json.dumps({k: v for k, v in stage.items() if k != "in_text"}, default=str))
        print("    rendered", record["rendered_sha"], record["rendered_chars"], "chars")


asyncio.run(main())
