"""Session memory: the bounded in-conversation summary, stored per session.

Revision ID: 0007_session_memory
Revises: 0006_guest_source_daily_usage
Create Date: 2026-08-20

Adds `sessions.memory`, a JSONB column holding one `SessionMemorySummary`
(Section 14.3), for build phase 4.5's T-4.5-05.

Why a column on `sessions` rather than a new table or an in-process cache.

The summary is exactly one object per session with no independent identity,
no history worth querying, and no rows to join against, so a table would add
a join and a lifecycle for nothing. An in-process dict was the cheaper
option and was rejected on two counts: it does not survive a restart, so a
conversation loses its context whenever the app redeploys, and it is not
shared across workers, so the same session gets different memory depending
on which worker answers. Both failures are invisible in a single-process
development run and obvious in production.

The `sessions` row also already carries `user_id`, which is what makes the
ownership check in `core/session_memory.load_for_caller` possible at all.
That check closes F-4.1-A-15, boarded at build phase 4.1: an MCP caller can
pass any `session_id` it likes, and the moment memory became readable by that
id, naming someone else's session would have handed over their conversation.
Storing the memory next to its owner is what makes "is this yours" a question
the database can answer.

Nullable with no server default, so every existing session row is valid
untouched and a session that has not accumulated memory yet is NULL rather
than an empty object. The expand-contract rule holds: this revision only
adds, nothing reads the column until the application code that owns it
deploys, and the downgrade drops only what the upgrade created.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_session_memory"
down_revision = "0006_guest_source_daily_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("memory", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "memory")
