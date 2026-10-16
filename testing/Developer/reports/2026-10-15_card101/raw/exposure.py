"""Card 101, graded breaks: what the new grading does to the recorded record values.

Usage: python -I exposure.py <develop-src> <new-src> trace <trace-folder>...
       python -I exposure.py <develop-src> <new-src> corpus <root>

Prints, over every distinct record value found: develop's breaks and units,
the units the new code reads (must equal develop's), breaks regraded
`mark` or `abbrev` with their text, develop units no longer whole (a unit
after a soft break), and units newly over 600 characters (must be 0).
"""

import importlib
import json
import sys
from pathlib import Path


def load(src):
    for name in [k for k in sys.modules if k.startswith("system_03")]:
        del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    sys.path.pop(0)
    return gr


def walk(node):
    if isinstance(node, dict):
        if "field" in node:
            for key in ("field_value", "value", "text"):
                if isinstance(node.get(key), str):
                    yield node[key]
            return
        for child in node.values():
            yield from walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from walk(child)


def trace_values(folders):
    values = set()
    for folder in folders:
        for path in Path(folder).glob("*.jsonl"):
            for line in path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("tag") == "FINDINGS":
                    values.update(f["text"] for f in row["data"] if f.get("text"))
    return values


def corpus_values(root):
    values = set()
    for path in list(Path(root).rglob("*.json")) + list(Path(root).rglob("*.jsonl")):
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError) as error:
            print(f"skipped {path.name}: {error}", file=sys.stderr)
            continue
        docs = []
        try:
            docs = [json.loads(text)]
        except json.JSONDecodeError:
            for line in text.splitlines():
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        for doc in docs:
            for s in walk(doc):
                if len(s) > 150 and ". " in s and not s.lstrip().startswith(("{", "<", "MATCH", "SELECT")):
                    values.add(" ".join(s.split()))
    return values


dev = load(sys.argv[1])
new = load(sys.argv[2])
mode = sys.argv[3]
values = trace_values(sys.argv[4:]) if mode == "trace" else corpus_values(sys.argv[4])
dev_breaks = dev_units = new_units = unequal = over = not_whole = 0
grades = {"mark": 0, "abbrev": 0, "hard": 0}
examples = []
for value in sorted(values):
    d_units = dev._record_sentences(value)
    n_units = new._record_units(value)
    dev_units += len(d_units)
    new_units += len(n_units)
    unequal += [t for t, _ in n_units] != d_units
    over += sum(len(t) > 600 for t, _ in n_units) - sum(len(t) > 600 for t in d_units)
    breaks = new._record_breaks(value)
    dev_breaks += len(list(dev._RECORD_SENTENCE_BOUNDARY.finditer(value)))
    for end, start, grade in breaks:
        grades[grade] += 1
        if grade != "hard":
            examples.append(f"{grade}: ..." + value[max(0, end - 40) : start + 30].replace("\n", " ") + "...")
    not_whole += sum(1 for _, g in n_units if g not in ("start", "hard"))
print(f"distinct record values {len(values)}; develop breaks {dev_breaks}; develop units {dev_units}")
print(f"new units {new_units}; values whose units differ from develop's {unequal}; units newly over 600 {over}")
print(f"breaks by grade {grades}; develop units that are now cuts (follow a soft break) {not_whole}")
for line in examples[:40]:
    print("  " + line)
