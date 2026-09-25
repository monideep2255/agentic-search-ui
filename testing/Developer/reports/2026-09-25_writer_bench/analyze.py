"""Analysis pass for the writer-tier bench, card 10, 2026-09-25.

Reads results.jsonl (one row per model x question run) and computes, per
row:

- answered: trust_outcome == "answer" (the clean, fully-trusted outcome).
  "ask" and "flag" are partial/hedge outcomes the trust gate can also
  return (contracts/events.py TrustOutcome = answer|flag|ask|refuse); they
  are reported separately, never folded into "answered".
- fallback: whether write_node discarded the model's own prose entirely
  and shipped the code-built per-record list instead. Detected by the
  fixed caveat sentence `_build_structured_fallback_note()` emits
  (core/graph.py ~line 7684), which is the only place that exact string is
  written and is shown to the reader whenever the fallback fires.
- prose_sentences_kept: count of the model's own generated sentences that
  survived the grounding gate and are shown. The opening "Found N ...
  records for X:" line is CODE-BUILT (`answer_summary_sentence`,
  core/graph.py ~line 10257 area, "built in code, not by the model"), and
  every "<Type> records found" section and the per-record lines under it
  are also code-built (core/graph.py:9829, `f"{noun} records found"`).
  Only the text between the opening summary line and the first such
  section header is the model's own prose. When fallback is True, this is
  0 by construction: the model's own summary was discarded outright.

This heuristic is stated here rather than hidden, per goal-contracts: it is
a bench measurement, not a shipped code path, and a different reader
counting differently is expected to get numbers close to, not identical
to, this script's.
"""
import json
import re
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
RESULTS = OUT_DIR / "results.jsonl"

FALLBACK_MARKER = "the written summary of these records could not be verified against them"
SECTION_HEADER_RE = re.compile(r"^[A-Z][A-Za-z /]+ records? found\s*$")


def strip_leading_summary(text: str) -> str:
    """Drop the code-built opening 'Found N ... for X: ...' sentence."""
    if text.startswith("Found "):
        # Cut at the first ". " or newline, whichever comes first.
        m = re.search(r"\.\s|\n", text)
        if m:
            return text[m.end():]
        return ""
    return text


def prose_region(text: str) -> str:
    """Return the model-authored slice of the answer, before any code-built
    findings-tail section header."""
    body = strip_leading_summary(text)
    lines = body.split("\n")
    cut = len(lines)
    for i, line in enumerate(lines):
        if SECTION_HEADER_RE.match(line.strip()):
            cut = i
            break
    return "\n".join(lines[:cut]).strip()


def split_sentences(text: str) -> list[str]:
    text = text.replace("\n\n", " ").replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Drop bare section-title fragments (title case, no terminal
        # punctuation, short) that survived the join, e.g. a subheading
        # like "Gene Function and Disease Context".
        word_count = len(p.split())
        if word_count < 4:
            continue
        out.append(p)
    return out


def analyze_row(row: dict) -> dict:
    text = row.get("answer_text") or ""
    trust_outcome = row.get("trust_outcome")
    answered = trust_outcome == "answer"
    fallback = FALLBACK_MARKER in text
    if fallback:
        kept_sentences: list[str] = []
    else:
        kept_sentences = split_sentences(prose_region(text))
    first_two = kept_sentences[:2]
    return {
        "model": row["model"],
        "question_id": row["question_id"],
        "trust_outcome": trust_outcome,
        "answered": answered,
        "fallback": fallback,
        "prose_sentences_kept": len(kept_sentences),
        "citations": row.get("citation_count"),
        "seconds": row.get("elapsed_s"),
        "cost_usd": row.get("cost_usd"),
        "first_two_sentences": first_two,
        "errors": row.get("errors") or [],
    }


def main() -> None:
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    analyzed = [analyze_row(r) for r in rows]
    out_path = OUT_DIR / "analyzed.jsonl"
    with open(out_path, "w") as f:
        for a in analyzed:
            f.write(json.dumps(a) + "\n")
    print(f"wrote {len(analyzed)} rows to {out_path}")


if __name__ == "__main__":
    main()
