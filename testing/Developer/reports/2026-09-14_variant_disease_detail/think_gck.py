"""Run think_node alone N times on one question with the real Plan-tier model
and the live NCBI lookups, logging per run: the model's extracted spans, every
symbol lookup's result, and the symbol cache state. Writes JSONL.

Usage: python3 think_gck.py "question" out.jsonl --runs 20
"""

import argparse
import asyncio
import json
import os
import sys
import time
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

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module

lookups: list[dict] = []
spans: list[dict] = []

_orig_uncached = graph_module._resolve_symbol_to_curie_uncached
_orig_confirm = graph_module._confirm_extracted_entities


async def _spy_uncached(symbol: str, taxon: str):
    started = time.monotonic()
    try:
        result = await _orig_uncached(symbol, taxon)
    except Exception as exc:
        lookups.append({"symbol": symbol, "taxon": taxon, "exception": type(exc).__name__,
                        "wall_s": round(time.monotonic() - started, 2)})
        raise
    lookups.append({"symbol": symbol, "taxon": taxon, "curie": result[0], "cacheable": result[1],
                    "wall_s": round(time.monotonic() - started, 2)})
    return result


async def _spy_confirm(entities):
    spans.extend({"text": e.text, "entity_type": e.entity_type} for e in entities)
    return await _orig_confirm(entities)


graph_module._resolve_symbol_to_curie_uncached = _spy_uncached
graph_module._confirm_extracted_entities = _spy_confirm


async def one(question: str) -> dict:
    lookups.clear()
    spans.clear()
    cache_before = dict(graph_module._SYMBOL_CURIE_CACHE)
    query = Query(text=question, session_id=f"tk-{os.urandom(3).hex()}",
                  trace_id=f"tk-{os.urandom(4).hex()}", user_id=None, audience_depth="researcher")
    state = {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [],
        "findings_count": 0,
    }
    started = time.monotonic()
    error = None
    result = {}
    try:
        result = await graph_module.think_node(state)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"[:300]
    resolved = [
        {"text": getattr(e, "text", None), "curie": getattr(e, "curie", None)}
        for e in (result.get("resolved_entities") or [])
    ]
    events = [e for e in result.get("events", []) if getattr(e, "type", "") == "think"]
    narrative = None
    if events:
        payload = events[0].payload
        payload = payload if isinstance(payload, dict) else payload.model_dump()
        narrative = payload.get("narrative")
    return {
        "question": question,
        "elapsed_s": round(time.monotonic() - started, 2),
        "error": error,
        "spans": list(spans),
        "lookups": list(lookups),
        "resolved": resolved,
        "unresolved_refusal": result.get("unresolved_entity_refusal") is not None
        or any(k for k in result if "unresolved" in str(k)),
        "narrative": narrative,
        "cache_before": cache_before,
        "cache_after": dict(graph_module._SYMBOL_CURIE_CACHE),
        "result_keys": sorted(str(k) for k in result),
    }


def _append(out: str, line: str) -> None:
    with open(out, "a") as handle:
        handle.write(line + "\n")


async def main(question: str, runs: int, out: str) -> None:
    for index in range(runs):
        record = await one(question)
        _append(out, json.dumps(record, default=str))
        print(index + 1, json.dumps({k: record[k] for k in ("elapsed_s", "error", "spans", "lookups", "resolved")}, default=str)[:400])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out")
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(main(args.question, args.runs, args.out))
