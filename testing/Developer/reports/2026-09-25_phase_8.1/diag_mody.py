"""Diagnostic for T-8.1-04: why "What genes are associated with MODY?" fails
its citation check on most runs.

Runs the real loop in-process against MY worktree's src (not the main
checkout), with the real model and graph. Monkeypatches
`system_03_search_agent.core.graph.run_grounding_pass` to print the exact
narrative the model wrote and why each clause was kept or stripped, without
editing core/graph.py (out of this builder's file fence).

Never prints an env value. Loads secrets from the main repository's .env by
key only.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

MAIN_REPO = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")  # local-refs: allow
MY_WORKTREE = Path(__file__).resolve().parents[4]  # .../worktrees/agent-.../

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

# MY worktree's src goes first, so we exercise the code under test, not the
# main checkout's copy.
sys.path.insert(0, str(MY_WORKTREE / "src"))

import system_03_search_agent.core.graph as _g
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run
from system_03_search_agent.synthesis.grounding import (
    split_into_sentences,
)

_real_gp = _g.run_grounding_pass


def _gp_spy(text, findings, *a, **kw):
    print("[RAW_SYNTH_TEXT]", json.dumps(text))
    for i, s in enumerate(split_into_sentences(text)):
        print(f"[SENTENCE {i}]", json.dumps(s))
    res = _real_gp(text, findings, *a, **kw)
    print(
        f"[GROUNDING_RESULT] claims={len(res.claims)} stripped={res.stripped_count} "
        f"refused={res.refused} narrative_len={len(res.narrative)}"
    )
    for c in res.claims:
        print("[CLAIM]", c.claim_text, "-> finding.field_value=", json.dumps(c.finding.field_value)[:150])
    return res


_g.run_grounding_pass = _gp_spy


async def main(question: str):
    query = Query(
        text=question,
        session_id="local-repro-mody",
        trace_id="trace-local-repro-mody",
        user_id=None,
        audience_depth="researcher",
    )
    context = RequestContext(surface="rest_sse", session_memory=None)
    trust_outcome = None
    async for e in run(query, context):
        if e.type == "done":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            trust_outcome = p.get("trust_outcome")
            print("[DONE]", json.dumps(p, default=str)[:800])
        elif e.type == "error":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            print("[ERROR]", json.dumps(p, default=str)[:800])
    print("[RESULT] trust_outcome=", trust_outcome)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "What genes are associated with MODY?"
    asyncio.run(main(q))
