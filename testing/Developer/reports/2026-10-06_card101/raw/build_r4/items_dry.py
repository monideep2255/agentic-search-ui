"""Card 101 round 4: the check items live_r3.py sent, built by a given tree (no model call)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
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
out = []
for label, narrative, fs in SYNTH:
    sink = []
    run_grounding_pass(narrative, fs, False, "", (), None, sink)
    out += [[label, c.sentence, list(c.quotes)] for c in sink]
rows = [json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines() if x.strip()]
data = next(r["data"] for r in rows if r.get("tag") == "FINDINGS")
fs = [SynthFinding(ref_index=int(d["ref"]), citation_id=f"c-{d['ref']}", layer="", tool=d.get("tool", ""),
                   field=d["field"], field_value=d["text"] or "", source_url=d.get("url", "")) for d in data]
narrative = next(r["data"]["narrative"] for r in rows if r.get("tag") == "GROUNDING")
sink = []
run_grounding_pass(narrative, fs, False, "", (), None, sink)
out += [[f"hb4_item{i}", c.sentence, list(c.quotes)] for i, c in enumerate(sink)]
print(json.dumps(out))
