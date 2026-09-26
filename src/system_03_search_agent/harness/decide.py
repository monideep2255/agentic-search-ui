"""The one classifier seam: Jev decides, and the guard tier steps in only
when Jev fails (build phase 8.2, cards 8, 9, 10 and 13; build phase 8.6,
DECISIONS.md 2026-09-25, "Jev decides; the guard tier (DeepSeek) is Jev's
fallback on failure only").

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
"think.recent_years"), never free text.

Who decides, since build phase 8.6. With `CLASSIFIER_PROVIDER=jev`, Jev is
asked alone. The guard tier is asked the same question over the same
bounded `state` only when Jev fails: a timeout at Jev's 3-second total
bound, an HTTP error, a malformed reply, an option outside the offered set,
the cost cap, or anything unexpected. The reason is recorded on the
`DecisionRecord`. Nothing runs beside Jev on the live path any more: the
build phase 8.2 design asked the guard tier every decision concurrently and
waited up to a one-second grace for its pick, only to record it, which
doubled the classifier calls on every question for a table that read "not
ready" in most rows. The comparison of the two models now runs offline,
through `compare_models` at the end of this module, which no live path calls;
its one caller is `testing/Developer/scripts/compare_classifiers.py`.

`ai-security-standards.md`'s prompt-injection defense applies directly
here: `state` is bounded (see `_STATE_MAX_CHARS`) and is the only free
text handed to either model. Neither model is ever asked to act on
retrieved content as an instruction; both are asked one narrow
multiple-choice question over a capped string.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

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

logger = logging.getLogger(__name__)

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
#: step budget plus a margin. The guard call enforces its own budget first;
#: this is the outer net, the same shape as `_JEV_WAIT_S`.
_GUARD_FALLBACK_WAIT_S = _GUARD_BUDGET_S + 1.0

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
    exceeded, the call times out, or the call fails: `decide()` records a
    None guard pick as no pick, and when Jev made none either, fills
    `chosen` with the caller's fail-open default. In Jev mode this runs
    only after Jev has failed.
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
    `cost_control.QueryCapExceededError` on any failure; `_jev_attempt`
    catches both.
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


def jev_decides() -> bool:
    """Whether Jev is the classifier: `CLASSIFIER_PROVIDER=jev`, read on
    every call so a deployment's setting is the only switch.

    Anything else, unset included, means the guard tier decides alone, the
    code default that keeps production untouched until the product owner
    flips the switch. `decide()` and the reworded-sentence check
    (`synthesis/sentence_check.py`) both read it here, so the two can never
    disagree about who decides.
    """
    return os.environ.get("CLASSIFIER_PROVIDER", "guard").strip().lower() == "jev"


async def _jev_attempt(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    model: str,
    api_key: str,
    instructions: str | None,
    criteria: Mapping[str, str] | None,
) -> JevResult | str:
    """Jev's pick, or the reason it made none.

    The reason is what `DecisionRecord.fallback_reason` records:
    `JevCallError.reason` ("timeout", "http_error", "malformed_reply",
    "invalid_option"), "cost_cap", "timeout" again when Jev's own bound did
    not fire and `_JEV_WAIT_S` did, or "unexpected_error". Never raises,
    except for cancellation: a caller that cancels the decision stops Jev's
    call with it, since `asyncio.wait_for` cancels what it waits on.
    """
    try:
        return await asyncio.wait_for(
            _run_jev_pick(
                harness, trace_id, point, state, options, model, api_key, instructions, criteria
            ),
            timeout=_JEV_WAIT_S,
        )
    except JevCallError as exc:
        return exc.reason
    except QueryCapExceededError:
        return "cost_cap"
    except TimeoutError:
        return "timeout"
    except Exception:  # noqa: BLE001 - a broken Jev call falls back, it never breaks the decision
        return "unexpected_error"


async def _guard_fallback_pick(
    harness: Harness,
    trace_id: str,
    state: str,
    options: Sequence[str],
    instructions: str | None,
    criteria: Mapping[str, str] | None,
) -> str | None:
    """The guard tier's pick, or None. `decide()` asks it only once Jev has
    failed; `compare_models` asks it beside Jev, offline.

    `_run_guard_pick` already returns None on the cost cap, a timeout of its
    own step budget and a failed call; the outer wait and the broad catch
    are nets for anything that slips past those, so a failed fallback reads
    as "no usable pick", never as an exception out of `decide()`.
    """
    try:
        return await asyncio.wait_for(
            _run_guard_pick(harness, trace_id, state, options, instructions, criteria),
            timeout=_GUARD_FALLBACK_WAIT_S,
        )
    except TimeoutError:
        return None
    except Exception:  # noqa: BLE001 - see the docstring
        return None


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
    code-authored description of the decision. Whichever model answers
    receives the same description: the guard tier in its system message,
    Jev in the endpoint's own `instructions` and `criteria` fields. `state`
    stays the person's bounded text only. Every wired decision point passes
    both; without them the models see only option names, which measured
    wrong on three of the five decision shapes (builder J, F-J-03).

    With `CLASSIFIER_PROVIDER` unset or anything other than `"jev"` (the
    code default, `"guard"`): Jev is never called. The guard tier decides
    alone and its pick is used. This is what keeps production untouched
    until the product owner flips the switch.

    With `CLASSIFIER_PROVIDER=jev` (build phase 8.6):

    - Jev is asked alone. When it answers within its 3-second TOTAL bound
      with one of the offered `options`, its choice is used at once:
      `decided_by == "jev"`, `guard_choice` None, `agreed` None,
      `fallback_reason` None. The guard tier is not called, so the
      decision takes Jev's time and nothing more.
    - When Jev fails, and only then, the guard tier is asked the same
      question within its own step budget. Its pick is used and
      `fallback_reason` names Jev's failure (`JevCallError.reason`,
      `"cost_cap"`, `"unexpected_error"`).
    - When neither model produced a valid answer (either provider),
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

    if not jev_decides():
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

    jev = await _jev_attempt(
        harness, trace_id, point, bounded_state, options, model, api_key, instructions, criteria
    )
    if isinstance(jev, JevResult):
        return _jev_mode_record(point, options, jev, None, fallback_default)

    logger.warning(
        "Jev made no pick for decision %s (trace %s, %s); asking the guard tier",
        point,
        trace_id,
        jev,
    )
    guard_choice = await _guard_fallback_pick(
        harness, trace_id, bounded_state, options, instructions, criteria
    )
    return _jev_mode_record(point, options, jev, guard_choice, fallback_default)


def _jev_mode_record(
    point: str,
    options: Sequence[str],
    jev: JevResult | str,
    guard_choice: str | None,
    fallback_default: str,
) -> DecisionRecord:
    """The record `decide()` returns in Jev mode, built in one place so the
    offline comparison hands the loop exactly the record the live seam would.

    - Jev made a pick: it decides, and no guard pick is recorded, since the
      live seam never asks the guard then.
    - Jev failed (`jev` is its reason) and the guard made a pick: the guard
      decides and the reason is recorded.
    - Neither made a pick (F-8.2-A04, F-8.2-J13): the record names no pick
      nobody made. Both picks stay None, the reason starts with
      "no_usable_pick" and keeps Jev's own failure after the colon, and
      `chosen` is the caller's fail-open default, which is what the loop
      actually does.
    """
    if isinstance(jev, JevResult):
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=jev.choice,
            decided_by="jev",
            jev_choice=jev.choice,
            jev_confidence=jev.confidence,
            jev_latency_ms=jev.latency_ms,
        )
    if guard_choice is not None:
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=guard_choice,
            decided_by="guard",
            guard_choice=guard_choice,
            fallback_reason=jev,
        )
    return DecisionRecord(
        name=point,
        options=list(options),
        chosen=fallback_default,
        decided_by="guard",
        fallback_reason=f"{NO_USABLE_PICK}:{jev}",
    )


# ---------------------------------------------------------------------------
# The offline comparison (build phase 8.6, T-8.6-03). No live path calls
# anything below; `tests/system_03_search_agent/harness/test_decide.py`
# asserts that nothing else under `src/` names `compare_models`.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelComparison:
    """Jev's and the guard tier's answers to one decision, asked side by side.

    `jev` is Jev's validated result, or the reason it made no pick, exactly
    as `decide()` sees it. Built only by `compare_models`.
    """

    point: str
    options: tuple[str, ...]
    jev: JevResult | str
    guard_choice: str | None
    guard_latency_ms: int

    @property
    def jev_choice(self) -> str | None:
        return self.jev.choice if isinstance(self.jev, JevResult) else None

    @property
    def jev_confidence(self) -> float | None:
        return self.jev.confidence if isinstance(self.jev, JevResult) else None

    @property
    def jev_probabilities(self) -> dict[str, float] | None:
        return dict(self.jev.probabilities) if isinstance(self.jev, JevResult) else None

    @property
    def jev_latency_ms(self) -> int | None:
        return self.jev.latency_ms if isinstance(self.jev, JevResult) else None

    @property
    def jev_failure(self) -> str | None:
        return None if isinstance(self.jev, JevResult) else self.jev

    @property
    def agreed(self) -> bool | None:
        """True or False only when both models made a pick."""
        if self.jev_choice is None or self.guard_choice is None:
            return None
        return self.jev_choice == self.guard_choice

    def live_record(self, default: str | None = None) -> DecisionRecord:
        """The record Jev-mode `decide()` returns for these picks, so a loop
        run under the comparison takes the path it takes on develop.

        Raises:
            ValueError: if `default` is not one of the offered options.
        """
        if default is not None and default not in self.options:
            raise ValueError(
                f"live_record() for {self.point!r}: default {default!r} is not an offered option"
            )
        fallback_default = default if default is not None else self.options[0]
        guard_choice = None if isinstance(self.jev, JevResult) else self.guard_choice
        return _jev_mode_record(self.point, self.options, self.jev, guard_choice, fallback_default)


async def compare_models(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    *,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> ModelComparison:
    """OFFLINE ONLY: ask Jev and the guard tier the same decision at once.

    Its one caller is `testing/Developer/scripts/compare_classifiers.py`.
    Both models get exactly what `decide()` gives them: the same bounded
    state, the same description, the same cost-cap checks, Jev's 3-second
    total bound and the guard's own budget. Both are asked whatever
    `CLASSIFIER_PROVIDER` says. A model's failure is recorded, never
    raised: Jev's as its reason, the guard's as no pick.

    Raises:
        ValueError: as `decide()` does, for empty options or a description
            that does not fit them.
    """
    if not options:
        raise ValueError(f"compare_models() for {point!r} was given an empty options list")
    _check_description(point, options, instructions, criteria)
    bounded_state = state[:_STATE_MAX_CHARS]

    async def _timed_guard_pick() -> tuple[str | None, int]:
        started = time.monotonic()
        choice = await _guard_fallback_pick(
            harness, trace_id, bounded_state, options, instructions, criteria
        )
        return choice, int((time.monotonic() - started) * 1000)

    jev, (guard_choice, guard_latency_ms) = await asyncio.gather(
        _jev_attempt(
            harness,
            trace_id,
            point,
            bounded_state,
            options,
            resolve_jev_model(),
            os.environ.get("OPENROUTER_API_KEY", ""),
            instructions,
            criteria,
        ),
        _timed_guard_pick(),
    )
    return ModelComparison(
        point=point,
        options=tuple(options),
        jev=jev,
        guard_choice=guard_choice,
        guard_latency_ms=guard_latency_ms,
    )
