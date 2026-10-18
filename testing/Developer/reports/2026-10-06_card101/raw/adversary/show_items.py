"""Print sentence, quotes and pairs (develop and branch) for named recorded items."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(HERE))
import scan_removed as s

want = set(sys.argv[1:])
raw = ROOT / "testing/Developer/reports/2026-10-05_wave3/sentence_check_raw"
for path in sorted(raw.glob("*.jsonl")) + sorted((raw / "develop_control").glob("*.jsonl")):
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    for c, d in enumerate([r["data"] for r in rows if r["tag"] == "CHECK_IN"], start=1):
        for i, it in enumerate(d["items"], start=1):
            key = f"{path.stem}c{c}i{i}"
            if key in want:
                print("==", key)
                print("S:", it["sentence"])
                for q in it["quotes"]:
                    print("Q:", q[:400])
                print("develop:", s.old.check_phrases(it["sentence"], it["quotes"]))
                print("branch :", s.new.check_phrases(it["sentence"], it["quotes"]))
