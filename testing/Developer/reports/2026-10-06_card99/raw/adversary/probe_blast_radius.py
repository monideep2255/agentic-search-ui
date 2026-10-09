"""Adversary, card 99: one pair call failing removes every sentence of the
check, including sentences with no pair and sentences whose pairs were in
another call that said no. Mocked client, offline, using the live check
gp4 c2 of 2026-10-05 (8 sentences, 3 pair calls)."""
import asyncio
import json
import os
from pathlib import Path

os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import JevAnswer, JevBatchResult, JevCallError
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

rows = [json.loads(l) for l in Path("testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/gp4.jsonl").read_text().splitlines()]
chk = [r["data"] for r in rows if r["tag"] == "CHECK_IN"][1]
cands = [SynthesisCandidate(key=(i["sentence"], tuple(i["quotes"])), sentence=i["sentence"], quotes=tuple(i["quotes"])) for i in chk["items"]]
cands.append(SynthesisCandidate(key=("no pairs", ("x",)), sentence="Heartburn is common", quotes=("Heartburn is common.",)))
count = {"n": 0}

async def fake(*, questions, **kw):
    count["n"] += 1
    if next(iter(questions)).startswith("pair_") and count.get("failed") is None and len(questions) == 30:
        count["failed"] = True
        raise JevCallError("timed out", reason="timeout")
    no = JevAnswer(choice="no", confidence=0.8, probabilities={"no": 0.9, "yes": 0.1})
    return JevBatchResult(resolved_model="m", answers={k: no for k in questions}, input_tokens=1, output_tokens=1, cost_usd=0.0001, latency_ms=10)

sc.call_jev_batch = fake

async def main():
    _s, sent = sc.build_jev_state(cands)
    calls, _na = sc.build_pair_calls(sent)
    print("calls:", [sorted(set(c.items.values())) for c in calls])
    h = Harness(trace_id="t")
    try:
        ok = await sc.check_reworded_sentences(cands, harness=h, trace_id="t", budget_s=12.0, ask_guard=None)
        print("approved", len(ok), "of", len(sent))
    except Exception as e:  # noqa: BLE001
        print("approved 0 of", len(sent), "->", type(e).__name__, str(e)[:100])

asyncio.run(main())
