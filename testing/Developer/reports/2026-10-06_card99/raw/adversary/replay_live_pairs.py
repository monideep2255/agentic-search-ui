"""Adversary, card 99: replay every live CHECK_IN of 2026-10-05 wave 3
through build_pair_calls. Offline, no model call."""
from __future__ import annotations

import json
from pathlib import Path

from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

RAW = Path("testing/Developer/reports/2026-10-05_wave3/sentence_check_raw")

def ok(a):
    p = a.get("probabilities", {})
    return a.get("choice") == "no" and (p.get("no") or 0) > (p.get("yes") or 0)

files = sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl"))
tot_pairs = []
for f in files:
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
    jevs = [r["data"] for r in rows if r["tag"] == "JEV_RESULT"]
    for n, chk in enumerate(checks):
        cands = [SynthesisCandidate(key=(i["sentence"], tuple(i.get("writer_quotes", i["quotes"]))), sentence=i["sentence"], quotes=tuple(i["quotes"])) for i in chk["items"]]
        state, sent = sc.build_jev_state(cands)
        calls, not_asked = sc.build_pair_calls(sent)
        answers = jevs[n].get("answers", {}) if n < len(jevs) else {}
        appr = [i for i in range(1, len(sent)+1) if ok(answers.get(f"item_{i}", {}))]
        npairs = [len(sc.check_phrases(c.sentence, c.quotes)) for c in sent]
        appr_with_pairs = [i for i in appr if npairs[i-1] > 0]
        tot_pairs.append(sum(npairs))
        print(f"{f.stem} c{n+1}: items {len(sent)}, pairs/item {npairs}, calls {len(calls)}, not_asked {sorted(not_asked)}, item-approved {appr}, approved-and-at-risk {appr_with_pairs}")
print("pairs per check: min", min(tot_pairs), "max", max(tot_pairs), "mean", sum(tot_pairs)/len(tot_pairs))
