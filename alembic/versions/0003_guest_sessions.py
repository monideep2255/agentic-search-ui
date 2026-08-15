"""Guest sessions: the anonymous visitor's counted allowance.

Revision ID: 0003_guest_sessions
Revises: 0002_auth_hardening
Create Date: 2026-08-15

Adds the `guest_sessions` table T-4.10-02 needs (design decision 3,
`tracker/phase_4.10.md`): one row per anonymous visitor, holding the
atomic run count the guest allowance is spent against. Hand-written
directly from the `GuestSession` model in
`system_03_search_agent/data/models.py`, matching that model's exact
column set, defaults, and constraint, the same relationship
0001_user_data_schema.py has to the other five ORM models.

Expand-contract rollback: this revision only ADDS a new table, and no
existing table gains a foreign key pointing INTO it, so `upgrade()` is a
pure expand step with no backward-compatibility hazard for code still
running the previous revision (a process on 0002 simply never touches a
table it does not know about). `downgrade()` is a pure contract step, a
single `DROP TABLE`: nothing else references `guest_sessions`, so no
other table, index, or constraint needs adjustment on rollback.
`guest_sessions.migrated_to_user_id` points OUT to `users.id` with
`ON DELETE SET NULL`, so deleting a user row never fails or cascades
because of this table, in either direction of the migration.

`pgcrypto` (for `gen_random_uuid()`) is already enabled by
0001_user_data_schema.py; this revision does not re-declare it and does
not drop it on downgrade, since 0001's tables still depend on it.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_guest_sessions"
down_revision = "0002_auth_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("runs_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "migrated_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("runs_used >= 0", name="ck_guest_sessions_runs_used"),
    )


def downgrade() -> None:
    op.drop_table("guest_sessions")
