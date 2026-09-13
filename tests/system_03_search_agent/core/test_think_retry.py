"""Think asks once more when the model's classification reply is unusable.

Product-owner decision, 2026-09-12 (`testing/UI_fix_plan.md` item 2.11).
About 1 search in 7 on develop ended with "the plan tier did not return
valid JSON for query classification", and nothing recorded what the model
had sent. `think_node` now retries the classification call once and logs a
bounded excerpt of the unusable reply.

COVERAGE, per `goal-contracts`.

Exercised:
- One unusable reply, then a valid one: the run continues past Think with no
  Think step error, the model is asked exactly twice, and a warning carrying
  a bounded excerpt of the bad reply is logged.
- Two unusable replies: the run ends with the same Think step error as
  before, and the model is asked exactly twice, never a third time.
- A valid first reply: exactly one Think call, so the retry never adds cost
  to a healthy run.

Not exercised: a live model; the per-query cost cap tripping on the second
call, which the harness's own cap tests own; a HarnessCallError on the retry,
which returns the step error through the unchanged `except` branch.
"""

from __future__ import annotations

import json
import logging
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION, compiled_graph
from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
from system_03_search_agent.harness import harness as harness_module

_GUARD_OK = (
    '{"is_injection": false, "is_off_topic": false, "confidence": 0.02, '
    '"reason": "an ordinary biomedical question"}'
)
_THINK_OK = json.dumps(
    {"query_class": "exploratory", "narrative": "stand-in classification", "entities": []}
)
_THINK_BAD = "Sure, here is the classification you asked for:\nquery_class = exploratory"


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _install_model(monkeypatch: pytest.MonkeyPatch, think_replies: list[str]) -> dict[str, int]:
    """Guard answers normally; Think answers from `think_replies` in order.

    Once the list is used up, Think answers validly. Returns a counter of
    Think calls, so each test can pin exactly how many were made.
    """
    calls = {"think": 0}

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(
            message.get("content") or ""
            for message in messages  # type: ignore[union-attr]
        )
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return _fake_response(_GUARD_OK)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            index = calls["think"]
            calls["think"] += 1
            return _fake_response(think_replies[index] if index < len(think_replies) else _THINK_OK)
        return _fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return calls


async def _run(text: str = "hello") -> list[Any]:
    from langsmith.run_helpers import tracing_context

    from system_03_search_agent.harness.harness import Harness

    query = Query(
        text=text,
        session_id="session-think-retry",
        trace_id="trace-think-retry",
        user_id=None,
        audience_depth="researcher",
    )
    context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)
    state = {
        "query": query,
        "context": context,
        "harness": Harness(trace_id=query.trace_id),
        "seq": 0,
        "events": [],
        "start_monotonic": time.monotonic(),
    }
    with tracing_context(enabled=False):
        final_state = await compiled_graph.ainvoke(state)
    return list(final_state["events"])


def _type(event: Any) -> str:
    kind = event.type
    return str(getattr(kind, "value", kind))


def _payload(event: Any) -> dict[str, Any]:
    payload = event.payload
    return payload if isinstance(payload, dict) else payload.model_dump()


def _think_errors(events: list[Any]) -> list[dict[str, Any]]:
    return [
        _payload(event)
        for event in events
        if _type(event) == "error" and _payload(event).get("source") == "think"
    ]


@pytest.mark.asyncio
async def test_one_unusable_reply_is_retried_and_the_run_continues(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls = _install_model(monkeypatch, [_THINK_BAD])
    caplog.set_level(logging.WARNING, logger="system_03_search_agent.core.graph")

    events = await _run()

    assert calls["think"] == 2, "an unusable reply must be asked for exactly once more"
    assert _think_errors(events) == [], "a valid second reply must not end the run"
    assert "think" in [_type(event) for event in events], (
        "populate-check: the run must reach a Think event, or the absence of a "
        "Think error above proves nothing"
    )
    warnings = [record.getMessage() for record in caplog.records]
    assert any("think classification unusable (attempt 1 of 2" in line for line in warnings)
    assert any("Sure, here is the classification" in line for line in warnings), (
        "the log must carry an excerpt of the reply, which is the point of logging it"
    )


@pytest.mark.asyncio
async def test_two_unusable_replies_end_the_run_as_before_and_never_a_third_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_model(monkeypatch, [_THINK_BAD, _THINK_BAD, _THINK_BAD])

    events = await _run()

    assert calls["think"] == 2, "Think must retry once, never more"
    errors = _think_errors(events)
    assert len(errors) == 1
    assert errors[0]["message"] == (
        "the plan tier did not return valid JSON for query classification"
    )
    assert errors[0]["fatal"] is True


@pytest.mark.asyncio
async def test_a_valid_first_reply_makes_exactly_one_think_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_model(monkeypatch, [])

    events = await _run()

    assert calls["think"] == 1, "a healthy run must not pay for a retry"
    assert _think_errors(events) == []


def test_the_logged_excerpt_is_bounded_and_escaped() -> None:
    """The warning uses %r on at most 200 characters, so a long or multi-line
    reply cannot flood the log or forge a second log line."""
    import inspect

    from system_03_search_agent.core import graph as graph_module

    source = inspect.getsource(graph_module.think_node)
    assert "content[:200]" in source
    assert "starts %r" in source
