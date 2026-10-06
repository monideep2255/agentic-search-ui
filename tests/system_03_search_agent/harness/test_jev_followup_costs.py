"""R-07 (phase 8.6 re-land follow-up): every Jev reply that came back
from the provider is charged inside its ceiling, and the log says what was
charged (F-8.6-RA01, RJ04, RJ05).

Before the fix, three reply shapes reached the provider, were billed by it,
and were charged $0.0 on the question:

- a `usage.cost` that is an integer too large for a float: `_reported_cost_usd`
  logged "charged the $0.01 ceiling", then `float(usage["cost"])` raised
  `OverflowError`, which escaped `call_jev` and `call_jev_batch` with no
  `billed_cost_usd`;
- a `confidence` (or a probability) too large for a float: the same escape;
- a 200 whose body is empty or not JSON: `billed_usd` was still 0.0 when
  `response.json()` raised.

What this file covers:
    - `call_jev` and `call_jev_batch` directly, every shape above.
    - The three charge sites end to end, each on a real `Harness`:
      `harness.decide.decide`, `core.graph._jev_injection_pick` and
      `synthesis.sentence_check._ask_jev`.
    - The warning names the amount the error carries.

What it deliberately omits: a live endpoint. No network call anywhere:
`jev_client._post` is the one seam, patched in every test.

The rule the charges follow is the one `JevCallError` states: a reply
that states a usable amount at or under the ceiling is charged that
amount, and anything else the ceiling. So a reply whose `confidence`
overflows but whose `cost` reads $0.001 is charged $0.001, exactly like a
reply whose `confidence` is the string "abc" (the control below), never
$0.0.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import httpx
import litellm
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import (
    MAX_JEV_COST_USD,
    JevCallError,
    JevChoiceQuestion,
    call_jev,
    call_jev_batch,
)
from system_03_search_agent.synthesis import sentence_check as sentence_check_module

_HUGE = "1" + "0" * 400  # an integer JSON parses and `float()` cannot hold


def _raw_json(body: dict[str, Any], raw: dict[str, str]) -> str:
    """`body` as JSON with each placeholder string in `raw` replaced by its
    raw JSON text, so a number too large for a float, or a string where a
    number belongs, can be written exactly as a reply would carry it."""
    text = json.dumps(body)
    for placeholder, value in raw.items():
        text = text.replace(json.dumps(placeholder), value)
    return text


def _single_body(*, key: str, choice: str, cost: str = "0.001", confidence: str = "0.8", prob: str = "0.8") -> str:
    body = {
        "model": "m",
        "answers": {
            key: {
                "type": "choice",
                "choice": choice,
                "confidence": "<confidence>",
                "probabilities": {choice: "<prob>"},
            }
        },
        "usage": {"input_tokens": 10, "output_tokens": 1, "cost": "<cost>"},
    }
    return _raw_json(body, {"<confidence>": confidence, "<prob>": prob, "<cost>": cost})


def _batch_body(*, cost: str = "0.001", confidence: str = "0.8") -> str:
    body = {
        "model": "m",
        "answers": {
            "item_1": {"choice": "no", "confidence": "<confidence>", "probabilities": {"no": 0.8}},
            "item_2": {"choice": "no", "confidence": 0.8, "probabilities": {"no": 0.8}},
        },
        "usage": {"input_tokens": 10, "output_tokens": 1, "cost": "<cost>"},
    }
    return _raw_json(body, {"<confidence>": confidence, "<cost>": cost})


def _patch_reply(monkeypatch: pytest.MonkeyPatch, content: bytes) -> None:
    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, content=content)

    monkeypatch.setattr(jev_client_module, "_post", _post)


async def _single() -> None:
    await call_jev(
        model="m",
        question_key="guardrail.relevancy",
        state="x",
        options=["on_topic", "off_topic"],
        api_key="test-key",
    )


async def _batch() -> None:
    question = JevChoiceQuestion(
        options=("yes", "no"), instructions="i", criteria={"yes": "y", "no": "n"}
    )
    await call_jev_batch(model="m", state="x", questions={"item_1": question, "item_2": question}, api_key="k")


# Every unreadable 200 reply, with what it must be charged.
_SINGLE_CASES = [
    (_single_body(key="guardrail.relevancy", choice="on_topic", cost=_HUGE).encode(), MAX_JEV_COST_USD),
    (_single_body(key="guardrail.relevancy", choice="on_topic", confidence=_HUGE).encode(), 0.001),
    (_single_body(key="guardrail.relevancy", choice="on_topic", prob=_HUGE).encode(), 0.001),
    (_single_body(key="guardrail.relevancy", choice="on_topic", confidence='"abc"').encode(), 0.001),
    (b"not json at all", MAX_JEV_COST_USD),
    (b"", MAX_JEV_COST_USD),
    (b"\xff\xfe\xfa", MAX_JEV_COST_USD),
]
_SINGLE_IDS = [
    "cost too large for a float",
    "confidence too large for a float",
    "probability too large for a float",
    "control: confidence a string",
    "a body that is not JSON",
    "an empty body",
    "a body that is not text",
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("content", "billed"), _SINGLE_CASES, ids=_SINGLE_IDS)
async def test_call_jev_charges_an_unreadable_reply_inside_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, content: bytes, billed: float
) -> None:
    _patch_reply(monkeypatch, content)
    with pytest.raises(JevCallError) as excinfo:
        await _single()
    assert excinfo.value.reason == "malformed_reply"
    assert excinfo.value.billed_cost_usd == pytest.approx(billed)
    assert "fall back to the guard tier" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "billed"),
    [
        (_batch_body(cost=_HUGE).encode(), MAX_JEV_COST_USD),
        (_batch_body(confidence=_HUGE).encode(), 0.001),
        (_batch_body(confidence='"abc"').encode(), 0.001),
        (b"not json at all", MAX_JEV_COST_USD),
        (b"", MAX_JEV_COST_USD),
    ],
    ids=[
        "cost too large for a float",
        "confidence too large for a float",
        "control: confidence a string",
        "a body that is not JSON",
        "an empty body",
    ],
)
async def test_call_jev_batch_charges_an_unreadable_reply_inside_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, content: bytes, billed: float
) -> None:
    _patch_reply(monkeypatch, content)
    with pytest.raises(JevCallError) as excinfo:
        await _batch()
    assert excinfo.value.reason == "malformed_reply"
    assert excinfo.value.billed_cost_usd == pytest.approx(billed)
    assert "fall back to the guard tier" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "said"),
    [
        (b"not json at all", "is not JSON, so it is charged the $0.01 ceiling"),
        (
            _single_body(key="guardrail.relevancy", choice="on_topic", cost=_HUGE).encode(),
            "so it is charged the $0.01 ceiling",
        ),
    ],
    ids=["a body that is not JSON", "cost too large for a float"],
)
async def test_the_warning_names_the_amount_actually_charged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, content: bytes, said: str
) -> None:
    """RA01: the warning said "charged the $0.01 ceiling" while $0.0 was
    charged. The warning and the error's charge now agree."""
    assert f"${MAX_JEV_COST_USD:.2f}" == "$0.01"
    _patch_reply(monkeypatch, content)
    with (
        caplog.at_level(logging.WARNING, logger=jev_client_module.__name__),
        pytest.raises(JevCallError) as excinfo,
    ):
        await _single()
    assert said in caplog.text
    assert excinfo.value.billed_cost_usd == pytest.approx(MAX_JEV_COST_USD)


# ---------------------------------------------------------------------------
# The three charge sites, each on a real Harness.
# ---------------------------------------------------------------------------


@pytest.fixture
def jev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")

    async def _guard_fallback(**_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="on_topic"))],
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
        )

    monkeypatch.setattr(litellm, "acompletion", _guard_fallback)
    monkeypatch.setattr(
        litellm, "get_model_info", lambda model: {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0}
    )


_SITE_CASES = [
    ("cost too large for a float", "cost"),
    ("a body that is not JSON", "not_json"),
    ("an empty body", "empty"),
]


def _site_content(shape: str, *, key: str, choice: str, batch: bool = False) -> bytes:
    if shape == "not_json":
        return b"not json at all"
    if shape == "empty":
        return b""
    if batch:
        return _batch_body(cost=_HUGE).encode()
    return _single_body(key=key, choice=choice, cost=_HUGE).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_decide_charges_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="guardrail.relevancy", choice="on_topic"))
    harness = Harness(trace_id="d")
    record = await decide(harness, "d", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.fallback_reason is not None and record.fallback_reason.endswith("malformed_reply")
    assert harness.get_query_cost_usd("d") == pytest.approx(MAX_JEV_COST_USD)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_injection_pick_charges_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="guardrail.injection", choice="not_injection"))
    harness = Harness(trace_id="i")
    result = await graph_module._jev_injection_pick(harness, "i", "What does BRCA1 do?")
    assert result == "malformed_reply"
    assert harness.get_query_cost_usd("i") == pytest.approx(MAX_JEV_COST_USD)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_sentence_check_charges_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="", choice="", batch=True))
    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    # Card 99: the placeholder items carry no sentence, so no pair call; this
    # test is about the item call's charge.
    monkeypatch.setattr(sentence_check_module, "build_pair_calls", lambda sent: ([], frozenset()))
    harness = Harness(trace_id="s")
    with pytest.raises(JevCallError) as excinfo:
        await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    assert excinfo.value.reason == "malformed_reply"
    assert harness.get_query_cost_usd("s") == pytest.approx(MAX_JEV_COST_USD)


def test_the_probe_bodies_are_what_they_claim() -> None:
    """The fixtures above really carry the shapes they name: the huge
    number parses from JSON and cannot become a float."""
    parsed = json.loads(_single_body(key="k", choice="c", cost=_HUGE))
    with pytest.raises(OverflowError):
        float(parsed["usage"]["cost"])
    with pytest.raises(ValueError):
        json.loads("")
