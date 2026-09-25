"""Tests for jev_client.py: the one HTTP call to OpenRouter's alpha
decisions endpoint (build phase 8.2, card 8).

No real network call anywhere in this file. Every case monkeypatches
`jev_client._post`, the one seam that module exposes for exactly this
purpose, to return a canned `httpx.Response` or raise a canned exception.
The confirmed request/response shapes these fixtures mirror are pinned
live in `testing/Developer/reports/2026-09-25_phase_8.2/builder_D.md`.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.jev_client import JevCallError, JevResult, call_jev


def _response(body: dict[str, Any], *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, content=json.dumps(body).encode())


def _success_body(question_key: str = "guardrail.relevancy", choice: str = "relevant") -> dict[str, Any]:
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            question_key: {
                "type": "choice",
                "choice": choice,
                "probabilities": {"relevant": 1.0, "not_relevant": 0.0},
                "confidence": 1.0,
            }
        },
        "usage": {"input_tokens": 352, "output_tokens": 40, "cost": 1.4784e-05},
        "id": "gen-dec-test",
        "provider": "TypeSafe",
    }


@pytest.mark.asyncio
async def test_call_jev_success_parses_the_confirmed_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(_success_body())))
    result = await call_jev(
        model="typesafe/jev-1.13",
        question_key="guardrail.relevancy",
        state="is this relevant?",
        options=["relevant", "not_relevant"],
        api_key="test-key",
    )
    assert isinstance(result, JevResult)
    assert result.choice == "relevant"
    assert result.confidence == 1.0
    assert result.cost_usd == pytest.approx(1.4784e-05)
    assert result.input_tokens == 352
    assert result.output_tokens == 40
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_call_jev_timeout_falls_to_actionable_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    )
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["a", "b"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "timeout"
    assert "fall back to the guard tier" in str(excinfo.value)


@pytest.mark.asyncio
async def test_call_jev_non_200_is_an_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(return_value=_response({"error": "bad"}, status_code=400))
    )
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["a", "b"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "http_error"


@pytest.mark.asyncio
async def test_call_jev_transport_failure_is_an_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(side_effect=httpx.ConnectError("refused"))
    )
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["a", "b"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "http_error"


@pytest.mark.asyncio
async def test_call_jev_missing_field_is_a_malformed_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _success_body()
    del body["usage"]["cost"]
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(body)))
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["relevant", "not_relevant"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "malformed_reply"


@pytest.mark.asyncio
async def test_call_jev_wrong_question_key_is_a_malformed_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _success_body(question_key="some_other_key")
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(body)))
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["relevant", "not_relevant"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "malformed_reply"


@pytest.mark.asyncio
async def test_call_jev_not_valid_json_is_a_malformed_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_response = httpx.Response(200, content=b"not json")
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=bad_response))
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["relevant", "not_relevant"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "malformed_reply"


@pytest.mark.asyncio
async def test_call_jev_choice_outside_options_is_an_invalid_option(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _success_body(choice="something_never_offered")
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(body)))
    with pytest.raises(JevCallError) as excinfo:
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["relevant", "not_relevant"],
            api_key="test-key",
        )
    assert excinfo.value.reason == "invalid_option"


@pytest.mark.asyncio
async def test_call_jev_never_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """No retries inside jev_client (the caller's fallback is the retry)."""
    mock_post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    monkeypatch.setattr(jev_client_module, "_post", mock_post)
    with pytest.raises(JevCallError):
        await call_jev(
            model="typesafe/jev-1.13",
            question_key="guardrail.relevancy",
            state="x",
            options=["a", "b"],
            api_key="test-key",
        )
    assert mock_post.call_count == 1


# Builder J, F-J-03: the decision's description rides in the endpoint's own
# `instructions` and `criteria` fields; `state` carries the person's text only.


def test_build_body_defaults_are_unchanged() -> None:
    body = jev_client_module._build_body(
        model="m", question_key="k", state="s", options=["a", "b"]
    )
    question = body["questions"]["k"]
    assert question["instructions"] == (
        "Read the state and answer with exactly one of the offered options."
    )
    assert question["criteria"] == {
        "a": "Choose 'a' when it is the best answer for this decision.",
        "b": "Choose 'b' when it is the best answer for this decision.",
    }


@pytest.mark.asyncio
async def test_call_jev_sends_the_callers_description(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_post = AsyncMock(return_value=_response(_success_body()))
    monkeypatch.setattr(jev_client_module, "_post", mock_post)
    await call_jev(
        model="typesafe/jev-1.13",
        question_key="guardrail.relevancy",
        state="the person's own words",
        options=["relevant", "not_relevant"],
        api_key="test-key",
        instructions="Decide whether it is biomedical.",
        criteria={"relevant": "It is.", "not_relevant": "It is not."},
    )
    body = mock_post.await_args.args[1]
    question = body["questions"]["guardrail.relevancy"]
    assert body["state"] == "the person's own words"
    assert question["instructions"] == "Decide whether it is biomedical."
    assert question["criteria"] == {"relevant": "It is.", "not_relevant": "It is not."}
