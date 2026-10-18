"""Card 101 round 2 adversary: if a copied cut were sent down the reworded path
with its whole record sentence as the quote (the diagnosis's option D), would
code's exact checks alone stop the reversals? No model call."""
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding


def f(v):
    return SynthFinding(ref_index=1, citation_id="c1", layer="l", tool="t", field="abstract", field_value=v,
                        source_url="u", entity_type="Publication", curie="pubmed:1")
CASES = [
    ("Aspirin prevents colorectal cancer in adults", "There is no evidence that aspirin prevents colorectal cancer in adults."),
    ("Montelukast improves symptoms", "Earlier studies suggested that montelukast improves symptoms, but this trial found no benefit."),
    ("Drug X reduces mortality in men", "Drug X reduces mortality in women but not in men."),
    ("Antibiotics are effective", "Antibiotics are effective only when a bacterial infection is confirmed."),
    ("Bronchiolitis is a self-limited disease", "Bronchiolitis is a self-limited disease in healthy infants and children."),
]
for claim, rec in CASES:
    print(f"{gr.exact_synthesis_checks_pass(claim, [(rec, f(rec))], '')!s:5} | {claim} | quote: {rec}")
