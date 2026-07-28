"""Auth hardening: case-insensitive email, refresh-hash uniqueness, absolute session ceiling.

Revision ID: 0002_auth_hardening
Revises: 0001_user_data_schema
Create Date: 2026-07-28

Closes the schema half of three adversary findings triaged on 2026-07-28
(see tracker/phase_1.1.md):

- F-1.1-08: `users.email` is unique byte-exact only, so `USER@example.com`
  and `user@example.com` are two accounts. This revision normalizes every
  existing address and adds a unique index on `lower(email)`, so the
  guarantee holds at the database level and not only in application code.
- F-1.1-12: `auth_sessions.refresh_token_hash` carries neither a unique
  constraint nor an index, giving a sequential scan on every auth call and
  a latent 500 if two rows ever share a hash. This revision adds one
  unique index, which is both halves.
- F-1.1-07: every rotation renews `expires_at`, so a continuously rotating
  refresh-token holder never expires. This revision adds
  `auth_sessions.absolute_expires_at`, the ceiling the router carries
  forward unchanged across a whole rotation chain.

Pre-existing conflicting rows are quarantined, never deleted. Both
quarantine paths preserve the original value: an email's original spelling
is written to `users.profile` under the key this module names below, and a
duplicate `auth_sessions` row keeps every column except the hash it
collided on. `downgrade()` reverses each step, restoring the quarantined
emails from `profile` and dropping the key again.

The quarantined refresh-token hash is deliberately not restorable: the
sentinel written over it is one-way, because restoring a duplicate hash
would recreate the exact ambiguity F-1.1-12 is about. The affected rows are
revoked as part of the same statement, so nothing usable is lost; the token
they held could not have been the live one for both rows anyway.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_auth_hardening"
down_revision = "0001_user_data_schema"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# Where an email's pre-normalization spelling is preserved, so nothing this
# revision rewrites is unrecoverable and `downgrade()` can put it back.
_ORIGINAL_EMAIL_KEY = "pre_0002_email"

# The absolute ceiling backfilled onto rows that predate this revision,
# anchored to each row's own `created_at`. Matches
# `auth.router._REFRESH_TOKEN_ABSOLUTE_TTL`; the two are stated in their
# own units because a migration must not import application code.
_ABSOLUTE_TTL_SQL = "interval '90 days'"


def upgrade() -> None:
    connection = op.get_bind()

    # ---------------------------------------------------------------
    # F-1.1-07: the absolute ceiling column.
    # ---------------------------------------------------------------
    # Nullable, expand-contract style: existing rows get a backfilled
    # value below, and the router treats a NULL as "anchored to
    # created_at" so a row written by an older deploy is still capped.
    op.add_column(
        "auth_sessions",
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    backfilled = connection.execute(
        sa.text(
            "UPDATE auth_sessions "
            f"SET absolute_expires_at = created_at + {_ABSOLUTE_TTL_SQL} "
            "WHERE absolute_expires_at IS NULL"
        )
    ).rowcount
    logger.info("0002: backfilled absolute_expires_at on %s auth_sessions rows", backfilled)

    # ---------------------------------------------------------------
    # F-1.1-12: quarantine duplicate refresh-token hashes, then enforce
    # uniqueness.
    # ---------------------------------------------------------------
    quarantined_sessions = connection.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY refresh_token_hash
                           ORDER BY created_at, id
                       ) AS rn
                  FROM auth_sessions
            )
            UPDATE auth_sessions AS s
               SET refresh_token_hash = 'quarantined-0002:' || s.id::text,
                   revoked_at = COALESCE(s.revoked_at, now())
              FROM ranked
             WHERE ranked.id = s.id
               AND ranked.rn > 1
            RETURNING s.id
            """
        )
    ).fetchall()
    if quarantined_sessions:
        # Row ids only. A refresh-token hash is never logged.
        logger.warning(
            "0002: quarantined %s duplicate auth_sessions rows before adding the "
            "unique index; each kept every column except the colliding hash and "
            "is now revoked. Row ids: %s",
            len(quarantined_sessions),
            ", ".join(str(row[0]) for row in quarantined_sessions),
        )
    op.create_index(
        "ux_auth_sessions_refresh_token_hash",
        "auth_sessions",
        ["refresh_token_hash"],
        unique=True,
    )

    # ---------------------------------------------------------------
    # F-1.1-08: normalize email, quarantine case-variant duplicates, then
    # enforce case-insensitive uniqueness.
    # ---------------------------------------------------------------
    # Step 1: preserve the original spelling of every row this revision is
    # about to rewrite, so nothing is lost and downgrade can restore it.
    preserved = connection.execute(
        sa.text(
            """
            UPDATE users
               SET profile = jsonb_set(
                       COALESCE(profile, '{}'::jsonb),
                       CAST(:key_path AS text[]),
                       to_jsonb(email),
                       true
                   )
             WHERE email <> lower(btrim(email))
                OR lower(btrim(email)) IN (
                       SELECT lower(btrim(email))
                         FROM users
                        GROUP BY lower(btrim(email))
                       HAVING count(*) > 1
                   )
            """
        ),
        {"key_path": "{" + _ORIGINAL_EMAIL_KEY + "}"},
    ).rowcount
    logger.info("0002: preserved the original email of %s users rows in profile", preserved)

    # Step 2: quarantine the losers of each case-insensitive collision
    # group. The earliest-created row in a group keeps the address; the
    # rest get a marked, still-valid address of the form
    # `dup2+user@example.com`, which is unique, obviously not the real
    # address, and reversible from `profile` on downgrade. No row is
    # deleted, and no password hash or session is touched.
    quarantined_users = connection.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       lower(btrim(email)) AS normalized,
                       row_number() OVER (
                           PARTITION BY lower(btrim(email))
                           ORDER BY created_at, id
                       ) AS rn
                  FROM users
            )
            UPDATE users AS u
               SET email = 'dup' || ranked.rn::text || '+' || ranked.normalized
              FROM ranked
             WHERE ranked.id = u.id
               AND ranked.rn > 1
            RETURNING u.id, u.email
            """
        )
    ).fetchall()
    if quarantined_users:
        logger.warning(
            "0002: quarantined %s users rows that differed only by email case or "
            "surrounding whitespace. None was deleted; each keeps its row, its "
            "password hash, and its sessions, and its original address is in "
            "profile.%s. Rewritten to: %s",
            len(quarantined_users),
            _ORIGINAL_EMAIL_KEY,
            ", ".join(str(row[1]) for row in quarantined_users),
        )

    # Step 3: normalize what remains. After step 2 no two rows can collide
    # on lower(btrim(email)), so this cannot raise.
    normalized = connection.execute(
        sa.text("UPDATE users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email))")
    ).rowcount
    logger.info("0002: normalized the email of %s users rows to lowercase", normalized)

    # Step 4: the guarantee itself. A functional unique index rather than a
    # UNIQUE constraint on the raw column, because only the functional form
    # rejects a case variant.
    op.execute("CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email))")


def downgrade() -> None:
    connection = op.get_bind()

    op.execute("DROP INDEX IF EXISTS ux_users_email_lower")

    # Restore every address this revision rewrote, then drop the key it
    # was preserved under, so `profile` is left exactly as it was found.
    restored = connection.execute(
        sa.text(
            """
            UPDATE users
               SET email = profile ->> :key,
                   profile = profile - :key
             WHERE profile ? :key
               AND profile ->> :key IS NOT NULL
            """
        ),
        {"key": _ORIGINAL_EMAIL_KEY},
    ).rowcount
    logger.info("0002 downgrade: restored the original email of %s users rows", restored)

    op.drop_index("ux_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    # The quarantined hashes are deliberately not restored; see the module
    # docstring. Those rows stay revoked and unusable, which is the same
    # state a rotated session is in.

    op.drop_column("auth_sessions", "absolute_expires_at")
