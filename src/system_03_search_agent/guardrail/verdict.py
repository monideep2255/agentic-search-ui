"""The shared admission verdict every Section 10 screen returns.

Depends on:
    - system_03_search_agent.contracts.events (GuardPayload, for the category
      vocabulary this type is required to stay inside)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The same six members as `GuardPayload.category`, deliberately not a second
# hand-maintained copy: `test_guard_category_matches_the_event_contract`
# asserts the two stay identical, so a contract change that forgets this file
# fails a test rather than drifting silently.
GuardCategory = Literal[
    "ok", "off_topic", "medical_advice", "injection", "rate_limited", "cost_capped"
]

# `GuardPayload.reason`'s own cap. Enforced here rather than at the event
# boundary so a reason can never be built too long and then silently truncated
# into something that reads as a different statement.
MAX_REASON_LENGTH = 256


@dataclass(frozen=True)
class GuardVerdict:
    """One admission decision, ready to become a `GuardPayload`.

    Frozen because a verdict is evidence of a decision already made. A screen
    that wants a different outcome returns a new verdict rather than mutating
    one, so no downstream step can quietly upgrade a refusal to an admission.
    """

    admitted: bool
    category: GuardCategory
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.admitted and self.category != "ok":
            raise ValueError(
                "an admitted verdict must carry category 'ok', not "
                f"{self.category!r}"
            )
        if not self.admitted and self.category == "ok":
            raise ValueError("a refused verdict cannot carry category 'ok'")
        if self.reason is not None and len(self.reason) > MAX_REASON_LENGTH:
            raise ValueError(
                f"reason exceeds {MAX_REASON_LENGTH} characters; truncate at "
                "the call site so the caller chooses what survives"
            )


def admitted() -> GuardVerdict:
    """The one admitting verdict. Takes no arguments by design.

    There is exactly one way to be admitted and many ways to be refused, so
    the admitting constructor carries no parameters a caller could get wrong.
    """
    return GuardVerdict(admitted=True, category="ok", reason=None)


def refused(category: GuardCategory, reason: str) -> GuardVerdict:
    """A refusal. `reason` is truncated to the contract's cap, never rejected.

    Truncation rather than an error because a refusal must never fail to be
    produced: a screen that raises while building its refusal would admit the
    query it was trying to block.
    """
    if category == "ok":
        raise ValueError("refused() requires a refusal category, not 'ok'")
    return GuardVerdict(
        admitted=False, category=category, reason=reason[:MAX_REASON_LENGTH]
    )
