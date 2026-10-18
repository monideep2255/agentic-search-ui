"""Card 101 build round 2: the diagnosis's scan with the new rule. No model call.

Per answer (trace), from the recorded first grounding passes and the screen:
- moved_shown: shown claim sentences that code alone approved (code-synth);
  under the new rule each goes to the sentence check instead.
- moved_first_pass: code-approved sentences kept by any first pass of
  `_ground_with_sentence_check` (first draft and repair), shown or not; these
  are what the new rule adds to the check's items.
- new_calls: first passes that had 0 candidates but >= 1 code-approved
  sentence, so the new rule adds one check call where there was none.
- joined: first passes that already had a call; the moved sentences join it.
"""
from __future__ import annotations

import ast
import json
import re
import statistics
import sys
from pathlib import Path

SP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SP / "diag101"))
import scan_unchecked as su

NAME_LINE = re.compile(r"^(publication pmid|a clinical trial named|is identified by)", re.IGNORECASE)


def moves(s, cands, findings, q):
    """Code-approved reworded sentence: code-synth and not a name or identifier line."""
    return su.classify(s, cands, findings, q)[0] == "code-synth" and not NAME_LINE.match(s.strip())


rows_out = []
check_durations = []
for name, files in su.SOURCES:
    for path in files:
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        findings = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
        if not findings:
            continue
        q = su.QUESTIONS[path.stem[:2]]
        cands = {su.plain(it["sentence"]) for r in rows if r["tag"] == "CHECK_IN" for it in (r["data"]["items"] if isinstance(r["data"]["items"], list) else ast.literal_eval(r["data"]["items"]))}
        shown = [r["data"][len("claim: "):] for r in rows if r["tag"] == "TOKEN"
                 and r["data"].startswith("claim: ") and not su.SUMMARY.match(r["data"][len("claim: "):])]
        moved_shown = sum(1 for s in shown if moves(s, cands, findings, q))
        # first passes, and the check timing that follows each
        moved_fp = new_calls = joined = 0
        for i, r in enumerate(rows):
            if r["tag"] != "GROUNDING":
                continue
            d = r["data"]
            cc = d.get("candidates_collected")
            if cc in (None, "None"):
                continue
            kept = d.get("kept_sentences")
            kept = ast.literal_eval(kept) if isinstance(kept, str) else kept
            m = sum(1 for s in kept if moves(s, set(), findings, q))
            moved_fp += m
            if m and int(cc) == 0:
                new_calls += 1
            elif m:
                joined += 1
        for i, r in enumerate(rows):
            if r["tag"] == "CHECK_IN":
                out = next((o for o in rows[i + 1:] if o["tag"] in ("CHECK_OUT", "CHECK_RAISED")), None)
                if out:
                    check_durations.append(out["t"] - r["t"])
        n_checks = sum(1 for r in rows if r["tag"] == "CHECK_IN")
        el = next((r["data"] for r in rows if r["tag"] == "ELAPSED_S"), None)
        rows_out.append((name, path.stem, len(shown), moved_shown, moved_fp, n_checks, new_calls, joined, el))

print("source | answer | shown | moved (shown) | moved (all first passes) | check calls recorded | new calls | joined calls | answer s")
for r in rows_out:
    print(" | ".join(str(x) for x in r))
print("\nTotals by source")
for name, _ in su.SOURCES:
    rs = [r for r in rows_out if r[0] == name]
    print(name, "answers", len(rs), "shown", sum(r[2] for r in rs), "moved shown", sum(r[3] for r in rs),
          "moved fp", sum(r[4] for r in rs), "answers with moved", sum(1 for r in rs if r[3] or r[4]),
          "new calls", sum(r[6] for r in rs), "joined", sum(r[7] for r in rs))
print("all: answers", len(rows_out), "shown", sum(r[2] for r in rows_out), "moved shown", sum(r[3] for r in rows_out),
      "moved fp", sum(r[4] for r in rows_out), "answers with moved shown", sum(1 for r in rows_out if r[3]),
      "new calls", sum(r[6] for r in rows_out), "joined", sum(r[7] for r in rows_out))
print("check call duration s: n", len(check_durations), "median", round(statistics.median(check_durations), 3),
      "p90", round(sorted(check_durations)[int(0.9 * len(check_durations)) - 1], 3), "max", round(max(check_durations), 3))
