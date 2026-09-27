"""Writer bench 3: one writer model, one golden question, one run.

Product-owner decision of 2026-09-26 (DECISIONS.md, "A third writer bench
runs with a spend of up to 30 dollars"). Only the synth tier's model varies.
Every other setting is pinned to develop's, in this process only:

- GUARD_MODEL and PLAN_MODEL: deepseek/deepseek-v4-flash
- CLASSIFIER_PROVIDER: jev
- PER_QUERY_COST_CAP_USD: 0.50, as the first writer bench did
- tracing and the tool audit log off, no caller identity, so nothing is
  persisted

Runs the real `core.run.run` from the code tree named by BENCH_TREE (a
detached worktree of origin/develop), or from this repository when unset.
Loads the repository's .env without printing a value and never edits it.
Nothing in any product file changes: the wrappers below live in this
process's memory only, and only observe (they call through unchanged).

What it records, per run, in raw/<model>__<question>__r<n>.json and as one
summary line in results.jsonl:

- every model call (`litellm.acompletion`): tier by model, duration, prompt,
  cached, completion and reasoning tokens, finish reason, OpenRouter's own
  reported cost, and whether the request carried the reasoning block
- every `Harness.call_tier` call: tier, `elapsed_s` (T-8.6-08), tokens and
  the harness's metered cost
- every grounding of a writer reply (`_ground_with_sentence_check`): the
  sentences and claims that survived and the cited ids, in call order, so
  the first reply and the completeness repair can be told apart
- every sentence check: how many reworded sentences went to Jev, and how
  many it approved
- the events: guard, think, citations, tokens, done, cost, errors

Usage: run_one.py <model_id>[+effort-<level>] <question_id> <run_index>
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TREE = Path(os.environ.get("BENCH_TREE") or REPO).resolve()
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)

for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

# A label of the form "<model id>+effort-<level>" is a bench-only variant,
# asked for by the lead on 2026-09-26 for models that refuse `effort: none`:
# the synth tier's reasoning effort is set to <level> in THIS process's
# memory only (`harness._TIER_REASONING["synth"]`). The product still asks
# for `none`, and nothing here is ever committed to it. A plain model id is
# the product's own request, unchanged.
LABEL = sys.argv[1]
MODEL, _, EFFORT = LABEL.partition("+effort-")
QID = sys.argv[2]
RUN_INDEX = int(sys.argv[3])

os.environ["GUARD_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PLAN_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["SYNTH_MODEL"] = MODEL
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.50"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

sys.path.insert(0, str(TREE / "src"))

import litellm

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as G
from system_03_search_agent.core.run import run
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import Harness

if EFFORT:
    harness_module._TIER_REASONING["synth"] = {"effort": EFFORT}

GOLDEN = TREE / "eval" / "golden" / "golden_dataset.json"
ROW = {q["id"]: q for q in json.loads(GOLDEN.read_text())["queries"]}[QID]
NOTE = "could not be verified against them"
T0 = time.monotonic()
T0_WALL = time.time()
REC: dict[str, list] = {"llm": [], "call_tier": [], "grounding": [], "sentence_check": []}
_PATH_WORDS = (str(REPO), str(TREE), str(Path.home()))


def now() -> float:
    return round(time.monotonic() - T0, 3)


def scrub(text: str, limit: int = 400) -> str:
    """Bound an error text and remove local paths and anything key-shaped."""
    text = str(text)
    for word in _PATH_WORDS:
        text = text.replace(word, "<path>")
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<key>", text)
    return text[:limit]


def payload(event) -> dict:
    p = event.payload
    if isinstance(p, dict):
        return p
    return p.model_dump() if hasattr(p, "model_dump") else {}


_acompletion = litellm.acompletion


async def traced_acompletion(**kw):
    started, t = time.monotonic(), now()
    rec = {
        "t": t,
        "model": kw.get("model"),
        "synth": (kw.get("model") or "").endswith(MODEL),
        "reasoning_param": "reasoning" in kw,
        "max_tokens": kw.get("max_tokens"),
    }
    try:
        response = await _acompletion(**kw)
        usage = response.usage
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        completion_details = getattr(usage, "completion_tokens_details", None)
        hidden = getattr(response, "_hidden_params", {}) or {}
        headers = hidden.get("additional_headers") or {}
        rec.update(
            ok=True,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cached_tokens=getattr(prompt_details, "cached_tokens", None) if prompt_details else None,
            reasoning_tokens=getattr(completion_details, "reasoning_tokens", None) if completion_details else None,
            finish=response.choices[0].finish_reason,
            openrouter_cost_usd=headers.get("llm_provider-x-litellm-response-cost"),
            reply=(response.choices[0].message.content or "") if rec["synth"] else None,
        )
        return response
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__, message=scrub(exc))
        raise
    finally:
        rec["dur"] = round(time.monotonic() - started, 3)
        REC["llm"].append(rec)


litellm.acompletion = traced_acompletion

_call_tier = Harness.call_tier


async def traced_call_tier(self, tier, messages, **kw):
    started, t = time.monotonic(), now()
    rec = {"t": t, "tier": tier}
    try:
        response = await _call_tier(self, tier, messages, **kw)
        rec.update(
            ok=True,
            elapsed_s=response.elapsed_s,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=response.call_cost_usd,
            model=response.model_id,
        )
        return response
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__, message=scrub(exc))
        raise
    finally:
        rec["dur"] = round(time.monotonic() - started, 3)
        REC["call_tier"].append(rec)


Harness.call_tier = traced_call_tier

_ground = G._ground_with_sentence_check


async def traced_ground(narrative, synth_findings, **kw):
    t, started = now(), time.monotonic()
    out = await _ground(narrative, synth_findings, **kw)
    if not REC.get("findings"):
        # The records the writer was shown, bounded, so a sentence can be read
        # against the record it cites.
        REC["findings"] = [
            {"ref": f.ref_index, "field": f.field, "value": f.field_value[:300], "url": f.source_url}
            for f in synth_findings
        ]
    REC["grounding"].append({
        "t": t,
        "dur": round(time.monotonic() - started, 4),
        "narrative_chars": len(narrative),
        "narrative": narrative[:6000],
        "sentences": list(out.sentences),
        "claims": len(out.claims),
        "claim_ids": sorted({c.finding.citation_id for c in out.claims}),
        "claim_detail": [
            {
                "text": c.claim_text[:400],
                "quote": (c.evidence_quote or "")[:300],
                "ref": c.finding.ref_index,
                "field": c.finding.field,
                "value": c.finding.field_value[:300],
            }
            for c in out.claims
        ],
        "stripped": out.stripped_count,
        "refused": out.refused,
    })
    return out


G._ground_with_sentence_check = traced_ground

_check = G.check_reworded_sentences


async def traced_check(candidates, **kw):
    t, started = now(), time.monotonic()
    rec = {"t": t, "sent": len(candidates), "approved": 0}
    try:
        out = await _check(candidates, **kw)
        rec["approved"] = sum(1 for c in candidates if c.key in out)
        rec["ok"] = True
        return out
    except BaseException as exc:
        rec.update(ok=False, error=type(exc).__name__)
        raise
    finally:
        rec["dur"] = round(time.monotonic() - started, 3)
        REC["sentence_check"].append(rec)


G.check_reworded_sentences = traced_check


def classify(guard, fatal, done, citations) -> str:
    """The golden consistency run's own outcome rule (run_consistency.py)."""
    if guard is not None and guard.get("passed") is False:
        category = guard.get("category") or "unknown"
        return "refused_offtopic" if category == "off_topic" else f"refused_{category}"
    if fatal is not None and "daily" in (fatal.get("source") or ""):
        return "capped"
    if fatal is not None:
        return "error"
    if done is None:
        return "no_done"
    if citations and done.get("trust_outcome") != "refuse":
        return "answered"
    if citations:
        return "refused_with_sources"
    return "refused_no_evidence"


def prose_of(answer: str) -> str:
    """The writer's region: after the code-built opening line, before the
    first code-built listing heading or note (p01_compare.py's rule)."""
    paras = [p.strip() for p in answer.split("\n\n") if p.strip()]
    out = []
    for p in paras[1:]:
        if re.search(r"records found$", p) or p.startswith(("Note:", "Where this answer")):
            break
        out.append(p)
    return " ".join(out)


async def main() -> None:
    slug = LABEL.replace("/", "_")
    query = Query(
        text=ROW["question"],
        session_id=f"wb3-{QID}-{RUN_INDEX}",
        # Query caps trace_id at 64 characters, so the label is not in it.
        trace_id=f"trace-wb3-{QID}-r{RUN_INDEX}-{uuid.uuid4().hex[:16]}",
        user_id=None,
        audience_depth="researcher",
    )
    context = RequestContext(surface="rest_sse", session_memory=None)
    events = []
    crashed = None
    try:
        async for event in run(query, context):
            emitted = round(event.ts.timestamp() - T0_WALL, 3) if getattr(event, "ts", None) else None
            events.append((event.type, payload(event), emitted))
    except Exception as exc:  # noqa: BLE001 - a crash is a result to record, not to hide
        crashed = f"{type(exc).__name__}: {scrub(exc)}"
    wall_s = now()

    def of(kind):
        return [p for k, p, _ in events if k == kind]

    guard = next(iter(of("guard")), None)
    fatal = next((p for p in of("error") if p.get("fatal")), None)
    done = next(iter(of("done")), None)
    citations = of("citation")
    answer = "".join(p.get("text") or "" for p in of("token"))
    cited_urls = [c.get("source_url") or "" for c in citations]
    must_cite = ROW.get("must_cite") or []
    synth_llm = [r for r in REC["llm"] if r["synth"]]
    synth_tier = [r for r in REC["call_tier"] if r["tier"] == "synth"]
    grounds = REC["grounding"]
    shipped = None
    if grounds:
        shipped = 0
        if len(grounds) > 1 and set(grounds[1]["claim_ids"]) > set(grounds[0]["claim_ids"]):
            shipped = 1
    withdrawn = NOTE in answer
    cost_events = of("cost")
    record = {
        "model": LABEL,
        "model_id": MODEL,
        "synth_effort": EFFORT or "none",
        "question_id": QID,
        "run": RUN_INDEX,
        "question": ROW["question"],
        "trace_id": query.trace_id,
        "tree_commit": os.environ.get("BENCH_TREE_COMMIT"),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0_WALL)),
        "outcome": "crashed" if crashed else classify(guard, fatal, done, citations),
        "crash": crashed,
        "trust_outcome": None if done is None else done.get("trust_outcome"),
        "fatal_source": None if fatal is None else fatal.get("source"),
        "fatal_class": None if fatal is None else fatal.get("error_class"),
        "citations": len(citations),
        "must_cite_total": len(must_cite),
        "must_cite_hits": sum(1 for prefix in must_cite if any(u.startswith(prefix) for u in cited_urls)),
        "withdrawn": withdrawn,
        "writer_calls": len(synth_tier),
        "writer_calls_ok": sum(1 for r in synth_tier if r.get("ok")),
        "repair_fired": len(synth_tier) >= 2,
        "shipped_draft": shipped,
        "prose_sentences_kept": 0 if (withdrawn or shipped is None) else len(grounds[shipped]["sentences"]),
        "prose_kept": [] if (withdrawn or shipped is None) else grounds[shipped]["sentences"],
        "prose_text": prose_of(answer),
        "jev_sent": sum(r["sent"] for r in REC["sentence_check"]),
        "jev_approved": sum(r["approved"] for r in REC["sentence_check"]),
        "writer_elapsed_s": [r.get("elapsed_s") for r in synth_tier if r.get("ok")],
        "writer_completion_tokens": [r.get("completion_tokens") for r in synth_tier if r.get("ok")],
        "writer_reasoning_tokens": [r.get("reasoning_tokens") for r in synth_llm if r.get("ok")],
        "writer_reasoning_refused": sum(
            1 for r in synth_llm if not r.get("ok") and "reasoning is mandatory" in (r.get("message") or "").lower()
        ),
        "writer_errors": [f"{r.get('error')}: {r.get('message')}" for r in synth_tier if not r.get("ok")],
        "wall_s": wall_s,
        "done_elapsed_s": None if done is None else round((done.get("elapsed_ms") or 0) / 1000, 3),
        # The done event's total is the question's final metered cost; the
        # last cost event can predate a timed-out writer call's charge.
        "metered_cost_usd": (
            done.get("total_cost_usd") if done is not None
            else (cost_events[-1].get("query_cost_usd") if cost_events else None)
        ),
        "done_cost_usd": None if done is None else done.get("total_cost_usd"),
        "openrouter_cost_usd": round(sum(float(r.get("openrouter_cost_usd") or 0) for r in REC["llm"]), 6),
        "writer_openrouter_cost_usd": round(sum(float(r.get("openrouter_cost_usd") or 0) for r in synth_llm), 6),
        "writer_metered_cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in synth_tier), 6),
        "answer_text": answer,
    }
    detail = {
        "record": record,
        "rec": REC,
        "events": [{"type": k, "emitted": e, "step": p.get("step"), "tool": p.get("tool")} for k, p, e in events],
        "done": done,
        "guard": guard,
        "citation_urls": cited_urls,
    }
    (RAW / f"{slug}__{QID}__r{RUN_INDEX}.json").write_text(json.dumps(detail, indent=1, default=str))
    with open(HERE / "results.jsonl", "a") as f:  # noqa: ASYNC230 - one small append per finished run
        f.write(json.dumps(record, default=str) + "\n")
    print(
        f"[DONE] {LABEL} {QID} r{RUN_INDEX} outcome={record['outcome']} withdrawn={withdrawn} "
        f"kept={record['prose_sentences_kept']} writer_s={record['writer_elapsed_s']} "
        f"wall={wall_s} metered=${record['metered_cost_usd']} openrouter=${record['openrouter_cost_usd']} "
        f"errors={record['writer_errors'][:1]}",
        flush=True,
    )


asyncio.run(main())
