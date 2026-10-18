"""Compare Jev and the guard tier on every decision the loop makes, offline.

Build phase 8.6, T-8.6-03 (DECISIONS.md 2026-09-25: "the comparison of the
two moves off the live path to a script run over each golden run's
questions"). Since T-8.6-01 the live loop asks Jev alone and the guard tier
only when Jev fails, so this script is where the two are compared. No live
path calls it, nor the function it uses, `harness.decide.compare_models`;
`tests/system_03_search_agent/harness/test_decide.py` asserts that nothing
under `src/` besides `decide.py` names that function.

What it does, for each golden question id given:

1. Builds the question's first-turn state the way `core/run.py` does, with
   no session memory.
2. Runs the loop's own Guardrail, Think and Plan steps, never Act or Write,
   so no answer is ever built and no search is run for one. Every `decide`
   the loop imported is swapped for a recorder first.
3. The recorder asks BOTH Jev and the guard tier the decision the loop just
   asked for, over the same bounded state and description, at the same time
   (`compare_models`). It records both picks and hands the loop the record
   Jev-mode `decide()` returns for those picks, so the loop takes the path it
   takes on develop. A comparison the loop stops waiting for (it cancels the
   literature decision once a gene resolves) still finishes and is recorded.
4. Writes a markdown report: one agreement table per decision point, every
   disagreement with Jev's confidence and probabilities, and each question's
   decisions.

Coverage, stated so a reader can tell what this misses:

- Exercises: every decision the loop asks through `decide()` on a question's
  first turn, from whichever module imported it, so a decision point added
  later is compared without editing this script.
- Omits: the Write step's reworded-sentence check, which needs the full
  answer this script never builds; follow-up questions, whose relevancy
  state carries the previous question (every run here is a first turn);
  decisions the loop does not ask for a question (the tables count only
  decisions actually asked); and any model call that does not go through
  `decide()`, such as the injection classifier and Think's classification,
  which still run but are not compared.

Spend is bounded in code. Every question runs under a per-query cost cap of
`--budget-usd` divided by the number of questions, which the harness checks
before every model call, so a run cannot spend past the budget. Below $0.02
per question the cap would refuse Think's own call, so the script refuses
to start instead. The report states the spend the harness measured.

Credentials and model settings come from the repository's `.env`, found from
this file's own path: this checkout's root, or for a git worktree the main
checkout's root. No value is ever printed or written.

Usage (from the repository root):

    python3 testing/Developer/scripts/compare_classifiers.py G-003 G-008 --out report.md
    python3 testing/Developer/scripts/compare_classifiers.py --all --budget-usd 1.50 --out report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_PATH = REPO_ROOT / "eval" / "golden" / "golden_dataset.json"

#: Below this per-question cap the harness refuses Think's own plan-tier call
#: (its pre-flight estimate is about $0.0125), and the run would compare
#: nothing past the guardrail.
MIN_PER_QUESTION_CAP_USD = 0.02

DEFAULT_BUDGET_USD = 0.50


# ---------------------------------------------------------------- environment


def _env_file() -> Path | None:
    """This checkout's `.env`, else the main checkout's for a git worktree."""
    own = REPO_ROOT / ".env"
    if own.is_file():
        return own
    try:
        common = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    main = Path(common).parent / ".env"
    return main if main.is_file() else None


def _load_env() -> None:
    """Read `.env` into the environment without overriding what is set, and
    without printing a single value."""
    path = _env_file()
    if path is None:
        sys.exit("No .env beside this checkout or its main checkout; OPENROUTER_API_KEY is needed.")
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("OPENROUTER_API_KEY is not set in .env; both models are reached through it.")
    # Keep this offline run out of traces and the tool audit log, as the
    # local live-run scripts do, and make the loop take develop's Jev paths.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
    os.environ["CLASSIFIER_PROVIDER"] = "jev"


# ---------------------------------------------------------------- the run


@dataclass
class _Row:
    """One decision the loop asked for, and what each model picked."""

    golden_id: str
    point: str
    comparison: Any = None  # harness.decide.ModelComparison, once both answered
    loop_cancelled: bool = False
    error: str | None = None


@dataclass
class _QuestionRun:
    golden_id: str
    question: str
    ended: str
    cost_usd: float
    seconds: float
    error: str | None = None


def _golden_questions(ids: Sequence[str], take_all: bool) -> list[tuple[str, str]]:
    rows = json.loads(GOLDEN_PATH.read_text())["queries"]
    by_id = {row["id"]: row["question"] for row in rows}
    if take_all:
        return [(row["id"], row["question"]) for row in rows]
    unknown = [golden_id for golden_id in ids if golden_id not in by_id]
    if unknown:
        sys.exit(f"Not in {GOLDEN_PATH.relative_to(REPO_ROOT)}: {', '.join(unknown)}")
    return [(golden_id, by_id[golden_id]) for golden_id in ids]


def _ended(final_state: dict[str, Any]) -> str:
    """Where the loop stopped, in the person's terms."""
    if final_state.get("daily_cap_declined"):
        return "declined by a daily cap"
    if final_state.get("guard_refused"):
        return "refused at the guardrail"
    if final_state.get("cap_exceeded"):
        return "stopped by the cost cap"
    if final_state.get("step_error") is not None:
        return "a step failed"
    if final_state.get("clarification_needed"):
        return "asked a question back"
    planned = len(final_state.get("tool_calls") or [])
    return f"planned {planned} tool call{'s' if planned != 1 else ''}"


def _install_recorder(
    rows: list[_Row], pending: list[asyncio.Task[Any]], current: dict[str, str]
) -> tuple[list[str], Callable[[], None]]:
    """Swap every module-level `decide` the loop imported for the recorder.

    Returns the names of the modules patched, for the report, and an
    `uninstall` that puts each module's original `decide` back. The caller
    must call it however the run ends: a module left patched sends every
    later `decide` in the same process through the recorder (finding K-14,
    which a test in another folder caught).
    """
    from system_03_search_agent.harness import decide as decide_module

    original = decide_module.decide

    async def _compare(row: _Row, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        try:
            row.comparison = await decide_module.compare_models(*args, **kwargs)
        except Exception as exc:
            # Recorded, then re-raised to the loop, which treats a failed
            # decision as no decision, exactly as `_decide_point` does live.
            row.error = type(exc).__name__
            raise
        return row.comparison

    async def recording_decide(
        harness: Any,
        trace_id: str,
        point: str,
        state: str,
        options: Sequence[str],
        *,
        instructions: str | None = None,
        criteria: Any = None,
        default: str | None = None,
    ) -> Any:
        row = _Row(golden_id=current["id"], point=point)
        rows.append(row)
        task = asyncio.create_task(
            _compare(
                row,
                (harness, trace_id, point, state, options),
                {"instructions": instructions, "criteria": criteria},
            )
        )
        pending.append(task)
        try:
            comparison = await asyncio.shield(task)
        except asyncio.CancelledError:
            # The loop stopped waiting; the comparison itself runs on.
            row.loop_cancelled = True
            raise
        return comparison.live_record(default)

    patched: dict[str, Any] = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("system_03_search_agent") or name == decide_module.__name__:
            continue
        if getattr(module, "decide", None) is original:
            module.decide = recording_decide
            patched[name] = module

    def uninstall() -> None:
        for module in patched.values():
            if getattr(module, "decide", None) is recording_decide:
                module.decide = original

    return sorted(patched), uninstall


def _guardrail_think_plan(graph_module: Any) -> Any:
    """The loop's own first three steps, with Act and Write cut off."""
    from langgraph.graph import END, StateGraph

    from system_03_search_agent.core.state import GraphState

    graph = StateGraph(GraphState)
    graph.add_node("guardrail", graph_module.guardrail_node)
    graph.add_node("think", graph_module.think_node)
    graph.add_node("plan", graph_module.plan_node)
    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail", graph_module._route_after_guardrail, {"think": "think", "write": END, "end": END}
    )
    graph.add_conditional_edges("think", graph_module._route_after_think, {"plan": "plan", "write": END})
    graph.add_conditional_edges("plan", graph_module._route_after_plan, {"act": END, "write": END})
    return graph.compile()


async def _run(questions: list[tuple[str, str]], per_question_cap_usd: float) -> dict[str, Any]:
    os.environ["PER_QUERY_COST_CAP_USD"] = f"{per_question_cap_usd:.4f}"
    sys.path.insert(0, str(REPO_ROOT / "src"))

    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.harness.tiers import resolve_jev_model, resolve_model

    rows: list[_Row] = []
    pending: list[asyncio.Task[Any]] = []
    current = {"id": ""}
    patched, uninstall = _install_recorder(rows, pending, current)
    try:
        runs = await _run_questions(questions, rows, pending, current, graph_module)
    finally:
        uninstall()

    return {
        "rows": rows,
        "runs": runs,
        "patched": patched,
        "models": {
            "jev": resolve_jev_model(),
            "guard": resolve_model("guard"),
            "plan": resolve_model("plan"),
        },
    }


async def _run_questions(
    questions: list[tuple[str, str]],
    rows: list[_Row],
    pending: list[asyncio.Task[Any]],
    current: dict[str, str],
    graph_module: Any,
) -> list[_QuestionRun]:
    """Each question through Guardrail, Think and Plan, with the recorder in
    place. Split out of `_run` so the recorder is uninstalled on every exit."""
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.harness.call_budget import query_budget_scope
    from system_03_search_agent.harness.harness import Harness
    from system_03_search_agent.observability.audit import trace_id_scope

    steps = _guardrail_think_plan(graph_module)
    runs: list[_QuestionRun] = []
    for golden_id, question in questions:
        current["id"] = golden_id
        trace_id = f"compare-{golden_id}-{uuid.uuid4().hex[:8]}"
        harness = Harness(trace_id=trace_id)
        query = Query(
            text=question,
            session_id=f"compare-classifiers-{golden_id}",
            trace_id=trace_id,
            user_id=None,
            audience_depth="researcher",
        )
        state = {
            "query": query,
            "context": RequestContext(surface="rest_sse", session_memory=None),
            "harness": harness,
            "seq": 0,
            "events": [],
            "start_monotonic": time.monotonic(),
        }
        started = time.monotonic()
        error: str | None = None
        ended = "did not finish"
        with trace_id_scope(trace_id), query_budget_scope("lookup"):
            try:
                final_state = await steps.ainvoke(state)
                ended = _ended(final_state)
            except Exception as exc:  # noqa: BLE001 - one broken question must not end the run
                error = type(exc).__name__
            # Comparisons the loop stopped waiting for finish here, before
            # the next question, so every row is complete and costed.
            await asyncio.gather(*pending, return_exceptions=True)
            pending.clear()
        runs.append(
            _QuestionRun(
                golden_id=golden_id,
                question=question,
                ended=ended,
                cost_usd=harness.get_query_cost_usd(trace_id),
                seconds=time.monotonic() - started,
                error=error,
            )
        )
        print(f"{golden_id}: {ended}, {sum(1 for r in rows if r.golden_id == golden_id)} decisions", flush=True)
    return runs


# ---------------------------------------------------------------- the report


def _cell(text: str, limit: int = 160) -> str:
    """One table cell: no pipes or line breaks, bounded."""
    flat = " ".join(str(text).replace("|", "/").split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def _median(values: list[int]) -> str:
    return f"{statistics.median(values):.0f}" if values else "n/a"


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def _probabilities(probabilities: dict[str, float] | None) -> str:
    if not probabilities:
        return "n/a"
    ordered = sorted(probabilities.items(), key=lambda item: -item[1])
    return ", ".join(f"{option} {value:.2f}" for option, value in ordered)


def render_report(result: dict[str, Any], *, budget_usd: float, per_question_cap_usd: float, seconds: float) -> str:
    rows: list[_Row] = result["rows"]
    runs: list[_QuestionRun] = result["runs"]
    models = result["models"]
    spend = sum(run.cost_usd for run in runs)
    compared = [row for row in rows if row.comparison is not None]
    points = sorted({row.point for row in rows})
    ids = ", ".join(run.golden_id for run in runs)
    today = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = [
        "# Jev and the guard tier on the loop's own decisions",
        "",
        f"Written by `testing/Developer/scripts/compare_classifiers.py` on {today}. For each golden question:",
        "",
        "- The script ran the loop's own Guardrail, Think and Plan steps, never Act or Write.",
        (
            "- Each time the loop asked for a decision, Jev and the guard tier were both asked the same "
            "question over the same bounded state."
        ),
        "- The loop went on with the pick Jev-mode `decide()` uses, so it took the path it takes on develop.",
        "",
        "## Table of contents",
        "",
        "- [The run](#the-run)",
        "- [Agreement by decision point](#agreement-by-decision-point)",
        "- [Disagreements](#disagreements)",
        "- [Every question](#every-question)",
        "- [What this does not compare](#what-this-does-not-compare)",
        "",
        "## The run",
        "",
        f"- Questions: {len(runs)}, {ids}.",
        (
            f"- Jev: `{models['jev']}`. Guard tier: `{models['guard']}`. Plan tier, which ran Think's own "
            f"classification and is not compared: `{models['plan']}`."
        ),
        f"- Decisions asked: {len(rows)}; compared, both models asked and returned: {len(compared)}.",
        (
            f"- Spend measured by the harness: ${spend:.4f}, under a budget of ${budget_usd:.2f} enforced "
            f"as a ${per_question_cap_usd:.4f} per-question cap."
        ),
        f"- Wall time: {seconds:.0f} s.",
        f"- Modules whose `decide` was recorded: {', '.join(f'`{name}`' for name in result['patched']) or 'none'}.",
        "",
        "## Agreement by decision point",
        "",
        (
            "Agreement counts only decisions where both models made a pick. A failed model is counted in "
            "its own column, never as a disagreement."
        ),
        "",
        (
            "| Decision point | Asked | Both picked | Agreed | Disagreed | Agreement | Jev failed | Guard made no pick "
            "| Jev median ms | Guard median ms |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for point in points:
        asked = [row for row in rows if row.point == point]
        done = [row.comparison for row in asked if row.comparison is not None]
        both = [c for c in done if c.jev_choice is not None and c.guard_choice is not None]
        agreed = sum(1 for c in both if c.jev_choice == c.guard_choice)
        jev_failed = sum(1 for c in done if c.jev_choice is None)
        guard_none = sum(1 for c in done if c.guard_choice is None)
        jev_ms = [c.jev_latency_ms for c in done if c.jev_latency_ms is not None]
        guard_ms = [c.guard_latency_ms for c in done]
        out.append(
            f"| `{point}` | {len(asked)} | {len(both)} | {agreed} | {len(both) - agreed} | "
            f"{_pct(agreed, len(both))} | {jev_failed} | {guard_none} | {_median(jev_ms)} | {_median(guard_ms)} |"
        )
    if not points:
        out.append("| none asked | 0 | 0 | 0 | 0 | n/a | 0 | 0 | n/a | n/a |")

    out += ["", "## Disagreements", ""]
    disagreements = [
        row
        for row in compared
        if row.comparison.jev_choice is not None
        and row.comparison.guard_choice is not None
        and row.comparison.jev_choice != row.comparison.guard_choice
    ]
    failures = [row for row in compared if row.comparison.jev_choice is None or row.comparison.guard_choice is None]
    if disagreements:
        out += [
            "| Question | Decision point | Jev picked | Jev confidence | Jev probabilities | Guard picked |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in disagreements:
            c = row.comparison
            out.append(
                f"| {row.golden_id} | `{row.point}` | {c.jev_choice} | {c.jev_confidence:.2f} | "
                f"{_probabilities(c.jev_probabilities)} | {c.guard_choice} |"
            )
    else:
        out.append("None: wherever both models made a pick, they made the same one.")
    if failures:
        out += [
            "",
            "Decisions where a model made no pick, so there is nothing to agree or disagree with:",
            "",
            "| Question | Decision point | Jev | Guard tier |",
            "| --- | --- | --- | --- |",
        ]
        for row in failures:
            c = row.comparison
            jev = c.jev_choice if c.jev_choice is not None else f"no pick ({c.jev_failure})"
            guard = c.guard_choice if c.guard_choice is not None else "no pick"
            out.append(f"| {row.golden_id} | `{row.point}` | {jev} | {guard} |")

    out += [
        "",
        "## Every question",
        "",
        "| Question | Text | Where the loop stopped | Decisions: Jev pick / guard pick | Spend | Seconds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        mine = [row for row in rows if row.golden_id == run.golden_id]
        picks = []
        for row in mine:
            c = row.comparison
            if c is None:
                picks.append(f"`{row.point}` not compared ({row.error or 'unfinished'})")
                continue
            note = ", the loop had moved on" if row.loop_cancelled else ""
            picks.append(f"`{row.point}` {c.jev_choice or 'none'} / {c.guard_choice or 'none'}{note}")
        ended = run.ended if run.error is None else f"error: {run.error}"
        out.append(
            f"| {run.golden_id} | {_cell(run.question, 90)} | {ended} | "
            f"{'; '.join(picks) or 'none asked'} | ${run.cost_usd:.4f} | {run.seconds:.1f} |"
        )

    out += [
        "",
        "## What this does not compare",
        "",
        "- The Write step's reworded-sentence check: it needs the full answer, which this script never builds.",
        "- Follow-up questions: every run here is a first turn, so the relevancy state never carries a previous question.",
        "- Decisions the loop did not ask for a question: the tables count only decisions actually asked.",
        (
            "- Model calls outside `decide()`, such as the injection classifier and Think's classification: they "
            "ran, but are not compared."
        ),
        "- Whether either pick was right: agreement is not correctness, and a disagreement is a row to read, not a verdict.",
        "",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------- entry point


def main(argv: Sequence[str] | None = None, *, printer: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("ids", nargs="*", help="golden question ids, e.g. G-003 G-008")
    parser.add_argument("--all", action="store_true", help="every golden question")
    parser.add_argument("--budget-usd", type=float, default=DEFAULT_BUDGET_USD)
    parser.add_argument("--out", type=Path, help="write the markdown report here instead of printing it")
    args = parser.parse_args(argv)
    if not args.ids and not args.all:
        parser.error("give golden question ids, or --all")

    questions = _golden_questions(args.ids, args.all)
    per_question_cap = args.budget_usd / len(questions)
    if per_question_cap < MIN_PER_QUESTION_CAP_USD:
        parser.error(
            f"${args.budget_usd:.2f} over {len(questions)} questions is ${per_question_cap:.4f} each, below "
            f"the ${MIN_PER_QUESTION_CAP_USD:.2f} Think's own call needs; raise --budget-usd or pass fewer ids"
        )
    _load_env()
    started = time.monotonic()
    result = asyncio.run(_run(questions, per_question_cap))
    report = render_report(
        result,
        budget_usd=args.budget_usd,
        per_question_cap_usd=per_question_cap,
        seconds=time.monotonic() - started,
    )
    if args.out is None:
        printer(report)
    else:
        args.out.write_text(report)
        printer(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
