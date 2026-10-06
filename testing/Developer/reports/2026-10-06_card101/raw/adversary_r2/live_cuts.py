"""Card 101 round 2 adversary: would the shipped Jev check (item call plus card
99's pair check) hold back the cuts and the wrapped value that still skip it,
if they were sent? Each sentence goes with its whole record sentence as the
quote, as the check reads it after card 89. Credentials from the main
checkout's .env, read into this process only and never printed.

Usage: python live_cuts.py <rep> ; prints approvals and the Jev call count.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ["MAIN_CHECKOUT"])
for raw in (ROOT / ".env").read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"
sys.path.insert(0, os.environ["WORKTREE"] + "/src")

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

ITEMS = [
    ("tail_antibiotics", "Antibiotics are effective", "Antibiotics are effective only when a bacterial infection is confirmed."),
    ("tail_selflimited", "Bronchiolitis is a self-limited disease", "Bronchiolitis is a self-limited disease in healthy infants and children."),
    ("wrap_ribavirin", "Ribavirin can cure bronchiolitis in babies", "Ribavirin"),
    ("control_faithful", "Treatment usually focuses on symptoms, aiming to keep oxygen and fluids adequate",
     "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate oxygenation and hydration."),
]
cands = [SynthesisCandidate(key=(i, (q,)), sentence=s, quotes=(q,)) for i, s, q in ITEMS]
pair_calls, not_asked = sc.build_pair_calls(cands)
print("Jev calls this check:", 1 + len(pair_calls), "not asked:", sorted(not_asked))


async def _never_guard(_m, _b):
    raise AssertionError("Jev mode never asks the guard tier")


async def main(rep):
    trace = f"adv101r2-{rep}"
    harness = Harness(trace_id=trace)
    try:
        approved = await sc.check_reworded_sentences(cands, harness=harness, trace_id=trace, budget_s=11.0,
                                                     ask_guard=_never_guard)
        err = None
    except Exception as exc:  # noqa: BLE001  measurement: record and go on
        approved, err = frozenset(), type(exc).__name__
    row = {"rep": rep, "approved": sorted(k[0] for k in approved), "error": err,
           "jev_calls": 1 + len(pair_calls), "cost_usd": harness.get_query_cost_usd(trace)}
    print(json.dumps(row))
    return row

if sys.argv[1] != "dry":
    result = asyncio.run(main(sys.argv[1]))
    with open(Path(__file__).with_name("live_cuts.jsonl"), "a") as out:
        out.write(json.dumps(result) + "\n")
