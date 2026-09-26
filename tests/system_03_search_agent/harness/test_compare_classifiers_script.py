"""Tests for `testing/Developer/scripts/compare_classifiers.py`, the offline
comparison of Jev and the guard tier (build phase 8.6, T-8.6-03).

No network and no model call anywhere in this file: the script is loaded
from its path and its pieces are exercised with stand-ins.

What this file exercises:

- The spend bound refuses a run before any credential is read.
- Golden ids are checked against the golden dataset.
- The recorder swaps a module's `decide`, asks `compare_models`, hands the
  loop the live record, and keeps comparing when the loop stops waiting.
- The report carries an agreement table per decision point, every
  disagreement with Jev's confidence, and each model failure in its own
  table rather than as a disagreement.
- The script finds the repository from its own path and names no absolute
  path.

What it deliberately omits: a live run. That is committed as the script's
own output under `testing/Developer/reports/2026-09-26_phase_8.6/`.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness.jev_client import JevResult

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "testing" / "Developer" / "scripts" / "compare_classifiers.py"


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """The script, loaded from its path. Registered in `sys.modules` while it
    runs, since its dataclasses resolve their annotations through it, and
    removed again after the test."""
    spec = importlib.util.spec_from_file_location("compare_classifiers_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _jev(choice: str, confidence: float = 0.8) -> JevResult:
    return JevResult(
        resolved_model="typesafe/jev-1.13-20260917",
        choice=choice,
        confidence=confidence,
        probabilities={choice: confidence},
        input_tokens=1,
        output_tokens=1,
        cost_usd=1e-05,
        latency_ms=300,
    )


def _comparison(point: str, jev: JevResult | str, guard: str | None) -> decide_module.ModelComparison:
    return decide_module.ModelComparison(
        point=point, options=("on_topic", "off_topic"), jev=jev, guard_choice=guard, guard_latency_ms=900
    )


def test_the_script_finds_the_repository_from_its_own_path(script) -> None:
    assert script.REPO_ROOT == REPO_ROOT
    assert script.GOLDEN_PATH.is_file()
    source = SCRIPT.read_text()
    assert "/Users/" not in source and "/home/" not in source, "no absolute path in a public repository"  # local-refs: allow


def test_a_budget_too_small_for_thinks_own_call_refuses_before_any_credential(script, monkeypatch) -> None:
    def _must_not_load() -> None:
        raise AssertionError("credentials were read for a run that was refused")

    monkeypatch.setattr(script, "_load_env", _must_not_load)
    with pytest.raises(SystemExit) as excinfo:
        script.main(["--all", "--budget-usd", "0.50"])
    assert excinfo.value.code == 2, "50 questions at $0.01 each is below the $0.02 Think needs"


def test_an_unknown_golden_id_stops_the_run(script, monkeypatch) -> None:
    monkeypatch.setattr(script, "_load_env", lambda: pytest.fail("credentials read"))
    with pytest.raises(SystemExit):
        script.main(["G-999"])


def test_known_golden_ids_come_back_in_order(script) -> None:
    questions = script._golden_questions(["G-038", "G-003"], take_all=False)
    assert [golden_id for golden_id, _ in questions] == ["G-038", "G-003"]
    assert questions[0][1] == "Tell me about the tree of life."


def _snapshot_every_decide(monkeypatch: pytest.MonkeyPatch) -> list[types.ModuleType]:
    """Register every loaded module's `decide` with monkeypatch BEFORE the
    recorder touches it, so teardown restores each one even if the test
    fails midway (finding K-14: `core.graph` was left patched and four
    later tests in `core/test_graph.py` failed)."""
    holders = [
        module
        for name, module in list(sys.modules.items())
        if name.startswith("system_03_search_agent")
        and name != decide_module.__name__
        and getattr(module, "decide", None) is decide_module.decide
    ]
    for module in holders:
        monkeypatch.setattr(module, "decide", module.decide)
    return holders


@pytest.mark.asyncio
async def test_the_recorder_compares_hands_back_the_live_record_and_survives_a_cancel(script, monkeypatch) -> None:
    fake = types.ModuleType("system_03_search_agent._compare_script_test_module")
    fake.decide = decide_module.decide
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    holders = _snapshot_every_decide(monkeypatch)
    release = asyncio.Event()

    async def _fake_compare(harness, trace_id, point, state, options, *, instructions=None, criteria=None):
        if point == "slow":
            await release.wait()
        return _comparison(point, _jev("off_topic") if point != "slow" else "timeout", "on_topic")

    monkeypatch.setattr(decide_module, "compare_models", _fake_compare)
    rows: list = []
    pending: list = []
    patched, uninstall = script._install_recorder(rows, pending, {"id": "G-042"})

    assert fake.__name__ in patched and fake.decide is not decide_module.decide
    record = await fake.decide(None, "t", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.decided_by == "jev" and record.chosen == "off_topic" and record.guard_choice is None

    waiting = asyncio.create_task(fake.decide(None, "t", "slow", "x", ["on_topic", "off_topic"], default="on_topic"))
    await asyncio.sleep(0.05)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    release.set()
    await asyncio.gather(*pending, return_exceptions=True)

    assert [row.point for row in rows] == ["guardrail.relevancy", "slow"]
    assert rows[1].loop_cancelled and rows[1].comparison is not None, "the comparison finished after the loop moved on"
    assert all(row.golden_id == "G-042" for row in rows)

    uninstall()
    assert all(module.decide is decide_module.decide for module in holders), (
        "the script's own uninstall puts every module's decide back"
    )


def test_the_report_counts_agreement_per_point_and_lists_disagreements(script) -> None:
    rows = [
        script._Row("G-008", "guardrail.relevancy", _comparison("guardrail.relevancy", _jev("off_topic", 0.61), "on_topic")),
        script._Row("G-038", "guardrail.relevancy", _comparison("guardrail.relevancy", _jev("on_topic"), "on_topic")),
        script._Row("G-009", "think.ask_back", _comparison("think.ask_back", "timeout", "on_topic")),
    ]
    runs = [
        script._QuestionRun("G-008", "334", "asked a question back", 0.001, 2.0),
        script._QuestionRun("G-038", "Tell me about the tree of life.", "planned 2 tool calls", 0.002, 3.0),
        script._QuestionRun("G-009", "the", "asked a question back", 0.001, 2.0),
    ]
    report = script.render_report(
        {"rows": rows, "runs": runs, "patched": ["system_03_search_agent.core.graph"],
         "models": {"jev": "typesafe/jev-1.13", "guard": "g", "plan": "p"}},
        budget_usd=0.5,
        per_question_cap_usd=0.05,
        seconds=12.0,
    )

    assert "| `guardrail.relevancy` | 2 | 2 | 1 | 1 | 50% | 0 | 0 | 300 | 900 |" in report
    assert "| `think.ask_back` | 1 | 0 | 0 | 0 | n/a | 1 | 0 | n/a | 900 |" in report
    assert "| G-008 | `guardrail.relevancy` | off_topic | 0.61 | off_topic 0.61 | on_topic |" in report
    assert "| G-009 | `think.ask_back` | no pick (timeout) | on_topic |" in report, "a failure is not a disagreement"
    assert "## What this does not compare" in report
    assert "—" not in report and "–" not in report, "house style: no em or en dashes"


def test_the_report_says_so_when_nothing_disagreed(script) -> None:
    rows = [script._Row("G-038", "guardrail.relevancy", _comparison("guardrail.relevancy", _jev("on_topic"), "on_topic"))]
    runs = [script._QuestionRun("G-038", "Tell me about the tree of life.", "planned 2 tool calls", 0.002, 3.0)]
    report = script.render_report(
        {"rows": rows, "runs": runs, "patched": [], "models": {"jev": "j", "guard": "g", "plan": "p"}},
        budget_usd=0.5,
        per_question_cap_usd=0.05,
        seconds=1.0,
    )
    assert "None: wherever both models made a pick, they made the same one." in report
