"""Card 88: run the ask-back pick through the real write step locally and log
where the model's prose goes.

Usage: python3 local_write_trace.py <label> <depth>

Runs "What are the typical symptoms and risk factors of GERD?" through
`core.run.run` with the real models, tools and graph (the approach of
testing/Developer/scripts/local_loop_run.py), CLASSIFIER_PROVIDER=jev so the
sentence check is the one develop uses, and spies on the write step:

- the synth model's raw reply (`_dispatch_tier_call`, tier synth),
- every `run_grounding_pass` (claims kept, clauses stripped),
- the reworded-sentence check (candidates in, approved out, or the failure),
- `drop_record_restatements` (sentences dropped).

Secrets are read from the repository's .env into this process only and are
never printed or written. Output goes to <label>.log beside this script.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["CLASSIFIER_PROVIDER"] = "jev"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.core.run import run

LABEL, DEPTH = sys.argv[1], sys.argv[2]
QUESTION = "What are the typical symptoms and risk factors of GERD?"


def log(tag: str, obj) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    LOG.write(f"[{tag}] {text}\n")
    LOG.flush()


_real_dispatch = g._dispatch_tier_call


async def _dispatch_spy(harness, trace_id, tier, step, messages, budget_s, *a, **kw):
    resp = await _real_dispatch(harness, trace_id, tier, step, messages, budget_s, *a, **kw)
    if tier == "synth" and step == "write":
        log("SYNTH_PROMPT_USER_TAIL", messages[-1]["content"][-6000:] if messages else "")
        log("SYNTH_REPLY", g._response_text(resp))
    if tier == "guard" and step == "write":
        log("GUARD_WRITE_REPLY", g._response_text(resp))
    return resp


g._dispatch_tier_call = _dispatch_spy

_real_gp = g.run_grounding_pass


def _gp_spy(narrative, findings, *a, **kw):
    res = _real_gp(narrative, findings, *a, **kw)
    log(
        "GROUNDING",
        {
            "input_chars": len(narrative),
            "input_head": narrative[:200],
            "verified_syntheses": len(kw.get("verified_syntheses") or ()),
            "claims": len(res.claims),
            "stripped": res.stripped_count,
            "refused": res.refused,
            "kept_sentences": list(res.sentences),
            "candidates_collected": len(kw["candidate_sink"]) if kw.get("candidate_sink") is not None else None,
        },
    )
    return res


g.run_grounding_pass = _gp_spy

_real_check = g.check_reworded_sentences


async def _check_spy(candidates, **kw):
    log("SENTENCE_CHECK_IN", {"n": len(candidates), "budget_s": kw.get("budget_s"),
                              "sentences": [c.sentence for c in candidates]})
    try:
        approved = await _real_check(candidates, **kw)
    except Exception as exc:
        log("SENTENCE_CHECK_RAISED", type(exc).__name__ + ": " + str(exc)[:300])
        raise
    log("SENTENCE_CHECK_OUT", {"approved": len(approved),
                               "approved_sentences": [k[0] for k in approved]})
    return approved


g.check_reworded_sentences = _check_spy

_real_drop = g.drop_record_restatements


def _drop_spy(grounding, findings):
    out, dropped = _real_drop(grounding, findings)
    log("RESTATEMENTS_DROPPED", {"dropped": dropped, "before": list(grounding.sentences),
                                 "after": list(out.sentences)})
    return out, dropped


g.drop_record_restatements = _drop_spy


async def main() -> None:
    query = Query(text=QUESTION, session_id="c88-local", trace_id=f"c88-local-{LABEL}",
                  user_id=None, audience_depth=DEPTH)
    context = RequestContext(surface="rest_sse", session_memory=None)
    async for e in run(query, context):
        p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
        if e.type == "token" and p.get("kind") in ("claim", "note", None):
            log("TOKEN", f"{p.get('kind')}: {p['text']}")
        elif e.type in ("think", "done", "error"):
            log(e.type.upper(), p)


with open(HERE / f"{LABEL}.log", "w") as LOG:
    asyncio.run(main())

