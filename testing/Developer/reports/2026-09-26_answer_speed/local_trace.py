"""Time every piece of one question locally, against develop's own code.

Method copied from the harness review's trace driver (2026-09-25): load the
repository's .env without printing any value, run the real `core.run.run`,
and wrap functions in THIS process only. Nothing in any product file changes.

Mirrors develop's settings in this process: CLASSIFIER_PROVIDER=jev, the
guard and plan tiers on deepseek/deepseek-v4-flash and the synth tier on
z-ai/glm-5.2 (docs/architecture/Model_architecture.md, read from Railway on
2026-09-25). Tracing and the audit log are off, and no caller identity is
passed, so no interaction row is written.

What it records, each with its start time since the question began and its
duration:
- every model call (`litellm.acompletion`): which call site, prompt, reply and
  cached prompt tokens, finish reason;
- every Jev call, the single decisions and the batched sentence check;
- every outbound HTTP request (`httpx.AsyncClient.send`), host and path with
  its query parameters minus the key, email and tool fields, so duplicate
  lookups inside one question can be counted;
- inside Write: name resolution, the features decision wait, every grounding
  pass (claims kept, sentences stripped), the sentence check with every
  candidate sentence and which ones Jev approved, and the reader pass in Act.

After the question finishes it asks the guard tier, the judge before phase
8.6, about the same candidate sentences, so Jev's approvals can be set beside
the old judge's on identical input. That call is made after the run and does
not touch its timing.

Usage: local_trace.py <repo_root> <out_dir> <question_id> [audience_depth]
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

REPO = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
QID = sys.argv[3]
DEPTH = sys.argv[4] if len(sys.argv) > 4 else "researcher"
TREE = Path(os.environ.get("SPEED_TREE", str(REPO))).resolve()
OUT.mkdir(parents=True, exist_ok=True)

for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["GUARD_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PLAN_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["SYNTH_MODEL"] = "z-ai/glm-5.2"

sys.path.insert(0, str(TREE / "src"))

import httpx
import litellm

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as G
from system_03_search_agent.core.run import run
from system_03_search_agent.harness import coordinator_worker as CW
from system_03_search_agent.harness import decide as D
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as SC

GOLDEN = TREE / "eval" / "golden" / "golden_dataset.json"
QTEXT = {q["id"]: q["question"] for q in json.loads(GOLDEN.read_text())["queries"]}[QID]
T0 = time.monotonic()
T0_WALL = time.time()
REC: dict[str, list] = {
    "model": [], "jev": [], "http": [], "write": [], "grounding": [], "sentence_check": [], "reader": [],
}
CANDIDATES: list = []

SITES = [
    ("You write the final answer", "write: synth"),
    ("You check an answer written from research papers", "write: sentence check (guard)"),
    ("You are the query-understanding step", "think: classification"),
    ("You are a read-only extraction reader", "act: reader pass"),
    ("Answer with exactly one of the offered options", "decide(): guard pick"),
]


def now() -> float:
    return round(time.monotonic() - T0, 3)


def site_of(messages) -> str:
    for m in messages:
        if m.get("role") != "system":
            continue
        c = m.get("content") or ""
        for opening, name in SITES:
            if opening in c[:400]:
                return name
    for m in messages:
        c = m.get("content") or ""
        for opening, name in SITES:
            if opening in c:
                return name
    first = next((m.get("content") or "" for m in messages if m.get("role") == "system"), "")
    return "other: " + first[:60].replace("\n", " ")


_acompletion = litellm.acompletion


async def traced_acompletion(**kw):
    t = now()
    s = time.monotonic()
    rec = {"t": t, "site": site_of(kw.get("messages") or []),
           "role": "synth" if kw.get("model", "").endswith(os.environ["SYNTH_MODEL"]) else "guard_or_plan",
           "prompt_chars": sum(len(m.get("content") or "") for m in kw.get("messages") or []),
           "max_tokens": kw.get("max_tokens")}
    try:
        r = await _acompletion(**kw)
        u = r.usage
        details = getattr(u, "prompt_tokens_details", None)
        rec.update(ok=True, prompt_tokens=u.prompt_tokens, completion_tokens=u.completion_tokens,
                   cached_tokens=getattr(details, "cached_tokens", None) if details else None,
                   finish=r.choices[0].finish_reason,
                   reply=(r.choices[0].message.content or "") if rec["role"] == "synth" else None)
        return r
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__)
        raise
    finally:
        rec["dur"] = round(time.monotonic() - s, 3)
        REC["model"].append(rec)


litellm.acompletion = traced_acompletion

_call_jev = D.call_jev


async def traced_call_jev(**kw):
    t, s = now(), time.monotonic()
    rec = {"t": t, "kind": "decide", "key": kw.get("question_key")}
    try:
        r = await _call_jev(**kw)
        rec["ok"] = True
        return r
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__)
        raise
    finally:
        rec["dur"] = round(time.monotonic() - s, 3)
        REC["jev"].append(rec)


D.call_jev = traced_call_jev
_call_jev_batch = SC.call_jev_batch


async def traced_call_jev_batch(**kw):
    t, s = now(), time.monotonic()
    rec = {"t": t, "kind": "sentence_batch", "questions": len(kw.get("questions") or {}), "timeout_s": kw.get("timeout_s")}
    try:
        r = await _call_jev_batch(**kw)
        rec["ok"] = True
        return r
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__, reason=getattr(exc, "reason", None))
        raise
    finally:
        rec["dur"] = round(time.monotonic() - s, 3)
        REC["jev"].append(rec)


SC.call_jev_batch = traced_call_jev_batch

_send = httpx.AsyncClient.send
DROP = {"api_key", "email", "tool"}


async def traced_send(self, request, *a, **kw):
    t, s = now(), time.monotonic()
    u = urlsplit(str(request.url))
    params = sorted((k, v[:120]) for k, v in parse_qsl(u.query) if k not in DROP)
    rec = {"t": t, "host": u.hostname, "path": u.path, "params": params, "method": request.method}
    try:
        r = await _send(self, request, *a, **kw)
        rec["status"] = r.status_code
        return r
    except BaseException as exc:
        rec["error"] = type(exc).__name__
        raise
    finally:
        rec["dur"] = round(time.monotonic() - s, 3)
        REC["http"].append(rec)


httpx.AsyncClient.send = traced_send


def timed_async(module, name, bucket, label, summarize=None):
    orig = getattr(module, name)

    async def wrapper(*a, **kw):
        t, s = now(), time.monotonic()
        out = await orig(*a, **kw)
        rec = {"t": t, "what": label, "dur": round(time.monotonic() - s, 3)}
        if summarize:
            rec.update(summarize(a, kw, out))
        REC[bucket].append(rec)
        return out

    setattr(module, name, wrapper)


timed_async(G, "resolve_concept_ids", "write", "resolve_concept_ids",
            lambda a, kw, out: {"ids": len(a[0]) if a else None})
timed_async(G, "resolve_descriptor_ids", "write", "resolve_descriptor_ids",
            lambda a, kw, out: {"ids": len(a[0]) if a else None})
timed_async(G, "_clinical_features_asked", "write", "features_decision_wait",
            lambda a, kw, out: {"asked": out})
timed_async(G, "_ground_with_sentence_check", "write", "ground_with_sentence_check",
            lambda a, kw, out: {"claims": len(out.claims), "stripped": out.stripped_count})
timed_async(CW, "_reader_pass", "reader", "reader_pass")

_rgp = G.run_grounding_pass


def traced_rgp(narrative, synth_findings, *a, **kw):
    t, s = now(), time.monotonic()
    out = _rgp(narrative, synth_findings, *a, **kw)
    REC["grounding"].append({
        "t": t, "dur": round(time.monotonic() - s, 4), "narrative_chars": len(narrative),
        "findings": len(synth_findings), "claims": len(out.claims), "stripped": out.stripped_count,
        "refused": out.refused, "with_verified": kw.get("verified_syntheses") is not None,
        "collects_candidates": kw.get("candidate_sink") is not None,
    })
    return out


G.run_grounding_pass = traced_rgp

_crs = G.check_reworded_sentences


async def traced_crs(candidates, **kw):
    t, s = now(), time.monotonic()
    rec = {"t": t, "candidates": [{"sentence": c.sentence, "quotes": list(c.quotes)} for c in candidates],
           "budget_s": kw.get("budget_s")}
    CANDIDATES.append(list(candidates))
    try:
        out = await _crs(candidates, **kw)
        rec["approved"] = [c.sentence for c in candidates if c.key in out]
        rec["ok"] = True
        return out
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__)
        raise
    finally:
        rec["dur"] = round(time.monotonic() - s, 3)
        REC["sentence_check"].append(rec)


G.check_reworded_sentences = traced_crs


async def guard_second_opinion():
    """The pre-8.6 judge on the same candidates, after the run, off its clock."""
    results = []
    h = Harness(trace_id=f"speed-guard-compare-{QID}-{int(time.time())}")
    for cands in CANDIDATES:
        s = time.monotonic()
        try:
            resp = await h.call_tier("guard", SC.build_sentence_check_messages(cands), cache_prefix=None, max_tokens=256)
            approved = SC.approved_keys(resp.content or "", cands)
            results.append({"ok": True, "dur": round(time.monotonic() - s, 3),
                            "approved": [c.sentence for c in cands if c.key in approved]})
        except Exception as exc:  # noqa: BLE001
            results.append({"ok": False, "error": type(exc).__name__, "dur": round(time.monotonic() - s, 3)})
    return results


async def main():
    query = Query(text=QTEXT, session_id=f"speed-{QID}", trace_id=f"trace-speed-{QID}-{int(time.time())}",
                  user_id=None, audience_depth=DEPTH)
    context = RequestContext(surface="rest_sse", session_memory=None)
    stamps, events = [], []
    async for event in run(query, context):
        events.append(event)
        p = event.payload if isinstance(event.payload, dict) else {}
        # `run()` is the buffered path and yields at the end, so the event's
        # own emit stamp, not the yield time, marks where a step ended.
        emitted = round(event.ts.timestamp() - T0_WALL, 3) if getattr(event, "ts", None) else None
        stamps.append({"t": now(), "emitted": emitted, "type": event.type, "step": p.get("step"),
                       "tool": p.get("tool"), "status": p.get("status")})
    wall = now()
    guard_cmp = await guard_second_opinion()
    done = next((e for e in events if e.type == "done"), None)
    answer = "".join(e.payload.get("text", "") for e in events if e.type == "token")
    out = {
        "id": QID, "question": QTEXT, "depth": DEPTH, "wall_s": wall,
        "done": done.payload if done else None,
        "withdrawn": "could not be verified against them" in answer,
        "citations": sum(1 for e in events if e.type == "citation"),
        "stamps": stamps, "rec": REC, "guard_sentence_check": guard_cmp, "answer_text": answer,
    }
    (OUT / f"{QID}.json").write_text(json.dumps(out, indent=1, default=str))
    synth = [m for m in REC["model"] if m["role"] == "synth"]
    print(f"{QID}: wall {wall}s withdrawn={out['withdrawn']} citations={out['citations']} "
          f"synth calls={len(synth)} {[m['dur'] for m in synth]} "
          f"jev batch={[j['dur'] for j in REC['jev'] if j['kind']=='sentence_batch']} "
          f"cands={[len(c['candidates']) for c in REC['sentence_check']]} "
          f"approved={[len(c.get('approved') or []) for c in REC['sentence_check']]} "
          f"guard_would={[len(g.get('approved') or []) for g in guard_cmp]}", flush=True)


asyncio.run(main())
