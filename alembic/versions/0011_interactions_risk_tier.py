"""interactions: the risk tier, so a reopened answer shows its high-risk tag.

Revision ID: 0011_interactions_risk_tier
Revises: 0010_interactions_saved_answer
Create Date: 2026-10-08

Card 71. What a person gets: an answer that showed the "High-risk claim" tag
when it was live shows the same tag when they reopen it from history. An
answer saved before this change shows no tag, rather than a wrong one.

WHAT THIS ADDS: one nullable column on `interactions`. No column is
dropped, no column's meaning changes, no existing row is rewritten, and
there is no backfill.

- `risk_tier TEXT NULL`: the worst risk tier of the run's `trust_signal`
  events, the value the live answer's tag is built from
  (`frontend/src/hooks/useRunView.ts`). NULL means "not recorded": every row
  saved before this revision, a guest's row, and any run that saved no
  answer. A reader must treat NULL as "show no tag", never as "low".

The product owner approved this one migration on 2026-10-08.

## The bound lives in code, not in a CHECK

The tier is at most 16 characters, the bound `TrustSignalPayload.risk_tier`
carries (`max_length=16`). Capture enforces it (`feedback/capture.py`,
`feedback/contracts.py`'s `MAX_RISK_TIER_CHARS`): a tier outside it is
stored as NULL, so the reopened answer loses only its tag, never the saved
answer. The first build also added a database CHECK. The fix round removed
it for two reasons (A-71T-03, A-71T-11, J-71T-04): adding it validated
every existing row while the ADD COLUMN's exclusive lock was held, and a
refused value would have failed capture's best-effort write and lost the
whole saved answer. Without it, this revision is a catalog-only ADD COLUMN
(nullable, no default), which rewrites and scans nothing.

## Rollback plan, in this order

1. Run `alembic downgrade 0010_interactions_saved_answer` from THIS build's
   code. Only this build's tree has the 0011 file; the previous build's
   tree cannot read revision 0011 at all.
2. Then, at once, redeploy the previous build. Never before step 1: the
   previous build's start command runs `alembic upgrade head`, which fails
   on an unknown revision 0011, and the service does not start (A-71T-05).

Between the two steps this build is still serving on the old schema, and
that breaks it: reopening any saved answer fails with a server error,
because the read selects `risk_tier`, and new searches are not saved to
history (J-71T-10, A-71T-04). Keep that window to the minutes the redeploy
takes, and never leave this build serving after a downgrade. `downgrade()`
itself loses only the stored tiers.

## Expand-contract

This is the EXPAND half and the whole of the change. Old application code
against the new schema never names the column and works unchanged. New
application code against the old schema does NOT work: it fails every
saved-answer read and every capture write. A normal deploy never reaches
that order, because the start command in `railway.json` runs `alembic
upgrade head` before the server starts; only the rollback window above
does.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_interactions_risk_tier"
down_revision = "0010_interactions_saved_answer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column("risk_tier", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interactions", "risk_tier")
