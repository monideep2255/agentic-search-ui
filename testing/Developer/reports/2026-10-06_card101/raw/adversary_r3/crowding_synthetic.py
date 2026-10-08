"""Card 101 round 3 adversary: a constructed answer whose early sentences are
lists of faithful copied cuts from long abstract sentences, followed by
reworded sentences. Do the cut items push the reworded ones out of the
check (sent and pairs asked)? No model call.
Usage: python crowding_synthetic.py <src>
"""
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.findings import SynthFinding


def f(ref, value):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field="abstract", field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
                        entity_type="Publication", curie=f"pubmed:{ref}")


LONG = ("In a multicentre cohort of {n} hospitalised infants recruited over three consecutive winter seasons "
        "across eleven tertiary paediatric centres, {fact}, although the authors caution that residual "
        "confounding by gestational age, socioeconomic status and viral co-detection could not be excluded.")
FACTS = [
    "high-flow nasal cannula therapy reduced escalation of care",
    "nebulised hypertonic saline shortened the length of stay",
    "respiratory syncytial virus was the most frequently detected pathogen",
    "early enteral feeding was associated with fewer complications",
    "chest radiography rarely changed clinical management",
    "bronchodilator trials did not improve oxygen saturation",
    "apnoea occurred mainly in infants younger than two months",
    "corticosteroids did not reduce admission rates",
    "palivizumab prophylaxis was associated with fewer admissions",
]
findings = [f(i + 1, LONG.format(n=100 + i, fact=fact)) for i, fact in enumerate(FACTS)]
REWORD = f(20, "Supportive care, including adequate oxygenation and hydration, remains the mainstay of treatment for acute bronchiolitis in infants.")
findings.append(REWORD)

cut = lambda i: FACTS[i][0].upper() + FACTS[i][1:]
# Three list sentences of three copied cuts each (each clause a faithful cut).
narr = []
for s in range(3):
    a, b, c = 3 * s, 3 * s + 1, 3 * s + 2
    narr.append(f"{cut(a)} [{a + 1}], {FACTS[b]} [{b + 1}], and {FACTS[c]} [{c + 1}].")
# Then reworded sentences, each carrying a valid writer quote.
rewords = [
    ("Supportive care remains the mainstay of treatment for acute bronchiolitis in infants",
     "Supportive care, including adequate oxygenation and hydration, remains the mainstay of treatment for acute bronchiolitis in infants"),
] * 1
quotes = []
for i, (sent, q) in enumerate(rewords):
    narr.append(f"{sent} [20#{i}].")
    quotes.append(q)
narrative = " ".join(narr)
for label, text in (("cuts first", narrative),):
    sink = []
    gr.run_grounding_pass(text, findings, True, "How is bronchiolitis in infants treated?", tuple(quotes), None, sink)
    state, sent = sc.build_jev_state(sink)
    calls, not_asked = sc.build_pair_calls(sent)
    pairs = [len(sc._proposed_pairs(c.sentence, c.quotes)) for c in sink]
    print(label, "items", len(sink), "sent", len(sent), "state chars", len(state), "pair calls", len(calls),
          "items not asked", sorted(not_asked))
    for i, c in enumerate(sink, start=1):
        print(f"  item {i}: pairs {pairs[i-1]:3d} quotes {len(c.quotes)} not asked {i in not_asked} :: {c.sentence[:90]}")
