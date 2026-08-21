"""Stage 3 and stage 4: the weekly human-gated review ritual (Section 16).

Depends on:
    - system_03_search_agent.data.models (Interaction, CqCandidate)
    - system_03_search_agent.data.session (session_scope)

Reads:
    - The `interactions` and `cq_candidates` tables in the user-data
      database, including `query_text` and `user_feedback`, which Section
      16 and Section 11.3 both treat as sensitive by default. Both are
      surfaced only to the terminal a human reviewer is reading, never
      written to a log file or any other durable sink by this module.

Writes:
    - The `cq_candidates` table only. This module never writes to
      `interactions`.

This is T-4.6-10: a real script a human runs on a cadence (starter value
weekly, per `docs/build/Feedback_review_ritual.md`), not a document
describing one. It has three jobs, run in one pass per Section 16 stage 3:

    1. Surface the week's candidates (`find_weekly_candidates`).
    2. Let the reviewer check novelty and recurrence against the same
       trigger rule stage 4 defines (`find_similar_existing_candidates`,
       `count_pattern_recurrence`, `evaluate_trigger_rule`).
    3. Insert or reinforce a `cq_candidates` row (`upsert_candidate`).

The human-terminal gate is structural, not conventional, and this module is
the other half of that guarantee alongside the schema itself. Section 16:
"The LLM-judge writes `llm_judge_rationale`; it has no column that can move
a row to `promoted`." Nothing in this module computes, defaults, or infers
`reviewed_by` or `review_decision`; both are required arguments that must
arrive already decided, from a human, at the call site. `upsert_candidate`
raises rather than silently defaulting if either is missing or malformed.

Stage 2 (mine and cluster) is out of scope for v1
(`.claude/rules/v1-scope-boundary.md`); nothing here builds a clustering
job. The grouping this module does is a shallow, deterministic
normalization (case and whitespace only) that a human reviewer still has to
read and judge, per Section 16 stage 3 step 2: "most of what turns up is
noise ... the reviewer's job is to find the recurring pattern underneath."
"""

from __future__ import annotations

import argparse
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from system_03_search_agent.data.models import CqCandidate, Interaction
from system_03_search_agent.data.session import session_scope

#: Stage 3 step 1's review cadence. Starter value, tunable "like the cost
#: caps" per Section 16.
REVIEW_WINDOW_DAYS = 7

#: Stage 4's trigger rule. Starter values named explicitly in Section 16
#: ("3 occurrences in 30 days, tunable"). Named constants rather than
#: literals buried in a query, per this ticket's own acceptance criteria.
TRIGGER_FREQUENCY_THRESHOLD = 3
TRIGGER_ROLLING_WINDOW_DAYS = 30

#: `pg_trgm` similarity floor used to narrow the novelty check's candidate
#: list for the reviewer. Section 16 stage 4 names two acceptable checks
#: for v1, `pg_trgm` similarity or reviewer judgment; this threshold only
#: shapes the first, and the reviewer still makes the actual call.
SIMILARITY_THRESHOLD = 0.4

_WHITESPACE_RE = re.compile(r"\s+")

#: Trust signals stage 3 step 1 names as candidates on their own, independent
#: of the rubric outcome.
_FLAGGED_TRUST_SIGNALS = ("flag", "ask", "refuse")

#: Code points a terminal can interpret as a rendering command rather than as
#: text. F-4.6-A-06: a `query_text` carrying `\x1b[2K\x1b[1A` erased the two
#: lines this script had just printed and substituted a forged, benign
#: candidate group, displacing the `interaction_ids` line a reviewer then
#: copies into `feedback-review record`. Named as a class, not enumerated by
#: the one sequence the adversary happened to try:
#:
#: - C0 controls (U+0000 to U+001F) and DEL (U+007F): cursor movement, line
#:   erasure, carriage return, tab, and the ESC byte that starts every ANSI
#:   escape sequence. The adversary's payload lives entirely in this range.
#: - C1 controls (U+0080 to U+009F): the same rendering functions, reachable
#:   on an 8-bit-aware terminal with no ESC byte at all.
#: - Bidi format controls (U+061C, U+200E, U+200F, U+202A to U+202E, U+2066
#:   to U+2069): the Trojan Source class. These bias or reverse the VISUAL
#:   reading order of surrounding text with no escape sequence and no
#:   cursor movement, so a filter that only looks for ESC misses this
#:   family entirely.
#:
#: Deliberately allowed through, unescaped: every other code point a `str`
#: can hold, including accented Latin letters, Greek, Cyrillic, CJK
#: ideographs, combining marks, and astral-plane characters such as emoji.
#: A biomedical question containing "cafe with an accent", "Omega-globin",
#: a CJK gene name, or an emoji is ordinary content, not an attack, and
#: renders exactly as typed.
_DISPLAY_HOSTILE_CODE_POINTS = re.compile(
    "[\\x00-\\x1f\\x7f\\x80-\\x9f\\u061c\\u200e\\u200f\\u202a-\\u202e\\u2066-\\u2069]"
)


def _escape_for_terminal_display(text: str) -> str:
    """Render every code point in `_DISPLAY_HOSTILE_CODE_POINTS` as a visible escape.

    This is the display-side half of F-4.6-A-06. `writer.py`'s module docstring
    (around line 150) explains why storage does not do this: a control
    character other than NUL stores fine, and stripping it there would
    destroy content the review ritual needs to read. That comment names
    "whoever prints the column" as the owner of the rendering problem; this
    function is that owner.

    Each matched character is replaced with `str.encode("unicode_escape")`,
    the same notation Python's own `repr()` uses and the same notation this
    finding's reproduction used to show the payload (`\\x1b[2K`), so a
    reviewer sees a Python-style escape sequence rather than a live control
    character, and can still tell roughly what was sent. The substitution
    runs per matched character in isolation: it can only ever lengthen a
    hostile code point into its visible spelling, never touch, reorder, or
    drop a byte of ordinary text on either side of it.
    """
    return _DISPLAY_HOSTILE_CODE_POINTS.sub(
        lambda match: match.group(0).encode("unicode_escape").decode("ascii"), text
    )


def normalize_query_text(query_text: str) -> str:
    """Collapse whitespace and case so near-duplicate phrasings group together.

    Stage 3 step 1 groups "by normalized query text or entity set"; this
    picks the first of the two options Section 16 names. Deliberately
    shallow: no stemming, no synonym folding, no entity resolution. The
    reviewer, not this function, is the one who finds the recurring pattern
    under the noise (Section 16 stage 3 step 2).
    """
    return _WHITESPACE_RE.sub(" ", query_text.strip().lower())


def _is_flagged(interaction: Interaction) -> bool:
    """Stage 3 step 1's exact three-part filter, restated as a predicate.

    Kept as a Python predicate, re-applied over rows the SQL WHERE clause
    in `find_weekly_candidates` already narrows, so the two can never
    silently drift apart: this is the same rule, asserted twice, not two
    different rules that happen to agree today.
    """
    if interaction.rubric_outcome != "pass":
        return True
    if interaction.trust_signal in _FLAGGED_TRUST_SIGNALS:
        return True
    feedback = interaction.user_feedback or {}
    return feedback.get("rating") == "down"


@dataclass(frozen=True)
class CandidateGroup:
    """One cluster surfaced by `find_weekly_candidates`: same normalized query, several rows."""

    normalized_query: str
    count: int
    interaction_ids: tuple[uuid.UUID, ...]
    sample_query_text: str
    trust_signals: tuple[str, ...]
    rubric_outcomes: tuple[str, ...]
    down_feedback_count: int


def find_weekly_candidates(
    session: Session, *, window_days: int = REVIEW_WINDOW_DAYS
) -> list[CandidateGroup]:
    """Stage 3 step 1: surface the week's candidates, grouped and ordered by count.

    Exactly the filter Section 16 states: rows where `rubric_outcome !=
    'pass'`, `trust_signal IN ('flag','ask','refuse')`, or
    `user_feedback->>'rating' = 'down'`. The SQL WHERE clause below applies
    the same three conditions server-side over the review window as a
    coarse prefilter; `_is_flagged` re-asserts the identical rule in Python
    over the returned rows before grouping.
    """
    window_start = datetime.now(UTC) - timedelta(days=window_days)
    stmt = (
        select(Interaction)
        .where(
            Interaction.created_at >= window_start,
            or_(
                Interaction.rubric_outcome != "pass",
                Interaction.trust_signal.in_(_FLAGGED_TRUST_SIGNALS),
                Interaction.user_feedback["rating"].astext == "down",
            ),
        )
        .order_by(Interaction.created_at.desc())
    )
    rows = [row for row in session.execute(stmt).scalars() if _is_flagged(row)]

    groups: dict[str, list[Interaction]] = {}
    for row in rows:
        key = normalize_query_text(row.query_text)
        groups.setdefault(key, []).append(row)

    result = [
        CandidateGroup(
            normalized_query=key,
            count=len(members),
            interaction_ids=tuple(m.id for m in members),
            sample_query_text=members[0].query_text,
            trust_signals=tuple(m.trust_signal for m in members),
            rubric_outcomes=tuple(m.rubric_outcome for m in members),
            down_feedback_count=sum(
                1 for m in members if (m.user_feedback or {}).get("rating") == "down"
            ),
        )
        for key, members in groups.items()
    ]
    result.sort(key=lambda g: g.count, reverse=True)
    return result


def find_similar_existing_candidates(
    session: Session,
    representative_query: str,
    *,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[CqCandidate]:
    """Stage 4's novelty check: `pg_trgm` similarity against `cq_candidates.representative_query`.

    Section 16 stage 4 names two acceptable v1 checks: `pg_trgm`
    similarity, or reviewer judgment. This runs the former as a filter and
    returns candidates for the reviewer to look at; it does not itself
    decide novel versus not-novel (`upsert_candidate`'s
    `existing_candidate_id` argument is where that decision lands).
    `representative_query` reaches `func.similarity` as a bound parameter,
    never string-interpolated into the query text, per `production-standards`.
    """
    similarity_expr = func.similarity(CqCandidate.representative_query, representative_query)
    stmt = select(CqCandidate).where(similarity_expr >= threshold).order_by(similarity_expr.desc())
    return list(session.execute(stmt).scalars())


def count_pattern_recurrence(
    session: Session,
    normalized_query: str,
    *,
    window_days: int = TRIGGER_ROLLING_WINDOW_DAYS,
) -> int:
    """Stage 4's frequency check: how many times this pattern recurred in the rolling window.

    Counts across ALL interactions matching the normalized pattern in the
    window, not only the ones this week's review flagged as noisy: a
    pattern that recurs mostly as clean passes plus a handful of downvotes
    is still a recurring pattern. Matches by the same normalization
    `find_weekly_candidates` groups by.
    """
    window_start = datetime.now(UTC) - timedelta(days=window_days)
    stmt = select(Interaction.query_text).where(Interaction.created_at >= window_start)
    return sum(
        1
        for (query_text,) in session.execute(stmt)
        if normalize_query_text(query_text) == normalized_query
    )


@dataclass(frozen=True)
class TriggerRuleResult:
    """Stage 4's three-part gate, evaluated but never auto-acted-on.

    Nothing here writes a row. The reviewer reads this and calls
    `upsert_candidate`: with `existing_candidate_id=None` for a new
    candidate, or with an id drawn from `similar_candidates` to reinforce
    one that already exists.
    """

    frequency_count: int
    frequency_met: bool
    moat_met: bool
    similar_candidates: tuple[CqCandidate, ...]
    is_novel: bool


def evaluate_trigger_rule(
    session: Session,
    *,
    normalized_query: str,
    representative_query: str,
    moat_gate_provenance: bool,
    moat_gate_deterministic: bool,
    moat_partial_or_better: bool,
    frequency_threshold: int = TRIGGER_FREQUENCY_THRESHOLD,
    window_days: int = TRIGGER_ROLLING_WINDOW_DAYS,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> TriggerRuleResult:
    """Stage 4: evaluate all three conditions together, in the same pass the ritual runs in.

    `moat_partial_or_better` is supplied by the reviewer from an actual run
    of the moat test's no-general-tool-equivalent check (Section 16 stage
    3 step 3): this function has no way to run that check itself, and does
    not try to.
    """
    frequency_count = count_pattern_recurrence(session, normalized_query, window_days=window_days)
    similar = tuple(
        find_similar_existing_candidates(
            session, representative_query, threshold=similarity_threshold
        )
    )
    return TriggerRuleResult(
        frequency_count=frequency_count,
        frequency_met=frequency_count >= frequency_threshold,
        moat_met=bool(moat_gate_provenance and moat_gate_deterministic and moat_partial_or_better),
        similar_candidates=similar,
        is_novel=len(similar) == 0,
    )


def upsert_candidate(
    session: Session,
    *,
    representative_query: str,
    source_interaction_ids: Sequence[uuid.UUID],
    wedge_type: str | None,
    moat_gate_provenance: bool | None,
    moat_gate_deterministic: bool | None,
    moat_rank: str | None,
    reviewed_by: str,
    review_decision: str,
    review_notes: str | None = None,
    reviewed_at: datetime | None = None,
    existing_candidate_id: uuid.UUID | None = None,
) -> CqCandidate:
    """Stage 3 steps 3-4: insert a new candidate, or reinforce an existing one.

    `reviewed_by` and `review_decision` are REQUIRED, human-supplied
    arguments. This function computes neither: it raises `ValueError`
    rather than defaulting or inferring either one, which is what keeps
    the human-terminal gate real rather than conventional (Section 16:
    "The LLM-judge writes `llm_judge_rationale`; it has no column that can
    move a row to `promoted`").

    `existing_candidate_id` given: stage 4's reinforcement path. Appends
    new, deduplicated ids to `source_interaction_ids`, increments
    `frequency_count`, and leaves `moat_rank` untouched, per Section 16
    stage 4 ("A cluster matching an existing candidate instead appends to
    its `source_interaction_ids`, increments `frequency_count`, and leaves
    `moat_rank` as is: a reinforcement, not a new row").

    `existing_candidate_id` omitted: a brand new `cq_candidates` row.
    """
    if not reviewed_by or not reviewed_by.strip():
        raise ValueError(
            "reviewed_by is required and must be a real reviewer identity; "
            "this function never defaults or infers one"
        )
    if review_decision not in ("approve", "reject", "needs_more_data"):
        raise ValueError(
            "review_decision must be one of 'approve', 'reject', or "
            f"'needs_more_data', got {review_decision!r}"
        )

    now = reviewed_at or datetime.now(UTC)

    if existing_candidate_id is not None:
        candidate = session.get(CqCandidate, existing_candidate_id)
        if candidate is None:
            raise ValueError(f"no cq_candidates row with id {existing_candidate_id}")
        existing_ids = set(candidate.source_interaction_ids)
        new_ids = [i for i in source_interaction_ids if i not in existing_ids]
        if new_ids:
            candidate.source_interaction_ids = [*candidate.source_interaction_ids, *new_ids]
            candidate.frequency_count += len(new_ids)
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = now
        candidate.review_decision = review_decision
        candidate.review_notes = review_notes
        candidate.updated_at = now
        session.flush()
        return candidate

    status = {
        "approve": "approved",
        "reject": "rejected",
        "needs_more_data": "proposed",
    }[review_decision]

    candidate = CqCandidate(
        representative_query=representative_query,
        source_interaction_ids=list(source_interaction_ids),
        frequency_count=len(source_interaction_ids) or 1,
        wedge_type=wedge_type,
        moat_gate_provenance=moat_gate_provenance,
        moat_gate_deterministic=moat_gate_deterministic,
        moat_rank=moat_rank,
        reviewed_by=reviewed_by,
        reviewed_at=now,
        review_decision=review_decision,
        review_notes=review_notes,
        status=status,
    )
    session.add(candidate)
    session.flush()
    return candidate


# ---------------------------------------------------------------------------
# CLI: `python -m system_03_search_agent.feedback.review <command>`.
# Printed output is for the human reviewer's terminal only; nothing here
# writes `query_text` or `user_feedback` to a log file.
#
# Every stored, caller-reachable string this CLI prints (`query_text`,
# `representative_query`) goes through `_escape_for_terminal_display` first.
# That text is untrusted: it is stored verbatim by design (see
# `writer.py`'s module docstring) and reaches this terminal with no
# upstream filtering (F-4.6-A-06). System-computed or database-enum-
# constrained fields (`trust_signal`, ids, counts, status) are printed
# raw.
# ---------------------------------------------------------------------------


def _print_candidate_groups(groups: Sequence[CandidateGroup]) -> None:
    if not groups:
        print("No candidates flagged in the review window.")
        return
    for group in groups:
        # trust_signals is drawn from Interaction.trust_signal, which carries
        # a database CHECK constraint restricting it to 'answer', 'flag',
        # 'ask', 'refuse' (ck_interactions_trust_signal). It is not caller
        # free text and needs no display escaping.
        signals = ",".join(sorted(set(group.trust_signals)))
        print(f"count={group.count}  trust_signals=[{signals}]  down={group.down_feedback_count}")
        # sample_query_text is caller-supplied free text (F-4.6-A-06).
        print(f"  query: {_escape_for_terminal_display(group.sample_query_text[:120])}")
        # interaction_ids are uuid.UUID objects read back from the database;
        # str(uuid.UUID) always produces the fixed 36-character hyphenated
        # form and cannot carry a hostile code point.
        shown = group.interaction_ids[:5]
        suffix = " ..." if len(group.interaction_ids) > 5 else ""
        print(f"  interaction_ids: {', '.join(str(i) for i in shown)}{suffix}")


def _cmd_list(args: argparse.Namespace) -> None:
    with session_scope() as session:
        groups = find_weekly_candidates(session, window_days=args.window_days)
        _print_candidate_groups(groups)


def _print_similar(matches: Sequence[CqCandidate]) -> None:
    if not matches:
        print("No similar existing candidates found.")
        return
    for match in matches:
        # representative_query is stored, caller-reachable free text (it is
        # written from CLI arguments today, but this module must not depend
        # on that staying the only writer; the same class applies as for
        # sample_query_text above, F-4.6-A-06).
        print(
            f"{match.id}  status={match.status}  "
            f"{_escape_for_terminal_display(match.representative_query)}"
        )


def _cmd_similar(args: argparse.Namespace) -> None:
    with session_scope() as session:
        matches = find_similar_existing_candidates(session, args.query, threshold=args.threshold)
        _print_similar(matches)


def _cmd_trigger(args: argparse.Namespace) -> None:
    with session_scope() as session:
        result = evaluate_trigger_rule(
            session,
            normalized_query=normalize_query_text(args.query),
            representative_query=args.query,
            moat_gate_provenance=args.moat_gate_provenance,
            moat_gate_deterministic=args.moat_gate_deterministic,
            moat_partial_or_better=args.moat_partial_or_better,
        )
        print(f"frequency_count={result.frequency_count} frequency_met={result.frequency_met}")
        print(f"moat_met={result.moat_met}")
        similar_ids = [str(c.id) for c in result.similar_candidates]
        print(f"is_novel={result.is_novel} similar_candidates={similar_ids}")


def _cmd_record(args: argparse.Namespace) -> None:
    with session_scope() as session:
        candidate = upsert_candidate(
            session,
            representative_query=args.representative_query,
            source_interaction_ids=[uuid.UUID(i) for i in args.source_interaction_id],
            wedge_type=args.wedge_type,
            moat_gate_provenance=args.moat_gate_provenance,
            moat_gate_deterministic=args.moat_gate_deterministic,
            moat_rank=args.moat_rank,
            reviewed_by=args.reviewed_by,
            review_decision=args.review_decision,
            review_notes=args.review_notes,
            existing_candidate_id=(
                uuid.UUID(args.existing_candidate_id) if args.existing_candidate_id else None
            ),
        )
        print(f"cq_candidates row {candidate.id} status={candidate.status}")


def build_arg_parser() -> argparse.ArgumentParser:
    """The weekly review ritual's CLI. See `docs/build/Feedback_review_ritual.md`."""
    parser = argparse.ArgumentParser(
        prog="feedback-review",
        description="Stage 3/4 weekly review ritual (Section 16).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "list", help="Surface the week's flagged candidates, grouped and ordered by count."
    )
    p_list.add_argument("--window-days", type=int, default=REVIEW_WINDOW_DAYS)
    p_list.set_defaults(func=_cmd_list)

    p_similar = sub.add_parser(
        "similar", help="Find existing cq_candidates rows similar to a query (novelty check)."
    )
    p_similar.add_argument("query")
    p_similar.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD)
    p_similar.set_defaults(func=_cmd_similar)

    p_trigger = sub.add_parser("trigger", help="Evaluate stage 4's trigger rule for a pattern.")
    p_trigger.add_argument("query")
    p_trigger.add_argument("--moat-gate-provenance", action="store_true")
    p_trigger.add_argument("--moat-gate-deterministic", action="store_true")
    p_trigger.add_argument("--moat-partial-or-better", action="store_true")
    p_trigger.set_defaults(func=_cmd_trigger)

    p_record = sub.add_parser(
        "record", help="Insert or reinforce a cq_candidates row (stage 3 steps 3-4)."
    )
    p_record.add_argument("--representative-query", required=True)
    p_record.add_argument(
        "--source-interaction-id", action="append", required=True, dest="source_interaction_id"
    )
    p_record.add_argument(
        "--wedge-type",
        choices=["gene-variant-literature", "pathogen-sequence-outbreak", "paper-data-tool", "other"],
    )
    p_record.add_argument("--moat-gate-provenance", action="store_true")
    p_record.add_argument("--moat-gate-deterministic", action="store_true")
    p_record.add_argument("--moat-rank", choices=["tier_1", "tier_2", "none"])
    p_record.add_argument("--reviewed-by", required=True)
    p_record.add_argument(
        "--review-decision", required=True, choices=["approve", "reject", "needs_more_data"]
    )
    p_record.add_argument("--review-notes")
    p_record.add_argument("--existing-candidate-id")
    p_record.set_defaults(func=_cmd_record)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
