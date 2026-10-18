"""Card 101 round 3 adversary (adapted from round 2's live_cuts.py): would the shipped Jev check (item call plus card
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
    ("colon_aspirin", "Aspirin prevents colorectal cancer in adults",
     ("There is no evidence for the claim: aspirin prevents colorectal cancer in adults.",)),
    ("question_title", "Vitamin D supplementation prevents bronchiolitis in infants",
     ("Vitamin D supplementation prevents bronchiolitis in infants?",)),
    ("abbrev_vs", "Placebo reduces mortality in adults",
     ("The trial did not show that drug X vs. placebo reduces mortality in adults.",)),
    ("quoted_claim", "Drug X cures cancer",
     ('Advertisements stated: "Drug X cures cancer." Regulators found this claim false.',)),
    ("semicolon_limit", "Drug X is safe in children",
     ("Drug X is safe in children; however, it caused deaths in infants under 6 months.",)),
    ("pronoun_switch", "Ribavirin is an antiviral drug. It reduced hospitalization by 55%",
     ("Ribavirin is an antiviral drug.", "Palivizumab was given to preterm infants. It reduced hospitalization by 55%.")),
    ("connective_faithful", "But they do not improve oxygen saturation",
     ("Bronchodilators are widely used in infants with bronchiolitis. But they do not improve oxygen saturation.",)),
    ("control_faithful", "Use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis",
     ("Use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis.",)),
]
cands = [SynthesisCandidate(key=(i, q), sentence=s, quotes=q) for i, s, q in ITEMS]
pair_calls, not_asked = sc.build_pair_calls(cands)
print("Jev calls this check:", 1 + len(pair_calls), "not asked:", sorted(not_asked))


async def _never_guard(_m, _b):
    raise AssertionError("Jev mode never asks the guard tier")


async def main(rep):
    trace = f"adv101r3-{rep}"
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
    with open(Path(__file__).with_name("live_routes.jsonl"), "a") as out:
        out.write(json.dumps(result) + "\n")
