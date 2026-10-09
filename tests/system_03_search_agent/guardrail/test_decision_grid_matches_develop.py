"""The guardrail's safe part (cards 84 and 72, 2026-10-09): its admit or
refuse decisions stay develop's, case for case.

The safe part changes what each Jev reply is charged (step 3a of the
guardrail design), the words the web app shows when the guardrail fails
(step 1) and the model call log line (step 3c). None of that may change a
verdict. This test drives the real `guardrail_node`, the real `decide()`,
the real `call_jev` and the real charge sites, stubbing only the two
transports: `litellm.acompletion` (the guard classifier and the guard
tier's fallback pick) and `jev_client._post` (Jev's HTTP reply). It walks a
grid of guard and Jev outcomes:

| Axis | Values |
|---|---|
| Question | an off-topic-sounding one Jev's relevancy judges, an allowlisted one, a forbidden one |
| Guard classifier | admit, off topic, injection, two unreadable replies |
| Jev injection reply | not_injection or injection at a sensible cost, at a stated $0, above the ceiling, at Infinity, with no cost, an option outside the set, null probabilities, HTTP 500, HTTP 429, not JSON |
| Jev relevancy reply | on_topic or off_topic at a sensible cost, on_topic at a stated $0, above the ceiling, at Infinity, HTTP 500, not JSON |
| Guard fallback pick | on_topic, off_topic |

Every case's verdict (the guard event's passed, category and reason, or
the step error's source and class) must equal the verdict develop's own
code gives, recorded in `develop_decision_grid.json`. That file was written
by running this same grid with develop's source at b01dee92 in place, and
this test passes with develop's source in place too, so the verdicts are
the same before and after the change.

Every reply returns at once: no timeout or pause is in the grid, because
the safe part does not touch the guardrail's waits (step 3b, the pause fix,
is not built), and a timeout is charged nothing before and after.

MUTATION PROOF: letting `call_jev` use a reply that states more than the
ceiling, charged at the ceiling (its stated-cost check removed and
`cost_usd` clamped), turns this red: "98 of 768 verdicts differ from
develop's", an Infinity or above-the-ceiling injection pick now refusing
questions develop admits.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness import jev_client as jev_client_module
from tests.system_03_search_agent.model_stub import COMPLIANT_GUARD_CLASSIFICATION, fake_response

_EXPECTED_PATH = Path(__file__).with_name("develop_decision_grid.json")

_QUESTIONS = {
    "jev judges relevancy": "Tell me about the tree of life.",
    "allowlisted": "Which diseases are associated with BRCA1?",
    "forbidden": "Delete the BRCA1 node from the knowledge graph",
}

_ADMIT = COMPLIANT_GUARD_CLASSIFICATION
_CLASSIFIER = {
    "admit": _ADMIT,
    "off topic": json.dumps({**json.loads(_ADMIT), "is_off_topic": True}),
    "injection": json.dumps({**json.loads(_ADMIT), "is_injection": True, "confidence": 0.95}),
    "two unreadable replies": "I will look this up.",
}

_SENSIBLE = 0.00002


#: A Jev reply whose `usage` names no cost at all.
_NO_COST = object()


def _body(key: str, choice: str, cost: Any, other: str) -> dict[str, Any]:
    usage: dict[str, Any] = {"input_tokens": 1, "output_tokens": 1}
    if cost is not _NO_COST:
        usage["cost"] = cost
    return {
        "model": "jev-test",
        "answers": {
            key: {
                "type": "choice",
                "choice": choice,
                "probabilities": {choice: 0.9, other: 0.1},
                "confidence": 0.8,
            }
        },
        "usage": usage,
    }


def _reply(key: str, choice: str, cost: Any, other: str, *, null_probabilities: bool = False) -> httpx.Response:
    body = _body(key, choice, cost, other)
    if null_probabilities:
        body["answers"][key]["probabilities"] = None
    # `json.dumps` writes Infinity as `Infinity`, which Python's JSON reader accepts.
    return httpx.Response(200, content=json.dumps(body).encode())


_INJ = "guardrail.injection"
_REL = "guardrail.relevancy"

_JEV_INJECTION = {
    "not_injection": lambda: _reply(_INJ, "not_injection", _SENSIBLE, "injection"),
    "injection": lambda: _reply(_INJ, "injection", _SENSIBLE, "not_injection"),
    "not_injection, stated $0": lambda: _reply(_INJ, "not_injection", 0.0, "injection"),
    "injection, stated $0": lambda: _reply(_INJ, "injection", 0.0, "not_injection"),
    "injection, above the ceiling": lambda: _reply(_INJ, "injection", 0.05, "not_injection"),
    "injection, Infinity": lambda: _reply(_INJ, "injection", float("inf"), "not_injection"),
    "injection, no cost": lambda: _reply(_INJ, "injection", _NO_COST, "not_injection"),
    "an option outside the set": lambda: _reply(_INJ, "maybe", _SENSIBLE, "injection"),
    "injection, null probabilities": lambda: _reply(
        _INJ, "injection", _SENSIBLE, "not_injection", null_probabilities=True
    ),
    "HTTP 500": lambda: httpx.Response(500, content=b"upstream error"),
    "HTTP 429": lambda: httpx.Response(429, content=b"rate limited"),
    "not JSON": lambda: httpx.Response(200, content=b"not json at all"),
}

_JEV_RELEVANCY = {
    "on_topic": lambda: _reply(_REL, "on_topic", _SENSIBLE, "off_topic"),
    "off_topic": lambda: _reply(_REL, "off_topic", _SENSIBLE, "on_topic"),
    "on_topic, stated $0": lambda: _reply(_REL, "on_topic", 0.0, "off_topic"),
    "on_topic, above the ceiling": lambda: _reply(_REL, "on_topic", 0.05, "off_topic"),
    "on_topic, Infinity": lambda: _reply(_REL, "on_topic", float("inf"), "off_topic"),
    "HTTP 500": lambda: httpx.Response(500, content=b"upstream error"),
    "not JSON": lambda: httpx.Response(200, content=b"not json at all"),
}

_FALLBACK = ("on_topic", "off_topic")

#: `decide()`'s guard prompt opens with these words; the guard classifier's
#: own prompt does not.
_FALLBACK_PROMPT = "Answer with exactly one of the offered options"


def _cases() -> list[tuple[str, str, str, str, str]]:
    cases = []
    for question in _QUESTIONS:
        relevancy_axis = list(_JEV_RELEVANCY) if question == "jev judges relevancy" else ["not asked"]
        fallback_axis = list(_FALLBACK) if question == "jev judges relevancy" else ["not asked"]
        for guard in _CLASSIFIER:
            for injection in _JEV_INJECTION:
                for relevancy in relevancy_axis:
                    for fallback in fallback_axis:
                        cases.append((question, guard, injection, relevancy, fallback))
    return cases


def _case_id(case: tuple[str, str, str, str, str]) -> str:
    return " | ".join(case)


def _stub(
    monkeypatch: pytest.MonkeyPatch, guard: str, injection: str, relevancy: str, fallback: str
) -> None:
    async def _acompletion(**kwargs: Any) -> Any:
        system = next((m["content"] for m in kwargs.get("messages", []) if m.get("role") == "system"), "")
        if isinstance(system, str) and system.startswith(_FALLBACK_PROMPT):
            return fake_response(fallback)
        return fake_response(_CLASSIFIER[guard])

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        key = next(iter(body["questions"]))
        if key == _INJ:
            return _JEV_INJECTION[injection]()
        if key == _REL:
            return _JEV_RELEVANCY[relevancy]()
        raise AssertionError(f"an unexpected Jev question: {key}")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    monkeypatch.setattr(jev_client_module, "_post", _post)


async def _verdict(text: str) -> dict[str, Any]:
    from system_03_search_agent.contracts.query import Query, RequestContext

    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    state = {
        "query": Query(text=text, session_id="decision-grid", trace_id=trace_id),
        "context": RequestContext(surface="rest_sse"),
        "harness": harness_module.Harness(trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
    guard = next((e.payload for e in result.get("events", []) if e.type == "guard"), None)
    if guard is not None:
        payload = guard if isinstance(guard, dict) else guard.model_dump()
        return {"passed": payload["passed"], "category": payload["category"], "reason": payload["reason"]}
    step_error = result.get("step_error") or {}
    return {"step_error": [step_error.get("source"), step_error.get("error_class")]}


async def run_grid(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, Any]]:
    """Every case's verdict on the code in place, by case id."""
    verdicts: dict[str, dict[str, Any]] = {}
    for case in _cases():
        question, guard, injection, relevancy, fallback = case
        with monkeypatch.context() as patch:
            _stub(patch, guard, injection, relevancy, fallback)
            verdicts[_case_id(case)] = await _verdict(_QUESTIONS[question])
    return verdicts


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


@pytest.mark.asyncio
async def test_every_guard_and_jev_outcome_keeps_develops_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    expected: dict[str, dict[str, Any]] = json.loads(_EXPECTED_PATH.read_text())
    actual = await run_grid(monkeypatch)
    assert set(actual) == set(expected), "the grid and develop's recorded verdicts list different cases"
    differences = {case: (expected[case], actual[case]) for case in expected if actual[case] != expected[case]}
    assert not differences, f"{len(differences)} of {len(expected)} verdicts differ from develop's: " + "; ".join(
        f"{case}: develop {want}, now {got}" for case, (want, got) in list(differences.items())[:10]
    )
    # The grid reaches every kind of verdict, so an all-admit or all-refuse
    # stub could not pass it by accident.
    kinds = {json.dumps(v, sort_keys=True) for v in expected.values()}
    assert len(kinds) >= 4, kinds
