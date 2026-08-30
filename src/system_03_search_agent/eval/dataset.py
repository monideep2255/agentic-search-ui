"""The golden dataset: schema, loader and the anti-circularity guard (T-5.1-01).

Depends on:
    - Nothing beyond the standard library.

Reads:
    - `eval/golden/golden_dataset.json`, a versioned file in the repository.

Writes:
    - Nothing.

## Why the loader refuses rows rather than warning about them

Product-owner decision, 2026-08-30 (`DECISIONS.md`): the 50 expected answers
are CONSTRAINT ASSERTIONS authored independently of the agent, never full
reference prose and never the agent's own curated output.

That decision is only worth something if it is structural. A convention that
expected answers are authored independently is exactly the kind of thing that
erodes under deadline, and the erosion is invisible: a row curated from agent
output looks identical to a row read from NCBI. So `authored_from` is a
required field with a closed vocabulary, and `agent_output` is refused by the
loader with the word "circular" in the message.

The failure this prevents, in one sentence: a wrong expected answer certifies
a wrong agent forever, and it does so behind a green gate.

## Why the dataset is a file and not a table

Same reason `.claude/rules/prompt-cache-discipline.md` forbids a live
per-request database read for the few-shot pool. A changing source defeats
reproducibility even when it happens to return the same content, and an eval
whose questions can change between runs cannot attribute a score change to
the agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from system_03_search_agent.tools.cypher_schemas import QueryClass

GOLDEN_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "eval" / "golden" / "golden_dataset.json"
)

# A row's expected answer may be established from a live source record, or
# from the locked planning documents that already fix it (the seven must-pass
# competency questions carry their own definitions). It may NEVER be
# established by asking the agent under test.
_ALLOWED_AUTHORED_FROM = frozenset({"live_source", "locked_requirements"})
_REFUSED_AUTHORED_FROM = frozenset({"agent_output"})

_EXPECTED_OUTCOMES = frozenset({"answer", "refuse", "ask", "flag"})

# Taken from the enum, never re-typed. A second hand-maintained copy of a
# vocabulary is the defect F-3.0-01 filed, where the frontend's own copy
# silently rejected a value the backend had just added.
_QUERY_CLASSES = frozenset(member.value for member in QueryClass)
_KNOWN_HARD_FAILS = frozenset({"provenance", "safety", "assembly_context"})

# The retrieval-shape taxonomy, product-owner decision 2026-08-30. It is
# ORTHOGONAL to wedge type and to query class, and it exists because the
# three shapes succeed and fail differently:
#
#   kiss      Known Item Search. One question, one exact answer. "What
#             diseases does BRCA1 cause?" The failure mode is being WRONG,
#             so the metric that matters is precision.
#   kisses    The plural. One question, ALL the known results. "Give me
#             every paper on cancer." The failure mode is being INCOMPLETE,
#             and worse, incomplete without saying so, so the metric that
#             matters is recall plus honest disclosure of truncation.
#   discovery A discussion. An open question, then another, each turn
#             depending on the last. "Tell me about the tree of life", then
#             where bacteria sit, then a specific organism. The failure mode
#             is LOSING THE THREAD, so the metric that matters is whether
#             turn four still knows what turn one established.
#
# Grading all three against one criterion would flatter the wrong thing: a
# KISS row scored on recall rewards padding, and a KISSES row scored on
# precision rewards answering with one row and stopping.
_SEARCH_CATEGORIES = frozenset({"kiss", "kisses", "discovery"})

# A KISSES row must forbid undisclosed truncation, always. F-2.2-06 records
# a truncated answer that disclosed the cut but not its scale, and on an
# exhaustive question "here are some of them" without a count is the exact
# failure the category exists to measure.
_TRUNCATION_CONSTRAINT = "undisclosed_truncation"

_REQUIRED_ROW_FIELDS = (
    "id",
    "question",
    "wedge_type",
    "query_class",
    "expected_outcome",
    "provenance",
)
_REQUIRED_PROVENANCE_FIELDS = (
    "authored_from",
    "source",
    "read_on",
    "signed_off_by",
    "sign_off_bound",
)


class DatasetValidationError(ValueError):
    """A golden dataset row that cannot be trusted to grade anything.

    Raised rather than logged. A dataset that loads with a bad row is worse
    than one that refuses to load, because the bad row still grades.
    """


@dataclass(frozen=True)
class Provenance:
    """Where a row's expected values came from, and what the sign-off covers.

    `sign_off_bound` is required and must be non-empty. A sign-off with no
    stated bound reads to the next person as a clinical review that never
    happened, which is the playbook's own flagged gap left open rather than
    narrowed.
    """

    authored_from: str
    source: str
    read_on: str
    signed_off_by: str
    sign_off_bound: str


@dataclass(frozen=True)
class GoldenQuery:
    """One question and the constraints its answer must satisfy.

    It pins what must be TRUE. It deliberately does not pin how it is said:
    the playbook's 8-point rubric grades that, and pinning prose would break
    the fixture every time the agent rewords a correct answer.
    """

    id: str
    question: str
    wedge_type: str
    query_class: str
    expected_outcome: str
    provenance: Provenance
    # See `_SEARCH_CATEGORIES` for what the three mean and why they are
    # graded differently. Required on every row: a row with no category
    # cannot be scored against the right metric.
    search_category: str = "kiss"
    # Turns 2..n of a discovery thread. Empty for kiss and kisses.
    follow_ups: list[str] = field(default_factory=list)
    # More than one outcome is correct for some questions. A bare number is
    # equally well handled by asking what it refers to or by refusing it, and
    # pinning one of the two would fail correct behaviour, which is the same
    # trap that ruled out pinning reference prose. Defaults to exactly
    # `expected_outcome`, so a row that means one thing says one thing.
    acceptable_outcomes: list[str] = field(default_factory=list)
    personas: list[int] = field(default_factory=list)
    must_resolve: list[str] = field(default_factory=list)
    must_cite: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    hard_fails_applicable: list[str] = field(default_factory=list)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        """The mapping shape the grader and hard-fail checker read."""
        return {
            "id": self.id,
            "question": self.question,
            "wedge_type": self.wedge_type,
            "query_class": self.query_class,
            "expected_outcome": self.expected_outcome,
            "search_category": self.search_category,
            "follow_ups": list(self.follow_ups),
            "acceptable_outcomes": list(self.acceptable_outcomes),
            "personas": list(self.personas),
            "must_resolve": list(self.must_resolve),
            "must_cite": list(self.must_cite),
            "forbidden": list(self.forbidden),
            "hard_fails_applicable": list(self.hard_fails_applicable),
        }


@dataclass(frozen=True)
class GoldenDataset:
    version: int
    queries: list[GoldenQuery]

    def by_id(self, query_id: str) -> GoldenQuery:
        for query in self.queries:
            if query.id == query_id:
                return query
        raise KeyError(query_id)


def _validate_provenance(row_id: str, raw: Any) -> Provenance:
    if not isinstance(raw, dict):
        raise DatasetValidationError(
            f"row {row_id}: provenance must be an object, got {type(raw).__name__}"
        )

    for name in _REQUIRED_PROVENANCE_FIELDS:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            if name == "sign_off_bound":
                raise DatasetValidationError(
                    f"row {row_id}: provenance.sign_off_bound is required and must "
                    "state what the sign-off does NOT cover. A sign-off with no "
                    "stated bound reads as a clinical review that never happened."
                )
            raise DatasetValidationError(
                f"row {row_id}: provenance.{name} is required and must be non-empty"
            )

    authored_from = raw["authored_from"]
    if authored_from in _REFUSED_AUTHORED_FROM:
        raise DatasetValidationError(
            f"row {row_id}: authored_from={authored_from!r} is refused as CIRCULAR. "
            "An expected answer taken from the agent under test certifies that "
            "agent's current behaviour as correct, permanently, behind a green "
            "gate. Establish the constraint from a live source record instead."
        )
    if authored_from not in _ALLOWED_AUTHORED_FROM:
        raise DatasetValidationError(
            f"row {row_id}: authored_from={authored_from!r} is not one of "
            f"{sorted(_ALLOWED_AUTHORED_FROM)}"
        )

    return Provenance(
        authored_from=authored_from,
        source=raw["source"],
        read_on=raw["read_on"],
        signed_off_by=raw["signed_off_by"],
        sign_off_bound=raw["sign_off_bound"],
    )


def _validate_row(raw: Any) -> GoldenQuery:
    if not isinstance(raw, dict):
        raise DatasetValidationError(
            f"every query must be an object, got {type(raw).__name__}"
        )

    row_id = str(raw.get("id") or "<no id>")

    for name in _REQUIRED_ROW_FIELDS:
        if name not in raw:
            raise DatasetValidationError(f"row {row_id}: missing required {name!r}")

    # `.get`, not `[...]`. There are TWO paths to a missing provenance:
    # the required-field loop above, and this call. Indexing here made the
    # second path raise a bare KeyError, so a caller who reached it got an
    # unusable error instead of one naming the row and the field. Found by
    # the mutation harness, which relaxed the first path and exposed the
    # second (F-5.1-04).
    provenance = _validate_provenance(row_id, raw.get("provenance"))

    expected_outcome = raw["expected_outcome"]
    if expected_outcome not in _EXPECTED_OUTCOMES:
        raise DatasetValidationError(
            f"row {row_id}: expected_outcome={expected_outcome!r} is not one of "
            f"{sorted(_EXPECTED_OUTCOMES)}"
        )

    query_class = raw["query_class"]
    if query_class not in _QUERY_CLASSES:
        raise DatasetValidationError(
            f"row {row_id}: query_class={query_class!r} is not one of "
            f"{sorted(_QUERY_CLASSES)}"
        )

    acceptable = list(raw.get("acceptable_outcomes") or [expected_outcome])
    unknown_outcomes = set(acceptable) - _EXPECTED_OUTCOMES
    if unknown_outcomes:
        raise DatasetValidationError(
            f"row {row_id}: unknown acceptable_outcomes {sorted(unknown_outcomes)}"
        )
    if expected_outcome not in acceptable:
        raise DatasetValidationError(
            f"row {row_id}: expected_outcome={expected_outcome!r} is missing from "
            f"acceptable_outcomes {acceptable}. The primary expectation must be "
            "one of the accepted ones, or the row contradicts itself."
        )

    search_category = raw.get("search_category")
    if search_category not in _SEARCH_CATEGORIES:
        raise DatasetValidationError(
            f"row {row_id}: search_category={search_category!r} is not one of "
            f"{sorted(_SEARCH_CATEGORIES)}"
        )

    follow_ups = list(raw.get("follow_ups") or [])
    if search_category == "discovery" and not follow_ups:
        raise DatasetValidationError(
            f"row {row_id}: a discovery row with no follow_ups is not a "
            "discovery thread. The category exists to measure whether the "
            "system holds a thread across turns, and one turn cannot show that."
        )
    if search_category != "discovery" and follow_ups:
        raise DatasetValidationError(
            f"row {row_id}: search_category={search_category!r} carries "
            f"{len(follow_ups)} follow_ups. Only a discovery row is graded "
            "across turns, so these would never be run."
        )

    hard_fails = list(raw.get("hard_fails_applicable") or [])
    unknown = set(hard_fails) - _KNOWN_HARD_FAILS
    if unknown:
        raise DatasetValidationError(
            f"row {row_id}: unknown hard_fails_applicable {sorted(unknown)}, "
            f"expected a subset of {sorted(_KNOWN_HARD_FAILS)}"
        )

    # A row expecting an answer that pins nothing it must cite grades
    # nothing. It would pass against any fluent output, which is the
    # vacuous-arm shape at dataset level rather than at test level.
    if expected_outcome == "answer" and not raw.get("must_cite"):
        raise DatasetValidationError(
            f"row {row_id}: expected_outcome='answer' with an empty must_cite "
            "pins nothing. Such a row passes against any fluent answer."
        )

    forbidden = list(raw.get("forbidden") or [])
    if search_category == "kisses" and _TRUNCATION_CONSTRAINT not in forbidden:
        raise DatasetValidationError(
            f"row {row_id}: a kisses row must forbid {_TRUNCATION_CONSTRAINT!r}. "
            "An exhaustive question answered with an undisclosed subset is a "
            "confident wrong answer, not a partial one."
        )

    return GoldenQuery(
        id=raw["id"],
        question=raw["question"],
        wedge_type=raw["wedge_type"],
        query_class=raw["query_class"],
        expected_outcome=expected_outcome,
        provenance=provenance,
        acceptable_outcomes=acceptable,
        personas=list(raw.get("personas") or []),
        must_resolve=list(raw.get("must_resolve") or []),
        must_cite=list(raw.get("must_cite") or []),
        forbidden=forbidden,
        search_category=search_category,
        follow_ups=follow_ups,
        hard_fails_applicable=hard_fails,
        notes=str(raw.get("notes") or ""),
    )


def load_golden_dataset(path: Path | str = GOLDEN_DATASET_PATH) -> GoldenDataset:
    """Load and validate the versioned golden dataset.

    Every row is validated. The first bad row raises, rather than the loader
    returning the good ones and reporting a count, because a partially loaded
    eval set silently changes the denominator of every metric computed from
    it.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetValidationError(
            f"golden dataset not found at {path}. It is a versioned file in the "
            "repository, never a live database read."
        ) from exc
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise DatasetValidationError(f"{path}: top level must be an object")

    version = raw.get("version")
    if not isinstance(version, int):
        raise DatasetValidationError(f"{path}: an integer 'version' is required")

    rows = raw.get("queries")
    if not isinstance(rows, list):
        raise DatasetValidationError(f"{path}: 'queries' must be a list")

    queries = [_validate_row(row) for row in rows]

    seen: set[str] = set()
    for query in queries:
        if query.id in seen:
            raise DatasetValidationError(f"duplicate query id {query.id!r}")
        seen.add(query.id)

    return GoldenDataset(version=version, queries=queries)
