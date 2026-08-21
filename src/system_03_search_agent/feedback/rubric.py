"""Deterministic `rubric_outcome`, at zero LLM cost (T-4.6-04).

Depends on:
    - Nothing. Pure lookup, no imports beyond typing.

Reads:
    - Nothing.

Writes:
    - Nothing.

Section 15: "`rubric_outcome` is deterministic and populated on every row at
zero LLM cost (the trust signal plus the hard-fail checks); `rubric_score`
(0 to 16) is populated only when the full graded rubric runs, which in v1
means offline golden-dataset replay, not every live query." This module is
the first half of that sentence. `rubric_score` is never set here; it stays
`None` on every live row (`feedback/capture.py` is the module that leaves it
`None`, since `InteractionRow.rubric_score` has no other writer on the live
path), and it is populated only by build phase 5.1's offline replay.
"""

from __future__ import annotations


def rubric_outcome_for(*, trust_signal: str, hard_fails: list[str]) -> str:
    """`abstain`, `fail`, or `pass`, from an already-decided signal and list.

    Per `requirements/Evaluation_playbook.md`'s "Composition with the
    eval-harness outcome model": "The rubric grades a single run into one
    outcome: pass (score at least 13 of 16, no hard-fail), fail (any
    hard-fail, or score under 13), or abstain (returned the refusal
    string)."

    `abstain` is the outcome for a run that returned the refusal path. On
    this system's own four-state trust signal (`TrustOutcome` in
    `contracts/events.py`: `answer`, `flag`, `ask`, `refuse`), `refuse` is
    the one state that IS that refusal path, so it is checked first and
    unconditionally: a refusal is never reclassified as `fail` even when a
    hard-fail was also recorded for the same run, since the playbook names
    exactly one condition for `abstain` and does not compose it with the
    hard-fail check. `flag` and `ask` are still answer-shaped outputs with
    caveats, not refusals, so they fall through to the same fail/pass check
    `answer` does.

    Both arguments are supplied by the caller (`feedback/capture.py`),
    never computed here. That split is what keeps this function a pure
    lookup over values someone else already decided, which is the whole
    reason `rubric_outcome` can be populated on every row at zero LLM cost:
    there is no data this function could reach for that would require a
    model call, because it reaches for nothing at all.
    """
    if trust_signal == "refuse":
        return "abstain"
    if hard_fails:
        return "fail"
    return "pass"
