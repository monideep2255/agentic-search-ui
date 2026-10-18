"""Per answer: seconds inside the sentence check, items asked, and seconds before the write step."""
import json
from pathlib import Path

for d, labels in (("live", None), ("../out", ("hb", "hd"))):
    for p in sorted(Path(d).glob("*.jsonl")):
        if labels and not p.stem.startswith(labels):
            continue
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        chk = items = 0.0
        for i, r in enumerate(rows):
            if r["tag"] == "CHECK_IN":
                o = next((o for o in rows[i + 1:] if o["tag"] in ("CHECK_OUT", "CHECK_RAISED")), None)
                chk += (o["t"] - r["t"]) if o else 0
                items += int(r["data"]["n"])
        first = next((r["t"] for r in rows if r["tag"] == "FINDINGS"), None)
        done = next((r["t"] for r in rows if r["tag"] == "DONE"), None)
        el = next((r["data"] for r in rows if r["tag"] == "ELAPSED_S"), None)
        start = done - el if done and el else None
        print(f"{p.stem}: total {el} s, before write {round(first - start, 1) if first and start else '?'} s, "
              f"write {round(done - first, 1) if first and done else '?'} s, in the check {chk:.2f} s, items {int(items)}")
