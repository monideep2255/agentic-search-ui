"""interactions: a composite index matching GET /v1/history's own query (F-4.13-A-03).

Revision ID: 0009_interactions_history_idx
Revises: 0008_interactions_owner_id
Create Date: 2026-08-27

Named `..._history_idx` rather than the longer, more descriptive name this
revision was first written under (`0009_interactions_owner_history_
index`): `alembic_version.version_num` is `VARCHAR(32)` and the longer id
does not fit, measured directly (`psycopg2.errors.StringDataRightTruncation`
on `UPDATE alembic_version ... SET version_num='0009_interactions_owner_
history_index'`, after the index itself had already built, since
`CREATE INDEX CONCURRENTLY` inside `autocommit_block()` commits
independently of alembic's own version-stamping statement). The index this
revision creates was dropped and rebuilt under the shorter id once this
was caught, so the deployed history matches what shipped.

`feedback.history.list_history` (build phase 4.13, T-4.13-01) issues:

    SELECT trace_id, query_text, created_at, trust_signal, citations
    FROM interactions
    WHERE owner_id = :owner_id
    ORDER BY created_at DESC, id DESC
    LIMIT :limit

`interactions.owner_id` carried no index of its own (0008 above added the
COLUMN, not an index on it), so this query paid a scan proportional to
every row every caller has EVER had captured, not the calling caller's
own rows, plus a `Sort` node, on every call. `GET /v1/history` is hit on
every page load by every signed-in visitor, so that cost was paid on the
hottest possible path. Measured against the live `search_agent_users`
database at 22,938 rows, for a REAL caller holding actual rows (`owner_id
= 'guest:11111111-1111-1111-1111-111111111111'`, 29 rows), the
representative case, before and after this revision, index dropped and
rebuilt around the measurement rather than reasoned about:

    -- BEFORE. `idx_interactions_created_at` (0001) lets the planner avoid
    -- a full Seq Scan by walking dates, but it still has to inspect and
    -- discard every row that fails the owner_id filter along the way.
    Limit  (cost=91.39..1851.34 rows=20 width=191) (actual time=18.103..18.105 rows=20 loops=1)
      Buffers: shared hit=13497
      ->  Incremental Sort  (cost=91.39..2643.32 rows=29 width=191) (actual time=18.101..18.102 rows=20 loops=1)
            Sort Key: created_at DESC, id DESC
            Presorted Key: created_at
            ->  Index Scan using idx_interactions_created_at on interactions
                  (cost=0.29..2642.02 rows=29 width=191) (actual time=17.843..18.041 rows=21 loops=1)
                  Filter: (owner_id = 'guest:1111...'::text)
                  Rows Removed by Filter: 21839
                  Buffers: shared hit=13488
    Execution Time: 18.193 ms

    -- AFTER. One Index Scan, no separate Sort node: the index already
    -- returns rows in `list_history`'s own output order.
    Limit  (cost=0.41..83.30 rows=20 width=191) (actual time=0.010..0.018 rows=20 loops=1)
      Buffers: shared hit=16
      ->  Index Scan using idx_interactions_owner_id_created_at_id on interactions
            (cost=0.41..120.59 rows=29 width=191) (actual time=0.009..0.017 rows=20 loops=1)
            Index Cond: (owner_id = 'guest:1111...'::text)
            Buffers: shared hit=16
    Execution Time: 0.025 ms

18.193ms down to 0.025ms, roughly 728x, and 13497 buffer hits down to 16.
Unlike the plan it replaces, the new one's cost no longer scales with the
total size of `interactions`: this `Index Scan` on `owner_id` costs the
same whether the table holds 23,000 rows or 23,000,000.

A second, honest data point rather than a cherry-picked one: for a
`owner_id` NOT present in the table at all (a probe an attacker or a
revoked credential could send), the planner's own row estimate for a
value it has never seen picks a `Bitmap Heap Scan` over the same new
index instead of a plain `Index Scan`, a different plan shape for the
zero-rows-returned case, not a regression: 31.587ms (`Seq Scan`, the
ORIGINAL plan, 22,938 rows removed by filter) down to 0.507ms. Both real
and nonexistent callers get the same order-of-magnitude win; the PLAN
PostgreSQL picks to deliver it differs by which case it is.

Why `created_at DESC, id DESC` rather than a plain `owner_id` index alone.
An index on `owner_id` by itself would still need a `Sort` node after
finding the matching rows, since a single-column btree index carries no
ordering guarantee among rows that tie on that column. Trailing `created_at
DESC` and `id DESC` in the SAME index, in the SAME order `list_history`'s
own `ORDER BY` uses, lets the planner walk the index in the exact output
order and skip the `Sort` node entirely for the representative case above.

Why `CREATE INDEX CONCURRENTLY` rather than a plain `CREATE INDEX`, stated
deliberately rather than assumed. A plain `CREATE INDEX` takes a
`SHARE` lock on the table for the DURATION of the build, which blocks
every `INSERT` and `UPDATE` against `interactions` until the index
finishes, and `interactions` is Section 16's append-only capture table:
every real query this product answers writes one row to it. On THIS
database, 22,938 rows, the build is near-instant and that lock would be
unnoticeable. The deployed database is not this one and is not assumed to
stay this size: `CONCURRENTLY` costs a slower build and a mandatory
non-transactional migration (below) in exchange for never blocking a
writer, which is the correct trade for a table every real query appends to
in production. The downgrade drops the same index `CONCURRENTLY` for the
identical reason in reverse.

`CREATE INDEX CONCURRENTLY` and `DROP INDEX CONCURRENTLY` cannot run
inside a transaction block; PostgreSQL rejects both with an error if
attempted inside one. Alembic wraps a migration's operations in one
transaction by default, so both operations below run inside
`op.get_context().autocommit_block()`, Alembic's documented mechanism for
exactly this case (`CREATE INDEX CONCURRENTLY`, `VACUUM`, and similar
statements that refuse to run transactionally).

A NOTE FOR THE NEXT PERSON, recorded here because it has already cost real
debugging time once and this phase is the second migration in this
repository's history. Adding an alembic revision destroys THIS PHASE'S OWN
ability to re-measure a test-suite baseline against an earlier commit
in the shared development database: a worktree checked out at a commit
before this revision cannot resolve `0009_interactions_history_idx`,
since the file does not exist there, and every test touching the
user database errors at setup with `alembic.script.revision.
ResolutionError`, which reads exactly like a wave of new regressions and
is not one. Full account: `LEARNINGS.md`'s 2026-08-21 entry ("any build
phase that adds an alembic migration, and every baseline re-measurement").
A baseline re-measurement on this branch, from this point forward, must
run against its own database, never the shared development one.

Expand-contract: this revision only adds an index. Nothing in the query
shape changes, and the downgrade drops only what the upgrade created.
"""

from alembic import op

revision = "0009_interactions_history_idx"
down_revision = "0008_interactions_owner_id"
branch_labels = None
depends_on = None

_INDEX_NAME = "idx_interactions_owner_id_created_at_id"


def upgrade() -> None:
    # Raw DDL, matching 0001's own precedent for `created_at DESC`: per-column
    # sort direction in a composite index is not expressible through
    # `op.create_index()`'s plain column-name list, and `CONCURRENTLY` needs
    # to run outside alembic's default per-migration transaction (see this
    # revision's own docstring).
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {_INDEX_NAME} "
            "ON interactions (owner_id, created_at DESC, id DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
