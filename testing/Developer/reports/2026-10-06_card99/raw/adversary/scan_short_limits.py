"""Adversary, card 99: live candidates (2026-10-05 wave 3) and labelled-set
items whose quote has a short limiting word (under 4 letters) the sentence
does not use. Offline."""
import json
from pathlib import Path

from system_03_search_agent.synthesis.sentence_check import _words, check_phrases

SHORT = {"may", "can", "few", "men", "not", "up", "low", "old", "mild", "most", "some", "only", "rare", "less", "all"}
RAW = Path("testing/Developer/reports/2026-10-05_wave3/sentence_check_raw")
def ok(a):
    p = a.get("probabilities", {}); return a.get("choice") == "no" and (p.get("no") or 0) > (p.get("yes") or 0)
seen = set()
for f in sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl")):
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
    jevs = [r["data"] for r in rows if r["tag"] == "JEV_RESULT"]
    for n, chk in enumerate(checks):
        ans = jevs[n].get("answers", {}) if n < len(jevs) else {}
        for i, item in enumerate(chk["items"], 1):
            sw = set(_words(item["sentence"]))
            qw = {w for q in item["quotes"] for w in _words(q)}
            dropped = sorted(w for w in (SHORT & qw) - sw if len(w) < 4)
            if dropped and item["sentence"] not in seen:
                seen.add(item["sentence"])
                print(f"{f.stem} c{n+1} i{i} item_ok={ok(ans.get(f'item_{i}', {}))} dropped_short={dropped}")
                print("   S:", item["sentence"][:300]); print("   Q:", " | ".join(item["quotes"])[:400])
                print("   pairs:", check_phrases(item["sentence"], item["quotes"]))
