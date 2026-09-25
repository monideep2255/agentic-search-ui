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

WIRED INTO THE LOOP in build phase 8.2's second wave (builder J): every
caller lives in `core/graph.py`, whose "classifier seam, wired" section
holds each decision point's fixed description and the list of points.

What this decides, and what it never decides: `decide()` answers exactly
one closed-option question at a time (`point`, e.g. "think.ask_back",
"guardrail.relevancy", "plan.literature", "plan.resource",
"think.recent_years"), never free text. Both Jev and the guard tier are
asked the SAME question over the SAME bounded `state`, concurrently. Per
the product owner's decision: Jev's answer is what a caller would actually
use; the guard tier's answer is recorded for a comparison table and used
only as the fallback when Jev cannot answer. Since the fix round, once Jev
has answered the comparison waits at most `GUARD_COMPARISON_GRACE_S` for
the guard, so the person never waits on a pick that is only recorded.

`ai-security-standards.md`'s prompt-injection defense applies directly
here: `state` is bounded (see `_STATE_MAX_CHARS`) and is the only free
text handed to either model. Neither model is ever asked to act on
retrieved content as an instruction; both are asked one narrow
multiple-choice question over a capped string.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import Harness, HarnessCallError, Message
from system_03_search_agent.harness.jev_client import (
    JEV_TOTAL_TIMEOUT_S,
    JevCallError,
    JevResult,
    call_jev,
)
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

#: How long `decide()` waits for Jev before treating the call as timed out:
#: Jev's own TOTAL bound (`jev_client.JEV_TOTAL_TIMEOUT_S`, 3 s, enforced
#: around the whole request since the fix round, F-8.2-J03) plus a small
#: margin for the cap check and scheduling. A second, outer net only: the
#: client's own bound fires first.
_JEV_WAIT_S = JEV_TOTAL_TIMEOUT_S + 0.5

#: How long `decide()` waits for the guard tier's pick once Jev has failed
#: and the guard's pick is the one that decides: the guard call's own
#: step budget plus a margin. A guard pick that ARRIVES within it is always
#: used, however long Jev took to fail (F-8.2-J04).
_GUARD_FALLBACK_WAIT_S = _GUARD_BUDGET_S + 1.0

#: How long `decide()` waits for the guard tier's COMPARISON pick after Jev
#: has already decided, in seconds. At most one second, by the fix round's
#: brief (F-8.2-A12): the guard's pick is recorded beside Jev's for the
#: comparison table and used only when Jev fails, so once Jev has answered
#: nobody should wait up to the guard's 15-second budget for a number the
#: person never sees. The decisions that sit on the person's path run
#: beside a longer call (the injection classifier, Think's own
#: classification, the choices writer), so this second is usually hidden.
GUARD_COMPARISON_GRACE_S: Final[float] = 1.0

#: `DecisionRecord.fallback_reason` when Jev decided and the guard tier's
#: comparison pick had not arrived within `GUARD_COMPARISON_GRACE_S`. The
#: guard call is then stopped; `guard_choice` is None because no pick was
#: made in time, not because the guard failed to make one.
GUARD_NOT_READY: Final[str] = "guard_not_ready"

#: How `DecisionRecord.fallback_reason` starts when NEITHER model made a
#: usable pick (fix round, F-8.2-A04). In Jev mode it is followed by a colon
#: and Jev's own failure reason, e.g. "no_usable_pick:timeout".
NO_USABLE_PICK: Final[str] = "no_usable_pick"


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


#: Words that, just before an option in a guard reply, turn a mention of the
#: option into its denial.
_NEGATION_WORDS: Final[frozenset[str]] = frozenset(
    {
        "not", "no", "never", "neither", "nor", "cannot", "can't", "cant",
        "isn't", "isnt", "doesn't", "doesnt", "don't", "dont", "won't", "wont",
    }
)


def _parse_guard_choice(raw: str, options: Sequence[str]) -> str | None:
    """Deterministic, exact-match-or-whole-token parse. Never a fuzzy score
    (production-standards.md's AI answer grounding gate applies the same
    exact-match discipline to this closed-option decision).

    The fallback matches an option only as a WHOLE token, and only when
    exactly one offered option appears. It was a bare substring test, which
    read "off_topic" out of `"is_off_topic": false` (builder J, F-J-06) and,
    for a reply naming two options ("not off_topic, on_topic"), returned
    whichever option happened to be listed first. Two options named, or
    none, is no usable pick, and the caller falls back or fails open.
    """
    text = raw.strip()
    for opt in options:
        if text == opt:
            return opt
    found = {
        opt: match
        for opt in options
        if (match := re.search(rf"(?<![\w-]){re.escape(opt)}(?![\w-])", text)) is not None
    }
    if len(found) != 1:
        return None
    ((opt, match),) = found.items()
    # "This is not off_topic." names one option and means the other (fix
    # round, F-8.2-J08). A negation in the three words before the option
    # makes the reply ambiguous, and an ambiguous reply is no usable pick.
    preceding = re.findall(r"[\w']+", text[: match.start()].lower())[-3:]
    if _NEGATION_WORDS.intersection(preceding):
        return None
    return opt


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
    caller records a None guard pick as no pick, and when Jev made none
    either, fills `chosen` with the caller's fail-open default.
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


def _retrieve_outcome(task: asyncio.Task[Any]) -> None:
    """Mark a finished task's exception as read, so asyncio never logs
    "exception was never retrieved" for a pick `decide()` stopped reading
    (a caller cancelled the decision, or the guard's comparison was dropped).
    `decide()` still reads every outcome it uses through the two helpers
    below."""
    if not task.cancelled():
        task.exception()


def _jev_outcome(task: asyncio.Task[JevResult], point: str) -> JevResult | BaseException:
    """Jev's result, its failure, or a timeout when it has not finished.

    Not finished within `_JEV_WAIT_S` means Jev's own total bound did not
    fire, which should not happen; it is treated as the timeout it is.
    """
    if not task.done():
        return JevCallError(
            f"Jev did not answer decision {point!r} within {_JEV_WAIT_S}s; "
            "fall back to the guard tier's pick for this decision",
            reason="timeout",
        )
    if task.cancelled():
        return JevCallError(
            f"Jev's call for decision {point!r} was cancelled; fall back to the guard "
            "tier's pick for this decision",
            reason="timeout",
        )
    exc = task.exception()
    return exc if exc is not None else task.result()


def _guard_outcome(task: asyncio.Task[str | None]) -> str | None:
    """The guard tier's pick if it has ARRIVED, else None.

    Read from the task itself rather than from any outer wait, so a pick
    that arrived is used however long the other call took (F-8.2-J04).
    """
    if not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return task.result()


async def decide(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    *,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
    default: str | None = None,
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
    CONCURRENTLY over the same `state` and `options`, as two tasks.

    - Jev's choice is used when it answers within its 3-second TOTAL bound
      with one of the offered `options`. `decide()` then waits at most
      `GUARD_COMPARISON_GRACE_S` for the guard's comparison pick; one that
      has not arrived by then is stopped and recorded as not ready
      (`fallback_reason == GUARD_NOT_READY`, `guard_choice` None).
    - When Jev fails, the guard tier's choice is used, waited for within
      the guard's own step budget, and `fallback_reason` names Jev's
      failure (`JevCallError.reason`, `"cost_cap"`, `"unexpected_error"`).
      A guard pick that has arrived is always read, never discarded by an
      outer limit.
    - When neither side produced a valid answer (either provider),
      `jev_choice` and `guard_choice` are both None, `fallback_reason`
      starts with `"no_usable_pick"` (in Jev mode followed by a colon and
      Jev's own failure, e.g. `"no_usable_pick:timeout"`), and `chosen` is
      `default`, the caller's fail-open option, so the record states what
      the loop actually did rather than a pick no model made (F-8.2-A04,
      F-8.2-J13). `decided_by` still reads `"guard"` there, because the
      contract's field allows only "jev" or "guard"; the None picks and the
      reason are what say that nobody decided. Without a `default`,
      `chosen` is `options[0]`.

    Raises:
        ValueError: if `options` is empty (there is nothing to decide
            between), the description does not fit the options (see
            `_check_description`), or `default` is not an offered option.
    """
    if not options:
        raise ValueError(f"decide() for {point!r} was given an empty options list")
    _check_description(point, options, instructions, criteria)
    if default is not None and default not in options:
        raise ValueError(
            f"decide() for {point!r}: default {default!r} is not one of the offered options"
        )
    fallback_default = default if default is not None else options[0]

    bounded_state = state[:_STATE_MAX_CHARS]
    provider = os.environ.get("CLASSIFIER_PROVIDER", "guard").strip().lower()

    if provider != "jev":
        guard_choice = await _run_guard_pick(
            harness, trace_id, bounded_state, options, instructions, criteria
        )
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=guard_choice if guard_choice is not None else fallback_default,
            decided_by="guard",
            guard_choice=guard_choice,
            fallback_reason=None if guard_choice is not None else NO_USABLE_PICK,
        )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = resolve_jev_model()

    # Two tasks, not one `gather` (fix round, F-8.2-J04, A12 and A05). A
    # gather returns nothing until BOTH calls finish, so a slow guard held
    # up a decision Jev had already made, and an outer limit that fired
    # threw away a guard pick that had arrived long before. Waiting on each
    # task on its own terms fixes both: Jev is waited for within its own
    # total bound; once Jev has decided, the guard's comparison pick gets a
    # short grace; once Jev has failed, the guard's pick is waited for
    # within the guard's own budget, and a pick that has arrived is always
    # read. No gather also means no orphaned gathering future to log an
    # asyncio ERROR when a caller cancels a decision nobody will read.
    guard_task = asyncio.create_task(
        _run_guard_pick(harness, trace_id, bounded_state, options, instructions, criteria)
    )
    jev_task = asyncio.create_task(
        _run_jev_pick(
            harness, trace_id, point, bounded_state, options, model, api_key, instructions, criteria
        )
    )
    for task in (guard_task, jev_task):
        task.add_done_callback(_retrieve_outcome)
    guard_ready = False
    try:
        await asyncio.wait({jev_task}, timeout=_JEV_WAIT_S)
        jev_outcome = _jev_outcome(jev_task, point)
        guard_wait_s = (
            GUARD_COMPARISON_GRACE_S
            if isinstance(jev_outcome, JevResult)
            else _GUARD_FALLBACK_WAIT_S
        )
        await asyncio.wait({guard_task}, timeout=guard_wait_s)
        guard_ready = guard_task.done()
    finally:
        # Whatever is still running is a pick nobody will read: the guard's
        # comparison past its grace, or both calls when the caller itself
        # cancelled this decision. Stop them so they spend nothing more.
        for task in (guard_task, jev_task):
            if not task.done():
                task.cancel()

    guard_choice = _guard_outcome(guard_task)

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
        if not guard_ready:
            fallback_reason = GUARD_NOT_READY
    elif guard_choice is not None:
        chosen = guard_choice
        decided_by = "guard"
        if fallback_reason is None:
            fallback_reason = "jev_unavailable"
    else:
        # Neither model made a pick (F-8.2-A04, F-8.2-J13). The record says
        # so, and names no pick nobody made: both picks stay None, the
        # reason starts with "no_usable_pick" and keeps Jev's own failure
        # after the colon, and `chosen` is the caller's fail-open default,
        # which is what the loop actually does.
        chosen = fallback_default
        decided_by = "guard"
        fallback_reason = (
            f"{NO_USABLE_PICK}:{fallback_reason}" if fallback_reason else NO_USABLE_PICK
        )

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
