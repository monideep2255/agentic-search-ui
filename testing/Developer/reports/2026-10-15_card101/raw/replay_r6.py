"""Card 101 last slices: the recorded drafts on develop and on each slice.

Usage: python -I replay_r6.py <out.txt> <name=src>... -- <trace-folder>...

The first tree named is the baseline (develop). The same draft selection as
round 5's `replay_r5.py`: every GROUNDING narrative beside a FINDINGS row,
deduplicated by trace and narrative, no model call, no writer quotes. Per tree
and draft, the sentences shown when the check approves nothing and when it
approves every item `sentence_check._read_whole` would send. Compared with
the baseline under the same approval, text with citation markers removed.
"""

import importlib
import json
import re
import sys
from pathlib import Path

split = sys.argv.index("--")
OUT = sys.argv[1]
TREES = [arg.split("=", 1) for arg in sys.argv[2:split]]
FOLDERS = sys.argv[split + 1 :]


def load(src):
    for name in [key for key in sys.modules if key.startswith("system_03")]:
        del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    fi = importlib.import_module("system_03_search_agent.synthesis.findings")
    sc = importlib.import_module("system_03_search_agent.synthesis.sentence_check")
    sys.path.pop(0)
    return gr, fi, sc


drafts = []
seen = set()
for folder in FOLDERS:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = []
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and "tag" in row:
                rows.append(row)
        data = next((row["data"] for row in rows if row.get("tag") == "FINDINGS"), [])
        if not data:
            continue
        for row in rows:
            if row["tag"] != "GROUNDING":
                continue
            narrative = row["data"].get("narrative") or ""
            if not narrative or narrative.lower().startswith(("pubmed title", "found ", "i found")):
                continue
            if (path.stem, narrative) in seen:
                continue
            seen.add((path.stem, narrative))
            label = f"{folder.rstrip('/').split('/')[-1]}/{path.stem}/{len(drafts) + 1}"
            drafts.append((label, narrative, data))


def findings(fi, data):
    return [
        fi.SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                        field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
        for f in data
    ]


def plain(sentence):
    text = " ".join(re.sub(r"\[\d+\]", "", sentence).split())
    return re.sub(r"\s+([.,;:])", r"\1", text)


def shown(result):
    return list(result.sentences) if result.narrative else []


def outcomes(src):
    gr, fi, sc = load(src)
    out, items, not_sent = [], 0, 0
    for _label, narrative, data in drafts:
        fs = findings(fi, data)
        sink = []
        none = shown(gr.run_grounding_pass(narrative, fs, False, "", (), None, sink))
        sent = [c for c in sink if sc._read_whole(c)]
        items += len(sink)
        not_sent += len(sink) - len(sent)
        every = shown(gr.run_grounding_pass(narrative, fs, False, "", (), frozenset(c.key for c in sent), []))
        out.append({"none": [plain(s) for s in none], "all": [plain(s) for s in every]})
    return out, items, not_sent


results = {name: outcomes(src) for name, src in TREES}
base_name = TREES[0][0]
base = results[base_name][0]
lines = [f"{len(drafts)} distinct recorded writer drafts, no model call, no writer quotes (replay_r6.py).", ""]
for name, (tree, items, not_sent) in results.items():
    lines.append(f"{name}: items {items}, not sent for length {not_sent}; "
                 f"shown none {sum(len(d['none']) for d in tree)}, all {sum(len(d['all']) for d in tree)}")
lines.append("")
for name, (tree, _items, _ns) in list(results.items())[1:]:
    for mode in ("none", "all"):
        new = dropped = emptied = 0
        texts = []
        for index, draft in enumerate(tree):
            before = base[index][mode]
            after = draft[mode]
            new += sum(1 for s in after if s not in before)
            lost = [s for s in before if s not in after]
            dropped += len(lost)
            emptied += bool(before) and not after
            texts.extend(f"    {drafts[index][0]}: {s}" for s in lost)
        lines.append(f"{name} vs {base_name}, approves {mode}: shown that {base_name} does not show {new}; "
                     f"{base_name} sentences dropped {dropped}; drafts emptied {emptied}")
        lines.extend(texts)
Path(OUT).write_text("\n".join(lines) + "\n")
print("\n".join(lines))
