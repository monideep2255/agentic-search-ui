"""Card 101: live runs of the design's questions through `core/run.py` `run_streaming`.

Usage: MAIN_CHECKOUT=<checkout holding .env> python live_check.py <src-dir> <label> <out.jsonl> <budget-usd> <q:runs>...

`q` is the question's index in QUESTIONS. Develop's settings: the web client's
`reads_placement=True`, CLASSIFIER_PROVIDER=jev, GUARD_MODEL and PLAN_MODEL
deepseek/deepseek-v4-flash, SYNTH_MODEL z-ai/glm-5.2, PER_QUERY_COST_CAP_USD=0.25.
Records, per run: the sentences shown (the claim tokens), items sent to the
sentence check, the check's approvals, cost. Stops when the spend passes the budget.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ["MAIN_CHECKOUT"])
for raw in (ROOT / ".env").read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
os.environ.update(
    CLASSIFIER_PROVIDER="jev",
    GUARD_MODEL="deepseek/deepseek-v4-flash",
    PLAN_MODEL="deepseek/deepseek-v4-flash",
    SYNTH_MODEL="z-ai/glm-5.2",
    PER_QUERY_COST_CAP_USD="0.25",
    LANGCHAIN_TRACING_V2="false",
    LANGSMITH_TRACING="false",
    TOOL_AUDIT_LOG_ENABLED="false",
)
sys.path.insert(0, sys.argv[1])
LABEL, OUT, BUDGET = sys.argv[2], Path(sys.argv[3]), float(sys.argv[4])
PLAN = [tuple(int(x) for x in arg.split(":")) for arg in sys.argv[5:]]

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph
from system_03_search_agent.core.run import run_streaming

QUESTIONS = [
    ("plain_language", "What are the typical symptoms and risk factors of GERD?"),
    ("plain_language", "What causes bronchiolitis in babies, and how is it usually treated?"),
    ("researcher", "What do studies say about Salmonella Typhimurium and extended-spectrum beta-lactamase genes?"),
    ("researcher", "Is the U.S. FDA-approved RSV vaccine shown to prevent bronchiolitis in infants?"),
    ("researcher", "Does azithromycin shorten bronchiolitis in infants?"),
    ("researcher", "Does ribavirin cure bronchiolitis in infants?"),
]

state = {"sent": 0, "approved": 0, "grounded": []}
real_check = graph.check_reworded_sentences
real_ground = graph._ground_with_sentence_check


async def counting_check(candidates, **kwargs):
    approved = await real_check(candidates, **kwargs)
    state["sent"] += len(candidates)
    state["approved"] += sum(1 for c in candidates if c.key in approved)
    return approved


async def recording_ground(*args, **kwargs):
    result = await real_ground(*args, **kwargs)
    state["grounded"].append(list(result.sentences))
    return result


graph.check_reworded_sentences = counting_check
graph._ground_with_sentence_check = recording_ground


async def one(index: int, run: int) -> dict:
    depth, text = QUESTIONS[index]
    state.update(sent=0, approved=0, grounded=[])
    trace_id = f"c101-{LABEL}-{index}-{run}-{int(time.time())}"[:64]
    query = Query(text=text, session_id=trace_id, trace_id=trace_id, audience_depth=depth)
    context = RequestContext(surface="web_ui", reads_placement=True)
    started = time.monotonic()
    cost, tokens, outcome = 0.0, [], None
    async for event in run_streaming(query, context):
        if event.type == "cost":
            cost = max(cost, float(event.payload.get("query_cost_usd", 0.0)))
        elif event.type == "token":
            tokens.append({k: event.payload.get(k) for k in ("text", "kind", "placement")})
        elif event.type == "done":
            outcome = event.payload.get("trust_outcome")
    claims = [t["text"] for t in tokens if t.get("kind") == "claim"]
    return {
        "label": LABEL, "q": index, "run": run, "depth": depth, "text": text,
        "seconds": round(time.monotonic() - started, 1), "cost_usd": round(cost, 5), "outcome": outcome,
        "final_grounded_sentences": state["grounded"][-1] if state["grounded"] else [],
        "grounding_calls": len(state["grounded"]), "items_sent": state["sent"], "items_approved": state["approved"],
        "claim_tokens": claims, "token_count": len(tokens),
    }


def _append(line: str) -> None:
    with OUT.open("a") as fh:
        fh.write(line + "\n")


async def main() -> None:
    spent = 0.0
    for index, runs in PLAN:
        for run in range(1, runs + 1):
            if spent >= BUDGET:
                print(f"budget {BUDGET} reached at {spent:.4f}; stopping", file=sys.stderr)
                return
            row = await one(index, run)
            spent += row["cost_usd"]
            print(json.dumps(row), flush=True)
            await asyncio.to_thread(_append, json.dumps(row))


asyncio.run(main())
