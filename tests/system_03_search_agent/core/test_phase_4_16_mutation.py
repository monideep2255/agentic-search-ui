"""Mutation coverage for build phase 4.16's premise gate: can each arm FAIL?

## Why this file exists

Build phase 4.16's premise gate was watched failing 5 of 5 before any
product code was written, and its own docstring recorded that this was NOT
sufficient for one arm:

    A3 currently stops at its "no tool_start was emitted at all" line and
    never reaches its timing comparison. So the timing assertion, which is
    the whole reason A3 exists and the only thing separating the correct
    fix from the one that changes nothing, is UNEXERCISED today.

That gap is what this file closes, and it is the one that matters most in
this phase. The plausible wrong fix for the reported defect is to call
`sink.emit("tool_start", ...)` inside `act_node`'s loop. Every event would
then exist, in the right order, with the right payloads, and A1, A2, A4 and
A5 would all go green. And a person watching the screen would see exactly
what they saw before, because `_EventSink` accumulates and `run_streaming`
yields a node's events at its RETURN, so all of them would arrive in one
burst at the end of an eleven-second silence.

M1 below IS that wrong fix, applied in process, and it asserts A3 goes red
on the TIMING branch specifically rather than on the presence branch. Until
M1 existed, nothing in this repository could tell the two fixes apart.

The wider argument is build phases 4.3, 4.7 and 4.11's, and it is now
predictive rather than anecdotal: three phases running produced vacuous gate
arms, all written by the lead, and in 4.7 the REPAIR for a vacuous arm was
itself vacuous. Reading an assertion has been demonstrated repeatedly not to
be a method for validating it. So vacuity is a build failure here, not a
review finding.

## How it runs

Entirely offline. No model call, no network, no graph. `tests/conftest.py`
hard-fails any real outbound HTTP and nothing here sets `RUN_PREMISE_GATE`,
so a leaked call raises rather than passing quietly.

Each mutation breaks ONE control in process, re-runs the corresponding gate
arm's own logic against the mutated tree, and asserts it raises
`AssertionError`. The arms are re-executed by calling the gate module's test
functions directly, so this file grades the SHIPPED arm rather than a
paraphrase of it. A paraphrase would drift from the arm it claims to cover,
which is the same class of defect one level up.

## Coverage, stated because a coverage claim this file cannot support is the
## same defect one level up

Five arms exist in `test_phase_4_16_premise.py`. This file mutates all five,
and mutates A3 twice because A3 has two distinct failure branches and only
one of them had ever been seen.

Not covered, and named rather than implied:

- The `run_streaming` de-duplication itself. Removing it does not make any
  arm here red, because a doubled event still arrives early, so A3 still
  passes. It is covered by `test_run.py`'s existing seq-monotonicity arm,
  which is the surface that actually breaks. Recorded here so a reader
  counting mutations does not conclude it is unguarded.
- The buffered `run()` path. `get_stream_writer` is a no-op there by
  design, so there is no live-versus-buffered distinction to mutate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import tests.system_03_search_agent.core.test_phase_4_16_premise as gate
from system_03_search_agent.core import graph as graph_module

# The gate's four autouse fixtures, re-registered HERE rather than copied.
#
# An autouse fixture is scoped to the module that defines it, so calling
# `gate.test_a3_...(monkeypatch)` from this file runs the arm's body with
# NONE of them applied. The first version of this file did exactly that and
# all six mutations failed identically, reaching for a real model and
# printing LiteLLM's provider list. That is worth recording rather than
# quietly fixing: the failure looked like six broken mutations and was one
# missing import, and a reader who saw only the red would have started
# debugging the mutations.
#
# Importing the fixture functions binds them into this module's namespace,
# which is how pytest activates them here, and it keeps ONE definition of
# each. Copying them would create a second set that could drift from the
# gate's own, so the mutations would eventually grade a different setup than
# the arms they claim to cover.
from tests.system_03_search_agent.core.test_phase_4_16_premise import (  # noqa: F401
    _env,
    _mock_litellm,
    _no_op_daily_caps,
    _stub_symbol_resolution,
)

_GATE_SOURCE = Path(gate.__file__)


async def _expect_arm_red(arm, monkeypatch: pytest.MonkeyPatch, *, because: str) -> str:
    """Run one gate arm and require it to fail.

    Returns the assertion message, so a caller can additionally pin WHICH
    branch fired. That second check is what makes M1 meaningful: an arm
    that goes red for the wrong reason is not evidence that it grades the
    thing it claims to grade.
    """
    try:
        await arm(monkeypatch)
    except AssertionError as exc:
        return str(exc)
    raise AssertionError(
        f"MUTATION SURVIVED: {because}. The arm stayed green while the control "
        "it grades was broken, so it is not an arm."
    )


# ---------------------------------------------------------------------------
# M1 and M1b: the two branches of A3, the arm this whole file exists for.
# ---------------------------------------------------------------------------


def _make_emit_live_deferred(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PLAUSIBLE WRONG FIX, applied in process.

    Strips the live write out of `emit_live` so it degrades to a plain
    `emit`: every event is still produced, still ordered, still correctly
    shaped, and still returned in the node's update. The only thing that
    changes is WHEN it reaches the consumer, which is the only thing the
    reported defect was ever about.
    """
    original_emit = graph_module._EventSink.emit

    def _deferred_emit_live(self, event_type: str, payload: object):
        return original_emit(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _deferred_emit_live)


@pytest.mark.asyncio
async def test_m1_a3_goes_red_on_the_timing_branch_when_events_flush_at_node_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation the gate's own docstring said it needed.

    Asserting merely that A3 fails here would be worth little: A3 fails
    against an unfixed tree too, at its presence check. What this pins is
    that A3 fails for the RIGHT reason once the events exist, which is the
    only way it can distinguish the correct fix from this one.
    """
    _make_emit_live_deferred(monkeypatch)
    message = await _expect_arm_red(
        gate.test_a3_tool_start_reaches_the_consumer_while_the_tool_is_still_running,
        monkeypatch,
        because="emit_live was degraded to a deferred emit, so every tool frame "
        "flushes at node return",
    )

    assert "no tool_start event was emitted at all" not in message, (
        "A3 went red on its PRESENCE branch under a mutation that leaves every "
        "event present. That means this mutation did not exercise the timing "
        "comparison, so A3's timing branch is still unproven and the whole "
        "point of this file is unmet."
    )
    assert "before done" in message and "flushed at node return" in message, (
        "A3 failed, but not on its timing comparison. Message was: " + message
    )


@pytest.mark.asyncio
async def test_m1b_a3_still_goes_red_on_the_presence_branch_when_no_frame_is_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3's other branch, pinned separately so the two cannot be confused.

    Together with M1 this proves A3 has two live failure modes rather than
    one, which is what lets its message be trusted as a diagnosis.
    """
    _suppress_frames(monkeypatch, {"tool_start", "tool_result"})
    message = await _expect_arm_red(
        gate.test_a3_tool_start_reaches_the_consumer_while_the_tool_is_still_running,
        monkeypatch,
        because="no tool frame is emitted at all",
    )
    assert "no tool_start event was emitted at all" in message, (
        "A3 went red for some reason other than the absence it was handed: " + message
    )


# ---------------------------------------------------------------------------
# M2 to M5: one per remaining arm.
# ---------------------------------------------------------------------------


def _suppress_frames(monkeypatch: pytest.MonkeyPatch, types: set[str]) -> None:
    """Drop the named event types on the floor at the sink."""
    original_emit_live = graph_module._EventSink.emit_live
    original_emit = graph_module._EventSink.emit

    def _filtered_emit_live(self, event_type: str, payload: object):
        if event_type in types:
            # Still advance seq, so this mutation isolates the missing
            # frame rather than also perturbing sequence numbering, which
            # would give an arm a second, unintended way to notice.
            self.seq += 1
            return None
        return original_emit_live(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _filtered_emit_live)
    monkeypatch.setattr(graph_module._EventSink, "emit", original_emit)


@pytest.mark.asyncio
async def test_m2_a1_goes_red_when_tool_start_is_never_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _suppress_frames(monkeypatch, {"tool_start"})
    message = await _expect_arm_red(
        gate.test_a1_a_dispatching_run_emits_a_tool_start_for_every_planned_call,
        monkeypatch,
        because="tool_start is suppressed",
    )
    assert "populate-check failed" not in message, (
        "A1 went red at its own populate-check rather than at its assertion, so "
        "this mutation proved nothing about the assertion. Message: " + message
    )


@pytest.mark.asyncio
async def test_m3_a2_goes_red_when_a_started_call_is_never_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unclosed-call defect, which on any surface that renders a chip
    leaves it spinning for ever."""
    _suppress_frames(monkeypatch, {"tool_result"})
    message = await _expect_arm_red(
        gate.test_a2_every_tool_start_is_closed_by_a_tool_result_for_the_same_call,
        monkeypatch,
        because="tool_result is suppressed, so every start is left open",
    )
    assert "populate-check failed" not in message, (
        "A2 went red at its populate-check rather than its assertion: " + message
    )


@pytest.mark.asyncio
async def test_m4_a4_goes_red_when_a_frame_names_the_wrong_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chip's colour is driven by `layer`, so a wrong layer is a
    silently wrong picture rather than a visible failure."""
    original_emit_live = graph_module._EventSink.emit_live

    def _relabelling_emit_live(self, event_type: str, payload: object):
        if event_type in {"tool_start", "tool_result"}:
            payload = payload.model_copy(update={"layer": "layer_3_enrichment"})
        return original_emit_live(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _relabelling_emit_live)

    message = await _expect_arm_red(
        gate.test_a4_every_tool_frame_is_schema_valid_and_names_its_tool_and_layer,
        monkeypatch,
        because="every tool frame is relabelled to Layer 3",
    )
    assert "populate-check failed" not in message, (
        "A4 went red at its populate-check rather than its assertion: " + message
    )
    assert "Layer 1" in message


@pytest.mark.asyncio
async def test_m5_a5_goes_red_when_the_act_step_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A5 restated the complaint in the reporter's own terms, so its
    mutation is the original defect: an Act step that says nothing."""
    _suppress_frames(monkeypatch, {"tool_start", "tool_result"})
    message = await _expect_arm_red(
        gate.test_a5_no_silent_gap_between_plan_and_the_answer,
        monkeypatch,
        because="the Act step emits nothing, which is the shipped defect",
    )
    assert "populate-check failed" not in message, (
        "A5 went red at its populate-check rather than its assertion: " + message
    )
    assert "frozen stepper" in message


# ---------------------------------------------------------------------------
# A structural guard on the gate itself.
# ---------------------------------------------------------------------------


def test_every_bound_arm_in_the_gate_carries_a_populate_check() -> None:
    """Build phases 4.7 and 4.11's durable rule, enforced rather than trusted.

    An arm that cannot distinguish "the control held" from "nothing
    happened" is not an arm. Each of the five reads a run's events, so each
    must first prove a tool was actually dispatched.

    This is a source-level check and it is honest about what that buys: it
    proves the words are present, not that the check is sound. F-4.7-J1-01
    was a populate-check that read the wrong field entirely and would pass
    this. The mutations above are what grade soundness; this only catches
    an arm added later with no populate-check at all.
    """
    source = _GATE_SOURCE.read_text(encoding="utf-8")
    arm_names = re.findall(r"^async def (test_a\d[a-z]?_\w+)", source, re.MULTILINE)
    assert len(arm_names) == 5, (
        f"expected 5 arms in the gate, found {len(arm_names)}: {arm_names}. If an "
        "arm was added, add its mutation above before relaxing this number."
    )

    bodies = re.split(r"^async def ", source, flags=re.MULTILINE)[1:]
    for body in bodies:
        name = body.split("(")[0]
        if not name.startswith("test_a"):
            continue
        assert "populate-check failed" in body, (
            f"{name} carries no populate-check. Every bound arm needs one: "
            "without it the arm cannot tell a held control from a run that "
            "never happened."
        )
