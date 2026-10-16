"""Card 101: the reworded path, replayed with synthetic writer quotes.

Usage: python -I reworded_replay.py <out.txt> <name=src>... -- <trace-folder>...

The recorded drafts carry no writer quotes, so `replay_r6.py` never measures
the path where the sentence check reads a widened quote (A-101N-14). Two
families of synthetic narratives, no model call:

- drafts: each recorded draft with a quote added to every marker, the
  longest contiguous run of the clause's words found in the cited record
  (at least 15 characters), as `_quote_is_valid` finds it;
- units: for every sentence of every recorded record value, a reworded
  sentence ("<middle of the sentence> in the study") quoting that middle.

Per tree, the check items collected on the first pass. The first tree is the
baseline. For each baseline item the new tree's item with the same key is
looked up: its quotes must contain every baseline quote, else the item
"lost text"; with no such item it is "held", which is acceptable only when
the baseline's quote was the writer's bare quote (the old fallback) or
longer than 600. Also what is shown with the check approving nothing and
everything, as `replay_r6.py`.
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


rows = []  # (label, narrative, findings data)
seen = set()
values = {}
for folder in FOLDERS:
    for path in sorted(Path(folder).glob("*.jsonl")):
        parsed = []
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and "tag" in row:
                parsed.append(row)
        data = next((row["data"] for row in parsed if row.get("tag") == "FINDINGS"), [])
        if not data:
            continue
        for row in parsed:
            if row["tag"] != "GROUNDING":
                continue
            narrative = row["data"].get("narrative") or ""
            if not narrative or narrative.lower().startswith(("pubmed title", "found ", "i found")):
                continue
            if (path.stem, narrative) in seen:
                continue
            seen.add((path.stem, narrative))
            rows.append((f"draft/{len(rows) + 1}", narrative, data))
        for f in data:
            if f.get("text"):
                values[" ".join(f["text"].split())] = f

MARKER = re.compile(r"\[(\d+)\]")


def quoted(narrative, data):
    """`narrative` with a quote added to every marker whose clause has a run in the record."""
    by_ref = {int(f["ref"]): " ".join((f["text"] or "").split()) for f in data}
    out, last = [], 0
    for match in MARKER.finditer(narrative):
        clause = narrative[last : match.start()]
        record = by_ref.get(int(match.group(1)), "")
        words = clause.split()
        best = ""
        for i in range(len(words)):
            for j in range(len(words), i, -1):
                if j - i < 3:
                    break
                cand = " ".join(words[i:j]).strip(",;:.()")
                if len(cand) > len(best) and len(cand) >= 15 and '"' not in cand and cand in record:
                    best = cand
                    break
        out.append(narrative[last : match.start()])
        out.append(f'[{match.group(1)}: "{best}"]' if best else match.group(0))
        last = match.end()
    out.append(narrative[last:])
    return "".join(out)


def unit_rows():
    n = 0
    for value, f in sorted(values.items()):
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", value):
            words = part.split()
            if len(words) < 8:
                continue
            middle = " ".join(words[1:-1]).strip(",;:.()")
            if len(middle) < 15 or '"' in middle or middle not in value:
                continue
            n += 1
            narrative = f'{middle[0].upper()}{middle[1:]} in the study [{int(f["ref"])}: "{middle}"].'
            yield f"unit/{n}", narrative, [f]


def findings(fi, data):
    return [
        fi.SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                        field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
        for f in data
    ]


def plain(sentence):
    text = " ".join(re.sub(r"\[\d+\]", "", sentence).split())
    return re.sub(r"\s+([.,;:])", r"\1", text)


cases = [(label, quoted(n, d), d) for label, n, d in rows] + list(unit_rows())


def run(src):
    gr, fi, sc = load(src)
    result = {}
    for label, narrative, data in cases:
        fs = findings(fi, data)
        sink = []
        none = gr.run_grounding_pass(narrative, fs, False, "", None, None, sink)
        sent = [c for c in sink if sc._read_whole(c)]
        every = gr.run_grounding_pass(
            narrative, fs, False, "", None, frozenset(c.key for c in sent), []
        )
        result[label] = {
            "items": {c.sentence: (c.quotes, c.key[1]) for c in sink},  # a copied clause's key holds its runs
            "none": [plain(s) for s in none.sentences],
            "all": [plain(s) for s in every.sentences],
        }
    return result


results = {name: run(src) for name, src in TREES}
base_name = TREES[0][0]
base = results[base_name]
n_drafts = sum(1 for c in cases if c[0].startswith("draft"))
n_units = sum(1 for c in cases if c[0].startswith("unit"))
lines = [f"{len(cases)} cases ({n_drafts} quoted drafts, {n_units} reworded units), no model call (reworded_replay.py).", ""]
for name, res in results.items():
    lines.append(f"{name}: items {sum(len(v['items']) for v in res.values())}; "
                 f"shown none {sum(len(v['none']) for v in res.values())}, all {sum(len(v['all']) for v in res.values())}")
lines.append("")
for name, res in list(results.items())[1:]:
    lost_text = held_ok = held_bad = 0
    detail = []
    for label, b in base.items():
        for key, (quotes, writer_quotes) in b["items"].items():
            theirs = res[label]["items"].get(key)
            theirs = theirs[0] if theirs else None
            if theirs is None:
                writer = set(writer_quotes)
                if all(q in writer or len(q) > 600 for q in quotes):
                    held_ok += 1
                else:
                    held_bad += 1
                    detail.append(f"    held where {base_name} read a run within 600: {label}: {key[:70]!r}")
            elif not all(any(q in t for t in theirs) for q in quotes):
                lost_text += 1
                detail.append(f"    quote lost text: {label}: {key[:70]!r}")
    lines.append(f"{name} vs {base_name}: items whose quote lost text {base_name}'s carried {lost_text}; "
                 f"held where {base_name} read only the bare quote or over 600 {held_ok}; "
                 f"held where {base_name}'s run was within 600 {held_bad}")
    lines.extend(detail)
    for mode in ("none", "all"):
        new = dropped = 0
        for label, b in base.items():
            new += sum(1 for s in res[label][mode] if s not in b[mode])
            dropped += sum(1 for s in b[mode] if s not in res[label][mode])
        lines.append(f"{name} vs {base_name}, approves {mode}: shown that {base_name} does not show {new}; "
                     f"{base_name} sentences dropped {dropped}")
Path(OUT).write_text("\n".join(lines) + "\n")
print("\n".join(lines))
