"""Card 101 round 3 adversary: a held cut turns a middle strip into an end strip.
No model call. Usage: python probe_fragment.py <src-dir>"""
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding


def f(ref, field, value, n):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{n}/",
                        entity_type="Publication", curie=f"pubmed:{n}")


F = [f(1, "name", "Ribavirin", 1),
     f(2, "abstract", "Palivizumab is not approved for treatment.", 2),
     f(3, "abstract", "Montelukast showed no benefit in infants with bronchiolitis.", 3),
     f(4, "title", "Use of Erythromycin in Mustard-Induced Bronchiolitis", 4)]
Q = "Which drugs treat bronchiolitis in babies?"
PROBES = [
    ("fragment prefix", "The drug Ribavirin [1] cures bronchiolitis in babies, as do palivizumab [2] and erythromycin [4]."),
    ("wrapped claim prefix", "Ribavirin can treat bronchiolitis in babies [1], unlike palivizumab which is withdrawn [2], and montelukast showed no benefit in infants [3]."),
    ("claim prefix", "Ribavirin [1] is first-line care, unlike palivizumab which is withdrawn [2], and montelukast showed no benefit in infants [3]."),
]
for label, narrative in PROBES:
    sink = []
    none = gr.run_grounding_pass(narrative, F, False, Q, (), None, sink)
    out = {"probe": label, "no_approval": none.narrative, "items": [c.sentence for c in sink]}
    if sink:
        out["all_approved"] = gr.run_grounding_pass(narrative, F, False, Q, (), frozenset(c.key for c in sink), []).narrative
    print(json.dumps(out))
