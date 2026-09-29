#!/usr/bin/env python3
"""Check that what System 3's web app says about itself is still true.

The About, Architecture, Integrations and Home screens, the onboarding tour
and the refusal banner state numbers, names, limits and capabilities: how
big the graph is, which tools exist, how long a call may take, which step
asks which model. Each of those has ONE source in the backend, the data or
the deployment. When the backend changes and the page does not, a person
reading the page is told something that is no longer so. This script finds
that, and it finds the same drift in the documents that restate the facts.

The product owner's request of 2026-09-26: before or after anything is
deployed, check that everything the UI says, and every downstream document,
reflects the current system. It runs as a step of `/verify`
(`.claude/skills/verify/SKILL.md`).

HOW IT WORKS

The registry, `facts_registry.py` beside this file, lists every fact. Each
fact names:

  - how its truth is computed from its one source, never from a second copy.
    Python sources are read with `ast`, never imported, so no code under
    check runs, no environment variable or secret is read, and a checkout
    without installed dependencies still checks. Documents and data files are
    read as text or JSON. The one process the script starts is
    `git rev-parse`, to find the main checkout when `reference/` does not
    resolve in an agent worktree.
  - every place a screen states it, as a file and a pattern that captures
    what the page says. The stated value is read out of the page's source
    each run, so an edited page is checked as edited.
  - every downstream document that restates it, checked the same way.

WHAT A PLACE IS READ FROM, since card 53's fix round (2026-09-29): the text
a person reads, never the raw file. Comments, docstrings and a constant
nothing uses are blanked first (`visible`), so a sentence kept in a comment
cannot vouch for a page that says something else. Four rules then make a
place FAIL rather than pass on part of what it says:

  - WHOLE SENTENCES. A place's match must cover every sentence it touches,
    whole, so a clause added before or after the guarded words, or a
    negation anywhere in the sentence, fails (`sentence_problem`). A place
    marked `block` reads fields out of a structure and is exempt; the prose
    inside such a structure is guarded only where a place of its own names
    it.
  - EVERY WORD READ. A list of names (APIs, surfaces, tools, modes) must
    consist of known names and a closed set of connective words; "not",
    "never" or "excluded" is a word the registry cannot read, so it fails.
  - EXACT COUNT. Each place says how many times its statement appears. One
    card of five dropping out is a FAIL, never a smaller count.
  - GONE IS FAIL. A statement that no longer matches, or reads as a wording
    the registry does not know, is a FAIL, not an ERROR the run shrugs at.

WHY THE REGISTRY IS PYTHON RATHER THAN JSON OR YAML. A fact's truth is
rarely a plain lookup: a count is the length of a `Literal`, "115M" is a
rounding of 115,406,761, "which steps ask a model" is a walk of the call
graph. A data format would need a small language for those; Python already
is one, and ruff checks it.

WHAT LIVES WHERE, stated as it is rather than as a wish. This file holds the
engine: the readers for constants, `Literal`s and fields, the comparisons,
the call graph, the verdicts and the self-test. The registry holds the fact
declarations AND the small functions that compute a fact's truth or parse
what a place says (tool layers, API families, the seed match, and so on).
So an edit to the registry can change how that fact is decided. It gets the
same review as an edit here, and `--self-test` must pass after it.

THE VERDICTS, the same three words `/verify` uses, plus one for the tool.
Only PASS passes this step: any line this script prints that is not PASS
fails `/verify`, a GAP included. That is stricter than the `/verify` report
as a whole, where a GAP line the model writes, for a screen with no design
or an unread deploy record, names a gap without failing the verdict.

  PASS   what the place says matches the source.
  FAIL   it does not: the page or document is stale, or the place no longer
         says what the registry reads there (see the four rules above).
  GAP    the source could not be read here, for example the data-engineering
         repository behind `reference/` is not checked out. The place is
         unchecked, so the run does not pass.
  ERROR  the registry no longer matches the CODE, or a source cannot be read
         without running it: a constant is gone or is not a literal, a
         function the truth reads has moved. The registry must be updated,
         which is the point: a fact cannot silently stop being checked. When
         a fact's truth cannot be computed, every one of its places gets its
         own ERROR line, so none is silently dropped.

EXIT CODES: 0 every place PASS; 1 at least one FAIL; 2 at least one ERROR,
or bad arguments, or a Python older than 3.11; 3 at least one GAP and no
FAIL or ERROR. Any exit but 0 fails `/verify`.

WHAT THIS SCRIPT DOES NOT CHECK, stated so a gap is arguable:

  - Anything the deployment decides at run time: the model a tier is set to
    on develop, `GRAPH_SNAPSHOT_VERSION`, `CLASSIFIER_PROVIDER`, the daily
    caps. Those are environment variables on the host, and reading them needs
    the host's credentials. The code default is checked instead, and the
    report names the difference.
  - Whether a command on the Integrations page runs. Another audit owns that,
    and `/verify` leaves a marked place for its smoke script.
  - Facts the page reads from the API at run time, such as the search limit
    (`GET /v1/allowance`) and the scientist's name. They cannot go stale.
  - Prose it has no pattern for. A new sentence stating a new number is not
    checked until the registry names it. Some guarded sentences are pinned
    word for word rather than computed (the tier cards' kinds, the layer 2
    walk's "fetched while you wait"): an edit to them fails, which sends
    the change to review, but their words are not derived from code.
  - Conditions a static read cannot prove. The layer 3 facts read the
    branches, the symbol test and the rs id cap in `core/graph.py`, but not
    what a model will decide on a given question.
  - The live graph's counts. The graph owner's reference document is the
    source; querying the graph would need its credential.
  - Calls the static call graph cannot see: a function reached through a
    dictionary, `getattr` or a callback stored on an object.

USAGE

  check_facts.py                  every check; prints FAIL, GAP, ERROR and a summary
  check_facts.py --all            also prints every PASS line
  check_facts.py --map            the downstream map: each fact, its source, every place
  check_facts.py --from PATH      only the facts computed from PATH, for "what does
                                  this change touch" (combine with --map); a file
                                  no fact reads prints so and exits 0, and a
                                  path that does not exist is refused, exit 2
  check_facts.py --reference DIR  the data-engineering repository, when reference/
                                  does not resolve (an agent worktree); a DIR that
                                  does not exist is refused, never ignored
  check_facts.py --root DIR       check another checkout
  check_facts.py --self-test      prove every check can pass and can fail, and prove
                                  each category above on every place (a clause
                                  added, the statement deleted, moved into a
                                  comment or an unused constant, negated); exits
                                  1 unless every reader is proven, so run it with
                                  the reference repository present
  check_facts.py --mutation-test  apply the registry's named break-it edits, the
                                  ones card 53's reviewers used, and prove each
                                  one fails the check

Run it with the repository's virtual environment, `venv/bin/python`, or any
Python 3.11 or later. An older Python is refused with exit code 2.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import itertools
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[3]
REFERENCE_LINK = "reference/agentic-search-data-engineering"
REF = "ref:"
PACKAGE_DIR = "src/system_03_search_agent"
MUTANT = "__mutant__"

# ------------------------------------------------------------------ errors


def literal(value: ast.expr, where: str) -> Any:
    """`ast.literal_eval`, or a RegistryError naming the file and constant:
    a value computed at run time cannot be read without running the code."""
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
        raise RegistryError(
            f"{where} is not a literal, so it cannot be read without running the code "
            f"({type(exc).__name__}); point the registry at the literal it is built from"
        ) from None


class Gap(Exception):
    """The source is not available here. Reported as GAP, never a pass."""


class RegistryError(Exception):
    """The registry names something the code no longer has."""


class PlaceFail(Exception):
    """A place no longer says what the registry reads there: its statement
    is gone, is there a different number of times, has words around it the
    registry does not read, or reads as something no known wording means.
    Reported as FAIL, never dropped from the count (card 53, F-53-A04)."""


# ------------------------------------------------------------------ repository


def scrub(text: str, repo: Repo | None = None) -> str:
    """Replace any absolute local path in a message with a placeholder, so a
    line pasted into a committed report carries none."""
    pairs = []
    if repo is not None:
        pairs.append((str(repo.root), "<repo-root>"))
        if repo.reference is not None:
            pairs.append((str(repo.reference), "<reference>"))
    pairs += [(str(DEFAULT_ROOT), "<repo-root>"), (str(Path.home()), "<home>")]
    for value, placeholder in pairs:
        text = text.replace(value, placeholder)
    return text


class Repo:
    """Reads files from one checkout, plus the data-engineering reference.

    `overlay` replaces a file's text without touching disk, which is how the
    self-test feeds a changed source to a reader.
    """

    def __init__(
        self, root: Path, reference: Path | None, overlay: dict[str, str] | None = None
    ) -> None:
        self.root = root
        self.reference = reference
        self.overlay = dict(overlay or {})
        self._texts: dict[str, str] = {}
        self.read_log: set[str] = set()

    def with_overlay(self, changes: dict[str, str]) -> Repo:
        return Repo(self.root, self.reference, {**self.overlay, **changes})

    def display(self, rel: str) -> str:
        return REFERENCE_LINK + "/" + rel[len(REF) :] if rel.startswith(REF) else rel

    def text(self, rel: str) -> str:
        self.read_log.add(rel)
        if rel in self.overlay:
            return self.overlay[rel]
        if rel in self._texts:
            return self._texts[rel]
        if rel.startswith(REF):
            if self.reference is None:
                raise Gap(f"{self.display(rel)}: the data-engineering repository is not here")
            path = self.reference / rel[len(REF) :]
            if not path.is_file():
                raise Gap(f"{self.display(rel)}: not found in the data-engineering repository")
        else:
            path = self.root / rel
            if not path.is_file():
                raise RegistryError(f"{rel}: the registry names a file that does not exist")
        # The message names the file by its path inside the repository only:
        # an OSError's own text carries the absolute path (PR118-V04).
        try:
            self._texts[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RegistryError(
                f"{self.display(rel)}: not valid UTF-8 at byte {exc.start} ({exc.reason}), "
                "so it cannot be read; save the file as UTF-8"
            ) from None
        except OSError as exc:
            raise RegistryError(
                f"{self.display(rel)}: cannot be read ({type(exc).__name__}: {exc.strerror})"
            ) from None
        return self._texts[rel]

    def python_files(self, directory: str) -> list[str]:
        found = {
            p.relative_to(self.root).as_posix()
            for p in (self.root / directory).rglob("*.py")
            if "__pycache__" not in p.parts
        }
        found |= {k for k in self.overlay if k.startswith(directory + "/") and k.endswith(".py")}
        return sorted(found)


def find_reference(root: Path, explicit: str | None) -> Path | None:
    """The data-engineering repository: --reference, then reference/, then
    the main checkout's reference/ when `root` is an agent worktree whose
    relative symlink does not resolve."""
    if explicit:
        if not Path(explicit).is_dir():
            raise RegistryError("--reference names no directory; nothing was checked")
        return Path(explicit).resolve()
    candidates: list[Path] = []
    candidates.append(root / REFERENCE_LINK)
    try:
        common = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        candidates.append(Path(common).parent / REFERENCE_LINK)
    except (OSError, subprocess.SubprocessError):
        pass
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


_AST_CACHE: dict[str, ast.Module] = {}


def parse_python(repo: Repo, rel: str) -> ast.Module:
    text = repo.text(rel)
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key not in _AST_CACHE:
        _AST_CACHE[key] = ast.parse(text)
    return _AST_CACHE[key]


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# ------------------------------------------------------------------ what a reader sees
#
# A place is read from the text a person actually reads, never from the raw
# file (card 53, F-53-A05). Comments, docstrings and a constant nothing uses
# are replaced by spaces of the same length, so every offset and line number
# still points at the file, and a pattern cannot find its claim in a comment
# while the rendered sentence says something else.
#
# The same pass finds the PROSE UNITS a reader reads as one run of text: a
# string literal, a run of JSX text, a markdown line or table cell, a Python
# string with its implicit concatenations joined. A place's match must cover
# every sentence of those units it touches, whole (`sentence_problem`), so a
# clause added before or after the guarded words fails the place.


@dataclass(frozen=True)
class Visible:
    text: str
    units: tuple[tuple[int, int], ...]


def _blank(text: str, spans: Iterable[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def _skip_quoted(text: str, i: int) -> int:
    """The offset just past the string literal opening at `i`. An
    unterminated string ends at the line's end, so one stray apostrophe
    cannot swallow the rest of the file."""
    quote = text[i]
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            return j + 1
        if text[j] == "\n":
            return j
        j += 1
    return j


def _skip_template(text: str, i: int) -> int:
    depth = 0
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text.startswith("${", j):
            depth += 1
            j += 2
            continue
        if text[j] == "}" and depth:
            depth -= 1
        elif text[j] == "`" and not depth:
            return j + 1
        j += 1
    return j


# The tokens after which a `<` opens a JSX element rather than comparing.
_JSX_BEFORE = frozenset({"", "(", ",", "=", "=>", "?", ":", "&&", "||", "{", "[", "return", ";"})


def _scan_script(text: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Comments and prose units of a TypeScript, TSX or JavaScript file.

    A small context scanner, enough for these screens: plain code, the inside
    of a JSX tag, and JSX children, whose text is prose. Apostrophes in JSX
    text are text, not quotes; `//` straight after a colon is a URL, not a
    comment."""
    comments: list[tuple[int, int]] = []
    units: list[tuple[int, int]] = []
    stack = ["js"]
    braces = [0]
    last = ""
    i, n = 0, len(text)
    while i < n:
        ctx = stack[-1]
        c = text[i]
        if ctx == "children":
            j = i
            while j < n and text[j] not in "<{":
                j += 1
            if j > i:
                units.append((i, j))
            if j >= n:
                break
            if text[j] == "{":
                stack.append("js")
                braces.append(0)
                last = "{"
                i = j + 1
            elif text.startswith("</", j):
                k = text.find(">", j)
                i = n if k < 0 else k + 1
                stack.pop()
                if stack[-1] == "js":
                    last = ")"
            else:
                stack.append("tag")
                i = j + 1
            continue
        if ctx == "tag":
            if c in "\"'":
                end = _skip_quoted(text, i)
                units.append((i + 1, max(i + 1, end - 1)))
                i = end
            elif c == "{":
                stack.append("js")
                braces.append(0)
                last = "{"
                i += 1
            elif text.startswith("/>", i):
                stack.pop()
                if stack[-1] == "js":
                    last = ")"
                i += 2
            elif c == ">":
                stack[-1] = "children"
                i += 1
            else:
                i += 1
            continue
        if text.startswith("//", i) and not (i and text[i - 1] == ":"):
            end = text.find("\n", i)
            end = n if end < 0 else end
            comments.append((i, end))
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            comments.append((i, end))
            i = end
        elif c in "\"'":
            end = _skip_quoted(text, i)
            units.append((i + 1, max(i + 1, end - 1)))
            i, last = end, "v"
        elif c == "`":
            end = _skip_template(text, i)
            units.append((i + 1, max(i + 1, end - 1)))
            i, last = end, "v"
        elif c == "{":
            braces[-1] += 1
            last = "{"
            i += 1
        elif c == "}":
            if braces[-1] == 0 and len(stack) > 1:
                stack.pop()
                braces.pop()
            else:
                braces[-1] = max(0, braces[-1] - 1)
                last = "}"
            i += 1
        elif (
            c == "<"
            and last in _JSX_BEFORE
            and i + 1 < n
            and (text[i + 1].isalpha() or text[i + 1] == ">")
        ):
            if text[i + 1] == ">":
                stack.append("children")
                i += 2
            else:
                stack.append("tag")
                i += 1
        elif text.startswith("=>", i):
            last = "=>"
            i += 2
        elif text.startswith("&&", i) or text.startswith("||", i):
            last = text[i : i + 2]
            i += 2
        elif c.isalnum() or c in "_$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            last = "return" if text[i:j] == "return" else "v"
            i = j
        elif c.isspace():
            i += 1
        else:
            last = c
            i += 1
    return comments, units


_TOP_CONST = re.compile(r"^(export\s+)?const\s+(\w+)\b", re.MULTILINE)
_TOP_START = re.compile(r"^[A-Za-z_@$]", re.MULTILINE)
FRONTEND_SRC = "frontend/src"


def _frontend_texts(repo: Repo, path: str) -> list[str]:
    """Every other non-test script under frontend/src, for "is this exported
    constant used anywhere"."""
    found = []
    for p in sorted((repo.root / FRONTEND_SRC).rglob("*")):
        rel = p.relative_to(repo.root).as_posix()
        if (
            rel == path
            or p.suffix not in {".ts", ".tsx"}
            or ".test." in p.name
            or "__tests__" in p.parts
        ):
            continue
        found.append(repo.overlay.get(rel) or p.read_text(encoding="utf-8"))
    return found


def _unused_constants(repo: Repo, path: str, text: str) -> list[tuple[int, int]]:
    """The spans of top-level `const` declarations nothing reads: not this
    file outside the declaration, and, for an exported one, no other
    non-test script. A reader never sees an unused constant, so a sentence
    kept in one cannot vouch for the page (F-53-A05)."""
    starts = [m.start() for m in _TOP_START.finditer(text)]
    spans = []
    others: list[str] | None = None
    for m in _TOP_CONST.finditer(text):
        later = [s for s in starts if s > m.start()]
        end = later[0] if later else len(text)
        name = m.group(2)
        pattern = re.compile(rf"(?<![\w$.]){re.escape(name)}(?![\w$])")
        rest = text[: m.start()] + text[end:]
        if pattern.search(rest):
            continue
        if m.group(1):
            if others is None:
                others = _frontend_texts(repo, path)
            if any(pattern.search(other) for other in others):
                continue
        spans.append((m.start(), end))
    return spans


def _python_visible(text: str) -> Visible:
    """A Python file with comments and docstrings blanked, and each run of
    implicitly concatenated string literals joined into one prose unit, its
    joins (closing quote, white space, opening quote) blanked too."""
    import io
    import tokenize

    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def at(row: int, col: int) -> int:
        prefix = (
            lines[row - 1].encode("utf-8")[:col].decode("utf-8", errors="ignore")
            if row <= len(lines)
            else ""
        )
        return starts[row - 1] + len(prefix) if row <= len(lines) else len(text)

    blank: list[tuple[int, int]] = []
    strings: list[tuple[int, int, str]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return Visible(text, ())
    fstring: tuple[int, str] | None = None
    for tok in tokens:
        kind = tokenize.tok_name[tok.type]
        start, end = at(*tok.start), at(*tok.end)
        if kind == "COMMENT":
            blank.append((start, end))
        elif kind == "STRING":
            strings.append((start, end, tok.string))
        elif kind == "FSTRING_START":
            fstring = (start, tok.string)
        elif kind == "FSTRING_END" and fstring is not None:
            strings.append((fstring[0], end, text[fstring[0] : end]))
            fstring = None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    docstrings: set[int] = set()
    if tree is not None:
        for node in [tree, *ast.walk(tree)]:
            body = getattr(node, "body", None)
            if (
                isinstance(body, list)
                and body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
                and isinstance(
                    node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
            ):
                docstrings.add(at(body[0].lineno, body[0].col_offset))
    units: list[tuple[int, int]] = []
    run: list[tuple[int, int, str]] = []

    def close_run() -> None:
        if not run:
            return
        first_open = _string_open(run[0][2])
        last_close = _string_close(run[-1][2])
        inner_start = run[0][0] + first_open
        inner_end = run[-1][1] - last_close
        for (_, a_end, a_src), (b_start, _, b_src) in itertools.pairwise(run):
            blank.append((a_end - _string_close(a_src), b_start + _string_open(b_src)))
        units.append((inner_start, max(inner_start, inner_end)))
        run.clear()

    for start, end, src in strings:
        if start in docstrings:
            close_run()
            blank.append((start, end))
            continue
        if run and not text[run[-1][1] : start].strip(" \t\r\n\\"):
            run.append((start, end, src))
        else:
            close_run()
            run.append((start, end, src))
    close_run()
    return Visible(_blank(text, blank), tuple(sorted(units)))


def _string_open(src: str) -> int:
    m = re.match(r"[A-Za-z]*('''|\"\"\"|'|\")", src)
    return m.end() if m else 0


def _string_close(src: str) -> int:
    for quote in ('"""', "'''", '"', "'"):
        if src.endswith(quote):
            return len(quote)
    return 0


def _markdown_visible(text: str) -> Visible:
    blank = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?-->", text, re.DOTALL)]
    shown = _blank(text, blank)
    units = []
    offset = 0
    for line in shown.splitlines(keepends=True):
        cell_start = offset
        for m in re.finditer(r"\|", line):
            units.append((cell_start, offset + m.start()))
            cell_start = offset + m.end()
        units.append((cell_start, offset + len(line.rstrip("\n"))))
        offset += len(line)
    return Visible(shown, tuple(u for u in units if u[1] > u[0]))


_VISIBLE: dict[str, Visible] = {}


CODE_PLACE = "code copy"


def visible(repo: Repo, rel: str, code: bool = False) -> Visible:
    """What a reader of `rel` sees, with the prose units in it. For a code
    copy (`code`), the reader is a program: comments are still blanked, but
    a constant only tests import is kept, since it is the copy under check."""
    text = repo.text(rel)
    key = f"{rel}|{code}|" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key in _VISIBLE:
        return _VISIBLE[key]
    suffix = Path(rel).suffix
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        comments, units = _scan_script(text)
        shown = _blank(text, comments)
        unused = [] if code else _unused_constants(repo, rel, shown)
        shown = _blank(shown, unused)
        units = [u for u in units if not any(a <= u[0] < b for a, b in unused)]
        result = Visible(shown, tuple(sorted(units)))
    elif suffix == ".py":
        result = _python_visible(text)
    elif suffix == ".md":
        result = _markdown_visible(text)
    else:
        result = Visible(text, ())
    if len(result.text) != len(text):  # pragma: no cover - blanking keeps length
        raise RegistryError(f"{rel}: the visible text lost its alignment with the file")
    _VISIBLE[key] = result
    return result


_WORDY = re.compile(r"[A-Za-z0-9]")


def sentences_in(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """The sentences of one prose unit: each ends at `.`, `!` or `?`
    followed by white space or the unit's end."""
    found = []
    begin = start
    for m in re.finditer(r"[.!?](?=\s|$)", text[start:end]):
        stop = start + m.end()
        found.append((begin, stop))
        begin = stop
    if begin < end:
        found.append((begin, end))
    return [(a, b) for a, b in found if _WORDY.search(text[a:b])]


def touched_sentences(doc: Visible, start: int, end: int) -> list[tuple[int, int]]:
    """Every sentence of a prose unit that overlaps the span, in order."""
    found = []
    for u_start, u_end in doc.units:
        if u_start >= end:
            break
        if u_end <= start:
            continue
        for s_start, s_end in sentences_in(doc.text, u_start, u_end):
            if s_start < end and s_end > start:
                found.append((s_start, s_end))
    return found


def sentence_problem(doc: Visible, start: int, end: int) -> str:
    """The first sentence the span touches but does not cover whole, or "".
    What lies outside the span may only be punctuation and white space."""
    for s_start, s_end in touched_sentences(doc, start, end):
        outside = doc.text[s_start : max(s_start, start)] + doc.text[min(s_end, end) : s_end]
        if _WORDY.search(outside):
            return " ".join(doc.text[s_start:s_end].split())
    return ""


def offsets(text: str, node: ast.AST) -> tuple[int, int]:
    """Character offsets of an AST node's source segment. The AST counts
    columns in UTF-8 bytes, so each is converted back to characters."""
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def at(lineno: int, col: int) -> int:
        prefix = lines[lineno - 1].encode("utf-8")[:col].decode("utf-8", errors="ignore")
        return starts[lineno - 1] + len(prefix)

    return at(node.lineno, node.col_offset), at(node.end_lineno, node.end_col_offset)


# ------------------------------------------------------------------ values


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
}
MONTHS = [dt.date(2000, m, 1).strftime("%B") for m in range(1, 13)]


def to_int(text: str) -> int:
    cleaned = text.strip().lower().replace(",", "")
    if cleaned in NUMBER_WORDS:
        return NUMBER_WORDS[cleaned]
    if re.fullmatch(r"\d+(\.0+)?", cleaned):
        return int(float(cleaned))
    raise ValueError(f"not a number: {text!r}")


def to_date(text: str) -> dt.date:
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        return dt.date(int(iso[1]), int(iso[2]), int(iso[3]))
    spoken = re.fullmatch(r"\s*(\d{1,2}) ([A-Z][a-z]+) (\d{4})\s*", text)
    if spoken and spoken[2] in MONTHS:
        return dt.date(int(spoken[3]), MONTHS.index(spoken[2]) + 1, int(spoken[1]))
    raise ValueError(f"not a date: {text!r}")


def words_list(text: str) -> list[str]:
    """ "a, b, c and d" or "a, b, and c" into its items."""
    parts = re.split(r",\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", " ".join(text.split()))
    return [p.strip() for p in parts if p.strip()]


def quoted(text: str) -> list[str]:
    return re.findall(r'"([^"]*)"', text)


def bump(value: Any) -> Any:
    """A changed value of the same kind, for the self-test."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, dt.date):
        return value + dt.timedelta(days=40)
    if isinstance(value, str):
        runs = list(re.finditer(r"\d+", value))
        if runs:
            last = runs[-1]
            new = str(int(last[0]) + 1).zfill(len(last[0]))
            return value[: last.start()] + new + value[last.end() :]
        return value + "_" + MUTANT
    if isinstance(value, dict):
        return {**value, MUTANT: next(iter(value.values()), MUTANT)}
    if isinstance(value, (set, frozenset)):
        return frozenset(value) | {MUTANT}
    if isinstance(value, (list, tuple)):
        return tuple(value) + (MUTANT,)
    raise TypeError(f"cannot bump {type(value).__name__}")


def show(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return "; ".join(
            f"{k}: {show(v)}" for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        )
    if isinstance(value, (set, frozenset)):
        return ", ".join(sorted(str(v) for v in value)) or "none"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "none"
    if isinstance(value, int):
        return f"{value:,}" if value >= 10000 else str(value)
    return str(value)


# ------------------------------------------------------------------ comparisons


@dataclass(frozen=True)
class Cmp:
    """How a stated value is compared with the truth.

    `agree` builds a truth the stated value should pass against, and
    `mutate` changes a truth so it should fail; the self-test uses both to
    prove every comparison can go either way.
    """

    name: str
    ok: Callable[[Any, Any], bool]
    describe: Callable[[Any, Any], str]
    agree: Callable[[Any], Any]
    mutate: Callable[[Any], Any] = bump


def _set_describe(stated: Any, truth: Any) -> str:
    missing = set(truth) - set(stated)
    extra = set(stated) - set(truth)
    parts = [show(set(truth))]
    if missing:
        parts.append("not named: " + show(missing))
    if extra:
        parts.append("named but not so: " + show(extra))
    return "; ".join(parts)


def _subset_describe(stated: Any, truth: Any) -> str:
    extra = set(stated) - set(truth)
    return show(set(truth)) + ("; named but not so: " + show(extra) if extra else "")


def _mapping_describe(stated: Any, truth: Any) -> str:
    diffs = [
        f"{k}: {show(truth.get(k))}"
        for k in sorted(set(stated) | set(truth), key=str)
        if _norm(stated.get(k)) != _norm(truth.get(k))
    ]
    return ("differs at " + "; ".join(diffs)) if diffs else show(truth)


def _norm(value: Any) -> Any:
    return frozenset(value) if isinstance(value, (set, frozenset, list, tuple)) else value


def _canon(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


def _millions_ok(stated: int, truth: int) -> bool:
    return stated in {truth // 1_000_000, round(truth / 1_000_000)}


EXACT = Cmp("exact", lambda s, t: _canon(s) == _canon(t), lambda s, t: show(t), lambda s: s)
MILLIONS = Cmp(
    "millions",
    _millions_ok,
    lambda s, t: f"{show(t)}, which is {round(t / 1e6)}M",
    lambda s: s * 1_000_000,
    lambda t: t + 2_000_000,
)
THOUSANDS = Cmp(
    "thousands",
    lambda s, t: s == round(t, -3),
    lambda s, t: f"{show(t)}, about {round(t, -3):,}",
    lambda s: s,
    lambda t: t + 2_000,
)
COUNT = Cmp(
    "count",
    lambda s, t: s == len(t),
    lambda s, t: f"{len(t)}: {show(t)}",
    lambda s: tuple(f"item{i}" for i in range(s)),
)


def _every_describe(stated: Any, truth: Any) -> str:
    bad = [item for item, qualifies in truth if not qualifies]
    good = len(truth) - len(bad)
    return f"{len(truth)} in all, {good} qualifying" + (
        "; not qualifying: " + ", ".join(str(b) for b in bad) if bad else ""
    )


# The truth is a tuple of (item, qualifies) pairs. A sentence such as "these
# four are real questions" passes only when it counts every item AND every
# item qualifies: counting only the ones that qualify would let a fifth,
# unqualified item ride under "four" (PR118-V03).
EVERY = Cmp(
    "every",
    lambda s, t: s == len(t) and all(qualifies for _, qualifies in t),
    _every_describe,
    lambda s: tuple((f"item{i}", True) for i in range(s)),
    lambda t: tuple(t) + ((MUTANT, False),),
)
SET = Cmp("set", lambda s, t: set(s) == set(t), _set_describe, lambda s: frozenset(s))


def set_allowing_omitted(omitted: Iterable[str]) -> Cmp:
    """SET, where the place may leave out the named members, but only while
    the truth still has them. A member the truth has dropped is not added
    back to what the place says, so a place that is right is never failed
    for it (the side note on PR118-15)."""
    allowed = frozenset(omitted)

    def completed(stated: Any, truth: Any) -> frozenset[Any]:
        return frozenset(stated) | (allowed & frozenset(truth))

    return Cmp(
        "set, less declared omissions",
        lambda s, t: completed(s, t) == set(t),
        lambda s, t: _set_describe(completed(s, t), t),
        lambda s: frozenset(s),
    )


SUBSET = Cmp(
    "subset",
    lambda s, t: set(s) <= set(t),
    _subset_describe,
    lambda s: frozenset(s),
    lambda t: frozenset(),
)
MEMBER = Cmp(
    "member",
    lambda s, t: s in t,
    lambda s, t: "exists: " + show(t),
    lambda s: frozenset({s}),
    lambda t: frozenset(),
)
BOOL = Cmp("bool", lambda s, t: s == t, lambda s, t: show(t), lambda s: s)
MAPPING = Cmp(
    "mapping",
    lambda s, t: {k: _norm(v) for k, v in s.items()} == {k: _norm(v) for k, v in t.items()},
    _mapping_describe,
    lambda s: dict(s),
)
STEPS = Cmp(
    "steps",
    lambda s, t: len(s) == len(t) and all(n.lower().startswith(x.lower()) for x, n in zip(s, t)),
    lambda s, t: show(t),
    lambda s: tuple(x.lower() for x in s),
)
MONTH = Cmp(
    "month",
    lambda s, t: s == t.strftime("%B"),
    lambda s, t: f"{show(t)}, so {t.strftime('%B')}",
    lambda s: dt.date(2000, MONTHS.index(s) + 1, 1),
)


# ------------------------------------------------------------------ truths


@dataclass(frozen=True)
class Truth:
    value: Any
    path: str
    line: int
    note: str = ""


class Reader:
    """Computes one fact's truth from its source. `mutate` returns an overlay
    that changes the source so the truth changes, or None when a reader has
    no source-level mutation (its comparison is still proven to fail).

    Every reader carries `path`, the file it reads, as its first field."""

    path: str

    def read(self, repo: Repo) -> Truth:
        raise NotImplementedError

    def mutate(self, repo: Repo) -> dict[str, str] | None:
        return None


def _assignment(tree: ast.Module, name: str) -> ast.Assign | ast.AnnAssign | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return node
    return None


def _class_field(tree: ast.Module, cls: str, field: str) -> ast.AnnAssign | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if (
                    isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.target.id == field
                ):
                    return item
    return None


def _literal_slice(annotation: ast.expr | None) -> ast.expr | None:
    if (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id == "Literal"
    ):
        return annotation.slice
    return None


def _literal_members(sliced: ast.expr) -> tuple[str, ...]:
    items = sliced.elts if isinstance(sliced, ast.Tuple) else [sliced]
    return tuple(ast.literal_eval(item) for item in items)


def _insert_literal_member(text: str, sliced: ast.expr) -> str:
    start, _ = offsets(text, sliced.elts[0] if isinstance(sliced, ast.Tuple) else sliced)
    return text[:start] + f'"{MUTANT}", ' + text[start:]


@dataclass(frozen=True)
class PyConst(Reader):
    """A module-level constant, read with `ast.literal_eval`."""

    path: str
    name: str
    conv: Callable[[Any], Any] | None = None

    def _node(self, repo: Repo) -> tuple[ast.Assign | ast.AnnAssign, ast.expr]:
        node = _assignment(parse_python(repo, self.path), self.name)
        if node is None or node.value is None:
            raise RegistryError(f"{self.path}: no constant {self.name}")
        return node, node.value

    def read(self, repo: Repo) -> Truth:
        node, value = self._node(repo)
        raw = literal(value, f"{self.path}: {self.name}")
        return Truth(self.conv(raw) if self.conv else raw, self.path, node.lineno)

    def mutate(self, repo: Repo) -> dict[str, str]:
        text = repo.text(self.path)
        _, value = self._node(repo)
        start, end = offsets(text, value)
        return {self.path: text[:start] + repr(bump(ast.literal_eval(value))) + text[end:]}


@dataclass(frozen=True)
class PyLiteral(Reader):
    """The members of a module-level `Name = Literal[...]`, or of a class
    field annotated `Literal[...]` when `cls` is given."""

    path: str
    name: str
    cls: str = ""
    drop: tuple[str, ...] = ()

    def _slice(self, repo: Repo) -> tuple[int, ast.expr]:
        tree = parse_python(repo, self.path)
        if self.cls:
            node = _class_field(tree, self.cls, self.name)
            sliced = _literal_slice(node.annotation) if node else None
        else:
            node = _assignment(tree, self.name)
            sliced = _literal_slice(node.value) if node else None
        if node is None or sliced is None:
            where = f"{self.cls}.{self.name}" if self.cls else self.name
            raise RegistryError(f"{self.path}: no Literal named {where}")
        return node.lineno, sliced

    def read(self, repo: Repo) -> Truth:
        line, sliced = self._slice(repo)
        members = tuple(m for m in _literal_members(sliced) if m not in self.drop)
        return Truth(members, self.path, line)

    def mutate(self, repo: Repo) -> dict[str, str]:
        _, sliced = self._slice(repo)
        return {self.path: _insert_literal_member(repo.text(self.path), sliced)}


@dataclass(frozen=True)
class PyFields(Reader):
    """The annotated field names of a class."""

    path: str
    cls: str

    def _fields(self, repo: Repo) -> tuple[int, list[ast.Name]]:
        for node in parse_python(repo, self.path).body:
            if isinstance(node, ast.ClassDef) and node.name == self.cls:
                names = [
                    i.target
                    for i in node.body
                    if isinstance(i, ast.AnnAssign)
                    and isinstance(i.target, ast.Name)
                    and i.target.id != "model_config"
                ]
                return node.lineno, names
        raise RegistryError(f"{self.path}: no class {self.cls}")

    def read(self, repo: Repo) -> Truth:
        line, names = self._fields(repo)
        return Truth(tuple(n.id for n in names), self.path, line)

    def mutate(self, repo: Repo) -> dict[str, str]:
        text = repo.text(self.path)
        start, end = offsets(text, self._fields(repo)[1][0])
        return {self.path: text[:start] + MUTANT + text[end:]}


@dataclass(frozen=True)
class PyFieldKw(Reader):
    """A keyword on a class field's `Field(...)`, such as `max_length`."""

    path: str
    cls: str
    field: str
    kw: str

    def _kw(self, repo: Repo) -> ast.keyword:
        node = _class_field(parse_python(repo, self.path), self.cls, self.field)
        if node is not None and isinstance(node.value, ast.Call):
            for keyword in node.value.keywords:
                if keyword.arg == self.kw:
                    return keyword
        raise RegistryError(f"{self.path}: {self.cls}.{self.field} has no {self.kw}")

    def read(self, repo: Repo) -> Truth:
        keyword = self._kw(repo)
        value = literal(keyword.value, f"{self.path}: {self.cls}.{self.field} {self.kw}")
        return Truth(value, self.path, keyword.value.lineno)

    def mutate(self, repo: Repo) -> dict[str, str]:
        text = repo.text(self.path)
        value = self._kw(repo).value
        start, end = offsets(text, value)
        return {self.path: text[:start] + repr(bump(ast.literal_eval(value))) + text[end:]}


@dataclass(frozen=True)
class TextMatch(Reader):
    """The first match of a pattern in a document, converted by `conv`
    from the match object."""

    path: str
    pattern: str
    conv: Callable[[re.Match[str]], Any]
    flags: int = 0

    def _match(self, repo: Repo) -> tuple[str, re.Match[str]]:
        text = repo.text(self.path)
        match = re.search(self.pattern, text, self.flags)
        if match is None:
            raise RegistryError(
                f"{repo.display(self.path)}: pattern {self.pattern!r} finds nothing"
            )
        return text, match

    def read(self, repo: Repo) -> Truth:
        text, match = self._match(repo)
        return Truth(self.conv(match), self.path, line_of(text, match.start()))

    def mutate(self, repo: Repo) -> dict[str, str]:
        text, match = self._match(repo)
        group = match.group(1)
        if re.fullmatch(r"[\d,]+", group):
            new = str(int(group.replace(",", "")) + 1)
            new = f"{int(new):,}" if "," in group else new
        else:
            new = bump(group)
        return {self.path: text[: match.start(1)] + new + text[match.end(1) :]}


@dataclass(frozen=True)
class Computed(Reader):
    """Any other computation, as a function of the repository."""

    path: str
    fn: Callable[[Repo], Truth]
    mutator: Callable[[Repo], dict[str, str]] | None = None

    def read(self, repo: Repo) -> Truth:
        return self.fn(repo)

    def mutate(self, repo: Repo) -> dict[str, str] | None:
        return self.mutator(repo) if self.mutator else None


def swap(path: str, pattern: str, replacement: str) -> Callable[[Repo], dict[str, str] | None]:
    """A source-level mutation for a computed reader: rewrite the first
    match of `pattern` in `path`. None when the pattern no longer matches,
    which the self-test names as a skipped reader."""

    def mutate(repo: Repo) -> dict[str, str] | None:
        text = repo.text(path)
        changed, count = re.subn(pattern, replacement, text, count=1)
        return {path: changed} if count else None

    return mutate


# ------------------------------------------------------------------ call graph


TIERS = frozenset({"guard", "plan", "synth"})
PRIMITIVE_ATTRS = frozenset({"call_tier"})
# Jev, the classifier, is asked one decision at a time through `call_jev`
# and a whole answer's reworded sentences at once through `call_jev_batch`
# (`synthesis/sentence_check.py`). Both count as a classifier call.
CLASSIFIER_CALLS = frozenset({"call_jev", "call_jev_batch"})
PRIMITIVE_NAMES = frozenset({"_dispatch_tier_call"}) | CLASSIFIER_CALLS
GRAPH_MODULE_PATH = f"{PACKAGE_DIR}/core/graph.py"


def _module_name(rel: str) -> str:
    dotted = rel[len("src/") : -len(".py")].replace("/", ".")
    return dotted.removesuffix(".__init__")


class CallGraph:
    """A static call graph of the package, enough to answer "does this loop
    step reach a model call, and on which tier".

    A model call is `harness.call_tier(...)` or `_dispatch_tier_call(...)`,
    whose string argument names the tier, or `call_jev(...)` or
    `call_jev_batch(...)`, the classifier.
    Calls are resolved by name within a module, through `from X import y`,
    through `module.attr` on an imported module, and through `self.method`.
    A function named without being called (a callback) counts as reached.
    """

    def __init__(self, repo: Repo) -> None:
        self.repo = repo
        self.funcs: dict[str, ast.AST] = {}
        self.modules: dict[str, dict[str, str]] = {}
        self.owner: dict[str, tuple[str, str]] = {}
        files = repo.python_files(PACKAGE_DIR)
        self.files = tuple(files)
        known = {_module_name(f) for f in files}
        for rel in files:
            module = _module_name(rel)
            tree = parse_python(repo, rel)
            imports: dict[str, str] = {}
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        target = f"{node.module}.{alias.name}"
                        imports[alias.asname or alias.name] = (
                            target if target in known else f"{node.module}:{alias.name}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports[alias.asname or alias.name] = alias.name
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._add(module, node.name, node, "")
                elif isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            self._add(module, f"{node.name}.{item.name}", item, node.name)
            self.modules[module] = imports
        self._reach: dict[str, frozenset[str]] = {}
        self._edges: dict[str, tuple[frozenset[str], frozenset[str]]] = {}

    def _add(self, module: str, name: str, node: ast.AST, cls: str) -> None:
        key = f"{module}:{name}"
        self.funcs[key] = node
        self.owner[key] = (module, cls)

    def _resolve(self, module: str, name: str) -> str | None:
        local = f"{module}:{name}"
        if local in self.funcs:
            return local
        target = self.modules.get(module, {}).get(name)
        return target if target in self.funcs else None

    def _scan(self, key: str) -> tuple[frozenset[str], frozenset[str]]:
        if key in self._edges:
            return self._edges[key]
        module, cls = self.owner[key]
        imports = self.modules[module]
        edges: set[str] = set()
        prims: set[str] = set()
        for node in ast.walk(self.funcs[key]):
            if isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                if called in PRIMITIVE_NAMES or (
                    isinstance(func, ast.Attribute) and called in PRIMITIVE_ATTRS
                ):
                    if called in CLASSIFIER_CALLS:
                        prims.add("classifier")
                        continue
                    literal = [
                        a.value
                        for a in [*node.args, *(k.value for k in node.keywords)]
                        if isinstance(a, ast.Constant) and a.value in TIERS
                    ]
                    prims.update(literal or ["unknown"])
                    continue
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    base = func.value.id
                    if base == "self" and cls and f"{module}:{cls}.{func.attr}" in self.funcs:
                        edges.add(f"{module}:{cls}.{func.attr}")
                    elif base in imports and f"{imports[base]}:{func.attr}" in self.funcs:
                        edges.add(f"{imports[base]}:{func.attr}")
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in PRIMITIVE_NAMES:
                    continue
                resolved = self._resolve(module, node.id)
                if resolved and resolved != key:
                    edges.add(resolved)
        self._edges[key] = (frozenset(edges), frozenset(prims))
        return self._edges[key]

    def reachable(self, start: str) -> frozenset[str]:
        """Every function reachable from `start`, `start` included."""
        if start not in self._reach:
            seen: set[str] = set()
            todo = [start]
            while todo:
                key = todo.pop()
                if key not in seen:
                    seen.add(key)
                    todo.extend(self._scan(key)[0])
            self._reach[start] = frozenset(seen)
        return self._reach[start]

    def tiers(self, key: str) -> frozenset[str]:
        """The model calls reachable from `key`: tier names, "classifier"
        for Jev, "unknown" for a tier passed as a variable."""
        found: set[str] = set()
        for reached in self.reachable(key):
            found |= self._scan(reached)[1]
        return frozenset(found)

    def reaches(self, start: str, target: str) -> bool:
        return target in self.reachable(start)


_GRAPHS: dict[str, CallGraph] = {}


def call_graph(repo: Repo) -> CallGraph:
    key = json.dumps(
        sorted(
            (k, hashlib.sha256(v.encode()).hexdigest())
            for k, v in repo.overlay.items()
            if k.startswith(PACKAGE_DIR + "/") and k.endswith(".py")
        )
    )
    key = f"{repo.root}|{key}"
    if key not in _GRAPHS:
        _GRAPHS[key] = CallGraph(repo)
    repo.read_log.update(_GRAPHS[key].files)
    return _GRAPHS[key]


def loop_steps(repo: Repo) -> list[tuple[str, str, int]]:
    """(step, function, line) for every `add_node("step", fn)` in core/graph.py."""
    steps = []
    for node in ast.walk(parse_python(repo, GRAPH_MODULE_PATH)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_node"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[1], ast.Name)
        ):
            steps.append((node.args[0].value, node.args[1].id, node.lineno))
    if not steps:
        raise RegistryError(f"{GRAPH_MODULE_PATH}: no add_node calls")
    return sorted(steps, key=lambda s: s[2])


def _step(repo: Repo, step: str) -> tuple[str, int]:
    for name, fn, line in loop_steps(repo):
        if name == step:
            return f"{_module_name(GRAPH_MODULE_PATH)}:{fn}", line
    raise RegistryError(f"{GRAPH_MODULE_PATH}: no loop step {step!r}")


def _function_line(repo: Repo, name: str) -> int:
    node = call_graph(repo).funcs.get(f"{_module_name(GRAPH_MODULE_PATH)}:{name}")
    if node is None:
        raise RegistryError(f"{GRAPH_MODULE_PATH}: no function {name}")
    return node.lineno


def _swap_step_function(repo: Repo, step: str, reach_model: bool) -> dict[str, str]:
    """Point one loop step at a new function that does, or does not, make a
    plan-tier call, so a call-graph truth must change."""
    text = repo.text(GRAPH_MODULE_PATH)
    for name, fn, _ in loop_steps(repo):
        if name == step:
            body = '    return _dispatch_tier_call("plan")\n' if reach_model else "    return {}\n"
            swapped = re.sub(
                rf'add_node\(\s*"{step}"\s*,\s*{fn}\s*\)',
                f'add_node("{step}", {MUTANT}_step)',
                text,
            )
            return {GRAPH_MODULE_PATH: swapped + f"\n\nasync def {MUTANT}_step(state):\n{body}"}
    raise RegistryError(f"{GRAPH_MODULE_PATH}: no loop step {step!r}")


def steps_reaching_model() -> Computed:
    def read(repo: Repo) -> Truth:
        graph = call_graph(repo)
        reached = tuple(
            name
            for name, fn, _ in loop_steps(repo)
            if graph.tiers(f"{_module_name(GRAPH_MODULE_PATH)}:{fn}")
        )
        return Truth(reached, GRAPH_MODULE_PATH, loop_steps(repo)[0][2])

    def mutate(repo: Repo) -> dict[str, str]:
        reached = read(repo).value
        first = loop_steps(repo)[0][0]
        return _swap_step_function(repo, first, reach_model=first not in reached)

    return Computed(GRAPH_MODULE_PATH, read, mutate)


def step_uses_tier(step: str, tier: str) -> Computed:
    """True when the step's call graph reaches a call on `tier`."""

    def read(repo: Repo) -> Truth:
        key, line = _step(repo, step)
        tiers = call_graph(repo).tiers(key)
        return Truth(
            tier in tiers, GRAPH_MODULE_PATH, line, f"the {step} step reaches: {show(tiers)}"
        )

    def mutate(repo: Repo) -> dict[str, str]:
        return _swap_step_function(repo, step, reach_model=not read(repo).value)

    return Computed(GRAPH_MODULE_PATH, read, mutate)


def step_calls_no_model(step: str) -> Computed:
    def read(repo: Repo) -> Truth:
        key, line = _step(repo, step)
        tiers = call_graph(repo).tiers(key)
        return Truth(not tiers, GRAPH_MODULE_PATH, line, f"the {step} step reaches: {show(tiers)}")

    def mutate(repo: Repo) -> dict[str, str]:
        return _swap_step_function(repo, step, reach_model=read(repo).value)

    return Computed(GRAPH_MODULE_PATH, read, mutate)


def checked_by_code_alone(step: str, function: str) -> Computed:
    """True when `function` is reached from the step and asks no model."""

    def read(repo: Repo) -> Truth:
        key, _ = _step(repo, step)
        target = f"{_module_name(GRAPH_MODULE_PATH)}:{function}"
        line = _function_line(repo, function)
        graph = call_graph(repo)
        if not graph.reaches(key, target):
            raise RegistryError(
                f"{GRAPH_MODULE_PATH}: the {step} step no longer reaches {function}"
            )
        tiers = graph.tiers(target)
        return Truth(not tiers, GRAPH_MODULE_PATH, line, f"{function} reaches: {show(tiers)}")

    def mutate(repo: Repo) -> dict[str, str]:
        # Replace the function's whole body with one statement that does the
        # opposite of what it does today.
        text = repo.text(GRAPH_MODULE_PATH)
        node = call_graph(repo).funcs[f"{_module_name(GRAPH_MODULE_PATH)}:{function}"]
        start, _ = offsets(text, node.body[0])
        _, stop = offsets(text, node)
        body = 'return _dispatch_tier_call("guard")' if read(repo).value else "return None"
        return {GRAPH_MODULE_PATH: text[:start] + body + text[stop:]}

    return Computed(GRAPH_MODULE_PATH, read, mutate)


def step_names() -> Computed:
    def read(repo: Repo) -> Truth:
        steps = loop_steps(repo)
        return Truth(tuple(s[0] for s in steps), GRAPH_MODULE_PATH, steps[0][2])

    return Computed(
        GRAPH_MODULE_PATH,
        read,
        swap(GRAPH_MODULE_PATH, r'add_node\("(\w+)"', f'add_node("{MUTANT}"'),
    )


# ------------------------------------------------------------------ places


def g(index: int = 1, conv: Callable[[str], Any] = str) -> Callable[[re.Match[str]], Any]:
    """Parse one capture group."""
    return lambda m: conv(" ".join(m.group(index).split()))


GROUP_1 = g()


def present(_: re.Match[str]) -> bool:
    """For a sentence that makes a yes-or-no claim: finding it means yes."""
    return True


def union(values: list[Any]) -> Any:
    merged: set[Any] = set()
    for value in values:
        merged |= set(value) if isinstance(value, (set, frozenset, list, tuple)) else {value}
    return frozenset(merged)


def merge_dicts(values: list[Any]) -> dict[Any, Any]:
    merged: dict[Any, Any] = {}
    for value in values:
        for key, item in value.items():
            if isinstance(item, (set, frozenset)) and key in merged:
                merged[key] = frozenset(merged[key]) | item
            else:
                merged[key] = item
    return merged


@dataclass(frozen=True)
class Where:
    """One place that states a fact: a file, a pattern that captures what it
    says, how to parse the capture, and how to compare it with the truth.

    With `collect`, every match is merged into one statement at the first
    match's line; otherwise each match is its own statement.

    `expect` is how many times the pattern must match the text a reader
    sees. A statement that disappears, or a multi-card pattern that loses
    one card, is a FAIL rather than a smaller count (F-53-A04).

    `block` marks a place that reads named fields out of a structure (a
    TypeScript array of layers, an object's keys) rather than a sentence. It
    is exempt from the whole-sentence rule, because the prose inside the
    structure is not what it claims; that prose is guarded, where it states
    a fact, by a place of its own.
    """

    place: str
    path: str
    pattern: str
    cmp: Cmp = EXACT
    parse: Callable[[re.Match[str]], Any] = GROUP_1
    collect: Callable[[list[Any]], Any] | None = None
    flags: int = 0
    expect: int = 1
    block: bool = False


@dataclass(frozen=True)
class Fact:
    fact_id: str
    what: str
    truth: Reader
    stated: tuple[Where, ...] = ()
    downstream: tuple[Where, ...] = ()


@dataclass(frozen=True)
class Statement:
    where: Where
    value: Any
    line: int
    says: str


@dataclass(frozen=True)
class Result:
    verdict: str
    fact: Fact
    where: Where | None
    line: str

    def render(self) -> str:
        return self.line


def statements(repo: Repo, where: Where) -> list[Statement]:
    """What a place says, read from the text a reader sees (`visible`).

    Four ways a place stops saying what the registry reads, each a FAIL
    (`PlaceFail`), never a silent drop: the pattern matches a different
    number of times than `expect`; a match reads as something no known
    wording or name means; it reads as nothing; or it touches a sentence it
    does not cover whole, so words the registry never reads sit in the same
    sentence as the claim (F-53-A03)."""
    doc = visible(repo, where.path, code=where.place == CODE_PLACE)
    text = doc.text
    matches = list(re.finditer(where.pattern, text, where.flags))
    if len(matches) != where.expect:
        where_lines = ", ".join(str(line_of(text, m.start())) for m in matches) or "nowhere"
        raise PlaceFail(
            f"{repo.display(where.path)}: pattern {_clip(where.pattern, 90)!r} is said "
            f"{len(matches)} times (lines {where_lines}) where the registry reads {where.expect}; "
            "the statement changed, moved into a comment or disappeared"
        )
    found = []
    for match in matches:
        line = line_of(text, match.start())
        try:
            value = where.parse(match)
        except Exception as exc:  # noqa: BLE001 - any parse failure is one FAIL line
            raise PlaceFail(
                f"{repo.display(where.path)}:{line}: cannot read {_clip(match.group(0), 80)!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from None
        if _empty(value):
            raise PlaceFail(
                f"{repo.display(where.path)}:{line}: reads as nothing, so it cannot be judged; "
                "the page no longer says what the registry expects there"
            )
        if not where.block:
            problem = sentence_problem(doc, match.start(), match.end())
            if problem:
                raise PlaceFail(
                    f"{repo.display(where.path)}:{line}: the sentence says more than the "
                    f"registry reads: {_clip(problem, 160)!r}"
                )
        found.append(Statement(where, value, line, _says(match, value)))
    if where.collect is not None:
        first = found[0]
        return [replace(first, value=where.collect([s.value for s in found]))]
    return found


def _empty(value: Any) -> bool:
    """A reading with nothing in it. It is never compared: an empty set is a
    subset of anything, so it would pass whatever the page said."""
    return value is None or (
        isinstance(value, (str, set, frozenset, list, tuple, dict)) and not value
    )


def _clip(text: str, limit: int = 100) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _says(match: re.Match[str], value: Any) -> str:
    """What the place says, as short as it can be read: the whole match,
    else the captured text, else the value parsed out of a long block. A
    pipe becomes a slash so a table row cannot break the line's columns."""
    whole = " ".join(match.group(0).split())
    if len(whole) > 120 and match.re.groups:
        captured = " ".join((match.group(1) or "").split())
        whole = captured if len(captured) <= 140 else "(reads as) " + show(value)
    return _clip(whole, 140).replace("|", "/")


def _reason(exc: BaseException, repo: Repo | None) -> str:
    """One line for a failure, scrubbed of local paths. The registry's own
    errors carry their message; anything else is named by its type too."""
    text = (
        str(exc)
        if isinstance(exc, (Gap, RegistryError, PlaceFail))
        else f"{type(exc).__name__}: {exc}"
    )
    return scrub(" ".join(text.split()), repo)


def check_fact(repo: Repo, fact: Fact) -> list[Result]:
    places = [*fact.stated, *fact.downstream]
    try:
        truth = fact.truth.read(repo)
    except Gap as exc:
        return [
            Result(
                "GAP",
                fact,
                w,
                f"GAP | {fact.fact_id} | {w.place} | {scrub(str(exc), repo)} | {w.path}",
            )
            for w in places
        ]
    except Exception as exc:  # noqa: BLE001 - one ERROR line per place, and the run goes on
        reason = _reason(exc, repo)
        return [
            Result(
                "ERROR",
                fact,
                w,
                f"ERROR | {fact.fact_id} | {w.place} | not judged, the truth could not be "
                f"computed: {reason} | {w.path}",
            )
            for w in places
        ] or [Result("ERROR", fact, None, f"ERROR | {fact.fact_id} | {reason}")]
    source = f"{repo.display(truth.path)}:{truth.line}"
    results = []
    for where in places:
        # Reading AND judging a place sit inside one catch-all: a file that is
        # not UTF-8, or a comparison that raises, is one ERROR line for this
        # place, never a traceback that ends the run before its summary.
        try:
            found = statements(repo, where)
            judged = [
                (st, where.cmp.ok(st.value, truth.value), where.cmp.describe(st.value, truth.value))
                for st in found
            ]
        except PlaceFail as exc:
            results.append(
                Result(
                    "FAIL",
                    fact,
                    where,
                    f"FAIL | {fact.fact_id} | {where.place} | {_reason(exc, repo)}",
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one ERROR line per place, and the run goes on
            results.append(
                Result(
                    "ERROR",
                    fact,
                    where,
                    f"ERROR | {fact.fact_id} | {where.place} | {_reason(exc, repo)}",
                )
            )
            continue
        for st, ok, true_text in judged:
            verdict = "PASS" if ok else "FAIL"
            if truth.note:
                true_text += f" ({truth.note})"
            results.append(
                Result(
                    verdict,
                    fact,
                    where,
                    " | ".join(
                        [
                            verdict,
                            fact.fact_id,
                            where.place,
                            f'says "{st.says}"',
                            f"true: {_clip(true_text, 240).replace('|', '/')}",
                            f"{repo.display(where.path)}:{st.line}",
                            source,
                        ]
                    ),
                )
            )
    return results


# ------------------------------------------------------------------ commands


def load_registry() -> tuple[Fact, ...]:
    # The registry imports this module by name. When this file runs as a
    # script it is `__main__`, so alias it first: otherwise the registry
    # would import a second copy and its Fact would not be this Fact.
    sys.modules.setdefault("check_facts", sys.modules[__name__])
    sys.path.insert(0, str(HERE))
    import facts_registry

    return facts_registry.FACTS


def run_checks(repo: Repo, facts: tuple[Fact, ...], show_all: bool) -> int:
    counts = {"PASS": 0, "FAIL": 0, "GAP": 0, "ERROR": 0}
    stale: set[str] = set()
    unchecked: set[str] = set()
    for fact in facts:
        for result in check_fact(repo, fact):
            counts[result.verdict] += 1
            if result.verdict == "FAIL":
                stale.add(fact.fact_id)
            elif result.verdict in ("GAP", "ERROR"):
                unchecked.add(fact.fact_id)
            if show_all or result.verdict != "PASS":
                print(result.render())
    # Only PASS passes: a GAP or ERROR place was never judged, so it can hide
    # a stale fact and must not read as a clean run.
    verdict = "NOT PASSED" if (counts["FAIL"] or counts["GAP"] or counts["ERROR"]) else "PASS"
    print(
        f"facts: {len(facts)} | stale {len(stale)} | not fully checked {len(unchecked)} | "
        f"places: PASS {counts['PASS']}, FAIL {counts['FAIL']}, GAP {counts['GAP']}, "
        f"ERROR {counts['ERROR']} | {verdict}"
    )
    if counts["ERROR"]:
        return 2
    if counts["FAIL"]:
        return 1
    return 3 if counts["GAP"] else 0


def sources_read(repo: Repo, fact: Fact) -> set[str]:
    """Every file the fact's truth is computed from, recorded as it is read."""
    probe = Repo(repo.root, repo.reference, repo.overlay)
    try:
        fact.truth.read(probe)
    except Exception:  # noqa: BLE001, S110 - only the files it read matter here
        pass
    return {probe.display(p) for p in probe.read_log} | {probe.display(fact.truth.path)}


def _from_path_problem(repo: Repo, wanted: str) -> str:
    """Why `--from` cannot name this path, or "" when it names an existing
    file or folder in the checkout under test, or in the data-engineering
    repository through `reference/`. Never echoes an absolute path."""
    if Path(wanted).is_absolute():
        return "takes a path relative to the checkout's root, not an absolute one"
    prefix = REFERENCE_LINK + "/"
    if wanted.startswith(prefix) and repo.reference is not None:
        target = repo.reference / wanted[len(prefix) :]
    else:
        target = repo.root / wanted
    if target.exists():
        return ""
    return f"names no file in the checkout under test: {wanted}"


def print_map(repo: Repo, facts: Iterable[Fact]) -> int:
    """For each fact: its source, then every place that states it. A change
    to the source names every place to update."""
    for fact in facts:
        print(f"{fact.fact_id}: {fact.what}")
        try:
            truth = fact.truth.read(repo)
            print(f"  source: {repo.display(truth.path)}:{truth.line}")
        except Exception as exc:  # noqa: BLE001 - the map still lists the places
            print(f"  source: {repo.display(fact.truth.path)} ({_reason(exc, repo)})")
        for where in (*fact.stated, *fact.downstream):
            try:
                lines = ", ".join(str(s.line) for s in statements(repo, where))
            except Exception:  # noqa: BLE001 - an unreadable place is named, and the map goes on
                lines = "not found"
            label = f"screen, {where.place}" if where in fact.stated else where.place
            print(f"  {label}: {repo.display(where.path)}:{lines}")
    return 0


# ------------------------------------------------------------------ self-test


def self_test(repo: Repo, facts: tuple[Fact, ...]) -> int:
    """Prove every check can pass and can fail.

    1. Every comparison, on every place it is used: a truth built to agree
       with what the place says passes, and that truth changed fails.
    2. Every reader that can change its source: the source is changed in an
       overlay, never on disk, and the computed truth must change with it.
    3. The parsers on fixed inputs.
    """
    failures: list[str] = []
    compared = proven = 0
    for fact in facts:
        for where in (*fact.stated, *fact.downstream):
            try:
                found = statements(repo, where)
            except Exception as exc:  # noqa: BLE001 - reported, and the self-test goes on
                failures.append(
                    f"{fact.fact_id} | {where.place}: cannot read the place: {_reason(exc, repo)}"
                )
                continue
            for st in found:
                compared += 1
                agreeing = where.cmp.agree(st.value)
                passes = where.cmp.ok(st.value, agreeing)
                fails = not where.cmp.ok(st.value, where.cmp.mutate(agreeing))
                if passes and fails:
                    proven += 1
                if not passes:
                    failures.append(
                        f"{fact.fact_id} | {where.place}:{st.line}: an agreeing truth does not pass"
                    )
                if not fails:
                    failures.append(
                        f"{fact.fact_id} | {where.place}:{st.line}: a changed truth still passes"
                    )

    mutated = 0
    skipped: list[str] = []
    for fact in facts:
        try:
            before = fact.truth.read(repo)
            overlay = fact.truth.mutate(repo)
        except Gap:
            skipped.append(f"{fact.fact_id} (source not here: pass --reference)")
            continue
        except Exception as exc:  # noqa: BLE001 - reported, and the self-test goes on
            failures.append(f"{fact.fact_id}: reader cannot read its source: {_reason(exc, repo)}")
            continue
        if overlay is None:
            skipped.append(f"{fact.fact_id} (its source-level mutation no longer finds its target)")
            continue
        mutated += 1
        try:
            after = fact.truth.read(repo.with_overlay(overlay))
        except Exception as exc:  # noqa: BLE001 - reported, and the self-test goes on
            failures.append(
                f"{fact.fact_id}: the changed source no longer reads: {_reason(exc, repo)}"
            )
            continue
        if _norm(after.value) == _norm(before.value):
            failures.append(
                f"{fact.fact_id}: a changed source did not change the truth ({show(before.value)})"
            )

    proofs, category_failures = category_proofs(repo, facts)
    failures += category_failures

    parser_cases: list[tuple[str, Any, Any]] = [
        ("to_int word", to_int("Eleven"), 11),
        ("to_int commas", to_int("115,406,761"), 115406761),
        ("to_int sixteen", to_int("Sixteen"), 16),
        ("to_date spoken", to_date("22 April 2026"), dt.date(2026, 4, 22)),
        ("to_date iso", to_date("ncbi_kg_v1_2026-04-22"), dt.date(2026, 4, 22)),
        ("words_list and", words_list("guard, think and done"), ["guard", "think", "done"]),
        (
            "words_list oxford",
            words_list("Gene, ClinVar, and Taxonomy"),
            ["Gene", "ClinVar", "Taxonomy"],
        ),
        ("bump date string", bump("v1_2026-04-22"), "v1_2026-04-23"),
        ("millions floor", _millions_ok(67, 67_536_325), True),
        ("millions wrong", _millions_ok(115, 693_295_991), False),
        # The visible-text scanner: an apostrophe in JSX text is text, a URL's
        # `//` is not a comment, a JSX comment is blanked, and Python's
        # implicit concatenation reads as one run of prose.
        (
            "jsx apostrophe and comment",
            _blank(
                "x = <p>It's fine {/* hidden */} here</p>;",
                _scan_script("x = <p>It's fine {/* hidden */} here</p>;")[0],
            ),
            "x = <p>It's fine {            } here</p>;",
        ),
        ("url is not a comment", _scan_script('a = "https://x.org"; // c')[0], [(21, 25)]),
        (
            "python joins concatenated strings",
            _python_visible('X = (\n    "one "\n    "two."\n)  # c\n').text,
            'X = (\n    "one  \n     two."\n)     \n',
        ),
        ("sentences split at a full stop", len(sentences_in("One. Two three.", 0, 15)), 2),
    ]
    for label, got, want in parser_cases:
        if got != want:
            failures.append(f"parser {label}: got {got!r}, want {want!r}")

    # A reader that was not proven is a failure, not a footnote: a self-test
    # that proves fewer than all readers has not shown every check can fail.
    for label in skipped:
        failures.append(f"reader not proven: {label}")
    for failure in failures:
        print(f"SELF-TEST FAIL | {failure}")
    print(
        f"self-test: {proven} of {compared} comparisons proven to pass and to fail; "
        f"{mutated - sum(1 for f in failures if 'did not change' in f or 'no longer reads' in f)} "
        f"of {len(facts)} readers proven to follow a changed source; "
        f"{len(parser_cases)} parser cases; {len(failures)} failures"
    )
    print(
        "self-test, by category (proven of tried): "
        + "; ".join(f"{name} {done} of {tried}" for name, (done, tried) in proofs.items())
    )
    return 1 if failures else 0


# ------------------------------------------------------------------ category proofs
#
# Card 53's review found the checker passing false pages in five shapes. Each
# is a CATEGORY here, proven on every place rather than on the examples the
# reviewers happened to write (Review_rounds.md, Rule 2):
#
#   extension  a clause added to a sentence a place reads fails a place in
#              that file.
#   removal    a statement deleted from the page fails its place.
#   comment    the statement moved into a comment fails its place, although
#              the raw file still carries the words.
#   unused     the statement moved into a constant nothing uses fails its place.
#   negation   "not " put at the start of any sentence a place touches fails
#              at least one place in that file.
#
# Every edit is an overlay in memory, never a change on disk.

DECOY_COMMENTS = {
    ".ts": ("/*\n", "\n*/\n", "*/"),
    ".tsx": ("/*\n", "\n*/\n", "*/"),
    ".md": ("<!--\n", "\n-->\n", "-->"),
}


class _Judge:
    """Whether one place passes on a changed file, reusing each fact's truth
    unless the change touches a file that truth reads."""

    def __init__(self, repo: Repo, facts: tuple[Fact, ...]) -> None:
        self.repo = repo
        self.truth: dict[str, Truth | None] = {}
        self.sources: dict[str, set[str]] = {}
        for fact in facts:
            probe = Repo(repo.root, repo.reference, repo.overlay)
            try:
                self.truth[fact.fact_id] = fact.truth.read(probe)
            except Exception:  # noqa: BLE001 - a fact whose truth fails is judged as failing
                self.truth[fact.fact_id] = None
            self.sources[fact.fact_id] = set(probe.read_log)

    def passes(self, fact: Fact, where: Where, overlay: dict[str, str]) -> bool:
        changed = self.repo.with_overlay(overlay)
        truth = self.truth[fact.fact_id]
        if set(overlay) & self.sources[fact.fact_id]:
            try:
                truth = fact.truth.read(changed)
            except Exception:  # noqa: BLE001 - an unreadable truth is not a pass
                return False
        if truth is None:
            return False
        try:
            found = statements(changed, where)
        except Exception:  # noqa: BLE001 - a place that cannot be read is not a pass
            return False
        return all(where.cmp.ok(st.value, truth.value) for st in found)


def _matches(repo: Repo, where: Where) -> list[re.Match[str]]:
    doc = visible(repo, where.path, code=where.place == CODE_PLACE)
    return list(re.finditer(where.pattern, doc.text, where.flags))


def category_proofs(
    repo: Repo, facts: tuple[Fact, ...]
) -> tuple[dict[str, tuple[int, int]], list[str]]:
    judge = _Judge(repo, facts)
    tally = {k: [0, 0] for k in ("extension", "removal", "comment", "unused", "negation")}
    failures: list[str] = []
    by_path: dict[str, list[tuple[Fact, Where]]] = {}
    for fact in facts:
        for where in (*fact.stated, *fact.downstream):
            by_path.setdefault(where.path, []).append((fact, where))

    def expect_fail(
        kind: str, fact: Fact, where: Where, overlay: dict[str, str], what: str
    ) -> None:
        tally[kind][1] += 1
        if judge.passes(fact, where, overlay):
            failures.append(f"{fact.fact_id} | {where.place} | {kind}: still passes after {what}")
        else:
            tally[kind][0] += 1

    negated: set[tuple[str, int]] = set()
    for fact in facts:
        for where in (*fact.stated, *fact.downstream):
            try:
                if not judge.passes(fact, where, {}):
                    continue  # already reported by the checks above
                raw = repo.text(where.path)
                doc = visible(repo, where.path, code=where.place == CODE_PLACE)
                matches = _matches(repo, where)
            except Exception:  # noqa: BLE001, S112 - an unreadable place is reported by step 1
                continue
            first = matches[0]
            original = raw[first.start() : first.end()]
            # removal
            expect_fail(
                "removal",
                fact,
                where,
                {where.path: raw[: first.start()] + raw[first.end() :]},
                "the statement was deleted",
            )
            # comment
            suffix = Path(where.path).suffix
            if suffix in DECOY_COMMENTS and DECOY_COMMENTS[suffix][2] not in original:
                opener, closer, _ = DECOY_COMMENTS[suffix]
                moved = opener + original + closer + raw[: first.start()] + raw[first.end() :]
                if len(re.findall(where.pattern, moved, where.flags)) >= where.expect:
                    expect_fail(
                        "comment",
                        fact,
                        where,
                        {where.path: moved},
                        "the statement moved into a comment",
                    )
            # unused constant
            if (
                suffix in {".ts", ".tsx"}
                and where.place != CODE_PLACE
                and "`" not in original
                and "${" not in original
            ):
                moved = (
                    raw[: first.start()]
                    + raw[first.end() :]
                    + f"\nconst {MUTANT}decoy = `{original}`;\n"
                )
                if len(re.findall(where.pattern, moved, where.flags)) >= where.expect:
                    expect_fail(
                        "unused",
                        fact,
                        where,
                        {where.path: moved},
                        "the statement moved into an unused constant",
                    )
            if where.block:
                continue
            for match in matches:
                sentences = touched_sentences(doc, match.start(), match.end())
                if not sentences:
                    continue
                # extension: a clause before the last sentence's full stop,
                # judged by every place in the file
                s_start, s_end = sentences[-1]
                at = s_end - 1 if raw[s_end - 1] in ".!?" else s_end
                overlay = {where.path: raw[:at] + ", but not always" + raw[at:]}
                tally["extension"][1] += 1
                if all(judge.passes(f, w_, overlay) for f, w_ in by_path[where.path]):
                    failures.append(
                        f"{fact.fact_id} | {where.place} | extension: no place fails when a clause "
                        f"is added to {_clip(' '.join(raw[s_start:s_end].split()), 90)!r}"
                    )
                else:
                    tally["extension"][0] += 1
                # negation, once per sentence, judged by every place in the file
                for s_start, s_end in sentences:
                    if (where.path, s_start) in negated:
                        continue
                    negated.add((where.path, s_start))
                    word = _WORDY.search(raw, s_start)
                    if word is None:
                        continue
                    at = word.start()
                    overlay = {where.path: raw[:at] + "not " + raw[at:]}
                    tally["negation"][1] += 1
                    if all(judge.passes(f, w_, overlay) for f, w_ in by_path[where.path]):
                        failures.append(
                            f"{fact.fact_id} | {where.place} | negation: no place fails when "
                            f"{_clip(' '.join(raw[s_start:s_end].split()), 90)!r} is negated"
                        )
                    else:
                        tally["negation"][0] += 1
    return {k: (v[0], v[1]) for k, v in tally.items()}, failures


def mutation_test(
    repo: Repo,
    facts: tuple[Fact, ...],
    mutations: tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...],
) -> int:
    """Apply each named break-it edit in memory and require the checker to
    stop passing. The unedited checkout must pass first, or no edit proves
    anything. An edit whose text is no longer in its file is a failure."""
    base = [r for fact in facts for r in check_fact(repo, fact) if r.verdict != "PASS"]
    if base:
        for result in base:
            print(f"MUTATION-TEST FAIL | the unedited checkout does not pass: {result.render()}")
        return 1
    missed = 0
    for label, finding, edits in mutations:
        overlay: dict[str, str] = {}
        stale = ""
        for path, old, new in edits:
            text = overlay.get(path, repo.text(path))
            if text.count(old) != 1:
                stale = f"{path} carries {_clip(old, 60)!r} {text.count(old)} times, not once"
                break
            overlay[path] = text.replace(old, new)
        if stale:
            missed += 1
            print(f"MISSED | {finding} | {label} | the edit no longer applies: {stale}")
            continue
        changed = repo.with_overlay(overlay)
        caught = ""
        for fact in facts:
            touches = any(w.path in overlay for w in (*fact.stated, *fact.downstream))
            if not touches and not (set(overlay) & sources_read(repo, fact)):
                continue
            for result in check_fact(changed, fact):
                if result.verdict != "PASS":
                    caught = result.render()
                    break
            if caught:
                break
        if caught:
            print(f"CAUGHT | {finding} | {label} | {_clip(caught, 220)}")
        else:
            missed += 1
            print(f"MISSED | {finding} | {label} | every place still passes")
    print(f"mutation-test: {len(mutations) - missed} of {len(mutations)} break-it edits caught")
    return 1 if missed else 0


def main(argv: list[str]) -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 - a system python3 may be 3.9
        print(
            "check_facts: needs Python 3.11 or later; run it with the repository's "
            f"venv/bin/python (this is {sys.version_info[0]}.{sys.version_info[1]})",
            file=sys.stderr,
        )
        return 2
    # Every place and every truth has its own catch-all. This last one means
    # a failure outside them, such as a registry that will not import, still
    # ends in one scrubbed line and exit 2, never a traceback that prints the
    # interpreter's and the script's absolute paths (PR118-V04).
    try:
        return _run(argv)
    except Exception as exc:  # noqa: BLE001 - one line, no traceback, exit 2
        print(f"check_facts: stopped before any verdict: {_reason(exc, None)}", file=sys.stderr)
        return 2


def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--all", action="store_true", help="also print PASS lines")
    parser.add_argument("--map", action="store_true", help="print the downstream map")
    parser.add_argument("--from", dest="source", help="only facts whose source is this path")
    parser.add_argument("--reference", help="the data-engineering repository")
    parser.add_argument("--root", help="the checkout to check (default: this one)")
    parser.add_argument("--self-test", action="store_true", help="prove every check can fail")
    parser.add_argument(
        "--mutation-test",
        action="store_true",
        help="apply the registry's break-it edits and prove each one fails the check",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else DEFAULT_ROOT
    try:
        reference = find_reference(root, args.reference)
    except RegistryError as exc:
        print(f"check_facts: {exc}", file=sys.stderr)
        return 2
    repo = Repo(root, reference)
    facts = load_registry()
    if args.source:
        # A fact is selected when its truth reads the file, not only when the
        # file is its main source: the tool-layer map reads every tool module.
        wanted = args.source.removeprefix("./")
        # A mistyped path must not read as "nothing restates it", exit 0,
        # which `/verify` counts as a pass (PR118-V06). An existing file no
        # fact reads still exits 0 below.
        missing = _from_path_problem(repo, wanted)
        if missing:
            print(f"check_facts: --from {missing}; nothing was checked", file=sys.stderr)
            return 2
        facts = tuple(f for f in facts if wanted in sources_read(repo, f))
        if not facts:
            print(f"check_facts: no fact is computed from {wanted}, so nothing restates it")
            return 0
    if args.self_test:
        return self_test(repo, facts)
    if args.mutation_test:
        import facts_registry

        return mutation_test(repo, facts, facts_registry.MUTATIONS)
    if args.map:
        return print_map(repo, facts)
    return run_checks(repo, facts, args.all)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
