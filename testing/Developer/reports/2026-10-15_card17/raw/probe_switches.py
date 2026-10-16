"""Card 17 option E design probe: find every shown sentence that fires the
switch rule, and by how many shared title words. Reuses replay_option_b.py's
trace reading. Read-only, no model call.

Usage: python -I probe_switches.py <src> <trace-folder>...
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC = sys.argv[1]
FOLDERS = sys.argv[2:]
sys.path.insert(0, SRC)

from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding


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


def drafts_of(rows):
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


def result_for(narrative, fs, quotes, approve):
    sink: list = []
    gr.run_grounding_pass(narrative, fs, True, "", quotes, None, sink)
    if approve == "all":
        keys = frozenset(c.key for c in sink)
    else:
        keys = frozenset(c.key for c in sink if c.key[0] in approve)
    return gr.run_grounding_pass(narrative, fs, True, "", quotes, keys)


def walk(result, fs):
    """Per shown sentence: refs, pages, reworded, and per cited page the shared stems."""
    {f.ref_index: f for f in fs}
    labels_by_url: dict[str, str] = {}
    for f in fs:
        url = (f.source_url or "").strip()
        if url and f.field in gr.LABEL_FIELDS:
            labels_by_url[url] = f"{labels_by_url.get(url, '')} {f.field_value}".strip()
    text_by_url: dict[str, list[str]] = {}
    for f in fs:
        url = (f.source_url or "").strip()
        if url:
            text_by_url.setdefault(url, []).append(f.field_value)
    short_by_url = {u: gr.defined_short_forms(" ".join(v)) for u, v in text_by_url.items()}
    claims = list(result.claims)
    cursor = 0
    out = []
    for sentence in result.sentences:
        n = len(gr._MARKER.findall(sentence))
        own = claims[cursor:cursor + n]
        cursor += n
        urls = {(c.finding.source_url or "").strip() for c in own}
        refs = {c.finding.ref_index for c in own}
        reworded = any(c.evidence_quote for c in own)
        shared = {}
        shorts = {}
        said = gr._stemmed(gr.content_tokens(plain(sentence)))
        for url in urls:
            title = gr._stemmed(gr.content_tokens(labels_by_url.get(url, "")))
            shared[url] = sorted(said & title)
            hit = []
            for short, long_form in short_by_url.get(url, {}).items():
                if gr._stemmed(gr.content_tokens(long_form)) & title and re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(short)}(?![A-Za-z0-9])", sentence
                ):
                    hit.append(short)
            shorts[url] = hit
        out.append({"sentence": plain(sentence), "refs": refs, "urls": urls, "reworded": reworded,
                        "shared": shared, "shorts": shorts, "labels": {u: labels_by_url.get(u, "") for u in urls}})
    return out


tally = {"shown": 0, "reworded": 0, "switch_ref": 0, "switch_page": 0, "one_word": 0, "first": 0}
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
        label = f"{Path(folder).name}/{path.stem}"
        for di, draft in enumerate(drafts):
            quotes = quotes_for(draft["narrative"], draft["items"])
            for mode in ("live", "all"):
                approve = "all" if mode == "all" else draft["approved"]
                res = result_for(draft["narrative"], fs, quotes, approve)
                walked = walk(res, fs)
                prev = None
                for i, s in enumerate(walked):
                    tally["shown"] += 1
                    if s["reworded"]:
                        tally["reworded"] += 1
                    if prev is None:
                        if s["reworded"]:
                            tally["first"] += 1
                        prev = s
                        continue
                    if s["reworded"] and not (s["refs"] & prev["refs"]):
                        tally["switch_ref"] += 1
                        new_pages = s["urls"] - prev["urls"]
                        if new_pages == s["urls"]:
                            tally["switch_page"] += 1
                            counts = {u: len(s["shared"][u]) for u in s["urls"]}
                            by_one = all(len(s["shared"][u]) <= 1 and not s["shorts"][u] for u in s["urls"]) and any(len(s["shared"][u]) == 1 for u in s["urls"])
                            if by_one:
                                tally["one_word"] += 1
                            print(f"== {label} draft{di} {mode} sent{i} {'ONE-WORD' if by_one else 'anchored'}")
                            print(f"   prev: {prev['sentence'][:160]}")
                            print(f"   prev titles: {[prev['labels'][u][:90] for u in prev['urls']]}")
                            print(f"   this: {s['sentence'][:220]}")
                            for u in s["urls"]:
                                print(f"   -> {s['labels'][u][:120]!r} shared={s['shared'][u]} short={s['shorts'][u]}")
                        else:
                            print(f"== {label} draft{di} {mode} sent{i} SAME-PAGE switch (ref only)")
                            print(f"   this: {s['sentence'][:160]}")
                    prev = s
print(tally)
