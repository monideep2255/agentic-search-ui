"""Card 101 round 3 adversary: cuts that look whole, and joined whole clauses.

No model call. Usage: python probe_whole.py <src-dir>; one JSON line per probe.
"shown_no_check" is what the first pass shows with no check run and no
approvals; "to_check" the check items collected.
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding


def f(ref, field, value, n=1, etype="Publication"):
    return SynthFinding(ref_index=ref, citation_id=f"c{ref}", layer="layer_2_ncbi_api", tool="ncbi_efetch",
                        field=field, field_value=value, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{n}/",
                        entity_type=etype, curie=f"pubmed:{n}")


Q = "How is bronchiolitis in babies treated?"
PROBES = [
    # label, narrative, findings, quotes
    ("semicolon: limit after '; however'", "Drug X is safe in children [1].",
     [f(1, "abstract", "Drug X is safe in children; however, it caused deaths in infants under 6 months.")], ()),
    ("semicolon: 'not' carried after semicolon", "Antibiotics shorten illness [1].",
     [f(1, "abstract", "Antibiotics shorten illness; this was not confirmed in randomized trials.")], ()),
    ("question title read as statement", "Vitamin D supplementation prevents bronchiolitis in infants [1].",
     [f(1, "title", "Vitamin D supplementation prevents bronchiolitis in infants?")], ()),
    ("question mark mid-abstract", "Does nebulized epinephrine reduce admissions [1].",
     [f(1, "abstract", "Does nebulized epinephrine reduce admissions? We found it did not.")], ()),
    ("question sentence, statement form", "Nebulized epinephrine reduces admissions [1].",
     [f(1, "abstract", "Is it true that nebulized epinephrine reduces admissions? Nebulized epinephrine reduces admissions? No.")], ()),
    ("colon: hypothesis label", "Montelukast reduces wheezing after bronchiolitis [1].",
     [f(1, "abstract", "Hypothesis: montelukast reduces wheezing after bronchiolitis. Results: no reduction was observed.")], ()),
    ("colon: myth label", "Antibiotics treat viral bronchiolitis [1].",
     [f(1, "abstract", "Myth: antibiotics treat viral bronchiolitis. Fact: they do not.")], ()),
    ("colon: 'do not' guidance list, semicolons", "Give antibiotics routinely [1].",
     [f(1, "abstract", "Do not: give antibiotics routinely; use bronchodilators; use systemic corticosteroids.")], ()),
    ("colon: 'There is no evidence for the claim:'", "Aspirin prevents colorectal cancer in adults [1].",
     [f(1, "abstract", "There is no evidence for the claim: aspirin prevents colorectal cancer in adults.")], ()),
    ("abbreviation vs.", "Placebo reduces mortality in adults [1].",
     [f(1, "abstract", "The trial did not show that drug X vs. placebo reduces mortality in adults.")], ()),
    ("abbreviation Dr.", "Smith's regimen cures leukemia in children [1].",
     [f(1, "abstract", "There is no evidence that Dr. Smith's regimen cures leukemia in children.")], ()),
    ("abbreviation et al.", "Reported that ribavirin shortens bronchiolitis, which we could not replicate [1].",
     [f(1, "abstract", "Smith et al. reported that ribavirin shortens bronchiolitis, which we could not replicate.")], ()),
    ("abbreviation e.g. inside a negated list", "Corticosteroids, are effective in infants [1].",
     [f(1, "abstract", "No drug class, e.g. corticosteroids, are effective in infants.")], ()),
    ("abbreviation approx.", "3 in 10 infants needed ventilation [1].",
     [f(1, "abstract", "Fewer than approx. 3 in 10 infants needed ventilation.")], ()),
    ("abbreviation approx., hedge dropped", "30% of infants respond to bronchodilators [1].",
     [f(1, "abstract", "It is often claimed, though unproven, that approx. 30% of infants respond to bronchodilators.")], ()),
    ("quote marks: quoted claim after colon", "Drug X cures cancer [1].",
     [f(1, "abstract", 'Advertisements stated: "Drug X cures cancer." Regulators found this claim false.')], ()),
    ("quote marks: quoted sentence opening", "Vaccines cause autism [1].",
     [f(1, "abstract", '"Vaccines cause autism." This myth persists despite a retracted study.')], ()),
    ("bracketed sentence", "Ribavirin was effective [1].",
     [f(1, "abstract", "Ribavirin was ineffective in the trial. (Ribavirin was effective.) An earlier report claimed otherwise.")], ()),
    ("bracket wraps a hedge removed", "Drug X reduces mortality [1].",
     [f(1, "abstract", "Unproven claim [Drug X reduces mortality.] was tested here and rejected.")], ()),
    ("list item from record", "Use bronchodilators [1].",
     [f(1, "abstract", "Avoid the following. 1. Use bronchodilators. 2. Use corticosteroids.")], ()),
    ("pronoun sentence shifts subject across records",
     "Ribavirin is an antiviral drug [2]. It reduced hospitalization by 55% [1].",
     [f(1, "abstract", "Palivizumab was given to preterm infants. It reduced hospitalization by 55%.", n=1),
      f(2, "abstract", "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended.", n=2)], ()),
    ("pronoun sentence after semicolon, lowercase",
     "Ribavirin is an antiviral drug [2]; it reduced hospitalization by 55% [1].",
     [f(1, "abstract", "Palivizumab was given to preterm infants. It reduced hospitalization by 55%.", n=1),
      f(2, "abstract", "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended.", n=2)], ()),
    ("'This drug' sentence shifts subject",
     "Ribavirin is an antiviral drug [2]. This drug reduced hospitalization by 55% [1].",
     [f(1, "abstract", "Palivizumab was given to preterm infants. This drug reduced hospitalization by 55%.", n=1),
      f(2, "abstract", "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended.", n=2)], ()),
    ("two whole sentences joined in one writer sentence, different records",
     "Ribavirin is an antiviral drug [2], and It reduced hospitalization by 55% [1].",
     [f(1, "abstract", "Palivizumab was given to preterm infants. It reduced hospitalization by 55%.", n=1),
      f(2, "abstract", "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended.", n=2)], ()),
    ("whole sentence then a cut from another record",
     "Ribavirin is an antiviral drug [2] that reduced hospitalization by 55% [1].",
     [f(1, "abstract", "Palivizumab was given to preterm infants. It reduced hospitalization by 55%.", n=1),
      f(2, "abstract", "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended.", n=2)], ()),
    ("same sentence in two records with different limits, writer cites the one without",
     "Hypertonic saline shortens hospital stay [2].",
     [f(1, "abstract", "Hypertonic saline shortens hospital stay only in inpatients.", n=1),
      f(2, "abstract", "Earlier work found no benefit. Hypertonic saline shortens hospital stay. This was a single small trial.", n=2)], ()),
    ("record sentence that is a negated fragment written as a whole", "Not in men [1].",
     [f(1, "abstract", "Drug X reduces mortality in women. Not in men.")], ()),
    ("whole sentence via a second record sentence that is a heading-like line", "Drug X Cures Cancer [1].",
     [f(1, "abstract", "Retracted: Drug X Cures Cancer. The paper was withdrawn for fabricated data.")], ()),
    ("retraction notice as title prefix", "Drug X cures cancer in mice [1].",
     [f(1, "title", "RETRACTED: Drug X cures cancer in mice.")], ()),
    ("first-letter case changes a proper noun to a word", "May improve symptoms [1].",
     [f(1, "abstract", "Some infants were treated. may improve symptoms.")], ()),
    ("control: whole first sentence", "Earlier work found no benefit [2].",
     [f(2, "abstract", "Earlier work found no benefit. Hypertonic saline shortens hospital stay.", n=2)], ()),
    ("control: head cut", "Aspirin prevents colorectal cancer in adults [1].",
     [f(1, "abstract", "There is no evidence that aspirin prevents colorectal cancer in adults.")], ()),
]

for label, narrative, findings, quotes in PROBES:
    sink = []
    res = gr.run_grounding_pass(narrative, findings, True, Q, quotes, None, sink)
    print(json.dumps({"probe": label, "shown_no_check": res.narrative, "to_check": [c.sentence for c in sink]}))
