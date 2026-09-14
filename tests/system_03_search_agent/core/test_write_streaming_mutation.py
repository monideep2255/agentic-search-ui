"""Mutation coverage for set 11.16's premise gate: can each arm FAIL?

Same shape and same reason as `test_phase_4_16_mutation.py`. The plausible
wrong fix for the measured defect is one that leaves every event present,
ordered and well-formed while changing nothing about when a reader sees it.
An arm that cannot go red under that fix is decoration. Each mutation here
breaks ONE control in process, re-runs the shipped arm, and requires it to
raise, then pins WHICH branch fired so a red for the wrong reason does not
count.

Coverage, stated because a claim this file cannot support is the same
defect one level up. Four arms exist in `test_write_streaming_premise.py`.
This file mutates W1, W2 and W4 and pins the branch each fails on. It does
not mutate W3, which compares two real runs against each other rather than
against a control, and it does not mutate the frontend skip.

The mutations are TYPE-SCOPED rather than node-scoped: `token`, `citation`,
`trust_signal` and `step` are emitted by `write_node` and by no other node
(`grep 'emit("token"' core/graph.py` lists only its branches), so degrading
`emit_live` for exactly those types is "revert write_node to sink.emit"
applied in process, while act_node's live writes, which W1's populate-check
depends on, stay live. A whole-sink degradation would turn W1 red at its
populate-check, which proves nothing about its assertion.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import tests.system_03_search_agent.core.test_write_streaming_premise as gate
from system_03_search_agent.core import graph as graph_module
from tests.system_03_search_agent.core.test_phase_4_16_premise import (  # noqa: F401
    _env,
    _mock_litellm,
    _no_op_daily_caps,
    _stub_symbol_resolution,
)

_GATE_SOURCE = Path(gate.__file__)
_WRITE_NODE_TYPES = {"token", "citation", "trust_signal", "step"}


async def _expect_arm_red(arm, *args, because: str) -> str:
    try:
        await arm(*args)
    except AssertionError as exc:
        return str(exc)
    raise AssertionError(
        f"MUTATION SURVIVED: {because}. The arm stayed green while the control "
        "it grades was broken, so it is not an arm."
    )


def _defer_write_node_live_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PLAUSIBLE WRONG FIX: write_node back on `sink.emit`, in process."""
    original_emit = graph_module._EventSink.emit
    original_emit_live = graph_module._EventSink.emit_live

    def _deferred_for_write_types(self, event_type: str, payload: object):
        if event_type in _WRITE_NODE_TYPES:
            return original_emit(self, event_type, payload)
        return original_emit_live(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _deferred_for_write_types)


def _suppress_step(monkeypatch: pytest.MonkeyPatch) -> None:
    original_emit_live = graph_module._EventSink.emit_live

    def _no_step(self, event_type: str, payload: object):
        if event_type == "step":
            self.seq += 1
            return None
        return original_emit_live(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _no_step)


@pytest.mark.asyncio
async def test_m1_w1_goes_red_at_its_assertion_when_write_node_flushes_at_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _defer_write_node_live_writes(monkeypatch)
    message = await _expect_arm_red(
        gate.test_w1_every_grounded_write_event_reaches_the_stream_writer_before_write_node_returns,
        monkeypatch,
        because="write_node's live writes were degraded to plain emit",
    )
    assert "populate-check failed" not in message, (
        "W1 went red at its populate-check rather than its assertion, so this "
        "mutation proved nothing about the assertion. Message: " + message
    )
    assert "flushed at node return" in message, (
        "W1 failed, but not on its channel comparison: " + message
    )


@pytest.mark.asyncio
async def test_m2_w2_goes_red_on_its_timing_branch_when_the_step_marker_flushes_at_return(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    _defer_write_node_live_writes(monkeypatch)
    message = await _expect_arm_red(
        gate.test_w2_the_step_event_reaches_the_consumer_while_the_synth_call_is_still_running,
        monkeypatch,
        request,
        because="the step marker was degraded to plain emit",
    )
    assert "populate-check failed" not in message, message
    assert "no step event was emitted at all" not in message, (
        "W2 went red on its PRESENCE branch under a mutation that leaves the "
        "marker present, so its timing branch is still unproven: " + message
    )
    assert "before done" in message and "flushed at node return" in message, (
        "W2 failed, but not on its timing comparison: " + message
    )


@pytest.mark.asyncio
async def test_m2b_w2_goes_red_on_its_presence_branch_when_no_step_marker_is_emitted(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    _suppress_step(monkeypatch)
    message = await _expect_arm_red(
        gate.test_w2_the_step_event_reaches_the_consumer_while_the_synth_call_is_still_running,
        monkeypatch,
        request,
        because="no step marker is emitted at all",
    )
    assert "populate-check failed" not in message, message
    assert "no step event was emitted at all" in message, message


@pytest.mark.asyncio
async def test_m3_w4_goes_red_when_a_refusal_announces_write(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """A step marker placed ABOVE the early returns, which is the wrong
    place for it, applied in process by emitting one on the first emit of
    a refusal token."""
    from system_03_search_agent.contracts.events import StepPayload

    original_emit = graph_module._EventSink.emit

    def _announcing_emit(self, event_type: str, payload: object):
        if event_type == "token" and not any(e.type == "step" for e in self.new_events):
            original_emit(self, "step", StepPayload(step="write", status="started"))
        return original_emit(self, event_type, payload)

    monkeypatch.setattr(graph_module._EventSink, "emit", _announcing_emit)
    message = await _expect_arm_red(
        gate.test_w4_a_refusal_decided_before_the_synth_call_never_announces_write_and_never_calls_synth,
        monkeypatch,
        request,
        because="the refusal path announces Write",
    )
    assert "populate-check failed" not in message, message
    assert "announced that Write" in message, message


def test_every_bound_arm_in_the_gate_carries_a_populate_check() -> None:
    source = _GATE_SOURCE.read_text(encoding="utf-8")
    arm_names = re.findall(r"^async def (test_w\d[a-z]?_\w+)", source, re.MULTILINE)
    assert len(arm_names) == 4, (
        f"expected 4 arms in the gate, found {len(arm_names)}: {arm_names}. If an "
        "arm was added, add its mutation above before relaxing this number."
    )
    bodies = re.split(r"^async def ", source, flags=re.MULTILINE)[1:]
    for body in bodies:
        name = body.split("(")[0]
        if not name.startswith("test_w"):
            continue
        assert "populate-check failed" in body, (
            f"{name} carries no populate-check."
        )
