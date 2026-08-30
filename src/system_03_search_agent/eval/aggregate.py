"""pass@k and pass^k over per-run outcomes (T-5.1-05).

Depends on:
    - Nothing beyond the standard library.

Reads / Writes:
    - Nothing.

`requirements/Evaluation_playbook.md`, "Composition with the eval-harness
outcome model": "The rubric grades a single run... eval-harness pass@k and
pass^k aggregate those per-run outcomes across k samples."

The two targets for a must-pass moat question, which are deliberately at
different levels:

- Hard-fails must hold on EVERY run: pass^k = 100 percent. No fabrication
  and no verdict, ever.
- Quality (13 of 16): pass@3 as the floor, pass^3 at least 90 percent as the
  reliability target.

The asymmetry is the point. A fabrication is never acceptable; quality is
high but not required to be perfect, which matches a biomedical setting
where a confident wrong answer is worse than no answer.

## Why abstain has its own token

A run that correctly refused when nothing was retrievable is a PASS. A run
that refused when a correct source existed is a FAIL. Both are abstains, so
a single `abstain` token would force every caller to re-derive the
distinction, and a caller that got it backwards would let the agent score
100 percent by refusing every question.
"""

from __future__ import annotations

from collections.abc import Sequence

PASSING_TOKENS = frozenset({"pass", "abstain_pass"})
FAILING_TOKENS = frozenset({"fail", "abstain_fail"})
KNOWN_TOKENS = PASSING_TOKENS | FAILING_TOKENS


def _validated(outcomes: Sequence[str], k: int) -> list[str]:
    unknown = sorted(set(outcomes) - KNOWN_TOKENS)
    if unknown:
        raise ValueError(
            f"unknown outcome token(s) {unknown}, expected a subset of "
            f"{sorted(KNOWN_TOKENS)}"
        )
    if k <= 0:
        raise ValueError("k must be positive")
    if len(outcomes) < k:
        raise ValueError(
            f"asked for k={k} but only {len(outcomes)} sample(s) were supplied. "
            "Scoring fewer samples than k would silently report a k-sample "
            "reliability figure that was never measured."
        )
    return list(outcomes[:k])


def pass_at_k(outcomes: Sequence[str], *, k: int) -> float:
    """1.0 when ANY of the first k samples passed. Can it do it at all?"""
    samples = _validated(outcomes, k)
    return 1.0 if any(token in PASSING_TOKENS for token in samples) else 0.0


def pass_caret_k(outcomes: Sequence[str], *, k: int) -> float:
    """1.0 when EVERY one of the first k samples passed. Does it do it reliably?"""
    samples = _validated(outcomes, k)
    return 1.0 if all(token in PASSING_TOKENS for token in samples) else 0.0


def hard_fail_free_rate(per_run_hard_fails: Sequence[Sequence[str]]) -> float:
    """The fraction of runs that hit no hard-fail at all.

    Reported separately from the quality metrics because its target is
    different: 100 percent, not 90. A single hard-fail in a hundred runs is
    a failed gate, and burying it in an average would hide exactly the event
    the gate exists to catch.
    """
    if not per_run_hard_fails:
        return 1.0
    clean = sum(1 for fails in per_run_hard_fails if not fails)
    return clean / len(per_run_hard_fails)


def aggregate_dataset(
    outcomes_by_query: dict[str, Sequence[str]], *, k: int
) -> dict[str, float]:
    """Mean pass@k and mean pass^k across every query in the dataset.

    The denominator is the number of queries ACTUALLY scored, and callers
    that dropped an unverifiable row must say so, per this phase's
    blocked-stop. Reporting 49 of 49 as 100 percent when the set holds 50 is
    the shape of dishonesty this harness exists to prevent.
    """
    if not outcomes_by_query:
        return {"pass_at_k": 0.0, "pass_caret_k": 0.0, "queries_scored": 0.0}

    at_k = [pass_at_k(o, k=k) for o in outcomes_by_query.values()]
    caret_k = [pass_caret_k(o, k=k) for o in outcomes_by_query.values()]
    return {
        "pass_at_k": sum(at_k) / len(at_k),
        "pass_caret_k": sum(caret_k) / len(caret_k),
        "queries_scored": float(len(outcomes_by_query)),
    }


def retrieval_consistency(records) -> float | None:
    """How much the samples of one question agree on WHAT THEY RETRIEVED.

    Returns the mean pairwise Jaccard overlap of the cited source ids across
    samples, or None when there are fewer than two samples.

    NONE RATHER THAN 1.0 FOR A SINGLE SAMPLE. A lone run never disagreed
    with anything, and reporting that as perfect agreement is the same class
    of claim as a coverage metric reporting 0 percent for a quantity nothing
    observed. Consistency is a property of a SET, so a set of one has none.

    THE PROPERTY THIS EXISTS FOR: the open flag this phase was built to
    measure is that the first answer grounds nothing on a single finding in
    about half of live runs, measured across twelve live runs at two commits
    on 2026-08-20. That is a RETRIEVAL consistency failure, and no per-run
    check can see it, because each individual run looks internally fine.
    """
    sets = [
        frozenset(
            str(c.get("source_id"))
            for c in record.citations
            if c.get("source_id")
        )
        for record in records
    ]
    if len(sets) < 2:
        return None

    scores: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            union = a | b
            scores.append(len(a & b) / len(union) if union else 1.0)
    return sum(scores) / len(scores)
