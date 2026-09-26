"""Run one question N times at one depth with the real models and graph, and
print one JSON line per run with: outcome, errors, total elapsed, and for
EVERY synth call its wall time, prompt/completion tokens, and whether it was
the repair call. Also the answer's first sentence, word count, headings,
list rows, sources, and unmarked claims, so the same line serves the
live-run table.

Copy of testing/Developer/reports/2026-09-14_answer_quality/measure_write.py,
extended additively (2026-09-14, synth-effort-none measurement) with one more
field: `step_seconds`, a per-step wall-time breakdown (guard, think, plan,
act, write) derived from each yielded event's own `ts` (set at emit time,
core/graph.py's `_EventSink.emit`), not from wrapping the node functions.
Wrapping was tried and rejected: `_build_graph()` calls `add_node("guardrail",
guardrail_node)` with the bare function object at IMPORT time inside
core/graph.py itself, so monkeypatching `graph_module.guardrail_node` (etc.)
after import never reaches the compiled graph, which already closed over the
original function. Event timestamps are stamped at the moment each step's
own event is constructed, which is the natural per-step boundary the run
already produces: the first `guard`/`think`/`plan` event marks that step's
end, the last `tool_start`/`tool_result` marks Act's end, and `done` (or the
last event, if the run ended in an error before `done`) marks Write's end.
`wall_start`, captured immediately before iterating `run()`'s events, anchors
Guard's own start.

Usage: python measure_write.py --depth researcher --runs 5 "question" out.jsonl
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
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

_MARKER = re.compile(r"\s*\[\d{1,3}\]")
synth_calls: list[dict] = []
_orig = graph_module._dispatch_tier_call


async def _spy(harness, trace_id, tier, step, messages, **kwargs):
    started = time.monotonic()
    record = {"tier": tier, "step": step, "repair": "COMPLETENESS CORRECTION" in messages[-1]["content"]}
    try:
        response = await _orig(harness, trace_id, tier, step, messages, **kwargs)
    except Exception as exc:
        record.update(wall_s=round(time.monotonic() - started, 1), exception=type(exc).__name__,
                      error_class=getattr(exc, "error_class", None))
        if tier == "synth":
            synth_calls.append(record)
        raise
    record["wall_s"] = round(time.monotonic() - started, 1)
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    record["response_type"] = type(response).__name__
    record["prompt_tokens"] = getattr(usage, "prompt_tokens", None) or (usage or {}).get("prompt_tokens") if usage is not None else None
    record["completion_tokens"] = getattr(usage, "completion_tokens", None) or (usage or {}).get("completion_tokens") if usage is not None else None
    if tier == "synth":
        record["reply_words"] = len(graph_module._response_text(response).split())
        synth_calls.append(record)
    return response


graph_module._dispatch_tier_call = _spy


def _step_seconds(markers: list[tuple[str, datetime | None]]) -> dict[str, float | None]:
    """Deltas between consecutive present markers, keyed by the later step.

    `markers` is the fixed ordered sequence [("start", wall_start),
    ("guard", ts_guard), ("think", ts_think), ("plan", ts_plan),
    ("act", ts_act_last), ("write", ts_write_end)]. A step whose own marker
    or whose predecessor's marker is missing (a run that refused before
    reaching that step, or a run with no tool call so `act`'s marker equals
    `plan`'s) reports None rather than a fabricated zero or a wrong delta
    across a skipped step.
    """
    out: dict[str, float | None] = {}
    prev_ts = None
    for name, ts in markers:
        if name == "start":
            prev_ts = ts
            continue
        if ts is None or prev_ts is None:
            out[name] = None
            continue
        out[name] = round((ts - prev_ts).total_seconds(), 3)
        prev_ts = ts
    return out


async def one(question: str, depth: str) -> dict:
    synth_calls.clear()
    query = Query(text=question, session_id=f"mw-{os.urandom(3).hex()}", trace_id=f"mw-{os.urandom(4).hex()}",
                  user_id=None, audience_depth=depth)
    tokens, sources, errors, tools = [], [], [], []
    done = None
    ts_guard = ts_think = ts_plan = ts_act_last = ts_final = None
    wall_start = datetime.now(UTC)
    started = time.monotonic()
    async for event in run(query, RequestContext(surface="rest_sse")):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        if event.type == "guard" and ts_guard is None:
            ts_guard = event.ts
        elif event.type == "think" and ts_think is None:
            ts_think = event.ts
        elif event.type == "plan" and ts_plan is None:
            ts_plan = event.ts
        elif event.type in ("tool_start", "tool_result"):
            ts_act_last = event.ts
        ts_final = event.ts
        if event.type == "token":
            tokens.append(payload)
        elif event.type == "citation":
            sources.append(payload["source_id"])
        elif event.type == "tool_result":
            tools.append(f"{payload.get('tool')}:{payload.get('status')}")
        elif event.type == "done":
            done = payload
        elif event.type == "error":
            errors.append({k: payload.get(k) for k in ("fatal", "scope", "source", "error_class", "message")})
    elapsed = round(time.monotonic() - started, 1)
    step_seconds = _step_seconds([
        ("start", wall_start),
        ("guard", ts_guard),
        ("think", ts_think),
        ("plan", ts_plan),
        ("act", ts_act_last if ts_act_last is not None else ts_plan),
        ("write", ts_final),
    ])
    claims = [t for t in tokens if t.get("kind") in ("claim", "list_item", "table_row", None)]
    words = 0
    for t in claims:
        shown = " / ".join(t.get("cells") or []) if t.get("kind") in ("list_item", "table_row") else _MARKER.sub("", t["text"])
        words += len(shown.split())
    first = next((_MARKER.sub("", t["text"]).strip() for t in tokens if t.get("kind") in ("claim", None)), "")
    return {
        "question": question, "depth": depth, "elapsed_s": elapsed,
        "outcome": (done or {}).get("trust_outcome"), "trust_line": (done or {}).get("trust_line"),
        "done": done is not None, "errors": errors, "tools": tools,
        "synth_calls": list(synth_calls),
        "first_sentence": first[:300], "words": words,
        "headings": [t["text"].strip() for t in tokens if t.get("kind") == "heading"],
        "list_rows": sum(1 for t in tokens if t.get("kind") in ("list_item", "table_row")),
        "unmarked_claims": sum(1 for t in claims if not t["marker_ids"]),
        "sources": sorted(set(sources)),
        "source_count": len(set(sources)),
        "step_seconds": step_seconds,
        "has_source_url_sentence": any("source URL" in t["text"] or "source_url" in t["text"] for t in tokens),
        "raw_medgen_in_words": any(re.search(r"MedGen:C\d", _MARKER.sub("", t["text"])) for t in claims
                                   if t.get("kind") in ("claim", None)),
        "claim_texts": [t["text"] for t in tokens if t.get("kind") in ("claim", None)][:40],
    }


def _append_line(out: str, line: str) -> None:
    with open(out, "a") as handle:
        handle.write(line + "\n")


async def main(question: str, depth: str, runs: int, out: str) -> None:
    for _ in range(runs):
        result = await one(question, depth)
        _append_line(out, json.dumps(result))
        print(json.dumps({k: result[k] for k in ("elapsed_s", "outcome", "errors", "source_count", "first_sentence", "step_seconds")})[:500])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out")
    parser.add_argument("--depth", required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.question, args.depth, args.runs, args.out))
