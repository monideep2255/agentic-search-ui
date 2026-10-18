"""Card 101 build round 2 (every rewording goes to the check): the fix
round's trace script with one spy added. On every first grounding pass it
logs, per sentence check candidate, whether code's old word check
(`grounding.synthesis_is_supported_by`) would have approved that sentence
alone, so the held-back sentences that code would have shown can be
counted. The quote of each candidate is found in the record the way the
exact checks find it. The fix round's text follows.

Card 101 fix round: the build's live trace script with one question
added, "bronch", a plain-language question outside the owner's test
questions and the golden set (fix_round.md says why it was chosen). REPO_ROOT
names the checkout whose `src` runs (this branch, or develop exported to a
scratch folder outside the repository). The build's text follows.

Card 101 live answers, copied from
`2026-10-05_wave3/sentence_check_raw/trace_run.py` with only its paths
adapted: ROOT is REPO_ROOT (default: four folders up, as before), and the
output goes to OUT_DIR (default: beside this script), so raw answers, which
carry record text, can stay outside the repository. The card 89 text follows.

Card 89 ship check: run one question through the real write step locally,
with the sentence check reading whole record sentences, and capture every
(sentence, quotes) pair the check saw, with the judge's verdict on each.

Adapted from testing/Developer/reports/2026-10-05_sentence_check/raw/
trace_run.py: the same spies, plus the writer's own quotes (the candidate's
key) beside the widened quotes the judge read. ROOT is the checkout whose
`src` is run; ENV_FILE names the .env to read (default ROOT/.env).

Usage: python3 trace_run.py <label> <med|gerd|bronch> <plain_language|researcher>

The approach of testing/Developer/reports/2026-10-05_card88/raw/
local_write_trace.py: `core.run.run` with the real models, tools and graph,
CLASSIFIER_PROVIDER=jev so the judge is the one develop uses. Spies:

- `sentence_check.call_jev_batch`: the state sent, and Jev's answer per item
  (choice and both probabilities).
- `core.graph.check_reworded_sentences`: candidates in (sentence, quotes),
  approved out.
- `core.graph.run_grounding_pass`: the findings' text, so a rejection can be
  classified against the whole record, not only the quote.

Secrets are read from the repository's .env into this process only and are
never printed or written. Output: <label>.jsonl beside this script.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("REPO_ROOT", HERE.parents[4]))
OUT_DIR = Path(os.environ.get("OUT_DIR", HERE))
for line in Path(os.environ.get("ENV_FILE", ROOT / ".env")).read_text().splitlines():
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
from system_03_search_agent.synthesis import sentence_check as sc

LABEL, WHICH, DEPTH = sys.argv[1], sys.argv[2], sys.argv[3]
QUESTIONS = {
    "med": "Are there any beneficial variants typically found in people of mediterranean descent?",
    "gerd": "What are the typical symptoms and risk factors of GERD?",
    "bronch": "What causes bronchiolitis in babies, and how is it usually treated?",
}
QUESTION = QUESTIONS[WHICH]
OUT = open(OUT_DIR / f"{LABEL}.jsonl", "w")  # noqa: SIM115 - closed at the end of the run


def log(tag: str, obj) -> None:
    OUT.write(json.dumps({"tag": tag, "t": round(time.time(), 3), "data": obj}, default=str) + "\n")
    OUT.flush()


_real_jev = sc.call_jev_batch


async def _jev_spy(**kw):
    sent = {"model": kw.get("model"), "state": kw.get("state"), "n_questions": len(kw.get("questions") or {}),
            "timeout_s": kw.get("timeout_s")}
    t = time.time()
    try:
        res = await _real_jev(**kw)
    except Exception as exc:
        log("JEV_RAISED", {**sent, "error": type(exc).__name__ + ": " + str(exc)[:300],
                           "elapsed_ms": int((time.time() - t) * 1000)})
        raise
    log("JEV_RESULT", {**sent, "resolved_model": res.resolved_model, "latency_ms": res.latency_ms,
                       "cost_usd": res.cost_usd,
                       "answers": {k: {"choice": a.choice, "confidence": a.confidence,
                                       "probabilities": a.probabilities} for k, a in res.answers.items()}})
    return res


sc.call_jev_batch = _jev_spy

_real_check = g.check_reworded_sentences


async def _check_spy(candidates, **kw):
    log("CHECK_IN", {"n": len(candidates), "budget_s": kw.get("budget_s"),
                     "items": [{"sentence": c.sentence, "quotes": list(c.quotes),
                                "writer_quotes": list(c.key[1])} for c in candidates]})
    try:
        approved = await _real_check(candidates, **kw)
    except Exception as exc:
        log("CHECK_RAISED", type(exc).__name__ + ": " + str(exc)[:300])
        raise
    log("CHECK_OUT", {"approved": len(approved), "approved_sentences": [k[0] for k in approved]})
    return approved


g.check_reworded_sentences = _check_spy

_real_gp = g.run_grounding_pass
_findings_logged = False


def _gp_spy(narrative, findings, *a, **kw):
    global _findings_logged
    if not _findings_logged:
        _findings_logged = True
        log("FINDINGS", [{"ref": f.ref_index, "tool": f.tool, "field": f.field, "url": f.source_url,
                          "text": (f.field_value or "")[:4000]} for f in findings])
    res = _real_gp(narrative, findings, *a, **kw)
    sink = kw.get("candidate_sink")
    if sink:
        _log_code_verdicts(sink, findings, kw.get("question") or "")
    log("GROUNDING", {"narrative": narrative[:5000],
                      "verified_syntheses": len(kw.get("verified_syntheses") or ()),
                      "claims": len(res.claims), "stripped": res.stripped_count, "refused": res.refused,
                      "kept_sentences": list(res.sentences),
                      "candidates_collected": len(kw["candidate_sink"]) if kw.get("candidate_sink") is not None else None})
    return res


def _log_code_verdicts(sink, findings, question) -> None:
    from system_03_search_agent.synthesis import grounding as gr

    licensed = gr._licensed_question_content(question)
    labels_by_url: dict[str, str] = {}
    for f in findings:
        url = (f.source_url or "").strip()
        if url and f.field in gr.LABEL_FIELDS:
            labels_by_url[url] = f"{labels_by_url.get(url, '')} {f.field_value}".strip()
    rows = []
    for c in sink:
        pairs = []
        for q in c.key[1]:
            f = next((f for f in findings if q and q in gr._quote_form(f.field_value)), None)
            if f is not None:
                pairs.append((q, f))
        labels = " ".join(labels_by_url.get((f.source_url or "").strip(), "") for _, f in pairs)
        ok = bool(pairs) and len(pairs) == len(c.key[1]) and gr.synthesis_is_supported_by(
            c.sentence, pairs, licensed, labels)
        rows.append({"sentence": c.sentence, "code_word_check_would_approve": ok})
    log("CODE_VERDICTS", rows)


g.run_grounding_pass = _gp_spy


async def main() -> None:
    query = Query(text=QUESTION, session_id=f"sc-{LABEL}", trace_id=f"sc-local-{LABEL}",
                  user_id=None, audience_depth=DEPTH)
    context = RequestContext(surface="rest_sse", session_memory=None)
    t = time.time()
    async for e in run(query, context):
        p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
        if e.type == "token" and p.get("kind") in ("claim", "note", None):
            log("TOKEN", f"{p.get('kind')}: {p['text']}")
        elif e.type in ("done", "error"):
            log(e.type.upper(), {k: p.get(k) for k in ("trust_outcome", "trust_line", "elapsed_ms", "total_cost_usd", "message")})
    log("ELAPSED_S", round(time.time() - t, 1))


asyncio.run(main())
OUT.close()
