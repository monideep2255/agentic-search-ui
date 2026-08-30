"""Offline golden-dataset replay, and the `rubric_score` write (T-5.1-09).

Depends on:
    - system_03_search_agent.eval.dataset
    - system_03_search_agent.eval.rubric_grader
    - system_03_search_agent.eval.aggregate
    - system_03_search_agent.eval.coverage
    - system_03_search_agent.eval.cost_report
    - system_03_search_agent.data.session (session_scope), for the write only

Reads:
    - The golden dataset file, and a set of `RunRecord`s captured from traces.

Writes:
    - `interactions.rubric_score`, and only that column.

## The field this module exists to fill

`feedback/rubric.py` computes `rubric_outcome` on every live row at zero LLM
cost, and its docstring states that `rubric_score` (0 to 16) "is populated
only by build phase 5.1's offline replay". Section 15 draws the same line.
This is that replay. Until now `rubric_score` had no writer anywhere in the
system and was `None` on every row ever captured.

## Why the pure part and the write are separate functions

`replay()` computes and returns. `apply_rubric_scores()` writes. Nothing
forces them to be split, and splitting them is what lets the entire scoring
path be exercised with no database at all, which matters because the scoring
is the part that can be subtly wrong and the write is the part that is
merely I/O.

It also keeps the write honest about idempotency. `.claude/rules/
production-standards.md` requires any code the agent loop may run more than
once to be repeat-safe. Replay is re-run every time the dataset or the
grader changes, over the same traces, so the write is an UPDATE keyed on
`trace_id` that sets a computed value. Running it twice sets the same score
twice; it never accumulates and never double-counts.

## What it deliberately does not do

It never writes `rubric_outcome`. That column already has a writer on the
live path, and a second writer for the same column is how build phase
4.13's F-4.13-FV-01 shipped: two writers keyed differently, one silently
overwriting the other. One column, one writer, and this module owns only
the one that had none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from system_03_search_agent.eval.aggregate import (
    aggregate_dataset,
    hard_fail_free_rate,
)
from system_03_search_agent.eval.cost_report import CostReport, cost_report
from system_03_search_agent.eval.coverage import CoverageReport, coverage_report
from system_03_search_agent.eval.dataset import GoldenDataset, load_golden_dataset
from system_03_search_agent.eval.rubric_grader import Judge, RubricResult, grade_run
from system_03_search_agent.eval.trace_source import RunRecord


@dataclass(frozen=True)
class GradedRun:
    """One run, its score, and the join key that lets it be written back."""

    trace_id: str
    query_id: str
    result: RubricResult

    @property
    def score(self) -> int:
        return self.result.total


@dataclass(frozen=True)
class ReplayReport:
    """Everything one replay pass measured."""

    graded: list[GradedRun]
    metrics: dict[str, float]
    coverage: CoverageReport
    cost: CostReport
    k: int
    queries_in_dataset: int
    queries_scored: int
    unscored_query_ids: list[str] = field(default_factory=list)

    @property
    def scored_fraction(self) -> float:
        if not self.queries_in_dataset:
            return 0.0
        return self.queries_scored / self.queries_in_dataset

    def summary_lines(self) -> list[str]:
        """The honest headline, denominator first.

        The denominator leads deliberately. Reporting "pass@3 100 percent"
        while 6 of 50 questions were never run is the shape of dishonesty
        this whole harness exists to prevent, and putting the coverage of
        the run itself at the top makes it impossible to quote the score
        without it.
        """
        lines = [
            (
                f"scored {self.queries_scored} of {self.queries_in_dataset} "
                f"golden queries at k={self.k}"
            ),
        ]
        if self.unscored_query_ids:
            lines.append(
                "NOT SCORED (no run records supplied): "
                + ", ".join(self.unscored_query_ids)
            )
        lines.extend(
            [
                f"pass@{self.k}:      {self.metrics['pass_at_k']:.1%}",
                f"pass^{self.k}:      {self.metrics['pass_caret_k']:.1%}",
                (
                    "hard-fail free: "
                    f"{self.metrics['hard_fail_free_rate']:.1%} (target 100%)"
                ),
                (
                    f"concept coverage:   {self.coverage.concept_coverage:.0%} "
                    "(diagnostic, gates nothing)"
                    if self.coverage.is_measurable
                    else "concept coverage:   NOT MEASURABLE from these runs"
                ),
                (
                    f"predicate coverage: {self.coverage.predicate_coverage:.0%} "
                    "(diagnostic, gates nothing)"
                    if self.coverage.is_measurable
                    else "predicate coverage: NOT MEASURABLE from these runs "
                    "(no Cypher on the trace: ToolResultPayload carries none)"
                ),
                f"cost: ${self.cost.total_usd:.4f} over {self.cost.runs} runs",
            ]
        )
        return lines


class HarnessParkedError(RuntimeError):
    """Raised when the parked harness is run without acknowledging that.

    Build phase 5.2 was PARKED on 2026-08-30 after four review rounds
    returned FAIL. The harness's own suite is GREEN with every defect
    live, so nothing about running it looks wrong, which is exactly why a
    docstring is not enough.

    `system-design-patterns` pattern 8: the strongest constraint is
    removing the ability, not asking the caller not to use one. A comment
    is a request the next reader can miss; this cannot be missed.

    THE SPECIFIC DEFECT, so a caller can judge for themselves: grounding
    compares the agent's prose against the agent's OWN citation payload,
    because a trace carries the agent's description of a record rather
    than the record. An answer about a gene that does not exist, citing a
    record that does not exist, scored 16 of 16 with no hard-fail.

    Read `tracker/phase_5.2.md` before passing `acknowledge_parked=True`.
    """


def replay(
    *,
    records: Sequence[RunRecord],
    dataset: GoldenDataset | None = None,
    judge: Judge | None = None,
    k: int = 3,
    acknowledge_parked: bool = False,
) -> ReplayReport:
    """Grade every supplied run against the golden dataset.

    Records are matched to golden rows by `query_id`. A record naming a
    query the dataset does not contain is an error rather than a skip: it
    means the traces and the dataset have drifted apart, and silently
    dropping such a record would let a replay report a clean pass over a
    set that no longer matches what was run.
    """
    if not acknowledge_parked:
        raise HarnessParkedError(
            "build phase 5.2 is PARKED and this harness is known broken. Its "
            "own suite is green with every defect live. Grounding measures "
            "self-consistency rather than grounding, so a fabricated answer "
            "citing a fabricated record scores full marks. Read "
            "tracker/phase_5.2.md, then pass acknowledge_parked=True if you "
            "still want a number from it."
        )
    dataset = dataset or load_golden_dataset()
    by_id = {q.id: q for q in dataset.queries}

    graded: list[GradedRun] = []
    outcomes: dict[str, list[str]] = {}
    per_run_hard_fails: list[list[str]] = []

    for record in records:
        query = by_id.get(record.query_id)
        if query is None:
            raise KeyError(
                f"run record {record.trace_id} names query_id "
                f"{record.query_id!r}, which is not in the golden dataset. The "
                "traces and the dataset have drifted apart."
            )
        result = grade_run(record=record, query=query.as_dict(), judge=judge)
        graded.append(
            GradedRun(
                trace_id=record.trace_id, query_id=record.query_id, result=result
            )
        )
        outcomes.setdefault(record.query_id, []).append(result.aggregate_token)
        per_run_hard_fails.append(result.hard_fails)

    # Only queries with at least k samples can report a k-sample figure. The
    # rest are named as unscored rather than averaged in at whatever depth
    # they happen to have, which would report a k-sample reliability number
    # that was never measured.
    scorable = {qid: toks for qid, toks in outcomes.items() if len(toks) >= k}
    unscored = sorted(set(by_id) - set(scorable))

    metrics = aggregate_dataset(scorable, k=k)
    metrics["hard_fail_free_rate"] = hard_fail_free_rate(per_run_hard_fails)

    return ReplayReport(
        graded=graded,
        metrics=metrics,
        coverage=coverage_report(records=records),
        cost=cost_report(records=records),
        k=k,
        queries_in_dataset=len(by_id),
        queries_scored=len(scorable),
        unscored_query_ids=unscored,
    )


def rubric_score_updates(report: ReplayReport) -> dict[str, int]:
    """The `trace_id` to score mapping, as a pure value.

    Separated from the write so the mapping can be inspected, diffed and
    tested without a database. The last graded run wins for a repeated
    `trace_id`, which cannot arise from one replay pass since a trace is one
    run, and is made explicit rather than left to dict ordering.
    """
    updates: dict[str, int] = {}
    for run in report.graded:
        updates[run.trace_id] = run.score
    return updates


def apply_rubric_scores(updates: dict[str, int]) -> int:
    """Write `rubric_score` onto existing `interactions` rows. Returns the count.

    IDEMPOTENT BY CONSTRUCTION: an UPDATE that sets a computed value on a row
    selected by its primary join key. Running it twice sets the same value
    twice. It never inserts, so a replay cannot manufacture interaction rows
    and inflate the counts the daily caps read.

    A `trace_id` with no matching row is skipped rather than created, and the
    return value is the number of rows actually updated, so a caller can see
    the difference between "wrote 50" and "matched 3".
    """
    from sqlalchemy import update as sql_update

    from system_03_search_agent.data.models import Interaction
    from system_03_search_agent.data.session import session_scope

    if not updates:
        return 0

    written = 0
    with session_scope() as db:
        for trace_id, score in updates.items():
            result = db.execute(
                sql_update(Interaction)
                .where(Interaction.trace_id == trace_id)
                .values(rubric_score=score)
            )
            written += int(result.rowcount or 0)
    return written


def render_report(report: ReplayReport) -> str:
    """The replay's own output, for a terminal or a log."""
    lines = list(report.summary_lines())
    if report.coverage.untouched_predicates:
        lines.append("")
        lines.append(
            "predicates the set never exercises: "
            + ", ".join(report.coverage.untouched_predicates)
        )
    failures = [g for g in report.graded if g.result.outcome == "fail"]
    if failures:
        lines.append("")
        lines.append("failing runs:")
        for run in failures:
            reason = ", ".join(run.result.hard_fails) or f"scored {run.score}/16"
            lines.append(f"  {run.query_id:<8}{run.trace_id:<14}{reason}")
    return "\n".join(lines)
