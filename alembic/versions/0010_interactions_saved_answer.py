"""interactions: the saved answer, so a past search opens instead of re-running.

Revision ID: 0010_interactions_saved_answer
Revises: 0009_interactions_history_idx
Create Date: 2026-09-22

Fix-plan item 10.2. What a person gets: clicking a past search shows the
answer they already got, at once, with no second search charged to them.
Today nothing stores an answer anywhere, so the only truthful thing the
history rail can do is ask the question again.

WHAT THIS ADDS: three nullable columns and three CHECK constraints on
`interactions`. No column is dropped, no column's meaning changes, and no
existing row is rewritten.

- `answer_markdown TEXT NULL`: the finished answer as it stood on screen,
  rendered to markdown in code from the run's own typed `token` events.
- `audience_depth TEXT NULL`: the depth that answer was written at, so a
  reader sees the depth they asked for and not today's default.
- `answer_trust_line TEXT NULL`: the one plain sentence the person read
  under their answer, for example "Sources disagree on at least one claim"
  (`DonePayload.trust_line`, built in code by `synthesis.trust.
  answer_trust_line`, never by a model).

  STORED BUT NOT SERVED, deliberately. The pinned wire contract for this
  feature carries `trust_signal` (one of four words) and no trust line, and
  that contract was not changed tonight. The column exists because the fact
  cannot be recovered later: measured across 150 live runs, ALL 35 that
  ended `answer` or `flag` carried a trust line, so without this column
  every answer saved tonight would permanently lack the sentence that told
  its reader how much to trust it. Deciding whether to SHOW it is the
  product owner's; see `testing/Developer/reports/2026-09-23_overnight/
  findings.md`.

## Signed-in accounts only, and it is the database that says so

Product-owner decision, 2026-09-22: store the answer for signed-in accounts
only, never for guests, and delete it with the account. The first half is
enforced here rather than only in Python, by
`ck_interactions_answer_account_only`:

    answer_markdown IS NULL OR left(owner_id, 5) = 'user:'

so a guest answer cannot reach disk even through a direct INSERT. The
exclusion is at the WRITE: a read-side filter would leave guest answers
sitting in the table, which is not what was approved.

`left(owner_id, 5) = 'user:'` rather than `owner_id LIKE 'user:%'` for one
practical reason: the second carries a `%`, and a `%` in DDL text is a
character a DBAPI can mistake for a parameter placeholder. The two
predicates say the same thing and only one of them has that edge.

## The bound, and why 32000

`production-standards` requires every stored string to carry a bound. The
number is measured rather than picked:

- Across the 150 live runs in
  `testing/Developer/reports/2026-09-22_10.3_consistency/runs.jsonl`, the
  longest answer was 1375 words, roughly 8,900 characters of prose.
- A table-bearing answer renders larger than its prose, because the visible
  content of a `table_row` token lives in `cells` and not in `text`.
  Measured on the real G-035 stream
  (`testing/Developer/reports/2026-09-22_isolate_search/round2/
  tokens_G-035.json`): 3,095 characters of markdown against a 1,448
  character text join, a factor of 2.1.
- So the worst realistic case is a longest-measured answer that is also a
  table: about 19,000 characters.

32000 clears that with headroom and is still a hard ceiling. It is
deliberately four times the 8000 that `adapters/mcp/server.py` and
`adapters/graphql/types.py` publish as `MAX_ANSWER_LENGTH`, and the
difference is not an inconsistency. Those two surfaces answer in one shot
and truncate on purpose. This column exists to reproduce exactly what was
on screen, so it must not truncate at all: an answer over the bound is
stored as NULL and the person is offered Run again, because a saved answer
that differs from the one they saw is worse than no saved answer.

## Rollback plan

`downgrade()` drops the three constraints and then the three columns. It is
complete and lossless in the only sense that matters here: every row's
identity, ownership, question, citations, classification and cost columns
are untouched, and the only thing lost is the saved answer text, which no
other feature reads and which the product regenerates by re-asking, which
is exactly today's behaviour. Running `downgrade` therefore returns the
product to what it does now rather than breaking it.

Proven, not asserted: `upgrade` then `downgrade` then `upgrade` was run
against a real PostgreSQL database and the table's column set compared at
each step (`tests/system_03_search_agent/data/test_migration_0010.py`).

## Expand-contract

This is the EXPAND half and it is the whole of the change. All three columns
are nullable with no server default and no backfill, so:

- Old application code deployed against the new schema keeps working: it
  never names these columns, and their NULL default satisfies every INSERT
  it issues.
- New application code deployed against the old schema fails only on the
  one new endpoint, never on the query path, because capture treats a
  failed write as best-effort (Section 16 stage 1).

There is no CONTRACT half to schedule: nothing is being replaced, so no
column becomes dead later. A future account-delete path is the one thing
that must still be written, and `feedback.history.
forget_saved_answers_for_account` exists, tested and unwired, so it cannot
ship without one. See `testing/Developer/reports/2026-09-23_overnight/
findings.md` for why no such path exists today.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_interactions_saved_answer"
down_revision = "0009_interactions_history_idx"
branch_labels = None
depends_on = None

_ACCOUNT_ONLY = "ck_interactions_answer_account_only"
_LENGTH = "ck_interactions_answer_markdown_length"
_DEPTH = "ck_interactions_audience_depth"

#: The measured bound. See this module's docstring for the measurement.
MAX_ANSWER_MARKDOWN_CHARS = 32000


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column("answer_markdown", sa.Text(), nullable=True),
    )
    op.add_column(
        "interactions",
        sa.Column("audience_depth", sa.Text(), nullable=True),
    )
    op.add_column(
        "interactions",
        sa.Column("answer_trust_line", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        _ACCOUNT_ONLY,
        "interactions",
        "answer_markdown IS NULL OR left(owner_id, 5) = 'user:'",
    )
    op.create_check_constraint(
        _LENGTH,
        "interactions",
        f"answer_markdown IS NULL OR char_length(answer_markdown) <= {MAX_ANSWER_MARKDOWN_CHARS}",
    )
    op.create_check_constraint(
        _DEPTH,
        "interactions",
        "audience_depth IS NULL OR audience_depth IN "
        "('clinical_brief','researcher','deep_technical','plain_language')",
    )


def downgrade() -> None:
    # Constraints first: dropping a column would take its constraints with
    # it, but naming them here keeps the rollback explicit about everything
    # it removes rather than relying on a cascade nobody reads.
    op.drop_constraint(_DEPTH, "interactions", type_="check")
    op.drop_constraint(_LENGTH, "interactions", type_="check")
    op.drop_constraint(_ACCOUNT_ONLY, "interactions", type_="check")
    op.drop_column("interactions", "answer_trust_line")
    op.drop_column("interactions", "audience_depth")
    op.drop_column("interactions", "answer_markdown")
