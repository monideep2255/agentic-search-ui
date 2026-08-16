"""Guest daily usage: the system-wide ceiling on anonymous spend.

Revision ID: 0004_guest_daily_usage
Revises: 0003_guest_sessions
Create Date: 2026-08-15

Adds the `guest_daily_usage` table design decision 8 needs
(`tracker/phase_4.10.md`): one row per UTC day, counting every anonymous
run the whole system has started that day. Hand-written directly from the
`GuestDailyUsage` model in `system_03_search_agent/data/models.py`,
matching its exact column set, default and constraint, the same
relationship 0003_guest_sessions.py has to `GuestSession`.

Why a second counter when 0003 already added one: `guest_sessions.
runs_used` is keyed on a guest identity, and `POST /auth/guest` mints
identities for free, so it bounds a variable the caller controls the
supply of. The build phase 4.10 adversary round measured 40 paid
pipelines accepted in 0.25 seconds by minting one guest per run
(F-4.10-A-01), with no backstop behind it: the per-user daily cap is
skipped for a caller with no `users` row, and the system-wide dollar cap
sums a table nothing writes yet (F-2.0-04). This table is keyed on the
calendar day, which nobody controls the supply of.

Expand-contract rollback: this revision only ADDS a new table, and no
existing table gains a foreign key pointing INTO it, so `upgrade()` is a
pure expand step with no backward-compatibility hazard for code still
running the previous revision (a process on 0003 never touches a table it
does not know about, and simply enforces one fewer cap). `downgrade()` is
a pure contract step, a single `DROP TABLE`: nothing references
`guest_daily_usage`, and it holds no foreign key of its own in either
direction, so no other table, index or constraint needs adjustment on
rollback.

One consequence of that rollback worth stating rather than discovering:
downgrading to 0003 removes the only enforced spending bound on an
anonymous caller, since the two pre-existing cost caps cannot reach one.
Rolling back is therefore a decision about exposure, not only about
schema. It is safe with anonymous access disabled and is not safe with it
live on a public URL.

`gen_random_uuid()` is not used here; this table's primary key is the
calendar day itself, so `pgcrypto` is irrelevant to this revision in
either direction.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_guest_daily_usage"
down_revision = "0003_guest_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_daily_usage",
        # The UTC calendar day, and the primary key. Deliberately not a
        # surrogate id: one row per day is the invariant, and making the
        # day itself the key is what enforces it, rather than a unique
        # index that a later migration could drop without anyone noticing
        # the counter had started double-counting.
        sa.Column("day", sa.Date(), primary_key=True, nullable=False),
        sa.Column("runs_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("runs_used >= 0", name="ck_guest_daily_usage_runs_used"),
    )


def downgrade() -> None:
    op.drop_table("guest_daily_usage")
