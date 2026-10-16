"""Card 17, option E: replay saved live write steps through the lead-in pass.

Usage: python -I replay_option_e.py <src> <out.txt> <trace-folder>...

No model call, no network. Reads the same traces as replay_option_b.py. Per
writer draft and approval mode (live, all) it builds:

- before: `run_grounding_pass`, then `drop_record_restatements` (develop);
- after: the same, then `name_switched_records`.

Then checks, and prints as counts: no sentence dropped, no body changed (the
after sentence with its lead-in removed equals the before sentence), the
lead-in on exactly the sentences meeting the conditions (computed here by a
separate walk that calls none of the helpers the change added), no lead-in
elsewhere, and every quoted title being the mechanically trimmed label of a
page the sentence cites.

Fix round 2026-10-16: the pass takes the order the reader sees. The saved
traces carry no lead pick and no card 111 listing, so the replay runs two
orders: the writer's own order, and the order with sentence 1 lifted to the
top (the lead pick's shape). In the second, the opener must never carry a
lead-in. Findings carry the record type their tool produces.

The expected walk shares only code that the change did not touch:
`gr.content_tokens`, `gr._stemmed` and `gr.defined_short_forms`. Those three
are exercised against develop by the judge's 39,888-call comparison; this
script does not make them independent of themselves.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC, OUT = sys.argv[1], sys.argv[2]
FOLDERS = sys.argv[3:]
sys.path.insert(0, SRC)

from system_03_search_agent.contracts.events import source_page_key
from system_03_search_agent.synthesis import answer_layout as al
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

LEAD = re.compile(
    r'^From (?:another record|(?:the|another|other) [A-Za-z ]+? (?:titled )?'
    r'((?:"[^"]*"(?: \(\d{4}\))?(?:, | and )?)+)(?: and another record)?): '
)
ENTITY_BY_TOOL = {
    "ncbi_efetch": "PubMed",
    "clinicaltrials_search": "ClinicalTrial",
    "pubtator_annotate": "Literature entity",
}


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
            ref_index=int(f["ref"]),
            citation_id=f"c-{f['ref']}",
            layer="",
            tool=f.get("tool", ""),
            field=f["field"],
            field_value=f.get("text") or "",
            source_url=f.get("url") or "",
            entity_type=ENTITY_BY_TOOL.get(f.get("tool", ""), ""),
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
        for k, quote in zip(ks, writer, strict=False):
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


def grounded(narrative, fs, quotes, approve):
    sink: list = []
    gr.run_grounding_pass(narrative, fs, True, "", quotes, None, sink)
    if approve == "all":
        keys = frozenset(c.key for c in sink)
    else:
        keys = frozenset(c.key for c in sink if c.key[0] in approve)
    return gr.run_grounding_pass(narrative, fs, True, "", quotes, keys)


def _stems(text):
    return gr._stemmed(gr.content_tokens(text))


def expected_fires(result, fs, order=None):
    """Which sentence indexes meet the conditions, by a separate walk.

    Written without `record_labels_by_page`, `short_forms_by_page`,
    `title_words_shared`, `names_by_short_form` or `short_form_definers`.
    """
    labels: dict[str, str] = {}
    texts: dict[str, list[str]] = {}
    for f in fs:
        url = (f.source_url or "").strip()
        if not url:
            continue
        texts.setdefault(url, []).append(f.field_value)
        if f.field in gr.LABEL_FIELDS:
            labels[url] = f"{labels.get(url, '')} {f.field_value}".strip()
    shorts = {u: gr.defined_short_forms(" ".join(v)) for u, v in texts.items()}
    pages_defining: dict[str, set[str]] = {}
    for u, forms in shorts.items():
        for short in forms:
            pages_defining.setdefault(short, set()).add(source_page_key(u) or u)
    claims = list(result.claims)
    cursor = 0
    per_sentence = []
    for sentence in result.sentences:
        n = len(gr._MARKER.findall(sentence))
        own = claims[cursor : cursor + n]
        cursor += n
        by_page: dict[str, set[str]] = {}
        for claim in own:
            url = (claim.finding.source_url or "").strip()
            by_page.setdefault(source_page_key(url), set()).add(url)
        text = gr._MARKER.sub(" ", sentence)
        counts = []
        short_hit = False
        for urls in by_page.values():
            label = " ".join(labels.get(u, "") for u in sorted(urls))
            counts.append(len(_stems(text) & _stems(label)) if label.strip() else 0)
            for u in urls:
                title = _stems(labels.get(u, ""))
                for short, long_form in shorts.get(u, {}).items():
                    if len(pages_defining.get(short, ())) > 1 or not labels.get(u, "").strip():
                        continue
                    if _stems(long_form) & title and re.search(
                        rf"(?<![A-Za-z0-9]){re.escape(short)}(?![A-Za-z0-9])", sentence
                    ):
                        short_hit = True
        per_sentence.append(
            (
                set(by_page),
                bool(own)
                and any(c.evidence_quote for c in own)
                and bool(counts)
                and max(counts) <= 1
                and 1 in counts
                and not short_hit,
            )
        )
    fired = []
    prev = None
    for index in order if order is not None else range(len(result.sentences)):
        pages, ok = per_sentence[index]
        if prev is not None and ok and not (pages & prev):
            fired.append(index)
        prev = pages
    return fired


def cited_titles(result, index, fs):
    """The mechanically trimmed labels of every page sentence `index` cites."""
    claims = list(result.claims)
    cursor = 0
    for i, sentence in enumerate(result.sentences):
        n = len(gr._MARKER.findall(sentence))
        own = claims[cursor : cursor + n]
        cursor += n
        if i == index:
            pages = {source_page_key(c.finding.source_url) for c in own}
            return {
                al.lead_in_title(f.field_value)
                for f in fs
                if f.field in gr.LABEL_FIELDS and source_page_key(f.source_url) in pages
            }
    return set()


tally = {
    "drafts": 0, "runs": 0, "shown": 0, "lead_in": {"live": 0, "all": 0},
    "expected": {"live": 0, "all": 0}, "dropped": 0, "changed": 0, "length_diff": 0,
    "unexpected_lead_in": 0, "missing_lead_in": 0, "title_mismatch": 0, "count_mismatch": 0,
    "lifted_runs": 0, "lifted_lead_in": 0, "lifted_opener_led": 0, "lifted_disagree": 0,
}
written = []
added: list[str] = []
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
        tally["runs"] += 1
        label = f"{Path(folder).name}/{path.stem}"
        shipped = None
        for di, draft in enumerate(drafts):
            tally["drafts"] += 1
            quotes = quotes_for(draft["narrative"], draft["items"])
            result_counts = {}
            for mode in ("live", "all"):
                approve = "all" if mode == "all" else draft["approved"]
                first = grounded(draft["narrative"], fs, quotes, approve)
                before, _ = al.drop_record_restatements(first, fs)
                after, named = al.name_switched_records(before, fs)
                if len(before.sentences) > 1:
                    # The lead pick's shape: sentence 1 opens the answer.
                    lifted = [1, 0, *range(2, len(before.sentences))]
                    lifted_after, lifted_named = al.name_switched_records(before, fs, lifted)
                    lifted_got = {
                        i
                        for i, (b, a) in enumerate(
                            zip(before.sentences, lifted_after.sentences, strict=True)
                        )
                        if a != b
                    }
                    tally["lifted_runs"] += 1
                    tally["lifted_lead_in"] += len(lifted_got)
                    tally["lifted_opener_led"] += int(1 in lifted_got)
                    tally["lifted_disagree"] += int(
                        lifted_got != set(expected_fires(before, fs, lifted))
                        or lifted_named != len(lifted_got)
                    )
                tally["shown"] += len(before.sentences)
                if len(before.sentences) != len(after.sentences):
                    tally["length_diff"] += 1
                    continue
                if (
                    after.claims != before.claims
                    or after.stripped_count != before.stripped_count
                    or after.sentence_origins != before.sentence_origins
                ):
                    tally["changed"] += 1
                expect = set(expected_fires(before, fs))
                got = set()
                for i, (b, a) in enumerate(zip(before.sentences, after.sentences, strict=True)):
                    if a == b:
                        continue
                    match = LEAD.match(a)
                    if not match or a[match.end():] != b:
                        tally["changed"] += 1
                        continue
                    got.add(i)
                    quoted = re.findall(r'"([^"]*)"', match.group(1))
                    if not set(quoted) <= cited_titles(before, i, fs):
                        tally["title_mismatch"] += 1
                    added.append(f"{label} draft{di} {mode} sent{i}: {a[: match.end()]}| {plain(b)[:90]}")
                tally["lead_in"][mode] += len(got)
                tally["expected"][mode] += len(expect)
                tally["missing_lead_in"] += len(expect - got)
                tally["unexpected_lead_in"] += len(got - expect)
                if named != len(got):
                    tally["count_mismatch"] += 1
                # Written (reworded) sentences shown: unchanged by construction.
                n_written = 0
                cursor = 0
                claims = list(after.claims)
                for s in after.sentences:
                    k = len(gr._MARKER.findall(s))
                    n_written += any(c.evidence_quote for c in claims[cursor : cursor + k])
                    cursor += k
                result_counts[mode] = n_written
            if draft["checked"]:
                shipped = result_counts
        if shipped is None:
            shipped = result_counts
        per_run.append((label, shipped))

lines = ["Card 17 option E replay (replay_option_e.py), no model call.", ""]
lines.append(f"Runs {tally['runs']}, writer drafts {tally['drafts']}, shown sentences (both modes) {tally['shown']}.")
lines.append(f"Lead-ins added, live: {tally['lead_in']['live']} (expected by the five conditions: {tally['expected']['live']})")
lines.append(f"Lead-ins added, all approved: {tally['lead_in']['all']} (expected: {tally['expected']['all']})")
lines.append(f"Sentence count changed (dropped): {tally['length_diff']}")
lines.append(f"Bodies, claims or counts changed: {tally['changed']}")
lines.append(f"Sentences meeting the conditions with no lead-in: {tally['missing_lead_in']}")
lines.append(f"Lead-ins on sentences not meeting the conditions: {tally['unexpected_lead_in']}")
lines.append(f"Quoted titles that are not the label of a cited page: {tally['title_mismatch']}")
lines.append(f"Pass count disagreeing with sentences changed: {tally['count_mismatch']}")
lines.append(
    f"Lead pick order (sentence 1 first): {tally['lifted_runs']} cases, {tally['lifted_lead_in']} lead-ins, "
    f"opener led in {tally['lifted_opener_led']}, disagreeing with the separate walk {tally['lifted_disagree']}"
)
lines.append("")
lines.append("Per run, last checked draft: written sentences shown (live; all). Unchanged by the pass.")
for label, res in per_run:
    lines.append(f"  {label}: {res.get('live')}; {res.get('all')}")
gerd = [r for r in per_run if re.search(r"/(gp|gr|gerd)\d$", r[0])]
lines.append(f"GERD runs with two or more written sentences live: {sum(1 for _, r in gerd if (r.get('live') or 0) >= 2)} of {len(gerd)}")
lines.append("")
lines.append("Every lead-in added (run, draft, mode, sentence index: lead-in | start of the sentence):")
lines.extend(f"  {a}" for a in added)
Path(OUT).write_text("\n".join(lines) + "\n")
print("\n".join(lines[:13]))
