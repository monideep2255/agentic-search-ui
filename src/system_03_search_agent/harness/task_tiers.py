"""One table naming, for every place the agent loop calls a model, which
tier or provider serves it (build phase 8.2, card 8, DECISIONS.md
2026-09-25).

Depends on:
    - Nothing repo-local. Pure data plus a lookup function.

Reads:
    - Nothing.

Writes:
    - Nothing.

Restates `docs/architecture/Model_architecture.md`'s "Every model call in
one question" table (the eight existing call sites) as code, and adds the
five decision points build phase 8.2 introduces as `"classifier"` rows.
Nothing in the loop calls `task_tier_for` yet; this module is pure data
and a lookup function, wired up by a later wave once the classifier seam
(`harness/decide.py`) is actually threaded into `core/graph.py`.

Keeping this in sync with `Model_architecture.md` is a manual discipline,
the same one that document's own "What this document did not check"
section names: a call site added after this table is written, or reached
through a path this table's own author did not search for, will not
appear here. Re-derive both together at the next model-architecture
review rather than trusting either alone to have stayed current.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# "classifier" is not one of the three call_tier tiers ("guard", "plan",
# "synth"): it names a call routed through `harness.decide.decide`, which
# itself dispatches a guard-tier call and, when CLASSIFIER_PROVIDER=jev,
# Jev concurrently. A row of this kind is a "which decision path" fact,
# not a "which of the three tiers" fact, hence the separate literal rather
# than folding it into `harness.tiers.Tier`.
TaskTier = Literal["guard", "plan", "synth", "classifier"]


@dataclass(frozen=True)
class TaskTierEntry:
    """One row: a named call site, the tier or provider that serves it, and
    a one-line reason. `step` matches the loop step name
    (`harness.harness.budget_for_step`'s five values plus the
    ask-or-proceed sub-step that sits inside Think), never a free string.
    """

    call_site: str
    step: str
    tier: TaskTier
    note: str


# The eight call sites `Model_architecture.md` names today, restated as
# data. Order matches that document's own table, top to bottom.
_EXISTING_CALL_SITES: tuple[TaskTierEntry, ...] = (
    TaskTierEntry(
        call_site="guardrail.attack_classification",
        step="guardrail",
        tier="guard",
        note="Whether the question looks like a prompt-injection attempt, yes or no.",
    ),
    TaskTierEntry(
        call_site="think.ask_or_proceed",
        step="think",
        tier="guard",
        note="Whether a one-to-three-word clarifying question should be asked, or proceed.",
    ),
    TaskTierEntry(
        call_site="think.classification",
        step="think",
        tier="plan",
        note="What kind of question this is, and which entities it names.",
    ),
    TaskTierEntry(
        call_site="act.cypher_generation_fallback",
        step="act",
        tier="plan",
        note="The literal Cypher query text, only when no fixed template matches.",
    ),
    TaskTierEntry(
        call_site="act.reader_pass",
        step="act",
        tier="guard",
        note="A short read of one free-text tool result, pulling out entities and ids.",
    ),
    TaskTierEntry(
        call_site="write.sentence_check",
        step="write",
        tier="guard",
        note="Whether one reworded answer sentence says more than the exact quote it cites.",
    ),
    TaskTierEntry(
        call_site="write.answer_synthesis",
        step="write",
        tier="synth",
        note="The prose answer itself, built only from the facts it was handed.",
    ),
    TaskTierEntry(
        call_site="write.repair_pass",
        step="write",
        tier="synth",
        note="A second attempt at the same answer, only when the first left out a shown fact.",
    ),
)

# The five decision points build phase 8.2 introduces (planned section of
# Model_architecture.md). Each one is a `harness.decide.decide` call, not
# yet wired into the loop step named here; the step is where it WILL sit
# once wired.
_CLASSIFIER_DECISION_POINTS: tuple[TaskTierEntry, ...] = (
    TaskTierEntry(
        call_site="guardrail.relevancy",
        step="guardrail",
        tier="classifier",
        note="Whether a question is relevant to what the system covers.",
    ),
    TaskTierEntry(
        call_site="think.ask_back",
        step="think",
        tier="classifier",
        note="The one-to-three-word ask-back decision.",
    ),
    TaskTierEntry(
        call_site="plan.literature",
        step="plan",
        tier="classifier",
        note="Which literature source to route a question to.",
    ),
    TaskTierEntry(
        call_site="think.recent_years",
        step="think",
        tier="classifier",
        note="Whether to ask about recent years.",
    ),
    TaskTierEntry(
        call_site="plan.resource",
        step="plan",
        tier="classifier",
        note="Which resource to pull.",
    ),
)

# Sorted by call_site, fixed in code. Not part of the prompt-cache stable
# prefix (this table is never assembled into a prompt), but the same
# never-reorder-at-runtime discipline applies for the same reason: a
# lookup table whose iteration order can silently change is harder to
# diff and to reason about than one that cannot.
ALL_TASK_TIERS: tuple[TaskTierEntry, ...] = tuple(
    sorted((*_EXISTING_CALL_SITES, *_CLASSIFIER_DECISION_POINTS), key=lambda entry: entry.call_site)
)

_BY_CALL_SITE: dict[str, TaskTierEntry] = {entry.call_site: entry for entry in ALL_TASK_TIERS}


class UnknownCallSiteError(KeyError):
    """Raised when `task_tier_for` is asked about a call site not in this table."""


def task_tier_for(call_site: str) -> TaskTierEntry:
    """Return the `TaskTierEntry` for `call_site`.

    Raises:
        UnknownCallSiteError: if `call_site` names nothing in
            `ALL_TASK_TIERS`, before any other lookup is attempted, so a
            typo in a caller surfaces as a named error rather than a
            silently missing row.
    """
    try:
        return _BY_CALL_SITE[call_site]
    except KeyError:
        raise UnknownCallSiteError(
            f"unknown call site {call_site!r}; expected one of "
            f"{sorted(_BY_CALL_SITE)}"
        ) from None
