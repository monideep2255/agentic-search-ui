"""Card 101 round 2 adversary: how many extra concurrent Jev pair calls the
moved sentences add per recorded check. Any one failed call approves nothing
for the whole answer, so an extra call is extra exposure for the sentences
that were checked before. No model call. Reuses the builder's selection."""
import os
import sys
from pathlib import Path

SP = Path(os.environ["SCRATCH"])
os.environ["REPO_ROOT"] = os.environ["WORKTREE"]
sys.path.insert(0, str(SP / "card101b"))
sys.path.insert(0, str(SP / "diag101"))
import contextlib
import io

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    import pair_cap_pressure as pcp
import ast
import json

from system_03_search_agent.synthesis.grounding import SynthesisCandidate
from system_03_search_agent.synthesis.sentence_check import build_pair_calls

su, snr = pcp.su, pcp.snr
tot_before = tot_after = grew = 0
for _, files in su.SOURCES:
    for path in files:
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        findings = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
        if not findings:
            continue
        q = su.QUESTIONS[path.stem[:2]]
        for i, r in enumerate(rows):
            if r["tag"] != "GROUNDING" or r["data"].get("candidates_collected") in (None, "None"):
                continue
            kept = r["data"]["kept_sentences"]
            kept = ast.literal_eval(kept) if isinstance(kept, str) else kept
            moved = [su.MARK.sub("", s).strip().rstrip(".") for s in kept if snr.moves(s, set(), findings, q)]
            if not moved:
                continue
            nxt = next((o for o in rows[i + 1:] if o["tag"] in ("CHECK_IN", "GROUNDING")), None)
            if not nxt or nxt["tag"] != "CHECK_IN":
                continue
            items = nxt["data"]["items"]
            items = ast.literal_eval(items) if isinstance(items, str) else items
            rec = [SynthesisCandidate(key=(it["sentence"], tuple(it["quotes"])), sentence=it["sentence"], quotes=tuple(it["quotes"])) for it in items]
            mv = [pcp.cand(s, pcp.best_sentence(s, findings)) for s in moved]
            b = len(build_pair_calls(rec)[0]); a = len(build_pair_calls(rec + mv)[0])
            tot_before += 1 + b; tot_after += 1 + a; grew += a > b
            print(path.parent.name, path.stem, "Jev calls before", 1 + b, "after", 1 + a)
print(f"Jev calls per affected check: before {tot_before}, after {tot_after}; checks that gained a call: {grew}")
