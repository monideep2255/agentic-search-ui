"""Adversary, card 99: the info log's "held back by a pair" count includes
sentences the item question had already rejected. Mocked client, offline."""
import asyncio
import logging
import os

os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
logging.basicConfig(level=logging.INFO, format="%(message)s")
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import JevAnswer, JevBatchResult
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

yes = JevAnswer(choice="yes", confidence=0.8, probabilities={"no": 0.1, "yes": 0.9})
async def fake(*, questions, **kw):
    return JevBatchResult(resolved_model="m", answers={k: yes for k in questions}, input_tokens=1, output_tokens=1, cost_usd=0.0001, latency_ms=10)
sc.call_jev_batch = fake
q = "In young children, GERD symptoms are varied and nonspecific."
cands = [SynthesisCandidate(key=(f"s{i}", (q,)), sentence=f"In children, GERD symptoms are varied {i}", quotes=(q,)) for i in range(3)]
async def main():
    ok = await sc.check_reworded_sentences(cands, harness=Harness(trace_id="t"), trace_id="t", budget_s=12.0, ask_guard=None)
    print("approved by the item question: 0; approved overall:", len(ok))
asyncio.run(main())
