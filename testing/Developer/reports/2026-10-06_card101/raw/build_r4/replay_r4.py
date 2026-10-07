"""Card 101 round 4: the adversary's replay (replay_traces.py), adapted.

Usage: python -I replay_r4.py <src-dir> <out.jsonl> <trace-folder>...

Per draft, the sentences shown with the check approving nothing and with it
approving every item, and the items collected. For every copied clause the
tree counts as a whole record sentence (writer path, no listing flag), one
line in <out.jsonl>, so two trees' whole sets can be compared.
Same draft selection and finding reconstruction as replay_traces.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

BRANCH = hasattr(gr, "is_whole_record_sentence")
ROUND4 = hasattr(gr, "_is_code_built_row")


def findings_of(rows):
    data = next((r["data"] for r in rows if r.get("tag") == "FINDINGS"), [])
    return [
        SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                     field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
        for f in data
    ]


def shown(res):
    return list(gr._split_sentences(res.narrative)) if res.narrative else []


tot = {"drafts": 0, "none": 0, "all": 0, "items": 0, "whole": 0}
per_draft = []
SEEN = set()
out = Path(sys.argv[2]).open("w")  # noqa: SIM115
for folder in sys.argv[3:]:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = []
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                r = None
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
            draft_id = f"{folder.rstrip('/').split('/')[-1]}/{path.stem}/{tot['drafts']}"
            sink = []
            res = gr.run_grounding_pass(narrative, fs, False, "", (), None, sink)
            s_none = shown(res)
            if BRANCH:
                res_all = gr.run_grounding_pass(narrative, fs, False, "", (), frozenset(c.key for c in sink), [])
                s_all = shown(res_all)
            else:
                s_all = s_none
            tot["none"] += len(s_none)
            tot["all"] += len(s_all)
            tot["items"] += len(sink)
            per_draft.append((draft_id, len(s_none), len(s_all), len(sink), s_none, s_all))
            if not BRANCH:
                continue
            for sentence_index, sent in enumerate(gr._split_sentences(narrative)):
                for seg_index, (text, marker, _) in enumerate(gr._segments(sent)):
                    if marker is None or marker not in by_ref:
                        continue
                    claim = gr._clean_claim(text)
                    f = by_ref[marker]
                    if not gr._asserts_something(claim) or not gr.ground_claim(claim, f.field_value):
                        continue
                    if gr._wraps_record_value(claim, f):
                        continue
                    whole = gr.is_whole_record_sentence(text if ROUND4 else claim, f)
                    if whole:
                        tot["whole"] += 1
                    out.write(json.dumps({"draft": draft_id, "s": sentence_index, "g": seg_index,
                                          "claim": claim, "whole": whole}) + "\n")
out.close()
print(json.dumps({"branch": BRANCH, "round4": ROUND4, **tot}))
Path(sys.argv[2] + ".drafts.json").write_text(json.dumps(per_draft))
