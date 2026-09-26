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
  FAIL   it does not: the page or document is stale.
  GAP    the source could not be read here, for example the data-engineering
         repository behind `reference/` is not checked out. The place is
         unchecked, so the run does not pass.
  ERROR  the registry no longer matches the code, or a source cannot be read
         without running it: a pattern finds nothing, a place reads as
         nothing, a constant is gone or is not a literal. The registry must
         be updated, which is the point: a fact cannot silently stop being
         checked. When a fact's truth cannot be computed, every one of its
         places gets its own ERROR line, so none is silently dropped.

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
    checked until the registry names it.
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
  check_facts.py --self-test      prove every check can pass and can fail; exits 1
                                  unless every reader is proven, so run it with
                                  the reference repository present

Run it with the repository's virtual environment, `venv/bin/python`, or any
Python 3.11 or later. An older Python is refused with exit code 2.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
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
PRIMITIVE_NAMES = frozenset({"_dispatch_tier_call", "call_jev"})
GRAPH_MODULE_PATH = f"{PACKAGE_DIR}/core/graph.py"


def _module_name(rel: str) -> str:
    dotted = rel[len("src/") : -len(".py")].replace("/", ".")
    return dotted.removesuffix(".__init__")


class CallGraph:
    """A static call graph of the package, enough to answer "does this loop
    step reach a model call, and on which tier".

    A model call is `harness.call_tier(...)` or `_dispatch_tier_call(...)`,
    whose string argument names the tier, or `call_jev(...)`, the classifier.
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
                    if called == "call_jev":
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
        sorted((k, hashlib.sha256(v.encode()).hexdigest()) for k, v in repo.overlay.items())
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
    """

    place: str
    path: str
    pattern: str
    cmp: Cmp = EXACT
    parse: Callable[[re.Match[str]], Any] = GROUP_1
    collect: Callable[[list[Any]], Any] | None = None
    flags: int = 0


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
    text = repo.text(where.path)
    matches = list(re.finditer(where.pattern, text, where.flags))
    if not matches:
        raise RegistryError(
            f"{repo.display(where.path)}: pattern {where.pattern!r} finds nothing, so the "
            "place no longer says this where the registry looks; update the registry"
        )
    found = []
    for match in matches:
        line = line_of(text, match.start())
        try:
            value = where.parse(match)
        except Exception as exc:  # noqa: BLE001 - any parse failure is one ERROR line
            raise RegistryError(
                f"{repo.display(where.path)}:{line}: cannot read {_clip(match.group(0), 80)!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from None
        if _empty(value):
            raise RegistryError(
                f"{repo.display(where.path)}:{line}: reads as nothing, so it cannot be judged; "
                "the page no longer says what the registry expects there"
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
    text = str(exc) if isinstance(exc, (Gap, RegistryError)) else f"{type(exc).__name__}: {exc}"
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
    return 1 if failures else 0


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
    if args.map:
        return print_map(repo, facts)
    return run_checks(repo, facts, args.all)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
