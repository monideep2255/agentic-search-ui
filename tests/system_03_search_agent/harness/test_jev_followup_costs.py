"""Step 3a of the guardrail design (cards 84 and 72): every Jev reply is
charged by the product owner's rule of 2026-09-29, through the real
`call_jev` and `call_jev_batch` and at all three charge sites on a real
`Harness`.

The rule:

| What came back | Charged |
|---|---|
| a reply stating a finite cost above $0 and at most `MAX_JEV_COST_USD` | that cost |
| a reply stating more, however spelled | `JEV_FLOOR_COST_USD` (the rule as written, J-GRS-03; develop charged the ceiling) |
| a reply stating $0, no cost, an unreadable amount, or a body that cannot be read | `JEV_FLOOR_COST_USD` (F-72-J02, A03) |
| an error status, 500, 429 or 402 | `JEV_FLOOR_COST_USD` (F-72-V03) |
| nothing: a timeout or a transport failure | nothing |

Usable or unusable makes no difference (F-84-J04). Before this, develop
charged a stated $0 nothing, an error status nothing, and a reply stating
no amount the one-cent ceiling, so a drift in Jev's reply shape cost about
seven cents a question and could stop every search at the $25 daily cap
(F-72-A03).

What it deliberately omits: a live endpoint. `jev_client._post` is the one
seam, patched in every test.

MUTATION PROOF: `_send` raising its error status with no charge again
(develop) turns the HTTP arms red; `_unusable_reply` charging the floor for
every unusable reply (the parked branch's F-84-J04) turns
"unusable, states a sensible cost" red; catching a list of error types in
`call_jev` again turns the `"probabilities": null` arm red with an
uncharged `AttributeError`; `call_jev_batch`'s invalid-option arm charging
`parsed.cost_usd` (the adversary's M4) turns "unusable, states $0" in the
batch red; `_json_payload` catching `ValueError` only (M5) turns "a body
nested too deep" red with an uncharged `RecursionError`.
"""

from __future__ import annotations

import asyncio
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
    JEV_FLOOR_COST_USD,
    JevCallError,
    JevChoiceQuestion,
    call_jev,
    call_jev_batch,
)
from system_03_search_agent.synthesis import sentence_check as sentence_check_module

_HUGE = "1" + "0" * 400  # an integer JSON parses and `float()` cannot hold
_DEEP = b"[" * 100_000 + b"]" * 100_000  # JSON nested deeper than the reader recurses
_SENSIBLE = "0.00002"


def _raw_json(body: dict[str, Any], raw: dict[str, str]) -> str:
    """`body` as JSON with each placeholder string in `raw` replaced by its
    raw JSON text, so a number too large for a float, or a string where a
    number belongs, can be written exactly as a reply would carry it."""
    text = json.dumps(body)
    for placeholder, value in raw.items():
        text = text.replace(json.dumps(placeholder), value)
    return text


def _single_body(
    *, key: str, choice: str, cost: str | None = _SENSIBLE, confidence: str = "0.8", probabilities: str | None = None
) -> bytes:
    usage: dict[str, Any] = {"input_tokens": 10, "output_tokens": 1}
    if cost is not None:
        usage["cost"] = "<cost>"
    body = {
        "model": "m",
        "answers": {key: {"type": "choice", "choice": choice, "confidence": "<confidence>", "probabilities": "<probs>"}},
        "usage": usage,
    }
    probs = probabilities if probabilities is not None else json.dumps({choice: 0.8})
    return _raw_json(body, {"<confidence>": confidence, "<cost>": cost or "", "<probs>": probs}).encode()


def _batch_body(*, cost: str | None = _SENSIBLE, choice: str = "no", confidence: str = "0.8") -> bytes:
    usage: dict[str, Any] = {"input_tokens": 10, "output_tokens": 1}
    if cost is not None:
        usage["cost"] = "<cost>"
    body = {
        "model": "m",
        "answers": {
            "item_1": {"choice": choice, "confidence": "<confidence>", "probabilities": {"no": 0.8}},
            "item_2": {"choice": "no", "confidence": 0.8, "probabilities": {"no": 0.8}},
        },
        "usage": usage,
    }
    return _raw_json(body, {"<confidence>": confidence, "<cost>": cost or ""}).encode()


def _patch_post(monkeypatch: pytest.MonkeyPatch, reply: Any) -> None:
    """`reply` is a status and body, an exception to raise, or "hang"."""

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        if reply == "hang":
            await asyncio.sleep(60)
        if isinstance(reply, BaseException):
            raise reply
        status, content = reply
        return httpx.Response(status, content=content)

    monkeypatch.setattr(jev_client_module, "_post", _post)


async def _single(key: str = "guardrail.relevancy", options: tuple[str, ...] = ("on_topic", "off_topic")) -> Any:
    return await call_jev(model="m", question_key=key, state="x", options=list(options), api_key="test-key")


async def _batch() -> Any:
    question = JevChoiceQuestion(options=("yes", "no"), instructions="i", criteria={"yes": "y", "no": "n"})
    return await call_jev_batch(model="m", state="x", questions={"item_1": question, "item_2": question}, api_key="k")


# Each case: a label, what `_post` does, the outcome ("ok" or a reason), the charge.
_RELEVANCY = "guardrail.relevancy"
_SINGLE_CASES: list[tuple[str, Any, str, float]] = [
    ("usable, states a sensible cost", (200, _single_body(key=_RELEVANCY, choice="on_topic")), "ok", 0.00002),
    ("usable, states the ceiling", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0.01")), "ok", 0.01),
    ("usable, states $0 (F-72-J02)", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0")), "ok",
     JEV_FLOOR_COST_USD),
    ("unusable, states a sensible cost (F-84-J04)", (200, _single_body(key=_RELEVANCY, choice="maybe")),
     "invalid_option", 0.00002),
    ("probabilities null, states a sensible cost (F-8.6-FJ01)",
     (200, _single_body(key=_RELEVANCY, choice="on_topic", probabilities="null")), "malformed_reply", 0.00002),
    ("confidence too large for a float", (200, _single_body(key=_RELEVANCY, choice="on_topic", confidence=_HUGE)),
     "malformed_reply", 0.00002),
    ("unusable, states $0", (200, _single_body(key=_RELEVANCY, choice="maybe", cost="0")), "invalid_option",
     JEV_FLOOR_COST_USD),
    ("no cost stated", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost=None)), "malformed_reply",
     JEV_FLOOR_COST_USD),
    ("a cost that is not a number", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost='"abc"')),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("states five cents (J-GRS-03)", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0.05")),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("states just above the ceiling", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0.0100000001")),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("states 1e309 (A-GRS-03)", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="1e309")),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("states Infinity", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost="Infinity")),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("states five cents as a string", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost='"0.05"')),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("a cost too large for a float (J-GRS-04)", (200, _single_body(key=_RELEVANCY, choice="on_topic", cost=_HUGE)),
     "malformed_reply", JEV_FLOOR_COST_USD),
    ("usable, states the smallest float above $0", (200, _single_body(key=_RELEVANCY, choice="on_topic",
     cost="5e-324")), "ok", 5e-324),
    ("a body that is not JSON (F-72-A03)", (200, b"not json at all"), "malformed_reply", JEV_FLOOR_COST_USD),
    ("a body nested too deep (F-8.6-FA01)", (200, _DEEP), "malformed_reply", JEV_FLOOR_COST_USD),
    ("an empty body", (200, b""), "malformed_reply", JEV_FLOOR_COST_USD),
    ("a body that is not text", (200, b"\xff\xfe\xfa"), "malformed_reply", JEV_FLOOR_COST_USD),
    ("HTTP 500 (F-72-V03)", (500, b"oops"), "http_error", JEV_FLOOR_COST_USD),
    ("HTTP 429 (F-72-V03)", (429, b"slow down"), "http_error", JEV_FLOOR_COST_USD),
    ("HTTP 402 (F-72-V03)", (402, b"pay"), "http_error", JEV_FLOOR_COST_USD),
    ("a transport failure", httpx.ConnectError("refused"), "http_error", 0.0),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "reply", "outcome", "charged"), _SINGLE_CASES, ids=[c[0] for c in _SINGLE_CASES])
async def test_call_jev_charges_every_reply_by_the_owners_rule(
    monkeypatch: pytest.MonkeyPatch, label: str, reply: Any, outcome: str, charged: float
) -> None:
    _patch_post(monkeypatch, reply)
    if outcome == "ok":
        result = await _single()
        assert result.cost_usd == pytest.approx(charged)
        return
    with pytest.raises(JevCallError) as excinfo:
        await _single()
    assert excinfo.value.reason == outcome
    assert excinfo.value.billed_cost_usd == pytest.approx(charged)
    assert "fall back to the guard tier" in str(excinfo.value)


@pytest.mark.asyncio
async def test_a_timeout_is_charged_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_client_module, "_TIMEOUT_S", 0.05)
    _patch_post(monkeypatch, "hang")
    with pytest.raises(JevCallError) as excinfo:
        await _single()
    assert excinfo.value.reason == "timeout"
    assert excinfo.value.billed_cost_usd == 0.0


_BATCH_CASES: list[tuple[str, Any, str, float]] = [
    ("usable, states a sensible cost", (200, _batch_body()), "ok", 0.00002),
    ("usable, states $0", (200, _batch_body(cost="0")), "ok", JEV_FLOOR_COST_USD),
    ("unusable, states a sensible cost", (200, _batch_body(choice="maybe")), "invalid_option", 0.00002),
    ("unusable, states $0 (A-GRS-06, M4)", (200, _batch_body(choice="maybe", cost="0")), "invalid_option",
     JEV_FLOOR_COST_USD),
    ("confidence too large for a float", (200, _batch_body(confidence=_HUGE)), "malformed_reply", 0.00002),
    ("no cost stated", (200, _batch_body(cost=None)), "malformed_reply", JEV_FLOOR_COST_USD),
    ("states five cents", (200, _batch_body(cost="0.05")), "malformed_reply", JEV_FLOOR_COST_USD),
    ("states 1e309", (200, _batch_body(cost="1e309")), "malformed_reply", JEV_FLOOR_COST_USD),
    ("a cost too large for a float", (200, _batch_body(cost=_HUGE)), "malformed_reply", JEV_FLOOR_COST_USD),
    ("a body that is not JSON", (200, b"not json at all"), "malformed_reply", JEV_FLOOR_COST_USD),
    ("a body nested too deep (A-GRS-06, M5)", (200, _DEEP), "malformed_reply", JEV_FLOOR_COST_USD),
    ("HTTP 500", (500, b"oops"), "http_error", JEV_FLOOR_COST_USD),
    ("a transport failure", httpx.ConnectError("refused"), "http_error", 0.0),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "reply", "outcome", "charged"), _BATCH_CASES, ids=[c[0] for c in _BATCH_CASES])
async def test_call_jev_batch_charges_every_reply_by_the_owners_rule(
    monkeypatch: pytest.MonkeyPatch, label: str, reply: Any, outcome: str, charged: float
) -> None:
    _patch_post(monkeypatch, reply)
    if outcome == "ok":
        result = await _batch()
        assert result.cost_usd == pytest.approx(charged)
        return
    with pytest.raises(JevCallError) as excinfo:
        await _batch()
    assert excinfo.value.reason == outcome
    assert excinfo.value.billed_cost_usd == pytest.approx(charged)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ((200, b"not json at all"), "it is charged $0.000100"),
        ((200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0.05")), "it is charged $0.000100"),
        ((200, _single_body(key=_RELEVANCY, choice="on_topic", cost="0")), "it is charged $0.000100"),
    ],
    ids=["a body that is not JSON", "states five cents", "usable, states $0"],
)
async def test_the_warning_names_the_amount_actually_charged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, reply: Any, said: str
) -> None:
    _patch_post(monkeypatch, reply)
    with caplog.at_level(logging.WARNING, logger=jev_client_module.__name__):
        try:
            await _single()
        except JevCallError:
            pass
    assert said in caplog.text


#: Words that stand for the person's own question, echoed back by Jev.
_ECHO = "I am Jane Example, my BRCA1 carrier status is positive"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        ("single", (200, _single_body(key=_RELEVANCY, choice=_ECHO))),
        ("single", (200, _single_body(key=_RELEVANCY, choice=_ECHO, cost="0.05"))),
        ("single", (200, _single_body(key=_RELEVANCY, choice=_ECHO, probabilities="null"))),
        ("single", (200, (_ECHO + " not json").encode())),
        ("single", (500, _ECHO.encode())),
        ("batch", (200, _batch_body(choice=_ECHO))),
        ("batch", (200, _batch_body(choice=_ECHO, cost="0.05"))),
        ("batch", (200, (_ECHO + " not json").encode())),
        ("batch", (429, _ECHO.encode())),
    ],
    ids=[
        "an option outside the set", "above the ceiling", "the wrong shape", "not JSON", "HTTP 500",
        "batch, an option outside the set", "batch, above the ceiling", "batch, not JSON", "batch, HTTP 429",
    ],
)
async def test_no_reply_text_reaches_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ask: str, reply: Any
) -> None:
    """A-GRS-05: Jev's state is the person's question, and a reply can echo
    it, as an option outside the set or as a body. The warning names a fixed
    category, the reply's length and the charge, and nothing the reply said.

    MUTATION PROOF: logging `detail` again (the line before this fix) turns
    the option-outside-the-set arms red."""
    _patch_post(monkeypatch, reply)
    _status, content = reply
    with caplog.at_level(logging.DEBUG), pytest.raises(JevCallError):
        await (_single() if ask == "single" else _batch())
    messages = [record.getMessage() for record in caplog.records]
    assert messages, "an unusable reply or an error status writes a warning"
    for message in messages:
        assert "Jane" not in message and "BRCA1" not in message, message
        assert f"reply length {len(content)} bytes" in message, message


@pytest.mark.parametrize(
    ("status", "expected"),
    [(500, "HTTP 500"), (429, "HTTP 429"), (402, "HTTP 402"), (401, "HTTP 401")],
)
@pytest.mark.asyncio
async def test_an_error_status_charge_writes_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int, expected: str
) -> None:
    """J-GRS-11: the module's docstring promises a warning whenever a reply
    is not charged a cost it states; an error status is charged the floor,
    so it writes one, by status and length, never the body.

    MUTATION PROOF: removing the warning in `_send` turns every arm red."""
    _patch_post(monkeypatch, (status, b"upstream said something"))
    with caplog.at_level(logging.WARNING, logger=jev_client_module.__name__), pytest.raises(JevCallError):
        await _single()
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, warnings
    assert expected in warnings[0]
    assert "it is charged $0.000100" in warnings[0]
    assert "upstream said" not in warnings[0]


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


# Each case: a label, the single-question reply shape, the batch reply, the charge.
_SITE_CASES: list[tuple[str, str, float]] = [
    ("usable, states $0", "zero", JEV_FLOOR_COST_USD),
    ("unusable, states a sensible cost", "unusable", 0.00002),
    ("states five cents", "five_cents", JEV_FLOOR_COST_USD),
    ("a body that is not JSON", "not_json", JEV_FLOOR_COST_USD),
    ("HTTP 500", "http_500", JEV_FLOOR_COST_USD),
    ("a transport failure", "transport", 0.0),
]


def _site_reply(shape: str, *, key: str, choice: str, batch: bool = False) -> Any:
    if shape == "not_json":
        return (200, b"not json at all")
    if shape == "http_500":
        return (500, b"oops")
    if shape == "transport":
        return httpx.ConnectError("refused")
    cost = {"zero": "0", "unusable": _SENSIBLE, "five_cents": "0.05"}[shape]
    pick = "maybe" if shape == "unusable" else choice
    if batch:
        return (200, _batch_body(cost=cost, choice="maybe" if shape == "unusable" else "no"))
    return (200, _single_body(key=key, choice=pick, cost=cost))


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape", "charged"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_decide_charges_by_the_owners_rule(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str, charged: float
) -> None:
    _patch_post(monkeypatch, _site_reply(shape, key=_RELEVANCY, choice="on_topic"))
    harness = Harness(trace_id="d")
    await decide(harness, "d", _RELEVANCY, "x", ["on_topic", "off_topic"], default="on_topic")
    assert harness.get_query_cost_usd("d") == pytest.approx(charged)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape", "charged"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_injection_pick_charges_by_the_owners_rule(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str, charged: float
) -> None:
    _patch_post(monkeypatch, _site_reply(shape, key="guardrail.injection", choice="not_injection"))
    harness = Harness(trace_id="i")
    await graph_module._jev_injection_pick(harness, "i", "What does BRCA1 do?")
    assert harness.get_query_cost_usd("i") == pytest.approx(charged)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape", "charged"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_sentence_check_charges_by_the_owners_rule(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str, charged: float
) -> None:
    _patch_post(monkeypatch, _site_reply(shape, key="", choice="", batch=True))
    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    # Card 99: the placeholder items carry no sentence, so no pair call; this
    # test is about the item call's charge.
    monkeypatch.setattr(sentence_check_module, "build_pair_calls", lambda sent: ([], frozenset()))
    harness = Harness(trace_id="s")
    try:
        await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    except (JevCallError, sentence_check_module.SentenceCheckUnreadable):
        pass
    assert harness.get_query_cost_usd("s") == pytest.approx(charged)


@pytest.mark.asyncio
async def test_a_drift_in_jevs_reply_shape_costs_a_question_cents_no_longer(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None
) -> None:
    """F-72-A03: every Jev reply unreadable, at the injection pick and a
    decision, the shape a format change would give. Develop charged a cent
    each; now each is the floor, so a question carries hundredths of a cent."""
    _patch_post(monkeypatch, (200, b"not json at all"))
    harness = Harness(trace_id="drift")
    await graph_module._jev_injection_pick(harness, "drift", "What does BRCA1 do?")
    await decide(harness, "drift", _RELEVANCY, "x", ["on_topic", "off_topic"], default="on_topic")
    assert harness.get_query_cost_usd("drift") == pytest.approx(2 * JEV_FLOOR_COST_USD)


def test_the_probe_bodies_are_what_they_claim() -> None:
    """The fixtures above really carry the shapes they name."""
    parsed = json.loads(_single_body(key="k", choice="c", cost=_HUGE))
    with pytest.raises(OverflowError):
        float(parsed["usage"]["cost"])
    assert "cost" not in json.loads(_single_body(key="k", choice="c", cost=None))["usage"]
    assert json.loads(_single_body(key="k", choice="c", probabilities="null"))["answers"]["k"]["probabilities"] is None
    with pytest.raises(ValueError):
        json.loads("")
