"""Card 101 round 3 adversary: replay recorded first drafts through develop's
and this branch's grounding pass, offline, no model call.

Usage: python replay_traces.py <src-dir> <trace-folder>... ; prints counts.
Writer quotes are not recorded beside the narrative, so keyed markers carry no
quote (both trees alike): reworded sentences are stripped on both, copied
clauses behave exactly as live. Only the difference between trees is read.

Per draft: shown with no check (no approvals), shown when the check approves
every item; and, for every clause the branch counts as a whole record
sentence, which relaxation it depended on (colon start, semicolon, question
mark, a start with no capital after the stop, stripped quote marks).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

BRANCH = hasattr(gr, "is_whole_record_sentence")


def findings_of(rows):
    data = next((r["data"] for r in rows if r.get("tag") == "FINDINGS"), [])
    return [SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                         field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
            for f in data]


def question_of(rows):
    return ""


def shown(res):
    return [s for s in gr._split_sentences(res.narrative)] if res.narrative else []


VARIANTS = {}
if BRANCH:
    base = (gr._WHOLE_SENTENCE_START, gr._WHOLE_SENTENCE_ENDS, gr._OPENING_MARKS, gr._CLOSING_MARKS)
    VARIANTS = {
        "colon": (re.compile(r"[.;!?]\s+"), base[1], base[2], base[3]),
        "semicolon": (re.compile(r"[.!?:]\s+"), (".", "?", "!"), base[2], base[3]),
        "question": (re.compile(r"[.;!:]\s+"), (".", ";", "!"), base[2], base[3]),
        "no_capital": (re.compile(r"[.;!?:]\s+(?=[A-Z\"'“‘(\[])"), base[1], base[2], base[3]),
        "marks": (base[0], base[1], "", ""),
    }


def why_whole(claim, finding):
    reasons = []
    for name, (st, en, op, cl) in VARIANTS.items():
        saved = (gr._WHOLE_SENTENCE_START, gr._WHOLE_SENTENCE_ENDS, gr._OPENING_MARKS, gr._CLOSING_MARKS)
        gr._WHOLE_SENTENCE_START, gr._WHOLE_SENTENCE_ENDS, gr._OPENING_MARKS, gr._CLOSING_MARKS = st, en, op, cl
        try:
            if not gr.is_whole_record_sentence(claim, finding):
                reasons.append(name)
        finally:
            gr._WHOLE_SENTENCE_START, gr._WHOLE_SENTENCE_ENDS, gr._OPENING_MARKS, gr._CLOSING_MARKS = saved
    return reasons


PRONOUN = re.compile(r"^\s*(it|its|they|their|this|these|those|such)\b", re.IGNORECASE)
tot = dict(drafts=0, dev_shown=0, br_none=0, br_all=0, items=0, drafts_lost_all_none=0, drafts_lost_all_all=0,  # noqa: C408
           whole_clauses=0, pronoun_switch=0)
reasons_count = {}
examples = []
SEEN = set()
for folder in sys.argv[2:]:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = []
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001, S112
                continue
            if isinstance(r, dict) and "tag" in r:
                rows.append(r)
        fs = findings_of(rows)
        if not fs:
            continue
        by_ref = {f.ref_index: f for f in fs}
        for r in rows:
            if r["tag"] != "GROUNDING":
                continue
            narrative = r["data"].get("narrative") or ""
            if not narrative or narrative.lower().startswith(("pubmed title", "found ", "i found")):
                continue
            if (path.stem, narrative) in SEEN:
                continue
            SEEN.add((path.stem, narrative))
            tot["drafts"] += 1
            sink = []
            res = gr.run_grounding_pass(narrative, fs, False, "", (), None, sink)
            n_none = len(shown(res))
            if BRANCH:
                res_all = gr.run_grounding_pass(narrative, fs, False, "", (), frozenset(c.key for c in sink), [])
                n_all = len(shown(res_all))
            else:
                n_all = n_none
            tot["br_none"] += n_none
            tot["br_all"] += n_all
            tot["items"] += len(sink)
            tot["dev_shown"] += n_none
            print("DRAFT", folder.rstrip("/").split("/")[-1], path.stem, tot["drafts"], n_none, n_all, len(sink))
            if BRANCH:
                prev_refs = set()
                for sent in shown(res):
                    refs = {int(m) for m in re.findall(r"\[(\d{1,3})\]", sent)}
                    for claim in res.claims:
                        pass
                    prev_refs = refs
                # whole clause reasons, over the draft as written
                prev_sentence_refs = set()
                for sent in gr._split_sentences(narrative):
                    segs = gr._segments(sent)
                    sent_refs = set()
                    for text, marker, _ in segs:
                        if marker is None or marker not in by_ref:
                            continue
                        sent_refs.add(marker)
                        claim = gr._clean_claim(text)
                        f = by_ref[marker]
                        if not gr._asserts_something(claim) or not gr.ground_claim(claim, f.field_value):
                            continue
                        if gr._wraps_record_value(claim, f) or not gr.is_whole_record_sentence(claim, f):
                            continue
                        tot["whole_clauses"] += 1
                        rs = why_whole(claim, f)
                        for x in rs:
                            reasons_count[x] = reasons_count.get(x, 0) + 1
                            examples.append((x, path.stem, claim[:140]))
                        if PRONOUN.match(claim) and prev_sentence_refs and marker not in prev_sentence_refs:
                            tot["pronoun_switch"] += 1
                            examples.append(("pronoun_switch", path.stem, claim[:140]))
                    if sent_refs:
                        prev_sentence_refs = sent_refs
print(json.dumps({"branch": BRANCH, **tot, "whole_by_relaxation": reasons_count}))
for e in examples:
    print("  ", e)
