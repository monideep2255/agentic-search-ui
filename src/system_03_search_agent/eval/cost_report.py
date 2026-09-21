"""The cost tracking report (T-5.1-08).

Depends on:
    - system_03_search_agent.eval.trace_source (RunRecord)

Reads / Writes:
    - Nothing. It summarises cost values build phase 5.0 already records on
      each trace; it never re-runs anything to measure them.

## Why a report and not a live dashboard

Section 25's row names "the cost tracking dashboard". What that has to be in
v1 is a thing that answers "what does a golden-set run cost, and which
questions are the expensive ones", and that answer is a function over
records this project already captures. A served page with its own endpoint,
auth surface and refresh path would be new attack surface and new tests for
no additional answer.

## The number this exists to make visible

`.claude/rules/system-design-patterns.md` pattern 4 makes cost control
safety-critical, with a per-query cap, a per-user daily cap and a
system-wide daily cap. The eval harness is the single largest deliberate
cost event this project runs: 50 queries at k samples each, with real model
calls and real live-API calls. A harness that cannot state its own bill is
one bad k away from tripping the system-wide cap and taking real users down
with it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from system_03_search_agent.eval.trace_source import RunRecord


@dataclass(frozen=True)
class QueryCost:
    query_id: str
    runs: int
    total_usd: float
    mean_usd: float
    max_usd: float
    mean_latency_ms: float


@dataclass(frozen=True)
class CostReport:
    total_usd: float
    runs: int
    mean_usd_per_run: float
    per_query: tuple[QueryCost, ...]

    @property
    def most_expensive(self) -> tuple[QueryCost, ...]:
        """Descending by total spend, so the top of the list is where to look."""
        return tuple(sorted(self.per_query, key=lambda q: -q.total_usd))

    def projected_usd(self, *, queries: int, k: int) -> float:
        """What a full run WOULD cost at this measured mean.

        Stated as a projection rather than a measurement, and named so, since
        the whole reason it exists is to be checked against the caps BEFORE
        the run rather than explained after it.
        """
        return self.mean_usd_per_run * queries * k


def cost_report(*, records: Sequence[RunRecord]) -> CostReport:
    """Summarise spend across a set of graded runs."""
    if not records:
        return CostReport(total_usd=0.0, runs=0, mean_usd_per_run=0.0, per_query=())

    by_query: dict[str, list[RunRecord]] = {}
    for record in records:
        by_query.setdefault(record.query_id, []).append(record)

    per_query: list[QueryCost] = []
    for query_id, runs in sorted(by_query.items()):
        costs = [r.cost_usd for r in runs]
        latencies = [r.latency_ms for r in runs]
        per_query.append(
            QueryCost(
                query_id=query_id,
                runs=len(runs),
                total_usd=sum(costs),
                mean_usd=sum(costs) / len(costs),
                max_usd=max(costs),
                mean_latency_ms=sum(latencies) / len(latencies),
            )
        )

    total = sum(r.cost_usd for r in records)
    return CostReport(
        total_usd=total,
        runs=len(records),
        mean_usd_per_run=total / len(records),
        per_query=tuple(per_query),
    )


def render_cost_report(report: CostReport) -> str:
    """A plain-text table, the dashboard's v1 surface."""
    lines = [
        f"runs: {report.runs}",
        f"total: ${report.total_usd:.4f}",
        f"mean per run: ${report.mean_usd_per_run:.4f}",
        "",
        f"{'query':<12}{'runs':>6}{'total':>12}{'mean':>12}{'max':>12}{'ms':>10}",
    ]
    for query in report.most_expensive:
        lines.append(
            f"{query.query_id:<12}{query.runs:>6}"
            f"{query.total_usd:>12.4f}{query.mean_usd:>12.4f}"
            f"{query.max_usd:>12.4f}{query.mean_latency_ms:>10.0f}"
        )
    return "\n".join(lines)
