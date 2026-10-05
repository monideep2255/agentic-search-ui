"""Card 72, the logging half: one structured line per classifier-model call.

## What these arms pin

- The guardrail's classifier call, the guard-tier fallback inside `decide()`
  and Jev's decision call each emit one `model call ...` line with the
  decision point, elapsed milliseconds, outcome, attempt number and the
  provider the router reported (or "unknown").
- The outcome words: ok, timeout, rate_limited, error, unusable_reply.
- The line never carries the question text, the prompt, the model's reply
  text, a token count or a cost.

## What they do not cover

- Whether a live router's reply carries a `provider` field. Every model
  here is a stub; the field name is OpenRouter's documented one and the live
  check is the first deployed log line.
- That behaviour is unchanged. The existing guardrail and decide suites
  pin that, and run unchanged beside this file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import JevCallError, JevResult
from tests.system_03_search_agent.model_stub import COMPLIANT_GUARD_CLASSIFICATION

_LOGGER = "system_03_search_agent.harness.call_log"
_LINE = re.compile(
    r"^model call point=(?P<point>\S+) trace=(?P<trace>\S+) kind=(?P<kind>\S+) "
    r"elapsed_ms=(?P<elapsed_ms>\d+) outcome=(?P<outcome>\S+) "
    r"attempt=(?P<attempt>\d+) provider=(?P<provider>.+)$"
)
_OPTIONS = ["relevant", "not_relevant"]
#: A marker no stub, prompt template or option contains, so finding it in a
#: line can only mean the question text leaked.
_QUESTION = "zq-marker-9137 which genes are linked to the condition?"
_REPLY_MARKER = "reply-marker-5521"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)
    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _reply(content: str, provider: str | None = None) -> SimpleNamespace:
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    if provider is not None:
        reply.provider = provider
    return reply


def _lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, str]]:
    parsed = []
    for record in caplog.records:
        if record.name != _LOGGER:
            continue
        match = _LINE.match(record.getMessage())
        assert match is not None, record.getMessage()
        parsed.append(match.groupdict())
    return parsed


def _stub_acompletion(monkeypatch: pytest.MonkeyPatch, *behaviours: Any) -> None:
    """One behaviour per request, the last repeating: "hang", an exception,
    or a ready reply object."""
    count = [0]

    async def _acompletion(**_kwargs: Any) -> Any:
        behaviour = behaviours[min(count[0], len(behaviours) - 1)]
        count[0] += 1
        if behaviour == "hang":
            await asyncio.sleep(60)
        if isinstance(behaviour, BaseException):
            raise behaviour
        return behaviour

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)


# ---------------------------------------------------------------------------
# decide(): the guard-tier call.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_decision_success_logs_the_fields(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, _reply("relevant", provider="Together"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c1"), "c1", "guardrail.relevancy", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["point"] == "guardrail.relevancy"
    assert line["trace"] == "c1"
    assert line["kind"] == "guard"
    assert line["outcome"] == "ok"
    assert line["attempt"] == "1"
    assert line["provider"] == "Together"
    assert int(line["elapsed_ms"]) >= 0


@pytest.mark.asyncio
async def test_guard_decision_without_a_provider_says_unknown(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, _reply("relevant"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c2"), "c2", "think.ask_back", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["provider"] == "unknown"


@pytest.mark.asyncio
async def test_guard_decision_timeout_logs_timeout_and_the_wait(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, "hang")
    monkeypatch.setattr(decide_module, "_GUARD_BUDGET_S", 0.2)
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c3"), "c3", "plan.literature", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["outcome"] == "timeout"
    assert 150 <= int(line["elapsed_ms"]) < 2000
    assert line["provider"] == "unknown"


@pytest.mark.asyncio
async def test_guard_decision_provider_error_logs_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, ValueError("boom"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c4"), "c4", "plan.literature", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["outcome"] == "error"


@pytest.mark.asyncio
async def test_guard_decision_rate_limit_logs_rate_limited(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    limited = litellm.RateLimitError("slow down", llm_provider="openrouter", model="m")
    _stub_acompletion(monkeypatch, limited)
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c5"), "c5", "plan.literature", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["outcome"] == "rate_limited"


@pytest.mark.asyncio
async def test_guard_decision_unparseable_reply_logs_unusable_reply(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, _reply(f"{_REPLY_MARKER} cannot say", provider="Fireworks"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("c6"), "c6", "plan.literature", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert line["outcome"] == "unusable_reply"
    assert line["provider"] == "Fireworks"


# ---------------------------------------------------------------------------
# decide(): Jev's call, and the guard fallback after it.
# ---------------------------------------------------------------------------


def _jev_result() -> JevResult:
    return JevResult(
        resolved_model="typesafe/jev-test",
        choice="relevant",
        confidence=0.9,
        probabilities={"relevant": 0.9, "not_relevant": 0.1},
        input_tokens=100,
        output_tokens=20,
        cost_usd=1.5e-05,
        latency_ms=285,
    )


@pytest.fixture
def _jev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_jev_decision_success_logs_one_jev_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, _jev_mode: None
) -> None:
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=_jev_result()))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("j1"), "j1", "think.ask_back", _QUESTION, _OPTIONS)

    (line,) = _lines(caplog)
    assert (line["kind"], line["point"], line["outcome"]) == ("jev", "think.ask_back", "ok")
    assert line["attempt"] == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "outcome"),
    [
        ("timeout", "timeout"),
        ("http_error", "error"),
        ("malformed_reply", "unusable_reply"),
        ("invalid_option", "unusable_reply"),
    ],
)
async def test_jev_failure_logs_its_outcome_then_the_guard_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    _jev_mode: None,
    reason: str,
    outcome: str,
) -> None:
    monkeypatch.setattr(
        decide_module, "call_jev", AsyncMock(side_effect=JevCallError("x", reason=reason))
    )
    _stub_acompletion(monkeypatch, _reply("relevant", provider="Together"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await decide(Harness("j2"), "j2", "think.ask_back", _QUESTION, _OPTIONS)

    jev_line, guard_line = _lines(caplog)
    assert (jev_line["kind"], jev_line["outcome"]) == ("jev", outcome)
    assert (guard_line["kind"], guard_line["outcome"]) == ("guard", "ok")
    assert guard_line["provider"] == "Together"


# ---------------------------------------------------------------------------
# The guardrail's classifier call, through the real node.
# ---------------------------------------------------------------------------


async def _run_guardrail(text: str) -> dict[str, Any]:
    from system_03_search_agent.contracts.query import Query, RequestContext

    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    state = {
        "query": Query(text=text, session_id="call-log-test", trace_id=trace_id),
        "context": RequestContext(surface="rest_sse", session_memory=None),
        "harness": Harness(trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
    return {"trace_id": trace_id, **result}


@pytest.mark.asyncio
async def test_guardrail_success_logs_attempt_one(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, _reply(COMPLIANT_GUARD_CLASSIFICATION, provider="DeepInfra"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    out = await _run_guardrail("Which diseases are associated with BRCA1?")

    (line,) = [entry for entry in _lines(caplog) if entry["point"] == "guardrail.classify"]
    assert line["trace"] == out["trace_id"]
    assert (line["kind"], line["outcome"], line["attempt"]) == ("guard", "ok", "1")
    assert line["provider"] == "DeepInfra"


@pytest.mark.asyncio
async def test_guardrail_timeout_then_success_logs_two_attempts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    real_budget = graph_module.budget_for_step
    monkeypatch.setattr(
        graph_module,
        "budget_for_step",
        lambda step, query_class: 1.0 if step == "guardrail" else real_budget(step, query_class),
    )
    _stub_acompletion(monkeypatch, "hang", _reply(COMPLIANT_GUARD_CLASSIFICATION))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    out = await _run_guardrail("Which diseases are associated with BRCA1?")

    assert out.get("step_error") is None
    lines = [entry for entry in _lines(caplog) if entry["point"] == "guardrail.classify"]
    assert [(entry["attempt"], entry["outcome"]) for entry in lines] == [
        ("1", "timeout"),
        ("2", "ok"),
    ]


@pytest.mark.asyncio
async def test_guardrail_unusable_replies_log_unusable_reply(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, _reply(f"{_REPLY_MARKER} not json"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    out = await _run_guardrail("Which diseases are associated with BRCA1?")

    assert out["step_error"]["error_class"] == "recoverable"
    lines = [entry for entry in _lines(caplog) if entry["point"] == "guardrail.classify"]
    assert [(entry["attempt"], entry["outcome"]) for entry in lines] == [
        ("1", "unusable_reply"),
        ("2", "unusable_reply"),
    ]


@pytest.mark.asyncio
async def test_guardrail_provider_error_logs_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub_acompletion(monkeypatch, ValueError("boom"))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    await _run_guardrail("Which diseases are associated with BRCA1?")

    (line,) = [entry for entry in _lines(caplog) if entry["point"] == "guardrail.classify"]
    assert line["outcome"] == "error"


# ---------------------------------------------------------------------------
# What a line never carries.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_line_carries_the_question_the_reply_or_a_count(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, _jev_mode: None
) -> None:
    """Every path above, run on a question and a reply carrying markers that
    nothing else in the code contains. The marker never shows in any line,
    and neither does a token or cost field."""
    caplog.set_level(logging.INFO, logger=_LOGGER)

    # decide(): Jev fails, the guard fallback replies with the marker.
    monkeypatch.setattr(
        decide_module, "call_jev", AsyncMock(side_effect=JevCallError("x", reason="timeout"))
    )
    _stub_acompletion(monkeypatch, _reply(f"{_REPLY_MARKER} none", provider="Together"))
    await decide(Harness("n1"), "n1", "think.ask_back", _QUESTION, _OPTIONS)

    # The guardrail, on a question with the marker, replying with the marker.
    _stub_acompletion(monkeypatch, _reply(f"{_REPLY_MARKER} not json"))
    await _run_guardrail(_QUESTION)

    lines = [r.getMessage() for r in caplog.records if r.name == _LOGGER]
    assert len(lines) >= 3
    for line in lines:
        assert "zq-marker-9137" not in line
        assert _REPLY_MARKER not in line
        assert "which genes" not in line
        for forbidden in ("token", "cost", "prompt", "content"):
            assert forbidden not in line.lower()
        assert _LINE.match(line) is not None, line


def test_a_logging_fault_never_reaches_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.harness import call_log

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("log sink down")

    monkeypatch.setattr(call_log.logger, "warning", _boom)
    call_log.log_model_call(
        point="p", trace_id="t", kind="guard", started=time.monotonic(), outcome=call_log.OK
    )


@pytest.mark.asyncio
async def test_the_line_is_visible_at_the_default_log_level(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The service sets no root level, so Python's default WARNING applies:
    an INFO line would never reach the deployment's log."""
    _stub_acompletion(monkeypatch, _reply("relevant"))
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    await decide(Harness("v1"), "v1", "think.ask_back", _QUESTION, _OPTIONS)

    assert len(_lines(caplog)) == 1


def test_provider_of_only_believes_a_plain_string() -> None:
    from system_03_search_agent.harness import call_log

    assert call_log.provider_of(SimpleNamespace(provider="  Together ")) == "Together"
    assert call_log.provider_of(SimpleNamespace(provider=["x"])) is None
    assert call_log.provider_of(SimpleNamespace()) is None
    assert call_log.provider_of(SimpleNamespace(provider="x" * 500)) == "x" * 64
    assert json.dumps(call_log.provider_of(SimpleNamespace(provider="a")))
