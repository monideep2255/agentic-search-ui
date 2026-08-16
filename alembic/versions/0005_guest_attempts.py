"""Guest attempts: the per-identity bound the refusal refund removed.

Revision ID: 0005_guest_attempts
Revises: 0004_guest_daily_usage
Create Date: 2026-08-15

Adds `guest_sessions.attempts_used`, the counter F-4.10-R-01 needs
(`tracker/phase_4.10.md`, design decisions 3 and 8). Hand-written directly
from the `GuestSession` model in
`system_03_search_agent/data/models.py`, matching its exact column
definition, default and CHECK constraint, the same relationship
0003_guest_sessions.py has to that model.

Why a second counter on a table that already counts. `runs_used` counts
ANSWERS and is refunded when the guardrail refuses a run
(F-4.10-A-04), so that a visitor is not pushed toward the sign-in wall by
questions that were never answered. That refund removed the only
per-identity bound: a caller who sends nothing but refusable text never
advances `runs_used` at all, so the only counter that still moves is the
SHARED daily ceiling in `guest_daily_usage`. Measured on this branch
before this revision existed: one guest token, minted once, started 200
paid pipelines in 1.68 seconds with its own allowance still reading
`used: 0`, exhausted the whole day's anonymous budget, and a brand-new
visitor asking a legitimate question was then refused 429.
`attempts_used` is never refunded, so it bounds that caller at
`ATTEMPT_ALLOWANCE` runs regardless of how each one ends.

Expand-contract rollback: `upgrade()` adds ONE nullable-free column with a
server default of 0, which is a pure expand step. A process still running
revision 0004 never names this column in any statement it issues (the
0004-era `_SPEND_STATEMENT` touches `runs_used` and `last_seen_at` only)
and its INSERTs still succeed because the server default supplies a value,
so old and new code can run against this schema at the same time.
`downgrade()` is a pure contract step, a single `DROP COLUMN`: no index,
foreign key or other constraint references it, and the table's own
`ck_guest_sessions_runs_used` constraint is untouched. The CHECK added
here is dropped implicitly with its column.

One consequence of that rollback worth stating rather than discovering:
downgrading to 0004 removes the per-identity bound on refused runs, which
restores exactly the drain measured above. Like 0004's own note, rolling
back is a decision about exposure, not only about schema. It is safe with
anonymous access disabled and is not safe with it live on a public URL.

Existing rows: every `guest_sessions` row that predates this revision gets
`attempts_used = 0`, so an in-flight guest is credited with a full attempt
allowance rather than being locked out mid-visit. That direction is
deliberate. Backfilling `attempts_used = runs_used` was considered and
rejected: `runs_used` is post-refund, so it under-counts attempts anyway,
and starting a live visitor at a number they cannot see would refuse them
for something that happened before the rule existed.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_guest_attempts"
down_revision = "0004_guest_daily_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guest_sessions",
        sa.Column(
            "attempts_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_guest_sessions_attempts_used",
        "guest_sessions",
        "attempts_used >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_guest_sessions_attempts_used", "guest_sessions", type_="check"
    )
    op.drop_column("guest_sessions", "attempts_used")
