"""Bonus, one-question probe, NOT part of the 40-row bench comparison.

The main bench proved anthropic/claude-opus-5.5 cannot run under this
product's actual synth-tier policy (reasoning forced off, effort="none"):
OpenRouter rejects the call outright for that endpoint ("Reasoning is
mandatory for this endpoint and cannot be disabled."). This script asks a
narrower, separate question for the record: if reasoning were allowed
(never in the main comparison, and never a product-file change), can this
model answer at all, and at what cost and latency?

The patch touches only this process's in-memory copy of
`harness.harness._TIER_REASONING["synth"]` (also
`harness.tiers._TIER_REASONING` is not a real name; the dict lives only in
harness.py). No file on disk is written. This is not comparable to the
other 4 models' numbers, which all ran at effort="none"; it is reported
separately and labeled as such.

Usage: python3 probe_opus_reasoning_on.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

MAIN_REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

os.environ["GUARD_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PLAN_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.75"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["SYNTH_MODEL"] = "anthropic/claude-opus-5.5"

sys.path.insert(0, str(MAIN_REPO / "src"))

from system_03_search_agent.harness import harness as H

# In-process only. Not a file edit. Reverted at the end of this script's
# own run (the process exits right after, so nothing persists).
_ORIGINAL_SYNTH_REASONING = H._TIER_REASONING["synth"]
H._TIER_REASONING["synth"] = {"effort": "low"}

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

QUESTION_ID = "G-016"
QUESTION_TEXT = "What are the known orthologs of TP53 in other species?"

query = Query(
    text=QUESTION_TEXT,
    session_id=f"writer-bench2-probe-{QUESTION_ID}",
    trace_id=f"trace-writer-bench2-probe-{QUESTION_ID}",
    user_id=None,
    audience_depth="researcher",
)
context = RequestContext(surface="rest_sse", session_memory=None)


async def main() -> None:
    result = {
        "model": "anthropic/claude-opus-5.5",
        "note": "PROBE ONLY: synth reasoning effort forced to 'low' in this "
        "process's memory only, not the product default of 'none'. Not "
        "comparable to the other 40 bench rows.",
        "question_id": QUESTION_ID,
        "question": QUESTION_TEXT,
        "outcome": None,
        "trust_outcome": None,
        "errors": [],
        "citation_count": 0,
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
            result["citation_count"] += 1
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
    with open(OUT_DIR / "probe_opus_reasoning_on.jsonl", "a") as f:  # noqa: ASYNC230
        f.write(json.dumps(result, default=str) + "\n")
    print(json.dumps(result, default=str, indent=2)[:3000])


asyncio.run(main())
