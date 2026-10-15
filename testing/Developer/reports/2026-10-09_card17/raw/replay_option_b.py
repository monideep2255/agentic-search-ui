"""Card 17, option B: replay saved live write steps through the grounding pass.

Usage: python -I replay_option_b.py <src> <out.txt> <trace-folder>...

No model call, no network. Each trace is a JSON-lines file written by a
`trace_run.py` of the card 88 bench family (`local_write_trace.py`'s spies,
plus the findings with their pages and the sentence check's items):

- FINDINGS: every finding the write step grounded against, with its page.
- GROUNDING: each narrative the pass saw, its quoted markers already
  rewritten to `[N#k]`.
- CHECK_IN and CHECK_OUT: the reworded sentences sent to the sentence check,
  with the writer's own quotes, and the ones it approved live.

The writer's quotes are rebuilt from CHECK_IN (sentence by sentence, in
marker order). A quote never sent to the check is left empty, so that
sentence is stripped alike on both sides.

Two sides, same code: "before" is the new code with the left records' titles
forced empty, which is exactly the code before card 17; "after" is the new
code. Per writer draft, two approval modes:

- live: the approvals the sentence check gave in that run;
- all: every reworded candidate approved, the widest test of the switch rule.

Reports the sentences "before" shows that "after" drops, and per run the
written sentences shown in the draft the run shipped (the last writer draft
the check saw), against the card 88 bar of two or more on 5 of 5 runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC, OUT = sys.argv[1], sys.argv[2]
FOLDERS = sys.argv[3:]
sys.path.insert(0, SRC)

from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

_real_names = gr._names_its_record


def _before(sentence, labels, short_forms=None, left_labels=""):
    return _real_names(sentence, labels, short_forms, "")


def plain(sentence: str) -> str:
    text = " ".join(re.sub(r"\[\d+(?:#\d+)?\]", "", sentence).split())
    return re.sub(r"\s+([.,;:])", r"\1", text)


def bare(sentence: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", plain(sentence).lower()).strip()


def rows_of(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "tag" in row:
            rows.append(row)
    return rows


def findings_of(data: list[dict]) -> list[SynthFinding]:
    return [
        SynthFinding(
            ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
            field=f["field"], field_value=f.get("text") or "", source_url=f.get("url") or "",
        )
        for f in data
    ]


def quotes_for(narrative: str, items: list[dict]) -> tuple[str, ...]:
    by_sentence = {
        bare(item["sentence"]): item.get("writer_quotes") or item.get("quotes") or []
        for item in items
    }
    count = len(re.findall(r"\[\d+#\d+\]", narrative))
    quotes = [""] * count
    for sentence in gr._split_sentences(narrative):
        ks = [int(k) for k in re.findall(r"\[\d+#(\d+)\]", sentence)]
        writer = by_sentence.get(bare(sentence))
        if writer is None:
            continue
        for k, quote in zip(ks, writer):
            if k < count:
                quotes[k] = quote
    return tuple(quotes)


def shown(narrative, fs, quotes, approve):
    sink: list = []
    gr.run_grounding_pass(narrative, fs, True, "", quotes, None, sink)
    if approve == "all":
        keys = frozenset(c.key for c in sink)
    else:
        keys = frozenset(c.key for c in sink if c.key[0] in approve)
    res = gr.run_grounding_pass(narrative, fs, True, "", quotes, keys)
    return [plain(s) for s in res.sentences]


def drafts_of(rows):
    """Each writer draft with its CHECK_IN items and live approvals."""
    out = []
    pending = None
    for row in rows:
        tag, data = row["tag"], row["data"]
        if tag == "GROUNDING":
            narrative = data.get("narrative") or ""
            if "#" not in narrative or narrative.lower().startswith(("pubmed title", "found ")):
                continue
            if pending is None or pending["narrative"] != narrative:
                pending = {"narrative": narrative, "items": [], "approved": set(), "checked": False}
                out.append(pending)
        elif tag == "CHECK_IN" and pending is not None:
            pending["items"] = data.get("items") or []
            pending["checked"] = True
        elif tag == "CHECK_OUT" and pending is not None:
            pending["approved"] = set(data.get("approved_sentences") or [])
    return out


lines = ["Card 17 option B replay (replay_option_b.py), no model call.", ""]
totals = {"drafts": 0, "runs": 0}
dropped: dict[str, list[tuple[str, str]]] = {"live": [], "all": []}
per_run = []
for folder in FOLDERS:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = rows_of(path)
        data = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), None)
        if not data:
            continue
        fs = findings_of(data)
        drafts = drafts_of(rows)
        if not drafts:
            continue
        totals["runs"] += 1
        label = f"{Path(folder).name}/{path.stem}"
        shipped = None
        for draft in drafts:
            totals["drafts"] += 1
            quotes = quotes_for(draft["narrative"], draft["items"])
            result = {}
            for mode in ("live", "all"):
                approve = "all" if mode == "all" else draft["approved"]
                gr._names_its_record = _before
                before = shown(draft["narrative"], fs, quotes, approve)
                gr._names_its_record = _real_names
                after = shown(draft["narrative"], fs, quotes, approve)
                lost = [s for s in before if s not in after]
                dropped[mode].extend((label, s) for s in lost)
                result[mode] = (len(before), len(after))
            if draft["checked"]:
                shipped = result
        if shipped is None:
            shipped = result
        per_run.append((label, shipped))

lines.append(f"Runs {totals['runs']}, writer drafts {totals['drafts']}.")
for mode in ("live", "all"):
    lines.append(f"Approves {mode}: sentences shown before and dropped after: {len(dropped[mode])}")
    for label, sentence in dropped[mode]:
        lines.append(f"  {label}: {sentence}")
lines.append("")
lines.append("Per run, the last checked draft: written sentences before -> after (live; all)")
for label, res in per_run:
    lines.append(f"  {label}: {res['live'][0]} -> {res['live'][1]}; {res['all'][0]} -> {res['all'][1]}")
Path(OUT).write_text("\n".join(lines) + "\n")
print("\n".join(lines))
