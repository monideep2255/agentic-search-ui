"""Adversary, card 99: fuzz build_pair_calls. Every PAIR block's number,
phrase and sentence must match the question key it is judged under, every
sentence is asked whole or not at all, bounds hold. Offline."""
import json
import random
import re

from system_03_search_agent.harness.jev_client import MAX_BATCH_QUESTIONS
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

VOCAB = ["young", "children", "adults", "elderly", "patients", "symptoms", "potentially", "attributable", "reflux", "disease", "outpatient", "setting", "abnormal", "transient", "relaxations", "sphincter", "rarely", "severe", "common", "may", "reduce", "risk", "esophageal", "adenocarcinoma", "among", "those", "most", "frequently", "reported", "primary", "care"]
rng = random.Random(99)
bad = 0
for trial in range(3000):
    cands = []
    for i in range(rng.randint(1, 30)):
        quotes = tuple(" ".join(rng.choice(VOCAB) for _ in range(rng.randint(3, 90))) + "." for _ in range(rng.randint(1, 3)))
        sentence = " ".join(rng.choice(VOCAB) for _ in range(rng.randint(2, 40)))
        cands.append(SynthesisCandidate(key=(f"k{i}", quotes), sentence=sentence, quotes=quotes))
    _s, sent = sc.build_jev_state(cands)
    calls, not_asked = sc.build_pair_calls(sent)
    asked = {}
    problems = []
    if len(calls) > sc.MAX_PAIR_CALLS:
        problems.append("too many calls")
    for call in calls:
        if len(call.questions) > MAX_BATCH_QUESTIONS or len(call.state) > sc.JEV_STATE_MAX_CHARS:
            problems.append("bounds")
        blocks = call.state.split("\n\n")
        if len(blocks) != len(call.questions):
            problems.append("block count")
        for m, (key, q) in enumerate(call.questions.items(), 1):
            item, k = map(int, key.split("_")[1:])
            if f"Judge PAIR {m} only" not in q.instructions:
                problems.append("instruction number")
            b = blocks[m - 1]
            if not b.startswith(f"PAIR {m}\n"):
                problems.append(f"block {m} header {b[:10]!r}")
            phrase = json.loads(re.search(r"PHRASE: (.*)", b).group(1))
            sentence = json.loads(re.search(r"SENTENCE: (.*)", b).group(1))
            pairs = sc.check_phrases(sent[item - 1].sentence, sent[item - 1].quotes)
            if phrase != pairs[k - 1] or sentence != sent[item - 1].sentence[:sc.MAX_SENTENCE_CHARS]:
                problems.append("block does not match key")
            asked.setdefault(item, set()).add(k)
    for n, c in enumerate(sent, 1):
        npairs = len(sc.check_phrases(c.sentence, c.quotes))
        if n in not_asked:
            if n in asked:
                problems.append("not_asked item still asked")
        elif npairs and asked.get(n) != set(range(1, npairs + 1)):
            problems.append(f"item {n} half asked")
    if problems:
        bad += 1
        if bad < 5:
            print("trial", trial, problems[:5])
print("trials 3000, with problems:", bad)
