"""Adversary probe, card 101: the same quote and sentence through develop's
check_phrases (exported to the scratchpad) and the branch's, side by side.
No model call."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
DEV = Path(os.environ["DEV_SRC"])  # scratch export of origin/develop:src


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(ROOT / "src"))
new = _load(ROOT / "src/system_03_search_agent/synthesis/sentence_check.py", "sc_branch")
old = _load(DEV / "system_03_search_agent/synthesis/sentence_check.py", "sc_dev")

# (name, limiting word dropped, quote, sentence) - each sentence drops the
# limiting word's force but carries another form of it somewhere.
CASES = [
    ("potentially->potential", "potentially",
     "Symptoms potentially caused by GERD are among the most common reasons for visits to primary care physicians.",
     "Symptoms caused by GERD, a condition with potential complications, are among the most common reasons for visits to primary care physicians"),
    ("generally->general", "generally",
     "Proton pump inhibitors are generally safe for long-term use.",
     "Proton pump inhibitors are safe for long-term use in the general population"),
    ("commonly->common", "commonly",
     "Heartburn is commonly caused by gastroesophageal reflux.",
     "Heartburn, a common complaint, is caused by gastroesophageal reflux"),
    ("usually->usual", "usually",
     "Symptoms usually resolve within two weeks of starting therapy.",
     "With usual care, symptoms resolve within two weeks of starting therapy"),
    ("typically->typical", "typically",
     "Infant reflux typically resolves by 12 months of age.",
     "Typical infant reflux resolves by 12 months of age"),
    ("frequently->frequent", "frequently",
     "Patients with Barrett esophagus frequently develop dysplasia.",
     "Patients with Barrett esophagus develop dysplasia and need frequent surveillance"),
    ("largely->large", "largely",
     "The condition is largely asymptomatic in adults.",
     "In a large cohort, the condition is asymptomatic in adults"),
    ("partially->partial", "partially",
     "Lifestyle changes are partially effective in reducing reflux symptoms.",
     "Lifestyle changes, a partial list of which follows, are effective in reducing reflux symptoms"),
    ("moderately->moderate", "moderately",
     "Baclofen is moderately effective in reducing reflux episodes.",
     "Baclofen is effective in reducing reflux episodes in moderate disease"),
    ("significantly->significant", "significantly",
     "Obesity significantly increases the risk of GERD.",
     "Obesity, a significant public health problem, increases the risk of GERD"),
    ("occasionally->occasional", "occasionally",
     "Esophagitis occasionally progresses to stricture.",
     "Esophagitis progresses to stricture, causing occasional dysphagia"),
    ("relatively->relative", "relatively",
     "Complications are relatively rare in treated patients.",
     "Complications are rare in treated patients and their relatives"),
    ("transiently->transient", "transiently",
     "Symptoms transiently improve after fundoplication.",
     "Symptoms improve after fundoplication despite transient dysphagia"),
    ("slightly->slight", "slightly",
     "Long-term PPI use slightly increases the risk of fractures.",
     "Long-term PPI use increases the risk of fractures, with slight variation by age"),
    ("chronically->chronic", "chronically",
     "Chronically treated patients may develop hypomagnesemia.",
     "Treated patients with chronic GERD may develop hypomagnesemia"),
    ("limited->limit (ed to stem)", "limited",
     "Limited evidence suggests that acupuncture reduces reflux symptoms.",
     "Evidence suggests that acupuncture reduces reflux symptoms within the limits of current trials"),
    ("selected->select", "selected",
     "Surgery benefits selected patients with refractory GERD.",
     "Surgery benefits patients with refractory GERD who select it"),
    ("treated->treatment (ment)", "treated",
     "Complications are rare in treated patients.",
     "Complications are rare in patients, whatever their treatment"),
    ("young (control, by design)", "young",
     "Symptoms in young children are varied and nonspecific.",
     "Symptoms in younger and older children are varied and nonspecific"),
    ("certain->certainly", "certain",
     "PPIs reduce acid in certain patients.",
     "PPIs certainly reduce acid in patients"),
    ("rarely->rare (below floor, control)", "rarely",
     "Esophagitis is rarely severe.",
     "Esophagitis is severe and not rare"),
    ("approximately->approximate", "approximately",
     "Approximately 20 percent of adults have weekly heartburn.",
     "20 percent of adults have weekly heartburn, an approximate figure from surveys"),
    ("suspected (ed)", "suspected",
     "In patients with suspected GERD, a trial of PPIs is recommended.",
     "In patients with GERD, a trial of PPIs is recommended when doctors suspect it"),
    ("reported->reports", "reported",
     "Up to 40 percent of patients reported partial response.",
     "Up to 40 percent of patients have partial response, reports show"),
    ("transient (adjective, the card's own word) ->transiently", "transient",
     "Factors include abnormal transient relaxations of the lower esophageal sphincter.",
     "Factors include abnormal relaxations of the lower esophageal sphincter, which open transiently"),
]


def main() -> None:
    hidden = 0
    for name, word, quote, sentence in CASES:
        before = old.check_phrases(sentence, [quote])
        after = new.check_phrases(sentence, [quote])
        b = [p for p in before if word in p.split()]
        a = [p for p in after if word in p.split()]
        flag = "HIDDEN" if b and not a else ("same" if b == a else "changed")
        hidden += flag == "HIDDEN"
        print(f"{flag:7} {name}")
        print(f"   develop pairs with '{word}': {b}")
        print(f"   branch  pairs with '{word}': {a}")
        print(f"   branch all pairs: {after}")
    print(f"limit pairs hidden by the branch: {hidden} of {len(CASES)}")


if __name__ == "__main__":
    main()
