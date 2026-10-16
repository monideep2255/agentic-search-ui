"""Card 101: a differential fuzz of the new record units against develop's.

Usage: python -I fuzz.py <develop-src> <new-src> [records] [seed]

Random record values from words, sentence ends, quote marks, brackets and the
shapes the reviews used ("S.", "U.S.", "e.g.", "Dr.", "vitamin D.", "?", ";",
":"), and a faithful writer copy of a random span or whole unit of each, run
through `run_grounding_pass` on its first pass with no approvals. Asserted:

- the unit count equals develop's on every record;
- the new tree shows nothing develop does not show;
- every item both trees send carries quotes that contain develop's;
- an item the new tree does not send is reported (held), with a count of
  those where develop's quote was within 600 and not the bare copy.
"""

import importlib
import random
import sys

DEV_SRC, NEW_SRC = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 101


def load(src):
    for name in [key for key in sys.modules if key.startswith("system_03")]:
        del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    sys.path.pop(0)
    return gr


dev = load(DEV_SRC)
new = load(NEW_SRC)

WORDS = ("Mortality was unchanged in the treated group", "Drug X cures cancer", "There was no evidence that aspirin helps",
         "Results were negative", "Infants improved by two days", "Samples were sent", "Resistance was rare",
         "The cohort lacked vitamin D", "No isolates of S. Typhimurium carried the gene", "The U.S. FDA approved it",
         "Smith et al. found a rise", "Dr. A. Smith reported nothing", "Patients were screened for hepatitis B",
         "Some drugs, e.g. aspirin, were excluded", "Is it safe", "Trials continue")
OPEN = ['"', "(", "[", "“", "‘", "'", "«", "„", "”", "5\" needle was used. ", ""]
CLOSE = ['"', ")", "]", "”", "’", "'", "»", "“", ""]
ENDS = [".", ".", ".", "?", "!", ";", ":", "."]


def record(rng):
    parts = []
    for _ in range(rng.randint(2, 9)):
        sentence = rng.choice(WORDS)
        roll = rng.random()
        if roll < 0.25:
            sentence = rng.choice(OPEN) + sentence
        if roll > 0.75:
            sentence = sentence + rng.choice(CLOSE)
        parts.append(sentence + rng.choice(ENDS))
    return " ".join(parts)


def finding(gr, value):
    return gr.SynthFinding(ref_index=1, citation_id="c-1", layer="l", tool="t", field="abstract",
                           field_value=value, source_url="https://example.org/1", entity_type="Publication", curie="pubmed:1")


def first_pass(gr, narrative, value):
    from system_03_search_agent.synthesis import grounding  # noqa: F401  (module already loaded)
    sink = []
    result = gr.run_grounding_pass(narrative, [finding(gr, value)], False, "", None, None, sink)
    return sink, [" ".join(s.split()) for s in result.sentences]


rng = random.Random(SEED)
unequal = more = quote_lost = held = held_in_600 = checked = items_both = 0
for _ in range(N):
    value = record(rng)
    if len(new._record_units(value)) != len(dev._record_sentences(value)) or [t for t, _ in new._record_units(value)] != dev._record_sentences(value):
        unequal += 1
        continue
    units = dev._record_sentences(value)
    if rng.random() < 0.5:
        copy = rng.choice(units)
    else:
        words = value.split()
        i = rng.randrange(len(words) - 3)
        copy = " ".join(words[i : i + rng.randint(3, 8)])
    copy = copy.strip().rstrip(".!?;:")
    if len(copy) < 8 or '"' in copy or "[" in copy or "]" in copy:
        continue
    narrative = f"{copy} [1]."
    d_sink, d_shown = first_pass(dev, narrative, value)
    n_sink, n_shown = first_pass(new, narrative, value)
    checked += 1
    more += sum(1 for s in n_shown if s not in d_shown)
    # A copied clause's key holds its record runs, which glue may widen: match on the sentence.
    d_items = {c.sentence: c.quotes for c in d_sink}
    n_items = {c.sentence: c.quotes for c in n_sink}
    for key, quotes in d_items.items():
        if key in n_items:
            items_both += 1
            if not all(any(q in t for t in n_items[key]) for q in quotes):
                quote_lost += 1
        else:
            held += 1
            if all(len(q) <= 600 and q != copy for q in quotes):
                held_in_600 += 1
print(f"records {N}, seed {SEED}; cases checked {checked}")
print(f"unit count (and unit texts) equal to develop's on {N - unequal} of {N}")
print(f"new tree shows more than develop: {more}")
print(f"items both send {items_both}; items whose quotes lost text develop's carried: {quote_lost}")
print(f"items develop sends that the new tree holds: {held} (of which develop's quote was a run within 600: {held_in_600})")
sys.exit(1 if unequal or more or quote_lost else 0)
