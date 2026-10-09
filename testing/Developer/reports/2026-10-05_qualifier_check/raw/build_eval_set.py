"""Build the qualifier-check evaluation set from the two labelled sources.

Sources, both read-only:

- `<repo-root>/testing/Developer/reports/2026-10-05_sentence_check/raw/`:
  65 (sentence, quotes) pairs with a hand class (F, R, A). Each quote is
  widened here to its whole record sentence(s), as card 89 ships, with the
  design's own `widen_to_sentences`; an R pair whose extra words sit inside
  the widened sentence is relabelled faithful (F), the rest stay R.
- The card 89 worktree's `sentence_check_raw/` (branch) and
  `develop_control/`: every sentence the live check approved (140), with the
  quotes the judge read, labelled from the wave 3 report's item ids
  (A: addition; B: borderline) and this reader's own sub-label.

Output: eval_set.jsonl beside this script. No secrets are read.

Usage: python3 build_eval_set.py
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SC = ROOT / "testing/Developer/reports/2026-10-05_sentence_check/raw"
W3 = ROOT / ".claude/worktrees/sentence-check/testing/Developer/reports/2026-10-05_wave3/sentence_check_raw"


def norm(text: str) -> str:
    return " ".join(re.sub(r"[()\[\]{}]", " ", text.lower()).split())


def record_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", text) if s.strip()]


def widen_to_sentences(quote: str, record: str) -> str:
    sents = record_sentences(record)
    q = norm(quote)
    for width in range(1, len(sents) + 1):
        for start in range(len(sents) - width + 1):
            span = " ".join(sents[start:start + width])
            if q in norm(span):
                return " ".join(sents[start:start + width])
    return quote


# ---- Source 1: the 65 design pairs ---------------------------------------
# An R pair is faithful to the widened sentence when the classification note
# says the extra words are in the same record sentence as the quote. Listed
# by id after reading each note and the widened quote (see design.md).
R_WITHIN_SENTENCE = {
    "med1-c2-i2", "med2-c1-i4", "med2-c2-i4",
    "gerd1-c1-i1", "gerd1-c1-i4", "gerd1-c1-i5", "gerd1-c1-i6",
    "gerd2-c1-i5", "gerd2-c1-i6", "gerd3-c1-i1", "gerd3-c1-i4", "gerd3-c1-i5",
    "gerd3-c1-i6", "gerd3-c2-i6",
}
# Sub-labels for the design's A and borderline items, this reader's.
DESIGN_SUBLABELS = {
    "med1-c1-i5": ("A", "reframed", "'studied in the context of screening' reframes 'understanding prevalence will improve screening'"),
    "med1-c2-i3": ("A", "other_record", "'autosomal recessive' from a different paper"),
    "med3-c1-i6": ("A", "added_explanation", "what hemoglobin does is not in the record"),
    "gerd1-c1-i2": ("A", "added_population", "'in adults' is nowhere in the record"),
    "gerd1-c2-i3": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gerd3-c2-i4": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gerd2-c1-i2": ("B", "stronger_degree", "'hallmark' for 'typical'; faithful enough, kept as F in the design"),
    "gerd3-c1-i2": ("B", "stronger_degree", "'hallmark' for 'typical'; faithful enough, kept as F in the design"),
    # this reader's additions after reading every pair against its widened quote
    "med1-c2-i4": ("B", "added_gloss", "'consortium study' for 'in this study ... from 35 universities and institutions'"),
    "gerd1-c2-i4": ("B", "narrowed", "'In children' is the record's population, not in the widened quote; a narrowing, not a widening"),
}

# ---- Source 2: the wave 3 approved sentences -------------------------------
# From the wave 3 report: the six branch additions, the four develop
# additions, and the twenty borderline items, each with this reader's label.
# Label: A (addition the check must reject), B (borderline: my own call in
# the third field, "reject" or "keep"), F otherwise.
W3_LABELS = {
    # branch additions
    "gp1-c1-i6": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gp2-c2-i5": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gp3-c2-i3": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gp5-c1-i4": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "gp1-c2-i6": ("A", "dropped_hedge", "'potentially attributable to GERD' stated as GERD symptoms"),
    "gp4-c2-i6": ("A", "dropped_hedge", "'potentially attributable' dropped"),
    # develop additions
    "cp2-c1-i4": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "cp4-c2-i6": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "cp5-c1-i3": ("A", "dropped_qualifier", "'children' for 'young children'"),
    "cp1-c2-i4": ("A", "dropped_hedge", "'These symptoms' states as GERD's what the paper calls potentially attributable"),
    # branch borderline
    "gp2-c2-i4": ("B", "relabelled", "'risk factors and underlying causes' for 'play a role in the pathogenesis'"),
    "gp3-c2-i4": ("B", "relabelled", "same"),
    "gp2-c1-i5": ("B", "stronger_degree", "'carries risks' for 'is associated with'"),
    "gp5-c1-i6": ("B", "stronger_degree", "same"),
    "gr3-c1-i3": ("B", "stronger_degree", "'hallmark' for 'typical'"),
    "gr5-c1-i3": ("B", "stronger_degree", "'hallmark' for 'typical'"),
    "gp1-c1-i4": ("B", "added_gloss", "'(the valve between the esophagus and stomach)' for the lower esophageal sphincter"),
    "md4-c1-i4": ("B", "weaker_degree", "'common' for 'the most common'"),
    "md3-c2-i2": ("B", "reframed", "'another group of studies' for one paper"),
    # develop borderline
    "cr1-c1-i3": ("B", "stronger_degree", "'hallmark' for 'typical'"),
    "cr3-c1-i3": ("B", "stronger_degree", "'hallmark' for 'typical'"),
    "cr4-c2-i7": ("B", "stronger_degree", "'fundamentally a clinical diagnosis'"),
    "cr5-c2-i4": ("B", "narrowed", "'pediatric GERD pathogenesis' for a general statement in a paediatric review"),
    "cp1-c2-i5": ("B", "stronger_degree", "'carries risks' for 'associated with'"),
    "cp2-c1-i3": ("B", "relabelled", "'risk factors include' for pathogenesis factors"),
    "cp3-c2-i5": ("B", "relabelled", "same"),
    "cp5-c2-i3": ("B", "relabelled", "same"),
    "cp4-c1-i4": ("B", "added_gloss", "'the muscular valve' as a gloss"),
    # the wave 3 report had these two as borderline; by this brief's definition
    # (a restricting word or hedge the sentence leaves out: frequency,
    # condition) both are dropped qualifiers, so this reader labels them A
    "cm5-c1-i8": ("A", "dropped_condition", "'spread across 10 different forms' drops 'seen in greater than 1% of patients'; wave 3 had it borderline"),
    "cm5-c2-i3": ("A", "loosened_frequency", "'occasionally' for 'in rare instances'; wave 3 had it borderline"),
    # this reader's addition after reading every approved sentence
    "md4-c1-i2": ("B", "weaker_degree", "'commonly affects' for 'most commonly affects'"),
}

# This reader's call on every borderline sub-label: what the check should do
# with it. "keep" means a rejection counts as a wrong rejection in the
# scores; "reject" means an approval is reported beside the additions;
# "either" is not scored.
MY_CALL = {
    "stronger_degree": "either",   # 'hallmark' or 'classic' for 'typical' reads as a synonym; 'carries risks' and 'fundamentally' lean reject
    "relabelled": "keep",          # the question asked for risk factors; the record's pathogenesis factors answer it
    "added_gloss": "reject",       # an explanation the record never gives, the same class as the design's hemoglobin addition
    "weaker_degree": "reject",     # a degree the quote does not give, named in today's criteria
    "reframed": "reject",
    "narrowed": "either",          # not a widening; the quote rule still rejects it
}


def approved(a: dict) -> bool:
    p = a.get("probabilities", {})
    return a.get("choice") == "no" and (p.get("no") or 0) > (p.get("yes") or 0)


def find_record(quote: str, findings: list[dict]) -> dict | None:
    q = norm(quote)
    for f in findings:
        if q and q in norm(f["text"]):
            return f
    return None


def main() -> None:
    items: list[dict] = []
    classes = {k: v for k, v in json.loads((SC / "classification.json").read_text()).items() if not k.startswith("_")}
    for line in (SC / "pairs.jsonl").read_text().splitlines():
        p = json.loads(line)
        cls = classes[p["id"]]["class"]
        note = classes[p["id"]]["note"]
        widened = []
        for q, r in zip(p["quotes"], p["records"]):
            w = widen_to_sentences(q, r["text"]) if r.get("text") else q
            if w not in widened:
                widened.append(w)
        label, sub, mynote = cls, "", note
        if p["id"] in DESIGN_SUBLABELS:
            label, sub, mynote = DESIGN_SUBLABELS[p["id"]]
        elif cls == "R":
            if p["id"] in R_WITHIN_SENTENCE:
                label, sub, mynote = "F", "within_widened_sentence", note
            else:
                label, sub = "R", "beyond_widened_sentence"
        elif cls == "F":
            sub = "faithful"
        items.append({
            "id": "d-" + p["id"], "source": "design_65", "sentence": p["sentence"],
            "quotes": widened, "writer_quotes": p["quotes"],
            "records": [{"url": r["url"], "text": r["text"]} for r in p["records"]],
            "label": label, "sublabel": sub, "note": mynote,
            "live_p_no": p["live_p_no"], "live_approved": p["live_approved"],
        })

    paths = sorted(glob.glob(str(W3 / "*.jsonl"))) + sorted(glob.glob(str(W3 / "develop_control/*.jsonl")))
    for path in paths:
        label_run = os.path.basename(path)[:-6]
        with open(path) as handle:
            rows = [json.loads(line) for line in handle]
        findings = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
        checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
        jevs = [r["data"] for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
        for k, c in enumerate(checks):
            ans = jevs[k].get("answers", {}) if k < len(jevs) else {}
            for i, it in enumerate(c["items"], 1):
                a = ans.get(f"item_{i}", {})
                if not approved(a):
                    continue
                pid = f"{label_run}-c{k + 1}-i{i}"
                label, sub, note = W3_LABELS.get(pid, ("F", "faithful", ""))
                recs = []
                for q in it["quotes"]:
                    f = find_record(q, findings)
                    recs.append({"url": f["url"] if f else None, "text": f["text"] if f else None})
                items.append({
                    "id": "w-" + pid, "source": "wave3_branch" if not label_run.startswith("c") else "wave3_develop",
                    "sentence": it["sentence"], "quotes": list(it["quotes"]),
                    "writer_quotes": list(it.get("writer_quotes", [])), "records": recs,
                    "label": label, "sublabel": sub, "note": note,
                    "live_p_no": a["probabilities"].get("no"), "live_approved": True,
                })
    with open(HERE / "eval_set.jsonl", "w") as out:
        for it in items:
            it["my_call"] = MY_CALL.get(it["sublabel"], "") if it["label"] == "B" else ""
            out.write(json.dumps(it, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(items), "items;", Counter((it["label"], it["sublabel"]) for it in items))
    missing = [k for k in W3_LABELS if not any(it["id"] == "w-" + k for it in items)]
    print("labelled ids not found among approvals:", missing)


if __name__ == "__main__":
    main()
