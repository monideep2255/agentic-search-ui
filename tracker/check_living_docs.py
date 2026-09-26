"""Check the living documents against tracker/Living_documents.md.

The registry names, for every document a session-closing skill keeps
current, the anchors (headings or line prefixes) the owner may write to.
This script reads those rows and checks one thing:

    --shape   every named anchor still exists in its document

A red --shape means the document changed shape and the registry has not
caught up. It is NOT an instruction to put the section back: the decision
guard in /phase-checkpoint reads DECISIONS.md and updates the registry first.

There is no freshness check any more. Until 2026-09-25 a `--fresh` flag
required every registered document to carry today's date, and /ship refused
to push until it did, so every session ended with edits that only moved a
date. Build harness review item D2 removed it, delegated by the product owner
on 2026-09-25 (DECISIONS.md, "The lead implements both harness reviews'
takeaways"): a session end rewrites HANDOFF.md, and every other document is
edited when its fact changes, not because a date is due.

Stdlib only. Runs from anywhere: paths resolve against the repository root.

Depends on:
    - tracker/Living_documents.md (the registry, the only input)

Reads:
    - every document the registry names

Writes:
    - nothing

--self-test mutates copies of the registry rows in memory and asserts each
arm can fail, so a green run proves the arms are live, not merely present.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
REGISTRY = ROOT / "Living_documents.md"

BACKTICK_RE = re.compile(r"`([^`]+)`")
ROW_RE = re.compile(r"^\|(.+)\|\s*$")
COLUMNS = 5


class Row:
    def __init__(self, cells: list[str]) -> None:
        self.document, self.job, self.owner, self.shape, self.set_by = cells
        self.paths = BACKTICK_RE.findall(self.document)
        self.anchors = [
            a for a in BACKTICK_RE.findall(self.shape)
            if a not in ("none", "unpinned")
        ]
        self.pinned = "`unpinned`" not in self.shape


def parse_registry(text: str) -> list[Row]:
    rows: list[Row] = []
    in_table = False
    for line in text.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            in_table = False
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if cells and cells[0] == "Document":
            in_table = True
            continue
        if not in_table or all(set(c) <= {"-"} for c in cells):
            continue
        if len(cells) != COLUMNS:
            raise ValueError(f"registry row has {len(cells)} cells, expected {COLUMNS}: {line[:80]}")
        rows.append(Row(cells))
    if not rows:
        raise ValueError("no registry rows found under a 'Document' header")
    return rows


def resolve_paths(row: Row) -> list[Path]:
    found: list[Path] = []
    for rel in row.paths:
        if "<date>" in rel:
            pattern = Path(rel.replace("<date>", "*"))
            found.extend(sorted((REPO_ROOT / pattern.parent).glob(pattern.name)))
        else:
            found.append(REPO_ROOT / rel)
    return found


def anchor_present(lines: list[str], anchor: str) -> bool:
    if anchor.startswith("#"):
        return any(line.strip() == anchor for line in lines)
    return any(line.startswith(anchor) for line in lines)


def check_shape(rows: list[Row], read=None) -> list[str]:
    read = read or (lambda p: p.read_text(encoding="utf-8").splitlines())
    problems: list[str] = []
    for row in rows:
        if not row.pinned:
            problems.append(f"{row.document}: shape is unpinned, pin it in the commit that lands the rewrite")
            continue
        for path in resolve_paths(row):
            rel = path.relative_to(REPO_ROOT).as_posix() if path.is_absolute() else str(path)
            if not path.exists():
                problems.append(f"{rel}: named in the registry but not on disk")
                continue
            lines = read(path)
            for anchor in row.anchors:
                if not anchor_present(lines, anchor):
                    problems.append(f"{rel}: anchor {anchor!r} is in the registry but not in the file")
    return problems


def self_test(rows: list[Row]) -> int:
    """Each arm must go red under a mutation and green on the real tree."""
    failures = 0
    def real(p: Path) -> list[str]:
        return p.read_text(encoding="utf-8").splitlines()

    # Arm 1: a missing anchor is reported.
    def drop_first_heading(p: Path) -> list[str]:
        lines = real(p)
        return [line for line in lines if not line.startswith("## ")]

    if not check_shape(rows, read=drop_first_heading):
        print("SELF-TEST FAIL: --shape stayed green with every ## heading removed")
        failures += 1

    # Arm 2: an unpinned row is reported, even on the real tree.
    unpinned = parse_registry(
        "| Document | Job | Owner | Shape | Set by |\n|---|---|---|---|---|\n"
        "| `CLAUDE.md` | j | o | `unpinned` | s |\n"
    )
    if not check_shape(unpinned, read=real):
        print("SELF-TEST FAIL: --shape stayed green on an unpinned row")
        failures += 1

    print(f"self-test: 2 arms, {failures} failed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--shape", action="store_true", help="every registry anchor exists in its document (the default)")
    parser.add_argument("--self-test", action="store_true", help="prove each arm can fail")
    args = parser.parse_args(argv)

    rows = parse_registry(REGISTRY.read_text(encoding="utf-8"))
    if args.self_test:
        return self_test(rows)

    problems = check_shape(rows)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} problem(s) against {REGISTRY.relative_to(REPO_ROOT)}")
        return 1
    print(f"living documents: {len(rows)} rows, shape as registered")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
