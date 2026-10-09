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
    JEV_FLOOR_COST_USD,
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
    # The live price stated, $0.0000148, is under the floor, so the floor is
    # what the caller charges (fix round, J-GR-04).
    assert result.cost_usd == pytest.approx(JEV_FLOOR_COST_USD)
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
        ("NaN", JEV_FLOOR_COST_USD),
        ("-0.1", JEV_FLOOR_COST_USD),
        ("0.5", MAX_JEV_COST_USD),
        ("0.02", MAX_JEV_COST_USD),
        ("true", JEV_FLOOR_COST_USD),
    ],
)
async def test_a_cost_no_decision_could_have_is_a_malformed_reply(
    monkeypatch: pytest.MonkeyPatch, cost: str, billed: float
) -> None:
    """F-8.2-J15: Jev's cost is charged straight into every cost cap. A
    reply claiming `Infinity` (which Python's JSON parser accepts) stopped
    every later model call in the question. Such a reply is malformed, so
    the guard's pick decides.

    The owner's rule of 2026-09-29 (step 3a of the guardrail design): a
    stated cost above the ceiling, infinity included, is billed the
    ceiling, never the reported figure and never less (F-84-A06); a figure
    that is not an amount (not a number, negative, a boolean) is billed the
    `JEV_FLOOR_COST_USD` floor, never $0.0."""
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
        (httpx.Response(200, content=b"not json at all"), "malformed_reply", JEV_FLOOR_COST_USD),
        (
            _response({"model": "m", "answers": {}, "usage": {"input_tokens": 1}}),
            "malformed_reply",
            JEV_FLOOR_COST_USD,
        ),
        (httpx.Response(503, content=b"unavailable"), "http_error", JEV_FLOOR_COST_USD),
        (httpx.Response(429, content=b"slow down"), "http_error", JEV_FLOOR_COST_USD),
        (httpx.Response(402, content=b"pay"), "http_error", JEV_FLOOR_COST_USD),
    ],
    ids=[
        "an option outside the set",
        "the wrong question key",
        "not JSON",
        "no cost stated",
        "HTTP 503",
        "HTTP 429",
        "HTTP 402",
    ],
)
async def test_an_unusable_reply_still_reports_what_it_cost(
    monkeypatch: pytest.MonkeyPatch, reply: httpx.Response, reason: str, billed: float
) -> None:
    """A reply that came back but cannot be used was billed all the same
    (F-8.6-J10), and is charged as any reply is (the owner's rule of
    2026-09-29, F-84-J04): the cost it states, or the `JEV_FLOOR_COST_USD`
    floor when it states none or its body cannot be read. An error status
    (503, 429, 402) is a reply from the provider too, so it is charged the
    floor, never $0.0 (F-72-V03)."""
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
    assert result.cost_usd == pytest.approx(JEV_FLOOR_COST_USD)  # $0.000053 stated, under the floor (J-GR-04)
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
        ("NaN", JEV_FLOOR_COST_USD),
        ("-0.1", JEV_FLOOR_COST_USD),
        ("0.5", MAX_JEV_COST_USD),
        ("0.02", MAX_JEV_COST_USD),
    ],
)
async def test_a_batch_cost_no_call_could_have_is_malformed(
    monkeypatch: pytest.MonkeyPatch, cost: str, billed: float
) -> None:
    """Malformed, so nothing in the reply is used; a stated cost above the
    ceiling is billed the ceiling (F-8.6-V01, F-84-A06), and a figure that
    is not an amount the floor, never $0.0 (the owner's rule of
    2026-09-29)."""
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


# ---------------------------------------------------------------------------
# Fix round of the guardrail design (cards 84 and 72): the free-time clock
# on every Jev call, `wait_counting_free_time`, on the virtual clock. Each
# arm names the finding it closes; each was red on the first build.
# ---------------------------------------------------------------------------

_BOUND_S = jev_client_module.JEV_TOTAL_TIMEOUT_S
_CAP_S = _BOUND_S + jev_client_module.JEV_STALL_ALLOWANCE_S
_TEST_KEY = "test-key"


def _on_the_virtual_clock(monkeypatch: pytest.MonkeyPatch, make: Any) -> Any:
    from tests.system_03_search_agent.virtual_clock import run_virtual

    return run_virtual(monkeypatch, make)


async def _never() -> str:
    await asyncio.sleep(10_000)
    return "never"


async def _timed(awaitable: Any, budget_s: float, *, guard_s: float | None = 200.0) -> tuple[object, float]:
    """(what the wait returned or raised, loop seconds it took), under an
    outer guard that a wait which never ends runs into (none when `guard_s`
    is None, so the guard's own turns are not measured)."""
    loop = asyncio.get_running_loop()
    began = loop.time()
    wait = jev_client_module.wait_counting_free_time(awaitable, budget_s)
    try:
        result: object = await (wait if guard_s is None else asyncio.wait_for(wait, guard_s))
    except TimeoutError as exc:
        result = exc
    return result, loop.time() - began


@pytest.mark.parametrize("chunk_s", [0.03, 0.06, 0.1, 0.15, 0.3, 0.6])
def test_a_hung_jev_call_on_a_busy_server_ends_by_its_bound_plus_the_allowance(
    monkeypatch: pytest.MonkeyPatch, chunk_s: float
) -> None:
    """A-GR-06: other questions' synchronous work blocks the loop in chunks,
    for ever, and Jev never answers. The wait ends by the bound plus the 2 s
    allowance, give or take one chunk of the busy loop (it stops rather than
    start a look that would carry it past, and does not wait for the call it
    stops to wind down). The first build ran 5.22 s at 0.06 s chunks and
    7.20 s at 0.6 s chunks.

    MUTATION PROOF: dropping the prediction (`next_look_s = 0.0`) turns the
    0.3 s and 0.6 s arms red; awaiting the stopped call again turns the
    0.6 s arm red."""

    async def _go() -> tuple[object, float]:
        loop = asyncio.get_running_loop()

        async def _busy() -> None:
            while True:
                loop.stall(chunk_s)  # type: ignore[attr-defined]
                await asyncio.sleep(0)

        busy = asyncio.ensure_future(_busy())
        try:
            return await _timed(_never(), _BOUND_S, guard_s=None)
        finally:
            busy.cancel()

    result, took_s = _on_the_virtual_clock(monkeypatch, _go)
    assert isinstance(result, TimeoutError)
    assert took_s <= _CAP_S + chunk_s + 1e-6, took_s


def test_a_clock_that_stands_still_still_ends_the_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """J-GR-03: the module's clock never moves, so nothing is ever counted;
    the wait still ends, on its look limit, within about the cap of loop
    time. The first build waited until the outer guard fired."""

    async def _go() -> tuple[object, float]:
        monkeypatch.setattr(jev_client_module.time, "monotonic", lambda: 5.0)
        return await _timed(_never(), _BOUND_S)

    result, took_s = _on_the_virtual_clock(monkeypatch, _go)
    assert isinstance(result, jev_client_module.PausedTimeoutError)
    assert took_s <= _CAP_S + 1.0, took_s


def test_a_clock_that_steps_backwards_still_ends_the_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """A-GR-09: the clock steps back 100 s once; the wait neither un-counts
    time below zero nor waits the 100 s. The first build waited 103 s."""

    async def _go() -> tuple[object, float]:
        loop = asyncio.get_running_loop()
        reads = [0]

        def _monotonic() -> float:
            reads[0] += 1
            return loop.time() - (100.0 if reads[0] >= 5 else 0.0)

        monkeypatch.setattr(jev_client_module.time, "monotonic", _monotonic)
        return await _timed(_never(), _BOUND_S)

    result, took_s = _on_the_virtual_clock(monkeypatch, _go)
    assert isinstance(result, TimeoutError)
    assert took_s <= _CAP_S + 1.0, took_s


@pytest.mark.parametrize("budget_s", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_a_budget_that_is_not_a_finite_amount_above_zero_ends_at_once(
    monkeypatch: pytest.MonkeyPatch, budget_s: float
) -> None:
    """J-GR-03, A-GR-14: a NaN or infinite budget made the wait look every
    50 ms for ever, since no comparison with NaN is true and infinity never
    runs out. It now times out at once, as `asyncio.wait_for(..., nan)` did
    on develop, and the call it would have waited on is closed, never left
    half started."""

    async def _go() -> tuple[object, float, bool]:
        awaitable = _never()
        result, took_s = await _timed(awaitable, budget_s, guard_s=30.0)
        return result, took_s, awaitable.cr_frame is None

    result, took_s, closed = _on_the_virtual_clock(monkeypatch, _go)
    assert isinstance(result, TimeoutError) and not isinstance(result, jev_client_module.PausedTimeoutError)
    assert took_s == 0.0
    assert closed


async def _batch_with_timeout(*, timeout_s: float) -> Any:
    question = jev_client_module.JevChoiceQuestion(
        options=("yes", "no"), instructions="i", criteria={"yes": "y", "no": "n"}
    )
    return await jev_client_module.call_jev_batch(
        model="m", state="x", questions={"item_1": question}, api_key=_TEST_KEY, timeout_s=timeout_s
    )


async def _hang(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
    await asyncio.sleep(60)
    raise AssertionError("never answers")


@pytest.mark.asyncio
async def test_a_batch_handed_a_nan_timeout_gives_up_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A-GR-14: `min(nan, 3.0)` is NaN, so `call_jev_batch` handed a NaN
    timeout waited for ever on a hung Jev; it now fails at once as a timeout,
    charged nothing."""
    monkeypatch.setattr(jev_client_module, "_post", _hang)
    started = time.monotonic()
    with pytest.raises(JevCallError) as excinfo:
        await _batch_with_timeout(timeout_s=float("nan"))
    assert excinfo.value.reason == "timeout" and excinfo.value.billed_cost_usd == 0.0
    assert time.monotonic() - started < 1.0


def test_a_reply_that_arrived_during_a_long_pause_wins_over_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A-GR-07: Jev answers at 0.2 s, but a 6 s pause of the server starts at
    0.1 s, so the reply lands while the loop is frozen and the pause carries
    the wait past its 5 s cap. The reply that arrived is read before the
    clock gives up. The first build checked its cap first and threw the
    reply away.

    MUTATION PROOF: `_read_what_arrived` returning False at once turns this
    red."""

    async def _go() -> tuple[object, float]:
        loop = asyncio.get_running_loop()

        async def _reply() -> str:
            await asyncio.sleep(0.2)
            return "reply"

        loop.call_later(0.1, loop.stall, 6.0)  # type: ignore[attr-defined]
        return await _timed(_reply(), _BOUND_S)

    result, took_s = _on_the_virtual_clock(monkeypatch, _go)
    assert result == "reply"
    assert took_s == pytest.approx(6.1)


def test_pauses_never_spend_jevs_own_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """J-GR-01, A-GR-08: three 0.3 s pauses inside the wait, and Jev's reply
    after 2.9 s of time the loop was free. Each pause interrupts one look,
    and that look counts nothing, so the reply is read. The first build
    counted each interrupted look as 0.1 s, more than the 0.05 s it asked,
    so the pauses spent Jev's last tenths and the reply was lost.

    MUTATION PROOF: counting an interrupted look as the time asked plus the
    slack again turns this red."""

    async def _go() -> tuple[object, float]:
        loop = asyncio.get_running_loop()

        async def _reply() -> str:
            await asyncio.sleep(2.9 + 0.9)  # 2.9 s free, plus the three pauses
            return "reply"

        for at_s in (0.52, 1.52, 2.52):
            loop.call_later(at_s, loop.stall, 0.3)  # type: ignore[attr-defined]
        return await _timed(_reply(), _BOUND_S)

    result, _ = _on_the_virtual_clock(monkeypatch, _go)
    assert result == "reply"


@pytest.mark.parametrize(
    ("pause_s", "paused"),
    [(0.0, False), (1.0, False), (2.5, True)],
    ids=["no pause: Jev's own bound", "a 1 s pause: Jev's own bound", "a 2.5 s pause: the real-time cap"],
)
def test_a_wait_says_whether_jevs_bound_or_a_pause_ended_it(
    monkeypatch: pytest.MonkeyPatch, pause_s: float, paused: bool
) -> None:
    """A-GR-11: a hung Jev call ends on Jev's own 3 s bound, a plain timeout,
    unless the server's pauses carried it to the real-time cap first; then
    it says so (`PausedTimeoutError`, `JevCallError.after_a_pause`), and the
    guardrail never reads the missing pick as "not an injection"."""
    monkeypatch.setattr(jev_client_module, "_post", _hang)

    async def _go() -> JevCallError:
        loop = asyncio.get_running_loop()
        if pause_s:
            loop.call_later(0.5, loop.stall, pause_s)  # type: ignore[attr-defined]
        with pytest.raises(JevCallError) as excinfo:
            await call_jev(
                model="m",
                question_key="guardrail.injection",
                state="x",
                options=["injection", "not_injection"],
                api_key=_TEST_KEY,
            )
        return excinfo.value

    error = _on_the_virtual_clock(monkeypatch, _go)
    assert error.reason == "timeout"
    assert error.after_a_pause is paused


def test_jevs_clock_ends_at_its_bound_plus_the_allowance_whatever_the_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-GR-02, the rule that ships, pinned: Jev's clock ends at its bound
    plus the 2 s allowance of real time from when the wait began, not at a
    pause of 2 s. A 4.7 s pause before a 0.2 s reply is read (4.9 s); a
    4.9 s pause before the same reply is not (5.1 s, past the 5 s)."""

    def _go(pause_s: float) -> Any:
        async def _run() -> object:
            loop = asyncio.get_running_loop()

            async def _reply() -> str:
                loop.stall(pause_s)  # type: ignore[attr-defined]
                await asyncio.sleep(0.2)
                return "reply"

            result, _ = await _timed(_reply(), _BOUND_S)
            return result

        return _run

    assert _on_the_virtual_clock(monkeypatch, _go(4.7)) == "reply"
    assert isinstance(_on_the_virtual_clock(monkeypatch, _go(4.9)), jev_client_module.PausedTimeoutError)
