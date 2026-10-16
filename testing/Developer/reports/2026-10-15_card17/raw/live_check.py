"""Card 17 live check: one question through `run_streaming`, develop's settings.

Usage: ASU_ENV_FILE=<path to the .env> python live_check.py <label> <med|gerd|ashk> <plain_language|researcher>

Settings pinned to develop's: CLASSIFIER_PROVIDER=jev, guard and plan
deepseek/deepseek-v4-flash, synth z-ai/glm-5.2, per-query cap 0.25 USD.
Secrets are read into this process only and never printed or written.
Spies log, per run, the sentences the pass received and returned, so a lost
sentence would show. Output: live_fix/<label>.jsonl beside this script (fix round 2026-10-16; live/ holds the first round).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
for line in Path(os.environ["ASU_ENV_FILE"]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.update(
    {
        "LANGCHAIN_TRACING_V2": "false",
        "TOOL_AUDIT_LOG_ENABLED": "false",
        "CLASSIFIER_PROVIDER": "jev",
        "GUARD_MODEL": "deepseek/deepseek-v4-flash",
        "PLAN_MODEL": "deepseek/deepseek-v4-flash",
        "SYNTH_MODEL": "z-ai/glm-5.2",
        "PER_QUERY_COST_CAP_USD": "0.25",
    }
)
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.core.run import run_streaming

LABEL, WHICH, DEPTH = sys.argv[1], sys.argv[2], sys.argv[3]
QUESTIONS = {
    "med": "Are there any beneficial variants typically found in people of mediterranean descent?",
    "gerd": "What are the typical symptoms and risk factors of GERD?",
    "ashk": "What genetic variants are common in people of Ashkenazi Jewish descent?",
}
OUT = open(HERE / "live_fix" / f"{LABEL}.jsonl", "w")  # noqa: SIM115


def log(tag: str, obj) -> None:
    OUT.write(json.dumps({"tag": tag, "data": obj}, default=str) + "\n")
    OUT.flush()


_real = g.name_switched_records


def _spy(grounding, findings, order=None):
    after, named = _real(grounding, findings, order)
    log("PASS", {"before": list(grounding.sentences), "after": list(after.sentences), "named": named, "order": None if order is None else list(order),
                 "entity_types": sorted({f.entity_type for f in findings}),
                 "labels": [[f.ref_index, f.field, f.entity_type, f.source_url, f.field_value[:200]]
                            for f in findings if f.field in ("title", "name")][:40]})
    return after, named


g.name_switched_records = _spy


async def main() -> None:
    query = Query(text=QUESTIONS[WHICH], session_id=f"c17-{LABEL}", trace_id=f"c17-live-{LABEL}",
                  user_id=None, audience_depth=DEPTH)
    context = RequestContext(surface="web_ui", session_memory=None, reads_placement=True)
    t = time.time()
    async for e in run_streaming(query, context):
        p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
        if e.type == "token":
            log("TOKEN", {k: p.get(k) for k in ("kind", "text", "placement")})
        elif e.type == "citation":
            log("CITATION", {k: p.get(k) for k in ("display_index", "citation_id", "source_id", "source_url", "field", "claim_text")})
        elif e.type in ("done", "error"):
            log(e.type.upper(), {k: p.get(k) for k in ("trust_outcome", "elapsed_ms", "total_cost_usd", "message")})
    log("ELAPSED_S", round(time.time() - t, 1))


asyncio.run(main())
OUT.close()
