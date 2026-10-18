"""Adversary, card 99: which dropped limits does check_phrases never propose?
Offline, pure, no model call."""
from system_03_search_agent.synthesis.sentence_check import check_phrases

CASES = [
    ("may dropped", "Proton pump inhibitors may reduce the risk of esophageal adenocarcinoma.",
     "Proton pump inhibitors reduce the risk of esophageal adenocarcinoma"),
    ("can dropped", "GERD can cause chronic cough in adults.", "GERD causes chronic cough in adults"),
    ("few dropped", "A few patients develop strictures.", "Patients develop strictures"),
    ("not-in-sentence low", "Low dose aspirin reduces cardiovascular events.", "Aspirin reduces cardiovascular events"),
    ("men dropped", "In men, the prevalence of Barrett esophagus is higher.", "The prevalence of Barrett esophagus is higher"),
    ("young children -> kids", "In young children, GERD symptoms are varied and nonspecific.", "In kids, GERD symptoms are varied and nonspecific"),
    ("young children -> a child", "Among young children, symptoms of GERD are varied and nonspecific.", "In a child, symptoms of GERD are varied and nonspecific"),
    ("limit word reused elsewhere", "In young children, GERD symptoms are varied and nonspecific, whereas older children report heartburn.",
     "In children, GERD symptoms are varied and nonspecific, while older children and young adults report heartburn"),
    ("treatment-naive with diaeresis", "In treatment-naïve patients, the drug reduced viral load.", "In patients, the drug reduced viral load"),
    ("curly apostrophe", "Children’s symptoms in infancy are mild.", "Children’s symptoms are mild"),
    ("very rare -> rare kept? both dropped", "Very rarely, severe bleeding occurs.", "Severe bleeding occurs"),
    ("limit moved", "Rarely, severe esophagitis develops in older patients.", "Severe esophagitis rarely develops in patients, older ones especially"),
    ("limit past MAX_QUOTE_CHARS", "x " * 300 + "Symptoms are potentially attributable to GERD.", "Symptoms are attributable to GERD"),
    ("ess hedge 'up to'", "Up to 20 percent of adults report weekly heartburn.", "20 percent of adults report weekly heartburn"),
    ("possibly ", "The variant is possibly pathogenic.", "The variant is pathogenic"),
    ("likely", "The variant is likely pathogenic.", "The variant is pathogenic"),
    ("some", "In some studies, PPIs were associated with fractures.", "PPIs were associated with fractures"),
    ("seems hedge in sentence boundary", "Symptoms are common. Possibly, they reflect reflux.", "Symptoms are common and reflect reflux"),
]
for name, quote, sentence in CASES:
    print(f"{name!r}: {check_phrases(sentence, [quote])}")
