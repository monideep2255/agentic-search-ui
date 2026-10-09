"""Card 101 round 2 adversary: which rewordings still reach the screen with no
sentence check, on develop and on this branch. No model call.

Usage: python probe_paths_r2.py <src-dir> ; prints one JSON line per probe.
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

URL = "https://pubmed.ncbi.nlm.nih.gov/1/"


def finding(ref, field, value, url=URL, etype="Publication", curie="pubmed:1"):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=url, entity_type=etype, curie=curie)


ABS = ("There is no evidence that aspirin prevents colorectal cancer in adults. "
       "Earlier studies suggested that montelukast improves symptoms, but this trial found no benefit. "
       "Antibiotics are effective only when a bacterial infection is confirmed. "
       "Drug X reduces mortality in women but not in men. "
       "Bronchiolitis is a self-limited disease in healthy infants and children. "
       "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate oxygenation and hydration. "
       "Use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis.")
F_ABS = finding(1, "abstract", ABS)
F_TITLE = finding(2, "title", "Acute bronchiolitis.")
F_DRUG = finding(3, "name", "Ribavirin", url="https://www.ncbi.nlm.nih.gov/mesh/1", etype="Chemical", curie="mesh:D012254")
F_ABS2 = finding(4, "abstract", "Nebulized hypertonic saline is used in infants with bronchiolitis.",
                 url="https://pubmed.ncbi.nlm.nih.gov/2/", curie="pubmed:2")
F = [F_ABS, F_TITLE, F_DRUG, F_ABS2]
Q_OPEN = "What causes bronchiolitis in babies, and how is it usually treated?"
Q_DRUG = "Which drugs can cure bronchiolitis in babies?"

PROBES = [
    ("P1 head cut reverses: 'no evidence that' dropped", "Aspirin prevents colorectal cancer in adults [1].", (), Q_OPEN),
    ("P1 head cut reverses, with the writer's own quote", 'Aspirin prevents colorectal cancer in adults [1#0].', ("aspirin prevents colorectal cancer in adults",), Q_OPEN),
    ("P1 head cut reverses: 'earlier studies suggested' dropped", "Montelukast improves symptoms [1].", (), Q_OPEN),
    ("P1 head cut, lowercase (fragment rule control)", "aspirin prevents colorectal cancer in adults [1].", (), Q_OPEN),
    ("P1 tail cut drops 'only when infection is confirmed'", "Antibiotics are effective [1].", (), Q_OPEN),
    ("P1 tail cut drops 'in healthy infants and children'", "Bronchiolitis is a self-limited disease [1].", (), Q_OPEN),
    ("P1 case changed in a copy", "Use Of A High-Flow Nasal Cannula is becoming common for children with severe bronchiolitis [1].", (), Q_OPEN),
    ("Punctuation changed in a copy (control, expect check)", "Use of a high flow nasal cannula is becoming common for children with severe bronchiolitis [1#0].", ("Use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis",), Q_OPEN),
    ("Two copied clauses composed into a reversal", "Drug X reduces mortality [1] in men [1].", (), Q_OPEN),
    ("Two records composed: cut of one, cut of another", "Use of a high-flow nasal cannula is becoming common [1] in infants with bronchiolitis [4].", (), Q_OPEN),
    ("Copy joined from two record sentences with 'and'", "Bronchiolitis is a self-limited disease in healthy infants and children [1], and treatment is usually symptomatic [1].", (), Q_OPEN),
    ("P2 title wrapped in question words", "Acute bronchiolitis is usually treated in babies [2].", (), Q_OPEN),
    ("P2 drug name wrapped in an open question's words", "Ribavirin can cure bronchiolitis in babies [3].", (), Q_DRUG),
    ("P2 drug name plus 'all' (function word)", "Ribavirin can cure bronchiolitis in all babies [3].", (), Q_DRUG),
    ("Former P3: babies for children (expect check)", "For babies with severe bronchiolitis, use of a high-flow nasal cannula is becoming common [1#0].", ("Use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis",), Q_OPEN),
    ("Former P3: dropped 'usually' (expect check)", "Bronchiolitis is a self-limited disease in healthy infants and children [1]. Treatment is symptomatic [1#0].", ("Treatment is usually symptomatic",), Q_OPEN),
]

for label, narrative, quotes, q in PROBES:
    sink = []
    res = gr.run_grounding_pass(narrative, F, True, q, quotes, None, sink)
    print(json.dumps({
        "probe": label,
        "shown_without_check": res.narrative,
        "to_check": [c.sentence for c in sink],
    }))
