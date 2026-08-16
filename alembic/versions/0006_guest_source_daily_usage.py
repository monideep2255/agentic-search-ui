"""Guest source daily usage: the share of the day any one source may take.

Revision ID: 0006_guest_source_daily_usage
Revises: 0005_guest_attempts
Create Date: 2026-08-15

Adds the `guest_source_daily_usage` table F-4.10-V-01 needs
(`tracker/phase_4.10.md`, design decision 8). Hand-written directly from the
`GuestSourceDailyUsage` model in
`system_03_search_agent/data/models.py`, matching its exact column set,
default and constraint, the same relationship 0004 and 0005 have to their
own models.

Why a THIRD counter when 0004 and 0005 already added two. 0005's
`attempts_used` bounds an identity, and `POST /auth/guest` mints identities
for free. 0004's `guest_daily_usage` bounds the day, and holds the money,
but says nothing about who spent it. Neither answers how much of the day one
caller may take. Measured on this branch with the shipped defaults, the mint
throttle live and zero mints refused: 20 identities from one apparent source
took all 200 of the day's anonymous runs in 1.84 seconds, and every other
anonymous visitor was refused until UTC midnight. This table is keyed on the
source, which is the one thing that attack did not vary.

`source_hash` stores `auth/router.py`'s `_hash_ip` output, a keyed
HMAC-SHA256 hex digest of the connection address. No raw IP is stored here
or anywhere else, and the column is sized to the digest's exact 64
characters rather than left unbounded.

Expand-contract rollback: this revision only ADDS a new table, and no
existing table gains a foreign key pointing INTO it, so `upgrade()` is a
pure expand step with no backward-compatibility hazard for code still
running revision 0005 (a process on 0005 never touches a table it does not
know about, and simply enforces one fewer bound). `downgrade()` is a pure
contract step, a single `DROP TABLE`: nothing references
`guest_source_daily_usage`, and it holds no foreign key of its own in
either direction, so no other table, index or constraint needs adjustment
on rollback.

One consequence of that rollback worth stating rather than discovering, the
same shape 0004 and 0005 each state for their own: downgrading to 0005
removes the only bound on how much of the shared day ONE source can take,
which restores exactly the drain measured above. Rolling back is a decision
about exposure, not only about schema. It is safe with anonymous access
disabled and is not safe with it live on a public URL.

Nothing prunes old days. Row growth is bounded by the number of distinct
sources that actually STARTED an anonymous run on a given day, since a row
appears only after a mint the throttle admitted and a run the daily ceiling
admitted. Retention is build phase 6.1's hardening pass, recorded here
rather than left to be discovered.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_guest_source_daily_usage"
down_revision = "0005_guest_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_source_daily_usage",
        # The composite key IS the invariant: one row per source per UTC
        # day. Deliberately not a surrogate id with a unique index, which a
        # later migration could drop without anyone noticing the counter had
        # started double-counting. Same reasoning as 0004's `day` key.
        sa.Column("day", sa.Date(), primary_key=True, nullable=False),
        sa.Column("source_hash", sa.String(64), primary_key=True, nullable=False),
        sa.Column("runs_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("runs_used >= 0", name="ck_guest_source_daily_usage_runs_used"),
    )


def downgrade() -> None:
    op.drop_table("guest_source_daily_usage")
