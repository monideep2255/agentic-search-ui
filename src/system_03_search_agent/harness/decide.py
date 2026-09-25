"""The one classifier seam: Jev, with the guard tier as a live-recorded
comparison and fallback (build phase 8.2, DECISIONS.md 2026-09-25, cards
8, 9, 10 and 13).

Depends on:
    - system_03_search_agent.harness.harness (Harness, HarnessCallError,
      Message)
    - system_03_search_agent.harness.cost_control (check_per_query_cap,
      QueryCapExceededError)
    - system_03_search_agent.harness.jev_client (call_jev, JevCallError,
      JevResult)
    - system_03_search_agent.harness.tiers (resolve_jev_model)
    - system_03_search_agent.contracts.events (DecisionRecord)

Reads:
    - Environment: CLASSIFIER_PROVIDER ("guard" is the code default; "jev"
      switches this decision seam on), OPENROUTER_API_KEY (Jev's own
      credential, the product's existing OpenRouter key), JEV_MODEL
      (resolved via `tiers.resolve_jev_model`, falling back to
      `typesafe/jev-1.13`).

Writes:
    - Nothing directly. Jev's own `usage.cost` is charged through
      `Harness.track_cost` inside this module, the same accumulator every
      other model call in the loop uses.

NOTHING IN THE AGENT LOOP CALLS `decide()` YET. This is build phase 8.2's
first wave: the seam is built, tested, and live-probed, but wiring it into
`core/graph.py`'s guardrail, think, or plan nodes is a later wave, after
the builders who own those files finish their own work this same night.

What this decides, and what it never decides: `decide()` answers exactly
one closed-option question at a time (`point`, e.g. "think.ask_back",
"guardrail.relevancy", "plan.literature", "plan.resource",
"think.recent_years"), never free text. Both Jev and the guard tier are
asked the SAME question over the SAME bounded `state`, concurrently, so
the comparison costs no extra wall-clock time. Per the product owner's
decision: Jev's answer is what a caller would actually use; the guard
tier's answer is recorded for a comparison table and used only as the
fallback when Jev cannot answer.

`ai-security-standards.md`'s prompt-injection defense applies directly
here: `state` is bounded (see `_STATE_MAX_CHARS`) and is the only free
text handed to either model. Neither model is ever asked to act on
retrieved content as an instruction; both are asked one narrow
multiple-choice question over a capped string.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import Harness, HarnessCallError, Message
from system_03_search_agent.harness.jev_client import JevCallError, JevResult, call_jev
from system_03_search_agent.harness.tiers import resolve_jev_model

# Bounded per ai-security-standards.md: only bounded state, never raw
# unbounded content, reaches an external model through this seam.
_STATE_MAX_CHARS = 4000

# The guard tier's own per-step timeout budget (harness.py's
# `_TIER_STEP_BUDGET_S["guard"]`, 15.0s), reused here rather than
# re-imported as a private constant: this decision call is guard-tier
# shaped work (a short classification), the same job `_TIER_STEP_BUDGET_S`
# already budgets for.
_GUARD_BUDGET_S = 15.0

# Jev's own per-call budget, per this ticket's interface: a 3-second
# timeout lives in jev_client.py itself; this is the cap on how long
# decide() waits for the concurrent guard/Jev pair before giving up on
# whichever side is slower, matching the guard tier's own step budget so
# neither side of the comparison is short-changed.
_DECIDE_BUDGET_S = _GUARD_BUDGET_S


#: A ceiling on the caller's description of a decision. The text is
#: code-authored and fixed per decision point, never user content, so this
#: is a bound on a programming mistake rather than on an attacker.
_DESCRIPTION_MAX_CHARS = 1000


def _check_description(
    point: str,
    options: Sequence[str],
    instructions: str | None,
    criteria: Mapping[str, str] | None,
) -> None:
    """Reject a description that does not fit the decision it describes.

    A criterion for an option that is not offered, or an offered option
    with no criterion, would tell the two models different things about
    the same choice, so both are programming errors, raised rather than
    sent.
    """
    if instructions is not None and len(instructions) > _DESCRIPTION_MAX_CHARS:
        raise ValueError(f"decide() for {point!r}: instructions exceed {_DESCRIPTION_MAX_CHARS} characters")
    if criteria is None:
        return
    if set(criteria) != set(options):
        raise ValueError(
            f"decide() for {point!r}: criteria must name exactly the offered options "
            f"{list(options)!r}, got {sorted(criteria)!r}"
        )
    for option, text in criteria.items():
        if len(text) > _DESCRIPTION_MAX_CHARS:
            raise ValueError(f"decide() for {point!r}: the criterion for {option!r} is too long")


def _build_guard_messages(
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> list[Message]:
    """One narrow classification prompt: no stable prefix (this is
    classification-shaped work, the same reason `_dispatch_tier_call`
    skips the prefix for the guardrail's own attack classifier and
    Think's classification call; see `core/graph.py`'s module docstring).

    The decision's own description, when the caller gives one, goes in the
    SYSTEM message and the person's text alone in the user message, so the
    instruction and the data it judges never share a turn. Without the
    description the guard saw only option names (builder J, F-J-03): its
    reply to "What is GERD?" for `think.ask_back` was unparseable.
    """
    options_line = ", ".join(repr(opt) for opt in options)
    content = (
        "Answer with exactly one of the offered options and nothing else. "
        f"Options: {options_line}"
    )
    if instructions:
        content += f"\n\nThe decision: {instructions}"
    if criteria:
        content += "\n\nWhen to choose each option:\n" + "\n".join(
            f"- {opt!r}: {criteria[opt]}" for opt in options
        )
    return [
        {"role": "system", "content": content},
        {"role": "user", "content": state},
    ]


def _parse_guard_choice(raw: str, options: Sequence[str]) -> str | None:
    """Deterministic, exact-match-or-substring parse. Never a fuzzy score
    (production-standards.md's AI answer grounding gate applies the same
    exact-match discipline to this closed-option decision).
    """
    text = raw.strip()
    for opt in options:
        if text == opt:
            return opt
    for opt in options:
        if opt in text:
            return opt
    return None


async def _run_guard_pick(
    harness: Harness,
    trace_id: str,
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> str | None:
    """The guard tier's own pick for the same closed-option question.

    Checks the per-query cost cap first, exactly like
    `core/graph.py`'s `_dispatch_tier_call` does for every other guard-tier
    call in the loop. Returns None (never raises) when the cap is
    exceeded, the call times out, or the call fails: this seam's `decide()`
    caller treats a None guard pick the same way it treats a fallback with
    no usable answer, by picking the first offered option rather than
    leaving the decision unresolved.
    """
    try:
        cost_control.check_per_query_cap(harness, trace_id, "guard")
    except QueryCapExceededError:
        return None
    messages = _build_guard_messages(state, options, instructions, criteria)
    try:
        response = await harness.enforce_timeout(
            "guardrail", harness.call_tier("guard", messages), _GUARD_BUDGET_S
        )
    except HarnessCallError:
        return None
    return _parse_guard_choice(response.content, options)


async def _run_jev_pick(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    model: str,
    api_key: str,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> JevResult:
    """Jev's pick, cap-checked first exactly like the guard call above.

    Raises JevCallError (from `jev_client.call_jev`) or
    `cost_control.QueryCapExceededError` on any failure; `decide()` is the
    only caller and it catches both.
    """
    # Jev has no tier of its own to draw a token-profile estimate from
    # (estimate_call_cost_usd is keyed strictly to {"guard", "plan",
    # "synth"}). Reusing the guard tier's conservative estimate is safe in
    # the direction that matters: Jev's measured live cost
    # ($0.0000148-$0.0000197 per call, see jev_client.py's module
    # docstring) is far below the guard tier's own token-profile estimate,
    # so this check never lets a call through that a Jev-specific estimate
    # would have refused.
    cost_control.check_per_query_cap(harness, trace_id, "guard")
    result = await call_jev(
        model=model,
        question_key=point,
        state=state,
        options=options,
        api_key=api_key,
        instructions=instructions,
        criteria=criteria,
    )
    # Charged under the "guard" tier bucket for the same reason the cap
    # check above reuses it: `Harness.track_cost`'s accumulator is not
    # broken down per tier (its own docstring says so), it only sums onto
    # `trace_id`'s running total, and Jev has no tier slot of its own.
    harness.track_cost(trace_id, "guard", result.cost_usd)  # type: ignore[arg-type]
    return result


async def decide(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    *,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> DecisionRecord:
    """Decide one closed-option question, `point`, over the bounded `state`.

    `instructions` (one line saying what is being decided) and `criteria`
    (one line per option saying when to choose it) are the caller's fixed,
    code-authored description of the decision. Both models receive the
    same description: the guard tier in its system message, Jev in the
    endpoint's own `instructions` and `criteria` fields. `state` stays the
    person's bounded text only. Every wired decision point passes both;
    without them the models see only option names, which measured wrong on
    three of the five decision shapes (builder J, F-J-03).

    With `CLASSIFIER_PROVIDER` unset or anything other than `"jev"` (the
    code default, `"guard"`): Jev is never called. The guard tier decides
    alone and its pick is used. This is what keeps production untouched
    until the product owner flips the switch.

    With `CLASSIFIER_PROVIDER=jev`: Jev and the guard tier are dispatched
    CONCURRENTLY over the same `state` and `options` (via `asyncio.gather`),
    so the comparison adds no wall-clock time to whichever call would have
    run anyway. Jev's choice is used when it answers in time with one of
    the offered `options`; otherwise the guard tier's choice is used and
    `fallback_reason` names why (Jev's own `JevCallError.reason`, or
    `"guard_only"` when Jev was never dispatched, or `"no_usable_pick"`
    when neither side produced a valid answer, in which case `chosen`
    falls back to `options[0]`).

    Raises:
        ValueError: if `options` is empty (there is nothing to decide
            between), or the description does not fit the options (see
            `_check_description`).
    """
    if not options:
        raise ValueError(f"decide() for {point!r} was given an empty options list")
    _check_description(point, options, instructions, criteria)

    bounded_state = state[:_STATE_MAX_CHARS]
    provider = os.environ.get("CLASSIFIER_PROVIDER", "guard").strip().lower()

    if provider != "jev":
        guard_choice = await _run_guard_pick(
            harness, trace_id, bounded_state, options, instructions, criteria
        )
        chosen = guard_choice if guard_choice is not None else options[0]
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=chosen,
            decided_by="guard",
            guard_choice=guard_choice,
            fallback_reason=None if guard_choice is not None else "no_usable_pick",
        )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = resolve_jev_model()

    guard_coro = _run_guard_pick(harness, trace_id, bounded_state, options, instructions, criteria)
    jev_coro = _run_jev_pick(
        harness, trace_id, point, bounded_state, options, model, api_key, instructions, criteria
    )

    try:
        guard_outcome, jev_outcome = await asyncio.wait_for(
            asyncio.gather(guard_coro, jev_coro, return_exceptions=True),
            timeout=_DECIDE_BUDGET_S + 1.0,
        )
    except TimeoutError:
        # Both `_run_guard_pick` (via `harness.enforce_timeout`, 15s) and
        # `call_jev` (via its own 3s client timeout) already bound
        # themselves well inside this outer budget, so reaching this
        # branch means something outside either call's own timeout hung
        # (an event-loop stall, not a call failure). Fail closed to the
        # first offered option rather than propagate: a decision-seam
        # hang must never take down the caller's own step.
        guard_outcome = None
        jev_outcome = JevCallError(
            f"decide() for {point!r} exceeded its own outer budget of "
            f"{_DECIDE_BUDGET_S + 1.0}s; fall back to the guard tier's pick for this decision",
            reason="timeout",
        )

    guard_choice: str | None = guard_outcome if not isinstance(guard_outcome, BaseException) else None

    jev_result: JevResult | None
    fallback_reason: str | None
    if isinstance(jev_outcome, JevCallError):
        jev_result = None
        fallback_reason = jev_outcome.reason
    elif isinstance(jev_outcome, QueryCapExceededError):
        jev_result = None
        fallback_reason = "cost_cap"
    elif isinstance(jev_outcome, BaseException):
        jev_result = None
        fallback_reason = "unexpected_error"
    else:
        jev_result = jev_outcome
        fallback_reason = None

    if jev_result is not None:
        chosen = jev_result.choice
        decided_by: str = "jev"
    else:
        chosen = guard_choice if guard_choice is not None else options[0]
        decided_by = "guard"
        if fallback_reason is None:
            fallback_reason = "no_usable_pick" if guard_choice is None else "jev_unavailable"

    agreed: bool | None = None
    if jev_result is not None and guard_choice is not None:
        agreed = jev_result.choice == guard_choice

    return DecisionRecord(
        name=point,
        options=list(options),
        chosen=chosen,
        decided_by=decided_by,  # type: ignore[arg-type]
        jev_choice=jev_result.choice if jev_result is not None else None,
        jev_confidence=jev_result.confidence if jev_result is not None else None,
        guard_choice=guard_choice,
        agreed=agreed,
        fallback_reason=fallback_reason,
        jev_latency_ms=jev_result.latency_ms if jev_result is not None else None,
    )
