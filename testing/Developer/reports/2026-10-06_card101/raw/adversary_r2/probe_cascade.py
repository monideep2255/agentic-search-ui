"""Card 101 round 2 adversary: when the check holds back a sentence code used to
approve, what ELSE leaves the screen with it? Mocked check verdicts, no model.

Usage: python probe_cascade.py <src-dir>
Check verdict mocked: every candidate approved EXCEPT the sentence code used to
approve (the decision's accepted cost, about 1 in 9 such sentences).
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

ABS = ("Bronchiolitis is a self-limited disease in healthy infants and children. It usually lasts about two weeks. "
       "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate oxygenation and hydration.")
A = SynthFinding(ref_index=1, citation_id="c1", layer="layer_2_ncbi_api", tool="ncbi_efetch", field="abstract",
                 field_value=ABS, source_url="https://pubmed.ncbi.nlm.nih.gov/1/", entity_type="Publication", curie="pubmed:1")
T = SynthFinding(ref_index=2, citation_id="c2", layer="layer_2_ncbi_api", tool="ncbi_efetch", field="title",
                 field_value="Bronchiolitis in children.", source_url="https://pubmed.ncbi.nlm.nih.gov/1/",
                 entity_type="Publication", curie="pubmed:1")
F = [A, T]
Q = "What causes bronchiolitis in babies, and how is it usually treated?"
CODE_OK = "Bronchiolitis is a self-limited disease in infants and children"   # dropped "healthy": code approved it on develop
CASES = {
    "copied pronoun sentence after it": (
        f"{CODE_OK} [1#0]. It usually lasts about two weeks [1].",
        ("Bronchiolitis is a self-limited disease in healthy infants and children",)),
    "approved rewording after it, same record, not naming it": (
        f"{CODE_OK} [1#0]. Care mainly treats the symptoms and keeps oxygen and fluids adequate [1#1].",
        ("Bronchiolitis is a self-limited disease in healthy infants and children",
         "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate oxygenation and hydration")),
    "copied clause after it in the same sentence": (
        f"{CODE_OK} [1#0], and treatment is usually symptomatic [1].",
        ("Bronchiolitis is a self-limited disease in healthy infants and children",)),
}
for label, (narr, quotes) in CASES.items():
    sink = []
    first = gr.run_grounding_pass(narr, F, True, Q, quotes, None, sink)
    approved = frozenset(c.key for c in sink if c.sentence != CODE_OK)
    final = gr.run_grounding_pass(narr, F, True, Q, quotes, approved) if approved else first
    print(json.dumps({"case": label, "candidates": [c.sentence for c in sink],
                      "check_holds_back": CODE_OK if any(c.sentence == CODE_OK for c in sink) else None,
                      "shown": final.narrative}))
