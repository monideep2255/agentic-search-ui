"""Card 101 round 3: which shown sentences the whole-record-sentence rule moves.

No model call. Reads the recorded traces of the diagnosis (wave 3, card 101
build and fix round) and of round 2's live answers. The traces sit outside the
repository (they carry record text); pass their folders as arguments:

    python scan_copied_cuts.py <wave3_raw> <wave3_develop_control> \
        <card101_build> <card101_fix_round> <round2_live>

Per answer:
- shown: claim sentences on screen (the code-built "I found N" line skipped).
- moved_shown: shown sentences that code alone accepted (not a sentence check
  candidate) with at least one clause that is not a whole record sentence
  (`grounding.is_whole_record_sentence`); split into cut and wrap.
- items_added: such clauses in every first grounding pass (a first draft or a
  repair), shown or not; each becomes one sentence check item.
- new_calls: first passes with no candidate before but at least one now.
- all_moved: every shown sentence moved, so the answer keeps prose only if the
  check approves at least one.

Prints counts and the moved sentences (record text stays in the console, the
committed output keeps counts only when run with --counts).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.findings import SynthFinding

SUMMARY = re.compile(r"^(I found|Found) \d")
DISPLAY_MARKER = re.compile(r"\[(\d{1,3})\]")
KEYED = re.compile(r"\[\d{1,3}(?:#\d{1,3})?\]")


def findings_of(rows: list[dict]) -> list[SynthFinding]:
    data = next((r["data"] for r in rows if r.get("tag") == "FINDINGS"), [])
    return [
        SynthFinding(
            ref_index=int(f["ref"]),
            citation_id=f"c-{f['ref']}",
            layer="",
            tool=f.get("tool", ""),
            field=f["field"],
            field_value=f["text"] or "",
            source_url=f.get("url", ""),
        )
        for f in data
    ]


def clauses(sentence: str) -> list[str]:
    """The clauses of a shown or kept sentence, one per marker."""
    out: list[str] = []
    cursor = 0
    for match in DISPLAY_MARKER.finditer(sentence):
        text = gr._clean_claim(sentence[cursor : match.start()])
        cursor = match.end()
        if gr._asserts_something(text):
            out.append(text)
    return out


def moved_clauses(sentence: str, findings: list[SynthFinding]) -> list[tuple[str, str]]:
    """(kind, clause) for every clause the new rule sends to the check."""
    moved = []
    for clause in clauses(sentence):
        grounds = [f for f in findings if gr.ground_claim(clause, f.field_value)]
        if not grounds:
            continue
        if any(gr.is_whole_record_sentence(clause, f) for f in grounds):
            continue
        kind = "wrap" if all(gr._wraps_record_value(clause, f) for f in grounds) else "cut"
        moved.append((kind, clause))
    return moved


def plain(text: str) -> str:
    return gr._quote_form(KEYED.sub(" ", text))


def scan(name: str, folder: Path, verbose: bool) -> list[tuple]:
    out = []
    for path in sorted(folder.glob("*.jsonl")):
        rows = [r for r in (json.loads(x) for x in path.read_text().splitlines() if x.strip()) if isinstance(r, dict) and "tag" in r]
        findings = findings_of(rows)
        if not findings:
            continue
        cands = set()
        for r in rows:
            if r["tag"] != "CHECK_IN":
                continue
            items = r["data"]["items"]
            items = items if isinstance(items, list) else ast.literal_eval(items)
            cands |= {plain(it["sentence"]) for it in items}
        shown = [
            r["data"][len("claim: ") :]
            for r in rows
            if r["tag"] == "TOKEN"
            and r["data"].startswith("claim: ")
            and not SUMMARY.match(r["data"][len("claim: ") :])
        ]
        cut_shown = wrap_shown = 0
        for s in shown:
            if plain(s) in cands:
                continue
            m = moved_clauses(s, findings)
            if not m:
                continue
            if any(k == "cut" for k, _ in m):
                cut_shown += 1
            else:
                wrap_shown += 1
            if verbose:
                for kind, clause in m:
                    print(f"  {name} {path.stem} [{kind}] {clause}")
        cut_items = wrap_items = new_calls_cut = new_calls_all = 0
        for r in rows:
            if r["tag"] != "GROUNDING":
                continue
            d = r["data"]
            cc = d.get("candidates_collected")
            if cc in (None, "None"):
                continue
            kept = d.get("kept_sentences")
            kept = ast.literal_eval(kept) if isinstance(kept, str) else kept
            moved = [k for s in kept for k, _ in moved_clauses(s, findings)]
            cuts, wraps = moved.count("cut"), moved.count("wrap")
            cut_items += cuts
            wrap_items += wraps
            new_calls_cut += bool(cuts and int(cc) == 0)
            new_calls_all += bool((cuts or wraps) and int(cc) == 0)
        out.append((
            name, path.stem, len(shown), cut_shown, wrap_shown, cut_items, wrap_items,
            new_calls_cut, new_calls_all,
            bool(shown) and cut_shown == len(shown),
            bool(shown) and cut_shown + wrap_shown == len(shown),
        ))
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verbose = "--counts" not in sys.argv
    names = [
        "2026-10-05 wave 3, card 89 branch",
        "2026-10-05 wave 3, develop control",
        "2026-10-06 card 101 build",
        "2026-10-06 card 101 fix round",
        "2026-10-06 card 101 round 2 live",
    ]
    rows = []
    for name, folder in zip(names, args, strict=True):
        rows += scan(name, Path(folder), verbose)
    print(
        "\nsource | answer | shown | moved, a cut (this build) | moved, wraps only (pending)"
        " | items, cuts | items, wraps | new calls, cuts | new calls, cuts and wraps"
        " | all shown moved, cuts | all shown moved, cuts and wraps"
    )
    for r in rows:
        print(" | ".join(str(x) for x in r))

    def total(rs: list[tuple], label: str) -> None:
        print(
            f"{label}: answers {len(rs)}, shown {sum(r[2] for r in rs)},"
            f" moved by this build {sum(r[3] for r in rs)} in {sum(1 for r in rs if r[3])} answers,"
            f" wraps pending {sum(r[4] for r in rs)} in {sum(1 for r in rs if r[4])} answers,"
            f" items added: cuts {sum(r[5] for r in rs)}, wraps {sum(r[6] for r in rs)};"
            f" new calls: cuts {sum(r[7] for r in rs)}, cuts and wraps {sum(r[8] for r in rs)};"
            f" answers with every shown sentence moved: cuts {sum(r[9] for r in rs)},"
            f" cuts and wraps {sum(r[10] for r in rs)}"
        )

    print("\nTotals")
    for name in names:
        total([r for r in rows if r[0] == name], name)
    total(rows, "all")

if __name__ == "__main__":
    main()
