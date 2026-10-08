"""Card 101 round 3 adversary: what the branch loses on recorded first passes.

No model call. For every recorded GROUNDING row (the writer's draft with its
findings) the draft is replayed through develop's and the branch's
`run_grounding_pass`:

- develop, approving every check item develop itself collects (best case);
- branch, best: approving every item the branch collects;
- branch, worst: approving only develop's items, so every copied cut the
  branch moved to the check is held (the check holds them, fails, times out
  or runs in guard mode and says no).

Counts per row: shown sentences, sentences lost in the worst case, and how
many of those lost sentences hold no moved clause themselves (collateral:
taken by the middle-strip, pronoun or switch rules). Writer quotes are
rebuilt from the CHECK_IN items where possible; an unknown quote is "".

Usage: python replay_cost.py <develop-src> <branch-src> <trace-folder>...
Prints counts only with --counts, otherwise also the lost sentences.
"""
import ast
import importlib
import json
import re
import sys
from pathlib import Path

DEV, BR = sys.argv[1], sys.argv[2]
FOLDERS = [a for a in sys.argv[3:] if not a.startswith("--")]
VERBOSE = "--counts" not in sys.argv

Q = {
    "m": "Are there any beneficial variants typically found in people of mediterranean descent?",
    "g": "What are the typical symptoms and risk factors of GERD?",
    "b": "What causes bronchiolitis in babies, and how is it usually treated?",
}


def load(src):
    for name in list(sys.modules):
        if name.startswith("system_03_search_agent"):
            del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    fi = importlib.import_module("system_03_search_agent.synthesis.findings")
    sys.path.remove(src)
    return gr, fi


def question_for(stem):
    s = stem.lstrip("c")
    if stem.startswith("c"):
        s = stem[1:]
    return Q.get(s[0], "")


KEYED = re.compile(r"\[(\d{1,3})#(\d{1,3})\]")


def rebuild_quotes(narrative, rows, gr):
    keys = [int(m.group(2)) for m in KEYED.finditer(narrative)]
    n = max(keys) + 1 if keys else 0
    quotes = [""] * n
    items = []
    for r in rows:
        if r["tag"] == "CHECK_IN":
            it = r["data"]["items"]
            items += it if isinstance(it, list) else ast.literal_eval(it)
    by_sentence = {}
    for it in items:
        by_sentence.setdefault(" ".join(it["sentence"].lower().split()), it.get("writer_quotes") or [])
    for sentence in gr._split_sentences(narrative):
        segs = gr._segments(sentence)
        for i, (text, marker, key) in enumerate(segs):
            if key is None:
                continue
            claim = " ".join(gr._clean_claim(text).lower().split())
            wq = by_sentence.get(claim)
            if not wq:
                continue
            # keys on this marker and on the bare markers following it
            ks = [key]
            for t2, m2, k2 in segs[i + 1:]:
                if m2 is None or gr._asserts_something(gr._clean_claim(t2)):
                    break
                if k2 is not None:
                    ks.append(k2)
            for k, q in zip(ks, wq):
                if k < n and not quotes[k]:
                    quotes[k] = q
    return tuple(quotes)


def run(gr, fi, narrative, findings_rows, q, quotes, verified):
    fs = [fi.SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                          field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
          for f in findings_rows]
    sink = []
    res = gr.run_grounding_pass(narrative, fs, True, q, quotes, verified, sink)
    return res, sink


def shown(res):
    return [s for s in res.narrative and _split(res.narrative) or []]


def _split(text):
    # Display markers removed, so a sentence renumbered after a held one is
    # not counted as lost.
    text = re.sub(r"\s*\[\d{1,3}\]", "", text)
    return [s.strip() for s in re.split(r"(?<=[.;?!])\s+", text.strip()) if s.strip()]


dev = load(DEV)
br = load(BR)
tot = dict(rows=0, dev_shown=0, best_shown=0, worst_shown=0, lost=0, rows_lost=0, rows_emptied=0,  # noqa: C408
           new_items=0, rows_new_call=0)
per = []
SEEN = set()
for folder in FOLDERS:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = []
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001, S112
                continue
            if isinstance(r, dict) and "tag" in r:
                rows.append(r)
        frows = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), None)
        if not frows:
            continue
        q = question_for(path.stem)
        for gi, r in enumerate(x for x in rows if x["tag"] == "GROUNDING"):
            narrative = r["data"]["narrative"]
            # The trace logs a draft's first and second pass alike; count each
            # distinct draft (narrative and findings) once.
            sig = (narrative, json.dumps(frows, sort_keys=True))
            if sig in SEEN:
                continue
            SEEN.add(sig)
            quotes = rebuild_quotes(narrative, rows, br[0])
            dres0, dsink = run(*dev, narrative, frows, q, quotes, None)
            dkeys = frozenset(c.key for c in dsink)
            dres, _ = run(*dev, narrative, frows, q, quotes, dkeys)
            bres0, bsink = run(*br, narrative, frows, q, quotes, None)
            bkeys = frozenset(c.key for c in bsink)
            bbest, _ = run(*br, narrative, frows, q, quotes, bkeys | dkeys)
            bworst, _ = run(*br, narrative, frows, q, quotes, dkeys)
            ds, bs, ws = _split(dres.narrative or ""), _split(bbest.narrative or ""), _split(bworst.narrative or "")
            lost = [s for s in ds if s not in ws]
            tot["rows"] += 1
            tot["dev_shown"] += len(ds)
            tot["best_shown"] += len(bs)
            tot["worst_shown"] += len(ws)
            tot["lost"] += len(lost)
            tot["rows_lost"] += bool(lost)
            tot["rows_emptied"] += bool(ds) and not ws
            new = len(bkeys - dkeys)
            tot["new_items"] += new
            tot["rows_new_call"] += bool(new and not dkeys)
            per.append((path.parent.name, path.stem, gi, len(ds), len(bs), len(ws), len(lost), new))
            if VERBOSE and (lost or len(bs) != len(ds)):
                print(f"== {path.parent.name}/{path.stem} grounding {gi}: dev {len(ds)} best {len(bs)} worst {len(ws)} new items {new}")
                for c in bsink:
                    if c.key not in dkeys:
                        print("   ITEM:", c.sentence[:200])
                for s in lost:
                    print("   LOST:", s[:200])
                for s in ds:
                    if s not in bs:
                        print("   LOST EVEN IF APPROVED:", s[:200])
print("folder | answer | grounding | dev shown | branch best | branch worst | lost worst | new items")
for p in per:
    if p[6] or p[7] or p[3] != p[4]:
        print(" | ".join(map(str, p)))
print(json.dumps(tot))
