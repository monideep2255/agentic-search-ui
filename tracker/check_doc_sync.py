#!/usr/bin/env python3
"""Check that the key documents agree with each other about the cards.

WHY THIS EXISTS

`tracker/check_doc_drift.py --check` proves each document's own structure and
`tracker/check_living_docs.py --shape` proves each registered document still
has its named sections. Neither compares one document with another. On
2026-10-06 cards 44 and 47 sat in the board's To do after they had merged,
and nothing noticed. The product owner, that day: "Documentation is the
foundation for success." This script is the cross-document check. It runs at
every `/phase-checkpoint` and before every push in `/ship`, and a finding
blocks the push. CI does not run it (the owner's choice, 2026-10-06).

WHAT IT PROVES, ONE NAMED RULE EACH

  card-in-one-place   A card in the board's To do or Build in progress
                      (`testing/UI_fix_plan.md`) is not also in "Waiting for
                      your retest" (`testing/UI_fixes_done.md`), and the
                      reverse. Exception: a retest row that marks the card
                      ", part" ("card 94, part"), the board's convention for
                      a card whose first part is live and the rest still to
                      do.
  retest-names-query  Every row of "Waiting for your retest" names at least
                      one query number that exists as a `### N.` heading in
                      `testing/Test_queries_and_workflows.md`, or says
                      plainly there is none ("none", "no query"). A number
                      with no heading is an error, and so is a row that
                      names neither.
  card-exists         Every card named in `testing/Board_plan.md`'s Waves
                      section and in `docs/build/Factory_onboarding.md`'s
                      card sections (each `## Card N` section and "Not yours
                      now") is somewhere: on the board, waiting for retest,
                      or in a done table of `testing/UI_fixes_done.md`.
  factory-lane        A card the brief gives Factory as its own (a `## Card
                      N` section) is not waiting for retest or done, unless
                      the retest row marks it ", part". And a To do card
                      whose Waiting on cell gives it to Factory has its own
                      `## Card N` section in the brief. A cell that says
                      "out of Factory's lane" or "not Factory's" does not
                      give it to Factory.
  handoff-agrees      Every card `HANDOFF.md` names is on the board, waiting
                      for retest, or done; and the develop commit it states,
                      if any, is an ancestor of HEAD
                      (`git merge-base --is-ancestor`).
  registry-paths      Every path in backticks in the Document column of
                      `tracker/Living_documents.md` exists.

HOW IT READS

Tables are found by their section heading and their header row's text, never
by line number. A card number is the first cell of a board row (`| 56 |`), a
list in the Build in progress Cards column (`2, 50, 5`), or, in prose and
other cells, "card 56", "cards 43 and 43b", "cards 79, 80 and 85", "cards 79
to 84". A number that is not written as a card reference (a pull request
`#190`, a query `106`, an item `12.3`) is never read as a card.

The rules are conservative on purpose: a false alarm every session teaches
people to ignore the check, while a miss loses only that one case. When a
cell's meaning is unclear the check reads nothing from it.

OUTPUT AND EXIT CODES

Each finding prints as `file:line: rule: what disagrees, and the fix`.
Exit 0 when the documents agree, 1 on any finding, 2 when the check cannot
run (a document, section or table it reads is missing, or git cannot be
asked). Exit 2 is never a pass.

  python3 tracker/check_doc_sync.py                  check the real documents
  python3 tracker/check_doc_sync.py --self-test      the readers, case by case
  python3 tracker/check_doc_sync.py --mutation-test  each rule can fail

`--mutation-test` builds a small set of documents that agree, proves it
passes with zero findings, then breaks one agreement per case and proves the
named rule reports it. It never reads the real documents, so it passes on any
day.

WHAT IT DOES NOT CHECK

  - Whether a card's status words agree with its detail section or with its
    query's text. Only where the card sits is compared.
  - "Card" references in any document other than the seven read here.
  - A card the Factory brief mentions only in passing outside its card
    sections, and the brief's ordering line ("in this order: 43b, then
    47").
  - Whether a retest row's query actually tests what the row describes.
  - Any count, or any date against the calendar.

Stdlib only. Runs from anywhere: paths resolve against the repository root.

Depends on:
    - git, for the handoff commit (rule handoff-agrees)

Reads:
    - testing/UI_fix_plan.md, testing/UI_fixes_done.md,
      testing/Test_queries_and_workflows.md, testing/Board_plan.md,
      docs/build/Factory_onboarding.md, HANDOFF.md,
      tracker/Living_documents.md

Writes:
    - nothing
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

BOARD = "testing/UI_fix_plan.md"
DONE = "testing/UI_fixes_done.md"
QUERIES = "testing/Test_queries_and_workflows.md"
BOARD_PLAN = "testing/Board_plan.md"
FACTORY = "docs/build/Factory_onboarding.md"
HANDOFF = "HANDOFF.md"
REGISTRY = "tracker/Living_documents.md"
DOCUMENTS = (BOARD, DONE, QUERIES, BOARD_PLAN, FACTORY, HANDOFF, REGISTRY)

TODO_HEADING = "## To do"
IN_PROGRESS_HEADING = "## Build in progress"
WAITING_HEADING = "## Waiting for your retest"
DONE_HEADINGS = ("## Done features at a glance", "## What is done, in summary")
WAVES_HEADING = "## Waves"
NOT_YOURS_HEADING = "## Not yours now"

CARD = r"\d+[a-z]?"
CARD_SHAPE_RE = re.compile(rf"^{CARD}$")
# "card 56", "cards 43 and 43b", "cards 79, 80 and 85", "cards 79 to 84".
# The list may not run on into ".5" (a phase such as 8.10) or a word.
CARD_REF_RE = re.compile(
    rf"\b[Cc]ards?\s+({CARD}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s+to\s+){CARD})*)(?!\.\d)(?![\w])"
)
LIST_SEP_RE = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s+to\s+")
PURE_CARD_LIST_RE = re.compile(rf"^\s*{CARD}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+){CARD})*\s*$")
PART_AFTER_RE = re.compile(r"^\s*,?\s*part\b")
LEADING_CARD_RE = re.compile(rf"^\s*({CARD})(?![\w.])")
QUERY_HEADING_RE = re.compile(r"^###\s+(\d+)\.")
NO_QUERY_RE = re.compile(r"\bnone\b|\bno query\b", re.IGNORECASE)
QUERY_RANGE_RE = re.compile(r"\b(\d+)\s+to\s+(\d+)\b")
QUERY_NUMBER_RE = re.compile(r"(?<![\w.#-])(\d+)(?![\w.-])")
QUOTED_RE = re.compile(r"\"[^\"]*\"|“[^”]*”|`[^`]*`")
FACTORY_CARD_HEADING_RE = re.compile(rf"^##\s+Card\s+({CARD})\b")
FACTORY_NAMED_RE = re.compile(r"\bFactory\b")
FACTORY_NOT_RE = re.compile(r"out of Factory's lane|not Factory's|not yours", re.IGNORECASE)
HANDOFF_DEVELOP_RE = re.compile(r"\b[Dd]evelop\b[^`\n]{0,20}?`([0-9a-f]{7,40})`")
BACKTICK_RE = re.compile(r"`([^`]+)`")
ROW_RE = re.compile(r"^\|(.*)\|\s*$")


class CannotRun(Exception):
    """A document, section or table the check reads is missing."""


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    message: str

    def format(self) -> str:
        return f"{self.file}:{self.line}: {self.rule}: {self.message}"


@dataclass
class Table:
    header: list[str]
    rows: list[tuple[int, list[str]]]  # (1-based line number, cells)

    def column(self, name: str) -> int | None:
        for i, cell in enumerate(self.header):
            if cell.strip().lower() == name.lower():
                return i
        return None


@dataclass
class CardRef:
    card: str
    part: bool = False


@dataclass
class Located:
    """Where each card sits, with the line that puts it there."""
    todo: dict[str, int] = field(default_factory=dict)
    in_progress: dict[str, int] = field(default_factory=dict)
    waiting: dict[str, tuple[int, bool]] = field(default_factory=dict)  # card -> (line, part)
    done: dict[str, int] = field(default_factory=dict)
    done_part: set[str] = field(default_factory=set)  # "card 94, part" in a done table

    def known(self, card: str) -> bool:
        return any(card in where for where in (self.todo, self.in_progress, self.waiting, self.done, self.done_part))


# --------------------------------------------------------------------------
# Readers
# --------------------------------------------------------------------------


def split_cells(line: str) -> list[str] | None:
    m = ROW_RE.match(line.strip())
    if not m:
        return None
    return [c.strip() for c in re.split(r"(?<!\\)\|", m.group(1))]


def is_separator(cells: list[str]) -> bool:
    return all(set(c.replace(":", "")) <= {"-"} and c for c in cells)


def section_lines(lines: list[str], heading: str) -> tuple[int, int]:
    """Return (start, end) indexes of the body under an exact heading, up to
    the next heading of the same or a higher level. Raises CannotRun."""
    level = len(heading) - len(heading.lstrip("#"))
    for i, line in enumerate(lines):
        if line.strip() == heading:
            end = len(lines)
            for j in range(i + 1, len(lines)):
                s = lines[j]
                if s.startswith("#"):
                    lvl = len(s) - len(s.lstrip("#"))
                    if lvl <= level and s[lvl:lvl + 1] == " ":
                        end = j
                        break
            return i + 1, end
    raise CannotRun(f"heading {heading!r} not found")


def tables_in(lines: list[str], start: int, end: int) -> list[Table]:
    tables: list[Table] = []
    i = start
    while i < end:
        cells = split_cells(lines[i])
        if cells is not None and i + 1 < end:
            sep = split_cells(lines[i + 1])
            if sep is not None and is_separator(sep):
                table = Table(header=cells, rows=[])
                j = i + 2
                while j < end:
                    row = split_cells(lines[j])
                    if row is None:
                        break
                    table.rows.append((j + 1, row))
                    j += 1
                tables.append(table)
                i = j
                continue
        i += 1
    return tables


def card_refs(text: str) -> list[CardRef]:
    """Every card a piece of prose names, with its ", part" marker."""
    refs: list[CardRef] = []
    for m in CARD_REF_RE.finditer(text):
        body = m.group(1)
        base = m.start(1)
        tokens = list(re.finditer(CARD, body))
        seps = LIST_SEP_RE.findall(body)
        # Expand "79 to 84" into every card between.
        expanded: list[tuple[str, int]] = []
        for k, tok in enumerate(tokens):
            expanded.append((tok.group(0), base + tok.end()))
            if k < len(seps) and seps[k].strip() == "to" and k + 1 < len(tokens):
                lo, hi = tok.group(0), tokens[k + 1].group(0)
                if lo.isdigit() and hi.isdigit() and 0 < int(hi) - int(lo) <= 50:
                    expanded.extend((str(n), -1) for n in range(int(lo) + 1, int(hi)))
        for card, after in expanded:
            part = after >= 0 and bool(PART_AFTER_RE.match(text[after:]))
            refs.append(CardRef(card, part))
    return refs


def leading_cards(cell: str) -> list[str]:
    """Card numbers that lead each comma segment of a Cards cell, such as
    "94 note, 91 wording, 77" or "33 (G-006)". Prose segments give none."""
    out: list[str] = []
    for segment in cell.split(","):
        m = LEADING_CARD_RE.match(segment)
        if m:
            out.append(m.group(1))
    return out


def query_numbers(cell: str) -> tuple[list[int], bool]:
    """Query numbers a Queries cell names, and whether it says there is
    none. Quoted text and code spans are dropped first, so a question's own
    digits ("BRCA1", "s3") are never read as query numbers."""
    text = QUOTED_RE.sub(" ", cell)
    says_none = bool(NO_QUERY_RE.search(text))
    numbers: list[int] = []
    for m in QUERY_RANGE_RE.finditer(text):
        lo, hi = int(m.group(1)), int(m.group(2))
        if 0 < hi - lo <= 50:
            numbers.extend(range(lo, hi + 1))
    text = QUERY_RANGE_RE.sub(" ", text)
    numbers.extend(int(m.group(1)) for m in QUERY_NUMBER_RE.finditer(text))
    return numbers, says_none


class Docs:
    """The documents, as lines, keyed by repository-relative path."""

    def __init__(self, texts: dict[str, str]) -> None:
        self.lines = {path: text.splitlines() for path, text in texts.items()}

    def get(self, path: str) -> list[str]:
        if path not in self.lines:
            raise CannotRun(f"{path} could not be read")
        return self.lines[path]

    @classmethod
    def load(cls, root: Path) -> Docs:
        texts: dict[str, str] = {}
        for rel in DOCUMENTS:
            p = root / rel
            if not p.is_file():
                raise CannotRun(f"{rel} is not on disk")
            texts[rel] = p.read_text(encoding="utf-8")
        return cls(texts)


def locate_cards(docs: Docs) -> Located:
    loc = Located()
    board = docs.get(BOARD)
    start, end = section_lines(board, TODO_HEADING)
    todo_tables = [t for t in tables_in(board, start, end) if t.header and t.header[0] == "#"]
    if not todo_tables:
        raise CannotRun(f"{BOARD}: no table with a '#' column under {TODO_HEADING!r}")
    for table in todo_tables:
        for line, cells in table.rows:
            if CARD_SHAPE_RE.match(cells[0]):
                loc.todo.setdefault(cells[0], line)

    start, end = section_lines(board, IN_PROGRESS_HEADING)
    for table in tables_in(board, start, end):
        col = table.column("Cards")
        for line, cells in table.rows:
            if table.header[0] == "#" and CARD_SHAPE_RE.match(cells[0]):
                loc.in_progress.setdefault(cells[0], line)
            elif col is not None and col < len(cells) and PURE_CARD_LIST_RE.match(cells[col]):
                for card in re.findall(CARD, cells[col]):
                    loc.in_progress.setdefault(card, line)

    for line, ref in waiting_rows_cards(docs):
        prev = loc.waiting.get(ref.card)
        if prev is None or (prev[1] and not ref.part):
            loc.waiting[ref.card] = (line, ref.part)

    done = docs.get(DONE)
    for heading in DONE_HEADINGS:
        start, end = section_lines(done, heading)
        for table in tables_in(done, start, end):
            col = table.column("Item")
            col = 0 if col is None else col
            for line, cells in table.rows:
                if col < len(cells):
                    for ref in card_refs(cells[col]):
                        if ref.part:
                            loc.done_part.add(ref.card)
                        else:
                            loc.done.setdefault(ref.card, line)
    return loc


def waiting_table(docs: Docs) -> Table:
    done = docs.get(DONE)
    start, end = section_lines(done, WAITING_HEADING)
    for table in tables_in(done, start, end):
        if table.column("Item") is not None and table.column("Queries") is not None:
            return table
    raise CannotRun(f"{DONE}: no table with Item and Queries columns under {WAITING_HEADING!r}")


def waiting_rows_cards(docs: Docs) -> list[tuple[int, CardRef]]:
    table = waiting_table(docs)
    col = table.column("Item")
    out: list[tuple[int, CardRef]] = []
    for line, cells in table.rows:
        if col is not None and col < len(cells):
            out.extend((line, ref) for ref in card_refs(cells[col]))
    return out


def factory_sections(docs: Docs) -> tuple[dict[str, int], list[tuple[int, str, bool]]]:
    """The brief's own cards (`## Card N` headings, card -> line) and every
    line of its card sections and its "Not yours now" section, each tagged
    True when it is in "Not yours now"."""
    lines = docs.get(FACTORY)
    own: dict[str, int] = {}
    body: list[tuple[int, str, bool]] = []
    section: str | None = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            m = FACTORY_CARD_HEADING_RE.match(line)
            section = "card" if m else ("not-yours" if line.strip() == NOT_YOURS_HEADING else None)
            if m:
                own.setdefault(m.group(1), i + 1)
        if section:
            body.append((i + 1, line, section == "not-yours"))
    if not own and not body:
        raise CannotRun(f"{FACTORY}: no '## Card N' section and no {NOT_YOURS_HEADING!r}")
    return own, body


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


def rule_card_in_one_place(docs: Docs, loc: Located) -> list[Finding]:
    findings: list[Finding] = []
    for where, cards in (("To do", loc.todo), ("Build in progress", loc.in_progress)):
        for card, line in cards.items():
            hit = loc.waiting.get(card)
            if hit and not hit[1]:
                findings.append(Finding(
                    BOARD, line, "card-in-one-place",
                    f"card {card} is in {where} and also in \"Waiting for your retest\" "
                    f"({DONE}:{hit[0]}). Take it off the board if it is live, or out of the "
                    "retest list if it is still being built; mark the retest row \"card "
                    f"{card}, part\" if only part of it is live",
                ))
    return findings


def rule_retest_names_query(docs: Docs) -> list[Finding]:
    table = waiting_table(docs)
    col = table.column("Queries")
    existing = {int(m.group(1)) for line in docs.get(QUERIES) if (m := QUERY_HEADING_RE.match(line))}
    findings: list[Finding] = []
    for line, cells in table.rows:
        cell = cells[col] if col is not None and col < len(cells) else ""
        numbers, says_none = query_numbers(cell)
        missing = sorted({n for n in numbers if n not in existing})
        if missing:
            findings.append(Finding(
                DONE, line, "retest-names-query",
                f"query {', '.join(map(str, missing))} has no \"### N.\" heading in {QUERIES}. "
                "Correct the number, or add the query to the test queries document",
            ))
        elif not numbers and not says_none:
            findings.append(Finding(
                DONE, line, "retest-names-query",
                f"the Queries cell names no query number and does not say there is none "
                f"({cell[:60]!r}). Name the query from {QUERIES}, add one, or write \"none\"",
            ))
    return findings


def rule_card_exists(docs: Docs, loc: Located) -> list[Finding]:
    named: list[tuple[str, int, str]] = []  # (file, line, card)
    plan = docs.get(BOARD_PLAN)
    start, end = section_lines(plan, WAVES_HEADING)
    for i in range(start, end):
        line = plan[i]
        named.extend((BOARD_PLAN, i + 1, ref.card) for ref in card_refs(line))
    for table in tables_in(plan, start, end):
        col = table.column("Cards")
        if col is None:
            continue
        for line, cells in table.rows:
            if col < len(cells):
                named.extend((BOARD_PLAN, line, card) for card in leading_cards(cells[col]))

    own, body = factory_sections(docs)
    named.extend((FACTORY, line, card) for card, line in own.items())
    for line, text, not_yours in body:
        named.extend((FACTORY, line, ref.card) for ref in card_refs(text))
        cells = split_cells(text)
        # "Not yours now" rows name their cards bare in the Card column: "18, 23".
        if not_yours and cells and PURE_CARD_LIST_RE.match(cells[0]):
            named.extend((FACTORY, line, card) for card in re.findall(CARD, cells[0]))

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for file, line, card in named:
        if loc.known(card) or (file, card) in seen:
            continue
        seen.add((file, card))
        findings.append(Finding(
            file, line, "card-exists",
            f"card {card} is on no list: not in the board's To do or Build in progress, "
            f"not in \"Waiting for your retest\", not in a done table of {DONE}. Correct the "
            "number, or put the card on the board",
        ))
    return findings


def rule_factory_lane(docs: Docs, loc: Located) -> list[Finding]:
    own, _ = factory_sections(docs)
    findings: list[Finding] = []
    for card, line in own.items():
        hit = loc.waiting.get(card)
        if hit and not hit[1]:
            findings.append(Finding(
                FACTORY, line, "factory-lane",
                f"card {card} is still one of Factory's cards here, but it is built and "
                f"waiting for retest ({DONE}:{hit[0]}). Take its section out of Factory's "
                "card list and update the order line",
            ))
        elif card in loc.done and not hit:
            findings.append(Finding(
                FACTORY, line, "factory-lane",
                f"card {card} is still one of Factory's cards here, but it is done "
                f"({DONE}:{loc.done[card]}). Take its section out of Factory's card list",
            ))

    board = docs.get(BOARD)
    start, end = section_lines(board, TODO_HEADING)
    for table in tables_in(board, start, end):
        col = table.column("Waiting on")
        if table.header[0] != "#" or col is None:
            continue
        for line, cells in table.rows:
            if not CARD_SHAPE_RE.match(cells[0]) or col >= len(cells):
                continue
            cell = cells[col]
            if FACTORY_NAMED_RE.search(cell) and not FACTORY_NOT_RE.search(cell) and cells[0] not in own:
                findings.append(Finding(
                    BOARD, line, "factory-lane",
                    f"card {cells[0]}'s Waiting on cell gives it to Factory, but "
                    f"{FACTORY} has no \"## Card {cells[0]}\" section. Add the card to the "
                    "brief, or say on the board that it is not Factory's",
                ))
    return findings


GitAncestor = Callable[[str], bool | None]


def git_is_ancestor(sha: str) -> bool | None:
    """True or False from `git merge-base --is-ancestor sha HEAD`; None when
    git does not know the commit. Raises CannotRun when git cannot run."""
    try:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CannotRun(f"git could not run: {exc}") from exc
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def rule_handoff_agrees(docs: Docs, loc: Located, is_ancestor: GitAncestor) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for i, line in enumerate(docs.get(HANDOFF)):
        for ref in card_refs(line):
            if loc.known(ref.card) or ref.card in seen:
                continue
            seen.add(ref.card)
            findings.append(Finding(
                HANDOFF, i + 1, "handoff-agrees",
                f"card {ref.card} is on no list: not on the board, not waiting for retest, "
                "not done. Correct the number, or put the card on the board",
            ))
        for m in HANDOFF_DEVELOP_RE.finditer(line):
            sha = m.group(1)
            verdict = is_ancestor(sha)
            if verdict is None:
                findings.append(Finding(
                    HANDOFF, i + 1, "handoff-agrees",
                    f"develop commit {sha} is not a commit in this repository. "
                    "Write the commit develop is at",
                ))
            elif not verdict:
                findings.append(Finding(
                    HANDOFF, i + 1, "handoff-agrees",
                    f"develop commit {sha} is not an ancestor of HEAD, so the handoff "
                    "describes a develop this checkout never had. Write the commit develop is at",
                ))
    return findings


def rule_registry_paths(docs: Docs, exists: Callable[[str], bool]) -> list[Finding]:
    findings: list[Finding] = []
    lines = docs.get(REGISTRY)
    start, end = section_lines(lines, "## The registry")
    tables = [t for t in tables_in(lines, start, end) if t.column("Document") is not None]
    if not tables:
        raise CannotRun(f"{REGISTRY}: no table with a Document column under '## The registry'")
    for table in tables:
        col = table.column("Document")
        for line, cells in table.rows:
            for path in BACKTICK_RE.findall(cells[col] if col < len(cells) else ""):
                if not exists(path):
                    findings.append(Finding(
                        REGISTRY, line, "registry-paths",
                        f"`{path}` is registered but not on disk. Correct the path, or "
                        "remove the row with a DECISIONS.md row saying why",
                    ))
    return findings


def path_exists(rel: str) -> bool:
    if "<date>" in rel:
        pattern = Path(rel.replace("<date>", "*"))
        return any((REPO_ROOT / pattern.parent).glob(pattern.name))
    return (REPO_ROOT / rel).exists()


def run_rules(docs: Docs, is_ancestor: GitAncestor, exists: Callable[[str], bool]) -> list[Finding]:
    loc = locate_cards(docs)
    findings: list[Finding] = []
    findings += rule_card_in_one_place(docs, loc)
    findings += rule_retest_names_query(docs)
    findings += rule_card_exists(docs, loc)
    findings += rule_factory_lane(docs, loc)
    findings += rule_handoff_agrees(docs, loc, is_ancestor)
    findings += rule_registry_paths(docs, exists)
    return findings


# --------------------------------------------------------------------------
# Self-test: the readers, case by case
# --------------------------------------------------------------------------


def _self_test_cases() -> list[tuple[str, object, object]]:
    def refs(text: str) -> list[tuple[str, bool]]:
        return [(r.card, r.part) for r in card_refs(text)]

    return [
        ("one card", refs("see card 56 first"), [("56", False)]),
        ("two cards with a letter", refs("cards 43 and 43b (#181)"), [("43", False), ("43b", False)]),
        ("a list with part on the last", refs("cards 79, 80 and 85, part (#167)"),
         [("79", False), ("80", False), ("85", True)]),
        ("one card, part", refs("card 94, part (#158)"), [("94", True)]),
        ("a range", refs("Cards 79 to 82"), [("79", False), ("80", False), ("81", False), ("82", False)]),
        ("possessive and sentence end", refs("card 99's measurement. Then card 56."), [("99", False), ("56", False)]),
        ("a phase number is not a card", refs("phase 8.10 and item 12.3"), []),
        ("the list stops at a word", refs("card 46 and decision D1"), [("46", False)]),
        ("a pull request number is not a card", refs("(#190, built by Factory)"), []),
        ("leading cards", leading_cards("94 note, 91 wording, 77"), ["94", "91", "77"]),
        ("leading cards skip prose", leading_cards("46, the hidden note"), ["46"]),
        ("leading card with a bracket", leading_cards("15, 74, 33 (G-006)"), ["15", "74", "33"]),
        ("queries, a list", query_numbers("75, 68"), ([75, 68], False)),
        ("queries, a range", query_numbers("33 to 37"), ([33, 34, 35, 36, 37], False)),
        ("queries, none", query_numbers("none; `s3` and `s3 mcp`"), ([], True)),
        ("queries, quoted digits ignored", query_numbers("the answer to \"What does BRCA1 do?\""), ([], False)),
        ("queries, a number beside a quote", query_numbers("25, and \"Any trials for GERD?\" in 76"), ([25, 76], False)),
        ("queries, none yet", query_numbers("none yet"), ([], True)),
        ("queries, a date is not a query", query_numbers("checked 2026-10-06"), ([], False)),
    ]


def run_self_test() -> int:
    failures = 0
    cases = _self_test_cases()
    for name, actual, expected in cases:
        ok = actual == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" (expected {expected!r}, got {actual!r})"))
        failures += 0 if ok else 1
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {len(cases)} self-test cases, {failures} failed")
    return failures


# --------------------------------------------------------------------------
# Mutation test: a set of documents that agree, then one break per rule
# --------------------------------------------------------------------------

GOLDEN: dict[str, str] = {
    BOARD: """# UI fix plan

## To do

| # | Feature, in plain words | Item | Waiting on |
|---|---|---|---|
| 56 | A question about SARS-CoV-2 | diagnosis | The lead |
| 94 | Isolates show their genes | G-035 | Part live, in Retest. Still open: the place column |
| 24 | Where the toggle goes | 8.4 branch | Factory's next screen card |
| 18 | Record lists | loose ends | Out of Factory's lane: the lead's lane |

### Set 11, still open

| # | Your feedback | Status | Where it stands |
|---|---|---|---|
| 11.11 | Use the reference prototype | Queued | Tenth |

## Build in progress

| What | Cards | Where |
|---|---|---|
| Phase 8.7 | 2, 50 | `tracker/phase_8.7.md` |
| Two reviews of the harness | the product owner, 2026-09-25 | reports |

## Retest

Moved to `testing/UI_fixes_done.md`.
""",
    DONE: """# UI fixes done

## Waiting for your retest

| # | What to check, in plain words | Item | Queries | Retest |
|---|---|---|---|---|
| 1 | A long name wraps | cards 43 and 43b (#181) | 1 | Waiting for your verdict |
| 2 | Isolates show genes | card 94, part (#158) | 2 to 3 | Waiting for your verdict |
| 3 | The design file | card 47 (#188) | none, a design file | Waiting for your verdict |
| 4 | A one-word question is asked back | 12.3 | 3 | Waiting for your verdict |

## Done features at a glance

| Item | What you see | Status | Test query |
|---|---|---|---|
| 1.1 | Remove the guest limit | Approved | 1 |
| card 62 | Install works first time | Approved | 3 |

## What is done, in summary

### 3. Done

| Feature, in plain words | Item | Where it stands |
|---|---|---|
| The trust line | card 8 | Fixed |
""",
    QUERIES: """# Test queries and workflows

## 1. Basic search

### 1. A first search

### 2. Plain language

### 3. Isolates
""",
    BOARD_PLAN: """# Board plan

## Waves

Wave 0, running now: root cause 1 (cards 56, 94).

| Build | Cards | Size |
|---|---|---|
| Records never dropped | 94 colistin, 2 | S |
| The page batch | 47, 43b, the hidden note | S |

- Card 50, the speed work.

## How each change is checked

Card 7777 here is outside the waves and never read.
""",
    FACTORY: """# Factory onboarding

## How you work here

Card 8888 here is outside the card sections and never read.

## Card 24: where the toggle goes

Leave card 62's fix alone.

## Not yours now

| Card | Why it waits |
|---|---|
| 18 | The lead's lane |
""",
    HANDOFF: """# Handoff

## What is live

- Develop: `abc1234`, the merge of #175.
- Factory's lane is cards 24 and 18.
""",
    REGISTRY: """# Living documents

## The registry

| Document | Job | Owner | Shape | Set by |
|---|---|---|---|---|
| `HANDOFF.md` | j | o | `## What is live` | s |
| `CLAUDE.md` and `AGENTS.md` | j | o | `## Skills` | s |
""",
}

GOLDEN_COMMITS = {"abc1234": True, "def5678": False}
GOLDEN_PATHS = {"HANDOFF.md", "CLAUDE.md", "AGENTS.md"}


def _golden_run(texts: dict[str, str]) -> list[Finding]:
    return run_rules(
        Docs(texts),
        is_ancestor=lambda sha: GOLDEN_COMMITS.get(sha),
        exists=lambda p: p in GOLDEN_PATHS,
    )


def _mutate(path: str, old: str, new: str) -> dict[str, str]:
    texts = dict(GOLDEN)
    if old not in texts[path]:
        raise AssertionError(f"mutation fixture bug: {old!r} not in {path}")
    texts[path] = texts[path].replace(old, new, 1)
    return texts


def _mutations() -> list[tuple[str, dict[str, str], str]]:
    """(name, mutated documents, the rule that must report it)."""
    return [
        ("a To do card also waiting for retest",
         _mutate(DONE, "| card 47 (#188) |", "| cards 47 and 56 (#188) |"), "card-in-one-place"),
        ("a Build in progress card also waiting for retest",
         _mutate(DONE, "| card 47 (#188) |", "| cards 47 and 50 (#188) |"), "card-in-one-place"),
        ("a part card loses its part marker",
         _mutate(DONE, "card 94, part (#158)", "card 94 (#158)"), "card-in-one-place"),
        ("a retest row names a query with no heading",
         _mutate(DONE, "| 2 to 3 |", "| 2 to 4 |"), "retest-names-query"),
        ("a retest row names no query and not none",
         _mutate(DONE, "| none, a design file |", "| the design file |"), "retest-names-query"),
        ("a wave names a card on no list",
         _mutate(BOARD_PLAN, "| 47, 43b, the hidden note |", "| 47, 43b, 61 |"), "card-exists"),
        ("a wave sentence names a card on no list",
         _mutate(BOARD_PLAN, "- Card 50, the speed work.", "- Card 51, the speed work."), "card-exists"),
        ("the Factory brief names a card on no list",
         _mutate(FACTORY, "| 18 | The lead's lane |", "| 19 | The lead's lane |"), "card-exists"),
        ("a Factory card section for a card waiting for retest",
         _mutate(FACTORY, "## Not yours now", "## Card 47: the prototype\n\n## Not yours now"), "factory-lane"),
        ("a Factory card section for a done card",
         _mutate(FACTORY, "## Not yours now", "## Card 8: the trust line\n\n## Not yours now"), "factory-lane"),
        ("a board card given to Factory with no section in the brief",
         _mutate(BOARD, "| The lead |", "| Factory's next item |"), "factory-lane"),
        ("the handoff names a card on no list",
         _mutate(HANDOFF, "cards 24 and 18", "cards 24 and 17"), "handoff-agrees"),
        ("the handoff's develop commit is not an ancestor",
         _mutate(HANDOFF, "`abc1234`", "`def5678`"), "handoff-agrees"),
        ("the handoff's develop commit is unknown",
         _mutate(HANDOFF, "`abc1234`", "`0000000`"), "handoff-agrees"),
        ("a registered path is not on disk",
         _mutate(REGISTRY, "`AGENTS.md`", "`AGENT.md`"), "registry-paths"),
    ]


def _cannot_run_cases() -> list[tuple[str, dict[str, str]]]:
    return [
        ("the retest section is missing", _mutate(DONE, WAITING_HEADING, "## Somewhere else")),
        ("the To do section is missing", _mutate(BOARD, TODO_HEADING, "## Not started")),
        ("the Waves section is missing", _mutate(BOARD_PLAN, WAVES_HEADING, "## Order")),
    ]


def run_mutation_test() -> int:
    failures = 0
    base = _golden_run(dict(GOLDEN))
    if base:
        print("FAIL  golden documents, documents that agree must give zero findings")
        for f in base:
            print(f"        {f.format()}")
        failures += 1
    else:
        print("PASS  golden documents agree (0 findings)")

    for name, texts, rule in _mutations():
        findings = _golden_run(texts)
        caught = [f for f in findings if f.rule == rule]
        others = [f for f in findings if f.rule != rule]
        ok = bool(caught) and not others
        print(f"{'PASS' if ok else 'FAIL'}  {name} (rule {rule}, "
              f"{'caught' if caught else 'NOT caught'}{', other rules fired' if others else ''})")
        if not ok:
            failures += 1
            for f in findings[:4]:
                print(f"        {f.format()}")

    for name, texts in _cannot_run_cases():
        try:
            _golden_run(texts)
        except CannotRun:
            print(f"PASS  {name} (cannot run, exit 2)")
            continue
        print(f"FAIL  {name}: the check ran over a missing section instead of exiting 2")
        failures += 1

    total = 1 + len(_mutations()) + len(_cannot_run_cases())
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {total} mutation cases, {failures} failed")
    return failures


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return 1 if run_self_test() else 0
    if "--mutation-test" in argv:
        return 1 if run_mutation_test() else 0
    unknown = [a for a in argv if a not in ("--check",)]
    if unknown:
        print(f"unknown argument(s): {' '.join(unknown)}", file=sys.stderr)
        return 2
    try:
        findings = run_rules(Docs.load(REPO_ROOT), git_is_ancestor, path_exists)
    except CannotRun as exc:
        print(f"cannot run: {exc}")
        return 2
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"error: {len(findings)} finding(s): the documents disagree")
        return 1
    print("ok: the board, the done file, the test queries, the board plan, the Factory brief, "
          "the handoff and the registry agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
