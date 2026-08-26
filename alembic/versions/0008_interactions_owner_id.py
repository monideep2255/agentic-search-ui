"""interactions.owner_id: the fact a feedback ownership check now reads (F-4.6-01).

Revision ID: 0008_interactions_owner_id
Revises: 0007_session_memory
Create Date: 2026-08-21

Adds `interactions.owner_id`, a nullable TEXT column holding the exact
namespaced principal string (`user:<uuid>` or `guest:<uuid>`) that
`feedback.capture.assemble_interaction` already has in hand when it builds
a row, for build phase 4.6's F-4.6-01.

Why this column exists rather than deriving ownership at check time.

`feedback/writer.py` shipped answering "is this row yours" for a guest by
reading the ownership envelope `core/session_memory.py` writes into
`sessions.memory`. That envelope is written LAZILY, on the first turn that
resolves an entity or grounds a finding, so a guest whose turn resolved
nothing had no envelope and every feedback attempt on that row was refused,
including the true owner's. Fail-closed was the right direction and the
wrong outcome: a control that refuses every guest passes every attack test
and destroys the product, the exact shape build phase 4.10's premise gate
named.

The fix is not a better derivation. It is to stop deriving the owner and
start recording it, the same lesson build phase 4.3 paid for twice: a check
that asks a proxy for safety instead of checking the value ships the same
critical again three rounds later. `owner_id` is recorded once, at capture
time, from `Query.owner_id`, the same value `assemble_interaction` already
uses to compute `session_id` (`core.session_memory.session_row_key`). The
ownership check in `write_feedback` becomes a direct compare against this
column: no session lookup, no envelope, no branch on whether `user_id` is
NULL.

Why a column on `interactions` rather than reusing `sessions.memory`'s
envelope, or widening it.

The envelope answers "who owns this SESSION". Capture can run on a turn
that never touched session memory at all (a Guardrail refusal, a turn that
resolved nothing), so a session-keyed envelope can never be guaranteed to
exist by the time a row needs to answer ownership for itself. Recording the
fact directly on the row it describes removes that dependency entirely:
every row `write_interaction` ever writes carries its own answer from the
moment it is written, not from whatever another module happened to do on
some other turn of the same session.

Why nullable with no default, matching 0007's expand-contract shape.

Every row written by this repository before this revision deploys has no
recorded owner: capture had no column to put one in until now. Nullable
with no server default is what makes the revision safe to run unchanged
against a populated `interactions` table, and it is also the honest
representation of those rows' actual state, an indeterminate owner, not a
guessed one. `write_feedback`'s ownership check treats a NULL `owner_id` as
refused for every caller, never as "unowned and claimable" and never as
"owned by whoever asks": NULL must not mean "anyone", the exact
`(None or None) != (None or None)` shape that made every guest one
principal in build phase 4.5 (F-4.5-A-02). A pre-migration row simply
cannot receive feedback until a query never happens for it again; that row
is already answered and done, so the cost is nothing in practice and it is
recorded here rather than left to be rediscovered.

Expand-contract: this revision only adds a column, nothing reads it until
the application code that owns it deploys in the same change, and the
downgrade drops only what the upgrade created.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_interactions_owner_id"
down_revision = "0007_session_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column("owner_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interactions", "owner_id")
