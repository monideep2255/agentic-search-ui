"""Whether the moved sentences push any sentence past card 99's pair-call cap.

For every recorded check whose first pass kept code-approved sentences, the
recorded candidates plus the moved sentences (each with its best-matching
whole record sentence as its quote, as the diagnosis's measurement did) go
through the shipped `build_pair_calls`, moved sentences first (worst case)
and last. Counts the sentences left unasked. No model call.
"""
import ast
import json
import os
import sys
from pathlib import Path

SP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SP / "diag101"))
sys.path.insert(0, os.path.join(os.environ["REPO_ROOT"], "src"))
import scan_new_rule as snr  # reuse `moves`
import scan_unchecked as su

from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.grounding import SynthesisCandidate
from system_03_search_agent.synthesis.sentence_check import build_pair_calls


def best_sentence(s, findings):
    said = gr._stemmed(gr.content_tokens(s))
    best, score = s, -1
    for f in findings:
        for rs in su.BOUNDARY.split(f["text"] or ""):
            sc = len(said & gr._stemmed(gr.content_tokens(rs)))
            if sc > score:
                best, score = rs.strip(), sc
    return best

def cand(s, q):
    return SynthesisCandidate(key=(s, (q,)), sentence=s, quotes=(q,))

checks = before = after_first = after_last = moved_total = 0
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
            mv = [cand(s, best_sentence(s, findings)) for s in moved]
            checks += 1; moved_total += len(mv)
            before += len(build_pair_calls(rec)[1])
            after_first += len(build_pair_calls(mv + rec)[1])
            after_last += len(build_pair_calls(rec + mv)[1])
            print(path.parent.name, path.stem, "items", len(rec), "+ moved", len(mv),
                  "unasked before", len(build_pair_calls(rec)[1]),
                  "moved first", len(build_pair_calls(mv + rec)[1]), "moved last", len(build_pair_calls(rec + mv)[1]),
                  "pair calls", len(build_pair_calls(rec + mv)[0]))
print(f"checks {checks}, moved sentences {moved_total}, sentences unasked: before {before}, moved first {after_first}, moved last {after_last}")
