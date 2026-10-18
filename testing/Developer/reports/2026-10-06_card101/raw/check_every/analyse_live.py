"""Card 101 round 2: per answer, from the round 2 traces. No model call.

shown: claim sentences on screen, the code-built "I found N" line excluded.
reworded shown: shown sentences that were check candidates (approved by the check).
code-approvable: candidates code's old word check would have approved alone.
held back, code would have shown: code-approvable candidates the check did not approve.
moved and approved: code-approvable candidates the check approved.
"""
import json
import os
import re
import sys
from pathlib import Path

LIVE = Path(os.environ.get("LIVE_DIR", Path(__file__).resolve().parent / "live"))
SUMMARY = re.compile(r"^(I found|Found) \d")
MARK = re.compile(r"\s*\[[0-9#,\s]+\]")
sys.path.insert(0, os.path.join(os.environ["REPO_ROOT"], "src"))
from system_03_search_agent.synthesis.grounding import normalize


def norm(s):
    return normalize(MARK.sub("", s).strip().rstrip("."))

detail = "--detail" in sys.argv
rows = []
for path in sorted(LIVE.glob("*.jsonl"), key=lambda p: (p.stem[:2], int(p.stem[2:]))):
    recs = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    shown = [r["data"][7:] for r in recs if r["tag"] == "TOKEN" and r["data"].startswith("claim: ")
             and not SUMMARY.match(r["data"][7:])]
    code = {}
    for r in recs:
        if r["tag"] == "CODE_VERDICTS":
            for x in r["data"]:
                code[normalize(x["sentence"])] = code.get(normalize(x["sentence"]), False) or x["code_word_check_would_approve"]
    approved = set()
    cands = {}
    for r in recs:
        if r["tag"] == "CHECK_OUT":
            approved |= {normalize(s) for s in r["data"]["approved_sentences"]}
        if r["tag"] == "CHECK_IN":
            for it in r["data"]["items"]:
                cands[normalize(it["sentence"])] = it
    raised = [r["data"] for r in recs if r["tag"] in ("CHECK_RAISED", "JEV_RAISED")]
    shown_n = [norm(s) for s in shown]
    reworded = [s for s in shown_n if s in cands]
    codeok = {s for s, ok in code.items() if ok}
    held = codeok - approved
    moved_ok = codeok & approved
    moved_shown = [s for s in shown_n if s in moved_ok]
    done = next((r["data"] for r in recs if r["tag"] in ("DONE", "ERROR")), {})
    el = next((r["data"] for r in recs if r["tag"] == "ELAPSED_S"), None)
    rows.append({"answer": path.stem, "shown": len(shown), "reworded": len(reworded), "cands": len(cands),
                 "codeok": len(codeok), "held": len(held), "moved_ok": len(moved_ok),
                 "moved_shown": len(moved_shown), "checks": sum(1 for r in recs if r["tag"] == "CHECK_IN"),
                 "raised": len(raised), "secs": el, "cost": float(done.get("total_cost_usd") or 0),
                 "outcome": done.get("trust_outcome")})
    if detail:
        print(f"\n== {path.stem}  {el} s")
        for s in shown:
            k = norm(s)
            tag = "REWORDED" if k in cands else "copied"
            if k in moved_ok: tag += ", code-approvable"
            print(f"  [{tag}] {s.strip()}")
            if k in cands:
                for q in cands[k]["quotes"]:
                    print(f"      quote: {q}")
        for s in sorted(held):
            print(f"  HELD BACK, code would have shown: {s}")
            it = cands.get(s)
            if it:
                for q in it["quotes"]:
                    print(f"      quote: {q}")
        if raised:
            print("  RAISED:", raised)

keys = ["answer", "shown", "reworded", "cands", "codeok", "held", "moved_ok", "moved_shown", "checks", "raised", "secs", "cost", "outcome"]
print("\n" + " | ".join(keys))
for r in rows:
    print(" | ".join(str(round(r[k], 4) if isinstance(r[k], float) else r[k]) for k in keys))
for p in ("ge", "me", "br"):
    rs = [r for r in rows if r["answer"].startswith(p)]
    if not rs: continue
    n = len(rs)
    print(f"{p}: answers {n}, shown {sum(r['shown'] for r in rs)} (mean {sum(r['shown'] for r in rs)/n:.2f}), "
          f"held back code-approvable {sum(r['held'] for r in rs)}, moved and approved {sum(r['moved_ok'] for r in rs)}, "
          f"of them shown {sum(r['moved_shown'] for r in rs)}, mean s {sum(r['secs'] or 0 for r in rs)/n:.1f}, "
          f"max s {max(r['secs'] or 0 for r in rs)}, answers with 0 shown {sum(1 for r in rs if r['shown']==0)}")
print(f"total spend ${sum(r['cost'] for r in rows):.4f} over {len(rows)} answers")
