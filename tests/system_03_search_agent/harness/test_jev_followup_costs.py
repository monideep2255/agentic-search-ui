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

The rule the charges follow, since R-10's fix round (the product owner's
decision of 2026-09-29; F-72-J02, A03, J09), is `jev_client.jev_charge_usd`:
a reply that came back is never charged $0. A usable reply is charged the
cost it states when that is above zero and at most `MAX_JEV_COST_USD`;
every other reply, whatever its body's shape and whatever cost it states,
is charged the small `JEV_FLOOR_COST_USD`, and the one warning
`jev_client` writes for it names that amount. R-07 charged a malformed
reply the cost it stated; that left a reply stating $0 charged $0 (FJ02),
and shapes the parse did not name (`"probabilities": null`, a list or a
string there, a body nested too deep for the JSON parser) escaped
uncharged at every site while the log said the ceiling was charged (FJ01,
FA01, FJ03). R-10 charged them the one-cent ceiling, about 500 times
develop when the endpoint's shape drifts (A03); the fix round charges the
floor. And no Jev call is let through that could take the question past
its per-query cap (J09).
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
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import (
    JEV_FLOOR_COST_USD,
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
def _probabilities_as(raw: str, *, key: str = "guardrail.relevancy", choice: str = "on_topic") -> bytes:
    """A reply whose `probabilities` is `raw` JSON text, stating a usable
    $0.00002: F-8.6-FJ01's shapes."""
    body = _single_body(key=key, choice=choice, cost="0.00002")
    return body.replace(f'"probabilities": {{"{choice}": 0.8}}', f'"probabilities": {raw}').encode()


#: A body nested too deep for the JSON parser: `response.json()` raises
#: `RecursionError`, not `ValueError` (F-8.6-FA01).
_DEEP = b"[" * 100_000 + b"]" * 100_000

_SINGLE_CASES = [
    _single_body(key="guardrail.relevancy", choice="on_topic", cost=_HUGE).encode(),
    _single_body(key="guardrail.relevancy", choice="on_topic", confidence=_HUGE).encode(),
    _single_body(key="guardrail.relevancy", choice="on_topic", prob=_HUGE).encode(),
    _single_body(key="guardrail.relevancy", choice="on_topic", confidence='"abc"').encode(),
    _single_body(key="guardrail.relevancy", choice="on_topic", confidence="7", cost="0").encode(),
    _probabilities_as("null"),
    _probabilities_as("[0.8, 0.2]"),
    _probabilities_as('"on_topic"'),
    _DEEP,
    b"not json at all",
    b"",
    b"\xff\xfe\xfa",
]
_SINGLE_IDS = [
    "cost too large for a float",
    "confidence too large for a float",
    "probability too large for a float",
    "confidence a string, cost stated",
    "confidence out of range, cost stated as 0",
    "probabilities null",
    "probabilities a list",
    "probabilities a string",
    "a body nested too deep",
    "a body that is not JSON",
    "an empty body",
    "a body that is not text",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", _SINGLE_CASES, ids=_SINGLE_IDS)
async def test_call_jev_charges_an_unreadable_reply_the_floor_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, content: bytes
) -> None:
    """MUTATION PROOF: narrowing `call_jev`'s parse arm back to a list of
    error types turns "probabilities null" red (it escapes as an
    `AttributeError`), and `_json_payload`'s back to `ValueError` turns "a
    body nested too deep" red; see the builder's report."""
    _patch_reply(monkeypatch, content)
    with (
        caplog.at_level(logging.WARNING, logger=jev_client_module.__name__),
        pytest.raises(JevCallError) as excinfo,
    ):
        await _single()
    assert excinfo.value.reason == "malformed_reply"
    assert excinfo.value.billed_cost_usd == JEV_FLOOR_COST_USD
    assert "fall back to the guard tier" in str(excinfo.value)
    assert [r.getMessage().endswith("it is charged $0.0001") for r in caplog.records] == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "billed"),
    [
        (_batch_body(cost=_HUGE).encode(), JEV_FLOOR_COST_USD),
        (_batch_body(confidence=_HUGE).encode(), JEV_FLOOR_COST_USD),
        (_batch_body(confidence='"abc"').encode(), JEV_FLOOR_COST_USD),
        (_batch_body().replace('"probabilities": {"no": 0.8}}, "item_2"', '"probabilities": null}, "item_2"').encode(),
         JEV_FLOOR_COST_USD),
        (_DEEP, JEV_FLOOR_COST_USD),
        (b"not json at all", JEV_FLOOR_COST_USD),
        (b"", JEV_FLOOR_COST_USD),
    ],
    ids=[
        "cost too large for a float",
        "confidence too large for a float",
        "confidence a string, cost stated",
        "probabilities null",
        "a body nested too deep",
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
        (b"not json at all", "could not be read as JSON (JSONDecodeError); it is charged $0.0001"),
        (
            _single_body(key="guardrail.relevancy", choice="on_topic", cost=_HUGE).encode(),
            "did not match the confirmed response shape (OverflowError); it is charged $0.0001",
        ),
        (_probabilities_as("null"), "(AttributeError); it is charged $0.0001"),
        (_DEEP, "could not be read as JSON (RecursionError); it is charged $0.0001"),
    ],
    ids=["a body that is not JSON", "cost too large for a float", "probabilities null", "a body nested too deep"],
)
async def test_the_warning_names_the_amount_actually_charged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, content: bytes, said: str
) -> None:
    """RA01: the warning said "charged the $0.01 ceiling" while $0.0 was
    charged. The warning and the error's charge now agree, on the floor."""
    assert f"${JEV_FLOOR_COST_USD:.4f}" == "$0.0001"
    _patch_reply(monkeypatch, content)
    with (
        caplog.at_level(logging.WARNING, logger=jev_client_module.__name__),
        pytest.raises(JevCallError) as excinfo,
    ):
        await _single()
    assert said in caplog.text
    assert excinfo.value.billed_cost_usd == pytest.approx(JEV_FLOOR_COST_USD)


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
    ("probabilities null, a usable cost stated", "probabilities_null"),
    ("probabilities a list, a usable cost stated", "probabilities_list"),
    ("probabilities a string, a usable cost stated", "probabilities_string"),
    ("a body nested too deep", "deep"),
    ("an option outside the set, a usable cost stated", "invalid_option"),
]


def _site_content(shape: str, *, key: str, choice: str, batch: bool = False) -> bytes:
    if shape == "not_json":
        return b"not json at all"
    if shape == "empty":
        return b""
    if shape == "deep":
        return _DEEP
    if shape.startswith("probabilities_"):
        raw = {"probabilities_null": "null", "probabilities_list": "[0.8]", "probabilities_string": '"x"'}[shape]
        if batch:
            return _batch_body().replace('"probabilities": {"no": 0.8}}, "item_2"', f'"probabilities": {raw}}}, "item_2"').encode()
        return _probabilities_as(raw, key=key, choice=choice)
    if shape == "invalid_option":
        if batch:
            return _batch_body().replace('"choice": "no"', '"choice": "maybe"', 1).encode()
        return _single_body(key=key, choice="maybe", cost="0.00002").encode()
    if batch:
        return _batch_body(cost=_HUGE).encode()
    return _single_body(key=key, choice=choice, cost=_HUGE).encode()


def _reason(shape: str) -> str:
    return "invalid_option" if shape == "invalid_option" else "malformed_reply"


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_decide_charges_the_floor(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="guardrail.relevancy", choice="on_topic"))
    harness = Harness(trace_id="d")
    record = await decide(harness, "d", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.fallback_reason is not None and record.fallback_reason.endswith(_reason(shape))
    assert harness.get_query_cost_usd("d") == pytest.approx(JEV_FLOOR_COST_USD)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_injection_pick_charges_the_floor(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="guardrail.injection", choice="not_injection"))
    harness = Harness(trace_id="i")
    result = await graph_module._jev_injection_pick(harness, "i", "What does BRCA1 do?")
    assert result == _reason(shape)
    assert harness.get_query_cost_usd("i") == pytest.approx(JEV_FLOOR_COST_USD)


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "shape"), _SITE_CASES, ids=[c[0] for c in _SITE_CASES])
async def test_the_sentence_check_charges_the_floor(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, label: str, shape: str
) -> None:
    _patch_reply(monkeypatch, _site_content(shape, key="", choice="", batch=True))
    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    harness = Harness(trace_id="s")
    with pytest.raises(JevCallError) as excinfo:
        await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    assert excinfo.value.reason == _reason(shape)
    assert harness.get_query_cost_usd("s") == pytest.approx(JEV_FLOOR_COST_USD)


def _patch_status(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(status, content=b"provider error")

    monkeypatch.setattr(jev_client_module, "_post", _post)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 429, 402])
async def test_a_reply_with_another_status_is_charged_the_floor_at_every_site(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, status: int
) -> None:
    """Card 84, F-72-V03: a 500, a 429 or a 402 is a reply that reached the
    provider, so it is charged the floor, never $0, at `decide`, at the
    injection pick and at the sentence check (the product owner's decision
    of 2026-09-29).

    MUTATION PROOF: `_send` raising its non-200 error with no charge again
    turns every arm red on the cost."""
    _patch_status(monkeypatch, status)
    harness = Harness(trace_id="d")
    record = await decide(harness, "d", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.fallback_reason is not None and record.fallback_reason.endswith("http_error")
    assert harness.get_query_cost_usd("d") == pytest.approx(JEV_FLOOR_COST_USD)

    harness = Harness(trace_id="i")
    assert await graph_module._jev_injection_pick(harness, "i", "What does BRCA1 do?") == "http_error"
    assert harness.get_query_cost_usd("i") == pytest.approx(JEV_FLOOR_COST_USD)

    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    harness = Harness(trace_id="s")
    with pytest.raises(JevCallError) as excinfo:
        await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    assert excinfo.value.reason == "http_error"
    assert harness.get_query_cost_usd("s") == pytest.approx(JEV_FLOOR_COST_USD)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "transport"])
async def test_a_call_no_reply_came_back_from_is_charged_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, failure: str
) -> None:
    """The floor is for replies. A call that timed out, or never reached the
    provider, carries no charge, as the decision's words say."""

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        if failure == "transport":
            raise httpx.ConnectError("refused (stub)")
        await asyncio.sleep(60)
        raise AssertionError("never reached")

    monkeypatch.setattr(jev_client_module, "_post", _post)
    monkeypatch.setattr(jev_client_module, "JEV_STALL_ALLOWANCE_S", 0.0)
    with pytest.raises(JevCallError) as excinfo:
        await call_jev_batch(
            model="m",
            state="x",
            questions={"item_1": JevChoiceQuestion(options=("yes", "no"), instructions="i", criteria={"yes": "y", "no": "n"})},
            api_key="k",
            timeout_s=0.05,
        )
    assert excinfo.value.reason == ("timeout" if failure == "timeout" else "http_error")
    assert excinfo.value.billed_cost_usd == 0.0


def test_the_probe_bodies_are_what_they_claim() -> None:
    """The fixtures above really carry the shapes they name: the huge
    number parses from JSON and cannot become a float."""
    parsed = json.loads(_single_body(key="k", choice="c", cost=_HUGE))
    with pytest.raises(OverflowError):
        float(parsed["usage"]["cost"])
    with pytest.raises(ValueError):
        json.loads("")
    with pytest.raises(RecursionError):
        json.loads(_DEEP)
    for shape in ("probabilities_null", "probabilities_list", "probabilities_string"):
        single = json.loads(_site_content(shape, key="k", choice="c"))
        batch = json.loads(_site_content(shape, key="", choice="", batch=True))
        assert not isinstance(single["answers"]["k"]["probabilities"], dict)
        assert not isinstance(batch["answers"]["item_1"]["probabilities"], dict)
        assert single["usage"]["cost"] == 0.00002


# ---------------------------------------------------------------------------
# R-10's fix round: a USABLE reply is never charged $0 either (F-72-J02), and
# no Jev charge takes a question past its per-query cap (F-72-J09).
# ---------------------------------------------------------------------------

_USABLE_CASES = [
    ("0", JEV_FLOOR_COST_USD),
    ("0.0", JEV_FLOOR_COST_USD),
    ("0.00002", 0.00002),
    ("0.004", 0.004),
    ("0.01", MAX_JEV_COST_USD),
    ("1e-12", 1e-12),
]
_USABLE_IDS = [
    "stated $0: the floor",
    "stated $0.0: the floor",
    "Jev's measured price: as stated",
    "a larger sensible amount: as stated",
    "exactly the ceiling: as stated",
    "a tiny amount above zero: as stated",
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("stated", "charged"), _USABLE_CASES, ids=_USABLE_IDS)
async def test_a_usable_reply_is_charged_its_sensible_cost_or_the_floor_at_every_site(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, stated: str, charged: float
) -> None:
    """F-72-J02: a usable reply stating $0 was charged $0 at `decide`, the
    injection pick and the sentence check, so the cap saw nothing for it.

    MUTATION PROOF: `jev_charge_usd` returning a stated $0 as $0 turns the
    two "the floor" arms red."""
    _patch_reply(monkeypatch, _single_body(key="guardrail.relevancy", choice="on_topic", cost=stated).encode())
    harness = Harness(trace_id="d")
    record = await decide(harness, "d", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.decided_by == "jev" and record.chosen == "on_topic"
    assert harness.get_query_cost_usd("d") == pytest.approx(charged)

    _patch_reply(monkeypatch, _single_body(key="guardrail.injection", choice="not_injection", cost=stated).encode())
    harness = Harness(trace_id="i")
    result = await graph_module._jev_injection_pick(harness, "i", "What does BRCA1 do?")
    assert not isinstance(result, str) and result.choice == "not_injection"
    assert harness.get_query_cost_usd("i") == pytest.approx(charged)

    _patch_reply(monkeypatch, _batch_body(cost=stated).encode())
    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    monkeypatch.setattr(sentence_check_module, "approved_keys_from_jev", lambda result, sent: frozenset())
    harness = Harness(trace_id="s")
    await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    assert harness.get_query_cost_usd("s") == pytest.approx(charged)


@pytest.mark.asyncio
async def test_a_floor_charge_is_logged_by_amount(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """R-10 line 3: the log names the amount charged."""
    _patch_reply(monkeypatch, _single_body(key="guardrail.relevancy", choice="on_topic", cost="0").encode())
    with caplog.at_level(logging.WARNING, logger=jev_client_module.__name__):
        await _single()
    assert "stated a cost of $0.000000, not a sensible amount; it is charged $0.0001" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("stated", ["0.009", "not json"], ids=["a usable reply near the ceiling", "an unusable reply"])
async def test_no_jev_charge_takes_a_question_past_its_cap(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, stated: str
) -> None:
    """F-72-J09: at $0.0965 of a $0.10 cap, a Jev call passed the guard
    tier's $0.003 pre-flight and an unusable reply then charged a cent,
    ending at $0.1065. The pre-flight now counts the most one Jev call can
    be charged, so no call is made and nothing passes the cap, at `decide`
    and at the injection pick.

    MUTATION PROOF: `check_jev_per_query_cap` checking the guard estimate
    only turns both arms red on the request count, and the first on the
    total."""
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    posts: list[str] = []

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        key = next(iter(body["questions"]))
        posts.append(key)
        choice = body["questions"][key]["options"][0]
        content = b"not json" if stated == "not json" else _single_body(key=key, choice=choice, cost=stated).encode()
        return httpx.Response(200, content=content)

    monkeypatch.setattr(jev_client_module, "_post", _post)
    harness = Harness(trace_id="c")
    harness.track_cost("c", "guard", 0.0965)
    record = await decide(harness, "c", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
    assert record.fallback_reason == "cost_cap"
    assert await graph_module._jev_injection_pick(harness, "c", "What does BRCA1 do?") == "cost_cap"
    assert posts == []
    assert harness.get_query_cost_usd("c") <= 0.10


def _slow_usable_post(posts: list[str], stated: str, *, delay_s: float = 0.05) -> Any:
    """A `_post` stand-in: a usable reply stating `stated`, `delay_s` late,
    batch or single by the body's shape, each request noted on `posts`."""

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        await asyncio.sleep(delay_s)
        keys = list(body["questions"])
        posts.append(",".join(keys))
        if keys and keys[0].startswith("item_"):
            return httpx.Response(200, content=_batch_body(cost=stated).encode())
        key = keys[0]
        choice = body["questions"][key]["options"][0]
        return httpx.Response(200, content=_single_body(key=key, choice=choice, cost=stated).encode())

    return _post


@pytest.mark.asyncio
@pytest.mark.parametrize("running", [0.085, 0.089])
async def test_two_jev_calls_checked_at_once_never_pass_the_cap(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None, running: float
) -> None:
    """Card 84, F-72-V02: the guardrail starts its Jev relevancy decision and
    its Jev injection pick at the same moment. Both pre-flights ran before
    either was charged, each saw room for one call, and at $0.089 of a $0.10
    cap two usable replies stating $0.009 ended at $0.107. Now the first
    call holds its most possible charge until it lands, the second sees
    that and is refused, and the question stays inside its cap.

    MUTATION PROOF: `check_jev_per_query_cap` ignoring what is held turns
    both arms red on the total."""
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    posts: list[str] = []
    monkeypatch.setattr(jev_client_module, "_post", _slow_usable_post(posts, "0.009"))
    harness = Harness(trace_id="v")
    harness.track_cost("v", "guard", running)
    record, injection = await asyncio.gather(
        decide(harness, "v", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic"),
        graph_module._jev_injection_pick(harness, "v", "Tell me about the tree of life."),
    )
    assert harness.get_query_cost_usd("v") <= 0.10
    assert len(posts) == 1
    assert "cost_cap" in (record.fallback_reason, injection)


@pytest.mark.asyncio
async def test_the_hold_is_let_go_once_the_charge_lands(monkeypatch: pytest.MonkeyPatch, jev_mode: None) -> None:
    """A Jev call's hold ends with it, whether it answered, failed or was
    stopped, so calls one after another are each checked against what was
    really charged."""
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    posts: list[str] = []
    monkeypatch.setattr(jev_client_module, "_post", _slow_usable_post(posts, "0.009"))
    harness = Harness(trace_id="h")
    for _ in range(3):
        record = await decide(harness, "h", "guardrail.relevancy", "x", ["on_topic", "off_topic"], default="on_topic")
        assert record.decided_by == "jev"
    assert len(posts) == 3
    assert decide_module._reserved_usd(harness, "h") == 0.0
    task = asyncio.ensure_future(graph_module._jev_injection_pick(harness, "h", "What does BRCA1 do?"))
    await asyncio.sleep(0.01)
    assert decide_module._reserved_usd(harness, "h") == pytest.approx(MAX_JEV_COST_USD)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert decide_module._reserved_usd(harness, "h") == 0.0


@pytest.mark.asyncio
async def test_the_sentence_check_checks_the_cost_it_can_be_charged(
    monkeypatch: pytest.MonkeyPatch, jev_mode: None
) -> None:
    """Card 84, F-72-J09: the sentence check's pre-flight counted only the
    guard tier's $0.003 estimate, so from $0.0965 of a $0.10 cap a usable
    batch reply stating $0.009 ended at $0.1055. It now checks the most a
    Jev call can be charged: no call is made, nothing is approved, and the
    question stays inside its cap.

    MUTATION PROOF: `_ask_jev` checking the guard tier's estimate again
    turns this red on the request count and the total."""
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    posts: list[str] = []
    monkeypatch.setattr(jev_client_module, "_post", _slow_usable_post(posts, "0.009"))
    monkeypatch.setattr(sentence_check_module, "build_jev_state", lambda candidates: ("STATE", [object(), object()]))
    harness = Harness(trace_id="s")
    harness.track_cost("s", "guard", 0.0965)
    with pytest.raises(QueryCapExceededError):
        await sentence_check_module._ask_jev([], harness=harness, trace_id="s", timeout_s=3.0)
    assert posts == []
    assert harness.get_query_cost_usd("s") == pytest.approx(0.0965)
