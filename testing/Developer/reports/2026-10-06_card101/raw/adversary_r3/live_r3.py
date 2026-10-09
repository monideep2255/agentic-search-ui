"""Card 101 round 3 adversary: what the shipped check says about items this
round's routing creates or would create under a tightened whole-sentence test.

Items are built by `run_grounding_pass` from the source tree given (the branch,
or a scratch copy with the colon start and the question mark removed), then
judged by the shipped `check_reworded_sentences` in Jev mode. Record text from
the recorded trace is read at run time and never written out; output is labels.

Usage: MAIN_CHECKOUT=<main> python live_r3.py <src-dir> <rep> <hb4-trace>
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
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"
sys.path.insert(0, sys.argv[1])

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import run_grounding_pass


def f(ref, field, value, n):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{n}/",
                        entity_type="Publication", curie=f"pubmed:{n}")


SYNTH = [
    ("colon_retracted", "Drug X cures cancer in mice [1].", [f(1, "title", "RETRACTED: Drug X cures cancer in mice.", 1)]),
    ("colon_no_evidence_claim", "Aspirin prevents colorectal cancer in adults [1].",
     [f(1, "abstract", "There is no evidence for the claim: aspirin prevents colorectal cancer in adults.", 1)]),
    ("question_title", "Vitamin D supplementation prevents bronchiolitis in infants [1].",
     [f(1, "title", "Vitamin D supplementation prevents bronchiolitis in infants?", 1)]),
    ("faithful_results_label", "No serious harm was seen in either group [1].",
     [f(1, "abstract", "Objective: To compare two regimens. Results: no serious harm was seen in either group.", 1)]),
    ("faithful_conclusion_label", "Supportive care remains the mainstay of treatment [1].",
     [f(1, "abstract", "Methods: We reviewed 12 trials. Conclusions: supportive care remains the mainstay of treatment.", 1)]),
]


def hb4_items(trace):
    rows = [json.loads(x) for x in Path(trace).read_text().splitlines() if x.strip()]
    data = next(r["data"] for r in rows if r.get("tag") == "FINDINGS")
    fs = [SynthFinding(ref_index=int(d["ref"]), citation_id=f"c-{d['ref']}", layer="", tool=d.get("tool", ""),
                       field=d["field"], field_value=d["text"] or "", source_url=d.get("url", "")) for d in data]
    narrative = next(r["data"]["narrative"] for r in rows if r.get("tag") == "GROUNDING")
    sink = []
    run_grounding_pass(narrative, fs, False, "", (), None, sink)
    return [(f"hb4_item{i}", c) for i, c in enumerate(sink)]


async def main(src, rep, trace):
    items = []
    for label, narrative, fs in SYNTH:
        sink = []
        run_grounding_pass(narrative, fs, False, "", (), None, sink)
        items += [(label, c) for c in sink]
    items += hb4_items(trace)
    if rep == "dry":
        for label, c in items:
            print(label, "|", c.sentence[:90], "| quotes", len(c.quotes))
        return
    cands = [c for _, c in items]
    pairs, not_asked = sc.build_pair_calls(cands)  # noqa: RUF059
    trace_id = f"adv101r3-{rep}"
    harness = Harness(trace_id=trace_id)

    async def never(_m, _b):
        raise AssertionError("jev mode")
    try:
        approved = await sc.check_reworded_sentences(cands, harness=harness, trace_id=trace_id, budget_s=11.0, ask_guard=never)
        err = None
    except Exception as exc:  # noqa: BLE001
        approved, err = frozenset(), type(exc).__name__
    out = {"rep": rep, "src": "tight" if "tight" in src else "branch",
           "approved": [lab for lab, c in items if c.key in approved],
           "held": [lab for lab, c in items if c.key not in approved],
           "error": err, "jev_calls": 1 + len(pairs), "cost_usd": harness.get_query_cost_usd(trace_id)}
    print(json.dumps(out))
    with open(Path(__file__).with_name("live_r3.jsonl"), "a") as fh:  # noqa: ASYNC230
        fh.write(json.dumps(out) + "\n")


asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
