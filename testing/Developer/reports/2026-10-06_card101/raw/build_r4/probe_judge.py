"""Card 101 round 4: judge_r3's in-scope attacks, offline, one JSON line each.

Usage: python -I probe_judge.py <src-dir>
"none": shown with the check approving nothing; "read": what the check was
asked; "all": shown when the check approves every item.
"""
import inspect
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)

LISTING_FLAG = "code_built_listing" in inspect.signature(gr.run_grounding_pass).parameters


def f(ref, value, field="abstract", etype="Publication"):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
                        entity_type=etype, curie=f"pubmed:{ref}")


def run(label, narrative, findings, question=""):
    sink = []
    first = gr.run_grounding_pass(narrative, findings, question=question, candidate_sink=sink)
    approved = frozenset(c.key for c in sink)
    second = gr.run_grounding_pass(narrative, findings, question=question, verified_syntheses=approved)
    print(json.dumps({"probe": label, "none": first.narrative, "read": [c.sentence for c in sink],
                      "all": second.narrative}))


ASPIRIN_Q = "Does aspirin prevent colorectal cancer?"
run("J1 hypothesis", "Aspirin prevents colorectal cancer in adults [1].",
    [f(1, "Background: Many believe a link exists. Hypothesis: aspirin prevents colorectal cancer in adults. "
          "Results: no effect was found.")], ASPIRIN_Q)
run("J1 myth", "Vaccines cause autism [1].", [f(1, "Myth: vaccines cause autism. Fact: large studies found no link.")])
run("J1 misconception", "Antibiotics cure viral bronchiolitis [1].",
    [f(1, "A common misconception is the following: antibiotics cure viral bronchiolitis.")])
run("J1 not recommended", "Antibiotics for bronchiolitis [1].",
    [f(1, "Not recommended: antibiotics for bronchiolitis. Recommended: supportive care.")])
run("J2 however", "Aspirin reduced colorectal cancer incidence [1].",
    [f(1, "Aspirin reduced colorectal cancer incidence; however, this was not seen in randomized trials.")],
    "Does aspirin reduce colorectal cancer incidence?")
run("J2 contraindications", "Aspirin in children [1].",
    [f(1, "Contraindications: aspirin in children; ibuprofen in asthma.")])
run("J3 e.g.", "Aspirin prevents colorectal cancer [1].",
    [f(1, "Several popular claims lack support, e.g. aspirin prevents colorectal cancer.")], ASPIRIN_Q)
US = [f(1, "Mortality fell in the U.S. but rose sharply in every other country studied.")]
run("J3 U.S. glued", "Mortality fell in the U.S.[1]", US)
run("J3 U.S. no stop", "Mortality fell in the U.S [1].", US)
run("J3 yrs.", "Benefit was seen in patients aged 50 to 70 yrs [1].",
    [f(1, "Benefit was seen in patients aged 50 to 70 yrs. but not in older adults.")])
run("J3 faithful i.e.", "Aspirin did not reduce mortality [1].",
    [f(1, "The trial was negative, i.e. aspirin did not reduce mortality.")])
for word in ("But", "And", "Then", "Or"):
    sentence = {"But": "bleeding increased in older adults", "And": "bleeding did not increase",
                "Then": "patients were followed for ten years", "Or": "so the authors claimed"}[word]
    finding = f(1, f"Aspirin was well tolerated. {word} {sentence}.")
    narrative = build_structured_fallback_narrative([finding])
    kwargs = {"code_built_listing": True} if LISTING_FLAG else {}
    res = gr.run_grounding_pass(narrative, [finding], **kwargs)
    print(json.dumps({"probe": f"J4 listing {word}", "shown": res.sentences, "stripped": res.stripped_count}))
CHILD = f(2, "Children", field="population", etype="Population")
run("J5 in children", "Drug X reduces mortality [1] in children [2].",
    [f(1, "Drug X reduces mortality in adults with heart failure."), CHILD],
    "Does drug X reduce mortality in children?")
run("J5 ribavirin infants", "Ribavirin reduced viral load [1] in bronchiolitis in infants [2].",
    [f(1, "Ribavirin reduced viral load in adults with hepatitis C."),
     f(2, "Bronchiolitis in infants", field="title")], "Does ribavirin help bronchiolitis in infants?")
run("J5 whole after cut", "Aspirin lowers the risk of colorectal adenoma [1] and it does not prevent cancer in children [1].",
    [f(1, "In adults aspirin lowers the risk of colorectal adenoma. It does not prevent cancer in children.")])
