"""Adversary, card 99: how many sentences go unasked (so unshown) when a
check carries more sentences than the live 4 to 10, using real live
candidates of 2026-10-05 wave 3 in their recorded order. Offline."""
import json
from pathlib import Path

from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

RAW = Path("testing/Developer/reports/2026-10-05_wave3/sentence_check_raw")
cands = []
for f in sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl")):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if r["tag"] == "CHECK_IN":
            for i in r["data"]["items"]:
                cands.append(SynthesisCandidate(key=(i["sentence"], tuple(i["quotes"])), sentence=i["sentence"], quotes=tuple(i["quotes"])))
print("live candidates", len(cands))
for size in (10, 15, 20, 25, 30):
    rows = []
    for s in range(0, len(cands) - size + 1, size):
        chunk = cands[s:s + size]
        _st, sent = sc.build_jev_state(chunk)
        calls, na = sc.build_pair_calls(sent)
        rows.append((len(sent), len(calls), len(na), sum(len(c.questions) for c in calls)))
    worst = max(rows, key=lambda r: r[2])
    print(f"check of {size}: checks {len(rows)}, mean not asked {sum(r[2] for r in rows)/len(rows):.1f}, "
          f"worst not asked {worst[2]} of {worst[0]}, checks with any not asked {sum(1 for r in rows if r[2])}")
# one sentence with many quotes: how many pairs can a single sentence carry?
big = max(cands, key=lambda c: len(sc.check_phrases(c.sentence, c.quotes)))
print("most pairs for one live sentence:", len(sc.check_phrases(big.sentence, big.quotes)))
