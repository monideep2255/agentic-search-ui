"""Tests for jev_client.py: the one HTTP call to OpenRouter's alpha
decisions endpoint (build phase 8.2, card 8).

No real network call anywhere in this file. Every case monkeypatches
`jev_client._post`, the one seam that module exposes for exactly this
purpose, to return a canned `httpx.Response` or raise a canned exception.
The confirmed request/response shapes these fixtures mirror are pinned
live in `testing/Developer/reports/2026-09-25_phase_8.2/builder_D.md`.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.jev_client import (
    MAX_JEV_COST_USD,
    JevCallError,
    JevResult,
    call_jev,
)


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


# ---------------------------------------------------------------------------
# Build phase 8.2 fix round, F-8.2-J03 and F-8.2-J06: the 3-second bound is a
# TOTAL bound on the call. httpx's own timeout float is four per-phase limits,
# and its read limit is the gap between two chunks, so a body that trickles in
# steadily outlasted it: the judge measured one decision held for 14 seconds.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cost", "billed"),
    [
        ("Infinity", MAX_JEV_COST_USD),
        ("NaN", MAX_JEV_COST_USD),
        ("-0.1", MAX_JEV_COST_USD),
        ("0.5", MAX_JEV_COST_USD),
        ("0.02", MAX_JEV_COST_USD),
        ("true", MAX_JEV_COST_USD),
    ],
)
async def test_a_cost_no_decision_could_have_is_a_malformed_reply(
    monkeypatch: pytest.MonkeyPatch, cost: str, billed: float
) -> None:
    """F-8.2-J15: Jev's cost is charged straight into every cost cap. A
    reply claiming `Infinity` (which Python's JSON parser accepts) stopped
    every later model call in the question. Such a reply is malformed, so
    the guard's pick decides.

    Fix round, F-8.6-J10, then clamped by F-8.6-V01 and V03: a real amount
    above the ceiling, or a figure that is not a finite, non-negative
    number (infinite, not a number, negative, a boolean), is billed the
    ceiling itself, never the reported figure and never $0.0."""
    raw = json.dumps(_success_body()).replace('"cost": 1.4784e-05', f'"cost": {cost}')
    assert f'"cost": {cost}' in raw
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(return_value=httpx.Response(200, content=raw.encode()))
    )
    with pytest.raises(JevCallError) as excinfo:
        await _call_once()
    assert excinfo.value.reason == "malformed_reply"
    assert excinfo.value.billed_cost_usd == pytest.approx(billed)
    assert "fall back to the guard tier's pick" in str(excinfo.value)


def _with_cost(body: dict[str, Any], cost: float) -> dict[str, Any]:
    body["usage"]["cost"] = cost
    return body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "reason", "billed"),
    [
        (
            _response(_with_cost(_success_body(choice="maybe"), 0.004)),
            "invalid_option",
            0.004,
        ),
        (
            _response(_with_cost(_success_body(question_key="another.decision"), 0.004)),
            "malformed_reply",
            0.004,
        ),
        (httpx.Response(200, content=b"not json at all"), "malformed_reply", 0.0),
        (
            _response({"model": "m", "answers": {}, "usage": {"input_tokens": 1}}),
            "malformed_reply",
            MAX_JEV_COST_USD,
        ),
        (httpx.Response(503, content=b"unavailable"), "http_error", 0.0),
    ],
    ids=["an option outside the set", "the wrong question key", "not JSON", "no cost stated", "HTTP 503"],
)
async def test_an_unusable_reply_still_reports_what_it_cost(
    monkeypatch: pytest.MonkeyPatch, reply: httpx.Response, reason: str, billed: float
) -> None:
    """Fix round, F-8.6-J10, then clamped by F-8.6-V01 and V03: a reply
    that came back but cannot be used was billed all the same. A reply
    that states no cost at all is billed the ceiling (V03), never $0.0,
    since a call that reached the provider and was billed should not be
    invisible to the cost caps; "not JSON" and "HTTP 503" never got far
    enough to state a cost at all, so those stay $0.0."""
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=reply))
    with pytest.raises(JevCallError) as excinfo:
        await _call_once()
    assert excinfo.value.reason == reason
    assert excinfo.value.billed_cost_usd == pytest.approx(billed)


@pytest.mark.asyncio
async def test_an_oversized_probabilities_map_is_a_malformed_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _success_body()
    body["answers"]["guardrail.relevancy"]["probabilities"] = {f"k{i}": 0.0 for i in range(13)}
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(body)))
    with pytest.raises(JevCallError) as excinfo:
        await _call_once()
    assert excinfo.value.reason == "malformed_reply"


async def _slow_post(*_args: Any, **_kwargs: Any) -> httpx.Response:
    await asyncio.sleep(5.0)
    return _response(_success_body())


async def _call_once() -> JevResult:
    return await call_jev(
        model="typesafe/jev-1.13",
        question_key="guardrail.relevancy",
        state="x",
        options=["relevant", "not_relevant"],
        api_key="test-key",
    )


@pytest.mark.asyncio
async def test_a_slow_jev_is_cut_off_at_three_seconds_in_total(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fake Jev that answers correctly after 5 seconds. Goes red if the
    total bound is removed, or if `_TIMEOUT_S` is raised past 5 seconds."""
    monkeypatch.setattr(jev_client_module, "_post", _slow_post)
    started = time.monotonic()
    with pytest.raises(JevCallError) as excinfo:
        await _call_once()
    elapsed = time.monotonic() - started
    assert excinfo.value.reason == "timeout"
    assert "in total" in str(excinfo.value)
    assert 2.9 <= elapsed < 3.5, elapsed


@pytest.mark.asyncio
async def test_a_body_that_trickles_in_cannot_outlast_the_total_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The judge's exact shape, through the REAL `_post` and a real httpx
    client: the headers arrive at once, then the JSON body in four pieces
    1.5 seconds apart. No single gap reaches 3 seconds, so a per-read limit
    never fires; only a bound on the whole call can stop it."""
    body = json.dumps(_success_body()).encode()
    size = len(body) // 4 + 1
    pieces = [body[i : i + size] for i in range(0, len(body), size)]

    async def _trickle() -> Any:
        for piece in pieces:
            await asyncio.sleep(1.5)
            yield piece

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_trickle())

    real_client = httpx.AsyncClient

    def _client_with_trickling_transport(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return real_client(*args, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(jev_client_module.httpx, "AsyncClient", _client_with_trickling_transport)
    started = time.monotonic()
    with pytest.raises(JevCallError) as excinfo:
        await _call_once()
    elapsed = time.monotonic() - started
    assert excinfo.value.reason == "timeout"
    assert elapsed < 3.5, elapsed


# ---------------------------------------------------------------------------
# Build phase 8.6, T-8.6-02: several questions in one call. The shape was
# pinned live on 2026-09-26 (builder K's report, findings K-02 to K-04).
# ---------------------------------------------------------------------------

_YES_NO = jev_client_module.JevChoiceQuestion(
    options=("yes", "no"),
    instructions="Judge ITEM 1 only.",
    criteria={"yes": "It adds something.", "no": "It adds nothing."},
)


def _batch_questions(count: int = 2) -> dict[str, jev_client_module.JevChoiceQuestion]:
    return {f"item_{n}": _YES_NO for n in range(1, count + 1)}


def _batch_body(choices: dict[str, str], *, cost: float = 5.3e-05) -> dict[str, Any]:
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            key: {
                "type": "choice",
                "choice": choice,
                "probabilities": {"yes": 0.1, "no": 0.9} if choice == "no" else {"yes": 1, "no": 0},
                "confidence": 0.8,
            }
            for key, choice in choices.items()
        },
        "usage": {"input_tokens": 1267, "output_tokens": 123, "cost": cost},
        "id": "gen-dec-test",
        "provider": "TypeSafe",
    }


async def _batch_once(**overrides: Any) -> jev_client_module.JevBatchResult:
    kwargs: dict[str, Any] = {
        "model": "typesafe/jev-1.13",
        "state": "ITEM 1 ... ITEM 2 ...",
        "questions": _batch_questions(),
        "api_key": "test-key",
    }
    kwargs.update(overrides)
    return await jev_client_module.call_jev_batch(**kwargs)


@pytest.mark.asyncio
async def test_a_batch_is_one_call_with_every_question_over_one_state(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_post = AsyncMock(return_value=_response(_batch_body({"item_1": "no", "item_2": "yes"})))
    monkeypatch.setattr(jev_client_module, "_post", mock_post)

    result = await _batch_once()

    assert mock_post.await_count == 1, "one call for every question, never one per question"
    body = mock_post.await_args.args[1]
    assert body["state"] == "ITEM 1 ... ITEM 2 ..."
    assert set(body["questions"]) == {"item_1", "item_2"}
    for question in body["questions"].values():
        assert question == {
            "type": "choice",
            "options": ["yes", "no"],
            "instructions": "Judge ITEM 1 only.",
            "criteria": {"yes": "It adds something.", "no": "It adds nothing."},
        }
    assert result.answers["item_1"].choice == "no" and result.answers["item_2"].choice == "yes"
    assert result.cost_usd == pytest.approx(5.3e-05)
    assert result.input_tokens == 1267


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "choices",
    [
        {"item_1": "no"},
        {"item_1": "no", "item_2": "no", "item_3": "no"},
        {"item_1": "no", "other": "no"},
    ],
    ids=["an item missing", "an item never asked", "a key never asked"],
)
async def test_a_batch_reply_that_does_not_match_the_questions_is_malformed(
    monkeypatch: pytest.MonkeyPatch, choices: dict[str, str]
) -> None:
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(_batch_body(choices))))
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once()
    assert excinfo.value.reason == "malformed_reply"
    assert "fall back to the guard tier" in str(excinfo.value)


@pytest.mark.asyncio
async def test_a_batch_answer_outside_its_options_is_an_invalid_option(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _batch_body({"item_1": "no", "item_2": "maybe"})
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=_response(body)))
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once()
    assert excinfo.value.reason == "invalid_option"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cost", "billed"),
    [
        ("Infinity", MAX_JEV_COST_USD),
        ("NaN", MAX_JEV_COST_USD),
        ("-0.1", MAX_JEV_COST_USD),
        ("0.5", MAX_JEV_COST_USD),
        ("0.02", MAX_JEV_COST_USD),
    ],
)
async def test_a_batch_cost_no_call_could_have_is_malformed(
    monkeypatch: pytest.MonkeyPatch, cost: str, billed: float
) -> None:
    """Malformed, so nothing in the reply is used; a real amount above the
    ceiling, or a figure that is not a finite, non-negative number, is
    billed the ceiling itself, never the reported figure and never $0.0
    (F-8.6-J10, clamped by F-8.6-V01 and V03)."""
    raw = json.dumps(_batch_body({"item_1": "no", "item_2": "no"})).replace('"cost": 5.3e-05', f'"cost": {cost}')
    assert f'"cost": {cost}' in raw
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=httpx.Response(200, content=raw.encode())))
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once()
    assert excinfo.value.reason == "malformed_reply"
    assert excinfo.value.billed_cost_usd == pytest.approx(billed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("choices", "reason"),
    [
        ({"item_1": "no", "item_2": "maybe"}, "invalid_option"),
        ({"item_1": "no"}, "malformed_reply"),
    ],
    ids=["an answer outside its options", "an item missing"],
)
async def test_an_unusable_batch_reply_still_reports_what_it_cost(
    monkeypatch: pytest.MonkeyPatch, choices: dict[str, str], reason: str
) -> None:
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(return_value=_response(_batch_body(choices, cost=0.004)))
    )
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once()
    assert excinfo.value.reason == reason
    assert excinfo.value.billed_cost_usd == pytest.approx(0.004)


@pytest.mark.asyncio
async def test_a_batch_is_cut_at_the_callers_shorter_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_client_module, "_post", _slow_post)
    started = time.monotonic()
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once(timeout_s=0.3)
    elapsed = time.monotonic() - started
    assert excinfo.value.reason == "timeout"
    assert 0.25 <= elapsed < 0.6, elapsed


@pytest.mark.asyncio
async def test_a_batch_bound_can_shorten_but_never_lengthen_the_total_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller passing more time than Jev's total bound still gets the
    bound: here the bound is patched to 0.2 s and the caller asks for 10."""
    monkeypatch.setattr(jev_client_module, "_TIMEOUT_S", 0.2)
    monkeypatch.setattr(jev_client_module, "_post", _slow_post)
    started = time.monotonic()
    with pytest.raises(JevCallError):
        await _batch_once(timeout_s=10.0)
    assert time.monotonic() - started < 0.5


@pytest.mark.asyncio
async def test_a_batch_with_no_time_left_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_post = AsyncMock(return_value=_response(_batch_body({"item_1": "no", "item_2": "no"})))
    monkeypatch.setattr(jev_client_module, "_post", mock_post)
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once(timeout_s=0.0)
    assert excinfo.value.reason == "timeout"
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_a_batch_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    monkeypatch.setattr(jev_client_module, "_post", mock_post)
    with pytest.raises(JevCallError) as excinfo:
        await _batch_once()
    assert excinfo.value.reason == "http_error"
    assert mock_post.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "questions",
    [
        {},
        {f"item_{n}": _YES_NO for n in range(1, jev_client_module.MAX_BATCH_QUESTIONS + 2)},
        {"item_1": jev_client_module.JevChoiceQuestion(options=("yes", "no"), instructions="x", criteria={"yes": "y"})},
        {"item_1": jev_client_module.JevChoiceQuestion(options=("yes", "no"), instructions="x" * 1001, criteria={"yes": "y", "no": "n"})},
    ],
    ids=["no questions", "too many", "a criterion missing", "instructions too long"],
)
async def test_a_batch_that_should_never_be_sent_is_refused_in_code(
    monkeypatch: pytest.MonkeyPatch, questions: dict[str, Any]
) -> None:
    mock_post = AsyncMock()
    monkeypatch.setattr(jev_client_module, "_post", mock_post)
    with pytest.raises(ValueError):
        await _batch_once(questions=questions)
    mock_post.assert_not_called()
