"""Adversary, card 99: a phrase found in two quotes is asked once, with the
FIRST quote as its context. Offline."""
import json
from pathlib import Path

from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

q1 = "Gastroesophageal reflux is common in young children and usually resolves without treatment."
q2 = "In young children, GERD symptoms are varied and nonspecific, so a careful diagnostic evaluation is needed."
s = "In children, GERD symptoms are varied and nonspecific, so a careful diagnostic evaluation is needed"
cand = SynthesisCandidate(key=(s, (q1, q2)), sentence=s, quotes=(q1, q2))
print("pairs:", sc._proposed_pairs(s, [q1, q2]))
calls, na = sc.build_pair_calls([cand])
print(calls[0].state)

# How often, in live candidates and the labelled set, does a proposed phrase
# occur in more than one quote of the same item?
RAW = Path("testing/Developer/reports/2026-10-05_wave3/sentence_check_raw")
hits = 0; total = 0
for f in sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl")):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if r["tag"] != "CHECK_IN":
            continue
        for it in r["data"]["items"]:
            total += 1
            for phrase, quote in sc._proposed_pairs(it["sentence"], it["quotes"]):
                others = [q for q in it["quotes"] if q[:sc.MAX_QUOTE_CHARS] != quote and phrase in " ".join(sc._words(q[:sc.MAX_QUOTE_CHARS]))]
                if others:
                    hits += 1
                    print("LIVE", f.stem, repr(phrase), "| asked with:", quote[:120], "| also in:", others[0][:120])
ev = Path("testing/Developer/reports/2026-10-05_qualifier_check/raw/eval_set.jsonl")
for line in ev.read_text().splitlines():
    it = json.loads(line)
    for phrase, quote in sc._proposed_pairs(it["sentence"], it["quotes"]):
        others = [q for q in it["quotes"] if q[:sc.MAX_QUOTE_CHARS] != quote and phrase in " ".join(sc._words(q[:sc.MAX_QUOTE_CHARS]))]
        if others:
            print("EVAL", it["id"], it["label"], repr(phrase))
print("live items", total, "phrase-in-two-quotes hits", hits)
