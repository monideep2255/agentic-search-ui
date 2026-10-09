"""interactions: the risk tier, so a reopened answer shows its high-risk tag.

Revision ID: 0011_interactions_risk_tier
Revises: 0010_interactions_saved_answer
Create Date: 2026-10-08

Card 71. What a person gets: an answer that showed the "High-risk claim" tag
when it was live shows the same tag when they reopen it from history. An
answer saved before this change shows no tag, rather than a wrong one.

WHAT THIS ADDS: one nullable column and one CHECK constraint on
`interactions`. No column is dropped, no column's meaning changes, no
existing row is rewritten, and there is no backfill.

- `risk_tier TEXT NULL`: the worst risk tier of the run's `trust_signal`
  events, the value the live answer's tag is built from
  (`frontend/src/hooks/useRunView.ts`). NULL means "not recorded": every row
  saved before this revision, a guest's row, and any run that saved no
  answer. A reader must treat NULL as "show no tag", never as "low".

The product owner approved this one migration on 2026-10-08.

## The bound

`ck_interactions_risk_tier_length` limits the value to 16 characters, the
same bound `TrustSignalPayload.risk_tier` carries (`max_length=16`). It is a
length bound and not a list of tiers on purpose. The wire field is a bare
string, the live tag treats an unrecognised tier as the most severe, and a
CHECK on a fixed list would make the database refuse a saved answer the day
the backend names a new tier. Capture is best-effort, so that refusal would
silently lose the whole saved answer. The tiers that exist today are `low`,
`high` and `unknown`; the live code also ranks `moderate` and `critical`.

## Rollback plan

`downgrade()` drops the constraint and then the column. The only thing lost
is the stored tier, which no other feature reads; a reopened answer then
shows no tag, which is exactly what it does today.

## Expand-contract

This is the EXPAND half and the whole of the change. The column is nullable
with no server default and no backfill, so old application code against the
new schema never names it, and new application code against the old schema
fails only in capture's best-effort write.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_interactions_risk_tier"
down_revision = "0010_interactions_saved_answer"
branch_labels = None
depends_on = None

_LENGTH = "ck_interactions_risk_tier_length"

#: Mirrors `TrustSignalPayload.risk_tier`'s `max_length`.
MAX_RISK_TIER_CHARS = 16


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column("risk_tier", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        _LENGTH,
        "interactions",
        f"risk_tier IS NULL OR char_length(risk_tier) <= {MAX_RISK_TIER_CHARS}",
    )


def downgrade() -> None:
    op.drop_constraint(_LENGTH, "interactions", type_="check")
    op.drop_column("interactions", "risk_tier")
