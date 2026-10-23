"""Card 145 probe: Think's classification and confirmation only, N times.

Runs `graph._think` (the Think step without the node's side decisions)
on the bronchiolitis question with no session memory, so exactly the path
`_needs_clarification` reads: the Think classification, live confirmation
in NCBI, the fallbacks, then the ask-back gate. Records, per run, every
reading's entities, the resolved entities, whether the ask-back fired,
and whether the second reading ran (absent before card 145's change).

Usage: ASU_ENV_FILE=<path> python think_probe.py <label> <runs>
Output: raw/<label>.jsonl beside this script.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from live_env import HERE, key_usage, load_env

load_env()

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.harness import harness as harness_module

QUESTION = "What causes bronchiolitis in babies, and how is it usually treated?"
LABEL, RUNS = sys.argv[1], int(sys.argv[2])
(HERE / "raw").mkdir(exist_ok=True)
OUT = open(HERE / "raw" / f"{LABEL}.jsonl", "w")  # noqa: SIM115

readings: list[list[list[str]]] = []
_real_classify = g._run_think_classification


async def _spy_classify(*args: object, **kwargs: object) -> object:
    outcome = await _real_classify(*args, **kwargs)
    if isinstance(outcome, dict):
        readings[-1].append([f"early exit {sorted(outcome)}"])
    else:
        readings[-1].append([f"{e.text}:{e.entity_type}" for e in outcome.entities])
    return outcome


g._run_think_classification = _spy_classify


async def one(index: int) -> dict[str, object]:
    readings.append([])
    trace_id = f"c145-{LABEL}-{index}"
    query = Query(text=QUESTION, session_id=trace_id, trace_id=trace_id)
    state = {
        "query": query,
        "context": RequestContext(surface="web_ui", session_memory=None),
        "harness": harness_module.Harness(trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "events": [],
    }
    recent = asyncio.create_task(g._no_decision())
    start = time.monotonic()
    result = await g._think(state, recent)
    elapsed = round(time.monotonic() - start, 1)
    think = next((e.payload for e in result.get("events", []) if e.type == "think"), None)
    payload = think.model_dump() if think is not None and hasattr(think, "model_dump") else think
    return {
        "run": index,
        "readings": readings[-1],
        "second_reading_fired": len(readings[-1]) > 1,
        "resolved": [f"{r['text']}={r['curie']}" for r in (payload or {}).get("resolved_entities", [])],
        "asked_back": (payload or {}).get("clarifying_question") == g.CLARIFICATION_QUESTION,
        "early_exit": sorted(k for k in result if k in ("cap_exceeded", "step_error")),
        "think_s": elapsed,
    }


async def main() -> None:
    before = key_usage()
    for index in range(1, RUNS + 1):
        row = await one(index)
        OUT.write(json.dumps(row) + "\n")
        OUT.flush()
        print(json.dumps(row))
    after = key_usage()
    OUT.write(json.dumps({"spend_usd": round(after - before, 4)}) + "\n")
    print(f"spend_usd={after - before:.4f}")


asyncio.run(main())
OUT.close()
