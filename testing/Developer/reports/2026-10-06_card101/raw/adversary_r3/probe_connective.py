"""Card 101 round 3 adversary: a whole record sentence that opens on a
connective `_clean_claim` strips ("But", "And", "Or", "Then", "Also ").
Written by the writer word for word, and in the code-built fallback.
No model call. Usage: python probe_connective.py <src>
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)


def f(ref, value):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field="abstract", field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
                        entity_type="Publication", curie=f"pubmed:{ref}")


REC = f(1, "Bronchodilators are widely used in infants with bronchiolitis. But they do not improve oxygen saturation. "
           "Then most infants recover within two weeks. And supportive care remains the mainstay of treatment.")
Q = "How is bronchiolitis in babies treated?"
cases = [
    ("writer copies 'But ...' whole", "Bronchodilators are widely used in infants with bronchiolitis [1]. But they do not improve oxygen saturation [1]."),
    ("writer copies 'And ...' whole", "And supportive care remains the mainstay of treatment [1]."),
    ("writer copies 'Then ...' whole", "Then most infants recover within two weeks [1]."),
    ("code-built fallback of the record", build_structured_fallback_narrative([REC])),
]
for label, narrative in cases:
    sink = []
    res = gr.run_grounding_pass(narrative, [REC], True, Q, (), None, sink)
    keys = frozenset(c.key for c in sink)
    approved = gr.run_grounding_pass(narrative, [REC], True, Q, (), keys, None)
    print(json.dumps({"case": label, "narrative": narrative, "shown_no_check": res.narrative,
                      "to_check": [c.sentence for c in sink], "shown_if_all_approved": approved.narrative}))
