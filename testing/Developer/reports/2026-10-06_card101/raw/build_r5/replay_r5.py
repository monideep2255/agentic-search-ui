"""Card 101 round 5: the recorded drafts under no, all and partial approvals.

Usage: python -I replay_r5.py <develop-src> <round4-src> <round5-src> <out.txt> <trace-folder>...

The same 168 distinct recorded first drafts, findings and draft selection as
`raw/build_r4/replay_r4.py` (itself the adversary's `replay_traces.py`).
Writer quotes are not recorded beside the drafts, so reworded sentences are
stripped alike on every tree; copied clauses behave as live. No model call.

Per tree and draft, the sentences shown when the check approves:

- none: nothing;
- all: every item it is sent (on round 5, only items `sentence_check.
  _read_whole` lets through, as `check_reworded_sentences` sends);
- partial: random subsets of the items sent, every subset for 8 items or
  fewer, else 200 random ones (seed 7), the judge's `partial2.py` scheme.

Compared with develop, text with citation markers removed: sentences shown
that develop does not show, drafts where develop shows prose and the tree
shows none, and sentences develop shows that the tree drops. Writes counts
and up to 12 quoted dropped sentences to <out.txt>; prints the summary.
"""

import importlib
import itertools
import json
import random
import re
import sys
from pathlib import Path

DEV_SRC, R4_SRC, R5_SRC, OUT = sys.argv[1:5]
FOLDERS = sys.argv[5:]


def load(src):
    for name in [key for key in sys.modules if key.startswith("system_03")]:
        del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    fi = importlib.import_module("system_03_search_agent.synthesis.findings")
    try:
        sc = importlib.import_module("system_03_search_agent.synthesis.sentence_check")
    except Exception:  # noqa: BLE001 - develop's tree may not import it alone
        sc = None
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


def shown(gr, result):
    return [plain(s) for s in gr._split_sentences(result.narrative)] if result.narrative else []


def tree_outcomes(src, filter_read_whole):
    gr, fi, sc = load(src)
    random.seed(7)
    out = {}
    stats = {"items": 0, "not_sent": 0, "drafts_with_items": 0}
    for index, (_label, narrative, data) in enumerate(drafts):
        fs = findings(fi, data)
        sink = []
        res = gr.run_grounding_pass(narrative, fs, False, "", (), None, sink)
        none = shown(gr, res)
        stats["items"] += len(sink)
        stats["drafts_with_items"] += bool(sink)
        sent = [c for c in sink if not filter_read_whole or sc._read_whole(c)]
        stats["not_sent"] += len(sink) - len(sent)
        keys = [c.key for c in sent]
        if not hasattr(gr, "is_whole_record_sentence") or not sink:
            out[index] = {"none": none, "all": none, "partial": [none]}
            continue
        every = shown(gr, gr.run_grounding_pass(narrative, fs, False, "", (), frozenset(keys), []))
        if len(keys) <= 8:
            subsets = [sub for r in range(len(keys) + 1) for sub in itertools.combinations(keys, r)]
        else:
            subsets = [tuple(k for k in keys if random.random() < 0.5) for _ in range(200)]
        partial = [
            shown(gr, gr.run_grounding_pass(narrative, fs, False, "", (), frozenset(sub), []))
            for sub in subsets
        ]
        out[index] = {"none": none, "all": every, "partial": partial}
    return out, stats


dev, _ = tree_outcomes(DEV_SRC, False)
r4, r4_stats = tree_outcomes(R4_SRC, False)
r5, r5_stats = tree_outcomes(R5_SRC, True)

lines = [f"{len(drafts)} distinct recorded writer drafts, no model call (replay_r5.py).", ""]
summary = {"drafts": len(drafts)}
examples = []
for tree_name, tree in (("round 4", r4), ("round 5", r5)):
    for mode in ("none", "all", "partial"):
        new_shown = emptied = dropped = runs = 0
        dropped_texts = set()
        for index in range(len(drafts)):
            develop = dev[index]["none"]
            outcomes = tree[index][mode] if mode == "partial" else [tree[index][mode]]
            for sentences in outcomes:
                runs += 1
                new_shown += sum(1 for s in sentences if s not in develop)
                emptied += bool(develop) and not sentences
                lost = [s for s in develop if s not in sentences]
                dropped += len(lost)
                dropped_texts.update((drafts[index][0], s) for s in lost)
        lines.append(
            f"{tree_name}, approves {mode}: runs {runs}; shown that develop does not show {new_shown}; "
            f"drafts emptied {emptied}; develop sentences dropped {dropped} "
            f"({len(dropped_texts)} distinct)"
        )
        summary[f"{tree_name} {mode}"] = {"runs": runs, "new": new_shown, "emptied": emptied,
                                          "dropped": dropped, "distinct_dropped": len(dropped_texts)}
        if tree_name == "round 5":
            examples.append((mode, sorted(dropped_texts)))
lines.append("")
lines.append(f"develop sentences shown, check approving nothing: {sum(len(v['none']) for v in dev.values())}")
for name, tree in (("round 4", r4), ("round 5", r5)):
    lines.append(
        f"{name} sentences shown: none {sum(len(v['none']) for v in tree.values())}, "
        f"all {sum(len(v['all']) for v in tree.values())}"
    )
lines.append(f"round 4 items: {r4_stats['items']} in {r4_stats['drafts_with_items']} drafts")
lines.append(
    f"round 5 items: {r5_stats['items']} in {r5_stats['drafts_with_items']} drafts; "
    f"longer than the check reads, not sent: {r5_stats['not_sent']}"
)
lines.append("")
lines.append("Round 5 versus round 4, per draft where the shown sentences differ (none / all):")
for index, (label, _n, _d) in enumerate(drafts):
    if r4[index]["none"] != r5[index]["none"] or r4[index]["all"] != r5[index]["all"]:
        lines.append(
            f"  {label}: develop {len(dev[index]['none'])}; round 4 {len(r4[index]['none'])}/"
            f"{len(r4[index]['all'])}; round 5 {len(r5[index]['none'])}/{len(r5[index]['all'])}"
        )
lines.append("")
lines.append("Round 5: develop sentences dropped, distinct, per mode (first 12 each):")
for mode, texts in examples:
    lines.append(f"  approves {mode}:")
    for label, text in texts[:12]:
        lines.append(f"    {label}: {text}")
Path(OUT).write_text("\n".join(lines) + "\n")
print(json.dumps(summary))
