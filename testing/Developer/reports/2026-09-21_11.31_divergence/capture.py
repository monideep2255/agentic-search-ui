"""Counts prose words, paragraphs, and record rows in each captured answer
under raw/, for the 2026-09-21 11.31 answer-mode divergence baseline.

Run as: python3 capture.py

Classification method (verified against the four captured answers by eye,
see raw/*.json): the answer text splits on blank lines ("\\n\\n") into
blocks. A block that matches "<Label> records found" or equals
"Variant-to-disease mapping" is a SECTION HEADER; the block immediately
following a header is always the one dump of record rows for that section
(confirmed: every header in all four captures is followed by exactly one
such block, never by another header). Every other block, including the
opening summary paragraph(s), the "Note:" lines, and the closing
disclaimer, is PROSE.

Record rows are counted as the number of "[n]" citation markers inside a
RECORD_DUMP block, since every rendered row in this answer format ends
with exactly one citation bracket (verified by inspection: "Disease name:
X [2]. Disease name: Y [4]." is two rows, two brackets).

Prose word count strips citation brackets "[n]" before splitting on
whitespace, so a bracket is not counted as a word.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"
HEADER_RE = re.compile(r"^[A-Za-z][A-Za-z\- ]* records found$")
BRACKET_RE = re.compile(r"\[\d+\]")

FILES = [
    "brca1_plain_language.json",
    "brca1_researcher.json",
    "hnf1a_plain_language.json",
    "hnf1a_researcher.json",
]


def is_header(block: str) -> bool:
    return bool(HEADER_RE.match(block)) or block.strip() == "Variant-to-disease mapping"


def classify_and_count(text: str):
    """Return (prose_word_count, paragraph_count, record_row_count, prose_text)."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    prose_words = 0
    paragraph_count = 0
    record_rows = 0
    prose_blocks = []
    expect_dump = False
    for block in blocks:
        if is_header(block):
            expect_dump = True
            continue
        if expect_dump:
            record_rows += len(BRACKET_RE.findall(block))
            expect_dump = False
            continue
        # Prose block: intro paragraph, a Note:, the placeholder-conditions
        # sentence, or the closing disclaimer.
        stripped = BRACKET_RE.sub("", block)
        words = stripped.split()
        prose_words += len(words)
        paragraph_count += 1
        prose_blocks.append(block)
    return prose_words, paragraph_count, record_rows, "\n\n".join(prose_blocks)


def main():
    results = {}
    for fname in FILES:
        path = RAW_DIR / fname
        data = json.loads(path.read_text())
        text = data["answer_text"]
        prose_words, paragraphs, rows, _prose_text = classify_and_count(text)
        ratio = prose_words / rows if rows else float("inf")
        results[fname] = {
            "question": data["question"],
            "audience_depth": data["audience_depth"],
            "outcome": data.get("outcome"),
            "run_id": data.get("run_id"),
            "prose_word_count": prose_words,
            "paragraph_count": paragraphs,
            "record_row_count": rows,
            "prose_words_per_record_row": round(ratio, 4) if rows else None,
            "total_char_count": len(text),
        }
        print(
            f"{fname}: depth={data['audience_depth']:<15} "
            f"prose_words={prose_words:<5} paragraphs={paragraphs:<3} "
            f"rows={rows:<3} ratio={results[fname]['prose_words_per_record_row']}"
        )

    out_path = RAW_DIR.parent / "counts.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
