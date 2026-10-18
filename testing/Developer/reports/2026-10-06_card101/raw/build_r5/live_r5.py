"""Card 101 round 5: the real sentence check on four cases, end to end.

Each case runs through the real `core.graph._ground_with_sentence_check`
with a real `Harness`: the first grounding pass, the shipped
`check_reworded_sentences` (Jev mode, develop's configured mode, or the
guard tier with `guard` as the mode argument), then the second pass. The
check's verdicts are recorded by wrapping the function `core.graph` calls.
All text is synthetic; nothing from a user or a trace is read.

Usage: MAIN_CHECKOUT=<main checkout with .env> python live_r5.py <src-dir> <jev|guard> <runs>
Appends one line per run and case to live_r5.jsonl beside this script.
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
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
MODE = sys.argv[2]
if MODE == "jev":
    os.environ["CLASSIFIER_PROVIDER"] = "jev"
else:
    os.environ.pop("CLASSIFIER_PROVIDER", None)
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"
sys.path.insert(0, sys.argv[1])

from system_03_search_agent.core import graph
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import extract_evidence_quotes


def f(ref, value, field="abstract"):
    return SynthFinding(ref_index=ref, citation_id=f"c-{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
                        entity_type="Publication", curie=f"pubmed:{ref}")


SYMPTOMATIC = f(9, "Treatment of bronchiolitis in infants is usually supportive.")
SYMPTOMATIC_COPY = "Treatment of bronchiolitis in infants is usually supportive [9]."
AZITHROMYCIN = (
    "Azithromycin shortens the course of bronchiolitis in infants [1] only when a bacterial "
    "co-infection is confirmed by culture [2]."
)
NO_EVIDENCE_RUN = (
    "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. "
    "142 infants were enrolled at six sites over three winters and followed for 21 days by parents "
    "using daily symptom diaries. 95% of diaries were returned complete and were scored blind by two "
    "investigators who did not know the allocation. p values were adjusted for the number of "
    "comparisons made across the secondary outcomes reported in the trial. 16 serious adverse events "
    "occurred, none judged related to the study drug by the independent safety board. 3 infants were "
    "withdrawn by their parents before the end of the study."
)
CASES = {
    "azithromycin limit": (
        f"{AZITHROMYCIN} {SYMPTOMATIC_COPY}",
        [
            f(1, "Azithromycin shortens the course of bronchiolitis in infants.", "title"),
            f(2, "Azithromycin shortens the course of bronchiolitis in infants only when a bacterial "
                 "co-infection is confirmed by culture; otherwise it has no effect."),
            SYMPTOMATIC,
        ],
    ),
    "no evidence, long run": (
        (
            f"Azithromycin shortened the illness in infants with bronchiolitis [1]. {SYMPTOMATIC_COPY} "
            "No serious harm was seen in either group [3]."
        ),
        [
            f(1, NO_EVIDENCE_RUN),
            SYMPTOMATIC,
            f(3, "Objective: To compare two regimens. Results: no serious harm was seen in either group."),
        ],
    ),
    "partial verdict, names": (
        "Ribavirin [4] and palivizumab [5] are used to treat bronchiolitis [6].",
        [
            f(4, "Ribavirin aerosol therapy", "title"),
            f(5, "Palivizumab prophylaxis", "title"),
            f(6, "Several antivirals are used to treat bronchiolitis in infants."),
        ],
    ),
    "faithful whole copy": (
        f"{SYMPTOMATIC_COPY} No serious harm was seen in either group [3].",
        [
            SYMPTOMATIC,
            f(3, "Objective: To compare two regimens. Results: no serious harm was seen in either group."),
        ],
    ),
}
QUESTION = "How is bronchiolitis in infants treated, and does azithromycin help?"

verdicts: list[dict] = []
real_check = graph.check_reworded_sentences


async def recording_check(candidates, **kwargs):
    try:
        approved = await real_check(candidates, **kwargs)
    except Exception as exc:
        verdicts.append({"items": [c.sentence for c in candidates], "error": type(exc).__name__})
        raise
    verdicts.append({
        "items": [c.sentence for c in candidates],
        "approved": [c.sentence for c in candidates if c.key in approved],
    })
    return approved


graph.check_reworded_sentences = recording_check


async def main(runs: int) -> None:
    out_path = Path(__file__).with_name("live_r5.jsonl")
    for run in range(1, runs + 1):
        for name, (narrative, findings) in CASES.items():
            verdicts.clear()
            trace_id = f"card101r5-{MODE}-{run}-{name.split()[0]}"
            harness = Harness(trace_id=trace_id)
            rewritten, quotes = extract_evidence_quotes(narrative)
            result = await graph._ground_with_sentence_check(
                rewritten, findings, question=QUESTION, evidence_quotes=quotes,
                harness=harness, trace_id=trace_id, budget_s=13.0,
            )
            row = {
                "mode": MODE, "run": run, "case": name,
                "check_calls": len(verdicts), "verdicts": verdicts[:],
                "shown": list(result.sentences),
                "cost_usd": round(harness.get_query_cost_usd(trace_id), 6),
            }
            print(json.dumps(row))
            with out_path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")


asyncio.run(main(int(sys.argv[3])))
