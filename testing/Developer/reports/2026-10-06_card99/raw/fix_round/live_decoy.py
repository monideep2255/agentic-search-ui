"""Fix round, card 99: A-99-01 live check through `check_reworded_sentences`.

One sentence, the adversary's decoy case (the decoy quote first), in Jev mode.
Two billed calls at most: the item call and one pair call. Records the pairs
asked and Jev's answers; no secret is printed or written.

Usage (from the worktree root): ENV_FILE=<env file> python live_decoy.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
for line in Path(os.environ["ENV_FILE"]).read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

Q1 = "Gastroesophageal reflux is common in young children and usually resolves without treatment."
Q2 = "In young children, GERD symptoms are varied and nonspecific, so a careful diagnostic evaluation is needed."
S = "In children, GERD symptoms are varied and nonspecific, so a careful diagnostic evaluation is needed"
CAND = SynthesisCandidate(key=(S, (Q1, Q2)), sentence=S, quotes=(Q1, Q2))

recorded: list[dict] = []
real = sc.call_jev_batch


async def wrapped(**kwargs):
    result = await real(**kwargs)
    recorded.append(
        {
            "keys": list(kwargs["questions"]),
            "cost_usd": result.cost_usd,
            "answers": {k: {"choice": a.choice, "p": dict(a.probabilities)} for k, a in result.answers.items()},
            "state": kwargs["state"],
        }
    )
    return result


sc.call_jev_batch = wrapped


async def main() -> None:
    approved = await sc.check_reworded_sentences(
        [CAND], harness=Harness(trace_id="fix-r"), trace_id="fix-r", budget_s=11.0, ask_guard=None
    )
    row = {"approved": bool(approved), "calls": recorded}
    print(json.dumps({k: v for k, v in row.items() if k != "calls"}), "billed calls:", len(recorded))
    for call in recorded:
        for key, ans in call["answers"].items():
            print(key, ans["choice"], ans["p"])
    with open(HERE / "live_decoy.jsonl", "a") as f:  # noqa: ASYNC230
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


asyncio.run(main())
