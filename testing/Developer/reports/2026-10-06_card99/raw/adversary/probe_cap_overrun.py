"""Adversary, card 99: concurrent calls that come back unusable are each
billed the $0.01 ceiling after a pre-check that reserved $0.003 each.
Mocked Jev client, offline."""
import asyncio
import os

os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.10"
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import MAX_JEV_COST_USD, JevCallError
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate


async def bad(**kw):
    await asyncio.sleep(0.01)
    raise JevCallError("unusable", reason="malformed_reply", billed_cost_usd=MAX_JEV_COST_USD)

sc.call_jev_batch = bad

def cands(n):
    # long sentences with many pairs so the check needs the full 4 pair calls
    q = ("In young children with chronic gastroesophageal reflux disease, symptoms potentially attributable "
         "to the disorder are frequently reported to primary care providers in the outpatient setting, "
         "and abnormal transient relaxations of the lower esophageal sphincter may contribute. ")
    return [SynthesisCandidate(key=(f"s{i}", (q,)), sentence=f"Item {i}: symptoms of reflux disease are reported to doctors", quotes=(q,)) for i in range(n)]

async def main():
    for pre in (0.0, 0.05, 0.08, 0.085):
        h = Harness(trace_id="t")
        if pre:
            h.track_cost("t", "guard", pre)
        cs = cands(12)
        _s, sent = sc.build_jev_state(cs)
        pcs, _na = sc.build_pair_calls(sent)
        try:
            await sc.check_reworded_sentences(cs, harness=h, trace_id="t", budget_s=12.0, ask_guard=None)
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
        print(f"pre-spent ${pre:.3f}: calls {1+len(pcs)}, outcome {err}, spent after ${h.get_query_cost_usd('t'):.3f}, "
              f"cap ${cost_control.per_query_cost_cap_usd():.2f}, guard estimate ${cost_control.estimate_call_cost_usd('guard'):.3f}")

asyncio.run(main())
