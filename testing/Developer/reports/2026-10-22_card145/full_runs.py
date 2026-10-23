"""Card 145 full live runs through `core.run.run_streaming()`, the web app's path.

Each run is a first question (no session memory) with `reads_placement=True`
under develop's pinned settings and the 25-cent per-question cap
(`live_env.load_env`). Per run it records: whether it answered or asked
back, seconds to the first answer token and to `done`, the number of Think
classification calls, and whether card 145's second reading ran.

Usage: ASU_ENV_FILE=<path> python full_runs.py <label> <bronch|brca1|q1> <runs>
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
from system_03_search_agent.core.run import run_streaming

QUESTIONS = {
    "bronch": (
        "What causes bronchiolitis in babies, and how is it usually treated?",
        "plain_language",
    ),
    "brca1": ("What does the BRCA1 gene do?", "researcher"),
    "q1": ("Which diseases are associated with BRCA1?", "researcher"),
}
LABEL, WHICH, RUNS = sys.argv[1], sys.argv[2], int(sys.argv[3])
TEXT, DEPTH = QUESTIONS[WHICH]
(HERE / "raw").mkdir(exist_ok=True)
OUT = open(HERE / "raw" / f"{LABEL}.jsonl", "w")  # noqa: SIM115

counts = {"think": 0, "second": 0}
_real_classify = g._run_think_classification
_real_again = getattr(g, "_read_question_again", None)


async def _spy_classify(*args: object, **kwargs: object) -> object:
    counts["think"] += 1
    return await _real_classify(*args, **kwargs)


g._run_think_classification = _spy_classify
if _real_again is not None:

    async def _spy_again(*args: object, **kwargs: object) -> object:
        counts["second"] += 1
        return await _real_again(*args, **kwargs)

    g._read_question_again = _spy_again


async def one(index: int) -> dict[str, object]:
    counts.update(think=0, second=0)
    trace_id = f"c145-{LABEL}-{index}"
    query = Query(text=TEXT, session_id=trace_id, trace_id=trace_id, audience_depth=DEPTH)
    context = RequestContext(surface="web_ui", session_memory=None, reads_placement=True)
    start = time.monotonic()
    first_token_s = None
    clarifying = None
    citations = 0
    done: dict[str, object] = {}
    async for event in run_streaming(query, context):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        if event.type == "think":
            clarifying = payload.get("clarifying_question")
        elif event.type == "token" and first_token_s is None:
            first_token_s = round(time.monotonic() - start, 1)
        elif event.type == "citation":
            citations += 1
        elif event.type in ("done", "error"):
            done = {k: payload.get(k) for k in ("trust_outcome", "total_cost_usd", "message")}
    return {
        "run": index,
        "question": WHICH,
        "asked_back": clarifying is not None,
        "clarifying_question": clarifying,
        "trust_outcome": done.get("trust_outcome"),
        "citations": citations,
        "first_token_s": first_token_s,
        "done_s": round(time.monotonic() - start, 1),
        "think_calls": counts["think"],
        "second_reading_fired": counts["second"] > 0,
        "cost_usd": done.get("total_cost_usd"),
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
